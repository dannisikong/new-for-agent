"""
agent_core.py —— 可复用后端核心（供 Streamlit Web UI 调用）
=============================================================
- build_react_graph(model)：参数化的 ReAct 循环图（任意兼容模型）
- WebLLM：真实 LLM 工厂（OpenAI 兼容 / Hugging Face），注入用户 Token
- 演示模式：复用 app.MockAlfredLLM（无需 Token）

命令行版（app.py）与本模块共用同一套工具与图结构。
"""

import time
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, ToolMessage, HumanMessage
from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from tools import TOOLS, TOOL_NAMES, TOOL_DESCRIPTIONS
from tool_policy import validate
from tool_errors import corrective_tool_message
from audit_log import log_event
from app import MockAlfredLLM
from knowledge_retriever import EmbeddingClient, set_embedding_client
from agentic_rag import _memory  # 复用同一个 checkpointer（Sqlite/Memory 自动降级）


# ============================================================
# 真实 LLM 工厂：把用户在 Web 界面填的 Token / 模型包装成
# 标准 Runnable（bind_tools 后可直接驱动 ToolNode）
# ============================================================

class WebLLM(Runnable):
    """根据提供商构造真实 LLM 并绑定工具"""

    def __init__(self, provider: str, api_key: str, model_name: str,
                 base_url: str | None = None):
        if provider == "Hugging Face":
            from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
            endpoint = HuggingFaceEndpoint(
                repo_id=model_name,
                huggingfacehub_api_token=api_key,
                task="text-generation",
                temperature=0,  # 固定温度，保证相同问题回答稳定
            )
            self.llm = ChatHuggingFace(llm=endpoint, verbose=True)
        else:  # OpenAI 兼容（OpenAI / DeepSeek / Moonshot / 通义千问等）
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url or None,
                temperature=0,
                max_retries=2,  # L1: 网络抖动自动重试 2 次（指数退避）
            )
        self.llm = self.llm.bind_tools(TOOLS)

    def invoke(self, messages, config=None, **kwargs):
        return self.llm.invoke(messages, config=config)


# ============================================================
# 客户端缓存：相同 provider/api_key/model/base_url 复用同一个 LLM 实例，
# 底层 OpenAI/HF 连接池随之复用；embedding 配置未变化时不重置 client、
# 不清空已建好的向量索引，避免每次问答重复建连与重建索引（P3 单例复用）。
# ============================================================
_llm_cache: dict[tuple, Runnable] = {}
# 上次生效的 embedding 配置指纹：(base_url, emb_model, api_key)，None 表示纯 BM25
_last_emb_key: tuple | None = None


def _embedding_config(provider: str, api_key: str, base_url: str | None) -> tuple | None:
    """返回 OpenAI 兼容提供商的 embedding 配置指纹；其余提供商返回 None（纯 BM25）。"""
    if provider != "OpenAI 兼容":
        return None
    base = (base_url or "").lower()
    emb_model = "text-embedding-v3" if "dashscope" in base else "text-embedding-3-small"
    return (base_url or "https://api.openai.com/v1", emb_model, api_key)


def make_llm(provider: str, api_key: str, model_name: str,
             base_url: str | None = None) -> Runnable:
    """统一入口：演示模式返回 MockAlfredLLM，其余返回 WebLLM。
    同时按提供商注入 embedding 配置（OpenAI 兼容 → 开启向量召回；其余 → 纯 BM25）。
    相同配置直接复用已缓存的客户端，不重复建立连接。"""
    global _last_emb_key

    cache_key = (provider, api_key, model_name, base_url or "")
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    if provider == "演示模式（无需 Token）":
        set_embedding_client(None)
        _last_emb_key = None
        llm = MockAlfredLLM()
    else:
        llm = WebLLM(provider, api_key, model_name, base_url)
        emb_cfg = _embedding_config(provider, api_key, base_url)
        if emb_cfg is None:
            set_embedding_client(None)
            _last_emb_key = None
        elif emb_cfg != _last_emb_key:
            # 只有配置真正变化时才重建 embedding client 并清空旧向量索引
            set_embedding_client(
                EmbeddingClient(api_key, base_url or "https://api.openai.com/v1", emb_cfg[1])
            )
            _last_emb_key = emb_cfg
        # embedding 配置未变：保留既有 client 与已建向量索引，不重复初始化

    _llm_cache[cache_key] = llm
    return llm


# ============================================================
# 参数化 ReAct 循环图（与 app.py 同构，模型可替换）
# ============================================================

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def _safe_tool_node(state: AgentState, config=None):
    """安全工具分发（三层防护）：
    ① 工具名白名单：幻觉调用不存在的工具 → 返回错误列出可用工具让模型纠正；
    ② 参数级最小权限：工具名合法但参数越权（命令符/本地路径/超长/非法字符）→ 拒绝执行；
    ③ 执行失败按错误返回可纠正提示，不抛异常打断循环。
    每次调用写一条本地审计（成功/拒绝/报错）。"""
    last_msg = state["messages"][-1]
    tool_calls = getattr(last_msg, "tool_calls", None) or []

    thread_id = ((config or {}).get("configurable") or {}).get("thread_id", "default")
    trace_id = ((config or {}).get("configurable") or {}).get("trace_id", "no-trace")
    # 建立工具名 → 工具实例映射
    tool_map = {t.name: t for t in TOOLS}
    results = []

    for tc in tool_calls:
        name = tc.get("name", "")
        call_id = tc.get("id", "")
        args = tc.get("args", {}) or {}

        # ① 白名单校验：模型幻觉调用了不存在的工具
        if name not in TOOL_NAMES:
            available = "、".join(sorted(TOOL_NAMES))
            log_event("tool_denied", tool=name, thread_id=thread_id, trace_id=trace_id,
                      span=f"tool:{name}", args=args, ok=False,
                      error=f"工具名不存在：{name}")
            results.append(ToolMessage(
                content=f"❌ 工具「{name}」不存在。可用工具：{available}。"
                        f"请从上面选择正确的工具名重试，不要编造工具。",
                tool_call_id=call_id,
            ))
            continue

        # ② 参数级最小权限校验：工具名合法但参数越权，拒绝执行并让模型纠正
        ok, reason = validate(name, args)
        if not ok:
            log_event("tool_denied", tool=name, thread_id=thread_id, trace_id=trace_id,
                      span=f"tool:{name}", args=args, ok=False, error=reason)
            results.append(ToolMessage(
                content=f"⛔ 工具「{name}」的参数被最小权限策略拒绝：{reason}。"
                        f"请按要求修正参数后重试，不要尝试绕过限制。",
                tool_call_id=call_id,
            ))
            continue

        # 工具名合法、参数合法，正常执行（包计时，记 span 耗时）
        try:
            _t0 = time.perf_counter()
            result = tool_map[name].invoke(args)
            duration_ms = (time.perf_counter() - _t0) * 1000
            log_event("tool_call", tool=name, thread_id=thread_id, trace_id=trace_id,
                      span=f"tool:{name}", duration_ms=duration_ms,
                      args=args, ok=True, result_preview=str(result))
            results.append(ToolMessage(content=str(result), tool_call_id=call_id))
        except Exception as e:
            log_event("tool_error", tool=name, thread_id=thread_id, trace_id=trace_id,
                      span=f"tool:{name}", args=args, ok=False,
                      error=f"{e.__class__.__name__}: {e}")
            results.append(ToolMessage(
                content=corrective_tool_message(name, e),
                tool_call_id=call_id,
            ))

    return {"messages": results}


def build_react_graph(model: Runnable):
    """构建 assistant ↔ tools 的 ReAct 循环图"""

    def assistant(state: AgentState):
        response = model.invoke(state["messages"])
        return {"messages": [response]}

    builder = StateGraph(AgentState)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", _safe_tool_node)
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    return builder.compile(checkpointer=_memory)

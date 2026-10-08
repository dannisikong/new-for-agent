"""
agent_core.py —— 可复用后端核心（供 Streamlit Web UI 调用）
=============================================================
- build_react_graph(model)：参数化的 ReAct 循环图（任意兼容模型）
- WebLLM：真实 LLM 工厂（OpenAI 兼容 / Hugging Face），注入用户 Token
- 演示模式：复用 app.MockAlfredLLM（无需 Token）

命令行版（app.py）与本模块共用同一套工具与图结构。
"""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from tools import TOOLS
from app import MockAlfredLLM


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
            )
        self.llm = self.llm.bind_tools(TOOLS)

    def invoke(self, messages, config=None, **kwargs):
        return self.llm.invoke(messages, config=config)


def make_llm(provider: str, api_key: str, model_name: str,
             base_url: str | None = None) -> Runnable:
    """统一入口：演示模式返回 MockAlfredLLM，其余返回 WebLLM"""
    if provider == "演示模式（无需 Token）":
        return MockAlfredLLM()
    return WebLLM(provider, api_key, model_name, base_url)


# ============================================================
# 参数化 ReAct 循环图（与 app.py 同构，模型可替换）
# ============================================================

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def build_react_graph(model: Runnable):
    """构建 assistant ↔ tools 的 ReAct 循环图"""

    def assistant(state: AgentState):
        response = model.invoke(state["messages"])
        return {"messages": [response]}

    builder = StateGraph(AgentState)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    return builder.compile()

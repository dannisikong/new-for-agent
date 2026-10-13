"""
agentic_rag.py —— Agentic RAG 闭环（知识库智能问答）
========================================================
移植官方 tutorial_rag 的经典闭环：
  判断是否需要检索 → 检索 → 评分 →（相关）生成回答
                                 └→（不相关）重写问题 → 再检索（上限 2 轮）

召回层仍为 BM25（knowledge_retriever，关键词版）；
评分 / 重写 / 回答在演示模式用规则实现（无 Token 可跑通闭环），
真实模式用 LLM 实现（用户填入 Token / 模型后自动切换）。
"""

import os
import re
import time
import uuid
import subprocess
from typing import TypedDict, Annotated

# LangSmith 可观测性配置（API key 从环境变量读取，不硬编码）
os.environ.setdefault("LANGSMITH_TRACING", "true")
os.environ.setdefault("LANGSMITH_PROJECT", "new-for-agent")

import jieba
import jieba.posseg as pseg
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from knowledge_retriever import hybrid_search
from tools import web_search as _web_search_tool

# 飞书多维表格日志配置
_LARK_BASE_TOKEN = "MqOEbCudzaX3BJse04wcY13qn5b"
_LARK_TABLE_ID = "tbltCqeEor5PxBdP"


def _log_to_lark(record: dict):
    """把一轮问答记录写入飞书多维表格，失败不影响主流程。"""
    try:
        import json
        fields = {
            "request_id": record.get("request_id", ""),
            "问题": record.get("question", "")[:500],
            "最终回答": record.get("answer", "")[:2000],
            "召回文档数": record.get("doc_count", 0),
            "召回文档标题": record.get("doc_titles", "")[:500],
            "评分结果": [record.get("grade", "relevant")],
            "重写次数": record.get("rewrites", 0),
            "是否降级": [record.get("fallback", "正常")],
            "总耗时ms": record.get("duration_ms", 0),
            "trace": "\n".join(record.get("trace", []))[:2000],
        }
        cmd = [
            "lark-cli", "base", "+record-upsert",
            "--base-token", _LARK_BASE_TOKEN,
            "--table-id", _LARK_TABLE_ID,
            "--json", json.dumps(fields, ensure_ascii=False),
            "--as", "user",
        ]
        subprocess.run(cmd, capture_output=True, timeout=10)
    except Exception:
        pass  # 日志失败不影响主流程

# 多轮记忆 checkpointer：优先 Sqlite（持久化），未装包时降级 Memory（重启丢失）
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    import sqlite3
    _conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
    _memory = SqliteSaver(_conn)
    try:
        _memory.setup()
    except Exception:
        pass
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver
    _memory = MemorySaver()

MAX_REWRITES = 2
TOP_K = 3

# 查询缓存：规范化问题 → {answer, trace, hits}
# 相同问题直接复用上次检索结果，避免重复检索（无状态图 → 带记忆）
_answer_cache: dict[str, dict] = {}


def _norm_question(question: str) -> str:
    return re.sub(r"\s+", "", question).strip().lower()


def _cache_hit(question: str) -> dict | None:
    key = _norm_question(question)
    return _answer_cache.get(key)


def _cache_store(question: str, answer: str, trace: list):
    _answer_cache[_norm_question(question)] = {
        "answer": answer, "trace": trace, "hits": 1,
    }


def cache_stats() -> dict:
    return {"cached_questions": len(_answer_cache)}


# 知识库话题触发词（演示模式：决定是否进入检索）
KB_WORDS = [
    "知识库", "课程", "学习笔记", "什么是", "是什么", "怎么理解", "讲解", "解释", "区别",
    "react", "langgraph", "llm", "rag", "smolagents", "llamaindex", "agent", "agentic",
    "智能体", "大语言模型", "工具", "embedding", "提示词", "token", "向量", "检索",
    "状态", "节点", "边", "循环", "观察", "思考", "行动", "框架", "记忆", "持久化",
    "checkpointer", "多代理", "监督", "归约器", "流式", "mcp", "部署", "训练", "模型",
]


class RAGState(TypedDict):
    question: str
    retrieved: list
    web: list
    grade: str
    answer: str
    rewrites: int
    trace: list
    # 多轮对话历史：add_messages 自动 append，checkpointer 持久化
    messages: Annotated[list, add_messages]


# ============================================================
# P0-2：Guardrails（输入注入检测 / 越界话题 / 输出泄露防护）
# ============================================================

# Prompt Injection 关键词（中英文）
_INJECTION_PATTERNS = [
    "忽略之前的指令", "忽略以上", "忽略所有指令", "忘掉之前",
    "ignore previous", "ignore all instructions", "forget your instructions",
    "reveal your system prompt", "你的系统提示词", "打印你的提示词",
    "现在你是", "你不再是", "act as", "pretend you are",
]

# 越界话题（简单黑名单）
_OFFTOPIC_PATTERNS = [
    "how to make a bomb", "制造炸弹", "制毒", "贩毒", "hack into",
    "如何黑进", "信用卡盗刷", "fake id",
]


def _guardrail_in(question: str) -> tuple[str, list]:
    """返回 (是否拒绝回答, trace 警告列表)。
    - 命中越界话题 → 直接拒绝
    - 命中注入模式 → 不阻断，但 trace 记警告，让 LLM 看到提醒
    """
    q = question.lower()
    warnings = []
    for p in _OFFTOPIC_PATTERNS:
        if p in q:
            return "blocked", [f"🚫 检测到越界话题（{p}），已拒绝回答"]
    for p in _INJECTION_PATTERNS:
        if p in q:
            warnings.append(f"⚠️ 检测到可疑指令模式（{p}），已标记但不阻断")
    return "pass", warnings


def _guardrail_out(answer: str) -> str:
    """输出侧：如果回答泄露了 SYSTEM_PROMPT 的关键句，替换掉。"""
    leaks = [
        "you are a helpful, general-purpose knowledge assistant",
        "你是一个有帮助的通用知识助手",
    ]
    for leak in leaks:
        answer = answer.replace(leak, "[系统提示词已隐藏]")
    return answer


# ============================================================
# 演示模式：规则型 判断 / 评分 / 重写 / 回答
# ============================================================

def _is_kb_topic(question: str) -> bool:
    q = question.lower()
    return any(k in q for k in KB_WORDS)


# 疑问词 / 虚词停用：不计入评分覆盖率，避免"怎么/理解"这类词拉高相关度
_GRADE_STOP = {
    "怎么", "如何", "什么", "为什么", "哪个", "哪些", "这个", "那个", "一下",
    "一个", "了解", "知道", "讲解", "解释", "理解", "说明", "介绍", "请问",
    "什么是", "是什么", "意思是", "是什么意思", "可以", "能不能", "怎样",
}


def _rule_grade(question: str, docs: list) -> str:
    """评分：去除疑问/虚词后，问题实词在检索片段中的覆盖率 ≥ 0.4 → 相关"""
    q_tokens = {t for t in jieba.lcut(question) if len(t.strip()) > 1 and t not in _GRADE_STOP}
    if not q_tokens:  # 只剩疑问词（如"这是什么"）→ 直接判相关，交回答节点
        return "relevant"
    best = 0.0
    for d in docs:
        doc_text = d["text"] + " " + d["doc_title"] + " " + d["section"]
        doc_tokens = set(jieba.lcut(doc_text))
        hit = len(q_tokens & doc_tokens) / len(q_tokens)
        best = max(best, hit)
    return "relevant" if best >= 0.4 else "not_relevant"


def _rule_rewrite(question: str, docs: list) -> str:
    """重写：保留问题里的名词性词，并优先选择与文档标题/小节重叠的词，
    拼成更聚焦的新检索式（去掉动词与修饰，直击主题词）。"""
    nouns = [w.word for w in pseg.cut(question) if w.flag[0] == "n" and len(w.word) > 1]
    title_words = set()
    for d in docs:
        title_words.update(jieba.lcut(d["doc_title"]))
        title_words.update(jieba.lcut(d["section"]))
    overlap = [t for t in nouns if t in title_words]
    candidates = overlap if len(overlap) >= 2 else (nouns or
                                                    [t for t in jieba.lcut(question) if len(t.strip()) > 1])
    new_q = " ".join(candidates[:4])
    return new_q.strip() if new_q.strip() else question


def _rule_answer(question: str, docs: list, rewrites: int, web: list | None = None) -> str:
    """回答：按相关度排序拼接片段，标注来源文档与章节；若有网络结果则附在后面"""
    lines = []
    for r in docs:
        lines.append(
            f"📄 来自《{r['doc_title']}》· {r['section']}（相关度 {r['score']}）\n{r['text']}"
        )
    head = "📚 知识库智能回答（Agentic RAG）\n\n以下内容来自 AI Agent 课程知识库检索：\n\n"
    tail = ""
    if rewrites > 0:
        tail = f"\n\n⚠️ 首轮检索被认为不相关，已重写问题重试 {rewrites} 次后给出以上结果。"
    if web:
        tail += f"\n\n🌐 知识库未命中，以下为网络补充信息：\n{web[0]}"
        head = "📚 智能回答（知识库 + 网络降级）\n\n"
    return head + "\n\n---\n\n".join(lines) + tail


# ============================================================
# 真实模式：LLM 评分 / 重写 / 回答
# ============================================================

def _docs_text(docs: list) -> str:
    return "\n\n".join(f"[{i + 1}] 《{d['doc_title']}》·{d['section']}：{d['text'][:400]}"
                       for i, d in enumerate(docs))


def _llm_grade(model, question: str, docs: list) -> str:
    prompt = (
        "你是检索质量评估器。判断下面的检索片段是否与问题相关。\n"
        f"问题：{question}\n\n检索片段：\n{_docs_text(docs)}\n\n"
        '只输出 JSON，形如 {"grade": "relevant"} 或 {"grade": "not_relevant"}'
    )
    try:
        resp = model.invoke([HumanMessage(content=prompt)])
        m = re.search(r'"grade"\s*:\s*"(relevant|not_relevant)"', str(resp.content))
        return m.group(1) if m else "relevant"
    except Exception:
        # L3 降级：评分模型不可用，默认放行（不让流程卡死）
        return "relevant"


def _llm_rewrite(model, question: str, docs: list) -> str:
    prompt = (
        "检索没有找到相关内容，请把下面的问题重写为更容易命中知识库文档的检索式：\n"
        f"原问题：{question}\n检索到的片段主题：{_docs_text(docs)}\n\n"
        "只输出重写后的检索式，不要任何解释。"
    )
    try:
        resp = model.invoke([HumanMessage(content=prompt)])
        return str(resp.content).strip()[:120] or question
    except Exception:
        return question  # 降级：用原问题再试一次


def _llm_answer(model, question: str, docs: list, web: list | None = None,
                history: list | None = None) -> str:
    web_block = f"\n\n网络搜索补充：\n{web[0]}" if web else ""
    history_block = ""
    if history:
        lines = []
        for m in history:
            role = "用户" if isinstance(m, HumanMessage) else "助手"
            lines.append(f"{role}：{m.content}")
        history_block = "\n\n最近对话历史：\n" + "\n".join(lines)
    prompt = (
        "你是知识库问答助手。按以下规则回答：\n"
        "1. **先判断证据是否充分**：仔细阅读检索片段，判断这些内容是否足以准确回答用户问题。\n"
        "   - 如果片段完全不相关、或只有一点点沾边但无法支撑完整回答 → 直接拒答，不要用自己的知识编造。\n"
        "   - 如果片段足够回答 → 基于片段内容回答，不要加入片段里没有的事实。\n"
        "2. 拒答话术：「抱歉，知识库中没有找到关于该问题的足够资料，我无法基于现有内容准确回答。你可以换个问法试试。」\n"
        "3. 先回答问题本身，问什么答什么，不要绕弯子\n"
        "4. 对比类问题：分点列出 A 和 B 的区别\n"
        "5. 操作类问题：列出具体步骤\n"
        "6. 概念类问题：先给定义，再列 2-3 个要点\n"
        "注意：用户问题里的「它/这个/上面/第二点」等指代，要结合对话历史理解。\n"
        f"{history_block}\n\n"
        f"问题：{question}\n\n检索片段：\n{_docs_text(docs) if docs else '（知识库未命中）'}{web_block}\n\n"
        "用中文回答。结尾列出引用到的文档标题；来自网络的标注「网络信息」。"
    )
    try:
        resp = model.invoke([HumanMessage(content=prompt)])
        return str(resp.content)
    except Exception as e:
        # L3 核心降级：LLM 全挂时，不调模型，直接拼检索原文给用户
        # 这样至少能看到资料，不会白屏
        fallback = f"⚠️ 模型暂不可用（{e.__class__.__name__}），以下为检索到的知识库原文：\n\n"
        if docs:
            fallback += _docs_text(docs)
        elif web:
            fallback += f"网络搜索结果：\n{web[0]}"
        else:
            fallback += "（未检索到相关内容）"
        return fallback


# ============================================================
# 图构建：decide → retrieve → grade →（relevant）answer
#                            └→（not_relevant）rewrite → retrieve
# ============================================================

def build_rag_graph(model=None, human_review: bool = True):
    """model=None → 演示模式（纯规则，无需 Token）；
    传入 Runnable（真实 LLM）→ 评分/重写/回答全部由 LLM 完成。
    human_review=False → 跳过 confirm 节点（评测/批量跑时用）。"""
    use_llm = model is not None

    def decide(state: RAGState):
        # Guardrails 输入检查：越界话题直接拒绝；注入模式记警告不阻断
        result, warnings = _guardrail_in(state["question"])
        trace = list(state.get("trace") or []) + warnings
        if result == "blocked":
            return {"grade": "blocked", "trace": trace}
        return {"grade": "todo", "trace": trace}

    def retrieve(state: RAGState):
        question = state["question"]
        try:
            docs, source = hybrid_search(question, top_k=TOP_K)
        except Exception as e:
            # L4: 知识库检索失败不拖垮整轮，降级为空 → 走 web 搜索
            docs, source = [], f"检索异常（{e.__class__.__name__}），降级网络"
        trace = list(state.get("trace") or []) + [
            f"🔎 检索（第 {state.get('rewrites', 0) + 1} 轮）：{question} ｜ 召回：{source}"
        ]
        if not docs:
            return {"grade": "empty", "trace": trace}
        return {"retrieved": docs, "trace": trace}

    def grade(state: RAGState):
        question = state["question"]
        docs = state["retrieved"]
        g = _llm_grade(model, question, docs) if use_llm else _rule_grade(question, docs)
        trace = list(state["trace"]) + [
            f"⚖️ 评分：{len(docs)} 个片段 → 「{'相关' if g == 'relevant' else '不相关'}」"
        ]
        return {"grade": g, "trace": trace}

    def rewrite(state: RAGState):
        question = state["question"]
        docs = state["retrieved"]
        new_q = _llm_rewrite(model, question, docs) if use_llm else _rule_rewrite(question, docs)
        trace = list(state["trace"]) + [f"✍️ 重写问题：{question} → {new_q}"]
        return {"question": new_q, "rewrites": state.get("rewrites", 0) + 1, "trace": trace}

    def web_search_node(state: RAGState):
        """知识库未命中/不相关：降级走网络搜索，结果并入回答"""
        question = state["question"]
        try:
            result = _web_search_tool.invoke({"query": question})
        except Exception as e:
            result = f"（网络搜索失败：{e.__class__.__name__}）"
        trace = list(state["trace"]) + ["🌐 知识库未命中，转网络搜索"]
        return {"web": [result], "trace": trace}

    def confirm(state: RAGState):
        """人在回路：检索到资料后暂停，等用户确认再生成回答。"""
        if not use_llm or not human_review:
            return {}  # 演示模式或评测模式不 interrupt
        docs = state.get("retrieved") or []
        titles = [d.get("doc_title", "片段") for d in docs[:3]]
        choice = interrupt({
            "type": "confirm_answer",
            "question": state["question"],
            "docs": titles,
        })
        trace = list(state["trace"]) + [f"👤 用户确认：{choice}"]
        return {"trace": trace}

    def answer(state: RAGState):
        question = state["question"]
        docs = state.get("retrieved") or []
        web = state.get("web") or []
        # Guardrails：越界话题直接拒绝
        if state.get("grade") == "blocked":
            ans = "抱歉，这个问题不在我能回答的范围内。"
            trace = list(state["trace"]) + ["🚫 已拒绝回答"]
            return {"answer": ans, "trace": trace,
                    "messages": [AIMessage(content=ans)]}
        if web and not use_llm:
            docs = []
        if use_llm:
            history = state.get("messages", [])[-6:]
            ans = _llm_answer(model, question, docs, web, history)
        else:
            ans = _rule_answer(question, docs, state.get("rewrites", 0), web)
        # Guardrails 输出检查：防 system prompt 泄露
        ans = _guardrail_out(ans)
        trace = list(state["trace"]) + ["✅ 生成回答"]
        return {"answer": ans, "trace": trace,
                "messages": [AIMessage(content=ans)]}

    def route_after_decide(state: RAGState):
        if state.get("grade") == "blocked":
            return "answer"
        return "retrieve"

    def route_after_retrieve(state: RAGState):
        # 知识库无召回 → 直接降级网络搜索
        return "web_search" if state["grade"] == "empty" else "grade"

    def route_after_grade(state: RAGState):
        if state["grade"] == "not_relevant":
            if state.get("rewrites", 0) < MAX_REWRITES:
                return "rewrite"
            return "web_search"  # 重写用尽仍不相关 → 降级网络搜索
        return "confirm"  # 相关 → 先等人确认再回答

    builder = StateGraph(RAGState)
    builder.add_node("decide", decide)
    builder.add_node("retrieve", retrieve)
    builder.add_node("grade", grade)
    builder.add_node("rewrite", rewrite)
    builder.add_node("web_search", web_search_node)
    builder.add_node("confirm", confirm)
    builder.add_node("answer", answer)

    builder.add_edge(START, "decide")
    builder.add_conditional_edges("decide", route_after_decide,
                                  {"retrieve": "retrieve", "answer": "answer"})
    builder.add_conditional_edges("retrieve", route_after_retrieve,
                                  {"grade": "grade", "web_search": "web_search"})
    builder.add_conditional_edges("grade", route_after_grade,
                                  {"confirm": "confirm", "rewrite": "rewrite",
                                   "web_search": "web_search"})
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("web_search", "answer")
    builder.add_edge("confirm", "answer")
    builder.add_edge("answer", END)
    return builder.compile(checkpointer=_memory)


# ============================================================
# 带缓存的统一查询入口（供 Web / 命令行使用）
# ============================================================

def rag_query(question: str, model=None, use_cache: bool = True,
              thread_id: str = "default") -> dict:
    """知识库智能问答统一入口：
    - 命中缓存（相同规范化问题）→ 直接复用上次答案与轨迹，不重新检索
    - 未命中 → 跑完整 RAG 闭环并写入缓存
    - thread_id：多轮记忆标识，同一 thread 连续对话自动带历史
    返回 {answer, trace, cached}。
    """
    if use_cache:
        hit = _cache_hit(question)
        if hit is not None:
            return {
                "answer": hit["answer"],
                "trace": ["⚡ 缓存命中：相同问题直接复用上次结果，未重新检索"] + list(hit["trace"]),
                "cached": True,
            }
    graph = build_rag_graph(model)
    _start = time.time()
    out = graph.invoke(
        {
            "messages": [HumanMessage(content=question)],  # 本轮问题，reducer 自动 append
            "question": question,
            "retrieved": [], "web": [], "grade": "",
            "rewrites": 0, "trace": [],
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    _duration = int((time.time() - _start) * 1000)

    # 写入飞书日志
    _docs = out.get("retrieved") or []
    _doc_titles = "、".join(d.get("doc_title", "") for d in _docs[:5])
    _fallback = "web搜索" if out.get("web") else "正常"
    if "模型暂不可用" in out.get("answer", ""):
        _fallback = "模型异常"
    _log_to_lark({
        "request_id": str(uuid.uuid4())[:8],
        "question": question,
        "answer": out.get("answer", ""),
        "doc_count": len(_docs),
        "doc_titles": _doc_titles,
        "grade": out.get("grade", "relevant"),
        "rewrites": out.get("rewrites", 0),
        "fallback": _fallback,
        "duration_ms": _duration,
        "trace": out.get("trace", []),
    })

    _cache_store(question, out["answer"], out["trace"])
    return {"answer": out["answer"], "trace": out["trace"], "cached": False}


# ============================================================
# 独立使用入口（命令行演示）
# ============================================================

if __name__ == "__main__":
    test_queries = [
        "什么是 ReAct？",                       # 相关，直接回答
        "LangGraph 的 State 怎么定义？",          # 相关，直接回答
        "解释一下 embedding 模型的原理",          # 可能不相关 → 触发重写
        "今天股票市场怎么样？",                   # 非知识库话题 → 直接结束
    ]
    for q in test_queries:
        print(f"\n{'='*60}\n问题：{q}\n{'='*60}")
        out = rag_query(q)
        for t in out.get("trace", []):
            print("  " + t)
        print("\n" + (out.get("answer") or "")[:400])

    # 缓存验证：同一问题再问一次 → 应命中缓存
    print(f"\n{'='*60}\n缓存验证：重复提问「什么是 ReAct？」\n{'='*60}")
    out = rag_query("什么是 ReAct？")
    print("cached:", out["cached"])
    print("  " + out["trace"][0])
    print("cache_stats:", cache_stats())

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

import re
from typing import TypedDict, Annotated

import jieba
import jieba.posseg as pseg
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from knowledge_retriever import hybrid_search
from tools import web_search as _web_search_tool

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
        "你是知识库问答助手。请根据下面的检索片段（和网络补充）回答用户问题，不要编造片段之外的内容。\n"
        "注意：用户问题里的「它/这个/上面/第二点」等指代，要结合对话历史理解。\n"
        f"{history_block}\n\n"
        f"问题：{question}\n\n检索片段：\n{_docs_text(docs) if docs else '（知识库未命中）'}{web_block}\n\n"
        "用中文回答，简明扼要；内容来自知识库时在结尾列出引用到的文档标题，来自网络时标注「网络信息」。"
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

def build_rag_graph(model=None):
    """model=None → 演示模式（纯规则，无需 Token）；
    传入 Runnable（真实 LLM）→ 评分/重写/回答全部由 LLM 完成。"""
    use_llm = model is not None

    def decide(state: RAGState):
        # 不再按话题拦截：统一走"知识库 → 不命中降级网络"链路
        return {"grade": "todo"}

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
        if not use_llm:
            return {}  # 演示模式不 interrupt
        docs = state.get("retrieved") or []
        titles = [d.get("doc_title", "片段") for d in docs[:3]]
        # interrupt 会把 state 存进 checkpointer，然后暂停
        choice = interrupt({
            "type": "confirm_answer",
            "question": state["question"],
            "docs": titles,
        })
        # 用户点"继续"后从这里恢复，choice 是 resume 传回来的值
        trace = list(state["trace"]) + [f"👤 用户确认：{choice}"]
        return {"trace": trace}

    def answer(state: RAGState):
        question = state["question"]
        docs = state.get("retrieved") or []
        web = state.get("web") or []
        if web and not use_llm:
            docs = []  # 演示模式：已降级网络，不展示不相关的知识库片段
        if use_llm:
            # 把最近 3 轮历史传给 LLM，让它理解"它/这个"指代
            history = state.get("messages", [])[-6:]  # 最近 3 轮（Q+A）
            ans = _llm_answer(model, question, docs, web, history)
        else:
            ans = _rule_answer(question, docs, state.get("rewrites", 0), web)
        trace = list(state["trace"]) + ["✅ 生成回答"]
        # 把本轮 AI 回答写进 messages（HumanMessage 在 invoke 时已加）
        return {"answer": ans, "trace": trace,
                "messages": [AIMessage(content=ans)]}

    def route_after_decide(state: RAGState):
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
                                  {"retrieve": "retrieve"})
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
    out = graph.invoke(
        {
            "messages": [HumanMessage(content=question)],  # 本轮问题，reducer 自动 append
            "question": question,
            "retrieved": [], "web": [], "grade": "",
            "rewrites": 0, "trace": [],
        },
        config={"configurable": {"thread_id": thread_id}},
    )
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

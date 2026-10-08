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
from typing import TypedDict

import jieba
import jieba.posseg as pseg
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END

from knowledge_retriever import _get_index

MAX_REWRITES = 2
TOP_K = 3

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
    grade: str
    answer: str
    rewrites: int
    trace: list


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


def _rule_answer(question: str, docs: list, rewrites: int) -> str:
    """回答：按相关度排序拼接片段，标注来源文档与章节"""
    lines = []
    for r in docs:
        lines.append(
            f"📄 来自《{r['doc_title']}》· {r['section']}（相关度 {r['score']}）\n{r['text']}"
        )
    head = "📚 知识库智能回答（Agentic RAG）\n\n以下内容来自 AI Agent 课程知识库检索：\n\n"
    tail = ""
    if rewrites > 0:
        tail = f"\n\n⚠️ 首轮检索被认为不相关，已重写问题重试 {rewrites} 次后给出以上结果。"
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
    resp = model.invoke([HumanMessage(content=prompt)])
    m = re.search(r'"grade"\s*:\s*"(relevant|not_relevant)"', str(resp.content))
    return m.group(1) if m else "relevant"


def _llm_rewrite(model, question: str, docs: list) -> str:
    prompt = (
        "检索没有找到相关内容，请把下面的问题重写为更容易命中知识库文档的检索式：\n"
        f"原问题：{question}\n检索到的片段主题：{_docs_text(docs)}\n\n"
        "只输出重写后的检索式，不要任何解释。"
    )
    resp = model.invoke([HumanMessage(content=prompt)])
    return str(resp.content).strip()[:120] or question


def _llm_answer(model, question: str, docs: list) -> str:
    prompt = (
        "你是知识库问答助手。请仅根据下面的检索片段回答用户问题，不要编造片段之外的内容。\n"
        f"问题：{question}\n\n检索片段：\n{_docs_text(docs)}\n\n"
        "用中文回答，简明扼要，并在结尾列出引用到的文档标题。"
    )
    resp = model.invoke([HumanMessage(content=prompt)])
    return str(resp.content)


# ============================================================
# 图构建：decide → retrieve → grade →（relevant）answer
#                            └→（not_relevant）rewrite → retrieve
# ============================================================

def build_rag_graph(model=None):
    """model=None → 演示模式（纯规则，无需 Token）；
    传入 Runnable（真实 LLM）→ 评分/重写/回答全部由 LLM 完成。"""
    use_llm = model is not None

    def decide(state: RAGState):
        question = state["question"]
        if not use_llm and not _is_kb_topic(question):
            return {"answer": ("🤖 这个问题似乎与 AI Agent 课程知识库的主题无关，"
                               "建议切换「标准智能体」模式询问，或换个知识库相关的问题。"),
                    "grade": "done"}
        return {"grade": "todo"}

    def retrieve(state: RAGState):
        question = state["question"]
        docs = _get_index().search(question, top_k=TOP_K)
        trace = list(state.get("trace") or []) + [f"🔎 检索（第 {state.get('rewrites', 0) + 1} 轮）：{question}"]
        if not docs:
            return {"answer": "📭 知识库中没有检索到相关内容，请换个问法试试。", "grade": "empty",
                    "trace": trace}
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

    def answer(state: RAGState):
        question = state["question"]
        docs = state["retrieved"]
        if use_llm:
            ans = _llm_answer(model, question, docs)
        else:
            ans = _rule_answer(question, docs, state.get("rewrites", 0))
        trace = list(state["trace"]) + ["✅ 生成回答"]
        return {"answer": ans, "trace": trace}

    def route_after_decide(state: RAGState):
        return "end" if state["grade"] == "done" else "retrieve"

    def route_after_retrieve(state: RAGState):
        return "end" if state["grade"] == "empty" else "grade"

    def route_after_grade(state: RAGState):
        if state["grade"] == "not_relevant" and state.get("rewrites", 0) < MAX_REWRITES:
            return "rewrite"
        return "answer"

    builder = StateGraph(RAGState)
    builder.add_node("decide", decide)
    builder.add_node("retrieve", retrieve)
    builder.add_node("grade", grade)
    builder.add_node("rewrite", rewrite)
    builder.add_node("answer", answer)

    builder.add_edge(START, "decide")
    builder.add_conditional_edges("decide", route_after_decide,
                                  {"retrieve": "retrieve", "end": END})
    builder.add_conditional_edges("retrieve", route_after_retrieve,
                                  {"grade": "grade", "end": END})
    builder.add_conditional_edges("grade", route_after_grade,
                                  {"answer": "answer", "rewrite": "rewrite"})
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("answer", END)
    return builder.compile()


# ============================================================
# 独立使用入口（命令行演示）
# ============================================================

if __name__ == "__main__":
    rag = build_rag_graph()
    test_queries = [
        "什么是 ReAct？",                       # 相关，直接回答
        "LangGraph 的 State 怎么定义？",          # 相关，直接回答
        "解释一下 embedding 模型的原理",          # 可能不相关 → 触发重写
        "今天股票市场怎么样？",                   # 非知识库话题 → 直接结束
    ]
    for q in test_queries:
        print(f"\n{'='*60}\n问题：{q}\n{'='*60}")
        out = rag.invoke({"question": q, "retrieved": [], "grade": "", "answer": "",
                          "rewrites": 0, "trace": []})
        for t in out.get("trace", []):
            print("  " + t)
        print("\n" + (out.get("answer") or "")[:400])

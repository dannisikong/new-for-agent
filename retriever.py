"""
retriever.py —— 宾客数据加载与检索（LangGraph 版舞会智能体）
=============================================================
对应课程第 19 章：把宾客数据集组织成可检索的文档。
这里使用"关键词打分检索"模拟 BM25（零依赖、可离线运行）；
实际生产环境可替换为 langchain_community 的 BM25Retriever：
    from langchain_community.retrievers import BM25Retriever
    retriever = BM25Retriever.from_documents(docs)
"""

from typing import List, Dict

# 宾客数据集（课程真实场景：舞会嘉宾档案）
# 实际场景可来自 HF 数据集 agents-course/unit3-invitees
GUEST_DATASET: List[Dict[str, str]] = [
    {
        "name": "Lady Ada Lovelace",
        "relation": "esteemed mathematician and friend",
        "description": (
            "Renowned for pioneering work in mathematics and computing; often celebrated "
            "as the first computer programmer due to her work on Charles Babbage's "
            "Analytical Engine. Passionate about the intersection of art and science."
        ),
        "email": "ada.lovelace@example.com",
    },
    {
        "name": "Dr. Nikola Tesla",
        "relation": "old friend from university days",
        "description": (
            "Recently patented a new wireless energy transmission system and would be "
            "delighted to discuss it. Passionate about pigeons, which makes for good "
            "small talk. A visionary in electrical engineering."
        ),
        "email": "nikola.tesla@gmail.com",
    },
    {
        "name": "Alan Turing",
        "relation": "respected colleague in computation",
        "description": (
            "Pioneer of theoretical computer science and artificial intelligence. "
            "Known for the Turing machine and the Turing test. Quiet, witty, and fond "
            "of long-distance running."
        ),
        "email": "alan.turing@example.com",
    },
    {
        "name": "Grace Hopper",
        "relation": "naval officer and computing legend",
        "description": (
            "Developed the first compiler and popularized the idea of machine-"
            "independent programming languages. Famous for the phrase 'It's easier "
            "to ask forgiveness than it is to get permission.'"
        ),
        "email": "grace.hopper@example.com",
    },
]


def _tokenize(text: str) -> List[str]:
    """简易分词：小写 + 按非字母数字切分"""
    import re
    return re.findall(r"[a-z0-9]+", text.lower())


def _score(query_tokens: List[str], candidate: Dict[str, str]) -> int:
    """关键词命中打分（模拟 BM25 的检索排序）"""
    haystack = _tokenize(" ".join([
        candidate["name"],
        candidate["relation"],
        candidate["description"],
    ]))
    return sum(1 for tok in query_tokens if tok in haystack)


def load_guest_dataset() -> List[Dict[str, str]]:
    """返回宾客数据集（对应课程 load_guest_dataset）"""
    return GUEST_DATASET


def retrieve_guest_info(query: str, top_k: int = 1) -> str:
    """
    检索函数：根据姓名/关系/关键词返回最相关的宾客信息。
    返回格式化文本；无匹配时返回友好提示。
    """
    query_tokens = _tokenize(query)
    ranked = sorted(GUEST_DATASET, key=lambda g: _score(query_tokens, g), reverse=True)

    best = ranked[0]
    if _score(query_tokens, best) == 0:
        return "No matching guest information found."

    results = ranked[:top_k]
    return "\n\n".join(
        f"Name: {g['name']}\n"
        f"Relation: {g['relation']}\n"
        f"Description: {g['description']}\n"
        f"Email: {g['email']}"
        for g in results
    )

"""
rerank.py —— 精排层（LLM-as-Reranker）
========================================
粗筛（BM25+向量 RRF）取 top20 后，用 LLM 对候选片段统一打分重排，取 top5。

为什么用 LLM 做 rerank 而不是 cross-encoder？
  - 个人 demo 项目，不想引入本地模型依赖
  - LLM 一次请求就能对所有候选打分，只调一次，延迟可控
  - 面试时能讲："我们用 LLM 做 cross-encoder 式的精排，对召回候选统一相关性打分"

流程：
  粗筛 top20 → LLM 批量打分（1-5分）→ 按分数重排 → 取 top5
"""

import json
import re

from langchain_openai import ChatOpenAI


RERANK_PROMPT = """你是一个检索结果排序专家。下面是用户问题和若干候选文档片段，请判断每个片段与问题的相关程度，打 1-5 分。

打分标准：
- 5 分：片段直接回答了问题，核心信息完整
- 4 分：片段与问题高度相关，包含主要答案
- 3 分：片段与问题有一定关联，但不完整或偏题
- 2 分：片段与问题关联很弱
- 1 分：片段与问题完全无关

【用户问题】{query}

【候选片段列表】
{candidates}

请输出一个 JSON 数组，每个元素包含 "id"（片段编号）和 "score"（1-5分）：
[{{"id": 1, "score": 5}}, {{"id": 2, "score": 3}}, ...]

只输出 JSON 数组，不要其他内容。"""


def rerank_candidates(
    query: str,
    candidates: list[dict],
    llm: ChatOpenAI,
    top_k: int = 5,
) -> list[dict]:
    """对粗筛候选做精排，返回 top_k 个最相关片段。

    Args:
        query: 用户问题
        candidates: 粗筛结果列表（每个含 doc_title / section / text）
        llm: 用于打分的 LLM 实例
        top_k: 最终保留的片段数

    Returns:
        重排后的 top_k 片段列表，按相关性从高到低
    """
    if len(candidates) <= top_k:
        # 候选数少于要保留的数量，不需要重排
        return candidates[:top_k]

    # 构造候选片段文本（截断每个片段避免超长）
    cand_texts = []
    for i, c in enumerate(candidates):
        text_preview = c["text"][:200]  # 每个片段取前 200 字打分足够
        cand_texts.append(f"[片段{i+1}] 《{c['doc_title']}》-{c['section']}\n{text_preview}")

    prompt = RERANK_PROMPT.format(
        query=query,
        candidates="\n\n".join(cand_texts),
    )

    try:
        resp = llm.invoke(prompt).content
        # 提取 JSON 数组
        m = re.search(r"\[.*\]", resp, re.DOTALL)
        if m:
            scores = json.loads(m.group(0))
        else:
            # 解析失败，直接返回原顺序
            return candidates[:top_k]
    except Exception as e:
        print(f"  [rerank] LLM 打分失败，降级原顺序：{e}")
        return candidates[:top_k]

    # 按分数排序
    score_map = {s["id"]: s["score"] for s in scores}
    ranked = sorted(
        range(len(candidates)),
        key=lambda i: score_map.get(i + 1, 0),
        reverse=True,
    )

    # 返回重排后的结果
    result = []
    for new_rank, idx in enumerate(ranked[:top_k]):
        c = candidates[idx].copy()
        c["original_rank"] = c.get("rank", idx)  # 保留原粗筛排名，方便对比
        c["rank"] = new_rank
        c["rerank_score"] = score_map.get(idx + 1, 0)
        result.append(c)

    return result


if __name__ == "__main__":
    # 自测：模拟候选
    demo_candidates = [
        {"doc_title": "MCP 核心概念", "section": "USB-C 类比", "text": "MCP 是模型上下文协议，像 USB-C 一样标准化接口..."},
        {"doc_title": "LangGraph 构建模块", "section": "State", "text": "LangGraph 的 State 是图运行时共享的数据结构..."},
        {"doc_title": "RAG 智能体", "section": "Agentic RAG", "text": "Agentic RAG 是带评分节点的检索增强生成..."},
    ]
    print("Rerank 模块就绪，用法见 rerank_candidates()")

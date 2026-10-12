"""
eval.py —— 评测脚本（LLM-as-Judge）
=====================================
跑 eval_dataset.py 里的 30 条问题，对我们的 RAG 系统打分。

用法：
    python eval.py --base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
                   --api-key sk-xxx --model qwen3.7-plus

输出：
    - 每条问题的得分
    - 汇总：召回准确率、平均回答分、幻觉率
    - 失败案例列表（方便针对性优化）
"""

import argparse
import re
import sys
from pathlib import Path

# 让 import 能找到项目根目录
sys.path.insert(0, str(Path(__file__).parent))

from eval_dataset import EVAL_DATASET
from agentic_rag import build_rag_graph
from langchain_openai import ChatOpenAI


# ---------- 裁判 prompt ----------
JUDGE_PROMPT = """你是一个严格的评分员。请根据以下信息，对 AI 的回答打分。

【问题】{question}
【标准答案要点】{keywords}
【AI 的回答】{answer}

请输出一个 JSON（不要其他内容）：
{{
  "score": 1-5 的整数（5=完全覆盖标准答案要点，1=完全没答到）,
  "covered": ["回答里实际覆盖到的标准答案要点"],
  "missed": ["没覆盖到的要点"],
  "hallucination": true/false（true=回答里编造了不存在的事实/文档/数据）
}}
只输出 JSON。"""


def make_judge_llm(base_url: str, api_key: str, model: str) -> ChatOpenAI:
    return ChatOpenAI(base_url=base_url, api_key=api_key, model=model, temperature=0)


def run_one(rag_graph, llm, item: dict) -> dict:
    """跑一条问题，返回评分结果。"""
    question = item["question"]
    # 用一个独立 thread_id 跑评测
    result = rag_graph.invoke(
        {"question": question, "messages": []},
        config={"configurable": {"thread_id": f"eval-{item['id']}"}},
    )
    answer = result.get("answer", "")
    retrieved = result.get("retrieved", [])
    retrieved_titles = [d.get("doc_title", "") for d in retrieved]

    # 1. 召回准确率：应命中的文档是否在 retrieved 里
    # expected_doc 格式："01-01___Agent_智能体.md"，提取章节号 "01"
    expected_doc = item["expected_doc"]
    m = re.match(r"(\d+)-", expected_doc)
    expected_num = m.group(1) if m else ""
    # retrieved title 格式："<title>01 · Agent（智能体）</title>"
    hit_recall = any(
        expected_num in re.findall(r"(\d+)\s*[·.•]", t) or expected_num in t.split()[0]
        for t in retrieved_titles
    )

    # 2. LLM-as-Judge 打分
    judge_input = JUDGE_PROMPT.format(
        question=question,
        keywords="、".join(item["expected_keywords"]),
        answer=answer[:1500],  # 截断避免超长
    )
    try:
        judge_resp = llm.invoke(judge_input).content
        # 提取 JSON
        m = re.search(r"\{[^}]+\}", judge_resp, re.DOTALL)
        if m:
            import json
            judge = json.loads(m.group(0))
        else:
            judge = {"score": 3, "covered": [], "missed": [], "hallucination": False}
    except Exception as e:
        judge = {"score": 0, "covered": [], "missed": [f"裁判失败: {e}"], "hallucination": False}

    return {
        "id": item["id"],
        "question": question,
        "type": item["type"],
        "expected_doc": expected_doc,
        "recall_hit": hit_recall,
        "retrieved_titles": retrieved_titles[:3],
        "answer_score": judge.get("score", 0),
        "covered": judge.get("covered", []),
        "missed": judge.get("missed", []),
        "hallucination": judge.get("hallucination", False),
        "answer_preview": answer[:200],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--model", default="qwen3.7-plus")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条（0=全跑）")
    args = parser.parse_args()

    print(f"🚀 开始评测：{len(EVAL_DATASET)} 条问题，模型={args.model}")
    print("=" * 70)

    llm = make_judge_llm(args.base_url, args.api_key, args.model)
    rag_graph = build_rag_graph(llm, human_review=False)  # 评测跳过 confirm

    items = EVAL_DATASET[:args.limit] if args.limit > 0 else EVAL_DATASET
    results = []
    for item in items:
        print(f"[{item['id']:>2}/{len(items)}] {item['question'][:40]}...")
        r = run_one(rag_graph, llm, item)
        results.append(r)
        flag = "✅" if r["recall_hit"] and r["answer_score"] >= 4 and not r["hallucination"] else "⚠️"
        print(f"     {flag} 召回={'✓' if r['recall_hit'] else '✗'} 回答分={r['answer_score']} 幻觉={'⚠️' if r['hallucination'] else '无'}")

    # ---------- 汇总 ----------
    print("\n" + "=" * 70)
    print("📊 评测报告")
    print("=" * 70)

    n = len(results)
    recall_rate = sum(1 for r in results if r["recall_hit"]) / n
    avg_score = sum(r["answer_score"] for r in results) / n
    halluc_rate = sum(1 for r in results if r["hallucination"]) / n

    print(f"总问题数：{n}")
    print(f"召回准确率：{recall_rate:.0%}（{sum(1 for r in results if r['recall_hit'])}/{n}）")
    print(f"平均回答分：{avg_score:.2f}/5")
    print(f"幻觉率：{halluc_rate:.0%}（{sum(1 for r in results if r['hallucination'])}/{n}）")

    # 按类型细分
    print("\n按类型：")
    from collections import defaultdict
    by_type = defaultdict(list)
    for r in results:
        by_type[r["type"]].append(r)
    for t, rs in by_type.items():
        ar = sum(1 for r in rs if r["recall_hit"]) / len(rs)
        asc = sum(r["answer_score"] for r in rs) / len(rs)
        print(f"  {t:10s}: 召回={ar:.0%}  平均分={asc:.1f}  ({len(rs)}条)")

    # 失败案例
    failures = [r for r in results if not r["recall_hit"] or r["answer_score"] < 4 or r["hallucination"]]
    if failures:
        print(f"\n⚠️ 失败/待优化案例（{len(failures)} 条）：")
        for r in failures:
            reasons = []
            if not r["recall_hit"]:
                reasons.append(f"未命中应检文档({r['expected_doc'][:20]})")
            if r["answer_score"] < 4:
                reasons.append(f"回答分低({r['answer_score']})")
            if r["hallucination"]:
                reasons.append("有幻觉")
            print(f"  #{r['id']} {r['question'][:35]}... → {'；'.join(reasons)}")


if __name__ == "__main__":
    main()

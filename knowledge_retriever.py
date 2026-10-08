"""
knowledge_retriever.py —— 飞书知识库关键词检索（BM25 中文版）
================================================================
数据源：docs/*.md（由飞书 AI Agent 学习知识库 22 篇文档导出）
流程：文档 → 段落分块 → jieba 中文分词 → BM25 索引 → 按查询返回最相关段落。

给 LangGraph Agent 提供 knowledge_search 工具（见 tools.py）。
"""

import glob
import math
import os
import re

import jieba

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
TOP_K = 3

# jieba 初次加载会输出日志，静默处理
jieba.setLogLevel(20)


# ============================================================
# 1. 加载文档并分块
# ============================================================

def _strip_markdown(text: str) -> str:
    """去掉 Markdown / HTML 语法，保留纯文本（便于分词与展示）"""
    text = re.sub(r"<[^>]+>", " ", text)  # HTML 标签（如飞书 <title>）
    text = re.sub(r"```.*?```", " ", text, flags=re.S)  # 代码块
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # 链接只留文字
    text = re.sub(r"[#>*`|~\-]", " ", text)  # 标题/列表/粗斜体符号
    return text


def _clean_chunk(text: str, doc_title: str) -> str:
    """清理块内噪声：重复的文档标题行、纯符号图标行"""
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s == doc_title:  # 块内重复的标题行
            continue
        if re.fullmatch(r"[!！·•\-—\s]+", s):  # 纯图标/分隔符行
            continue
        lines.append(s)
    return "\n".join(lines)


def _load_chunks() -> list[dict]:
    """返回 [{doc_title, section, text}]，按文档标题与段落切块"""
    chunks = []
    for path in sorted(glob.glob(os.path.join(DOCS_DIR, "*.md"))):
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        # 文档标题取首行 "# xxx"（去掉序号等内部文件命名干扰）
        first_line = raw.splitlines()[0] if raw.splitlines() else ""
        doc_title = re.sub(r"^#\s*", "", first_line).strip() or os.path.basename(path)[:-3]
        # 正文从第二行起
        lines = raw.splitlines()
        body_lines = [ln for ln in lines[1:] if ln.strip()]
        section = "全文"
        buf = []
        for ln in body_lines:
            if re.match(r"^#{2,3}\s", ln):  # 二级/三级标题 → 新块
                if buf:
                    chunks.append({"doc_title": doc_title, "section": section,
                                   "text": _clean_chunk(_strip_markdown("\n".join(buf)), doc_title)})
                section = re.sub(r"^#+\s*", "", ln).strip()
                buf = []
            else:
                buf.append(ln)
        if buf:
            chunks.append({"doc_title": doc_title, "section": section,
                           "text": _clean_chunk(_strip_markdown("\n".join(buf)), doc_title)})
    # 过滤过短块与"标签"噪声块（纯关键词短行）
    return [c for c in chunks
            if len(c["text"]) >= 20 and not (c["section"] == "标签" and len(c["text"]) < 60)]


# ============================================================
# 2. BM25 索引与检索（经典实现，k1=1.5, b=0.75）
# ============================================================

class BM25Index:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.tokenized = [jieba.lcut(c["text"]) for c in chunks]
        self.doc_count = len(chunks)
        # 文档频率：df[term] = 包含该词的文档数
        self.df: dict[str, int] = {}
        self.doc_len = [len(t) for t in self.tokenized]
        self.avg_len = sum(self.doc_len) / max(1, self.doc_count)
        for toks in self.tokenized:
            for t in set(toks):
                self.df[t] = self.df.get(t, 0) + 1
        self.k1, self.b = 1.5, 0.75

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log((self.doc_count - n + 0.5) / (n + 0.5) + 1.0)

    def search(self, query: str, top_k: int = TOP_K) -> list[dict]:
        q_tokens = [t for t in jieba.lcut(query) if len(t.strip()) > 1]
        if not q_tokens:
            return []
        scores = []
        for i, toks in enumerate(self.tokenized):
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            score = 0.0
            for t in q_tokens:
                if t in tf:
                    idf = self._idf(t)
                    tf_norm = (tf[t] * (self.k1 + 1)) / (
                        tf[t] + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avg_len)
                    )
                    score += idf * tf_norm
            if score > 0:
                scores.append((score, i))
        scores.sort(reverse=True, key=lambda x: x[0])
        results = []
        for _, i in scores[:top_k]:
            c = self.chunks[i]
            results.append({
                "score": round(scores[scores.index((_, i))][0], 2),
                "doc_title": c["doc_title"],
                "section": c["section"],
                "text": c["text"][:500],
            })
        return results


# ============================================================
# 3. 检索工具函数（供 tools.py 注册）
# ============================================================

_index: BM25Index | None = None


def _get_index() -> BM25Index:
    global _index
    if _index is None:
        _index = BM25Index(_load_chunks())
    return _index


def knowledge_search(query: str, top_k: int = TOP_K) -> str:
    """检索 AI Agent 课程知识库（22 篇中文学习笔记），返回最相关的文档片段。

    Args:
        query: 用户想了解的知识点或问题（中文）。
        top_k: 返回的相关片段数量。
    """
    results = _get_index().search(query, top_k)
    if not results:
        return "[知识库] 未找到相关文档片段，请尝试换一种问法。"
    parts = []
    for r in results:
        parts.append(
            f"【文档】{r['doc_title']}（章节：{r['section']}，相关度 {r['score']}）\n{r['text']}"
        )
    return "[知识库检索结果]\n" + "\n\n---\n\n".join(parts)


if __name__ == "__main__":
    # 自测
    for q in ["什么是 ReAct？", "LangGraph 的 State 是什么", "什么是 embedding 模型？", "智能体有哪几种框架？"]:
        print(f"\n== 查询：{q} ==")
        print(knowledge_search(q))

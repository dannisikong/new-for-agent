"""
knowledge_retriever.py —— 飞书知识库混合检索（BM25 + 向量 + RRF 融合）
================================================================
数据源：docs/*.md（由飞书 AI Agent 学习知识库 22 篇文档导出）
流程：文档 → 段落分块 →
  ① jieba 中文分词 → BM25 索引（关键词召回）
  ② embedding → 向量索引（语义召回）
  ③ RRF 倒数排名融合两路结果
无 embedding 配置（演示模式 / 未填 Token）时自动降级纯 BM25。

给 LangGraph Agent 提供 knowledge_search 工具（见 tools.py）。
"""

import glob
import math
import os
import re

import jieba

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
TOP_K = 3
RECALL_N = 10  # 每路召回数量（融合前）
RRF_K = 60     # RRF 常数（经验值）

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

    def search_raw(self, query: str, top_n: int = RECALL_N) -> list[tuple[float, int]]:
        """返回 [(score, chunk_idx), ...] 已按分数降序，供 RRF 融合"""
        q_tokens = [t for t in jieba.lcut(query) if len(t.strip()) > 1]
        if not q_tokens:
            return []
        scored: list[tuple[float, int]] = []
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
                scored.append((score, i))
        scored.sort(reverse=True, key=lambda x: x[0])
        return scored[:top_n]

    def search(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """单路 BM25 检索（旧接口，供未配置 embedding 时降级使用）"""
        return [self._format(rank, score, idx)
                for rank, (score, idx) in enumerate(self.search_raw(query, top_n=top_k))]

    def _format(self, rank: int, score: float, idx: int) -> dict:
        c = self.chunks[idx]
        return {
            "rank": rank,
            "score": round(score, 3),
            "doc_title": c["doc_title"],
            "section": c["section"],
            "text": c["text"][:500],
        }


# ============================================================
# 3. Embedding 客户端 + 向量索引（OpenAI 兼容 /embeddings 接口）
# ============================================================

class EmbeddingClient:
    """OpenAI 兼容 embedding 接口：POST {base_url}/embeddings"""

    def __init__(self, api_key: str, base_url: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        import requests
        resp = requests.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=30,
        )
        resp.raise_for_status()
        return [d["embedding"] for d in resp.json()["data"]]


class VectorIndex:
    """内存向量索引：L2 归一化后点积即余弦相似度（语料量小，无需外部向量库）"""

    def __init__(self, chunks: list[dict], client: EmbeddingClient):
        self.chunks = chunks
        self.client = client
        texts = [c["text"][:800] for c in chunks]
        vecs: list[list[float]] = []
        for i in range(0, len(texts), 64):  # 分批请求，避免单次过长
            vecs.extend(client.embed(texts[i:i + 64]))
        import numpy as np
        self.mat = np.array(vecs, dtype="float32")
        self.mat /= (np.linalg.norm(self.mat, axis=1, keepdims=True) + 1e-8)

    def search_raw(self, query: str, top_n: int = RECALL_N) -> list[tuple[float, int]]:
        import numpy as np
        qv = np.array(self.client.embed([query])[0], dtype="float32")
        qv /= (np.linalg.norm(qv) + 1e-8)
        sims = self.mat @ qv
        order = sims.argsort()[::-1][:top_n]
        return [(float(sims[i]), int(i)) for i in order]


# ============================================================
# 4. RRF 倒数排名融合 + 统一混合检索入口
# ============================================================

def _rrf_fuse(*ranked_lists: list[tuple[float, int]], top_k: int = TOP_K) -> list[tuple[float, int]]:
    """多路 [(score, idx)] → RRF 融合：每路贡献 1/(k+rank+1)，求和后取 top_k"""
    fused: dict[int, float] = {}
    for rl in ranked_lists:
        for rank, (_, idx) in enumerate(rl):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)
    return sorted(fused.items(), key=lambda x: -x[1])[:top_k]


_index: BM25Index | None = None
_embedding_client: EmbeddingClient | None = None
_vector_index: VectorIndex | None = None


def _get_index() -> BM25Index:
    global _index
    if _index is None:
        _index = BM25Index(_load_chunks())
    return _index


def set_embedding_client(client: EmbeddingClient | None):
    """Web 层每次请求注入用户的 embedding 配置；传 None 表示纯 BM25"""
    global _embedding_client, _vector_index
    _embedding_client = client
    _vector_index = None  # 配置变了，下次检索时重建向量索引


def _get_vector_index() -> VectorIndex | None:
    global _vector_index, _embedding_client
    if _embedding_client is None:
        return None
    if _vector_index is None:
        try:
            _vector_index = VectorIndex(_get_index().chunks, _embedding_client)
        except Exception as e:  # embedding 不可用 → 永久降级纯 BM25（本次会话）
            print(f"  [vector] 向量索引不可用，降级纯 BM25：{e.__class__.__name__}: {e}")
            _embedding_client = None
            return None
    return _vector_index


def hybrid_search(query: str, top_k: int = TOP_K) -> tuple[list[dict], str]:
    """统一检索入口：BM25 + 向量两路召回，RRF 融合。
    返回 (结果列表, 召回方式说明)。无 embedding 配置时自动降级纯 BM25。"""
    bm25 = _get_index().search_raw(query, top_n=RECALL_N)
    vi = _get_vector_index()
    if vi is None:
        picks = [(s, i) for s, i in bm25[:top_k]]
        source = "BM25 关键词"
    else:
        try:
            vec = vi.search_raw(query, top_n=RECALL_N)
            picks = _rrf_fuse(bm25, vec, top_k=top_k)
            source = "BM25 + 向量语义（RRF 融合）"
        except Exception as e:
            print(f"  [vector] 向量检索失败，降级 BM25：{e}")
            picks = [(s, i) for s, i in bm25[:top_k]]
            source = "BM25 关键词（向量不可用降级）"
    results = []
    for rank, (score, i) in enumerate(picks):
        c = _get_index().chunks[i]
        results.append({
            "rank": rank,
            "score": round(score, 3),
            "doc_title": c["doc_title"],
            "section": c["section"],
            "text": c["text"][:500],
        })
    return results, source


def knowledge_search(query: str, top_k: int = TOP_K) -> str:
    """检索 AI Agent 课程知识库（22 篇中文学习笔记），返回最相关的文档片段。

    Args:
        query: 用户想了解的知识点或问题（中文）。
        top_k: 返回的相关片段数量。
    """
    results, source = hybrid_search(query, top_k)
    if not results:
        return "[知识库] 未找到相关文档片段，请尝试换一种问法。"
    parts = []
    for r in results:
        parts.append(
            f"【文档】{r['doc_title']}（章节：{r['section']}，相关度 {r['score']}）\n{r['text']}"
        )
    return f"[知识库检索结果 · 召回方式：{source}]\n" + "\n\n---\n\n".join(parts)


if __name__ == "__main__":
    # 自测
    for q in ["什么是 ReAct？", "LangGraph 的 State 是什么", "什么是 embedding 模型？", "智能体有哪几种框架？"]:
        print(f"\n== 查询：{q} ==")
        print(knowledge_search(q))

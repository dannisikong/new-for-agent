"""
tools.py —— Alfred 舞会智能体的五个工具（LangGraph 版）
========================================================
网络搜索、天气、HF Hub 统计 + 宾客检索 + 知识库检索。
全部使用 langchain_core.tools 的 @tool 装饰器定义。

P0-1：工具调用重试幂等（只读工具，天然幂等；失败按错误类型分类重试）。
"""

import random
import time
from functools import wraps
from typing import Annotated, Optional

from pydantic import Field
from langchain_core.tools import tool

from retriever import retrieve_guest_info
from knowledge_retriever import knowledge_search as _kb_search


# ============================================================
# P0-1：通用重试装饰器（按错误类型区分策略）
# ============================================================

def _classify_error(exc: Exception) -> tuple[bool, float]:
    """判断异常是否值得重试，返回 (是否重试, 本次等待秒数)。
    - 401/403 认证失败 → 不重试
    - 404 资源不存在 → 不重试
    - 429 限流 → 退避更久（5s）
    - 5xx 服务端错误 → 正常退避（1s）
    - 网络超时/连接错误 → 正常退避（1s）
    - 其他异常 → 保守重试（0.5s）
    """
    resp = getattr(exc, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", 0)
        if code in (401, 403):
            return False, 0.0
        if code == 404:
            return False, 0.0
        if code == 429:
            return True, 5.0
        if 500 <= code < 600:
            return True, 1.0
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True, 1.0
    return True, 0.5


def with_retry(max_attempts: int = 3):
    """工具级重试包装：指数退避，按错误类型决定是否重试。"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    retry, wait = _classify_error(e)
                    if not retry or attempt == max_attempts:
                        break
                    time.sleep(wait * attempt)  # 指数退避：1s, 2s, 4s
            raise last_exc
        return wrapper
    return decorator

# ============================================================
# 工具 1：宾客信息检索（对应课程 guest_info_retriever）
# ============================================================

@tool
def guest_info_retriever(query: Annotated[str, Field(description="宾客姓名或关系关键词，纯文本，不含路径或命令")]) -> str:
    """检索舞会宾客档案，返回对应宾客的身份、与主人的关系、简介和邮箱。

    何时调用：用户询问某位宾客是谁、与主人什么关系、有什么背景或邮箱时使用；
    仅覆盖内置的 4 位历史宾客档案，超出范围不要强行匹配。

    Args:
        query: 宾客姓名或与宾客相关的关系关键词，纯文本；不要带文件路径、URL 或 shell 命令。

    Returns:
        格式化多行文本，依次为 Name / Relation / Description / Email 四行；
        无匹配时返回 "No matching guest information found."。
    """
    return retrieve_guest_info(query)


# ============================================================
# 工具 2：网络搜索（对应课程 DuckDuckGoSearchTool）
# ============================================================

def _duckduckgo_search_real(query: str) -> str:
    """真实 DuckDuckGo 搜索；失败抛异常（由外层 with_retry 重试）"""
    from ddgs import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=3))
    if not results:
        raise RuntimeError("DDG returned no results")
    return "\n".join(
        f"- {r['title']}: {r['body'][:200]}" for r in results
    )


@tool
@with_retry(3)
def web_search(query: Annotated[str, Field(description="联网搜索关键词短语，不含本地路径或 shell 命令")]) -> str:
    """联网检索最新资讯与外部事实，返回最多 3 条标题加摘要的编号列表。

    何时调用：问题需要外部实时信息（新闻、最新进展、外部事实）而本地知识库查不到时使用；
    概念定义、课程知识点优先调用 knowledge_search，不要在两个工具间重复发起。

    Args:
        query: 搜索关键词短语（一句话或核心词组均可），不要传本地文件路径或 shell 命令，长度不超过 300 字。

    Returns:
        以 "- 标题: 摘要" 逐行列出的搜索结果文本；联网彻底失败时返回标注为"[模拟搜索结果]"的降级文案，
        此时必须提示用户以官方信源为准，不得把模拟结果当作事实。
    """
    try:
        return _duckduckgo_search_real(query)
    except Exception:
        # 重试都失败，降级模拟结果
        return (
            f"[模拟搜索结果] 关于“{query}”的最新进展：多家机构发布了相关研究，"
            "业界普遍认为该领域正处于快速迭代期，更多细节请以官方信源为准。"
        )


# ============================================================
# 工具 3：天气查询（对应课程 WeatherInfoTool，dummy API）
# ============================================================

@tool
def weather_info(location: Annotated[str, Field(description="城市或地点名称，中英文文字，不含命令符或路径")]) -> str:
    """查询指定城市或地点的示例天气（演示用占位数据，不是实时气象预报）。

    何时调用：用户询问某个地点的天气状况时使用；返回的是随机占位演示数据，不能当作真实天气预报引用。

    Args:
        location: 城市或地点名称（中英文均可），仅文字、数字与常见空格连字符，不要带命令符或路径，长度不超过 100 字。

    Returns:
        一行形如 "Weather in {location}: {condition}, {temp_c}°C" 的文本，
        天气条件在 Rainy / Clear / Windy 三者中随机选取。
    """
    weather_conditions = [
        {"condition": "Rainy", "temp_c": 15},
        {"condition": "Clear", "temp_c": 25},
        {"condition": "Windy", "temp_c": 20},
    ]
    data = random.choice(weather_conditions)
    return f"Weather in {location}: {data['condition']}, {data['temp_c']}°C"


# ============================================================
# 工具 4：HF Hub 模型统计（对应课程 HubStatsTool）
# ============================================================

def _hub_stats_real(author: str) -> str:
    """真实查询 HF Hub；失败抛异常（由外层 with_retry 重试）"""
    from huggingface_hub import list_models
    models = list(list_models(author=author, sort="downloads", direction=-1, limit=1))
    if not models:
        raise RuntimeError(f"No models found for author {author}")
    m = models[0]
    return f"The most downloaded model by {author} is {m.id} with {m.downloads:,} downloads."


@tool
@with_retry(3)
def hub_stats(author: Annotated[str, Field(description="HF Hub 用户名或组织名，字母/数字/下划线/连字符，非完整模型 ID")]) -> str:
    """查询 Hugging Face Hub 上指定作者或组织下载量最高的模型及其下载量。

    何时调用：用户询问某 HF 用户或机构（如 google、facebook、qwen）最热门的模型时使用；
    作者名必须是 HF Hub 上的用户名或组织名，不要填完整模型 ID 或自然语言句子。

    Args:
        author: HF Hub 用户名或组织名，仅允许字母、数字、下划线、连字符，长度不超过 64 字符。

    Returns:
        一句说明"下载量最高的模型是 {model_id}，下载量 {count}"；真实查询失败时用内置示例数据兜底，
        无匹配作者时返回 "No models found for author {author}."。
    """
    try:
        return _hub_stats_real(author)
    except Exception:
        fake = {
            "qwen": "Qwen/Qwen2.5-VL-7B-Instruct with 3,313,345 downloads",
            "google": "google/electra-base-discriminator with 28,546,752 downloads",
            "facebook": "facebook/esmfold_v1 with 12,544,550 downloads",
        }
        key = author.lower()
        for k, v in fake.items():
            if k in key:
                return f"The most downloaded model by {author} is {v}."
        return f"No models found for author {author}."


# ============================================================
# 工具 5：AI Agent 课程知识库检索（BM25 关键词版）
# ============================================================

@tool
def knowledge_search(query: Annotated[str, Field(description="知识点或问题，中文提问效果最佳，不含命令或路径")]) -> str:
    """检索内置 AI Agent 课程知识库（MCP、LangGraph、RAG、LLM、框架等中文学习笔记），返回最相关的文档片段。

    何时调用：用户询问 Agent 概念、LangGraph、LLM、RAG、工具调用、框架
    （smolagents / LlamaIndex / LangGraph）等课程范围内知识点时优先使用；
    外部实时新闻、最新进展不要用本工具，改用 web_search。

    Args:
        query: 想了解的知识点或问题，中文提问检索效果最好；纯文本，不要带命令或路径，长度不超过 300 字。

    Returns:
        多条"【文档】标题（章节 + 相关度分数）+ 正文片段"列表，开头标注召回方式
        （BM25 关键词 / BM25 + 向量语义 RRF 融合 / 附带 LLM Rerank 精排）；未命中时返回换一种问法的提示。
    """
    return _kb_search(query)


# 统一工具列表（对应课程 tools=[...]）
TOOLS = [guest_info_retriever, web_search, weather_info, hub_stats, knowledge_search]

# 工具名白名单：模型幻觉调用不存在的工具时，用于前置校验
TOOL_NAMES = {t.name for t in TOOLS}
TOOL_DESCRIPTIONS = {t.name: t.description for t in TOOLS}

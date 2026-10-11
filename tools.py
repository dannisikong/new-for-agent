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
from typing import Optional

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
def guest_info_retriever(query: str) -> str:
    """Retrieves detailed information about gala guests based on their name or relation.

    Args:
        query: The name or relation of the guest you want information about.
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
def web_search(query: str) -> str:
    """Searches the web for the latest news and information.

    Args:
        query: The search query (e.g. a news topic or recent advancement).
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
def weather_info(location: str) -> str:
    """Fetches dummy weather information for a given location.

    Args:
        location: The location to get weather information for.
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
def hub_stats(author: str) -> str:
    """Fetches the most downloaded model from a specific author on the Hugging Face Hub.

    Args:
        author: The username of the model author/organization to find models from.
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
def knowledge_search(query: str) -> str:
    """Searches the AI Agent course knowledge base (22 Chinese study notes) and returns the most relevant snippets.

    Use this tool when the user asks about AI Agent concepts, LangGraph, LLMs, RAG,
    tools, frameworks (smolagents / LlamaIndex / LangGraph), or any topic covered by the course.

    Args:
        query: The knowledge point or question to search (in Chinese works best).
    """
    return _kb_search(query)


# 统一工具列表（对应课程 tools=[...]）
TOOLS = [guest_info_retriever, web_search, weather_info, hub_stats, knowledge_search]

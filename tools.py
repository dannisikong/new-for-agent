"""
tools.py —— Alfred 舞会智能体的四个工具（LangGraph 版）
========================================================
对应课程第 20 章：网络搜索、天气、HF Hub 统计 + 宾客检索。
全部使用 langchain_core.tools 的 @tool 装饰器定义，
可直接交给 LangGraph 的 ToolNode 执行。

网络搜索与 HF Hub 均优先走真实 API，失败时自动降级为模拟结果
（保证无 Key / 离线环境也能完整演示 ReAct 循环）。
"""

import random
from typing import Optional

from langchain_core.tools import tool

from retriever import retrieve_guest_info

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

def _duckduckgo_search(query: str) -> Optional[str]:
    """真实 DuckDuckGo 搜索；失败返回 None"""
    try:
        from ddgs import DDGS  # 包已由 duckduckgo-search 重命名为 ddgs
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if results:
            return "\n".join(
                f"- {r['title']}: {r['body'][:200]}" for r in results
            )
    except Exception as e:  # 网络受限 / 反爬时降级
        print(f"  [tools] DDG 搜索不可用（{e.__class__.__name__}），使用模拟结果")
    return None

@tool
def web_search(query: str) -> str:
    """Searches the web for the latest news and information.

    Args:
        query: The search query (e.g. a news topic or recent advancement).
    """
    real = _duckduckgo_search(query)
    if real:
        return real
    # 模拟结果（保证演示闭环；真实部署时删除此分支）
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

def _hub_stats_real(author: str) -> Optional[str]:
    """真实查询 HF Hub 上该作者下载量最高的模型；失败返回 None"""
    try:
        from huggingface_hub import list_models
        models = list(list_models(author=author, sort="downloads", direction=-1, limit=1))
        if models:
            m = models[0]
            return f"The most downloaded model by {author} is {m.id} with {m.downloads:,} downloads."
    except Exception as e:
        print(f"  [tools] HF Hub 查询不可用（{e.__class__.__name__}），使用模拟结果")
    return None

@tool
def hub_stats(author: str) -> str:
    """Fetches the most downloaded model from a specific author on the Hugging Face Hub.

    Args:
        author: The username of the model author/organization to find models from.
    """
    real = _hub_stats_real(author)
    if real:
        return real
    # 模拟结果（保证演示闭环；真实部署时删除此分支）
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


# 统一工具列表（对应课程 tools=[...]）
TOOLS = [guest_info_retriever, web_search, weather_info, hub_stats]

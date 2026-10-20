"""
mcp_server.py —— 最小 MCP Server（P1）
==========================================
把项目已有的两个工具包装成 MCP 工具，通过 stdio 暴露给任何 MCP Client
（Cursor / Claude Desktop / 自研 agent）。

- knowledge_search：检索 AI Agent 课程知识库（复用 knowledge_retriever）
- web_search：联网搜索（复用 tools.py 的降级逻辑）

本地运行（stdio，由 Client 拉起进程）：
    python mcp_server.py

设计要点：
- 只用官方 mcp SDK 的 FastMCP，不自己手写 JSON-RPC；
- 工具内部复用项目已有逻辑，不在 server 里重复实现；
- 调用前复用 tool_policy 做参数级最小权限校验，与主项目防护一致。
"""

import logging

# 抑制 mcp SDK 的 INFO 请求日志，避免污染标准输出（stdio 通道）
logging.getLogger("mcp").setLevel(logging.WARNING)

from mcp.server.fastmcp import FastMCP

from knowledge_retriever import knowledge_search as _kb_search
from tools import web_search as _web_search_tool
from tool_policy import validate

mcp = FastMCP("new-for-agent")


@mcp.tool()
def knowledge_search(query: str) -> str:
    """检索 AI Agent 课程知识库（中文学习笔记），返回最相关文档片段。

    Args:
        query: 想了解的知识点或问题（中文效果最好）
    """
    ok, reason = validate("knowledge_search", {"query": query})
    if not ok:
        return f"⛔ 参数被最小权限策略拒绝：{reason}"
    return _kb_search(query)


@mcp.tool()
def web_search(query: str) -> str:
    """联网搜索最新信息；失败时返回降级提示。

    Args:
        query: 要搜索的关键词短语
    """
    ok, reason = validate("web_search", {"query": query})
    if not ok:
        return f"⛔ 参数被最小权限策略拒绝：{reason}"
    return _web_search_tool.invoke({"query": query})


if __name__ == "__main__":
    # 默认 stdio 传输：Client 通过标准输入输出与本进程通信
    mcp.run()

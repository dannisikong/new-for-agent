"""
mcp_client_check.py —— MCP Server 端到端自检（本地）
=====================================================
用官方 MCP Client 通过 stdio 拉起 mcp_server.py，
1) 列出可用工具；2) 各调用一次，打印结果摘要。
用于验证 server 能被标准 MCP Client 发现并成功调用。

运行：python mcp_client_check.py
"""

import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# server 进程的工作目录设为本项目根，保证能 import 本地模块
_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


async def main() -> None:
    # stdio_client 以子进程方式拉起 server
    params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
        cwd=_PROJECT_DIR,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # 1) 发现工具
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("== 已发现 MCP 工具：", names)

            # 2) 调用知识库检索
            kb = await session.call_tool(
                "knowledge_search", {"query": "什么是 ReAct？"}
            )
            print("\n== knowledge_search 返回（前300字）：")
            print(_text(kb)[:300])

            # 3) 调用联网搜索（环境可能联网受限，加超时容错，不阻塞自检）
            try:
                ws = await asyncio.wait_for(
                    session.call_tool(
                        "web_search", {"query": "MCP Model Context Protocol 是什么"}
                    ),
                    timeout=12,
                )
                print("\n== web_search 返回（前200字）：")
                print(_text(ws)[:200])
            except asyncio.TimeoutError:
                print("\n== web_search：联网超时（环境网络限制，走既有降级，不影响 MCP 链路）")

            # 4) 越权参数应被最小权限策略拒绝
            denied = await session.call_tool(
                "web_search", {"query": "; cat /etc/passwd"}
            )
            print("\n== 越权参数拦截（前120字）：")
            print(_text(denied)[:120])


def _text(result) -> str:
    """从 call_tool 返回里提取文本内容。"""
    parts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


if __name__ == "__main__":
    asyncio.run(main())

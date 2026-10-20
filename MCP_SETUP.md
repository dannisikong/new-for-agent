# MCP Server 接入说明（P1）

把项目已有的 `knowledge_search` / `web_search` 两个工具包装成标准 MCP Server，
任何兼容 MCP 的 Client（Cursor、Claude Desktop、自研 Agent）都能通过标准协议发现并调用，
不用改工具本身的实现。

## 架构

```
MCP Client（Cursor / Claude Desktop / 自研 Agent）
        │  stdio（JSON-RPC over 标准输入输出）
        ▼
mcp_server.py（FastMCP，只做协议适配，不含业务逻辑）
        ├── knowledge_search → knowledge_retriever.knowledge_search
        └── web_search       → tools.web_search（失败走既有降级）
        │
        └─ 调用前复用 tool_policy 做参数级最小权限校验
```

## 本地自检

```bash
# 1. 列出工具 + 实际调用（端到端验证）
python mcp_client_check.py
# 预期：发现 ['knowledge_search', 'web_search']，知识库召回成功，越权参数被拒

# 2. 单独启动 server（stdio，一般由 Client 拉起，手动调试用）
python mcp_server.py
```

## 在 Cursor 中接入

打开 Cursor → Settings → Tools & Integrations → Add Custom MCP，填入（把路径换成你本机绝对路径）：

```json
{
  "mcpServers": {
    "new-for-agent": {
      "command": "python3",
      "args": ["mcp_server.py"],
      "cwd": "/绝对路径/new-for-agent"
    }
  }
}
```

保存后在 Cursor 对话里直接说："用 knowledge_search 查一下什么是 ReAct"，
或"用 web_search 搜一下最新的 MCP 动态"。

## 关键点

- **传输**：本地用 stdio（Client 拉起 server 子进程，走标准输入输出）；远程 HTTP/SSE 是另一种场景，本最小版不涉及。
- **复用而非重写**：Server 只做协议适配，检索/搜索逻辑仍在 `knowledge_retriever.py`、`tools.py`。
- **安全一致**：MCP 边界同样过 `tool_policy` 参数校验，命令符/本地路径/超长参数被拒绝。
- **扩展**：新增工具只需在 `mcp_server.py` 用 `@mcp.tool()` 包一层，Client 无需改动即可发现。

## 面试可讲

> "我把项目工具用 MCP 协议暴露出去，Server 只做协议适配、业务逻辑零重复；
> 用官方 FastMCP 省掉手写 JSON-RPC，本地 stdio 跑通，并在 MCP 边界保留参数级最小权限校验。"

# 29 · MCP SDK 开发工具包

## 一句话总述

MCP SDK 是官方提供的代码库，让你不用自己写底层通信协议，直接用几行代码就能写出 MCP Server。

---

## 一、为什么需要 SDK？

MCP 协议本身是 JSON-RPC 格式的，如果从零手写，你需要处理：
- 协议握手和版本协商
- 消息序列化和反序列化
- 连接管理（stdio / HTTP）
- 错误处理和重试

官方 SDK 把这些底层细节都封装好了，你只需要写业务逻辑。

**类比**：就像你写网页不用自己解析 HTTP 协议，直接用 Flask/FastAPI 一样。

---

## 二、Python SDK 快速上手（FastMCP）

Python 官方 SDK 叫 `FastMCP`，写法非常简洁：

```python
from mcp.server.fastmcp import FastMCP

# 1. 创建一个 MCP Server
mcp = FastMCP("Weather Service")

# 2. 用装饰器注册一个 Tool（工具）
@mcp.tool()
def get_weather(location: str) -> str:
    """获取指定地点的天气"""
    return f"{location}：晴天，72°F"

# 3. 用装饰器注册一个 Resource（资源）
@mcp.resource("weather://{location}")
def weather_resource(location: str) -> str:
    """提供天气数据作为资源"""
    return f"{location} 天气数据：晴天，72°F"

# 4. 用装饰器注册一个 Prompt（提示词模板）
@mcp.prompt()
def weather_report(location: str) -> str:
    """生成天气预报提示词"""
    return f"你是天气预报员，请播报 {location} 的天气"

# 5. 启动服务
if __name__ == "__main__":
    mcp.run()
```

**关键点**：
- `@mcp.tool()` → 注册工具（LLM 可以调用）
- `@mcp.resource()` → 注册资源（只读数据）
- `@mcp.prompt()` → 注册提示词模板（用户可选）

---

## 三、TypeScript SDK 写法

TypeScript SDK 写法类似，用 `zod` 做参数校验：

```javascript
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({ name: "Weather Service", version: "1.0.0" });

// 注册 Tool
server.tool("get_weather", { location: z.string() }, async ({ location }) => ({
  content: [{ type: "text", text: `${location}：晴天，72°F` }],
}));

// 启动
const transport = new StdioServerTransport();
await server.connect(transport);
```

---

## 四、MCP Inspector 调试工具

写完 Server 后，怎么测试？官方提供了一个调试工具叫 **MCP Inspector**：

```bash
# Python
mcp dev server.py

# TypeScript
npx @modelcontextprotocol/inspector node ./index.mjs
```

启动后会打开一个网页界面（http://127.0.0.1:6274），你可以：
- 看到 Server 注册了哪些 Tool / Resource / Prompt
- 直接在网页上调用工具测试
- 查看请求和响应的完整内容

**类比**：就像 Postman 测试 API，MCP Inspector 是专门测 MCP Server 的工具。

---

## 五、官方 SDK 支持的语言

| 语言 | 维护方 | 状态 |
|---|---|---|
| TypeScript | Anthropic | 活跃 |
| Python | Anthropic | 活跃 |
| Java | Spring AI (VMware) | 活跃 |
| Kotlin | JetBrains | 活跃 |
| C# | Microsoft | 预览版 |
| Swift | loopwork-ai | 活跃 |
| Rust | Anthropic / 社区 | 活跃 |
| Dart | Flutter 社区 | 活跃 |

---

## 六、新手常见误区

### 误区1：以为 MCP Server 很难写
**实际**：FastMCP 装饰器几行代码就能写一个可用的 Server，难点不在写代码，在设计好的 Tool。

### 误区2：SDK 就是全部
**实际**：SDK 只是封装了通信协议，真正的价值在于你写的 Tool 好不好用、参数清不清楚、返回内容是不是 LLM 需要的。

### 误区3：MCP Inspector 没用
**实际**：调试 MCP Server 的必备工具，不用它你得自己写客户端测试，浪费时间。

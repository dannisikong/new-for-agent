<title>27 · MCP 通信协议：JSON-RPC、传输机制与生命周期</title>

# 27 · MCP 通信协议：JSON-RPC、传输机制与生命周期

<callout emoji="💡">
这是协议底层细节，实际写 MCP server 时 SDK 会帮你处理，不需要手撸 JSON。知道它长什么样、能调试时看懂就行。
</callout>

## 一、消息格式：JSON-RPC 2.0

MCP 所有 Client ↔ Server 通信都用 JSON-RPC 2.0 编码——一个轻量、人类可读、跨语言的 RPC 格式。

| 消息类型 | 方向 | 说明 | 例子 |
|-|-|-|-|
| **Request** | Client → Server | 带 id、method、参数，要对方执行 | tools/call，参数 name=weather |
| **Response** | Server → Client | 带同样 id，返回 result 或 error | 返回温度 62°F |
| **Notification** | Server → Client（单向） | 不需要响应的事件通知 | progress: 处理中 50% |

## 二、两种传输方式

| 传输 | 场景 | 原理 | 典型用途 |
|-|-|-|-|
| **stdio** | 本地（Client 和 Server 同机） | Host 把 Server 当子进程启动，通过标准输入/输出收发消息 | 文件系统、本地脚本、你写的 mcp_server.py 第一版 |
| **HTTP + SSE / Streamable HTTP** | 远程（跨机器） | HTTP 请求 + Server-Sent Events 长连接推送，可按需升级到流式 | 云端 API、共享服务、生产部署 |

## 三、交互生命周期（4 个阶段）

1. **Initialize（握手）**：Client 连 Server，双方交换协议版本和能力清单，Server 回支持的版本，Client 再发 initialized 通知确认
2. **Discovery（发现）**：Client 发 tools/list，Server 返回它提供的所有 Tool / Resource / Prompt 清单
3. **Execution（执行）**：Client 发 tools/call，Server 边执行边推 progress notification（可选），最后回 response
4. **Termination（结束）**：Client 发 shutdown，Server 确认，Client 再发 exit，连接关闭

## 四、为什么这样设计

- **版本协商**：握手时交换版本号，老 Server 也能和新 Client 兼容
- **能力发现**：Discovery 阶段才知道 Server 有啥，所以 Server 可以新增能力而不影响 Host
- **可演进**：协议预留扩展位，新能力通过能力协商逐步上线

<callout emoji="💡">
对我们项目的启发：第一版 mcp_server.py 用 stdio 就够了——Claude Code 启动时把子进程跑起来，通过 stdin/stdout 对话，不用开端口、不用配网络。等要部署给别人用了，再切 Streamable HTTP。
</callout>
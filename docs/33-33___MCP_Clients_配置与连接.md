# 33 · Building MCP Clients（一）：Client 配置与连接

## 一句话总述

Client 不用写代码也能先连上 Server：在 `mcp.json` / `config.json` 里写清"Server 叫什么、用什么传输、地址在哪"，Host（Cursor / 网页 UI）就会自动发现工具；远程用 SSE、本地脚本用 stdio，老版本不支持远程时用 `mcp-remote` 桥接。

---

## 一、Client 连接靠什么：配置文件

MCP 规范还在演进，配置方式会变，但当前最佳实践很统一：**所有主流 Host 都用配置文件管理 Server 连接**，文件定义"有哪些 Server、怎么连"，结构简单、跨 Host 一致。

**类比**：Server 是一家店，Client 是你手机里的外卖 App，配置文件就是"收货地址 + 店铺电话"清单，App 拿到就能下单，不用你重新认识这家店。

---

## 二、标准 `mcp.json` 结构

```json
{
  "servers": [
    {
      "name": "MCP Server",
      "transport": {
        "type": "sse",
        "url": "http://localhost:7860/gradio_api/mcp/sse"
      }
    }
  ]
}
```

每个 Server 条目就两个核心：
- `name`：给这个 Server 起个内部名字
- `transport`：怎么连
  - `type: "sse"` + `url`：连**远程/已启动的服务**（HTTP+SSE）
  - `type: "stdio"` + `command`/`args`：连**本地脚本**，Client 帮你拉起进程，走标准输入输出

### SSE 还是 stdio？怎么选

| 场景 | 传输 | 理由 |
|---|---|---|
| Gradio Server 跑在远程/线上（HF Spaces） | `sse` + url | 服务已独立运行，Client 只要联网连地址 |
| 本地一个 Python 脚本当 Server | `stdio` | Client 直接启动这个进程，通过标准输入输出通信 |

> 课程假设 Gradio 跑在远程，所以用 SSE；连本地脚本时 stdio 更合适。

### 远程 HTTP+SSE 配置示例

```json
{
  "servers": [
    {
      "name": "Remote MCP Server",
      "transport": {
        "type": "sse",
        "url": "https://example.com/gradio_api/mcp/sse"
      }
    }
  ]
}
```

---

## 三、UI Client 的配置（`config.json`）

连 Gradio MCP Server 的网页 UI 客户端，用另一种更扁平的写法（注意键名是 `mcpServers`，不是 `servers`）：

```json
{
  "mcpServers": {
    "mcp": {
      "url": "http://localhost:7860/gradio_api/mcp/sse"
    }
  }
}
```

**两种格式别混**：

| 格式 | 顶层键 | 结构 | 用在哪 |
|---|---|---|---|
| 标准 mcp.json | `servers`（数组） | 每项含 `transport` 对象 | 通用规范、部分 Host |
| UI / Cursor config | `mcpServers`（对象） | 键是 Server 名，值直接放 `url` 或 `command/args` | 网页 UI、Cursor |

---

## 四、在 Cursor 里配置（内置 MCP 支持）

Cursor 原生支持 MCP，把部署好的 Server 直接接进开发环境。

**入口**：设置（`Ctrl/Cmd + Shift + J`）→ **Tools & Integrations** 标签 → **Add Custom MCP**。

### 老写法：用 `mcp-remote` 桥接

**macOS：**
```json
{
  "mcpServers": {
    "sentiment-analysis": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://YOURUSERNAME-mcp-sentiment.hf.space/gradio_api/mcp/sse",
        "--transport",
        "sse-only"
      ]
    }
  }
}
```

**Windows（多一层 `cmd /c`）：**
```json
{
  "mcpServers": {
    "sentiment-analysis": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "mcp-remote",
        "https://YOURUSERNAME-mcp-sentiment.hf.space/gradio_api/mcp/sse",
        "--transport",
        "sse-only"
      ]
    }
  }
}
```

### 为什么需要 `mcp-remote`？

早期 MCP Client（包括旧版 Cursor）**只支持本地 stdio Server**，不支持带鉴权的远程 Server。`mcp-remote` 是当时的补丁方案：

- 在你本机运行
- 把 Cursor 和远程 MCP Server 桥接起来
- 隐式处理传输转换和鉴权
- 仍沿用熟悉的配置文件格式

**现状（2025 年中起）**：Cursor 已原生支持远程 HTTP+SSE 和 OAuth，大多数情况**不需要 mcp-remote**，直接写 url 即可：

```json
{
  "mcpServers": {
    "my-server": {
      "url": "https://your-mcp-server.hf.space/gradio_api/mcp/sse"
    }
  }
}
```

> 仅在老环境或特定兼容问题下才退回 mcp-remote。最新写法以 Cursor 官方文档为准。

### 配好后怎么用

在 Cursor 对话里直接让它调用这个情感分析工具，比如：分析代码注释、用户反馈、PR 描述的情绪倾向——工具自动出现在可用工具列表里。

---

## 五、新手误区

### 误区1：以为 Client 一定要写代码
**实际**：这一节就是"零代码连接"，改配置文件就能让 Cursor / UI 发现并调用 Server。写代码的 Client（JS / smolagents）是下一节，用于自己程序里集成。

### 误区2：把 `servers` 和 `mcpServers` 两种格式混用
**实际**：标准规范用 `servers` 数组，UI/Cursor 用 `mcpServers` 对象，照对应 Host 的要求写，别自己发明结构。

### 误区3：本地脚本也硬用 sse
**实际**：本地脚本用 stdio（Client 帮你起进程），远程服务才用 sse（给 url）。

### 误区4：无脑套 mcp-remote
**实际**：新版 Cursor 原生支持远程 url，mcp-remote 是兼容补丁，先试直连，连不上再桥接。

---

## 六、待续

本节只讲了"配置连接"，下一节进入**代码级 Client**：
1. HuggingFace.js 客户端（参考 Tiny Agents）
2. smolagents Python 客户端

同一个已部署的 Server，两种语言代码都能调。

# 36 · Tiny Agents（TS + Python）与 Unit 2 端到端闭环

## 一句话总述

Tiny Agents 是 Hugging Face 的极简 MCP Client：一个 JSON 配置（模型 + provider + servers）就能起 Agent，用 `mcp-remote` 桥接 SSE Server；TypeScript 和 Python 两套写法等价，至此完成"Gradio Server → 多 Client 连接"的完整闭环。

---

## 一、Unit 2 完整闭环回顾

```
┌──────────────────────────────────────────────────────────────┐
│ ① Gradio MCP Server（app.py, launch(mcp_server=True)）        │
│    暴露 sentiment_analysis 工具 → 部署到 HF Spaces             │
└───────────────▲───────────────────────────────┬──────────────┘
                │ SSE / mcp-remote 桥接          │
┌───────────────┴───────────────────────────────▼──────────────┐
│ ② 多种 Client 连接同一个 Server：                             │
│   · UI Client / Cursor（配置文件直连或 mcp-remote）            │
│   · smolagents MCPClient + CodeAgent + Gradio ChatInterface   │
│   · Tiny Agents（TS / Python，本节）                           │
│   · Continue + 本地开源模型（Ollama/Llama.cpp/LM Studio）      │
└───────────────────────────────────────────────────────────────┘
```

**核心思想**：用熟悉的框架（Gradio）做专用工具 → 通过 MCP 标准化暴露 → 任何兼容 Client/Agent 都能无缝调用，还能和文件系统、浏览等其他工具组合。

---

## 二、安装

Tiny Agent 通过命令行环境跑 MCP Server，所以 Python 和 JS 都需要 `npx`：

```bash
# 1. 装 npx（没有 npm 先装 Node.js）
npm install -g npx

# 2. mcp-remote 桥接（部分 Client 如 Claude Desktop 不支持 SSE 时用）
npm i mcp-remote

# 3. JS 版 Tiny Agents
npm install @huggingface/tiny-agents

# 4. Python 版
pip install "huggingface_hub[mcp]>=0.32.0"
```

---

## 三、命令行版：一个 `agent.json` 起 Agent

```bash
mkdir my-agent && touch my-agent/agent.json && cd my-agent
```

```json
{
    "model": "Qwen/Qwen2.5-72B-Instruct",
    "provider": "novita",
    "servers": [
        {
            "type": "stdio",
            "command": "npx",
            "args": ["mcp-remote", "http://localhost:7860/gradio_api/mcp/sse"]
        }
    ]
}
```

运行：
```bash
npx @huggingface/tiny-agents run agent.json   # JS
# 或
tiny-agents run agent.json                    # Python
```

**配置字段**：

| 字段 | 含义 |
|---|---|
| `model` | Agent 用的开源模型 |
| `provider` | 推理服务提供商（如 novita） |
| `servers` | 要连的 MCP Server 列表；这里用 mcp-remote 桥接 Gradio SSE |

### 变体：接本地模型

把 `provider` 换成 `endpointUrl`（OpenAI 兼容端点）即可连本机推理服务：

```json
{
    "model": "Qwen/Qwen3-32B",
    "endpointUrl": "http://localhost:1234/v1",
    "servers": [
        {
            "type": "stdio",
            "command": "npx",
            "args": ["mcp-remote", "http://localhost:1234/v1/mcp/sse"]
        }
    ]
}
```

---

## 四、代码版：TS 与 Python 等价写法

### TypeScript

```ts
import { Agent } from "@huggingface/tiny-agents";

const agent = new Agent({
    provider: process.env.PROVIDER ?? "novita",
    model: process.env.MODEL_ID ?? "Qwen/Qwen2.5-72B-Instruct",
    apiKey: process.env.HF_TOKEN,
    servers: [
        {
            command: "npx",
            args: ["mcp-remote", "http://localhost:7860/gradio_api/mcp/sse"]
        }
    ],
});
```

### Python

```python
import os
from huggingface_hub import Agent

agent = Agent(
    model="Qwen/Qwen2.5-72B-Instruct",
    provider="novita",
    servers=[
        {
            "command": "npx",
            "args": ["mcp-remote", "http://localhost:7860/gradio_api/mcp/sse"]
        }
    ],
)
```

两版结构一一对应：`provider / model / apiKey(token) / servers[]`，只是语言不同。

### 工具组合场景

挂上情感分析 Server 后，Agent 可以把它和其他工具串起来：
1. 用文件系统 Server 读一个文本文件
2. 调 Gradio Server 的情感分析工具
3. 把结果写回文件

这就是 MCP 的"积木"效果：专用工具 + 通用能力（文件、浏览）自由拼接。

---

## 五、部署后改 URL

Server 推到 HF Spaces 后，把配置里的本地地址换成线上 sse：

```json
{
    "command": "npx",
    "args": [
        "mcp-remote",
        "https://YOUR_USERNAME-mcp-sentiment.hf.space/gradio_api/mcp/sse"
    ]
}
```

Agent 在任何地方都能用这个情感分析工具，不再局限本机。

---

## 六、Unit 2 学完你掌握了什么

| 能力 | 对应章节 |
|---|---|
| 用 Gradio `mcp_server=True` 把 Python 函数变成 MCP 工具 + 网页 | 32 |
| 写 mcp.json / config 连接 Server，区分 sse/stdio、mcp-remote 桥接 | 33 |
| Continue + 本地开源模型（须支持 tool calling）挂 MCP | 34 |
| smolagents MCPClient + CodeAgent + Gradio ChatInterface 当 Client | 35 |
| Tiny Agents（TS/Python）命令行与代码两种方式起 Agent | 36 |
| 把 Server/Client 部署到 HF Spaces | 32 / 35 |

**面试可讲的一句话**："我用 Gradio 写过一个情感分析 MCP Server 并部署到 HF Spaces，分别用 Cursor、smolagents、Tiny Agents（TS/Python）三种 Client 连上，理解了 sse/stdio 传输、mcp-remote 桥接和工具标准化复用。"

---

## 七、新手误区

**误区1：Tiny Agents 还要自己写工具调用逻辑**
**实际**：它只负责连 Server、动态发现工具，工具调用由 Agent 循环完成，配置里声明 servers 即可。

**误区2：apiKey 写进配置文件**
**实际**：走环境变量 `HF_TOKEN`，代码里 `process.env` / `os.getenv` 读取。

**误区3：本地和线上用同一个 URL**
**实际**：本地 `localhost:7860`，部署后必须换成 hf.space 线上 sse 地址。

---

## 八、延伸阅读

- Python Tiny Agents 博客：huggingface.co/blog/python-tiny-agents
- TypeScript Tiny Agents 博客：huggingface.co/blog/tiny-agents
- Tiny Agents 官方文档：huggingface.co/docs/huggingface.js

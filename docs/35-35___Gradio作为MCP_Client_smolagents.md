# 35 · Gradio 作为 MCP Client（smolagents 连远程 Server）

## 一句话总述

视角反转：前面 Gradio 当 Server 暴露工具，这节用 smolagents 的 `MCPClient` 连上远程 Server、把工具取出来喂给 `CodeAgent`，再套一层 `gr.ChatInterface` 当聊天界面——Gradio 在这里是 Client 的 UI 壳。

---

## 一、整体数据流

```
┌──────────────────────────┐   SSE    ┌─────────────────────────┐
│ 远程 MCP Server           │ ───────▶ │ MCPClient (smolagents)  │
│ abidlabs-mcp-tool-http    │          │ get_tools() 取工具清单   │
│ (HF Spaces 上已运行)       │          └───────────┬─────────────┘
└──────────────────────────┘                      ▼
                                    ┌─────────────────────────┐
                                    │ CodeAgent                │
                                    │ tools=[*tools]           │
                                    │ model=InferenceClientModel│
                                    └───────────┬─────────────┘
                                                ▼
                                    ┌─────────────────────────┐
                                    │ gr.ChatInterface 网页    │
                                    │ 用户提问 → agent.run()   │
                                    └─────────────────────────┘
```

**类比**：上一节是"我开店卖工具"（Gradio Server），这节是"我当顾客，去别人店里挑工具，雇个管家（Agent）拿着工具帮我办事，再在自家客厅摆个接待台（ChatInterface）"。

---

## 二、先单独测连接：列出远程工具

不写界面，先用 `MCPClient` 连上看看 Server 提供了什么：

```python
from smolagents.mcp_client import MCPClient

with MCPClient(
    {"url": "https://abidlabs-mcp-tool-http.hf.space/gradio_api/mcp/sse",
     "transport": "sse"}
) as tools:
    print("\n".join(f"{t.name}: {t.description}" for t in tools))
```

输出（这个示例 Server 带 4 个工具）：
```
prime_factors: Compute the prime factorization of a positive integer.
generate_cheetah_image: Generate a cheetah image.
image_orientation: Returns whether image is portrait or landscape.
sepia: Apply a sepia filter to the input image.
```

`with` 上下文退出自动断开；工具以 `name + description` 形式暴露给 Agent。

---

## 三、安装依赖

```bash
pip install "smolagents[mcp]" "gradio[mcp]" mcp fastmcp
```

- `smolagents[mcp]`：带 MCP 客户端能力的 smolagents
- `gradio[mcp]`：Gradio MCP 扩展
- `mcp` / `fastmcp`：协议底层库

---

## 四、代码四步走

### 第1步：连 Server、取工具

```python
from smolagents import InferenceClientModel, CodeAgent, MCPClient

mcp_client = MCPClient(
    {"url": "https://abidlabs-mcp-tool-http.hf.space/gradio_api/mcp/sse",
     "transport": "sse"}
)
tools = mcp_client.get_tools()
```

### 第2步：建模型 + Agent

```python
import os
model = InferenceClientModel(token=os.getenv("HF_TOKEN"))
agent = CodeAgent(tools=[*tools], model=model)
```

- `InferenceClientModel` 走 HF Inference API，token 从 HF 账号拿，用环境变量 `HF_TOKEN` 传入，**不要硬编码**
- `tools=[*tools]` 把 MCP 取到的工具展开传给 Agent

### 第3步：套 Gradio 聊天界面

```python
import gradio as gr

demo = gr.ChatInterface(
    fn=lambda message, history: str(agent.run(message)),
    type="messages",
    examples=["Prime factorization of 68"],
    title="Agent with MCP Tools",
    description="This is a simple agent that uses MCP tools to answer questions."
)

demo.launch()
```

`type="messages"` 用新版消息格式；`agent.run(message)` 执行后转成字符串返回给界面。

---

## 五、完整示例（含资源释放）

```python
import gradio as gr
import os
from smolagents import InferenceClientModel, CodeAgent, MCPClient

try:
    mcp_client = MCPClient(
        {"url": "https://abidlabs-mcp-tool-http.hf.space/gradio_api/mcp/sse",
         "transport": "sse"}
    )
    tools = mcp_client.get_tools()

    model = InferenceClientModel(token=os.getenv("HUGGINGFACE_API_TOKEN"))
    agent = CodeAgent(
        tools=[*tools],
        model=model,
        additional_authorized_imports=["json", "ast", "urllib", "base64"]
    )

    demo = gr.ChatInterface(
        fn=lambda message, history: str(agent.run(message)),
        type="messages",
        examples=["Analyze the sentiment of the following text 'This is awesome'"],
        title="Agent with MCP Tools",
    )
    demo.launch()
finally:
    mcp_client.disconnect()
```

**两个关键点**：
1. **`finally` 里 `disconnect()`**：MCP Client 是长连接对象，程序退出必须显式关闭，否则连接泄漏。
2. **`additional_authorized_imports`**：CodeAgent 会自己写代码执行，这里白名单允许它 import `json/ast/urllib/base64`，安全沙箱只放行列出的库。

---

## 六、部署到 HF Spaces

1. New Space → SDK 选 Gradio → 命名（如 `mcp-client`）
2. 代码里填对远程 Server 的 sse URL
3. `requirements.txt`：

```txt
gradio[mcp]
smolagents[mcp]
```

4. 推送：

```bash
git init
git add app.py requirements.txt
git commit -m "Initial commit"
git remote add origin https://huggingface.co/spaces/YOUR_USERNAME/mcp-client
git push -u origin main
```

> 认证用 AccessToken（HF 已弃用密码 git 推送），参考官方 password-git-deprecation 说明。

---

## 七、新手误区

### 误区1：以为 Gradio 只能当 Server
**实际**：Gradio 擅长做 UI Client 和 Server，这节就是把它当 Client 的界面壳，真正连 Server 的是 smolagents 的 MCPClient。

### 误区2：忘了 finally disconnect
**实际**：Client 是长连接，不显式关闭会泄漏；用 try/finally 兜底。

### 误区3：把 HF token 写进代码
**实际**：走环境变量 `HF_TOKEN` / `HUGGINGFACE_API_TOKEN`，Space 里配 Secrets，别硬编码。

### 误区4：CodeAgent 不放行必要库导致报错
**实际**：Agent 自己生成的代码要 import 什么，必须进 `additional_authorized_imports` 白名单，否则沙箱拦截。

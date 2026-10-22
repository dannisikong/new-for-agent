# 32 · Building the Gradio MCP Server（情感分析服务）

## 一句话总述

给普通 Python 函数套一层 `gr.Interface` 并在 `launch(mcp_server=True)`，Gradio 就自动把它同时变成"人能点的网页"和"AI 能调的 MCP 工具"，你不用手写一行 HTTP 或 JSON-RPC。

---

## 一、Gradio MCP 到底帮你做了什么？

传统做法：写一个函数 → 自己包 HTTP 服务 → 自己定义 JSON-RPC 协议 → 再单独做个网页，四件事。

Gradio 的做法：`mcp_server=True` 一个开关，自动完成 5 件事：

```
                    ┌─────────────────────────────────────┐
                    │          你的 Python 函数            │
                    │   sentiment_analysis(text) -> json  │
                    └──────────────┬──────────────────────┘
                                   │ Gradio 自动转换
                 ┌─────────────────┴─────────────────┐
                 ▼                                     ▼
        ┌──────────────────┐              ┌──────────────────────────┐
        │  网页界面 (Web UI) │              │  MCP Server 端点          │
        │  人打开浏览器点按钮 │              │  JSON-RPC over HTTP+SSE   │
        │  localhost:7860   │              │  /gradio_api/mcp/sse      │
        └──────────────────┘              └──────────────────────────┘
                 给"人"用                          给"AI 模型"用
```

**Gradio 自动做的 5 步**：
1. 把你的函数自动转换成 MCP Tool
2. 把输入组件（Textbox）映射成工具的参数 schema
3. 从输出组件推断响应格式
4. 搭好 JSON-RPC over HTTP+SSE 的通信层
5. 同时产出网页界面和 MCP 服务端点

**类比**：一个函数像一道菜，Gradio 给它同时开了两个窗口——一个窗口端给堂食客人（网页，人点按钮），一个窗口端给外卖平台（MCP，AI 按协议下单），厨房（函数）只有一个。

---

## 二、项目搭建

```bash
mkdir mcp-sentiment
cd mcp-sentiment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install "gradio[mcp]" textblob
```

- `gradio[mcp]`：带 MCP 扩展的 Gradio（默认包不含 MCP 能力）
- `textblob`：轻量英文情感分析库，本项目只当演示工具，不深究算法

> 注意：部署到 Hugging Face Spaces 时，入口文件名必须叫 `app.py`（Space 按这个文件名找启动脚本）。

---

## 三、完整代码 `app.py`

```python
import json
import gradio as gr
from textblob import TextBlob

def sentiment_analysis(text: str) -> str:
    """
    Analyze the sentiment of the given text.

    Args:
        text (str): The text to analyze

    Returns:
        str: A JSON string containing polarity, subjectivity, and assessment
    """
    blob = TextBlob(text)
    sentiment = blob.sentiment

    result = {
        "polarity": round(sentiment.polarity, 2),        # -1(负面) ~ 1(正面)
        "subjectivity": round(sentiment.subjectivity, 2), # 0(客观) ~ 1(主观)
        "assessment": "positive" if sentiment.polarity > 0
                      else "negative" if sentiment.polarity < 0
                      else "neutral"
    }

    return json.dumps(result)

# 一个 Interface 同时生成网页 + MCP 工具
demo = gr.Interface(
    fn=sentiment_analysis,
    inputs=gr.Textbox(placeholder="Enter text to analyze..."),
    outputs=gr.Textbox(),
    title="Text Sentiment Analysis",
    description="Analyze the sentiment of text using TextBlob"
)

if __name__ == "__main__":
    demo.launch(mcp_server=True)
```

---

## 四、逐块解读

### 1. 函数本身（MCP Tool 的"真身"）

| 要素 | 作用 | 为什么关键 |
|---|---|---|
| `text: str` 类型提示 | 告诉 Gradio 参数是什么类型 | 自动生成 MCP 参数 schema 的依据 |
| docstring（含 `Args:` 块） | 描述参数含义 | Gradio 据此生成工具说明，AI 靠它理解"这个工具干嘛的" |
| `-> str` 返回类型 | 声明返回值类型 | 决定输出 schema |
| 返回 `json.dumps(result)` | 返回 JSON 字符串 | MCP 传输要求可序列化；这里故意用 Textbox 而不是 JSON 组件 |

**TextBlob 三个输出字段**：
- `polarity`（极性）：-1 最负面 → 0 中性 → 1 最正面
- `subjectivity`（主观性）：0 完全客观事实 → 1 纯主观感受
- `assessment`：按 polarity 符号判成 positive / negative / neutral

### 2. `gr.Interface`（双窗口开关）

```python
demo = gr.Interface(
    fn=sentiment_analysis,      # 绑定哪个函数
    inputs=gr.Textbox(...),     # 网页输入框 = MCP 工具的入参
    outputs=gr.Textbox(),       # 网页输出框 = MCP 工具的返回
    title=..., description=...  # 网页展示文案
)
```

输入/输出组件同时承担两个职责：**网页上长什么样** + **MCP schema 里参数怎么定义**。

### 3. `launch(mcp_server=True)`（真正打开 MCP 窗口）

- 也可以不开代码，用环境变量：`export GRADIO_MCP_SERVER=True`
- 启动后两个地址同时可用：

| 用途 | 地址 |
|---|---|
| 人用的网页 | `http://localhost:7860` |
| MCP SSE 端点 | `http://localhost:7860/gradio_api/mcp/sse` |
| 工具 schema 查看 | `http://localhost:7860/gradio_api/mcp/schema` |

---

## 五、本地测试两种方式

**方式1：网页手测**
1. 浏览器打开 `http://localhost:7860`
2. 输入一句话点 Submit，看返回的 JSON

**方式2：看 MCP schema**
- 访问 `http://localhost:7860/gradio_api/mcp/schema`，这就是 Client 连接后看到的工具清单
- 也可以在 Gradio 网页页脚点 "View API" 链接查看

---

## 六、排坑清单（Troubleshooting）

| 坑 | 解法 |
|---|---|
| MCP 工具 schema 生成不准 | 一定写全**类型提示** + docstring 的 `Args:` 块，Gradio 靠这两样生成 schema |
| 参数类型兼容性差 | 入参先统一收 `str`，函数内部再转成需要的类型，对 MCP Client 最友好 |
| Client 不支持 SSE 传输 | 用 `mcp-remote` 桥接（见下方配置） |
| 连不上 | 先重启 Server 和 Client，确认 Server 在跑、schema 地址可访问 |

**SSE 不支持时的桥接配置**（写进 Client 的 mcp 配置）：

```json
{
  "mcpServers": {
    "gradio": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://localhost:7860/gradio_api/mcp/sse"
      ]
    }
  }
}
```

`mcp-remote` 把 SSE 端点转成 Client 能识别的形式，相当于给两种传输协议之间加个翻译。

---

## 七、部署到 Hugging Face Spaces

1. 打开 huggingface.co/spaces → New Space
2. 命名（如 `mcp-sentiment`），**SDK 选 Gradio**，Create
3. 在 Space 里建 `requirements.txt`：

```txt
gradio[mcp]
textblob
```

4. 本地 git 推送：

```bash
git init
git add app.py requirements.txt
git commit -m "Initial commit"
git remote add origin https://huggingface.co/spaces/YOUR_USERNAME/mcp-sentiment
git push -u origin main
```

5. 部署成功后，线上 MCP 端点：

```
https://YOUR_USERNAME-mcp-sentiment.hf.space/gradio_api/mcp/sse
```

本地 `localhost:7860` 换成线上 `你的用户名-mcp-sentiment.hf.space`，路径 `/gradio_api/mcp/sse` 不变——这正是 MCP 的价值：Server 从本地搬到线上，Client 配置只改一个 URL。

---

## 八、新手误区

### 误区1：以为要自己写 MCP 协议代码
**实际**：Gradio 模式下你只写业务函数，JSON-RPC、SSE、schema 全是自动生成的，这是 Gradio MCP 相比手写 FastMCP 最大的省事点。

### 误区2：docstring 随便写写
**实际**：docstring 的 `Args:` 块就是 AI 看到的工具说明书，写得含糊，模型就不知道什么时候该调这个工具。

### 误区3：输出直接返回 Python dict
**实际**：MCP 走 JSON 传输，示例里用 `json.dumps()` 转成字符串再返回，避免序列化问题；输出组件也用 Textbox 而不是 JSON 组件。

### 误区4：部署后忘了入口文件名
**实际**：HF Spaces 只认 `app.py` 当启动文件，叫别的名字 Space 起不来。

---

## 九、下一步

Server 跑起来后，下一节做两个 Client 连它：
1. HuggingFace.js 客户端（参考 Tiny Agents）
2. smolagents Python 客户端

同一个 Server，两种语言 Client 都能调——这就是 MCP "一次实现、处处连接"的意义。

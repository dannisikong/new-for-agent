# 34 · MCP 接本地/开源模型（Continue + Ollama/Llama.cpp/LM Studio）

## 一句话总述

用 VS Code 扩展 Continue 当助手壳，把模型换成本机跑的开源模型（Ollama / Llama.cpp / LM Studio），再通过 yaml 挂上 MCP Server，就能在完全本地、代码数据不出机器的情况下跑工具调用。

---

## 一、三个角色怎么搭

```
┌─────────────────────────────────────────────────────────┐
│  Continue（VS Code / JetBrains 扩展，助手"外壳"）         │
│  ├─ 模型层：本机开源模型（Ollama / Llama.cpp / LM Studio）│
│  └─ 工具层：内置工具 + MCP Server（如 Playwright）        │
└─────────────────────────────────────────────────────────┘
        全部跑在本机 → 代码和数据不出机器，隐私可控
```

**类比**：Continue 是店里的服务员（外壳），本地模型是店员大脑（模型），MCP Server 是外包的专项师傅（工具），三个都在自己店里，不用把客人资料递给外面公司。

---

## 二、安装 Continue

1. VS Code marketplace 搜 Continue 扩展 → Install（页面点一次、VS Code 里再点一次）
2. 左侧栏出现 Continue logo，建议拖到右侧边栏体验更好
3. JetBrains 系也有对应插件

---

## 三、本地模型三种跑法（任选其一）

| 工具 | 特点 | 启动方式 |
|---|---|---|
| **Ollama** | 开源、最易用，一行命令拉模型 | `ollama run hf.co/unsloth/Devstral-Small-2505-GGUF:Q4_K_M` |
| **Llama.cpp** | 高性能 C++ 库，`llama-server` 提供 OpenAI 兼容 HTTP server | `llama-server -hf unsloth/Devstral-Small-2505-GGUF:Q4_K_M` |
| **LM Studio** | 图形界面，最省事 | 下载模型 → Local Server tab → Start Server |

模型从 Hugging Face Hub 获取，Hub 页面会给各本地推理工具的一键命令/快捷链接。

**显存/内存坑**：示例 Devstral-Small 约 14GB，机器 RAM 不够会报 `model requires more system memory than is available`，先确认内存再跑。

### 关键前提：模型必须内建 Tool Calling

能调工具的模型要求**原生支持工具调用**，如 Codestral、Qwen、Llama 3.1x。普通纯聊天模型没有 tool calling 能力，挂了 MCP 也不会发起工具调用。

---

## 四、配置模型（`.continue/models/local-models.yaml`）

在工作区顶层建 `.continue/models` 文件夹，放模型配置文件。三种 provider 写法：

### Llama.cpp（llama-server，端口 8080）

```yaml
name: Llama.cpp model
version: 0.0.1
schema: v1
models:
  - provider: llama.cpp
    model: unsloth/Devstral-Small-2505-GGUF
    apiBase: http://localhost:8080
    defaultCompletionOptions:
      contextLength: 8192      # 按模型调整
    name: Llama.cpp Devstral-Small
    roles: [chat, edit]
```

### LM Studio（端口 1234/v1）

```yaml
name: LM Studio Model
version: 0.0.1
schema: v1
models:
  - provider: lmstudio
    model: unsloth/Devstral-Small-2505-GGUF
    name: LM Studio Devstral-Small
    apiBase: http://localhost:1234/v1
    roles: [chat, edit]
```

### Ollama

```yaml
name: Ollama Devstral model
version: 0.0.1
schema: v1
models:
  - provider: ollama
    model: unsloth/devstral-small-2505-gguf:Q4_K_M
    defaultCompletionOptions:
      contextLength: 8192
    name: Ollama Devstral-Small
    roles: [chat, edit]
```

**要点**：
- `apiBase` 指向本地服务端口（8080 / 1234 / Ollama 默认端口）
- `contextLength` 要留够：多次 MCP 请求会累积 token，小窗口容易溢出
- `roles` 声明这个模型能承担 `chat`（对话）和 `edit`（改代码）

---

## 五、Tool Handshake（工具握手六步循环）

工具以 JSON 对象（名字 + 参数 schema）交给模型，比如 `read_file(filepath)` 让模型能请求指定文件内容。完整循环：

```
① 用户提问，可用工具清单随请求一起发给模型
        ↓
② 模型决定：要不要在回复里发起 tool call
        ↓
③ 用户授权（该工具策略设为 Automatic 则跳过）
        ↓
④ Continue 执行工具（内置功能 或 对应的 MCP Server）
        ↓
⑤ 工具结果发回模型
        ↓
⑥ 模型再响应，可能再次发起 tool call → 回到②，循环
```

> Continue 同时支持 OpenAI / Anthropic / Azure / Mistral 等云端 provider，本节聚焦本地优先，但本质是通用的。

---

## 六、挂一个 MCP Server（Playwright 浏览器）

工作区顶层建 `.continue/mcpServers` 文件夹，写 `playwright-mcp.yaml`：

```yaml
name: Playwright mcpServer
version: 0.0.1
schema: v1
mcpServers:
  - name: Browser search
    command: npx
    args:
      - "@playwright/mcp@latest"
```

**测试任务**（直接让它干完，不要输出代码）：
1. 用 Playwright 打开 https://news.ycombinator.com
2. 提取首页前 4 条帖子的标题和 URL
3. 在项目根目录建 `hn.txt`
4. 每行"标题 - URL"纯文本写进去

完成后工作目录会生成 `hn.txt`。

---

## 七、价值与误区

### 这套方案的意义

本地模型 + MCP Server 组合，代码和数据留在本机，同时能用 web 自动化、文件管理等专项工具；还能去 Continue Hub 的 MCP 探索页挑选更多 Server 自定义助手。

### 新手误区

**误区1：随便下个开源模型就能调 MCP 工具**
**实际**：必须选原生 tool calling 的模型（Codestral/Qwen/Llama 3.1x），否则模型不会发起工具调用。

**误区2：contextLength 用默认值就够**
**实际**：多轮 MCP 请求会累积 token，窗口小了中途溢出，要按任务调大。

**误区3：Continue 和 Cursor 配置格式一样**
**实际**：Continue 用 `.continue/` 下的 **yaml**（models、mcpServers 分开配），Cursor 用 JSON，别照搬。

**误区4：内存不够硬跑大模型**
**实际**：先看模型体积（示例 14GB），RAM 不足直接报错，选更小量化版（Q4_K_M）或更小模型。

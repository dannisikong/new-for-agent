# 30 · MCP Clients 客户端

## 一句话总述

MCP Client 是 Host 应用（比如 Claude Desktop、Cursor）里负责和 MCP Server 通信的模块，你只需要在配置文件里告诉它 Server 在哪、怎么连，它就会自动发现工具并调用。

---

## 一、什么是 MCP Client？

之前讲过 MCP 架构有三个角色：
- **Host**：用户直接用的应用（Claude Desktop、Cursor、VS Code）
- **Client**：Host 内部的一个模块，专门负责和某个 MCP Server 通信
- **Server**：提供工具/资源/提示词的外部服务

**类比**：Host 是你的电脑，Client 是 USB-C 接口，Server 是 U 盘/鼠标/键盘。你插上去就能用，不用管内部协议。

---

## 二、常见的 MCP Client 有哪些？

| 类型 | 代表 |
|---|---|
| 聊天界面 | Claude Desktop（Anthropic 官方） |
| IDE 编辑器 | Cursor（内置 MCP）、VS Code（Continue 插件）、Zed |

这些 Client 都支持同时连接多个 MCP Server，实时调用工具。

---

## 三、怎么配置 MCP Client？

所有 MCP Host 都用同一个配置文件叫 **`mcp.json`**，结构非常简单：

```json
{
  "servers": [
    {
      "name": "Server 名字",
      "transport": {
        "type": "stdio 或 sse"
      }
    }
  ]
}
```

### 场景1：本地 Server（stdio 传输）

比如你写了一个 Python 脚本当 Server：

```json
{
  "servers": [
    {
      "name": "File Explorer",
      "transport": {
        "type": "stdio",
        "command": "python",
        "args": ["/path/to/file_explorer_server.py"]
      }
    }
  ]
}
```

**说明**：Client 会启动这个 Python 进程，通过标准输入输出和它通信。

### 场景2：远程 Server（SSE 传输）

比如远程部署的天气 API：

```json
{
  "servers": [
    {
      "name": "Weather API",
      "transport": {
        "type": "sse",
        "url": "https://example.com/mcp-server"
      }
    }
  ]
}
```

### 场景3：传环境变量（API Key）

Server 需要 API Key 怎么办？用 `env` 字段传：

```json
{
  "servers": [
    {
      "name": "GitHub API",
      "transport": {
        "type": "stdio",
        "command": "python",
        "args": ["/path/to/github_server.py"],
        "env": {
          "GITHUB_TOKEN": "你的token"
        }
      }
    }
  ]
}
```

Server 代码里直接 `os.environ.get("GITHUB_TOKEN")` 就能拿到。

---

## 四、快速连接 Hugging Face MCP Server

Hugging Face 提供了一个托管的 MCP Server，自带模型/数据集/Space/论文搜索工具：

1. 登录 https://huggingface.co/settings/mcp
2. 选择你的 Client（VS Code / Cursor / Claude Desktop）
3. 复制生成的配置片段，粘贴到 Client 的配置文件里
4. 重启 Client，就能看到"Hugging Face"连上了

**提示**：用生成的配置片段，不要手写，它会根据你的 Client 自动调整格式。

---

## 五、代码级 Client：Tiny Agents

除了在 IDE 里配，你也可以在自己的代码里当 Client：

```bash
# 安装
pip install "huggingface_hub[mcp]>=0.32.0"
```

然后写一个 `agent.json`：

```json
{
    "name": "playwright-agent",
    "model": "Qwen/Qwen2.5-72B-Instruct",
    "provider": "novita",
    "servers": [
        {
            "type": "stdio",
            "command": "npx",
            "args": ["@playwright/mcp@latest"]
        }
    ]
}
```

运行：
```bash
tiny-agents run agent.json
```

这个 Agent 就能用 Playwright 控制浏览器了。

---

## 六、新手常见误区

### 误区1：以为 Client 和 Host 是一回事
**实际**：Host 是整个应用，Client 是应用内部负责和 Server 通信的那个模块。一个 Host 可以有多个 Client（连多个 Server）。

### 误区2：配置文件很复杂
**实际**：mcp.json 就那几个字段，name + transport 类型 + command/url，5 分钟就能配好。

### 误区3：必须自己写 Server 才能用
**实际**：Hugging Face、GitHub、Playwright 都有现成的 MCP Server，你直接配置连接就能用，不用自己写。

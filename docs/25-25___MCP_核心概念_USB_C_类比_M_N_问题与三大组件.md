<title>25 · MCP 核心概念：USB-C 类比、M×N 问题与三大组件</title>

# 25 · MCP 核心概念：USB-C 类比、M×N 问题与三大组件

## 一、一句话定位

MCP 被称为「**AI 应用的 USB-C**」：像 USB-C 用统一物理/逻辑接口接各种外设一样，MCP 用统一协议把 AI 模型接到外部工具和数据。用户得到一致体验，应用方一次接入，工具方一次实现。

## 二、M×N → M+N 问题

| 场景 | 集成数量 | 说明 |
|-|-|-|
| 无 MCP | M × N | 每个 AI 应用接每个工具都要写一套定制对接，M 个应用 × N 个工具 = M×N 套代码，维护爆炸 |
| 有 MCP | M + N | 每个 AI 应用实现一次 MCP Client，每个工具实现一次 MCP Server，总数从 M×N 降到 M+N |

## 三、三大组件

| 组件 | 角色 | 例子 |
|-|-|-|
| **Host** | 用户直接面对的 AI 应用，发起连接、编排流程 | Claude Desktop、Cursor、Hugging Face SDK、LangChain/smolagents 自建应用 |
| **Client** | Host 内部的组件，与某个 Server 保持 1:1 连接，处理协议细节 | Host 里同时连多个 Server 时，每个 Server 对应一个 Client |
| **Server** | 外部程序/服务，通过 MCP 暴露能力（工具、资源、提示词） | 天气服务、知识库、数据库 MCP server |

<callout emoji="💡">
很多文档把 Client 和 Host 混用，技术上要分清：Host 是用户看得见的应用，Client 是 Host 内部连某个 Server 的组件。
</callout>

## 四、四大能力（Capabilities）

| 能力 | 含义 | 例子 |
|-|-|-|
| **Tools** | 可执行函数，LLM 调用后执行动作或返回计算结果 | 天气函数、代码解释器、知识库检索 |
| **Resources** | 只读数据源，提供上下文，不做重计算 | 论文库、应用文档 |
| **Prompts** | 预定义模板/工作流，引导用户和 LLM 交互方式 | 总结提示词、代码风格模板 |
| **Sampling** | Server 反向请求 Host 做 LLM 调用，让 LLM 递归审查自己的输出 | 写作 app 自查后继续润色；code review |

## 五、Code Agent 示例

一个代码 Agent 应用如何用 MCP 四大能力：

- **Tool** = Code Interpreter（执行 LLM 写的代码）
- **Resource** = Documentation（应用文档）
- **Prompt** = Code Style（引导代码风格）
- **Sampling** = Code Review（LLM 审查自己的代码再决定是否改进）

## 六、对本项目的映射

我们项目下一步要做的 mcp_server.py，本质就是写一个 **Server**：把现有 hybrid_search 暴露成 **Tool**，把 docs/ 里的课程笔记暴露成 **Resource**，把"知识问答"的系统提示词包装成 **Prompt**。Host 就是 Claude Code / Cursor。
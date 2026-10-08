# 10 · smolagents 入门（模块概览）

<title>10 · smolagents 入门（模块概览）</title>

![](https://feishu.cn/file/Fe2sb4LB5o6CcSxtbC7chZnAn4d)

# smolagents 入门（模块概览）

**一句话总述：**smolagents 是 Hugging Face 开发的轻量智能体框架，教你构建能搜索数据、执行代码、交互网页的 AI 智能体，并支持组合多个智能体构建更强大的系统。

## 一、smolagents 是什么

- Hugging Face 出品的 **轻量级开源框架**，用于创建能力强的 AI 智能体
- 本模块将系统学习它的核心概念与实战策略
- 可以搜索数据、执行代码、与网页交互
- 可以组合多个智能体，构建更强大的系统

**背景故事：**第一单元的 Alfred 管家回归了！这次他使用 smolagents 框架来组织韦恩庄园的派对——通过他的任务旅程，我们一起探索框架的核心概念。

## 二、为什么值得学这个模块

开源框架很多，理解 smolagents 的组件和能力，能帮你判断：

- 什么时候 smolagents 是合适的选择
- 什么时候其他方案（如 LlamaIndex、LangGraph）更合适

## 三、本模块 7 个部分概览

| 章节 | 核心内容 |
|-|-|
| **1. 为什么用 smolagents** | 分析优势与缺点，帮你基于项目需求做选型决策 |
| **2. CodeAgents** | 主要智能体类型：不生成 JSON 或文本，而是生成 Python 代码执行动作（含实操示例） |
| **3. ToolCallingAgents** | 第二种智能体：依赖 JSON/文本块，由系统解析执行；对比 CodeAgents 差异 |
| **4. Tools 工具** | 用 Tool 类或 @tool 装饰器创建工具、默认工具箱、社区分享与加载 |
| **5. Retrieval Agents 检索智能体** | 访问知识库，用向量存储实现 RAG 模式，结合网页搜索与记忆系统，含兜底机制 |
| **6. Multi-Agent Systems 多智能体** | 编排不同能力的智能体（如网页搜索 + 代码执行），提升效率与可靠性 |
| **7. Vision and Browser agents 视觉与浏览器** | 用视觉语言模型（VLM）处理图像信息，并构建能浏览网页、提取信息的浏览器智能体 |

## 四、两大核心智能体类型

- **CodeAgents（代码智能体）：**生成 Python 代码来执行动作——主要类型
- **ToolCallingAgents（工具调用智能体）：**生成 JSON/文本，由系统解析执行

## 五、进阶能力亮点

- **检索增强（RAG）：**向量存储 + 知识库，实现高效检索与信息综合
- **多智能体编排：**组合不同能力的智能体解决复杂问题
- **多模态：**VLM 支持图像理解，浏览器智能体可抓取网页信息

## 六、参考资源

- [smolagents 官方文档](https://huggingface.co/docs/smolagents)
- [Building Effective Agents（Anthropic）](https://www.anthropic.com/research/building-effective-agents)
- [Agent Guidelines 最佳实践](https://huggingface.co/docs/smolagents/tutorials/building_good_agents)
- [RAG Best Practices](https://www.pinecone.io/learn/retrieval-augmented-generation/)

## 标签

#smolagents #CodeAgent #ToolCallingAgent #RAG

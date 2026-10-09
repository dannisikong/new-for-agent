<title>12 · LangGraph（框架导论）</title>

![](https://feishu.cn/file/FAJ7bHCI4oQuW4xCcw6cJvGhnjh)

# LangGraph（框架导论）

**一句话总述：**LangGraph 是 LangChain 出品的智能体框架，用**图结构**编排复杂 LLM 工作流，提供对 Agent 流程的精细控制，目标是构建**生产级**应用。

## 一、LangGraph 是什么

LangGraph 是一个用于构建应用的框架，帮助开发者**结构化并编排复杂的 LLM 工作流**。

- **生产级（production-ready）：**适合真实上线运行的应用
- **控制力：**提供工具，让你对 Agent 的流程拥有明确控制
- **核心思想：**把工作流建模成一张"图"——节点（步骤）和边（流转）

## 二、模块内容预览（5 部分）

1. **什么是 LangGraph，什么时候用它**——框架定位与选型判断
2. **LangGraph 的构建模块（Building Blocks）**——图、节点、边、状态等核心概念
3. **Alfred，邮件分拣管家（first_graph）**——上手写第一个图
4. **Alfred，文档分析智能体（document_analysis_agent）**——构建更完整的分析型 Agent
5. **Quiz 测验**——检验学习成果

> ⚠️ 注意：本节示例需要强大的 LLM/VLM 模型。课程作者使用 GPT-4o API 运行，因为它与 LangGraph 的兼容性最好。

## 三、学完你能获得什么

- 构建**稳健、有条理、生产级**的应用
- 掌握用图结构组织复杂工作流的方法
- 为深入学习 LangChain Academy 的《Introduction to LangGraph》课程打基础

## 四、与其他框架的定位对比

| 框架 | 特点 | 适合场景 |
|-|-|-|
| **smolagents** | 轻量、代码优先 | 快速实验、简单逻辑 |
| **LlamaIndex** | 上下文增强、端到端 | 生产级 RAG / 数据应用 |
| **LangGraph** | 图结构、有状态编排、精细控制 | 复杂工作流、生产级应用 |

## 五、新手常见误区

- **误区1：以为 LangGraph 和 smolagents 二选一。**它们解决不同问题：smolagents 轻量快速，LangGraph 精细编排。
- **误区2：忽略"图"的思维。**LangGraph 的核心是把流程画成图：节点做什么、边怎么走、状态存什么。
- **误区3：用便宜模型跑复杂示例。**LangGraph 示例通常需要强模型（如 GPT-4o）才能稳定工作。

## 六、本节小结

LangGraph = 图结构 + 精细控制 + 生产级。理解它"把工作流建模成图"的核心思想，是掌握这个框架的第一步。接下来学习它的构建模块。

## 标签

#LangGraph #LangChain #工作流编排 #生产级
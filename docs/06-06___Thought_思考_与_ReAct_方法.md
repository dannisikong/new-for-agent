# 06 · Thought（思考）与 ReAct 方法

<title>06 · Thought（思考）与 ReAct 方法</title>

![](https://feishu.cn/file/O9heboJ9johaC7xh77TcCDXPnIa)

# Thought（思考）与 ReAct 方法

**一句话总述：**思考（Thought）是 Agent 的内部推理与规划过程；ReAct 则把"思考"与"行动"交替结合，让 Agent 逐步解决问题。CoT 思维链是纯推理的提示技巧，ReAct 是"推理+行动"的进阶方法。

## 一、什么是 Thought（思考）

Thought 代表 Agent **解决任务时的内部推理与规划过程**。它利用 LLM 分析 prompt 中信息的能力——本质上就是模型解决问题时的一段"内心独白"。

思考的作用：

- **评估当前观察结果**，决定下一步应该做什么
- **把复杂问题拆解成更小的、可管理的步骤**
- **反思过去的经验**，根据新信息持续调整计划

## 二、常见的思考类型

| 思考类型 | 例子 |
|-|-|
| **规划 Planning** | "我需要把任务拆成三步：1) 收集数据，2) 分析趋势，3) 生成报告" |
| **分析 Analysis** | "根据错误信息，问题似乎出在数据库连接参数上" |
| **决策 Decision Making** | "考虑到用户的预算，我应该推荐中档选项" |
| **问题解决 Problem Solving** | "要优化这段代码，我应该先剖析它找出瓶颈" |
| **记忆整合 Memory Integration** | "用户之前提到喜欢 Python，所以我会用 Python 举例子" |
| **自我反思 Self-Reflection** | "我上次的方法效果不好，应该换一种策略" |
| **目标设定 Goal Setting** | "要完成这个任务，我需要先确定验收标准" |
| **优先级排序 Prioritization** | "安全漏洞应该先于新功能处理" |

> 注意：对于专门为函数调用微调的 LLM，思考过程是可选的——它们可以直接输出工具调用。这一点在 Actions 章节会详述。

## 三、Chain-of-Thought（CoT）思维链

**CoT（思维链）**是一种提示技术：引导模型**在给出最终答案前，一步一步把推理过程想清楚**。它通常以 "Let's think step by step" 开头。

特点：

- 帮助模型在**逻辑和数学任务**上内部推理
- **不调用外部工具**，纯靠内部思考

**例子（CoT）：**

```
Question: What is 15% of 200?
Thought: Let's think step by step. 10% of 200 is 20, and 5% of 200 is 10, so 15% is 30.
Answer: 30

```

## 四、ReAct：推理 + 行动

**ReAct**（Reasoning + Acting）把"推理（Think）"和"行动（Act）"结合起来。它是一种提示技术：**鼓励模型逐步思考，并在推理步骤之间穿插行动（例如调用工具）**。

通过交替执行，Agent 能解决复杂多步任务：

- **Thought（思考）：**内部推理
- **Action（行动）：**使用工具
- **Observation（观察）：**接收工具输出

**例子（ReAct）：**

```
Thought: I need to find the latest weather in Paris.
Action: Search["weather in Paris"]
Observation: It's 18°C and cloudy.
Thought: Now that I know the weather...
Action: Finish["It's 18°C and cloudy in Paris."]

```

注意区别：ReAct 会在思考之间真正"动手"（搜索、查证），而不是一直空想。

## 五、CoT vs ReAct 对比

| 对比项 | CoT 思维链 | ReAct |
|-|-|-|
| **逐步逻辑** | ✅ 有 | ✅ 有 |
| **外部工具** | ❌ 不用 | ✅ 用（行动+观察） |
| **最适合场景** | 逻辑推理、数学、内部任务 | 信息检索、动态多步任务 |

**一句话选型：**纯动脑的任务用 CoT；需要动手查证、多步协作的任务用 ReAct。

## 六、训练级别的"先思考"技术

近年像 **DeepSeek R1**、**OpenAI o1** 等模型，通过微调学会了"先思考再回答"。它们使用 **<think> 和 </think>** 这样的结构化 token，把推理阶段和最终答案显式分开。

**关键区别：**CoT 和 ReAct 是**提示策略**（不改变模型）；而 R1/o1 是**训练级技术**——模型通过训练样本直接学会了思考。

## 七、新手常见误区

- **误区1：混淆 CoT 和 ReAct。**两者都有逐步推理，但 ReAct 会调用工具，CoT 不会。
- **误区2：以为"思考"是模型天生自带。**ReAct/CoT 是提示技巧；R1/o1 的思考则是训练出来的。
- **误区3：所有任务都套 ReAct。**纯逻辑任务用 CoT 更省；需要实时信息才用 ReAct。

## 八、本节小结

思考让 Agent 会"想"，工具让 Agent 会"做"。CoT 教会模型逐步想，ReAct 让它在想和做之间交替——这是构建复杂 Agent 的基石。

## 标签

#Thought #ReAct #CoT #推理

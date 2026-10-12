"""
eval_dataset.py —— 评测集（30 条）
=================================
基于 AI Agent 课程知识库 27 篇文档抽取。
每条包含：问题、标准答案要点（关键词）、应命中的文档、问题类型。

类型说明：
- fact: 事实性问题（考概念定义）
- compare: 对比性问题（A 和 B 的区别）
- howto: 操作性问题（怎么做某事）
- concept: 概念理解题（为什么/解决什么问题）
"""

EVAL_DATASET = [
    # ---- 基础概念（01-09）----
    {
        "id": 1,
        "question": "什么是 Agent（智能体）？它和普通大语言模型调用有什么区别？",
        "expected_keywords": ["LLM 作为引擎", "自主决策", "循环", "工具调用", "目标驱动"],
        "expected_doc": "01-01___Agent_智能体.md",
        "type": "fact",
    },
    {
        "id": 2,
        "question": "Thought-Action-Observation 循环是什么？请简述每个环节的作用。",
        "expected_keywords": ["思考", "行动", "观察", "循环", "ReAct"],
        "expected_doc": "05-05___Thought_Action_Observation_思考_行动_观察循环.md",
        "type": "fact",
    },
    {
        "id": 3,
        "question": "ReAct 方法是什么？它和单纯的 Chain-of-Thought 有什么不同？",
        "expected_keywords": ["推理", "行动", "外部世界", "工具", "观察结果"],
        "expected_doc": "06-06___Thought_思考_与_ReAct_方法.md",
        "type": "compare",
    },
    {
        "id": 4,
        "question": "LLM 为什么需要 Tools（工具）？没有工具它有什么局限？",
        "expected_keywords": ["实时信息", "计算", "外部系统", "知识截止", "可操作性"],
        "expected_doc": "04-04___Tools_工具.md",
        "type": "concept",
    },

    # ---- 框架选型（09-14）----
    {
        "id": 5,
        "question": "LangGraph 是什么？它和 LangChain 是什么关系？",
        "expected_keywords": ["图", "状态", "循环", "编排", "运行时"],
        "expected_doc": "13-13___LangGraph_是什么_控制流与选型.md",
        "type": "compare",
    },
    {
        "id": 6,
        "question": "LangGraph 的核心构建模块有哪些？",
        "expected_keywords": ["State", "Node", "Edge", "Reducer", "Graph"],
        "expected_doc": "14-14___LangGraph_构建模块.md",
        "type": "fact",
    },
    {
        "id": 7,
        "question": "什么时候该选 LangGraph，什么时候用普通 LangChain Chain 就够了？",
        "expected_keywords": ["循环", "条件分支", "多步", "简单调用", "状态管理"],
        "expected_doc": "13-13___LangGraph_是什么_控制流与选型.md",
        "type": "concept",
    },
    {
        "id": 8,
        "question": "smolagents 是什么？它和 LangGraph 这类重型框架有什么定位差异？",
        "expected_keywords": ["轻量", "代码智能体", "Hugging Face", "简洁", "快速原型"],
        "expected_doc": "10-10___smolagents_入门_模块概览.md",
        "type": "compare",
    },
    {
        "id": 9,
        "question": "Code Agent 和普通 Tool Calling Agent 有什么区别？",
        "expected_keywords": ["写代码", "执行", "Python", "灵活性", "工具调用"],
        "expected_doc": "11-11___CodeAgents_代码智能体.md",
        "type": "compare",
    },

    # ---- RAG 闭环（17-19）----
    {
        "id": 10,
        "question": "什么是 Agentic RAG？它和普通 RAG 的区别是什么？",
        "expected_keywords": ["检索", "评分", "重写", "决策", "多步"],
        "expected_doc": "18-18___Agentic_RAG_智能体.md",
        "type": "compare",
    },
    {
        "id": 11,
        "question": "Agentic RAG 闭环里为什么需要一个 grade（评分）节点？",
        "expected_keywords": ["相关性", "不相关", "重写", "再检索", "避免幻觉"],
        "expected_doc": "18-18___Agentic_RAG_智能体.md",
        "type": "concept",
    },
    {
        "id": 12,
        "question": "RAG 检索回来的文档不相关时，通常怎么处理？",
        "expected_keywords": ["重写问题", "再检索", "降级网络搜索", "多轮", "上限"],
        "expected_doc": "17-17___Agentic_RAG_用例导论.md",
        "type": "howto",
    },

    # ---- MCP（23-27）----
    {
        "id": 13,
        "question": "MCP（Model Context Protocol）是什么？它解决什么问题？",
        "expected_keywords": ["USB-C", "标准化", "M×N", "工具接入", "互操作"],
        "expected_doc": "25-25___MCP_核心概念_USB_C_类比_M_N_问题与三大组件.md",
        "type": "concept",
    },
    {
        "id": 14,
        "question": "MCP 里的 Host、Client、Server 分别是什么？它们的关系？",
        "expected_keywords": ["用户应用", "1:1 连接", "外部服务", "工具暴露", "协议"],
        "expected_doc": "26-26___MCP_架构组件与通信流程.md",
        "type": "fact",
    },
    {
        "id": 15,
        "question": "MCP 支持哪两种主要的传输机制（transport）？分别用在什么场景？",
        "expected_keywords": ["stdio", "本地", "HTTP", "SSE", "远程"],
        "expected_doc": "27-27___MCP_通信协议_JSON_RPC_传输机制与生命周期.md",
        "type": "fact",
    },
    {
        "id": 16,
        "question": "为什么说 M×N 问题用 MCP 后变成 M+N？",
        "expected_keywords": ["M 个应用", "N 个工具", "标准化接口", "一次实现", "复用"],
        "expected_doc": "25-25___MCP_核心概念_USB_C_类比_M_N_问题与三大组件.md",
        "type": "concept",
    },
    {
        "id": 17,
        "question": "MCP 用什么作为消息格式？它的三种消息类型是什么？",
        "expected_keywords": ["JSON-RPC", "Request", "Response", "Notification", "id"],
        "expected_doc": "27-27___MCP_通信协议_JSON_RPC_传输机制与生命周期.md",
        "type": "fact",
    },

    # ---- 工程实践（15,16,20,21,22）----
    {
        "id": 18,
        "question": "LangGraph 里人在回路（human-in-the-loop）是怎么实现的？",
        "expected_keywords": ["interrupt", "暂停", "恢复", "checkpointer", "审批"],
        "expected_doc": "22-22___LangGraph_实战_邮件分拣_人工审阅_舞会智能体.md",
        "type": "howto",
    },
    {
        "id": 19,
        "question": "LangGraph 的 Checkpointer 是做什么的？它解决什么问题？",
        "expected_keywords": ["状态持久化", "断点恢复", "多轮对话", "thread_id", "持久化"],
        "expected_doc": "12-12___LangGraph_框架导论.md",
        "type": "concept",
    },
    {
        "id": 20,
        "question": "LangGraph 里 Reducer（归约器）是干什么用的？",
        "expected_keywords": ["状态更新", "合并", "add_messages", "自定义", "冲突"],
        "expected_doc": "14-14___LangGraph_构建模块.md",
        "type": "fact",
    },
    {
        "id": 21,
        "question": "给 Agent 加工具时，为什么工具描述（description）很重要？",
        "expected_keywords": ["LLM 选择", "参数", "准确率", "路由", "语义"],
        "expected_doc": "20-20___工具构建与整合.md",
        "type": "concept",
    },
    {
        "id": 22,
        "question": "LangGraph 里条件边（conditional edge）的作用是什么？",
        "expected_keywords": ["路由", "根据状态", "分支", "动态", "函数"],
        "expected_doc": "14-14___LangGraph_构建模块.md",
        "type": "fact",
    },

    # ---- 综合/跨文档（需要理解）----
    {
        "id": 23,
        "question": "一个生产级 Agent 除了能跑通 ReAct 循环，还需要哪些工程能力？",
        "expected_keywords": ["错误重试", "记忆", "Guardrails", "评测", "可观测"],
        "expected_doc": "22-22___LangGraph_实战_邮件分拣_人工审阅_舞会智能体.md",
        "type": "concept",
    },
    {
        "id": 24,
        "question": "Agent 调用工具失败时，工业界通常怎么处理？",
        "expected_keywords": ["重试", "退避", "降级", "错误分类", "幂等"],
        "expected_doc": "20-20___工具构建与整合.md",
        "type": "howto",
    },
    {
        "id": 25,
        "question": "LLM 产生幻觉时，RAG 系统通常怎么缓解？",
        "expected_keywords": ["检索增强", "基于上下文", "评分", "不编造", "引用"],
        "expected_doc": "18-18___Agentic_RAG_智能体.md",
        "type": "howto",
    },
    {
        "id": 26,
        "question": "Messages 里的特殊标记（如 system/user/assistant role）有什么作用？",
        "expected_keywords": ["角色", "区分", "上下文", "指令", "对话历史"],
        "expected_doc": "03-03___Messages_and_Special_Tokens_消息与特殊标记.md",
        "type": "fact",
    },
    {
        "id": 27,
        "question": "Observation（观察）在 ReAct 循环里起什么作用？",
        "expected_keywords": ["工具返回", "反馈", "下一步", "更新状态", "外部信息"],
        "expected_doc": "08-08___Observation_观察.md",
        "type": "fact",
    },
    {
        "id": 28,
        "question": "为什么说 Code Agent 比纯 Tool Calling 更灵活？",
        "expected_keywords": ["写代码", "组合", "多步", "图灵完备", "复杂任务"],
        "expected_doc": "11-11___CodeAgents_代码智能体.md",
        "type": "compare",
    },
    {
        "id": 29,
        "question": "LangGraph 的 State 在图运行中是怎么流转的？",
        "expected_keywords": ["节点", "返回更新", "Reducer", "合并", "下一个节点"],
        "expected_doc": "14-14___LangGraph_构建模块.md",
        "type": "fact",
    },
    {
        "id": 30,
        "question": "MCP 生态里 Server 暴露的三类能力（Tools / Resources / Prompts）有什么区别？",
        "expected_keywords": ["可执行函数", "只读数据", "模板", "采样", "使用场景"],
        "expected_doc": "25-25___MCP_核心概念_USB_C_类比_M_N_问题与三大组件.md",
        "type": "compare",
    },
]


if __name__ == "__main__":
    from collections import Counter
    types = Counter(q["type"] for q in EVAL_DATASET)
    print(f"评测集总数：{len(EVAL_DATASET)}")
    print(f"类型分布：{dict(types)}")

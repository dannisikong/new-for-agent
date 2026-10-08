"""
app.py —— Alfred 舞会智能体（LangGraph 版）主程序
=================================================
对应课程第 21 章：把宾客检索 / 网络搜索 / 天气 / HF 统计四个工具
整合进 LangGraph 的 ReAct 循环：
    START → assistant → (tools_condition) → tools → assistant → ... → END

模型：默认使用内置 MockAlfredLLM（可产出标准 tool_calls，无需 API Key）。
接入真实 LLM（配置 Key 后）：
    from langchain_openai import ChatOpenAI
    model = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(TOOLS)
    然后删除 assistant 节点里的 mock 分支即可，图结构完全不变。
"""

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, AnyMessage
from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from tools import TOOLS

# ============================================================
# 1. 模拟 LLM：规则型决策 + 标准 tool_calls 输出
#    这是"Agent 的大脑"：决定何时调用哪个工具、何时收尾回答
# ============================================================

GUEST_NAMES = ["ada", "lovelace", "tesla", "turing", "hopper"]
CITY_WORDS = ["paris", "london", "new york", "tokyo", "beijing", "上海", "北京", "巴黎"]
AUTHOR_WORDS = ["qwen", "google", "facebook", "meta", "openai", "mistral"]
# 知识库触发词：课程术语 / 中文知识类提问
KNOWLEDGE_WORDS = [
    "知识库", "课程", "学习笔记", "什么是", "是什么", "怎么理解", "讲解", "解释",
    "react", "langgraph", "llm", "rag", "smolagents", "llamaindex", "agent", "agentic",
    "智能体", "大语言模型", "工具", "embedding", "提示词", "token", "向量", "检索",
    "状态", "节点", "边", "循环", "观察", "思考", "行动", "框架",
]


class MockAlfredLLM(Runnable):
    """模拟 LLM：根据用户问题规划工具调用序列，工具结果返回后汇总作答
    继承 Runnable 以兼容 create_react_agent 等需要标准接口的场景"""

    def __init__(self):
        self.tools = []

    def bind_tools(self, tools):
        self.tools = list(tools)
        return self

    # ---- 工具调用规划 ----
    def _plan(self, query: str):
        """返回按优先级排序的、该问题需要的工具名列表"""
        q = query.lower()
        plan = []
        if any(n in q for n in GUEST_NAMES):       # 宾客档案（按姓名触发）
            plan.append("guest_info_retriever")
        if any(k in q for k in ["weather", "天气", "firework", "烟花", "rain", "suitable"]):
            plan.append("weather_info")            # 天气 / 烟花排期
        if any(k in q for k in ["model", "模型", "download", "下载", "hub", "popular"]):
            plan.append("hub_stats")               # HF 模型统计
        if any(k in q for k in ["search", "搜索", "news", "新闻", "latest", "最新",
                                "advancement", "进展", "recent", "information about"]):
            plan.append("web_search")              # 网络搜索
        # 知识库查询：未命中其他工具时，知识类问题走 knowledge_search
        if not any(n in plan for n in ["guest_info_retriever", "weather_info", "hub_stats"]):
            if any(k in q for k in KNOWLEDGE_WORDS):
                plan.append("knowledge_search")
        return plan

    # ---- 工具参数提取 ----
    def _args_for(self, tool_name: str, query: str):
        q = query.lower()
        if tool_name == "weather_info":
            city = next((c for c in CITY_WORDS if c in q), "Paris")
            return {"location": city.title()}
        if tool_name == "hub_stats":
            author = next((a for a in AUTHOR_WORDS if a in q), None)
            return {"author": author or "Qwen"}
        # guest_info_retriever / web_search：把完整问题作为查询
        return {"query": query}

    # ---- 汇总最终答案 ----
    def _compose_answer(self, tool_msgs, query: str):
        parts = []
        for m in tool_msgs:
            if m.name == "guest_info_retriever":
                parts.append(f"根据宾客档案：\n{m.content}")
            elif m.name == "web_search":
                parts.append(f"基于网络搜索的最新信息：\n{m.content}")
            elif m.name == "knowledge_search":
                parts.append(f"根据知识库（AI Agent 课程笔记）：\n{m.content}")
            else:  # weather_info / hub_stats 直接引用
                parts.append(m.content)
        return "🎩 Alfred:\n\n" + "\n\n".join(parts)

    # ---- 核心入口：接收消息列表，返回 AIMessage ----
    # config/**kwargs 用于兼容 Runnable 标准接口（create_react_agent 等）
    def invoke(self, messages, config=None, **kwargs):
        user_msg = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        query = user_msg.content if user_msg else ""
        called = {m.name for m in messages if isinstance(m, ToolMessage)}

        # 还有未调用的工具 → 输出一个 tool_call，交回给图去执行
        for name in self._plan(query):
            if name not in called:
                return AIMessage(content="", tool_calls=[{
                    "name": name,
                    "args": self._args_for(name, query),
                    "id": f"call_{len(called)}",
                    "type": "tool_call",
                }])

        # 全部工具已调用（或无需工具）→ 生成最终回答
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        if tool_msgs:
            return AIMessage(content=self._compose_answer(tool_msgs, query))
        return AIMessage(content="🎩 Alfred:\n\n我可以帮您筹备舞会——查宾客档案、看天气、聊 AI 模型或搜最新进展，请问需要哪一项？")


# ============================================================
# 2. 图结构与节点
# ============================================================

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # add_messages：追加而非覆盖


model = MockAlfredLLM().bind_tools(TOOLS)


def assistant(state: AgentState):
    """Agent 大脑节点：生成回复或工具调用"""
    response = model.invoke(state["messages"])
    return {"messages": [response]}


def build_react_graph():
    builder = StateGraph(AgentState)

    # 节点：做事的函数
    builder.add_node("assistant", assistant)   # 大脑：决定下一步
    builder.add_node("tools", ToolNode(TOOLS)) # 手：执行工具调用

    # 边：控制流
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges(
        "assistant",
        tools_condition,          # 有 tool_calls → tools；否则 → END
    )
    builder.add_edge("tools", "assistant")     # 关键回边：构成 ReAct 循环

    return builder.compile()


# ============================================================
# 3. 主程序：四场景实测
# ============================================================

if __name__ == "__main__":
    alfred = build_react_graph()

    queries = [
        # 例1：宾客检索（单工具）
        "Tell me about Lady Ada Lovelace",
        # 例2：天气 + 烟花（单工具）
        "What's the weather like in Paris tonight? Will it be suitable for our fireworks display?",
        # 例3：HF 模型统计（单工具）
        "One of our guests is from Qwen. What can you tell me about their most popular model?",
        # 例4：多工具组合（宾客 + 搜索）★
        "I need to speak with Dr. Nikola Tesla about recent advancements in wireless energy. Can you help me prepare for this conversation?",
    ]

    for i, q in enumerate(queries, 1):
        print(f"\n{'#'*62}\n# 示例 {i}：{q}\n{'#'*62}")
        result = alfred.invoke({"messages": [HumanMessage(content=q)]})

        # 打印每一步（ReAct 轨迹）
        for m in result["messages"]:
            if isinstance(m, AIMessage) and m.tool_calls:
                for tc in m.tool_calls:
                    print(f"  ✦ 思考→行动: 调用工具 {tc['name']}({tc['args']})")
            elif isinstance(m, ToolMessage):
                print(f"  ◉ 观察: {m.name} 返回: {m.content[:80]}{'...' if len(m.content) > 80 else ''}")
        print(f"\n最终回答:\n{result['messages'][-1].content}")

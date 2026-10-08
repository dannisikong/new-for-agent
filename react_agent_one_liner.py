"""
react_agent_one_liner.py —— create_react_agent 一行版对比
=========================================================
对比手写 StateGraph：langgraph.prebuilt 的 create_react_agent
几行代码就搭出完全相同的 ReAct 循环（assistant ↔ tools），
适合快速原型；需要精细控制（如人工介入、自定义边）时再手写图。
"""

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from tools import TOOLS
from app import MockAlfredLLM

# ---- 一行版 ReAct Agent（对比 app.py 里手写的 ~20 行图） ----
model = MockAlfredLLM()  # 无 API Key 也可跑；真实环境换成 ChatOpenAI(...)
alfred = create_react_agent(model, TOOLS)

if __name__ == "__main__":
    queries = [
        "Tell me about Dr. Nikola Tesla",
        "What's the weather like in Paris tonight? Suitable for fireworks?",
        "One of our guests is from Google. What's their most popular model?",
    ]

    for q in queries:
        print(f"\n{'#'*58}\n# {q}\n{'#'*58}")
        result = alfred.invoke({"messages": [HumanMessage(content=q)]})

        for m in result["messages"]:
            if getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    print(f"  ✦ 行动: {tc['name']}({tc['args']})")
            elif getattr(m, "name", None) and m.type == "tool":
                print(f"  ◉ 观察: {m.name} 返回: {m.content[:60]}...")
        print(f"\n最终回答:\n{result['messages'][-1].content}")

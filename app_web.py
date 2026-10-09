"""
app_web.py —— AI Agent 知识问答助手 · Web 界面（Streamlit）
========================================================
侧边栏可自定义：
  - 回答模式：标准智能体（ReAct）/ 知识库智能问答（Agentic RAG）
  - 模型提供商（OpenAI 兼容 / Hugging Face / 演示模式）
  - API Token（仅本次会话内存中使用，不落盘、不写入仓库）
  - 模型名称与 Base URL

运行：streamlit run app_web.py
"""

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from agent_core import make_llm, build_react_graph
from agentic_rag import rag_query

st.set_page_config(page_title="智能知识助手", page_icon="📚", layout="wide")

SYSTEM_PROMPT = (
    "You are a helpful, general-purpose knowledge assistant. "
    "You have a knowledge_search tool covering a course-notes knowledge base on "
    "AI Agent concepts, LangGraph, LLMs, RAG, tools and frameworks; use it when the question matches that domain. "
    "You also have web_search for external or up-to-date information. "
    "For other questions, answer from your own knowledge. "
    "Answer in the user's language. Be concise and accurate; "
    "if you are unsure, say so rather than making things up."
)

# ---------------- 侧边栏配置 ----------------
with st.sidebar:
    st.header("⚙️ 智能体配置")
    answer_mode = st.selectbox(
        "回答模式",
        ["🌐 标准智能体（ReAct）", "📚 知识库智能问答（Agentic RAG）"],
        index=0,
        help="知识库智能问答走「检索→评分→不相关重写→再检索」闭环，适合问 AI Agent 课程知识点",
    )
    provider = st.selectbox(
        "模型提供商",
        ["演示模式（无需 Token）", "OpenAI 兼容", "Hugging Face"],
        index=0,
        help="演示模式使用内置规则 LLM，无需 Token；选真实提供商后请填写下方 Token",
    )
    api_key = st.text_input("API Token", type="password",
                            placeholder="sk-... 或 hf_...（仅会话内使用）")
    model_name = st.text_input(
        "模型名称",
        value="gpt-4o" if provider == "OpenAI 兼容"
        else ("Qwen/Qwen2.5-Coder-32B-Instruct" if provider == "Hugging Face" else "gpt-4o"),
    )
    base_url = st.text_input(
        "Base URL（OpenAI 兼容）",
        value="https://api.openai.com/v1",
        help="OpenAI: api.openai.com/v1 · DeepSeek: api.deepseek.com/v1 · 通义: dashscope.aliyuncs.com/compatible-mode/v1",
        disabled=provider != "OpenAI 兼容",
    )
    st.divider()
    st.caption("提示：Token 只在本次会话内存中使用，不会写入代码或仓库。")
    if st.button("🗑️ 清空对话"):
        st.session_state.messages = []

# ---------------- 主区：聊天界面 ----------------
st.title("📚 智能知识助手")
st.caption("LangGraph 实战应用：ReAct 智能体 / Agentic RAG 知识库问答（检索→评分→重写闭环），内置 AI Agent 课程知识库，可自由切换模型")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("输入你的问题… 例如：什么是 RAG？/ LangGraph 和 LangChain 是什么关系？")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        # 1. 按侧边栏配置构造模型（演示模式无需 Token）
        if provider != "演示模式（无需 Token）" and not api_key:
            raise ValueError("请先在左侧填写 API Token（或改用演示模式）")

        llm = make_llm(provider, api_key, model_name, base_url)

        # 2. 按回答模式运行
        with st.spinner("正在检索知识库并组织回答…"):
            if answer_mode == "📚 知识库智能问答（Agentic RAG）":
                # 带缓存：相同问题直接复用上次结果，不重新检索（回答也保持一致）
                rag_model = None if provider == "演示模式（无需 Token）" else llm
                result = rag_query(prompt, model=rag_model)
                answer = result["answer"]
                trace = result.get("trace", [])
                if result.get("cached"):
                    st.caption("⚡ 命中查询缓存：相同问题直接复用上次答案，未重新检索")
            else:
                graph = build_react_graph(llm)
                msgs = [SystemMessage(content=SYSTEM_PROMPT)]
                for m in st.session_state.messages:
                    if m["role"] == "user":
                        msgs.append(HumanMessage(content=m["content"]))
                    else:
                        msgs.append(AIMessage(content=m["content"]))
                result = graph.invoke({"messages": msgs})
                answer = result["messages"][-1].content
                # 标准模式的工具调用轨迹
                trace = []
                for m in result["messages"]:
                    if getattr(m, "tool_calls", None):
                        for tc in m.tool_calls:
                            trace.append(f"✏️ 思考→行动：调用 {tc['name']}({tc['args']})")
                    elif getattr(m, "type", "") == "tool":
                        trace.append(f"📊 观察：{m.name} 返回 {m.content[:100]}{'…' if len(m.content) > 100 else ''}")

        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)

        # 3. 展开显示轨迹（标准模式 TAO / RAG 模式 检索→评分→重写）
        if trace:
            label = "查看 Agentic RAG 轨迹（检索→评分→重写→回答）" if answer_mode.startswith("📚") \
                else "查看工具调用轨迹（Thought-Action-Observation）"
            with st.expander(label):
                for line in trace:
                    st.code(line)

    except Exception as e:
        st.error(f"调用失败：{e}")
        if "api_key" in str(e).lower() or "401" in str(e) or "auth" in str(e).lower():
            st.info("请检查 Token 是否正确、模型名称是否可用、Base URL 是否匹配所选提供商。")

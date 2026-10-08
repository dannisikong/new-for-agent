"""
app_web.py —— Alfred 舞会智能体 · Web 界面（Streamlit）
========================================================
侧边栏可自定义：
  - 模型提供商（OpenAI 兼容 / Hugging Face / 演示模式）
  - API Token（仅本次会话内存中使用，不落盘、不写入仓库）
  - 模型名称与 Base URL

运行：streamlit run app_web.py
"""

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from agent_core import make_llm, build_react_graph

st.set_page_config(page_title="Alfred · LangGraph Agent", page_icon="🎩", layout="wide")

SYSTEM_PROMPT = (
    "You are Alfred, a helpful agent. You have these tools: "
    "knowledge_search (search the AI Agent course knowledge base, best for questions about "
    "AI Agent concepts, LangGraph, LLMs, RAG, tools and frameworks), "
    "guest_info_retriever (gala guest profiles), "
    "web_search, weather_info and hub_stats (Hugging Face model stats). "
    "When the user asks a conceptual or knowledge question, prefer knowledge_search first. "
    "Answer in the user's language. Be polite, concise and helpful."
)

# ---------------- 侧边栏配置 ----------------
with st.sidebar:
    st.header("⚙️ 智能体配置")
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
st.title("🎩 Alfred — 舞会智能体")
st.caption("LangGraph ReAct 智能体：知识库检索 / 宾客检索 / 网络搜索 / 天气 / HF 模型统计")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("问 Alfred 一个问题… 例如：Tell me about Dr. Nikola Tesla")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        # 1. 按侧边栏配置构造模型（演示模式无需 Token）
        if provider != "演示模式（无需 Token）" and not api_key:
            raise ValueError("请先在左侧填写 API Token（或改用演示模式）")

        llm = make_llm(provider, api_key, model_name, base_url)
        graph = build_react_graph(llm)

        # 2. 把会话历史组装成消息列表交给图
        msgs = [SystemMessage(content=SYSTEM_PROMPT)]
        for m in st.session_state.messages:
            if m["role"] == "user":
                msgs.append(HumanMessage(content=m["content"]))
            else:
                msgs.append(AIMessage(content=m["content"]))

        # 3. 运行 ReAct 循环
        with st.spinner("Alfred 正在思考并调用工具…"):
            result = graph.invoke({"messages": msgs})

        answer = result["messages"][-1].content
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)

        # 4. 展开显示工具调用轨迹
        trace = []
        for m in result["messages"]:
            if getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    trace.append(f"✏️ 思考→行动：调用 {tc['name']}({tc['args']})")
            elif getattr(m, "type", "") == "tool":
                trace.append(f"📊 观察：{m.name} 返回 {m.content[:100]}{'…' if len(m.content) > 100 else ''}")
        if trace:
            with st.expander("查看工具调用轨迹（Thought-Action-Observation）"):
                for line in trace:
                    st.code(line)

    except Exception as e:
        st.error(f"调用失败：{e}")
        if "api_key" in str(e).lower() or "401" in str(e) or "auth" in str(e).lower():
            st.info("请检查 Token 是否正确、模型名称是否可用、Base URL 是否匹配所选提供商。")

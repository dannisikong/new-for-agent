<title>15 · 第一个LangGraph应用（Alfred邮件分拣）</title>

![](https://feishu.cn/file/Rp5mbfUOjouyGYx0FSOcj3Qunxd)

# 第一个LangGraph应用（Alfred邮件分拣）

**一句话总述：**本章用 LangGraph 构建 Alfred 邮件处理系统：读取邮件 → LLM 分类（垃圾/正常）→ 垃圾直接丢弃、正常邮件起草回复并通知 Mr. Hugg。这是把四大构建模块落地的第一个完整实战。

> 注意：本例没有调用工具，严格说还不算 Agent，重点是学习 LangGraph 框架本身。

## 一、工作流总览

邮件分拣流程（有向图）：

**START → read_email → classify_email → 条件路由 → [垃圾] handle_spam → END | [正常] draft_response → notify_mr_hugg → END**

Alfred 需要做 4 件事：读取邮件、分类垃圾/正常、为正常邮件起草初步回复、正常时通知 Mr. Hugg（仅打印）。

## 二、环境搭建

```python
%pip install langgraph langchain_openai

```

```python
import os
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

```

## 三、Step 1：定义 State（EmailState）

```python
class EmailState(TypedDict):
    email: Dict[str, Any]          # 邮件内容（主题、发件人、正文等）
    email_category: Optional[str]  # 邮件类别（询问、投诉等）
    spam_reason: Optional[str]     # 标记为垃圾的原因
    is_spam: Optional[bool]        # 是否垃圾
    email_draft: Optional[str]     # 草拟的回复
    messages: List[Dict[str, Any]] # 与 LLM 的对话记录（分析用）

```

**设计提示：**State 要**足够全面**以跟踪所有重要信息，但**避免塞入无关细节**。

## 四、Step 2：定义 Nodes（5 个节点）

初始化 LLM：`model = ChatOpenAI(temperature=0)`（temperature=0 让输出更确定）。

### 1. read_email —— 读取记录

```python
def read_email(state: EmailState):
    """Alfred reads and logs the incoming email"""
    email = state["email"]
    print(f"Alfred is processing an email from {email['sender']} with subject: {email['subject']}")
    return {}  # 无需状态变更

```

### 2. classify_email —— LLM 分类（核心节点）

```python
def classify_email(state: EmailState):
    """Alfred uses an LLM to determine if the email is spam or legitimate"""
    email = state["email"]
    prompt = f"""
    As Alfred the butler, analyze this email and determine if it is spam or legitimate.
    Email:
    From: {email['sender']}
    Subject: {email['subject']}
    Body: {email['body']}
    First, determine if this email is spam. If it is spam, explain why.
    If it is legitimate, categorize it (inquiry, complaint, thank you, etc.).
    """
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    # 简单解析响应（真实应用需要更健壮的解析）
    response_text = response.content.lower()
    is_spam = "spam" in response_text and "not spam" not in response_text

    spam_reason = None
    if is_spam and "reason:" in response_text:
        spam_reason = response_text.split("reason:")[1].strip()

    email_category = None
    if not is_spam:
        categories = ["inquiry", "complaint", "thank you", "request", "information"]
        for category in categories:
            if category in response_text:
                email_category = category
                break

    new_messages = state.get("messages", []) + [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": response.content}
    ]
    return {"is_spam": is_spam, "spam_reason": spam_reason,
            "email_category": email_category, "messages": new_messages}

```

**要点：**节点向 LLM 提问 → 解析响应 → 更新 state 字段 → 记录对话到 messages。

### 3. handle_spam —— 处理垃圾

```python
def handle_spam(state: EmailState):
    """Alfred discards spam email with a note"""
    print(f"Alfred has marked the email as spam. Reason: {state['spam_reason']}")
    print("The email has been moved to the spam folder.")
    return {}

```

### 4. draft_response —— 起草回复

```python
def draft_response(state: EmailState):
    """Alfred drafts a preliminary response for legitimate emails"""
    email = state["email"]
    category = state["email_category"] or "general"
    prompt = f"""
    As Alfred the butler, draft a polite preliminary response to this email.
    Email:
    From: {email['sender']}
    Subject: {email['subject']}
    Body: {email['body']}
    This email has been categorized as: {category}
    Draft a brief, professional response that Mr. Hugg can review and personalize before sending.
    """
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)
    new_messages = state.get("messages", []) + [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": response.content}
    ]
    return {"email_draft": response.content, "messages": new_messages}

```

### 5. notify_mr_hugg —— 通知先生

```python
def notify_mr_hugg(state: EmailState):
    """Alfred notifies Mr. Hugg about the email and presents the draft response"""
    email = state["email"]
    print("\n" + "="*50)
    print(f"Sir, you've received an email from {email['sender']}.")
    print(f"Subject: {email['subject']}")
    print(f"Category: {state['email_category']}")
    print("\nI've prepared a draft response for your review:")
    print("-"*50)
    print(state["email_draft"])
    print("="*50 + "\n")
    return {}

```

## 五、Step 3：定义路由逻辑

```python
def route_email(state: EmailState) -> str:
    """Determine the next step based on spam classification"""
    if state["is_spam"]:
        return "spam"
    else:
        return "legitimate"

```

**关键规则：**路由函数的返回值必须匹配条件边映射（conditional edges mapping）中的 key。

## 六、Step 4：创建 StateGraph 并连接边

```python
# 创建图
email_graph = StateGraph(EmailState)

# 添加节点
email_graph.add_node("read_email", read_email)
email_graph.add_node("classify_email", classify_email)
email_graph.add_node("handle_spam", handle_spam)
email_graph.add_node("draft_response", draft_response)
email_graph.add_node("notify_mr_hugg", notify_mr_hugg)

# 连接边
email_graph.add_edge(START, "read_email")
email_graph.add_edge("read_email", "classify_email")

# 条件分支
email_graph.add_conditional_edges(
    "classify_email",
    route_email,
    {"spam": "handle_spam", "legitimate": "draft_response"}
)

# 收尾边
email_graph.add_edge("handle_spam", END)
email_graph.add_edge("draft_response", "notify_mr_hugg")
email_graph.add_edge("notify_mr_hugg", END)

# 编译
compiled_graph = email_graph.compile()

```

**注意：**END 是 LangGraph 提供的特殊节点，表示工作流完成的**终止状态**。

## 七、Step 5：运行应用

两封测试邮件——正常邮件（服务咨询）和垃圾邮件（中奖诈骗）：

```python
legitimate_email = {
    "sender": "john.smith@example.com",
    "subject": "Question about your services",
    "body": "Dear Mr. Hugg, I was referred to you by a colleague and I'm interested in learning more about your consulting services. Could we schedule a call next week? Best regards, John Smith"
}

spam_email = {
    "sender": "winner@lottery-intl.com",
    "subject": "YOU HAVE WON $5,000,000!!!",
    "body": "CONGRATULATIONS! ... send us your bank details and a processing fee of $100."
}

legitimate_result = compiled_graph.invoke({
    "email": legitimate_email, "is_spam": None, "spam_reason": None,
    "email_category": None, "email_draft": None, "messages": []
})

spam_result = compiled_graph.invoke({
    "email": spam_email, "is_spam": None, "spam_reason": None,
    "email_category": None, "email_draft": None, "messages": []
})

```

**注意：**invoke 时要提供完整的初始 state（所有字段都要有值）。

## 八、Step 6：用 Langfuse 观察调试

**为什么需要？**Agent 天生不可预测、难以检查。要上线生产，需要可靠的**可观测性（traceability）**。

```python
%pip install -q langfuse
%pip install langchain

import os
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-..." 
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-..."
os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"  # EU 区域
# os.environ["LANGFUSE_HOST"] = "https://us.cloud.langfuse.com"  # US 区域

from langfuse.langchain import CallbackHandler
langfuse_handler = CallbackHandler()

# 调用时挂上回调
compiled_graph.invoke(
    input={"email": legitimate_email, "is_spam": None, "spam_reason": None,
           "email_category": None, "draft_response": None, "messages": []},
    config={"callbacks": [langfuse_handler]}
)

```

配置好后，每次运行都会被记录到 Langfuse，可以回看之前的运行、调试并改进邮件分拣智能体。

## 九、可视化流程图

```python
compiled_graph.get_graph().draw_mermaid_png()

```

生成图结构，清晰展示节点连接和条件路径，便于理解和调试。

## 十、关键收获（Key Takeaways）

- **状态管理：**定义了全面的 State 来跟踪邮件处理的每个方面
- **节点实现：**创建了与 LLM 交互的功能节点
- **条件路由：**基于邮件分类实现分支逻辑
- **终止状态：**用 END 节点标记工作流完成点

## 十一、新手常见误区

- **误区1：invoke 时漏传 state 字段。**初始 state 必须包含所有字段（可传 None 或空列表）。
- **误区2：路由返回值与映射 key 不匹配。**route_email 返回的字符串必须与 add_conditional_edges 的映射字典 key 一致。
- **误区3：忘了把 LLM 调用记录到 messages。**追踪对话历史对调试和后续功能很重要。
- **误区4：生产环境不上可观测性。**Agent 行为多变，Langfuse 这类工具是生产必备。

## 十二、下一步预告

下一节将探索 LangGraph 更高级的特性：在流程中处理**人工交互（human-in-the-loop）**，以及基于多条件实现**更复杂的分支逻辑**。

## 标签

#LangGraph #StateGraph #条件路由 #Langfuse
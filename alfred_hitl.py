"""
alfred_hitl.py —— 带 Human-in-the-Loop 的邮件分拣智能体（LangGraph 升级版）
============================================================================
在课程第 15 章邮件分拣的基础上加入"人类介入"：
草拟回复后，流程暂停（interrupt），等待 Mr. Hugg 审阅草稿——
    approve  → 发送
    revise   → 显示修订稿
    reject   → 直接丢弃

技术要点：
- interrupt() 在节点内暂停图执行，返回一个 payload 给外部调用者
- 调用者读取 __interrupt__，再用 Command(resume=决策) 恢复执行
- 必须配 checkpointer（InMemorySaver）保存中间状态才能恢复
"""

from typing import TypedDict, List, Dict, Any, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver

# ============================================================
# 1. 模拟 LLM（规则型，无需 API Key；换真实 LLM 只需替换此处）
# ============================================================

def mock_llm_classify(email: Dict[str, Any]) -> Dict[str, Any]:
    body = (email.get("subject", "") + " " + email.get("body", "")).lower()
    spam_hints = ["lottery", "won", "congratulations", "winner", "prize",
                  "$", "bank details", "processing fee", "click here"]
    hit = [h for h in spam_hints if h in body]
    if hit:
        return {"is_spam": True, "spam_reason": f"包含垃圾特征词: {', '.join(hit[:3])}",
                "email_category": None}
    categories = ["inquiry", "complaint", "thank you", "request", "information"]
    category = next((c for c in categories if c in email.get("body", "").lower()), "general")
    return {"is_spam": False, "spam_reason": None, "email_category": category}

def mock_llm_draft(email: Dict[str, Any], category: str) -> str:
    templates = {
        "inquiry":    "Thank you for your inquiry. We have received your questions and will respond within 24 hours.",
        "complaint":  "We are sorry to hear about your issue. We take complaints seriously and will investigate promptly.",
        "thank you":  "You are most welcome! We truly appreciate your kind words.",
        "request":    "Thank you for your request. We will process it as soon as possible.",
        "information": "Thank you for your message. Here is the information you requested...",
        "general":    "Thank you for reaching out. We will get back to you shortly.",
    }
    return templates.get(category, templates["general"])

# ============================================================
# 2. State
# ============================================================

class EmailState(TypedDict):
    email: Dict[str, Any]
    email_category: Optional[str]
    spam_reason: Optional[str]
    is_spam: Optional[bool]
    email_draft: Optional[str]
    review_status: Optional[str]   # approved / revised / rejected
    messages: List[Dict[str, Any]]

# ============================================================
# 3. 节点
# ============================================================

def read_email(state: EmailState):
    email = state["email"]
    print(f"  [Alfred] 收到来自 {email['sender']} 的邮件，主题: {email['subject']}")
    return {}

def classify_email(state: EmailState):
    email = state["email"]
    result = mock_llm_classify(email)
    new_messages = state.get("messages", []) + [
        {"role": "user", "content": f"Analyze email from {email['sender']}"},
        {"role": "assistant", "content": str(result)},
    ]
    return {**result, "messages": new_messages}

def handle_spam(state: EmailState):
    print(f"  [Alfred] 判定为垃圾邮件，原因: {state['spam_reason']}")
    print("  [Alfred] 已移入垃圾箱 ✅")
    return {}

def draft_response(state: EmailState):
    email = state["email"]
    category = state["email_category"] or "general"
    draft = mock_llm_draft(email, category)
    return {"email_draft": draft}

def human_review(state: EmailState):
    """★ 人类介入点：暂停图，等 Mr. Hugg 审阅草稿后决定去向"""
    email = state["email"]
    draft = state["email_draft"]

    decision = interrupt({
        "question": "Mr. Hugg，请审阅这封邮件的回复草稿（approve/revise/reject）",
        "from": email["sender"],
        "subject": email["subject"],
        "draft": draft,
    })
    # decision 由外部调用者通过 Command(resume=...) 提供

    if decision == "revise":
        return {
            "review_status": "revised",
            "email_draft": draft + "\n\n[P.S.] 已按 Mr. Hugg 意见修订。",
        }
    if decision == "reject":
        return {"review_status": "rejected"}
    return {"review_status": "approved"}

def send_email(state: EmailState):
    print(f"\n  ✉️  [Alfred] 已发送给 {state['email']['sender']}：")
    print("  ----------------------------------------")
    print(f"  {state['email_draft']}")
    print("  ----------------------------------------")
    return {}

def notify_revised(state: EmailState):
    print(f"\n  📝  [Alfred] 已按 Mr. Hugg 意见修订，展示修订稿：")
    print("  ----------------------------------------")
    print(f"  {state['email_draft']}")
    print("  ----------------------------------------")
    return {}

def handle_reject(state: EmailState):
    print(f"  🗑️  [Alfred] Mr. Hugg 拒绝该回复，草稿已丢弃。")
    return {}

# ============================================================
# 4. 路由
# ============================================================

def route_email(state: EmailState) -> str:
    return "spam" if state["is_spam"] else "legitimate"

def route_review(state: EmailState) -> str:
    """根据 Mr. Hugg 的审阅结果决定下一步"""
    return {
        "approved": "send_email",
        "revised": "notify_revised",
        "rejected": "handle_reject",
    }[state["review_status"]]

# ============================================================
# 5. 图组装
# ============================================================

def build_graph():
    builder = StateGraph(EmailState)

    builder.add_node("read_email", read_email)
    builder.add_node("classify_email", classify_email)
    builder.add_node("handle_spam", handle_spam)
    builder.add_node("draft_response", draft_response)
    builder.add_node("human_review", human_review)   # ★ 人类介入节点
    builder.add_node("send_email", send_email)
    builder.add_node("notify_revised", notify_revised)
    builder.add_node("handle_reject", handle_reject)

    builder.add_edge(START, "read_email")
    builder.add_edge("read_email", "classify_email")

    builder.add_conditional_edges("classify_email", route_email, {
        "spam": "handle_spam",
        "legitimate": "draft_response",
    })
    builder.add_edge("handle_spam", END)

    builder.add_edge("draft_response", "human_review")
    builder.add_conditional_edges("human_review", route_review, {
        "send_email": "send_email",
        "notify_revised": "notify_revised",
        "handle_reject": "handle_reject",
    })
    builder.add_edge("send_email", END)
    builder.add_edge("notify_revised", END)
    builder.add_edge("handle_reject", END)

    # ★ 必须配 checkpointer，interrupt 才能暂停/恢复
    return builder.compile(checkpointer=InMemorySaver())

# ============================================================
# 6. 测试：三封邮件 × 三种 Mr. Hugg 决策
# ============================================================

if __name__ == "__main__":
    alfred = build_graph()

    legit_email = {
        "sender": "john.smith@example.com",
        "subject": "Question about your services",
        "body": "Dear Mr. Hugg, I'm interested in your consulting services and would "
                "like to schedule a call. This is an inquiry. Best regards, John Smith",
    }

    tests = [
        ("thread-approve", "approve", "✅ Mr. Hugg 批准发送"),
        ("thread-revise", "revise", "📝 Mr. Hugg 要求修改"),
        ("thread-reject", "reject", "🗑️ Mr. Hugg 拒绝回复"),
    ]

    for thread_id, decision, note in tests:
        config = {"configurable": {"thread_id": thread_id}}
        print(f"\n{'#'*60}\n# {note}\n{'#'*60}")

        result = alfred.invoke({
            "email": legit_email, "is_spam": None, "spam_reason": None,
            "email_category": None, "email_draft": None,
            "review_status": None, "messages": [],
        }, config)

        # 图在 human_review 处暂停：读取中断信息
        if "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            print(f"  🛑 流程暂停，等待 Mr. Hugg 决策")
            print(f"     来自: {payload['from']} | 主题: {payload['subject']}")
            print(f"     草稿: {payload['draft'][:50]}...")
            print(f"     → Mr. Hugg 选择: {decision}")

            # 恢复执行：把 Mr. Hugg 的决策传回图
            result = alfred.invoke(Command(resume=decision), config)

        print(f"  最终状态: review_status={result['review_status']}")

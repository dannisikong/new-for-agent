"""
Alfred 邮件分拣智能体 —— LangGraph 完整实现
============================================
对应课程第 15 章工作流：
读邮件 → 分类(垃圾/正常) → 分支处理 → 草拟回复 → 通知主人

运行方式：本文件默认使用"内置规则 LLM"（不依赖任何 API Key），
可直接 python3 alfred_mail_agent.py 跑通全流程。

接入真实 LLM（任选其一，配置对应 API Key 后取消注释）：
    # 方案 A：OpenAI
    # from langchain_openai import ChatOpenAI
    # model = ChatOpenAI(model="gpt-4o", temperature=0)
    # 方案 B：Hugging Face Inference API
    # from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
    # llm = HuggingFaceEndpoint(repo_id="Qwen/Qwen2.5-Coder-32B-Instruct")
    # model = ChatHuggingFace(llm=llm, verbose=True)
"""

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

# ============================================================
# 1. 模拟 LLM：规则型分类器（不依赖 API，用于演示整条工作流）
#    换成真实 LLM 时，仅需替换这里的实现，图结构完全不变
# ============================================================

def mock_llm_classify(email: Dict[str, Any]) -> Dict[str, Any]:
    """规则型模拟 LLM：根据邮件特征判断垃圾/正常，并给出分类"""
    body = (email.get("subject", "") + " " + email.get("body", "")).lower()
    text = email.get("body", "").lower()
    sender = email.get("sender", "").lower()

    spam_hints = ["lottery", "won", "congratulations", "winner", "prize",
                  "$", "bank details", "processing fee", "click here"]
    hit = [h for h in spam_hints if h in body]
    if hit:
        return {
            "is_spam": True,
            "spam_reason": f"包含垃圾邮件特征词: {', '.join(hit[:3])}",
            "email_category": None,
        }

    # 正常邮件：按内容归入类别
    categories = ["inquiry", "complaint", "thank you", "request", "information"]
    category = next((c for c in categories if c in text), "general")
    return {
        "is_spam": False,
        "spam_reason": None,
        "email_category": category,
    }

def mock_llm_draft(email: Dict[str, Any], category: str) -> str:
    """规则型模拟 LLM：根据类别生成初步回复草稿"""
    templates = {
        "inquiry":    f"Dear {email.get('sender','')},\n\nThank you for your inquiry. "
                      "We have received your questions and will respond within 24 hours.\n\nBest regards, Mr. Hugg's Office",
        "complaint":  f"Dear {email.get('sender','')},\n\nWe are sorry to hear about your issue. "
                      "We take complaints seriously and will investigate promptly.\n\nBest regards, Mr. Hugg's Office",
        "thank you":  f"Dear {email.get('sender','')},\n\nYou are most welcome! We truly appreciate your kind words.\n\nBest regards, Mr. Hugg's Office",
        "request":    f"Dear {email.get('sender','')},\n\nThank you for your request. We will process it as soon as possible.\n\nBest regards, Mr. Hugg's Office",
        "information":f"Dear {email.get('sender','')},\n\nThank you for your message. Here is the information you requested...\n\nBest regards, Mr. Hugg's Office",
        "general":    f"Dear {email.get('sender','')},\n\nThank you for reaching out. We will get back to you shortly.\n\nBest regards, Mr. Hugg's Office",
    }
    return templates.get(category, templates["general"])

# ============================================================
# 2. 定义 State：图中流转的全部信息
# ============================================================

class EmailState(TypedDict):
    email: Dict[str, Any]          # 正在处理的邮件（sender/subject/body）
    email_category: Optional[str]  # 正常邮件的类别（inquiry/complaint/...）
    spam_reason: Optional[str]     # 判为垃圾邮件的原因
    is_spam: Optional[bool]        # 是否垃圾邮件
    email_draft: Optional[str]     # 草拟的回复
    messages: List[Dict[str, Any]] # 与 LLM 的对话记录（便于追踪）

# ============================================================
# 3. 定义 Nodes：每个节点是一个 Python 函数
# ============================================================

def read_email(state: EmailState):
    """Alfred 读取并登记收到的邮件"""
    email = state["email"]
    print(f"  [Alfred] 收到来自 {email['sender']} 的邮件，主题: {email['subject']}")
    return {}  # 无需修改 state

def classify_email(state: EmailState):
    """Alfred 用 LLM 判断邮件是垃圾还是正常"""
    email = state["email"]

    # ---- 在这里换成真实 LLM 调用 ----
    result = mock_llm_classify(email)
    # -------------------------------

    new_messages = state.get("messages", []) + [
        {"role": "user", "content": f"Analyze email from {email['sender']}"},
        {"role": "assistant", "content": str(result)},
    ]
    return {**result, "messages": new_messages}

def handle_spam(state: EmailState):
    """垃圾邮件：丢弃并记录原因"""
    print(f"  [Alfred] 判定为垃圾邮件，原因: {state['spam_reason']}")
    print("  [Alfred] 已移入垃圾箱 ✅")
    return {}

def draft_response(state: EmailState):
    """正常邮件：草拟初步回复"""
    email = state["email"]
    category = state["email_category"] or "general"

    # ---- 在这里换成真实 LLM 调用 ----
    draft = mock_llm_draft(email, category)
    # -------------------------------

    new_messages = state.get("messages", []) + [
        {"role": "user", "content": f"Draft response for {category} email"},
        {"role": "assistant", "content": draft},
    ]
    return {"email_draft": draft, "messages": new_messages}

def notify_mr_hugg(state: EmailState):
    """通知 Mr. Hugg：展示邮件信息与回复草稿"""
    email = state["email"]
    print("\n" + "=" * 56)
    print(f"  Sir，您收到一封来自 {email['sender']} 的邮件")
    print(f"  主题: {email['subject']}")
    print(f"  类别: {state['email_category']}")
    print("\n  我已草拟好回复，请您审阅：")
    print("-" * 56)
    print(state["email_draft"])
    print("=" * 56 + "\n")
    return {}

# ============================================================
# 4. 路由逻辑：分类后走哪条分支
# ============================================================

def route_email(state: EmailState) -> str:
    """根据分类结果决定下一步：spam → 丢弃；legitimate → 草拟回复"""
    return "spam" if state["is_spam"] else "legitimate"

# ============================================================
# 5. 组装 StateGraph：节点 + 边 + 条件分支
# ============================================================

def build_alfred_graph():
    graph = StateGraph(EmailState)

    # 添加节点（做事的函数）
    graph.add_node("read_email", read_email)
    graph.add_node("classify_email", classify_email)
    graph.add_node("handle_spam", handle_spam)
    graph.add_node("draft_response", draft_response)
    graph.add_node("notify_mr_hugg", notify_mr_hugg)

    # 定义边（控制流走向）
    graph.add_edge(START, "read_email")
    graph.add_edge("read_email", "classify_email")

    # 条件分支：从 classify_email 出发，由 route_email 决定去向
    graph.add_conditional_edges(
        "classify_email",
        route_email,
        {
            "spam": "handle_spam",            # 垃圾 → 丢弃
            "legitimate": "draft_response",   # 正常 → 草拟回复
        },
    )

    graph.add_edge("handle_spam", END)
    graph.add_edge("draft_response", "notify_mr_hugg")
    graph.add_edge("notify_mr_hugg", END)

    return graph.compile()

# ============================================================
# 6. 测试：一封正常邮件 + 一封垃圾邮件
# ============================================================

if __name__ == "__main__":
    alfred = build_alfred_graph()

    legit_email = {
        "sender": "john.smith@example.com",
        "subject": "Question about your services",
        "body": "Dear Mr. Hugg, I was referred to you by a colleague and I'm "
                "interested in learning more about your consulting services. "
                "Could we schedule a call next week? This is an inquiry. "
                "Best regards, John Smith",
    }
    spam_email = {
        "sender": "winner@lottery-intl.com",
        "subject": "YOU HAVE WON $5,000,000!!!",
        "body": "CONGRATULATIONS! You have been selected as the winner of our "
                "international lottery! To claim your $5,000,000 prize, please "
                "send us your bank details and a processing fee of $100.",
    }

    for label, mail in [("正常邮件", legit_email), ("垃圾邮件", spam_email)]:
        print(f"\n{'='*56}\n【{label}】处理开始\n{'='*56}")
        result = alfred.invoke({
            "email": mail,
            "is_spam": None,
            "spam_reason": None,
            "email_category": None,
            "email_draft": None,
            "messages": [],
        })
        print(f"【{label}】处理完成\n最终 state: is_spam={result['is_spam']}, "
              f"category={result['email_category']}, 草稿长度={len(result['email_draft'] or '')}")

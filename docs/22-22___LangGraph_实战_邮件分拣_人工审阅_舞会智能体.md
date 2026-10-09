<title>22 · LangGraph 实战（邮件分拣/人工审阅/舞会智能体）</title>

![](https://feishu.cn/file/U5ezbYalfo2QKnxDP0lcvc78nog)

# LangGraph 实战（邮件分拣/人工审阅/舞会智能体）

**一句话总述：**把课程学到的 LangGraph 知识真正跑起来——本实践交付 4 个可运行项目：**邮件分拣智能体**（5 节点条件分支）、**人工审阅版**（human-in-the-loop）、**舞会智能体**（ReAct 循环四工具）和 **create_react_agent 一行版**，全部无需 API Key 即可运行。

## 一、为什么动手跑一遍？

前 21 篇文档都是"读"，这一篇是"做"。动手写代码才能真正确认理解了：State 怎么流转、条件边怎么分流、interrupt 怎么暂停恢复。三件事：

1. 搭环境：Python 3.12 + pip install langgraph langchain-core
2. 写项目：从最简单的邮件分拣开始，逐步加复杂度
3. 验证：真实运行，观察每条分支的 trace 输出

## 二、项目1：邮件分拣智能体（5 节点图）

对应课程第 15 章，核心是**一张带条件分支的图**：

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class EmailState(TypedDict):
    email: dict
    is_spam: bool | None
    email_draft: str | None
    messages: list

# 节点：每个都是纯 Python 函数
def read_email(state): ...
def classify_email(state): ...   # 用 LLM 判断垃圾/正常
def handle_spam(state): ...
def draft_response(state): ...
def notify_mr_hugg(state): ...

graph = StateGraph(EmailState)
graph.add_node("read_email", read_email)
# ... 依次添加全部节点
graph.add_edge(START, "read_email")
graph.add_conditional_edges("classify_email", route_email, {
    "spam": "handle_spam", "legitimate": "draft_response"})
graph.add_edge("handle_spam", END)
graph.add_edge("notify_mr_hugg", END)
alfred = graph.compile()

```

**运行结果（两种分支）：**

- 正常邮件 inquiry → 草拟回复（156 字）+ 通知 Mr. Hugg
- 垃圾邮件（lottery/won/congratulations）→ 识别特征词 → 移入垃圾箱

## 三、项目2：人工审阅版（Human-in-the-Loop）

在草拟回复后插入**人工确认节点**——这是 LangGraph 相对 smolagents 的核心差异化能力。

```python
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver

def human_review(state):
    decision = interrupt({
        "question": "请审阅草稿（approve/revise/reject）",
        "from": state["email"]["sender"],
        "draft": state["email_draft"],
    })
    if decision == "revise":
        return {"review_status": "revised",
                "email_draft": state["email_draft"] + "\n[P.S.] 已修订"}
    if decision == "reject":
        return {"review_status": "rejected"}
    return {"review_status": "approved"}

# 图在 human_review 处暂停后：
result = alfred.invoke(input, config)          # 遇到 interrupt 暂停
payload = result["__interrupt__"][0].value     # 读取审阅信息
result = alfred.invoke(Command(resume="approve"), config)  # 恢复

```

**HITL 四要素：**

| 机制 | 作用 |
|-|-|
| interrupt(payload) | 在节点内暂停图执行，把待审内容抛给外部 |
| result["\_\_interrupt\_\_"] | 外部读取中断信息（谁发的、草稿内容） |
| Command(resume=决策) | 把人的决定传回图，从暂停处继续 |
| InMemorySaver checkpointer | 保存中间状态——能"暂停-恢复"的前提 |

**运行结果（三决策三路径）：**approve → 发送成功；revise → 展示修订稿；reject → 草稿丢弃。生产落地时 interrupt 对接真实审批界面。

## 四、项目3：舞会智能体（ReAct 循环四工具）

对应课程第 21 章，按工程结构拆三文件：retriever.py（宾客数据+检索）、tools.py（四工具）、app.py（图）。核心是 **assistant ↔ tools 的 ReAct 循环**：

```python
from langgraph.prebuilt import ToolNode, tools_condition

builder.add_node("assistant", assistant)   # 大脑：决定调哪个工具
builder.add_node("tools", ToolNode(TOOLS)) # 手：执行工具调用
builder.add_edge(START, "assistant")
builder.add_conditional_edges("assistant", tools_condition)  # 有tool_call→tools，否则→END
builder.add_edge("tools", "assistant")     # 关键回边：构成循环

```

**四场景实测：**

| 场景 | ReAct 轨迹 | 结果 |
|-|-|-|
| 查宾客 | assistant → guest_info_retriever | Ada Lovelace 完整档案+邮箱 |
| 天气烟花 | assistant → weather_info | Paris: Clear, 25°C |
| 聊 Qwen 模型 | assistant → hub_stats | Qwen2.5-VL-7B 3.3M 下载 |
| 多工具组合 ★ | assistant → guest_info → assistant → web_search | Tesla 档案 + 无线能量进展 |

**工程细节：**工具用 @tool 装饰器定义；真实 API（DDG 搜索、HF Hub）优先调用，网络受限时自动降级为模拟结果——生产级容错设计。

## 五、项目4：create_react_agent 一行版

对比手写图，prebuilt 一行搭出完全相同的 ReAct 循环：

```python
from langgraph.prebuilt import create_react_agent
from app import MockAlfredLLM
from tools import TOOLS

alfred = create_react_agent(MockAlfredLLM(), TOOLS)
result = alfred.invoke({"messages": [HumanMessage(content="Tell me about Dr. Nikola Tesla")]})

```

**手写图 vs 一行版：**一行版适合快速原型；需要精细控制（人工介入、自定义边、状态持久化）时手写 StateGraph。注意模型需兼容 Runnable 接口（继承 Runnable 并实现 invoke）。

## 六、新手常见误区

- **误区1：interrupt 不配 checkpointer。**没有 checkpointer 无法保存状态，暂停恢复会失败。
- **误区2：忘记 tools → assistant 回边。**没有回边就没有多轮工具调用，只有一轮。
- **误区3：把 tool_calls 当最终回答。**模型输出 tool_call 后必须等 ToolMessage 回来再作答。
- **误区4：create_react_agent 传非 Runnable 模型。**自定义模型要继承 Runnable。
- **误区5：外部 API 不设降级。**搜索/HF 查询失败会直接崩溃，应 try/except 优雅兜底。

## 七、本节小结

从"读"到"做"：邮件分拣验证了节点与条件分支，人工审阅掌握了 interrupt/Command/checkpointer 三件套，舞会智能体跑通了 ReAct 循环与多工具组合，一行版学会了选型。LangGraph 实战闭环完成——接下来换真实 LLM 即可直接部署。

## 标签

#LangGraph #ReAct #HITL #实战
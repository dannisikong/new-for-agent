<title>16 · LangGraph文档分析智能体</title>

![](https://feishu.cn/file/MidgbZdn9oFa8Oxi6VccXnZvnJe)

# LangGraph文档分析智能体

**一句话总述：**本章用 LangGraph 构建 Alfred 文档分析系统：用**视觉语言模型（VLM）**从图片提取文本、用普通工具做计算、分析内容并给出总结——这是第一个真正的 **Agent（含工具调用的 ReAct 循环）**。

## 一、系统能力

这个文档分析系统可以：

1. **处理图像文档**
2. **用视觉模型（VLM）提取文本**
3. **需要时执行计算**（演示普通工具）
4. **分析内容并提供简洁总结**
5. **执行与文档相关的特定指令**

**场景：**Mr. Wayne 留下训练计划和营养笔记，Alfred 分析文档并给出明天的菜单、购物清单。

## 二、环境搭建

```python
%pip install langgraph langchain_openai langchain_core

```

```python
import base64
from typing import List, TypedDict, Annotated, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage
from langgraph.graph.message import add_messages
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from IPython.display import Image, display

```

## 三、定义 AgentState（新概念：操作符）

```python
class AgentState(TypedDict):
    input_file: Optional[str]  # 文件路径（PDF/PNG）
    messages: Annotated[list[AnyMessage], add_messages]

```

**新概念：状态操作符（operators）**

- `AnyMessage`：LangChain 定义消息的类
- `add_messages`：一个**操作符**——把新消息**追加**到已有列表，而不是用最新状态**覆盖**
- LangGraph 允许在 state 字段里加操作符，自定义字段间的交互方式

## 四、准备工具

### 1. extract_text —— 视觉提取文本

```python
vision_llm = ChatOpenAI(model="gpt-4o")

def extract_text(img_path: str) -> str:
    """Extract text from an image file using a multimodal model."""
    all_text = ""
    try:
        with open(img_path, "rb") as image_file:
            image_bytes = image_file.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        message = [
            HumanMessage(content=[
                {"type": "text", "text": "Extract all the text from this image. Return only the extracted text, no explanations."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
            ])
        ]
        response = vision_llm.invoke(message)
        all_text += response.content + "\n\n"
        return all_text.strip()
    except Exception as e:
        error_msg = f"Error extracting text: {str(e)}"
        print(error_msg)
        return ""

```

**要点：**图片转 base64 → 以 image_url 形式发给多模态模型 → 提取文本；用 try/except **优雅处理错误**。

### 2. divide —— 计算工具

```python
def divide(a: int, b: int) -> float:
    """Divide a and b - for Master Wayne's occasional calculations."""
    return a / b

tools = [divide, extract_text]

llm = ChatOpenAI(model="gpt-4o")
llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=False)

```

**bind_tools：**把工具绑定给 LLM，让它知道可以调用这些工具（parallel_tool_calls=False 表示一次只调一个工具）。

## 五、assistant 节点

```python
def assistant(state: AgentState):
    textual_description_of_tool = """
extract_text(img_path: str) -> str: ...
divide(a: int, b: int) -> float: ...
"""
    image = state["input_file"]
    sys_msg = SystemMessage(content=f"You are a helpful butler named Alfred that serves Mr. Wayne and Batman. You can analyse documents and run computations with provided tools:\n{textual_description_of_tool} \n You have access to some optional images. Currently the loaded image is: {image}")
    return {
        "messages": [llm_with_tools.invoke([sys_msg] + state["messages"])],
        "input_file": state["input_file"]
    }

```

系统消息告诉模型：你是谁、有哪些工具、当前加载的图片是什么。

## 六、ReAct 模式与图结构（核心）

这个 Agent 遵循 **ReAct 模式（Reason-Act-Observe）**：

1. **Reason（思考）：**分析文档和请求
2. **Act（行动）：**使用合适的工具
3. **Observe（观察）：**查看结果
4. **Repeat（重复）：**直到完全满足需求

```python
builder = StateGraph(AgentState)

builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "assistant")
builder.add_conditional_edges("assistant", tools_condition)  # 关键：条件边
builder.add_edge("tools", "assistant")  # 关键：工具连回助理，形成循环

react_graph = builder.compile()

display(Image(react_graph.get_graph(xray=True).draw_mermaid_png()))

```

**循环如何工作：**

- `tools_condition`：检查 assistant 的最新输出是否调用了工具  

  - 调用了 → 路由到 tools 节点
  - 没调用 → 路由到 END，流程结束
- tools 节点执行后**连回 assistant**，循环继续
- 只要模型决定调用工具，循环就一直进行

**这就是 Agent 的本质：**LLM 决定何时用工具、何时结束回答。xray=True 可以透视内部结构。

## 七、实战演示

### 示例1：简单计算

```python
messages = [HumanMessage(content="Divide 6790 by 5")]
messages = react_graph.invoke({"messages": messages, "input_file": None})

```

对话流程：

```text
Human: Divide 6790 by 5
AI Tool Call: divide(a=6790, b=5)
Tool Response: 1358.0
Alfred: The result of dividing 6790 by 5 is 1358.0.

```

### 示例2：分析训练文档

```python
messages = [HumanMessage(content="According to the note provided by Mr. Wayne in the provided images. What's the list of items I should buy for the dinner menu?")]
messages = react_graph.invoke({"messages": messages, "input_file": "Batman_training_and_meals.png"})

```

对话流程：

```text
Human: 根据提供的图片笔记，晚宴菜单要买哪些东西？
AI Tool Call: extract_text(img_path="Batman_training_and_meals.png")
Tool Response: [提取出的训练计划和菜单文本]
Alfred: 菜单需要购买：1. 草饲牛排 2. 有机菠菜 3. Piquillo辣椒 4. 土豆 5. 鱼油2克

```

## 八、关键收获（Key Takeaways）

1. **定义清晰的工具：**为文档相关任务准备专用工具（提取文本、计算）
2. **创建健壮的状态追踪器：**维护工具调用之间的上下文
3. **考虑错误处理：**工具失败时优雅降级（如 extract_text 的 try/except）
4. **保持上下文感知：**用 add_messages 操作符确保模型能看到之前的对话

## 九、新手常见误区

- **误区1：忘了 tools_condition。**它决定"该调工具还是该结束"，是循环的关键开关。
- **误区2：忘了把 tools 连回 assistant。**没有这条边，Agent 只能调用一次工具，无法多轮推理。
- **误区3：用普通 model 而非 bind_tools。**不绑定工具，模型不知道可以调用工具。
- **误区4：messages 用覆盖而非追加。**要用 Annotated + add_messages，否则上下文会丢失。

## 十、本节小结

这个"assistant ↔ tools"循环图就是 Agent 的最小骨架：模型思考 → 决定调工具 → 观察结果 → 继续或结束。加上 VLM 视觉工具，Alfred 就能分析文档了。接下来可以探索更复杂的编排。

## 标签

#LangGraph #ReAct #VLM #ToolNode
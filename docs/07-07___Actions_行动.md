<title>07 · Actions（行动）</title>

![](https://feishu.cn/file/SeuMbd8bRoaUNexIJnbcPOROnEX)

# Actions（行动）

**一句话总述：**行动（Action）是 Agent 与环境交互的具体步骤，通过 JSON、代码或函数调用执行，并用"停止与解析（Stop and Parse）"方法保证输出结构化、可预测。

## 一、什么是 Action

Action 是 **Agent 与环境交互时执行的具体操作**——无论是浏览网页获取信息，还是控制物理设备。每个行动都是 Agent 执行的一次有目的的操作。

**例子：**客服 Agent 可能检索客户数据、推荐帮助文章，或把问题转给人工客服。

## 二、三种类型的 Agent（行动方式不同）

| 类型 | 说明 |
|-|-|
| **JSON Agent** | 要执行的动作以 JSON 格式指定 |
| **Code Agent** | Agent 编写一段代码块，由外部解释执行 |
| **Function-calling Agent** | JSON Agent 的子类，经过微调，能为每个动作生成一条新消息 |

## 三、Action 的四大用途

| 动作类型 | 说明 |
|-|-|
| **信息收集 Information Gathering** | 网页搜索、查询数据库、检索文档 |
| **工具使用 Tool Usage** | 调用 API、运行计算、执行代码 |
| **环境交互 Environment Interaction** | 操作数字界面、控制物理设备 |
| **沟通 Communication** | 通过聊天与用户互动，或与其他 Agent 协作 |

## 四、为什么 LLM 必须"停止生成"？

LLM 只处理文本，它用文本描述**想执行的动作和传给工具的参数**。要让 Agent 正常工作，关键要求是：

**LLM 在输出完定义完整动作的所有 token 后，必须停止生成新 token。**

这样做的原因：

- 把控制权从 LLM 交还给 Agent
- 确保输出可以被解析（无论是 JSON、代码还是函数调用格式）
- 防止多余的、错误的输出污染解析结果

## 五、Stop and Parse（停止与解析）方法

实现 Action 的关键方法，分三步：

1. **结构化格式生成：**Agent 用清晰、预定义的格式（JSON 或代码）输出它的意图动作
2. **停止继续生成：**动作文本输出完毕后，LLM 立即停止生成更多 token
3. **解析输出：**外部解析器读取格式化输出，确定调用哪个工具、提取所需参数

**例子：**检查天气的 Agent 可能输出：

```json
Thought: I need to check the current weather for New York.
Action:
{
  "action": "get_weather",
  "action_input": {"location": "New York"}
}

```

框架可以轻松解析出要调用的函数名和参数。这种清晰、机器可读的格式减少了错误，让外部工具能准确处理 Agent 的指令。

> 函数调用型 Agent（Function-calling）原理类似：把每个动作结构化，让指定函数以正确参数被调用。

## 六、Code Agent：另一种实现方式

Code Agent 的思路：**不是输出简单的 JSON 对象，而是生成一段可执行的代码块**（通常是 Python 等高级语言）。

### 优点

- **表达力强：**代码能自然表达复杂逻辑——循环、条件、嵌套函数，比 JSON 灵活得多
- **模块化与可复用：**生成的代码可以包含函数和模块，跨任务复用
- **更易调试：**有明确的编程语法，代码错误更容易发现和修正
- **直接集成：**可以直接对接外部库和 API，支持数据处理、实时决策等复杂操作

### 安全风险（重要！）

执行 LLM 生成的代码有安全风险，从 **prompt 注入**到执行**有害代码**。因此建议使用像 **smolagents** 这样内置默认防护的 AI Agent 框架，而不是自己裸执行代码。

**例子：**获取天气的 Code Agent 可能生成：

```python
# Code Agent Example: Retrieve Weather Information
def get_weather(city):
    import requests
    api_url = f"https://api.weather.com/v1/location/{city}?apiKey=YOUR_API_KEY"
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        return data.get("weather", "No weather information available")
    else:
        return "Error: Unable to fetch weather data."

result = get_weather("New York")
final_answer = f"The current weather in New York is: {result}"
print(final_answer)

```

这个例子中 Code Agent：通过 API 调用获取天气 → 处理响应 → 用 print() 输出最终答案。它同样遵循停止与解析方法：清晰界定代码块，并用输出（打印 final_answer）表示执行完成。

## 七、本节小结

Action 连接了 Agent 的内部推理与真实世界交互：通过 JSON、代码或函数调用执行清晰的结构化任务，用"停止与解析"保证动作精确、可被外部处理。下一节将学习 Observation（观察）——Agent 如何捕捉并整合环境反馈。

## 标签

#Actions #JSON #CodeAgent #StopAndParse
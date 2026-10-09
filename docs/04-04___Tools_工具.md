<title>04 · Tools（工具）</title>

![](https://feishu.cn/file/L5EfbuWLbo1NFXxS0qFcJ1PBnsh)

# Tools（工具）

**一句话总述：**工具是赋予LLM额外能力的函数，通过系统提示注入描述，让Agent能够调用工具执行动作、获取实时信息。

## 一、什么是 AI 工具

一个**工具（Tool）就是一个给 LLM 用的函数**，每个工具应该实现一个清晰的目标。常见的工具有：

| 工具 | 作用 |
|-|-|
| **Web Search（联网搜索）** | 让 Agent 获取互联网上的最新信息 |
| **Image Generation（图像生成）** | 根据文字描述生成图片 |
| **Retrieval（信息检索）** | 从外部数据源检索信息 |
| **API Interface（API接口）** | 与外部 API 交互（GitHub、YouTube、Spotify 等） |

这些只是例子——你几乎可以为任何需求创建工具。

## 二、为什么 LLM 需要工具？

- **LLM 只会"预测下一个词"：**它基于训练数据补全回答，内部知识只到训练截止日期为止
- **需要实时数据时必须靠工具：**比如直接问 LLM "今天的天气"，它可能编造一个随机天气（幻觉）；给它一个天气查询工具，就能拿到真实数据
- **工具能补足 LLM 的短板：**比如算数，用计算器工具比依赖模型原生能力更准确

**一句话：好的工具应该"互补 LLM 的能力"。**

## 三、一个工具包含什么

- **文本描述：**说明这个函数做什么
- **可调用对象（Callable）：**真正执行动作的函数
- **带类型的参数（Arguments）：**期望的输入及其类型
- **输出（Outputs，可选）：**返回结果的类型

## 四、工具是怎么工作的？

LLM 只能接收和生成文本，**它本身不会调用工具**。实际流程是：

1. 我们通过系统提示"告诉" LLM 存在哪些工具
2. LLM 在需要时**生成一段文本形式的工具调用**，例如 call weather_tool('Paris')
3. **Agent 读取这段响应**，识别出需要调用工具，代为执行工具并拿到真实数据
4. Agent 把工具结果作为新消息追加进对话，再次交给 LLM
5. LLM 基于结果生成自然语言回复给用户

**关键点：**工具调用过程通常不展示给用户，用户看到的效果就像 LLM 直接操作了工具，其实是 Agent 在后台完成的。

## 五、怎么把工具给 LLM？

核心方法：**用系统提示（system prompt）提供工具的文本描述**。必须精确说明两点：

- **工具做什么**
- **它期望什么输入**

通常用 JSON 或编程语言这类精确结构来描述（不是必须，但更可靠）。

**例子：一个乘法计算器**——先用 Python 实现：

```python
def calculator(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b

```

把它描述成给 LLM 的文本：

```
Tool Name: calculator, Description: Multiply two integers., Arguments: a: int, b: int, Outputs: int

```

## 六、@tool 装饰器：自动生成工具描述

手写描述容易遗漏细节。好消息是：**Python 源码本身就包含所有信息**——函数名、docstring、类型注解。利用 Python 的内省（introspection）能力，可以自动提取：

```python
@tool
def calculator(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b

print(calculator.to_string())

```

输出：

```
Tool Name: calculator, Description: Multiply two integers., Arguments: a: int, b: int, Outputs: int

```

**原理：**一个通用的 Tool 类封装函数的名称、描述、可调用对象、参数和输出；**@tool 装饰器**用 inspect.signature 自动提取函数签名、返回注解、docstring 和函数名，帮你生成 Tool 实例。这样工具描述就由代码自动维护，不会遗漏。

## 七、MCP：统一的工具接口协议

**Model Context Protocol（MCP）**是一个开放协议，标准化"应用如何把工具提供给 LLM"。它提供：

- 大量**预构建集成**，LLM 可直接插拔使用
- 灵活在**不同 LLM 供应商之间切换**
- 数据安全的**最佳实践**

**好处：**任何实现了 MCP 的框架，都能复用协议内定义的工具，不用为每个框架重写工具接口。

## 八、新手常见误区

- **误区1：以为 LLM 能自己调用工具。**实际上 LLM 只会生成"调用文本"，真正执行的是 Agent。
- **误区2：工具描述不精确。**说不清"做什么、要什么输入"，LLM 就会乱传参或不敢用。
- **误区3：手写描述。**用 @tool 自动生成更可靠，避免遗漏细节。

## 九、本节小结

工具让 Agent 突破静态知识的限制，处理实时任务和专门动作。理解"LLM 生成调用 → Agent 执行 → 结果回传"这条链路，是构建 Agent 的核心基础。

## 标签

#Tool #工具 #MCP #function_calling
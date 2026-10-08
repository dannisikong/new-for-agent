# 11 · CodeAgents（代码智能体）

<title>11 · CodeAgents（代码智能体）</title>

![](https://feishu.cn/file/ZfxNb9966ogCSWxqbRAcwX5InTh)

# CodeAgents（代码智能体）

**一句话总述：**CodeAgent 是 smolagents 的默认智能体类型——它生成 Python 代码（而不是 JSON）来表达动作，实现高效、表达力强、准确的操作，并配有沙箱执行保证安全。整个框架仅约 1000 行代码。

## 一、什么是 CodeAgent

CodeAgent 是 smolagents 的**默认智能体类型**。它通过生成 Python 工具调用来执行动作，相比传统 JSON 方式，动作表示更高效、更有表达力、更准确。

它的优势：

- **精简流程：**减少所需动作数量
- **简化复杂操作**
- **复用现有代码函数**

**轻量：**smolagents 构建代码智能体的框架仅约 1000 行代码。

## 二、为什么用代码而不是 JSON？

传统多步智能体流程中，LLM 用 JSON 格式指定工具名和参数字符串，**系统必须解析 JSON 才能确定执行哪个工具**。

但研究（论文《Executable Code Actions Elicit Better LLM Agents》）表明：**工具调用的 LLM 直接用代码效果更好**。这是 smolagents 的核心原则。

用代码写动作（而非 JSON）的四大优点：

| 优点 | 说明 |
|-|-|
| **组合性 Composability** | 容易组合和复用动作 |
| **对象管理 Object Management** | 直接处理复杂结构，如图像对象 |
| **通用性 Generality** | 能表达任何计算上可行的任务 |
| **对 LLM 自然 Natural for LLMs** | 高质量代码已经在 LLM 训练数据中大量存在 |

## 三、CodeAgent 是如何工作的？

CodeAgent 遵循第一单元学过的 **ReAct 框架**。smolagents 中智能体的核心抽象是 **MultiStepAgent**，CodeAgent 是它的一种特殊类型。

执行流程（CodeAgent.run()）：

1. 系统提示存入 **SystemPromptStep**，用户查询记录在 **TaskStep**
2. 进入 while 循环，每轮：  

   1. **write_memory_to_messages()：**把智能体的日志写成 LLM 可读的聊天消息列表
   2. 消息发送给 **Model**，生成一个补全（completion）
   3. **解析补全**提取动作——对 CodeAgent 来说就是一段代码片段
   4. **执行动作**
   5. 结果记录到内存中的 **ActionStep**
3. 每步结束时，如果智能体包含函数调用（agent.step_callback），则执行它们

## 四、实战：Alfred 筹备派对

Alfred 要在韦恩庄园办派对，我们用 CodeAgent 帮他。先安装并登录：

```bash
pip install smolagents -U

```

```python
from huggingface_hub import login
login()

```

### 示例1：联网选歌单

```python
from smolagents import CodeAgent, DuckDuckGoSearchTool, InferenceClientModel

agent = CodeAgent(tools=[DuckDuckGoSearchTool()], model=InferenceClientModel())

agent.run("Search for the best music recommendations for a party at the Wayne's mansion.")

```

运行时会显示工作流步骤轨迹和生成的 Python 代码（如 web_search(query="best music for a Batman party")），几轮后输出歌单。

**要点：**工具放在 **tools 列表**里给智能体；模型用 **InferenceClientModel**（Hugging Face 无服务器推理 API，默认模型 Qwen2.5-Coder-32B-Instruct）。

### 示例2：用 @tool 自定义工具准备菜单

```python
from smolagents import CodeAgent, tool, InferenceClientModel

@tool
def suggest_menu(occasion: str) -> str:
    """
    Suggests a menu based on the occasion.
    Args:
        occasion (str): The type of occasion for the party. Allowed values are:
                        - "casual": Menu for casual party.
                        - "formal": Menu for formal party.
                        - "superhero": Menu for superhero party.
                        - "custom": Custom menu.
    """
    if occasion == "casual":
        return "Pizza, snacks, and drinks."
    elif occasion == "formal":
        return "3-course dinner with wine and dessert."
    elif occasion == "superhero":
        return "Buffet with high-energy and healthy food."
    else:
        return "Custom menu for the butler."

agent = CodeAgent(tools=[suggest_menu], model=InferenceClientModel())
agent.run("Prepare a formal menu for the party.")

```

**技巧：**在 docstring 里精确写明 allowed values（允许值），能引导智能体传入真实存在的参数值，减少幻觉。

### 示例3：Python 导入（沙箱安全）

```python
from smolagents import CodeAgent, InferenceClientModel
import numpy as np
import time
import datetime

agent = CodeAgent(tools=[], model=InferenceClientModel(), additional_authorized_imports=['datetime'])

agent.run("""
    Alfred needs to prepare for the party. Here are the tasks:
    1. Prepare the drinks - 30 minutes
    2. Decorate the mansion - 60 minutes
    3. Set up the menu - 45 minutes
    4. Prepare the music and playlist - 45 minutes

    If we start right now, at what time will the party be ready?
    """)

```

**安全机制：**代码在沙箱中执行，白名单以外的 import 默认被阻止；用 **additional_authorized_imports** 参数可以授权额外模块（如 datetime）。

### 示例4：把智能体分享到 Hub

```python
agent.push_to_hub('sergiopaniego/AlfredAgent')

```

一键把完整智能体分享给社区，别人也能直接下载使用。

## 五、本节小结

smolagents 专精于"写并执行 Python 代码片段"的智能体：代码表达更自然、更强大，沙箱执行保证安全，本地和 API 模型都能用。这些例子只是开始——接下来我们会深入学习工具（Tools）的创建与使用。

## 标签

#CodeAgent #smolagents #ReAct #沙箱执行

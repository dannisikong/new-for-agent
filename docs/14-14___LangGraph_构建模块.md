<title>14 · LangGraph 构建模块</title>

![](https://feishu.cn/file/NFFEbgqEVovMXwxTm7dcmpVyncb)

# LangGraph 构建模块

**一句话总述：**LangGraph 应用由四大构建模块组成：**State（状态）**保存信息、**Nodes（节点）**执行操作、**Edges（边）**连接节点、**StateGraph（状态图）**是容纳整个工作流的容器。应用从入口点（START）出发，依流程走向不同函数，直到 END。

## 一、总览：应用如何运行

一个 LangGraph 应用：

- 从**入口点（entrypoint，即 START）**开始
- 根据执行情况，流程流向一个或另一个函数
- 直到到达 **END** 结束

接下来逐一认识四大核心组件。

## 二、State（状态）——中央概念

State 是 LangGraph 的**核心概念**，代表**流经应用的所有信息**。它用 TypedDict 定义：

```python
from typing_extensions import TypedDict

class State(TypedDict):
    graph_state: str

```

要点：

- State 是**用户自定义**的——字段应精心设计，包含**决策所需的所有数据**
- 想一想：应用需要在步骤之间跟踪哪些信息？

## 三、Nodes（节点）——Python 函数

Nodes 就是 Python 函数，每个节点：

1. **接收 state 作为输入**
2. **执行一些操作**
3. **返回对 state 的更新**

```python
def node_1(state):
    print("---Node 1---")
    return {"graph_state": state['graph_state'] +" I am"}

def node_2(state):
    print("---Node 2---")
    return {"graph_state": state['graph_state'] +" happy!"}

def node_3(state):
    print("---Node 3---")
    return {"graph_state": state['graph_state'] +" sad!"}

```

节点内可以包含：

- **LLM 调用：**生成文本或做决策
- **工具调用：**与外部系统交互
- **条件逻辑：**决定下一步
- **人工干预：**获取用户输入

> 提示：工作流必需的 START 和 END 节点由 LangGraph 直接内置提供。

## 四、Edges（边）——连接节点

Edges 连接节点，定义图中所有可能的路径。两种类型：

| 类型 | 行为 |
|-|-|
| **直接边（Direct）** | 总是从节点 A 到节点 B |
| **条件边（Conditional）** | 根据当前状态选择下一个节点 |

条件边示例（decide_mood 函数决定去 node_2 还是 node_3，这里是 50/50 随机）：

```python
import random
from typing import Literal

def decide_mood(state) -> Literal["node_2", "node_3"]:
    # 通常我们用 state 来决定下一个访问的节点
    user_input = state['graph_state']

    # 这里做个 50/50 的随机分流
    if random.random() < 0.5:
        return "node_2"   # 50% 去 Node 2
    return "node_3"        # 50% 去 Node 3

```

## 五、StateGraph（状态图）——工作流容器

StateGraph 是**容纳整个 Agent 工作流的容器**。构建流程：

```python
from IPython.display import Image, display
from langgraph.graph import StateGraph, START, END

# 1. 构建图
builder = StateGraph(State)
builder.add_node("node_1", node_1)
builder.add_node("node_2", node_2)
builder.add_node("node_3", node_3)

# 2. 连接逻辑
builder.add_edge(START, "node_1")
builder.add_conditional_edges("node_1", decide_mood)
builder.add_edge("node_2", END)
builder.add_edge("node_3", END)

# 3. 编译
graph = builder.compile()

```

可以可视化：

```python
display(Image(graph.get_graph().draw_mermaid_png()))

```

更重要的是可以调用：

```python
graph.invoke({"graph_state" : "Hi, this is Lance."})

```

输出（假设随机走到 node_3）：

```text
---Node 1---
---Node 3---
{'graph_state': 'Hi, this is Lance. I am sad!'}

```

流程拆解：START → node_1（追加 " I am"）→ 条件边 decide_mood → node_3（追加 " sad!"）→ END。

## 六、核心概念关系图

| 组件 | 类比 | 作用 |
|-|-|-|
| **State** | 共享笔记本 | 保存所有信息，节点间传递 |
| **Nodes** | 工作人员 | 读状态、干活、更新状态 |
| **Edges** | 路线图 | 规定流程走向，可直走可分支 |
| **StateGraph** | 公司大楼 | 容纳整个流程，编译后可运行 |

## 七、新手常见误区

- **误区1：忘记节点要返回状态更新。**节点不返回字典，状态就不会更新，后续节点拿不到数据。
- **误区2：以为 START/END 要自己定义。**它们由 LangGraph 内置。
- **误区3：条件边返回的名字与节点名不一致。**decide_mood 返回的字符串必须对应已 add_node 的名字。
- **误区4：状态字段乱设计。**字段要覆盖所有决策需要的数据，否则流程中缺信息。

## 八、本节小结

State 存信息、Nodes 做处理、Edges 定走向、StateGraph 装一切——这是 LangGraph 的"乐高积木"。下一步，用这些积木构建第一个图：Alfred 邮件分类智能体。

## 标签

#LangGraph #State #Nodes #Edges
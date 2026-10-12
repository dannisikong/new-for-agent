# 28 · MCP 四种能力：Tools、Resources、Prompts、Sampling

MCP Server 向 Client 暴露四类能力，每类有不同的控制方、安全级别和使用场景。

## 一、Tools（工具）：模型可控的可执行函数

Tools 是 AI 模型可以调用的可执行函数或动作，由 LLM 自主决定何时调用。

- **控制方**：模型（LLM）决定调用时机
- **安全**：有副作用（会执行操作），通常需要用户显式批准
- **典型场景**：发消息、创建工单、查询 API、执行计算
- **例子**：天气工具 get_weather(location) 返回温度和天气状况

## 二、Resources（资源）：应用可控的只读数据

Resources 提供只读数据访问，让 AI 模型获取上下文而不执行复杂逻辑。

- **控制方**：Host 应用决定何时访问
- **安全**：只读，风险低，类似 REST API 的 GET 请求
- **典型场景**：读取文件内容、查询数据库记录、读取配置
- **例子**：read_file(file_path) 返回文件内容

## 三、Prompts（提示模板）：用户可控的预定义工作流

Prompts 是预定义的模板或工作流，引导用户、AI 模型和 Server 能力之间的交互。

- **控制方**：用户选择使用哪个 Prompt
- **用途**：结构化交互，让用户在开始前选定任务模板
- **典型场景**：常用工作流、专业任务模板、引导式交互
- **例子**：code_review(code, language) 生成代码审查的系统提示和用户提示

## 四、Sampling（采样）：Server 发起的 LLM 请求

Sampling 允许 Server 请求 Client（Host 应用）执行 LLM 调用，实现递归或多步交互。

- **控制方**：Server 发起请求，Client 执行
- **安全**：需要用户批准
- **典型场景**：复杂多步任务、自主 Agent 工作流、交互式流程
- **流程**：Server 发 sampling/createMessage → Client 审核 → Client 调 LLM → Client 审核结果 → 返回给 Server

## 五、四种能力对比表

| 能力 | 控制方 | 方向 | 副作用 | 需要批准 | 典型场景 |
|------|--------|------|--------|----------|----------|
| Tools | 模型（LLM） | Client → Server | 有 | 是 | 执行动作、API 调用 |
| Resources | 应用 | Client → Server | 无（只读） | 通常不需要 | 数据查询、上下文获取 |
| Prompts | 用户 | Server → Client | 无 | 否 | 引导式工作流、模板 |
| Sampling | Server | Server → Client → Server | 间接 | 是 | 多步任务、自主 Agent |

## 六、四种能力如何配合使用

一个完整的 MCP 交互流程：
1. 用户选择一个 **Prompt** 启动专业工作流
2. Prompt 从 **Resources** 获取上下文数据
3. 处理过程中 LLM 调用 **Tools** 执行具体操作
4. 复杂任务时 Server 用 **Sampling** 请求额外的 LLM 处理

## 七、动态发现机制（Discovery）

Client 连接 Server 后，可以通过以下方法动态查询 Server 提供了哪些能力：

- `tools/list`：查询可用工具
- `resources/list`：查询可用资源
- `prompts/list`：查询可用提示模板

这种动态发现让 Client 不需要硬编码 Server 的功能，能自适应不同 Server。

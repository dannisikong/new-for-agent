# new-for-agent

LangGraph 学习与实践项目：一个可自定义模型的智能问答助手。基于 Hugging Face Agents 课程的 LangGraph 动手实现，默认使用内置模拟 LLM，无需 API Key 即可运行。内置 AI Agent 课程笔记知识库（Agentic RAG 闭环），也支持通过自定义 Token 接入任意 OpenAI 兼容模型进行通用问答。

## 项目内容

| 文件 | 说明 |
|---|---|
| `agent_core.py` | **ReAct 核心图**：assistant ↔ tools 循环，内置 Watchdog 死循环检测（最大步数 + 重复调用拦截），参数化 LLM 工厂 |
| `agentic_rag.py` | **Agentic RAG 闭环**：检索 → Fast Path 预判 → LLM 精判 → 不相关重写 → 再检索（上限 2 轮）→ 回答；Fast Path 覆盖率 <0.15 直接跳过 LLM 评分 |
| `knowledge_retriever.py` | 知识库检索：加载 `docs/*.md` → jieba 分词 → BM25 索引，HTTP/embedding client 单例复用 |
| `rerank.py` | Rerank 重排序（检索结果二次精排） |
| `tools.py` | 五个工具：知识库检索、宾客检索、网络搜索、天气、HF Hub 模型统计（真实 API 优先，失败自动降级） |
| `tool_errors.py` | 工具报错可纠正化：错误信息带修正建议，模型可自我纠错重试 |
| `tool_policy.py` | 工具权限策略：按场景控制工具可用范围 |
| `mcp_server.py` | 最小 MCP Server：把 knowledge_search / web_search 封装为 MCP 工具 |
| `mcp_client_check.py` | MCP Client 连通性自检 |
| `audit_log.py` | 可观测性 trace 化：全链路审计日志（tool_call / tool_result / watchdog_break 等事件） |
| `eval.py` + `eval_dataset.py` | 评测体系：演示模式下的问答准确率评估 |
| `alfred_mail_agent.py` | 邮件分拣智能体：5 节点图 + 条件分支 |
| `alfred_hitl.py` | 带 Human-in-the-Loop 的邮件分拣：interrupt / Command(resume) / checkpointer |
| `retriever.py` | 宾客数据集与关键词检索（模拟 BM25） |
| `sync_kb.py` | 飞书知识库 → 本地 docs/ Markdown 同步脚本 |
| `app.py` | 命令行版 ReAct 智能体 |
| `app_web.py` | Web 界面（Streamlit）：自定义 Token/模型，聊天操作智能体 |
| `react_agent_one_liner.py` | create_react_agent 一行版对比 |
| `docs/` | 飞书「AI Agent 学习知识库」45 篇课程笔记 Markdown 快照（检索数据源） |

## 快速开始

```bash
pip install -r requirements.txt

# 命令行版 ReAct 智能体
python3 app.py

# 知识库检索自测（BM25 中文检索）
python3 knowledge_retriever.py

# Agentic RAG 闭环自测（检索→评分→重写→回答）
python3 agentic_rag.py

# MCP Server 启动
python3 mcp_server.py

# 邮件分拣 / 人工审阅
python3 alfred_mail_agent.py
python3 alfred_hitl.py
```

## Web 界面

```bash
streamlit run app_web.py
```

两种模式：

1. **🌐 标准智能体（ReAct）**：五工具多步循环，带 Watchdog 死循环保护。
2. **📚 知识库智能问答（Agentic RAG）**：Fast Path 两级评分 + 重写闭环，回答标注来源文档。

侧边栏可自定义模型提供商、API Token、模型名与 Base URL（支持 OpenAI / DeepSeek / Moonshot / 通义千问等 OpenAI 兼容接口）。Token 仅在会话内存中使用，不写入代码或仓库。

线上实例：https://new-for-agent.streamlit.app/

## 技术要点

- **LangGraph 核心构件**：State / Nodes / Edges / 条件分支 / END / checkpointer
- **ReAct 循环 + Watchdog**：assistant ↔ tools 多步循环；最大 8 步工具调用 + 最近 5 次窗口内同工具重复 ≥3 次即强制收尾，审计日志记录 `watchdog_break`
- **Agentic RAG 两级评分**：Fast Path 程序层实词覆盖率（<0.15 直接拒，省 LLM 调用）→ Slow Path LLM 精判；不相关则重写问题重新检索（最多 2 轮）
- **Human-in-the-Loop**：`interrupt(payload)` 暂停 → 外部决策 → `Command(resume=决策)` 恢复
- **MCP Server**：工具通过 Model Context Protocol 暴露，支持外部 MCP Client 调用
- **可观测性**：全链路 trace 日志（thread_id / trace_id / span），可审计每次工具调用与异常
- **工具报错可纠正化**：错误信息带修正建议（如"网络超时，稍后重试"），模型可基于错误信息自我纠正
- **模型兼容**：自定义模型需继承 `Runnable` 并实现 `invoke`

## 接入真实 LLM

默认使用规则型模拟 LLM（无需 Key）。配置 API Key 后，在 Web 界面侧边栏填入即可；命令行版替换为：

```python
from langchain_openai import ChatOpenAI
model = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(TOOLS)
```

图结构无需改动。

## 说明

- 外部 API（DuckDuckGo 搜索、Hugging Face Hub）在受限网络环境下自动降级为模拟结果，保证演示闭环。
- `docs/` 知识库快照来自飞书「AI Agent 学习知识库」，共 45 篇课程笔记。
- 本项目为学习用途，代码中的邮箱、宾客信息均为示例数据。

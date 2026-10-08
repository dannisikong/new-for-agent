# new-for-agent

LangGraph 学习与实践项目：Alfred 智能体系列。基于 Hugging Face Agents 课程（Unit 1–3）的 LangGraph 动手实现，默认使用内置模拟 LLM，无需 API Key 即可运行。

## 项目内容

| 文件 | 说明 |
|---|---|
| `alfred_mail_agent.py` | 邮件分拣智能体：5 节点图 + 条件分支（垃圾/正常两路径） |
| `alfred_hitl.py` | 带 Human-in-the-Loop 的邮件分拣：interrupt / Command(resume) / checkpointer |
| `retriever.py` | 宾客数据集与关键词检索（模拟 BM25，可替换为 BM25Retriever） |
| `knowledge_retriever.py` | **AI Agent 课程知识库检索（BM25 中文版）**：加载 `docs/*.md` → jieba 分词 → BM25 索引，提供 `knowledge_search` 检索函数 |
| `agentic_rag.py` | **Agentic RAG 闭环（知识库智能问答）**：检索 → 评分 → 不相关重写 → 再检索（上限 2 轮）→ 回答；演示模式规则评分，真实模式 LLM 评分/重写 |
| `tools.py` | 五个工具：知识库检索、宾客检索、网络搜索、天气、HF Hub 模型统计（真实 API 优先，失败自动降级） |
| `docs/` | 飞书知识库「AI Agent 学习知识库」22 篇课程笔记的 Markdown 快照（检索数据源） |
| `app.py` | 舞会智能体：ReAct 循环图（assistant ↔ tools），四场景实测 |
| `react_agent_one_liner.py` | create_react_agent 一行版对比 |
| `agent_core.py` | 可复用后端核心：参数化 ReAct 图 + 真实 LLM 工厂（Web UI 使用） |
| `app_web.py` | Web 界面（Streamlit）：自定义 Token/模型，聊天操作智能体 |

## 快速开始

```bash
pip install -r requirements.txt

# 舞会智能体（ReAct 工具，四场景实测）
python3 app.py

# 知识库检索自测（BM25 中文检索）
python3 knowledge_retriever.py

# Agentic RAG 闭环自测（检索→评分→重写→回答）
python3 agentic_rag.py

# 邮件分拣（两种分支）
python3 alfred_mail_agent.py

# 人工审阅（三种决策：approve / revise / reject）
python3 alfred_hitl.py

# 一行版对比
python3 react_agent_one_liner.py
```

## Web 界面（可选）

带图形界面的聊天应用，侧边栏可自定义**回答模式**与模型提供商、API Token、模型名与 Base URL（支持 OpenAI / DeepSeek / Moonshot / 通义千问等 OpenAI 兼容接口，及 Hugging Face Inference API）。两种模式：

1. **🌐 标准智能体（ReAct）**：五工具（知识库 / 宾客 / 网络 / 天气 / HF 统计）多步循环，适合综合任务。
2. **📚 知识库智能问答（Agentic RAG）**：把官方教程的"检索 → 评分 → 不相关重写 → 再检索 → 回答"闭环移植到 AI Agent 课程知识库——首轮 BM25 召回，评分节点判断相关度，不相关则重写问题重新检索（最多 2 轮），回答标注来源文档。演示模式用规则评分，填 Token 后自动切真实 LLM 评分/重写。

```bash
streamlit run app_web.py
```

Token 仅在会话内存中使用，不写入代码或仓库。

### 部署到 Streamlit Community Cloud（免费）

1. 代码已在本仓库，无需改动。
2. 登录 https://streamlit.io/cloud 并用 GitHub 账号授权。
3. 点击 **New app** → 选择 `dannisikong/new-for-agent` 仓库 → Main branch → 入口文件填 `app_web.py` → Deploy。
4. 部署完成后获得公开 URL；侧边栏填入你自己的 API Token 即可使用。

> 备选：将本仓库推送到 Hugging Face 创建 Space（Streamlit SDK），同样可直接运行。

## 技术要点

- **LangGraph 核心构件**：State / Nodes / Edges / 条件分支 / END
- **ReAct 循环**：`assistant` 节点决定调用哪个工具，`tools_condition` 分岔，`tools → assistant` 回边构成多步循环
- **Agentic RAG 闭环**：`decide → retrieve → grade →（相关）answer /（不相关）rewrite → retrieve`；评分用问题实词覆盖率（演示）或 LLM 结构化输出（真实），重写保留名词并聚焦文档主题词
- **Human-in-the-Loop**：`interrupt(payload)` 暂停图 → 外部读取 `__interrupt__` → `Command(resume=决策)` 恢复；需配置 checkpointer
- **模型兼容**：自定义模型需继承 `Runnable` 并实现 `invoke`，才能用于 `create_react_agent`

## 接入真实 LLM

默认使用规则型模拟 LLM（无需 Key）。配置 API Key 后，将 `app.py` / `alfred_hitl.py` 中的模型替换为：

```python
from langchain_openai import ChatOpenAI
model = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(TOOLS)
```

图结构无需改动。

## 说明

- 外部 API（DuckDuckGo 搜索、Hugging Face Hub）在受限网络环境下自动降级为模拟结果，保证演示闭环。
- `docs/` 知识库快照来自飞书「AI Agent 学习知识库」课程笔记（知识库内容已获授权公开）。本地知识库更新后，可重新从飞书导出同步。
- 本项目为学习用途，代码中的邮箱、宾客信息均为示例数据。

# 开发纪要（Development Log）

> 记录 new-for-agent 项目每个阶段做了什么、为什么做、验证方式。最新在最前。

## 2026-11-08 · Watchdog 死循环检测 + RAG Fast Path 两级评分

### 背景
借鉴 DeepSeek Super-agent 架构（44 号笔记）里的 Watchdog 外部控制回路和 Fast Path/Slow Path 两级过滤思想，在学习项目里实践最小版本。ReAct 图此前只有步数自然终止，模型一旦陷入重复工具调用就会无限循环；RAG 评分节点每次都调 LLM，即使检索结果明显不相关也不例外。

### 完成
- **`agent_core.py` 新增 Watchdog 死循环检测**：
  - 新增 `_detect_loop()` 函数，两类异常：总工具调用超过 `MAX_TOOL_CALLS=8` 次强制收尾；最近 `REPEAT_WINDOW=5` 次窗口内同一工具名出现 `REPEAT_LIMIT=3` 次判定循环。
  - 命中后**不执行工具**，直接返回一条强制收尾提示（"请基于已有信息直接回答，不要再调用工具"），让 assistant 下一轮停止调工具。
  - 审计日志新增 `watchdog_break` 事件，记录 span=watchdog、pending 工具数、ok=False。
- **`agentic_rag.py` 新增 Fast Path 两级评分**：
  - grade 节点先跑程序层实词覆盖率计算（复用 jieba 分词 + 停用词表），覆盖率 < `_FAST_PATH_COVERAGE=0.15` 直接判 `not_relevant`，**跳过 LLM grade**。
  - 覆盖率 ≥0.15 才走 Slow Path 交 LLM 精判（真实模式）或规则判定（演示模式）。
  - 设计原则"宁可误放不可误杀"：只有覆盖率极低的明显不相关场景才 Fast Path 拦截，其余都交 LLM 判，避免误杀相关文档。

### 验证
- 编译/导入通过；ReAct 演示模式 4 步正常收尾；RAG 演示模式 3 步（检索→评分→回答）正常。
- Watchdog 单元测试 4 case：正常调用放行 / 重复 guest_info ×3 拦截 / 超步数 9+1=10 拦截 / 边界 7+1=8 放行，全通过。
- Fast Path 边界验证："什么是 RAG？"覆盖率 ≥0.15 走 Slow Path 不误杀；"今天股票市场怎么样？"覆盖率在 0.15-0.4 之间也走 Slow Path 交 LLM 判，行为正确。
- commit `46c2be1`，代码单独提交不混笔记。

---

## 2026-11-08 · 笔记归档 43–45 + README 专业化

### 背景
持续推进学习笔记线（本地 docs/ → 飞书知识库 → GitHub 三重交付），同时把 README 从课程作业风格改成面试可用的专业项目描述。

### 完成
- **43 号笔记**：面试八股速查（分布式限流 / 布隆过滤器 / MySQL / LangGraph Reducer 与多 Agent / 链表哈希），结合本项目实践整理。
- **44 号笔记**：DeepSeek Super-agent 架构探索（双层 Router-Worker / 事件驱动 / 存算分离 / Watchdog 外部控制回路）。
- **45 号笔记**：FDE 前沿部署工程师（Palantir 模式 / Builds-Embeds-Owns 三动词 / 深层剥离法 / 中国实践数据）。
- **README 更新**：补全 MCP Server / 可观测性 trace / 评测体系 / Rerank / 工具报错可纠正化等文件描述；docs 数量从 22 篇更新到 45 篇；去除"宾客检索""邮件分拣"等 demo 措辞，改为"样本查询""条件分支图示例"等专业表述；删掉"代码中的邮箱、宾客信息均为示例数据"那句。

### 验证
- 每篇笔记：本地写 `docs/NN-*.md` → 飞书 `wiki +node-create` → `docs +update --command append` → `docs +fetch --scope keyword` 回读关键词全命中 → git 单独 commit 推送。
- tracked docs 从 42 篇增长到 45 篇。
- commits：`b5446af`（43）→ `4215f6c`（44）→ `b541509`（45）→ `6f47111`（README 更新）→ `911fd38`（README 专业化）。

---

## 2026-10-22 · 修复演示模式 ReAct 死循环（任务 #6 本地验证）

### 背景
推进 #6 Streamlit 本地验证时，headless 起服务后脚本化跑演示模式 ReAct 图，提问直接挂起（40s 超时被终止）。最小复现定位：`_safe_tool_node` 构造 `ToolMessage` 时只传 `content` 与 `tool_call_id`，没回传 `name`；`MockAlfredLLM` 靠 `m.name` 集合判断工具是否已调用，结果 `called` 全为 `None`，每轮都以为工具没调过 → 无限 ReAct 循环。真实 LLM 不依赖 `ToolMessage.name` 做判断，所以线上真实模式未暴露，仅演示模式必现。

### 完成
- `agent_core._safe_tool_node` 三条 `ToolMessage`（白名单拒绝、参数级拒绝、正常执行）统一补 `name=name`，让消息历史能被模型/规则正确识别归属工具。
- 未改图结构、工具执行逻辑、权限校验与审计字段。

### 验证
- ReAct 单工具「Tell me about Ada Lovelace」5 条消息正常收尾，返回宾客档案；多工具「Dr. Nikola Tesla + recent advancements」两轮 `guest_info_retriever → web_search` 后收尾，`web_search` 超时走既有模拟降级文案，不挂死。
- RAG 演示模式 `build_rag_graph(None)` 3 步轨迹正常输出；全模块编译、`import` 链无报错。
- headless `streamlit run app_web.py`：`/healthz` 与首页均 200，启动日志无 traceback；MCP stdio 自检枚举 `['knowledge_search','web_search']`，KB 真实召回，越权参数被拦截。
- 线上实例 https://new-for-agent.streamlit.app/ 已完成浏览器复测：单工具 / 多工具 / 知识库三类问题均正常。

---

## 2026-10-22 · HTTP/embedding client 单例复用（任务 #4）

### 背景
Streamlit 每次脚本重跑（每次提问、人在回路 resume）都调 `make_llm(...)`，旧实现每次新建 `ChatOpenAI / ChatHuggingFace` 与 `EmbeddingClient`，底层 TCP/TLS 连接不复用；且每次都 `set_embedding_client(new)` 会把全局 `_vector_index` 置空，导致下一轮检索重复重建向量索引。查询答案已有 LRU 缓存，底层连接与索引这一层还是反复初始化。

### 完成
- **`knowledge_retriever.EmbeddingClient` 连接池化**：实例内持有一个 `requests.Session()`，Authorization 在 session 头里设置一次，`embed()` 复用同一连接池，跨多次向量请求不重复建连；接口签名与返回格式不变。
- **`agent_core.make_llm` 配置级缓存**：以 `(provider, api_key, model_name, base_url)` 为 key 缓存已构造的 Runnable，同配置直接复用，底层 OpenAI/HF 客户端连接池随之复用；配置变更（换 Key/模型/Base URL）才缓存未命中、新建实例。
- **embedding 配置去重置**：记录上次生效的 embedding 指纹 `(base_url, emb_model, api_key)`，配置未变化时保留既有 client 与已建向量索引，不再重复 `set_embedding_client` 清空索引；配置变化或切到纯 BM25 提供商时才重建/置空。
- 图编译（`build_rag_graph / build_react_graph`）保持每次新建：checkpointer 是全局共享单例，图对象轻量，本轮不做图缓存，避免过度工程。

### 验证
- `python3 -m py_compile` 全部模块通过；`import tools / agent_core / agentic_rag / knowledge_retriever / app / app_web` 无报错。
- 单例断言：演示模式两次 `make_llm` 返回同一实例；OpenAI 兼容同配置复用 LLM 与 embedding client；换 Key 后新 LLM 实例、embedding client 重建；回退演示模式 embedding 正确置空。
- `EmbeddingClient` 持有 `requests.Session`，鉴权头已注入，base_url / model 取值正确。
- RAG 演示模式端到端冒烟：召回正常、3 步轨迹、重复提问 LRU 缓存命中；MCP stdio 自检枚举 `['knowledge_search','web_search']`，KB 真实召回，越权参数被拦截，web_search 超时走既有降级。
- 备注：Hugging Face 分支依赖 `langchain-huggingface`（已在 requirements.txt），本运行环境未安装该包，属既有环境限制，非本轮回归。

---

## 2026-10-22 · 工具 docstring/schema 规范化（任务 #1）

### 背景
五个 `@tool` 的旧 docstring 是零散英文短句，模型选工具时拿不到"何时调用/何时不用"的边界；且参数说明只写在 docstring 里，LangChain 不会把它解析进字段级 schema。模型选错工具、把知识库问题拿去联网搜，根因之一就是工具描述不够清晰。

### 完成
- **五个工具统一改成三段式 docstring**：`何时调用（触发场景 + 边界排除）→ Args 入参含义/格式/禁止项 → Returns 返回格式`，语言以中文为主、保留关键英文术语，描述与后端真实返回逐一对齐（不写没实现的能力）。
  - `guest_info_retriever`：4 位内置宾客档案，无匹配返回固定英文提示；
  - `web_search`：只用于外部实时信息，课程概念优先 `knowledge_search`；联网失败返回的是"[模拟搜索结果]"降级文案，不得当事实；
  - `weather_info`：明确是随机占位演示数据，不是实时预报；
  - `hub_stats`：author 必须是 HF 用户名/组织名，非完整模型 ID；
  - `knowledge_search`：课程范围内知识点优先用本工具，外部新闻走 `web_search`。
- **字段级 schema 补描述**：参数改用 `Annotated[str, Field(description=...)]`，让参数说明进入 `args_schema.model_fields`，模型在 function calling 时同时看到工具描述与参数描述。
- 纯文档/注解改动，未改任何工具执行逻辑、重试策略与权限校验。

### 验证
- `python3 -m py_compile tools.py` 通过；`import tools / agent_core / agentic_rag` 均无报错。
- 五个字段 description 全部进入 schema（`f.description` 非空）；`TOOL_NAMES`、`TOOL_DESCRIPTIONS` 映射完整（5 个）。
- 本地冒烟：`guest_info_retriever("Ada Lovelace")` 命中档案、`weather_info("Beijing")` 返回占位天气、`knowledge_search("什么是 MCP")` 命中文档片段（len 886）。
- MCP stdio 自检 `mcp_client_check.py`：发现 `['knowledge_search','web_search']`，KB 真实召回；越权参数 `; cat /etc/passwd` 被最小权限策略拒绝；web_search 联网超时走既有降级，与本轮改动无关。

---

## 2026-10-21 · P3.5 Agent 可观测性 trace 化

### 背景
对齐当日行业信号（Anthropic 为托管 Agent 出 OpenTelemetry traces、MCP 缺鉴权与可观测被反复点名）：现有 `audit_log.jsonl` 是离散事件，只有会话级 `thread_id`，缺"单次问答内各步串联"和耗时/成本。

### 完成
- **`audit_log.py` 升级**：`log_event` 新增可选字段 `trace_id / span / duration_ms / tokens / cost_usd`（全部默认 None，旧调用零改动向后兼容）；新增 `new_trace_id()` 生成 `tr-xxxxxxxx`、`read_trace(trace_id)` 拉一次 trace 的全部 span、`summarize_trace(trace_id)` 汇总总耗时/总成本/失败数。
- **`agentic_rag.rag_query` 入口**：每次问答生成一个 `trace_id` 注入 `config.configurable`，自动透传给图内所有节点；`round` 审计带上 trace_id、span=`round`、duration_ms。
- **`agentic_rag.web_search_node`** 与 **`agent_core._safe_tool_node`**：从 config 取 trace_id，用 `time.perf_counter()` 包工具调用计时，span 命名 `tool:<工具名>`，成功/拒绝/报错三类日志全部串上同一 trace。

### 设计要点
- 一次问答 = 一个 trace_id，内部每步是一个 span，对应"trace → span → 事件"标准可观测模型；当前阶段本地 JSONL 已满足学习项目的可观测需求，暂不引入外部 trace 后端（LangSmith / OTel）。
- tokens/cost_usd 字段先预留，等模型侧用量上报接入即可填充，不阻塞当前链路。
- 审计写失败依旧全静默吞掉，绝不影响主流程。

### 验证
- 向后兼容：不带 trace 的旧 `log_event` 调用正常落盘。
- 新链路冒烟：`new_trace_id → log_event(tool/round) → read_trace → summarize_trace`，2 个 span 正确汇总 total_duration_ms=923.4、failed=0。
- `audit_log.py / agent_core.py / agentic_rag.py` 编译通过，`import agent_core` 无报错。

---

## 2026-10-18 · P2 工具报错可纠正化 + 收尾

### 本轮完成
- **新增 `tool_errors.py`**：把工具异常按类别归类（auth 认证/401-403、not_found 404、rate_limit 429、server 5xx、network 网络超时、invalid_args 参数格式、unknown），并为每类给出模型可执行的下一步动作，替代原先泛泛的"请检查参数后重试"。
- **接入两个调用点**：
  - `agent_core.py` 的 `_safe_tool_node` 执行失败分支，改用 `corrective_tool_message` 返回可纠正提示；
  - `agentic_rag.py` 的 `web_search_node` 异常分支同步替换。
- 错误摘要只取异常类型 + 首条消息，不带堆栈，避免把内部细节甩给模型。

### 设计要点
- 分类口径与 `tools.py` 的 `_classify_error` 保持一致，但职责分离：`_classify_error` 决定"要不要重试、退避多久"，`tool_errors` 决定"告诉模型下一步怎么纠正"。
- 不鼓励盲目重试：401/403 提示检查凭证、404 提示换关键词、429 提示退避后只重试一次。

### 验证
- 8 类异常分类单测全过（401/403→auth，404→not_found，429→rate_limit，5xx→server，ConnectionError→network，TypeError→invalid_args，其余→unknown）。
- 知识库问答回归通过，整体 import 无报错。

---

## 2026-10-18 · P1 最小 MCP Server

### 完成
- 新增 `mcp_server.py`：用官方 FastMCP 把 `knowledge_search`、`web_search` 包装成 MCP 工具，stdio 传输；Server 只做协议适配，业务逻辑零重复，边界复用 `tool_policy` 参数校验。
- 新增 `mcp_client_check.py`：stdio 端到端自检（发现工具 → 调用 → 越权拦截）。
- 新增 `MCP_SETUP.md`：本地启动与 Cursor 接入 JSON 配置说明。
- `requirements.txt` 补 `mcp` 依赖。

### 验证
- Client 发现工具 `['knowledge_search', 'web_search']`；knowledge_search 真实召回课程笔记；越权参数 `; cat /etc/passwd` 被最小权限策略拒绝；web_search 联网超时走容错，不影响 MCP 链路。

---

## 2026-10-18 · P0 安全加固（参数级最小权限 + 本地审计）

### 完成
- 新增 `tool_policy.py`：每个工具的参数规则（类型/长度上限/允许字符），命令符、本地路径穿越、超长、非法字符一律 fail-closed 拒绝，并给出可读原因让模型纠正。
- 新增 `audit_log.py`：JSONL 结构化审计轨，记录 `round / tool_call / tool_denied / tool_error / human_review`，写失败静默不影响主流程。
- `agent_core.py` 工具分发节点：白名单后加参数校验，成功/拒绝/报错都写审计。
- `agentic_rag.py`：web_search 调用前过权限校验，整轮问答与人工确认落审计。
- 修复 decide 路由映射缺失 `rewrite_query` 键的既有问题。
- `.gitignore` 忽略 `logs/`、`checkpoints.db`、`.env`。

### 三层防护（面试可讲）
1. function calling 工具名白名单，拦幻觉工具名；
2. 参数级最小权限，命令符/本地路径/超长直接拒；
3. 高风险人工审批 + 每步结构化审计，可复盘、可熔断。

### 验证
- `tool_policy` 9 组用例全过；工具节点实测：幻觉工具名拒绝、危险参数拒绝、正常参数执行，三类事件正确落审计；知识库问答回归通过。

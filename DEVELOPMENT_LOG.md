# 开发纪要（Development Log）

> 记录 new-for-agent 项目每个阶段做了什么、为什么做、验证方式。最新在最前。

## 2026-10-21 · P3.5 Agent 可观测性 trace 化

### 背景
对齐当日行业信号（Anthropic 为托管 Agent 出 OpenTelemetry traces、MCP 缺鉴权与可观测被反复点名）：现有 `audit_log.jsonl` 是离散事件，只有会话级 `thread_id`，缺"单次问答内各步串联"和耗时/成本。

### 完成
- **`audit_log.py` 升级**：`log_event` 新增可选字段 `trace_id / span / duration_ms / tokens / cost_usd`（全部默认 None，旧调用零改动向后兼容）；新增 `new_trace_id()` 生成 `tr-xxxxxxxx`、`read_trace(trace_id)` 拉一次 trace 的全部 span、`summarize_trace(trace_id)` 汇总总耗时/总成本/失败数。
- **`agentic_rag.rag_query` 入口**：每次问答生成一个 `trace_id` 注入 `config.configurable`，自动透传给图内所有节点；`round` 审计带上 trace_id、span=`round`、duration_ms。
- **`agentic_rag.web_search_node`** 与 **`agent_core._safe_tool_node`**：从 config 取 trace_id，用 `time.perf_counter()` 包工具调用计时，span 命名 `tool:<工具名>`，成功/拒绝/报错三类日志全部串上同一 trace。

### 设计要点
- 一次问答 = 一个 trace_id，内部每步是一个 span，对应"trace → span → 事件"标准可观测模型；不引入外部 trace 后端，先在本地 JSONL 落地，后续可平移到 LangSmith / OTel。
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

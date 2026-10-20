# 开发纪要（Development Log）

> 记录 new-for-agent 项目每个阶段做了什么、为什么做、验证方式。最新在最前。

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

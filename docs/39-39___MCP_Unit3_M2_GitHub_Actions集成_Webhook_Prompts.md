# 39 · MCP Unit 3 Module 2：GitHub Actions 集成（Webhook + MCP Prompts）

## 一句话总述

在 M1 静态分析的基础上，再加一个独立的 webhook 服务（:8080）收 GitHub Actions 事件落盘 `github_events.json`，MCP Server 只读卡文件分析，并新增两个 CI/CD 工具和四个 `@mcp.prompt()` 标准化工作流模板；用 Cloudflare Tunnel 把本地 8080 暴露给公网 GitHub。

---

## 一、场景：静默的失败

周二 CI 测试失败没人看（47 个仓库、每天几十个 commit，没人逐个点 build），周五下午支付系统线上故障，排查两小时才发现根因就是那次被忽略的红叉。

**任务**：给 PR Agent 加实时监控，问题刚发生就被 Claude 发现并提示，不再等线上炸了才追。

- M1 是**静态**：你问它才分析代码。
- M2 是**动态**：7×24 盯着 CI/CD，Claude 随时能查最近发生了什么。

---

## 二、架构：双服务分离（重点）

```
┌─────────────── GitHub 仓库（Actions 跑测试）───────────────┐
│        workflow_run 完成 → 发 webhook 事件                   │
└───────────────────────────┬────────────────────────────────┘
                            │ HTTPS（经 Cloudflare Tunnel）
                            ▼
┌─────────────────── webhook_server.py (:8080) ──────────────┐
│ 处理 HTTP 复杂度：校验、解析、追加写入                        │
│   → github_events.json（带时间戳，纯文件，无数据库）         │
└───────────────────────────┬────────────────────────────────┘
                            │ 读 JSON 文件（不碰 HTTP）
┌──────────────────────────▼────────────────────────────────┐
│  MCP Server（跟 Claude 通信）                                │
│   · M1 工具：analyze_file_changes / get_pr_templates / suggest_template │
│   · M2 工具：get_recent_actions_events / get_workflow_status │
│   · M2 Prompts：4 个标准化工作流模板                          │
└───────────────────────────▲────────────────────────────────┘
                            │ MCP 协议（stdio）
                        Claude Code
```

**为什么分两个服务**：webhook server 专管 HTTP 收发，MCP server 专管数据分析和跟 Claude 集成，关注点分离；而且 MCP 只读卡文件，测试时**手动往 JSON 里塞事件**就能测工具，不用真搭 webhook。

---

## 三、事件存储：一个 JSON 文件

- 每个进来的 webhook（push / pull_request / workflow 完成等）追加到 `github_events.json`，带时间戳。
- 文件就是事件日志，MCP 工具读它分析；不需要数据库。
- 第一次收到事件时文件才自动创建；文件不存在时工具返回空列表，不报错。

```python
# MCP server 里只需要一个路径常量，不处理 HTTP
EVENTS_FILE = Path(__file__).parent / "github_events.json"
```

---

## 四、两个新 CI/CD 工具（Step 3）

| 工具 | 职责 |
|---|---|
| `get_recent_actions_events` | 读 EVENTS_FILE，返回最近 N 条事件；文件不存在返回空列表 |
| `get_workflow_status` | 读全部事件，筛出 `workflow_run`，按 workflow 名分组，显示各自最新状态 |

和 M1 一样：工具只取数/整理，"这失败意味着什么、该怎么跟团队说"交给 Claude 判断。

---

## 五、MCP Prompts（Step 4，本模块新概念）

**Tools vs Prompts 的区别（面试常问）**：

| | Tools | Prompts |
|---|---|---|
| 谁触发 | Claude **自动**决定调用 | **用户主动**发起的模板 |
| 本质 | 可执行函数（取数/操作） | 给 Claude 的一段结构化引导词（"对话起点"） |
| 写法 | `@mcp.tool()` | `@mcp.prompt()`，**只返回字符串** |

四个 Prompts（标准化团队动作，保证每次流程一致）：

| Prompt | 用途 |
|---|---|
| `analyze_ci_results` | 综合 CI/CD 分析（统一排查口径） |
| `create_deployment_summary` | 写给团队看的友好部署更新 |
| `generate_pr_status_report` | 代码改动 + CI 状态合并报告 |
| `troubleshoot_workflow_failure` | 系统化排错，不走马观花 |

```python
@mcp.prompt()
def analyze_ci_results(event_limit: int = 20) -> str:
    """引导 Claude 按固定步骤分析最近 CI 结果，返回指导字符串。"""
    return (
        f"请先调用 get_recent_actions_events(limit={event_limit}) 取最近事件，"
        "再用 get_workflow_status 汇总各 workflow 最新结论；"
        "把失败的测试/步骤单独列出，给出根因假设和下一步，不要只复述原始 JSON。"
    )
```

> FastMCP 的 prompt 不执行逻辑，就是返回一段给用户/Claude 的引导文本，别在里面做计算。

---

## 六、Cloudflare Tunnel（Step 5，本地测公网 webhook）

本地服务只有 localhost，GitHub 在公网发 webhook 打不进来，用 tunnel 临时暴露：

```bash
# 终端1：起 MCP server
uv run server.py

# 终端2：起 webhook server
python webhook_server.py

# 终端3：把本地 8080 暴露成公网临时 URL
cloudflared tunnel --url http://localhost:8080
```

然后在 GitHub 仓库 Settings → Webhooks 填 tunnel 给出的公网 URL，**payload 路径要带 `/webhook/github`**。

---

## 七、三个扩展练习

1. **自定义 Workflow Prompt**：结合 M1 代码改动工具 + M2 CI 工具，做一个带评审 checklist 的 PR review prompt。
2. **事件过滤**：`get_workflow_status` 支持按 conclusion（success/failure）过滤、按仓库分组、显示距上次运行多久。
3. **通知系统**：新增工具记录哪些事件已"看过"，高亮新失败，建议该通知哪位队友。

---

## 八、常见问题速查

| 现象 | 排查 |
|---|---|
| webhook 收不到事件 | tunnel 是否在跑；GitHub webhook 设置里看 Recent deliveries；payload URL 是否带 `/webhook/github` |
| Prompt 不生效 | 是否用 `@mcp.prompt()` 装饰；它只返回字符串，别写成 tool |
| webhook server 起不来 | 另开终端跑；8080 被占用：`lsof -i :8080` |
| 找不到事件文件 | 首事件到达前文件不存在属正常，工具要能返回空列表 |

---

## 九、面试可讲的一句话

> "我在 MCP Server 里做了双服务分离：webhook server 收 GitHub Actions 事件落盘 JSON，MCP 只读卡文件做分析；新增 CI 查询工具，并用 @mcp.prompt() 把'分析 CI / 部署总结 / PR 报告 / 排错'固化成团队标准流程，本地用 Cloudflare Tunnel 暴露 8080 测公网 webhook。"

---

## 十、新手误区

**误区1：把 HTTP 接收逻辑写进 MCP 工具里**
**实际**：webhook 由独立 server 处理并落盘，MCP 工具只读 JSON，这是本模块的架构要点，也让测试不用真网。

**误区2：Prompts 里写业务计算逻辑**
**实际**：prompt 只返回一段引导字符串，取数和判断还是靠 Tools + Claude。

**误区3：Tools 和 Prompts 混为一谈**
**实际**：Tools 是 Claude 自动调的函数；Prompts 是用户主动触发的模板引导。

**误区4：以为必须真有 GitHub 仓库才能测**
**实际**：手动往 github_events.json 塞几条事件，就能测两个分析工具。

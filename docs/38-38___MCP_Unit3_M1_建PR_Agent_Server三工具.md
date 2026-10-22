# 38 · MCP Unit 3 Module 1：建 PR Agent Server（三个 Tools + 输出治理 + Roots）

## 一句话总述

用 FastMCP 给 Claude Code 写一个 PR Agent Server：只提供三个"取数"工具（分析 git 改动、列 PR 模板、建议模板），**不写死分类规则，把原始 git 数据交给 Claude 自己分析决策**；本模块两个实战硬坑：25000 token 输出上限要截断、用 MCP Roots 解决"git 在错目录跑"。

---

## 一、场景：CodeCraft Studios 的 PR 混乱

团队 PR 标题全是 `stuff` / `more changes` / `fix` / `update things`，评审者要自己翻 47 个文件拼凑"到底改了啥"，评审积压。

**任务**：建一个智能 PR Agent，分析代码改动，自动给出清晰描述并建议合适的 PR 模板。

```
Before：开发者手写模糊 PR  →  评审自己翻 diff 猜意图  →  评审慢、漏问题
After：Claude 调三个工具取原始数据  →  自己总结改动/发现安全问题/列待办/排优先级  →  生成清晰 PR
```

---

## 二、三个 Tools（数据采集 → 资源管理 → 智能决策）

| 工具 | 职责 | 类比 |
|---|---|---|
| `analyze_file_changes` | 跑 git 命令取 diff、改动文件、统计（**数据采集**） | 资料员把原始材料抱给分析师 |
| `get_pr_templates` | 列出可用 PR 模板清单（**资源管理**） | 摆出可选的表格模板 |
| `suggest_template` | 让 Claude 按改动类型推荐最合适模板（**智能决策**） | 分析师自己判断用哪张表 |

### 设计哲学（MCP 核心原则）

> 不在工具里写复杂规则（按文件后缀/正则硬分类），而是**把丰富的原始数据（diff、文件列表、统计）给 Claude，让模型的智能去做决策**。代码因此更简单、更灵活，适配任意代码库和风格。

**类比**：工具是"递原始卷宗的资料员"，不是"替法官下判决的规则引擎"；判断和总结留给模型。

---

## 三、FastMCP 工具写法模板

```python
import json, subprocess
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pr-agent")

@mcp.tool()
async def tool_name(param1: str, param2: bool = True) -> str:
    """工具描述（给 Claude 看的）。

    Args:
        param1: 参数说明（会进工具 schema）
        param2: 带默认值的可选参数
    """
    result = {"key": "value"}
    return json.dumps(result)
```

**错误处理铁律**：即使出错也必须返回合法 JSON，Claude 才能读懂并给用户回应，不要抛裸异常：

```python
try:
    result = subprocess.run(["git", "diff"], capture_output=True, text=True)
    return json.dumps({"output": result.stdout})
except Exception as e:
    return json.dumps({"error": str(e)})
```

> docstring 的描述和 `Args:` 会被 FastMCP 自动生成工具 schema，Claude 靠它理解工具用途——和 Unit 2 Gradio MCP 的要求一致。

---

## 四、实战硬坑 1：25000 token 输出上限（关键）

大仓库单个文件改动上千行，`git diff` 默认带完整上下文，很容易 26 万 token，直接报错：

```
Error: MCP tool response (262521 tokens) exceeds maximum allowed tokens (25000)
```

**解法：工具设计时就带输出限制**——`analyze_file_changes` 加 `max_diff_lines` 智能截断：

```python
@mcp.tool()
async def analyze_file_changes(base_branch: str = "main",
                               include_diff: bool = True,
                               max_diff_lines: int = 500) -> str:
    """分析文件改动，带输出限制。

    Args:
        base_branch: 对比基准分支
        include_diff: 是否带完整 diff
        max_diff_lines: 最多返回的 diff 行数（默认 500）
    """
    result = subprocess.run(
        ["git", "diff", f"{base_branch}...HEAD"],
        capture_output=True, text=True)
    diff_lines = result.stdout.split("\n")

    # 超量就截断并标注
    if len(diff_lines) > max_diff_lines:
        truncated = "\n".join(diff_lines[:max_diff_lines])
        truncated += f"\n\n... 已截断：展示 {max_diff_lines} / 共 {len(diff_lines)} 行 ..."
        diff_output = truncated

    stats = subprocess.run(
        ["git", "diff", "--stat", f"{base_branch}...HEAD"],
        capture_output=True, text=True)

    return json.dumps({
        "stats": stats.stdout,                 # 先给统计摘要
        "total_lines": len(diff_lines),
        "diff": diff_output if include_diff else "设 include_diff=true 查看 diff",
    })
```

**大输出最佳实践**：
1. 分页：把大结果拆页
2. 加过滤选项：只请求特定文件/目录
3. 先给摘要：返回统计，再决定要不要全文
4. 渐进披露（progressive disclosure）：先高层信息，再下钻
5. 合理默认值：默认限额覆盖大多数场景

---

## 五、实战硬坑 2：工作目录（MCP Roots）

MCP Server 默认在**自己的安装目录**跑命令，不是 Claude 当前所在目录——直接 `git diff` 会分析错仓库。

**解法：用 MCP Roots**，Client（Claude Code）会把自己的工作目录作为 root 告诉 Server，工具里取出来当 `cwd`：

```python
@mcp.tool()
async def analyze_file_changes(...):
    context = mcp.get_context()
    roots_result = await context.session.list_roots()
    working_dir = roots_result.roots[0].uri.path   # FileUrl 对象的 .path

    result = subprocess.run(
        ["git", "diff", "--name-status"],
        capture_output=True, text=True,
        cwd=working_dir,          # 在 Claude 的仓库里跑！
    )
```

Claude Code 会自动把当前目录作为 root，这样工具操作的才是用户真正在改的仓库。

---

## 六、环境与测试

### 前置
- Python 3.10+、已装 git、用 `uv` 包管理器

```bash
git clone https://github.com/huggingface/mcp-course.git
cd mcp-course/projects/unit3/build-mcp-server/starter
uv venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv sync --all-extras
```

打开 `server.py` 按 TODO 实现三个工具。

### 三层验证

```bash
# 1. 校验实现
uv run python validate_starter.py

# 2. 单元测试
uv run pytest test_server.py -v

# 3. 接 Claude Code 实测
claude mcp add pr-agent -- uv --directory /absolute/path/to/starter run server.py
claude mcp list
```

然后在一个 git 仓库改几行，问 Claude："分析我的改动并建议一个 PR 模板"，看它是否依次调工具。

---

## 七、本模块可复用模式

| 模式 | 说明 |
|---|---|
| 数据采集工具 | 从外部（git/文件/API）取结构化原始数据给模型 |
| 智能分析 | 模型处理原始数据做决策，工具不写死规则 |
| 输出治理 | 截断/摘要/分页，守住 token 上限 |
| 结构化错误 | 错误也返回 JSON，不抛裸异常 |
| 测试策略 | 校验脚本 + pytest + 真实 Client 实测 |

---

## 八、面试可讲的一句话

> "我用 FastMCP 写过一个 PR Agent：只提供取数工具（git diff 分析、列模板、建议模板），把原始数据交给 Claude 自己总结和选型，不在工具里写死规则；并处理了 25000 token 上限截断和用 MCP Roots 取 Claude 工作目录两个真实工程问题。"

---

## 九、新手误区

**误区1：在工具里写规则判断"这是 Feature 还是 Bugfix"**
**实际**：那是传统规则系统的思路；MCP 哲学是给原始数据让 Claude 判断，工具只负责准确取数。

**误区2：工具出错就 `raise` 或返回字符串报错**
**实际**：必须返回合法 JSON（含 `error` 字段），否则 Claude 读不懂、无法回应。

**误区3：直接 `git diff` 就能用，不用管目录**
**实际**：Server 在自己安装目录执行，必须通过 Roots 拿 Claude 的 cwd 并传给 `subprocess cwd=`，否则分析错仓库。

**误区4：diff 全量返回最保险**
**实际**：全量必爆 25000 token，要默认截断、先给 stat 摘要、按需取全文。

---

## 十、延伸阅读

- MCP 官方文档：modelcontextprotocol.io
- FastMCP 入门：modelcontextprotocol.io/quickstart/server
- 课程 solution：`projects/unit3/build-mcp-server/solution/`（多种实现，没有唯一正解）

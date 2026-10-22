# 37 · MCP Unit 3 导论：PR Agent Workflow Server（给 Claude Code 装研发工作流）

## 一句话总述

Unit 3 从"装单个工具"升级到"装一套团队研发工作流"：用 MCP 给 Claude Code 写一个 **PR Agent Workflow Server**，把「选 PR 模板 → 监控 GitHub Actions → Slack 通知全队」这条日常流水线自动化，重点实战 MCP 的 **Tools** 和 **Prompts** 两个原语。

---

## 一、Unit 2 vs Unit 3：从单点工具到工作流

| | Unit 2（已学完） | Unit 3（本篇） |
|---|---|---|
| 做的事 | 给 Agent 装一个专用工具（情感分析） | 给 Claude Code 装一条团队研发流水线 |
| 场景 | 单功能：分析一段话的情绪 | 多环节串联：PR → CI/CD → 通知 |
| 重点原语 | Tools + Client 连接 | **Tools + Prompts**，并把原语组合起来 |
| 服务对象 | 个人问答 | 团队协作（GitHub / Actions / Slack） |

**类比**：Unit 2 是给扳手配一个标准接口，谁都能插上去拧螺丝；Unit 3 是把"选模板 → 检查 → 汇报"整条装配线做成一个 MCP Server，让 Claude Code 变成懂你们团队规矩的研发助手。

---

## 二、要建的 Server：三个能力

```
┌─────────────────────────── Claude Code（MCP Client）───────────────────────────┐
│                                                                                  │
│  ① Tools：按改动文件自动建议合适的 PR 模板                                        │
│  ② Prompts：标准化监控 GitHub Actions，输出格式化的 CI/CD 摘要                    │
│  ③ 集成：部署成功/失败自动发 Slack 通知（Tools + Prompts 协同）                  │
└───────────────▲───────────────────────────────▲──────────────────┬─────────────┘
                │ MCP 协议                        │ webhook          │
        ┌───────┴───────┐                ┌────────┴────────┐   ┌─────┴──────┐
        │ 本地/隧道 Server │◄── Cloudflare Tunnel │ GitHub Actions │   │  Slack     │
        └───────────────┘   （公网收 webhook） │  (CI/CD 运行)   │   │  webhook   │
                                            └─────────────────┘   └────────────┘
```

### Before / After（课程给的真实团队痛点）

| 环节 | Before（手动） | After（Claude Code 连 Server 后） |
|---|---|---|
| 建 PR | 自己翻文档挑模板 | 按改动文件自动建议对的 PR 模板 |
| 看 CI/CD | 手动等 Actions、点开看结果 | 自动跟踪 Actions run，给出格式化摘要 |
| 通知队友 | 自己记得去 Slack 说成功/失败 | 部署成功/失败自动发 Slack |
| 评审引导 | 凭记忆走团队流程 | 按 Actions 结果引导走对应评审流程 |

---

## 三、三个 MCP 原语在 Unit 3 怎么用

| 原语 | Unit 3 中的落地 |
|---|---|
| **Tools**（可调用函数） | Module 1：分析改动文件、建议 PR 模板的函数 |
| **Prompts**（标准化模板/工作流） | Module 2：固定的 CI/CD 监控流程，保证团队动作一致 |
| **Resources**（已读，不重点） | Unit 1 讲过，Unit 3 只在集成里顺带用到 |

> 注意：课程标题说"all three primitives"，但 Unit 3 动手重点是 **Tools + Prompts**；Resources 是第一单元已学的基础，这里不重新展开。

---

## 四、三个模块怎么走

| 模块 | 内容 | 产出 |
|---|---|---|
| **Module 1：建 MCP Server** | 搭基础 Server，写"按文件建议 PR 模板"的 Tool | 一个能分析文件、选模板的最小 Server |
| **Module 2：GitHub Actions 集成** | 用 Cloudflare Tunnel 暴露本地端口收 webhook，用 Prompts 标准化监控 CI/CD | 能跟踪 Actions run 并出摘要 |
| **Module 3：Slack 通知** | 集成所有原语，部署结果自动通知团队 | 完整自动化工作流 |

---

## 五、前置条件（开始前自检）

- [ ] 完成 Unit 1、Unit 2
- [ ] 懂 GitHub Actions 和 webhook 基本概念
- [ ] 有一个可测试的 GitHub 仓库（个人测试 repo 即可）
- [ ] 有一个能建 webhook 的 Slack 工作区
- [ ] **装 Claude Code**：npm 安装 → 进到项目目录 → 跑 `claude` → 通过 console.anthropic.com 登录

> Claude Code 安装/认证出问题，看官方 troubleshooting：docs.anthropic.com/en/docs/claude-code/troubleshooting

---

## 六、学习目标（学完应能讲）

1. 用实战掌握 MCP 的 Tools 与 Prompts 两个原语
2. 写出结构清晰、带错误处理的功能型 MCP Server
3. 用 Cloudflare Tunnel 收 GitHub Actions webhook 处理 CI/CD 事件
4. 为 LLM 研发团队设计专用工作流（HF Hub 场景）
5. 经 MCP 把 GitHub、Slack、HF Hub 多系统连起来
6. 让 Claude Code 理解你们团队的专属研发流程

---

## 七、面试可讲的一句话

> "我给 Claude Code 写过一个团队研发工作流 MCP Server：用 Tools 按改动文件建议 PR 模板、用 Prompts 标准化监控 GitHub Actions，并通过 webhook 把部署结果自动发到 Slack，理解了 MCP 从单点工具走向多系统工作流集成的思路。"

---

## 八、新手误区

**误区1：Unit 3 又要从零讲一遍 MCP 协议**
**实际**：协议基础 Unit 1/2 已学，Unit 3 直接上 Tools/Prompts 的工程组合，重点是"多系统串联"。

**误区2：Cloudflare Tunnel 是可选炫技**
**实际**：本地 Server 默认只有 localhost，GitHub Actions 的 webhook 从公网打不进来，Tunnel 是让 webhook 能到达本地的必要通道。

**误区3：Slack 通知只是发条消息**
**实际**：它是 Tools（查结果）+ Prompts（决定发什么、怎么发）协同的集成样例，用来演示原语组合。

**误区4：没有现成团队仓库就做不了**
**实际**：课程允许用个人测试 repo + 测试 Slack webhook，重点跑通链路。

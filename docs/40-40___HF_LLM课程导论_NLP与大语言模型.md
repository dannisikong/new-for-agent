# 40 · Hugging Face LLM Course 导论：NLP 与大语言模型（课程地图）

> 来源：https://huggingface.co/learn/llm-course/chapter1/1
> 性质：LLM/NLP 基础导论（非 MCP），归入 Agent 学习知识库打底。

## 一句话总述

Hugging Face 官方免费课程，从 Transformer 原理 → Transformers/Datasets/Tokenizers 工具库 → 经典 NLP 任务与 LLM 微调/推理，帮你用 `🤗 Transformers` 生态把一个模型从"会调 pipeline"走到"能在 Hub 上分享 demo"。

---

## 一、NLP vs LLM：先分清两个概念

| | NLP（自然语言处理） | LLM（大语言模型） |
|---|---|---|
| 层级 | 更**大**的领域 | NLP 的一个**强大子集** |
| 关注点 | 让计算机理解、解释、生成人类语言 | 超大规模模型 |
| 典型任务 | 情感分析、命名实体识别、机器翻译 | 极少任务特定训练，就能泛化到大量语言任务 |
| 代表 | 朴素贝叶斯、LSTM、传统 Transformer | Llama / GPT / Claude 系列 |

> 关键认知：LLM 是最新进展，但课程强调**先懂传统 NLP 基础**才能用好 LLM——情感分析、NER 这些"小任务"仍是理解模型行为的地基。

---

## 二、课程用什么库

- **🤗 Transformers**：模型主干。
- **🤗 Datasets**：数据集加载与处理。
- **🤗 Tokenizers**：文本切词。
- **🤗 Accelerate**：大模型训练/推理加速。
- **Hugging Face Hub**：模型与 demo 的分享枢纽。
- 同时也覆盖 HF 生态之外的优秀开源库。
- 完全免费、无广告；代码在 `huggingface/notebooks`，可一键 Open in Colab / SageMaker Studio Lab。

---

## 三、课程地图（12 章）

```
Ch1–4   入门：Transformer 模型 / 用 Transformers / 微调预训练模型 / 分享模型与 tokenizer
Ch5–8   深入：Datasets 库 / Tokenizers 库 / 主流 NLP 任务 / 怎么求助
Ch9     展示：在 Hub 上构建并分享模型 demos
Ch10–12 高级：微调 / 高质量数据策划 / 构建推理模型
```

- 学完 Ch1–4：会用 Hub 上的模型、在自己数据集上微调、再分享回 Hub。
- 学完 Ch5–8：能独立处理常见语言任务。
- 学完 Ch9：能把 Transformers 应用做成 demo 展示给别人。
- Ch10–12：进入高级 LLM 话题（推理模型是重点）。

---

## 四、前置要求

- ✅ 要求：**熟练 Python**。
- 👍 建议先学一门入门深度学习课（fast.ai《Practical Deep Learning for Coders》或 DeepLearning.AI 课程）。
- 不要求先会 PyTorch / TensorFlow，但会一点更顺。
- 学完本课后推荐 DeepLearning.AI 的 NLP 专项课，补朴素贝叶斯、LSTM 等传统模型。

---

## 五、FAQ 要点

| 问题 | 答案 |
|---|---|
| 有证书吗 | 暂无，正在做 HF 生态认证 |
| 花多久 | 每章约 1 周、每周 6–8 小时，可按自己节奏 |
| 提问 | 页面顶部 "Ask a question" 按钮跳 HF 论坛对应板块 |
| 代码在哪 | `huggingface/notebooks` repo，可 Colab/Studio Lab 运行 |
| 怎么贡献 | 在 `course` repo 提 issue（错别字/ bug）或参与翻译 |
| 许可 | Apache 2.0，需署名 + 链许可；可商用 |
| 中文 | 有简体中文翻译（社区贡献），YouTube 视频可开字幕 |

---

## 六、第 1 章你会学到

1. 用 `pipeline()` 函数解决文本生成、分类等 NLP 任务；
2. Transformer 架构原理；
3. 区分 **encoder / decoder / encoder-decoder** 三种架构及各自适用场景。

---

## 七、面试可讲的一句话

> "我系统过了一遍 HF LLM 课程：先用 pipeline 跑通任务，再理解 Transformer 三种架构（encoder 适合理解类、decoder 适合生成类、encoder-decoder 适合翻译类），并在 Datasets/Tokenizers 之上做过微调与 Hub 分享。"

---

## 八、新手误区

**误区1：跳过 NLP 基础直接冲 LLM**
**实际**：课程明确要求先懂传统 NLP，否则只懂调 API、不懂模型为什么这样表现。

**误区2：以为要先精通 PyTorch 才能学**
**实际**：课程不要求先会框架，会 Python 即可入门；框架知识边做边补。

**误区3：把 LLM 和 NLP 对立**
**实际**：LLM 是 NLP 的子集/最新进展，不是替代品；情感分析、NER 这类任务仍大量在用传统模型。

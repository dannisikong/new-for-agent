# 42 · HF LLM 课程 1.3：Transformers 能做什么——pipeline() 全实操

> 来源：https://huggingface.co/learn/llm-course/chapter1/3

## 一句话总述

`pipeline()` 是 🤗 Transformers 最基础的对象，它把**模型 + 预处理 + 后处理**打包成一行调用：你丢文本进去，它直接给可读结果；本节用它跑通情感分析、零样本分类、文本生成、完形填空、NER、问答、摘要、翻译，以及图像/音频任务。

---

## 一、pipeline 的本质：三步流水线

```
你的原始文本
   │  ① 预处理：转成模型能懂的张量/token
   ▼
   ② 喂给模型前向推理
   ▼
   ③ 后处理：把模型输出整理成人能读的结果
```

- 默认会自动选一个为该任务微调好的英文预训练模型，首次创建时下载并**缓存**，之后不再重复下载。
- 模型与 Hub：Model Hub 有百万级预训练模型可下载，也能上传自己的；Hub 不只有 Transformer 模型。

```python
from transformers import pipeline
classifier = pipeline("sentiment-analysis")
classifier("I've been waiting for a HuggingFace course my whole life.")
# [{'label': 'POSITIVE', 'score': 0.9598...}]
# 也支持一次传一个句子列表批量跑
```

---

## 二、可用 pipeline 全景（按模态）

| 模态 | pipeline 任务 | 作用 |
|---|---|---|
| 文本 | `text-generation` | 从 prompt 续写 |
| 文本 | `text-classification` | 分到预定义类别 |
| 文本 | `summarization` | 长文缩成短文、保留要点 |
| 文本 | `translation` | 语言互译 |
| 文本 | `zero-shot-classification` | 不训练就按你给的标签分类 |
| 文本 | `feature-extraction` | 抽文本向量表示 |
| 图像 | `image-to-text` | 给图像生成文字描述 |
| 图像 | `image-classification` | 识别图中物体 |
| 图像 | `object-detection` | 在图中定位并框出物体 |
| 音频 | `automatic-speech-recognition` | 语音转文字（ASR） |
| 音频 | `audio-classification` | 给音频分类 |
| 音频 | `text-to-speech` | 文字转语音 |
| 多模态 | `image-text-to-text` | 根据文字 prompt 回答关于图像的问题 |

---

## 三、逐个任务详解（含关键参数）

### 1. Zero-shot 零样本分类
不依赖模型自带标签，你自己传 `candidate_labels`，模型直接给每个标签打分——真实项目里没标注数据时特别好用。

```python
classifier = pipeline("zero-shot-classification")
classifier("This is a course about the Transformers library",
          candidate_labels=["education", "politics", "business"])
# labels 按概率排序: education(0.84) > business(0.11) > politics(0.04)
```
叫"zero-shot"就是**不用在你的数据上微调**。

### 2. Text generation 文本生成
给 prompt 让模型自动补全，类似手机预测输入；**有随机性**，每次结果可能不同。

```python
generator = pipeline("text-generation")
generator("In this course, we will teach you how to")
# 参数：num_return_sequences=生成几条；max_length=总长度
```

### 3. 指定 Hub 上的任意模型
默认模型只是缺省值，可以用 `model=` 指定任何 Hub 模型（如 `HuggingFaceTB/SmolLM2-360M`），还能按语言标签筛多语模型。Hub 页面的 widget 可在线先试再下载；背后是 Inference Providers（可付费用于生产）。

### 4. Fill-mask 完形填空
把句子里的 `<mask>` 填回去，`top_k` 控制返回几个候选。

```python
unmasker = pipeline("fill-mask")
unmasker("This course will teach you all about <mask> models.", top_k=2)
# -> "mathematical models"(0.20) / "computational models"(0.04)
```
注意：不同模型的 mask token 可能不是 `<mask>`，要去 widget 里确认。

### 5. NER 命名实体识别
找出句中的人/地点/组织。`grouped_entities=True` 会把被切分的同实体词合并（如 "Hugging"+"Face" 合成一个 ORG）。

```python
ner = pipeline("ner", grouped_entities=True)
ner("My name is Sylvain and I work at Hugging Face in Brooklyn.")
# Sylvain=PER, Hugging Face=ORG, Brooklyn=LOC
```
背后细节：预处理会把词切成子词（Sylvain → S/##yl/##va/##in），后处理再拼回整实体。

### 6. Question answering 问答
**从给定 context 里抽取答案**，不是凭空生成——返回答案在原文中的 start/end 位置。

```python
question_answerer = pipeline("question-answering")
question_answerer(question="Where do I work?",
                 context="My name is Sylvain ... at Hugging Face in Brooklyn")
# answer: "Hugging Face" (score 0.64)
```

### 7. Summarization 摘要
压缩长文保留要点，可用 `max_length` / `min_length` 控制长度。

### 8. Translation 翻译
最省事是在 Hub 直接挑模型：`pipeline("translation", model="Helsinki-NLP/opus-mt-fr-en")`。

### 9. 图像 / 音频
```python
pipeline("image-classification", model="google/vit-base-patch16-224")      # ViT 分类图
pipeline("automatic-speech-recognition", model="openai/whisper-large-v3") # Whisper 转写
```

---

## 四、多源数据融合（Agent 视角重点）

Transformer 的一个强应用是**跨模态/跨库整合**：
1. 跨多个数据库或仓库检索；
2. 合并不同格式（文本、图像、音频）的信息；
3. 形成统一视图——例如同时从音频文件和文字描述里拼出一个连贯回答。

> 这正是 RAG / 多模态 Agent 的雏形：不是单模型答题，而是跨源取数 + 融合。

---

## 五、面试可讲的一句话

> "我用 HF pipeline 一行调用跑通过 NLP 全任务：它内部固定走预处理→模型→后处理三步；零样本分类不用微调就能自定义标签，NER 靠 grouped_entities 把子词拼回实体，QA 是从上下文抽取而非生成；换模型只需在 Hub 选一个用 model= 传入。"

---

## 六、新手误区

**误区1：pipeline("sentiment-analysis") 里那个模型是写死的**
**实际**：只是默认选了个英文情感模型，`model=` 可换成 Hub 任意同任务模型。

**误区2：QA 是模型自己编答案**
**实际**：这节的 extractive QA 是从 context 里抽原文片段，会给 start/end；自由生成答案是另一类生成式任务。

**误区3：生成结果每次都一样**
**实际**：text-generation 有随机性，复现要固定 seed / 调温度参数。

**误区4：所有 fill-mask 模型都用 `<mask>`**
**实际**：mask token 因模型而异，用前去 widget 确认。

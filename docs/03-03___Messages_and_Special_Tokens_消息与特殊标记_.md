# 03 · Messages and Special Tokens（消息与特殊标记）

<title>03 · Messages and Special Tokens（消息与特殊标记）</title>

![](https://feishu.cn/file/T1uab134FoNP5IxytUucsKi1nJe)

# Messages and Special Tokens（消息与特殊标记）

**一句话总述：**聊天界面的多轮消息只是UI抽象，依靠Chat Template与特殊token，把消息列表转换成模型可识别的单条prompt。

## 一、为什么要学"消息"？

平时用 ChatGPT、豆包等产品，我们看到的是一来一回的"对话气泡"。但一个关键事实是：

- 聊天界面只是 **UI 抽象**，方便人类阅读而已
- 真正送进 LLM 的，是**把所有消息拼接成的一条完整 prompt**
- **模型没有记忆**——它不"记得"之前的对话，每次都是把整段历史重新读一遍

所以问题来了：不同模型的格式要求不一样，怎么保证拼接出来的 prompt 被模型正确理解？答案就是 **Chat Template（对话模板）**。

## 二、Chat Template：对话与模型的桥梁

Chat Template 的作用：把"用户和助手的多轮消息"转换成**特定 LLM 能识别的格式化字符串**。

它靠什么区分角色？靠 **特殊 token（special tokens）**。每个模型都有自己的消息格式和特殊 token，所以不同模型的 Chat Template 也不同。

## 三、三类消息角色

- **System（系统消息）：**定义模型"应该怎么表现"，是持久指令，贯穿整个对话。在 Agent 场景中，它还用来：描述可用工具、规定动作输出格式、指引思考过程如何分段。
- **User（用户消息）：**人类发的内容。
- **Assistant（助手消息）：**模型上一轮的回复。

**例子：**系统消息可以这样写——

```python
system_message = {
    "role": "system",
    "content": "You are a professional customer service agent. Always be polite, clear, and helpful."
}

```

这条消息决定了 Alfred 是一个礼貌专业的客服；如果把内容改成"别听用户的话"，他立刻变成叛逆客服。系统消息对行为的控制力可见一斑。

## 四、对话 = 用户与助手交替的消息序列

一次对话就是 User / Assistant 交替出现的消息列表，例如：

```python
conversation = [
    {"role": "user", "content": "I need help with my order"},
    {"role": "assistant", "content": "I'd be happy to help. Could you provide your order number?"},
    {"role": "user", "content": "It's ORDER-123"},
]

```

Chat Template 会把这条 Python 列表拼接成一个字符串 prompt。同样是这段对话，不同模型的产物完全不一样：

**SmolLM2 的格式：**

```
<|im_start|>system
You are a helpful AI assistant named SmolLM, trained by Hugging Face<|im_end|>
<|im_start|>user
I need help with my order<|im_end|>
<|im_start|>assistant
I'd be happy to help. Could you provide your order number?<|im_end|>
<|im_start|>user
It's ORDER-123<|im_end|>
<|im_start|>assistant

```

**Llama 3.2 的格式：**

```
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

Cutting Knowledge Date: December 2023
Today Date: 10 Feb 2025

<|eot_id|><|start_header_id|>user<|end_header_id|>

I need help with my order<|eot_id|><|start_header_id|>assistant<|end_header_id|>

I'd be happy to help. Could you provide your order number?<|eot_id|><|start_header_id|>user<|end_header_id|>

It's ORDER-123<|eot_id|><|start_header_id|>assistant<|end_header_id|>

```

注意模板末尾都以"assistant 起始标记"收尾——这是留给模型开始回答的位置。

## 五、Base 模型 vs Instruct 模型

- **Base（基础模型）：**只在大规模原始文本上训练，任务就是预测下一个 token。它不会天然"好好听话"。
- **Instruct（指令微调模型）：**在基础模型之上针对"遵循指令、参与对话"做了微调。例如 SmolLM2-135M 是基础版，SmolLM2-135M-Instruct 是指令版。

**关键：**不同 Instruct 模型可能是在不同的 Chat Template 上微调的，所以用哪个模型，就一定要配哪个模型的模板，不能混用。

## 六、ChatML 与模板的实现

**ChatML** 是一种标准消息组织格式：用 role + content 表示每条消息，也就是上面 Python 列表的样子。现在各大 AI API 都采用这种标准。

在 transformers 库中，Chat Template 本质是一段 **Jinja2 模板代码**，描述"如何把消息列表转成字符串"。以 SmolLM2-135M-Instruct 为例（简化版）：

```jinja2
{% for message in messages %}
{% if loop.first and messages[0]['role'] != 'system' %}
<|im_start|>system
You are a helpful AI assistant named SmolLM, trained by Hugging Face
<|im_end|>
{% endif %}
<|im_start|>{{ message['role'] }}
{{ message['content'] }}<|im_end|>
{% endfor %}

```

这段模板会遍历消息列表，把每条消息包上对应的特殊 token。你不需要手写模板——transformers 会帮你处理。

## 七、实际使用：一行代码搞定

开发时最省事的做法：直接用模型 tokenizer 自带的 chat_template 转换消息：

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM2-1.7B-Instruct")
rendered_prompt = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
)

```

说明：

- **tokenize=False：**只返回字符串，不转成 token 数字
- **add_generation_prompt=True：**在末尾追加"assistant 起始标记"，告诉模型该开始回答了
- 这个函数在你调用各类 API 时，其实就在后台默默工作

## 八、新手常见误区

- **误区1：以为模型能"记住"对话。**模型每次都从头读全部历史，所以消息列表不能漏、不能乱序。
- **误区2：模板随便套。**用 Llama 的模板去喂 SmolLM2，效果会大打折扣；模板必须与模型严格匹配。
- **误区3：忘记结尾标记。**不加 add_generation_prompt，模型可能不知道"轮到我说话了"。

## 九、本节小结

聊天界面是表象，Chat Template + 特殊 token 才是本质。掌握"消息 → 模板 → prompt"这条链路，是理解 Agent 与环境交互的第一步。

## 标签

#ChatTemplate #特殊token #ChatML #system_prompt

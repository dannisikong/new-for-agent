"""
tool_policy.py —— 参数级最小权限校验（P0 安全）
=================================================
工具名白名单只解决「模型编造不存在的工具」；本模块再拦一层：
即使工具名合法，也校验它传入的参数是否落在允许范围内，
防止模型把工具当成执行任意命令 / 读本地文件 / 越权访问的入口。

设计原则（最小权限）：
- 每个工具只声明自己真正需要的参数类型、长度上限和允许字符；
- 命中 shell 命令符、本地路径穿越、超长输入 → 拒绝执行，
  返回可读原因让模型纠正重试，而不是直接抛异常；
- 校验失败绝不放行，宁可拒答也不执行越权参数（fail-closed）。
"""

import re

# 跨工具通用危险字符：shell 命令分隔 / 重定向 / 命令替换 / 换行
_DANGEROUS_CHARS = re.compile(r"[;|&$`<>]|\n|\r")
# 本地路径 / 穿越（防止模型让工具去读服务器文件系统）
_LOCAL_PATH = re.compile(r"(/home/|/etc/|/root/|C:\\|\\\\|\.\./|\./)", re.IGNORECASE)

# 每个工具的参数规则：{参数名: (最大长度, 允许字符正则或 None=不限, 说明)}
# 说明会拼进拒绝消息，指导模型怎么改。
_POLICY: dict[str, dict[str, dict]] = {
    "guest_info_retriever": {
        "query": {"max_len": 200, "allowed": None,
                  "hint": "宾客姓名或关系，纯文本，不要带路径或命令"},
    },
    "web_search": {
        "query": {"max_len": 300, "allowed": None,
                  "hint": "要搜索的关键词短语，不要传本地文件路径或 shell 命令"},
    },
    "weather_info": {
        "location": {"max_len": 100,
                     "allowed": re.compile(r"^[\u4e00-\u9fa5A-Za-z0-9\s.\-]+$"),
                     "hint": "城市/地点名称（中英文均可），仅文字，不要带命令符"},
    },
    "hub_stats": {
        "author": {"max_len": 64,
                   "allowed": re.compile(r"^[A-Za-z0-9_\-]+$"),
                   "hint": "Hugging Face 用户名/组织名，仅字母数字下划线连字符"},
    },
    "knowledge_search": {
        "query": {"max_len": 300, "allowed": None,
                  "hint": "知识库问题/关键词，纯文本，不要带命令或路径"},
    },
}


def validate(tool_name: str, args: dict) -> tuple[bool, str]:
    """校验某个工具的调用参数。

    返回 (是否放行, 拒绝原因)。放行时原因是空字符串。
    未登记的工具不额外拦截（白名单已在上游校验），交由工具自身处理。
    """
    rules = _POLICY.get(tool_name)
    if not rules:
        return True, ""

    if not isinstance(args, dict):
        return False, f"工具「{tool_name}」的参数必须是对象（JSON），收到：{type(args).__name__}"

    for param, rule in rules.items():
        value = args.get(param)
        # 必填参数缺失
        if value is None:
            return False, f"工具「{tool_name}」缺少必填参数「{param}」（{rule['hint']}）"
        if not isinstance(value, str):
            return False, f"参数「{param}」必须是文本，收到 {type(value).__name__}，请改用字符串"

        text = value.strip()
        if not text:
            return False, f"参数「{param}」不能为空（{rule['hint']}）"
        if len(text) > rule["max_len"]:
            return False, f"参数「{param}」超长（{len(text)} > {rule['max_len']} 字），请精简后重试"
        if _DANGEROUS_CHARS.search(text):
            return False, f"参数「{param}」包含命令/重定向等危险字符，已拒绝（{rule['hint']}）"
        if _LOCAL_PATH.search(text):
            return False, f"参数「{param}」看起来像本地路径，本工具不访问服务器文件系统（{rule['hint']}）"
        if rule["allowed"] and not rule["allowed"].match(text):
            return False, f"参数「{param}」含不允许的字符（{rule['hint']}）"

    return True, ""

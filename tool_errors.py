"""
tool_errors.py —— 工具错误分类与「可纠正」提示（P2）
=====================================================
工具执行失败时，裸抛 "ExceptionType: msg" 对模型没有指导意义，
模型只能盲目重试或编造结果。本模块把异常归类，并给出模型可执行的
下一步动作（改参数格式 / 换关键词 / 退避重试一次 / 换工具 / 告知用户）。

分类与 tools.py 的 _classify_error 保持同一套状态码口径，但职责独立：
tools.py 决定「要不要重试、退避多久」，本模块决定「告诉模型该怎么纠正」。
"""

from typing import Optional


# 错误类别 → 给模型的可操作建议（下一步动作）
_ADVICE: dict[str, str] = {
    "auth": "这是凭证/权限问题，盲目重试无用：请检查所用服务的 API Key 是否有效、"
            "该工具是否被授权；若仍失败，明确告知用户需要检查凭证，不要编造结果。",
    "not_found": "目标资源不存在：请更换查询关键词/对象名后重试一次；"
                 "若仍失败就改用其他工具或如实告知未找到，不要重复同一调用。",
    "rate_limit": "触发限流：请等待片刻后只重试一次，不要连续密集调用；"
                  "若多次仍被限流，改用其他工具完成任务。",
    "server": "服务端临时故障（5xx）：可稍后重试一次；若持续失败，"
              "换用其他工具或如实告知用户当前服务不稳定。",
    "network": "网络连接/超时问题：检查网络后重试一次；仍失败则换工具或告知用户，"
               "不要反复空转重试。",
    "invalid_args": "传入参数格式不符合工具要求：请对照工具说明修正参数类型/取值后重试，"
                    "不要换一个无关工具硬凑。",
    "unknown": "未归类错误：简要说明现象，可换用其他工具完成；"
               "若影响结论，如实告知用户，不要编造。",
}

# 类别中文名（审计/日志用）
_CN = {
    "auth": "认证/权限失败(401/403)",
    "not_found": "资源不存在(404)",
    "rate_limit": "限流(429)",
    "server": "服务端错误(5xx)",
    "network": "网络/超时",
    "invalid_args": "参数格式错误",
    "unknown": "未知错误",
}


def _status_code(exc: BaseException) -> Optional[int]:
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    return getattr(resp, "status_code", None)


def classify_tool_error(exc: BaseException) -> str:
    """把异常归到一个类别 key，供建议与日志使用。"""
    code = _status_code(exc)
    if code in (401, 403):
        return "auth"
    if code == 404:
        return "not_found"
    if code == 429:
        return "rate_limit"
    if code is not None and 500 <= code < 600:
        return "server"
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return "network"
    # 工具内部主动抛的参数类错误
    if isinstance(exc, (TypeError, ValueError)):
        return "invalid_args"
    return "unknown"


def safe_summary(exc: BaseException, limit: int = 200) -> str:
    """提取安全的错误摘要：只取异常类型与首条消息，不带堆栈。"""
    msg = str(exc) or exc.__class__.__name__
    msg = msg.strip().splitlines()[0]
    if len(msg) > limit:
        msg = msg[:limit] + "…"
    return f"{exc.__class__.__name__}: {msg}"


def corrective_tool_message(tool_name: str, exc: BaseException) -> str:
    """组装给模型的「可纠正」工具失败提示。

    结构：发生了什么（类别）→ 建议的下一步动作，明确不鼓励盲目重试/编造。
    """
    category = classify_tool_error(exc)
    summary = safe_summary(exc)
    advice = _ADVICE[category]
    return (
        f"⚠️ 工具「{tool_name}」执行失败（{_CN[category]}）：{summary}\n"
        f"下一步：{advice}"
    )

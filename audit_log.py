"""
audit_log.py —— 本地结构化审计日志（P0 可观测性）
====================================================
每一次工具调用 / 被拒 / 报错 / 整轮问答，都追加一条 JSONL 记录到
logs/agent_audit.jsonl。与 LangSmith（线上 trace）、飞书表格（业务汇总）互补：
这里是一份不依赖外部服务、可本地复盘、可离线排查的最小审计轨。

设计原则：
- 写日志失败绝不影响主流程（try/except 全吞）；
- 每条一行 JSON，字段固定，便于后续 grep / jq / 接 BI；
- 只记录参数与结果摘要（截断），不落完整敏感正文。
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "agent_audit.jsonl")
_TZ = timezone(timedelta(hours=8))  # Asia/Shanghai


def _preview(text: str, limit: int = 200) -> str:
    """结果/参数摘要截断，避免单条日志过大。"""
    if text is None:
        return ""
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "…"


def new_trace_id() -> str:
    """生成一次问答的 trace 标识，贯穿这一轮的所有 span。"""
    return "tr-" + uuid.uuid4().hex[:8]


def log_event(event: str, *, tool: str | None = None, thread_id: str | None = None,
              args: dict | None = None, ok: bool = True, error: str | None = None,
              result_preview: str | None = None, extra: dict | None = None,
              trace_id: str | None = None, span: str | None = None,
              duration_ms: float | None = None, tokens: int | None = None,
              cost_usd: float | None = None) -> None:
    """追加一条审计记录。event 取值：
    - round：一整轮问答汇总（问题/评分/重写次数/是否降级/耗时）
    - tool_call：工具成功执行
    - tool_denied：参数越权被最小权限策略拒绝
    - tool_error：工具执行异常
    - human_review：人在回路确认节点

    trace 可观测性字段（P3，全部可选、向后兼容）：
    - trace_id：一次问答的串联标识（用 new_trace_id() 生成）；
    - span：这一步叫什么（如 rewrite / retrieve / tool:web_search / answer）；
    - duration_ms：该步耗时；tokens / cost_usd：该步用量与成本。
    """
    try:
        record = {
            "ts": datetime.now(_TZ).isoformat(timespec="seconds"),
            "event": event,
            "ok": ok,
            "thread_id": thread_id or "default",
            "tool": tool,
            "trace_id": trace_id or "no-trace",
            "span": span,
            "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
            "tokens": tokens,
            "cost_usd": round(cost_usd, 5) if cost_usd is not None else None,
            "args": {k: _preview(v) for k, v in (args or {}).items()},
            "error": _preview(error, 300) if error else None,
            "result_preview": _preview(result_preview) if result_preview else None,
        }
        if extra:
            record.update(extra)
        os.makedirs(_LOG_DIR, exist_ok=True)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 审计失败不影响主流程


def read_trace(trace_id: str) -> list[dict]:
    """拉出某一次 trace 的全部 span（按文件顺序即时间顺序）。"""
    try:
        return [r for r in read_recent(500) if r.get("trace_id") == trace_id]
    except Exception:
        return []


def summarize_trace(trace_id: str) -> dict:
    """汇总一次 trace：各步耗时、总耗时、总成本、是否有失败。"""
    spans = read_trace(trace_id)
    total_ms = 0.0
    total_cost = 0.0
    failed = 0
    for s in spans:
        d = s.get("duration_ms")
        if isinstance(d, (int, float)):
            total_ms += d
        c = s.get("cost_usd")
        if isinstance(c, (int, float)):
            total_cost += c
        if s.get("ok") is False:
            failed += 1
    return {
        "trace_id": trace_id,
        "span_count": len(spans),
        "total_duration_ms": round(total_ms, 1),
        "total_cost_usd": round(total_cost, 5),
        "failed_spans": failed,
    }


def read_recent(n: int = 50) -> list[dict]:
    """读取最近 n 条审计记录（供调试/UI 展示），文件不存在返回空列表。"""
    try:
        if not os.path.exists(_LOG_FILE):
            return []
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        records = []
        for line in lines[-n:]:
            line = line.strip()
            if line:
                records.append(json.loads(line))
        return records
    except Exception:
        return []

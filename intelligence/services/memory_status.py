"""记忆退出机制（slice 5）：append-only 台账的状态覆盖行——归档/撤销不改历史。

背景（补哪块拼图）：
    记忆的「入口状态机」已有 `memory_gate.py`（fail-closed 晋升门：只有已回检的
    checkpoint 教训或 provenance 绑定的用户显式纠偏才进 durable 层）。缺的是
    **出口**：judgments/corrections 是 append-only JSONL，错记/过时的记录没有
    退出机制，只能人工删行——删行会破坏台账的可回放性。

设计（与 sector snapshot 分代、事件日志派生阶段同一个思想）：
    - **不改历史行**。归档/撤销/恢复都是**追加**一条状态行：
        {"record_type": "memory_status", "target_ts": "<原记录 ts>",
         "status": "archived|rejected|reinstated", "reason": "...", "ts": "..."}
    - 同一 target_ts 以**最新**状态行为准（可归档后再恢复，全程留痕）。
    - loader 侧过滤：archived/rejected 的记录不再被召回；台账里没有状态行时
      行为逐字节不变（棘轮：存量不迁移，只约束新增能力）。
    - 状态行本身永不作为记忆内容被召回。

技术选型说明：另一条路是给原记录就地加 status 字段（改历史行）。不选它：
    ① append-only 文件被两处以上并发写时就地改行会互相踩；② 改行丢失
    「谁在何时以何理由归档」的审计链；③ 可回放性被破坏（重放到某时刻的
    状态需要完整事件流）。追加式覆盖三者全保。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_RECORD_TYPE = "memory_status"
VALID_STATUSES = ("archived", "rejected", "reinstated")
_SUPPRESSED = frozenset({"archived", "rejected"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_status_record(rec: Any) -> bool:
    return isinstance(rec, dict) and rec.get("record_type") == STATUS_RECORD_TYPE


def record_status(
    path: str | Path,
    *,
    target_ts: str,
    status: str,
    reason: str = "",
    ts: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """向台账追加一条状态覆盖行。target_ts 为空或 status 非法时抛 ValueError。"""
    target = str(target_ts or "").strip()
    if not target:
        raise ValueError("target_ts 不能为空：状态行必须指向一条既有记录")
    if status not in VALID_STATUSES:
        raise ValueError(f"status 必须是 {VALID_STATUSES} 之一，得到 {status!r}")
    record: dict[str, Any] = {
        "record_type": STATUS_RECORD_TYPE,
        "ts": ts or _now().isoformat(timespec="seconds"),
        "target_ts": target,
        "status": status,
    }
    cleaned_reason = re.sub(r"\s+", " ", str(reason or "")).strip()
    if cleaned_reason:
        record["reason"] = cleaned_reason
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


def suppressed_targets(records: list[dict[str, Any]]) -> set[str]:
    """从原始行（含状态行）算出当前应被屏蔽的 target_ts 集合。

    同一 target_ts 以文件中**最后出现**的状态行为准（append-only 语义下即最新）。
    """
    latest: dict[str, str] = {}
    for rec in records:
        if not is_status_record(rec):
            continue
        target = str(rec.get("target_ts") or "").strip()
        status = str(rec.get("status") or "").strip()
        if target and status in VALID_STATUSES:
            latest[target] = status
    return {t for t, s in latest.items() if s in _SUPPRESSED}


def apply_status_overrides(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """过滤：剔除状态行本身 + 被 archived/rejected 的目标记录。

    无状态行时原样返回（除剔除非 dict 外零改动）——棘轮保证。
    """
    suppressed = suppressed_targets(records)
    out: list[dict[str, Any]] = []
    for rec in records:
        if not isinstance(rec, dict) or is_status_record(rec):
            continue
        if suppressed and str(rec.get("ts") or "").strip() in suppressed:
            continue
        out.append(rec)
    return out

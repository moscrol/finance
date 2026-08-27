"""读取知识库仓的跨仓回补队列回执（receipt.json），让金融仓感知缺口处置状态。

kb-ingest-queue v1 是单向的：金融仓抛出缺口 → 知识库归档 → 人工入库，
金融仓永远不知道缺口补上没有。知识库仓的 ``kb_ingest_queue.py`` 在
receive/mark 时会把任务生命周期（pending → received → ingested/skipped）
聚合成 ``wiki/raw/cross-repo-ingest-queue/<date>/receipt.json``；本模块只读
这些回执并汇总，供 CLI 展示与下次出队列时去重（已 ingested 的主题不再重复抛出）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

QUEUE_DIR_PARTS = ("raw", "cross-repo-ingest-queue")
RECEIPT_NAME = "receipt.json"
OPEN_STATUSES = {"pending", "received"}


@dataclass(frozen=True)
class QueueHealth:
    """跨仓队列消费 SLA。条数会骗人，最老未消费年龄才是残局信号。"""

    receipt_days: int
    task_count: int
    by_status: dict[str, int]
    open_count: int
    oldest_received_date: str | None
    oldest_received_age_days: int | None
    oldest_received_theme: str | None
    oldest_received_type: str | None


def queue_root(kb_wiki: str | Path) -> Path:
    return Path(kb_wiki).expanduser().joinpath(*QUEUE_DIR_PARTS)


def load_receipts(kb_wiki: str | Path, *, since: str | None = None) -> list[dict[str, Any]]:
    """按日期升序读出各日期目录的 receipt.json（缺回执的日期目录跳过）。"""
    root = queue_root(kb_wiki)
    if not root.exists():
        return []
    receipts: list[dict[str, Any]] = []
    for day_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if since and day_dir.name < since:
            continue
        receipt_path = day_dir / RECEIPT_NAME
        if not receipt_path.exists():
            continue
        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            payload["_receipt_path"] = str(receipt_path)
            receipts.append(payload)
    return receipts


def flatten_tasks(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for receipt in receipts:
        market_date = str(receipt.get("market_date") or "-")
        for queue in receipt.get("queues") or []:
            for task in queue.get("tasks") or []:
                tasks.append({**task, "market_date": market_date})
    return tasks


def resolved_themes(kb_wiki: str | Path, *, since: str | None = None) -> set[str]:
    """已被知识库标记为 ingested 的主题集合（供出队列时去重）。

    只认 ingested，不认 skipped：宁可重提不可漏提。skipped 是处置意见，
    不是「缺口已补」；消费端 SLA 看 ``queue_health.oldest_received_age_days``。
    """
    return {
        str(task.get("theme") or "")
        for task in flatten_tasks(load_receipts(kb_wiki, since=since))
        if task.get("status") == "ingested" and task.get("theme")
    }


def queue_health(
    kb_wiki: str | Path,
    *,
    since: str | None = None,
    as_of: date | None = None,
) -> QueueHealth:
    """汇总回执，并算出最老一条 pending/received 的年龄。"""
    receipts = load_receipts(kb_wiki, since=since)
    tasks = flatten_tasks(receipts)
    by_status: dict[str, int] = {}
    for task in tasks:
        status = str(task.get("status") or "pending")
        by_status[status] = by_status.get(status, 0) + 1
    open_tasks = [task for task in tasks if str(task.get("status") or "pending") in OPEN_STATUSES]
    oldest = min(
        (task for task in open_tasks if _parse_market_date(task.get("market_date"))),
        key=lambda task: str(task.get("market_date")),
        default=None,
    )
    oldest_date = str(oldest.get("market_date")) if oldest else None
    parsed = _parse_market_date(oldest_date) if oldest_date else None
    today = as_of or date.today()
    age = (today - parsed).days if parsed else None
    return QueueHealth(
        receipt_days=len(receipts),
        task_count=len(tasks),
        by_status=by_status,
        open_count=len(open_tasks),
        oldest_received_date=oldest_date,
        oldest_received_age_days=age,
        oldest_received_theme=str(oldest.get("theme") or "-") if oldest else None,
        oldest_received_type=str(oldest.get("task_type") or "-") if oldest else None,
    )


def _parse_market_date(value: object) -> date | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def render_status(
    kb_wiki: str | Path,
    *,
    since: str | None = None,
    as_of: date | None = None,
) -> str:
    receipts = load_receipts(kb_wiki, since=since)
    if not receipts:
        return (
            f"未找到回执（{queue_root(kb_wiki)}）。"
            "知识库侧 receive/mark 后会生成 receipt.json；旧归档可在知识库仓跑 "
            "`python3 scripts/kb_ingest_queue.py receipt <date_dir>` 补建。"
        )
    health = queue_health(kb_wiki, since=since, as_of=as_of)
    tasks = flatten_tasks(receipts)
    by_status = health.by_status
    lines = [
        f"跨仓回补队列回执：{health.receipt_days} 天、{health.task_count} 个任务、未消费 {health.open_count}",
        "状态汇总：" + "、".join(f"{k}×{v}" for k, v in sorted(by_status.items())),
    ]
    if health.oldest_received_date is not None:
        age = (
            f"{health.oldest_received_age_days} 天"
            if health.oldest_received_age_days is not None
            else "年龄未知"
        )
        lines.append(
            f"最老未消费：{health.oldest_received_date} · "
            f"{health.oldest_received_theme} · {health.oldest_received_type} · {age}"
            "（盯年龄，不盯条数）"
        )
    lines.append("")
    open_tasks = [t for t in tasks if str(t.get("status") or "pending") in OPEN_STATUSES]
    done_tasks = [t for t in tasks if t.get("status") == "ingested"]
    if open_tasks:
        lines.append("待处理（知识库尚未入库）：")
        for task in open_tasks[:20]:
            lines.append(
                f"- {task['market_date']} | {task.get('theme', '-')} | {task.get('task_type', '-')} | {task.get('status')}"
            )
        if len(open_tasks) > 20:
            lines.append(f"  ... 还有 {len(open_tasks) - 20} 条")
    if done_tasks:
        lines.append("已补齐（下次出队列自动去重）：")
        for task in done_tasks[:20]:
            note = f" | {task.get('status_note')}" if task.get("status_note") else ""
            lines.append(f"- {task['market_date']} | {task.get('theme', '-')} | {task.get('task_type', '-')}{note}")
        if len(done_tasks) > 20:
            lines.append(f"  ... 还有 {len(done_tasks) - 20} 条")
    return "\n".join(lines)

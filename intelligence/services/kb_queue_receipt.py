"""读取知识库仓的跨仓回补队列回执（receipt.json），让金融仓感知缺口处置状态。

kb-ingest-queue v1 是单向的：金融仓抛出缺口 → 知识库归档 → 人工入库，
金融仓永远不知道缺口补上没有。知识库仓的 ``kb_ingest_queue.py`` 在
receive/mark 时会把任务生命周期（pending → received → ingested/skipped）
聚合成 ``wiki/raw/cross-repo-ingest-queue/<date>/receipt.json``；本模块只读
这些回执并汇总，供 CLI 展示与下次出队列时去重（已 ingested 的主题不再重复抛出）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

QUEUE_DIR_PARTS = ("raw", "cross-repo-ingest-queue")
RECEIPT_NAME = "receipt.json"
OPEN_STATUSES = {"pending", "received"}


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
    """已被知识库标记为 ingested 的主题集合（供出队列时去重）。"""
    return {
        str(task.get("theme") or "")
        for task in flatten_tasks(load_receipts(kb_wiki, since=since))
        if task.get("status") == "ingested" and task.get("theme")
    }


def render_status(kb_wiki: str | Path, *, since: str | None = None) -> str:
    receipts = load_receipts(kb_wiki, since=since)
    if not receipts:
        return (
            f"未找到回执（{queue_root(kb_wiki)}）。"
            "知识库侧 receive/mark 后会生成 receipt.json；旧归档可在知识库仓跑 "
            "`python3 scripts/kb_ingest_queue.py receipt <date_dir>` 补建。"
        )
    tasks = flatten_tasks(receipts)
    by_status: dict[str, int] = {}
    for task in tasks:
        status = str(task.get("status") or "pending")
        by_status[status] = by_status.get(status, 0) + 1
    lines = [
        f"跨仓回补队列回执：{len(receipts)} 天、{len(tasks)} 个任务",
        "状态汇总：" + "、".join(f"{k}×{v}" for k, v in sorted(by_status.items())),
        "",
    ]
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

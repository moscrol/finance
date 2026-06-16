"""record-interaction workflow：把一条用户反馈落到 users/<id>/interactions.jsonl。

这是「越用越懂」反馈回路的写入入口：用户点开 / 追问 / 喜欢 / 忽略 / 打分某条
「猜你想问」问题时记一笔，下次 foresight 排序据此给相关题材/个股加成。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.services import interactions
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


@dataclass(frozen=True)
class RecordInteractionOptions:
    kind: str
    user: str | None = None
    question: str | None = None
    themes: list[str] = field(default_factory=list)
    stocks: list[str] = field(default_factory=list)
    weight: float | None = None
    rating: float | None = None
    note: str | None = None
    interactions_file: str | Path | None = None


def run_record_interaction(
    options: RecordInteractionOptions,
) -> tuple[WorkflowSummary, dict[str, Any]]:
    summary = WorkflowSummary(
        workflow="record-interaction",
        status="PASS",
        started_at=now_iso(),
        inputs={
            "user": options.user or "default",
            "kind": options.kind,
            "themes": list(options.themes),
            "stocks": list(options.stocks),
        },
    )

    if options.interactions_file:
        path: Path = Path(options.interactions_file).expanduser()
    else:
        path = userspace.user_space(options.user).interactions_path

    kind = str(options.kind or "").strip().lower()
    if kind not in interactions.KNOWN_KINDS and options.weight is None and options.rating is None:
        summary.warnings.append(
            f"未知反馈类型「{kind}」且未给 --weight/--rating，权重将记为 0（不影响排序）。"
        )

    written, record = interactions.record_interaction(
        path,
        kind=kind,
        question=options.question,
        themes=options.themes,
        stocks=options.stocks,
        weight=options.weight,
        rating=options.rating,
        note=options.note,
    )

    summary.steps.append(
        WorkflowStep(
            name="record",
            status="PASS",
            outputs=[
                f"path={written}",
                f"kind={record['kind']}",
                f"weight={record['weight']}",
                f"themes={'/'.join(record['themes']) or '-'}",
                f"stocks={'/'.join(record['stocks']) or '-'}",
            ],
        )
    )
    summary.outputs = [str(written)]
    summary.next_actions = [
        "下次 `foresight --user <id>` 排序会对这些题材/个股给可解释加成（越用越懂）。",
    ]
    summary.finish("PASS")
    return summary, record


def render(record: dict[str, Any], path: str) -> str:
    parts = [f"已记录反馈：{record['kind']}（权重 {record['weight']}）"]
    if record.get("themes"):
        parts.append("题材 " + "、".join(record["themes"]))
    if record.get("stocks"):
        parts.append("个股 " + "、".join(record["stocks"]))
    head = " · ".join(parts)
    return f"{head}\n→ {path}\n"

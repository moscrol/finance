from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "market_feature_store" / "exports"
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
REVIEW_ACTIONS = {
    "missing_concept": "review_create_or_link_concept",
    "missing_entity_exposures": "review_map_entity_exposures",
    "missing_evidence": "review_attach_or_archive_evidence",
}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing input file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json root is not an object: {path}")
    return data


def priority_allowed(priority: str, min_priority: str) -> bool:
    return PRIORITY_ORDER[priority] <= PRIORITY_ORDER[min_priority]


def is_placeholder(item: dict[str, Any]) -> bool:
    values = [item.get("theme"), item.get("canonical_concept")]
    return any("未映射" in str(value) for value in values if value)


def item_status(item: dict[str, Any]) -> str:
    if is_placeholder(item):
        return "blocked_review"
    return "pending_review"


def review_note(item: dict[str, Any]) -> str:
    gap_type = str(item.get("gap_type") or "")
    if is_placeholder(item):
        return "候选名称包含未映射占位符，需先回到市场映射层确认真实题材，不建议直接写知识库。"
    if gap_type == "missing_concept":
        return "先检查 wiki/concepts 是否已有同义概念；若无，再创建概念页。"
    if gap_type == "missing_entity_exposures":
        return "先确认题材核心公司，再补 entity_exposures 映射；不要用泛行业公司凑数。"
    if gap_type == "missing_evidence":
        return "先寻找研报、公告或已归档 source 作为证据；没有证据时保持待补状态。"
    return "人工复核后再决定是否写入知识库。"


def build_review_queue(queue: dict[str, Any], source_path: Path, min_priority: str) -> dict[str, Any]:
    items = []
    for raw in as_list(queue.get("items")):
        if not isinstance(raw, dict):
            continue
        priority = str(raw.get("priority") or "")
        if priority not in PRIORITY_ORDER or not priority_allowed(priority, min_priority):
            continue
        gap_type = str(raw.get("gap_type") or "")
        item = dict(raw)
        item["review_status"] = item_status(item)
        item["review_action"] = REVIEW_ACTIONS.get(gap_type, "review_backfill_gap")
        item["review_note"] = review_note(item)
        item["knowledge_write_allowed"] = False
        items.append(item)
    status_counts = Counter(str(item.get("review_status")) for item in items)
    action_counts = Counter(str(item.get("review_action")) for item in items)
    return {
        "trade_date": queue.get("trade_date") or "",
        "source": "theme-backfill-review-queue",
        "source_file": str(source_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "mode": "review_only",
            "min_priority": min_priority,
            "knowledge_write_allowed": False,
            "placeholder_rule": "items containing 未映射 are blocked_review",
        },
        "review_count": len(items),
        "status_counts": dict(sorted(status_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "items": sorted(
            items,
            key=lambda row: (
                PRIORITY_ORDER[str(row.get("priority"))],
                str(row.get("review_status")),
                int(row.get("rank") or 0),
                str(row.get("gap_type") or ""),
            ),
        ),
    }


def md_table(items: list[dict[str, Any]]) -> str:
    lines = [
        "| 优先级 | 状态 | Rank | Tier | 题材 | 缺口 | 动作 | 复核说明 |",
        "|---|---|---:|---|---|---|---|---|",
    ]
    for item in items:
        lines.append(
            "| {priority} | {status} | {rank} | {tier} | {theme} | {gap} | {action} | {note} |".format(
                priority=item.get("priority") or "-",
                status=item.get("review_status") or "-",
                rank=item.get("rank") or "-",
                tier=item.get("candidate_tier") or "-",
                theme=str(item.get("theme") or "-").replace("|", "/"),
                gap=item.get("gap_type") or "-",
                action=item.get("review_action") or "-",
                note=str(item.get("review_note") or "-").replace("|", "/"),
            )
        )
    return "\n".join(lines)


def render_markdown(payload: dict[str, Any]) -> str:
    trade_date = payload.get("trade_date") or ""
    policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
    items = [item for item in as_list(payload.get("items")) if isinstance(item, dict)]
    return "\n".join([
        f"# {trade_date} 题材补库 Review Queue",
        "",
        "本文件是 review_only 清单，不直接写知识库。",
        "",
        "## 策略",
        "",
        f"- **mode**: {policy.get('mode')}",
        f"- **min_priority**: {policy.get('min_priority')}",
        f"- **knowledge_write_allowed**: {policy.get('knowledge_write_allowed')}",
        f"- **placeholder_rule**: {policy.get('placeholder_rule')}",
        "",
        "## 摘要",
        "",
        f"- **review_count**: {payload.get('review_count')}",
        f"- **status_counts**: `{json.dumps(payload.get('status_counts', {}), ensure_ascii=False)}`",
        f"- **action_counts**: `{json.dumps(payload.get('action_counts', {}), ensure_ascii=False)}`",
        "",
        "## 待审核项",
        "",
        md_table(items),
        "",
    ])


def output_paths_for(trade_date: str) -> tuple[Path, Path]:
    return (
        EXPORT_DIR / f"{trade_date}-theme-backfill-review-queue.json",
        EXPORT_DIR / f"{trade_date}-theme-backfill-review-queue.md",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only queue from theme backfill queue")
    parser.add_argument("date")
    parser.add_argument("--input", dest="input_path")
    parser.add_argument("--out-json", dest="out_json")
    parser.add_argument("--out-md", dest="out_md")
    parser.add_argument("--min-priority", choices=["critical", "high", "medium", "low"], default="high")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_path).expanduser() if args.input_path else EXPORT_DIR / f"{args.date}-theme-backfill-queue.json"
    out_json, out_md = output_paths_for(args.date)
    if args.out_json:
        out_json = Path(args.out_json).expanduser()
    if args.out_md:
        out_md = Path(args.out_md).expanduser()
    queue = load_json(input_path)
    payload = build_review_queue(queue, input_path, args.min_priority)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(payload), encoding="utf-8")
    print(out_json)
    print(out_md)
    print(f"review_count={payload['review_count']}")
    print(f"status_counts={payload['status_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

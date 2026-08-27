from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "market_feature_store" / "exports"
STATUS_ORDER = {
    "candidate_detected": 0,
    "backfill_queued": 1,
    "pending_review": 2,
    "blocked_review": 3,
    "review_ready": 4,
}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"missing input file: {path}")
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json root is not an object: {path}")
    return data


def candidate_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = as_list(data.get("candidates"))
    out = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["rank"] = int(item.get("rank") or index)
        item["candidate_tier"] = item.get("candidate_tier") or _tier_from_rank(int(item["rank"]))
        out.append(item)
    return out


def build_ledger(
    candidates: dict[str, Any],
    backfill_queue: dict[str, Any],
    review_queue: dict[str, Any],
    candidate_path: Path | None,
    backfill_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    trade_date = backfill_queue.get("trade_date") or review_queue.get("trade_date") or candidates.get("trade_date") or ""
    rows: dict[str, dict[str, Any]] = {}
    for candidate in candidate_rows(candidates):
        rank = int(candidate.get("rank") or 0)
        item_id = f"{trade_date}-{rank:02d}-candidate"
        rows[item_id] = _ledger_item(
            item_id,
            trade_date,
            "candidate_detected",
            candidate.get("market_theme"),
            candidate.get("canonical_concept"),
            candidate.get("candidate_tier"),
            rank,
            candidate.get("priority_score"),
            "",
            "市场触发候选已发现，等待知识库缺口判定。",
            "detect_candidate",
            "来自 theme-candidates，尚未进入补库队列。",
            str(candidate_path) if candidate_path else "",
        )
    for raw in as_list(backfill_queue.get("items")):
        if not isinstance(raw, dict):
            continue
        item_id = str(raw.get("id") or _fallback_id(trade_date, raw))
        rows[item_id] = _ledger_item_from_queue(item_id, raw, "backfill_queued", "queue_backfill_gap", str(backfill_path))
    for raw in as_list(review_queue.get("items")):
        if not isinstance(raw, dict):
            continue
        item_id = str(raw.get("id") or _fallback_id(trade_date, raw))
        review_status = str(raw.get("review_status") or "pending_review")
        status = review_status if review_status in {"pending_review", "blocked_review"} else "review_ready"
        rows[item_id] = _ledger_item_from_queue(
            item_id,
            raw,
            status,
            str(raw.get("review_action") or "review_backfill_gap"),
            str(review_path),
            str(raw.get("review_note") or ""),
        )
    items = sorted(rows.values(), key=lambda row: (STATUS_ORDER.get(str(row.get("ingest_status")), 99), int(row.get("rank") or 0), str(row.get("id") or "")))
    status_counts = Counter(str(item.get("ingest_status")) for item in items)
    action_counts = Counter(str(item.get("next_action")) for item in items)
    return {
        "trade_date": trade_date,
        "source": "ingest-status-ledger",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "theme_candidates": str(candidate_path) if candidate_path else "",
            "theme_backfill_queue": str(backfill_path),
            "theme_backfill_review_queue": str(review_path),
        },
        "status_order": list(STATUS_ORDER.keys()),
        "item_count": len(items),
        "status_counts": dict(sorted(status_counts.items(), key=lambda item: STATUS_ORDER.get(item[0], 99))),
        "action_counts": dict(sorted(action_counts.items())),
        "items": items,
    }


def _ledger_item_from_queue(
    item_id: str,
    raw: dict[str, Any],
    status: str,
    next_action: str,
    source_file: str,
    note: str = "",
) -> dict[str, Any]:
    return _ledger_item(
        item_id,
        str(raw.get("trade_date") or ""),
        status,
        raw.get("theme"),
        raw.get("canonical_concept"),
        raw.get("candidate_tier"),
        int(raw.get("rank") or 0),
        raw.get("priority_score"),
        str(raw.get("gap_type") or ""),
        str(raw.get("reason") or ""),
        next_action,
        note,
        source_file,
        str(raw.get("priority") or ""),
    )


def _ledger_item(
    item_id: str,
    trade_date: str,
    status: str,
    theme: Any,
    concept: Any,
    tier: Any,
    rank: int,
    priority_score: Any,
    gap_type: str,
    reason: str,
    next_action: str,
    note: str,
    source_file: str,
    priority: str = "",
) -> dict[str, Any]:
    return {
        "id": item_id,
        "trade_date": trade_date,
        "ingest_status": status,
        "theme": theme,
        "canonical_concept": concept,
        "candidate_tier": tier,
        "rank": rank,
        "priority": priority,
        "priority_score": priority_score,
        "gap_type": gap_type,
        "reason": reason,
        "next_action": next_action,
        "status_note": note,
        "source_file": source_file,
    }


def _fallback_id(trade_date: str, row: dict[str, Any]) -> str:
    return f"{trade_date}-{int(row.get('rank') or 0):02d}-{row.get('gap_type') or 'gap'}"


def _tier_from_rank(rank: int) -> str:
    if rank <= 10:
        return "deep"
    if rank <= 30:
        return "watch"
    return "long_tail"


def md_table(items: list[dict[str, Any]]) -> str:
    lines = [
        "| 状态 | 优先级 | Rank | Tier | 题材 | 缺口 | 下一步 |",
        "|---|---|---:|---|---|---|---|",
    ]
    for item in items:
        lines.append(
            "| {status} | {priority} | {rank} | {tier} | {theme} | {gap} | {action} |".format(
                status=item.get("ingest_status") or "-",
                priority=item.get("priority") or "-",
                rank=item.get("rank") or "-",
                tier=item.get("candidate_tier") or "-",
                theme=str(item.get("theme") or "-").replace("|", "/"),
                gap=item.get("gap_type") or "-",
                action=str(item.get("next_action") or "-").replace("|", "/"),
            )
        )
    return "\n".join(lines)


def render_markdown(payload: dict[str, Any]) -> str:
    items = [item for item in as_list(payload.get("items")) if isinstance(item, dict)]
    return "\n".join([
        f"# {payload.get('trade_date')} Ingest Status Ledger",
        "",
        "## 摘要",
        "",
        f"- **item_count**: {payload.get('item_count')}",
        f"- **status_counts**: `{json.dumps(payload.get('status_counts', {}), ensure_ascii=False)}`",
        f"- **action_counts**: `{json.dumps(payload.get('action_counts', {}), ensure_ascii=False)}`",
        "",
        "## 明细",
        "",
        md_table(items),
        "",
    ])


def output_paths_for(trade_date: str) -> tuple[Path, Path]:
    return (
        EXPORT_DIR / f"{trade_date}-ingest-status-ledger.json",
        EXPORT_DIR / f"{trade_date}-ingest-status-ledger.md",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ingest status ledger from theme backfill queues")
    parser.add_argument("date")
    parser.add_argument("--candidates", dest="candidate_path")
    parser.add_argument("--backfill", dest="backfill_path")
    parser.add_argument("--review", dest="review_path")
    parser.add_argument("--out-json", dest="out_json")
    parser.add_argument("--out-md", dest="out_md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate_path = Path(args.candidate_path).expanduser() if args.candidate_path else EXPORT_DIR / f"{args.date}-theme-candidates.json"
    backfill_path = Path(args.backfill_path).expanduser() if args.backfill_path else EXPORT_DIR / f"{args.date}-theme-backfill-queue.json"
    review_path = Path(args.review_path).expanduser() if args.review_path else EXPORT_DIR / f"{args.date}-theme-backfill-review-queue.json"
    out_json, out_md = output_paths_for(args.date)
    if args.out_json:
        out_json = Path(args.out_json).expanduser()
    if args.out_md:
        out_md = Path(args.out_md).expanduser()
    candidates = load_json(candidate_path, required=False)
    backfill_queue = load_json(backfill_path)
    review_queue = load_json(review_path)
    payload = build_ledger(candidates, backfill_queue, review_queue, candidate_path if candidate_path.exists() else None, backfill_path, review_path)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(payload), encoding="utf-8")
    print(out_json)
    print(out_md)
    print(f"item_count={payload['item_count']}")
    print(f"status_counts={payload['status_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

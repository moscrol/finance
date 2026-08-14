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
TIER_LABELS = {"deep": "Deep", "watch": "Watch", "long_tail": "Long Tail"}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing input file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json root is not an object: {path}")
    return data


def candidate_rows(data: dict[str, Any], tier_filter: str) -> list[dict[str, Any]]:
    if tier_filter == "deep":
        rows = as_list(data.get("deep_candidates"))
    elif tier_filter == "watch":
        rows = as_list(data.get("watch_candidates"))
    elif tier_filter == "long_tail":
        rows = as_list(data.get("long_tail_candidates"))
    else:
        rows = as_list(data.get("candidates"))
    out = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        item = dict(row)
        rank = item.get("rank")
        if not rank:
            rank = index if tier_filter == "all" else _rank_from_tier(tier_filter, index)
        item["rank"] = int(rank)
        item["candidate_tier"] = item.get("candidate_tier") or _tier_from_rank(int(rank))
        out.append(item)
    return out


def _rank_from_tier(tier: str, index: int) -> int:
    if tier == "watch":
        return 10 + index
    if tier == "long_tail":
        return 30 + index
    return index


def _tier_from_rank(rank: int) -> str:
    if rank <= 10:
        return "deep"
    if rank <= 30:
        return "watch"
    return "long_tail"


def gap_priority(tier: str, gap_type: str) -> str:
    if tier == "deep" and gap_type in {"missing_concept", "missing_entity_exposures"}:
        return "critical"
    if tier == "deep" and gap_type == "missing_evidence":
        return "high"
    if tier == "watch" and gap_type == "missing_concept":
        return "high"
    if tier == "watch" and gap_type in {"missing_entity_exposures", "missing_evidence"}:
        return "medium"
    return "low"


def gap_reason(tier: str, gap_type: str) -> str:
    tier_label = TIER_LABELS.get(tier, tier)
    if gap_type == "missing_concept":
        return f"{tier_label} 市场触发候选缺少本地概念匹配"
    if gap_type == "missing_entity_exposures":
        return f"{tier_label} 市场触发候选缺少本地公司暴露映射"
    if gap_type == "missing_evidence":
        return f"{tier_label} 市场触发候选缺少本地证据支撑"
    return f"{tier_label} 市场触发候选存在知识库缺口"


def build_queue(data: dict[str, Any], source_path: Path, tier_filter: str, min_priority: str) -> dict[str, Any]:
    trade_date = data.get("trade_date") or ""
    candidates = candidate_rows(data, tier_filter)
    items = []
    for candidate in candidates:
        status = candidate.get("knowledge_status") if isinstance(candidate.get("knowledge_status"), dict) else {}
        gaps = [str(value) for value in as_list(status.get("backfill_gaps")) if str(value).strip()]
        for gap_type in gaps:
            tier = str(candidate.get("candidate_tier") or _tier_from_rank(int(candidate.get("rank") or 0)))
            priority = gap_priority(tier, gap_type)
            if PRIORITY_ORDER[priority] > PRIORITY_ORDER[min_priority]:
                continue
            rank = int(candidate.get("rank") or 0)
            items.append(
                {
                    "id": f"{trade_date}-{rank:02d}-{gap_type}",
                    "trade_date": trade_date,
                    "theme": candidate.get("market_theme"),
                    "canonical_concept": candidate.get("canonical_concept"),
                    "sw_l1": candidate.get("sw_l1"),
                    "candidate_tier": tier,
                    "rank": rank,
                    "priority_score": candidate.get("priority_score"),
                    "gap_type": gap_type,
                    "priority": priority,
                    "reason": gap_reason(tier, gap_type),
                    "trigger_types": as_list(candidate.get("trigger_types")),
                    "concept_count": status.get("concept_count", 0),
                    "exposure_count": status.get("exposure_count", 0),
                    "evidence_count": status.get("evidence_count", 0),
                }
            )
    items = sorted(items, key=lambda row: (PRIORITY_ORDER[row["priority"]], int(row.get("rank") or 0), str(row.get("gap_type") or "")))
    priority_counts = Counter(str(item.get("priority")) for item in items)
    gap_counts = Counter(str(item.get("gap_type")) for item in items)
    tier_counts = Counter(str(item.get("candidate_tier")) for item in items)
    return {
        "trade_date": trade_date,
        "source": "theme-candidates-backfill-queue",
        "source_file": str(source_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "tier": tier_filter,
            "min_priority": min_priority,
        },
        "candidate_count": len(candidates),
        "queue_count": len(items),
        "priority_counts": dict(sorted(priority_counts.items(), key=lambda item: PRIORITY_ORDER[item[0]])),
        "gap_counts": dict(sorted(gap_counts.items())),
        "tier_counts": dict(sorted(tier_counts.items())),
        "items": items,
    }


def output_path_for(trade_date: str) -> Path:
    return EXPORT_DIR / f"{trade_date}-theme-backfill-queue.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build theme backfill queue from theme-candidates JSON")
    parser.add_argument("date")
    parser.add_argument("--input", dest="input_path")
    parser.add_argument("--output", dest="output_path")
    parser.add_argument("--tier", choices=["all", "deep", "watch", "long_tail"], default="all")
    parser.add_argument("--min-priority", choices=["critical", "high", "medium", "low"], default="low")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_path).expanduser() if args.input_path else EXPORT_DIR / f"{args.date}-theme-candidates.json"
    output_path = Path(args.output_path).expanduser() if args.output_path else output_path_for(args.date)
    data = load_json(input_path)
    payload = build_queue(data, input_path, args.tier, args.min_priority)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    print(f"queue_count={payload['queue_count']}")
    print(f"priority_counts={payload['priority_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

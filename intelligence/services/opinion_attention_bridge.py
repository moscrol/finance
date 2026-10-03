"""Bridge public attention into the existing opinion track without replacing report coverage."""
from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from intelligence.services.opinion_attention import (
    SHANGHAI,
    attention_snapshot,
    default_ledger_path,
    digest,
    read_ledger,
    timestamp,
)


def river_attention_objects(as_of: str, knowledge_cutoff: str, entity_id: str, *, ledger_path: Path | None = None) -> list[dict[str, Any]]:
    """Fixed calendar-day cutoff for deterministic six-track reads.

    Never relax time travel for public news: even the existing hindsight view only
    gets observations available by min(as_of, knowledge_cutoff). No ledger => no
    change to the original track. A malformed ledger fails closed, not silently empty.
    """
    path = ledger_path or default_ledger_path()
    if not path.exists():
        return []
    cutoff_day = min(date.fromisoformat(as_of), date.fromisoformat(knowledge_cutoff))
    cutoff = datetime.combine(cutoff_day, time.max, SHANGHAI)
    snapshot = attention_snapshot(read_ledger(path), cutoff, entity_id=entity_id)
    result = []
    for event in snapshot["events"]:
        known = [timestamp(source["recorded_at"]) for source in event["sources"]]
        recorded = max(value for value in known if value is not None)
        result.append({
            "track": "opinion", "entity_id": entity_id, "object_type": "public_news_attention",
            "ref": f"opinion-attention:{event['id']}:{digest(event)[:16]}",
            "source_hash": digest(event), "valid_from": as_of,
            "recorded_at": recorded.astimezone(SHANGHAI).isoformat(),
            "payload": {**event, "subtrack": "public_attention", "rule_version": snapshot["rule_version"],
                        "scope": "observed_sources_only", "knowledge_cutoff": cutoff.isoformat(),
                        "caveat": "传播热度不等于事实硬度；与研报覆盖分列，未据此判定共识阶段。"},
        })
    return result

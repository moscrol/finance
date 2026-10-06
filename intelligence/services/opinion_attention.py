"""Public attention observations, separate from sell-side judgments and verified facts.

AIHOT-inspired 48-hour independent-participant heat (24h half life). This module
is offline: no collection, model calls, market DB writes, or automatic KB promotion.
Every revision is locally timestamped; upstream discovery time never substitutes
for local knowledge time. Replaying a date reads only revisions known by that cutoff.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc
RULE_VERSION = "public-attention-v1-48h-half24h"
SCHEMA_VERSION = 1
MAX_ITEMS = 10000


def default_ledger_path() -> Path:
    from intelligence.paths import data_repo_root

    override = os.getenv("OPINION_ATTENTION_LEDGER")
    return Path(override).expanduser() if override else data_repo_root() / "state" / "opinion-attention" / "observations.jsonl"


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        out = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        # A date-only or timezone-free source stamp is not precise enough for an intraday signal.
        if "T" not in value and " " not in value:
            return None
        return out.astimezone(UTC) if out.tzinfo else None
    except ValueError:
        return None


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def cutoff_for_date(day: date, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    return min(datetime.combine(day, time.max, SHANGHAI).astimezone(UTC), current)


def canonical_url(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("original URL required")
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("only credential-free http(s) original URLs are accepted")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(sorted(query)), ""))


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def adapt_aihot(payload: Any, mapping: dict[str, Any], *, now: datetime | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Accept stock /api/v1/items payloads; optional reviewed mapping enriches grouping.

    Stock v1 does not expose story membership/source lineage. Never infer those from
    generated titles or treat a news site's 'fact' label as verified ground truth.
    mapping.sources[name] explicitly identifies an independent publisher group;
    mapping.items[upstream_id] can supply a reviewed event_key and entity_keys.
    mapping.entities[key] resolves these keys to canonical sector IDs/names.
    """
    current = now or datetime.now(UTC)
    recorded_at = iso(current)
    items = payload if isinstance(payload, list) else payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise ValueError("expected items array with at most 10000 items")
    if not isinstance(mapping, dict):
        raise ValueError("mapping must be an object")
    source_map = mapping.get("sources", {})
    entity_map = mapping.get("entities", {})
    item_map = mapping.get("items", {})
    if not all(isinstance(x, dict) for x in [source_map, entity_map, item_map]):
        raise ValueError("sources, entities and items must be objects")
    out, errors = [], []
    for index, item in enumerate(items):
        try:
            if not isinstance(item, dict):
                raise ValueError("item must be an object")
            upstream_id = str(item.get("id") or "").strip()
            title = str(item.get("title") or "").strip()
            links = item.get("links") if isinstance(item.get("links"), dict) else {}
            url = canonical_url(links.get("original") or item.get("url"))
            if not title:
                raise ValueError("title required")
            src = item.get("source")
            source_name = str(src.get("name") or "") if isinstance(src, dict) else str(src or item.get("sourceName") or "")
            cfg = source_map.get(source_name, {})
            review = item_map.get(upstream_id, {})
            if not isinstance(cfg, dict) or not isinstance(review, dict):
                raise ValueError("source/item mapping must be objects")
            participant = str(cfg.get("participant_key") or "").strip() or None
            origin = str(review.get("origin_key") or "").strip() or None
            entity_keys = review.get("entity_keys", [])
            if not isinstance(entity_keys, list):
                raise ValueError("entity_keys must be an array")
            entities = []
            for key in dict.fromkeys(entity_keys):
                entity = entity_map.get(key)
                if not isinstance(entity, dict) or not entity.get("id") or not entity.get("name"):
                    raise ValueError(f"unresolved entity mapping: {key}")
                entities.append({"id": str(entity["id"]), "name": str(entity["name"])})
            published = timestamp(item.get("publishedAt"))
            discovered = timestamp(item.get("discoveredAt"))
            if published and published > current:
                raise ValueError("publication is in the future; quarantine rather than heat")
            material_id = "url:" + digest(url)[:24]
            event_key = str(review.get("event_key") or "").strip()
            row = {
                "schema_version": SCHEMA_VERSION, "provider": "aihot", "upstream_id": upstream_id,
                "material_id": material_id, "url": url, "title": title[:2000],
                "summary": str(item.get("summary") or "")[:12000],
                "source_name": source_name[:300], "source_kind": str(cfg.get("kind") or "unknown")[:50],
                "participant_key": participant, "origin_key": origin,
                "event_key": "reviewed:" + event_key if event_key else material_id,
                "grouping": "reviewed" if event_key else "unclustered",
                "entities": entities,
                "published_at": iso(published) if published else None,
                "upstream_discovered_at": iso(discovered) if discovered else None,
                "published_at_claim": str(item.get("publishedAt") or "")[:100],
                "evidence_status": "unreviewed", "summary_origin": "upstream_model_or_editor",
                "selected": item.get("selected") is True,
                "removed": review.get("removed") is True,
                "mapping_hash": digest({"source": cfg, "item": review, "entities": entities}),
            }
            row["content_hash"] = digest(row)
            row["revision_id"] = row["content_hash"]
            row["recorded_at"] = recorded_at
            out.append(row)
        except (ValueError, TypeError, AttributeError) as exc:
            errors.append(f"item[{index}]: {exc}")
    return out, errors


def read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
        for i, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if row.get("schema_version") != SCHEMA_VERSION or not timestamp(row.get("recorded_at")):
                    raise ValueError("bad schema or recorded_at")
                rows.append(row)
            except (ValueError, AttributeError) as exc:
                raise ValueError(f"invalid opinion ledger line {i}; refusing partial history") from exc
    return rows


def append_observations(path: Path, observations: list[dict[str, Any]]) -> dict[str, int]:
    """One writer, file lock, idempotent revisions; no writes for a dry-run caller."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.seek(0)
        existing = [json.loads(line) for line in stream if line.strip()]
        latest = {row["material_id"]: row for row in existing}
        pending = []
        skipped = 0
        for row in observations:
            prior = latest.get(row["material_id"])
            if prior and prior.get("content_hash", prior["revision_id"]) == row["content_hash"]:
                skipped += 1
                continue
            if prior and row["recorded_at"] < prior["recorded_at"]:
                raise ValueError("refusing backdated local recorded_at")
            predecessor = prior["revision_id"] if prior else None
            revision = digest({"content": row["content_hash"], "supersedes": predecessor})
            entry = {**row, "revision_id": revision, "supersedes": predecessor}
            pending.append(entry)
            latest[row["material_id"]] = entry
        stream.seek(0, os.SEEK_END)
        for row in pending:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return {"added": len(pending), "skipped": skipped}


def visible_observations(rows: list[dict[str, Any]], cutoff: datetime) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        recorded = timestamp(row.get("recorded_at"))
        if recorded and recorded <= cutoff:
            prior = latest.get(row["material_id"])
            if prior is None or row["recorded_at"] >= prior["recorded_at"]:
                latest[row["material_id"]] = row
    return [row for row in latest.values() if not row.get("removed")]


def attention_snapshot(rows: list[dict[str, Any]], cutoff: datetime, *, entity_id: str | None = None) -> dict[str, Any]:
    visible = visible_observations(rows, cutoff)
    if entity_id:
        visible = [row for row in visible if any(e["id"] == entity_id for e in row["entities"])]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in visible:
        published = timestamp(row["published_at"])
        if published is not None and cutoff - timedelta(hours=48) < published <= cutoff:
            groups.setdefault(row["event_key"], []).append(row)
    events = []
    for key, members in groups.items():
        participants: dict[str, datetime] = {}
        for row in members:
            if row["participant_key"]:
                # Known syndicated origin counts once even across different publishers.
                p = row.get("origin_key") or row["participant_key"]
                when = timestamp(row["published_at"])
                if when is not None and (p not in participants or when > participants[p]):
                    participants[p] = when
        heat = sum(math.pow(0.5, (cutoff - when).total_seconds() / 86400) for when in participants.values())
        known_lineage = all(row.get("origin_key") for row in members)
        events.append({
            "id": key, "title": members[-1]["title"], "entities": members[-1]["entities"],
            "heat": round(heat, 3) if participants and members[-1]["grouping"] == "reviewed" else None,
            "participant_count": len(participants), "report_count": len(members),
            "unknown_sources": sum(not row["participant_key"] for row in members),
            "lineage_complete": known_lineage, "grouping": members[-1]["grouping"],
            "evidence_status": "unreviewed", "trend_pct": None,
            "trend_status": "collection_coverage_unverified",
            "first_published_at": min(row["published_at"] for row in members),
            "latest_published_at": max(row["published_at"] for row in members),
            "sources": [{k: row[k] for k in ["source_name", "source_kind", "url", "title", "published_at", "recorded_at"]} for row in members],
        })
    events.sort(key=lambda event: (event["heat"] is not None, event["heat"] or 0, event["latest_published_at"]), reverse=True)
    missing_times = sum(row["published_at"] is None for row in visible)
    return {
        "schema_version": SCHEMA_VERSION, "rule_version": RULE_VERSION, "cutoff": iso(cutoff),
        "knowledge_mode": "locally_recorded_at", "window_hours": 48,
        "visible_observations": len(visible), "event_count": len(events),
        "events": events[:100], "truncated": len(events) > 100,
        "missing_publication_times": missing_times,
        "collection_status": "not_connected" if not rows else "imported_snapshot",
        "last_import_at": max((row["recorded_at"] for row in rows if timestamp(row["recorded_at"]) <= cutoff), default=None),
        "gaps": [
            "传播热度不是事实硬度、情绪方向或投资结论。",
            "仅统计白名单来源中已观察到的传播；没有连续采集覆盖证明，不判定升温/降温。",
            "未复核事件聚类不计算热度；同源转载须通过 origin_key 归并，未确认血缘会明确标注。",
        ] + ([f"{missing_times} 条缺少带时区的发布时间，未计入热度。"] if missing_times else []),
    }

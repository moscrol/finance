"""Read-only opinion projection: immutable originals plus reviewed corrections.

Cutoffs are end-of-day in Asia/Shanghai. Date-only ingestion proves availability
by that day's end, not intraday availability. This is not the river catalog.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

STORE_RELPATH = Path("raw/theme-radar/opinion-store/opinion-events.jsonl")
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
SCHEMA = "opinion-corrections/v1"
REPLACEMENT_KEYS = frozenset({
    "concept", "term", "claim_summary", "hardness", "hard_evidence", "soft_claims",
    "catalysts", "evidence_layer", "date_status", "verification_status",
})


class OpinionDataError(ValueError):
    """An invalid review must never silently expose the uncorrected record."""


def record_hash(record: dict[str, Any]) -> str:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def day(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("expected YYYY-MM-DD")
    return date.fromisoformat(value)


def known_at(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing ingestion time")
    if len(value) == 10:
        return datetime.combine(day(value), time.max, LOCAL_TZ)
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return stamp.astimezone(LOCAL_TZ)


def read_originals(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise OpinionDataError(f"{path.name}:{n}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise OpinionDataError(f"{path.name}:{n}: expected object")
        rows.append(row)
    return rows


def _raw_quote(wiki: Path, ref: Any, cache: dict[str, str]) -> str:
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256", "start", "end"}:
        raise OpinionDataError("invalid raw_ref")
    rel = ref["path"]
    if not isinstance(rel, str) or not rel.startswith("raw/sellside/"):
        raise OpinionDataError("raw_ref must refer to archived sellside input")
    path = (wiki / rel).resolve()
    if not path.is_relative_to((wiki / "raw/sellside").resolve()):
        raise OpinionDataError("raw_ref escapes archive")
    if rel not in cache:
        raw = path.read_bytes()
        cache[rel] = raw.decode("utf-8")
        cache[rel + ":sha256"] = hashlib.sha256(raw).hexdigest()
    if cache[rel + ":sha256"] != ref["sha256"]:
        raise OpinionDataError("raw_ref content changed")
    start, end = ref["start"], ref["end"]
    text = cache[rel]
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise OpinionDataError("invalid raw_ref character offsets")
    return text[start:end]


def validate_batches(
    wiki: Path, originals: list[dict[str, Any]], batches: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Validate the complete revision chains, including revisions beyond cutoff."""
    originals_by_id: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for row in originals:
        eid = row.get("event_id")
        if not isinstance(eid, str) or not eid:
            continue
        if eid in originals_by_id:
            duplicates.add(eid)
        originals_by_id[eid] = row
    revisions: dict[str, list[dict[str, Any]]] = {}
    raw_cache: dict[str, str] = {}
    batch_ids: set[str] = set()
    ordered: list[tuple[datetime, str, dict[str, Any]]] = []
    for batch in batches:
        if not isinstance(batch, dict) or batch.get("schema") != SCHEMA:
            raise OpinionDataError("invalid correction schema")
        bid = batch.get("batch_id")
        if not isinstance(bid, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", bid):
            raise OpinionDataError("invalid batch_id")
        if bid in batch_ids:
            raise OpinionDataError("duplicate correction batch")
        batch_ids.add(bid)
        stamp = known_at(batch.get("recorded_at"))
        if len(batch["recorded_at"]) <= 10:
            raise OpinionDataError("correction requires timestamp")
        ordered.append((stamp, bid, batch))
    for stamp, bid, batch in sorted(ordered, key=lambda item: (item[0], item[1])):
        corrections = batch.get("corrections")
        if not isinstance(corrections, list) or not corrections:
            raise OpinionDataError("empty correction batch")
        seen: set[str] = set()
        for correction in corrections:
            if not isinstance(correction, dict):
                raise OpinionDataError("invalid correction object")
            eid = correction.get("event_id")
            if not isinstance(eid, str) or eid not in originals_by_id or eid in duplicates or eid in seen:
                raise OpinionDataError("unknown or duplicate corrected event")
            seen.add(eid)
            original = originals_by_id[eid]
            if correction.get("base_sha256") != record_hash(original):
                raise OpinionDataError(f"{eid}: original record changed")
            history = revisions.setdefault(eid, [])
            expected = history[-1]["revision_id"] if history else None
            if correction.get("supersedes") != expected:
                raise OpinionDataError(f"{eid}: revision conflict")
            if history and stamp <= known_at(history[-1]["recorded_at"]):
                raise OpinionDataError("revision timestamps must increase")
            if stamp < known_at(original.get("ingested_at")):
                raise OpinionDataError("correction predates original ingestion")
            action = correction.get("action")
            if action not in {"replace", "quarantine", "retract"}:
                raise OpinionDataError("invalid correction action")
            if not isinstance(correction.get("reason"), str) or not correction["reason"].strip():
                raise OpinionDataError("correction reason required")
            quote = _raw_quote(wiki, correction.get("raw_ref"), raw_cache)
            replacement = correction.get("replacement", {})
            if action != "replace":
                if replacement:
                    raise OpinionDataError("non-replacement action cannot patch fields")
            else:
                if not isinstance(replacement, dict) or set(replacement) != REPLACEMENT_KEYS:
                    raise OpinionDataError("replacement must provide the complete allowed semantic fields")
                for key in ("concept", "term", "claim_summary", "hardness"):
                    if not isinstance(replacement[key], str) or not replacement[key].strip():
                        raise OpinionDataError(f"replacement missing {key}")
                if replacement["claim_summary"] not in quote:
                    raise OpinionDataError("claim_summary must be verbatim within raw_ref")
                if replacement["evidence_layer"] not in {"L3", "L4"}:
                    raise OpinionDataError("sellside review cannot upgrade to primary evidence")
                if replacement["verification_status"] != "unverified" or replacement["hard_evidence"] != []:
                    raise OpinionDataError("sellside review cannot assert verified hard evidence")
                if replacement["hardness"] != "软推演":
                    raise OpinionDataError("unverified replacement must be downgraded")
                if replacement["date_status"] not in {"confirmed", "inferred_unconfirmed"}:
                    raise OpinionDataError("invalid date_status")
                for key in ("soft_claims", "catalysts"):
                    if not isinstance(replacement[key], list) or any(
                        not isinstance(s, str) or not s.strip() or s not in quote for s in replacement[key]
                    ):
                        raise OpinionDataError("replacement claims must be verbatim raw excerpts")
            history.append({**correction, "revision_id": f"{bid}:{eid}", "recorded_at": batch["recorded_at"]})
    return revisions


def read_batches(store: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((store.parent / "corrections").glob("*.json"))]
    except (ValueError, OSError) as exc:
        raise OpinionDataError("cannot read opinion corrections") from exc


def load_events(
    wiki: Path, *, as_of: str, knowledge_cutoff: str | None = None,
    allow_hindsight: bool = False, allow_inferred: bool = False,
    warnings: list[str] | None = None, store_relpath: Path = STORE_RELPATH,
) -> list[dict[str, Any]]:
    """Filter both clocks before projection; failures exclude, never use report_date as ingestion.

    Missing date_status on legacy records means unassessed, not confirmed. Explicit
    inferred dates are excluded by default. This enforces temporal eligibility,
    not semantic approval of all legacy rows or full-source coverage.
    """
    report_end = day(as_of)
    cutoff_day = day(as_of if knowledge_cutoff is None else knowledge_cutoff)
    if cutoff_day > report_end and not allow_hindsight:
        raise ValueError("future knowledge_cutoff requires allow_hindsight=True")
    cutoff = known_at(cutoff_day.isoformat())
    store = wiki / store_relpath
    if not store.resolve().is_relative_to(wiki.resolve()):
        raise OpinionDataError("event store escapes wiki")
    originals = read_originals(store)
    try:
        revisions = validate_batches(wiki, originals, read_batches(store))
    except (TypeError, ValueError, KeyError) as exc:
        raise OpinionDataError(f"invalid opinion correction chain: {exc}") from exc
    excluded: Counter[str] = Counter()
    ids = Counter(row["event_id"] for row in originals if isinstance(row.get("event_id"), str) and row["event_id"].strip())
    out: list[dict[str, Any]] = []
    for original in originals:
        eid = original.get("event_id")
        if not isinstance(eid, str) or not eid.strip() or ids[eid] != 1:
            excluded["invalid_or_duplicate_id"] += 1
            continue
        try:
            rd = day(original.get("report_date"))
            ingested = known_at(original.get("ingested_at"))
        except (TypeError, ValueError):
            excluded["invalid_time"] += 1
            continue
        if rd > report_end:
            excluded["future_report"] += 1
            continue
        if ingested > cutoff:
            excluded["late_ingestion"] += 1
            continue
        event = dict(original)
        eid = event.get("event_id")
        history = revisions.get(eid, []) if isinstance(eid, str) else []
        applicable = [r for r in history if known_at(r["recorded_at"]) <= cutoff]
        if applicable:
            revision = applicable[-1]
            if revision["action"] != "replace":
                excluded[revision["action"]] += 1
                continue
            event.update(revision["replacement"])
            # Old KB tags and tier belonged to the defective extraction, not this claim.
            for key in ("chain_layer", "kb_strength", "kb_fact_hardness", "expectation_gap", "resonance_tier"):
                event.pop(key, None)
            event.update({
                "raw_ref": revision["raw_ref"], "revision_id": revision["revision_id"],
                "recorded_at": revision["recorded_at"], "review_status": "reviewed",
                "correction_reason": revision["reason"],
            })
        else:
            event["recorded_at"] = ingested.isoformat()
        if event.get("date_status") == "inferred_unconfirmed" and not allow_inferred:
            excluded["inferred_date"] += 1
            continue
        out.append(event)
    if warnings is not None and excluded:
        warnings.append("opinion_events excluded: " + ", ".join(f"{k}={v}" for k, v in sorted(excluded.items())))
    return out


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

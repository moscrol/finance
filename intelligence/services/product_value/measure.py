"""measure_pair：把一对配对任务（原流程 vs 辅助流程）的原始事件算成 MeasurementReceipt。

确定性、无模型、不落盘。所有「算不出」都以 ``null + reason`` 或 ``limitations``
呈现，绝不把未知写成 0、失败或已完成（总合同 §5.5）。

几条容易算错的口径，在这里钉死：

- **端到端耗时只扣预登记暂停**：``pause`` 区间的 ``pause_reason`` 必须在协议
  ``allowed_pause_reasons`` 里才扣；切到后台读原资料不是暂停，是主动时间。
- **重叠区间求并集**：同一活动的多段区间先并再算分钟，救援工时另列不抵扣。
- **前端计时与完成意图不能覆盖 S/M 证据**：同一 ``interval_id`` 同时有前端与
  服务端版本时取服务端；``task_completed`` 只认 server / manual_import。
- **费用按覆盖集合去重**：同一 (component, run) 组里选最粗一层，已包含子任务
  不再加；覆盖不明或缺费率一律留在 ``unknown_cost_components``。
- **失败与降级 run 全部入账**：只要证据读取器能证明 run 存在，失败尝试就计一次
  尝试、算一份已知费用；``degrades`` 非空如实标 ``degraded``。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from intelligence.services.product_value import contracts as C
from intelligence.services.product_value.evidence import (
    EVIDENCE_CROSS_OWNER,
    EVIDENCE_OK,
    EVIDENCE_TAMPERED,
    EvidenceReader,
)
from intelligence.services.product_value.events import (
    PreparedEvents,
    event_time,
    parse_ts,
    prepare_events,
)
from intelligence.services.product_value.hashing import content_id, hash_ids
from intelligence.services.product_value.protocol import (
    allowed_pause_reasons,
    case_index,
    exclusion_rule_versions,
    pair_index,
    protocol_hash,
    validate_protocol,
)

_SM = frozenset({C.SOURCE_SERVER, C.SOURCE_MANUAL})
_TERMINAL_TYPES = {
    "task_completed": C.TERMINAL_COMPLETED,
    "task_failed": C.TERMINAL_FAILED,
    "task_abandoned": C.TERMINAL_ABANDONED,
}
# 这些限制项存在时，收据不能是 valid（可用但不完整）。
_BLOCKING_LIMITATION_PREFIXES: tuple[str, ...] = (
    "missing_assignment",
    "run_evidence_missing",
    "consent_unknown",
    "timing_missing",
    "timing_client_only",
    "quality_unknown",
    "cost_unknown",
    "cost_coverage_unknown",
    "completion_evidence_missing",
    "usage_missing",
)


def _now_iso(now: datetime | None) -> str:
    stamp = now if now is not None else datetime.now().astimezone()
    if stamp.tzinfo is None:
        stamp = stamp.astimezone()
    return stamp.isoformat(timespec="seconds")


def _minutes(seconds: float) -> float:
    return round(seconds / 60.0, 2)


def _union_seconds(intervals: Iterable[tuple[datetime, datetime]]) -> float:
    """重叠区间并集的总秒数。"""
    ordered = sorted((start, end) for start, end in intervals if end >= start)
    total = 0.0
    cursor_start: datetime | None = None
    cursor_end: datetime | None = None
    for start, end in ordered:
        if cursor_end is None or cursor_start is None or start > cursor_end:
            if cursor_end is not None and cursor_start is not None:
                total += (cursor_end - cursor_start).total_seconds()
            cursor_start, cursor_end = start, end
        elif end > cursor_end:
            cursor_end = end
    if cursor_end is not None and cursor_start is not None:
        total += (cursor_end - cursor_start).total_seconds()
    return total


def _clip(intervals: Iterable[tuple[datetime, datetime]], lo: datetime, hi: datetime) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    for start, end in intervals:
        clipped = (max(start, lo), min(end, hi))
        if clipped[1] > clipped[0]:
            out.append(clipped)
    return out


def _subtract(intervals: Iterable[tuple[datetime, datetime]], holes: Iterable[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """从区间集合里挖掉 ``holes``（用于把预登记暂停从主动时间里扣掉）。"""
    pieces = [(start, end) for start, end in intervals if end > start]
    for hole_start, hole_end in holes:
        if hole_end <= hole_start:
            continue
        next_pieces: list[tuple[datetime, datetime]] = []
        for start, end in pieces:
            if hole_end <= start or hole_start >= end:
                next_pieces.append((start, end))
                continue
            if start < hole_start:
                next_pieces.append((start, hole_start))
            if hole_end < end:
                next_pieces.append((hole_end, end))
        pieces = next_pieces
    return pieces


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _sum_by_currency(items: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    totals: dict[str, Decimal] = {}
    for item in items:
        currency = str(item.get("currency"))
        totals[currency] = totals.get(currency, Decimal("0")) + _decimal(item.get("amount"))
    return {currency: float(total) for currency, total in sorted(totals.items())}


# --------------------------------------------------------------------------
# 同意状态
# --------------------------------------------------------------------------


def _consent_timeline(events: Sequence[Mapping[str, Any]]) -> dict[str, list[tuple[datetime, str, frozenset[str]]]]:
    timeline: dict[str, list[tuple[datetime, str, frozenset[str]]]] = {}
    for event in events:
        if event.get("event_type") != "consent_changed" or not event.get("participant_id"):
            continue
        payload = event["payload"]
        effective = parse_ts(payload.get("effective_at")) or event_time(event)
        timeline.setdefault(str(event["participant_id"]), []).append(
            (effective, str(payload.get("action")), frozenset(str(s) for s in payload.get("scopes") or ()))
        )
    for entries in timeline.values():
        entries.sort(key=lambda item: (item[0], item[1]))
    return timeline


def _scopes_at(timeline: dict[str, list[tuple[datetime, str, frozenset[str]]]], participant: str, at: datetime) -> frozenset[str] | None:
    """参与者在 ``at`` 时刻生效的同意范围；没有任何记录返回 None（≠ 空集）。"""
    entries = timeline.get(participant)
    if not entries:
        return None
    active: set[str] = set()
    for effective, action, scopes in entries:
        if effective > at:
            break
        if action == "grant":
            active |= scopes
        elif action == "withdraw":
            active -= scopes
    return frozenset(active)


# --------------------------------------------------------------------------
# 单个任务
# --------------------------------------------------------------------------


def _pick_intervals(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """同 interval_id 取 S/M 版本；前端版本只在没有别的来源时使用。"""
    by_id: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        by_id.setdefault(str(event["payload"].get("interval_id")), []).append(event)
    chosen: list[dict[str, Any]] = []
    for interval_id, versions in sorted(by_id.items()):
        trusted = [v for v in versions if v.get("source_channel") in _SM]
        pool = trusted or list(versions)
        picked = sorted(pool, key=lambda item: (event_time(item), str(item["event_id"])))[-1]
        payload = picked["payload"]
        start, end = parse_ts(payload.get("start")), parse_ts(payload.get("end"))
        if start is None or end is None:
            continue
        chosen.append(
            {
                "interval_id": interval_id,
                "event_id": picked["event_id"],
                "start": start,
                "end": end,
                "activity": str(payload.get("activity")),
                "clock_source": str(payload.get("clock_source")),
                "pause_reason": payload.get("pause_reason"),
                "source_channel": picked.get("source_channel"),
                "overridden_frontend": bool(trusted) and len(versions) > len(trusted),
            }
        )
    return chosen


def _measure_task(
    assignment: Mapping[str, Any],
    task_events: Sequence[Mapping[str, Any]],
    *,
    owner: str,
    reader: EvidenceReader,
    pauses_allowed: frozenset[str],
    invalid: list[dict[str, str]],
    limitations: set[str],
) -> dict[str, Any]:
    task_id = str(assignment["task_id"])
    payload = assignment["payload"]
    deadline = parse_ts(payload.get("deadline"))
    condition = str(assignment.get("assistance_condition") or payload.get("condition"))

    # ---- 终态：S/M 优先；前端只能表达放弃意图 ----
    terminal_state, terminal_at, terminal_source, terminal_event = C.TERMINAL_OPEN, None, None, None
    trusted_terminals = sorted(
        (e for e in task_events if e["event_type"] in _TERMINAL_TYPES and e.get("source_channel") in _SM),
        key=lambda e: (event_time(e), str(e["event_id"])),
    )
    if trusted_terminals:
        terminal_event = trusted_terminals[-1]
        terminal_state = _TERMINAL_TYPES[terminal_event["event_type"]]
        terminal_at = event_time(terminal_event)
        terminal_source = str(terminal_event["source_channel"])
    else:
        intents = sorted(
            (e for e in task_events if e["event_type"] == "task_abandoned"),
            key=lambda e: (event_time(e), str(e["event_id"])),
        )
        if intents:
            terminal_event = intents[-1]
            terminal_state = C.TERMINAL_ABANDONED
            terminal_at = event_time(terminal_event)
            terminal_source = "frontend_intent"
    timed_out = bool(deadline is not None and terminal_at is not None and terminal_at > deadline)

    # ---- 完成证据引用：哈希不符判 invalid，缺失判 incomplete ----
    completion_evidence: list[dict[str, Any]] = []
    if terminal_event is not None and terminal_state == C.TERMINAL_COMPLETED:
        for ref in terminal_event.get("object_refs") or ():
            resolved = reader.resolve_ref(owner, ref)
            completion_evidence.append({"ref": dict(ref), "status": resolved.get("status"), "reason": resolved.get("reason")})
            if resolved.get("status") == EVIDENCE_TAMPERED:
                invalid.append({"code": "artifact_hash_mismatch", "detail": f"{task_id}:{ref.get('id')}"})
            elif resolved.get("status") == EVIDENCE_CROSS_OWNER:
                invalid.append({"code": "reference_cross_owner", "detail": f"{task_id}:{ref.get('id')}"})
            elif resolved.get("status") not in (EVIDENCE_OK,):
                limitations.add(f"completion_evidence_missing:{task_id}:{ref.get('id')}")

    # ---- 尝试：真实 run 的终态、错误、降级 ----
    attempts: dict[str, dict[str, Any]] = {}
    for event in task_events:
        if event["event_type"] not in {"run_started", "run_finished"}:
            continue
        run_payload = event["payload"]
        attempt_id = str(run_payload.get("attempt_id"))
        record = attempts.setdefault(
            attempt_id,
            {
                "attempt_id": attempt_id,
                "run_id": str(run_payload.get("run_id")),
                "started_at": None,
                "finished_at": None,
                "reported_status": None,
                "error_ref": None,
            },
        )
        if event["event_type"] == "run_started":
            record["started_at"] = event_time(event).isoformat()
        else:
            record["finished_at"] = event_time(event).isoformat()
            record["reported_status"] = str(run_payload.get("status"))
            record["error_ref"] = run_payload.get("error_ref")
    attempt_rows: list[dict[str, Any]] = []
    for attempt_id, record in sorted(attempts.items()):
        evidence = reader.resolve_run(owner, record["run_id"])
        status = str(evidence.get("status"))
        run_status = evidence.get("run_status") if status == EVIDENCE_OK else None
        effective_status = run_status or record["reported_status"]
        if status == EVIDENCE_CROSS_OWNER:
            invalid.append({"code": "run_cross_owner", "detail": record["run_id"]})
        elif status == EVIDENCE_TAMPERED:
            invalid.append({"code": "run_tampered", "detail": record["run_id"]})
        elif status != EVIDENCE_OK:
            limitations.add(f"run_evidence_missing:{record['run_id']}")
        if run_status and record["reported_status"] and run_status != record["reported_status"]:
            limitations.add(f"attempt_status_conflict:{attempt_id}")
        attempt_rows.append(
            {
                **record,
                "evidence_status": status,
                "evidence_reason": evidence.get("reason"),
                "run_status": run_status,
                "effective_status": effective_status,
                "failed": effective_status in {"failed", "cancelled"},
                "degraded": bool(evidence.get("degrades")),
                "degrades": list(evidence.get("degrades") or ()),
                "has_error": bool(evidence.get("has_error")),
            }
        )

    # ---- 计时 ----
    intervals = _pick_intervals([e for e in task_events if e["event_type"] == "time_interval"])
    rescue_spans: list[tuple[datetime, datetime]] = []
    for event in task_events:
        if event["event_type"] == "manual_assistance":
            start, end = parse_ts(event["payload"].get("start")), parse_ts(event["payload"].get("end"))
            if start is not None and end is not None:
                rescue_spans.append((start, end))
    starts: list[datetime] = []
    ends: list[datetime] = []
    trusted_anchor = False
    for event in task_events:
        if event["event_type"] == "task_started":
            starts.append(event_time(event))
            trusted_anchor = trusted_anchor or event.get("source_channel") in _SM
    for row in attempt_rows:
        if row["started_at"]:
            starts.append(datetime.fromisoformat(row["started_at"]))
            trusted_anchor = True
        if row["finished_at"]:
            ends.append(datetime.fromisoformat(row["finished_at"]))
    for item in intervals:
        starts.append(item["start"])
        ends.append(item["end"])
        trusted_anchor = trusted_anchor or item["source_channel"] in _SM
    if terminal_at is not None:
        ends.append(terminal_at)
        trusted_anchor = trusted_anchor or terminal_source in _SM
    for start, end in rescue_spans:
        starts.append(start)
        ends.append(end)

    timing: dict[str, Any] = {
        "started_at": None,
        "ended_at": None,
        "end_to_end_minutes": None,
        "user_active_minutes": None,
        "model_wait_minutes": None,
        "manual_rescue_minutes": _minutes(_union_seconds([(i["start"], i["end"]) for i in intervals if i["activity"] == C.ACTIVITY_MANUAL_RESCUE] + rescue_spans)),
        "pause_deducted_minutes": 0.0,
        "pause_not_deducted": [],
        "clock_sources": sorted({i["clock_source"] for i in intervals}),
        "certainty": None,
        "client_only": False,
        "reason": None,
        "interval_ids": [i["interval_id"] for i in intervals],
        "frontend_overridden": sorted(i["interval_id"] for i in intervals if i["overridden_frontend"]),
    }
    if not starts or not ends:
        timing["reason"] = "no_timing_evidence"
        limitations.add(f"timing_missing:{task_id}")
    else:
        started, ended = min(starts), max(ends)
        if ended < started:
            timing["reason"] = "anchors_inverted"
            limitations.add(f"timing_missing:{task_id}")
        else:
            deducted: list[tuple[datetime, datetime]] = []
            for item in intervals:
                if item["activity"] != C.ACTIVITY_PAUSE:
                    continue
                if item["pause_reason"] in pauses_allowed:
                    deducted.append((item["start"], item["end"]))
                else:
                    timing["pause_not_deducted"].append({"interval_id": item["interval_id"], "pause_reason": item["pause_reason"]})
            pause_seconds = _union_seconds(_clip(deducted, started, ended))
            total_seconds = (ended - started).total_seconds()
            active_spans = [(i["start"], i["end"]) for i in intervals if i["activity"] in C.USER_ACTIVE_ACTIVITIES]
            timing.update(
                {
                    "started_at": started.isoformat(),
                    "ended_at": ended.isoformat(),
                    "end_to_end_minutes": _minutes(max(0.0, total_seconds - pause_seconds)),
                    # 主动时间同样扣掉预登记暂停：参与者报「10:00–10:40 在做」又报「10:20–10:25 暂停」，
                    # 两条都算数就会把暂停既扣出端到端又留在主动时间里。
                    "user_active_minutes": _minutes(_union_seconds(_subtract(active_spans, deducted))),
                    "model_wait_minutes": _minutes(_union_seconds([(i["start"], i["end"]) for i in intervals if i["activity"] == C.ACTIVITY_MODEL_WAIT])),
                    "pause_deducted_minutes": _minutes(pause_seconds),
                    "certainty": C.CERTAINTY_ESTIMATED if any(i["clock_source"] == C.CLOCK_MANUAL_ESTIMATE for i in intervals) else C.CERTAINTY_KNOWN,
                    "client_only": not trusted_anchor,
                }
            )
            if not trusted_anchor:
                limitations.add(f"timing_client_only:{task_id}")

    return {
        "task_id": task_id,
        "condition": condition,
        "participant_id": assignment.get("participant_id"),
        "case_id": assignment.get("case_id"),
        "case_version": str(assignment.get("case_version")) if assignment.get("case_version") is not None else None,
        "assigned_at": payload.get("assigned_at"),
        "deadline": deadline.isoformat() if deadline else None,
        "completion_condition": payload.get("completion_condition"),
        "terminal_state": terminal_state,
        "terminal_at": terminal_at.isoformat() if terminal_at else None,
        "terminal_source": terminal_source,
        "terminal_reason": terminal_event["payload"].get("terminal_reason") if terminal_event else None,
        "timed_out": timed_out,
        "attempts": attempt_rows,
        "attempt_count": len(attempt_rows),
        "failed_attempt_count": sum(1 for row in attempt_rows if row["failed"]),
        "degraded_attempt_count": sum(1 for row in attempt_rows if row["degraded"]),
        "completion_evidence": completion_evidence,
        "timing": timing,
        "quality": None,  # 由 _quality_for_task 填
        "event_ids": sorted(str(e["event_id"]) for e in task_events),
    }


def _quality_for_task(
    task_id: str,
    task_events: Sequence[Mapping[str, Any]],
    *,
    consent: dict[str, list[tuple[datetime, str, frozenset[str]]]],
    participant: str | None,
    limitations: set[str],
    exclusions: list[dict[str, Any]],
    rule_versions: Mapping[str, str],
) -> dict[str, Any]:
    reviews: list[Mapping[str, Any]] = []
    consent_unknown = False
    for event in task_events:
        if event["event_type"] != "quality_reviewed" or event.get("source_channel") != C.SOURCE_MANUAL:
            continue
        if participant is not None:
            scopes = _scopes_at(consent, participant, event_time(event))
            # 没有同意记录 ≠ 已同意盲审。缺记录与明确未授权同样不能进质量读数，
            # 否则「缺同意」只留一条 limitation，判据照常算出 pass（评审 PV1）。
            if scopes is None or "blind_review" not in scopes:
                reason = "blind_review_consent_unknown" if scopes is None else "blind_review_consent_missing"
                consent_unknown = consent_unknown or scopes is None
                exclusions.append(
                    {
                        "id": str(event["event_id"]),
                        "reason": reason,
                        "rule_version": rule_versions.get("consent_scope", ""),
                    }
                )
                continue
        reviews.append(event)
    if not reviews:
        limitations.add(f"quality_unknown:{task_id}")
        return {
            "status": "unknown",
            "reason": "blind_review_consent_unknown" if consent_unknown else "no_independent_review",
        }
    adjudicated = [r for r in reviews if r["payload"].get("adjudication_ref")]
    pool = adjudicated or reviews
    chosen = sorted(pool, key=lambda e: (event_time(e), str(e["event_id"])))[-1]
    payload = chosen["payload"]
    dims = {name: int(payload["dimensions"][name]) for name in C.RUBRIC_DIMENSIONS}
    return {
        "status": "reviewed",
        "event_id": chosen["event_id"],
        "rubric_version": payload.get("rubric_version"),
        "reviewer_id": payload.get("reviewer_id"),
        "blinded": bool(payload.get("blinded")),
        "artifact_refs": list(payload.get("artifact_refs") or ()),
        "dimensions": dims,
        "total": sum(dims.values()),
        "max_total": C.RUBRIC_MAX_PER_DIMENSION * len(C.RUBRIC_DIMENSIONS),
        "severe_error_count": int(payload.get("severe_error_count")),
        "adjudication_ref": payload.get("adjudication_ref"),
        "review_count": len(reviews),
    }


# --------------------------------------------------------------------------
# 费用
# --------------------------------------------------------------------------


def _aggregate_costs(
    cost_events: Sequence[Mapping[str, Any]],
    tasks: Mapping[str, Mapping[str, Any]],
    *,
    limitations: set[str],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for event in cost_events:
        raw = dict(event["payload"]["cost_item"])
        raw["event_id"] = event["event_id"]
        raw["source_channel"] = event.get("source_channel")
        raw["task_id"] = event.get("task_id")
        items.append(raw)

    # 分组：同一 (component, run_id 或 task_id) 内按覆盖粗细选一层。
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in items:
        anchor = str(item.get("run_id") or item.get("task_id") or "pilot")
        groups.setdefault((str(item.get("component")), anchor), []).append(item)

    selected: list[dict[str, Any]] = []
    for (component, anchor), members in sorted(groups.items()):
        scoped = [m for m in members if m.get("coverage_scope") in C.COVERAGE_SCOPES]
        for member in members:
            if member.get("coverage_scope") not in C.COVERAGE_SCOPES:
                member["selected"] = False
                member["dedup_reason"] = "coverage_unknown"
                member["certainty"] = C.CERTAINTY_UNKNOWN
                limitations.add(f"cost_coverage_unknown:{member.get('cost_id')}")
                selected.append(member)
        if not scoped:
            continue
        present = {m["coverage_scope"] for m in scoped}
        coarsest = next(scope for scope in C.COVERAGE_SCOPES_COARSE_TO_FINE if scope in present)
        for member in scoped:
            if member["coverage_scope"] == coarsest:
                member["selected"] = True
                member["dedup_reason"] = None
                selected.append(member)
            else:
                member["selected"] = False
                member["dedup_reason"] = f"covered_by_{coarsest}"
                selected.append(member)

    known = [m for m in selected if m.get("selected") and m.get("certainty") == C.CERTAINTY_KNOWN]
    estimated = [m for m in selected if m.get("selected") and m.get("certainty") == C.CERTAINTY_ESTIMATED]
    unknown: list[dict[str, Any]] = []
    for member in selected:
        if member.get("selected") is False and member.get("dedup_reason") != "coverage_unknown":
            continue
        if member.get("certainty") == C.CERTAINTY_UNKNOWN or member.get("dedup_reason") == "coverage_unknown":
            reason = "coverage_unknown" if member.get("dedup_reason") == "coverage_unknown" else (
                "usage_without_rate" if member.get("quantity") is not None and not member.get("rate_version") else "amount_unknown"
            )
            unknown.append(
                {
                    "component": member.get("component"),
                    "cost_id": member.get("cost_id"),
                    "run_id": member.get("run_id"),
                    "attempt_id": member.get("attempt_id"),
                    "quantity": member.get("quantity"),
                    "unit": member.get("unit"),
                    "reason": reason,
                }
            )
            limitations.add(f"cost_unknown:{member.get('cost_id')}")
        elif member.get("quantity") is None and member.get("component") in {"writer_model", "review_model", "other_model"}:
            # 金额有、用量没有：账能对，用量对不上（自审缺用量）。
            limitations.add(f"usage_missing:{member.get('cost_id')}")

    # 派生缺口：有尝试没账、有人工救援没工时费。预算与未观察到的调用都不作零费用依据。
    costed_runs = {str(m.get("run_id")) for m in selected if m.get("run_id")}
    costed_attempts = {str(m.get("attempt_id")) for m in selected if m.get("attempt_id")}
    for task in tasks.values():
        for attempt in task.get("attempts") or ():
            if attempt["run_id"] in costed_runs or attempt["attempt_id"] in costed_attempts:
                continue
            unknown.append(
                {
                    "component": "retry" if attempt["failed"] else "writer_model",
                    "cost_id": None,
                    "run_id": attempt["run_id"],
                    "attempt_id": attempt["attempt_id"],
                    "quantity": None,
                    "unit": None,
                    "reason": "no_usage_evidence_for_attempt",
                }
            )
            limitations.add(f"cost_unknown:attempt:{attempt['attempt_id']}")
    rescue_minutes = sum(float(task["timing"].get("manual_rescue_minutes") or 0.0) for task in tasks.values())
    if rescue_minutes > 0 and not any(m.get("component") == "manual_rescue" for m in selected):
        unknown.append(
            {
                "component": "manual_rescue",
                "cost_id": None,
                "run_id": None,
                "attempt_id": None,
                "quantity": round(rescue_minutes, 2),
                "unit": "minutes",
                "reason": "manual_time_uncosted",
            }
        )
        limitations.add("cost_unknown:manual_rescue")

    unknown.sort(key=lambda item: (str(item["component"]), str(item.get("cost_id")), str(item.get("attempt_id"))))
    return {
        "cost_items": sorted(selected, key=lambda m: (str(m.get("component")), str(m.get("cost_id")))),
        "known_cost_by_currency": _sum_by_currency(known),
        "estimated_cost_by_currency": _sum_by_currency(estimated),
        "unknown_cost_components": unknown,
        "manual_minutes": {"rescue": round(rescue_minutes, 2)},
    }


# --------------------------------------------------------------------------
# 配对
# --------------------------------------------------------------------------


def measure_pair(
    events: Iterable[Any],
    protocol: Mapping[str, Any],
    evidence_reader: EvidenceReader,
    *,
    case_pair_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """把一对配对任务的事件算成 MeasurementReceipt（measurement-receipt/v1）。

    ``events`` 可包含该配对的全部事件与同 owner 的参与者级事件（如 consent）。
    传入别的配对的事件会让收据 ``invalid``（case_pair_mismatch），不会被静默丢弃。
    """
    proto = validate_protocol(protocol)
    p_hash = protocol_hash(proto)
    pauses_allowed = allowed_pause_reasons(proto)
    rule_versions = exclusion_rule_versions(proto)
    cases = case_index(proto)
    pairs = pair_index(proto)
    prepared: PreparedEvents = prepare_events(events, protocol=proto)
    accepted = prepared.accepted

    invalid: list[dict[str, str]] = []
    limitations: set[str] = set()
    exclusions: list[dict[str, Any]] = []

    owners = sorted({str(e["owner_user_id"]) for e in accepted})
    if len(owners) > 1:
        invalid.append({"code": "owner_mismatch", "detail": ",".join(owners)})
    owner = owners[0] if owners else None
    pilots = sorted({str(e["pilot_id"]) for e in accepted})
    if len(pilots) > 1:
        invalid.append({"code": "pilot_mismatch", "detail": ",".join(pilots)})
    if pilots and pilots[0] != proto["pilot_id"]:
        invalid.append({"code": "pilot_mismatch", "detail": f"{pilots[0]} != protocol {proto['pilot_id']}"})

    pair_ids = sorted({str(e["case_pair_id"]) for e in accepted if e.get("case_pair_id")})
    pair = case_pair_id
    if pair is None:
        if len(pair_ids) == 1:
            pair = pair_ids[0]
        elif not pair_ids:
            invalid.append({"code": "no_case_pair", "detail": "no accepted event carries a case_pair_id"})
        else:
            invalid.append({"code": C.ERR_PAIR_MISMATCH, "detail": ",".join(pair_ids)})
    else:
        foreign = [p for p in pair_ids if p != pair]
        if foreign:
            invalid.append({"code": C.ERR_PAIR_MISMATCH, "detail": ",".join(foreign)})
    if pair is not None and pair not in pairs:
        invalid.append({"code": "unknown_case_pair", "detail": pair})
    for conflict in prepared.conflicts:
        invalid.append({"code": "conflicting_event_id", "detail": str(conflict["event_id"])})
        exclusions.append({"id": str(conflict["event_id"]), "reason": "conflicting_event_id", "rule_version": rule_versions.get("conflicting_event_id", "")})

    pair_events = [e for e in accepted if e.get("case_pair_id") in (pair, None)]
    consent = _consent_timeline(pair_events)

    # ---- 分配 ----
    assignments: dict[str, dict[str, Any]] = {}
    for event in pair_events:
        if event["event_type"] != "assignment_created" or event.get("case_pair_id") != pair:
            continue
        condition = str(event["payload"].get("condition"))
        if condition in assignments:
            invalid.append({"code": "duplicate_assignment", "detail": condition})
            continue
        assignments[condition] = event
    for condition in (C.CONDITION_ORIGINAL, C.CONDITION_ASSISTED):
        if condition not in assignments:
            limitations.add(f"missing_assignment:{condition}")
    if len(assignments) == 2:
        original, assisted = assignments[C.CONDITION_ORIGINAL], assignments[C.CONDITION_ASSISTED]
        if original.get("participant_id") == assisted.get("participant_id") and original.get("case_id") == assisted.get("case_id"):
            invalid.append({"code": "same_participant_same_case", "detail": str(original.get("case_id"))})
    pair_def = pairs.get(pair or "", {})
    for condition, assignment in assignments.items():
        case_id = str(assignment.get("case_id"))
        if pair_def and case_id not in (pair_def.get("case_ids") or ()):
            invalid.append({"code": "case_not_in_pair", "detail": f"{condition}:{case_id}"})
        expected_version = str(cases.get(case_id, {}).get("case_version", ""))
        if case_id in cases and str(assignment.get("case_version")) != expected_version:
            invalid.append({"code": "case_version_mismatch", "detail": f"{condition}:{case_id}@{assignment.get('case_version')}"})
        if not assignment.get("task_id"):
            invalid.append({"code": "assignment_without_task", "detail": condition})

    # ---- 任务事件归属与一致性 ----
    task_ctx: dict[str, dict[str, Any]] = {str(a["task_id"]): a for a in assignments.values() if a.get("task_id")}
    task_events: dict[str, list[dict[str, Any]]] = {task_id: [] for task_id in task_ctx}
    task_by_run: dict[str, str] = {}
    for event in pair_events:
        task_id = event.get("task_id")
        if not task_id or event["event_type"] == "assignment_created":
            continue
        task_id = str(task_id)
        if task_id not in task_ctx:
            # 带本配对号却对不上任何分配的任务才是孤儿；参与者级事件（无配对号）属于别的
            # 任务或试点级信号，不在这里记。
            if event.get("case_pair_id") == pair:
                limitations.add(f"orphan_task_events:{task_id}")
            continue
        assignment = task_ctx[task_id]
        if event.get("assistance_condition") not in (None, assignment.get("assistance_condition")):
            invalid.append({"code": "condition_mismatch", "detail": f"{event['event_id']}"})
        if event.get("case_version") is not None and str(event["case_version"]) != str(assignment.get("case_version")):
            invalid.append({"code": "case_version_mismatch", "detail": f"{event['event_id']}"})
        participant = assignment.get("participant_id")
        if participant is not None:
            scopes = _scopes_at(consent, str(participant), event_time(event))
            if scopes is None:
                limitations.add(f"consent_unknown:{participant}")
            elif not C.REQUIRED_MEASUREMENT_SCOPES <= scopes:
                exclusions.append({"id": str(event["event_id"]), "reason": "consent_withdrawn", "rule_version": rule_versions.get("consent_withdrawn", "")})
                continue
        task_events[task_id].append(event)
        for run_id in event.get("run_ids") or ():
            task_by_run[str(run_id)] = task_id

    # ---- 逐任务测量 ----
    tasks: dict[str, dict[str, Any]] = {}
    if owner is not None:
        for condition, assignment in sorted(assignments.items()):
            task_id = str(assignment.get("task_id") or "")
            if not task_id:
                continue
            measured = _measure_task(
                assignment,
                task_events.get(task_id, []),
                owner=owner,
                reader=evidence_reader,
                pauses_allowed=pauses_allowed,
                invalid=invalid,
                limitations=limitations,
            )
            measured["quality"] = _quality_for_task(
                task_id,
                task_events.get(task_id, []),
                consent=consent,
                participant=str(assignment["participant_id"]) if assignment.get("participant_id") else None,
                limitations=limitations,
                exclusions=exclusions,
                rule_versions=rule_versions,
            )
            tasks[condition] = measured

    # ---- 费用：任务级 + run 级 + 配对级 ----
    cost_events: list[dict[str, Any]] = []
    for event in pair_events:
        if event["event_type"] != "cost_recorded":
            continue
        item = event["payload"]["cost_item"]
        run_id = item.get("run_id")
        if event.get("task_id") and str(event["task_id"]) in task_ctx:
            cost_events.append(event)
        elif run_id and str(run_id) in task_by_run:
            cost_events.append(event)
        elif event.get("case_pair_id") == pair:
            cost_events.append(event)
    costs = _aggregate_costs(cost_events, tasks, limitations=limitations)

    # ---- 配对级读数 ----
    original = tasks.get(C.CONDITION_ORIGINAL)
    assisted = tasks.get(C.CONDITION_ASSISTED)
    ratio: float | None = None
    ratio_reason: str | None = None
    if original is None or assisted is None:
        ratio_reason = "missing_condition"
    else:
        orig_minutes = original["timing"].get("end_to_end_minutes")
        asst_minutes = assisted["timing"].get("end_to_end_minutes")
        if orig_minutes is None or asst_minutes is None:
            ratio_reason = "timing_missing"
        elif orig_minutes == 0:
            rule_version = rule_versions.get("original_time_zero")
            if rule_version is None:
                limitations.add("original_time_zero_unexcludable")
                ratio_reason = "original_time_zero_no_rule"
            else:
                exclusions.append({"id": pair, "reason": "original_time_zero", "rule_version": rule_version})
                ratio_reason = "original_time_zero"
        else:
            ratio = round((orig_minutes - asst_minutes) / orig_minutes, 4)
    quality_block: dict[str, Any] = {
        "original": original["quality"] if original else None,
        "assisted": assisted["quality"] if assisted else None,
        "assisted_not_lower": None,
        "severe_error_count_assisted": None,
        "reason": None,
    }
    if original and assisted and original["quality"]["status"] == "reviewed" and assisted["quality"]["status"] == "reviewed":
        quality_block["assisted_not_lower"] = assisted["quality"]["total"] >= original["quality"]["total"]
        quality_block["severe_error_count_assisted"] = assisted["quality"]["severe_error_count"]
        if not (original["quality"]["blinded"] and assisted["quality"]["blinded"]):
            limitations.add("unblinded_review")
    else:
        quality_block["reason"] = "review_missing"
        if assisted and assisted["quality"]["status"] == "reviewed":
            quality_block["severe_error_count_assisted"] = assisted["quality"]["severe_error_count"]

    denominator_ids = sorted(task["task_id"] for task in tasks.values())
    numerator_ids = sorted(task["task_id"] for task in tasks.values() if task["terminal_state"] == C.TERMINAL_COMPLETED)

    kinds = [str(e["provenance"]["kind"]) for e in pair_events]
    mix = {kind: kinds.count(kind) for kind in sorted(C.PROVENANCE_KINDS)}
    provenance_kind = (
        C.PROVENANCE_SYNTHETIC if mix[C.PROVENANCE_SYNTHETIC] else C.PROVENANCE_IMPORTED if mix[C.PROVENANCE_IMPORTED] else C.PROVENANCE_OBSERVED
    )

    if invalid:
        status = C.RECEIPT_INVALID
    elif any(lim.startswith(_BLOCKING_LIMITATION_PREFIXES) for lim in limitations):
        status = C.RECEIPT_INCOMPLETE
    else:
        status = C.RECEIPT_VALID

    input_ids = sorted(str(e["event_id"]) for e in pair_events)
    receipt: dict[str, Any] = {
        "schema_version": C.RECEIPT_SCHEMA,
        "receipt_id": None,
        "owner_user_id": owner,
        "pilot_id": pilots[0] if pilots else None,
        "case_pair_id": pair,
        "category": pair_def.get("category") if pair_def else None,
        "protocol_version": proto["protocol_version"],
        "protocol_hash": p_hash,
        "generated_at": _now_iso(now),
        "input_event_ids": input_ids,
        "input_hash": hash_ids([f"{eid}:{prepared.content_hashes.get(eid, '')}" for eid in input_ids]),
        "source_versions": {
            "code_shas": sorted({str(e["source_version"].get("code_sha")) for e in pair_events}),
            "protocol_versions": sorted({str(e["source_version"].get("protocol_version")) for e in pair_events}),
            "artifact_hashes": sorted({str(e["source_version"].get("artifact_hash")) for e in pair_events if e["source_version"].get("artifact_hash")}),
        },
        "status": status,
        "invalid_reasons": sorted(invalid, key=lambda item: (item["code"], item["detail"])),
        "limitations": sorted(limitations),
        "provenance": {"kind": provenance_kind, "mix": mix, "synthetic": provenance_kind == C.PROVENANCE_SYNTHETIC},
        "participants": sorted({str(a["participant_id"]) for a in assignments.values() if a.get("participant_id")}),
        "tasks": tasks,
        "timing": {
            "original": original["timing"] if original else None,
            "assisted": assisted["timing"] if assisted else None,
            "time_saving_ratio": ratio,
            "time_saving_reason": ratio_reason,
        },
        "quality": quality_block,
        "cost_items": costs["cost_items"],
        "known_cost_by_currency": costs["known_cost_by_currency"],
        "estimated_cost_by_currency": costs["estimated_cost_by_currency"],
        "unknown_cost_components": costs["unknown_cost_components"],
        "manual_minutes": costs["manual_minutes"],
        "numerator_ids": numerator_ids,
        "denominator_ids": denominator_ids,
        "exclusions": sorted(exclusions, key=lambda item: (str(item["reason"]), str(item["id"]))),
        "event_accounting": prepared.accounting(),
    }
    # 内容 id 只看测量语义：生成时间与入账审计（重复 / 拒收清单）不改变「这对配对算出了什么」。
    receipt["receipt_id"] = content_id("mr", receipt, drop_keys=frozenset({"generated_at", "receipt_id", "event_accounting"}))
    return receipt


__all__ = ["measure_pair"]

"""ProductValueEvent（product-value-event/v1）的校验、幂等与排序。

三条纪律，都是从既有台账踩过的坑里搬来的：

- **时间带时区**（同 ``SelfUseEvent.validated``）：``event_at`` 是发生时间、
  ``recorded_at`` 是登记时间，补录时两者都保留，不把补录伪装成实时事件。
- **同 ID 同内容幂等，不同内容拒收**（同 ``RunStore.append_stream_event`` 的
  conflicting duplicate 规则）：内容摘要不含 ``recorded_at``，因为重试同一条上报
  会拿到不同的接收时钟，那不算改内容。
- **前端不能自报成功 / 质量 / 金额**：由事件类型 × 来源渠道白名单机械拦住，
  不靠读 payload 猜意图。

``validate_event`` 是纯函数：不读磁盘、不看环境变量、不判定来源真伪（那是 06
按接收入口做的事）。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from intelligence.services.product_value import contracts as C
from intelligence.services.product_value.hashing import content_hash
from intelligence.services.product_value.protocol import protocol_hash, rubric_version

_ID_MAX_LEN = 128
# 内容摘要不含接收时钟：重试同一条上报不算改内容。
_CONTENT_DROP_KEYS = frozenset({"recorded_at"})


@dataclass(frozen=True)
class Issue:
    code: str
    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "field": self.field, "message": self.message}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    issues: tuple[Issue, ...]
    normalized: dict[str, Any] | None
    content_hash: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
            "content_hash": self.content_hash,
        }


def parse_ts(value: Any) -> datetime | None:
    """ISO 时间串 → 带时区的 datetime；缺时区或不可解析返回 None。"""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def parse_date_or_ts(value: Any) -> datetime | None:
    """允许纯日期（按 UTC 零点）或带时区时间；用于 service_period 这类日粒度字段。"""
    if isinstance(value, str) and len(value.strip()) == 10:
        try:
            day = date.fromisoformat(value.strip())
        except ValueError:
            return None
        from datetime import timezone

        return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return parse_ts(value)


def event_time(event: Mapping[str, Any]) -> datetime:
    parsed = parse_ts(event.get("event_at"))
    if parsed is None:
        raise ValueError(f"event {event.get('event_id')!r} has no timezone-aware event_at")
    return parsed


class _Collector:
    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def add(self, code: str, field_name: str, message: str) -> None:
        self.issues.append(Issue(code, field_name, message))

    def ts(self, value: Any, field_name: str, *, allow_null: bool = False) -> datetime | None:
        if value is None:
            if not allow_null:
                self.add(C.ERR_MISSING_FIELD, field_name, "timestamp required")
            return None
        if not isinstance(value, str):
            self.add(C.ERR_TIMESTAMP_INVALID, field_name, "timestamp must be an ISO string")
            return None
        parsed = parse_ts(value)
        if parsed is None:
            try:
                naive = datetime.fromisoformat(value.strip())
            except ValueError:
                self.add(C.ERR_TIMESTAMP_INVALID, field_name, f"not an ISO datetime: {value!r}")
                return None
            if naive.tzinfo is None:
                self.add(C.ERR_TIMESTAMP_NAIVE, field_name, "timestamp must carry a timezone offset")
            return None
        return parsed

    def ident(self, value: Any, field_name: str, *, allow_null: bool = False) -> str | None:
        if value is None:
            if not allow_null:
                self.add(C.ERR_MISSING_FIELD, field_name, "identifier required")
            return None
        if not isinstance(value, str):
            self.add(C.ERR_ID_INVALID, field_name, "identifier must be a string")
            return None
        text = value.strip()
        if not text or len(text) > _ID_MAX_LEN or any(ch.isspace() for ch in text):
            self.add(C.ERR_ID_INVALID, field_name, "identifier must be non-empty, ≤128 chars, no whitespace")
            return None
        return text

    def enum(self, value: Any, field_name: str, allowed: frozenset[str], *, allow_null: bool = False) -> str | None:
        if value is None and allow_null:
            return None
        if not isinstance(value, str) or value not in allowed:
            self.add(C.ERR_ENUM_INVALID, field_name, f"must be one of {sorted(allowed)}; got {value!r}")
            return None
        return value

    def number(self, value: Any, field_name: str, *, allow_null: bool = True) -> float | None:
        if value is None:
            if not allow_null:
                self.add(C.ERR_MISSING_FIELD, field_name, "number required")
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.add(C.ERR_TYPE_INVALID, field_name, "must be a number")
            return None
        if value < 0:
            self.add(C.ERR_TYPE_INVALID, field_name, "must be non-negative")
            return None
        return float(value)


def _validate_object_ref(ref: Any, field_name: str, owner: str | None, col: _Collector) -> None:
    if not isinstance(ref, Mapping):
        col.add(C.ERR_REF_INVALID, field_name, "object_ref must be a mapping")
        return
    for key in C.OBJECT_REF_FIELDS:
        if key not in ref:
            col.add(C.ERR_REF_INVALID, f"{field_name}.{key}", "object_ref field missing")
    col.ident(ref.get("kind"), f"{field_name}.kind")
    col.ident(ref.get("id"), f"{field_name}.id")
    # 缺命名空间不能靠文本猜（总合同 §5.3）。
    col.ident(ref.get("namespace"), f"{field_name}.namespace")
    version = ref.get("version_or_hash")
    if version is None:
        if not isinstance(ref.get("reason"), str) or not ref.get("reason"):
            col.add(C.ERR_REF_INVALID, f"{field_name}.version_or_hash", "null version_or_hash needs a reason")
    elif not isinstance(version, str) or not version.strip():
        col.add(C.ERR_REF_INVALID, f"{field_name}.version_or_hash", "must be a non-empty string or null+reason")
    scope = ref.get("scope")
    if scope is not None and not isinstance(scope, Mapping):
        col.add(C.ERR_REF_INVALID, f"{field_name}.scope", "scope must be a mapping or null")
    elif isinstance(scope, Mapping):
        scoped_owner = scope.get("owner_user_id")
        if scoped_owner is not None and owner is not None and scoped_owner != owner:
            col.add(C.ERR_REF_CROSS_OWNER, f"{field_name}.scope.owner_user_id", "reference crosses owner boundary")


def _validate_cost_item(item: Any, col: _Collector) -> None:
    field_name = "payload.cost_item"
    if not isinstance(item, Mapping):
        col.add(C.ERR_COST_ITEM_INVALID, field_name, "cost_item must be a mapping")
        return
    for key in C.COST_ITEM_FIELDS:
        if key not in item:
            col.add(C.ERR_COST_ITEM_INVALID, f"{field_name}.{key}", "cost_item field missing")
    col.ident(item.get("cost_id"), f"{field_name}.cost_id")
    col.enum(item.get("component"), f"{field_name}.component", C.COST_COMPONENTS)
    col.enum(item.get("coverage_scope"), f"{field_name}.coverage_scope", C.COVERAGE_SCOPES, allow_null=True)
    certainty = col.enum(item.get("certainty"), f"{field_name}.certainty", C.CERTAINTIES)
    amount = col.number(item.get("amount"), f"{field_name}.amount")
    col.number(item.get("quantity"), f"{field_name}.quantity")
    currency = item.get("currency")
    if currency is not None and (not isinstance(currency, str) or not currency.strip()):
        col.add(C.ERR_COST_ITEM_INVALID, f"{field_name}.currency", "currency must be a non-empty string or null")
    if certainty in {C.CERTAINTY_KNOWN, C.CERTAINTY_ESTIMATED}:
        if amount is None or currency is None:
            col.add(
                C.ERR_COST_ITEM_INVALID,
                f"{field_name}.certainty",
                f"{certainty} cost needs amount and currency; use certainty=unknown when only usage is known",
            )
    if certainty == C.CERTAINTY_KNOWN and not item.get("evidence_ref"):
        col.add(C.ERR_COST_ITEM_INVALID, f"{field_name}.evidence_ref", "known cost needs an evidence_ref")


def _validate_payload(event: Mapping[str, Any], spec: C.EventTypeSpec, protocol: Mapping[str, Any] | None, col: _Collector) -> None:
    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        col.add(C.ERR_TYPE_INVALID, "payload", "payload must be a mapping")
        return
    event_type = event.get("event_type")
    channel = event.get("source_channel")
    for key in C.PAYLOAD_COMMON_FIELDS:
        if key not in payload or payload.get(key) in (None, ""):
            col.add(C.ERR_PAYLOAD_MISSING_FIELD, f"payload.{key}", "required on every payload; do not infer initiative")
    for key in spec.payload_fields:
        if key not in payload:
            col.add(C.ERR_PAYLOAD_MISSING_FIELD, f"payload.{key}", f"required for {event_type}")
    if channel == C.SOURCE_MANUAL:
        for key in C.MANUAL_IMPORT_FIELDS:
            if not payload.get(key):
                col.add(C.ERR_MANUAL_IMPORT_EVIDENCE, f"payload.{key}", "manual import must carry importer_id/evidence_ref/evidence_hash")

    task_id = event.get("task_id")
    payload_task = payload.get("task_id")
    if payload_task is not None and task_id is not None and payload_task != task_id:
        col.add(C.ERR_TASK_MISMATCH, "payload.task_id", "payload.task_id differs from event.task_id")

    if event_type == "time_interval":
        start = col.ts(payload.get("start"), "payload.start")
        end = col.ts(payload.get("end"), "payload.end")
        if start is not None and end is not None and end < start:
            col.add(C.ERR_INTERVAL_NEGATIVE, "payload.end", "interval end precedes start")
        activity = col.enum(payload.get("activity"), "payload.activity", C.ACTIVITIES)
        clock = col.enum(payload.get("clock_source"), "payload.clock_source", C.CLOCK_SOURCES)
        if channel == C.SOURCE_FRONTEND and clock not in (None, C.CLOCK_CLIENT):
            col.add(C.ERR_SOURCE_NOT_ALLOWED, "payload.clock_source", "frontend may only report client clock")
        if channel == C.SOURCE_MANUAL and clock not in (None, C.CLOCK_MANUAL_ACTUAL, C.CLOCK_MANUAL_ESTIMATE):
            col.add(C.ERR_SOURCE_NOT_ALLOWED, "payload.clock_source", "manual import must declare manual_actual or manual_estimate")
        if channel == C.SOURCE_SERVER and clock not in (None, C.CLOCK_SERVER, C.CLOCK_RUN):
            col.add(C.ERR_SOURCE_NOT_ALLOWED, "payload.clock_source", "server intervals use server or run clock")
        if activity == C.ACTIVITY_PAUSE and not payload.get("pause_reason"):
            col.add(C.ERR_PAYLOAD_MISSING_FIELD, "payload.pause_reason", "pause needs a pause_reason")
    elif event_type == "quality_reviewed":
        dims = payload.get("dimensions")
        if not isinstance(dims, Mapping):
            col.add(C.ERR_DIMENSION_OUT_OF_RANGE, "payload.dimensions", "dimensions must be a mapping")
        else:
            for name in C.RUBRIC_DIMENSIONS:
                score = dims.get(name)
                if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= C.RUBRIC_MAX_PER_DIMENSION:
                    col.add(C.ERR_DIMENSION_OUT_OF_RANGE, f"payload.dimensions.{name}", f"score must be int in [0,{C.RUBRIC_MAX_PER_DIMENSION}]")
            extra = set(dims) - set(C.RUBRIC_DIMENSIONS)
            if extra:
                col.add(C.ERR_DIMENSION_OUT_OF_RANGE, "payload.dimensions", f"unknown dimensions {sorted(extra)}")
        severe = payload.get("severe_error_count")
        if isinstance(severe, bool) or not isinstance(severe, int) or severe < 0:
            col.add(C.ERR_TYPE_INVALID, "payload.severe_error_count", "must be a non-negative int")
        if not isinstance(payload.get("blinded"), bool):
            col.add(C.ERR_TYPE_INVALID, "payload.blinded", "must be a boolean")
        col.ident(payload.get("reviewer_id"), "payload.reviewer_id")
        declared = payload.get("rubric_version")
        if protocol is not None and declared != rubric_version(protocol):
            col.add(C.ERR_RUBRIC_VERSION, "payload.rubric_version", "rubric_version differs from frozen protocol")
    elif event_type == "cost_recorded":
        _validate_cost_item(payload.get("cost_item"), col)
    elif event_type == "consent_changed":
        scopes = payload.get("scopes")
        if not isinstance(scopes, list) or any(s not in C.CONSENT_SCOPES for s in scopes):
            col.add(C.ERR_ENUM_INVALID, "payload.scopes", f"scopes must be a subset of {sorted(C.CONSENT_SCOPES)}")
        col.enum(payload.get("action"), "payload.action", C.CONSENT_ACTIONS)
        col.ts(payload.get("effective_at"), "payload.effective_at")
    elif event_type == "payment_recorded":
        col.number(payload.get("amount"), "payload.amount", allow_null=False)
        col.ident(payload.get("currency"), "payload.currency")
        status = col.enum(payload.get("status"), "payload.status", C.PAYMENT_STATUSES)
        period = payload.get("service_period")
        if not isinstance(period, Mapping) or parse_date_or_ts(period.get("start")) is None or parse_date_or_ts(period.get("end")) is None:
            col.add(C.ERR_TIMESTAMP_INVALID, "payload.service_period", "service_period needs start/end dates")
        col.ident(payload.get("verified_by"), "payload.verified_by")
        if status == "refunded" and not payload.get("refunds_payment_ref"):
            col.add(C.ERR_PAYLOAD_MISSING_FIELD, "payload.refunds_payment_ref", "refund must reference the original payment")
    elif event_type in {"run_started", "run_finished"}:
        run_id = col.ident(payload.get("run_id"), "payload.run_id")
        col.ident(payload.get("attempt_id"), "payload.attempt_id")
        run_ids = event.get("run_ids")
        if run_id is not None and isinstance(run_ids, list) and run_id not in run_ids:
            col.add(C.ERR_REF_INVALID, "payload.run_id", "run_id must also be listed in event.run_ids")
        if not isinstance(payload.get("status"), str):
            col.add(C.ERR_TYPE_INVALID, "payload.status", "run status must be a string")
    elif event_type == "assignment_created":
        condition = col.enum(payload.get("condition"), "payload.condition", C.ASSISTANCE_CONDITIONS)
        if condition is not None and event.get("assistance_condition") not in (None, condition):
            col.add(C.ERR_CONDITION_INVALID, "payload.condition", "payload.condition differs from event.assistance_condition")
        if payload.get("case_pair_id") != event.get("case_pair_id"):
            col.add(C.ERR_PAIR_MISMATCH, "payload.case_pair_id", "payload.case_pair_id differs from event.case_pair_id")
        col.ts(payload.get("assigned_at"), "payload.assigned_at")
        col.ts(payload.get("deadline"), "payload.deadline")
        declared_hash = payload.get("protocol_hash")
        if not isinstance(declared_hash, str) or not declared_hash:
            col.add(C.ERR_PAYLOAD_MISSING_FIELD, "payload.protocol_hash", "assignment must carry the frozen protocol hash")
        elif protocol is not None and declared_hash != protocol_hash(protocol):
            col.add(C.ERR_PROTOCOL_HASH, "payload.protocol_hash", "assignment was created under a different frozen protocol")
    elif event_type == "reuse_observed":
        col.ts(payload.get("activation_at"), "payload.activation_at")
        reminders = payload.get("reminder_refs")
        if not isinstance(reminders, list):
            col.add(C.ERR_TYPE_INVALID, "payload.reminder_refs", "must be a list")
        else:
            for index, reminder in enumerate(reminders):
                if not isinstance(reminder, Mapping):
                    col.add(C.ERR_TYPE_INVALID, f"payload.reminder_refs[{index}]", "must be a mapping")
                    continue
                col.enum(reminder.get("kind"), f"payload.reminder_refs[{index}].kind", C.REMINDER_KINDS)
                col.ts(reminder.get("at"), f"payload.reminder_refs[{index}].at")
        window = payload.get("observation_window")
        if not isinstance(window, Mapping):
            col.add(C.ERR_TYPE_INVALID, "payload.observation_window", "must be a mapping with start/end")
        else:
            col.ts(window.get("start"), "payload.observation_window.start")
            col.ts(window.get("end"), "payload.observation_window.end")
        col.ts(payload.get("new_task_started_at"), "payload.new_task_started_at", allow_null=True)
    elif event_type in {"recheck_viewed", "recheck_completed"}:
        _validate_object_ref(payload.get("object_ref"), "payload.object_ref", event.get("owner_user_id"), col)
        if not isinstance(payload.get("evidence_refs"), list):
            col.add(C.ERR_TYPE_INVALID, "payload.evidence_refs", "must be a list")
    elif event_type == "manual_assistance":
        start = col.ts(payload.get("start"), "payload.start")
        end = col.ts(payload.get("end"), "payload.end")
        if start is not None and end is not None and end < start:
            col.add(C.ERR_INTERVAL_NEGATIVE, "payload.end", "assistance end precedes start")
    elif event_type == "exercise_submitted":
        col.ts(payload.get("submitted_at"), "payload.submitted_at")
    elif event_type in {"task_completed", "task_failed", "task_abandoned"}:
        if not isinstance(payload.get("completion_evidence_refs"), list):
            col.add(C.ERR_TYPE_INVALID, "payload.completion_evidence_refs", "must be a list")


def validate_event(event: Any, *, protocol: Mapping[str, Any] | None = None) -> ValidationResult:
    """校验一条事件。返回规范化副本与内容摘要；任何 issue 都让 ``ok=False``。

    传入 ``protocol`` 时额外核对协议版本 / 协议哈希 / 评分表版本；不传时只做合同校验。
    """
    col = _Collector()
    if not isinstance(event, Mapping):
        col.add(C.ERR_TYPE_INVALID, "", "event must be a mapping")
        return ValidationResult(False, tuple(col.issues), None, None)

    if event.get("schema_version") != C.EVENT_SCHEMA:
        col.add(C.ERR_SCHEMA_VERSION, "schema_version", f"expected {C.EVENT_SCHEMA!r}")

    gaps = event.get("gaps")
    gap_reasons: dict[str, str] = {}
    if gaps is not None:
        if not isinstance(gaps, list):
            col.add(C.ERR_TYPE_INVALID, "gaps", "gaps must be a list of {field, reason}")
        else:
            for gap in gaps:
                if isinstance(gap, Mapping) and isinstance(gap.get("field"), str) and isinstance(gap.get("reason"), str) and gap["reason"]:
                    gap_reasons[gap["field"]] = gap["reason"]
                else:
                    col.add(C.ERR_TYPE_INVALID, "gaps[]", "each gap needs field and non-empty reason")

    for name in C.TOP_LEVEL_FIELDS:
        if name not in event:
            col.add(C.ERR_MISSING_FIELD, name, "top-level field missing (use null + gaps reason when unknown)")
        elif event[name] is None:
            if name in C.NULLABLE_TOP_LEVEL_FIELDS:
                if name not in gap_reasons:
                    col.add(C.ERR_NULL_WITHOUT_REASON, name, "null must be explained in gaps")
            else:
                col.add(C.ERR_MISSING_FIELD, name, "field may not be null")

    col.ident(event.get("event_id"), "event_id")
    owner = col.ident(event.get("owner_user_id"), "owner_user_id")
    col.ident(event.get("pilot_id"), "pilot_id")
    col.ident(event.get("participant_id"), "participant_id", allow_null=True)
    col.ident(event.get("task_id"), "task_id", allow_null=True)
    col.ident(event.get("case_id"), "case_id", allow_null=True)
    col.ident(event.get("case_pair_id"), "case_pair_id", allow_null=True)
    if event.get("supersedes_event_id") is not None:
        col.ident(event.get("supersedes_event_id"), "supersedes_event_id")

    event_type = event.get("event_type")
    spec = C.EVENT_TYPES.get(event_type) if isinstance(event_type, str) else None
    if spec is None:
        col.add(C.ERR_UNKNOWN_EVENT_TYPE, "event_type", f"unknown event_type {event_type!r}")
    channel = col.enum(event.get("source_channel"), "source_channel", C.SOURCE_CHANNELS)
    if spec is not None and channel is not None and channel not in spec.sources:
        col.add(
            C.ERR_SOURCE_NOT_ALLOWED,
            "source_channel",
            f"{event_type} may not come from {channel}; allowed {sorted(spec.sources)}",
        )

    condition = event.get("assistance_condition")
    if condition is not None and condition not in C.ASSISTANCE_CONDITIONS:
        col.add(C.ERR_CONDITION_INVALID, "assistance_condition", f"must be one of {sorted(C.ASSISTANCE_CONDITIONS)}")

    col.ts(event.get("event_at"), "event_at")
    col.ts(event.get("recorded_at"), "recorded_at")

    provenance = event.get("provenance")
    if not isinstance(provenance, Mapping):
        col.add(C.ERR_PROVENANCE_INVALID, "provenance", "provenance must be a mapping")
    else:
        for key in C.PROVENANCE_FIELDS:
            if key not in provenance:
                col.add(C.ERR_PROVENANCE_INVALID, f"provenance.{key}", "provenance field missing")
        if provenance.get("kind") not in C.PROVENANCE_KINDS:
            col.add(C.ERR_PROVENANCE_INVALID, "provenance.kind", f"must be one of {sorted(C.PROVENANCE_KINDS)}")
        if not isinstance(provenance.get("source_ref"), str):
            col.add(C.ERR_PROVENANCE_INVALID, "provenance.source_ref", "must be a string")

    source_version = event.get("source_version")
    if not isinstance(source_version, Mapping):
        col.add(C.ERR_TYPE_INVALID, "source_version", "source_version must be a mapping")
    else:
        for key in C.SOURCE_VERSION_FIELDS:
            if key not in source_version:
                col.add(C.ERR_MISSING_FIELD, f"source_version.{key}", "source_version field missing")
        col.ident(source_version.get("code_sha"), "source_version.code_sha")
        declared_version = source_version.get("protocol_version")
        if not isinstance(declared_version, str) or not declared_version:
            col.add(C.ERR_MISSING_FIELD, "source_version.protocol_version", "protocol_version required")
        elif protocol is not None and declared_version != protocol.get("protocol_version"):
            col.add(C.ERR_PROTOCOL_VERSION, "source_version.protocol_version", "event was produced under another protocol version")

    run_ids = event.get("run_ids")
    if not isinstance(run_ids, list) or any(not isinstance(item, str) or not item for item in run_ids):
        col.add(C.ERR_TYPE_INVALID, "run_ids", "run_ids must be a list of non-empty strings")
    refs = event.get("object_refs")
    if not isinstance(refs, list):
        col.add(C.ERR_TYPE_INVALID, "object_refs", "object_refs must be a list")
    else:
        for index, ref in enumerate(refs):
            _validate_object_ref(ref, f"object_refs[{index}]", owner, col)

    if spec is not None:
        _validate_payload(event, spec, protocol, col)

    if col.issues:
        return ValidationResult(False, tuple(col.issues), None, None)

    normalized = deepcopy(dict(event))
    for name in ("event_id", "owner_user_id", "pilot_id", "participant_id", "task_id", "case_id", "case_pair_id"):
        if isinstance(normalized.get(name), str):
            normalized[name] = normalized[name].strip()
    if isinstance(normalized.get("case_version"), (int, float)) and not isinstance(normalized["case_version"], bool):
        normalized["case_version"] = str(normalized["case_version"])
    digest = content_hash(normalized, drop_keys=_CONTENT_DROP_KEYS)
    return ValidationResult(True, (), normalized, digest)


def _sort_key(event: Mapping[str, Any]) -> tuple[str, str, str]:
    stamp = event_time(event).astimezone().isoformat()
    return (stamp, str(event.get("case_version") or ""), str(event.get("event_id")))


@dataclass
class PreparedEvents:
    """校验 + 幂等 + 排序后的事件集合，以及一份可审计的入账清单。"""

    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    superseded: list[str] = field(default_factory=list)
    content_hashes: dict[str, str] = field(default_factory=dict)

    def accounting(self) -> dict[str, Any]:
        return {
            "accepted": len(self.accepted),
            "rejected": sorted(self.rejected, key=lambda item: str(item.get("event_id"))),
            "duplicates": sorted(set(self.duplicates)),
            "conflicts": sorted(self.conflicts, key=lambda item: str(item.get("event_id"))),
            "superseded": sorted(set(self.superseded)),
        }


def prepare_events(
    events: Iterable[Any],
    *,
    protocol: Mapping[str, Any] | None = None,
) -> PreparedEvents:
    """校验、去重、解冲突、应用修订、按发生时间排序。结果与输入顺序无关。

    - 同 ``event_id`` 同内容：只计一次（记 ``duplicates``）；
    - 同 ``event_id`` 不同内容：两份都不进入计算（记 ``conflicts``）——不能靠到达顺序
      挑一份，那会让结论依赖网络时序；
    - ``supersedes_event_id``：修订生效，被修订的原件退出计算（记 ``superseded``）。
    """
    prepared = PreparedEvents()
    by_id: dict[str, dict[str, dict[str, Any]]] = {}
    for index, raw in enumerate(events):
        result = validate_event(raw, protocol=protocol)
        if not result.ok or result.normalized is None or result.content_hash is None:
            event_id = raw.get("event_id") if isinstance(raw, Mapping) else None
            prepared.rejected.append(
                {
                    "event_id": event_id if isinstance(event_id, str) else f"<index:{index}>",
                    "issues": [issue.to_dict() for issue in result.issues],
                }
            )
            continue
        event_id = result.normalized["event_id"]
        bucket = by_id.setdefault(event_id, {})
        if result.content_hash in bucket:
            prepared.duplicates.append(event_id)
            continue
        bucket[result.content_hash] = result.normalized

    accepted: dict[str, dict[str, Any]] = {}
    for event_id, versions in by_id.items():
        if len(versions) > 1:
            prepared.conflicts.append({"event_id": event_id, "content_hashes": sorted(versions)})
            continue
        digest, normalized = next(iter(versions.items()))
        accepted[event_id] = normalized
        prepared.content_hashes[event_id] = digest

    for event_id, normalized in list(accepted.items()):
        target = normalized.get("supersedes_event_id")
        if isinstance(target, str) and target in accepted and target != event_id:
            prepared.superseded.append(target)
    for target in prepared.superseded:
        accepted.pop(target, None)
        prepared.content_hashes.pop(target, None)

    prepared.accepted = sorted(accepted.values(), key=_sort_key)
    return prepared


def load_events_jsonl(path: Any) -> list[dict[str, Any]]:
    """读 JSONL（空行跳过）。坏行原样保留为 ``{"_parse_error": ...}`` 让校验去拒收。"""
    import json
    from pathlib import Path

    out: list[dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            out.append({"_parse_error": f"line {line_no}: {exc.msg}"})
            continue
        out.append(row if isinstance(row, dict) else {"_parse_error": f"line {line_no}: not an object"})
    return out


__all__ = [
    "Issue",
    "PreparedEvents",
    "ValidationResult",
    "event_time",
    "load_events_jsonl",
    "parse_date_or_ts",
    "parse_ts",
    "prepare_events",
    "validate_event",
]

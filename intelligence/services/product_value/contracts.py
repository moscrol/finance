"""合同常量：ProductValueEvent / MeasurementReceipt / PilotSummary 的 schema 名、白名单与稳定错误码。

这是 05 轨与 06（Workbench 集成）之间的**交换合同**，字段名与取值一律用字符串
字面量声明，原因有二：

1. 06 用结构化 JSON 与本模块通信，不依赖共享 Python 基类（总合同 §5）；
2. 本仓 `check_unread_fields.py` 门禁把「作为字符串字面量出现过的属性名」视为可能
   被动态读取——合同字段就是要被别的进程读的，用字符串键是它的读法。

来源渠道（spec §3 表中的 F / S / M）：

- ``frontend``（F）：前端动作上报。只能表达意图与客户端计时，不能自报成功、
  质量或金额；
- ``server``（S）：服务端事实与计算，例如真实 run 的生命周期、接收时钟；
- ``manual_import``（M）：经权限校验的人工导入，必须带 ``importer_id`` /
  ``evidence_ref`` / ``evidence_hash``。

哪一档可信由 06 按接收入口与凭据判定并写入 ``source_channel``；客户端不能自选
``observed`` 或升级身份。本模块只校验「这个类型允许来自这个渠道吗」。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

EVENT_SCHEMA = "product-value-event/v1"
RECEIPT_SCHEMA = "measurement-receipt/v1"
SUMMARY_SCHEMA = "pilot-summary/v1"
PROTOCOL_SCHEMA = "pilot-protocol/v1"

SOURCE_FRONTEND = "frontend"
SOURCE_SERVER = "server"
SOURCE_MANUAL = "manual_import"
SOURCE_CHANNELS: frozenset[str] = frozenset({SOURCE_FRONTEND, SOURCE_SERVER, SOURCE_MANUAL})
# 便于文档与 06 对照 spec 表里的单字母写法。
SOURCE_CHANNEL_LETTER = {SOURCE_FRONTEND: "F", SOURCE_SERVER: "S", SOURCE_MANUAL: "M"}

PROVENANCE_OBSERVED = "observed"
PROVENANCE_IMPORTED = "imported"
PROVENANCE_SYNTHETIC = "synthetic"
PROVENANCE_KINDS: frozenset[str] = frozenset(
    {PROVENANCE_OBSERVED, PROVENANCE_IMPORTED, PROVENANCE_SYNTHETIC}
)
# 只有这两种能进入真人分母；synthetic 永远只改变工程状态。
REAL_PROVENANCE: frozenset[str] = frozenset({PROVENANCE_OBSERVED, PROVENANCE_IMPORTED})

CONDITION_ORIGINAL = "original"
CONDITION_ASSISTED = "assisted"
ASSISTANCE_CONDITIONS: frozenset[str] = frozenset({CONDITION_ORIGINAL, CONDITION_ASSISTED})

CERTAINTY_KNOWN = "known"
CERTAINTY_ESTIMATED = "estimated"
CERTAINTY_UNKNOWN = "unknown"
CERTAINTIES: frozenset[str] = frozenset({CERTAINTY_KNOWN, CERTAINTY_ESTIMATED, CERTAINTY_UNKNOWN})

# time_interval.activity：用户主动 / 查阅原资料（也算主动）/ 等模型 / 人工救援 / 暂停。
ACTIVITY_USER_ACTIVE = "user_active"
ACTIVITY_EXTERNAL_LOOKUP = "external_lookup"
ACTIVITY_MODEL_WAIT = "model_wait"
ACTIVITY_MANUAL_RESCUE = "manual_rescue"
ACTIVITY_PAUSE = "pause"
ACTIVITIES: frozenset[str] = frozenset(
    {
        ACTIVITY_USER_ACTIVE,
        ACTIVITY_EXTERNAL_LOOKUP,
        ACTIVITY_MODEL_WAIT,
        ACTIVITY_MANUAL_RESCUE,
        ACTIVITY_PAUSE,
    }
)
USER_ACTIVE_ACTIVITIES: frozenset[str] = frozenset({ACTIVITY_USER_ACTIVE, ACTIVITY_EXTERNAL_LOOKUP})

CLOCK_CLIENT = "client"
CLOCK_SERVER = "server"
CLOCK_RUN = "run"
CLOCK_MANUAL_ACTUAL = "manual_actual"
CLOCK_MANUAL_ESTIMATE = "manual_estimate"
CLOCK_SOURCES: frozenset[str] = frozenset(
    {CLOCK_CLIENT, CLOCK_SERVER, CLOCK_RUN, CLOCK_MANUAL_ACTUAL, CLOCK_MANUAL_ESTIMATE}
)

# 费用类别（spec §3 MeasurementReceipt.cost_items）。
COST_COMPONENTS: frozenset[str] = frozenset(
    {
        "writer_model",
        "review_model",
        "other_model",
        "tool",
        "retry",
        "manual_import",
        "manual_rescue",
        "manual_maintenance",
        "data_license",
        "hosting",
        "acquisition_allocation",
    }
)


def cost_item_covers_attempt(item: Mapping[str, Any], *, attempt_id: str, run_id: str) -> bool:
    """费用条目是否为该执行实例作证——attempt_id / run_id 联合身份校验。

    测量层（派生缺口核销）与汇总层（组件级覆盖）共用同一条规则（round-8 补遗）：
    条目带了 attempt 身份就必须联合一致——attempt_id 命中但 run_id 属于另一次执行 =
    错误组合，不为任何执行作证；只带 run_id 的条目是该 run 的共享账；只带
    attempt_id 的按 attempt 归属。
    """
    item_aid = str(item.get("attempt_id") or "")
    item_rid = str(item.get("run_id") or "")
    if item_aid:
        return bool(attempt_id) and item_aid == attempt_id and (not item_rid or not run_id or item_rid == run_id)
    if item_rid:
        return bool(run_id) and item_rid == run_id
    return False


# 一次执行实例固有的模型组件（成功要 writer+review；失败只要 writer——review 未发生不强要）。
ATTEMPT_MODEL_COMPONENTS: frozenset[str] = frozenset({"writer_model", "review_model"})


def attempt_uncovered_components(
    items: Iterable[Mapping[str, Any]],
    *,
    attempt_id: str,
    run_id: str,
    applicable: Iterable[str],
    failed: bool,
) -> list[str]:
    """该执行实例仍缺的必需费用组件——「按协议 × 执行实例 × 组件」规则。

    测量层（收据派生缺口）与汇总层（组件级覆盖）共用（round-9）：先统一有效费用
    候选集（``selected=False`` 的去重排除项不作证），再做联合身份匹配
    （``cost_item_covers_attempt``）；必需组件 = 协议适用集 ∩ 固有模型组件，
    失败执行只要 writer_model。
    """
    required = {str(a) for a in applicable} & (frozenset({"writer_model"}) if failed else ATTEMPT_MODEL_COMPONENTS)
    covered = {
        str(i.get("component"))
        for i in items
        if i.get("selected") and cost_item_covers_attempt(i, attempt_id=attempt_id, run_id=run_id)
    }
    return sorted(required - covered)
# 覆盖集合从粗到细；同一 (component, run) 组里只选最粗的一层，已包含子任务不再加。
COVERAGE_SCOPES_COARSE_TO_FINE: tuple[str, ...] = ("pilot", "task", "run", "attempt", "span")
COVERAGE_SCOPES: frozenset[str] = frozenset(COVERAGE_SCOPES_COARSE_TO_FINE)

ACTIVITY_TIMER_SCOPE = "activity-timer"
CONSENT_SCOPES: frozenset[str] = frozenset(
    {"research", "logging", "blind_review", "team_share", "external_display", ACTIVITY_TIMER_SCOPE}
)
# 进入有效测量至少要这两项同意在事件发生时生效。
REQUIRED_MEASUREMENT_SCOPES: frozenset[str] = frozenset({"research", "logging"})
CONSENT_ACTIONS: frozenset[str] = frozenset({"grant", "withdraw"})

RUBRIC_DIMENSIONS: tuple[str, ...] = (
    "fact_sourcing",
    "calculation",
    "assumption_gaps",
    "task_completion",
)
RUBRIC_MAX_PER_DIMENSION = 2

TERMINAL_COMPLETED = "completed"
TERMINAL_FAILED = "failed"
TERMINAL_ABANDONED = "abandoned"
TERMINAL_OPEN = "open"

RUN_STATUSES_TERMINAL: frozenset[str] = frozenset({"completed", "failed", "cancelled"})

PAYMENT_STATUSES: frozenset[str] = frozenset({"paid", "refunded"})
REMINDER_KINDS: frozenset[str] = frozenset({"system", "manual", "unknown"})


@dataclass(frozen=True)
class EventTypeSpec:
    """一种事件类型的最低 payload 字段与允许的来源渠道。"""

    payload_fields: tuple[str, ...]
    sources: frozenset[str]


_TASK_VIEW_FIELDS = ("task_id", "policy_version", "view_id", "client_at")
_RUN_FIELDS = ("run_id", "attempt_id", "status", "error_ref")
_TERMINAL_FIELDS = ("task_id", "completion_evidence_refs", "terminal_reason")
_RECHECK_FIELDS = ("object_ref", "verdict_ref", "action_id", "evidence_refs")

EVENT_TYPES: dict[str, EventTypeSpec] = {
    "assignment_created": EventTypeSpec(
        (
            "protocol_hash",
            "assigned_at",
            "condition",
            "case_pair_id",
            "completion_condition",
            "deadline",
        ),
        frozenset({SOURCE_MANUAL, SOURCE_SERVER}),
    ),
    "task_exposed": EventTypeSpec(_TASK_VIEW_FIELDS, frozenset({SOURCE_FRONTEND, SOURCE_SERVER})),
    "task_selected": EventTypeSpec(_TASK_VIEW_FIELDS, frozenset({SOURCE_FRONTEND, SOURCE_SERVER})),
    "task_started": EventTypeSpec(_TASK_VIEW_FIELDS, frozenset({SOURCE_FRONTEND, SOURCE_SERVER})),
    "run_started": EventTypeSpec(_RUN_FIELDS, frozenset({SOURCE_SERVER})),
    "run_finished": EventTypeSpec(_RUN_FIELDS, frozenset({SOURCE_SERVER})),
    # F 可表达放弃意图，不能自报成功 / 失败。
    "task_completed": EventTypeSpec(_TERMINAL_FIELDS, frozenset({SOURCE_SERVER, SOURCE_MANUAL})),
    "task_failed": EventTypeSpec(_TERMINAL_FIELDS, frozenset({SOURCE_SERVER, SOURCE_MANUAL})),
    "task_abandoned": EventTypeSpec(_TERMINAL_FIELDS, SOURCE_CHANNELS),
    "time_interval": EventTypeSpec(
        (
            "interval_id",
            "start",
            "end",
            "activity",
            "clock_source",
            "pause_reason",
            "visibility",
        ),
        SOURCE_CHANNELS,
    ),
    "quality_reviewed": EventTypeSpec(
        (
            "rubric_version",
            "reviewer_id",
            "blinded",
            "artifact_refs",
            "dimensions",
            "severe_error_count",
        ),
        frozenset({SOURCE_MANUAL}),
    ),
    "manual_assistance": EventTypeSpec(
        ("helper_id", "task_id", "start", "end", "help_kind"),
        frozenset({SOURCE_MANUAL}),
    ),
    "reuse_observed": EventTypeSpec(
        ("first_task_id", "new_task_id", "activation_at", "reminder_refs", "observation_window"),
        frozenset({SOURCE_SERVER}),
    ),
    "recheck_viewed": EventTypeSpec(_RECHECK_FIELDS, frozenset({SOURCE_FRONTEND, SOURCE_SERVER})),
    "recheck_completed": EventTypeSpec(_RECHECK_FIELDS, frozenset({SOURCE_SERVER})),
    "cost_recorded": EventTypeSpec(("cost_item",), frozenset({SOURCE_SERVER, SOURCE_MANUAL})),
    "consent_changed": EventTypeSpec(
        ("consent_version", "scopes", "effective_at", "action", "terms_hash"),
        SOURCE_CHANNELS,
    ),
    "payment_recorded": EventTypeSpec(
        ("payment_ref", "amount", "currency", "service_period", "status", "verified_by"),
        frozenset({SOURCE_MANUAL}),
    ),
    "exercise_submitted": EventTypeSpec(
        ("exercise_id", "exercise_version", "submission_ref", "submitted_at"),
        frozenset({SOURCE_FRONTEND, SOURCE_SERVER}),
    ),
}

# 所有 payload 都要带的两个字段：谁发起、辅助来自哪里。不能靠推断补「主动」。
PAYLOAD_COMMON_FIELDS: tuple[str, ...] = ("initiator", "assistance_source")
# M 渠道额外必填。
MANUAL_IMPORT_FIELDS: tuple[str, ...] = ("importer_id", "evidence_ref", "evidence_hash")

# 顶层必填字段。允许为 null 的必须在 ``gaps`` 里给出 reason。
TOP_LEVEL_FIELDS: tuple[str, ...] = (
    "schema_version",
    "event_id",
    "event_type",
    "owner_user_id",
    "pilot_id",
    "participant_id",
    "task_id",
    "case_id",
    "case_version",
    "case_pair_id",
    "run_ids",
    "object_refs",
    "assistance_condition",
    "event_at",
    "recorded_at",
    "source_version",
    "provenance",
    "source_channel",
    "payload",
)
NULLABLE_TOP_LEVEL_FIELDS: frozenset[str] = frozenset(
    {"participant_id", "task_id", "case_id", "case_version", "case_pair_id", "assistance_condition"}
)
SOURCE_VERSION_FIELDS: tuple[str, ...] = ("code_sha", "protocol_version", "artifact_hash")
PROVENANCE_FIELDS: tuple[str, ...] = ("kind", "source_ref", "source_hash")
OBJECT_REF_FIELDS: tuple[str, ...] = ("kind", "id", "namespace", "version_or_hash", "scope")
COST_ITEM_FIELDS: tuple[str, ...] = (
    "cost_id",
    "component",
    "run_id",
    "attempt_id",
    "span_id",
    "coverage_scope",
    "quantity",
    "unit",
    "amount",
    "currency",
    "certainty",
    "evidence_ref",
    "rate_version",
    "allocation_rule",
)

# 稳定业务错误码（06 的 API 直接透传给客户端；不要改名，只能追加）。
ERR_SCHEMA_VERSION = "schema_version_mismatch"
ERR_MISSING_FIELD = "missing_field"
ERR_NULL_WITHOUT_REASON = "null_without_reason"
ERR_UNKNOWN_EVENT_TYPE = "unknown_event_type"
ERR_SOURCE_NOT_ALLOWED = "source_not_allowed"
ERR_PROVENANCE_INVALID = "provenance_invalid"
ERR_TIMESTAMP_INVALID = "timestamp_invalid"
ERR_TIMESTAMP_NAIVE = "timestamp_naive"
ERR_INTERVAL_NEGATIVE = "interval_negative"
ERR_PAYLOAD_MISSING_FIELD = "payload_missing_field"
ERR_MANUAL_IMPORT_EVIDENCE = "manual_import_missing_evidence"
ERR_CONDITION_INVALID = "assistance_condition_invalid"
ERR_REF_INVALID = "object_ref_invalid"
ERR_REF_CROSS_OWNER = "object_ref_cross_owner"
ERR_ENUM_INVALID = "enum_invalid"
ERR_DIMENSION_OUT_OF_RANGE = "rubric_dimension_out_of_range"
ERR_COST_ITEM_INVALID = "cost_item_invalid"
ERR_TYPE_INVALID = "type_invalid"
ERR_ID_INVALID = "id_invalid"
ERR_PROTOCOL_VERSION = "protocol_version_mismatch"
ERR_PROTOCOL_HASH = "protocol_hash_mismatch"
ERR_RUBRIC_VERSION = "rubric_version_mismatch"
ERR_PAIR_MISMATCH = "case_pair_mismatch"
ERR_TASK_MISMATCH = "task_id_mismatch"

# 收据 / 总结状态。
RECEIPT_VALID = "valid"
RECEIPT_INCOMPLETE = "incomplete"
RECEIPT_INVALID = "invalid"

FIELD_PENDING = "pending"
FIELD_COLLECTING = "collecting"
FIELD_OBSERVED = "observed"
FIELD_INCONCLUSIVE = "inconclusive"

COMMERCIAL_UNSTARTED = "unstarted"
COMMERCIAL_OBSERVED = "observed"

ENGINEERING_COMPLETE = "engineering_complete"
ENGINEERING_NO_INPUT = "no_input"
ENGINEERING_INPUT_ERROR = "input_error"

VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"
VERDICT_UNKNOWN = "unknown"
VERDICT_OBSERVED_ONLY = "observed_only"

__all__ = [name for name in globals() if name.isupper() or name == "EventTypeSpec"]

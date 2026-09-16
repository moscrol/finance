"""02 · 下一步研究排序：对象合同、枚举与校验。

本模块只声明「长什么样」并做确定性校验，不读文件、不读时钟、不调模型。
对外 JSON 形状固定（`research-task/v1` / `research-priority/v1`），字段语义见
`docs/superpowers/specs/2026-09-13-research-evolution/02-research-priority.md` §4。

校验策略（spec §5.1）：越权、未知 schema、未知枚举、非法引用、裸时间戳都
**拒绝整份输入**并给稳定业务码（`ContractError.code`），不静默丢弃、不猜修。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

SCHEMA_TASK = "research-task/v1"
SCHEMA_REPORT = "research-priority/v1"
SCHEMA_CANDIDATES = "research-priority-candidates/v1"
SCHEMA_VIEW = "research-priority-view/v1"
POLICY_VERSION = "research-priority-policy/v1"
KNOWN_POLICY_VERSIONS = (POLICY_VERSION,)

EFFECT_ABANDON = "abandon_or_downgrade"
EFFECT_REVIEW_CHANGED = "review_changed_evidence"
EFFECT_VERIFY_DUE = "verify_due_condition"
EFFECT_FILL_GAP = "fill_gap"
EFFECT_EXPLORE = "explore"
EFFECT_KINDS = (EFFECT_ABANDON, EFFECT_REVIEW_CHANGED, EFFECT_VERIFY_DUE, EFFECT_FILL_GAP, EFFECT_EXPLORE)

AVAIL_ACTIONABLE = "actionable"
AVAIL_WAITING_RELEASE = "waiting_release"
AVAIL_MISSING_PERMISSION = "missing_permission"
AVAIL_MISSING_DATA = "missing_data"
AVAIL_UNSUPPORTED = "unsupported"
AVAILABILITIES = (
    AVAIL_ACTIONABLE,
    AVAIL_WAITING_RELEASE,
    AVAIL_MISSING_PERMISSION,
    AVAIL_MISSING_DATA,
    AVAIL_UNSUPPORTED,
)

CONDITION_UNKNOWN = "unknown"
EFFORT_KINDS = ("observed", "user_estimate", "unknown")
PIT_GRADES = ("strict", "trade_date_only", "unverifiable")
# 01 的管理状态；closed/superseded 在适配层就已跳过，这里只允许「还在办」的几种。
MANAGEMENT_STATUSES = ("open", "claimed", "snoozed", "rejudgment_requested")

GROUP_ABANDON = 1
GROUP_REVIEW_CHANGED = 2
GROUP_VERIFY_DUE = 3
GROUP_FILL_GAP = 4
GROUP_EXPLORE = 5
GROUP_LABELS = {
    GROUP_ABANDON: "放弃/降级条件已被观测触发，尚未复核",
    GROUP_REVIEW_CHANGED: "跟踪对象依赖的证据发生需复核变化",
    GROUP_VERIFY_DUE: "到期/逾期的明确条件，当前资料可核查",
    GROUP_FILL_GAP: "与已登记判断绑定、补到即可改变判断的缺口",
    GROUP_EXPLORE: "其余探索任务（含未绑定判断的旧队列项）",
}

DEFER_MAX_ITEMS = "max_items_reached"
DEFER_PER_OBJECT = "per_object_limit"
DEFER_OVER_BUDGET = "over_budget"
DEFER_EFFORT_UNKNOWN = "effort_unknown"
DEFER_USER_SNOOZED = "user_snoozed"

BLOCK_NOT_YET_DUE = "not_yet_due"
BLOCK_FUTURE_RECORD = "future_record"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WS_RE = re.compile(r"\s+")


class ContractError(ValueError):
    """输入不满足合同。``code`` 是稳定业务码，``detail`` 只放定位信息，不回显他人对象。"""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = dict(detail)


@dataclass(frozen=True)
class Policy:
    """排序策略。数值是首版界面约束（spec §1），随 policy_version 记录，不是金融阈值。"""

    policy_version: str = POLICY_VERSION
    max_items: int = 3
    max_per_object: int = 1

    @classmethod
    def from_value(cls, value: Any) -> "Policy":
        if value is None:
            return cls()
        if isinstance(value, Policy):
            policy = value
        elif isinstance(value, dict):
            unknown = set(value) - {"policy_version", "max_items", "max_per_object"}
            if unknown:
                raise ContractError("unknown_policy_field", f"policy 含未知字段 {sorted(unknown)}")
            policy = cls(
                policy_version=str(value.get("policy_version") or POLICY_VERSION),
                max_items=value.get("max_items", 3),
                max_per_object=value.get("max_per_object", 1),
            )
        else:
            raise ContractError("invalid_policy", "policy 必须是 dict 或 Policy")
        if policy.policy_version not in KNOWN_POLICY_VERSIONS:
            raise ContractError("unknown_policy", f"未知 policy_version {policy.policy_version!r}")
        for name in ("max_items", "max_per_object"):
            raw = getattr(policy, name)
            if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
                raise ContractError("invalid_policy", f"{name} 必须是非负整数")
        return policy

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "max_items": self.max_items,
            "max_per_object": self.max_per_object,
        }


@dataclass(frozen=True)
class Budget:
    """分钟预算；None = 未给预算（按 max_items 取前几项），0 = 明确没时间。"""

    minutes: float | None = None

    @classmethod
    def from_value(cls, value: Any) -> "Budget":
        if value is None:
            return cls()
        if isinstance(value, Budget):
            return value
        if isinstance(value, dict):
            unknown = set(value) - {"minutes"}
            if unknown:
                raise ContractError("invalid_budget", f"budget 含未知字段 {sorted(unknown)}")
            minutes = value.get("minutes")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            minutes = value
        else:
            raise ContractError("invalid_budget", "budget 必须是 dict / 数字 / None")
        if minutes is None:
            return cls()
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes < 0:
            raise ContractError("invalid_budget", "budget.minutes 必须是非负数或 None")
        return cls(minutes=float(minutes))

    @property
    def seconds(self) -> float | None:
        return None if self.minutes is None else self.minutes * 60.0


# ---------------------------------------------------------------------------
# 时间：只解析，不读时钟。日期只与 evaluation_at 的 UTC 日历日比较，不补假时分秒。
# ---------------------------------------------------------------------------


def parse_instant(value: Any, *, field: str) -> datetime | None:
    """ISO 时间戳（必须带时区）或 ``YYYY-MM-DD`` 日期（视为当日 00:00Z，仅用于比较）。

    裸 datetime（无时区）拒绝：静默当 UTC 会把本地时间读错 8 小时，且无法事后发现。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ContractError("naive_timestamp", f"{field} 是不带时区的 datetime")
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        raise ContractError("invalid_timestamp", f"{field} 必须是 ISO 字符串、date 或 datetime")
    text = value.strip()
    if _DATE_RE.match(text):
        try:
            d = date.fromisoformat(text)
        except ValueError as exc:
            raise ContractError("invalid_timestamp", f"{field} 不是合法日期：{text}") from exc
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("invalid_timestamp", f"{field} 不是 ISO 时间：{text}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError("naive_timestamp", f"{field} 缺时区：{text}")
    return parsed.astimezone(timezone.utc)


def parse_evaluation_at(value: Any) -> datetime:
    if value is None:
        raise ContractError("evaluation_at_required", "evaluation_at 必须由调用方注入（本包不读系统时钟）")
    if isinstance(value, str) and _DATE_RE.match(value.strip()):
        raise ContractError("invalid_timestamp", "evaluation_at 必须是带时区的时刻，不能只给日期")
    instant = parse_instant(value, field="evaluation_at")
    assert instant is not None
    return instant


def parse_market_date(value: Any, *, field: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        raise ContractError("invalid_timestamp", f"{field} 是市场日，应为 YYYY-MM-DD，不是时刻")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _DATE_RE.match(value.strip()):
        raise ContractError("invalid_timestamp", f"{field} 必须是 YYYY-MM-DD")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ContractError("invalid_timestamp", f"{field} 不是合法日期：{value}") from exc


def iso_utc(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# A 股市场日按 Asia/Shanghai 日历（仓内既有约定：market_snapshot_sync / duckdb_market_snapshot 等）。
MARKET_TZ = ZoneInfo("Asia/Shanghai")


def market_date_of(instant: datetime) -> date:
    """评估时刻在市场时区的日历日。市场日 as_of 是否未来按它判断（S5）：市场日 09-14 在北京时间
    09-14 00:00 就开始，拿 UTC 日历日比会把已开场的当天资料多挡 8 小时。"""
    return instant.astimezone(MARKET_TZ).date()


def market_day_start(day: date) -> datetime:
    """市场日开始的真实时刻（市场时区当日零点）。"""
    return datetime(day.year, day.month, day.day, tzinfo=MARKET_TZ)


# ---------------------------------------------------------------------------
# 摘要与身份
# ---------------------------------------------------------------------------


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: Any) -> str:
    return _WS_RE.sub(" ", str(text or "")).strip().lower()


def ref_identity(ref: dict[str, Any]) -> tuple[str, str, str, str]:
    """引用身份：kind / namespace / id-or-ref / version。用于去重与合并键。"""
    return (
        str(ref.get("kind") or ""),
        str(ref.get("namespace") or ""),
        str(ref.get("id") if ref.get("id") is not None else ref.get("ref") or ""),
        str(ref.get("version_or_hash") or ""),
    )


def object_identity(owner_user_id: str, ref: dict[str, Any]) -> tuple[str, str, str]:
    """受影响对象身份：owner + kind + id（spec §5.2：不按引用条数、不按版本膨胀）。"""
    return (
        owner_user_id,
        str(ref.get("kind") or ""),
        str(ref.get("id") if ref.get("id") is not None else ref.get("ref") or ""),
    )


def object_label(ref: dict[str, Any]) -> str:
    ident = ref.get("id") if ref.get("id") is not None else ref.get("ref")
    return f"{ref.get('kind') or '?'}:{ident}"


def condition_result_of(value: Any) -> Any:
    """归一到 True / False / 'unknown' / None；其它值拒绝。"""
    if value is None or value is True or value is False:
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == CONDITION_UNKNOWN:
            return CONDITION_UNKNOWN
        if lowered in ("null", "none", ""):
            return None
    raise ContractError("invalid_enum", f"condition_result 非法：{value!r}")


# ---------------------------------------------------------------------------
# 任务校验
# ---------------------------------------------------------------------------

_REF_FIELDS = ("kind", "id", "namespace", "version_or_hash", "scope", "ref")


def _validate_ref(ref: Any, *, field: str, index: int) -> dict[str, Any]:
    if not isinstance(ref, dict):
        raise ContractError("invalid_ref", f"{field} 第 {index} 项不是对象")
    kind = ref.get("kind")
    namespace = ref.get("namespace")
    if not isinstance(kind, str) or not kind.strip():
        raise ContractError("invalid_ref", f"{field} 第 {index} 项缺 kind")
    if not isinstance(namespace, str) or not namespace.strip():
        raise ContractError("invalid_ref", f"{field} 第 {index} 项缺 namespace")
    ident = ref.get("id")
    raw_ref = ref.get("ref")
    if (ident is None or str(ident) == "") and (raw_ref is None or str(raw_ref) == ""):
        raise ContractError("invalid_ref", f"{field} 第 {index} 项既无 id 也无 ref")
    version = ref.get("version_or_hash")
    if version is not None and not isinstance(version, str):
        raise ContractError("invalid_ref", f"{field} 第 {index} 项 version_or_hash 必须是字符串或 null")
    scope = ref.get("scope")
    if scope is not None and not isinstance(scope, dict):
        raise ContractError("invalid_ref", f"{field} 第 {index} 项 scope 必须是对象或 null")
    out: dict[str, Any] = {
        "kind": kind.strip(),
        "id": None if ident is None else str(ident),
        "namespace": namespace.strip(),
        "version_or_hash": version,
        "scope": dict(scope) if isinstance(scope, dict) else None,
    }
    if raw_ref is not None:
        out["ref"] = str(raw_ref)
    return out


def _validate_effort(value: Any) -> dict[str, Any]:
    if value is None:
        return {"seconds": None, "kind": "unknown", "source_ref": None}
    if not isinstance(value, dict):
        raise ContractError("invalid_effort", "effort 必须是对象")
    seconds = value.get("seconds")
    kind = value.get("kind") or ("unknown" if seconds is None else None)
    if kind not in EFFORT_KINDS:
        raise ContractError("invalid_effort", f"effort.kind 非法：{kind!r}")
    if seconds is not None:
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
            raise ContractError("invalid_effort", "effort.seconds 必须是非负数或 null")
        if kind == "unknown":
            raise ContractError("invalid_effort", "effort.kind=unknown 时 seconds 必须为 null（未知不当零）")
        seconds = float(seconds)
    elif kind != "unknown":
        raise ContractError("invalid_effort", f"effort.kind={kind} 但 seconds 为 null")
    source_ref = value.get("source_ref")
    if source_ref is not None and not isinstance(source_ref, str):
        raise ContractError("invalid_effort", "effort.source_ref 必须是字符串或 null")
    return {"seconds": seconds, "kind": kind, "source_ref": source_ref}


def _validate_gap(gap: Any, *, index: int) -> dict[str, Any]:
    if isinstance(gap, str):
        return {"reason": gap, "ref": None, "checked_at": None, "retryable": None}
    if not isinstance(gap, dict) or not gap.get("reason"):
        raise ContractError("invalid_gap", f"gaps 第 {index} 项缺 reason")
    return {
        "reason": str(gap["reason"]),
        "ref": None if gap.get("ref") is None else str(gap["ref"]),
        "checked_at": None if gap.get("checked_at") is None else str(gap["checked_at"]),
        "retryable": gap.get("retryable") if isinstance(gap.get("retryable"), bool) else None,
    }


def validate_task(task: Any, *, owner_user_id: str, index: int = 0) -> dict[str, Any]:
    """校验并归一一条候选；返回深拷贝，不改原对象。任何一处不合同都抛 ``ContractError``。"""
    where = f"candidates[{index}]"
    if not isinstance(task, dict):
        raise ContractError("invalid_task", f"{where} 不是对象")
    if task.get("schema_version") != SCHEMA_TASK:
        raise ContractError("unknown_schema", f"{where} schema_version={task.get('schema_version')!r}，仅接受 {SCHEMA_TASK}")
    owner = task.get("owner_user_id")
    if not isinstance(owner, str) or not owner.strip():
        raise ContractError("owner_missing", f"{where} 缺 owner_user_id")
    if owner != owner_user_id:
        # 不回显对方 owner：错误只说「不属于当前用户」。
        raise ContractError("owner_mismatch", f"{where} 不属于当前用户", index=index)
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ContractError("invalid_task", f"{where} 缺 id")

    effect_kind = task.get("effect_kind")
    if effect_kind not in EFFECT_KINDS:
        raise ContractError("invalid_enum", f"{where} effect_kind 非法：{effect_kind!r}")
    availability = task.get("availability")
    if availability not in AVAILABILITIES:
        raise ContractError("invalid_enum", f"{where} availability 非法：{availability!r}")
    pit_grade = task.get("pit_grade")
    if pit_grade not in PIT_GRADES:
        raise ContractError("invalid_enum", f"{where} pit_grade 非法：{pit_grade!r}")
    condition_result = condition_result_of(task.get("condition_result"))

    scope_raw = task.get("scope") or {}
    if not isinstance(scope_raw, dict):
        raise ContractError("invalid_task", f"{where} scope 必须是对象")
    entity_refs = scope_raw.get("entity_refs") or []
    if not isinstance(entity_refs, list) or not all(isinstance(e, str) for e in entity_refs):
        raise ContractError("invalid_task", f"{where} scope.entity_refs 必须是字符串数组")
    conversation_id = scope_raw.get("conversation_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise ContractError("invalid_task", f"{where} scope.conversation_id 必须是字符串或 null")

    source = _validate_ref(task.get("source"), field=f"{where}.source", index=0)
    object_refs = [
        _validate_ref(ref, field=f"{where}.object_refs", index=i) for i, ref in enumerate(task.get("object_refs") or [])
    ]
    evidence_refs = [
        _validate_ref(ref, field=f"{where}.effect_evidence_refs", index=i)
        for i, ref in enumerate(task.get("effect_evidence_refs") or [])
    ]
    merged_sources_raw = task.get("merged_source_refs") or [task["source"]]
    merged_source_refs = [
        _validate_ref(ref, field=f"{where}.merged_source_refs", index=i) for i, ref in enumerate(merged_sources_raw)
    ]
    maintenance_item_ids = task.get("maintenance_item_ids") or []
    if not isinstance(maintenance_item_ids, list) or not all(isinstance(m, str) for m in maintenance_item_ids):
        raise ContractError("invalid_task", f"{where} maintenance_item_ids 必须是字符串数组")

    legacy_unbound = task.get("legacy_unbound")
    if not isinstance(legacy_unbound, bool):
        raise ContractError("invalid_task", f"{where} legacy_unbound 必须是布尔")
    if legacy_unbound != (not object_refs):
        raise ContractError(
            "unbound_flag_mismatch",
            f"{where} legacy_unbound={legacy_unbound} 与 object_refs 数量 {len(object_refs)} 不一致",
        )

    if effect_kind == EFFECT_ABANDON:
        # spec §4：放弃/降级只能来自已登记条件角色 + 已观测触发；hash 变化、标题「利空」都不算。
        if condition_result is not True or not evidence_refs or not object_refs:
            raise ContractError(
                "abandon_without_observed_trigger",
                f"{where} effect_kind=abandon_or_downgrade 需要 condition_result=true、非空 effect_evidence_refs 与 object_refs",
            )

    for name in ("question", "discriminating_evidence", "completion_condition"):
        if not isinstance(task.get(name), str) or not task[name].strip():
            raise ContractError("invalid_task", f"{where} 缺 {name}")

    as_of = parse_market_date(task.get("as_of"), field=f"{where}.as_of")
    parse_instant(task.get("knowledge_cutoff"), field=f"{where}.knowledge_cutoff")
    parse_instant(task.get("due_at"), field=f"{where}.due_at")
    parse_instant(task.get("available_at"), field=f"{where}.available_at")

    management_status = task.get("management_status")
    if management_status is not None and management_status not in MANAGEMENT_STATUSES:
        raise ContractError("invalid_enum", f"{where} management_status 非法：{management_status!r}")
    human_review_required = task.get("human_review_required", False)
    if not isinstance(human_review_required, bool):
        raise ContractError("invalid_task", f"{where} human_review_required 必须是布尔")
    availability_reason = task.get("availability_reason")
    if availability_reason is not None and not isinstance(availability_reason, str):
        raise ContractError("invalid_task", f"{where} availability_reason 必须是字符串或 null")
    # 09-06 终局 §4.1：hindsight（历史 as_of 配更晚 cutoff）只供人工复核，不得进校准；02 只透传并标出。
    hindsight = task.get("hindsight", False)
    if not isinstance(hindsight, bool):
        raise ContractError("invalid_task", f"{where} hindsight 必须是布尔")

    return {
        "schema_version": SCHEMA_TASK,
        "id": task_id,
        "owner_user_id": owner,
        "scope": {"conversation_id": conversation_id, "entity_refs": sorted(set(entity_refs))},
        "source": source,
        "object_refs": object_refs,
        "maintenance_item_ids": sorted(set(maintenance_item_ids)),
        "question": task["question"].strip(),
        "discriminating_evidence": task["discriminating_evidence"].strip(),
        "completion_condition": task["completion_condition"].strip(),
        "human_review_required": human_review_required,
        "effect_kind": effect_kind,
        "effect_evidence_refs": evidence_refs,
        "condition_result": condition_result,
        "availability": availability,
        "availability_reason": availability_reason,
        "available_at": task.get("available_at"),
        "due_at": task.get("due_at"),
        "as_of": None if as_of is None else as_of.isoformat(),
        "knowledge_cutoff": task.get("knowledge_cutoff"),
        "pit_grade": pit_grade,
        "effort": _validate_effort(task.get("effort")),
        "gaps": [_validate_gap(g, index=i) for i, g in enumerate(task.get("gaps") or [])],
        "legacy_unbound": legacy_unbound,
        "management_status": management_status,
        "merged_source_refs": merged_source_refs,
        "source_task_ids": sorted(set(task.get("source_task_ids") or [task_id])),
        "synthetic": bool(task.get("synthetic", False)),
        "hindsight": hindsight,
    }


def observation_window(task: dict[str, Any]) -> tuple[str, str]:
    """观测窗口 =（市场日 as_of, 资料截止 knowledge_cutoff）。

    01 的 dedup_key 含「条件/观测窗口」，02 保持同一口径：同一条证据在不同市场日或不同
    资料截止下的观测是两次观测，不是同一件待办。缺值用空串参与键，缺失与已知不互相顶替。
    """
    return (str(task.get("as_of") or ""), str(task.get("knowledge_cutoff") or ""))


def execution_window(task: dict[str, Any]) -> tuple[str, str]:
    """执行窗口 =（到期 due_at, 发布 available_at），统一折算成 UTC 时刻串参与合并键。

    同证据但到期 / 发布时间不同是两个不同的核查机会（评审 P2）：先合并再判可执行性，
    未到期项会随今日项提前入选、今日已发布项会陪未来项一起等。缺值用空串参与键，
    缺失与已知不互相顶替（与 observation_window 同口径）。
    """

    def _norm(value: Any, field: str) -> str:
        instant = parse_instant(value, field=field)
        return iso_utc(instant) if instant is not None else ""

    return (_norm(task.get("due_at"), "due_at"), _norm(task.get("available_at"), "available_at"))


def identity_key(task: dict[str, Any]) -> tuple[Any, ...]:
    """合并键（spec §5.3）：同 owner、同效果、**同观测窗口**、**同执行窗口**、同一组证据版本 →
    同一个「核查该证据」任务；没有证据引用的任务再按（问题文字 + 实体范围 + 绑定对象）判重，
    所以「相同问题文字、不同实体或时间窗」不会被误合并（P07）。

    观测窗口进键是 spec §5.3「仅文本相似但对象或时间窗不同，不合并」的直接落实，也堵住
    「未来观测记录与当天关键条件先合并、再被整体判成 future_record」这条路：两个窗口的键
    不同，未来那条永远不可能把当天那条一起带走。执行窗口同理：due_at / available_at 不同的
    同证据任务各自保留自己的到期机会与等待状态，不在合并时取 min/max 互相拖入拖出（P2）。
    hindsight 回放与当前观测不合并；只在 hindsight 时追加标记，普通任务的键（与 id）保持不变。"""
    owner = task["owner_user_id"]
    window = observation_window(task)
    execution = execution_window(task)
    evidence = tuple(sorted({ref_identity(r) for r in task["effect_evidence_refs"]}))
    if evidence:
        base: tuple[Any, ...] = ("evidence", owner, task["effect_kind"], task["availability"], window, execution, evidence)
    else:
        base = (
            "question",
            owner,
            task["effect_kind"],
            task["availability"],
            window,
            execution,
            normalize_text(task["question"]),
            tuple(task["scope"]["entity_refs"]),
            tuple(sorted({ref_identity(r) for r in task["object_refs"]})),
        )
    return base + (("hindsight",) if task.get("hindsight") else ())


def task_id_for(key: tuple[Any, ...]) -> str:
    return "rt_" + sha256_hex(canonical_json(list(key)))[:16]

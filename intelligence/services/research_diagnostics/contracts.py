"""个人研究流程诊断（研究进化 04）：输入 / 输出合同。

规格 ``docs/superpowers/specs/2026-09-13-research-evolution/04-personal-diagnostics.md`` §3。

本模块只定义**类型与校验**，不做判定。三条设计约束贯穿全包：

1. 归属：所有输入都带 ``owner_user_id``，与 ``diagnose`` 的 owner 不一致就拒绝
   （``OwnerMismatch``）——请求正文里的 owner 不能替代访问控制，这里是最后一道兜底。
2. 版本：外部合同（01 的维护报告、策略、题包）都带 ``schema_version``，未知版本拒绝
   （``UnsupportedSchema``），不猜字段。
3. 引用：``ObjectRef`` 只保留 ``kind / id / namespace / version_or_hash / scope / ref``，
   结构上像路径穿越或绝对路径的 ref 直接拒绝（``InvalidRef``）。真正的访问校验归 06。

所有 dataclass 都是 frozen 的，``to_dict()`` 是唯一序列化出口——报告 id 与输入摘要都从
``canonical_json(to_dict())`` 派生，所以字段顺序、None 的表示都要稳定。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "research-diagnostics/v1"
POLICY_SCHEMA_VERSION = "research-diagnostics-policy/v1"
EXERCISE_PACK_SCHEMA_VERSION = "research-diagnostics-exercise-pack/v1"
# 01 的合同版本：本轨只接这一版，字段调整先改总合同再改这里。
MAINTENANCE_SCHEMA_VERSION = "judgment-maintenance/v1"

KINDS = (
    "late_registration",
    "condition_revision",
    "stale_evidence_reuse",
    "stage_mismatch",
    "overdue_unreviewed",
)
CLASSIFICATIONS = ("issue", "context", "unknown")
ACTOR_GROUPS = ("user_original", "agent_generated", "user_after_agent", "unknown_origin")
AUTHORS = ("user", "agent", "system", "unknown")
PIT_GRADES = ("strict", "trade_date_only", "unverifiable")
MODEL_EXPOSURE_GRADES = ("deterministic_only", "model_exposure_unknown", "known_exposed")
LEARNER_EXPOSURE_GRADES = ("not_declared", "declared_unseen", "seen_or_repeated")
FEEDBACK_STATUSES = ("checked", "manual_review")
UNCERTAINTY_KINDS = (
    "small_sample",
    "selection_bias",
    "source_coverage",
    "actor_coverage",
    "correlated_observations",
)
DENOMINATOR_UNIT = "original_object_check_opportunity"
TIME_GRANULARITIES = ("datetime", "date", "unknown")
OBJECT_KINDS = ("judgment", "checkpoint", "observation_script", "scenario_tree", "method_observation")
REVIEW_RESPONSIBILITIES = ("user", "system", "unknown")
RECEIPT_KINDS = (
    "evidence_use",  # 实际投影 / 引用了某证据版本
    "revision",  # 条件 / 版本修改
    "stage_use",  # 在某阶段标签下使用了某方法
    "review",  # 回检 / 延期动作
    "exposure",  # 用户看过某 agent 产物 / 维护项
    "backfill",  # 显式声明的历史补录
    "system_failure",  # 系统 / 数据失败窗口
    "coverage",  # 台账完整性声明
    "exercise_seen",  # 06 记录的练习曝光
    "learner_declaration",  # 学习者自报未见
    "model_exposure",  # 模型已见某结局
)
STAGE_LABEL_GRADES = ("deterministic", "ambiguous", "gap")
PROVENANCES = ("observed", "synthetic")


class DiagnosticsInputError(ValueError):
    """输入不合合同：拒绝而不是猜。"""


class OwnerMismatch(DiagnosticsInputError):
    """跨 owner 输入。故意不带对方 id 的存在性信息。"""


class UnsupportedSchema(DiagnosticsInputError):
    """未知 schema_version。"""


class InvalidRef(DiagnosticsInputError):
    """引用结构不安全或不完整。"""


# --------------------------------------------------------------------------- #
# 通用工具
# --------------------------------------------------------------------------- #
def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def _enum(value: Any, allowed: tuple[str, ...], name: str) -> str:
    text = str(value or "").strip()
    if text not in allowed:
        raise DiagnosticsInputError(f"{name}={value!r} 不在允许值 {allowed}")
    return text


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _str_tuple(values: Any, name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        raise DiagnosticsInputError(f"{name} 必须是列表")
    out: list[str] = []
    for v in values:
        text = str(v).strip()
        if text and text not in out:
            out.append(text)
    return tuple(out)


def _opt_bool(value: Any, name: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise DiagnosticsInputError(f"{name} 必须是 true/false/null")


def check_ref_text(text: Any, name: str) -> str:
    """引用串的结构门：非空、无路径穿越、非绝对路径、无控制字符。"""
    s = str(text or "").strip()
    if not s:
        raise InvalidRef(f"{name} 不能为空")
    if s.startswith(("/", "~", "\\")) or "\\" in s:
        raise InvalidRef(f"{name} 不接受绝对路径或反斜杠：{s!r}")
    if any(part == ".." for part in s.replace("\\", "/").split("/")):
        raise InvalidRef(f"{name} 不接受路径穿越：{s!r}")
    if any(ord(ch) < 32 for ch in s):
        raise InvalidRef(f"{name} 含控制字符")
    return s


def require_owner(owner_user_id: str, candidate: Any, *, where: str) -> str:
    """所有输入的 owner 必须与调用方一致；不一致只报位置，不回显对方 id。"""
    expected = str(owner_user_id or "").strip()
    if not expected:
        raise DiagnosticsInputError("owner_user_id 不能为空")
    got = str(candidate or "").strip()
    if got != expected:
        raise OwnerMismatch(f"{where} 的 owner 与请求 owner 不一致，拒绝")
    return expected


def require_schema(raw: Mapping[str, Any], expected: str, *, where: str) -> None:
    got = str(raw.get("schema_version") or "")
    if got != expected:
        raise UnsupportedSchema(f"{where} schema_version={got!r}，只接 {expected!r}")


# --------------------------------------------------------------------------- #
# 引用与时间
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ObjectRef:
    """原对象 / 证据的引用。与 01 的 object_ref 同形：kind、id、namespace、版本或不可变哈希、scope、ref。"""

    kind: str
    namespace: str
    id: str | None = None
    version_or_hash: str | None = None
    scope: str | None = None
    ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", check_ref_text(self.kind, "object_ref.kind"))
        object.__setattr__(self, "namespace", check_ref_text(self.namespace, "object_ref.namespace"))
        if self.id is None and self.ref is None:
            raise InvalidRef("object_ref 至少要有 id 或 ref")
        if self.id is not None:
            object.__setattr__(self, "id", check_ref_text(self.id, "object_ref.id"))
        if self.ref is not None:
            object.__setattr__(self, "ref", check_ref_text(self.ref, "object_ref.ref"))

    @property
    def identity(self) -> str:
        """对象身份（不含版本）：同一原对象的不同版本 / 多源引用折到同一身份。"""
        return f"{self.kind}|{self.namespace}|{self.id if self.id is not None else 'ref:' + str(self.ref)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "namespace": self.namespace,
            "id": self.id,
            "version_or_hash": self.version_or_hash,
            "scope": self.scope,
            "ref": self.ref,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, where: str = "object_ref") -> ObjectRef:
        if not isinstance(raw, Mapping):
            raise InvalidRef(f"{where} 必须是对象")
        return cls(
            kind=str(raw.get("kind") or ""),
            namespace=str(raw.get("namespace") or ""),
            id=_opt_str(raw.get("id")),
            version_or_hash=_opt_str(raw.get("version_or_hash")),
            scope=_opt_str(raw.get("scope")),
            ref=_opt_str(raw.get("ref")),
        )


@dataclass(frozen=True)
class TimePoint:
    """一个时刻及其粒度。``datetime`` = 带时区的精确时刻；``date`` = 只到日；``unknown`` = 没有。

    粒度是 PIT 档位的来源：只有 ``datetime`` 能判「晚于截止时刻」这种精确先后。
    """

    value: str | None
    granularity: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "granularity", _enum(self.granularity, TIME_GRANULARITIES, "time.granularity"))
        if self.granularity == "unknown" and self.value is not None:
            raise DiagnosticsInputError("granularity=unknown 时 value 必须为 null")
        if self.granularity != "unknown" and not self.value:
            raise DiagnosticsInputError(f"granularity={self.granularity} 需要 value")

    @property
    def day(self) -> str | None:
        return self.value[:10] if self.value else None

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "granularity": self.granularity}

    @classmethod
    def unknown(cls) -> TimePoint:
        return cls(None, "unknown")

    @classmethod
    def from_dict(cls, raw: Any) -> TimePoint:
        if raw is None:
            return cls.unknown()
        if isinstance(raw, str):
            from intelligence.services.research_diagnostics.clock import classify_time

            return classify_time(raw)
        if not isinstance(raw, Mapping):
            raise DiagnosticsInputError("time 必须是字符串或 {value, granularity}")
        return cls(_opt_str(raw.get("value")), str(raw.get("granularity") or "unknown"))


# --------------------------------------------------------------------------- #
# 输入：原对象记录 / 回检 / 收据
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ActorInfo:
    """作者与曝光。``author`` 来自记录本身的字段（如 object_type），``agent_refs`` 是记录里保留的原 agent
    引用（看后采纳 / 修改都保留它），``exposure_refs`` 是曝光收据。**不做文本相似推断。**"""

    author: str
    agent_refs: tuple[str, ...] = ()
    exposure_refs: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "author", _enum(self.author, AUTHORS, "actor.author"))
        object.__setattr__(self, "agent_refs", _str_tuple(self.agent_refs, "actor.agent_refs"))
        object.__setattr__(self, "exposure_refs", _str_tuple(self.exposure_refs, "actor.exposure_refs"))
        object.__setattr__(self, "evidence", _str_tuple(self.evidence, "actor.evidence"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "author": self.author,
            "agent_refs": list(self.agent_refs),
            "exposure_refs": list(self.exposure_refs),
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, raw: Any) -> ActorInfo:
        if raw is None:
            return cls("unknown")
        if not isinstance(raw, Mapping):
            raise DiagnosticsInputError("actor 必须是对象")
        return cls(
            author=str(raw.get("author") or "unknown"),
            agent_refs=raw.get("agent_refs") or (),
            exposure_refs=raw.get("exposure_refs") or (),
            evidence=raw.get("evidence") or (),
        )


@dataclass(frozen=True)
class VersionEntry:
    """版本链的一节：``disclosed=None`` 表示日志没说，不是「未披露」。"""

    version: str
    recorded_at: str | None = None
    content_hash: str | None = None
    reason: str | None = None
    disclosed: bool | None = None
    linked_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", check_ref_text(self.version, "version.version"))
        object.__setattr__(self, "linked_refs", _str_tuple(self.linked_refs, "version.linked_refs"))
        object.__setattr__(self, "disclosed", _opt_bool(self.disclosed, "version.disclosed"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "recorded_at": self.recorded_at,
            "content_hash": self.content_hash,
            "reason": self.reason,
            "disclosed": self.disclosed,
            "linked_refs": list(self.linked_refs),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> VersionEntry:
        return cls(
            version=str(raw.get("version") or ""),
            recorded_at=_opt_str(raw.get("recorded_at")),
            content_hash=_opt_str(raw.get("content_hash")),
            reason=_opt_str(raw.get("reason")),
            disclosed=raw.get("disclosed"),
            linked_refs=raw.get("linked_refs") or (),
        )


@dataclass(frozen=True)
class ProcessRecord:
    """一条原对象的流程快照（判断 / 检查点 / 剧本 / 树）。原判断正文**不进**这里——报告只引用。

    - ``recorded_at`` 记录时刻；``event_time`` 对象针对的市场日（as_of）；两者分开。
    - ``declared_deadline`` 预先声明的登记截止（带时区 ISO）；没有就是 None，由规则判 unknown。
    - ``derived_from`` 表示本行是另一原对象的派生表示（如剧本登记出的 checkpoint 行）：
      迟登 / 条件修改不对派生行重复计数，到期回检仍以派生行（它才有 due）为准。
    - ``version_chain_complete=None`` = 不知道链是否完整，不能据此判「未披露」。
    """

    record_id: str
    owner_user_id: str
    object_ref: ObjectRef
    object_kind: str
    actor: ActorInfo
    recorded_at: TimePoint
    event_time: TimePoint = field(default_factory=TimePoint.unknown)
    knowledge_cutoff: str | None = None
    declared_deadline: str | None = None
    deadline_rule_ref: str | None = None
    due: str | None = None
    hindsight: bool = False
    is_backfill: bool = False
    review_responsibility: str = "unknown"
    versions: tuple[VersionEntry, ...] = ()
    version_chain_complete: bool | None = None
    pit_grade: str = "unverifiable"
    derived_from: str | None = None
    source_refs: tuple[str, ...] = ()
    provenance: str = "observed"

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", check_ref_text(self.record_id, "record.record_id"))
        object.__setattr__(self, "object_kind", _enum(self.object_kind, OBJECT_KINDS, "record.object_kind"))
        object.__setattr__(
            self,
            "review_responsibility",
            _enum(self.review_responsibility, REVIEW_RESPONSIBILITIES, "record.review_responsibility"),
        )
        object.__setattr__(self, "pit_grade", _enum(self.pit_grade, PIT_GRADES, "record.pit_grade"))
        object.__setattr__(self, "provenance", _enum(self.provenance, PROVENANCES, "record.provenance"))
        object.__setattr__(self, "versions", tuple(self.versions))
        object.__setattr__(self, "source_refs", _str_tuple(self.source_refs, "record.source_refs"))
        object.__setattr__(
            self, "version_chain_complete", _opt_bool(self.version_chain_complete, "record.version_chain_complete")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "owner_user_id": self.owner_user_id,
            "object_ref": self.object_ref.to_dict(),
            "object_kind": self.object_kind,
            "actor": self.actor.to_dict(),
            "recorded_at": self.recorded_at.to_dict(),
            "event_time": self.event_time.to_dict(),
            "knowledge_cutoff": self.knowledge_cutoff,
            "declared_deadline": self.declared_deadline,
            "deadline_rule_ref": self.deadline_rule_ref,
            "due": self.due,
            "hindsight": self.hindsight,
            "is_backfill": self.is_backfill,
            "review_responsibility": self.review_responsibility,
            "versions": [v.to_dict() for v in self.versions],
            "version_chain_complete": self.version_chain_complete,
            "pit_grade": self.pit_grade,
            "derived_from": self.derived_from,
            "source_refs": list(self.source_refs),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ProcessRecord:
        if not isinstance(raw, Mapping):
            raise DiagnosticsInputError("record 必须是对象")
        return cls(
            record_id=str(raw.get("record_id") or ""),
            owner_user_id=str(raw.get("owner_user_id") or ""),
            object_ref=ObjectRef.from_dict(raw.get("object_ref") or {}, where="record.object_ref"),
            object_kind=str(raw.get("object_kind") or ""),
            actor=ActorInfo.from_dict(raw.get("actor")),
            recorded_at=TimePoint.from_dict(raw.get("recorded_at")),
            event_time=TimePoint.from_dict(raw.get("event_time")),
            knowledge_cutoff=_opt_str(raw.get("knowledge_cutoff")),
            declared_deadline=_opt_str(raw.get("declared_deadline")),
            deadline_rule_ref=_opt_str(raw.get("deadline_rule_ref")),
            due=_opt_str(raw.get("due")),
            hindsight=bool(raw.get("hindsight", False)),
            is_backfill=bool(raw.get("is_backfill", False)),
            review_responsibility=str(raw.get("review_responsibility") or "unknown"),
            versions=tuple(VersionEntry.from_dict(v) for v in (raw.get("versions") or [])),
            version_chain_complete=raw.get("version_chain_complete"),
            pit_grade=str(raw.get("pit_grade") or "unverifiable"),
            derived_from=_opt_str(raw.get("derived_from")),
            source_refs=raw.get("source_refs") or (),
            provenance=str(raw.get("provenance") or "observed"),
        )


@dataclass(frozen=True)
class VerdictRecord:
    """一条回检打分。``degradation_reason`` 只在 unverifiable 时有值（系统 / 数据限制）。"""

    verdict_id: str
    owner_user_id: str
    object_ref: ObjectRef
    verdict: str
    checked_at: str | None = None
    data_source: str | None = None
    auto: bool = False
    degradation_reason: str | None = None
    source_refs: tuple[str, ...] = ()
    provenance: str = "observed"

    def __post_init__(self) -> None:
        object.__setattr__(self, "verdict_id", check_ref_text(self.verdict_id, "verdict.verdict_id"))
        object.__setattr__(self, "verdict", _enum(self.verdict, ("hit", "partial", "miss", "unverifiable"), "verdict"))
        object.__setattr__(self, "source_refs", _str_tuple(self.source_refs, "verdict.source_refs"))
        object.__setattr__(self, "provenance", _enum(self.provenance, PROVENANCES, "verdict.provenance"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict_id": self.verdict_id,
            "owner_user_id": self.owner_user_id,
            "object_ref": self.object_ref.to_dict(),
            "verdict": self.verdict,
            "checked_at": self.checked_at,
            "data_source": self.data_source,
            "auto": self.auto,
            "degradation_reason": self.degradation_reason,
            "source_refs": list(self.source_refs),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> VerdictRecord:
        return cls(
            verdict_id=str(raw.get("verdict_id") or ""),
            owner_user_id=str(raw.get("owner_user_id") or ""),
            object_ref=ObjectRef.from_dict(raw.get("object_ref") or {}, where="verdict.object_ref"),
            verdict=str(raw.get("verdict") or ""),
            checked_at=_opt_str(raw.get("checked_at")),
            data_source=_opt_str(raw.get("data_source")),
            auto=bool(raw.get("auto", False)),
            degradation_reason=_opt_str(raw.get("degradation_reason")),
            source_refs=raw.get("source_refs") or (),
            provenance=str(raw.get("provenance") or "observed"),
        )


@dataclass(frozen=True)
class ProcessReceipt:
    """用户 / 系统实际做了什么的收据。``payload`` 按 ``kind`` 校验必填键（见 ``REQUIRED_PAYLOAD``）。

    ``occurred_at`` 是行为发生时刻，``recorded_at`` 是收据落盘时刻；判可知性用前者，过 cutoff 用后者。
    """

    receipt_id: str
    owner_user_id: str
    kind: str
    object_ref: ObjectRef | None = None
    occurred_at: str | None = None
    recorded_at: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    source_refs: tuple[str, ...] = ()
    provenance: str = "observed"

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", check_ref_text(self.receipt_id, "receipt.receipt_id"))
        object.__setattr__(self, "kind", _enum(self.kind, RECEIPT_KINDS, "receipt.kind"))
        object.__setattr__(self, "source_refs", _str_tuple(self.source_refs, "receipt.source_refs"))
        object.__setattr__(self, "provenance", _enum(self.provenance, PROVENANCES, "receipt.provenance"))
        payload = dict(self.payload or {})
        missing = [k for k in REQUIRED_PAYLOAD.get(self.kind, ()) if payload.get(k) in (None, "")]
        if missing:
            raise DiagnosticsInputError(f"receipt kind={self.kind} 缺 payload 键 {missing}")
        if self.kind == "stage_use":
            grade = payload.get("stage_label_grade")
            if grade is not None:
                payload["stage_label_grade"] = _enum(grade, STAGE_LABEL_GRADES, "stage_use.stage_label_grade")
        object.__setattr__(self, "payload", payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "owner_user_id": self.owner_user_id,
            "kind": self.kind,
            "object_ref": self.object_ref.to_dict() if self.object_ref else None,
            "occurred_at": self.occurred_at,
            "recorded_at": self.recorded_at,
            "payload": dict(self.payload),
            "source_refs": list(self.source_refs),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ProcessReceipt:
        ref = raw.get("object_ref")
        return cls(
            receipt_id=str(raw.get("receipt_id") or ""),
            owner_user_id=str(raw.get("owner_user_id") or ""),
            kind=str(raw.get("kind") or ""),
            object_ref=ObjectRef.from_dict(ref, where="receipt.object_ref") if ref else None,
            occurred_at=_opt_str(raw.get("occurred_at")),
            recorded_at=_opt_str(raw.get("recorded_at")),
            payload=dict(raw.get("payload") or {}),
            source_refs=raw.get("source_refs") or (),
            provenance=str(raw.get("provenance") or "observed"),
        )


REQUIRED_PAYLOAD: dict[str, tuple[str, ...]] = {
    "evidence_use": ("evidence_ref",),
    "revision": ("to_version",),
    "stage_use": ("method_ref",),
    "review": ("action",),
    "exposure": ("target_ref",),
    "backfill": (),
    "system_failure": ("scope",),
    "coverage": ("ledger", "complete_through"),
    "exercise_seen": (),
    "learner_declaration": ("declared",),
    "model_exposure": ("outcome_identity",),
}


# --------------------------------------------------------------------------- #
# 输入：01 维护报告的只读视图
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EvidenceVersionView:
    ref: str
    source_hash: str | None
    valid_from: str | None
    valid_to: str | None
    recorded_at: str | None
    expired_at: str | None
    supersedes_ref: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "source_hash": self.source_hash,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "recorded_at": self.recorded_at,
            "expired_at": self.expired_at,
            "supersedes_ref": self.supersedes_ref,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> EvidenceVersionView:
        return cls(
            ref=check_ref_text(raw.get("ref"), "evidence_version.ref"),
            source_hash=_opt_str(raw.get("source_hash")),
            valid_from=_opt_str(raw.get("valid_from")),
            valid_to=_opt_str(raw.get("valid_to")),
            recorded_at=_opt_str(raw.get("recorded_at")),
            expired_at=_opt_str(raw.get("expired_at")),
            supersedes_ref=_opt_str(raw.get("supersedes_ref")),
        )


@dataclass(frozen=True)
class MaintenanceItemView:
    """01 ``MaintenanceItem`` 的只读投影：只取本轨要用的字段，不复制判定器。"""

    item_id: str
    report_id: str
    object_ref: ObjectRef
    change_type: str
    reason_code: str
    as_of: str | None
    knowledge_cutoff: str | None
    pit_grade: str
    before: tuple[EvidenceVersionView, ...]
    current: tuple[EvidenceVersionView, ...]
    # 来源必须跟着输入走：合成维护证据不能混进真实用户效果统计（总合同 §5 第 8 条）。
    # ``provenance_declared=False`` 表示 01 报告没写来源、这里按失败关闭默认成 synthetic，不是认证结果。
    provenance: str = "synthetic"
    provenance_declared: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "report_id": self.report_id,
            "object_ref": self.object_ref.to_dict(),
            "change_type": self.change_type,
            "reason_code": self.reason_code,
            "as_of": self.as_of,
            "knowledge_cutoff": self.knowledge_cutoff,
            "pit_grade": self.pit_grade,
            "before": [v.to_dict() for v in self.before],
            "current": [v.to_dict() for v in self.current],
            "provenance": self.provenance,
            "provenance_declared": self.provenance_declared,
        }


def parse_maintenance_reports(
    reports: Iterable[Mapping[str, Any]], *, owner_user_id: str
) -> tuple[MaintenanceItemView, ...]:
    """把 01 的 ``judgment-maintenance/v1`` 报告拆成项视图；版本不对、owner 不对都拒绝。

    来源（``provenance``）跟着项一起传出去：报告级声明，项可自带覆盖。**没有声明时失败关闭成
    ``synthetic``**——``PROVENANCES`` 只有 ``observed/synthetic`` 两个值，没有「未知」档，而 ``observed``
    是一句「这是真实用户效果」的断言，必须被证明而不是被默认。01 现有产物还不带这个字段，所以缺声明
    会标 ``provenance_declared=False``，由 ``diagnose`` 出一条 gap 让降级可见（接线见 06）。
    """
    out: list[MaintenanceItemView] = []
    for i, report in enumerate(reports or ()):
        where = f"maintenance_reports[{i}]"
        if not isinstance(report, Mapping):
            raise DiagnosticsInputError(f"{where} 必须是对象")
        require_schema(report, MAINTENANCE_SCHEMA_VERSION, where=where)
        require_owner(owner_user_id, report.get("owner_user_id"), where=where)
        report_id = check_ref_text(report.get("id"), f"{where}.id")
        report_pit = str(report.get("pit_grade") or "unverifiable")
        report_prov = _opt_str(report.get("provenance"))
        for j, item in enumerate(report.get("items") or []):
            w = f"{where}.items[{j}]"
            if not isinstance(item, Mapping):
                raise DiagnosticsInputError(f"{w} 必须是对象")
            item_schema = item.get("schema_version")
            if item_schema is not None and str(item_schema) != MAINTENANCE_SCHEMA_VERSION:
                raise UnsupportedSchema(f"{w} schema_version={item_schema!r}")
            require_owner(owner_user_id, item.get("owner_user_id", report.get("owner_user_id")), where=w)
            declared = _opt_str(item.get("provenance")) or report_prov
            out.append(
                MaintenanceItemView(
                    item_id=check_ref_text(item.get("id"), f"{w}.id"),
                    report_id=report_id,
                    object_ref=ObjectRef.from_dict(item.get("object_ref") or {}, where=f"{w}.object_ref"),
                    change_type=str(item.get("change_type") or "unknown"),
                    reason_code=str(item.get("reason_code") or "unknown"),
                    as_of=_opt_str(item.get("as_of")),
                    knowledge_cutoff=_opt_str(item.get("knowledge_cutoff")),
                    pit_grade=_enum(item.get("pit_grade") or report_pit, PIT_GRADES, f"{w}.pit_grade"),
                    before=tuple(EvidenceVersionView.from_dict(v) for v in (item.get("before") or [])),
                    current=tuple(EvidenceVersionView.from_dict(v) for v in (item.get("current") or [])),
                    provenance=_enum(declared or "synthetic", PROVENANCES, f"{w}.provenance"),
                    provenance_declared=declared is not None,
                )
            )
    return tuple(out)


# --------------------------------------------------------------------------- #
# 输入：策略（规则版本 + 适用表）
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rule:
    """一条当时适用的显式规则。``effective_from/to`` 是日期；行为时刻不在效则不能据它判 issue。"""

    rule_id: str
    rule_version: str
    kind: str
    effective_from: str | None = None
    effective_to: str | None = None
    applies_to_object_kinds: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", check_ref_text(self.rule_id, "rule.rule_id"))
        object.__setattr__(self, "rule_version", check_ref_text(self.rule_version, "rule.rule_version"))
        object.__setattr__(self, "kind", _enum(self.kind, KINDS, "rule.kind"))
        kinds = _str_tuple(self.applies_to_object_kinds, "rule.applies_to_object_kinds")
        for k in kinds:
            _enum(k, OBJECT_KINDS, "rule.applies_to_object_kinds[]")
        object.__setattr__(self, "applies_to_object_kinds", kinds)
        object.__setattr__(self, "params", dict(self.params or {}))

    def in_effect(self, at: str | None) -> bool | None:
        """行为时刻 ``at``（ISO）时本规则是否在效；``at`` 未知返回 None。"""
        if not at:
            return None
        day = at[:10]
        if self.effective_from and day < self.effective_from:
            return False
        if self.effective_to and day > self.effective_to:
            return False
        return True

    def applies_to(self, object_kind: str) -> bool:
        return not self.applies_to_object_kinds or object_kind in self.applies_to_object_kinds

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "kind": self.kind,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "applies_to_object_kinds": list(self.applies_to_object_kinds),
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Rule:
        return cls(
            rule_id=str(raw.get("rule_id") or ""),
            rule_version=str(raw.get("rule_version") or ""),
            kind=str(raw.get("kind") or ""),
            effective_from=_opt_str(raw.get("effective_from")),
            effective_to=_opt_str(raw.get("effective_to")),
            applies_to_object_kinds=raw.get("applies_to_object_kinds") or (),
            params=dict(raw.get("params") or {}),
        )


@dataclass(frozen=True)
class ApplicabilityTable:
    """某方法在哪些阶段适用的版本化表。``method_version=None`` 表示对该方法所有版本适用。"""

    table_ref: str
    version: str
    method_ref: str
    applicable_stages: tuple[str, ...]
    method_version: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "table_ref", check_ref_text(self.table_ref, "applicability_table.table_ref"))
        object.__setattr__(self, "version", check_ref_text(self.version, "applicability_table.version"))
        object.__setattr__(self, "method_ref", check_ref_text(self.method_ref, "applicability_table.method_ref"))
        object.__setattr__(
            self, "applicable_stages", _str_tuple(self.applicable_stages, "applicability_table.applicable_stages")
        )

    def in_effect(self, at: str | None) -> bool | None:
        if not at:
            return None
        day = at[:10]
        if self.effective_from and day < self.effective_from:
            return False
        if self.effective_to and day > self.effective_to:
            return False
        return True

    def matches(self, method_ref: str, method_version: str | None) -> bool:
        if method_ref != self.method_ref:
            return False
        return self.method_version is None or method_version is None or self.method_version == method_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_ref": self.table_ref,
            "version": self.version,
            "method_ref": self.method_ref,
            "method_version": self.method_version,
            "applicable_stages": list(self.applicable_stages),
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> ApplicabilityTable:
        return cls(
            table_ref=str(raw.get("table_ref") or ""),
            version=str(raw.get("version") or ""),
            method_ref=str(raw.get("method_ref") or ""),
            applicable_stages=raw.get("applicable_stages") or (),
            method_version=_opt_str(raw.get("method_version")),
            effective_from=_opt_str(raw.get("effective_from")),
            effective_to=_opt_str(raw.get("effective_to")),
        )


@dataclass(frozen=True)
class DiagnosticPolicy:
    policy_id: str
    rules: tuple[Rule, ...] = ()
    applicability_tables: tuple[ApplicabilityTable, ...] = ()
    min_sample: int = 10
    schema_version: str = POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != POLICY_SCHEMA_VERSION:
            raise UnsupportedSchema(f"policy schema_version={self.schema_version!r}，只接 {POLICY_SCHEMA_VERSION!r}")
        object.__setattr__(self, "policy_id", check_ref_text(self.policy_id, "policy.policy_id"))
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "applicability_tables", tuple(self.applicability_tables))
        if int(self.min_sample) < 1:
            raise DiagnosticsInputError("policy.min_sample 至少为 1")

    def rule_for(self, kind: str, object_kind: str, at: str | None) -> tuple[Rule | None, str | None]:
        """找到行为时刻在效、对该对象类型适用的规则。返回 ``(rule, gap_reason)``。

        ``at`` 未知 → ``(None, "rule_time_unknown")``；无规则在效 → ``(None, "rule_not_in_effect")``。
        两个以上同时在效取 ``(rule_id, rule_version)`` 字典序最大的——确定性优先，策略作者应避免重叠。
        """
        candidates = [r for r in self.rules if r.kind == kind and r.applies_to(object_kind)]
        if not candidates:
            return None, "rule_not_defined"
        if not at:
            return None, "rule_time_unknown"
        live = [r for r in candidates if r.in_effect(at)]
        if not live:
            return None, "rule_not_in_effect"
        live.sort(key=lambda r: (r.rule_id, r.rule_version))
        return live[-1], None

    def table_for(self, method_ref: str, method_version: str | None, at: str | None) -> tuple[ApplicabilityTable | None, str | None]:
        candidates = [t for t in self.applicability_tables if t.matches(method_ref, method_version)]
        if not candidates:
            return None, "applicability_table_missing"
        if not at:
            return None, "rule_time_unknown"
        live = [t for t in candidates if t.in_effect(at)]
        if not live:
            return None, "applicability_table_not_in_effect"
        live.sort(key=lambda t: (t.table_ref, t.version))
        return live[-1], None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "rules": [r.to_dict() for r in self.rules],
            "applicability_tables": [t.to_dict() for t in self.applicability_tables],
            "min_sample": self.min_sample,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> DiagnosticPolicy:
        if not isinstance(raw, Mapping):
            raise DiagnosticsInputError("policy 必须是对象")
        require_schema(raw, POLICY_SCHEMA_VERSION, where="policy")
        return cls(
            policy_id=str(raw.get("policy_id") or ""),
            rules=tuple(Rule.from_dict(r) for r in (raw.get("rules") or [])),
            applicability_tables=tuple(ApplicabilityTable.from_dict(t) for t in (raw.get("applicability_tables") or [])),
            min_sample=int(raw.get("min_sample") or 10),
            schema_version=str(raw.get("schema_version") or ""),
        )


# --------------------------------------------------------------------------- #
# 输入：冻结题包
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ExerciseMaterial:
    ref: str
    dated: str | None  # 材料自身的日期；None = 时间不明，不能进严格题包

    def to_dict(self) -> dict[str, Any]:
        return {"ref": self.ref, "dated": self.dated}


@dataclass(frozen=True)
class AnswerKey:
    """隐藏答案。``ref`` 是不透明引用，学习者投影只见 ref 不见内容。"""

    ref: str
    expected_choices: tuple[str, ...]
    expected_refs: tuple[str, ...]
    explanation_ref: str
    rule_id: str
    rule_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ref", check_ref_text(self.ref, "answer_key.ref"))
        object.__setattr__(self, "expected_choices", _str_tuple(self.expected_choices, "answer_key.expected_choices"))
        object.__setattr__(self, "expected_refs", _str_tuple(self.expected_refs, "answer_key.expected_refs"))
        object.__setattr__(self, "explanation_ref", check_ref_text(self.explanation_ref, "answer_key.explanation_ref"))
        object.__setattr__(self, "rule_id", check_ref_text(self.rule_id, "answer_key.rule_id"))
        object.__setattr__(self, "rule_version", check_ref_text(self.rule_version, "answer_key.rule_version"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "expected_choices": list(self.expected_choices),
            "expected_refs": list(self.expected_refs),
            "explanation_ref": self.explanation_ref,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> AnswerKey:
        return cls(
            ref=str(raw.get("ref") or ""),
            expected_choices=raw.get("expected_choices") or (),
            expected_refs=raw.get("expected_refs") or (),
            explanation_ref=str(raw.get("explanation_ref") or ""),
            rule_id=str(raw.get("rule_id") or ""),
            rule_version=str(raw.get("rule_version") or ""),
        )


@dataclass(frozen=True)
class ExerciseCase:
    """题包里的一题。``outcome_identity`` 是底层结局身份哈希：改名、去日期都不改变它，泄漏判定按它走。"""

    case_id: str
    case_ref: str
    kind: str
    training_goal: str
    as_of: str
    knowledge_cutoff: str
    prompt: str
    visible_evidence_refs: tuple[str, ...]
    materials: tuple[ExerciseMaterial, ...]
    answer_key: AnswerKey
    outcome_identity: str
    pack_version: str
    declared_data_pit_grade: str = "trade_date_only"
    model_exposure_grade: str = "deterministic_only"
    provenance: str = "synthetic"

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", check_ref_text(self.case_id, "case.case_id"))
        object.__setattr__(self, "case_ref", check_ref_text(self.case_ref, "case.case_ref"))
        object.__setattr__(self, "kind", _enum(self.kind, KINDS, "case.kind"))
        object.__setattr__(self, "outcome_identity", check_ref_text(self.outcome_identity, "case.outcome_identity"))
        object.__setattr__(self, "pack_version", check_ref_text(self.pack_version, "case.pack_version"))
        object.__setattr__(self, "visible_evidence_refs", _str_tuple(self.visible_evidence_refs, "case.visible_evidence_refs"))
        object.__setattr__(self, "materials", tuple(self.materials))
        object.__setattr__(
            self, "declared_data_pit_grade", _enum(self.declared_data_pit_grade, PIT_GRADES, "case.declared_data_pit_grade")
        )
        object.__setattr__(
            self, "model_exposure_grade", _enum(self.model_exposure_grade, MODEL_EXPOSURE_GRADES, "case.model_exposure_grade")
        )
        object.__setattr__(self, "provenance", _enum(self.provenance, PROVENANCES, "case.provenance"))
        if not str(self.prompt or "").strip():
            raise DiagnosticsInputError("case.prompt 不能为空")
        if not self.as_of or not self.knowledge_cutoff:
            raise DiagnosticsInputError("case 需要 as_of 与 knowledge_cutoff")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_ref": self.case_ref,
            "kind": self.kind,
            "training_goal": self.training_goal,
            "as_of": self.as_of,
            "knowledge_cutoff": self.knowledge_cutoff,
            "prompt": self.prompt,
            "visible_evidence_refs": list(self.visible_evidence_refs),
            "materials": [m.to_dict() for m in self.materials],
            "answer_key": self.answer_key.to_dict(),
            "outcome_identity": self.outcome_identity,
            "pack_version": self.pack_version,
            "declared_data_pit_grade": self.declared_data_pit_grade,
            "model_exposure_grade": self.model_exposure_grade,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], *, pack_version: str | None = None) -> ExerciseCase:
        return cls(
            case_id=str(raw.get("case_id") or ""),
            case_ref=str(raw.get("case_ref") or ""),
            kind=str(raw.get("kind") or ""),
            training_goal=str(raw.get("training_goal") or ""),
            as_of=str(raw.get("as_of") or ""),
            knowledge_cutoff=str(raw.get("knowledge_cutoff") or ""),
            prompt=str(raw.get("prompt") or ""),
            visible_evidence_refs=raw.get("visible_evidence_refs") or (),
            materials=tuple(
                ExerciseMaterial(ref=check_ref_text(m.get("ref"), "material.ref"), dated=_opt_str(m.get("dated")))
                for m in (raw.get("materials") or [])
            ),
            answer_key=AnswerKey.from_dict(raw.get("answer_key") or {}),
            outcome_identity=str(raw.get("outcome_identity") or ""),
            pack_version=str(raw.get("pack_version") or pack_version or ""),
            declared_data_pit_grade=str(raw.get("declared_data_pit_grade") or "trade_date_only"),
            model_exposure_grade=str(raw.get("model_exposure_grade") or "deterministic_only"),
            provenance=str(raw.get("provenance") or "synthetic"),
        )


def parse_exercise_pack(raw: Mapping[str, Any]) -> tuple[ExerciseCase, ...]:
    """题包文件 → 题列表。版本不对拒绝；``pack_version`` 下发到每题。"""
    if not isinstance(raw, Mapping):
        raise DiagnosticsInputError("exercise pack 必须是对象")
    require_schema(raw, EXERCISE_PACK_SCHEMA_VERSION, where="exercise_pack")
    version = check_ref_text(raw.get("pack_version"), "exercise_pack.pack_version")
    cases = tuple(ExerciseCase.from_dict(c, pack_version=version) for c in (raw.get("cases") or []))
    ids = [c.case_id for c in cases]
    if len(ids) != len(set(ids)):
        raise DiagnosticsInputError("exercise pack 内 case_id 重复")
    return cases


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Gap:
    """缺口：``reason`` 机器码，``ref`` 指向缺的对象，``retryable`` 表示补了输入能不能重算。"""

    reason: str
    ref: str | None = None
    retryable: bool = True
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"reason": self.reason, "ref": self.ref, "retryable": self.retryable, "detail": self.detail}


@dataclass(frozen=True)
class DiagnosticFinding:
    id: str
    kind: str
    classification: str
    actor_group: str
    object_refs: tuple[ObjectRef, ...]
    evidence_refs: tuple[str, ...]
    maintenance_item_ids: tuple[str, ...]
    rule_id: str | None
    rule_version: str | None
    observed: str
    expected: str
    occurred_at: str | None
    knowledge_cutoff: str | None
    pit_grade: str
    gaps: tuple[Gap, ...]
    limitation: str
    opportunity_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "classification": self.classification,
            "actor_group": self.actor_group,
            "object_refs": [r.to_dict() for r in self.object_refs],
            "evidence_refs": list(self.evidence_refs),
            "maintenance_item_ids": list(self.maintenance_item_ids),
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "observed": self.observed,
            "expected": self.expected,
            "occurred_at": self.occurred_at,
            "knowledge_cutoff": self.knowledge_cutoff,
            "pit_grade": self.pit_grade,
            "gaps": [g.to_dict() for g in self.gaps],
            "limitation": self.limitation,
            "opportunity_key": self.opportunity_key,
        }


@dataclass(frozen=True)
class Exclusion:
    """被排除的机会：一机会一桶，并列原因。"""

    kind: str
    actor_group: str
    object_identity: str
    reason: str
    opportunity_key: str
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "actor_group": self.actor_group,
            "object_identity": self.object_identity,
            "reason": self.reason,
            "opportunity_key": self.opportunity_key,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Denominator:
    kind: str
    actor_group: str
    eligible: int
    evaluated: int
    issue: int
    context: int
    unknown: int
    excluded: int
    sample_refs: tuple[str, ...]
    exclusion_reasons: Mapping[str, int]
    unit: str = DENOMINATOR_UNIT
    rate: None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "actor_group": self.actor_group,
            "eligible": self.eligible,
            "evaluated": self.evaluated,
            "issue": self.issue,
            "context": self.context,
            "unknown": self.unknown,
            "excluded": self.excluded,
            "unit": self.unit,
            "sample_refs": list(self.sample_refs),
            "exclusion_reasons": dict(sorted(self.exclusion_reasons.items())),
            "rate": self.rate,
        }


@dataclass(frozen=True)
class NonAttributable:
    kind: str
    object_identity: str
    reason: str
    refs: tuple[str, ...]
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "object_identity": self.object_identity,
            "reason": self.reason,
            "refs": list(self.refs),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class UncertaintyFlag:
    kind: str
    detail: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _enum(self.kind, UNCERTAINTY_KINDS, "uncertainty.kind"))

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "detail": self.detail}


@dataclass(frozen=True)
class HistoricalExercise:
    """学习者投影：只含 prompt / 可见引用 / 三轴分档 / 不透明 answer_key_ref。**没有答案、没有结局。**"""

    id: str
    target_finding_id: str
    case_ref: str
    as_of: str
    knowledge_cutoff: str
    prompt: str
    visible_evidence_refs: tuple[str, ...]
    projection_hash: str
    data_pit_grade: str
    model_exposure_grade: str
    learner_exposure_grade: str
    exercise_status: str
    answer_key_ref: str
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_finding_id": self.target_finding_id,
            "case_ref": self.case_ref,
            "as_of": self.as_of,
            "knowledge_cutoff": self.knowledge_cutoff,
            "prompt": self.prompt,
            "visible_evidence_refs": list(self.visible_evidence_refs),
            "projection_hash": self.projection_hash,
            "data_pit_grade": self.data_pit_grade,
            "model_exposure_grade": self.model_exposure_grade,
            "learner_exposure_grade": self.learner_exposure_grade,
            "exercise_status": self.exercise_status,
            "answer_key_ref": self.answer_key_ref,
            "limitation": self.limitation,
        }


@dataclass(frozen=True)
class ExerciseResponse:
    exercise_id: str
    selected_choices: tuple[str, ...] = ()
    cited_refs: tuple[str, ...] = ()
    rationale: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "exercise_id", check_ref_text(self.exercise_id, "response.exercise_id"))
        object.__setattr__(self, "selected_choices", _str_tuple(self.selected_choices, "response.selected_choices"))
        object.__setattr__(self, "cited_refs", _str_tuple(self.cited_refs, "response.cited_refs"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "exercise_id": self.exercise_id,
            "selected_choices": list(self.selected_choices),
            "cited_refs": list(self.cited_refs),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ExerciseCheck:
    name: str
    passed: bool
    expected: tuple[str, ...]
    got: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "expected": list(self.expected), "got": list(self.got)}


@dataclass(frozen=True)
class ExerciseFeedback:
    exercise_id: str
    status: str
    checks: tuple[ExerciseCheck, ...]
    missing_evidence_refs: tuple[str, ...]
    explanation_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "exercise_id": self.exercise_id,
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
            "missing_evidence_refs": list(self.missing_evidence_refs),
            "explanation_ref": self.explanation_ref,
        }


@dataclass(frozen=True)
class InputSummary:
    """输入规模与过滤计数：给 06 展示「这份报告看了多少东西」，不进任何率。"""

    records: int
    verdicts: int
    receipts: int
    maintenance_items: int
    exercise_cases: int
    filtered_after_cutoff: int
    out_of_range: int
    duplicates_dropped: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "records": self.records,
            "verdicts": self.verdicts,
            "receipts": self.receipts,
            "maintenance_items": self.maintenance_items,
            "exercise_cases": self.exercise_cases,
            "filtered_after_cutoff": self.filtered_after_cutoff,
            "out_of_range": self.out_of_range,
            "duplicates_dropped": self.duplicates_dropped,
        }


@dataclass(frozen=True)
class DiagnosticReport:
    id: str
    owner_user_id: str
    start: str
    end: str
    knowledge_cutoff: str
    input_digest: str
    generated_at: str | None
    pit_grade: str
    gaps: tuple[Gap, ...]
    findings: tuple[DiagnosticFinding, ...]
    denominators: tuple[Denominator, ...]
    exclusions: tuple[Exclusion, ...]
    uncertainty: tuple[UncertaintyFlag, ...]
    non_attributable: tuple[NonAttributable, ...]
    exercise: HistoricalExercise | None
    input_summary: InputSummary
    provenance: str
    policy_id: str
    schema_version: str = SCHEMA_VERSION

    def content_dict(self) -> dict[str, Any]:
        """参与 id 的内容：不含 ``id`` 与 ``generated_at``。"""
        return {
            "schema_version": self.schema_version,
            "owner_user_id": self.owner_user_id,
            "start": self.start,
            "end": self.end,
            "knowledge_cutoff": self.knowledge_cutoff,
            "input_digest": self.input_digest,
            "pit_grade": self.pit_grade,
            "gaps": [g.to_dict() for g in self.gaps],
            "findings": [f.to_dict() for f in self.findings],
            "denominators": [d.to_dict() for d in self.denominators],
            "exclusions": [e.to_dict() for e in self.exclusions],
            "uncertainty": [u.to_dict() for u in self.uncertainty],
            "non_attributable": [n.to_dict() for n in self.non_attributable],
            "exercise": self.exercise.to_dict() if self.exercise else None,
            "input_summary": self.input_summary.to_dict(),
            "provenance": self.provenance,
            "policy_id": self.policy_id,
        }

    def to_dict(self) -> dict[str, Any]:
        out = self.content_dict()
        out["id"] = self.id
        out["generated_at"] = self.generated_at
        return out

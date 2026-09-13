"""判断持续维护 · 交换合同（spec 01 §3 / §5；总合同 §5）。

这里只有数据形状、词表、校验与稳定摘要：不读文件、不查库、不联网、不依赖 cwd。
06 用同一份合同把真实对象（checkpoint / judgment / 情景树）适配进来，04 用它读夹具。

三条贯穿全包的纪律：

- **未知版本 / 未知枚举 / 未知字段一律拒绝**（``MaintenanceContractError``），不默默按默认值走：
  「填了没人读」和「读了不存在的字段」都是这么长出来的。
- **归属只认经验证的 ``owner_user_id``**：请求正文里的 owner、引用里的用户目录段都要与它一致，
  不一致就拒绝，且错误信息里不回显对方 id（不泄露存在性）。
- **内容摘要不含扫描时间**：``generated_at`` 只是展示元数据；id / item_version / input_digest
  全部由输入内容派生，同输入同 id，乱序、重复输入不重造项。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime
from typing import Any, Mapping

from intelligence import userspace

# --------------------------------------------------------------------------- #
# 版本号与词表
# --------------------------------------------------------------------------- #
SCHEMA_VERSION = "judgment-maintenance/v1"
POLICY_SCHEMA_VERSION = "judgment-maintenance-policy/v1"
BINDING_SCHEMA_VERSION = "judgment-maintenance-binding/v1"
EVIDENCE_SCHEMA_VERSION = "judgment-maintenance-evidence/v1"
OBSERVATION_SCHEMA_VERSION = "judgment-maintenance-observation/v1"
COMMAND_SCHEMA_VERSION = "judgment-maintenance-command/v1"
EVENT_SCHEMA_VERSION = "judgment-maintenance-event/v1"
ACTION_RESULT_SCHEMA_VERSION = "judgment-maintenance-action-result/v1"

CHANGE_TYPES = (
    "content_changed",
    "source_corrected",
    "source_expired",
    "dependency_missing",
    "condition_evaluated",
    "unchanged",
)
REASON_CODES = (
    "hash_changed",
    "explicit_supersession",
    "validity_ended",
    "ref_unresolved",
    "time_metadata_missing",
    "dependency_unbound",
    "condition_true",
    "condition_false",
    "condition_unknown",
    "no_change",
)
EPISTEMIC_STATES = ("observed", "requires_review", "unknown")
# JSON 里 condition_result 用字符串 "true" / "false" / "unknown"，null = 未登记确定性条件。
CONDITION_RESULTS = ("true", "false", "unknown")
ITEM_STATUSES = ("open", "claimed", "snoozed", "rejudgment_requested", "closed", "superseded")
# 待办口径：这些状态算「还在手上」；snoozed 是主动搁置，closed / superseded 是终态。
OPEN_STATUSES = ("open", "claimed", "rejudgment_requested")
ACTIONS = ("review_evidence", "restore_evidence", "rejudge", "none")
PIT_GRADES = ("strict", "trade_date_only", "unverifiable")
_PIT_RANK = {"strict": 2, "trade_date_only": 1, "unverifiable": 0}
CONDITION_ROLES = ("upgrade", "downgrade", "abandon", "review")
BINDING_ORIGINS = ("user_confirmed", "verified_structured_output")
# 与 river.Derivation 对齐（deterministic / frozen_llm）；unknown 只给「绑定时有哈希、无来源对象」的基线占位。
DERIVATIONS = ("deterministic", "frozen_llm", "unknown")
OBJECT_KINDS = ("checkpoint", "judgment", "scenario_tree", "observation_script")
DEFAULT_OBJECT_NAMESPACES = ("checkpoints", "judgments", "scenario_trees", "observation_scripts")
COMMANDS = ("claim", "snooze", "rejudge", "reviewed_no_change")
COMMAND_EVENT_KIND = {
    "claim": "claimed",
    "snooze": "snoozed",
    "rejudge": "rejudgment_requested",
    "reviewed_no_change": "reviewed_no_change",
}
# 前四种由用户命令派生；后三种是 06 接旧研究正门后的系统事件（成功关联 / 失败 / 取消）。
EVENT_KINDS = (
    "claimed",
    "snoozed",
    "rejudgment_requested",
    "reviewed_no_change",
    "rejudgment_linked",
    "rejudgment_failed",
    "rejudgment_cancelled",
)
ACTION_RESULT_STATUSES = ("accepted", "replayed", "conflict", "rejected")

ITEM_ID_PREFIX = "jmi-"
REPORT_ID_PREFIX = "jmr-"
EVENT_ID_PREFIX = "jme-"


class MaintenanceContractError(ValueError):
    """合同不满足：``code`` 稳定业务码、``where`` 字段路径、``detail`` 人读说明。"""

    def __init__(self, code: str, where: str, detail: str = "") -> None:
        self.code = code
        self.where = where
        self.detail = detail
        super().__init__(f"{code}@{where}" + (f": {detail}" if detail else ""))


# --------------------------------------------------------------------------- #
# 稳定摘要
# --------------------------------------------------------------------------- #
def canonical_json(payload: Any) -> str:
    """键排序、无空白、非 ASCII 原样——同一内容永远同一串字节。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def short_hash(payload: Any, n: int = 16) -> str:
    return sha256_hex(payload)[:n]


def weakest_pit(grades: Any) -> str:
    """多档取最弱；空集合 fail closed 为 unverifiable（``all([])`` 恒真的坑同 river.pit_grade）。"""
    grades = [g for g in grades if g in _PIT_RANK]
    if not grades:
        return "unverifiable"
    return min(grades, key=lambda g: _PIT_RANK[g])


# --------------------------------------------------------------------------- #
# 基础校验
# --------------------------------------------------------------------------- #
_OWNER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 引用：表:主键 / 台账文件:记录 id / content_sha256:<hex>。允许中文实体名（river 的 ref 带题材名）。
# 不允许空白、控制字符、反斜杠、绝对路径与 ``..`` 段——本包不开文件，但 06 会拿 ref 去解析。
_REF_CHARS_RE = re.compile(r"^[A-Za-z0-9一-鿿][A-Za-z0-9一-鿿._:/@#=+%,()\[\]\-]{0,255}$")
_USERS_SEG_RE = re.compile(r"(?:^|/)users/([^/]+)/")


def _as_mapping(data: Any, where: str) -> Mapping[str, Any]:
    if isinstance(data, Mapping):
        return data
    raise MaintenanceContractError("invalid_shape", where, f"需要对象，收到 {type(data).__name__}")


def _reject_unknown_keys(data: Mapping[str, Any], allowed: tuple[str, ...], where: str) -> None:
    extra = sorted(set(data) - set(allowed))
    if extra:
        raise MaintenanceContractError("unknown_field", where, f"未知字段 {extra}")


def _req_str(data: Mapping[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MaintenanceContractError("missing_field", f"{where}.{key}", "必填字符串缺失或为空")
    return value.strip()


def _opt_str(data: Mapping[str, Any], key: str, where: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MaintenanceContractError("invalid_type", f"{where}.{key}", "需要字符串或 null")
    value = value.strip()
    return value or None


def _req_int(data: Mapping[str, Any], key: str, where: str, *, minimum: int = 0) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise MaintenanceContractError("invalid_type", f"{where}.{key}", f"需要 ≥{minimum} 的整数")
    return value


def _opt_bool(data: Mapping[str, Any], key: str, where: str, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise MaintenanceContractError("invalid_type", f"{where}.{key}", "需要 true / false")
    return value


def _enum(value: Any, allowed: tuple[str, ...], where: str) -> str:
    if value not in allowed:
        raise MaintenanceContractError("unknown_enum", where, f"{value!r} 不在 {list(allowed)}")
    return str(value)


def _schema(data: Mapping[str, Any], expected: str, where: str, *, required: bool) -> str:
    value = data.get("schema_version")
    if value is None and not required:
        return expected
    if value != expected:
        raise MaintenanceContractError("unknown_schema_version", f"{where}.schema_version", f"期望 {expected}，收到 {value!r}")
    return expected


def validate_owner(value: Any, where: str) -> str:
    """owner 只认合法 user_id；判据与 ``userspace.resolve_user_id`` 同一条，再过一次现役实现防两处漂移。"""
    if not isinstance(value, str) or not value.strip():
        raise MaintenanceContractError("invalid_owner", where, "owner_user_id 缺失")
    raw = value.strip()
    if raw in {".", ".."} or "/" in raw or "\\" in raw or not _OWNER_RE.match(raw):
        raise MaintenanceContractError("invalid_owner", where, "非法 owner_user_id（只允许字母数字与 . _ -，不得含路径分隔）")
    try:
        userspace.resolve_user_id(raw)
    except ValueError as exc:
        raise MaintenanceContractError("invalid_owner", where, str(exc)) from exc
    return raw


def validate_date(value: Any, where: str) -> str:
    """市场日 / 知识截止只收 ``YYYY-MM-DD``：带时分秒的截止会被当成「比日频更精确」的假承诺。"""
    if not isinstance(value, str) or not _DATE_RE.match(value.strip()):
        raise MaintenanceContractError("invalid_date", where, f"需要 YYYY-MM-DD，收到 {value!r}")
    try:
        date_cls.fromisoformat(value.strip())
    except ValueError as exc:
        raise MaintenanceContractError("invalid_date", where, f"非法日期 {value!r}") from exc
    return value.strip()


def validate_stamp(value: Any, where: str) -> str:
    """记录时刻 / 动作时刻：ISO 日期或日期时间，原样保留（不补假时分秒，不截精度）。"""
    if not isinstance(value, str) or not value.strip():
        raise MaintenanceContractError("invalid_stamp", where, "需要 ISO 时间字符串")
    raw = value.strip()
    try:
        if len(raw) == 10:
            date_cls.fromisoformat(raw)
        else:
            datetime.fromisoformat(raw)
    except ValueError as exc:
        raise MaintenanceContractError("invalid_stamp", where, f"非法 ISO 时间 {value!r}") from exc
    return raw


def day_of(stamp: str | None) -> str | None:
    return stamp[:10] if stamp else None


def validate_ref(value: Any, *, owner_user_id: str, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MaintenanceContractError("invalid_ref", where, "引用缺失")
    raw = value.strip()
    if not _REF_CHARS_RE.match(raw) or "/../" in f"/{raw}/" or raw.endswith("/.."):
        raise MaintenanceContractError("invalid_ref", where, "引用含非法字符、绝对路径或 .. 段")
    seg = _USERS_SEG_RE.search(raw)
    if seg and seg.group(1) != owner_user_id:
        # 不回显对方 id：错误信息只说「不在本用户范围」。
        raise MaintenanceContractError("foreign_user_ref", where, "引用不在本用户范围内")
    return raw


def _scalar(value: Any, where: str) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise MaintenanceContractError("invalid_type", where, "观测值只能是标量或 null")


# --------------------------------------------------------------------------- #
# 输入对象
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ObjectRef:
    """原判断对象的身份：复用旧 id，无原生版本用 ``content_sha256:`` + 原不可变记录哈希。"""

    kind: str
    id: str | None
    namespace: str
    version_or_hash: str
    ref: str
    scope: dict[str, str] = field(default_factory=dict)

    def identity(self) -> tuple[str, str, str, str]:
        """去重身份：无 id 用可验证旧行 ref 代位。"""
        return (self.kind, self.namespace, self.id or self.ref, self.version_or_hash)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "namespace": self.namespace,
            "version_or_hash": self.version_or_hash,
            "ref": self.ref,
            "scope": dict(sorted(self.scope.items())),
        }


_OBJECT_REF_KEYS = ("kind", "id", "namespace", "version_or_hash", "ref", "scope")


def parse_object_ref(data: Any, *, owner_user_id: str, where: str) -> ObjectRef:
    if isinstance(data, ObjectRef):
        return data
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _OBJECT_REF_KEYS, where)
    kind = _enum(d.get("kind"), OBJECT_KINDS, f"{where}.kind")
    namespace = _req_str(d, "namespace", where)
    version_or_hash = _req_str(d, "version_or_hash", where)
    ref = validate_ref(d.get("ref"), owner_user_id=owner_user_id, where=f"{where}.ref")
    obj_id = _opt_str(d, "id", where)
    scope_raw = d.get("scope") or {}
    if not isinstance(scope_raw, Mapping):
        raise MaintenanceContractError("invalid_type", f"{where}.scope", "scope 需要对象")
    scope: dict[str, str] = {}
    for key, value in scope_raw.items():
        if not isinstance(key, str) or not (value is None or isinstance(value, str)):
            raise MaintenanceContractError("invalid_type", f"{where}.scope", "scope 只收 字符串→字符串")
        if value is not None and value.strip():
            scope[key] = value.strip()
    return ObjectRef(kind=kind, id=obj_id, namespace=namespace, version_or_hash=version_or_hash, ref=ref, scope=scope)


@dataclass(frozen=True)
class BindingCondition:
    """绑定上明示的确定性条件：``expression`` 必须是情景树编译器接受的 ``{"all": [谓词...]}``。

    自然语言、冻结模型散文、``otherwise`` 都不是条件——这里只存原样，编译与拒绝在 ``conditions`` 模块。
    """

    condition_id: str
    role: str
    expression: Any
    entity_id: str = ""
    label_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "role": self.role,
            "expression": self.expression,
            "entity_id": self.entity_id,
            "label_version": self.label_version,
        }


_CONDITION_KEYS = ("condition_id", "role", "expression", "entity_id", "label_version")


def parse_condition(data: Any, *, where: str) -> BindingCondition:
    if isinstance(data, BindingCondition):
        return data
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _CONDITION_KEYS, where)
    if "expression" not in d:
        raise MaintenanceContractError("missing_field", f"{where}.expression", "条件必须带表达式")
    return BindingCondition(
        condition_id=_req_str(d, "condition_id", where),
        role=_enum(d.get("role"), CONDITION_ROLES, f"{where}.role"),
        expression=d.get("expression"),
        entity_id=_opt_str(d, "entity_id", where) or "",
        label_version=_opt_str(d, "label_version", where),
    )


@dataclass(frozen=True)
class DependencyBinding:
    """自绑定时刻起持续维护的元数据（spec 01 §3）。

    它不是「原判断当时的证据」：``created_at`` 是用户确认 / 结构化输出被核实的真实时刻，
    ``baseline_cutoff`` 是解析基线哈希时的知识截止，两者都不回填到原判断的登记时刻。
    ``baseline_source_hashes[ref] = None`` 表示「绑定时明知没有哈希」——与「忘了传」分开：
    每个 ref 都必须在字典里出现，否则拒绝。
    """

    binding_id: str
    binding_version: int
    owner_user_id: str
    object_ref: ObjectRef
    baseline_evidence_refs: tuple[str, ...]
    baseline_source_hashes: dict[str, str | None]
    baseline_cutoff: str
    created_at: str
    binding_origin: str
    conditions: tuple[BindingCondition, ...] = ()
    schema_version: str = BINDING_SCHEMA_VERSION

    @property
    def created_day(self) -> str:
        return self.created_at[:10]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "binding_id": self.binding_id,
            "binding_version": self.binding_version,
            "owner_user_id": self.owner_user_id,
            "object_ref": self.object_ref.to_dict(),
            "baseline_evidence_refs": list(self.baseline_evidence_refs),
            "baseline_source_hashes": {k: self.baseline_source_hashes[k] for k in sorted(self.baseline_source_hashes)},
            "baseline_cutoff": self.baseline_cutoff,
            "created_at": self.created_at,
            "binding_origin": self.binding_origin,
            "conditions": [c.to_dict() for c in self.conditions],
        }


_BINDING_KEYS = (
    "schema_version",
    "binding_id",
    "binding_version",
    "owner_user_id",
    "object_ref",
    "baseline_evidence_refs",
    "baseline_source_hashes",
    "baseline_cutoff",
    "created_at",
    "binding_origin",
    "conditions",
)


def parse_binding(data: Any, *, owner_user_id: str, where: str) -> DependencyBinding:
    if isinstance(data, DependencyBinding):
        binding = data
        if binding.owner_user_id != owner_user_id:
            raise MaintenanceContractError("owner_mismatch", f"{where}.owner_user_id", "绑定不属于本用户")
        return binding
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _BINDING_KEYS, where)
    _schema(d, BINDING_SCHEMA_VERSION, where, required=True)
    owner = validate_owner(d.get("owner_user_id"), f"{where}.owner_user_id")
    if owner != owner_user_id:
        raise MaintenanceContractError("owner_mismatch", f"{where}.owner_user_id", "绑定不属于本用户")
    refs_raw = d.get("baseline_evidence_refs")
    if not isinstance(refs_raw, list) or not refs_raw:
        raise MaintenanceContractError("binding_without_refs", f"{where}.baseline_evidence_refs", "无引用不能绑定：主题同名不够")
    refs: list[str] = []
    for i, raw in enumerate(refs_raw):
        ref = validate_ref(raw, owner_user_id=owner_user_id, where=f"{where}.baseline_evidence_refs[{i}]")
        if ref in refs:
            raise MaintenanceContractError("duplicate_ref", f"{where}.baseline_evidence_refs[{i}]", f"引用重复 {ref}")
        refs.append(ref)
    hashes_raw = d.get("baseline_source_hashes")
    if not isinstance(hashes_raw, Mapping):
        raise MaintenanceContractError("invalid_type", f"{where}.baseline_source_hashes", "需要 ref→hash|null 字典")
    hashes: dict[str, str | None] = {}
    for ref in refs:
        if ref not in hashes_raw:
            raise MaintenanceContractError("hash_not_declared", f"{where}.baseline_source_hashes", f"{ref} 未声明哈希（明知没有请显式给 null）")
        value = hashes_raw[ref]
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise MaintenanceContractError("invalid_type", f"{where}.baseline_source_hashes[{ref}]", "哈希需要字符串或 null")
        hashes[ref] = value.strip() if isinstance(value, str) else None
    undeclared = sorted(set(hashes_raw) - set(refs))
    if undeclared:
        raise MaintenanceContractError("hash_for_undeclared_ref", f"{where}.baseline_source_hashes", f"这些 ref 不在 baseline_evidence_refs：{undeclared}")
    baseline_cutoff = validate_date(d.get("baseline_cutoff"), f"{where}.baseline_cutoff")
    created_at = validate_stamp(d.get("created_at"), f"{where}.created_at")
    if baseline_cutoff > created_at[:10]:
        raise MaintenanceContractError("baseline_cutoff_after_created_at", f"{where}.baseline_cutoff", "基线截止不能晚于绑定时刻")
    conditions_raw = d.get("conditions") or []
    if not isinstance(conditions_raw, list):
        raise MaintenanceContractError("invalid_type", f"{where}.conditions", "conditions 需要列表")
    conditions: list[BindingCondition] = []
    seen_ids: set[str] = set()
    for i, raw in enumerate(conditions_raw):
        cond = parse_condition(raw, where=f"{where}.conditions[{i}]")
        if cond.condition_id in seen_ids:
            raise MaintenanceContractError("duplicate_condition_id", f"{where}.conditions[{i}]", cond.condition_id)
        seen_ids.add(cond.condition_id)
        conditions.append(cond)
    return DependencyBinding(
        binding_id=_req_str(d, "binding_id", where),
        binding_version=_req_int(d, "binding_version", where, minimum=1),
        owner_user_id=owner,
        object_ref=parse_object_ref(d.get("object_ref"), owner_user_id=owner_user_id, where=f"{where}.object_ref"),
        baseline_evidence_refs=tuple(refs),
        baseline_source_hashes=hashes,
        baseline_cutoff=baseline_cutoff,
        created_at=created_at,
        binding_origin=_enum(d.get("binding_origin"), BINDING_ORIGINS, f"{where}.binding_origin"),
        conditions=tuple(conditions),
    )


@dataclass(frozen=True)
class EvidenceVersion:
    """一个证据引用在某个版本上的冻结观测（字段对齐 river.RiverObject，加 expired_at / supersedes_ref）。

    ``valid_from`` 是世界里什么时候为真（交易日），``recorded_at`` 是系统什么时候知道；
    两者缺一都不补：缺 recorded_at 只能按交易日放置（pit 降为 trade_date_only），
    两者都缺就放不到时间轴上（gap: time_metadata_missing）。
    """

    ref: str
    source_hash: str | None
    valid_from: str | None = None
    valid_to: str | None = None
    recorded_at: str | None = None
    expired_at: str | None = None
    supersedes_ref: str | None = None
    derivation: str = "deterministic"
    label_version: str | None = None
    namespace: str | None = None

    def dedupe_key(self) -> tuple[Any, ...]:
        return (
            self.ref,
            self.source_hash,
            self.valid_from,
            self.valid_to,
            self.recorded_at,
            self.expired_at,
            self.supersedes_ref,
            self.derivation,
            self.label_version,
            self.namespace,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "source_hash": self.source_hash,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "recorded_at": self.recorded_at,
            "expired_at": self.expired_at,
            "supersedes_ref": self.supersedes_ref,
            "derivation": self.derivation,
            "label_version": self.label_version,
            "namespace": self.namespace,
        }


_EVIDENCE_KEYS = (
    "schema_version",
    "ref",
    "source_hash",
    "valid_from",
    "valid_to",
    "recorded_at",
    "expired_at",
    "supersedes_ref",
    "derivation",
    "label_version",
    "namespace",
)


def parse_evidence_version(data: Any, *, owner_user_id: str, where: str, allow_placeholder: bool = False) -> EvidenceVersion:
    """``allow_placeholder`` 只给报告里的 ``before``：绑定时明知无哈希的基线占位（derivation=unknown）。
    输入侧的冻结版本必须带哈希——没有哈希的版本不是版本。"""
    if isinstance(data, EvidenceVersion):
        return data
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _EVIDENCE_KEYS, where)
    _schema(d, EVIDENCE_SCHEMA_VERSION, where, required=False)
    valid_from = d.get("valid_from")
    valid_to = d.get("valid_to")
    recorded_at = d.get("recorded_at")
    expired_at = d.get("expired_at")
    supersedes = _opt_str(d, "supersedes_ref", where)
    derivation = d.get("derivation", "deterministic")
    version = EvidenceVersion(
        ref=validate_ref(d.get("ref"), owner_user_id=owner_user_id, where=f"{where}.ref"),
        source_hash=_opt_str(d, "source_hash", where),
        valid_from=validate_date(valid_from, f"{where}.valid_from") if valid_from is not None else None,
        valid_to=validate_date(valid_to, f"{where}.valid_to") if valid_to is not None else None,
        recorded_at=validate_stamp(recorded_at, f"{where}.recorded_at") if recorded_at is not None else None,
        expired_at=validate_stamp(expired_at, f"{where}.expired_at") if expired_at is not None else None,
        supersedes_ref=validate_ref(supersedes, owner_user_id=owner_user_id, where=f"{where}.supersedes_ref") if supersedes else None,
        derivation=_enum(derivation, DERIVATIONS, f"{where}.derivation"),
        label_version=_opt_str(d, "label_version", where),
        namespace=_opt_str(d, "namespace", where),
    )
    if version.source_hash is None and not (allow_placeholder and version.derivation == "unknown"):
        raise MaintenanceContractError("missing_field", f"{where}.source_hash", "冻结版本必须带 source_hash（无哈希的版本不是版本）")
    if version.valid_from and version.valid_to and version.valid_to < version.valid_from:
        raise MaintenanceContractError("invalid_validity", where, "valid_to 早于 valid_from")
    if version.supersedes_ref == version.ref:
        raise MaintenanceContractError("invalid_supersession", f"{where}.supersedes_ref", "版本不能替代自己的 ref")
    return version


@dataclass(frozen=True)
class ConditionObservation:
    """某个注册标签在某个交易日上的冻结观测：``value`` 为 null 即缺原料，谓词判 unknown。"""

    label: str
    as_of: str
    value: Any
    entity_id: str = ""
    recorded_at: str | None = None
    label_version: str | None = None
    source_ref: str | None = None

    def dedupe_key(self) -> tuple[Any, ...]:
        return (self.label, self.entity_id, self.as_of, self.value, self.recorded_at, self.label_version, self.source_ref)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "entity_id": self.entity_id,
            "as_of": self.as_of,
            "value": self.value,
            "recorded_at": self.recorded_at,
            "label_version": self.label_version,
            "source_ref": self.source_ref,
        }


_OBSERVATION_KEYS = ("schema_version", "label", "entity_id", "as_of", "value", "recorded_at", "label_version", "source_ref")


def parse_observation(data: Any, *, owner_user_id: str, where: str) -> ConditionObservation:
    if isinstance(data, ConditionObservation):
        return data
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _OBSERVATION_KEYS, where)
    _schema(d, OBSERVATION_SCHEMA_VERSION, where, required=False)
    if "value" not in d:
        raise MaintenanceContractError("missing_field", f"{where}.value", "观测必须显式带 value（缺原料请给 null）")
    recorded_at = d.get("recorded_at")
    source_ref = _opt_str(d, "source_ref", where)
    return ConditionObservation(
        label=_req_str(d, "label", where),
        as_of=validate_date(d.get("as_of"), f"{where}.as_of"),
        value=_scalar(d.get("value"), f"{where}.value"),
        entity_id=_opt_str(d, "entity_id", where) or "",
        recorded_at=validate_stamp(recorded_at, f"{where}.recorded_at") if recorded_at is not None else None,
        label_version=_opt_str(d, "label_version", where),
        source_ref=validate_ref(source_ref, owner_user_id=owner_user_id, where=f"{where}.source_ref") if source_ref else None,
    )


@dataclass(frozen=True)
class MaintenancePolicy:
    """判定策略：只有能改变输出的旋钮，且全部进 input_digest。"""

    evaluate_conditions: bool = True
    emit_unchanged: bool = False
    allowed_object_namespaces: tuple[str, ...] = DEFAULT_OBJECT_NAMESPACES
    schema_version: str = POLICY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evaluate_conditions": self.evaluate_conditions,
            "emit_unchanged": self.emit_unchanged,
            "allowed_object_namespaces": list(self.allowed_object_namespaces),
        }


_POLICY_KEYS = ("schema_version", "evaluate_conditions", "emit_unchanged", "allowed_object_namespaces")


def parse_policy(data: Any, *, where: str = "policy") -> MaintenancePolicy:
    if data is None:
        return MaintenancePolicy()
    if isinstance(data, MaintenancePolicy):
        return data
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _POLICY_KEYS, where)
    _schema(d, POLICY_SCHEMA_VERSION, where, required=True)
    namespaces_raw = d.get("allowed_object_namespaces", list(DEFAULT_OBJECT_NAMESPACES))
    if not isinstance(namespaces_raw, list) or not namespaces_raw or not all(isinstance(x, str) and x.strip() for x in namespaces_raw):
        raise MaintenanceContractError("invalid_type", f"{where}.allowed_object_namespaces", "需要非空字符串列表")
    return MaintenancePolicy(
        evaluate_conditions=_opt_bool(d, "evaluate_conditions", where, True),
        emit_unchanged=_opt_bool(d, "emit_unchanged", where, False),
        allowed_object_namespaces=tuple(sorted({x.strip() for x in namespaces_raw})),
    )


# --------------------------------------------------------------------------- #
# 输出对象
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Gap:
    """一处说不清的地方。``retryable`` 回答「再扫一次可能补上吗」，``checked_at`` 是逻辑检查时刻（知识截止日）。"""

    reason: str
    ref: str | None
    checked_at: str
    retryable: bool
    detail: str = ""
    binding_id: str | None = None
    condition_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "ref": self.ref,
            "checked_at": self.checked_at,
            "retryable": self.retryable,
            "detail": self.detail,
            "binding_id": self.binding_id,
            "condition_ref": self.condition_ref,
        }


_GAP_KEYS = ("reason", "ref", "checked_at", "retryable", "detail", "binding_id", "condition_ref")


def parse_gap(data: Any, *, where: str) -> Gap:
    if isinstance(data, Gap):
        return data
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _GAP_KEYS, where)
    retryable = d.get("retryable")
    if not isinstance(retryable, bool):
        raise MaintenanceContractError("invalid_type", f"{where}.retryable", "需要 true / false")
    return Gap(
        reason=_req_str(d, "reason", where),
        ref=_opt_str(d, "ref", where),
        checked_at=validate_stamp(d.get("checked_at"), f"{where}.checked_at"),
        retryable=retryable,
        detail=str(d.get("detail") or ""),
        binding_id=_opt_str(d, "binding_id", where),
        condition_ref=_opt_str(d, "condition_ref", where),
    )


@dataclass(frozen=True)
class ItemManagement:
    """管理侧元数据：随动作变，不进 item_version。``applied_commands`` 让重复 command_id 可判 replayed。"""

    applied_commands: tuple[dict[str, Any], ...] = ()
    snooze_until: str | None = None
    claimed_at: str | None = None
    closed_at: str | None = None
    closure: dict[str, Any] | None = None
    rejudgment: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied_commands": [dict(c) for c in self.applied_commands],
            "snooze_until": self.snooze_until,
            "claimed_at": self.claimed_at,
            "closed_at": self.closed_at,
            "closure": dict(self.closure) if self.closure else None,
            "rejudgment": dict(self.rejudgment) if self.rejudgment else None,
        }


_MANAGEMENT_KEYS = ("applied_commands", "snooze_until", "claimed_at", "closed_at", "closure", "rejudgment")


def parse_management(data: Any, *, where: str) -> ItemManagement:
    if data is None:
        return ItemManagement()
    if isinstance(data, ItemManagement):
        return data
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _MANAGEMENT_KEYS, where)
    applied_raw = d.get("applied_commands") or []
    if not isinstance(applied_raw, list) or not all(isinstance(x, Mapping) for x in applied_raw):
        raise MaintenanceContractError("invalid_type", f"{where}.applied_commands", "需要对象列表")
    for key in ("closure", "rejudgment"):
        if d.get(key) is not None and not isinstance(d.get(key), Mapping):
            raise MaintenanceContractError("invalid_type", f"{where}.{key}", "需要对象或 null")
    snooze_until = d.get("snooze_until")
    claimed_at = d.get("claimed_at")
    closed_at = d.get("closed_at")
    return ItemManagement(
        applied_commands=tuple(dict(x) for x in applied_raw),
        snooze_until=validate_stamp(snooze_until, f"{where}.snooze_until") if snooze_until is not None else None,
        claimed_at=validate_stamp(claimed_at, f"{where}.claimed_at") if claimed_at is not None else None,
        closed_at=validate_stamp(closed_at, f"{where}.closed_at") if closed_at is not None else None,
        closure=dict(d["closure"]) if d.get("closure") else None,
        rejudgment=dict(d["rejudgment"]) if d.get("rejudgment") else None,
    )


@dataclass(frozen=True)
class MaintenanceItem:
    """一条维护项（spec 01 §3 ``MaintenanceItem``）。

    ``id`` 由 ``dedup_key`` 派生（不含扫描时间）；``item_version`` 是证据 / 绑定 / 条件快照哈希，
    不含管理状态；``management_revision`` 随每一个被接受的管理动作 +1。
    ``epistemic_state`` 只描述变化证据，不描述原判断对错。
    """

    id: str
    item_version: str
    owner_user_id: str
    object_ref: ObjectRef
    before: tuple[EvidenceVersion, ...]
    current: tuple[EvidenceVersion, ...]
    change_type: str
    reason_code: str
    epistemic_state: str
    condition_result: str | None
    as_of: str
    knowledge_cutoff: str
    pit_grade: str
    gaps: tuple[Gap, ...]
    action: str
    status: str
    dedup_key: str
    binding_id: str
    binding_version: int
    dependency_ref: str | None = None
    condition_ref: str | None = None
    condition_role: str | None = None
    condition_evaluation: dict[str, Any] | None = None
    supersedes_item_id: str | None = None
    # 这个状态最早在哪个知识日可知（替代链里的项各有自己的起点）；knowledge_cutoff 是报告的截止日。
    first_known_day: str | None = None
    management_revision: int = 0
    management: ItemManagement = field(default_factory=ItemManagement)
    schema_version: str = SCHEMA_VERSION

    @property
    def is_open(self) -> bool:
        """待办口径：还在手上（open / claimed / rejudgment_requested）且有建议动作。"""
        return self.status in OPEN_STATUSES and self.action != "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "item_version": self.item_version,
            "owner_user_id": self.owner_user_id,
            "object_ref": self.object_ref.to_dict(),
            "before": [v.to_dict() for v in self.before],
            "current": [v.to_dict() for v in self.current],
            "change_type": self.change_type,
            "reason_code": self.reason_code,
            "epistemic_state": self.epistemic_state,
            "condition_result": self.condition_result,
            "as_of": self.as_of,
            "knowledge_cutoff": self.knowledge_cutoff,
            "pit_grade": self.pit_grade,
            "gaps": [g.to_dict() for g in self.gaps],
            "action": self.action,
            "status": self.status,
            "dedup_key": self.dedup_key,
            "binding_id": self.binding_id,
            "binding_version": self.binding_version,
            "dependency_ref": self.dependency_ref,
            "condition_ref": self.condition_ref,
            "condition_role": self.condition_role,
            "condition_evaluation": self.condition_evaluation,
            "supersedes_item_id": self.supersedes_item_id,
            "first_known_day": self.first_known_day,
            "management_revision": self.management_revision,
            "management": self.management.to_dict(),
        }


_ITEM_KEYS = (
    "schema_version",
    "id",
    "item_version",
    "owner_user_id",
    "object_ref",
    "before",
    "current",
    "change_type",
    "reason_code",
    "epistemic_state",
    "condition_result",
    "as_of",
    "knowledge_cutoff",
    "pit_grade",
    "gaps",
    "action",
    "status",
    "dedup_key",
    "binding_id",
    "binding_version",
    "dependency_ref",
    "condition_ref",
    "condition_role",
    "condition_evaluation",
    "supersedes_item_id",
    "first_known_day",
    "management_revision",
    "management",
)


def parse_item(data: Any, *, owner_user_id: str, where: str) -> MaintenanceItem:
    if isinstance(data, MaintenanceItem):
        if data.owner_user_id != owner_user_id:
            raise MaintenanceContractError("owner_mismatch", f"{where}.owner_user_id", "维护项不属于本用户")
        return data
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _ITEM_KEYS, where)
    _schema(d, SCHEMA_VERSION, where, required=True)
    owner = validate_owner(d.get("owner_user_id"), f"{where}.owner_user_id")
    if owner != owner_user_id:
        raise MaintenanceContractError("owner_mismatch", f"{where}.owner_user_id", "维护项不属于本用户")
    for key in ("before", "current", "gaps"):
        if not isinstance(d.get(key), list):
            raise MaintenanceContractError("invalid_type", f"{where}.{key}", "需要列表")
    condition_result = d.get("condition_result")
    if condition_result is not None:
        _enum(condition_result, CONDITION_RESULTS, f"{where}.condition_result")
    evaluation = d.get("condition_evaluation")
    if evaluation is not None and not isinstance(evaluation, Mapping):
        raise MaintenanceContractError("invalid_type", f"{where}.condition_evaluation", "需要对象或 null")
    condition_role = _opt_str(d, "condition_role", where)
    if condition_role is not None:
        _enum(condition_role, CONDITION_ROLES, f"{where}.condition_role")
    return MaintenanceItem(
        id=_req_str(d, "id", where),
        item_version=_req_str(d, "item_version", where),
        owner_user_id=owner,
        object_ref=parse_object_ref(d.get("object_ref"), owner_user_id=owner_user_id, where=f"{where}.object_ref"),
        before=tuple(parse_evidence_version(v, owner_user_id=owner_user_id, where=f"{where}.before[{i}]", allow_placeholder=True) for i, v in enumerate(d["before"])),
        current=tuple(parse_evidence_version(v, owner_user_id=owner_user_id, where=f"{where}.current[{i}]") for i, v in enumerate(d["current"])),
        change_type=_enum(d.get("change_type"), CHANGE_TYPES, f"{where}.change_type"),
        reason_code=_enum(d.get("reason_code"), REASON_CODES, f"{where}.reason_code"),
        epistemic_state=_enum(d.get("epistemic_state"), EPISTEMIC_STATES, f"{where}.epistemic_state"),
        condition_result=condition_result,
        as_of=validate_date(d.get("as_of"), f"{where}.as_of"),
        knowledge_cutoff=validate_date(d.get("knowledge_cutoff"), f"{where}.knowledge_cutoff"),
        pit_grade=_enum(d.get("pit_grade"), PIT_GRADES, f"{where}.pit_grade"),
        gaps=tuple(parse_gap(g, where=f"{where}.gaps[{i}]") for i, g in enumerate(d["gaps"])),
        action=_enum(d.get("action"), ACTIONS, f"{where}.action"),
        status=_enum(d.get("status"), ITEM_STATUSES, f"{where}.status"),
        dedup_key=_req_str(d, "dedup_key", where),
        binding_id=_req_str(d, "binding_id", where),
        binding_version=_req_int(d, "binding_version", where, minimum=1),
        dependency_ref=_opt_str(d, "dependency_ref", where),
        condition_ref=_opt_str(d, "condition_ref", where),
        condition_role=condition_role,
        condition_evaluation=dict(evaluation) if evaluation is not None else None,
        supersedes_item_id=_opt_str(d, "supersedes_item_id", where),
        first_known_day=validate_date(d["first_known_day"], f"{where}.first_known_day") if d.get("first_known_day") is not None else None,
        management_revision=_req_int(d, "management_revision", where, minimum=0),
        management=parse_management(d.get("management"), where=f"{where}.management"),
    )


@dataclass(frozen=True)
class MaintenanceReport:
    """维护报告（spec 01 §3 ``MaintenanceReport``）。``generated_at`` 不进 id / 摘要。"""

    id: str
    owner_user_id: str
    as_of: str
    knowledge_cutoff: str
    input_digest: str
    generated_at: str
    pit_grade: str
    hindsight: bool
    gaps: tuple[Gap, ...]
    items: tuple[MaintenanceItem, ...]
    counts: dict[str, int]
    management_log: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def item(self, item_id: str) -> MaintenanceItem | None:
        return next((it for it in self.items if it.id == item_id), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "owner_user_id": self.owner_user_id,
            "as_of": self.as_of,
            "knowledge_cutoff": self.knowledge_cutoff,
            "input_digest": self.input_digest,
            "generated_at": self.generated_at,
            "pit_grade": self.pit_grade,
            "hindsight": self.hindsight,
            "gaps": [g.to_dict() for g in self.gaps],
            "items": [it.to_dict() for it in self.items],
            "counts": dict(self.counts),
            "management_log": dict(self.management_log),
        }


_REPORT_KEYS = (
    "schema_version",
    "id",
    "owner_user_id",
    "as_of",
    "knowledge_cutoff",
    "input_digest",
    "generated_at",
    "pit_grade",
    "hindsight",
    "gaps",
    "items",
    "counts",
    "management_log",
)
COUNT_KEYS = ("objects_seen", "objects_bound", "objects_unverifiable", "dependencies_checked", "items_open")


def parse_report(data: Any, *, where: str = "report") -> MaintenanceReport:
    if isinstance(data, MaintenanceReport):
        return data
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _REPORT_KEYS, where)
    _schema(d, SCHEMA_VERSION, where, required=True)
    owner = validate_owner(d.get("owner_user_id"), f"{where}.owner_user_id")
    for key in ("gaps", "items"):
        if not isinstance(d.get(key), list):
            raise MaintenanceContractError("invalid_type", f"{where}.{key}", "需要列表")
    counts_raw = d.get("counts")
    if not isinstance(counts_raw, Mapping) or set(counts_raw) != set(COUNT_KEYS):
        raise MaintenanceContractError("invalid_type", f"{where}.counts", f"counts 需要且只需要 {list(COUNT_KEYS)}")
    counts = {k: _req_int(counts_raw, k, f"{where}.counts") for k in COUNT_KEYS}
    hindsight = d.get("hindsight")
    if not isinstance(hindsight, bool):
        raise MaintenanceContractError("invalid_type", f"{where}.hindsight", "需要 true / false")
    log_raw = d.get("management_log") or {}
    if not isinstance(log_raw, Mapping):
        raise MaintenanceContractError("invalid_type", f"{where}.management_log", "需要对象")
    return MaintenanceReport(
        id=_req_str(d, "id", where),
        owner_user_id=owner,
        as_of=validate_date(d.get("as_of"), f"{where}.as_of"),
        knowledge_cutoff=validate_date(d.get("knowledge_cutoff"), f"{where}.knowledge_cutoff"),
        input_digest=_req_str(d, "input_digest", where),
        generated_at=validate_stamp(d.get("generated_at"), f"{where}.generated_at"),
        pit_grade=_enum(d.get("pit_grade"), PIT_GRADES, f"{where}.pit_grade"),
        hindsight=hindsight,
        gaps=tuple(parse_gap(g, where=f"{where}.gaps[{i}]") for i, g in enumerate(d["gaps"])),
        items=tuple(parse_item(it, owner_user_id=owner, where=f"{where}.items[{i}]") for i, it in enumerate(d["items"])),
        counts=counts,
        management_log=dict(log_raw),
    )


# --------------------------------------------------------------------------- #
# 管理动作：命令 / 事件 / 结果
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ActionCommand:
    """用户发出的一条管理命令（spec 01 §5）。``payload_digest`` 不含 command_id 与 acted_at：
    同一 command_id 重发同载荷 = replayed，换载荷 = conflict。"""

    command_id: str
    item_id: str
    owner_user_id: str
    expected_item_version: str
    expected_management_revision: int
    action: str
    acted_at: str
    snooze_until: str | None = None
    reviewed_source_versions: tuple[tuple[str, str], ...] | None = None
    schema_version: str = COMMAND_SCHEMA_VERSION

    def payload(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "action": self.action,
            "expected_item_version": self.expected_item_version,
            "expected_management_revision": self.expected_management_revision,
            "snooze_until": self.snooze_until,
            "reviewed_source_versions": [list(x) for x in self.reviewed_source_versions] if self.reviewed_source_versions is not None else None,
        }

    def payload_digest(self) -> str:
        return sha256_hex(self.payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "command_id": self.command_id,
            "item_id": self.item_id,
            "owner_user_id": self.owner_user_id,
            "expected_item_version": self.expected_item_version,
            "expected_management_revision": self.expected_management_revision,
            "action": self.action,
            "acted_at": self.acted_at,
            "snooze_until": self.snooze_until,
            "reviewed_source_versions": [list(x) for x in self.reviewed_source_versions] if self.reviewed_source_versions is not None else None,
        }


_COMMAND_KEYS = (
    "schema_version",
    "command_id",
    "item_id",
    "owner_user_id",
    "expected_item_version",
    "expected_management_revision",
    "action",
    "acted_at",
    "snooze_until",
    "reviewed_source_versions",
)


def parse_command(data: Any, *, owner_user_id: str, where: str = "command") -> ActionCommand:
    if isinstance(data, ActionCommand):
        return data
    d = _as_mapping(data, where)
    _reject_unknown_keys(d, _COMMAND_KEYS, where)
    _schema(d, COMMAND_SCHEMA_VERSION, where, required=False)
    snooze_until = d.get("snooze_until")
    reviewed_raw = d.get("reviewed_source_versions")
    reviewed: tuple[tuple[str, str], ...] | None = None
    if reviewed_raw is not None:
        if not isinstance(reviewed_raw, list):
            raise MaintenanceContractError("invalid_type", f"{where}.reviewed_source_versions", "需要 [{ref, source_hash}] 列表")
        pairs: list[tuple[str, str]] = []
        for i, entry in enumerate(reviewed_raw):
            e = _as_mapping(entry, f"{where}.reviewed_source_versions[{i}]")
            _reject_unknown_keys(e, ("ref", "source_hash"), f"{where}.reviewed_source_versions[{i}]")
            pairs.append(
                (
                    validate_ref(e.get("ref"), owner_user_id=owner_user_id, where=f"{where}.reviewed_source_versions[{i}].ref"),
                    _req_str(e, "source_hash", f"{where}.reviewed_source_versions[{i}]"),
                )
            )
        reviewed = tuple(sorted(set(pairs)))
    return ActionCommand(
        command_id=_req_str(d, "command_id", where),
        item_id=_req_str(d, "item_id", where),
        owner_user_id=validate_owner(d.get("owner_user_id"), f"{where}.owner_user_id"),
        expected_item_version=_req_str(d, "expected_item_version", where),
        expected_management_revision=_req_int(d, "expected_management_revision", where, minimum=0),
        action=_enum(d.get("action"), COMMANDS, f"{where}.action"),
        acted_at=validate_stamp(d.get("acted_at"), f"{where}.acted_at"),
        snooze_until=validate_stamp(snooze_until, f"{where}.snooze_until") if snooze_until is not None else None,
        reviewed_source_versions=reviewed,
    )


@dataclass(frozen=True)
class ManagementEvent:
    """追加到 06 台账的管理事件（本包只生成、只归约，不写）。"""

    event_id: str
    item_id: str
    owner_user_id: str
    kind: str
    at: str
    expected_management_revision: int
    command_id: str | None = None
    payload_digest: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: str = EVENT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "item_id": self.item_id,
            "owner_user_id": self.owner_user_id,
            "kind": self.kind,
            "at": self.at,
            "expected_management_revision": self.expected_management_revision,
            "command_id": self.command_id,
            "payload_digest": self.payload_digest,
            "payload": dict(self.payload),
        }


_EVENT_KEYS = (
    "schema_version",
    "event_id",
    "item_id",
    "owner_user_id",
    "kind",
    "at",
    "expected_management_revision",
    "command_id",
    "payload_digest",
    "payload",
)


def parse_event(data: Any, *, owner_user_id: str, where: str = "event") -> ManagementEvent:
    if isinstance(data, ManagementEvent):
        event = data
    else:
        d = _as_mapping(data, where)
        _reject_unknown_keys(d, _EVENT_KEYS, where)
        _schema(d, EVENT_SCHEMA_VERSION, where, required=True)
        payload_raw = d.get("payload") or {}
        if not isinstance(payload_raw, Mapping):
            raise MaintenanceContractError("invalid_type", f"{where}.payload", "需要对象")
        event = ManagementEvent(
            event_id=_req_str(d, "event_id", where),
            item_id=_req_str(d, "item_id", where),
            owner_user_id=validate_owner(d.get("owner_user_id"), f"{where}.owner_user_id"),
            kind=_enum(d.get("kind"), EVENT_KINDS, f"{where}.kind"),
            at=validate_stamp(d.get("at"), f"{where}.at"),
            expected_management_revision=_req_int(d, "expected_management_revision", where, minimum=0),
            command_id=_opt_str(d, "command_id", where),
            payload_digest=_opt_str(d, "payload_digest", where),
            payload=dict(payload_raw),
        )
    if event.owner_user_id != owner_user_id:
        raise MaintenanceContractError("owner_mismatch", f"{where}.owner_user_id", "事件不属于本用户")
    return event


@dataclass(frozen=True)
class ActionResult:
    """``validate_action`` 的结论：拟追加事件由 06 落盘，本包不写。"""

    status: str
    reason_code: str
    item_id: str | None
    command_id: str | None
    event: ManagementEvent | None
    resulting_status: str | None
    resulting_management_revision: int | None
    detail: str = ""
    schema_version: str = ACTION_RESULT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "reason_code": self.reason_code,
            "item_id": self.item_id,
            "command_id": self.command_id,
            "event": self.event.to_dict() if self.event else None,
            "resulting_status": self.resulting_status,
            "resulting_management_revision": self.resulting_management_revision,
            "detail": self.detail,
        }


__all__ = [
    "ACTIONS",
    "ACTION_RESULT_SCHEMA_VERSION",
    "ACTION_RESULT_STATUSES",
    "BINDING_ORIGINS",
    "BINDING_SCHEMA_VERSION",
    "CHANGE_TYPES",
    "COMMANDS",
    "COMMAND_EVENT_KIND",
    "COMMAND_SCHEMA_VERSION",
    "CONDITION_RESULTS",
    "CONDITION_ROLES",
    "COUNT_KEYS",
    "DEFAULT_OBJECT_NAMESPACES",
    "DERIVATIONS",
    "EPISTEMIC_STATES",
    "EVENT_ID_PREFIX",
    "EVENT_KINDS",
    "EVENT_SCHEMA_VERSION",
    "EVIDENCE_SCHEMA_VERSION",
    "ITEM_ID_PREFIX",
    "ITEM_STATUSES",
    "OBJECT_KINDS",
    "OBSERVATION_SCHEMA_VERSION",
    "OPEN_STATUSES",
    "PIT_GRADES",
    "POLICY_SCHEMA_VERSION",
    "REASON_CODES",
    "REPORT_ID_PREFIX",
    "SCHEMA_VERSION",
    "ActionCommand",
    "ActionResult",
    "BindingCondition",
    "ConditionObservation",
    "DependencyBinding",
    "EvidenceVersion",
    "Gap",
    "ItemManagement",
    "MaintenanceContractError",
    "MaintenanceItem",
    "MaintenancePolicy",
    "MaintenanceReport",
    "ManagementEvent",
    "ObjectRef",
    "canonical_json",
    "day_of",
    "parse_binding",
    "parse_command",
    "parse_condition",
    "parse_event",
    "parse_evidence_version",
    "parse_gap",
    "parse_item",
    "parse_management",
    "parse_object_ref",
    "parse_observation",
    "parse_policy",
    "parse_report",
    "sha256_hex",
    "short_hash",
    "validate_date",
    "validate_owner",
    "validate_ref",
    "validate_stamp",
    "weakest_pit",
]

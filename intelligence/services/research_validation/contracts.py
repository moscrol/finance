"""研究验证合同（spec 03 §4）：对象 schema、语义身份、纯校验与 gap 码。

本模块**不触盘、不读时钟、不查库**。它回答三个问题：

1. 一个对象「是什么」——``StudyProtocol`` / ``ProbabilityForecast`` / ``OutcomeObservation`` /
   ``MethodValidationReceipt`` / ``ExposureReceipt`` 各有哪些字段、取值边界；
2. 一个对象「是谁」——语义 SHA-256 作 id：**记录时间**（``created_at`` / ``frozen_at`` /
   ``registered_at`` / ``observed_at`` / ``generated_at`` / ``accessed_at``）不进身份，
   **事件时间**（``as_of`` / ``forecast_at`` / ``outcome_due`` / ``knowledge_cutoff``）进身份。
   同语义重试得到同 id → 幂等返回原件；改义得到新 id → 新对象；
3. 哪些输入必须拒收——概率 bool / NaN / 越界、非有限数、非法日期、越权 owner。

时间口径：时戳一律 tz-aware，落盘转 UTC；市场日按 Asia/Shanghai 取；收盘 15:00。
JSON 走 ``canonical_bytes``（``allow_nan=False``），非有限数在序列化这一层就炸，
不会以 ``NaN`` 字面量写进任何原件。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from intelligence.services.checkpoints import DEFAULT_CALIBRATION_MIN_N
from intelligence.services.methodology_backtest.rules import (
    DEFAULT_MIN_N,
    LABEL_KINDS,
    MAX_HORIZON,
    METRICS,
    SUCCESS_OPS,
    validate_rule,
)
from intelligence.services.methodology_backtest.stats import (
    DEFAULT_BLOCK_BOOT,
    DEFAULT_BLOCK_SEED,
    DEFAULT_MIN_BLOCKS,
)
from intelligence.services.river_projection import HASH_PREFIX as RIVER_PROJECTION_HASH_PREFIX

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
SCHEMA_STUDY = "research-study/v1"
SCHEMA_FORECAST = "probability-forecast/v1"
SCHEMA_OBSERVATION = "outcome-observation/v1"
SCHEMA_RECEIPT = "method-validation-receipt/v1"
SCHEMA_EXPOSURE = "exposure-receipt/v1"

SHANGHAI = ZoneInfo("Asia/Shanghai")
MARKET_CLOSE = time(15, 0)

VISIBILITY_PRIVATE = "private"
MODES = ("forward", "historical_rule", "historical_llm")
ORIGINS = ("human_manual", "deterministic", "historical_llm")
STUDY_STATUSES = ("draft", "frozen", "closed", "invalid")
OBSERVATION_STATUSES = ("settled", "pending", "missing", "invalid")
EMPIRICAL_STATUSES = (
    "pending",
    "descriptive",
    "insufficient",
    "not_distinguishable",
    "supported",
    "refuted",
    "invalid",
)
CLAIM_KIND_PRIMARY = "paired_date_win_rate"
CLAIM_KINDS = (CLAIM_KIND_PRIMARY, "mean_brier_difference_descriptive")
ARM_ROLES = ("base", "full", "minus_track", "candidate", "human")
PIT_GRADES = ("strict", "trade_date_only", "unverified")
EXPOSURE_STAGES = ("evaluate", "read_receipt", "practice_reveal", "raw_access", "external")
BASELINE_KINDS = ("discovery_event_days",)
NULL_P0 = 0.5  # 对称胜负的零假设，不是市场上涨率
DEFAULT_ENTITY_TYPE = "sector"  # 首版限板块

GAP_CODES = (
    "future_not_due",
    "outcome_missing",
    "baseline_unavailable",
    "arm_missing",
    "unverified_pit",
    "holdout_exposed",
    "version_mismatch",
    "ties_test_not_defined",
    "insufficient_n",
    "insufficient_blocks",
    "isolation_unverified",
    "exposure_unknown",
    "descriptive_only",
    "no_pairs",
)

_ID_RE = re.compile(r"^[0-9a-f]{64}$")
# 河的上下文投影哈希形状（river_projection.HASH_PREFIX + sha256[:16]）；常量从源头 import，不手抄。
_RIVER_PROJECTION_HASH_RE = re.compile(r"^" + re.escape(RIVER_PROJECTION_HASH_PREFIX) + r"[0-9a-f]{16}$")
_ARM_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_OWNER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")

STUDY_RECORD_TIME_FIELDS = frozenset({"created_at", "frozen_at"})
STUDY_STATE_FIELDS = frozenset({"id", "study_id", "status", "exposure_receipt_refs"})
FORECAST_RECORD_TIME_FIELDS = frozenset({"registered_at"})
OBSERVATION_RECORD_TIME_FIELDS = frozenset({"observed_at"})
RECEIPT_RECORD_TIME_FIELDS = frozenset({"generated_at", "as_of_now"})
EXPOSURE_RECORD_TIME_FIELDS = frozenset({"accessed_at"})


class ContractError(ValueError):
    """输入不符合合同：拒收，不落盘。"""


class ConflictError(ContractError):
    """同唯一键已有**异义**原件：不覆盖、不合并、不静默返回。"""


class OwnerMismatch(ContractError):
    """owner 与对象归属不一致：越权访问一律拒绝。"""


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def canonical_bytes(value: Any) -> bytes:
    """排序键、无空白、禁 NaN/Infinity 的 JSON 字节；同语义永远同字节。"""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def is_probability(value: Any) -> bool:
    """[0, 1] 内的有限、非 bool 数字。``True`` / ``NaN`` / ``1.2`` 都不是概率。"""
    return is_finite_number(value) and 0.0 <= float(value) <= 1.0


def iso_date(value: Any, *, field_name: str = "date") -> str:
    if not isinstance(value, str):
        raise ContractError(f"{field_name} 必须是 YYYY-MM-DD 字符串，得到 {type(value).__name__}")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError(f"{field_name} 不是合法日期：{value!r}") from exc
    if parsed.isoformat() != value:
        raise ContractError(f"{field_name} 必须是规范 YYYY-MM-DD：{value!r}")
    return value


def parse_ts(value: Any, *, field_name: str = "timestamp") -> datetime:
    """解析 tz-aware 时戳；naive 一律拒绝（不猜时区）。"""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractError(f"{field_name} 不是合法 ISO 时戳：{value!r}") from exc
    else:
        raise ContractError(f"{field_name} 必须是 ISO 时戳字符串，得到 {type(value).__name__}")
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise ContractError(f"{field_name} 必须带时区：{value!r}")
    return parsed


def utc_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds")


def ensure_aware_now(now: Any) -> datetime:
    if not isinstance(now, datetime):
        raise ContractError("now 必须是 datetime（由可信时钟提供，客户端不得自填）")
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ContractError("now 必须是 tz-aware datetime")
    return now


def market_close(day: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), MARKET_CLOSE, tzinfo=SHANGHAI)


def market_day(ts: datetime) -> str:
    return ts.astimezone(SHANGHAI).date().isoformat()


def validate_owner(owner: Any) -> str:
    if not isinstance(owner, str) or not _OWNER_RE.match(owner):
        raise ContractError(f"非法 owner_user_id：{owner!r}")
    return owner


def validate_content_id(value: Any, *, field_name: str = "id") -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ContractError(f"{field_name} 必须是 64 位十六进制 SHA-256：{value!r}")
    return value


def validate_projection_hash(value: Any) -> str:
    """预测绑定的投影哈希。两种合法形状：

    - 河的上下文投影 ``river_projection.ContextProjection.projection_hash``（``cp:`` + 16 位十六进制，
      §4.5：每条 agent 产物记 projection_hash，回溯时能重建「那天实际看到的那一小片」）；
    - 规则臂的字段投影 ``digest(projection)``（64 位 SHA-256，eval runner 产出）。
    其余一律拒收——散文、文件名、截断串都不是投影身份。
    """
    if isinstance(value, str) and _ID_RE.match(value):
        return value
    if isinstance(value, str) and _RIVER_PROJECTION_HASH_RE.match(value):
        return value
    raise ContractError(
        f"projection_hash 必须是 64 位 SHA-256 或河投影哈希（{RIVER_PROJECTION_HASH_PREFIX}+16 位十六进制）：{value!r}"
    )


def validate_token(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.match(value):
        raise ContractError(f"{field_name} 必须是安全短标识：{value!r}")
    return value


def validate_operation_id(value: Any) -> str:
    if not isinstance(value, str) or not _OPERATION_ID_RE.match(value):
        raise ContractError(f"operation_id 必须是 8..128 位安全标识：{value!r}")
    return value


def _str_map(value: Any, *, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContractError(f"{field_name} 必须是 {{str: str}} 对象")
    out: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str) or not key or not item:
            raise ContractError(f"{field_name} 的键与值都必须是非空字符串：{key!r}={item!r}")
        out[key] = item
    return dict(sorted(out.items()))


# --------------------------------------------------------------------------- #
# gap
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Gap:
    """缺口：说清缺什么、缺在谁身上、能不能重试、何时再查。UNKNOWN 不得变成零 / 失败 / 已解除。"""

    code: str
    object_refs: tuple[str, ...] = ()
    retryable: bool = False
    next_check_at: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "object_refs": list(self.object_refs),
            "retryable": self.retryable,
        }
        if self.next_check_at is not None:
            out["next_check_at"] = self.next_check_at
        if self.detail is not None:
            out["detail"] = self.detail
        return out


def make_gap(
    code: str,
    refs: Iterable[str] = (),
    *,
    retryable: bool = False,
    next_check_at: str | None = None,
    detail: str | None = None,
) -> Gap:
    if code not in GAP_CODES:
        raise ContractError(f"未知 gap 码 {code!r}")
    return Gap(
        code=code,
        object_refs=tuple(sorted(set(str(r) for r in refs))),
        retryable=bool(retryable),
        next_check_at=next_check_at,
        detail=detail,
    )


# --------------------------------------------------------------------------- #
# 冻结交易日历
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Calendar:
    """冻结的交易日序列。到期日 = 事件日之后第 h 个交易日；出界即报错，不外推。"""

    dates: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.dates:
            raise ContractError("calendar 不能为空")
        for d in self.dates:
            iso_date(d, field_name="calendar")
        if list(self.dates) != sorted(set(self.dates)):
            raise ContractError("calendar 必须严格递增且无重复")

    @classmethod
    def from_any(cls, value: Any) -> "Calendar":
        if not isinstance(value, (list, tuple)):
            raise ContractError("calendar 必须是日期列表")
        return cls(tuple(str(d) for d in value))

    @property
    def hash(self) -> str:
        return digest(list(self.dates))

    def index(self, day: str) -> int:
        try:
            return self.dates.index(day)
        except ValueError as exc:
            raise ContractError(f"{day} 不在冻结日历内") from exc

    def contains(self, day: str) -> bool:
        return day in self.dates

    def shift(self, day: str, n: int) -> str:
        idx = self.index(day) + int(n)
        if idx < 0 or idx >= len(self.dates):
            raise ContractError(f"日历不足：{day} 之后 {n} 个交易日超出冻结日历末端 {self.dates[-1]}")
        return self.dates[idx]

    def between(self, start: str, end: str) -> tuple[str, ...]:
        return tuple(d for d in self.dates if start <= d <= end)


# --------------------------------------------------------------------------- #
# outcome 谓词（首版限 history_outcomes.fwd_return 布尔谓词）
# --------------------------------------------------------------------------- #
def validate_outcome_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, Mapping):
        raise ContractError("outcome_spec 必须是对象 {metric, horizon, op, value}")
    if set(spec) != {"metric", "horizon", "op", "value"}:
        raise ContractError("outcome_spec 只允许 metric/horizon/op/value 四个键")
    metric = spec["metric"]
    if metric not in METRICS:
        raise ContractError(f"outcome_spec.metric 必须在 {METRICS}，得到 {metric!r}")
    horizon = spec["horizon"]
    if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= MAX_HORIZON:
        raise ContractError(f"outcome_spec.horizon 必须是 1..{MAX_HORIZON} 的整数，得到 {horizon!r}")
    op = spec["op"]
    if op not in SUCCESS_OPS:
        raise ContractError(f"outcome_spec.op 必须在 {SUCCESS_OPS}，得到 {op!r}")
    value = spec["value"]
    if not is_finite_number(value):
        raise ContractError(f"outcome_spec.value 必须是有限数，得到 {value!r}")
    return {"metric": metric, "horizon": int(horizon), "op": op, "value": float(value)}


def outcome_predicate(spec: Mapping[str, Any], metric_value: Any) -> bool | None:
    """metric 值 → 0/1；非有限数返回 None（未知不转 false）。"""
    if not is_finite_number(metric_value):
        return None
    x = float(metric_value)
    v = float(spec["value"])
    op = spec["op"]
    if op == ">":
        return x > v
    if op == ">=":
        return x >= v
    if op == "<":
        return x < v
    if op == "<=":
        return x <= v
    raise ContractError(f"未知 outcome op {op!r}")


# --------------------------------------------------------------------------- #
# 身份派生
# --------------------------------------------------------------------------- #
def derive_case_id(
    *,
    entity_type: str,
    entity_id: str,
    as_of: str,
    event_spec_hash: str,
    outcome_due: str,
    universe_hash: str,
) -> str:
    """case 身份：各臂共享，不含预测结果。"""
    return digest(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "as_of": as_of,
            "event_spec_hash": event_spec_hash,
            "outcome_due": outcome_due,
            "universe_hash": universe_hash,
        }
    )


def outcome_identity(
    *, entity_type: str, entity_id: str, as_of: str, outcome_due: str, horizon: int
) -> dict[str, Any]:
    """底层结果身份：真实实体 + 结果区间。改 case 名、改谓词阈值、换 study 都不改变它。"""
    body = {
        "entity_type": str(entity_type),
        "entity_id": str(entity_id),
        "as_of": iso_date(as_of, field_name="as_of"),
        "outcome_due": iso_date(outcome_due, field_name="outcome_due"),
        "horizon": int(horizon),
    }
    return {**body, "identity": digest(body)}


def validate_outcome_identity(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("outcome identity 必须是对象")
    required = {"entity_type", "entity_id", "as_of", "outcome_due", "horizon"}
    if not required.issubset(value):
        raise ContractError(f"outcome identity 缺字段：{sorted(required - set(value))}")
    horizon = value["horizon"]
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
        raise ContractError("outcome identity.horizon 必须是正整数")
    rebuilt = outcome_identity(
        entity_type=str(value["entity_type"]),
        entity_id=str(value["entity_id"]),
        as_of=value["as_of"],
        outcome_due=value["outcome_due"],
        horizon=int(horizon),
    )
    if "identity" in value and value["identity"] != rebuilt["identity"]:
        raise ContractError("outcome identity 哈希与字段不符")
    return rebuilt


def identities_overlap(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """同实体且结果区间 [as_of, outcome_due] 相交即视为同一底层事实已暴露（保守口径）。"""
    if a["entity_type"] != b["entity_type"] or a["entity_id"] != b["entity_id"]:
        return False
    return not (a["outcome_due"] < b["as_of"] or b["outcome_due"] < a["as_of"])


def _semantic(obj: Mapping[str, Any], exclude: frozenset[str]) -> dict[str, Any]:
    return {k: v for k, v in obj.items() if k not in exclude}


def study_semantic(protocol: Mapping[str, Any]) -> dict[str, Any]:
    return _semantic(protocol, STUDY_RECORD_TIME_FIELDS | STUDY_STATE_FIELDS)


def study_identity(protocol: Mapping[str, Any]) -> str:
    return digest(study_semantic(protocol))


def forecast_semantic(forecast: Mapping[str, Any]) -> dict[str, Any]:
    return _semantic(forecast, FORECAST_RECORD_TIME_FIELDS | frozenset({"id"}))


def forecast_identity(forecast: Mapping[str, Any]) -> str:
    return digest(forecast_semantic(forecast))


def observation_semantic(observation: Mapping[str, Any]) -> dict[str, Any]:
    return _semantic(observation, OBSERVATION_RECORD_TIME_FIELDS | frozenset({"id"}))


def observation_identity(observation: Mapping[str, Any]) -> str:
    return digest(observation_semantic(observation))


def receipt_semantic(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return _semantic(receipt, RECEIPT_RECORD_TIME_FIELDS | frozenset({"id"}))


def receipt_identity(receipt: Mapping[str, Any]) -> str:
    return digest(receipt_semantic(receipt))


def exposure_intent(exposure: Mapping[str, Any]) -> dict[str, Any]:
    return _semantic(exposure, EXPOSURE_RECORD_TIME_FIELDS | frozenset({"id"}))


def exposure_identity(exposure: Mapping[str, Any]) -> str:
    return digest(exposure_intent(exposure))


# --------------------------------------------------------------------------- #
# analysis_policy：冻结统计口径，只能等于或严于既有缺省
# --------------------------------------------------------------------------- #
def default_analysis_policy(horizon: int) -> dict[str, Any]:
    return {
        "min_n": DEFAULT_MIN_N,
        "min_blocks": DEFAULT_MIN_BLOCKS,
        "n_boot": DEFAULT_BLOCK_BOOT,
        "seed": DEFAULT_BLOCK_SEED,
        "block_len": int(horizon),
        "null_p0": NULL_P0,
        "calibration_min_n": DEFAULT_CALIBRATION_MIN_N,
        "ties": "insufficient",
        "exposure_ledger_complete": False,
    }


def validate_analysis_policy(policy: Any, *, horizon: int) -> dict[str, Any]:
    defaults = default_analysis_policy(horizon)
    if policy is None:
        return defaults
    if not isinstance(policy, Mapping):
        raise ContractError("analysis_policy 必须是对象")
    unknown = set(policy) - set(defaults)
    if unknown:
        raise ContractError(f"analysis_policy 含未知键 {sorted(unknown)}")
    merged = {**defaults, **dict(policy)}
    for key in ("min_n", "min_blocks", "n_boot", "block_len", "calibration_min_n"):
        v = merged[key]
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            raise ContractError(f"analysis_policy.{key} 必须是正整数，得到 {v!r}")
    for key in ("min_n", "min_blocks", "n_boot", "calibration_min_n"):
        if merged[key] < defaults[key]:
            raise ContractError(
                f"analysis_policy.{key}={merged[key]} 低于冻结缺省 {defaults[key]}：不能为了得到支持而放宽"
            )
    if merged["block_len"] < int(horizon):
        raise ContractError(f"analysis_policy.block_len={merged['block_len']} 必须 ≥ outcome horizon {horizon}")
    if merged["seed"] != DEFAULT_BLOCK_SEED:
        raise ContractError(f"analysis_policy.seed 必须等于 {DEFAULT_BLOCK_SEED}：换种子 = 换口径，须走版本")
    if merged["null_p0"] != NULL_P0:
        raise ContractError(f"analysis_policy.null_p0 必须是 {NULL_P0}（对称胜负零假设）")
    if merged["ties"] != "insufficient":
        raise ContractError("analysis_policy.ties v1 只支持 'insufficient'（含平局 → 检验未定义）")
    if not isinstance(merged["exposure_ledger_complete"], bool):
        raise ContractError("analysis_policy.exposure_ledger_complete 必须是 bool")
    return merged


# --------------------------------------------------------------------------- #
# 窗口 / 臂 / 比较 / 基准
# --------------------------------------------------------------------------- #
def validate_window(value: Any, *, name: str, calendar: Calendar) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {"start", "end"}:
        raise ContractError(f"{name} 必须是 {{start, end}}")
    start = iso_date(value["start"], field_name=f"{name}.start")
    end = iso_date(value["end"], field_name=f"{name}.end")
    if start > end:
        raise ContractError(f"{name}.start {start} 晚于 end {end}")
    if not calendar.contains(start) or not calendar.contains(end):
        raise ContractError(f"{name} 的端点必须是冻结日历内的交易日")
    return {"start": start, "end": end}


def validate_arm(value: Any, *, outcome_spec: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError("arm 必须是对象")
    allowed_keys = {"arm_id", "role", "rule", "allowed_fields", "removed_track", "recipe_id"}
    unknown = set(value) - allowed_keys
    if unknown:
        raise ContractError(f"arm 含未知键 {sorted(unknown)}")
    arm_id = value.get("arm_id")
    if not isinstance(arm_id, str) or not _ARM_ID_RE.match(arm_id):
        raise ContractError(f"arm_id 必须匹配 {_ARM_ID_RE.pattern}：{arm_id!r}")
    role = value.get("role")
    if role not in ARM_ROLES:
        raise ContractError(f"arm[{arm_id}].role 必须在 {ARM_ROLES}")
    fields = value.get("allowed_fields", [])
    if not isinstance(fields, list) or any(not isinstance(f, str) for f in fields):
        raise ContractError(f"arm[{arm_id}].allowed_fields 必须是标签名列表")
    bad = [f for f in fields if f not in LABEL_KINDS]
    if bad:
        raise ContractError(f"arm[{arm_id}].allowed_fields 含白名单外标签 {bad}")
    allowed = sorted(set(fields))
    removed = value.get("removed_track")
    removed_norm: dict[str, Any] | None = None
    if removed is not None:
        if not isinstance(removed, Mapping) or set(removed) - {"track_id", "fields", "derived_fields"}:
            raise ContractError(f"arm[{arm_id}].removed_track 只允许 track_id/fields/derived_fields")
        track_id = validate_token(removed.get("track_id"), field_name=f"arm[{arm_id}].removed_track.track_id")
        rf = removed.get("fields", [])
        df = removed.get("derived_fields", [])
        for name, seq in (("fields", rf), ("derived_fields", df)):
            if not isinstance(seq, list) or any(not isinstance(f, str) for f in seq):
                raise ContractError(f"arm[{arm_id}].removed_track.{name} 必须是标签名列表")
        removed_norm = {"track_id": track_id, "fields": sorted(set(rf)), "derived_fields": sorted(set(df))}
        leaked = (set(rf) | set(df)) & set(allowed)
        if leaked:
            raise ContractError(
                f"arm[{arm_id}] 声明删轨 {track_id} 却仍允许其字段/派生量 {sorted(leaked)}：残留信息，拒绝冻结"
            )
    rule = value.get("rule")
    rule_norm: dict[str, Any] | None = None
    if rule is not None:
        parsed, errors = validate_rule(rule)
        if errors or parsed is None:
            raise ContractError(f"arm[{arm_id}].rule 不合白名单：" + "; ".join(str(e) for e in errors))
        if parsed.entity_type != DEFAULT_ENTITY_TYPE:
            raise ContractError(f"arm[{arm_id}].rule 首版只支持 {DEFAULT_ENTITY_TYPE} 实体")
        success = parsed.success
        if (
            success.metric != outcome_spec["metric"]
            or success.horizon != outcome_spec["horizon"]
            or success.op != outcome_spec["op"]
            or success.value != outcome_spec["value"]
        ):
            raise ContractError(f"arm[{arm_id}].rule.outcome.success 必须与 study.outcome_spec 一致")
        labels = sorted({p.label for p in parsed.predicates})
        outside = [lab for lab in labels if lab not in allowed]
        if outside:
            raise ContractError(f"arm[{arm_id}].rule 引用了 allowed_fields 之外的标签 {outside}：输入隔离不成立")
        rule_norm = json.loads(canonical_bytes(rule))
    recipe_id = value.get("recipe_id")
    if recipe_id is not None:
        validate_token(recipe_id, field_name=f"arm[{arm_id}].recipe_id")
    return {
        "arm_id": arm_id,
        "role": role,
        "rule": rule_norm,
        "allowed_fields": allowed,
        "removed_track": removed_norm,
        "recipe_id": recipe_id,
    }


def validate_comparisons(value: Any, *, arm_ids: Sequence[str], primary: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ContractError("comparisons 必须是非空列表")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    confirmatory: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ContractError("comparison 必须是对象")
        keys = {"comparison_id", "base_arm_id", "candidate_arm_id", "claim_kind", "confirmatory"}
        if set(item) != keys:
            raise ContractError(f"comparison 必须恰有键 {sorted(keys)}")
        cid = validate_token(item["comparison_id"], field_name="comparison_id")
        if cid in seen:
            raise ContractError(f"comparison_id 重复：{cid}")
        seen.add(cid)
        base, cand = item["base_arm_id"], item["candidate_arm_id"]
        if base not in arm_ids or cand not in arm_ids:
            raise ContractError(f"comparison {cid} 引用了不存在的臂 {base!r}/{cand!r}")
        if base == cand:
            raise ContractError(f"comparison {cid} 两臂相同")
        if item["claim_kind"] not in CLAIM_KINDS:
            raise ContractError(f"comparison {cid}.claim_kind 必须在 {CLAIM_KINDS}")
        if not isinstance(item["confirmatory"], bool):
            raise ContractError(f"comparison {cid}.confirmatory 必须是 bool")
        if item["confirmatory"]:
            confirmatory.append(cid)
            if item["claim_kind"] != CLAIM_KIND_PRIMARY:
                raise ContractError(f"确认性比较 {cid} 只能声明 {CLAIM_KIND_PRIMARY}")
        out.append(
            {
                "comparison_id": cid,
                "base_arm_id": base,
                "candidate_arm_id": cand,
                "claim_kind": item["claim_kind"],
                "confirmatory": item["confirmatory"],
            }
        )
    if len(confirmatory) != 1:
        raise ContractError(f"每个 study 只能有一个确认性主比较，得到 {len(confirmatory)} 个")
    if primary != confirmatory[0]:
        raise ContractError(f"primary_comparison_id={primary!r} 必须等于唯一确认性比较 {confirmatory[0]}")
    return out


def validate_baseline_spec(value: Any) -> dict[str, Any]:
    """冻结基准：源行 / 分母 / 版本 / purge / p_baseline 全部落在协议里；无有效样本 p_baseline=None。"""
    if not isinstance(value, Mapping):
        raise ContractError("baseline_spec 必须是对象")
    required = {"kind", "p_baseline", "n_dates", "n_rows", "n_unknown", "n_purged", "source_hash", "recipe_hash"}
    if set(value) != required:
        raise ContractError(f"baseline_spec 必须恰有键 {sorted(required)}")
    if value["kind"] not in BASELINE_KINDS:
        raise ContractError(f"baseline_spec.kind 必须在 {BASELINE_KINDS}")
    for key in ("n_dates", "n_rows", "n_unknown", "n_purged"):
        v = value[key]
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ContractError(f"baseline_spec.{key} 必须是非负整数")
    p = value["p_baseline"]
    if value["n_dates"] == 0:
        if p is not None:
            raise ContractError("baseline_spec 无有效日期时 p_baseline 必须为 null，不得填 0.5")
    elif not is_probability(p):
        raise ContractError(f"baseline_spec.p_baseline 必须是 [0,1] 概率，得到 {p!r}")
    validate_content_id(value["source_hash"], field_name="baseline_spec.source_hash")
    validate_content_id(value["recipe_hash"], field_name="baseline_spec.recipe_hash")
    return {
        **{k: value[k] for k in sorted(required)},
        "p_baseline": (float(p) if p is not None else None),
    }


def validate_event_spec(value: Any, *, arm_ids: Sequence[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or "kind" not in value:
        raise ContractError("event_spec 必须是含 kind 的对象")
    kind = value["kind"]
    if kind == "rule":
        if set(value) != {"kind", "arm_id"} or value["arm_id"] not in arm_ids:
            raise ContractError("event_spec{kind=rule} 必须引用一个已声明且带规则的臂")
        return {"kind": "rule", "arm_id": value["arm_id"]}
    if kind == "manual":
        desc = value.get("description")
        if set(value) != {"kind", "description"} or not isinstance(desc, str) or not desc.strip():
            raise ContractError("event_spec{kind=manual} 必须带非空 description（散文不作真值，只作说明）")
        return {"kind": "manual", "description": desc.strip()}
    raise ContractError(f"event_spec.kind 未知：{kind!r}")


# --------------------------------------------------------------------------- #
# StudyProtocol：从输入体冻结为协议
# --------------------------------------------------------------------------- #
_STUDY_INPUT_KEYS = {
    "owner_user_id",
    "lineage_id",
    "parent_study_id",
    "question",
    "mode",
    "event_spec",
    "universe_ref",
    "universe_hash",
    "universe_members",
    "outcome_spec",
    "calendar",
    "forward_start",
    "evaluation_end",
    "discovery_window",
    "validation_window",
    "holdout_window",
    "arms",
    "baseline_spec",
    "comparisons",
    "primary_comparison_id",
    "analysis_policy",
    "source_hashes",
    "version_hashes",
    "tags",
}


def freeze_protocol_content(body: Any, *, owner: str, now: datetime) -> dict[str, Any]:
    """把 06 传来的协议输入体校验并冻结为 ``StudyProtocol``。

    纯函数：``now`` 只用于 ``created_at/frozen_at`` 与「forward_start 前冻结」检查。
    ``owner`` 是经验证的用户上下文；正文里的 ``owner_user_id`` 若与之不符直接拒绝——
    请求正文不能替代访问控制。
    """
    owner = validate_owner(owner)
    if not isinstance(body, Mapping):
        raise ContractError("协议输入必须是对象")
    unknown = set(body) - _STUDY_INPUT_KEYS
    if unknown:
        raise ContractError(f"协议输入含未知键 {sorted(unknown)}（不接受调用方自填 id/status/eligible）")
    body_owner = body.get("owner_user_id")
    if body_owner is not None and body_owner != owner:
        raise OwnerMismatch(f"正文 owner_user_id={body_owner!r} 与认证 owner={owner!r} 不一致")

    mode = body.get("mode")
    if mode not in MODES:
        raise ContractError(f"mode 必须在 {MODES}，得到 {mode!r}")
    question = body.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ContractError("question 必须是非空字符串")
    lineage_id = validate_token(body.get("lineage_id"), field_name="lineage_id")
    parent = body.get("parent_study_id")
    if parent is not None:
        validate_content_id(parent, field_name="parent_study_id")

    outcome_spec = validate_outcome_spec(body.get("outcome_spec"))
    horizon = outcome_spec["horizon"]
    calendar = Calendar.from_any(body.get("calendar"))

    arms_in = body.get("arms")
    if not isinstance(arms_in, list) or not arms_in:
        raise ContractError("arms 必须是非空列表")
    arms = [validate_arm(a, outcome_spec=outcome_spec) for a in arms_in]
    arm_ids = [a["arm_id"] for a in arms]
    if len(set(arm_ids)) != len(arm_ids):
        raise ContractError("arm_id 重复")
    comparisons = validate_comparisons(
        body.get("comparisons"), arm_ids=arm_ids, primary=body.get("primary_comparison_id")
    )
    event_spec = validate_event_spec(body.get("event_spec"), arm_ids=arm_ids)
    if event_spec["kind"] == "rule":
        event_arm = next(a for a in arms if a["arm_id"] == event_spec["arm_id"])
        if event_arm["rule"] is None:
            raise ContractError("event_spec 引用的臂没有规则")

    universe_ref = validate_token(body.get("universe_ref"), field_name="universe_ref")
    members = body.get("universe_members")
    if members is not None:
        if not isinstance(members, list) or not members or any(not isinstance(m, str) or not m for m in members):
            raise ContractError("universe_members 必须是非空实体 id 列表")
        members = sorted(set(members))
        computed = digest(members)
        if body.get("universe_hash") not in (None, computed):
            raise ContractError("universe_hash 与 universe_members 不符")
        universe_hash = computed
    else:
        universe_hash = validate_content_id(body.get("universe_hash"), field_name="universe_hash")

    discovery = validate_window(body.get("discovery_window"), name="discovery_window", calendar=calendar)
    validation = body.get("validation_window")
    holdout = body.get("holdout_window")
    validation = validate_window(validation, name="validation_window", calendar=calendar) if validation else None
    holdout = validate_window(holdout, name="holdout_window", calendar=calendar) if holdout else None
    last_end = discovery["end"]
    for name, win in (("validation_window", validation), ("holdout_window", holdout)):
        if win is None:
            continue
        if win["start"] <= last_end:
            raise ContractError(f"{name}.start {win['start']} 必须严格晚于前一窗末 {last_end}（三段窗严格递进）")
        last_end = win["end"]

    forward_start = iso_date(body.get("forward_start"), field_name="forward_start")
    evaluation_end = iso_date(body.get("evaluation_end"), field_name="evaluation_end")
    if not calendar.contains(forward_start) or not calendar.contains(evaluation_end):
        raise ContractError("forward_start / evaluation_end 必须是冻结日历内的交易日")
    if forward_start > evaluation_end:
        raise ContractError("forward_start 不能晚于 evaluation_end")
    if forward_start <= discovery["end"]:
        raise ContractError("forward_start 必须晚于 discovery_window.end：发现窗不能与结果期重叠")
    # 日历必须能覆盖 evaluation_end 之后 h 个交易日，否则到期日无从冻结。
    calendar.shift(evaluation_end, horizon)
    frozen_day = market_day(now)
    if mode == "forward" and frozen_day > forward_start:
        raise ContractError(f"forward 协议必须在 forward_start={forward_start} 之前（含当日）冻结，现在是 {frozen_day}")

    policy = validate_analysis_policy(body.get("analysis_policy"), horizon=horizon)
    baseline_spec = validate_baseline_spec(body.get("baseline_spec"))
    source_hashes = _str_map(body.get("source_hashes"), field_name="source_hashes")
    version_hashes = _str_map(body.get("version_hashes"), field_name="version_hashes")
    if mode != "forward" and not version_hashes:
        raise ContractError("历史模式必须冻结 version_hashes（源版本身份），否则结算无法核版本")
    tags = body.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise ContractError("tags 必须是字符串列表")

    semantic: dict[str, Any] = {
        "schema_version": SCHEMA_STUDY,
        "owner_user_id": owner,
        "visibility": VISIBILITY_PRIVATE,
        "lineage_id": lineage_id,
        "parent_study_id": parent,
        "question": question.strip(),
        "mode": mode,
        "event_spec": event_spec,
        "event_spec_hash": digest(event_spec),
        "universe_ref": universe_ref,
        "universe_hash": universe_hash,
        "universe_members": members,
        "outcome_spec": outcome_spec,
        "outcome_spec_hash": digest(outcome_spec),
        "calendar": list(calendar.dates),
        "calendar_hash": calendar.hash,
        "forward_start": forward_start,
        "evaluation_end": evaluation_end,
        "discovery_window": discovery,
        "validation_window": validation,
        "holdout_window": holdout,
        "arms": arms,
        "baseline_spec": baseline_spec,
        "baseline_hash": digest(baseline_spec),
        "comparisons": comparisons,
        "primary_comparison_id": body.get("primary_comparison_id"),
        "analysis_policy": policy,
        "framework_hash": digest(
            {
                "arms": arms,
                "comparisons": comparisons,
                "outcome_spec": outcome_spec,
                "event_spec": event_spec,
                "analysis_policy": policy,
            }
        ),
        "source_hashes": source_hashes,
        "version_hashes": version_hashes,
        "tags": sorted(set(tags)),
    }
    study_id = digest(semantic)
    protocol = {
        **semantic,
        "id": study_id,
        "study_id": study_id,
        "status": "frozen",
        "exposure_receipt_refs": [],
        "created_at": utc_iso(now),
        "frozen_at": utc_iso(now),
    }
    canonical_bytes(protocol)
    return protocol


def validate_frozen_protocol(protocol: Any, *, owner: str | None = None) -> dict[str, Any]:
    """读回校验：形状、身份哈希、归属。归档件可读，不可篡改。"""
    if not isinstance(protocol, Mapping):
        raise ContractError("protocol 必须是对象")
    if protocol.get("schema_version") != SCHEMA_STUDY:
        raise ContractError(f"protocol.schema_version 必须是 {SCHEMA_STUDY}")
    if protocol.get("status") not in STUDY_STATUSES:
        raise ContractError("protocol.status 非法")
    study_id = validate_content_id(protocol.get("study_id"), field_name="study_id")
    if protocol.get("id") != study_id or study_identity(protocol) != study_id:
        raise ContractError("protocol 身份哈希与内容不符")
    validate_owner(protocol.get("owner_user_id"))
    if owner is not None and protocol["owner_user_id"] != owner:
        raise OwnerMismatch("protocol 不属于该 owner")
    Calendar.from_any(protocol.get("calendar"))
    return dict(protocol)


# --------------------------------------------------------------------------- #
# ProbabilityForecast / OutcomeObservation / Receipt / Exposure 的形状校验
# --------------------------------------------------------------------------- #
_FORECAST_KEYS = {
    "schema_version",
    "id",
    "owner_user_id",
    "study_id",
    "case_id",
    "arm_id",
    "case",
    "forecast_at",
    "registered_at",
    "as_of",
    "knowledge_cutoff",
    "outcome_due",
    "p",
    "p_baseline",
    "origin",
    "mode",
    "projection_hash",
    "input_refs",
    "model_id",
    "model_version",
    "prompt_hash",
    "framework_hash",
    "probability_recipe_hash",
    "baseline_hash",
    "pit_grade",
    "memory_bucket",
    "outcome_spec_hash",
    "calendar_hash",
    "capture_receipt_ref",
    "supersedes_id",
    "isolation_verified",
    "actor",
}


def validate_forecast_record(forecast: Any, *, owner: str | None = None) -> dict[str, Any]:
    if not isinstance(forecast, Mapping):
        raise ContractError("forecast 必须是对象")
    if set(forecast) != _FORECAST_KEYS:
        missing = _FORECAST_KEYS - set(forecast)
        extra = set(forecast) - _FORECAST_KEYS
        raise ContractError(f"forecast 字段不符：缺 {sorted(missing)} 多 {sorted(extra)}")
    if forecast["schema_version"] != SCHEMA_FORECAST:
        raise ContractError("forecast.schema_version 不符")
    fid = validate_content_id(forecast["id"], field_name="forecast.id")
    if forecast_identity(forecast) != fid:
        raise ContractError("forecast 身份哈希与内容不符")
    validate_owner(forecast["owner_user_id"])
    if owner is not None and forecast["owner_user_id"] != owner:
        raise OwnerMismatch("forecast 不属于该 owner")
    if not is_probability(forecast["p"]):
        raise ContractError("forecast.p 不是概率")
    if forecast["p_baseline"] is not None and not is_probability(forecast["p_baseline"]):
        raise ContractError("forecast.p_baseline 不是概率")
    if forecast["origin"] not in ORIGINS or forecast["mode"] not in MODES:
        raise ContractError("forecast.origin/mode 非法")
    if forecast["pit_grade"] not in PIT_GRADES:
        raise ContractError("forecast.pit_grade 非法")
    return dict(forecast)


_OBSERVATION_KEYS = {
    "schema_version",
    "id",
    "owner_user_id",
    "study_id",
    "forecast_id",
    "case_id",
    "observed_at",
    "available_at",
    "due",
    "source_refs",
    "value",
    "status",
    "metric_value",
    "reason",
}


def validate_observation_record(observation: Any, *, owner: str | None = None) -> dict[str, Any]:
    if not isinstance(observation, Mapping) or set(observation) != _OBSERVATION_KEYS:
        raise ContractError("observation 字段不符")
    if observation["schema_version"] != SCHEMA_OBSERVATION:
        raise ContractError("observation.schema_version 不符")
    oid = validate_content_id(observation["id"], field_name="observation.id")
    if observation_identity(observation) != oid:
        raise ContractError("observation 身份哈希与内容不符")
    if owner is not None and observation["owner_user_id"] != owner:
        raise OwnerMismatch("observation 不属于该 owner")
    if observation["status"] not in OBSERVATION_STATUSES:
        raise ContractError("observation.status 非法")
    value = observation["value"]
    if observation["status"] == "settled":
        if value not in (0, 1) or isinstance(value, bool):
            raise ContractError("settled observation 的 value 必须是 0 或 1")
    elif value is not None:
        raise ContractError("非 settled observation 的 value 必须为 null（缺记录不等于事实为假）")
    return dict(observation)


_EXPOSURE_KEYS = {
    "schema_version",
    "id",
    "owner_user_id",
    "operation_id",
    "lineage_id",
    "study_id",
    "framework_hash",
    "window",
    "case_manifest_hash",
    "outcome_identities",
    "stage",
    "accessed_at",
    "actor",
    "reason",
}


def build_exposure_intent(
    *,
    owner: str,
    operation_id: str,
    lineage_id: str | None,
    study_id: str | None,
    framework_hash: str | None,
    window: Mapping[str, str] | None,
    case_manifest_hash: str | None,
    outcome_identities: Iterable[Mapping[str, Any]],
    stage: str,
    actor: str,
    reason: str,
) -> dict[str, Any]:
    """曝光意图（不含 accessed_at / id）。同意图重试 → 同 id → 返回原件。"""
    owner = validate_owner(owner)
    operation_id = validate_operation_id(operation_id)
    if stage not in EXPOSURE_STAGES:
        raise ContractError(f"stage 必须在 {EXPOSURE_STAGES}")
    if not isinstance(actor, str) or not actor.strip():
        raise ContractError("actor 必须是非空字符串（未知来源请显式写 'unknown'）")
    if not isinstance(reason, str):
        raise ContractError("reason 必须是字符串")
    if lineage_id is not None:
        validate_token(lineage_id, field_name="lineage_id")
    if study_id is not None:
        validate_content_id(study_id, field_name="study_id")
    if framework_hash is not None:
        validate_content_id(framework_hash, field_name="framework_hash")
    if case_manifest_hash is not None:
        validate_content_id(case_manifest_hash, field_name="case_manifest_hash")
    win = None
    if window is not None:
        if not isinstance(window, Mapping) or set(window) != {"start", "end"}:
            raise ContractError("window 必须是 {start, end}")
        win = {
            "start": iso_date(window["start"], field_name="window.start"),
            "end": iso_date(window["end"], field_name="window.end"),
        }
        if win["start"] > win["end"]:
            raise ContractError("window.start 晚于 end")
    ids = [validate_outcome_identity(x) for x in outcome_identities]
    ids.sort(key=lambda x: (x["entity_type"], x["entity_id"], x["as_of"], x["outcome_due"], x["horizon"]))
    return {
        "schema_version": SCHEMA_EXPOSURE,
        "owner_user_id": owner,
        "operation_id": operation_id,
        "lineage_id": lineage_id,
        "study_id": study_id,
        "framework_hash": framework_hash,
        "window": win,
        "case_manifest_hash": case_manifest_hash,
        "outcome_identities": ids,
        "stage": stage,
        "actor": actor.strip(),
        "reason": reason,
    }


def validate_exposure_record(exposure: Any, *, owner: str | None = None) -> dict[str, Any]:
    if not isinstance(exposure, Mapping) or set(exposure) != _EXPOSURE_KEYS:
        raise ContractError("exposure 字段不符")
    if exposure["schema_version"] != SCHEMA_EXPOSURE:
        raise ContractError("exposure.schema_version 不符")
    eid = validate_content_id(exposure["id"], field_name="exposure.id")
    if exposure_identity(exposure) != eid:
        raise ContractError("exposure 身份哈希与内容不符")
    if owner is not None and exposure["owner_user_id"] != owner:
        raise OwnerMismatch("exposure 不属于该 owner")
    return dict(exposure)


@dataclass(frozen=True)
class RejectedInput:
    index: int
    reason: str
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "reason": self.reason, "detail": self.detail, **self.extra}


__all__ = [
    "Calendar",
    "ConflictError",
    "ContractError",
    "Gap",
    "OwnerMismatch",
    "RejectedInput",
    "canonical_bytes",
    "derive_case_id",
    "digest",
    "ensure_aware_now",
    "exposure_identity",
    "exposure_intent",
    "forecast_identity",
    "forecast_semantic",
    "freeze_protocol_content",
    "identities_overlap",
    "is_probability",
    "iso_date",
    "make_gap",
    "market_close",
    "market_day",
    "observation_identity",
    "outcome_identity",
    "outcome_predicate",
    "parse_ts",
    "receipt_identity",
    "study_identity",
    "study_semantic",
    "utc_iso",
    "validate_exposure_record",
    "validate_forecast_record",
    "validate_frozen_protocol",
    "validate_observation_record",
    "validate_outcome_identity",
    "validate_outcome_spec",
    "validate_owner",
    "validate_projection_hash",
]

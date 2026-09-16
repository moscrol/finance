"""研究验证服务门面（spec 03 §5 / §7 / §8）。

六个公开函数，全部显式接收 ``owner`` / ``repository`` / ``now``：

    freeze_study        协议冻结（forward_start 前；同语义幂等）
    register_forecasts  事前概率登记（forward 限 D0 盘后；历史模式限确定性 / LLM 原件）
    settle_outcomes     到期结算（now ≥ D+h 收盘、源可用、版本一致；未到期 pending）
    evaluate_study      配对评分 + 胜出日期检验 + 曝光判定 → MethodValidationReceipt
    read_receipt        读收据（先登记曝光再返回）
    record_exposure     原子登记底层结果曝光（owner 全局台账）

06 负责认证 owner、提供可信时钟与 ``userspace`` 解析后的私有根；本模块不读环境变量、
不从 cwd 推断、不 import ``intelligence.eval``。客户端不传 ``now``。

eligible 由冻结身份与曝光记录**派生**，任何输入里的 ``eligible=true`` 都是未知键 → 拒收。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol, Sequence

from .contracts import (
    SCHEMA_FORECAST,
    SCHEMA_OBSERVATION,
    SCHEMA_RECEIPT,
    Calendar,
    ConflictError,
    ContractError,
    Gap,
    OwnerMismatch,
    RejectedInput,
    build_exposure_intent,
    derive_case_id,
    digest,
    ensure_aware_now,
    exposure_intent,
    forecast_identity,
    forecast_semantic,
    freeze_protocol_content,
    identities_overlap,
    is_probability,
    iso_date,
    make_gap,
    market_close,
    market_day,
    observation_identity,
    outcome_identity,
    outcome_predicate,
    parse_ts,
    receipt_identity,
    utc_iso,
    validate_content_id,
    validate_owner,
    validate_projection_hash,
    validate_token,
)
from .repository import Repository
from .scoring import DailyDelta, PairSample, calibration_buckets, daily_deltas, paired_readout

ORIGINS_BY_MODE: dict[str, tuple[str, ...]] = {
    "forward": ("human_manual", "deterministic"),
    "historical_rule": ("deterministic",),
    "historical_llm": ("historical_llm",),
}
UNKNOWN_ACTORS = frozenset({"unknown", "external"})
EVALUATE_ACTOR = "research_validation.evaluate_study"
SEALED_UNTIL_END = "sealed_until_evaluation_end"
_FORECAST_INPUT_KEYS = {
    "entity_type",
    "entity_id",
    "as_of",
    "arm_id",
    "p",
    "forecast_at",
    "origin",
    "knowledge_cutoff",
    "pit_grade",
    "memory_bucket",
    "projection_hash",
    "input_refs",
    "model_id",
    "model_version",
    "prompt_hash",
    "probability_recipe_hash",
    "capture_receipt_ref",
    "actor",
    "isolation_verified",
}


class OutcomeSource(Protocol):
    """06 注入的已授权结果源（只读）。"""

    def describe(self) -> Mapping[str, Any]:
        """``{"source_ref", "source_max_trade_date", "version_hashes": {..}, "calendar": [..]?}``"""

    def lookup(self, *, entity_type: str, entity_id: str, as_of: str, horizon: int) -> Mapping[str, Any] | None:
        """``{"status": ok|pending|missing, "metric_value": float|None, "computed_at": iso}`` 或 None。"""


class PitVerifier(Protocol):
    """06 注入的 PIT 收据校验器：返回 ``{"verified": bool, "pit_grade": str, "knowledge_cutoff"?: iso}`` 或 None。"""

    def verify(self, capture_receipt_ref: str) -> Mapping[str, Any] | None: ...


@dataclass
class RegisterResult:
    study_id: str
    accepted: list[dict[str, Any]] = field(default_factory=list)
    idempotent: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[RejectedInput] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "accepted": [f["id"] for f in self.accepted],
            "idempotent": [f["id"] for f in self.idempotent],
            "rejected": [r.to_dict() for r in self.rejected],
            "gaps": [g.to_dict() for g in self.gaps],
        }


@dataclass
class SettleResult:
    study_id: str
    refused: bool = False
    settled: list[dict[str, Any]] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    revised: list[dict[str, Any]] = field(default_factory=list)
    invalid: list[dict[str, Any]] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "refused": self.refused,
            "settled": [o["id"] for o in self.settled],
            "unchanged": list(self.unchanged),
            "revised": [o["id"] for o in self.revised],
            "invalid": [o["id"] for o in self.invalid],
            "pending": list(self.pending),
            "missing": list(self.missing),
            "gaps": [g.to_dict() for g in self.gaps],
        }


# --------------------------------------------------------------------------- #
# 公共守卫
# --------------------------------------------------------------------------- #
def _guard(owner: Any, repository: Any, now: Any) -> tuple[str, Repository, Any]:
    owner = validate_owner(owner)
    if not isinstance(repository, Repository):
        raise ContractError("repository 必须是 research_validation.Repository")
    if repository.owner_user_id != owner:
        raise OwnerMismatch(f"repository 属于 {repository.owner_user_id!r}，请求 owner={owner!r}")
    return owner, repository, ensure_aware_now(now)


def _load(owner: str, repository: Repository, study_id: str) -> dict[str, Any]:
    protocol = repository.load_protocol(validate_content_id(study_id, field_name="study_id"))
    if protocol["owner_user_id"] != owner:
        raise OwnerMismatch("study 不属于该 owner")
    return protocol


# --------------------------------------------------------------------------- #
# 1. 冻结
# --------------------------------------------------------------------------- #
def freeze_study(*, owner: str, repository: Repository, now: Any, protocol_input: Mapping[str, Any]) -> dict[str, Any]:
    owner, repository, now = _guard(owner, repository, now)
    protocol = freeze_protocol_content(protocol_input, owner=owner, now=now)
    stored, _created = repository.publish_protocol(protocol)
    # study_id 是语义摘要：同 id 必同语义，落盘的只可能在记录时间上不同 → 返回首次原件。
    return stored


# --------------------------------------------------------------------------- #
# 2. 登记
# --------------------------------------------------------------------------- #
def _as_of_allowed(protocol: Mapping[str, Any], as_of: str) -> None:
    if as_of <= protocol["discovery_window"]["end"]:
        raise ContractError(f"as_of={as_of} 落在发现窗内或之前：结果期不能与发现窗重叠", "as_of_in_discovery_window")
    windows = [w for w in (protocol.get("validation_window"), protocol.get("holdout_window")) if w]
    if protocol["mode"] == "forward" or not windows:
        if not protocol["forward_start"] <= as_of <= protocol["evaluation_end"]:
            raise ContractError(
                f"as_of={as_of} 不在 [{protocol['forward_start']}, {protocol['evaluation_end']}]", "as_of_out_of_range"
            )
        return
    if not any(w["start"] <= as_of <= w["end"] for w in windows):
        raise ContractError(f"as_of={as_of} 不在 validation / holdout 窗内", "as_of_out_of_range")


def _reason(exc: ContractError, default: str) -> str:
    return exc.args[1] if len(exc.args) > 1 and isinstance(exc.args[1], str) else default


def _build_forecast(
    protocol: Mapping[str, Any],
    calendar: Calendar,
    item: Any,
    *,
    now: Any,
    pit_verifier: PitVerifier | None,
) -> tuple[dict[str, Any], list[Gap]]:
    if not isinstance(item, Mapping):
        raise ContractError("forecast 输入必须是对象", "invalid_input")
    unknown = set(item) - _FORECAST_INPUT_KEYS
    if unknown:
        raise ContractError(f"forecast 输入含未知键 {sorted(unknown)}（不接受 id/case_id/registered_at/eligible 自填）", "unknown_keys")
    arms = {a["arm_id"]: a for a in protocol["arms"]}
    arm_id = item.get("arm_id")
    if arm_id not in arms:
        raise ContractError(f"arm_id={arm_id!r} 不在协议臂里", "arm_unknown")
    p = item.get("p")
    if not is_probability(p):
        raise ContractError(f"p={p!r} 不是 [0,1] 内的有限非 bool 数字", "invalid_probability")
    mode = protocol["mode"]
    origin = item.get("origin")
    if origin not in ORIGINS_BY_MODE[mode]:
        raise ContractError(f"origin={origin!r} 不允许出现在 mode={mode} 的 study（允许 {ORIGINS_BY_MODE[mode]}）", "mode_origin_mismatch")
    recipe_hash = item.get("probability_recipe_hash")
    if origin == "deterministic":
        validate_content_id(recipe_hash, field_name="probability_recipe_hash")
    elif recipe_hash is not None:
        raise ContractError("只有确定性概率才绑定 probability_recipe_hash", "recipe_not_allowed")
    if origin == "historical_llm":
        if not isinstance(item.get("model_id"), str) or not item.get("model_id"):
            raise ContractError("historical_llm 概率必须带 model_id", "model_required")

    entity_type = item.get("entity_type", "sector")
    entity_id = item.get("entity_id")
    if not isinstance(entity_type, str) or not entity_type or not isinstance(entity_id, str) or not entity_id:
        raise ContractError("entity_type / entity_id 必须是非空字符串", "invalid_entity")
    members = protocol.get("universe_members")
    if members is not None and entity_id not in members:
        raise ContractError(f"{entity_id} 不在冻结宇宙内", "entity_not_in_universe")

    as_of = iso_date(item.get("as_of"), field_name="as_of")
    if not calendar.contains(as_of):
        raise ContractError(f"as_of={as_of} 不是冻结日历内的交易日", "as_of_not_trading_day")
    horizon = int(protocol["outcome_spec"]["horizon"])
    outcome_due = calendar.shift(as_of, horizon)
    _as_of_allowed(protocol, as_of)

    forecast_at = parse_ts(item.get("forecast_at"), field_name="forecast_at")
    if forecast_at > now:
        raise ContractError("forecast_at 晚于可信 now", "forecast_at_in_future")
    if mode == "forward":
        today = market_day(now)
        if as_of < today:
            raise ContractError(f"as_of={as_of} 早于登记日 {today}：前向登记不可回填", "late_registration")
        if as_of > today:
            raise ContractError(f"as_of={as_of} 晚于登记日 {today}", "as_of_in_future")
        if now < market_close(as_of):
            raise ContractError("前向登记限 D0 盘后（15:00 Asia/Shanghai 之后）", "before_market_close")

    cutoff_default = market_close(as_of)
    cutoff_raw = item.get("knowledge_cutoff")
    cutoff = parse_ts(cutoff_raw, field_name="knowledge_cutoff") if cutoff_raw is not None else cutoff_default
    if cutoff > cutoff_default:
        raise ContractError("knowledge_cutoff 晚于 as_of 收盘：晚于 cutoff 的信息不得进入事前概率", "knowledge_cutoff_late")

    gaps: list[Gap] = []
    pit_grade = "unverified"
    ref = item.get("capture_receipt_ref")
    if ref is not None:
        validate_token(ref, field_name="capture_receipt_ref")
        verdict = pit_verifier.verify(ref) if pit_verifier is not None else None
        if verdict and verdict.get("verified") is True and verdict.get("pit_grade") in ("strict", "trade_date_only"):
            pit_grade = str(verdict["pit_grade"])
            receipt_cutoff = verdict.get("knowledge_cutoff")
            # 方向：捕获件的可知时刻必须 **不晚于** 本次预测截止。晚于 = 捕获件里含预测截止
            # 之后的信息，拿它当事前证据就是前视偏差（spec 03 §5「晚于 cutoff 拒收」）。
            # 反向（收据早于本次截止）是正常事前证据：更早可知者必然在更晚的截止前也可知，
            # 拒绝它会把「盘中抓料、收盘定 cutoff」这种正常流程整批打掉。
            # cutoff ≤ market_close(as_of) ≤ now 恒成立，所以本判据同时覆盖「收据晚于可信 now」。
            if receipt_cutoff is not None and parse_ts(receipt_cutoff, field_name="receipt.knowledge_cutoff") > cutoff:
                raise ContractError(
                    "PIT 收据的可知时刻晚于本次预测 knowledge_cutoff：捕获件含截止后信息，不得作事前证据",
                    "pit_receipt_after_forecast_cutoff",
                )
    if pit_grade == "unverified":
        claimed = item.get("pit_grade")
        detail = "无可验证 PIT 收据；只有 hash 而无原件 / 验证收据不能升 strict"
        if claimed in ("strict", "trade_date_only"):
            detail = f"调用方声明 pit_grade={claimed} 但无验证收据 → 降为 unverified"
        gaps.append(make_gap("unverified_pit", [f"{entity_id}@{as_of}#{arm_id}"], detail=detail))

    projection_hash = item.get("projection_hash")
    if projection_hash is not None:
        try:
            validate_projection_hash(projection_hash)
        except ContractError as exc:
            raise ContractError(str(exc.args[0]), "invalid_projection_hash") from exc
    input_refs = item.get("input_refs") or {}
    if not isinstance(input_refs, Mapping) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in input_refs.items()
    ):
        raise ContractError("input_refs 必须是 {str: str}", "invalid_input_refs")
    for key in ("model_id", "model_version", "prompt_hash", "memory_bucket", "actor"):
        v = item.get(key)
        if v is not None and not isinstance(v, str):
            raise ContractError(f"{key} 必须是字符串或 null", "invalid_input")
    isolation = item.get("isolation_verified")
    if isolation is not None and not isinstance(isolation, bool):
        raise ContractError("isolation_verified 必须是 bool 或 null", "invalid_input")

    case_id = derive_case_id(
        entity_type=entity_type,
        entity_id=entity_id,
        as_of=as_of,
        event_spec_hash=protocol["event_spec_hash"],
        outcome_due=outcome_due,
        universe_hash=protocol["universe_hash"],
    )
    record: dict[str, Any] = {
        "schema_version": SCHEMA_FORECAST,
        "owner_user_id": protocol["owner_user_id"],
        "study_id": protocol["study_id"],
        "case_id": case_id,
        "arm_id": arm_id,
        "case": {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "as_of": as_of,
            "outcome_due": outcome_due,
            "horizon": horizon,
        },
        "forecast_at": utc_iso(forecast_at),
        "registered_at": utc_iso(now),
        "as_of": as_of,
        "knowledge_cutoff": utc_iso(cutoff),
        "outcome_due": outcome_due,
        "p": float(p),
        "p_baseline": protocol["baseline_spec"]["p_baseline"],
        "origin": origin,
        "mode": mode,
        "projection_hash": projection_hash,
        "input_refs": dict(sorted(input_refs.items())),
        "model_id": item.get("model_id"),
        "model_version": item.get("model_version"),
        "prompt_hash": item.get("prompt_hash"),
        "framework_hash": protocol["framework_hash"],
        "probability_recipe_hash": recipe_hash,
        "baseline_hash": protocol["baseline_hash"],
        "pit_grade": pit_grade,
        "memory_bucket": item.get("memory_bucket"),
        "outcome_spec_hash": protocol["outcome_spec_hash"],
        "calendar_hash": protocol["calendar_hash"],
        "capture_receipt_ref": ref,
        "supersedes_id": None,
        "isolation_verified": isolation,
        "actor": item.get("actor"),
    }
    record["id"] = forecast_identity(record)
    if protocol["baseline_spec"]["p_baseline"] is None:
        gaps.append(make_gap("baseline_unavailable", [case_id], detail="冻结基准无有效样本，p_baseline=null"))
    return record, gaps


def register_forecasts(
    *,
    owner: str,
    repository: Repository,
    now: Any,
    study_id: str,
    forecasts: Sequence[Any],
    pit_verifier: PitVerifier | None = None,
) -> RegisterResult:
    owner, repository, now = _guard(owner, repository, now)
    protocol = _load(owner, repository, study_id)
    if protocol["status"] != "frozen":
        raise ContractError(f"study 状态 {protocol['status']}，只有 frozen 可登记")
    calendar = Calendar.from_any(protocol["calendar"])
    result = RegisterResult(study_id=protocol["study_id"])
    for index, item in enumerate(forecasts):
        try:
            record, gaps = _build_forecast(protocol, calendar, item, now=now, pit_verifier=pit_verifier)
        except ContractError as exc:
            result.rejected.append(RejectedInput(index=index, reason=_reason(exc, "contract_error"), detail=str(exc.args[0])))
            continue
        stored, created = repository.publish_forecast(record)
        if created:
            result.accepted.append(stored)
            result.gaps.extend(gaps)
        elif forecast_semantic(stored) == forecast_semantic(record):
            result.idempotent.append(stored)
        else:
            result.rejected.append(
                RejectedInput(
                    index=index,
                    reason="conflict",
                    detail="同 (study, case, arm) 已有异义原件：v1 拒绝修订预测；改 p / 基准 / 时间 / recipe 请另开 study",
                    extra={"existing_id": stored["id"], "existing_p": stored["p"]},
                )
            )
    return result


# --------------------------------------------------------------------------- #
# 3. 结算
# --------------------------------------------------------------------------- #
def _latest_observation(observations: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    return observations[-1] if observations else None


def _describe_source(source: OutcomeSource) -> dict[str, Any]:
    desc = source.describe()
    if not isinstance(desc, Mapping):
        raise ContractError("outcome_source.describe() 必须返回对象")
    ref = desc.get("source_ref")
    if not isinstance(ref, str) or not ref:
        raise ContractError("outcome_source.describe().source_ref 必须是非空字符串")
    watermark = iso_date(desc.get("source_max_trade_date"), field_name="source_max_trade_date")
    versions = desc.get("version_hashes") or {}
    if not isinstance(versions, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in versions.items()):
        raise ContractError("outcome_source.describe().version_hashes 必须是 {str: str}")
    calendar = desc.get("calendar")
    if calendar is not None:
        calendar = list(Calendar.from_any(calendar).dates)
    return {"source_ref": ref, "source_max_trade_date": watermark, "version_hashes": dict(versions), "calendar": calendar}


def settle_outcomes(
    *, owner: str, repository: Repository, now: Any, study_id: str, outcome_source: OutcomeSource
) -> SettleResult:
    owner, repository, now = _guard(owner, repository, now)
    protocol = _load(owner, repository, study_id)
    calendar = Calendar.from_any(protocol["calendar"])
    spec = protocol["outcome_spec"]
    result = SettleResult(study_id=protocol["study_id"])
    desc = _describe_source(outcome_source)

    mismatched = {
        k: (protocol["version_hashes"][k], desc["version_hashes"][k])
        for k in protocol["version_hashes"]
        if k in desc["version_hashes"] and desc["version_hashes"][k] != protocol["version_hashes"][k]
    }
    if mismatched:
        result.refused = True
        result.gaps.append(
            make_gap("version_mismatch", [protocol["study_id"]], detail=f"源版本与冻结版本不一致：{mismatched}")
        )
        return result
    if desc["calendar"] is not None:
        frozen = calendar.dates
        prefix_end = min(frozen[-1], desc["calendar"][-1]) if desc["calendar"] else frozen[0]
        frozen_prefix = [d for d in frozen if d <= prefix_end]
        source_prefix = [d for d in desc["calendar"] if d <= prefix_end]
        if frozen_prefix != source_prefix:
            result.refused = True
            result.gaps.append(
                make_gap("version_mismatch", [protocol["study_id"]], detail="源交易日历与冻结日历前缀不一致")
            )
            return result

    source_refs = {
        "source_ref": desc["source_ref"],
        "source_max_trade_date": desc["source_max_trade_date"],
        **{f"version:{k}": v for k, v in sorted(desc["version_hashes"].items())},
    }
    for forecast in repository.list_forecasts(protocol["study_id"]):
        fid = forecast["id"]
        latest = _latest_observation(repository.list_observations(protocol["study_id"], fid))
        due = forecast["outcome_due"]
        due_close = market_close(due)
        if now < due_close:
            result.pending.append(fid)
            result.gaps.append(make_gap("future_not_due", [fid], retryable=True, next_check_at=utc_iso(due_close)))
            continue
        if desc["source_max_trade_date"] < due:
            result.missing.append(fid)
            result.gaps.append(
                make_gap("outcome_missing", [fid], retryable=True, detail=f"源水位 {desc['source_max_trade_date']} 未到 {due}")
            )
            continue
        case = forecast["case"]
        row = outcome_source.lookup(
            entity_type=case["entity_type"], entity_id=case["entity_id"], as_of=case["as_of"], horizon=int(case["horizon"])
        )
        if row is None or row.get("status") in (None, "missing", "pending", "pending_window"):
            result.missing.append(fid)
            result.gaps.append(make_gap("outcome_missing", [fid], retryable=True, detail="到期但源无有效行"))
            continue
        if row.get("status") != "ok":
            status, value, reason = "invalid", None, f"source_status:{row.get('status')}"
        else:
            verdict = outcome_predicate(spec, row.get("metric_value"))
            if verdict is None:
                status, value, reason = "invalid", None, "non_finite_metric"
            else:
                status, value, reason = "settled", int(verdict), None
        computed_at = row.get("computed_at")
        available_at = parse_ts(computed_at, field_name="computed_at") if computed_at is not None else due_close
        if available_at > now:
            result.pending.append(fid)
            result.gaps.append(make_gap("future_not_due", [fid], retryable=True, next_check_at=utc_iso(available_at), detail="源行可用时刻晚于 now"))
            continue
        metric_value = row.get("metric_value")
        observation: dict[str, Any] = {
            "schema_version": SCHEMA_OBSERVATION,
            "owner_user_id": protocol["owner_user_id"],
            "study_id": protocol["study_id"],
            "forecast_id": fid,
            "case_id": forecast["case_id"],
            "observed_at": utc_iso(now),
            "available_at": utc_iso(available_at),
            "due": due,
            "source_refs": source_refs,
            "value": value,
            "status": status,
            "metric_value": (float(metric_value) if status == "settled" else None),
            "reason": reason,
        }
        observation["id"] = observation_identity(observation)
        if latest is not None and latest["status"] == "settled" and status == "settled" and latest["value"] == value:
            result.unchanged.append(fid)
            continue
        stored, created = repository.append_observation(observation)
        if not created:
            result.unchanged.append(fid)
            continue
        if status == "invalid":
            result.invalid.append(stored)
        elif latest is not None and latest["status"] == "settled":
            result.revised.append(stored)
        else:
            result.settled.append(stored)
    return result


# --------------------------------------------------------------------------- #
# 6. 曝光（放在评估之前定义：评估要先登记曝光）
# --------------------------------------------------------------------------- #
def record_exposure(
    *,
    owner: str,
    repository: Repository,
    now: Any,
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
    """原子登记一次对底层结果的访问。同 operation_id 同意图 → 返回首次原件；异意图 → ConflictError。"""
    owner, repository, now = _guard(owner, repository, now)
    intent = build_exposure_intent(
        owner=owner,
        operation_id=operation_id,
        lineage_id=lineage_id,
        study_id=study_id,
        framework_hash=framework_hash,
        window=window,
        case_manifest_hash=case_manifest_hash,
        outcome_identities=outcome_identities,
        stage=stage,
        actor=actor,
        reason=reason,
    )
    record = {**intent, "id": digest(intent), "accessed_at": utc_iso(now)}
    stored, created = repository.publish_exposure(record)
    if not created and exposure_intent(stored) != intent:
        raise ConflictError(
            f"operation_id={operation_id} 已被另一意图占用（stage={stored['stage']}, actor={stored['actor']}）：不得趁未写完重占"
        )
    return stored


def foreign_exposures(repository: Repository, protocol: Mapping[str, Any]) -> list[dict[str, Any]]:
    """对本 study 而言「外来」的曝光：任何**不是本 study 自己写的**访问，以及来源未知的访问。

    同方法重试由「同 study_id 重新 evaluate」承接（同意图返回原件），所以一个**新** study——
    哪怕同谱系同框架——只要碰到已被别的 study 看过的事实，就是在已见样本上再做一次
    确认检验（只留赢家 / 事后挑窗都长这样），一律 holdout_exposed。改 study_id / lineage_id /
    case 别名 / 谓词阈值都不改变底层结果身份，洗不白。
    """
    out: list[dict[str, Any]] = []
    for exposure in repository.list_exposures():
        if exposure["study_id"] == protocol["study_id"] and exposure["actor"] not in UNKNOWN_ACTORS:
            continue
        out.append(exposure)
    return out


def exposed_case_ids(
    protocol: Mapping[str, Any], cases: Mapping[str, Mapping[str, Any]], exposures: Sequence[Mapping[str, Any]]
) -> dict[str, list[str]]:
    """case_id → 命中的曝光 operation_id 列表（按真实实体 + 结果区间匹配，不看 case 名）。"""
    hits: dict[str, list[str]] = {}
    for case_id, case in cases.items():
        identity = outcome_identity(
            entity_type=case["entity_type"],
            entity_id=case["entity_id"],
            as_of=case["as_of"],
            outcome_due=case["outcome_due"],
            horizon=int(case["horizon"]),
        )
        for exposure in exposures:
            if any(identities_overlap(identity, x) for x in exposure["outcome_identities"]):
                hits.setdefault(case_id, []).append(exposure["operation_id"])
    return hits


# --------------------------------------------------------------------------- #
# 4. 评估
# --------------------------------------------------------------------------- #
def _forecast_state(forecast: Mapping[str, Any], latest: Mapping[str, Any] | None, now: Any) -> str:
    if latest is not None and latest["status"] == "settled":
        return "settled"
    if latest is not None and latest["status"] == "invalid":
        return "invalid"
    return "pending" if now < market_close(forecast["outcome_due"]) else "missing"


def evaluate_study(
    *, owner: str, repository: Repository, now: Any, study_id: str, actor: str = EVALUATE_ACTOR
) -> dict[str, Any]:
    owner, repository, now = _guard(owner, repository, now)
    protocol = _load(owner, repository, study_id)
    policy = protocol["analysis_policy"]
    forecasts = repository.list_forecasts(protocol["study_id"])
    arm_ids = [a["arm_id"] for a in protocol["arms"]]
    origin_by_arm = {a["arm_id"]: a for a in protocol["arms"]}

    # 每条预测的当前状态与最新观察
    states: dict[str, str] = {}
    latest_obs: dict[str, Mapping[str, Any] | None] = {}
    correction_replay = False
    for f in forecasts:
        observations = repository.list_observations(protocol["study_id"], f["id"])
        settled_count = sum(1 for o in observations if o["status"] == "settled")
        if settled_count > 1:
            correction_replay = True
        latest = _latest_observation(observations)
        latest_obs[f["id"]] = latest
        states[f["id"]] = _forecast_state(f, latest, now)

    cases: dict[str, dict[str, Any]] = {}
    for f in forecasts:
        case = cases.setdefault(f["case_id"], {**f["case"], "forecasts": {}})
        case["forecasts"][f["arm_id"]] = f

    # 读结果前先登记本次曝光（同意图重试返回原件）
    settled_identities = []
    seen_identity: set[str] = set()
    for f in forecasts:
        if states[f["id"]] != "settled":
            continue
        ident = outcome_identity(
            entity_type=f["case"]["entity_type"],
            entity_id=f["case"]["entity_id"],
            as_of=f["case"]["as_of"],
            outcome_due=f["case"]["outcome_due"],
            horizon=int(f["case"]["horizon"]),
        )
        if ident["identity"] not in seen_identity:
            seen_identity.add(ident["identity"])
            settled_identities.append(ident)
    case_manifest_hash = digest(sorted(cases))
    settled_manifest_hash = digest(sorted(seen_identity))
    window = {"start": protocol["forward_start"], "end": protocol["evaluation_end"]}
    # operation_id 必须由**整份意图**决定，否则「意图变了」会伪装成「别人占了同一个 id」。
    # 只算 study + 已结算集合时，逐日登记（case 集合变、settled 仍为空）会撞同一个 id 却带
    # 不同 case_manifest_hash → ConflictError，把正常使用路径判成重占（评审 RV1）。
    # 这里逐字段覆盖 build_exposure_intent 的全部身份输入：settled_manifest_hash 是
    # outcome_identities 的无损摘要（identity 本身就是整条身份的 sha256），reason 在本调用点是常量。
    operation_id = digest(
        {
            "kind": "evaluate",
            "lineage_id": protocol["lineage_id"],
            "study_id": protocol["study_id"],
            "framework_hash": protocol["framework_hash"],
            "window": window,
            "case_manifest_hash": case_manifest_hash,
            "settled": settled_manifest_hash,
            "stage": "evaluate",
            "actor": actor,
        }
    )
    exposure = record_exposure(
        owner=owner,
        repository=repository,
        now=now,
        operation_id=operation_id,
        lineage_id=protocol["lineage_id"],
        study_id=protocol["study_id"],
        framework_hash=protocol["framework_hash"],
        window=window,
        case_manifest_hash=case_manifest_hash,
        outcome_identities=settled_identities,
        stage="evaluate",
        actor=actor,
        reason="evaluate_study reads settled outcomes",
    )

    gaps: list[Gap] = []
    eligibility_reasons: list[str] = []
    foreign = foreign_exposures(repository, protocol)
    exposed = exposed_case_ids(protocol, cases, foreign)
    if exposed:
        eligibility_reasons.append("holdout_exposed")
        gaps.append(
            make_gap(
                "holdout_exposed",
                sorted(exposed),
                detail="以下 case 的底层结果已被其他方法 / 谱系 / 未知来源访问过；换名、换 study、换阈值均不能洗白",
            )
        )
    if not policy["exposure_ledger_complete"]:
        eligibility_reasons.append("exposure_unknown")
        gaps.append(
            make_gap(
                "exposure_unknown",
                [protocol["study_id"]],
                detail="曝光台账未被 06 认证为完整：外部 / 人工访问历史未知 → exploratory，不能靠声明证明未见",
            )
        )
    for f in forecasts:
        if f["isolation_verified"] is False:
            if "isolation_unverified" not in eligibility_reasons:
                eligibility_reasons.append("isolation_unverified")
            gaps.append(make_gap("isolation_unverified", [f["id"]], detail="runner 记录的实际 projection 含臂外字段或残留派生量"))
    for gap_code in ("unverified_pit",):
        refs = [f["id"] for f in forecasts if f["pit_grade"] == "unverified"]
        if refs:
            gaps.append(make_gap(gap_code, refs, detail="无可验证 PIT 收据；不能声明严格时点可知"))

    # holdout_exposed 这里指「排除在确认性声明之外」的 case 数；描述性读数仍包含它们。
    excluded_counts: dict[str, int] = {"future_not_due": 0, "outcome_missing": 0, "invalid": 0, "holdout_exposed": 0}
    for f in forecasts:
        st = states[f["id"]]
        if st == "pending":
            excluded_counts["future_not_due"] += 1
            gaps.append(make_gap("future_not_due", [f["id"]], retryable=True, next_check_at=utc_iso(market_close(f["outcome_due"]))))
        elif st == "missing":
            excluded_counts["outcome_missing"] += 1
            gaps.append(make_gap("outcome_missing", [f["id"]], retryable=True))
        elif st == "invalid":
            excluded_counts["invalid"] += 1
    for case_id in exposed:
        excluded_counts["holdout_exposed"] += 1

    evaluation_end_reached = now >= market_close(protocol["evaluation_end"])
    pending_total = excluded_counts["future_not_due"]
    # 唯一的封存闸门：期末到达且无未到期预测才跑一次确认检验。comparison 与 calibration
    # 共用它——评审 RV3 正是因为两处各写一份条件、只有一处生效。
    confirmatory_test_run = bool(evaluation_end_reached and pending_total == 0)

    readouts: list[dict[str, Any]] = []
    for comparison in protocol["comparisons"]:
        base_id, cand_id = comparison["base_arm_id"], comparison["candidate_arm_id"]
        pairs: list[PairSample] = []
        items: list[dict[str, Any]] = []
        excluded: dict[str, int] = {"arm_missing": 0, "future_not_due": 0, "outcome_missing": 0, "invalid": 0}
        human_both = 0
        exposed_pairs = 0
        for case_id in sorted(cases):
            case = cases[case_id]
            fb, fc = case["forecasts"].get(base_id), case["forecasts"].get(cand_id)
            if fb is None or fc is None:
                excluded["arm_missing"] += 1
                continue
            if case_id in exposed:
                # 已暴露的事实仍可**描述**（数字就是数字），但不能进入确认性声明；
                # 计数如实报出，eligible=false 由 study 级判定承担。
                exposed_pairs += 1
            sb, sc = states[fb["id"]], states[fc["id"]]
            if "pending" in (sb, sc):
                excluded["future_not_due"] += 1
                continue
            if "missing" in (sb, sc):
                excluded["outcome_missing"] += 1
                continue
            if "invalid" in (sb, sc):
                excluded["invalid"] += 1
                continue
            ob, oc = latest_obs[fb["id"]], latest_obs[fc["id"]]
            assert ob is not None and oc is not None
            if ob["value"] != oc["value"]:
                excluded["invalid"] += 1
                gaps.append(make_gap("version_mismatch", [fb["id"], fc["id"]], detail="同 case 两臂结算值不同：结果源不一致"))
                continue
            if fb["origin"] == "human_manual" and fc["origin"] == "human_manual":
                human_both += 1
            y = int(ob["value"])
            pairs.append(
                PairSample(
                    case_id=case_id,
                    entity_id=case["entity_id"],
                    trade_date=case["as_of"],
                    p_base=float(fb["p"]),
                    p_candidate=float(fc["p"]),
                    y=y,
                )
            )
            items.append(
                {
                    "case_id": case_id,
                    "trade_date": case["as_of"],
                    "brier_base": (float(fb["p"]) - y) ** 2,
                    "brier_candidate": (float(fc["p"]) - y) ** 2,
                }
            )
        coverage = {
            arm: {
                "answered": sum(1 for c in cases.values() if arm in c["forecasts"]),
                "total_cases": len(cases),
            }
            for arm in (base_id, cand_id)
        }
        days: list[DailyDelta] = daily_deltas(pairs)
        readout = paired_readout(days, policy=policy, comparison_id=comparison["comparison_id"])
        readout.update(
            {
                "base_arm_id": base_id,
                "candidate_arm_id": cand_id,
                "claim_kind": comparison["claim_kind"],
                "confirmatory": comparison["confirmatory"],
                "n_cases_total": len(cases),
                "n_pairs": len(pairs),
                "holdout_exposed_pairs": exposed_pairs,
                "excluded": excluded,
                "coverage": coverage,
                "items": items,
                "descriptive_only": False,
                "verdict_if_eligible": readout["verdict"],
            }
        )
        if human_both:
            readout["descriptive_only"] = True
            readout["notes"].append(f"{human_both} 个配对两臂都是人工概率：先看 full 再填删轨可能记得答案，仅描述")
            if comparison["confirmatory"] and "descriptive_only" not in eligibility_reasons:
                eligibility_reasons.append("descriptive_only")
                gaps.append(make_gap("descriptive_only", [comparison["comparison_id"]]))
        if comparison["confirmatory"] and (coverage[base_id]["answered"] == 0 or coverage[cand_id]["answered"] == 0):
            if "arm_missing" not in eligibility_reasons:
                eligibility_reasons.append("arm_missing")
            gaps.append(make_gap("arm_missing", [comparison["comparison_id"]], detail="主比较有臂没有任何预测"))
        if not confirmatory_test_run:
            # 期末未到：累计评分封存，只报 pending 数与单项
            for key in ("mean_brier_base", "mean_brier_candidate", "mean_brier_difference_descriptive", "independent", "dependence", "verdict", "verdict_if_eligible"):
                readout[key] = None
            readout["wins"] = readout["losses"] = readout["ties"] = None
            readout["daily"] = []
            readout["gaps"] = [g for g in readout["gaps"] if g["code"] not in ("no_pairs", "ties_test_not_defined", "insufficient_n", "insufficient_blocks")]
            readout["status"] = "pending"
            readout["pending_forecasts"] = pending_total
            readout["notes"].append(
                "evaluation_end 未到或仍有未到期预测：确认检验封存，只报 pending 数与单项"
                if not evaluation_end_reached
                else "仍有未到期预测：确认检验封存"
            )
        elif not comparison["confirmatory"] or readout["descriptive_only"] or eligibility_reasons:
            if readout["status"] not in ("insufficient",):
                readout["status"] = "descriptive"
            readout["verdict"] = None
        readouts.append(readout)

    primary = next(r for r in readouts if r["comparison_id"] == protocol["primary_comparison_id"])
    eligible = not eligibility_reasons
    empirical_status = primary["status"]
    if empirical_status in ("supported", "refuted", "not_distinguishable") and not eligible:
        empirical_status = "descriptive"

    # 期末未到（或仍有未到期预测）时，comparison 已封存累计评分；calibration 必须一起封存，
    # 否则两臂的 mean_brier / 桶频率就是同一份累计表现的另一个出口，能直接推回累计改善（评审 RV3）。
    # 允许保留的是 spec 03 §7 明说的「pending 数与单项」：n_settled、桶计数、口径标签。
    calibration: dict[str, Any] = {}
    for arm in arm_ids:
        samples = [
            (float(f["p"]), int(latest_obs[f["id"]]["value"]))  # type: ignore[index]
            for f in forecasts
            if f["arm_id"] == arm and states[f["id"]] == "settled"
        ]
        buckets = calibration_buckets(samples, min_n=int(policy["calibration_min_n"]))
        mean_brier = (sum((p - y) ** 2 for p, y in samples) / len(samples)) if samples else None
        if not confirmatory_test_run:
            mean_brier = None
            for bucket in buckets:
                bucket["mean_p"] = None
                bucket["observed_rate"] = None
                bucket["reason"] = SEALED_UNTIL_END
        calibration[arm] = {
            "n_settled": len(samples),
            "mean_brier": mean_brier,
            "sealed": not confirmatory_test_run,
            "sealed_reason": None if confirmatory_test_run else SEALED_UNTIL_END,
            "buckets": buckets,
            "origins": sorted({f["origin"] for f in forecasts if f["arm_id"] == arm}),
            "pit_grades": sorted({f["pit_grade"] for f in forecasts if f["arm_id"] == arm}),
            "recipe_id": origin_by_arm[arm]["recipe_id"],
        }

    sample_manifest = sorted(
        (f["case_id"], f["arm_id"], f["id"], (latest_obs[f["id"]] or {}).get("id"), states[f["id"]]) for f in forecasts
    )
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_RECEIPT,
        "owner_user_id": protocol["owner_user_id"],
        "visibility": "private",
        "study_id": protocol["study_id"],
        "lineage_id": protocol["lineage_id"],
        "protocol_hash": protocol["study_id"],
        "framework_hash": protocol["framework_hash"],
        "generated_at": utc_iso(now),
        "as_of_now": market_day(now),
        "source_hashes": protocol["source_hashes"],
        "version_hashes": protocol["version_hashes"],
        "mode": protocol["mode"],
        "empirical_status": empirical_status,
        "eligible": eligible,
        "eligibility_reasons": eligibility_reasons,
        "evaluation_end": protocol["evaluation_end"],
        "evaluation_end_reached": evaluation_end_reached,
        "confirmatory_test_run": confirmatory_test_run,
        "pending_gaps": [g.to_dict() for g in gaps],
        "excluded_counts": excluded_counts,
        "counts": {
            "forecasts": len(forecasts),
            "cases": len(cases),
            "settled": sum(1 for s in states.values() if s == "settled"),
            "pending": sum(1 for s in states.values() if s == "pending"),
            "missing": sum(1 for s in states.values() if s == "missing"),
            "invalid": sum(1 for s in states.values() if s == "invalid"),
        },
        "sample_manifest_hash": digest(sample_manifest),
        "comparison_readouts": readouts,
        "calibration": calibration,
        "outcome_receipt_refs": sorted({o["id"] for o in latest_obs.values() if o is not None}),
        "settled_outcome_identities": settled_identities,
        "exposure_receipt_ref": exposure["id"],
        "correction_replay": correction_replay,
        "tags": protocol["tags"],
        "synthetic": "synthetic" in protocol["tags"],
        "decision_eligible": False,
        "promotion_eligible": False,
    }
    receipt["id"] = receipt_identity(receipt)
    stored, _created = repository.publish_receipt(receipt)
    return stored


# --------------------------------------------------------------------------- #
# 5. 读收据
# --------------------------------------------------------------------------- #
def read_receipt(
    *,
    owner: str,
    repository: Repository,
    now: Any,
    study_id: str,
    receipt_id: str | None = None,
    actor: str = "research_validation.read_receipt",
) -> dict[str, Any] | None:
    """读收据前先登记曝光（收据里有已结算结果）；没有收据返回 None，不伪造。"""
    owner, repository, now = _guard(owner, repository, now)
    protocol = _load(owner, repository, study_id)
    receipts = repository.list_receipts(protocol["study_id"])
    if not receipts:
        return None
    if receipt_id is not None:
        validate_content_id(receipt_id, field_name="receipt_id")
        matches = [r for r in receipts if r["id"] == receipt_id]
        if not matches:
            raise ContractError(f"receipt {receipt_id} 不存在")
        receipt = matches[0]
    else:
        receipt = receipts[-1]
    if receipt["settled_outcome_identities"]:
        record_exposure(
            owner=owner,
            repository=repository,
            now=now,
            operation_id=digest({"kind": "read_receipt", "receipt_id": receipt["id"], "actor": actor}),
            lineage_id=protocol["lineage_id"],
            study_id=protocol["study_id"],
            framework_hash=protocol["framework_hash"],
            window={"start": protocol["forward_start"], "end": protocol["evaluation_end"]},
            case_manifest_hash=None,
            outcome_identities=receipt["settled_outcome_identities"],
            stage="read_receipt",
            actor=actor,
            reason=f"read receipt {receipt['id']}",
        )
    return receipt


__all__ = [
    "EVALUATE_ACTOR",
    "OutcomeSource",
    "PitVerifier",
    "RegisterResult",
    "SettleResult",
    "evaluate_study",
    "exposed_case_ids",
    "foreign_exposures",
    "freeze_study",
    "read_receipt",
    "record_exposure",
    "register_forecasts",
    "settle_outcomes",
]

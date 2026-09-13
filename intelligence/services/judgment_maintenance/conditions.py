"""确定性条件：编译复用情景树编译器，判定用三值逻辑（spec 01 §4 第 2、3 条）。

- 只有 ``{"all": [谓词...]}`` 且每个谓词落在注册标签白名单（``river_derive.SLICE_EVALUABLE_LABELS``）
  的条件能出 true / false；自然语言、冻结模型散文、``otherwise`` 一律拒绝，不强转二值。
- 判定只看冻结观测（``ConditionObservation``），不取数、不写回；缺观测 / 值为 null → unknown。
- 合取用 Kleene 三值：任一谓词为 false 则整体 false；否则任一 unknown 则 unknown；全 true 才 true。
  这与 ``scenario_trees.resolve`` 遇到第一个 None 就停的写法不同——那里停是「树不再往前走」，
  这里要回答的是「条件是否触发」，已知的 false 不该被另一条缺原料的谓词掩成 unknown。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intelligence.services import scenario_trees as st
from intelligence.services.judgment_maintenance.contracts import (
    BindingCondition,
    ConditionObservation,
    Gap,
    MaintenanceContractError,
    day_of,
    stamp_grade,
    weakest_pit,
)

ObservationIndex = dict[tuple[str, str, str], list[ConditionObservation]]


def compile_binding_condition(cond: BindingCondition, *, where: str) -> tuple[st.Predicate, ...]:
    """绑定条件 → 谓词合取；编译不过就抛 ``MaintenanceContractError``（拒绝，不降级成 unknown）。"""
    expr = cond.expression
    if isinstance(expr, str):
        raise MaintenanceContractError(
            "condition_not_deterministic",
            f"{where}.expression",
            "字符串不是确定性条件：自然语言 / 模型散文 / otherwise 都不能被判为 true 或 false",
        )
    compiled, rejections = st.compile_condition(expr, where=f"{where}.expression")
    if rejections or not isinstance(compiled, tuple) or not compiled:
        detail = "; ".join(f"{r.code}@{r.where}: {r.detail}" for r in rejections) or "条件形状必须是 {\"all\": [谓词...]}"
        raise MaintenanceContractError("condition_not_compilable", f"{where}.expression", detail)
    return compiled


def index_observations(observations: list[ConditionObservation]) -> ObservationIndex:
    index: ObservationIndex = {}
    for obs in observations:
        index.setdefault((obs.label, obs.entity_id, obs.as_of), []).append(obs)
    return index


@dataclass(frozen=True)
class PredicateReading:
    label: str
    op: str
    value: Any
    entity_id: str
    observed: Any
    result: str
    source_ref: str | None = None
    recorded_at: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "op": self.op,
            "value": list(self.value) if isinstance(self.value, tuple) else self.value,
            "entity_id": self.entity_id,
            "observed": self.observed,
            "result": self.result,
            "source_ref": self.source_ref,
            "recorded_at": self.recorded_at,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ConditionEvaluation:
    result: str
    readings: tuple[PredicateReading, ...]
    gaps: tuple[Gap, ...]
    pit_grade: str

    def to_dict(self) -> dict[str, Any]:
        return {"result": self.result, "readings": [r.to_dict() for r in self.readings]}


def _tri(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "true" if value else "false"


def evaluate_condition(
    preds: tuple[st.Predicate, ...],
    cond: BindingCondition,
    index: ObservationIndex,
    *,
    as_of: str,
    knowledge_cutoff: str,
    hindsight: bool,
    binding_id: str,
) -> ConditionEvaluation:
    readings: list[PredicateReading] = []
    gaps: list[Gap] = []
    grades: list[str] = ["trade_date_only" if hindsight else "strict"]
    for pred in preds:
        candidates = index.get((pred.label, cond.entity_id, as_of), [])
        # 先按知识截止过滤：recorded_at 晚于截止的观测「当时还不知道」；没有 recorded_at 的只能按交易日放置。
        known: list[ConditionObservation] = []
        for obs in candidates:
            if obs.recorded_at is not None and day_of(obs.recorded_at) > knowledge_cutoff:
                continue
            known.append(obs)
        base = dict(label=pred.label, op=pred.op, value=pred.value, entity_id=cond.entity_id)
        if not known:
            readings.append(PredicateReading(**base, observed=None, result="unknown", reason="no_observation"))
            gaps.append(
                Gap(
                    reason="condition_unknown",
                    ref=None,
                    checked_at=knowledge_cutoff,
                    retryable=True,
                    detail=f"标签 {pred.label} 在 {as_of}（实体 {cond.entity_id or 'market'}）截止 {knowledge_cutoff} 无观测",
                    binding_id=binding_id,
                    condition_ref=cond.condition_id,
                )
            )
            continue
        mismatched = [o for o in known if cond.label_version and o.label_version and o.label_version != cond.label_version]
        if mismatched:
            readings.append(PredicateReading(**base, observed=None, result="unknown", reason="label_version_mismatch"))
            gaps.append(
                Gap(
                    reason="label_version_mismatch",
                    ref=mismatched[0].source_ref,
                    checked_at=knowledge_cutoff,
                    retryable=False,
                    detail=f"条件按 {cond.label_version} 登记，观测标签版本为 {mismatched[0].label_version}",
                    binding_id=binding_id,
                    condition_ref=cond.condition_id,
                )
            )
            continue
        distinct = {o.value for o in known}
        if len(distinct) > 1:
            readings.append(PredicateReading(**base, observed=sorted(distinct, key=str), result="unknown", reason="ambiguous_observation"))
            gaps.append(
                Gap(
                    reason="ambiguous_observation",
                    ref=None,
                    checked_at=knowledge_cutoff,
                    retryable=True,
                    detail=f"标签 {pred.label} 在 {as_of} 有多个不同观测值，不择其一",
                    binding_id=binding_id,
                    condition_ref=cond.condition_id,
                )
            )
            continue
        obs = sorted(known, key=lambda o: (o.recorded_at or "", o.source_ref or ""))[-1]
        verdict = st.eval_predicate(pred, obs.value)
        result = _tri(verdict)
        if result == "unknown":
            gaps.append(
                Gap(
                    reason="condition_unknown",
                    ref=obs.source_ref,
                    checked_at=knowledge_cutoff,
                    retryable=True,
                    detail=f"标签 {pred.label} 在 {as_of} 的观测值为空或不可比",
                    binding_id=binding_id,
                    condition_ref=cond.condition_id,
                )
            )
        # 与证据版本同一把尺子：观测的 recorded_at 也按实际精度定档，纯日期不冒充严格回放。
        # 完全没有 recorded_at 时仍按交易日放置（as_of 本身可信），维持既有的 trade_date_only。
        grades.append(stamp_grade(obs.recorded_at) if obs.recorded_at else "trade_date_only")
        readings.append(
            PredicateReading(
                **base,
                observed=obs.value,
                result=result,
                source_ref=obs.source_ref,
                recorded_at=obs.recorded_at,
                reason=None if result != "unknown" else "value_missing",
            )
        )
    results = [r.result for r in readings]
    if "false" in results:
        overall = "false"
    elif "unknown" in results:
        overall = "unknown"
    else:
        overall = "true"
    pit = "unverifiable" if overall == "unknown" else weakest_pit(grades)
    return ConditionEvaluation(result=overall, readings=tuple(readings), gaps=tuple(gaps), pit_grade=pit)


__all__ = [
    "ConditionEvaluation",
    "ObservationIndex",
    "PredicateReading",
    "compile_binding_condition",
    "evaluate_condition",
    "index_observations",
]

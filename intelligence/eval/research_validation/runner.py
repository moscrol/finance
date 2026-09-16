"""消融离线 runner（spec 03 §6）：冻结 manifest → 每臂桶概率 → 逐 case projection → 登记。

两步走，因为基准是协议的语义字段：

1. ``build_protocol_input``：从旁路库取冻结日历、版本、发现窗基准（事件臂规则），
   拼出 ``freeze_study`` 的输入体；
2. ``run_ablation``：读已冻结协议，在**结果窗**里枚举事件 case，对每个臂用白名单 recipe
   算 p，记录实际 projection / hash / 隔离核验，调用 ``register_forecasts``。

测量对象是「规则 + 信息配置」，不是纯因果效应。删轨臂的规则只允许比 base 少谓词；
projection 里出现臂外字段或删轨派生量 → ``isolation_verified=False``（service 据此 eligible=false）。
覆盖率（每臂答了多少 case）如实进 summary，少答难题不能隐去。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from intelligence.services.methodology_backtest.rules import Rule
from intelligence.services.research_validation.baseline import OutcomeRow, compute_baseline
from intelligence.services.research_validation.contracts import (
    ContractError,
    digest,
    market_close,
    utc_iso,
)
from intelligence.services.research_validation.repository import Repository
from intelligence.services.research_validation.service import RegisterResult, register_forecasts

from .recipes import resolve_recipe
from .rule_two_bucket import (
    LabelSnapshot,
    arm_rule,
    bucket_probabilities_for_rule,
    evaluate_condition,
    load_snapshot,
    outcome_value,
    rule_diff,
)

DEFAULT_RECIPE_ID = "rule_two_bucket/v1"


def _result_windows(protocol: Mapping[str, Any]) -> list[dict[str, str]]:
    windows = [w for w in (protocol.get("validation_window"), protocol.get("holdout_window")) if w]
    if not windows:
        windows = [{"start": protocol["forward_start"], "end": protocol["evaluation_end"]}]
    clipped = []
    for w in windows:
        start = max(w["start"], protocol["forward_start"])
        end = min(w["end"], protocol["evaluation_end"])
        if start <= end:
            clipped.append({"start": start, "end": end})
    return clipped


def build_protocol_input(*, labels_db: str | Path, draft: Mapping[str, Any]) -> dict[str, Any]:
    """补齐 calendar / baseline_spec / version_hashes / source_hashes；其余字段原样透传给 freeze_study 校验。"""
    if not isinstance(draft, Mapping):
        raise ContractError("draft 必须是对象")
    outcome_spec = draft.get("outcome_spec") or {}
    horizon = int(outcome_spec.get("horizon", 5))
    metric = str(outcome_spec.get("metric", "fwd_return"))
    discovery = draft.get("discovery_window") or {}
    event_spec = draft.get("event_spec") or {}
    arms = {a.get("arm_id"): a for a in (draft.get("arms") or []) if isinstance(a, Mapping)}
    if event_spec.get("kind") != "rule" or event_spec.get("arm_id") not in arms:
        raise ContractError("runner 首版只支持 event_spec{kind=rule, arm_id=<带规则的臂>}")
    event_rule = arm_rule(arms[event_spec["arm_id"]])
    snapshot = load_snapshot(
        labels_db,
        entity_type=event_rule.entity_type,
        start=discovery["start"],
        end=draft.get("evaluation_end") or discovery["end"],
        horizon=horizon,
        metric=metric,
    )
    rows: list[OutcomeRow] = []
    for day, entities in snapshot.universe.items():
        if not discovery["start"] <= day <= discovery["end"]:
            continue
        for entity_id in entities:
            condition, _ = evaluate_condition(event_rule.predicates, snapshot=snapshot, entity_id=entity_id, day=day)
            if condition is True:
                rows.append(OutcomeRow(entity_id, day, outcome_value(snapshot, outcome_spec, entity_id, day)))
    baseline = compute_baseline(
        rows,
        window={"start": discovery["start"], "end": discovery["end"]},
        calendar=snapshot.calendar,
        horizon=horizon,
        source_hash=snapshot.source_hash,
    )
    body = dict(draft)
    body["calendar"] = list(snapshot.calendar.dates)
    body["baseline_spec"] = baseline
    body["version_hashes"] = {**snapshot.version_hashes, **dict(draft.get("version_hashes") or {})}
    body["source_hashes"] = {"labels_db": snapshot.source_hash, **dict(draft.get("source_hashes") or {})}
    body.setdefault("mode", "historical_rule")
    return body


def _isolation(arm: Mapping[str, Any], projection: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """实际读到的字段必须 ⊆ allowed_fields，且不含删轨字段 / 派生量。"""
    allowed = set(arm.get("allowed_fields") or [])
    removed = arm.get("removed_track") or {}
    banned = set(removed.get("fields") or []) | set(removed.get("derived_fields") or [])
    leaks: list[str] = []
    for key in projection:
        label = key.split(":", 1)[1].split("@", 1)[0]
        if label not in allowed or label in banned:
            leaks.append(key)
    return (not leaks), sorted(leaks)


def run_ablation(
    *,
    owner: str,
    repository: Repository,
    now: Any,
    study_id: str,
    labels_db: str | Path,
    forecast_actor: str = "eval.research_validation.runner",
) -> dict[str, Any]:
    protocol = repository.load_protocol(study_id)
    if protocol["mode"] != "historical_rule":
        raise ContractError(f"runner 只跑 historical_rule 协议，得到 {protocol['mode']}")
    outcome_spec = protocol["outcome_spec"]
    event_arm = next(a for a in protocol["arms"] if a["arm_id"] == protocol["event_spec"]["arm_id"])
    event_rule = arm_rule(event_arm)
    snapshot = load_snapshot(
        labels_db,
        entity_type=event_rule.entity_type,
        start=protocol["discovery_window"]["start"],
        end=protocol["evaluation_end"],
        horizon=int(outcome_spec["horizon"]),
        metric=str(outcome_spec["metric"]),
    )
    mismatched = {
        k: (protocol["version_hashes"][k], snapshot.version_hashes[k])
        for k in protocol["version_hashes"]
        if k in snapshot.version_hashes and snapshot.version_hashes[k] != protocol["version_hashes"][k]
    }
    if mismatched:
        raise ContractError(f"旁路库版本与冻结协议不一致：{mismatched}", "version_mismatch")

    rules: dict[str, Rule] = {}
    buckets: dict[str, dict[str, Any]] = {}
    diffs: dict[str, Any] = {}
    for arm in protocol["arms"]:
        if arm["rule"] is None:
            continue
        rule = arm_rule(arm)
        rules[arm["arm_id"]] = rule
        buckets[arm["arm_id"]] = bucket_probabilities_for_rule(
            rule, snapshot=snapshot, window=protocol["discovery_window"], outcome_spec=outcome_spec
        )
    base_ids = [a["arm_id"] for a in protocol["arms"] if a["role"] in ("base", "full")]
    for arm_id, rule in rules.items():
        for base_id in base_ids:
            if base_id != arm_id and base_id in rules:
                diffs[f"{base_id}->{arm_id}"] = rule_diff(rules[base_id], rule)

    cases: list[tuple[str, str]] = []
    for window in _result_windows(protocol):
        for day, entities in snapshot.universe.items():
            if not window["start"] <= day <= window["end"]:
                continue
            for entity_id in entities:
                condition, _ = evaluate_condition(event_rule.predicates, snapshot=snapshot, entity_id=entity_id, day=day)
                if condition is True:
                    cases.append((entity_id, day))
    cases.sort(key=lambda c: (c[1], c[0]))

    inputs: list[dict[str, Any]] = []
    coverage: dict[str, dict[str, Any]] = {}
    unknown_by_arm: dict[str, list[str]] = {}
    leaks_by_arm: dict[str, list[dict[str, Any]]] = {}
    for arm in protocol["arms"]:
        arm_id = arm["arm_id"]
        if arm_id not in rules:
            continue
        predict, recipe_hash = resolve_recipe(arm.get("recipe_id") or DEFAULT_RECIPE_ID)
        answered = 0
        for entity_id, day in cases:
            condition, fields = evaluate_condition(rules[arm_id].predicates, snapshot=snapshot, entity_id=entity_id, day=day)
            isolated, leaks = _isolation(arm, fields)
            if leaks:
                leaks_by_arm.setdefault(arm_id, []).append({"entity_id": entity_id, "as_of": day, "fields": leaks})
            bucket_p = {"true": buckets[arm_id]["true"]["p"], "false": buckets[arm_id]["false"]["p"]}
            projection = {"condition": condition, "fields": fields, "bucket_p": bucket_p}
            p = predict(projection)
            if p is None:
                unknown_by_arm.setdefault(arm_id, []).append(f"{entity_id}@{day}")
                continue
            answered += 1
            inputs.append(
                {
                    "entity_type": event_rule.entity_type,
                    "entity_id": entity_id,
                    "as_of": day,
                    "arm_id": arm_id,
                    "p": p,
                    "forecast_at": utc_iso(market_close(day)),
                    "origin": "deterministic",
                    "probability_recipe_hash": recipe_hash,
                    "projection_hash": digest(projection),
                    "input_refs": {"labels_db": snapshot.source_hash, **snapshot.version_hashes},
                    "isolation_verified": isolated,
                    "actor": forecast_actor,
                }
            )
        coverage[arm_id] = {
            "answered": answered,
            "total_cases": len(cases),
            "unknown_condition": len(unknown_by_arm.get(arm_id, [])),
            "leaks": len(leaks_by_arm.get(arm_id, [])),
        }

    result: RegisterResult = register_forecasts(
        owner=owner, repository=repository, now=now, study_id=protocol["study_id"], forecasts=inputs
    )
    return {
        "study_id": protocol["study_id"],
        "synthetic": "synthetic" in protocol["tags"],
        "n_cases": len(cases),
        "coverage": coverage,
        "buckets": buckets,
        "rule_diffs": diffs,
        "unknown_condition": unknown_by_arm,
        "isolation_leaks": leaks_by_arm,
        "register": result.to_dict(),
        "snapshot": {"labels_db": snapshot.labels_db, "source_hash": snapshot.source_hash, **snapshot.version_hashes},
    }


def snapshot_for(protocol: Mapping[str, Any], labels_db: str | Path) -> LabelSnapshot:
    event_arm = next(a for a in protocol["arms"] if a["arm_id"] == protocol["event_spec"]["arm_id"])
    rule = arm_rule(event_arm)
    return load_snapshot(
        labels_db,
        entity_type=rule.entity_type,
        start=protocol["discovery_window"]["start"],
        end=protocol["evaluation_end"],
        horizon=int(protocol["outcome_spec"]["horizon"]),
        metric=str(protocol["outcome_spec"]["metric"]),
    )


__all__ = ["DEFAULT_RECIPE_ID", "build_protocol_input", "run_ablation", "snapshot_for"]

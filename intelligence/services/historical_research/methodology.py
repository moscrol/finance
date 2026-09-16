"""Pure handoff to existing methodology rules; never creates evaluation evidence.

Window features and endpoint labels are different definitions. A caller must
author the existing Rule predicates explicitly; this module does not infer an
equivalence from the hypothesis text or silently rename a feature.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from intelligence.services.historical_research.research import ResearchCase
from intelligence.services.methodology_backtest.compiler import compile_rule
from intelligence.services.methodology_backtest.labels import LABEL_VERSION
from intelligence.services.methodology_backtest.lifecycle import derive_state
from intelligence.services.methodology_backtest.propose import build_rule_doc
from intelligence.services.methodology_backtest.rules import (
    RULE_ID_RE,
    RuleValidationError,
    validate_rule,
)

BRIDGE_VERSION = "historical-methodology-handoff-v1"

_MAPPING_NOTES = {
    "max_double_red_streak": (
        "window_max_is_not_endpoint_streak",
        "窗内最长双红不等于截至事件日连续双红；既有标签还处理全市场 data_gap，不能自动改名为 dual_red_streak。",
    ),
    "double_red_days": (
        "window_count_is_not_endpoint_label",
        "窗内双红计数不等于事件日 dual_red_strict；既有标签另有 data_gap 规则。",
    ),
    "return_pct": (
        "observation_return_is_not_forward_outcome",
        "观察窗累计涨幅不能充当前向收益条件标签；仅明确 D+1..D+h 结果口径可用既有 fwd_return。",
    ),
    "amount_ratio": (
        "missing_label_operator",
        "既有标签白名单没有实体观察窗末日/首日成交额比。",
    ),
    "advancer_share": (
        "missing_label_operator",
        "既有标签白名单没有逐日成员上涨占比均值。",
    ),
    "limit_up_share": ("missing_label_operator", "涨停占比不等于既有涨停热度名次。"),
    "first_surge_lag": (
        "missing_sequence_operator",
        "现有规则标签不表达成员首次大涨与板块首次双红的跨日先后差。",
    ),
    "market_relative_return_pct": (
        "missing_label_operator",
        "既有标签白名单没有观察窗实体与指数累计收益之差。",
    ),
}


def prepare_methodology_candidate(
    case: ResearchCase,
    hypothesis_id: str,
    *,
    owner: str,
    rule_id: str,
    entity_type: str,
    predicates: list[dict[str, Any]] | None = None,
    success: dict[str, Any] | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Prepare a private Rule document and compiler summary without IO.

    ``rule_id`` is a caller-supplied candidate identifier under the existing Rule
    contract, not an allocated experiment/R number. ``predicates`` and ``success``
    use the existing Rule schema. A valid formalization still requires review; no
    runner, receipt writer, registration, or lifecycle advancement is performed.
    """
    if not isinstance(case, ResearchCase):
        raise ValueError("case must be an authorized ResearchCase")
    if not isinstance(rule_id, str) or not RULE_ID_RE.fullmatch(rule_id):
        raise ValueError("rule_id must satisfy the existing candidate Rule contract")
    if type(version) is not int or version < 1:
        raise ValueError("version must be a positive integer")
    hypothesis = next(
        (h for h in case.hypotheses if h.hypothesis_id == hypothesis_id), None
    )
    if hypothesis is None:
        raise ValueError("hypothesis_id is not in the supplied ResearchCase")
    source_context = {
        "case_ref": f"{case.case_id}@r{case.revision}",
        "hypothesis_ref": f"{hypothesis.hypothesis_id}@v{hypothesis.version}",
        "case": case.to_dict(),
        "hypothesis": hypothesis.to_dict(),
    }
    mapping_notes = []
    for definition in hypothesis.feature_definitions:
        name = definition.split("@", 1)[0]
        code, message = _MAPPING_NOTES.get(
            name,
            (
                "no_declared_exact_mapping",
                "该定义没有在本桥声明与现有标签等价；需显式书写规则并审阅。",
            ),
        )
        mapping_notes.append(
            {"definition_ref": definition, "code": code, "message": message}
        )
    if entity_type == "stock":
        mapping_notes.append(
            {
                "code": "stock_universe_requires_review",
                "message": "既有 stock 评价器取 limit_high_union 全池；不等于研究中的显式股票名单。",
            }
        )
    result: dict[str, Any] = {
        "schema_version": BRIDGE_VERSION,
        "status": "unsupported_definition",
        "research_only": True,
        "decision_eligible": False,
        "promotion_eligible": False,
        "formalization_requires_review": True,
        "automatic_equivalence": False,
        "source_context": source_context,
        "mapping_notes": mapping_notes,
        "issues": [],
        "rule_doc": None,
        "compiled_summary": None,
        "lifecycle": None,
        "data_status": "not_checked",
        "required_inputs": [
            "reviewed_explicit_formalization",
            "history_labels",
            "history_outcomes",
            "history_calendar",
            "history_data_gaps",
            "history_build_meta",
            "matching_source_and_label_version",
            "complete_declared_rule_universe",
            "unexposed_validation_window",
            "certification_gate_for_any_promotion",
        ],
        "next_action": {
            "writer": "intelligence.services.methodology_backtest.propose.write_rule_file",
            "evaluator": "intelligence.services.methodology_backtest.runner.run_rule",
            "lifecycle_reader": "intelligence.services.methodology_backtest.lifecycle.derive_state",
            "automatic_execution": False,
            "instruction": "审阅显式规则和样本宇宙后，沿既有私人候选 writer/evaluator 接续；本产物不是收据，也不注册实验或改变方法状态。",
        },
    }
    issues = result["issues"]
    for field, value in (("predicates", predicates), ("success", success)):
        if value is None:
            issues.append(
                {
                    "path": field,
                    "code": "explicit_rule_required",
                    "message": "需显式提供现有 Rule 语法；不从自然语言或窗口特征自动猜定义。",
                }
            )
    if issues:
        issues.extend(mapping_notes)
    for definition in hypothesis.unresolved_definitions:
        issues.append(
            {
                "path": "hypothesis.unresolved_definitions",
                "code": "unresolved_definition",
                "message": definition,
            }
        )
    if hypothesis.status == "unsupported":
        issues.append(
            {
                "path": "hypothesis.status",
                "code": "unsupported_hypothesis",
                "message": "先保留来源修订假设，不能将 unsupported 原件当成已支持规则。",
            }
        )
    if issues:
        return result
    try:
        # Existing provenance kind=manual means explicit authoring here, never
        # human approval; the actual model/user origin stays in full context.
        doc, rule = build_rule_doc(
            rule_id=rule_id,
            version=version,
            title=hypothesis.statement[:200],
            entity_type=entity_type,
            predicates=predicates,
            success=success,
            sharing="private",
            owner=owner,
            source_perspective="历史研究候选：显式形式化，需审阅；不代表人工批准",
            provenance={
                "kind": "manual",
                "ref": f"{source_context['case_ref']}:{source_context['hypothesis_ref']}",
                "text": f"origin={hypothesis.origin}; explicit formalization, not equivalence or approval",
                "user": owner,
            },
            notes=json.dumps(
                source_context, ensure_ascii=False, sort_keys=True, allow_nan=False
            ),
        )
        # Freeze caller-owned lists and reject nonfinite JSON before handoff.
        doc = json.loads(json.dumps(doc, ensure_ascii=False, allow_nan=False))
        rule, errors = validate_rule(doc)
        if errors:
            raise RuleValidationError(errors)
        assert rule is not None
    except RuleValidationError as exc:
        issues.extend(
            {"path": e.path, "code": "unsupported_definition", "message": e.message}
            for e in exc.errors
        )
        return result
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        issues.append(
            {
                "path": "formalization",
                "code": "unsupported_definition",
                "message": str(exc),
            }
        )
        return result
    result["rule_doc"] = doc
    result["lifecycle"] = derive_state(doc, []).to_dict()
    result["required_inputs"].append(
        f"prebuilt_outcome_horizons:{','.join(map(str, rule.horizons))}"
    )
    result["candidate_scope"] = {
        "entity_type": rule.entity_type,
        "universe": rule.universe,
    }
    result["compiled_definition_refs"] = [
        f"{p.label}@{LABEL_VERSION}" for p in rule.predicates
    ]
    if case.window_start is None or case.window_end is None:
        result["status"] = "needs_data"
        result["required_inputs"].append("resolved_research_window")
        return result
    compiled = compile_rule(rule, start=case.window_start, end=case.window_end)
    result["compiled_summary"] = {
        "compiler": "intelligence.services.methodology_backtest.compiler.compile_rule",
        "window": {"start": case.window_start, "end": case.window_end},
        "predicate_count": len(rule.predicates),
        "baseline_kind": compiled.baseline_kind,
        "queries": {
            name: {
                "sql_sha256": hashlib.sha256(query.sql.encode()).hexdigest(),
                "parameters": list(query.params),
            }
            for name, query in (
                ("events", compiled.events),
                ("metrics", compiled.metrics),
            )
        },
        "evaluated": False,
    }
    result["status"] = "candidate_prepared"
    return result

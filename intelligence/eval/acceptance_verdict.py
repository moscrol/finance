"""Fail-closed verdicts for the 28-case product acceptance board.

The module is deliberately pure: callers provide a compiled case contract and a
serialized run, and receive immutable operational/truth/experience verdicts. It
does not call a model, database, knowledge base, or product runtime.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[2]
VERDICT_OVERLAY_PATH = (
    REPO / "intelligence/eval/cases/acceptance_verdict_contracts.json"
)

_KNOWN_CASE_FIELDS = frozenset(
    {
        "id",
        "tier",
        "query",
        "date",
        "followups",
        "pass_rule",
        "expect_tools",
        "must_mention",
        "expect_facts",
        "expect_entities",
        "expect_answer_set",
        "exact_set",
        "expect_refusal",
        "forbid_phrases",
        "forbid_future_data",
        "require_falsifiable",
        "require_flag_inconsistency",
        "check_citation_registry",
        "check_cross_turn_consistency",
        "known_data_bug",
        "cross_check_hint",
        "inherit_from",
    }
)
_KNOWN_OVERLAY_FIELDS = frozenset(
    {"coverage", "reason", "required_any_phrases", "required_all_phrases", "fact_aliases"}
)

_NUMBER_RE = re.compile(r"(?<![\w])[-+]?\d[\d,]*(?:\.\d+)?%?")
_TAG_RE = re.compile(r"\[([SGRWE]\d+)\]")
_ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
_CN_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日")
_REFUSAL_MARKS = (
    "无数据",
    "没有数据",
    "没有可用",
    "无可用",
    "不可用",
    "无法",
    "不能可靠回答",
    "超出覆盖",
    "0 行",
    "0行",
    "不存在",
    "休市",
    "非交易日",
)
_INCONSISTENCY_MARKS = (
    "矛盾",
    "不一致",
    "异常",
    "冲突",
    "不可能",
    "重复",
    "质疑",
)
_CONDITION_MARKS = ("若", "如果", "一旦", "跌破", "突破", "失效", "证伪")
_CONTEXT_LOSS_MARKS = (
    "你指的是",
    "请补充",
    "请明确",
    "哪家公司、题材",
    "哪个板块",
    "上一条研究逻辑",
)
_PREDICTIVE_MARKS = ("预计", "预期", "大概率", "可能", "研判", "若", "如果", "或将")
_REALIZED_MARKS = ("实际", "收涨", "收跌", "收盘", "上涨", "下跌", "涨停", "跌停", "成交额")


class VerdictState(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNJUDGEABLE = "unjudgeable"
    NOT_RUN = "not_run"


class OperationalState(str, Enum):
    NOT_RUN = "not_run"
    BLOCKED = "blocked"
    FAILED = "failed"
    DEGRADED = "degraded"
    COMPLETED = "completed"


class ExperienceState(str, Enum):
    UNLABELED = "unlabeled"
    LABELED = "labeled"
    INELIGIBLE = "ineligible"


@dataclass(frozen=True)
class RuleVerdict:
    rule_id: str
    kind: str
    state: VerdictState
    reason: str


@dataclass(frozen=True)
class OperationalVerdict:
    state: OperationalState
    reason: str


@dataclass(frozen=True)
class TruthVerdict:
    state: VerdictState
    rules: tuple[RuleVerdict, ...] = ()


@dataclass(frozen=True)
class ExperienceVerdict:
    state: ExperienceState = ExperienceState.UNLABELED
    label: str | None = None
    reason: str = "blind experience label not supplied"


@dataclass(frozen=True)
class CaseVerdict:
    case_id: str
    operational: OperationalVerdict
    truth: TruthVerdict
    experience: ExperienceVerdict = field(default_factory=ExperienceVerdict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class CaseContract:
    case_id: str
    tier: str
    query: str
    cutoff_date: str | None
    pass_rule: str
    coverage: str
    coverage_reason: str | None
    required_any_phrases: tuple[str, ...]
    required_all_phrases: tuple[str, ...]
    fact_aliases: Mapping[str, tuple[str, ...]]
    case: Mapping[str, Any]
    diagnostics: tuple[str, ...] = ()


def load_verdict_overlay(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load the additive verdict overlay, returning only its case mapping."""

    payload = json.loads((path or VERDICT_OVERLAY_PATH).read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, dict):
        raise ValueError("verdict overlay must contain an object-valued cases field")
    return {str(case_id): dict(entry) for case_id, entry in cases.items()}


def compile_case_contract(
    case: Mapping[str, Any], overlay: Mapping[str, Any] | None = None
) -> CaseContract:
    """Compile one canonical case plus its additive verdict overlay."""

    overlay = dict(overlay or {})
    diagnostics: list[str] = []
    unknown_case = sorted(set(case) - _KNOWN_CASE_FIELDS)
    if unknown_case:
        diagnostics.append("unknown case fields: " + ", ".join(unknown_case))
    unknown_overlay = sorted(set(overlay) - _KNOWN_OVERLAY_FIELDS)
    if unknown_overlay:
        diagnostics.append("unknown overlay fields: " + ", ".join(unknown_overlay))

    coverage = str(overlay.get("coverage") or "semantic_required")
    if coverage not in {"structured", "semantic_required"}:
        diagnostics.append(f"invalid coverage: {coverage}")
        coverage = "semantic_required"
    aliases_raw = overlay.get("fact_aliases") or {}
    aliases = {
        str(field_name): tuple(str(item) for item in values)
        for field_name, values in aliases_raw.items()
    }
    return CaseContract(
        case_id=str(case["id"]),
        tier=str(case.get("tier") or "unknown"),
        query=str(case.get("query") or ""),
        cutoff_date=str(case["date"]) if case.get("date") else None,
        pass_rule=str(case.get("pass_rule") or ""),
        coverage=coverage,
        coverage_reason=(
            str(overlay["reason"]) if overlay.get("reason") is not None else None
        ),
        required_any_phrases=tuple(
            str(item) for item in (overlay.get("required_any_phrases") or [])
        ),
        required_all_phrases=tuple(
            str(item) for item in (overlay.get("required_all_phrases") or [])
        ),
        fact_aliases=aliases,
        case=dict(case),
        diagnostics=tuple(diagnostics),
    )


def evaluate_case(
    contract: CaseContract, case_run: Mapping[str, Any] | None
) -> CaseVerdict:
    """Evaluate one case without conflating absence, operation, and quality."""

    if case_run is None:
        return CaseVerdict(
            case_id=contract.case_id,
            operational=OperationalVerdict(
                state=OperationalState.NOT_RUN,
                reason="no case run recorded",
            ),
            truth=TruthVerdict(state=VerdictState.NOT_RUN),
        )
    operational = _evaluate_operational(case_run)
    truth = _evaluate_truth(contract, case_run, operational)
    return CaseVerdict(
        case_id=contract.case_id,
        operational=operational,
        truth=truth,
        experience=_evaluate_experience(case_run),
    )


def _evaluate_operational(case_run: Mapping[str, Any]) -> OperationalVerdict:
    blocked_reason = case_run.get("blocked_reason")
    turns = case_run.get("turns") or []
    if blocked_reason and not turns:
        return OperationalVerdict(
            state=OperationalState.BLOCKED,
            reason=str(blocked_reason),
        )
    if not turns:
        return OperationalVerdict(
            state=OperationalState.FAILED,
            reason="case run has no turns",
        )

    statuses = [str(turn.get("status") or "unknown") for turn in turns]
    if any(status != "completed" for status in statuses):
        errors = [str(turn.get("error")) for turn in turns if turn.get("error")]
        reason = ", ".join(errors) if errors else "terminal states: " + ", ".join(statuses)
        return OperationalVerdict(state=OperationalState.FAILED, reason=reason)
    if any(turn.get("degrades") for turn in turns):
        return OperationalVerdict(
            state=OperationalState.DEGRADED,
            reason="one or more completed turns reported degradation",
        )
    return OperationalVerdict(
        state=OperationalState.COMPLETED,
        reason="all recorded turns completed",
    )


def _evaluate_truth(
    contract: CaseContract,
    case_run: Mapping[str, Any],
    operational: OperationalVerdict,
) -> TruthVerdict:
    if operational.state in {OperationalState.BLOCKED, OperationalState.FAILED}:
        return TruthVerdict(state=VerdictState.UNJUDGEABLE)

    turns = [turn for turn in (case_run.get("turns") or []) if isinstance(turn, Mapping)]
    answers = [str(turn.get("answer") or "") for turn in turns]
    text = "\n".join(answers)
    rules: list[RuleVerdict] = [
        _bool_rule(
            "answer_present",
            "answer",
            bool(text.strip()),
            "at least one answer is present",
            "all answer texts are empty",
        )
    ]
    case = contract.case

    if case.get("expect_refusal"):
        refused = any(mark in text for mark in _REFUSAL_MARKS)
        rules.append(
            _bool_rule(
                "refusal",
                "refusal",
                refused,
                "answer explicitly reports unavailable/no data",
                "answer does not explicitly report unavailable/no data",
            )
        )

    forbidden = tuple(str(item) for item in (case.get("forbid_phrases") or []))
    if forbidden:
        hits = [item for item in forbidden if item in text]
        rules.append(
            _bool_rule(
                "forbidden_phrases",
                "forbidden_text",
                not hits,
                "no forbidden phrase observed",
                "forbidden phrases observed: " + ", ".join(hits),
            )
        )

    if contract.required_any_phrases:
        hits = [item for item in contract.required_any_phrases if item in text]
        rules.append(
            _bool_rule(
                "required_any_phrases",
                "required_text",
                bool(hits),
                "required alternative observed: " + ", ".join(hits),
                "none of the required alternatives was observed",
            )
        )
    if contract.required_all_phrases:
        missing = [item for item in contract.required_all_phrases if item not in text]
        rules.append(
            _bool_rule(
                "required_all_phrases",
                "required_text",
                not missing,
                "all required phrases observed",
                "missing required phrases: " + ", ".join(missing),
            )
        )

    must_mention = tuple(str(item) for item in (case.get("must_mention") or []))
    if must_mention:
        missing = [item for item in must_mention if item not in text]
        rules.append(
            _bool_rule(
                "must_mention",
                "product_language",
                not missing,
                "all product terms observed",
                "missing product terms: " + ", ".join(missing),
            )
        )

    expected_entities = tuple(str(item) for item in (case.get("expect_entities") or []))
    if expected_entities:
        missing = [item for item in expected_entities if item not in text]
        rules.append(
            _bool_rule(
                "expected_entities",
                "entity_presence",
                not missing,
                "all expected entities observed",
                "missing expected entities: " + ", ".join(missing),
            )
        )

    for item in case.get("expect_facts") or []:
        rules.append(_evaluate_fact(item, text, contract.fact_aliases))

    if case.get("forbid_future_data"):
        rules.append(_evaluate_cutoff(contract.cutoff_date, turns, text))

    if case.get("check_citation_registry"):
        rules.append(_evaluate_citation_integrity(turns, text))

    if case.get("require_flag_inconsistency"):
        found = any(mark in text for mark in _INCONSISTENCY_MARKS)
        rules.append(
            _bool_rule(
                "inconsistency",
                "semantic_marker",
                found,
                "answer flags an inconsistency",
                "answer does not flag the required inconsistency",
            )
        )

    if case.get("require_falsifiable"):
        has_condition = any(mark in text for mark in _CONDITION_MARKS)
        has_number = bool(_extract_numbers(text))
        rules.append(
            _bool_rule(
                "falsifiable",
                "semantic_marker",
                has_condition and has_number,
                "answer contains a condition and numeric threshold",
                "answer lacks a condition or numeric threshold",
            )
        )

    if case.get("check_cross_turn_consistency"):
        lost = any(mark in answer for answer in answers[1:] for mark in _CONTEXT_LOSS_MARKS)
        if lost:
            rules.append(
                RuleVerdict(
                    rule_id="cross_turn_consistency",
                    kind="multi_turn",
                    state=VerdictState.FAIL,
                    reason="follow-up lost already established conversation context",
                )
            )
        else:
            rules.append(
                _observation_or_unjudgeable(
                    case_run,
                    "cross_turn_consistency",
                    "multi_turn",
                    "text alone cannot prove set/count consistency",
                )
            )

    if case.get("expect_answer_set") and contract.coverage == "structured":
        rules.append(
            _evaluate_answer_set(
                case_run,
                tuple(str(item) for item in case.get("expect_answer_set") or []),
                exact=bool(case.get("exact_set")),
            )
        )

    if case.get("inherit_from"):
        rules.append(
            _observation_or_unjudgeable(
                case_run,
                "inherited_golden",
                "agent_eval",
                "historical acceptance trace lacks agent_eval TurnInput observations",
            )
        )

    if contract.coverage == "semantic_required":
        rules.append(
            _observation_or_unjudgeable(
                case_run,
                "pass_rule",
                "semantic",
                contract.coverage_reason or "pass rule needs semantic observation",
            )
        )

    if contract.diagnostics:
        rules.append(
            RuleVerdict(
                rule_id="contract_diagnostics",
                kind="contract",
                state=VerdictState.UNJUDGEABLE,
                reason="; ".join(contract.diagnostics),
            )
        )

    return TruthVerdict(state=_aggregate_rules(rules), rules=tuple(rules))


def _evaluate_fact(
    raw: Mapping[str, Any],
    text: str,
    aliases_by_field: Mapping[str, tuple[str, ...]],
) -> RuleVerdict:
    field_name = str(raw.get("field") or "unknown")
    if "value" not in raw:
        return RuleVerdict(
            rule_id=f"fact:{field_name}",
            kind="fact",
            state=VerdictState.UNJUDGEABLE,
            reason="fact expectation has no value",
        )
    expected = raw["value"]
    aliases = aliases_by_field.get(field_name, ())
    candidate_text = _alias_windows(text, aliases) if aliases else text
    if isinstance(expected, bool):
        matched = str(expected).lower() in candidate_text.lower()
    elif isinstance(expected, (int, float)):
        numbers = _extract_numbers(candidate_text)
        tolerance = 0.0
        if raw.get("tol_abs") is not None:
            tolerance = abs(float(raw["tol_abs"]))
        elif raw.get("tol_pct") is not None:
            tolerance = abs(float(expected)) * abs(float(raw["tol_pct"])) / 100.0
        matched = any(abs(value - float(expected)) <= tolerance + 1e-9 for value in numbers)
    else:
        matched = str(expected) in candidate_text
    return _bool_rule(
        f"fact:{field_name}",
        "fact",
        matched,
        f"expected fact {field_name} observed",
        f"expected fact {field_name}={expected!r} not observed within tolerance",
    )


def _evaluate_cutoff(
    cutoff_text: str | None,
    turns: list[Mapping[str, Any]],
    answer_text: str,
) -> RuleVerdict:
    try:
        cutoff = date.fromisoformat(str(cutoff_text))
    except (TypeError, ValueError):
        return RuleVerdict(
            "cutoff",
            "temporal",
            VerdictState.UNJUDGEABLE,
            "case cutoff date is missing or invalid",
        )
    citation_dates: list[date] = []
    for turn in turns:
        for citation in turn.get("citations") or []:
            if not isinstance(citation, Mapping) or not citation.get("date"):
                continue
            try:
                citation_dates.append(date.fromisoformat(str(citation["date"])))
            except ValueError:
                continue
    future = sorted({item.isoformat() for item in citation_dates if item > cutoff})
    if future or _has_realized_future_claim(answer_text, cutoff):
        detail = ", ".join(future) if future else "future realized claim in answer text"
        return RuleVerdict(
            "cutoff",
            "temporal",
            VerdictState.FAIL,
            "future-of-cutoff evidence observed: " + detail,
        )
    if not citation_dates:
        return RuleVerdict(
            "cutoff",
            "temporal",
            VerdictState.UNJUDGEABLE,
            "no structured citation dates available to prove cutoff compliance",
        )
    return RuleVerdict(
        "cutoff",
        "temporal",
        VerdictState.PASS,
        "all structured citation dates are on or before the cutoff",
    )


def _evaluate_citation_integrity(
    turns: list[Mapping[str, Any]], answer_text: str
) -> RuleVerdict:
    cited = set(_TAG_RE.findall(answer_text))
    minted: set[str] = set()
    for turn in turns:
        for evidence in turn.get("evidence") or []:
            if isinstance(evidence, Mapping):
                minted.update(_TAG_RE.findall(str(evidence.get("label") or "")))
    dangling = sorted(cited - minted)
    return _bool_rule(
        "citation_integrity",
        "citation",
        not dangling,
        "all cited tags were minted; no tags is vacuously clean",
        "unminted citation tags: " + ", ".join(dangling),
    )


def _evaluate_answer_set(
    case_run: Mapping[str, Any], expected: tuple[str, ...], *, exact: bool
) -> RuleVerdict:
    raw = (case_run.get("truth_observations") or {}).get("answer_set")
    if not isinstance(raw, Mapping) or not isinstance(raw.get("values"), list):
        return RuleVerdict(
            "answer_set",
            "set",
            VerdictState.UNJUDGEABLE,
            "typed answer_set observation not supplied",
        )
    observed = {str(item) for item in raw["values"]}
    expected_set = set(expected)
    passed = observed == expected_set if exact else expected_set <= observed
    return _bool_rule(
        "answer_set",
        "set",
        passed,
        "observed answer set satisfies the contract",
        f"observed answer set {sorted(observed)} does not satisfy {sorted(expected_set)}",
    )


def _observation_or_unjudgeable(
    case_run: Mapping[str, Any], rule_id: str, kind: str, missing_reason: str
) -> RuleVerdict:
    raw = (case_run.get("truth_observations") or {}).get(rule_id)
    if not isinstance(raw, Mapping):
        return RuleVerdict(rule_id, kind, VerdictState.UNJUDGEABLE, missing_reason)
    try:
        state = VerdictState(str(raw.get("state")))
    except ValueError:
        state = VerdictState.UNJUDGEABLE
    if state is VerdictState.NOT_RUN:
        state = VerdictState.UNJUDGEABLE
    return RuleVerdict(
        rule_id=rule_id,
        kind=kind,
        state=state,
        reason=str(raw.get("reason") or "external typed observation"),
    )


def _evaluate_experience(case_run: Mapping[str, Any]) -> ExperienceVerdict:
    raw = case_run.get("experience_verdict")
    if not isinstance(raw, Mapping):
        return ExperienceVerdict()
    if raw.get("eligible") is False:
        return ExperienceVerdict(
            state=ExperienceState.INELIGIBLE,
            reason=str(raw.get("reason") or "reference is ineligible for this case/dimension"),
        )
    label = raw.get("label")
    if label:
        return ExperienceVerdict(
            state=ExperienceState.LABELED,
            label=str(label),
            reason=str(raw.get("reason") or "external blind label"),
        )
    return ExperienceVerdict()


def _bool_rule(
    rule_id: str,
    kind: str,
    passed: bool,
    pass_reason: str,
    fail_reason: str,
) -> RuleVerdict:
    return RuleVerdict(
        rule_id=rule_id,
        kind=kind,
        state=VerdictState.PASS if passed else VerdictState.FAIL,
        reason=pass_reason if passed else fail_reason,
    )


def _aggregate_rules(rules: list[RuleVerdict]) -> VerdictState:
    if not rules:
        return VerdictState.UNJUDGEABLE
    if any(rule.state is VerdictState.FAIL for rule in rules):
        return VerdictState.FAIL
    if any(rule.state is VerdictState.UNJUDGEABLE for rule in rules):
        return VerdictState.UNJUDGEABLE
    return VerdictState.PASS


def _extract_numbers(text: str) -> list[float]:
    values: list[float] = []
    for raw in _NUMBER_RE.findall(text):
        normalized = raw.rstrip("%").replace(",", "")
        try:
            values.append(float(normalized))
        except ValueError:
            continue
    return values


def _alias_windows(text: str, aliases: tuple[str, ...]) -> str:
    windows: list[str] = []
    for alias in aliases:
        start = 0
        while True:
            index = text.find(alias, start)
            if index < 0:
                break
            windows.append(text[max(0, index - 8) : index + len(alias) + 40])
            start = index + len(alias)
    return "\n".join(windows)


def _has_realized_future_claim(text: str, cutoff: date) -> bool:
    sentences = re.split(r"[。！？!?；;\n]", text)
    for sentence in sentences:
        observed: list[date] = []
        for year, month, day in _ISO_DATE_RE.findall(sentence):
            try:
                observed.append(date(int(year), int(month), int(day)))
            except ValueError:
                continue
        for month, day in _CN_DATE_RE.findall(sentence):
            try:
                observed.append(date(cutoff.year, int(month), int(day)))
            except ValueError:
                continue
        if not any(item > cutoff for item in observed):
            continue
        predictive = any(mark in sentence for mark in _PREDICTIVE_MARKS)
        realized = any(mark in sentence for mark in _REALIZED_MARKS)
        if realized and not predictive:
            return True
    return False


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value

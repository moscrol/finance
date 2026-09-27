"""Rejected lexical experiment, retained ONLY for audit reproduction.

Scope challenges disproved its suitability for perspective judgments. Production
scoring/saving rejects signal_match_rules; a lexical match here grants no stance,
approval or runtime capability. Do not import this experiment into intelligence.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

_FIELDS = ("opportunity_preferences", "risk_triggers")
_NON_ASSERTION = re.compile(
    r"如果|假设|假如|假定|倘若|若|一旦|只要|除非|可能|或许|预计|有望|"
    r"据说|传闻|听说|是否|吗|例如|示例|举例|样例|引用|[?？`\"'“”‘’「」]|"
    r"\b(?:if|assuming|hypothetically|may|might|reportedly|example)\b"
)
_NEGATION = re.compile(r"未|没|不|无|非|否认|否定|消失|减弱|缺乏|失去|\b(?:no|not|never|without|neither)\b")


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def value_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _phrases(value: Any, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError("Signal phrases must be a nonempty list")
    if any(not isinstance(item, str) or len(_norm(item)) < 2 for item in value):
        raise ValueError("Signal phrases must contain at least two characters")
    normalized = [_norm(item) for item in value]
    if len(set(normalized)) != len(normalized):
        raise ValueError("Duplicate signal phrase")
    return normalized


def validated_rules(profile: dict[str, Any]) -> dict[tuple[str, str], dict]:
    """Reject malformed/stale contracts instead of silently using legacy matching."""
    raw = profile.get("signal_match_rules", [])
    if not isinstance(raw, list):
        raise ValueError("Signal match rules must be a list")
    rules = {}
    for rule in raw:
        if not isinstance(rule, dict) or set(rule) != {"field", "value_sha256", "all_of", "none_of"}:
            raise ValueError("Invalid signal match rule schema")
        field = rule["field"]
        if not isinstance(field, str) or field not in _FIELDS:
            raise ValueError("Invalid signal match field")
        values = profile.get(field) or []
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ValueError("Signal target field must be a string list")
        targets = [value for value in values if value_sha256(value) == rule["value_sha256"]]
        if len(targets) != 1:
            raise ValueError("Signal rule target absent or ambiguous")
        key = field, targets[0]
        if key in rules:
            raise ValueError("Duplicate signal target")
        groups = rule["all_of"]
        if not isinstance(groups, list) or len(groups) < 2:
            raise ValueError("Signal rule needs at least two condition groups")
        normalized = [_phrases(group) for group in groups]
        phrases = [phrase for group in normalized for phrase in group]
        if len(set(phrases)) != len(phrases):
            raise ValueError("Condition groups must not share phrases")
        rules[key] = {"all_of": normalized, "none_of": _phrases(rule["none_of"], allow_empty=True)}
    return rules


def matches(rule: dict, facts: str) -> bool:
    """Require all groups within one sentence; explicit contrary evidence vetoes.

    These conservative guards deliberately reject some valid wording (including
    double negation). They do not resolve time, subject identity or arbitrary
    natural-language entailment. Question text never enters this function.
    """
    text = _norm(facts)
    if (_NON_ASSERTION.search(text) or _NON_ASSERTION.search(facts.casefold())
            or any(phrase in text for phrase in rule["none_of"])):
        return False
    groups = rule["all_of"]
    aliases = [phrase for group in groups for phrase in group]
    clauses = re.split(r"[，,；;。.!！？?\n]", facts)
    # A positive elsewhere must not override an explicit negative observation.
    if any(
        (_NEGATION.search(clause.casefold()) or _NEGATION.search(_norm(clause)))
        and any(alias in _norm(clause) for alias in aliases)
        for clause in clauses
    ):
        return False
    return any(
        all(any(alias in _norm(sentence) for alias in group) for group in groups)
        for sentence in re.split(r"[。.!！？?\n]", facts)
    )


def challenge(rule: dict, cases: Any) -> dict:
    """Measure frozen semantic expectations without repairing or approving them."""
    if not isinstance(cases, list) or not cases:
        raise ValueError("Missing challenge cases")
    rows, seen = [], set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Invalid challenge case")
        ident, facts, expected = case.get("id"), case.get("facts"), case.get("expected_match")
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise ValueError("Missing or duplicate challenge identity")
        if not isinstance(facts, str) or not facts.strip() or type(expected) is not bool:
            raise ValueError("Invalid challenge facts or expectation")
        seen.add(ident)
        actual = matches(rule, facts)
        rows.append({"id": ident, "expected_match": expected, "actual_match": actual,
                     "facts_sha256": value_sha256(facts), "passed": actual == expected})
    failed = sum(not row["passed"] for row in rows)
    return {"status": "FAIL" if failed else "PASS", "passed": len(rows) - failed,
            "failed": failed, "cases": rows}

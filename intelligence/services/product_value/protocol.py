"""试点协议（pilot-protocol/v1）：加载、校验、冻结哈希与判据默认值。

协议是「事前登记」的载体：任务卡版本、评分维度、允许扣除的暂停理由、排除规则
及其版本、判据阈值，全部在采集前冻结成一个哈希。``assignment_created`` 事件带着
这个哈希，测量时对不上就是「版本 / 截止时点不符」，整对配对判 ``invalid``。
改判据只能另开一版协议、另开一组，不能就地改。

哈希对象是**去掉 ``protocol_hash`` 自身**之后的全部内容（含 ``frozen_at``），
所以冻结时间本身也被钉住。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from intelligence.services.product_value.contracts import (
    PROTOCOL_SCHEMA,
    RUBRIC_DIMENSIONS,
    RUBRIC_MAX_PER_DIMENSION,
)
from intelligence.services.product_value.hashing import content_hash


class ProtocolError(ValueError):
    """协议不满足合同，拒绝使用（不静默降级）。"""


DEFAULT_CRITERIA: dict[str, dict[str, Any]] = {
    "completion_quality": {"severe_error_max": 0},
    "time_saving": {
        "min_participants": 3,
        "min_complete_pairs": 6,
        "require_both_categories": True,
        "median_saving_min": 0.20,
    },
    "proactive_reuse": {
        "min_participants": 3,
        "min_rate": 0.5,
        "manual_reminder_quiet_hours": 72,
    },
    "recheck": {},
    "cost": {},
    "renewal": {"renewal_window_days": 14},
}

REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "protocol_version",
    "pilot_id",
    "task_categories",
    "cases",
    "case_pairs",
    "rubric",
    "allowed_pause_reasons",
    "criteria",
    "exclusion_rules",
    "cohort_window",
)


def load_protocol(path: str | Path) -> dict[str, Any]:
    """按后缀读 YAML 或 JSON。YAML 需要 pyyaml（本仓 .venv-workbench 已带）。"""
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() in {".yaml", ".yml"}:
        import yaml  # 局部导入：JSON 调用方不必带 pyyaml

        loaded = yaml.safe_load(text)
    else:
        loaded = json.loads(text)
    if not isinstance(loaded, Mapping):
        raise ProtocolError(f"protocol must be a mapping: {source}")
    return dict(loaded)


def _require_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"protocol.{name} must be a non-empty string")
    return value.strip()


def validate_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    """返回规范化副本；不满足合同抛 ``ProtocolError``。"""
    if not isinstance(protocol, Mapping):
        raise ProtocolError("protocol must be a mapping")
    missing = [name for name in REQUIRED_FIELDS if name not in protocol]
    if missing:
        raise ProtocolError(f"protocol missing fields: {', '.join(missing)}")
    if protocol["schema_version"] != PROTOCOL_SCHEMA:
        raise ProtocolError(
            f"protocol.schema_version must be {PROTOCOL_SCHEMA!r}, got {protocol['schema_version']!r}"
        )
    normalized = deepcopy(dict(protocol))
    normalized["protocol_version"] = _require_str(protocol["protocol_version"], "protocol_version")
    normalized["pilot_id"] = _require_str(protocol["pilot_id"], "pilot_id")

    categories = protocol["task_categories"]
    if not isinstance(categories, list) or not categories:
        raise ProtocolError("protocol.task_categories must be a non-empty list")
    category_set = {_require_str(item, "task_categories[]") for item in categories}

    cases = protocol["cases"]
    if not isinstance(cases, list) or not cases:
        raise ProtocolError("protocol.cases must be a non-empty list")
    case_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise ProtocolError(f"protocol.cases[{index}] must be a mapping")
        case_id = _require_str(case.get("case_id"), f"cases[{index}].case_id")
        if case_id in case_ids:
            raise ProtocolError(f"duplicate case_id {case_id!r}")
        case_ids.add(case_id)
        _require_str(str(case.get("case_version", "")), f"cases[{index}].case_version")
        category = _require_str(case.get("category"), f"cases[{index}].category")
        if category not in category_set:
            raise ProtocolError(f"cases[{index}].category {category!r} not in task_categories")

    pairs = protocol["case_pairs"]
    if not isinstance(pairs, list) or not pairs:
        raise ProtocolError("protocol.case_pairs must be a non-empty list")
    pair_ids: set[str] = set()
    for index, pair in enumerate(pairs):
        if not isinstance(pair, Mapping):
            raise ProtocolError(f"protocol.case_pairs[{index}] must be a mapping")
        pair_id = _require_str(pair.get("case_pair_id"), f"case_pairs[{index}].case_pair_id")
        if pair_id in pair_ids:
            raise ProtocolError(f"duplicate case_pair_id {pair_id!r}")
        pair_ids.add(pair_id)
        category = _require_str(pair.get("category"), f"case_pairs[{index}].category")
        if category not in category_set:
            raise ProtocolError(f"case_pairs[{index}].category {category!r} not in task_categories")
        members = pair.get("case_ids")
        if not isinstance(members, list) or len(members) != 2:
            raise ProtocolError(f"case_pairs[{index}].case_ids must list exactly two cases")
        for member in members:
            if member not in case_ids:
                raise ProtocolError(f"case_pairs[{index}] references unknown case {member!r}")

    rubric = protocol["rubric"]
    if not isinstance(rubric, Mapping):
        raise ProtocolError("protocol.rubric must be a mapping")
    _require_str(rubric.get("rubric_version"), "rubric.rubric_version")
    dimensions = rubric.get("dimensions")
    if not isinstance(dimensions, list) or tuple(dimensions) != RUBRIC_DIMENSIONS:
        raise ProtocolError(
            f"protocol.rubric.dimensions must be exactly {list(RUBRIC_DIMENSIONS)!r} (v1 contract)"
        )
    max_per = rubric.get("max_per_dimension", RUBRIC_MAX_PER_DIMENSION)
    if max_per != RUBRIC_MAX_PER_DIMENSION:
        raise ProtocolError(f"protocol.rubric.max_per_dimension must be {RUBRIC_MAX_PER_DIMENSION}")

    pauses = protocol["allowed_pause_reasons"]
    if not isinstance(pauses, list):
        raise ProtocolError("protocol.allowed_pause_reasons must be a list")
    for item in pauses:
        _require_str(item, "allowed_pause_reasons[]")

    if not isinstance(protocol["criteria"], Mapping):
        raise ProtocolError("protocol.criteria must be a mapping")

    rules = protocol["exclusion_rules"]
    if not isinstance(rules, list):
        raise ProtocolError("protocol.exclusion_rules must be a list")
    rule_ids: set[str] = set()
    for index, rule in enumerate(rules):
        if not isinstance(rule, Mapping):
            raise ProtocolError(f"protocol.exclusion_rules[{index}] must be a mapping")
        rule_id = _require_str(rule.get("rule_id"), f"exclusion_rules[{index}].rule_id")
        _require_str(str(rule.get("rule_version", "")), f"exclusion_rules[{index}].rule_version")
        if rule_id in rule_ids:
            raise ProtocolError(f"duplicate exclusion rule {rule_id!r}")
        rule_ids.add(rule_id)

    window = protocol["cohort_window"]
    if not isinstance(window, Mapping) or "start" not in window or "end" not in window:
        raise ProtocolError("protocol.cohort_window must have start and end")

    declared = protocol.get("protocol_hash")
    if declared is not None:
        computed = protocol_hash(protocol)
        if declared != computed:
            raise ProtocolError("protocol_hash does not match protocol content (was it edited after freezing?)")
    return normalized


def protocol_hash(protocol: Mapping[str, Any]) -> str:
    """协议内容哈希（不含 ``protocol_hash`` 字段本身）。"""
    return content_hash(dict(protocol), drop_keys=frozenset({"protocol_hash"}))


def freeze_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    """校验并写入 ``protocol_hash``。已有且不一致的哈希会被 ``validate_protocol`` 拒绝。"""
    normalized = validate_protocol(protocol)
    normalized["protocol_hash"] = protocol_hash(normalized)
    return normalized


def criteria(protocol: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """协议判据 ⊕ 默认值（协议优先，单层合并）。"""
    merged: dict[str, dict[str, Any]] = {}
    declared = protocol.get("criteria") or {}
    for key, defaults in DEFAULT_CRITERIA.items():
        block = dict(defaults)
        override = declared.get(key) if isinstance(declared, Mapping) else None
        if isinstance(override, Mapping):
            block.update(override)
        merged[key] = block
    return merged


def allowed_pause_reasons(protocol: Mapping[str, Any]) -> frozenset[str]:
    return frozenset(str(item) for item in protocol.get("allowed_pause_reasons") or ())


def exclusion_rule_versions(protocol: Mapping[str, Any]) -> dict[str, str]:
    """``rule_id -> rule_version``。排除只能命中这里登记过的规则。"""
    out: dict[str, str] = {}
    for rule in protocol.get("exclusion_rules") or ():
        if isinstance(rule, Mapping) and rule.get("rule_id"):
            out[str(rule["rule_id"])] = str(rule.get("rule_version", ""))
    return out


def case_index(protocol: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(case["case_id"]): dict(case) for case in protocol.get("cases") or ()}


def pair_index(protocol: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(pair["case_pair_id"]): dict(pair) for pair in protocol.get("case_pairs") or ()}


def rubric_version(protocol: Mapping[str, Any]) -> str:
    rubric = protocol.get("rubric") or {}
    return str(rubric.get("rubric_version", "")) if isinstance(rubric, Mapping) else ""


__all__ = [
    "DEFAULT_CRITERIA",
    "ProtocolError",
    "allowed_pause_reasons",
    "case_index",
    "criteria",
    "exclusion_rule_versions",
    "freeze_protocol",
    "load_protocol",
    "pair_index",
    "protocol_hash",
    "rubric_version",
    "validate_protocol",
]

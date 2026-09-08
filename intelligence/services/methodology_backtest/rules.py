"""方法论规则 JSON schema v0 + 白名单校验（设计稿 §3.2）。

一条方法论 = 一个声明式 JSON（``methodology/rules/<rule_id>.v<version>.json``）。这里只做两件事：
校验（**不触库**，每个错误带字段路径）与解析成不可变 ``Rule``。SQL 由 ``compiler`` 生成，规则文件里
**不允许出现任何 SQL 片段**——``label`` / ``op`` / ``metric`` / ``universe`` / ``baseline.kind`` 全部走
白名单，谓词值只接受 bool / 数值 / 受限字符集的短文本 / 上述的列表。

为什么白名单而不是转义：转义防的是注入，白名单防的是「规则说了什么」失控。2026-08-20 已拍决策
（asof-prefetch-dual-red-design §1）：不给 agent 开任意 SQL；规则是能被 diff、被复用同一套白名单的
声明，不是通道。

示例（设计稿 §3.2）::

    {
      "rule_id": "dual_red_streak3_continuation",
      "version": 1,
      "title": "连续三日严格双红的板块，后 5 日仍上涨",
      "scope": {"entity_type": "sector", "universe": "published_snapshot"},
      "condition": {"all": [
        {"label": "dual_red_strict", "op": "==", "value": true, "lag": 0},
        {"label": "dual_red_streak", "op": ">=", "value": 3, "lag": 0},
        {"entity": "market", "label": "market_stage", "op": "in", "value": ["主升"], "lag": 0}
      ]},
      "outcome": {
        "target": "pct_chg",
        "horizons": [3, 5, 7, 10],
        "metrics": ["fwd_return", "max_return", "days_to_peak", "drawdown_after_peak"],
        "success": {"metric": "fwd_return", "horizon": 5, "op": ">", "value": 0}
      },
      "baseline": {"kind": "same_universe_all_days"},
      "min_n": 20,
      "sharing": "shared",
      "owner": "system"
    }

归属层（设计稿 §6 BP v0.4 产品约束第一条）：``sharing`` ∈ {shared, private}，``owner`` 共享规则恒为 ``system``
（来源写 ``source_perspective``：经视角蒸馏的 KOL 方法论或系统内置），私有规则为用户 id。两字段**必填**——
渲染层的合规硬门是「缺任一字段即不渲染」，规则层就不给默认值，免得一条漏写的私有规则被当成共享规则渲染出去。
私有 → 共享的升格必须过统计门 ``supported`` 且由人拍板：改文件、升 version，不在这里自动做。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .labels import ALL_LABELS, MARKET_LABELS, SECTOR_LABELS, STOCK_LABELS, STOCK_UNIVERSE, THEME_LABELS

# --------------------------------------------------------------------------- #
# 白名单
# --------------------------------------------------------------------------- #
ENTITY_TYPES = ("sector", "theme", "market", "stock")
SCOPE_ENTITY_TYPES = ("sector", "theme", "stock")
UNIVERSES: dict[str, tuple[str, ...]] = {
    "sector": ("published_snapshot",),
    "theme": ("heat_final",),
    "stock": (STOCK_UNIVERSE,),
}

# label → (entity_type, 值类型)。值类型决定允许的 op 与 value 形态。
LABEL_KINDS: dict[str, tuple[str, str]] = {
    **{name: ("sector", "bool") for name in SECTOR_LABELS if name != "dual_red_streak"},
    "dual_red_streak": ("sector", "num"),
    "limit_heat_rank": ("theme", "num"),
    "limit_heat_rank_jump": ("theme", "bool"),
    "mainline_flag": ("theme", "bool"),
    # 舆论生命周期段（#36 / G-06）：文本标签，词表见 opinion_stage.STAGES + "unverifiable"。
    "opinion_stage": ("theme", "text"),
    "market_stage": ("market", "text"),
    "volume_surge": ("market", "bool"),
    "ma5_peak_confirmed": ("market", "bool"),
    "ma5_valley_confirmed": ("market", "bool"),
    **{name: ("stock", "bool") for name in STOCK_LABELS},
}
assert set(LABEL_KINDS) == set(ALL_LABELS) == set(SECTOR_LABELS + THEME_LABELS + MARKET_LABELS + STOCK_LABELS)
assert set(UNIVERSES) == set(SCOPE_ENTITY_TYPES)

OPS_BY_KIND: dict[str, tuple[str, ...]] = {
    "bool": ("==", "!="),
    "num": ("==", "!=", ">", ">=", "<", "<=", "in", "not_in"),
    "text": ("==", "!=", "in", "not_in"),
}
SET_OPS = ("in", "not_in")
SUCCESS_OPS = (">", ">=", "<", "<=")
METRICS = ("fwd_return", "max_return", "days_to_peak", "drawdown_after_peak")
TARGETS = ("pct_chg",)
# same_universe_all_days：首末事件日之间、同 universe 全部 (实体, 日)——设计稿 §3.2 原口径；
# same_universe_event_days：只取事件发生的那些交易日里的全体实体——把「择时」效应剥掉，只检验「选择」。
BASELINE_KINDS = ("same_universe_all_days", "same_universe_event_days")

DEFAULT_MIN_N = 20
MAX_LAG = 20
MAX_PREDICATES = 8
MAX_HORIZON = 60
MAX_LIST_VALUES = 16

RULE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
# 文本值：字母数字下划线、CJK、少量连接符。分号、引号、括号、比较符、注释符一律拒——规则里不该有 SQL 味。
TEXT_VALUE_RE = re.compile(r"^[0-9A-Za-z_\u4e00-\u9fff\u00b7/\-]{1,32}$")
# 归属：共享 / 私有；owner 是用户 id 或 system。
SHARING_LEVELS = ("shared", "private")
SYSTEM_OWNER = "system"
OWNER_RE = re.compile(r"^[0-9A-Za-z_.@\-]{1,64}$")
MAX_SOURCE_PERSPECTIVE = 200

_TOP_KEYS = {
    "rule_id", "version", "title", "scope", "condition", "outcome", "baseline", "min_n", "notes", "provenance",
    "sharing", "owner", "source_perspective",
}
# 候选规则从哪来：kind=correction 时 ref 是 corrections.jsonl 的记录 id / ts。只做溯源，不参与编译。
_PROVENANCE_KEYS = {"kind", "ref", "ts", "text", "registered_at", "user"}
PROVENANCE_KINDS = ("correction", "manual")
MAX_PROVENANCE_TEXT = 500
_SCOPE_KEYS = {"entity_type", "universe"}
_PRED_KEYS = {"label", "op", "value", "lag", "entity"}
_OUTCOME_KEYS = {"target", "horizons", "metrics", "success"}
_SUCCESS_KEYS = {"metric", "horizon", "op", "value"}
_BASELINE_KEYS = {"kind"}


# --------------------------------------------------------------------------- #
# 数据类
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RuleError:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class RuleValidationError(ValueError):
    """规则不合法。``errors`` 逐条带字段路径，方便定位到 JSON 里的那一行。"""

    def __init__(self, errors: list[RuleError], source: str | None = None):
        self.errors = list(errors)
        self.source = source
        head = f"规则校验失败（{len(self.errors)} 处）" + (f" {source}" if source else "")
        super().__init__(head + "\n" + "\n".join(f"  - {e}" for e in self.errors))


@dataclass(frozen=True)
class Predicate:
    label: str
    op: str
    value: Any  # bool | float | str | tuple[...]
    lag: int
    entity_type: str
    kind: str  # bool / num / text


@dataclass(frozen=True)
class Success:
    metric: str
    horizon: int
    op: str
    value: float


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: int
    title: str
    entity_type: str
    universe: str
    predicates: tuple[Predicate, ...]
    target: str
    horizons: tuple[int, ...]
    metrics: tuple[str, ...]
    success: Success
    baseline_kind: str
    min_n: int
    sharing: str
    owner: str
    raw: dict[str, Any]

    @property
    def ref(self) -> str:
        return f"{self.rule_id}@v{self.version}"


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v: Any) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool)) and v == v  # 排除 NaN


def _unknown_keys(doc: dict[str, Any], allowed: set[str], path: str, errors: list[RuleError]) -> None:
    for key in sorted(set(doc) - allowed):
        errors.append(RuleError(f"{path}.{key}" if path else key, "未知字段（白名单外的键一律拒绝）"))


def _check_text_value(v: Any, path: str, errors: list[RuleError]) -> bool:
    if not isinstance(v, str):
        errors.append(RuleError(path, f"文本标签的值必须是字符串，得到 {type(v).__name__}"))
        return False
    if not TEXT_VALUE_RE.match(v):
        errors.append(
            RuleError(path, f"文本值 {v!r} 含白名单外字符（只允许字母数字下划线/中文/·/-；不接受任何 SQL 片段）")
        )
        return False
    return True


def _validate_predicate(doc: Any, path: str, errors: list[RuleError]) -> Predicate | None:
    if not isinstance(doc, dict):
        errors.append(RuleError(path, "谓词必须是对象"))
        return None
    _unknown_keys(doc, _PRED_KEYS, path, errors)

    label = doc.get("label")
    if not isinstance(label, str) or label not in LABEL_KINDS:
        errors.append(RuleError(f"{path}.label", f"label {label!r} 不在白名单 {sorted(LABEL_KINDS)}"))
        return None
    label_entity, kind = LABEL_KINDS[label]

    entity = doc.get("entity", label_entity)
    if not isinstance(entity, str) or entity not in ENTITY_TYPES:
        errors.append(RuleError(f"{path}.entity", f"entity {entity!r} 不在 {ENTITY_TYPES}"))
        return None
    if entity != label_entity:
        errors.append(RuleError(f"{path}.entity", f"label {label!r} 属于 {label_entity} 实体，不是 {entity}"))
        return None

    op = doc.get("op")
    allowed_ops = OPS_BY_KIND[kind]
    if not isinstance(op, str) or op not in allowed_ops:
        errors.append(RuleError(f"{path}.op", f"op {op!r} 不在 {kind} 标签允许的 {allowed_ops}"))
        return None

    lag = doc.get("lag", 0)
    if not _is_int(lag) or lag < 0 or lag > MAX_LAG:
        errors.append(RuleError(f"{path}.lag", f"lag 必须是 0..{MAX_LAG} 的整数，得到 {lag!r}"))
        return None

    if "value" not in doc:
        errors.append(RuleError(f"{path}.value", "缺少 value"))
        return None
    raw_value = doc["value"]
    value: Any
    if op in SET_OPS:
        if not isinstance(raw_value, list) or not raw_value or len(raw_value) > MAX_LIST_VALUES:
            errors.append(RuleError(f"{path}.value", f"{op} 的 value 必须是 1..{MAX_LIST_VALUES} 个元素的列表"))
            return None
        items: list[Any] = []
        for i, item in enumerate(raw_value):
            item_path = f"{path}.value[{i}]"
            if kind == "text":
                if not _check_text_value(item, item_path, errors):
                    return None
                items.append(item)
            else:
                if not _is_num(item):
                    errors.append(RuleError(item_path, f"数值标签的列表元素必须是数值，得到 {item!r}"))
                    return None
                items.append(float(item))
        value = tuple(items)
    elif kind == "bool":
        if not isinstance(raw_value, bool):
            errors.append(RuleError(f"{path}.value", f"布尔标签的值必须是 true/false，得到 {raw_value!r}"))
            return None
        value = bool(raw_value)
    elif kind == "num":
        if not _is_num(raw_value):
            errors.append(RuleError(f"{path}.value", f"数值标签的值必须是数值，得到 {raw_value!r}"))
            return None
        value = float(raw_value)
    else:
        if not _check_text_value(raw_value, f"{path}.value", errors):
            return None
        value = raw_value
    return Predicate(label=label, op=op, value=value, lag=int(lag), entity_type=entity, kind=kind)


def validate_rule(doc: Any) -> tuple[Rule | None, list[RuleError]]:
    """校验规则文档。返回 ``(rule, errors)``：errors 非空则 rule 为 None。纯函数，不触库。"""
    errors: list[RuleError] = []
    if not isinstance(doc, dict):
        return None, [RuleError("", f"规则必须是 JSON 对象，得到 {type(doc).__name__}")]
    _unknown_keys(doc, _TOP_KEYS, "", errors)

    rule_id = doc.get("rule_id")
    if not isinstance(rule_id, str) or not RULE_ID_RE.match(rule_id):
        errors.append(RuleError("rule_id", f"必须匹配 {RULE_ID_RE.pattern}，得到 {rule_id!r}"))
    version = doc.get("version")
    if not _is_int(version) or version < 1:
        errors.append(RuleError("version", f"必须是 >=1 的整数，得到 {version!r}"))
    title = doc.get("title", "")
    if not isinstance(title, str) or len(title) > 200:
        errors.append(RuleError("title", "必须是 <=200 字的字符串"))
    if "notes" in doc and not isinstance(doc["notes"], str):
        errors.append(RuleError("notes", "必须是字符串"))

    # scope
    scope = doc.get("scope")
    entity_type = universe = None
    if not isinstance(scope, dict):
        errors.append(RuleError("scope", "缺少或不是对象"))
    else:
        _unknown_keys(scope, _SCOPE_KEYS, "scope", errors)
        entity_type = scope.get("entity_type")
        if entity_type not in SCOPE_ENTITY_TYPES:
            errors.append(RuleError("scope.entity_type", f"必须在 {SCOPE_ENTITY_TYPES}，得到 {entity_type!r}"))
            entity_type = None
        universe = scope.get("universe")
        if entity_type is not None and universe not in UNIVERSES[entity_type]:
            errors.append(
                RuleError("scope.universe", f"{entity_type} 允许的 universe 是 {UNIVERSES[entity_type]}，得到 {universe!r}")
            )

    # condition
    predicates: list[Predicate] = []
    condition = doc.get("condition")
    if not isinstance(condition, dict) or set(condition) != {"all"}:
        errors.append(RuleError("condition", "v0 只支持 {\"all\": [谓词, ...]}"))
    else:
        preds = condition["all"]
        if not isinstance(preds, list) or not preds or len(preds) > MAX_PREDICATES:
            errors.append(RuleError("condition.all", f"必须是 1..{MAX_PREDICATES} 个谓词的列表"))
        else:
            for i, pred_doc in enumerate(preds):
                pred = _validate_predicate(pred_doc, f"condition.all[{i}]", errors)
                if pred is None:
                    continue
                if entity_type is not None and pred.entity_type not in (entity_type, "market"):
                    errors.append(
                        RuleError(
                            f"condition.all[{i}].label",
                            f"{pred.label} 是 {pred.entity_type} 标签，{entity_type} 规则只能引用本实体或 market 标签",
                        )
                    )
                    continue
                predicates.append(pred)

    # outcome
    outcome = doc.get("outcome")
    horizons: tuple[int, ...] = ()
    metrics: tuple[str, ...] = ()
    success: Success | None = None
    target = None
    if not isinstance(outcome, dict):
        errors.append(RuleError("outcome", "缺少或不是对象"))
    else:
        _unknown_keys(outcome, _OUTCOME_KEYS, "outcome", errors)
        target = outcome.get("target")
        if target not in TARGETS:
            errors.append(RuleError("outcome.target", f"必须在 {TARGETS}，得到 {target!r}"))
        hs = outcome.get("horizons")
        if (
            not isinstance(hs, list)
            or not hs
            or any(not _is_int(h) or h <= 0 or h > MAX_HORIZON for h in hs)
            or len(set(hs)) != len(hs)
        ):
            errors.append(RuleError("outcome.horizons", f"必须是不重复的 1..{MAX_HORIZON} 整数列表，得到 {hs!r}"))
        else:
            horizons = tuple(sorted(int(h) for h in hs))
        ms = outcome.get("metrics")
        if not isinstance(ms, list) or not ms or any(m not in METRICS for m in ms) or len(set(ms)) != len(ms):
            errors.append(RuleError("outcome.metrics", f"必须是 {METRICS} 的非空子集，得到 {ms!r}"))
        else:
            metrics = tuple(ms)
        sc = outcome.get("success")
        if not isinstance(sc, dict):
            errors.append(RuleError("outcome.success", "缺少或不是对象"))
        else:
            _unknown_keys(sc, _SUCCESS_KEYS, "outcome.success", errors)
            s_metric = sc.get("metric")
            s_h = sc.get("horizon")
            s_op = sc.get("op")
            s_val = sc.get("value")
            ok = True
            if s_metric not in METRICS:
                errors.append(RuleError("outcome.success.metric", f"必须在 {METRICS}，得到 {s_metric!r}"))
                ok = False
            elif metrics and s_metric not in metrics:
                errors.append(RuleError("outcome.success.metric", f"{s_metric} 不在 outcome.metrics 里"))
                ok = False
            if not _is_int(s_h) or s_h <= 0:
                errors.append(RuleError("outcome.success.horizon", f"必须是正整数，得到 {s_h!r}"))
                ok = False
            elif horizons and s_h not in horizons:
                errors.append(RuleError("outcome.success.horizon", f"{s_h} 不在 outcome.horizons 里"))
                ok = False
            if s_op not in SUCCESS_OPS:
                errors.append(RuleError("outcome.success.op", f"必须在 {SUCCESS_OPS}，得到 {s_op!r}"))
                ok = False
            if not _is_num(s_val):
                errors.append(RuleError("outcome.success.value", f"必须是数值，得到 {s_val!r}"))
                ok = False
            if ok:
                success = Success(metric=s_metric, horizon=int(s_h), op=s_op, value=float(s_val))

    # baseline
    baseline = doc.get("baseline", {"kind": BASELINE_KINDS[0]})
    baseline_kind = None
    if not isinstance(baseline, dict):
        errors.append(RuleError("baseline", "必须是对象"))
    else:
        _unknown_keys(baseline, _BASELINE_KEYS, "baseline", errors)
        baseline_kind = baseline.get("kind")
        if baseline_kind not in BASELINE_KINDS:
            errors.append(RuleError("baseline.kind", f"必须在 {BASELINE_KINDS}，得到 {baseline_kind!r}"))

    min_n = doc.get("min_n", DEFAULT_MIN_N)
    if not _is_int(min_n) or min_n < 1:
        errors.append(RuleError("min_n", f"必须是 >=1 的整数，得到 {min_n!r}"))

    # 归属层：两字段必填，不给默认值（漏写的私有规则不能默认成共享）
    sharing = doc.get("sharing")
    owner = doc.get("owner")
    if sharing not in SHARING_LEVELS:
        errors.append(RuleError("sharing", f"必填，必须在 {SHARING_LEVELS}，得到 {sharing!r}"))
    if not isinstance(owner, str) or not OWNER_RE.match(owner):
        errors.append(RuleError("owner", f"必填，必须匹配 {OWNER_RE.pattern}，得到 {owner!r}"))
    elif sharing == "shared" and owner != SYSTEM_OWNER:
        errors.append(RuleError("owner", f"共享规则的 owner 必须是 {SYSTEM_OWNER!r}（来源写 source_perspective），得到 {owner!r}"))
    elif sharing == "private" and owner == SYSTEM_OWNER:
        errors.append(RuleError("owner", f"私有规则的 owner 必须是用户 id，不能是 {SYSTEM_OWNER!r}"))
    if "source_perspective" in doc:
        sp = doc["source_perspective"]
        if not isinstance(sp, str) or not sp.strip() or len(sp) > MAX_SOURCE_PERSPECTIVE:
            errors.append(RuleError("source_perspective", f"必须是 1..{MAX_SOURCE_PERSPECTIVE} 字的非空字符串"))

    if "provenance" in doc:
        prov = doc["provenance"]
        if not isinstance(prov, dict):
            errors.append(RuleError("provenance", "必须是对象"))
        else:
            _unknown_keys(prov, _PROVENANCE_KEYS, "provenance", errors)
            if prov.get("kind") not in PROVENANCE_KINDS:
                errors.append(RuleError("provenance.kind", f"必须在 {PROVENANCE_KINDS}，得到 {prov.get('kind')!r}"))
            for key in ("ref", "ts", "text", "registered_at", "user"):
                if key in prov and (not isinstance(prov[key], str) or len(prov[key]) > MAX_PROVENANCE_TEXT):
                    errors.append(RuleError(f"provenance.{key}", f"必须是 <={MAX_PROVENANCE_TEXT} 字的字符串"))
            if prov.get("kind") == "correction" and not str(prov.get("ref") or "").strip():
                errors.append(RuleError("provenance.ref", "kind=correction 时必须给纠偏记录的 id 或 ts"))

    if errors:
        return None, errors
    assert entity_type is not None and universe is not None and success is not None and baseline_kind is not None
    rule = Rule(
        rule_id=rule_id,
        version=int(version),
        title=title,
        entity_type=entity_type,
        universe=universe,
        predicates=tuple(predicates),
        target=target,
        horizons=horizons,
        metrics=metrics,
        success=success,
        baseline_kind=baseline_kind,
        min_n=int(min_n),
        sharing=str(sharing),
        owner=str(owner),
        raw=doc,
    )
    return rule, []


def parse_rule(doc: Any, *, source: str | None = None) -> Rule:
    rule, errors = validate_rule(doc)
    if errors or rule is None:
        raise RuleValidationError(errors, source=source)
    return rule


def load_rule(path: str | Path) -> Rule:
    p = Path(path).expanduser()
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuleValidationError([RuleError("", f"JSON 解析失败: {exc}")], source=str(p)) from exc
    rule = parse_rule(doc, source=str(p))
    expected = f"{rule.rule_id}.v{rule.version}.json"
    if p.name != expected:
        raise RuleValidationError(
            [RuleError("rule_id/version", f"文件名 {p.name} 应为 {expected}（文件名即版本标识）")],
            source=str(p),
        )
    return rule

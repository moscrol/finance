"""规则二桶适配器：在旁路库上按三值逻辑评估臂规则，产出桶概率与逐 case projection（spec 03 §6）。

与 ``methodology_backtest.compiler`` 的关系：编译器只产出「条件成立的事件集」，回答不了
「这一行条件是 False 还是 Unknown」；两桶 recipe 需要三值——**已知 False 进 false 桶，
Unknown 不进任何桶、不出预测**。所以这里用 Python 在已取出的标签行上逐谓词求值，
运算符 / 值类型仍严格沿用 ``rules`` 白名单解析出的 ``Predicate``。

三值合取：任一谓词 False → False（即便别的谓词未知）；否则任一未知 → None；否则 True。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from intelligence.services.methodology_backtest.labels import MARKET_ENTITY_ID
from intelligence.services.methodology_backtest.rules import Predicate, Rule, parse_rule
from intelligence.services.methodology_backtest.store import open_labels_db, read_meta
from intelligence.services.research_validation.baseline import (
    OutcomeRow,
    purge_cut_date,
    two_bucket_probabilities,
)
from intelligence.services.research_validation.contracts import (
    Calendar,
    ContractError,
    digest,
    outcome_predicate,
    utc_iso,
)


@dataclass(frozen=True)
class LabelSnapshot:
    """一次只读取出的旁路库切片。"""

    labels_db: str
    calendar: Calendar
    labels: Mapping[tuple[str, str, str, str], Any]  # (entity_type, entity_id, trade_date, label) -> value
    universe: Mapping[str, tuple[str, ...]]  # trade_date -> entity ids（有标签行的实体）
    outcomes: Mapping[tuple[str, str], tuple[str, Any, Any]]  # (entity_id, trade_date) -> (status, metric, computed_at)
    meta: Mapping[str, Any]

    @property
    def version_hashes(self) -> dict[str, str]:
        labels = self.meta.get("labels") or {}
        return {
            "label_version": str(labels.get("label_version")),
            "source_db": str(labels.get("source_db")),
            "source_max_trade_date": str(labels.get("source_max_trade_date")),
        }

    @property
    def source_hash(self) -> str:
        return digest({"labels_db": self.labels_db, "meta": {k: dict(v) for k, v in self.meta.items()}})


def load_snapshot(
    labels_db: str | Path,
    *,
    entity_type: str,
    start: str,
    end: str,
    horizon: int,
    metric: str,
    max_lag: int = 20,
) -> LabelSnapshot:
    """只读取 [start−max_lag 交易日, end] 的标签与 [start, end] 的结果；不写任何东西。"""
    path = Path(labels_db).expanduser()
    con = open_labels_db(path, read_only=True)
    try:
        meta = read_meta(con)
        if not meta.get("labels") or not meta.get("outcomes"):
            raise ContractError("旁路库缺 labels / outcomes 构建记录")
        if meta["labels"]["label_version"] != meta["outcomes"]["label_version"]:
            raise ContractError("labels 与 outcomes 的 label_version 不一致")
        if horizon not in (meta["outcomes"].get("horizons") or []):
            raise ContractError(f"旁路库未构建 horizon={horizon}（只有 {meta['outcomes'].get('horizons')}）")
        calendar = Calendar(tuple(str(r[0]) for r in con.execute("SELECT trade_date FROM history_calendar ORDER BY idx").fetchall()))
        start_idx = max(0, calendar.index(start) - int(max_lag))
        label_start = calendar.dates[start_idx]
        rows = con.execute(
            """SELECT entity_type, entity_id, trade_date, label, value_num, value_text
               FROM history_labels
               WHERE trade_date BETWEEN ? AND ? AND (entity_type = ? OR (entity_type = 'market' AND entity_id = ?))
               ORDER BY trade_date, entity_type, entity_id, label""",
            [label_start, end, entity_type, MARKET_ENTITY_ID],
        ).fetchall()
        labels: dict[tuple[str, str, str, str], Any] = {}
        universe: dict[str, set[str]] = {}
        for et, eid, day, label, num, text in rows:
            day = str(day)
            labels[(str(et), str(eid), day, str(label))] = text if text is not None else num
            if et == entity_type and start <= day <= end:
                universe.setdefault(day, set()).add(str(eid))
        if metric not in ("fwd_return", "max_return", "days_to_peak", "drawdown_after_peak"):
            raise ContractError(f"未知 metric {metric!r}")
        out_rows = con.execute(
            f"""SELECT entity_id, trade_date, status, {metric}, computed_at
                FROM history_outcomes
                WHERE entity_type = ? AND horizon = ? AND trade_date BETWEEN ? AND ?""",
            [entity_type, int(horizon), start, end],
        ).fetchall()
    finally:
        con.close()
    outcomes = {(str(eid), str(day)): (str(status), value, computed) for eid, day, status, value, computed in out_rows}
    return LabelSnapshot(
        labels_db=str(path),
        calendar=calendar,
        labels=labels,
        universe={d: tuple(sorted(s)) for d, s in sorted(universe.items())},
        outcomes=outcomes,
        meta=meta,
    )


def _compare(pred: Predicate, value: Any) -> bool | None:
    if value is None:
        return None
    if pred.kind == "bool":
        if value not in (0, 1, 0.0, 1.0):
            return None
        actual = bool(value)
        return (actual == bool(pred.value)) if pred.op == "==" else (actual != bool(pred.value))
    if pred.kind == "num":
        try:
            x = float(value)
        except (TypeError, ValueError):
            return None
        if x != x:
            return None
        if pred.op in ("in", "not_in"):
            hit = any(x == float(v) for v in pred.value)
            return hit if pred.op == "in" else not hit
        v = float(pred.value)
        return {"==": x == v, "!=": x != v, ">": x > v, ">=": x >= v, "<": x < v, "<=": x <= v}[pred.op]
    text = str(value)
    if pred.op in ("in", "not_in"):
        hit = text in tuple(pred.value)
        return hit if pred.op == "in" else not hit
    return (text == pred.value) if pred.op == "==" else (text != pred.value)


def evaluate_condition(
    predicates: Sequence[Predicate], *, snapshot: LabelSnapshot, entity_id: str, day: str
) -> tuple[bool | None, dict[str, Any]]:
    """三值合取 + 实际读到的字段（projection）。"""
    projection: dict[str, Any] = {}
    verdicts: list[bool | None] = []
    for pred in predicates:
        try:
            lag_day = snapshot.calendar.shift(day, -int(pred.lag)) if pred.lag else day
        except ContractError:
            lag_day = None
        key_entity = MARKET_ENTITY_ID if pred.entity_type == "market" else entity_id
        value = snapshot.labels.get((pred.entity_type, key_entity, lag_day, pred.label)) if lag_day else None
        projection[f"{pred.entity_type}:{pred.label}@lag{pred.lag}"] = value
        verdicts.append(_compare(pred, value))
    if any(v is False for v in verdicts):
        return False, projection
    if any(v is None for v in verdicts):
        return None, projection
    return True, projection


def outcome_value(snapshot: LabelSnapshot, outcome_spec: Mapping[str, Any], entity_id: str, day: str) -> int | None:
    row = snapshot.outcomes.get((entity_id, day))
    if row is None or row[0] != "ok":
        return None
    verdict = outcome_predicate(outcome_spec, row[1])
    return None if verdict is None else int(verdict)


def bucket_probabilities_for_rule(
    rule: Rule,
    *,
    snapshot: LabelSnapshot,
    window: Mapping[str, str],
    outcome_spec: Mapping[str, Any],
) -> dict[str, Any]:
    """发现窗内每个 (实体, 日) 按臂条件分桶（跨窗 purge 后），返回两桶平滑概率与计数。"""
    cut = purge_cut_date(snapshot.calendar, window["end"], int(outcome_spec["horizon"]))
    rows: list[tuple[bool | None, OutcomeRow]] = []
    n_purged = 0
    for day, entities in snapshot.universe.items():
        if not window["start"] <= day <= window["end"]:
            continue
        if cut is None or day > cut:
            n_purged += len(entities)
            continue
        for entity_id in entities:
            condition, _proj = evaluate_condition(rule.predicates, snapshot=snapshot, entity_id=entity_id, day=day)
            rows.append((condition, OutcomeRow(entity_id, day, outcome_value(snapshot, outcome_spec, entity_id, day))))
    buckets = two_bucket_probabilities(rows)
    buckets["n_purged"] = n_purged
    buckets["window"] = dict(window)
    buckets["purge_cut_date"] = cut
    return buckets


def arm_rule(arm: Mapping[str, Any]) -> Rule:
    if arm.get("rule") is None:
        raise ContractError(f"臂 {arm.get('arm_id')} 没有规则，不能跑规则二桶")
    return parse_rule(arm["rule"])


def rule_diff(base: Rule, other: Rule) -> dict[str, Any]:
    """臂间规则差分：只允许「移除谓词」；多出来的谓词如实记录，由调用方判定是否合法。"""
    b = {(p.entity_type, p.label, p.op, str(p.value), p.lag) for p in base.predicates}
    o = {(p.entity_type, p.label, p.op, str(p.value), p.lag) for p in other.predicates}
    fmt = lambda s: sorted(f"{et}:{lab} {op} {val} @lag{lag}" for et, lab, op, val, lag in s)  # noqa: E731
    return {"removed_from_base": fmt(b - o), "added_to_base": fmt(o - b), "shared": fmt(b & o)}


def computed_at_iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "tzinfo"):
        ts = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return utc_iso(ts)
    return str(value)


__all__ = [
    "LabelSnapshot",
    "arm_rule",
    "bucket_probabilities_for_rule",
    "computed_at_iso",
    "evaluate_condition",
    "load_snapshot",
    "outcome_value",
    "rule_diff",
]

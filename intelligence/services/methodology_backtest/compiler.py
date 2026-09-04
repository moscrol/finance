"""规则 → 参数化 DuckDB SQL（设计稿 §3.2「一段话 → 可执行查询」）。

编译器是**唯一知道旁路库表结构的地方**。职责：

- ``condition.all`` 的每个谓词 → 对 ``history_labels`` 的一次 join；``lag`` 通过 ``history_calendar``
  的 idx 位移到之前第 lag 个交易日（只能往过去看，lag>=0 在 rules 里已卡死）；
- ``entity: market`` 的谓词 → 按日 join 大盘标签（entity_id 常量 ``'market'``）；
- 交集 = 事件集；事件集 join ``history_outcomes`` → 逐事件 metrics；``success`` → 命中布尔；
- ``baseline`` → 同 universe、同日期范围内全部 (实体, 日) 的同一 success 比例。

安全边界：谓词值、日期、horizon 全部走 ``?`` 绑定参数；进入 SQL 文本的只有白名单映射出来的
列名 / 运算符 / 表别名与整数 lag。任何用户可控字符串都不会拼进 SQL。

前视：事件在 D 日成立只用 D 及之前的标签（lag>=0），结果只用 D 之后的收益（outcomes 窗口从 D+1 起）。
把 outcomes 整体前移一个交易日的作弊夹具会让阳性对照失去 ``supported``——这是 selftest 的第三组对照。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .labels import MARKET_ENTITY_ID
from .rules import METRICS, Predicate, Rule

# 白名单 → SQL 片段。规则里的字符串永远经过这两张表映射，不直接进 SQL。
_OP_SQL: dict[str, str] = {"==": "=", "!=": "<>", ">": ">", ">=": ">=", "<": "<", "<=": "<="}
_METRIC_COL: dict[str, str] = {m: m for m in METRICS}
_VALUE_COL: dict[str, str] = {"bool": "value_num", "num": "value_num", "text": "value_text"}


@dataclass(frozen=True)
class Query:
    sql: str
    params: tuple[Any, ...]


@dataclass(frozen=True)
class CompiledRule:
    events: Query
    metrics: Query
    baseline_template: Query  # params 里留两个日期位，见 baseline_for

    def baseline_for(self, start: date | str, end: date | str) -> Query:
        """基准率查询：同 universe、[start, end] 内全部 (实体, 日) 的 success 比例。"""
        head, tail = self.baseline_template.params[:1], self.baseline_template.params[1:]
        return Query(self.baseline_template.sql, (*head, str(start), str(end), *tail))


def _bind_value(pred: Predicate) -> tuple[Any, ...]:
    if isinstance(pred.value, tuple):
        return tuple(pred.value)
    if pred.kind == "bool":
        return (1.0 if pred.value else 0.0,)
    return (pred.value,)


def _predicate_sql(k: int, pred: Predicate) -> tuple[str, tuple[Any, ...], str, tuple[Any, ...]]:
    """返回 (join_sql, join_params, where_sql, where_params)。"""
    p = f"p{k}"
    joins: list[str] = []
    join_params: list[Any] = []
    if pred.lag == 0:
        date_expr = "u.trade_date"
    else:
        c = f"c{k}"
        joins.append(f"JOIN history_calendar {c} ON {c}.idx = u.idx - {int(pred.lag)}")
        date_expr = f"{c}.trade_date"
    id_expr = "?" if pred.entity_type == "market" else "u.entity_id"
    joins.append(
        f"JOIN history_labels {p} ON {p}.entity_type = ? AND {p}.entity_id = {id_expr} "
        f"AND {p}.label = ? AND {p}.trade_date = {date_expr}"
    )
    join_params.append(pred.entity_type)
    if pred.entity_type == "market":
        join_params.append(MARKET_ENTITY_ID)
    join_params.append(pred.label)

    col = _VALUE_COL[pred.kind]
    values = _bind_value(pred)
    if pred.op in ("in", "not_in"):
        keyword = "IN" if pred.op == "in" else "NOT IN"
        placeholders = ", ".join("?" for _ in values)
        where = f"{p}.{col} {keyword} ({placeholders})"
    else:
        where = f"{p}.{col} {_OP_SQL[pred.op]} ?"
    return "\n    ".join(joins), tuple(join_params), where, values


def compile_rule(rule: Rule, *, start: date | str, end: date | str) -> CompiledRule:
    """把规则编译成三段参数化查询（事件集 + 命中 / 逐事件多窗口 metrics / 基准率模板）。"""
    if rule.baseline_kind not in _BASELINE_SQL:
        # rules 已按白名单校验过；这里再拦一次是为了新 kind 加进白名单却没写编译分支时 fail closed。
        raise ValueError(f"编译器不认识 baseline.kind={rule.baseline_kind!r}")
    joins: list[str] = []
    join_params: list[Any] = []
    wheres: list[str] = []
    where_params: list[Any] = []
    for k, pred in enumerate(rule.predicates):
        j_sql, j_params, w_sql, w_params = _predicate_sql(k, pred)
        joins.append(j_sql)
        join_params.extend(j_params)
        wheres.append(w_sql)
        where_params.extend(w_params)

    metric_col = _METRIC_COL[rule.success.metric]
    success_op = _OP_SQL[rule.success.op]
    universe_cte = (
        "WITH u AS (\n"
        "    SELECT DISTINCT l.entity_id, l.trade_date, c.idx\n"
        "    FROM history_labels l\n"
        "    JOIN history_calendar c ON c.trade_date = l.trade_date\n"
        "    WHERE l.entity_type = ? AND l.trade_date BETWEEN ? AND ?\n"
        ")"
    )
    universe_params: list[Any] = [rule.entity_type, str(start), str(end)]
    joins_sql = "\n    ".join(joins)
    where_sql = "\n  AND ".join(wheres) if wheres else "TRUE"

    events_sql = (
        f"{universe_cte}\n"
        "SELECT u.entity_id, u.trade_date, o.status,\n"
        f"       CASE WHEN o.status = 'ok' THEN (o.{metric_col} {success_op} ?) END AS success,\n"
        f"       o.{metric_col} AS success_metric\n"
        "FROM u\n"
        f"    {joins_sql}\n"
        "    LEFT JOIN history_outcomes o\n"
        "      ON o.entity_type = ? AND o.entity_id = u.entity_id\n"
        "     AND o.trade_date = u.trade_date AND o.horizon = ?\n"
        f"WHERE {where_sql}\n"
        "ORDER BY u.trade_date, u.entity_id"
    )
    events_params = (
        *universe_params,
        rule.success.value,
        *join_params,
        rule.entity_type,
        rule.success.horizon,
        *where_params,
    )

    horizon_placeholders = ", ".join("?" for _ in rule.horizons)
    metrics_sql = (
        f"{universe_cte}\n"
        "SELECT u.entity_id, u.trade_date, o.horizon, o.status,\n"
        "       o.fwd_return, o.max_return, o.days_to_peak, o.drawdown_after_peak\n"
        "FROM u\n"
        f"    {joins_sql}\n"
        "    JOIN history_outcomes o\n"
        "      ON o.entity_type = ? AND o.entity_id = u.entity_id\n"
        f"     AND o.trade_date = u.trade_date AND o.horizon IN ({horizon_placeholders})\n"
        f"WHERE {where_sql}\n"
        "ORDER BY u.trade_date, u.entity_id, o.horizon"
    )
    metrics_params = (
        *universe_params,
        *join_params,
        rule.entity_type,
        *rule.horizons,
        *where_params,
    )

    baseline_sql = _BASELINE_SQL[rule.baseline_kind].format(metric_col=metric_col, success_op=success_op)
    # 两个日期位由 baseline_for 填：params = (entity_type, <start>, <end>, success_value, entity_type, horizon)
    baseline_params = (rule.entity_type, rule.success.value, rule.entity_type, rule.success.horizon)

    return CompiledRule(
        events=Query(events_sql, events_params),
        metrics=Query(metrics_sql, metrics_params),
        baseline_template=Query(baseline_sql, baseline_params),
    )


# baseline.kind → SQL 模板。{metric_col} / {success_op} 只接受白名单映射结果。
_BASELINE_SQL: dict[str, str] = {
    "same_universe_all_days": (
        "WITH u AS (\n"
        "    SELECT DISTINCT entity_id, trade_date FROM history_labels\n"
        "    WHERE entity_type = ? AND trade_date BETWEEN ? AND ?\n"
        ")\n"
        "SELECT COUNT(*) AS n,\n"
        "       COUNT(*) FILTER (WHERE o.{metric_col} {success_op} ?) AS k\n"
        "FROM u\n"
        "JOIN history_outcomes o\n"
        "  ON o.entity_type = ? AND o.entity_id = u.entity_id\n"
        " AND o.trade_date = u.trade_date AND o.horizon = ? AND o.status = 'ok'"
    ),
}

"""规则 → 参数化 DuckDB SQL（设计稿 §3.2「一段话 → 可执行查询」）。

编译器是**唯一知道旁路库表结构的地方**。职责：

- ``condition.all`` 的每个谓词 → 对 ``history_labels`` 的一次 join；``lag`` 通过 ``history_calendar``
  的 idx 位移到之前第 lag 个交易日（只能往过去看，lag>=0 在 rules 里已卡死）；
- ``entity: market`` 的谓词 → 按日 join 大盘标签（entity_id 常量 ``'market'``）；
- 交集 = 事件集；事件集 join ``history_outcomes`` → 逐事件 metrics；``success`` → 命中布尔；
- ``baseline`` → 同 universe、同日期范围内全部 (实体, 日) 的同一 success 比例；
- 按阶段基准率 → 同一条基准率查询多一个 ``GROUP BY 当日 market_stage``（大盘标签按日 LEFT JOIN，缺标签的日
  归 NULL 桶由 runner 命名）。同 universe、同窗口、同 success 定义，只是按事件日所处的大盘阶段分层。

安全边界：谓词值、日期、horizon 全部走 ``?`` 绑定参数；进入 SQL 文本的只有白名单映射出来的
列名 / 运算符 / 表别名与整数 lag。任何用户可控字符串都不会拼进 SQL。

前视：事件在 D 日成立只用 D 及之前的标签（lag>=0），结果只用 D 之后的收益（outcomes 窗口从 D+1 起）。
把 outcomes 整体前移一个交易日的作弊夹具会让阳性对照失去 ``supported``——这是 selftest 的第三组对照。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence

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
    baseline_kind: str  # 规则声明的基准口径（定结论用）；另一种由 runner 作对照列
    baseline_params: tuple[Any, ...]  # (entity_type, success_value, entity_type, horizon)，日期位由 baseline_for 填
    metric_col: str
    success_op: str

    def baseline_for(
        self,
        start: date | str,
        end: date | str,
        *,
        kind: str | None = None,
        event_dates: Sequence[date | str] = (),
    ) -> Query:
        """基准率查询。``all_days``：[start, end] 内同 universe 全部 (实体, 日)；
        ``event_days``：只取 ``event_dates`` 那些交易日（日期走绑定参数，个数 <= 日历长度）。"""
        kind = kind or self.baseline_kind
        if kind not in _BASELINE_SQL:
            raise ValueError(f"编译器不认识 baseline.kind={kind!r}")
        entity_type, success_value, _et, horizon = self.baseline_params
        if kind == "same_universe_event_days":
            dates = sorted({str(d) for d in event_dates})
            if not dates:
                return Query(_EMPTY_BASELINE_SQL, ())
            sql = _BASELINE_SQL[kind].format(
                metric_col=self.metric_col,
                success_op=self.success_op,
                date_placeholders=", ".join("?" for _ in dates),
            )
            return Query(sql, (entity_type, *dates, success_value, entity_type, horizon))
        sql = _BASELINE_SQL[kind].format(metric_col=self.metric_col, success_op=self.success_op)
        return Query(sql, (entity_type, str(start), str(end), success_value, entity_type, horizon))

    def baseline_by_stage_for(
        self,
        start: date | str,
        end: date | str,
        *,
        kind: str | None = None,
        event_dates: Sequence[date | str] = (),
    ) -> Query:
        """按阶段基准率：与 ``baseline_for`` 同一 universe / 窗口 / success 定义，按当日 ``market_stage`` 分组，
        返回 ``(stage_text, n, k)`` 多行；缺大盘标签的日 ``stage_text`` 为 NULL。"""
        kind = kind or self.baseline_kind
        if kind not in _STAGE_BASELINE_SQL:
            raise ValueError(f"编译器不认识 baseline.kind={kind!r}")
        entity_type, success_value, _et, horizon = self.baseline_params
        stage_params = (MARKET_ENTITY_TYPE, MARKET_ENTITY_ID, STAGE_LABEL)
        if kind == "same_universe_event_days":
            dates = sorted({str(d) for d in event_dates})
            if not dates:
                return Query(_EMPTY_STAGE_BASELINE_SQL, ())
            sql = _STAGE_BASELINE_SQL[kind].format(
                metric_col=self.metric_col,
                success_op=self.success_op,
                date_placeholders=", ".join("?" for _ in dates),
            )
            return Query(sql, (entity_type, *dates, success_value, entity_type, horizon, *stage_params))
        sql = _STAGE_BASELINE_SQL[kind].format(metric_col=self.metric_col, success_op=self.success_op)
        return Query(sql, (entity_type, str(start), str(end), success_value, entity_type, horizon, *stage_params))


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

    return CompiledRule(
        events=Query(events_sql, events_params),
        metrics=Query(metrics_sql, metrics_params),
        baseline_kind=rule.baseline_kind,
        baseline_params=(rule.entity_type, rule.success.value, rule.entity_type, rule.success.horizon),
        metric_col=metric_col,
        success_op=success_op,
    )


# baseline.kind → SQL 模板。{metric_col} / {success_op} 只接受白名单映射结果；{date_placeholders} 是 ? 序列。
_BASELINE_UNIVERSE: dict[str, str] = {
    "same_universe_all_days": (
        "WITH u AS (\n"
        "    SELECT DISTINCT entity_id, trade_date FROM history_labels\n"
        "    WHERE entity_type = ? AND trade_date BETWEEN ? AND ?\n"
        ")\n"
    ),
    "same_universe_event_days": (
        "WITH u AS (\n"
        "    SELECT DISTINCT entity_id, trade_date FROM history_labels\n"
        "    WHERE entity_type = ? AND trade_date IN ({date_placeholders})\n"
        ")\n"
    ),
}
_BASELINE_TAIL = (
    "SELECT COUNT(*) AS n,\n"
    "       COUNT(*) FILTER (WHERE o.{metric_col} {success_op} ?) AS k\n"
    "FROM u\n"
    "JOIN history_outcomes o\n"
    "  ON o.entity_type = ? AND o.entity_id = u.entity_id\n"
    " AND o.trade_date = u.trade_date AND o.horizon = ? AND o.status = 'ok'"
)
_BASELINE_SQL: dict[str, str] = {kind: cte + _BASELINE_TAIL for kind, cte in _BASELINE_UNIVERSE.items()}
_EMPTY_BASELINE_SQL = "SELECT 0 AS n, 0 AS k"

# 按阶段基准率：同一个 u，多一个对大盘阶段标签的按日 LEFT JOIN + GROUP BY。阶段值来自 G-05
# canonical 标签（NULL = 当日无标签）；命名 / 归一都不在 SQL 里做。大盘标签的 entity_type /
# entity_id / label 也走绑定参数，SQL 文本里没有任何常量字面量。
MARKET_ENTITY_TYPE = "market"
STAGE_LABEL = "market_stage"
_STAGE_BASELINE_TAIL = (
    "SELECT ms.value_text AS stage,\n"
    "       COUNT(*) AS n,\n"
    "       COUNT(*) FILTER (WHERE o.{metric_col} {success_op} ?) AS k\n"
    "FROM u\n"
    "JOIN history_outcomes o\n"
    "  ON o.entity_type = ? AND o.entity_id = u.entity_id\n"
    " AND o.trade_date = u.trade_date AND o.horizon = ? AND o.status = 'ok'\n"
    "LEFT JOIN history_labels ms\n"
    "  ON ms.entity_type = ? AND ms.entity_id = ? AND ms.label = ? AND ms.trade_date = u.trade_date\n"
    "GROUP BY ms.value_text"
)
_STAGE_BASELINE_SQL: dict[str, str] = {kind: cte + _STAGE_BASELINE_TAIL for kind, cte in _BASELINE_UNIVERSE.items()}
_EMPTY_STAGE_BASELINE_SQL = "SELECT NULL AS stage, 0 AS n, 0 AS k WHERE FALSE"

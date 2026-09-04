"""在旁路库上执行编译结果，产出一条规则的完整读数（只读连接）。

流程：读成立条件（labels / outcomes 两次构建必须同源同版本，否则 fail closed）→ 解析窗口 →
编译 → 事件集 + 命中 → 基准率（同 universe、[首个事件日, 末个事件日]）→ 逐窗口 metrics 汇总 →
四态。``scan_rules`` 在此之上做 Benjamini–Hochberg 降级。

不写任何东西：主库、旁路库、用户台账、params.json、经验卡、画像都不碰。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Sequence

import duckdb

from .compiler import CompiledRule, compile_rule
from .rules import BASELINE_KINDS, Rule
from .stats import Readout, apply_bh_downgrade, benjamini_hochberg, four_state, readout
from .store import read_meta

EVENT_SAMPLE_LIMIT = 12


@dataclass(frozen=True)
class HorizonSummary:
    horizon: int
    n: int
    win_rate: float | None
    mean_fwd_return: float | None
    mean_max_return: float | None
    mean_days_to_peak: float | None
    mean_drawdown_after_peak: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "horizon": self.horizon,
            "n": self.n,
            "win_rate": self.win_rate,
            "mean_fwd_return": self.mean_fwd_return,
            "mean_max_return": self.mean_max_return,
            "mean_days_to_peak": self.mean_days_to_peak,
            "mean_drawdown_after_peak": self.mean_drawdown_after_peak,
        }


@dataclass(frozen=True)
class AltBaseline:
    """规则没声明的那种基准口径，只作对照列，不参与结论。"""

    kind: str
    n: int
    k: int
    p0: float | None
    lift: float | None
    verdict_if_used: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "n": self.n, "k": self.k, "p0": self.p0, "lift": self.lift, "verdict_if_used": self.verdict_if_used}


@dataclass
class RunResult:
    rule: Rule
    window: tuple[str, str]
    baseline_window: tuple[str, str] | None
    readout: Readout
    baseline_alt: AltBaseline | None
    n_matched: int
    n_pending: int
    n_missing: int
    first_event_date: str | None
    last_event_date: str | None
    horizons: list[HorizonSummary]
    conditions: dict[str, Any]
    events_sample: list[dict[str, Any]]
    sql: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    results: list[RunResult]
    p_values: list[float | None]
    rejected: list[bool]
    adjusted_p: list[float | None]
    verdicts_bh: list[str]
    q: float


# --------------------------------------------------------------------------- #
# 成立条件与窗口
# --------------------------------------------------------------------------- #
def load_conditions(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """旁路库两次构建的元数据 + data_gap + 日历。labels 与 outcomes 不同源不同版本时拒绝。"""
    meta = read_meta(con)
    labels = meta.get("labels")
    outcomes = meta.get("outcomes")
    if not labels:
        raise RuntimeError("旁路库缺 labels 构建记录，先跑 build-labels")
    if not outcomes:
        raise RuntimeError("旁路库缺 outcomes 构建记录，先跑 outcomes")
    if labels["source_max_trade_date"] != outcomes["source_max_trade_date"]:
        raise RuntimeError(
            "labels 与 outcomes 的源库 max(trade_date) 不一致："
            f"{labels['source_max_trade_date']} vs {outcomes['source_max_trade_date']}，两者须同一轮重建"
        )
    if labels["label_version"] != outcomes["label_version"]:
        raise RuntimeError(
            f"labels 与 outcomes 的 label_version 不一致：{labels['label_version']} vs {outcomes['label_version']}"
        )
    cal = con.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM history_calendar").fetchone()
    gaps = [str(r[0]) for r in con.execute("SELECT trade_date FROM history_data_gaps ORDER BY 1").fetchall()]
    return {
        "source_db": labels["source_db"],
        "source_max_trade_date": labels["source_max_trade_date"],
        "label_version": labels["label_version"],
        "labels_computed_at": labels["computed_at"],
        "labels_row_count": labels["row_count"],
        "outcomes_computed_at": outcomes["computed_at"],
        "outcomes_row_count": outcomes["row_count"],
        "outcomes_horizons": outcomes["horizons"],
        "calendar": {
            "start": str(cal[0]) if cal[0] is not None else None,
            "end": str(cal[1]) if cal[1] is not None else None,
            "days": int(cal[2]),
        },
        "data_gap_days": gaps,
        "data_gap_count": len(gaps),
        "source_row_counts": labels.get("source_row_counts", {}),
    }


def resolve_window(
    conditions: dict[str, Any],
    start: date | str | None,
    end: date | str | None,
) -> tuple[str, str]:
    cal = conditions["calendar"]
    s = str(start) if start else cal["start"]
    e = str(end) if end else cal["end"]
    if s is None or e is None:
        raise RuntimeError("旁路库日历为空")
    if s > e:
        raise ValueError(f"窗口起点 {s} 晚于终点 {e}")
    return s, e


def _check_horizons(rule: Rule, conditions: dict[str, Any]) -> None:
    built = set(conditions.get("outcomes_horizons") or [])
    missing = [h for h in rule.horizons if h not in built]
    if missing:
        raise RuntimeError(
            f"规则 {rule.ref} 要求的窗口 {missing} 没有构建（旁路库只有 {sorted(built)}），"
            "请用 outcomes --horizons 重建"
        )


# --------------------------------------------------------------------------- #
# 执行
# --------------------------------------------------------------------------- #
def _mean(values: list[float]) -> float | None:
    return (sum(values) / len(values)) if values else None


def _summarize_horizons(rows: Sequence[tuple], horizons: Sequence[int]) -> list[HorizonSummary]:
    by_h: dict[int, list[tuple]] = {h: [] for h in horizons}
    for _eid, _d, h, status, fwd, mx, peak, dd in rows:
        if status == "ok" and h in by_h:
            by_h[h].append((fwd, mx, peak, dd))
    out: list[HorizonSummary] = []
    for h in horizons:
        vals = by_h[h]
        fwds = [v[0] for v in vals if v[0] is not None]
        out.append(
            HorizonSummary(
                horizon=h,
                n=len(vals),
                win_rate=(sum(1 for f in fwds if f > 0) / len(fwds)) if fwds else None,
                mean_fwd_return=_mean(fwds),
                mean_max_return=_mean([v[1] for v in vals if v[1] is not None]),
                mean_days_to_peak=_mean([float(v[2]) for v in vals if v[2] is not None]),
                mean_drawdown_after_peak=_mean([v[3] for v in vals if v[3] is not None]),
            )
        )
    return out


def execute_compiled(
    con: duckdb.DuckDBPyConnection,
    rule: Rule,
    compiled: CompiledRule,
    *,
    window: tuple[str, str],
    conditions: dict[str, Any],
) -> RunResult:
    events = con.execute(compiled.events.sql, list(compiled.events.params)).fetchall()
    ok_events = [(eid, d, bool(s), metric) for eid, d, status, s, metric in events if status == "ok"]
    n_pending = sum(1 for e in events if e[2] == "pending")
    n_missing = sum(1 for e in events if e[2] not in ("ok", "pending"))

    baseline_window: tuple[str, str] | None = None
    baseline_n = baseline_k = 0
    baseline_sql: dict[str, Any] | None = None
    alt: AltBaseline | None = None
    if ok_events:
        dates = [str(e[1]) for e in ok_events]
        baseline_window = (min(dates), max(dates))
        bq = compiled.baseline_for(*baseline_window, event_dates=dates)
        baseline_n, baseline_k = con.execute(bq.sql, list(bq.params)).fetchone()
        baseline_sql = {"kind": compiled.baseline_kind, "sql": bq.sql, "params": list(bq.params)}

    rd = readout(
        [s for _eid, _d, s, _m in ok_events],
        baseline_n=int(baseline_n or 0),
        baseline_k=int(baseline_k or 0),
        min_n=rule.min_n,
    )
    if ok_events:
        # 另一种口径只作对照：同一事件集换个 p0，看结论会不会变——变了说明读数受择时 / 选择的混杂
        other = next(k for k in BASELINE_KINDS if k != compiled.baseline_kind)
        aq = compiled.baseline_for(*baseline_window, kind=other, event_dates=dates)
        an, ak = con.execute(aq.sql, list(aq.params)).fetchone()
        an, ak = int(an or 0), int(ak or 0)
        p0_alt = (ak / an) if an else None
        alt = AltBaseline(
            kind=other,
            n=an,
            k=ak,
            p0=p0_alt,
            lift=(rd.p - p0_alt) if (rd.p is not None and p0_alt is not None) else None,
            verdict_if_used=four_state(rd.n, rd.k, p0_alt, rd.p_first, rd.p_second, rule.min_n),
        )
    metric_rows = con.execute(compiled.metrics.sql, list(compiled.metrics.params)).fetchall()
    horizons = _summarize_horizons(metric_rows, rule.horizons)

    sample = [
        {
            "entity_id": eid,
            "trade_date": str(d),
            "success": s,
            rule.success.metric: (round(float(m), 4) if m is not None else None),
        }
        for eid, d, s, m in ok_events[:EVENT_SAMPLE_LIMIT]
    ]
    all_dates = [str(e[1]) for e in events]
    return RunResult(
        rule=rule,
        window=window,
        baseline_window=baseline_window,
        readout=rd,
        baseline_alt=alt,
        n_matched=len(events),
        n_pending=n_pending,
        n_missing=n_missing,
        first_event_date=min(all_dates) if all_dates else None,
        last_event_date=max(all_dates) if all_dates else None,
        horizons=horizons,
        conditions=conditions,
        events_sample=sample,
        sql={
            "events": {"sql": compiled.events.sql, "params": list(compiled.events.params)},
            "metrics": {"sql": compiled.metrics.sql, "params": list(compiled.metrics.params)},
            "baseline": baseline_sql,
        },
    )


def run_rule(
    con: duckdb.DuckDBPyConnection,
    rule: Rule,
    *,
    start: date | str | None = None,
    end: date | str | None = None,
    conditions: dict[str, Any] | None = None,
) -> RunResult:
    conditions = conditions or load_conditions(con)
    _check_horizons(rule, conditions)
    window = resolve_window(conditions, start, end)
    compiled = compile_rule(rule, start=window[0], end=window[1])
    return execute_compiled(con, rule, compiled, window=window, conditions=conditions)


def scan_rules(
    con: duckdb.DuckDBPyConnection,
    rules: Sequence[Rule],
    *,
    start: date | str | None = None,
    end: date | str | None = None,
    q: float = 0.05,
) -> ScanResult:
    """多条规则一起跑：每条先出单次读数，再按 BH 控制 FDR、降级未过校正的支持 / 证伪。"""
    conditions = load_conditions(con)
    results = [run_rule(con, r, start=start, end=end, conditions=conditions) for r in rules]
    p_values = [r.readout.p_value for r in results]
    testable = [i for i, p in enumerate(p_values) if p is not None]
    rejected = [False] * len(results)
    adjusted: list[float | None] = [None] * len(results)
    if testable:
        rej, adj = benjamini_hochberg([p_values[i] for i in testable], q=q)
        for j, i in enumerate(testable):
            rejected[i] = rej[j]
            adjusted[i] = adj[j]
    verdicts_bh = apply_bh_downgrade([r.readout.verdict for r in results], rejected)
    return ScanResult(
        results=results,
        p_values=p_values,
        rejected=rejected,
        adjusted_p=adjusted,
        verdicts_bh=verdicts_bh,
        q=q,
    )

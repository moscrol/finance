"""在时间长河上的三种查询形状：横扫、纵扫、区间聚合。

`river.py` 给的是**点查**——一天 × 一个实体的六维切片。真实问题基本落在另外三种形状：

- **横扫 `scan_cross_section`**：一天 × 全部实体，跨维度比较，找错位。
  例：「盘面较弱、但近期卖方覆盖多的板块」。
- **纵扫 `cohort_compare`**：一个条件筛出一批日子 × 同一个特征，与同期基准比。
  例：「MA5 波谷确认日之后，盘面阶段有没有共性」。
- **区间聚合 `range_aggregate`**：一个实体 × 一段日子，出区间涨幅 / 最大回撤 / 成交额。
  例：「算力租赁 8 月涨了多少」。

三条都**不新增存储**，都在现有事实表上现算。

区间聚合为什么不能只返回一个数
------------------------------
区间涨幅是最常被问、也最容易静默算错的量，两个坑都不报错（2026-09-06 实测）：

1. **板块没有收盘点位**。`fact_sector_daily` 只有每日 `pct_chg`，区间涨幅只能连乘。
   缺一天就少乘一天，**结果偏低而不报错**。1 个月窗口 402 个板块 0 个缺天，看着没事；
   3 个月窗口 549 个里 **431 个缺天**。窗口一拉长坑就张开。
2. **换过数据供应商**（`.TI` → `.FP`，每个板块切换日还不同）。2026-03~09 区间里
   **128 个板块名跨了两套代码**，两套成分不同——直接按名连乘等于把两个宇宙接在一起。

所以本模块的返回值**强制携带 `coverage` 与 `codes_seen`**，缺天与跨换源都写成显式
`caveats`；`require_complete=True` 时干脆不给数、只给 gap。这和 `river` 的
「缺轨返回 `Gap` 不猜」是同一条纪律：宁可说不出来，不给一个不知道偏了多少的数。

第三个坑是**列在库里但一行都没写过值**（实测 `fact_stock_daily.turnover` 非空 0 行）：
这类 SQL 跑得通、不报错、返回 NULL，看起来像「这段时间没数据」。本模块把它判成
`MetricGap` 并写明原因，不混进正常读数。

纵扫必须挂统计门，这不是可选项
--------------------------------
2026-09-05 实测：37 个 MA5 谷底确认日上，「横盘」占 27.0% vs 基准 20.6%（1.31 倍），
看着像规律；过 Wilson 之后**七个格子全部 `not_distinguishable`**——每格区间都含基准，
最大的格才 11 个样本。所以本模块不自己算显著性，直接调
``methodology_backtest.stats``（Wilson / 精确二项 / BH / 前后半段 / 四态），
与方法论回测同一条门、同一套判词，**不建第二套统计口径**。

默认输出是「不可区分」而不是规律：`four_state` 只有在 Wilson 下界高过基准、
且前后半段同向时才给 `supported`。

两个已知的读数陷阱（写在这里，因为它们会伪装成结论）
--------------------------------------------------
1. **`market_stage` 有两套写法**——「顶部横盘阶段」与「顶部横盘」、「下跌阶段」与
   「下跌」在库里各算各的。不归一，一个阶段会被劈成两格、每格样本减半，
   纵扫直接失真。本模块用 `normalize_stage` 兜住，但那只是补丁：
   正解是 roadmap G-05 归一并升 `LABEL_VERSION`。
2. **研报覆盖的累计数被回填批次污染**——469 份里 249 份（53%）在 2026-01。
   横扫一律按近 90 日覆盖排序，累计只作背景列。理由见 `river.coverage_metrics`。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from intelligence.services.methodology_backtest.stats import (
    benjamini_hochberg,
    binom_two_sided_p,
    four_state,
    split_halves,
    wilson,
)
from intelligence.services.river import (
    DEFAULT_DB,
    coverage_hits,
    coverage_metrics,
    load_reports_asof,
)

# 与 methodology_backtest 的 DEFAULT_CALIBRATION_MIN_N 同源：N < 10 不出率。
MIN_N = 10
# BH 的 FDR 水平。一次纵扫要比较七个阶段格，就是七次检验。
BH_Q = 0.05


def normalize_stage(value: Any) -> str:
    """`market_stage` 两套写法归一。「顶部横盘阶段」→「顶部横盘」。

    ⚠ 这是**读取侧的补丁**，不是修复。真正的归一要在标签层做并升
    `LABEL_VERSION`（roadmap G-05），否则每个读取方都得记得打这个补丁，
    而漏打的那个会安静地给出减半的样本。
    """
    text = str(value or "").strip()
    if not text:
        return "未知"
    return text[:-2] if text.endswith("阶段") else text


# --------------------------------------------------------------------------- #
# 横扫：一天 × 全部实体
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CrossSectionRow:
    entity_id: str
    entity_name: str
    # 盘面
    pct_chg: float | None
    diff_ratio: float | None
    amount: float | None
    strict_double_red: bool | None
    limit_up_count: int | None
    # 舆论（主口径是 count_90d）
    coverage_90d: int
    coverage_cumulative: int
    days_since_last_report: int | None
    # 资金
    fund_flow_1d: float | None
    # 跨维错位：两个维度在当日横截面里的分位差，纯算术，不是阶段判词
    market_pctile: float | None = None
    opinion_pctile: float | None = None

    @property
    def dislocation(self) -> float | None:
        """舆论分位 − 盘面分位。正 = 舆论热于盘面（喊得多、还没走）。"""
        if self.market_pctile is None or self.opinion_pctile is None:
            return None
        return round(self.opinion_pctile - self.market_pctile, 3)

    def to_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        d["dislocation"] = self.dislocation
        return d


def _pctile(values: list[float | None]) -> list[float | None]:
    """升序分位（0=最低，1=最高）。None 保持 None，不参与排名也不补零。"""
    idx = [i for i, v in enumerate(values) if v is not None]
    out: list[float | None] = [None] * len(values)
    if not idx:
        return out
    order = sorted(idx, key=lambda i: values[i])  # type: ignore[index,arg-type]
    denom = max(len(order) - 1, 1)
    for rank, i in enumerate(order):
        out[i] = round(rank / denom, 3)
    return out


def scan_cross_section(
    as_of: str, *, db_path: str | Path | None = None
) -> list[CrossSectionRow]:
    """一天 × 全部板块的跨维横截面。无 LLM，纯查询 + 算术。"""
    import duckdb

    db = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB)).expanduser()
    if not db.exists():
        raise FileNotFoundError(f"数据库不存在：{db}（不自动创建）")
    con = duckdb.connect(str(db), read_only=True)
    try:
        sectors = con.execute(
            """
            SELECT sector_ts_code, sector_name, pct_chg, diff_ratio, amount
            FROM fact_sector_daily WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
            ORDER BY sector_ts_code
            """,
            [as_of],
        ).fetchall()
        heat = dict(
            con.execute(
                """
                SELECT sector_name, MAX(limit_up_count) FROM fact_theme_limit_heat_daily
                WHERE CAST(trade_date AS DATE) = CAST(? AS DATE) GROUP BY 1
                """,
                [as_of],
            ).fetchall()
        )
        # 用 DECIMAL 求和而不是浮点：DuckDB 并行聚合的相加顺序不固定，
        # 浮点 SUM 会在最后几位飘（实测同一天两次调用差 2e-14），
        # 直接违反「同一 (T, entity) 两次调用结果相同」。DECIMAL 加法精确、与顺序无关。
        flow = {
            code: (None if total is None else float(total))
            for code, total in con.execute(
                """
                SELECT sector_ts_code, SUM(CAST(fund_flow_1d AS DECIMAL(18,4)))
                FROM fact_sector_stock_daily
                WHERE CAST(trade_date AS DATE) = CAST(? AS DATE) GROUP BY 1
                """,
                [as_of],
            ).fetchall()
        }
        reports = load_reports_asof(con, as_of)  # 一次取回，逐板块精确比对标签
        rows: list[CrossSectionRow] = []
        for code, name, pct, diff, amt in sectors:
            hits = coverage_hits(con, as_of, name, rows=reports)
            cov = coverage_metrics(hits, as_of) if hits else None
            rows.append(
                CrossSectionRow(
                    entity_id=str(code),
                    entity_name=str(name),
                    pct_chg=pct,
                    diff_ratio=diff,
                    amount=amt,
                    strict_double_red=(
                        None
                        if pct is None or diff is None or amt is None
                        else bool(pct > 0 and diff > 10 and amt > 500)
                    ),
                    limit_up_count=heat.get(name),
                    coverage_90d=cov["count_90d"] if cov else 0,
                    coverage_cumulative=cov["cumulative_count"] if cov else 0,
                    days_since_last_report=cov["days_since_last"] if cov else None,
                    fund_flow_1d=flow.get(code),
                )
            )
    finally:
        con.close()

    # 分位在当日横截面内算：跨日比较分位没有意义，所以不缓存、不跨日复用。
    mkt = _pctile([r.pct_chg for r in rows])
    # 舆论分位只在「有覆盖」的子集里排：0 份覆盖不是「舆论最冷」，是没有数据。
    op_raw: list[float | None] = [float(r.coverage_90d) if r.coverage_90d > 0 else None for r in rows]
    opn = _pctile(op_raw)
    return [
        replace(r, market_pctile=m, opinion_pctile=o)
        for r, m, o in zip(rows, mkt, opn, strict=True)
    ]


def find_dislocation(
    as_of: str,
    *,
    min_coverage_90d: int = 3,
    max_market_pctile: float = 0.4,
    db_path: str | Path | None = None,
) -> list[CrossSectionRow]:
    """盘面弱 × 舆论热的板块。两个阈值都显式传，不藏默认判词。

    ``min_coverage_90d`` 用近 90 日覆盖而不是累计——累计被回填批次污染（见模块注释）。
    """
    rows = scan_cross_section(as_of, db_path=db_path)
    hit = [
        r
        for r in rows
        if r.coverage_90d >= min_coverage_90d
        and r.market_pctile is not None
        and r.market_pctile <= max_market_pctile
    ]
    hit.sort(key=lambda r: (-(r.dislocation or 0), -r.coverage_90d))
    return hit


# --------------------------------------------------------------------------- #
# 纵扫：一批日子 × 一个特征，挂统计门
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CohortCell:
    value: str
    k: int
    n: int
    rate: float
    baseline: float
    wilson_lo: float
    wilson_hi: float
    p_value: float
    p_adjusted: float
    rate_first_half: float | None
    rate_second_half: float | None
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


@dataclass(frozen=True)
class CohortReport:
    feature: str
    cohort_size: int
    baseline_size: int
    cells: list[CohortCell] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "cohort_size": self.cohort_size,
            "baseline_size": self.baseline_size,
            "cells": [c.to_dict() for c in self.cells],
            "notes": list(self.notes),
        }


def cohort_compare(
    dates: list[str],
    *,
    feature: str = "market_stage",
    db_path: str | Path | None = None,
) -> CohortReport:
    """把一批日子的某个盘面特征，与全样本基准比，逐格给四态判词。

    判词来自 `methodology_backtest.stats.four_state`：``insufficient_n`` /
    ``not_distinguishable`` / ``supported`` / ``refuted``。**这里不会因为倍数好看
    就说「有规律」**——Wilson 下界不超过基准、或前后半段不同向，一律
    ``not_distinguishable``。

    BH 校正跨本次所有格子做：一次比七个阶段就是七次检验，不校正必然刷出假阳性。
    """
    import duckdb

    db = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB)).expanduser()
    if not db.exists():
        raise FileNotFoundError(f"数据库不存在：{db}（不自动创建）")
    if feature not in {"market_stage", "volume_state", "concentration_state"}:
        raise ValueError(f"未知特征 {feature}（只接受 fact_market_daily 上的类别列）")

    con = duckdb.connect(str(db), read_only=True)
    try:
        base_rows = con.execute(
            f"SELECT CAST(trade_date AS DATE), {feature} FROM fact_market_daily ORDER BY trade_date"  # noqa: S608
        ).fetchall()
    finally:
        con.close()

    by_date = {str(d): normalize_stage(v) for d, v in base_rows}
    wanted = [d for d in sorted(dates) if d in by_date]
    missing = sorted(set(dates) - set(by_date))
    notes: list[str] = []
    if missing:
        notes.append(f"{len(missing)} 个日期在 fact_market_daily 里没有行，已剔除：{missing[:5]}")
    if len(wanted) < MIN_N:
        notes.append(f"队列只有 {len(wanted)} 天，低于 MIN_N={MIN_N}，所有格必为 insufficient_n")

    n = len(wanted)
    baseline_n = len(by_date)
    cohort_vals = [by_date[d] for d in wanted]  # 已按日期升序 → 前后半段可切
    all_vals = list(by_date.values())

    values = sorted(set(cohort_vals))
    cells_raw: list[tuple[str, int, float, float | None, float | None, float]] = []
    for value in values:
        k = sum(1 for v in cohort_vals if v == value)
        p0 = sum(1 for v in all_vals if v == value) / baseline_n if baseline_n else 0.0
        flags = [v == value for v in cohort_vals]
        first, second = split_halves(flags)
        r1 = (sum(first) / len(first)) if first else None
        r2 = (sum(second) / len(second)) if second else None
        cells_raw.append((value, k, p0, r1, r2, binom_two_sided_p(k, n, p0)))

    rejected, adjusted = benjamini_hochberg([c[5] for c in cells_raw], q=BH_Q)
    cells: list[CohortCell] = []
    for (value, k, p0, r1, r2, p), padj, ok in zip(cells_raw, adjusted, rejected, strict=True):
        lo, hi = wilson(k, n)
        verdict = four_state(n, k, p0, r1, r2, MIN_N)
        # `stats.four_state` 的签名里没有 p——它只看 Wilson 下界与前后半段，
        # **不做多重检验校正**。一次比七个阶段就是七次检验，只靠它必然刷假阳性：
        # 实测随机 37 天的队列 5 次里有 1 次刷出 `supported`（BH p=0.185）。
        # 所以这里把 BH 拒绝作为出结论的**附加必要条件**，不是替代——
        # 两道都过才算数，任一不过一律降回 not_distinguishable。
        if verdict in {"supported", "refuted"} and not ok:
            verdict = "not_distinguishable"
        cells.append(
            CohortCell(
                value=value,
                k=k,
                n=n,
                rate=round(k / n, 4) if n else 0.0,
                baseline=round(p0, 4),
                wilson_lo=round(lo, 4),
                wilson_hi=round(hi, 4),
                p_value=round(p, 4),
                p_adjusted=round(padj, 4),
                rate_first_half=None if r1 is None else round(r1, 4),
                rate_second_half=None if r2 is None else round(r2, 4),
                verdict=verdict,
            )
        )
    cells.sort(key=lambda c: -c.k)
    return CohortReport(
        feature=feature, cohort_size=n, baseline_size=baseline_n, cells=cells, notes=notes
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def render_scan(rows: list[CrossSectionRow], as_of: str) -> str:
    out = [f"as_of={as_of}  盘面弱 × 舆论热（近 90 日覆盖为准，累计仅作背景）", ""]
    out.append(
        f"  {'板块':<14}{'涨幅%':>8}{'边际量%':>9}{'盘面分位':>9}"
        f"{'近90日':>7}{'累计':>6}{'距上次':>7}{'错位':>7}"
    )
    for r in rows[:20]:
        out.append(
            f"  {r.entity_name:<14}{_f(r.pct_chg):>8}{_f(r.diff_ratio):>9}"
            f"{_f(r.market_pctile):>9}{r.coverage_90d:>7}{r.coverage_cumulative:>6}"
            f"{r.days_since_last_report if r.days_since_last_report is not None else '—':>7}"
            f"{_f(r.dislocation):>7}"
        )
    if not rows:
        out.append("  （没有板块同时满足两个阈值——这是读数，不是失败）")
    return "\n".join(out)


def _f(v: Any) -> str:
    return "—" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))


def render_cohort(rep: CohortReport) -> str:
    out = [
        f"特征={rep.feature}  队列={rep.cohort_size} 天  基准={rep.baseline_size} 天  "
        f"（MIN_N={MIN_N}，BH 跨 {len(rep.cells)} 格校正）",
        "",
        f"  {'取值':<10}{'队列':>7}{'占比':>8}{'基准':>8}{'Wilson 95%':>18}"
        f"{'BH p':>8}{'前半':>7}{'后半':>7}  判词",
    ]
    for c in rep.cells:
        # 前后半段必须显示：`four_state` 只有在两半同向时才给结论，看不到这两列
        # 就没法复核「为什么是 not_distinguishable」——是区间盖住基准，还是两半打架。
        half = lambda v: "—" if v is None else f"{v:.0%}"  # noqa: E731
        out.append(
            f"  {c.value:<10}{c.k:>3}/{c.n:<3}{c.rate:>8.1%}{c.baseline:>8.1%}"
            f"{f'[{c.wilson_lo:.1%},{c.wilson_hi:.1%}]':>18}{c.p_adjusted:>8.3f}"
            f"{half(c.rate_first_half):>7}{half(c.rate_second_half):>7}  {c.verdict}"
        )
    for note in rep.notes:
        out.append(f"  ⚠ {note}")
    verdicts = {c.verdict for c in rep.cells}
    if verdicts <= {"not_distinguishable", "insufficient_n"}:
        out.append("")
        out.append("  结论：没有任何一格与基准可区分——这个问题目前答不了，不是答案是「没规律」。")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# 区间聚合：一个实体 × 一段日子
# --------------------------------------------------------------------------- #
# 个股与板块的算法**必须不同**，因为可得的原料不同：
#   个股 `fact_stock_daily` 有 close / pre_close → 首尾直接相除，精确；
#   板块 `fact_sector_daily` **没有点位**，只有每日 pct_chg → 只能连乘。
# 把两者混成一个「区间涨幅」函数、内部偷偷用连乘，是最容易过审但最错的做法：
# 个股本来能精确算，连乘会引入完全不必要的缺天误差。
STOCK_METHOD = "close_to_close"
SECTOR_METHOD = "compounded_daily"

RANGE_METRICS: tuple[str, ...] = (
    "cumulative_return_pct",
    "max_drawdown_pct",
    "peak_return_pct",
    "amount_sum",
    "amount_avg",
    "turnover_avg",
)


@dataclass(frozen=True)
class RangeCoverage:
    """区间里**应该**有几个交易日、**实际**读到几个、缺了哪些。

    `expected` 取自 `fact_market_daily`——它是库里唯一的交易日历。缺天数不是
    附注，是判断这个数能不能用的前提，所以进主结构而不是日志。
    """

    expected_days: int
    actual_days: int
    missing_dates: tuple[str, ...] = ()
    # 同一天读到多行。连乘一旦按行遍历就会把那天乘两次：三天各 +10% 本该 33.1%，
    # 多乘一天变成 46.41%（1.1**4）。而 actual_days 数的是**去重日期**，
    # 所以覆盖率照样报「完整」——错得又大又安静，正是最该拦的形状。
    duplicate_dates: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return self.expected_days > 0 and self.actual_days == self.expected_days

    @property
    def clean(self) -> bool:
        """既不缺天也不重复。``complete`` 只回答缺不缺，回答不了重不重。"""
        return self.complete and not self.duplicate_dates

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_days": self.expected_days,
            "actual_days": self.actual_days,
            "complete": self.complete,
            "clean": self.clean,
            "missing_dates": list(self.missing_dates),
            "duplicate_dates": list(self.duplicate_dates),
        }


@dataclass(frozen=True)
class MetricGap:
    """某个量算不出来，且**说明为什么**。不要用 None 冒充 0，也不要用 0 冒充没数据。"""

    metric: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"metric": self.metric, "reason": self.reason}


@dataclass(frozen=True)
class RangeAggregate:
    kind: str  # stock | sector
    entity_id: str
    entity_name: str
    start: str
    end: str
    method: str
    coverage: RangeCoverage
    codes_seen: tuple[str, ...] = ()
    values: dict[str, float | None] = field(default_factory=dict)
    peak_date: str | None = None
    gaps: tuple[MetricGap, ...] = ()
    caveats: tuple[str, ...] = ()

    @property
    def trustworthy(self) -> bool:
        """能不能直接拿去用：覆盖**干净**（不缺天且无重复）且没跨过换源日。

        用 ``clean`` 而不是 ``complete``：同一天重复时 ``complete`` 仍为真
        （它数的是去重日期），于是一个被多乘过的数会自称「数据完整、结果可信」。
        """
        return self.coverage.clean and len(self.codes_seen) <= 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "start": self.start,
            "end": self.end,
            "method": self.method,
            "trustworthy": self.trustworthy,
            "coverage": self.coverage.to_dict(),
            "codes_seen": list(self.codes_seen),
            "values": self.values,
            "peak_date": self.peak_date,
            "gaps": [g.to_dict() for g in self.gaps],
            "caveats": list(self.caveats),
        }


def trading_days(con: Any, start: str, end: str) -> list[str]:
    """区间内的交易日（`fact_market_daily` 是库里唯一的交易日历）。"""
    rows = con.execute(
        "SELECT DISTINCT CAST(trade_date AS DATE) d FROM fact_market_daily "
        "WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE) ORDER BY d",
        [start, end],
    ).fetchall()
    return [str(r[0]) for r in rows]


def _drawdown_and_peak(curve: list[tuple[str, float]]) -> tuple[float | None, float | None, str | None]:
    """从累计收益曲线（相对起点的倍数）算最大回撤与峰值。曲线不足两点时不出数。"""
    if len(curve) < 2:
        return None, None, None
    peak_v, peak_d, max_dd = curve[0][1], curve[0][0], 0.0
    for day, value in curve:
        if value > peak_v:
            peak_v, peak_d = value, day
        if peak_v > 0:
            max_dd = min(max_dd, value / peak_v - 1.0)
    return round(max_dd * 100, 4), round((peak_v - 1.0) * 100, 4), peak_d


def _stock_rows(con: Any, start: str, end: str, entity: str) -> list[dict[str, Any]]:
    return _rows_dict(
        con,
        """
        SELECT CAST(trade_date AS DATE) AS d, stock_ts_code, stock_name,
               close, pre_close, amount, turnover
        FROM fact_stock_daily
        WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
          AND (stock_ts_code = ? OR stock_name = ?)
        ORDER BY d
        """,
        [start, end, entity, entity],
    )


def _sector_rows(con: Any, start: str, end: str, entity: str) -> list[dict[str, Any]]:
    # 按**名字**取而不是代码：代码会随供应商换代，名字不会——这也是为什么必须
    # 把 codes_seen 摆出来，让调用方看见这段区间横跨了几套代码。
    return _rows_dict(
        con,
        """
        SELECT CAST(trade_date AS DATE) AS d, sector_ts_code, sector_name,
               pct_chg, amount
        FROM fact_sector_daily
        WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
          AND (sector_name = ? OR sector_ts_code = ?)
        ORDER BY d
        """,
        [start, end, entity, entity],
    )


def _dedupe_by_date(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """一天只留一行，并把出现重复的日子报出来。

    为什么不静默去重：同一天两行、值还不一样时，**没有依据判断哪一行是对的**。
    去重只是止血（不让它重复连乘），不代表结果可信——所以重复日期一并返回，
    由调用方标成 caveat 并把 ``trustworthy`` 判否。

    留哪一行：按 ``(日期, 行内容的稳定序列化)`` 排序后取第一条。这个选择是**任意但确定**的
    ——任意是因为确实无从判断，确定是因为「两次调用结果相同」那条验收不能因它变假绿。
    """
    seen: dict[str, dict[str, Any]] = {}
    dups: set[str] = set()
    for row in sorted(rows, key=lambda r: (str(r["d"]), json.dumps(r, ensure_ascii=False, sort_keys=True, default=str))):
        day = str(row["d"])
        if day in seen:
            dups.add(day)
            continue
        seen[day] = row
    return [seen[d] for d in sorted(seen)], tuple(sorted(dups))


def _rows_dict(con: Any, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    cur = con.execute(sql, params)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def _agg_numeric(rows: list[dict[str, Any]], key: str) -> tuple[float | None, float | None, int]:
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    if not vals:
        return None, None, 0
    return round(sum(vals), 4), round(sum(vals) / len(vals), 4), len(vals)


def range_aggregate(
    start: str,
    end: str,
    entity: str,
    *,
    kind: str | None = None,
    db_path: str | Path | None = None,
    require_complete: bool = False,
) -> RangeAggregate:
    """一个实体在 ``[start, end]`` 上的区间读数。

    ``require_complete=True``：覆盖不完整或跨过换源日时**不给数**，只给 gap
    ——回放、校准、方法检验这类不能吃「偏低但不知道偏多少」的消费方必须传它。
    与 `river.slice_river(require_strict=True)` 是同一个态度，参数名也照它。

    个股走 ``close_to_close``（精确），板块走 ``compounded_daily``（连乘，缺天会偏低）。
    """
    import duckdb

    db = Path(db_path or os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB)).expanduser()
    if not db.exists():
        raise FileNotFoundError(f"数据库不存在：{db}（不自动创建）")

    con = duckdb.connect(str(db), read_only=True)
    try:
        expected = trading_days(con, start, end)
        rows = _stock_rows(con, start, end, entity) if kind == "stock" else []
        if not rows and kind != "stock":
            rows = _sector_rows(con, start, end, entity)
            resolved_kind = "sector"
        else:
            resolved_kind = "stock"
        if not rows and kind is None:
            rows = _stock_rows(con, start, end, entity)
            resolved_kind = "stock" if rows else "sector"
    finally:
        con.close()

    # 先去重再算任何东西：下面的连乘、首尾取值、回撤曲线全都按行遍历，
    # 重复行会被算两遍。codes_seen 用**去重前**的行，跨换源检测不受影响。
    all_rows = rows
    rows, duplicate_dates = _dedupe_by_date(rows) if rows else ([], ())
    coverage = RangeCoverage(
        expected_days=len(expected),
        actual_days=len({str(r["d"]) for r in rows}),
        missing_dates=tuple(sorted(set(expected) - {str(r["d"]) for r in rows})),
        duplicate_dates=duplicate_dates,
    )
    if not rows:
        return RangeAggregate(
            kind=resolved_kind,
            entity_id=entity,
            entity_name=entity,
            start=start,
            end=end,
            method="none",
            coverage=coverage,
            gaps=(MetricGap("*", f"{start}~{end} 区间内读不到「{entity}」的任何行"),),
        )

    code_key = "stock_ts_code" if resolved_kind == "stock" else "sector_ts_code"
    name_key = "stock_name" if resolved_kind == "stock" else "sector_name"
    # 用去重**前**的行：去重可能恰好丢掉换源那一侧的代码，那就检测不出跨换源了。
    codes_seen = tuple(sorted({str(r[code_key]) for r in all_rows if r.get(code_key)}))
    entity_name = str(rows[-1].get(name_key) or entity)

    gaps: list[MetricGap] = []
    caveats: list[str] = []
    values: dict[str, float | None] = {}
    peak_date: str | None = None

    if resolved_kind == "stock":
        method = STOCK_METHOD
        first = next((r for r in rows if r.get("pre_close")), None)
        last = next((r for r in reversed(rows) if r.get("close")), None)
        if first and last and float(first["pre_close"]):
            base = float(first["pre_close"])
            values["cumulative_return_pct"] = round((float(last["close"]) / base - 1) * 100, 4)
            curve = [(str(r["d"]), float(r["close"]) / base) for r in rows if r.get("close")]
            dd, peak, peak_date = _drawdown_and_peak(curve)
            values["max_drawdown_pct"], values["peak_return_pct"] = dd, peak
        else:
            gaps.append(MetricGap("cumulative_return_pct", "区间内没有可用的 close / pre_close"))
    else:
        method = SECTOR_METHOD
        daily = [(str(r["d"]), float(r["pct_chg"])) for r in rows if r.get("pct_chg") is not None]
        if daily:
            curve, level = [], 1.0
            for day, pct in daily:
                level *= 1 + pct / 100.0
                curve.append((day, level))
            values["cumulative_return_pct"] = round((level - 1) * 100, 4)
            dd, peak, peak_date = _drawdown_and_peak([(daily[0][0], 1.0), *curve])
            values["max_drawdown_pct"], values["peak_return_pct"] = dd, peak
            caveats.append(
                "板块无收盘点位，区间涨幅由每日涨幅连乘得到；缺一天就少乘一天，结果偏低且不报错"
            )
        else:
            gaps.append(MetricGap("cumulative_return_pct", "区间内 pct_chg 全为空"))

    for metric, column in (("amount_sum", "amount"), ("amount_avg", "amount"), ("turnover_avg", "turnover")):
        if column not in rows[0]:
            gaps.append(MetricGap(metric, f"本表没有 {column} 列"))
            continue
        total, avg, n = _agg_numeric(rows, column)
        if n == 0:
            # 列在库里但一行都没写过值：SQL 跑得通、不报错、返回 NULL，
            # 看起来像「这段时间没数据」。实测 fact_stock_daily.turnover 全库非空 0 行。
            gaps.append(MetricGap(metric, f"{column} 列存在但区间内 0 行有值（写入侧从未填充）"))
            continue
        values[metric] = total if metric.endswith("_sum") else avg

    if not coverage.complete:
        caveats.append(
            f"覆盖不完整：应有 {coverage.expected_days} 个交易日、实读 {coverage.actual_days} 个"
            f"（缺 {len(coverage.missing_dates)} 天）"
        )
    if coverage.duplicate_dates:
        caveats.append(
            f"同一天读到多行：{'、'.join(coverage.duplicate_dates)}（共 {len(coverage.duplicate_dates)} 天）。"
            "已按日去重止血，但无从判断哪一行是对的——这个数不可直接使用，先查数据源"
        )
    if len(codes_seen) > 1:
        caveats.append(
            f"区间跨过供应商换源：读到 {len(codes_seen)} 套代码 {codes_seen}，"
            "两套口径成分不同，连乘等于把两个宇宙接在一起"
        )

    if require_complete and not (coverage.clean and len(codes_seen) <= 1):
        gaps.append(
            MetricGap(
                "*",
                "require_complete=True：覆盖不完整 / 同日重复 / 跨换源，本层不给数（缺口见 caveats）",
            )
        )
        values = dict.fromkeys(values, None)
        peak_date = None

    return RangeAggregate(
        kind=resolved_kind,
        entity_id=codes_seen[-1] if codes_seen else entity,
        entity_name=entity_name,
        start=start,
        end=end,
        method=method,
        coverage=coverage,
        codes_seen=codes_seen,
        values=values,
        peak_date=peak_date,
        gaps=tuple(gaps),
        caveats=tuple(caveats),
    )


def render_range(agg: RangeAggregate) -> str:
    """人读版。**caveats 与 gaps 永远打印**——它们被折叠掉的那一刻，这个数就变危险了。"""
    head = f"{agg.entity_name}（{agg.entity_id}）  {agg.start} ~ {agg.end}  [{agg.kind}/{agg.method}]"
    cov = agg.coverage
    out = [
        head,
        f"  覆盖 {cov.actual_days}/{cov.expected_days} 个交易日"
        + ("" if cov.complete else f"，缺 {len(cov.missing_dates)} 天")
        + ("" if not cov.duplicate_dates else f"，{len(cov.duplicate_dates)} 天有重复行")
        + (f"｜代码 {'/'.join(agg.codes_seen)}" if agg.codes_seen else ""),
        f"  可直接使用：{'是' if agg.trustworthy else '否——先看下面的限制'}",
        "",
    ]
    for key in RANGE_METRICS:
        if key in agg.values:
            v = agg.values[key]
            tail = f"（峰值日 {agg.peak_date}）" if key == "peak_return_pct" and agg.peak_date else ""
            out.append(f"  {key:<22} {'—' if v is None else f'{v:+.2f}'}{tail}")
    if agg.gaps:
        out += ["", "  算不出来的："] + [f"    - {g.metric}：{g.reason}" for g in agg.gaps]
    if agg.caveats:
        out += ["", "  限制："] + [f"    - {c}" for c in agg.caveats]
    return "\n".join(out)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="时间长河查询：横扫 / 纵扫 / 区间聚合")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("range", help="区间聚合：一个实体 × 一段日子（涨幅 / 回撤 / 成交额）")
    r.add_argument("entity", help="板块名 / 题材名 / 个股代码或名称")
    r.add_argument("start")
    r.add_argument("end")
    r.add_argument("--kind", choices=["stock", "sector"], default=None, help="缺省自动判别")
    r.add_argument(
        "--require-complete",
        action="store_true",
        help="覆盖不完整或跨换源时不给数、只给 gap（回放 / 校准必须带）",
    )
    r.add_argument("--json", action="store_true")

    s = sub.add_parser("scan", help="横扫：一天 × 全部板块，找盘面弱 × 舆论热")
    s.add_argument("as_of")
    s.add_argument("--min-coverage-90d", type=int, default=3)
    s.add_argument("--max-market-pctile", type=float, default=0.4)
    s.add_argument("--json", action="store_true")

    c = sub.add_parser("cohort", help="纵扫：一批日子 × 一个特征，挂统计门")
    c.add_argument("dates", nargs="+", help="日期列表，或 @文件（每行一个日期）")
    c.add_argument("--feature", default="market_stage")
    c.add_argument("--json", action="store_true")

    args = ap.parse_args()
    if args.cmd == "range":
        agg = range_aggregate(
            args.start, args.end, args.entity,
            kind=args.kind, require_complete=args.require_complete,
        )
        print(json.dumps(agg.to_dict(), ensure_ascii=False, indent=2) if args.json else render_range(agg))
        return 0

    if args.cmd == "scan":
        rows = find_dislocation(
            args.as_of,
            min_coverage_90d=args.min_coverage_90d,
            max_market_pctile=args.max_market_pctile,
        )
        print(
            json.dumps([r.to_dict() for r in rows], ensure_ascii=False, indent=2)
            if args.json
            else render_scan(rows, args.as_of)
        )
        return 0

    dates: list[str] = []
    for token in args.dates:
        if token.startswith("@"):
            dates.extend(
                line.strip() for line in Path(token[1:]).read_text(encoding="utf-8").splitlines() if line.strip()
            )
        else:
            dates.append(token)
    rep = cohort_compare(dates, feature=args.feature)
    print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2) if args.json else render_cohort(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

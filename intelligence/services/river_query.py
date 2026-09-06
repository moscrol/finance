"""在时间长河上的两种查询形状：横扫与纵扫。

`river.py` 给的是**点查**——一天 × 一个实体的六维切片。真实问题基本落在另外两种形状：

- **横扫 `scan_cross_section`**：一天 × 全部实体，跨维度比较，找错位。
  例：「盘面较弱、但近期卖方覆盖多的板块」。
- **纵扫 `cohort_compare`**：一个条件筛出一批日子 × 同一个特征，与同期基准比。
  例：「MA5 波谷确认日之后，盘面阶段有没有共性」。

两条都**不新增存储**，都在现有事实表上现算。

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


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="时间长河查询：横扫 / 纵扫")
    sub = ap.add_subparsers(dest="cmd", required=True)

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

#!/usr/bin/env python3
"""回补验收：目标日与「最近 N 个完整交易日」基线逐项对齐（只读，零网络）。

同一天的两道门（check_daily_review_data / check-daily）回答「有没有」；本脚本回答
「像不像之前」——行数、来源语义、链式一致、金额量纲、字段空值、双红名单。2026-09-07
的 09-03 回补就是行数过门、值是空壳（fact_market_daily 全 NULL 还标 ✅）才立的这道。

    python3 skills/duckdb-backfill/scripts/qa_backfill_align.py 2026-09-03 2026-09-04
    python3 skills/duckdb-backfill/scripts/qa_backfill_align.py 2026-09-03 --baseline 6 --json /tmp/qa.json

退出码：0 = PASS（无 FAIL 项，WARN 允许）；2 = FAIL；3 = BLOCKED（写锁占用，检查未执行）。
只读连接，写进程在跑时等锁而不是误报缺数（与 check_daily_review_data 同一语义）。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXIT_FAIL = 2
EXIT_BLOCKED = 3

# 阈值都放这里，改口径改一处。
CONSTANT_UNIVERSE_MIN_RATIO = 0.98  # 宇宙恒定表（板块/申万/全A/…）行数 ≥ 基线中位 × 0.98
VOLATILE_SHRINK_RATIO = 0.5  # 随行情波动的表，收缩到中位一半以下只 WARN（同 quality.ROW_SHRINK_RATIO）
FEATURE_MIN_RATIO = 0.95  # 派生层行数低于基线 95% → 半成品上算的，必须重算
NULL_DRIFT_PP = 10.0  # 非价格列空值率偏离基线均值 > 10pp → WARN
PRICE_NULL_PP = 0.5  # 价格类列（close/pre_close/pct_chg/amount/price）空值率高于基线 0.5pp → FAIL
PCT_RECALC_TOL = 0.05  # |pct_chg − (close/pre_close−1)×100| 容差（百分点）
PRE_CLOSE_TOL = 0.011  # pre_close 与前一交易日 close 的容差（元，绕开浮点尾数）
PCT_RECALC_FAIL_RATIO = 0.001  # 个股 pct_chg 重算不符占比 > 0.1% → FAIL
RATIO_BAND_PAD = 0.02  # 金额量纲比允许比基线区间再宽 ±0.02
SECTOR_PAYLOAD_TOL = 0.05  # 板块日线 pct_chg 与 sectors/search payload 的容差
PRICE_COLUMNS = {"close", "pre_close", "pct_chg", "amount", "price"}
# 「取最新」语义的来源：只有在交易日当天写的才是真值，写到历史日 = 盘中/次日数据污染。
LATEST_SNAPSHOT_SOURCES = {
    "fact_stock_daily": ("source = 'eastmoney:snapshot'",),
    "fact_sw_l1_daily": ("source LIKE '%realtime%'",),
}


def _load_gate_module():
    """复用 same-day gate 的表清单/字段清单，不再抄一份（单一真本源）。"""
    path = ROOT / "scripts" / "check_daily_review_data.py"
    spec = importlib.util.spec_from_file_location("check_daily_review_data", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Report:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, level: str, date_str: str, check: str, message: str) -> None:
        self.items.append({"level": level, "date": date_str, "check": check, "message": message})
        print(f"[{level}] {date_str} {check}: {message}", flush=True)

    def fail(self, d: str, check: str, msg: str) -> None:
        self.add("FAIL", d, check, msg)

    def warn(self, d: str, check: str, msg: str) -> None:
        self.add("WARN", d, check, msg)

    def ok(self, d: str, check: str, msg: str) -> None:
        self.add("PASS", d, check, msg)

    def info(self, d: str, check: str, msg: str) -> None:
        self.add("INFO", d, check, msg)

    @property
    def failed(self) -> bool:
        return any(i["level"] == "FAIL" for i in self.items)


def _date_column(table: str, gate) -> str:
    return gate.DATE_COLUMNS.get(table, "trade_date")


def pick_baseline(con, before: str, n: int) -> list[str]:
    """基线 = before 之前最近 n 个「完整日」：市场行有量能、成分表有行。"""
    rows = con.execute(
        """
        SELECT CAST(m.trade_date AS VARCHAR)
        FROM fact_market_daily m
        WHERE m.trade_date < ? AND m.total_amount IS NOT NULL AND m.advancers IS NOT NULL
          AND EXISTS (SELECT 1 FROM fact_sector_stock_daily s WHERE s.trade_date = m.trade_date)
        ORDER BY m.trade_date DESC LIMIT ?
        """,
        [before, n],
    ).fetchall()
    return sorted(r[0] for r in rows)


def counts_by_date(con, table: str, col: str, dates: list[str]) -> dict[str, int]:
    placeholders = ",".join("?" for _ in dates)
    rows = con.execute(
        f"SELECT CAST({col} AS VARCHAR), COUNT(*) FROM {table} WHERE {col} IN ({placeholders}) GROUP BY 1",
        dates,
    ).fetchall()
    out = {d: 0 for d in dates}
    out.update({d: int(n) for d, n in rows})
    return out


def check_rows(con, rep: Report, gate, quality, target: str, baseline: list[str]) -> None:
    tables = list(dict.fromkeys([*gate.TABLES, "fact_sector_universe_daily", *quality.GAP_TABLES]))
    constant = set(quality.ROW_ANOMALY_TABLES) | {"fact_sector_universe_daily"}
    for table in tables:
        col = _date_column(table, gate)
        try:
            counts = counts_by_date(con, table, col, [*baseline, target])
        except Exception as exc:  # noqa: BLE001
            rep.warn(target, "rows", f"{table} 无法统计: {str(exc)[:80]}")
            continue
        base = [counts[d] for d in baseline]
        med = median(base) if base else 0
        cur = counts[target]
        if med == 0:
            continue
        if cur == 0:
            rep.fail(target, "rows", f"{table} 0 行（基线中位 {med:.0f}）")
        elif table in constant and cur < med * CONSTANT_UNIVERSE_MIN_RATIO:
            rep.fail(target, "rows", f"{table} {cur} 行 < 基线中位 {med:.0f} × {CONSTANT_UNIVERSE_MIN_RATIO}")
        elif table.startswith("feature_") or table == "fact_sector_period_rank_daily":
            if cur < med * FEATURE_MIN_RATIO:
                rep.warn(target, "features", f"{table} {cur} 行 < 基线中位 {med:.0f} × {FEATURE_MIN_RATIO}——半成品上算的，回补完必须重跑 compute_features")
        elif cur < med * VOLATILE_SHRINK_RATIO:
            rep.warn(target, "rows", f"{table} {cur} 行 < 基线中位 {med:.0f} × {VOLATILE_SHRINK_RATIO}")


def check_market_row(con, rep: Report, gate, target: str) -> bool:
    cur = con.execute("SELECT * FROM fact_market_daily WHERE trade_date = ?", [target])
    values = cur.fetchone()
    if values is None:
        rep.fail(target, "market", "fact_market_daily 无当日行")
        return False
    row = {c[0]: v for c, v in zip(cur.description, values)}
    empty = [f for f in gate.MARKET_FIELDS if gate.is_null(row.get(f))]
    if empty:
        rep.fail(
            target,
            "market-hollow",
            f"fact_market_daily 空壳：{len(empty)}/{len(gate.MARKET_FIELDS)} 字段为空（{', '.join(empty[:6])}…）"
            "——sync-market-overview 撞 429 会整行写 NULL 还报 ok，写完必须回读",
        )
    else:
        rep.ok(target, "market", "fact_market_daily 字段齐全")
    return True


def check_calendar_side_effect(con, rep: Report, quality, target: str, has_market_row: bool) -> None:
    """有日历行（fact_market_daily）而 GAP_TABLES 缺行：check-daily 的 20 日日历会把它算成断档，
    夜跑 cross-day-gate FAIL → S7 不换名。头部模块（market-overview/index-daily）必须最后写。"""
    if not has_market_row:
        return
    missing = []
    for table in quality.GAP_TABLES:
        n = con.execute(f"SELECT COUNT(*) FROM {table} WHERE trade_date = ?", [target]).fetchone()[0]
        if not n:
            missing.append(table)
    if missing:
        rep.fail(
            target,
            "calendar",
            f"fact_market_daily 已有 {target} 行，但 {len(missing)} 张 GAP_TABLES 无行（{', '.join(missing[:5])}…）"
            "——今晚 check-daily 会把它算断档并连坐夜跑不换名",
        )


def check_latest_snapshot_sources(con, rep: Report, target: str) -> None:
    for table, predicates in LATEST_SNAPSHOT_SOURCES.items():
        for pred in predicates:
            n, wrote_same_day = con.execute(
                f"""
                SELECT COUNT(*), COUNT(*) FILTER (WHERE CAST(updated_at AS DATE) = trade_date)
                FROM {table} WHERE trade_date = ? AND ({pred})
                """,
                [target],
            ).fetchone()
            if n and wrote_same_day < n:
                rep.fail(
                    target,
                    "source-semantics",
                    f"{table} 有 {n - wrote_same_day} 行「取最新」来源（{pred}）不是交易日当天写的"
                    "——历史日只能用日期参数化源（mootdx / index_hist_sw / 东财 hist kline）",
                )


def check_sources(con, rep: Report, target: str, baseline: list[str]) -> None:
    for table in ("fact_stock_daily", "fact_sector_daily", "fact_sw_l1_daily", "fact_sector_stock_daily"):
        rows = con.execute(
            f"SELECT COALESCE(source, '<null>'), COUNT(*) FROM {table} WHERE trade_date = ? GROUP BY 1 ORDER BY 2 DESC",
            [target],
        ).fetchall()
        if not rows:
            continue
        base_sources = {
            r[0]
            for r in con.execute(
                f"SELECT DISTINCT COALESCE(source, '<null>') FROM {table} WHERE trade_date IN ({','.join('?' for _ in baseline)})",
                baseline,
            ).fetchall()
        }
        # 申万 source 带行业代码后缀，按前缀归一
        norm = lambda s: s.rsplit(":", 1)[0] if s.startswith("akshare:index_") else s  # noqa: E731
        new = sorted({norm(s) for s, _ in rows} - {norm(s) for s in base_sources})
        desc = ", ".join(f"{s}={n}" for s, n in rows[:4])
        if new:
            rep.info(target, "source", f"{table} 来源与基线不同：{desc}（基线未见 {', '.join(new)}）——语义差异见 runbook「已知语义坑」")
        else:
            rep.ok(target, "source", f"{table} 来源同基线：{desc}")


def check_stock_chain(con, rep: Report, target: str, baseline: list[str]) -> None:
    def stats(d: str):
        prev = con.execute("SELECT MAX(trade_date) FROM fact_stock_daily WHERE trade_date < ?", [d]).fetchone()[0]
        if prev is None:
            return None
        return con.execute(
            """
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE p.close IS NOT NULL AND ABS(c.pre_close - p.close) > ?),
                   COUNT(*) FILTER (WHERE c.pre_close > 0 AND ABS(c.pct_chg - (c.close / c.pre_close - 1) * 100) > ?),
                   COUNT(*) FILTER (WHERE POSITION(chr(0) IN c.stock_name) > 0),
                   COUNT(*) FILTER (WHERE c.close IS NULL OR c.pct_chg IS NULL OR c.amount IS NULL OR c.amount <= 0)
            FROM fact_stock_daily c
            LEFT JOIN fact_stock_daily p ON p.stock_ts_code = c.stock_ts_code AND p.trade_date = ?
            WHERE c.trade_date = ?
            """,
            [PRE_CLOSE_TOL, PCT_RECALC_TOL, prev, d],
        ).fetchone()

    cur = stats(target)
    if not cur or not cur[0]:
        return
    n, pre_mis, pct_mis, nul_names, bad_vals = cur
    base_pre_rates, base_bad = [], []
    for d in baseline:
        s = stats(d)
        if s and s[0]:
            base_pre_rates.append(s[1] / s[0])
            base_bad.append(s[4])
    if pct_mis / n > PCT_RECALC_FAIL_RATIO:
        rep.fail(target, "stock-chain", f"fact_stock_daily pct_chg 重算不符 {pct_mis}/{n}")
    # 停牌股 amount=0/NULL 每天都有几只；只有明显多于基线才是抓取问题
    bad_allow = max(base_bad) + 3 if base_bad else 3
    if bad_vals > bad_allow:
        rep.fail(target, "stock-values", f"fact_stock_daily {bad_vals} 行 close/pct_chg/amount 空或 amount<=0（基线最多 {max(base_bad) if base_bad else 0}）")
    if nul_names:
        rep.fail(target, "stock-names", f"fact_stock_daily {nul_names} 行 stock_name 带 \\x00 填充（mootdx 定长字段未 strip）")
    pre_rate = pre_mis / n
    base_max = max(base_pre_rates) if base_pre_rates else 0.0
    if pre_rate > base_max + 0.01:
        rep.warn(target, "stock-chain", f"pre_close≠前收 {pre_mis}/{n}={pre_rate:.2%}，基线最高 {base_max:.2%}")
    elif pre_mis == 0 and base_max > 0:
        rep.warn(
            target,
            "stock-chain",
            f"pre_close 与前收 100% 相等（基线每日 {base_max:.2%} 行因除权除息不等）——来源未做除息调整，"
            "除息日 pct_chg 含股息缺口",
        )
    else:
        rep.ok(target, "stock-chain", f"pre_close 链 {pre_mis}/{n} 不等（基线同量级），pct_chg 重算 {pct_mis} 不符")


def check_sw_chain(con, rep: Report, gate, target: str) -> None:
    prev = con.execute("SELECT MAX(trade_date) FROM fact_sw_l1_daily WHERE trade_date < ?", [target]).fetchone()[0]
    rows = con.execute(
        """
        SELECT c.sw_l1_code, c.close, c.pre_close, p.close, c.pct_chg, c.amount, c.source
        FROM fact_sw_l1_daily c
        LEFT JOIN fact_sw_l1_daily p ON p.sw_l1_code = c.sw_l1_code AND p.trade_date = ?
        WHERE c.trade_date = ?
        """,
        [prev, target],
    ).fetchall()
    if not rows:
        return
    if len(rows) != gate.SW_L1_COUNT:
        rep.fail(target, "sw-l1", f"fact_sw_l1_daily {len(rows)} 行 ≠ {gate.SW_L1_COUNT}")
    pre_bad = [r for r in rows if r[3] is not None and r[2] is not None and abs(r[2] - r[3]) > 0.02]
    pct_bad = [r for r in rows if r[1] and r[2] and r[4] is not None and abs(r[4] - (r[1] / r[2] - 1) * 100) > PCT_RECALC_TOL]
    if pre_bad:
        rep.fail(target, "sw-l1", f"{len(pre_bad)} 个行业 pre_close≠前一日 close（如 {pre_bad[0][0]} {pre_bad[0][2]} vs {pre_bad[0][3]}）——realtime 覆盖历史日的形状")
    if pct_bad:
        rep.fail(target, "sw-l1", f"{len(pct_bad)} 个行业 pct_chg 与 close/pre_close 重算不符")
    if not pre_bad and not pct_bad and len(rows) == gate.SW_L1_COUNT:
        rep.ok(target, "sw-l1", f"31 行业链式一致，source={sorted({str(r[6]).rsplit(':', 1)[0] for r in rows})}")


def check_index_chain(con, rep: Report, target: str) -> None:
    row = con.execute(
        """
        SELECT c.sh_index_close, c.sh_index_pct_chg, p.sh_index_close
        FROM fact_market_daily c
        LEFT JOIN fact_market_daily p ON p.trade_date = (SELECT MAX(trade_date) FROM fact_market_daily WHERE trade_date < ?)
        WHERE c.trade_date = ?
        """,
        [target, target],
    ).fetchone()
    if not row or row[0] is None or row[2] is None or row[1] is None:
        return
    recalc = (row[0] / row[2] - 1) * 100
    if abs(recalc - row[1]) > PCT_RECALC_TOL:
        rep.fail(target, "index-chain", f"上证 pct_chg {row[1]:.3f} 与收盘链重算 {recalc:.3f} 不符")
    else:
        rep.ok(target, "index-chain", f"上证 {row[0]} ({row[1]:+.2f}%) 与前收链一致")


def _ratio_band(values: list[float]) -> tuple[float, float]:
    return min(values) - RATIO_BAND_PAD, max(values) + RATIO_BAND_PAD


def check_amount_basis(con, rep: Report, target: str, baseline: list[str]) -> None:
    """全A个股合计 / 申万合计、市场总额 / 全A合计：量纲（亿）与全日/半日的探针。"""
    dates = [*baseline, target]
    rows = con.execute(
        f"""
        SELECT CAST(k.trade_date AS VARCHAR), k.stk, s.sw, m.total_amount
        FROM (SELECT trade_date, SUM(amount) stk FROM fact_stock_daily WHERE trade_date IN ({','.join('?' for _ in dates)}) GROUP BY 1) k
        LEFT JOIN (SELECT trade_date, SUM(amount) sw FROM fact_sw_l1_daily GROUP BY 1) s USING (trade_date)
        LEFT JOIN fact_market_daily m USING (trade_date)
        """,
        dates,
    ).fetchall()
    by = {r[0]: r for r in rows}
    if target not in by:
        return
    _d, stk, sw, tot = by[target]
    stk_sw_base = [by[d][1] / by[d][2] for d in baseline if d in by and by[d][1] and by[d][2]]
    tot_stk_base = [by[d][3] / by[d][1] for d in baseline if d in by and by[d][3] and by[d][1]]
    if stk and sw and stk_sw_base:
        lo, hi = _ratio_band(stk_sw_base)
        r = stk / sw
        (rep.ok if lo <= r <= hi else rep.fail)(
            target, "amount-basis", f"全A合计/申万合计 = {r:.4f}（基线 {min(stk_sw_base):.4f}~{max(stk_sw_base):.4f}）"
        )
    if stk and tot and tot_stk_base:
        lo, hi = _ratio_band(tot_stk_base)
        r = tot / stk
        (rep.ok if lo <= r <= hi else rep.fail)(
            target, "amount-basis", f"市场总额/全A合计 = {r:.4f}（基线 {min(tot_stk_base):.4f}~{max(tot_stk_base):.4f}）"
        )


def check_null_drift(con, rep: Report, target: str, baseline: list[str]) -> None:
    for table in ("fact_stock_daily", "fact_sector_daily", "fact_sector_stock_daily", "fact_sw_l1_daily"):
        cols = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall() if r[0] != "trade_date"]
        exprs = ", ".join(f"100.0 * SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) / COUNT(*)" for c in cols)
        dates = [*baseline, target]
        rows = con.execute(
            f"SELECT CAST(trade_date AS VARCHAR), {exprs} FROM {table} WHERE trade_date IN ({','.join('?' for _ in dates)}) GROUP BY 1",
            dates,
        ).fetchall()
        per = {r[0]: r[1:] for r in rows}
        if target not in per:
            continue
        drift, price_nulls = [], []
        for i, c in enumerate(cols):
            base = [per[d][i] for d in baseline if d in per]
            if not base:
                continue
            cur = per[target][i]
            base_avg = sum(base) / len(base)
            if c in PRICE_COLUMNS:
                # 新股首日 pre_close 空、停牌股 amount 空是常态；超出基线 + 0.5pp 才是抓取缺字段
                if cur > base_avg + PRICE_NULL_PP:
                    price_nulls.append(f"{c} {base_avg:.2f}%→{cur:.2f}%")
            elif abs(cur - base_avg) > NULL_DRIFT_PP:
                drift.append(f"{c} {base_avg:.0f}%→{cur:.0f}%")
        if price_nulls:
            rep.fail(target, "nulls", f"{table} 价格类列空值率高于基线：{', '.join(price_nulls)}")
        if drift:
            rep.warn(target, "nulls", f"{table} 空值率偏离基线 >{NULL_DRIFT_PP:.0f}pp：{', '.join(drift[:6])}")


def check_sectors(con, rep: Report, target: str) -> None:
    uni = con.execute("SELECT COUNT(DISTINCT sector_ts_code) FROM fact_sector_universe_daily WHERE trade_date = ?", [target]).fetchone()[0]
    sd = con.execute("SELECT COUNT(*) FROM fact_sector_daily WHERE trade_date = ?", [target]).fetchone()[0]
    ss = con.execute("SELECT COUNT(DISTINCT sector_ts_code), COUNT(*) FROM fact_sector_stock_daily WHERE trade_date = ?", [target]).fetchone()
    if uni:
        if sd < uni:
            rep.fail(target, "sectors", f"fact_sector_daily {sd}/{uni} 板块（宇宙已发布 {uni}）")
        if ss[0] < uni:
            rep.fail(target, "sectors", f"fact_sector_stock_daily 覆盖 {ss[0]}/{uni} 板块（{ss[1]} 行）")
        if sd >= uni and ss[0] >= uni:
            rep.ok(target, "sectors", f"板块日线 {sd} / 成分覆盖 {ss[0]} 板块 {ss[1]} 行，宇宙 {uni}")
    cmp = con.execute(
        """
        SELECT COUNT(*), COUNT(*) FILTER (WHERE ABS(d.pct_chg - p.pct_chg) > ?)
        FROM fact_sector_daily d JOIN ops_sector_search_payload_daily p USING (trade_date, sector_ts_code)
        WHERE d.trade_date = ? AND p.pct_chg IS NOT NULL
        """,
        [SECTOR_PAYLOAD_TOL, target],
    ).fetchone()
    if cmp and cmp[0]:
        n, bad = cmp
        if bad > n * 0.05:
            rep.fail(target, "sector-payload", f"板块 pct_chg 与 sectors/search payload 不符 {bad}/{n}")
        elif bad:
            rep.warn(target, "sector-payload", f"板块 pct_chg 与 payload 不符 {bad}/{n}")
        else:
            rep.ok(target, "sector-payload", f"板块 pct_chg 与 payload 逐板块一致 {n}/{n}")


def double_red(con, rep: Report, target: str, baseline: list[str]) -> list[dict]:
    from market_feature_store.signals import DOUBLE_RED_SQL

    rows = con.execute(
        f"SELECT sector_name, ROUND(pct_chg, 2), ROUND(diff_ratio, 2), ROUND(amount, 1) FROM fact_sector_daily "
        f"WHERE trade_date = ? AND {DOUBLE_RED_SQL} ORDER BY amount DESC",
        [target],
    ).fetchall()
    base_counts = [
        con.execute(f"SELECT COUNT(*) FROM fact_sector_daily WHERE trade_date = ? AND {DOUBLE_RED_SQL}", [d]).fetchone()[0]
        for d in baseline
    ]
    names = ", ".join(f"{r[0]}({r[1]}%/{r[2]}/{r[3]}亿)" for r in rows[:15])
    rep.info(target, "double-red", f"严格双红 {len(rows)} 个（基线各日 {base_counts}）：{names}{' …' if len(rows) > 15 else ''}")
    return [{"sector": r[0], "pct_chg": r[1], "diff_ratio": r[2], "amount": r[3]} for r in rows]


def run(dates: list[str], baseline_n: int, json_path: str | None) -> int:
    from market_feature_store import quality
    from market_feature_store.db import DatabaseLockedError, connect, connect_read_only_with_retry

    gate = _load_gate_module()
    attempts = int(os.environ.get("REVIEW_GATE_LOCK_ATTEMPTS", "13"))
    delay = float(os.environ.get("REVIEW_GATE_LOCK_DELAY_SECONDS", "10"))
    try:
        con = connect_read_only_with_retry(attempts=attempts, delay_seconds=delay, opener=lambda: connect(read_only=True))
    except DatabaseLockedError as exc:
        print("RESULT: BLOCKED")
        print(f"- 验收未能执行：{exc}")
        print("- 处置：等写进程收工后重跑，勿按缺数补录")
        return EXIT_BLOCKED

    rep = Report()
    payload: dict = {"dates": {}, "generated_at": datetime.now().isoformat(timespec="seconds")}
    try:
        for target in sorted(dates):
            baseline = pick_baseline(con, target, baseline_n)
            print(f"\n== {target} | 基线 {baseline_n} 个完整日: {baseline} ==")
            if len(baseline) < max(2, baseline_n // 2):
                rep.warn(target, "baseline", f"完整基线日只有 {len(baseline)} 个，比例类判定可信度低")
            check_rows(con, rep, gate, quality, target, baseline)
            has_market = check_market_row(con, rep, gate, target)
            check_calendar_side_effect(con, rep, quality, target, has_market)
            check_latest_snapshot_sources(con, rep, target)
            check_sources(con, rep, target, baseline)
            check_stock_chain(con, rep, target, baseline)
            check_sw_chain(con, rep, gate, target)
            check_index_chain(con, rep, target)
            check_amount_basis(con, rep, target, baseline)
            check_null_drift(con, rep, target, baseline)
            check_sectors(con, rep, target)
            reds = double_red(con, rep, target, baseline)
            payload["dates"][target] = {"baseline": baseline, "double_red": reds}
    finally:
        con.close()

    fails = [i for i in rep.items if i["level"] == "FAIL"]
    warns = [i for i in rep.items if i["level"] == "WARN"]
    print(f"\nRESULT: {'FAIL' if fails else 'PASS'} | FAIL {len(fails)} / WARN {len(warns)} / 检查项 {len(rep.items)}")
    for i in fails:
        print(f"- {i['date']} {i['check']}: {i['message']}")
    payload["items"] = rep.items
    payload["ok"] = not fails
    if json_path:
        Path(json_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"json -> {json_path}")
    return EXIT_FAIL if fails else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dates", nargs="+", help="目标交易日 YYYY-MM-DD，可多个")
    parser.add_argument("--baseline", type=int, default=6, help="基线取目标日之前最近 N 个完整交易日，默认 6")
    parser.add_argument("--json", default=None, help="把逐项结果写成 JSON（贴进交接）")
    parser.add_argument("--db", default=None, help="验 staging 时指向那份库；默认生产库（也可用 MARKET_FEATURE_STORE_DB）")
    args = parser.parse_args(argv)
    for d in args.dates:
        date.fromisoformat(d)
    if args.db:
        os.environ["MARKET_FEATURE_STORE_DB"] = args.db
    return run(args.dates, args.baseline, args.json)


if __name__ == "__main__":
    raise SystemExit(main())

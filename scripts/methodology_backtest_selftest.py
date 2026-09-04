#!/usr/bin/env python3
"""methodology_backtest 零凭证自测（照 theme-fermentation-tracer/selftest.py 的形状）。

在没有真实 market_feature_store.duckdb 的机器上，用 schema.sql 在临时目录造最小主库，灌合成盘面，
跑 build-labels → outcomes → run，断言三组对照 + 编译器拒绝夹具 + 重建幂等：

  阳性对照   植入「严格双红日之后 5 个交易日必为正」的形态 → 结论必须是 supported 且 lo > p0
  阴性对照   与收益独立的随机标签（multi_period_resonance）→ 结论 ∈ {not_distinguishable, insufficient_n}
  个股对照   植入「首板之后 5 个交易日必为正」→ supported；limit_up 事件数更多、命中率更低（二连板窗口为负）
  前视对照   把 outcomes 整体前移一个交易日 → 板块 / 个股两组阳性对照的 supported 都必须消失（翻转或降级）
  拒绝夹具   label 不在白名单 / op 为 "; DROP" / value 含 SQL 片段 → 各返回带字段路径的错误，且不触库
  幂等       重跑 build-labels 行数一致；删旁路库重建行数一致；data_gap 日被列出；个股 universe 行数 = 植入并集

合成形态（种子固定，确定性）：事件日 D 双红（pct +3 / diff 25 / amount 800），D+1..D+5 每日 +2%，
D+6 −15%，其余日 diff -5 永不双红、pct 微负随机。前移一天后事件对上的窗口变成 D+2..D+6，
1.02^4 × 0.85 − 1 ≈ −8%，命中率从 100% 掉到 0%——这就是「任何回测框架第一个 bug」的探针。

个股（P1）同一形状：事件日 D 首板（涨停表 limit_times=1，pct +10），D+1..D+5 每日 +2%，D+6 −15%；
每 4 只里 1 只在 D+1 二连板（limit_times=2，pct +10）——它是 limit_up 但不是 first_board，且自身
窗口 D+2..D+6 为负，所以 ``limit_up == true`` 的命中率会低于 ``first_board == true``。新高表按
(日 + 股) % 4 != 0 铺 3/4 的个股日、周期轮转，构成「涨停表 ∪ 新高表」的稀疏 universe；每 3 只里
1 只的首板行在两个板块下重复，考折叠。

样本数据全部虚构，仅用于逻辑自测。用法：
    python scripts/methodology_backtest_selftest.py
退出码：0 = PASS，非 0 = FAIL。
"""

from __future__ import annotations

import copy
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from intelligence.services.methodology_backtest.labels import build_labels  # noqa: E402
from intelligence.services.methodology_backtest.outcomes import build_outcomes  # noqa: E402
from intelligence.services.methodology_backtest.rules import parse_rule, validate_rule  # noqa: E402
from intelligence.services.methodology_backtest.runner import run_rule  # noqa: E402
from market_feature_store.db import init_db  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "market_feature_store" / "schema.sql"

N_DAYS = 160
N_SECTORS = 24
EVENT_SPACING = 12
EVENT_FIRST = 10
GAP_DAY_IDX = 40  # 与任何事件日错开（事件 idx = 10 + 12j + s%4）
SEED = 20260904
# 阴性对照的随机标签走独立 RNG 流（与收益独立是结构保证；改动其它合成数据不会顺带改写它），
# 但流的种子必须**派生自 seed**：若写死一个常数，标签模式与确定性的事件相位之间的那一次偶然相关
# 就会在所有 seed 下原样复现，变成常量偏差（实测 12 个 seed lift 全为 +1.6%～+2.9%）。
# 任何 95% 区间都有 ~5% 假阳性，固定 SEED 只是让夹具确定性，不是统计保证。
NEGATIVE_LABEL_SEED_SALT = 7
NEGATIVE_LABEL_RATE = 0.3
STAGES = ("主升阶段", "顶部横盘阶段", "下跌阶段", "底部横盘阶段", "反弹阶段")
N_STOCKS = 16
HIGH_PERIODS = ("20d", "60d", "1y", "history")
HIGH_LABELS = {"20d": "20日新高", "60d": "60日新高", "1y": "1年新高", "history": "历史新高"}

POSITIVE_RULE = {
    "rule_id": "selftest_positive",
    "version": 1,
    "title": "阳性对照：严格双红后 5 日为正",
    "scope": {"entity_type": "sector", "universe": "published_snapshot"},
    "condition": {"all": [{"label": "dual_red_strict", "op": "==", "value": True, "lag": 0}]},
    "outcome": {
        "target": "pct_chg",
        "horizons": [3, 5, 7, 10],
        "metrics": ["fwd_return", "max_return", "days_to_peak", "drawdown_after_peak"],
        "success": {"metric": "fwd_return", "horizon": 5, "op": ">", "value": 0},
    },
    "baseline": {"kind": "same_universe_all_days"},
    "min_n": 20,
}
NEGATIVE_RULE = {
    **POSITIVE_RULE,
    "rule_id": "selftest_negative",
    "title": "阴性对照：随机标签",
    "condition": {"all": [{"label": "multi_period_resonance", "op": "==", "value": True, "lag": 0}]},
}
STOCK_POSITIVE_RULE = {
    **POSITIVE_RULE,
    "rule_id": "selftest_stock_positive",
    "title": "阳性对照（个股）：首板后 5 日为正",
    "scope": {"entity_type": "stock", "universe": "limit_high_union"},
    "condition": {"all": [{"label": "first_board", "op": "==", "value": True, "lag": 0}]},
}


def trading_days(n: int, start: date = date(2026, 1, 5)) -> list[date]:
    out: list[date] = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def event_days(sector_idx: int, n_days: int) -> list[int]:
    out: list[int] = []
    i = EVENT_FIRST + (sector_idx % 4)
    while i + 7 < n_days:
        out.append(i)
        i += EVENT_SPACING
    return out


def build_sample_db(db_path: Path, *, seed: int = SEED, n_days: int = N_DAYS, n_sectors: int = N_SECTORS) -> dict:
    """造最小主库。返回植入统计（事件数等），供断言引用。"""
    rng = random.Random(seed)
    label_rng = random.Random(seed * 1_000_003 + NEGATIVE_LABEL_SEED_SALT)
    days = trading_days(n_days)
    con = duckdb.connect(str(db_path))
    try:
        init_db(con)
        prev_amount = 10000.0
        for i, d in enumerate(days):
            amount = prev_amount * (1 + rng.uniform(-0.12, 0.15))
            con.execute(
                "INSERT INTO fact_market_daily (trade_date, market_stage, total_amount, amount_vs_yesterday_pct, advancers) "
                "VALUES (?, ?, ?, ?, ?)",
                [d, STAGES[(i // 20) % len(STAGES)], amount, (amount / prev_amount - 1) * 100, rng.randint(1200, 4200)],
            )
            prev_amount = amount

        n_events = 0
        rows: list[tuple] = []
        for s in range(n_sectors):
            code = f"{880000 + s}.TI"
            name = f"测试板块{s}"
            evs = set(event_days(s, n_days))
            n_events += len(evs)
            plan: dict[int, tuple[float, float]] = {}
            for e in evs:
                plan[e] = (3.0, 25.0)
                for k in range(1, 6):
                    plan[e + k] = (2.0, -5.0)
                plan[e + 6] = (-15.0, -5.0)
            for i, d in enumerate(days):
                pct, diff = plan.get(i, (rng.gauss(-0.15, 1.2), -5.0))
                if i == GAP_DAY_IDX:
                    diff = 0.0
                mpr = label_rng.random() < NEGATIVE_LABEL_RATE
                rows.append((d, "legacy", code, name, pct, 800.0, diff, mpr))
        con.executemany(
            "INSERT INTO fact_sector_daily_generation (trade_date, sector_universe_snapshot_id, sector_ts_code, "
            "sector_name, pct_chg, amount, diff_ratio, multi_period_resonance) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        # 题材热度 + 主线：只为覆盖 theme 分支，随机名次
        heat_rows: list[tuple] = []
        ml_rows: list[tuple] = []
        for i, d in enumerate(days):
            order = list(range(6))
            rng.shuffle(order)
            for rank, s in enumerate(order, start=1):
                heat_rows.append((d, f"{880000 + s}.TI", f"测试板块{s}", "sector", "all", "final", False, rank, rng.randint(0, 9)))
            if i >= 30:
                ml_rows.append((d, "TH0001.FP", "测试主线", f"{880000 + order[0]}.TI", f"测试板块{order[0]}", 1))
        con.executemany(
            "INSERT INTO fact_theme_limit_heat_daily (trade_date, sector_ts_code, sector_name, dimension, scope, "
            "data_stage, is_realtime, rank, limit_up_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            heat_rows,
        )
        con.executemany(
            "INSERT INTO fact_mainline_sector_daily (trade_date, theme_code, theme_name, sector_ts_code, sector_name, sort_no) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ml_rows,
        )
        stock_stats = _plant_stocks(con, days, rng, n_sectors=n_sectors)
    finally:
        con.close()
    return {
        "n_days": n_days,
        "n_sectors": n_sectors,
        "n_events": n_events,
        "gap_day": str(days[GAP_DAY_IDX]),
        **stock_stats,
    }


def _plant_stocks(con: duckdb.DuckDBPyConnection, days: list[date], rng: random.Random, *, n_sectors: int) -> dict:
    """个股三张表：fact_stock_daily（价格序列）/ fact_theme_limit_stock_daily（涨停）/ fact_stock_high_daily（新高）。"""
    n_days = len(days)
    daily: list[tuple] = []
    limit_rows: list[tuple] = []
    high_rows: list[tuple] = []
    universe: set[tuple[int, int]] = set()
    n_first_boards = 0
    for s in range(N_STOCKS):
        code = f"{600000 + s}.SH"
        name = f"测试个股{s}"
        evs = set(event_days(s, n_days))
        n_first_boards += len(evs)
        plan: dict[int, float] = {}
        for e in evs:
            plan[e] = 10.0
            for k in range(1, 6):
                plan[e + k] = 2.0
            plan[e + 6] = -15.0
            if s % 4 == 0:
                plan[e + 1] = 10.0  # 二连板：limit_up 但不是 first_board，自身窗口 D+2..D+6 为负
        for i, d in enumerate(days):
            daily.append((d, code, name, plan.get(i, rng.gauss(-0.15, 1.2))))
            sector = f"{880000 + s % n_sectors}.TI"
            if i in evs:
                limit_rows.append((d, sector, f"测试板块{s % n_sectors}", code, name, 10.0, 1, "U"))
                if s % 3 == 0:  # 同一首板挂在第二个板块下：涨停表 PK 含板块，标签层必须按 (日, 股) 折叠
                    other = f"{880000 + (s + 1) % n_sectors}.TI"
                    limit_rows.append((d, other, f"测试板块{(s + 1) % n_sectors}", code, name, 10.0, 1, "U"))
                universe.add((i, s))
            elif (i - 1) in evs and s % 4 == 0:
                limit_rows.append((d, sector, f"测试板块{s % n_sectors}", code, name, 10.0, 2, "U"))
                universe.add((i, s))
            if (i + s) % 4 != 0:
                period = HIGH_PERIODS[((i + s) // 4) % len(HIGH_PERIODS)]
                high_rows.append((d, code, name, period, HIGH_LABELS[period], (i + s) % 8 == 1))
                universe.add((i, s))
    con.executemany(
        "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, pct_chg) VALUES (?, ?, ?, ?)",
        daily,
    )
    con.executemany(
        "INSERT INTO fact_theme_limit_stock_daily (trade_date, sector_ts_code, sector_name, stock_ts_code, stock_name, "
        "pct_chg, limit_times, limit_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        limit_rows,
    )
    con.executemany(
        "INSERT INTO fact_stock_high_daily (trade_date, stock_ts_code, stock_name, primary_high_period, "
        "primary_high_label, is_new) VALUES (?, ?, ?, ?, ?, ?)",
        high_rows,
    )
    return {"n_stocks": N_STOCKS, "n_first_boards": n_first_boards, "n_stock_universe": len(universe)}


def shift_outcomes_one_day_earlier(labels_db: Path) -> int:
    """作弊夹具：outcomes 整体前移一个交易日（D 日的结果挂到 D 的前一交易日）。返回改写行数。"""
    con = duckdb.connect(str(labels_db))
    try:
        con.execute(
            """
            CREATE OR REPLACE TEMP TABLE _shifted AS
            SELECT o.entity_type, o.entity_id, p.trade_date AS trade_date, o.horizon, o.fwd_return, o.max_return,
                   o.days_to_peak, o.drawdown_after_peak, o.status, o.computed_at
            FROM history_outcomes o
            JOIN history_calendar c ON c.trade_date = o.trade_date
            JOIN history_calendar p ON p.idx = c.idx - 1
            """
        )
        con.execute("DELETE FROM history_outcomes")
        con.execute("INSERT INTO history_outcomes SELECT * FROM _shifted")
        n = con.execute("SELECT COUNT(*) FROM history_outcomes").fetchone()[0]
        con.execute("DROP TABLE _shifted")
    finally:
        con.close()
    return int(n)


def run(labels_db: Path, rule_doc: dict):
    con = duckdb.connect(str(labels_db), read_only=True)
    try:
        return run_rule(con, parse_rule(rule_doc))
    finally:
        con.close()


def rejection_fixtures() -> list[tuple[str, dict, str]]:
    """三组必须被拒的输入：(名字, 文档, 期望出现的字段路径)。"""
    bad_label = copy.deepcopy(POSITIVE_RULE)
    bad_label["condition"]["all"][0]["label"] = "sector_close"
    bad_op = copy.deepcopy(POSITIVE_RULE)
    bad_op["condition"]["all"][0]["op"] = "; DROP"
    bad_value = copy.deepcopy(POSITIVE_RULE)
    bad_value["condition"]["all"] = [
        {"entity": "market", "label": "market_stage", "op": "in", "value": ["主升' OR 1=1 --"], "lag": 0}
    ]
    return [
        ("label 不在白名单", bad_label, "condition.all[0].label"),
        ("op 为 '; DROP'", bad_op, "condition.all[0].op"),
        ("value 含 SQL 片段", bad_value, "condition.all[0].value[0]"),
    ]


def main() -> int:
    if not SCHEMA_PATH.is_file():
        print(f"[FAIL] schema.sql 不存在: {SCHEMA_PATH}")
        return 1
    checks: dict[str, bool] = {}
    details: dict[str, str] = {}

    def record(name: str, ok: bool, detail: str = "") -> None:
        checks[name] = ok
        details[name] = detail
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    # 编译器拒绝夹具：纯校验，不需要任何库
    for name, doc, path in rejection_fixtures():
        rule, errors = validate_rule(doc)
        hit = rule is None and any(e.path == path for e in errors)
        record(f"拒绝夹具：{name}", hit, "; ".join(str(e) for e in errors) if errors else "未报错")

    with tempfile.TemporaryDirectory(prefix="mb-selftest-") as tmp:
        tmp_path = Path(tmp)
        source_db = tmp_path / "sample_feature_store.duckdb"
        labels_db = tmp_path / "history_labels.duckdb"
        planted = build_sample_db(source_db)

        rep1 = build_labels(source_db, labels_db)
        record(
            "标签层：15 个标签 + data_gap 日",
            len(rep1.rows_by_label) == 15 and rep1.data_gap_days == [planted["gap_day"]],
            f"labels={len(rep1.rows_by_label)} gap={rep1.data_gap_days} rows={rep1.row_count}",
        )
        cov = rep1.extras["source_row_counts"]["stock_coverage"]
        record(
            "个股 universe = 涨停表 ∪ 新高表的个股日并集",
            cov["universe_stock_days"] == planted["n_stock_universe"]
            and rep1.rows_by_label.get("first_board") == planted["n_stock_universe"],
            f"universe={cov['universe_stock_days']} planted={planted['n_stock_universe']} limit_days={cov['limit_list_days']}",
        )
        rep2 = build_labels(source_db, labels_db)
        record("幂等：重跑 build-labels 行数一致", rep2.row_count == rep1.row_count, f"{rep1.row_count} vs {rep2.row_count}")
        labels_db.unlink()
        rep3 = build_labels(source_db, labels_db)
        record("可重建：删旁路库重建行数一致", rep3.row_count == rep1.row_count, f"{rep1.row_count} vs {rep3.row_count}")
        out = build_outcomes(source_db, labels_db)
        record("前瞻结果表构建", out.row_count > 0, f"rows={out.row_count} status={out.extras.get('by_status')}")

        pos = run(labels_db, POSITIVE_RULE)
        rd = pos.readout
        record(
            "阳性对照：supported 且 lo > p0",
            rd.verdict == "supported" and rd.p0 is not None and rd.lo > rd.p0,
            f"N={rd.n} p={rd.p:.3f} p0={rd.p0:.3f} lo={rd.lo:.3f} halves={rd.p_first}/{rd.p_second} → {rd.verdict}"
            if rd.p is not None and rd.p0 is not None
            else f"N={rd.n} → {rd.verdict}",
        )
        record(
            "阳性对照：事件数与植入一致（扣除 pending）",
            rd.n + pos.n_pending == planted["n_events"],
            f"ok={rd.n} pending={pos.n_pending} planted={planted['n_events']}",
        )

        neg = run(labels_db, NEGATIVE_RULE)
        nd = neg.readout
        record(
            "阴性对照：随机标签 ∈ {not_distinguishable, insufficient_n}",
            nd.verdict in ("not_distinguishable", "insufficient_n"),
            f"N={nd.n} p={nd.p:.3f} p0={nd.p0:.3f} Wilson=[{nd.lo:.3f}, {nd.hi:.3f}] → {nd.verdict}"
            if nd.p is not None and nd.p0 is not None
            else f"N={nd.n} → {nd.verdict}",
        )

        stk = run(labels_db, STOCK_POSITIVE_RULE)
        sd = stk.readout
        record(
            "阳性对照（个股）：首板后 5 日为正 supported 且 lo > p0",
            sd.verdict == "supported" and sd.p0 is not None and sd.lo > sd.p0,
            f"N={sd.n} p={sd.p:.3f} p0={sd.p0:.3f} lo={sd.lo:.3f} → {sd.verdict}"
            if sd.p is not None and sd.p0 is not None
            else f"N={sd.n} → {sd.verdict}",
        )
        record(
            "阳性对照（个股）：首板事件数与植入一致（扣除 pending），二连板不算首板",
            sd.n + stk.n_pending == planted["n_first_boards"],
            f"ok={sd.n} pending={stk.n_pending} planted={planted['n_first_boards']}",
        )
        limit_any = run(labels_db, {**STOCK_POSITIVE_RULE, "rule_id": "selftest_stock_limit_any",
                                    "condition": {"all": [{"label": "limit_up", "op": "==", "value": True, "lag": 0}]}})
        record(
            "个股标签语义：limit_up 事件数 > first_board 事件数，命中率更低（二连板窗口为负）",
            limit_any.readout.n > sd.n and limit_any.readout.p is not None and limit_any.readout.p < sd.p,
            f"limit_up N={limit_any.readout.n} p={limit_any.readout.p} vs first_board N={sd.n} p={sd.p}",
        )

        shifted = shift_outcomes_one_day_earlier(labels_db)
        cheat = run(labels_db, POSITIVE_RULE)
        cd = cheat.readout
        record(
            "前视对照：outcomes 前移一日后 supported 消失",
            shifted > 0 and cd.verdict != "supported",
            f"N={cd.n} p={cd.p:.3f} p0={cd.p0:.3f} → {cd.verdict}" if cd.p is not None and cd.p0 is not None else f"→ {cd.verdict}",
        )
        cheat_stk = run(labels_db, STOCK_POSITIVE_RULE).readout
        record(
            "前视对照（个股）：outcomes 前移一日后首板 supported 消失",
            cheat_stk.verdict != "supported",
            f"N={cheat_stk.n} p={cheat_stk.p} p0={cheat_stk.p0} → {cheat_stk.verdict}",
        )
        build_outcomes(source_db, labels_db)
        again = run(labels_db, POSITIVE_RULE)
        record("前视对照：重建 outcomes 后阳性恢复 supported", again.readout.verdict == "supported", again.readout.verdict)
        record(
            "前视对照（个股）：重建 outcomes 后首板恢复 supported",
            run(labels_db, STOCK_POSITIVE_RULE).readout.verdict == "supported",
        )

    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        print(f"\n[FAIL] {len(failed)} 项断言未通过: {failed}")
        return 1
    print(f"\n[PASS] 全部 {len(checks)} 项断言通过；合成库上标签层 → outcomes → 编译 → 四态端到端跑通。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

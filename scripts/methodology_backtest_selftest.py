#!/usr/bin/env python3
"""methodology_backtest 零凭证自测（照 theme-fermentation-tracer/selftest.py 的形状）。

在没有真实 market_feature_store.duckdb 的机器上，用 schema.sql 在临时目录造最小主库，灌合成盘面，
跑 build-labels → outcomes → run，断言三组对照 + 编译器拒绝夹具 + 重建幂等：

  阳性对照   植入「严格双红日之后 5 个交易日必为正」的形态 → 结论必须是 supported 且 lo > p0
  阴性对照   与收益独立的随机标签（multi_period_resonance）→ 结论 ∈ {not_distinguishable, insufficient_n}
  前视对照   把 outcomes 整体前移一个交易日 → 阳性对照的 supported 必须消失（翻转或降级）
  拒绝夹具   label 不在白名单 / op 为 "; DROP" / value 含 SQL 片段 → 各返回带字段路径的错误，且不触库
  幂等       重跑 build-labels 行数一致；删旁路库重建行数一致；data_gap 日被列出

合成形态（种子固定，确定性）：事件日 D 双红（pct +3 / diff 25 / amount 800），D+1..D+5 每日 +2%，
D+6 −15%，其余日 diff -5 永不双红、pct 微负随机。前移一天后事件对上的窗口变成 D+2..D+6，
1.02^4 × 0.85 − 1 ≈ −8%，命中率从 100% 掉到 0%——这就是「任何回测框架第一个 bug」的探针。

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
    finally:
        con.close()
    return {"n_days": n_days, "n_sectors": n_sectors, "n_events": n_events, "gap_day": str(days[GAP_DAY_IDX])}


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
            "标签层：12 个标签 + data_gap 日",
            len(rep1.rows_by_label) == 12 and rep1.data_gap_days == [planted["gap_day"]],
            f"labels={len(rep1.rows_by_label)} gap={rep1.data_gap_days} rows={rep1.row_count}",
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

        shifted = shift_outcomes_one_day_earlier(labels_db)
        cheat = run(labels_db, POSITIVE_RULE)
        cd = cheat.readout
        record(
            "前视对照：outcomes 前移一日后 supported 消失",
            shifted > 0 and cd.verdict != "supported",
            f"N={cd.n} p={cd.p:.3f} p0={cd.p0:.3f} → {cd.verdict}" if cd.p is not None and cd.p0 is not None else f"→ {cd.verdict}",
        )
        build_outcomes(source_db, labels_db)
        again = run(labels_db, POSITIVE_RULE)
        record("前视对照：重建 outcomes 后阳性恢复 supported", again.readout.verdict == "supported", again.readout.verdict)

    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        print(f"\n[FAIL] {len(failed)} 项断言未通过: {failed}")
        return 1
    print(f"\n[PASS] 全部 {len(checks)} 项断言通过；合成库上标签层 → outcomes → 编译 → 四态端到端跑通。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

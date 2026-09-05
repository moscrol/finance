"""方法论回测 P0/P1：编译器白名单 / Wilson 数值 / 四态边界 / 标签语义 / 前视检测 / 重建幂等 /
基准率双口径 / 纠偏登记入口 / 个股标签（涨停表 ∪ 新高表 universe、series 键不串线）。

变异测试（记进交接）：把 ``outcomes.WINDOW_START_OFFSET`` 从 1 改成 0（窗口含 D0 = 前视），
``test_outcomes_window_excludes_label_day`` 与 ``test_lookahead_shift_flips_positive_control`` 必须变红。
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from intelligence.services.methodology_backtest import outcomes as outcomes_mod
from intelligence.services.methodology_backtest.compiler import compile_rule
from intelligence.services.methodology_backtest.labels import LABEL_VERSION, build_labels
from intelligence.services.methodology_backtest.outcomes import build_outcomes
from intelligence.services.methodology_backtest.receipts import build_receipt, render_receipt_markdown
from intelligence.services.methodology_backtest.rules import RuleValidationError, load_rule, parse_rule, validate_rule
from intelligence.services.methodology_backtest.runner import load_conditions, run_rule, scan_rules
from intelligence.services.methodology_backtest.stats import (
    benjamini_hochberg,
    binom_two_sided_p,
    four_state,
    readout,
    wilson,
)
from market_feature_store.db import init_db

REPO = Path(__file__).resolve().parents[2]
SELFTEST = REPO / "scripts" / "methodology_backtest_selftest.py"
CLI = REPO / "scripts" / "methodology_backtest.py"

BASE_RULE = {
    "rule_id": "test_rule",
    "version": 1,
    "title": "t",
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
    "sharing": "shared",
    "owner": "system",
}


def _load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclass / argparse 脚本按文件加载要先登记
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# 编译器白名单（不触库）
# --------------------------------------------------------------------------- #
def _bad(mutate):
    doc = copy.deepcopy(BASE_RULE)
    mutate(doc)
    return doc


@pytest.mark.parametrize(
    "mutate, path",
    [
        (lambda d: d["condition"]["all"][0].__setitem__("label", "sector_close"), "condition.all[0].label"),
        (lambda d: d["condition"]["all"][0].__setitem__("op", "; DROP"), "condition.all[0].op"),
        (
            lambda d: d["condition"].__setitem__(
                "all", [{"entity": "market", "label": "market_stage", "op": "in", "value": ["主升' OR 1=1 --"]}]
            ),
            "condition.all[0].value[0]",
        ),
        (lambda d: d["outcome"]["success"].__setitem__("metric", "fwd_return; DROP TABLE x"), "outcome.success.metric"),
        (lambda d: d.__setitem__("sql", "select 1"), "sql"),
        (lambda d: d["condition"]["all"][0].__setitem__("lag", -1), "condition.all[0].lag"),
        (lambda d: d["scope"].__setitem__("universe", "everything"), "scope.universe"),
        (lambda d: d["baseline"].__setitem__("kind", "made_up"), "baseline.kind"),
    ],
)
def test_validator_rejects_with_field_path(mutate, path):
    rule, errors = validate_rule(_bad(mutate))
    assert rule is None
    assert any(e.path == path for e in errors), [str(e) for e in errors]


def test_validator_accepts_design_example_shape():
    rule, errors = validate_rule(BASE_RULE)
    assert errors == [] and rule is not None
    assert rule.ref == "test_rule@v1"
    assert rule.predicates[0].kind == "bool"


def test_load_rule_requires_versioned_filename(tmp_path):
    p = tmp_path / "test_rule.v2.json"
    p.write_text(__import__("json").dumps(BASE_RULE), encoding="utf-8")
    with pytest.raises(RuleValidationError) as exc:
        load_rule(p)
    assert "文件名" in str(exc.value)


def test_compiler_binds_values_not_text():
    rule = parse_rule(BASE_RULE)
    compiled = compile_rule(rule, start="2026-01-01", end="2026-12-31")
    assert "DROP" not in compiled.events.sql
    # 谓词值、日期、horizon 都在参数里，不在 SQL 文本里
    assert 1.0 in compiled.events.params and "2026-01-01" in compiled.events.params and 5 in compiled.events.params
    assert compiled.events.sql.count("?") == len(compiled.events.params)
    assert compiled.metrics.sql.count("?") == len(compiled.metrics.params)
    bq = compiled.baseline_for("2026-02-01", "2026-03-01")
    assert bq.sql.count("?") == len(bq.params)
    assert bq.params[1:3] == ("2026-02-01", "2026-03-01")


# --------------------------------------------------------------------------- #
# 统计
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("k, n, lo, hi", [(0, 20, 0.0, 0.161), (20, 20, 0.839, 1.0), (10, 20, 0.299, 0.701)])
def test_wilson_matches_public_tables(k, n, lo, hi):
    got_lo, got_hi = wilson(k, n)
    assert round(got_lo, 3) == lo and round(got_hi, 3) == hi


def test_wilson_never_leaves_unit_interval():
    for n in (1, 2, 5, 20, 100):
        for k in range(n + 1):
            lo, hi = wilson(k, n)
            assert 0.0 <= lo <= hi <= 1.0


def test_binomial_two_sided_matches_scipy_reference():
    assert round(binom_two_sided_p(7, 20, 0.5), 6) == 0.263176
    assert binom_two_sided_p(10, 20, 0.5) == 1.0
    assert binom_two_sided_p(0, 20, 0.5) < 1e-5


def test_benjamini_hochberg_known_example():
    rejected, adjusted = benjamini_hochberg([0.01, 0.04, 0.03, 0.20], q=0.05)
    assert rejected == [True, False, False, False]
    assert [round(a, 4) for a in adjusted] == [0.04, 0.0533, 0.0533, 0.2]


def test_four_state_boundaries():
    assert four_state(19, 19, 0.5, 1.0, 1.0, min_n=20) == "insufficient_n"
    lo, _ = wilson(18, 20)
    assert lo > 0.5
    assert four_state(20, 18, 0.5, 1.0, 0.4, min_n=20) == "not_distinguishable"
    assert four_state(20, 18, 0.5, 0.9, 0.9, min_n=20) == "supported"
    assert four_state(40, 4, 0.5, 0.1, 0.1, min_n=20) == "refuted"
    assert four_state(40, 30, None, 0.7, 0.8, min_n=20) == "not_distinguishable"


def test_readout_single_correction_cannot_flip_verdict():
    """一次纠偏 = 事件集多一行，改不了结论：N 从 40 到 41，supported 还是 supported。"""
    base = [True] * 34 + [False] * 6
    r1 = readout(base, baseline_n=1000, baseline_k=500, min_n=20)
    r2 = readout(base + [False], baseline_n=1000, baseline_k=500, min_n=20)
    assert r1.verdict == r2.verdict == "supported"


# --------------------------------------------------------------------------- #
# 手工小库：标签语义 + outcomes 口径
# --------------------------------------------------------------------------- #
def _weekdays(n: int, start: date = date(2026, 3, 2)) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


DAYS = _weekdays(12)
GAP = 6  # 全零日
# S1：双红 1,2,3 → 0 → 1 → gap → 1,2 ；pct 序列另供 outcomes 手算
S1 = {
    0: (5.0, 20.0, 1000.0),
    1: (1.0, 15.0, 1000.0),
    2: (2.0, 15.0, 1000.0),
    3: (1.0, 15.0, 1000.0),
    4: (-0.5, 15.0, 1000.0),
    5: (0.5, 15.0, 1000.0),
    6: (0.5, 0.0, 1000.0),
    7: (0.5, 15.0, 1000.0),
    8: (0.5, 15.0, 1000.0),
    9: (0.5, -5.0, 1000.0),
    10: (0.5, -5.0, 1000.0),
    11: (0.5, -5.0, 1000.0),
}
# S2：diff_ratio 拐点 -3 → +2(1) → +1(0) → -1(0) → 0(0) → +1(1) → gap(NULL) → +1(NULL: 前一日是 gap)
S2_DIFF = {0: -3.0, 1: 2.0, 2: 1.0, 3: -1.0, 4: 0.0, 5: 1.0, 6: 0.0, 7: 1.0, 8: 1.0, 9: 1.0, 10: 1.0, 11: 1.0}
# S3：第 3 日缺行；第 4 日双红 → streak 1（断档重新计数）、turn_up NULL
S3_SKIP = {3}

# 个股：K1 全 12 日有价，D0 涨停首板（两个板块下重复）、D1 二连板；K2 第 2 日停牌缺行，D3 涨停但连板数缺失、
# D4 炸板（status Z）；K3 故意用板块代码 "S1.TI" 当个股代码且日日 -1%，考 series 键不串线；
# K4 只在涨停表出现（三连板），没有价格行 → outcomes 全 missing。
# 涨停表缺第 2、6 日（→ limit_up / first_board NULL）；新高表缺第 9 日（→ new_high_1y NULL）。
K1, K2, K3, K4 = "000001.SZ", "000002.SZ", "S1.TI", "000004.SZ"
LIMIT_DAYS = {0, 1, 3, 4, 5, 7, 8, 9, 10, 11}
HIGH_DAYS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11}
K1_HIGH = {0: "1y", 1: "20d", 2: "history", 3: "20d", 4: "60d", 5: "3y", 6: "120d", 7: "20d", 8: "20d", 10: "20d", 11: "20d"}
K2_HIGH = {0: "60d", 6: "2y"}


def _plant_mini_stocks(con) -> None:
    daily = []
    for i, d in enumerate(DAYS):
        daily.append((d, K1, "个股一", 10.0 if i == 0 else S1[i][0]))
        if i != 2:
            daily.append((d, K2, "个股二", 0.3))
        daily.append((d, K3, "同名个股", -1.0))
    con.executemany("INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, pct_chg) VALUES (?,?,?,?)", daily)
    limit = [
        (DAYS[0], "S1.TI", "板块一", K1, "个股一", 1, "U"),
        (DAYS[0], "S2.TI", "板块二", K1, "个股一", 1, "U"),
        (DAYS[1], "S1.TI", "板块一", K1, "个股一", 2, "U"),
        (DAYS[3], "S1.TI", "板块一", K2, "个股二", None, "U"),
        (DAYS[4], "S1.TI", "板块一", K2, "个股二", 1, "Z"),
        (DAYS[0], "S2.TI", "板块二", K3, "同名个股", 1, "U"),
    ]
    limit += [(DAYS[i], "S3.TI", "板块三", K4, "个股四", 3, "U") for i in sorted(LIMIT_DAYS)]
    con.executemany(
        "INSERT INTO fact_theme_limit_stock_daily (trade_date, sector_ts_code, sector_name, stock_ts_code, stock_name, limit_times, limit_status) VALUES (?,?,?,?,?,?,?)",
        limit,
    )
    high = [(DAYS[i], K1, "个股一", p, p, i % 2 == 0) for i, p in K1_HIGH.items()]
    high += [(DAYS[i], K2, "个股二", p, p, True) for i, p in K2_HIGH.items()]
    con.executemany(
        "INSERT INTO fact_stock_high_daily (trade_date, stock_ts_code, stock_name, primary_high_period, primary_high_label, is_new) VALUES (?,?,?,?,?,?)",
        high,
    )


def _build_mini_db(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        init_db(con)
        for i, d in enumerate(DAYS):
            avp = None if i == 0 else (15.0 if i == 3 else 5.0)
            con.execute(
                "INSERT INTO fact_market_daily (trade_date, market_stage, total_amount, amount_vs_yesterday_pct, advancers) VALUES (?,?,?,?,?)",
                [d, "主升阶段" if i < 6 else "下跌阶段", 10000.0, avp, 2000 + i * 10],
            )
        rows = []
        for i, d in enumerate(DAYS):
            pct, diff, amt = S1[i]
            rows.append((d, "legacy", "S1.TI", "板块一", pct, amt, diff, True if i == 1 else None))
            rows.append((d, "legacy", "S2.TI", "板块二", 0.1, 800.0, S2_DIFF[i], False))
            if i not in S3_SKIP:
                dr = i == 4
                rows.append((d, "legacy", "S3.TI", "板块三", 1.0 if dr else -1.0, 600.0, 20.0 if dr else -5.0, None))
            # 第 9 日再塞 12 个小板块测 top10 恰好 10 个
            if i == 9:
                for j in range(12):
                    rows.append((d, "legacy", f"T{j:02d}.TI", f"小板块{j}", 0.0, 100.0 + j, -5.0, None))
        # gap 日：所有板块 diff_ratio=0（S1/S2 已是 0；S3 也置 0）
        rows = [(d, s, c, n, p, a, 0.0 if d == DAYS[GAP] else df, m) for d, s, c, n, p, a, df, m in rows]
        con.executemany(
            "INSERT INTO fact_sector_daily_generation (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount, diff_ratio, multi_period_resonance) VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        heat = [(DAYS[0], 10), (DAYS[1], 4), (DAYS[2], 3), (DAYS[4], 1)]
        for d, rank in heat:
            con.execute(
                "INSERT INTO fact_theme_limit_heat_daily (trade_date, sector_ts_code, sector_name, dimension, scope, data_stage, is_realtime, rank) VALUES (?,?,?,?,?,?,?,?)",
                [d, "S1.TI", "板块一", "sector", "all", "final", False, rank],
            )
        # proxy 档不应进标签
        con.execute(
            "INSERT INTO fact_theme_limit_heat_daily (trade_date, sector_ts_code, sector_name, dimension, scope, data_stage, is_realtime, rank) VALUES (?,?,?,?,?,?,?,?)",
            [DAYS[3], "S1.TI", "板块一", "sector", "all", "proxy", False, 99],
        )
        con.execute(
            "INSERT INTO fact_mainline_sector_daily (trade_date, theme_code, theme_name, sector_ts_code, sector_name, sort_no) VALUES (?,?,?,?,?,?)",
            [DAYS[2], "TH1.FP", "主线", "S1.TI", "板块一", 1],
        )
        con.execute(
            "INSERT INTO fact_mainline_sector_daily (trade_date, theme_code, theme_name, sector_ts_code, sector_name, sort_no) VALUES (?,?,?,?,?,?)",
            [DAYS[4], "TH1.FP", "主线", "S2.TI", "板块二", 1],
        )
        _plant_mini_stocks(con)
    finally:
        con.close()


@pytest.fixture(scope="module")
def mini(tmp_path_factory):
    root = tmp_path_factory.mktemp("mini")
    src = root / "src.duckdb"
    lab = root / "labels.duckdb"
    _build_mini_db(src)
    report = build_labels(src, lab)
    build_outcomes(src, lab)
    return {"src": src, "labels": lab, "report": report}


def _label(con, entity_type, entity_id, label):
    rows = con.execute(
        "SELECT trade_date, value_num, value_text FROM history_labels WHERE entity_type=? AND entity_id=? AND label=? ORDER BY trade_date",
        [entity_type, entity_id, label],
    ).fetchall()
    return {DAYS.index(d): (t if t is not None else v) for d, v, t in rows}


def test_labels_inventory_and_data_gap(mini):
    rep = mini["report"]
    assert len(rep.rows_by_label) == 15
    assert rep.data_gap_days == [str(DAYS[GAP])]
    assert rep.label_version == LABEL_VERSION
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        assert con.execute("SELECT COUNT(DISTINCT label) FROM history_labels").fetchone()[0] == 15
        assert con.execute("SELECT MAX(trade_date) FROM history_labels").fetchone()[0] == DAYS[-1]
    finally:
        con.close()


def test_stock_label_semantics_dense_within_union_universe(mini):
    """个股 universe = 涨停表 ∪ 新高表；并集内三标签稠密 1/0，源表整日缺失才 NULL；跨板块重复按 (日, 股) 折叠。"""
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        cov = mini["report"].extras["source_row_counts"]["stock_coverage"]
        assert cov["universe"] == "limit_high_union"
        assert cov["limit_list_days"] == len(LIMIT_DAYS) and cov["high_list_days"] == len(HIGH_DAYS)
        assert cov["limit_list_missing_days"] == [str(DAYS[2]), str(DAYS[6])]
        # K1：第 9 日两表都没有 → 根本没有标签行；其余日三标签各一行
        k1_days = {DAYS.index(d) for (d,) in con.execute(
            "SELECT DISTINCT trade_date FROM history_labels WHERE entity_type='stock' AND entity_id=?", [K1]).fetchall()}
        assert k1_days == set(range(12)) - {9}
        lu = _label(con, "stock", K1, "limit_up")
        fb = _label(con, "stock", K1, "first_board")
        nh = _label(con, "stock", K1, "new_high_1y")
        assert (lu[0], fb[0], nh[0]) == (1, 1, 1)  # 首板 + 一年新高；两个板块下重复只算一次
        assert (lu[1], fb[1], nh[1]) == (1, 0, 0)  # 二连板：涨停但不是首板
        assert (lu[2], fb[2], nh[2]) == (None, None, 1)  # 涨停表缺第 2 日
        assert (lu[3], fb[3], nh[3]) == (0, 0, 0)  # 在榜（20d 新高）但没涨停
        assert (lu[5], fb[5], nh[5]) == (0, 0, 1)  # 3 年新高 ⊃ 一年新高
        assert (lu[6], fb[6], nh[6]) == (None, None, 0)  # 120d 不算一年新高；涨停表缺第 6 日
        assert con.execute(
            "SELECT COUNT(*) FROM history_labels WHERE entity_type='stock' AND entity_id=? AND label='limit_up'", [K1]
        ).fetchone()[0] == 11
        # K2：连板数缺失 → first_board NULL 但 limit_up=1；炸板 Z → 不算涨停
        assert (_label(con, "stock", K2, "limit_up")[3], _label(con, "stock", K2, "first_board")[3]) == (1, None)
        assert (_label(con, "stock", K2, "limit_up")[4], _label(con, "stock", K2, "first_board")[4]) == (0, 0)
        assert _label(con, "stock", K2, "new_high_1y") == {0: 0, 3: 0, 4: 0, 6: 1}
        assert _label(con, "stock", K2, "limit_up")[6] is None
        # K4：只在涨停表；新高表缺第 9 日 → new_high_1y NULL，其余日 0
        k4 = _label(con, "stock", K4, "new_high_1y")
        assert k4[9] is None and all(k4[i] == 0 for i in LIMIT_DAYS - {9})
        assert set(_label(con, "stock", K4, "first_board").values()) == {0}
        # 个股标签只挂在 stock 实体下，板块 / 题材实体不受影响
        assert con.execute("SELECT COUNT(*) FROM history_labels WHERE entity_type<>'stock' AND label IN ('limit_up','first_board','new_high_1y')").fetchone()[0] == 0
    finally:
        con.close()


def test_stock_outcomes_use_stock_series_not_sector(mini):
    """个股前瞻收益取 fact_stock_daily；同代码的板块与个股（K3 = 'S1.TI'）各走各的序列；停牌缺行 → missing。"""
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        fwd, status = con.execute(
            "SELECT fwd_return, status FROM history_outcomes WHERE entity_type='stock' AND entity_id=? AND trade_date=? AND horizon=3",
            [K1, DAYS[0]],
        ).fetchone()
        assert status == "ok" and fwd == pytest.approx((1.01 * 1.02 * 1.01 - 1) * 100, abs=1e-9)
        stock_k3, sector_s1 = con.execute(
            "SELECT (SELECT fwd_return FROM history_outcomes WHERE entity_type='stock' AND entity_id='S1.TI' AND trade_date=? AND horizon=3),"
            "       (SELECT fwd_return FROM history_outcomes WHERE entity_type='sector' AND entity_id='S1.TI' AND trade_date=? AND horizon=3)",
            [DAYS[0], DAYS[0]],
        ).fetchone()
        assert stock_k3 == pytest.approx((0.99**3 - 1) * 100, abs=1e-9) and sector_s1 > 0
        assert con.execute(
            "SELECT status FROM history_outcomes WHERE entity_type='stock' AND entity_id=? AND trade_date=? AND horizon=3", [K2, DAYS[0]]
        ).fetchone()[0] == "missing"
        # K4 没有价格行：日历够长的窗口 missing，够不到 T+h 的仍按既有规矩记 pending，绝不出现 ok
        k4_status = {DAYS.index(d): s for d, s in con.execute(
            "SELECT trade_date, status FROM history_outcomes WHERE entity_type='stock' AND entity_id=? AND horizon=3", [K4]).fetchall()}
        assert k4_status[0] == "missing" and k4_status[11] == "pending" and "ok" not in k4_status.values()
        # 每个 universe 里的个股日、每个窗口恰一行（含 missing / pending），与 sector / theme 同规矩
        n_universe, n_outcomes = con.execute(
            "SELECT (SELECT COUNT(DISTINCT (entity_id, trade_date)) FROM history_labels WHERE entity_type='stock'),"
            "       (SELECT COUNT(*) FROM history_outcomes WHERE entity_type='stock')"
        ).fetchone()
        assert n_outcomes == n_universe * 4 > 0
    finally:
        con.close()


@pytest.mark.parametrize(
    "mutate, path",
    [
        (lambda d: d["condition"]["all"][0].__setitem__("label", "dual_red_strict"), "condition.all[0].label"),
        (lambda d: d["scope"].__setitem__("universe", "published_snapshot"), "scope.universe"),
        (lambda d: d["condition"]["all"][0].__setitem__("value", 1), "condition.all[0].value"),
    ],
)
def test_stock_rule_whitelist_rejections(mutate, path):
    doc = copy.deepcopy(BASE_RULE)
    doc["scope"] = {"entity_type": "stock", "universe": "limit_high_union"}
    doc["condition"] = {"all": [{"label": "first_board", "op": "==", "value": True, "lag": 0}]}
    assert validate_rule(doc)[0] is not None
    mutate(doc)
    rule, errors = validate_rule(doc)
    assert rule is None and any(e.path == path for e in errors), [str(e) for e in errors]
    # 反向：板块规则引用个股标签也被拒
    sector_doc = copy.deepcopy(BASE_RULE)
    sector_doc["condition"]["all"].append({"label": "new_high_1y", "op": "==", "value": True})
    rule, errors = validate_rule(sector_doc)
    assert rule is None and any(e.path == "condition.all[1].label" for e in errors)


def test_stock_rule_may_reference_market_labels():
    doc = copy.deepcopy(BASE_RULE)
    doc["scope"] = {"entity_type": "stock", "universe": "limit_high_union"}
    doc["condition"] = {"all": [
        {"label": "first_board", "op": "==", "value": True, "lag": 0},
        {"entity": "market", "label": "market_stage", "op": "in", "value": ["主升阶段", "主升"], "lag": 1},
    ]}
    rule = parse_rule(doc)
    compiled = compile_rule(rule, start="2026-01-01", end="2026-12-31")
    assert compiled.events.params[0] == "stock" and "market" in compiled.events.params
    assert compiled.events.sql.count("?") == len(compiled.events.params)


def test_seed_rules_load_and_stock_seed_targets_stock_universe():
    files = sorted((REPO / "methodology" / "rules").glob("*.v*.json"))
    rules = {load_rule(f).rule_id: load_rule(f) for f in files}
    assert {"dual_red_streak3_continuation", "diff_ratio_turn_up_5d", "limit_heat_rank_jump_3d", "first_board_new_high_1y_5d"} <= set(rules)
    stock = rules["first_board_new_high_1y_5d"]
    assert stock.entity_type == "stock" and stock.universe == "limit_high_union"
    assert {p.label for p in stock.predicates} == {"first_board", "new_high_1y"}
    assert stock.success.horizon == 5 and stock.min_n == 20
    # 种子规则全部共享层、owner=system、来源写明（设计稿 §6 产品约束第一条）
    for r in rules.values():
        assert (r.sharing, r.owner) == ("shared", "system") and r.raw.get("source_perspective"), r.ref


# --------------------------------------------------------------------------- #
# 归属层（sharing / owner）白名单
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "mutate, path",
    [
        (lambda d: d.pop("sharing"), "sharing"),
        (lambda d: d.__setitem__("sharing", "public"), "sharing"),
        (lambda d: d.pop("owner"), "owner"),
        (lambda d: d.__setitem__("owner", "alice"), "owner"),  # shared 必须 system
        (lambda d: d.update(sharing="private", owner="system"), "owner"),  # private 不能 system
        (lambda d: d.__setitem__("owner", "a; DROP TABLE x"), "owner"),
        (lambda d: d.__setitem__("source_perspective", ""), "source_perspective"),
        (lambda d: d.__setitem__("source_perspective", "x" * 201), "source_perspective"),
    ],
)
def test_sharing_owner_whitelist_rejections(mutate, path):
    rule, errors = validate_rule(_bad(mutate))
    assert rule is None and any(e.path == path for e in errors), [str(e) for e in errors]


def test_sharing_owner_accepted_and_carried_into_receipt(mini):
    private = parse_rule({**BASE_RULE, "sharing": "private", "owner": "alice@x"})
    assert (private.sharing, private.owner) == ("private", "alice@x")
    shared = parse_rule({**BASE_RULE, "source_perspective": "某 KOL 视角蒸馏"})
    assert (shared.sharing, shared.owner) == ("shared", "system")
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        res = run_rule(con, shared)
    finally:
        con.close()
    env = {"tree": "t", "branch": "b", "revision": "r", "dirty": False, "interpreter": "py", "python_version": "3", "duckdb_version": "d"}
    receipt = build_receipt(res, rule_path=None, rule_sha256=None, environment=env)
    assert (receipt["sharing"], receipt["owner"]) == ("shared", "system")
    assert receipt["rule"]["source_perspective"] == "某 KOL 视角蒸馏"
    md = render_receipt_markdown(receipt)
    assert "归属 `shared` / owner `system`" in md and "某 KOL 视角蒸馏" in md


# --------------------------------------------------------------------------- #
# 按大盘阶段拆分 + 证伪库
# --------------------------------------------------------------------------- #
def test_stage_breakdown_splits_ok_events_by_market_stage(mini):
    """mini 库：第 0–5 日主升阶段、第 6 日起下跌阶段；双红事件 T+3 已到期的 8 个里 6 个在主升、2 个在下跌。"""
    doc = copy.deepcopy(BASE_RULE)
    doc["outcome"]["success"]["horizon"] = 3
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        res = run_rule(con, parse_rule(doc))
    finally:
        con.close()
    buckets = {b.stage: (b.n, b.k) for b in res.stage_breakdown}
    assert buckets == {"主升阶段": (6, 5), "下跌阶段": (2, 2)}  # S3 第 4 日双红后三日 -1% 是唯一落空
    assert sum(b.n for b in res.stage_breakdown) == res.readout.n == 8
    assert sum(b.k for b in res.stage_breakdown) == res.readout.k == 7
    assert res.stage_breakdown[0].stage == "主升阶段" and res.stage_breakdown[0].p == pytest.approx(5 / 6)
    env = {"tree": "t", "branch": "b", "revision": "r", "dirty": False, "interpreter": "py", "python_version": "3", "duckdb_version": "d"}
    receipt = build_receipt(res, rule_path=None, rule_sha256=None, environment=env)
    assert [b["stage"] for b in receipt["by_market_stage"]] == ["主升阶段", "下跌阶段"]
    assert "按大盘阶段拆分" in render_receipt_markdown(receipt)


# --------------------------------------------------------------------------- #
# 按阶段基准率（第五刀）：每桶自己的 p0、规则内阶段族 BH、第三列对照 same_stage_days
# --------------------------------------------------------------------------- #
_ENV = {"tree": "t", "branch": "b", "revision": "r", "dirty": False, "interpreter": "py", "python_version": "3", "duckdb_version": "d"}


def _mini_stage_run(mini, *, min_n: int = 20):
    doc = copy.deepcopy(BASE_RULE)
    doc["outcome"]["success"]["horizon"] = 3
    doc["min_n"] = min_n
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        return run_rule(con, parse_rule(doc))
    finally:
        con.close()


def test_stage_buckets_carry_their_own_baseline_exact(mini):
    """mini 库手算：主升阶段 universe 内 ok 的 (板块, 日) 14 个、12 个为正 → p0=6/7；下跌阶段 9 个、6 个 → p0=2/3。
    整体 p0=18/23。若阶段过滤被去掉（退化成整体 p0），两桶 p0 都会变成 18/23——这条断言就是那个变异的哨兵。"""
    res = _mini_stage_run(mini)
    rd = res.readout
    assert (rd.baseline_n, rd.baseline_k) == (23, 18) and rd.p0 == pytest.approx(18 / 23)
    by = {b.stage: b for b in res.stage_breakdown}
    assert set(by) == {"主升阶段", "下跌阶段"}
    up, down = by["主升阶段"], by["下跌阶段"]
    assert (up.n, up.k, up.readout.baseline_n, up.readout.baseline_k) == (6, 5, 14, 12)
    assert (down.n, down.k, down.readout.baseline_n, down.readout.baseline_k) == (2, 2, 9, 6)
    assert up.p0 == pytest.approx(6 / 7) and down.p0 == pytest.approx(2 / 3)
    assert up.p0 != pytest.approx(rd.p0) and down.p0 != pytest.approx(rd.p0) and up.p0 != pytest.approx(down.p0)
    # 各阶段基准率的 n / k 之和 = 整体基准率的 n / k（同 universe 同窗口，只是分层）
    assert sum(b.readout.baseline_n for b in res.stage_breakdown) == rd.baseline_n
    assert sum(b.readout.baseline_k for b in res.stage_breakdown) == rd.baseline_k
    assert sum(b.n for b in res.stage_breakdown) == rd.n == 8
    assert up.readout.lift == pytest.approx(5 / 6 - 6 / 7) and down.readout.lift == pytest.approx(1 - 2 / 3)
    # n < min_n=20 → 阶段级一律 insufficient_n，不进 BH 族
    assert all(b.verdict == b.readout.verdict == "insufficient_n" and b.adjusted_p is None and not b.rejected for b in res.stage_breakdown)
    # 第三列对照：p0 = (6·6/7 + 2·2/3) / 8 = 17/21
    sm = res.baseline_stage_matched
    assert sm is not None and sm.kind == "same_stage_days" and (sm.n, sm.k) == (23, 18)
    assert sm.p0 == pytest.approx(17 / 21) and sm.lift == pytest.approx(7 / 8 - 17 / 21)
    assert sm.verdict_if_used == "insufficient_n"

    receipt = build_receipt(res, rule_path=None, rule_sha256=None, environment=_ENV)
    for b in receipt["by_market_stage"]:
        for key in ("p0", "baseline_n", "baseline_k", "lift", "wilson_lo", "wilson_hi", "p_value", "adjusted_p", "verdict_single", "verdict"):
            assert key in b, key
    assert receipt["baseline_stage_matched"]["kind"] == "same_stage_days"
    assert receipt["baseline_stage_matched"]["p0"] == pytest.approx(17 / 21)
    assert receipt["sql"]["baseline_by_stage"]["sql"].count("?") == len(receipt["sql"]["baseline_by_stage"]["params"])
    md = render_receipt_markdown(receipt)
    assert "p0（阶段）" in md and "same_stage_days" in md and "| 主升阶段 | 6 | 5 | 83.3% | 85.7% | -2.4% |" in md


def test_stage_baseline_matches_independent_sql(mini):
    """另写一条不经编译器的 SQL 算各阶段基准率，与 runner 逐桶相等——两条独立路径对账。"""
    res = _mini_stage_run(mini)
    start, end = res.baseline_window
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        rows = con.execute(
            """
            WITH u AS (SELECT DISTINCT entity_id, trade_date FROM history_labels WHERE entity_type='sector' AND trade_date BETWEEN ? AND ?)
            SELECT ms.value_text, COUNT(*), COUNT(*) FILTER (WHERE o.fwd_return > 0)
            FROM u
            JOIN history_outcomes o ON o.entity_type='sector' AND o.entity_id=u.entity_id AND o.trade_date=u.trade_date AND o.horizon=3 AND o.status='ok'
            LEFT JOIN history_labels ms ON ms.entity_type='market' AND ms.entity_id='market' AND ms.label='market_stage' AND ms.trade_date=u.trade_date
            GROUP BY 1
            """,
            [start, end],
        ).fetchall()
    finally:
        con.close()
    independent = {stage: (n, k) for stage, n, k in rows}
    assert independent == {b.stage: (b.readout.baseline_n, b.readout.baseline_k) for b in res.stage_breakdown}


def test_stage_readouts_bh_within_rule_downgrades_borderline_stage():
    """纯函数：阶段 A 单次 supported（15/20 对 p0=0.5，双侧 p≈0.041，Wilson lo≈0.53>0.5，两半 8/10、7/10）；
    单独一个阶段时保住 supported；加进一个不显著的阶段 B（12/20，p≈0.50）后族 m=2，A 的 BH adjusted p≈0.083 > q → 降级。
    n < min_n 的阶段不进族、不被改写。"""
    from intelligence.services.methodology_backtest.stats import stage_readouts

    seq_a = [True] * 8 + [False] * 2 + [True] * 7 + [False] * 3
    seq_b = [True] * 6 + [False] * 4 + [True] * 6 + [False] * 4
    base = {"A": (1000, 500), "B": (1000, 500), "C": (1000, 500)}
    alone = stage_readouts({"A": seq_a}, base, min_n=20, q=0.05)
    assert [(b.stage, b.readout.verdict, b.verdict, b.rejected) for b in alone] == [("A", "supported", "supported", True)]
    assert alone[0].adjusted_p == pytest.approx(alone[0].readout.p_value)

    both = stage_readouts({"B": seq_b, "A": seq_a, "C": [True, False, True]}, base, min_n=20, q=0.05)
    by = {b.stage: b for b in both}
    assert [b.stage for b in both] == ["A", "B", "C"]  # n 降序、同 n 按名
    assert by["A"].readout.verdict == "supported" and by["A"].verdict == "not_distinguishable" and not by["A"].rejected
    assert by["A"].adjusted_p == pytest.approx(min(1.0, by["A"].readout.p_value * 2)) and by["A"].adjusted_p > 0.05
    assert by["B"].readout.verdict == by["B"].verdict == "not_distinguishable"
    assert by["C"].readout.verdict == by["C"].verdict == "insufficient_n" and by["C"].adjusted_p is None
    d = by["A"].to_dict()
    assert d["verdict_single"] == "supported" and d["verdict"] == "not_distinguishable" and d["stage"] == "A" and "verdict" in d


def test_stage_matched_p0_weights_by_event_distribution():
    from intelligence.services.methodology_backtest.stats import stage_matched_p0, stage_readouts

    buckets = stage_readouts({"上": [True] * 6, "下": [True, False]}, {"上": (14, 12), "下": (9, 6)}, min_n=20, q=0.05)
    assert stage_matched_p0(buckets) == pytest.approx((6 * 6 / 7 + 2 * 2 / 3) / 8)
    assert stage_matched_p0([]) is None
    no_base = stage_readouts({"x": [True] * 3}, {}, min_n=20, q=0.05)
    assert no_base[0].p0 is None and stage_matched_p0(no_base) is None


def test_compiler_stage_baseline_sql_parameterized_for_both_kinds():
    rule = parse_rule(BASE_RULE)
    compiled = compile_rule(rule, start="2026-01-01", end="2026-12-31")
    for kind in ("same_universe_all_days", "same_universe_event_days"):
        q = compiled.baseline_by_stage_for("2026-01-01", "2026-12-31", kind=kind, event_dates=["2026-03-02", "2026-03-03"])
        assert q.sql.count("?") == len(q.params) and "GROUP BY ms.value_text" in q.sql
        assert "'market'" not in q.sql and "'market_stage'" not in q.sql  # 大盘标签定位全走绑定参数
        assert q.params[-3:] == ("market", "market", "market_stage")
    empty = compiled.baseline_by_stage_for("2026-01-01", "2026-12-31", kind="same_universe_event_days")
    assert empty.params == () and "WHERE FALSE" in empty.sql
    with pytest.raises(ValueError):
        compiled.baseline_by_stage_for("2026-01-01", "2026-12-31", kind="same_stage_days")


def test_synthetic_positive_control_supported_in_every_stage_with_own_baseline(synthetic, tmp_path):
    """合成库阳性对照（120 日 / 12 板块）：五个阶段各自 p=1.0、各自 p0≈0.5；n ≥ min_n 的阶段 supported 且过规则内 BH，
    n < min_n 的阶段一律 insufficient_n（不因 p=1.0 而升格）；前视夹具翻转后同样按 n 分成 refuted / insufficient_n；
    证伪库条目与 report 带阶段级 p0 / 结论。"""
    from intelligence.services.methodology_backtest.receipts import load_refuted, render_refuted_markdown, summarize_refuted_by_stage, write_refuted

    st = synthetic["st"]
    res = st.run(synthetic["labels"], st.POSITIVE_RULE)
    stages = res.stage_breakdown
    assert len(stages) == 5 and all(b.p == 1.0 for b in stages)
    assert all(0.3 < b.p0 < 0.7 for b in stages), [(b.stage, b.p0) for b in stages]
    big = [b for b in stages if b.n >= 20]
    small = [b for b in stages if b.n < 20]
    assert len(big) >= 3 and small, [(b.stage, b.n) for b in stages]
    assert all(b.readout.verdict == b.verdict == "supported" and b.rejected for b in big)
    assert all(b.readout.verdict == b.verdict == "insufficient_n" and b.adjusted_p is None for b in small)
    assert sum(b.readout.baseline_n for b in stages) == res.readout.baseline_n
    sm = res.baseline_stage_matched
    assert sm is not None and sm.verdict_if_used == "supported" and sm.lift > 0.3

    shifted = _shifted_labels_db(st, synthetic["src"], tmp_path / "labels-shift.duckdb")
    bad = st.run(shifted, st.POSITIVE_RULE)
    assert bad.readout.verdict == "refuted" and all(b.p == 0.0 for b in bad.stage_breakdown)
    assert {b.verdict for b in bad.stage_breakdown if b.n >= 20} == {"refuted"}
    assert {b.verdict for b in bad.stage_breakdown if b.n < 20} <= {"insufficient_n"}
    receipt = build_receipt(bad, rule_path=None, rule_sha256=None, environment=_ENV)
    root = tmp_path / "refuted"
    write_refuted(root, receipt, date_str="2026-09-05", receipt_path=None)
    loaded = load_refuted(root)
    entry = loaded[0]
    assert entry["baseline_stage_matched"]["kind"] == "same_stage_days"
    rows = summarize_refuted_by_stage(loaded)
    assert all(r["p0_stage"] is not None for r in rows)
    assert {r["verdict_stage"] for r in rows if r["n"] >= 20} == {"refuted"}
    md = render_refuted_markdown(loaded)
    assert "p0（阶段）" in md and "`refuted`" in md
    # 老条目（没有阶段级字段）仍能汇总渲染
    legacy = [dict(entry, by_market_stage=[{"stage": "主升阶段", "n": 3, "k": 0, "p": 0.0}])]
    legacy_rows = summarize_refuted_by_stage(legacy)
    assert legacy_rows[0]["p0_stage"] is None and legacy_rows[0]["verdict_stage"] is None
    assert "| — |" in render_refuted_markdown(legacy)


def _shifted_labels_db(st, src: Path, path: Path) -> Path:
    build_labels(src, path)
    build_outcomes(src, path)
    assert st.shift_outcomes_one_day_earlier(path) > 0
    return path


def test_refuted_entry_written_only_for_refuted_verdict(synthetic, tmp_path):
    """前视夹具把阳性对照打成 refuted → 落证伪库，字段齐；supported / not_distinguishable 不落。"""
    from intelligence.services.methodology_backtest.receipts import (
        REFUTED_SCHEMA,
        build_refuted_entry,
        load_refuted,
        render_refuted_markdown,
        summarize_refuted_by_stage,
        write_refuted,
    )

    st = synthetic["st"]
    env = {"tree": "t", "branch": "b", "revision": "r", "dirty": False, "interpreter": "py", "python_version": "3", "duckdb_version": "d"}
    shifted = _shifted_labels_db(st, synthetic["src"], tmp_path / "labels-shift.duckdb")
    res = st.run(shifted, st.POSITIVE_RULE)
    assert res.readout.verdict == "refuted"
    receipt = build_receipt(res, rule_path="methodology/rules/x.v1.json", rule_sha256=None, environment=env)
    root = tmp_path / "refuted"
    assert load_refuted(root) == [] and "证伪库为空" in render_refuted_markdown([])
    path = write_refuted(root, receipt, date_str="2026-09-04", receipt_path="methodology/receipts/x@v1/2026-09-04.json")
    assert path == root / "selftest_positive@v1" / "2026-09-04.json"
    entry = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert entry["schema_version"] == REFUTED_SCHEMA
    for key in ("rule_id", "rule_version", "sharing", "owner", "n", "p", "p0", "ci", "by_market_stage", "refuted_at", "receipt_path"):
        assert key in entry, key
    assert entry["rule_id"] == "selftest_positive" and entry["rule_version"] == 1 and entry["n"] == res.readout.n
    assert entry["ci"]["lo"] == res.readout.lo and entry["ci"]["hi"] < entry["p0"]
    assert entry["by_market_stage"] and sum(b["n"] for b in entry["by_market_stage"]) == entry["n"]
    assert entry["refuted_at"] == receipt["generated_at"]

    loaded = load_refuted(root)
    assert len(loaded) == 1 and loaded[0]["_path"] == str(path)
    rows = summarize_refuted_by_stage(loaded)
    assert rows and all(r["rule_ref"] == "selftest_positive@v1" and r["p0"] == entry["p0"] for r in rows)
    assert {r["stage"] for r in rows} == {b["stage"] for b in entry["by_market_stage"]}
    md = render_refuted_markdown(loaded)
    assert "selftest_positive@v1" in md and "| 大盘阶段 |" in md

    # 非 refuted 的收据进证伪库 → 拒
    good = build_receipt(st.run(synthetic["labels"], st.POSITIVE_RULE), rule_path=None, rule_sha256=None, environment=env)
    assert good["verdict"] == "supported"
    with pytest.raises(ValueError):
        build_refuted_entry(good, receipt_path=None)
    # 坏文件 / 别的 schema 跳过
    (root / "selftest_positive@v1" / "broken.json").write_text("{", encoding="utf-8")
    (root / "selftest_positive@v1" / "other.json").write_text('{"schema_version": "x"}', encoding="utf-8")
    assert len(load_refuted(root)) == 1


def test_cli_run_scan_write_refuted_and_report_refuted(synthetic, tmp_path, capsys):
    cli = _load_script(CLI, "mb_cli_for_pytest_refuted")
    st = synthetic["st"]
    shifted = _shifted_labels_db(st, synthetic["src"], tmp_path / "labels-shift.duckdb")
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    pos = rules_dir / "selftest_positive.v1.json"
    pos.write_text(__import__("json").dumps(st.POSITIVE_RULE, ensure_ascii=False), encoding="utf-8")
    neg = rules_dir / "selftest_negative.v1.json"
    neg.write_text(__import__("json").dumps(st.NEGATIVE_RULE, ensure_ascii=False), encoding="utf-8")
    receipts, refuted = tmp_path / "receipts", tmp_path / "refuted"
    common = ["--receipts-dir", str(receipts), "--refuted-dir", str(refuted)]

    # 正常库：supported → 有收据、无证伪条目
    assert cli.main(["run", str(pos), "--labels-db", str(synthetic["labels"]), *common]) == 0
    assert list((receipts / "selftest_positive@v1").glob("*.json")) and not refuted.exists()
    # 前视库：refuted → 证伪条目落地；--no-write 不落
    assert cli.main(["run", str(pos), "--labels-db", str(shifted), *common, "--no-write"]) == 0
    assert not refuted.exists()
    assert cli.main(["run", str(pos), "--labels-db", str(shifted), *common]) == 0
    entries = list((refuted / "selftest_positive@v1").glob("*.json"))
    assert len(entries) == 1
    capsys.readouterr()
    # scan：阳性 refuted（BH 拒绝 H0）落库，阴性不落
    assert cli.main(["scan", str(pos), str(neg), "--labels-db", str(shifted), *common]) == 0
    assert not (refuted / "selftest_negative@v1").exists()
    doc = __import__("json").loads(entries[0].read_text(encoding="utf-8"))
    assert doc["test_mode"] == "scan" and doc["bh"]["rejected"] is True  # 同日重跑覆盖，最后一次是 scan
    capsys.readouterr()
    assert cli.main(["report", "--refuted", "--refuted-dir", str(refuted), "--labels-db", str(tmp_path / "nope.duckdb")]) == 0
    out = capsys.readouterr().out
    assert "证伪库 · 1 条规则" in out and "selftest_positive@v1" in out and "| 大盘阶段 |" in out
    assert cli.main(["report", "--refuted", "--refuted-dir", str(tmp_path / "empty"), "--labels-db", str(tmp_path / "nope.duckdb")]) == 0
    assert "证伪库为空" in capsys.readouterr().out


def test_cli_propose_sharing_defaults_and_shared_owner_rule(synthetic, tmp_path):
    cli = _load_script(CLI, "mb_cli_for_pytest_propose_sharing")
    rules_dir = tmp_path / "rules"
    base = [
        "propose", "--title", "t", "--entity-type", "sector",
        "--pred", "dual_red_strict == true", "--success", "fwd_return 5 > 0", "--manual-note", "n", "--rules-dir", str(rules_dir),
    ]
    assert cli.main([*base, "--rule-id", "priv_rule", "--user", "alice"]) == 0
    priv = load_rule(rules_dir / "priv_rule.v1.json")
    assert (priv.sharing, priv.owner) == ("private", "alice")
    assert cli.main([*base, "--rule-id", "shared_rule", "--sharing", "shared", "--source-perspective", "系统内置"]) == 0
    shared = load_rule(rules_dir / "shared_rule.v1.json")
    assert (shared.sharing, shared.owner, shared.raw["source_perspective"]) == ("shared", "system", "系统内置")
    assert cli.main([*base, "--rule-id", "bad_shared", "--sharing", "shared", "--owner", "alice"]) == 2
    assert not (rules_dir / "bad_shared.v1.json").exists()


def test_sector_label_semantics(mini):
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        streak = _label(con, "sector", "S1.TI", "dual_red_streak")
        assert [streak[i] for i in range(9)] == [1, 2, 3, 4, 0, 1, None, 1, 2]
        dr = _label(con, "sector", "S1.TI", "dual_red_strict")
        assert dr[GAP] is None and dr[0] == 1 and dr[4] == 0
        turn = _label(con, "sector", "S2.TI", "diff_ratio_turn_up")
        assert turn[0] is None  # 无前一日
        assert [turn[i] for i in range(1, 8)] == [1, 0, 0, 0, 1, None, None]
        s3 = _label(con, "sector", "S3.TI", "dual_red_streak")
        assert 3 not in s3 and s3[4] == 1  # 缺行日无标签；断档后重新计数
        assert _label(con, "sector", "S3.TI", "diff_ratio_turn_up")[4] is None
        mpr = _label(con, "sector", "S1.TI", "multi_period_resonance")
        assert mpr[1] == 1 and mpr[0] is None
        top = con.execute(
            "SELECT SUM(value_num), COUNT(*) FROM history_labels WHERE label='amount_rank_top10' AND trade_date=?",
            [DAYS[9]],
        ).fetchone()
        assert top == (10, 15)
    finally:
        con.close()


def test_theme_and_market_label_semantics(mini):
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        rank = _label(con, "theme", "S1.TI", "limit_heat_rank")
        assert rank == {0: 10, 1: 4, 2: 3, 4: 1}  # proxy 档第 3 日不进
        jump = _label(con, "theme", "S1.TI", "limit_heat_rank_jump")
        assert jump == {0: None, 1: 1, 2: 0, 4: None}
        ml = _label(con, "theme", "S1.TI", "mainline_flag")
        assert ml == {0: None, 1: None, 2: 1, 4: 0}
        stage = _label(con, "market", "market", "market_stage")
        assert stage[0] == "主升阶段" and stage[6] == "下跌阶段"
        vs = _label(con, "market", "market", "volume_surge")
        assert vs[0] is None and vs[3] == 1 and vs[4] == 0
        assert set(_label(con, "market", "market", "ma5_peak_confirmed").values()) <= {0, 1}
    finally:
        con.close()


def test_outcomes_window_excludes_label_day(mini):
    """前视靶点：S1 第 0 日 +5%，之后 1/2/1/-0.5/0.5 → T+3 = 1.01*1.02*1.01-1 ≈ 4.06%，不含 D0 的 +5%。

    变异：outcomes.WINDOW_START_OFFSET=0 时窗口变成 D0..D+2 = 1.05*1.01*1.02-1 ≈ 8.17%，本测试变红。
    """
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        row = con.execute(
            "SELECT fwd_return, max_return, days_to_peak, drawdown_after_peak, status FROM history_outcomes "
            "WHERE entity_type='sector' AND entity_id='S1.TI' AND trade_date=? AND horizon=3",
            [DAYS[0]],
        ).fetchone()
        fwd, mx, peak, dd, status = row
        assert status == "ok"
        assert fwd == pytest.approx((1.01 * 1.02 * 1.01 - 1) * 100, abs=1e-9)
        assert mx == pytest.approx(fwd, abs=1e-9) and peak == 3 and dd == pytest.approx(0.0, abs=1e-9)
        # T+5：路径 1,2,1,-0.5,0.5 → 峰值在第 3 步，之后回撤
        fwd5, mx5, peak5, dd5, _ = con.execute(
            "SELECT fwd_return, max_return, days_to_peak, drawdown_after_peak, status FROM history_outcomes "
            "WHERE entity_type='sector' AND entity_id='S1.TI' AND trade_date=? AND horizon=5",
            [DAYS[0]],
        ).fetchone()
        path = [1.01 * 1.02 * 1.01, 1.01 * 1.02 * 1.01 * 0.995, 1.01 * 1.02 * 1.01 * 0.995 * 1.005]
        assert fwd5 == pytest.approx((path[-1] - 1) * 100, abs=1e-9)
        assert peak5 == 3 and mx5 == pytest.approx((path[0] - 1) * 100, abs=1e-9)
        assert dd5 == pytest.approx((path[-1] / path[0] - 1) * 100, abs=1e-9)
        assert outcomes_mod.WINDOW_START_OFFSET == 1
    finally:
        con.close()


def test_outcomes_status_pending_and_missing(mini):
    con = duckdb.connect(str(mini["labels"]), read_only=True)
    try:
        status_last = con.execute(
            "SELECT status FROM history_outcomes WHERE entity_id='S1.TI' AND trade_date=? AND horizon=3", [DAYS[-1]]
        ).fetchone()[0]
        assert status_last == "pending"
        status_s3 = con.execute(
            "SELECT status FROM history_outcomes WHERE entity_id='S3.TI' AND trade_date=? AND horizon=3", [DAYS[1]]
        ).fetchone()[0]
        assert status_s3 == "missing"  # 第 3 日缺行落在窗口内
        theme_eq = con.execute(
            "SELECT COUNT(*) FILTER (WHERE t.fwd_return = s.fwd_return), COUNT(*) FROM history_outcomes t "
            "JOIN history_outcomes s ON s.entity_type='sector' AND s.entity_id=t.entity_id AND s.trade_date=t.trade_date AND s.horizon=t.horizon "
            "WHERE t.entity_type='theme' AND t.status='ok'"
        ).fetchone()
        assert theme_eq[0] == theme_eq[1] > 0
    finally:
        con.close()


def test_rebuild_is_idempotent_and_recreatable(tmp_path):
    src = tmp_path / "src.duckdb"
    lab = tmp_path / "labels.duckdb"
    _build_mini_db(src)
    r1 = build_labels(src, lab)
    r2 = build_labels(src, lab)
    assert r1.row_count == r2.row_count == sum(r1.rows_by_label.values())
    lab.unlink()
    r3 = build_labels(src, lab)
    assert r3.row_count == r1.row_count and r3.rows_by_label == r1.rows_by_label


def test_conditions_fail_closed_when_builds_diverge(tmp_path):
    src = tmp_path / "src.duckdb"
    lab = tmp_path / "labels.duckdb"
    _build_mini_db(src)
    build_labels(src, lab)
    with pytest.raises(RuntimeError):
        con = duckdb.connect(str(lab), read_only=True)
        try:
            load_conditions(con)  # 缺 outcomes
        finally:
            con.close()
    build_outcomes(src, lab)
    con = duckdb.connect(str(lab))
    try:
        con.execute("UPDATE history_build_meta SET source_max_trade_date = DATE '2000-01-01' WHERE build_kind='outcomes'")
    finally:
        con.close()
    con = duckdb.connect(str(lab), read_only=True)
    try:
        with pytest.raises(RuntimeError, match="不一致"):
            load_conditions(con)
    finally:
        con.close()


def test_rule_horizon_not_built_is_rejected(tmp_path):
    src = tmp_path / "src.duckdb"
    lab = tmp_path / "labels.duckdb"
    _build_mini_db(src)
    build_labels(src, lab)
    build_outcomes(src, lab, horizons=(3,))
    doc = copy.deepcopy(BASE_RULE)
    con = duckdb.connect(str(lab), read_only=True)
    try:
        with pytest.raises(RuntimeError, match="没有构建"):
            run_rule(con, parse_rule(doc))
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# 合成库端到端：阳性 / 阴性 / 前视（复用 selftest 的生成器）
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    st = _load_script(SELFTEST, "mb_selftest_for_pytest")
    root = tmp_path_factory.mktemp("synthetic")
    src = root / "src.duckdb"
    lab = root / "labels.duckdb"
    planted = st.build_sample_db(src, n_days=120, n_sectors=12)
    build_labels(src, lab)
    build_outcomes(src, lab)
    return {"st": st, "src": src, "labels": lab, "planted": planted}


def test_positive_control_supported(synthetic):
    st = synthetic["st"]
    res = st.run(synthetic["labels"], st.POSITIVE_RULE)
    rd = res.readout
    assert rd.verdict == "supported" and rd.lo > rd.p0
    assert rd.n + res.n_pending == synthetic["planted"]["n_events"]


def test_negative_control_not_supported(synthetic):
    st = synthetic["st"]
    rd = st.run(synthetic["labels"], st.NEGATIVE_RULE).readout
    assert rd.verdict in ("not_distinguishable", "insufficient_n")


def test_lookahead_shift_flips_positive_control(synthetic, tmp_path):
    """outcomes 整体前移一个交易日 → 阳性对照的 supported 必须消失；重建后恢复。"""
    st = synthetic["st"]
    lab = tmp_path / "labels-shift.duckdb"
    build_labels(synthetic["src"], lab)
    build_outcomes(synthetic["src"], lab)
    assert st.run(lab, st.POSITIVE_RULE).readout.verdict == "supported"
    assert st.shift_outcomes_one_day_earlier(lab) > 0
    assert st.run(lab, st.POSITIVE_RULE).readout.verdict != "supported"
    build_outcomes(synthetic["src"], lab)
    assert st.run(lab, st.POSITIVE_RULE).readout.verdict == "supported"


def test_stock_positive_control_with_union_universe_baseline(synthetic):
    """个股阳性对照 supported；基准率取「涨停表 ∪ 新高表」并集，比事件集大、比全市场小；对照列同存。"""
    st = synthetic["st"]
    planted = synthetic["planted"]
    res = st.run(synthetic["labels"], st.STOCK_POSITIVE_RULE)
    rd = res.readout
    assert rd.verdict == "supported" and rd.lo > rd.p0
    assert rd.n + res.n_pending == planted["n_first_boards"]
    full_market = planted["n_stocks"] * planted["n_days"]
    assert rd.n < rd.baseline_n <= planted["n_stock_universe"] < full_market
    assert res.baseline_alt is not None and res.baseline_alt.kind == "same_universe_event_days"
    assert 0 < res.baseline_alt.n <= rd.baseline_n
    # limit_up 比 first_board 宽（二连板也算），且二连板窗口为负 → 命中率更低
    wide = st.run(synthetic["labels"], {**st.STOCK_POSITIVE_RULE, "rule_id": "wide",
                                        "condition": {"all": [{"label": "limit_up", "op": "==", "value": True, "lag": 0}]}}).readout
    assert wide.n > rd.n and wide.p < rd.p
    # 个股规则不会误取板块 universe：换成 sector 同谓词直接被白名单拒
    with pytest.raises(RuleValidationError):
        parse_rule({**st.STOCK_POSITIVE_RULE, "scope": {"entity_type": "sector", "universe": "published_snapshot"}})


def test_cli_propose_stock_rule_and_run(synthetic, tmp_path):
    cli = _load_script(CLI, "mb_cli_for_pytest_propose_stock")
    rules_dir = tmp_path / "rules"
    args = [
        "propose", "--rule-id", "first_board_then_up", "--title", "首板后 5 日上涨", "--entity-type", "stock",
        "--pred", "first_board == true", "--pred", "market:volume_surge@1 == false",
        "--success", "fwd_return 5 > 0", "--manual-note", "个股 P1 冒烟", "--rules-dir", str(rules_dir),
    ]
    assert cli.main(args) == 0
    rule = load_rule(rules_dir / "first_board_then_up.v1.json")
    assert rule.entity_type == "stock" and rule.universe == "limit_high_union"
    assert rule.predicates[0].entity_type == "stock" and rule.predicates[1].entity_type == "market"
    assert cli.main(["run", str(rules_dir / "first_board_then_up.v1.json"), "--labels-db", str(synthetic["labels"]), "--no-write"]) == 0
    # entity_type 不在白名单 → argparse 直接拒
    with pytest.raises(SystemExit):
        cli.main([*args[:5], "--entity-type", "index", *args[7:]])


def test_scan_applies_bh_and_marks_exploratory(synthetic):
    st = synthetic["st"]
    third = copy.deepcopy(st.POSITIVE_RULE)
    third["rule_id"] = "selftest_third"
    third["condition"] = {"all": [{"label": "dual_red_streak", "op": ">=", "value": 1, "lag": 0}]}
    rules = [parse_rule(st.POSITIVE_RULE), parse_rule(st.NEGATIVE_RULE), parse_rule(third)]
    con = duckdb.connect(str(synthetic["labels"]), read_only=True)
    try:
        scan = scan_rules(con, rules)
    finally:
        con.close()
    assert len(scan.verdicts_bh) == 3 and len(scan.adjusted_p) == 3
    assert scan.verdicts_bh[0] == "supported" and scan.rejected[0]
    assert scan.verdicts_bh[1] != "supported"
    env = {"tree": "t", "branch": "b", "revision": "r", "dirty": False, "interpreter": "py", "python_version": "3", "duckdb_version": "d"}
    receipt = build_receipt(
        scan.results[0],
        rule_path=None,
        rule_sha256=None,
        environment=env,
        test_mode="scan",
        bh={"q": 0.05, "family": [r.ref for r in rules], "adjusted_p": scan.adjusted_p[0], "rejected": True, "verdict_bh": scan.verdicts_bh[0]},
    )
    assert receipt["exploratory"] is True
    for key in ("source_max_trade_date", "label_version", "rule_ref", "n", "data_gap_days", "environment"):
        assert key in receipt["conditions"]
    md = render_receipt_markdown(receipt)
    assert "成立条件" in md and "Wilson" in md


def test_latest_receipt_picks_newest_across_versions(synthetic, tmp_path):
    """P1 统计门读的是规则最近一次收据：跨版本按 generated_at 取，坏文件与别的 schema 跳过。"""
    from intelligence.services.methodology_backtest.receipts import latest_receipt, write_receipt

    st = synthetic["st"]
    res = st.run(synthetic["labels"], st.POSITIVE_RULE)
    env = {"tree": "t", "branch": "b", "revision": "r", "dirty": False, "interpreter": "py", "python_version": "3", "duckdb_version": "d"}
    root = tmp_path / "receipts"
    old = build_receipt(res, rule_path=None, rule_sha256=None, environment=env, now=__import__("datetime").datetime(2026, 9, 1, tzinfo=__import__("datetime").timezone.utc))
    write_receipt(root, old, date_str="2026-09-01")
    v2_rule = copy.deepcopy(st.POSITIVE_RULE)
    v2_rule["version"] = 2
    res2 = st.run(synthetic["labels"], v2_rule)
    new = build_receipt(res2, rule_path=None, rule_sha256=None, environment=env, now=__import__("datetime").datetime(2026, 9, 3, tzinfo=__import__("datetime").timezone.utc))
    write_receipt(root, new, date_str="2026-09-03")
    (root / "selftest_positive@v1" / "broken.json").write_text("{not json", encoding="utf-8")
    (root / "scan").mkdir()
    (root / "scan" / "2026-09-04.json").write_text(__import__("json").dumps({"schema_version": "methodology-backtest-scan/v0"}), encoding="utf-8")

    got = latest_receipt(root, "selftest_positive")
    assert got is not None and got["rule"]["ref"] == "selftest_positive@v2"
    assert got["verdict"] == "supported" and got["_path"].endswith("selftest_positive@v2/2026-09-03.json")
    assert latest_receipt(root, "nope") is None
    assert latest_receipt(tmp_path / "missing", "selftest_positive") is None


def test_cli_answer_score_gate_refuses_promotion_without_supported_receipt(synthetic, tmp_path):
    """经验卡统计门端到端：not_distinguishable 的规则不能把卡晋升为 methodology；candidate 仍可落卡。"""
    from intelligence import cli as intel_cli
    from intelligence.services.methodology_backtest.receipts import write_receipt

    st = synthetic["st"]
    env = {"tree": "t", "branch": "b", "revision": "r", "dirty": False, "interpreter": "py", "python_version": "3", "duckdb_version": "d"}
    root = tmp_path / "receipts"
    neg = build_receipt(st.run(synthetic["labels"], st.NEGATIVE_RULE), rule_path=None, rule_sha256=None, environment=env)
    write_receipt(root, neg, date_str="2026-09-04")
    pos = build_receipt(st.run(synthetic["labels"], st.POSITIVE_RULE), rule_path=None, rule_sha256=None, environment=env)
    write_receipt(root, pos, date_str="2026-09-04")
    cards = tmp_path / "cards.jsonl"
    common = [
        "answer-score", "--question", "双红后还涨吗", "--answer", "会涨。（非投资建议）",
        "--local-source", "market_feature_store", "--save-card", "--card-file", str(cards),
        "--receipts-dir", str(root), "--json",
    ]
    assert intel_cli.main([*common, "--promotion", "methodology", "--rule-id", "selftest_negative"]) == 2
    assert not cards.exists()
    assert intel_cli.main([*common, "--promotion", "methodology", "--rule-id", "nope_rule"]) == 2
    assert intel_cli.main([*common, "--promotion", "candidate", "--rule-id", "selftest_negative"]) == 0
    assert intel_cli.main([*common, "--promotion", "methodology", "--rule-id", "selftest_positive"]) == 0
    rows = [__import__("json").loads(line) for line in cards.read_text(encoding="utf-8").splitlines()]
    assert [r["promotion"] for r in rows] == ["candidate", "methodology"]
    assert rows[0]["rule_verdict"] != "supported" and rows[1]["rule_verdict"] == "supported"
    assert rows[1]["rule_receipt"].endswith("selftest_positive@v1/2026-09-04.json")


# --------------------------------------------------------------------------- #
# 基准率两种口径：声明的定结论，另一种作对照
# --------------------------------------------------------------------------- #
def test_compiler_event_day_baseline_binds_dates():
    rule = parse_rule({**BASE_RULE, "baseline": {"kind": "same_universe_event_days"}})
    compiled = compile_rule(rule, start="2026-01-01", end="2026-12-31")
    assert compiled.baseline_kind == "same_universe_event_days"
    q = compiled.baseline_for("2026-01-01", "2026-12-31", event_dates=["2026-03-02", "2026-03-04", "2026-03-02"])
    assert q.sql.count("?") == len(q.params) and q.params[1:3] == ("2026-03-02", "2026-03-04")
    assert "IN (?, ?)" in q.sql and "BETWEEN" not in q.sql
    empty = compiled.baseline_for("2026-01-01", "2026-12-31", event_dates=[])
    assert empty.params == () and "SELECT 0" in empty.sql
    other = compiled.baseline_for("2026-01-01", "2026-12-31", kind="same_universe_all_days")
    assert "BETWEEN ? AND ?" in other.sql and other.params[1:3] == ("2026-01-01", "2026-12-31")
    with pytest.raises(ValueError):
        compiled.baseline_for("2026-01-01", "2026-12-31", kind="made_up")


def test_runner_reports_alternative_baseline_as_comparison(synthetic):
    """阳性对照下两种口径都该 supported；对照列只记读数，不改结论。"""
    st = synthetic["st"]
    con = duckdb.connect(str(synthetic["labels"]), read_only=True)
    try:
        primary = run_rule(con, parse_rule(st.POSITIVE_RULE))
        swapped = run_rule(con, parse_rule({**st.POSITIVE_RULE, "baseline": {"kind": "same_universe_event_days"}}))
    finally:
        con.close()
    assert primary.baseline_alt is not None and primary.baseline_alt.kind == "same_universe_event_days"
    assert swapped.baseline_alt is not None and swapped.baseline_alt.kind == "same_universe_all_days"
    # 互为对照：A 的主基准 == B 的对照基准
    assert primary.baseline_alt.n == swapped.readout.baseline_n and primary.baseline_alt.k == swapped.readout.baseline_k
    assert swapped.baseline_alt.n == primary.readout.baseline_n
    assert primary.readout.verdict == swapped.readout.verdict == "supported"
    assert primary.baseline_alt.verdict_if_used == "supported"
    # 事件日口径的 universe 只含事件日：行数必然 <= 全日期口径
    assert primary.baseline_alt.n <= primary.readout.baseline_n
    env = {"tree": "t", "branch": "b", "revision": "r", "dirty": False, "interpreter": "py", "python_version": "3", "duckdb_version": "d"}
    receipt = build_receipt(primary, rule_path=None, rule_sha256=None, environment=env)
    assert receipt["baseline_kind"] == "same_universe_all_days" and receipt["baseline_alt"]["kind"] == "same_universe_event_days"
    assert "对照基准率" in render_receipt_markdown(receipt)


# --------------------------------------------------------------------------- #
# 纠偏 → 候选规则登记入口
# --------------------------------------------------------------------------- #
def test_parse_predicate_grammar():
    from intelligence.services.methodology_backtest.propose import parse_predicate, parse_success

    assert parse_predicate("dual_red_strict == true") == {"label": "dual_red_strict", "op": "==", "value": True, "lag": 0}
    assert parse_predicate("dual_red_streak@1 >= 3") == {"label": "dual_red_streak", "op": ">=", "value": 3, "lag": 1}
    assert parse_predicate("market:market_stage in 主升阶段,主升") == {
        "label": "market_stage", "op": "in", "value": ["主升阶段", "主升"], "lag": 0, "entity": "market",
    }
    assert parse_predicate("limit_heat_rank <= 10.5")["value"] == 10.5
    assert parse_success("fwd_return 5 > 0") == {"metric": "fwd_return", "horizon": 5, "op": ">", "value": 0.0}
    for bad in ("dual_red_strict", "dual_red_strict === true", "x@-1 > 0", ""):
        with pytest.raises(ValueError):
            parse_predicate(bad)
    with pytest.raises(ValueError):
        parse_success("fwd_return > 0")


def test_build_rule_doc_validates_and_pins_provenance(tmp_path):
    from intelligence.services.methodology_backtest.propose import (
        build_rule_doc,
        correction_provenance,
        find_correction,
        parse_predicate,
        parse_success,
        write_rule_file,
    )

    records = [
        {"ts": "2026-09-01T10:00:00", "id": "abc123def456", "correction": "双红要连三天才算启动", "principle": "连续双红看第三天", "themes": ["双红"]},
        {"ts": "2026-09-02T10:00:00", "correction": "无 id 的旧行"},
    ]
    assert find_correction(records, "abc123def456") is records[0]
    assert find_correction(records, "2026-09-02T10:00:00") is records[1]
    assert find_correction(records, "nope") is None
    prov = correction_provenance(records[0], user="tester", now=__import__("datetime").datetime(2026, 9, 4, tzinfo=__import__("datetime").timezone.utc))
    assert prov["kind"] == "correction" and prov["ref"] == "abc123def456" and prov["text"] == "连续双红看第三天" and prov["user"] == "tester"

    doc, rule = build_rule_doc(
        rule_id="dual_red_third_day",
        title="连续双红第三天后 5 日上涨",
        entity_type="sector",
        predicates=[parse_predicate("dual_red_strict == true"), parse_predicate("dual_red_streak >= 3")],
        success=parse_success("fwd_return 5 > 0"),
        horizons=[3, 10],
        provenance=prov,
        owner="tester",
    )
    assert rule.ref == "dual_red_third_day@v1"
    assert doc["outcome"]["horizons"] == [3, 5, 10]  # success 的窗口自动并入
    assert doc["provenance"]["ref"] == "abc123def456"
    assert (rule.sharing, rule.owner) == ("private", "tester")  # 纠偏是某人的纠偏，候选默认私有
    path = write_rule_file(tmp_path, doc)
    assert path.name == "dual_red_third_day.v1.json"
    assert load_rule(path).raw["provenance"]["kind"] == "correction"
    with pytest.raises(FileExistsError):
        write_rule_file(tmp_path, doc)

    # 白名单仍然生效：谓词短句语法对但 label 不在白名单 → 带字段路径的校验错
    with pytest.raises(RuleValidationError) as exc:
        build_rule_doc(
            rule_id="bad_label_rule", title="t", entity_type="sector", owner="tester",
            predicates=[parse_predicate("sector_close > 0")], success=parse_success("fwd_return 5 > 0"),
        )
    assert any(e.path == "condition.all[0].label" for e in exc.value.errors)
    # 归属：private 没给 owner 拒；shared 自动 owner=system
    with pytest.raises(RuleValidationError) as exc:
        build_rule_doc(
            rule_id="no_owner", title="t", entity_type="sector",
            predicates=[parse_predicate("dual_red_strict == true")], success=parse_success("fwd_return 5 > 0"),
        )
    assert any(e.path == "owner" for e in exc.value.errors)
    _, shared = build_rule_doc(
        rule_id="shared_rule", title="t", entity_type="sector", sharing="shared", source_perspective="某视角",
        predicates=[parse_predicate("dual_red_strict == true")], success=parse_success("fwd_return 5 > 0"),
    )
    assert (shared.sharing, shared.owner, shared.raw["source_perspective"]) == ("shared", "system", "某视角")
    # provenance 本身也过白名单
    rule2, errors = validate_rule({**doc, "rule_id": "prov_bad", "provenance": {"kind": "llm", "sql": "x"}})
    assert rule2 is None and {e.path for e in errors} >= {"provenance.kind", "provenance.sql"}


def test_cli_propose_writes_rule_and_refuses_overwrite(synthetic, tmp_path):
    cli = _load_script(CLI, "mb_cli_for_pytest_propose")
    corrections = tmp_path / "corrections.jsonl"
    corrections.write_text(
        __import__("json").dumps({"ts": "2026-09-01T10:00:00", "id": "c0ffee000001", "correction": "边际量拐头当天别追", "principle": "拐点看次日"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rules_dir = tmp_path / "rules"
    args = [
        "propose", "--rule-id", "turn_up_next_day", "--title", "拐点次日再看 3 日", "--entity-type", "sector",
        "--pred", "diff_ratio_turn_up@1 == true", "--pred", "market:volume_surge == true",
        "--success", "fwd_return 3 > 0", "--min-n", "30",
        "--from-correction", "c0ffee000001", "--corrections-file", str(corrections), "--rules-dir", str(rules_dir),
    ]
    assert cli.main(args) == 0
    written = rules_dir / "turn_up_next_day.v1.json"
    rule = load_rule(written)
    assert rule.min_n == 30 and rule.predicates[0].lag == 1 and rule.predicates[1].entity_type == "market"
    assert rule.raw["provenance"] == {**rule.raw["provenance"], "kind": "correction", "ref": "c0ffee000001", "text": "拐点看次日"}
    assert cli.main(args) == 2  # 不覆盖已存在版本
    assert cli.main([*args[:-2], "--rules-dir", str(rules_dir), "--from-correction", "missing"]) == 2
    # 登记出来的规则能直接跑
    assert cli.main(["run", str(written), "--labels-db", str(synthetic["labels"]), "--no-write"]) == 0


def test_cli_run_and_invalid_rule_exit_codes(synthetic, tmp_path):
    cli = _load_script(CLI, "mb_cli_for_pytest")
    st = synthetic["st"]
    rule_path = tmp_path / "selftest_positive.v1.json"
    rule_path.write_text(__import__("json").dumps(st.POSITIVE_RULE, ensure_ascii=False), encoding="utf-8")
    receipts = tmp_path / "receipts"
    rc = cli.main(["run", str(rule_path), "--labels-db", str(synthetic["labels"]), "--receipts-dir", str(receipts)])
    assert rc == 0
    written = list((receipts / "selftest_positive@v1").glob("*.json"))
    assert len(written) == 1
    bad = tmp_path / "bad_rule.v1.json"
    bad.write_text('{"rule_id": "bad_rule", "version": 1}', encoding="utf-8")
    assert cli.main(["run", str(bad), "--labels-db", str(synthetic["labels"]), "--no-write"]) == 2
    assert cli.main(["run", str(rule_path), "--labels-db", str(tmp_path / "nope.duckdb"), "--no-write"]) == 2

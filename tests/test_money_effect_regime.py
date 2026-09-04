"""赚钱效应 regime（market_feature_store.money_effect_regime）的机制测试。

守四件事：
1. 四条决策表各能命中一簇，且阈值只有 THRESHOLD_QUANTILES 一份定义（别处不得抄数字）；
2. 去抖是因果的：新簇第 1 日不切、第 2 日切——把 DEBOUNCE_DAYS 改成 1 这里必须红（变异测试）；
3. 分位阈值随滚动窗口变化，且 lookback 上限真的生效；
4. 无前视：整段一次算完 == 逐日 as_of 截断各算一次。
簇标签（k-means）不进仓，所以这里没有「一致率」断言——那是实验目录与 registry decisions 的事。
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import numpy as np
import pytest

from market_feature_store import money_effect_regime as mer

ROOT = Path(__file__).resolve().parents[1]
DAY0 = date(2025, 1, 6)


def _day(i: int) -> str:
    return (DAY0 + timedelta(days=i)).isoformat()


def _vec(i: int, **override) -> dict:
    base = {
        "trade_date": _day(i),
        "total_amount": 15000.0,
        "advancers": 3000,
        "limit_up": 60,
        "limit_down": 20,
        "sh_deviation_pct": None,  # 该维允许缺，规则不用
        "sh_index_pct_chg": 0.0,
        "max_boards": 5.0,
        "double_red_theme_count": 15.0,
        "top1_theme_share": 25.0,
        "new_high_count": 600.0,
    }
    base.update(override)
    return base


def _scenario() -> list[dict]:
    """70 天平稳 → 10 天巨量+新高少 → 10 天巨量+新高多 → 10 天缩量+主线。"""
    rows = [_vec(i) for i in range(70)]
    rows += [_vec(i, total_amount=30000.0, new_high_count=300.0) for i in range(70, 80)]
    rows += [_vec(i, total_amount=30000.0, new_high_count=900.0) for i in range(80, 90)]
    rows += [_vec(i, top1_theme_share=40.0, max_boards=8.0) for i in range(90, 100)]
    return rows


def _by_date(series):
    return {rd.trade_date: rd for rd in series}


# ---------------------------------------------------------------------------
# 分位与阈值
# ---------------------------------------------------------------------------


def test_quantile_matches_numpy_linear():
    rng = np.random.default_rng(7)
    values = list(rng.normal(size=53))
    for q in (0.0, 0.36, 0.5, 0.59, 0.75, 0.78, 1.0):
        assert mer.quantile(values, q) == pytest.approx(float(np.quantile(values, q)))
    with pytest.raises(ValueError):
        mer.quantile([], 0.5)


def test_threshold_quantiles_are_the_only_numeric_definition():
    """阈值单一真本源：模块里的分位数只在 THRESHOLD_QUANTILES；cli / reports 不得再写一份。"""
    assert set(mer.THRESHOLD_QUANTILES) == {"amount_huge", "amount_high", "new_high_low", "share_high", "boards_high"}
    for key, (axis, q) in mer.THRESHOLD_QUANTILES.items():
        assert axis in mer.AXES, key
        assert 0.0 < q < 1.0, key
    pattern = re.compile(r"THRESHOLD_QUANTILES\s*(?::[^=]*)?=\s*\{")
    hits = [
        p.relative_to(ROOT).as_posix()
        for top in ("market_feature_store", "intelligence")
        for p in (ROOT / top).rglob("*.py")
        if "tests" not in p.parts and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert hits == ["market_feature_store/money_effect_regime.py"], hits


def test_rolling_thresholds_follow_the_window_and_respect_lookback_cap():
    days = [_vec(i, total_amount=10000.0 + 100.0 * i) for i in range(40)]
    windows = mer.trailing_windows(days)
    early = mer.rolling_thresholds(windows, 19, lookback=250, min_history=10)
    late = mer.rolling_thresholds(windows, 35, lookback=250, min_history=10)
    assert early is not None and late is not None
    assert late["amount_high"] > early["amount_high"]
    # lookback 上限：index 35 只看 26..35 这 10 个窗口
    capped = mer.rolling_thresholds(windows, 35, lookback=10, min_history=10)
    sample = [w.means["total_amount"] for w in windows[26:36]]
    assert capped is not None
    assert capped["amount_high"] == pytest.approx(float(np.quantile(sample, 0.59)))
    assert mer.rolling_thresholds(windows, 5, lookback=250, min_history=10) is None


# ---------------------------------------------------------------------------
# 决策表与四簇
# ---------------------------------------------------------------------------


def test_decision_table_hits_each_regime_in_order():
    thr = {"amount_huge": 26000.0, "amount_high": 22000.0, "new_high_low": 464.0, "share_high": 29.0, "boards_high": 6.0}
    base = {"total_amount": 15000.0, "new_high_count": 600.0, "top1_theme_share": 25.0, "max_boards": 5.0}
    assert mer.classify({**base, "total_amount": 30000.0, "new_high_count": 300.0}, thr) == "巨量轮动"
    assert mer.classify({**base, "total_amount": 30000.0, "new_high_count": 900.0}, thr) == "放量分化"
    assert mer.classify({**base, "total_amount": 23000.0}, thr) == "放量分化"
    assert mer.classify({**base, "top1_theme_share": 35.0, "max_boards": 7.0}, thr) == "主线引领"
    assert mer.classify({**base, "top1_theme_share": 35.0, "max_boards": 6.0}, thr) == "缩量普涨"  # 连板 = 阈值不算超过
    assert mer.classify(base, thr) == "缩量普涨"
    # ① 优先于 ③：巨量且主线特征并存时判巨量轮动
    assert mer.classify({"total_amount": 30000.0, "new_high_count": 300.0, "top1_theme_share": 35.0, "max_boards": 7.0}, thr) == "巨量轮动"


def test_scenario_series_reaches_all_four_regimes():
    series = mer.compute_regime_series(_scenario())
    by = _by_date(series)
    assert by[_day(65)].regime == "缩量普涨"
    assert by[_day(78)].raw_regime == "巨量轮动"
    assert by[_day(88)].raw_regime == "放量分化"
    assert by[_day(98)].raw_regime == "主线引领"
    assert {rd.regime for rd in series if rd.regime} == set(mer.REGIMES)
    # 窗口不足 MIN_HISTORY 的前段不出簇名（fail closed）
    assert by[_day(50)].regime is None and by[_day(50)].raw_regime is None
    assert series[mer.MIN_HISTORY + mer.WINDOW - 2].regime is not None


def test_available_days_requires_nine_dims_but_not_deviation():
    rows = [_vec(0), _vec(1, max_boards=None), _vec(2, sh_deviation_pct=1.2)]
    kept = mer.available_days(rows)
    assert [r["trade_date"] for r in kept] == [_day(0), _day(2)]


# ---------------------------------------------------------------------------
# 去抖（含变异测试的靶子）
# ---------------------------------------------------------------------------


def test_debounce_is_causal_first_day_holds_second_day_switches():
    raw = ["A", "A", "A", "B", "B", "B", "A", "B", "B", "C", "C"]
    assert mer.debounce(raw, days=2) == ["A", "A", "A", "A", "B", "B", "B", "B", "B", "B", "C"]
    #                                                 ^第1日不切 ^第2日切        ^孤立的 A 不切  ^孤立 B 不切回
    assert mer.debounce([None, None, "A", "B", "B"], days=2) == [None, None, "A", "A", "B"]
    with pytest.raises(ValueError):
        mer.debounce(raw, days=0)


def test_scenario_switch_count_with_production_debounce():
    """变异靶：把 money_effect_regime.DEBOUNCE_DAYS 从 2 改成 1，这条必须红。

    场景里原始标签在 70/80/90 三处各切一次（窗口混合期可能多抖一下），
    因果 2 日去抖后切换日 = 新簇第 2 日，且切换总数固定为 3。
    """
    series = mer.compute_regime_series(_scenario())
    by = _by_date(series)
    switches = [rd.trade_date for rd in series if rd.switched]
    assert len(switches) == 3, switches
    first_raw_change = next(rd.trade_date for rd in series if rd.raw_regime not in (None, "缩量普涨"))
    assert by[first_raw_change].regime == "缩量普涨", "新簇第 1 日不得切换"
    idx = [rd.trade_date for rd in series].index(first_raw_change)
    assert series[idx + 1].switched and series[idx + 1].regime == series[idx].raw_regime
    assert switches[0] == series[idx + 1].trade_date
    assert mer.DEBOUNCE_DAYS == 2


# ---------------------------------------------------------------------------
# 无前视
# ---------------------------------------------------------------------------


def test_full_series_equals_as_of_truncation():
    rows = _scenario()
    full = _by_date(mer.compute_regime_series(rows))
    for cut in (66, 71, 79, 85, 93, 99):
        truncated = mer.compute_regime_series([r for r in rows if r["trade_date"] <= _day(cut)])
        last = truncated[-1]
        assert last.trade_date == _day(cut)
        assert last.to_dict() == full[_day(cut)].to_dict()


# ---------------------------------------------------------------------------
# 事实走法与回放
# ---------------------------------------------------------------------------


def test_forward_facts_use_entry_days_and_compound_index_return():
    rows = _scenario()
    for r in rows:
        r["sh_index_pct_chg"] = 1.0  # 每日 +1%
    series = mer.compute_regime_series(rows)
    facts = mer.forward_facts_by_regime(series, rows)
    entries = {regime: f["entries"] for regime, f in facts.items()}
    assert sum(entries.values()) == 3
    for f in facts.values():
        five = f["horizons"]["5"]
        if five is not None:
            assert five["median_pct"] == pytest.approx((1.01 ** 5 - 1) * 100, abs=0.01)
            assert five["positive"] == five["n"]
    # before_index 排除今日自己的切换
    last_switch = max(i for i, rd in enumerate(series) if rd.switched)
    before = mer.forward_facts_by_regime(series, rows, before_index=last_switch)
    assert sum(f["entries"] for f in before.values()) == 2


def test_replay_reports_switches_and_confusion_against_labels():
    rows = _scenario()
    series = mer.compute_regime_series(rows)
    labels = {rd.trade_date: rd.raw_regime for rd in series if rd.raw_regime}
    result = mer.replay(series, labels, since=_day(0))
    assert result["switches"] == 3
    assert result["windows"] == sum(1 for rd in series if rd.regime)
    cmp = result["cluster_comparison"]
    assert cmp["agreement_raw"] == 1.0
    assert cmp["paired_windows"] == result["windows"]
    assert sum(sum(row.values()) for row in cmp["confusion_cluster_rows_rule_cols"].values()) == result["windows"]
    assert "cluster_comparison" not in mer.replay(series, None)


# ---------------------------------------------------------------------------
# 取数装配：合成库 → 状态；缺表 / 样本不足 fail closed
# ---------------------------------------------------------------------------


def _make_db(path: Path, rows: list[dict], *, with_aux: bool = True) -> None:
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_market_daily (trade_date date, total_amount double, advancers integer, "
        "limit_up integer, limit_down integer, sh_deviation_pct double, sh_index_pct_chg double)"
    )
    if with_aux:
        con.execute("create table fact_limit_advance_daily (trade_date date, stock_ts_code varchar, boards integer)")
        con.execute("create table fact_sector_daily (trade_date date, sector_name varchar, pct_chg double, diff_ratio double, amount double)")
        con.execute("create table fact_theme_limit_heat_daily (trade_date date, sector_name varchar, market_share double)")
        con.execute("create table fact_stock_high_daily (trade_date date, stock_ts_code varchar)")
    for v in rows:
        con.execute(
            "insert into fact_market_daily values (?, ?, ?, ?, ?, ?, ?)",
            [v["trade_date"], v["total_amount"], v["advancers"], v["limit_up"], v["limit_down"], v["sh_deviation_pct"], v["sh_index_pct_chg"]],
        )
        if not with_aux:
            continue
        con.execute("insert into fact_limit_advance_daily values (?, 's1', ?)", [v["trade_date"], int(v["max_boards"])])
        for k in range(int(v["double_red_theme_count"])):
            con.execute("insert into fact_sector_daily values (?, ?, 2.5, 15.0, 900.0)", [v["trade_date"], f"题材{k}"])
        con.execute("insert into fact_theme_limit_heat_daily values (?, '题材0', ?)", [v["trade_date"], v["top1_theme_share"]])
        for k in range(int(v["new_high_count"] // 100)):
            con.execute("insert into fact_stock_high_daily values (?, ?)", [v["trade_date"], f"h{k}"])
    con.close()


def test_load_regime_state_from_synthetic_db_and_as_of():
    rows = _scenario()
    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "t.duckdb"
        _make_db(db, rows)
        con = duckdb.connect(str(db), read_only=True)
        try:
            latest = mer.load_regime_state(con)
            cut = mer.load_regime_state(con, as_of=_day(78))
            short = mer.load_regime_state(con, as_of=_day(30))
        finally:
            con.close()
    assert latest.available and latest.today is not None
    assert latest.today.trade_date == _day(99)
    assert latest.today.regime == "主线引领"
    assert latest.run_length >= 1
    assert cut.available and cut.today.trade_date == _day(78) and cut.today.regime == "巨量轮动"
    assert not short.available and "MIN_HISTORY" in (short.reason or "")
    payload = latest.to_dict()
    assert payload["parameters"]["debounce_days"] == mer.DEBOUNCE_DAYS
    assert set(payload["today"]["thresholds"]) == set(mer.THRESHOLD_QUANTILES)


def test_missing_aux_table_fails_closed_instead_of_guessing():
    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "t.duckdb"
        _make_db(db, _scenario(), with_aux=False)
        con = duckdb.connect(str(db), read_only=True)
        try:
            state = mer.load_regime_state(con)
        finally:
            con.close()
    assert not state.available
    assert "缺维" in (state.reason or "")
    assert mer.one_line(state).startswith("赚钱效应状态：不可用")


def test_text_renderers_mark_switch_day_and_keep_facts_factual():
    rows = _scenario()
    series = mer.compute_regime_series(rows)
    switch_day = next(rd for rd in series if rd.switched)
    state_switch = mer.regime_state_from_vectors([r for r in rows if r["trade_date"] <= switch_day.trade_date], [])
    assert state_switch.available and state_switch.today.switched
    assert mer.switch_headline(state_switch).startswith("⚠ 赚钱效应状态切换：缩量普涨 → **巨量轮动**")
    rows_table = mer.axis_rows(state_switch.today)
    assert len(rows_table) == len(mer.THRESHOLD_QUANTILES)
    assert any("命中" == r[-1] for r in rows_table)
    text = mer.forward_facts_text("巨量轮动", state_switch.forward_facts)
    assert "此前没有进入" in text  # 第一次进入，没有历史可列
    quiet = mer.regime_state_from_vectors([r for r in rows if r["trade_date"] <= _day(66)], [])
    assert mer.switch_headline(quiet) is None
    assert mer.one_line(quiet).startswith("赚钱效应状态：**缩量普涨**")


def test_cli_json_outputs_today_and_replay(monkeypatch):
    from market_feature_store import cli

    rows = _scenario()
    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "t.duckdb"
        _make_db(db, rows)
        monkeypatch.setattr(cli, "connect", lambda read_only=False: duckdb.connect(str(db), read_only=True))
        out: list[str] = []
        monkeypatch.setattr("builtins.print", lambda *a, **k: out.append(" ".join(str(x) for x in a)))
        assert cli.main(["money-effect-regime", "--json"]) == 0
        today = json.loads(out[-1])
        assert today["available"] and today["today"]["regime"] == "主线引领"
        out.clear()
        labels_path = Path(tmp) / "labels.json"
        labels_path.write_text(json.dumps({rd.trade_date: rd.raw_regime for rd in mer.compute_regime_series(rows) if rd.raw_regime}), encoding="utf-8")
        assert cli.main(["money-effect-regime", "--json", "--replay-since", _day(0), "--cluster-labels", str(labels_path)]) == 0
        replay = json.loads(out[-1])
        assert replay["switches"] == 3
        assert replay["cluster_comparison"]["agreement_raw"] == 1.0
        assert replay["series"][-1]["trade_date"] == _day(99)

"""赚钱效应 regime（market_feature_store.money_effect_regime）的机制测试。

守五件事：
1. 四条决策表各能命中一簇，且阈值只有 THRESHOLDS / THRESHOLD_QUANTILES 各一份定义（别处不得抄数字）；
2. 去抖是因果的：新簇第 1 日不切、第 2 日切——把 DEBOUNCE_DAYS 改成 1 这里必须红（变异测试）；
3. 判定**不依赖样本分布**：同一个今日窗口，换一段历史进去，簇名不变（round 4 换成冻结阈值的核心性质，
   分位版做不到这条）；重校准是显式动作，`recalibration_report` 只报不改；
4. 漂移看得见：距校准日超过 RECALIBRATE_AFTER_WINDOWS 个窗口时 recalibration_due 置位并进措辞
   （把 due_after 改大到测不出这里必须红——变异靶二）；
5. 无前视：整段一次算完 == 逐日 as_of 截断各算一次。
簇标签（k-means）不进仓，所以这里没有「一致率」断言——那是实验目录与 registry decisions 的事。
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import numpy as np
import pytest

from market_feature_store import money_effect_regime as mer
from market_feature_store.market_regime_vectors import load_market_regime_vectors

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


def test_thresholds_are_the_only_numeric_definition():
    """阈值单一真本源：绝对值只在 THRESHOLDS、分位只在 THRESHOLD_QUANTILES；cli / reports 不得再写一份。"""
    keys = {"amount_huge", "amount_high", "new_high_low", "share_high", "boards_high"}
    assert set(mer.THRESHOLD_QUANTILES) == keys
    assert set(mer.THRESHOLDS) == keys
    for key, (axis, q) in mer.THRESHOLD_QUANTILES.items():
        assert axis in mer.AXES, key
        assert 0.0 < q < 1.0, key
    assert mer.THRESHOLDS["amount_huge"] > mer.THRESHOLDS["amount_high"], "决策表按序命中要求 ① 的量能门更高"
    for name in ("THRESHOLD_QUANTILES", "THRESHOLDS"):
        pattern = re.compile(rf"^{name}\s*(?::[^=]*)?=\s*\{{", re.MULTILINE)
        hits = [
            p.relative_to(ROOT).as_posix()
            for top in ("market_feature_store", "intelligence")
            for p in (ROOT / top).rglob("*.py")
            if "tests" not in p.parts and pattern.search(p.read_text(encoding="utf-8"))
        ]
        assert hits == ["market_feature_store/money_effect_regime.py"], (name, hits)


def test_production_constants_are_pinned_to_the_registry_ledger():
    """代码里的生效值必须与 registry decisions 里写的那份一致。

    选 (1)「绝对阈值 + 定期重校准」付的账就是「校准日与阈值要写进 decisions」；
    光靠人记必漂，这里让它变成 exit code：改了常数不改台账（或反过来）就红。
    上一条 deadline 测试用常数自己当参照系，测得出「> 而不是 >=」，测不出 250 被改成 249——
    这条补的就是那个洞：参照系在台账，不在被测物。
    """
    text = (ROOT / "market_feature_store" / "consumption_registry.yaml").read_text(encoding="utf-8")
    block = text.split("- key: money_effect_clustering", 1)[1].split("\n  - key: ", 1)[0]
    assert f"CALIBRATED_ON = {mer.CALIBRATED_ON}" in block, "校准日没写进 decisions"
    assert f"RECALIBRATE_AFTER_WINDOWS = {mer.RECALIBRATE_AFTER_WINDOWS} 个窗口" in block, "重校准周期没写进 decisions"
    for key, value in mer.THRESHOLDS.items():
        assert f"{key} {value:,.0f} ".replace(",", "") in block.replace(",", ""), (key, value)


def test_verdict_does_not_depend_on_the_sample_distribution():
    """round 4 的核心性质：同一个今日窗口，换一段历史进去，判定不变。

    分位版做不到这条（阈值由样本自己派生）——这条测试就是「换成冻结阈值」这个决定的靶子。
    """
    today = [_vec(i, total_amount=23000.0) for i in range(200, 205)]
    calm = [_vec(i, total_amount=12000.0) for i in range(200)] + today
    hot = [_vec(i, total_amount=31000.0) for i in range(200)] + today
    calm_last = mer.compute_regime_series(calm)[-1]
    hot_last = mer.compute_regime_series(hot)[-1]
    assert calm_last.trade_date == hot_last.trade_date
    assert calm_last.raw_regime == hot_last.raw_regime == "放量分化"
    assert calm_last.thresholds == hot_last.thresholds == mer.THRESHOLDS


def test_quantile_thresholds_are_calibration_only_and_refuse_short_samples():
    """校准函数还在（重校准要用），但生产路径不调用它；短样本拒绝出值。"""
    days = [_vec(i, total_amount=10000.0 + 100.0 * i) for i in range(80)]
    windows = mer.trailing_windows(days)
    proposed = mer.quantile_thresholds(windows, min_windows=10)
    assert proposed is not None
    sample = [w.means["total_amount"] for w in windows]
    assert proposed["amount_high"] == pytest.approx(float(np.quantile(sample, 0.59)))
    assert mer.quantile_thresholds(windows[:5], min_windows=10) is None
    # 生产路径读的是冻结表，不是这里算出来的值
    assert mer.compute_regime_series(days)[-1].thresholds == mer.THRESHOLDS


def test_recalibration_report_flags_due_and_only_reports():
    days = [_vec(i, total_amount=30000.0) for i in range(90)]
    windows = mer.trailing_windows(days)
    fresh = mer.recalibration_report(windows, calibrated_on="2099-01-01")
    assert fresh["windows_since_calibration"] == 0 and fresh["due"] is False
    due = mer.recalibration_report(windows, calibrated_on="2024-01-01", due_after=10)
    assert due["windows_since_calibration"] == len(windows) and due["due"] is True
    # 只报不改：冻结表原封不动，建议值单独列出并带偏移
    assert mer.THRESHOLDS["amount_high"] == 22114.0
    assert due["proposed_thresholds"]["amount_high"]["frozen"] == 22114.0
    assert due["proposed_thresholds"]["amount_high"]["proposed"] == pytest.approx(30000.0)
    assert due["proposed_thresholds"]["amount_high"]["delta_pct"] > 0


def test_recalibration_due_reaches_the_wording():
    """变异靶：把 RECALIBRATE_AFTER_WINDOWS 改大到测不出（或删掉 recalibration_note 的调用），
    这条必须红——到期提示必须走到用户眼前的那行字，不能只躺在字段里。"""
    days = [_vec(i) for i in range(40)]
    due_day = mer.compute_regime_series(days, calibrated_on="2024-01-01", due_after=5)[-1]
    assert due_day.recalibration_due is True
    assert "重校准" in mer.recalibration_note(due_day)
    assert mer.recalibration_note(replace(due_day, recalibration_due=False)) == ""
    # 生产默认（校准日 2026-09-05）在这段 2025 年样本上不该报到期，也不该出现在措辞里
    state = mer.regime_state_from_vectors(days, [])
    assert state.available and state.today is not None
    assert state.today.recalibration_due is False
    assert "重校准" not in mer.one_line(state)


def test_production_recalibration_deadline_is_exactly_at_the_constant():
    """钉生产常数本身的边界：第 RECALIBRATE_AFTER_WINDOWS 个窗口不报，第 +1 个报。

    变异靶：把 RECALIBRATE_AFTER_WINDOWS 调大或调小，这条必须红。
    上一条测试显式传了 due_after，**测不到生产常数**——那种写法能让常数改成 10 亿还全绿。
    """
    after = date.fromisoformat(mer.CALIBRATED_ON) + timedelta(days=1)

    def series_with(n_windows: int):
        n_days = n_windows + mer.WINDOW - 1
        days = [
            {**_vec(0), "trade_date": (after + timedelta(days=i)).isoformat()}
            for i in range(n_days)
        ]
        return mer.compute_regime_series(days)

    at_limit = series_with(mer.RECALIBRATE_AFTER_WINDOWS)[-1]
    assert at_limit.windows_since_calibration == mer.RECALIBRATE_AFTER_WINDOWS
    assert at_limit.recalibration_due is False, "恰好到线不该报到期"
    over = series_with(mer.RECALIBRATE_AFTER_WINDOWS + 1)[-1]
    assert over.windows_since_calibration == mer.RECALIBRATE_AFTER_WINDOWS + 1
    assert over.recalibration_due is True, "超线一个窗口必须报到期"


# ---------------------------------------------------------------------------
# 决策表与四簇
# ---------------------------------------------------------------------------


def test_decision_table_hits_each_regime_in_order():
    thr = mer.THRESHOLDS
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
    # 冻结阈值下没有「样本不足」的前段：第一个满 WINDOW 的窗口就判得出（分位版这里是 None）
    assert series[0].trade_date == _day(mer.WINDOW - 1)
    assert series[0].regime == "缩量普涨"
    assert all(rd.regime is not None for rd in series)


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
    switches = [rd.trade_date for rd in series if rd.switched]
    assert len(switches) == 3, switches
    # 每个提交的切换日，raw 必须已连续 DEBOUNCE_DAYS 个窗口是新簇，且前一日尚未切
    dates = [rd.trade_date for rd in series]
    for day in switches:
        i = dates.index(day)
        assert series[i].raw_regime == series[i].regime
        assert all(series[i - k].raw_regime == series[i].regime for k in range(mer.DEBOUNCE_DAYS))
        assert series[i - 1].regime == series[i].prev_regime, "新簇第 1 日不得切换"
    # 窗口混合期的单窗口毛刺（03-19 放量分化）必须被去抖吃掉——DEBOUNCE_DAYS=1 时它会变成第 4 次切换
    blip = next(rd for rd in series if rd.raw_regime == "放量分化" and rd.regime == "缩量普涨")
    assert blip.switched is False
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
    """建合成库。**新高家数按真实量纲逐行写**（600 家就写 600 行）——不是 //100 缩水版：
    规则阈值是绝对值（新高 ≤ 464 家），夹具缩了量纲就会让这条判据恒真，
    `test_db_fixture_reproduces_vector_magnitudes` 守着这件事。"""
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_market_daily (trade_date date, total_amount double, advancers integer, "
        "limit_up integer, limit_down integer, sh_deviation_pct double, sh_index_pct_chg double)"
    )
    con.executemany(
        "insert into fact_market_daily values (?, ?, ?, ?, ?, ?, ?)",
        [[v["trade_date"], v["total_amount"], v["advancers"], v["limit_up"], v["limit_down"],
          v["sh_deviation_pct"], v["sh_index_pct_chg"]] for v in rows],
    )
    if not with_aux:
        con.close()
        return
    con.execute("create table fact_limit_advance_daily (trade_date date, stock_ts_code varchar, boards integer)")
    con.execute("create table fact_sector_daily (trade_date date, sector_name varchar, pct_chg double, diff_ratio double, amount double)")
    con.execute("create table fact_theme_limit_heat_daily (trade_date date, sector_name varchar, market_share double)")
    con.execute("create table fact_stock_high_daily (trade_date date, stock_ts_code varchar)")
    con.executemany(
        "insert into fact_limit_advance_daily values (?, 's1', ?)",
        [[v["trade_date"], int(v["max_boards"])] for v in rows],
    )
    con.executemany(
        "insert into fact_sector_daily values (?, ?, 2.5, 15.0, 900.0)",
        [[v["trade_date"], f"题材{k}"] for v in rows for k in range(int(v["double_red_theme_count"]))],
    )
    con.executemany(
        "insert into fact_theme_limit_heat_daily values (?, '题材0', ?)",
        [[v["trade_date"], v["top1_theme_share"]] for v in rows],
    )
    con.executemany(
        "insert into fact_stock_high_daily values (?, ?)",
        [[v["trade_date"], f"h{k}"] for v in rows for k in range(int(v["new_high_count"]))],
    )
    con.close()


def test_db_fixture_reproduces_vector_magnitudes():
    """夹具保真：从合成库读回的向量必须与内存向量逐字段等值。

    绝对阈值把量纲变成了判据的一部分——夹具缩了量纲，守门断言就会打在一个
    「每天只有 6 家新高」的假市场上，而且照样发绿。
    """
    rows = _scenario()
    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "t.duckdb"
        _make_db(db, rows)
        con = duckdb.connect(str(db), read_only=True)
        try:
            vectors, missing = load_market_regime_vectors(con)
        finally:
            con.close()
    assert missing == []
    assert len(vectors) == len(rows)
    for got, want in zip(vectors, rows):
        for field in mer.AXES:
            assert float(got[field]) == pytest.approx(float(want[field])), (got["trade_date"], field)
    assert mer.compute_regime_series(vectors) == mer.compute_regime_series(rows)


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
    # 冻结阈值不需要历史样本：30 天的短库照样判得出（分位版这里报 MIN_HISTORY 不足）
    assert short.available and short.today is not None
    assert short.today.trade_date == _day(30) and short.today.regime == "缩量普涨"
    payload = latest.to_dict()
    assert payload["parameters"]["debounce_days"] == mer.DEBOUNCE_DAYS
    assert payload["parameters"]["calibrated_on"] == mer.CALIBRATED_ON
    assert payload["parameters"]["thresholds"] == mer.THRESHOLDS
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

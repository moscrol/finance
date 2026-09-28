"""事件定价第一刀（设计稿 §8 验收）：分类器正反例 / 反应日映射 / latest_known 形状 / 前视 / 与 outcomes 对账 /
四态读数与禁词 / 横截面无个股 / 来源等级与冲突 / 版本号 / 重建幂等。

手工小库：70 个工作日（2026-03-02 起，抽掉 2026-04-20 当「假日」），板块 S1 是阳性对照——锚点日 D0 跌 4%，
D0+1..D0+5 每日 +3%，其余日 0；事后 5 日必须等于 1.03^5-1 且不含 D0（含了就是前视）。
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from intelligence.services.event_pricing import event_calendar as cal_mod
from intelligence.services.event_pricing.anchors import build_anchors
from intelligence.services.event_pricing.classify import EditorialRow, classify_row, parse_period
from intelligence.services.event_pricing.event_calendar import build_calendar, latest_known, map_reaction_day
from intelligence.services.event_pricing.params import DEFAULT_PARAMS_PATH, load_params
from intelligence.services.event_pricing.reaction import SHAPES, build_reaction
from intelligence.services.event_pricing.readouts import (
    STOCK_CODE_RE,
    assert_no_forbidden_words,
    build_receipt,
    render_markdown,
    write_receipt,
)
from intelligence.services.event_pricing.schedule import derive_lpr_by_rule, load_schedule_files
from intelligence.services.event_pricing.store import table_hash
from intelligence.services.methodology_backtest.labels import build_labels
from intelligence.services.methodology_backtest.outcomes import build_outcomes
from intelligence.services.methodology_backtest.store import open_labels_db
from market_feature_store.db import init_db

HOLIDAY = date(2026, 4, 20)  # 抽掉的周一：LPR 20 日须顺延到 21 日


def _weekdays(n: int, start: date = date(2026, 3, 2)) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5 and d != HOLIDAY:
            out.append(d)
        d += timedelta(days=1)
    return out


DAYS = _weekdays(70)
D0 = date(2026, 4, 30)  # PMI 官方日 + FOMC 反应日（04-29 美国周三 → 04-30）
assert D0 in DAYS
D0_IDX = DAYS.index(D0)
S1, S2, S3 = "S1.TI", "S2.TI", "S3.TI"
SMALL = [f"T{j:02d}.TI" for j in range(10)]


def _s1_pct(i: int) -> float:
    if i == D0_IDX:
        return -4.0
    if D0_IDX < i <= D0_IDX + 5:
        return 3.0
    return 0.0


def _build_mini_db(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        init_db(con)
        for i, d in enumerate(DAYS):
            con.execute(
                """
                INSERT INTO fact_market_daily (trade_date, market_stage, total_amount, amount_vs_yesterday_pct, advancers,
                                               limit_up, sh_index_pct_chg, amount_ma20)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                [d, "主升阶段" if i % 2 == 0 else "下跌阶段", 10000.0 + i, None if i == 0 else 5.0, 2000, 50 + (i % 7), 0.1, 10000.0],
            )
        rows = []
        for i, d in enumerate(DAYS):
            rows.append((d, "legacy", S1, "板块一", _s1_pct(i), 1000.0 + i, 15.0, None))
            rows.append((d, "legacy", S2, "板块二", 0.5 if i % 3 else -0.5, 800.0, -5.0, None))
            rows.append((d, "legacy", S3, "板块三", -0.2, 600.0, -5.0, None))
            for j, code in enumerate(SMALL):
                rows.append((d, "legacy", code, f"小板块{j}", ((i + j) % 5 - 2) * 0.3, 100.0 + j, -5.0, None))
        con.executemany(
            "INSERT INTO fact_sector_daily_generation (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount, diff_ratio, multi_period_resonance) VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        for i, d in enumerate(DAYS):
            con.execute(
                "INSERT INTO fact_theme_limit_heat_daily (trade_date, sector_ts_code, sector_name, dimension, scope, data_stage, is_realtime, rank, limit_up_count) VALUES (?,?,?,?,?,?,?,?,?)",
                [d, S1, "板块一", "sector", "all", "final", False, 1, 3 + (i % 4)],
            )
            for k, name in enumerate(("电子", "医药生物", "银行")):
                con.execute(
                    "INSERT INTO fact_sw_l1_daily (trade_date, sw_l1_code, sw_l1, pct_chg) VALUES (?,?,?,?)",
                    [d, f"SW{k}", name, (k - 1) * 0.4],
                )
        events = [
            # (event_date, id, title, event_type, sectors, is_future)
            (date(2026, 4, 21), "e-lpr", "中国LPR利率数据发布（2026年4月）", "数据发布", None, False),
            (date(2026, 4, 30), "e-pmi-1", "4月PMI数据发布", "数据发布", None, False),
            (date(2026, 4, 30), "e-pmi-2", "4月PMI", None, None, False),
            (date(2026, 5, 4), "e-caixin", "4月财新制造业PMI数据发布", "数据发布", None, False),
            (date(2026, 4, 9), "e-cpi-early", "3月CPI数据发布", "数据发布", None, False),
            (date(2026, 4, 20), "e-hkcpi", "中国香港公布3月综合CPI当月同比数据", "数据发布", None, False),
            # 编辑日历把 FOMC 记在北京日期（决议次日）：04-30 ↔ 官方美国日期 04-29，反应日同为 04-30 → both
            (date(2026, 4, 30), "e-fomc", "美联储议息会议", "会议", None, False),
            (date(2026, 4, 8), "e-fomc-minutes", "美联储发布3月FOMC会议纪要", "数据发布", None, False),
            (date(2026, 4, 10), "e-credit", "央行公布3月金融数据：社融与M2", "数据发布", None, False),
            # 同所属期两天不同日期、无官方仲裁 → 双双 editorial_ambiguous，不入锚点
            (date(2026, 5, 12), "e-credit-dup1", "中国4月M1货币供应量同比数据发布", "数据发布", None, False),
            (date(2026, 5, 14), "e-credit-dup2", "中国4月M0货币供应量数据发布", "数据发布", None, False),
            (date(2026, 5, 13), "e-credit-macau", "澳门M2货币供应数据发布（2026年04月）", "数据发布", None, False),
            (
                date(2026, 4, 15),
                "e-policy",
                "《某行业管理办法》正式实施",
                "政策",
                json.dumps([{"ts_code": S1, "name": "板块一", "type": "I"}, {"ts_code": "ZZZ.FP", "name": "未映射", "type": "N"}]),
                False,
            ),
            (date(2026, 5, 6), "e-industry", "某行业大会召开", "行业事件", json.dumps([{"ts_code": S2, "name": "板块二", "type": "I"}]), False),
            (date(2026, 5, 7), "e-policy-nosector", "另一政策发布", "政策", "[]", False),
            (date(2026, 4, 14), "e-conf", "某公司新品发布会", "会议", None, False),
            (date(2026, 9, 9), "e-future-cpi", "8月CPI数据发布", "数据发布", None, True),
        ]
        con.executemany(
            "INSERT INTO fact_event_daily (event_date, event_id, title, content, importance, event_type, source_types, sectors, is_future, source, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(d, eid, title, None, 2, et, None, sec, fut, "test", None) for d, eid, title, et, sec, fut in events],
        )
    finally:
        con.close()


def _write_schedule(dir_: Path) -> None:
    doc = {
        "schema_version": 1,
        "year": 2026,
        "entered_at": "2026-09-07",
        "sources": [
            {"id": "nbs_2026", "event_classes": ["cn_pmi_official", "cn_cpi_ppi"], "url": "https://www.stats.gov.cn/sj/fbrc/bnxxfb/", "schedule_published_at": "2025-12-31", "fetched_at": "2026-09-07"},
            {"id": "fomc_2026", "event_classes": ["fomc_decision"], "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", "schedule_published_at": "2025-12-31", "fetched_at": "2026-09-07"},
            {"id": "nifc_lpr_api", "event_classes": ["cn_lpr"], "url": "https://www.chinamoney.com.cn/chinese/bklpr/", "schedule_published_at": "2019-08-17", "fetched_at": "2026-09-07"},
        ],
        "entries": [
            {"event_class": "cn_cpi_ppi", "indicator": "cn_cpi", "event_date": "2026-04-10", "period": "2026-03", "time_local": "09:30", "tz": "Asia/Shanghai", "source_id": "nbs_2026"},
            {"event_class": "cn_cpi_ppi", "indicator": "cn_ppi", "event_date": "2026-04-10", "period": "2026-03", "time_local": "09:30", "tz": "Asia/Shanghai", "source_id": "nbs_2026"},
            {"event_class": "cn_cpi_ppi", "indicator": "cn_cpi", "event_date": "2026-05-11", "period": "2026-04", "time_local": "09:30", "tz": "Asia/Shanghai", "source_id": "nbs_2026"},
            {"event_class": "cn_cpi_ppi", "indicator": "cn_ppi", "event_date": "2026-05-11", "period": "2026-04", "time_local": "09:30", "tz": "Asia/Shanghai", "source_id": "nbs_2026"},
            {"event_class": "cn_pmi_official", "indicator": "cn_pmi_official", "event_date": "2026-04-30", "period": "2026-04", "time_local": "09:30", "tz": "Asia/Shanghai", "source_id": "nbs_2026"},
            {"event_class": "cn_pmi_official", "indicator": "cn_pmi_official", "event_date": "2026-05-31", "period": "2026-05", "time_local": "09:30", "tz": "Asia/Shanghai", "source_id": "nbs_2026"},
            {"event_class": "fomc_decision", "indicator": "fomc_decision", "event_date": "2026-04-29", "period": "2026-04-29", "time_local": "14:00", "tz": "America/New_York", "source_id": "fomc_2026"},
            {"event_class": "fomc_decision", "indicator": "fomc_decision", "event_date": "2026-06-17", "period": "2026-06-17", "time_local": "14:00", "tz": "America/New_York", "source_id": "fomc_2026"},
            {"event_class": "cn_lpr", "indicator": "cn_lpr", "event_date": "2026-05-20", "period": "2026-05", "time_local": "09:00", "tz": "Asia/Shanghai", "source_id": "nifc_lpr_api"},
        ],
    }
    (dir_ / "official_release_schedule.2026.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def _write_params(path: Path, **overrides) -> Path:
    doc = json.loads(DEFAULT_PARAMS_PATH.read_text(encoding="utf-8"))
    doc.update({"crowding_lookback_days": 20, "crowding_min_obs": 10, "amount_ratio_lookback_days": 10})
    doc.update(overrides)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("event_pricing")
    db = root / "mini.duckdb"
    labels = root / "history_labels.duckdb"
    sched = root / "calendars"
    sched.mkdir()
    _write_schedule(sched)
    params_path = _write_params(root / "params.json")
    _build_mini_db(db)
    build_labels(db, labels)
    build_outcomes(db, labels)
    params = load_params(params_path, schedule_dir=sched)
    cal = build_calendar(db, labels, params=params)
    anc = build_anchors(db, labels, params=params)
    rea = build_reaction(db, labels, params=params)
    return {"db": db, "labels": labels, "params": params, "params_path": params_path, "sched": sched, "cal": cal, "anc": anc, "rea": rea, "root": root}


def _q(labels: Path, sql: str, params: list | None = None):
    con = open_labels_db(labels, read_only=True)
    try:
        return con.execute(sql, params or []).fetchall()
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# 分类器（不触库）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "title, event_type, expected",
    [
        ("4月PMI数据发布", "数据发布", "cn_pmi_official"),
        ("4月财新制造业PMI数据发布", "数据发布", None),
        ("3月CPI数据发布", "数据发布", "cn_cpi_ppi"),
        ("中国香港公布3月综合CPI当月同比数据", "数据发布", None),
        ("美联储公布4月利率决议", "会议", "fomc_decision"),
        ("美联储发布3月FOMC会议纪要", "数据发布", None),
        ("中国LPR利率数据发布（2026年4月）", "数据发布", "cn_lpr"),
        ("央行公布3月金融数据：社融与M2", "数据发布", "cn_credit_data"),
        ("某公司新品发布会", "会议", None),
    ],
)
def test_classifier_positive_and_negative_examples(title, event_type, expected):
    params = load_params()
    events, gap = classify_row(EditorialRow("x", "2026-04-30", title, event_type, None), params)
    got = events[0].event_class if events else None
    assert got == expected, (title, got, gap)
    if expected is None:
        assert gap is not None and gap.reason == "unparsed"


def test_classifier_sector_class_requires_sectors():
    params = load_params()
    events, gap = classify_row(EditorialRow("p", "2026-05-07", "另一政策发布", "政策", "[]"), params)
    assert events == [] and gap.reason == "sector_class_without_sectors"
    events, gap = classify_row(
        EditorialRow("p2", "2026-05-07", "政策", "政策", json.dumps([{"ts_code": "S1.TI", "name": "板块一"}])), params
    )
    assert gap is None and events[0].event_class == "policy_release" and events[0].sector_codes == ("S1.TI",)


def test_period_parsing_wraps_year():
    params = load_params()
    spec = params.classes["cn_cpi_ppi"]
    assert parse_period("12月CPI数据发布", "2026-01-09", spec) == "2025-12"
    assert parse_period("3月CPI数据发布", "2026-04-10", spec) == "2026-03"
    assert parse_period("CPI数据发布", "2026-04-10", spec) is None
    assert parse_period("中国LPR利率数据发布（2026年8月）", "2026-08-20", params.classes["cn_lpr"]) == "2026-08"


def test_cpi_ppi_indicators_split_by_title():
    params = load_params()
    events, _ = classify_row(EditorialRow("a", "2026-04-10", "3月CPI数据发布", "数据发布", None), params)
    assert [e.indicator for e in events] == ["cn_cpi"]
    events, _ = classify_row(EditorialRow("b", "2026-04-10", "3月CPI、PPI数据发布", "数据发布", None), params)
    assert sorted(e.indicator for e in events) == ["cn_cpi", "cn_ppi"]


# --------------------------------------------------------------------------- #
# 反应日 / 官方日程 / LPR 规则
# --------------------------------------------------------------------------- #
def test_reaction_day_rules():
    tds = DAYS
    assert map_reaction_day(date(2026, 4, 29), "next_trading_day_after_us_date", tds) == date(2026, 4, 30)
    assert map_reaction_day(date(2026, 4, 10), "next_trading_day", tds) == date(2026, 4, 13)  # 周五盘后 → 周一
    assert map_reaction_day(date(2026, 5, 31), "same_day_or_next", tds) == date(2026, 6, 1)  # 周日 → 周一
    assert map_reaction_day(HOLIDAY, "same_day_or_next", tds) == date(2026, 4, 21)  # 假日顺延
    assert map_reaction_day(date(2027, 1, 1), "same_day_or_next", tds) is None
    with pytest.raises(ValueError):
        map_reaction_day(date(2026, 4, 1), "made_up", tds)


def test_lpr_rule_derivation_skips_official_months_and_shifts_holiday(built):
    params = built["params"]
    entries, _ = load_schedule_files(params)
    derived = derive_lpr_by_rule(params, DAYS, entries)
    months = {e.period for e in derived}
    assert "2026-05" not in months  # 官方已有
    by_month = {e.period: e.event_date for e in derived}
    assert by_month["2026-04"] == "2026-04-21"  # 20 日是假日 → 21
    assert by_month["2026-03"] == "2026-03-20"
    in_range = [e for e in derived if e.source_grade == "rule_derived"]
    future = [e for e in derived if e.source_grade == "rule_derived_future"]
    # 日历到 2026-06-08 前后：06 月的 20 日已超日历 → future；再加 07 / 08 / 09 三个月，只按周末顺延
    assert in_range and {e.period for e in future} == {"2026-06", "2026-07", "2026-08", "2026-09"}
    assert by_month["2026-07"] == "2026-07-20" and by_month["2026-09"] == "2026-09-21"  # 09-20 是周日


def test_official_schedule_files_in_repo_are_loadable_and_weekday_consistent():
    params = load_params()
    entries, meta = load_schedule_files(params)
    assert len(meta) == 2 and {m["year"] for m in meta} == {2025, 2026}
    assert all(m["skipped_classes"] == [] for m in meta)
    by_class = {}
    for e in entries:
        by_class[e.event_class] = by_class.get(e.event_class, 0) + 1
    assert by_class["fomc_decision"] == 16 and by_class["cn_pmi_official"] == 24 and by_class["cn_cpi_ppi"] == 48
    # 2026-07-09（周四）发 6 月 CPI；2026-09-09 发 8 月 CPI —— E-007 P3 / P4 的真值
    cpi = {e.event_date: e.period for e in entries if e.indicator == "cn_cpi"}
    assert cpi["2026-07-09"] == "2026-06" and cpi["2026-09-09"] == "2026-08" and cpi["2026-06-10"] == "2026-05"
    assert all(e.schedule_published_at for e in entries)


# --------------------------------------------------------------------------- #
# 日历构建
# --------------------------------------------------------------------------- #
def test_calendar_merge_grades_and_conflict(built):
    labels = built["labels"]
    rows = _q(labels, "SELECT event_class, indicator, event_date, reaction_day, source_grade, editorial_date, period FROM history_event_calendar ORDER BY 1,2,3")
    by = {(r[0], r[1], str(r[2])): r for r in rows}
    # 官方 + 编辑同反应日 → both（PMI 04-30，两条编辑行合成）
    assert by[("cn_pmi_official", "cn_pmi_official", "2026-04-30")][4] == "both"
    # 编辑 04-09 vs 官方 04-10 同所属期 → conflict，官方为准，记 editorial_date
    r = by[("cn_cpi_ppi", "cn_cpi", "2026-04-10")]
    assert r[4] == "conflict" and str(r[5]) == "2026-04-09" and r[6] == "2026-03"
    assert ("cn_cpi_ppi", "cn_cpi", "2026-04-09") not in by
    # FOMC 官方 04-29（美国日期）→ 反应日 04-30；编辑北京日期 04-30 按同日规则也落 04-30 → both
    fomc = by[("fomc_decision", "fomc_decision", "2026-04-29")]
    assert str(fomc[3]) == "2026-04-30" and fomc[4] == "both" and str(fomc[5]) == "2026-04-30"
    assert ("fomc_decision", "fomc_decision", "2026-04-30") not in by
    # 4 月金融数据两条编辑行日期不同、无官方 → editorial_ambiguous；澳门行被排除词挡在 unparsed
    dups = [r for r in rows if r[0] == "cn_credit_data" and r[6] == "2026-04"]
    assert len(dups) == 2 and all(r[4] == "editorial_ambiguous" for r in dups)
    assert not any("澳门" in (r[0] or "") for r in _q(labels, "SELECT title_sample FROM history_event_calendar WHERE event_class='cn_credit_data'"))
    # 金融数据 周五 → 周一
    assert str(by[("cn_credit_data", "cn_credit_data", "2026-04-10")][3]) == "2026-04-13"
    assert by[("cn_credit_data", "cn_credit_data", "2026-04-10")][4] == "editorial"
    # LPR：04 月规则派生且编辑同日 → 仍 rule_derived；05 月官方
    assert by[("cn_lpr", "cn_lpr", "2026-04-21")][4] == "rule_derived"
    assert by[("cn_lpr", "cn_lpr", "2026-05-20")][4] == "official"
    # 未来事件（超日历）reaction_day 为 NULL 且进缺口
    fut = by[("cn_cpi_ppi", "cn_cpi", "2026-09-09")]
    assert fut[3] is None
    gaps = dict((r[0], r[1]) for r in _q(labels, "SELECT reason, COUNT(*) FROM history_event_gaps GROUP BY 1"))
    assert gaps.get("beyond_calendar", 0) >= 1
    assert gaps.get("unparsed", 0) >= 4  # 财新 / 香港 / 纪要 / 发布会
    assert gaps.get("sector_class_without_sectors", 0) == 1
    assert gaps.get("conflict_official_wins", 0) == 1
    assert gaps.get("unmapped_sector", 0) == 1
    assert gaps.get("duplicate_period_dates", 0) == 2
    # 小库里每个锚点实体当天都有价格行 → 该缺口为 0；真库里它是板块序列换宇宙的主要缺口
    assert gaps.get("no_price_row_on_reaction_day", 0) == 0
    unparsed = [r[0] for r in _q(labels, "SELECT detail FROM history_event_gaps WHERE reason = 'unparsed'")]
    assert any("财新" in d for d in unparsed) and any("香港" in d for d in unparsed) and any("纪要" in d for d in unparsed)


def test_latest_known_shapes_and_no_numbers(built):
    con = open_labels_db(built["labels"], read_only=True)
    try:
        r = latest_known(con, "cn_cpi", "2026-05-08")
        assert r["status"] == "released" and r["period"] == "2026-03" and r["release_date"] == "2026-04-10"
        assert r["next_release_date"] == "2026-05-11"
        r2 = latest_known(con, "cn_cpi", "2026-05-11")  # 09:30 发布，当日收盘即知
        assert r2["status"] == "released" and r2["period"] == "2026-04"
        r3 = latest_known(con, "cn_cpi", "2026-04-09")
        assert r3["status"] == "not_yet_released" and r3["next_release_date"] == "2026-04-10"
        # 收盘后发布的金融数据：事件日当天还不知道，次日才知道
        c1 = latest_known(con, "cn_credit_data", "2026-04-10")
        c2 = latest_known(con, "cn_credit_data", "2026-04-13")
        assert c1["status"] == "not_yet_released" and c2["status"] == "released"
        for out in (r, r2, r3, c1, c2):
            assert not any(k in ("value", "actual", "consensus") for k in out)
            assert all(not isinstance(v, (int, float)) or isinstance(v, bool) for v in out.values())
        assert latest_known(con, "nope", "2026-05-08")["status"] == "unknown_schedule"
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# 锚点与反应
# --------------------------------------------------------------------------- #
def test_anchors_two_layers_and_dedupe(built):
    labels = built["labels"]
    rows = _q(labels, "SELECT entity_type, entity_id, trade_date, label FROM history_event_anchors ORDER BY 3,4,1,2")
    market = [r for r in rows if r[0] == "market"]
    sector = [r for r in rows if r[0] == "sector"]
    # CPI 04-10 两指标同日 → 一条 market 锚点
    assert sum(1 for r in market if r[3] == "ev.cn_cpi_ppi" and str(r[2]) == "2026-04-10") == 1
    assert {r[3] for r in market} >= {"ev.cn_lpr", "ev.cn_pmi_official", "ev.cn_cpi_ppi", "ev.fomc_decision", "ev.cn_credit_data"}
    # editorial_ambiguous 的 4 月金融数据不成锚点；3 月那条唯一 → 成锚点
    credit_days = sorted(str(r[2]) for r in market if r[3] == "ev.cn_credit_data")
    assert credit_days == ["2026-04-13"]
    assert (("sector", S1, date(2026, 4, 15), "ev.policy_release") in [(r[0], r[1], r[2], r[3]) for r in sector])
    assert (("sector", S2, date(2026, 5, 6), "ev.industry_event") in [(r[0], r[1], r[2], r[3]) for r in sector])
    assert all(r[1] != "ZZZ.FP" for r in sector)


def test_positive_control_windows_exclude_d0_and_match_outcomes(built):
    labels = built["labels"]
    # S1 在 04-15（政策锚点）是 state_only、在 D0 没有板块级锚点；用 D0 的 market 锚点核市场层，用 policy 锚点核板块层公式
    rows = _q(
        labels,
        "SELECT pre_return_m, d0_return, fwd_return_5, excess_fwd_5, status, pre_window_semantics FROM history_event_reaction WHERE entity_type='market' AND event_class='cn_pmi_official' AND reaction_day = ?",
        [D0],
    )
    assert len(rows) == 1
    pre, d0, f5, ex5, status, sem = rows[0]
    assert status == "ok" and sem == "expectation"
    assert abs(d0 - 0.1) < 1e-9 and abs(f5 - ((1.001**5 - 1) * 100)) < 1e-6 and ex5 is None
    # 板块层公式：直接从特征池核阳性对照（S1 在 D0 的 fwd_5 = 1.03^5 - 1，pre_5 = 0，d0 = -4）
    out = _q(labels, "SELECT fwd_return FROM history_outcomes WHERE entity_type='sector' AND entity_id=? AND trade_date=? AND horizon=5", [S1, D0])
    assert abs(out[0][0] - ((1.03**5 - 1) * 100)) < 1e-6
    # 反应表里板块记录的 fwd_5 必须与 outcomes 同键行相等（对账）
    mism = _q(
        labels,
        """
        SELECT COUNT(*) FROM history_event_reaction r
        JOIN history_outcomes o ON o.entity_type = r.entity_type AND o.entity_id = r.entity_id AND o.trade_date = r.reaction_day AND o.horizon = 5
        WHERE r.entity_type = 'sector' AND r.fwd_return_5 IS NOT NULL AND ABS(r.fwd_return_5 - o.fwd_return) > 1e-9
        """,
    )
    assert mism[0][0] == 0
    pol = _q(labels, "SELECT pre_return_m, d0_return, fwd_return_5, excess_d0, pre_window_semantics, status FROM history_event_reaction WHERE entity_type='sector' AND entity_id=? AND event_class='policy_release'", [S1])
    assert len(pol) == 1 and pol[0][4] == "state_only" and pol[0][5] == "ok"
    assert abs(pol[0][3] - (0.0 - 0.1)) < 1e-9  # 04-15 S1 涨跌 0，市场 0.1 → 超额 -0.1


def test_lookahead_mutation_shifting_prices_changes_only_forward_side(built):
    """把 S1 的 pct_chg 整体后移一个交易日重建：D0 的 fwd_5 应少一个 +3%、多一个 D0 的 -4%；pre_5 仍为 0。"""
    root = built["root"]
    db2 = root / "shifted.duckdb"
    _build_mini_db(db2)
    con = duckdb.connect(str(db2))
    try:
        rows = con.execute("SELECT trade_date, pct_chg FROM fact_sector_daily_generation WHERE sector_ts_code = ? ORDER BY trade_date", [S1]).fetchall()
        shifted = [None] + [r[1] for r in rows[:-1]]
        for (d, _), v in zip(rows, shifted):
            con.execute("UPDATE fact_sector_daily_generation SET pct_chg = ? WHERE sector_ts_code = ? AND trade_date = ?", [v if v is not None else 0.0, S1, d])
    finally:
        con.close()
    labels2 = root / "labels_shifted.duckdb"
    build_labels(db2, labels2)
    build_outcomes(db2, labels2)
    params = built["params"]
    build_calendar(db2, labels2, params=params)
    build_anchors(db2, labels2, params=params)
    build_reaction(db2, labels2, params=params)
    orig = _q(built["labels"], "SELECT fwd_return FROM history_outcomes WHERE entity_type='sector' AND entity_id=? AND trade_date=? AND horizon=5", [S1, D0])[0][0]
    new = _q(labels2, "SELECT fwd_return FROM history_outcomes WHERE entity_type='sector' AND entity_id=? AND trade_date=? AND horizon=5", [S1, D0])[0][0]
    assert abs(orig - ((1.03**5 - 1) * 100)) < 1e-6
    assert abs(new - ((0.96 * 1.03**4 - 1) * 100)) < 1e-6  # 后移后 D0+1 变成 -4%
    assert new < orig


def test_shape_semantics_and_status(built):
    labels = built["labels"]
    rows = _q(labels, "SELECT event_class, pre_window_semantics, status, shape_tag, consensus_stage_gap, consensus_stage_dm1 FROM history_event_reaction")
    assert rows
    assert all(r[4] == "not_wired" and r[5] is None for r in rows)
    sem = {(r[0], r[1]) for r in rows}
    assert ("cn_credit_data", "state_only") in sem  # 非预期类只能是 state_only
    assert ("policy_release", "state_only") in sem
    assert ("cn_pmi_official", "expectation") in sem
    assert all(r[3] in (None, "pre_up_post_down", "pre_down_post_up", "continuation_up", "continuation_down", "flat", "mixed") for r in rows)
    ok = [r for r in rows if r[2] == "ok"]
    assert all(r[3] is not None for r in ok)
    # 日历末尾附近的锚点 → pending（06-17 FOMC 反应日 06-18 后不足 5 日）
    pend = _q(labels, "SELECT status FROM history_event_reaction WHERE event_class='fomc_decision' AND reaction_day = ?", [date(2026, 6, 18)])
    if pend:
        assert pend[0][0] in ("pending", "ok")


def test_cross_section_has_no_stock_codes(built):
    labels = built["labels"]
    rows = _q(labels, "SELECT entity_kind, entity_id, entity_name, metric FROM history_event_cross_section")
    assert rows
    assert {r[0] for r in rows} <= {"sector", "sw_l1"}
    for r in rows:
        assert not STOCK_CODE_RE.search(str(r[1]) or "") and not STOCK_CODE_RE.search(str(r[2]) or "")
    metrics = {r[3] for r in rows}
    assert "excess_d0_top" in metrics and "sw_l1_excess_fwd5" in metrics


# --------------------------------------------------------------------------- #
# 读数与收据
# --------------------------------------------------------------------------- #
def test_receipt_uses_stats_readout_and_has_no_forbidden_words(built):
    receipt = build_receipt(built["db"], built["labels"], params=built["params"])
    cls = receipt["classes"]
    assert "cn_pmi_official" in cls and cls["cn_pmi_official"]["entity_type"] == "market"
    exp = cls["cn_pmi_official"]["by_semantics"]["expectation"]
    rd = exp["shapes"]["flat"]
    for key in ("n", "k", "p", "p0", "wilson_lo", "wilson_hi", "first_half", "second_half", "verdict", "verdict_single", "bh"):
        assert key in rd
    assert rd["verdict"] == "insufficient_n" and rd["bh"]["family"] == list(SHAPES)  # 小库 N < 10
    assert all(b["verdict"] == "insufficient_n" for b in exp["by_stage"]["flat"]["buckets"])
    assert "state_only" not in cls["cn_pmi_official"]["by_semantics"] or cls["cn_pmi_official"]["by_semantics"]["state_only"]["n"] >= 1
    assert "expectation" not in cls["cn_credit_data"]["by_semantics"]
    md = render_markdown(receipt)
    assert_no_forbidden_words(md)
    with pytest.raises(AssertionError):
        assert_no_forbidden_words("历史上 70% 会上涨")
    with pytest.raises(AssertionError):
        assert_no_forbidden_words("这就是利好出尽")
    jp, mp = write_receipt(built["root"] / "receipts", receipt, date_str="2026-09-07")
    assert jp.exists() and mp.exists()
    lk = receipt["latest_known_at_calendar_end"]["by_indicator"]
    assert lk["cn_cpi"]["status"] in ("released", "not_yet_released")
    assert "cn_lpr" in lk


def test_source_grade_distribution_in_receipt(built):
    receipt = build_receipt(built["db"], built["labels"], params=built["params"])
    grades = receipt["calendar"]["by_source_grade"]
    assert grades.get("official", 0) >= 1 and grades.get("conflict", 0) == 1 and grades.get("both", 0) >= 1
    assert grades.get("rule_derived", 0) >= 1 and grades.get("editorial", 0) >= 1
    assert receipt["calendar"]["gaps"].get("calendar/conflict_official_wins") == 1


# --------------------------------------------------------------------------- #
# 幂等 / 版本 / 门禁
# --------------------------------------------------------------------------- #
def test_rebuild_is_idempotent(built):
    labels = built["labels"]
    con = open_labels_db(labels, read_only=True)
    try:
        before = {t: table_hash(con, t) for t in ("history_event_calendar", "history_event_anchors", "history_event_reaction", "history_event_cross_section")}
    finally:
        con.close()
    params = built["params"]
    build_calendar(built["db"], labels, params=params)
    build_anchors(built["db"], labels, params=params)
    build_reaction(built["db"], labels, params=params)
    con = open_labels_db(labels, read_only=True)
    try:
        after = {t: table_hash(con, t) for t in before}
    finally:
        con.close()
    assert before == after and all(v != "empty" for v in before.values())


def test_version_changes_with_params_and_schedule(built):
    p1 = built["params"]
    p2 = load_params(_write_params(built["root"] / "params2.json", crowding_lookback_days=20, crowding_min_obs=10, amount_ratio_lookback_days=10, pre_days=3), schedule_dir=built["sched"])
    assert p1.ev_version != p2.ev_version
    p3 = load_params(built["params_path"], schedule_dir=built["root"])  # 目录里没有日程文件 → 版本也不同
    assert p3.ev_version != p1.ev_version and p3.schedule_files == ()


def test_anchor_build_refuses_stale_calendar_version(built):
    p2 = load_params(_write_params(built["root"] / "params3.json", crowding_lookback_days=20, crowding_min_obs=10, amount_ratio_lookback_days=10, min_n=11), schedule_dir=built["sched"])
    with pytest.raises(RuntimeError):
        build_anchors(built["db"], built["labels"], params=p2)


def test_params_reject_unsupported_horizons(tmp_path):
    p = _write_params(tmp_path / "p.json", post_horizons=[3, 5, 20], shape_horizon=5)
    params = load_params(p)
    with pytest.raises(ValueError):
        from intelligence.services.event_pricing.reaction import build_feature_pool

        build_feature_pool(duckdb.connect(), params)


def test_code_does_not_read_docs_directory():
    pkg = Path(cal_mod.__file__).resolve().parent
    for f in pkg.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert "docs/learning" not in text.replace("docs/superpowers/specs", "") or "设计稿" in text
        assert 'open("docs' not in text and "Path(\"docs" not in text

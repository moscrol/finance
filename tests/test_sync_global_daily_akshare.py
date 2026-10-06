"""外盘 AKShare 写入链：只补表尾断档与复制行、口径对齐复盘会、无前视、只写克隆库（2026-10-06）。

全部用假取数器，不联网。日历：2026-09-07 是美国劳动节（美股休市、A 股与港股照常）。
"""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import duckdb
import pytest

from market_feature_store.db import init_db
from market_feature_store.sync import sync_global_daily_akshare as glob

D = date.fromisoformat
A_SHARE_DAYS = ["2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-07", "2026-09-08"]
US_SESSIONS = ["2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28", "2026-08-31", "2026-09-01",
               "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-08", "2026-09-09"]
HK_SESSIONS = ["2026-08-28", "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04",
               "2026-09-07", "2026-09-08"]


def _series(sessions: list[str], base: float) -> list[tuple[date, float]]:
    rows = [(D(day), base + index) for index, day in enumerate(sessions)]
    # 区间之后的会话给一个离谱的数：任何前视都会把它带进来。
    return [(day, 999.0 if day > D("2026-09-08") else close) for day, close in rows]


HISTORIES = {
    ("index_us_stock_sina", ".DJI"): _series(US_SESSIONS, 100.0),
    ("stock_hk_index_daily_sina", "HSI"): _series(HK_SESSIONS, 200.0),
    ("stock_us_daily", "AAPL"): _series(US_SESSIONS, 10.0),
    ("stock_us_daily", "MSFT"): _series(US_SESSIONS, 50.0),
}


def fake_fetch(function: str, symbol: str) -> list[tuple[date, float]]:
    # 本夹具没有拆股，前复权序列与裸价相同；显式提供，而不是靠异常回退。
    if function == glob.STOCK_QFQ_SOURCE:
        function = glob.STOCK_SOURCE
    if (function, symbol) not in HISTORIES:
        raise LookupError(symbol)
    return list(HISTORIES[(function, symbol)])


def _close(sessions: list[str], base: float, day: str) -> float:
    return base + sessions.index(day)


def _build(path: Path, *, stock_codes=("AAPL", "MSFT")) -> Path:
    with duckdb.connect(str(path)) as con:
        init_db(con)
        for day in A_SHARE_DAYS:
            con.execute("insert into fact_market_daily (trade_date) values (?)", [day])
        for code, base, sessions in (("DJI", 100.0, US_SESSIONS), ("HSI", 200.0, HK_SESSIONS)):
            group = "us" if code == "DJI" else "hk"
            for day in ("2026-08-31", "2026-09-01", "2026-09-02"):
                close = _close(sessions, base, day)
                prev = close - 1
                con.execute(
                    "insert into fact_global_index_daily values (?, ?, ?, ?, ?, ?, ?, 'final', 'fupanhui', now())",
                    [day, day, code, code, group, close, (close / prev - 1) * 100],
                )
        # 复制旧值：DJI 09-02 抄了 09-01 的数，会话日却写 09-02。
        con.execute("update fact_global_index_daily set close = 105.0, pct_chg = (105.0 / 104.0 - 1) * 100 "
                    "where code = 'DJI' and trade_date in ('2026-09-01', '2026-09-02')")
        # 一行与新源不同、但不是复制行：必须原样保留（不在断档 / 复制行范围内）。
        con.execute("update fact_global_index_daily set close = 201.5 where code = 'HSI' and trade_date = '2026-08-31'")
        for code in stock_codes:
            base = 10.0 if code == "AAPL" else 50.0
            for day in ("2026-08-31", "2026-09-01", "2026-09-02"):
                close = _close(US_SESSIONS, base, day)
                con.execute(
                    "insert into fact_global_stock_daily values (?, ?, ?, ?, 'en', 'NASDAQ', ?, ?, 1.0, 3.0e12, "
                    "'业务', '地位', 'fupanhui', now())",
                    [day, day, code, f"{code}中文", close, (close / (close - 1) - 1) * 100],
                )
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(path: Path, *, apply: bool, main: Path | None = None, **kwargs):
    return glob.run(path, start=D("2026-08-31"), end=D("2026-09-08"), apply=apply,
                    main_db_path=main or path.parent / "main.duckdb", fetch=fake_fetch,
                    complete_before=kwargs.pop("complete_before", D("2026-10-06")), **kwargs)


def test_dry_run_reports_targets_and_writes_nothing(tmp_path: Path) -> None:
    db = _build(tmp_path / "clone.duckdb")
    before = _sha(db)

    result = _run(db, apply=False)

    assert result["status"] == "ok" and result["applied"] is None
    index_report, stock_report = result["reports"]
    # 表尾之后 4 个 A 股日 × 2 个代码；外加 DJI 09-02 一行复制旧值。
    assert index_report["targets"] == {"gap": 8, "clone": 1, "frozen": 0}
    assert stock_report["targets"] == {"gap": 8, "clone": 0, "frozen": 0}
    assert _sha(db) == before


def test_apply_on_clone_follows_the_existing_calendar_contract(tmp_path: Path) -> None:
    db = _build(tmp_path / "clone.duckdb")

    result = _run(db, apply=True)

    assert result["status"] == "ok" and result["applied"] == {"index_rows": 9, "stock_rows": 8}
    with duckdb.connect(str(db), read_only=True) as con:
        rows = {
            (code, str(day)): (str(session), close, round(pct, 6))
            for code, day, session, close, pct in con.execute(
                "select code, trade_date, source_trade_date, close, pct_chg from fact_global_index_daily").fetchall()
        }
        stock = con.execute(
            "select close, pct_chg_5d, market_cap_usd, name_cn, business, source from fact_global_stock_daily "
            "where ts_code = 'AAPL' and trade_date = '2026-09-08'").fetchone()
    us = {day: _close(US_SESSIONS, 100.0, day) for day in US_SESSIONS[:-1]}
    # 复制行改回真实会话值。
    assert rows[("DJI", "2026-09-02")] == ("2026-09-02", us["2026-09-02"], round((us["2026-09-02"] / us["2026-09-01"] - 1) * 100, 6))
    # 美股劳动节休市：A 股 09-07 那行取 09-04 那一场、如实写会话日；港股当天照常。
    assert rows[("DJI", "2026-09-07")][0] == "2026-09-04"
    assert rows[("HSI", "2026-09-07")][0] == "2026-09-07"
    # 日历日 D 那一场，不是「隔夜」前一场。
    assert rows[("DJI", "2026-09-08")][:2] == ("2026-09-08", us["2026-09-08"])
    # 不在断档 / 复制行范围内的已有行原样保留。
    assert rows[("HSI", "2026-08-31")][1] == 201.5
    # 美股：5 日涨跌自算、市值留空、名称与业务沿用、来源换成 AKShare。
    close = _close(US_SESSIONS, 10.0, "2026-09-08")
    five_back = _close(US_SESSIONS, 10.0, US_SESSIONS[US_SESSIONS.index("2026-09-08") - 5])
    assert stock[0] == close and stock[1] == pytest.approx((close / five_back - 1) * 100)
    assert stock[2] is None and stock[3] == "AAPL中文" and stock[4] == "业务"
    assert stock[5] == "akshare:sina/stock_us_daily"


def test_never_reads_a_session_after_the_row_date(tmp_path: Path) -> None:
    # 截止日放得很远，只剩「不晚于行日期」这一道约束在起作用。
    db = _build(tmp_path / "clone.duckdb")

    _run(db, apply=True, complete_before=D("2026-12-31"))

    with duckdb.connect(str(db), read_only=True) as con:
        closes = [row[0] for row in con.execute("select close from fact_global_index_daily").fetchall()]
        late = con.execute("select count(*) from fact_global_index_daily where source_trade_date > trade_date").fetchone()[0]
    assert 999.0 not in closes and late == 0


def test_never_reads_an_unfinished_session(tmp_path: Path) -> None:
    db = _build(tmp_path / "clone.duckdb")

    _run(db, apply=True, complete_before=D("2026-09-08"))

    with duckdb.connect(str(db), read_only=True) as con:
        session = con.execute("select source_trade_date from fact_global_index_daily "
                              "where code = 'DJI' and trade_date = '2026-09-08'").fetchone()[0]
    # 09-08 那一场还没收完（complete_before），只能用此前最后一场 09-04。
    assert str(session) == "2026-09-04"


def test_validation_compares_against_the_independent_old_rows(tmp_path: Path) -> None:
    db = _build(tmp_path / "clone.duckdb")

    result = _run(db, apply=False)

    index_validation = result["reports"][0]["validation"]
    # 旧行 6 行，去掉 1 行复制行；HSI 08-31 被改成 201.5，是唯一不一致的一行。
    assert index_validation["checked"] == 5 and index_validation["exact"] == 4
    assert [item["day"] for item in index_validation["mismatches"]] == ["2026-08-31"]
    assert result["reports"][1]["validation"]["exact"] == result["reports"][1]["validation"]["checked"] == 6


def test_missing_tickers_over_the_threshold_stop_for_a_human(tmp_path: Path) -> None:
    db = _build(tmp_path / "clone.duckdb", stock_codes=("AAPL", "ZZZZ"))
    before = _sha(db)

    result = _run(db, apply=True)

    assert result["status"] == "needs_user" and result["applied"] is None
    assert any("缺口" in reason for reason in result["reasons"])
    assert any(item["code"] == "ZZZZ" for item in result["reports"][1]["skipped"])
    assert _sha(db) == before


def test_an_index_that_cannot_be_fetched_stops_the_run(tmp_path: Path, monkeypatch) -> None:
    db = _build(tmp_path / "clone.duckdb")
    monkeypatch.setitem(glob.INDEX_SOURCES, "HSI", ("stock_hk_index_daily_sina", "NOPE", "恒生指数", "hk"))

    result = _run(db, apply=True)

    assert result["status"] == "needs_user" and result["applied"] is None
    assert any("指数取不到" in reason for reason in result["reasons"])


def test_apply_refuses_the_main_database(tmp_path: Path) -> None:
    db = _build(tmp_path / "main.duckdb")
    before = _sha(db)

    result = _run(db, apply=True, main=db)

    assert result["status"] == "refused"
    assert _sha(db) == before


# ---- 七月初：两地休市、休市型复制、未标出的冻结、拆股 ----------------------------------------
# 07-01 香港回归纪念日（港股休市）；07-03 美国独立日补休（美股休市）。
JULY_A_SHARE = ["2026-06-30", "2026-07-01", "2026-07-02", "2026-07-03", "2026-07-06", "2026-07-07"]
JULY_US = ["2026-06-24", "2026-06-25", "2026-06-26", "2026-06-29", "2026-06-30", "2026-07-01",
           "2026-07-02", "2026-07-06", "2026-07-07"]
JULY_HK = ["2026-06-24", "2026-06-25", "2026-06-26", "2026-06-29", "2026-06-30", "2026-07-02",
           "2026-07-03", "2026-07-06", "2026-07-07"]
DJI_JULY = {day: 100.0 + index * 1.5 for index, day in enumerate(JULY_US)}
HSI_JULY = {day: 200.0 + index * 2.0 for index, day in enumerate(JULY_HK)}
# 07-06 一拆四：未复权收盘从 404 掉到 101，前复权序列连续。
SPLT_RAW = {"2026-06-24": 396.0, "2026-06-25": 397.0, "2026-06-26": 398.0, "2026-06-29": 399.0, "2026-06-30": 400.0,
            "2026-07-01": 402.0, "2026-07-02": 404.0, "2026-07-06": 101.5, "2026-07-07": 102.0}
SPLT_QFQ = {day: (close / 4 if day < "2026-07-06" else close) for day, close in SPLT_RAW.items()}
# 真平盘：每天都有会话、收盘一直 50、涨跌一直 0——收盘与涨跌同上一行，却是对的。
FLAT = {day: 50.0 for day in JULY_US}


def july_fetch(function: str, symbol: str) -> list[tuple[date, float]]:
    table = {
        ("index_us_stock_sina", ".DJI"): DJI_JULY,
        ("stock_hk_index_daily_sina", "HSI"): HSI_JULY,
        ("stock_us_daily", "SPLT"): SPLT_RAW,
        ("stock_us_daily_qfq", "SPLT"): SPLT_QFQ,
        ("stock_us_daily", "FLAT"): FLAT,
        ("stock_us_daily_qfq", "FLAT"): FLAT,
    }[(function, symbol)]
    return [(D(day), close) for day, close in table.items()]


def _pct(series: dict, day: str, previous: str) -> float:
    return (series[day] / series[previous] - 1) * 100


def _build_july(path: Path) -> Path:
    with duckdb.connect(str(path)) as con:
        init_db(con)
        for day in JULY_A_SHARE:
            con.execute("insert into fact_market_daily (trade_date) values (?)", [day])
        dji = [
            ("2026-06-30", "2026-06-30", DJI_JULY["2026-06-30"], _pct(DJI_JULY, "2026-06-30", "2026-06-29")),
            ("2026-07-01", "2026-07-01", DJI_JULY["2026-07-01"], _pct(DJI_JULY, "2026-07-01", "2026-06-30")),
            ("2026-07-02", "2026-07-02", DJI_JULY["2026-07-02"], _pct(DJI_JULY, "2026-07-02", "2026-07-01")),
            # 休市型复制：会话日往前推成 07-03，数值抄 07-02（已被查询层判据标出）。
            ("2026-07-03", "2026-07-03", DJI_JULY["2026-07-02"], _pct(DJI_JULY, "2026-07-02", "2026-07-01")),
            # 未标出的冻结：07-06 美股照常开盘，库里却连会话日一起抄了上一行。
            ("2026-07-06", "2026-07-03", DJI_JULY["2026-07-02"], _pct(DJI_JULY, "2026-07-02", "2026-07-01")),
        ]
        hsi = [
            ("2026-06-30", "2026-06-30", HSI_JULY["2026-06-30"], _pct(HSI_JULY, "2026-06-30", "2026-06-29")),
            # 合法休市重复：港股 07-01 休市，会话日如实停在 06-30。
            ("2026-07-01", "2026-06-30", HSI_JULY["2026-06-30"], _pct(HSI_JULY, "2026-06-30", "2026-06-29")),
            ("2026-07-02", "2026-07-02", HSI_JULY["2026-07-02"], _pct(HSI_JULY, "2026-07-02", "2026-06-30")),
            ("2026-07-03", "2026-07-03", HSI_JULY["2026-07-03"], _pct(HSI_JULY, "2026-07-03", "2026-07-02")),
            ("2026-07-06", "2026-07-06", HSI_JULY["2026-07-06"], _pct(HSI_JULY, "2026-07-06", "2026-07-03")),
        ]
        for code, rows, group in (("DJI", dji, "us"), ("HSI", hsi, "hk")):
            for day, session, close, pct in rows:
                con.execute("insert into fact_global_index_daily values (?, ?, ?, ?, ?, ?, ?, 'final', 'fupanhui', now())",
                            [day, session, code, code, group, close, pct])
        for day in ("2026-06-30", "2026-07-01", "2026-07-02"):
            previous = JULY_US[JULY_US.index(day) - 1]
            con.execute(
                "insert into fact_global_stock_daily values (?, ?, 'SPLT', '拆股', 'Split', 'NYSE', ?, ?, 0.5, 9.9e9, "
                "'业务', '地位', 'fupanhui', now())",
                [day, day, SPLT_RAW[day], _pct(SPLT_RAW, day, previous)],
            )
            con.execute(
                "insert into fact_global_stock_daily values (?, ?, 'FLAT', '平盘', 'Flat', 'NYSE', 50.0, 0.0, 0.0, 1.0e9, "
                "'业务', '地位', 'fupanhui', now())",
                [day, day],
            )
    return path


def _july_rows(db: Path, table: str, key: str, code: str) -> dict:
    with duckdb.connect(str(db), read_only=True) as con:
        return {str(day): (str(session), close, pct, source) for day, session, close, pct, source in con.execute(
            f"select trade_date, source_trade_date, close, pct_chg, source from {table} where {key} = ?", [code]).fetchall()}


def test_holiday_copies_only_get_their_session_date_fixed_and_frozen_rows_get_real_values(tmp_path: Path) -> None:
    db = _build_july(tmp_path / "clone.duckdb")

    result = glob.run(db, start=D("2026-06-30"), end=D("2026-07-07"), apply=True,
                      main_db_path=tmp_path / "main.duckdb", fetch=july_fetch, complete_before=D("2026-10-06"))

    assert result["status"] == "ok"
    assert result["reports"][0]["targets"] == {"gap": 2, "clone": 1, "frozen": 1}
    dji = _july_rows(db, "fact_global_index_daily", "code", "DJI")
    # 休市型：会话日改回 07-02，数值保留库里原值，来源标成只修会话日。
    assert dji["2026-07-03"][:3] == ("2026-07-02", DJI_JULY["2026-07-02"], pytest.approx(_pct(DJI_JULY, "2026-07-02", "2026-07-01")))
    assert dji["2026-07-03"][3] == glob.SESSION_FIX_SOURCE
    # 冻结：认出来并写成 07-06 那一场的真实值。
    assert dji["2026-07-06"][:3] == ("2026-07-06", DJI_JULY["2026-07-06"], pytest.approx(_pct(DJI_JULY, "2026-07-06", "2026-07-02")))
    # 合法休市重复（会话日如实停在上一场）不动。
    hsi = _july_rows(db, "fact_global_index_daily", "code", "HSI")
    assert hsi["2026-07-01"][3] == "fupanhui"


def test_split_day_return_uses_the_adjusted_series_and_close_stays_actual(tmp_path: Path) -> None:
    db = _build_july(tmp_path / "clone.duckdb")

    glob.run(db, start=D("2026-06-30"), end=D("2026-07-07"), apply=True,
             main_db_path=tmp_path / "main.duckdb", fetch=july_fetch, complete_before=D("2026-10-06"))

    splt = _july_rows(db, "fact_global_stock_daily", "ts_code", "SPLT")
    # 美股 07-03 休市：断档行沿用 07-02 的值、会话日写 07-02。
    assert splt["2026-07-03"][:2] == ("2026-07-02", SPLT_RAW["2026-07-02"])
    # 拆股日：收盘写实际收盘 101.5，涨跌幅是经济收益 +0.495%，不是未复权相除的 -74.9%。
    assert splt["2026-07-06"][1] == 101.5
    assert splt["2026-07-06"][2] == pytest.approx(_pct(SPLT_QFQ, "2026-07-06", "2026-07-02"))
    assert splt["2026-07-06"][2] > -1


@pytest.mark.parametrize("failure", ["exception", "empty", "stale", "missing_previous", "missing_five_back", "zero", "nan"])
def test_unusable_adjusted_history_blocks_apply_without_raw_return_fallback(tmp_path: Path, failure: str) -> None:
    db = _build_july(tmp_path / "clone.duckdb")
    before = _sha(db)

    def fetch(function: str, symbol: str):
        if function != glob.STOCK_QFQ_SOURCE or symbol != "SPLT":
            return july_fetch(function, symbol)
        if failure == "exception":
            raise RuntimeError("provider unavailable")
        if failure == "empty":
            return []
        rows = july_fetch(function, symbol)
        if failure == "stale":
            return [(day, close) for day, close in rows if day <= D("2026-07-02")]
        if failure in {"missing_previous", "missing_five_back"}:
            missing = D("2026-07-02" if failure == "missing_previous" else "2026-06-26")
            return [(day, close) for day, close in rows if day != missing]
        bad = 0.0 if failure == "zero" else float("nan")
        return [(day, bad if day == D("2026-07-06") else close) for day, close in rows]

    result = glob.run(db, start=D("2026-06-30"), end=D("2026-07-07"), apply=True,
                      main_db_path=tmp_path / "main.duckdb", fetch=fetch, complete_before=D("2026-10-06"))

    assert result["status"] == "needs_user" and result["applied"] is None
    assert any(item["code"] == "SPLT" and item["reason"].startswith("adjusted_")
               for item in result["reports"][1]["skipped"])
    assert any("缺口" in reason for reason in result["reasons"])
    assert _sha(db) == before


def test_adjusted_failure_below_threshold_skips_only_the_affected_stock(tmp_path: Path) -> None:
    db = _build_july(tmp_path / "clone.duckdb")
    with duckdb.connect(str(db)) as con:
        # 21 个代码，缺 1 个 = 4.76%，沿用既有 5% 容忍线，不扩大为全批停写。
        for i in range(19):
            con.execute("insert into fact_global_stock_daily select trade_date, source_trade_date, ?, name_cn, name_en, "
                        "exchange, close, pct_chg, pct_chg_5d, market_cap_usd, business, industry_position, source, updated_at "
                        "from fact_global_stock_daily where ts_code = 'FLAT'", [f"GOOD{i}"])

    def fetch(function: str, symbol: str):
        if function == glob.STOCK_QFQ_SOURCE and symbol == "SPLT":
            raise RuntimeError("provider unavailable")
        return july_fetch(function, "FLAT" if symbol.startswith("GOOD") else symbol)

    result = glob.run(db, start=D("2026-06-30"), end=D("2026-07-07"), apply=True,
                      main_db_path=tmp_path / "main.duckdb", fetch=fetch, complete_before=D("2026-10-06"))

    assert result["status"] == "ok" and result["applied"]["stock_rows"] == 60
    assert result["reports"][1]["targets"]["gap"] == 63
    assert result["reports"][1]["skipped"]
    splt = _july_rows(db, "fact_global_stock_daily", "ts_code", "SPLT")
    assert set(splt) == {"2026-06-30", "2026-07-01", "2026-07-02"}
    assert all(row[3] == "fupanhui" for row in splt.values())
    assert _july_rows(db, "fact_global_stock_daily", "ts_code", "GOOD0")["2026-07-06"][2] == 0.0


def test_a_genuinely_flat_stock_is_not_mistaken_for_a_frozen_copy(tmp_path: Path) -> None:
    db = _build_july(tmp_path / "clone.duckdb")

    result = glob.run(db, start=D("2026-06-30"), end=D("2026-07-07"), apply=True,
                      main_db_path=tmp_path / "main.duckdb", fetch=july_fetch, complete_before=D("2026-10-06"))

    # 两只股票各 3 个表尾断档日；平盘股的已有行不进冻结目标。
    assert result["reports"][1]["targets"] == {"gap": 6, "clone": 0, "frozen": 0}
    flat = _july_rows(db, "fact_global_stock_daily", "ts_code", "FLAT")
    assert {day: row[3] for day, row in flat.items() if day <= "2026-07-02"} == {
        "2026-06-30": "fupanhui", "2026-07-01": "fupanhui", "2026-07-02": "fupanhui"}

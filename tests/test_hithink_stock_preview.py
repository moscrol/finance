"""个股标准化只读预演：自造 schema/数据，不读真 dump、不打开生产库。"""
from datetime import date, datetime
from decimal import DefaultContext, Inexact, ROUND_DOWN, Rounded, localcontext
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest

from market_feature_store.db import SCHEMA_PATH

DAY = date(2026, 9, 15)
PREV = date(2026, 9, 14)
CODE = "600001.SH"
OTHER = "000001.SZ"


def preview(con, **kwargs):
    # 延迟 import：实现前每个行为测试各自见红，不以一次 collection error 冒充反例。
    module = importlib.import_module("market_feature_store.hithink_stock_preview")
    return module.preview_stock_calculation(
        con, kwargs.pop("trade_date", DAY), stock_codes=kwargs.pop("stock_codes", [CODE]),
        **kwargs,
    )


def seed(con):
    # 从唯一 schema 提取三个表定义；canonical 仅作「不可暗回退」哨兵。
    schema = SCHEMA_PATH.read_text()
    for name in ("fact_stock_daily_hithink", "fact_stock_adjustment_hithink", "fact_stock_daily"):
        start = schema.index(f"CREATE TABLE IF NOT EXISTS {name} (")
        con.execute(con.extract_statements(schema[start:])[0].query)
    for day, close in ((PREV, 10.0), (DAY, 10.25)):
        con.execute(
            "INSERT INTO fact_stock_daily_hithink VALUES (?, ?, 10, 11, 9, ?, "
            "150, 123455000, 'none', 'hithink:daily-k-10d', '2026-09-15 18:00:00')",
            [day, CODE, close],
        )
    con.execute(
        "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, "
        "close, pre_close, pct_chg, amount, turnover, source) "
        "VALUES (?, ?, '不能借用的旧名称', 999, 998, 99, 88, 77, 'eastmoney:snapshot')",
        [DAY, CODE],
    )


@pytest.fixture
def con():
    with duckdb.connect(":memory:") as c:
        seed(c)
        yield c


def event(con, *, cash=0.5, bonus=0.0, ratio=0.0, price=0.0, currency="CNY",
          source="hithink:adjustment-factors", day=DAY):
    con.execute(
        "INSERT INTO fact_stock_adjustment_hithink VALUES (?, ?, ?, ?, ?, ?, ?, ?, "
        "'2026-09-15 18:00:00')",
        [CODE, day, cash, bonus, ratio, price, currency, source],
    )


def reasons(report):
    return {reason for gap in report["gaps"] for reason in gap["reasons"]}


def assert_blocked(report, reason):
    assert report["calculation_ready"] is False
    assert report["production_ready"] is False
    assert reason in reasons(report)
    json.dumps(report, allow_nan=False)


def test_units_reference_and_no_canonical_borrowing(con):
    result = preview(con)
    assert result["calculation_ready"] is True
    assert result["production_ready"] is False
    assert result["request_complete"] is None
    assert result["provider_completeness"] == "unverified"
    assert result["adjustment_coverage"] == "unverified"
    assert result["previous_trade_date"] == str(PREV)
    assert result["requested_stock_count"] == result["calculated_stock_count"] == 1
    row = result["rows"][0]
    assert (row["close"], row["pre_close"], row["pct_chg"]) == (10.25, 10.0, 2.5)
    assert (row["amount"], row["volume"]) == (1.2346, 2.0)
    assert row["stock_name"] is None and row["turnover"] is None
    assert row["reference_basis"] == "previous_scheduled_close_no_recorded_event"
    assert result["basis"]["price_adjustment"] == "none"
    assert result["basis"]["amount_unit"] == "亿元"
    assert result["basis"]["volume_unit"] == "手"
    assert result["basis"]["rounding"] == "decimal_from_double_text_half_up"
    assert result["basis"]["window"] == "two_adjacent_scheduled_trading_days"
    json.dumps(result, allow_nan=False)
    con.execute("DROP TABLE fact_stock_daily")
    assert preview(con) == result  # 不依赖旧事实表，名称/换手率不从昨天或旧源填。


def test_cash_dividend_is_not_a_raw_price_drop(con):
    con.execute("UPDATE fact_stock_daily_hithink SET close=9.69 WHERE trade_date=?", [DAY])
    event(con)
    row = preview(con)["rows"][0]
    assert (row["pre_close"], row["pct_chg"]) == (9.5, 2.0)
    assert row["reference_basis"] == "cash_dividend_reference"
    assert row["adjustment_source"] == "hithink:adjustment-factors"


def test_reference_price_rounds_half_up_before_percentage(con):
    event(con, cash=0.005)
    row = preview(con)["rows"][0]
    assert row["pre_close"] == 10.0  # 9.995 → 10.00，不能直接拿9.995除。
    assert row["pct_chg"] == 2.5


@pytest.mark.parametrize("close,pct", [(8.01, 0.13), (6.41, -19.88)])
def test_percentage_half_up_ties_in_both_directions(con, close, pct):
    con.execute("UPDATE fact_stock_daily_hithink SET close=8 WHERE trade_date=?", [PREV])
    con.execute("UPDATE fact_stock_daily_hithink SET low=6")
    # 8.01/8 - 1 = 0.125%；6.41/8 - 1 = -19.875%，两端都不用银行家舍入。
    con.execute("UPDATE fact_stock_daily_hithink SET close=? WHERE trade_date=?", [close, DAY])
    assert preview(con)["rows"][0]["pct_chg"] == pct


@pytest.mark.parametrize("options,reason", [
    ({"bonus": 0.1}, "unsupported-noncash-action"),
    ({"ratio": 0.1, "price": 5.0}, "unsupported-noncash-action"),
    ({"price": 5.0}, "unsupported-noncash-action"),
    ({"cash": None}, "invalid-adjustment-values"),
    ({"bonus": None}, "invalid-adjustment-values"),
    ({"ratio": None}, "invalid-adjustment-values"),
    ({"price": None}, "invalid-adjustment-values"),
    ({"cash": -1.0}, "invalid-adjustment-values"),
    ({"cash": float("nan")}, "invalid-adjustment-values"),
    ({"cash": float("inf")}, "invalid-adjustment-values"),
    ({"currency": "USD"}, "adjustment-provenance"),
    ({"source": "fallback"}, "adjustment-provenance"),
    ({"cash": 10.0}, "invalid-reference-price"),
    ({"cash": 11.0}, "invalid-reference-price"),
])
def test_actions_are_explicit_not_null_to_zero_or_cash_fallback(con, options, reason):
    event(con, **options)
    assert_blocked(preview(con), reason)


def test_only_target_ex_date_affects_return(con):
    baseline = preview(con)
    event(con, day=date(2026, 9, 16), cash=9.9, bonus=10.0)
    assert preview(con) == baseline


def test_missing_previous_day_does_not_use_older_or_canonical_close(con):
    con.execute("UPDATE fact_stock_daily_hithink SET trade_date='2026-09-11' WHERE trade_date=?", [PREV])
    assert_blocked(preview(con), "missing-previous-bar")


def test_weekend_is_crossed_by_schedule_not_latest_observation(con):
    con.execute("UPDATE fact_stock_daily_hithink SET trade_date='2026-09-11' WHERE trade_date=?", [PREV])
    con.execute("UPDATE fact_stock_daily_hithink SET trade_date=? WHERE trade_date=?", [PREV, DAY])
    result = preview(con, trade_date=PREV)
    assert result["calculation_ready"]
    assert result["previous_trade_date"] == "2026-09-11"


@pytest.mark.parametrize("day", ["2026-09-13", "2026-10-01", "2099-09-15", "20260915", datetime(2026, 9, 15)])
def test_unknown_closed_or_ambiguous_dates_rejected_before_read(con, day):
    con.execute("DROP TABLE fact_stock_daily_hithink")
    with pytest.raises(ValueError):
        preview(con, trade_date=day)


@pytest.mark.parametrize("codes", [[], [CODE, CODE], ["600001"], ["000001.SH"],
                                   ["600001.SZ"], ["000001.TI"], [None], CODE, {CODE}])
def test_scope_requires_nonempty_explicit_unique_a_share_identities(con, codes):
    con.execute("DROP TABLE fact_stock_daily_hithink")
    with pytest.raises(ValueError):
        preview(con, stock_codes=codes)


def test_declared_denominator_is_not_reduced_to_observed_rows(con):
    result = preview(con, stock_codes=[CODE, OTHER])
    assert result["requested_stock_count"] == 2
    assert result["calculated_stock_count"] == 1
    assert [row["stock_ts_code"] for row in result["rows"]] == [CODE]
    assert_blocked(result, "missing-current-bar")
    assert result["gaps"][0]["stock_ts_code"] == OTHER


@pytest.mark.parametrize("day,prefix", [(DAY, "current"), (PREV, "previous")])
@pytest.mark.parametrize("column,value,reason", [
    ("close", None, "invalid-price"), ("close", 0, "invalid-price"),
    ("high", float("inf"), "invalid-price"), ("open", float("nan"), "invalid-price"),
    ("low", -1, "invalid-price"), ("close", 10.001, "invalid-price-tick"),
    ("high", 9, "invalid-ohlc"), ("low", 11, "invalid-ohlc"),
    ("volume", None, "invalid-volume-or-amount"), ("volume", -1, "invalid-volume-or-amount"),
    ("volume", 150.5, "invalid-volume-or-amount"),
    ("volume", 0, "nontrading-or-zero-volume-amount"),
    ("turnover", 0, "nontrading-or-zero-volume-amount"),
    ("turnover", float("nan"), "invalid-volume-or-amount"),
    ("source", "hithink:daily-k-10d:fake", "bar-provenance"),
    ("adjusted", "forward", "bar-provenance"), ("updated_at", None, "bar-provenance"),
])
def test_bad_bars_block_without_dropping_fields(con, day, prefix, column, value, reason):
    con.execute(f"UPDATE fact_stock_daily_hithink SET {column}=? WHERE trade_date=?", [value, day])
    assert_blocked(preview(con), f"{prefix}:{reason}")


@pytest.mark.parametrize("table,reason", [
    ("fact_stock_daily_hithink", "duplicate-current-bar"),
    ("fact_stock_adjustment_hithink", "duplicate-adjustment"),
])
def test_duplicate_input_identities_not_silently_deduplicated(con, table, reason):
    event(con)
    # 生产 schema 主键挡重；损坏/旧 schema 也不允许字典末行覆盖前行。
    con.execute(f"CREATE TABLE duplicate_input AS SELECT * FROM {table}")
    con.execute(f"DROP TABLE {table}")
    con.execute(f"ALTER TABLE duplicate_input RENAME TO {table}")
    con.execute(f"INSERT INTO {table} SELECT * FROM {table}")
    assert_blocked(preview(con), reason)


def test_missing_adjustment_table_is_unknown_not_no_actions(con):
    con.execute("DROP TABLE fact_stock_adjustment_hithink")
    with pytest.raises(duckdb.CatalogException):
        preview(con)


def test_read_set_is_one_statement_and_fingerprint_tracks_values(con):
    class OneRead:
        def __init__(self):
            self.statements = []

        def execute(self, sql, params):
            self.statements.append(sql)
            assert len(self.statements) == 1, "行情与事件必须在同一数据库读取快照中取得"
            return con.execute(sql, params)

    guarded = OneRead()
    before = preview(guarded)
    assert len(guarded.statements) == 1
    assert preview(con) == before
    con.execute("UPDATE fact_stock_daily_hithink SET turnover=123465000 WHERE trade_date=?", [DAY])
    after = preview(con)
    assert before["input_fingerprint"] != after["input_fingerprint"]
    assert before["scope_fingerprint"] == after["scope_fingerprint"]


def test_extreme_finite_numbers_do_not_emit_nonfinite_json(con):
    con.execute("UPDATE fact_stock_daily_hithink SET open=1e308, high=1e308, "
                "low=1e308, close=1e308 WHERE trade_date=?", [DAY])
    report = preview(con)
    assert report["calculation_ready"] is False
    assert report["gaps"]
    json.dumps(report, allow_nan=False)


def test_decimal_ambient_precision_rounding_and_traps_cannot_change_result(con):
    baseline = preview(con)
    with localcontext() as ctx:
        ctx.prec = 3
        ctx.rounding = ROUND_DOWN
        ctx.traps[Inexact] = True
        ctx.traps[Rounded] = True
        ctx.Emax = 3
        ctx.Emin = -3
        assert preview(con) == baseline


def test_decimal_default_context_mutation_cannot_change_result(con, monkeypatch):
    baseline = preview(con)
    monkeypatch.setattr(DefaultContext, "Emax", 3)
    monkeypatch.setattr(DefaultContext, "Emin", -3)
    monkeypatch.setattr(DefaultContext, "prec", 3)
    monkeypatch.setitem(DefaultContext.traps, Rounded, True)
    monkeypatch.setitem(DefaultContext.traps, Inexact, True)
    assert preview(con) == baseline


def test_integer_oracle_agrees_with_half_up_price_amount_and_volume(con):
    # 独立整数有理数 oracle：不用被测模块的 Decimal / round 或单日修复器同款表达式。
    def half_up(numerator, denominator):
        sign = -1 if numerator < 0 else 1
        whole, remainder = divmod(abs(numerator), denominator)
        return sign * (whole + (2 * remainder >= denominator))

    count = 0
    con.execute("UPDATE fact_stock_daily_hithink SET open=8, high=100, low=0.01")
    for previous_cents, current_cents in ((800, 801), (800, 641), (999, 1000), (1033, 990)):
        for shares in (1, 49, 50, 149, 150):
            amount_yuan = 123450000 + shares * 100
            con.execute("UPDATE fact_stock_daily_hithink SET close=? WHERE trade_date=?",
                        [previous_cents / 100, PREV])
            con.execute("UPDATE fact_stock_daily_hithink SET close=?, volume=?, turnover=? WHERE trade_date=?",
                        [current_cents / 100, shares, amount_yuan, DAY])
            row = preview(con)["rows"][0]
            assert row["pct_chg"] == half_up((current_cents - previous_cents) * 10000, previous_cents) / 100
            assert row["volume"] == half_up(shares, 100)
            assert row["amount"] == half_up(amount_yuan, 10000) / 10000
            count += 1
    assert count == 20


def test_input_order_does_not_change_scope_or_value_fingerprint(con):
    first = preview(con, stock_codes=[CODE, OTHER])
    assert preview(con, stock_codes=[OTHER, CODE]) == first
    con.execute("CREATE TABLE reordered AS SELECT * FROM fact_stock_daily_hithink ORDER BY trade_date DESC")
    con.execute("DROP TABLE fact_stock_daily_hithink")
    con.execute("ALTER TABLE reordered RENAME TO fact_stock_daily_hithink")
    assert preview(con, stock_codes=[CODE, OTHER]) == first


@pytest.mark.parametrize("code", ["000001.SZ", "302132.SZ", "688001.SH", "920001.BJ", "830001.BJ"])
def test_a_share_market_shapes_are_not_old_single_day_whitelist(con, code):
    con.execute("UPDATE fact_stock_daily_hithink SET stock_ts_code=?", [code])
    assert preview(con, stock_codes=[code])["calculation_ready"]


def test_unselected_or_wrong_day_bad_rows_do_not_contaminate_scope(con):
    baseline = preview(con)
    con.execute("INSERT INTO fact_stock_daily_hithink (trade_date, stock_ts_code) VALUES "
                "(?, ?), ('2026-09-11', ?)", [DAY, OTHER, CODE])
    assert preview(con) == baseline


def test_tiny_positive_turnover_and_volume_expose_rounding_not_suspension(con):
    con.execute("UPDATE fact_stock_daily_hithink SET volume=1, turnover=10 WHERE trade_date=?", [DAY])
    result = preview(con)
    assert result["calculation_ready"]
    row = result["rows"][0]
    assert (row["amount"], row["volume"]) == (0.0, 0.0)
    assert (row["raw_amount_yuan"], row["raw_volume_shares"]) == (10.0, 1.0)


def test_current_and_previous_dump_sources_may_differ_with_explicit_provenance(con):
    con.execute("UPDATE fact_stock_daily_hithink SET source='hithink:daily-k' WHERE trade_date=?", [PREV])
    row = preview(con)["rows"][0]
    assert row["bar_source"] == "hithink:daily-k-10d"
    assert row["previous_bar_source"] == "hithink:daily-k"


def test_duplicate_previous_bar_and_missing_current_remain_gaps(con):
    con.execute("CREATE TABLE duplicated AS SELECT * FROM fact_stock_daily_hithink")
    con.execute("DROP TABLE fact_stock_daily_hithink")
    con.execute("ALTER TABLE duplicated RENAME TO fact_stock_daily_hithink")
    con.execute("INSERT INTO fact_stock_daily_hithink SELECT * FROM fact_stock_daily_hithink WHERE trade_date=?", [PREV])
    con.execute("DELETE FROM fact_stock_daily_hithink WHERE trade_date=?", [DAY])
    report = preview(con)
    assert_blocked(report, "duplicate-previous-bar")
    assert "missing-current-bar" in reasons(report)


def cli_args():
    return ["hithink-stock-preview", "--trade-date", str(DAY), "--stock-code", CODE]


def run_cli(path, args):
    return subprocess.run(
        [sys.executable, "-m", "market_feature_store.cli", *args],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "MARKET_FEATURE_STORE_DB": str(path)},
        capture_output=True, text=True, timeout=20,
    )


@pytest.mark.parametrize("complete", [True, False])
def test_real_cli_exit_readonly_hash_and_scope(tmp_path, complete):
    path = tmp_path / "isolated.duckdb"
    with duckdb.connect(str(path)) as c:
        seed(c)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    args = cli_args() + ([] if complete else ["--stock-code", OTHER])
    process = run_cli(path, args)
    assert process.returncode == (0 if complete else 2), process.stderr
    report = json.loads(process.stdout)
    assert report["calculation_ready"] is complete
    assert not report["production_ready"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_cli_missing_database_never_initializes_it(tmp_path):
    path = tmp_path / "missing" / "never-created.duckdb"
    process = run_cli(path, cli_args())
    assert process.returncode == 2
    report = json.loads(process.stdout)
    assert not report["calculation_ready"]
    assert report["gaps"][0]["reason"] == "database-unavailable-or-schema-mismatch"
    assert not path.parent.exists()


def test_cli_missing_action_table_and_invalid_scope_are_structural(tmp_path):
    path = tmp_path / "isolated.duckdb"
    with duckdb.connect(str(path)) as c:
        seed(c)
        c.execute("DROP TABLE fact_stock_adjustment_hithink")
    process = run_cli(path, cli_args())
    assert process.returncode == 2
    assert json.loads(process.stdout)["gaps"][0]["reason"] == "database-unavailable-or-schema-mismatch"
    process = run_cli(path, cli_args() + ["--stock-code", CODE])
    assert process.returncode == 2
    assert json.loads(process.stdout)["gaps"][0]["reason"] == "invalid-preview-options"


def test_cli_requires_denominator_before_database_open(tmp_path):
    path = tmp_path / "missing" / "never-created.duckdb"
    process = run_cli(path, cli_args()[:-2])
    assert process.returncode == 2
    assert "--stock-code" in process.stderr
    assert not path.parent.exists()


def test_cli_no_key_no_network_no_schema_write(tmp_path, monkeypatch, capsys):
    from market_feature_store import cli, db, hithink_client
    path = tmp_path / "isolated.duckdb"
    with duckdb.connect(str(path)) as c:
        seed(c)

    def forbidden(*a, **kw):
        pytest.fail("只读预演禁止取密钥、外呼或初始化")

    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(cli, "init_db", forbidden)
    monkeypatch.setattr(db, "init_db", forbidden)
    monkeypatch.setattr(hithink_client, "load_api_key", forbidden)
    monkeypatch.setattr(hithink_client, "get_json", forbidden)
    assert cli.main(cli_args()) == 0
    assert json.loads(capsys.readouterr().out)["calculation_ready"]

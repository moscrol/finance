"""repair_backfill_stock_history 单测：scoped 语义 / 预期置缺 / 拒跑 / 幂等。

合同：`docs/handoffs/2026-09-14-302132-prep-review.md`「下一轮执行前合同」。
合成库 30 个交易日（2026-08-03 起的工作日），目标股 999999.SZ：
主表仅 D0 正常行 + D1 空壳 + D2 正常行 + D29 钉值行；并跑表 07-31 起全覆盖；
parquet 夹具供 D27/D28 尾段。另有一只他股 000001.SZ 全量行作不变见证。

钉值策略：technical 用解析精确值（等差 close 步长 0.5 → ma26=18.25、
std26=3.75 等比可手算）；window 钉值由夹具 SQL 对并跑表源数据独立计算。
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import duckdb
import pytest

from market_feature_store.db import init_db
from market_feature_store.sync.repair_backfill_stock_history import (
    BackfillSpec,
    run_backfill_child,
)
from market_feature_store.sync.repair_hithink_stock_day import RepairRefused

CODE = "999999.SZ"
NAME = "测试股份"
OTHER = "000001.SZ"
PREV = "2026-07-31"  # 窗口前一交易日（周五）


def _calendar() -> list[str]:
    days, d = [], date(2026, 8, 3)
    while len(days) < 30:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    return days


CAL = _calendar()


def _close(i: int) -> float:
    return round(10.0 + 0.5 * i, 2)


def _turnover(i: int) -> float:
    return round(_close(i) * (i + 1) * 10000, 2)


def _amount(i: int) -> float:
    """映射后 amount（亿，round4）——与模块 SQL 同式的 Decimal oracle。"""
    v = Decimal(str(_turnover(i))).quantize(Decimal("0.01")) / Decimal(10**8)
    return float(v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _epoch_ms(d: str) -> int:
    dt = datetime.fromisoformat(d).replace(tzinfo=timezone.utc) + timedelta(hours=12)
    return int(dt.timestamp() * 1000)


def _insert(con, table: str, row: dict) -> None:
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))


def _fixture(db_path: Path, parquet_path: Path) -> dict:
    con = duckdb.connect(str(db_path))
    init_db(con)
    for d in [PREV] + CAL:
        _insert(con, "fact_market_daily", {"trade_date": d})
    _insert(con, "fact_stock_daily_hithink", {
        "trade_date": PREV, "stock_ts_code": CODE,
        "open": 9.4, "high": 9.7, "low": 9.3, "close": 9.5, "volume": 5000.0,
        "turnover": 47500.0, "adjusted": "none",
        "source": "hithink:daily-k", "updated_at": datetime(2026, 9, 10, 22, 8)})
    for i, d in enumerate(CAL[:27]):  # 并跑表止于 D26（对齐生产：尾段只由 parquet 供）
        _insert(con, "fact_stock_daily_hithink", {
            "trade_date": d, "stock_ts_code": CODE,
            "open": _close(i) - 0.1, "high": _close(i) + 0.2, "low": _close(i) - 0.2,
            "close": _close(i), "volume": float((i + 1) * 10000),
            "turnover": _turnover(i), "adjusted": "none",
            "source": "hithink:daily-k", "updated_at": datetime(2026, 9, 10, 22, 8)})
    # 主表：D0/D2 正常行、D1 空壳、D29 钉值行（updated_at 固定以便逐字节对照）
    def main_row(i: int, d: str, null_shell: bool = False) -> dict:
        base = {"trade_date": d, "stock_ts_code": CODE, "stock_name": NAME,
                "close": _close(i), "pre_close": _close(i - 1),
                "pct_chg": 5.0, "amount": _amount(i), "turnover": None,
                "source": "fupanhui:sector_stock_daily:fallback",
                "updated_at": datetime(2026, 9, 1, 8),
                "open": _close(i) - 0.1, "high": _close(i) + 0.2,
                "low": _close(i) - 0.2, "volume": float((i + 1) * 100)}
        if null_shell:
            for k in ("open", "high", "low", "close", "pre_close", "pct_chg",
                      "amount", "volume"):
                base[k] = None
        return base

    _insert(con, "fact_stock_daily", main_row(0, CAL[0]))
    _insert(con, "fact_stock_daily", main_row(1, CAL[1], null_shell=True))
    _insert(con, "fact_stock_daily", main_row(2, CAL[2]))
    pinned = {"trade_date": CAL[29], "stock_ts_code": CODE, "stock_name": NAME,
              "close": _close(29), "pre_close": _close(28), "pct_chg": 2.13,
              "amount": _amount(29), "turnover": None, "source": "hithink:daily-k-10d",
              "updated_at": datetime(2026, 9, 12, 2, 19), "open": _close(29) - 0.1,
              "high": _close(29) + 0.2, "low": _close(29) - 0.2, "volume": 3000.0}
    _insert(con, "fact_stock_daily", pinned)
    # 他股见证行：全历 + 派生行（calculated_at 固定）
    for i, d in enumerate(CAL):
        _insert(con, "fact_stock_daily", {
            "trade_date": d, "stock_ts_code": OTHER, "stock_name": "见证股份",
            "close": 20.0 + i, "pre_close": 19.0 + i, "pct_chg": 5.0,
            "amount": 1.5, "turnover": 2.5, "source": "eastmoney:snapshot",
            "updated_at": datetime(2026, 9, 1, 8), "open": 19.5 + i,
            "high": 20.5 + i, "low": 19.0 + i, "volume": 1000.0})
        _insert(con, "feature_stock_technical_daily", {
            "trade_date": d, "stock_ts_code": OTHER, "stock_name": "见证股份",
            "close": 20.0 + i, "ma26": 20.0, "std26": 1.0, "up_value": 20.764,
            "deviation_pct": 1.0, "calculated_at": datetime(2026, 9, 1, 9)})
        _insert(con, "feature_stock_window", {
            "as_of_date": d, "start_date": CAL[0], "end_date": d,
            "stock_ts_code": OTHER, "stock_name": "见证股份",
            "interval_gain_pct": 1.0, "avg_amount": 1.5, "weighted_gain": 0.015,
            "sector_count": 0, "sector_names": None, "sw_l1_names": None,
            "calculated_at": datetime(2026, 9, 1, 9)})
    # 目标股窗内旧派生（待删）：D0 technical + (D4, D0-start) window；窗外旧 technical
    _insert(con, "feature_stock_technical_daily", {
        "trade_date": CAL[0], "stock_ts_code": CODE, "stock_name": NAME,
        "close": _close(0), "ma26": 99.0, "std26": 9.0, "up_value": 99.9,
        "deviation_pct": -9.0, "calculated_at": datetime(2026, 9, 1, 9)})
    _insert(con, "feature_stock_technical_daily", {
        "trade_date": "2025-06-16", "stock_ts_code": CODE, "stock_name": NAME,
        "close": 8.0, "ma26": 7.5, "std26": 0.5, "up_value": 7.882,
        "deviation_pct": 1.5, "calculated_at": datetime(2026, 9, 1, 9)})
    _insert(con, "feature_stock_window", {
        "as_of_date": CAL[4], "start_date": CAL[0], "end_date": CAL[4],
        "stock_ts_code": CODE, "stock_name": NAME, "interval_gain_pct": -9.99,
        "avg_amount": 0.1, "weighted_gain": -0.01, "sector_count": 0,
        "sector_names": None, "sw_l1_names": None,
        "calculated_at": datetime(2026, 9, 1, 9)})
    # parquet 尾段夹具：D26..D29（D26 供 lag 链）
    rows = ", ".join(
        f"('{CODE}', 'CNY', '1d', 'none', {_epoch_ms(CAL[i])}, "
        f"{_close(i) - 0.1}, {_close(i) + 0.2}, {_close(i) - 0.2}, {_close(i)}, "
        f"{(i + 1) * 10000}.0, {_turnover(i)})"
        for i in range(26, 30)
    )
    con.execute(
        f"""
        COPY (
          SELECT * FROM (VALUES {rows}
          ) AS v(thscode, currency, interval, adjusted, date_ms,
                 open_price, high_price, low_price, close_price, volume, turnover)
        ) TO '{parquet_path}' (FORMAT PARQUET)
        """
    )
    con.close()
    return {"pinned": pinned}


def _spec(db_path: Path, parquet_path: Path, pinned: dict) -> BackfillSpec:
    sha = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    # window 钉值由夹具 SQL 对并跑表源数据独立计算（D29 的 5/10/20 日窗）
    con = duckdb.connect(str(db_path), read_only=True)
    win_pins = []
    for p in (20, 10, 5):  # 钉值元组按 start 升序：20d 起点最早
        row = con.execute(
            f"""
            WITH s AS (
              SELECT trade_date, close,
                     round(CAST(turnover AS DECIMAL(38,2)) / 100000000, 4) AS amt
              FROM fact_stock_daily_hithink WHERE stock_ts_code = '{CODE}'
                AND trade_date BETWEEN '{CAL[0]}' AND '{CAL[26]}'
              UNION ALL
              SELECT CAST(to_timestamp(date_ms/1000) AS DATE), close_price,
                     round(CAST(turnover AS DECIMAL(38,2)) / 100000000, 4)
              FROM read_parquet('{parquet_path}')
              WHERE thscode = '{CODE}'
                AND CAST(to_timestamp(date_ms/1000) AS DATE) > '{CAL[26]}'
            ), b AS (
              SELECT trade_date, close,
                     LAG(close, {p}) OVER (ORDER BY trade_date) AS cs,
                     LAG(trade_date, {p}) OVER (ORDER BY trade_date) AS sd,
                     AVG(amt) OVER (ORDER BY trade_date ROWS BETWEEN {p - 1} PRECEDING
                                    AND CURRENT ROW) AS aa
              FROM s
            )
            SELECT CAST(sd AS VARCHAR),
                   ROUND((close / cs - 1) * 100, 2), ROUND(aa, 4)
            FROM b WHERE trade_date = '{CAL[29]}'
            """).fetchone()
        win_pins.append((row[0], float(row[1]), float(row[2])))
    con.close()
    win_pins.sort(key=lambda t: t[0])
    return BackfillSpec(
        code=CODE, name=NAME,
        window_start=CAL[0], main_fill_end=CAL[28], window_end=CAL[29],
        shell_date=CAL[1],
        gap_parallel=tuple(CAL[3:27]), gap_parquet=(CAL[27], CAL[28]),
        expected_total_rows=30,
        stale_technical_dates=(CAL[0],),
        stale_window_keys=((CAL[4], CAL[0]),),
        pinned_0911={k: pinned[k] for k in (
            "stock_name", "close", "pre_close", "pct_chg", "amount", "turnover",
            "source", "open", "high", "low", "volume")},
        pinned_technical_0911={"ma26": 18.25, "std26": 3.75, "up_value": 21.115,
                               "deviation_pct": 16.03},
        pinned_windows_0911=tuple(win_pins),
        expected_technical_count=5,
        expected_window_counts={5: 25, 10: 20, 20: 10, 60: 0},
        parquet_sha256=sha,
        spec_version="test-v1",
    )


def _others_snapshot(con) -> dict:
    return {
        t: con.execute(
            f"SELECT * FROM {t} WHERE stock_ts_code = '{OTHER}' ORDER BY 1, 2"
        ).fetchall()
        for t in ("fact_stock_daily", "feature_stock_technical_daily",
                  "feature_stock_window")
    }


def _outside_snapshot(con) -> dict:
    w0, w1 = CAL[0], CAL[29]
    return {
        "tech": con.execute(
            f"SELECT * FROM feature_stock_technical_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date NOT BETWEEN '{w0}' AND '{w1}'").fetchall(),
        "win": con.execute(
            f"SELECT * FROM feature_stock_window WHERE stock_ts_code='{CODE}' "
            f"AND as_of_date NOT BETWEEN '{w0}' AND '{w1}'").fetchall(),
    }


@pytest.fixture()
def env(tmp_path):
    db = tmp_path / "mini.duckdb"
    pq = tmp_path / "tail.parquet"
    fx = _fixture(db, pq)
    spec = _spec(db, pq, fx["pinned"])
    return db, pq, spec


def test_happy_path_scoped_rebuild(env):
    db, pq, spec = env
    con = duckdb.connect(str(db))
    others_before, outside_before = _others_snapshot(con), _outside_snapshot(con)
    report = run_backfill_child(con, spec, pq)
    assert report["mode"] == "apply"
    n = con.execute(
        f"SELECT COUNT(*) FROM fact_stock_daily WHERE stock_ts_code='{CODE}'"
    ).fetchone()[0]
    assert n == 30
    # 旧行处置：D0 technical 删除（观测不足置缺），(D4, D0-start) window key 删除
    assert con.execute(
        f"SELECT COUNT(*) FROM feature_stock_technical_daily WHERE stock_ts_code='{CODE}' "
        f"AND trade_date='{CAL[0]}'").fetchone()[0] == 0
    assert con.execute(
        f"SELECT COUNT(*) FROM feature_stock_window WHERE stock_ts_code='{CODE}' "
        f"AND as_of_date='{CAL[4]}'").fetchone()[0] == 0
    # 派生物化节奏：technical 5 行（D25..D29）；window 55 行（25+20+10+0）
    assert report["technical_rows"] == 5
    assert report["window_rows"] == 55
    assert report["window_counts"] == {5: 25, 10: 20, 20: 10, 60: 0}
    # 空壳已填充且关键值非空
    shell = con.execute(
        f"SELECT close, pre_close, pct_chg, amount, volume FROM fact_stock_daily "
        f"WHERE stock_ts_code='{CODE}' AND trade_date='{CAL[1]}'").fetchone()
    assert all(v is not None for v in shell)
    # 他股与窗外行逐字节不变（含 calculated_at / updated_at）
    assert _others_snapshot(con) == others_before
    assert _outside_snapshot(con) == outside_before
    con.close()


def test_rerun_idempotent_verify_mode(env):
    db, pq, spec = env
    con = duckdb.connect(str(db))
    run_backfill_child(con, spec, pq)
    snap1_main = con.execute(
        f"SELECT * FROM fact_stock_daily WHERE stock_ts_code='{CODE}' ORDER BY 1"
    ).fetchall()
    snap1_tech_vals = con.execute(
        f"SELECT * FROM feature_stock_technical_daily "
        f"WHERE stock_ts_code='{CODE}' ORDER BY 1").fetchall()
    report2 = run_backfill_child(con, spec, pq)
    assert report2["mode"] == "verify"
    assert con.execute(
        f"SELECT * FROM fact_stock_daily WHERE stock_ts_code='{CODE}' ORDER BY 1"
    ).fetchall() == snap1_main  # 主表逐字节幂等（updated_at 不刷新）
    assert con.execute(
        f"SELECT * FROM feature_stock_technical_daily "
        f"WHERE stock_ts_code='{CODE}' ORDER BY 1").fetchall() == snap1_tech_vals
    # verify 模式零写入：连 calculated_at 都不刷新
    con.close()


@pytest.mark.parametrize("mutate", ["bad_code", "empty_gap", "bad_end",
                                    "bad_hash", "shell_filled", "stale_missing"])
def test_refusals_fail_closed(env, mutate):
    db, pq, spec = env
    con = duckdb.connect(str(db))
    before = _others_snapshot(con)
    kw = dict(code=spec.code, name=spec.name, window_start=spec.window_start,
              main_fill_end=spec.main_fill_end, window_end=spec.window_end,
              shell_date=spec.shell_date, gap_parallel=spec.gap_parallel,
              gap_parquet=spec.gap_parquet,
              expected_total_rows=spec.expected_total_rows,
              stale_technical_dates=spec.stale_technical_dates,
              stale_window_keys=spec.stale_window_keys,
              pinned_0911=spec.pinned_0911,
              pinned_technical_0911=spec.pinned_technical_0911,
              pinned_windows_0911=spec.pinned_windows_0911,
              expected_technical_count=spec.expected_technical_count,
              expected_window_counts=dict(spec.expected_window_counts),
              parquet_sha256=spec.parquet_sha256, spec_version="test-v1")
    if mutate == "bad_code":
        kw["code"] = "BAD"
    elif mutate == "empty_gap":
        kw["gap_parallel"] = ()
    elif mutate == "bad_end":
        kw["window_end"] = "2026-09-12"  # 周六，非交易日
    elif mutate == "bad_hash":
        kw["parquet_sha256"] = "0" * 64
    elif mutate == "shell_filled":
        con.execute(
            f"UPDATE fact_stock_daily SET close=1.0 WHERE stock_ts_code='{CODE}' "
            f"AND trade_date='{CAL[1]}'")
    elif mutate == "stale_missing":
        kw["stale_technical_dates"] = ()
    bad = spec if mutate == "shell_filled" else BackfillSpec(**kw)
    with pytest.raises(RepairRefused):
        run_backfill_child(con, bad, pq)
    # 拒跑后他股不变、目标股主表保持 4 行（guard 在任何写入前）
    assert _others_snapshot(con) == before
    assert con.execute(
        f"SELECT COUNT(*) FROM fact_stock_daily WHERE stock_ts_code='{CODE}'"
    ).fetchone()[0] == 4
    con.close()


def test_widened_delete_counterexample_caught(env, monkeypatch):
    """「只筛 INSERT 不筛 DELETE」反例必须被保护切片指纹抓住。"""
    import market_feature_store.sync.repair_backfill_stock_history as mod

    db, pq, spec = env
    con = duckdb.connect(str(db))

    real = mod._rebuild_derived_scoped

    def evil(con_, spec_, mode_="apply"):
        out = real(con_, spec_, mode_)
        con_.execute(  # 越权删窗外旧行（只筛 INSERT 不筛 DELETE 的等价破坏）
            f"DELETE FROM feature_stock_technical_daily WHERE stock_ts_code='{CODE}' "
            f"AND trade_date='2025-06-16'")
        return out

    monkeypatch.setattr(mod, "_rebuild_derived_scoped", evil)
    with pytest.raises(RepairRefused, match="保护切片"):
        mod.run_backfill_child(con, spec, pq)
    con.close()


def test_oracle_matches_module_mapping():
    """python oracle 与模块 SQL 映射在一组值上逐项相等（映射受测复用的单测锚）。"""
    from market_feature_store.sync.repair_backfill_stock_history import (
        _oracle_amount, _oracle_pct, _oracle_volume)
    mem = duckdb.connect()
    cases = [(62.21, 61.33, 506166603.05, 8159946.0),
             (63.42, 64.35, 598632440.33, 9447135.0),
             (10.0, 9.75, 1234567.89, 10000.0),
             (24.5, 24.0, 73500000.0, 300000.0)]
    for close, pre, turnover, volume in cases:
        row = mem.execute(
            "SELECT CAST(round(CAST((CAST(? AS DECIMAL(18,4))"
            " / CAST(? AS DECIMAL(18,2)) - 1) * 100 AS DECIMAL(38,12)), 2) AS DOUBLE),"
            " CAST(round(CAST(? AS DECIMAL(38,2)) / 100000000, 4) AS DOUBLE),"
            " CAST(round(CAST(? AS DECIMAL(38,0)) / 100, 0) AS DOUBLE)",
            [close, pre, turnover, volume]).fetchone()
        assert abs(row[0] - _oracle_pct(close, pre)) < 1e-9
        assert abs(row[1] - _oracle_amount(turnover)) < 1e-9
        assert abs(row[2] - _oracle_volume(volume)) < 1e-9
    mem.close()


# ── 评审退修（6abd08ac）七条误放行反例 → 全部必须拒绝 ─────────────
import json  # noqa: E402

import market_feature_store.sync.repair_backfill_stock_history as mod  # noqa: E402


def test_refused_missing_retained_source_day(env):
    """P1-2：保留日主表行的并跑表源被删，LAG 会跨日——必须写前拒绝。"""
    db, pq, spec = env
    con = duckdb.connect(str(db))
    con.execute("DELETE FROM fact_stock_daily_hithink WHERE stock_ts_code=? "
                "AND trade_date=?", [CODE, CAL[2]])
    with pytest.raises(RepairRefused, match="源日期集合"):
        mod.run_backfill_child(con, spec, pq)
    con.close()


@pytest.mark.parametrize("field,value", [("open", None), ("pre_close", -999.0)])
def test_refused_verify_corrupt_backfilled_fields(env, field, value):
    """P2-1：回填行关键字段损坏，verify 必须拒绝（全字段 oracle + 键集分母）。"""
    db, pq, spec = env
    con = duckdb.connect(str(db))
    mod.run_backfill_child(con, spec, pq)
    con.execute(f"UPDATE fact_stock_daily SET {field}=? WHERE stock_ts_code=? "
                "AND trade_date=?", [value, CODE, CAL[3]])
    with pytest.raises(RepairRefused, match="oracle"):
        mod.run_backfill_child(con, spec, pq)
    con.close()


def test_refused_verify_source_label_swap(env):
    """P2-1：并跑段行误标 parquet 来源——逐键标签断言必须拒绝。"""
    db, pq, spec = env
    con = duckdb.connect(str(db))
    mod.run_backfill_child(con, spec, pq)
    con.execute("UPDATE fact_stock_daily SET source=? WHERE stock_ts_code=? "
                "AND trade_date=?", [mod.SOURCE_PARQUET, CODE, CAL[3]])
    with pytest.raises(RepairRefused, match="oracle"):
        mod.run_backfill_child(con, spec, pq)
    con.close()


def test_refused_window_nontrading_start(env, monkeypatch):
    """P2-2：窗口起点改为非交易日（跨度计数不变）——黄金三元组必须拒绝。"""
    db, pq, spec = env
    con = duckdb.connect(str(db))
    real = mod._rebuild_derived_scoped

    def corrupt(connection, contract, mode="apply"):
        out = real(connection, contract, mode)
        sunday = (date.fromisoformat(CAL[5]) - timedelta(days=1)).isoformat()
        connection.execute(
            "UPDATE feature_stock_window SET start_date=? WHERE stock_ts_code=? "
            "AND as_of_date=? AND start_date=?", [sunday, CODE, CAL[10], CAL[5]])
        return out

    monkeypatch.setattr(mod, "_rebuild_derived_scoped", corrupt)
    with pytest.raises(RepairRefused, match="黄金三元组"):
        mod.run_backfill_child(con, spec, pq)
    con.close()


def test_refused_pinned_updated_at_tamper(env, monkeypatch):
    """P2-1：09-11 updated_at 被改——保留行全列快照（含 updated_at）必须拒绝。"""
    db, pq, spec = env
    con = duckdb.connect(str(db))
    real = mod._apply_main

    def corrupt(connection, contract, parquet, prev_day, mode="apply"):
        out = real(connection, contract, parquet, prev_day, mode)
        connection.execute("UPDATE fact_stock_daily SET updated_at='2000-01-01' "
                           "WHERE stock_ts_code=? AND trade_date=?",
                           [CODE, spec.window_end])
        return out

    monkeypatch.setattr(mod, "_apply_main", corrupt)
    with pytest.raises(RepairRefused, match="保留行"):
        mod.run_backfill_child(con, spec, pq)
    con.close()


# ── P1-1/P2-3：CLI 报告/收据写出守卫 ────────────────────────────────
def _cli_args(pq, db, report_path=None):
    from types import SimpleNamespace
    return SimpleNamespace(parquet=str(pq), child=True, db=str(db),
                           report_path=str(report_path) if report_path else None)


def test_refused_cli_report_path_overwrites_canonical(tmp_path, monkeypatch):
    """P1-1：--report-path 指向 canonical 见证库——拒绝且库内容不变。"""
    from market_feature_store import cli

    db, pq = tmp_path / "staging.duckdb", tmp_path / "tail.parquet"
    fixture = _fixture(db, pq)
    spec = _spec(db, pq, fixture["pinned"])
    canonical = tmp_path / "canonical-witness.duckdb"
    with duckdb.connect(str(canonical)) as c:
        c.execute("CREATE TABLE witness AS SELECT 123 AS x")
    before = canonical.read_bytes()
    monkeypatch.setenv("MARKET_FEATURE_STORE_PRODUCTION_DB", str(canonical))
    monkeypatch.setattr(mod, "BackfillSpec", lambda: spec)
    rc = cli.cmd_repair_backfill_302132(_cli_args(pq, db, canonical))
    assert rc == 2 and canonical.read_bytes() == before


def test_refused_cli_report_path_existing_file(tmp_path, monkeypatch):
    """P2-3：--report-path 已存在——不可覆盖。"""
    from market_feature_store import cli

    db, pq = tmp_path / "staging.duckdb", tmp_path / "tail.parquet"
    fixture = _fixture(db, pq)
    spec = _spec(db, pq, fixture["pinned"])
    existing = tmp_path / "occupied.json"
    existing.write_text("{}")
    monkeypatch.setenv("MARKET_FEATURE_STORE_PRODUCTION_DB",
                       str(tmp_path / "elsewhere.duckdb"))
    monkeypatch.setattr(mod, "BackfillSpec", lambda: spec)
    rc = cli.cmd_repair_backfill_302132(_cli_args(pq, db, existing))
    assert rc == 2 and existing.read_text() == "{}"


def test_cli_child_receipt_binds_revision_and_run_id(tmp_path, monkeypatch):
    """P2-3：每轮收据绑定 revision/dirty/run_id/spec/源指纹，按 run_id 命名不覆盖。"""
    from market_feature_store import cli

    db, pq = tmp_path / "staging.duckdb", tmp_path / "tail.parquet"
    fixture = _fixture(db, pq)
    spec = _spec(db, pq, fixture["pinned"])
    monkeypatch.setenv("MARKET_FEATURE_STORE_PRODUCTION_DB",
                       str(tmp_path / "elsewhere.duckdb"))
    monkeypatch.setenv("MARKET_FEATURE_STORE_RUN_ID", "test-run-001")
    monkeypatch.setattr(mod, "BackfillSpec", lambda: spec)
    rc = cli.cmd_repair_backfill_302132(_cli_args(pq, db))
    assert rc == 0
    report_path = tmp_path / "staging.duckdb.backfill-report.test-run-001.json"
    report = json.loads(report_path.read_text())
    assert report["run_id"] == "test-run-001"
    assert len(report["code_revision"]) == 40
    assert report["code_dirty"] is not None
    assert report["parquet_sha256"] and report["parallel_source_md5"]
    assert report["interpreter"]
    # 同 run_id 重跑：报告已存在 → 拒绝覆盖
    rc2 = cli.cmd_repair_backfill_302132(_cli_args(pq, db))
    assert rc2 == 2
    count = len(list(tmp_path.glob("staging.duckdb.backfill-report.*.json")))
    assert count == 1

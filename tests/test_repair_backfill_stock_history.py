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

CODE = "302132.SZ"  # 与验收脚本钉死的合同代码一致（E2E 验收回归复用本夹具）
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


def test_cli_parent_rejects_ignored_db_argument_before_side_effects(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from market_feature_store import cli
    from market_feature_store.sync import sync_daily_full

    pq = tmp_path / "source.parquet"
    pq.write_bytes(b"no data access authorized")
    witness = tmp_path / "default-production.duckdb"
    witness.write_bytes(b"production witness")
    called = []

    def parent(**kwargs):
        called.append(kwargs)
        return {"swapped": False, "reason": "must not reach", "rc": 2}

    monkeypatch.setattr(sync_daily_full, "run_daily_full_staged", parent)
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(witness))
    probe_calls = []
    monkeypatch.setattr(mod, "_guarded_write_json", lambda *a, **kw: probe_calls.append(a))
    args = SimpleNamespace(parquet=str(pq), child=False,
                           db=str(tmp_path / "intended-clone.duckdb"), report_path=None)
    assert cli.cmd_repair_backfill_302132(args) == 2
    assert called == []
    assert probe_calls == []
    assert witness.read_bytes() == b"production witness"


def test_cli_parent_preflight_blocks_unwritable_receipt_dir(tmp_path, monkeypatch):
    """收据目录不可写 → 换库前拦截（run_daily_full_staged 不得被调用）。"""
    from market_feature_store import cli
    from market_feature_store.sync import sync_daily_full

    ro_dir = tmp_path / "ro"
    ro_dir.mkdir()
    ro_dir.chmod(0o555)
    pq = tmp_path / "source.parquet"
    pq.write_bytes(b"preflight only checks dir writability")
    called = {}

    def parent(**kwargs):
        called.update(kwargs)
        return {"swapped": False, "reason": "must not reach", "rc": 2}

    monkeypatch.setattr(sync_daily_full, "run_daily_full_staged", parent)
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(ro_dir / "fake.duckdb"))
    from types import SimpleNamespace
    args = SimpleNamespace(parquet=str(pq), child=False, db=None, report_path=None)
    assert cli.cmd_repair_backfill_302132(args) == 2
    assert called == {}  # 预校验拦截在父编排之前


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
    # 身份断言（不是存在性断言）：revision 必须等于运行时 HEAD，dirty 必须如实
    import subprocess
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(mod.PROJECT_DIR),
                          capture_output=True, text=True, check=True,
                          env=_subprocess_env()).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"],
                                cwd=str(mod.PROJECT_DIR), capture_output=True,
                                text=True, check=True,
                                env=_subprocess_env()).stdout.strip())
    assert report["code_revision"] == head
    assert report["code_dirty"] is dirty
    assert report["parquet_sha256"] and report["parallel_source_md5"]
    assert report["interpreter"]
    # 同 run_id 重跑：报告已存在 → 拒绝覆盖
    rc2 = cli.cmd_repair_backfill_302132(_cli_args(pq, db))
    assert rc2 == 2
    count = len(list(tmp_path.glob("staging.duckdb.backfill-report.*.json")))
    assert count == 1


def test_refused_receipt_write_failure_cleans_partial(tmp_path, monkeypatch):
    """P1：write/flush 阶段 OSError → RepairRefused 且不留半截文件。"""
    import os as _os

    target = tmp_path / "r.json"

    class Bomb:
        def __init__(self, fd):
            self.fd = fd

        def __enter__(self):
            return self

        def __exit__(self, *a):
            _os.close(self.fd)
            return False

        def write(self, _s):
            raise OSError("ENOSPC (simulated)")

        def flush(self):
            pass

        def fileno(self):
            return self.fd

    monkeypatch.setattr(mod.os, "fdopen",
                        lambda fd, mode, encoding=None: Bomb(fd))
    with pytest.raises(RepairRefused, match="收据写出失败"):
        mod._guarded_write_json(target, {"x": 1})
    assert not target.exists()


def test_cli_parent_preflight_blocks_on_open_permission_error(tmp_path,
                                                              monkeypatch):
    """预校验拦截不依赖运行用户权限：os.open 抛 PermissionError 也必须拒绝。"""
    from market_feature_store import cli
    from market_feature_store.sync import sync_daily_full

    pq = tmp_path / "source.parquet"
    pq.write_bytes(b"preflight bomb")
    called = {}

    def parent(**kwargs):
        called.update(kwargs)
        return {"swapped": False, "reason": "must not reach", "rc": 2}

    def bomb(*_a, **_k):
        raise PermissionError(13, "simulated")

    monkeypatch.setattr(sync_daily_full, "run_daily_full_staged", parent)
    monkeypatch.setattr(mod.os, "open", bomb)
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "fake.duckdb"))
    from types import SimpleNamespace
    args = SimpleNamespace(parquet=str(pq), child=False, db=None, report_path=None)
    assert cli.cmd_repair_backfill_302132(args) == 2
    assert called == {}


def test_refused_cli_parent_report_path_never_deletes_user_file(tmp_path,
                                                                monkeypatch):
    """P1-1（五轮）：--report-path 指向已有文件时，父命令拒绝但绝不删除它。"""
    from market_feature_store import cli
    from market_feature_store.sync import sync_daily_full

    db, pq = tmp_path / "staging.duckdb", tmp_path / "tail.parquet"
    fixture = _fixture(db, pq)
    spec = _spec(db, pq, fixture["pinned"])
    witness = tmp_path / "witness.duckdb"
    with duckdb.connect(str(witness)) as c:
        c.execute("CREATE TABLE witness AS SELECT 123 AS x")
    before = witness.read_bytes()
    called = {}

    def parent(**kwargs):
        called.update(kwargs)
        return {"swapped": False, "reason": "must not reach", "rc": 2}

    monkeypatch.setattr(sync_daily_full, "run_daily_full_staged", parent)
    monkeypatch.setenv("MARKET_FEATURE_STORE_PRODUCTION_DB",
                       str(tmp_path / "elsewhere.duckdb"))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(db))
    monkeypatch.setattr(mod, "BackfillSpec", lambda: spec)
    from types import SimpleNamespace
    args = SimpleNamespace(parquet=str(pq), child=False, db=None,
                           report_path=str(witness))
    assert cli.cmd_repair_backfill_302132(args) == 2
    assert called == {}                       # 父编排未被调用
    assert witness.read_bytes() == before     # 用户文件原样


def test_refused_receipt_eexist_race_keeps_other_writers_file(tmp_path,
                                                              monkeypatch):
    """P1-2（五轮）：O_EXCL 竞争失败——另一写者的文件必须原样保留。"""
    import os as _os

    target = tmp_path / "r.json"
    real_open = _os.open

    def racing_open(path, flags, mode=0o644):
        # 另一写者抢先创建并写完自己的文件
        fd = real_open(path, _os.O_WRONLY | _os.O_CREAT | _os.O_EXCL, mode)
        with _os.fdopen(fd, "w") as fh:
            fh.write('{"winner": true}\n')
        raise FileExistsError(17, "File exists (simulated race)")

    monkeypatch.setattr(mod.os, "open", racing_open)
    with pytest.raises(RepairRefused, match="收据写出失败|已存在"):
        mod._guarded_write_json(target, {"loser": 1})
    assert target.read_text() == '{"winner": true}\n'


def test_acceptance_script_rejects_hardlink_alias(tmp_path):
    """P1-3（五轮）：production 与 clone 互为硬链接 → 预检拒绝，rc=2。"""
    import subprocess
    import sys

    prod = tmp_path / "prod.duckdb"
    with duckdb.connect(str(prod)) as c:
        c.execute("CREATE TABLE t AS SELECT 1 AS x")
    clone = tmp_path / "clone-hard.duckdb"
    import os as _os
    _os.link(prod, clone)  # 硬链接：realpath 不同，同一 inode
    pq = tmp_path / "q.parquet"
    pq.write_bytes(b"x")
    out = tmp_path / "out.json"
    script = (mod.PROJECT_DIR / "scripts"
              / "verify_302132_backfill_acceptance.py")
    res = subprocess.run(
        [sys.executable, str(script), "--production", str(prod),
         "--clone", str(clone), "--parquet", str(pq),
         "--run-apply", "a", "--run-verify", "v",
         "--expected-revision", "0" * 40,
         "--expected-production-sha256", "0" * 64,
         "--output", str(out)],
        capture_output=True, text=True, timeout=120, env=_subprocess_env())
    assert res.returncode == 2
    verdict = json.loads(out.read_text())
    assert verdict["verdict"] == "FAIL"
    alias = [c for c in verdict["checks"]
             if c["name"] == "clone_is_not_production_alias"]
    assert alias and alias[0]["ok"] is False
    skipped = [c for c in verdict["checks"]
               if c["name"] == "data_checks_executed"]
    assert skipped and skipped[0]["ok"] is False  # 数据检查被跳过，不发绿


def test_acceptance_script_receipt_schema_mutation_fails(tmp_path):
    """P2-1（五轮）：收据缺 spec_version → 结构化 FAIL，缺证据不发绿。"""
    import subprocess
    import sys

    prod = tmp_path / "prod.duckdb"
    with duckdb.connect(str(prod)) as c:
        c.execute("CREATE TABLE t AS SELECT 1 AS x")
    clone = tmp_path / "clone.duckdb"
    with duckdb.connect(str(clone)) as c:
        c.execute("CREATE TABLE t AS SELECT 2 AS x")
    pq = tmp_path / "q.parquet"
    pq.write_bytes(b"x")
    prod_sha = mod._sha256(prod)
    for tag in ("apply", "verify"):
        receipt = {
            "kind": "repair-backfill-302132", "run_id": tag, "trade_date": "2026-09-11",
            "code_revision": "f" * 40, "code_dirty": False, "interpreter": "py",
            "parent": {"swapped": True, "rc": 0, "run_id": tag},
            "backup": {"backup_path": str(prod), "backup_sha256": prod_sha},
            "spec": {"code": "302132.SZ", "name": "中航成飞",
                     # spec_version 故意缺失（变异）
                     "window_start": "2026-06-15", "window_end": "2026-09-11",
                     "main_fill_end": "2026-09-10", "shell_date": "2026-06-23",
                     "parquet_sha256": "0" * 64,
                     "gap_parallel": ["2026-06-17"], "gap_parquet": ["2026-09-09"],
                     "pinned_technical_0911": {}, "pinned_windows_0911": [1],
                     "expected_window_counts": {}, "expected_technical_count": 39},
            "child_report": {"kind": "repair-backfill-302132", "run_id": tag,
                             "mode": tag, "code_revision": "f" * 40,
                             "code_dirty": False, "parquet_sha256": "0" * 64,
                             "protected_slices": {}},
            "child_report_path": None,
        }
        (tmp_path / f"clone.duckdb.repair-backfill-execution.{tag}.json"
         ).write_text(json.dumps(receipt))
    out = tmp_path / "out.json"
    script = (mod.PROJECT_DIR / "scripts"
              / "verify_302132_backfill_acceptance.py")
    res = subprocess.run(
        [sys.executable, str(script), "--production", str(prod),
         "--clone", str(clone), "--parquet", str(pq),
         "--run-apply", "apply", "--run-verify", "verify",
         "--expected-revision", "f" * 40,
         "--expected-production-sha256", prod_sha,
         "--output", str(out)],
        capture_output=True, text=True, timeout=120, env=_subprocess_env())
    assert res.returncode == 2
    verdict = json.loads(out.read_text())
    assert verdict["verdict"] == "FAIL"
    schema = [c for c in verdict["checks"] if c["name"] == "receipt_apply_schema"]
    assert schema and schema[0]["ok"] is False
    assert "spec.spec_version" in str(schema[0]["detail"])
    skipped = [c for c in verdict["checks"]
               if c["name"] == "data_checks_executed"]
    assert skipped and skipped[0]["ok"] is False


# ── 第六轮退修（审查 595a9acd）：验收脚本深 schema / 跨轮绑定 / oracle 输入独立 ──
# 策略：好产物必绿（真实形状两轮产物 E2E PASS）+ 坏产物必红（逐字段单因素变异，
# 父收据与独立子报告同步修改，与审查探针 qc_302132_round6_probes.py 同构）。
import copy  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from dataclasses import asdict, replace  # noqa: E402
from unittest import mock  # noqa: E402

import scripts.verify_302132_backfill_acceptance as verify_acceptance  # noqa: E402

E2E_REV = "f" * 40
APPLY_RUN = "run-apply-001"
VERIFY_RUN = "run-verify-001"
SCHEMA_BOTH = ("receipt_apply_schema", "receipt_verify_schema")


def _subprocess_env() -> dict[str, str]:
    """子进程只接收测试所需白名单，避免宿主凭据进入失败输出。"""
    return {
        "HOME": os.environ.get("HOME", str(Path.home())),
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "FWP_TEST_RECEIPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(mod.PROJECT_DIR),
    }


def _build_e2e_artifacts(root: Path) -> dict:
    """完整可通过验收的两轮产物：基线库 + 结果库（apply/verify 各跑一遍）+
    冻结 parquet + 父收据/独立子报告（字段形状与 cli.py 实际写出一致）。"""
    baseline = root / "baseline.duckdb"
    pq = root / "tail.parquet"
    fx = _fixture(baseline, pq)
    spec = replace(_spec(baseline, pq, fx["pinned"]),
                   spec_version="302132-backfill-test-v1")
    clone = root / "clone.duckdb"
    shutil.copy(str(baseline), str(clone))
    children = {}
    with mock.patch.object(mod, "_code_revision",
                           return_value=(E2E_REV, False)):
        con = duckdb.connect(str(clone))
        try:
            for mode, rid in (("apply", APPLY_RUN), ("verify", VERIFY_RUN)):
                report = mod.run_backfill_child(con, spec, pq)
                assert report["mode"] == mode
                report.update({"run_id": rid, "trade_date": spec.window_end,
                               "kind": "repair-backfill-302132", "ok": True})
                # JSON 往返：内存中的产物形状与验收器读到的完全一致
                # （int 键 → str 键等），变异测试不会在假形状上操作
                children[mode] = json.loads(json.dumps(report))
        finally:
            con.close()
    base_sha = mod._sha256(baseline)
    receipts = {}
    for mode, rid in (("apply", APPLY_RUN), ("verify", VERIFY_RUN)):
        child_path = root / f"child-{mode}.json"
        child_path.write_text(json.dumps(children[mode], ensure_ascii=False))
        receipt = {
            "kind": "repair-backfill-302132", "trade_date": spec.window_end,
            "run_id": rid, "code_revision": E2E_REV, "code_dirty": False,
            "interpreter": sys.executable,
            "spec": json.loads(json.dumps(asdict(spec))),
            "child_report_path": str(child_path),
            "child_report": children[mode], "child_report_error": None,
            "backup": {"backup_path": str(baseline), "backup_sha256": base_sha,
                       "run_id": rid},
            "parent": {"swapped": True, "rc": 0, "run_id": rid},
        }
        (root / f"clone.duckdb.repair-backfill-execution.{rid}.json"
         ).write_text(json.dumps(receipt, ensure_ascii=False))
        receipts[mode] = receipt
    return {"baseline": baseline, "clone": clone, "pq": pq, "spec": spec,
            "receipts": receipts, "base_sha": base_sha}


@pytest.fixture(scope="module")
def e2e_art(tmp_path_factory):
    return _build_e2e_artifacts(tmp_path_factory.mktemp("e2e302132"))


def _run_acceptance(clone: Path, art: dict, out: Path,
                    expected_revision: str = E2E_REV):
    script = mod.PROJECT_DIR / "scripts" / "verify_302132_backfill_acceptance.py"
    return subprocess.run(
        [sys.executable, str(script), "--production", str(art["baseline"]),
         "--clone", str(clone), "--parquet", str(art["pq"]),
         "--run-apply", APPLY_RUN, "--run-verify", VERIFY_RUN,
         "--expected-revision", expected_revision,
         "--expected-production-sha256", art["base_sha"],
         "--output", str(out)],
        capture_output=True, text=True, timeout=120, env=_subprocess_env())


def _install(tmp_path: Path, art: dict, mutate) -> Path:
    """复制结果库并按轮同步变异父收据与独立子报告（与审查探针 install 同构）。"""
    clone = tmp_path / "clone.duckdb"
    shutil.copy(str(art["clone"]), str(clone))
    for mode, rid in (("apply", APPLY_RUN), ("verify", VERIFY_RUN)):
        receipt = copy.deepcopy(art["receipts"][mode])
        mutate(mode, receipt)
        child_path = tmp_path / f"child-{mode}.json"
        child_path.write_text(
            json.dumps(receipt["child_report"], ensure_ascii=False))
        receipt["child_report_path"] = str(child_path)
        (tmp_path / f"clone.duckdb.repair-backfill-execution.{rid}.json"
         ).write_text(json.dumps(receipt, ensure_ascii=False))
    return clone


def _assert_structured_fail(res, out: Path, must_fail=(), must_pass=()):
    """坏产物必红：rc=2 + 结构化 FAIL JSON（非裸异常）；指定检查必红/必绿。"""
    assert res.returncode == 2, (res.stdout, res.stderr)
    assert out.exists(), (res.stdout, res.stderr)
    verdict = json.loads(out.read_text())
    assert verdict["verdict"] == "FAIL"
    for name in must_fail:
        assert name in verdict["failed"], verdict["failed"]
    for name in must_pass:
        assert name not in verdict["failed"], verdict["failed"]
    return verdict


def test_acceptance_e2e_baseline_pass(e2e_art, tmp_path):
    """好产物必绿：深 schema 加严后，真实形状的两轮产物仍通过（不用全绿替代必红）。"""
    out = tmp_path / "out.json"
    res = _run_acceptance(e2e_art["clone"], e2e_art, out)
    assert res.returncode == 0, (res.stdout, res.stderr)
    verdict = json.loads(out.read_text())
    assert verdict["verdict"] == "PASS" and verdict["failed"] == []


def _set0(lst, v):
    lst[0] = v


# 逐字段单因素变异（删除/错误类型/非法值）；每个变异同步作用于两轮收据及其
# 独立子报告文件。全部必须结构化 FAIL（rc=2 + FAIL JSON），不允许裸异常。
RECEIPT_MUTATIONS = [
    # ── 子报告字段（含六轮实测发绿的 parallel_source_md5 缺失 / ok=false）──
    ("child_missing_parallel_source_md5",
     lambda m, r: r["child_report"].pop("parallel_source_md5")),
    ("child_ok_false", lambda m, r: r["child_report"].update(ok=False)),
    ("child_mode_wrong",
     lambda m, r: r["child_report"].update(
         mode="verify" if m == "apply" else "apply")),
    ("child_code_dirty_true",
     lambda m, r: r["child_report"].update(code_dirty=True)),
    ("child_interpreter_mismatch",
     lambda m, r: r["child_report"].update(interpreter="/other/python")),
    ("child_trade_date_mismatch",
     lambda m, r: r["child_report"].update(trade_date="2026-01-04")),
    ("child_window_counts_mismatch",
     lambda m, r: r["child_report"]["window_counts"].update({"5": 999})),
    ("child_window_rows_mismatch",
     lambda m, r: r["child_report"].update(window_rows=1)),
    ("child_technical_rows_mismatch",
     lambda m, r: r["child_report"].update(technical_rows=99)),
    ("child_technical_staged_mismatch",
     lambda m, r: r["child_report"].update(technical_staged=1)),
    ("child_protected_slices_missing_key",
     lambda m, r: r["child_report"]["protected_slices"].pop("tech_protected")),
    ("child_spec_version_mismatch",
     lambda m, r: r["child_report"].update(
         spec_version="302132-backfill-other")),
    ("child_parquet_sha_mismatch",
     lambda m, r: r["child_report"].update(parquet_sha256="1" * 64)),
    ("child_code_mismatch",
     lambda m, r: r["child_report"].update(code="000001.SZ")),
    ("child_run_id_mismatch",
     lambda m, r: r["child_report"].update(run_id="other-run")),
    # ── spec 字段（含六轮实测发绿的空 expected_window_counts / 缺 ma26）──
    ("empty_expected_window_counts",
     lambda m, r: r["spec"].update(expected_window_counts={})),
    ("expected_window_counts_missing_key",
     lambda m, r: r["spec"]["expected_window_counts"].pop("60")),
    ("expected_window_counts_negative",
     lambda m, r: r["spec"]["expected_window_counts"].update({"5": -1})),
    ("expected_window_counts_wrong_type",
     lambda m, r: r["spec"]["expected_window_counts"].update({"5": "59"})),
    ("missing_nested_ma26",
     lambda m, r: r["spec"]["pinned_technical_0911"].pop("ma26")),
    ("pinned_technical_extra_key",
     lambda m, r: r["spec"]["pinned_technical_0911"].update(foo=1.0)),
    ("pinned_technical_nan",
     lambda m, r: r["spec"]["pinned_technical_0911"].update(
         ma26=float("nan"))),
    ("pinned_stock_huge_int",
     lambda m, r: r["spec"]["pinned_0911"].update(close=10**400)),
    ("pinned_technical_huge_int",
     lambda m, r: r["spec"]["pinned_technical_0911"].update(ma26=10**400)),
    ("pinned_window_huge_int",
     lambda m, r: r["spec"]["pinned_windows_0911"][0].__setitem__(1, 10**400)),
    ("pinned_windows_member_short",
     lambda m, r: r["spec"].update(pinned_windows_0911=[["2026-08-28", 5.7]])),
    ("pinned_windows_empty",
     lambda m, r: r["spec"].update(pinned_windows_0911=[])),
    ("pinned_windows_member_bad_type",
     lambda m, r: r["spec"].update(
         pinned_windows_0911=[["2026-08-28", "5.7", 7.9]])),
    ("pinned_0911_missing_key",
     lambda m, r: r["spec"]["pinned_0911"].pop("close")),
    ("pinned_0911_turnover_wrong_type",
     lambda m, r: r["spec"]["pinned_0911"].update(turnover="x")),
    ("gap_parallel_empty", lambda m, r: r["spec"].update(gap_parallel=[])),
    ("gap_parallel_duplicate",
     lambda m, r: r["spec"].update(
         gap_parallel=r["spec"]["gap_parallel"][:1] * 2
         + r["spec"]["gap_parallel"][1:])),
    ("gap_parallel_bad_member_type",
     lambda m, r: _set0(r["spec"]["gap_parallel"], 123)),
    ("gap_parallel_out_of_window",
     lambda m, r: _set0(r["spec"]["gap_parallel"], r["spec"]["window_end"])),
    ("gap_lists_overlap",
     lambda m, r: _set0(r["spec"]["gap_parquet"],
                        r["spec"]["gap_parallel"][0])),
    ("shell_date_in_gap",
     lambda m, r: r["spec"].update(shell_date=r["spec"]["gap_parallel"][0])),
    ("window_order_bad",
     lambda m, r: r["spec"].update(main_fill_end=r["spec"]["window_end"])),
    ("shell_date_out_of_window",
     lambda m, r: r["spec"].update(shell_date=r["spec"]["window_end"])),
    ("spec_version_bad_prefix",
     lambda m, r: r["spec"].update(spec_version="v9")),
    ("spec_parquet_sha_short",
     lambda m, r: r["spec"].update(parquet_sha256="0" * 63)),
    ("spec_code_bad_format", lambda m, r: r["spec"].update(code="BAD")),
    ("expected_technical_count_zero",
     lambda m, r: r["spec"].update(expected_technical_count=0)),
    ("expected_total_rows_zero",
     lambda m, r: r["spec"].update(expected_total_rows=0)),
    ("stale_technical_bad_member",
     lambda m, r: r["spec"].update(stale_technical_dates=["not-a-date"])),
    ("stale_window_keys_bad_member",
     lambda m, r: r["spec"].update(stale_window_keys=[["2026-06-25"]])),
    # ── 父收据字段 ──
    ("parent_swapped_false", lambda m, r: r["parent"].update(swapped=False)),
    ("parent_rc_nonzero", lambda m, r: r["parent"].update(rc=1)),
    ("parent_run_id_mismatch", lambda m, r: r["parent"].update(run_id="x")),
    ("backup_sha_short",
     lambda m, r: r["backup"].update(backup_sha256="0" * 63)),
    ("backup_run_id_mismatch", lambda m, r: r["backup"].update(run_id="x")),
    ("child_report_error_nonnull",
     lambda m, r: r.update(child_report_error="boom")),
    ("trade_date_not_window_end",
     lambda m, r: r.update(trade_date="2026-09-10")),
    ("code_dirty_true", lambda m, r: r.update(code_dirty=True)),
    ("interpreter_empty", lambda m, r: r.update(interpreter="")),
    ("kind_wrong", lambda m, r: r.update(kind="other")),
    ("run_id_mismatch", lambda m, r: r.update(run_id="other-run")),
]


@pytest.mark.parametrize("case,mutate", RECEIPT_MUTATIONS,
                         ids=[c for c, _ in RECEIPT_MUTATIONS])
def test_acceptance_receipt_mutation_fails(e2e_art, tmp_path, case, mutate):
    """六轮 P2-1：逐字段单独变异（父收据与独立子报告同步）→ 结构化 FAIL。"""
    clone = _install(tmp_path, e2e_art, mutate)
    out = tmp_path / "out.json"
    res = _run_acceptance(clone, e2e_art, out)
    _assert_structured_fail(res, out, must_fail=SCHEMA_BOTH)


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, False),
        (False, False),
        (float("nan"), False),
        (float("inf"), False),
        (float("-inf"), False),
        (10**400, False),
        (-(10**400), False),
        (7, True),
        (-2.5, True),
    ],
)
def test_acceptance_is_num_is_total_for_json_numbers(value, expected):
    """JSON 数值判定对布尔、非有限数和超大整数都返回 bool，不得抛异常。"""
    assert verify_acceptance._is_num(value) is expected


@pytest.mark.parametrize(
    "wrong_modes,must_fail,must_pass",
    [
        (("apply",),
         ("receipt_apply_schema", "spec_alignment_apply_verify"),
         ("receipt_verify_schema",)),
        (("verify",),
         ("receipt_verify_schema", "spec_alignment_apply_verify"),
         ("receipt_apply_schema",)),
        (("apply", "verify"),
         SCHEMA_BOTH,
         ("spec_alignment_apply_verify",)),
    ],
    ids=("apply-only", "verify-only", "both-rounds"),
)
def test_acceptance_rejects_spec_code_not_bound_to_sql_target(
        e2e_art, tmp_path, wrong_modes, must_fail, must_pass):
    """每轮 spec/嵌入 child/外部 child 即使同步伪造，也不能改变 SQL 授权对象。"""
    def mutate(mode, receipt):
        if mode in wrong_modes:
            receipt["spec"]["code"] = OTHER
            receipt["child_report"]["code"] = OTHER

    clone = _install(tmp_path, e2e_art, mutate)
    out = tmp_path / "out.json"
    res = _run_acceptance(clone, e2e_art, out)
    _assert_structured_fail(res, out, must_fail=must_fail, must_pass=must_pass)


def test_acceptance_malformed_revision_fails(e2e_art, tmp_path):
    """六轮 P2-1：revision 非 40hex——连 --expected-revision 同步造假也必红。"""
    def mutate(_m, r):
        r["code_revision"] = "not-a-git-revision"
        r["child_report"]["code_revision"] = "not-a-git-revision"

    clone = _install(tmp_path, e2e_art, mutate)
    out = tmp_path / "out.json"
    res = _run_acceptance(clone, e2e_art, out,
                          expected_revision="not-a-git-revision")
    _assert_structured_fail(res, out, must_fail=("args_expected_revision_format",
                                                 *SCHEMA_BOTH))


def test_acceptance_verify_other_parquet_fails(e2e_art, tmp_path):
    """六轮 P2-2：只改 verify 轮 parquet 哈希（父=子同步）必红；apply 臂不受影响。"""
    def mutate(m, r):
        if m == "verify":
            r["spec"]["parquet_sha256"] = "0" * 64
            r["child_report"]["parquet_sha256"] = "0" * 64

    clone = _install(tmp_path, e2e_art, mutate)
    out = tmp_path / "out.json"
    res = _run_acceptance(clone, e2e_art, out)
    _assert_structured_fail(
        res, out,
        must_fail=("parquet_identity_verify", "spec_alignment_apply_verify"),
        must_pass=("parquet_identity_apply", "receipt_verify_schema"))


def test_acceptance_apply_other_parquet_fails(e2e_art, tmp_path):
    """P2-2 对称臂：只改 apply 轮输入哈希同样必红，verify 臂不受影响。"""
    def mutate(m, r):
        if m == "apply":
            r["spec"]["parquet_sha256"] = "0" * 64
            r["child_report"]["parquet_sha256"] = "0" * 64

    clone = _install(tmp_path, e2e_art, mutate)
    out = tmp_path / "out.json"
    res = _run_acceptance(clone, e2e_art, out)
    _assert_structured_fail(
        res, out,
        must_fail=("parquet_identity_apply", "spec_alignment_apply_verify"),
        must_pass=("parquet_identity_verify", "receipt_apply_schema"))


def test_acceptance_verify_spec_divergence_fails(e2e_art, tmp_path):
    """六轮 P2-2：只改 verify 轮授权 spec（子报告同步、轮内一致）——
    跨轮 spec 深比较无白名单，必须单独抓住。"""
    def mutate(m, r):
        if m == "verify":
            r["spec"]["expected_window_counts"]["5"] += 1
            r["child_report"]["window_counts"]["5"] += 1
            r["child_report"]["window_rows"] += 1

    clone = _install(tmp_path, e2e_art, mutate)
    out = tmp_path / "out.json"
    res = _run_acceptance(clone, e2e_art, out)
    _assert_structured_fail(res, out,
                            must_fail=("spec_alignment_apply_verify",),
                            must_pass=SCHEMA_BOTH)


# ── 数据库层变异（六轮 P1-1）：源/输出共同损坏不得自证通过 ──
_GAP_DAY = CAL[3]  # 并跑段首个回填日
_DB_MUTATIONS = [
    # 输出与源一起改（六轮实测发绿的反例）：源表禁止变更 + 基线 oracle 双臂抓住
    ("output_and_source_corrupted_together",
     [f"UPDATE fact_stock_daily SET open=open+1 WHERE stock_ts_code='{CODE}' "
      f"AND trade_date='{_GAP_DAY}'",
      f"UPDATE fact_stock_daily_hithink SET open=open+1 "
      f"WHERE stock_ts_code='{CODE}' AND trade_date='{_GAP_DAY}' "
      f"AND adjusted='none'"],
     ("hithink_source_untouched", "keyset_fullfield_oracle"), ()),
    # 只改结果库源表：oracle 从基线读，键集仍过；整表禁止变更单独抓住
    ("source_only_corrupted",
     [f"UPDATE fact_stock_daily_hithink SET open=open+1 "
      f"WHERE stock_ts_code='{CODE}' AND trade_date='{_GAP_DAY}' "
      f"AND adjusted='none'"],
     ("hithink_source_untouched",),
     ("keyset_fullfield_oracle", "parallel_source_md5_binding")),
    # 只改输出：基线 oracle 单独抓住（源表比较不受影响）
    ("output_only_corrupted",
     [f"UPDATE fact_stock_daily SET open=open+1 WHERE stock_ts_code='{CODE}' "
      f"AND trade_date='{_GAP_DAY}'"],
     ("keyset_fullfield_oracle",), ("hithink_source_untouched",)),
    # 删结果库源行：禁止变更抓住；基线重算指纹不受影响
    ("source_row_deleted",
     [f"DELETE FROM fact_stock_daily_hithink WHERE stock_ts_code='{CODE}' "
      f"AND trade_date='{_GAP_DAY}' AND adjusted='none'"],
     ("hithink_source_untouched",), ("parallel_source_md5_binding",)),
    # 除权源表（pre_close 口径前提）越权写入也禁止
    ("adjustment_source_tampered",
     [f"INSERT INTO fact_stock_adjustment_hithink VALUES "
      f"('{CODE}', '{_GAP_DAY}', 0.1, 0.0, 0.0, 0.0, 'CNY', "
      f"'hithink:adjustment-factors', '2026-09-14 00:00:00')"],
     ("hithink_adjustment_untouched",), ()),
]


@pytest.mark.parametrize("case,sqls,must_fail,must_pass", _DB_MUTATIONS,
                         ids=[c for c, *_ in _DB_MUTATIONS])
def test_acceptance_db_mutation_fails(e2e_art, tmp_path, case, sqls,
                                      must_fail, must_pass):
    """六轮 P1-1：结果库源表/输出任何组合损坏 → 结构化 FAIL（rc=2）。"""
    clone = _install(tmp_path, e2e_art, lambda m, r: None)
    con = duckdb.connect(str(clone))
    try:
        for sql in sqls:
            con.execute(sql)
    finally:
        con.close()
    out = tmp_path / "out.json"
    res = _run_acceptance(clone, e2e_art, out)
    _assert_structured_fail(res, out, must_fail=must_fail, must_pass=must_pass)

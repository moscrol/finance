"""非交易日不得把 L2 状态降级：既不落 failed，也不判缺数。

背景（2026-08-06 覆写事故）：非交易日夜跑照常跑资金流段，段内必然失败
（上游本来就没有数据），外层 `--fail` 把 `ops_pipeline_run_daily` 里
**已经 complete 的历史状态覆写成 failed**。丢的不是当天的空跑，是历史。

契约（三条，各自独立成立）：
1. `mark_failed` 在非交易日直接返回，一行 failed 都不写。
2. `begin_l2_run` 遇到已 complete 的步骤跳过，不把它降级回 running。
3. `check_l2` 在非交易日放行，不把"没有数据"报成"数据不完整"。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
MONEYFLOW_DIR = ROOT / "scripts" / "moneyflow"

TRADING_DAY = "2026-08-04"
NON_TRADING_DAY = "2026-08-08"  # 周六


def _load_write_to_duckdb(monkeypatch):
    monkeypatch.syspath_prepend(str(MONEYFLOW_DIR))
    monkeypatch.delitem(sys.modules, "config", raising=False)
    spec = importlib.util.spec_from_file_location(
        "write_to_duckdb", MONEYFLOW_DIR / "write_to_duckdb.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["write_to_duckdb"] = module
    spec.loader.exec_module(module)
    return module


def _seed_db(path: Path, rows: list[tuple[str, str, str]]) -> None:
    """rows: (trade_date, step, status)

    建表用仓里真实的 DDL（含 PRIMARY KEY）——手搓一张缺主键的同名表会让
    被测代码的 ON CONFLICT 直接 BinderException，测出来的是夹具不是产品。
    """
    ddl = (ROOT / "market_feature_store" / "schema.sql").read_text()
    start = ddl.index("CREATE TABLE IF NOT EXISTS ops_pipeline_run_daily")
    end = ddl.index(");", start) + 2

    con = duckdb.connect(str(path))
    con.execute(ddl[start:end])
    for trade_date, step, status in rows:
        con.execute(
            "INSERT INTO ops_pipeline_run_daily (trade_date, pipeline, step, status) "
            "VALUES (?, 'l2-moneyflow', ?, ?)",
            [trade_date, step, status],
        )
    con.close()


def _statuses(path: Path, trade_date: str) -> dict[str, str]:
    con = duckdb.connect(str(path), read_only=True)
    rows = con.execute(
        "SELECT step, status FROM ops_pipeline_run_daily WHERE trade_date = ?",
        [trade_date],
    ).fetchall()
    con.close()
    return {step: status for step, status in rows}


def test_mark_failed_writes_nothing_on_non_trading_day(monkeypatch, tmp_path):
    """事故复现位：非交易日 --fail 不得覆写历史 complete。"""
    db_path = tmp_path / "m.duckdb"
    _seed_db(db_path, [(NON_TRADING_DAY, "limitup", "complete")])

    module = _load_write_to_duckdb(monkeypatch)
    monkeypatch.setattr(module, "is_trading_day", lambda d: False)
    monkeypatch.setattr(module, "init_db", lambda con: None)
    monkeypatch.setattr(module, "connect", lambda: duckdb.connect(str(db_path)))

    module.mark_failed(NON_TRADING_DAY, "nightly moneyflow rc=1")

    assert _statuses(db_path, NON_TRADING_DAY) == {"limitup": "complete"}


def test_mark_failed_still_writes_on_trading_day(monkeypatch, tmp_path):
    """变异对照：交易日必须照常落 failed，否则这道守卫等于把闸门关死。"""
    db_path = tmp_path / "m.duckdb"
    _seed_db(db_path, [(TRADING_DAY, "limitup", "running")])

    module = _load_write_to_duckdb(monkeypatch)
    monkeypatch.setattr(module, "is_trading_day", lambda d: True)
    monkeypatch.setattr(module, "init_db", lambda con: None)
    monkeypatch.setattr(module, "connect", lambda: duckdb.connect(str(db_path)))

    module.mark_failed(TRADING_DAY, "nightly moneyflow rc=1", steps=("limitup",))

    assert _statuses(db_path, TRADING_DAY)["limitup"] == "failed"


def test_begin_does_not_downgrade_completed_step(monkeypatch, tmp_path):
    """重跑不得把已 complete 的步骤打回 running——那会丢掉完成统计。"""
    db_path = tmp_path / "m.duckdb"
    _seed_db(
        db_path,
        [(TRADING_DAY, "limitup", "complete"), (TRADING_DAY, "top100", "failed")],
    )

    module = _load_write_to_duckdb(monkeypatch)
    monkeypatch.setattr(module, "init_db", lambda con: None)
    monkeypatch.setattr(module, "connect", lambda: duckdb.connect(str(db_path)))

    module.begin_l2_run(TRADING_DAY)

    statuses = _statuses(db_path, TRADING_DAY)
    assert statuses["limitup"] == "complete", "已完成步骤被 begin 降级了"


def test_check_l2_passes_on_non_trading_day_without_touching_db(monkeypatch):
    """非交易日没有 L2 数据是正常的，不该报成"数据不完整"，也不该连库。"""
    from scripts import check_daily_review_data

    monkeypatch.setattr(check_daily_review_data, "is_trading_day", lambda d: False)

    def _boom():
        raise AssertionError("非交易日不应连库")

    monkeypatch.setattr(check_daily_review_data, "_connect_read_only", _boom)

    assert check_daily_review_data.check_l2(NON_TRADING_DAY) == []


def test_check_l2_still_inspects_on_trading_day(monkeypatch):
    """变异对照：交易日必须真的去查，否则 L2 门永远绿。"""
    from scripts import check_daily_review_data

    monkeypatch.setattr(check_daily_review_data, "is_trading_day", lambda d: True)

    called = {"n": 0}

    def _boom():
        called["n"] += 1
        raise RuntimeError("stop-after-connect")

    monkeypatch.setattr(check_daily_review_data, "_connect_read_only", _boom)

    with pytest.raises(RuntimeError, match="stop-after-connect"):
        check_daily_review_data.check_l2(TRADING_DAY)
    assert called["n"] == 1

from __future__ import annotations

from datetime import date, timedelta
import importlib.util
from pathlib import Path
import sys

import duckdb
import pandas as pd
import pytest

from market_feature_store import cli
from market_feature_store.sync import sync_fupanhui_mainline_daily as mainline
from market_feature_store.sync import sync_fupanhui_mainline_sector_daily as mainline_sector
from scripts import check_daily_review_data
from scripts.compute_features import compute_features


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "market_feature_store" / "schema.sql").read_text(encoding="utf-8")
TRADE_DATE = "2026-07-10"
RUN_REVIEW_PATH = ROOT / "skills" / "daily-full-review" / "scripts" / "run_review_sync.py"
RUN_REVIEW_SPEC = importlib.util.spec_from_file_location("run_review_sync", RUN_REVIEW_PATH)
assert RUN_REVIEW_SPEC and RUN_REVIEW_SPEC.loader
run_review_sync = importlib.util.module_from_spec(RUN_REVIEW_SPEC)
RUN_REVIEW_SPEC.loader.exec_module(run_review_sync)


def _database(path: Path | str = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(path))
    con.execute(SCHEMA)
    return con


def _theme(code: str = "T1") -> dict:
    return {"theme_code": code, "theme_name": f"主题{code}", "sector_count": 1, "min_sort": 1}


def _stock_payload(code: str = "000001.SZ") -> dict:
    return {
        "groups": [
            {
                "groupType": "核心",
                "stocks": [
                    {
                        "ts_code": code,
                        "name": "测试股",
                        "price": 10,
                        "changePct": 2,
                        "amount": 100,
                    }
                ],
            }
        ]
    }


def _sector_payload(code: str = "885001.TI") -> list[dict]:
    return [{"sector_code": code, "sector_name": "测试板块", "today_pct": 1.2}]


def _patch_writer(monkeypatch, module, db_path: Path) -> None:
    monkeypatch.setattr(module, "init_db", lambda: None)
    monkeypatch.setattr(module, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)


def test_mainline_complete_snapshot_is_atomic_and_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "mainline.duckdb"
    _database(db_path).close()
    _patch_writer(monkeypatch, mainline, db_path)
    monkeypatch.setattr(mainline.fs, "get_mainline_themes", lambda _date: [_theme()])
    monkeypatch.setattr(mainline.fs, "get_mainline_stocks", lambda _date, _code: _stock_payload())

    first = mainline.sync(TRADE_DATE, attempts=1)
    second = mainline.sync(TRADE_DATE, attempts=1)

    assert first["status"] == second["status"] == "complete"
    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute(
            "SELECT COUNT(*) FROM fact_mainline_theme_daily WHERE trade_date = ?", [TRADE_DATE]
        ).fetchone()[0] == 1
        assert con.execute(
            "SELECT COUNT(*) FROM fact_mainline_stock_daily WHERE trade_date = ?", [TRADE_DATE]
        ).fetchone()[0] == 1


@pytest.mark.parametrize("failure_mode", ["exception", "empty_groups", "empty_stocks"])
def test_mainline_partial_writes_succeeded_themes_as_degraded(tmp_path, monkeypatch, failure_mode):
    """单题材上游失败时写入已成功的题材，status=degraded（不再全有全无）。

    旧契约是「任一题材失败就整批不写、保留前一日快照」，会让上游偶发单题材空
    groups 拖死全日主线落库。现在只要有题材成功就原子写入那些，失败题材进
    ``failures``；全部失败才 ``failed`` 且不写。
    """
    db_path = tmp_path / "mainline-partial.duckdb"
    con = _database(db_path)
    con.execute(
        "INSERT INTO fact_mainline_theme_daily VALUES (?, 'OLD', '旧主题', 1, 1, 'seed', NOW())",
        [TRADE_DATE],
    )
    con.execute(
        """
        INSERT INTO fact_mainline_stock_daily
        VALUES (?, 'OLD', '旧主题', '核心', 'OLD.SZ', '旧股票', 1, 1, 1, 'seed', NOW())
        """,
        [TRADE_DATE],
    )
    con.close()
    _patch_writer(monkeypatch, mainline, db_path)
    monkeypatch.setattr(mainline.fs, "get_mainline_themes", lambda _date: [_theme("T1"), _theme("T2")])
    calls = {"T1": 0, "T2": 0}

    def get_stocks(_date, code):
        calls[code] += 1
        if code == "T1":
            return _stock_payload()
        if failure_mode == "exception":
            raise RuntimeError("upstream unavailable")
        if failure_mode == "empty_groups":
            return {"groups": []}
        return {"groups": [{"groupType": "核心", "stocks": []}]}

    monkeypatch.setattr(mainline.fs, "get_mainline_stocks", get_stocks)

    stats = mainline.sync(TRADE_DATE, attempts=2, retry_delay=0)

    assert stats["status"] == "degraded"
    assert stats["themes"] == stats["stocks"] == 1
    assert stats["expected_themes"] == 2
    assert stats["completed_themes"] == 1
    assert [f["theme_code"] for f in stats["failures"]] == ["T2"]
    assert calls == {"T1": 1, "T2": 2}
    with duckdb.connect(str(db_path), read_only=True) as con:
        # 成功题材落库，前一日快照被当日结果替换（degraded 不等于"什么都没做"）
        assert con.execute(
            "SELECT theme_code FROM fact_mainline_theme_daily WHERE trade_date = ?", [TRADE_DATE]
        ).fetchall() == [("T1",)]
        assert con.execute(
            "SELECT stock_ts_code FROM fact_mainline_stock_daily WHERE trade_date = ?", [TRADE_DATE]
        ).fetchall() == [("000001.SZ",)]


def test_mainline_empty_theme_list_is_failed_without_writing(tmp_path, monkeypatch):
    db_path = tmp_path / "empty-themes.duckdb"
    _database(db_path).close()
    _patch_writer(monkeypatch, mainline, db_path)
    monkeypatch.setattr(mainline.fs, "get_mainline_themes", lambda _date: [])

    stats = mainline.sync(TRADE_DATE, attempts=2, retry_delay=0)

    assert stats["status"] == "failed"
    assert stats["expected_themes"] == 0


@pytest.mark.parametrize("response", [[], RuntimeError("sector request failed")])
def test_mainline_sector_failure_keeps_previous_snapshot(tmp_path, monkeypatch, response):
    db_path = tmp_path / "mainline-sector.duckdb"
    con = _database(db_path)
    con.execute(
        """
        INSERT INTO fact_mainline_sector_daily (
            trade_date, theme_code, theme_name, sector_ts_code, sector_name, source, updated_at
        ) VALUES (?, 'OLD', '旧主题', 'OLD.TI', '旧板块', 'seed', NOW())
        """,
        [TRADE_DATE],
    )
    con.close()
    _patch_writer(monkeypatch, mainline_sector, db_path)
    monkeypatch.setattr(mainline_sector.fs, "get_mainline_themes", lambda _date: [_theme()])
    calls = 0

    def get_sectors(_date, _code):
        nonlocal calls
        calls += 1
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(mainline_sector.fs, "get_mainline_sectors", get_sectors)

    stats = mainline_sector.sync(TRADE_DATE, attempts=2, retry_delay=0)

    assert stats["status"] == "failed"
    assert calls == 2
    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute(
            "SELECT sector_ts_code FROM fact_mainline_sector_daily WHERE trade_date = ?",
            [TRADE_DATE],
        ).fetchall() == [("OLD.TI",)]


def test_mainline_cli_returns_nonzero_for_partial(monkeypatch):
    partial = {
        "themes": 0,
        "stocks": 0,
        "failures": [{"theme_code": "T2", "error": "failed"}],
        "status": "partial",
    }
    monkeypatch.setattr(mainline, "sync", lambda _date: partial)

    assert cli.cmd_sync_mainline_daily(type("Args", (), {"trade_date": TRADE_DATE})()) == 2


def _seed_feature_inputs(con: duckdb.DuckDBPyConnection, count: int = 70) -> str:
    start = date(2026, 1, 1)
    for offset in range(count):
        current = start + timedelta(days=offset)
        con.execute(
            """
            INSERT INTO fact_market_daily (
                trade_date, total_amount, advancers, limit_up, limit_down, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'test', NOW())
            """,
            [current, 10000 + offset, 2000 + offset * 10, 40 + offset, 5],
        )
        con.execute(
            """
            INSERT INTO fact_stock_daily (
                trade_date, stock_ts_code, stock_name, close, amount, source, updated_at
            ) VALUES (?, '000001.SZ', '测试股', ?, ?, 'test', NOW())
            """,
            [current, 10 + offset / 10, 100 + offset],
        )
        con.execute(
            """
            -- fact_sector_daily 是 VIEW，写入落 *_generation；'legacy' 对应
            -- 快照机制上线前的历史数据（当日无 published 快照时可见）。
            INSERT INTO fact_sector_daily_generation (
                trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                sw_l1, pct_chg, amount, diff_ratio, source, updated_at
            ) VALUES (?, 'legacy', '885001.TI', '测试板块', '一级行业', 1, ?, ?, 'test', NOW())
            """,
            [current, 1000 + offset, offset / 10],
        )
    return str(start + timedelta(days=count - 1))


def test_compute_features_uses_latest_canonical_inputs():
    con = _database()
    latest = _seed_feature_inputs(con)

    stats = compute_features(con=con)

    assert stats["trade_date"] == latest
    assert stats["status"] == "complete"
    assert stats["tables"]["feature_market_window"] == 4
    assert stats["tables"]["feature_stock_window"] == 4
    assert stats["tables"]["feature_sector_window"] == 4
    assert stats["tables"]["feature_stock_technical_daily"] == 1
    assert stats["tables"]["fact_sector_period_rank_daily"] == 4
    assert con.execute(
        """
        SELECT period_type, change_pct, source
        FROM fact_sector_period_rank_daily
        WHERE trade_date = ?
        ORDER BY CASE period_type
            WHEN 'daily' THEN 1 WHEN 'day3' THEN 2 WHEN 'day5' THEN 3 ELSE 4
        END
        """,
        [latest],
    ).fetchall() == [
        ("daily", 1.0, "derived:fact_sector_daily"),
        ("day3", 3.03, "derived:fact_sector_daily"),
        ("day5", 5.1, "derived:fact_sector_daily"),
        ("day10", 10.46, "derived:fact_sector_daily"),
    ]
    assert con.execute(
        "SELECT COUNT(*) FROM feature_stock_technical_daily WHERE trade_date = ?", [latest]
    ).fetchone()[0] == 1


def test_compute_feature_failure_preserves_existing_rows():
    con = _database()
    latest = _seed_feature_inputs(con)
    next_date = str(date.fromisoformat(latest) + timedelta(days=1))
    con.execute(
        """
        INSERT INTO fact_market_daily (
            trade_date, total_amount, advancers, limit_up, limit_down, source, updated_at
        ) VALUES (?, 20000, 3000, 100, 1, 'test', NOW())
        """,
        [next_date],
    )
    con.execute(
        """
        INSERT INTO feature_market_window (
            as_of_date, start_date, end_date, advancers_start, advancers_end,
            advancers_change, calculated_at
        ) VALUES (?, ?, ?, 1, 2, 1, NOW())
        """,
        [next_date, latest, next_date],
    )

    with pytest.raises(RuntimeError, match="feature_stock_window"):
        compute_features(next_date, selected=("market", "stock"), con=con)

    assert con.execute(
        "SELECT advancers_start FROM feature_market_window WHERE as_of_date = ?", [next_date]
    ).fetchall() == [(1,)]


def test_daily_gate_reports_mainline_coverage_gap(tmp_path, monkeypatch):
    db_path = tmp_path / "quality.duckdb"
    con = _database(db_path)
    con.execute(
        "INSERT INTO fact_mainline_theme_daily VALUES (?, 'T1', '主题', 1, 1, 'test', NOW())",
        [TRADE_DATE],
    )
    con.execute(
        """
        INSERT INTO fact_mainline_stock_daily
        VALUES (?, 'T1', '主题', '核心', '000001.SZ', '测试股', 1, 1, 1, 'test', NOW())
        """,
        [TRADE_DATE],
    )
    con.close()
    monkeypatch.setattr(
        check_daily_review_data,
        "connect",
        lambda read_only=False: duckdb.connect(str(db_path), read_only=read_only),
    )
    monkeypatch.setattr(check_daily_review_data, "TABLES", ["fact_mainline_theme_daily"])
    monkeypatch.setattr(check_daily_review_data, "MARKET_FIELDS", [])

    missing = check_daily_review_data.check_data(TRADE_DATE)

    assert any("主线题材 T1/主题 覆盖不完整" in item and "核心板块 0 行" in item for item in missing)


def test_l2_gate_reports_stale_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "l2.duckdb"
    con = _database(db_path)
    con.execute(
        """
        INSERT INTO feature_l2_capital_flow_daily (
            trade_date, scan_type, stock_code, stock_ts_code, stock_name, source, calculated_at
        ) VALUES ('2026-07-09', 'top100', '000001', '000001.SZ', '测试股', 'test', NOW())
        """
    )
    con.close()
    monkeypatch.setattr(
        check_daily_review_data,
        "connect",
        lambda read_only=False: duckdb.connect(str(db_path), read_only=read_only),
    )

    missing = check_daily_review_data.check_l2(TRADE_DATE)

    assert len(missing) == 3
    assert all("无 2026-07-10 完成记录" in item for item in missing)


def _load_l2_writer(monkeypatch, db_path):
    moneyflow_dir = ROOT / "scripts" / "moneyflow"
    monkeypatch.syspath_prepend(str(moneyflow_dir))
    monkeypatch.delitem(sys.modules, "config", raising=False)
    spec = importlib.util.spec_from_file_location(
        "test_write_to_duckdb", moneyflow_dir / "write_to_duckdb.py"
    )
    assert spec and spec.loader
    writer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(writer)
    monkeypatch.setattr(writer, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(writer, "init_db", lambda con: con.execute(SCHEMA))
    return writer


def _gate_db(monkeypatch, db_path):
    monkeypatch.setattr(
        check_daily_review_data,
        "connect",
        lambda read_only=False: duckdb.connect(str(db_path), read_only=read_only),
    )


def _stats(input_count, processed=None, failed=0):
    return {
        "input_count": input_count,
        "processed_count": input_count if processed is None else processed,
        "failed_count": failed,
    }


def test_l2_gate_rejects_empty_results_without_stats(tmp_path, monkeypatch):
    db_path = tmp_path / "l2-nostats.duckdb"
    _database(db_path).close()
    writer = _load_l2_writer(monkeypatch, db_path)
    empty = pd.DataFrame()

    writer.begin_l2_run(TRADE_DATE)
    with pytest.raises(RuntimeError, match="missing scan stats"):
        writer.write_capital_flow(TRADE_DATE, "limitup", empty, 50)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        status, message = con.execute(
            "SELECT status, message FROM ops_pipeline_run_daily "
            "WHERE trade_date = ? AND step = 'limitup'",
            [TRADE_DATE],
        ).fetchone()
    finally:
        con.close()
    assert status == "failed"
    assert "missing scan stats" in message

    _gate_db(monkeypatch, db_path)
    missing = check_daily_review_data.check_l2(TRADE_DATE)
    assert any("limitup 状态为 failed" in item for item in missing)


def _sample_capital_df(n=1):
    """最小非空 capital 榜，避免 0 行被新闸门拒绝。"""
    rows = []
    for i in range(n):
        code = f"{i + 1:06d}"
        rows.append(
            {
                "code": code,
                "name": f"测试{i}",
                "主买净额(万)": 100.0 + i,
                "总买净额(万)": 80.0 + i,
                "流通市值(亿)": 50.0,
                "综合得分": 1.0,
                "当日涨幅%": 1.5,
            }
        )
    return pd.DataFrame(rows)


def test_l2_gate_rejects_zero_capital_results(tmp_path, monkeypatch):
    """有候选却 0 行 capital 结果：写库拒绝 complete，闸门报 failed。"""
    db_path = tmp_path / "l2-empty.duckdb"
    _database(db_path).close()
    writer = _load_l2_writer(monkeypatch, db_path)
    empty = pd.DataFrame()

    writer.begin_l2_run(TRADE_DATE)
    with pytest.raises(RuntimeError, match="zero rows for limitup"):
        writer.write_capital_flow(TRADE_DATE, "limitup", empty, 50, stats=_stats(20))

    _gate_db(monkeypatch, db_path)
    missing = check_daily_review_data.check_l2(TRADE_DATE)
    assert any("limitup 状态为 failed" in item for item in missing)


def test_l2_gate_accepts_nonempty_capital_and_empty_quant(tmp_path, monkeypatch):
    """capital 有数据、quant 可为 0 行（当日无量化簇）。"""
    db_path = tmp_path / "l2-ok.duckdb"
    _database(db_path).close()
    writer = _load_l2_writer(monkeypatch, db_path)
    capital = _sample_capital_df(3)
    empty = pd.DataFrame()

    writer.begin_l2_run(TRADE_DATE)
    writer.write_capital_flow(TRADE_DATE, "limitup", capital, 50, stats=_stats(20))
    writer.write_capital_flow(TRADE_DATE, "top100", capital, 50, stats=_stats(120))
    writer.write_quant_orders(TRADE_DATE, empty, 50, 200, stats=_stats(150))

    _gate_db(monkeypatch, db_path)
    assert check_daily_review_data.check_l2(TRADE_DATE) == []


def test_l2_gate_rejects_failed_scan_stats(tmp_path, monkeypatch):
    db_path = tmp_path / "l2-failed.duckdb"
    _database(db_path).close()
    writer = _load_l2_writer(monkeypatch, db_path)
    empty = pd.DataFrame()

    writer.begin_l2_run(TRADE_DATE)
    with pytest.raises(RuntimeError, match="failed_count=3"):
        writer.write_quant_orders(
            TRADE_DATE, empty, 50, 200, stats=_stats(150, processed=147, failed=3)
        )

    _gate_db(monkeypatch, db_path)
    missing = check_daily_review_data.check_l2(TRADE_DATE)
    assert any("quant 状态为 failed" in item for item in missing)


def test_l2_gate_rejects_top100_with_insufficient_inputs(tmp_path, monkeypatch):
    db_path = tmp_path / "l2-top50.duckdb"
    _database(db_path).close()
    writer = _load_l2_writer(monkeypatch, db_path)
    capital = _sample_capital_df(2)
    empty = pd.DataFrame()

    writer.begin_l2_run(TRADE_DATE)
    writer.write_capital_flow(TRADE_DATE, "limitup", capital, 50, stats=_stats(20))
    writer.write_capital_flow(TRADE_DATE, "top100", capital, 50, stats=_stats(50))
    writer.write_quant_orders(TRADE_DATE, empty, 50, 200, stats=_stats(150))

    _gate_db(monkeypatch, db_path)
    missing = check_daily_review_data.check_l2(TRADE_DATE)
    assert any("top100 input_count=50 < 100" in item for item in missing)


def test_l2_gate_rejects_row_count_mismatch(tmp_path, monkeypatch):
    db_path = tmp_path / "l2-mismatch.duckdb"
    _database(db_path).close()
    writer = _load_l2_writer(monkeypatch, db_path)
    capital = _sample_capital_df(2)
    empty = pd.DataFrame()

    writer.begin_l2_run(TRADE_DATE)
    writer.write_capital_flow(TRADE_DATE, "limitup", capital, 50, stats=_stats(20))
    writer.write_capital_flow(TRADE_DATE, "top100", capital, 50, stats=_stats(120))
    writer.write_quant_orders(TRADE_DATE, empty, 50, 200, stats=_stats(150))
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "UPDATE ops_pipeline_run_daily SET row_count = 5 "
            "WHERE trade_date = ? AND step = 'top100'",
            [TRADE_DATE],
        )
    finally:
        con.close()

    _gate_db(monkeypatch, db_path)
    missing = check_daily_review_data.check_l2(TRADE_DATE)
    assert any("top100 状态表 row_count=5 与结果表实际 2 行不一致" in item for item in missing)


def test_mark_failed_covers_running_steps_only(tmp_path, monkeypatch):
    db_path = tmp_path / "l2-markfail.duckdb"
    _database(db_path).close()
    writer = _load_l2_writer(monkeypatch, db_path)
    capital = _sample_capital_df(1)

    writer.begin_l2_run(TRADE_DATE)
    writer.write_capital_flow(TRADE_DATE, "limitup", capital, 50, stats=_stats(20))
    writer.mark_failed(TRADE_DATE, "nightly moneyflow rc=1")

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = dict(con.execute(
            "SELECT step, status FROM ops_pipeline_run_daily WHERE trade_date = ?",
            [TRADE_DATE],
        ).fetchall())
    finally:
        con.close()
    assert rows == {"limitup": "complete", "top100": "failed", "quant": "failed"}

    _gate_db(monkeypatch, db_path)
    missing = check_daily_review_data.check_l2(TRADE_DATE)
    assert any("top100 状态为 failed" in item for item in missing)
    assert any("quant 状态为 failed" in item for item in missing)


def test_sync_plan_includes_mainline_sectors_and_features(monkeypatch):
    monkeypatch.setattr(run_review_sync, "run_step", lambda *args, **kwargs: True)
    names = [name for name, _runner in run_review_sync.build_plan(TRADE_DATE, 1, 2)]

    assert names.index("mainline-sector-daily") == names.index("mainline-daily") + 1
    assert names.index("features") > names.index("theme-flow-daily")


def test_nightly_script_attempts_l2_before_sync_failure_exit():
    """`all` 阶段里 L2 必须在「同步段失败就退出」之前跑。

    L2（资金流）不依赖同步段产物，所以同步失败也该照跑，否则一次 CDP 掉线就
    连带丢掉当天的 L2 数据。脚本后来拆成 sync/finalize/all 三阶段，调用点从
    ``run_moneyflow`` 改名为 ``run_l2_branch``（后者内部才调前者），这里按新
    名字锚定，并把断言限定在 `all)` 分支内——sync 阶段本就不跑 L2。
    """
    script = (
        ROOT / "skills" / "daily-full-review" / "scripts" / "nightly_full_review.sh"
    ).read_text(encoding="utf-8")
    all_phase = script.index("\n  all)")
    sync_result = script.index("rc=$?", all_phase)
    l2 = script.index("run_l2_branch", sync_result)
    sync_exit = script.index('if [ "$rc" -ne 0 ]', l2)

    assert sync_result < l2 < sync_exit

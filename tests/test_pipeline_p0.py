from __future__ import annotations

from datetime import date, timedelta
import importlib.util
from pathlib import Path
import sys

import duckdb
import pandas as pd
import pytest

from market_feature_store import cli, db
from market_feature_store.sync import sync_fupanhui_mainline_daily as mainline
from market_feature_store.sync import sync_fupanhui_mainline_sector_daily as mainline_sector
from scripts import check_daily_review_data
from scripts.compute_features import compute_features


ROOT = Path(__file__).resolve().parents[1]
TRADE_DATE = "2026-07-10"
RUN_REVIEW_PATH = ROOT / "skills" / "daily-full-review" / "scripts" / "run_review_sync.py"
RUN_REVIEW_SPEC = importlib.util.spec_from_file_location("run_review_sync", RUN_REVIEW_PATH)
assert RUN_REVIEW_SPEC and RUN_REVIEW_SPEC.loader
run_review_sync = importlib.util.module_from_spec(RUN_REVIEW_SPEC)
RUN_REVIEW_SPEC.loader.exec_module(run_review_sync)


def _database(path: Path | str = ":memory:") -> duckdb.DuckDBPyConnection:
    """用生产入口 init_db 建库, 让测试看到与生产一致的迁移后 schema。"""
    con = duckdb.connect(str(path))
    db.init_db(con)
    return con


def _seed_legacy_sector_daily(con: duckdb.DuckDBPyConnection, rows: list[tuple]) -> None:
    """向尚未发布快照的交易日写入 legacy 代际行。

    公开的 fact_sector_daily 已是只读视图, 没有 published 表头的日期只暴露 legacy 行;
    测试目录不在 Task 7 访问门禁的扫描范围内。
    """
    con.executemany(
        """
        INSERT INTO fact_sector_daily_generation (
            trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
            sw_l1, pct_chg, amount, diff_ratio, source, updated_at
        ) VALUES (?, 'legacy', ?, ?, ?, ?, ?, ?, 'test', NOW())
        """,
        rows,
    )


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
    # Legacy server scans can confirm empty ticks; file-source coverage has separate tests.
    monkeypatch.setenv("L2_SOURCE", "clickhouse:test")
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
    monkeypatch.setattr(writer, "init_db", db.init_db)
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


def test_sync_plan_includes_public_assets_between_theme_flow_and_features(monkeypatch):
    monkeypatch.setattr(run_review_sync, "run_step", lambda *args, **kwargs: True)
    names = [name for name, _runner in run_review_sync.build_plan(TRADE_DATE, 1, 2)]

    assert names.index("public-assets") == names.index("theme-flow-daily") + 1
    assert names.index("features") == names.index("public-assets") + 1


def test_sync_plan_omits_retired_sector_feishu_step(monkeypatch):
    monkeypatch.setattr(run_review_sync, "run_step", lambda *args, **kwargs: True)
    names = [name for name, _runner in run_review_sync.build_plan(TRADE_DATE, 1, 2)]

    assert "sector-resonance" not in names
    assert "market-daily" not in names


def test_cli_omits_retired_sector_feishu_commands():
    parser = cli.build_parser()
    commands = set(parser._subparsers._group_actions[0].choices)

    assert {
        "sync-sector-marginal",
        "sync-sector-daily-metrics",
        "sync-sector-resonance",
        "sync-market-daily",
        # 2026-09-11 随飞书自建应用一起退：最后一个拿凭证的 sync 子命令。
        "sync-limit-advance-feishu",
    }.isdisjoint(commands)


def test_no_module_reads_feishu_credentials():
    """仓内不得再有任何东西拿飞书凭证。

    这是「删应用」能不能真删的门禁：只要还有一处读 `feishu_config.json` /
    换 `tenant_access_token`，用户在开放平台上删掉应用就会把某条链路打断。
    `intelligence/dream/collector.py` 的 `normalize_feishu_event` 不在此列：
    它只解析已归档的 transcript 文件，不联网、不拿密钥。

    用 `git grep`（只看已跟踪文件）——门禁守的是「能合进主干的东西」，
    本地未入库的草稿文件不在射程内，这是有意的取舍。

    2026-09-11 #729 收窄口径（用户裁定「那几个 skill 别删，它们是有用的」）：
    禁令对**自动链路**（`market_feature_store/` `intelligence/` `scripts/` 等）保持绝对——
    那才是「删掉应用会把某条链路打断」的射程。`skills/` 下是人/agent 显式触发、
    且已在各自 SKILL.md 标注「写入步已停」的封存脚本，没有任何流水线调用它们，
    删应用不会打断任何链路，故予以豁免；但豁免是**逐文件钉死的**，
    新增的读取点仍会红——只保留不扩张。
    """
    import subprocess

    needles = ("feishu_config.json", "tenant_access_token", "FEISHU_APP_SECRET", "feishu_utils")
    # 反向白名单：这些地方提到文件名是为了「禁止提交它」，是防线不是读取点
    # （worktree_closeout.py：拆树前封存未提交源码时，凭证配置一律不进封存提交）。
    allowed = {"scripts/agent_review/contract.py", "scripts/worktree_closeout.py"}
    # 封存名单（#729）：飞书退役前就存在、随 skill 一并保留的读取点，逐个钉死。
    parked_allowed = {
        "skills/advancers-chart/scripts/feishu_chart.py",
        "skills/advancers-chart/scripts/migrate_dates.py",
        "skills/advancers-chart/scripts/sync.py",
        "skills/high-volume-gainers/scripts/write.py",
        "skills/limit-advance/scripts/check_coverage.py",
        "skills/limit-advance/scripts/dedup_fields.py",
        "skills/limit-advance/scripts/write.py",
        "skills/market-overview/scripts/check_coverage.py",
        "skills/market-overview/scripts/verify_and_patch.py",
        "skills/top-gainers-feishu/scripts/query_ma.py",
        "skills/top-gainers-feishu/scripts/write.py",
        "skills/up-line/scripts/update.py",
        "skills/watchlist-ma/scripts/query.py",
    }
    live_hits: list[str] = []
    parked_hits: list[str] = []
    for needle in needles:
        out = subprocess.run(
            ["git", "grep", "-l", "-F", needle, "--", "*.py", "*.sh"],
            cwd=ROOT, capture_output=True, text=True,
        ).stdout
        for line in out.splitlines():
            if not line or "tests/" in line or line in allowed:
                continue
            (parked_hits if line.startswith("skills/") else live_hits).append(f"{needle}: {line}")

    assert not live_hits, "飞书凭证读取点已退役，自动链路不得重新引入：" + "; ".join(live_hits)

    unexpected = sorted({h.split(": ", 1)[1] for h in parked_hits} - parked_allowed)
    assert not unexpected, (
        "skills/ 下新增了飞书凭证读取点——封存名单只保留不扩张，"
        "新链路请走 DuckDB：" + "; ".join(unexpected)
    )


def test_daily_update_omits_retired_sector_feishu_module():
    source = (
        ROOT / "market_feature_store" / "sync" / "sync_daily_full.py"
    ).read_text(encoding="utf-8")

    assert "sync_feishu_sector_resonance" not in source
    assert "sync-sector-resonance" not in source
    assert "sync_feishu_market_daily" not in source
    assert "sync-market-daily" not in source


def test_nightly_attempts_l2_before_the_sync_guard():
    """L2 排在同步守卫**之前**：同步失败不连坐 L2。（工单 #51 已做）

    L2（资金流 + 质量门）读逐笔日包，不依赖同步段产物，一次 CDP 掉线不该连带丢掉
    当天的 L2。这条不变量的前身 ``test_nightly_script_attempts_l2_before_sync_failure_exit``
    只钉在 `all)` 分支上，而生产链是 sync plist（走 S7）+ finalize plist 两个独立
    job，`finalize)` 里一直是守卫在前、L2 在后——**生产路径从未满足过它**。代价已经
    发生：`feature_l2_capital_flow_daily` / `feature_l2_quant_orders_daily` 的 max 都
    停在 2026-09-09，9-10 与 9-11 两天的 L2 全丢。`all)` 因绕开 staging 被删除后，
    那条断言连唯一的锚点也没了（见 ``test_nightly_closes_the_staging_bypassing_sync_phases``）。

    现在锚点落在 `finalize)` 这条**生产真路径**上。本测试是结构侧的快速哨兵，行为侧
    由 ``test_nightly_finalize_attempts_l2_even_when_the_sync_guard_fails`` 真跑脚本
    验证（假执行器记录 L2 到底有没有被调用）。两条都在，别只留一条。
    """
    script = (
        ROOT / "skills" / "daily-full-review" / "scripts" / "nightly_full_review.sh"
    ).read_text(encoding="utf-8")
    finalize = script.index("\n  finalize)")
    end = script.index("\nesac", finalize)
    body = script[finalize:end]

    # 1. L2 还在被调用——别在收拾旁路时把它整个弄丢。
    assert "run_l2_branch" in body

    # 2. 顺序：L2 在前、同步守卫在后。
    guard = body.index("$REVIEW_CHECKER")
    l2 = body.index("run_l2_branch")
    assert l2 < guard, (
        "同步守卫又排到 L2 之前了——同步一失败就会连坐掉当天的 L2（9-10/9-11 就是这么丢的）"
    )

    # 3. 生成段仍然严格守门：守卫非 0 就不许走到 run_generation_and_finalize。
    #    L2 提前不等于放宽生成段，这两件事必须分开。
    assert "run_generation_and_finalize" in body
    gen = body.index("run_generation_and_finalize")
    assert guard < gen, "生成段跑到同步守卫之前了"

    # 4. `all)` 分支必须保持消失（它绕开 staging）。
    assert "\n  all)" not in script


def test_market_dependent_tables_are_excluded_from_row_anomaly_checks() -> None:
    """随行情波动的表不做行数收缩检查，但断档检查保留。

    回归：三张 fact_mainline_* 统计的是「当日有几条主线、主线里有几只股」，本身
    随行情变化。近 29 个交易日实测 theme 2~7（3.5x）、stock 30~163（5.4x）、
    sector 5~15（3.0x），对照恒定表 fact_sw_l1_daily 与
    fact_sector_period_rank_daily 均为 1.0x。

    后果不是少报一个告警：跨日门禁 FAIL 会让夜间管线其后 16 步全部 SKIP，包括
    theme-candidates / agent-daily / 策略矩阵 / cockpit。2026-07-29 主线只有 3 条
    题材 53 只股，重跑同步仍是 53 且报 complete——数据完整，行情就是那么窄。
    行情越窄，题材层被掐得越死，而那正是最需要它的时候。
    """
    from market_feature_store.quality import GAP_TABLES, ROW_ANOMALY_TABLES

    for table in (
        "fact_mainline_theme_daily",
        "fact_mainline_stock_daily",
        "fact_mainline_sector_daily",
    ):
        assert table not in ROW_ANOMALY_TABLES
        assert table in GAP_TABLES


def test_constant_universe_tables_keep_row_anomaly_checks() -> None:
    """宇宙规模恒定的表必须保留行数收缩检查，这条门禁不能整体失效。"""
    from market_feature_store.quality import ROW_ANOMALY_TABLES

    for table in (
        "fact_sector_daily",
        "fact_sw_l1_daily",
        "fact_sector_stock_daily",
        "fact_stock_daily",
        "fact_sector_period_rank_daily",
    ):
        assert table in ROW_ANOMALY_TABLES

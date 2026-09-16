import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
MONEYFLOW_DIR = ROOT / "scripts" / "moneyflow"


def _load_module(monkeypatch, name, filename):
    monkeypatch.syspath_prepend(str(MONEYFLOW_DIR))
    monkeypatch.delitem(sys.modules, "config", raising=False)
    spec = importlib.util.spec_from_file_location(name, MONEYFLOW_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return self.rows

    def disconnect(self):
        return None


@pytest.mark.parametrize(
    ("code", "table", "time_column", "type_filter"),
    [
        ("600000", "share.ngts_tick", "TickTime", "TickType"),
        ("000001", "share.trans", "TradeTime", "ExecType"),
    ],
)
def test_server_queries_use_prewhere(
    monkeypatch, code, table, time_column, type_filter
):
    module = _load_module(
        monkeypatch, f"server_aggregation_{code}", "server_aggregation.py"
    )

    capital_sql = module.build_capital_flow_query(code)
    buyer_sql = module.build_buyer_order_query(code)

    for sql in (capital_sql, buyer_sql):
        assert f"FROM {table}" in sql
        assert "PREWHERE TradeDate = %(date)s AND SecurityID = %(code)s" in sql
        assert time_column in sql
        assert type_filter in sql
    assert "sum(amount) OVER (PARTITION BY buy_no)" in capital_sql
    assert "sum(amount) OVER (PARTITION BY sell_no)" in capital_sql
    assert "GROUP BY buy_no" in buyer_sql
    assert "HAVING order_amount >= %(threshold)s" in buyer_sql


def test_same_day_symbol_capital_flow_uses_shared_cache(tmp_path, monkeypatch):
    module = _load_module(
        monkeypatch, "server_aggregation_shared_cache", "server_aggregation.py"
    )
    cache_path = tmp_path / "l2-cache.json"
    client = FakeClient([(12, 10.0, 11.0, 1_500_000.0, 2_000_000.0)])
    cache = module.SharedQueryCache(cache_path)
    service = module.L2QueryService(
        "2026-07-15", 50.0, lambda: client, cache=cache, retries=1
    )

    _, first = service.capital_flow(client, "600000")
    reloaded = module.L2QueryService(
        "2026-07-15",
        50.0,
        lambda: client,
        cache=module.SharedQueryCache(cache_path),
        retries=1,
    )
    _, second = reloaded.capital_flow(client, "600000")

    assert first == second
    assert first.active_net_wan == 150.0
    assert first.total_net_wan == 200.0
    assert first.change_pct == pytest.approx(10.0)
    assert len(client.calls) == 1
    assert reloaded.cache_stats()["hits"] == 1
    assert reloaded.cache_stats()["entries"] == 1
    assert reloaded.cache_stats()["queries"] == 0


def test_canonical_pct_chg_overrides_intraday_on_read_side(tmp_path, monkeypatch):
    """2026-09-13 QC E3：当日涨幅%以日线口径（收盘/前收）为准，读出侧统一覆盖。

    - 传了覆盖表：返回值用日线口径，不是逐笔的末笔/首笔；
    - 覆盖表缺该代码：None，不拿日内口径冒充日线；
    - 磁盘缓存里的旧口径条目命中时同样被纠正（覆盖在读出侧，无需清缓存）；
    - 不传覆盖表：兼容旧行为。
    """
    module = _load_module(
        monkeypatch, "server_aggregation_canonical_pct", "server_aggregation.py"
    )
    cache_path = tmp_path / "l2-cache.json"
    rows = [(12, 10.0, 11.0, 1_500_000.0, 2_000_000.0)]  # 日内末笔/首笔 = +10%

    legacy = module.L2QueryService(
        "2026-07-15",
        50.0,
        lambda: FakeClient(list(rows)),
        cache=module.SharedQueryCache(cache_path),
        retries=1,
    )
    _, seeded = legacy.capital_flow(FakeClient(list(rows)), "600000")
    assert seeded.change_pct == pytest.approx(10.0)

    service = module.L2QueryService(
        "2026-07-15",
        50.0,
        lambda: FakeClient(list(rows)),
        cache=module.SharedQueryCache(cache_path),
        retries=1,
        pct_chg_by_code={"600000": 3.5},
    )
    _, covered = service.capital_flow(FakeClient(list(rows)), "600000")
    assert covered.change_pct == pytest.approx(3.5)
    assert covered.active_net_wan == 150.0  # 净额不受覆盖影响

    _, missing = service.capital_flow(FakeClient(list(rows)), "000001")
    assert missing.change_pct is None

    plain = module.L2QueryService(
        "2026-07-15",
        50.0,
        lambda: FakeClient(list(rows)),
        cache=module.SharedQueryCache(tmp_path / "other.json"),
        retries=1,
    )
    _, raw = plain.capital_flow(FakeClient(list(rows)), "600000")
    assert raw.change_pct == pytest.approx(10.0)


def test_default_shared_cache_uses_moneyflow_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEYFLOW_OUTPUT_DIR", str(tmp_path))
    module = _load_module(
        monkeypatch, "server_aggregation_output_dir", "server_aggregation.py"
    )
    service = module.L2QueryService(
        "2026-07-15", 50.0, lambda: FakeClient([]), retries=1
    )

    assert service.cache_stats()["path"] == str(
        tmp_path / "l2_query_cache_2026-07-15.json"
    )


def test_legacy_null_capital_cache_is_treated_as_miss(tmp_path, monkeypatch):
    module = _load_module(
        monkeypatch, "server_aggregation_null_cache", "server_aggregation.py"
    )
    path = tmp_path / "l2_query_cache_2026-07-15.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": {"capital:2026-07-15:000001:500000": None},
            }
        ),
        encoding="utf-8",
    )
    client = FakeClient([(8, 10.0, 11.0, 1_500_000.0, 2_000_000.0)])
    service = module.L2QueryService(
        "2026-07-15",
        50.0,
        lambda: FakeClient([]),
        cache=module.SharedQueryCache(path),
        retries=1,
    )

    _, summary = service.capital_flow(client, "000001")

    assert summary is not None
    assert len(client.calls) == 1
    assert service.cache_stats()["misses"] == 1
    assert service.cache_stats()["queries"] == 1
    assert service.cache_stats()["writes"] == 1


def test_scan_checkpoint_counts_only_initial_current_candidates(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEYFLOW_OUTPUT_DIR", str(tmp_path))
    clickhouse = ModuleType("clickhouse_driver")
    clickhouse.Client = object
    matplotlib = ModuleType("matplotlib")
    matplotlib.__path__ = []
    matplotlib.use = lambda _backend: None
    pyplot = ModuleType("matplotlib.pyplot")
    pyplot.rcParams = {}
    dates = ModuleType("matplotlib.dates")
    matplotlib.pyplot = pyplot
    matplotlib.dates = dates
    monkeypatch.setitem(sys.modules, "clickhouse_driver", clickhouse)
    monkeypatch.setitem(sys.modules, "matplotlib", matplotlib)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", pyplot)
    monkeypatch.setitem(sys.modules, "matplotlib.dates", dates)
    monkeypatch.setitem(sys.modules, "pandas", ModuleType("pandas"))
    module = _load_module(monkeypatch, "moneyflow_scan_checkpoint", "moneyflow.py")
    module.AdaptiveThrottle.wait = lambda self: None
    path = tmp_path / "scan_cache_test_2026-07-15.json"
    path.write_text(
        json.dumps(
            {
                "000001": {"code": "000001"},
                "600000": {"code": "600000"},
                "300001": None,
            }
        ),
        encoding="utf-8",
    )

    def compute(client, code):
        return client, {"code": code}

    _, rows, stats = module.run_scan(
        FakeClient([]),
        ["000001", "000002"],
        "2026-07-15",
        "test",
        compute,
        passes=1,
        batch_size=0,
        batch_rest=0,
    )

    assert stats["scan_cache_hits"] == 1
    assert stats["nonempty_count"] == 2
    assert {row["code"] for row in rows} == {"000001", "000002"}
    assert set(json.loads(path.read_text(encoding="utf-8"))) == {
        "000001",
        "000002",
    }


def test_buyer_order_cache_round_trips_aggregated_rows(tmp_path, monkeypatch):
    module = _load_module(
        monkeypatch, "server_aggregation_buyer_cache", "server_aggregation.py"
    )
    cache_path = tmp_path / "l2-cache.json"
    rows = [
        (datetime(2026, 7, 15, 10, 0), 2_500_000.0),
        (datetime(2026, 7, 15, 10, 5), 2_510_000.0),
    ]
    client = FakeClient(rows)
    service = module.L2QueryService(
        "2026-07-15",
        50.0,
        lambda: client,
        cache=module.SharedQueryCache(cache_path),
        retries=1,
    )

    _, first = service.buyer_orders(client, "000001")
    reloaded = module.L2QueryService(
        "2026-07-15",
        50.0,
        lambda: client,
        cache=module.SharedQueryCache(cache_path),
        retries=1,
    )
    _, second = reloaded.buyer_orders(client, "000001")

    assert first == second
    assert first[0] == ("2026-07-15T10:00:00", 2_500_000.0)
    assert len(client.calls) == 1


def test_mark_calendar_ledgers_verdict(tmp_path, monkeypatch):
    """2026-09-13 QC S2：日历判定（含 unknown）写 ops_pipeline_run_daily 的
    calendar 步，不再只在 stderr 吼一声；message 记判定来源与理由。"""
    import market_feature_store.db as mfs_db

    monkeypatch.setattr(mfs_db, "DB_PATH", tmp_path / "t.duckdb")
    monkeypatch.setattr(mfs_db, "DB_DIR", tmp_path)
    writer = _load_module(
        monkeypatch, "moneyflow_writer_calendar", "write_to_duckdb.py"
    )

    writer.mark_calendar("2026-09-11", "unknown", "probe_failed_rc=1", "boom")

    import duckdb

    con = duckdb.connect(str(tmp_path / "t.duckdb"), read_only=True)
    try:
        row = con.execute(
            "SELECT step, status, message FROM ops_pipeline_run_daily "
            "WHERE trade_date='2026-09-11' AND pipeline='l2-moneyflow'"
        ).fetchone()
    finally:
        con.close()
    assert row is not None
    assert row[0] == "calendar" and row[1] == "unknown"
    assert "probe_failed_rc=1" in row[2] and "boom" in row[2]


def test_failed_scan_stats_cannot_pass_completion_gate(monkeypatch):
    writer = _load_module(monkeypatch, "moneyflow_writer_stats", "write_to_duckdb.py")
    stats = {
        "input_count": 2,
        "processed_count": 1,
        "failed_count": 1,
    }

    assert writer._stats_problem(stats) == "failed_count=1"


def test_l2_status_message_includes_shared_cache_stats(monkeypatch):
    writer = _load_module(
        monkeypatch, "moneyflow_writer_cache_stats", "write_to_duckdb.py"
    )
    stats = {
        "nonempty_count": 3,
        "empty_count": 2,
        "shared_cache": {
            "hits": 4,
            "misses": 5,
            "queries": 5,
            "writes": 6,
            "entries": 7,
            "path": "/tmp/l2_query_cache_2026-07-15.json",
        },
    }

    message = writer._format_message(None, stats)

    assert "shared_cache hits=4 misses=5 queries=5 writes=6 entries=7" in message
    assert "nonempty=3 empty=2" in message


def test_repair_pct_chg_backfills_daily_caliber_and_nulls_missing(tmp_path, monkeypatch):
    """2026-09-13 QC E3 旧窗口收口：pct_change 从 fact_stock_daily 直填日线口径，
    缺日线的行置 NULL 不冒充，台账 step='repair_pct_chg' 记更新/置空数。"""
    import market_feature_store.db as mfs_db

    monkeypatch.setattr(mfs_db, "DB_PATH", tmp_path / "t.duckdb")
    monkeypatch.setattr(mfs_db, "DB_DIR", tmp_path)
    writer = _load_module(
        monkeypatch, "moneyflow_writer_repair_pct", "write_to_duckdb.py"
    )

    import duckdb

    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    writer.init_db(con)
    con.execute(
        "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, "
        "close, pre_close, pct_chg, amount, turnover, source, updated_at) VALUES "
        "('2026-07-15','000001.SZ','平安银行',10.0,9.85,1.5,1e8,2.0,'test',CURRENT_TIMESTAMP)"
    )
    con.execute(
        "INSERT INTO feature_l2_capital_flow_daily VALUES "
        "('2026-07-15','top100','000001','000001.SZ','平安银行',"
        "100.0,120.0,500.0,0.02,9.99,100.0,1,NULL,'test',CURRENT_TIMESTAMP),"
        "('2026-07-15','top100','000002','000002.SZ','万科A',"
        "200.0,210.0,800.0,0.03,-8.88,50.0,2,NULL,'test',CURRENT_TIMESTAMP)"
    )
    con.execute(
        "INSERT INTO feature_l2_quant_orders_daily VALUES "
        "('2026-07-15','000001','000001.SZ','平安银行',"
        "300.0,25.0,3,40,'850万x20笔',9.99,200.0,100.0,1,'test',CURRENT_TIMESTAMP),"
        "('2026-07-15','000002','000002.SZ','万科A',"
        "150.0,15.0,2,30,'500万x15笔',-8.88,200.0,50.0,2,'test',CURRENT_TIMESTAMP)"
    )
    con.close()

    msg = writer.repair_pct_chg("2026-07-15")

    con = duckdb.connect(str(tmp_path / "t.duckdb"), read_only=True)
    try:
        rows = con.execute(
            "SELECT stock_code, pct_change FROM feature_l2_capital_flow_daily "
            "WHERE trade_date='2026-07-15' ORDER BY stock_code"
        ).fetchall()
        qrows = con.execute(
            "SELECT stock_code, pct_change FROM feature_l2_quant_orders_daily "
            "WHERE trade_date='2026-07-15' ORDER BY stock_code"
        ).fetchall()
        ledger = con.execute(
            "SELECT status, message FROM ops_pipeline_run_daily "
            "WHERE trade_date='2026-07-15' AND pipeline='l2-moneyflow' "
            "AND step='repair_pct_chg'"
        ).fetchone()
    finally:
        con.close()

    assert rows == [("000001", 1.5), ("000002", None)]
    assert qrows == [("000001", 1.5), ("000002", None)]
    assert ledger is not None and ledger[0] == "complete"
    # 新分母格式（二轮 QC 返修）：行数与代码数拆开
    assert "matched_rows=1" in ledger[1] and "null_rows=1" in ledger[1]
    assert "target_rows=2" in ledger[1] and "distinct_codes=2" in ledger[1]
    assert "000002" in ledger[1]
    assert "capital" in msg


def test_repair_pct_chg_refuses_nonexistent_db(tmp_path, monkeypatch):
    """二轮 QC P2-1：库路径指向不存在位置时必须报错，不得新建空库报 complete。"""
    import market_feature_store.db as mfs_db

    ghost = tmp_path / "nope.duckdb"
    monkeypatch.setattr(mfs_db, "DB_PATH", ghost)
    monkeypatch.setattr(mfs_db, "DB_DIR", tmp_path)
    writer = _load_module(
        monkeypatch, "moneyflow_writer_repair_ghost", "write_to_duckdb.py"
    )

    with pytest.raises(FileNotFoundError, match="目标库不存在"):
        writer.repair_pct_chg("2026-07-15")
    assert not ghost.exists(), "repair 不得新建空库"


def test_repair_pct_chg_noop_on_zero_target(tmp_path, monkeypatch):
    """二轮 QC P2-1b：库存在但当日两表无目标行——标 noop 不标 complete。"""
    import market_feature_store.db as mfs_db

    monkeypatch.setattr(mfs_db, "DB_PATH", tmp_path / "t.duckdb")
    monkeypatch.setattr(mfs_db, "DB_DIR", tmp_path)
    writer = _load_module(
        monkeypatch, "moneyflow_writer_repair_noop", "write_to_duckdb.py"
    )

    import duckdb

    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    writer.init_db(con)
    con.close()

    assert writer.repair_pct_chg("2026-07-15") == "noop"

    con = duckdb.connect(str(tmp_path / "t.duckdb"), read_only=True)
    try:
        row = con.execute(
            "SELECT status FROM ops_pipeline_run_daily "
            "WHERE trade_date='2026-07-15' AND pipeline='l2-moneyflow' "
            "AND step='repair_pct_chg'"
        ).fetchone()
    finally:
        con.close()
    assert row is not None and row[0] == "noop"


def test_repair_pct_chg_counts_rows_across_scan_types(tmp_path, monkeypatch):
    """二轮 QC P2-2：同一代码同时上两个榜单占两行——matched_rows 记行数（2），
    distinct_codes 记代码数（1），不再混淆。"""
    import market_feature_store.db as mfs_db

    monkeypatch.setattr(mfs_db, "DB_PATH", tmp_path / "t.duckdb")
    monkeypatch.setattr(mfs_db, "DB_DIR", tmp_path)
    writer = _load_module(
        monkeypatch, "moneyflow_writer_repair_rows", "write_to_duckdb.py"
    )

    import duckdb

    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    writer.init_db(con)
    con.execute(
        "INSERT INTO fact_stock_daily (trade_date, stock_ts_code, stock_name, "
        "close, pre_close, pct_chg, amount, turnover, source, updated_at) VALUES "
        "('2026-07-15','000001.SZ','平安银行',10.0,9.85,1.5,1e8,2.0,'test',CURRENT_TIMESTAMP)"
    )
    for scan in ("limitup", "top100"):
        con.execute(
            "INSERT INTO feature_l2_capital_flow_daily VALUES "
            f"('2026-07-15','{scan}','000001','000001.SZ','平安银行',"
            "100.0,120.0,500.0,0.02,9.99,100.0,1,NULL,'test',CURRENT_TIMESTAMP)"
        )
    con.close()

    writer.repair_pct_chg("2026-07-15")

    con = duckdb.connect(str(tmp_path / "t.duckdb"), read_only=True)
    try:
        msg = con.execute(
            "SELECT message FROM ops_pipeline_run_daily "
            "WHERE trade_date='2026-07-15' AND step='repair_pct_chg'"
        ).fetchone()[0]
        vals = con.execute(
            "SELECT DISTINCT pct_change FROM feature_l2_capital_flow_daily "
            "WHERE trade_date='2026-07-15'"
        ).fetchall()
    finally:
        con.close()
    assert "target_rows=2" in msg
    assert "distinct_codes=1" in msg
    assert "matched_rows=2" in msg and "null_rows=0" in msg
    assert vals == [(1.5,)]


def test_repair_pct_chg_missing_detail_not_truncated(tmp_path, monkeypatch):
    """二轮 QC P2-3：21 个缺日线代码全部置 NULL，台账带明细文件指针，
    文件里有全部 21 个代码（不截断）。"""
    import market_feature_store.db as mfs_db

    monkeypatch.setattr(mfs_db, "DB_PATH", tmp_path / "t.duckdb")
    monkeypatch.setattr(mfs_db, "DB_DIR", tmp_path)
    monkeypatch.setenv("L2_REPAIR_DETAIL_DIR", str(tmp_path / "detail"))
    writer = _load_module(
        monkeypatch, "moneyflow_writer_repair_trunc", "write_to_duckdb.py"
    )

    import duckdb

    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    writer.init_db(con)
    codes = [f"600{i:03d}" for i in range(21)]
    for code in codes:
        con.execute(
            "INSERT INTO feature_l2_capital_flow_daily VALUES "
            f"('2026-07-15','top100','{code}','{code}.XSHG','测试股',"
            "100.0,120.0,500.0,0.02,9.99,100.0,1,NULL,'test',CURRENT_TIMESTAMP)"
        )
    con.close()

    msg = writer.repair_pct_chg("2026-07-15")

    con = duckdb.connect(str(tmp_path / "t.duckdb"), read_only=True)
    try:
        nulls = con.execute(
            "SELECT COUNT(*) FROM feature_l2_capital_flow_daily "
            "WHERE trade_date='2026-07-15' AND pct_change IS NULL"
        ).fetchone()[0]
    finally:
        con.close()
    assert nulls == 21
    assert "(+1 more, full=" in msg
    detail_file = tmp_path / "detail" / "2026-07-15.txt"
    assert detail_file.is_file()
    saved = detail_file.read_text(encoding="utf-8").split()
    assert saved == codes, "明细文件必须含全部 21 个代码"
    assert codes[-1] not in msg.split("full=")[0], "第 21 个代码不应出现在台账内联段"

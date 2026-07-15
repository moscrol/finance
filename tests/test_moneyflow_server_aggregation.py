import importlib.util
import sys
from datetime import datetime
from pathlib import Path

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


def test_failed_scan_stats_cannot_pass_completion_gate(monkeypatch):
    writer = _load_module(monkeypatch, "moneyflow_writer_stats", "write_to_duckdb.py")
    stats = {
        "input_count": 2,
        "processed_count": 1,
        "failed_count": 1,
    }

    assert writer._stats_problem(stats) == "failed_count=1"

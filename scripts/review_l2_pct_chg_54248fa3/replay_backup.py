"""Replay supplied pre-repair pct values against read-only source rows in a temp DB.

Production is opened read_only=True once. All repair calls target TemporaryDirectory.
Tests exact row values and every non-pct column, not just counts; no network calls.
"""
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile

import duckdb

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
import market_feature_store.db as db  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts/moneyflow"))
spec = importlib.util.spec_from_file_location("writer_replay", ROOT / "scripts/moneyflow/write_to_duckdb.py")
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)
repair_root = Path.home() / ".finance-runtime/db-repair/l2-pct-chg-20260913"
receipt = json.loads((repair_root / "repair-receipt.json").read_text())
with Path(receipt["backup"]["path"]).open(newline="") as stream:
    backup = list(csv.DictReader(stream))
tables = ("feature_l2_capital_flow_daily", "feature_l2_quant_orders_daily")
expected = {}
columns = {}
with duckdb.connect(receipt["db"], read_only=True) as source:
    for table in tables:
        cursor = source.execute(f"SELECT * FROM {table} WHERE trade_date < '2026-08-27' ORDER BY ALL")
        columns[table] = [c[0] for c in cursor.description]
        expected[table] = cursor.fetchall()
    daily = source.execute("""
        SELECT trade_date, stock_ts_code, pct_chg FROM fact_stock_daily d
        WHERE EXISTS (SELECT 1 FROM feature_l2_capital_flow_daily l
            WHERE l.trade_date < '2026-08-27' AND l.trade_date=d.trade_date
              AND l.stock_code=substr(d.stock_ts_code,1,6))
           OR EXISTS (SELECT 1 FROM feature_l2_quant_orders_daily l
            WHERE l.trade_date < '2026-08-27' AND l.trade_date=d.trade_date
              AND l.stock_code=substr(d.stock_ts_code,1,6))
        ORDER BY ALL
    """).fetchall()


def state(path):
    with duckdb.connect(str(path), read_only=True) as con:
        return {t: con.execute(f"SELECT * FROM {t} ORDER BY ALL").fetchall() for t in tables}


def digest(value):
    return hashlib.sha256(json.dumps(value, default=str, ensure_ascii=False).encode()).hexdigest()


with tempfile.TemporaryDirectory(prefix="l2-qc-replay-") as temp:
    db.DB_PATH = Path(temp) / "replay.duckdb"
    db.DB_DIR = Path(temp)
    original_pct = {(r["table"], r["trade_date"], r["scan_type"], r["stock_code"]):
                    (float(r["pct_change"]) if r["pct_change"] else None) for r in backup}
    with duckdb.connect(str(db.DB_PATH)) as con:
        writer.init_db(con)
        con.executemany("INSERT INTO fact_stock_daily (trade_date,stock_ts_code,pct_chg) VALUES (?,?,?)", daily)
        for table in tables:
            names = columns[table]
            restored = []
            for row in expected[table]:
                r = dict(zip(names, row))
                key = (table, str(r["trade_date"]), r.get("scan_type", ""), r["stock_code"])
                r["pct_change"] = original_pct[key]
                restored.append(tuple(r[n] for n in names))
            con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in names)})", restored)
    before = state(db.DB_PATH)
    dates = sorted({r["trade_date"] for r in backup})
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        for date in dates:
            writer.repair_pct_chg(date)
    first = state(db.DB_PATH)
    assert first == expected, "Replay differs from current canonical rows"
    with contextlib.redirect_stdout(capture):
        for date in dates:
            writer.repair_pct_chg(date)
    second = state(db.DB_PATH)
    assert second == first, "Second run changed feature rows"
    for table in tables:
        pct_index = columns[table].index("pct_change")
        def strip_pct(values):
            return [tuple(v for i, v in enumerate(row) if i != pct_index) for row in values]

        assert strip_pct(before[table]) == strip_pct(first[table])
    output = {"days_each_run": len(dates), "feature_rows": sum(map(len, first.values())),
              "replay_equals_current_canonical_all_columns": first == expected,
              "all_non_pct_columns_unchanged": True,
              "idempotent_feature_rows": first == second,
              "hash_definition": "sha256(json.dumps(dict(table -> SELECT * ORDER BY ALL), default=str, ensure_ascii=False).encode())",
              "first_hash": digest(first), "second_hash": digest(second),
              "production_access": "read_only; no repair calls against production"}
print(json.dumps(output, ensure_ascii=False, indent=2))

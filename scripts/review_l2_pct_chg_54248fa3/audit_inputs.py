"""Read-only audit of the supplied L2 repair receipt, backup, and canonical DB.

No repair execution, initialization, or write connection is permitted here.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import subprocess

import duckdb

HOME = Path.home()
RUNTIME = HOME / ".finance-runtime"
REPAIR = RUNTIME / "db-repair/l2-pct-chg-20260913"
receipt = json.loads((REPAIR / "repair-receipt.json").read_text())
backup = Path(receipt["backup"]["path"])
with backup.open(newline="") as stream:
    rows = list(csv.DictReader(stream))
counts = Counter(row["table"] for row in rows)
output = {
    "receipt_sha256": hashlib.sha256((REPAIR / "repair-receipt.json").read_bytes()).hexdigest(),
    "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
    "backup_sha256_matches": hashlib.sha256(backup.read_bytes()).hexdigest() == receipt["backup"]["sha256"],
    "backup_rows": len(rows),
    "backup_counts": dict(counts),
    "backup_days": len({row["trade_date"] for row in rows}),
    "receipt_days": len(receipt["days"]),
    "receipt_counts_reconcile": {},
    "data": {},
    "test_receipts": [],
}
for key, table in (("capital_flow", "feature_l2_capital_flow_daily"),
                   ("quant", "feature_l2_quant_orders_daily")):
    total = sum(day[key]["updated"] + day[key]["null"] for day in receipt["days"])
    distinct = len({(r["trade_date"], r["stock_code"]) for r in rows if r["table"] == table})
    output["receipt_counts_reconcile"][key] = {
        "updated_plus_null": total,
        "actual_backup_rows": counts[table],
        "distinct_date_code_pairs": distinct,
        "row_gap": counts[table] - total,
    }

with duckdb.connect(receipt["db"], read_only=True) as con:
    for table in counts:
        qc = con.execute(f"""
            SELECT count(*), count(DISTINCT l.trade_date),
                   count(*) FILTER(WHERE l.pct_change IS NULL),
                   count(*) FILTER(WHERE l.pct_change IS DISTINCT FROM d.pct_chg),
                   count(*) FILTER(WHERE l.pct_change * d.pct_chg < 0)
            FROM {table} l LEFT JOIN fact_stock_daily d
              ON l.trade_date=d.trade_date AND l.stock_code=substr(d.stock_ts_code,1,6)
            WHERE l.trade_date < DATE '2026-08-27'
        """).fetchone()
        nulls = con.execute(f"""
            SELECT trade_date, stock_code FROM {table}
            WHERE trade_date < DATE '2026-08-27' AND pct_change IS NULL
            ORDER BY ALL
        """).fetchall()
        output["data"][table] = dict(zip(("rows", "days", "nulls", "mismatches_null_safe", "opposite_signs"), qc))
        output["data"][table]["null_keys"] = nulls
        key_cols = "trade_date, scan_type, stock_code" if "capital" in table else "trade_date, stock_code"
        actual_keys = {tuple(str(v) for v in r) for r in con.execute(
            f"SELECT {key_cols} FROM {table} WHERE trade_date < DATE '2026-08-27'"
        ).fetchall()}
        cols = key_cols.split(", ")
        backup_keys = {tuple(r[c] for c in cols) for r in rows if r["table"] == table}
        output["data"][table]["primary_key_sets_equal_backup"] = actual_keys == backup_keys
    ledger = con.execute("""
        SELECT trade_date, status, message FROM ops_pipeline_run_daily
        WHERE pipeline='l2-moneyflow' AND step='repair_pct_chg'
          AND trade_date < DATE '2026-08-27' ORDER BY trade_date
    """).fetchall()
    output["ledger"] = {"days": len(ledger), "statuses": dict(Counter(r[1] for r in ledger)),
                        "null_day": [r for r in ledger if str(r[0]) == "2026-06-24"]}

for filename in ("20260913T082354Z-f59ab082.json", "20260913T085357Z-2188a711.json",
                 "20260913T094228Z-e40f22b8.json", "20260913T101411Z-ecc404da.json"):
    path = RUNTIME / "test-receipts" / filename
    r = json.loads(path.read_text())
    fields = ("revision", "tree", "interpreter", "python_version", "dependency_fingerprint",
              "target", "counts", "dirty", "dirty_paths", "worktree_dirty_total", "exit_status")
    output["test_receipts"].append({"path": str(path), **{k: r.get(k) for k in fields}})

output["refs_at_audit"] = subprocess.check_output(
    ["git", "rev-parse", "HEAD", "gitea/main", "gitea/fix/l2-pct-chg-backfill-0913"], text=True
).splitlines()
print(json.dumps(output, ensure_ascii=False, default=str, indent=2))

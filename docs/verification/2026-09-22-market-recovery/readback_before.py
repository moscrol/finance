"""Read-only freshness readback of every dated fact_* table (workorder #61 step 1). No writes.

usage: readback_before.py <duckdb path> <output json (must not exist)>
"""
import json
import os
import sys
import time

import duckdb

db = sys.argv[1]
out = sys.argv[2]
st = os.stat(db)
con = duckdb.connect(db, read_only=True)
tables = [r[0] for r in con.execute("""
  select table_name from information_schema.columns
  where table_schema='main' and column_name='trade_date' and table_name like 'fact_%'
  group by table_name order by table_name""").fetchall()]
kinds = dict(con.execute(
    "select table_name, table_type from information_schema.tables where table_schema='main'"
).fetchall())
rows = {}
for t in tables:
    q = f"""select cast(max(trade_date) as varchar),
                   count(*) filter (where trade_date = date '2026-09-21'),
                   count(*) filter (where trade_date = date '2026-09-22'),
                   count(*) filter (where trade_date = date '2026-09-18')
            from {t}"""
    mx, c21, c22, c18 = con.execute(q).fetchone()
    rows[t] = {"type": kinds.get(t), "max_trade_date": mx, "rows_0921": c21, "rows_0922": c22, "rows_0918": c18}
extra = {}
for t in ("fact_market_daily", "fact_stock_daily"):
    if t in rows:
        extra[t] = [
            list(map(str, r))
            for r in con.execute(
                f"select trade_date, coalesce(source,'?') s, count(*) from {t} "
                "where trade_date >= date '2026-09-17' group by 1,2 order by 1,2"
            ).fetchall()
        ]
con.close()
res = {
    "db": db,
    "db_size": st.st_size,
    "db_mtime": time.strftime("%FT%T%z", time.localtime(st.st_mtime)),
    "read_at": time.strftime("%FT%TZ", time.gmtime()),
    "read_only": True,
    "n_tables": len(rows),
    "tables": rows,
    "recent_source_rows": extra,
}
json.dump(res, open(out, "x"), ensure_ascii=False, indent=1)
print(json.dumps({"n_tables": len(rows), "out": out}, ensure_ascii=False))
for t, r in sorted(rows.items(), key=lambda kv: kv[1]["max_trade_date"] or ""):
    print(f"{r['max_trade_date']}  {t:40s} 0918={r['rows_0918']:>6} 0921={r['rows_0921']:>6} 0922={r['rows_0922']:>6} {r['type']}")

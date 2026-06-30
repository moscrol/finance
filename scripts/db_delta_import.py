#!/usr/bin/env python3
"""把 db_delta_export.py 导出的单日增量 zip 幂等合并进本地 DuckDB。

用途：另一台电脑收到当天的 mfs-delta-<date>.zip 后，跑这个脚本就把当天的 fact 行
合并进它本地的 market_feature_store.duckdb，之后所有复盘/查询 skill 都能看到今天的数据。

幂等原理：对每张表，先 `DELETE WHERE trade_date = 当天` 再 `INSERT`，所以同一个包
重复导多次结果一致，不会重复累加。整个过程包在一个事务里，要么全成要么全不动。

技术选型 / 替代方案对比（教学）：
- `INSERT INTO t BY NAME SELECT * FROM read_parquet(...)`：`BY NAME` 按列名对齐，
  两边列顺序不同也不会错位（比按位置 INSERT 稳）；前提是目标表已存在同名 schema。
- delete+insert vs `INSERT OR REPLACE`/MERGE：DuckDB 的 upsert 依赖主键约束，而这些
  fact 表大多没声明主键，所以用「按分区键 delete 再 insert」最稳、最好懂，也天然幂等。
- 要求目标库已有表结构：单日增量不负责建表/迁移 schema。第一次在新机器上，应先用整库
  快照（db_delta_export 的整库 zip / EXPORT DATABASE）建好底库，之后再每天打增量。

可复用知识点：分区表的增量同步普遍用「同一分区先删后插 + 事务」保证幂等，离线数仓、
特征平台、报表库都这么做。
"""
from __future__ import annotations
import argparse, json, os, sys, tempfile, zipfile
import duckdb


def main() -> int:
    ap = argparse.ArgumentParser(description="把单日增量 zip 合并进本地 DuckDB（幂等）")
    ap.add_argument("--zip", required=True, help="db_delta_export.py 产出的 zip")
    ap.add_argument("--db", default="db/market_feature_store.duckdb")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要做的操作，不写库")
    a = ap.parse_args()

    if not os.path.exists(a.zip):
        print(f"[err] zip 不存在: {a.zip}", file=sys.stderr); return 2
    if not os.path.exists(a.db):
        print(f"[err] 目标 DB 不存在: {a.db}（请先用整库快照建底库）", file=sys.stderr); return 2

    tmp = tempfile.mkdtemp(prefix="mfs-delta-")
    with zipfile.ZipFile(a.zip) as z:
        z.extractall(tmp)
    with open(os.path.join(tmp, "manifest.json")) as f:
        man = json.load(f)
    date = man["trade_date"]
    print(f"[*] 增量日期 {date}，{len(man['tables'])} 张表，目标库 {a.db}"
          + ("  (dry-run)" if a.dry_run else ""))

    con = duckdb.connect(a.db, read_only=a.dry_run)
    existing = {r[0] for r in con.execute(
        "select table_name from information_schema.tables where table_schema='main'").fetchall()}

    if not a.dry_run:
        con.execute("begin transaction")
    applied = 0
    try:
        for item in man["tables"]:
            t, dc, rows = item["table"], item["date_col"], item["rows"]
            pq = os.path.join(tmp, item["file"])
            if t not in existing:
                print(f"  [skip] 目标库无表 {t}（schema 不匹配，先建底库）", file=sys.stderr)
                continue
            before = con.execute('select count(*) from "%s" where cast("%s" as varchar)=?'
                                 % (t, dc), [date]).fetchone()[0]
            if a.dry_run:
                print(f"  {t:42s} 现有当天 {before} 行 → 将替换为包内 {rows} 行")
                continue
            con.execute('delete from "%s" where cast("%s" as varchar)=?' % (t, dc), [date])
            con.execute("insert into \"%s\" by name select * from read_parquet('%s')" % (t, pq))
            after = con.execute('select count(*) from "%s" where cast("%s" as varchar)=?'
                                % (t, dc), [date]).fetchone()[0]
            print(f"  {t:42s} {before:>8} → {after:>8} 行")
            applied += 1
        if not a.dry_run:
            con.execute("commit")
    except Exception:
        if not a.dry_run:
            con.execute("rollback")
        raise
    finally:
        con.close()
        for fn in os.listdir(tmp):
            os.remove(os.path.join(tmp, fn))
        os.rmdir(tmp)

    if a.dry_run:
        print("[dry-run] 未写库")
    else:
        print(f"\n[ok] 已合并 {applied} 张表的 {date} 增量进 {a.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

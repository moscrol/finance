#!/usr/bin/env python3
"""导出「当日增量」DuckDB 快照到 iCloud（每日增量备份）。

背景 / 选型：
- `market_feature_store.duckdb` 是单个 ~3GB 文件，iCloud 对它没有块级增量，
  每次改动只会整文件重传，慢且耗流量。所以「只同步今天的增量」不能靠同步大文件，
  而是把当日新增的行按 `trade_date` 过滤、单独导出成小 parquet 再同步。
- 每日增量小（几 MB）、快；配合一份全量基线即可还原：
  还原 = 最近一次全量基线 + 其后每日增量按序回放（IMPORT/COPY）。
- 增量只覆盖「按日期新增的行」，对历史行的改删、schema 变更抓不到——那类变化靠
  周期性全量基线兜底（本脚本只管每日增量）。

产物：
  <out-root>/increments/market_feature_store-inc-YYYY-MM-DD.tar.gz
  内含每张有当日数据的 fact/feature 表的 <table>.parquet（zstd 压缩）+ manifest.json。

用法：
  python3 export_increment.py [--date YYYY-MM-DD] [--db PATH] [--out-root DIR] [--keep N]
  --date     默认取库内 fact_market_daily 的最新 trade_date。
  --db       默认 <repo>/db/market_feature_store.duckdb。
  --out-root 默认 <repo>/db/snapshots（iCloud 目的地已于 2026-09-01 退役，
             历史 2026-09-01 及之前的增量仍在 ~/Library/Mobile Documents/
             com~apple~CloudDocs/duckdb-snapshots/）。
  --keep     只保留最近 N 份增量 tar.gz（可选；默认不清理）。

iCloud 退役原因（2026-09-01）：macOS TCC 下手动会话对 iCloud 既有占位文件
「能新建、不能读/改/改名」，当日 rerun 覆盖必 EPERM；且无进程能从会话内
校验 iCloud 副本完整性。备份价值由本地 <repo>/db/snapshots 承接，
全量基线另行另存。
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path

import duckdb

try:
    REPO_ROOT = Path(__file__).resolve().parents[3]
except IndexError:  # 脚本被复制到别处(如 /tmp)测试时, 退回当前目录, 靠 --db 显式指定
    REPO_ROOT = Path.cwd()
DEFAULT_DB = REPO_ROOT / "db" / "market_feature_store.duckdb"
# iCloud 目的地已退役（2026-09-01），默认落仓内本地目录；
# DUCKDB_SNAPSHOT_OUT_ROOT 仍可整体重定向（逃生口）。
DEFAULT_OUT = Path(
    os.environ.get(
        "DUCKDB_SNAPSHOT_OUT_ROOT",
        str(REPO_ROOT / "db" / "snapshots"),
    )
)


def _tables_with_trade_date(con: duckdb.DuckDBPyConnection) -> list[str]:
    names = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='main' ORDER BY 1").fetchall()]
    out = []
    for t in names:
        cols = [c[1] for c in con.execute(f"PRAGMA table_info('{t}')").fetchall()]
        if "trade_date" in cols:
            out.append(t)
    return out


def _resolve_date(con: duckdb.DuckDBPyConnection, date_arg: str | None) -> str:
    if date_arg:
        return date_arg
    row = con.execute("SELECT max(trade_date) FROM fact_market_daily").fetchone()
    if not row or row[0] is None:
        sys.exit("无法从 fact_market_daily 推断最新 trade_date，请用 --date 指定")
    return str(row[0])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--out-root", default=str(DEFAULT_OUT))
    ap.add_argument("--keep", type=int, default=0)
    a = ap.parse_args()

    db_path = Path(a.db)
    if not db_path.exists():
        sys.exit(f"DB 不存在: {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    date = _resolve_date(con, a.date)

    inc_dir = Path(a.out_root) / "increments"
    inc_dir.mkdir(parents=True, exist_ok=True)
    tar_path = inc_dir / f"market_feature_store-inc-{date}.tar.gz"

    manifest = {
        "kind": "daily-increment",
        "date": date,
        "db": str(db_path),
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tables": {},
    }
    exported = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for t in _tables_with_trade_date(con):
            n = con.execute(
                f"SELECT COUNT(*) FROM {t} WHERE trade_date=DATE '{date}'").fetchone()[0]
            if not n:
                continue
            pq = tmp_dir / f"{t}.parquet"
            con.execute(
                f"COPY (SELECT * FROM {t} WHERE trade_date=DATE '{date}') "
                f"TO '{pq}' (FORMAT PARQUET, COMPRESSION zstd)")
            manifest["tables"][t] = {"rows": n, "bytes": pq.stat().st_size}
            exported += n
        con.close()
        if not manifest["tables"]:
            sys.exit(f"{date} 无任何含 trade_date 的表有数据，未导出")
        manifest["total_rows"] = exported
        (tmp_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        with tarfile.open(tar_path, "w:gz") as tar:
            for f in sorted(tmp_dir.iterdir()):
                tar.add(f, arcname=f.name)

    size_mb = tar_path.stat().st_size / 1e6
    print(f"[export-increment] {date}: {len(manifest['tables'])} 表 / {exported} 行 "
          f"-> {tar_path} ({size_mb:.1f} MB)")

    if a.keep and a.keep > 0:
        snaps = sorted(inc_dir.glob("market_feature_store-inc-*.tar.gz"))
        for old in snaps[:-a.keep]:
            old.unlink()
            print(f"[export-increment] 清理旧增量: {old.name}")


if __name__ == "__main__":
    main()

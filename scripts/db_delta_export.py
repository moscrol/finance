#!/usr/bin/env python3
"""按交易日导出 DuckDB 增量（只导当天分区行）→ parquet + manifest → zip。

用途：每天复盘后，把当天新增的 fact 行打成一个几 MB 的小包，传到另一台电脑用
`db_delta_import.py` 合并进它本地的同名库——不用每天传 700M+ 的整库快照。

原理：market_feature_store 里按 `trade_date` 分区的 fact 表是「当天一批新行」的
追加式表，所以单日增量 = `WHERE trade_date = 当天` 的那几千行。每张这样的表导成
一个 parquet（列存、自带 schema、压缩好），再加一份 manifest.json 记录表名/日期列/
行数，最后整体打成 zip。

技术选型 / 替代方案对比（教学）：
- parquet vs CSV：parquet 列存 + 内置类型 + 压缩，DuckDB 原生 `read_parquet`/`COPY`
  零损耗往返；CSV 会丢类型（日期/数值变字符串）、体积大。日志/人看用 CSV，机器搬数用 parquet。
- 单日 parquet 增量 vs `EXPORT DATABASE` 整库：EXPORT 导全库所有表，适合整库迁移/备份；
  这里只要「当天 diff」，所以按 trade_date 过滤导出，体量小、可天天传。
- 不导 `feature_*_window`（滚动窗口派生表）和 `config_*`（静态配置）：滚动窗口靠历史重算，
  搬单日行没意义；这些表要么在目标机重算、要么走整库快照。本脚本只搬「按日分区的事实表」。

可复用知识点：这套「按分区键导 diff → parquet → 目标库 delete+insert 幂等合并」的模式，
在任何按日期/分区追加的数据仓（数据库同步、离线特征表、日志归档）都通用。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import zipfile

import duckdb

_ISO_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")


def is_iso_date(s: object) -> bool:
    """严格 ISO YYYY-MM-DD（且是真实日历）。不接受 2026-7-1 / 20260701 / 时间后缀。"""
    if not isinstance(s, str) or not _ISO_DATE.match(s):
        return False
    try:
        datetime.date.fromisoformat(s)
        return True
    except ValueError:
        return False

CANDIDATE_DATE_COLS = ("trade_date", "date", "dt", "day", "stat_date")
# 滚动窗口 / 静态表：不参与单日增量（靠目标机重算或整库快照）
SKIP_PREFIXES = ("feature_", "config_", "dim_")

# 包级数据契约版本。import 端据此判定校验能力；不兼容的旧包应被拒绝而非静默降级。
# v1: 引入 schema_version / 每文件 sha256 / 零行分区表登记 / 列清单。
SCHEMA_VERSION = 1


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _table_columns(con, table: str) -> list[str]:
    return [r[0] for r in con.execute(
        "select column_name from information_schema.columns "
        "where table_name=? order by ordinal_position", [table]).fetchall()]


def _date_col(con, table: str) -> str | None:
    cols = _table_columns(con, table)
    return next((c for c in CANDIDATE_DATE_COLS if c in cols), None)


def discover_tables(con, include_skipped: bool) -> list[tuple[str, str]]:
    tabs = [r[0] for r in con.execute(
        "select table_name from information_schema.tables "
        "where table_schema='main' order by table_name").fetchall()]
    out = []
    for t in tabs:
        if not include_skipped and t.startswith(SKIP_PREFIXES):
            continue
        dc = _date_col(con, t)
        if dc:
            out.append((t, dc))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="按交易日导出 DuckDB 增量 → zip")
    ap.add_argument("--trade-date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--db", default="db/market_feature_store.duckdb")
    ap.add_argument("--out", default=None, help="输出 zip 路径（默认 ~/Desktop/mfs-delta-<date>.zip）")
    ap.add_argument("--tables", default=None, help="逗号分隔，只导这些表（默认自动发现所有按日分区表）")
    ap.add_argument("--include-skipped", action="store_true",
                    help="连 feature_/config_/dim_ 表也尝试导（默认跳过）")
    a = ap.parse_args()

    date = a.trade_date
    if not is_iso_date(date):
        print(f"[err] --trade-date 需严格 ISO YYYY-MM-DD: {date!r}", file=sys.stderr)
        return 2
    if not os.path.exists(a.db):
        print(f"[err] DB 不存在: {a.db}", file=sys.stderr)
        return 2
    out_zip = a.out or os.path.join(
        os.path.expanduser("~/Desktop"), f"mfs-delta-{date}.zip")
    work = out_zip + ".d"
    os.makedirs(work, exist_ok=True)

    con = duckdb.connect(a.db, read_only=True)
    # partial 判定：--tables 子集导出 或 --include-skipped（非默认可增量表集）都不是
    # 「当日完整日期分区表集」，import 需显式 --allow-partial 才能接受。
    partial = bool(a.tables) or bool(a.include_skipped)
    if a.tables:
        want = [t.strip() for t in a.tables.split(",") if t.strip()]
        tables = [(t, _date_col(con, t)) for t in want]
        tables = [(t, dc) for t, dc in tables if dc]
    else:
        tables = discover_tables(con, a.include_skipped)

    manifest = {"schema_version": SCHEMA_VERSION,
                "trade_date": date, "db": os.path.basename(a.db),
                "partial": partial,
                "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "tables": []}
    total_rows = 0
    for t, dc in tables:
        n = con.execute(
            'select count(*) from "%s" where cast("%s" as varchar)=?' % (t, dc),
            [date]).fetchone()[0]
        cols = _table_columns(con, t)
        entry = {"table": t, "date_col": dc, "rows": n, "columns": cols}
        # 零行分区表也登记（rows=0, file=None）：让 import 端能把目标从「非零」修正为「零」，
        # 而不是因为包里缺这张表就默默跳过、留下过期数据。
        if n == 0:
            entry["file"] = None
            entry["sha256"] = None
            manifest["tables"].append(entry)
            print(f"  {t:42s} {dc:12s} {n:>8} 行 (零行登记)")
            continue
        pq = os.path.join(work, f"{t}.parquet")
        con.execute(
            'copy (select * from "%s" where cast("%s" as varchar)=?) '
            "to '%s' (format parquet)" % (t, dc, pq), [date])
        entry["file"] = f"{t}.parquet"
        entry["sha256"] = _sha256(pq)
        manifest["tables"].append(entry)
        total_rows += n
        print(f"  {t:42s} {dc:12s} {n:>8} 行")
    con.close()

    with open(os.path.join(work, "manifest.json"), "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in os.listdir(work):
            z.write(os.path.join(work, fn), fn)
    for fn in os.listdir(work):
        os.remove(os.path.join(work, fn))
    os.rmdir(work)

    size = os.path.getsize(out_zip)
    n_data = sum(1 for e in manifest["tables"] if e["rows"] > 0)
    n_zero = len(manifest["tables"]) - n_data
    print(f"\n[ok] {n_data} 张有数据表 + {n_zero} 张零行登记 / {total_rows} 行 → "
          f"{out_zip} ({size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

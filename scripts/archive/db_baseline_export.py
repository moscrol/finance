#!/usr/bin/env python3
"""导出可恢复的 DuckDB 全量基线包，供 db_delta_pull.py 在新机器或灾难恢复时使用。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime

import duckdb

try:
    from scripts.db_delta_export import is_iso_date
    from scripts.db_delta_import import _schema_snapshot
except ImportError:  # pragma: no cover
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from db_delta_export import is_iso_date
    from db_delta_import import _schema_snapshot


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export_baseline(db_path: str, out_zip: str, trade_date: str, *, force: bool = False) -> dict:
    if not is_iso_date(trade_date):
        raise ValueError(f"trade_date 需严格 ISO YYYY-MM-DD: {trade_date!r}")
    if not os.path.exists(db_path):
        raise ValueError(f"DB 不存在: {db_path}")
    if os.path.exists(out_zip) and not force:
        raise ValueError(f"输出已存在: {out_zip}（加 --force 覆盖）")

    os.makedirs(os.path.dirname(os.path.abspath(out_zip)) or ".", exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mfs-baseline-export-") as tmp:
        snapshot = os.path.join(tmp, "market_feature_store.duckdb")
        con = duckdb.connect(db_path)
        try:
            con.execute("checkpoint")
        finally:
            con.close()
        shutil.copy2(db_path, snapshot)

        check = duckdb.connect(snapshot, read_only=True)
        try:
            table_count = check.execute(
                "select count(*) from information_schema.tables where table_schema='main'"
            ).fetchone()[0]
            schema_hash = _schema_snapshot(check)["hash"]
        finally:
            check.close()

        manifest = {
            "schema_version": 1,
            "kind": "full_baseline",
            "trade_date": trade_date,
            "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "db_file": os.path.basename(snapshot),
            "sha256": _sha256(snapshot),
            "table_count": table_count,
            "schema_hash": schema_hash,
        }
        staged_zip = out_zip + ".tmp"
        with zipfile.ZipFile(staged_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, manifest["db_file"])
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
        os.replace(staged_zip, out_zip)
        return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 DuckDB 全量基线恢复包")
    parser.add_argument("--trade-date", required=True, help="基线覆盖到的最新交易日 YYYY-MM-DD")
    parser.add_argument("--db", default="db/market_feature_store.duckdb")
    parser.add_argument("--out", default=None, help="默认 ~/Desktop/mfs-baseline-<date>.zip")
    parser.add_argument("--force", action="store_true", help="覆盖已存在输出")
    args = parser.parse_args()

    out_zip = args.out or os.path.join(
        os.path.expanduser("~/Desktop"), f"mfs-baseline-{args.trade_date}.zip"
    )
    try:
        manifest = export_baseline(args.db, out_zip, args.trade_date, force=args.force)
    except ValueError as exc:
        print(f"[err] {exc}", file=sys.stderr)
        return 2
    print(
        f"[ok] baseline {manifest['trade_date']} / {manifest['table_count']} tables "
        f"→ {out_zip}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

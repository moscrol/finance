#!/usr/bin/env python3
"""只读导出教学旁路库；默认只披露市场级标签，不自动上传。

--scope market / market+sector 仅导对应实体的 history_teaching_labels；
含个股身份、原始载荷或构建来源的其他表只在 --scope all 时导出。
给 --knowledge-cutoff 时，同时限制 trade_date 和 first_known_at；没有可知性列的表
一律省略，而非带着警告放行。这只保留源库的 PIT（时点可知性）证据，不证明源戳正确。

导出目录必须全新。还原核对清单、SHA256、列和行数，按当前 DDL 建表，
在临时库完整写成之后发布；绝不覆盖已有文件（包括 legacy 旁路库）。

    python3 scripts/export_teaching_river.py --labels-db db/history_labels.duckdb --out river-export/
    python3 scripts/export_teaching_river.py --rehydrate river-export/ --to slim_sidecar.duckdb
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, time, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.methodology_backtest.store import TEACHING_DDL, TEACHING_TABLES  # noqa: E402

SCHEMA_VERSION = "teaching-river-export/v1"
SCOPES = {"market": ("market",), "market+sector": ("market", "sector"), "all": None}
LABELS = "history_teaching_labels"
OMITTED_STATUSES = {"absent", "omitted_scope", "omitted_pit"}


def _sha256(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def _columns(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    return [str(r[1]) for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()]


def _schemas() -> dict[str, list[str]]:
    con = duckdb.connect(":memory:")
    try:
        for ddl in TEACHING_DDL:
            con.execute(ddl)
        return {t: _columns(con, t) for t in TEACHING_TABLES}
    finally:
        con.close()


def export(labels_db: Path, out: Path, *, scope: str, cutoff: str | None) -> int:
    entity_types = SCOPES[scope]
    cutoff_day = date.fromisoformat(cutoff) if cutoff else None
    if not labels_db.is_file():
        raise FileNotFoundError(f"旁路库不存在: {labels_db}")
    schemas = _schemas()
    # 独占一个新目录，防止上次 all 导出的文件混进本次 market 包。
    out.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_name": labels_db.name,
        "scope": scope,
        "knowledge_cutoff": cutoff,
        "read_only": True,
        "pit_note": (
            "按源库 first_known_at 与 trade_date 过滤；无法证明源戳本身正确。"
            "无可知性列的表已省略。" if cutoff else
            "未给 cutoff；这是事后数据包，消费时仍须过河的 PIT 闸。"
        ),
        "tables": {},
    }
    con = None
    try:
        con = duckdb.connect(str(labels_db), read_only=True)
        con.execute("BEGIN TRANSACTION")
        present = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for table in TEACHING_TABLES:
            if entity_types and table != LABELS:
                manifest["tables"][table] = {"status": "omitted_scope"}
                continue
            if cutoff and table != LABELS:
                manifest["tables"][table] = {"status": "omitted_pit"}
                continue
            if table not in present:
                manifest["tables"][table] = {"status": "absent"}
                continue
            cols = _columns(con, table)
            if set(cols) != set(schemas[table]):
                raise ValueError(f"{table}: schema 过期，先按 reset-teaching 流程重建教学表，勿删整个库")
            predicates, params = ["TRUE"], []
            if entity_types:
                predicates.append(f"entity_type IN ({', '.join('?' for _ in entity_types)})")
                params.extend(entity_types)
            if cutoff_day:
                predicates.append("trade_date <= ? AND first_known_at IS NOT NULL AND first_known_at <= ?")
                params.extend([cutoff_day, datetime.combine(cutoff_day, time.max)])
            sql = f"SELECT * FROM {table} WHERE {' AND '.join(predicates)}"
            target = out / f"{table}.parquet"
            # COPY 的目标是 SQL 字面量；必须转义路径里的单引号。
            quoted = str(target).replace("'", "''")
            con.execute(f"COPY ({sql}) TO '{quoted}' (FORMAT parquet, COMPRESSION zstd)", params)
            n = con.execute(f"SELECT count(*) FROM ({sql})", params).fetchone()[0]
            info = {"status": "ok", "rows": n, "columns": cols,
                    "bytes": target.stat().st_size, "sha256": _sha256(target)}
            if "trade_date" in cols and n:
                lo, hi = con.execute(f"SELECT min(trade_date), max(trade_date) FROM ({sql})", params).fetchone()
                info["trade_date_range"] = [str(lo), str(hi)]
            if "first_known_at" in cols:
                distinct, missing = con.execute(
                    f"SELECT count(DISTINCT first_known_at), count(*) FILTER (WHERE first_known_at IS NULL) FROM ({sql})",
                    params,
                ).fetchone()
                info.update(first_known_at_distinct=distinct, first_known_at_null=missing)
            manifest["tables"][table] = info
        con.execute("COMMIT")
        (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        shutil.rmtree(out)  # 仅清理本次独占创建的输出目录，绝不动源库。
        raise
    finally:
        if con is not None:
            con.close()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"导出完成 → {out}；只在本地写出，尚未披露或上传。")
    return 0


def rehydrate(src: Path, to: Path) -> int:
    """还原到一个全新文件。清单哈希是完整性校验，不是来源真实性签名。"""
    if to.exists() or to.is_symlink():
        raise FileExistsError(f"拒绝覆盖已有目标: {to}")
    manifest = json.loads((src / "MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("不支持的导出清单版本；请用当前工具重新导出")
    tables = manifest.get("tables", {})
    if set(tables) != set(TEACHING_TABLES):
        raise ValueError("清单必须逐一声明当前教学表，不能包含其他表")
    files = {}
    for table, info in tables.items():
        if info.get("status") in OMITTED_STATUSES:
            continue
        if info.get("status") != "ok":
            raise ValueError(f"{table}: 未知的清单状态")
        path = src / f"{table}.parquet"
        if path.is_symlink() or not path.is_file() or _sha256(path) != info.get("sha256"):
            raise ValueError(f"{table}: SHA256 校验失败或文件缺失")
        files[table] = path
    if {p.name for p in src.glob("*.parquet")} != {p.name for p in files.values()}:
        raise ValueError("目录内 parquet 与清单不一致，拒绝混包")
    to.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{to.name}-", dir=to.parent) as staging:
        staged_db = Path(staging) / "sidecar.duckdb"
        con = duckdb.connect(str(staged_db))
        try:
            for ddl in TEACHING_DDL:
                con.execute(ddl)
            for table, path in files.items():
                info = tables[table]
                result = con.execute("SELECT * FROM read_parquet(?) LIMIT 0", [str(path)])
                cols = [str(d[0]) for d in result.description]
                if cols != info.get("columns") or set(cols) != set(_columns(con, table)):
                    raise ValueError(f"{table}: 列与清单/当前 DDL 不符")
                con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM read_parquet(?)", [str(path)])
                n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                if n != info.get("rows"):
                    raise ValueError(f"{table}: 行数与清单不符")
        finally:
            con.close()
        # 同目录文件系统上的硬链接：原子发布且目标若在期间出现也绝不覆盖。
        os.link(staged_db, to)
    print(f"还原完成 → {to}；被省略的表为空表，仍须按消费方 PIT 合同读取。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels-db", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--scope", choices=sorted(SCOPES), default="market")
    ap.add_argument("--knowledge-cutoff", help="YYYY-MM-DD，UTC 当日末；未知可知性的表不导出")
    ap.add_argument("--rehydrate", type=Path)
    ap.add_argument("--to", type=Path)
    args = ap.parse_args()
    if args.rehydrate:
        if not args.to:
            ap.error("--rehydrate 需要 --to")
        return rehydrate(args.rehydrate, args.to)
    if not args.labels_db or not args.out:
        ap.error("导出需要 --labels-db 和 --out")
    return export(args.labels_db, args.out, scope=args.scope, cutoff=args.knowledge_cutoff)


if __name__ == "__main__":
    raise SystemExit(main())

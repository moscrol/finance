"""库级维护: 成分股表空壳行清除 (顺带装上 CHECK) + 整库压缩, 走克隆换名。

## 两件事为什么绑在一起

- **空壳行**: fact_sector_stock_daily_generation 里 810 万行 price/pct_chg/amount 全 NULL
  (fast_daily_sync 与 copy_legacy_member_generation 的「拷成分、改日期」), 占表 67%。
  DuckDB 没有 ALTER TABLE ADD CONSTRAINT, 给表加 CHECK 只能重建; 重建时顺手只搬有报价行,
  一次事务同时完成「删空壳」与「装规则」。
- **压缩**: DuckDB 删行不缩文件 (4.59 GB 里 1.69 GB 已是空闲块), 只有 COPY FROM DATABASE
  到新文件才回收。删完再压, 只换一次名。

## 为什么走克隆换名而不是直接改生产库

重建 4M 行 + 拷 2.9 GB 要几十秒到几分钟, 全程持生产库写锁会饿死 read_only 短连接
(db.py 记录的 bookgap S7 事故)。复用 daily-full 的四个原语: 克隆是 APFS COW 秒级,
所有重活在副本上做, 生产文件只在 os.replace 一瞬变化; 任何守卫失败都不换名。

用法 (生产库):
    python3 -m market_feature_store.cli maintenance --dry-run      # 只读报告: 会删多少、能省多少
    python3 -m market_feature_store.cli maintenance --staged       # 克隆 → 重建+压缩 → 校验 → 换名
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import duckdb

from . import db as _db
from .sector_universe import QUOTE_COLUMNS, QUOTELESS_PREDICATE

TARGET_TABLE = "fact_sector_stock_daily_generation"
TARGET_VIEW = "fact_sector_stock_daily"
REBUILD_TABLE = TARGET_TABLE + "__rebuild"
COMPACT_SUFFIX = ".compact"

_TABLE_DDL_RE = re.compile(
    r"CREATE TABLE IF NOT EXISTS " + TARGET_TABLE + r" \((.*?)\n\);", re.S
)


# ---------------------------------------------------------------------------
# 只读读数
# ---------------------------------------------------------------------------


def shell_row_report(con: duckdb.DuckDBPyConnection) -> dict:
    total, shell = con.execute(
        f"SELECT COUNT(*), COUNT(*) FILTER (WHERE {QUOTELESS_PREDICATE}) FROM {TARGET_TABLE}"
    ).fetchone()
    by_source = con.execute(
        f"""
        SELECT coalesce(source, '<NULL>'), COUNT(*), MIN(trade_date), MAX(trade_date)
        FROM {TARGET_TABLE} WHERE {QUOTELESS_PREDICATE}
        GROUP BY 1 ORDER BY 2 DESC
        """
    ).fetchall()
    return {
        "table": TARGET_TABLE,
        "rows_total": int(total),
        "rows_shell": int(shell),
        "rows_keep": int(total - shell),
        "shell_by_source": [
            {"source": s, "rows": int(n), "first": str(lo), "last": str(hi)}
            for s, n, lo, hi in by_source
        ],
        "has_quote_check": has_quote_check(con),
    }


def has_quote_check(con: duckdb.DuckDBPyConnection) -> bool:
    rows = con.execute(
        """
        SELECT expression FROM duckdb_constraints()
        WHERE table_name = ? AND constraint_type = 'CHECK'
        """,
        [TARGET_TABLE],
    ).fetchall()
    return any(all(col in (expr or "") for col in QUOTE_COLUMNS) for (expr,) in rows)


def db_shape(con: duckdb.DuckDBPyConnection) -> dict:
    """换名前后要对得上的账: 每表行数 + 对象数。"""
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' ORDER BY 1"
    ).fetchall()]
    rows = {t: int(con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]) for t in tables}
    return {
        "rows": rows,
        "tables": len(tables),
        "views": int(con.execute("SELECT COUNT(*) FROM duckdb_views() WHERE NOT internal").fetchone()[0]),
        "indexes": int(con.execute("SELECT COUNT(*) FROM duckdb_indexes()").fetchone()[0]),
        "constraints": int(con.execute("SELECT COUNT(*) FROM duckdb_constraints()").fetchone()[0]),
        "max_trade_date": str(con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()[0]),
    }


def file_usage(path: Path) -> dict:
    con = duckdb.connect(str(path), read_only=True)
    try:
        total_blocks, used_blocks, free_blocks, block_size = con.execute(
            "SELECT total_blocks, used_blocks, free_blocks, block_size FROM pragma_database_size()"
        ).fetchone()
    finally:
        con.close()
    return {
        "bytes": path.stat().st_size,
        "used_bytes": int(used_blocks * block_size),
        "free_bytes": int(free_blocks * block_size),
    }


# ---------------------------------------------------------------------------
# 重建: 删空壳 + 装 CHECK
# ---------------------------------------------------------------------------


def target_table_ddl(rebuild_name: str = REBUILD_TABLE) -> str:
    """从 schema.sql 取成分股代际表的正典 DDL (含 CHECK), 换成重建表名。"""
    text = _db.SCHEMA_PATH.read_text(encoding="utf-8")
    match = _TABLE_DDL_RE.search(text)
    if match is None:
        raise RuntimeError(f"schema.sql 里找不到 {TARGET_TABLE} 的 CREATE TABLE")
    body = match.group(1)
    if "CHECK" not in body:
        raise RuntimeError(f"schema.sql 里 {TARGET_TABLE} 没有 CHECK, 重建没有意义")
    return f"CREATE TABLE {rebuild_name} ({body}\n)"


def _declared_columns(ddl: str) -> list[str]:
    cols: list[str] = []
    for line in ddl.splitlines()[1:]:
        token = line.strip().split()
        if not token or token[0] in {"PRIMARY", "CHECK", ")"} or token[0].startswith("--"):
            continue
        cols.append(token[0])
    return cols


def rebuild_with_quote_check(con: duckdb.DuckDBPyConnection) -> dict:
    """单事务: 建重建表 (正典 DDL + CHECK) → 按列名只搬有报价行 → 换掉旧表 → 重放 schema。

    幂等: 已有 CHECK 且没有空壳行就什么都不做。列集必须与 schema.sql 完全一致,
    否则 fail closed——多出的列会被静默丢掉, 那比不重建更糟。
    """
    before = shell_row_report(con)
    if before["has_quote_check"] and before["rows_shell"] == 0:
        return {"rebuilt": False, "before": before, "after": before}

    ddl = target_table_ddl()
    declared = _declared_columns(ddl)
    existing = [r[0] for r in con.execute(f"DESCRIBE {TARGET_TABLE}").fetchall()]
    extra = sorted(set(existing) - set(declared))
    if extra:
        raise RuntimeError(f"{TARGET_TABLE} 有 schema.sql 未声明的列 {extra}, 拒绝重建以免丢数据")
    columns = ", ".join(f'"{c}"' for c in declared if c in existing)

    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(f"DROP TABLE IF EXISTS {REBUILD_TABLE}")
        con.execute(ddl)
        con.execute(
            f"INSERT INTO {REBUILD_TABLE} ({columns}) SELECT {columns} FROM {TARGET_TABLE} "
            f"WHERE NOT ({QUOTELESS_PREDICATE})"
        )
        # 视图与索引挂在旧表上; 先拆再换, 之后由 schema 重放按正典名重建。
        con.execute(f"DROP VIEW IF EXISTS {TARGET_VIEW}")
        for (index_name,) in con.execute(
            "SELECT index_name FROM duckdb_indexes() WHERE table_name = ?", [TARGET_TABLE]
        ).fetchall():
            con.execute(f'DROP INDEX IF EXISTS "{index_name}"')
        con.execute(f"DROP TABLE {TARGET_TABLE}")
        con.execute(f"ALTER TABLE {REBUILD_TABLE} RENAME TO {TARGET_TABLE}")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    _db.init_db(con)
    after = shell_row_report(con)
    if not after["has_quote_check"] or after["rows_shell"] != 0:
        raise RuntimeError(f"重建后仍不满足规则: {after}")
    if after["rows_total"] != before["rows_keep"]:
        raise RuntimeError(
            f"重建后行数 {after['rows_total']} != 预期保留 {before['rows_keep']}"
        )
    return {"rebuilt": True, "before": before, "after": after}


# ---------------------------------------------------------------------------
# 压缩
# ---------------------------------------------------------------------------


def compact_database(source: Path, dest: Path) -> dict:
    """COPY FROM DATABASE 把 source 完整拷进全新文件 dest (schema+约束+索引+视图+数据)。"""
    started = time.monotonic()
    if dest.exists():
        dest.unlink()
    _db.wal_path(dest).unlink(missing_ok=True)
    con = duckdb.connect()
    try:
        con.execute(f"ATTACH '{source}' AS src (READ_ONLY)")
        con.execute(f"ATTACH '{dest}' AS dst")
        con.execute("COPY FROM DATABASE src TO dst")
        con.execute("DETACH dst")
    finally:
        con.close()
    return {
        "seconds": round(time.monotonic() - started, 1),
        "bytes_before": source.stat().st_size,
        "bytes_after": dest.stat().st_size,
    }


def compare_shapes(expected: dict, actual: dict) -> list[str]:
    problems: list[str] = []
    for table, n in expected["rows"].items():
        got = actual["rows"].get(table)
        if got != n:
            problems.append(f"{table}: 行数 {got} != {n}")
    for key in ("tables", "views", "indexes", "constraints", "max_trade_date"):
        if actual.get(key) != expected.get(key):
            problems.append(f"{key}: {actual.get(key)} != {expected.get(key)}")
    return problems


# ---------------------------------------------------------------------------
# 编排
# ---------------------------------------------------------------------------


def _write_receipt(con, *, started_at: datetime, copy: dict | None, rows_summary: dict, steps: list[dict]) -> str:
    run_id = uuid.uuid4().hex[:12]
    finished = datetime.now()
    con.execute(
        """
        INSERT INTO ops_sync_run
            (run_id, kind, plan, trade_date, started_at, finished_at, duration_s, ok,
             pid, child_pid, copy_method, copy_seconds, source_bytes, rows_summary, steps_summary)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            run_id, "maintenance", "staging-swap", None, started_at, finished,
            round((finished - started_at).total_seconds(), 1), True, os.getpid(), None,
            (copy or {}).get("method"), (copy or {}).get("seconds"), (copy or {}).get("bytes"),
            json.dumps(rows_summary, ensure_ascii=False), json.dumps(steps, ensure_ascii=False),
        ],
    )
    return run_id


def dry_run_report(target: Path | None = None) -> dict:
    target = Path(target) if target is not None else _db.DB_PATH
    con = duckdb.connect(str(target), read_only=True)
    try:
        report = shell_row_report(con)
        shape = db_shape(con)
    finally:
        con.close()
    usage = file_usage(target)
    return {"target": str(target), "shell": report, "file": usage, "shape": shape}


def run_maintenance_staged(
    target: Path | None = None,
    *,
    purge: bool = True,
    compact: bool = True,
) -> dict:
    """克隆 → (重建删空壳+装 CHECK) → (COPY FROM DATABASE 压缩) → 校验 → 守卫 → 换名。

    返回 {swapped, reason, ...}; swapped=False 时生产库一字未动, 中间产物留作取证。
    """
    target = Path(target) if target is not None else _db.DB_PATH
    staging = _db.staging_path(target)
    compact_path = target.with_name(target.name + COMPACT_SUFFIX)
    result: dict = {"target": str(target), "staging": str(staging), "swapped": False, "steps": []}

    _db.remove_stale_staging(staging)
    if compact_path.exists():
        compact_path.unlink()
    _db.wal_path(compact_path).unlink(missing_ok=True)
    if not target.exists():
        result["reason"] = f"目标库不存在: {target}"
        return result
    try:
        _db.probe_no_active_writer(target)
    except _db.DatabaseLockedError as exc:
        result["reason"] = f"生产库有活跃写者, 拒绝开工: {exc}"
        return result

    started = datetime.now()
    result["file_before"] = file_usage(target)
    copy = _db.clone_to_staging(target, staging)
    base_stat = target.stat()
    result["copy"] = copy

    con = duckdb.connect(str(staging))
    try:
        shape_before = db_shape(con)
        rebuild = None
        if purge:
            rebuild = rebuild_with_quote_check(con)
            result["steps"].append({"name": "rebuild_with_quote_check", "ok": True, **rebuild})
        shape_after = db_shape(con)
    finally:
        con.close()
    # 重建只许动目标表; 其他表行数一行都不能变。
    expected_rows = dict(shape_before["rows"])
    if rebuild and rebuild["rebuilt"]:
        expected_rows[TARGET_TABLE] = rebuild["after"]["rows_total"]
    mismatch = [
        f"{t}: {shape_after['rows'].get(t)} != {n}"
        for t, n in expected_rows.items() if shape_after["rows"].get(t) != n
    ]
    if mismatch:
        result["reason"] = "重建后行数对不上, 不换名: " + "; ".join(mismatch)
        return result

    final = staging
    if compact:
        comp = compact_database(staging, compact_path)
        con = duckdb.connect(str(compact_path), read_only=True)
        try:
            problems = compare_shapes(shape_after, db_shape(con))
            if purge and not has_quote_check(con):
                problems.append("压缩后 CHECK 约束丢失")
        finally:
            con.close()
        if problems:
            result["reason"] = "压缩校验失败, 不换名: " + "; ".join(problems)
            return result
        result["steps"].append({"name": "compact", "ok": True, **comp})
        final = compact_path
        _db.remove_stale_staging(staging)

    # 收据写进最终要换上去的文件, 这样压缩的实际数字也在账上。
    con = duckdb.connect(str(final))
    try:
        result["run_id"] = _write_receipt(
            con,
            started_at=started,
            copy=copy,
            rows_summary={"before": shape_before["rows"], "after": shape_after["rows"]},
            steps=[
                {k: v for k, v in step.items() if k not in {"before", "after"}}
                | ({"rows_shell_removed": step["before"]["rows_shell"]} if "before" in step else {})
                for step in result["steps"]
            ],
        )
    finally:
        con.close()

    now_stat = target.stat()
    if now_stat.st_mtime_ns != base_stat.st_mtime_ns or now_stat.st_size != base_stat.st_size:
        result["reason"] = "第三方写者守卫: 生产库在维护期间被修改, 拒绝换名; 产物保留待裁决"
        return result
    try:
        _db.probe_no_active_writer(target)
    except _db.DatabaseLockedError as exc:
        result["reason"] = f"第三方写者守卫: {exc}; 拒绝换名"
        return result
    try:
        _db.atomic_swap_into_place(final, target)
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        result["reason"] = f"换名失败: {exc}"
        return result
    result["file_after"] = file_usage(target)
    result["swapped"] = True
    result["reason"] = "ok"
    return result

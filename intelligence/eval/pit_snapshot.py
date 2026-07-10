"""Immutable daily snapshots and historical point-in-time evidence inventory."""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

SNAPSHOT_TABLES = {
    "fact_market_daily": "history",
    "fact_sector_daily": "history",
    "fact_sw_l1_daily": "history",
    "fact_sector_stock_daily": "current",
    "fact_stock_daily": "current",
    "fact_stock_high_daily": "current",
    "fact_theme_limit_heat_daily": "current",
    "fact_theme_limit_stock_daily": "current",
    "fact_limit_advance_daily": "current",
    "fact_limit_advance_presence": "current",
    "fact_mainline_sector_daily": "current",
    "fact_mainline_theme_daily": "current",
    "fact_mainline_stock_daily": "current",
    "fact_theme_flow_daily": "current",
}
REQUIRED_TABLES = {
    "fact_market_daily",
    "fact_sector_daily",
    "fact_sw_l1_daily",
    "fact_sector_stock_daily",
    "fact_stock_daily",
    "fact_stock_high_daily",
}
PIT_BASELINE_TABLES = (
    "fact_market_daily",
    "fact_sector_daily",
    "fact_stock_daily",
)
ARTIFACT_SUFFIXES = {
    ".csv",
    ".html",
    ".json",
    ".jsonl",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
}


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _connect(db_path: str | Path):
    import duckdb

    return duckdb.connect(str(Path(db_path).expanduser()), read_only=True)


def _table_columns(con: Any, table: str) -> list[str]:
    return [
        str(row[0])
        for row in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = ?
            ORDER BY ordinal_position
            """,
            [table],
        ).fetchall()
    ]


def _git(
    root: str | Path, args: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(Path(root).expanduser()), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def git_state(
    root: str | Path, *, as_of: str | None = None
) -> dict[str, Any] | None:
    repo = Path(root).expanduser()
    try:
        if as_of:
            cutoff = f"{as_of}T23:59:59+08:00"
            commit = _git(repo, ["rev-list", "-1", f"--before={cutoff}", "HEAD"])
            sha = commit.stdout.strip()
        else:
            sha = _git(repo, ["rev-parse", "HEAD"]).stdout.strip()
        if not sha:
            return None
        committed_at = _git(repo, ["show", "-s", "--format=%cI", sha]).stdout.strip()
        state = {
            "root": str(repo),
            "commit": sha,
            "committed_at": committed_at,
        }
        if as_of is None:
            state["dirty"] = bool(_git(repo, ["status", "--porcelain"]).stdout.strip())
        return state
    except (OSError, subprocess.CalledProcessError):
        return None


def _trade_dates(con: Any, as_of: str, lookback: int) -> list[str]:
    rows = con.execute(
        """
        SELECT DISTINCT CAST(trade_date AS VARCHAR)
        FROM fact_market_daily
        WHERE CAST(trade_date AS DATE) <= CAST(? AS DATE)
        ORDER BY 1 DESC
        LIMIT ?
        """,
        [as_of, lookback],
    ).fetchall()
    return sorted(str(row[0])[:10] for row in rows)


def _table_rows(
    con: Any, table: str, dates: Iterable[str]
) -> list[dict[str, Any]]:
    selected_dates = list(dates)
    if not selected_dates:
        return []
    placeholders = ", ".join("?" for _ in selected_dates)
    cursor = con.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE CAST(trade_date AS VARCHAR) IN ({placeholders})
        """,
        selected_dates,
    )
    columns = [str(item[0]) for item in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    rows.sort(
        key=lambda row: json.dumps(
            row, ensure_ascii=False, sort_keys=True, default=_json_default
        )
    )
    return rows


def _table_stats(
    con: Any, table: str, as_of: str, captured_local: datetime
) -> dict[str, Any]:
    columns = _table_columns(con, table)
    required = table in REQUIRED_TABLES
    if not columns or "trade_date" not in columns:
        return {
            "required": required,
            "status": "missing_table",
            "d0_rows": 0,
            "timestamp_field": None,
        }
    d0_rows = int(
        con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)",
            [as_of],
        ).fetchone()[0]
    )
    if "updated_at" not in columns:
        return {
            "required": required,
            "status": "unverifiable" if d0_rows else "missing",
            "d0_rows": d0_rows,
            "timestamp_field": None,
        }
    row = con.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE updated_at IS NOT NULL),
            MIN(updated_at),
            MAX(updated_at),
            COUNT(*) FILTER (WHERE updated_at > ?)
        FROM {table}
        WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
        """,
        [captured_local, as_of],
    ).fetchone()
    timestamped = int(row[0] or 0)
    unsafe = int(row[3] or 0)
    if not d0_rows:
        status = "missing"
    elif timestamped != d0_rows:
        status = "unverifiable"
    elif unsafe:
        status = "future_timestamp"
    else:
        status = "captured"
    return {
        "required": required,
        "status": status,
        "d0_rows": d0_rows,
        "timestamped_rows": timestamped,
        "min_updated_at": _json_default(row[1]) if row[1] else None,
        "max_updated_at": _json_default(row[2]) if row[2] else None,
        "future_timestamp_rows": unsafe,
        "timestamp_field": "updated_at",
    }


def _coverage_checks(con: Any, as_of: str) -> dict[str, Any]:
    active_sectors = int(
        con.execute(
            "SELECT COUNT(*) FROM dim_sector WHERE COALESCE(is_active, TRUE)"
        ).fetchone()[0]
    )
    sector_daily = int(
        con.execute(
            """
            SELECT COUNT(DISTINCT sector_ts_code)
            FROM fact_sector_daily
            WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
            """,
            [as_of],
        ).fetchone()[0]
    )
    sector_stock = int(
        con.execute(
            """
            SELECT COUNT(DISTINCT sector_ts_code)
            FROM fact_sector_stock_daily
            WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
            """,
            [as_of],
        ).fetchone()[0]
    )
    stock_rows = int(
        con.execute(
            """
            SELECT COUNT(DISTINCT stock_ts_code)
            FROM fact_stock_daily
            WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
            """,
            [as_of],
        ).fetchone()[0]
    )
    previous = con.execute(
        """
        SELECT CAST(trade_date AS VARCHAR), COUNT(DISTINCT stock_ts_code)
        FROM fact_stock_daily
        WHERE CAST(trade_date AS DATE) < CAST(? AS DATE)
        GROUP BY trade_date
        ORDER BY trade_date DESC
        LIMIT 1
        """,
        [as_of],
    ).fetchone()
    previous_stock_rows = int(previous[1]) if previous else None
    return {
        "active_sectors": active_sectors,
        "sector_daily": {
            "covered": sector_daily,
            "expected": active_sectors,
            "rate": round(sector_daily / active_sectors, 6)
            if active_sectors
            else None,
        },
        "sector_stock": {
            "covered": sector_stock,
            "expected": active_sectors,
            "rate": round(sector_stock / active_sectors, 6)
            if active_sectors
            else None,
        },
        "stock_daily": {
            "covered": stock_rows,
            "previous_trade_date": str(previous[0])[:10] if previous else None,
            "previous_covered": previous_stock_rows,
            "ratio_to_previous": round(stock_rows / previous_stock_rows, 6)
            if previous_stock_rows
            else None,
        },
    }


def build_daily_snapshot(
    db_path: str | Path,
    *,
    as_of: str | None,
    finance_root: str | Path,
    kb_root: str | Path,
    lookback: int = 20,
) -> tuple[dict[str, Any], dict[str, Any]]:
    con = _connect(db_path)
    try:
        captured_at, captured_local = con.execute(
            "SELECT current_timestamp, current_localtimestamp()"
        ).fetchone()
        if as_of is None:
            row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
            if not row or not row[0]:
                raise ValueError("fact_market_daily has no trade date")
            as_of = str(row[0])[:10]
        dates = _trade_dates(con, as_of, lookback)
        if as_of not in dates:
            raise ValueError(f"{as_of} is not available in fact_market_daily")
        stats = {
            table: _table_stats(con, table, as_of, captured_local)
            for table in SNAPSHOT_TABLES
        }
        data: dict[str, list[dict[str, Any]]] = {}
        for table, mode in SNAPSHOT_TABLES.items():
            if stats[table]["status"] == "missing_table":
                data[table] = []
                continue
            data[table] = _table_rows(
                con, table, dates if mode == "history" else [as_of]
            )
        coverage = _coverage_checks(con, as_of)
    finally:
        con.close()

    required_failures = [
        table
        for table in sorted(REQUIRED_TABLES)
        if stats[table]["status"] != "captured"
    ]
    coverage_gaps = [
        name
        for name in ("sector_daily", "sector_stock")
        if coverage[name]["rate"] is not None and coverage[name]["rate"] < 1
    ]
    status = (
        "pending"
        if required_failures
        else "frozen_with_gaps"
        if coverage_gaps
        else "frozen"
    )
    snapshot = {
        "schema_version": "pit-daily-snapshot-1.0",
        "task_id": "pit-snapshot-inventory-v1",
        "as_of": as_of,
        "captured_at": _json_default(captured_at),
        "captured_at_local": _json_default(captured_local),
        "timezone": "Asia/Shanghai",
        "lookback_trade_dates": dates,
        "boundary": {
            "max_embedded_date": as_of,
            "outcome_data_included": False,
            "result_phase_physically_separate": True,
        },
        "repositories": {
            "finance": git_state(finance_root),
            "wiki": git_state(kb_root),
        },
        "data": data,
    }
    canonical = _canonical_bytes(snapshot)
    manifest = {
        "schema_version": "pit-daily-manifest-1.0",
        "task_id": "pit-snapshot-inventory-v1",
        "as_of": as_of,
        "captured_at": snapshot["captured_at"],
        "status": status,
        "required_failures": required_failures,
        "coverage_gaps": coverage_gaps,
        "coverage": coverage,
        "tables": stats,
        "snapshot_sha256": _sha256(canonical),
        "repositories": snapshot["repositories"],
        "boundary": snapshot["boundary"],
    }
    return snapshot, manifest


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _latest_trade_date(db_path: str | Path) -> str:
    con = _connect(db_path)
    try:
        row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        raise ValueError("fact_market_daily has no trade date")
    return str(row[0])[:10]


def _existing_frozen_manifest(root: Path, as_of: str) -> dict[str, Any] | None:
    manifest_path = root / f"{as_of}.manifest.json"
    snapshot_path = root / f"{as_of}.snapshot.json.gz"
    if not manifest_path.exists() and not snapshot_path.exists():
        return None
    if not manifest_path.exists() or not snapshot_path.exists():
        raise ValueError(f"incomplete frozen pair for {as_of}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    compressed_sha = _sha256(snapshot_path.read_bytes())
    if compressed_sha != manifest.get("compressed_sha256"):
        raise ValueError(f"frozen snapshot checksum mismatch for {as_of}")
    return {**manifest, "write_status": "already_frozen"}


def freeze_daily_snapshot(
    db_path: str | Path,
    *,
    as_of: str | None,
    finance_root: str | Path,
    kb_root: str | Path,
    out_dir: str | Path,
    lookback: int = 20,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(out_dir).expanduser()
    as_of = as_of or _latest_trade_date(db_path)
    existing = _existing_frozen_manifest(root, as_of)
    if existing is not None:
        return existing

    snapshot, manifest = build_daily_snapshot(
        db_path,
        as_of=as_of,
        finance_root=finance_root,
        kb_root=kb_root,
        lookback=lookback,
    )
    resolved_as_of = str(snapshot["as_of"])
    manifest_path = root / f"{resolved_as_of}.manifest.json"
    snapshot_path = root / f"{resolved_as_of}.snapshot.json.gz"
    if manifest_path.exists() or snapshot_path.exists():
        raise ValueError(f"frozen snapshot already exists for {resolved_as_of}")
    canonical = _canonical_bytes(snapshot)
    compressed = gzip.compress(canonical, compresslevel=9, mtime=0)
    manifest.update(
        {
            "snapshot_file": snapshot_path.name,
            "manifest_file": manifest_path.name,
            "compressed_sha256": _sha256(compressed),
            "uncompressed_bytes": len(canonical),
            "compressed_bytes": len(compressed),
            "write_status": "dry_run" if dry_run else "written",
        }
    )
    if not dry_run:
        _write_atomic(snapshot_path, compressed)
        _write_atomic(
            manifest_path,
            json.dumps(
                manifest, ensure_ascii=False, indent=2, default=_json_default
            ).encode("utf-8")
            + b"\n",
        )
    return manifest


def _pit_table_status(con: Any, table: str, as_of: str) -> dict[str, Any]:
    columns = _table_columns(con, table)
    if "trade_date" not in columns:
        return {"status": "missing_table", "rows": 0, "provable_rows": 0}
    rows = int(
        con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)",
            [as_of],
        ).fetchone()[0]
    )
    if not rows:
        return {"status": "missing", "rows": 0, "provable_rows": 0}
    if "updated_at" not in columns:
        return {"status": "unverifiable", "rows": rows, "provable_rows": 0}
    provable = int(
        con.execute(
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
              AND updated_at < CAST(? AS DATE) + INTERVAL 1 DAY
            """,
            [as_of, as_of],
        ).fetchone()[0]
    )
    return {
        "status": "ready"
        if provable == rows
        else "partial"
        if provable
        else "unavailable",
        "rows": rows,
        "provable_rows": provable,
    }


def _dated_artifacts(root: str | Path, commit: str, as_of: str) -> list[str]:
    try:
        paths = _git(root, ["ls-tree", "-r", "--name-only", commit]).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return []
    compact = as_of.replace("-", "")
    return sorted(
        path
        for path in paths
        if (as_of in path or compact in path)
        and Path(path).suffix.lower() in ARTIFACT_SUFFIXES
    )


def build_historical_inventory(
    db_path: str | Path,
    *,
    finance_root: str | Path,
    kb_root: str | Path,
    start: str,
    end: str,
) -> dict[str, Any]:
    con = _connect(db_path)
    try:
        dates = [
            str(row[0])[:10]
            for row in con.execute(
                """
                SELECT DISTINCT trade_date
                FROM fact_market_daily
                WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
                ORDER BY trade_date
                """,
                [start, end],
            ).fetchall()
        ]
        cases: list[dict[str, Any]] = []
        for as_of in dates:
            db_tables = {
                table: _pit_table_status(con, table, as_of)
                for table in PIT_BASELINE_TABLES
            }
            db_ready = all(item["status"] == "ready" for item in db_tables.values())
            repos: dict[str, Any] = {}
            for name, root in (("finance", finance_root), ("wiki", kb_root)):
                state = git_state(root, as_of=as_of)
                artifacts = (
                    _dated_artifacts(root, state["commit"], as_of) if state else []
                )
                repos[name] = {
                    **(state or {"commit": None, "committed_at": None}),
                    "artifact_count": len(artifacts),
                    "artifacts": artifacts[:100],
                }
            artifact_count = sum(item["artifact_count"] for item in repos.values())
            status = (
                "ready_db"
                if db_ready
                else "artifact_candidate"
                if artifact_count
                else "pending"
            )
            cases.append(
                {
                    "as_of": as_of,
                    "status": status,
                    "db_tables": db_tables,
                    "repositories": repos,
                    "artifact_count": artifact_count,
                    "note": (
                        "artifact_candidate 仅证明文件在 cutoff 前存在；"
                        "仍需人工确认其字段与语义足以重建当日输入。"
                        if status == "artifact_candidate"
                        else ""
                    ),
                }
            )
    finally:
        con.close()
    counts = {
        status: sum(case["status"] == status for case in cases)
        for status in ("ready_db", "artifact_candidate", "pending")
    }
    return {
        "schema_version": "pit-historical-inventory-1.0",
        "task_id": "pit-snapshot-inventory-v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "range": {"start": start, "end": end},
        "trade_date_count": len(cases),
        "status_counts": counts,
        "cases": cases,
        "rules": [
            "DuckDB ready 要求基线表全部行 updated_at < as_of + 1 day。",
            "Git artifact 只接受在 as_of 当日 23:59:59+08:00 前已提交的文件。",
            "artifact_candidate 不自动升级为可回放，必须人工核验内容覆盖。",
        ],
    }


def render_historical_inventory(inventory: dict[str, Any]) -> str:
    counts = inventory["status_counts"]
    lines = [
        "# 历史 PIT 证据盘点",
        "",
        f"- 区间：{inventory['range']['start']} ～ {inventory['range']['end']}",
        f"- 交易日：{inventory['trade_date_count']}",
        f"- DuckDB 可证明：{counts['ready_db']}",
        f"- Git 旧资料候选：{counts['artifact_candidate']}",
        f"- 无候选：{counts['pending']}",
        "",
        "> `artifact_candidate` 仅证明资料当时已存在，不代表已通过人工金标准。",
        "",
        "| 日期 | 状态 | DB ready | finance 资料 | wiki 资料 |",
        "|---|---:|---:|---:|---:|",
    ]
    for case in inventory["cases"]:
        db_ready = sum(
            item["status"] == "ready" for item in case["db_tables"].values()
        )
        repos = case["repositories"]
        lines.append(
            f"| {case['as_of']} | {case['status']} | {db_ready}/{len(PIT_BASELINE_TABLES)} "
            f"| {repos['finance']['artifact_count']} | {repos['wiki']['artifact_count']} |"
        )
    lines.extend(["", "## 判定规则", ""])
    lines.extend(f"- {rule}" for rule in inventory["rules"])
    return "\n".join(lines) + "\n"

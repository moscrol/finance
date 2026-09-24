#!/usr/bin/env python3
"""Read-only diagnostic for configured sync code and observed database freshness.

Reads only the selected plist fields, source AST and explicitly listed tables.
Does not load credentials, import/execute the deployed pipeline, write the DB,
change launchd or prove supplier coverage. Exit 2 means a gap or unavailable
check, not permission to repair production automatically.
"""

from __future__ import annotations

import argparse
import ast
from datetime import date
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess

import duckdb

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = Path("skills/daily-full-review/scripts/run_review_sync.py")
TABLES = (
    "fact_stock_daily_hithink",
    "fact_sector_kline_daily",
    "fact_limit_pool_hithink",
    "fact_dragon_tiger_hithink",
    "fact_hot_stock_rank_hithink",
    "fact_auction_hithink",
)
DAILY_TABLES = {"fact_stock_daily_hithink", "fact_sector_kline_daily"}


def declared_steps(root: Path) -> tuple[str, ...]:
    tree = ast.parse((root / PIPELINE).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "HITHINK_STEPS" for t in node.targets
        ):
            values = ast.literal_eval(node.value)
            if isinstance(values, (tuple, list)) and all(
                isinstance(v, str) for v in values
            ):
                return tuple(values)
            raise ValueError("invalid HITHINK_STEPS declaration")
    return ()


def revision(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def audit(
    *, launchd_plist: Path, db_path: Path, target: date, expected_root: Path = ROOT
) -> dict:
    with launchd_plist.open("rb") as handle:
        config = plistlib.load(handle)
    env = config.get("EnvironmentVariables", {})
    configured = env.get("FINANCE_SYNC_CODE_ROOT")
    if not isinstance(configured, str) or not Path(configured).is_absolute():
        raise ValueError("plist must explicitly set absolute FINANCE_SYNC_CODE_ROOT")
    runtime = Path(configured).resolve(strict=True)
    expected = declared_steps(expected_root)
    actual = declared_steps(runtime)
    if not expected:
        raise ValueError("expected checkout has no HITHINK_STEPS declaration")
    missing = sorted(set(expected) - set(actual))
    tables, gaps = {}, []
    if env.get("REVIEW_SYNC_PLAN") != "local":
        gaps.append("configured_plan_is_not_local")
    if missing:
        gaps.append("configured_code_missing_hithink_steps")
    # strict resolve before connect: a missing DB must not be created.
    path = db_path.resolve(strict=True)
    with duckdb.connect(str(path), read_only=True) as con:
        existing = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        for table in TABLES:
            if table not in existing:
                tables[table] = {"state": "missing"}
                if table in DAILY_TABLES:
                    gaps.append(table + ":missing")
                continue
            latest, rows = con.execute(
                f"SELECT max(trade_date), count(*) FILTER (WHERE trade_date=?) FROM {table}",
                [target],
            ).fetchone()
            tables[table] = {
                "latest_date": latest.isoformat() if latest else None,
                "target_day_rows": rows,
            }
            if table in DAILY_TABLES and not rows:
                gaps.append(table + ":target_day_absent")
    return {
        "status": "gaps" if gaps else "checks_passed",
        "configured_root": str(runtime),
        "configured_revision": revision(runtime),
        "configured_pipeline_sha256": hashlib.sha256(
            (runtime / PIPELINE).read_bytes()
        ).hexdigest(),
        "configured_plan": env.get("REVIEW_SYNC_PLAN"),
        "expected_revision": revision(expected_root),
        "expected_pipeline_sha256": hashlib.sha256(
            (expected_root / PIPELINE).read_bytes()
        ).hexdigest(),
        "missing_declared_steps": missing,
        "target_date": target.isoformat(),
        "tables": tables,
        "gaps": gaps,
        "boundary": "configured plist, not loaded launchd environment; step declarations, not execution proof; row counts, not field completeness",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launchd-plist", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--expected-code-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        report = audit(
            launchd_plist=args.launchd_plist,
            db_path=args.db,
            target=args.date,
            expected_root=args.expected_code_root,
        )
    except (
        OSError,
        ValueError,
        SyntaxError,
        duckdb.Error,
        subprocess.SubprocessError,
    ) as exc:
        print(json.dumps({"status": "unavailable", "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "checks_passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

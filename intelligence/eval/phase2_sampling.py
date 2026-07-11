"""Deterministic stratified sampling for fidelity replay Phase 2."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
BASELINE_TABLES = (
    "fact_market_daily",
    "fact_sector_daily",
    "fact_stock_daily",
)
REPORT_PATTERNS = (
    "market_feature_store/exports/{date}-daily-agent.json",
    "复盘/daily/{date}/{date}-daily-review.html",
    "docs/learning/forecast-review-ledger/{date}.md",
    "market_feature_store/exports/{date}-20d-plus-new-highs.md",
)


def _cutoff(value: str) -> datetime:
    return datetime.combine(
        date.fromisoformat(value) + timedelta(days=1),
        time.min,
        tzinfo=SHANGHAI,
    )


def discover_canonical_report(
    repo_root: str | Path,
    report_date: str,
) -> str | None:
    root = Path(repo_root).expanduser().resolve()
    for pattern in REPORT_PATTERNS:
        relative = pattern.format(date=report_date)
        if (root / relative).is_file():
            return relative
    return None


def _table_rows_by_date(
    connection: object,
    table: str,
    start: str,
    end: str,
) -> dict[str, tuple[int, int]]:
    rows = connection.execute(
        f"""
        SELECT
            CAST(trade_date AS VARCHAR) AS trade_date,
            COUNT(*) AS total_rows,
            SUM(
                CASE
                    WHEN updated_at < CAST(trade_date AS DATE)
                        + INTERVAL 1 DAY
                    THEN 1
                    ELSE 0
                END
            ) AS known_rows
        FROM {table}
        WHERE CAST(trade_date AS DATE)
            BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
        GROUP BY trade_date
        """,
        [start, end],
    ).fetchall()
    return {
        str(value)[:10]: (int(total), int(known or 0))
        for value, total, known in rows
    }


def _completeness(
    table_counts: dict[str, tuple[int, int]],
) -> str:
    totals = [value[0] for value in table_counts.values()]
    known = [value[1] for value in table_counts.values()]
    if totals and all(total > 0 for total in totals) and all(
        visible == total
        for total, visible in zip(totals, known)
    ):
        return "ready"
    if any(visible > 0 for visible in known):
        return "partial"
    return "pending"


def load_sampling_frame(
    db_path: str | Path,
    repo_root: str | Path,
    start: str,
    end: str,
) -> list[dict[str, object]]:
    import duckdb

    connection = duckdb.connect(
        str(Path(db_path).expanduser()),
        read_only=True,
    )
    try:
        market_rows = connection.execute(
            """
            SELECT
                CAST(trade_date AS VARCHAR) AS trade_date,
                COALESCE(market_stage, 'missing') AS market_stage
            FROM fact_market_daily
            WHERE CAST(trade_date AS DATE)
                BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            ORDER BY trade_date
            """,
            [start, end],
        ).fetchall()
        baseline = {
            table: _table_rows_by_date(
                connection,
                table,
                start,
                end,
            )
            for table in BASELINE_TABLES
        }
    finally:
        connection.close()

    frame: list[dict[str, object]] = []
    for raw_date, stage in market_rows:
        value = str(raw_date)[:10]
        counts = {
            table: baseline[table].get(value, (0, 0))
            for table in BASELINE_TABLES
        }
        report_path = discover_canonical_report(repo_root, value)
        frame.append(
            {
                "report_date": value,
                "month": value[:7],
                "market_stage": str(stage),
                "data_completeness": _completeness(counts),
                "baseline_counts": {
                    table: {
                        "total_rows": total,
                        "known_rows": known,
                    }
                    for table, (total, known) in counts.items()
                },
                "canonical_report_path": report_path,
                "report_status": (
                    "registered" if report_path else "missing"
                ),
                "cutoff_timestamp": _cutoff(value).isoformat(),
            }
        )
    return frame


def _stable_rank(seed: str, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def select_stratified_dates(
    frame: Iterable[dict[str, object]],
    *,
    count: int,
    seed: str,
) -> list[dict[str, object]]:
    rows = [dict(row) for row in frame]
    if count < 1 or count > len(rows):
        raise ValueError("count must be between 1 and candidate count")

    required = [
        row for row in rows if row.get("canonical_report_path")
    ]
    if len(required) > count:
        raise ValueError("count is smaller than canonical report dates")

    selected_dates = {
        str(row["report_date"]) for row in required
    }
    groups: dict[
        tuple[str, str, str],
        list[dict[str, object]],
    ] = defaultdict(list)
    for row in rows:
        value = str(row["report_date"])
        if value in selected_dates:
            continue
        key = (
            str(row["month"]),
            str(row["market_stage"]),
            str(row["data_completeness"]),
        )
        groups[key].append(row)
    for group in groups.values():
        group.sort(
            key=lambda row: _stable_rank(
                seed,
                str(row["report_date"]),
            )
        )

    slots = count - len(required)
    ordered_keys = sorted(groups)
    selected = list(required)
    while slots:
        progressed = False
        for key in ordered_keys:
            group = groups[key]
            if not group:
                continue
            selected.append(group.pop(0))
            slots -= 1
            progressed = True
            if not slots:
                break
        if not progressed:
            raise RuntimeError("stratified pools exhausted")
    return sorted(selected, key=lambda row: str(row["report_date"]))


def _strata_counts(
    rows: Iterable[dict[str, object]],
) -> dict[str, dict[str, int]]:
    values = list(rows)
    return {
        "month": dict(
            sorted(
                Counter(str(row["month"]) for row in values).items()
            )
        ),
        "market_stage": dict(
            sorted(
                Counter(
                    str(row["market_stage"]) for row in values
                ).items()
            )
        ),
        "data_completeness": dict(
            sorted(
                Counter(
                    str(row["data_completeness"]) for row in values
                ).items()
            )
        ),
        "report_status": dict(
            sorted(
                Counter(
                    str(row["report_status"]) for row in values
                ).items()
            )
        ),
    }


def build_phase2_plan(
    *,
    db_path: str | Path,
    repo_root: str | Path,
    start: str,
    end: str,
    count: int,
    seed: str = "fidelity-replay-phase2-v1",
) -> tuple[dict[str, object], dict[str, object]]:
    if not 50 <= count <= 100:
        raise ValueError("Phase 2 count must be between 50 and 100")
    frame = load_sampling_frame(
        db_path,
        repo_root,
        start,
        end,
    )
    selected = select_stratified_dates(
        frame,
        count=count,
        seed=seed,
    )
    plan = {
        "schema_version": "fidelity-replay-phase2-plan-1.0",
        "task_id": "fidelity-replay-phase2-v1",
        "date_range": {"start": start, "end": end},
        "target_count": count,
        "candidate_count": len(frame),
        "selected_count": len(selected),
        "seed": seed,
        "selection_rule": (
            "Include every exact-date canonical report, then fill remaining "
            "slots by deterministic round-robin over month, market stage, "
            "and PIT data completeness strata."
        ),
        "negative_control_rule": (
            "Selected trading dates without an exact-date canonical report "
            "remain missing; no current report is substituted."
        ),
        "candidate_strata": _strata_counts(frame),
        "selected_strata": _strata_counts(selected),
        "dates": selected,
        "decision_eligible": False,
    }
    registry = {
        "schema_version": "claim-fidelity-report-registry-2.0",
        "task_id": "fidelity-replay-phase2-v1",
        "selection_rule": plan["selection_rule"],
        "negative_control_rule": plan["negative_control_rule"],
        "reports": [
            {
                "report_date": row["report_date"],
                "canonical_report_path": row["canonical_report_path"],
                "status": row["report_status"],
                "strata": {
                    "month": row["month"],
                    "market_stage": row["market_stage"],
                    "data_completeness": row["data_completeness"],
                },
            }
            for row in selected
        ],
    }
    return plan, registry


def write_json(path: str | Path, body: dict[str, object]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

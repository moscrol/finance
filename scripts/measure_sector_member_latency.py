"""Measure read-only fupanhui sector-member workload latency."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import re
import statistics
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class _ProviderFailure(Exception):
    """Internal signal that a provider call failed after safe reporting."""


def _provider_call(stage: str, call):
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            return call()
    except Exception as exc:
        exception_type = (
            type(exc).__name__
            if type(exc).__module__ == "builtins"
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", type(exc).__name__)
            else "Exception"
        )
        print(
            json.dumps(
                {
                    "error_code": "provider_exception",
                    "exception_type": exception_type,
                    "stage": stage,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise _ProviderFailure from None


def _count(row: Mapping[str, Any]) -> int:
    """Return a positive numeric stock count, otherwise zero."""
    value = row.get("stock_count")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value <= 0
    ):
        return 0
    return int(value)


def select_probe_sectors(
    sectors: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """Select representative valid sectors from smallest through largest."""
    valid = sorted(
        (row for row in sectors if row.get("ts_code") and _count(row) > 0),
        key=lambda row: (_count(row), str(row["ts_code"])),
    )
    if not valid:
        raise ValueError("no sectors with ts_code and positive stock_count")

    last = len(valid) - 1
    high = min(len(valid) - 2, (len(valid) * 4) // 5) if len(valid) > 2 else last
    indexes = (0, len(valid) // 2, high, last)
    return tuple(valid[index] for index in dict.fromkeys(indexes))


def select_probe_batches(
    sectors: Sequence[Mapping[str, Any]], batch_size: int
) -> tuple[tuple[str, ...], ...]:
    """Select representative centred batches from valid sectors."""
    if batch_size <= 0:
        raise ValueError("batch size must be positive")
    valid = sorted(
        (row for row in sectors if row.get("ts_code") and _count(row) > 0),
        key=lambda row: (_count(row), str(row["ts_code"])),
    )
    if not valid:
        raise ValueError("no sectors with ts_code and positive stock_count")

    last = len(valid) - 1
    centres = (0, len(valid) // 2, (len(valid) * 4) // 5, last)
    batches: list[tuple[str, ...]] = []
    for centre in centres:
        width = min(batch_size, len(valid))
        start = max(0, min(centre - width // 2, len(valid) - width))
        batch = tuple(str(row["ts_code"]) for row in valid[start : start + width])
        if batch not in batches:
            batches.append(batch)
    return tuple(batches)


def project_wall_clock(
    *,
    sector_count: int,
    batch_size: int,
    batch_elapsed_seconds: Sequence[float],
    nightly_window_seconds: float,
) -> dict[str, int | float | bool]:
    """Project full-run wall clock from representative batch observations."""
    if sector_count <= 0 or batch_size <= 0 or nightly_window_seconds <= 0:
        raise ValueError("counts, batch size, and nightly window must be positive")
    if not batch_elapsed_seconds or any(
        not math.isfinite(float(value)) or value <= 0 for value in batch_elapsed_seconds
    ):
        raise ValueError("batch elapsed observations must be non-empty and positive")

    observations = sorted(float(value) for value in batch_elapsed_seconds)
    p50 = statistics.median(observations)
    p95 = observations[math.ceil(len(observations) * 0.95) - 1]
    batches = math.ceil(sector_count / batch_size)
    projected = batches * p95
    return {
        "batches": batches,
        "batch_p50_seconds": round(p50, 3),
        "batch_p95_seconds": round(p95, 3),
        "projected_seconds": round(projected, 3),
        "nightly_window_seconds": round(float(nightly_window_seconds), 3),
        "fits_nightly_window": projected <= nightly_window_seconds,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--nightly-window-seconds", type=float, default=7200)
    return parser


def main(argv: Sequence[str] | None = None, *, provider: Any | None = None) -> int:
    args = _build_parser().parse_args(argv)
    args.output.unlink(missing_ok=True)
    if provider is None:
        repository_root = str(Path(__file__).resolve().parents[1])
        if repository_root not in sys.path:
            sys.path.insert(0, repository_root)
        from market_feature_store.sources import fupanhui_source as provider

    try:
        sectors = _provider_call(
            "list_sectors",
            lambda: provider.list_sectors(trade_date=args.trade_date),
        )
        individual_probes: list[dict[str, Any]] = []
        for sector in select_probe_sectors(sectors):
            started = time.perf_counter()
            payload = _provider_call(
                "individual_probe",
                lambda: provider.get_sector_stocks(
                    str(sector["ts_code"]), trade_date=args.trade_date
                ),
            )
            elapsed = time.perf_counter() - started
            actual_codes = {
                str(stock["ts_code"])
                for stock in payload.get("stocks", [])
                if stock.get("ts_code")
            }
            declared = _count(sector)
            actual = len(actual_codes)
            individual_probes.append(
                {
                    "code": str(sector["ts_code"]),
                    "name": str(sector.get("name") or ""),
                    "declared": declared,
                    "actual": actual,
                    "elapsed_seconds": round(elapsed, 3),
                    "count_matches": declared == actual,
                }
            )

        batch_observations: list[float] = []
        for batch in select_probe_batches(sectors, args.batch_size):
            started = time.perf_counter()
            _provider_call(
                "batch_probe",
                lambda: provider.get_sector_stocks_batch(
                    list(batch),
                    trade_date=args.trade_date,
                    batch=args.batch_size,
                ),
            )
            elapsed = time.perf_counter() - started
            batch_observations.append(elapsed)
    except _ProviderFailure:
        return 3

    projection = project_wall_clock(
        sector_count=len(sectors),
        batch_size=args.batch_size,
        batch_elapsed_seconds=batch_observations,
        nightly_window_seconds=args.nightly_window_seconds,
    )
    receipt = {
        "schema_version": 1,
        "trade_date": args.trade_date,
        "sector_count": len(sectors),
        "batch_size": args.batch_size,
        "individual_probes": individual_probes,
        "projection": projection,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(projection, ensure_ascii=False, sort_keys=True))
    return 0 if all(probe["count_matches"] for probe in individual_probes) else 2


if __name__ == "__main__":
    raise SystemExit(main())

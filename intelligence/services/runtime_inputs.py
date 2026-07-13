from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from intelligence.services.market_snapshot_contract import (
    validate_market_snapshot_root,
)


_EXPORT_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})-theme-candidates\.json$")


@dataclass(frozen=True)
class RuntimeResearchInputs:
    code_root: Path
    data_root: Path
    users_root: Path
    knowledge_wiki: Path
    vector_index_dir: Path
    market_db_path: Path
    exports_dir: Path
    market_snapshot_dir: Path

    @classmethod
    def from_roots(
        cls,
        *,
        code_root: Path,
        data_root: Path,
        users_root: Path,
        knowledge_wiki: Path,
        vector_index_dir: Path,
        market_snapshot_dir: Path | None = None,
    ) -> RuntimeResearchInputs:
        code = code_root.expanduser().resolve()
        data = data_root.expanduser().resolve()
        snapshot = market_snapshot_dir or data / "market_snapshot"
        return cls(
            code_root=code,
            data_root=data,
            users_root=users_root.expanduser().resolve(),
            knowledge_wiki=knowledge_wiki.expanduser().resolve(),
            vector_index_dir=vector_index_dir.expanduser().resolve(),
            market_db_path=data / "db/market_feature_store.duckdb",
            exports_dir=data / "market_feature_store/exports",
            market_snapshot_dir=snapshot.expanduser().resolve(),
        )


@dataclass(frozen=True)
class MarketInputStatus:
    duckdb_available: bool
    duckdb_cutoff: str | None
    latest_export_date: str | None
    export_freshness: str
    market_snapshot_available: bool
    market_snapshot_date: str | None
    market_data_available: bool
    warning: str | None = None
    export_warning: str | None = None


def _parse_iso_date(raw: str) -> date | None:
    try:
        parsed = date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.isoformat() == raw else None


def _duckdb_cutoff(path: Path) -> tuple[str | None, str | None]:
    if not path.is_file():
        return None, "duckdb_missing"
    try:
        import duckdb

        connection = duckdb.connect(str(path), read_only=True)
        try:
            value = connection.execute(
                "select max(trade_date) from fact_market_daily"
            ).fetchone()[0]
        finally:
            connection.close()
    except Exception:  # optional dependency, lock, corrupt file, or missing schema
        return None, "duckdb_unavailable"
    if value is None:
        return None, None
    raw_cutoff = str(value)
    parsed_cutoff = _parse_iso_date(raw_cutoff)
    if parsed_cutoff is None:
        return None, "duckdb_invalid_cutoff"
    return parsed_cutoff.isoformat(), None


def _latest_export_date(exports_dir: Path) -> tuple[str | None, str | None]:
    try:
        if not exports_dir.is_dir():
            return None, None
        dates = [
            parsed
            for path in exports_dir.iterdir()
            if path.is_file()
            and (match := _EXPORT_DATE.fullmatch(path.name))
            and (parsed := _parse_iso_date(match.group(1))) is not None
        ]
    except OSError:
        return None, "exports_unavailable"
    latest = max(dates, default=None)
    return (latest.isoformat() if latest is not None else None), None


def probe_market_inputs(inputs: RuntimeResearchInputs) -> MarketInputStatus:
    cutoff, warning = _duckdb_cutoff(inputs.market_db_path)
    export_date, export_warning = _latest_export_date(inputs.exports_dir)
    cutoff_date = _parse_iso_date(cutoff) if cutoff else None
    latest_export_date = _parse_iso_date(export_date) if export_date else None
    if cutoff_date and latest_export_date:
        if latest_export_date == cutoff_date:
            export_freshness = "fresh"
        elif latest_export_date < cutoff_date:
            export_freshness = "stale"
        else:
            export_freshness = "conflict"
    else:
        export_freshness = "missing"

    snapshot_validation = validate_market_snapshot_root(inputs.market_snapshot_dir)
    snapshot_status = snapshot_validation.get("status")
    snapshot_errors = snapshot_validation.get("errors") or []
    snapshot_warnings = snapshot_validation.get("warnings") or []
    snapshot_date = _parse_iso_date(str(snapshot_validation.get("date") or ""))
    missing_core_market = any(
        str(item) == "market must be an object"
        or str(item).startswith("missing market.")
        for item in snapshot_warnings
    )
    snapshot_available = snapshot_date is not None and (
        snapshot_status == "PASS"
        or (
            snapshot_status == "WARN"
            and not snapshot_errors
            and not missing_core_market
        )
    )

    return MarketInputStatus(
        duckdb_available=cutoff is not None,
        duckdb_cutoff=cutoff,
        latest_export_date=export_date,
        export_freshness=export_freshness,
        market_snapshot_available=snapshot_available,
        market_snapshot_date=(
            snapshot_date.isoformat() if snapshot_available else None
        ),
        market_data_available=cutoff is not None or snapshot_available,
        warning=warning,
        export_warning=export_warning,
    )

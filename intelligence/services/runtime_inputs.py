from __future__ import annotations

import re
from dataclasses import dataclass
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
    return (str(value) if value is not None else None), None


def _latest_export_date(exports_dir: Path) -> str | None:
    if not exports_dir.is_dir():
        return None
    dates = [
        match.group(1)
        for path in exports_dir.iterdir()
        if path.is_file() and (match := _EXPORT_DATE.fullmatch(path.name))
    ]
    return max(dates, default=None)


def probe_market_inputs(inputs: RuntimeResearchInputs) -> MarketInputStatus:
    cutoff, warning = _duckdb_cutoff(inputs.market_db_path)
    export_date = _latest_export_date(inputs.exports_dir)
    if cutoff and export_date:
        if export_date == cutoff:
            export_freshness = "fresh"
        elif export_date < cutoff:
            export_freshness = "stale"
        else:
            export_freshness = "conflict"
    else:
        export_freshness = "missing"

    snapshot_validation = validate_market_snapshot_root(inputs.market_snapshot_dir)
    snapshot_available = snapshot_validation["status"] in {"PASS", "WARN"}
    snapshot_date = str(snapshot_validation.get("date") or "") or None

    return MarketInputStatus(
        duckdb_available=cutoff is not None,
        duckdb_cutoff=cutoff,
        latest_export_date=export_date,
        export_freshness=export_freshness,
        market_snapshot_available=snapshot_available,
        market_snapshot_date=snapshot_date if snapshot_available else None,
        market_data_available=cutoff is not None or snapshot_available,
        warning=warning,
    )

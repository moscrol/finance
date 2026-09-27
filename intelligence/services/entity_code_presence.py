"""Read-only identity checks; a missing price row never proves nonexistence.

Published sector snapshots define a closed local catalog. Other dated records
can prove that an exact code existed, including codes retired before the query
window. The store has no complete stock directory: absence there is unverified.
All reads use the caller's connection, transaction and deadline checks.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class EntityCodeCheck:
    entity_kind: str
    as_of: date
    known_codes: tuple[str, ...]
    unknown_codes: tuple[str, ...]
    unverifiable_codes: tuple[str, ...]
    checked_sources: tuple[str, ...]

    @property
    def failure_code(self) -> str | None:
        if self.unknown_codes:
            return "unknown_entity_code"
        if self.unverifiable_codes:
            return "entity_catalog_unavailable"
        return None

    @property
    def gaps(self) -> tuple[str, ...]:
        gaps = []
        if self.unknown_codes:
            gaps.append("fabricated_entity:" + self.entity_kind + ":" + ",".join(self.unknown_codes))
        if self.unverifiable_codes:
            gaps.append("entity_catalog_unavailable:" + self.entity_kind + ":" + ",".join(self.unverifiable_codes))
        return tuple(gaps)

    @property
    def message(self) -> str:
        if self.unknown_codes:
            detail = "截至请求时点的本地已发布板块目录不存在精确代码：" + ", ".join(self.unknown_codes)
        else:
            detail = "本地目录不能核实以下精确代码，不能据此判定实体不存在：" + ", ".join(self.unverifiable_codes)
        return f"{self.failure_code}: {detail}。请先查验同一时点的实体代码；不猜测代码或交易所后缀。"

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.failure_code,
            "entity_kind": self.entity_kind,
            "as_of": self.as_of.isoformat(),
            "known_codes": list(self.known_codes),
            "unknown_codes": list(self.unknown_codes),
            "unverifiable_codes": list(self.unverifiable_codes),
            "checked_sources": list(self.checked_sources),
        }


def check_entity_codes(
    con: Any,
    *,
    entity_kind: str,
    codes: Sequence[str],
    as_of: date,
    check: Callable[[], None],
    observed_table: str | None = None,
    observed_date_field: str = "trade_date",
) -> EntityCodeCheck:
    """Check exact codes without aliases, suffix repair or interval-row inference.

    ``observed_table`` is the caller's registered dataset, never model SQL.
    Facts only provide positive identity evidence, across all dates up to as_of.
    Undated/current dimensions cannot close a historical directory.
    """
    requested = tuple(dict.fromkeys(codes))
    if not requested or entity_kind == "market":
        return EntityCodeCheck(entity_kind, as_of, requested, (), (), ())
    if entity_kind not in {"sector", "stock"}:
        raise ValueError("entity_kind must be sector, stock or market")
    check()
    columns: dict[str, set[str]] = {}
    for table, column in con.execute(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'main'"
    ).fetchall():
        columns.setdefault(table, set()).add(column)
    known: set[str] = set()
    undated: set[str] = set()
    sources: list[str] = []
    code_field = f"{entity_kind}_ts_code"

    def has(table: str, *fields: str) -> bool:
        return set(fields) <= columns.get(table, set())

    def quote(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def observed(table: str, time_field: str) -> None:
        if not has(table, code_field, time_field):
            return
        check()
        known.update(row[0] for row in con.execute(
            f"SELECT DISTINCT {quote(code_field)} FROM {quote(table)} "
            f"WHERE {quote(code_field)} IN (SELECT unnest(?)) AND {quote(time_field)} <= ?",
            [list(requested), as_of],
        ).fetchall())
        sources.append(table)

    authoritative = False
    if entity_kind == "sector":
        header = "ops_sector_universe_snapshot_daily"
        universe = "fact_sector_universe_daily"
        if has(header, "trade_date", "snapshot_id", "status", "sector_count") and has(
            universe, "trade_date", "snapshot_id", "sector_ts_code"
        ):
            check()
            snapshots = con.execute(
                "SELECT h.sector_count, count(u.sector_ts_code) "
                "FROM ops_sector_universe_snapshot_daily h LEFT JOIN fact_sector_universe_daily u "
                "ON u.trade_date = h.trade_date AND u.snapshot_id = h.snapshot_id "
                "WHERE h.status = 'published' AND h.trade_date <= ? "
                "GROUP BY h.trade_date, h.snapshot_id, h.sector_count",
                [as_of],
            ).fetchall()
            # An incomplete published directory cannot support a negative claim.
            authoritative = bool(snapshots) and all(expected == actual and actual > 0 for expected, actual in snapshots)
            check()
            known.update(row[0] for row in con.execute(
                "SELECT DISTINCT u.sector_ts_code FROM fact_sector_universe_daily u "
                "JOIN ops_sector_universe_snapshot_daily h "
                "ON u.trade_date = h.trade_date AND u.snapshot_id = h.snapshot_id "
                "WHERE h.status = 'published' AND u.trade_date <= ? "
                "AND u.sector_ts_code IN (SELECT unnest(?))",
                [as_of, list(requested)],
            ).fetchall())
            sources.append("fact_sector_universe_daily:published")
        for table, time_field in (("dim_sector", "first_seen_date"), ("dim_sector_hithink", "updated_at")):
            if has(table, code_field):
                check()
                # first_seen_date can lag historical fact dates; it is positive
                # evidence only. Never reject an old code using this timestamp.
                timestamp = quote(time_field) if has(table, time_field) else "NULL"
                for code, seen in con.execute(
                    f"SELECT {quote(code_field)}, CAST({timestamp} AS DATE) FROM {quote(table)} "
                    f"WHERE {quote(code_field)} IN (SELECT unnest(?))", [list(requested)],
                ).fetchall():
                    (known if seen is not None and seen <= as_of else undated).add(code)
                sources.append(table)
        observed("fact_sector_daily", "trade_date")  # published view, including visible legacy rows
        observed("fact_sector_kline_daily", "trade_date")
        # The canonical published universe does not enumerate Hithink's separate
        # index/concept definitions. Its absence cannot disprove those codes.
        if observed_table in {"fact_sector_kline_daily", "fact_sector_constituent_hithink"}:
            authoritative = False
    else:
        for table, time_field in (
            ("fact_stock_daily", "trade_date"),
            ("fact_stock_daily_hithink", "trade_date"),
            ("fact_sector_stock_daily", "trade_date"),
            ("fact_sector_constituent_hithink", "captured_at"),
        ):
            observed(table, time_field)
    if observed_table is not None and observed_table not in sources:
        observed(observed_table, observed_date_field)
    check()
    missing = set(requested) - known
    unknown = missing - undated if authoritative else set()
    return EntityCodeCheck(
        entity_kind, as_of,
        tuple(code for code in requested if code in known),
        tuple(code for code in requested if code in unknown),
        tuple(code for code in requested if code in missing - unknown),
        tuple(sources),
    )

"""板块宇宙 (sector universe) 深模块。

这是生产代码里唯一允许触碰物理代际表
(`fact_sector_daily_generation` / `fact_sector_stock_daily_generation`) 以及
快照/回执表的地方。对外公开的 `fact_sector_daily` /
`fact_sector_stock_daily` 是只读视图, 只暴露某个交易日「唯一已发布代际」,
因此读者不会跨代际混池, 也不需要知道底层存储。

本文件当前实现 Task 2-3 的范围: schema 装载、幂等 legacy 迁移、每日宇宙
验证/发布以及 active identities 所有权。代际事实写入 (Task 4)、成员结果
(Task 5)、完成审计 (Task 7) 在后续任务中按同一接口边界补齐。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import unicodedata

import duckdb

PACKAGE_DIR = Path(__file__).resolve().parent
SECTOR_SCHEMA_PATH = PACKAGE_DIR / "sector_schema.sql"

#: 迁移前历史行统一挂在这个哨兵代际下, 它永远不会有 published 表头。
LEGACY_SNAPSHOT_ID = "legacy"

_MIGRATIONS = (
    ("fact_sector_daily", "_legacy_fact_sector_daily", "fact_sector_daily_generation"),
    (
        "fact_sector_stock_daily",
        "_legacy_fact_sector_stock_daily",
        "fact_sector_stock_daily_generation",
    ),
)


class SectorUniverseValidationError(ValueError):
    """Provider universe cannot be published without weakening its contract."""


class _CommittedPublicationRejection(Exception):
    """Internal signal: the rejected audit header has already committed."""


@dataclass(frozen=True, slots=True)
class SectorDescriptor:
    """One provider-declared sector identity in an immutable daily universe."""

    sector_ts_code: str
    sector_name: str
    expected_stock_count: int
    sw_l1: str | None = None


@dataclass(frozen=True, slots=True)
class PublishedSectorSnapshot:
    """Public receipt for the one published provider universe generation."""

    trade_date: date
    snapshot_id: str
    provider_source: str
    sector_count: int
    declared_relationship_count: int
    captured_at: datetime


def _canonical_text(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).split())


def _normalize_trade_date(value: str | date) -> date:
    if isinstance(value, datetime):
        raise SectorUniverseValidationError("trade_date must not include a time")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise SectorUniverseValidationError("trade_date must be ISO YYYY-MM-DD") from exc


def _normalize_captured_at(value: str | datetime) -> datetime:
    try:
        captured_at = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise SectorUniverseValidationError("captured_at must be an ISO timestamp") from exc
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise SectorUniverseValidationError("captured_at must be timezone-aware")
    return captured_at


def _normalize_sectors(
    sectors: tuple[SectorDescriptor, ...] | list[SectorDescriptor],
) -> tuple[SectorDescriptor, ...]:
    normalized: list[SectorDescriptor] = []
    codes: set[str] = set()
    names: set[str] = set()
    for raw in sectors:
        if not isinstance(raw, SectorDescriptor):
            raise SectorUniverseValidationError("all sectors must be SectorDescriptor values")
        code = _canonical_text(raw.sector_ts_code).upper()
        name = _canonical_text(raw.sector_name)
        name_identity = name.casefold()
        if not code or not name:
            raise SectorUniverseValidationError("sector code and name must be non-empty")
        if code in codes or name_identity in names:
            raise SectorUniverseValidationError("sector identities must be unique")
        if type(raw.expected_stock_count) is not int or raw.expected_stock_count <= 0:
            raise SectorUniverseValidationError("expected_stock_count must be a positive integer")
        sw_l1 = _canonical_text(raw.sw_l1) if raw.sw_l1 is not None else None
        normalized.append(
            SectorDescriptor(code, name, raw.expected_stock_count, sw_l1 or None)
        )
        codes.add(code)
        names.add(name_identity)
    if not normalized:
        raise SectorUniverseValidationError("sector universe must be non-empty")
    return tuple(sorted(normalized, key=lambda row: row.sector_ts_code))


def _snapshot_id(
    *,
    trade_date: date,
    provider_source: str,
    sectors: tuple[SectorDescriptor, ...],
) -> str:
    rows = [
        {
            "expected_stock_count": row.expected_stock_count,
            "provider_source": provider_source,
            "sector_name": row.sector_name,
            "sector_ts_code": row.sector_ts_code,
            "trade_date": trade_date.isoformat(),
        }
        for row in sectors
    ]
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _adjacent_name_continuity(
    con: duckdb.DuckDBPyConnection,
    *,
    trade_date: date,
    snapshot_id: str,
    provider_source: str,
    sectors: tuple[SectorDescriptor, ...],
) -> tuple[int, int] | None:
    baseline = con.execute(
        """
        SELECT h.trade_date, h.snapshot_id, h.sector_count
        FROM ops_sector_universe_snapshot_daily AS h
        WHERE h.provider_source = ? AND h.status = 'published'
          AND h.trade_date <= ? AND h.snapshot_id <> ?
        ORDER BY h.trade_date DESC, h.captured_at DESC
        LIMIT 1
        """,
        [provider_source, trade_date, snapshot_id],
    ).fetchone()
    if baseline is None:
        return None
    prior_names = {
        _canonical_text(row[0]).casefold()
        for row in con.execute(
            """
            SELECT sector_name FROM fact_sector_universe_daily
            WHERE trade_date = ? AND snapshot_id = ?
            """,
            [baseline[0], baseline[1]],
        ).fetchall()
    }
    current_names = {row.sector_name.casefold() for row in sectors}
    return len(prior_names & current_names), int(baseline[2])


def _table_type(con: duckdb.DuckDBPyConnection, name: str) -> str | None:
    row = con.execute(
        """
        SELECT table_type FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [name],
    ).fetchone()
    return row[0] if row else None


def _columns(con: duckdb.DuckDBPyConnection, name: str) -> tuple[str, ...]:
    rows = con.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = ?
        ORDER BY ordinal_position
        """,
        [name],
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _drop_dependent_indexes(con: duckdb.DuckDBPyConnection, table_name: str) -> None:
    """删掉挂在遗留表上的显式索引。

    生产库上 schema.sql 为两张事实表建了 5 个显式索引; DuckDB 会因为这些依赖拒绝
    `ALTER TABLE ... RENAME`。索引本身是可重建的加速结构, 不含数据: 代际表在
    sector_schema.sql 里重新建了等价索引, 遗留表随迁移结束一起被删除。
    """
    rows = con.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE schema_name = 'main' AND table_name = ?",
        [table_name],
    ).fetchall()
    for (index_name,) in rows:
        con.execute(f'DROP INDEX IF EXISTS "{index_name}"')


def _copy_legacy_rows(
    con: duckdb.DuckDBPyConnection,
    *,
    legacy_name: str,
    generation_name: str,
) -> None:
    """按列名 (不是列序) 把 legacy 行复制进代际表并打上 legacy 戳。

    生产库里 `multi_period_*` / `pct_chg_3d` 等列是历史 ALTER 追加的, 物理列序
    与 schema.sql 不一致, 因此必须按名映射; legacy 表缺失的列补 NULL。
    """
    legacy_columns = set(_columns(con, legacy_name))
    target_columns = [
        column
        for column in _columns(con, generation_name)
        if column != "sector_universe_snapshot_id"
    ]
    selected = ", ".join(
        f'l."{column}"' if column in legacy_columns else f'NULL AS "{column}"'
        for column in target_columns
    )
    quoted_targets = ", ".join(f'"{column}"' for column in target_columns)
    con.execute(
        f'INSERT INTO "{generation_name}" (sector_universe_snapshot_id, {quoted_targets}) '
        f'SELECT ?, {selected} FROM "{legacy_name}" AS l '
        "ON CONFLICT DO NOTHING",
        [LEGACY_SNAPSHOT_ID],
    )


class SectorUniverseStore:
    """板块宇宙的唯一生产入口。

    调用方只使用本类的公开方法; 物理表名不在本模块和
    `market_feature_store/sector_schema.sql` 之外出现。
    """

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._con

    def publish_snapshot(
        self,
        *,
        trade_date: str | date,
        provider_source: str,
        sectors: tuple[SectorDescriptor, ...] | list[SectorDescriptor],
        captured_at: str | datetime,
    ) -> PublishedSectorSnapshot:
        """Validate and atomically publish one daily provider universe."""
        canonical_date = _normalize_trade_date(trade_date)
        canonical_provider = _canonical_text(provider_source).casefold()
        if not canonical_provider:
            raise SectorUniverseValidationError("provider_source must be non-empty")
        canonical_captured_at = _normalize_captured_at(captured_at)
        canonical_sectors = _normalize_sectors(sectors)
        snapshot_id = _snapshot_id(
            trade_date=canonical_date,
            provider_source=canonical_provider,
            sectors=canonical_sectors,
        )
        sector_count = len(canonical_sectors)
        declared_relationship_count = sum(
            row.expected_stock_count for row in canonical_sectors
        )
        published = PublishedSectorSnapshot(
            trade_date=canonical_date,
            snapshot_id=snapshot_id,
            provider_source=canonical_provider,
            sector_count=sector_count,
            declared_relationship_count=declared_relationship_count,
            captured_at=canonical_captured_at,
        )

        self._con.execute("BEGIN TRANSACTION")
        try:
            published_before = self._con.execute(
                """
                SELECT count(*) FROM ops_sector_universe_snapshot_daily
                WHERE trade_date = ? AND provider_source = ? AND status = 'published'
                """,
                [canonical_date, canonical_provider],
            ).fetchone()[0]
            if published_before > 1:
                raise SectorUniverseValidationError(
                    "more than one published snapshot exists before publication"
                )
            existing = self._con.execute(
                """
                SELECT status, sector_count, declared_relationship_count, captured_at
                FROM ops_sector_universe_snapshot_daily
                WHERE trade_date = ? AND snapshot_id = ? AND provider_source = ?
                """,
                [canonical_date, snapshot_id, canonical_provider],
            ).fetchone()
            if existing is not None:
                if existing[0] != "published":
                    raise SectorUniverseValidationError(
                        f"snapshot already exists with status={existing[0]}"
                    )
                if existing[1:3] != (sector_count, declared_relationship_count):
                    raise SectorUniverseValidationError(
                        "persisted snapshot metadata does not match canonical rows"
                    )
                persisted_universe = self._con.execute(
                    """
                    SELECT sector_ts_code, sector_name, expected_stock_count,
                           provider_source, captured_at
                    FROM fact_sector_universe_daily
                    WHERE trade_date = ? AND snapshot_id = ?
                    ORDER BY sector_ts_code
                    """,
                    [canonical_date, snapshot_id],
                ).fetchall()
                expected_universe = [
                    (
                        row.sector_ts_code,
                        row.sector_name,
                        row.expected_stock_count,
                        canonical_provider,
                        existing[3],
                    )
                    for row in canonical_sectors
                ]
                if persisted_universe != expected_universe:
                    raise SectorUniverseValidationError(
                        "persisted universe does not match canonical snapshot rows"
                    )
                self._con.execute("COMMIT")
                return PublishedSectorSnapshot(
                    trade_date=canonical_date,
                    snapshot_id=snapshot_id,
                    provider_source=canonical_provider,
                    sector_count=sector_count,
                    declared_relationship_count=declared_relationship_count,
                    captured_at=existing[3],
                )

            self._con.execute(
                """
                INSERT INTO ops_sector_universe_snapshot_daily
                    (trade_date, snapshot_id, provider_source, sector_count,
                     declared_relationship_count, status, captured_at)
                VALUES (?, ?, ?, ?, ?, 'candidate', ?)
                """,
                [
                    canonical_date,
                    snapshot_id,
                    canonical_provider,
                    sector_count,
                    declared_relationship_count,
                    canonical_captured_at,
                ],
            )
            self._con.executemany(
                """
                INSERT INTO fact_sector_universe_daily
                    (trade_date, snapshot_id, sector_ts_code, sector_name,
                     expected_stock_count, provider_source, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        canonical_date,
                        snapshot_id,
                        row.sector_ts_code,
                        row.sector_name,
                        row.expected_stock_count,
                        canonical_provider,
                        canonical_captured_at,
                    )
                    for row in canonical_sectors
                ],
            )

            continuity = _adjacent_name_continuity(
                self._con,
                trade_date=canonical_date,
                snapshot_id=snapshot_id,
                provider_source=canonical_provider,
                sectors=canonical_sectors,
            )
            if continuity is not None:
                overlap, prior_count = continuity
                if prior_count <= 0 or overlap * 100 < prior_count * 95:
                    self._con.execute(
                        """
                        UPDATE ops_sector_universe_snapshot_daily
                        SET status = 'rejected'
                        WHERE trade_date = ? AND snapshot_id = ?
                          AND provider_source = ? AND status = 'candidate'
                        """,
                        [canonical_date, snapshot_id, canonical_provider],
                    )
                    self._con.execute("COMMIT")
                    raise _CommittedPublicationRejection(
                        f"name continuity below 95% ({overlap}/{prior_count})"
                    )

            self._con.execute(
                """
                UPDATE ops_sector_universe_snapshot_daily
                SET status = 'superseded'
                WHERE trade_date = ? AND provider_source = ?
                  AND status = 'published' AND snapshot_id <> ?
                """,
                [canonical_date, canonical_provider, snapshot_id],
            )
            self._con.execute(
                """
                UPDATE ops_sector_universe_snapshot_daily
                SET status = 'published'
                WHERE trade_date = ? AND snapshot_id = ? AND provider_source = ?
                  AND status = 'candidate'
                """,
                [canonical_date, snapshot_id, canonical_provider],
            )
            published_count = self._con.execute(
                """
                SELECT count(*) FROM ops_sector_universe_snapshot_daily
                WHERE trade_date = ? AND provider_source = ? AND status = 'published'
                """,
                [canonical_date, canonical_provider],
            ).fetchone()[0]
            if published_count != 1:
                raise SectorUniverseValidationError(
                    "publication must leave exactly one published snapshot"
                )

            self._con.executemany(
                """
                INSERT INTO dim_sector
                    (sector_ts_code, sector_name, sw_l1, is_active,
                     first_seen_date, last_seen_date, source, updated_at)
                VALUES (?, ?, ?, true, ?, ?, ?, ?)
                ON CONFLICT (sector_ts_code) DO UPDATE SET
                    sector_name = excluded.sector_name,
                    sw_l1 = coalesce(excluded.sw_l1, dim_sector.sw_l1),
                    is_active = true,
                    first_seen_date = coalesce(
                        least(dim_sector.first_seen_date, excluded.first_seen_date),
                        dim_sector.first_seen_date,
                        excluded.first_seen_date
                    ),
                    last_seen_date = coalesce(
                        greatest(dim_sector.last_seen_date, excluded.last_seen_date),
                        dim_sector.last_seen_date,
                        excluded.last_seen_date
                    ),
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        row.sector_ts_code,
                        row.sector_name,
                        row.sw_l1,
                        canonical_date,
                        canonical_date,
                        canonical_provider,
                        canonical_captured_at,
                    )
                    for row in canonical_sectors
                ],
            )
            self._con.execute(
                """
                UPDATE dim_sector AS d
                SET is_active = false, updated_at = ?
                WHERE d.source = ? AND d.is_active IS TRUE
                  AND NOT EXISTS (
                    SELECT 1 FROM fact_sector_universe_daily AS u
                    WHERE u.trade_date = ? AND u.snapshot_id = ?
                      AND u.sector_ts_code = d.sector_ts_code
                  )
                """,
                [
                    canonical_captured_at,
                    canonical_provider,
                    canonical_date,
                    snapshot_id,
                ],
            )
            self._con.executemany(
                """
                INSERT INTO ops_sector_member_sync_daily
                    (trade_date, snapshot_id, sector_ts_code, status,
                     expected_stock_count, attempt_count)
                VALUES (?, ?, ?, 'pending', ?, 0)
                """,
                [
                    (
                        canonical_date,
                        snapshot_id,
                        row.sector_ts_code,
                        row.expected_stock_count,
                    )
                    for row in canonical_sectors
                ],
            )
            self._con.execute("COMMIT")
        except _CommittedPublicationRejection as exc:
            raise SectorUniverseValidationError(str(exc)) from None
        except Exception:
            self._con.execute("ROLLBACK")
            raise
        return published

    @staticmethod
    def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
        """建代际 schema, 并把遗留的两张物理事实表一次性迁进代际存储。

        幂等: 表已经是视图时只重放 DDL, 不再迁移。整个过程在单个事务里,
        任何一步失败都回滚, 遗留表保持原名原状。
        """
        con.execute("BEGIN TRANSACTION")
        try:
            pending: list[tuple[str, str]] = []
            for public_name, legacy_name, generation_name in _MIGRATIONS:
                if _table_type(con, public_name) == "BASE TABLE":
                    _drop_dependent_indexes(con, public_name)
                    con.execute(f'ALTER TABLE "{public_name}" RENAME TO "{legacy_name}"')
                    pending.append((legacy_name, generation_name))

            con.execute(SECTOR_SCHEMA_PATH.read_text(encoding="utf-8"))

            for legacy_name, generation_name in pending:
                _copy_legacy_rows(
                    con,
                    legacy_name=legacy_name,
                    generation_name=generation_name,
                )
            for legacy_name, _generation_name in pending:
                con.execute(f'DROP TABLE "{legacy_name}"')
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

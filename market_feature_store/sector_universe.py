"""板块宇宙 (sector universe) 深模块。

这是生产代码里唯一允许触碰物理代际表
(`fact_sector_daily_generation` / `fact_sector_stock_daily_generation`) 以及
快照/回执表的地方。对外公开的 `fact_sector_daily` /
`fact_sector_stock_daily` 是只读视图, 只暴露某个交易日「唯一已发布代际」,
因此读者不会跨代际混池, 也不需要知道底层存储。

本文件当前实现 Task 2-4 的范围: schema 装载、幂等 legacy 迁移、每日宇宙
验证/发布、active identities 所有权以及完整的 published-generation 板块日行情
替换。成员结果 (Task 5) 和完成审计 (Task 7) 在后续任务中按同一接口边界补齐。
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    sectors: tuple[SectorDescriptor, ...]


@dataclass(frozen=True, slots=True)
class MemberWorkItem:
    """一个仍需抓取成分的板块。分母来自快照声明, 不是抓到多少算多少。"""

    sector_ts_code: str
    sector_name: str
    expected_stock_count: int
    attempt_count: int
    status: str


@dataclass(frozen=True, slots=True)
class MemberResult:
    """一次成分抓取的结果。

    三态而非布尔: ``empty`` 与 ``error`` 都可重试但含义不同——前者是 provider
    确实返回空, 后者是抓取失败。分开记账才能在夜间编排里区分"这个板块今天
    真没成分"和"我们还没成功问到"。
    """

    kind: str  # success | empty | error
    served_date: str | None = None
    stocks: tuple[Mapping[str, object], ...] = ()
    error_code: str | None = None

    @classmethod
    def success(
        cls,
        *,
        served_date: str,
        stocks: Sequence[Mapping[str, object]],
    ) -> MemberResult:
        return cls(kind="success", served_date=served_date, stocks=tuple(stocks))

    @classmethod
    def empty(cls) -> MemberResult:
        return cls(kind="empty")

    @classmethod
    def error(cls, error_code: str) -> MemberResult:
        return cls(kind="error", error_code=_canonical_text(error_code) or "unknown")


@dataclass(frozen=True, slots=True)
class CompletionAudit:
    """一个交易日的精确完成度。夜间编排唯一的停止条件。

    存在的理由: 各处自造"完成"公式会各自漂移——旧的编排循环拿
    ``count(distinct sector_ts_code)`` 当分子、``count(*) from dim_sector``
    当分母, 两个数不同源, 分子会把降级复制写的行算作完成, 分母会把当日宇宙
    里没有的陈旧身份算进去。审计只认已发布快照的声明。
    """

    trade_date: date
    snapshot_id: str | None
    declared_sector_count: int
    declared_relationship_count: int
    status_counts: Mapping[str, int]
    missing_tables: tuple[str, ...]
    complete: bool
    # 逐项对账，而不是"看起来齐了"。名称连续性 100% 也可能只有 406/407 条关系。
    actual_relationship_count: int = 0
    relationships_match: bool = False
    daily_identities_match: bool = False
    member_identities_contained: bool = False
    critical_null_count: int = 0
    # 相邻已发布代际的板块名重合率。首个代际没有基准可比，为 None——不伪造 100%。
    name_continuity: float | None = None
    # provider 声明数减去明细实际给到的数，按成功回执逐板块累加。
    # 精确性的定义是「实际 + 本字段 == 声明」，即没有**未记录**的缺口。
    declared_shortfall: int = 0

    @property
    def success_count(self) -> int:
        return int(self.status_counts.get("success", 0))

    @property
    def pending_count(self) -> int:
        return int(self.status_counts.get("pending", 0))

    @property
    def retriable_error_count(self) -> int:
        return sum(
            int(self.status_counts.get(status, 0))
            for status in _RETRIABLE_MEMBER_STATUSES
        )

    def brief(self) -> str:
        """一行可进日志的进度摘要, 始终带 snapshot_id 以便跨轮核对。"""
        if self.snapshot_id is None:
            return f"{self.trade_date} no published universe"
        mismatches = [
            name
            for name, ok in (
                ("relationships", self.relationships_match),
                ("daily_identities", self.daily_identities_match),
                ("member_identities", self.member_identities_contained),
            )
            if not ok
        ]
        continuity = (
            "-" if self.name_continuity is None else f"{self.name_continuity:.0%}"
        )
        return (
            f"{self.trade_date} snapshot={self.snapshot_id[:12]} "
            f"success={self.success_count}/{self.declared_sector_count} "
            f"rel={self.actual_relationship_count}+{self.declared_shortfall}"
            f"/{self.declared_relationship_count} "
            f"pending={self.pending_count} retriable={self.retriable_error_count} "
            f"nulls={self.critical_null_count} continuity={continuity} "
            f"missing_tables={','.join(self.missing_tables) or '-'} "
            f"mismatch={','.join(mismatches) or '-'}"
        )


@dataclass(frozen=True, slots=True)
class MemberReceipt:
    """成分回执的对外投影。调用方据此判断是否成功, 无需再查表。"""

    sector_ts_code: str
    status: str
    attempt_count: int
    expected_stock_count: int
    actual_stock_count: int | None
    last_error_code: str | None


# provider 数据问题记成 error 回执 (可重试、可审计); 身份/代际问题直接抛错
# (调用方传错了东西, 留回执只会污染台账)。
_MEMBER_COUNT_MISMATCH = "member_count_mismatch"
_MEMBER_SURPLUS = "member_count_surplus"
_MEMBER_SHORTFALL_TOO_LARGE = "member_shortfall_exceeds_bound"

# provider 的明细接口会遗漏极少数已声明成员。2026-07-30 全量实测（403 个板块、
# 声明 52,734 条关系）：
#   缺口分布 -1×82、-2×15、-4×2、-5×2，其余 302 个板块精确一致
#   实际缺失 130 条 = 全局单只缺失率 0.2465%（失败板块内 0.522%）
#   通过率随板块规模单调下降（<50 只 88% → ≥400 只 33%），与「每只成员有约
#   0.25% 独立概率不出现在明细里」的模型吻合
#
# 原先要求「实际 == 声明」才算成功，后果是 0.25% 的缺失造成 47% 的数据被拒：
# 101 个板块整块落库 0 行，共 24,772 条好关系连带丢弃，且集中在机器人概念、
# 人工智能、新能源车、芯片、储能等主线题材上。用零行抗议 0.5% 的缺失，得到的
# 数据严格劣于 1203/1205。
#
# 现在的精确性定义：实际 + 记录在案的缺口 == 声明。缺口逐板块记录（由
# expected_stock_count - actual_stock_count 推导），审计汇总上报，因此没有任何
# 东西被隐藏。上界存在的意义是区分「provider 的已知微量遗漏」和「明细被截断」
# ——后者通常丢远超 5%，仍然 fail-closed。
MEMBER_SHORTFALL_MAX_RATIO = 0.05
# 绝对下限：纯比例上界对小板块过严。「1205 只缺 2」和「14 只缺 1」是同一类事件
# （单只成员未出现在明细里），但 14×5% = 0.7，缺 1 只就超界——实测确实把
# 日用化工(21)、摩托车(14)、疫苗(14)、化妆品(13) 等 7 个小板块全拒了。
# 取 5 是因为全量实测的最大绝对缺口就是 5；再大的缺口才可能是截断。
MEMBER_SHORTFALL_MAX_ABSOLUTE = 5


def _member_shortfall_bound(expected_count: int) -> float:
    """允许的最大缺口：绝对下限与比例上界取大者。"""
    return max(
        float(MEMBER_SHORTFALL_MAX_ABSOLUTE),
        expected_count * MEMBER_SHORTFALL_MAX_RATIO,
    )
_MEMBER_SERVED_DATE_MISMATCH = "served_date_mismatch"
_MEMBER_DUPLICATE_IDENTITY = "duplicate_member_identity"
_MEMBER_EMPTY_IDENTITY = "empty_member_identity"

_RETRIABLE_MEMBER_STATUSES = ("empty", "error")

# 对外声明表名 -> 其物理代际表。审计只查代际表, 因为公开视图会把 legacy
# 迁移行也暴露出来, 用它做分子会把历史行当成今天的完成度。
_DECLARED_GENERATION_TABLES = {
    "fact_sector_daily": "fact_sector_daily_generation",
    "fact_sector_stock_daily": "fact_sector_stock_daily_generation",
}

# 关键字段：为空即该行不构成有效事实。板块日线取双红判断依赖的三列
# （pct_chg/amount/diff_ratio 见 strategy1-matrix 的严格双红定义），成分取身份两列。
_CRITICAL_COLUMNS = {
    "fact_sector_daily_generation": (
        "sector_ts_code",
        "pct_chg",
        "amount",
        "diff_ratio",
    ),
    "fact_sector_stock_daily_generation": ("stock_ts_code", "stock_name"),
}


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
    sectors: Sequence[SectorDescriptor],
) -> tuple[SectorDescriptor, ...]:
    normalized: list[SectorDescriptor] = []
    codes: set[str] = set()
    for raw in sectors:
        if not isinstance(raw, SectorDescriptor):
            raise SectorUniverseValidationError("all sectors must be SectorDescriptor values")
        code = _canonical_text(raw.sector_ts_code).upper()
        name = _canonical_text(raw.sector_name)
        if not code or not name:
            raise SectorUniverseValidationError("sector code and name must be non-empty")
        # 身份是 sector_ts_code；sector_name 按设计只是 display name，要求非空但
        # 不要求唯一（见设计文档「all codes and identity rows are unique; names are
        # non-empty」）。实现原先额外要求名称唯一，比规格严，结果被真实数据卡死：
        # fupanhui 有两个同名不同码的板块 990143.FP「国防军工」530 只 与
        # 990144.FP「国防军工」136 只，导致整份宇宙拒绝发布、夜间管线停摆。
        if code in codes:
            raise SectorUniverseValidationError("sector identities must be unique")
        if type(raw.expected_stock_count) is not int or raw.expected_stock_count <= 0:
            raise SectorUniverseValidationError("expected_stock_count must be a positive integer")
        sw_l1 = _canonical_text(raw.sw_l1) if raw.sw_l1 is not None else None
        normalized.append(
            SectorDescriptor(code, name, raw.expected_stock_count, sw_l1 or None)
        )
        codes.add(code)
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

    def published_snapshot(
        self,
        trade_date: str | date,
        provider_source: str = "fupanhui",
    ) -> PublishedSectorSnapshot:
        """Return and revalidate the single published generation for one date."""
        canonical_date = _normalize_trade_date(trade_date)
        canonical_provider = _canonical_text(provider_source).casefold()
        headers = self._con.execute(
            """
            SELECT snapshot_id, sector_count, declared_relationship_count, captured_at
            FROM ops_sector_universe_snapshot_daily
            WHERE trade_date = ? AND provider_source = ? AND status = 'published'
            """,
            [canonical_date, canonical_provider],
        ).fetchall()
        if len(headers) != 1:
            raise SectorUniverseValidationError(
                "expected exactly one published snapshot for trade date and provider"
            )
        snapshot_id, sector_count, declared_relationship_count, captured_at = headers[0]
        sector_rows = self._con.execute(
            """
            SELECT u.sector_ts_code, u.sector_name, u.expected_stock_count, d.sw_l1
            FROM fact_sector_universe_daily AS u
            LEFT JOIN dim_sector AS d ON d.sector_ts_code = u.sector_ts_code
            WHERE u.trade_date = ? AND u.snapshot_id = ? AND u.provider_source = ?
            ORDER BY u.sector_ts_code
            """,
            [canonical_date, snapshot_id, canonical_provider],
        ).fetchall()
        sectors = _normalize_sectors(
            tuple(
                SectorDescriptor(code, name, expected_count, sw_l1)
                for code, name, expected_count, sw_l1 in sector_rows
            )
        )
        if (
            len(sectors) != sector_count
            or sum(row.expected_stock_count for row in sectors)
            != declared_relationship_count
            or _snapshot_id(
                trade_date=canonical_date,
                provider_source=canonical_provider,
                sectors=sectors,
            )
            != snapshot_id
        ):
            raise SectorUniverseValidationError(
                "published snapshot header and universe rows do not match"
            )
        return PublishedSectorSnapshot(
            trade_date=canonical_date,
            snapshot_id=snapshot_id,
            provider_source=canonical_provider,
            sector_count=int(sector_count),
            declared_relationship_count=int(declared_relationship_count),
            captured_at=captured_at,
            sectors=sectors,
        )

    def publish_snapshot(
        self,
        *,
        trade_date: str | date,
        provider_source: str,
        sectors: Sequence[SectorDescriptor],
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
            sectors=canonical_sectors,
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
                    sectors=canonical_sectors,
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

    def replace_sector_daily(
        self,
        snapshot_id: str,
        rows: Sequence[Mapping[str, object]],
    ) -> int:
        """Atomically replace the complete daily-fact generation for a snapshot."""
        header_rows = self._con.execute(
            """
            SELECT trade_date, provider_source
            FROM ops_sector_universe_snapshot_daily
            WHERE snapshot_id = ? AND status = 'published'
            """,
            [snapshot_id],
        ).fetchall()
        if len(header_rows) != 1:
            raise SectorUniverseValidationError(
                "sector daily replacement requires one published snapshot"
            )
        snapshot = self.published_snapshot(header_rows[0][0], header_rows[0][1])
        if snapshot.snapshot_id != snapshot_id:
            raise SectorUniverseValidationError(
                "snapshot is not the published generation for its trade date"
            )

        by_code: dict[str, Mapping[str, object]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                raise SectorUniverseValidationError("sector daily rows must be mappings")
            code = _canonical_text(row.get("sector_ts_code", "")).upper()
            if not code or code in by_code:
                raise SectorUniverseValidationError(
                    "sector daily identities must be non-empty and unique"
                )
            by_code[code] = row

        expected_by_code = {row.sector_ts_code: row for row in snapshot.sectors}
        if set(by_code) != set(expected_by_code):
            missing = len(set(expected_by_code) - set(by_code))
            foreign = len(set(by_code) - set(expected_by_code))
            raise SectorUniverseValidationError(
                f"sector daily batch must exactly match universe (missing={missing}, foreign={foreign})"
            )

        now = datetime.now()
        insert_rows = []
        for code in sorted(expected_by_code):
            descriptor = expected_by_code[code]
            row = by_code[code]
            insert_rows.append(
                (
                    snapshot.trade_date,
                    snapshot.snapshot_id,
                    code,
                    descriptor.sector_name,
                    descriptor.sw_l1,
                    row.get("pct_chg"),
                    row.get("amount"),
                    row.get("diff_ratio"),
                    row.get("strength"),
                    row.get("multi_period_resonance"),
                    row.get("multi_period_source"),
                    row.get("multi_period_updated_at"),
                    _canonical_text(row.get("source") or snapshot.provider_source),
                    row.get("updated_at") or now,
                )
            )

        self._con.execute("BEGIN TRANSACTION")
        try:
            still_published = self._con.execute(
                """
                SELECT count(*) FROM ops_sector_universe_snapshot_daily
                WHERE trade_date = ? AND snapshot_id = ?
                  AND provider_source = ? AND status = 'published'
                """,
                [snapshot.trade_date, snapshot.snapshot_id, snapshot.provider_source],
            ).fetchone()[0]
            if still_published != 1:
                raise SectorUniverseValidationError(
                    "snapshot stopped being published before sector daily replacement"
                )
            self._con.execute(
                """
                DELETE FROM fact_sector_daily_generation
                WHERE trade_date = ? AND sector_universe_snapshot_id = ?
                """,
                [snapshot.trade_date, snapshot.snapshot_id],
            )
            self._con.executemany(
                """
                INSERT INTO fact_sector_daily_generation
                    (trade_date, sector_universe_snapshot_id, sector_ts_code,
                     sector_name, sw_l1, pct_chg, amount, diff_ratio, strength,
                     multi_period_resonance, multi_period_source,
                     multi_period_updated_at, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                insert_rows,
            )
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise
        return len(insert_rows)

    def _published_header(self, snapshot_id: str) -> tuple[date, str]:
        """解析并校验 snapshot_id 对应唯一 published 表头, 返回 (交易日, provider)。"""
        rows = self._con.execute(
            """
            SELECT trade_date, provider_source
            FROM ops_sector_universe_snapshot_daily
            WHERE snapshot_id = ? AND status = 'published'
            """,
            [_canonical_text(snapshot_id)],
        ).fetchall()
        if len(rows) != 1:
            raise SectorUniverseValidationError(
                "member work requires exactly one published snapshot"
            )
        return rows[0][0], rows[0][1]

    def completion_audit(
        self,
        trade_date: str | date,
        *,
        declared_tables: frozenset[str] = frozenset({"fact_sector_stock_daily"}),
    ) -> CompletionAudit:
        """审计某交易日相对已发布宇宙的精确完成度。

        fail-closed: 没有唯一已发布表头就 ``complete=False`` 且
        ``snapshot_id=None``——绝不把"没有宇宙"当成"没有缺口"。
        """
        if not declared_tables:
            # 收窄声明范围不得成为拿绿灯的手段：不声明任何表就等于不检查。
            raise SectorUniverseValidationError(
                "completion audit requires at least one declared table"
            )
        unknown_tables = sorted(set(declared_tables) - set(_DECLARED_GENERATION_TABLES))
        if unknown_tables:
            raise SectorUniverseValidationError(
                f"unknown declared tables: {', '.join(unknown_tables)}"
            )
        canonical_date = _normalize_trade_date(trade_date)
        headers = self._con.execute(
            """
            SELECT snapshot_id, sector_count, declared_relationship_count,
                   provider_source
            FROM ops_sector_universe_snapshot_daily
            WHERE trade_date = ? AND status = 'published'
            """,
            [canonical_date],
        ).fetchall()
        if len(headers) != 1:
            return CompletionAudit(
                trade_date=canonical_date,
                snapshot_id=None,
                declared_sector_count=0,
                declared_relationship_count=0,
                status_counts={},
                missing_tables=tuple(sorted(declared_tables)),
                complete=False,
            )
        snapshot_id, sector_count, relationship_count, provider_source = headers[0]

        counts = {
            row[0]: int(row[1])
            for row in self._con.execute(
                """
                SELECT status, count(*)
                FROM ops_sector_member_sync_daily
                WHERE trade_date = ? AND snapshot_id = ?
                GROUP BY status
                """,
                [canonical_date, snapshot_id],
            ).fetchall()
        }

        # 每张声明表都必须在本代际下有行。成分抓全但板块日线未写, 同样不算完成。
        # 所有计数都限定 sector_universe_snapshot_id = 本代际, 因此 legacy 迁移行
        # 与被取代代际自然被排除, 不会把历史行算成今天的完成度。
        missing: list[str] = []
        critical_nulls = 0
        for table in sorted(declared_tables):
            generation_table = _DECLARED_GENERATION_TABLES[table]
            present = self._con.execute(
                f"""
                SELECT count(DISTINCT sector_ts_code) FROM "{generation_table}"
                WHERE trade_date = ? AND sector_universe_snapshot_id = ?
                """,
                [canonical_date, snapshot_id],
            ).fetchone()[0]
            if int(present) != int(sector_count):
                missing.append(table)
            null_clause = " OR ".join(
                f'"{column}" IS NULL' for column in _CRITICAL_COLUMNS[generation_table]
            )
            critical_nulls += int(
                self._con.execute(
                    f"""
                    SELECT count(*) FROM "{generation_table}"
                    WHERE trade_date = ? AND sector_universe_snapshot_id = ?
                      AND ({null_clause})
                    """,
                    [canonical_date, snapshot_id],
                ).fetchone()[0]
            )

        declared_codes = {
            row[0]
            for row in self._con.execute(
                """
                SELECT sector_ts_code FROM fact_sector_universe_daily
                WHERE trade_date = ? AND snapshot_id = ?
                """,
                [canonical_date, snapshot_id],
            ).fetchall()
        }
        daily_codes = {
            row[0]
            for row in self._con.execute(
                """
                SELECT DISTINCT sector_ts_code FROM fact_sector_daily_generation
                WHERE trade_date = ? AND sector_universe_snapshot_id = ?
                """,
                [canonical_date, snapshot_id],
            ).fetchall()
        }
        member_rows = self._con.execute(
            """
            SELECT sector_ts_code, count(*) FROM fact_sector_stock_daily_generation
            WHERE trade_date = ? AND sector_universe_snapshot_id = ?
            GROUP BY sector_ts_code
            """,
            [canonical_date, snapshot_id],
        ).fetchall()
        member_codes = {row[0] for row in member_rows}
        actual_relationships = sum(int(row[1]) for row in member_rows)

        # 已记录的缺口：成功回执上「声明 − 实际」之和。
        shortfall = int(
            self._con.execute(
                """
                SELECT coalesce(sum(expected_stock_count - actual_stock_count), 0)
                FROM ops_sector_member_sync_daily
                WHERE trade_date = ? AND snapshot_id = ? AND status = 'success'
                  AND actual_stock_count IS NOT NULL
                """,
                [canonical_date, snapshot_id],
            ).fetchone()[0]
        )

        # 日线要求身份完全相等；成分允许尚未抓全（包含即可），但绝不允许出现
        # 快照外的板块——那是跨代际污染, 不是进度不足。
        daily_identities_match = daily_codes == declared_codes
        member_identities_contained = member_codes <= declared_codes
        # 精确性：实际 + 已记录缺口 == 声明。即不存在**未记录**的差额。
        # provider 明细会遗漏约 0.25% 的已声明成员（见 MEMBER_SHORTFALL_MAX_RATIO
        # 的实测依据），那部分逐板块记在回执上，不算未解释的缺口。
        relationships_match = (
            actual_relationships + shortfall == int(relationship_count)
        )

        continuity = _adjacent_name_continuity(
            self._con,
            trade_date=canonical_date,
            snapshot_id=snapshot_id,
            provider_source=provider_source,
            sectors=self.published_snapshot(canonical_date, provider_source).sectors,
        )
        name_continuity = (
            None
            if continuity is None or continuity[1] <= 0
            else continuity[0] / continuity[1]
        )

        complete = (
            int(counts.get("success", 0)) == int(sector_count)
            and not missing
            and relationships_match
            and daily_identities_match
            and member_identities_contained
            and critical_nulls == 0
        )
        return CompletionAudit(
            trade_date=canonical_date,
            snapshot_id=snapshot_id,
            declared_sector_count=int(sector_count),
            declared_relationship_count=int(relationship_count),
            status_counts=counts,
            missing_tables=tuple(missing),
            complete=complete,
            actual_relationship_count=actual_relationships,
            relationships_match=relationships_match,
            daily_identities_match=daily_identities_match,
            member_identities_contained=member_identities_contained,
            critical_null_count=critical_nulls,
            name_continuity=name_continuity,
            declared_shortfall=shortfall,
        )

    def has_published_universe(self, trade_date: str | date) -> bool:
        """该交易日是否已有已发布宇宙。历史前推复制的合格性判定用。"""
        return bool(
            self._con.execute(
                """
                SELECT count(*) FROM ops_sector_universe_snapshot_daily
                WHERE trade_date = ? AND status = 'published'
                """,
                [_normalize_trade_date(trade_date)],
            ).fetchone()[0]
        )

    def member_generation_row_count(self, trade_date: str | date | None = None) -> int:
        """物理代际表的成分行数。``trade_date`` 为 None 时统计全表。

        对外暴露这个计数，是为了让调用方不必自己碰物理表——物理读写只允许发生
        在本模块（见 scripts/check_sector_fact_access.py 的静态守卫）。
        """
        if trade_date is None:
            return int(
                self._con.execute(
                    "SELECT count(*) FROM fact_sector_stock_daily_generation"
                ).fetchone()[0]
            )
        return int(
            self._con.execute(
                """
                SELECT count(*) FROM fact_sector_stock_daily_generation
                WHERE trade_date = ?
                """,
                [_normalize_trade_date(trade_date)],
            ).fetchone()[0]
        )

    def latest_member_generation_date(self, before: str | date) -> date | None:
        """早于 ``before`` 且已有成分行的最近交易日。历史前推复制的取源用。"""
        row = self._con.execute(
            """
            SELECT max(trade_date) FROM fact_sector_stock_daily_generation
            WHERE trade_date < ?
            """,
            [_normalize_trade_date(before)],
        ).fetchone()
        return row[0] if row and row[0] else None

    def copy_legacy_member_generation(
        self,
        *,
        target_date: str | date,
        source_date: str | date,
    ) -> int:
        """把 ``source_date`` 的成分身份前推复制到 ``target_date`` 的 legacy 代际。

        只服务没有已发布宇宙的历史交易日：有表头就拒绝，因为凭空造出的成分会
        满足覆盖率查询却与 provider 声明矛盾。价格类字段一律置空——复制的是身份，
        不是当日行情。写入 ``sector_universe_snapshot_id='legacy'``，不产生成功回执。
        """
        target = _normalize_trade_date(target_date)
        source = _normalize_trade_date(source_date)
        published = self._con.execute(
            """
            SELECT count(*) FROM ops_sector_universe_snapshot_daily
            WHERE trade_date = ? AND status = 'published'
            """,
            [target],
        ).fetchone()[0]
        if published:
            raise SectorUniverseValidationError(
                f"{target} has a published universe; legacy copy is not eligible"
            )
        self._con.execute(
            """
            INSERT INTO fact_sector_stock_daily_generation
                (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                 sw_l1, stock_ts_code, stock_name,
                 price, pct_chg, amount, pct_chg_5d, pct_chg_10d, pct_chg_20d,
                 fund_flow_1d, fund_flow_5d, sw_industry, leader_plate,
                 leader_sub_plate, source, updated_at)
            SELECT
                ?, 'legacy', sector_ts_code, sector_name,
                sw_l1, stock_ts_code, stock_name,
                NULL, NULL, NULL, NULL, NULL, NULL,
                NULL, NULL, sw_industry, leader_plate,
                leader_sub_plate, 'incremental-copy', CURRENT_TIMESTAMP
            FROM fact_sector_stock_daily_generation
            WHERE trade_date = ?
            """,
            [target, source],
        )
        return self.member_generation_row_count(target)

    def next_member_work(
        self,
        snapshot_id: str,
        *,
        limit: int = 1,
        max_attempts: int = 3,
    ) -> tuple[MemberWorkItem, ...]:
        """取下一批仍需抓取的板块, 公平排序, 不会被失败板块饿死。

        排序: pending 优先于可重试的 empty/error; 然后按尝试次数升序、最久
        未尝试优先 (NULL 视为最久)、最后按代码稳定排序。因此一个反复失败的
        板块会自动排到队尾, 后面的板块不会永远拿不到配额。
        """
        trade_date, _provider = self._published_header(snapshot_id)
        if limit <= 0:
            return ()
        rows = self._con.execute(
            f"""
            SELECT m.sector_ts_code, u.sector_name, m.expected_stock_count,
                   m.attempt_count, m.status
            FROM ops_sector_member_sync_daily AS m
            JOIN fact_sector_universe_daily AS u
              ON u.trade_date = m.trade_date
             AND u.snapshot_id = m.snapshot_id
             AND u.sector_ts_code = m.sector_ts_code
            WHERE m.trade_date = ? AND m.snapshot_id = ?
              AND (
                    m.status = 'pending'
                 OR (m.status IN {_RETRIABLE_MEMBER_STATUSES} AND m.attempt_count < ?)
              )
            ORDER BY (m.status = 'pending') DESC,
                     m.attempt_count ASC,
                     m.last_attempted_at ASC NULLS FIRST,
                     m.sector_ts_code ASC
            LIMIT ?
            """,
            [trade_date, _canonical_text(snapshot_id), max_attempts, limit],
        ).fetchall()
        return tuple(
            MemberWorkItem(
                sector_ts_code=row[0],
                sector_name=row[1],
                expected_stock_count=int(row[2]),
                attempt_count=int(row[3]),
                status=row[4],
            )
            for row in rows
        )

    def record_member_result(
        self,
        snapshot_id: str,
        sector_ts_code: str,
        result: MemberResult,
    ) -> MemberReceipt:
        """记录一次成分抓取结果, 成功时在同一事务里替换该板块的代际成分行。

        校验顺序即失败语义: 身份/代际错误抛异常 (调用方传错了东西, 不留回执);
        provider 数据问题 (日期不符/重复代码/数量不等于声明) 记成 error 回执,
        既保留可重试性, 又让"缺了多少"在台账上可见——这正是本任务要消灭的
        "静默丢失的工作"。
        """
        trade_date, provider = self._published_header(snapshot_id)
        canonical_snapshot = _canonical_text(snapshot_id)
        code = _canonical_text(sector_ts_code).upper()
        descriptor = self._con.execute(
            """
            SELECT u.sector_name, u.expected_stock_count, d.sw_l1
            FROM fact_sector_universe_daily AS u
            LEFT JOIN dim_sector AS d ON d.sector_ts_code = u.sector_ts_code
            WHERE u.trade_date = ? AND u.snapshot_id = ? AND u.sector_ts_code = ?
            """,
            [trade_date, canonical_snapshot, code],
        ).fetchone()
        if descriptor is None:
            raise SectorUniverseValidationError(
                f"sector {code or '<empty>'} is not declared by the published universe"
            )
        sector_name, expected_count, sw_l1 = descriptor[0], int(descriptor[1]), descriptor[2]

        error_code: str | None = None
        stock_rows: list[tuple] = []
        now = datetime.now()

        if result.kind == "error":
            error_code = result.error_code or "unknown"
        elif result.kind == "success":
            try:
                served = _normalize_trade_date(result.served_date or "")
            except Exception:
                served = None
            if served != trade_date:
                error_code = _MEMBER_SERVED_DATE_MISMATCH
            else:
                seen: set[str] = set()
                for row in result.stocks:
                    stock_code = _canonical_text(row.get("ts_code", "")).upper()
                    if not stock_code:
                        error_code = _MEMBER_EMPTY_IDENTITY
                        break
                    if stock_code in seen:
                        error_code = _MEMBER_DUPLICATE_IDENTITY
                        break
                    seen.add(stock_code)
                    stock_rows.append(
                        self._member_row(
                            trade_date=trade_date,
                            snapshot_id=canonical_snapshot,
                            sector_ts_code=code,
                            sector_name=sector_name,
                            sw_l1=sw_l1,
                            stock_ts_code=stock_code,
                            row=row,
                            provider=provider,
                            now=now,
                        )
                    )
                if error_code is None:
                    delivered = len(stock_rows)
                    if delivered > expected_count:
                        # 多出来的成员意味着拿到了别的宇宙，不是遗漏，必须拒绝。
                        error_code = _MEMBER_SURPLUS
                    elif expected_count - delivered > _member_shortfall_bound(
                        expected_count
                    ):
                        error_code = _MEMBER_SHORTFALL_TOO_LARGE

        status = "success" if (result.kind == "success" and error_code is None) else (
            "empty" if result.kind == "empty" else "error"
        )
        actual_count = len(stock_rows) if status == "success" else None

        self._con.execute("BEGIN TRANSACTION")
        try:
            still_published = self._con.execute(
                """
                SELECT count(*) FROM ops_sector_universe_snapshot_daily
                WHERE trade_date = ? AND snapshot_id = ? AND status = 'published'
                """,
                [trade_date, canonical_snapshot],
            ).fetchone()[0]
            if still_published != 1:
                raise SectorUniverseValidationError(
                    "snapshot stopped being published before member commit"
                )
            if status == "success":
                # 只替换本板块本代际的行: 其他板块已同步的结果不受影响。
                self._con.execute(
                    """
                    DELETE FROM fact_sector_stock_daily_generation
                    WHERE trade_date = ? AND sector_universe_snapshot_id = ?
                      AND sector_ts_code = ?
                    """,
                    [trade_date, canonical_snapshot, code],
                )
                self._con.executemany(
                    """
                    INSERT INTO fact_sector_stock_daily_generation
                        (trade_date, sector_universe_snapshot_id, sector_ts_code,
                         sector_name, sw_l1, stock_ts_code, stock_name, price,
                         pct_chg, amount, pct_chg_3d, pct_chg_5d, pct_chg_10d,
                         pct_chg_20d, high_status, high_status_label, limit_times,
                         fund_flow_1d, fund_flow_5d, sw_industry, leader_plate,
                         leader_sub_plate, role_tags_json, circ_mv, float_mcap_yi,
                         total_mcap_yi, free_float_mcap_yi, mcap_source, source,
                         updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    stock_rows,
                )
            self._con.execute(
                """
                UPDATE ops_sector_member_sync_daily
                SET status = ?,
                    actual_stock_count = ?,
                    attempt_count = attempt_count + 1,
                    last_error_code = ?,
                    first_attempted_at = coalesce(first_attempted_at, ?),
                    last_attempted_at = ?,
                    completed_at = CASE WHEN ? = 'success' THEN ? ELSE NULL END
                WHERE trade_date = ? AND snapshot_id = ? AND sector_ts_code = ?
                """,
                [
                    status,
                    actual_count,
                    error_code,
                    now,
                    now,
                    status,
                    now,
                    trade_date,
                    canonical_snapshot,
                    code,
                ],
            )
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise

        row = self._con.execute(
            """
            SELECT status, attempt_count, expected_stock_count,
                   actual_stock_count, last_error_code
            FROM ops_sector_member_sync_daily
            WHERE trade_date = ? AND snapshot_id = ? AND sector_ts_code = ?
            """,
            [trade_date, canonical_snapshot, code],
        ).fetchone()
        return MemberReceipt(
            sector_ts_code=code,
            status=row[0],
            attempt_count=int(row[1]),
            expected_stock_count=int(row[2]),
            actual_stock_count=None if row[3] is None else int(row[3]),
            last_error_code=row[4],
        )

    @staticmethod
    def _member_row(
        *,
        trade_date: date,
        snapshot_id: str,
        sector_ts_code: str,
        sector_name: str,
        sw_l1: object,
        stock_ts_code: str,
        row: Mapping[str, object],
        provider: str,
        now: datetime,
    ) -> tuple:
        return (
            trade_date,
            snapshot_id,
            sector_ts_code,
            sector_name,
            sw_l1,
            stock_ts_code,
            row.get("name") or row.get("stock_name"),
            row.get("price"),
            row.get("pct_chg"),
            row.get("amount"),
            row.get("pct_chg_3d"),
            row.get("pct_chg_5d"),
            row.get("pct_chg_10d"),
            row.get("pct_chg_20d"),
            row.get("high_status"),
            row.get("high_status_label"),
            row.get("limit_times"),
            row.get("fund_flow_1d"),
            row.get("fund_flow_5d"),
            row.get("sw_industry"),
            row.get("leader_plate"),
            row.get("leader_sub_plate"),
            row.get("role_tags_json"),
            row.get("circ_mv"),
            row.get("float_mcap_yi"),
            row.get("total_mcap_yi"),
            row.get("free_float_mcap_yi"),
            row.get("mcap_source"),
            _canonical_text(row.get("source") or provider),
            row.get("updated_at") or now,
        )

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

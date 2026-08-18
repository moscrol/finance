"""Delivery-layer facts the model must not be asked to recite.

Calendar closure, retired table names, empty-caliber disclosure,
subject-scoped caliber bind (dirty sector amount / copied stock rows /
theme limit heat), and a question-stated information cutoff are
deterministic. Prompting the model to mention them has failed in
production (R16/R18 C1; 2026-08-13 C2/C7/C8; 2026-08-18 C3/C4/C5/A5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from intelligence.services.research_contract import InformationCutoff
from intelligence.services.task_frame import TaskFrame

# 主库已退役、既非表也非视图的旧名 → canonical fact_*。问句命中旧名时，
# 交付层必须明说「表不存在」并给出替代，不能让模型改口成「把表贴过来」。
_RETIRED_TABLES: tuple[tuple[str, str], ...] = (
    ("sector_marginal", "fact_sector_daily"),
    ("daily_market", "fact_market_daily"),
    ("advancers", "fact_market_daily"),
)

# 只认站立日，不认区间起点。``market_review_requested_date`` 会把
# 「2026年7月1日至5日」收成 07-01，因果窗口上界会被截错。
_STANDING_CUTOFF_RE = re.compile(
    r"(?:站在\s*)?(?P<iso>\d{4}-\d{2}-\d{2})\s*(?:收盘|盘后|收市)"
    r"|(?:站在\s*)?(?P<cn>\d{4}年\d{1,2}月\d{1,2}日)\s*(?:收盘|盘后|收市)"
)


def calendar_disclosure(frame: TaskFrame) -> str | None:
    """任务假设里的休市事实（纯事实子句），没有则 None。

    单一事实源：``build_task_frame`` 已经判定过「金融题 + 问句日期休市」
    才注入该假设；交付层只读出，不重新判定。
    """

    for item in frame.assumptions:
        if "休市" in item:
            return item.split("；")[0].strip()
    return None


def with_calendar_disclosure(answer: str, frame: TaskFrame) -> str:
    """确定性前置休市事实——不依赖模型转述。"""

    disclosure = calendar_disclosure(frame)
    if disclosure is None or not answer.strip() or "休市" in answer:
        return answer
    return f"{disclosure}。\n{answer}"


_TECHNICAL_SNAPSHOT_RE = re.compile(r"技术面快照|技术快照")
_EMPTY_CALIBER_TABLE = "fact_stock_technical_snapshot"


def _count_table_rows(table: str) -> int | None:
    """Return row count, 0 if the table is missing, None if the DB cannot be probed."""

    from intelligence.paths import default_market_db_path

    path = default_market_db_path()
    if not path.is_file():
        return None
    try:
        import duckdb
    except Exception:
        return None
    con = None
    try:
        con = duckdb.connect(str(path), read_only=True)
        row = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
        return int(row[0] or 0) if row else 0
    except Exception as exc:
        text = str(exc).lower()
        if "does not exist" in text or "catalog" in text or "not found" in text:
            return 0
        return None
    finally:
        if con is not None:
            con.close()


def empty_caliber_disclosure(
    query: str,
    *,
    row_count: int | None = None,
    table: str = _EMPTY_CALIBER_TABLE,
) -> str | None:
    """目标口径空表时必须声明不可用，不得静默换表交付。

    缺表 ≡ 空表（C3）。库文件不存在或锁定时 fail-open，交给后面的车道。
    """

    if not _TECHNICAL_SNAPSHOT_RE.search(str(query or "")):
        return None
    counted = _count_table_rows(table) if row_count is None else row_count
    if counted is None or counted > 0:
        return None
    return (
        f"{table} 当前是空表（0 行），该技术面快照数据不可用。"
        "不会用价格表或其他口径替代。"
    )


def retired_table_disclosure(query: str) -> str | None:
    """问句点名已退役表时，给出「表不存在 + canonical 替代」的确定性说明。"""

    text = str(query or "")
    for old_name, canonical in _RETIRED_TABLES:
        if re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(old_name)}(?![A-Za-z0-9_-])",
            text,
        ):
            return f"`{old_name}` 表不存在。当前库请查 `{canonical}`。"
    return None


def requested_information_cutoff(
    query: str,
    *,
    today: str | None = None,
) -> InformationCutoff | None:
    """问句里的站立日（「站在 X 收盘」）成为 information_cutoff。

    「站在 2026-07-21 收盘，给出对 07-22 的研判」若 cutoff 落成今天，
    盘面快照会把 08-13 的数送进模型（C7 实测）。区间题（1 日至 5 日）
    不走这条——窗口上界由因果工具自己解析，避免把起点当成截止日。
    """

    match = _STANDING_CUTOFF_RE.search(str(query or ""))
    if match is None:
        return None
    raw = match.group("iso") or match.group("cn")
    try:
        if "年" in raw:
            requested_date = date(
                int(raw.split("年", 1)[0]),
                int(raw.split("年", 1)[1].split("月", 1)[0]),
                int(raw.split("月", 1)[1].rstrip("日")),
            )
        else:
            requested_date = date.fromisoformat(raw)
    except ValueError:
        return None
    try:
        runtime_date = date.fromisoformat(str(today or "")[:10])
    except ValueError:
        runtime_date = None
    if runtime_date is not None and requested_date > runtime_date:
        requested_date = runtime_date
    return InformationCutoff(requested_date, "requested")


UNREADABLE = object()
_LIVE = object()
_AMOUNT_OUTLIER = 100_000.0
_AMOUNT_VS_MEDIAN = 50.0
_MARKET_WIDE_NAMES = frozenset({"全市", "大盘", "a股", "市场", "全市场"})
_SECTOR_AMOUNT_RE = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<name>.+?)\s*板块?\s*成交额"
)
_STOCK_TWO_DAY_RE = re.compile(
    r"(?P<name>.+?)\s+(?P<d1>\d{4}-\d{2}-\d{2})\s*和\s*"
    r"(?P<d2>(?:\d{4}-)?\d{1,2}-\d{1,2}).{0,24}(?:涨了多少|收盘)"
)
_THEME_HEAT_RE = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2}).{0,24}(?:涨停集中|题材热度)"
)


@dataclass(frozen=True)
class SectorAmountRow:
    sector_name: str
    trade_date: str
    amount: float
    median_amount: float | None = None
    caliber: str = "fact_sector_daily.amount"


@dataclass(frozen=True)
class StockDailyRow:
    stock_name: str
    trade_date: str
    close: float
    pct_chg: float
    caliber: str = "fact_stock_daily"


@dataclass(frozen=True)
class ThemeHeatRow:
    sector_name: str
    limit_up_count: int
    trade_date: str
    caliber: str = "fact_theme_limit_heat_daily"


def _parse_sector_amount_query(query: str) -> tuple[str, str] | None:
    text = str(query or "").strip()
    match = _SECTOR_AMOUNT_RE.search(text)
    if match is None:
        return None
    name = match.group("name").strip()
    if not name or name.casefold() in _MARKET_WIDE_NAMES:
        return None
    return match.group("date"), name


def _probe_sector_amount(trade_date: str, sector_name: str) -> SectorAmountRow | object | None:
    from intelligence.paths import default_market_db_path

    path = default_market_db_path()
    if not path.is_file():
        return UNREADABLE
    try:
        import duckdb
    except Exception:
        return UNREADABLE
    con = None
    try:
        con = duckdb.connect(str(path), read_only=True)
        row = con.execute(
            """
            SELECT sector_name, amount
            FROM fact_sector_daily
            WHERE trade_date = ?
              AND (
                  sector_name = ?
                  OR sector_name ILIKE '%' || ? || '%'
              )
            ORDER BY CASE WHEN sector_name = ? THEN 0 ELSE 1 END, amount DESC
            LIMIT 1
            """,
            [trade_date, sector_name, sector_name, sector_name],
        ).fetchone()
        if row is None or row[1] is None:
            return None
        median_row = con.execute(
            "SELECT median(amount) FROM fact_sector_daily WHERE trade_date = ?",
            [trade_date],
        ).fetchone()
        median = float(median_row[0]) if median_row and median_row[0] is not None else None
        return SectorAmountRow(
            sector_name=str(row[0]),
            trade_date=trade_date,
            amount=float(row[1]),
            median_amount=median,
        )
    except Exception:
        return UNREADABLE
    finally:
        if con is not None:
            con.close()


def _format_sector_amount(row: SectorAmountRow) -> str:
    amount = row.amount
    amount_text = (
        f"{amount:.0f}" if float(amount).is_integer() else format(amount, ".10g")
    )
    head = (
        f"fact_sector_daily {row.trade_date} {row.sector_name} "
        f"成交额 amount={amount_text}（表内原值，未换算）。"
    )
    outlier = amount >= _AMOUNT_OUTLIER
    if row.median_amount not in (None, 0) and amount > _AMOUNT_VS_MEDIAN * row.median_amount:
        outlier = True
    if not outlier:
        return head
    median_bit = ""
    if row.median_amount is not None:
        median_bit = f"同日板块成交额中位数 {format(row.median_amount, '.10g')}。"
    return (
        f"{head}{median_bit}"
        "该值偏离正常量级，单位异常，不会按亿元或万亿报出。"
    )


def _complete_iso_date(raw: str, anchor: str) -> str | None:
    text = str(raw or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    match = re.fullmatch(r"(\d{1,2})-(\d{1,2})", text)
    if match is None or len(anchor) < 4:
        return None
    return f"{anchor[:4]}-{int(match.group(1)):02d}-{int(match.group(2)):02d}"


def _parse_two_day_stock_query(query: str) -> tuple[str, str, str] | None:
    text = str(query or "").strip()
    match = _STOCK_TWO_DAY_RE.search(text)
    if match is None:
        return None
    name = match.group("name").strip()
    first = match.group("d1")
    second = _complete_iso_date(match.group("d2"), first)
    if not name or second is None:
        return None
    return name, first, second


def _probe_two_day_stock(
    stock_name: str, first: str, second: str
) -> tuple[StockDailyRow, ...] | object | None:
    from intelligence.paths import default_market_db_path

    path = default_market_db_path()
    if not path.is_file():
        return UNREADABLE
    try:
        import duckdb
    except Exception:
        return UNREADABLE
    con = None
    try:
        con = duckdb.connect(str(path), read_only=True)
        rows = con.execute(
            """
            SELECT stock_name, CAST(trade_date AS VARCHAR), close, pct_chg
            FROM fact_stock_daily
            WHERE stock_name = ? AND trade_date IN (?, ?)
            ORDER BY trade_date
            """,
            [stock_name, first, second],
        ).fetchall()
        parsed = tuple(
            StockDailyRow(str(row[0]), str(row[1])[:10], float(row[2]), float(row[3]))
            for row in rows
            if row[2] is not None and row[3] is not None
        )
        return parsed if parsed else None
    except Exception:
        return UNREADABLE
    finally:
        if con is not None:
            con.close()


def _format_number(value: float) -> str:
    return f"{value:.0f}" if float(value).is_integer() else format(value, ".10g")


def _format_stock_days(rows: tuple[StockDailyRow, ...]) -> str:
    parts = [
        f"{row.trade_date} close={_format_number(row.close)} "
        f"pct_chg={_format_number(row.pct_chg)}"
        for row in rows
    ]
    head = f"fact_stock_daily {rows[0].stock_name} " + "；".join(parts) + "。"
    if len(rows) < 2:
        return head
    copied = (
        rows[0].close == rows[1].close and rows[0].pct_chg == rows[1].pct_chg
    )
    if not copied:
        return head
    return head + "两日收盘与涨幅完全相同，口径内部不一致。"


def _parse_theme_heat_query(query: str) -> str | None:
    match = _THEME_HEAT_RE.search(str(query or ""))
    if match is None:
        return None
    return match.group("date")


def _probe_theme_heat(trade_date: str) -> tuple[ThemeHeatRow, ...] | object | None:
    from intelligence.paths import default_market_db_path

    path = default_market_db_path()
    if not path.is_file():
        return UNREADABLE
    try:
        import duckdb
    except Exception:
        return UNREADABLE
    con = None
    try:
        con = duckdb.connect(str(path), read_only=True)
        rows = con.execute(
            """
            SELECT sector_name, limit_up_count
            FROM fact_theme_limit_heat_daily
            WHERE trade_date = ? AND COALESCE(limit_up_count, 0) >= 2
            ORDER BY limit_up_count DESC, market_share DESC
            LIMIT 8
            """,
            [trade_date],
        ).fetchall()
        parsed = tuple(
            ThemeHeatRow(str(row[0]), int(row[1]), trade_date)
            for row in rows
            if row[0] and row[1] is not None
        )
        return parsed if parsed else None
    except Exception:
        return UNREADABLE
    finally:
        if con is not None:
            con.close()


def _format_theme_heat(rows: tuple[ThemeHeatRow, ...]) -> str:
    ranking = "、".join(
        f"{row.sector_name} {row.limit_up_count} 家" for row in rows
    )
    return (
        f"fact_theme_limit_heat_daily {rows[0].trade_date} 涨停集中：{ranking}。"
    )


def bound_caliber_disclosure(
    query: str,
    *,
    sector_row: SectorAmountRow | object | None = _LIVE,
    stock_rows: tuple[StockDailyRow, ...] | object | None = _LIVE,
    heat_rows: tuple[ThemeHeatRow, ...] | object | None = _LIVE,
) -> str | None:
    """Subject-scoped 口径取值：取到原值，脏数必须标单位异常或内部矛盾。

    全市/大盘成交额不走这条——那是 fact_market_daily。库不可读 fail-open。
    """

    parsed_sector = _parse_sector_amount_query(query)
    if parsed_sector is not None:
        trade_date, sector_name = parsed_sector
        row = sector_row
        if row is _LIVE:
            row = _probe_sector_amount(trade_date, sector_name)
        if row is UNREADABLE or row is None:
            return None
        if not isinstance(row, SectorAmountRow):
            return None
        return _format_sector_amount(row)

    parsed_stock = _parse_two_day_stock_query(query)
    if parsed_stock is not None:
        stock_name, first, second = parsed_stock
        rows = stock_rows
        if rows is _LIVE:
            rows = _probe_two_day_stock(stock_name, first, second)
        if rows is UNREADABLE or rows is None:
            return None
        if not isinstance(rows, tuple) or not rows:
            return None
        if not all(isinstance(item, StockDailyRow) for item in rows):
            return None
        return _format_stock_days(rows)

    parsed_heat = _parse_theme_heat_query(query)
    if parsed_heat is not None:
        rows = heat_rows
        if rows is _LIVE:
            rows = _probe_theme_heat(parsed_heat)
        if rows is UNREADABLE or rows is None:
            return None
        if not isinstance(rows, tuple) or not rows:
            return None
        if not all(isinstance(item, ThemeHeatRow) for item in rows):
            return None
        return _format_theme_heat(rows)
    return None

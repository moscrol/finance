"""Delivery-layer facts the model must not be asked to recite.

Calendar closure, retired table names, empty-caliber disclosure, and a
question-stated information cutoff are deterministic. Prompting the model
to mention them has failed in production (R16/R18 C1; 2026-08-13 C2/C7/C8;
2026-08-18 C3).
"""

from __future__ import annotations

import re
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

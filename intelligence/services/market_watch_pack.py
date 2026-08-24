"""Deterministic market_watch component pack.

Four bags run before any owner/model fork. Explicit standing dates use
``trade_date = ?``. Implicit "today" first resolves ``max(trade_date)``, then
the same exact-day queries. Never fall back to a neighbor day.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.services import retrieval_cache
from intelligence.services.query_understanding import market_review_requested_date
from market_feature_store.signals import DOUBLE_RED_SQL

BAG_MARKET = "market_daily"
BAG_MAINLINE = "mainline"
BAG_DUAL_RED = "dual_red"
BAG_LIMIT_HEAT = "limit_heat"
REQUIRED_BAGS = (BAG_MARKET, BAG_MAINLINE, BAG_DUAL_RED, BAG_LIMIT_HEAT)


@dataclass(frozen=True)
class PackBag:
    name: str
    requested_date: str | None
    served_date: str | None
    status: str
    rows: tuple[dict[str, Any], ...]

    @property
    def empty(self) -> bool:
        return self.status != "hit"


@dataclass(frozen=True)
class MarketWatchPack:
    standing_date: str | None
    explicit: bool
    calendar_disclosure: str | None
    bags: tuple[PackBag, ...]

    def bag(self, name: str) -> PackBag | None:
        for item in self.bags:
            if item.name == name:
                return item
        return None

    @property
    def complete(self) -> bool:
        return {item.name for item in self.bags} >= set(REQUIRED_BAGS)

    @property
    def market_daily_empty(self) -> bool:
        bag = self.bag(BAG_MARKET)
        return bag is None or bag.empty

    @property
    def should_stop(self) -> bool:
        if self.calendar_disclosure:
            return True
        # 只有显式站立日且库里确认无该日行才停。库打不开时袋也是 empty，
        # 那是「没查成」不是「该日无行情」，停了会盖掉 daily-review / 旧答。
        return self.explicit and self.market_daily_empty

    def stop_text(self) -> str:
        if self.calendar_disclosure:
            text = self.calendar_disclosure
            return text if text.endswith("。") else f"{text}。"
        date = self.standing_date or "该日"
        return f"{date} 无行情数据。"

    def mainline_dual_red_gap(self) -> str | None:
        """主线 ∩ 严格双红为空时的缺口句（spec §1.1 / §7.3 #8）。

        主线是题材名、双红是板块名，两个名字空间靠文本包含对齐；
        对不上就必须写缺口，不许把「名单上有某题材」写成「当天在加量」。
        """

        mainline = self.bag(BAG_MAINLINE)
        if mainline is None or mainline.empty:
            return None
        mainline_names = [
            str(row.get("theme_name") or row.get("sector_name") or "")
            for row in mainline.rows
            if row.get("theme_name") or row.get("sector_name")
        ]
        if not mainline_names:
            return None
        dual = self.bag(BAG_DUAL_RED)
        dual_names = (
            [
                str(row.get("sector_name") or "")
                for row in dual.rows
                if row.get("sector_name")
            ]
            if dual is not None and not dual.empty
            else []
        )
        overlap = any(
            m and d and (m in d or d in m)
            for m in mainline_names
            for d in dual_names
        )
        if overlap:
            return None
        names = "、".join(mainline_names)
        return (
            f"- 缺口：主线题材（{names}）当日无对应板块进入严格双红，"
            "在榜不构成加量证据。"
        )

    def render(self) -> str:
        lines = ["## 指定日盘面组件包"]
        if self.standing_date:
            kind = "显式站立日" if self.explicit else "隐式最新交易日"
            lines.append(f"- {kind}：{self.standing_date}。")
        if self.calendar_disclosure:
            lines.append(f"- 日历：{self.stop_text()}")
        market = self.bag(BAG_MARKET)
        if market is None or market.empty:
            lines.append("- 总量袋：empty。")
        else:
            row = market.rows[0]
            lines.append(f"- 总量袋 served_date={market.served_date}。")
            lines.append(
                f"- 全市场成交额：{row.get('total_amount')} 亿元；"
                f"较前一日 {row.get('amount_vs_yesterday_pct')}%；"
                f"涨停 {row.get('limit_up')} 家；跌停 {row.get('limit_down')} 家；"
                f"上证 {row.get('sh_index_pct_chg')}%；"
                f"量能 {row.get('volume_state') or '未标注'}；"
                f"阶段 {row.get('market_stage') or '未标注'}"
                + (
                    f"（第 {row.get('stage_day')} 天）"
                    if row.get("stage_day") is not None
                    else ""
                )
                + "。"
            )
        mainline = self.bag(BAG_MAINLINE)
        if mainline is None or mainline.empty:
            lines.append("- 主线袋：该日无行。")
        else:
            names = "、".join(
                str(row.get("theme_name") or row.get("sector_name") or "")
                for row in mainline.rows
                if row.get("theme_name") or row.get("sector_name")
            )
            lines.append(f"- 主线袋 served_date={mainline.served_date}：{names}。")
        dual = self.bag(BAG_DUAL_RED)
        if dual is None or dual.empty:
            lines.append("- 严格双红 0 个。")
        else:
            names = "、".join(
                str(row.get("sector_name") or "")
                for row in dual.rows
                if row.get("sector_name")
            )
            lines.append(
                f"- 严格双红 served_date={dual.served_date}："
                f"{len(dual.rows)} 个（{names}）。"
            )
        gap = self.mainline_dual_red_gap()
        if gap:
            lines.append(gap)
        heat = self.bag(BAG_LIMIT_HEAT)
        if heat is None or heat.empty:
            lines.append("- 涨停热度该日无行。")
        else:
            names = "、".join(
                str(row.get("sector_name") or "")
                for row in heat.rows
                if row.get("sector_name")
            )
            lines.append(
                f"- 涨停热度 served_date={heat.served_date}：{names}。"
            )
        return "\n".join(lines)


def merge_into_public_answer(text: str, pack: MarketWatchPack | None) -> str:
    """Lock cells must reach the public answer even if daily-review owns prose."""

    if pack is None:
        return text
    if pack.should_stop:
        return pack.stop_text()
    if pack.market_daily_empty:
        return text
    rendered = pack.render()
    body = text or ""
    if not rendered:
        return body
    if rendered in body:
        return body
    # 不能因为 owner 正文里出现了总量数字就跳过合并：live 的
    # 2026-07-23-daily-review.md 含 21949.97，但它的「双红 1 个」是另一套
    # 口径——据此去重会让严格双红名单、涨停热度被 md 顶掉（spec §7.1 #2a）。
    return f"{rendered}\n\n{body}".strip() if body else rendered


def resolve_standing_date(
    query: str,
    *,
    cutoff: str | None = None,
) -> tuple[str | None, bool]:
    requested = market_review_requested_date(query)
    if requested:
        return requested, True
    if cutoff:
        return cutoff, True
    return None, False


def exact_market_daily_exists(
    market_db_path: str | Path | None,
    trade_date: str,
) -> bool | None:
    """True/False if the db is reachable; None if it cannot be opened."""

    con = _connect(market_db_path)
    if con is None:
        return None
    try:
        if not _has_table(con, "fact_market_daily"):
            return False
        row = con.execute(
            "select 1 from fact_market_daily where trade_date = cast(? as date) limit 1",
            [trade_date],
        ).fetchone()
        return row is not None
    except Exception:
        return None
    finally:
        con.close()


def run_market_watch_pack(
    query: str,
    *,
    market_db_path: str | Path | None,
    calendar_disclosure: str | None = None,
    cutoff: str | None = None,
) -> MarketWatchPack:
    standing, explicit = resolve_standing_date(query, cutoff=cutoff)
    con = _connect(market_db_path)
    if con is None:
        requested = standing
        empty = tuple(
            PackBag(name=name, requested_date=requested, served_date=None, status="empty", rows=())
            for name in REQUIRED_BAGS
        )
        return MarketWatchPack(
            standing_date=standing,
            explicit=explicit,
            calendar_disclosure=calendar_disclosure,
            bags=empty,
        )
    try:
        if not explicit:
            standing = _latest_market_date(con)
        bags = (
            _query_market_daily(con, standing),
            _query_mainline(con, standing),
            _query_dual_red(con, standing),
            _query_limit_heat(con, standing),
        )
        return MarketWatchPack(
            standing_date=standing,
            explicit=explicit,
            calendar_disclosure=calendar_disclosure,
            bags=bags,
        )
    finally:
        con.close()


def _connect(market_db_path: str | Path | None):
    if not market_db_path:
        return None
    path = Path(market_db_path).expanduser()
    if not path.exists():
        return None
    db_result = retrieval_cache.try_connect_readonly(path)
    if not db_result.available:
        return None
    return db_result.connection


def _has_table(con: Any, name: str) -> bool:
    row = con.execute(
        """
        select 1 from information_schema.tables
        where table_schema = 'main' and table_name = ?
        """,
        [name],
    ).fetchone()
    return row is not None


def _latest_market_date(con: Any) -> str | None:
    if not _has_table(con, "fact_market_daily"):
        return None
    row = con.execute("select max(trade_date) from fact_market_daily").fetchone()
    return str(row[0]) if row and row[0] else None


def _empty(name: str, requested: str | None) -> PackBag:
    return PackBag(
        name=name,
        requested_date=requested,
        served_date=None,
        status="empty",
        rows=(),
    )


def _query_market_daily(con: Any, standing: str | None) -> PackBag:
    if standing is None or not _has_table(con, "fact_market_daily"):
        return _empty(BAG_MARKET, standing)
    columns = (
        "trade_date",
        "market_stage",
        "stage_day",
        "total_amount",
        "amount_vs_yesterday_pct",
        "volume_state",
        "limit_up",
        "limit_down",
        "sh_index_pct_chg",
    )
    available = {
        str(row[1])
        for row in con.execute("pragma table_info('fact_market_daily')").fetchall()
    }
    select_columns = [
        column if column in available else f"null as {column}" for column in columns
    ]
    row = con.execute(
        f"select {', '.join(select_columns)} from fact_market_daily "
        "where trade_date = cast(? as date) limit 1",
        [standing],
    ).fetchone()
    if not row or not row[0]:
        return _empty(BAG_MARKET, standing)
    values = dict(zip(columns, row, strict=True))
    served = str(values["trade_date"])
    return PackBag(
        name=BAG_MARKET,
        requested_date=standing,
        served_date=served,
        status="hit",
        rows=(values,),
    )


def _query_mainline(con: Any, standing: str | None) -> PackBag:
    if standing is None:
        return _empty(BAG_MAINLINE, standing)
    rows: list[dict[str, Any]] = []
    if _has_table(con, "fact_mainline_theme_daily"):
        try:
            fetched = con.execute(
                """
                select theme_name, sector_count
                from fact_mainline_theme_daily
                where trade_date = cast(? as date)
                order by theme_name
                limit 10
                """,
                [standing],
            ).fetchall()
        except Exception:
            fetched = []
        rows.extend(
            {"theme_name": str(name), "sector_count": count}
            for name, count in fetched
            if name
        )
    if _has_table(con, "fact_mainline_sector_daily") and not rows:
        try:
            fetched = con.execute(
                """
                select sector_name
                from fact_mainline_sector_daily
                where trade_date = cast(? as date)
                limit 10
                """,
                [standing],
            ).fetchall()
        except Exception:
            fetched = []
        rows.extend({"sector_name": str(name[0])} for name in fetched if name and name[0])
    if not rows:
        return _empty(BAG_MAINLINE, standing)
    return PackBag(
        name=BAG_MAINLINE,
        requested_date=standing,
        served_date=standing,
        status="hit",
        rows=tuple(rows),
    )


def _query_dual_red(con: Any, standing: str | None) -> PackBag:
    if standing is None or not _has_table(con, "fact_sector_daily"):
        return _empty(BAG_DUAL_RED, standing)
    fetched = con.execute(
        f"""
        select sector_name, pct_chg, diff_ratio, amount
        from fact_sector_daily
        where trade_date = cast(? as date) and {DOUBLE_RED_SQL}
        order by amount desc nulls last, pct_chg desc
        limit 30
        """,
        [standing],
    ).fetchall()
    rows = tuple(
        {
            "sector_name": str(name),
            "pct_chg": pct,
            "diff_ratio": diff,
            "amount": amount,
        }
        for name, pct, diff, amount in fetched
        if name
    )
    if not rows:
        return _empty(BAG_DUAL_RED, standing)
    return PackBag(
        name=BAG_DUAL_RED,
        requested_date=standing,
        served_date=standing,
        status="hit",
        rows=rows,
    )


def _query_limit_heat(con: Any, standing: str | None) -> PackBag:
    if standing is None or not _has_table(con, "fact_theme_limit_heat_daily"):
        return _empty(BAG_LIMIT_HEAT, standing)
    fetched = con.execute(
        """
        select sector_name, limit_up_count, market_share
        from fact_theme_limit_heat_daily
        where trade_date = cast(? as date)
        order by limit_up_count desc nulls last, market_share desc
        limit 20
        """,
        [standing],
    ).fetchall()
    rows = tuple(
        {
            "sector_name": str(name),
            "limit_up_count": count,
            "market_share": share,
        }
        for name, count, share in fetched
        if name
    )
    if not rows:
        return _empty(BAG_LIMIT_HEAT, standing)
    return PackBag(
        name=BAG_LIMIT_HEAT,
        requested_date=standing,
        served_date=standing,
        status="hit",
        rows=rows,
    )


@dataclass(frozen=True)
class StrictSignalHit:
    operator: str
    status: str
    detail: str
    rows: tuple[dict[str, Any], ...] = ()


def run_strict_signal_pack(
    program: Any,
    *,
    query: str,
    market_db_path: str | Path | None,
) -> tuple[StrictSignalHit, ...]:
    """Execute compiled operators by reusing the four-bag queries. No new SQL."""

    from intelligence.services.research_contract import (
        OPERATOR_AGGREGATE_COUNT,
        OPERATOR_CATALOG_PREFLIGHT,
        OPERATOR_CONTRADICTION_AUDIT,
        OPERATOR_CROSS_TABLE,
        OPERATOR_DETAIL_ROWS,
        OPERATOR_STRICT_DOUBLE_RED,
    )

    operators = tuple(getattr(program, "operators", ()) or ())
    if not operators:
        return ()
    standing, explicit = resolve_standing_date(query)
    con = _connect(market_db_path)
    hits: list[StrictSignalHit] = []
    try:
        if con is not None and standing is None and not explicit:
            standing = _latest_market_date(con)
        for operator in operators:
            if operator == OPERATOR_CATALOG_PREFLIGHT:
                hits.append(_catalog_preflight(con, standing))
            elif operator == OPERATOR_STRICT_DOUBLE_RED:
                hits.append(_signal_from_bag(operator, _query_dual_red(con, standing) if con else None))
            elif operator == OPERATOR_AGGREGATE_COUNT:
                bag = _query_dual_red(con, standing) if con else None
                count = len(bag.rows) if bag is not None else 0
                hits.append(
                    StrictSignalHit(
                        operator=operator,
                        status="hit" if bag is not None and not bag.empty else "empty",
                        detail=f"count={count}",
                        rows=bag.rows if bag is not None else (),
                    )
                )
            elif operator == OPERATOR_DETAIL_ROWS:
                hits.append(_signal_from_bag(operator, _query_dual_red(con, standing) if con else None))
            elif operator == OPERATOR_CROSS_TABLE:
                hits.append(_cross_table_hit(con, standing))
            elif operator == OPERATOR_CONTRADICTION_AUDIT:
                hits.append(_contradiction_hit(con, standing))
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
    return tuple(hits)


def render_strict_signal_pack(hits: tuple[StrictSignalHit, ...]) -> str:
    if not hits:
        return ""
    lines = ["## 研究程序信号包"]
    for hit in hits:
        lines.append(f"- {hit.operator}：{hit.status}。{hit.detail}")
    return "\n".join(lines)


def _signal_from_bag(operator: str, bag: PackBag | None) -> StrictSignalHit:
    if bag is None:
        return StrictSignalHit(operator, "empty", "库不可用")
    return StrictSignalHit(
        operator=operator,
        status=bag.status,
        detail=f"{len(bag.rows)} 行",
        rows=bag.rows,
    )


def _catalog_preflight(con: Any, standing: str | None) -> StrictSignalHit:
    from intelligence.services.research_contract import OPERATOR_CATALOG_PREFLIGHT

    if con is None:
        return StrictSignalHit(OPERATOR_CATALOG_PREFLIGHT, "empty", "库不可用")
    if not _has_table(con, "fact_market_daily"):
        return StrictSignalHit(OPERATOR_CATALOG_PREFLIGHT, "empty", "fact_market_daily 不存在")
    if standing is None:
        return StrictSignalHit(OPERATOR_CATALOG_PREFLIGHT, "empty", "无站立日")
    row = con.execute(
        "select 1 from fact_market_daily where trade_date = cast(? as date) limit 1",
        [standing],
    ).fetchone()
    if row is None:
        return StrictSignalHit(
            OPERATOR_CATALOG_PREFLIGHT,
            "empty",
            f"{standing} 无行情行",
        )
    return StrictSignalHit(
        OPERATOR_CATALOG_PREFLIGHT,
        "hit",
        f"{standing} fact_market_daily 有行",
    )


def _cross_table_hit(con: Any, standing: str | None) -> StrictSignalHit:
    from intelligence.services.research_contract import OPERATOR_CROSS_TABLE

    if con is None or standing is None:
        return StrictSignalHit(OPERATOR_CROSS_TABLE, "empty", "库或站立日不可用")
    mainline = _query_mainline(con, standing)
    dual = _query_dual_red(con, standing)
    mainline_names = [
        str(row.get("theme_name") or row.get("sector_name") or "")
        for row in mainline.rows
    ]
    dual_names = [str(row.get("sector_name") or "") for row in dual.rows]
    overlap = tuple(
        {"name": m}
        for m in mainline_names
        if m and any(m in d or d in m for d in dual_names if d)
    )
    return StrictSignalHit(
        OPERATOR_CROSS_TABLE,
        "hit" if overlap else "empty",
        f"交集 {len(overlap)} 项",
        overlap,
    )


def _contradiction_hit(con: Any, standing: str | None) -> StrictSignalHit:
    from intelligence.services.research_contract import OPERATOR_CONTRADICTION_AUDIT

    if con is None or standing is None:
        return StrictSignalHit(OPERATOR_CONTRADICTION_AUDIT, "empty", "库或站立日不可用")
    pack = MarketWatchPack(
        standing_date=standing,
        explicit=True,
        calendar_disclosure=None,
        bags=(
            _query_market_daily(con, standing),
            _query_mainline(con, standing),
            _query_dual_red(con, standing),
            _query_limit_heat(con, standing),
        ),
    )
    gap = pack.mainline_dual_red_gap()
    return StrictSignalHit(
        OPERATOR_CONTRADICTION_AUDIT,
        "hit" if gap else "empty",
        gap or "主线与双红无冲突声明",
    )

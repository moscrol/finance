"""Five-session market pack for market_forecast opening prefetch.

Delegates each day to ``run_market_watch_pack`` so dual-red SQL stays single-source.
``double_red_count`` is a COUNT, not ``len`` after LIMIT.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from intelligence.services import retrieval_cache
from intelligence.services.market_watch_pack import (
    BAG_DUAL_RED,
    BAG_LIMIT_HEAT,
    BAG_MAINLINE,
    BAG_MARKET,
    REQUIRED_BAGS,
    MarketWatchPack,
    run_market_watch_pack,
)
from market_feature_store.signals import DOUBLE_RED_SQL

DEFAULT_WINDOW = 5


@dataclass(frozen=True)
class DailyEnergy:
    trade_date: str
    total_amount: float | None
    volume_ratio: float | None
    amount_ma20: float | None
    double_red_count: int | None


Access = Literal["ok", "locked", "unavailable"]
LOCKED_HINT = "复盘写入中，请稍后。不是该日无数据。"


@dataclass(frozen=True)
class WeeklyWatchPack:
    end_date: str
    window: int
    days: tuple[str, ...]
    packs: tuple[MarketWatchPack, ...]
    energy: tuple[DailyEnergy, ...]
    access: Access = "ok"

    def pack_for(self, trade_date: str) -> MarketWatchPack | None:
        for pack in self.packs:
            if pack.standing_date == trade_date:
                return pack
        return None

    def energy_for(self, trade_date: str) -> DailyEnergy | None:
        for row in self.energy:
            if row.trade_date == trade_date:
                return row
        return None

    def tape_summary(self) -> str:
        amounts = " / ".join(
            _fmt(row.total_amount) for row in self.energy
        )
        ratios = " / ".join(_fmt(row.volume_ratio) for row in self.energy)
        duals = " / ".join(
            "—" if row.double_red_count is None else str(row.double_red_count)
            for row in self.energy
        )
        names: list[str] = []
        last = self.packs[-1] if self.packs else None
        if last is not None:
            mainline = last.bag(BAG_MAINLINE)
            if mainline is not None:
                for row in mainline.rows:
                    name = str(row.get("theme_name") or row.get("sector_name") or "")
                    if name:
                        names.append(name)
        return (
            f"先验周 {self.days[0] if self.days else self.end_date}"
            f"至{self.days[-1] if self.days else self.end_date} "
            f"成交额{amounts} 量比{ratios} 双红{duals} "
            f"末日主线{'、'.join(names) or '无'}"
        )


def run_weekly_watch_pack(
    end_date: str,
    *,
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
) -> WeeklyWatchPack:
    opened = _open(market_db_path)
    if opened is None or not opened.available:
        access: Access = "locked" if opened is not None and opened.locked else "unavailable"
        return WeeklyWatchPack(
            end_date=end_date,
            window=window,
            days=(),
            packs=(),
            energy=(),
            access=access,
        )
    opened.connection.close()
    days = _trade_dates(market_db_path, end_date, window)
    packs: list[MarketWatchPack] = []
    energy: list[DailyEnergy] = []
    for day in days:
        packs.append(
            run_market_watch_pack(
                "盘面",
                market_db_path=market_db_path,
                cutoff=day,
                # 替补观察只开在最新交易日袋（spec 2026-08-25 §8 P1-a）：
                # 历史日的观察池没有行动意义，开了只稀释开口预算。
                substitute_probes=(day == days[-1]),
            )
        )
        energy.append(_energy_row(market_db_path, day))
    return WeeklyWatchPack(
        end_date=end_date,
        window=window,
        days=days,
        packs=tuple(packs),
        energy=tuple(energy),
        access="ok",
    )


def day_bag_details(pack: WeeklyWatchPack) -> tuple[tuple[str, str], ...]:
    """(title, detail) pairs for opening prefetch. Formatter lives in asof_prefetch."""

    if pack.access == "locked":
        return (("先验周盘面", f"status=locked {LOCKED_HINT}"),)
    if pack.access == "unavailable":
        return (("先验周盘面", "status=unavailable 盘面库打不开，不是该日无数据。"),)
    rows = [("先验周量能序列", pack.tape_summary())]
    for day, daily in zip(pack.days, pack.packs, strict=False):
        rows.append((f"{day} 四袋", _render_day(day, daily, pack.energy_for(day))))
    return tuple(rows)


def _trade_dates(
    market_db_path: str | Path | None,
    end_date: str,
    window: int,
) -> tuple[str, ...]:
    con = _connect(market_db_path)
    if con is None:
        return ()
    try:
        if not _has_table(con, "fact_market_daily"):
            return ()
        rows = con.execute(
            """
            select distinct trade_date
            from fact_market_daily
            where trade_date <= cast(? as date)
            order by trade_date desc
            limit ?
            """,
            [end_date, window],
        ).fetchall()
    finally:
        con.close()
    days: list[str] = []
    for (raw,) in rows:
        days.append(raw.isoformat() if hasattr(raw, "isoformat") else str(raw)[:10])
    return tuple(reversed(days))


def _energy_row(market_db_path: str | Path | None, day: str) -> DailyEnergy:
    con = _connect(market_db_path)
    if con is None:
        return DailyEnergy(day, None, None, None, None)
    try:
        total = ratio = ma20 = None
        if _has_table(con, "fact_market_daily"):
            available = {
                str(row[1])
                for row in con.execute("pragma table_info('fact_market_daily')").fetchall()
            }
            wanted = ("total_amount", "volume_ratio", "amount_ma20")
            select = [
                column if column in available else f"null as {column}"
                for column in wanted
            ]
            row = con.execute(
                f"select {', '.join(select)} from fact_market_daily "
                "where trade_date = cast(? as date) limit 1",
                [day],
            ).fetchone()
            if row:
                total, ratio, ma20 = row
        count: int | None = None
        if _has_table(con, "fact_sector_daily"):
            fetched = con.execute(
                f"select count(*) from fact_sector_daily "
                f"where trade_date = cast(? as date) and {DOUBLE_RED_SQL}",
                [day],
            ).fetchone()
            count = int(fetched[0]) if fetched else 0
        return DailyEnergy(
            trade_date=day,
            total_amount=_num(total),
            volume_ratio=_num(ratio),
            amount_ma20=_num(ma20),
            double_red_count=count,
        )
    finally:
        con.close()


def _render_day(day: str, pack: MarketWatchPack, energy: DailyEnergy | None) -> str:
    lines = [f"{day}"]
    for name in REQUIRED_BAGS:
        bag = pack.bag(name)
        if bag is not None and bag.locked:
            served = bag.served_date
            requested = bag.requested_date or day
            lines.append(f"- {name}: locked requested={requested} served={served} {LOCKED_HINT}")
            continue
        if bag is None or bag.empty:
            label = {
                BAG_MARKET: "该日无行情数据",
                BAG_MAINLINE: "主线表该日无行",
                BAG_DUAL_RED: "严格双红 0 个" if energy and energy.double_red_count == 0 else "严格双红该日无行",
                BAG_LIMIT_HEAT: "涨停热度该日无行",
            }.get(name, f"{name} empty")
            served = bag.served_date if bag is not None else None
            requested = bag.requested_date if bag is not None else day
            lines.append(f"- {name}: empty requested={requested} served={served} {label}")
            continue
        extra = ""
        if name == BAG_DUAL_RED and energy is not None and energy.double_red_count is not None:
            extra = f" count={energy.double_red_count}"
        if name == BAG_MAINLINE:
            names = [
                str(row.get("theme_name") or row.get("sector_name") or "")
                for row in bag.rows
            ]
            extra = f" {('、'.join(n for n in names if n)) or ''}"
        if name == BAG_MARKET and energy is not None:
            extra = (
                f" amount={_fmt(energy.total_amount)}"
                f" volume_ratio={_fmt(energy.volume_ratio)}"
                f" amount_ma20={_fmt(energy.amount_ma20)}"
            )
        lines.append(
            f"- {name}: hit requested={bag.requested_date} served={bag.served_date}{extra}"
        )
    if pack.probes:
        from intelligence.services.market_watch_pack import render_probe_lines

        lines.append("替补观察（出清/分歧观察，非机会）：")
        lines.extend(render_probe_lines(pack.probes))
    return "\n".join(lines)


def _open(market_db_path: str | Path | None):
    if not market_db_path:
        return None
    path = Path(market_db_path).expanduser()
    if not path.exists():
        return None
    return retrieval_cache.try_connect_readonly(path)


def _connect(market_db_path: str | Path | None):
    opened = _open(market_db_path)
    if opened is None or not opened.available:
        return None
    return opened.connection


def _has_table(con: Any, name: str) -> bool:
    row = con.execute(
        """
        select 1 from information_schema.tables
        where table_schema = 'main' and table_name = ?
        """,
        [name],
    ).fetchone()
    return row is not None


def _num(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:g}"

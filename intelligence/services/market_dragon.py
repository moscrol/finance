"""D13 龙虎榜席位块：本地 DuckDB 上榜日 + 买卖前五席位类型分布。

Spec 写 [D10]，但注册表 D10 已是市场情绪类比；本块用 D13，D12 留给资金面三件套。

- 意图：龙虎榜 / 席位 / 游资 / 机构专用；解析不到个股不输出块。
- 数据：`fact_dragon_tiger_daily` + `fact_dragon_seat_daily`（复盘会公开源）。
- 席位类型沿用库口径：营业部 / 游资 / 机构。库内无独立「量化」标签，不补造。
- 只列事实，不构成跟单或买卖建议。席位行以本地库为准，可能少于东财页当日全部席位。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from intelligence.paths import default_market_db_path
from intelligence.services import retrieval_cache

DEFAULT_MARKET_DB_PATH = default_market_db_path()
DEFAULT_DAYS = 5
TOP_SEATS = 5

_DRAGON_TERMS = (
    "龙虎榜",
    "席位",
    "游资",
    "机构专用",
)


@dataclass(frozen=True)
class DragonSeat:
    seat_no: int
    exalter: str
    seat_type: str
    hm_name: str | None
    buy: float | None
    sell: float | None
    net_buy: float | None

    def display_name(self) -> str:
        alias = (self.hm_name or "").strip()
        if alias and alias != self.exalter:
            return f"{alias} / {self.exalter}"
        return self.exalter or alias or "缺席位名"


@dataclass(frozen=True)
class DragonDay:
    trade_date: str
    reason: str
    net_amount: float | None
    buy_seats: tuple[DragonSeat, ...]
    sell_seats: tuple[DragonSeat, ...]


def parse_dragon_intent(query: str) -> bool:
    """确定性意图：命中龙虎榜/席位/游资/机构专用才触发。"""
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    return any(term in text for term in _DRAGON_TERMS)


def _date_text(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "")[:10]


def _fmt(value: float | None) -> str:
    if value is None:
        return "缺"
    return f"{value}"


def _type_dist(seats: tuple[DragonSeat, ...]) -> str:
    counts = Counter(seat.seat_type or "未标注" for seat in seats)
    if not counts:
        return "缺"
    order = ("机构", "游资", "营业部")
    parts = [f"{label} {counts[label]}" for label in order if counts.get(label)]
    extras = [f"{label} {n}" for label, n in counts.items() if label not in order]
    return " / ".join(parts + extras)


def resolve_dragon_stock(con: Any, query: str) -> tuple[str, str] | None:
    code_match = re.search(r"\b(\d{6})(?:\.(SH|SZ|BJ))?\b", str(query or ""), re.I)
    if code_match:
        raw = code_match.group(1)
        suffix = code_match.group(2)
        if suffix:
            rows = con.execute(
                "select stock_ts_code, stock_name from fact_stock_daily where stock_ts_code=? limit 1",
                [f"{raw}.{suffix.upper()}"],
            ).fetchall()
        else:
            rows = con.execute(
                "select stock_ts_code, stock_name from fact_stock_daily where stock_ts_code like ? limit 1",
                [f"{raw}.%"],
            ).fetchall()
        if rows:
            return str(rows[0][0]), str(rows[0][1] or rows[0][0])
    rows = con.execute(
        """
        select stock_ts_code, stock_name
        from fact_stock_daily
        where stock_name is not null and stock_name <> ''
        group by stock_ts_code, stock_name
        """
    ).fetchall()
    q = str(query or "")
    matches = [(str(code), str(name)) for code, name in rows if str(name) and str(name) in q]
    if matches:
        matches.sort(key=lambda item: len(item[1]), reverse=True)
        return matches[0]
    return None


def _seats_for(
    con: Any, ts_code: str, trade_date: str, side: str
) -> tuple[DragonSeat, ...]:
    rows = con.execute(
        """
        select seat_no, exalter, seat_type, hm_name, buy, sell, net_buy
        from fact_dragon_seat_daily
        where stock_ts_code = ? and trade_date = ? and side = ?
        order by seat_no asc nulls last
        limit ?
        """,
        [ts_code, trade_date, side, TOP_SEATS],
    ).fetchall()
    seats: list[DragonSeat] = []
    for row in rows:
        seats.append(
            DragonSeat(
                seat_no=int(row[0] or 0),
                exalter=str(row[1] or ""),
                seat_type=str(row[2] or ""),
                hm_name=str(row[3]) if row[3] else None,
                buy=None if row[4] is None else float(row[4]),
                sell=None if row[5] is None else float(row[5]),
                net_buy=None if row[6] is None else float(row[6]),
            )
        )
    return tuple(seats)


def load_dragon_days(
    con: Any, ts_code: str, days: int = DEFAULT_DAYS
) -> tuple[DragonDay, ...]:
    rows = con.execute(
        """
        select trade_date, reason, net_amount
        from fact_dragon_tiger_daily
        where stock_ts_code = ?
        order by trade_date desc
        limit ?
        """,
        [ts_code, int(days)],
    ).fetchall()
    out: list[DragonDay] = []
    for row in rows:
        trade_date = _date_text(row[0])
        out.append(
            DragonDay(
                trade_date=trade_date,
                reason=str(row[1] or "缺理由"),
                net_amount=None if row[2] is None else float(row[2]),
                buy_seats=_seats_for(con, ts_code, trade_date, "buy"),
                sell_seats=_seats_for(con, ts_code, trade_date, "sell"),
            )
        )
    return tuple(out)


def _render_seats(title: str, seats: tuple[DragonSeat, ...]) -> list[str]:
    lines = [f"- {title}类型分布：{_type_dist(seats)}"]
    if not seats:
        lines.append(f"- {title}：缺席位明细")
        return lines
    lines.append(f"- | {title} | 类型 | 席位 | 买入(亿) | 卖出(亿) | 净买(亿) |")
    lines.append("- |---|---|---|---|---|---|")
    for seat in seats:
        lines.append(
            f"- | {seat.seat_no} | {seat.seat_type or '缺'} | {seat.display_name()} | "
            f"{_fmt(seat.buy)} | {_fmt(seat.sell)} | {_fmt(seat.net_buy)} |"
        )
    return lines


def build_dragon_block(
    target_name: str,
    ts_code: str,
    days: tuple[DragonDay, ...],
) -> str:
    lines = [f"## 龙虎榜席位数据块 [D13]（{target_name} {ts_code}）"]
    lines.append(
        "- 口径：本地 DuckDB `fact_dragon_tiger_daily` / `fact_dragon_seat_daily`"
        "（复盘会公开 /data/dragon）；金额单位=亿；席位类型沿用源口径（营业部/游资/机构），"
        "库内无独立「量化」标签，不得补造。席位行以**本地库为准**，可能少于东财页当日全部席位。"
        "只列上榜日事实，**不构成跟单**或买卖建议。"
    )
    if not days:
        lines.append(f"- ⚠近窗口未上榜：{target_name}（{ts_code}）在本地龙虎榜表无上榜日，按缺口处理，不得编造席位。")
        return "\n".join(lines)
    lines.append(f"- 近 {len(days)} 个上榜日（新→旧）：")
    for day in days:
        lines.append(
            f"- {day.trade_date} ｜ 理由：{day.reason} ｜ 龙虎榜净额 {_fmt(day.net_amount)} 亿"
        )
        lines.extend(_render_seats("买方前五", day.buy_seats))
        lines.extend(_render_seats("卖方前五", day.sell_seats))
    return "\n".join(lines)


def dragon_block_for_llm(
    query: str,
    market_db_path: str | Path | None,
    days: int = DEFAULT_DAYS,
) -> str:
    """给定问句取数并渲染 D13；解析不到个股或库不可用时返回空串。"""
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return ""
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return ""
    con = db_result.connection
    try:
        stock = resolve_dragon_stock(con, query)
        if stock is None:
            return ""
        ts_code, name = stock
        listed = load_dragon_days(con, ts_code, days=days)
        return build_dragon_block(name, ts_code, listed)
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass

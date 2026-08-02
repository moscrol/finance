"""D9 L2 大单资金流数据块：把 l2-moneyflow 落库的特征表接进答题证据链。

背景（为什么要这个块）：
    l2-moneyflow skill 盘后把 ClickHouse 逐笔成交聚合成 DuckDB 特征表
    （feature_l2_capital_flow_daily / feature_l2_quant_orders_daily），但答题链
    没有模块取用——「资金流/大单/主买」类问题只能靠印象。本块做确定性直查。

设计（沿用 D6/D8 的参数化白名单纪律）：
    - **确定性意图路由**：命中「资金流/大单/主买/总买/净流入/量化单」词面才触发。
    - **个股视角**：从表内 distinct stock_name 子串匹配解析目标股（锚定实体兜底），
      取近 N 日主买净额/总买净额/净流入强度/榜单名次 + 量化单特征。
    - **榜单视角**：最新交易日 top K（按 score 名次），给「钱在谁身上」的横截面。
    - **覆盖口径必须显式声明**：榜单只扫涨停股+成交额 top100，**缺该股行 ≠ 无资金
      流入**，只能说「不在扫描名单内」；缺库/缺表返回空串。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from intelligence.services import retrieval_cache
from intelligence.paths import default_market_db_path

REPO_ROOT = Path(__file__).resolve().parents[2]


DEFAULT_MARKET_DB_PATH = default_market_db_path()

DEFAULT_WINDOW = 10
TOP_K = 10

_MONEYFLOW_TERMS = (
    "资金流",
    "大单",
    "主买",
    "总买",
    "净流入",
    "净流出",
    "量化单",
    "量化买单",
    "接力资金",
    "moneyflow",
)


@dataclass(frozen=True)
class MoneyflowRow:
    stock_code: str
    stock_name: str
    scan_type: str
    main_buy_net_wan: float | None
    total_buy_net_wan: float | None
    score: float | None
    rank: int | None
    pct_change: float | None


@dataclass(frozen=True)
class QuantOrderRow:
    stock_code: str
    stock_name: str
    quant_amount_wan: float | None
    quant_pct_of_big_buy: float | None
    cluster_count: int | None
    biggest_cluster: str | None
    rank: int | None


@dataclass(frozen=True)
class MoneyflowSnapshot:
    status: str
    target_date: str | None
    trade_date: str | None
    coverage: dict[str, int]
    leaders: tuple[MoneyflowRow, ...]
    quant_orders: tuple[QuantOrderRow, ...]
    warnings: tuple[str, ...]
    source: str = "feature_l2_capital_flow_daily + feature_l2_quant_orders_daily"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_moneyflow_intent(query: str) -> bool:
    """确定性意图路由：命中「资金流/大单/主买/量化单」词面才触发。"""
    text = re.sub(r"\s+", "", str(query or "")).lower()
    if not text:
        return False
    return any(term in text for term in _MONEYFLOW_TERMS)


def resolve_query_stocks(con: Any, query: str, anchored_entity: str | None = None, limit: int = 3) -> list[str]:
    """从表内 distinct stock_name 子串匹配解析目标股（长名优先，锚定实体兜底）。"""
    text = re.sub(r"\s+", "", str(query or ""))
    try:
        names = [str(r[0]) for r in con.execute(
            "select distinct stock_name from feature_l2_capital_flow_daily where stock_name is not null"
        ).fetchall()]
    except Exception:
        return []
    names_sorted = sorted({n for n in names if n}, key=len, reverse=True)
    hit: list[str] = []
    remaining = text
    for name in names_sorted:
        if name in remaining and name not in hit:
            hit.append(name)
            remaining = remaining.replace(name, "□")
        if len(hit) >= limit:
            break
    if anchored_entity and anchored_entity not in hit:
        if any(anchored_entity == n for n in names_sorted):
            hit.append(anchored_entity)
    return hit[:limit]


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else str(value)


def load_moneyflow_snapshot(
    market_db_path: str | Path | None,
    *,
    as_of_date: str | None = None,
    top_k: int = TOP_K,
) -> MoneyflowSnapshot:
    """Return a bounded, UI-safe L2 snapshot without rendering Markdown or HTML."""
    db_path = (
        Path(market_db_path).expanduser()
        if market_db_path
        else DEFAULT_MARKET_DB_PATH
    )
    missing = MoneyflowSnapshot(
        status="missing",
        target_date=as_of_date,
        trade_date=None,
        coverage={},
        leaders=(),
        quant_orders=(),
        warnings=("L2 资金流特征库不可用；本模块未据此下资金面结论。",),
    )
    if not db_path.exists():
        return missing
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return missing
    con = db_result.connection
    try:
        if as_of_date:
            latest = con.execute(
                """
                select max(trade_date)
                from feature_l2_capital_flow_daily
                where trade_date <= ?
                """,
                [as_of_date],
            ).fetchone()
        else:
            latest = con.execute(
                "select max(trade_date) from feature_l2_capital_flow_daily"
            ).fetchone()
        trade_date = _date_text(latest[0] if latest else None)
        if trade_date is None:
            return missing

        coverage = {
            str(scan_type): int(count)
            for scan_type, count in con.execute(
                """
                select scan_type, count(distinct stock_code)
                from feature_l2_capital_flow_daily
                where trade_date = ?
                group by scan_type
                order by scan_type
                """,
                [trade_date],
            ).fetchall()
        }
        raw_leaders = con.execute(
            """
            select stock_code, stock_name, scan_type, main_buy_net_wan,
                   total_buy_net_wan, score, rank, pct_change
            from feature_l2_capital_flow_daily
            where trade_date = ?
            order by score desc nulls last, rank asc nulls last
            """,
            [trade_date],
        ).fetchall()
        leaders: list[MoneyflowRow] = []
        seen_stocks: set[str] = set()
        for row in raw_leaders:
            stock_code = str(row[0] or "")
            if not stock_code or stock_code in seen_stocks:
                continue
            seen_stocks.add(stock_code)
            leaders.append(
                MoneyflowRow(
                    stock_code=stock_code,
                    stock_name=str(row[1] or stock_code),
                    scan_type=str(row[2] or ""),
                    main_buy_net_wan=row[3],
                    total_buy_net_wan=row[4],
                    score=row[5],
                    rank=row[6],
                    pct_change=row[7],
                )
            )
            if len(leaders) >= max(1, int(top_k)):
                break

        quant_rows = con.execute(
            """
            select stock_code, stock_name, quant_amount_wan,
                   quant_pct_of_big_buy, cluster_count, biggest_cluster, rank
            from feature_l2_quant_orders_daily
            where trade_date = ?
            order by rank asc nulls last, quant_pct_of_big_buy desc nulls last
            limit ?
            """,
            [trade_date, max(1, int(top_k))],
        ).fetchall()
        quant_orders = tuple(
            QuantOrderRow(
                stock_code=str(row[0] or ""),
                stock_name=str(row[1] or row[0] or ""),
                quant_amount_wan=row[2],
                quant_pct_of_big_buy=row[3],
                cluster_count=row[4],
                biggest_cluster=str(row[5]) if row[5] is not None else None,
                rank=row[6],
            )
            for row in quant_rows
        )
        warnings = [
            "仅覆盖昨日涨停股和成交额前 100；缺行不等于无资金流入。",
            "大单方向由委托编号口径推断，不等同于问财或全市场资金流口径。",
        ]
        status = "ok"
        if as_of_date and trade_date < as_of_date:
            status = "stale"
            warnings.insert(0, f"L2 最新扫描日为 {trade_date}，早于报告日 {as_of_date}。")
        return MoneyflowSnapshot(
            status=status,
            target_date=as_of_date,
            trade_date=trade_date,
            coverage=coverage,
            leaders=tuple(leaders),
            quant_orders=quant_orders,
            warnings=tuple(warnings),
        )
    except Exception:
        return missing
    finally:
        con.close()


def moneyflow_block_for_llm(
    query: str,
    anchored_entity: str | None,
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
    top_k: int = TOP_K,
    as_of_date: str | None = None,
) -> str:
    """把 L2 大单资金流特征渲染成带 [D9] 引用编号的确定性数据块（空串=未取到）。"""
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return ""
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return ""
    con = db_result.connection
    try:
        try:
            if as_of_date:
                latest = con.execute(
                    """
                    select max(trade_date)
                    from feature_l2_capital_flow_daily
                    where trade_date <= ?
                    """,
                    [as_of_date],
                ).fetchone()
            else:
                latest = con.execute(
                    "select max(trade_date) from feature_l2_capital_flow_daily"
                ).fetchone()
        except Exception:
            return ""
        if not latest or latest[0] is None:
            return ""
        latest_date = str(latest[0])
        lines = ["## L2 大单资金流数据块 [D9]"]
        lines.append(
            f"- 口径：l2-moneyflow 盘后特征表（大单=同一委托单当日累计成交额过阈值，主买净额=主动买-主动卖；"
            f"最新扫描日 {latest_date}），本地 DuckDB feature_l2_capital_flow_daily / feature_l2_quant_orders_daily 直查，非 LLM 生成。"
        )

        stocks = resolve_query_stocks(con, query, anchored_entity)
        missing: list[str] = []
        for stock in stocks:
            rows = con.execute(
                f"""
                select trade_date, scan_type, main_buy_net_wan, total_buy_net_wan, score, rank, pct_change
                from feature_l2_capital_flow_daily
                where stock_name = ?
                order by trade_date desc limit {int(window)}
                """,
                [stock],
            ).fetchall()
            if not rows:
                missing.append(stock)
                continue
            lines.append("")
            lines.append(f"### {stock} 近 {len(rows)} 条大单资金流记录")
            lines.append("| 日期 | 扫描口径 | 主买净额(万) | 总买净额(万) | 净流入强度% | 当日名次 | 涨幅% |")
            lines.append("|" + "---|" * 7)
            for r in rows:
                lines.append(
                    f"| {r[0]} | {r[1]} | {_fmt(r[2])} | {_fmt(r[3])} | {_fmt(r[4], 2)} | {r[5] if r[5] is not None else '—'} | {_fmt(r[6])} |"
                )
            quant = con.execute(
                f"""
                select trade_date, quant_amount_wan, quant_pct_of_big_buy, cluster_count, biggest_cluster
                from feature_l2_quant_orders_daily
                where stock_name = ?
                order by trade_date desc limit {int(window)}
                """,
                [stock],
            ).fetchall()
            if quant:
                lines.append("| 日期 | 量化单总额(万) | 占大单买入% | 簇数 | 最大簇 |")
                lines.append("|" + "---|" * 5)
                for q in quant:
                    lines.append(f"| {q[0]} | {_fmt(q[1])} | {_fmt(q[2])} | {q[3]} | {q[4] or '—'} |")

        top = con.execute(
            f"""
            select rank, scan_type, stock_name, main_buy_net_wan, total_buy_net_wan, score, pct_change
            from feature_l2_capital_flow_daily
            where trade_date = ? order by score desc nulls last limit {int(top_k)}
            """,
            [latest_date],
        ).fetchall()
        if top:
            lines.append("")
            lines.append(f"### 最新扫描日（{latest_date}）大单净流入榜 top{len(top)}")
            lines.append("| 口径内名次 | 扫描口径 | 股票 | 主买净额(万) | 总买净额(万) | 净流入强度% | 涨幅% |")
            lines.append("|" + "---|" * 7)
            for r in top:
                lines.append(
                    f"| {r[0]} | {r[1]} | {r[2]} | {_fmt(r[3])} | {_fmt(r[4])} | {_fmt(r[5], 2)} | {_fmt(r[6])} |"
                )
        if missing:
            lines.append("")
            lines.append(
                "- 数据缺口：" + "、".join(missing) + " 不在扫描名单内（榜单只扫涨停股+成交额 top100）。"
                "**缺行 ≠ 无资金流入**，只能表述为「未被大单扫描覆盖」，禁止据此下资金面结论。"
            )
        lines.append("")
        lines.append(
            "- 使用要求：本块是自有大单口径（委托编号判主动方向）的盘后事实，不代表全市场资金流向；"
            "与问财口径资金流可能不一致，引用时须注明口径。量化单占比高只说明存在程序化买入特征，"
            "不得直接推断「量化接力→可持续」这类因果结论。"
        )
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass

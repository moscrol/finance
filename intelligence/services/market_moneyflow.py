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
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

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


def moneyflow_block_for_llm(
    query: str,
    anchored_entity: str | None,
    market_db_path: str | Path | None,
    window: int = DEFAULT_WINDOW,
    top_k: int = TOP_K,
) -> str:
    """把 L2 大单资金流特征渲染成带 [D9] 引用编号的确定性数据块（空串=未取到）。"""
    db_path = Path(market_db_path).expanduser() if market_db_path else REPO_ROOT / "db" / "market_feature_store.duckdb"
    if not db_path.exists():
        return ""
    try:
        import duckdb  # type: ignore
    except Exception:
        return ""
    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except Exception:
        return ""
    try:
        try:
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
            select rank, stock_name, main_buy_net_wan, total_buy_net_wan, score, pct_change
            from feature_l2_capital_flow_daily
            where trade_date = ? order by rank asc limit {int(top_k)}
            """,
            [latest_date],
        ).fetchall()
        if top:
            lines.append("")
            lines.append(f"### 最新扫描日（{latest_date}）大单净流入榜 top{len(top)}")
            lines.append("| 名次 | 股票 | 主买净额(万) | 总买净额(万) | 净流入强度% | 涨幅% |")
            lines.append("|" + "---|" * 6)
            for r in top:
                lines.append(
                    f"| {r[0]} | {r[1]} | {_fmt(r[2])} | {_fmt(r[3])} | {_fmt(r[4], 2)} | {_fmt(r[5])} |"
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

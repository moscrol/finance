"""ask 的数据块构建层：D0-D9/W7/M/V 数据块与盘面块的取数/格式化（从 ask.py 拆出，行为不变）。"""

from __future__ import annotations


import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from intelligence.services import retrieval_cache
from intelligence.services import (
    answer_model,
    ask_planner,
    market_financials,
    research_brief,
)
from intelligence.services import valuation_estimate
from intelligence.services.trading_calendar import (
    next_trading_day,
)
from intelligence.services.ask_types import (
    DEFAULT_MARKET_DB_PATH,
    SUBHEAD,
    AskResult,
    Citation,
    _normalize,
)
from intelligence.services.evidence_window import select_text_window


def _evidence_text_for_llm(
    evidence_chain: list[str],
    gap_lines: list[str],
    *,
    query: str = "",
    max_chars: int = 9000,
) -> str:
    """Flatten a ranked, globally bounded evidence window for the LLM prompt.

    Provider traces keep the full chain; only the model-facing window is
    bounded so a long weak source cannot push hard evidence out of context.
    """
    out: list[str] = ["## 证据链"]
    selected = select_text_window(query, evidence_chain, max_chars=max_chars)
    for item in selected:
        out.append(f"- {item}")
    out.append("## 分歧反证")
    remaining = max(0, max_chars - len("\n".join(out)))
    for gap in gap_lines:
        if remaining <= 0:
            break
        text = str(gap or "").strip()
        if not text:
            continue
        out.append(f"- {text[: min(360, remaining)]}")
        remaining -= len(text) + 3
    return "\n".join(out)


def _evidence_chain_with_llm_wiki(
    evidence_chain: list[str],
    wiki_llm_line_pairs: list[tuple[str, str]],
) -> list[str]:
    if not wiki_llm_line_pairs:
        return evidence_chain
    replacements = dict(wiki_llm_line_pairs)
    return [replacements.get(item, item) for item in evidence_chain]


def _market_review_evidence_chain(evidence_chain: list[str]) -> list[str]:
    """Keep broad market-review synthesis focused on market-level evidence."""
    allowed_sections = {
        "盘面",
        "最新市场总览（本地 DuckDB）",
    }
    filtered: list[str] = []
    include_section = False
    for item in evidence_chain:
        if item.startswith(SUBHEAD):
            section = item[len(SUBHEAD):]
            include_section = section in allowed_sections
            if include_section:
                filtered.append(item)
            continue
        if include_section:
            filtered.append(item)
    return filtered


def _customer_evidence_hardness_block_for_llm(evidence_chain: list[str], gap_lines: list[str]) -> str:
    """Classify customer/order evidence into hardness buckets for compose answers."""
    hard: list[str] = []
    candidate: list[str] = []
    weak: list[str] = []
    rebuttal: list[str] = []
    for raw in [*evidence_chain, *gap_lines]:
        if raw.startswith(SUBHEAD):
            continue
        line = re.sub(r"\s+", " ", str(raw or "")).strip()
        if not line or line.startswith("（"):
            continue
        bucket = _classify_customer_evidence_line(line)
        if bucket == "hard":
            _append_unique_limited(hard, _shorten_evidence_line(line))
        elif bucket == "candidate":
            _append_unique_limited(candidate, _shorten_evidence_line(line))
        elif bucket == "weak":
            _append_unique_limited(weak, _shorten_evidence_line(line))
        elif bucket == "rebuttal":
            _append_unique_limited(rebuttal, _shorten_evidence_line(line))

    lines = ["## 客户证据硬度数据块 [D2]"]
    lines.append("- 硬证据：" + ("；".join(hard[:4]) if hard else "未从本轮证据链识别到公告/互动易/年报等官方口径的订单、量产、批量供货、收入或客户验证硬证据。"))
    lines.append("- 候选证据：" + ("；".join(candidate[:4]) if candidate else "未识别到带客户/导入/送样/审厂/收入目标的研报或调研候选证据。"))
    lines.append("- 弱证据/研报推断：" + ("；".join(weak[:4]) if weak else "未识别到仅有空间测算、预期、市场传闻或无客户落点的弱证据。"))
    lines.append("- 反证/缺口：" + ("；".join(rebuttal[:4]) if rebuttal else "本轮证据未给出明确反证；仍需检查是否存在公司口径保守、未并表、低占比或尚未进入财务的约束。"))
    lines.append("- 使用要求：回答时必须先说客户证据属于硬证据、候选证据还是弱证据；硬证据可支撑当期逻辑，候选证据只能支撑跟踪假设，弱证据不能直接当作基本面兑现。")
    return "\n".join(lines)


def _classify_customer_evidence_line(line: str) -> str | None:
    text = line.lower()
    customer_terms = r"客户|终端|订单|合同|中标|量产|批量|供货|出货|导入|认证|审厂|验证|收入|定点|供应商|配套|a客户|b客户"
    rebuttal_terms = r"否认|未确认|尚未|暂无|缺失|低占比|保守|未进入财务|不并表|亏损|证据不足|待证|待验证|不确定|缺口"
    hard_source_terms = r"公告|互动|年报|季报|半年报|招股书|定期报告|问询函|交易所|公司|官网|监管|合同|中标"
    hard_action_terms = r"量产|批量|订单|合同|中标|收入|出货|供货|定点|认证|客户验证|通过验证"
    candidate_source_terms = r"研报|调研|纪要|卖方|券商|ima|晨汇|产业链"
    weak_terms = r"预计|有望|推断|猜测|传闻|市场|空间|目标|测算|可能|预期|或将|弹性"
    has_customer = re.search(customer_terms, text) is not None
    if re.search(rebuttal_terms, text):
        return "rebuttal"
    if not has_customer and not re.search(hard_action_terms, text):
        return None
    if re.search(hard_source_terms, text) and re.search(hard_action_terms, text):
        return "hard"
    if re.search(candidate_source_terms, text) and (has_customer or re.search(hard_action_terms, text)):
        return "candidate"
    if re.search(weak_terms, text):
        return "weak"
    return "candidate" if has_customer else None


def _append_unique_limited(items: list[str], value: str, limit: int = 8) -> None:
    if value and value not in items and len(items) < limit:
        items.append(value)


def _shorten_evidence_line(line: str, max_chars: int = 120) -> str:
    line = line.replace(SUBHEAD, "")
    return line if len(line) <= max_chars else line[: max_chars - 1] + "…"


def _mainline_context_block_for_llm(
    query: str,
    theme: str | None,
    market_db_path: str | Path | None,
    lookback_days: int = 20,
    *,
    as_of: str | None = None,
) -> str:
    """Build the D4 mainline-theme structure block from local DuckDB.

    Grain: trade_date × mainline theme × core sector. This is L4 market signal,
    not entity baseline or hard company evidence.
    """
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return ""
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return ""
    con = db_result.connection
    try:
        exists = con.execute(
            "select count(*) from information_schema.tables where table_name='fact_mainline_sector_daily'"
        ).fetchone()[0]
        if not exists:
            return ""
        latest = con.execute(
            "select max(trade_date) from fact_mainline_sector_daily "
            "where (? is null or trade_date <= cast(? as date))",
            [as_of, as_of],
        ).fetchone()[0]
        if not latest:
            return ""
        target_theme = _resolve_mainline_theme(con, query, theme, latest)
        params: list[Any] = [latest]
        theme_filter = ""
        if target_theme:
            theme_filter = "and m.theme_name = ?"
            params.append(target_theme)
        rows = con.execute(
            f"""
            select
              m.trade_date, m.theme_name, m.sector_name, m.sort_no,
              m.cycle_status, m.cycle_level, m.today_pct, m.limit_up_count,
              m.startup_date_small, m.high_status_label, m.near_breakout_label,
              coalesce(s.pct_chg, m.today_pct) as sector_pct,
              s.diff_ratio, coalesce(s.amount, m.amount / 10000.0) as sector_amount,
              s.sw_l1
            from fact_mainline_sector_daily m
            left join fact_sector_daily s
              on m.trade_date = s.trade_date and m.sector_ts_code = s.sector_ts_code
            where m.trade_date = ? {theme_filter}
            order by m.theme_name, m.sort_no nulls last, m.sector_name
            limit 30
            """,
            params,
        ).fetchall()
        if not rows:
            return ""
        cutoff = latest - timedelta(days=int(lookback_days)) if hasattr(latest, "__sub__") else latest
        history_params: list[Any] = [latest, cutoff]
        history_filter = ""
        if target_theme:
            history_filter = "and theme_name = ?"
            history_params.append(target_theme)
        history = con.execute(
            f"""
            select theme_name, count(distinct trade_date) as day_count,
                   min(trade_date) as first_date, max(trade_date) as last_date,
                   count(*) as sector_rows
            from fact_mainline_sector_daily
            where trade_date <= ?
              and trade_date >= ?
              {history_filter}
            group by theme_name
            order by day_count desc, sector_rows desc, theme_name
            limit 8
            """,
            history_params,
        ).fetchall()
        lines = ["## 主线题材结构数据块 [D4]"]
        matched = target_theme or "最新全市场主线"
        lines.append(f"- 最新主线日期：{latest}；匹配口径：{matched}；该块是 L4_market_signal，只能说明市场主线归因，不等同公司基本面兑现。")
        if history:
            hist_text = "；".join(
                f"{name}近{lookback_days}日出现{days}天（{first}~{last}，板块行{sector_rows}）"
                for name, days, first, last, sector_rows in history[:5]
            )
            lines.append(f"- 主线持续性：{hist_text}")
        grouped: dict[str, list[tuple[Any, ...]]] = {}
        for row in rows:
            grouped.setdefault(str(row[1]), []).append(row)
        for theme_name, items in grouped.items():
            sector_bits = []
            for row in items[:8]:
                (
                    _td,
                    _theme_name,
                    sector_name,
                    _sort_no,
                    cycle_status,
                    cycle_level,
                    _today_pct,
                    limit_up_count,
                    startup_date_small,
                    high_status_label,
                    near_breakout_label,
                    sector_pct,
                    diff_ratio,
                    sector_amount,
                    sw_l1,
                ) = row
                volume_state = _classify_mainline_volume_state(sector_pct, diff_ratio, sector_amount)
                breakout = high_status_label or near_breakout_label or ""
                breakout_text = f"，{breakout}" if breakout else ""
                startup_text = f"，启动日{startup_date_small}" if startup_date_small else ""
                sector_bits.append(
                    f"{sector_name}({sw_l1 or '-'}，{cycle_status or '未标注'}/{cycle_level or '-'}，"
                    f"涨{_fmt_optional(sector_pct)}%，边际量{_fmt_optional(diff_ratio)}%，"
                    f"成交{_fmt_optional(sector_amount)}亿，涨停{limit_up_count or 0}，{volume_state}{breakout_text}{startup_text})"
                )
            lines.append(f"- {theme_name}核心板块：" + "；".join(sector_bits))
        lines.append("- 使用要求：回答时要区分连续主线与新启动主线；cycle_status=分歧/消亡不能写成无条件主升；涨幅为正但 diff_ratio 为负时，优先解释为缩量强修复/存量抱团，而不是低位放量启动。")
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass


def _market_review_mainline_context_block_for_llm(
    query: str,
    theme: str | None,
    market_db_path: str | Path | None,
    *,
    as_of: str | None = None,
) -> str:
    market_date = _market_data_asof(market_db_path, as_of=as_of)
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not market_date or not db_path.exists():
        return ""
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return ""
    con = db_result.connection
    try:
        table_names = {
            str(row[0])
            for row in con.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'main'
                """
            ).fetchall()
        }
        theme_date = None
        themes: list[tuple[str, int]] = []
        if "fact_mainline_theme_daily" in table_names:
            row = con.execute(
                "select max(trade_date) from fact_mainline_theme_daily "
                "where trade_date <= cast(? as date)",
                [market_date],
            ).fetchone()
            theme_date = str(row[0]) if row and row[0] else None
            if theme_date == market_date:
                themes = [
                    (str(name), int(sector_count or 0))
                    for name, sector_count in con.execute(
                        """
                        select theme_name, sector_count
                        from fact_mainline_theme_daily
                        where trade_date = ?
                        order by min_sort nulls last, theme_name
                        limit 10
                        """,
                        [theme_date],
                    ).fetchall()
                    if name
                ]
        sector_date = None
        if "fact_mainline_sector_daily" in table_names:
            row = con.execute(
                "select max(trade_date) from fact_mainline_sector_daily "
                "where trade_date <= cast(? as date)",
                [market_date],
            ).fetchone()
            sector_date = str(row[0]) if row and row[0] else None
    except Exception:
        return ""
    finally:
        con.close()
    if sector_date == market_date:
        return _mainline_context_block_for_llm(
            query,
            theme,
            market_db_path,
            as_of=market_date,
        )
    lines = ["## 市场复盘主线数据边界"]
    if theme_date == market_date and themes:
        theme_text = "、".join(name for name, _ in themes)
        lines.append(
            f"- 当日市场总览和题材级主线汇总均截至 {market_date}；"
            f"当前主线题材为 {theme_text}。"
        )
    elif theme_date:
        lines.append(
            f"- 当日市场总览截至 {market_date}；主线题材汇总仅截至 {theme_date}。"
        )
        lines.append(
            "- 当前交易日的题材级主线未知，禁止把旧题材名称写成当日事实。"
        )
    else:
        lines.append(
            f"- 当日市场总览截至 {market_date}；没有可用的同日主线题材汇总。"
        )
        lines.append("- 当前交易日的题材级主线未知。")
    if sector_date:
        lines.append(
            f"- 核心板块明细仅截至 {sector_date}；当前核心板块、周期状态和标的未知。"
        )
    else:
        lines.append("- 没有可用的核心板块明细；当前核心板块、周期状态和标的未知。")
    lines.append(
        "- 禁止把旧板块名称、涨幅、生命周期或标的写成当日事实。"
    )
    return "\n".join(lines)


def _mainline_theme_names(
    market_db_path: str | Path | None,
    *,
    as_of: str | None = None,
    limit: int = 6,
) -> tuple[str, list[str]]:
    """当日主线方向名。返回 (主线日期, 方向名列表)；同日没有汇总就返回空列表。

    与 _market_review_mainline_context_block_for_llm 用同一张
    fact_mainline_theme_daily、同一个「必须同日」判据，避免两个块讲不同的主线。
    """
    if not market_db_path:
        # 不回退 DEFAULT_MARKET_DB_PATH：调用方没给库就是没要盘面数据。回退会让
        # 单测和 eval 悄悄读到真实生产库——test_market_review_* 就是这么被打破的，
        # 而且只在设了 FINANCE_WS 的服务配置下才复现。
        return "", []
    market_date = _market_data_asof(market_db_path, as_of=as_of)
    db_path = Path(market_db_path).expanduser()
    if not market_date or not db_path.exists():
        return "", []
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return "", []
    con = db_result.connection
    try:
        exists = con.execute(
            """
            select count(*) from information_schema.tables
            where table_schema = 'main' and table_name = 'fact_mainline_theme_daily'
            """
        ).fetchone()
        if not exists or not exists[0]:
            return "", []
        row = con.execute(
            "select max(trade_date) from fact_mainline_theme_daily "
            "where trade_date <= cast(? as date)",
            [market_date],
        ).fetchone()
        theme_date = str(row[0]) if row and row[0] else None
        if theme_date != market_date:
            return str(theme_date or ""), []
        names = [
            str(name)
            for (name,) in con.execute(
                """
                select theme_name from fact_mainline_theme_daily
                where trade_date = ?
                order by min_sort nulls last, theme_name
                limit ?
                """,
                [theme_date, limit],
            ).fetchall()
            if name
        ]
        return market_date, names
    except Exception:
        return "", []
    finally:
        con.close()


def mainline_knowledge_coverage(
    market_db_path: str | Path | None,
    *,
    as_of: str | None = None,
    kb_wiki: str | Path | None = None,
    concepts_per_direction: int = 3,
    companies_per_direction: int = 4,
    evidence_per_direction: int = 3,
    warnings: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """当日主线方向在知识库里有多少积累。

    返回 (主线日期, 每个方向的积累, 库内一条都没有的方向名)。

    按方向逐个取锚，不是把整句问题当题材名去匹配：市场级问题里根本没有题材名，
    match_candidate 在这类问题上必然落空（那正是「当日盘面候选未命中」的来历）。

    结构化返回而不是直接拼字符串，是因为有两个消费方——给 LLM 的证据块和日报
    skill 的模块——它们的渲染不同但不该各查一遍知识库。
    """
    notes = warnings if warnings is not None else []
    market_date, directions = _mainline_theme_names(market_db_path, as_of=as_of)
    if not directions:
        # 只在「读到了盘面库、但主线汇总不同日」时告警。读不到库本身是另一个层级的
        # 问题（新装/无数据根），由盘面侧自己报，不该在这里再响一遍。
        if market_date:
            notes.append(
                "知识库锚点未生成：主线方向汇总与盘面不同日"
                f"（fact_mainline_theme_daily 最新 {market_date}）"
            )
        return market_date, [], []
    from intelligence.adapters.knowledge import KnowledgeAdapter

    try:
        knowledge = KnowledgeAdapter(wiki_root=kb_wiki)
    except Exception as exc:
        notes.append(f"知识库锚点未生成：知识库不可用（{type(exc).__name__}: {exc}）")
        return market_date, [], []

    covered: list[dict[str, Any]] = []
    uncovered: list[str] = []
    for direction in directions:
        try:
            concepts = knowledge.get_concept_matches(
                direction, limit=concepts_per_direction
            ).get("items", [])
            exposures = knowledge.get_exposure_matches(
                direction, limit=companies_per_direction
            ).get("items", [])
            evidence = knowledge.get_evidence(
                direction, limit=evidence_per_direction
            ).get("items", [])
        except Exception as exc:
            notes.append(
                f"知识库锚点跳过方向「{direction}」：{type(exc).__name__}: {exc}"
            )
            continue
        # 用过滤后的值判定，不用原始列表：只匹配到空串的方向会通过原始判定，
        # 却渲染出「- 半导体：」这样后面什么都没有的空行。
        concept_names = [
            str(item.get("concept") or "").strip()
            for item in concepts
            if str(item.get("concept") or "").strip()
        ]
        companies = [
            {
                "company": str(item.get("company") or "").strip(),
                "role": str(item.get("role") or "").strip(),
                "tier": str(
                    item.get("evidence_layer") or item.get("strength") or ""
                ).strip(),
            }
            for item in exposures
            if str(item.get("company") or "").strip()
        ]
        if not concept_names and not companies and not evidence:
            uncovered.append(direction)
            continue
        covered.append(
            {
                "direction": direction,
                "concepts": concept_names,
                "companies": companies,
                "evidence_count": len(evidence),
            }
        )
    return market_date, covered, uncovered


def _format_company(entry: dict[str, Any]) -> str:
    """公司（角色｜证据层级）。层级必须带上：块本身要求模型标注证据层级并且
    不得把 graph_only 写成已兑现事实，而层级不在载荷里的话，模型只能省略或编造。
    实测同一个方向里 graph_only/L2_candidate/L1 会被渲染成完全一样的样子。"""
    company = str(entry.get("company") or "").strip()
    role = str(entry.get("role") or "").strip()
    tier = str(entry.get("tier") or "").strip()
    inner = "｜".join(part for part in (role, tier) if part)
    return f"{company}（{inner}）" if company and inner else company


def _coverage_summary(entry: dict[str, Any]) -> str:
    parts: list[str] = []
    concepts = entry.get("concepts") or []
    companies = entry.get("companies") or []
    evidence_count = int(entry.get("evidence_count") or 0)
    if concepts:
        parts.append(f"概念页 {len(concepts)}（{'、'.join(concepts)}）")
    if companies:
        names = "、".join(_format_company(item) for item in companies if _format_company(item))
        parts.append(f"公司暴露 {len(companies)}（{names}）" if names else f"公司暴露 {len(companies)}")
    if evidence_count:
        parts.append(f"已入库证据 {evidence_count} 条")
    return "；".join(parts)


def _market_review_knowledge_anchor_block_for_llm(
    market_db_path: str | Path | None,
    *,
    as_of: str | None = None,
    kb_wiki: str | Path | None = None,
    concepts_per_direction: int = 3,
    companies_per_direction: int = 4,
    evidence_per_direction: int = 3,
    warnings: list[str] | None = None,
) -> str:
    """盘面回答"哪个方向在走"，知识库回答"我对这个方向研究到什么程度"。

    真正有用的是缺口那一行——盘面已经进主线、库里却一条都没有的方向，正是当天
    最该补研究的地方。
    """
    market_date, covered, uncovered = mainline_knowledge_coverage(
        market_db_path,
        as_of=as_of,
        kb_wiki=kb_wiki,
        concepts_per_direction=concepts_per_direction,
        companies_per_direction=companies_per_direction,
        evidence_per_direction=evidence_per_direction,
        warnings=warnings,
    )
    if not covered and not uncovered:
        return ""
    lines = [
        "## 主线方向的知识库积累 [MAINLINE_KB]",
        f"- 口径：盘面主线取自 fact_mainline_theme_daily（{market_date}），"
        "知识库侧是概念页 / 公司暴露 / 已入库证据。两边分开陈述："
        "知识库有积累不等于当日盘面强，盘面强也不等于库内有依据。",
    ]
    lines.extend(f"- {entry['direction']}：{_coverage_summary(entry)}" for entry in covered)
    if uncovered:
        lines.append(
            f"- 知识库尚无积累的主线方向：{'、'.join(uncovered)}"
            "（盘面已进主线但库内无概念页/公司暴露/证据，是当天最该补研究的方向）"
        )
    lines.append(
        "- 使用要求：引用公司暴露时要带上它的角色与证据层级，不得把 graph_only "
        "或研报判断写成公司已兑现的基本面事实。"
    )
    return "\n".join(lines)


def mainline_knowledge_module(
    market_db_path: str | Path | None,
    *,
    as_of: str | None = None,
    kb_wiki: str | Path | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any] | None:
    """日报 skill 用的模块形态；没有任何可说的就返回 None，不塞空模块。"""
    market_date, covered, uncovered = mainline_knowledge_coverage(
        market_db_path,
        as_of=as_of,
        kb_wiki=kb_wiki,
        warnings=warnings,
    )
    if not covered and not uncovered:
        return None
    items: list[dict[str, Any]] = [
        {"title": entry["direction"], "summary": _coverage_summary(entry)}
        for entry in covered
    ]
    if uncovered:
        items.append(
            {
                "title": "知识库尚无积累",
                "summary": (
                    f"{'、'.join(uncovered)}——盘面已进主线但库内无概念页/公司暴露/证据，"
                    "是当天最该补研究的方向"
                ),
            }
        )
    return {
        "module_id": "daily_knowledge_anchor",
        "title": "主线方向的知识库积累",
        "kind": "list",
        "status": "complete" if covered else "partial",
        "summary": (
            f"主线方向取自 {market_date} 盘面；知识库侧为概念页/公司暴露/已入库证据。"
            "知识库有积累不等于当日盘面强，两者不得互相推导。"
        ),
        "content": None,
        "metrics": [],
        "items": items,
    }


def _resolve_mainline_theme(con: Any, query: str, theme: str | None, latest_date: Any) -> str | None:
    rows = con.execute(
        """
        select distinct theme_name
        from fact_mainline_sector_daily
        where trade_date=?
        order by theme_name
        """,
        [latest_date],
    ).fetchall()
    names = [str(r[0]) for r in rows if r and r[0]]
    text = f"{query or ''} {theme or ''}"
    normalized_text = _normalize(text)
    for name in names:
        n = _normalize(name)
        if n and (n in normalized_text or normalized_text in n):
            return name
    return None


def _classify_mainline_volume_state(pct_chg: Any, diff_ratio: Any, amount: Any) -> str:
    pct = _safe_float(pct_chg)
    diff = _safe_float(diff_ratio)
    amt = _safe_float(amount)
    if pct is not None and pct > 0 and diff is not None and diff > 10 and (amt is None or amt > 500):
        return "真正双红/增量启动"
    if pct is not None and pct > 0 and diff is not None and diff < 0:
        return "缩量强修复/存量抱团"
    if pct is not None and pct > 0 and diff is not None and diff >= 0:
        return "弱放量修复"
    if pct is not None and pct < 0 and diff is not None and diff > 0:
        return "放量分歧/承接检验"
    return "量价状态待确认"


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_optional(value: Any, digits: int = 2) -> str:
    num = _safe_float(value)
    if num is None:
        return "-"
    return f"{num:.{digits}f}"


def _second_derivative_queue_block_for_llm(
    query: str,
    theme: str | None,
    market_db_path: str | Path | None,
    evidence_text: str,
) -> str:
    """Build a structured P0/P1/P2 second-derivative research queue."""
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return _second_derivative_queue_from_text_only(theme, evidence_text)
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return _second_derivative_queue_from_text_only(theme, evidence_text)
    con = db_result.connection

    try:
        stock = _resolve_stock_for_market_block(con, query)
        if not stock:
            return _second_derivative_queue_from_text_only(theme, evidence_text)
        stock_code, stock_name = stock
        latest = con.execute(
            """
            select trade_date, close, pct_chg, amount
            from fact_stock_daily
            where stock_ts_code=? and close is not null
            order by trade_date desc
            limit 1
            """,
            [stock_code],
        ).fetchone()
        if not latest:
            return _second_derivative_queue_from_text_only(theme, evidence_text)
        latest_date, latest_close, latest_pct, latest_amount = latest
        sector_rows = con.execute(
            """
            select sector_name, sw_l1, pct_chg, amount
            from fact_sector_stock_daily
            where trade_date=? and stock_ts_code=?
            order by amount desc
            limit 8
            """,
            [latest_date, stock_code],
        ).fetchall()
        sector_names = _prioritize_sector_names([str(r[0]) for r in sector_rows if r and r[0]], theme)
        sector_lines = _format_sector_state_lines(con, latest_date, sector_names[:5])
        rank_lines = _format_stock_rank_lines(con, latest_date, stock_code, sector_names)
        alternative_lines = _format_alternative_queue_lines(con, latest_date, stock_code, sector_names[:4])
        bottlenecks = _extract_bottleneck_terms(evidence_text)

        lines = ["## 二阶导研究队列数据块 [D3]"]
        lines.append(
            f"- 标的状态：{stock_name}（{stock_code}）最新有效交易日 {latest_date}，涨跌幅 {latest_pct}%，成交额 {latest_amount} 亿；"
            + ("相对强度=" + "；".join(rank_lines[:4]) if rank_lines else "相对强度排名未取到")
        )
        lines.append(
            "- P0 盘面已选择的强势替代表达："
            + ("；".join(alternative_lines[:6]) if alternative_lines else "未从同题材中取到明确强势替代队列，需观察是否只是目标股孤立行情。")
        )
        lines.append(
            "- P1 目标股再升级条件："
            + f"观察 {stock_name} 是否重新进入所属题材涨幅/成交前排、是否收复近 90 日高点或形成新高，并且关联题材从非双红转为连续双红；"
            + ("当前关联题材状态=" + "；".join(sector_lines[:5]) if sector_lines else "当前关联题材双红状态未取到")
        )
        lines.append(
            "- P2 产业瓶颈补盲："
            + ("围绕 " + "、".join(bottlenecks[:8]) + " 查找客户验证、产能、良率、涨价、国产替代和上游材料/设备约束。" if bottlenecks else "本轮证据文本未抽到明确瓶颈词；需要用年报、互动易、公告或研报全文补公司产品结构、客户链和上游约束。")
        )
        lines.append(
            "- 反向观察：若板块继续有双红/新高集群但目标股相对强度掉队，优先把它降为后排跟随或旧逻辑分歧承接；若替代队列持续扩散而目标股不修复，说明市场可能已经选择了更优表达。"
        )
        return "\n".join(lines)
    except Exception:
        return _second_derivative_queue_from_text_only(theme, evidence_text)
    finally:
        try:
            con.close()
        except Exception:
            pass


def _second_derivative_queue_from_text_only(theme: str | None, evidence_text: str) -> str:
    bottlenecks = _extract_bottleneck_terms(evidence_text)
    lines = ["## 二阶导研究队列数据块 [D3]"]
    lines.append("- P0 盘面已选择的强势替代表达：本轮未取到 DuckDB 同题材强势替代队列，回答时必须把这一项作为数据缺口说明。")
    lines.append("- P1 目标股再升级条件：需要补最新相对强度、成交额边际、所属题材双红/新高/涨停扩散，确认它是核心、同步、补涨还是后排。")
    lines.append(
        "- P2 产业瓶颈补盲："
        + ("围绕 " + "、".join(bottlenecks[:8]) + " 继续查客户验证、订单、产能和上游约束。" if bottlenecks else f"围绕 {theme or '命中主题'} 补上游材料/设备、关键客户、价格传导和替代公司。")
    )
    lines.append("- 反向观察：若缺少 P0/P1 数据，不能直接给出强趋势结论，只能提出待验证假设。")
    return "\n".join(lines)


def _extract_bottleneck_terms(text: str) -> list[str]:
    terms = [
        "HBM",
        "DDR5",
        "CXL",
        "TLVR",
        "AI电感",
        "钽电容",
        "MLCC",
        "LTCC",
        "银浆",
        "磁性材料",
        "陶瓷粉体",
        "玻璃基板",
        "CoWoS",
        "先进封装",
        "存储",
        "光模块",
        "CPO",
        "交换芯片",
        "电源模块",
        "功率模块",
        "良率",
        "产能",
        "涨价",
        "国产替代",
        "客户验证",
        "量产",
    ]
    out: list[str] = []
    lower = text.lower()
    for term in terms:
        if term.lower() in lower and term not in out:
            out.append(term)
    return out


def _append_block_outcome(
    result: AskResult,
    outcome: ask_planner.BlockOutcome,
    evidence_text: str,
    citations: list[Citation],
) -> str:
    """把并行子任务的取数结果按原有串行语义汇总：登记可观测、拼 evidence、记引用。"""
    if outcome.error:
        result.warnings.append(f"{outcome.tag} {outcome.label}块生成失败（已降级为缺失）：{outcome.error}")
    result.d_block_stats.append(_d_block_stat(outcome.tag, outcome.label, outcome.block))
    if outcome.block:
        evidence_text = f"{evidence_text}\n\n{outcome.block}"
        if outcome.citation is not None:
            citations.append(outcome.citation)
    return evidence_text


def _d_block_stat(tag: str, source: str, block: str | None) -> research_brief.DBlockStat:
    text = (block or "").strip()
    return research_brief.DBlockStat(
        tag,
        source,
        attempted=True,
        generated=bool(text),
        line_count=len(text.splitlines()) if text else 0,
        note="" if text else "无匹配数据或未提供 market_db_path",
    )


def _daily_market_overview_block_for_llm(
    market_db_path: str | Path | None,
    *,
    as_of: str | None = None,
) -> str:
    db_path = (
        Path(market_db_path).expanduser()
        if market_db_path
        else DEFAULT_MARKET_DB_PATH
    )
    if not db_path.exists():
        return ""
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return ""
    con = db_result.connection

    try:
        table_names = {
            str(row[0])
            for row in con.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'main'
                """
            ).fetchall()
        }
        if "fact_market_daily" not in table_names:
            return ""

        available_columns = {
            str(row[1])
            for row in con.execute("pragma table_info('fact_market_daily')").fetchall()
        }
        wanted_columns = (
            "trade_date",
            "market_stage",
            "stage_day",
            "total_amount",
            "amount_vs_yesterday_pct",
            "volume_ratio",
            "volume_state",
            "advancers",
            "limit_up",
            "limit_down",
            "sh_index_close",
            "sh_index_pct_chg",
            "concentration_state",
            "industry_1",
            "industry_1_ratio",
            "industry_2",
            "industry_2_ratio",
            "industry_3",
            "industry_3_ratio",
            "strength_avg_pct",
            "strength_marginal_pct",
            "strength_status",
        )
        select_columns = [
            column if column in available_columns else f"null as {column}"
            for column in wanted_columns
        ]
        row = con.execute(
            f"""
            select {", ".join(select_columns)}
            from fact_market_daily
            where (? is null or trade_date <= cast(? as date))
            order by trade_date desc
            limit 1
            """,
            [as_of, as_of],
        ).fetchone()
        if not row or not row[0]:
            return ""

        values = dict(zip(wanted_columns, row, strict=True))
        trade_date = str(values["trade_date"])
        stage = str(values["market_stage"] or "未标注")
        stage_day = values["stage_day"]
        stage_text = f"{stage}（第 {stage_day} 天）" if stage_day is not None else stage
        lines = [
            "## 本地 DuckDB 最新市场总览",
            f"- 市场数据截至：{trade_date}。该日期是本轮整体盘面日期。",
            f"- 市场阶段：{stage_text}；量能状态：{values['volume_state'] or '未标注'}。",
            (
                f"- 全市场成交额：{_fmt_optional(values['total_amount'])} 亿元；"
                f"较前一日 {_fmt_optional(values['amount_vs_yesterday_pct'])}%；"
                f"量比 {_fmt_optional(values['volume_ratio'])}%。"
            ),
            (
                f"- 涨跌结构：上涨 {values['advancers'] if values['advancers'] is not None else '-'} 家；"
                f"涨停 {values['limit_up'] if values['limit_up'] is not None else '-'} 家；"
                f"跌停 {values['limit_down'] if values['limit_down'] is not None else '-'} 家。"
            ),
            (
                f"- 上证指数：{_fmt_optional(values['sh_index_close'], 3)} 点，"
                f"当日 {_fmt_optional(values['sh_index_pct_chg'])}%。"
            ),
            (
                f"- 强势股状态：{values['strength_status'] or '未标注'}；"
                f"平均涨幅 {_fmt_optional(values['strength_avg_pct'])}%；"
                f"边际变化 {_fmt_optional(values['strength_marginal_pct'])}%。"
            ),
        ]

        industries = [
            (values["industry_1"], values["industry_1_ratio"]),
            (values["industry_2"], values["industry_2_ratio"]),
            (values["industry_3"], values["industry_3_ratio"]),
        ]
        industry_text = "、".join(
            f"{name}（{_fmt_optional(ratio)}%）"
            for name, ratio in industries
            if name
        )
        if industry_text:
            lines.append(
                f"- 行业集中度：{values['concentration_state'] or '未标注'}；"
                f"领先行业为 {industry_text}。"
            )

        theme_date = None
        if "fact_mainline_theme_daily" in table_names:
            theme_date_row = con.execute(
                "select max(trade_date) from fact_mainline_theme_daily "
                "where trade_date <= cast(? as date)",
                [trade_date],
            ).fetchone()
            theme_date = theme_date_row[0] if theme_date_row else None
            if theme_date:
                themes = con.execute(
                    """
                    select theme_name, sector_count
                    from fact_mainline_theme_daily
                    where trade_date = ?
                    order by min_sort nulls last, theme_name
                    limit 10
                    """,
                    [theme_date],
                ).fetchall()
                theme_text = "、".join(
                    f"{name}（{sector_count or 0} 个核心板块）"
                    for name, sector_count in themes
                    if name
                )
                if theme_text and str(theme_date) == trade_date:
                    lines.append(f"- 主线题材（截至 {theme_date}）：{theme_text}。")
                elif theme_text:
                    lines.append(
                        f"- 主线题材汇总仅截至 {theme_date}，早于整体盘面日期 {trade_date}；"
                        "当前题材级主线未知，不展示旧题材名称。"
                    )

        if "fact_mainline_sector_daily" in table_names:
            sector_date_row = con.execute(
                "select max(trade_date) from fact_mainline_sector_daily "
                "where trade_date <= cast(? as date)",
                [trade_date],
            ).fetchone()
            sector_date = sector_date_row[0] if sector_date_row else None
            if sector_date and str(sector_date) != trade_date:
                if theme_date and str(theme_date) == trade_date:
                    lines.append(
                        f"- 局部数据提示：题材级主线汇总已更新到 {trade_date}，"
                        f"但核心板块明细仅更新到 {sector_date}；当前核心板块、周期状态和标的未知。"
                    )
                else:
                    lines.append(
                        f"- 局部数据提示：核心板块明细仅更新到 {sector_date}，"
                        f"早于整体盘面日期 {trade_date}；只能作历史参考。"
                    )
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        con.close()


def _market_cause_window_block_for_llm(
    market_db_path: str | Path | None,
    *,
    window: int = 5,
    as_of: str | None = None,
) -> str:
    """固定口径输出最近 N 个交易日的市场变化，供原因归因工具使用。

    这里只描述可核验的周内变化，不把盘面现象自动解释成外部因果；因果证据
    由 market_data 与 news/web 工具共同提供，避免单日复盘块冒充周度归因。
    """
    db_path = (
        Path(market_db_path).expanduser()
        if market_db_path
        else DEFAULT_MARKET_DB_PATH
    )
    if not db_path.exists():
        return ""
    # 连接由 try_connect_readonly 统一取，与本文件其余块一致：它内部兜住
    # duckdb 缺失（dependency_unavailable）和打开失败（open_failed），不抛异常，
    # 所以这里不需要再包一层 try，也不需要单独的 `import duckdb` 可用性探针。
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return ""
    con = db_result.connection
    try:
        rows = con.execute(
            """
            select trade_date, market_stage, stage_day, total_amount,
                   advancers, limit_up, limit_down, sh_index_close,
                   sh_index_pct_chg, industry_1, industry_1_ratio,
                   industry_2, industry_2_ratio, industry_3, industry_3_ratio
            from fact_market_daily
            where (? is null or trade_date <= cast(? as date))
            order by trade_date desc
            limit ?
            """,
            [as_of, as_of, max(2, min(int(window), 10))],
        ).fetchall()
        if not rows:
            return ""
        rows = list(reversed(rows))
        dates = [str(row[0]) for row in rows]
        first_close = rows[0][7]
        last_close = rows[-1][7]
        cumulative_pct = None
        try:
            cumulative_pct = (float(last_close) / float(first_close) - 1) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        down_days = sum(
            1 for row in rows if row[8] is not None and float(row[8]) < 0
        )
        first_amount, last_amount = rows[0][3], rows[-1][3]
        amount_change = None
        try:
            amount_change = (float(last_amount) / float(first_amount) - 1) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        lines = [
            "## 最近交易日市场原因归因窗口 [MCAUSE]",
            f"- 窗口：{dates[0]} ~ {dates[-1]}，共 {len(rows)} 个交易日；该块只描述周内变化，不等同于外部因果。",
            f"- 上证指数：{first_close if first_close is not None else '—'} → {last_close if last_close is not None else '—'} 点；区间变化 {cumulative_pct:.2f}% 。" if cumulative_pct is not None else "- 上证指数区间变化：缺数据。",
            f"- 下跌交易日：{down_days}/{len(rows)}；成交额 {first_amount if first_amount is not None else '—'} → {last_amount if last_amount is not None else '—'} 亿元；区间变化 {amount_change:.2f}% 。" if amount_change is not None else "- 成交额区间变化：缺数据。",
        ]
        for row in rows:
            industries = "、".join(
                f"{row[i] or '—'}({row[i + 1] if row[i + 1] is not None else '—'}%)"
                for i in (9, 11, 13)
                if row[i]
            )
            lines.append(
                f"- {row[0]}：指数 {row[8] if row[8] is not None else '—'}%；"
                f"成交 {row[3] if row[3] is not None else '—'} 亿；"
                f"上涨 {row[4] if row[4] is not None else '—'} 家；"
                f"涨停/跌停 {row[5] if row[5] is not None else '—'}/{row[6] if row[6] is not None else '—'}；"
                "行业成交额占全市场比例前三"
                f"（括号为成交额占比，绝非行业涨跌幅）{industries or '—'}。"
            )
        lines.append("- 因果使用要求：只能把与上述时间窗口对齐的新闻、宏观、外盘或资金证据作为原因；没有对齐证据时保留为候选解释并报告缺口。")
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass


def _market_data_asof(
    market_db_path: str | Path | None,
    *,
    as_of: str | None = None,
) -> str | None:
    """盘面库 fact_market_daily 最新交易日（回检块新鲜度自检用）；库/duckdb 不可用返回 None。"""
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return None
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return None
    con = db_result.connection
    try:
        # 连接由函数顶部的 try_connect_readonly 统一管理（legacy 分支的重构），
        # 查询保留 as_of 上界（exposure 分支）——签名收了 as_of 就必须用，
        # 否则回检块的时间边界会静默失效。
        row = con.execute(
            "SELECT MAX(trade_date) FROM fact_market_daily "
            "WHERE (? IS NULL OR trade_date <= CAST(? AS DATE))",
            [as_of, as_of],
        ).fetchone()
        return str(row[0]) if row and row[0] else None
    except Exception:
        return None
    finally:
        con.close()


def _is_market_index_comparison_query(query: str) -> bool:
    names = ("上证指数", "深证成指", "创业板指")
    return sum(name in query for name in names) >= 2


def _quoted_topic(query: str) -> str | None:
    match = re.search(r"[“《\"]([^”》\"]{2,40})[”》\"]", query)
    return match.group(1).strip() if match else None


def _theme_research_framing(
    research_spec: answer_model.ThemeResearchSpec | None,
    matched_theme: str | None,
) -> dict[str, list[str]]:
    if research_spec is None:
        return {}
    stage_labels = ("上游", "中游", "下游")
    chain_lines = [
        f"产业链{stage_labels[index] if index < len(stage_labels) else index + 1}"
        f"（研究口径，待公司级证据验证）：{stage}。"
        for index, stage in enumerate(research_spec.chain_stages)
    ]
    framing = {
        "conclusion": [
            f"题材定义（研究口径，非公司级事实）：{research_spec.definition}"
        ],
        "evidence": [
            *chain_lines,
            f"公司映射边界：{research_spec.company_scope}",
        ],
        "gaps": [
            "事实、推测与待验证边界：题材定义和产业链属于研究口径；"
            f"公司结论必须满足：{'、'.join(research_spec.evidence_requirements)}。"
        ],
        "follow_ups": [
            f"核验动作：{action}" for action in research_spec.verification_actions
        ],
    }
    if matched_theme and matched_theme not in research_spec.theme:
        framing["conclusion"].append(
            f"盘面数据仅以“{matched_theme}”作为近似映射，不能替代"
            f"“{research_spec.theme}”本身的公司级证据。"
        )
    return framing


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _confidence_score(value: Any) -> float | None:
    normalized = str(value or "").strip().lower()
    mapped = {
        "high": 0.9,
        "medium": 0.65,
        "mid": 0.65,
        "low": 0.35,
    }.get(normalized)
    return mapped if mapped is not None else _finite_float(value)


def _populate_market_index_comparison(
    result: AskResult,
    query: str,
    market_db_path: str | Path | None,
) -> None:
    requested = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", query)
    trade_date = requested.group(1) if requested else result.trade_date
    result.trade_date = trade_date
    result.next_trade_date = next_trading_day(
        trade_date,
        db_path=market_db_path,
    )
    db_path = (
        Path(market_db_path).expanduser()
        if market_db_path
        else DEFAULT_MARKET_DB_PATH
    )
    row: tuple[Any, ...] | None = None
    if trade_date and db_path.exists():
        db_result = retrieval_cache.try_connect_readonly(db_path)
        if db_result.available:
            con = db_result.connection
            try:
                row = con.execute(
                    """
                    select sh_index_close, sh_index_pct_chg, sh_index_amount,
                           sh_index_volume, sh_index_source
                    from fact_market_daily
                    where trade_date = ?
                    """,
                    [trade_date],
                ).fetchone()
            except Exception:
                row = None
            finally:
                con.close()

    evidence: list[str] = []
    gaps: list[str] = []
    citations: list[Citation] = []
    if row:
        close = _finite_float(row[0])
        pct_chg = _finite_float(row[1])
        amount = _finite_float(row[2])
        volume = _finite_float(row[3])
        raw_source = str(row[4] or "")
        source = (
            "AkShare 上证指数日线"
            if raw_source.startswith("akshare:")
            else "本地市场数据"
        )
        metric = "成交额缺失；成交量等可用强弱指标也缺失"
        if amount is not None:
            metric = f"成交额 {amount / 100_000_000:.2f} 亿元"
        elif volume is not None:
            metric = (
                f"成交额缺失；可用强弱指标为成交量 "
                f"{volume / 100_000_000:.2f} 亿"
            )
        close_text = f"{close:.3f}" if close is not None else "缺失"
        pct_text = f"{pct_chg:+.2f}%" if pct_chg is not None else "缺失"
        evidence.append(
            f"上证指数：收盘 {close_text}，当日涨跌 {pct_text}，{metric}；"
            f"来源：{source}；数据截止日：{trade_date}。[S1]"
        )
        citations.append(
            Citation(
                "S1",
                source,
                f"上证指数日线，截至 {trade_date}",
            )
        )
        result.found_market = True
    else:
        evidence.append(
            f"上证指数：当日涨跌、成交或强弱指标均缺失；"
            f"当前本地数据源未找到 {trade_date or '目标日期'} 记录，不猜测。"
        )
        gaps.append("上证指数目标交易日记录缺失。")

    for name in ("深证成指", "创业板指"):
        evidence.append(
            f"{name}：当日涨跌、成交或强弱指标均缺失；"
            "当前本地市场库未覆盖该指数日线，不使用其他指数或自然语言描述代替。"
        )
        gaps.append(f"{name}日线未接入，无法完成三指数强弱排序。")

    next_trade_line = (
        f"下一交易日为 {result.next_trade_date}（按交易日历确认）。"
        if result.next_trade_date
        else "下一交易日待交易日历确认，不按自然日猜测。"
    )
    conclusion = [
        f"{trade_date or '目标日期'} 的三指数对比只能部分完成："
        "上证指数有可验证日线，深证成指和创业板指明确缺失。",
        next_trade_line,
    ]
    result.sections = {
        "结论": conclusion,
        "证据链": evidence,
        "分歧反证": gaps
        or ["三项指数均有完整同口径日线，可直接比较。"],
        "后续验证点": [
            "补同步深证成指与创业板指同一交易日的收盘、涨跌幅和成交指标。",
            "三项指数必须使用同一来源、同一截止日后再做强弱排序。",
            f"在 {result.next_trade_date or '下一交易日'} 开盘前复核数据是否完成更新。",
        ],
        "检索可观测": [],
        "输出质检": [],
        "交易含义": [
            "当前只能确认上证指数当日表现，不能据此推断深证成指或创业板指相对强弱。"
        ],
        "引用来源": [
            f"[{citation.tag}] {citation.source} — {citation.detail}"
            for citation in citations
        ],
    }
    result.citations = citations


def _market_value_block_for_llm(
    query: str,
    theme: str | None,
    market_db_path: str | Path | None,
) -> str:
    """Build a deterministic market-value and alternative-queue block.

    This is intentionally lightweight and best-effort. It enriches compose
    answers with measurable L4 context without turning the LLM into a calculator.
    """
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return ""
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return ""
    con = db_result.connection
    try:
        stock = _resolve_stock_for_market_block(con, query)
        if not stock:
            return ""
        stock_code, stock_name = stock
        latest = con.execute(
            """
            select trade_date, close, pct_chg, amount
            from fact_stock_daily
            where stock_ts_code=? and close is not null
            order by trade_date desc
            limit 1
            """,
            [stock_code],
        ).fetchone()
        if not latest:
            return ""
        latest_date, latest_close, latest_pct, latest_amount = latest
        rows = con.execute(
            """
            select trade_date, close
            from fact_stock_daily
            where stock_ts_code=? and close is not null
              and trade_date >= cast(? as date) - interval 90 day
              and trade_date <= cast(? as date)
            order by trade_date
            """,
            [stock_code, latest_date, latest_date],
        ).fetchall()
        value_lines = _format_market_value_rows(rows, latest_close)

        sector_rows = con.execute(
            """
            select sector_name, sw_l1, pct_chg, amount
            from fact_sector_stock_daily
            where trade_date=? and stock_ts_code=?
            order by amount desc
            limit 8
            """,
            [latest_date, stock_code],
        ).fetchall()
        sector_names = _prioritize_sector_names([str(r[0]) for r in sector_rows if r and r[0]], theme)
        rank_lines = _format_stock_rank_lines(con, latest_date, stock_code, sector_names)
        sector_lines = _format_sector_state_lines(con, latest_date, sector_names[:5])
        alternative_lines = _format_alternative_queue_lines(con, latest_date, stock_code, sector_names[:4])

        lines = [
            "## 市场价值与替代队列数据块 [D1]",
            f"- 标的识别：{stock_name}（{stock_code}），最新有效交易日 {latest_date}，收盘 {latest_close}，当日涨跌幅 {latest_pct}%，成交额 {latest_amount} 亿。",
        ]
        lines.extend(value_lines)
        if sector_lines:
            lines.append("- 关联题材/行业状态：" + "；".join(sector_lines))
        if rank_lines:
            lines.append("- 个股相对强度排名：" + "；".join(rank_lines))
        if alternative_lines:
            lines.append("- 同题材强势替代队列：" + "；".join(alternative_lines))
        lines.append("- 使用要求：把该块用于回答 CAR/峰后回撤/半衰期代理、相对强度和二阶导，不要机械照抄；若指标口径不足，要说明这是本地 DuckDB 的代理口径。")
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass


def _resolve_stock_for_market_block(con: Any, query: str) -> tuple[str, str] | None:
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


def _prioritize_sector_names(sector_names: list[str], theme: str | None) -> list[str]:
    """Prefer the matched theme when a stock is mapped to many sectors."""
    names = [s for s in dict.fromkeys(sector_names) if s]
    if not theme:
        return names
    normalized_theme = _normalize(theme)
    matched = [s for s in names if normalized_theme and (_normalize(s) in normalized_theme or normalized_theme in _normalize(s))]
    if not matched:
        return names
    preferred = matched[0]
    return [preferred] + [s for s in names if s != preferred]


def _format_market_value_rows(rows: list[tuple[Any, Any]], latest_close: float | None) -> list[str]:
    clean = [(r[0], float(r[1])) for r in rows if r and r[1] is not None]
    if len(clean) < 2 or latest_close is None:
        return ["- 市场价值成绩单：近 90 日有效行情不足，CAR/峰后回撤/半衰期代理未取到。"]
    base_date, base_close = clean[0]
    peak_date, peak_close = max(clean, key=lambda x: x[1])
    latest = float(latest_close)
    interval_gain = _pct(latest / base_close - 1)
    peak_gain = _pct(peak_close / base_close - 1)
    drawdown = _pct(latest / peak_close - 1)
    retention = None
    if peak_gain and peak_gain > 0:
        retention = latest / base_close - 1
        retention = round(retention / (peak_gain / 100) * 100, 2)
    half_life = "未跌破峰值收益一半" if retention is not None and retention >= 50 else "已跌破峰值收益一半" if retention is not None else "未计算"
    return [
        f"- 市场价值成绩单：从 {base_date} 到 {clean[-1][0]} 区间涨幅 {interval_gain}%，峰值日 {peak_date} 峰值涨幅 {peak_gain}%，峰后回撤 {drawdown}%，峰值收益保留率 {retention if retention is not None else '—'}%，半衰期代理={half_life}。",
    ]


def _format_stock_rank_lines(con: Any, latest_date: Any, stock_code: str, sector_names: list[str]) -> list[str]:
    if not sector_names:
        return []
    out: list[str] = []
    for sector in sector_names[:5]:
        row = con.execute(
            """
            with base as (
              select sector_name, stock_ts_code, stock_name, pct_chg, amount,
                     rank() over(partition by sector_name order by amount desc nulls last) as amount_rank,
                     rank() over(partition by sector_name order by pct_chg desc nulls last) as pct_rank,
                     count(*) over(partition by sector_name) as n
              from fact_sector_stock_daily
              where trade_date=? and sector_name=?
            )
            select amount_rank, pct_rank, n, pct_chg, amount
            from base where stock_ts_code=?
            """,
            [latest_date, sector, stock_code],
        ).fetchone()
        if row:
            out.append(f"{sector}成交排名{row[0]}/{row[2]}、涨幅排名{row[1]}/{row[2]}、涨跌幅{row[3]}%、成交{row[4]}亿")
    return out


def _format_sector_state_lines(con: Any, latest_date: Any, sector_names: list[str]) -> list[str]:
    if not sector_names:
        return []
    out: list[str] = []
    for sector in sector_names:
        row = con.execute(
            """
            select pct_chg, amount, diff_ratio
            from fact_sector_daily
            where trade_date=? and sector_name=?
            limit 1
            """,
            [latest_date, sector],
        ).fetchone()
        if row:
            proxy = "双红代理" if (row[0] or 0) > 0 and (row[2] or 0) > 0 else "非双红代理"
            out.append(f"{sector}{row[0]}%、成交{row[1]}亿、边际量{row[2]}%，{proxy}")
    return out


def _valuation_block_for_llm(
    query: str,
    theme: str | None,
    market_db_path: str | Path | None,
    fetcher: Any = None,
    *,
    as_of: str | None = None,
    snapshot_date_hint: str | None = None,
) -> str:
    """Build the D5 valuation block: target snapshot + same-theme peer band.

    目标/可比标的从本地 DuckDB 解析（可比取同板块成交额前排），估值快照走东财
    免费接口（valuation_estimate）；网络或库不可用时返回带显式缺口的块或空串。
    """
    fetch = fetcher or valuation_estimate.fetch_eastmoney_snapshot
    if not valuation_estimate.fetch_enabled():
        return valuation_estimate.build_valuation_block(None, [], fetch_disabled=True)
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    target_code: str | None = None
    target_name = ""
    peer_codes: list[tuple[str, str]] = []
    local_snapshots: dict[str, valuation_estimate.ValuationSnapshot] = {}
    if db_path.exists():
        db_result = retrieval_cache.try_connect_readonly(db_path)
        if db_result.available:
            con = db_result.connection
            try:
                stock = _resolve_stock_for_market_block(con, query)
                if stock:
                    target_code, target_name = stock
                    latest = con.execute(
                        "select max(trade_date) from fact_sector_stock_daily "
                        "where stock_ts_code=? "
                        "and (? is null or trade_date <= cast(? as date))",
                        [target_code, as_of, as_of],
                    ).fetchone()
                    latest_date = latest[0] if latest else None
                    if latest_date is not None:
                        local_target = _local_valuation_snapshot(
                            con,
                            target_code,
                            target_name,
                            str(latest_date),
                        )
                        if local_target is not None:
                            local_snapshots[target_code] = local_target
                        sector_rows = con.execute(
                            """
                            select sector_name from fact_sector_stock_daily
                            where trade_date=? and stock_ts_code=?
                            order by amount desc limit 4
                            """,
                            [latest_date, target_code],
                        ).fetchall()
                        sectors = _prioritize_sector_names([str(r[0]) for r in sector_rows if r and r[0]], theme)
                        if sectors:
                            rows = con.execute(
                                """
                                select stock_ts_code, stock_name from fact_sector_stock_daily
                                where trade_date=? and sector_name=? and stock_ts_code<>?
                                order by amount desc nulls last limit 4
                                """,
                                [latest_date, sectors[0], target_code],
                            ).fetchall()
                            peer_codes = [(str(c), str(n or c)) for c, n in rows]
                            for peer_code, peer_name in peer_codes:
                                local_peer = _local_valuation_snapshot(
                                    con,
                                    peer_code,
                                    peer_name,
                                    str(latest_date),
                                )
                                if local_peer is not None:
                                    local_snapshots[peer_code] = local_peer
            except Exception:
                pass
            finally:
                con.close()
    if target_code is None:
        code_match = re.search(r"\b(\d{6})(?:\.(SH|SZ|BJ))?\b", str(query or ""), re.I)
        if not code_match:
            return ""
        target_code = code_match.group(1)
    use_live_snapshot = not (
        as_of
        and snapshot_date_hint
        and str(snapshot_date_hint)[:10] > str(as_of)[:10]
    )
    target = fetch(target_code, target_name) if use_live_snapshot else None
    if not _valuation_snapshot_within_as_of(target, as_of):
        target = local_snapshots.get(target_code)
    peers = []
    for peer_code, peer_name in peer_codes:
        candidate = fetch(peer_code, peer_name) if use_live_snapshot else None
        if not _valuation_snapshot_within_as_of(candidate, as_of):
            candidate = local_snapshots.get(peer_code)
        if candidate is not None:
            peers.append(candidate)
    return valuation_estimate.build_valuation_block(target, peers)


def _valuation_snapshot_within_as_of(
    snapshot: valuation_estimate.ValuationSnapshot | None,
    as_of: str | None,
) -> bool:
    if snapshot is None:
        return False
    if not as_of:
        return True
    source_date = str(snapshot.source_date or "")[:10]
    return bool(source_date) and source_date <= str(as_of)[:10]


def _local_valuation_snapshot(
    con: Any,
    stock_code: str,
    stock_name: str,
    trade_date: str,
) -> valuation_estimate.ValuationSnapshot | None:
    try:
        row = con.execute(
            """
            select stock_name, total_mcap_yi
            from fact_sector_stock_daily
            where trade_date = cast(? as date) and stock_ts_code = ?
              and total_mcap_yi is not null and total_mcap_yi > 0
            order by amount desc nulls last
            limit 1
            """,
            [trade_date, stock_code],
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    return valuation_estimate.ValuationSnapshot(
        ts_code=stock_code,
        name=str(row[0] or stock_name or stock_code),
        total_mv_yi=float(row[1]),
        source_date=str(trade_date)[:10],
        source="本地 DuckDB 市值快照",
    )


def _financials_block_for_llm(
    query: str,
    market_db_path: str | Path | None,
    fetcher: Any = None,
    timeout: float = 8.0,
) -> str:
    """Build the D7 quarterly-financials block for a single target stock.

    目标股从本地 DuckDB 解析（代码/名称），逐季财务走 D7 provider 链
    （东财 F10 → 新浪利润表 → AKShare）；解析不到目标股时返回空串（不追加块），
    网络/库不可用时返回带显式缺口的块。
    """
    if not market_financials.fetch_enabled():
        return market_financials.build_financials_block("", "", [], fetch_disabled=True)
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    target_code: str | None = None
    target_name = ""
    if db_path.exists():
        db_result = retrieval_cache.try_connect_readonly(db_path)
        if db_result.available:
            con = db_result.connection
            try:
                stock = _resolve_stock_for_market_block(con, query)
                if stock:
                    target_code, target_name = stock
            except Exception:
                pass
            finally:
                con.close()
    if target_code is None:
        code_match = re.search(r"\b(\d{6})(?:\.(SH|SZ|BJ))?\b", str(query or ""), re.I)
        if not code_match:
            return ""
        target_code = code_match.group(0)
    return market_financials.financials_block_for_target(
        target_code,
        target_name,
        fetcher=fetcher,
        timeout=timeout,
    )


def _format_alternative_queue_lines(con: Any, latest_date: Any, stock_code: str, sector_names: list[str]) -> list[str]:
    if not sector_names:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for sector in sector_names:
        rows = con.execute(
            """
            select sector_name, stock_name, pct_chg, amount, pct_chg_5d, pct_chg_10d, high_status_label, limit_times
            from fact_sector_stock_daily
            where trade_date=? and stock_ts_code<>? and sector_name=?
            order by pct_chg desc nulls last, amount desc nulls last
            limit 5
            """,
            [latest_date, stock_code, sector],
        ).fetchall()
        added_for_sector = 0
        for sector_name, name, pct, amount, pct5, pct10, high, limits in rows:
            if name in seen:
                continue
            seen.add(str(name))
            added_for_sector += 1
            tag = f"，{high}" if high else ""
            limit_tag = f"，涨停次数{limits}" if limits else ""
            out.append(f"{name}({sector_name}) {pct}%、成交{amount}亿、5日{pct5}%、10日{pct10}%{tag}{limit_tag}")
            if len(out) >= 6 or added_for_sector >= 3:
                break
        if len(out) >= 6:
            break
    return out


def _pct(value: float) -> float:
    return round(value * 100, 2)

"""ask 的表达层：六段模板渲染与会话渲染（从 ask.py 拆出，行为不变）。"""

from __future__ import annotations


import re

from intelligence.services import (
    answer_model,
)
from intelligence.services.ask_types import (
    SUBHEAD,
    SECTION_ORDER,
    NO_EVIDENCE_NOTICE,
    AskResult,
)



def render_answer(result: AskResult) -> str:
    use_research_answer_spec = result.answer_spec is not None
    lines: list[str] = []
    lines.append(f"# ask：{result.query}")
    if result.clarify is not None:
        lines.append("")
        lines.append("## 【澄清追问】")
        lines.extend(f"- {line}" for line in result.clarify.summary_lines())
        lines.append("")
        lines.append("（问题过于模糊，本次未检索；补充后重新提问，或用 --no-clarify 强制硬答。）")
        return "\n".join(lines) + "\n"
    meta = [
        f"盘面日期={result.trade_date or '—'}",
        f"命中主题={result.matched_theme or '—'}",
        f"模块路由={'/'.join(result.routed_modules) or '—'}",
        f"召回状态={result.status}",
    ]
    if result.wiki_rag_telemetry is not None and result.wiki_rag_telemetry.status != "pending":
        t = result.wiki_rag_telemetry
        meta.append(f"W检索={t.mode}/{t.index_kind or '?'}·命中{t.hit_count}·{t.status}")
    lines.append("> " + " | ".join(meta))
    if result.warnings:
        lines.append("> 警告：" + "；".join(result.warnings))
    if not result.citations and not use_research_answer_spec:
        lines.append(f"> {NO_EVIDENCE_NOTICE}")
    if result.synthesis:
        lines.append("")
        lines.append("## 【对话式回答】"
                     + (f"（LLM·{result.llm_provider} 有机合成）" if result.llm_provider else ""))
        lines.append("")
        lines.append(result.synthesis.rstrip())
        lines.append("")
        lines.append("---")
        lines.append("*以下为确定性检索的结构化证据，供核对引用编号：*")
    elif use_research_answer_spec:
        assert result.answer_spec is not None
        lines.append("")
        lines.append(answer_model.render_answer_spec(result.answer_spec).rstrip())
        if result.detail_reports:
            lines.append("")
            lines.append("## 【模块完整报告（--detail 钻取）】")
            for label, body in result.detail_reports:
                lines.extend(
                    [
                        "",
                        f"<details><summary>完整报告 · {label}</summary>",
                        "",
                        body.rstrip(),
                        "",
                        "</details>",
                    ]
                )
        return "\n".join(lines) + "\n"
    for name in SECTION_ORDER:
        lines.append("")
        lines.append(f"## 【{name}】")
        for item in result.sections.get(name, []):
            if item.startswith(SUBHEAD):
                lines.append(f"\n*{item[len(SUBHEAD):]}*")
            else:
                lines.append(f"- {item}")
    if result.detail_reports:
        lines.append("")
        lines.append("## 【模块完整报告（--detail 钻取）】")
        for label, body in result.detail_reports:
            lines.append("")
            lines.append(f"<details><summary>完整报告 · {label}</summary>")
            lines.append("")
            lines.append(body.rstrip())
            lines.append("")
            lines.append("</details>")
    return "\n".join(lines) + "\n"


def render_conversation_answer(result: AskResult) -> str:
    evidence_notice = f"{NO_EVIDENCE_NOTICE}\n\n" if not result.citations else ""
    if result.synthesis:
        return result.synthesis
    if result.answer_spec is not None:
        return answer_model.render_answer_spec(result.answer_spec)

    lines: list[str] = []
    if evidence_notice:
        lines.append(NO_EVIDENCE_NOTICE)
    if result.data_notice:
        if lines:
            lines.append("")
        lines.append(result.data_notice)
    if re.search(r"T\+1|下一交易日|明天", result.query, re.IGNORECASE):
        if lines:
            lines.append("")
        if result.next_trade_date:
            lines.append(
                f"下一交易日为 {result.next_trade_date}（按交易日历确认，不按自然日顺延）。"
            )
        else:
            lines.append("下一交易日（日期待交易日历确认），不得按自然日猜测。")
    if result.market_summary:
        if lines:
            lines.append("")
        lines.append(
            result.market_summary.replace(
                "## 本地 DuckDB 最新市场总览",
                "## 市场概览",
                1,
            )
        )

    visible_sections = (
        ("结论", 8),
        ("证据链", 40),
        ("分歧反证", 12),
        ("后续验证点", 12),
        ("交易含义", 6),
        ("引用来源", 12),
    )
    rendered_sections = False
    for title, limit in visible_sections:
        if result.market_summary and title == "证据链":
            continue
        items = result.sections.get(title, [])
        if not items:
            continue
        if lines:
            lines.append("")
        lines.append(f"## {title}")
        for item in items[:limit]:
            if item.startswith(SUBHEAD):
                lines.append(f"### {item[len(SUBHEAD):]}")
            else:
                lines.append(f"- {item}")
        rendered_sections = True

    if rendered_sections or result.market_summary:
        if lines:
            lines.append("")
        lines.append(
            "自然语言综合暂时不可用；以上为确定性检索结果，"
            "缺失项未作猜测。完整来源和结构化产物保留在“运行详情”中。"
        )
    else:
        if lines:
            lines.append("")
        lines.append(
            "本轮检索已完成，但没有形成可展示的确定性结果。"
            "自然语言综合暂时不可用，请在“运行详情”中核对数据缺口后重试。"
        )
    return "\n".join(lines).rstrip() + "\n"

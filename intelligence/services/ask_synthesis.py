"""ask 的合成层：AnswerSpec 构建、LLM 合成、grounded presenter 提升（从 ask.py 拆出，行为不变）。"""

from __future__ import annotations


import os
import random
import re
import time
from dataclasses import replace
from pathlib import Path

from intelligence import userspace
from intelligence.services import (
    answer_model,
    evidence_providers,
    evidence_registry,
    experience_cards,
    forecast_preflight,
    llm_refine,
    perspective_lab,
    scenario_tree,
)
from intelligence.services.answer_quality import (
    AnswerQualityContext,
)
from intelligence.services.answer_orchestrator import (
    QUESTION_FINANCIAL_ANALYSIS,
    QUESTION_MARKET_FORECAST,
    QUESTION_NEWS_IMPACT,
    QUESTION_STOCK_DEEP_DIVE,
    QUESTION_THEME_ANALYSIS,
    QUESTION_VALUATION,
    QuestionPlan,
)
from intelligence.services.ask_types import (
    REPO_ROOT,
    AskOptions,
    AskResult,
    Citation,
    PreparedAnswer,
    _stage_timeout,
    _synthesis_timeout,
    _llm_deadline,
)


# few-shot 锚：高分样板目录。文件名前缀按问题类型路由（deep-dive-* / forecast-*），
# 最多注入 EXEMPLAR_MAX_FILES 篇、总长度上限 EXEMPLAR_MAX_CHARS（超量会稀释证据注意力）。
EXEMPLAR_DIR = REPO_ROOT / "skills" / "stock-deep-dive" / "exemplars"
EXEMPLAR_MAX_FILES = 3
EXEMPLAR_MAX_CHARS = 6000
# 主观分析段落的合成温度（0.5~0.7 放开文风）；claim 绑定修订轮仍固定 0.0。
def _subjective_temperature() -> float:
    raw = os.environ.get("ASK_SUBJECTIVE_TEMPERATURE", "0.6")
    try:
        value = float(raw)
    except ValueError:
        return 0.6
    return min(max(value, 0.0), 1.0)


def _section_titles(text: str) -> list[str]:
    return [
        line.strip().lstrip("#").strip()
        for line in text.splitlines()
        if line.lstrip().startswith("#")
    ]


def _section_bodies(text: str) -> dict[str, str]:
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            current = line.strip().lstrip("#").strip()
            bodies.setdefault(current, [])
            continue
        if current is not None:
            bodies[current].append(line)
    return {title: "\n".join(lines).strip() for title, lines in bodies.items()}


_EXEMPLAR_PREFIX_BY_TYPE = {
    QUESTION_STOCK_DEEP_DIVE: "deep-dive-",
    QUESTION_MARKET_FORECAST: "forecast-",
    QUESTION_VALUATION: "valuation-",
}


def _exemplar_guidance_for(
    question_type: str,
    exemplar_dir: Path = EXEMPLAR_DIR,
    rng: random.Random | None = None,
) -> str:
    prefix = _EXEMPLAR_PREFIX_BY_TYPE.get(question_type)
    if prefix is None or not exemplar_dir.is_dir():
        return ""
    candidates = sorted(exemplar_dir.glob(f"{prefix}*.md"))
    # 文风放开：同类型多篇结构不同的范文随机选一，避免每次都用同一套行文结构。
    if len(candidates) > 1:
        candidates = [(rng or random).choice(candidates)]
    parts: list[str] = []
    budget = EXEMPLAR_MAX_CHARS
    for path in candidates[:EXEMPLAR_MAX_FILES]:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not text:
            continue
        snippet = text[:budget]
        parts.append(f"### 样板：{path.stem}\n{snippet}")
        budget -= len(snippet)
        if budget <= 0:
            break
    return "\n\n".join(parts)


# 数据块 claim 默认状态覆盖（P0 修复）：VERIFIED 不能靠"没出现坏词"铸造。
# W7 资讯只是"标题存在"的存在性证据，标题内容未证实；M/V 是用户先验与历史裁决
# 快照，不是当期市场事实；D8 历史类比是推演。其余 DuckDB/东财确定性取数块保持
# VERIFIED（数据本身可回查）。
_DATA_BLOCK_STATUS_OVERRIDES = {
    "W7": answer_model.ClaimStatus.CANDIDATE,
    "M": answer_model.ClaimStatus.CANDIDATE,
    "V": answer_model.ClaimStatus.CANDIDATE,
    "D8": answer_model.ClaimStatus.INFERRED,
}


def _claims_from_data_block(
    block: str,
    tag: str,
    label: str,
    theme: str,
) -> list[answer_model.Claim]:
    claims: list[answer_model.Claim] = []
    for index, raw in enumerate(block.splitlines(), start=1):
        line = raw.strip().lstrip("-").strip()
        if not line or line.startswith("口径"):
            continue
        if line.startswith("#"):
            status = answer_model.ClaimStatus.INFERRED
        elif any(
            term in line
            for term in (
                "缺失",
                "未取得",
                "未取到",
                "不可用",
                "无匹配",
                "未识别",
            )
        ):
            status = answer_model.ClaimStatus.MISSING
        elif tag in {"D2", "D3"} or any(
            term in line
            for term in ("必须", "需要补", "使用要求", "回答时", "继续查")
        ):
            status = answer_model.ClaimStatus.INFERRED
        else:
            status = _DATA_BLOCK_STATUS_OVERRIDES.get(
                tag, answer_model.ClaimStatus.VERIFIED
            )
        claims.append(
            answer_model.make_claim(
                claim_id=f"data:{tag}:{index}",
                text=f"{label}：{line}",
                claim_type="market_data",
                theme=theme,
                status=status,
                evidence_tier="market_data",
                evidence_ids=(tag,),
            )
        )
    return claims


_company_name_from_official_title = evidence_providers._company_name_from_official_title


def _build_answer_spec_for_result(
    *,
    result: AskResult,
    research_spec: answer_model.ThemeResearchSpec,
    conclusion_lines: list[str],
    structured_claims: list[answer_model.Claim],
    company_candidates: list[answer_model.CompanyCandidate],
    counter_lines: list[str],
    gap_lines: list[str],
    trigger_lines: list[str],
    follow_ups: list[str],
    citations: list[Citation],
) -> answer_model.AnswerSpec:
    claims = _dedupe_structured_claims(structured_claims)
    company_table = answer_model.build_company_assessments(
        company_candidates,
        claims,
    )
    market_claims = [
        claim
        for claim in claims
        if claim.claim_type in {"market_signal", "market_context"}
        and claim.status == answer_model.ClaimStatus.VERIFIED
    ]
    signal_labels: list[str] = []
    for claim in market_claims:
        rendered = answer_model.humanize(claim.text)
        if claim.claim_type != "market_signal":
            continue
        label = rendered.split("：", 1)[0].strip()
        if label and label not in signal_labels:
            signal_labels.append(label)
    question_type = (
        result.question_plan.question_type
        if result.question_plan is not None
        else ""
    )
    is_theme_research = question_type in {
        QUESTION_THEME_ANALYSIS,
        QUESTION_NEWS_IMPACT,
        QUESTION_STOCK_DEEP_DIVE,
    }
    if is_theme_research:
        summary: list[answer_model.Claim] = [
            answer_model.make_claim(
                claim_id="summary:definition",
                text=(
                    f"{research_spec.theme}的研究范围是："
                    f"{research_spec.definition.rstrip('。')}。"
                ),
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.INFERRED,
                evidence_tier="research_ontology",
                evidence_ids=("ONTOLOGY",),
            )
        ]
    elif question_type == QUESTION_VALUATION:
        subject = (
            result.question_plan.query_envelope.subject
            if result.question_plan is not None
            else None
        )
        summary = [
            answer_model.make_claim(
                claim_id="summary:valuation-gap",
                text=(
                    f"{subject or result.query}本轮尚未取得足够的当前估值、财务和"
                    "可比公司数据，不能可靠判断估值高低。"
                ),
                claim_type="summary",
                theme=subject or research_spec.theme,
                status=answer_model.ClaimStatus.MISSING,
            )
        ]
    else:
        summary = [
            answer_model.make_claim(
                claim_id=f"summary:base:{index}",
                text=line,
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.INFERRED,
                evidence_tier="base_finance",
            )
            for index, line in enumerate(dict.fromkeys(conclusion_lines[:3]), start=1)
            if line
        ]
    if is_theme_research and signal_labels:
        market_evidence_ids = tuple(
            dict.fromkeys(
                evidence_id
                for claim in market_claims
                for evidence_id in claim.evidence_ids
            )
        )
        summary.append(
            answer_model.make_claim(
                claim_id="summary:market",
                text=(
                    f"盘面上已经出现{'、'.join(signal_labels[:3])}，"
                    "说明市场关注度有所升温；但这些信号只能反映资金行为，"
                    "不能替代公司公告、客户、订单或收入证据。"
                ),
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.CANDIDATE,
                evidence_tier="market_data",
                evidence_ids=market_evidence_ids,
            )
        )
    elif is_theme_research:
        summary.append(
            answer_model.make_claim(
                claim_id="summary:market-gap",
                text=(
                    "盘面数据本轮不足，暂时无法判断资金是否已经形成持续共识。"
                ),
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.MISSING,
            )
        )
    verified_company_claims = [
        claim
        for claim in claims
        if claim.company and claim.status == answer_model.ClaimStatus.VERIFIED
    ]
    if is_theme_research and verified_company_claims:
        verified_companies = list(
            dict.fromkeys(
                claim.company for claim in verified_company_claims if claim.company
            )
        )
        summary.append(
            answer_model.make_claim(
                claim_id="summary:company",
                text=(
                    f"公司层面已找到可回查的公开材料，覆盖"
                    f"{'、'.join(verified_companies[:3])}；是否属于核心受益者，"
                    "仍需结合业务直接性和收入贡献判断。"
                ),
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.VERIFIED,
                evidence_tier="company_evidence",
                evidence_ids=tuple(
                    dict.fromkeys(
                        evidence_id
                        for claim in verified_company_claims
                        for evidence_id in claim.evidence_ids
                    )
                ),
            )
        )
    elif is_theme_research:
        summary.append(
            answer_model.make_claim(
                claim_id="summary:company-gap",
                text=(
                    "公司层面尚未形成可回查的公告、年报、官网产品或客户订单证据，"
                    "因此不能把任何公司列为核心受益者。"
                ),
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.MISSING,
            )
        )
    user_gaps = [
        line
        for line in gap_lines
        if line
        and not line.startswith(
            (
                "阶段判断",
                "市场结构推演路径",
                "反方审稿",
                "市场结构状态机",
                "证据分层审计",
            )
        )
        and "Temporal Facts" not in line
    ]
    gaps = tuple(
        answer_model.make_claim(
            claim_id=f"gap:{index}",
            text=line,
            claim_type="evidence_gap",
            theme=research_spec.theme,
            status=answer_model.ClaimStatus.MISSING,
        )
        for index, line in enumerate(dict.fromkeys(user_gaps), start=1)
    )
    counter_evidence = tuple(
        answer_model.make_claim(
            claim_id=f"counter:{index}",
            text=line,
            claim_type="counter_evidence",
            theme=research_spec.theme,
            status=answer_model.ClaimStatus.CONFLICT,
        )
        for index, line in enumerate(dict.fromkeys(counter_lines), start=1)
    )
    triggers: list[answer_model.Claim] = []
    for index, line in enumerate(dict.fromkeys(trigger_lines), start=1):
        matching_claim = next(
            (claim for claim in claims if answer_model.humanize(claim.text) == answer_model.humanize(line)),
            None,
        )
        triggers.append(
            answer_model.make_claim(
                claim_id=f"trigger:{index}",
                text=line,
                claim_type="trigger",
                theme=research_spec.theme,
                status=(
                    matching_claim.status
                    if matching_claim is not None
                    else answer_model.ClaimStatus.INFERRED
                ),
                evidence_tier=(
                    matching_claim.evidence_tier
                    if matching_claim is not None
                    else "research_ontology"
                ),
                evidence_ids=(
                    matching_claim.evidence_ids
                    if matching_claim is not None
                    else ("ONTOLOGY",)
                ),
            )
        )
    evidence_tiers: dict[str, str] = {}
    for claim in claims:
        for evidence_id in claim.evidence_ids:
            current = evidence_tiers.get(evidence_id, "")
            if not current or answer_model.is_hard_evidence_tier(
                claim.evidence_tier,
                (evidence_id,),
            ):
                evidence_tiers[evidence_id] = claim.evidence_tier
    sources = [
        answer_model.EvidenceRef(
            evidence_id=citation.tag,
            source=citation.source,
            detail=citation.detail,
            tier=evidence_tiers.get(citation.tag, ""),
            # 来源溯源传播（P2）：Citation 携带的索引新鲜度/内容 hash/来源
            # 版本此前在转 EvidenceRef 时丢失（Codex 点名的具体断点）。
            freshness=citation.index_freshness or "unknown",
            content_hash=citation.content_hash,
            source_revision=citation.index_source_revision,
        )
        for citation in citations
    ]
    if is_theme_research:
        sources.append(
            answer_model.EvidenceRef(
                evidence_id="ONTOLOGY",
                source=f"题材研究配置 · {research_spec.theme}",
                detail="仅用于定义、产业链和核验协议，不作为公司级事实。",
                tier="research_ontology",
            )
        )
    for index, item in enumerate(result.l3_evidence.items, start=1):
        sources.append(
            answer_model.EvidenceRef(
                evidence_id=f"L{index}",
                source=item.citation or item.source_type,
                detail=item.title,
                tier="L3",
            )
        )
    notices: list[str] = []
    if result.data_notice:
        notices.append(result.data_notice)
    if re.search(r"T\+1|下一交易日|明天", result.query, re.IGNORECASE):
        notices.append(
            f"下一交易日为 {result.next_trade_date}（按交易日历确认，不按自然日顺延）。"
            if result.next_trade_date
            else "下一交易日（日期待交易日历确认），不得按自然日猜测。"
        )
    requires_company_evidence = (
        result.question_plan is not None
        and result.question_plan.question_type
        in {
            QUESTION_THEME_ANALYSIS,
            QUESTION_NEWS_IMPACT,
            QUESTION_STOCK_DEEP_DIVE,
            QUESTION_FINANCIAL_ANALYSIS,
            QUESTION_VALUATION,
        }
    )
    has_verified_company_claim = any(
        claim.company and claim.status == answer_model.ClaimStatus.VERIFIED
        for claim in claims
    )
    if requires_company_evidence and not has_verified_company_claim:
        notices.append("本轮未形成可验证的公司级来源；公司判断均按待验证展示。")
    if any(
        term in warning.lower()
        for warning in result.warnings
        for term in ("失败", "不可用", "timeout", "degraded")
    ):
        notices.append("部分资料源本轮不可用，未用于结论。")
    actions = list(research_spec.verification_actions) if is_theme_research else []
    actions.extend(
        line for line in conclusion_lines if line.startswith("观点有效期")
    )
    actions.extend(
        line
        for line in follow_ups
        if line
        and "市场结构推演路径" not in line
        and not re.match(r"^\[[^\]]+\]", line)
    )
    # 候选证据通道：agent 补检索 / Web 兜底 / 模块召回 / wiki 语义召回等 CANDIDATE
    # claim 中，未随公司表进入 registry 的部分。上限 24 条防 prompt 膨胀。
    company_claim_ids = {
        claim.claim_id
        for assessment in company_table
        for claim in assessment.claims
    }
    candidate_facts = tuple(
        claim
        for claim in claims
        if claim.status == answer_model.ClaimStatus.CANDIDATE
        and claim.claim_id not in company_claim_ids
    )[:24]
    spec = answer_model.AnswerSpec(
        research_spec=research_spec,
        summary=tuple(summary),
        verified_facts=tuple(
            claim for claim in claims if claim.status == answer_model.ClaimStatus.VERIFIED
        ),
        company_table=company_table,
        counter_evidence=counter_evidence,
        gaps=gaps,
        triggers=tuple(triggers),
        candidate_facts=candidate_facts,
        next_actions=tuple(dict.fromkeys(actions)),
        sources=tuple(dict.fromkeys(sources)),
        system_notices=tuple(dict.fromkeys(notices)),
        prompt_constraints=tuple(
            item
            for item in (
                result.question_plan.to_prompt_block(compact=True)
                if result.question_plan is not None
                else "",
                (
                    "## 交易日历约束\n"
                    f"- 数据交易日：{result.trade_date or '未确认'}\n"
                    f"- 下一交易日：{result.next_trade_date or '日期待交易日历确认'}"
                ),
                (
                    forecast_preflight.render_preflight_prompt(
                        result.forecast_preflight
                    )
                    if result.forecast_preflight is not None
                    else ""
                ),
                (
                    result.l3_evidence.to_prompt_block()
                    if result.l3_evidence is not None
                    and (
                        result.l3_evidence.items
                        or result.l3_evidence.gaps
                        or result.l3_evidence.warnings
                    )
                    else ""
                ),
            )
            if item
        ),
        presentation_kind=(
            "theme_research"
            if result.question_plan is not None
            and result.question_plan.question_type
            in {
                QUESTION_THEME_ANALYSIS,
                QUESTION_NEWS_IMPACT,
                QUESTION_STOCK_DEEP_DIVE,
            }
            else "base_finance"
        ),
        presentation_title=(
            {
                QUESTION_MARKET_FORECAST: "市场判断",
                QUESTION_VALUATION: "估值判断",
            }.get(
                result.question_plan.question_type,
                "金融问题裁决",
            )
            if result.question_plan is not None
            else "金融问题裁决"
        ),
    )
    return answer_model.finalize_answer_spec(spec)


def _presentable_lines(*blocks: str) -> list[str]:
    lines: list[str] = []
    for block in blocks:
        for raw in str(block or "").splitlines():
            line = raw.strip().lstrip("-").strip()
            if (
                not line
                or line.startswith("#")
                or line.startswith("|")
                or set(line) <= {"-", "|", ":", " "}
            ):
                continue
            lines.append(line)
    return list(dict.fromkeys(lines))


def _build_base_answer_spec_from_sections(
    result: AskResult,
    *,
    theme: str,
    evidence_blocks: tuple[str, ...] = (),
    direct_lines: tuple[str, ...] = (),
    risk_lines: tuple[str, ...] = (),
    action_lines: tuple[str, ...] = (),
    presentation_kind: str = "base_finance",
) -> answer_model.AnswerSpec:
    citations = [
        citation for citation in result.citations if citation.tag not in {"M", "V"}
    ]
    sources = [
        answer_model.EvidenceRef(
            evidence_id=citation.tag,
            source=citation.source,
            detail=citation.detail,
            freshness=citation.index_freshness or "unknown",
            content_hash=citation.content_hash,
            source_revision=citation.index_source_revision,
        )
        for citation in citations
    ]
    evidence_ids = tuple(dict.fromkeys(citation.tag for citation in citations))
    if evidence_blocks:
        sources.append(
            answer_model.EvidenceRef(
                evidence_id="BASE",
                source="本轮可核验资料",
                detail="用于统一答案裁决与展示。",
            )
        )
        evidence_ids = (*evidence_ids, "BASE")

    conclusions = list(direct_lines) or _presentable_lines(
        "\n".join(result.sections.get("结论", []))
    )
    if not conclusions:
        conclusions = ["当前证据不足，暂时不能形成可靠定性。"]
    summary_status = (
        answer_model.ClaimStatus.INFERRED
        if evidence_ids
        else answer_model.ClaimStatus.MISSING
    )
    summary = tuple(
        answer_model.make_claim(
            claim_id=f"base:summary:{index}",
            text=line,
            claim_type="summary",
            theme=theme,
            status=summary_status,
            evidence_tier="base_finance",
            evidence_ids=evidence_ids,
        )
        for index, line in enumerate(conclusions[:3], start=1)
    )

    evidence_lines = _presentable_lines(
        "\n".join(result.sections.get("证据链", [])),
        *evidence_blocks,
    )
    verified_facts = tuple(
        answer_model.make_claim(
            claim_id=f"base:fact:{index}",
            text=line,
            claim_type="supporting_fact",
            theme=theme,
            status=answer_model.ClaimStatus.VERIFIED,
            evidence_tier="base_finance",
            evidence_ids=evidence_ids,
        )
        for index, line in enumerate(evidence_lines[:8], start=1)
        if evidence_ids
    )

    risks = list(risk_lines) or _presentable_lines(
        "\n".join(result.sections.get("分歧反证", []))
    )
    if not risks:
        risks = ["缺少足以独立复核结论的反方资料。"]
    gaps = tuple(
        answer_model.make_claim(
            claim_id=f"base:gap:{index}",
            text=line,
            claim_type="evidence_gap",
            theme=theme,
            status=answer_model.ClaimStatus.MISSING,
        )
        for index, line in enumerate(risks[:6], start=1)
    )

    implications = _presentable_lines(
        "\n".join(result.sections.get("交易含义", []))
    )
    boundary_lines = implications or [
        "若关键证据或市场条件出现反向变化，当前判断应立即降级。"
    ]
    triggers = tuple(
        answer_model.make_claim(
            claim_id=f"base:trigger:{index}",
            text=line,
            claim_type="condition_boundary",
            theme=theme,
            status=answer_model.ClaimStatus.INFERRED,
            evidence_tier="base_finance",
            evidence_ids=evidence_ids,
        )
        for index, line in enumerate(boundary_lines[:3], start=1)
    )

    actions = list(action_lines) or _presentable_lines(
        "\n".join(result.sections.get("后续验证点", []))
    )
    if not actions:
        actions = ["补齐核心数据后重新裁决。"]
    spec = answer_model.AnswerSpec(
        research_spec=answer_model.ThemeResearchSpec(
            theme=theme,
            pack_id="base_finance_mode",
            definition="常驻金融问答基座",
            chain_stages=(),
            company_scope="",
            as_of=result.trade_date,
            evidence_requirements=(),
            counter_evidence_requirements=(),
            trigger_conditions=(),
            verification_actions=tuple(actions),
            focus_entities=(),
            requested_sections=(
                "direct_assessment",
                "strongest_evidence",
                "main_risk",
                "condition_boundary",
                "next_verification",
            ),
        ),
        summary=summary,
        verified_facts=verified_facts,
        company_table=(),
        counter_evidence=(),
        gaps=gaps,
        triggers=triggers,
        next_actions=tuple(actions),
        sources=tuple(dict.fromkeys(sources)),
        system_notices=tuple(
            item for item in (result.data_notice,) if item
        ),
        prompt_constraints=tuple(
            item
            for item in (
                (
                    result.question_plan.to_prompt_block(compact=True)
                    if result.question_plan is not None
                    else ""
                ),
                *evidence_blocks,
            )
            if item
        ),
        presentation_kind=presentation_kind,
        presentation_title=theme,
    )
    return answer_model.finalize_answer_spec(spec)


def _dedupe_structured_claims(
    claims: list[answer_model.Claim],
) -> list[answer_model.Claim]:
    seen: set[tuple[str, str | None, answer_model.ClaimStatus]] = set()
    result: list[answer_model.Claim] = []
    for claim in claims:
        key = (answer_model.humanize(claim.text), claim.company, claim.status)
        if key in seen:
            continue
        seen.add(key)
        result.append(claim)
    return result


def _prepare_answer_spec_synthesis(
    *,
    options: AskOptions,
    result: AskResult,
    question_plan: QuestionPlan,
    theme: str,
    citations: list[Citation],
    quality_context: AnswerQualityContext,
    is_market_review: bool,
) -> list[dict]:
    if result.answer_spec is None:
        return []
    citation_legend = "\n".join(
        f"[{citation.tag}] {citation.source}"
        + (f" — {citation.detail}" if citation.detail else "")
        for citation in citations
    )
    us = userspace.user_space(options.user)
    perspective_context = perspective_lab.build_runtime_context(
        us,
        mode=options.perspective_mode,
        perspective_ids=options.perspective_ids,
        query=options.query,
    )
    experience_guidance = ""
    if evidence_registry.provider_enabled(options, "M"):
        cards, card_warn = experience_cards.load_cards(
            us.experience_cards_path,
            window=options.experience_cards_window,
        )
        if card_warn:
            result.warnings.append(card_warn)
        selected_cards = experience_cards.select_relevant_cards(
            cards,
            options.query,
        )
        experience_guidance = experience_cards.render_for_prompt(
            selected_cards
        )
    exemplar_guidance = _exemplar_guidance_for(question_plan.question_type)
    if options.include_scenario_guidance:
        scenario_guidance = scenario_tree.scenario_guidance_for_query(
            options.query,
            question_plan.question_type,
        )
        if scenario_guidance:
            experience_guidance = (
                f"{experience_guidance}\n\n{scenario_guidance}"
                if experience_guidance
                else scenario_guidance
            )
    messages = llm_refine.build_synthesis_messages(
        options.query,
        theme,
        result.answer_spec.to_prompt_block(),
        citation_legend=citation_legend,
        quality_context=None if is_market_review else quality_context,
        experience_guidance=experience_guidance,
        exemplar_guidance=exemplar_guidance,
    )
    messages[0]["content"] = (
        f"{messages[0]['content']}\n\n## 本轮视角约束\n"
        f"{perspective_context.prompt}"
    )
    if options.conversation_context:
        messages.insert(
            1,
            {
                "role": "system",
                "content": (
                    "以下会话上下文仅用于理解指代和用户意图，不是本轮检索证据；"
                    "事实判断仍须引用当前轮证据：\n"
                    f"{options.conversation_context}"
                ),
            },
        )
    return messages


def synthesize_prepared_answer(prepared: PreparedAnswer) -> AskResult:
    options = prepared.options
    result = prepared.result
    messages = result.prepared_synthesis_messages
    if result.answer_spec is None or not messages:
        return result
    if promote_grounded_answer(options, result):
        return result
    if (
        result.prepared_synthesis_is_market_review
        and options.grounded_presenter
        and result.grounded_composer_shadow is not None
    ):
        # 市场复盘的可信自然语言出口只有 Grounded Composer。它不可用或未过
        # 门禁时保留结构化 AnswerSpec 供上层确定性渲染，不再启动无 claim/
        # EvidenceAtom 绑定的旧散文合成，否则等于在安全链失败后绕回软出口。
        return result
    started = time.monotonic()
    deadline = _llm_deadline(options)
    chunks: list[str] = []
    provider_connect_ms: int | None = None
    first_token_ms: int | None = None
    last_token_ms: int | None = None
    stream_elapsed_ms: int | None = None
    quality_gate_ms: int | None = None
    provider_finish_reason: str | None = None
    provider = llm_refine.detect_provider(options.llm_model)

    def capture_connected() -> None:
        nonlocal provider_connect_ms
        if provider_connect_ms is None:
            provider_connect_ms = max(
                0,
                round((time.monotonic() - started) * 1000),
            )

    def capture(delta: str) -> None:
        nonlocal first_token_ms, last_token_ms
        if options.stream_cancel_check is not None and options.stream_cancel_check():
            raise llm_refine.LLMStreamCancelled()
        elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
        if first_token_ms is None:
            first_token_ms = elapsed_ms
        last_token_ms = elapsed_ms
        chunks.append(delta)

    def capture_finish_reason(finish_reason: str | None) -> None:
        nonlocal provider_finish_reason
        if finish_reason in {
            "stop",
            "length",
            "content_filter",
            "tool_calls",
            "function_call",
        }:
            provider_finish_reason = finish_reason

    def telemetry(
        *,
        composed: llm_refine.SynthesisResult | None,
        fallback_reason: str | None,
    ) -> dict[str, object]:
        elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
        remaining_ms = max(0, round(deadline.remaining() * 1000))
        text = composed.answer if composed is not None else "".join(chunks)
        safe_finish_reason = (
            composed.finish_reason
            if composed is not None
            and composed.finish_reason
            in {"stop", "length", "content_filter", "tool_calls", "function_call"}
            else provider_finish_reason
        )
        return {
            "provider": (
                composed.provider
                if composed is not None
                else provider.name if provider is not None else None
            ),
            "model": (
                composed.model
                if composed is not None
                else provider.model if provider is not None else options.llm_model
            ),
            "deadline_ms": round(
                (
                    options.deadline.remaining()
                    if options.deadline is not None
                    else options.llm_timeout
                )
                * 1000
            ),
            "remaining_budget_ms": remaining_ms,
            "provider_connect_ms": provider_connect_ms,
            "first_token_ms": first_token_ms,
            "last_token_ms": last_token_ms,
            "stream_elapsed_ms": stream_elapsed_ms,
            "quality_gate_ms": quality_gate_ms,
            "total_synthesis_ms": elapsed_ms,
            "elapsed_ms": elapsed_ms,
            "chunk_count": len(chunks),
            "output_chars": len(text),
            "finish_reason": safe_finish_reason,
            "thinking_disabled": llm_refine.synthesis_thinking_disabled(),
            "fallback_reason": fallback_reason,
        }

    synthesis_temperature = _subjective_temperature()
    if result.prepared_synthesis_is_market_review:
        composed, reason = llm_refine.synthesize_messages(
            messages,
            model_override=options.llm_model,
            timeout=_synthesis_timeout(options, options.llm_timeout),
            temperature=synthesis_temperature,
            deadline=deadline,
        )
    else:
        composed, reason = llm_refine.synthesize_messages_stream(
            messages,
            on_delta=capture,
            on_connected=capture_connected,
            on_finish_reason=capture_finish_reason,
            is_cancelled=options.stream_cancel_check,
            model_override=options.llm_model,
            timeout=_synthesis_timeout(options, options.llm_timeout),
            temperature=synthesis_temperature,
            deadline=deadline,
        )
    stream_elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
    if composed is None:
        result.warnings.append(reason)
        result.llm_fallback_reason = _stable_llm_fallback_reason(reason)
        result.llm_stream_telemetry = telemetry(
            composed=None,
            fallback_reason=result.llm_fallback_reason,
        )
        return result
    if composed.finish_reason is not None and composed.finish_reason != "stop":
        reason = (
            "LLM 合成响应被截断，已降级为模板"
            if composed.finish_reason == "length"
            else "LLM 合成未正常停止，已降级为模板"
        )
        result.warnings.append(reason)
        result.llm_fallback_reason = _stable_llm_fallback_reason(reason)
        result.llm_stream_telemetry = telemetry(
            composed=composed,
            fallback_reason=result.llm_fallback_reason,
        )
        return result
    result.llm_fallback_reason = composed.fallback_reason
    result.llm_stream_telemetry = telemetry(
        composed=composed,
        fallback_reason=result.llm_fallback_reason,
    )
    proposed_synthesis = composed.answer
    initial_synthesis = composed.answer
    accepted_composition = composed
    quality_gate_started = time.monotonic()
    gate_issues = answer_model.validate_llm_answer(
        proposed_synthesis,
        result.answer_spec,
    )
    blocking_issues = [
        issue for issue in gate_issues if issue.severity == "error"
    ]
    # claim-binding 修订轮只适用于 registry 契约：散文契约（市场复盘）没有
    # registry 可复制，泄漏即直接退稿，不浪费一次错误契约的修订调用。
    if (
        blocking_issues
        and deadline.remaining() > 0
        and not result.prepared_synthesis_is_market_review
    ):
        correction_started = time.monotonic()
        correction, correction_reason = llm_refine.synthesize_messages(
            [
                *messages,
                {
                    "role": "user",
                    "content": llm_refine.claim_binding_revision_user_content(
                        [issue.message for issue in blocking_issues],
                        answer_model.structured_claim_registry_block(
                            result.answer_spec
                        ),
                    ),
                },
            ],
            model_override=options.llm_model,
            timeout=_synthesis_timeout(options, options.llm_timeout),
            deadline=deadline,
            temperature=0.0,
        )
        result.llm_stream_telemetry["claim_binding_revision_ms"] = round(
            (time.monotonic() - correction_started) * 1000
        )
        result.llm_stream_telemetry["claim_binding_revision_reason"] = (
            correction_reason or None
        )
        if correction is not None:
            corrected_synthesis = correction.answer
            corrected_issues = answer_model.validate_llm_answer(
                corrected_synthesis,
                result.answer_spec,
            )
            corrected_blocking = [
                issue
                for issue in corrected_issues
                if issue.severity == "error"
            ]
            if not corrected_blocking:
                proposed_synthesis = corrected_synthesis
                accepted_composition = correction
                blocking_issues = []
            else:
                blocking_issues = corrected_blocking
    structured_claims, unbound_claim_lines = (
        answer_model.parse_structured_claims(proposed_synthesis)
    )
    quality_gate_ms = max(
        0,
        round((time.monotonic() - quality_gate_started) * 1000),
    )
    result.llm_stream_telemetry["quality_gate_ms"] = quality_gate_ms
    result.llm_stream_telemetry["total_synthesis_ms"] = max(
        0,
        round((time.monotonic() - started) * 1000),
    )
    result.llm_stream_telemetry["elapsed_ms"] = result.llm_stream_telemetry[
        "total_synthesis_ms"
    ]
    result.llm_stream_telemetry["structured_claim_count"] = len(
        structured_claims
    )
    result.llm_stream_telemetry["unbound_claim_line_count"] = len(
        unbound_claim_lines
    )
    if blocking_issues:
        result.warnings.extend(
            f"LLM 输出被 AnswerSpec 门禁拒绝：{issue.message}"
            for issue in blocking_issues
        )
        result.llm_fallback_reason = "quality_gate_rejected"
        result.llm_stream_telemetry["fallback_reason"] = result.llm_fallback_reason
        return result
    presented_synthesis = answer_model.present_llm_answer(
        proposed_synthesis,
        result.answer_spec,
    )
    # sections 遥测：降级/修订从“静默”变“可观测”。kept/dropped 对比合成稿与
    # 展示稿的小节集合；revised 统计修订轮改动过正文的小节数。
    proposed_titles = _section_titles(proposed_synthesis)
    presented_titles = set(_section_titles(presented_synthesis))
    initial_bodies = _section_bodies(initial_synthesis)
    final_bodies = _section_bodies(proposed_synthesis)
    result.llm_stream_telemetry["sections_kept"] = sum(
        1 for title in proposed_titles if title in presented_titles
    )
    result.llm_stream_telemetry["sections_dropped"] = sum(
        1 for title in proposed_titles if title not in presented_titles
    )
    result.llm_stream_telemetry["sections_revised"] = (
        sum(
            1
            for title, body in final_bodies.items()
            if initial_bodies.get(title) != body
        )
        if proposed_synthesis is not initial_synthesis
        else 0
    )
    result.synthesis = (
        f"{result.data_notice}\n\n{presented_synthesis}"
        if result.data_notice and not result.prepared_synthesis_is_market_review
        else presented_synthesis
    )
    result.llm_provider = accepted_composition.provider
    result.synthesis_messages = [
        *messages,
        {"role": "assistant", "content": result.synthesis},
    ]
    if options.stream_text_delta is not None:
        options.stream_text_delta(result.synthesis)
    if reason:
        result.warnings.append(reason)
    return result


def _strip_empty_grounded_sections(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    for index, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            has_body = False
            for later in lines[index + 1 :]:
                if later.lstrip().startswith("#"):
                    break
                if later.strip():
                    has_body = True
                    break
            if not has_body:
                continue
        kept.append(line)
    collapsed: list[str] = []
    for line in kept:
        if not line.strip() and collapsed and not collapsed[-1].strip():
            continue
        collapsed.append(line)
    return "\n".join(collapsed).strip()


def _grounded_body_line_count(text: str) -> int:
    return sum(
        1
        for line in text.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and "非投资建议" not in line
    )


def promote_grounded_answer(
    options: AskOptions,
    result: AskResult,
) -> bool:
    """用 Grounded Composer 链路生成自然语言回答并接管 result.synthesis。

    daily-agent 契约受 ``daily_agent_grounded_presenter`` 控制（行为不变）；
    其余 compose 回答（包括 market_review）受 ``grounded_presenter`` 控制。
    开关启用后，门禁失败时使用确定性 verified brief 短答，
    不再绕回旧 LLM marker/Daily 模板出口。
    """
    spec = result.answer_spec
    if spec is None or not isinstance(spec, answer_model.AnswerSpec):
        return False
    is_daily_agent = (
        spec.presentation_kind
        == answer_model.DAILY_AGENT_PRESENTATION_KIND
    )
    if is_daily_agent:
        if not options.daily_agent_grounded_presenter:
            return False
    elif not options.grounded_presenter:
        return False
    synthesize_shadow_grounded_answer(
        PreparedAnswer(
            options=replace(
                options,
                shadow_grounded_composer=True,
            ),
            result=result,
        ),
        repair_drop_invalid=True,
        token_budget_scale=3,
    )
    shadow = result.grounded_composer_shadow
    presented = (
        _strip_empty_grounded_sections(shadow.presented_answer)
        if shadow is not None and shadow.presented_answer
        else ""
    )
    if (
        shadow is None
        or shadow.status not in {"accepted", "repaired"}
        or _grounded_body_line_count(presented) < 2
    ):
        if shadow is not None:
            reason = shadow.failure_reason or (
                "insufficient_grounded_body"
                if shadow.status in {"accepted", "repaired"}
                else shadow.status
            )
            label = "研究雷达" if is_daily_agent else "Grounded Presenter"
            result.warnings.append(
                f"{label}自然语言合成未通过门禁或不可用"
                f"（{reason}），已降级为可核验短答。"
            )
        # 这里返回 True 是关键：阻止 synthesize_prepared_answer
        # 继续落入旧 marker 合成路径。长尾/daily 使用只展示
        # verified facts 的短答；专项 owner 保留自己的确定性
        # AnswerSpec renderer，避免在合成故障时丢掉其业务契约。
        if result.answer_spec.presentation_kind in {
            "generic_research",
            answer_model.DAILY_AGENT_PRESENTATION_KIND,
        }:
            fallback = answer_model.render_decision_brief_fallback(
                shadow.decision_brief if shadow is not None else None,
                result.answer_spec,
                verified_only=True,
            )
        else:
            fallback = answer_model.render_answer_spec(result.answer_spec)
        result.synthesis = (
            f"{result.data_notice}\n\n{fallback}"
            if result.data_notice
            else fallback
        )
        result.synthesis_messages = [
            *(result.prepared_synthesis_messages or []),
            {"role": "assistant", "content": result.synthesis},
        ]
        result.grounded_fallback_used = True
        if options.stream_text_delta is not None:
            options.stream_text_delta(result.synthesis)
        return True
    result.synthesis = (
        f"{result.data_notice}\n\n{presented}"
        if result.data_notice
        else presented
    )
    result.llm_provider = shadow.provider
    result.synthesis_messages = [
        *(result.prepared_synthesis_messages or []),
        {"role": "assistant", "content": result.synthesis},
    ]
    if options.stream_text_delta is not None:
        options.stream_text_delta(result.synthesis)
    return True


# 向后兼容别名：daily-agent 路径早于通用 Grounded Presenter 存在。
promote_daily_agent_grounded_answer = promote_grounded_answer


def _shadow_support_claims(
    answer_spec: answer_model.AnswerSpec,
) -> tuple[answer_model.Claim, ...]:
    return tuple(
        claim
        for claim in (*answer_spec.summary, *answer_spec.verified_facts)
        if claim.claim_id
        and claim.evidence_ids
        and claim.status is not answer_model.ClaimStatus.MISSING
    )


def _shadow_deadline(options: AskOptions) -> llm_refine.Deadline:
    """影子链截止时间 = min(自身超时, turn 根 Deadline)。

    P0 修复：此前 promote 路径把 shadow timeout 抬到 ≥240s 并新建 Deadline，
    完全无视 turn 级 ResearchDeadline——子流程可以突破根截止时间。规则收敛为
    child = min(parent, now + stage_slice)，任何子阶段不得晚于根。
    """
    deadline = llm_refine.Deadline.from_timeout(options.shadow_grounded_timeout)
    if options.deadline is not None:
        deadline = llm_refine.Deadline(
            min(deadline.expires_at, options.deadline.expires_at)
        )
    return deadline


def _shadow_phase_timeout(
    deadline: llm_refine.Deadline,
    configured: int,
    share: float,
) -> int:
    """给 brief/composer/judge 分配同一根 deadline 的有限时间片。"""

    remaining = max(0.0, deadline.remaining())
    if remaining <= 0:
        return 1
    return max(1, min(int(configured), int(max(1.0, remaining * share))))


def synthesize_shadow_grounded_answer(
    prepared: PreparedAnswer,
    *,
    repair_drop_invalid: bool = False,
    token_budget_scale: int = 1,
) -> AskResult:
    options = prepared.options
    result = prepared.result
    if (
        not options.shadow_grounded_composer
        or result.answer_spec is None
    ):
        return result
    started = time.monotonic()
    if not _shadow_support_claims(result.answer_spec):
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="ineligible_evidence",
                failure_reason="no_valid_support_claims",
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    deadline = _shadow_deadline(options)
    brief_timeout = _shadow_phase_timeout(
        deadline, options.shadow_grounded_timeout, 0.25
    )
    registry_block = answer_model.grounded_claim_registry_block(
        result.answer_spec,
        query=options.query,
        max_chars=12_000,
    )
    brief_result, brief_reason = llm_refine.synthesize_messages(
        llm_refine.build_decision_brief_messages(
            options.query,
            registry_block,
        ),
        model_override=options.llm_model,
        timeout=brief_timeout,
        deadline=deadline,
        temperature=0.0,
        max_tokens=1200 * token_budget_scale,
        max_chars=8000 * token_budget_scale,
    )
    if brief_result is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="brief_unavailable",
                failure_reason=brief_reason,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    decision_brief, brief_issues = answer_model.parse_decision_brief(
        brief_result.answer,
        result.answer_spec,
    )
    if decision_brief is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="brief_rejected",
                deterministic_issues=brief_issues,
                provider=brief_result.provider,
                model=brief_result.model,
                failure_reason="decision_brief_quality_gate_rejected",
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    composed, compose_reason = llm_refine.synthesize_messages(
        llm_refine.build_grounded_composer_messages(
            options.query,
            decision_brief.to_prompt_block(),
            registry_block,
        ),
        model_override=options.llm_model,
        timeout=_shadow_phase_timeout(
            deadline, options.shadow_grounded_timeout, 0.5
        ),
        deadline=deadline,
        temperature=0.2,
        max_tokens=2400 * token_budget_scale,
        max_chars=16000 * token_budget_scale,
    )
    if composed is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="composer_unavailable",
                decision_brief=decision_brief,
                provider=brief_result.provider,
                model=brief_result.model,
                failure_reason=compose_reason,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    raw_answer = composed.answer
    # composer 常把 atom id 串位写进 claim_ids，导致整句判无效、修复失败、好答案被丢。
    # atom id 唯一指向所属 claim，可确定还原；brief 侧早有同样的规范化。
    if result.answer_spec is not None:
        raw_answer = answer_model.canonicalize_grounded_claim_ids(
            raw_answer,
            result.answer_spec,
        )
    deterministic_issues = (
        answer_model.validate_grounded_composer_answer(
            raw_answer,
            result.answer_spec,
        )
    )
    candidate_answer = raw_answer
    repaired = False
    if any(
        issue.severity == "error" for issue in deterministic_issues
    ):
        deterministic_repair = (
            answer_model.repair_grounded_composer_answer(
                raw_answer,
                result.answer_spec,
                drop_invalid=repair_drop_invalid,
            )
        )
        if deterministic_repair is None:
            result.grounded_composer_shadow = (
                answer_model.GroundedComposerShadow(
                    status="deterministic_gate_rejected",
                    decision_brief=decision_brief,
                    raw_answer=raw_answer,
                    deterministic_issues=deterministic_issues,
                    provider=composed.provider,
                    model=composed.model,
                    failure_reason="deterministic_repair_failed",
                    elapsed_ms=round(
                        (time.monotonic() - started) * 1000
                    ),
                )
            )
            return result
        candidate_answer = deterministic_repair
        repaired = True
    sentences, _unbound = answer_model.parse_grounded_sentences(
        candidate_answer
    )
    # 语义审独立性：配置 LLM_JUDGE_* 时 judge 走独立 provider，
    # 降低与 composer 同模型的相关性失败；未配置回落主 provider。
    judge_override = llm_refine.judge_provider()
    judge_messages = llm_refine.build_grounding_judge_messages(
        options.query,
        candidate_answer,
        registry_block,
    )
    if judge_override is not None:
        with llm_refine.provider_override(judge_override):
            judged, judge_reason = llm_refine.synthesize_messages(
                judge_messages,
                timeout=_shadow_phase_timeout(
                    deadline, options.shadow_grounded_timeout, 0.35
                ),
                deadline=deadline,
                temperature=0.0,
                max_tokens=1200 * token_budget_scale,
                max_chars=8000 * token_budget_scale,
            )
    else:
        judged, judge_reason = llm_refine.synthesize_messages(
            judge_messages,
            model_override=options.llm_model,
            timeout=_shadow_phase_timeout(
                deadline, options.shadow_grounded_timeout, 0.35
            ),
            deadline=deadline,
            temperature=0.0,
            max_tokens=1200 * token_budget_scale,
            max_chars=8000 * token_budget_scale,
        )
    if judged is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="judge_unavailable",
                decision_brief=decision_brief,
                raw_answer=raw_answer,
                repaired_answer=(
                    candidate_answer if repaired else None
                ),
                deterministic_issues=deterministic_issues,
                provider=composed.provider,
                model=composed.model,
                failure_reason=judge_reason,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    judge_report = answer_model.parse_grounding_judge_report(
        judged.answer,
        sentence_count=len(sentences),
    )
    if judge_report is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="judge_rejected",
                decision_brief=decision_brief,
                raw_answer=raw_answer,
                repaired_answer=(
                    candidate_answer if repaired else None
                ),
                deterministic_issues=deterministic_issues,
                judge_raw=judged.answer,
                provider=composed.provider,
                model=composed.model,
                failure_reason="judge_output_invalid",
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    if not judge_report.passed:
        semantic_repair = answer_model.repair_grounded_composer_answer(
            candidate_answer,
            result.answer_spec,
            rejected_sentence_indexes=(
                judge_report.rejected_sentence_indexes
            ),
            drop_invalid=repair_drop_invalid,
        )
        if semantic_repair is None:
            result.grounded_composer_shadow = (
                answer_model.GroundedComposerShadow(
                    status="semantic_gate_rejected",
                    decision_brief=decision_brief,
                    raw_answer=raw_answer,
                    repaired_answer=(
                        candidate_answer if repaired else None
                    ),
                    deterministic_issues=deterministic_issues,
                    judge_report=judge_report,
                    provider=composed.provider,
                    model=composed.model,
                    failure_reason="semantic_repair_failed",
                    elapsed_ms=round(
                        (time.monotonic() - started) * 1000
                    ),
                )
            )
            return result
        candidate_answer = semantic_repair
        repaired = True
    # brief 点名了产业链映射而正文没写时，确定性补一节。必需输出不能依赖模型遵从：
    # 实测 composer 拿到含 12 家公司的 chain_mapping、系统提示词也明确要求逐个写出，
    # 它仍然一家都不提，于是 chain_mapping 判缺、整份 919 字答案被 fail-closed 丢弃。
    candidate_answer = answer_model.ensure_chain_mapping_section(
        candidate_answer,
        result.answer_spec,
        decision_brief,
    )
    result.grounded_composer_shadow = (
        answer_model.GroundedComposerShadow(
            status="repaired" if repaired else "accepted",
            decision_brief=decision_brief,
            raw_answer=raw_answer,
            repaired_answer=candidate_answer if repaired else None,
            presented_answer=(
                answer_model.present_grounded_composer_answer(
                    candidate_answer,
                    result.answer_spec,
                )
            ),
            deterministic_issues=deterministic_issues,
            judge_report=judge_report,
            provider=composed.provider,
            model=composed.model,
            elapsed_ms=round((time.monotonic() - started) * 1000),
        )
    )
    return result


def _stable_llm_fallback_reason(reason: str) -> str:
    normalized = str(reason or "").casefold()
    if "未配置" in normalized:
        return "provider_unavailable"
    if "截止时间" in normalized or "超时" in normalized:
        return "timeout"
    if "输出超长" in normalized or "too long" in normalized:
        return "output_too_long"
    if "截断" in normalized or "length" in normalized:
        return "truncated_response"
    if "未正常停止" in normalized or "stalled" in normalized:
        return "provider_stalled"
    if "http" in normalized:
        return "provider_http_error"
    if "空内容" in normalized:
        return "empty_response"
    return "provider_unavailable"

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
    SynthesisDiagnostic,
    SynthesisPhase,
    _synthesis_timeout,
    _llm_deadline,
)
from intelligence.services.task_fulfillment import answer_has_output_marker
from intelligence.services.research_policy import grounded_deep


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
    "D10": answer_model.ClaimStatus.INFERRED,
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


def _synthesis_claim_counts(result: AskResult) -> tuple[int, int]:
    spec = result.answer_spec
    if spec is None:
        return 0, 0
    claims: list[object] = []
    for field_name in ("summary", "verified_facts", "candidate_facts"):
        value = getattr(spec, field_name, ())
        if isinstance(value, (list, tuple)):
            claims.extend(value)
    bound = sum(bool(getattr(claim, "evidence_ids", ())) for claim in claims)
    return len(claims), bound


def _set_synthesis_diagnostic(
    result: AskResult,
    *,
    state: str,
    reason_code: str,
    detail: str,
) -> None:
    candidate_claim_count, bound_claim_count = _synthesis_claim_counts(result)
    shadow = result.grounded_composer_shadow
    result.synthesis_diagnostic = SynthesisDiagnostic(
        state=state,
        reason_code=str(reason_code or "unknown")[:80],
        detail=detail,
        prepared_message_count=len(result.prepared_synthesis_messages or ()),
        candidate_claim_count=candidate_claim_count,
        bound_claim_count=bound_claim_count,
        shadow_status=str(getattr(shadow, "status", "") or "")[:40],
        phases=tuple(result.synthesis_phases),
    )


def _record_synthesis_phase(
    result: AskResult,
    *,
    name: str,
    status: str,
    remaining_ms_at_entry: float,
    timeout_s: int,
    started: float,
    reason: str = "",
    execution_mode: str = "provider",
) -> None:
    """记一段 grounded 链的耗时与入口剩余预算。

    只在这里做取整和归一，调用点保持一行；失败原因存归一码而不是原始串，
    原始串可能带 provider 措辞，不该进公开 trace。
    """

    result.synthesis_phases = (
        *result.synthesis_phases,
        SynthesisPhase(
            name=name,
            status=status,
            remaining_ms_at_entry=max(0, round(remaining_ms_at_entry)),
            timeout_s=max(0, int(timeout_s)),
            elapsed_ms=max(0, round((time.monotonic() - started) * 1000)),
            reason_code=(
                _stable_llm_fallback_reason(reason) if reason else ""
            ),
            execution_mode=execution_mode,
        ),
    )


def _quality_gate_diagnostic_reason(
    issues: list[answer_model.QualityIssue],
) -> tuple[str, str]:
    codes = {
        issue.code
        for issue in issues
        if isinstance(getattr(issue, "code", None), str)
    }
    binding_codes = {
        "llm_missing_claim_binding",
        "llm_invalid_claim_id",
        "llm_invalid_evidence_atom_id",
        "llm_fact_without_evidence_atom",
    }
    if codes & binding_codes:
        return (
            "claim_binding_failed",
            "synthesis candidate did not pass claim and evidence binding validation",
        )
    return (
        "quality_gate_rejected",
        "synthesis candidate did not pass deterministic quality validation",
    )


def synthesize_prepared_answer(prepared: PreparedAnswer) -> AskResult:
    options = prepared.options
    result = prepared.result
    messages = result.prepared_synthesis_messages
    if not messages:
        _set_synthesis_diagnostic(
            result,
            state="not_prepared",
            reason_code="no_prepared_messages",
            detail="synthesis messages were not prepared for this route",
        )
        return result
    if result.answer_spec is None:
        _set_synthesis_diagnostic(
            result,
            state="not_prepared",
            reason_code="no_answer_spec",
            detail="no AnswerSpec was available for synthesis",
        )
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
        _set_synthesis_diagnostic(
            result,
            state="rejected",
            reason_code="grounded_required_fallback",
            detail="grounded presenter did not promote an answer; legacy prose is disabled",
        )
        return result
    started = time.monotonic()
    deadline = _llm_deadline(options)
    chunks: list[str] = []
    provider_connect_ms: int | None = None
    first_token_ms: int | None = None
    last_token_ms: int | None = None
    # 相邻 delta 的最大间隔（TTFB 不计入——首 token 慢是模型在想，不是卡住）。
    max_gap_ms: int = 0
    stream_elapsed_ms: int | None = None
    quality_gate_ms: int | None = None
    provider_finish_reason: str | None = None
    provider = llm_refine.detect_provider(options.llm_model)
    _set_synthesis_diagnostic(
        result,
        state="attempted",
        reason_code="provider_started",
        detail="synthesis provider call started",
    )

    def capture_connected() -> None:
        nonlocal provider_connect_ms
        if provider_connect_ms is None:
            provider_connect_ms = max(
                0,
                round((time.monotonic() - started) * 1000),
            )

    def capture(delta: str) -> None:
        nonlocal first_token_ms, last_token_ms, max_gap_ms
        if options.stream_cancel_check is not None and options.stream_cancel_check():
            raise llm_refine.LLMStreamCancelled()
        elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
        # 相邻内容 delta 之间的最大间隔。ch06b 把这个叫 stall 检测，与 idle
        # 看门狗解决的是不同问题——idle 是「一个事件都没有，连接可能死了」，
        # stall 是「有事件但间隔大，连接活着但那边很慢」。判据挂在
        # last_token_ms 上而不是 first_token_ms：没有前一个 delta 就没有「间隔」
        # 可言，首 token 慢是模型在想，不是卡住（ch06b 明确点名的坑）。
        #
        # 这里**故意不设阈值**：ch06b 的 30s 来自 Anthropic 的生产数据，而
        # grounded composer 的固定 grant 也只有 40 秒，照抄 30s 基本不会触发。先把实测
        # 分布记下来，有数据了再定阈值和是否要中断。
        if last_token_ms is not None:
            max_gap_ms = max(max_gap_ms, elapsed_ms - last_token_ms)
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
            "max_delta_gap_ms": max_gap_ms,
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
        _set_synthesis_diagnostic(
            result,
            state="failed",
            reason_code=result.llm_fallback_reason or "provider_unavailable",
            detail=(
                "synthesis provider did not return a usable response "
                f"({result.llm_fallback_reason or 'provider_unavailable'})"
            ),
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
        _set_synthesis_diagnostic(
            result,
            state="failed",
            reason_code=result.llm_fallback_reason or "provider_incomplete",
            detail="synthesis provider response did not finish cleanly",
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
        diagnostic_reason, diagnostic_detail = _quality_gate_diagnostic_reason(
            blocking_issues
        )
        _set_synthesis_diagnostic(
            result,
            state="rejected",
            reason_code=diagnostic_reason,
            detail=diagnostic_detail,
        )
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
    _set_synthesis_diagnostic(
        result,
        state="accepted",
        reason_code="validated",
        detail="synthesis passed deterministic quality gates",
    )
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


# 可以落到用户面前的影子状态。``judge_outage_released`` 是 judge 因瞬时故障缺席时
# 的降级放行——正文已过确定性层且自带警示，见 ``_judge_outage_release``。
_PROMOTABLE_SHADOW_STATUSES = frozenset(
    {"accepted", "repaired", "judge_outage_released"}
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
        # Frozen production replay used the base 2400/1200-token contract.
        token_budget_scale=1,
    )
    shadow = result.grounded_composer_shadow
    presented = (
        _strip_empty_grounded_sections(shadow.presented_answer)
        if shadow is not None and shadow.presented_answer
        else ""
    )
    if (
        shadow is None
        or shadow.status not in _PROMOTABLE_SHADOW_STATUSES
        or _grounded_body_line_count(presented) < 2
    ):
        if shadow is not None:
            reason = shadow.failure_reason or (
                "insufficient_grounded_body"
                if shadow.status in _PROMOTABLE_SHADOW_STATUSES
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
        # 补分支必须在 stream 之前：先推给前端再改 result.synthesis，会让流式看到的
        # 正文和最终落库的正文不一致。
        ensure_forecast_scenarios_visible(result)
        result.synthesis_messages = [
            *(result.prepared_synthesis_messages or []),
            {"role": "assistant", "content": result.synthesis},
        ]
        result.grounded_fallback_used = True
        _set_synthesis_diagnostic(
            result,
            state="rejected",
            reason_code="grounded_required_fallback",
            detail="grounded presenter did not pass validation; deterministic fallback used",
        )
        if options.stream_text_delta is not None:
            options.stream_text_delta(result.synthesis)
        return True
    result.synthesis = (
        f"{result.data_notice}\n\n{presented}"
        if result.data_notice
        else presented
    )
    # 「过了语义审」和「没人审但放行了」不是同一件事，遥测不能都写成 accepted。
    # 原先这里无条件写 accepted/validated，于是 2026-08-02 那批 7 个 accepted 里
    # 有 6 个的语义审根本没跑——正文自带「语义复核未完成」的告示，诊断却说 passed。
    # 台账按 state 聚合，读出来的健康度就是假的。
    if shadow.status == "judge_outage_released":
        _set_synthesis_diagnostic(
            result,
            state="released_unverified",
            reason_code="judge_outage_released",
            detail=(
                "deterministic binding passed; semantic judge absent, "
                "released with an explicit notice"
            ),
        )
    else:
        _set_synthesis_diagnostic(
            result,
            state="accepted",
            reason_code="validated",
            detail="grounded presenter passed deterministic and semantic gates",
        )
    ensure_forecast_scenarios_visible(result)
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


# 预测题的三个必需分支，以及 AnswerSpec 里承载它们的确定性 claim。
_FORECAST_SCENARIO_CLAIMS: tuple[tuple[str, str], ...] = (
    ("rebound_case", "generic:rebound_case"),
    ("decline_case", "generic:decline_case"),
    ("invalidation", "generic:invalidation"),
)


def ensure_forecast_scenarios_visible(result: AskResult) -> None:
    """Keep the user-facing answer complete when LLM prose drops required claims.

    AnswerSpec already contains the three deterministic, evidence-bound scenario
    claims.  A grounded composer may validly paraphrase them, but it must not
    silently omit an entire branch of a two-scenario question.  Append only the
    missing deterministic block; do not regenerate or overwrite the model's
    useful prose.

    这个收口原先挂在 ``ask.py`` 的尾部，而 GenericResearchOwner 路径（也就是
    「明天怎么走」实际走的那条）在 ``_answer_query_impl`` 开头就 return 了，永远到
    不了那一行——于是它对前瞻题一次都没生效过。实测：composer 的 judge 判掉了写着
    失效条件的那句，repair 把它删掉，最终正文只剩「反之…有走弱的风险」，门禁判
    invalidation 缺失，整份答案被 fail-closed 成「请补充数据源或稍后重试」。

    因此改挂在合成之后：composer 怎么改写都行，但删掉一整支必需分支时由确定性
    文本补回。判定直接复用门禁的 ``answer_has_output_marker``，不再维护第二套
    ("反弹","继续下跌","失效条件") 词表——两套词表迟早会漂移，而漂移的结果就是
    「补过了但门禁仍判缺」或者反过来。
    """

    if (
        result.question_plan is None
        or result.question_plan.question_type != QUESTION_MARKET_FORECAST
        or not result.synthesis
        or result.answer_spec is None
    ):
        return
    claims = {
        claim.claim_id: claim
        for claim in result.answer_spec.candidate_facts
        if claim.claim_id in {claim_id for _, claim_id in _FORECAST_SCENARIO_CLAIMS}
    }
    lines: list[str] = []
    for output_id, claim_id in _FORECAST_SCENARIO_CLAIMS:
        # 只补真正缺的那一支：整块重贴会把 composer 已经写好的情景又复述一遍。
        if answer_has_output_marker(output_id, result.synthesis):
            continue
        claim = claims.get(claim_id)
        if claim is None or not claim.text.strip():
            continue
        refs = f" [{', '.join(claim.evidence_ids)}]" if claim.evidence_ids else ""
        lines.append(f"{claim.text.strip()}{refs}")
    if not lines:
        return
    block = "## 基准判断与条件情景\n" + "\n".join(lines)
    body = result.synthesis.rstrip()
    # 「（非投资建议）」是收尾声明，必须留在最后一行；补的分支插在它前面，
    # 否则正文读起来是「…（非投资建议）」之后又冒出两段判断。
    disclaimer = "（非投资建议）"
    if body.endswith(disclaimer):
        head = body[: -len(disclaimer)].rstrip()
        result.synthesis = f"{head}\n\n{block}\n\n{disclaimer}"
        return
    result.synthesis = f"{body}\n\n{block}"


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


def _grounded_profile(options: AskOptions):
    """本轮生效的 grounded 预算档位；缺省回退到模块级 ``grounded_deep``。

    存在的理由是让**准入地板和发钱的信封出自同一套数**。此前地板直接读
    模块级常量（按 root=180 标定的 97s），而窗口由 policy/owner tier 决定，
    两边一错位就静默恒降级，且 trace 只留一句「预算不足」，读起来像偶发。
    """

    return options.grounded_budget_profile or grounded_deep


def _shadow_deadline(options: AskOptions) -> llm_refine.Deadline:
    """影子链截止时间 = min(自身超时, 合成尾段父 Deadline)。

    P0 修复：此前 promote 路径把 shadow timeout 抬到 ≥240s 并新建 Deadline，
    完全无视 turn 级 ResearchDeadline——子流程可以突破根截止时间。规则收敛为
    child = min(parent, now + stage_slice)，任何子阶段不得晚于根。

    父 Deadline 取 ``synthesis_deadline``（turn 根）而非 ``deadline``（owner 检索
    窗口）。两者曾是同一个：结果是 generic owner 那 30s/90s 的**检索**窗口反过来
    给**合成**尾段定了上限，而准入地板 97s 是按根 180s 标定的——standard tier
    整窗 90 < 97，composer 恒进不去，研究耗时为 0 也一样。owner 阶段此时已经
    completed，它的窗口本就不该再约束后面的合成。

    仍然 clamp：合成尾段不得晚于根 turn，``shadow_grounded_timeout``
    （= ``child_seconds``）继续封顶单段用量。
    """
    deadline = llm_refine.Deadline.from_timeout(options.shadow_grounded_timeout)
    parent = options.synthesis_deadline or options.deadline
    if parent is not None:
        deadline = llm_refine.Deadline(
            min(deadline.expires_at, parent.expires_at)
        )
    return deadline


def repair_unfulfilled_answer(
    *,
    question: str,
    answer_text: str,
    answer_spec: answer_model.AnswerSpec,
    verdict,  # task_fulfillment.FulfillmentVerdict（避免模块级循环导入）
    required_outputs,  # tuple[RequiredOutput, ...]
    llm_model: str | None = None,
    timeout: int,
) -> tuple[str, object] | None:
    """门禁判缺时补写一轮；仍不过则返回 None，由调用方 fail-closed。

    这是官方 Claude Code「拒绝作为反馈回灌」的对应物：工具被拒时模型收到的是
    一条拒绝消息**作为 tool result**，然后换方法或说明无法继续，而不是整轮作废。
    ch04「分层错误级联」给了它的通用形式——Bash 出错只取消同级 Bash、不动
    Read/Grep，为的是避开「完全隔离（错误被忽视）」和「全局中止（一个小错误
    杀死整个会话）」两个极端。我们原先站在「全局中止」这一极。

    三条约束都在这个函数里，不依赖调用方守规矩：

    1. **只补一轮**——这里没有循环。额外那次调用由 turn 级 ``LlmCallLedger``
       兜底（``conversation_orchestrator`` 的 ``call_ledger_scope``），预算耗尽
       时 ``synthesize_messages`` 直接拒发，修复轮自动不发生，退回今天的行为。
       所以**不需要第二个计数器**。
    2. **补写只能用 registry 里已有的事实**——见
       ``fulfillment_revision_user_content`` 的来源约束。
    3. **补写后必须重新过门禁**——重判在下面，只有新判定为 complete 才返回。
       这一条做成结构性的：调用方拿不到「跑过修复轮」这个理由来放行。
    """

    from intelligence.services import task_fulfillment

    missing = tuple(
        (item.output_id, item.gap or "未覆盖")
        for item in verdict.missing_required
    )
    if not missing:
        return None
    registry_block = answer_model.grounded_claim_registry_block(
        answer_spec,
        query=question,
        max_chars=12_000,
    )
    if not registry_block.strip():
        return None
    revised, _reason = llm_refine.synthesize_messages(
        [
            {
                "role": "system",
                "content": llm_refine.grounded_composer_system_prompt(),
            },
            {
                "role": "user",
                "content": llm_refine.fulfillment_revision_user_content(
                    missing,
                    registry_block,
                    answer_text,
                ),
            },
        ],
        model_override=llm_model,
        timeout=timeout,
        temperature=0.0,
    )
    if revised is None or not revised.answer.strip():
        return None
    recheck = task_fulfillment.evaluate_answer_spec_fulfillment(
        question=question,
        required_outputs=required_outputs,
        answer_text=revised.answer,
        answer_spec=answer_spec,
    )
    if recheck.status != "complete":
        return None
    return revised.answer, recheck


def _shadow_phase_timeout(
    deadline: llm_refine.Deadline,
    configured: int,
    share: float,
) -> int:
    """给 judge 分配同一根 deadline 的全部实际剩余时间。"""

    remaining = max(0.0, deadline.remaining())
    if remaining <= 0:
        return 1
    return max(1, min(int(configured), int(max(1.0, remaining * share))))


def _phase_slice_collapsed(
    deadline: llm_refine.Deadline,
    share: float,
) -> bool:
    """这一段分到的时间片是否已经塌到下限——塌了就别发这个请求了。

    判据不是新拍的数：``_shadow_phase_timeout`` 里那个 ``max(1, ...)`` 就是下限。
    当 ``remaining * share < 1`` 时它返回的 1 秒不是「预算」，是兜底值——拿 1 秒去
    换一次上千 token 的生成，结果必然是超时，而代价是把最后这点时间也烧掉，然后
    才降级。先降级和后降级输出完全一样，区别只是用户多等了这一段。

    刻意只堵**必然失败**这一档，不做「估计来不及就放弃」——那需要实测吞吐
    （token/秒 × 剩余秒数 vs max_tokens），而吞吐正是 phase 埋点这一轮才开始收的。
    等有了分布再收紧，现在不拍脑袋。
    """

    return deadline.remaining() * share < 1.0


# judge 是「后台请求」——用户不在等它的结果，它挂了不代表被审对象有问题。
# 官方 Claude Code 对这类请求的处理是减载而不是重试（`FOREGROUND_529_RETRY_SOURCES`
# 只放前台请求，摘要/标题/分类器一律立即放弃），理由是过载时每次重试对网关是 3-10 倍
# 放大，而「用户根本看不到这些失败」。我们这里的对应动作是：judge 因瞬时故障没能给出
# 判定时，放行已经通过确定性绑定校验的候选正文，而不是把整份答案换成缺口模板。
#
# 白名单只收「provider 那边出了事」，不收「judge 自己产出有问题」和配置问题——
# 这跟 episode 侧 `_transient_failure_candidate` 的取舍一致（那里的注释写得很明白：
# configuration、malformed-output、contract 三类继续走 fail-closed）。
# 注意 4xx 的取舍跟 ch06b 的 `shouldRetry` 不一样，这是**两个不同的问题**：
# 它问「这次调用该不该重试」（401 要重试，因为可能是另一个进程刷新了 token）；
# 我们问「被审对象是不是无辜的」。401/403 意味着后续每次调用都会失败，
# 放行会从例外变成常态——所以跟配置问题一样 fail-closed。别照抄。
_TRANSIENT_JUDGE_REASONS = frozenset(
    {
        "timeout",
        "provider_stalled",
        "provider_rate_limited",
        "provider_overloaded",
        "provider_http_error",
        "empty_response",
        "call_budget_exhausted",
    }
)
_INSUFFICIENT_BUDGET_REASON = "本轮剩余预算不足，未发起该段合成"
# 刻意不在上面：``deadline_exhausted_local`` 与 ``insufficient_budget``。那是我们自己的共享 deadline 用完了，
# 按本文件上方的判据（放行会不会从例外变成常态）属于必须 fail-closed 的一类——
# 2026-08-02 那批 23 轮里 15 轮撞的就是它，放行等于把「多数答案没过语义审」写成常态。
# 代价是可见降级率上升；这是把静默的未核验答案换成显式降级，不是新增故障。

_JUDGE_OUTAGE_NOTICE = (
    "（本条已通过证据绑定校验，但语义复核因服务瞬时问题未完成。）"
)


def _judge_outage_release(
    candidate_answer: str,
    answer_spec: answer_model.AnswerSpec,
    judge_reason: str,
) -> str | None:
    """judge 因瞬时故障缺席时，把候选正文带警示放行；否则返回 None。

    三条约束照抄 episode 侧的 ``_transient_failure_candidate``：
    只放行瞬时故障、正文必须已经过确定性层、放行后的文本自带警示。
    这里**不放宽任何领域判据**——数字/公司/日期是否有出处仍由确定性层把关，
    跳过的只是语义复核这一道通用层的第二意见。
    """

    if _stable_llm_fallback_reason(judge_reason) not in _TRANSIENT_JUDGE_REASONS:
        return None
    presented = answer_model.present_grounded_composer_answer(
        candidate_answer,
        answer_spec,
    )
    if not _strip_empty_grounded_sections(presented).strip():
        return None
    return f"{_JUDGE_OUTAGE_NOTICE}\n\n{presented}"


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
    registry_block = answer_model.grounded_claim_registry_block(
        result.answer_spec,
        query=options.query,
        max_chars=12_000,
    )
    # 本轮的验收标准。空元组保持旧行为（专项 owner 之外的调用方尚未提供契约）。
    required_outputs_block = tuple(result.answer_spec.prompt_constraints)
    brief_started = time.monotonic()
    brief_remaining_ms = deadline.remaining() * 1000
    decision_brief = answer_model.build_deterministic_decision_brief(
        result.answer_spec
    )
    _record_synthesis_phase(
        result,
        name="brief",
        status="failed" if decision_brief is None else "ok",
        remaining_ms_at_entry=brief_remaining_ms,
        timeout_s=0,
        started=brief_started,
        execution_mode="deterministic",
    )
    if decision_brief is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="brief_rejected",
                failure_reason="deterministic_brief_unavailable",
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    compose_started = time.monotonic()
    compose_remaining = deadline.remaining()
    compose_remaining_ms = compose_remaining * 1000
    profile = _grounded_profile(options)
    if (
        compose_remaining
        < profile.minimum_two_phase_entry_seconds
    ):
        _record_synthesis_phase(
            result,
            name="composer",
            status="skipped",
            remaining_ms_at_entry=compose_remaining_ms,
            timeout_s=0,
            started=compose_started,
            reason=_INSUFFICIENT_BUDGET_REASON,
        )
        result.grounded_composer_shadow = answer_model.GroundedComposerShadow(
            status="composer_unavailable",
            decision_brief=decision_brief,
            failure_reason=_INSUFFICIENT_BUDGET_REASON,
            elapsed_ms=round((time.monotonic() - started) * 1000),
        )
        return result
    # Fixed grant derived from the frozen replay. Subtract the judge reserve
    # again at the provider boundary so prompt-building overhead cannot steal
    # the 57s admitted for phase two.
    compose_timeout = min(
        profile.composer_grant_seconds,
        max(0.0, deadline.remaining() - profile.judge_reserve_seconds),
    )
    composed, compose_reason = llm_refine.synthesize_messages(
        llm_refine.build_grounded_composer_messages(
            options.query,
            decision_brief.to_prompt_block(),
            registry_block,
            required_outputs=required_outputs_block,
        ),
        model_override=options.llm_model,
        timeout=compose_timeout,
        deadline=deadline,
        temperature=0.2,
        max_tokens=2400 * token_budget_scale,
        max_chars=16000 * token_budget_scale,
    )
    _record_synthesis_phase(
        result,
        name="composer",
        status="failed" if composed is None else "ok",
        remaining_ms_at_entry=compose_remaining_ms,
        timeout_s=compose_timeout,
        started=compose_started,
        reason=compose_reason if composed is None else "",
    )
    if composed is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="composer_unavailable",
                decision_brief=decision_brief,
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
        # 同一类笔误的第二种形状：把聚合 claim 展开成一家一行，却每行都绑回聚合。
        raw_answer = answer_model.rebind_entity_claim_ids(
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
    judge_started = time.monotonic()
    judge_remaining_ms = deadline.remaining() * 1000
    judge_timeout = _shadow_phase_timeout(
        deadline, options.shadow_grounded_timeout, 1.0
    )
    judge_skipped = _phase_slice_collapsed(deadline, 1.0)
    if judge_skipped:
        # 不发这次调用，但**不放行**：跳过的原因是我们自己的预算，
        # ``insufficient_budget`` 不在瞬时故障白名单里，下面照常 fail-closed。
        judged, judge_reason = None, _INSUFFICIENT_BUDGET_REASON
    elif judge_override is not None:
        with llm_refine.provider_override(judge_override):
            judged, judge_reason = llm_refine.synthesize_messages(
                judge_messages,
                timeout=judge_timeout,
                deadline=deadline,
                temperature=0.0,
                max_tokens=1200 * token_budget_scale,
                max_chars=8000 * token_budget_scale,
            )
    else:
        judged, judge_reason = llm_refine.synthesize_messages(
            judge_messages,
            model_override=options.llm_model,
            timeout=judge_timeout,
            deadline=deadline,
            temperature=0.0,
            max_tokens=1200 * token_budget_scale,
            max_chars=8000 * token_budget_scale,
        )
    _record_synthesis_phase(
        result,
        name="judge",
        status=(
            "skipped" if judge_skipped else ("failed" if judged is None else "ok")
        ),
        remaining_ms_at_entry=judge_remaining_ms,
        timeout_s=judge_timeout,
        started=judge_started,
        reason=judge_reason if judged is None else "",
    )
    if judged is None:
        released = _judge_outage_release(
            candidate_answer,
            result.answer_spec,
            judge_reason,
        )
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                # 状态不冒充 accepted：这份答案没被语义复核过，遥测要能分得出来。
                status=(
                    "judge_outage_released"
                    if released is not None
                    else "judge_unavailable"
                ),
                decision_brief=decision_brief,
                raw_answer=raw_answer,
                repaired_answer=(
                    candidate_answer if repaired else None
                ),
                presented_answer=released,
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
            # judge 的序号跟 harness 的编号对不上，按它 issue 里引用的原文重新定位。
            rejected_sentence_indexes=(
                answer_model.resolve_judge_sentence_indexes(
                    judge_report,
                    sentences,
                )
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


# 分类器已下沉到 llm_refine——它解析的字符串就是那边产出的，放在一起改产出
# 的人才看得见解析规则。此处保留旧名，ask.py 和 judge 测试按这个名字引用。
_stable_llm_fallback_reason = llm_refine.stable_llm_fallback_reason

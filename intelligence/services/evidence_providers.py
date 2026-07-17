"""证据源 provider 层：把 ``answer_query`` 的各证据段拆成独立、可测的采集函数。

每个 provider 只消费 :class:`EvidenceContext`（检索共享上下文），产出带引用标签的
证据行 + 结构化 claim（写入 ``ctx.structured_claims``）。行为与拆分前逐字一致，
由黄金快照测试（``test_golden_answers.py``）保护。

当前覆盖：S（盘面快照）、G（图谱概念/公司分层）、R（evidence_index + 候选携带证据）。
后续阶段将纳入 W/E/L 与 D 数据块，并引入 provider registry。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from intelligence.adapters.knowledge import evidence_status
from intelligence.services import answer_model, research_brief

if TYPE_CHECKING:
    from intelligence.adapters.knowledge import KnowledgeAdapter
    from intelligence.services.answer_orchestrator import QuestionPlan
    from intelligence.services.ask import AskOptions, AskResult
    from intelligence.services.entity_anchor import EntityAnchor


def _company_exposure_tier(row: dict[str, Any]) -> str:
    strength = str(row.get("strength") or "").lower()
    confidence = str(row.get("confidence") or "").lower()
    evidence_layer = str(row.get("evidence_layer") or "").lower()
    direct_company_evidence = (
        evidence_layer in {"l3", "l2_l3", "l3_l4", "official"}
        and "candidate" not in evidence_layer
    )
    if (
        strength in {"core", "strong"}
        and confidence == "high"
        and direct_company_evidence
    ):
        return "core"
    if (
        strength in {"peripheral", "weak"}
        or evidence_layer in {"graph_only", "exposure_only"}
        or confidence == "low"
    ):
        return "peripheral"
    return "other"


@dataclass
class EvidenceContext:
    """一次 ask 检索的共享上下文；provider 只读配置、追加 claims/citations。"""

    options: "AskOptions"
    result: "AskResult"
    knowledge: "KnowledgeAdapter"
    question_plan: "QuestionPlan"
    anchor: "EntityAnchor | None"
    candidate: dict[str, Any] | None
    doc: dict[str, Any]
    export_name: str
    claim_theme: str
    graph_query: str
    cite: Callable[..., str]
    structured_claims: list[answer_model.Claim]
    company_candidates: list[answer_model.CompanyCandidate]
    is_stale: Callable[[dict[str, Any]], bool]
    confidence_score: Callable[[Any], float | None]


@dataclass
class GraphEvidence:
    concept_lines: list[str] = field(default_factory=list)
    company_lines: list[str] = field(default_factory=list)
    company_evidence_concepts: dict[str, str] = field(default_factory=dict)
    tiers: dict[str, list[str]] = field(
        default_factory=lambda: {"core": [], "peripheral": [], "other": []}
    )
    concepts_result: dict[str, Any] = field(default_factory=dict)
    exposures_result: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceIndexBundle:
    lines: list[str] = field(default_factory=list)
    stale_notes: list[str] = field(default_factory=list)


def collect_market_snapshot(ctx: EvidenceContext) -> list[str]:
    """S：盘面 theme-candidates 快照信号与市场环境。"""
    candidate = ctx.candidate
    cite = ctx.cite
    market_lines: list[str] = []
    if candidate:
        for sd in (candidate.get("score_detail") or [])[:5]:
            sig = sd.get("signal")
            sc = sd.get("score")
            reason = sd.get("reason", "")
            tag = cite("S", f"{ctx.export_name} · score_detail.{sig}", str(sd.get("source", "")))
            line = f"信号 {sig}（{sc}）：{reason} {tag}"
            market_lines.append(line)
            ctx.structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"market:{tag.strip('[]')}",
                    text=line,
                    claim_type="market_signal",
                    theme=ctx.claim_theme,
                    status=answer_model.ClaimStatus.VERIFIED,
                    evidence_tier="L4",
                )
            )
        market_context = ctx.doc.get("market_context") or {}
        if market_context:
            caps = "、".join(
                f"{s.get('name')}（占比 {s.get('ratio')}%）"
                for s in (market_context.get("capacity_sectors") or [])[:3]
            )
            tag = cite("S", f"{ctx.export_name} · market_context")
            line = (
                f"市场环境：{market_context.get('market_stage')}，成交 {market_context.get('total_amount')} 亿，"
                f"涨停 {market_context.get('limit_up')} / 跌停 {market_context.get('limit_down')}，容量前三 {caps} {tag}"
            )
            market_lines.append(line)
            ctx.structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"market:{tag.strip('[]')}",
                    text=line,
                    claim_type="market_context",
                    theme=ctx.claim_theme,
                    status=answer_model.ClaimStatus.VERIFIED,
                    evidence_tier="L4",
                )
            )
    return market_lines


def collect_graph(ctx: EvidenceContext) -> GraphEvidence:
    """G：知识图谱概念命中 + 公司暴露分层。"""
    options = ctx.options
    anchor = ctx.anchor
    cite = ctx.cite
    knowledge = ctx.knowledge
    bundle = GraphEvidence()
    if anchor is not None:
        ctx.result.found_graph = True
        tag = cite("G", "knowledge-base · wiki/relations/entity_exposures.json", f"实体解析 matched_by={anchor.matched_by}")
        bundle.concept_lines.append(f"{anchor.summary()} {tag}")
    concepts = knowledge.get_concept_matches(ctx.graph_query, limit=options.top_concepts)
    bundle.concepts_result = concepts
    if concepts.get("found"):
        ctx.result.found_graph = True
        names = "、".join(f"{i['concept']}({i['score']})" for i in concepts["items"])
        tag = cite("G", "knowledge-base · wiki/relations/concept_graph.json")
        line = f"命中概念：{names} {tag}"
        bundle.concept_lines.append(line)
        ctx.structured_claims.append(
            answer_model.make_claim(
                claim_id=f"concept:{tag.strip('[]')}",
                text=line,
                claim_type="theme_mapping",
                theme=ctx.claim_theme,
                status=answer_model.ClaimStatus.CANDIDATE,
                evidence_tier="concept_graph",
            )
        )

    focus_entities = (
        ctx.question_plan.research_spec.focus_entities
        if ctx.question_plan.research_spec is not None
        else ()
    )
    exposure_limit = max(options.top_companies, len(focus_entities) * 4)
    exposures = knowledge.get_exposure_matches(ctx.graph_query, limit=exposure_limit)
    bundle.exposures_result = exposures
    if exposures.get("found") and focus_entities:
        focus_order = {
            company: index for index, company in enumerate(focus_entities)
        }
        exposure_items = list(exposures["items"])
        exposure_items.sort(
            key=lambda row: (
                0 if str(row.get("company") or "") in focus_order else 1,
                focus_order.get(str(row.get("company") or ""), len(focus_order)),
            )
        )
        exposures["items"] = exposure_items[: options.top_companies]
    tiers = bundle.tiers
    if exposures.get("found"):
        ctx.result.found_graph = True
        for row in exposures["items"]:
            conf = str(row.get("confidence") or "").lower()
            layer = str(row.get("evidence_layer") or "")
            company = str(row.get("company") or "").strip()
            concept = str(row.get("concept") or "").strip()
            if company and concept:
                bundle.company_evidence_concepts[company] = concept
            exposure_tier = _company_exposure_tier(row)
            label = f"{company}({row.get('ticker')}|{row.get('role') or '—'}|{conf or '?'}/{layer or '?'})"
            tiers[exposure_tier].append(label)
            requested_tier = {
                "core": answer_model.CompanyTier.CORE,
                "peripheral": answer_model.CompanyTier.PERIPHERAL,
            }.get(exposure_tier, answer_model.CompanyTier.CANDIDATE)
            ctx.company_candidates.append(
                answer_model.CompanyCandidate(
                    company=company,
                    ticker=str(row.get("ticker") or ""),
                    chain_stage=str(row.get("chain_stage") or row.get("role") or "待确认"),
                    directness=str(row.get("strength") or "待确认"),
                    requested_tier=requested_tier,
                    evidence_layer=layer,
                )
            )
        tag = cite("G", "knowledge-base · wiki/relations/entity_exposures.json")
        for candidate_company in ctx.company_candidates:
            is_direct = candidate_company.requested_tier == answer_model.CompanyTier.CORE
            ctx.structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"company:{candidate_company.company}:{tag.strip('[]')}",
                    text=(
                        f"{candidate_company.company}与"
                        f"{bundle.company_evidence_concepts.get(candidate_company.company, '该题材')}"
                        "存在公司级映射。"
                    ),
                    claim_type="company_mapping",
                    theme=ctx.claim_theme,
                    status=(
                        answer_model.ClaimStatus.VERIFIED
                        if is_direct
                        else answer_model.ClaimStatus.CANDIDATE
                    ),
                    evidence_tier=candidate_company.evidence_layer,
                    company=candidate_company.company,
                    evidence_ids=(tag.strip("[]"),),
                )
            )
        if tiers["core"]:
            bundle.company_lines.append(f"核心层：{'、'.join(tiers['core'])} {tag}")
        if tiers["other"]:
            bundle.company_lines.append(f"中间层：{'、'.join(tiers['other'])} {tag}")
        if tiers["peripheral"]:
            bundle.company_lines.append(f"外围/弱关联层：{'、'.join(tiers['peripheral'])} {tag}")
    return bundle


def collect_evidence_index(
    ctx: EvidenceContext,
    company_evidence_concepts: dict[str, str],
) -> EvidenceIndexBundle:
    """R：KB evidence_index 证据（含 Temporal Facts 状态）+ 盘面候选携带证据。"""
    options = ctx.options
    anchor = ctx.anchor
    cite = ctx.cite
    result = ctx.result
    bundle = EvidenceIndexBundle()
    evidence_lines = bundle.lines
    stale_notes = bundle.stale_notes
    seen_evidence: set[str] = set()
    targets: list[str] = []
    if anchor is not None:
        targets.append(anchor.entity)
    if result.matched_theme:
        targets.append(result.matched_theme)
    targets.append(options.query)
    targets.extend(company_evidence_concepts)
    for target in dict.fromkeys(t for t in targets if t):
        ev = ctx.knowledge.get_evidence(
            target,
            concept=company_evidence_concepts.get(target),
            limit=options.max_evidence,
        )
        if not ev.get("found"):
            continue
        for item in ev["items"]:
            key = f"{item.get('target')}|{item.get('source')}|{item.get('evidence')}"
            if key in seen_evidence:
                continue
            seen_evidence.add(key)
            result.found_graph = True
            stale = ctx.is_stale(item)
            status = evidence_status(item)
            superseded = status == "superseded"
            tag = cite(
                "R",
                "knowledge-base · wiki/relations/evidence_index.json",
                f"target={item.get('target')} source={item.get('source')}",
            )
            mark = ""
            if superseded:
                mark = " ⚠️已被新证据取代"
            elif stale:
                mark = " ⚠️过期"
            line = (
                f"{item.get('target')}：{str(item.get('evidence'))[:80]}"
                f"（{item.get('source')}, {item.get('source_date') or '无日期'}, "
                f"质量 {item.get('confidence') or '?'}{mark}） {tag}"
            )
            evidence_lines.append(line)
            layer_name = research_brief.classify_evidence_line(line, "R")
            target_name = str(item.get("target") or "").strip()
            ctx.structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"evidence:{tag.strip('[]')}",
                    text=line,
                    claim_type="company_evidence" if target_name in company_evidence_concepts else "theme_evidence",
                    theme=ctx.claim_theme,
                    status=(
                        answer_model.ClaimStatus.VERIFIED
                        if layer_name == "L3" and not stale and not superseded
                        else answer_model.ClaimStatus.CANDIDATE
                    ),
                    evidence_tier=layer_name,
                    company=target_name if target_name in company_evidence_concepts else None,
                    confidence=ctx.confidence_score(item.get("confidence")),
                    freshness=(
                        "superseded"
                        if superseded
                        else "stale"
                        if stale
                        else "current"
                    ),
                )
            )
            if superseded:
                replacement = str(
                    item.get("superseded_by") or item.get("status_note") or ""
                ).strip()
                suffix = f"，新证据：{replacement}" if replacement else ""
                stale_notes.append(
                    f"{item.get('target')} 该条证据已被取代{suffix}，只能作历史参照，不能当作当前事实 {tag}"
                )
            elif stale:
                stale_notes.append(
                    f"{item.get('target')} 证据 {item.get('source_date')} 已超 {options.stale_days} 天，需复核是否被新数据证伪 {tag}"
                )
            if len(evidence_lines) >= options.max_evidence:
                break
        if len(evidence_lines) >= options.max_evidence:
            break

    # candidate-embedded knowledge_evidence as cross-check
    for ke in (ctx.candidate or {}).get("knowledge_evidence", []) or []:
        src = ke.get("source")
        key = f"{ke.get('target')}|{src}"
        if not src or key in seen_evidence:
            continue
        seen_evidence.add(key)
        tag = cite("R", f"{ctx.export_name} · knowledge_evidence")
        line = (
            f"{ke.get('target')}：{src}（质量 {ke.get('quality') or '?'}，盘面候选携带） {tag}"
        )
        evidence_lines.append(line)
        target_name = str(ke.get("target") or "").strip()
        ctx.structured_claims.append(
            answer_model.make_claim(
                claim_id=f"candidate-evidence:{tag.strip('[]')}",
                text=line,
                claim_type="company_evidence" if target_name in company_evidence_concepts else "theme_evidence",
                theme=ctx.claim_theme,
                status=answer_model.ClaimStatus.CANDIDATE,
                evidence_tier="candidate_snapshot",
                company=target_name if target_name in company_evidence_concepts else None,
            )
        )
    return bundle

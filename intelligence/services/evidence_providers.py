"""证据源 provider 层：把 ``answer_query`` 的各证据段拆成独立、可测的采集函数。

每个 provider 只消费 :class:`EvidenceContext`（检索共享上下文），产出带引用标签的
证据行 + 结构化 claim（写入 ``ctx.structured_claims``）。行为与拆分前逐字一致，
由黄金快照测试（``test_golden_answers.py``）保护。

当前覆盖：S（盘面快照）、G（图谱概念/公司分层）、R（evidence_index + 候选携带证据）、
W（知识库 hybrid 闭环召回）、E（外部 Web 兜底）、L（L3 官方证据补查）。
后续阶段将纳入 D 数据块，并引入 provider registry。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from intelligence.adapters.knowledge import evidence_status
from intelligence.services import (
    answer_model,
    closed_loop_retrieval,
    evidence_judge,
    exposure_selector,
    kb_rag,
    l3_evidence,
    llm_refine,
    research_brief,
    web_research,
)
from intelligence.services.answer_orchestrator import (
    QUESTION_GENERAL,
    QUESTION_STOCK_DEEP_DIVE,
)
from intelligence.services.research_contract import ResearchDeadline

if TYPE_CHECKING:
    from intelligence.adapters.knowledge import KnowledgeAdapter
    from intelligence.services.answer_orchestrator import QuestionPlan
    from intelligence.services.ask import AskOptions, AskResult
    from intelligence.services.entity_anchor import EntityAnchor


# 旧结论核验门：这些 wiki 目录里的页面本质是“某个时点的判断”而非可直接引用的事实，
# W 召回命中时打〔历史基线〕标签，合成层按先验处理（当下盘面核验 + 四态对照）。
_PRIOR_CONCLUSION_DIRS = ("synthesis/", "briefings/")
_STALE_BYPASS_NOTE_MAX_CHARS = 180
_STALE_EDGE_STATUSES = frozenset({"superseded", "invalidated"})
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_L3_GAP_TERMS = (
    "客户",
    "合作",
    "订单",
    "合同",
    "中标",
    "认证",
    "定点",
    "送样",
    "导入",
    "量产",
    "供货",
    "出货",
    "收入占比",
    "供应商",
)
_L3_OWNER_TYPES = {
    "stock_deep_dive",
    "valuation_estimate",
    "financial_analysis",
    "news_impact",
}
_L3_HARD_SOURCE_TERMS = (
    "L3 官方证据",
    "公司公告",
    "交易所公告",
    "互动易",
    "定期报告",
)


def _is_prior_conclusion_page(file_path: str) -> bool:
    p = str(file_path).replace("\\", "/").lstrip("/")
    return p.startswith(_PRIOR_CONCLUSION_DIRS)


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
    stage_timeout: Callable[[float], float]
    # 本轮题材的逻辑生命周期阶段（如「旧逻辑唤醒·沉睡后唤醒」）。None = 取不到
    # 快照历史，此时证据只按日期做中性标注，不再断言「过期」。
    lifecycle_stage: str | None = None


@dataclass
class WikiEvidence:
    lines: list[str] = field(default_factory=list)
    counter_lines: list[str] = field(default_factory=list)
    llm_line_pairs: list[tuple[str, str]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


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


def _company_name_from_official_title(title: str) -> str | None:
    candidate = re.split(
        r"(?:公告|问询函|回复|互动易|投资者关系|调研纪要)",
        str(title or "").strip(),
        maxsplit=1,
    )[0].strip(" ：:（）()")
    if re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9]{2,20}", candidate):
        return candidate
    return None


def should_request_l3_lookup(
    *,
    options: "AskOptions",
    question_plan: "QuestionPlan",
    local_evidence_text: str = "",
) -> bool:
    """Enable official-evidence lookup only when the answer has an L3-shaped gap.

    The explicit option remains an override.  Otherwise deep company/event
    questions and queries asking about customers/orders/production trigger the
    lookup when the local window does not already contain an official source.
    This closes the previous mismatch where the plan promised L3 retrieval but
    runtime silently kept the tool disabled.
    """
    if options.use_l3_lookup:
        return True
    query = str(options.query or "")
    question_type = str(question_plan.question_type or "")
    asks_hard_fact = any(term in query for term in _L3_GAP_TERMS)
    specific_target = bool(
        re.search(r"(?:股份|集团|科技|电子|能源|公司|个股|股票|\d{6})", query)
    )
    deep_owner = (
        question_type in _L3_OWNER_TYPES
        and (
            question_type == "valuation_estimate"
            or (
                getattr(question_plan, "depth", "standard") == "deep"
                and specific_target
            )
        )
    )
    if not (asks_hard_fact or deep_owner):
        return False
    local = str(local_evidence_text or "")
    return not any(term in local for term in _L3_HARD_SOURCE_TERMS)


def collect_l3_official(
    ctx: EvidenceContext,
    *,
    company_evidence_concepts: dict[str, str],
    local_evidence_text: str,
) -> list[str]:
    """L：runtime L3 官方证据补查（公告/互动易），产出追加进 evidence_chain 的行。"""
    options = ctx.options
    anchor = ctx.anchor
    question_plan = ctx.question_plan
    chain_lines: list[str] = []
    if not should_request_l3_lookup(
        options=options,
        question_plan=question_plan,
        local_evidence_text=local_evidence_text,
    ):
        return chain_lines
    l3_bundle = l3_evidence.lookup_l3_evidence(
        options.query,
        question_plan,
        local_evidence_text,
        config=l3_evidence.L3LookupConfig.from_env(
            enabled=True,
            timeout=ctx.stage_timeout(options.l3_lookup_timeout),
            limit=options.l3_lookup_limit,
        ),
        company_hint=anchor.entity if anchor is not None else None,
    )
    ctx.result.l3_evidence = l3_bundle
    ctx.result.warnings.extend(f"l3-evidence：{w}" for w in l3_bundle.warnings)
    chain_lines.extend(l3_bundle.to_prompt_block().splitlines())
    for index, item in enumerate(l3_bundle.items, start=1):
        company = next(
            (
                name
                for name in company_evidence_concepts
                if name in f"{item.title} {item.summary}"
            ),
            anchor.entity if anchor is not None else None,
        )
        if company is None and question_plan.question_type == QUESTION_STOCK_DEEP_DIVE:
            company = _company_name_from_official_title(item.title)
        if company and not any(
            candidate.company == company for candidate in ctx.company_candidates
        ):
            ctx.company_candidates.append(
                answer_model.CompanyCandidate(
                    company=company,
                    directness="研究对象",
                    requested_tier=answer_model.CompanyTier.CANDIDATE,
                )
            )
        ctx.structured_claims.append(
            answer_model.make_claim(
                claim_id=f"official:L{index}",
                text=f"{item.title}：{item.summary}",
                claim_type="company_evidence" if company else "theme_evidence",
                theme=ctx.claim_theme,
                status=answer_model.ClaimStatus.VERIFIED,
                evidence_tier="L3",
                company=company,
                evidence_ids=(f"L{index}",),
            )
        )
    return chain_lines


def collect_web_fallback(
    ctx: EvidenceContext,
    *,
    local_lines_empty: bool,
) -> tuple[list[str], bool]:
    """E：外部 Web 检索兜底（仅 general lane 且本地证据全空时触发）。"""
    web_fallback_lines: list[str] = []
    web_fallback_attempted = False
    if (
        ctx.question_plan.question_type == QUESTION_GENERAL
        and local_lines_empty
    ):
        web_fallback_attempted = True
        web_result = web_research.fetch_web_search(ctx.options.query)
        ctx.result.provider_traces.append(web_result.trace)
        for item in web_result.items[:4]:
            tag = ctx.cite("E", item.title, item.url)
            line = (
                f"{item.title}：{item.snippet or '搜索结果未提供摘要'}（外部快照，仅作背景线索） {tag}"
            )
            web_fallback_lines.append(line)
            # P0 修复：兜底证据同步铸 CANDIDATE claim 进 registry——否则它只在
            # 证据链展示层出现，合成层在白名单契约下无法合法引用（死证据）。
            ctx.structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"web:{tag.strip('[]')}",
                    text=line,
                    claim_type="theme_evidence",
                    theme=ctx.claim_theme,
                    status=answer_model.ClaimStatus.CANDIDATE,
                    evidence_tier="external_web_snapshot",
                )
            )
    return web_fallback_lines, web_fallback_attempted


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


# 交给模型挑之前先摆多少家候选。太窄等于把取舍又还给确定性排序，太宽会把
# prompt 撑大且拖慢关键路径。实测「固态电池」全量 86 家，60 家已覆盖到
# peripheral 档尾部；更长尾的题材本来也不该指望模型从几百家里挑。
_SELECTOR_POOL = 60


def _select_exposures_by_intent(
    ctx: EvidenceContext,
    options: Any,
    knowledge: Any,
    ordered: list[dict[str, Any]],
    exposures: dict[str, Any],
) -> list[dict[str, Any]]:
    """按问题意图重排候选：模型挑中的提到最前，其余保持确定性顺序跟在后面。

    返回的是**重排过的宽表**而不是截好的 12 家——截断留给调用方统一做，
    这样 focus_entities 的置顶逻辑仍能在完整候选里找到它要的公司。

    结果和降级原因都写进 ``exposures['selector']``，一路进 trace——降级了但没人
    知道为什么，就是这轮一直在治的那个病。
    """
    if exposure_selector.selector_mode() == "off":
        exposures["selector"] = {
            "mode": "deterministic",
            "reason": "selector_off",
            "candidate_count": 0,
        }
        return ordered
    # 重新宽召回一次。relations 走带 stat 校验的进程内缓存，这一次不读盘。
    pool = knowledge.get_exposure_matches(ctx.graph_query, limit=_SELECTOR_POOL)
    candidates = list(pool.get("items") or []) or ordered
    selection = exposure_selector.select_exposures(
        str(options.query or ""),
        candidates,
        options.top_companies,
    )
    exposures["selector"] = selection.telemetry
    if not selection.items:
        return ordered
    picked = {str(row.get("company") or "") for row in selection.items}
    rest = [
        row for row in candidates if str(row.get("company") or "") not in picked
    ]
    return list(selection.items) + rest


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
    if exposures.get("found"):
        ordered = list(exposures["items"])
        if exposures.get("truncated"):
            # 候选池装不下配额时，静态标注排不出「对这个问题谁最相关」——让模型挑。
            ordered = _select_exposures_by_intent(ctx, options, knowledge, ordered, exposures)
        if focus_entities:
            # focus_entities 是 research_spec 推导出的重点公司，永远钉在最前面。
            # 它一般只有三四家，填不满 top_companies——剩下的槽位才是选择器的战场，
            # 所以这两件事是叠加关系，不是二选一（本轮实测踩过：以为 focus 非空就
            # 该跳过选择器，结果 12 个槽位里有 8 个仍由公司名字典序决定）。
            focus_order = {
                company: index for index, company in enumerate(focus_entities)
            }
            # sort 是稳定的：非 focus 行的键完全相同，选择器排好的相对顺序不会被打乱。
            ordered.sort(
                key=lambda row: (
                    0 if str(row.get("company") or "") in focus_order else 1,
                    focus_order.get(str(row.get("company") or ""), len(focus_order)),
                )
            )
        # 这是**第二次**截断：adapter 已按 exposure_limit 截过一次，这里收窄到
        # top_companies。不同步 truncated 的话，下游会拿 adapter 那次的结论去描述
        # 一个更短的名单，把「少送了多少」说小。
        if len(ordered) > options.top_companies:
            exposures["items"] = ordered[: options.top_companies]
            exposures["truncated"] = True
        else:
            exposures["items"] = ordered
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


def _evidence_row_key(item: dict[str, Any]) -> str:
    return f"{item.get('target')}|{item.get('source')}|{item.get('evidence')}"


def _stale_replacement_pointer(item: dict[str, Any]) -> str:
    return str(item.get("superseded_by") or item.get("status_note") or "").strip()


def _stale_pointer_recency(item: dict[str, Any]) -> str:
    pointer = _stale_replacement_pointer(item)
    dates = _ISO_DATE.findall(pointer)
    if dates:
        return max(dates)
    return str(item.get("source_date") or "")


def _format_stale_bypass_note(target: str, items: list[dict[str, Any]]) -> str:
    newest = max(
        items,
        key=lambda item: (_stale_pointer_recency(item), _stale_replacement_pointer(item)),
    )
    pointer = _stale_replacement_pointer(newest)
    prefix = f"{target} 有 {len(items)} 条证据已被取代"
    if not pointer:
        return prefix[:_STALE_BYPASS_NOTE_MAX_CHARS]
    glue = "；最近新证据："
    room = _STALE_BYPASS_NOTE_MAX_CHARS - len(prefix) - len(glue)
    if room <= 1:
        return prefix[:_STALE_BYPASS_NOTE_MAX_CHARS]
    if len(pointer) > room:
        pointer = pointer[: room - 1] + "…"
    return prefix + glue + pointer


def _stale_edges_for_target(knowledge: Any, target: str) -> list[dict[str, Any]]:
    getter = getattr(knowledge, "get_stale_edges", None)
    if callable(getter):
        payload = getter(target)
        if isinstance(payload, dict):
            raw_items = payload.get("items") or []
        else:
            raw_items = payload or []
        return [item for item in raw_items if isinstance(item, dict)]
    try:
        payload = knowledge.get_evidence(
            target,
            concept=None,
            limit=10_000,
            include_invalidated=True,
        )
    except TypeError:
        payload = knowledge.get_evidence(target, limit=10_000)
    return [
        item
        for item in list((payload or {}).get("items") or [])
        if isinstance(item, dict) and evidence_status(item) in _STALE_EDGE_STATUSES
    ]


def _append_stale_bypass_notes(
    *,
    knowledge: Any,
    targets: list[str],
    seen_evidence: set[str],
    stale_notes: list[str],
) -> None:
    """每个 target 至多一行提醒；只计 top-8 窗外的 superseded/invalidated。"""
    for target in targets:
        outside = [
            item
            for item in _stale_edges_for_target(knowledge, target)
            if evidence_status(item) in _STALE_EDGE_STATUSES
            and _evidence_row_key(item) not in seen_evidence
        ]
        if not outside:
            continue
        stale_notes.append(_format_stale_bypass_note(target, outside))


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
    unique_targets = list(dict.fromkeys(t for t in targets if t))
    for target in unique_targets:
        # 图谱暴露绑的是实体登记概念袋里的一条（如 1.6T CPO），不是这条
        # 证据该用的题材。锚定实体若带这个 concept 去过滤，对不上就
        # found=False，整包被跳过，名额被盘面候选占满。
        concept = company_evidence_concepts.get(target)
        if anchor is not None and target == anchor.entity:
            concept = None
        ev = ctx.knowledge.get_evidence(
            target,
            concept=concept,
            limit=options.max_evidence,
        )
        if not ev.get("found"):
            continue
        for item in ev["items"]:
            key = _evidence_row_key(item)
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
                # 「被取代」是证据层面的真失效：有更新的同主体证据顶掉了它。
                mark = " ⚠️已被新证据取代"
            elif stale:
                # 旧 ≠ 失效。同一条旧证据在 logic_lifecycle 里可能是「旧逻辑唤醒」
                # （盘面重新触发，最高价值信号），也可能是「衰退观察」——区分它们
                # 的是盘面时序，不是日历天数，所以这里报生命周期阶段而非「过期」。
                #
                # ⚠️ 这个标记会拼进 line，而 line 紧接着要过下面的
                # research_brief.classify_evidence_line 做 L1-L4 分层：**文案里
                # 绝不能出现 _L4_TERMS 里的词**（涨停/新高/成交/盘面/信号/强势股…），
                # 否则这条知识证据被误判成 L4 盘面证据，audit.has_l4 翻 True，
                # build_counterevidence_plan 的反证就从「盘面未验证」跳到「拥挤度」。
                # 初版写「待盘面复核」正好踩中，被 golden answer 快照抓出来。
                # logic_lifecycle 的七个阶段名都不含这些词，可以直接用。
                mark = (
                    f" ｜{ctx.lifecycle_stage}"
                    if ctx.lifecycle_stage
                    else " ｜周期待判"
                )
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
                # 旧证据的处置由逻辑生命周期决定，不由天数决定：同样一条旧材料，
                # 盘面重新触发时它是「旧逻辑唤醒」的依据，盘面走弱时才是衰退信号。
                # 原文案「需复核是否被新数据证伪」预设了证伪方向，会把唤醒信号
                # 读成风险提示。
                if ctx.lifecycle_stage:
                    stale_notes.append(
                        f"{item.get('target')} 证据 {item.get('source_date')}｜"
                        f"该题材当前逻辑生命周期：{ctx.lifecycle_stage}；"
                        f"按盘面阶段而非天数判断这条是否仍然成立 {tag}"
                    )
                else:
                    stale_notes.append(
                        f"{item.get('target')} 证据 {item.get('source_date')}，"
                        f"距今超过 {options.stale_days} 天且本轮取不到题材盘面历史，"
                        f"需人工判断处于唤醒还是衰退 {tag}"
                    )
            if len(evidence_lines) >= options.max_evidence:
                break
        if len(evidence_lines) >= options.max_evidence:
            break

    _append_stale_bypass_notes(
        knowledge=ctx.knowledge,
        targets=unique_targets,
        seen_evidence=seen_evidence,
        stale_notes=stale_notes,
    )

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


def _apply_semantic_judge(
    ctx: EvidenceContext,
    loop: closed_loop_retrieval.ClosedLoopRetrievalResult,
    *,
    deadline: ResearchDeadline | None = None,
) -> None:
    """LLM 语义闸门：把词面重叠但语义无关的结论/反方召回移入 discarded。

    fail-open：judge 关闭或失败时不动任何桶（与原行为逐字一致）。
    """
    buckets = [*loop.conclusion, *loop.counter_clues]
    if (
        not buckets
        or not evidence_judge.should_judge()
        or (deadline is not None and deadline.expired)
    ):
        return
    timeout = (
        deadline.stage_timeout(evidence_judge.DEFAULT_TIMEOUT)
        if deadline is not None
        else evidence_judge.DEFAULT_TIMEOUT
    )
    verdict = evidence_judge.judge_relevance(
        ctx.options.query,
        [(item.hit.title, item.hit.excerpt) for item in buckets],
        timeout=max(0.001, timeout),
        deadline=(
            llm_refine.Deadline(deadline.expires_at)
            if deadline is not None
            else None
        ),
    )
    if verdict is None:
        return
    keep_indexes, reason = verdict
    dropped = [
        item for index, item in enumerate(buckets) if index not in keep_indexes
    ]
    if not dropped:
        return
    dropped_keys = {
        (item.aperture, item.hit.file_path, item.hit.best_chunk_id)
        for item in dropped
    }

    def _kept(
        items: list[closed_loop_retrieval.BucketedHit],
    ) -> list[closed_loop_retrieval.BucketedHit]:
        return [
            item
            for item in items
            if (item.aperture, item.hit.file_path, item.hit.best_chunk_id)
            not in dropped_keys
        ]

    loop.conclusion[:] = _kept(loop.conclusion)
    loop.counter_clues[:] = _kept(loop.counter_clues)
    loop.clues[:] = _kept(loop.clues)
    loop.discarded.extend(dropped)
    titles = "、".join(dict.fromkeys(item.hit.title for item in dropped))
    loop.diagnostics.append(
        f"语义闸门丢弃 {len(dropped)} 条词面重叠但语义无关的召回（{titles}）"
        + (f"：{reason}" if reason else "")
    )


def collect_wiki_rag(
    ctx: EvidenceContext,
    company_evidence_concepts: dict[str, str],
) -> WikiEvidence:
    """W：知识库 hybrid 向量召回（语义选页 → 读候选页正文作证据，含反方线索桶）。

    召回先过 closed-loop 词面闸门，再过 :mod:`evidence_judge` 语义闸门——词面
    重叠但语义无关的命中（问指数「支撑位」召回某公司「基本面支撑」）移入
    discarded 桶，不进结论/反方线索。
    """
    bundle = WikiEvidence()
    bundle.stats = {
        "attempted": bool(ctx.options.use_wiki_rag),
        "mode": ctx.options.wiki_rag_mode,
        "index": "full" if ctx.options.wiki_rag_index_dir else "structured",
    }
    if ctx.options.use_wiki_rag:
        wiki_stage_deadline = ResearchDeadline.from_timeout(
            ctx.stage_timeout(
                min(
                    closed_loop_retrieval.MAX_TOTAL_SECONDS,
                    ctx.options.wiki_rag_timeout,
                )
            )
        )

        def retrieve_with_stage_deadline(retrieval_query: str):
            return kb_rag.retrieve(
                retrieval_query,
                ctx.knowledge.resolved_wiki_root,
                k=ctx.options.wiki_rag_k,
                mode=ctx.options.wiki_rag_mode,
                timeout=max(
                    0.001,
                    wiki_stage_deadline.stage_timeout(
                        ctx.options.wiki_rag_timeout
                    ),
                ),
                excerpt_chars=ctx.options.wiki_rag_excerpt,
                budget_query=ctx.graph_query,
                index_dir=ctx.options.wiki_rag_index_dir,
                require_fresh=True,
                cache_scope=ctx.options.wiki_rag_cache_scope,
            )

        loop = closed_loop_retrieval.retrieve_closed_loop(
            ctx.graph_query,
            anchor=ctx.anchor,
            # 闭环的每次子查询共享同一个 stage deadline；不能在阶段只剩 2 秒时
            # 再拿 turn 根剩余时间启动一个 90 秒子进程。
            total_seconds=wiki_stage_deadline.remaining(),
            retrieve=retrieve_with_stage_deadline,
        )
        _apply_semantic_judge(
            ctx,
            loop,
            deadline=wiki_stage_deadline,
        )
        _, wiki_evidence_total_chars = kb_rag.evidence_budget_for_query(
            ctx.options.query,
            mode=ctx.options.wiki_rag_mode,
            index_kind=loop.telemetry.index_kind if loop.telemetry else "",
        )
        conclusion_hits = [item.hit for item in loop.conclusion]
        counter_hits = [item.hit for item in loop.counter_clues]
        if counter_hits:
            conclusion_budget = int(wiki_evidence_total_chars * 0.75)
            kb_rag.apply_total_llm_budget(conclusion_hits, conclusion_budget)
            kb_rag.apply_total_llm_budget(
                counter_hits,
                wiki_evidence_total_chars - conclusion_budget,
            )
        else:
            kb_rag.apply_total_llm_budget(
                conclusion_hits,
                wiki_evidence_total_chars,
            )
        ctx.result.closed_loop_retrieval = loop
        bundle.stats.update(
            {
                "ok": bool(loop.conclusion),
                "hits": len(loop.conclusion),
                "clues": len(loop.clues),
                "discarded": len(loop.discarded),
                "counter_clues": len(loop.counter_clues),
                "scores": [item.hit.score for item in loop.conclusion],
                "neighbor_hits": sum(
                    1 for item in loop.conclusion if item.hit.via_neighbor
                ),
                "pages": [item.hit.file_path for item in loop.conclusion],
                "warning": "；".join(loop.warnings),
                "diagnostics": list(loop.diagnostics),
                "attempts": loop.inspector_dict()["attempts"],
            }
        )
        ctx.result.wiki_rag_telemetry = loop.telemetry
        if loop.conclusion:
            ctx.result.found_wiki = True
            ctx.result.found_graph = True
            for bucketed in loop.conclusion:
                h = bucketed.hit
                nb = "·邻居扩展" if h.via_neighbor else ""
                section_ref = f"｜section={h.section}" if h.section else ""
                tag = ctx.cite(
                    "W",
                    f"knowledge-base · {h.file_path}",
                    (
                        f"closed-loop:{bucketed.aperture}｜{h.title}"
                        f"｜chunk={h.best_chunk_id}{section_ref}"
                        f"｜evidence_chunks={','.join(h.evidence_chunk_ids or (h.best_chunk_id,))}"
                        f"｜hash={h.content_hash[:12]}｜index={h.index_source_revision[:12]}"
                        f"｜freshness={h.index_freshness}"
                    ),
                    chunk_id=h.best_chunk_id,
                    content_hash=h.content_hash,
                    index_source_revision=h.index_source_revision,
                    index_freshness=h.index_freshness,
                )
                # 旧结论核验门：synthesis/briefings 页是历史判断而非当前事实，打〔历史基线〕
                # 标签供合成层按 prior 处理（引用前须用当下盘面核验，给四态对照）。
                baseline = (
                    "〔历史基线·仅作先验，须以当下盘面核验〕"
                    if _is_prior_conclusion_page(h.file_path)
                    else ""
                )
                line = (
                    f"{baseline}{h.title}（相关度 {round(h.score, 4)}{nb}）：{h.excerpt} {tag}"
                )
                llm_body = h.llm_evidence or h.excerpt
                llm_line = (
                    f"{baseline}{h.title}（相关度 {round(h.score, 4)}{nb}）：{llm_body} {tag}"
                )
                bundle.lines.append(line)
                bundle.llm_line_pairs.append((line, llm_line))
                matched_company = next(
                    (
                        company
                        for company in company_evidence_concepts
                        if company in line
                    ),
                    None,
                )
                ctx.structured_claims.append(
                    answer_model.make_claim(
                        claim_id=f"wiki:{tag.strip('[]')}",
                        text=line,
                        claim_type="company_evidence" if matched_company else "theme_evidence",
                        theme=ctx.claim_theme,
                        status=answer_model.ClaimStatus.CANDIDATE,
                        evidence_tier="wiki_candidate",
                        company=matched_company,
                        confidence=h.score,
                        freshness=h.index_freshness,
                    )
                )
        if loop.counter_clues:
            ctx.result.found_wiki = True
            for bucketed in loop.counter_clues:
                h = bucketed.hit
                section_ref = f"｜section={h.section}" if h.section else ""
                tag = ctx.cite(
                    "W",
                    f"knowledge-base · {h.file_path}",
                    (
                        f"closed-loop:counter｜{h.title}"
                        f"｜chunk={h.best_chunk_id}{section_ref}"
                        f"｜evidence_chunks={','.join(h.evidence_chunk_ids or (h.best_chunk_id,))}"
                        f"｜hash={h.content_hash[:12]}｜index={h.index_source_revision[:12]}"
                        f"｜freshness={h.index_freshness}"
                    ),
                    chunk_id=h.best_chunk_id,
                    content_hash=h.content_hash,
                    index_source_revision=h.index_source_revision,
                    index_freshness=h.index_freshness,
                )
                line = f"反方线索（待进一步核验）：{h.title}：{h.excerpt} {tag}"
                llm_line = (
                    f"反方线索（待进一步核验）：{h.title}：{h.llm_evidence or h.excerpt} {tag}"
                )
                bundle.counter_lines.append(line)
                bundle.llm_line_pairs.append((line, llm_line))
        ctx.result.warnings.extend(f"wiki-rag：{warning}" for warning in loop.warnings)
    return bundle

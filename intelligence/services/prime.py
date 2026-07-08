"""检索前置（prime）：每轮回答前必跑的编排层。

把「问题 → 自动查 checkpoint 校准 + 个人库（画像/亲和/纠偏/判断）+ 知识库图谱
（概念/暴露/证据）→ 拼成一段可直接前置到推理上下文的前缀」收口成一个只读、
可离线、默认不依赖 DuckDB/LLM 的入口。目标是把现有资产从「被动可查」变成
「主动条件化」——不再依赖 agent 记得去查。

设计约束：

- **只读**：不写任何台账文件，不碰 DuckDB 写进程；
- **快**：默认只读本地 JSON/JSONL + relations/*.json，可选 W（wiki 向量召回）
  须显式 ``--wiki-rag`` 开启，且任何一路失败只降级、不阻断；
- **可机读**：``--json`` 输出结构化结果，供 route.py / 上层 agent 编排调用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services import checkpoints as checkpoints_service
from intelligence.services import corrections as corrections_service
from intelligence.services import interactions as interactions_service
from intelligence.services import judgments as judgments_service
from intelligence.userspace import effective_profile, user_space

DEFAULT_TOP_CONCEPTS = 5
DEFAULT_TOP_COMPANIES = 8
DEFAULT_MAX_EVIDENCE = 6
DEFAULT_AFFINITY_TOP = 8
DEFAULT_CORRECTIONS_WINDOW = 5
DEFAULT_JUDGMENTS_WINDOW = 5
DEFAULT_WIKI_RAG_K = 4


@dataclass
class PrimeOptions:
    query: str
    user: str | None = None
    kb_wiki: str | Path | None = None
    top_concepts: int = DEFAULT_TOP_CONCEPTS
    top_companies: int = DEFAULT_TOP_COMPANIES
    max_evidence: int = DEFAULT_MAX_EVIDENCE
    affinity_top: int = DEFAULT_AFFINITY_TOP
    corrections_window: int = DEFAULT_CORRECTIONS_WINDOW
    judgments_window: int = DEFAULT_JUDGMENTS_WINDOW
    calibration_min_n: int = checkpoints_service.DEFAULT_CALIBRATION_MIN_N
    use_wiki_rag: bool = False
    wiki_rag_k: int = DEFAULT_WIKI_RAG_K
    wiki_rag_timeout: int = 30


@dataclass
class PrimeResult:
    query: str
    user: str = "default"
    calibration_lines: str = ""
    pending_recheck: int = 0
    affinity: list[dict[str, Any]] = field(default_factory=list)
    corrections_lines: str = ""
    judgments_lines: str = ""
    profile_focus: list[str] = field(default_factory=list)
    graph_concepts: list[dict[str, Any]] = field(default_factory=list)
    graph_companies: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    wiki_hits: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _match_terms(query: str) -> list[str]:
    return KnowledgeAdapter._search_terms(query)


def _query_hits(query: str, labels: list[str]) -> bool:
    terms = _match_terms(query)
    for label in labels:
        for term in terms:
            if KnowledgeAdapter._contains(term, label) or KnowledgeAdapter._contains(label, term):
                return True
    return False


def build_prime(options: PrimeOptions) -> PrimeResult:
    us = user_space(options.user)
    result = PrimeResult(query=options.query, user=us.user_id)

    # --- ① 校准（checkpoint 台账 → 你哪类判断靠谱/偏差） ---
    cal, warns = checkpoints_service.load_calibration(us.checkpoints_path, us.verdicts_path)
    result.warnings.extend(warns)
    result.calibration_lines = checkpoints_service.render_calibration_for_prompt(
        cal, min_n=options.calibration_min_n
    )
    cks, _ = checkpoints_service.load_checkpoints(us.checkpoints_path)
    vds, _ = checkpoints_service.load_verdicts(us.verdicts_path)
    result.pending_recheck = len(checkpoints_service.due_checkpoints(cks, vds))

    # --- ② 个人库：画像焦点 + 反馈亲和 + 纠偏原则 + 核心判断 ---
    profile, pwarns = effective_profile(us)
    result.warnings.extend(pwarns)
    for key in ("focus_themes", "watchlist"):
        values = profile.get(key)
        if isinstance(values, list):
            for v in values:
                if isinstance(v, dict):
                    v = v.get("theme") or v.get("name") or ""
                if str(v).strip():
                    result.profile_focus.append(str(v).strip())
    result.profile_focus = result.profile_focus[:12]

    records, iwarn = interactions_service.load_interactions(us.interactions_path)
    if iwarn:
        result.warnings.append(iwarn)
    affinity = interactions_service.compute_affinity(records)
    relevant = [a for a in affinity if _query_hits(options.query, [a.label])]
    rest = [a for a in affinity if a not in relevant]
    picked = (relevant + rest)[: options.affinity_top]
    result.affinity = [
        {"kind": a.kind, "label": a.label, "score": round(a.score, 2), "relevant": a in relevant}
        for a in picked
    ]

    crecs, cwarn = corrections_service.load_corrections(
        us.corrections_path, window=options.corrections_window
    )
    if cwarn:
        result.warnings.append(cwarn)
    result.corrections_lines = corrections_service.render_for_prompt(crecs)

    jrecs, jwarn = judgments_service.load_judgments(
        us.judgments_path, window=options.judgments_window
    )
    if jwarn:
        result.warnings.append(jwarn)
    relevant_j = [r for r in jrecs if _query_hits(options.query, [str(r.get("memo") or "")] + [str(t) for t in (r.get("themes") or [])] + [str(s) for s in (r.get("stocks") or [])])]
    result.judgments_lines = judgments_service.render_for_prompt(relevant_j or jrecs)

    # --- ③ 图谱：概念命中 + 公司暴露分层 + 证据（含时效标注由调用方判断） ---
    knowledge = KnowledgeAdapter(wiki_root=options.kb_wiki)
    concepts = knowledge.get_concept_matches(options.query, limit=options.top_concepts)
    result.graph_concepts = list(concepts.get("items") or [])
    exposures = knowledge.get_exposure_matches(options.query, limit=options.top_companies)
    result.graph_companies = list(exposures.get("items") or [])

    targets: list[str] = []
    for item in result.graph_concepts[:2]:
        targets.append(str(item.get("concept") or ""))
    for row in result.graph_companies[:3]:
        targets.append(str(row.get("company") or ""))
    targets.append(options.query)
    seen: set[str] = set()
    for target in dict.fromkeys(t for t in targets if t):
        ev = knowledge.get_evidence(target, limit=options.max_evidence)
        for item in ev.get("items") or []:
            key = f"{item.get('target')}|{item.get('source')}|{item.get('evidence')}"
            if key in seen:
                continue
            seen.add(key)
            result.evidence.append(item)
            if len(result.evidence) >= options.max_evidence:
                break
        if len(result.evidence) >= options.max_evidence:
            break

    # --- ④ 可选 W：wiki 向量语义召回（显式开启才跑，失败只降级） ---
    if options.use_wiki_rag:
        from intelligence.services import kb_rag

        rag = kb_rag.retrieve(
            options.query,
            options.kb_wiki,
            k=options.wiki_rag_k,
            timeout=options.wiki_rag_timeout,
        )
        if rag.warning:
            result.warnings.append(f"wiki-rag：{rag.warning}")
        result.wiki_hits = [
            {"page": hit.title or hit.page_id, "path": hit.file_path, "score": hit.score, "excerpt": hit.excerpt}
            for hit in (rag.hits or [])
        ]

    return result


def render_prefix(result: PrimeResult) -> str:
    """渲染成可直接前置到推理上下文的紧凑前缀（markdown）。"""
    lines: list[str] = [f"== 检索前置（prime · user={result.user}）=="]
    lines.append(f"问题：{result.query}")

    if result.calibration_lines:
        lines.append("")
        lines.append("【校准｜历史判断胜率】")
        lines.append(result.calibration_lines)
    if result.pending_recheck:
        lines.append(f"⚠ 有 {result.pending_recheck} 个可证伪点到期未回检（checkpoint due）")

    if result.profile_focus or result.affinity:
        lines.append("")
        lines.append("【个人库｜画像与近期关注】")
        if result.profile_focus:
            lines.append(f"画像焦点：{'、'.join(result.profile_focus)}")
        if result.affinity:
            parts = [
                f"{a['label']}({a['score']:+.1f}{'·相关' if a.get('relevant') else ''})"
                for a in result.affinity
            ]
            lines.append(f"反馈亲和：{'、'.join(parts)}")
    if result.corrections_lines:
        lines.append("【纠偏｜别再犯】")
        lines.append(result.corrections_lines)
    if result.judgments_lines:
        lines.append("【核心判断｜在此基础上往前推】")
        lines.append(result.judgments_lines)

    if result.graph_concepts or result.graph_companies or result.evidence:
        lines.append("")
        lines.append("【图谱｜知识库命中】")
        if result.graph_concepts:
            names = "、".join(f"{i['concept']}({i['score']})" for i in result.graph_concepts)
            lines.append(f"命中概念：{names}")
        if result.graph_companies:
            rows = "、".join(
                f"{r.get('company')}({r.get('ticker') or '—'}|{r.get('strength') or '?'}|{r.get('confidence') or '?'})"
                for r in result.graph_companies
            )
            lines.append(f"公司暴露：{rows}")
        for item in result.evidence:
            lines.append(
                f"- {item.get('target')}：{str(item.get('evidence'))[:80]}"
                f"（{item.get('source')}, {item.get('source_date') or '无日期'}, 质量 {item.get('confidence') or '?'}）"
            )

    if result.wiki_hits:
        lines.append("")
        lines.append("【W｜wiki 语义召回】")
        for hit in result.wiki_hits:
            lines.append(f"- {hit.get('page')}（{hit.get('score')}）：{str(hit.get('excerpt') or '')[:100]}")

    if result.warnings:
        lines.append("")
        lines.append("【降级提示】")
        for w in result.warnings:
            lines.append(f"- {w}")

    lines.append("")
    lines.append(
        "（以上为自动检索前缀：回答须以校准提示调节自信度、以图谱/证据为 grounding；"
        "证据不足时明说缺口，不编造。）"
    )
    return "\n".join(lines)


def result_to_dict(result: PrimeResult) -> dict[str, Any]:
    return {
        "query": result.query,
        "user": result.user,
        "calibration": result.calibration_lines,
        "pending_recheck": result.pending_recheck,
        "profile_focus": result.profile_focus,
        "affinity": result.affinity,
        "corrections": result.corrections_lines,
        "judgments": result.judgments_lines,
        "graph_concepts": result.graph_concepts,
        "graph_companies": result.graph_companies,
        "evidence": result.evidence,
        "wiki_hits": result.wiki_hits,
        "warnings": result.warnings,
        "prefix": render_prefix(result),
    }

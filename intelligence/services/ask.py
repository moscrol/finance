"""Unified multi-source `ask` over the local knowledge graph + market 盘面 snapshot.

This is a deterministic *retrieval skeleton*: it routes a query to the matching
theme candidate (盘面/S source, read from the committed
``market_feature_store/exports/*-theme-candidates.json`` snapshot) and to the
knowledge graph (G/R sources, read live from the cross-repo knowledge base
``wiki/relations/*.json`` via :class:`KnowledgeAdapter`), then assembles a fixed
six-section answer with numbered citations.

No external LLM is required. The 结论 / 交易含义 sections are template-generated
placeholders meant to be refined by an LLM downstream; every factual line carries
a ``[S#]/[G#]/[R#]`` citation back to its source.
"""

from __future__ import annotations

import glob
import json
import re
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.theme_modules import (
    MODULE_BRIEF,
    MODULE_REPLAY,
    route_modules,
    run_module,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORTS_DIR = REPO_ROOT / "market_feature_store" / "exports"

# Trade-date freshness threshold (calendar days) above which graph evidence is
# flagged as potentially stale. Stand-in for a real Temporal Facts layer.
DEFAULT_STALE_DAYS = 45


@dataclass(frozen=True)
class AskOptions:
    query: str
    date: str | None = None
    exports_dir: str | Path | None = None
    kb_wiki: str | Path | None = None
    top_companies: int = 12
    top_concepts: int = 6
    max_evidence: int = 8
    stale_days: int = DEFAULT_STALE_DAYS
    use_modules: bool = True
    modules: tuple[str, ...] | None = None
    module_timeout: int = 180


@dataclass
class Citation:
    tag: str  # e.g. "S1", "G2", "R3"
    source: str
    detail: str = ""


@dataclass
class AskResult:
    query: str
    trade_date: str | None
    matched_theme: str | None
    candidate_tier: str | None
    priority_score: float | None
    sections: dict[str, list[str]] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    found_market: bool = False
    found_graph: bool = False
    routed_modules: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.found_market and self.found_graph:
            return "PASS"
        if self.found_market or self.found_graph:
            return "WARN"
        return "FAIL"


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _contains(a: str, b: str) -> bool:
    na, nb = _normalize(a), _normalize(b)
    return bool(na and nb and (na in nb or nb in na))


def _resolve_exports_dir(exports_dir: str | Path | None) -> Path:
    if exports_dir:
        return Path(exports_dir).expanduser()
    return DEFAULT_EXPORTS_DIR


def load_theme_candidates(exports_dir: str | Path | None, date: str | None) -> dict[str, Any]:
    """Load a theme-candidates export. Defaults to the latest available date."""
    base = _resolve_exports_dir(exports_dir)
    if date:
        path = base / f"{date}-theme-candidates.json"
        if not path.exists():
            return {"found": False, "path": str(path), "warnings": [f"no export for {date}"], "doc": {}}
    else:
        matches = sorted(glob.glob(str(base / "*-theme-candidates.json")))
        if not matches:
            return {"found": False, "path": str(base), "warnings": ["no theme-candidates export found"], "doc": {}}
        path = Path(matches[-1])
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return {"found": False, "path": str(path), "warnings": [str(exc)], "doc": {}}
    return {"found": True, "path": str(path), "warnings": [], "doc": doc}


def _all_candidates(doc: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(doc.get("candidates"), list):
        return [c for c in doc["candidates"] if isinstance(c, dict)]
    out: list[dict[str, Any]] = []
    for key in ("deep_candidates", "watch_candidates", "long_tail_candidates"):
        for c in doc.get(key, []) or []:
            if isinstance(c, dict):
                out.append(c)
    return out


def match_candidate(query: str, doc: dict[str, Any]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = 0
    for cand in _all_candidates(doc):
        score = 0
        for key in ("canonical_concept", "market_theme"):
            name = cand.get(key)
            if not name:
                continue
            if _normalize(name) == _normalize(query):
                score = max(score, 100)
            elif _contains(query, str(name)):
                score = max(score, 60)
        for mc in cand.get("matched_concepts", []) or []:
            name = mc.get("concept") if isinstance(mc, dict) else None
            if name and _contains(query, str(name)):
                score = max(score, 30)
        if score > best_score:
            best_score, best = score, cand
    return best


def _evidence_is_stale(item: dict[str, Any], stale_days: int) -> bool:
    raw = str(item.get("source_date") or "")
    m = re.search(r"(\d{4})\D?(\d{2})\D?(\d{2})", raw)
    if not m:
        return False
    try:
        ev_date = date_cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return False
    return (date_cls.today() - ev_date).days > stale_days


def answer_query(options: AskOptions) -> AskResult:
    knowledge = KnowledgeAdapter(wiki_root=options.kb_wiki)
    loaded = load_theme_candidates(options.exports_dir, options.date)
    doc = loaded["doc"] if loaded["found"] else {}
    candidate = match_candidate(options.query, doc) if doc else None

    result = AskResult(
        query=options.query,
        trade_date=doc.get("trade_date"),
        matched_theme=(candidate or {}).get("canonical_concept") or (candidate or {}).get("market_theme"),
        candidate_tier=(candidate or {}).get("candidate_tier"),
        priority_score=(candidate or {}).get("priority_score"),
    )
    result.warnings.extend(loaded.get("warnings", []))
    result.found_market = candidate is not None

    citations: list[Citation] = []

    def cite(prefix: str, source: str, detail: str = "") -> str:
        n = sum(1 for c in citations if c.tag.startswith(prefix)) + 1
        tag = f"{prefix}{n}"
        citations.append(Citation(tag=tag, source=source, detail=detail))
        return f"[{tag}]"

    export_name = Path(loaded.get("path", "")).name

    # --- S: 盘面 from theme-candidates snapshot ---
    market_lines: list[str] = []
    if candidate:
        for sd in (candidate.get("score_detail") or [])[:5]:
            sig = sd.get("signal")
            sc = sd.get("score")
            reason = sd.get("reason", "")
            tag = cite("S", f"{export_name} · score_detail.{sig}", str(sd.get("source", "")))
            market_lines.append(f"信号 {sig}（{sc}）：{reason} {tag}")
        ctx = doc.get("market_context") or {}
        if ctx:
            caps = "、".join(
                f"{s.get('name')}({s.get('ratio')}%,{s.get('capacity_type')})"
                for s in (ctx.get("capacity_sectors") or [])[:3]
            )
            tag = cite("S", f"{export_name} · market_context")
            market_lines.append(
                f"市场环境：{ctx.get('market_stage')}，成交 {ctx.get('total_amount')}，"
                f"涨停 {ctx.get('limit_up')} / 跌停 {ctx.get('limit_down')}，容量前三 {caps} {tag}"
            )

    # --- G: graph (concepts + company tiers) from KB relations ---
    graph_concept_lines: list[str] = []
    concepts = knowledge.get_concept_matches(options.query, limit=options.top_concepts)
    if concepts.get("found"):
        result.found_graph = True
        names = "、".join(f"{i['concept']}({i['score']})" for i in concepts["items"])
        tag = cite("G", "knowledge-base · wiki/relations/concept_graph.json")
        graph_concept_lines.append(f"命中概念：{names} {tag}")

    company_lines: list[str] = []
    exposures = knowledge.get_exposure_matches(options.query, limit=options.top_companies)
    tiers: dict[str, list[str]] = {"core": [], "peripheral": [], "other": []}
    if exposures.get("found"):
        result.found_graph = True
        for row in exposures["items"]:
            strength = str(row.get("strength") or "").lower()
            conf = str(row.get("confidence") or "")
            layer = str(row.get("evidence_layer") or "")
            label = f"{row.get('company')}({row.get('ticker')}|{row.get('role') or '—'}|{conf or '?'}/{layer or '?'})"
            if strength in {"core", "strong"} or conf in {"high"}:
                tiers["core"].append(label)
            elif strength in {"peripheral", "weak"} or layer in {"graph_only"}:
                tiers["peripheral"].append(label)
            else:
                tiers["other"].append(label)
        tag = cite("G", "knowledge-base · wiki/relations/entity_exposures.json")
        if tiers["core"]:
            company_lines.append(f"核心层：{'、'.join(tiers['core'])} {tag}")
        if tiers["other"]:
            company_lines.append(f"中间层：{'、'.join(tiers['other'])} {tag}")
        if tiers["peripheral"]:
            company_lines.append(f"外围/弱关联层：{'、'.join(tiers['peripheral'])} {tag}")

    # --- R: evidence from KB evidence_index (+ candidate snapshot) + staleness ---
    evidence_lines: list[str] = []
    stale_notes: list[str] = []
    seen_evidence: set[str] = set()
    targets: list[str] = []
    if result.matched_theme:
        targets.append(result.matched_theme)
    targets.append(options.query)
    for label in tiers["core"][:3]:
        targets.append(label.split("(")[0])
    for target in dict.fromkeys(t for t in targets if t):
        ev = knowledge.get_evidence(target, limit=options.max_evidence)
        if not ev.get("found"):
            continue
        for item in ev["items"]:
            key = f"{item.get('target')}|{item.get('source')}|{item.get('evidence')}"
            if key in seen_evidence:
                continue
            seen_evidence.add(key)
            result.found_graph = True
            stale = _evidence_is_stale(item, options.stale_days)
            tag = cite(
                "R",
                "knowledge-base · wiki/relations/evidence_index.json",
                f"target={item.get('target')} source={item.get('source')}",
            )
            mark = " ⚠️过期" if stale else ""
            line = (
                f"{item.get('target')}：{str(item.get('evidence'))[:80]}"
                f"（{item.get('source')}, {item.get('source_date') or '无日期'}, "
                f"质量 {item.get('confidence') or '?'}{mark}） {tag}"
            )
            evidence_lines.append(line)
            if stale:
                stale_notes.append(
                    f"{item.get('target')} 证据 {item.get('source_date')} 已超 {options.stale_days} 天，需复核是否被新数据证伪 {tag}"
                )
            if len(evidence_lines) >= options.max_evidence:
                break
        if len(evidence_lines) >= options.max_evidence:
            break

    # candidate-embedded knowledge_evidence as cross-check
    for ke in (candidate or {}).get("knowledge_evidence", []) or []:
        src = ke.get("source")
        key = f"{ke.get('target')}|{src}"
        if not src or key in seen_evidence:
            continue
        seen_evidence.add(key)
        tag = cite("R", f"{export_name} · knowledge_evidence")
        evidence_lines.append(
            f"{ke.get('target')}：{src}（质量 {ke.get('quality') or '?'}，盘面候选携带） {tag}"
        )

    # --- 模块 fan-out: route query to theme-radar 模式 as recall backends ---
    module_block: list[str] = []
    module_follow_ups: list[str] = []
    module_summ: list[str] = []
    if options.use_modules:
        routed = route_modules(options.query, list(options.modules) if options.modules else None)
        result.routed_modules = list(routed)
        label = {
            MODULE_BRIEF: "brief（产业维 · radar.py --mode brief）",
            MODULE_REPLAY: "replay（时间维 · 模块7 发酵复盘）",
        }
        for name in routed:
            mr = run_module(name, options.query, options.kb_wiki, options.module_timeout)
            module_block.append(f"{SUBHEAD}模块·{label.get(name, name)}")
            if mr.ok and mr.highlights:
                result.found_graph = True
                tag = cite("G", mr.citation_source, f"{mr.command}" + (f" | {mr.citation_detail}" if mr.citation_detail else ""))
                for hl in mr.highlights:
                    module_block.append(f"{hl} {tag}")
                module_follow_ups.extend(mr.follow_ups)
                if name == MODULE_BRIEF and mr.title:
                    module_summ.append(f"产业维定锚「{mr.title[:24]}…」")
                elif name == MODULE_REPLAY and mr.title:
                    module_summ.append(f"时间维发酵阶段「{mr.title}」")
            else:
                reason = mr.warning or "无产出"
                module_block.append(f"（{name} 模块未接入产出：{reason}）")
                result.warnings.append(f"模块 {name}：{reason}")

    # --- gaps / contradictions ---
    gap_lines: list[str] = []
    ks = (candidate or {}).get("knowledge_status") or {}
    gaps = ks.get("backfill_gaps") or []
    if gaps:
        gap_lines.append(f"盘面候选标记缺口：{'、'.join(map(str, gaps))}（图谱覆盖不足，证据待补）")
    if not result.found_graph:
        gap_lines.append("知识图谱未命中该词：可能是新词/别名未登记，建议先 concept-ingest 或 disclosure-archive 补证")
    if tiers["peripheral"]:
        gap_lines.append(
            f"{len(tiers['peripheral'])} 家公司为 graph_only/低置信暴露，属预期差待证伪区，不宜直接作为基本面依据"
        )
    gap_lines.extend(stale_notes)
    gap_lines.append(
        "Temporal Facts 层尚未接入：以上证据仅按 source_date 标注新鲜度；"
        "正式版应把会过期/被证伪的事实建成带 status(active/superseded/invalidated) 的时序边"
    )

    # ---------- assemble fixed six sections ----------
    theme = result.matched_theme or options.query
    triggers = "、".join((candidate or {}).get("trigger_types", []) or []) or "无盘面触发"
    concept_count = ks.get("concept_count", len(concepts.get("items", [])))
    exposure_count = ks.get("exposure_count", len(exposures.get("items", [])))

    stance_bits = []
    trig = set((candidate or {}).get("trigger_types", []) or [])
    if {"double_red"} & trig:
        stance_bits.append("板块双红（涨幅+边际量齐升）")
    if {"new_high_cluster", "new_high_direction"} & trig:
        stance_bits.append("新高成簇，方向被确认")
    if {"limit_advance_cluster", "limit_heat"} & trig:
        stance_bits.append("涨停热度集中")
    if gaps or not result.found_graph:
        stance_bits.append("但基本面证据不足，偏盘面驱动")
    stance = "；".join(stance_bits) if stance_bits else "盘面信号有限"

    conclusion = [
        f"主题「{theme}」"
        + (
            f"（{result.candidate_tier or '候选'}，盘面评分 {result.priority_score}，所属 {(candidate or {}).get('sw_l1', '?')}）"
            if candidate
            else "（当日盘面候选未命中，以下仅基于知识图谱）"
        )
        + f"：{stance}。",
        f"图谱命中 {concept_count} 概念 / {exposure_count} 公司暴露，证据 {len(evidence_lines)} 条；盘面触发：{triggers}。",
        "模块路由："
        + ("、".join(result.routed_modules) if result.routed_modules else "未启用")
        + ("｜" + "；".join(module_summ) if module_summ else ""),
        "（注：结论与交易含义为模板化骨架，待接 LLM 精修；证据链/分歧/模块召回为真实检索结果。）",
    ]

    follow_ups: list[str] = []
    if "double_red" in trig:
        follow_ups.append("跟踪边际量能否连续 ≥2 日维持（双红是否衰减）")
    if {"new_high_cluster", "new_high_direction"} & trig:
        follow_ups.append("观察高位股能否带动补涨扩散，还是仅龙头孤军")
    if {"limit_heat", "limit_advance_cluster"} & trig:
        follow_ups.append("看连板高度与晋级率，确认资金接力意愿")
    if gaps or tiers["peripheral"]:
        follow_ups.append("对 graph_only / 缺口公司补研报与官方披露（disclosure-archive → apply）")
    for item in module_follow_ups:
        follow_ups.append(f"[replay] {item}")
    if not follow_ups:
        follow_ups.append("补充盘面与基本面证据后再评估")

    tier = (result.candidate_tier or "").lower()
    if "deep" in tier:
        implication = "盘面属核心候选：若起涨龙头已高位，重点在低位补涨与上游；缺口公司仅作观察。"
    elif "watch" in tier:
        implication = "盘面属观察候选：等量价进一步确认或证据补齐再参与。"
    elif candidate:
        implication = "盘面属长尾候选：信号弱，暂列观察，不主动参与。"
    else:
        implication = "当日盘面未触发：以图谱认知储备为主，等待盘面信号出现。"
    implication += "（非投资建议，检索骨架输出。）"

    result.sections = {
        "结论": conclusion,
        "证据链": [f"{SUBHEAD}盘面"] + (market_lines or ["（当日无盘面候选命中）"])
        + [f"{SUBHEAD}图谱·概念"] + (graph_concept_lines or ["（图谱未命中概念）"])
        + [f"{SUBHEAD}图谱·公司分层"] + (company_lines or ["（图谱未命中公司暴露）"])
        + [f"{SUBHEAD}证据"] + (evidence_lines or ["（evidence_index 未命中）"])
        + module_block,
        "分歧反证": gap_lines,
        "后续验证点": follow_ups,
        "交易含义": [implication],
        "引用来源": [f"[{c.tag}] {c.source}" + (f" — {c.detail}" if c.detail else "") for c in citations],
    }
    result.citations = citations
    return result


SUBHEAD = "\x00SUB\x00"
SECTION_ORDER = ["结论", "证据链", "分歧反证", "后续验证点", "交易含义", "引用来源"]


def render_answer(result: AskResult) -> str:
    lines: list[str] = []
    lines.append(f"# ask：{result.query}")
    meta = [
        f"盘面日期={result.trade_date or '—'}",
        f"命中主题={result.matched_theme or '—'}",
        f"模块路由={'/'.join(result.routed_modules) or '—'}",
        f"召回状态={result.status}",
    ]
    lines.append("> " + " | ".join(meta))
    if result.warnings:
        lines.append("> 警告：" + "；".join(result.warnings))
    for name in SECTION_ORDER:
        lines.append("")
        lines.append(f"## 【{name}】")
        for item in result.sections.get(name, []):
            if item.startswith(SUBHEAD):
                lines.append(f"\n*{item[len(SUBHEAD):]}*")
            else:
                lines.append(f"- {item}")
    return "\n".join(lines) + "\n"

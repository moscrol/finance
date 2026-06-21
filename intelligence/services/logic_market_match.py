from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.ask import load_theme_candidates, match_candidate


LABEL_OLD_WAKEUP = "old_logic_wakeup"
LABEL_NEW_CANDIDATE = "new_logic_candidate"
LABEL_NOISE = "noise_or_unconfirmed"
LABEL_DATA_GAP = "data_gap"


@dataclass
class SourceTrace:
    source: str
    source_name: str = ""
    source_exists: bool = False
    source_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_name": self.source_name,
            "source_exists": self.source_exists,
            "source_path": self.source_path,
        }


@dataclass
class LogicMarketMatchResult:
    query: str
    date: str | None
    classification: str
    confidence: float
    market_found: bool
    matched_theme: str = ""
    market_theme: str = ""
    priority_score: float | None = None
    trigger_types: list[str] = field(default_factory=list)
    strong_stocks: list[dict[str, Any]] = field(default_factory=list)
    concept_matches: list[dict[str, Any]] = field(default_factory=list)
    entity_exposures: list[dict[str, Any]] = field(default_factory=list)
    evidence_items: list[dict[str, Any]] = field(default_factory=list)
    source_traces: list[SourceTrace] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "date": self.date,
            "classification": self.classification,
            "confidence": self.confidence,
            "market_found": self.market_found,
            "matched_theme": self.matched_theme,
            "market_theme": self.market_theme,
            "priority_score": self.priority_score,
            "trigger_types": self.trigger_types,
            "strong_stocks": self.strong_stocks,
            "concept_matches": self.concept_matches,
            "entity_exposures": self.entity_exposures,
            "evidence_items": self.evidence_items,
            "source_traces": [item.to_dict() for item in self.source_traces],
            "data_gaps": self.data_gaps,
            "next_actions": self.next_actions,
            "warnings": self.warnings,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def source_name_from_ref(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"\[\[([^\]]+)\]\]", text)
    if match:
        return match.group(1).strip()
    return text.strip()


def check_source_trace(wiki_root: Path, evidence_items: list[dict[str, Any]]) -> list[SourceTrace]:
    traces: list[SourceTrace] = []
    seen = set()
    for item in evidence_items:
        source = str(item.get("source") or item.get("source_name") or "").strip()
        if not source or source in seen:
            continue
        seen.add(source)
        source_name = source_name_from_ref(source)
        source_path = wiki_root / "sources" / f"{source_name}.md"
        traces.append(
            SourceTrace(
                source=source,
                source_name=source_name,
                source_exists=source_path.exists(),
                source_path=str(source_path),
            )
        )
    return traces


def _candidate_theme(candidate: dict[str, Any] | None, fallback: str) -> str:
    if not candidate:
        return fallback
    return str(candidate.get("canonical_concept") or candidate.get("market_theme") or fallback)


def _strong_stocks(candidate: dict[str, Any] | None, limit: int) -> list[dict[str, Any]]:
    if not candidate:
        return []
    market_evidence = candidate.get("market_evidence") if isinstance(candidate.get("market_evidence"), dict) else {}
    stocks = market_evidence.get("strong_stocks", []) if isinstance(market_evidence, dict) else []
    out = []
    for row in stocks[:limit]:
        if not isinstance(row, dict):
            continue
        out.append({
            "stock_name": row.get("stock_name") or row.get("name") or "",
            "stock_ts_code": row.get("stock_ts_code") or row.get("code") or "",
            "pct_chg": row.get("pct_chg"),
            "amount": row.get("amount"),
            "high_status_label": row.get("high_status_label"),
        })
    return out


def _score(market_found: bool, concept_count: int, exposure_count: int, evidence_count: int, trace_missing: int) -> float:
    score = 0.0
    if market_found:
        score += 0.35
    if concept_count:
        score += 0.2
    if exposure_count:
        score += 0.2
    if evidence_count:
        score += 0.2
    if trace_missing:
        score -= min(0.15, trace_missing * 0.05)
    return max(0.05, min(0.95, round(score, 2)))


def _classify(market_found: bool, concept_count: int, exposure_count: int, evidence_count: int, gaps: list[str]) -> str:
    if market_found and concept_count and exposure_count and evidence_count:
        return LABEL_OLD_WAKEUP
    if market_found and gaps:
        return LABEL_DATA_GAP
    if market_found:
        return LABEL_NEW_CANDIDATE
    if concept_count or exposure_count or evidence_count:
        return LABEL_DATA_GAP
    return LABEL_NOISE


def _next_actions(classification: str, gaps: list[str]) -> list[str]:
    actions: list[str] = []
    if classification == LABEL_OLD_WAKEUP:
        actions.append("进入 front-map/deep-dive 验证发酵阶段与公司弹性。")
        actions.append("把强势股与已有 entity exposure 对齐，挑出需要跟踪的核心公司。")
    elif classification == LABEL_NEW_CANDIDATE:
        actions.append("先做 front-map 建立题材地图，再决定是否 deep-dive。")
    elif classification == LABEL_DATA_GAP:
        actions.append("先补影响当前判断的数据缺口，不做全库大扫除。")
    else:
        actions.append("暂不 deep-dive；等待更多盘面信号或证据。")
    if "missing_source_trace" in gaps:
        actions.append("优先补 source/raw trace，避免证据不可追溯。")
    if "missing_concept" in gaps:
        actions.append("先判断概念是新概念、别名还是污染词，再进入 concept backfill。")
    if "missing_entity_exposure" in gaps:
        actions.append("补 entity exposure 或 IMA 个股卡，确认哪些公司是真暴露。")
    if "missing_evidence" in gaps:
        actions.append("补公告/研报/订单/客户验证等 evidence，不要只靠市场叙事。")
    return actions


def match_logic_to_market(
    query: str,
    date: str | None = None,
    exports_dir: str | Path | None = None,
    kb_wiki: str | Path | None = None,
    top_companies: int = 12,
    max_evidence: int = 8,
) -> LogicMarketMatchResult:
    loaded = load_theme_candidates(exports_dir, date)
    doc = loaded["doc"] if loaded.get("found") else {}
    candidate = match_candidate(query, doc) if doc else None
    theme = _candidate_theme(candidate, query)

    knowledge = KnowledgeAdapter(wiki_root=kb_wiki)
    concept_result = knowledge.get_concept_matches(theme, limit=6)
    exposure_result = knowledge.get_exposure_matches(theme, limit=top_companies)
    evidence_result = knowledge.get_evidence(theme, limit=max_evidence)

    concepts = concept_result.get("items", [])
    exposures = exposure_result.get("items", [])
    evidence = evidence_result.get("items", [])
    wiki_root = knowledge.resolved_wiki_root
    traces = check_source_trace(wiki_root, evidence)

    gaps: list[str] = []
    if not candidate:
        gaps.append("missing_market_signal")
    if not concepts:
        gaps.append("missing_concept")
    if not exposures:
        gaps.append("missing_entity_exposure")
    if not evidence:
        gaps.append("missing_evidence")
    if any(not trace.source_exists for trace in traces):
        gaps.append("missing_source_trace")

    classification = _classify(bool(candidate), len(concepts), len(exposures), len(evidence), gaps)
    confidence = _score(bool(candidate), len(concepts), len(exposures), len(evidence), sum(1 for trace in traces if not trace.source_exists))

    warnings = []
    warnings.extend(loaded.get("warnings", []))
    warnings.extend(concept_result.get("warnings", []))
    warnings.extend(exposure_result.get("warnings", []))
    warnings.extend(evidence_result.get("warnings", []))

    return LogicMarketMatchResult(
        query=query,
        date=str(doc.get("trade_date") or date or ""),
        classification=classification,
        confidence=confidence,
        market_found=bool(candidate),
        matched_theme=theme,
        market_theme=str((candidate or {}).get("market_theme") or ""),
        priority_score=(candidate or {}).get("priority_score"),
        trigger_types=list((candidate or {}).get("trigger_types") or []),
        strong_stocks=_strong_stocks(candidate, top_companies),
        concept_matches=concepts,
        entity_exposures=exposures,
        evidence_items=evidence,
        source_traces=traces,
        data_gaps=gaps,
        next_actions=_next_actions(classification, gaps),
        warnings=warnings,
    )


def render_match(result: LogicMarketMatchResult) -> str:
    lines = [
        f"# Logic Market Match - {result.query}",
        "",
        f"- Classification: `{result.classification}`",
        f"- Confidence: {result.confidence:.2f}",
        f"- Date: {result.date or '-'}",
        f"- Market found: {result.market_found}",
        f"- Matched theme: {result.matched_theme or '-'}",
        f"- Priority score: {result.priority_score if result.priority_score is not None else '-'}",
        f"- Data gaps: {', '.join(result.data_gaps) or '-'}",
        "",
        "## Market Signals",
        "",
        f"- Trigger types: {', '.join(result.trigger_types) or '-'}",
    ]
    for row in result.strong_stocks[:10]:
        lines.append(
            f"- {row.get('stock_name')} {row.get('stock_ts_code')}｜涨跌幅 {row.get('pct_chg')}｜成交 {row.get('amount')}｜{row.get('high_status_label') or '-'}"
        )
    lines.extend(["", "## Knowledge Matches", ""])
    lines.append(f"- Concepts: {len(result.concept_matches)}")
    for row in result.concept_matches[:6]:
        lines.append(f"- {row.get('concept')}｜score={row.get('score')}")
    lines.append(f"- Entity exposures: {len(result.entity_exposures)}")
    for row in result.entity_exposures[:10]:
        lines.append(
            f"- {row.get('company')} {row.get('ticker')}｜{row.get('concept')}｜{row.get('strength') or '-'}｜{row.get('role') or '-'}"
        )
    lines.extend(["", "## Evidence", ""])
    lines.append(f"- Evidence items: {len(result.evidence_items)}")
    for row in result.evidence_items[:8]:
        evidence = str(row.get("evidence") or "").replace("\n", " ")
        lines.append(f"- {row.get('source') or '-'}｜{row.get('source_date') or '-'}｜{evidence[:120]}")
    lines.extend(["", "## Source Trace", ""])
    if result.source_traces:
        for trace in result.source_traces:
            status = "OK" if trace.source_exists else "MISSING"
            lines.append(f"- {status}｜{trace.source}｜`{trace.source_path}`")
    else:
        lines.append("- no evidence source")
    lines.extend(["", "## Next Actions", ""])
    for action in result.next_actions:
        lines.append(f"- {action}")
    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in result.warnings:
            lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)


from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.ask import DEFAULT_EXPORTS_DIR, load_theme_candidates, match_candidate
from intelligence.services.claim_lineage import resolve_candidate_lineage


LABEL_OLD_WAKEUP = "old_logic_wakeup"
LABEL_NEW_CANDIDATE = "new_logic_candidate"
LABEL_NOISE = "noise_or_unconfirmed"
LABEL_DATA_GAP = "data_gap"
PLACEHOLDER_MARKET_GAP = "placeholder_market_theme"


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
    market_evidence: dict[str, Any] = field(default_factory=dict)
    market_evidence_lineage: dict[str, dict[str, object]] = field(default_factory=dict)
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
            "market_evidence": self.market_evidence,
            "market_evidence_lineage": self.market_evidence_lineage,
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


@dataclass
class GapQueueItem:
    date: str
    query: str
    classification: str
    priority: float
    market_priority_score: float | None
    data_gaps: list[str]
    matched_theme: str
    trigger_types: list[str]
    strong_stocks: list[str]
    next_actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "query": self.query,
            "classification": self.classification,
            "priority": self.priority,
            "market_priority_score": self.market_priority_score,
            "data_gaps": self.data_gaps,
            "matched_theme": self.matched_theme,
            "trigger_types": self.trigger_types,
            "strong_stocks": self.strong_stocks,
            "next_actions": self.next_actions,
        }


@dataclass
class LogicMatchBatchResult:
    dates: list[str]
    scanned_count: int
    results: list[LogicMarketMatchResult]
    gap_queue: list[GapQueueItem]
    summary: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dates": self.dates,
            "scanned_count": self.scanned_count,
            "summary": self.summary,
            "gap_queue": [item.to_dict() for item in self.gap_queue],
            "results": [item.to_dict() for item in self.results],
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


def _is_placeholder_market_theme(*values: Any) -> bool:
    text = " ".join(str(value or "") for value in values)
    return any(marker in text for marker in ("未映射", "未命名题材", "待映射"))


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


# 四分类的中文表述。
#
# ⚠️ 这些文案会拼进 ask 的证据段，而证据行紧接着要过
# ``research_brief.classify_evidence_line`` 做 L1-L4 分层：**文案里不得出现
# ``research_brief._L4_TERMS`` 里的任何词**（涨停/新高/双红/边际量/成交/量能/
# 相对强度/涨跌家数/MA5/盘面/信号/市场环境/容量前三/连板/强势股），否则这条知识
# 证据会被误判成 L4 盘面证据，``audit.has_l4`` 翻 True，
# ``build_counterevidence_plan`` 的反证从「盘面未验证」跳成「拥挤度」——纯文案改动
# 穿过分类器改变风险结论。
#
# 「信号」正是 _L4_TERMS 成员，所以 noise 档取「未确认线索」而不是「待确认信号」；
# 报表侧的 badge 文案（api/daily_reports、workbench_skills）不过分类器，保持原样。
CLASSIFICATION_LABELS: dict[str, str] = {
    LABEL_OLD_WAKEUP: "旧逻辑重新活跃",
    LABEL_NEW_CANDIDATE: "新逻辑候选",
    LABEL_DATA_GAP: "数据待补",
    LABEL_NOISE: "未确认线索",
}


@dataclass
class LogicMatchVerdict:
    """一次「盘面 × 知识」四分类的裁定；不含检索结果本身。"""

    classification: str
    label: str
    confidence: float
    data_gaps: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "label": self.label,
            "confidence": self.confidence,
            "data_gaps": self.data_gaps,
            "next_actions": self.next_actions,
        }


def derive_data_gaps(
    market_found: bool,
    concept_count: int,
    exposure_count: int,
    evidence_count: int,
    trace_missing: int = 0,
) -> list[str]:
    """由检索计数推出数据缺口；``match_logic_to_market`` 与 ask/agent 共用同一实现。"""
    gaps: list[str] = []
    if not market_found:
        gaps.append("missing_market_signal")
    if not concept_count:
        gaps.append("missing_concept")
    if not exposure_count:
        gaps.append("missing_entity_exposure")
    if not evidence_count:
        gaps.append("missing_evidence")
    if trace_missing:
        gaps.append("missing_source_trace")
    return gaps


def classify_market_logic(
    market_found: bool,
    concept_count: int,
    exposure_count: int,
    evidence_count: int,
    trace_missing: int = 0,
) -> LogicMatchVerdict:
    """用**已经算好的**检索计数做四分类，不再自己跑一遍 KB 检索。

    这是 ask / agent 接入四分类的入口：两条路径已经各自检索过概念、暴露和证据，
    再调 ``match_logic_to_market`` 会把同样的检索重跑一遍（而且它自带的
    ``load_theme_candidates`` 会覆盖调用方已匹配到的 candidate）。判据仍归本模块
    单点所有——``_classify`` / ``_score`` / ``_next_actions`` 三个函数是唯一实现，
    调用方只传计数，不复制阈值。
    """
    gaps = derive_data_gaps(
        market_found, concept_count, exposure_count, evidence_count, trace_missing
    )
    classification = _classify(
        market_found, concept_count, exposure_count, evidence_count, gaps
    )
    return LogicMatchVerdict(
        classification=classification,
        label=CLASSIFICATION_LABELS.get(classification, classification),
        confidence=_score(
            market_found, concept_count, exposure_count, evidence_count, trace_missing
        ),
        data_gaps=gaps,
        next_actions=_next_actions(classification, gaps),
    )


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
    if "placeholder_market_theme" in gaps:
        actions.append("这是盘面占位信号：先看连板股名单和主导行业，不做 concept deep-dive。")
        actions.append("等题材归因明确后，再映射到真实概念或标记为噪音。")
    elif classification == LABEL_OLD_WAKEUP:
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
    evidence_catalog = doc.get("evidence_catalog")
    candidate_lineage = resolve_candidate_lineage(
        candidate or {},
        evidence_catalog if isinstance(evidence_catalog, dict) else {},
    )

    if _is_placeholder_market_theme(
        query,
        theme,
        (candidate or {}).get("market_theme"),
        (candidate or {}).get("canonical_concept"),
    ):
        gaps = [PLACEHOLDER_MARKET_GAP]
        return LogicMarketMatchResult(
            query=query,
            date=str(doc.get("trade_date") or date or ""),
            classification=LABEL_NOISE,
            confidence=0.2,
            market_found=bool(candidate),
            matched_theme=theme,
            market_theme=str((candidate or {}).get("market_theme") or ""),
            priority_score=(candidate or {}).get("priority_score"),
            trigger_types=list((candidate or {}).get("trigger_types") or []),
            strong_stocks=_strong_stocks(candidate, top_companies),
            market_evidence=dict((candidate or {}).get("market_evidence") or {}),
            market_evidence_lineage=candidate_lineage,
            data_gaps=gaps,
            next_actions=_next_actions(LABEL_NOISE, gaps),
            warnings=list(loaded.get("warnings", [])),
        )

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
        market_evidence=dict((candidate or {}).get("market_evidence") or {}),
        market_evidence_lineage=candidate_lineage,
        concept_matches=concepts,
        entity_exposures=exposures,
        evidence_items=evidence,
        source_traces=traces,
        data_gaps=gaps,
        next_actions=_next_actions(classification, gaps),
        warnings=warnings,
    )


def available_candidate_dates(exports_dir: str | Path | None = None) -> list[str]:
    base = Path(exports_dir).expanduser() if exports_dir else DEFAULT_EXPORTS_DIR
    if not base.exists():
        return []
    dates = []
    for path in sorted(base.glob("*-theme-candidates.json")):
        match = re.match(r"(\d{4}-\d{2}-\d{2})-theme-candidates\.json$", path.name)
        if match:
            dates.append(match.group(1))
    return dates


def _candidate_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(doc.get("candidates"), list):
        return [row for row in doc["candidates"] if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    for key in ("deep_candidates", "watch_candidates", "long_tail_candidates"):
        rows.extend(row for row in doc.get(key, []) or [] if isinstance(row, dict))
    return rows


def _candidate_query(row: dict[str, Any]) -> str:
    return str(row.get("canonical_concept") or row.get("market_theme") or "").strip()


def _gap_priority(result: LogicMarketMatchResult) -> float:
    market_score = float(result.priority_score or 0.0)
    gap_weight = {
        "missing_source_trace": 35.0,
        "missing_evidence": 30.0,
        "missing_entity_exposure": 25.0,
        "missing_concept": 20.0,
        PLACEHOLDER_MARKET_GAP: 5.0,
        "missing_market_signal": 5.0,
    }
    weighted_gaps = sum(gap_weight.get(gap, 10.0) for gap in result.data_gaps)
    if result.classification == LABEL_NEW_CANDIDATE:
        weighted_gaps += 15.0
    if result.classification == LABEL_DATA_GAP:
        weighted_gaps += 20.0
    return round(market_score + weighted_gaps, 2)


def _gap_queue_item(result: LogicMarketMatchResult) -> GapQueueItem | None:
    if not result.data_gaps and result.classification == LABEL_OLD_WAKEUP:
        return None
    return GapQueueItem(
        date=str(result.date or ""),
        query=result.query,
        classification=result.classification,
        priority=_gap_priority(result),
        market_priority_score=result.priority_score,
        data_gaps=list(result.data_gaps),
        matched_theme=result.matched_theme,
        trigger_types=list(result.trigger_types),
        strong_stocks=[str(row.get("stock_name") or "") for row in result.strong_stocks[:5] if row.get("stock_name")],
        next_actions=list(result.next_actions),
    )


def batch_match_logic_to_market(
    dates: list[str] | None = None,
    recent: int = 5,
    top_per_date: int = 10,
    exports_dir: str | Path | None = None,
    kb_wiki: str | Path | None = None,
    top_companies: int = 8,
    max_evidence: int = 5,
) -> LogicMatchBatchResult:
    selected_dates = list(dates or [])
    if not selected_dates:
        selected_dates = available_candidate_dates(exports_dir)[-recent:]

    results: list[LogicMarketMatchResult] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for date in selected_dates:
        loaded = load_theme_candidates(exports_dir, date)
        if not loaded.get("found"):
            warnings.extend([f"{date}: {warning}" for warning in loaded.get("warnings", [])])
            continue
        rows = sorted(
            _candidate_rows(loaded.get("doc", {})),
            key=lambda row: float(row.get("priority_score") or 0.0),
            reverse=True,
        )[:top_per_date]
        for row in rows:
            query = _candidate_query(row)
            if not query:
                continue
            key = (date, query)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                match_logic_to_market(
                    query=query,
                    date=date,
                    exports_dir=exports_dir,
                    kb_wiki=kb_wiki,
                    top_companies=top_companies,
                    max_evidence=max_evidence,
                )
            )

    gap_queue = sorted(
        (item for item in (_gap_queue_item(result) for result in results) if item is not None),
        key=lambda item: (-item.priority, item.date, item.query),
    )
    classification_counts: dict[str, int] = {}
    gap_counts: dict[str, int] = {}
    for result in results:
        classification_counts[result.classification] = classification_counts.get(result.classification, 0) + 1
        for gap in result.data_gaps:
            gap_counts[gap] = gap_counts.get(gap, 0) + 1
    summary = {
        "classification_counts": classification_counts,
        "gap_counts": gap_counts,
        "gap_queue_count": len(gap_queue),
        "old_logic_wakeup_count": classification_counts.get(LABEL_OLD_WAKEUP, 0),
    }
    return LogicMatchBatchResult(
        dates=selected_dates,
        scanned_count=len(results),
        results=results,
        gap_queue=gap_queue,
        summary=summary,
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


def render_batch(result: LogicMatchBatchResult) -> str:
    lines = [
        "# Logic Market Match Batch",
        "",
        f"- Dates: {', '.join(result.dates) or '-'}",
        f"- Scanned candidates: {result.scanned_count}",
        f"- Gap queue: {len(result.gap_queue)}",
        "",
        "## Summary",
        "",
    ]
    for key, value in result.summary.get("classification_counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Gap Counts", ""])
    gap_counts = result.summary.get("gap_counts", {})
    if gap_counts:
        for key, value in sorted(gap_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- no gaps")
    lines.extend(["", "## Priority Gap Queue", ""])
    if result.gap_queue:
        lines.append("| Priority | Date | Query | Classification | Gaps | Strong Stocks | Next Action |")
        lines.append("|---:|---|---|---|---|---|---|")
        for item in result.gap_queue[:50]:
            lines.append(
                "| "
                f"{item.priority:.2f} | {item.date} | {item.query} | {item.classification} | "
                f"{', '.join(item.data_gaps) or '-'} | {', '.join(item.strong_stocks) or '-'} | "
                f"{item.next_actions[0] if item.next_actions else '-'} |"
            )
    else:
        lines.append("- no priority gaps")
    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in result.warnings:
            lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)

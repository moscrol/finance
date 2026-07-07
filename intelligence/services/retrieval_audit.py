"""检索审计台账（第三阶段最小版）：把每次 ask 的 query→命中→回答质量落成 JSONL.

对应 docs/learning/finance-agent-skill-expansion-brainstorm.md §五 第三阶段
（把 RAG 评估做成工程样板）的最小闭环：

- 每次回答追加一条审计记录：query / 问题类型 / 检索遥测（模式/索引/命中/
  分数/降级）/ 证据分层分布与裁定 / 市场结构阶段 / 是否失败样本
- 失败样本自动标记（检索全空、降级、证据不足、L3 缺失且弱证据），后续
  复盘时 `load_failure_samples` 直接捞出来做失败样本集
- 聚合统计 `summarize_ledger`：命中来源分布、L3 覆盖率、失败率 —— 是
  recall@k / 调参评估的原始数据底座

只追加本地 JSONL、不写知识库正文，不含任何交易指令。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.services.research_brief import DBlockStat, EvidenceAudit, RetrievalTelemetry

VERDICT_INSUFFICIENT = "证据不足"


@dataclass
class RetrievalAuditRecord:
    ts: str
    query: str
    question_type: str
    trade_date: str | None
    verdict: str
    layer_counts: dict[str, int]
    covers_l3: bool
    source_hits: dict[str, int]
    wiki_mode: str | None
    wiki_index: str | None
    wiki_hits: int
    wiki_top_score: float | None
    wiki_mean_score: float | None
    wiki_degraded: str | None
    wiki_pages: list[str] = field(default_factory=list)
    market_phase: str | None = None
    failure_tags: list[str] = field(default_factory=list)
    d_blocks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_failure(self) -> bool:
        return bool(self.failure_tags)

    def to_dict(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["is_failure"] = self.is_failure
        return doc


def _failure_tags(audit: EvidenceAudit, telemetry: RetrievalTelemetry) -> list[str]:
    tags: list[str] = []
    if not telemetry.source_hits:
        tags.append("empty_retrieval")
    if telemetry.wiki_degraded:
        tags.append("wiki_degraded")
    if audit.verdict == VERDICT_INSUFFICIENT:
        tags.append("insufficient_evidence")
    if not telemetry.covers_l3 and audit.layer_counts:
        tags.append("no_l3_coverage")
    return tags


def build_audit_record(
    *,
    query: str,
    question_type: str,
    trade_date: str | None,
    audit: EvidenceAudit,
    telemetry: RetrievalTelemetry,
    market_phase: str | None = None,
    d_block_stats: list[DBlockStat] | None = None,
) -> RetrievalAuditRecord:
    return RetrievalAuditRecord(
        ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        query=query,
        question_type=question_type,
        trade_date=trade_date,
        verdict=audit.verdict,
        layer_counts=dict(audit.layer_counts),
        covers_l3=telemetry.covers_l3,
        source_hits=dict(telemetry.source_hits),
        wiki_mode=telemetry.wiki_mode,
        wiki_index=telemetry.wiki_index,
        wiki_hits=telemetry.wiki_hits,
        wiki_top_score=telemetry.wiki_top_score,
        wiki_mean_score=telemetry.wiki_mean_score,
        wiki_degraded=telemetry.wiki_degraded,
        wiki_pages=list(getattr(telemetry, "wiki_pages", None) or []),
        market_phase=market_phase,
        failure_tags=_failure_tags(audit, telemetry),
        d_blocks=[s.to_dict() for s in (d_block_stats or [])],
    )


def append_record(ledger_path: str | Path, record: RetrievalAuditRecord) -> None:
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")


def load_records(ledger_path: str | Path) -> list[dict[str, Any]]:
    path = Path(ledger_path)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def load_failure_samples(ledger_path: str | Path) -> list[dict[str, Any]]:
    return [r for r in load_records(ledger_path) if r.get("is_failure")]


def summarize_pages(ledger_path: str | Path) -> dict[str, Any]:
    """页级命中统计：每个 wiki 页被检索命中几次、最后一次命中时间。

    这是「档案维护降级」决策的数据底座：长期零命中的页不删（存储免费），
    但应停止对它们的精修/证据分层投入；高命中页才值得花 ingest 预算。
    （思路即 LRU 缓存分层，可迁移到任何知识管理/检索系统的维护预算分配。）
    """
    records = load_records(ledger_path)
    pages: dict[str, dict[str, Any]] = {}
    queries_with_wiki = 0
    for rec in records:
        page_list = [str(p) for p in (rec.get("wiki_pages") or []) if str(p).strip()]
        if page_list:
            queries_with_wiki += 1
        ts = str(rec.get("ts") or "")
        for p in page_list:
            st = pages.setdefault(p, {"page": p, "hits": 0, "last_hit": ""})
            st["hits"] += 1
            if ts > st["last_hit"]:
                st["last_hit"] = ts
    ranked = sorted(pages.values(), key=lambda s: (-s["hits"], s["page"]))
    return {
        "total_records": len(records),
        "records_with_wiki_pages": queries_with_wiki,
        "distinct_pages": len(ranked),
        "pages": ranked,
    }


def summarize_ledger(ledger_path: str | Path) -> dict[str, Any]:
    records = load_records(ledger_path)
    total = len(records)
    if not total:
        return {"total": 0}
    source_totals: dict[str, int] = {}
    verdicts: dict[str, int] = {}
    failure_tags: dict[str, int] = {}
    l3_covered = 0
    for rec in records:
        for src, n in (rec.get("source_hits") or {}).items():
            source_totals[src] = source_totals.get(src, 0) + int(n)
        verdicts[rec.get("verdict", "?")] = verdicts.get(rec.get("verdict", "?"), 0) + 1
        if rec.get("covers_l3"):
            l3_covered += 1
        for tag in rec.get("failure_tags") or []:
            failure_tags[tag] = failure_tags.get(tag, 0) + 1
    failures = sum(1 for r in records if r.get("is_failure"))
    return {
        "total": total,
        "failures": failures,
        "failure_rate": round(failures / total, 4),
        "l3_coverage_rate": round(l3_covered / total, 4),
        "source_hit_totals": source_totals,
        "verdict_distribution": verdicts,
        "failure_tag_distribution": failure_tags,
    }

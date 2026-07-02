from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from intelligence.services import l3_ingest
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


@dataclass(frozen=True)
class L3IngestWorkflowOptions:
    company: str
    sources: tuple[str, ...] = ("cninfo",)
    days: int = 30
    limit: int = 20
    out_json: str | Path | None = None


@dataclass(frozen=True)
class L3ApplyWorkflowOptions:
    payload_path: str | Path
    kb_wiki: str | Path
    apply: bool = False
    reviewed: bool = False


def run_l3_ingest(options: L3IngestWorkflowOptions) -> tuple[WorkflowSummary, l3_ingest.L3IngestResult, str]:
    summary = WorkflowSummary(
        workflow="l3-ingest",
        status="PASS",
        started_at=now_iso(),
        inputs={
            "company": options.company,
            "sources": list(options.sources),
            "days": options.days,
            "limit": options.limit,
        },
    )
    result = l3_ingest.ingest_l3_company(
        options.company,
        sources=options.sources,
        days=options.days,
        limit=options.limit,
    )
    report = l3_ingest.render_l3_ingest_report(result)

    outputs: list[str] = [
        f"raw_items={len(result.raw_items)}",
        f"candidates={len(result.candidates)}",
        f"rejected={len(result.rejected)}",
        f"commands={len(result.commands)}",
    ]
    if options.out_json:
        written = result.write_json(options.out_json)
        outputs.append(f"out_json={written}")

    lookup_status = "PASS" if result.raw_items else ("WARN" if result.commands else "SKIP")
    summary.steps.append(
        WorkflowStep(
            name="lookup-runtime-l3",
            status=lookup_status,
            outputs=[f"commands={len(result.commands)}", f"raw_items={len(result.raw_items)}"],
            warnings=list(result.warnings),
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="extract-and-gate-candidates",
            status="PASS" if result.candidates else "WARN",
            outputs=[f"candidates={len(result.candidates)}", f"rejected={len(result.rejected)}"],
            warnings=[] if result.candidates else ["未抽取到可沉淀 L3 候选；可能是公告噪音、命中太少或需要互动易慢源。"],
        )
    )
    summary.outputs = outputs
    summary.warnings = list(result.warnings)
    summary.next_actions = [
        "人工复核 candidates 后，再决定是否升级写入 knowledge-base 的 evidence_index/entity/relations。",
        "若公告快路径无候选，可打开 sse_einteract 慢路径补互动易，但不要把泛泛问答直接入库。",
    ]
    summary.finish("PASS" if result.candidates else "WARN")
    return summary, result, report


def run_l3_apply(options: L3ApplyWorkflowOptions) -> tuple[WorkflowSummary, l3_ingest.L3ApplyResult, str]:
    summary = WorkflowSummary(
        workflow="l3-ingest-apply",
        status="PASS",
        started_at=now_iso(),
        inputs={
            "payload_path": str(options.payload_path),
            "kb_wiki": str(options.kb_wiki),
            "apply": options.apply,
            "reviewed": options.reviewed,
        },
    )
    result = l3_ingest.apply_l3_payload(
        options.payload_path,
        kb_wiki=options.kb_wiki,
        apply=options.apply,
        reviewed=options.reviewed,
    )
    report = l3_ingest.render_l3_apply_report(result)
    summary.steps.append(
        WorkflowStep(
            name="select-l3-candidates",
            status="PASS" if result.selected_count else "WARN",
            outputs=[f"selected={result.selected_count}"],
            warnings=[] if result.selected_count else ["payload 中没有可写 L3 候选。"],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="write-wiki-l3-assets",
            status="PASS" if options.apply and result.created_sources else ("SKIP" if not options.apply else "WARN"),
            outputs=[
                f"created_sources={len(result.created_sources)}",
                f"updated_entities={len(result.updated_entities)}",
                f"dry_run={not options.apply}",
            ],
            warnings=list(result.warnings),
        )
    )
    summary.outputs = [
        f"selected={result.selected_count}",
        f"source_note={result.source_note_path}",
        f"entity={result.entity_path}",
    ]
    summary.warnings = list(result.warnings)
    summary.next_actions = [
        "先检查生成的 wiki/sources L3 证据页，再决定是否把其中硬事实升级到 relations/evidence_index。",
        "若要进入 Theme Radar 打分层，优先走 knowledge-base disclosure-archive reviewed apply。",
    ]
    status = "WARN" if result.warnings else "PASS"
    if not result.selected_count:
        status = "WARN"
    summary.finish(status)
    return summary, result, report

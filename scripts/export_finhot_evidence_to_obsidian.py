from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.paths import default_paths

DEFAULT_OUTPUT_DIR = Path("raw") / "finhot-evidence-staging"
PRIMARY_LAYERS = {
    "L3_current_official_catalyst",
    "L3_historical_official_fact",
    "L2_official_baseline",
}
CANDIDATE_LAYER = "L3_candidate"
MIN_LAYER_CHOICES = {"L2", "L3"}
DEFAULT_L3_CANDIDATE_MIN_CONFIDENCE = 0.6
MAX_TEXT_SNIPPET_CHARS = 260
SOURCE_FINGERPRINT_VERSION = "v1"
ID_FIELD_PRIORITY = ("origin_queue_task_id", "kb_task_id", "queue_task_id", "task_id")
APPROVAL_DECISIONS = ("pending", "approved", "rejected", "applied")


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def text_value(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"missing evidence report: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def escape_md(value: Any) -> str:
    text = text_value(value)
    return text.replace("|", "/").replace("\r", " ").replace("\n", " ") or "-"


def yaml_scalar(value: Any) -> str:
    return json.dumps(text_value(value), ensure_ascii=False)


def stable_candidate_id(item: dict[str, Any]) -> str:
    payload = "|".join([
        text_value(item.get("task_id")),
        text_value(item.get("item_id")),
        text_value(item.get("url")),
        text_value(item.get("evidence_layer")),
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def normalized_url(value: Any) -> str:
    url = text_value(value)
    if not url:
        return ""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme in {"http", "https"}:
        scheme = "https"
    path = parts.path
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)), doseq=True)
    return urlunsplit((scheme, parts.netloc.lower(), path, query, ""))


def normalized_excerpt(value: Any) -> str:
    return " ".join(text_value(value).split())[:MAX_TEXT_SNIPPET_CHARS]


def excerpt_hash(item: dict[str, Any]) -> str:
    excerpt = normalized_excerpt(item.get("text") or item.get("title") or item.get("reason"))
    return hashlib.sha1(excerpt.encode("utf-8")).hexdigest()


def stable_source_fingerprint(item: dict[str, Any]) -> str:
    payload = "|".join([
        normalized_url(item.get("url")),
        text_value(item.get("item_id")),
        text_value(item.get("evidence_layer")),
        excerpt_hash(item),
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def identity_from_mapping(mapping: dict[str, Any], *, include_task_id: bool = True) -> str:
    fields = ID_FIELD_PRIORITY if include_task_id else tuple(field for field in ID_FIELD_PRIORITY if field != "task_id")
    metadata = mapping.get("metadata") if isinstance(mapping.get("metadata"), dict) else {}
    for field in fields:
        value = text_value(mapping.get(field)) or text_value(metadata.get(field))
        if value:
            return value
    return ""


def queue_task_id_for(item: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> str:
    item_identity = identity_from_mapping(item, include_task_id=False)
    if item_identity:
        return item_identity
    task = tasks.get(text_value(item.get("task_id")), {})
    return identity_from_mapping(task) or text_value(item.get("task_id"))


def confidence_value(item: dict[str, Any]) -> float:
    try:
        return float(item.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def validate_report(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise ValueError("evidence report root must be an object")
    if not isinstance(report.get("matched_items"), list):
        raise ValueError("evidence report missing matched_items; rerun Evidence Hunter")
    if not isinstance(report.get("rejected_items"), list):
        raise ValueError("evidence report missing rejected_items; rerun Evidence Hunter")
    if not isinstance(report.get("tasks"), list):
        raise ValueError("evidence report missing tasks; rerun Evidence Hunter")
    return report


def primary_layers_for(min_layer: str) -> set[str]:
    normalized = text_value(min_layer) or "L2"
    if normalized not in MIN_LAYER_CHOICES:
        raise ValueError("min_layer must be L2 or L3")
    if normalized == "L3":
        return PRIMARY_LAYERS - {"L2_official_baseline"}
    return set(PRIMARY_LAYERS)


def include_candidate(item: dict[str, Any], l3_candidate_min_confidence: float, min_layer: str = "L2") -> bool:
    layer = text_value(item.get("evidence_layer"))
    if layer in primary_layers_for(min_layer):
        return True
    if layer == CANDIDATE_LAYER and confidence_value(item) >= l3_candidate_min_confidence:
        return True
    return False


def with_candidate_ids(items: list[dict[str, Any]], l3_candidate_min_confidence: float, min_layer: str = "L2", tasks: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    task_lookup = tasks or {}
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not include_candidate(item, l3_candidate_min_confidence, min_layer):
            continue
        row = dict(item)
        origin_queue_task_id = queue_task_id_for(row, task_lookup)
        row["candidate_id"] = stable_candidate_id(row)
        row["source_fingerprint"] = stable_source_fingerprint(row)
        row["origin_queue_task_id"] = origin_queue_task_id
        row["kb_task_id"] = origin_queue_task_id
        out.append(row)
    out.sort(key=lambda row: (text_value(row.get("evidence_layer")), -confidence_value(row), text_value(row.get("task_id")), text_value(row.get("item_id"))))
    return out


def group_by_item(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    tasks_by_key: dict[str, list[str]] = defaultdict(list)
    ids_by_key: dict[str, list[str]] = defaultdict(list)
    origin_ids_by_key: dict[str, list[str]] = defaultdict(list)
    kb_ids_by_key: dict[str, list[str]] = defaultdict(list)
    for item in items:
        key = text_value(item.get("source_fingerprint")) or stable_source_fingerprint(item)
        if key not in grouped or confidence_value(item) > confidence_value(grouped[key]):
            grouped[key] = item
        task_id = text_value(item.get("task_id"))
        if task_id and task_id not in tasks_by_key[key]:
            tasks_by_key[key].append(task_id)
        candidate_id = text_value(item.get("candidate_id"))
        if candidate_id and candidate_id not in ids_by_key[key]:
            ids_by_key[key].append(candidate_id)
        origin_queue_task_id = text_value(item.get("origin_queue_task_id"))
        if origin_queue_task_id and origin_queue_task_id not in origin_ids_by_key[key]:
            origin_ids_by_key[key].append(origin_queue_task_id)
        kb_task_id = text_value(item.get("kb_task_id"))
        if kb_task_id and kb_task_id not in kb_ids_by_key[key]:
            kb_ids_by_key[key].append(kb_task_id)
    rows = []
    for key, item in grouped.items():
        row = dict(item)
        row["source_fingerprint"] = key
        row["matched_tasks"] = tasks_by_key[key]
        row["candidate_ids"] = ids_by_key[key]
        row["origin_queue_task_ids"] = origin_ids_by_key[key]
        row["kb_task_ids"] = kb_ids_by_key[key]
        rows.append(row)
    rows.sort(key=lambda row: (text_value(row.get("evidence_layer")), -confidence_value(row), text_value(row.get("source_fingerprint"))))
    return rows


def reject_summary(rejected_items: list[Any]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in rejected_items:
        if isinstance(item, dict):
            counter[text_value(item.get("reject_reason")) or "unknown"] += 1
    return dict(sorted(counter.items()))


def task_index(tasks: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if isinstance(task, dict):
            task_id = text_value(task.get("task_id"))
            if task_id:
                out[task_id] = task
    return out


def snippet(text: Any, limit: int = MAX_TEXT_SNIPPET_CHARS) -> str:
    value = " ".join(text_value(text).split())
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def render_candidate_table(items: list[dict[str, Any]], tasks: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["| Source fingerprint | Candidate | KB task | Layer | Conf | Source | Published | Theme | Entity | Fact terms | Title | URL |", "|---|---|---|---|---:|---|---|---|---|---|---|---|"]
    if not items:
        lines.append("| - | - | - | - | - | - | - | - | - | - | - | - |")
        return lines
    for item in items:
        matched_tasks = as_list(item.get("matched_tasks")) or [item.get("task_id")]
        themes = []
        for task_id in matched_tasks:
            task = tasks.get(text_value(task_id), {})
            theme = text_value(task.get("theme") or task.get("concept"))
            if theme and theme not in themes:
                themes.append(theme)
        lines.append(
            "| {fingerprint} | {candidate} | {kb_task} | {layer} | {conf:.2f} | {source} | {published} | {theme} | {entity} | {facts} | {title} | {url} |".format(
                fingerprint=escape_md(item.get("source_fingerprint")),
                candidate=escape_md(", ".join(as_list(item.get("candidate_ids"))) or item.get("candidate_id")),
                kb_task=escape_md("、".join(as_list(item.get("kb_task_ids"))) or item.get("kb_task_id")),
                layer=escape_md(item.get("evidence_layer")),
                conf=confidence_value(item),
                source=escape_md(item.get("source")),
                published=escape_md(item.get("published_at")),
                theme=escape_md("、".join(themes)),
                entity=escape_md("、".join(as_list(item.get("matched_entities")))),
                facts=escape_md("、".join(as_list(item.get("matched_fact_terms"))[:8])),
                title=escape_md(item.get("title")),
                url=escape_md(item.get("url")),
            )
        )
    return lines


def render_candidate_details(items: list[dict[str, Any]], tasks: dict[str, dict[str, Any]]) -> list[str]:
    if not items:
        return ["无。"]
    lines: list[str] = []
    for idx, item in enumerate(items, start=1):
        matched_tasks = [text_value(x) for x in as_list(item.get("matched_tasks"))] or [text_value(item.get("task_id"))]
        task_labels = []
        for task_id in matched_tasks:
            task = tasks.get(task_id, {})
            theme = text_value(task.get("theme") or task.get("concept"))
            task_labels.append(f"{task_id}（{theme or '-'}）")
        lines.extend([
            f"### {idx}. {text_value(item.get('title')) or '-'}",
            "",
            f"- **source_fingerprint**: `{text_value(item.get('source_fingerprint')) or '-'}`",
            f"- **candidate_id**: `{', '.join(as_list(item.get('candidate_ids'))) or text_value(item.get('candidate_id'))}`",
            f"- **origin_queue_task_id**: `{', '.join(as_list(item.get('origin_queue_task_ids'))) or text_value(item.get('origin_queue_task_id')) or '-'}`",
            f"- **kb_task_id**: `{', '.join(as_list(item.get('kb_task_ids'))) or text_value(item.get('kb_task_id')) or '-'}`",
            f"- **evidence_layer**: `{text_value(item.get('evidence_layer')) or '-'}`",
            f"- **confidence**: `{confidence_value(item):.2f}`",
            f"- **source**: {text_value(item.get('source')) or '-'}",
            f"- **published_at**: {text_value(item.get('published_at')) or '-'}",
            f"- **url**: {text_value(item.get('url')) or '-'}",
            f"- **matched_tasks**: {'；'.join(task_labels) or '-'}",
            f"- **matched_entities**: {'、'.join(as_list(item.get('matched_entities'))) or '-'}",
            f"- **matched_fact_terms**: {'、'.join(as_list(item.get('matched_fact_terms'))[:8]) or '-'}",
            f"- **reason**: {text_value(item.get('reason')) or '-'}",
            "",
            "> " + (snippet(item.get("text")) or "-"),
            "",
        ])
    return lines


def items_for_layer(grouped_items: list[dict[str, Any]], layer: str) -> list[dict[str, Any]]:
    return [item for item in grouped_items if text_value(item.get("evidence_layer")) == layer]


def render_markdown(report: dict[str, Any], selected_items: list[dict[str, Any]], *, date_text: str, generated_at: str, source_report: Path, l3_candidate_min_confidence: float, min_layer: str, include_rejected_summary: bool) -> str:
    grouped_items = group_by_item(selected_items)
    tasks = task_index(as_list(report.get("tasks")))
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    rejected = as_list(report.get("rejected_items"))
    rejects = reject_summary(rejected)
    selected_counts = Counter(text_value(item.get("evidence_layer")) for item in selected_items)
    lines = [
        "---",
        f"title: {yaml_scalar(f'FinHot Evidence Staging {date_text}')}",
        "type: raw_staging",
        "source: finhot",
        "evidence_workflow: evidence_hunter",
        "status: candidate",
        "review_required: true",
        f"date: {yaml_scalar(date_text)}",
        f"generated_at: {yaml_scalar(generated_at)}",
        "tags: [finhot, evidence-hunter, staging]",
        "---",
        "",
        f"# FinHot Evidence Staging {date_text}",
        "",
        "## 使用口径",
        "",
        "- **FinHot 原始数据**: 继续留在 SQLite，本文件只承载 Evidence Hunter 的人工待审候选。",
        "- **正式知识层**: 本文件位于 `raw/finhot-evidence-staging/`，不等同于 `sources/` 正式证据。",
        "- **纳入分层**: `L3_current_official_catalyst`、`L3_historical_official_fact`、`L2_official_baseline`、高置信 `L3_candidate`。",
        f"- **min_layer**: `{min_layer}`。",
        f"- **L3_candidate 阈值**: `{l3_candidate_min_confidence:.2f}`。",
        f"- **source_report**: `{source_report}`",
        "",
        "## 摘要",
        "",
        f"- **task_count**: {summary.get('task_count', len(tasks))}",
        f"- **matched_count**: {summary.get('matched_count', len(as_list(report.get('matched_items'))))}",
        f"- **selected_candidate_count**: {len(selected_items)}",
        f"- **deduped_item_count**: {len(grouped_items)}",
        f"- **rejected_count**: {summary.get('rejected_count', len(rejected))}",
        f"- **selected_layer_counts**: `{json.dumps(dict(sorted(selected_counts.items())), ensure_ascii=False)}`",
    ]
    if include_rejected_summary:
        lines.append(f"- **reject_reason_counts**: `{json.dumps(rejects, ensure_ascii=False)}`")
    lines.extend([
        "",
        "## L3 当前官方催化候选",
        "",
        *render_candidate_table(items_for_layer(grouped_items, "L3_current_official_catalyst"), tasks),
        "",
        *render_candidate_details(items_for_layer(grouped_items, "L3_current_official_catalyst"), tasks),
        "## L3 历史官方事实",
        "",
        *render_candidate_table(items_for_layer(grouped_items, "L3_historical_official_fact"), tasks),
        "",
        *render_candidate_details(items_for_layer(grouped_items, "L3_historical_official_fact"), tasks),
        "## L2 官方基线",
        "",
        *render_candidate_table(items_for_layer(grouped_items, "L2_official_baseline"), tasks),
        "",
        *render_candidate_details(items_for_layer(grouped_items, "L2_official_baseline"), tasks),
        "## L3 待追官方原文候选",
        "",
        *render_candidate_table(items_for_layer(grouped_items, "L3_candidate"), tasks),
        "",
        *render_candidate_details(items_for_layer(grouped_items, "L3_candidate"), tasks),
    ])
    if include_rejected_summary:
        lines.extend(["## 被拒绝或低置信线索摘要", ""])
        if rejects:
            lines.extend(["| Reject reason | Count |", "|---|---:|"])
            lines.extend(f"| {escape_md(reason)} | {count} |" for reason, count in rejects.items())
        else:
            lines.append("无 rejected 条目。")
    lines.extend([
        "",
        "## 人工确认清单",
        "",
        "| Source fingerprint | Candidate | KB task | Decision | Proposed layer | Target note path | Reviewer note |",
        "|---|---|---|---|---|---|---|",
    ])
    for item in selected_items:
        lines.append(
            "| {fingerprint} | {candidate} | {kb_task} | pending | {proposed} |  |  |".format(
                fingerprint=escape_md(item.get("source_fingerprint")),
                candidate=escape_md(item.get("candidate_id")),
                kb_task=escape_md(item.get("kb_task_id")),
                proposed=escape_md(proposed_layer_for(item)),
            )
        )
    if not selected_items:
        lines.append("| - | - | - | - | - | - | - |")
    lines.append("")
    return "\n".join(lines)


def proposed_layer_for(item: dict[str, Any]) -> str | None:
    layer = text_value(item.get("evidence_layer"))
    if layer == CANDIDATE_LAYER:
        return None
    return layer or None


def cannot_upgrade_without_official_url(item: dict[str, Any]) -> bool:
    return text_value(item.get("evidence_layer")) == CANDIDATE_LAYER


def build_manifest(report: dict[str, Any], selected_items: list[dict[str, Any]], *, date_text: str, source_report: Path, staging_note: Path, wiki_root: Path) -> dict[str, Any]:
    approvals = []
    for item in selected_items:
        approvals.append({
            "candidate_id": text_value(item.get("candidate_id")),
            "source_fingerprint": text_value(item.get("source_fingerprint")),
            "source_fingerprint_version": SOURCE_FINGERPRINT_VERSION,
            "task_id": text_value(item.get("task_id")),
            "origin_queue_task_id": text_value(item.get("origin_queue_task_id")),
            "kb_task_id": text_value(item.get("kb_task_id")),
            "decision": "pending",
            "allowed_decisions": list(APPROVAL_DECISIONS),
            "evidence_layer_original": text_value(item.get("evidence_layer")),
            "evidence_layer_proposed": proposed_layer_for(item),
            "approval_cannot_upgrade_without_official_url": cannot_upgrade_without_official_url(item),
            "approved_layer": None,
            "target_source_note": None,
            "target_note_path": None,
            "reviewer": None,
            "reviewed_at": None,
            "decision_reason": "",
            "related_entities": as_list(item.get("matched_entities")),
            "related_concepts": as_list(item.get("matched_theme_terms")),
            "reviewer_note": "",
        })
    try:
        staging_ref = str(staging_note.relative_to(wiki_root))
    except ValueError:
        staging_ref = str(staging_note)
    return {
        "date": date_text,
        "source": "finhot-evidence-hunter",
        "source_fingerprint_version": SOURCE_FINGERPRINT_VERSION,
        "source_report": str(source_report),
        "staging_note": staging_ref,
        "summary": {
            "task_count": len(as_list(report.get("tasks"))),
            "selected_candidate_count": len(selected_items),
            "source_fingerprint_count": len({text_value(item.get("source_fingerprint")) for item in selected_items}),
            "reject_reason_counts": reject_summary(as_list(report.get("rejected_items"))),
        },
        "approvals": approvals,
    }


def default_date(report: dict[str, Any]) -> str:
    return text_value(report.get("trade_date")) or datetime.now().date().isoformat()


def export_report(evidence_report_path: Path, wiki_root: Path, *, date_text: str = "", output_dir: Path = DEFAULT_OUTPUT_DIR, overwrite: bool = False, min_layer: str = "L2", include_rejected_summary: bool = True, l3_candidate_min_confidence: float = DEFAULT_L3_CANDIDATE_MIN_CONFIDENCE) -> dict[str, Any]:
    report = validate_report(load_json(evidence_report_path))
    date_value = date_text or default_date(report)
    if not wiki_root.exists() or not wiki_root.is_dir():
        raise FileNotFoundError(f"wiki root does not exist: {wiki_root}")
    target_dir = output_dir if output_dir.is_absolute() else wiki_root / output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    staging_note = target_dir / f"{date_value}-finhot-evidence-staging.md"
    manifest_path = target_dir / f"{date_value}-finhot-evidence-approval-template.json"
    if not overwrite:
        existing = [path for path in (staging_note, manifest_path) if path.exists()]
        if existing:
            raise FileExistsError("output already exists; pass --overwrite: " + ", ".join(str(path) for path in existing))
    matched_items = [item for item in as_list(report.get("matched_items")) if isinstance(item, dict)]
    tasks = task_index(as_list(report.get("tasks")))
    selected_items = with_candidate_ids(matched_items, l3_candidate_min_confidence, min_layer, tasks)
    generated_at = datetime.now(timezone.utc).isoformat()
    markdown = render_markdown(
        report,
        selected_items,
        date_text=date_value,
        generated_at=generated_at,
        source_report=evidence_report_path,
        l3_candidate_min_confidence=l3_candidate_min_confidence,
        min_layer=min_layer,
        include_rejected_summary=include_rejected_summary,
    )
    staging_note.write_text(markdown, encoding="utf-8")
    manifest = build_manifest(report, selected_items, date_text=date_value, source_report=evidence_report_path, staging_note=staging_note, wiki_root=wiki_root)
    write_json(manifest_path, manifest)
    return {
        "staging_note": str(staging_note),
        "manifest": str(manifest_path),
        "selected_candidate_count": len(selected_items),
        "deduped_item_count": len(group_by_item(selected_items)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export FinHot Evidence Hunter report to Obsidian staging")
    parser.add_argument("--evidence-report", required=True)
    parser.add_argument("--wiki-root", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--min-layer", choices=sorted(MIN_LAYER_CHOICES), default="L2")
    parser.add_argument("--include-rejected-summary", dest="include_rejected_summary", action="store_true", default=True)
    parser.add_argument("--no-rejected-summary", dest="include_rejected_summary", action="store_false")
    parser.add_argument("--l3-candidate-min-confidence", type=float, default=DEFAULT_L3_CANDIDATE_MIN_CONFIDENCE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence_report = Path(args.evidence_report).expanduser()
    wiki_root = Path(args.wiki_root).expanduser() if args.wiki_root else default_paths().knowledge_wiki
    output_dir = Path(args.output_dir).expanduser()
    result = export_report(
        evidence_report,
        wiki_root,
        date_text=args.date,
        output_dir=output_dir,
        overwrite=args.overwrite,
        min_layer=args.min_layer,
        include_rejected_summary=args.include_rejected_summary,
        l3_candidate_min_confidence=args.l3_candidate_min_confidence,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

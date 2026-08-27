from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "market_feature_store" / "exports"


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing input file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json root is not an object: {path}")
    return data


def load_indexed_files(index_path: Path) -> set[str]:
    indexed: set[str] = set()
    if not index_path.exists():
        return indexed
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        file_path = str(row.get("file_path") or "").strip()
        if file_path:
            indexed.add(file_path)
    return indexed


def enrich_ledger_with_index(ledger: dict[str, Any], kb_root: Path, index_path: Path | None = None) -> dict[str, Any]:
    index_file = index_path or kb_root / ".rag_index" / "chunks.jsonl"
    indexed_files = load_indexed_files(index_file)
    items = []
    for raw in as_list(ledger.get("items")):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        concept = str(item.get("canonical_concept") or item.get("theme") or "").strip()
        concept_file = f"wiki/concepts/{concept}.md" if concept else ""
        concept_path = kb_root / concept_file if concept_file else None
        concept_page_exists = bool(concept_path and concept_path.exists())
        rag_indexed = bool(concept_file and concept_file in indexed_files)
        item["index_probe"] = {
            "concept": concept,
            "concept_file": concept_file,
            "concept_page_exists": concept_page_exists,
            "rag_indexed": rag_indexed,
        }
        item["index_status"] = _index_status(concept, concept_page_exists, rag_indexed)
        items.append(item)
    out = dict(ledger)
    out["source"] = "ingest-status-ledger-indexed"
    out["generated_at"] = datetime.now(timezone.utc).isoformat()
    inputs = dict(out.get("inputs") or {})
    inputs["knowledge_base_root"] = str(kb_root)
    inputs["rag_index"] = str(index_file)
    out["inputs"] = inputs
    out["items"] = items
    out["item_count"] = len(items)
    out["index_status_counts"] = dict(sorted(Counter(str(item.get("index_status")) for item in items).items()))
    out["index_probe_counts"] = {
        "concept_page_exists": sum(1 for item in items if item.get("index_probe", {}).get("concept_page_exists")),
        "rag_indexed": sum(1 for item in items if item.get("index_probe", {}).get("rag_indexed")),
        "not_indexed": sum(1 for item in items if not item.get("index_probe", {}).get("rag_indexed")),
    }
    return out


def _index_status(concept: str, concept_page_exists: bool, rag_indexed: bool) -> str:
    if not concept:
        return "missing_concept_name"
    if rag_indexed:
        return "rag_indexed"
    if concept_page_exists:
        return "concept_page_exists"
    return "not_in_kb"


def md_table(items: list[dict[str, Any]]) -> str:
    lines = [
        "| Index | Ingest | Rank | 题材 | Concept | Concept Page | RAG |",
        "|---|---|---:|---|---|---|---|",
    ]
    for item in items:
        probe = item.get("index_probe") if isinstance(item.get("index_probe"), dict) else {}
        lines.append(
            "| {index} | {ingest} | {rank} | {theme} | {concept} | {page} | {rag} |".format(
                index=str(item.get("index_status") or "-").replace("|", "/"),
                ingest=str(item.get("ingest_status") or "-").replace("|", "/"),
                rank=item.get("rank") or "-",
                theme=str(item.get("theme") or "-").replace("|", "/"),
                concept=str(probe.get("concept") or "-").replace("|", "/"),
                page="yes" if probe.get("concept_page_exists") else "no",
                rag="yes" if probe.get("rag_indexed") else "no",
            )
        )
    return "\n".join(lines)


def render_markdown(payload: dict[str, Any]) -> str:
    items = [item for item in as_list(payload.get("items")) if isinstance(item, dict)]
    return "\n".join([
        f"# {payload.get('trade_date')} Ingest Status Index Probe",
        "",
        "## 摘要",
        "",
        f"- **item_count**: {payload.get('item_count')}",
        f"- **status_counts**: `{json.dumps(payload.get('status_counts', {}), ensure_ascii=False)}`",
        f"- **index_status_counts**: `{json.dumps(payload.get('index_status_counts', {}), ensure_ascii=False)}`",
        f"- **index_probe_counts**: `{json.dumps(payload.get('index_probe_counts', {}), ensure_ascii=False)}`",
        "",
        "## 明细",
        "",
        md_table(items),
        "",
    ])


def output_paths_for(trade_date: str) -> tuple[Path, Path]:
    return (
        EXPORT_DIR / f"{trade_date}-ingest-status-ledger-indexed.json",
        EXPORT_DIR / f"{trade_date}-ingest-status-ledger-indexed.md",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich ingest status ledger with read-only KB/RAG index probes")
    parser.add_argument("date")
    parser.add_argument("--ledger", dest="ledger_path")
    parser.add_argument("--kb-root", required=True)
    parser.add_argument("--index", dest="index_path")
    parser.add_argument("--out-json", dest="out_json")
    parser.add_argument("--out-md", dest="out_md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger_path = Path(args.ledger_path).expanduser() if args.ledger_path else EXPORT_DIR / f"{args.date}-ingest-status-ledger.json"
    kb_root = Path(args.kb_root).expanduser()
    index_path = Path(args.index_path).expanduser() if args.index_path else None
    out_json, out_md = output_paths_for(args.date)
    if args.out_json:
        out_json = Path(args.out_json).expanduser()
    if args.out_md:
        out_md = Path(args.out_md).expanduser()
    payload = enrich_ledger_with_index(load_json(ledger_path), kb_root, index_path)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(payload), encoding="utf-8")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print(f"index_probe_counts={json.dumps(payload['index_probe_counts'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

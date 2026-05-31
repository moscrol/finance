#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path("/Users/lbq/Desktop/c c/知识库")
WIKI = ROOT / "wiki"
FINANCE = Path("/Users/lbq/Desktop/c c/金融")
SOURCES = [
    "20260213市场逻辑精选",
    "20260224市场逻辑精选",
    "20260225市场逻辑精选",
    "20260226市场逻辑精选",
    "20260227市场逻辑精选",
    "20260302市场逻辑精选",
    "20260303市场逻辑精选",
    "20260304市场逻辑精选",
]
LOG_IDS = set(range(148, 156))
RELATION_FILES = ["entity_exposures.json", "evidence_index.json", "concept_graph.json", "report_contexts.json"]


def backup_dir() -> Path:
    existing_root = WIKI / "archive" / "auto-hbs-rollback"
    existing_root.mkdir(parents=True, exist_ok=True)
    existing = [p for p in existing_root.iterdir() if p.is_dir()]
    if existing:
        return max(existing, key=lambda p: p.name)
    target = existing_root / datetime.now().strftime("%Y%m%d-%H%M%S")
    target.mkdir(parents=True, exist_ok=True)
    return target


def copy_if_exists(path: Path, target: Path) -> None:
    if not path.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def check_relations_clean() -> dict[str, dict[str, int]]:
    result = {}
    for source in SOURCES:
        hits = {}
        for name in RELATION_FILES:
            path = WIKI / "relations" / name
            if not path.exists():
                continue
            text = json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False)
            hits[name] = text.count(source) + text.count(f"[[{source}]]")
        result[source] = hits
    return result


def remove_log_blocks() -> None:
    log_path = WIKI / "log.md"
    text = log_path.read_text(encoding="utf-8")
    pattern = re.compile(r"\n?### #(\d+) \|.*?(?=\n### #\d+ \||\Z)", re.S)
    text = pattern.sub(lambda m: "" if int(m.group(1)) in LOG_IDS else m.group(0), text).rstrip() + "\n"
    log_path.write_text(text, encoding="utf-8")


def update_index() -> dict[str, int]:
    index_path = WIKI / "index.md"
    text = index_path.read_text(encoding="utf-8")
    for number, source in zip(range(148, 156), SOURCES):
        text = text.replace(f', "#{number:03d} PDF ingest: {source}"', "")
        text = text.replace(f'"#{number:03d} PDF ingest: {source}", ', "")
        text = text.replace(f'"#{number:03d} PDF ingest: {source}"', "")
    for source in SOURCES:
        text = re.sub(r',?\s*"#[0-9]{3} PDF ingest: ' + re.escape(source) + r'[^"\\]*(?:\\.[^"\\]*)*"', "", text)
    source_count = len(list((WIKI / "sources").glob("*.md")))
    concept_count = len(list((WIKI / "concepts").glob("*.md")))
    entity_count = len(list((WIKI / "entities").glob("*.md")))
    synthesis_count = len(list((WIKI / "synthesis").glob("*.md")))
    total = source_count + concept_count + entity_count + synthesis_count
    rev = re.search(r"^revision:\s*(\d+)\s*$", text, re.M)
    if rev:
        text = re.sub(r"^revision:\s*\d+\s*$", f"revision: {int(rev.group(1)) + 1}", text, count=1, flags=re.M)
    text = re.sub(
        r"\*\*\d+ 页 \| \d+ 个来源 \| \d+ 个概念 \| \d+ 个实体 \| \d+ 个综合分析\*\*",
        f"**{total} 页 | {source_count} 个来源 | {concept_count} 个概念 | {entity_count} 个实体 | {synthesis_count} 个综合分析**",
        text,
        count=1,
    )
    text = re.sub(r"## Sources（\d+个）", f"## Sources（{source_count}个）", text, count=1)
    index_path.write_text(text, encoding="utf-8")
    return {"sources": source_count, "concepts": concept_count, "entities": entity_count, "synthesis": synthesis_count, "total": total}


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback auto-generated hbs market-logic ingest entries #148-#155.")
    parser.add_argument("--apply", action="store_true", help="Actually delete generated raw/source files and edit log/index.")
    args = parser.parse_args()

    relation_hits = check_relations_clean()
    dirty_relations = {source: hits for source, hits in relation_hits.items() if any(hits.values())}
    if dirty_relations:
        raise SystemExit("Abort: relation hits found: " + json.dumps(dirty_relations, ensure_ascii=False))

    file_plan = []
    for source in SOURCES:
        for rel in [Path("raw") / f"{source}.md", Path("wiki/sources") / f"{source}.md"]:
            path = ROOT / rel
            file_plan.append({"path": str(path), "exists": path.exists(), "bytes": path.stat().st_size if path.exists() else 0})

    if not args.apply:
        print(json.dumps({"mode": "dry_run", "files": file_plan, "relation_hits": relation_hits}, ensure_ascii=False, indent=2))
        return 0

    backup = backup_dir()
    for path in [WIKI / "log.md", WIKI / "index.md", FINANCE / "scripts" / "hbs_market_logic_worker.py.disabled"]:
        copy_if_exists(path, backup / path.name)
    removed = []
    for source in SOURCES:
        for rel in [Path("raw") / f"{source}.md", Path("wiki/sources") / f"{source}.md"]:
            path = ROOT / rel
            if path.exists():
                copy_if_exists(path, backup / rel)
                path.unlink()
                removed.append(str(rel))
    remove_log_blocks()
    counts = update_index()
    print(json.dumps({"mode": "applied", "backup": str(backup), "removed": removed, "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

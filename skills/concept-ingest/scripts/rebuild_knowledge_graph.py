#!/usr/bin/env python3
"""Rebuild filesystem relation JSON from existing concept/entity markdown."""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))

from knowledge_graph import (  # noqa: E402
    default_aliases,
    default_concept_graph,
    default_entity_exposures,
    default_evidence_index,
    normalize_target,
    update_concept_graph,
    update_entity_exposures,
    write_json,
)


VAULT = Path(os.path.expanduser(os.environ.get("CONCEPT_VAULT", "~/Desktop/c c/知识库/wiki")))


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return {}, text
    lines = text.splitlines()
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            fm = {}
            for line in lines[1:i]:
                m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
                if m:
                    fm[m.group(1)] = m.group(2).strip()
            return fm, "\n".join(lines[i + 1 :])
    return {}, text


def parse_list(value):
    value = str(value or "")
    quoted = re.findall(r'"([^"]+)"', value)
    if quoted:
        return quoted
    links = re.findall(r"\[\[([^\]]+)\]\]", value)
    if links:
        return [normalize_target(v) for v in links]
    return [v.strip() for v in value.strip("[]").split(",") if v.strip()]


def parse_related_concepts(body):
    out = []
    m = re.search(r"## 相关概念\s*\n+(.+?)(?:\n## |\Z)", body, re.S)
    if m:
        out.extend(normalize_target(x) for x in re.findall(r"\[\[([^\]]+)\]\]", m.group(1)))
    for title, rel in re.findall(r"^### \[\[([^\]]+)\]\]\s*—\s*(.+)$", body, re.M):
        out.append(normalize_target(title))
    return list(dict.fromkeys(x for x in out if x))


def parse_companies(body):
    companies = []
    seen = set()
    for name, code in re.findall(r"([一-鿿A-Za-z0-9]{2,20})（(\d{6})）", body):
        if name in seen:
            continue
        seen.add(name)
        companies.append({"name": name, "code": code, "tier": "related", "role": "受益标的", "reason": "从既有Markdown关系表重建"})
    return companies


def reset_relation_files():
    write_json("concept_graph.json", default_concept_graph())
    write_json("entity_exposures.json", default_entity_exposures())
    write_json("aliases.json", default_aliases())
    write_json("evidence_index.json", default_evidence_index())


def main():
    reset_relation_files()
    concepts_dir = VAULT / "concepts"
    entities_dir = VAULT / "entities"
    concept_count = entity_count = 0

    for path in sorted(concepts_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        title = normalize_target(fm.get("title", "").strip('"')) or path.stem
        aliases = parse_list(fm.get("aliases", "[]"))
        sources = parse_list(fm.get("sources", "[]"))
        source_name = normalize_target(sources[-1]) if sources else ""
        related = parse_related_concepts(body)
        companies = parse_companies(body)
        ticker_map = {c["name"]: c["code"] for c in companies if c.get("code")}
        update_concept_graph(
            title,
            source_name=source_name,
            related_concepts=related,
            companies=companies,
            ticker_map=ticker_map,
            aliases=aliases,
            evidence="从既有concept markdown重建",
            confidence="medium",
        )
        concept_count += 1

    for path in sorted(entities_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        raw_title = fm.get("title", "").strip('"') or path.stem
        name = re.sub(r"（\d{6}）$", "", raw_title).strip()
        codes = re.findall(r"\b\d{6}\b", fm.get("tickers", "") + " " + raw_title)
        concepts = parse_related_concepts(body) or parse_list(fm.get("tags", "[]"))
        update_entity_exposures(
            name,
            code=codes[0] if codes else "",
            concepts=concepts,
            source_name=normalize_target((parse_list(fm.get("sources", "[]")) or [""])[-1]),
            evidence="从既有entity markdown重建",
            confidence="medium",
        )
        entity_count += 1

    print(f"rebuilt concepts={concept_count} entities={entity_count} into {VAULT / 'relations'}")


if __name__ == "__main__":
    main()

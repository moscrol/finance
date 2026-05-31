#!/usr/bin/env python3
"""PDF ingest post-write semantic lint.

Checks source notes, entity/concept markdown, and relations JSON for
consistency with Theme Radar quality rules.

Usage:
    python3 pdf_ingest_lint.py <source_name>
    python3 pdf_ingest_lint.py 0412评级日报

Exit code 0 = pass, 1 = issues found.
"""

import json
import re
import sys
from pathlib import Path

VAULT = Path.home() / "Desktop/c c/知识库/wiki"
SOURCES_DIR = VAULT / "sources"
ENTITIES_DIR = VAULT / "entities"
CONCEPTS_DIR = VAULT / "concepts"
RELATIONS_DIR = VAULT / "relations"

# Theme Radar enums
VALID_CHAIN_LAYERS = {
    "upstream_materials", "upstream_components", "upstream_equipment",
    "midstream_manufacturing", "midstream_components", "midstream_service", "midstream_equipment",
    "downstream_application", "downstream_operation", "ecosystem",
}
VALID_UPDATE_TYPES = {"baseline", "curated_research", "delta", "graph_only"}
VALID_EVIDENCE_LAYERS = {"L1", "L2", "L3", "L1_L3_candidate", "L2_candidate"}
VALID_FACT_HARDNESS = {"hard_fact", "baseline", "review_candidate", "research_claim", "market_narrative", "legacy_rebuilt", "unknown"}
VALID_SOURCE_QUALITY = {
    "official_disclosure", "company_primary",
    "broker_research_high", "broker_research_normal",
    "market_news", "market_narrative", "legacy_rebuilt", "unknown",
}
L3_SOURCES = {"official_disclosure", "company_primary"}
BROKER_SOURCES = {"broker_research_high", "broker_research_normal"}

GENERIC_ROLES = {
    "", "受益标的", "相关公司", "产业链供应商", "待验证受益标的", "市场信号弱关联", "图谱弱关联",
}
CHAIN_LAYER_VALUES = VALID_CHAIN_LAYERS | {"upstream", "midstream", "downstream", "上游", "中游", "下游"}

# fact_hardness → allowed update_type
HARDNESS_UPDATE_TYPE_MAP = {
    "hard_fact": {"delta", "hard_delta"},
    "baseline": {"baseline"},
    "review_candidate": {"delta", "curated_research"},
    "research_claim": {"curated_research", "graph_only"},
    "market_narrative": {"graph_only"},
    "unknown": {"graph_only"},
    "legacy_rebuilt": {"graph_only"},
}

# update_type → allowed fact_hardness
UPDATE_TYPE_HARDNESS_MAP = {
    "delta": {"hard_fact", "baseline", "review_candidate"},
    "hard_delta": {"hard_fact", "baseline"},
    "curated_research": {"research_claim", "review_candidate"},
    "graph_only": {"research_claim", "market_narrative", "unknown", "legacy_rebuilt"},
    "baseline": {"baseline"},
}

ISSUES = []


def issue(category, location, message, severity="ERROR"):
    ISSUES.append({
        "severity": severity,
        "category": category,
        "location": location,
        "message": message,
    })


def source_matches_source_list(sources, source_name):
    """Check if source_name matches any entry in a sources list (handles wikilinks)."""
    candidates = {source_name, f"[[{source_name}]]"}
    return any(str(s).strip() in candidates for s in sources or [])


def source_matches_value(value, source_name):
    """Check if a single value matches source_name (handles wikilinks)."""
    value = str(value or "").strip()
    return value in {source_name, f"[[{source_name}]]"} or source_name in value


def find_entities_for_source(source_name):
    """Scan all entities in entity_exposures.json that reference this source."""
    exposures = load_json("entity_exposures.json")
    result = []
    for entity, ent in (exposures.get("entities") or {}).items():
        for concept, exp in (ent.get("concepts") or {}).items():
            if source_matches_source_list(exp.get("sources"), source_name):
                result.append((entity, concept, exp))
    return result


def find_evidence_for_source(source_name):
    """Scan all evidence items that reference this source."""
    evidence_db = load_json("evidence_index.json")
    result = []
    for item in (evidence_db.get("items") or []):
        if source_matches_value(item.get("source"), source_name):
            result.append(item)
    return result


def reconcile_evidence_with_exposures(source_name):
    """Sync evidence_index fields with entity_exposures for a given source."""
    exposures = load_json("entity_exposures.json")
    evidence_db = load_json("evidence_index.json")
    changed = 0

    # Build lookup: (target, concept) -> exposure fields
    exp_lookup = {}
    for entity, ent in (exposures.get("entities") or {}).items():
        for concept, exp in (ent.get("concepts") or {}).items():
            if source_matches_source_list(exp.get("sources"), source_name):
                exp_lookup[(entity, concept)] = exp

    # Update evidence items
    for item in (evidence_db.get("items") or []):
        if not source_matches_value(item.get("source"), source_name):
            continue
        # Skip entity_research_note — these are curated_research evidence
        # that coexist with graph_only exposures and should not be overwritten
        if item.get("evidence_purpose") == "entity_research_note":
            continue
        key = (item.get("target", ""), item.get("concept", ""))
        if key not in exp_lookup:
            continue
        exp = exp_lookup[key]
        # Sync fields from exposure to evidence
        for field in ["update_type", "fact_hardness", "source_quality", "evidence_layer", "chain_layer"]:
            exp_val = exp.get(field, "")
            if exp_val and exp_val != item.get(field, ""):
                item[field] = exp_val
                changed += 1
        # Sync review_required
        if exp.get("review_required") and not item.get("review_required"):
            item["review_required"] = True
            changed += 1

    if changed:
        write_json("evidence_index.json", evidence_db)
    return changed


def check_source_note_idempotency(source_name):
    """Rule 1: No duplicate sections in source note."""
    path = SOURCES_DIR / f"{source_name}.md"
    if not path.exists():
        issue("source", str(path), "Source note not found")
        return

    text = path.read_text(encoding="utf-8")
    section_pattern = re.compile(r"^## (.+)$", re.MULTILINE)
    sections = section_pattern.findall(text)

    seen = {}
    for sec in sections:
        if sec in seen:
            issue("source", str(path),
                  f"Duplicate section: ## {sec} (first at char {seen[sec]}, duplicate at char {text.find('## ' + sec)})")
        else:
            seen[sec] = text.find("## " + sec)

    # Check for contradictions: concept in both "已更新概念" and "跳过概念增量 concept not found"
    if "已更新概念" in text and "跳过概念增量" in text:
        # Extract concepts from both sections
        updated_match = re.search(r"## 已更新概念\s*\n+(.+?)(?=\n## |\Z)", text, re.S)
        skipped_match = re.search(r"## 跳过概念增量\s*\n+(.+?)(?=\n## |\Z)", text, re.S)
        if updated_match and skipped_match:
            updated_concepts = set(re.findall(r"\[\[([^\]]+)\]\]", updated_match.group(1)))
            skipped_lines = skipped_match.group(1)
            for concept in updated_concepts:
                if concept in skipped_lines and "concept not found" in skipped_lines:
                    issue("source", str(path),
                          f"Contradiction: [[{concept}]] in both 已更新概念 and 跳过概念增量 (concept not found)")


def check_entity_page_exists(entity_name, source_name):
    """Check if curated_research exposure points to existing entity markdown."""
    path = ENTITIES_DIR / f"{entity_name}.md"
    if not path.exists():
        issue("consistency", f"{entity_name}",
              f"Entity page missing but has curated_research exposure from {source_name}")


def check_concept_page_sections(source_name):
    """Check if concept pages use 边际变化 for broker_research_high sources."""
    exposures = load_json("entity_exposures.json")
    # Find all concepts referenced by this source
    concepts_with_source = set()
    for entity, ent in (exposures.get("entities") or {}).items():
        for concept, exp in (ent.get("concepts") or {}).items():
            if source_matches_source_list(exp.get("sources"), source_name):
                concepts_with_source.add(concept)

    # Also check concept_graph
    graph = load_json("concept_graph.json")
    for concept_name, node in (graph.get("concepts") or {}).items():
        sources = node.get("sources", [])
        if source_matches_source_list(sources, source_name):
            concepts_with_source.add(concept_name)

    # Check each concept page
    for concept in concepts_with_source:
        path = CONCEPTS_DIR / f"{concept}.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")

        # Check if ## 边际变化 (exactly 2 #) section has entries from this source
        delta_match = re.search(r"^## 边际变化\s*\n+(.+?)(?=\n## |\Z)", text, re.MULTILINE | re.S)
        if delta_match and source_name in delta_match.group(1):
            # Determine if source is broker research
            is_broker = False

            # Check entity_exposures for source_quality
            exposures_for_concept = load_json("entity_exposures.json")
            for entity, ent in (exposures_for_concept.get("entities") or {}).items():
                for c, exp in (ent.get("concepts") or {}).items():
                    if c == concept and source_matches_source_list(exp.get("sources"), source_name):
                        sq = exp.get("source_quality", "")
                        if sq in BROKER_SOURCES:
                            is_broker = True
                            break

            # Also check concept_graph for source_quality
            if not is_broker:
                graph_node = (graph.get("concepts") or {}).get(concept, {})
                # If concept was created from this source and source name matches broker patterns
                log = graph_node.get("log", [])
                if any(source_name in entry for entry in log):
                    # Infer from source name pattern
                    broker_patterns = ["强势股脱水", "脱水研报", "评级日报", "早知道", "风口研报"]
                    if any(p in source_name for p in broker_patterns):
                        is_broker = True

            if is_broker:
                issue("consistency", f"concepts/{concept}",
                      f"## 边际变化 has entries from broker source {source_name} (should be ## 高信度研究线索)")


def check_entity_fact_hardness_routing(entity_name, concept, exp, source_name):
    """Rule 2: fact_hardness determines write location."""
    path = ENTITIES_DIR / f"{entity_name}.md"
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    loc = f"{entity_name}/{concept}"

    # Check if 边际变化 section exists and has entries from this source
    delta_match = re.search(r"## 边际变化\s*\n+(.+?)(?=\n## |\Z)", text, re.S)
    if delta_match and source_name in delta_match.group(1):
        hardness = exp.get("fact_hardness", "")
        source_quality = exp.get("source_quality", "")
        if hardness in {"research_claim", "market_narrative", "unknown", "legacy_rebuilt"}:
            issue("routing", loc,
                  f"fact_hardness={hardness} wrote to ## 边际变化 (should be ## 高信度研究线索 or graph_only)")
        if hardness == "review_candidate":
            issue("routing", loc,
                  "fact_hardness=review_candidate should write to ## 高信度研究线索, not ## 边际变化")
        if hardness == "hard_fact" and source_quality not in L3_SOURCES:
            issue("routing", loc,
                  f"hard_fact in 边际变化 requires L3 source, got source_quality={source_quality}")


def check_consistency_gates(entity_name, concept, exp, source_name):
    """Rule 3: update_type/fact_hardness/evidence_layer/source_quality consistency."""
    update_type = exp.get("update_type", "")
    hardness = exp.get("fact_hardness", "")
    evidence_layer = exp.get("evidence_layer", "")
    review_required = exp.get("review_required", False)
    source_quality = exp.get("source_quality", "")

    loc = f"{entity_name}/{concept}"

    # update_type + fact_hardness combo
    if update_type and hardness:
        allowed_hardness = UPDATE_TYPE_HARDNESS_MAP.get(update_type, set())
        if allowed_hardness and hardness not in allowed_hardness:
            issue("consistency", loc,
                  f"update_type={update_type} + fact_hardness={hardness} conflict")

    # evidence_layer + fact_hardness combo
    if evidence_layer == "L1_L3_candidate":
        if hardness not in {"review_candidate"}:
            issue("consistency", loc,
                  f"evidence_layer=L1_L3_candidate should pair with fact_hardness=review_candidate, got {hardness}")
        if not review_required:
            issue("consistency", loc,
                  "evidence_layer=L1_L3_candidate requires review_required=true")

    # research_claim should not be delta
    if hardness == "research_claim" and update_type == "delta":
        issue("consistency", loc,
              "fact_hardness=research_claim cannot be update_type=delta")

    # hard_fact requires L3 source (including empty source_quality)
    if hardness == "hard_fact":
        if not source_quality:
            issue("consistency", loc,
                  "fact_hardness=hard_fact requires source_quality to be set")
        elif source_quality not in L3_SOURCES:
            issue("consistency", loc,
                  f"fact_hardness=hard_fact requires source_quality in {L3_SOURCES}, got {source_quality}")

    # broker source should not be delta without hard_fact
    if source_quality in BROKER_SOURCES and update_type == "delta":
        if hardness not in {"hard_fact"}:
            issue("consistency", loc,
                  f"source_quality={source_quality} with update_type=delta requires fact_hardness=hard_fact")

    # missing source_quality warning
    if not source_quality:
        issue("consistency", loc, "source_quality is missing", severity="WARNING")

    # chain_layer validation
    chain_layer = exp.get("chain_layer", "")
    if not chain_layer:
        issue("consistency", loc, "chain_layer is missing")
    elif chain_layer not in VALID_CHAIN_LAYERS:
        issue("consistency", loc,
              f"chain_layer='{chain_layer}' not in valid enum {sorted(VALID_CHAIN_LAYERS)}")

    # graph_only validation
    if update_type == "graph_only":
        if hardness not in {"research_claim", "market_narrative", "unknown", "legacy_rebuilt", ""}:
            issue("consistency", loc,
                  f"graph_only should not have fact_hardness={hardness} (use research_claim/market_narrative/unknown)")
        strength = exp.get("strength", "")
        if strength in {"core", "related"}:
            issue("consistency", loc,
                  f"graph_only should not have strength={strength} (use peripheral)")
        if review_required:
            issue("consistency", loc,
                  "graph_only should not have review_required=true")


def check_role_quality(entity_name, concept, exp, source_name):
    """Rule 4: role must be specific, not generic or equal to chain_layer."""
    role = exp.get("role", "")
    chain_layer = exp.get("chain_layer", "")
    loc = f"{entity_name}/{concept}"

    if role in GENERIC_ROLES:
        issue("role", loc, f"role is too generic: '{role}'")
    if role in CHAIN_LAYER_VALUES:
        issue("role", loc, f"role equals chain_layer value: '{role}' (should be business description)")
    if not role:
        issue("role", loc, "role is empty")


def check_evidence_index_hardness(source_name):
    """Rule 7: evidence_index items should have fact_hardness."""
    evidence_db = load_json("evidence_index.json")
    for item in (evidence_db.get("items") or []):
        if source_matches_value(item.get("source"), source_name):
            if not item.get("fact_hardness"):
                issue("evidence", f"evidence_index/{item.get('target')}",
                      f"Missing fact_hardness for source={source_name}")
            if not item.get("source_quality"):
                issue("evidence", f"evidence_index/{item.get('target')}",
                      f"Missing source_quality for source={source_name}", severity="WARNING")


def check_source_note_classification(source_name, source_exposures):
    """Check source note sections match entity_exposures classification."""
    path = SOURCES_DIR / f"{source_name}.md"
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")

    # Build lookup: entity_name -> (update_type, strength)
    exposure_lookup = {}
    for entity_name, concept, exp in source_exposures:
        exposure_lookup[entity_name] = {
            "update_type": exp.get("update_type", ""),
            "strength": exp.get("strength", ""),
        }

    # Check 已更新实体 section
    updated_match = re.search(r"## 已更新实体\s*\n+(.+?)(?=\n## |\Z)", text, re.S)
    if updated_match:
        entities_in_section = re.findall(r"\[\[([^\]]+)\]\]", updated_match.group(1))
        for entity in entities_in_section:
            if entity in exposure_lookup:
                exp = exposure_lookup[entity]
                if exp["update_type"] == "graph_only":
                    issue("source", str(path),
                          f"[[{entity}]] in 已更新实体 but is graph_only (should be in 仅更新图谱)")

    # Check 仅更新图谱 section
    graph_match = re.search(r"## 仅更新图谱\s*\n+(.+?)(?=\n## |\Z)", text, re.S)
    if graph_match:
        # Extract entity names (may not have wikilinks)
        graph_text = graph_match.group(1)
        for entity_name, exp in exposure_lookup.items():
            if exp["update_type"] == "graph_only" and entity_name in graph_text:
                if exp["strength"] not in {"peripheral", ""}:
                    issue("source", str(path),
                          f"{entity_name} in 仅更新图谱 but strength={exp['strength']} (should be peripheral)")

    # Check 观察列表 section - entities should not be in entity_exposures unless graph_only
    watchlist_match = re.search(r"## 观察列表\s*\n+(.+?)(?=\n## |\Z)", text, re.S)
    if watchlist_match:
        watchlist_text = watchlist_match.group(1)
        for entity_name, exp in exposure_lookup.items():
            if entity_name in watchlist_text and exp["update_type"] not in {"graph_only", ""}:
                issue("source", str(path),
                      f"{entity_name} in 观察列表 but has exposure update_type={exp['update_type']}")


def check_evidence_index_coverage(source_name, source_exposures):
    """Rule 7b: Each entity exposure should have a corresponding evidence_index item."""
    evidence_db = load_json("evidence_index.json")

    # Build lookup of existing evidence items for this source
    existing_evidence = set()
    for item in (evidence_db.get("items") or []):
        if source_matches_value(item.get("source"), source_name):
            if item.get("target_type") == "entity":
                key = (item.get("target", ""), item.get("concept", ""))
                existing_evidence.add(key)

    # Check each exposure
    for entity_name, concept, exp in source_exposures:
        update_type = exp.get("update_type", "")
        # graph_only exposures may not need evidence_index
        if update_type == "graph_only":
            continue
        key = (entity_name, concept)
        if key not in existing_evidence:
            issue("evidence", f"{entity_name}/{concept}",
                  f"Missing evidence_index item for entity exposure (source={source_name})")


def check_entity_annotation(source_name, source_exposures):
    """Check curated_research entries have proper evidence annotations in entity markdown."""
    for entity_name, concept, exp in source_exposures:
        update_type = exp.get("update_type", "")
        hardness = exp.get("fact_hardness", "")
        sq = exp.get("source_quality", "")

        # Only check curated_research + review_candidate from broker sources
        if update_type != "curated_research":
            continue
        if hardness != "review_candidate":
            continue

        path = ENTITIES_DIR / f"{entity_name}.md"
        if not path.exists():
            continue

        text = path.read_text(encoding="utf-8")
        loc = f"{entity_name}/{concept}"

        # Find the source entry in entity markdown
        # Check if source appears in 高信度研究线索 section
        cr_match = re.search(r"^## 高信度研究线索\s*\n+(.+?)(?=\n## |\Z)", text, re.MULTILINE | re.S)
        if not cr_match:
            issue("annotation", loc,
                  f"curated_research entry for {source_name} but no ## 高信度研究线索 section in entity markdown")
            continue

        cr_text = cr_match.group(1)
        if source_name not in cr_text:
            # Source might be in 边际变化 instead
            delta_match = re.search(r"^## 边际变化\s*\n+(.+?)(?=\n## |\Z)", text, re.MULTILINE | re.S)
            if delta_match and source_name in delta_match.group(1):
                issue("annotation", loc,
                      f"curated_research entry for {source_name} in ## 边际变化 (should be ## 高信度研究线索)")
            continue

        # Check if annotation exists near the source entry
        # Find the section for this source
        source_section_pattern = rf"### [^|]*｜{re.escape(source_name)}.*?(?=\n### |\Z)"
        section_match = re.search(source_section_pattern, cr_text, re.S)
        if section_match:
            section_text = section_match.group(0)
            if "source_quality=" not in section_text:
                issue("annotation", loc,
                      f"Missing source_quality annotation in {source_name} entry")
            if "fact_hardness=" not in section_text:
                issue("annotation", loc,
                      f"Missing fact_hardness annotation in {source_name} entry")
            if "evidence_layer=" not in section_text:
                issue("annotation", loc,
                      f"Missing evidence_layer annotation in {source_name} entry")


def check_source_note_residual_contradictions(source_name):
    """Check for contradictions in source note sections."""
    path = SOURCES_DIR / f"{source_name}.md"
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")

    # Check: same entity in multiple sections
    sections_to_check = ["已更新实体", "仅更新图谱", "观察列表"]
    section_entities = {}
    for sec in sections_to_check:
        match = re.search(rf"## {sec}\s*\n+(.+?)(?=\n## |\Z)", text, re.S)
        if match:
            # Extract entity names (wikilinks or plain text before ：)
            entities = set()
            for line in match.group(1).split("\n"):
                line = line.strip()
                if line.startswith("- [["):
                    name = re.findall(r"\[\[([^\]]+)\]\]", line)
                    entities.update(name)
                elif line.startswith("- ") and "：" in line:
                    name = line[2:line.index("：")].strip()
                    entities.add(name)
            section_entities[sec] = entities

    # Check for overlaps
    all_pairs = [
        ("已更新实体", "仅更新图谱"),
        ("已更新实体", "观察列表"),
        ("仅更新图谱", "观察列表"),
    ]
    for sec1, sec2 in all_pairs:
        set1 = section_entities.get(sec1, set())
        set2 = section_entities.get(sec2, set())
        overlap = set1 & set2
        if overlap:
            for entity in overlap:
                issue("source", str(path),
                      f"[[{entity}]] appears in both {sec1} and {sec2}")

    # Check: 已更新概念 vs 跳过概念增量 contradiction
    updated_concepts = set()
    skipped_concepts = set()
    updated_match = re.search(r"## 已更新概念\s*\n+(.+?)(?=\n## |\Z)", text, re.S)
    if updated_match:
        updated_concepts = set(re.findall(r"\[\[([^\]]+)\]\]", updated_match.group(1)))
    skipped_match = re.search(r"## 跳过概念增量\s*\n+(.+?)(?=\n## |\Z)", text, re.S)
    if skipped_match:
        for line in skipped_match.group(1).split("\n"):
            for concept in updated_concepts:
                if concept in line and "concept not found" in line:
                    issue("source", str(path),
                          f"Contradiction: [[{concept}]] in both 已更新概念 and 跳过概念增量 (concept not found)")


def check_source_name_consistency(source_name):
    """Rule 8: source_name consistent across layers."""
    # Check source note exists
    source_path = SOURCES_DIR / f"{source_name}.md"
    if not source_path.exists():
        issue("consistency", str(source_path), "Source note missing")
        return

    # Check entity exposures
    source_exposures = find_entities_for_source(source_name)
    found_in_exposures = len(source_exposures) > 0

    # Check evidence index
    source_evidence = find_evidence_for_source(source_name)
    found_in_evidence = len(source_evidence) > 0

    # Check if source note has only watchlist (no exposures expected)
    text = source_path.read_text(encoding="utf-8")
    has_watchlist = bool(re.search(r"^## 观察列表", text, re.MULTILINE))
    has_updated_entities = bool(re.search(r"^## 已更新实体", text, re.MULTILINE))
    has_graph_only = bool(re.search(r"^## 仅更新图谱", text, re.MULTILINE))

    # Only flag error if source note claims updates but exposures are missing
    if not found_in_exposures and not found_in_evidence:
        if has_updated_entities or has_graph_only:
            issue("consistency", source_name,
                  "Source not found in entity_exposures or evidence_index but has 已更新实体/仅更新图谱")
        elif not has_watchlist:
            issue("consistency", source_name,
                  "Source not found in entity_exposures or evidence_index")


def check_graph_only_strength(entity_name, concept, exp, source_name):
    """Rule 6: graph_only entries should not be core/related without proper support."""
    strength = exp.get("strength", "")
    update_type = exp.get("update_type", "")
    if update_type == "graph_only" and strength in {"core", "related"}:
        issue("consistency", f"{entity_name}/{concept}",
              f"graph_only entry has strength={strength} (should be peripheral)")


def load_json(name):
    path = RELATIONS_DIR / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(name, data):
    RELATIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = RELATIONS_DIR / name
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 pdf_ingest_lint.py <source_name>")
        sys.exit(1)

    source_name = sys.argv[1]
    print(f"Running PDF ingest lint for: {source_name}")
    print("=" * 60)

    # Rule 1: Source note idempotency
    check_source_note_idempotency(source_name)

    # Scan ALL entity exposures that reference this source
    source_exposures = find_entities_for_source(source_name)
    print(f"Found {len(source_exposures)} entity/concept exposures for source")

    # Rules 2-4, 6: Per-exposure checks
    for entity_name, concept, exp in source_exposures:
        check_entity_fact_hardness_routing(entity_name, concept, exp, source_name)
        check_consistency_gates(entity_name, concept, exp, source_name)
        check_role_quality(entity_name, concept, exp, source_name)
        check_graph_only_strength(entity_name, concept, exp, source_name)

    # Rule 9: Markdown-level consistency
    check_concept_page_sections(source_name)
    check_entity_annotation(source_name, source_exposures)
    for entity_name, concept, exp in source_exposures:
        ut = exp.get("update_type", "")
        if ut in {"curated_research", "delta"}:
            check_entity_page_exists(entity_name, source_name)

    # Rule 7: Evidence index checks
    check_evidence_index_hardness(source_name)
    check_evidence_index_coverage(source_name, source_exposures)

    # Rule 7c: Reconcile evidence_index with entity_exposures
    if source_exposures:
        changed = reconcile_evidence_with_exposures(source_name)
        if changed:
            print(f"Reconciled {changed} evidence fields with entity_exposures")

    # Rule 8: Source name consistency
    check_source_name_consistency(source_name)

    # Rule 10: Source note classification consistency
    check_source_note_classification(source_name, source_exposures)

    # Rule 11: Source note residual contradictions
    check_source_note_residual_contradictions(source_name)

    # Report
    print()
    errors = [i for i in ISSUES if i["severity"] == "ERROR"]
    warnings = [i for i in ISSUES if i["severity"] == "WARNING"]

    if errors or warnings:
        print(f"ISSUES FOUND: {len(errors)} errors, {len(warnings)} warnings")
        print()
        for iss in ISSUES:
            marker = "ERROR" if iss["severity"] == "ERROR" else "WARN "
            print(f"  [{marker}] {iss['category']}: {iss['location']}")
            print(f"         {iss['message']}")
            print()

    # Scorecard summary
    print("--- SCORECARD ---")

    # Source note checks
    source_path = SOURCES_DIR / f"{source_name}.md"
    source_exists = source_path.exists()
    has_dupes = any(i["category"] == "source" for i in ISSUES)
    print(f"  Source note exists: {source_exists}")
    print(f"  Source note no duplicate sections: {not has_dupes}")

    # Exposure checks
    print(f"  Entity exposures scanned: {len(source_exposures)}")

    # Per-exposure details
    for entity_name, concept, exp in source_exposures:
        loc = f"{entity_name}/{concept}"
        cl = exp.get("chain_layer", "")
        role = exp.get("role", "")
        hardness = exp.get("fact_hardness", "")
        ut = exp.get("update_type", "")
        sq = exp.get("source_quality", "")
        el = exp.get("evidence_layer", "")

        chain_ok = cl in VALID_CHAIN_LAYERS
        role_ok = role not in GENERIC_ROLES and role not in CHAIN_LAYER_VALUES
        has_evidence = any(
            i.get("target") == entity_name and i.get("concept") == concept and i.get("target_type") == "entity"
            for i in find_evidence_for_source(source_name)
        )
        is_graph_only = ut == "graph_only"

        print(f"\n  [{loc}]")
        print(f"    chain_layer={cl} {'OK' if chain_ok else 'FAIL'}")
        print(f"    role={role[:60]}{'...' if len(role)>60 else ''} {'OK' if role_ok else 'FAIL'}")
        print(f"    source_quality={sq} fact_hardness={hardness}")
        print(f"    update_type={ut} evidence_layer={el}")
        if is_graph_only and not has_evidence:
            print(f"    evidence_index=N/A (graph_only exempt)")
        else:
            print(f"    evidence_index={'YES' if has_evidence else 'MISSING'}")

    # Evidence index coverage
    missing_ev = [f"{e}/{c}" for e, c, _ in source_exposures
                  if not any(i.get("target") == e and i.get("concept") == c and i.get("target_type") == "entity"
                             for i in find_evidence_for_source(source_name))
                  and _.get("update_type") != "graph_only"]
    print(f"\n  Evidence index coverage: {len(source_exposures) - len(missing_ev)}/{len(source_exposures)}")

    # Final verdict
    print()
    if not ISSUES:
        print("ALL CHECKS PASSED (0 errors, 0 warnings)")
        sys.exit(0)
    elif errors:
        print(f"FAILED: {len(errors)} errors")
        sys.exit(1)
    else:
        print(f"PASSED WITH WARNINGS: {len(warnings)} warnings")
        sys.exit(0)


if __name__ == "__main__":
    main()

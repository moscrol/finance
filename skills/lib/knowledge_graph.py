#!/usr/bin/env python3
"""Filesystem knowledge graph helpers for finance wiki ingest writers."""

import json
import os
import re
from datetime import date
from pathlib import Path


def _resolve_vault():
    for env in ("CONCEPT_VAULT", "ENTITY_VAULT"):
        value = os.environ.get(env)
        if value:
            return Path(os.path.expanduser(value))
    for cand in (
        Path(os.path.expanduser("~/Desktop/c c/知识库/wiki")),
        Path.home() / "repos" / "knowledge-base-private" / "wiki",
    ):
        if cand.exists():
            return cand
    return Path(os.path.expanduser("~/Desktop/c c/知识库/wiki"))


VAULT = _resolve_vault()
RELATIONS_DIR = VAULT / "relations"


def today():
    return date.today().isoformat()


def normalize_target(value):
    text = str(value or "").strip()
    while text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2].strip()
    if text.endswith(".md"):
        text = text[:-3]
    return text.strip()


def wikilink(value):
    target = normalize_target(value)
    return f"[[{target}]]" if target else ""


def safe_key(value):
    return normalize_target(value)


def load_json(name, default):
    RELATIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = RELATIONS_DIR / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(name, data):
    RELATIONS_DIR.mkdir(parents=True, exist_ok=True)
    data["updated"] = today()
    path = RELATIONS_DIR / name
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return str(path)


def default_concept_graph():
    return {"version": 1, "updated": today(), "concepts": {}, "relations": []}


def default_entity_exposures():
    return {"version": 1, "updated": today(), "entities": {}}


def default_aliases():
    return {"version": 1, "updated": today(), "aliases": {}}


def default_evidence_index():
    return {"version": 1, "updated": today(), "items": []}


def unique_append(items, item, keys):
    for old in items:
        if all(old.get(k) == item.get(k) for k in keys):
            old.update({k: v for k, v in item.items() if v not in ("", [], None)})
            return
    items.append(item)


def normalize_strength(value):
    value = str(value or "").strip().lower()
    if value in {"core", "核心"}:
        return "core"
    if value in {"peripheral", "边缘"}:
        return "peripheral"
    return "related"


def normalize_confidence(value):
    value = str(value or "").strip().lower()
    if value in {"high", "medium", "low"}:
        return value
    if value in {"高", "中", "低"}:
        return {"高": "high", "中": "medium", "低": "low"}[value]
    return "medium"


def company_name(company):
    if isinstance(company, str):
        return company.strip()
    return str(company.get("name") or company.get("company") or "").strip()


def company_code(company, ticker_map=None):
    if isinstance(company, dict):
        code = re.sub(r"\D", "", str(company.get("code", "")))
        if len(code) == 6:
            return code
    ticker_map = ticker_map or {}
    name = company_name(company)
    return ticker_map.get(name, "")


def company_role(company):
    if isinstance(company, dict):
        return str(company.get("role") or company.get("chain_role") or company.get("segment") or "受益标的").strip()
    return "受益标的"


def company_reason(company):
    if isinstance(company, dict):
        return str(company.get("reason") or company.get("evidence") or "").strip()
    return ""


def update_concept_graph(
    concept,
    *,
    source_name="",
    source_date="",
    parent_concepts=None,
    related_concepts=None,
    relationships=None,
    supply_chain=None,
    companies=None,
    ticker_map=None,
    evidence="",
    confidence="medium",
    aliases=None,
):
    concept = safe_key(concept)
    if not concept:
        return {}

    graph = load_json("concept_graph.json", default_concept_graph())
    alias_db = load_json("aliases.json", default_aliases())
    evidence_db = load_json("evidence_index.json", default_evidence_index())
    exposures = load_json("entity_exposures.json", default_entity_exposures())

    node = graph["concepts"].setdefault(concept, {
        "name": concept,
        "parents": [],
        "related_concepts": [],
        "supply_chain": {},
        "companies": [],
        "sources": [],
        "confidence": normalize_confidence(confidence),
    })
    if not isinstance(node.get("supply_chain"), dict):
        legacy = node.get("supply_chain") or []
        node["supply_chain"] = {"未分层": [str(v) for v in legacy]} if legacy else {}
    node["confidence"] = normalize_confidence(confidence or node.get("confidence"))
    if source_name:
        source_link = wikilink(source_name)
        if source_link not in node["sources"]:
            node["sources"].append(source_link)

    for parent in parent_concepts or []:
        parent = safe_key(parent)
        if parent and parent not in node["parents"]:
            node["parents"].append(parent)
        if parent:
            unique_append(graph["relations"], {
                "from": concept,
                "to": parent,
                "type": "上位概念",
                "source": wikilink(source_name),
                "confidence": normalize_confidence(confidence),
                "updated": today(),
            }, ["from", "to", "type"])

    relationships = relationships or {}
    for related in related_concepts or []:
        related = safe_key(related)
        if not related:
            continue
        if related not in node["related_concepts"]:
            node["related_concepts"].append(related)
        unique_append(graph["relations"], {
            "from": concept,
            "to": related,
            "type": relationships.get(related, "相关"),
            "source": wikilink(source_name),
            "confidence": normalize_confidence(confidence),
            "updated": today(),
        }, ["from", "to", "type"])

    if isinstance(supply_chain, dict):
        for layer, values in supply_chain.items():
            if isinstance(values, str):
                values = [v.strip() for v in re.split(r"[、,，/]+", values) if v.strip()]
            existing = node["supply_chain"].setdefault(str(layer), [])
            for item in values or []:
                item = str(item).strip()
                if item and item not in existing:
                    existing.append(item)

    ticker_map = ticker_map or {}
    for company in companies or []:
        name = company_name(company)
        if not name:
            continue
        code = company_code(company, ticker_map)
        strength = normalize_strength(company.get("tier", "") if isinstance(company, dict) else "")
        role = company_role(company)
        reason = company_reason(company)
        # Extract Theme Radar fields from company dict
        company_dict = company if isinstance(company, dict) else {}
        chain_layer = str(company_dict.get("chain_layer", "")).strip()
        source_quality = str(company_dict.get("source_quality", "")).strip()
        fact_hardness = str(company_dict.get("fact_hardness", "")).strip()
        evidence_layer = str(company_dict.get("evidence_layer", "")).strip()
        update_type = str(company_dict.get("update_type", "")).strip()
        review_required = bool(company_dict.get("review_required", False))

        item = {
            "name": name,
            "code": code,
            "role": role,
            "strength": strength,
            "reason": reason,
        }
        unique_append(node["companies"], item, ["name", "code"])

        ent = exposures["entities"].setdefault(name, {"name": name, "codes": [], "concepts": {}})
        if code and code not in ent["codes"]:
            ent["codes"].append(code)
        exp = ent["concepts"].setdefault(concept, {
            "role": role,
            "strength": strength,
            "evidence": "",
            "sources": [],
            "updated": today(),
        })
        exp.update({
            "role": role or exp.get("role"),
            "strength": strength or exp.get("strength"),
            "evidence": reason or exp.get("evidence", ""),
            "updated": today(),
        })
        # Apply Theme Radar fields
        if chain_layer:
            exp["chain_layer"] = chain_layer
        if source_quality:
            exp["source_quality"] = source_quality
        if fact_hardness:
            exp["fact_hardness"] = fact_hardness
        if evidence_layer:
            exp["evidence_layer"] = evidence_layer
        if update_type:
            exp["update_type"] = update_type
        if review_required:
            exp["review_required"] = True
        if source_name:
            source_link = wikilink(source_name)
            if source_link not in exp["sources"]:
                exp["sources"].append(source_link)

    for alias in aliases or []:
        alias = str(alias).strip()
        if alias and alias != concept:
            alias_db["aliases"][alias] = concept

    if evidence:
        unique_append(evidence_db["items"], {
            "source": wikilink(source_name),
            "source_date": source_date,
            "target_type": "concept",
            "target": concept,
            "evidence": str(evidence).strip(),
            "confidence": normalize_confidence(confidence),
        }, ["source", "target_type", "target", "evidence"])

    return {
        "concept_graph": write_json("concept_graph.json", graph),
        "entity_exposures": write_json("entity_exposures.json", exposures),
        "aliases": write_json("aliases.json", alias_db),
        "evidence_index": write_json("evidence_index.json", evidence_db),
    }


def update_entity_exposures(
    entity,
    *,
    code="",
    concepts=None,
    source_name="",
    source_date="",
    role="",
    strength="",
    evidence="",
    confidence="",
    chain_layer="",
    evidence_layer="",
    update_type="",
    fact_hardness="",
    source_quality="",
    review_required=False,
):
    entity = safe_key(entity)
    if not entity:
        return {}

    exposures = load_json("entity_exposures.json", default_entity_exposures())
    evidence_db = load_json("evidence_index.json", default_evidence_index())
    ent = exposures["entities"].setdefault(entity, {"name": entity, "codes": [], "concepts": {}})
    code = re.sub(r"\D", "", str(code or ""))
    if len(code) == 6 and code not in ent["codes"]:
        ent["codes"].append(code)

    for concept in concepts or []:
        concept = safe_key(concept)
        if not concept:
            continue
        exp = ent["concepts"].setdefault(concept, {"role": "受益标的", "strength": "related", "evidence": "", "sources": [], "updated": today()})
        incoming_update_type = str(update_type or "").strip()
        existing_update_type = str(exp.get("update_type") or "").strip()
        protect_existing = incoming_update_type == "baseline" and existing_update_type in {"curated_research", "delta", "hard_delta"}
        if protect_existing:
            exp["updated"] = today()
            if confidence and not exp.get("confidence"):
                exp["confidence"] = normalize_confidence(confidence)
            if chain_layer and not exp.get("chain_layer"):
                exp["chain_layer"] = str(chain_layer).strip()
            if evidence_layer and not exp.get("evidence_layer"):
                exp["evidence_layer"] = str(evidence_layer).strip()
        else:
            patch = {
                "role": str(role or exp.get("role") or "受益标的"),
                "strength": normalize_strength(strength or exp.get("strength")),
                "evidence": str(evidence or exp.get("evidence", "")).strip(),
                "updated": today(),
            }
            if confidence or not exp.get("confidence"):
                patch["confidence"] = normalize_confidence(confidence or exp.get("confidence"))
            if chain_layer:
                patch["chain_layer"] = str(chain_layer).strip()
            if evidence_layer:
                patch["evidence_layer"] = str(evidence_layer).strip()
            if update_type:
                patch["update_type"] = incoming_update_type
            if fact_hardness:
                patch["fact_hardness"] = str(fact_hardness).strip()
            if source_quality:
                patch["source_quality"] = str(source_quality).strip()
            if review_required:
                patch["review_required"] = True
            exp.update(patch)
        if source_name:
            source_link = wikilink(source_name)
            if source_link not in exp["sources"]:
                exp["sources"].append(source_link)
        if evidence:
            item = {
                "source": wikilink(source_name),
                "source_date": source_date,
                "target_type": "entity",
                "target": entity,
                "concept": concept,
                "evidence": str(evidence).strip(),
                "confidence": normalize_confidence(confidence),
            }
            if chain_layer:
                item["chain_layer"] = str(chain_layer).strip()
            if evidence_layer:
                item["evidence_layer"] = str(evidence_layer).strip()
            if update_type:
                item["update_type"] = str(update_type).strip()
            if fact_hardness:
                item["fact_hardness"] = str(fact_hardness).strip()
            if source_quality:
                item["source_quality"] = str(source_quality).strip()
            if review_required:
                item["review_required"] = True
            unique_append(evidence_db["items"], item, ["source", "target_type", "target", "concept", "evidence"])

    return {
        "entity_exposures": write_json("entity_exposures.json", exposures),
        "evidence_index": write_json("evidence_index.json", evidence_db),
    }

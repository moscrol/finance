#!/usr/bin/env python3
"""Draft a theme-radar supplement pool from raw notes (theme-agnostic).

This is intentionally conservative: it produces a *reviewable draft* of the
`theme_supplement_pool` JSON that ``radar.py`` consumes
(``build_theme_supplement_pool_context``), not a finished research result.

Two sources are combined:

1. The knowledge base (``concept_graph.json`` + ``entity_exposures.json`` under
   ``<vault>/relations``) supplies the *theme-specific* skeleton — which
   sub-directions belong to the term and which companies sit on each, with
   strength / role / chain-layer. This replaces the previous hard-coded
   PCB/mSAP rules so the tool works for any theme (CPO, 硅光, 固态电池, ...).
2. The raw input text supplies the *evidence* layer — definition, mention
   frequency per direction, catalysts (time windows) and validation items.

Output schema (matches radar.py consumer):

    theme, generated_at, source_file, summary,
    definition_profile, demand_scenarios, material_process_scan,
    industry_chain_panorama, recognition_timeline, progress_ruler,
    action_plan, validation_items, catalyst_calendar, evidence_items,
    extraction_quality

``recognition_timeline`` / ``progress_ruler`` / ``action_plan`` are emitted as
empty lists on purpose — those are higher-conviction outputs that an agent
should fill in after review (they are the next optimization stage), and the
rule layer must not fabricate them.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
from pathlib import Path


def _default_vault() -> Path:
    for var in ("KB_VAULT", "KNOWLEDGE_WIKI", "CONCEPT_VAULT", "ENTITY_VAULT"):
        val = os.environ.get(var)
        if val:
            return Path(os.path.expanduser(val))
    return Path.home() / "knowledge-base-private" / "wiki"


DEFAULT_VAULT = _default_vault()

# Map knowledge-base supply-chain bucket keys / entity chain_layer prefixes to
# human-readable Chinese labels used in the rendered report.
CHAIN_LABELS = {
    "upstream_materials": "上游材料",
    "upstream_equipment": "上游设备",
    "upstream_components": "上游零部件/光芯片",
    "midstream": "中游制造",
    "midstream_manufacturing": "中游制造",
    "midstream_components": "中游器件",
    "downstream": "下游应用",
    "downstream_infrastructure": "下游基础设施",
}

STRENGTH_ORDER = {"core": 0, "related": 1, "peripheral": 2, "": 3, None: 3}

TIME_PATTERNS = [
    r"(6月|7月|8月|9月|10月|11月|12月|Q[1-4]|202[5-9]年|今年|明年|后年|下半年|上半年|年底|年内)[:：]?\s*([^。\n；;]{4,60})",
]

VALIDATION_KEYS = [
    "是否", "验证", "订单", "中标", "涨价", "认证", "送样", "供货", "量产",
    "扩产", "产线", "产能", "收入占比", "毛利", "良率", "确收", "落地", "放量",
]

# Words that signal *hard fact* vs *soft projection* vs *noise* — used only to
# tag evidence_type, not to filter (filtering is the agent's job on review).
HARD_FACT_KEYS = ["订单", "中标", "合同", "入股", "持股", "公告", "确收", "供货", "签署", "收购", "增资"]
SOFT_KEYS = ["目标", "预期", "预计", "看好", "空间", "市值", "有望", "弹性", "或将", "假设"]


def unique(items):
    out, seen = [], set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def contains_any(text: str, words: list[str]) -> bool:
    lowered = text.lower()
    return any(word and word.lower() in lowered for word in words)


def split_sentences(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for part in re.split(r"[。；;\n]\s*", line):
            part = part.strip(" 　-□*•·")
            if part:
                out.append(part)
    return out


def short_hits(sentences: list[str], words: list[str], limit: int = 3) -> list[str]:
    hits = []
    for s in sentences:
        if contains_any(s, words):
            hits.append(s[:90])
        if len(hits) >= limit:
            break
    return hits


def load_json(path: Path, default):
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def load_relations(vault: Path) -> tuple[dict, dict]:
    relations = vault / "relations"
    concept_graph = load_json(relations / "concept_graph.json", {})
    entity_exposures = load_json(relations / "entity_exposures.json", {})
    concepts = concept_graph.get("concepts", {}) if isinstance(concept_graph, dict) else {}
    entities = entity_exposures.get("entities", {}) if isinstance(entity_exposures, dict) else {}
    return concepts, entities


def match_concept(term: str, concepts: dict) -> str:
    if not concepts:
        return term
    if term in concepts:
        return term
    lowered = term.lower()
    # case-insensitive exact
    for key in concepts:
        if key.lower() == lowered:
            return key
    # term is a substring of a concept key (prefer shortest match)
    candidates = [key for key in concepts if lowered in key.lower() or key.lower() in lowered]
    if candidates:
        return min(candidates, key=len)
    return term


def aliases_for(term_key: str, concepts: dict) -> list[str]:
    """Tokens used to detect mentions of a direction in free text."""
    toks = {term_key}
    node = concepts.get(term_key, {})
    for parent in node.get("parents", []) if isinstance(node, dict) else []:
        toks.add(parent)
    # split CamelCase / mixed alnum like "1.6T CPO" -> also add "CPO"
    for piece in re.split(r"[\s/、，,]", term_key):
        piece = piece.strip()
        if len(piece) >= 2:
            toks.add(piece)
    return [t for t in toks if t]


def directions_for(term_key: str, concepts: dict) -> list[str]:
    """Sub-directions for a theme, sourced from the knowledge graph."""
    node = concepts.get(term_key, {})
    if not isinstance(node, dict):
        return []
    out = []
    for rel in node.get("related_concepts", []) or []:
        if rel and rel != term_key:
            out.append(rel)
    # supplement with midstream supply-chain stages (often the real "工艺/方向")
    chain = node.get("supply_chain", {}) if isinstance(node.get("supply_chain"), dict) else {}
    for stage in chain.get("midstream", []) or []:
        out.append(stage)
    return unique(out)


def chain_bucket_of(direction: str, term_key: str, concepts: dict) -> str:
    """Locate a direction within the theme's supply_chain buckets."""
    node = concepts.get(term_key, {})
    chain = node.get("supply_chain", {}) if isinstance(node, dict) else {}
    if isinstance(chain, dict):
        for bucket, members in chain.items():
            for m in members or []:
                if m and (m in direction or direction in m):
                    return CHAIN_LABELS.get(bucket, bucket)
    return ""


def companies_for_direction(direction: str, concepts: dict, entities: dict, limit: int = 8) -> tuple[list[str], str]:
    """Return (representative_entity_names, dominant_chain_layer_label).

    Primary source: reverse index in entity_exposures (richer). Fallback:
    companies listed directly on the concept node in concept_graph.
    """
    rows = []  # (strength_rank, name, chain_layer)
    for name, info in entities.items():
        if name == "ALL" or not isinstance(info, dict):
            continue
        cmap = info.get("concepts", {})
        if not isinstance(cmap, dict) or direction not in cmap:
            continue
        rel = cmap[direction] or {}
        strength = rel.get("strength")
        rows.append((STRENGTH_ORDER.get(strength, 3), name, rel.get("chain_layer") or ""))
    rows.sort(key=lambda r: r[0])

    if not rows:
        # fallback: concept_graph node companies
        node = concepts.get(direction, {})
        for c in (node.get("companies", []) if isinstance(node, dict) else []):
            if not isinstance(c, dict):
                continue
            rows.append((STRENGTH_ORDER.get(c.get("strength"), 3), c.get("name", ""), ""))
        rows.sort(key=lambda r: r[0])

    names = unique([r[1] for r in rows if r[1]])[:limit]
    # dominant chain layer among the kept companies
    layer = ""
    for r in rows:
        if r[2]:
            layer = CHAIN_LABELS.get(r[2], r[2])
            break
    return names, layer


DEFINITION_CUES = [
    "技术", "材料", "方案", "器件", "封装", "工艺", "集成", "芯片", "设备",
    "光学", "架构", "互联", "模块", "系统", "路线",
]


def infer_definition(term: str, sentences: list[str]) -> str:
    """Return a definition only if the text genuinely defines the term:
    the term must be immediately followed (within a short window) by a
    copula (是/指/为/即) and the sentence must carry a domain noun cue.
    Otherwise return "" — radar.py will fall back to the KB concept page,
    which is more reliable than grabbing a random commentary sentence."""
    pattern = re.compile(rf"{re.escape(term)}[（(][^)）]*[)）]?[^，。\n]{{0,6}}(?:是|指|为|即)|{re.escape(term)}[^，。\n]{{0,6}}(?:是|指|为|即)", re.I)
    for s in sentences:
        if 8 <= len(s) <= 160 and pattern.search(s) and any(cue in s for cue in DEFINITION_CUES):
            return s.strip(" ，。：:")
    return ""


def frequency_label(count: int) -> str:
    if count >= 3:
        return "高频"
    if count >= 1:
        return "中频"
    return "低频"


def cognition_label(count: int) -> str:
    if count >= 3:
        return "L2-L3（已被多条资料确认）"
    if count >= 1:
        return "L1-L2（资料提及，待加强）"
    return "L0-L1（图谱关联，文本未提）"


def classify(count: int) -> str:
    return "发酵" if count >= 1 else "布局"


def evidence_kind(hits: list[str]) -> str:
    joined = " ".join(hits)
    if contains_any(joined, HARD_FACT_KEYS):
        return "hard_fact"
    if contains_any(joined, SOFT_KEYS):
        return "soft_projection"
    return "source" if hits else "inferred"


def build_material_process_scan(term_key: str, concepts: dict, entities: dict, sentences: list[str]) -> list[dict]:
    rows = []
    for direction in directions_for(term_key, concepts):
        alias = aliases_for(direction, concepts)
        hits = short_hits(sentences, alias, limit=3)
        count = sum(1 for s in sentences if contains_any(s, alias))
        names, layer = companies_for_direction(direction, concepts, entities)
        chain_position = layer or chain_bucket_of(direction, term_key, concepts)
        rows.append({
            "name": direction,
            "major_track": term_key,
            "chain_position": chain_position or "待补",
            "prosperity_judgment": hits[0] if hits else "",
            "daily_review_frequency": frequency_label(count),
            "cognition_level": cognition_label(count),
            "classification": classify(count),
            "core_catalyst": hits[0] if hits else "",
            "next_validation": "订单/客户认证/出货量或价格信号",
            "representative_entities": names,
            "evidence": hits[:2],
            "evidence_type": evidence_kind(hits),
        })
    # stable order: 发酵 first, then by mention frequency
    freq_rank = {"高频": 0, "中频": 1, "低频": 2}
    rows.sort(key=lambda r: (0 if r["classification"] == "发酵" else 1, freq_rank.get(r["daily_review_frequency"], 3)))
    return rows


def infer_demand_scenarios(term_key: str, concepts: dict, entities: dict, sentences: list[str]) -> list[dict]:
    node = concepts.get(term_key, {})
    chain = node.get("supply_chain", {}) if isinstance(node, dict) else {}
    downstream = chain.get("downstream", []) if isinstance(chain, dict) else []
    rows = []
    for scenario in unique(downstream):
        alias = aliases_for(scenario, concepts)
        hits = short_hits(sentences, alias, limit=2)
        names, _ = companies_for_direction(scenario, concepts, entities, limit=6)
        rows.append({
            "scenario": scenario,
            "downstream_driver": hits[0] if hits else "",
            "beneficiary_links": [],
            "representative_entities": names,
            "evidence": hits[:2],
            "evidence_type": evidence_kind(hits),
        })
    return rows


def infer_catalyst_calendar(sentences: list[str], directions: list[str]) -> list[dict]:
    rows = []
    text = "\n".join(sentences)
    for m in re.finditer(TIME_PATTERNS[0], text):
        window, event = m.group(1), m.group(2).strip()
        if not event:
            continue
        direction = ""
        for d in directions:
            if d and (d in event):
                direction = d
                break
        rows.append({
            "direction": direction,
            "time_window": window,
            "event": event[:80],
            "event_type": "hard" if contains_any(event, HARD_FACT_KEYS) else ("soft" if contains_any(event, SOFT_KEYS) else "信号"),
            "evidence_summary": event[:80],
            "next_watch": "验证订单/价格/客户认证/产能变化",
            "source": "user_input",
            "source_date": "",
            "item_id": "",
        })
        if len(rows) >= 12:
            break
    return rows


def infer_validation_items(sentences: list[str], directions: list[str]) -> list[dict]:
    rows = []
    for s in sentences:
        if not any(k in s for k in VALIDATION_KEYS):
            continue
        direction = ""
        for d in directions:
            if d and d in s:
                direction = d
                break
        rows.append({
            "direction": direction,
            "item": s[:100],
            "validation_window": "",
            "upgrade_condition": "出现订单/客户认证/出货或价格的硬证据",
            "downgrade_condition": "证伪或长期无进展",
            "status": "待验证",
            "validation_type": "hard_fact" if contains_any(s, HARD_FACT_KEYS) else "soft_projection",
            "source": "user_input",
            "source_date": "",
            "item_id": "",
        })
        if len(rows) >= 12:
            break
    return rows


def extraction_quality(pool: dict, concept_matched: bool) -> dict:
    tracked = ["demand_scenarios", "material_process_scan", "validation_items", "catalyst_calendar"]
    total = source_backed = inferred = 0
    missing = []
    for field in tracked:
        rows = pool.get(field) or []
        if not rows:
            missing.append(field)
            continue
        total += len(rows)
        for row in rows:
            et = row.get("evidence_type") if isinstance(row, dict) else None
            if et in ("source", "hard_fact", "soft_projection"):
                source_backed += 1
            else:
                inferred += 1
    return {
        "mode": "rule_draft_v2_theme_agnostic",
        "concept_matched": concept_matched,
        "total_items": total,
        "source_backed_items": source_backed,
        "inferred_items": inferred,
        "missing_fields": missing,
        "review_required": True,
    }


def build_context(term: str, text: str, vault: Path) -> dict:
    concepts, entities = load_relations(vault)
    term_key = match_concept(term, concepts)
    concept_matched = term_key in concepts
    sentences = split_sentences(text)

    material_process_scan = build_material_process_scan(term_key, concepts, entities, sentences)
    directions = [r["name"] for r in material_process_scan]
    demand_scenarios = infer_demand_scenarios(term_key, concepts, entities, sentences)
    catalyst_calendar = infer_catalyst_calendar(sentences, directions)
    validation_items = infer_validation_items(sentences, directions)

    pool = {
        "theme": term_key,
        "term": term,
        "generated_at": _dt.date.today().isoformat(),
        "source_file": "",
        "summary": {
            "row_count": len(material_process_scan),
            "company_count": len(unique(sum((r.get("representative_entities", []) for r in material_process_scan), []))),
        },
        "definition_profile": {
            "definition": infer_definition(term, sentences),
            "aliases": aliases_for(term_key, concepts),
        },
        "demand_scenarios": demand_scenarios,
        "material_process_scan": material_process_scan,
        "industry_chain_panorama": [],
        "recognition_timeline": [],
        "progress_ruler": [],
        "action_plan": [],
        "validation_items": validation_items,
        "catalyst_calendar": catalyst_calendar,
        "evidence_items": [],
        "raw_extraction_note": (
            "规则抽取草稿 v2（题材无关，骨架取自知识库 concept_graph/entity_exposures，"
            "证据取自原文）。recognition_timeline/progress_ruler/action_plan 需人工/LLM 复核补充，"
            "规则层不臆造。"
        ),
    }
    pool["extraction_quality"] = extraction_quality(pool, concept_matched)
    return pool


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a draft theme_supplement_pool JSON from text notes (theme-agnostic)."
    )
    parser.add_argument("--term", required=True)
    parser.add_argument("--input", required=True, help="raw text file")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="wiki vault path (reads <vault>/relations)")
    parser.add_argument("--out", help="optional JSON output")
    args = parser.parse_args()

    text = Path(args.input).expanduser().read_text(encoding="utf-8")
    vault = Path(args.vault).expanduser()
    data = build_context(args.term, text, vault)
    data["source_file"] = str(Path(args.input).expanduser())
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(str(out))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

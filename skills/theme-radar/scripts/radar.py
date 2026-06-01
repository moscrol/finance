#!/usr/bin/env python3
"""Read-only theme radar report from the finance wiki relation graph."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROJECT_SCRIPTS = PROJECT_ROOT / "scripts"
if str(PROJECT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_SCRIPTS))

import theme_radar_quality_rules as quality_rules

try:
    import build_theme_evidence_readiness as readiness_builder
except Exception:
    readiness_builder = None


DEFAULT_VAULT = Path(os.path.expanduser(os.environ.get("CONCEPT_VAULT", "~/Desktop/c c/知识库/wiki")))
RELATION_FILES = {
    "concept_graph": "concept_graph.json",
    "entity_exposures": "entity_exposures.json",
    "aliases": "aliases.json",
    "evidence_index": "evidence_index.json",
    "theme_signals": "theme_signals.json",
    "pattern_library": "pattern_library.json",
    "report_contexts": "report_contexts.json",
}
STRENGTH_RANK = {"core": 0, "related": 1, "peripheral": 2}
EVIDENCE_BUCKETS = ("baseline", "curated_research", "delta", "graph_only", "missing")
EVIDENCE_WEIGHTS = {"delta": 4, "curated_research": 3, "baseline": 2, "graph_only": 1, "missing": -1}
SUBTYPE_RANK = {
    "core_subject": 0,
    "component_supplier": 1,
    "service_provider": 2,
    "upstream_equipment": 3,
    "upstream_materials": 4,
    "downstream_channel": 5,
    "ecosystem": 6,
    "weak_graph": 7,
    "unknown": 8,
}
SUBTYPE_LABELS = {
    "core_subject": "核心主体",
    "component_supplier": "核心部件/产品供应商",
    "service_provider": "服务/平台商",
    "upstream_equipment": "上游设备",
    "upstream_materials": "上游材料",
    "downstream_channel": "下游渠道/运营",
    "ecosystem": "生态/配套",
    "weak_graph": "弱图谱关联",
    "unknown": "待判定",
}


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"JSON 读取失败: {path}\n{exc}") from exc


def strip_wikilink(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("[[") and text.endswith("]]"):
        return text[2:-2].strip()
    return text


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def context_term_hit(needle: str, haystack: str) -> bool:
    needle_norm = normalize(needle)
    haystack_norm = normalize(haystack)
    if not needle_norm or not haystack_norm:
        return False
    if re.search(r"[a-z0-9]", needle_norm):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(needle_norm)}(?![a-z0-9])", haystack_norm))
    return needle_norm in haystack_norm


def split_terms(text: str) -> list[str]:
    raw = re.split(r"[\s,，、/｜|;；:：()（）《》“”\"'【】\[\]]+", text)
    terms = [x.strip() for x in raw if x.strip()]
    terms.extend(x for x in re.findall(r"[A-Za-z][A-Za-z0-9+-]*", text or "") if len(x) >= 3)
    return unique(terms)


def resolve_query(term: str, aliases: dict, concepts: dict) -> tuple[str, list[str], list[str]]:
    alias_map = aliases.get("aliases", {}) if isinstance(aliases, dict) else {}
    candidates = []
    notes = []

    if term in alias_map:
        candidates.append(alias_map[term])
        notes.append(f"命中别名：{term} -> {alias_map[term]}")

    term_norm = normalize(term)
    concept_names = list(concepts)
    norm_to_name = {normalize(name): name for name in concept_names}
    if term_norm in norm_to_name:
        candidates.append(norm_to_name[term_norm])

    exact_token_norms = set()
    tokens = split_terms(term)
    for token in tokens:
        if token in alias_map:
            candidates.append(alias_map[token])
        token_norm = normalize(token)
        if token_norm in norm_to_name:
            candidates.append(norm_to_name[token_norm])
            exact_token_norms.add(token_norm)

    for token in tokens:
        token_norm = normalize(token)
        if token_norm in exact_token_norms or len(token_norm) < 3 or not re.search(r"[a-z]", token_norm):
            continue
        for name in concept_names:
            n = normalize(name)
            if token_norm in n:
                candidates.append(name)

    if not candidates:
        for name in concept_names:
            n = normalize(name)
            if term_norm and (term_norm in n or n in term_norm):
                candidates.append(name)
            elif any(normalize(token) in n or n in normalize(token) for token in split_terms(term) if len(token) >= 2):
                candidates.append(name)

    seen = set()
    unique = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)

    primary = unique[0] if unique else term.strip()
    return primary, unique[:8], notes


def relation_neighbors(graph: dict, concept: str) -> list[dict]:
    rows = []
    for rel in graph.get("relations", []):
        src = rel.get("from")
        dst = rel.get("to")
        if src == concept or dst == concept:
            other = dst if src == concept else src
            rows.append(
                {
                    "concept": other,
                    "direction": "out" if src == concept else "in",
                    "type": rel.get("type", "相关"),
                    "source": rel.get("source", ""),
                    "confidence": rel.get("confidence", "medium"),
                }
            )
    return rows


def collect_companies(concepts: list[str], graph: dict, exposures: dict) -> list[dict]:
    by_key = {}

    for concept in concepts:
        node = graph.get("concepts", {}).get(concept, {})
        for company in node.get("companies", []):
            name = company.get("name", "")
            code = company.get("code", "")
            if not name:
                continue
            key = (name, code)
            item = by_key.setdefault(
                key,
                {
                    "name": name,
                    "code": code,
                    "strength": company.get("strength", "related"),
                    "roles": [],
                    "concepts": [],
                    "evidence": [],
                    "sources": [],
                    "chain_layers": [],
                    "evidence_layers": [],
                    "update_types": [],
                    "fact_hardness": [],
                    "source_quality": [],
                    "review_required": False,
                    "evidence_buckets": empty_evidence_buckets(),
                },
            )
            item["concepts"].append(concept)
            if company.get("role"):
                item["roles"].append(company["role"])
            if company.get("reason"):
                item["evidence"].append(company["reason"])
                add_evidence_bucket(item, "graph_only", concept, company["reason"], "")

    exposure_entities = exposures.get("entities", {}) if isinstance(exposures, dict) else {}
    concept_set = set(concepts)
    for name, ent in exposure_entities.items():
        ent_concepts = ent.get("concepts", {})
        matched = concept_set & set(ent_concepts)
        if not matched:
            continue
        codes = ent.get("codes", []) or [""]
        code = codes[0] if codes else ""
        key = (name, code)
        item = by_key.setdefault(
            key,
            {
                "name": name,
                "code": code,
                "strength": "related",
                "roles": [],
                "concepts": [],
                "evidence": [],
                "sources": [],
                "chain_layers": [],
                "evidence_layers": [],
                "update_types": [],
                "fact_hardness": [],
                "source_quality": [],
                "review_required": False,
                "evidence_buckets": empty_evidence_buckets(),
            },
        )
        for concept in matched:
            exp = ent_concepts.get(concept, {})
            item["concepts"].append(concept)
            item["strength"] = min_strength(item["strength"], exp.get("strength", "related"))
            if exp.get("role"):
                item["roles"].append(exp["role"])
            if exp.get("evidence"):
                item["evidence"].append(exp["evidence"])
                for bucket in buckets_for_exposure(exp):
                    add_evidence_bucket(
                        item,
                        bucket,
                        concept,
                        exp.get("evidence"),
                        "、".join(exp.get("sources", []) or []),
                    )
            if exp.get("chain_layer"):
                item["chain_layers"].append(exp["chain_layer"])
            if exp.get("evidence_layer"):
                item["evidence_layers"].append(exp["evidence_layer"])
            if exp.get("update_type"):
                item["update_types"].append(exp["update_type"])
            if exp.get("fact_hardness"):
                item["fact_hardness"].append(exp["fact_hardness"])
            if exp.get("source_quality"):
                item["source_quality"].append(exp["source_quality"])
            if exp.get("review_required"):
                item["review_required"] = True
            for source in exp.get("sources", []) or []:
                item["sources"].append(source)

    for item in by_key.values():
        for field in ("roles", "concepts", "evidence", "sources", "chain_layers", "evidence_layers", "update_types", "fact_hardness", "source_quality"):
            item[field] = unique(item[field])
        if should_force_peripheral(item):
            item["strength"] = "peripheral"
        item["company_subtype"] = company_subtype(item)

    return sorted(
        by_key.values(),
        key=company_sort_key,
    )


def min_strength(a: str, b: str) -> str:
    return a if STRENGTH_RANK.get(a, 1) <= STRENGTH_RANK.get(b, 1) else b


def unique(items: list[str]) -> list[str]:
    out = []
    seen = set()
    for item in items:
        item = str(item or "").strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def empty_evidence_buckets() -> dict:
    return {key: [] for key in EVIDENCE_BUCKETS}


def bucket_for_update_type(update_type: str | None) -> str:
    value = str(update_type or "").strip()
    if value in EVIDENCE_BUCKETS:
        return value
    return "missing"


def is_explicit_weak_graph_only(data: dict) -> bool:
    update_type = str(data.get("update_type") or "").strip()
    fact_hardness = str(data.get("fact_hardness") or "").strip()
    evidence = str(data.get("evidence") or "")
    return (
        update_type == "graph_only"
        or fact_hardness == "legacy_rebuilt"
        or "从既有entity markdown重建" in evidence
        or "从既有concept markdown重建" in evidence
    )


def buckets_for_exposure(exp: dict) -> list[str]:
    buckets = []
    update_type = str(exp.get("update_type") or "").strip()
    if update_type == "hard_delta":
        buckets.append("delta")
    if update_type in EVIDENCE_BUCKETS:
        buckets.append(update_type)
    if update_type == "baseline":
        buckets.append("baseline")
    sources = " ".join(str(x) for x in exp.get("sources", []) or [])
    if "iFinD baseline" in sources or "AkShare baseline" in sources or "Baseline" in sources:
        buckets.append("baseline")
    if not is_explicit_weak_graph_only(exp) and any(token in sources for token in ("市场逻辑", "强势股", "评级日报", "复盘", "脱水")):
        buckets.append("delta")
    if not buckets:
        buckets.append("missing")
    return unique(buckets)


def add_evidence_bucket(company: dict, bucket: str, concept: str, evidence: str, source: str) -> None:
    bucket = bucket if bucket in EVIDENCE_BUCKETS else "missing"
    text = str(evidence or "").strip()
    if not text:
        return
    concept_text = str(concept or "").strip()
    source_text = str(source or "").strip()
    row = f"{concept_text}：{text}" if concept_text else text
    if source_text:
        row = f"{row}（{source_text}）"
    buckets = company.setdefault("evidence_buckets", empty_evidence_buckets())
    if row not in buckets[bucket]:
        buckets[bucket].append(row)


def company_evidence_score(company: dict) -> int:
    buckets = company.get("evidence_buckets", {}) or {}
    score = 0
    for bucket, weight in EVIDENCE_WEIGHTS.items():
        if buckets.get(bucket):
            score += weight
    score += quality_rules.evidence_score_adjustment(company)
    if is_generic_company_hit(company):
        score -= 2
    return score


def company_subtype(company: dict) -> str:
    text = evidence_text(company)
    role_text = " ".join(str(x) for x in company.get("roles", []) or [])
    layers = " ".join(str(x) for x in company.get("chain_layers", []) or [])
    buckets = company.get("evidence_buckets", {}) or {}
    has_non_graph_evidence = any(buckets.get(x) for x in ("baseline", "curated_research", "delta"))
    has_direct_signal = any(buckets.get(x) for x in ("curated_research", "delta"))
    if any(x in role_text for x in ("弱相关", "待验证", "潜在相关")) and not has_direct_signal:
        return "weak_graph"
    if (("图谱弱关联" in role_text or "从既有entity markdown重建" in role_text) and not has_direct_signal) or (buckets.get("graph_only") and not has_non_graph_evidence):
        return "weak_graph"
    optical_component_tokens = ("光芯片", "激光器芯片", "探测器芯片", "PLC", "AWG", "EML", "VCSEL", "CWLaser", "光模块", "光收发模块", "光器件", "硅光", "光引擎", "无源光器件")
    if any(x in role_text for x in optical_component_tokens) or any(x in text for x in optical_component_tokens):
        return "component_supplier"
    if any(x in role_text for x in ("设备", "装备", "制药装备", "刻蚀", "检测", "量测", "PECVD", "ALD")):
        return "upstream_equipment"
    if any(x in role_text for x in ("材料", "原料药", "中间体", "CMP", "硅片", "特气", "电子化学品")):
        return "upstream_materials"
    if any(x in role_text for x in ("CDMO", "CRO", "CMO", "临床试验", "外包", "服务商", "平台", "高精地图", "软件", "服务")):
        return "service_provider"
    if any(x in role_text for x in ("创新药", "管线", "新药", "研发商", "药物开发", "整车", "车型", "智驾", "自动驾驶")):
        return "core_subject"
    if any(x in role_text for x in ("药店", "零售", "流通", "渠道", "运营商", "客运", "物流运营", "Robotaxi运营", "出行")):
        return "downstream_channel"
    if any(x in text for x in ("CDMO", "CRO", "CMO", "临床试验", "外包", "服务商", "平台", "高精地图", "软件")) or "midstream_service" in layers:
        return "service_provider"
    if any(x in text for x in ("传感器", "激光雷达", "毫米波雷达", "域控制器", "智能底盘", "芯片", "接口芯片", "封测", "封装")) or "upstream_components" in layers:
        return "component_supplier"
    if any(x in text for x in ("创新药", "管线", "新药", "研发商", "药物开发", "整车", "车型", "智驾", "自动驾驶")):
        return "core_subject"
    if "upstream_equipment" in layers:
        return "upstream_equipment"
    if "upstream_materials" in layers:
        return "upstream_materials"
    if "ecosystem" in layers:
        return "ecosystem"
    return "unknown"


def subtype_sort_rank(company: dict) -> int:
    return SUBTYPE_RANK.get(company.get("company_subtype") or company_subtype(company), SUBTYPE_RANK["unknown"])


def company_display_strength(company: dict) -> str:
    strength = company.get("strength", "related")
    subtype = company.get("company_subtype") or company_subtype(company)
    if subtype == "weak_graph":
        return "peripheral"
    if strength == "core" and subtype not in {"core_subject", "component_supplier"}:
        return "related"
    return strength


def company_sort_key(company: dict) -> tuple:
    return (
        STRENGTH_RANK.get(company_display_strength(company), 1),
        subtype_sort_rank(company),
        -company_evidence_score(company),
        -len(company.get("concepts", [])),
        company["name"],
    )


def refresh_company_subtypes(companies: list[dict]) -> list[dict]:
    for company in companies:
        company["company_subtype"] = company_subtype(company)
    return sorted(companies, key=company_sort_key)


def fact_hardness_rank(company: dict) -> str:
    return quality_rules.fact_hardness_rank(company)


def evidence_text(company: dict) -> str:
    parts = []
    for field in ("roles", "evidence", "sources", "chain_layers", "evidence_layers", "update_types", "fact_hardness", "source_quality"):
        value = company.get(field, [])
        if isinstance(value, list):
            parts.extend(str(x) for x in value)
        else:
            parts.append(str(value))
    buckets = company.get("evidence_buckets", {}) or {}
    for values in buckets.values():
        parts.extend(str(x) for x in values or [])
    return " ".join(parts)


def has_weak_granularity_signal(company: dict) -> bool:
    if has_official_l2_hard_evidence(company):
        return False
    text = evidence_text(company)
    weak_tokens = (
        "弱相关",
        "待验证",
        "潜在相关",
        "市场信号弱关联",
        "基础资料未直接",
        "不直接证明",
        "从既有entity markdown重建",
        "从既有concept markdown重建",
        "L2_candidate",
        "L1_L3_candidate",
    )
    return any(token in text for token in weak_tokens)


def has_official_l2_hard_evidence(company: dict) -> bool:
    hardness = fact_hardness_rank(company)
    layers = {str(x).strip() for x in company.get("evidence_layers", [])}
    source_quality_text = evidence_text(company)
    return (
        hardness in ("hard_fact", "baseline")
        and "L2" in layers
        and ("official_disclosure" in source_quality_text or "company_primary" in source_quality_text)
    )


def needs_granularity_review(company: dict) -> bool:
    flags = company_qc_flags(company)
    buckets = company.get("evidence_buckets", {}) or {}
    if company.get("review_required"):
        return True
    if "context_rank_mismatch" in flags or "context_overranked" in flags:
        return True
    if "possible_overranked" in flags or "missing_evidence" in flags:
        return True
    if has_weak_granularity_signal(company) and company.get("strength") in ("core", "related"):
        return True
    if buckets.get("curated_research"):
        return True
    if buckets.get("graph_only") and company.get("strength") in ("core", "related"):
        return True
    return False


def should_force_peripheral(company: dict) -> bool:
    buckets = company.get("evidence_buckets", {}) or {}
    if has_official_l2_hard_evidence(company):
        return False
    if quality_rules.should_force_peripheral_by_quality(company):
        return True
    has_strong = any(buckets.get(key) for key in ("baseline", "curated_research"))
    if has_strong:
        return False
    if not (buckets.get("delta") or buckets.get("missing")):
        return False
    weak_rebuilt = any("从既有" in str(item) and "重建" in str(item) for item in company.get("evidence", []))
    low_confidence = "low" in [str(x).lower() for x in company.get("confidence", [])] if isinstance(company.get("confidence"), list) else False
    generic_role = not company.get("roles") or all("待验证受益标的" in str(role) or str(role).strip() == "受益标的" for role in company.get("roles", []))
    return weak_rebuilt or low_confidence or generic_role


def related_concepts(primary: str, matches: list[str], graph: dict) -> list[str]:
    out = []
    for concept in matches or [primary]:
        node = graph.get("concepts", {}).get(concept, {})
        out.extend(node.get("parents", []))
        out.extend(node.get("related_concepts", []))
        for values in (node.get("supply_chain", {}) or {}).values():
            out.extend(values if isinstance(values, list) else [values])
        out.extend([r["concept"] for r in relation_neighbors(graph, concept)])
    return unique([x for x in out if x and x != primary])[:30]


def context_company_mentions(company: dict) -> list[dict]:
    rows = company.get("context_mentions", [])
    return rows if isinstance(rows, list) else []


def collect_evidence(concepts: list[str], companies: list[dict], evidence_index: dict) -> list[dict]:
    targets = set(concepts)
    targets.update(c["name"] for c in companies[:20])
    rows = []
    seen = set()
    for item in evidence_index.get("items", []):
        target = strip_wikilink(item.get("target", ""))
        if target in targets:
            key = (target, item.get("source", ""), item.get("evidence", ""))
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
    return rows[:30]


def normalize_chain_layer(value: str) -> str:
    return quality_rules.normalize_chain_layer(value)


def normalized_chain_layers(company: dict) -> list[str]:
    layers = unique([normalize_chain_layer(x) for x in company.get("chain_layers", []) if x])
    layers = [x for x in layers if x and x != "unknown"]
    if not layers:
        derived = []
        for role in company.get("roles", []):
            normalized = normalize_chain_layer(role)
            if normalized and normalized != "unknown":
                derived.append(normalized)
        layers = unique(derived)
    return layers or ["unknown"]


def has_chain_layer_conflict(company: dict) -> bool:
    raw_layers = [normalize_chain_layer(x) for x in company.get("chain_layers", []) if x]
    role_layers = []
    for role in company.get("roles", []):
        role_layers.extend(quality_rules.strict_role_chain_layers(role))
    raw_layers = {x for x in raw_layers if x and x != "unknown"}
    role_layers = {x for x in role_layers if x and x != "unknown"}
    if not raw_layers or not role_layers:
        return False
    return not bool(raw_layers & role_layers)


def enrich_companies_from_evidence_index(companies: list[dict], evidence_index: dict, concepts: list[str]) -> None:
    items = evidence_index.get("items", []) if isinstance(evidence_index, dict) else []
    if not items:
        return
    by_name = {c.get("name"): c for c in companies if c.get("name")}
    if not by_name:
        return
    concept_set = {str(x) for x in concepts if x}
    delta_source_tokens = ("市场逻辑", "强势股", "评级日报", "复盘", "脱水")
    research_source_tokens = ("研究报告", "产业新变化", "深度研究", "深度分析", "格局深度", "新格局")
    for item in items:
        target = strip_wikilink(item.get("target", ""))
        company = by_name.get(target)
        if not company:
            continue
        concept = strip_wikilink(item.get("concept", "")) if item.get("concept") else ""
        update_type = str(item.get("update_type") or "").strip()
        source = str(item.get("source") or "")
        evidence = str(item.get("evidence") or "").strip()
        is_company_baseline = "iFinD baseline" in source or "AkShare baseline" in source or "Baseline" in source
        if concept and concept_set and concept not in concept_set and not is_company_baseline:
            continue
        chosen_buckets = []
        if update_type in EVIDENCE_BUCKETS:
            chosen_buckets.append(update_type)
        if is_company_baseline:
            chosen_buckets.append("baseline")
        if not is_explicit_weak_graph_only(item) and any(token in source for token in delta_source_tokens):
            chosen_buckets.append("delta")
        if any(token in source for token in research_source_tokens) and "重建" not in evidence:
            chosen_buckets.append("curated_research")
        if not chosen_buckets:
            continue
        for bucket in unique(chosen_buckets):
            add_evidence_bucket(company, bucket, concept, evidence, source)
        layer = item.get("evidence_layer")
        if layer and layer not in company.setdefault("evidence_layers", []):
            company["evidence_layers"].append(layer)
        if update_type and update_type not in company.setdefault("update_types", []):
            company["update_types"].append(update_type)
        source_quality = item.get("source_quality")
        if source_quality and source_quality not in company.setdefault("source_quality", []):
            company["source_quality"].append(source_quality)
    for company in companies:
        if should_force_peripheral(company):
            company["strength"] = "peripheral"


def acceptance_score_section(companies: list[dict], context: dict, local_report_contexts: list[dict], term_matched: bool) -> str:
    counts = evidence_bucket_counts(companies)
    qc_overranked = [c for c in companies if "possible_overranked" in company_qc_flags(c)]
    qc_weak = [c for c in companies if "weak_granularity" in company_qc_flags(c)]
    qc_deep = [c for c in companies if "need_deep_read" in company_qc_flags(c)]
    qc_chain_conflict = [c for c in companies if "chain_layer_conflict" in company_qc_flags(c)]
    total = len(companies)
    has_external_def = bool((context or {}).get("definition")) or bool((context or {}).get("external_definition"))
    has_local_def = term_matched or bool(local_report_contexts)
    has_def = has_external_def or has_local_def
    has_chain = bool((context or {}).get("industry_chain_map")) or bool(local_report_contexts)
    top10 = companies[:10]
    top10_baseline = sum(1 for c in top10 if (c.get("evidence_buckets", {}) or {}).get("baseline"))
    top10_overranked = sum(1 for c in top10 if "possible_overranked" in company_qc_flags(c))
    top10_weak = sum(1 for c in top10 if "weak_granularity" in company_qc_flags(c))
    top10_unknown_layer = sum(1 for c in top10 if "unknown" in normalized_chain_layers(c))
    top10_chain_conflict = sum(1 for c in top10 if "chain_layer_conflict" in company_qc_flags(c))
    top10_review_required = sum(1 for c in top10 if "review_required" in company_qc_flags(c))
    top10_soft_fact = sum(1 for c in top10 if "soft_fact_hardness" in company_qc_flags(c))

    if has_external_def:
        definition_score = 9
        definition_note = "有外部定义"
    elif has_local_def:
        definition_score = 7
        definition_note = "有本地概念/研报定义，缺外部定义"
    else:
        definition_score = 4
        definition_note = "缺定义"
    chain_score = 12 if has_chain else 8
    if not term_matched:
        chain_score = max(4, chain_score - 4)
    if total == 0:
        ranking_score = 0
    else:
        ranking_score = 30
        ranking_score -= min(15, top10_overranked * 3)
        ranking_score -= min(10, top10_weak * 2)
        ranking_score -= min(8, top10_unknown_layer * 2)
        ranking_score -= min(6, top10_chain_conflict * 2)
        ranking_score -= min(8, top10_review_required * 2)
        ranking_score -= min(6, top10_soft_fact * 2)
        ranking_score = max(0, ranking_score)
    if total == 0:
        bucket_score = 0
    else:
        good = counts["baseline"] + counts["curated_research"] + counts["delta"]
        weak_ratio = (counts["graph_only"] + counts["missing"]) / max(1, total)
        weak_granularity_ratio = len(qc_weak) / max(1, total)
        chain_conflict_ratio = len(qc_chain_conflict) / max(1, total)
        review_required_ratio = len([c for c in companies if "review_required" in company_qc_flags(c)]) / max(1, total)
        soft_fact_ratio = len([c for c in companies if "soft_fact_hardness" in company_qc_flags(c)]) / max(1, total)
        bucket_score = int(round(20 * (good / max(1, total))))
        bucket_score = max(0, bucket_score - int(round(weak_ratio * 6)))
        bucket_score = max(0, bucket_score - int(round(weak_granularity_ratio * 6)))
        bucket_score = max(0, bucket_score - int(round(chain_conflict_ratio * 4)))
        bucket_score = max(0, bucket_score - int(round(review_required_ratio * 5)))
        bucket_score = max(0, bucket_score - int(round(soft_fact_ratio * 4)))
    deep_queue_score = 0 if not qc_deep else min(15, 6 + min(9, len(qc_deep)))
    usability = 7 if (top10_baseline >= 3 or counts["curated_research"] >= 2) else 5
    if top10_overranked >= len(top10) // 2 and len(top10):
        usability -= 2
    if top10_weak >= len(top10) // 2 and len(top10):
        usability -= 2
    if top10_chain_conflict:
        usability -= 1
    if top10_review_required:
        usability -= 1
    if top10_soft_fact:
        usability -= 1
    usability = max(3, usability)

    total_score = definition_score + chain_score + ranking_score + bucket_score + deep_queue_score + usability
    if total_score >= 85:
        verdict = "可投入日常使用"
    elif total_score >= 70:
        verdict = "可用，建议先修排序污染"
    elif total_score >= 50:
        verdict = "有条件可用，需要补证据/收敛排序"
    else:
        verdict = "暂不可用，需先回到数据结构"

    lines = [
        "| 模块 | 分值 | 评分 | 备注 |",
        "|---|---:|---:|---|",
        f"| 题材定义 | 10 | {definition_score} | {definition_note} |",
        f"| 产业链拆解 | 15 | {chain_score} | {'有本地或外部产业链' if has_chain else '产业链字段空缺'} |",
        f"| Top 10 公司排序 | 30 | {ranking_score} | Top10 过度高估 {top10_overranked}，弱颗粒度 {top10_weak}，未知链层 {top10_unknown_layer}，链层冲突 {top10_chain_conflict}，需复核 {top10_review_required}，软事实 {top10_soft_fact} |",
        f"| 证据桶准确性 | 20 | {bucket_score} | baseline={counts['baseline']}，curated={counts['curated_research']}，delta={counts['delta']}，graph_only={counts['graph_only']} |",
        f"| 精读候选队列 | 15 | {deep_queue_score} | 队列公司 {len(qc_deep)} |",
        f"| 结论可用性 | 10 | {usability} | Top10 baseline 支撑 {top10_baseline} |",
        f"| **总分** | **100** | **{total_score}** | **{verdict}** |",
        "",
        f"- possible_overranked={len(qc_overranked)}，weak_granularity={len(qc_weak)}，chain_layer_conflict={len(qc_chain_conflict)}，review_required={sum(1 for c in companies if 'review_required' in company_qc_flags(c))}，soft_fact_hardness={sum(1 for c in companies if 'soft_fact_hardness' in company_qc_flags(c))}，need_deep_read={len(qc_deep)}",
        "- 评分仅基于本地证据桶/链层归一化的启发式估计，未替代人工复核。",
    ]
    return "\n".join(lines)


def load_signal(theme_signals: dict, primary: str, matches: list[str]) -> dict:
    data = theme_signals.get("themes", theme_signals) if isinstance(theme_signals, dict) else {}
    for key in [primary] + matches:
        if key in data:
            return data[key]
    return {}


def match_patterns(pattern_library: dict, term: str, concepts: list[str]) -> list[tuple[str, dict]]:
    patterns = pattern_library.get("patterns", pattern_library) if isinstance(pattern_library, dict) else {}
    hits = []
    haystack = normalize(" ".join([term] + concepts))
    for name, pattern in patterns.items():
        words = [name] + pattern.get("keywords", [])
        if any(normalize(word) and normalize(word) in haystack for word in words):
            hits.append((name, pattern))
    return hits[:5]


def bullets(items: list[str], empty: str = "待补") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {item}" for item in items)


def company_table(rows: list[dict], strength: str, limit: int = 12) -> str:
    selected = [r for r in rows if company_display_strength(r) == strength][:limit]
    if not selected:
        return "- 待 baseline 补证"
    lines = ["| 公司 | 代码 | 公司类型 | 关联概念 | 原始链条层级 | 归一链条层级 | 证据桶 | 证据层 | 更新类型 | 事实硬度 | 产业链角色 | 证据 |", "|---|---:|---|---|---|---|---|---|---|---|---|---|"]
    for r in selected:
        evidence = "；".join(r["evidence"][:2]) or "待补证"
        roles = "；".join(r["roles"][:2]) or "受益标的"
        chain_layers = "、".join(r.get("chain_layers", [])[:3]) or "待补"
        normalized_layers = "、".join(normalized_chain_layers(r)[:3]) or "unknown"
        evidence_layers = "、".join(r.get("evidence_layers", [])[:3]) or "待补"
        update_types = "、".join(r.get("update_types", [])[:3]) or "待补"
        fact_hardness = fact_hardness_rank(r)
        if r.get("review_required"):
            fact_hardness = f"{fact_hardness}/需复核"
        bucket_summary = evidence_bucket_summary(r)
        subtype = SUBTYPE_LABELS.get(r.get("company_subtype") or company_subtype(r), "待判定")
        lines.append(
            f"| {r['name']} | {r.get('code','')} | {subtype} | {'、'.join(r['concepts'][:4])} | {chain_layers} | {normalized_layers} | {bucket_summary} | {evidence_layers} | {update_types} | {fact_hardness} | {roles} | {evidence} |"
        )
    return "\n".join(lines)


def evidence_bucket_summary(company: dict) -> str:
    buckets = company.get("evidence_buckets", {}) or {}
    labels = {
        "baseline": "baseline",
        "curated_research": "高信度",
        "delta": "边际",
        "graph_only": "图谱",
        "missing": "待补",
    }
    parts = []
    for key in EVIDENCE_BUCKETS:
        count = len(buckets.get(key, []) or [])
        if count:
            suffix = f"({count})" if count > 1 else ""
            parts.append(f"{labels[key]}✓{suffix}")
    return "、".join(parts) if parts else "待补"


def local_evidence_stack_section(companies: list[dict]) -> str:
    counts = evidence_bucket_counts(companies)
    return "\n".join(
        [
            "- baseline：基础画像 / 主营业务 / 长期产业链暴露。",
            "- curated_research：full.md 高信度研究线索，适合进入精读候选。",
            "- delta：边际变化 / 市场逻辑 / 短期催化，需要一手来源复核。",
            "- graph_only：弱召回 / 图谱连接，不能单独支撑核心排序。",
            "- missing：来自旧 markdown 重建或字段缺失，必须补证后再提高权重。",
            f"- 当前公司证据桶统计：baseline={counts['baseline']}，curated_research={counts['curated_research']}，delta={counts['delta']}，graph_only={counts['graph_only']}，missing={counts['missing']}。",
        ]
    )


def theme_evidence_readiness_section(theme: str) -> str:
    if readiness_builder is None:
        return "- Readiness builder 不可用；可单独运行 `python3 scripts/build_theme_evidence_readiness.py --theme <题材>`。"
    try:
        result = readiness_builder.build(theme)
    except Exception as exc:
        return f"- Readiness 生成失败：{exc}"
    summary = result.get("summary", {})
    rows = result.get("rows", [])
    lines = [
        "| 指标 | 数量 |",
        "|---|---:|",
        f"| 公司总数 | {summary.get('company_count', 0)} |",
        f"| 高置信公司 | {summary.get('high_confidence', 0)} |",
        f"| 中置信公司 | {summary.get('medium_confidence', 0)} |",
        f"| 低置信公司 | {summary.get('low_confidence', 0)} |",
        f"| Entity baseline ready | {summary.get('entity_baseline_ready', 0)} |",
        f"| 题材证据 ready | {summary.get('theme_evidence_ready', 0)} |",
        f"| 官方/公司级证据 ready | {summary.get('official_evidence_ready', 0)} |",
        f"| 直接题材证据 ready | {summary.get('direct_theme_evidence_ready', 0)} |",
        "",
        "### 补证优先队列",
        "",
        "| Priority | 公司 | 强度 | 置信 | 官方证据 | 直接证据 | 缺口 | 下一步 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    queue = [row for row in rows if row.get("priority") in {"P0", "P1"}][:12]
    if not queue:
        lines.append("| - | 暂无 | - | - | - | - | - | - |")
    for row in queue:
        lines.append(
            "| {priority} | {company} | {strength} | {tier} | {official} | {direct} | {missing} | {action} |".format(
                priority=row.get("priority", ""),
                company=row.get("company", ""),
                strength=row.get("strength", ""),
                tier=row.get("confidence_tier", ""),
                official="Y" if row.get("official_evidence_ready") else "N",
                direct="Y" if row.get("direct_theme_evidence_ready") else "N",
                missing=str(row.get("missing_reason", "")).replace("|", "\\|"),
                action=str(row.get("next_action", "")).replace("|", "\\|"),
            )
        )
    lines.extend(
        [
            "",
            "### 补证工具建议",
            "",
            "- 缺官方/公司级来源：使用 `disclosure-archive` 归档年报、公告、官网产品页、互动易。",
            "- 归档后先生成 review queue，不直接写入 entities/relations。",
            "- 只有 review queue 审核通过后，再用对应 writer 写入 baseline、entity_delta 或 evidence_index。",
        ]
    )
    return "\n".join(lines)


def evidence_bucket_counts(companies: list[dict]) -> dict:
    counts = {key: 0 for key in EVIDENCE_BUCKETS}
    for company in companies:
        buckets = company.get("evidence_buckets", {}) or {}
        for key in EVIDENCE_BUCKETS:
            if buckets.get(key):
                counts[key] += 1
    return counts


def company_qc_flags(company: dict) -> list[str]:
    buckets = company.get("evidence_buckets", {}) or {}
    flags = []
    hardness = fact_hardness_rank(company)
    mentions = context_company_mentions(company)
    if buckets.get("curated_research"):
        flags.append("strong_curated")
    if buckets.get("baseline"):
        flags.append("baseline_supported")
    if buckets.get("delta"):
        flags.append("delta_supported")
    if company.get("review_required"):
        flags.append("review_required")
    if hardness in ("research_claim", "market_narrative", "legacy_rebuilt", "unknown") and company.get("strength") in ("core", "related"):
        flags.append("soft_fact_hardness")
    if buckets.get("graph_only") and not any(buckets.get(k) for k in ("baseline", "curated_research", "delta")):
        flags.append("graph_only_only")
    if buckets.get("missing") and not any(buckets.get(k) for k in ("baseline", "curated_research", "delta")):
        flags.append("missing_evidence")
    if not company.get("chain_layers"):
        flags.append("missing_chain_layer")
    if has_chain_layer_conflict(company):
        flags.append("chain_layer_conflict")
    if not company.get("update_types"):
        flags.append("missing_update_type")
    if company.get("strength") in ("core", "related") and ("graph_only_only" in flags or "missing_evidence" in flags):
        flags.append("possible_overranked")
    if has_weak_granularity_signal(company) and company.get("strength") in ("core", "related"):
        flags.append("weak_granularity")
    if any(row.get("directness") == "direct" for row in mentions) and (
        company.get("strength") == "peripheral" or "graph_only_only" in flags or "missing_evidence" in flags
    ):
        flags.append("context_rank_mismatch")
    if company.get("context_checked") and company.get("strength") in ("core", "related") and not mentions and ("weak_granularity" in flags or "possible_overranked" in flags):
        flags.append("context_overranked")
    if buckets.get("curated_research") and (not buckets.get("baseline") or company.get("strength") in ("core", "related")):
        flags.append("need_deep_read")
    if "possible_overranked" in flags or "weak_granularity" in flags or "chain_layer_conflict" in flags or "review_required" in flags or "soft_fact_hardness" in flags or "context_rank_mismatch" in flags or "context_overranked" in flags:
        flags.append("need_deep_read")
    return flags


def theme_qc_section(companies: list[dict]) -> str:
    counts = evidence_bucket_counts(companies)
    graph_only_only = [c for c in companies if "graph_only_only" in company_qc_flags(c)]
    missing_evidence = [c for c in companies if "missing_evidence" in company_qc_flags(c)]
    possible_overranked = [c for c in companies if "possible_overranked" in company_qc_flags(c)]
    need_deep_read = [c for c in companies if "need_deep_read" in company_qc_flags(c)]
    missing_chain_layer = [c for c in companies if "missing_chain_layer" in company_qc_flags(c)]
    chain_layer_conflict = [c for c in companies if "chain_layer_conflict" in company_qc_flags(c)]
    weak_granularity = [c for c in companies if "weak_granularity" in company_qc_flags(c)]
    review_required = [c for c in companies if "review_required" in company_qc_flags(c)]
    soft_fact_hardness = [c for c in companies if "soft_fact_hardness" in company_qc_flags(c)]
    context_rank_mismatch = [c for c in companies if "context_rank_mismatch" in company_qc_flags(c)]
    context_overranked = [c for c in companies if "context_overranked" in company_qc_flags(c)]
    lines = [
        "| 指标 | 数量 |",
        "|---|---:|",
        f"| 公司总数 | {len(companies)} |",
        f"| baseline 支撑公司 | {counts['baseline']} |",
        f"| 高信度研究线索公司 | {counts['curated_research']} |",
        f"| 边际变化支撑公司 | {counts['delta']} |",
        f"| graph_only only 公司 | {len(graph_only_only)} |",
        f"| missing evidence 公司 | {len(missing_evidence)} |",
        f"| missing chain_layer 公司 | {len(missing_chain_layer)} |",
        f"| chain_layer_conflict 公司 | {len(chain_layer_conflict)} |",
        f"| possible_overranked | {len(possible_overranked)} |",
        f"| weak_granularity | {len(weak_granularity)} |",
        f"| review_required | {len(review_required)} |",
        f"| soft_fact_hardness | {len(soft_fact_hardness)} |",
        f"| context_rank_mismatch | {len(context_rank_mismatch)} |",
        f"| context_overranked | {len(context_overranked)} |",
        f"| need_deep_read | {len(need_deep_read)} |",
        "",
        f"- possible_overranked：{'、'.join(c['name'] for c in possible_overranked[:12]) if possible_overranked else '无'}",
        f"- weak_granularity：{'、'.join(c['name'] for c in weak_granularity[:12]) if weak_granularity else '无'}",
        f"- review_required：{'、'.join(c['name'] for c in review_required[:12]) if review_required else '无'}",
        f"- soft_fact_hardness：{'、'.join(c['name'] for c in soft_fact_hardness[:12]) if soft_fact_hardness else '无'}",
        f"- chain_layer_conflict：{'、'.join(c['name'] for c in chain_layer_conflict[:12]) if chain_layer_conflict else '无'}",
        f"- context_rank_mismatch：{'、'.join(c['name'] for c in context_rank_mismatch[:12]) if context_rank_mismatch else '无'}",
        f"- context_overranked：{'、'.join(c['name'] for c in context_overranked[:12]) if context_overranked else '无'}",
        f"- 待补证公司：{'、'.join(c['name'] for c in missing_evidence[:12]) if missing_evidence else '无'}",
    ]
    return "\n".join(lines)


def deep_read_queue_section(companies: list[dict], limit: int = 12) -> str:
    rows = [c for c in companies if needs_granularity_review(c)]
    rows = sorted(rows, key=company_sort_key)[:limit]
    if not rows:
        return "- 暂无。"
    lines = ["| 公司 | 强度 | 证据桶 | 精读原因 | 优先核验点 |", "|---|---|---|---|---|"]
    for company in rows:
        flags = company_qc_flags(company)
        reason = "、".join(flag for flag in flags if flag in ("strong_curated", "baseline_supported", "delta_supported", "possible_overranked", "weak_granularity", "graph_only_only", "missing_chain_layer", "chain_layer_conflict", "missing_update_type", "review_required", "soft_fact_hardness", "context_rank_mismatch", "context_overranked"))
        checks = []
        if not company.get("evidence_buckets", {}).get("baseline"):
            checks.append("补 baseline")
        if company.get("review_required"):
            checks.append("按底层审核标准复核")
        if "soft_fact_hardness" in flags:
            checks.append("补硬事实或降权")
        if "weak_granularity" in flags:
            checks.append("核准主营占比/直接业务关系")
        if "possible_overranked" in flags:
            checks.append("判断是否降级到 peripheral")
        if "chain_layer_conflict" in flags:
            checks.append("核对链层/角色冲突")
        if "context_rank_mismatch" in flags:
            checks.append("按精读上下文补证或修暴露")
        if "context_overranked" in flags:
            checks.append("按精读上下文判断是否降权")
        checks.extend(["核对 full.md 原文上下文", "找公告/年报/官网验证订单、份额、收入占比"])
        lines.append(f"| {company['name']} | {company.get('strength', '')} | {evidence_bucket_summary(company)} | {reason or '高信度线索'} | {'；'.join(checks[:3])} |")
    return "\n".join(lines)


def signal_lines(signal: dict) -> str:
    fields = [
        ("sell_side_coverage", "卖方覆盖"),
        ("price_signals", "价格信号"),
        ("order_signals", "订单 / 验证"),
        ("market_heat", "市场热度"),
        ("industry_progress", "产业进度"),
        ("risks", "反证 / 风险"),
    ]
    lines = []
    for key, label in fields:
        values = signal.get(key, []) if isinstance(signal, dict) else []
        if isinstance(values, str):
            values = [values]
        text = "；".join(str(v) for v in values if v) if values else "待补"
        lines.append(f"- {label}：{text}")
    return "\n".join(lines)


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in re.split(r"[、,，/;；]+", value) if x.strip()]
    return [str(value).strip()]


def read_theme_information_jsonl(path: Path, term: str) -> list[dict]:
    if not path or not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            theme = str(row.get("theme") or "").strip()
            if theme and term and term not in theme and theme not in term:
                continue
            rows.append(row)
    return rows


def read_theme_direction_pool(path: Path, term: str) -> dict:
    if not path or not path.exists():
        return {}
    data = load_json(path, {})
    theme = str(data.get("theme") or "").strip()
    if theme and term and term not in theme and theme not in term:
        return {}
    directions = data.get("directions", [])
    if not isinstance(directions, list):
        return {}
    return data


def theme_info_types(row: dict) -> set[str]:
    values = row.get("info_types") or [row.get("primary_info_type")]
    return {str(v) for v in values if v}


def theme_info_anchor(rows: list[dict]) -> str:
    candidates = []
    for row in rows:
        if "theme_anchor" not in theme_info_types(row) and row.get("source_record_type") != "deep_dive_theme_anchor":
            continue
        claim = str(row.get("claim") or "").strip()
        if not claim:
            continue
        score = theme_info_score(row)
        if row.get("suggested_use") == "deep_dive":
            score += 4
        candidates.append((score, claim))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][1]


def theme_info_source_label(row: dict) -> str:
    systems = row.get("source_systems") or []
    systems = [str(x) for x in systems if str(x).strip()]
    if len(set(systems)) > 1:
        return "多源"
    return systems[0] if systems else "未知"


def theme_info_score(row: dict) -> int:
    types = theme_info_types(row)
    score = {"high": 8, "medium": 4, "low": 0}.get(str(row.get("specificity") or ""), 0)
    if row.get("entity_name"):
        score += 3
    if row.get("ticker"):
        score += 2
    if "segment_mapping" in types:
        score += 8
    if "relationship" in types:
        score += 7
    if "marginal_change" in types:
        score += 3
    if theme_info_source_label(row) == "多源":
        score += 4
    text = " ".join(str(row.get(k) or "") for k in ("segment", "component", "claim", "chain_position"))
    for token in ("上游", "中游", "下游", "供应", "客户", "导入", "量产", "出货", "认证", "设备", "材料", "芯片", "器件"):
        if token in text:
            score += 1
    for token in ("建议关注", "买入评级", "长期看好", "graph_only"):
        if token in text:
            score -= 4
    return score


def theme_info_chain_bucket(row: dict) -> str:
    text = " ".join(str(row.get(k) or "") for k in ("chain_position", "segment", "component"))
    if "下游" in text or "云厂商" in text or "数据中心" in text:
        return "downstream"
    if "设备" in text or "测试" in text or "仪器" in text or "贴片" in text:
        return "upstream_equipment"
    if "上游" in text or any(t in text for t in ("EML", "CW", "InP", "磷化铟", "光芯片", "材料", "隔离器", "MPO")):
        return "upstream_materials"
    return "midstream"


def theme_info_short(text: str, limit: int = 80) -> str:
    text = " ".join(str(text or "").split()).replace("|", "/")
    return text if len(text) <= limit else text[: limit - 1] + "…"


GENERIC_THEME_INFO_SEGMENTS = {
    "收入",
    "订单",
    "产能",
    "客户",
    "认证",
    "量产",
    "交付",
    "送样",
    "并购",
    "并购公告",
    "合作协议公告",
    "产品发布",
    "项目上线",
    "技术融合",
    "收入确认",
    "订单数据",
    "认证/运营",
    "海外扩张",
    "复购",
    "产品线",
    "涨价/订单",
    "瓶颈缓解",
    "明确合作",
    "合作",
    "市占率",
    "资本开支",
    "出货",
    "出货量",
    "收入结构",
    "客户/覆盖",
    "研发投入",
    "市场预测",
    "产品",
    "良率",
    "项目落地",
    "中标",
    "收入增速",
    "业务数据",
    "产能/装机",
    "年报（收入/利润/业务）",
    "并购/整合",
    "业绩",
    "估值",
    "股价",
    "其他",
    "待核验",
    "未分段",
}


def is_generic_theme_info_segment(segment: str) -> bool:
    s = str(segment or "").strip()
    if not s:
        return True
    if s in GENERIC_THEME_INFO_SEGMENTS:
        return True
    return s.startswith(("全产业链", "全T链", "全链条"))


def build_theme_information_context(term: str, rows: list[dict]) -> dict:
    if not rows:
        return {}
    catalyst_rows = [r for r in rows if r.get("source_record_type") == "deep_dive_catalyst"]
    demand_drivers = unique([
        theme_info_short(r.get("claim"), 120)
        for r in sorted(catalyst_rows, key=theme_info_score, reverse=True)
        if str(r.get("claim") or "").strip()
    ])[:10]
    verification_nodes = unique([
        theme_info_short((r.get("raw_row") or {}).get("下一步验证"), 120)
        for r in rows
        if isinstance(r.get("raw_row"), dict) and (r.get("raw_row") or {}).get("下一步验证")
    ])[:10]
    selected_all = [r for r in rows if theme_info_score(r) >= 12 and theme_info_types(r) & {"segment_mapping", "relationship"}]
    selected = [
        r for r in selected_all
        if not is_generic_theme_info_segment(r.get("segment") or r.get("chain_position") or "")
    ]
    by_segment: dict[str, list[dict]] = {}
    for row in selected:
        seg = str(row.get("segment") or row.get("chain_position") or "未分段").strip()
        if not seg:
            continue
        by_segment.setdefault(seg, []).append(row)
    if not by_segment:
        anchor = theme_info_anchor(rows)
        out = {}
        if anchor:
            out["definition"] = anchor
        if demand_drivers:
            out["demand_drivers"] = demand_drivers
        if verification_nodes:
            out["verification_nodes"] = verification_nodes
        return out

    chain = {key: [] for key in ["downstream", "midstream", "upstream_materials", "upstream_equipment"]}
    direction_scan = []
    progress_ranking = []
    segment_rows = []
    relationship_rows = []
    sorted_segments = sorted(by_segment.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for idx, (seg, items) in enumerate(sorted_segments[:24], 1):
        bucket = theme_info_chain_bucket(items[0])
        companies = unique([
            name for name in [str(r.get("entity_name") or "").strip() for r in sorted(items, key=theme_info_score, reverse=True)[:8]]
            if name and name not in {"—", "-", "无", "unknown"}
        ])
        mapping_count = sum(1 for r in items if "segment_mapping" in theme_info_types(r))
        relationship_count = sum(1 for r in items if "relationship" in theme_info_types(r))
        chain[bucket].append(
            {
                "name": seg,
                "evidence_type": "theme_information_pool",
                "role": bucket,
                "companies": companies[:5],
            }
        )
        direction_scan.append(
            {
                "direction": seg,
                "sector": term,
                "prosperity": f"统一信息池命中 {len(items)} 条，其中题材地图 {mapping_count} 条、上下游关系 {relationship_count} 条。",
                "mention_frequency": "IMA/Obsidian 信息池命中",
                "recognition_level": "L1结构线索 + 展示层待复核",
                "classification": "细颗粒题材地图",
                "core_catalyst": "继续观察该环节是否被更多来源确认，并映射到公司级产品/客户/量产线索。",
                "candidate_companies": companies[:6],
            }
        )
        progress_ranking.append(
            {
                "direction": seg,
                "stage": "结构补全",
                "recognition_level": "信息池结构线索",
                "evidence_level": "theme_information_pool",
                "progress_score": max(35, 85 - idx),
                "key_signal": f"细颗粒地图/上下游关系合计 {mapping_count + relationship_count} 条。",
                "next_validation": "人工确认是否进入正式产业链全景图；公司级事实另行用公告/订单/业绩验证。",
                "priority": "地图补强",
            }
        )
        segment_rows.append(
            {
                "segment": seg,
                "total": len(items),
                "mapping_count": mapping_count,
                "relationship_count": relationship_count,
                "companies": companies[:6],
                "bucket": bucket,
            }
        )

    relation_candidates = [
        r for r in selected
        if "relationship" in theme_info_types(r) and str(r.get("entity_name") or "").strip()
    ]
    for row in sorted(relation_candidates, key=lambda r: theme_info_score(r)+(20 if 'IMA' in set(r.get('source_systems') or []) else 0)-(20 if str(r.get('claim') or '').count('/')>5 else 0), reverse=True)[:16]:
        relationship_rows.append(
            {
                "segment": row.get("segment") or row.get("chain_position") or "未分段",
                "entity": row.get("entity_name") or "",
                "ticker": row.get("ticker") or "",
                "claim": row.get("claim") or "",
                "specificity": row.get("specificity") or "",
                "source": theme_info_source_label(row),
            }
        )

    catalyst_preview = [
        {
            "claim": theme_info_short(r.get("claim"), 100),
            "source": theme_info_source_label(r),
            "confidence": r.get("confidence") or "",
        }
        for r in sorted(catalyst_rows, key=theme_info_score, reverse=True)[:8]
        if str(r.get("claim") or "").strip()
    ]
    out = {
        "theme_information_pool": {
            "enabled": True,
            "total_rows": len(rows),
            "selected_rows": len(selected),
            "filtered_generic_rows": len(selected_all) - len(selected),
            "catalysts": catalyst_preview,
            "verification_nodes": verification_nodes[:8],
            "segments": segment_rows,
            "relationships": relationship_rows,
            "note": "只读接入 IMA/Obsidian 统一信息池；用于题材地图和上下游关系，不写入 entities，不升级公司事实。",
        },
        "industry_chain_map": chain,
        "direction_scan": direction_scan[:12],
        "progress_ranking": progress_ranking[:12],
        "related_terms": [row["segment"] for row in segment_rows[:24]],
        "capability_stack": [row["segment"] for row in segment_rows[:12]],
        "core_benefit_links": [
            f"{row['segment']}：{ '、'.join(row.get('companies') or []) }"
            for row in segment_rows[:12]
            if row.get("segment") and row.get("companies")
        ],
    }
    if demand_drivers:
        out["demand_drivers"] = demand_drivers
    if verification_nodes:
        out["verification_nodes"] = verification_nodes
    anchor = theme_info_anchor(rows)
    if anchor:
        out["definition"] = anchor
    return out


def merge_theme_information_context(context: dict, theme_context: dict) -> dict:
    if not theme_context:
        return context or {}
    merged = dict(context or {})
    if theme_context.get("definition"):
        merged["definition"] = theme_context.get("definition")
    for key in ("demand_drivers", "core_benefit_links", "verification_nodes"):
        merged[key] = unique(as_list(theme_context.get(key)) + as_list(merged.get(key)))[:16]
    merged["theme_information_pool"] = theme_context.get("theme_information_pool", {})
    for key in ("related_terms", "capability_stack"):
        merged[key] = unique(as_list(merged.get(key)) + as_list(theme_context.get(key)))
    for key in ("direction_scan", "progress_ranking"):
        merged[key] = (merged.get(key) or []) + (theme_context.get(key) or [])
    base_chain = merged.get("industry_chain_map") if isinstance(merged.get("industry_chain_map"), dict) else {}
    add_chain = theme_context.get("industry_chain_map") if isinstance(theme_context.get("industry_chain_map"), dict) else {}
    chain = {}
    for bucket in ["downstream", "midstream", "upstream_materials", "upstream_equipment"]:
        seen = set()
        rows = []
        for item in (base_chain.get(bucket, []) or []) + (add_chain.get(bucket, []) or []):
            name = item.get("name") if isinstance(item, dict) else str(item)
            if name and name not in seen:
                seen.add(name)
                rows.append(item if isinstance(item, dict) else {"name": name})
        chain[bucket] = rows[:16]
    merged["industry_chain_map"] = chain
    return merged


def direction_pool_entities(row: dict, limit: int = 6) -> list[str]:
    return unique([
        str(entity.get("name") or "").strip()
        for entity in (row.get("representative_entities") or [])
        if isinstance(entity, dict) and str(entity.get("name") or "").strip()
    ])[:limit]


def direction_pool_evidence_label(profile: dict) -> str:
    if not isinstance(profile, dict):
        return "direction_pool"
    layer = profile.get("highest_evidence_layer", "direction_pool")
    count = profile.get("item_count", 0)
    systems = "、".join(as_list(profile.get("source_systems"))[:3])
    official = "；含官方证据" if profile.get("has_official_evidence") else ""
    return f"{count}条/{layer}/{systems}{official}".strip("/")


def direction_pool_score(row: dict) -> int:
    profile = row.get("evidence_profile", {}) if isinstance(row, dict) else {}
    stage = str(row.get("recognition_stage") or "")
    stage_score = {"暗流": 30, "萌芽": 45, "第一轮": 60, "催化共振": 78, "一致认同": 90}.get(stage, 35)
    try:
        item_count = int(profile.get("item_count", 0))
    except Exception:
        item_count = 0
    score = stage_score + min(item_count, 10)
    if profile.get("has_multi_source_support"):
        score += 5
    if profile.get("has_official_evidence"):
        score += 8
    if row.get("verification_items"):
        score += 3
    return min(score, 99)


def direction_pool_first_verification(row: dict) -> str:
    verification = row.get("verification_items") or []
    if verification and isinstance(verification[0], dict):
        return str(verification[0].get("item") or "")
    catalysts = row.get("catalysts") or []
    if catalysts and isinstance(catalysts[0], dict):
        return str(catalysts[0].get("event") or "")
    return ""


def build_theme_direction_pool_context(pool: dict) -> dict:
    directions = pool.get("directions", []) if isinstance(pool, dict) else []
    if not isinstance(directions, list) or not directions:
        return {}
    demand_map = pool.get("demand_bottleneck_map", []) if isinstance(pool.get("demand_bottleneck_map"), list) else []
    scan_rows = []
    ranking_rows = []
    catalyst_rows = []
    validation_rows = []
    for row in directions:
        if not isinstance(row, dict):
            continue
        profile = row.get("evidence_profile", {}) if isinstance(row.get("evidence_profile"), dict) else {}
        companies = direction_pool_entities(row)
        evidence_label = direction_pool_evidence_label(profile)
        demand = "、".join(as_list(row.get("demand_sources")))
        bottleneck = "、".join(as_list(row.get("bottlenecks_solved")))
        verification = direction_pool_first_verification(row)
        scan_rows.append({
            "direction": row.get("direction", ""),
            "sector": row.get("parent_sector", ""),
            "prosperity": "；".join(x for x in [f"需求：{demand}" if demand else "", f"瓶颈：{bottleneck}" if bottleneck else "", evidence_label] if x),
            "mention_frequency": f"方向池命中 {profile.get('item_count', 0)} 条",
            "recognition_level": row.get("recognition_stage", ""),
            "classification": f"{row.get('direction_type','')}/{row.get('chain_bucket','')}",
            "core_catalyst": verification,
            "candidate_companies": companies,
        })
        ranking_rows.append({
            "direction": row.get("direction", ""),
            "stage": row.get("recognition_stage", ""),
            "recognition_level": row.get("recognition_stage", ""),
            "evidence_level": profile.get("highest_evidence_layer", "direction_pool"),
            "progress_score": direction_pool_score(row),
            "key_signal": evidence_label,
            "next_validation": verification,
            "priority": "优先跟踪" if direction_pool_score(row) >= 60 else "观察验证",
        })
        for catalyst in row.get("catalysts") or []:
            if not isinstance(catalyst, dict):
                continue
            catalyst_rows.append({
                "time": catalyst.get("time_window", ""),
                "event": catalyst.get("event", ""),
                "watch_item": row.get("direction", ""),
            })
        for item in row.get("verification_items") or []:
            if not isinstance(item, dict):
                continue
            validation_rows.append({
                "item": item.get("item", ""),
                "why": row.get("direction", ""),
                "status": "待验证",
            })
    return {
        "theme_direction_pool": {
            "enabled": True,
            "theme": pool.get("theme", ""),
            "generated_at": pool.get("generated_at", ""),
            "summary": pool.get("summary", {}),
        },
        "direction_scan": scan_rows,
        "progress_ranking": ranking_rows,
        "catalyst_calendar": catalyst_rows[:30],
        "validation_checklist": validation_rows[:30],
        "demand_bottleneck_map": demand_map,
        "demand_drivers": unique([str(row.get("demand_source") or "") for row in demand_map if isinstance(row, dict) and row.get("demand_source")]),
        "bottlenecks": unique([str(row.get("bottleneck") or "") for row in demand_map if isinstance(row, dict) and row.get("bottleneck")]),
        "core_benefit_links": unique([str(link) for row in demand_map if isinstance(row, dict) for link in as_list(row.get("chain_links"))]),
        "verification_nodes": unique([str(item) for row in demand_map if isinstance(row, dict) for item in as_list(row.get("verification_items"))])[:20],
    }


def merge_theme_direction_pool_context(context: dict, direction_context: dict) -> dict:
    if not direction_context:
        return context or {}
    merged = dict(context or {})
    merged["theme_direction_pool"] = direction_context.get("theme_direction_pool", {})
    for key in ("direction_scan", "progress_ranking", "catalyst_calendar", "validation_checklist", "demand_bottleneck_map"):
        existing = merged.get(key) if isinstance(merged.get(key), list) else []
        incoming = direction_context.get(key) if isinstance(direction_context.get(key), list) else []
        if key in ("direction_scan", "progress_ranking"):
            seen = set()
            rows = []
            for item in incoming + existing:
                if not isinstance(item, dict):
                    continue
                direction = str(item.get("direction") or "")
                if direction and direction in seen:
                    continue
                if direction:
                    seen.add(direction)
                rows.append(item)
            merged[key] = rows
        elif key == "demand_bottleneck_map":
            seen = set()
            rows = []
            for item in incoming + existing:
                if not isinstance(item, dict):
                    continue
                map_key = (str(item.get("demand_source") or ""), str(item.get("bottleneck") or ""))
                if map_key in seen:
                    continue
                seen.add(map_key)
                rows.append(item)
            merged[key] = rows
        else:
            merged[key] = incoming + existing
    for key in ("demand_drivers", "core_benefit_links", "verification_nodes", "bottlenecks"):
        existing = as_list(merged.get(key))
        incoming = as_list(direction_context.get(key))
        merged[key] = unique([str(item) for item in incoming + existing if str(item).strip()])
    return merged


def theme_information_pool_section(context: dict) -> str:
    pool = context.get("theme_information_pool", {}) if isinstance(context, dict) else {}
    if not isinstance(pool, dict) or not pool.get("enabled"):
        return "- 未接入 IMA/Obsidian 统一信息池。"
    lines = [
        f"- 信息池：全量 {pool.get('total_rows', 0)} 条；进入题材地图/上下游展示层 {pool.get('selected_rows', 0)} 条；过滤泛化分段 {pool.get('filtered_generic_rows', 0)} 条。",
        f"- 边界：{pool.get('note', '')}",
    ]
    catalysts = pool.get("catalysts", []) or []
    if catalysts:
        lines.extend(["", "### IMA 催化事件", "", "| 催化/边际变化 | 可信度 | 来源 |", "|---|---|---|"])
        for row in catalysts[:8]:
            lines.append(f"| {row.get('claim','')} | {row.get('confidence','')} | {row.get('source','')} |")
    lines.extend([
        "",
        "### IMA 细颗粒题材地图",
        "",
        "| 细分环节 | 层级 | 信息项 | 地图项 | 关系项 | 代表主体 |",
        "|---|---|---:|---:|---:|---|",
    ])
    for row in pool.get("segments", [])[:24]:
        lines.append(
            f"| {row.get('segment','')} | {row.get('bucket','')} | {row.get('total',0)} | {row.get('mapping_count',0)} | {row.get('relationship_count',0)} | {'、'.join(row.get('companies') or [])} |"
        )
    relationships = pool.get("relationships", []) or []
    if relationships:
        lines.extend(["", "### 上下游关系样例", "", "| 细分环节 | 主体 | 具体度 | 来源 | 关系/位置 |", "|---|---|---|---|---|"])
        for row in relationships[:12]:
            name = str(row.get("entity", ""))
            if row.get("ticker"):
                name = f"{name} ({row.get('ticker')})"
            lines.append(
                f"| {row.get('segment','')} | {name} | {row.get('specificity','')} | {row.get('source','')} | {theme_info_short(row.get('claim'), 110)} |"
            )
    verification_nodes = pool.get("verification_nodes", []) or []
    if verification_nodes:
        lines.extend(["", "### IMA 后续验证节点", ""])
        lines.extend([f"- {x}" for x in verification_nodes[:8]])
    return "\n".join(lines)


def theme_direction_pool_section(context: dict) -> str:
    pool = context.get("theme_direction_pool", {}) if isinstance(context, dict) else {}
    if not isinstance(pool, dict) or not pool.get("enabled"):
        return "- 未接入标准细分方向池。"
    summary = pool.get("summary", {}) if isinstance(pool.get("summary"), dict) else {}
    lines = [
        f"- 方向池：{summary.get('direction_count', 0)} 个方向；匹配 {summary.get('matched_row_count', 0)} / 输入 {summary.get('input_row_count', 0)} 条信息池记录。",
        f"- 生成日期：{pool.get('generated_at', '')}",
        f"- 边界：{summary.get('safety_statement', '')}",
    ]
    by_stage = summary.get("directions_by_recognition_stage", {})
    if isinstance(by_stage, dict) and by_stage:
        lines.append(f"- 认知水位分布：{'; '.join(f'{k}={v}' for k, v in by_stage.items())}")
    by_type = summary.get("directions_by_type", {})
    if isinstance(by_type, dict) and by_type:
        lines.append(f"- 方向类型分布：{'; '.join(f'{k}={v}' for k, v in by_type.items())}")
    return "\n".join(lines)


def demand_bottleneck_map_section(context: dict) -> str:
    rows = context.get("demand_bottleneck_map", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要方向池生成 demand_bottleneck_map。"
    lines = [
        "| 需求来源 | 技术瓶颈 | 受益环节/方向 | 代表实体 | 证据画像 | 下一步验证 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows[:18]:
        if not isinstance(row, dict):
            continue
        profile = row.get("evidence_profile", {}) if isinstance(row.get("evidence_profile"), dict) else {}
        evidence = direction_pool_evidence_label(profile)
        verification = "；".join(as_list(row.get("verification_items"))[:2])
        lines.append(
            "| {demand} | {bottleneck} | {links} | {entities} | {evidence} | {verification} |".format(
                demand=row.get("demand_source", ""),
                bottleneck=row.get("bottleneck", ""),
                links="、".join(as_list(row.get("chain_links"))[:6]),
                entities="、".join(as_list(row.get("beneficiary_entities"))[:6]),
                evidence=evidence,
                verification=verification,
            )
        )
    return "\n".join(lines)


def context_definition(context: dict) -> str:
    return str(context.get("definition") or "").strip() if isinstance(context, dict) else ""


def context_search_text(context: dict) -> str:
    if not isinstance(context, dict):
        return ""
    hard_fields = [
        "definition",
        "aliases",
        "english_terms",
        "parent_concepts",
        "chain_position",
        "related_terms",
        "problem_solved",
        "technical_modules",
        "required_capabilities",
        "capability_stack",
        "demand_drivers",
        "proxy_variables",
    ]
    parts = []
    for field in hard_fields:
        value = context.get(field)
        if isinstance(value, list):
            parts.extend(str(x) for x in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def high_relevance_segments(context: dict) -> list[dict]:
    rows = context.get("segment_scores", []) if isinstance(context, dict) else []
    if not isinstance(rows, list):
        return []
    allowed = {"high", "medium_high", "中高", "高"}
    return [row for row in rows if isinstance(row, dict) and str(row.get("relevance", "")).strip().lower() in allowed]


def context_company_text(context: dict) -> str:
    if not isinstance(context, dict):
        return ""
    focused_fields = ["aliases", "english_terms", "technical_modules", "required_capabilities", "proxy_variables"]
    parts = []
    for field in focused_fields:
        value = context.get(field)
        if isinstance(value, list):
            parts.extend(str(x) for x in value)
        elif value:
            parts.append(str(value))
    for row in high_relevance_segments(context):
        parts.extend(as_list(row.get("mapped_concepts")))
    return " ".join(parts)


def excluded_concepts(context: dict) -> set[str]:
    values = as_list(context.get("excluded_broad_concepts")) if isinstance(context, dict) else []
    return {normalize(v) for v in values if v}


def filter_concepts(concepts: list[str], context: dict) -> list[str]:
    excluded = excluded_concepts(context)
    if not excluded:
        return concepts
    return [c for c in concepts if normalize(c) not in excluded]


def context_section(context: dict) -> str:
    if not isinstance(context, dict) or not context:
        return "- 未提供结构化画像。"
    hard = [
        ("aliases", "同义词"),
        ("english_terms", "英文/缩写"),
        ("parent_concepts", "上位概念"),
        ("chain_position", "产业链位置"),
        ("related_terms", "相关技术/概念"),
        ("problem_solved", "解决的问题"),
        ("technical_modules", "技术模块"),
        ("required_capabilities", "所需能力"),
        ("capability_stack", "能力栈"),
        ("demand_drivers", "需求驱动"),
        ("proxy_variables", "代理变量"),
        ("excluded_broad_concepts", "排除泛概念"),
        ("upstream", "上游"),
        ("midstream", "中游"),
        ("downstream", "下游"),
    ]
    soft = [
        ("core_benefit_links", "受益链条"),
        ("bottlenecks", "瓶颈/壁垒"),
        ("verification_nodes", "验证节点"),
        ("candidate_companies", "候选公司线索"),
        ("source_urls", "外部来源"),
        ("confidence", "外部画像置信度"),
    ]
    lines = ["### 匹配字段"]
    for key, label in hard:
        values = as_list(context.get(key))
        lines.append(f"- {label}：{('、'.join(values) if values else '待补')}")
    lines.append("")
    lines.append("### 判断字段")
    for key, label in soft:
        values = as_list(context.get(key))
        lines.append(f"- {label}：{('、'.join(values) if values else '待补')}")
    return "\n".join(lines)


def extraction_quality_section(context: dict) -> str:
    quality = context.get("extraction_quality", {}) if isinstance(context, dict) else {}
    if not quality:
        note = context.get("raw_extraction_note", "") if isinstance(context, dict) else ""
        return f"- {note or '未提供抽取质量信息。'}"
    missing = as_list(quality.get("missing_fields"))
    lines = [
        f"- 抽取模式：{quality.get('mode', 'unknown')}",
        f"- 条目总数：{quality.get('total_items', 0)}",
        f"- 原文支撑：{quality.get('source_backed_items', 0)}",
        f"- 规则推断：{quality.get('inferred_items', 0)}",
        f"- 缺失字段：{('、'.join(missing) if missing else '无')}",
        f"- 是否需要复核：{'是' if quality.get('review_required', True) else '否'}",
    ]
    return "\n".join(lines)


def evidence_stack_section(context: dict) -> str:
    stack = context.get("evidence_stack", {}) if isinstance(context, dict) else {}
    if not isinstance(stack, dict) or not stack:
        return "- 待补：需要区分外部定义、产业翻译、baseline、事实验证和市场信号。"
    labels = [
        ("external_definition", "外部定义"),
        ("industry_translation", "产业翻译"),
        ("baseline_validation", "baseline 验证"),
        ("fact_validation", "事实验证"),
        ("market_signal", "市场信号"),
    ]
    lines = ["| 证据层 | 当前证据 |", "|---|---|"]
    for key, label in labels:
        values = as_list(stack.get(key))
        lines.append(f"| {label} | {'；'.join(values) if values else '待补'} |")
    return "\n".join(lines)


def company_tier(company: dict) -> str:
    flags = company_qc_flags(company)
    buckets = company.get("evidence_buckets", {}) or {}
    strength = company.get("strength", "related")
    if "graph_only_only" in flags or "missing_evidence" in flags:
        return "Watch"
    if "weak_granularity" in flags and strength != "core":
        return "Watch"
    if strength == "core" and (buckets.get("baseline") or buckets.get("delta") or buckets.get("curated_research")):
        return "Tier 1"
    if strength == "related" and (buckets.get("baseline") or buckets.get("delta") or buckets.get("curated_research")):
        return "Tier 2"
    if strength == "peripheral":
        return "Noise"
    return "Tier 3"


def company_evidence_tiers_section(context: dict, companies: list[dict] | None = None) -> str:
    rows = context.get("company_evidence_tiers", []) if isinstance(context, dict) else []
    lines = ["| 公司 | Tier | 依据 | 命中层级 | 缺失验证 |", "|---|---|---|---|---|"]
    if not isinstance(rows, list) or not rows:
        for company in (companies or [])[:20]:
            tier = company_tier(company)
            flags = company_qc_flags(company)
            if tier == "Noise" and "weak_granularity" not in flags:
                continue
            missing = []
            if not company.get("evidence_buckets", {}).get("baseline"):
                missing.append("baseline")
            if "weak_granularity" in flags:
                missing.append("直接业务/收入占比")
            if "graph_only_only" in flags:
                missing.append("公告/年报/研报原文")
            lines.append(
                "| {company} | {tier} | {basis} | {matched} | {missing} |".format(
                    company=company.get("name", ""),
                    tier=tier,
                    basis=evidence_bucket_summary(company),
                    matched="、".join(company.get("chain_layers", [])[:3]) or "待补",
                    missing="、".join(missing) or "无",
                )
            )
        return "\n".join(lines) if len(lines) > 2 else "- 暂无可分层公司。"
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {company} | {tier} | {basis} | {matched} | {missing} |".format(
                company=row.get("company", ""),
                tier=row.get("tier", ""),
                basis=row.get("basis", ""),
                matched="、".join(as_list(row.get("matched_layer"))),
                missing="、".join(as_list(row.get("missing_validation"))),
            )
        )
    return "\n".join(lines)


def segment_scores_section(context: dict) -> str:
    rows = context.get("segment_scores", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要把新词拆成技术模块和产业环节，标注 high/medium_high/medium/low。"
    lines = ["| 环节 | 相关度 | 映射概念 | 判断理由 |", "|---|---|---|---|"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('segment','')} | {row.get('relevance','')} | {'、'.join(as_list(row.get('mapped_concepts')))} | {row.get('reason','')} |"
        )
    return "\n".join(lines)


def adjacent_concepts_section(context: dict) -> str:
    rows = context.get("adjacent_concepts", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要区分相邻概念，避免把相似模式混用。"
    lines = ["| 相邻概念 | 区别 |", "|---|---|"]
    for row in rows:
        if isinstance(row, dict):
            lines.append(f"| {row.get('name','')} | {row.get('difference','')} |")
        else:
            lines.append(f"| {row} | 待补 |")
    return "\n".join(lines)


def capability_and_rules_section(context: dict) -> str:
    if not isinstance(context, dict) or not context:
        return "- 待补"
    parts = [
        "### 能力栈",
        bullets(as_list(context.get("capability_stack")), "待补"),
        "",
        "### 公司筛选规则",
        bullets(as_list(context.get("company_screening_rules")), "待补"),
        "",
        "### 排除规则",
        bullets(as_list(context.get("company_exclusion_rules")), "待补"),
        "",
        "### 证据要求",
        bullets(as_list(context.get("evidence_requirements")), "待补"),
    ]
    return "\n".join(parts)


def demand_drivers_section(context: dict) -> str:
    if not isinstance(context, dict) or not context:
        return "- 待补"
    parts = [
        "### 需求驱动",
        bullets(as_list(context.get("demand_drivers")), "待补"),
        "",
        "### 受益链条",
        bullets(as_list(context.get("core_benefit_links")), "待补"),
        "",
        "### 验证节点",
        bullets(as_list(context.get("verification_nodes")), "待补"),
        "",
        "### 瓶颈与反证",
        bullets(as_list(context.get("bottlenecks")), "待补"),
    ]
    return "\n".join(parts)


def industry_chain_map_section(context: dict) -> str:
    chain = context.get("industry_chain_map", {}) if isinstance(context, dict) else {}
    if not isinstance(chain, dict) or not chain:
        upstream = as_list(context.get("upstream")) if isinstance(context, dict) else []
        midstream = as_list(context.get("midstream")) if isinstance(context, dict) else []
        downstream = as_list(context.get("downstream")) if isinstance(context, dict) else []
        if not any([upstream, midstream, downstream]):
            return "- 待补：需要把方向放进上游材料/设备、中游制造、下游需求。"
        chain = {
            "upstream_materials": [{"name": x} for x in upstream],
            "midstream": [{"name": x} for x in midstream],
            "downstream": [{"name": x} for x in downstream],
        }
    labels = {
        "downstream": "下游需求",
        "midstream": "中游制造/工艺",
        "upstream_materials": "上游材料",
        "upstream_equipment": "上游设备",
    }
    lines = ["| 层级 | 条目 | 证据类型 |", "|---|---|---|"]
    for key in ["downstream", "midstream", "upstream_materials", "upstream_equipment"]:
        items = chain.get(key, [])
        if not items:
            lines.append(f"| {labels[key]} | 待补 |  |")
            continue
        names = []
        evidence_types = []
        for item in items:
            if isinstance(item, dict):
                names.append(str(item.get("name", "")))
                if item.get("evidence_type"):
                    evidence_types.append(str(item.get("evidence_type")))
            else:
                names.append(str(item))
        lines.append(f"| {labels[key]} | {'、'.join(x for x in names if x)} | {'、'.join(sorted(set(evidence_types)))} |")
    return "\n".join(lines)


def match_report_contexts(term: str, primary: str, matches: list[str], report_contexts: dict) -> list[dict]:
    reports = report_contexts.get("reports", {}) if isinstance(report_contexts, dict) else {}
    needles = {normalize(x) for x in [term, primary] + matches if x}
    exact_rows = []
    related_rows = []
    for source_name, ctx in reports.items():
        if not isinstance(ctx, dict):
            continue
        if should_skip_report_context(term, source_name, ctx):
            continue
        concept_norm = normalize(ctx.get("concept", ""))
        direct_hit = any(n and (n == concept_norm or context_term_hit(n, source_name)) for n in needles)
        related_hit = any(context_term_hit(n, x) for n in needles for x in (ctx.get("related_concepts", []) or []))
        if direct_hit:
            row = dict(ctx)
            row["source_name"] = source_name
            exact_rows.append(row)
        elif related_hit:
            row = dict(ctx)
            row["source_name"] = source_name
            related_rows.append(row)
    return (exact_rows[:6] or related_rows[:4])


def should_skip_report_context(term: str, source_name: str, ctx: dict) -> bool:
    query = normalize(term)
    if "创新药" not in query:
        return False
    explicit_rwa = any(token in query for token in ("rwa", "真实世界资产", "区块链", "web3", "数字资产"))
    if explicit_rwa:
        return False
    haystack = " ".join(
        [
            str(source_name or ""),
            str(ctx.get("concept", "")),
            " ".join(str(x) for x in ctx.get("related_concepts", []) or []),
            json.dumps(ctx.get("supply_chain", {}), ensure_ascii=False),
            " ".join(str(ev.get("text", "")) for ev in (ctx.get("evidence", []) or []) if isinstance(ev, dict)),
        ]
    ).lower()
    off_topic_tokens = ("rwa", "真实世界资产", "区块链", "web3", "数字资产", "kucoin", "交易所")
    return any(token in haystack for token in off_topic_tokens)


def filtered_report_context_values(values: list[str]) -> list[str]:
    noise_tokens = (
        "生态",
        "国产化率",
        "应用场景",
        "产业链",
        "中游制造层",
        "下游应用层",
        "主战场",
    )
    out = []
    for value in values:
        text = str(value or "").strip()
        if len(text) < 3:
            continue
        if text in noise_tokens:
            continue
        if any(token == text for token in noise_tokens):
            continue
        out.append(text)
    return out[:8]


def report_contexts_section(rows: list[dict]) -> str:
    if not rows:
        return "- 本地研报上下文暂未命中。"
    labels = {
        "downstream": "下游需求",
        "midstream": "中游制造/工艺",
        "upstream_materials": "上游材料",
        "upstream_equipment": "上游设备",
        "ecosystem": "生态/配套",
    }
    lines = ["| 来源 | 概念 | 层级 | 条目 |", "|---|---|---|---|"]
    for row in rows:
        chain = row.get("supply_chain", {}) or {}
        for key in ["downstream", "midstream", "upstream_materials", "upstream_equipment", "ecosystem"]:
            values = filtered_report_context_values([str(v) for v in chain.get(key, []) if str(v).strip()])
            if values:
                lines.append(
                    f"| [[{row.get('source_name','')}]] | {row.get('concept','')} | {labels.get(key, key)} | {'、'.join(values)} |"
                )
    return "\n".join(lines) if len(lines) > 2 else "- 本地研报上下文命中，但产业链字段为空。"


def looks_like_company_clue(value: str) -> bool:
    text = str(value or "").strip()
    if not text or len(text) > 14:
        return False
    if re.fullmatch(r"[A-Za-z0-9+./ -]+", text):
        return False
    non_company_tokens = (
        "技术",
        "算力",
        "云计算",
        "数据中心",
        "互联",
        "光学",
        "服务器",
        "产业链",
        "国产化",
        "模块",
        "材料",
        "设备",
        "应用",
        "需求",
        "市场",
    )
    return not any(token in text for token in non_company_tokens)


def report_context_company_clues_section(rows: list[dict], limit: int = 20) -> str:
    clues = []
    seen = set()
    folded_noise = 0
    for row in rows:
        source = row.get("source_name") or row.get("source") or "report_contexts"
        for mention in row.get("company_mentions", []) or []:
            if not isinstance(mention, dict):
                continue
            name = str(mention.get("company") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            clues.append(
                {
                    "name": name,
                    "source": source,
                    "role": mention.get("role", "精读提及"),
                    "layer": mention.get("chain_layer", "待判定"),
                    "basis": mention.get("evidence_text", ""),
                }
            )
        supply = row.get("supply_chain", {}) or {}
        for value in supply.get("ecosystem", []) or []:
            name = str(value or "").strip()
            if any(token in name for token in REPORT_HEADING_NOISE_TOKENS) or any(token in name for token in ANALYSIS_DIMENSION_TOKENS):
                folded_noise += 1
                continue
            if not name or name in seen or not looks_like_company_clue(name):
                continue
            seen.add(name)
            clues.append(
                {
                    "name": name,
                    "source": source,
                    "role": "精读上下文生态/配套线索",
                    "layer": "ecosystem",
                    "basis": "来自 full 精读 supply_chain.ecosystem，仅作候选线索。",
                }
            )
    if not clues:
        return f"- 暂无。{'已折叠章节/分析噪声 ' + str(folded_noise) + ' 条。' if folded_noise else ''}"
    lines = []
    if folded_noise:
        lines.append(f"- 已折叠章节/分析噪声 {folded_noise} 条。")
        lines.append("")
    lines.extend(["| 线索 | 来源 | 环节 | 角色/依据 | 边界 |", "|---|---|---|---|---|"])
    for item in clues[:limit]:
        lines.append(f"| {item['name']} | {item['source']} | {item['layer']} | {str(item['role'])[:80]}；{str(item['basis'])[:80]} | 只作 full 精读上下文线索，不写入 entities，不直接升核心 |")
    return "\n".join(lines)


def merge_context_lists(rows: list[dict], field: str, limit: int = 12) -> list[str]:
    values = []
    for row in rows:
        value = row.get(field)
        if isinstance(value, list):
            values.extend(str(x) for x in value)
        elif value:
            values.append(str(value))
    return unique(values)[:limit]


GENERIC_DIRECTION_TOKENS = (
    "产业", "行业", "市场", "规模", "报告", "研究", "分析", "格局", "背景", "趋势", "现状", "预期",
    "企业", "公司", "供应商", "供应链", "产业链", "第一梯队", "第二梯队", "第三梯队", "投资价值", "市场份额",
    "概念", "人工智能", "云计算", "产业概况", "增长驱动",
)

ANALYSIS_DIMENSION_TOKENS = (
    "盈利能力", "市场规模", "增长预测", "产能水平", "扩张计划", "边际份额", "发展阶段", "技术发展",
    "技术路径", "产业趋势", "投资机会", "竞争格局", "价值分布", "市场预期", "发展现状", "前景",
    "能力分级", "分级体系", "代际", "技术特征", "投资标的", "纯度标准", "标准体系", "技术要求",
    "Token 成本", "token 成本", "Token成本", "token数", "Token 数", "成本",
)

REPORT_HEADING_NOISE_TOKENS = (
    "研究背景", "研究目标", "产业链结构", "核心供应商分析", "产业基础", "技术路径分析",
    "报告", "摘要", "结论", "深度研究", "新变化", "新格局", "章节", "目录", "产业链",
)

DOWNSTREAM_SCENARIO_TOKENS = {
    "新能源汽车", "消费电子", "储能", "储能系统", "机器人", "无人机", "航空航天", "eVTOL", "风力发电",
    "数据中心", "云厂商", "运营商", "医院", "药店", "AI 服务器", "AI服务器", "服务器",
    "芯片制造", "半导体制造", "晶圆制造", "EUV", "EUV 光刻机", "光伏", "光伏石英坩埚",
    "金融服务", "医疗健康", "制造业", "企业服务",
}

ECOSYSTEM_NAME_TOKENS = {
    "安费诺", "Amphenol", "莫仕", "Molex", "泰科电子", "TE Connectivity", "英伟达", "微软", "微软 Azure", "亚马逊", "谷歌", "Meta", "苹果", "特斯拉", "特斯拉供应链", "OpenAI", "博通", "紫金矿业", "住友电工", "恒丰特导", "中国联塑",
}

ORGANIZATION_ENTITY_TOKENS = {
    "Research", "研究院", "研究所", "电科院", "科学院", "大学", "ASML", "蔡司", "Cymer",
    "Neuralink", "Synchron", "Medtronic", "Abbott", "Blackrock", "IMEC", "NeuroPace",
}

CORE_DIRECTION_KEYWORDS = (
    "电解质", "负极", "正极", "设备", "电芯", "材料", "机床", "磁材", "光模块", "CRO", "CDMO", "ADC", "GLP", "CAR-T",
    "电极", "铜缆", "铜连接", "连接器", "互连", "背板", "线束", "PAM4", "DAC", "ACC", "AEC", "调制", "CPO", "硅光",
    "数控", "五轴", "刀具", "压铸", "注塑", "锂盐", "集流体", "石英砂", "石英材料", "石英器件",
    "Agent", "智能体", "RPA", "工作流", "编排", "推理", "多模态", "端侧", "AI应用", "智能硬件",
    "光刻", "曝光", "显影", "涂胶", "光源", "光学", "物镜", "工件台", "掩模", "对准", "量测",
    "脑电", "电极", "传感", "神经调控", "DBS", "医疗器械", "临床", "康复", "植入式", "非侵入式", "半侵入式",
    "6G", "5G-A", "基站", "核心网", "太赫兹", "毫米波", "射频", "天线", "相控阵", "T/R", "TR组件", "卫星",
    "空天地", "通感", "RIS", "智能超表面", "原型机", "测试仪器", "网络设备",
)

COMPANY_LIKE_SUFFIXES = ("科技", "股份", "集团", "电工", "光电", "电子", "通信", "材料", "精密", "互连", "特导", "半导体")


ADJACENT_THEME_BY_DOMAIN = {
    "high_speed_interconnect": ("CPO", "共封装光学", "光模块", "光芯片", "硅光", "先进封装", "PCB", "HDI", "mSAP", "芯片概念", "人工智能", "云计算"),
    "optical_interconnect": ("铜缆", "DAC", "ACC", "AEC"),
    "energy_storage": ("光模块", "CPO", "PCB", "AI服务器", "人工智能", "云计算"),
    "software_ai_application": ("国产AI芯片", "AI芯片", "算力基础设施", "服务器", "数据中心", "云计算", "芯片概念"),
    "semiconductor_materials": ("EUV", "光刻机", "光伏石英坩埚", "光伏", "光刻胶", "掩模版"),
    "semiconductor_patterning_equipment": ("ASML", "蔡司", "Cymer", "EUV", "先进封装", "光刻胶"),
    "next_generation_communications": ("CPO", "光模块", "硅光", "云计算", "算力租赁", "AI算力", "低空经济", "商业航天"),
}


def primary_domains_for_term(term: str) -> set[str]:
    return infer_theme_domains(str(term or ""))


DOMAIN_PRIORITY = (
    "bioelectronic_medical_device",
    "next_generation_communications",
    "software_ai_application",
    "semiconductor_patterning_equipment",
    "semiconductor_materials",
    "advanced_battery_materials",
    "high_speed_interconnect",
    "optical_interconnect",
    "critical_materials",
    "industrial_equipment",
    "power_equipment",
    "energy_storage",
    "pharma",
    "compute",
    "power",
    "semiconductor",
)


def dominant_domains(domains: set[str]) -> set[str]:
    for domain in DOMAIN_PRIORITY:
        if domain in domains:
            return {domain}
    return set(domains)


def is_adjacent_direction_label(value: str, primary_domains: set[str]) -> bool:
    text = str(value or "")
    for domain in primary_domains:
        if any(token_hit(text, token) for token in ADJACENT_THEME_BY_DOMAIN.get(domain, ())):
            return True
    return False


def classify_runtime_direction(value: str, primary_domains: set[str] | None = None) -> str:
    text = str(value or "").strip()
    if not text or len(text) < 2:
        return "generic_context"
    if text in {"固态电池", "工业母机", "稀土永磁", "创新药", "储能", "光模块", "算力租赁", "半导体石英砂", "AI Agent与智能体", "AI智能体", "AI应用"}:
        return "generic_context"
    if any(token in text for token in REPORT_HEADING_NOISE_TOKENS):
        return "report_heading_noise"
    if any(token in text for token in ANALYSIS_DIMENSION_TOKENS):
        return "analysis_dimension"
    has_core_keyword = any(token in text for token in CORE_DIRECTION_KEYWORDS)
    if any(token in text for token in DOWNSTREAM_SCENARIO_TOKENS) and not has_core_keyword:
        return "downstream_scenario"
    if any(token in text for token in ORGANIZATION_ENTITY_TOKENS):
        return "ecosystem_entity"
    if any(token in text for token in ECOSYSTEM_NAME_TOKENS):
        return "ecosystem_entity"
    if any(suffix in text for suffix in COMPANY_LIKE_SUFFIXES) and not has_core_keyword:
        return "ecosystem_entity"
    if any(token in text for token in GENERIC_DIRECTION_TOKENS) and not has_core_keyword:
        return "generic_context"
    if primary_domains and is_adjacent_direction_label(text, primary_domains):
        return "adjacent_theme"
    if len(text) <= 4 and not has_core_keyword:
        return "generic_context"
    return "core_direction"


def is_generic_direction_label(value: str, primary_domains: set[str] | None = None) -> bool:
    return classify_runtime_direction(value, primary_domains) != "core_direction"


def runtime_direction_tokens(label: str) -> tuple[str, ...]:
    text = str(label or "").strip()
    tokens = [text]
    for sep in ("/", "、", "-", "—", "与", "和", "及", "+"):
        if sep in text:
            tokens.extend(part.strip() for part in text.split(sep) if part.strip())
    if "硫化物" in text and "电解质" in text:
        tokens.extend(["硫化物", "硫化物固态电解质", "硫化锂"])
    if "氧化物" in text and "电解质" in text:
        tokens.extend(["氧化物", "氧化物固态电解质", "LLZO", "锆源"])
    if "聚合物" in text and "电解质" in text:
        tokens.extend(["聚合物", "聚合物固态电解质"])
    if "负极" in text:
        tokens.extend(["负极材料", "金属负极", "硅碳", "硅碳负极"])
    if "正极" in text:
        tokens.extend(["正极材料", "高镍", "高镍正极", "前驱体"])
    if "设备" in text or "干法电极" in text:
        tokens.extend(["中试线", "量产线", "设备", "辊压", "干法电极设备"])
    if "集流体" in text or "铜箔" in text:
        tokens.extend(["铜箔", "复合集流体", "铝箔"])
    if "铜缆" in text or "铜连接" in text:
        tokens.extend(["高速铜缆", "铜缆高速连接", "DAC", "ACC", "AEC", "有源铜缆", "无源铜缆"])
    if "连接器" in text or "背板" in text or "线束" in text or "互连" in text:
        tokens.extend(["高速连接器", "连接器", "背板", "线束", "高速互连", "高速线束"])
    return tuple(unique(tokens))


def compact_direction_label(value: str) -> str:
    return re.sub(r"[\s/、\-—_（）()]+", "", str(value or "").lower())


def is_redundant_direction_label(label: str, existing_labels: list[str]) -> bool:
    text = compact_direction_label(label)
    if len(text) < 3:
        return False
    for existing in existing_labels:
        base = compact_direction_label(existing)
        if base and text != base and text in base:
            return True
    return False


def is_redundant_direction_row(label: str, existing_rows: list[dict]) -> bool:
    if is_redundant_direction_label(label, [str(row.get("label", "")) for row in existing_rows if isinstance(row, dict)]):
        return True
    text = compact_direction_label(label)
    for row in existing_rows:
        if not isinstance(row, dict):
            continue
        for token in row.get("tokens", ()) or ():
            token_text = compact_direction_label(token)
            if len(token_text) >= 4 and token_text in text:
                return True
    return False


def runtime_direction_frame(term: str, raw_terms: list[str], evidence_texts: list[str], related: list[str]) -> dict:
    seed_text = " ".join([term] + related + raw_terms[:20])
    primary_domains = primary_domains_for_term(term)
    inferred_domains = primary_domains or infer_theme_domains(seed_text)
    allowed_domains = sorted(dominant_domains(inferred_domains))
    secondary_domains = set(inferred_domains) - set(allowed_domains)
    directions = []
    secondary = {key: [] for key in ("adjacent_theme", "ecosystem_entity", "downstream_scenario", "analysis_dimension", "generic_context", "report_heading_noise")}
    seen = set()
    ordered_terms = unique(related + raw_terms)
    haystack = " ".join(evidence_texts + raw_terms + related + [term])
    for rule in CAPABILITY_RULES:
        if not (set(rule.get("domains", ())) & set(allowed_domains)):
            continue
        if not any(token_hit(haystack, token) for token in rule.get("tokens", ())):
            continue
        label = str(rule.get("label", "")).strip()
        if not label or label in seen:
            continue
        seen.add(label)
        directions.append(
            {
                "label": label,
                "tokens": rule.get("tokens", ()),
                "theme": rule.get("theme", label),
                "why": rule.get("why", ""),
                "validation": rule.get("validation", ""),
                "source": "capability_rule",
            }
        )
    capability_direction_count = len(directions)
    runtime_add_limit = 0 if capability_direction_count >= 3 else max(0, 6 - capability_direction_count)
    runtime_added = 0
    for rule in CAPABILITY_RULES:
        if not (set(rule.get("domains", ())) & secondary_domains):
            continue
        if set(rule.get("domains", ())) & set(allowed_domains):
            continue
        if not any(token_hit(haystack, token) for token in rule.get("tokens", ())):
            continue
        label = str(rule.get("label", "")).strip()
        if label and label not in seen:
            seen.add(label)
            secondary.setdefault("adjacent_theme", []).append(
                {"label": label, "classification": "adjacent_theme", "source": "secondary_domain_rule"}
            )
    core_labels = {
        str(value or "").strip()
        for value in ordered_terms
        if classify_runtime_direction(str(value or "").strip(), set(allowed_domains)) == "core_direction"
    }
    for value in ordered_terms:
        label = str(value or "").strip()
        if label in seen:
            continue
        if label == str(term or "").strip():
            secondary.setdefault("generic_context", []).append(
                {"label": label, "classification": "generic_context", "source": "theme_self_label"}
            )
            seen.add(label)
            continue
        if not context_term_hit(label, haystack):
            continue
        seen.add(label)
        classification = classify_runtime_direction(label, set(allowed_domains))
        if classification != "core_direction":
            if label in core_labels:
                continue
            secondary.setdefault(classification, []).append(
                {
                    "label": label,
                    "classification": classification,
                    "source": "runtime_direction_frame",
                }
            )
            continue
        if len(directions) >= 5 and not any(token in label for token in CORE_DIRECTION_KEYWORDS):
            secondary.setdefault("generic_context", []).append(
                {"label": label, "classification": "generic_context", "source": "low_confidence_runtime_direction"}
            )
            continue
        if runtime_added >= runtime_add_limit:
            secondary.setdefault("generic_context", []).append(
                {"label": label, "classification": "generic_context", "source": "runtime_direction_deferred"}
            )
            continue
        if is_redundant_direction_row(label, directions):
            secondary.setdefault("generic_context", []).append(
                {"label": label, "classification": "generic_context", "source": "folded_duplicate_direction"}
            )
            continue
        directions.append(
            {
                "label": label,
                "tokens": runtime_direction_tokens(label),
                "theme": label,
                "why": "来自 report_contexts/full 精读的运行时细分方向，作为词典未覆盖时的兜底方向。",
                "validation": f"后续跟踪 {label} 是否被更多研报/精选逻辑强化，并能映射到公司级产品、工艺或客户线索。",
                "source": "runtime_direction_frame",
            }
        )
        runtime_added += 1
        if len(directions) >= 20:
            break
    return {
        "allowed_domains": allowed_domains,
        "secondary_domains": sorted(secondary_domains),
        "directions": directions,
        "secondary": secondary,
    }


def runtime_context_from_report_contexts(term: str, rows: list[dict]) -> dict:
    if not rows:
        return {}
    chain = {key: [] for key in ["downstream", "midstream", "upstream_materials", "upstream_equipment"]}
    ecosystem = []
    evidence_texts = []
    sources = []
    for row in rows:
        source = row.get("source_name") or row.get("source") or ""
        if source:
            sources.append(str(source))
        supply = row.get("supply_chain", {}) or {}
        for key in chain:
            for value in supply.get(key, []) or []:
                text = str(value).strip()
                if text:
                    chain[key].append({"name": text, "evidence_type": "report_context"})
        for value in supply.get("ecosystem", []) or []:
            text = str(value).strip()
            if text:
                ecosystem.append(text)
        for ev in row.get("evidence", []) or []:
            if isinstance(ev, dict) and ev.get("text"):
                evidence_texts.append(str(ev.get("text")))
    related = merge_context_lists(rows, "related_concepts", 24)
    raw_midstream_terms = unique([item["name"] for item in chain["midstream"]])[:24]
    upstream_terms = unique([item["name"] for item in chain["upstream_materials"] + chain["upstream_equipment"]])[:24]
    direction_frame = runtime_direction_frame(term, raw_midstream_terms + upstream_terms, evidence_texts, related)
    direction_rows = [row for row in direction_frame.get("directions", [])[:8] if isinstance(row, dict)]
    midstream_terms = [row["label"] for row in direction_rows if row.get("label")]
    if not midstream_terms:
        midstream_terms = context_subdirection_terms(term, raw_midstream_terms[:8], evidence_texts, related)
        direction_rows = [
            {
                "label": value,
                "theme": value,
                "why": "来自本地 full 精读上下文的候选方向，需要继续用公司级产品、工艺或客户线索确认。",
                "validation": f"后续跟踪 {value} 是否被更多研报/精选逻辑强化。",
                "source": "context_subdirection_terms",
            }
            for value in midstream_terms
        ]
    upstream_terms = upstream_terms[:8]
    downstream_terms = unique([item["name"] for item in chain["downstream"]])[:8]
    segment_scores = []
    if midstream_terms:
        segment_scores.append({"segment": "核心制造/工艺", "relevance": "high", "mapped_concepts": midstream_terms[:6], "reason": "来自已精读 full.md 的中游/工艺上下文。"})
    if upstream_terms:
        segment_scores.append({"segment": "上游材料/设备", "relevance": "medium_high", "mapped_concepts": upstream_terms[:6], "reason": "来自已精读 full.md 的上游配套上下文，需公司级证据验证。"})
    if downstream_terms:
        segment_scores.append({"segment": "下游需求", "relevance": "medium", "mapped_concepts": downstream_terms[:6], "reason": "来自已精读 full.md 的需求场景，用于解释题材传导，不直接扩公司。"})
    demand_drivers = unique([x for x in downstream_terms + ecosystem if x])[:10]
    direction_scan = []
    for idx, row in enumerate(direction_rows[:6], 1):
        value = str(row.get("label", "")).strip()
        if not value:
            continue
        direction_scan.append(
            {
                "direction": value,
                "sector": row.get("theme") or term,
                "prosperity": direction_prosperity_text(term, row, demand_drivers),
                "mention_frequency": "本地精读命中",
                "recognition_level": direction_recognition_level(row),
                "classification": direction_classification_text(row),
                "core_catalyst": direction_catalyst_text(row, demand_drivers),
                "candidate_companies": [],
            }
        )
    progress_ranking = []
    for idx, row in enumerate(direction_scan[:5], 1):
        progress_ranking.append(
            {
                "direction": row["direction"],
                "stage": "待信号验证",
                "recognition_level": row["recognition_level"],
                "evidence_level": "L1 curated research",
                "progress_score": max(40, 75 - idx * 5),
                "key_signal": row["core_catalyst"],
                "next_validation": direction_next_validation(row["direction"], direction_rows),
                "priority": "补证跟踪",
            }
        )
    return {
        "definition": evidence_texts[0] if evidence_texts else f"{term}：来自已精读 full.md 的本地研报上下文。",
        "parent_concepts": related[:8],
        "related_terms": related,
        "demand_drivers": demand_drivers,
        "capability_stack": midstream_terms[:8],
        "company_screening_rules": ["公司角色直接落在题材关键环节", "PDF研报/精选逻辑/脱水文本形成多源共识", "baseline 只校验基础业务是否冲突"],
        "company_exclusion_rules": ["只命中下游需求或泛生态但缺直接产品", "只由旧图谱重建或弱相关文本支撑", "full.md 仅作题材结构上下文，不直接升级公司事实"],
        "evidence_requirements": ["PDF ingest 研报、精选逻辑、脱水文本是当前主信源", "baseline 提供基础画像与主营校验", "公告/订单/业绩作为 future validation slot，不参与高权重核心判断"],
        "evidence_stack": {
            "industry_translation": [f"命中已精读研报：{x}" for x in unique(sources)[:6]],
            "baseline_validation": ["entity_exposures/evidence_index 中的 baseline 只用于基础画像和主营校验。"],
            "fact_validation": ["公告、订单、业绩暂作后续验证空位，不作为当前核心公司高权重判断。"],
            "market_signal": ["精选逻辑/脱水/强势股文本用于识别市场共识和题材发酵阶段。"],
        },
        "segment_scores": segment_scores,
        "industry_chain_map": chain,
        "direction_scan": direction_scan,
        "direction_frame": direction_frame,
        "progress_ranking": progress_ranking,
        "demand_scenarios": [
            {"scenario": value, "logic": "来自已精读 full.md 的下游需求或应用场景。", "process_requirement": "需映射到中游核心环节和公司级能力。", "evidence": ["report_contexts.json"]}
            for value in downstream_terms[:5]
        ],
        "validation_checklist": direction_validation_checklist(direction_rows[:6]),
        "candidate_companies": [],
        "source_urls": unique(sources)[:8],
        "confidence": "high",
        "extraction_quality": {
            "mode": "report_contexts_runtime",
            "total_items": sum(len(v) for v in chain.values()),
            "source_backed_items": sum(len(v) for v in chain.values()),
            "inferred_items": 0,
            "missing_fields": [],
            "review_required": True,
        },
    }


def direction_row_lookup(label: str, rows: list[dict]) -> dict:
    for row in rows:
        if isinstance(row, dict) and row.get("label") == label:
            return row
    return {}


def direction_prosperity_text(term: str, row: dict, demand_drivers: list[str]) -> str:
    why = str(row.get("why") or "").strip()
    label = str(row.get("label") or "").strip()
    demand = "、".join(demand_drivers[:2])
    if why:
        tail = f"；需求牵引看 {demand}" if demand else ""
        return f"{why}{tail}。"
    return f"{label} 是 {term} 的可验证细分环节，后续需要看公司级产品、客户和订单是否兑现。"


def direction_recognition_level(row: dict) -> str:
    source = str(row.get("source") or "")
    if source == "capability_rule":
        return "L1结构线索 + L3待验证"
    if source == "runtime_direction_frame":
        return "L1精读候选 + L3待验证"
    return "L1-L3"


def direction_classification_text(row: dict) -> str:
    source = str(row.get("source") or "")
    if source == "capability_rule":
        return "能力骨架"
    if source == "runtime_direction_frame":
        return "精读补充"
    return "精读线索"


def direction_catalyst_text(row: dict, demand_drivers: list[str]) -> str:
    validation = str(row.get("validation") or "").strip()
    if validation:
        return validation
    return "、".join(demand_drivers[:3]) or "待补产品/客户/订单验证"


def direction_next_validation(label: str, rows: list[dict]) -> str:
    row = direction_row_lookup(label, rows)
    validation = str(row.get("validation") or "").strip()
    if validation:
        return validation
    return "后续研报/精选逻辑是否继续强化，公告/订单/业绩仅作验证空位"


def direction_validation_checklist(rows: list[dict]) -> list[dict]:
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        if not label:
            continue
        validation = str(row.get("validation") or "").strip() or f"{label} 是否被更多研报/精选逻辑和公司级证据强化"
        items.append({"item": f"{label}：{validation}", "why": str(row.get("why") or "确认该方向不是泛概念，而是可落到产品、工艺、客户或订单的细分环节。"), "status": "待新文本/公司证据"})
    items.extend(
        [
            {"item": "相对核心公司是否被多源研报/精选逻辑共同提及", "why": "区分核心公司与泛概念暴露", "status": "自动聚合"},
            {"item": "baseline 是否与公司题材角色冲突", "why": "只做基础画像校验，不主导核心判断", "status": "辅助校验"},
        ]
    )
    return items[:10]


def context_subdirection_terms(term: str, midstream_terms: list[str], evidence_texts: list[str], related: list[str]) -> list[str]:
    haystack = " ".join([term] + evidence_texts + related + midstream_terms)
    domains = infer_theme_domains(haystack)
    if not domains:
        return midstream_terms
    rows = [
        rule["label"]
        for rule in CAPABILITY_RULES
        if domains & set(rule.get("domains", ())) and any(token_hit(haystack, token) for token in rule.get("tokens", ()))
    ]
    return rows[:8] or midstream_terms


def demand_scenarios_section(context: dict) -> str:
    rows = context.get("demand_scenarios", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要抽取需求场景、传导逻辑和工艺要求。"
    lines = ["| 需求场景 | 逻辑 | 工艺要求 | 证据 |", "|---|---|---|---|"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('scenario','')} | {row.get('logic','')} | {row.get('process_requirement','')} | {'；'.join(as_list(row.get('evidence'))[:2])} |"
        )
    return "\n".join(lines)


def direction_scan_section(context: dict) -> str:
    rows = context.get("direction_scan", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要从主题向下扫描工艺、材料、设备、应用等细分方向。"
    lines = [
        "| 细分方向 | 所属赛道 | 景气判断 | 提及频率 | 认知层级 | 分类 | 核心催化 | 候选公司 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {direction} | {sector} | {prosperity} | {mention_frequency} | {recognition_level} | {classification} | {core_catalyst} | {companies} |".format(
                direction=row.get("direction", ""),
                sector=row.get("sector", ""),
                prosperity=row.get("prosperity", ""),
                mention_frequency=row.get("mention_frequency", "待补"),
                recognition_level=row.get("recognition_level", "待补"),
                classification=row.get("classification", "待补"),
                core_catalyst=row.get("core_catalyst", ""),
                companies="、".join(as_list(row.get("candidate_companies"))),
            )
        )
    return "\n".join(lines)


def catalyst_calendar_section(context: dict) -> str:
    rows = context.get("catalyst_calendar", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要把后续验证点拆成时间、事件和观察项。"
    lines = ["| 时间 | 事件 | 观察项 |", "|---|---|---|"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(f"| {row.get('time','')} | {row.get('event','')} | {row.get('watch_item','')} |")
    return "\n".join(lines)


def validation_checklist_section(context: dict) -> str:
    rows = context.get("validation_checklist", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要列出订单、价格、客户认证、量产、收入占比等验证事项。"
    lines = ["| 验证事项 | 重要性 | 当前状态 |", "|---|---|---|"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(f"| {row.get('item','')} | {row.get('why','')} | {row.get('status','待验证')} |")
    return "\n".join(lines)


def secondary_runtime_context_section(context: dict) -> str:
    frame = context.get("direction_frame", {}) if isinstance(context, dict) else {}
    secondary = frame.get("secondary", {}) if isinstance(frame, dict) else {}
    groups = [
        ("adjacent_theme", "相邻/替代路线", "相关但不作为当前主方向，可用于理解竞争、替代或配套关系"),
        ("ecosystem_entity", "生态/对标/海外线索", "公司、客户、海外对标或生态角色，不作为细分方向"),
        ("downstream_scenario", "下游需求场景", "解释题材发酵来源和需求牵引，不直接等同于核心环节"),
        ("analysis_dimension", "分析维度/验证指标", "用于后续验证或分析，不作为产业链细分方向"),
        ("generic_context", "泛背景/宏观语境", "帮助理解叙事背景，但权重低于公司和核心方向"),
    ]
    lines = []
    noise_rows = secondary.get("report_heading_noise", []) if isinstance(secondary, dict) else []
    noise_count = len(unique([str(row.get("label", "")).strip() for row in noise_rows if isinstance(row, dict) and str(row.get("label", "")).strip()]))
    if noise_count:
        lines.append(f"- 已折叠报告章节/标题噪声 {noise_count} 条。")
        lines.append("")
    for key, title, boundary in groups:
        rows = secondary.get(key, []) if isinstance(secondary, dict) else []
        labels = unique([str(row.get("label", "")).strip() for row in rows if isinstance(row, dict) and str(row.get("label", "")).strip()])
        if not labels:
            continue
        lines.append(f"### {title}")
        lines.append("")
        lines.append("| 线索 | 权重/边界 |")
        lines.append("|---|---|")
        for label in labels[:12]:
            lines.append(f"| {label} | {boundary} |")
        lines.append("")
    return "\n".join(lines).strip() or "- 暂无需要降权展示的相邻、生态或泛背景线索。"


def progress_ranking_section(context: dict) -> str:
    rows = context.get("progress_ranking", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要把细分方向按暗流期/萌芽期/第一轮/催化共振/一致认同排序。"
    def score(row):
        try:
            return float(row.get("progress_score", 0))
        except Exception:
            return 0
    rows = sorted([r for r in rows if isinstance(r, dict)], key=score, reverse=True)
    lines = [
        "| 序号 | 方向 | 阶段 | 认知层级 | 证据等级 | 内部进度 | 关键信号 | 下一验证 | 优先级 |",
        "|---:|---|---|---|---|---:|---|---|---|",
    ]
    for idx, row in enumerate(rows, 1):
        lines.append(
            "| {idx} | {direction} | {stage} | {recognition_level} | {evidence_level} | {progress_score} | {key_signal} | {next_validation} | {priority} |".format(
                idx=idx,
                direction=row.get("direction", ""),
                stage=row.get("stage", "待补"),
                recognition_level=row.get("recognition_level", "待补"),
                evidence_level=row.get("evidence_level", "待补"),
                progress_score=row.get("progress_score", ""),
                key_signal=row.get("key_signal", ""),
                next_validation=row.get("next_validation", ""),
                priority=row.get("priority", "待补"),
            )
        )
    return "\n".join(lines)


def candidate_company_section(context: dict, companies: list[dict]) -> str:
    candidates = as_list(context.get("candidate_companies")) if isinstance(context, dict) else []
    if not candidates:
        return "- 待补：外部资料未给候选公司线索。"
    by_name = {c.get("name"): c for c in companies}
    lines = ["| 候选公司 | 本地匹配 | 说明 |", "|---|---|---|"]
    for name in candidates:
        hit = by_name.get(name)
        if hit:
            level = "弱匹配" if is_generic_company_hit(hit) else "有证据匹配"
            note = "仅命中辅助概念，需新词证据验证" if level == "弱匹配" else "已有非泛化证据，可优先复核"
            lines.append(f"| {name} | {level} | {'、'.join(hit.get('concepts', [])[:4])}；{note} |")
        else:
            lines.append(f"| {name} | 否 | 仅为外部线索，待 baseline 或证据补充 |")
    return "\n".join(lines)


def is_generic_company_hit(company: dict) -> bool:
    roles = company.get("roles", [])
    evidence = company.get("evidence", [])
    generic_role = not roles or all(str(role).strip() == "受益标的" for role in roles)
    generic_evidence = not evidence or all("从既有" in str(item) and "重建" in str(item) for item in evidence)
    return generic_role and generic_evidence


def filter_new_term_companies(companies: list[dict], context: dict, term_matched: bool) -> tuple[list[dict], int]:
    has_company_gate = isinstance(context, dict) and any(
        context.get(key)
        for key in (
            "candidate_companies",
            "company_screening_rules",
            "company_exclusion_rules",
            "evidence_requirements",
        )
    )
    if term_matched and not has_company_gate:
        return companies, 0
    candidates = set(as_list(context.get("candidate_companies"))) if isinstance(context, dict) else set()
    kept = []
    dropped = 0
    for company in companies:
        if company.get("name") in candidates or not is_generic_company_hit(company):
            kept.append(company)
        else:
            dropped += 1
    return kept, dropped


def source_basis(company: dict) -> list[str]:
    buckets = company.get("evidence_buckets", {}) or {}
    basis = []
    if buckets.get("curated_research"):
        basis.append("PDF研报/深度研究")
    if buckets.get("delta"):
        basis.append("精选逻辑/脱水/复盘")
    if company.get("context_mentions"):
        basis.append("full精读上下文提及")
    if buckets.get("baseline"):
        basis.append("baseline基础画像")
    if buckets.get("graph_only") and not basis:
        basis.append("旧图谱/弱关联")
    return basis or ["待补来源"]


def source_consensus_count(company: dict) -> int:
    basis = source_basis(company)
    return sum(1 for item in basis if item not in {"待补来源", "旧图谱/弱关联", "baseline基础画像"})


def is_explicit_weak_company(company: dict) -> bool:
    flags = set(company_qc_flags(company))
    text = evidence_text(company)
    return (
        company.get("company_subtype") == "weak_graph"
        or "graph_only_only" in flags
        or "missing_evidence" in flags
        or "市场信号弱关联" in text
        or "图谱弱关联" in text
        or "从既有entity markdown重建" in text
        or "从既有concept markdown重建" in text
    )


def company_guardrail_note(company: dict) -> str:
    flags = [x for x in company_qc_flags(company) if x in ("weak_granularity", "review_required", "soft_fact_hardness", "chain_layer_conflict", "graph_only_only", "missing_evidence")]
    if is_explicit_weak_company(company):
        return "弱相关护栏：仅作观察，不进入相对核心。"
    if flags:
        return f"数据护栏：{ '、'.join(flags) }；不否定题材逻辑，但需要后续文本/资料继续验证。"
    return "后续看研报/精选逻辑是否继续强化；公告订单业绩仅作验证空位。"


def is_downstream_or_ecosystem_company(company: dict) -> bool:
    layers = set(normalized_chain_layers(company))
    subtype = company.get("company_subtype") or company_subtype(company)
    return bool(layers & {"downstream_application", "downstream_channel", "ecosystem"}) or subtype in {"downstream_channel", "ecosystem"}


def company_deep_dive_tier(company: dict) -> str:
    flags = set(company_qc_flags(company))
    buckets = company.get("evidence_buckets", {}) or {}
    basis = set(source_basis(company))
    if is_explicit_weak_company(company):
        return "weak"
    if has_weak_granularity_signal(company) and company.get("strength") != "core" and not buckets.get("curated_research"):
        return "weak"
    research_or_logic = bool(buckets.get("curated_research") or buckets.get("delta"))
    has_context = "full精读上下文提及" in basis
    has_baseline = bool(buckets.get("baseline"))
    consensus = source_consensus_count(company)
    subtype = company.get("company_subtype") or company_subtype(company)
    if has_baseline and not research_or_logic and not has_context and consensus == 0:
        return "weak"
    if is_downstream_or_ecosystem_company(company) and company.get("strength") != "core":
        return "watch" if research_or_logic or has_baseline or has_context else "weak"
    if company.get("strength") == "core" and research_or_logic:
        return "relative_core"
    if consensus >= 3 and subtype in {"core_subject", "component_supplier", "upstream_equipment", "upstream_materials", "service_provider"}:
        return "relative_core"
    if research_or_logic and has_context and has_baseline:
        return "relative_core"
    if "weak_granularity" in flags and company.get("strength") != "core":
        return "watch" if consensus < 2 else "related"
    if research_or_logic or (has_context and has_baseline):
        return "related"
    return "watch"


LIGHT_MODULE_SUBDIRECTION_RULES = [
    ("高速光模块/800G/1.6T", ("800G", "1.6T", "3.2T", "400G", "高速光模块", "数通光模块", "光收发模块", "光模块产能")),
    ("CPO/NPO/LPO/硅光", ("CPO", "NPO", "LPO", "硅光", "共封装光学", "光I/O", "光引擎")),
    ("光芯片/核心器件", ("光芯片", "激光器芯片", "探测器芯片", "EML", "VCSEL", "CWLaser", "PLC", "AWG", "DFB")),
    ("OCS/光交换", ("OCS", "光电路交换", "光交换", "电路交换")),
    ("PCB/HDI/mSAP配套", ("PCB", "HDI", "mSAP", "HLC", "高多层", "高频高速", "铜箔", "RTF", "HVLP")),
    ("光器件/无源器件", ("光器件", "无源光器件", "FAU", "MPO", "光纤阵列", "连接器", "耦合")),
    ("封测/设备", ("封测", "贴片", "耦合设备", "检测设备", "组装", "设备")),
    ("下游需求/运营商", ("运营商", "电信", "云厂商", "数据中心", "东数西算", "5G")),
]


ENERGY_STORAGE_SUBDIRECTION_RULES = [
    ("储能系统/集成", ("储能系统", "系统集成", "储能集成", "集成商", "大型储能", "工商业储能", "户储", "储能设备", "储能柜")),
    ("PCS/逆变器", ("PCS", "逆变器", "变流器", "储能变流", "组串式", "集中式逆变")),
    ("BMS/EMS/温控消防", ("BMS", "EMS", "热管理", "温控", "液冷", "消防", "能量管理", "电池管理")),
    ("电芯/电池系统", ("电芯", "电池系统", "磷酸铁锂", "钠电", "动力电池", "储能电池", "电池舱", "电池包")),
    ("电解液/锂盐/材料", ("电解液", "六氟磷酸锂", "6F", "VC", "正极", "负极", "隔膜", "锂盐", "碳酸锂", "石墨", "三元")),
    ("变压器/电源/HVDC", ("变压器", "电源", "UPS", "HVDC", "SST", "一体柜", "数据中心电源", "弹性直流")),
    ("海外/大储需求", ("海外储能", "海外能源", "美国储能", "欧洲储能", "大储", "电网侧", "源网荷储", "新能源消纳")),
    ("下游场景/数据中心", ("数据中心", "互联网大厂", "腾讯", "阿里", "算力中心", "IDC")),
]


INNOVATIVE_DRUG_SUBDIRECTION_RULES = [
    ("小分子创新药", ("小分子", "心血管", "S086", "口服", "化学药", "靶点", "管线")),
    ("ADC/双抗/单抗", ("ADC", "双抗", "单抗", "抗体", "PD-1", "HER2", "EGFR", "抗体偶联")),
    ("GLP-1/多肽药物", ("GLP-1", "GLP1", "多肽", "司美格鲁肽", "利拉鲁肽", "减肥药")),
    ("细胞基因治疗", ("细胞治疗", "基因治疗", "CAR-T", "CAR T", "GCT", "病毒载体", "细胞基因")),
    ("CRO/临床试验", ("CRO", "临床试验", "临床研究", "注册申报", "患者入组")),
    ("CDMO/原料药外包", ("CDMO", "CMO", "原料药", "中间体", "定制研发生产", "外包服务", "小分子CDMO")),
    ("License-out/BD出海", ("license-out", "license out", "BD", "出海", "海外授权", "权益转让", "首付款", "里程碑")),
    ("药械一体化", ("药械一体", "药械组合", "无创治疗", "治疗产品")),
    ("商业化/院外渠道", ("商业化", "院外", "药店", "零售", "流通", "销售渠道")),
    ("中药创新药", ("中药创新药", "中成药", "中药", "院内制剂")),
]


CAPABILITY_RULES = [
    {"label": "高速光模块/800G/1.6T", "domains": ("optical_interconnect", "compute"), "tokens": ("800G", "1.6T", "3.2T", "400G", "高速光模块", "数通光模块", "光收发模块", "光模块产能"), "theme": "高速光模块", "why": "对应AI数据中心高速互联和带宽升级需求", "validation": "后续文本是否继续强化800G/1.6T/3.2T放量或客户需求"},
    {"label": "CPO/NPO/LPO/硅光", "domains": ("optical_interconnect", "compute"), "tokens": ("CPO", "NPO", "LPO", "硅光", "共封装光学", "光I/O", "光引擎"), "theme": "CPO/LPO/硅光", "why": "对应低功耗高速互连和光电融合方案", "validation": "CPO/LPO/硅光方案是否从概念进入更多研报共识"},
    {"label": "光芯片/核心器件", "domains": ("optical_interconnect",), "tokens": ("光芯片", "激光器芯片", "探测器芯片", "EML", "VCSEL", "CWLaser", "PLC", "AWG", "DFB"), "theme": "光芯片/核心器件", "why": "处在国产化率低、价值量高的核心器件瓶颈环节", "validation": "光芯片/EML/VCSEL/PLC/AWG是否被更多资料确认为瓶颈环节"},
    {"label": "OCS/光交换", "domains": ("optical_interconnect", "compute"), "tokens": ("OCS", "光电路交换", "光交换", "电路交换"), "theme": "OCS/光交换", "why": "对应数据中心光交换和网络架构升级", "validation": "OCS是否从网络架构概念进入产品、样机、客户测试或更多产业链公司提及"},
    {"label": "PCB/HDI/mSAP配套", "domains": ("optical_interconnect", "compute", "semiconductor"), "tokens": ("PCB", "HDI", "mSAP", "HLC", "高多层", "高频高速", "铜箔", "RTF", "HVLP"), "theme": "PCB/HDI/mSAP", "why": "对应高速硬件系统中的高频高速连接和板级配套", "validation": "PCB/HDI/mSAP是否从配套逻辑升级为独立发酵方向"},
    {"label": "光器件/无源器件", "domains": ("optical_interconnect",), "tokens": ("光器件", "无源光器件", "FAU", "MPO", "光纤阵列", "连接器", "耦合"), "theme": "无源光器件/连接器", "why": "对应光互联中的无源器件和连接配套", "validation": "FAU、MPO、光纤阵列、连接器、耦合等是否被更多资料确认受益"},
    {"label": "高速铜缆/DAC/ACC/AEC", "domains": ("high_speed_interconnect",), "tokens": ("高速铜缆", "铜缆高速连接", "铜连接", "高速铜连接", "DAC", "ACC", "AEC", "有源铜缆", "无源铜缆"), "theme": "高速铜缆/DAC/ACC/AEC", "why": "对应AI服务器和数据中心短距高速互连中的铜连接方案", "validation": "DAC/ACC/AEC产品迭代、速率升级、客户认证和AI服务器导入是否继续强化"},
    {"label": "高速连接器/背板/线束", "domains": ("high_speed_interconnect",), "tokens": ("高速连接器", "连接器", "背板", "高速背板", "线束", "高速线束", "互连组件", "高速互连"), "theme": "高速连接器/背板/线束", "why": "对应高速铜互连中的连接器、背板和线束组件环节", "validation": "高速连接器、背板、线束的速率、良率、认证和供货能力是否继续强化"},
    {"label": "高速传输材料/屏蔽散热", "domains": ("high_speed_interconnect",), "tokens": ("高速传输材料", "线缆材料", "低损耗", "屏蔽", "绝缘", "导体", "散热", "热管理"), "theme": "高速传输材料/屏蔽散热", "why": "对应高速铜缆在信号完整性、低损耗和散热约束下的材料配套", "validation": "低损耗材料、屏蔽散热方案和高速传输稳定性是否被更多资料验证"},
    {"label": "Agent应用/企业服务", "domains": ("software_ai_application",), "tokens": ("AI智能体", "AI Agent", "Agent应用", "企业服务", "办公智能体", "AI员工", "智能客服", "RPA"), "theme": "Agent应用/企业服务", "why": "对应大模型从聊天工具走向自动执行任务和企业流程重构", "validation": "企业客户、付费订阅、项目落地和续费率是否继续强化"},
    {"label": "工作流编排/工具调用", "domains": ("software_ai_application",), "tokens": ("工作流", "编排", "工具调用", "函数调用", "插件", "MCP", "自动化流程", "低代码"), "theme": "工作流编排/工具调用", "why": "对应智能体从单轮问答走向多步骤任务执行的中间层能力", "validation": "工具调用、流程编排和行业模板是否有产品化与客户验证"},
    {"label": "模型推理/多模态交互", "domains": ("software_ai_application",), "tokens": ("模型推理", "推理框架", "多模态", "语音交互", "视觉理解", "大模型应用", "AI应用"), "theme": "模型推理/多模态交互", "why": "对应智能体理解、规划和交互能力的底层软件模块", "validation": "推理成本、响应速度、多模态能力和场景适配是否继续改善"},
    {"label": "端侧智能体/智能硬件入口", "domains": ("software_ai_application",), "tokens": ("端侧AI", "端侧", "智能硬件", "AI眼镜", "AI手机", "AI玩具", "机器人入口", "陪伴机器人"), "theme": "端侧智能体/智能硬件入口", "why": "对应智能体从云端软件向终端设备和交互入口扩散", "validation": "端侧模型、硬件出货、应用留存和场景闭环是否出现验证"},
    {"label": "高纯石英砂/天然矿源", "domains": ("semiconductor_materials",), "tokens": ("高纯石英砂", "天然高纯石英砂", "石英砂", "矿源", "IOTA", "杂质控制"), "theme": "高纯石英砂/天然矿源", "why": "对应半导体石英材料上游纯度、矿源和供给约束", "validation": "矿源、纯度指标、客户认证和供给约束是否继续强化"},
    {"label": "合成石英砂/合成石英材料", "domains": ("semiconductor_materials",), "tokens": ("合成石英砂", "合成石英", "气相合成", "高纯合成", "石英材料"), "theme": "合成石英砂/合成石英材料", "why": "对应先进制程对高纯、稳定、可控石英材料的替代路线", "validation": "合成路线、纯度、成本、客户验证和产能是否继续强化"},
    {"label": "石英器件/精密加工", "domains": ("semiconductor_materials",), "tokens": ("石英器件", "石英制品", "石英坩埚", "精密加工", "扩散管", "石英舟", "刻蚀环"), "theme": "石英器件/精密加工", "why": "对应石英材料向晶圆制造耗材和精密部件加工延伸", "validation": "晶圆厂认证、部件品类、良率和国产替代进度是否继续强化"},
    {"label": "图形化整机/DUV/KrF/ArF", "domains": ("semiconductor_patterning_equipment",), "tokens": ("光刻机", "DUV", "KrF", "ArF", "UV光刻机", "整机制造", "曝光机"), "theme": "图形化整机/DUV/KrF/ArF", "why": "对应半导体图形化核心整机平台和成熟/先进制程设备国产替代", "validation": "整机交付、客户验证、制程节点和良率是否继续强化"},
    {"label": "光源系统/激光器/特气", "domains": ("semiconductor_patterning_equipment",), "tokens": ("光源系统", "光源", "激光光源", "Cymer", "准分子", "Kr/Ne", "光刻气", "特种气体", "LBO", "BBO", "非线性光学晶体"), "theme": "光源系统/激光器/特气", "why": "对应曝光能量来源及激光、晶体、特气等关键上游约束", "validation": "光源功率、稳定性、材料认证和供应链替代是否被验证"},
    {"label": "光学系统/物镜/镜片", "domains": ("semiconductor_patterning_equipment",), "tokens": ("光学系统", "物镜", "镜头", "镜片", "蔡司", "光学材料", "投影物镜", "透镜"), "theme": "光学系统/物镜/镜片", "why": "对应分辨率、成像质量和高端装备核心壁垒", "validation": "高精度光学加工、镀膜、检测和客户认证是否继续强化"},
    {"label": "双工件台/运动控制/精密机械", "domains": ("semiconductor_patterning_equipment",), "tokens": ("双工件台", "工件台", "运动控制", "精密机械", "导轨", "气浮", "真空系统", "对准系统", "控制系统"), "theme": "双工件台/运动控制/精密机械", "why": "对应套刻精度、吞吐量和稳定性的核心机械控制环节", "validation": "套刻精度、运动平台、控制系统和客户验证是否继续强化"},
    {"label": "涂胶显影/配套工艺设备", "domains": ("semiconductor_patterning_equipment",), "tokens": ("涂胶显影", "涂胶", "显影", "Track", "清洗", "烘烤", "配套工艺设备"), "theme": "涂胶显影/配套工艺设备", "why": "对应图形化前后道配套工艺，常与光刻设备形成验证闭环", "validation": "涂胶显影订单、晶圆厂导入和国产替代是否继续强化"},
    {"label": "掩模版/光刻胶/图形化材料", "domains": ("semiconductor_patterning_equipment",), "tokens": ("掩模版", "光罩", "Mask", "光刻胶", "光刻材料", "掩模", "版图"), "theme": "掩模版/光刻胶/图形化材料", "why": "对应图形化关键耗材和材料认证环节", "validation": "材料等级、客户认证、价格信号和供应稳定性是否继续强化"},
    {"label": "量测检测/对准校准", "domains": ("semiconductor_patterning_equipment",), "tokens": ("量测", "检测", "套刻", "overlay", "对准", "校准", "缺陷检测", "计量"), "theme": "量测检测/对准校准", "why": "对应图形化过程控制、良率提升和设备闭环验证", "validation": "套刻量测、缺陷检测、晶圆厂验证和国产替代是否继续强化"},
    {"label": "信号采集/脑电传感", "domains": ("bioelectronic_medical_device",), "tokens": ("脑电", "EEG", "脑电图", "信号采集", "脑信号", "采集设备", "传感器", "脑电采集"), "theme": "信号采集/脑电传感", "why": "对应生物电信号获取入口，是医疗/消费级脑电设备和神经科技的基础能力", "validation": "采集精度、抗干扰、低功耗、客户/临床验证是否持续强化"},
    {"label": "电极/柔性电极/生物材料", "domains": ("bioelectronic_medical_device",), "tokens": ("电极", "柔性电极", "植入式电极", "非植入式电极", "生物相容", "硬脑膜", "铂铱", "石墨烯", "碳纤维"), "theme": "电极/柔性电极/生物材料", "why": "对应信号质量、长期稳定性和植入安全性的关键材料环节", "validation": "生物相容性、寿命、通道密度、临床或客户认证是否出现"},
    {"label": "植入式/半侵入式/非侵入式系统", "domains": ("bioelectronic_medical_device",), "tokens": ("侵入式", "植入式", "半侵入式", "非侵入式", "BCI整机", "脑机接口系统", "系统集成", "头环", "头显"), "theme": "植入式/半侵入式/非侵入式系统", "why": "对应不同风险收益路线和系统集成产品形态", "validation": "人体试验、产品认证、系统可靠性和商业场景是否被验证"},
    {"label": "神经调控/DBS/康复设备", "domains": ("bioelectronic_medical_device",), "tokens": ("神经调控", "DBS", "深部脑刺激", "电刺激", "康复设备", "神经康复", "脑卒中", "帕金森", "癫痫"), "theme": "神经调控/DBS/康复设备", "why": "对应医疗端更明确的疾病治疗和康复支付场景", "validation": "临床数据、适应症、注册认证、医院导入和手术量是否强化"},
    {"label": "信号处理芯片/低功耗通信", "domains": ("bioelectronic_medical_device", "semiconductor"), "tokens": ("ASIC", "FPGA", "信号处理芯片", "信号采集芯片", "ADC", "低功耗", "无线传输", "通信芯片", "电源管理"), "theme": "信号处理芯片/低功耗通信", "why": "对应高通道、低噪声、低延迟和无线化的硬件底座", "validation": "芯片量产、功耗、通道数、通信稳定性和客户导入是否出现"},
    {"label": "算法解码/多模态交互", "domains": ("bioelectronic_medical_device",), "tokens": ("算法", "解码", "意图识别", "语言解码", "运动意图", "多模态", "EEG+AI", "脑电文字", "交互控制"), "theme": "算法解码/多模态交互", "why": "对应从信号到可用指令和人机交互体验的核心软件能力", "validation": "准确率、延迟、泛化能力和真实场景验证是否改善"},
    {"label": "临床应用/医疗器械认证", "domains": ("bioelectronic_medical_device",), "tokens": ("临床", "医疗器械", "三类医疗器械", "注册", "认证", "人体植入", "手术", "医院", "医保"), "theme": "临床应用/医疗器械认证", "why": "对应医疗端商业化的准入、支付和场景闭环", "validation": "注册审批、临床试验、医院落地、医保支付和收入确认是否出现"},
    {"label": "主设备/系统集成", "domains": ("power_equipment",), "tokens": ("固态变压器", "SST", "HVDC", "PCS", "逆变器", "变流器", "电源", "系统集成", "电网设备"), "theme": "主设备/系统集成", "why": "对应电力电子设备整机和系统方案交付能力", "validation": "项目落地、客户认证、系统效率和可靠性是否继续强化"},
    {"label": "功率器件/功率模块", "domains": ("power_equipment",), "tokens": ("IGBT", "SiC", "MOSFET", "功率器件", "功率模块", "半导体器件", "碳化硅"), "theme": "功率器件/功率模块", "why": "对应高频高压电力电子转换的核心器件瓶颈", "validation": "器件认证、模块出货、良率和成本是否继续改善"},
    {"label": "控制系统/能量管理", "domains": ("power_equipment",), "tokens": ("控制系统", "控制器", "EMS", "BMS", "能量管理", "算法", "软件平台"), "theme": "控制系统/能量管理", "why": "对应设备运行稳定性、并网控制和系统效率优化", "validation": "控制策略、软件平台、客户项目和运行数据是否验证"},
    {"label": "磁件/绝缘/散热材料", "domains": ("power_equipment",), "tokens": ("磁件", "磁芯", "电感", "电容", "绝缘", "散热", "热管理", "材料"), "theme": "磁件/绝缘/散热材料", "why": "对应高频化、小型化和可靠性约束下的关键材料部件", "validation": "材料认证、散热方案、寿命和供货能力是否强化"},
    {"label": "电网/快充/数据中心应用", "domains": ("power_equipment",), "tokens": ("电网", "智能电网", "快充", "数据中心", "储能", "新能源并网", "柔性直流", "新能源接入"), "theme": "电网/快充/数据中心应用", "why": "对应电力设备需求来源和项目落地场景", "validation": "示范项目、招标、订单和应用侧经济性是否验证"},
    {"label": "硫化物固态电解质", "domains": ("advanced_battery_materials",), "tokens": ("硫化物电解质", "硫化物固态电解质", "硫化锂", "Li2S", "固态电解质"), "theme": "硫化物固态电解质", "why": "对应全固态电池高离子电导率路线和材料壁垒", "validation": "硫化锂供给、湿敏控制、客户验证和中试量产是否强化"},
    {"label": "氧化物/聚合物固态电解质", "domains": ("advanced_battery_materials",), "tokens": ("氧化物电解质", "聚合物电解质", "LLZO", "锆源", "固态电解质", "氧化物固态电解质", "聚合物固态电解质"), "theme": "氧化物/聚合物固态电解质", "why": "对应安全性、工艺兼容和不同固态路线的材料选择", "validation": "离子电导率、界面阻抗、工艺兼容和客户验证是否改善"},
    {"label": "锂金属/硅碳负极", "domains": ("advanced_battery_materials",), "tokens": ("锂金属负极", "金属负极", "硅碳负极", "硅碳", "负极材料", "负极", "预锂化"), "theme": "锂金属/硅碳负极", "why": "对应固态/高能量密度电池的负极升级方向", "validation": "循环寿命、膨胀控制、预锂化和客户导入是否验证"},
    {"label": "高镍正极/复合正极", "domains": ("advanced_battery_materials",), "tokens": ("高镍三元正极", "高镍正极", "正极材料", "正极", "高镍", "超高镍", "复合正极", "前驱体", "单晶高镍", "单晶正极"), "theme": "高镍正极/复合正极", "why": "对应高能量密度体系中的正极材料升级", "validation": "容量、循环、安全性和量产适配是否改善"},
    {"label": "干法电极/固态电池设备", "domains": ("advanced_battery_materials",), "tokens": ("干法电极", "固态电池设备", "辊压", "中试线", "量产线", "叠片", "涂布", "等静压"), "theme": "干法电极/固态电池设备", "why": "对应固态电池从材料到工艺放大的设备和产线瓶颈", "validation": "中试线、量产线、设备订单和良率是否出现"},
    {"label": "复合集流体/电池结构件", "domains": ("advanced_battery_materials",), "tokens": ("复合集流体", "集流体", "铜箔", "铝箔", "PET铜箔", "结构件"), "theme": "复合集流体/电池结构件", "why": "对应安全、轻量化和电池材料体系配套升级", "validation": "客户认证、量产良率、成本和安全收益是否验证"},
    {"label": "固态/半固态电芯系统", "domains": ("advanced_battery_materials",), "tokens": ("电芯", "电池系统", "半固态电池", "全固态电池", "固态电池", "软包", "动力电池", "电池包", "能量密度"), "theme": "固态/半固态电芯系统", "why": "对应固态电池从材料体系走向整包和整车验证的中游产品环节", "validation": "量产、客户车型、能量密度、循环寿命和安全测试是否验证"},
    {"label": "隔膜/界面材料", "domains": ("advanced_battery_materials",), "tokens": ("隔膜", "涂覆膜", "界面材料", "固固界面", "粘结剂", "陶瓷涂覆", "电解质膜"), "theme": "隔膜/界面材料", "why": "对应固态/半固态电池界面阻抗、安全性和工艺兼容配套", "validation": "界面阻抗、涂覆工艺、客户认证和量产良率是否验证"},
    {"label": "6G基站/核心网/主设备", "domains": ("next_generation_communications",), "tokens": ("6G基站", "6G 基站", "基站设备", "宏基站", "小基站", "核心网", "核心网设备", "6G设备", "网络设备", "6G网络架构", "主设备"), "theme": "6G基站/核心网/主设备", "why": "对应6G从标准和试验网走向网络建设的主设备与系统平台", "validation": "试验网、原型机、标准参与、主设备订单和运营商验证是否出现"},
    {"label": "太赫兹/毫米波通信", "domains": ("next_generation_communications",), "tokens": ("太赫兹", "太赫兹通信", "太赫兹原型系统", "毫米波", "毫米波通信", "W波段", "200GHz", "0.1-10THz"), "theme": "太赫兹/毫米波通信", "why": "对应6G高频大带宽路线，是器件、功耗、距离和测试验证的核心瓶颈", "validation": "太赫兹/毫米波样机、芯片、功放、测试系统和客户验证是否推进"},
    {"label": "射频前端/GaN/T-R组件", "domains": ("next_generation_communications",), "tokens": ("射频前端", "射频芯片", "射频器件", "射频组件", "T/R", "TR组件", "T-R组件", "GaN", "氮化镓", "砷化镓", "功率放大器", "PA"), "theme": "射频前端/GaN/T-R组件", "why": "对应高频通信、卫星通信和相控阵系统中的核心射频器件价值量", "validation": "射频芯片、T/R组件、GaN器件的订单、认证、量产和客户导入是否强化"},
    {"label": "相控阵/多频段天线", "domains": ("next_generation_communications",), "tokens": ("相控阵天线", "有源相控阵", "太赫兹天线", "毫米波天线", "多频段", "MIMO天线", "卫通天线", "基站天线", "终端天线", "天线阵列", "Massive MIMO"), "theme": "相控阵/多频段天线", "why": "对应波束赋形、天地一体覆盖和终端/基站高频连接能力", "validation": "天线阵列、相控阵、MIMO产品的客户认证、项目落地和量产节奏是否明确"},
    {"label": "卫星互联网/空天地一体化", "domains": ("next_generation_communications",), "tokens": ("卫星互联网", "卫星通信", "低轨卫星", "低轨星座", "星载", "卫星载荷", "地面站", "卫星通信终端", "空天地一体化", "空天地海一体化", "卫星组网"), "theme": "卫星互联网/空天地一体化", "why": "对应6G覆盖从地面网络向低轨卫星、高空平台和地面基站协同扩展", "validation": "星座建设、载荷订单、地面站、卫星终端和运营商试验是否形成事实验证"},
    {"label": "通感一体/RIS智能超表面", "domains": ("next_generation_communications",), "tokens": ("通感一体", "通感融合", "通信感知一体化", "感知与通信融合", "RIS", "智能超表面", "可重构智能表面", "感知终端", "感知即服务"), "theme": "通感一体/RIS智能超表面", "why": "对应6G从连接网络扩展到感知、定位、探测和可重构传播环境", "validation": "通感试验、RIS样机、场景验证、项目落地和标准进展是否强化"},
    {"label": "AI原生网络/通感算融合", "domains": ("next_generation_communications",), "tokens": ("AI原生网络", "AI + 通信", "AI赋能服务", "人工智能与通信融合", "通感算一体化", "通信感知计算", "NaaS", "网络即服务", "网络切片", "智能运维"), "theme": "AI原生网络/通感算融合", "why": "对应网络资源调度、运维、切片和服务模式的软件化智能化升级", "validation": "AI网络架构、切片服务、网络智能运维和运营商试点是否有产品化证据"},
    {"label": "通信测试/原型验证仪器", "domains": ("next_generation_communications",), "tokens": ("测试仪器", "通信测试", "网络测试", "原型机", "原型系统", "外场试验网", "6G试验网", "6G 试验网", "仿真验证", "频谱仪", "矢量网络分析"), "theme": "通信测试/原型验证仪器", "why": "对应6G早期研发、标准验证和高频器件调试中的先行设备需求", "validation": "试验网、测试设备采购、原型验证和客户导入是否出现"},
    {"label": "高频高速材料/连接器/PCB", "domains": ("next_generation_communications",), "tokens": ("高频高速覆铜板", "覆铜板", "PCB", "高频高速", "连接器", "高端连接器", "太赫兹通讯连接器", "高速连接器", "液冷板", "光子晶体", "新材料"), "theme": "高频高速材料/连接器/PCB", "why": "对应高频设备、基站、终端和卫星通信系统中的材料与互连配套", "validation": "高频材料、连接器、PCB的客户认证、量产良率和订单是否验证"},
    {"label": "光通信承载/CPO/硅光", "domains": ("next_generation_communications",), "tokens": ("光通信", "光互连", "高速光通信", "CPO", "共封装光学", "硅光", "光模块", "1.6T", "800G", "薄膜铌酸锂", "光器件"), "theme": "光通信承载/CPO/硅光", "why": "对应6G承载网、数据传输和算力互联的配套环节，权重低于基站/射频/卫星本体", "validation": "光通信承载是否从AI算力线外溢到6G网络建设和运营商需求"},
    {"label": "AI芯片/国产算力", "domains": ("compute", "semiconductor"), "tokens": ("AI芯片", "GPU", "DCU", "NPU", "算力芯片", "国产算力", "推理芯片", "训练芯片", "处理器", "CUDA"), "theme": "AI芯片/国产算力", "why": "处在算力供给的核心芯片环节", "validation": "芯片供给、生态适配、客户导入和算力需求是否持续强化"},
    {"label": "AI服务器/整机", "domains": ("compute",), "tokens": ("AI服务器", "整机", "GPU服务器", "算力服务器", "超算服务器"), "theme": "AI服务器/整机", "why": "对应算力基础设施的服务器和整机交付环节", "validation": "AI服务器需求、交付节奏、客户结构和供应链配套是否继续强化"},
    {"label": "IDC/智算中心运营", "domains": ("compute",), "tokens": ("IDC", "数据中心", "智算中心", "算力中心", "机柜", "机房", "上架率"), "theme": "IDC/智算中心运营", "why": "对应算力租赁和智算服务的基础设施承载环节", "validation": "机柜资源、上架率、客户结构和智算中心交付是否被持续强化"},
    {"label": "算力租赁/智算服务", "domains": ("compute",), "tokens": ("算力租赁", "智算服务", "算力服务", "边缘计算", "高弹性算力", "云服务", "大模型训练", "大模型推理"), "theme": "算力租赁/智算服务", "why": "对应算力从硬件建设向服务化出租和模型训练推理需求转化", "validation": "算力租赁订单、客户利用率、租赁价格和大模型需求是否继续强化"},
    {"label": "液冷/温控", "domains": ("compute", "energy_storage", "power"), "tokens": ("液冷", "冷板", "浸没式", "温控", "热管理", "散热", "冷却", "集装箱式液冷"), "theme": "液冷/温控", "why": "对应高功耗算力或储能系统的散热和可靠性约束", "validation": "液冷渗透率、客户导入、产品路线和订单线索是否继续强化"},
    {"label": "电源/HVDC/电力配套", "domains": ("compute", "energy_storage", "power"), "tokens": ("电源", "UPS", "HVDC", "SST", "变压器", "直流供电", "弹性直流", "一体柜"), "theme": "电源/HVDC/电力配套", "why": "对应数据中心、储能和高功耗设备的电力电子配套", "validation": "电源/HVDC/SST是否从配套环节形成独立需求弹性"},
    {"label": "储能系统/集成", "domains": ("energy_storage",), "tokens": ("储能系统", "系统集成", "储能集成", "集成商", "大型储能", "工商业储能", "户储", "储能设备", "储能柜"), "theme": "系统集成/大储/工商业储能", "why": "对应储能从电芯销售走向系统集成和解决方案交付", "validation": "系统集成、大储项目、工商业储能和交付能力是否继续被强化"},
    {"label": "PCS/逆变器", "domains": ("energy_storage", "power"), "tokens": ("PCS", "逆变器", "变流器", "储能变流", "组串式", "集中式逆变"), "theme": "PCS/逆变器/变流器", "why": "处在储能并网变流和能量转换的核心设备环节", "validation": "PCS/逆变器是否从配套设备升级为储能弹性核心环节"},
    {"label": "BMS/EMS/温控消防", "domains": ("energy_storage",), "tokens": ("BMS", "EMS", "消防", "能量管理", "电池管理"), "theme": "BMS/EMS/温控消防", "why": "对应储能安全、效率和运行管理能力", "validation": "BMS/EMS/温控消防是否被更多资料确认为安全和效率瓶颈"},
    {"label": "电芯/电池系统", "domains": ("energy_storage",), "tokens": ("电芯", "电池系统", "磷酸铁锂", "钠电", "动力电池", "储能电池", "电池舱", "电池包"), "theme": "电芯/电池系统", "why": "处在储能系统成本和性能权重最高的电池环节", "validation": "电芯路线、产能利用率和储能订单是否继续被研报/精选逻辑强化"},
    {"label": "电解液/锂盐/材料", "domains": ("energy_storage",), "tokens": ("电解液", "六氟磷酸锂", "6F", "VC", "正极", "负极", "隔膜", "锂盐", "碳酸锂", "石墨", "三元"), "theme": "电解液/锂盐/正负极材料", "why": "对应电芯材料供需和成本弹性的上游环节", "validation": "电解液/锂盐/材料供需是否形成独立价格或盈利弹性"},
    {"label": "稀土资源/冶炼分离", "domains": ("critical_materials",), "tokens": ("稀土资源", "稀土储量", "稀土矿", "冶炼分离", "氧化镨钕", "镨钕", "重稀土", "轻稀土", "镝", "铽", "稀土配额", "稀土精矿"), "theme": "资源/冶炼分离", "why": "对应关键材料上游资源约束、配额和冶炼分离能力", "validation": "资源储量、配额、冶炼分离产能和镨钕/镝铽供给约束是否继续强化"},
    {"label": "钕铁硼永磁材料", "domains": ("critical_materials",), "tokens": ("钕铁硼", "烧结钕铁硼", "粘结钕铁硼", "热压钕铁硼", "永磁材料", "高性能磁材", "磁材", "磁体"), "theme": "钕铁硼/永磁材料", "why": "对应稀土永磁材料的主流产品和高性能磁材供给环节", "validation": "钕铁硼产品结构、产能利用率、高性能磁材需求和客户导入是否继续强化"},
    {"label": "钐钴/钐铁氮新型磁材", "domains": ("critical_materials",), "tokens": ("钐钴", "钐铁氮", "SmCo", "SmFeN", "新型磁材", "粘结钐铁氮", "烧结磁体"), "theme": "钐钴/钐铁氮新型磁材", "why": "对应高温、高性能或重稀土减量方向的新型磁材路线", "validation": "钐钴/钐铁氮技术成熟度、量产能力和下游验证是否继续强化"},
    {"label": "晶界扩散/重稀土减量", "domains": ("critical_materials",), "tokens": ("晶界扩散", "重稀土减量", "低重稀土", "无重稀土", "渗镝", "渗铽", "矫顽力"), "theme": "晶界扩散/重稀土减量", "why": "对应高性能磁材降本、性能提升和重稀土依赖降低", "validation": "晶界扩散工艺、重稀土减量路线和高牌号产品占比是否继续强化"},
    {"label": "磁组件/电机应用", "domains": ("critical_materials",), "tokens": ("磁组件", "电机", "永磁电机", "永磁直驱", "新能源汽车", "风力发电", "机器人", "消费电子", "伺服电机"), "theme": "磁组件/电机应用", "why": "对应磁材向新能源车、风电、机器人等电机应用场景传导", "validation": "新能源车、风电、机器人等电机需求是否持续传导到磁材订单和产品结构"},
    {"label": "材料回收/供给约束", "domains": ("critical_materials",), "tokens": ("回收稀土", "稀土回收", "再生资源", "废料回收", "出口管制", "供给约束", "战略资源"), "theme": "材料回收/供给约束", "why": "对应关键材料供给安全、回收利用和政策约束带来的产业链弹性", "validation": "回收产能、出口管制、供给约束和价格弹性是否继续被多源资料强化"},
    {"label": "数控系统/工业控制", "domains": ("industrial_equipment",), "tokens": ("数控系统", "CNC系统", "CNC", "工业控制", "控制系统", "运动控制", "伺服系统", "PLC"), "theme": "数控系统/工业控制", "why": "对应工业母机的大脑和控制软件核心环节", "validation": "数控系统国产化、控制精度、客户导入和高端机床配套是否继续强化"},
    {"label": "数控机床/加工中心", "domains": ("industrial_equipment",), "tokens": ("数控机床", "加工中心", "机床", "车床", "铣床", "磨床", "高端机床", "中高端数控机床"), "theme": "数控机床/加工中心", "why": "对应工业母机整机制造和高端制造加工平台", "validation": "数控机床订单、产品结构、高端化和国产替代是否持续被资料强化"},
    {"label": "五轴/高端数控机床", "domains": ("industrial_equipment",), "tokens": ("五轴", "五轴联动", "高档数控", "高端数控", "复合加工", "核心部件+整机", "全自主化"), "theme": "五轴/高端数控机床", "why": "对应航空航天、复杂曲面加工等高壁垒高端机床方向", "validation": "五轴机床自主化率、核心部件自制、客户验证和高端订单是否继续强化"},
    {"label": "核心功能部件", "domains": ("industrial_equipment",), "tokens": ("主轴", "丝杠", "导轨", "转台", "刀库", "数控转台", "直线电机", "轴承", "功能部件"), "theme": "核心功能部件", "why": "对应机床精度、寿命和国产替代瓶颈部件", "validation": "主轴、丝杠、导轨、转台等核心部件自制率和客户验证是否继续强化"},
    {"label": "刀具/硬质合金耗材", "domains": ("industrial_equipment",), "tokens": ("刀具", "硬质合金", "刀片", "涂层", "槽型", "切削", "车削", "铣削", "钨价"), "theme": "刀具/硬质合金耗材", "why": "对应高端加工耗材、国产替代和上游钨等材料成本传导", "validation": "高端刀具替代、涂层槽型工艺、钨价传导和客户认证是否继续强化"},
    {"label": "成型装备/注塑压铸", "domains": ("industrial_equipment",), "tokens": ("注塑机", "压铸机", "冷热室压铸", "金属压铸", "注射成型", "MIM", "成型设备", "重载成型"), "theme": "成型装备/注塑压铸", "why": "对应广义工业母机中的材料成型装备和高端制造设备", "validation": "注塑、压铸、MIM等成型装备是否有高端化、国产替代和下游订单强化"},
    {"label": "工业软件/CAD/CAM/CAE", "domains": ("industrial_equipment",), "tokens": ("工业软件", "CAD", "CAM", "CAE", "数控编程", "仿真", "工艺软件", "制造软件"), "theme": "工业软件/CAD/CAM/CAE", "why": "对应高端装备从硬件向工艺软件和数字化制造延伸", "validation": "CAD/CAM/CAE、数控编程和工艺软件是否形成国产替代与客户验证"},
    {"label": "自动化产线/机器人集成", "domains": ("industrial_equipment",), "tokens": ("自动化产线", "自动化生产线", "机器人集成", "柔性产线", "智能制造", "产线集成"), "theme": "自动化产线/机器人集成", "why": "对应工业母机向智能制造单元和自动化产线延伸", "validation": "自动化产线、柔性制造和机器人集成订单是否继续强化"},
    {"label": "小分子创新药", "domains": ("pharma",), "tokens": ("小分子", "心血管", "S086", "口服", "化学药", "靶点", "管线"), "theme": "小分子/核心管线", "why": "对应自主创新管线和临床/商业化兑现的核心主体", "validation": "核心管线临床进展、适应症扩展和商业化放量是否继续被资料强化"},
    {"label": "ADC/双抗/单抗", "domains": ("pharma",), "tokens": ("ADC", "双抗", "单抗", "抗体", "PD-1", "HER2", "EGFR", "抗体偶联"), "theme": "抗体药物/ADC/双抗", "why": "对应抗体药物、ADC/双抗等创新药高景气技术路线", "validation": "ADC/双抗/单抗是否出现临床数据、适应症扩张或授权出海线索"},
    {"label": "GLP-1/多肽药物", "domains": ("pharma",), "tokens": ("GLP-1", "GLP1", "多肽", "司美格鲁肽", "利拉鲁肽", "减肥药"), "theme": "GLP-1/多肽", "why": "对应GLP-1/多肽等需求高增长和工艺壁垒方向", "validation": "GLP-1/多肽需求、产能和CDMO订单是否继续形成共识"},
    {"label": "细胞基因治疗", "domains": ("pharma",), "tokens": ("细胞治疗", "基因治疗", "CAR-T", "CAR T", "GCT", "病毒载体", "细胞基因"), "theme": "细胞基因治疗/GCT", "why": "对应细胞治疗、基因治疗和病毒载体等前沿疗法", "validation": "细胞基因治疗是否从技术平台走向临床/商业化或病毒载体需求"},
    {"label": "CRO/临床试验", "domains": ("pharma",), "tokens": ("CRO", "临床试验", "临床研究", "注册申报", "患者入组"), "theme": "CRO/临床试验", "why": "对应创新药研发外包、临床推进和研发效率提升", "validation": "CRO/临床试验是否受益于创新药融资和研发管线恢复"},
    {"label": "CDMO/原料药外包", "domains": ("pharma",), "tokens": ("CDMO", "CMO", "原料药", "中间体", "定制研发生产", "外包服务", "小分子CDMO"), "theme": "CDMO/原料药/工艺放大", "why": "对应创新药从研发到产业化的定制生产和工艺放大环节", "validation": "CDMO/原料药外包是否出现订单、产能利用率或出海需求改善线索"},
    {"label": "License-out/BD出海", "domains": ("pharma",), "tokens": ("license-out", "license out", "BD", "出海", "海外授权", "权益转让", "首付款", "里程碑"), "theme": "BD出海/授权交易", "why": "对应创新药出海、授权交易和估值重估逻辑", "validation": "License-out/BD出海是否成为估值重估和产业共识主线"},
    {"label": "药械一体化", "domains": ("pharma",), "tokens": ("药械一体", "药械组合", "无创治疗", "治疗产品"), "theme": "药械一体化", "why": "对应创新治疗方式和产品形态差异化", "validation": "药械一体化产品是否有临床、注册或商业化节点继续强化"},
    {"label": "商业化/院外渠道", "domains": ("pharma",), "tokens": ("商业化", "院外", "药店", "零售", "流通", "销售渠道"), "theme": "商业化/院外渠道", "why": "对应药品放量和渠道承接环节", "validation": "商业化和院外渠道是否真正承接核心产品放量"},
]


THEME_DOMAIN_RULES = {
    "next_generation_communications": ("6G", "6G产业", "第六代移动通信", "5G-A", "太赫兹", "毫米波", "射频前端", "相控阵", "卫星互联网", "空天地一体化", "通感一体", "RIS", "智能超表面", "AI原生网络", "6G基站", "核心网", "通信测试"),
    "compute": ("算力", "算力租赁", "智算", "数据中心", "AI服务器", "GPU", "IDC", "液冷", "大模型", "云服务"),
    "optical_interconnect": ("光模块", "CPO", "LPO", "硅光", "800G", "1.6T", "光芯片", "光器件"),
    "high_speed_interconnect": ("高速铜缆", "铜缆", "铜连接", "高速连接器", "高速互连", "DAC", "ACC", "AEC", "线束", "背板"),
    "advanced_battery_materials": ("固态电池", "半固态电池", "全固态电池", "固态电解质", "硫化物电解质", "氧化物电解质", "聚合物电解质", "锂金属负极", "硅碳负极", "干法电极", "复合集流体"),
    "energy_storage": ("储能", "电池", "锂电", "固态电池", "半固态电池", "全固态电池", "PCS", "BMS", "电芯", "电解液", "磷酸铁锂", "大储"),
    "pharma": ("创新药", "CRO", "CDMO", "ADC", "GLP-1", "CAR-T", "多肽", "单抗", "双抗"),
    "power": ("电力", "电源", "HVDC", "变压器", "SST"),
    "power_equipment": ("固态变压器", "高压快充", "柔性直流", "电网设备", "数据中心电源", "变流器", "逆变器", "PCS", "HVDC", "SST", "功率器件"),
    "semiconductor": ("半导体", "芯片", "GPU", "NPU", "DCU"),
    "semiconductor_materials": ("半导体石英砂", "高纯石英砂", "合成石英砂", "石英材料", "石英器件", "半导体材料"),
    "semiconductor_patterning_equipment": ("光刻机", "光刻", "曝光机", "图形化", "涂胶显影", "掩模版", "光刻胶", "光源系统", "光学系统", "工件台", "套刻", "量测"),
    "software_ai_application": ("AI Agent", "AI智能体", "智能体", "Agent", "AI应用", "RPA", "工作流", "模型推理", "多模态", "端侧AI"),
    "bioelectronic_medical_device": ("脑机接口", "BCI", "神经调控", "脑电", "EEG", "DBS", "植入式医疗", "非侵入式", "半侵入式", "康复设备", "医疗器械", "生物电子"),
    "critical_materials": ("稀土", "永磁", "钕铁硼", "钐钴", "钐铁氮", "磁材", "磁体", "小金属", "关键金属", "关键材料", "功能材料"),
    "industrial_equipment": ("工业母机", "数控机床", "数控系统", "机床", "加工中心", "五轴", "高端装备", "工业软件", "刀具", "硬质合金", "注塑机", "压铸机", "成型设备"),
}


def company_theme_key(company: dict) -> str:
    text = " ".join([str(company.get("deep_dive_term", "")), " ".join(company.get("concepts", []) or []), evidence_text(company)])
    norm = normalize(text)
    if "创新药" in norm or "cro" in norm or "cdmo" in norm or "license" in norm or "glp" in norm or "car-t" in norm:
        return "innovative_drug"
    if "储能" in norm or "pcs" in norm or "bms" in norm or "电解液" in norm or "磷酸铁锂" in norm:
        return "energy_storage"
    if "光模块" in norm or "cpo" in norm or "lpo" in norm or "硅光" in norm or "800g" in norm or "1.6t" in norm:
        return "light_module"
    return "generic"


def infer_theme_domains(text: str) -> set[str]:
    domains = set()
    for domain, tokens in THEME_DOMAIN_RULES.items():
        if any(token_hit(text, token) for token in tokens):
            domains.add(domain)
    return domains


def company_theme_domains(company: dict) -> set[str]:
    frame = company.get("direction_frame", {}) or {}
    allowed = set(frame.get("allowed_domains", []) or [])
    if allowed:
        return allowed
    topic_text = " ".join([str(company.get("deep_dive_term", "")), " ".join(company.get("concepts", []) or [])])
    domains = infer_theme_domains(topic_text)
    if domains:
        return domains
    return infer_theme_domains(evidence_text(company))


def capability_rule_by_label(label: str) -> dict:
    for rule in CAPABILITY_RULES:
        if rule.get("label") == label:
            return rule
    return {}


def selected_subdirection_rules(company: dict) -> list[tuple[str, tuple[str, ...]]]:
    domains = company_theme_domains(company)
    if not domains:
        return []
    return [(rule["label"], tuple(rule.get("tokens", ()))) for rule in CAPABILITY_RULES if domains & set(rule.get("domains", ()))]


def company_evidence_snippets(company: dict) -> list[str]:
    snippets = []
    for value in company.get("evidence", []) or []:
        snippets.append(str(value))
    for values in (company.get("evidence_buckets", {}) or {}).values():
        snippets.extend(str(x) for x in values or [])
    snippets.extend(str(x) for x in company.get("roles", []) or [])
    return [x for x in snippets if x.strip()]


def direction_frame_tokens(company: dict) -> list[str]:
    frame = company.get("direction_frame", {}) or {}
    tokens = []
    for row in frame.get("directions", []) or []:
        tokens.extend(str(x) for x in row.get("tokens", []) or [])
    tokens.extend(str(x) for x in company.get("concepts", []) or [])
    tokens.append(str(company.get("deep_dive_term", "")))
    return [x for x in unique(tokens) if x and len(x) >= 2]


def topic_relevant_evidence_text(company: dict) -> str:
    snippets = company_evidence_snippets(company)
    tokens = direction_frame_tokens(company)
    if not tokens:
        return evidence_text(company)
    selected = [text for text in snippets if any(token_hit(text, token) for token in tokens)]
    return " ".join(selected) if selected else " ".join(snippets[:3])


def runtime_direction_matches(company: dict, text: str) -> list[str]:
    frame = company.get("direction_frame", {}) or {}
    hits = []
    for row in frame.get("directions", []) or []:
        label = str(row.get("label", ""))
        tokens = row.get("tokens", []) or []
        if label and any(token_hit(text, token) for token in tokens):
            hits.append(label)
    return hits


def token_hit(text: str, token: str) -> bool:
    token_text = str(token or "").lower()
    target_text = str(text or "").lower()
    if not token_text:
        return False
    if re.fullmatch(r"[a-z0-9.+/-]+", token_text):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(token_text)}(?![a-z0-9])", target_text))
    return token_text in target_text or compact_direction_label(token_text) in compact_direction_label(target_text)


def semantic_company_subdirection_fallback(company: dict, text: str, layers: set[str], domains: set[str]) -> list[str]:
    full_text = " ".join([text, evidence_text(company), " ".join(company.get("concepts", []) or []), " ".join(company.get("roles", []) or [])])
    if "semiconductor_patterning_equipment" in domains:
        if any(token_hit(full_text, x) for x in ("LBO", "BBO", "非线性光学晶体", "光刻气", "特种气体", "准分子")):
            return ["光源系统/激光器/特气"]
        if any(token_hit(full_text, x) for x in ("光学", "物镜", "镜头", "镜片", "透镜", "镀膜")):
            return ["光学系统/物镜/镜片"]
        if any(token_hit(full_text, x) for x in ("工件台", "导轨", "气浮", "运动控制", "精密机械", "控制系统")):
            return ["双工件台/运动控制/精密机械"]
        if any(token_hit(full_text, x) for x in ("涂胶", "显影", "Track", "清洗", "烘烤")):
            return ["涂胶显影/配套工艺设备"]
        if any(token_hit(full_text, x) for x in ("掩模", "光罩", "Mask", "光刻胶", "光刻材料")):
            return ["掩模版/光刻胶/图形化材料"]
        if any(token_hit(full_text, x) for x in ("量测", "检测", "对准", "套刻", "校准")):
            return ["量测检测/对准校准"]
        if "upstream_equipment" in layers or "midstream_manufacturing" in layers:
            return ["图形化整机/DUV/KrF/ArF"]
    if "power_equipment" in domains:
        if any(token_hit(full_text, x) for x in ("IGBT", "SiC", "MOSFET", "功率器件", "功率模块")):
            return ["功率器件"]
        if any(token_hit(full_text, x) for x in ("磁件", "磁芯", "电感", "电容", "绝缘", "散热")):
            return ["磁件/材料"]
        if any(token_hit(full_text, x) for x in ("控制系统", "控制器", "EMS", "BMS", "能量管理", "算法")):
            return ["控制/软件"]
        if any(token_hit(full_text, x) for x in ("变压器", "SST", "HVDC", "PCS", "逆变器", "变流器", "电源")):
            return ["主设备/系统"]
    if "next_generation_communications" in domains:
        if any(token_hit(full_text, x) for x in ("核心网", "基站", "主设备", "网络设备", "中兴", "运营商")):
            return ["6G基站/核心网/主设备"]
        if any(token_hit(full_text, x) for x in ("太赫兹", "毫米波", "W波段", "200GHz")):
            return ["太赫兹/毫米波通信"]
        if any(token_hit(full_text, x) for x in ("射频", "T/R", "TR组件", "GaN", "氮化镓", "砷化镓", "功率放大")):
            return ["射频前端/GaN/T-R组件"]
        if any(token_hit(full_text, x) for x in ("相控阵", "MIMO", "天线", "波束")):
            return ["相控阵/多频段天线"]
        if any(token_hit(full_text, x) for x in ("卫星", "低轨", "星载", "地面站", "空天地")):
            return ["卫星互联网/空天地一体化"]
        if any(token_hit(full_text, x) for x in ("通感", "RIS", "智能超表面", "感知")):
            return ["通感一体/RIS智能超表面"]
        if any(token_hit(full_text, x) for x in ("AI原生", "网络切片", "NaaS", "智能运维")):
            return ["AI原生网络/通感算融合"]
        if any(token_hit(full_text, x) for x in ("测试", "原型", "试验网", "频谱仪")):
            return ["通信测试/原型验证仪器"]
        if any(token_hit(full_text, x) for x in ("连接器", "PCB", "覆铜板", "高频高速", "光通信", "光模块", "硅光")):
            return ["高频高速材料/连接器/PCB"]
    if "industrial_equipment" in domains:
        if any(token_hit(full_text, x) for x in ("主轴", "丝杠", "导轨", "转台", "刀库", "轴承")):
            return ["核心功能部件"]
        if any(token_hit(full_text, x) for x in ("刀具", "硬质合金", "刀片", "切削")):
            return ["刀具/硬质合金耗材"]
        if any(token_hit(full_text, x) for x in ("工业软件", "CAD", "CAM", "CAE", "自动化", "机器人集成")):
            return ["工业软件/CAD/CAM/CAE"]
    if "bioelectronic_medical_device" in domains:
        if any(token_hit(full_text, x) for x in ("脑电", "EEG", "信号采集", "传感器", "采集设备")):
            return ["信号采集/脑电传感"]
        if any(token_hit(full_text, x) for x in ("电极", "柔性电极", "生物相容", "硬脑膜", "生物材料")):
            return ["电极/柔性电极/生物材料"]
        if any(token_hit(full_text, x) for x in ("侵入式", "植入式", "半侵入式", "非侵入式", "脑机接口系统", "系统集成")):
            return ["植入式/半侵入式/非侵入式系统"]
        if any(token_hit(full_text, x) for x in ("神经调控", "DBS", "康复", "电刺激", "帕金森", "癫痫")):
            return ["神经调控/DBS/康复设备"]
        if any(token_hit(full_text, x) for x in ("ASIC", "FPGA", "芯片", "低功耗", "无线传输", "通信")):
            return ["信号处理芯片/低功耗通信"]
        if any(token_hit(full_text, x) for x in ("算法", "解码", "意图识别", "多模态", "EEG+AI", "脑电文字")):
            return ["算法解码/多模态交互"]
        if any(token_hit(full_text, x) for x in ("临床", "医疗器械", "认证", "医院", "手术", "医保")):
            return ["临床应用/医疗器械认证"]
    return []


def company_subdirections(company: dict) -> list[str]:
    text = topic_relevant_evidence_text(company)
    hits = runtime_direction_matches(company, text)
    for label, tokens in selected_subdirection_rules(company):
        if any(token_hit(text, token) for token in tokens):
            hits.append(label)
    if hits:
        return unique(hits)[:3]
    frame = company.get("direction_frame", {}) or {}
    layers = set(normalized_chain_layers(company))
    domains = company_theme_domains(company)
    semantic_hits = semantic_company_subdirection_fallback(company, text, layers, domains)
    if semantic_hits:
        return semantic_hits[:3]
    if frame.get("directions"):
        if "downstream_application" in layers or "downstream_channel" in layers:
            return ["待判定：下游应用/渠道"]
        if "upstream_equipment" in layers:
            return ["待判定：上游设备"]
        if "upstream_materials" in layers:
            return ["待判定：上游材料"]
        return ["待判定细分方向"]
    layers = set(normalized_chain_layers(company))
    domains = company_theme_domains(company)
    if "pharma" in domains:
        subtype = company.get("company_subtype") or company_subtype(company)
        text = evidence_text(company)
        if subtype == "service_provider" or any(x in text for x in ("CRO", "CDMO", "临床试验", "外包")):
            return ["CRO/临床试验"]
        if "upstream_materials" in layers:
            return ["CDMO/原料药外包"]
        if "downstream_application" in layers or "downstream_channel" in layers:
            return ["商业化/院外渠道"]
        return ["创新药管线/待细分"]
    if "energy_storage" in domains:
        if "upstream_components" in layers:
            return ["电芯/电池系统"]
        if "upstream_equipment" in layers:
            return ["PCS/逆变器"]
        if "upstream_materials" in layers:
            return ["电解液/锂盐/材料"]
        if "downstream_application" in layers or "downstream_channel" in layers:
            return ["海外/大储需求"]
    if "compute" in domains:
        if "upstream_components" in layers:
            return ["AI芯片/国产算力"]
        if "midstream_manufacturing" in layers:
            return ["IDC/智算中心运营"]
        if "downstream_application" in layers or "downstream_channel" in layers:
            return ["算力租赁/智算服务"]
        if "upstream_equipment" in layers or "upstream_materials" in layers:
            return ["算力基础设施/待细分"]
    if "optical_interconnect" in domains and "upstream_components" in layers:
        return ["光芯片/核心器件"]
    if "optical_interconnect" in domains and "upstream_equipment" in layers:
        return ["光器件/无源器件"]
    if "optical_interconnect" in domains and "upstream_materials" in layers:
        return ["PCB/HDI/mSAP配套"]
    if "downstream_application" in layers or "downstream_channel" in layers:
        return ["待判定：下游应用/渠道"]
    if "upstream_equipment" in layers:
        return ["待判定：上游设备"]
    if "upstream_materials" in layers:
        return ["待判定：上游材料"]
    return ["待判定细分方向"]


def company_logic_strength(company: dict) -> str:
    if is_explicit_weak_company(company):
        return "弱逻辑"
    consensus = source_consensus_count(company)
    tier = company_deep_dive_tier(company)
    if tier == "relative_core" and consensus >= 2:
        return "强逻辑"
    if tier in {"relative_core", "related"}:
        return "中强逻辑"
    if tier == "watch":
        return "观察逻辑"
    return "弱逻辑"


def compact_text(text: str, limit: int = 120) -> str:
    value = re.sub(r"\s+", "", str(text or "").strip())
    value = value.replace("", "")
    return value[:limit] + ("…" if len(value) > limit else "")


def strongest_evidence_snippet(company: dict) -> str:
    buckets = company.get("evidence_buckets", {}) or {}
    for bucket in ("curated_research", "delta", "baseline", "graph_only", "missing"):
        rows = buckets.get(bucket) or []
        if rows:
            return compact_text(rows[0])
    if company.get("evidence"):
        return compact_text(company["evidence"][0])
    return "当前缺少可提纯证据片段。"


def capability_why(subdirs: list[str]) -> str:
    parts = []
    for label in subdirs:
        rule = capability_rule_by_label(label)
        if rule.get("why"):
            parts.append(rule["why"])
    return "；".join(parts[:2]) if parts else "需要更多文本确认其在题材链条中的关键性"


def capability_validation(label: str) -> tuple[str, str]:
    rule = capability_rule_by_label(label)
    return str(rule.get("theme") or label), str(rule.get("validation") or "后续研报/精选逻辑是否继续强化该方向。")


def company_logic_summary(company: dict) -> str:
    name = company.get("name", "")
    role = "；".join(company.get("roles", [])[:2]) or "待补角色"
    subdirs = "、".join(company_subdirections(company))
    strength = company_logic_strength(company)
    basis_items = [x for x in source_basis(company) if x != "baseline基础画像"]
    basis = "、".join(basis_items) if basis_items else "当前主信源不足"
    baseline_note = "；baseline仅作基础画像校验" if "baseline基础画像" in source_basis(company) else ""
    snippet = strongest_evidence_snippet(company)
    subdir_items = company_subdirections(company)
    why = capability_why(subdir_items)
    if is_explicit_weak_company(company):
        return f"{name}当前只作为弱相关线索：文本或图谱显示其与{subdirs}有边缘关联，但证据形态偏弱，暂不进入核心逻辑池。依据片段：{snippet}"
    if is_downstream_or_ecosystem_company(company) and company.get("strength") != "core":
        return f"{name}更偏下游需求/生态侧，能够解释{subdirs}的需求来源，但不是当前题材弹性最集中的核心供给环节。依据片段：{snippet}"
    if not basis_items:
        return f"{name}的角色是{role}，目前映射到{subdirs}。这条线索的看点在于：{why}。但当前主要题材证据仍需 PDF研报/精选逻辑/full上下文继续补强{baseline_note}。依据片段：{snippet}"
    return f"{name}的角色是{role}，主要落在{subdirs}。这条逻辑的关键在于：{why}。当前由{basis}提供题材支撑{baseline_note}。依据片段：{snippet}"


def company_validation_focus(company: dict) -> str:
    subdirs = company_subdirections(company)
    checks = [capability_validation(label)[1] for label in subdirs if capability_rule_by_label(label)]
    if not checks:
        checks.append("后续研报/精选逻辑是否继续强化该公司与题材主线的直接关系")
    checks.append("公告订单业绩仅作后续验证空位")
    return "；".join(checks[:3])


def subdirection_validation_section(companies: list[dict]) -> str:
    rows = []
    seen = set()
    for company in companies:
        for subdir in company_subdirections(company):
            if subdir in seen or subdir.startswith("待判定") or "待细分" in subdir:
                continue
            seen.add(subdir)
            theme, validation = capability_validation(subdir)
            examples = [
                c.get("name", "")
                for c in sorted(companies, key=lambda x: ({"relative_core": 0, "related": 1, "watch": 2, "weak": 3}.get(company_deep_dive_tier(x), 3), company_sort_key(x)))
                if subdir in company_subdirections(c) and company_deep_dive_tier(c) != "weak"
            ][:5]
            if not examples:
                continue
            rows.append((subdir, theme, "、".join(examples), validation))
    if not rows:
        return "- 暂无可聚合的细分方向验证清单。"
    lines = ["| 细分方向 | 跟踪主题 | 当前线索公司 | 后续验证重点 |", "|---|---|---|---|"]
    for subdir, theme, examples, validation in rows:
        lines.append(f"| {subdir} | {theme} | {examples or '待补'} | {validation} |")
    return "\n".join(lines)


def deep_company_cards_section(companies: list[dict], tier: str, limit: int = 10) -> str:
    labels = {
        "relative_core": "相对核心",
        "related": "重点相关",
        "watch": "观察/弹性",
        "weak": "弱相关",
    }
    rows = [c for c in companies if company_deep_dive_tier(c) == tier]
    rows = sorted(rows, key=company_sort_key)[:limit]
    if not rows:
        return "- 暂无。"
    parts = []
    for company in rows:
        roles = "；".join(company.get("roles", [])[:2]) or "待补角色"
        layers = "、".join(normalized_chain_layers(company)[:3]) or "unknown"
        sources = "、".join(source_basis(company))
        baseline = "支持/不冲突" if (company.get("evidence_buckets", {}) or {}).get("baseline") else "待补基础画像或仅作辅助"
        parts.append(
            "\n".join(
                [
                    f"### {company.get('name','')}（{labels.get(tier, tier)}）",
                    f"- 细分方向：{'、'.join(company_subdirections(company))}",
                    f"- 逻辑强度：{company_logic_strength(company)}",
                    f"- 产业链角色：{roles}",
                    f"- 所属环节：{layers}；公司类型：{SUBTYPE_LABELS.get(company.get('company_subtype'), '待判定')}",
                    f"- 题材逻辑：{company_logic_summary(company)}",
                    f"- 来源依据：{sources}",
                    f"- baseline校验：{baseline}",
                    f"- 重点验证：{company_validation_focus(company)}",
                    f"- 护栏/验证：{company_guardrail_note(company)}",
                ]
            )
        )
    return "\n\n".join(parts)


def resonance_tiers_section(context: dict, companies: list[dict]) -> str:
    directions = context.get("direction_scan", []) if isinstance(context, dict) else []
    lines = ["| Tier | 方向/公司 | 共振依据 | 判断 |", "|---|---|---|---|"]
    tier1 = [c for c in companies if company_deep_dive_tier(c) == "relative_core"][:8]
    tier2 = [c for c in companies if company_deep_dive_tier(c) == "related"][:8]
    tier3 = [c for c in companies if company_deep_dive_tier(c) in {"watch", "weak"}][:8]
    if directions:
        for row in directions[:6]:
            if not isinstance(row, dict):
                continue
            lines.append(f"| 细分方向 | {row.get('direction','')} | {row.get('core_catalyst','待补')} | {row.get('classification','精读线索')} |")
    for label, rows, judgement in [
        ("Tier 1 三重共振", tier1, "相对核心：主信源支持较强，适合优先讲逻辑"),
        ("Tier 2 双重验证", tier2, "重点相关：逻辑清楚但共识或上下文仍需补强"),
        ("Tier 3 观察/弱相关", tier3, "暂不作为核心：单源、弱相关或待验证"),
    ]:
        for company in rows:
            lines.append(f"| {label} | {company.get('name','')} | {'、'.join(source_basis(company))} | {judgement} |")
    return "\n".join(lines) if len(lines) > 2 else "- 暂无可分层信号。"


def deep_dive_conclusion(term: str, context: dict, companies: list[dict]) -> str:
    direction_rows = context.get("direction_scan", []) if isinstance(context, dict) else []
    directions = [row for row in direction_rows if isinstance(row, dict) and row.get("direction")]
    demand = as_list(context.get("demand_drivers"))[:4] if isinstance(context, dict) else []
    core = [c for c in companies if company_deep_dive_tier(c) == "relative_core"][:6]
    related = [c for c in companies if company_deep_dive_tier(c) == "related"][:6]
    watch = [c for c in companies if company_deep_dive_tier(c) == "watch"][:4]

    lines = [
        f"### 1）题材为什么发酵",
        conclusion_theme_driver(term, directions, demand),
        "",
        "### 2）当前主线落在哪些环节",
        conclusion_direction_bullets(directions),
        "",
        "### 3）公司分层为什么这样分",
        conclusion_company_tiers(core, related, watch),
        "",
        "### 4）下一步最该盯什么验证信号",
        conclusion_validation_bullets(context, directions),
        "",
        "### 5）边界",
        "- 本报告用于题材结构和证据分层，不做个股排名；公告、订单、业绩是后续验证空位，不作为当前核心判断的唯一高权重依据。",
    ]
    return "\n".join(lines)


def conclusion_theme_driver(term: str, directions: list[dict], demand: list[str]) -> str:
    if directions:
        first = directions[0]
        why = str(first.get("prosperity") or "").strip()
        if why:
            demand_text = f"需求侧线索集中在 {'、'.join(demand[:3])}。" if demand else ""
            return f"{term}的发酵不是单一概念扩散，而是先落到“{first.get('direction')}”等可验证环节；{why}{demand_text}"
    if demand:
        return f"{term}的发酵主要来自 {'、'.join(demand[:3])} 等需求场景，但仍需继续拆到可验证的产品、工艺和公司证据。"
    return f"{term} 当前主要依赖本地研报/full 精读上下文，需要继续补充需求侧和公司级验证信号。"


def conclusion_direction_bullets(directions: list[dict]) -> str:
    if not directions:
        return "- 暂无稳定主方向，优先补足产业链拆解和公司证据。"
    lines = []
    for row in directions[:5]:
        direction = str(row.get("direction") or "").strip()
        catalyst = str(row.get("core_catalyst") or "").strip()
        classification = str(row.get("classification") or "").strip()
        level = str(row.get("recognition_level") or "").strip()
        detail = f"；验证重点：{catalyst}" if catalyst else ""
        lines.append(f"- **{direction}**：{classification or '核心方向'}，{level or '待验证'}{detail}")
    return "\n".join(lines)


def company_tier_line(title: str, rows: list[dict], reason: str) -> str:
    if not rows:
        return f"- **{title}**：暂无。"
    items = []
    for company in rows[:5]:
        name = company.get("name", "")
        subdirs = [x for x in company_subdirections(company) if not str(x).startswith("待判定")][:2]
        basis = "、".join(source_basis(company)[:2])
        suffix = f"（{'/'.join(subdirs)}）" if subdirs else ""
        basis_text = f"，依据：{basis}" if basis else ""
        items.append(f"{name}{suffix}{basis_text}")
    return f"- **{title}**：{'；'.join(items)}。{reason}"


def conclusion_company_tiers(core: list[dict], related: list[dict], watch: list[dict]) -> str:
    lines = [
        company_tier_line("相对核心", core, "这些公司通常同时具备较强题材证据、较清晰产业链角色和可落到细分方向的产品/工艺线索。"),
        company_tier_line("重点相关", related, "这些公司逻辑较清楚，但仍需更多共识文本、客户/订单或收入占比验证。"),
    ]
    if watch:
        lines.append(company_tier_line("观察/弹性", watch, "这些公司保留线索，但暂不作为主线核心，避免把泛概念暴露误判为强逻辑。"))
    return "\n".join(lines)


def conclusion_validation_bullets(context: dict, directions: list[dict]) -> str:
    rows = context.get("validation_checklist", []) if isinstance(context, dict) else []
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = str(row.get("item") or "").strip()
        if item and not item.startswith("相对核心公司") and not item.startswith("baseline"):
            items.append(item)
    if not items:
        items = [str(row.get("core_catalyst") or "").strip() for row in directions if isinstance(row, dict) and row.get("core_catalyst")]
    if not items:
        return "- 后续重点补 PDF/精选逻辑/公告验证，确认方向是否能映射到公司级产品、工艺、客户或订单。"
    return "\n".join(f"- {item}" for item in unique(items)[:5])


def deep_dive_governance_section(companies: list[dict]) -> str:
    if not companies:
        return "- 暂无公司暴露，底层治理摘要为空。"
    issue_keys = (
        "weak_granularity",
        "review_required",
        "soft_fact_hardness",
        "chain_layer_conflict",
        "graph_only_only",
        "missing_evidence",
    )
    counts = {key: 0 for key in issue_keys}
    tier_counts = {"relative_core": 0, "related": 0, "watch": 0, "weak": 0}
    for company in companies:
        tier_counts[company_deep_dive_tier(company)] = tier_counts.get(company_deep_dive_tier(company), 0) + 1
        flags = set(company_qc_flags(company))
        for key in issue_keys:
            if key in flags:
                counts[key] += 1
    lines = [
        "| 项目 | 数量 | 用途 |",
        "|---|---:|---|",
        f"| 相对核心 | {tier_counts.get('relative_core', 0)} | 主报告优先讲逻辑 |",
        f"| 重点相关 | {tier_counts.get('related', 0)} | 逻辑清楚但仍需共识/上下文补强 |",
        f"| 观察/弹性 | {tier_counts.get('watch', 0)} | 有线索但暂不作为核心 |",
        f"| 弱相关 | {tier_counts.get('weak', 0)} | 只作隔离展示 |",
    ]
    for key in issue_keys:
        lines.append(f"| QC:{key} | {counts[key]} | 旧题材雷达底层护栏，不直接等于否定逻辑 |")
    return "\n".join(lines)


EQUIPMENT_COVERAGE_RULES = {
    "next_generation_communications": {
        "label": "下一代通信覆盖度",
        "min_hits": 5,
        "clusters": {
            "主设备/核心网": ("基站", "核心网", "主设备", "网络设备"),
            "高频通信": ("太赫兹", "毫米波", "高频"),
            "射频/天线": ("射频", "T/R", "GaN", "相控阵", "天线"),
            "卫星/空天地": ("卫星", "空天地", "星载", "地面站"),
            "通感/RIS": ("通感", "RIS", "智能超表面", "感知"),
            "AI网络/软件": ("AI原生", "通感算", "网络切片", "智能运维"),
            "测试验证": ("测试", "原型", "试验网", "仪器"),
            "材料/互连": ("高频高速", "连接器", "PCB", "覆铜板", "光通信"),
        },
    },
    "semiconductor_patterning_equipment": {
        "label": "复杂设备覆盖度",
        "min_hits": 4,
        "clusters": {
            "整机/系统": ("整机", "DUV", "KrF", "ArF", "曝光机", "系统"),
            "核心子系统": ("光源", "光学", "物镜", "工件台", "运动控制", "精密机械"),
            "工艺配套": ("涂胶", "显影", "配套工艺", "清洗", "烘烤"),
            "材料/耗材": ("掩模", "光刻胶", "光罩", "图形化材料", "特气"),
            "量测/校准": ("量测", "检测", "对准", "校准", "套刻"),
        },
    },
    "industrial_equipment": {
        "label": "复杂设备覆盖度",
        "min_hits": 4,
        "clusters": {
            "整机/加工平台": ("机床", "加工中心", "注塑", "压铸", "成型装备", "整机"),
            "控制系统": ("数控", "CNC", "控制系统", "伺服", "PLC", "运动控制"),
            "核心功能部件": ("主轴", "丝杠", "导轨", "转台", "刀库", "轴承", "功能部件"),
            "工具/耗材": ("刀具", "硬质合金", "刀片", "涂层", "切削"),
            "软件/自动化": ("工业软件", "CAD", "CAM", "CAE", "自动化", "机器人集成", "柔性产线"),
        },
    },
    "power_equipment": {
        "label": "复杂设备覆盖度",
        "min_hits": 4,
        "clusters": {
            "主设备/系统": ("变压器", "SST", "HVDC", "PCS", "逆变器", "变流器", "电源", "系统"),
            "功率器件": ("IGBT", "SiC", "MOSFET", "功率器件", "模块", "半导体"),
            "控制/软件": ("控制系统", "控制器", "EMS", "BMS", "能量管理", "算法"),
            "磁件/材料": ("磁件", "磁芯", "电感", "电容", "绝缘", "散热", "材料"),
            "应用场景": ("电网", "快充", "数据中心", "储能", "新能源", "柔性直流"),
        },
    },
    "bioelectronic_medical_device": {
        "label": "医疗器械覆盖度",
        "min_hits": 4,
        "clusters": {
            "信号采集": ("信号采集", "脑电", "传感"),
            "材料/电极": ("电极", "柔性电极", "生物材料", "生物相容"),
            "系统路线": ("植入式", "半侵入式", "非侵入式", "系统"),
            "芯片/通信": ("芯片", "低功耗", "通信", "ADC", "ASIC"),
            "算法/交互": ("算法", "解码", "多模态", "意图识别", "交互"),
            "临床/认证": ("临床", "医疗器械", "认证", "医院", "医保"),
        },
    },
}


def equipment_coverage_gate(context: dict) -> tuple[str, bool, str] | None:
    frame = context.get("direction_frame", {}) if isinstance(context, dict) else {}
    domains = set(frame.get("allowed_domains", []) or [])
    labels = [
        str(row.get("label", ""))
        for row in frame.get("directions", []) or []
        if isinstance(row, dict)
    ]
    text = " ".join(labels)
    for domain, rule in EQUIPMENT_COVERAGE_RULES.items():
        if domain not in domains:
            continue
        hits = [
            name
            for name, tokens in rule["clusters"].items()
            if any(token in text for token in tokens)
        ]
        ok = len(hits) >= int(rule.get("min_hits", 4))
        return (rule["label"], ok, f"{len(hits)}/{len(rule['clusters'])}：{'、'.join(hits) or '待补'}")
    return None


def deep_dive_quality_gate_section(context: dict, companies: list[dict]) -> str:
    if not companies:
        return "- 暂无公司数据，无法评估深拆质量。"
    validation_text = subdirection_validation_section(companies)
    total = len(companies)
    core_related = [c for c in companies if company_deep_dive_tier(c) in {"relative_core", "related"}]
    active_companies = [c for c in companies if company_deep_dive_tier(c) != "weak"]
    mapped_core_related = [c for c in core_related if not any(x.startswith("待判定") or "待细分" in x for x in company_subdirections(c))]
    pending = [c for c in active_companies if any(x.startswith("待判定") or "待细分" in x for x in company_subdirections(c))]
    direction_count = len([row for row in context.get("direction_scan", []) if isinstance(row, dict)]) if isinstance(context, dict) else 0
    context_validation_ok = bool(context.get("validation_checklist")) if isinstance(context, dict) else False
    validation_ok = context_validation_ok or not validation_text.startswith("- 暂无")
    mapped_ratio = round(len(mapped_core_related) / max(1, len(core_related)) * 100)
    pending_ratio = round(len(pending) / max(1, len(active_companies)) * 100)
    mapping_ok = True if not core_related else mapped_ratio >= 70
    mapping_value = "无核心/相关样本" if not core_related else f"{mapped_ratio}%"
    pass_items = [
        ("方向数量", direction_count >= 3, f"{direction_count} 个"),
        ("核心/相关公司映射率", mapping_ok, mapping_value),
        ("待判定占比", pending_ratio <= 35, f"{pending_ratio}%"),
        ("验证清单", validation_ok, "非空" if validation_ok else "为空"),
    ]
    equipment_gate = equipment_coverage_gate(context)
    if equipment_gate:
        pass_items.append(equipment_gate)
    passed = all(item[1] for item in pass_items)
    lines = [
        "| 门禁项 | 状态 | 当前值 |",
        "|---|---|---|",
    ]
    for name, ok, value in pass_items:
        lines.append(f"| {name} | {'通过' if ok else '需优化'} | {value} |")
    lines.append(f"| 总体判断 | {'通过' if passed else '未通过'} | {'可进入人工阅读' if passed else '需要补方向骨架/主题边界/证据匹配'} |")
    return "\n".join(lines)


def build_theme_state(term: str, vault: Path, definition: str = "", context: dict | None = None, theme_info_rows: list[dict] | None = None, theme_direction_pool: dict | None = None) -> dict:
    rel_dir = vault / "relations"
    graph = load_json(rel_dir / RELATION_FILES["concept_graph"], {"concepts": {}, "relations": []})
    exposures = load_json(rel_dir / RELATION_FILES["entity_exposures"], {"entities": {}})
    aliases = load_json(rel_dir / RELATION_FILES["aliases"], {"aliases": {}})
    evidence_index = load_json(rel_dir / RELATION_FILES["evidence_index"], {"items": []})
    theme_signals = load_json(rel_dir / RELATION_FILES["theme_signals"], {"version": 1, "themes": {}})
    pattern_library = load_json(rel_dir / RELATION_FILES["pattern_library"], {"version": 1, "patterns": {}})
    report_contexts = load_json(rel_dir / RELATION_FILES["report_contexts"], {"version": 1, "reports": {}})
    concepts = graph.get("concepts", {})
    context = context or {}
    explicit_definition = bool(definition.strip())
    theme_info_context = build_theme_information_context(term, theme_info_rows or [])
    if not explicit_definition and theme_info_context.get("definition"):
        definition = theme_info_context.get("definition", "")
    if not definition.strip():
        definition = context_definition(context)
    external_search_text = " ".join(x for x in [definition, context_search_text(context)] if x.strip())
    primary, matches, notes = resolve_query(term, aliases, concepts)
    term_matched = bool(matches)
    if not matches and external_search_text.strip():
        _def_primary, def_matches, def_notes = resolve_query(external_search_text, aliases, concepts)
        if def_matches:
            matches = filter_concepts(def_matches, context)
            notes.extend([f"外部结构化信息辅助匹配：{x}" for x in def_matches[:5]])
            notes.extend(def_notes)
    local_report_contexts = match_report_contexts(term, primary, matches, report_contexts)
    if not context and local_report_contexts:
        context = runtime_context_from_report_contexts(term, local_report_contexts)
        if not definition.strip():
            definition = context_definition(context)
    context = merge_theme_information_context(context, theme_info_context)
    direction_pool_context = build_theme_direction_pool_context(theme_direction_pool or {})
    context = merge_theme_direction_pool_context(context, direction_pool_context)
    if not explicit_definition and theme_info_context.get("definition"):
        definition = theme_info_context.get("definition", "")
    match_scope = matches or ([primary] if primary in concepts else [])
    rels = related_concepts(primary, match_scope, graph)
    all_scope = unique(match_scope + rels[:12])
    company_scope = match_scope[:]
    if not term_matched and context:
        _focused_primary, focused_matches, _focused_notes = resolve_query(context_company_text(context), aliases, concepts)
        if focused_matches:
            company_scope = filter_concepts(focused_matches, context)
    companies = collect_companies(company_scope, graph, exposures)
    broadened_company_scope = False
    if not companies and all_scope:
        company_scope = all_scope
        companies = collect_companies(company_scope, graph, exposures)
        broadened_company_scope = True
    companies, dropped_generic_companies = filter_new_term_companies(companies, context, term_matched)
    enrich_companies_from_evidence_index(companies, evidence_index, company_scope or all_scope)
    if local_report_contexts:
        t = " ".join(str(ev.get("text", "")) for r in local_report_contexts for ev in (r.get("evidence", []) or []) if isinstance(ev, dict))
        structured_mentions = {}
        for row in local_report_contexts:
            for mention in row.get("company_mentions", []) or []:
                if not isinstance(mention, dict):
                    continue
                name = str(mention.get("company") or "").strip()
                if name:
                    structured_mentions.setdefault(name, []).append(mention)
        for company in companies:
            company["context_checked"] = True
            name = company.get("name")
            if name and structured_mentions.get(name):
                company["context_mentions"] = structured_mentions[name]
            elif name and name in t:
                company["context_mentions"] = [{"directness": "direct"}]
    companies = refresh_company_subtypes(companies)
    evidence = collect_evidence(company_scope or all_scope, companies, evidence_index)
    signal = load_signal(theme_signals, primary, matches)
    patterns = match_patterns(pattern_library, " ".join([term, external_search_text]), match_scope or [term])
    return {
        "graph": graph,
        "concepts": concepts,
        "primary": primary,
        "matches": matches,
        "notes": notes,
        "term_matched": term_matched,
        "context": context,
        "definition": definition,
        "local_report_contexts": local_report_contexts,
        "match_scope": match_scope,
        "rels": rels,
        "all_scope": all_scope,
        "company_scope": company_scope,
        "companies": companies,
        "evidence": evidence,
        "signal": signal,
        "patterns": patterns,
        "broadened_company_scope": broadened_company_scope,
        "dropped_generic_companies": dropped_generic_companies,
        "theme_info_context": theme_info_context,
        "theme_direction_pool": theme_direction_pool or {},
    }


def build_deep_dive_report(term: str, vault: Path, definition: str = "", context: dict | None = None, theme_info_rows: list[dict] | None = None, theme_direction_pool: dict | None = None) -> str:
    state = build_theme_state(term, vault, definition, context, theme_info_rows, theme_direction_pool)
    context = state["context"]
    companies = state["companies"]
    for company in companies:
        company["deep_dive_term"] = term
        company["direction_frame"] = context.get("direction_frame", {}) if isinstance(context, dict) else {}
    definition_text = state["definition"].strip() or context_definition(context) or f"{term}：待从 full 精读/PDF ingest 中补一句话定锚。"
    return f"""# {term} 题材深拆

生成日期：{date.today().isoformat()}

## 一、一句话定锚

{definition_text}

## 二、为什么现在发酵

{demand_drivers_section(context)}

### 需求-瓶颈-环节传导表

{demand_bottleneck_map_section(context)}

### 需求场景表

{demand_scenarios_section(context)}

## 三、产业链全景图

{industry_chain_map_section(context)}

### IMA/Obsidian 统一信息池：细颗粒地图与上下游关系

{theme_information_pool_section(context)}

### 标准细分方向池：方向级中间层

{theme_direction_pool_section(context)}

### 本地 full 精读 / report_contexts 上下文

{report_contexts_section(state["local_report_contexts"])}

## 四、细分方向扫描

{direction_scan_section(context)}

### 降权但保留的背景/生态线索

{secondary_runtime_context_section(context)}

## 五、共振分层：主信源 × 产业链 × 公司逻辑

{resonance_tiers_section(context, companies)}

## 六、full 精读提及/生态线索

{report_context_company_clues_section(state["local_report_contexts"])}

## 七、发酵进度与预期差

{progress_ranking_section(context)}

## 八、相对核心个股逻辑卡

{deep_company_cards_section(companies, "relative_core")}

## 九、重点相关个股逻辑卡

{deep_company_cards_section(companies, "related")}

## 十、观察/弹性与弱相关隔离

### 观察/弹性

{deep_company_cards_section(companies, "watch", limit=8)}

### 弱相关/暂不作为核心

{deep_company_cards_section(companies, "weak", limit=8)}

## 十一、验证清单

### 细分方向专属验证

{subdirection_validation_section(companies)}

### 通用验证

{validation_checklist_section(context)}

## 十二、核心结论

{deep_dive_conclusion(term, context, companies)}

## 十三、底层题材雷达护栏摘要

{deep_dive_governance_section(companies)}

### 深拆质量门禁

{deep_dive_quality_gate_section(context, companies)}

## 十四、数据来源与边界

- 主信源：PDF ingest 研报、精选逻辑/脱水文本、full 精读/report_contexts。
- baseline：只做公司基础画像和主营业务是否冲突的辅助校验。
- full 精读：只用于题材定义、产业链上下游、关键环节和细分方向，不写入 entities，也不直接升级公司事实。
- 公告/订单/业绩：当前仅作为后续验证空位，不作为高权重核心判断。
- 输出方式：不做个股排名，不展示分数，只做相对核心/重点相关/观察/弱相关分层与逻辑解释。
"""


def build_report(term: str, vault: Path, definition: str = "", context: dict | None = None) -> str:
    rel_dir = vault / "relations"
    graph = load_json(rel_dir / RELATION_FILES["concept_graph"], {"concepts": {}, "relations": []})
    exposures = load_json(rel_dir / RELATION_FILES["entity_exposures"], {"entities": {}})
    aliases = load_json(rel_dir / RELATION_FILES["aliases"], {"aliases": {}})
    evidence_index = load_json(rel_dir / RELATION_FILES["evidence_index"], {"items": []})
    theme_signals = load_json(rel_dir / RELATION_FILES["theme_signals"], {"version": 1, "themes": {}})
    pattern_library = load_json(rel_dir / RELATION_FILES["pattern_library"], {"version": 1, "patterns": {}})
    report_contexts = load_json(rel_dir / RELATION_FILES["report_contexts"], {"version": 1, "reports": {}})

    concepts = graph.get("concepts", {})
    context = context or {}
    if not definition.strip():
        definition = context_definition(context)
    external_search_text = " ".join(x for x in [definition, context_search_text(context)] if x.strip())

    primary, matches, notes = resolve_query(term, aliases, concepts)
    term_matched = bool(matches)
    if not matches and external_search_text.strip():
        _def_primary, def_matches, def_notes = resolve_query(external_search_text, aliases, concepts)
        if def_matches:
            matches = filter_concepts(def_matches, context)
            notes.extend([f"外部结构化信息辅助匹配：{x}" for x in def_matches[:5]])
            notes.extend(def_notes)
    local_report_contexts = match_report_contexts(term, primary, matches, report_contexts)
    if not context and local_report_contexts:
        context = runtime_context_from_report_contexts(term, local_report_contexts)
        if not definition.strip():
            definition = context_definition(context)
    match_scope = matches or ([primary] if primary in concepts else [])
    rels = related_concepts(primary, match_scope, graph)
    all_scope = unique(match_scope + rels[:12])
    company_scope = match_scope[:]
    if not term_matched and context:
        _focused_primary, focused_matches, _focused_notes = resolve_query(context_company_text(context), aliases, concepts)
        if focused_matches:
            company_scope = filter_concepts(focused_matches, context)
    companies = collect_companies(company_scope, graph, exposures)
    broadened_company_scope = False
    if not companies and all_scope:
        company_scope = all_scope
        companies = collect_companies(company_scope, graph, exposures)
        broadened_company_scope = True
    companies, dropped_generic_companies = filter_new_term_companies(companies, context, term_matched)
    enrich_companies_from_evidence_index(companies, evidence_index, company_scope or all_scope)
    if local_report_contexts:
        t = " ".join(str(ev.get("text", "")) for r in local_report_contexts for ev in (r.get("evidence", []) or []) if isinstance(ev, dict))
        structured_mentions = {}
        for row in local_report_contexts:
            for mention in row.get("company_mentions", []) or []:
                if not isinstance(mention, dict):
                    continue
                name = str(mention.get("company") or "").strip()
                if name:
                    structured_mentions.setdefault(name, []).append(mention)
        for company in companies:
            company["context_checked"] = True
            name = company.get("name")
            if name and structured_mentions.get(name):
                company["context_mentions"] = structured_mentions[name]
            elif name and name in t:
                company["context_mentions"] = [{"directness": "direct"}]
    companies = refresh_company_subtypes(companies)
    evidence = collect_evidence(company_scope or all_scope, companies, evidence_index)
    signal = load_signal(theme_signals, primary, matches)
    patterns = match_patterns(pattern_library, " ".join([term, external_search_text]), match_scope or [term])

    node = concepts.get(primary, {})
    supply_chain = node.get("supply_chain", {}) if isinstance(node, dict) else {}
    supply_lines = []
    for layer, values in supply_chain.items():
        vals = values if isinstance(values, list) else [values]
        supply_lines.append(f"- {layer}：{'、'.join(str(v) for v in vals if v)}")

    evidence_lines = []
    for item in evidence[:16]:
        source = item.get("source", "")
        target = item.get("target", "")
        ev = item.get("evidence", "")
        evidence_lines.append(f"- {target}：{ev}（{source}）")

    pattern_lines = []
    for name, pattern in patterns:
        stages = " -> ".join(pattern.get("stages", [])) or "待补"
        key_signals = "、".join(pattern.get("key_signals", [])) or "待补"
        pattern_lines.append(f"- {name}：阶段路径 {stages}；关键信号 {key_signals}")

    gaps = []
    if not match_scope:
        gaps.append("概念图谱尚未命中该新词，需要先做 concept-ingest。")
    if not companies:
        gaps.append("暂无可用公司映射，需要等待 baseline 或手动补 entity exposure。")
    if not signal:
        gaps.append("信号层为空，需要后续补卖方覆盖、价格信号、订单验证和市场热度。")
    if not patterns:
        gaps.append("暂无历史题材类比，需要补 pattern_library。")

    if term_matched:
        conclusion = "已命中知识库，可先做公司分层和证据回看。"
    elif match_scope:
        conclusion = "新词本身尚未入库，但外部定义命中了本地相关概念，可先做辅助映射。"
    else:
        conclusion = "未命中知识库，当前只能生成分析框架。"
    if companies:
        conclusion += f" 已找到 {len(companies)} 个相关公司，其中第一梯队 {sum(1 for c in companies if c.get('strength') == 'core')} 个。"
    if broadened_company_scope:
        conclusion += " 主概念暂无公司，已临时扩展到相关概念，需人工复核。"
    if dropped_generic_companies:
        conclusion += f" 已过滤 {dropped_generic_companies} 个泛化公司命中。"

    return f"""# {term} 题材雷达

生成日期：{date.today().isoformat()}

## 雷达结论

{conclusion}

## 外部定义

{definition.strip() if definition.strip() else '未提供。若知识库未命中，建议先用 web access 查公开定义、同义词、上位概念和产业链位置。'}

## 外部结构化信息

{context_section(context)}

### 抽取质量

{extraction_quality_section(context)}

### 证据分层

{evidence_stack_section(context)}

### 本地证据桶

{local_evidence_stack_section(companies)}

### 证据准备度

{theme_evidence_readiness_section(primary if term_matched else term)}

## 新词定位

- 输入：{term}
- 主匹配：{primary if term_matched else '未入库'}
- {'命中概念' if term_matched else '辅助命中概念'}：{('、'.join(matches) if matches else '未命中')}
{bullets(notes, '无别名命中')}

## 技术模块与环节相关度

{segment_scores_section(context)}

## 相邻概念区分

{adjacent_concepts_section(context)}

## 能力栈与筛选规则

{capability_and_rules_section(context)}

## 需求驱动与验证

{demand_drivers_section(context)}

### 需求场景表

{demand_scenarios_section(context)}

## 产业链全景

{industry_chain_map_section(context)}

### 本地研报产业链上下文

{report_contexts_section(local_report_contexts)}

## 细分方向扫描

{direction_scan_section(context)}

## 发酵进度排序

{progress_ranking_section(context)}

## 催化日历与验证清单

### 催化日历

{catalyst_calendar_section(context)}

### 验证清单

{validation_checklist_section(context)}

## 产业链与相关概念

### 已有产业链字段

{chr(10).join(supply_lines) if supply_lines else '- 待补'}

### 相关概念

{bullets(rels, '待补')}

### 历史题材类比

{chr(10).join(pattern_lines) if pattern_lines else '- 暂无合适类比'}

## 核心公司分层

### 第一梯队：core

{company_table(companies, 'core') if term_matched else '- 待验证：新词未入库前，不把辅助概念公司直接升为核心。'}

### 第二梯队：related

{company_table(companies, 'related')}

### 第三梯队：peripheral

{company_table(companies, 'peripheral')}

## 题材雷达 QC

{theme_qc_section(companies)}

## 验收评分

{acceptance_score_section(companies, context, local_report_contexts, term_matched)}

## 精读候选队列

{deep_read_queue_section(companies)}

## 候选公司线索

{candidate_company_section(context, companies)}

### 公司证据 Tier

{company_evidence_tiers_section(context, companies)}

## 证据索引

{chr(10).join(evidence_lines) if evidence_lines else '- 待补'}

## 信号层

{signal_lines(signal)}

## 预期差初判

- 产业逻辑：{'已有概念图谱支撑' if term_matched else ('外部定义辅助命中，待 concept-ingest 固化' if match_scope else '待 concept-ingest 确认')}
- 个股映射：{'已有公司暴露可用' if companies else '待 baseline 补证'}
- 市场认知：{('已有信号层记录' if signal else '待补')}
- 历史类比：{('、'.join(name for name, _ in patterns) if patterns else '待补')}
- 初步判断：信号层未补全前，只能做低置信预判，不能直接当成交易结论。

## 待补数据

{bullets(gaps, '暂无明显缺口')}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a read-only theme radar report.")
    parser.add_argument("--term", required=True, help="新词、题材或新闻短句")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="wiki vault path")
    parser.add_argument("--definition", default="", help="外部定义/技术拆解摘要，可来自 web access")
    parser.add_argument("--definition-file", help="外部定义摘要文件路径")
    parser.add_argument("--context-json", help="外部新词画像 JSON 路径")
    parser.add_argument("--theme-info-jsonl", help="IMA/Obsidian 统一题材信息池 JSONL，只读接入题材地图/上下游关系")
    parser.add_argument("--theme-direction-pool", help="标准细分方向池 JSON，只读接入细分方向扫描/发酵进度/验证清单")
    parser.add_argument("--out", help="optional markdown output path")
    parser.add_argument("--mode", choices=["radar", "qc", "deep-dive"], default="radar", help="输出模式：radar/qc=底层雷达与QC；deep-dive=题材深拆")
    args = parser.parse_args()

    definition = args.definition
    if args.definition_file:
        definition_path = Path(args.definition_file).expanduser()
        definition = definition_path.read_text(encoding="utf-8").strip()
    context = {}
    if args.context_json:
        context_path = Path(args.context_json).expanduser()
        context = load_json(context_path, {})

    theme_info_rows = []
    if args.theme_info_jsonl:
        theme_info_rows = read_theme_information_jsonl(Path(args.theme_info_jsonl).expanduser(), args.term)
    theme_direction_pool = {}
    if args.theme_direction_pool:
        theme_direction_pool = read_theme_direction_pool(Path(args.theme_direction_pool).expanduser(), args.term)

    vault = Path(args.vault).expanduser()
    if args.mode == "deep-dive":
        report = build_deep_dive_report(args.term, vault, definition, context, theme_info_rows, theme_direction_pool)
    else:
        report = build_report(args.term, vault, definition, context)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(str(out))
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

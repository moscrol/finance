#!/usr/bin/env python3
"""Read-only theme radar report from the finance wiki relation graph."""

from __future__ import annotations

import argparse
import ast
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
DEFAULT_IMA_PARSED_DIR = Path(os.path.expanduser(os.environ.get("IMA_PARSED_DIR", "~/Desktop/c c/ima/parsed")))
RELATION_FILES = {
    "concept_graph": "concept_graph.json",
    "entity_exposures": "entity_exposures.json",
    "aliases": "aliases.json",
    "evidence_index": "evidence_index.json",
    "theme_signals": "theme_signals.json",
    "pattern_library": "pattern_library.json",
    "report_contexts": "report_contexts.json",
    "benchmark_maps": "benchmark_maps.json",
}
STRENGTH_RANK = {"core": 0, "related": 1, "peripheral": 2}
EVIDENCE_BUCKETS = ("baseline", "curated_research", "delta", "graph_only", "missing")
EVIDENCE_WEIGHTS = {"delta": 4, "curated_research": 3, "baseline": 2, "graph_only": 1, "missing": -1}
IMA_LOGIC_CARD_SOURCE_TOKENS = ("个股逻辑卡", "最新逻辑卡", "最新逻辑跟踪", "研究素材", "素材整理")
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
DIRECTION_RANK = {
    "core_product": 0,
    "storage_product": 1,
    "component_module": 2,
    "manufacturing": 3,
    "package_test": 4,
    "equipment": 5,
    "materials": 6,
    "service_platform": 7,
    "downstream_channel": 8,
    "ecosystem": 9,
    "weak_watch": 10,
    "unknown": 11,
}
DIRECTION_LABELS = {
    "core_product": "核心产品/主线主体",
    "storage_product": "存储产品/模组与价格弹性",
    "optical_module": "光模块/光引擎",
    "optical_chip": "光芯片/光器件",
    "drug_pipeline": "药物管线/核心品种",
    "drug_platform": "平台技术/靶点机制",
    "pv_silicon": "硅料/硅片",
    "pv_cell_module": "电池片/组件",
    "pv_inverter_storage": "逆变器/储能配套",
    "component_module": "核心器件/模组",
    "manufacturing": "制造/工艺/产能",
    "package_test": "封测/先进封装",
    "equipment": "上游设备/量检测",
    "materials": "上游材料/电子化学品",
    "service_platform": "服务/平台",
    "downstream_channel": "下游渠道/运营",
    "ecosystem": "生态配套",
    "weak_watch": "弱关联观察",
    "unknown": "待判定",
}

THEME_DIRECTION_PROFILES = {
    "storage": {
        "aliases": ("存储", "HBM", "DRAM", "NAND", "DDR", "SSD", "存储芯片", "国产存储"),
        "ranks": ("storage_product", "manufacturing", "package_test", "equipment", "materials", "service_platform", "ecosystem", "weak_watch", "unknown"),
        "labels": {"manufacturing": "制造/晶圆代工"},
        "core_fallback": "storage_product",
        "component_fallback": "storage_product",
        "subdirection_tokens": ("存储", "DRAM", "NAND", "NOR", "HBM", "DDR", "LPDDR", "SSD", "Flash", "封测", "先进封装", "CMP", "硅片", "特气", "电子化学品", "PECVD", "量测", "检测", "主控", "内存接口"),
        "rules": (
            ("ecosystem", ("股权投资", "参股", "投资潜在相关")),
            ("materials", ("材料", "硅片", "特气", "电子化学品", "湿电子", "电子级磷酸", "清洗液", "CMP", "光刻胶", "前驱体", "抛光液", "封装材料", "树脂")),
            ("equipment", ("设备", "装备", "刻蚀设备", "薄膜设备", "沉积设备", "量测", "清洗设备", "检测设备", "PECVD", "ALD")),
            ("package_test", ("封测", "封装测试", "先进封装", "芯片测试", "测试服务", "TSV", "CoWoS", "CoWoP", "Fanout", "Chiplet")),
            ("storage_product", ("DRAM", "NAND", "NOR", "SLC", "SSD", "eSSD", "HBM", "DDR", "存储器", "存储产品", "存储模组", "内存接口芯片", "主控芯片", "模组", "汽车电子存储")),
            ("manufacturing", ("中游制造", "晶圆制造", "晶圆代工", "晶圆厂", "Foundry", "IDM", "FAB", "存储厂")),
        ),
    },
    "optical": {
        "aliases": ("光模块", "CPO", "硅光", "光芯片", "光通信", "1.6T", "800G"),
        "ranks": ("optical_module", "optical_chip", "component_module", "manufacturing", "equipment", "materials", "downstream_channel", "ecosystem", "weak_watch", "unknown"),
        "labels": {"manufacturing": "封装/代工/产线"},
        "core_fallback": "optical_module",
        "component_fallback": "optical_chip",
        "subdirection_tokens": ("光模块", "光芯片", "光器件", "硅光", "CPO", "LPO", "NPO", "800G", "1.6T", "EML", "VCSEL", "激光器", "探测器", "PCB", "mSAP", "HDI", "铜箔", "连接器", "散热"),
        "rules": (
            ("materials", ("材料", "PCB", "mSAP", "感光干膜", "载体铜箔", "陶瓷基板", "玻璃基板", "TGV", "DPC", "磷化铟", "InP", "光刻胶", "连接器", "散热")),
            ("equipment", ("设备", "检测", "测试", "耦合", "贴片", "封装设备", "光器件设备")),
            ("optical_chip", ("光芯片", "激光器", "探测器", "EML", "VCSEL", "CW Laser", "CPO", "硅光", "光引擎", "PLC", "AWG", "光器件")),
            ("optical_module", ("光模块", "光收发", "800G", "1.6T", "3.2T", "LPO", "AOC", "数据中心光模块")),
            ("manufacturing", ("代工", "制造", "封装", "产线", "扩产")),
        ),
    },
    "pharma": {
        "aliases": ("创新药", "医药", "药物", "管线", "ADC", "GLP", "小核酸", "双抗", "单抗"),
        "ranks": ("drug_pipeline", "drug_platform", "service_platform", "equipment", "materials", "manufacturing", "downstream_channel", "ecosystem", "weak_watch", "unknown"),
        "labels": {"equipment": "制药装备/生命科学工具", "materials": "原料药/中间体/耗材", "manufacturing": "制剂/商业化产能"},
        "core_fallback": "drug_pipeline",
        "component_fallback": "drug_platform",
        "subdirection_tokens": ("创新药", "管线", "ADC", "双抗", "单抗", "GLP", "小分子", "临床", "BD", "License", "CRO", "CDMO", "原料药", "中间体", "制药装备"),
        "rules": (
            ("service_platform", ("CXO", "CRO", "CDMO", "CMO", "临床试验", "外包", "研发服务", "平台服务")),
            ("equipment", ("制药装备", "生物工艺装备", "生产装备", "生命科学工具", "仪器", "设备")),
            ("materials", ("原料药", "中间体", "辅料", "培养基", "耗材", "试剂", "上游原料")),
            ("drug_platform", ("平台", "靶点", "技术平台", "ADC平台", "双抗平台", "小核酸平台", "基因编辑", "递送系统")),
            ("drug_pipeline", ("创新药", "管线", "新药", "候选药物", "临床", "适应症", "获批", "NDA", "IND", "III期", "II期", "I期", "单抗", "双抗", "ADC", "GLP-1")),
            ("manufacturing", ("商业化生产", "生产基地", "制剂生产", "产能", "GMP", "药品生产")),
            ("downstream_channel", ("销售", "商业化", "渠道", "药店", "院内", "医保", "集采")),
        ),
    },
    "pv": {
        "aliases": ("光伏", "BC电池", "TOPCon", "HJT", "钙钛矿", "组件", "逆变器", "硅片", "硅料"),
        "ranks": ("pv_silicon", "pv_cell_module", "pv_inverter_storage", "equipment", "materials", "downstream_channel", "ecosystem", "weak_watch", "unknown"),
        "labels": {"equipment": "光伏设备", "materials": "辅材/支架/玻璃胶膜"},
        "core_fallback": "pv_cell_module",
        "component_fallback": "pv_cell_module",
        "subdirection_tokens": ("光伏", "硅料", "硅片", "电池片", "组件", "TOPCon", "HJT", "BC", "钙钛矿", "逆变器", "储能", "胶膜", "玻璃", "银浆", "支架", "设备"),
        "rules": (
            ("equipment", ("设备", "电池设备", "组件设备", "丝网印刷", "镀膜", "PECVD", "PVD", "激光设备", "串焊机")),
            ("materials", ("胶膜", "玻璃", "银浆", "背板", "焊带", "靶材", "浆料", "边框", "支架", "BOS", "材料")),
            ("pv_inverter_storage", ("逆变器", "储能", "微逆", "PCS", "变流器", "电站配套")),
            ("pv_cell_module", ("电池片", "组件", "TOPCon", "HJT", "BC", "XBC", "钙钛矿", "叠层", "异质结")),
            ("pv_silicon", ("硅料", "硅片", "多晶硅", "单晶硅", "拉晶", "切片")),
            ("downstream_channel", ("电站", "EPC", "运营商", "装机", "户用", "工商业")),
        ),
    },
}

DIRECTION_SUBDIRECTION_TOKENS = {
    "storage_product": ("存储", "DRAM", "NAND", "NOR", "HBM", "DDR", "LPDDR", "SSD", "Flash", "主控", "内存接口"),
    "manufacturing": ("制造", "晶圆", "产线", "扩产", "代工", "IDM"),
    "package_test": ("封测", "封装", "先进封装", "测试", "HBM"),
    "equipment": ("设备", "PECVD", "ALD", "刻蚀", "量测", "检测", "清洗", "交付", "验收"),
    "materials": ("CMP", "硅片", "特气", "电子化学品", "光刻胶", "胶膜", "玻璃", "银浆", "支架", "背板", "焊带", "靶材", "浆料", "边框"),
    "optical_module": ("光模块", "800G", "1.6T", "3.2T", "LPO", "NPO", "CPO", "光引擎"),
    "optical_chip": ("光芯片", "光器件", "硅光", "激光器", "探测器", "EML", "VCSEL", "FAU", "MPO", "连接器"),
    "drug_pipeline": ("创新药", "管线", "小分子", "ADC", "双抗", "单抗", "GLP", "临床", "获批", "BD", "License"),
    "drug_platform": ("平台", "靶点", "ADC", "双抗", "小核酸", "License", "BD", "授权"),
    "pv_silicon": ("硅料", "硅片", "多晶硅", "单晶硅", "拉晶", "切片"),
    "pv_cell_module": ("电池片", "组件", "TOPCon", "HJT", "BC", "XBC", "钙钛矿", "异质结"),
    "pv_inverter_storage": ("逆变器", "储能", "PCS", "变流器", "微逆", "EMS", "BMS"),
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
                    "confidence": [],
                    "guardrails": [],
                    "validation_focus": [],
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
                "confidence": [],
                "guardrails": [],
                "validation_focus": [],
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
            if exp.get("confidence"):
                item["confidence"].append(exp["confidence"])
            if exp.get("guardrail"):
                item["guardrails"].append(exp["guardrail"])
            if exp.get("validation_focus"):
                item["validation_focus"].append(exp["validation_focus"])
            if exp.get("review_required"):
                item["review_required"] = True
            for source in exp.get("sources", []) or []:
                item["sources"].append(source)

    for item in by_key.values():
        for field in ("roles", "concepts", "evidence", "sources", "chain_layers", "evidence_layers", "update_types", "fact_hardness", "source_quality", "confidence", "guardrails", "validation_focus"):
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


def has_ima_logic_card_source_text(text: str) -> bool:
    return any(token in str(text or "") for token in IMA_LOGIC_CARD_SOURCE_TOKENS)


def has_ima_logic_card_source(company: dict) -> bool:
    return has_ima_logic_card_source_text(" ".join(str(x) for x in company.get("sources", []) or []))


def confidence_score(company: dict) -> int:
    values = {str(x).lower() for x in company.get("confidence", []) or []}
    if "high" in values:
        return 3
    if "medium" in values:
        return 2
    if "low" in values:
        return 1
    return 0


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
    if not is_explicit_weak_graph_only(exp) and has_ima_logic_card_source_text(sources):
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
    if has_ima_logic_card_source(company):
        score += 2
    score += confidence_score(company)
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
    if any(x in role_text for x in ("药店", "零售", "流通", "渠道", "分销", "代理", "经销", "运营商", "客运", "物流运营", "Robotaxi运营", "出行")):
        return "downstream_channel"
    if "upstream_equipment" in layers:
        return "upstream_equipment"
    if "upstream_materials" in layers:
        return "upstream_materials"
    if any(x in text for x in ("电子元器件分销", "分销商", "分销平台", "代理分销", "经销")):
        return "downstream_channel"
    if any(x in text for x in ("CDMO", "CRO", "CMO", "临床试验", "外包", "服务商", "平台", "高精地图", "软件")) or "midstream_service" in layers:
        return "service_provider"
    if any(x in text for x in ("传感器", "激光雷达", "毫米波雷达", "域控制器", "智能底盘", "芯片", "接口芯片", "封测", "封装")) or "upstream_components" in layers:
        return "component_supplier"
    if any(x in text for x in ("创新药", "管线", "新药", "研发商", "药物开发", "整车", "车型", "智驾", "自动驾驶")):
        return "core_subject"
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


def theme_direction_profile(term: str = "", concepts: list[str] | None = None) -> dict:
    haystack = " ".join([str(term or "")] + [str(x) for x in concepts or []])
    for profile in THEME_DIRECTION_PROFILES.values():
        if any(token and token in haystack for token in profile.get("aliases", ())):
            return profile
    return {"ranks": tuple(DIRECTION_RANK), "rules": ()}


def direction_rank(direction: str, profile: dict | None = None) -> int:
    if profile:
        ranks = profile.get("ranks", ())
        if direction in ranks:
            return ranks.index(direction)
    return DIRECTION_RANK.get(direction, DIRECTION_RANK["unknown"])


def direction_label(direction: str, profile: dict | None = None) -> str:
    if profile:
        labels = profile.get("labels", {})
        if isinstance(labels, dict) and direction in labels:
            return str(labels[direction])
    return DIRECTION_LABELS.get(direction, "待判定")


def profile_direction_match(profile: dict, haystack: str) -> str | None:
    for direction, tokens in profile.get("rules", ()) or ():
        if any(token and token in haystack for token in tokens):
            return direction
    return None


def company_direction_key(company: dict, profile: dict | None = None) -> str:
    subtype = company.get("company_subtype") or company_subtype(company)
    layers = " ".join(normalized_chain_layers(company))
    raw_layers = " ".join(str(x) for x in company.get("chain_layers", []) or [])
    role_text = " ".join(str(x) for x in company.get("roles", []) or [])
    evidence_body = " ".join(str(x) for x in company.get("evidence", []) or [])
    haystack = f"{role_text} {evidence_body} {raw_layers} {layers}"

    if subtype == "weak_graph":
        return "weak_watch"
    profile_match = profile_direction_match(profile or {}, haystack) if profile else None
    if profile_match:
        return profile_match
    if subtype == "service_provider":
        return "service_platform"
    if subtype == "downstream_channel":
        return "downstream_channel"
    if subtype == "ecosystem":
        return "ecosystem"
    if subtype == "component_supplier":
        return str((profile or {}).get("component_fallback") or "component_module")
    if subtype == "core_subject":
        return str((profile or {}).get("core_fallback") or "core_product")
    return "unknown"


def direction_group_sort_key(company: dict, profile: dict | None = None) -> tuple:
    direction = company_direction_key(company, profile)
    return (
        direction_rank(direction, profile),
        company_sort_key(company),
    )


def refresh_company_subtypes(companies: list[dict], profile: dict | None = None) -> list[dict]:
    for company in companies:
        company["company_subtype"] = company_subtype(company)
    return sorted(companies, key=lambda company: direction_group_sort_key(company, profile))


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


def acceptance_score_section(companies: list[dict], context: dict, local_report_contexts: list[dict], term_matched: bool, profile: dict | None = None) -> str:
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
    top10 = direction_ranked_sample(companies, profile)
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
        f"| 方向内公司排序 | 30 | {ranking_score} | 方向头部样本过度高估 {top10_overranked}，弱颗粒度 {top10_weak}，未知链层 {top10_unknown_layer}，链层冲突 {top10_chain_conflict}，需复核 {top10_review_required}，软事实 {top10_soft_fact} |",
        f"| 证据桶准确性 | 20 | {bucket_score} | baseline={counts['baseline']}，curated={counts['curated_research']}，delta={counts['delta']}，graph_only={counts['graph_only']} |",
        f"| 精读候选队列 | 15 | {deep_queue_score} | 队列公司 {len(qc_deep)} |",
        f"| 结论可用性 | 10 | {usability} | 方向头部样本 baseline 支撑 {top10_baseline} |",
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


def company_direction_table(rows: list[dict], limit: int = 8) -> str:
    selected = sorted(rows, key=company_sort_key)[:limit]
    if not selected:
        return "- 待 baseline 补证"
    lines = ["| 公司 | 代码 | 强度 | 公司类型 | 关联概念 | 归一链条层级 | 证据桶 | 事实硬度 | 产业链角色 | 证据 |", "|---|---:|---|---|---|---|---|---|---|---|"]
    for r in selected:
        evidence = "；".join(r["evidence"][:2]) or "待补证"
        roles = "；".join(r["roles"][:2]) or "受益标的"
        normalized_layers = "、".join(normalized_chain_layers(r)[:3]) or "unknown"
        fact_hardness = fact_hardness_rank(r)
        if r.get("review_required"):
            fact_hardness = f"{fact_hardness}/需复核"
        bucket_summary = evidence_bucket_summary(r)
        subtype = SUBTYPE_LABELS.get(r.get("company_subtype") or company_subtype(r), "待判定")
        strength = company_display_strength(r)
        lines.append(
            f"| {r['name']} | {r.get('code','')} | {strength} | {subtype} | {'、'.join(r['concepts'][:4])} | {normalized_layers} | {bucket_summary} | {fact_hardness} | {roles} | {evidence} |"
        )
    if len(rows) > limit:
        lines.append(f"\n- 另有 {len(rows) - limit} 家同方向公司进入候补/精读队列。")
    return "\n".join(lines)


def direction_company_section(companies: list[dict], term_matched: bool, profile: dict | None = None, limit_per_direction: int = 8) -> str:
    if not companies:
        return "- 待 baseline 补证"

    groups: dict[str, list[dict]] = {}
    for company in companies:
        direction = company_direction_key(company, profile)
        groups.setdefault(direction, []).append(company)

    lines = []
    if not term_matched:
        lines.append("- 待验证：新词未入库前，不把辅助概念公司直接升为核心。")
        lines.append("")
    for direction in sorted(groups, key=lambda key: direction_rank(key, profile)):
        rows = groups[direction]
        label = direction_label(direction, profile)
        core_count = sum(1 for r in rows if company_display_strength(r) == "core")
        related_count = sum(1 for r in rows if company_display_strength(r) == "related")
        peripheral_count = sum(1 for r in rows if company_display_strength(r) == "peripheral")
        lines.extend(
            [
                f"### {label}",
                "",
                f"- 方向内样本：{len(rows)} 家；core={core_count}，related={related_count}，peripheral={peripheral_count}",
                "",
                company_direction_table(rows, limit_per_direction),
                "",
            ]
        )
    return "\n".join(lines).strip()


def direction_ranked_sample(companies: list[dict], profile: dict | None = None, per_direction: int = 3, limit: int = 10) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for company in companies:
        groups.setdefault(company_direction_key(company, profile), []).append(company)
    sample = []
    for direction in sorted(groups, key=lambda key: direction_rank(key, profile)):
        sample.extend(sorted(groups[direction], key=company_sort_key)[:per_direction])
    return sample[:limit]


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


def first_text(items, fallback: str = "待补") -> str:
    values = sorted(as_list(items), key=signal_text_sort_key)
    for value in values:
        text = compact_text(value, 140)
        if text:
            return text
    return fallback


def signal_text_sort_key(value: str) -> tuple:
    text = str(value or "")
    high_tokens = (
        "AI", "算力", "服务器", "HBM", "1.6T", "800G", "CPO", "资本开支",
        "订单", "小批量", "量产", "扩产", "认证", "涨价", "价格", "客户",
        "临床", "获批", "NDA", "IND", "License", "BD", "出海",
        "TOPCon", "HJT", "BC", "钙钛矿", "逆变器", "储能",
    )
    generic_tokens = ("消费电子", "计算机", "工业控制", "物联网", "生态", "相关", "待补")
    high = sum(1 for token in high_tokens if token in text)
    generic = sum(1 for token in generic_tokens if token in text)
    return (-high, generic, len(text), text)


def company_bucket_hits(companies: list[dict], bucket: str) -> list[dict]:
    return [company for company in companies if (company.get("evidence_buckets", {}) or {}).get(bucket)]


def top_company_names(companies: list[dict], limit: int = 5) -> str:
    rows = sorted(companies, key=company_sort_key)[:limit]
    return "、".join(company.get("name", "") for company in rows if company.get("name")) or "待补"


def trigger_strength_label(source_count: int, quality_count: int = 0) -> str:
    if source_count >= 3 and quality_count >= 2:
        return "Tier 1"
    if source_count >= 2:
        return "Tier 2"
    if source_count >= 1:
        return "Tier 3"
    return "待补"


def signal_dimension_rows(context: dict, signal: dict, companies: list[dict]) -> list[dict]:
    context = context if isinstance(context, dict) else {}
    signal = signal if isinstance(signal, dict) else {}
    baseline_hits = company_bucket_hits(companies, "baseline")
    research_hits = company_bucket_hits(companies, "curated_research")
    delta_hits = company_bucket_hits(companies, "delta")
    graph_hits = company_bucket_hits(companies, "graph_only")

    fact_items = []
    fact_items.extend(as_list(signal.get("order_signals")))
    fact_items.extend(as_list(signal.get("industry_progress")))
    fact_items.extend(as_list(context.get("verification_nodes")))
    fact_items.extend(as_list(context.get("catalysts")))
    has_direct_fact_signal = bool(fact_items)
    if not fact_items and baseline_hits:
        fact_items.append(f"baseline 支撑 {len(baseline_hits)} 家公司基础业务映射")

    industry_items = []
    industry_items.extend(as_list(context.get("demand_drivers")))
    industry_items.extend(as_list(context.get("core_benefit_links")))
    industry_items.extend(as_list(signal.get("industry_progress")))
    direction_rows = context.get("direction_scan", []) if isinstance(context.get("direction_scan"), list) else []
    for row in direction_rows[:5]:
        if isinstance(row, dict):
            industry_items.append(row.get("name") or row.get("direction") or "")

    market_items = []
    market_items.extend(as_list(signal.get("market_heat")))
    market_items.extend(as_list(signal.get("price_signals")))
    market_items.extend(as_list(signal.get("sell_side_coverage")))
    if delta_hits:
        market_items.append(f"delta/复盘线索命中 {len(delta_hits)} 家：{top_company_names(delta_hits, 4)}")

    return [
        {
            "dimension": "公告/事实",
            "signal": first_text(fact_items),
            "source": "theme_signals / validation / baseline",
            "tier": trigger_strength_label(2 if has_direct_fact_signal else int(bool(fact_items)), 1 if has_direct_fact_signal else 0),
            "explain": f"用于确认题材不是纯叙事；当前 baseline={len(baseline_hits)}，graph_only={len(graph_hits)}；{'有直接事实触发' if has_direct_fact_signal else '暂无直接公告/订单触发'}。",
        },
        {
            "dimension": "产业趋势",
            "signal": first_text(industry_items),
            "source": "report_contexts / direction_scan",
            "tier": trigger_strength_label(int(bool(industry_items)) + int(bool(research_hits)), int(bool(research_hits))),
            "explain": f"用于确认需求链条和受益环节；当前 curated_research={len(research_hits)}。",
        },
        {
            "dimension": "市场热点",
            "signal": first_text(market_items),
            "source": "theme_signals / delta evidence",
            "tier": trigger_strength_label(int(bool(market_items)) + int(bool(delta_hits)), int(bool(delta_hits))),
            "explain": f"用于确认市场是否开始交易；当前 delta={len(delta_hits)}。",
        },
    ]


def resonance_tier(rows: list[dict]) -> str:
    active = [row for row in rows if row.get("signal") and row.get("signal") != "待补"]
    hard = [row for row in active if row.get("tier") in ("Tier 1", "Tier 2")]
    if len(hard) >= 3:
        return "Tier 1：公告/事实 + 产业趋势 + 市场热点三重共振"
    if len(active) >= 2:
        return "Tier 2：双重验证，已具备跟踪价值但仍需补强缺口"
    if len(active) == 1:
        return "Tier 3：单点逻辑，进入观察池"
    return "待补：缺触发信号，暂按静态产业链处理"


def signal_gap_items(rows: list[dict], companies: list[dict]) -> list[str]:
    gaps = []
    for row in rows:
        if row.get("signal") == "待补":
            gaps.append(f"补{row.get('dimension')}线索")
    qc_weak = [c for c in companies if "weak_granularity" in company_qc_flags(c)]
    qc_soft = [c for c in companies if "soft_fact_hardness" in company_qc_flags(c)]
    if qc_weak:
        gaps.append(f"弱颗粒度公司 {len(qc_weak)} 家，需补主营占比/产品直接性")
    if qc_soft:
        gaps.append(f"软事实公司 {len(qc_soft)} 家，需补公告/年报/官网")
    return gaps[:5]


def fermentation_signal_section(context: dict, signal: dict, companies: list[dict]) -> str:
    rows = signal_dimension_rows(context, signal, companies)
    lines = [
        "### 触发信号三维交叉",
        "",
        "| 维度 | 信号 | 证据来源 | 强度 | 解释 |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('dimension','')} | {compact_text(row.get('signal',''), 140)} | {row.get('source','')} | {row.get('tier','')} | {compact_text(row.get('explain',''), 140)} |"
        )

    tier = resonance_tier(rows)
    gaps = signal_gap_items(rows, companies)
    if tier.startswith("Tier 1"):
        judgement = "已经从静态产业链进入共振跟踪状态，优先看方向内头部公司是否有硬事实继续确认。"
    elif tier.startswith("Tier 2"):
        judgement = "具备发酵雏形，适合跟踪验证清单，但还不能当成一致预期后的强结论。"
    elif tier.startswith("Tier 3"):
        judgement = "目前更像单点线索，先观察是否扩散到产业趋势或盘面信号。"
    else:
        judgement = "当前主要是知识库静态拆解，缺少足够的今日触发信号。"

    lines.extend(
        [
            "",
            "### 共振分层",
            f"- {tier}",
            "",
            "### 判断",
            f"- {judgement}",
            "",
            "### 风险提示",
            bullets(gaps, "暂无明显风险缺口"),
            "",
            "### 下一步验证",
            "- 公告/年报/官网：确认订单、客户、产能、认证、收入占比。",
            "- 盘面/复盘：确认是否从单家公司扩散到方向内多家公司。",
            "- 产业资料：确认需求、瓶颈和工艺环节是否继续被多源强化。",
        ]
    )
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
            if not theme_compatible(term, theme):
                continue
            rows.append(row)
    return rows


def theme_compatible(term: str, theme: str) -> bool:
    term_text = str(term or "").strip()
    theme_text = str(theme or "").strip()
    if not term_text or not theme_text:
        return True
    if term_text in theme_text or theme_text in term_text:
        return True
    alias_groups = [
        {"存储芯片", "国产存储", "HBM与国产存储", "HBM", "DRAM", "NAND", "NOR"},
    ]
    for group in alias_groups:
        term_hit = any(token and token in term_text for token in group)
        theme_hit = any(token and token in theme_text for token in group)
        if term_hit and theme_hit:
            return True
    return False


def read_theme_direction_pool(path: Path, term: str) -> dict:
    if not path or not path.exists():
        return {}
    data = load_json(path, {})
    theme = str(data.get("theme") or "").strip()
    if not theme_compatible(term, theme):
        return {}
    directions = data.get("directions", [])
    if not isinstance(directions, list):
        return {}
    return data


def read_theme_supplement_pool(path: Path, term: str) -> dict:
    if not path or not path.exists():
        return {}
    data = load_json(path, {})
    theme = str(data.get("theme") or "").strip()
    if not theme_compatible(term, theme):
        return {}
    return data if isinstance(data, dict) else {}


def theme_asset_score(term: str, path: Path, theme: str = "") -> int:
    name = path.name
    score = 0
    if term and term in name:
        score += 100
    if theme and (term in theme or theme in term):
        score += 80
    if theme_compatible(term, theme or name):
        score += 40
    if ".merged." in name:
        score += 30
    if "DeepDive" in name:
        score += 10
    return score


def auto_discover_theme_supplement_pool(term: str, parsed_dir: Path = DEFAULT_IMA_PARSED_DIR) -> dict:
    if not parsed_dir.exists():
        return {}
    candidates = []
    patterns = ["*.merged.theme_supplement_pool.json", "*.theme_supplement_pool.json"]
    for pattern in patterns:
        for path in parsed_dir.glob(pattern):
            data = load_json(path, {})
            if not isinstance(data, dict):
                continue
            theme = str(data.get("theme") or "").strip()
            if not theme_compatible(term, theme or path.name):
                continue
            summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
            row_count = int(summary.get("row_count", 0) or 0)
            candidates.append((theme_asset_score(term, path, theme) + min(row_count, 300), path, data))
    if not candidates:
        return {}
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][2]


def auto_discover_theme_info_rows(term: str, parsed_dir: Path = DEFAULT_IMA_PARSED_DIR) -> list[dict]:
    if not parsed_dir.exists():
        return []
    candidates = []
    for path in parsed_dir.glob("*.theme_information_items.jsonl"):
        if not theme_compatible(term, path.name):
            continue
        candidates.append((theme_asset_score(term, path, path.name), path))
    if not candidates:
        return []
    candidates.sort(key=lambda item: item[0], reverse=True)
    return read_theme_information_jsonl(candidates[0][1], term)


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
    "公告",
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
    "材料",
    "电池",
    "良率",
    "项目落地",
    "中标",
    "收入增速",
    "业务数据",
    "业绩预告",
    "产量数据",
    "产能/装机",
    "年报（收入/利润/业务）",
    "年报数据",
    "季报数据",
    "ipo",
    "IPO",
    "设备",
    "上游材料",
    "Capex",
    "capex",
    "并购/整合",
    "业绩",
    "估值",
    "股价",
    "其他",
    "待核验",
    "未分段",
    "明确产能",
    "明确收入结构",
    "明确合作协议",
    "明确合作协议/并购",
    "明确库存",
    "明确成本",
    "明确资源储量",
    "明确项目",
    "明确项目落地",
    "明确分红",
}


def is_generic_theme_info_segment(segment: str) -> bool:
    s = str(segment or "").strip()
    if not s:
        return True
    if s in GENERIC_THEME_INFO_SEGMENTS:
        return True
    if s.startswith("明确"):
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


def supplement_demand_drivers(rows: list[dict]) -> list[str]:
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        scenario = str(row.get("scenario") or "").strip()
        driver = str(row.get("downstream_driver") or "").strip()
        if scenario and driver:
            out.append(f"{scenario}：{driver}")
        elif scenario:
            out.append(scenario)
    return unique(out)[:12]


def supplement_core_benefit_links(rows: list[dict]) -> list[str]:
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        links = "、".join(as_list(row.get("beneficiary_links"))[:4])
        entities = "、".join(as_list(row.get("representative_entities"))[:6])
        if links and entities:
            out.append(f"{links}：{entities}")
        elif links:
            out.append(links)
    return unique(out)[:12]


def merge_theme_information_context(context: dict, theme_context: dict) -> dict:
    if not theme_context:
        return context or {}
    merged = dict(context or {})
    if theme_context.get("definition"):
        merged["definition"] = theme_context.get("definition")
    for key in ("demand_drivers", "core_benefit_links", "verification_nodes"):
        if theme_context.get(key):
            merged[key] = unique(as_list(theme_context.get(key)))[:16]
        else:
            merged[key] = unique(as_list(merged.get(key)))[:16]
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
    recognition = row.get("recognition_profile", {}) if isinstance(row, dict) else {}
    if isinstance(recognition, dict) and recognition.get("score") is not None:
        try:
            return int(recognition.get("score"))
        except Exception:
            pass
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
    opportunity_rows = []
    evidence_trace_rows = []
    for row in directions:
        if not isinstance(row, dict):
            continue
        profile = row.get("evidence_profile", {}) if isinstance(row.get("evidence_profile"), dict) else {}
        companies = direction_pool_entities(row)
        evidence_label = direction_pool_evidence_label(profile)
        demand = "、".join(as_list(row.get("demand_sources")))
        bottleneck = "、".join(as_list(row.get("bottlenecks_solved")))
        verification = direction_pool_first_verification(row)
        hierarchy = row.get("sector_hierarchy", {}) if isinstance(row.get("sector_hierarchy"), dict) else {}
        recognition = row.get("recognition_profile", {}) if isinstance(row.get("recognition_profile"), dict) else {}
        validation_plan = row.get("validation_plan", {}) if isinstance(row.get("validation_plan"), dict) else {}
        opportunity = row.get("opportunity_profile", {}) if isinstance(row.get("opportunity_profile"), dict) else {}
        evidence_trace = row.get("evidence_trace", []) if isinstance(row.get("evidence_trace"), list) else []
        recognition_stage = recognition.get("stage") or row.get("recognition_stage", "")
        recognition_score = recognition.get("score", "")
        recognition_label = f"{recognition_stage}（{recognition_score}）" if recognition_score != "" else recognition_stage
        scan_rows.append({
            "direction": row.get("direction", ""),
            "sector": row.get("primary_sector") or row.get("parent_sector", ""),
            "sector_hierarchy": hierarchy,
            "primary_sector": row.get("primary_sector") or row.get("parent_sector", ""),
            "secondary_sectors": as_list(row.get("secondary_sectors")),
            "sector_confidence": row.get("sector_confidence", ""),
            "sector_match_reason": row.get("sector_match_reason", ""),
            "sector_source": row.get("sector_source", ""),
            "prosperity": "；".join(x for x in [f"需求：{demand}" if demand else "", f"瓶颈：{bottleneck}" if bottleneck else "", evidence_label] if x),
            "mention_frequency": f"方向池命中 {profile.get('item_count', 0)} 条",
            "recognition_level": recognition_label,
            "recognition_profile": recognition,
            "classification": f"{row.get('direction_type','')}/{row.get('chain_bucket','')}",
            "core_catalyst": verification,
            "candidate_companies": companies,
        })
        ranking_rows.append({
            "direction": row.get("direction", ""),
            "stage": recognition_stage,
            "recognition_level": recognition_label,
            "stage_reason": "；".join(as_list(recognition.get("stage_reason"))[:3]) if isinstance(recognition, dict) else "",
            "upgrade_triggers": "；".join(as_list(recognition.get("upgrade_triggers"))[:2]) if isinstance(recognition, dict) else "",
            "downgrade_risks": "；".join(as_list(recognition.get("downgrade_risks"))[:2]) if isinstance(recognition, dict) else "",
            "tier": opportunity.get("tier", ""),
            "evidence_level": profile.get("highest_evidence_layer", "direction_pool"),
            "progress_score": opportunity.get("opportunity_score") or direction_pool_score(row),
            "key_signal": evidence_label,
            "next_validation": verification,
            "priority": opportunity.get("follow_up_priority") or ("优先跟踪" if direction_pool_score(row) >= 60 else "观察验证"),
        })
        opportunity_rows.append({
            "direction": row.get("direction", ""),
            "tier": opportunity.get("tier", ""),
            "follow_up_priority": opportunity.get("follow_up_priority", ""),
            "opportunity_score": opportunity.get("opportunity_score", ""),
            "supporting_evidence": "；".join(as_list(opportunity.get("supporting_evidence"))[:3]),
            "missing_proof": "；".join(as_list(opportunity.get("missing_proof"))[:3]),
            "next_actions": "；".join(as_list(opportunity.get("next_actions"))[:3]),
        })
        for trace in evidence_trace[:4]:
            if not isinstance(trace, dict):
                continue
            source_ref = str(trace.get("source_path") or "")
            if trace.get("line_no"):
                source_ref = f"{source_ref}:{trace.get('line_no')}" if source_ref else str(trace.get("line_no"))
            evidence_trace_rows.append({
                "direction": row.get("direction", ""),
                "entity": trace.get("entity", ""),
                "claim": trace.get("claim", ""),
                "evidence_level": trace.get("evidence_level", ""),
                "confidence": trace.get("confidence", ""),
                "source": trace.get("source_title") or trace.get("source_system", ""),
                "source_date": trace.get("source_date", ""),
                "item_id": trace.get("item_id", ""),
                "needs_review": "是" if trace.get("needs_review") else "否",
                "source_ref": source_ref,
            })
        for catalyst in validation_plan.get("occurred_catalysts") or row.get("catalysts") or []:
            if not isinstance(catalyst, dict):
                continue
            catalyst_rows.append({
                "direction": row.get("direction", ""),
                "time": catalyst.get("time_window", ""),
                "event": catalyst.get("event", ""),
                "event_type": catalyst.get("event_type", "occurred_catalyst"),
                "evidence": evidence_label,
                "watch_item": catalyst.get("next_watch") or row.get("direction", ""),
            })
        fallback_downgrade = "；".join(as_list(validation_plan.get("downgrade_conditions"))[:2])
        for item in validation_plan.get("upcoming_catalysts") or row.get("verification_items") or []:
            if not isinstance(item, dict):
                continue
            validation_rows.append({
                "direction": row.get("direction", ""),
                "item": item.get("event") or item.get("item", ""),
                "window": item.get("time_window") or validation_plan.get("validation_window", ""),
                "upgrade_condition": item.get("next_watch") or item.get("upgrade_condition", ""),
                "downgrade_condition": fallback_downgrade or item.get("downgrade_condition", ""),
                "status": validation_plan.get("status", "待验证"),
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
        "opportunity_priorities": opportunity_rows,
        "evidence_trace": evidence_trace_rows[:80],
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
    for key in ("direction_scan", "progress_ranking", "opportunity_priorities", "evidence_trace", "catalyst_calendar", "validation_checklist", "demand_bottleneck_map"):
        existing = merged.get(key) if isinstance(merged.get(key), list) else []
        incoming = direction_context.get(key) if isinstance(direction_context.get(key), list) else []
        if key in ("direction_scan", "progress_ranking", "opportunity_priorities"):
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


def build_theme_supplement_pool_context(pool: dict) -> dict:
    if not isinstance(pool, dict) or not pool:
        return {}
    context = {
        "theme_supplement_pool": {
            "enabled": True,
            "theme": pool.get("theme", ""),
            "generated_at": pool.get("generated_at", ""),
            "source_file": pool.get("source_file", ""),
            "summary": pool.get("summary", {}),
        },
        "definition_profile": pool.get("definition_profile", {}) if isinstance(pool.get("definition_profile"), dict) else {},
        "demand_scenarios": pool.get("demand_scenarios", []) if isinstance(pool.get("demand_scenarios"), list) else [],
        "material_process_scan": pool.get("material_process_scan", []) if isinstance(pool.get("material_process_scan"), list) else [],
        "industry_chain_panorama": pool.get("industry_chain_panorama", []) if isinstance(pool.get("industry_chain_panorama"), list) else [],
        "recognition_timeline": pool.get("recognition_timeline", []) if isinstance(pool.get("recognition_timeline"), list) else [],
        "action_plan": pool.get("action_plan", []) if isinstance(pool.get("action_plan"), list) else [],
        "progress_ruler": pool.get("progress_ruler", []) if isinstance(pool.get("progress_ruler"), list) else [],
        "supplement_evidence_items": pool.get("evidence_items", []) if isinstance(pool.get("evidence_items"), list) else [],
    }
    context["demand_drivers"] = supplement_demand_drivers(context["demand_scenarios"])
    context["core_benefit_links"] = supplement_core_benefit_links(context["demand_scenarios"])
    scan_rows = []
    ranking_rows = []
    for idx, row in enumerate(context["material_process_scan"]):
        if not isinstance(row, dict) or not row.get("name"):
            continue
        prosperity = "；".join(
            x for x in [
                str(row.get("prosperity_judgment") or "").strip(),
                str(row.get("core_catalyst") or "").strip(),
            ] if x
        )
        scan_rows.append({
            "direction": row.get("name", ""),
            "sector": row.get("major_track", ""),
            "sector_hierarchy": {
                "level_1": row.get("major_track", ""),
                "level_2": row.get("chain_position", ""),
                "level_3": row.get("name", ""),
            },
            "primary_sector": row.get("major_track", ""),
            "secondary_sectors": [row.get("chain_position", "")] if row.get("chain_position") else [],
            "prosperity": prosperity,
            "mention_frequency": row.get("daily_review_frequency", ""),
            "recognition_level": row.get("cognition_level", ""),
            "classification": row.get("classification", ""),
            "core_catalyst": row.get("next_validation") or row.get("core_catalyst", ""),
            "candidate_companies": as_list(row.get("representative_entities")),
        })
        ranking_rows.append({
            "direction": row.get("name", ""),
            "stage": row.get("cognition_level", ""),
            "recognition_level": row.get("cognition_level", ""),
            "stage_reason": prosperity,
            "evidence_level": "theme_supplement_pool",
            "progress_score": max(40, 85 - idx),
            "key_signal": row.get("core_catalyst", ""),
            "next_validation": row.get("next_validation", ""),
            "priority": row.get("daily_review_frequency", ""),
        })
    context["direction_scan"] = scan_rows
    context["progress_ranking"] = ranking_rows
    context["direction_frame"] = {
        "allowed_domains": [],
        "directions": [
            {
                "label": row.get("direction", ""),
                "tokens": [
                    x for x in [
                        row.get("direction", ""),
                        row.get("sector", ""),
                        row.get("primary_sector", ""),
                        row.get("classification", ""),
                        row.get("core_catalyst", ""),
                        *as_list(row.get("secondary_sectors")),
                        *as_list(row.get("candidate_companies")),
                    ] if x
                ],
                "theme": row.get("sector", "") or row.get("direction", ""),
                "why": row.get("prosperity", ""),
                "validation": row.get("core_catalyst", ""),
                "source": "theme_supplement_pool",
            }
            for row in scan_rows
        ],
        "secondary": {},
        "source": "theme_supplement_pool",
    }
    validation_rows = []
    for row in pool.get("validation_items", []) if isinstance(pool.get("validation_items"), list) else []:
        if not isinstance(row, dict):
            continue
        validation_rows.append({
            "direction": row.get("direction", ""),
            "item": row.get("item", ""),
            "window": row.get("validation_window", ""),
            "upgrade_condition": row.get("upgrade_condition", ""),
            "downgrade_condition": row.get("downgrade_condition", ""),
            "status": row.get("status", "待验证"),
            "validation_type": row.get("validation_type", ""),
            "source": row.get("source", ""),
            "source_date": row.get("source_date", ""),
            "item_id": row.get("item_id", ""),
        })
    catalyst_rows = []
    for row in pool.get("catalyst_calendar", []) if isinstance(pool.get("catalyst_calendar"), list) else []:
        if not isinstance(row, dict):
            continue
        catalyst_rows.append({
            "direction": row.get("direction", ""),
            "time": row.get("time_window", ""),
            "event": row.get("event", ""),
            "event_type": row.get("event_type", ""),
            "evidence": row.get("evidence_summary", ""),
            "watch_item": row.get("next_watch", ""),
            "source": row.get("source", ""),
            "source_date": row.get("source_date", ""),
            "item_id": row.get("item_id", ""),
        })
    context["validation_checklist"] = validation_rows
    context["catalyst_calendar"] = catalyst_rows
    return context


THEME_INFO_FINE_COMPONENT_TOKENS = (
    "法拉第", "旋片", "旋光片", "光隔离器", "隔离器", "磁光", "TGG", "TSAG", "SGGG",
    "FAU", "光纤阵列", "MPO", "MTP", "MMC", "MT插芯", "陶瓷插芯", "连接器",
    "AWG", "PLC", "WDM", "波分", "滤波片", "薄膜滤波", "环形器", "准直器",
    "透镜", "透镜阵列", "棱镜", "偏振", "光引擎", "光器件", "OSA", "TOSA", "ROSA",
)


def theme_info_fine_component_name(row: dict) -> str:
    segment = str(row.get("segment") or "").strip()
    component = str(row.get("component") or "").strip()
    label_text = f"{segment} {component}"
    if not any(token in label_text for token in THEME_INFO_FINE_COMPONENT_TOKENS):
        return ""
    if any(token in label_text for token in ("MPO", "MTP", "MMC")) and any(token in label_text for token in ("FAU", "AWG")):
        return "MPO/FAU/AWG"
    if any(token in label_text for token in ("FAU", "光纤阵列")):
        return "FAU/光纤阵列"
    if any(token in label_text for token in ("MPO", "MTP", "MMC", "MT插芯", "陶瓷插芯")):
        return "MPO/MTP/MMC连接器"
    if any(token in label_text for token in ("AWG", "PLC", "WDM", "波分")):
        return "AWG/PLC/WDM"
    if any(token in label_text for token in ("环形器", "滤波片", "薄膜滤波", "偏振", "棱镜")):
        return "环形器/滤波片/偏振器件"
    if any(token in label_text for token in ("准直器", "透镜", "透镜阵列")):
        return "准直器/透镜阵列"
    if any(token in label_text for token in ("法拉第", "旋片", "旋光片", "磁光", "TGG", "TSAG", "SGGG")) or (
        any(token in label_text for token in ("光隔离器", "隔离器"))
        and not any(token in label_text for token in ("FAU", "MPO", "MTP", "MMC", "光引擎"))
    ):
        return "法拉第旋片/光隔离器"
    broad_segment_tokens = ("涨价", "CPO、OCS", "光通信设备", "光器件、CPO", "上游-", "中游-", "下游-")
    name = component if component and any(token in segment for token in broad_segment_tokens) else (segment or component)
    if not name:
        return ""
    name = re.sub(r"^\d+(?:\.\d+)?\s*", "", name)
    name = name.replace("上游-", "").replace("中游-", "").replace("下游-", "")
    name = name.replace("法拉第旋片、光隔离器", "法拉第旋片/光隔离器")
    name = name.replace("MPO连接器、FAU、AWG", "MPO/FAU/AWG")
    return name.strip(" /｜|")


def theme_info_fine_component_position(name: str, text: str) -> str:
    haystack = f"{name} {text}"
    if any(token in haystack for token in ("FAU", "光纤阵列")):
        return "光纤阵列/光引擎器件"
    if any(token in haystack for token in ("MPO", "MTP", "MMC", "MT插芯", "陶瓷插芯", "连接器")):
        return "互连器件"
    if any(token in haystack for token in ("AWG", "PLC", "WDM", "波分")):
        return "无源光芯片/波分器件"
    if any(token in haystack for token in ("环形器", "滤波片", "薄膜滤波", "偏振", "棱镜")):
        return "OCS光学器件"
    if any(token in haystack for token in ("准直器", "透镜", "透镜阵列")):
        return "微光学元件"
    if any(token in haystack for token in ("法拉第", "旋片", "旋光片", "光隔离器", "隔离器", "磁光", "TGG", "TSAG", "SGGG")):
        return "光隔离器/磁光材料"
    if "光引擎" in haystack:
        return "光引擎器件"
    return "光器件/材料"


def theme_info_fine_component_rows(term: str, rows: list[dict], limit: int = 24) -> list[dict]:
    if not rows or not theme_compatible(term, "光模块"):
        return []
    grouped: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = theme_info_fine_component_name(row)
        if not name:
            continue
        claim = str(row.get("claim") or "").strip()
        entity = str(row.get("entity_name") or row.get("company") or "").strip()
        raw = row.get("raw_row") if isinstance(row.get("raw_row"), dict) else {}
        for field in ("相关公司", "代表公司", "公司", "企业"):
            if raw.get(field):
                entity = entity or str(raw.get(field)).strip()
        text = " ".join(str(row.get(k) or "") for k in ("chain_position", "segment", "component", "claim"))
        item = grouped.setdefault(
            name,
            {
                "name": name,
                "major_track": "光通信",
                "chain_position": theme_info_fine_component_position(name, text),
                "prosperity_judgment": "",
                "classification": "细颗粒光器件/材料",
                "core_catalyst": "",
                "representative_entities": [],
                "evidence_summary": "",
                "source": "theme_information_pool",
            },
        )
        if entity:
            item["representative_entities"].extend([x for x in re.split(r"[、,，/\s]+", entity) if x])
        if claim:
            existing = as_list(item.get("evidence_summary"))
            if claim not in existing:
                existing.append(claim)
            item["evidence_summary"] = "；".join(existing[:2])
            name_tokens = [x for x in re.split(r"[/、,，()\s]+", name) if len(x) >= 2]
            current = str(item.get("core_catalyst") or "")
            if not current or (any(token in claim for token in name_tokens) and not any(token in current for token in name_tokens)):
                item["core_catalyst"] = claim
    out = []
    for item in grouped.values():
        item["representative_entities"] = unique(item["representative_entities"])[:8]
        out.append(item)
    return sorted(out, key=lambda item: (0 if item.get("representative_entities") else 1, item.get("name", "")))[:limit]


def merge_theme_info_fine_components(context: dict, term: str, theme_info_rows: list[dict]) -> dict:
    additions = theme_info_fine_component_rows(term, theme_info_rows)
    if not additions:
        return context
    merged = dict(context or {})
    existing = [row for row in merged.get("material_process_scan", []) if isinstance(row, dict)]
    seen = {str(row.get("name") or row.get("direction") or "").strip() for row in existing}
    for row in additions:
        name = str(row.get("name") or "").strip()
        if name and name not in seen:
            existing.append(row)
            seen.add(name)
    merged["material_process_scan"] = existing
    return merged


def merge_theme_supplement_pool_context(context: dict, supplement_context: dict) -> dict:
    if not supplement_context:
        return context or {}
    merged = dict(context or {})
    merged["theme_supplement_pool"] = supplement_context.get("theme_supplement_pool", {})
    if supplement_context.get("definition_profile"):
        merged["definition_profile"] = supplement_context.get("definition_profile", {})
    generic_direction_labels = {"年报", "起点", "明确产能", "明确项目", "明确合作协议", "待确认", "应用"}
    if supplement_context.get("demand_drivers"):
        merged["demand_drivers"] = supplement_context.get("demand_drivers", [])
    if supplement_context.get("core_benefit_links"):
        merged["core_benefit_links"] = supplement_context.get("core_benefit_links", [])
    for key in (
        "demand_scenarios",
        "material_process_scan",
        "industry_chain_panorama",
        "recognition_timeline",
        "action_plan",
        "progress_ruler",
        "supplement_evidence_items",
        "direction_frame",
        "direction_scan",
        "progress_ranking",
        "catalyst_calendar",
        "validation_checklist",
    ):
        if key == "direction_frame":
            incoming_frame = supplement_context.get(key) if isinstance(supplement_context.get(key), dict) else {}
            if incoming_frame.get("directions"):
                merged[key] = incoming_frame
            continue
        existing = merged.get(key) if isinstance(merged.get(key), list) else []
        incoming = supplement_context.get(key) if isinstance(supplement_context.get(key), list) else []
        if incoming and key == "demand_scenarios":
            existing = [
                row for row in existing
                if not (isinstance(row, dict) and "report_contexts.json" in as_list(row.get("evidence")))
            ]
        if incoming and key == "direction_scan":
            existing = [
                row for row in existing
                if not (
                    isinstance(row, dict)
                    and (
                        row.get("mention_frequency") == "本地精读命中"
                        or str(row.get("direction") or "").strip() in generic_direction_labels
                        or is_generic_theme_info_segment(row.get("direction") or "")
                    )
                )
            ]
        if incoming and key == "progress_ranking":
            existing = [
                row for row in existing
                if not (
                    isinstance(row, dict)
                    and (
                        row.get("evidence_level") == "L1 curated research"
                        or str(row.get("direction") or "").strip() in generic_direction_labels
                        or is_generic_theme_info_segment(row.get("direction") or "")
                    )
                )
            ]
        if incoming and key == "validation_checklist":
            existing = [
                row for row in existing
                if not (isinstance(row, dict) and not row.get("direction") and not row.get("source"))
            ]
        merged[key] = incoming + existing
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
            lines.append(f"| {compact_text(row.get('claim',''), 120)} | {row.get('confidence','')} | {compact_text(row.get('source',''), 80)} |")
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
                f"| {row.get('segment','')} | {name} | {row.get('specificity','')} | {compact_text(row.get('source',''), 80)} | {theme_info_short(compact_text(row.get('claim'), 130), 110)} |"
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


def theme_supplement_pool_section(context: dict) -> str:
    pool = context.get("theme_supplement_pool", {}) if isinstance(context, dict) else {}
    if not isinstance(pool, dict) or not pool.get("enabled"):
        return "- 未接入 Theme Radar 补充数据池。"
    summary = pool.get("summary", {}) if isinstance(pool.get("summary"), dict) else {}
    table_counts = summary.get("table_counts", {}) if isinstance(summary.get("table_counts"), dict) else {}
    parts = [
        f"- 补充数据池：{summary.get('row_count', 0)} 条结构化记录；证据项 {summary.get('evidence_item_count', 0)} 条。",
        f"- 来源文件：{pool.get('source_file', '')}",
    ]
    missing = summary.get("missing_required_sections", []) if isinstance(summary.get("missing_required_sections"), list) else []
    if missing:
        parts.append(f"- P0 缺失：{', '.join(str(x) for x in missing)}")
    if table_counts:
        parts.append("- 表覆盖：" + "；".join(f"{k}={v}" for k, v in table_counts.items() if v))
    return "\n".join(parts)


def context_chain_items(context: dict, key: str, limit: int = 8) -> list[str]:
    if not isinstance(context, dict):
        return []
    chain = context.get("industry_chain_map", {})
    items = []
    if isinstance(chain, dict):
        for item in chain.get(key, []) or []:
            if isinstance(item, dict):
                items.append(str(item.get("name", "")).strip())
            else:
                items.append(str(item).strip())
    if not items:
        fallback_key = {
            "downstream": "downstream",
            "midstream": "midstream",
            "upstream_materials": "upstream",
            "upstream_equipment": "upstream",
        }.get(key, key)
        items = as_list(context.get(fallback_key))
    return unique([x for x in items if x])[:limit]


def direction_company_groups(companies: list[dict], profile: dict | None = None) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for company in companies or []:
        direction = company_direction_key(company, profile)
        groups.setdefault(direction, []).append(company)
    return {
        direction: sorted(rows, key=company_sort_key)
        for direction, rows in sorted(groups.items(), key=lambda item: direction_rank(item[0], profile))
    }


def direction_validation_focus(direction: str, label: str) -> str:
    if direction == "drug_pipeline":
        return "临床进展/获批节点/BD出海/商业化放量"
    if direction == "drug_platform":
        return "临床数据/授权交易/平台复用/新适应症"
    if direction in {"storage_product", "optical_module", "optical_chip", "pv_cell_module", "pv_inverter_storage", "core_product", "component_module"}:
        return "订单/客户认证/出货节奏/收入占比"
    if direction in {"materials", "pv_silicon"}:
        return "价格/产能/客户导入/国产替代进度"
    if direction == "equipment":
        return "招标/交付/验收/产线导入"
    if direction in {"package_test", "manufacturing"}:
        return "扩产/良率/封测订单/资本开支"
    if direction in {"service_platform", "downstream_channel"}:
        return "订单/在手项目/续费或商业化放量"
    return f"{label} 是否被公告、研报和复盘继续强化"


def inferred_bottleneck_for_direction(direction: str, label: str, context: dict) -> str:
    upstream_materials = "、".join(context_chain_items(context, "upstream_materials", 3))
    upstream_equipment = "、".join(context_chain_items(context, "upstream_equipment", 3))
    midstream = "、".join(context_chain_items(context, "midstream", 4))
    noisy_midstream = any(token in midstream for token in ("中研普华", "中商产业", "国家药品监督", "NMPA", "协会", "研究院"))
    if noisy_midstream:
        midstream = ""
    if direction == "drug_pipeline":
        return "临床数据、注册审批、BD出海与商业化兑现"
    if direction == "drug_platform":
        return "靶点机制、平台复用能力、临床数据和授权交易"
    if direction in {"storage_product", "optical_module", "optical_chip", "drug_pipeline", "pv_cell_module", "pv_inverter_storage"}:
        return compact_text(midstream or f"{label} 的产品迭代、供给和客户验证", 90)
    if direction in {"materials", "pv_silicon"}:
        return compact_text(upstream_materials or f"{label} 的供给、价格和认证约束", 90)
    if direction == "equipment":
        if "制药" in label or "生命科学" in label:
            return "制药装备、生物工艺装备的订单、交付和客户验证"
        if "光伏" in label:
            return "光伏设备的订单、交付、验收和新技术路线导入"
        return compact_text(upstream_equipment or f"{label} 的交付、验证和产线导入", 90)
    if direction in {"package_test", "manufacturing"}:
        return compact_text(midstream or f"{label} 的产能、良率和工艺验证", 90)
    return compact_text(f"{label} 的公司级产品、客户或订单验证", 90)


def inferred_demand_source(context: dict) -> str:
    drivers = []
    drivers.extend(as_list(context.get("demand_drivers")) if isinstance(context, dict) else [])
    drivers.extend(context_chain_items(context, "downstream", 8))
    return "、".join(unique(drivers)[:4]) or "下游需求待补"


def inferred_demand_bottleneck_rows(context: dict, companies: list[dict], profile: dict | None = None) -> list[dict]:
    rows = []
    groups = direction_company_groups(companies, profile)
    demand_source = inferred_demand_source(context)
    for direction, direction_companies in groups.items():
        if direction in {"weak_watch", "unknown"}:
            continue
        label = direction_label(direction, profile)
        reps = unique([company.get("name", "") for company in direction_companies if company.get("name")])[:4]
        if not reps:
            continue
        rows.append(
            {
                "demand_source": demand_source,
                "bottleneck": inferred_bottleneck_for_direction(direction, label, context),
                "chain_links": [label],
                "beneficiary_entities": reps,
                "evidence": f"方向内公司 {len(direction_companies)} 家；头部样本 {len(reps)} 家",
                "verification_items": [direction_validation_focus(direction, label)],
            }
        )
    return rows[:10]


def demand_bottleneck_map_section(context: dict, companies: list[dict] | None = None, profile: dict | None = None) -> str:
    rows = context.get("demand_bottleneck_map", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        rows = inferred_demand_bottleneck_rows(context if isinstance(context, dict) else {}, companies or [], profile)
    if not rows:
        return "- 待补：需要方向池生成 demand_bottleneck_map，或先补公司方向分组。"
    lines = [
        "| 需求来源 | 瓶颈/约束 | 传导到的环节 | 代表公司 | 证据画像 | 下一步验证 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows[:18]:
        if not isinstance(row, dict):
            continue
        evidence_profile = row.get("evidence_profile", {}) if isinstance(row.get("evidence_profile"), dict) else {}
        evidence = row.get("evidence") or direction_pool_evidence_label(evidence_profile)
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


def compact_chain_panorama_section(context: dict, companies: list[dict] | None = None, profile: dict | None = None) -> str:
    groups = direction_company_groups(companies or [], profile)
    if not groups:
        return ""
    downstream = "、".join(context_chain_items(context, "downstream", 4)) or "下游需求待补"
    midstream = "、".join(context_chain_items(context, "midstream", 4)) or "中游工艺待补"
    upstream_equipment = "、".join(context_chain_items(context, "upstream_equipment", 3)) or "设备待补"
    upstream_materials = "、".join(context_chain_items(context, "upstream_materials", 3)) or "材料待补"
    lines = [
        "### 压缩全景表",
        "",
        "| 下游需求 | 中游核心/工艺 | 上游设备 | 上游材料 | 方向 | 代表公司 | 验证点 |",
        "|---|---|---|---|---|---|---|",
    ]
    for direction, rows in groups.items():
        if direction in {"weak_watch", "unknown"}:
            continue
        label = direction_label(direction, profile)
        reps = "、".join(unique([company.get("name", "") for company in rows if company.get("name")])[:4]) or "待补"
        lines.append(
            f"| {compact_text(downstream, 110)} | {compact_text(midstream, 110)} | {compact_text(upstream_equipment, 90)} | {compact_text(upstream_materials, 90)} | {label} | {reps} | {direction_validation_focus(direction, label)} |"
        )
    return "\n".join(lines)


def industry_chain_map_section(context: dict, companies: list[dict] | None = None, profile: dict | None = None) -> str:
    chain = context.get("industry_chain_map", {}) if isinstance(context, dict) else {}
    if not isinstance(chain, dict) or not chain:
        upstream = as_list(context.get("upstream")) if isinstance(context, dict) else []
        midstream = as_list(context.get("midstream")) if isinstance(context, dict) else []
        downstream = as_list(context.get("downstream")) if isinstance(context, dict) else []
        if not any([upstream, midstream, downstream]):
            panorama = compact_chain_panorama_section(context if isinstance(context, dict) else {}, companies, profile)
            return panorama or "- 待补：需要把方向放进上游材料/设备、中游制造、下游需求。"
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
    lines = []
    panorama = compact_chain_panorama_section(context if isinstance(context, dict) else {}, companies, profile)
    if panorama:
        lines.extend([panorama, "", "### 原始产业链字段", ""])
    lines.extend(["| 层级 | 条目 | 证据类型 |", "|---|---|---|"])
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
    haystack = " ".join(
        [
            str(source_name or ""),
            str(ctx.get("concept", "")),
            " ".join(str(x) for x in ctx.get("related_concepts", []) or []),
            json.dumps(ctx.get("supply_chain", {}), ensure_ascii=False),
            " ".join(str(ev.get("text", "")) for ev in (ctx.get("evidence", []) or []) if isinstance(ev, dict)),
        ]
    ).lower()
    if "黄金" in query:
        gold_context_tokens = (
            "金价",
            "金矿",
            "矿产金",
            "央行购金",
            "黄金储备",
            "黄金etf",
            "黄金股",
            "金饰",
            "金条",
            "金币",
            "贵金属",
            "comex",
            "lbma",
            "上海金",
            "au9999",
            "伦敦金",
            "实际利率",
            "美元指数",
            "美联储",
            "避险",
        )
        return not any(token in haystack for token in gold_context_tokens)
    if "创新药" not in query:
        return False
    explicit_rwa = any(token in query for token in ("rwa", "真实世界资产", "区块链", "web3", "数字资产"))
    if explicit_rwa:
        return False
    off_topic_tokens = ("rwa", "真实世界资产", "区块链", "web3", "数字资产", "kucoin", "交易所")
    return any(token in haystack for token in off_topic_tokens)


def filtered_report_context_values(values: list[str], term: str = "") -> list[str]:
    noise_tokens = (
        "生态",
        "国产化率",
        "应用场景",
        "产业链",
        "中游制造层",
        "下游应用层",
        "主战场",
    )
    term_text = str(term or "")
    off_topic_tokens = []
    if not any(token in term_text for token in ("光伏", "太阳能", "电池")):
        off_topic_tokens.extend(["TOPCon", "HJT", "PERC", "钙钛矿", "光伏电池", "太阳能电池"])
    if "3D打印" not in term_text:
        off_topic_tokens.append("3D打印钛合金")
    if "通信" not in term_text and "6G" not in term_text:
        off_topic_tokens.append("6G产业")
    if not any(token in term_text for token in ("光伏", "硅片", "硅料", "电池")):
        off_topic_tokens.append("210尺寸")
    out = []
    for value in values:
        text = str(value or "").strip()
        if len(text) < 3:
            continue
        if text in noise_tokens:
            continue
        if any(token == text for token in noise_tokens):
            continue
        if any(token in text for token in off_topic_tokens):
            continue
        out.append(text)
    return out[:8]


def report_contexts_section(rows: list[dict], term: str = "") -> str:
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
            values = filtered_report_context_values([str(v) for v in chain.get(key, []) if str(v).strip()], term)
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
    lines = ["| 需求场景 | 下游驱动 | 传导逻辑 | 工艺要求 | 受益环节 | 代表公司 | 下一步验证 | 证据 |", "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('scenario','')} | {row.get('downstream_driver','')} | {row.get('transmission_logic') or row.get('logic','')} | {row.get('process_requirement','')} | {'、'.join(as_list(row.get('beneficiary_links')))} | {'、'.join(as_list(row.get('representative_entities')))} | {row.get('next_validation','')} | {theme_info_short(compact_text(row.get('evidence_summary') or '；'.join(as_list(row.get('evidence'))), 120), 100)} |"
        )
    return "\n".join(lines)


def material_process_scan_section(context: dict) -> str:
    rows = context.get("material_process_scan", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要补充工艺/材料/零部件扫描表。"
    lines = [
        "| 一级方向 | 二级细分 | 三级归类/环节 | 细分标签 | 代表公司 | 可检索验证项 | 产业进程影响权重 | 备注 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {display_label(row.get('major_track',''), context)} | {display_label(row.get('name',''), context)} | {display_label(row.get('chain_position',''), context)} | {display_label(row.get('classification',''), context)} | {'、'.join(as_list(row.get('representative_entities')))} | {theme_info_short(row.get('next_validation') or row.get('core_catalyst',''), 80)} |  | {theme_info_short(row.get('prosperity_judgment',''), 70)} |"
        )
    return "\n".join(lines)


def industry_chain_panorama_section(context: dict, companies: list[dict] | None = None, profile: dict | None = None) -> str:
    rows = context.get("industry_chain_panorama", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return industry_chain_map_section(context, companies, profile)
    lines = []
    panorama = compact_chain_panorama_section(context if isinstance(context, dict) else {}, companies, profile)
    if panorama:
        lines.extend([panorama, "", "### 补充池产业链明细", ""])
    lines.extend(["| 层级 | 环节 | 关键要素 | 代表公司 | 市场空间/价值量/产能 | 供需状态 | 产业逻辑 |", "|---|---|---|---|---|---|---|"])
    for row in rows:
        if not isinstance(row, dict):
            continue
        segment = str(row.get("segment") or "").strip()
        if is_generic_theme_info_segment(segment):
            continue
        lines.append(
            f"| {row.get('layer','')} | {row.get('segment','')} | {'、'.join(as_list(row.get('key_elements')))} | {'、'.join(as_list(row.get('representative_entities')))} | {theme_info_short(compact_text(row.get('market_value_capacity',''), 90), 70)} | {row.get('supply_demand_status','')} | {theme_info_short(compact_text(row.get('industry_logic',''), 120), 100)} |"
        )
    return "\n".join(lines)


def direction_scan_section(context: dict) -> str:
    rows = context.get("direction_scan", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要从主题向下扫描工艺、材料、设备、应用等细分方向。"
    lines = [
        "| 一级方向 | 二级细分 | 三级归类/环节 | 细分标签 | 候选公司 | 可检索验证项 | 产业进程影响权重 | 备注 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        hierarchy = row.get("sector_hierarchy", {}) if isinstance(row.get("sector_hierarchy"), dict) else {}
        level_1 = hierarchy.get("level_1") or row.get("sector", "")
        level_2 = hierarchy.get("level_2") or row.get("primary_sector") or row.get("sector", "")
        level_3 = hierarchy.get("level_3") or ""
        lines.append(
            "| {level_1} | {direction} | {level_3} | {classification} | {companies} | {core_catalyst} |  | {note} |".format(
                direction=display_label(row.get("direction", ""), context),
                level_1=display_label(level_1, context),
                level_3=display_label(level_3, context),
                classification=display_label(row.get("classification", "待补"), context),
                core_catalyst=row.get("core_catalyst", ""),
                companies="、".join(as_list(row.get("candidate_companies"))),
                note=display_label(level_2, context),
            )
        )
    return "\n".join(lines)


def evidence_bucket_count_summary(companies: list[dict]) -> str:
    counts = {key: 0 for key in EVIDENCE_BUCKETS}
    for company in companies:
        buckets = company.get("evidence_buckets", {}) or {}
        for key in EVIDENCE_BUCKETS:
            if buckets.get(key):
                counts[key] += 1
    parts = []
    labels = {
        "baseline": "baseline",
        "curated_research": "精读",
        "delta": "复盘",
        "graph_only": "图谱",
        "missing": "待补",
    }
    for key in EVIDENCE_BUCKETS:
        if counts[key]:
            parts.append(f"{labels[key]}{counts[key]}")
    return "、".join(parts) or "待补"


def direction_qc_gap_summary(companies: list[dict]) -> str:
    gap_specs = [
        ("weak_granularity", "弱颗粒度"),
        ("soft_fact_hardness", "软事实"),
        ("chain_layer_conflict", "链层冲突"),
        ("possible_overranked", "疑似高估"),
        ("graph_only_only", "仅图谱"),
        ("missing_evidence", "缺证据"),
    ]
    parts = []
    for flag, label in gap_specs:
        count = sum(1 for company in companies if flag in company_qc_flags(company))
        if count:
            parts.append(f"{label}{count}")
    return "、".join(parts[:4]) or "暂无明显缺口"


def direction_stage_label(companies: list[dict]) -> str:
    total = len(companies)
    if total == 0:
        return "待补"
    delta = len(company_bucket_hits(companies, "delta"))
    curated = len(company_bucket_hits(companies, "curated_research"))
    baseline = len(company_bucket_hits(companies, "baseline"))
    graph = len(company_bucket_hits(companies, "graph_only"))
    if delta >= 3 and curated >= 2:
        return "催化共振"
    if delta >= 1 and curated >= 1:
        return "第一轮发酵"
    if curated >= 2:
        return "产业线索"
    if baseline >= max(2, total // 2):
        return "基础验证"
    if graph >= max(1, total // 2):
        return "观察池"
    return "待补证"


def direction_opportunity_class(direction: str, companies: list[dict], profile: dict | None = None) -> str:
    stage = direction_stage_label(companies)
    if direction in {"weak_watch", "unknown"}:
        return "观察"
    if stage in {"催化共振", "第一轮发酵"}:
        return "发酵"
    if direction in {"materials", "equipment", "package_test", "pv_silicon", "drug_platform"}:
        return "布局"
    if stage == "产业线索":
        return "布局"
    return "补证"


def profile_subdirection_allowed(value: str, profile: dict | None = None) -> bool:
    tokens = tuple((profile or {}).get("subdirection_tokens", ()) or ())
    if not tokens:
        return True
    text = str(value or "")
    return any(token and token in text for token in tokens)


def direction_subdirection_allowed(value: str, direction: str, profile: dict | None = None) -> bool:
    text = str(value or "")
    direction_tokens = DIRECTION_SUBDIRECTION_TOKENS.get(direction, ())
    if direction_tokens:
        return any(token and token in text for token in direction_tokens)
    return profile_subdirection_allowed(value, profile)


def direction_subdirection_summary(companies: list[dict], direction: str = "", profile: dict | None = None, limit: int = 5) -> str:
    values = []
    for company in companies:
        values.extend(company_subdirections(company))
    cleaned = [
        str(value)
        for value in values
        if value and not str(value).startswith("待判定") and "待细分" not in str(value)
    ]
    preferred = [value for value in cleaned if direction_subdirection_allowed(value, direction, profile)]
    if (profile or {}).get("subdirection_tokens"):
        return "、".join(unique(preferred)[:limit]) or "待细分"
    return "、".join(unique(cleaned)[:limit]) or "待细分"


def direction_primary_catalyst(direction: str, label: str, companies: list[dict]) -> str:
    if direction in {"storage_product", "optical_module", "optical_chip", "pv_cell_module", "pv_inverter_storage"}:
        return "订单/客户认证/出货或价格信号"
    if direction == "drug_pipeline":
        return "临床数据/获批/BD出海"
    if direction == "drug_platform":
        return "平台复用/授权交易/新适应症"
    if direction in {"materials", "pv_silicon"}:
        return "价格/产能/国产替代/客户导入"
    if direction == "equipment":
        return "招标/交付/验收/产线导入"
    if direction in {"package_test", "manufacturing"}:
        return "扩产/良率/资本开支/封测订单"
    return direction_validation_focus(direction, label)


def direction_radar_matrix_section(context: dict, companies: list[dict], profile: dict | None = None) -> str:
    groups = direction_company_groups(companies, profile)
    if not groups:
        return "- 待补：需要先形成公司方向分组。"
    lines = [
        "### 题材地图检索表",
        "",
        "| 一级方向 | 二级细分归类 | 公司归类 | 代表公司 | 公司数 | 可检索验证项 | 证据来源类型 | 产业进程影响权重 | 备注 |",
        "|---|---|---|---|---:|---|---|---|---|",
    ]
    for direction, rows in groups.items():
        if direction in {"weak_watch", "unknown"}:
            continue
        label = direction_label(direction, profile)
        top_names = "、".join(unique([company.get("name", "") for company in rows if company.get("name")])[:4]) or "待补"
        lines.append(
            "| {label} | {subdirs} | {dtype} | {top_names} | {count} | {validation} | {evidence} |  | {gaps} |".format(
                label=label,
                dtype=SUBTYPE_LABELS.get(rows[0].get("company_subtype") or company_subtype(rows[0]), "方向聚合") if rows else "方向聚合",
                subdirs=direction_subdirection_summary(rows, direction, profile),
                count=len(rows),
                top_names=top_names,
                evidence=evidence_bucket_count_summary(rows),
                validation=direction_validation_focus(direction, label),
                gaps=direction_qc_gap_summary(rows),
            )
        )
    return "\n".join(lines)


def context_direction_terms(context: dict, profile: dict | None = None, limit: int = 12) -> list[str]:
    rows = context.get("direction_scan", []) if isinstance(context, dict) else []
    values = []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                values.append(str(row.get("direction") or row.get("name") or "").strip())
    rows = context.get("material_process_scan", []) if isinstance(context, dict) else []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                values.append(str(row.get("name") or row.get("direction") or "").strip())
    filtered = [value for value in unique(values) if value and profile_subdirection_allowed(value, profile)]
    return filtered[:limit]


def inferred_material_process_scan_section(context: dict, companies: list[dict], profile: dict | None = None) -> str:
    rows = context.get("material_process_scan", []) if isinstance(context, dict) else []
    if isinstance(rows, list) and rows:
        return material_process_scan_section(context)
    items = []
    seen = set()
    groups = direction_company_groups(companies, profile)
    for company in sorted(companies or [], key=company_sort_key):
        direction = company_direction_key(company, profile)
        if direction in {"weak_watch", "unknown"}:
            continue
        for subdir in company_subdirections(company):
            if not subdir or subdir.startswith("待判定") or "待细分" in subdir or subdir in seen:
                continue
            if not direction_subdirection_allowed(subdir, direction, profile):
                continue
            seen.add(subdir)
            label = direction_label(direction, profile)
            direction_rows = groups.get(direction, [])
            items.append(
                {
                    "subdir": subdir,
                    "direction": label,
                    "stage": direction_stage_label(direction_rows),
                    "category": direction_opportunity_class(direction, direction_rows, profile),
                    "company": company.get("name", ""),
                    "evidence": evidence_bucket_summary(company),
                    "validation": company_validation_focus(company),
                }
            )
            break
    if not items:
        terms = context_direction_terms(context, profile)
        if not terms:
            return "- 待补：需要补充工艺/材料/零部件扫描表。"
        lines = [
            "| 一级方向 | 二级细分 | 三级归类/环节 | 代表公司 | 可检索验证项 | 产业进程影响权重 | 备注 |",
            "|---|---|---|---|---|---|---|",
        ]
        for term in terms[:10]:
            lines.append(f"| 精读/方向池线索 | {term} | 产业线索 | 待补 | 后续映射到公司级产品、工艺、客户或订单 |  | report_context/direction_scan |")
        return "\n".join(lines)
    lines = [
        "| 一级方向 | 二级细分 | 三级归类/环节 | 代表公司 | 可检索验证项 | 产业进程影响权重 | 备注 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in items[:12]:
        lines.append(
            f"| {item['direction']} | {item['subdir']} | {item['category']} | {item['company']} | {compact_text(item['validation'], 90)} |  | {item['evidence']} |"
        )
    return "\n".join(lines)


def direction_tracking_window(direction: str, signal: str) -> str:
    text = f"{direction} {signal}"
    if any(token in text for token in ("临床", "获批", "BD", "授权")):
        return "下一临床/审评/BD窗口"
    if any(token in text for token in ("价格", "库存", "价差")):
        return "周度/月度价格与库存窗口"
    if any(token in text for token in ("招标", "交付", "验收")):
        return "下一招标/交付/验收窗口"
    if any(token in text for token in ("扩产", "良率", "资本开支", "产能")):
        return "月度产能/良率/资本开支窗口"
    if any(token in text for token in ("客户", "认证", "出货", "订单", "收入占比")):
        return "月度订单/客户认证/出货窗口"
    return "未来1-3个月验证窗口"


def direction_specific_watch_item(label: str, signal: str, top_names: str) -> str:
    text = f"{label} {signal}"
    items = []
    if "价格" in text:
        items.append(f"{label} ASP/现货价/合约价是否上行，并能否传导到毛利率")
    if "客户" in text or "认证" in text:
        items.append(f"{top_names} 是否披露头部客户认证、导入、定点或供应份额")
    if "订单" in text or "出货" in text:
        items.append(f"{top_names} 是否出现带金额、数量、交付周期或收入占比的订单/出货证据")
    if "扩产" in text or "产能" in text or "良率" in text:
        items.append(f"{top_names} 的扩产、良率、稼动率或资本开支是否兑现")
    if "招标" in text or "交付" in text or "验收" in text:
        items.append(f"{top_names} 是否进入招标、中标、交付或验收节点")
    if "临床" in text or "获批" in text:
        items.append(f"{top_names} 是否出现临床数据、注册审批、适应症拓展或商业化放量")
    return "；".join(unique(items)[:3]) or f"{label} 是否出现公司级产品、客户、订单、产能或认证证据"


def direction_upgrade_condition(label: str, signal: str, top_names: str) -> str:
    watch = direction_specific_watch_item(label, signal, top_names)
    return f"{watch}，且至少有一条来自公告/年报/官网/招股书/官方文件或多源研报交叉验证。"


def direction_downgrade_condition(label: str, gaps: str) -> str:
    if gaps and gaps != "暂无明显缺口":
        return f"{gaps} 持续存在，或两轮验证窗口仍无法落到公司级硬事实。"
    return f"{label} 只停留在图谱/概念/下游需求映射，缺少订单、客户、价格、产能或收入占比验证。"


def inferred_direction_tracking_rows(context: dict, companies: list[dict], profile: dict | None = None, limit: int = 6) -> list[dict]:
    groups = direction_company_groups(companies, profile)
    ranked = []
    for direction, rows in groups.items():
        if direction in {"weak_watch", "unknown"}:
            continue
        label = direction_label(direction, profile)
        score = direction_progress_score(direction, rows)
        ranked.append((score, direction, label, rows))
    output = []
    for score, direction, label, rows in sorted(ranked, reverse=True)[:limit]:
        stage = direction_stage_label(rows)
        signal = direction_primary_catalyst(direction, label, rows)
        evidence = evidence_bucket_count_summary(rows)
        top_names = "、".join(unique([company.get("name", "") for company in rows if company.get("name")])[:4]) or "代表公司待补"
        gaps = direction_qc_gap_summary(rows)
        window = direction_tracking_window(direction, signal)
        watch = direction_specific_watch_item(label, signal, top_names)
        upgrade = direction_upgrade_condition(label, signal, top_names)
        downgrade = direction_downgrade_condition(label, gaps)
        output.append({
            "direction": label,
            "time": "当前已发生",
            "event": f"{label} 已进入{stage}：{evidence}",
            "event_type": "已发生催化/证据沉淀",
            "evidence": f"方向评分 {score}；代表公司：{top_names}",
            "watch_item": watch,
            "upgrade_condition": upgrade,
            "downgrade_condition": downgrade,
        })
        output.append({
            "direction": label,
            "time": window,
            "event": f"验证 {signal} 是否落到 {top_names}",
            "event_type": "未来验证窗口",
            "evidence": "自动推导自方向矩阵、公司证据桶和 QC 缺口",
            "watch_item": watch,
            "upgrade_condition": upgrade,
            "downgrade_condition": downgrade,
        })
    return output


def inferred_validation_rows(context: dict, companies: list[dict], profile: dict | None = None, limit: int = 8) -> list[dict]:
    rows = []
    for item in inferred_direction_tracking_rows(context, companies, profile, limit):
        if item.get("event_type") != "未来验证窗口":
            continue
        rows.append({
            "direction": item.get("direction", ""),
            "item": item.get("watch_item", ""),
            "window": item.get("time", ""),
            "upgrade_condition": item.get("upgrade_condition", ""),
            "downgrade_condition": item.get("downgrade_condition", ""),
            "status": "自动推导｜待外部证据确认",
            "evidence": item.get("evidence", ""),
        })
    return rows


def validation_rows_are_weak(rows: list[dict]) -> bool:
    checked = [row for row in rows if isinstance(row, dict)]
    if not checked:
        return True
    directional = sum(1 for row in checked if str(row.get("direction") or "").strip())
    actionable = sum(1 for row in checked if str(row.get("upgrade_condition") or row.get("downgrade_condition") or "").strip())
    return directional < max(2, len(checked) // 2) or actionable < max(2, len(checked) // 3)


def catalyst_calendar_section(context: dict, companies: list[dict] | None = None, profile: dict | None = None) -> str:
    rows = context.get("catalyst_calendar", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        rows = inferred_direction_tracking_rows(context if isinstance(context, dict) else {}, companies or [], profile)
    if not rows:
        return "- 待补：需要把后续验证点拆成时间、事件和观察项。"
    lines = ["| 方向 | 时间/窗口 | 催化/验证事件 | 类型 | 当前证据 | 下一步观察 | 升级条件 | 降级条件 |", "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(f"| {compact_text(row.get('direction',''), 80)} | {compact_text(row.get('time') or row.get('time_window',''), 40)} | {compact_text(row.get('event',''), 120)} | {compact_text(row.get('event_type',''), 60)} | {compact_text(row.get('evidence') or row.get('evidence_summary',''), 120)} | {compact_text(row.get('watch_item') or row.get('next_watch',''), 120)} | {compact_text(row.get('upgrade_condition',''), 120)} | {compact_text(row.get('downgrade_condition',''), 120)} |")
    return "\n".join(lines)


def validation_checklist_section(context: dict, companies: list[dict] | None = None, profile: dict | None = None) -> str:
    rows = context.get("validation_checklist", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        rows = inferred_validation_rows(context if isinstance(context, dict) else {}, companies or [], profile)
    elif validation_rows_are_weak(rows):
        inferred = inferred_validation_rows(context if isinstance(context, dict) else {}, companies or [], profile)
        if inferred:
            rows = inferred
    if not rows:
        return "- 待补：需要列出订单、价格、客户认证、量产、收入占比等验证事项。"
    lines = ["| 方向 | 验证事项 | 窗口 | 升级条件 | 降级条件 | 当前状态 | 证据依据 |", "|---|---|---|---|---|---|---|"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(f"| {compact_text(row.get('direction',''), 80)} | {compact_text(row.get('item') or row.get('validation_item',''), 120)} | {compact_text(row.get('window') or row.get('time_window',''), 40)} | {compact_text(row.get('upgrade_condition') or row.get('why',''), 120)} | {compact_text(row.get('downgrade_condition',''), 120)} | {compact_text(row.get('status','待验证'), 120)} | {compact_text(row.get('evidence') or row.get('evidence_summary',''), 120)} |")
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
        "| 序号 | 方向 | 阶段 | Tier | 评分 | 阶段理由 | 证据等级 | 关键信号 | 升级触发 | 降级风险 | 下一验证 | 优先级 |",
        "|---:|---|---|---|---:|---|---|---|---|---|---|---|",
    ]
    for idx, row in enumerate(rows, 1):
        lines.append(
            "| {idx} | {direction} | {stage} | {tier} | {progress_score} | {stage_reason} | {evidence_level} | {key_signal} | {upgrade_triggers} | {downgrade_risks} | {next_validation} | {priority} |".format(
                idx=idx,
                direction=display_label(row.get("direction", ""), context),
                stage=display_label(row.get("stage", "待补"), context),
                tier=display_label(row.get("tier", ""), context),
                evidence_level=row.get("evidence_level", "待补"),
                progress_score=row.get("progress_score", ""),
                stage_reason=row.get("stage_reason", ""),
                key_signal=row.get("key_signal", ""),
                upgrade_triggers=row.get("upgrade_triggers", ""),
                downgrade_risks=row.get("downgrade_risks", ""),
                next_validation=row.get("next_validation", ""),
                priority=display_label(row.get("priority", "待补"), context),
            )
        )
    return "\n".join(lines)


def direction_progress_score(direction: str, companies: list[dict]) -> int:
    if not companies:
        return 0
    stage_scores = {
        "催化共振": 82,
        "第一轮发酵": 68,
        "产业线索": 56,
        "基础验证": 44,
        "观察池": 30,
        "待补证": 24,
        "待补": 10,
    }
    score = stage_scores.get(direction_stage_label(companies), 30)
    score += min(8, len(company_bucket_hits(companies, "delta")) * 2)
    score += min(8, len(company_bucket_hits(companies, "curated_research")))
    score += min(5, len(company_bucket_hits(companies, "baseline")) // 2)
    score -= min(8, sum(1 for company in companies if "weak_granularity" in company_qc_flags(company)))
    score -= min(6, sum(1 for company in companies if "soft_fact_hardness" in company_qc_flags(company)))
    score -= min(5, sum(1 for company in companies if "graph_only_only" in company_qc_flags(company)))
    if direction in {"weak_watch", "unknown"}:
        score = min(score, 25)
    return max(0, min(100, score))


def direction_progress_tier(score: int, stage: str) -> str:
    if score >= 80:
        return "Tier 1"
    if score >= 60:
        return "Tier 2"
    if score >= 40:
        return "Tier 3"
    return "Watch"


def direction_progress_priority(score: int, gaps: str) -> str:
    if score >= 80 and "暂无明显缺口" in gaps:
        return "优先跟踪"
    if score >= 65:
        return "重点补证"
    if score >= 45:
        return "观察验证"
    return "降权观察"


def direction_progress_reason(direction: str, companies: list[dict]) -> str:
    stage = direction_stage_label(companies)
    evidence = evidence_bucket_count_summary(companies)
    gaps = direction_qc_gap_summary(companies)
    return f"{stage}；证据结构：{evidence}；缺口：{gaps}"


def direction_progress_ranking_section(context: dict, companies: list[dict], profile: dict | None = None) -> str:
    groups = direction_company_groups(companies, profile)
    rows = []
    for direction, direction_companies in groups.items():
        if direction in {"weak_watch", "unknown"}:
            continue
        label = direction_label(direction, profile)
        stage = direction_stage_label(direction_companies)
        score = direction_progress_score(direction, direction_companies)
        gaps = direction_qc_gap_summary(direction_companies)
        rows.append(
            {
                "direction": label,
                "stage": stage,
                "tier": direction_progress_tier(score, stage),
                "score": score,
                "reason": direction_progress_reason(direction, direction_companies),
                "evidence": evidence_bucket_count_summary(direction_companies),
                "signal": direction_primary_catalyst(direction, label, direction_companies),
                "upgrade": direction_validation_focus(direction, label),
                "downgrade": gaps if gaps != "暂无明显缺口" else "方向内头部公司失去复盘/精读支撑",
                "next": direction_validation_focus(direction, label),
                "priority": direction_progress_priority(score, gaps),
            }
        )
    if not rows:
        return progress_ranking_section(context)
    rows = sorted(rows, key=lambda row: row["score"], reverse=True)
    lines = [
        "| 序号 | 方向 | 阶段 | Tier | 评分 | 阶段理由 | 证据结构 | 关键信号 | 升级触发 | 降级风险 | 下一验证 | 优先级 |",
        "|---:|---|---|---|---:|---|---|---|---|---|---|---|",
    ]
    for idx, row in enumerate(rows, 1):
        lines.append(
            "| {idx} | {direction} | {stage} | {tier} | {score} | {reason} | {evidence} | {signal} | {upgrade} | {downgrade} | {next} | {priority} |".format(
                idx=idx,
                direction=row["direction"],
                stage=row["stage"],
                tier=row["tier"],
                score=row["score"],
                reason=compact_text(row["reason"], 100),
                evidence=row["evidence"],
                signal=row["signal"],
                upgrade=row["upgrade"],
                downgrade=compact_text(row["downgrade"], 80),
                next=row["next"],
                priority=row["priority"],
            )
        )
    original = progress_ranking_section(context)
    if not original.startswith("- 待补"):
        lines.extend(["", "### 原始方向池进度", "", original])
    return "\n".join(lines)


def opportunity_priorities_section(context: dict) -> str:
    rows = context.get("opportunity_priorities", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要把细分方向按研究跟踪优先级分层。"
    def score(row):
        try:
            return float(row.get("opportunity_score", 0))
        except Exception:
            return 0
    rows = sorted([r for r in rows if isinstance(r, dict)], key=score, reverse=True)
    lines = ["| 方向 | Tier | 跟踪优先级 | 机会评分 | 支撑证据 | 缺口 | 下一步动作 |", "|---|---|---|---:|---|---|---|"]
    for row in rows:
        lines.append(f"| {row.get('direction','')} | {row.get('tier','')} | {row.get('follow_up_priority','')} | {row.get('opportunity_score','')} | {row.get('supporting_evidence','')} | {row.get('missing_proof','')} | {row.get('next_actions','')} |")
    return "\n".join(lines)


def evidence_trace_section(context: dict) -> str:
    rows = context.get("evidence_trace", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要把方向结论映射到 item_id、来源和原文位置。"
    lines = [
        "| 方向 | 实体 | 证据摘要 | 证据层级 | 置信度 | 来源 | 日期 | item_id | 需复核 | 原文位置 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('direction','')} | {row.get('entity','')} | {theme_info_short(row.get('claim',''), 80)} | {row.get('evidence_level','')} | {row.get('confidence','')} | {row.get('source','')} | {row.get('source_date','')} | {row.get('item_id','')} | {row.get('needs_review','')} | {row.get('source_ref','')} |"
        )
    return "\n".join(lines)


def recognition_timeline_section(context: dict) -> str:
    rows = context.get("recognition_timeline", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要补充从暗流到一致认同的认知演变时间线。"
    lines = ["| 时间窗口 | 事件 | 认知阶段 | 认同度 | 事实等级 | 相关方向 | 相关公司 | 证据 |", "|---|---|---|---:|---|---|---|---|"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        time_window = compact_text(row.get("time_window", ""), 40)
        event = theme_info_short(compact_text(row.get("event", ""), 120), 90)
        recognition_stage = compact_text(row.get("recognition_stage", ""), 40)
        market_consensus = compact_text(row.get("market_consensus", ""), 30)
        fact_level = compact_text(row.get("fact_level", ""), 40)
        direction = compact_text(row.get("direction", ""), 80)
        related_entities = compact_text("、".join(as_list(row.get("related_entities"))), 80)
        evidence_summary = theme_info_short(compact_text(row.get("evidence_summary", ""), 120), 90)
        lines.append(
            f"| {time_window} | {event} | {recognition_stage} | {market_consensus} | {fact_level} | {direction} | {related_entities} | {evidence_summary} |"
        )
    return "\n".join(lines)


def progress_ruler_section(context: dict) -> str:
    rows = context.get("progress_ruler", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要补充相邻方向横向对比表，或由历史快照生成发酵进度标尺。"
    lines = ["| 方向 | 当前阶段 | 阶段位置 | 阶段理由 | 领先/落后 | 相关催化 | 下一步验证 |", "|---|---|---:|---|---|---|---|"]
    def stage_position(row: dict) -> int:
        value = row.get("stage_position", 0)
        try:
            return int(value)
        except Exception:
            return 0
    for row in sorted([r for r in rows if isinstance(r, dict)], key=stage_position, reverse=True):
        lines.append(
            f"| {row.get('direction','')} | {row.get('current_stage','')} | {row.get('stage_position','')} | {theme_info_short(row.get('stage_reason',''), 80)} | {row.get('relative_position','')} | {theme_info_short(row.get('related_catalyst',''), 70)} | {theme_info_short(row.get('next_validation',''), 70)} |"
        )
    return "\n".join(lines)


def action_plan_section(context: dict) -> str:
    rows = context.get("action_plan", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：需要补充最优先/次优先/观察方向的操作建议表。"
    priority_rank = {"最优先": 0, "次优先": 1, "观察": 2, "暂不跟": 3}
    rows = sorted([r for r in rows if isinstance(r, dict)], key=lambda x: priority_rank.get(str(x.get("priority_bucket") or ""), 9))
    lines = ["| 优先级 | 方向 | 核心逻辑 | 操作思路 | 等待条件 | 风险提示 |", "|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            f"| {compact_text(display_label(row.get('priority_bucket',''), context), 40)} | {compact_text(display_label(row.get('direction',''), context), 80)} | {theme_info_short(compact_text(row.get('core_logic',''), 120), 90)} | {theme_info_short(compact_text(row.get('action_thesis',''), 120), 90)} | {theme_info_short(compact_text(row.get('wait_for',''), 100), 80)} | {theme_info_short(compact_text(row.get('risk_warning',''), 100), 80)} |"
        )
    return "\n".join(lines)


def supplement_evidence_section(context: dict) -> str:
    rows = context.get("supplement_evidence_items", []) if isinstance(context, dict) else []
    if not isinstance(rows, list) or not rows:
        return "- 待补：补充数据池暂无独立证据项。"
    lines = ["| 模块 | 对象 | 证据 | 来源 | 日期 | 可信度 | 需复核 | item_id |", "|---|---|---|---|---|---|---|---|"]
    for row in rows[:40]:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('section_type','')} | {row.get('target','')} | {theme_info_short(compact_text(row.get('evidence',''), 120), 90)} | {compact_text(row.get('source',''), 80)} | {row.get('source_date','')} | {row.get('confidence','')} | {'是' if row.get('needs_review') else '否'} | {row.get('item_id','')} |"
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
    if has_ima_logic_card_source(company):
        basis.append("IMA个股逻辑卡")
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


def is_distribution_channel_company(company: dict) -> bool:
    subtype = company.get("company_subtype") or company_subtype(company)
    if subtype == "downstream_channel":
        return True
    text = evidence_text(company)
    return any(token in text for token in ("电子元器件分销", "分销商", "分销平台", "代理分销", "经销"))


def company_guardrail_note(company: dict) -> str:
    flags = [x for x in company_qc_flags(company) if x in ("weak_granularity", "review_required", "soft_fact_hardness", "chain_layer_conflict", "graph_only_only", "missing_evidence")]
    guardrails = [compact_text(x, 90) for x in company.get("guardrails", []) if str(x).strip()]
    if is_explicit_weak_company(company):
        return "弱相关护栏：仅作观察，不进入相对核心。"
    if guardrails:
        prefix = f"结构化护栏：{'；'.join(unique(guardrails)[:2])}"
        return f"{prefix}；数据标记：{'、'.join(flags)}" if flags else prefix
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
    has_ima_logic = has_ima_logic_card_source(company)
    if has_weak_granularity_signal(company) and company.get("strength") != "core" and not buckets.get("curated_research") and not has_ima_logic:
        return "weak"
    research_or_logic = bool(buckets.get("curated_research") or buckets.get("delta"))
    has_context = "full精读上下文提及" in basis
    has_baseline = bool(buckets.get("baseline"))
    consensus = source_consensus_count(company)
    subtype = company.get("company_subtype") or company_subtype(company)
    if has_baseline and not research_or_logic and not has_context and consensus == 0:
        return "weak"
    if is_distribution_channel_company(company):
        return "watch" if research_or_logic or has_baseline or has_context else "weak"
    if is_downstream_or_ecosystem_company(company) and company.get("strength") != "core":
        return "watch" if research_or_logic or has_baseline or has_context else "weak"
    if "weak_granularity" in flags and has_ima_logic and not buckets.get("curated_research") and not has_context and not has_baseline:
        return "related" if company.get("strength") == "core" else "watch"
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
    value = value.replace("券商研判", "第三方研判").replace("券商", "第三方机构")
    value = re.sub(r"[\u4e00-\u9fa5]{0,8}证券", "第三方机构", value)
    value = re.sub(r"[\u4e00-\u9fa5]{0,8}证券(研报|认为|电话会)", r"第三方\1", value)
    value = value.replace("风光核电", "风光等非煤电源").replace("核电", "非煤电源")
    return value[:limit] + ("…" if len(value) > limit else "")


def display_label(value: str, context=None) -> str:
    label = str(value or "").strip()
    if not label:
        return ""
    context_text = ""
    if isinstance(context, dict):
        context_text = " ".join(
            str(x)
            for x in (
                as_list(context.get("aliases"))
                + as_list(context.get("related_terms"))
                + as_list(context.get("capability_stack"))
                + as_list(context.get("definition"))
                + as_list((context.get("theme_supplement_pool") or {}).get("source_file") if isinstance(context.get("theme_supplement_pool"), dict) else "")
            )
        )
    if "人形机器人" in context_text or "具身智能" in context_text:
        replacements = {
            "材料": "轻量化材料",
            "电池": "机器人电池/电源管理",
            "设备": "机器人制造/检测设备",
        }
        return replacements.get(label, label)
    return label


def should_skip_structured_company_card(company: dict, term: str) -> bool:
    if not isinstance(company, dict):
        return True
    text = " ".join(
        str(x)
        for x in [
            company.get("name", ""),
            " ".join(company.get("roles", []) or []),
            " ".join(company.get("evidence", []) or []),
            " ".join(company_subdirections(company)),
        ]
    )
    subdirs = company_subdirections(company)
    pending_subdir = not subdirs or all("待判定" in str(x) or "待细分" in str(x) for x in subdirs)
    term_text = str(term or "")
    if "AI PCB" in term_text or "AIPCB" in term_text:
        contamination_tokens = ("人形机器人", "机器人", "Optimus", "火箭", "商业航天", "谐波减速器", "关节模组")
        if pending_subdir and any(token in text for token in contamination_tokens):
            return True
    return False


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


def split_display_chunks(text: str, separators: str = "；;、") -> list[str]:
    chunks = []
    current = []
    depth = 0
    pairs = {"（": "）", "(": ")", "【": "】", "[": "]"}
    closes = set(pairs.values())
    for char in str(text or ""):
        if char in pairs:
            depth += 1
        elif char in closes and depth > 0:
            depth -= 1
        if char in separators and depth == 0:
            value = "".join(current).strip()
            if value:
                chunks.append(value)
            current = []
        else:
            current.append(char)
    value = "".join(current).strip()
    if value:
        chunks.append(value)
    return chunks


def themed_company_roles(company: dict, term: str = "", limit: int = 2) -> str:
    roles = [str(x) for x in company.get("roles", []) or [] if str(x).strip()]
    if not roles:
        return "待补角色"
    chunks = []
    for role in roles:
        chunks.extend(split_display_chunks(role))
    if theme_compatible(term, "存储芯片"):
        storage_tokens = ("存储", "HBM", "DRAM", "NAND", "NOR", "DDR", "SSD", "封测", "封装", "测试", "半导体", "晶圆", "主控", "EEPROM", "芯片", "洁净室", "ASIC", "MCU")
        focused = [chunk for chunk in chunks if any(token in chunk for token in storage_tokens)]
        if focused:
            chunks = focused
    return compact_text("；".join(unique(chunks)[:limit]) or "待补角色", 160)


def company_logic_summary(company: dict, term: str = "") -> str:
    name = company.get("name", "")
    role = themed_company_roles(company, term)
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
    explicit = [compact_text(x, 100) for x in company.get("validation_focus", []) if str(x).strip()]
    if explicit:
        return "；".join(unique(explicit)[:3])
    subdirs = company_subdirections(company)
    checks = [capability_validation(label)[1] for label in subdirs if capability_rule_by_label(label)]
    if not checks:
        checks.append("后续研报/精选逻辑是否继续强化该公司与题材主线的直接关系")
    checks.append("复盘中观察逻辑卡、业务线和同环节公司是否继续强化")
    return "；".join(checks[:3])


def recent_ima_company_sort_key(company: dict) -> tuple:
    tier_rank = {"relative_core": 0, "related": 1, "watch": 2, "weak": 3}
    return (
        1 if is_distribution_channel_company(company) else 0,
        tier_rank.get(company_deep_dive_tier(company), 3),
        -confidence_score(company),
        company_sort_key(company),
    )


def recent_ima_logic_card_pool_section(companies: list[dict], limit: int = 20, term: str = "") -> str:
    rows = [
        c for c in companies
        if has_ima_logic_card_source(c)
        and company_deep_dive_tier(c) != "weak"
        and not should_skip_structured_company_card(c, term)
    ]
    rows = sorted(rows, key=recent_ima_company_sort_key)[:limit]
    if not rows:
        return "- 暂无近期 IMA 个股逻辑卡候选。"
    lines = [
        "| 公司 | 分层 | 置信度 | 公司类型 | 关联概念 | 产业链角色 | 来源 | 护栏 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    tier_labels = {"relative_core": "相对核心", "related": "重点相关", "watch": "观察/弹性", "weak": "弱相关"}
    for company in rows:
        tier = company_deep_dive_tier(company)
        confidence = "、".join(company.get("confidence", [])[:2]) or "待标注"
        subtype = SUBTYPE_LABELS.get(company.get("company_subtype") or company_subtype(company), "待判定")
        concepts = "、".join(company.get("concepts", [])[:4])
        roles = compact_text(themed_company_roles(company, term), 90)
        sources = compact_text("、".join([s for s in company.get("sources", []) if has_ima_logic_card_source_text(s)][:2]), 90)
        guardrail = "分销/生态侧，默认不提核心" if is_distribution_channel_company(company) else compact_text(company_guardrail_note(company), 80)
        lines.append(
            f"| {company.get('name','')} | {tier_labels.get(tier, tier)} | {confidence} | {subtype} | {concepts} | {roles} | {sources} | {guardrail} |"
        )
    return "\n".join(lines)


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


def deep_company_cards_section(companies: list[dict], tier: str, limit: int = 10, term: str = "", has_structured_supplement: bool = False) -> str:
    labels = {
        "relative_core": "相对核心",
        "related": "重点相关",
        "watch": "观察/弹性",
        "weak": "弱相关",
    }
    rows = [c for c in companies if company_deep_dive_tier(c) == tier]
    if has_structured_supplement:
        rows = [c for c in rows if not should_skip_structured_company_card(c, term)]
    rows = sorted(rows, key=company_sort_key)[:limit]
    if not rows:
        return "- 暂无。"
    parts = []
    for company in rows:
        roles = themed_company_roles(company, term)
        layers = "、".join(normalized_chain_layers(company)[:3]) or "unknown"
        sources = compact_text("、".join(source_basis(company)), 120)
        baseline = "支持/不冲突" if (company.get("evidence_buckets", {}) or {}).get("baseline") else "待补基础画像或仅作辅助"
        wiki_lines = []
        if company.get("wiki_one_liner"):
            freshness = f"（wiki 实体页，更新 {company.get('wiki_updated')}）" if company.get("wiki_updated") else "（wiki 实体页）"
            wiki_lines.append(f"- 一句话定位：{compact_text(company.get('wiki_one_liner'), 110)}{freshness}")
        if company.get("wiki_judgement"):
            wiki_lines.append(f"- wiki 当前判断：{compact_text(company.get('wiki_judgement'), 110)}")
        parts.append(
            "\n".join(
                [
                    f"### {company.get('name','')}（{labels.get(tier, tier)}）",
                ]
                + wiki_lines
                + [
                    f"- 细分方向：{compact_text('、'.join(company_subdirections(company)), 120)}",
                    f"- 逻辑强度：{company_logic_strength(company)}",
                    f"- 产业链角色：{roles}",
                    f"- 所属环节：{layers}；公司类型：{SUBTYPE_LABELS.get(company.get('company_subtype'), '待判定')}",
                    f"- 题材逻辑：{compact_text(company_logic_summary(company, term), 260)}",
                    f"- 来源依据：{sources}",
                    f"- baseline校验：{baseline}",
                    f"- 重点验证：{compact_text(company_validation_focus(company), 160)}",
                    f"- 护栏/验证：{compact_text(company_guardrail_note(company), 160)}",
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


def conclusion_direction_candidates(context: dict) -> list[dict]:
    direction_rows = context.get("direction_scan", []) if isinstance(context, dict) else []
    directions = [row for row in direction_rows if isinstance(row, dict) and row.get("direction")]
    material_rows = context.get("material_process_scan", []) if isinstance(context, dict) else []
    supplement_directions = []
    for row in material_rows if isinstance(material_rows, list) else []:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        prosperity = "；".join(
            x for x in [
                str(row.get("prosperity_judgment") or "").strip(),
                str(row.get("core_catalyst") or "").strip(),
            ] if x
        )
        supplement_directions.append({
            "direction": row.get("name", ""),
            "prosperity": prosperity,
            "core_catalyst": row.get("next_validation") or row.get("core_catalyst", ""),
            "classification": row.get("classification") or row.get("chain_position", ""),
            "recognition_level": row.get("cognition_level") or row.get("daily_review_frequency", ""),
            "candidate_companies": as_list(row.get("representative_entities")),
        })
    seen = set()
    merged = []
    for row in supplement_directions + directions:
        key = str(row.get("direction") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged


def deep_dive_conclusion(term: str, context: dict, companies: list[dict]) -> str:
    directions = conclusion_direction_candidates(context)
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


WIKI_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def read_wiki_page(path: Path, max_chars: int = 6000) -> tuple[dict, str]:
    """Read frontmatter metadata and body head of a wiki markdown page (read-only)."""
    try:
        text = path.read_text(encoding="utf-8")[:max_chars]
    except Exception:
        return {}, ""
    meta: dict[str, str] = {}
    body = text
    match = WIKI_FRONTMATTER_RE.match(text)
    if match:
        body = text[match.end():]
        for line in match.group(1).splitlines():
            if ":" not in line or line.startswith(" "):
                continue
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    return meta, body


def strip_wiki_links(text: str) -> str:
    return WIKI_LINK_RE.sub(r"\1", str(text or ""))


def squeeze_text(text: str, limit: int = 160) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def wiki_section_raw(body: str, names: tuple[str, ...]) -> str:
    for name in names:
        match = re.search(rf"^##+\s*{re.escape(name)}\s*$\n+(.+?)(?=\n##|\Z)", body, re.S | re.M)
        if match:
            return match.group(1)
    return ""


def load_wiki_concept_cards(vault: Path, names: list[str], limit: int = 8) -> list[dict]:
    """Read concept page digests from wiki/concepts for matched + related concepts."""
    cards: list[dict] = []
    seen = 0
    for name in unique([str(n).strip() for n in names if str(n).strip()]):
        if seen >= limit:
            break
        path = vault / "concepts" / f"{name}.md"
        if not path.exists():
            cards.append({"name": name, "missing": True})
            continue
        seen += 1
        meta, body = read_wiki_page(path)
        one_liner = ""
        match = re.search(r"\*\*一句话\*\*[:：]\s*(.+)", body)
        if match:
            one_liner = squeeze_text(strip_wiki_links(match.group(1)), 140)
        definition = ""
        match = re.search(r"^#\s+.+?$\n+(.+?)(?=\n\*\*|\n#)", body, re.S | re.M)
        if match:
            definition = squeeze_text(strip_wiki_links(match.group(1)), 140)
        core_logic = squeeze_text(strip_wiki_links(wiki_section_raw(body, ("核心逻辑", "核心机制", "炒作逻辑"))), 160)
        market = squeeze_text(strip_wiki_links(wiki_section_raw(body, ("市场", "产业链"))), 140)
        related = unique(WIKI_LINK_RE.findall(wiki_section_raw(body, ("相关概念",))))
        cards.append(
            {
                "name": name,
                "updated": meta.get("updated", ""),
                "revision": meta.get("revision", ""),
                "one_liner": one_liner,
                "definition": definition,
                "core_logic": core_logic,
                "market": market,
                "related": related[:10],
            }
        )
    return cards


def enrich_companies_with_wiki_pages(vault: Path, companies: list[dict], limit: int = 80) -> None:
    """Attach entity page one-liner positioning, judgement and freshness to companies."""
    ent_dir = vault / "entities"
    if not ent_dir.exists():
        return
    for company in sorted(companies, key=company_sort_key)[:limit]:
        name = str(company.get("name") or "").strip()
        if not name:
            continue
        path = ent_dir / f"{name}.md"
        if not path.exists():
            continue
        meta, body = read_wiki_page(path, 3000)
        match = re.search(r"一句话定位[:：]\s*(.+)", body)
        if not match:
            match = re.search(r"^#\s+.+?\n+([^#|\n-][^\n]*)", body, re.M)
        if match:
            one_liner = squeeze_text(strip_wiki_links(match.group(1)), 90)
            if one_liner and "待补" not in one_liner:
                company["wiki_one_liner"] = one_liner
        match = re.search(r"\|\s*当前判断\s*\|\s*([^|\n]+)\|", body)
        if match:
            company["wiki_judgement"] = squeeze_text(strip_wiki_links(match.group(1)), 90)
        if meta.get("updated"):
            company["wiki_updated"] = meta.get("updated")
        if meta.get("revision"):
            company["wiki_revision"] = meta.get("revision")


def is_junk_definition(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return True
    if len(value) <= 12 and "：" not in value:
        return True
    return any(token in value for token in ("关系表重建", "从既有", "待补一句话", "待从 full"))


def clean_synthesis_summary(raw: str, limit: int = 180) -> str:
    lines: list[str] = []
    for line in str(raw or "").splitlines():
        s = line.strip()
        if not s or s.startswith("|") or s.startswith("---"):
            continue
        s = re.sub(r"^#+\s*", "", s)
        s = re.sub(r"^>\s*", "", s)
        s = re.sub(r"^[-*]\s*", "", s)
        if re.match(r"^(信息日期|沉淀日期|生成日期|来源|关联节点|tags|title)[:：]", s):
            continue
        if s:
            lines.append(s)
        if len(" ".join(lines)) >= limit:
            break
    return squeeze_text(strip_wiki_links(" ".join(lines)), limit).replace("|", "/")


def load_synthesis_insights(vault: Path, term: str, scope_names: list[str], company_names: list[str], limit: int = 8) -> list[dict]:
    """Match wiki/synthesis research notes by theme/concept/company tokens in filename."""
    syn_dir = vault / "synthesis"
    if not syn_dir.exists():
        return []
    tokens = unique(
        [str(t).strip() for t in ([term] + list(scope_names or []) + list(company_names or [])) if str(t).strip() and len(str(t).strip()) >= 2]
    )
    hits = []
    for path in syn_dir.glob("*.md"):
        stem = path.stem
        matched = [t for t in tokens if t in stem]
        if not matched:
            continue
        date_match = re.search(r"(20\d{6})", stem)
        term_hit = 1 if (term and term in stem) else 0
        hits.append((term_hit, date_match.group(1) if date_match else "", path, matched))
    hits.sort(key=lambda item: (item[0], item[1], item[2].name), reverse=True)
    out = []
    for _term_hit, date_str, path, matched in hits[:limit]:
        meta, body = read_wiki_page(path, 4000)
        summary_raw = ""
        match = re.search(r"^#+ .*(?:核心结论|结论|一句话|定锚|核心判断).*$\n+(.+?)(?=\n#|\Z)", body, re.S | re.M)
        if match:
            summary_raw = match.group(1)
        else:
            match = re.search(r"^#\s+.+?\n+(.+?)(?=\n#|\Z)", body, re.S)
            summary_raw = match.group(1) if match else body
        summary = clean_synthesis_summary(summary_raw, 180)
        if not summary:
            summary = clean_synthesis_summary(body, 180)
        display_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if date_str else (meta.get("updated") or meta.get("created") or "")
        out.append(
            {
                "title": path.stem,
                "date": display_date,
                "matched": matched[:4],
                "summary": summary,
            }
        )
    return out


def wiki_concept_knowledge_section(state: dict) -> str:
    cards = state.get("wiki_concept_cards", []) or []
    present = [c for c in cards if not c.get("missing")]
    missing = [str(c.get("name")) for c in cards if c.get("missing")]
    if not present and not missing:
        return "- 未读取到 wiki 概念页。"
    lines: list[str] = []
    if present:
        lines.extend(["| 概念 | 更新 | 一句话定锚 | 核心逻辑 |", "|---|---|---|---|"])
        for card in present:
            anchor = card.get("one_liner") or card.get("definition") or "待补"
            lines.append(
                f"| {card.get('name','')} | {card.get('updated','')} | {compact_text(anchor, 130)} | {compact_text(card.get('core_logic') or '待补', 150)} |"
            )
        related = unique([r for card in present for r in card.get("related", []) or []])
        if related:
            lines.extend(["", f"- 概念页相关概念扩散：{'、'.join(related[:14])}"])
    if missing:
        lines.append(f"- 缺概念页（可考虑 concept-ingest 补齐）：{'、'.join(missing[:8])}")
    return "\n".join(lines)


def synthesis_insights_section(state: dict) -> str:
    rows = state.get("synthesis_insights", []) or []
    if not rows:
        return "- 暂无命中的本地合成研究（wiki/synthesis）。"
    lines = ["| 日期 | 合成研究 | 命中词 | 核心观点 |", "|---|---|---|---|"]
    for row in rows:
        lines.append(
            f"| {row.get('date','')} | {row.get('title','')} | {'、'.join(row.get('matched', []) or [])} | {compact_text(row.get('summary',''), 170)} |"
        )
    lines.extend(["", "- 合成研究为历史分析快照，仅作认知线索；结论需结合最新盘面与公告复核，不自动升级公司事实。"])
    return "\n".join(lines)


def radar_digest_section(state: dict) -> str:
    companies = state.get("companies", []) or []
    tiers = {"relative_core": 0, "related": 0, "watch": 0, "weak": 0}
    for company in companies:
        tier = company_deep_dive_tier(company)
        tiers[tier] = tiers.get(tier, 0) + 1
    card_count = sum(1 for c in companies if has_ima_logic_card_source(c))
    cards = state.get("wiki_concept_cards", []) or []
    present = [c for c in cards if not c.get("missing")]
    missing = [c for c in cards if c.get("missing")]
    synthesis = state.get("synthesis_insights", []) or []
    benchmarks = state.get("benchmark_matches", []) or []
    lines = [
        "| 维度 | 状态 |",
        "|---|---|",
        f"| 概念命中 | 主匹配 {state.get('primary') or '未入库'}；命中概念 {len(state.get('matches') or [])} 个；相关概念 {len(state.get('rels') or [])} 个 |",
        f"| 公司分层 | 相对核心 {tiers.get('relative_core', 0)} / 重点相关 {tiers.get('related', 0)} / 观察 {tiers.get('watch', 0)} / 弱相关 {tiers.get('weak', 0)} |",
        f"| 个股逻辑卡 | {card_count} 家公司带 IMA 逻辑卡 |",
        f"| wiki 概念页 | 已建 {len(present)} 个；缺页 {len(missing)} 个 |",
        f"| 合成研究 | 命中 {len(synthesis)} 篇（wiki/synthesis） |",
        f"| 海外对标 | 命中 {len(benchmarks)} 张 benchmark map |",
    ]
    dated = sorted(
        [c for c in companies if c.get("wiki_updated")],
        key=lambda c: str(c.get("wiki_updated")),
        reverse=True,
    )
    if dated:
        recent = "、".join(f"{c.get('name')}({c.get('wiki_updated')})" for c in dated[:5])
        lines.append(f"| 最近更新实体 | {recent} |")
        core_related = [c for c in dated if company_deep_dive_tier(c) in {"relative_core", "related"}]
        if len(core_related) > 3:
            oldest = "、".join(f"{c.get('name')}({c.get('wiki_updated')})" for c in core_related[-3:])
            lines.append(f"| 待刷新实体 | {oldest}（核心/相关层中最久未更新） |")
    return "\n".join(lines)


def build_theme_state(term: str, vault: Path, definition: str = "", context: dict | None = None, theme_info_rows: list[dict] | None = None, theme_direction_pool: dict | None = None, theme_supplement_pool: dict | None = None) -> dict:
    rel_dir = vault / "relations"
    graph = load_json(rel_dir / RELATION_FILES["concept_graph"], {"concepts": {}, "relations": []})
    exposures = load_json(rel_dir / RELATION_FILES["entity_exposures"], {"entities": {}})
    aliases = load_json(rel_dir / RELATION_FILES["aliases"], {"aliases": {}})
    evidence_index = load_json(rel_dir / RELATION_FILES["evidence_index"], {"items": []})
    theme_signals = load_json(rel_dir / RELATION_FILES["theme_signals"], {"version": 1, "themes": {}})
    pattern_library = load_json(rel_dir / RELATION_FILES["pattern_library"], {"version": 1, "patterns": {}})
    report_contexts = load_json(rel_dir / RELATION_FILES["report_contexts"], {"version": 1, "reports": {}})
    benchmark_maps = load_json(rel_dir / RELATION_FILES["benchmark_maps"], {"version": 1, "maps": []})
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
    supplement_pool_context = build_theme_supplement_pool_context(theme_supplement_pool or {})
    context = merge_theme_supplement_pool_context(context, supplement_pool_context)
    context = merge_theme_info_fine_components(context, term, theme_info_rows or [])
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
    direction_profile = theme_direction_profile(term, company_scope or all_scope or match_scope)
    companies = refresh_company_subtypes(companies, direction_profile)
    evidence = collect_evidence(company_scope or all_scope, companies, evidence_index)
    signal = load_signal(theme_signals, primary, matches)
    patterns = match_patterns(pattern_library, " ".join([term, external_search_text]), match_scope or [term])
    benchmark_query_text = " ".join(
        [
            term,
            primary,
            " ".join(matches or []),
            " ".join(rels or []),
            definition,
            context_search_text(context),
            context_company_text(context),
            " ".join(c.get("name", "") for c in companies if isinstance(c, dict)),
        ]
    )
    benchmark_matches = match_benchmark_maps(term, benchmark_maps, benchmark_query_text)
    has_structured_supplement = bool(theme_supplement_pool) and any(
        (theme_supplement_pool.get(key) or [])
        for key in (
            "definition_profile_rows",
            "demand_scenarios",
            "material_process_scan",
            "validation_items",
            "catalyst_calendar",
            "industry_chain_panorama",
            "recognition_timeline",
            "action_plan",
        )
    )
    display_report_contexts = [] if has_structured_supplement else local_report_contexts
    wiki_concept_cards = load_wiki_concept_cards(vault, (match_scope or [term]) + rels[:6])
    if not explicit_definition and is_junk_definition(definition):
        for card in wiki_concept_cards:
            anchor = card.get("one_liner") or card.get("definition") or ""
            if anchor:
                definition = anchor
                notes.append(f"定义回退：使用 wiki 概念页 [[{card.get('name')}]] 的一句话定锚。")
                break
    enrich_companies_with_wiki_pages(vault, companies)
    synthesis_insights = load_synthesis_insights(
        vault,
        term,
        (match_scope or []) + rels[:8],
        [c.get("name", "") for c in sorted(companies, key=company_sort_key)[:30]],
    )
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
        "display_report_contexts": display_report_contexts,
        "has_structured_supplement": has_structured_supplement,
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
        "theme_supplement_pool": theme_supplement_pool or {},
        "direction_profile": direction_profile,
        "benchmark_maps": benchmark_maps,
        "benchmark_matches": benchmark_matches,
        "benchmark_query_text": benchmark_query_text,
        "wiki_concept_cards": wiki_concept_cards,
        "synthesis_insights": synthesis_insights,
    }


def front_compact_text(text: str, limit: int = 90) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    if value.startswith("{") and value.endswith("}"):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, dict):
                value = "；".join(str(parsed.get(key, "")).strip() for key in ("concept", "role", "business_line", "evidence", "validation_focus", "guardrail") if str(parsed.get(key, "")).strip())
        except Exception:
            extracted = []
            for key in ("concept", "role", "business_line", "evidence", "validation_focus", "guardrail"):
                m = re.search(rf"['\"]{key}['\"]\s*:\s*['\"]([^'\"]+)['\"]", value)
                if m:
                    extracted.append(m.group(1))
            if extracted:
                value = "；".join(extracted)
    elif value.startswith("{"):
        extracted = []
        for key in ("concept", "role", "business_line", "evidence", "validation_focus", "guardrail"):
            m = re.search(rf"['\"]{key}['\"]\s*:\s*['\"]([^'\"]+)['\"]", value)
            if m:
                extracted.append(m.group(1))
        if extracted:
            value = "；".join(extracted)
    value = value.replace("", "")
    value = value.replace("券商研判", "第三方研判").replace("券商", "第三方机构")
    value = re.sub(r"[\u4e00-\u9fa5]{0,8}证券", "第三方机构", value)
    value = value.replace("公告订单业绩仅作验证空位", "后续看复盘、逻辑卡和业务数据是否继续强化")
    value = value.replace("公告订单业绩仅作后续验证空位", "复盘中观察逻辑卡、业务线和同环节公司是否继续强化")
    value = value.replace("复盘/逻辑卡/业务数据仅作后续验证空位", "复盘中观察逻辑卡、业务线和同环节公司是否继续强化")
    value = value.replace("公告订单业绩", "复盘/逻辑卡/业务数据")
    value = value.replace("公告、研报和复盘", "复盘、研报和逻辑卡")
    value = value.replace("公告、定报", "定报/业务数据")
    value = value.replace("后续研报/精选逻辑是否继续强化该公司与题材主线的直接关系；", "")
    value = value.replace("复盘中观察逻辑卡、业务线和同环节公司是否继续强化", "看逻辑卡/业务线/同环节扩散")
    value = value.replace("是否被更多资料确认受益；", "")
    value = value.replace("是否被更多资料确认受益", "")
    value = value.replace("无需特别追踪", "")
    value = value.replace("同环节公司/相邻工艺待补", "")
    return value[:limit] + ("…" if len(value) > limit else "")


def front_unique_join(values: list[str], limit: int = 4, empty: str = "待补") -> str:
    items = unique([front_compact_text(v, 36) for v in values if str(v).strip()])
    return "、".join(items[:limit]) if items else empty


def front_theme_anchor(term: str, definition: str, context: dict) -> str:
    profile = context.get("definition_profile", {}) if isinstance(context, dict) and isinstance(context.get("definition_profile"), dict) else {}
    anchor = str(profile.get("one_line_anchor", "")).strip()
    if anchor:
        return front_compact_text(anchor, 140)
    if definition.strip():
        return front_compact_text(definition, 140)
    return f"{term}：由需求变化、供给周期、产业链验证和个股逻辑卡共同驱动的题材地图。"


def front_driver_items(context: dict, companies: list[dict], limit: int = 5) -> list[str]:
    items = []
    for key in ("demand_drivers", "demand_scenarios", "recognition_timeline", "catalyst_calendar"):
        for row in context.get(key, []) or []:
            if not isinstance(row, dict):
                continue
            text = "：".join(
                str(row.get(field, "")).strip()
                for field in ("driver", "scenario", "event", "catalyst", "change", "logic", "description", "impact")
                if str(row.get(field, "")).strip()
            )
            if text:
                items.append(front_compact_text(text, 80))
            if len(unique(items)) >= limit:
                return unique(items)[:limit]
    if companies:
        basis = [c.get("name", "") for c in sorted(companies, key=company_sort_key)[:6]]
        items.append(f"公司业务线更新：{front_unique_join(basis, 6)}等公司出现新的业务线或上下游发散线索。")
    return unique(items)[:limit] or ["暂无明确发酵驱动。"]


def front_company_bucket(company: dict, term: str = "", profile: dict | None = None) -> str:
    if profile:
        direction = company_direction_key(company, profile)
        label = direction_label(direction, profile)
        if label and label != "待判定":
            return label
    text = " ".join(
        str(x)
        for x in (
            [company.get("name", ""), themed_company_roles(company, term)]
            + as_list(company.get("concepts"))
            + as_list(company.get("chain_layers"))
            + as_list(company.get("evidence"))
        )
    )
    if any(token in text for token in ("DDR5", "RCD", "SPD", "VPD", "MRDIMM", "CXL", "内存接口")):
        return "DDR5/接口芯片"
    if any(token in text for token in ("模组", "SSD", "eSSD", "主控", "嵌入式存储", "移动存储")):
        return "模组/SSD/主控"
    if any(token in text for token in ("NOR", "NAND", "DRAM", "存储芯片", "利基存储", "芯片设计")) and not any(token in text for token in ("设备", "封测", "封装", "材料")):
        return "存储设计/产品"
    if any(token in text for token in ("封测", "封装", "HBM封装", "CoWoS", "先进封装", "DRAM封测")):
        return "封测/HBM封装"
    if any(token in text for token in ("测试", "量测", "探针", "测试机")):
        return "测试设备"
    if any(token in text for token in ("设备", "ALD", "CVD", "刻蚀", "清洗", "SDBG", "隐切", "沉积")):
        return "前道/专用设备"
    if any(token in text for token in ("材料", "EMC", "Low-α", "球硅", "前驱体", "电镀液", "硅片", "靶材", "特气", "CMP")):
        return "材料/硅片/化学品"
    return "相关环节"


def front_bucket_order(companies: list[dict], profile: dict | None = None) -> list[str]:
    labels = []
    if profile:
        for direction in profile.get("ranks", ()) or ():
            label = direction_label(direction, profile)
            if label and label != "待判定":
                labels.append(label)
    labels.extend(front_company_bucket(company, profile=profile) for company in companies)
    labels.extend(["相关环节"])
    return unique([label for label in labels if label and label != "待判定"])


def front_context_bucket(row: dict) -> str:
    text = " ".join(
        str(row.get(field, ""))
        for field in ("layer", "segment", "name", "major_track", "chain_position", "key_elements", "industry_logic", "evidence_summary")
    )
    if any(token in text for token in ("DDR5", "RCD", "SPD", "VPD", "MRDIMM", "CXL", "内存接口")):
        return "DDR5/接口芯片"
    if any(token in text for token in ("模组", "SSD", "eSSD", "主控", "嵌入式存储", "移动存储")):
        return "模组/SSD/主控"
    if any(token in text for token in ("封测", "封装", "HBM封装", "CoWoS", "先进封装", "DRAM封测")):
        return "封测/HBM封装"
    if any(token in text for token in ("测试", "量测", "探针", "测试机")):
        return "测试设备"
    if any(token in text for token in ("设备", "ALD", "CVD", "刻蚀", "清洗", "SDBG", "隐切", "沉积")):
        return "前道/专用设备"
    if any(token in text for token in ("材料", "EMC", "Low-α", "球硅", "前驱体", "电镀液", "硅片", "靶材", "特气", "CMP")):
        return "材料/硅片/化学品"
    if any(token in text for token in ("NOR", "NAND", "DRAM", "存储芯片", "利基存储", "芯片设计", "HBM")):
        return "存储设计/产品"
    return "相关环节"


def front_context_chain_additions(context: dict) -> dict[str, list[dict]]:
    banned = {"SK海力士", "三星", "美光", "英伟达", "台积电", "长鑫科技", "长鑫存储", "长江存储", "爱德万", "泰瑞达"}
    additions: dict[str, list[dict]] = {}
    rows = []
    for key in ("industry_chain_panorama", "material_process_scan"):
        rows.extend([row for row in (context.get(key, []) or []) if isinstance(row, dict)])
    for row in rows:
        reps = as_list(row.get("representative_entities") or row.get("candidate_companies"))
        reps = [name for name in reps if name and name not in banned and not re.search(r"^[A-Za-z0-9_ .-]+$", str(name))]
        if not reps:
            continue
        bucket = front_context_bucket(row)
        additions.setdefault(bucket, []).append({
            "names": reps,
            "role": row.get("segment") or row.get("name") or row.get("key_elements") or "",
            "validation": row.get("next_validation") or row.get("core_catalyst") or "",
        })
    return additions


def front_chain_stage_for_bucket(bucket: str) -> str:
    text = str(bucket or "")
    if any(token in text for token in ("下游", "渠道", "运营", "电站", "商业化")):
        return "下游需求/应用"
    if any(token in text for token in ("材料", "化学品", "硅料", "硅片", "辅材", "玻璃", "胶膜")):
        return "上游材料"
    if any(token in text for token in ("设备", "量检测", "测试", "制药装备")):
        return "上游设备"
    if any(token in text for token in ("服务", "平台", "生态", "CXO", "CRO", "CDMO")):
        return "配套服务/生态"
    return "中游产品/制造"


def front_chain_rows(companies: list[dict], term: str = "", context: dict | None = None, profile: dict | None = None, limit_per_bucket: int = 10) -> list[dict]:
    bucket_order = front_bucket_order(companies, profile)
    grouped = {key: [] for key in bucket_order}
    for company in sorted(companies, key=lambda c: ({"relative_core": 0, "related": 1, "watch": 2, "weak": 3}.get(company_deep_dive_tier(c), 3), company_sort_key(c))):
        if company_deep_dive_tier(company) == "weak":
            continue
        grouped.setdefault(front_company_bucket(company, term, profile), []).append(company)
    additions = front_context_chain_additions(context or {})
    rows_out = []
    for bucket in bucket_order:
        rows = grouped.get(bucket, [])[:limit_per_bucket]
        extra_rows = additions.get(bucket, [])
        if not rows and not extra_rows:
            continue
        company_names = [c.get("name", "") for c in rows]
        extra_names = [name for row in extra_rows for name in row.get("names", [])]
        names = front_unique_join(company_names + extra_names, limit_per_bucket)
        roles = front_unique_join([themed_company_roles(c, term) for c in rows] + [row.get("role", "") for row in extra_rows], 4)
        rows_out.append({"bucket": bucket, "roles": roles, "companies": names, "stage": front_chain_stage_for_bucket(bucket)})
    return rows_out


def front_chain_tree_section(term: str, rows: list[dict], context: dict | None = None) -> str:
    if not rows:
        return ""
    stage_order = ["下游需求/应用", "中游产品/制造", "上游材料", "上游设备", "配套服务/生态"]
    grouped: dict[str, list[dict]] = {stage: [] for stage in stage_order}
    for row in rows:
        grouped.setdefault(row["stage"], []).append(row)
    downstream_items = context_chain_items(context or {}, "downstream", 5)
    lines = [front_compact_text(term or "题材", 40)]
    if downstream_items:
        lines.append(f"├─ 终端需求：{front_unique_join(downstream_items, 5, '')}")
    visible_stages = [stage for stage in stage_order if grouped.get(stage)]
    for stage_index, stage in enumerate(visible_stages):
        stage_is_last = stage_index == len(visible_stages) - 1
        stage_prefix = "└─" if stage_is_last else "├─"
        child_prefix = "   " if stage_is_last else "│  "
        lines.append(f"{stage_prefix} {stage}")
        stage_rows = grouped.get(stage, [])
        for row_index, row in enumerate(stage_rows):
            row_is_last = row_index == len(stage_rows) - 1
            branch = "└─" if row_is_last else "├─"
            companies = front_compact_text(row.get("companies", ""), 70)
            lines.append(f"{child_prefix}{branch} {row.get('bucket', '')}：{companies}")
    return "```text\n" + "\n".join(lines) + "\n```"


def front_chain_map_section(companies: list[dict], term: str = "", context: dict | None = None, profile: dict | None = None, limit_per_bucket: int = 10) -> str:
    rows = front_chain_rows(companies, term, context, profile, limit_per_bucket)
    if not rows:
        return "- 暂无可展示的产业链节点。"
    tree = front_chain_tree_section(term, rows, context)
    lines = ["| 地图节点 | 主要看点 | 代表公司 |", "|---|---|---|"]
    for row in rows:
        lines.append(f"| {row.get('bucket', '')} | {row.get('roles', '')} | {row.get('companies', '')} |")
    return tree + "\n\n" + "\n".join(lines) if tree else "\n".join(lines)


def front_company_cards_section(companies: list[dict], tier: str, term: str = "", profile: dict | None = None, limit: int = 6) -> str:
    rows = [c for c in companies if company_deep_dive_tier(c) == tier and not should_skip_structured_company_card(c, term)]
    rows = sorted(rows, key=company_sort_key)[:limit]
    if not rows:
        return "- 暂无。"
    labels = {"relative_core": "主线公司", "related": "相关公司", "watch": "延伸公司", "weak": "弱相关"}
    lines = ["| 公司 | 角色 | 位置 | 一句话定位（wiki） |", "|---|---|---|---|"]
    for company in rows:
        role = front_compact_text(themed_company_roles(company, term), 32)
        bucket = front_company_bucket(company, term, profile)
        one_liner = front_compact_text(company.get("wiki_one_liner") or "", 46) or "待补"
        lines.append(f"| {company.get('name', '')} | {role} | {bucket}/{labels.get(tier, tier)} | {one_liner} |")
    return "\n".join(lines)


def front_company_logic_summary(company: dict, term: str = "", limit: int = 120) -> str:
    sources = " ".join(str(x) for x in company.get("sources", []) or [])
    preferred = []
    if has_ima_logic_card_source_text(sources):
        preferred.extend(str(x) for x in company.get("evidence_buckets", {}).get("delta", []) or [])
        preferred.extend(str(x) for x in company.get("evidence", []) or [])
    preferred.extend(str(x) for x in company.get("context_mentions", []) or [])
    preferred.extend(str(x) for x in company.get("roles", []) or [])
    tokens = [term] + as_list(company.get("concepts")) + as_list(company.get("subdirections"))
    focused = []
    for text in preferred:
        if not str(text).strip():
            continue
        if any(token and token in str(text) for token in tokens):
            focused.append(text)
    selected = focused or preferred
    return front_compact_text("；".join(unique([str(x).strip() for x in selected if str(x).strip()])[:3]), limit) or "待补逻辑摘要"


def front_company_source_bridge(company: dict) -> str:
    buckets = company.get("evidence_buckets", {}) or {}
    sources = set(source_basis(company))
    labels = []
    if has_ima_logic_card_source(company):
        labels.append("卡")
    if buckets.get("curated_research") or "PDF研报/深度研究" in sources:
        labels.append("PDF")
    if company.get("context_mentions") or "full精读上下文提及" in sources:
        labels.append("IMA")
    if buckets.get("delta") and "精选逻辑/脱水/复盘" in sources:
        labels.append("复盘")
    if buckets.get("baseline"):
        labels.append("画像")
    return "+".join(unique(labels)[:4]) or "wiki"


def front_company_review_use(company: dict, term: str = "", profile: dict | None = None) -> str:
    bucket = front_company_bucket(company, term, profile)
    if has_ima_logic_card_source(company):
        return front_compact_text(f"逻辑解释 / {bucket}扩散", 42)
    if company.get("context_mentions"):
        return front_compact_text(f"产业链补位 / {bucket}", 42)
    return front_compact_text(f"{bucket}延伸池", 42)


def front_company_observation_point(company: dict, term: str = "", profile: dict | None = None) -> str:
    explicit = company_validation_focus(company)
    generic = "后续研报/精选逻辑是否继续强化该公司与题材主线的直接关系；复盘中观察逻辑卡、业务线和同环节公司是否继续强化"
    if explicit and explicit != generic:
        return front_compact_text(explicit, 62)
    if has_ima_logic_card_source(company):
        return "逻辑卡业务线是否继续扩散"
    bucket = front_company_bucket(company, term, profile)
    return front_compact_text(f"{bucket}是否扩散", 42)


def front_related_names_for_company(company: dict, companies: list[dict], profile: dict | None = None, term: str = "", limit: int = 4) -> str:
    current = company.get("name")
    direction = company_direction_key(company, profile)
    broad = {term, company.get("deep_dive_term", ""), "存储芯片", "光模块", "创新药", "光伏"}
    concepts = set(company.get("concepts", []) or []) - {x for x in broad if x}
    rows = []
    for other in companies:
        if other.get("name") == current or company_deep_dive_tier(other) == "weak":
            continue
        same_direction = company_direction_key(other, profile) == direction
        shared_concepts = concepts & (set(other.get("concepts", []) or []) - {x for x in broad if x})
        if same_direction or shared_concepts:
            rows.append((0 if same_direction else 1, other))
    rows = [row for _rank, row in sorted(rows, key=lambda item: (item[0], company_sort_key(item[1])))]
    return front_unique_join([row.get("name", "") for row in rows], limit, "待补")


def front_logic_card_expansion_section(companies: list[dict], term: str = "", profile: dict | None = None, limit: int = 14) -> str:
    rows = [
        c for c in companies
        if has_ima_logic_card_source(c)
        and company_deep_dive_tier(c) != "weak"
        and not should_skip_structured_company_card(c, term)
    ]
    rows = sorted(rows, key=recent_ima_company_sort_key)[:limit]
    if not rows:
        return "- 暂无近期 IMA 个股逻辑卡候选。"
    lines = [
        "| 公司 | 角色 | 位置 |",
        "|---|---|---|",
    ]
    for company in rows:
        bucket = front_company_bucket(company, term, profile)
        role = front_compact_text(themed_company_roles(company, term), 42)
        lines.append(f"| {company.get('name', '')} | {role} | {bucket} |")
    return "\n".join(lines)


def front_key_validation_section(context: dict, companies: list[dict], limit: int = 8) -> str:
    items = []
    for row in context.get("validation_checklist", []) or []:
        if isinstance(row, dict):
            text = "：".join(str(row.get(field, "")).strip() for field in ("item", "validation", "watch", "signal", "criteria", "description") if str(row.get(field, "")).strip())
            if text:
                items.append(front_compact_text(text, 88))
    for company in sorted(companies, key=company_sort_key):
        if company_deep_dive_tier(company) in {"relative_core", "related", "watch"}:
            items.append(front_compact_text(f"{company.get('name', '')}：{company_validation_focus(company)}", 88))
        if len(unique(items)) >= limit:
            break
    return bullets(unique(items)[:limit], "待补验证点")


def front_guardrail_section(companies: list[dict], limit: int = 8) -> str:
    items = []
    for company in sorted(companies, key=lambda c: (company_deep_dive_tier(c), company_sort_key(c))):
        note = company_guardrail_note(company)
        if note and "后续看研报" not in note:
            items.append(front_compact_text(f"{company.get('name', '')}：{note}", 88))
        if len(unique(items)) >= limit:
            break
    return bullets(unique(items)[:limit], "暂无显性护栏")


def front_information_bridge_section(state: dict, active: list[dict]) -> str:
    context = state.get("context", {}) or {}
    report_sources = unique([
        str(row.get("source_name") or row.get("source") or "")
        for row in state.get("local_report_contexts", []) or []
        if isinstance(row, dict) and str(row.get("source_name") or row.get("source") or "").strip()
    ])
    logic_names = [c.get("name", "") for c in active if has_ima_logic_card_source(c)]
    curated_count = sum(1 for c in active if (c.get("evidence_buckets", {}) or {}).get("curated_research"))
    delta_count = sum(1 for c in active if (c.get("evidence_buckets", {}) or {}).get("delta"))
    rows = [
        ("wiki 概念/关系", f"{state.get('primary') or state.get('term')} + {len(state.get('rels', []) or [])} 个相关概念", "确定题材边界、上下游节点和公司关系。"),
        ("个股逻辑卡", f"{len(logic_names)} 个公司样本：{front_unique_join(logic_names, 8)}", "解释复盘个股为什么属于这条线，并向同环节/上下游发散。"),
        ("IMA DeepDive / full 精读", f"{len(context.get('industry_chain_panorama', []) or [])} 条产业链、{len(context.get('material_process_scan', []) or [])} 条工艺材料线索", "补齐模板里的产业链全景、工艺材料扫描和细分方向。"),
        ("PDF ingest / 研报上下文", f"{len(report_sources)} 个上下文来源；{curated_count} 个公司带研报证据", "把研报中的需求、环节、公司线索沉淀成可复盘的题材地图。"),
        ("复盘/精选逻辑", f"{delta_count} 个公司带边际逻辑或复盘线索", "用于识别当前市场更可能扩散的方向和公司池。"),
    ]
    lines = ["| 数据桥梁 | 当前命中 | 如何服务题材雷达/复盘 |", "|---|---|---|"]
    for name, hit, use in rows:
        lines.append(f"| {name} | {front_compact_text(hit, 90)} | {front_compact_text(use, 110)} |")
    return "\n".join(lines)


def front_review_feedback_section(state: dict, active: list[dict], term: str = "", profile: dict | None = None, limit: int = 10) -> str:
    rows = []
    logic_rows = [c for c in active if has_ima_logic_card_source(c)]
    for company in sorted(logic_rows, key=recent_ima_company_sort_key)[:limit]:
        bucket = front_company_bucket(company, term, profile)
        related = front_related_names_for_company(company, active, profile, term, 4)
        observation = front_company_observation_point(company, term, profile)
        rows.append((company.get("name", ""), bucket, related, observation))
    if not rows:
        for company in sorted(active, key=company_sort_key)[:limit]:
            bucket = front_company_bucket(company, term, profile)
            related = front_related_names_for_company(company, active, profile, term, 4)
            rows.append((company.get("name", ""), bucket, related, front_company_observation_point(company, term, profile)))
    if not rows:
        return "- 暂无可反哺复盘的公司线索。"
    lines = ["| 复盘抓手 | 题材位置 | 可继续发散 |", "|---|---|---|"]
    for name, bucket, related, observation in rows[:limit]:
        lines.append(f"| {name} | {bucket} | {related} |")
    return "\n".join(lines)


def front_review_trigger_section(review_context: dict | None, companies: list[dict], term: str = "") -> str:
    review_context = review_context or {}
    source = str(review_context.get("source") or "").strip()
    direction = str(review_context.get("direction") or "").strip()
    note = str(review_context.get("note") or "").strip()
    review_names = as_list(review_context.get("companies"))
    if not any([source, direction, note, review_names]):
        return bullets(
            [
                f"当前由 `{term}` 题材查询触发。",
                f"已整理 {len(companies)} 个相关公司样本，可展开产业链位置、业务线和上下游发散。",
            ],
            "待补复盘触发",
        )
    items = []
    if source:
        items.append(f"复盘来源：{source}")
    if direction:
        items.append(f"复盘方向：{direction}")
    if review_names:
        items.append(f"触发个股：{front_unique_join(review_names, 12)}")
    if note:
        items.append(f"备注：{front_compact_text(note, 120)}")
    return bullets(items, "待补复盘触发")


def front_definition_is_generic(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    generic_tokens = (
        "追踪", "无需", "待补", "验证", "观察", "后续", "是否", "进展", "价格走势",
        "量产节奏", "出货", "客户导入", "国产化进展", "继续强化", "资料确认",
        "毛利率", "收入占比", "产能及良率", "季度变化",
    )
    return any(token in text for token in generic_tokens)


def front_subdirection_definition(row: dict) -> str:
    subdir = map_clean_plain(row.get("subdir"), limit=70) or map_clean_plain(row.get("layer"), limit=70)
    layer = map_clean_plain(row.get("layer"), limit=70)
    desc = map_clean_plain(row.get("desc"), limit=110)
    if desc and not front_definition_is_generic(desc):
        return desc

    text = f"{subdir} {layer}"
    rules = [
        (("HBM", "高带宽内存"), "AI服务器高带宽内存升级方向"),
        (("DRAM",), "通用内存产品，受服务器需求与产能周期影响"),
        (("NAND", "eSSD", "企业级SSD"), "闪存与企业级SSD容量升级方向"),
        (("DDR5", "RCD", "SPD", "MRDIMM", "CXL"), "服务器内存代际升级和接口芯片方向"),
        (("TSV",), "HBM与先进封装里的硅通孔工艺"),
        (("混合键合", "Hybrid Bonding"), "高层数HBM与3D封装连接工艺"),
        (("400G", "800G", "1.6T", "3.2T"), "AI数据中心高速光互联产品代际"),
        (("OSFP", "QSFP"), "高速光模块封装形态"),
        (("硅光", "CPO", "LPO", "NPO"), "高速互联技术路线"),
        (("EML", "DFB", "VCSEL", "CW光源"), "光芯片与激光器器件路线"),
        (("法拉第", "光隔离器", "磁光", "TGG", "TSAG"), "光隔离器和磁光材料方向"),
        (("FAU", "光纤阵列"), "光引擎里的光纤阵列单元方向"),
        (("MPO", "MTP", "MMC", "MT插芯", "陶瓷插芯"), "高速光互连连接器方向"),
        (("AWG", "PLC", "WDM", "波分"), "无源光芯片和波分器件方向"),
        (("环形器", "滤波片", "准直器", "透镜", "棱镜"), "OCS/光引擎相关精密光学器件方向"),
        (("ADC",), "抗体偶联药物平台和管线方向"),
        (("双抗",), "双特异性抗体平台和管线方向"),
        (("GLP", "减重"), "代谢类创新药管线方向"),
        (("CAR-T", "细胞治疗"), "细胞治疗平台和管线方向"),
        (("核药", "放射性药物"), "核素诊疗和放射性药物方向"),
        (("TOPCon", "HJT", "BC电池", "XBC", "HPBC", "TBC", "IBC", "钙钛矿", "叠层"), "光伏电池技术路线"),
        (("硅片", "组件", "逆变器", "银浆", "胶膜", "支架"), "光伏产业链环节或辅材方向"),
        (("mSAP", "半加成"), "高密度PCB精细线路制造工艺"),
        (("载体铜箔", "感光干膜", "DPC", "TGV"), "先进封装和高端PCB相关材料/基板方向"),
    ]
    for tokens, definition in rules:
        if any(token in text for token in tokens):
            return definition
    if layer and subdir and layer != subdir:
        return f"{layer}中的{subdir}方向"
    return f"{subdir}相关细分方向" if subdir else "题材内细分方向"


def front_subdirection_digest_section(state: dict, limit: int = 12) -> str:
    rows = map_subdirection_rows(state)[:limit]
    if not rows:
        return "- 暂无可展示的细分方向。"
    lines = ["| 细分方向 | 一句话定义 | 代表公司 |", "|---|---|---|"]
    for row in rows:
        subdir = map_clean_plain(row.get("subdir"), limit=70) or map_clean_plain(row.get("layer"), limit=70)
        companies = map_clean_plain(row.get("companies"), limit=120)
        desc = front_subdirection_definition(row)
        lines.append(f"| {subdir} | {desc} | {companies} |")
    return "\n".join(lines)


def front_material_row_text(row: dict) -> str:
    values = []
    for field in ("name", "direction", "classification", "major_track", "chain_position", "core_catalyst", "prosperity_judgment", "prosperity_reason", "next_validation", "evidence_summary"):
        values.extend(as_list(row.get(field)))
    values.extend(as_list(row.get("representative_entities")))
    return " ".join(str(x) for x in values if str(x).strip())


def front_material_is_specific(name: str, row_text: str) -> bool:
    text = f"{name} {row_text}"
    if len(str(name or "").strip()) < 2:
        return False
    generic = {
        "其他观察", "相关环节", "待补", "核心产品/主线主体", "上游材料/电子化学品", "上游设备/量检测", "服务/平台", "下游渠道/运营",
        "ASP（平均售价）", "毛利率", "客户认证", "产能（扩产）", "出货量（800G/1.6T）", "良率（硅光芯片）",
    }
    if str(name).strip() in generic:
        return False
    if any(token in str(name) for token in ("ASP", "平均售价", "毛利率", "客户认证", "产能", "出货量", "良率")):
        return False
    tokens = (
        "工艺", "材料", "设备", "零部件", "封装", "基板", "铜箔", "干膜", "玻璃", "陶瓷", "硅片", "靶材", "特气", "胶", "树脂", "球硅",
        "HBM", "DDR", "NAND", "NOR", "SSD", "TSV", "TGV", "CPO", "LPO", "NPO", "硅光", "EML", "VCSEL", "CW", "PCB", "HDI", "mSAP",
        "法拉第", "旋片", "旋光片", "光隔离器", "隔离器", "磁光", "TGG", "TSAG", "SGGG", "FAU", "光纤阵列", "MPO", "MTP", "MMC",
        "MT插芯", "陶瓷插芯", "AWG", "PLC", "WDM", "波分", "滤波片", "环形器", "准直器", "透镜", "棱镜", "偏振", "OSA", "TOSA", "ROSA",
        "ADC", "双抗", "GLP", "管线", "临床", "BD", "TOPCon", "BC", "钙钛矿", "逆变器", "组件", "银浆", "胶膜", "玻璃", "支架",
    )
    return any(token in text for token in tokens)


def front_material_display_priority(row: dict) -> tuple:
    name = str(row.get("name") or row.get("direction") or "")
    text = front_material_row_text(row)
    fine_tokens = (
        "法拉第", "旋片", "光隔离器", "隔离器", "磁光", "TGG", "TSAG", "FAU", "光纤阵列",
        "MPO", "MTP", "MMC", "MT插芯", "陶瓷插芯", "AWG", "PLC", "WDM", "环形器", "滤波片", "准直器", "透镜",
    )
    if any(token in name for token in fine_tokens):
        return (0, name)
    if str(row.get("source") or "") == "theme_information_pool" and any(token in text for token in fine_tokens):
        return (1, name)
    if any(token in name for token in ("ASP", "毛利率", "客户认证", "产能", "出货量", "良率")):
        return (9, name)
    return (3, name)


def front_material_company_matches(row: dict, companies: list[dict], term: str = "", profile: dict | None = None, limit: int = 8) -> list[dict]:
    row_text = front_material_row_text(row)
    names = [str(x).strip() for x in as_list(row.get("representative_entities") or row.get("candidate_companies")) if str(x).strip()]
    name_set = set(names)
    explicit_name_matches = [company for company in companies if company.get("name") in name_set]
    if explicit_name_matches:
        return sorted(unique_by_name(explicit_name_matches), key=company_sort_key)[:limit]
    tokens = unique([
        str(row.get("name") or row.get("direction") or "").strip(),
        str(row.get("classification") or "").strip(),
        str(row.get("major_track") or "").strip(),
        str(row.get("chain_position") or "").strip(),
    ] + [x for x in re.split(r"[/、,，\s]+", row_text) if len(x) >= 3])
    weak_tokens = {"存储芯片", "存储", "芯片", "AI存储", "存储产业链下游", "光通信", "光模块", "创新药", "光伏", "先进封装", "半导体设备"}
    tokens = [token for token in tokens if token and token not in weak_tokens]
    matched = []
    for company in companies:
        company_text = " ".join(
            str(x)
            for x in (
                [company.get("name", ""), front_company_bucket(company, term, profile), themed_company_roles(company, term)]
                + as_list(company.get("concepts"))
                + as_list(company.get("roles"))
                + as_list(company.get("evidence"))
                + company_subdirections(company)
            )
        )
        if any(token and token in company_text for token in tokens[:10]):
            matched.append(company)
    return sorted(unique_by_name(matched), key=company_sort_key)[:limit]


def unique_by_name(companies: list[dict]) -> list[dict]:
    seen = set()
    rows = []
    for company in companies:
        name = company.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append(company)
    return rows


def front_material_logic_source(row: dict, matches: list[dict]) -> str:
    labels = []
    source = str(row.get("source") or "")
    if source or row.get("raw_row"):
        labels.append("IMA")
    if any((c.get("evidence_buckets", {}) or {}).get("curated_research") for c in matches):
        labels.append("PDF")
    if any(has_ima_logic_card_source(c) for c in matches):
        labels.append("逻辑卡")
    if matches:
        labels.append("wiki")
    return "+".join(unique(labels)[:4]) or "wiki"


def front_material_expand_terms(row: dict, all_rows: list[dict], matches: list[dict], term: str = "", profile: dict | None = None) -> str:
    name = str(row.get("name") or row.get("direction") or "")
    layer = str(row.get("chain_position") or row.get("major_track") or "")
    peers = []
    for other in all_rows:
        if not isinstance(other, dict):
            continue
        other_name = str(other.get("name") or other.get("direction") or "")
        if not other_name or other_name == name:
            continue
        other_layer = str(other.get("chain_position") or other.get("major_track") or "")
        if layer and other_layer == layer:
            peers.append(other_name)
    company_peers = []
    for company in matches[:3]:
        company_peers.extend(front_related_names_for_company(company, matches, profile, term, 3).split("、"))
    values = unique([x for x in peers + company_peers if x and x != "待补"])
    return front_unique_join(values, 4, "")


def front_material_watch(row: dict, matches: list[dict], term: str = "", profile: dict | None = None) -> str:
    explicit = row.get("next_validation") or row.get("core_catalyst") or row.get("prosperity_reason") or row.get("evidence_summary")
    if explicit:
        value = front_compact_text(explicit, 58)
        generic_tokens = ("无需特别追踪", "继续强化", "更多资料确认", "后续跟踪", "待补", "验证空位")
        return "" if any(token in value for token in generic_tokens) else value
    if matches:
        company = matches[0]
        bucket = front_company_bucket(company, term, profile)
        return front_compact_text(f"{company.get('name')}->{bucket}扩散", 42)
    return ""


def front_material_scan_rows(state: dict) -> list[dict]:
    context = state.get("context", {}) or {}
    raw_rows = [row for row in (context.get("material_process_scan", []) or []) if isinstance(row, dict)]
    rows = []
    for row in raw_rows:
        name = str(row.get("name") or row.get("direction") or "").strip()
        row_text = front_material_row_text(row)
        if front_material_is_specific(name, row_text):
            rows.append(row)
    if not rows:
        for row in map_subdirection_rows(state):
            name = str(row.get("subdir") or row.get("layer") or "").strip()
            row_text = " ".join(str(row.get(field, "")) for field in ("subdir", "layer", "desc", "concepts", "companies"))
            if front_material_is_specific(name, row_text):
                rows.append({
                    "name": name,
                    "major_track": row.get("layer"),
                    "chain_position": row.get("layer"),
                    "core_catalyst": row.get("desc"),
                    "representative_entities": as_list(row.get("companies")),
                    "source": row.get("source"),
                    "next_validation": row.get("gap"),
                })
    return sorted(rows, key=front_material_display_priority)


def front_material_process_radar_section(state: dict, active: list[dict], term: str = "", profile: dict | None = None, limit: int = 16) -> str:
    rows = front_material_scan_rows(state)
    if not rows:
        return "- 暂无可展示的工艺/材料/零部件扫描。"
    lines = [
        "| 细颗粒对象 | 所属大方向 | 产业链位置 | 逻辑一句话 | 代表公司 | 可发散方向 |",
        "|---|---|---|---|---|---|",
    ]
    seen = set()
    for row in rows:
        name = str(row.get("name") or row.get("direction") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        matches = front_material_company_matches(row, active, term, profile, 8)
        explicit_companies = as_list(row.get("representative_entities"))
        companies = front_unique_join(explicit_companies + [c.get("name", "") for c in matches], 8)
        logic = row.get("core_catalyst") or row.get("prosperity_judgment") or row.get("prosperity_reason") or row.get("evidence_summary") or row.get("next_validation")
        major = row.get("major_track") or row.get("classification") or row.get("direction")
        position = row.get("chain_position") or row.get("layer") or major
        expand = front_material_expand_terms(row, rows, matches, term, profile)
        cells = [
            front_compact_text(str(name or ""), 42),
            front_compact_text(str(major or ""), 52),
            front_compact_text(str(position or ""), 46),
            front_compact_text(str(logic or ""), 78),
            front_compact_text(str(companies or ""), 62),
            front_compact_text(str(expand or ""), 52),
        ]
        lines.append("| " + " | ".join(cells) + " |")
        if len(lines) >= limit + 2:
            break
    return "\n".join(lines) if len(lines) > 2 else "- 暂无可展示的工艺/材料/零部件扫描。"


def front_data_advantage_section(state: dict, active: list[dict]) -> str:
    context = state.get("context", {}) or {}
    logic_count = sum(1 for c in active if has_ima_logic_card_source(c))
    return bullets(
        [
            f"概念与关系：主概念 `{state.get('primary') or state.get('term')}`，相关概念 {len(state.get('rels', []) or [])} 个。",
            f"公司图谱：活跃公司 {len(active)} 个，带 IMA 个股逻辑卡 {logic_count} 个。",
            f"题材信息池：{len(context.get('direction_scan', []) or [])} 条方向扫描，{len(context.get('material_process_scan', []) or [])} 条工艺/材料扫描，{len(context.get('industry_chain_panorama', []) or [])} 条产业链全景。",
            "前端优先服务复盘和交易理解：展示产业链、公司位置、逻辑来源、发散对象和观察点；工程质检字段留在 deep-dive/report_contexts 中追溯。",
        ],
        "待补数据资产",
    )


def benchmark_map_text(row: dict) -> str:
    values = [
        row.get("benchmark_company", ""),
        row.get("benchmark_ticker", ""),
        row.get("benchmark_theme", ""),
        " ".join(as_list(row.get("theme_routes"))),
    ]
    for business in row.get("benchmark_business_lines", []) or []:
        if isinstance(business, dict):
            values.extend(
                [
                    business.get("business_line", ""),
                    business.get("english_name", ""),
                    business.get("definition", ""),
                    business.get("importance", ""),
                    " ".join(as_list(business.get("key_products"))),
                    " ".join(as_list(business.get("downstream_applications"))),
                ]
            )
    for company in row.get("mapped_companies", []) or []:
        if isinstance(company, dict):
            values.extend(
                [
                    company.get("company", ""),
                    company.get("mapped_business_line", ""),
                    company.get("mapped_business", ""),
                    company.get("mapping_type", ""),
                    company.get("core_basis", ""),
                ]
            )
    return normalize(" ".join(str(x) for x in values if str(x).strip()))


def match_benchmark_maps(term: str, benchmark_maps: dict, state_text: str = "", limit: int = 4) -> list[dict]:
    maps = benchmark_maps.get("maps", []) if isinstance(benchmark_maps, dict) else []
    if not isinstance(maps, list):
        return []
    query_terms = unique([term] + split_terms(term) + split_terms(state_text))
    query_terms = [q for q in query_terms if len(normalize(q)) >= 2 and q not in {"AI", "C", "H"}]
    rows = []
    for row in maps:
        if not isinstance(row, dict):
            continue
        haystack = benchmark_map_text(row)
        route_hits = [route for route in as_list(row.get("theme_routes")) if context_term_hit(route, term) or context_term_hit(term, route)]
        direct_hits = [q for q in query_terms if q and context_term_hit(q, haystack)]
        score = len(route_hits) * 5 + min(len(direct_hits), 12)
        if score <= 0:
            continue
        row_copy = dict(row)
        row_copy["_benchmark_match_score"] = score
        row_copy["_benchmark_hits"] = unique(route_hits + direct_hits)[:10]
        rows.append(row_copy)
    rows.sort(key=lambda r: (-int(r.get("_benchmark_match_score") or 0), str(r.get("benchmark_company") or "")))
    return rows[:limit]


def benchmark_row_score(row: dict) -> float:
    value = row.get("mapping_score", 0)
    try:
        return float(value)
    except Exception:
        text = str(row.get("mapping_strength") or "")
        if "强" in text:
            return 8.0
        if "中" in text:
            return 6.0
        if "弱" in text:
            return 3.0
        return 0.0


def benchmark_mapped_company_is_domestic(row: dict) -> bool:
    market = str(row.get("market") or "")
    ticker = str(row.get("ticker") or "")
    market_upper = market.upper()
    ticker_upper = ticker.upper()
    if any(token in market for token in ("A股", "港股", "H股", "北交所")):
        return True
    if any(token in ticker_upper for token in (".SH", ".SZ", ".BJ", ".HK")):
        return True
    if any(token in market_upper for token in ("NASDAQ", "NYSE", "EURONEXT", "LSE")):
        return False
    return True


def benchmark_focus_tokens(term: str) -> list[str]:
    text = str(term or "")
    rules = [
        (("光模块", "光通信", "光互联", "CPO", "硅光", "光芯片", "光器件"), ("光互联", "光模块", "Optical", "Transceiver", "Datacom", "DSP", "CPO", "硅光", "Photonic", "AEC", "Retimer有源电缆")),
        (("光芯片", "EML", "VCSEL", "InP"), ("光芯片", "EML", "VCSEL", "InP", "CW激光器", "激光芯片", "200G", "100G")),
        (("OCS", "光交换机", "光路交换", "光电路交换"), ("OCS", "光电路交换", "光路交换", "Optical Circuit Switch", "MEMS", "LCOS")),
        (("工业激光", "激光器", "激光设备"), ("工业激光", "Industrial Lasers", "光纤激光器", "超快激光器", "准分子激光器", "Lasers")),
        (("光学材料", "磁光材料", "光学晶体"), ("光学晶体", "磁光材料", "TGG", "TSAG", "法拉第", "工程材料", "SiC")),
        (("HBM", "高带宽内存"), ("HBM", "High Bandwidth Memory", "TSV", "Base Die", "3D堆叠", "混合键合")),
        (("DRAM", "DDR", "LPDDR", "内存"), ("DRAM", "DDR5", "DDR4", "MRDIMM", "LPDDR", "RDIMM", "内存接口")),
        (("3D NAND", "NAND"), ("NAND", "3D NAND", "SLC NAND", "QLC", "TLC", "UFS", "eMMC")),
        (("SSD", "固态硬盘"), ("SSD", "eSSD", "Enterprise SSD", "Client SSD", "PCIe 5.0", "PCIe 6.0", "主控")),
        (("利基存储", "NOR Flash", "SLC NAND", "特种存储"), ("利基", "NOR Flash", "SLC NAND", "Specialty Memory", "MCP", "eMCP")),
        (("存储", "AI存储", "国产存储"), ("存储", "HBM", "DRAM", "NAND", "SSD", "TSV", "内存", "Storage", "NOR Flash", "SLC NAND")),
        (("光刻机", "EUV", "DUV", "国产光刻机"), ("光刻", "EUV", "DUV", "ArFi", "High-NA", "TWINSCAN", "SMEE", "曝光", "物镜", "光源")),
        (("半导体设备", "先进制程", "晶圆制造"), ("光刻", "EUV", "DUV", "前道", "制程", "量测", "检测", "曝光", "良率", "先进封装")),
        (("量测设备", "检测设备", "半导体量测"), ("量测", "检测", "Metrology", "Inspection", "缺陷检测", "良率控制", "电子束")),
        (("半导体软件", "计算光刻", "EDA"), ("计算光刻", "OPC", "SMO", "Brion", "EDA", "TCAD", "掩模")),
        (("晶圆代工", "代工", "Foundry"), ("晶圆代工", "Foundry", "先进制程逻辑代工", "成熟/特色工艺", "N3", "N2", "A16", "N28", "N16HV")),
        (("AI算力", "国产GPU", "AI芯片", "GPU", "AI GPU", "DCU"), ("GPU", "DCU", "CUDA", "Blackwell", "Hopper", "AI训练", "AI推理", "算力", "数据中心AI", "HBM", "服务器", "加速芯片", "ASIC", "XPU")),
        (("ASIC", "定制芯片", "AI芯片", "XPU"), ("ASIC", "Custom", "XPU", "定制AI", "Chiplet", "云厂商")),
        (("交换芯片", "以太网", "网络芯片", "UALink"), ("交换芯片", "Ethernet", "Switch", "Teralynx", "Prestera", "UALink", "ESUN")),
        (("存储互连", "PCIe", "CXL", "Retimer"), ("服务器存储连接", "PCIe", "Retimer", "CXL", "FC SAN", "SAS", "RAID", "NVMe-oF")),
        (("无线连接芯片", "WiFi", "蓝牙", "NFC"), ("无线连接", "WiFi", "蓝牙", "NFC", "Wireless Connectivity")),
        (("基础设施软件", "VMware", "虚拟化", "云基础设施"), ("VMware", "虚拟化", "云基础设施", "混合云", "超融合", "vSphere", "vSAN", "NSX")),
        (("车载以太网", "汽车电子芯片"), ("车载以太网", "车规", "汽车电子", "智能网联汽车")),
        (("CoWoS", "硅中介层"), ("CoWoS", "Chip on Wafer on Substrate", "硅中介层", "reticle", "2.5D", "XDFOI")),
        (("SoIC", "混合键合", "3D堆叠"), ("SoIC 3D", "SoIC", "混合键合", "3D堆叠", "face-to-face", "Hybrid Bonding")),
        (("先进封装", "Chiplet"), ("先进封装", "Chiplet", "HBM", "CPO", "die-to-die", "CoWoS", "SoIC", "TSV", "混合键合")),
        (("硅光", "CPO", "COUPE"), ("硅光", "硅光子", "COUPE", "CPO", "Photonic", "光引擎", "光互联")),
        (("成熟制程", "特色工艺", "显示驱动", "DDIC"), ("成熟/特色工艺", "特色工艺", "N28", "N16HV", "BCD", "SOI", "显示驱动", "DDIC")),
        (("GLP-1", "减重药", "肥胖", "代谢疾病"), ("GLP-1", "GIP", "GCG", "Tirzepatide", "Semaglutide", "司美格鲁肽", "替尔泊肽", "口服GLP-1", "减重", "肥胖", "MASH", "Amylin")),
        (("糖尿病", "胰岛素"), ("糖尿病", "胰岛素", "Insulin", "SGLT2", "DPP-4", "GLP-1", "降糖")),
        (("创新药", "生物制药", "MNC"), ("创新药", "生物制药", "肿瘤", "免疫", "罕见病", "诊断", "GLP-1", "ADC", "双抗")),
        (("肿瘤药", "肿瘤", "抗癌", "IO"), ("肿瘤", "Oncology", "血液", "肺癌", "乳腺癌", "PD-1", "PD-L1", "Keytruda", "EGFR", "BTK", "CDK4/6")),
        (("ADC", "抗体偶联"), ("ADC", "抗体偶联", "HER2 ADC", "TROP2", "双抗ADC", "DXd", "Enhertu", "Kadcyla")),
        (("双抗", "双特异性抗体"), ("双抗", "双特异性", "PD-1/VEGF", "CD3×CD20", "TCE", "Tetrabody")),
        (("自免药", "自免", "免疫药"), ("自免", "免疫", "Immunology", "IL-4R", "IL-5", "IL-13", "IL-17", "IL-23", "JAK", "SLE")),
        (("罕见病", "血友病"), ("罕见病", "Rare Disease", "血友病", "补体", "C5", "生长激素", "PNH")),
        (("体外诊断", "IVD", "分子诊断", "病理诊断", "伴随诊断"), ("诊断", "IVD", "中心化诊断", "分子诊断", "POCT", "组织诊断", "病理", "伴随诊断", "NGS", "FMI")),
        (("自动驾驶", "智驾", "车载计算"), ("自动驾驶", "智能驾驶", "DRIVE", "Orin", "Thor", "车载", "域控制器", "智驾芯片")),
        (("机器人", "物理AI", "具身智能", "人形机器人"), ("机器人", "物理AI", "Omniverse", "Isaac", "Cosmos", "GR00T", "仿真", "数字孪生")),
        (("AI PC", "端侧AI", "消费级GPU"), ("AI PC", "RTX", "GeForce", "端侧AI", "游戏", "工作站", "图形GPU")),
        (("AI服务器", "算力", "数据中心"), ("AI服务器", "数据中心", "ASIC", "光互联", "交换芯片", "CXL", "Scale-Up", "Scale-Out")),
    ]
    for aliases, tokens in rules:
        if any(alias in text for alias in aliases):
            return list(tokens)
    return split_terms(term)[:12]


def benchmark_business_line_excluded(term: str, row_text: str) -> bool:
    term_text = str(term or "")
    if any(token in term_text for token in ("存储", "HBM", "SSD", "CXL", "DRAM", "NAND")) and not any(token in term_text for token in ("AEC", "有源电缆", "铜缆")):
        if any(token in row_text for token in ("AEC", "有源电缆", "Active Electrical Cable")):
            return True
    if any(token in term_text for token in ("AI算力", "国产GPU", "AI芯片", "AI GPU", "DCU")) and not any(token in term_text for token in ("自动驾驶", "智驾", "机器人", "AI PC", "端侧AI")):
        if any(token in row_text for token in ("自动驾驶", "车载", "游戏", "AI PC", "GeForce", "机器人", "Physical AI", "Omniverse", "专业可视化")):
            return True
    if "DRAM" in term_text and "HBM" not in term_text:
        if any(token in row_text for token in ("HBM", "High Bandwidth Memory", "高带宽内存")):
            return True
    if "CoWoS" in term_text:
        if "SoIC" in row_text and "CoWoS" not in row_text:
            return True
    if "SoIC" in term_text:
        if any(token in row_text for token in ("COUPE", "CPO", "硅光子")) and "SoIC 3D" not in row_text:
            return True
    if any(token in term_text for token in ("GLP-1", "减重药", "肥胖", "代谢疾病")) and not any(token in term_text for token in ("糖尿病", "胰岛素")):
        if any(token in row_text for token in ("胰岛素/传统糖尿病", "Insulin / Legacy Diabetes", "传统糖尿病")):
            return True
    return False


def front_benchmark_relevant_business_lines(benchmark: dict, term: str, state_text: str, limit: int = 8) -> list[dict]:
    query_tokens = split_terms(" ".join([term, state_text]))[:100]
    focus_tokens = benchmark_focus_tokens(term)
    rows = []
    for row in benchmark.get("benchmark_business_lines", []) or []:
        if not isinstance(row, dict):
            continue
        text = normalize(
            " ".join(
                [
                    str(row.get("business_line") or ""),
                    str(row.get("english_name") or ""),
                    str(row.get("definition") or ""),
                    str(row.get("importance") or ""),
                    " ".join(as_list(row.get("key_products"))),
                    " ".join(as_list(row.get("downstream_applications"))),
                ]
            )
        )
        raw_text = " ".join(
            [
                str(row.get("business_line") or ""),
                str(row.get("english_name") or ""),
                str(row.get("definition") or ""),
                " ".join(as_list(row.get("key_products"))),
            ]
        )
        if benchmark_business_line_excluded(term, raw_text):
            continue
        focus_hit = any(token and context_term_hit(token, text) for token in focus_tokens)
        hit = focus_hit or (not focus_tokens and (context_term_hit(term, text) or any(token and context_term_hit(token, text) for token in query_tokens)))
        if hit:
            rows.append(row)
    return rows[:limit] or [row for row in benchmark.get("benchmark_business_lines", []) or [] if isinstance(row, dict)][: min(4, limit)]


def front_benchmark_relevant_companies(benchmark: dict, term: str, state_text: str, active: list[dict], allowed_business_lines: set[str] | None = None, limit: int = 12) -> list[dict]:
    active_names = {c.get("name") for c in active if c.get("name")}
    query_tokens = split_terms(" ".join([term, state_text]))[:100]
    focus_tokens = benchmark_focus_tokens(term)
    allowed_business_lines = allowed_business_lines or set()
    rows = []
    for row in benchmark.get("mapped_companies", []) or []:
        if not isinstance(row, dict):
            continue
        if not benchmark_mapped_company_is_domestic(row):
            continue
        mapped_line = str(row.get("mapped_business_line") or "")
        raw_text = " ".join(
            [
                mapped_line,
                str(row.get("mapped_business") or ""),
                str(row.get("core_basis") or ""),
                str(row.get("risk_note") or ""),
            ]
        )
        if benchmark_business_line_excluded(term, raw_text):
            continue
        if allowed_business_lines and not any(line and line in mapped_line for line in allowed_business_lines):
            mapped_text_for_focus = normalize(" ".join([mapped_line, str(row.get("mapped_business") or ""), str(row.get("core_basis") or "")]))
            if not any(token and context_term_hit(token, mapped_text_for_focus) for token in focus_tokens):
                continue
        text = normalize(
            " ".join(
                [
                    str(row.get("company") or ""),
                    str(row.get("mapped_business_line") or ""),
                    str(row.get("mapped_business") or ""),
                    str(row.get("mapping_type") or ""),
                    str(row.get("core_basis") or ""),
                ]
            )
        )
        focus_hit = any(token and context_term_hit(token, text) for token in focus_tokens)
        hit = row.get("company") in active_names or focus_hit or (not focus_tokens and (context_term_hit(term, text) or any(token and context_term_hit(token, text) for token in query_tokens)))
        if hit:
            rows.append(row)
    rows.sort(key=lambda r: (-benchmark_row_score(r), str(r.get("company") or "")))
    return rows[:limit]


def front_benchmark_relevant_gaps(benchmark: dict, term: str, state_text: str, limit: int = 8) -> list[dict]:
    rows = []
    query_tokens = split_terms(" ".join([term, state_text]))[:100]
    focus_tokens = benchmark_focus_tokens(term)
    for row in benchmark.get("mapping_gaps", []) or []:
        if not isinstance(row, dict):
            continue
        text = normalize(" ".join(str(row.get(key) or "") for key in ("business_line", "gap_reason", "possible_beneficiary_direction")))
        focus_hit = any(token and context_term_hit(token, text) for token in focus_tokens)
        if focus_hit or (not focus_tokens and (context_term_hit(term, text) or any(token and context_term_hit(token, text) for token in query_tokens))):
            rows.append(row)
    return rows[:limit]


def front_benchmark_map_section(state: dict, active: list[dict], term: str = "") -> str:
    benchmarks = state.get("benchmark_matches", []) or []
    if not benchmarks:
        return "- 暂无可展示的海外龙头对标图谱。"
    state_text = state.get("benchmark_query_text", "")
    chunks = []
    for benchmark in benchmarks[:3]:
        name = benchmark.get("benchmark_company") or "海外龙头"
        ticker = benchmark.get("benchmark_ticker") or ""
        routes = front_unique_join(as_list(benchmark.get("theme_routes")), 8, "")
        chunks.extend(
            [
                f"### {front_compact_text(name, 40)}{('（' + ticker + '）') if ticker else ''}",
                "",
                f"- **对标主题**：{front_compact_text(str(benchmark.get('benchmark_theme') or routes or '待补'), 140)}",
                f"- **可反哺题材**：{routes or '待补'}",
                "",
                "| 海外业务线 | 业务定义 | 关键产品/技术 | 国内映射/受益公司 |",
                "|---|---|---|---|",
            ]
        )
        relevant_companies = benchmark.get("mapped_companies", []) or []
        relevant_companies = [row for row in relevant_companies if isinstance(row, dict) and benchmark_mapped_company_is_domestic(row)]
        business_rows = front_benchmark_relevant_business_lines(benchmark, term, state_text, 8)
        allowed_business_lines = {str(row.get("business_line") or "") for row in business_rows if isinstance(row, dict) and str(row.get("business_line") or "").strip()}
        for business in business_rows:
            if not isinstance(business, dict):
                continue
            line = str(business.get("business_line") or "")
            company_names = [
                str(row.get("company") or "")
                for row in relevant_companies
                if isinstance(row, dict) and line and line in str(row.get("mapped_business_line") or "")
            ]
            if not company_names:
                line_text = normalize(" ".join([line, str(business.get("definition") or ""), " ".join(as_list(business.get("key_products")))]))
                for row in relevant_companies:
                    if not isinstance(row, dict):
                        continue
                    mapped_text = normalize(" ".join([str(row.get("mapped_business_line") or ""), str(row.get("mapped_business") or ""), str(row.get("core_basis") or "")]))
                    if any(token and context_term_hit(token, mapped_text) for token in split_terms(line_text)[:20]):
                        company_names.append(str(row.get("company") or ""))
            chunks.append(
                "| "
                + " | ".join(
                    [
                        front_compact_text(line, 42),
                        front_compact_text(str(business.get("definition") or business.get("importance") or ""), 80),
                        front_compact_text("、".join(as_list(business.get("key_products"))), 80),
                        front_unique_join(company_names, 8, "待补"),
                    ]
                )
                + " |"
            )
        companies = front_benchmark_relevant_companies(benchmark, term, state_text, active, allowed_business_lines, 12)
        if companies:
            chunks.extend(["", "| 国内公司 | 映射业务线 | 映射类型 | 映射依据 | 风险边界 |", "|---|---|---|---|---|"])
            for company in companies:
                chunks.append(
                    "| "
                    + " | ".join(
                        [
                            front_compact_text(str(company.get("company") or ""), 30),
                            front_compact_text(str(company.get("mapped_business_line") or ""), 44),
                            front_compact_text(str(company.get("mapping_type") or company.get("mapping_strength") or ""), 38),
                            front_compact_text(str(company.get("core_basis") or ""), 80),
                            front_compact_text(str(company.get("risk_note") or ""), 70),
                        ]
                    )
                    + " |"
                )
        gaps = front_benchmark_relevant_gaps(benchmark, term, state_text, 6)
        if gaps:
            chunks.extend(["", "| 国内缺口/空白映射 | 为什么缺 | 可发散方向 |", "|---|---|---|"])
            for gap in gaps:
                chunks.append(
                    "| "
                    + " | ".join(
                        [
                            front_compact_text(str(gap.get("business_line") or ""), 42),
                            front_compact_text(str(gap.get("gap_reason") or ""), 90),
                            front_compact_text(str(gap.get("possible_beneficiary_direction") or ""), 80),
                        ]
                    )
                    + " |"
                )
        chunks.append("")
    return "\n".join(chunks).rstrip()


def build_front_map_report(term: str, vault: Path, definition: str = "", context: dict | None = None, theme_info_rows: list[dict] | None = None, theme_direction_pool: dict | None = None, theme_supplement_pool: dict | None = None, review_context: dict | None = None) -> str:
    state = build_theme_state(term, vault, definition, context, theme_info_rows, theme_direction_pool, theme_supplement_pool)
    context = state["context"]
    companies = state["companies"]
    profile = state.get("direction_profile")
    for company in companies:
        company["deep_dive_term"] = term
        company["direction_frame"] = context.get("direction_frame", {}) if isinstance(context, dict) else {}
    anchor = front_theme_anchor(term, state["definition"], context)
    active = [c for c in companies if company_deep_dive_tier(c) != "weak"]
    lines = [
        f"# {term} 题材信息地图",
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        "## 1. 核心信号",
        "",
        front_review_trigger_section(review_context, active, term),
        "",
        "## 2. 雷达速览",
        "",
        radar_digest_section(state),
        "",
        "## 3. 一句话定锚",
        "",
        anchor,
        "",
        "### Wiki 概念知识卡",
        "",
        wiki_concept_knowledge_section(state),
        "",
        "## 4. 为什么值得展开",
        "",
        bullets(front_driver_items(context, active, 5), "待补发酵驱动"),
        "",
        "## 5. 产业链全景图",
        "",
        front_chain_map_section(active, term, context, profile),
        "",
        "## 6. 细分方向扫描",
        "",
        front_subdirection_digest_section(state, 22),
        "",
        "## 7. 工艺/材料/零部件扫描",
        "",
        front_material_process_radar_section(state, active, term, profile, 28),
        "",
        "## 8. 公司地图",
        "",
        "### 主线公司",
        "",
        front_company_cards_section(active, "relative_core", term, profile, 8),
        "",
        "### 相关公司",
        "",
        front_company_cards_section(active, "related", term, profile, 8),
        "",
        "### 延伸公司",
        "",
        front_company_cards_section(active, "watch", term, profile, 8),
        "",
        "## 9. 海外龙头对标图谱",
        "",
        front_benchmark_map_section(state, active, term),
        "",
        "## 10. 本地合成研究洞察",
        "",
        synthesis_insights_section(state),
        "",
        "## 11. 个股逻辑卡与上下游发散",
        "",
        front_logic_card_expansion_section(active, term, profile, 18),
        "",
        "## 12. 如何反哺复盘",
        "",
        front_review_feedback_section(state, active, term, profile, 10),
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


BRIEF_TIER_LABELS = {"relative_core": "核心", "related": "相关", "watch": "延伸"}


def brief_clip_section(raw: str, max_lines: int = 26) -> str:
    text = strip_wiki_links(str(raw or "")).strip()
    if not text:
        return ""
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines[:max_lines]).strip()


def brief_primary_page_sections(vault: Path, primary: str) -> dict:
    if not primary:
        return {}
    path = vault / "concepts" / f"{primary}.md"
    if not path.exists():
        return {}
    _meta, body = read_wiki_page(path, 12000)
    out = {}
    for key, names in (
        ("tech", ("技术路线", "技术拆解", "技术分层", "技术路径")),
        ("chain", ("产业链", "产业链全景", "产业链结构")),
        ("market", ("市场数据", "市场规模", "市场格局", "供需格局")),
    ):
        raw = brief_clip_section(wiki_section_raw(body, names))
        if raw:
            out[key] = raw
    return out


def brief_subconcept_segments(term: str, state: dict, vault: Path, limit: int = 12, per_segment: int = 10) -> list[dict]:
    graph = state.get("graph", {}) or {}
    concepts = graph.get("concepts", {}) or {}
    scope = {s for s in set(state.get("match_scope") or []) | {term, str(state.get("primary") or "")} if s}
    exposures = load_json(vault / "relations" / RELATION_FILES["entity_exposures"], {"entities": {}})
    candidates = set(concepts.keys())
    for ent in (exposures.get("entities") or {}).values():
        candidates |= set((ent.get("concepts") or {}).keys())
    con_dir = vault / "concepts"
    if con_dir.exists():
        candidates |= {p.stem for p in con_dir.glob("*.md")}
    names = set()
    for name in candidates:
        if not name or name in scope:
            continue
        if any(s in name for s in scope):
            names.add(name)
            continue
        parents = (concepts.get(name) or {}).get("parent_concepts") or []
        if any(p in scope for p in parents):
            names.add(name)
    segments = []
    for name in sorted(names):
        rows = []
        for ent_name, ent in (exposures.get("entities") or {}).items():
            con = (ent.get("concepts") or {}).get(name)
            if not isinstance(con, dict):
                continue
            rows.append({
                "name": ent_name,
                "strength": str(con.get("strength") or ""),
                "roles": [str(con.get("role") or "")] if con.get("role") else [],
            })
        anchor = ""
        page = vault / "concepts" / f"{name}.md"
        if page.exists():
            _meta, body = read_wiki_page(page, 2500)
            match = re.search(r"\*\*一句话\*\*[:：]\s*(.+)", body)
            if not match:
                match = re.search(r"^#\s+.+?$\n+(.+?)(?=\n\*\*|\n#)", body, re.S | re.M)
            if match:
                anchor = squeeze_text(strip_wiki_links(match.group(1)), 120)
            if "占位概念页" in anchor:
                anchor = ""
        if not rows and not anchor:
            continue
        rows.sort(key=lambda r: (0 if r.get("strength") == "core" else 1, r.get("name", "")))
        rows = rows[:per_segment]
        enrich_companies_with_wiki_pages(vault, rows)
        segments.append({"name": name, "anchor": anchor, "companies": rows})
    segments.sort(key=lambda s: -len(s["companies"]))
    return segments[:limit]


def brief_definition_section(state: dict, term: str) -> str:
    context = state.get("context", {}) or {}
    cards = [c for c in (state.get("wiki_concept_cards") or []) if not c.get("missing")]
    primary = state.get("primary")
    cards = sorted(cards, key=lambda c: 0 if c.get("name") == primary else 1)
    primary_card = cards[0] if cards and cards[0].get("name") == primary else None
    anchor = ""
    if primary_card:
        anchor = front_compact_text(primary_card.get("one_liner") or primary_card.get("definition") or "", 160)
    if not anchor:
        fallback = front_theme_anchor(term, state.get("definition", ""), context)
        if fallback and not is_junk_definition(fallback):
            anchor = front_compact_text(fallback, 160)
    lines = []
    if anchor:
        lines.append(f"**一句话定锚**：{anchor}")
    if primary_card:
        logic = front_compact_text(primary_card.get("core_logic") or "", 320)
        if logic and "待补" not in logic:
            lines.append("")
            lines.append(f"**核心逻辑**：{logic}")
    page_sections = state.get("brief_page_sections", {}) or {}
    if page_sections.get("tech"):
        lines.append("")
        lines.append("**技术路线（wiki 概念页）**")
        lines.append("")
        lines.append(page_sections["tech"])
    if page_sections.get("market"):
        lines.append("")
        lines.append("**市场数据（wiki 概念页）**")
        lines.append("")
        lines.append(page_sections["market"])
    related_cards = [c for c in cards if c is not primary_card]
    if related_cards:
        lines.append("")
        lines.append("**相关概念**")
        lines.append("")
        for card in related_cards[:4]:
            name = card.get("name", "")
            one = front_compact_text(card.get("one_liner") or card.get("definition") or "", 140)
            updated = f"，更新 {card.get('updated')}" if card.get("updated") else ""
            lines.append(f"- **{name}**（wiki 概念页{updated}）：{one or '待补定锚'}")
            logic = front_compact_text(card.get("core_logic") or "", 220)
            if logic and "待补" not in logic:
                lines.append(f"  - 核心逻辑：{logic}")
    return "\n".join(lines) or "- 暂无可用定义，建议先补 wiki 概念页。"


def brief_chain_section(state: dict, active: list[dict], term: str, profile: dict | None) -> str:
    context = state.get("context", {}) or {}
    rows = front_chain_rows(active, term, context, profile, 12)
    page_sections = state.get("brief_page_sections", {}) or {}
    page_chain = ""
    if page_sections.get("chain"):
        page_chain = "**Wiki 沉淀产业链（概念页）**\n\n" + page_sections["chain"]
    if not rows:
        return page_chain or "- 暂无可展示的产业链节点。"
    tree = front_chain_tree_section(term, rows, context)
    if page_chain:
        tree = page_chain + "\n\n**图谱产业链分布（entity_exposures）**\n\n" + tree if tree else page_chain
    stage_order = ["下游需求/应用", "中游产品/制造", "上游材料", "上游设备", "配套服务/生态"]
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.get("stage", ""), []).append(row)
    lines = [tree, ""] if tree else []
    downstream_items = context_chain_items(context, "downstream", 6)
    if downstream_items:
        lines.append(f"- **终端需求**：{front_unique_join(downstream_items, 6, '待补')}")
    for stage in stage_order:
        for row in grouped.get(stage, []):
            bucket = row.get("bucket", "")
            companies = front_compact_text(row.get("companies", ""), 110)
            roles = front_compact_text(row.get("roles", ""), 90)
            line = f"- **{stage}｜{bucket}**：{companies}"
            if roles and roles != "待补":
                line += f"（看点：{roles}）"
            lines.append(line)
    return "\n".join(lines)


def brief_material_scan_section(state: dict, active: list[dict], term: str, profile: dict | None, limit: int = 20) -> str:
    rows = front_material_scan_rows(state)
    sub_segments = state.get("brief_sub_segments", []) or []
    if not rows and not sub_segments:
        return "- 暂无可展示的工艺/材料细分扫描。"
    lines = []
    seen = set()
    for seg in sub_segments:
        name = str(seg.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        lines.append(f"- **{front_compact_text(name, 46)}**｜wiki 细分概念")
        if seg.get("anchor"):
            lines.append(f"  - 定锚：{front_compact_text(seg['anchor'], 120)}")
        names = [c.get("name", "") for c in seg.get("companies", [])]
        if names:
            lines.append(f"  - 代表公司：{front_unique_join(names, 10)}")
    for row in rows:
        name = str(row.get("name") or row.get("direction") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        position = front_compact_text(str(row.get("chain_position") or row.get("layer") or row.get("major_track") or ""), 40)
        logic = front_compact_text(
            str(row.get("core_catalyst") or row.get("prosperity_judgment") or row.get("prosperity_reason") or row.get("evidence_summary") or row.get("next_validation") or ""),
            120,
        )
        matches = front_material_company_matches(row, active, term, profile, 8)
        companies = front_unique_join(as_list(row.get("representative_entities")) + [c.get("name", "") for c in matches], 8)
        header = f"- **{front_compact_text(name, 46)}**"
        if position:
            header += f"｜{position}"
        lines.append(header)
        if logic:
            lines.append(f"  - 逻辑：{logic}")
        lines.append(f"  - 代表公司：{companies}")
        if len(seen) >= limit:
            break
    return "\n".join(lines)


def brief_segment_companies(row: dict, active: list[dict]) -> list[dict]:
    explicit = {str(x).strip() for x in re.split(r"[、,，\s]+", map_clean_plain(row.get("companies"), limit=200)) if str(x).strip()}
    term_names = {str(x).strip() for x in map_companies_for_term(active, str(row.get("subdir") or ""), 10).split("、") if str(x).strip()}
    names = explicit | term_names
    matched = [c for c in active if c.get("name") in names]
    tier_rank = {"relative_core": 0, "related": 1, "watch": 2}
    matched = [c for c in matched if company_deep_dive_tier(c) in tier_rank]
    return sorted(unique_by_name(matched), key=lambda c: (tier_rank.get(company_deep_dive_tier(c), 3), company_sort_key(c)))


def brief_segment_core_companies_section(state: dict, active: list[dict], term: str, profile: dict | None, limit: int = 14, per_segment: int = 8) -> str:
    chunks = []
    seen = set()
    seen_company_sets: list[frozenset] = []
    active_by_name = {c.get("name"): c for c in active}
    for seg in state.get("brief_sub_segments", []) or []:
        name = str(seg.get("name") or "").strip()
        companies = seg.get("companies", [])
        if not name or name in seen or not companies:
            continue
        name_set = frozenset(c.get("name", "") for c in companies)
        if any(name_set <= prev for prev in seen_company_sets):
            continue
        seen.add(name)
        seen_company_sets.append(name_set)
        lines = [f"### {name}（wiki 细分概念）", "", "| 公司 | 暴露 | 一句话定位（wiki） |", "|---|---|---|"]
        for company in companies[:per_segment]:
            strength = "核心" if company.get("strength") == "core" else "相关"
            merged = active_by_name.get(company.get("name")) or company
            one = front_compact_text(merged.get("wiki_one_liner") or "", 80) or front_compact_text("、".join(company.get("roles", [])) or "待补", 60)
            lines.append(f"| {company.get('name', '')} | {strength} | {one} |")
        chunks.append("\n".join(lines))
    for row in map_subdirection_rows(state):
        subdir = map_clean_plain(row.get("subdir"), limit=70) or map_clean_plain(row.get("layer"), limit=70)
        if not subdir or subdir in seen or subdir == "待细分":
            continue
        companies = brief_segment_companies(row, active)
        if not companies:
            continue
        name_set = frozenset(c.get("name", "") for c in companies)
        if any(name_set <= prev for prev in seen_company_sets):
            continue
        seen_company_sets.append(name_set)
        seen.add(subdir)
        lines = [f"### {subdir}", "", "| 公司 | 分层 | 一句话定位（wiki） |", "|---|---|---|"]
        for company in companies[:per_segment]:
            tier = BRIEF_TIER_LABELS.get(company_deep_dive_tier(company), "延伸")
            one = front_compact_text(company.get("wiki_one_liner") or "", 80) or front_compact_text(themed_company_roles(company, term), 60)
            lines.append(f"| {company.get('name', '')} | {tier} | {one} |")
        chunks.append("\n".join(lines))
        if len(seen) >= limit:
            break
    if not chunks:
        return "- 暂无可映射的细分核心个股。"
    return "\n\n".join(chunks)


def build_brief_report(term: str, vault: Path, definition: str = "", context: dict | None = None, theme_info_rows: list[dict] | None = None, theme_direction_pool: dict | None = None, theme_supplement_pool: dict | None = None) -> str:
    state = build_theme_state(term, vault, definition, context, theme_info_rows, theme_direction_pool, theme_supplement_pool)
    context = state["context"]
    companies = state["companies"]
    profile = state.get("direction_profile")
    for company in companies:
        company["deep_dive_term"] = term
        company["direction_frame"] = context.get("direction_frame", {}) if isinstance(context, dict) else {}
    active = [c for c in companies if company_deep_dive_tier(c) != "weak"]
    state["brief_page_sections"] = brief_primary_page_sections(vault, str(state.get("primary") or term))
    state["brief_sub_segments"] = brief_subconcept_segments(term, state, vault)
    lines = [
        f"# {term} 题材速读",
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        "## 一、题材定义",
        "",
        brief_definition_section(state, term),
        "",
        "## 二、产业链上下游",
        "",
        brief_chain_section(state, active, term, profile),
        "",
        "## 三、工艺与材料细分扫描",
        "",
        brief_material_scan_section(state, active, term, profile),
        "",
        "## 四、各细分核心个股",
        "",
        brief_segment_core_companies_section(state, active, term, profile),
        "",
        "## 数据边界",
        "",
        "- 数据全部来自 wiki 知识库（concepts/entities/relations/synthesis）与已入库研报上下文，只读不回写。",
        "- 公司分层：核心=主线承接，相关=逻辑可解释，延伸=有线索待验证；不构成交易建议。",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_deep_dive_report(term: str, vault: Path, definition: str = "", context: dict | None = None, theme_info_rows: list[dict] | None = None, theme_direction_pool: dict | None = None, theme_supplement_pool: dict | None = None) -> str:
    state = build_theme_state(term, vault, definition, context, theme_info_rows, theme_direction_pool, theme_supplement_pool)
    context = state["context"]
    companies = state["companies"]
    for company in companies:
        company["deep_dive_term"] = term
        company["direction_frame"] = context.get("direction_frame", {}) if isinstance(context, dict) else {}
    definition_profile = context.get("definition_profile", {}) if isinstance(context, dict) and isinstance(context.get("definition_profile"), dict) else {}
    state_definition = state["definition"].strip()
    supplement_anchor = str(definition_profile.get("one_line_anchor", "")).strip()
    explicit_definition = bool(definition.strip())
    if explicit_definition:
        definition_text = definition.strip()
    elif supplement_anchor:
        definition_text = supplement_anchor
    else:
        definition_text = state_definition or context_definition(context) or f"{term}：待从 full 精读/PDF ingest 中补一句话定锚。"
    return f"""# {term} 题材深拆

生成日期：{date.today().isoformat()}

## 雷达速览

{radar_digest_section(state)}

## 一、一句话定锚

{definition_text}

### Wiki 概念知识卡

{wiki_concept_knowledge_section(state)}

## 二、为什么现在发酵

{fermentation_signal_section(context, state.get("signal", {}), companies)}

### 基础需求拆解

{demand_drivers_section(context)}

### 需求-瓶颈-环节传导表

{demand_bottleneck_map_section(context, companies, state.get("direction_profile"))}

### 需求场景表

{demand_scenarios_section(context)}

## 三、产业链全景图

{industry_chain_panorama_section(context, companies, state.get("direction_profile"))}

### IMA/Obsidian 统一信息池：细颗粒地图与上下游关系

{theme_information_pool_section(context)}

### 标准细分方向池：方向级中间层

{theme_direction_pool_section(context)}

### Theme Radar 补充数据池：截图功能对齐层

{theme_supplement_pool_section(context)}

### 本地 full 精读 / report_contexts 上下文

{report_contexts_section(state["display_report_contexts"], state.get("primary") or state.get("term") or "")}

## 四、细分方向扫描

{direction_radar_matrix_section(context, companies, state.get("direction_profile"))}

### 原始方向扫描

{direction_scan_section(context)}

### 工艺/材料/零部件扫描

{inferred_material_process_scan_section(context, companies, state.get("direction_profile"))}

### 降权但保留的背景/生态线索

{secondary_runtime_context_section(context)}

## 五、共振分层：主信源 × 产业链 × 公司逻辑

{resonance_tiers_section(context, companies)}

## 六、full 精读提及/生态线索

{report_context_company_clues_section(state["display_report_contexts"])}

## 七、发酵进度与预期差

{direction_progress_ranking_section(context, companies, state.get("direction_profile"))}

### 认知演变时间线

{recognition_timeline_section(context)}

### 多方向发酵进度横向对比

{progress_ruler_section(context)}

### 跟踪优先级

{opportunity_priorities_section(context)}

### 证据追踪表

{evidence_trace_section(context)}

### 补充数据证据表

{supplement_evidence_section(context)}

### 催化日历

{catalyst_calendar_section(context, companies, state.get("direction_profile"))}

## 本地合成研究洞察（wiki/synthesis）

{synthesis_insights_section(state)}

## 八、相对核心个股逻辑卡

{deep_company_cards_section(companies, "relative_core", term=state.get("primary") or state.get("term") or "", has_structured_supplement=state.get("has_structured_supplement", False))}

## 九、重点相关个股逻辑卡

{deep_company_cards_section(companies, "related", term=state.get("primary") or state.get("term") or "", has_structured_supplement=state.get("has_structured_supplement", False))}

### 近期 IMA 个股逻辑卡观察池

{recent_ima_logic_card_pool_section(companies, term=state.get("primary") or state.get("term") or "")}

## 十、观察/弹性与弱相关隔离

### 观察/弹性

{deep_company_cards_section(companies, "watch", limit=8, term=state.get("primary") or state.get("term") or "", has_structured_supplement=state.get("has_structured_supplement", False))}

### 弱相关/暂不作为核心

{"- 结构化补充池已接入，弱相关公司线索默认不展开，避免泛概念或跨主题弱线索污染。" if state.get("has_structured_supplement") else deep_company_cards_section(companies, "weak", limit=8, term=state.get("primary") or state.get("term") or "", has_structured_supplement=False)}

## 十一、验证清单

### 细分方向专属验证

{subdirection_validation_section(companies)}

### 通用验证

{validation_checklist_section(context, companies, state.get("direction_profile"))}

## 十二、核心结论

### 操作建议汇总

{action_plan_section(context)}

### 结论摘要

{deep_dive_conclusion(term, context, companies)}

## 十三、底层题材雷达护栏摘要

{deep_dive_governance_section(companies)}

### 深拆质量门禁

{deep_dive_quality_gate_section(context, companies)}

## 十四、数据来源与边界

- 主信源：PDF ingest 研报、精选逻辑/脱水文本、full 精读/report_contexts。
- wiki 页面层：concepts 概念页（定锚/核心逻辑）、entities 实体页（一句话定位/更新时间）、synthesis 合成研究（历史分析快照），全部只读接入，不回写。
- baseline：只做公司基础画像和主营业务是否冲突的辅助校验。
- full 精读：只用于题材定义、产业链上下游、关键环节和细分方向，不写入 entities，也不直接升级公司事实。
- 公告/订单/业绩：当前仅作为后续验证空位，不作为高权重核心判断。
- 输出方式：不做个股排名，不展示分数，只做相对核心/重点相关/观察/弱相关分层与逻辑解释。
"""


def md_cell(value, limit: int = 120) -> str:
    text = compact_text(str(value or ""), limit)
    replacements = {
        "推荐": "提及",
        "买入": "买方动作",
        "卖出": "卖方动作",
        "最优先": "第一类",
        "次优先": "第二类",
        "强烈关注": "重点记录",
        "操作建议": "后续信息",
        "交易机会": "市场表述",
        "权重": "占比字段",
        "打分": "分项记录",
        "评分": "分项记录",
        "发酵强度": "关注热度",
        "预期差排序": "差异信息列表",
        "弹性最大": "弹性描述",
        "最强标的": "相关公司",
        "个股投资价值": "公司信息",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.replace("|", "/") or "待补"


def map_sources(*values, limit: int = 120) -> str:
    items = []
    for value in values:
        items.extend(as_list(value))
    return md_cell("、".join(unique(items)) or "待补", limit)


def map_flat_terms(*values, limit: int = 16) -> list[str]:
    out = []

    def visit(value):
        if value is None:
            return
        if isinstance(value, dict):
            for key in ("name", "direction", "segment", "scenario", "layer", "chain_position"):
                if value.get(key):
                    visit(value.get(key))
                    return
            for item in value.values():
                visit(item)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)
            return
        for item in as_list(value):
            text = str(item or "").strip()
            if text and text != "待补":
                out.append(text)

    for value in values:
        visit(value)
    return unique(out)[:limit]


def map_clean_plain(value, limit: int = 0) -> str:
    values = []
    source_items = value if isinstance(value, list) else [value]
    for item in source_items:
        text = str(item or "").strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"（[^）]*\[\[[^）]*\]\][^）]*）", "", text)
        text = re.sub(r"\[\[[^\]]+\]\]", "", text)
        text = text.replace("从既有entity markdown重建", "")
        text = text.replace("从既有concept markdown重建", "")
        text = text.replace("从既有entitymarkdown重建", "")
        text = text.replace("从既有conceptmarkdown重建", "")
        text = text.replace("图谱弱关联", "延伸线索")
        text = text.replace("弱关联观察", "延伸观察")
        text = text.replace("市场信号弱关联", "延伸线索")
        text = text.replace("待公告验证", "需公告验证")
        text = text.replace("mootdxF10主营业务显示：", "主营业务显示：")
        text = text.replace("iFinD摘要显示公司", "公司")
        text = text.replace("iFinD摘要显示", "")
        text = text.replace("iFinD主营业务为：", "主营业务为：")
        text = text.replace("AkShare公开资料显示、", "")
        text = text.replace("iFinD", "")
        text = text.replace("AkShare", "")
        text = text.replace("mootdx", "")
        text = text.replace("F10主营业务显示：", "主营业务显示：")
        text = text.replace("摘要显示公司", "公司")
        text = text.replace("摘要显示", "")
        text = text.replace("公开资料显示、", "")
        text = text.replace("公开资料显示", "")
        text = text.replace("基础主营支持", "主营业务涉及")
        text = text.replace("主要核心主业明确为", "主要业务为")
        text = text.replace("基础资料未直接给出相关产品或收入", "相关产品或收入口径需要继续确认")
        text = text.replace("实体概念映射包含", "概念映射涉及")
        text = text.replace("既有边际变化", "产业链线索")
        text = text.replace("存储芯片属性来自产业链线索、", "产业链线索显示，")
        text = text.replace("存储芯片属性来自产业链线索，", "产业链线索显示，")
        text = text.replace("需后续公告、年报、研报证据交叉验证", "产品与业务口径需继续确认")
        text = text.replace("公告验证", "事实验证")
        text = re.sub(r"^[（(][^）)]*(风口研报|调研日报|市场逻辑|强势脱水|脱水研报)[^）)]*[）)]", "", text)
        text = re.sub(r"[（(][^）)]*(风口研报|调研日报|市场逻辑|强势脱水|脱水研报)[^）)]*[）)]", "", text)
        text = re.sub(r"[（(]\d{4}[^）)]*(风口|调研|强势|脱水|需事实验证|需公告验证).*", "", text)
        text = re.sub(r"\b\d{4}[^：:]{0,30}[：:]", "", text)
        text = re.sub(r"(风口研报|调研日报|强势脱水|市场逻辑精选)[0-9一二三四五六七八九十]*[：:]", "", text)
        text = re.sub(r"\d{4}[^：]{0,20}(风口研报|调研日报|强势脱水|市场逻辑精选)[^：]*：", "", text)
        text = re.sub(r"第三方机构[^、，：]{0,12}(覆盖|称)", "", text)
        text = re.sub(r"第三方机构[^、，。；;：:]{0,20}(覆盖|称)", "", text)
        if "是否被更多研报" in text or "能否落到明确产品" in text:
            continue
        text = text.replace("后续跟踪", "")
        text = re.sub(r"^(存储芯片|先进封装|半导体设备|晶圆代工|利基存储|半导体材料|半导体量检测设备)[：:]", "", text)
        text = text.replace("由公司子方向归集", "由公司角色和产品方向归集")
        text = re.sub(r"（\s*[、,，;；]*\s*）", "", text)
        text = text.strip(" ；;，,。、")
        if not text or text in {"待补", "missing", "暂无明显缺口"}:
            continue
        if text in {"由公司角色和产品方向归集", "围绕需求、产品、工艺和公司映射继续展开"}:
            continue
        if any(token in text for token in ("既有raw", "既有entity", "既有concept", "不直接证明", "仅支持主营业务基础")):
            continue
        if any(token in text for token in ("report_contexts", "entity_exposures", "evidence_index", "concept_graph", "theme_supplement_pool", "direction_scan", "material_process_scan", "aliases.json", "context.", "从既有")):
            continue
        if "待判定" in text or "待细分" in text:
            continue
        values.append(text)
    text = "、".join(unique(values))
    if limit and text:
        text = compact_text(text, limit)
    text = text.replace("（、）", "").replace("（，）", "").replace("(、)", "")
    return text


def map_clean_display(value, default: str = "—", limit: int = 120) -> str:
    text = map_clean_plain(value, limit=limit)
    return md_cell(text if text else default, limit)


def map_blank_display(value, limit: int = 120) -> str:
    text = map_clean_plain(value, limit=limit)
    return md_cell(text, limit) if text else ""


def map_wiki_name(value, limit: int = 80) -> str:
    text = map_clean_plain(strip_wikilink(str(value or "")), limit=limit)
    text = text.replace("[[", "").replace("]]", "").replace("|", "/").strip()
    return text


def map_wiki_link(value, limit: int = 80) -> str:
    text = map_wiki_name(value, limit=limit)
    return f"[[{text}]]" if text else ""


def map_wiki_join(values, limit: int = 12) -> str:
    items = []
    for item in as_list(values):
        link = map_wiki_link(item)
        if link:
            items.append(link)
    return "、".join(unique(items)[:limit])


def map_wiki_path(*values) -> str:
    items = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            for item in value:
                link = map_wiki_link(item)
                if link:
                    items.append(link)
        else:
            link = map_wiki_link(value)
            if link:
                items.append(link)
    return " → ".join(unique(items))


def map_first_clean(values, limit: int = 120) -> str:
    for item in as_list(values):
        text = map_clean_plain(item, limit=limit)
        if text:
            return text
    return ""


def map_context_chain_terms(context: dict, key: str, limit: int = 12) -> list[str]:
    chain = context.get("industry_chain_map", {}) if isinstance(context, dict) else {}
    if not isinstance(chain, dict):
        return []
    return map_flat_terms(chain.get(key, []), limit=limit)


def map_report_chain_terms(report_rows: list[dict], key: str, limit: int = 12) -> list[str]:
    values = []
    for row in report_rows or []:
        if not isinstance(row, dict):
            continue
        supply = row.get("supply_chain", {}) if isinstance(row.get("supply_chain"), dict) else {}
        values.extend(map_flat_terms(supply.get(key, []), limit=limit))
    return unique(values)[:limit]


def map_companies_for_term(companies: list[dict], term: str, limit: int = 6) -> str:
    needle = normalize(term)
    if not needle:
        return ""
    names = []
    for company in companies or []:
        haystack = normalize(
            " ".join(
                str(x)
                for x in (
                    company.get("roles", [])
                    + company.get("evidence", [])
                    + company.get("concepts", [])
                    + company_subdirections(company)
                )
            )
        )
        if needle in haystack:
            names.append(company.get("name", ""))
    return "、".join(unique(names)[:limit])


def map_company_names_for_directions(companies: list[dict], profile: dict | None, directions: set[str], subtypes: set[str] | None = None, limit: int = 8) -> str:
    names = []
    subtypes = subtypes or set()
    for company in companies or []:
        direction = company_direction_key(company, profile)
        subtype = company.get("company_subtype") or company_subtype(company)
        if direction in directions or subtype in subtypes:
            names.append(company.get("name", ""))
    return "、".join(unique(names)[:limit])


def map_generic_demand_row(row: dict) -> bool:
    text = " ".join(str(row.get(key) or "") for key in ("logic", "transmission_logic", "evidence_summary", "process_requirement", "next_validation"))
    return any(token in text for token in ("来自已精读full.md", "需映射到中游核心环节", "补需求到具体环节", "待映射到"))


def map_theme_keyword_text(state: dict) -> str:
    context = state.get("context", {}) or {}
    report_rows = state.get("local_report_contexts", []) or []
    values = []
    values.extend(map_flat_terms(context.get("demand_drivers"), context.get("capability_stack"), context.get("direction_scan"), context.get("material_process_scan"), limit=80))
    for row in report_rows:
        if isinstance(row, dict):
            values.extend(map_flat_terms(row.get("related_concepts"), row.get("supply_chain"), row.get("summary"), limit=80))
    for company in state.get("companies", []) or []:
        values.extend(map_flat_terms(company.get("roles"), company.get("evidence"), company.get("concepts"), company_subdirections(company), limit=80))
    return " ".join(unique(values))


def map_inferred_demand_engine_rows(state: dict, limit: int = 8) -> list[dict]:
    context = state.get("context", {}) or {}
    theme_text = " ".join(str(x or "") for x in (state.get("term"), state.get("primary"), state.get("definition"), context_definition(context)))
    text = map_theme_keyword_text(state)
    companies = state.get("companies", []) or []
    rules = [
        (("存储", "HBM", "DRAM", "NAND", "NOR"), ("AI服务器", "GPU", "数据中心", "推理", "算力", "HBM"), "AI算力/数据中心", "AI服务器、GPU和推理算力提升带来容量、带宽和功耗约束。", "HBM、DDR5、企业级SSD、先进封装/封测、核心材料", ("HBM", "DDR5", "SSD", "NAND", "先进封装")),
        (("存储", "HBM", "DRAM", "NAND", "NOR"), ("HBM", "DDR5", "LPDDR5", "DRAM"), "高带宽/高速内存升级", "存储带宽、容量和功耗要求提升，推动内存产品代际切换。", "HBM、DDR5、LPDDR、接口芯片、封测", ("HBM", "DDR5", "LPDDR", "DRAM")),
        (("存储", "HBM", "DRAM", "NAND", "NOR"), ("NAND", "3DNAND", "SSD", "QLC", "UFS"), "NAND/SSD容量升级", "终端与数据中心容量需求提升，牵引NAND、SSD、主控与封测环节。", "NAND、SSD、主控、封测、硅片/材料", ("NAND", "SSD", "UFS", "3DNAND")),
        (("存储", "HBM", "DRAM", "NAND", "NOR"), ("NOR", "EEPROM", "MCU", "车规", "汽车电子", "工业控制", "物联网"), "利基存储/车规与工控", "汽车电子、工业控制和物联网场景更重视可靠性、长周期供货和小容量存储。", "NOR、EEPROM、车规存储、控制芯片", ("NOR", "EEPROM", "车规", "汽车")),
        (("光模块", "光通信", "光芯片", "CPO", "硅光"), ("1.6T", "800G", "光模块", "CPO", "硅光", "EML", "VCSEL"), "AI集群网络升级", "AI集群带宽升级带动高速光模块、光芯片和封装配套需求。", "光模块、光芯片、硅光/CPO、PCB/封装材料", ("光模块", "CPO", "硅光", "EML", "VCSEL")),
        (("创新药", "医药", "Biotech", "药"), ("临床", "BD", "医保", "NMPA", "FDA", "License", "管线", "双抗", "ADC", "GLP"), "临床/商业化/BD节点", "管线进展、医保准入、出海授权和商业化放量构成创新药主要信息节点。", "临床阶段、适应症、审批、BD、销售收入", ("临床", "BD", "医保", "管线", "ADC")),
        (("光伏", "硅料", "硅片", "组件", "逆变器"), ("TOPCon", "BC电池", "钙钛矿", "硅片", "组件", "逆变器", "储能", "海外"), "光伏技术迭代与出海需求", "电池片技术、组件价格、海外装机和储能配套共同影响产业链环节。", "硅料/硅片、电池片、组件、逆变器、储能", ("TOPCon", "BC", "钙钛矿", "组件", "逆变器")),
    ]
    rows = []
    for domain_tokens, tokens, scenario, logic, process, company_terms in rules:
        if not any(token in theme_text for token in domain_tokens):
            continue
        if not any(token in text for token in tokens):
            continue
        names = []
        for term in company_terms:
            names.extend(as_list(map_companies_for_term(companies, term, 4)))
        rows.append(
            {
                "scenario": scenario,
                "logic": logic,
                "process": process,
                "companies": "、".join(unique(names)[:6]) or "待补",
                "source": "report_contexts/entity_exposures/关键词归纳",
                "gap": "补原文段落、公司产品、客户和量化字段",
            }
        )
    return rows[:limit]


def map_existing_report_files(term: str, limit: int = 6) -> list[str]:
    ima_dir = Path("/Users/a77/Desktop/c c/ima")
    if not ima_dir.exists():
        return []
    patterns = [
        f"*{term}*ThemeRadar*DeepDive*接入补充池*.md",
        f"*{term}*ThemeRadar*.md",
    ]
    files = []
    for pattern in patterns:
        files.extend(str(path) for path in ima_dir.glob(pattern) if path.is_file())
    return unique(files)[:limit]


def map_bucket_text(company: dict) -> str:
    buckets = company.get("evidence_buckets", {}) or {}
    labels = {
        "baseline": "baseline",
        "curated_research": "curated_research",
        "delta": "delta",
        "graph_only": "graph_only",
        "missing": "missing",
    }
    parts = [labels[key] for key in EVIDENCE_BUCKETS if buckets.get(key)]
    return "、".join(parts) or "missing"


def map_company_gap(company: dict) -> str:
    labels = {
        "graph_only_only": "仅图谱关联",
        "missing_evidence": "证据待补",
        "chain_layer_conflict": "链层冲突待复核",
        "weak_granularity": "颗粒度待补",
        "soft_fact_hardness": "事实硬度待复核",
        "missing_chain_layer": "链层待补",
        "review_required": "需复核",
    }
    return "、".join(labels[f] for f in company_qc_flags(company) if f in labels) or "暂无明显缺口"


def map_company_role(company: dict) -> str:
    return md_cell("、".join(unique(company.get("roles", []) or [])) or SUBTYPE_LABELS.get(company.get("company_subtype") or company_subtype(company), "待判定"), 100)


def map_one_line_anchor(term: str, state: dict) -> str:
    context = state.get("context", {}) or {}
    definition_profile = context.get("definition_profile", {}) if isinstance(context.get("definition_profile"), dict) else {}
    anchor = str(definition_profile.get("one_line_anchor") or state.get("definition") or context_definition(context) or "").strip()
    if not anchor:
        anchor = f"{term}：围绕题材定义、产业链位置、需求驱动、细分方向和相关公司展开的信息地图。"
    return f"{md_cell(anchor, 220)}本地图按“需求 → 产品/工艺 → 产业链环节 → 相关公司 → 核验问题”组织。"


def map_concept_boundary_section(term: str, state: dict) -> str:
    graph = state.get("graph", {}) or {}
    concepts = state.get("concepts", {}) or {}
    primary = state.get("primary") or term
    matches = state.get("matches", []) or []
    node = concepts.get(primary, {}) if isinstance(concepts, dict) else {}
    rows = []
    for name in as_list(node.get("parents")):
        rows.append(("上位概念", name, "用于判断题材所属的大类和外延。"))
    for name in matches:
        if name != primary:
            rows.append(("同义词/别名", name, "用于合并不同表述下的同一题材。"))
    for name in as_list(node.get("children")):
        rows.append(("子概念", name, "用于拆分题材内部的细分方向。"))
    for name in as_list(node.get("related_concepts")):
        rows.append(("相邻概念", name, "用于识别上下游、替代路线或相邻主题。"))
    for rel in relation_neighbors(graph, primary)[:12]:
        rows.append(("相邻概念", rel.get("concept", ""), rel.get("type", "相关")))
    if not rows:
        rows.append(("核心概念", primary if primary != term else term, "作为本报告的分析起点。"))
    lines = ["| 边界类型 | 内容 | 说明 |", "|---|---|---|"]
    for row in rows[:24]:
        lines.append("| " + " | ".join(md_cell(x, 90) for x in row) + " |")
    return "\n".join(lines)


def map_attention_section(state: dict) -> str:
    context = state.get("context", {}) or {}
    report_rows = state.get("local_report_contexts", []) or []
    demand_terms = unique(map_flat_terms(context.get("demand_drivers"), map_report_chain_terms(report_rows, "downstream", 18), limit=24))
    process_terms = unique(map_flat_terms(context.get("capability_stack"), map_report_chain_terms(report_rows, "midstream", 18), limit=24))
    rows = context.get("demand_scenarios", []) if isinstance(context.get("demand_scenarios"), list) else []
    inferred_rows = map_inferred_demand_engine_rows(state)
    structured_rows = [row for row in rows if isinstance(row, dict) and not map_generic_demand_row(row)]
    lines = [
        "### 需求引擎",
        "",
        "| 需求引擎 | 变化逻辑 | 传导环节 | 相关公司 |",
        "|---|---|---|---|",
    ]
    if structured_rows:
        for row in structured_rows[:8]:
            lines.append(
                f"| {map_clean_display(row.get('scenario') or row.get('downstream_driver'))} | {map_clean_display(row.get('logic') or row.get('transmission_logic') or row.get('evidence_summary'), limit=130)} | {map_clean_display(row.get('process_requirement') or row.get('chain_position'), limit=100)} | {map_clean_display(row.get('representative_entities'), limit=100)} |"
            )
    elif inferred_rows:
        for row in inferred_rows:
            lines.append(
                f"| {map_clean_display(row.get('scenario'))} | {map_clean_display(row.get('logic'), limit=130)} | {map_clean_display(row.get('process'), limit=120)} | {map_clean_display(row.get('companies'), limit=100)} |"
            )
    else:
        for term in demand_terms[:8]:
            lines.append(
                f"| {map_clean_display(term)} | 需求变化通过产品容量、性能、价格或客户认证向产业链传导。 | {map_clean_display(process_terms[:5])} | — |"
            )
    if len(lines) == 4:
        lines.append("| 主题需求 | 需求变化通过产品、工艺和客户认证向产业链传导。 | — | — |")
    summary_terms = unique(demand_terms[:4] + process_terms[:4])
    if summary_terms:
        lines.extend(["", "### 主线小结", "", "- **关键词**：" + md_cell("、".join(summary_terms), 180)])
    return "\n".join(lines)


def map_chain_rows_from_context(context: dict) -> list[dict]:
    rows = []
    panorama = context.get("industry_chain_panorama", []) if isinstance(context, dict) else []
    if isinstance(panorama, list):
        for row in panorama:
            if not isinstance(row, dict):
                continue
            rows.append(
                {
                    "layer": row.get("layer") or "待补",
                    "segment": row.get("segment") or row.get("name") or "待补",
                    "subdir": "、".join(as_list(row.get("key_elements"))) or row.get("segment") or "待补",
                    "desc": row.get("industry_logic") or row.get("supply_demand_status") or "",
                    "companies": "、".join(as_list(row.get("representative_entities"))),
                    "source": row.get("source") or "theme_supplement_pool/context",
                    "gap": "待补" if not row.get("representative_entities") else "",
                }
            )
    chain = context.get("industry_chain_map", {}) if isinstance(context, dict) else {}
    labels = {
        "downstream": "下游需求",
        "midstream": "中游产品/制造",
        "upstream_equipment": "上游设备",
        "upstream_materials": "上游材料",
        "ecosystem": "生态/配套",
    }
    if isinstance(chain, dict):
        for key, values in chain.items():
            for value in values or []:
                name = value.get("name") if isinstance(value, dict) else str(value)
                if name:
                    rows.append({"layer": labels.get(key, key), "segment": name, "subdir": name, "desc": "来自产业链上下文字段", "companies": "", "source": "report_contexts/runtime_context", "gap": "公司映射待补"})
    return rows


def map_industry_chain_section(state: dict) -> str:
    context = state.get("context", {}) or {}
    companies = state.get("companies", []) or []
    profile = state.get("direction_profile")
    report_rows = state.get("local_report_contexts", []) or []
    rows = [
        {
            "layer": "下游需求",
            "segment": "终端/应用场景",
            "subdir": "、".join(unique(map_context_chain_terms(context, "downstream", 10) + map_report_chain_terms(report_rows, "downstream", 10))) or "待补",
            "desc": "解释题材需求来源，只做场景归类。",
            "companies": map_company_names_for_directions(companies, profile, {"downstream_channel"}, {"downstream_channel"}, 8),
            "source": "report_contexts/context",
            "gap": "需求到产品/工艺映射待补",
        },
        {
            "layer": "中游产品/制造",
            "segment": "核心产品与制造",
            "subdir": "、".join(unique(map_context_chain_terms(context, "midstream", 10) + map_report_chain_terms(report_rows, "midstream", 10))) or "待补",
            "desc": "承接需求并形成题材主体的产品、制造或工艺环节。",
            "companies": map_company_names_for_directions(companies, profile, {"core_product", "storage_product", "optical_module", "drug_pipeline", "pv_cell_module", "manufacturing"}, {"core_subject", "component_supplier"}, 10),
            "source": "concept_graph/entity_exposures/report_contexts",
            "gap": "产品口径、客户和收入占比待补",
        },
        {
            "layer": "封测/工程/服务",
            "segment": "封装测试/工程服务/平台",
            "subdir": "、".join(unique([direction_label("package_test", profile), direction_label("service_platform", profile)])),
            "desc": "连接产品制造、验证、交付和配套服务的中间环节。",
            "companies": map_company_names_for_directions(companies, profile, {"package_test", "service_platform"}, {"service_provider"}, 10),
            "source": "entity_exposures/evidence_index",
            "gap": "服务边界和客户验证待补",
        },
        {
            "layer": "上游设备",
            "segment": "设备/量测/检测",
            "subdir": "、".join(unique(map_context_chain_terms(context, "upstream_equipment", 10) + map_report_chain_terms(report_rows, "upstream_equipment", 10))) or direction_label("equipment", profile),
            "desc": "为制造、封测或工艺升级提供设备和量检测能力。",
            "companies": map_company_names_for_directions(companies, profile, {"equipment"}, {"upstream_equipment"}, 10),
            "source": "concept_graph/entity_exposures/report_contexts",
            "gap": "订单、验收、导入进度待补",
        },
        {
            "layer": "上游材料",
            "segment": "材料/化学品/零部件",
            "subdir": "、".join(unique(map_context_chain_terms(context, "upstream_materials", 10) + map_report_chain_terms(report_rows, "upstream_materials", 10))) or direction_label("materials", profile),
            "desc": "为核心工艺、封测或产品性能提供材料和零部件约束。",
            "companies": map_company_names_for_directions(companies, profile, {"materials", "pv_silicon"}, {"upstream_materials"}, 10),
            "source": "concept_graph/entity_exposures/report_contexts",
            "gap": "认证、产能、客户导入待补",
        },
    ]
    lines = [
        "```text",
        "下游需求/应用场景",
        "        ↓",
        "中游产品/制造 ── 封测/工程/服务",
        "        ↑             ↑",
        "上游设备/量检测   上游材料/零部件",
        "```",
        "",
        "| 层级 | 核心环节 | 关键内容 | 作用 |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {map_clean_display(row.get('layer'))} | {map_clean_display(row.get('segment'))} | {map_clean_display(row.get('subdir'), limit=120)} | {map_clean_display(row.get('desc'), limit=120)} |")
    return "\n".join(lines)


def map_demand_bottleneck_section(state: dict) -> str:
    context = state.get("context", {}) or {}
    rows = context.get("demand_scenarios", []) if isinstance(context.get("demand_scenarios"), list) else []
    out = []
    for row in rows:
        if not isinstance(row, dict) or map_generic_demand_row(row):
            continue
        out.append(
            {
                "source": row.get("scenario") or row.get("demand_source") or row.get("downstream_driver"),
                "desc": row.get("logic") or row.get("transmission_logic") or row.get("evidence_summary"),
                "bottleneck": row.get("process_requirement") or row.get("bottleneck"),
                "link": "、".join(as_list(row.get("beneficiary_links"))) or row.get("chain_position"),
                "subdir": row.get("direction") or row.get("scenario"),
                "companies": "、".join(as_list(row.get("representative_entities"))),
            }
        )
    if not out:
        for row in map_inferred_demand_engine_rows(state):
            out.append({"source": row.get("scenario"), "desc": row.get("logic"), "bottleneck": "容量、带宽、功耗、良率、认证和供给节奏", "link": row.get("process"), "subdir": row.get("scenario"), "companies": row.get("companies")})
    if not out:
        for value in as_list(context.get("demand_drivers"))[:8]:
            out.append({"source": value, "desc": "需求变化通过产品容量、性能、价格或客户认证向产业链传导。", "bottleneck": "容量、成本、良率、客户认证", "link": "产品/工艺/制造环节", "subdir": value, "companies": ""})
    lines = ["| 需求引擎 | 传导逻辑 | 关键约束 | 传导环节 | 对应方向/公司 |", "|---|---|---|---|---|"]
    if not out:
        out.append({"source": "主题需求", "desc": "需求变化通过产品和产业链环节传导。", "bottleneck": "容量、成本、良率、客户认证", "link": "产品/工艺/制造环节", "subdir": "", "companies": ""})
    for row in out[:24]:
        target = " / ".join(x for x in (map_clean_display(row.get("subdir"), default="", limit=70), map_clean_display(row.get("companies"), default="", limit=80)) if x)
        lines.append(f"| {map_clean_display(row.get('source'), limit=80)} | {map_clean_display(row.get('desc'), limit=120)} | {map_clean_display(row.get('bottleneck'), limit=100)} | {map_clean_display(row.get('link'), limit=100)} | {target or '—'} |")
    return "\n".join(lines)


def map_subdirection_rows(state: dict) -> list[dict]:
    context = state.get("context", {}) or {}
    companies = state.get("companies", []) or []
    profile = state.get("direction_profile")
    rows = []
    for row in context.get("direction_scan", []) if isinstance(context.get("direction_scan"), list) else []:
        if isinstance(row, dict):
            rows.append({"subdir": row.get("direction") or row.get("name"), "layer": row.get("sector") or "待补", "desc": row.get("core_catalyst") or row.get("prosperity") or "", "concepts": "、".join(as_list(row.get("secondary_sectors"))), "companies": "、".join(as_list(row.get("candidate_companies"))), "evidence": row.get("mention_frequency") or "context", "source": "direction_scan", "gap": row.get("next_validation") or "公司映射待补"})
    for row in context.get("material_process_scan", []) if isinstance(context.get("material_process_scan"), list) else []:
        if isinstance(row, dict):
            rows.append({"subdir": row.get("name") or row.get("direction"), "layer": row.get("chain_position") or row.get("major_track") or "待补", "desc": row.get("core_catalyst") or row.get("next_validation") or "", "concepts": row.get("classification") or "", "companies": "、".join(as_list(row.get("representative_entities"))), "evidence": row.get("source") or "material_process_scan", "source": "material_process_scan", "gap": row.get("next_validation") or "待补"})
    for direction, group in direction_company_groups(companies, profile).items():
        if direction in {"unknown", "weak_watch", "ecosystem"}:
            continue
        rows.append({"subdir": direction_subdirection_summary(group, direction, profile), "layer": direction_label(direction, profile), "desc": "", "concepts": "、".join(unique([x for c in group for x in c.get("concepts", [])])[:6]), "companies": "、".join(unique([c.get("name", "") for c in group if c.get("name")])[:8]), "evidence": evidence_bucket_count_summary(group), "source": "entity_exposures/evidence_index", "gap": direction_qc_gap_summary(group)})
    dedup = []
    seen = set()
    for row in rows:
        key = (str(row.get("subdir")), str(row.get("layer")))
        if key in seen or not row.get("subdir"):
            continue
        seen.add(key)
        dedup.append(row)
    return dedup


def map_subdirection_section(state: dict) -> str:
    rows = map_subdirection_rows(state)
    companies = state.get("companies", []) or []
    lines = ["| 细分方向/环节 | 对应公司 |", "|---|---|"]
    for row in rows[:40]:
        subdir = row.get("subdir")
        if not map_clean_plain(subdir):
            subdir = row.get("layer")
        mapped_companies = map_clean_plain(row.get("companies"), limit=120)
        if not mapped_companies:
            mapped_companies = map_clean_plain(map_companies_for_term(companies, str(subdir or ""), 8), limit=120)
        if not mapped_companies:
            mapped_companies = map_clean_plain(map_companies_for_term(companies, str(row.get("layer") or ""), 8), limit=120)
        clean_subdir = map_clean_plain(subdir, limit=120)
        clean_layer = map_clean_plain(row.get("layer"), limit=120)
        if not clean_subdir or not mapped_companies:
            continue
        label = clean_subdir if clean_subdir == clean_layer or not clean_layer else f"{clean_layer}：{clean_subdir}"
        lines.append("| " + " | ".join(map_blank_display(value, limit=140) for value in (label, mapped_companies)) + " |")
    if len(lines) == 2:
        return ""
    return "\n".join(lines)


def map_validation_item_for_direction(name: str, layer: str) -> str:
    text = f"{name} {layer}"
    if any(token in text for token in ("临床", "获批", "BD", "License", "管线", "药")):
        return "临床进展、审评节点、商业化进展、BD授权、收入贡献"
    if any(token in text for token in ("设备", "PECVD", "ALD", "量测", "检测", "装备")):
        return "招标、订单、交付、验收、客户导入、产线适配"
    if any(token in text for token in ("材料", "硅片", "CMP", "特气", "光刻胶", "铜箔", "玻璃", "胶膜", "银浆")):
        return "客户认证、供货、产能、价格、良率、收入占比"
    if any(token in text for token in ("封测", "封装", "先进封装", "CoWoS", "Chiplet", "CPO")):
        return "封装技术、客户、量产、产能利用率、订单/收入口径"
    if any(token in text for token in ("NAND", "NOR", "DRAM", "HBM", "DDR", "SSD", "光模块", "组件", "逆变器")):
        return "产品代际、客户认证、出货、价格/库存、收入占比"
    return "产品、客户、订单、产能、认证、收入占比"


def map_subdirection_deep_dive_section(state: dict) -> str:
    rows = []
    for row in map_subdirection_rows(state):
        subdir = str(row.get("subdir") or "").strip()
        if not subdir or subdir == "待细分":
            continue
        companies = map_clean_plain(row.get("companies") or map_companies_for_term(state.get("companies", []) or [], subdir, 6), limit=100)
        why = map_clean_plain(row.get("desc"), limit=130)
        if not companies or not why:
            continue
        clean_row = dict(row)
        clean_row["companies"] = companies
        clean_row["desc"] = why
        rows.append(clean_row)
    lines = [
        "| 细分方向 | 链条位置 | 为什么重要 | 相关公司 | 重点核验字段 |",
        "|---|---|---|---|---|",
    ]
    if not rows:
        return ""
    for row in rows[:14]:
        name = row.get("subdir") or "主题主线"
        layer = row.get("layer") or "—"
        companies = row.get("companies")
        why = row.get("desc")
        fields = map_validation_item_for_direction(str(name), str(layer))
        lines.append(f"| {map_clean_display(name)} | {map_clean_display(layer)} | {map_clean_display(why, limit=130)} | {map_clean_display(companies, limit=100)} | {map_clean_display(fields)} |")
    return "\n".join(lines)


def map_process_material_section(state: dict) -> str:
    context = state.get("context", {}) or {}
    rows = []
    for row in context.get("material_process_scan", []) if isinstance(context.get("material_process_scan"), list) else []:
        if isinstance(row, dict):
            rows.append({"name": row.get("name") or row.get("direction"), "layer": row.get("chain_position") or row.get("major_track"), "subdir": row.get("classification") or row.get("direction") or row.get("name"), "desc": row.get("core_catalyst") or row.get("next_validation") or row.get("prosperity_judgment"), "companies": "、".join(as_list(row.get("representative_entities"))), "source": row.get("source") or "material_process_scan", "gap": row.get("next_validation") or "待补"})
    if not rows:
        for row in map_subdirection_rows(state):
            text = str(row.get("subdir") or "")
            if any(token in text for token in ("材料", "工艺", "设备", "NAND", "NOR", "HBM", "DDR", "ADC", "双抗", "GLP", "硅料", "硅片", "组件", "逆变器", "EML", "VCSEL", "硅光", "CPO", "PCB", "CMP", "PECVD")):
                rows.append({"name": text, "layer": row.get("layer"), "subdir": row.get("subdir"), "desc": row.get("desc"), "companies": row.get("companies"), "source": row.get("source"), "gap": row.get("gap")})
    lines = ["| 工艺/材料/零部件 | 所在环节 | 对应方向 | 为什么重要 | 相关公司 |", "|---|---|---|---|---|"]
    if not rows:
        return ""
    for row in rows[:36]:
        desc = map_clean_plain(row.get("desc"), limit=120)
        companies = map_clean_plain(row.get("companies"), limit=120)
        if not desc and not companies:
            continue
        lines.append("| " + " | ".join(map_clean_display(value, limit=120) for value in (row.get("name"), row.get("layer"), row.get("subdir"), desc, companies)) + " |")
    if len(lines) == 2:
        return ""
    return "\n".join(lines)


def map_company_table(companies: list[dict], profile: dict | None, subtypes: set[str], limit: int = 40) -> str:
    rows = [c for c in companies if (c.get("company_subtype") or company_subtype(c)) in subtypes]
    lines = ["| 公司 | 所属环节 | 业务/线索 |", "|---|---|---|"]
    generic_roles = {"芯片/核心器件", "上游设备", "上游材料", "中游制造", "中游封装测试", "相关公司"}
    for company in rows[:limit]:
        direction = company_direction_key(company, profile)
        evidence = map_first_clean(unique(company.get("evidence", []) or []), 120)
        role_parts = []
        role = map_clean_plain(company.get("roles", []), limit=90)
        products = map_clean_plain(company_subdirections(company), limit=90)
        if evidence and role in generic_roles:
            role = ""
        if role:
            role_parts.append(role)
        if products and products not in role:
            role_parts.append(products)
        role_text = "；".join(unique(role_parts))
        if not evidence and (not role_text or role_text in {"延伸线索", "相关公司", "上游设备", "上游材料", "中游制造", "中游封装测试", "股权投资潜在相关"}):
            continue
        if not evidence and any(token in role_text for token in ("延伸线索", "潜在相关")):
            continue
        detail = "；".join(unique([x for x in (role_text, evidence) if x]))
        if not detail:
            continue
        lines.append(f"| {map_blank_display(company.get('name'))} | {map_blank_display(direction_label(direction, profile))} | {map_blank_display(detail, limit=220)} |")
    if len(lines) == 2:
        return ""
    return "\n".join(lines)


def map_company_map_section(state: dict) -> str:
    companies = state.get("companies", []) or []
    profile = state.get("direction_profile")
    sections = [
        ("核心产品/主体相关公司", {"core_subject", "component_supplier"}),
        ("上游设备公司", {"upstream_equipment"}),
        ("上游材料公司", {"upstream_materials"}),
        ("制造 / 封测 / 工程服务公司", {"manufacturer", "package_test", "service_provider"}),
        ("下游渠道 / 运营 / 应用公司", {"downstream_channel"}),
        ("生态及延伸线索", {"ecosystem", "weak_graph", "unknown"}),
    ]
    lines = []
    for title, subtypes in sections:
        table = map_company_table(companies, profile, subtypes)
        if table:
            lines.extend([f"### {title}", "", table, ""])
    return "\n".join(lines).strip()


def map_wiki_subdirection_company_rows(state: dict, limit: int = 40) -> list[dict]:
    companies = state.get("companies", []) or []
    rows = []
    seen = set()
    for row in map_subdirection_rows(state):
        name = map_wiki_name(row.get("subdir"))
        layer = map_wiki_name(row.get("layer"))
        if not name:
            name = layer
        if not name or name in {"生态配套", "生态/配套"} or layer in {"生态配套", "生态/配套"}:
            continue
        mapped = map_clean_plain(row.get("companies"), limit=160)
        if not mapped:
            mapped = map_clean_plain(map_companies_for_term(companies, name, 10), limit=160)
        if not mapped and layer:
            mapped = map_clean_plain(map_companies_for_term(companies, layer, 10), limit=160)
        if not mapped:
            continue
        key = (name, mapped)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"name": name, "layer": layer, "companies": mapped})
        if len(rows) >= limit:
            break
    return rows


def map_wiki_graph_section(state: dict) -> str:
    root = map_wiki_link(state.get("primary") or state.get("term"))
    rows = map_wiki_subdirection_company_rows(state, 14)
    if not root and not rows:
        return ""
    lines = [f"- {root or map_clean_display(state.get('term') or state.get('primary'))}"]
    for row in rows:
        node = map_wiki_link(row.get("name"))
        companies = map_wiki_join(row.get("companies"), 10)
        if node and companies:
            lines.append(f"  - {node}：{companies}")
    return "\n".join(lines)


def map_wiki_theme_card_section(term: str, state: dict) -> str:
    context = state.get("context", {}) or {}
    profile = context.get("definition_profile", {}) if isinstance(context.get("definition_profile"), dict) else {}
    action_rows = context.get("action_plan", []) if isinstance(context.get("action_plan"), list) else []
    validation_rows = context.get("validation_checklist", []) if isinstance(context.get("validation_checklist"), list) else []
    anchor = map_clean_plain(profile.get("one_line_anchor") or map_one_line_anchor(term, state), limit=260)
    why = map_clean_plain(profile.get("why_it_matters") or profile.get("technical_definition") or profile.get("boundary_notes"), limit=220)
    focus = []
    for row in action_rows:
        if not isinstance(row, dict):
            continue
        item = map_clean_plain(row.get("target_entity") or row.get("direction"), limit=40)
        if item:
            focus.append(item)
    variables = []
    for row in validation_rows:
        if not isinstance(row, dict):
            continue
        item = map_clean_plain(row.get("item") or row.get("upgrade_condition") or row.get("window"), limit=60)
        if item:
            variables.append(item)
    lines = []
    if anchor:
        lines.append(f"- **一句话**：{anchor}")
    if why:
        lines.append(f"- **核心问题**：{why}")
    if focus:
        lines.append("- **当前关注**：" + "、".join(unique(focus)[:6]))
    if variables:
        lines.append("- **关键变量**：" + "、".join(unique(variables)[:6]))
    root = map_wiki_link(state.get("primary") or state.get("term"))
    if root:
        lines.append(f"- **Wiki 入口**：{root}")
    return "\n".join(lines)


def map_wiki_demand_chain_section(state: dict) -> str:
    root = map_wiki_link(state.get("primary") or state.get("term"))
    rows = []
    context = state.get("context", {}) or {}
    demand_rows = context.get("demand_scenarios", []) if isinstance(context.get("demand_scenarios"), list) else []
    for row in demand_rows:
        if not isinstance(row, dict) or map_generic_demand_row(row):
            continue
        scenario = row.get("scenario") or row.get("demand_source") or row.get("downstream_driver")
        driver = row.get("downstream_driver") or row.get("transmission_logic") or row.get("logic")
        process = row.get("beneficiary_links") or row.get("process_requirement") or row.get("chain_position")
        companies = row.get("representative_entities")
        watch = row.get("next_validation") or row.get("evidence_summary")
        if scenario and (process or companies):
            rows.append({"scenario": scenario, "driver": driver, "process": process, "companies": "、".join(as_list(companies)), "watch": watch})
    if not rows:
        rows = map_inferred_demand_engine_rows(state, 8)
    if not rows:
        return ""
    lines = ["| 需求场景 | 传导逻辑 | Wiki 传导路径 | 对应公司 | 看什么 |", "|---|---|---|---|---|"]
    for row in rows[:8]:
        scenario = map_wiki_link(row.get("scenario"))
        process = map_wiki_join(row.get("process"), 6)
        companies = map_wiki_join(row.get("companies"), 8)
        path_parts = [x for x in (root, scenario, process) if x]
        if not path_parts:
            continue
        lines.append(f"| {scenario or map_blank_display(row.get('scenario'))} | {map_blank_display(row.get('driver'), 120)} | {' → '.join(path_parts)} | {companies} | {map_blank_display(row.get('watch'), 100)} |")
    return "\n".join(lines) if len(lines) > 2 else ""


def map_wiki_material_cards_section(state: dict) -> str:
    context = state.get("context", {}) or {}
    rows = context.get("material_process_scan", []) if isinstance(context.get("material_process_scan"), list) else []
    if not rows:
        return ""
    lines = ["| 方向节点 | 所属环节 | 景气/催化 | 对应公司 | 下一步验证 |", "|---|---|---|---|---|"]
    for row in rows[:14]:
        if not isinstance(row, dict):
            continue
        name = map_wiki_link(row.get("name") or row.get("direction"))
        if not name:
            continue
        layer = map_wiki_link(row.get("chain_position") or row.get("major_track"))
        catalyst = map_clean_plain([row.get("prosperity_judgment"), row.get("core_catalyst"), row.get("prosperity_reason")], limit=130)
        companies = map_wiki_join(row.get("representative_entities"), 8)
        validation = map_clean_plain(row.get("next_validation") or row.get("evidence_summary"), limit=100)
        if not catalyst and not companies and not validation:
            continue
        lines.append(f"| {name} | {layer} | {map_blank_display(catalyst, 140)} | {companies} | {map_blank_display(validation, 120)} |")
    return "\n".join(lines) if len(lines) > 2 else ""


def map_wiki_subdirection_mapping_section(state: dict) -> str:
    rows = map_wiki_subdirection_company_rows(state, 40)
    if not rows:
        return ""
    lines = ["| Wiki 节点 | 对应公司 |", "|---|---|"]
    for row in rows:
        node = map_wiki_link(row.get("name"))
        companies = map_wiki_join(row.get("companies"), 12)
        lines.append(f"| {node} | {companies} |")
    return "\n".join(lines)


def map_wiki_tracking_priority_section(state: dict) -> str:
    context = state.get("context", {}) or {}
    rows = context.get("action_plan", []) if isinstance(context.get("action_plan"), list) else []
    if not rows:
        return ""
    priority_order = {"P0": 0, "P0核心跟踪": 0, "P1": 1, "P1重点观察": 1, "P2": 2, "P2弹性观察": 2}
    def rank(row: dict) -> int:
        value = str(row.get("priority_bucket") or "")
        return min([priority_order[key] for key in priority_order if key in value] or [9])
    lines = ["| 优先级 | 跟踪对象 | Wiki 方向 | 核心逻辑 | 等待信号 | 风险/证伪 |", "|---|---|---|---|---|---|"]
    for row in sorted([r for r in rows if isinstance(r, dict)], key=rank)[:10]:
        target = row.get("target_entity") or row.get("direction")
        direction = row.get("direction") or row.get("target_entity")
        combined = " ".join(str(row.get(key) or "") for key in ("target_entity", "direction", "core_logic", "action_thesis"))
        if any(token in combined for token in ("稀土", "回收链类比")):
            continue
        if "P3" in str(row.get("priority_bucket") or ""):
            continue
        logic = row.get("core_logic") or row.get("action_thesis") or row.get("evidence_summary")
        lines.append(
            f"| {map_blank_display(row.get('priority_bucket'), 30)} | {map_wiki_link(target) or map_blank_display(target)} | {map_wiki_link(direction) or map_blank_display(direction)} | {map_blank_display(logic, 130)} | {map_blank_display(row.get('wait_for'), 120)} | {map_blank_display(row.get('risk_warning'), 100)} |"
        )
    return "\n".join(lines) if len(lines) > 2 else ""


def map_wiki_validation_watch_section(state: dict) -> str:
    context = state.get("context", {}) or {}
    rows = context.get("validation_checklist", []) if isinstance(context.get("validation_checklist"), list) else []
    if not rows:
        return ""
    lines = ["| 方向 | 验证事项 | 窗口/状态 | 正向信号 | 反向信号 |", "|---|---|---|---|---|"]
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        direction = map_wiki_link(row.get("direction")) or map_blank_display(row.get("direction"))
        status = " / ".join(x for x in [map_clean_plain(row.get("window"), 30), map_clean_plain(row.get("status"), 30)] if x)
        lines.append(f"| {direction} | {map_blank_display(row.get('item'), 80)} | {map_blank_display(status, 60)} | {map_blank_display(row.get('upgrade_condition'), 110)} | {map_blank_display(row.get('downgrade_condition'), 100)} |")
    return "\n".join(lines) if len(lines) > 2 else ""


def map_wiki_catalyst_section(state: dict) -> str:
    context = state.get("context", {}) or {}
    rows = context.get("catalyst_calendar", []) if isinstance(context.get("catalyst_calendar"), list) else []
    if not rows:
        return ""
    lines = ["| 时间 | 事件 | 相关方向 | 观察点 |", "|---|---|---|---|"]
    for row in rows[:6]:
        if not isinstance(row, dict):
            continue
        direction = row.get("direction") or row.get("相关方向")
        if not map_clean_plain(direction) or map_clean_plain(direction) == "催化日历":
            direction = row.get("event_type") or row.get("direction") or row.get("相关方向")
        event = row.get("event")
        watch = row.get("watch_item") or row.get("next_watch") or row.get("impact_logic")
        if not event:
            continue
        lines.append(f"| {map_blank_display(row.get('time') or row.get('time_window'), 40)} | {map_blank_display(event, 120)} | {map_wiki_link(direction) or map_blank_display(direction, 80)} | {map_blank_display(watch, 100)} |")
    return "\n".join(lines) if len(lines) > 2 else ""


def map_wiki_company_paths_section(state: dict) -> str:
    companies = state.get("companies", []) or []
    profile = state.get("direction_profile")
    root = state.get("primary") or state.get("term")
    lines = ["| 公司 | 映射路径 | 关键线索 |", "|---|---|---|"]
    for company in companies[:18]:
        direction = company_direction_key(company, profile)
        if direction in {"unknown", "weak_watch", "ecosystem"}:
            continue
        company_name = company.get("name")
        layer = direction_label(direction, profile)
        products = company_subdirections(company)[:2]
        evidence = map_first_clean(unique(company.get("evidence", []) or []), 130)
        role = map_clean_plain(company.get("roles", []), limit=90)
        generic_roles = {"芯片/核心器件", "上游设备", "上游材料", "中游制造", "中游封装测试", "相关公司", "延伸线索", "延伸观察", "股权投资潜在相关"}
        if evidence and role in generic_roles:
            role = ""
        detail = "；".join(unique([x for x in (role, evidence) if x]))
        if not detail or detail in generic_roles:
            continue
        path_values = [root, layer] + products + [company_name]
        lines.append(f"| {map_wiki_link(company_name)} | {map_wiki_path(path_values)} | {map_blank_display(detail, 180)} |")
    return "\n".join(lines) if len(lines) > 2 else ""


def map_wiki_navigation_section(state: dict) -> str:
    companies = state.get("companies", []) or []
    rows = map_wiki_subdirection_company_rows(state, 30)
    concept_links = map_wiki_join([row.get("name") for row in rows], 24)
    profile = state.get("direction_profile")
    company_names = []
    for company in companies:
        if company_direction_key(company, profile) in {"unknown", "weak_watch", "ecosystem"}:
            continue
        evidence = map_first_clean(unique(company.get("evidence", []) or []), 80)
        role = map_clean_plain(company.get("roles", []), limit=80)
        if not evidence and role in {"延伸线索", "延伸观察", "股权投资潜在相关"}:
            continue
        company_names.append(company.get("name"))
    company_links = map_wiki_join(company_names, 30)
    root = map_wiki_link(state.get("primary") or state.get("term"))
    lines = []
    if root:
        lines.append(f"- **主题入口**：{root}")
    if concept_links:
        lines.append(f"- **方向节点**：{concept_links}")
    if company_links:
        lines.append(f"- **公司节点**：{company_links}")
    return "\n".join(lines)


def map_wiki_backlog_section(state: dict) -> str:
    companies = state.get("companies", []) or []
    rows = []
    for row in map_subdirection_rows(state):
        name = map_wiki_name(row.get("subdir") or row.get("layer"))
        if not name or name in {"生态配套", "生态/配套"}:
            continue
        mapped = map_clean_plain(row.get("companies") or map_companies_for_term(companies, name, 6), limit=100)
        if not mapped:
            rows.append((map_wiki_link(name), "方向已有，但公司映射较少。"))
    for company in companies[:24]:
        evidence = map_first_clean(unique(company.get("evidence", []) or []), 80)
        if not evidence and company_direction_key(company, state.get("direction_profile")) not in {"unknown", "weak_watch", "ecosystem"}:
            rows.append((map_wiki_link(company.get("name")), "公司已进入映射，但业务线索较少。"))
    if not rows:
        return ""
    lines = []
    seen = set()
    for node, reason in rows:
        key = (node, reason)
        if key in seen:
            continue
        seen.add(key)
        if node:
            lines.append(f"- {node}：{reason}")
        if len(lines) >= 12:
            break
    return "\n".join(lines)


def map_evidence_section(state: dict) -> str:
    rows = []
    for row in map_subdirection_rows(state)[:12]:
        name = row.get("subdir")
        if not map_clean_plain(name):
            name = row.get("layer")
        if not map_clean_plain(name):
            continue
        rows.append((name, row.get("layer"), map_validation_item_for_direction(str(name or ""), str(row.get("layer") or ""))))
    if not rows:
        return ""
    lines = ["| 对象 | 归属方向 | 核验重点 |", "|---|---|---|"]
    for row in rows[:48]:
        lines.append("| " + " | ".join(map_clean_display(x, limit=140) for x in row) + " |")
    return "\n".join(lines)


def map_cross_validation_section(state: dict) -> str:
    companies = state.get("companies", []) or []
    profile = state.get("direction_profile")
    rows = []
    for company in companies[:18]:
        increment = "、".join(company_subdirections(company)) or direction_label(company_direction_key(company, profile), profile)
        role = map_clean_plain(company.get("roles", []), limit=80)
        signal = map_clean_plain([role, increment], limit=100)
        rows.append(
            (
                company.get("name"),
                direction_label(company_direction_key(company, profile), profile),
                signal or increment,
                "产品口径、客户导入、产能/出货、收入占比、认证进度",
            )
        )
    if not rows:
        rows.append(("主题主线", "—", "围绕定义、产业链位置和公司映射继续核验。", "产品、客户、订单、产能、认证"))
    lines = [
        "| 对象 | 链条位置 | 当前线索 | 核验重点 |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(map_clean_display(x, limit=130) for x in row) + " |")
    return "\n".join(lines)


def map_gap_section(state: dict) -> str:
    context = state.get("context", {}) or {}
    companies = state.get("companies", []) or []
    rows = []
    rows.append(("定义边界", "主题边界是否只覆盖核心环节，是否混入相邻主题。", "定义、上位概念、相邻概念"))
    rows.append(("产业链位置", "需求、产品、制造、封测、设备、材料之间的传导关系是否闭合。", "上下游、环节、代表公司"))
    rows.append(("细分方向", "内部方向是否已经拆到可观察的产品、工艺、客户或认证口径。", "产品代际、工艺路线、应用场景"))
    missing_company = sum(1 for c in companies if "missing_evidence" in company_qc_flags(c) or "graph_only_only" in company_qc_flags(c))
    rows.append(("公司映射", f"{missing_company}家公司需要继续确认产品、客户或业务占比。", "公司名称、产品、客户、收入贡献"))
    conflict = sum(1 for c in companies if "chain_layer_conflict" in company_qc_flags(c))
    rows.append(("链层归类", f"{conflict}家公司需要确认到底属于产品主体、设备材料、封测服务还是生态延伸。", "公司角色、环节归属"))
    rows.append(("事实口径", "重点信息需要落到时间、产品、客户、订单、产能、认证或收入占比。", "可验证字段"))
    lines = ["| 核验问题 | 为什么要看 | 重点字段 |", "|---|---|---|"]
    for row in rows:
        lines.append("| " + " | ".join(map_clean_display(x, limit=120) for x in row) + " |")
    return "\n".join(lines)


def map_source_index_section(state: dict) -> str:
    term = state.get("term") or state.get("primary") or ""
    report_sources = unique([r.get("source_name", "") for r in state.get("local_report_contexts", []) if isinstance(r, dict) and r.get("source_name")])
    evidence_sources = unique([x.get("source", "") for x in state.get("evidence", []) if isinstance(x, dict) and x.get("source")])
    existing_reports = map_existing_report_files(term)
    rows = [
        ("concept_graph.json", "概念节点、相关概念、产业链字段、图谱公司", "概念关系/产业链"),
        ("entity_exposures.json", f"{len(state.get('companies', []) or [])}家公司映射", "公司映射"),
        ("evidence_index.json", "、".join(evidence_sources[:6]) or "待补", "证据来源"),
        ("report_contexts.json", "、".join(report_sources[:6]) or "待补", "研报上下文"),
        ("aliases.json", "查询别名和同义词", "别名/同义词"),
        ("concepts/*.md", state.get("primary") or "待补", "概念定义"),
        ("sources/*.md", "、".join(report_sources[:6]) or "待补", "原始资料"),
        ("已生成 Theme Radar 报告", "、".join(existing_reports) or "待补", "结构参考/历史输出索引"),
    ]
    lines = ["| 来源文件/数据表 | 命中内容 | 用途 |", "|---|---|---|"]
    for row in rows:
        lines.append("| " + " | ".join(md_cell(x, 160) for x in row) + " |")
    return "\n".join(lines)


def map_appendix_section(state: dict) -> str:
    context = state.get("context", {}) or {}
    graph = state.get("graph", {}) or {}
    concepts = state.get("concepts", {}) or {}
    primary = state.get("primary", "")
    term = state.get("term") or primary
    node = concepts.get(primary, {}) if isinstance(concepts, dict) else {}
    companies = state.get("companies", []) or []
    report_sources = unique([r.get("source_name", "") for r in state.get("local_report_contexts", []) if isinstance(r, dict) and r.get("source_name")])
    lines = [
        "- 原始 related concepts：" + md_cell("、".join(as_list(node.get("related_concepts")) or state.get("rels", [])), 220),
        "- 原始 supply_chain：" + md_cell(json.dumps(node.get("supply_chain", {}), ensure_ascii=False), 220),
        "- 原始 company exposure：" + md_cell("、".join(c.get("name", "") for c in companies[:20]), 220),
        "- 原始 evidence bucket：" + md_cell("；".join(f"{c.get('name')}={map_bucket_text(c)}" for c in companies[:12]), 220),
        "- 原始 report_contexts 命中：" + md_cell("、".join(report_sources), 220),
        "- 原始 source 文件名：" + md_cell("、".join(unique([s for c in companies for s in c.get("sources", [])])[:20]), 220),
        "- 已生成 Theme Radar 报告：" + md_cell("、".join(map_existing_report_files(term)), 220),
    ]
    if context.get("theme_information_pool"):
        lines.append("- IMA/Obsidian 信息池：" + md_cell(json.dumps(context.get("theme_information_pool"), ensure_ascii=False), 220))
    return "\n".join(lines)


def build_theme_information_map(term: str, vault: Path, definition: str = "", context: dict | None = None, theme_info_rows: list[dict] | None = None, theme_direction_pool: dict | None = None, theme_supplement_pool: dict | None = None) -> str:
    state = build_theme_state(term, vault, definition, context, theme_info_rows, theme_direction_pool, theme_supplement_pool)
    state["term"] = term
    sections = [
        ("题材卡片", map_wiki_theme_card_section(term, state)),
        ("题材知识图谱", map_wiki_graph_section(state)),
        ("需求与产业链", map_wiki_demand_chain_section(state)),
        ("细分方向卡片", map_wiki_material_cards_section(state)),
        ("P0/P1 跟踪优先级", map_wiki_tracking_priority_section(state)),
        ("关键验证与证伪信号", map_wiki_validation_watch_section(state)),
        ("催化与观察日历", map_wiki_catalyst_section(state)),
        ("公司映射路径", map_wiki_company_paths_section(state)),
    ]
    lines = [f"# {term} 题材信息地图", "", f"生成日期：{date.today().isoformat()}", ""]
    index = 1
    for title, body in sections:
        body = str(body or "").strip()
        if not body:
            continue
        lines.extend([f"## {index}. {title}", "", body, ""])
        index += 1
    return "\n".join(lines).rstrip() + "\n"


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
    direction_profile = theme_direction_profile(term, company_scope or all_scope or match_scope)
    companies = refresh_company_subtypes(companies, direction_profile)
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

    wiki_concept_cards = load_wiki_concept_cards(vault, (match_scope or [term]) + rels[:6])
    enrich_companies_with_wiki_pages(vault, companies)
    synthesis_insights = load_synthesis_insights(
        vault,
        term,
        (match_scope or []) + rels[:8],
        [c.get("name", "") for c in sorted(companies, key=company_sort_key)[:30]],
    )
    wiki_state = {
        "primary": primary if term_matched else "",
        "matches": matches,
        "rels": rels,
        "companies": companies,
        "wiki_concept_cards": wiki_concept_cards,
        "synthesis_insights": synthesis_insights,
        "benchmark_matches": [],
    }

    return f"""# {term} 题材雷达

生成日期：{date.today().isoformat()}

## 雷达结论

{conclusion}

## 雷达速览

{radar_digest_section(wiki_state)}

## 外部定义

{definition.strip() if definition.strip() else '未提供。若知识库未命中，建议先用 web access 查公开定义、同义词、上位概念和产业链位置。'}

## Wiki 概念知识卡

{wiki_concept_knowledge_section(wiki_state)}

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

## 为什么现在发酵

{fermentation_signal_section(context, signal, companies)}

### 基础需求拆解

{demand_drivers_section(context)}

### 需求-瓶颈-环节传导表

{demand_bottleneck_map_section(context, companies, direction_profile)}

### 需求场景表

{demand_scenarios_section(context)}

## 产业链全景

{industry_chain_map_section(context, companies, direction_profile)}

### 本地研报产业链上下文

{report_contexts_section(local_report_contexts)}

## 细分方向扫描

{direction_radar_matrix_section(context, companies, direction_profile)}

### 原始方向扫描

{direction_scan_section(context)}

### 工艺/材料/零部件扫描

{inferred_material_process_scan_section(context, companies, direction_profile)}

## 发酵进度排序

{direction_progress_ranking_section(context, companies, direction_profile)}

## 催化日历与验证清单

### 催化日历

{catalyst_calendar_section(context, companies, direction_profile)}

### 验证清单

{validation_checklist_section(context, companies, direction_profile)}

## 产业链与相关概念

### 已有产业链字段

{chr(10).join(supply_lines) if supply_lines else '- 待补'}

### 相关概念

{bullets(rels, '待补')}

### 历史题材类比

{chr(10).join(pattern_lines) if pattern_lines else '- 暂无合适类比'}

## 本地合成研究洞察（wiki/synthesis）

{synthesis_insights_section(wiki_state)}

## 核心公司分组（按产业方向）

{direction_company_section(companies, term_matched, direction_profile)}

## 题材雷达 QC

{theme_qc_section(companies)}

## 验收评分

{acceptance_score_section(companies, context, local_report_contexts, term_matched, direction_profile)}

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
    parser.add_argument("--theme-supplement-pool", help="Theme Radar 补充数据池 JSON，只读接入截图对齐层：需求场景/工艺材料/验证/催化/认知演变/操作建议")
    parser.add_argument("--review-source", default="", help="复盘触发来源，例如 日复盘/板块复盘/新高复盘")
    parser.add_argument("--review-direction", default="", help="复盘识别出的方向，用于前端题材地图的核心信号区")
    parser.add_argument("--review-companies", default="", help="复盘触发个股，逗号/顿号/空格分隔，用于个股逻辑卡展开")
    parser.add_argument("--review-note", default="", help="复盘备注，用于记录触发原因或观察问题")
    parser.add_argument("--out", help="optional markdown output path")
    parser.add_argument("--mode", choices=["radar", "qc", "deep-dive", "map", "front-map", "brief"], default="radar", help="输出模式：radar/qc=底层雷达与QC；deep-dive=题材深拆；map=题材信息地图；front-map=前端精简信息地图；brief=题材速读（定义/产业链/细分扫描/核心个股）")
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
    elif args.mode in {"map", "front-map", "brief"}:
        theme_info_rows = auto_discover_theme_info_rows(args.term)
    theme_direction_pool = {}
    if args.theme_direction_pool:
        theme_direction_pool = read_theme_direction_pool(Path(args.theme_direction_pool).expanduser(), args.term)
    theme_supplement_pool = {}
    if args.theme_supplement_pool:
        theme_supplement_pool = read_theme_supplement_pool(Path(args.theme_supplement_pool).expanduser(), args.term)
    elif args.mode in {"map", "front-map", "brief"}:
        theme_supplement_pool = auto_discover_theme_supplement_pool(args.term)

    vault = Path(args.vault).expanduser()
    review_context = {
        "source": args.review_source,
        "direction": args.review_direction,
        "companies": [x for x in re.split(r"[,，、\s]+", args.review_companies) if x],
        "note": args.review_note,
    }
    if args.mode == "deep-dive":
        report = build_deep_dive_report(args.term, vault, definition, context, theme_info_rows, theme_direction_pool, theme_supplement_pool)
    elif args.mode == "front-map":
        report = build_front_map_report(args.term, vault, definition, context, theme_info_rows, theme_direction_pool, theme_supplement_pool, review_context)
    elif args.mode == "brief":
        report = build_brief_report(args.term, vault, definition, context, theme_info_rows, theme_direction_pool, theme_supplement_pool)
    elif args.mode == "map":
        report = build_theme_information_map(args.term, vault, definition, context, theme_info_rows, theme_direction_pool, theme_supplement_pool)
    elif theme_info_rows or theme_direction_pool or theme_supplement_pool:
        report = build_deep_dive_report(args.term, vault, definition, context, theme_info_rows, theme_direction_pool, theme_supplement_pool)
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

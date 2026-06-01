#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

DIRECTION_TYPE_RULES = [
    ("process", ["工艺", "制程", "半加成", "mSAP", "SAP", "刻蚀", "电镀", "贴装"]),
    ("material", ["材料", "干膜", "铜箔", "树脂", "PI", "ABF", "玻纤", "磷化铟", "InP", "陶瓷", "化学品"]),
    ("equipment", ["设备", "测试", "AOI", "曝光", "显影", "蚀刻", "电镀线", "激光", "机台", "仪器"]),
    ("component", ["零部件", "组件", "器件", "芯片", "光芯片", "连接器", "模组", "发动机", "箭体", "载荷", "太阳翼"]),
    ("substrate", ["基板", "载板", "TGV", "玻璃基板", "陶瓷基板", "DPC"]),
    ("packaging", ["封装", "CoWoP", "CoWoS", "Chiplet", "先进封装", "散热"]),
    ("downstream_demand", ["AI服务器", "服务器", "光模块", "1.6T", "800G", "DDR", "HBM", "云厂", "数据中心", "终端需求"]),
    ("software_control", ["软件", "控制", "算法", "调度", "系统"]),
]

CHAIN_BUCKET_RULES = [
    ("downstream", ["下游", "需求", "服务器", "云厂", "数据中心", "客户", "终端", "光模块"]),
    ("upstream_equipment", ["设备", "测试", "机台", "仪器", "产线", "曝光", "显影", "蚀刻", "电镀"]),
    ("upstream_materials", ["材料", "干膜", "铜箔", "树脂", "基板", "载板", "陶瓷", "玻璃", "InP", "化学品", "ABF"]),
    ("midstream", ["制造", "加工", "封装", "PCB", "模组", "中游"]),
]

DEMAND_RULES = [
    ("AI服务器", ["AI服务器", "AI 服务器", "服务器", "算力", "GPU", "英伟达", "Rubin", "Blackwell"]),
    ("1.6T光模块", ["1.6T", "光模块", "CPO", "NPO", "LPO", "800G", "3.2T"]),
    ("先进封装", ["CoWoP", "CoWoS", "Chiplet", "先进封装", "封装", "异构集成"]),
    ("存储/DDR/HBM", ["DDR", "HBM", "存储", "内存", "DRAM"]),
    ("国产替代", ["国产替代", "国产化", "进口替代", "自主可控"]),
    ("低空/机器人/新能源等终端", ["机器人", "低空", "eVTOL", "新能源", "汽车", "智驾"]),
    ("商业发射", ["商业发射", "火箭发射", "发射场", "发射服务", "可回收火箭"]),
    ("卫星制造", ["卫星制造", "整星", "总装", "太阳翼", "星敏感器", "卫星载荷"]),
    ("低轨星座建设", ["低轨", "星座", "千帆", "GW星网", "中国星网", "星链"]),
    ("卫星通信/终端", ["卫星通信", "卫星互联网", "终端", "相控阵", "T/R", "核心网", "基带", "连接器"]),
    ("太空能源", ["太空光伏", "砷化镓", "HJT", "太阳翼", "钙钛矿"]),
]

BOTTLENECK_RULES = [
    ("高密度互联", ["高密度", "互联", "线宽", "线距", "精细线路", "HDI", "微细"]),
    ("散热", ["散热", "热", "导热", "液冷", "热管理"]),
    ("低介电/高速信号", ["低介电", "低损耗", "高速", "信号", "传输", "Low-CTE", "Dk", "Df"]),
    ("良率/可靠性", ["良率", "可靠性", "稳定性", "一致性", "验证"]),
    ("国产替代/供应链安全", ["国产替代", "国产化", "替代", "供应链", "自主"]),
    ("成本/量产", ["成本", "量产", "放量", "产能", "扩产", "规模化"]),
    ("宇航级可靠性", ["宇航", "星载", "抗辐照", "航天级", "空间环境", "卫星"]),
    ("轻量化/结构强度", ["轻量化", "结构件", "箭体", "贮箱", "碳纤维", "钛合金", "铝合金"]),
    ("射频通信/高速传输", ["射频", "相控阵", "T/R", "基带", "高压缩比", "视频传输", "连接器", "天线"]),
    ("发射降本/复用", ["可回收", "复用", "液氧甲烷", "推力室", "发动机", "商业发射"]),
]

CANONICAL_DIRECTION_RULES = [
    ("火箭发动机与推进系统", ["发动机", "推力室", "液氧", "甲烷", "推进", "贮箱"]),
    ("火箭箭体与总装", ["火箭总装", "箭体", "火箭结构", "发射平台", "火箭+卫星"]),
    ("卫星制造与整星总装", ["卫星整星", "整星制造", "卫星总装", "G60星座载荷", "太阳翼", "星敏感器", "卫星铰链"]),
    ("卫星载荷与通信芯片", ["载荷", "相控阵", "T/R", "射频芯片", "基带", "FPGA", "星载", "通信载荷"]),
    ("星座运营与卫星通信服务", ["星座运营", "卫星通信运营", "千帆", "GW星网", "中国星网"]),
    ("地面终端与连接器", ["终端", "连接器", "继电器", "北斗"]),
    ("卫星互联网信息化与应用", ["核心网", "发射场信息化", "数字地球", "太空算力", "遥感", "应用"]),
    ("卫星能源与太空光伏", ["太空光伏", "砷化镓电池", "HJT", "钙钛矿", "胶膜"]),
    ("商业航天材料与结构件", ["LCP材料", "锗衬底", "3D打印", "结构件", "材料", "钛合金", "碳纤维"]),
    ("政策与产业组织", ["政策", "行业", "三年行动计划", "ITU", "股权投资", "SpaceX"]),
    ("mSAP/精细线路工艺", ["mSAP", "半加成", "精细线路", "线宽", "线距", "HDI"]),
    ("感光干膜", ["感光干膜", "干膜"]),
    ("载体铜箔", ["载体铜箔", "铜箔"]),
    ("PCB化学品", ["PCB化学品", "化学品", "电镀液", "蚀刻液"]),
    ("DPC陶瓷基板", ["DPC", "陶瓷基板"]),
    ("TGV玻璃基板", ["TGV", "玻璃基板"]),
    ("ABF/先进载板", ["ABF", "载板"]),
    ("CoWoP/先进封装", ["CoWoP", "CoWoS", "Chiplet", "先进封装"]),
    ("高速光模块与CPO", ["光模块", "CPO", "NPO", "LPO", "1.6T", "800G", "3.2T"]),
    ("光芯片与InP材料", ["光芯片", "InP", "磷化铟", "EML", "DFB", "VCSEL"]),
]

GENERIC_SEGMENTS = {
    "", "unknown", "未知", "未分段", "收入", "订单", "产能", "客户", "认证", "量产", "交付", "送样", "并购", "产品", "良率", "其他", "待核验",
}

GENERIC_CHAIN_LINKS = {"", "unknown", "未知", "上游", "中游", "下游", "配套", "生态", "产业链", "全链条"}

EVIDENCE_LAYER_RANK = {
    "graph_only": 0,
    "exposure_only": 1,
    "L4": 2,
    "L3_candidate": 3,
    "L3": 4,
    "L2_candidate": 5,
    "L1_L3_candidate": 6,
    "L2": 7,
    "L1": 8,
}

SOURCE_QUALITY_OFFICIAL = {"official_disclosure", "company_primary"}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return rows


def norm_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def short_text(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split()).replace("|", "/")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def match_rules(text: str, rules: list[tuple[str, list[str]]]) -> list[str]:
    return [label for label, keys in rules if any(key in text for key in keys)]


def infer_direction_type(direction: str, items: list[dict[str, Any]]) -> str:
    text = " ".join([direction] + [str(i.get(k) or "") for i in items for k in ("segment", "component", "claim", "chain_position")])
    hits = match_rules(text, DIRECTION_TYPE_RULES)
    return hits[0] if hits else "ecosystem"


def infer_chain_bucket(direction: str, items: list[dict[str, Any]]) -> str:
    text = " ".join([direction] + [str(i.get(k) or "") for i in items for k in ("segment", "component", "claim", "chain_position")])
    hits = match_rules(text, CHAIN_BUCKET_RULES)
    return hits[0] if hits else "midstream"


def infer_parent_sector(theme: str, direction: str, items: list[dict[str, Any]]) -> str:
    text = " ".join([theme, direction] + [str(i.get(k) or "") for i in items for k in ("segment", "component", "claim")])
    if any(x in text for x in ("PCB", "mSAP", "HDI", "干膜", "铜箔", "化学品")):
        return "PCB/载板"
    if any(x in text for x in ("光模块", "CPO", "1.6T", "800G", "光芯片")):
        return "光模块/CPO"
    if any(x in text for x in ("封装", "CoWo", "Chiplet", "TGV", "ABF")):
        return "先进封装"
    if any(x in text for x in ("服务器", "算力", "数据中心", "AI")):
        return "AI算力基础设施"
    return theme


def canonical_direction(raw: str, row: dict[str, Any]) -> str:
    raw_text = str(raw or "")
    for canonical, keys in CANONICAL_DIRECTION_RULES:
        if any(key in raw_text for key in keys):
            return canonical
    text = " ".join(str(row.get(k) or "") for k in ("segment", "component", "claim", "chain_position", "entity_name"))
    text = f"{raw} {text}"
    for canonical, keys in CANONICAL_DIRECTION_RULES:
        if any(key in text for key in keys):
            return canonical
    return raw


def raw_direction_key(row: dict[str, Any]) -> str:
    segment = str(row.get("segment") or row.get("chain_position") or "").strip()
    component = str(row.get("component") or "").strip()
    if segment and segment not in GENERIC_SEGMENTS:
        return segment
    if component and component not in GENERIC_SEGMENTS:
        return component
    entity = str(row.get("entity_name") or "").strip()
    if entity:
        return segment or component or entity
    return "未分段"


def direction_key(row: dict[str, Any]) -> str:
    raw = raw_direction_key(row)
    return canonical_direction(raw, row)


def theme_matches(row: dict[str, Any], theme: str) -> bool:
    row_theme = str(row.get("theme") or "").strip()
    if not row_theme or not theme:
        return True
    return theme in row_theme or row_theme in theme


def row_score(row: dict[str, Any]) -> int:
    types = set(as_list(row.get("info_types") or row.get("primary_info_type")))
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
        score += 5
    if len(set(as_list(row.get("source_systems")))) > 1 or row.get("cross_source"):
        score += 5
    if row.get("needs_review") is True:
        score -= 2
    if str(row.get("evidence_level") or "") in {"exposure_only", "graph_only"}:
        score -= 2
    return score


def evidence_rank(layer: str) -> int:
    return EVIDENCE_LAYER_RANK.get(str(layer or ""), -1)


def evidence_layer_from_items(items: list[dict[str, Any]]) -> str:
    layers = [str(i.get("evidence_level") or "") for i in items if i.get("evidence_level")]
    if not layers:
        return "theme_information_pool"
    return max(layers, key=evidence_rank)


def source_systems_from_items(items: list[dict[str, Any]]) -> list[str]:
    values = []
    for item in items:
        values.extend(str(x) for x in as_list(item.get("source_systems")) if str(x).strip())
    return unique(values)


def representative_entities_from_items(items: list[dict[str, Any]], exposures: dict[str, Any], evidence_index: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    evidence_items = evidence_index.get("items", []) if isinstance(evidence_index, dict) else []
    for item in sorted(items, key=row_score, reverse=True):
        name = str(item.get("entity_name") or "").strip()
        if not name or name in {"—", "-", "unknown", "无"}:
            continue
        node = exposures.get("entities", {}).get(name, {}) if isinstance(exposures, dict) else {}
        concepts = node.get("concepts", {}) if isinstance(node, dict) else {}
        exposure_values = list(concepts.values()) if isinstance(concepts, dict) else []
        highest_layer = ""
        source_quality = ""
        strength = ""
        role = ""
        review_required = item.get("needs_review")
        if exposure_values:
            best = max(exposure_values, key=lambda x: evidence_rank(str(x.get("evidence_layer") or "")) if isinstance(x, dict) else -1)
            if isinstance(best, dict):
                highest_layer = str(best.get("evidence_layer") or "")
                source_quality = str(best.get("source_quality") or "")
                strength = str(best.get("strength") or "")
                role = str(best.get("role") or "")
                if "review_required" in best:
                    review_required = best.get("review_required")
        ev_hits = [ev for ev in evidence_items if isinstance(ev, dict) and ev.get("target") == name]
        grouped.setdefault(name, {
            "name": name,
            "ticker": str(item.get("ticker") or "") or (node.get("codes", [""])[0] if isinstance(node.get("codes"), list) and node.get("codes") else ""),
            "role": role,
            "exposure_strength": strength,
            "evidence_layer": highest_layer or str(item.get("evidence_level") or ""),
            "source_quality": source_quality,
            "review_required": review_required,
            "pool_item_count": 0,
            "evidence_index_hits": len(ev_hits),
        })
        grouped[name]["pool_item_count"] += 1
    return list(grouped.values())[:8]


def evidence_profile(items: list[dict[str, Any]], representative_entities: list[dict[str, Any]]) -> dict[str, Any]:
    layers = [str(i.get("evidence_level") or "") for i in items]
    types = [str(t) for i in items for t in as_list(i.get("info_types") or i.get("primary_info_type")) if str(t)]
    systems = source_systems_from_items(items)
    entity_layers = [str(e.get("evidence_layer") or "") for e in representative_entities if e.get("evidence_layer")]
    official_entities = [e for e in representative_entities if str(e.get("source_quality") or "") in SOURCE_QUALITY_OFFICIAL]
    return {
        "item_count": len(items),
        "source_systems": systems,
        "source_count": sum(len(as_list(i.get("source_refs"))) or 1 for i in items),
        "highest_evidence_layer": max(layers + entity_layers, key=evidence_rank) if (layers or entity_layers) else "theme_information_pool",
        "has_official_evidence": bool(official_entities),
        "has_multi_source_support": len(systems) > 1 or any(i.get("cross_source") for i in items),
        "review_required_count": sum(1 for i in items if i.get("needs_review") is True),
        "hard_fact_candidate_count": sum(1 for x in layers if "hard_fact" in x),
        "research_claim_count": sum(1 for x in layers if x in {"curated_research", "review_candidate", "hard_fact_candidate"}),
        "graph_only_count": sum(1 for x in layers if x in {"graph_only", "exposure_only"}),
        "info_types": dict(Counter(types).most_common()),
    }


def recognition_stage(profile: dict[str, Any], items: list[dict[str, Any]]) -> str:
    score = 0
    if profile.get("item_count", 0) >= 8:
        score += 2
    elif profile.get("item_count", 0) >= 3:
        score += 1
    if profile.get("has_multi_source_support"):
        score += 2
    if profile.get("has_official_evidence"):
        score += 2
    if any("marginal_change" in set(as_list(i.get("info_types"))) for i in items):
        score += 1
    if any(str(i.get("source_date") or "") for i in items):
        score += 1
    if score >= 7:
        return "催化共振"
    if score >= 5:
        return "第一轮"
    if score >= 3:
        return "萌芽"
    return "暗流"


def catalysts_from_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in sorted(items, key=row_score, reverse=True):
        types = set(as_list(item.get("info_types") or item.get("primary_info_type")))
        text = str(item.get("claim") or "")
        if "marginal_change" not in types and not re.search(r"试产|量产|订单|扩产|涨价|发布|验证|导入|客户|政策|会议|电话会", text):
            continue
        out.append({
            "event": short_text(text, 120),
            "time_window": str(item.get("source_date") or ""),
            "source": source_systems_from_items([item])[0] if source_systems_from_items([item]) else str(item.get("source_title") or ""),
            "confidence": str(item.get("confidence") or ""),
            "item_id": item.get("item_id"),
        })
    return out[:6]


def verification_items_from_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in sorted(items, key=row_score, reverse=True):
        raw = item.get("raw_row") if isinstance(item.get("raw_row"), dict) else {}
        text = raw.get("下一步验证") or raw.get("验证节点") or raw.get("待验证事项") or ""
        if not text:
            claim = str(item.get("claim") or "")
            if re.search(r"试产|量产|订单|扩产|认证|客户|导入|收入|占比|ASP|涨价", claim):
                text = "跟踪公告/定期报告/电话会中是否确认：" + short_text(claim, 80)
        if not text:
            continue
        out.append({
            "item": short_text(text, 140),
            "upgrade_condition": "出现官方公告、定期报告、客户/订单/量产/收入占比等一手证据后升级证据层级。",
            "downgrade_condition": "后续公告或产业反馈证伪、进度延后、或无法形成公司级证据时降级为观察线索。",
            "source_item_id": item.get("item_id"),
        })
    return out[:6]


def risks_from_items(items: list[dict[str, Any]], profile: dict[str, Any]) -> list[str]:
    risks = []
    if profile.get("review_required_count", 0):
        risks.append("部分来源标记为 needs_review，需人工复核后再进入硬事实。")
    if not profile.get("has_official_evidence"):
        risks.append("暂缺公告/公司官网/定期报告等官方证据，不能升级为 hard_fact。")
    if not profile.get("has_multi_source_support"):
        risks.append("当前主要为单源线索，需跨源互证。")
    if any(str(i.get("ticker") or "").lower() in {"unknown", ""} and i.get("entity_name") for i in items):
        risks.append("部分实体 ticker 缺失或未核验。")
    if any(str(i.get("evidence_level") or "") in {"graph_only", "exposure_only"} for i in items):
        risks.append("存在 graph_only/exposure_only 弱证据，只能作为地图或观察线索。")
    return unique(risks)[:5]


def aggregate_direction_profiles(rows: list[dict[str, Any]]) -> dict[str, Any]:
    profiles = [row.get("evidence_profile", {}) for row in rows if isinstance(row.get("evidence_profile"), dict)]
    layers = [str(p.get("highest_evidence_layer") or "") for p in profiles if p.get("highest_evidence_layer")]
    systems = unique([str(system) for p in profiles for system in as_list(p.get("source_systems"))])
    return {
        "direction_count": len(rows),
        "item_count": sum(int(p.get("item_count") or 0) for p in profiles),
        "source_systems": systems,
        "highest_evidence_layer": max(layers, key=evidence_rank) if layers else "direction_pool",
        "has_official_evidence": any(p.get("has_official_evidence") for p in profiles),
        "has_multi_source_support": any(p.get("has_multi_source_support") for p in profiles) or len(systems) > 1,
        "review_required_count": sum(int(p.get("review_required_count") or 0) for p in profiles),
    }


def build_demand_bottleneck_map(directions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in directions:
        if not isinstance(row, dict):
            continue
        demands = as_list(row.get("demand_sources"))
        bottlenecks = as_list(row.get("bottlenecks_solved"))
        if not demands and not bottlenecks:
            continue
        if not demands:
            demands = ["题材主线需求"]
        if not bottlenecks:
            bottlenecks = ["待验证瓶颈"]
        for demand in demands[:2]:
            for bottleneck in bottlenecks[:2]:
                grouped[(str(demand), str(bottleneck))].append(row)
    rows = []
    for (demand, bottleneck), linked in grouped.items():
        entities = []
        for direction in linked:
            entities.extend(entity.get("name", "") for entity in direction.get("representative_entities", []) if isinstance(entity, dict))
        verifications = []
        for direction in linked:
            verifications.extend(item.get("item", "") for item in direction.get("verification_items", []) if isinstance(item, dict))
        catalysts = []
        for direction in linked:
            catalysts.extend(item.get("event", "") for item in direction.get("catalysts", []) if isinstance(item, dict))
        source_items = []
        for direction in linked:
            source_items.extend(str(item) for item in direction.get("source_items", []) if item)
        rows.append({
            "demand_source": demand,
            "bottleneck": bottleneck,
            "chain_links": unique([direction.get("direction", "") for direction in linked if str(direction.get("direction", "")).strip() not in GENERIC_CHAIN_LINKS] + [link for direction in linked for link in as_list(direction.get("beneficiary_links")) if str(link).strip() not in GENERIC_CHAIN_LINKS])[:12],
            "directions": unique([direction.get("direction", "") for direction in linked])[:12],
            "beneficiary_entities": unique(entities)[:12],
            "evidence_profile": aggregate_direction_profiles(linked),
            "verification_items": unique(verifications)[:8],
            "catalysts": unique(catalysts)[:8],
            "source_items": unique(source_items)[:40],
        })
    return sorted(rows, key=lambda row: (row["evidence_profile"]["item_count"], row["evidence_profile"]["direction_count"]), reverse=True)


def build_direction_pool(theme: str, rows: list[dict[str, Any]], relations_dir: Path, min_score: int) -> dict[str, Any]:
    graph = load_json(relations_dir / "concept_graph.json", {"concepts": {}})
    exposures = load_json(relations_dir / "entity_exposures.json", {"entities": {}})
    evidence_index = load_json(relations_dir / "evidence_index.json", {"items": []})
    filtered = [r for r in rows if theme_matches(r, theme)]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in filtered:
        if row_score(row) < min_score:
            continue
        key = direction_key(row)
        if key in GENERIC_SEGMENTS:
            continue
        groups[key].append(row)
    directions = []
    for direction, items in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        ranked_items = sorted(items, key=row_score, reverse=True)
        raw_directions = unique([raw_direction_key(i) for i in ranked_items if raw_direction_key(i) not in GENERIC_SEGMENTS])
        text = " ".join([direction] + raw_directions + [str(i.get(k) or "") for i in ranked_items for k in ("claim", "segment", "component", "chain_position")])
        representatives = representative_entities_from_items(ranked_items, exposures, evidence_index)
        profile = evidence_profile(ranked_items, representatives)
        source_ids = [str(i.get("item_id")) for i in ranked_items if i.get("item_id")]
        directions.append({
            "direction": direction,
            "raw_directions": raw_directions[:20],
            "direction_type": infer_direction_type(direction, ranked_items),
            "chain_bucket": infer_chain_bucket(direction, ranked_items),
            "parent_sector": infer_parent_sector(theme, direction, ranked_items),
            "demand_sources": match_rules(text, DEMAND_RULES),
            "bottlenecks_solved": match_rules(text, BOTTLENECK_RULES),
            "beneficiary_links": unique([str(i.get("chain_position") or i.get("segment") or "") for i in ranked_items])[:8],
            "representative_entities": representatives,
            "evidence_profile": profile,
            "recognition_stage": recognition_stage(profile, ranked_items),
            "catalysts": catalysts_from_items(ranked_items),
            "verification_items": verification_items_from_items(ranked_items),
            "risks": risks_from_items(ranked_items, profile),
            "source_items": source_ids[:30],
            "sample_claims": [short_text(i.get("claim"), 120) for i in ranked_items[:5] if i.get("claim")],
        })
    demand_bottleneck_map = build_demand_bottleneck_map(directions)
    summary = {
        "theme": theme,
        "generated_at": date.today().isoformat(),
        "direction_count": len(directions),
        "demand_bottleneck_map_count": len(demand_bottleneck_map),
        "input_row_count": len(rows),
        "matched_row_count": len(filtered),
        "min_score": min_score,
        "directions_by_type": dict(Counter(d["direction_type"] for d in directions)),
        "directions_by_chain_bucket": dict(Counter(d["chain_bucket"] for d in directions)),
        "directions_by_recognition_stage": dict(Counter(d["recognition_stage"] for d in directions)),
        "safety_statement": "Direction pool is read-only intelligence. It does not write entities/relations and must not upgrade IMA/research clues to hard facts without official evidence.",
    }
    return {
        "version": 1,
        "theme": theme,
        "generated_at": summary["generated_at"],
        "summary": summary,
        "directions": directions,
        "demand_bottleneck_map": demand_bottleneck_map,
        "relation_inputs": {
            "concept_graph_loaded": bool(graph.get("concepts")),
            "entity_exposures_loaded": bool(exposures.get("entities")),
            "evidence_index_items": len(evidence_index.get("items", [])) if isinstance(evidence_index, dict) else 0,
        },
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, pool: dict[str, Any], limit: int) -> None:
    lines = [
        f"# {pool['theme']} 细分方向池",
        "",
        f"生成日期：{pool['generated_at']}",
        "",
        "## 摘要",
        "",
        f"- 方向数：{pool['summary']['direction_count']}",
        f"- 需求-瓶颈映射数：{pool['summary'].get('demand_bottleneck_map_count', 0)}",
        f"- 匹配条目：{pool['summary']['matched_row_count']} / 输入条目：{pool['summary']['input_row_count']}",
        f"- 安全边界：{pool['summary']['safety_statement']}",
        "",
        "## 需求-瓶颈-环节传导",
        "",
        "| 需求来源 | 技术瓶颈 | 受益环节 | 代表实体 | 证据画像 | 下一步验证 |",
        "|---|---|---|---|---|---|",
    ]
    for row in pool.get("demand_bottleneck_map", [])[:limit]:
        profile = row.get("evidence_profile", {})
        evidence = f"{profile.get('item_count', 0)}条/{profile.get('highest_evidence_layer', '')}"
        lines.append(
            "| "
            + " | ".join([
                str(row.get("demand_source", "")),
                str(row.get("bottleneck", "")),
                "、".join(row.get("chain_links", [])[:6]),
                "、".join(row.get("beneficiary_entities", [])[:6]),
                evidence,
                short_text((row.get("verification_items") or [""])[0], 80),
            ])
            + " |"
        )
    lines.extend([
        "",
        "## 方向扫描",
        "",
        "| 方向 | 类型 | 链条位置 | 认知水位 | 需求来源 | 技术瓶颈 | 代表实体 | 证据画像 | 下一步验证 |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    for row in pool.get("directions", [])[:limit]:
        entities = "、".join(e.get("name", "") for e in row.get("representative_entities", [])[:5] if e.get("name"))
        profile = row.get("evidence_profile", {})
        evidence = f"{profile.get('item_count', 0)}条/{profile.get('highest_evidence_layer', '')}"
        verify = row.get("verification_items", [])
        lines.append(
            "| "
            + " | ".join([
                str(row.get("direction", "")),
                str(row.get("direction_type", "")),
                str(row.get("chain_bucket", "")),
                str(row.get("recognition_stage", "")),
                "、".join(row.get("demand_sources", []) or []),
                "、".join(row.get("bottlenecks_solved", []) or []),
                entities,
                evidence,
                short_text(verify[0].get("item") if verify else "", 80),
            ])
            + " |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Theme Radar fine-grained direction pool")
    parser.add_argument("--theme", required=True)
    parser.add_argument("--theme-info-jsonl", required=True)
    parser.add_argument("--relations-dir", default="/Users/lbq/Desktop/c c/知识库/wiki/relations")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--min-score", type=int, default=8)
    parser.add_argument("--md-limit", type=int, default=30)
    args = parser.parse_args()

    jsonl_path = Path(args.theme_info_jsonl).expanduser()
    relations_dir = Path(args.relations_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    rows = read_jsonl(jsonl_path)
    pool = build_direction_pool(args.theme, rows, relations_dir, args.min_score)
    prefix = args.prefix or args.theme
    write_json(out_dir / f"{prefix}.theme_direction_pool.json", pool)
    write_markdown(out_dir / f"{prefix}.theme_direction_pool.md", pool, args.md_limit)
    print(json.dumps(pool["summary"], ensure_ascii=False, indent=2))
    print(f"[OK] wrote: {out_dir / f'{prefix}.theme_direction_pool.json'}")
    print(f"[OK] wrote: {out_dir / f'{prefix}.theme_direction_pool.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

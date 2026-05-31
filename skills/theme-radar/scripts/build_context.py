#!/usr/bin/env python3
"""Draft a theme-radar context JSON from raw notes.

This is intentionally conservative. It creates a reviewable draft instead of
claiming a fully verified research result.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DIRECTION_RULES = [
    ("mSAP半加成法", "PCB", ["mSAP", "MSAP", "半加成法"], "PCB精细线路工艺升级"),
    ("感光干膜", "PCB材料", ["感光干膜", "干膜"], "mSAP扩散带动高端干膜需求"),
    ("载体铜箔", "PCB材料", ["载体铜箔", "HVLP"], "高频高速PCB铜箔升级与国产替代"),
    ("PCB化学品", "PCB材料", ["PCB化学品", "电镀液", "蚀刻液"], "精细线路制程材料需求"),
    ("DPC陶瓷基板", "半导体散热", ["DPC陶瓷基板", "DPC"], "高功率芯片散热方案验证"),
    ("TGV玻璃基板", "先进封装", ["TGV", "玻璃基板"], "先进封装载板长期替代"),
    ("磷化铟(InP)", "光芯片材料", ["磷化铟", "InP"], "高速光模块材料升级"),
    ("ABF载板", "封装载板", ["ABF载板", "ABF"], "先进封装载板需求"),
    ("Low-CTE/T布", "PCB材料", ["Low-CTE", "T布", "低CTE"], "高速PCB低膨胀材料"),
]

CHAIN_BUCKETS = {
    "upstream_materials": ["感光干膜", "载体铜箔", "PCB化学品", "磷化铟(InP)", "ABF载板", "Low-CTE/T布"],
    "upstream_equipment": ["曝光", "设备", "激光", "电镀设备"],
    "midstream": ["mSAP半加成法", "PCB", "HDI", "类载板", "DPC陶瓷基板", "TGV玻璃基板"],
    "downstream": ["1.6T光模块", "DDR5/存储模组", "CoWoP先进封装", "AI服务器", "Rubin平台"],
}

SCENARIO_RULES = [
    ("1.6T光模块", ["1.6T", "光模块"], "速率提升推动PCB线宽/线距和高频材料要求提升"),
    ("DDR5/存储模组", ["DDR5", "存储模组", "SO-DIMM"], "服务器内存条升级提升PCB制程要求"),
    ("CoWoP先进封装", ["CoWoP", "先进封装"], "去中介层后PCB承载更多互联功能"),
    ("AI服务器", ["AI服务器", "算力服务器"], "算力需求拉动高速PCB和材料升级"),
    ("Rubin平台", ["Rubin"], "新平台试产是需求确认节点"),
]

TIME_PATTERNS = [
    r"即时[:：]?\s*([^。\n]+)",
    r"(6月|Q[1-4]|202[6-9]年|明年|下半年|上半年)[:：]?\s*([^。\n]+)",
]


def unique(items):
    out = []
    seen = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def contains_any(text: str, words: list[str]) -> bool:
    lowered = text.lower()
    return any(word.lower() in lowered for word in words)


def short_hits(text: str, words: list[str], limit: int = 3) -> list[str]:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"[。；;]\s*", line)
        lines.extend(part.strip() for part in parts if part.strip())
    hits = []
    for line in lines:
        if contains_any(line, words):
            hits.append(line[:80])
        if len(hits) >= limit:
            break
    return hits


def infer_definition(term: str, text: str) -> str:
    patterns = [
        rf"{re.escape(term)}[^。\n]{{0,120}}(?:是|指|为)[^。\n]{{5,160}}",
        r"mSAP[^。\n]{0,80}(?:是|为)[^。\n]{5,160}",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(0).strip(" ，。")
    return ""


def infer_demand_scenarios(text: str) -> list[dict]:
    rows = []
    for scenario, words, logic in SCENARIO_RULES:
        if not contains_any(text, words):
            continue
        hits = short_hits(text, words)
        requirement = ""
        joined = " ".join(hits)
        m = re.search(r"(线宽[^，。；\n]{0,30}|高层数[^，。；\n]{0,20}|高密度[^，。；\n]{0,20}|超精细线路[^，。；\n]{0,20})", joined)
        if m:
            requirement = m.group(0)
        rows.append({
            "scenario": scenario,
            "logic": logic,
            "process_requirement": requirement or "待补",
            "evidence": hits[:2],
            "evidence_type": "source" if hits else "inferred",
            "confidence": "medium" if hits else "low",
        })
    return rows


def infer_direction_scan(text: str) -> list[dict]:
    rows = []
    for direction, sector, words, default_logic in DIRECTION_RULES:
        if not contains_any(text, words):
            continue
        hits = short_hits(text, words)
        freq = "中频" if len(hits) >= 2 else "低频"
        recognition = "L2-L3" if freq == "中频" else "L1-L2"
        classification = "发酵" if freq == "中频" else "布局"
        rows.append({
            "direction": direction,
            "sector": sector,
            "prosperity": hits[0] if hits else default_logic,
            "mention_frequency": freq,
            "recognition_level": recognition,
            "classification": classification,
            "core_catalyst": infer_catalyst_for_direction(direction, text),
            "candidate_companies": infer_companies_near_direction(direction, text),
            "evidence": hits[:2],
            "evidence_type": "source" if hits else "inferred",
            "confidence": "medium" if hits else "low",
        })
    return rows


def infer_catalyst_for_direction(direction: str, text: str) -> str:
    if direction == "感光干膜":
        return "mSAP产线扩张 -> 高端干膜需求验证"
    if direction == "载体铜箔":
        return "HVLP涨价/国产替代/客户导入"
    if direction == "mSAP半加成法":
        return "AI服务器PCB升级 + Rubin/光模块/存储需求确认"
    if direction == "TGV玻璃基板":
        return "量产进度与ABF替代验证"
    if direction == "DPC陶瓷基板":
        return "Rubin散热方案验证"
    return "待补"


def infer_companies_near_direction(direction: str, text: str) -> list[str]:
    known = {
        "mSAP半加成法": ["鹏鼎控股", "深南电路", "一博科技", "景旺电子", "兴森科技", "胜宏科技"],
        "感光干膜": ["福斯特", "容大感光"],
        "PCB化学品": ["天承科技"],
    }
    found = []
    for company in known.get(direction, []):
        if company in text:
            found.append(company)
    return found


def infer_progress_ranking(direction_scan: list[dict], text: str) -> list[dict]:
    rows = []
    for row in direction_scan:
        direction = row["direction"]
        freq = row.get("mention_frequency", "低频")
        classification = row.get("classification", "布局")
        score = 55
        stage = "萌芽期"
        priority = "观察"
        evidence = "Tier 3"
        if classification == "发酵":
            score = 78
            stage = "第一轮"
            priority = "重点跟踪"
            evidence = "Tier 2"
        if direction == "mSAP半加成法":
            score = 86
            stage = "催化共振"
            priority = "已发酵，防一致预期"
            evidence = "Tier 1"
        elif direction in {"感光干膜", "载体铜箔", "PCB化学品"}:
            score = max(score, 70)
            priority = "重点跟踪"
            evidence = "Tier 2"
        rows.append({
            "direction": direction,
            "stage": stage,
            "recognition_level": row.get("recognition_level", "待补"),
            "evidence_level": evidence,
            "progress_score": score,
            "key_signal": row.get("prosperity", ""),
            "next_validation": row.get("core_catalyst", "待补"),
            "priority": priority,
            "evidence_type": "inferred",
            "confidence": "low",
        })
    return rows


def infer_catalyst_calendar(text: str) -> list[dict]:
    rows = []
    for pattern in TIME_PATTERNS:
        for m in re.finditer(pattern, text):
            if len(m.groups()) == 1:
                time, event = "即时", m.group(1)
            else:
                time, event = m.group(1), m.group(2)
            rows.append({"time": time, "event": event.strip(), "watch_item": "验证订单、价格、客户认证或产能变化"})
    return rows[:12]


def infer_validation_checklist(text: str) -> list[dict]:
    rows = []
    lines = []
    for line in text.splitlines():
        line = line.strip(" 　-□*")
        if not line:
            continue
        if "验证清单" in line:
            line = line.split("：", 1)[-1]
        lines.extend(part.strip(" 　-□*") for part in re.split(r"[；;。]", line) if part.strip())
    for line in lines:
        if any(key in line for key in ["是否", "验证", "订单", "涨价", "认证", "产线", "扩产", "收入占比"]):
            rows.append({
                "item": line[:100],
                "why": "关系到题材从逻辑推演进入事实验证",
                "status": "待验证",
                "evidence_type": "source",
            })
        if len(rows) >= 12:
            break
    return rows


def infer_industry_chain_map(direction_scan: list[dict], demand_scenarios: list[dict]) -> dict:
    chain = {key: [] for key in CHAIN_BUCKETS}
    direction_names = [row["direction"] for row in direction_scan]
    scenario_names = [row["scenario"] for row in demand_scenarios]
    all_names = direction_names + scenario_names
    for bucket, keywords in CHAIN_BUCKETS.items():
        for name in all_names:
            if any(keyword in name for keyword in keywords):
                chain[bucket].append({"name": name, "role": bucket, "evidence_type": "source"})
    return {key: unique_by_name(value) for key, value in chain.items()}


def unique_by_name(items: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for item in items:
        name = item.get("name")
        if name and name not in seen:
            seen.add(name)
            out.append(item)
    return out


def extraction_quality(data: dict) -> dict:
    tracked = [
        "demand_scenarios",
        "direction_scan",
        "progress_ranking",
        "catalyst_calendar",
        "validation_checklist",
    ]
    total = 0
    source_backed = 0
    inferred = 0
    missing = []
    for field in tracked:
        rows = data.get(field) or []
        if not rows:
            missing.append(field)
            continue
        total += len(rows)
        for row in rows:
            if isinstance(row, dict) and row.get("evidence_type") == "source":
                source_backed += 1
            else:
                inferred += 1
    return {
        "mode": "rule_draft",
        "total_items": total,
        "source_backed_items": source_backed,
        "inferred_items": inferred,
        "missing_fields": missing,
        "review_required": True,
    }


def build_context(term: str, text: str) -> dict:
    direction_scan = infer_direction_scan(text)
    demand_scenarios = infer_demand_scenarios(text)
    progress_ranking = infer_progress_ranking(direction_scan, text)
    demand_drivers = unique([row["scenario"] for row in demand_scenarios])
    related_terms = unique([row["direction"] for row in direction_scan])

    data = {
        "term": term,
        "definition": infer_definition(term, text),
        "aliases": [],
        "english_terms": [],
        "parent_concepts": [],
        "chain_position": [],
        "related_terms": related_terms,
        "problem_solved": "",
        "technical_modules": [],
        "required_capabilities": [],
        "capability_stack": [],
        "demand_drivers": demand_drivers,
        "demand_scenarios": demand_scenarios,
        "industry_chain_map": infer_industry_chain_map(direction_scan, demand_scenarios),
        "direction_scan": direction_scan,
        "progress_ranking": progress_ranking,
        "catalyst_calendar": infer_catalyst_calendar(text),
        "validation_checklist": infer_validation_checklist(text),
        "upstream": [],
        "midstream": [],
        "downstream": [],
        "core_benefit_links": [],
        "bottlenecks": [],
        "verification_nodes": [],
        "candidate_companies": unique(sum((row.get("candidate_companies", []) for row in direction_scan), [])),
        "source_urls": [],
        "confidence": "low",
        "raw_extraction_note": "规则抽取草稿，需人工/LLM复核后再用于正式分析。"
    }
    data["extraction_quality"] = extraction_quality(data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a draft theme-radar context JSON from text notes.")
    parser.add_argument("--term", required=True)
    parser.add_argument("--input", required=True, help="raw text file")
    parser.add_argument("--out", help="optional JSON output")
    args = parser.parse_args()

    text = Path(args.input).expanduser().read_text(encoding="utf-8")
    data = build_context(args.term, text)
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

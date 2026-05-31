#!/usr/bin/env python3
"""Backfill entity delta notes from raw *-full.md research reports.

This is a conservative extractor for the theme-radar/entity-delta workflow:
- read each raw full report as one source;
- only update existing wiki/entities pages;
- skip a company if that entity page already mentions the source;
- split report mentions into full delta notes vs exposure-only graph evidence;
- write report-level industry-chain context to relations/report_contexts.json;
- write per-source JSON payloads for review, then optionally call the writer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VAULT = Path(os.path.expanduser("~/Desktop/c c/知识库/wiki"))
DEFAULT_RAW_DIR = DEFAULT_VAULT.parent / "raw"
WRITER = ROOT / "skills/entity-delta-ingest/scripts/entity_delta_writer.py"
RELATIONS_DIR = DEFAULT_VAULT / "relations"


STRONG_KEYWORDS = (
    "核心供应商", "绝对龙头", "龙头", "独家", "第一", "全球第", "国内第",
    "市占率", "份额", "供货", "供应", "客户", "订单", "合同", "产能",
    "量产", "投产", "突破", "认证", "导入", "营收", "净利润", "同比",
    "毛利率", "增长", "核心标的", "重点投资标的", "配置价值",
)
HARD_DELTA_KEYWORDS = (
    "订单", "合同", "中标", "认证", "客户导入", "量产", "投产", "扩产", "产能",
    "样机", "技术突破", "项目落地", "公告",
)
HARD_FINANCIAL_KEYWORDS = ("营收", "收入", "净利润", "扣非", "同比", "毛利率", "销量", "出货")
REVIEW_CANDIDATE_KEYWORDS = (
    "送样", "样品", "长协", "配套", "供货", "供应商", "客户", "合作方", "导入",
    "控股", "持股", "参股", "股东", "良率", "收入", "营收", "销量", "出货",
    "同比", "市占率", "市场占有率", "份额", "项目", "套", "台",
)
CORE_KEYWORDS = ("核心供应商", "绝对龙头", "龙头", "全球第一", "国内第一", "第一大", "市占率", "份额")
PERIPHERAL_ROLE_KEYWORDS = ("上游材料", "上游设备", "下游应用", "客户", "生态", "原材料")
WEAK_LIST_MARKERS = ("包括：", "主要包括", "相关公司", "标的包括", "等。")
BAD_SECTIONS = ("参考文献", "资料来源", "免责声明", "风险提示", "附录")
CHAIN_HEADINGS = ("产业链", "上游", "中游", "下游", "核心个股", "关联概念", "细分", "应用")


def split_frontmatter(text: str):
    if not text.startswith("---\n"):
        return {}, text
    lines = text.splitlines()
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            meta = {}
            for line in lines[1:i]:
                m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
                if m:
                    meta[m.group(1)] = m.group(2).strip()
            return meta, "\n".join(lines[i + 1 :])
    return {}, text


def parse_list_value(value: str):
    value = str(value or "").strip()
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
    except Exception:
        pass
    return re.findall(r'"([^"]+)"', value)


def normalize_company(name: str) -> str:
    name = re.sub(r"（\d{6}）$", "", str(name or "")).strip()
    return name


def safe_source_name(path: Path) -> str:
    return path.stem.removesuffix("-full").strip()


def infer_concept(source_name: str) -> str:
    text = source_name
    text = re.sub(r"(深度|全面)?研究(分析)?报告.*$", "", text)
    text = re.sub(r"产业(链)?(新变化|新格局|投资|深度|全面|分析|研究|与|：|:).*$", "", text)
    text = re.sub(r"行业.*$", "", text)
    text = text.strip(" ：:-")
    return text or source_name


def load_entities(vault: Path):
    entities = []
    for path in sorted((vault / "entities").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, _ = split_frontmatter(text)
        title = meta.get("title", "").strip().strip('"')
        name = normalize_company(re.sub(r"（\d{6}）", "", title) or path.stem)
        if not name or len(name) < 2:
            continue
        tickers = parse_list_value(meta.get("tickers", "[]"))
        code = tickers[0] if tickers else ""
        aliases = parse_list_value(meta.get("aliases", "[]"))
        names = [name, path.stem] + [normalize_company(a) for a in aliases]
        names = sorted({n for n in names if len(n) >= 2}, key=len, reverse=True)
        entities.append({"name": name, "code": code, "path": path, "names": names})
    return entities


def already_has_source(entity_path: Path, source_name: str) -> bool:
    text = entity_path.read_text(encoding="utf-8")
    return f"### " in text and f"｜{source_name}" in text


def report_date(text: str) -> str:
    head = "\n".join(text.splitlines()[:80])
    m = re.search(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", head)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", head)
    if m:
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return date.today().isoformat()


def clean_segment(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\(\d+\)", "", text)
    return text.strip()


def split_sentences(text: str):
    text = clean_segment(text)
    parts = re.split(r"(?<=[。！？；;])", text)
    return [p.strip() for p in parts if p.strip()]


def iter_blocks(text: str):
    current_heading = ""
    in_bad = False
    buf = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if buf:
                yield current_heading, "\n".join(buf)
                buf = []
            continue
        if any(bad in line for bad in BAD_SECTIONS):
            in_bad = True
        if re.match(r"^(#{1,6}\s+)?(\d+(\.\d+)*[、. ]+|[一二三四五六七八九十]+[、.])", line):
            if buf:
                yield current_heading, "\n".join(buf)
                buf = []
            current_heading = re.sub(r"^#{1,6}\s*", "", line)
            in_bad = any(bad in line for bad in BAD_SECTIONS)
            continue
        if in_bad:
            continue
        if re.match(r"^\[\d+\]", line):
            continue
        buf.append(line)
    if buf:
        yield current_heading, "\n".join(buf)


def score_block(block: str, company: str) -> int:
    score = 0
    if company in block:
        score += 5
    score += sum(2 for kw in STRONG_KEYWORDS if kw in block)
    if re.search(r"\d+(\.\d+)?\s*(%|亿元|万|亿|万吨|片|GW|GWh|MW|TOPS)", block):
        score += 4
    if any(marker in block for marker in WEAK_LIST_MARKERS) and len(block) > 180:
        score -= 4
    if len(block) < 35:
        score -= 5
    if len(block) > 900:
        score -= 3
    return score


def is_company_subject(block: str, company: str, aliases=None) -> bool:
    aliases = aliases or [company]
    prefix = block[:80]
    for name in aliases:
        if not name:
            continue
        if re.search(rf"^(\*\*\s*)?{re.escape(name)}(（\d{{6}}）)?", prefix):
            return True
        if re.search(rf"(^|[。；;]\s*){re.escape(name)}(（\d{{6}}）)?(是|作为|为|在|拥有|实现|已|将|具有)", block[:220]):
            return True
    return False


def infer_role(heading: str, block: str) -> str:
    text = f"{heading} {block}"
    for key, role in [
        ("上游", "上游材料/设备"),
        ("材料", "上游材料"),
        ("设备", "上游设备"),
        ("中游", "中游制造/服务"),
        ("制造", "中游制造"),
        ("封装", "中游封装测试"),
        ("封测", "中游封装测试"),
        ("芯片", "芯片/核心器件"),
        ("零部件", "核心零部件"),
        ("供应商", "产业链供应商"),
        ("下游", "下游应用/客户"),
        ("应用", "下游应用"),
    ]:
        if key in text:
            return role
    return heading[:40] if heading else "受益标的"


def infer_chain_layer(role: str, heading: str, block: str) -> str:
    text = f"{role} {heading} {block}"
    if any(k in text for k in ("上游", "材料", "原材料", "铜材", "钢材", "稀土", "树脂", "光刻胶")):
        return "upstream_materials"
    if any(k in text for k in ("设备", "装备", "机床", "检测", "仪器")):
        return "upstream_equipment"
    if any(k in text for k in ("下游", "应用", "客户", "需求", "终端")):
        return "downstream"
    if any(k in text for k in ("生态", "平台", "运营商")):
        return "ecosystem"
    return "midstream"


def infer_context_term_layer(token: str) -> str:
    if any(k in token for k in ("石英", "材料", "毛细管", "预制棒", "光棒")):
        return "upstream_materials"
    if any(k in token for k in ("拉丝设备", "检测设备", "测试设备")):
        return "upstream_equipment"
    if any(k in token for k in ("光纤拉丝", "制造", "成缆", "连接器", "耦合器", "光模块", "系统集成", "传输设备", "海底光缆")):
        return "midstream"
    if any(k in token for k in ("数据中心", "金融", "量子通信", "高功率激光", "运营商", "云厂商", "低时延网络", "互联")):
        return "downstream"
    return ""


def infer_tier(block: str, role: str = "", chain_layer: str = "") -> str:
    if chain_layer in {"upstream_materials", "upstream_equipment", "downstream", "ecosystem"}:
        if not any(kw in block for kw in CORE_KEYWORDS):
            return "peripheral"
    if any(kw in block for kw in ("绝对龙头", "核心供应商", "核心标的", "独家", "全球第一", "国内第一", "第一大")):
        return "core"
    if any(marker in block for marker in WEAK_LIST_MARKERS) and len(block) > 180:
        return "peripheral"
    return "related"


def has_hard_delta_fact(block: str) -> bool:
    if any(kw in block for kw in HARD_DELTA_KEYWORDS):
        return True
    if any(kw in block for kw in ("营收", "收入", "净利润", "扣非", "毛利率")) and re.search(r"\d+(\.\d+)?\s*(亿元|万元|亿|万)", block):
        return True
    if any(kw in block for kw in ("销量", "出货", "出货量")) and re.search(r"\d+(\.\d+)?\s*(万片|片|万台|台|万辆|辆|GW|GWh|MW)", block):
        return True
    return False


def has_review_candidate_fact(block: str) -> bool:
    if "市值弹性" in block:
        return False
    if not any(kw in block for kw in REVIEW_CANDIDATE_KEYWORDS):
        return False
    if any(kw in block for kw in ("送样", "样品", "长协", "配套", "供货", "供应商", "客户", "合作方", "导入", "控股", "持股", "参股", "股东")):
        return True
    if any(kw in block for kw in ("收入", "营收", "销量", "出货", "同比", "增长", "良率", "市占率", "市场占有率", "份额")) and re.search(r"\d+(\.\d+)?\s*(%|亿元|万元|亿|万|万片|片|万台|台|万辆|辆|GW|GWh|MW|TOPS)", block):
        return True
    if any(kw in block for kw in ("项目", "套", "台")) and re.search(r"\d+(\.\d+)?\s*(个|套|台)", block):
        return True
    return False


def should_write_delta(block: str, role: str, chain_layer: str, tier: str) -> bool:
    return False


def evidence_layer_for(block: str, exposure_only: bool) -> str:
    if not exposure_only and any(kw in block for kw in ("公告", "订单", "合同", "中标", "认证", "量产", "投产", "客户导入", "项目落地")):
        return "L2_candidate"
    if exposure_only and has_review_candidate_fact(block):
        return "L1_L3_candidate"
    return "L1" if exposure_only else "L1_L3_candidate"


def build_update(company, code, source_date, source_name, concept, heading, block):
    sentences = split_sentences(block)
    selected = [s for s in sentences if company in s][:2]
    if not selected:
        selected = sentences[:2]
    if len(selected) == 1:
        try:
            idx = sentences.index(selected[0])
        except ValueError:
            idx = -1
        if idx >= 0 and idx + 1 < len(sentences):
            nxt = sentences[idx + 1]
            looks_like_other_company = re.match(r"^[\u4e00-\u9fa5A-Za-z0-9]{2,12}(（\d{6}）)?(在|作为|是|凭借|同样|：)", nxt) and company not in nxt[:20]
            if not looks_like_other_company and (
                any(kw in nxt for kw in STRONG_KEYWORDS)
                or re.search(r"\d+(\.\d+)?\s*(%|亿元|万|亿|万吨|片|GW|GWh|MW|TOPS)", nxt)
            ):
                selected.append(nxt)
    bullets = []
    for sent in selected:
        sent = clean_segment(sent)
        if len(sent) > 180:
            sent = sent[:177].rstrip() + "..."
        if sent and sent not in bullets:
            bullets.append(sent)
    if not bullets:
        return None
    evidence = bullets[0]
    evidence_text = "。".join(bullets)
    title = f"{concept}研究报告提及公司边际信息"
    if any(k in evidence_text for k in ("营收", "净利润", "同比", "毛利率")):
        title = f"{concept}相关业绩与产业链进展"
    elif any(k in evidence_text for k in ("核心供应商", "供货", "客户", "订单", "认证", "导入")):
        title = f"{concept}供应链角色强化"
    role = infer_role(heading, block)
    chain_layer = infer_chain_layer(role, heading, block)
    tier = infer_tier(block, role, chain_layer)
    review_candidate = has_review_candidate_fact(evidence_text)
    exposure_only = not should_write_delta(evidence_text, role, chain_layer, tier)
    graph_only = exposure_only
    update_type = "review_candidate" if review_candidate else "graph_only"
    return {
        "company": company,
        "code": code,
        "date": source_date,
        "title": title,
        "judgment": "研究报告提及，需后续公告/财报交叉验证",
        "concepts": [concept],
        "role": role,
        "chain_layer": chain_layer,
        "tier": tier,
        "confidence": "medium",
        "evidence_layer": evidence_layer_for(evidence_text, exposure_only),
        "exposure_only": exposure_only,
        "graph_only": graph_only,
        "update_type": update_type,
        "fact_hardness": "review_candidate" if review_candidate else "research_claim",
        "source_quality": "broker_research_normal",
        "review_required": review_candidate,
        "bullets": bullets,
        "evidence": evidence,
    }


def extract_report_context(text: str, source_name: str, source_date: str, concept: str):
    context = {
        "source_name": source_name,
        "source_date": source_date,
        "concept": concept,
        "supply_chain": {
            "upstream_materials": [],
            "upstream_equipment": [],
            "midstream": [],
            "downstream": [],
            "ecosystem": [],
        },
        "related_concepts": [],
        "evidence": [],
    }
    layer_aliases = {
        "上游": "upstream_materials",
        "原材料": "upstream_materials",
        "材料": "upstream_materials",
        "设备": "upstream_equipment",
        "中游": "midstream",
        "制造": "midstream",
        "下游": "downstream",
        "应用": "downstream",
        "生态": "ecosystem",
    }

    def add_items(layer, raw_items):
        bucket = context["supply_chain"].setdefault(layer, [])
        for item in split_items_for_context(raw_items):
            if item not in bucket:
                bucket.append(item)

    for line in text.splitlines():
        cells = [c.strip() for c in re.split(r"\t+|\s{2,}", line.strip()) if c.strip()]
        if len(cells) < 2:
            continue
        layer = ""
        for key, value in layer_aliases.items():
            if key in cells[0]:
                layer = value
                break
        if not layer:
            continue
        add_items(layer, cells[1])
        context["evidence"].append({"heading": cells[0], "text": clean_segment(line)[:240]})

    for heading, block in iter_blocks(text):
        if not any(k in heading for k in CHAIN_HEADINGS):
            continue
        compact = clean_segment(block)
        if len(compact) < 15:
            continue
        sample = compact[:240]
        context["evidence"].append({"heading": heading, "text": sample})
        for token in split_items_for_context(compact):
            if any(token in values for values in context["supply_chain"].values()):
                continue
            layer = infer_context_term_layer(token) or infer_chain_layer("", heading, token)
            if any(k in token for k in ("概念", "技术", "替代", "国产", "双碳", "AI", "数据中心", "新能源")):
                if token not in context["related_concepts"]:
                    context["related_concepts"].append(token)
            bucket = context["supply_chain"].setdefault(layer, [])
            if token not in bucket and not re.search(r"^\d", token):
                bucket.append(token)
    for key, values in context["supply_chain"].items():
        context["supply_chain"][key] = values[:30]
    context["related_concepts"] = context["related_concepts"][:40]
    context["evidence"] = context["evidence"][:12]
    return context


def split_items_for_context(text: str):
    known_terms = (
        "高纯石英砂", "高纯度石英材料", "高纯石英材料", "石英材料", "石英毛细管", "大口径毛细管",
        "光纤预制棒", "预制棒", "光纤拉丝", "拉丝设备", "检测设备", "测试设备",
        "连接器", "耦合器", "光模块", "光纤制造", "空芯光纤制造", "光缆制造", "成缆",
        "系统集成", "传输设备", "数据中心互联", "AI数据中心", "金融高频交易",
        "运营商骨干网", "城域网", "量子通信", "高功率激光", "海底光缆", "云厂商",
        "运营商", "金融机构", "数据中心", "低时延网络",
    )
    compact_text = clean_segment(text)
    matched_terms = []
    compact_no_space = re.sub(r"\s+", "", compact_text)
    for term in known_terms:
        if term in compact_text or term in compact_no_space:
            matched_terms.append(term)
    if len(compact_text) > 300 and len(matched_terms) >= 3:
        return matched_terms

    stop = {
        "预计", "其中", "此外", "随着", "根据", "当前", "未来", "主要组成", "价值占比", "技术特点",
        "高技术壁垒", "高集中度", "技术复杂度高", "定制化程度高", "投资规模大", "回报周期长",
        "全球", "中国", "市场", "规模", "同比", "增长", "突破", "预计到", "最新数据",
    }
    noisy_fragments = (
        "的", "是", "达到", "以上", "以下", "采用", "由于", "随着", "根据", "预计", "认为", "显示",
        "包括", "方面", "特征", "优势", "阶段", "环节", "占比", "毛利率", "国产化率",
        "成本", "规模", "市场", "分析", "判断", "预测", "风险", "水平", "能力", "空间",
        "可将", "满足", "提升", "用于", "可实现", "无需", "主要用于", "来自", "无法",
        "需要", "正在", "共同", "处于", "取得", "通过", "产能", "市占率", "纯度",
        "杂质", "含量", "级别", "工艺", "专利费", "包装", "容量",
    )
    keep_suffixes = (
        "材料", "石英", "石英砂", "毛细管", "预制棒", "光棒", "光纤", "光缆", "拉丝",
        "设备", "测试设备", "检测设备", "连接器", "耦合器", "光模块", "芯片", "系统",
        "制造", "封装", "集成", "互联", "通信", "交易", "数据中心", "运营商", "云厂商",
        "金融", "量子通信", "激光", "海底光缆",
    )
    items = []
    for token in re.split(r"[、,，/；;：:\s]+", compact_text):
        token = token.strip("。；;，,、()（）*\"“”")
        token = re.sub(r"\(\d+%?\)", "", token).strip()
        if not (2 <= len(token) <= 18):
            continue
        if token in stop or re.search(r"^\d", token):
            continue
        if any(ch in token for ch in "()（）<>《》"):
            continue
        if any(bad in token for bad in ("呈现出", "从价值", "将从", "迈向", "需求爆发", "能力快速提升", "根据", "预计", "同比", "亿元", "亿美元", "市场", "规模", "占据", "超过", "提升至", "年均", "作为最", "技术正", "产业链呈现", "价值最")):
            continue
        if any(noise in token for noise in noisy_fragments):
            continue
        if re.fullmatch(r"[A-Za-z]{2,}", token) and token not in {"AI", "GPU", "ASIC", "FPGA", "IDC", "CPO", "PCB", "HBM"}:
            continue
        if token not in items:
            items.append(token)
    return items


def extract_report(path: Path, entities, vault: Path, min_score: int, max_updates: int):
    text = path.read_text(encoding="utf-8", errors="ignore")
    source_name = safe_source_name(path)
    source_date = report_date(text)
    concept = infer_concept(source_name)
    best = {}
    entity_by_name = {entity["name"]: entity for entity in entities}

    for update in extract_markdown_tables(text, entity_by_name, source_name, source_date, concept):
        best.setdefault(update["company"], {
            "score": 999,
            "update": update,
            "entity": entity_by_name[update["company"]],
        })

    for heading, block in iter_blocks(text):
        compact = clean_segment(block)
        if len(compact) < 25:
            continue
        for entity in entities:
            if not any(name in compact for name in entity["names"]):
                continue
            company = entity["name"]
            if not entity.get("code"):
                continue
            if not is_company_subject(compact, company, entity["names"]):
                continue
            if already_has_source(entity["path"], source_name):
                continue
            score = score_block(compact, company)
            if score < min_score:
                continue
            old = best.get(company)
            if old is None or score > old["score"]:
                best[company] = {
                    "score": score,
                    "heading": heading,
                    "block": compact,
                    "entity": entity,
                }

    ranked = sorted(best.items(), key=lambda item: item[1]["score"], reverse=True)[:max_updates]
    updates = []
    for company, item in ranked:
        if "update" in item:
            updates.append(item["update"])
            continue
        update = build_update(
            company,
            item["entity"]["code"],
            source_date,
            source_name,
            concept,
            item["heading"],
            item["block"],
        )
        if update:
            updates.append(update)

    return {
        "source_name": source_name,
        "source_date": source_date,
        "source_file": str(path),
        "raw_sources": [f"raw/{path.name}"],
        "report_context": extract_report_context(text, source_name, source_date, concept),
        "create_missing": False,
        "updates": updates,
        "watchlist": [],
    }


def extract_markdown_tables(text: str, entity_by_name, source_name: str, source_date: str, concept: str):
    updates = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        if "---" in stripped or "股票" in stripped or "代码" in stripped:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        company = normalize_company(cells[0])
        code = re.sub(r"\D", "", cells[1])
        logic = clean_segment(" ".join(cells[2:]))
        if company not in entity_by_name or len(code) != 6 or len(logic) < 18:
            continue
        entity = entity_by_name[company]
        if already_has_source(entity["path"], source_name):
            continue
        role = infer_role("", logic)
        chain_layer = infer_chain_layer(role, "", logic)
        tier = infer_tier(logic, role, chain_layer)
        is_curated = has_review_candidate_fact(logic)
        exposure_only = True
        graph_only = exposure_only
        update_type = "review_candidate" if is_curated else "graph_only"
        title = f"{concept}核心个股表回填"
        if any(k in logic for k in ("增长", "同比", "营收", "净利润", "销量")):
            title = f"{concept}相关业务与数据回填"
        updates.append({
            "company": company,
            "code": code or entity["code"],
            "date": source_date,
            "title": title,
            "judgment": "研究报告核心个股表提及，需后续公告/财报交叉验证",
            "concepts": [concept],
            "role": role,
            "chain_layer": chain_layer,
            "tier": tier,
            "confidence": "medium",
            "evidence_layer": evidence_layer_for(logic, exposure_only),
            "exposure_only": exposure_only,
            "graph_only": graph_only,
            "update_type": update_type,
            "fact_hardness": "review_candidate" if is_curated else "research_claim",
            "source_quality": "broker_research_normal",
            "review_required": is_curated,
            "bullets": [logic[:180].rstrip() + ("..." if len(logic) > 180 else "")],
            "evidence": logic[:180].rstrip() + ("..." if len(logic) > 180 else ""),
        })
    return updates


def write_payload(payload, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[/:*?"<>|\n\r\t]+', "_", payload["source_name"]).strip()
    path = out_dir / f"{safe}.entity-delta.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run_writer(payload_path: Path):
    with payload_path.open("rb") as fh:
        proc = subprocess.run(
            [sys.executable, str(WRITER)],
            stdin=fh,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    return proc


def merge_report_context(payload):
    context = payload.get("report_context")
    if not context:
        return None
    RELATIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = RELATIONS_DIR / "report_contexts.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {"version": 1, "reports": {}}
    else:
        data = {"version": 1, "reports": {}}
    data.setdefault("reports", {})[payload["source_name"]] = context
    data["updated"] = date.today().isoformat()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return str(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_VAULT / "raw/entity-delta-backfill")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-score", type=int, default=9)
    parser.add_argument("--max-updates-per-report", type=int, default=18)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write-context", action="store_true")
    parser.add_argument("--start-after", default="")
    args = parser.parse_args()

    entities = load_entities(args.vault)
    files = sorted(args.raw_dir.glob("*-full.md"))
    if args.start_after:
        files = [p for p in files if p.name > args.start_after]
    if args.limit:
        files = files[: args.limit]

    summary = {
        "reports_seen": len(files),
        "payloads": 0,
        "updates": 0,
        "written": 0,
        "errors": [],
        "payload_files": [],
    }
    for path in files:
        payload = extract_report(path, entities, args.vault, args.min_score, args.max_updates_per_report)
        if not payload:
            continue
        payload_path = write_payload(payload, args.out_dir)
        context_path = merge_report_context(payload) if (args.write_context or args.apply) else None
        summary["payloads"] += 1
        summary["updates"] += len(payload["updates"])
        summary["payload_files"].append(str(payload_path))
        if context_path:
            summary.setdefault("context_files", [])
            if context_path not in summary["context_files"]:
                summary["context_files"].append(context_path)
        if args.apply:
            proc = run_writer(payload_path)
            if proc.returncode == 0:
                summary["written"] += len(payload["updates"])
            else:
                summary["errors"].append({
                    "payload": str(payload_path),
                    "returncode": proc.returncode,
                    "stderr": proc.stderr.decode("utf-8", errors="ignore")[-2000:],
                })

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

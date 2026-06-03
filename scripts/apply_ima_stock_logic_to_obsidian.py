#!/usr/bin/env python3
"""Apply an IMA stock logic markdown card into the Obsidian wiki.

Default mode is dry-run. Use --apply to write files.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_VAULT = Path(os.environ.get("KNOWLEDGE_VAULT", "/Users/lbq/Desktop/c c/知识库"))


def now_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def run_git(args: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(cwd), text=True).strip()
    except Exception:
        return ""


def split_frontmatter(text: str) -> tuple[dict[str, Any], str, bool]:
    if not text.startswith("---"):
        return {}, text, False
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}, text, False
    fm_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).lstrip("\n")
    return parse_simple_yaml(fm_text), body, True


def parse_simple_yaml(fm_text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key = ""
    for raw in fm_text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("- ") and current_key:
            result.setdefault(current_key, [])
            if isinstance(result[current_key], list):
                result[current_key].append(clean_scalar(line.lstrip()[2:].strip()))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        if value == "":
            result[key] = []
        else:
            result[key] = parse_scalar_or_array(value)
    return result


def parse_scalar_or_array(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        try:
            return ast.literal_eval(value)
        except Exception:
            return [clean_scalar(v.strip()) for v in value.strip("[]").split(",") if v.strip()]
    return clean_scalar(value)


def clean_scalar(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def dump_simple_yaml(data: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            elif all(is_simple_scalar(v) for v in value) and len("".join(map(str, value))) < 220:
                lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {quote_yaml_scalar(str(item))}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif value is None:
            lines.append(f"{key}:")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {quote_yaml_scalar(str(value))}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def is_simple_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def quote_yaml_scalar(value: str) -> str:
    if value == "":
        return '""'
    if any(ch in value for ch in [":", "#", "[", "]", "{", "}"]) or value.startswith("[") or value.startswith("#"):
        return json.dumps(value, ensure_ascii=False)
    return value


def section_map(body: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", body, flags=re.M))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[title] = body[start:end].strip()
    return sections


def first_h1(body: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*$", body, flags=re.M)
    return m.group(1).strip() if m else ""


def normalize_entity_name(meta: dict[str, Any], body: str) -> str:
    h1 = first_h1(body)
    if h1:
        name = re.split(r"[｜|]", h1, maxsplit=1)[0].strip()
        name = re.sub(r"[（(].*?[）)]", "", name).strip()
        name = re.sub(r"\s+(?:SZ|SH|BJ|sz|sh|bj)?\d{6}$", "", name).strip()
        name = re.sub(r"(个股)?最新逻辑(跟踪|卡)?$", "", name).strip()
        name = re.sub(r"个股逻辑卡$", "", name).strip()
        if name:
            return name
    company = str(meta.get("company") or meta.get("entity") or "").strip()
    company = re.sub(r"[（(].*?[）)]", "", company).strip()
    company = re.sub(r"股份有限公司$|有限公司$|公司$", "", company).strip()
    return company


def normalize_ticker(ticker: Any) -> str:
    if isinstance(ticker, list):
        values = [normalize_ticker(item) for item in ticker]
        for value in values:
            if re.fullmatch(r"\d{6}", value) and value[0] in {"0", "3", "6", "8", "9"}:
                return value
        return values[0] if values else ""
    ticker = str(ticker or "").strip().strip('"')
    tokens = re.findall(r"(?:SZ|SH|BJ)?\d{6}(?:\.(?:SZ|SH|BJ|HK|US|NASDAQ|NYSE))?", ticker, flags=re.I)
    if tokens:
        values = [normalize_ticker_token(token) for token in tokens]
        for value in values:
            if re.fullmatch(r"\d{6}", value) and value[0] in {"0", "3", "6", "8", "9"}:
                return value
        if len(values) > 1:
            return values[0] if values else ""
    return normalize_ticker_token(ticker)


def normalize_ticker_token(ticker: str) -> str:
    ticker = str(ticker or "").strip().strip('"')
    ticker = re.sub(r"\.(SZ|SH|BJ|HK|US|NASDAQ|NYSE)$", "", ticker, flags=re.I)
    return re.sub(r"^(SZ|SH|BJ)", "", ticker, flags=re.I)


def normalize_source_name(stem: str) -> str:
    return re.sub(r"\s+\(\d+\)$", "", stem).strip()


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = re.split(r"[、,，/；;]", value)
        return [p.strip() for p in parts if p.strip()]
    return [str(value).strip()]


def wikilink(name: str) -> str:
    return f"[[{name}]]"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def existing_concepts(vault: Path) -> set[str]:
    names = {p.stem for p in (vault / "wiki" / "concepts").glob("*.md")}
    graph = load_json(vault / "wiki" / "relations" / "concept_graph.json", {"concepts": {}})
    if isinstance(graph, dict) and isinstance(graph.get("concepts"), dict):
        names.update(graph["concepts"].keys())
    return names


def concept_candidates(meta: dict[str, Any], body: str, concepts: set[str]) -> list[str]:
    generic_concepts = {"全球化", "基建", "通胀", "产业化", "新材料", "出海", "精密制造", "智能汽车", "通信服务", "液冷", "机器人", "一带一路", "能源转型", "传统能源", "出口管制", "出口", "电商", "国企改革", "央企改革", "新能源消纳", "工程", "系统集成", "公用事业", "检测设备", "北交所", "全产业链", "清洁能源", "高端制造", "智能制造", "智能化", "环保", "软件", "IT服务", "应用软件", "新基建", "电力设备", "家电", "大数据", "薄膜", "消费", "影视", "食品饮料", "医药生物", "医药", "国防军工", "通信设备", "国产替代", "自动化设备", "安防", "军工", "5G", "光学系统", "深海", "新能源储能", "OCS光交换", "OCS", "光器件", "光缆", "连接器", "服务器", "交换机", "算力服务", "数据中心", "高纯金属", "膜材料", "稀土", "LCD", "LED", "物联网", "自主可控", "战略金属", "小金属", "贵金属", "铅锌", "有色金属", "建材", "CIS", "化工", "半导体", "信息化", "医疗"}
    raw: list[str] = []
    raw.extend(as_list(meta.get("themes")))
    raw.extend(as_list(meta.get("related_business")))
    raw.extend(as_list(meta.get("industry")))
    raw.extend(as_list(meta.get("sector")))
    raw.extend(as_list(meta.get("tags")))
    text = "\n".join(raw + [first_h1(body)])
    if not raw:
        text = "\n".join([first_h1(body), body[:5000]])
    candidates: list[str] = []
    for name in sorted(concepts, key=lambda item: (-len(item), item)):
        if len(name) < 2:
            continue
        if name in generic_concepts:
            continue
        aliases = {name}
        if " " in name:
            aliases.add(name.replace(" ", "-"))
            aliases.add(name.replace(" ", ""))
        if any(alias in text for alias in aliases) and name not in candidates:
            candidates.append(name)
    entity_name = normalize_entity_name(meta, body)
    if entity_name in candidates:
        candidates.remove(entity_name)
    for item in raw:
        cleaned = re.sub(r"[（(].*?[）)]", "", item).strip()
        if cleaned in concepts and cleaned not in generic_concepts and cleaned not in candidates:
            candidates.append(cleaned)
    if "AI算力" in candidates and "算力" in candidates:
        candidates.remove("算力")
    if "算力基建" in candidates and "算力" in candidates:
        candidates.remove("算力")
    if "AI算力基础设施" in candidates and "算力基础设施" in candidates:
        candidates.remove("算力基础设施")
    if "AI算力基础设施" in candidates and "AI算力" in candidates:
        candidates.remove("AI算力")
    if "AI PCB" in candidates and "AI PC" in candidates:
        candidates.remove("AI PC")
    if "AI PCB" in candidates and "PCB" in candidates:
        candidates.remove("PCB")
    if "PCB铜箔" in candidates and "PCB" in candidates:
        candidates.remove("PCB")
    if "消费电子" in candidates and "新消费" in candidates:
        candidates.remove("新消费")
    if "消费电子" in candidates and "消费" in candidates:
        candidates.remove("消费")
    if "Mini LED" in candidates and "LED" in candidates:
        candidates.remove("LED")
    if "储能消防" in candidates and "储能" in candidates:
        candidates.remove("储能")
    if "高股息红利" in candidates and "高股息" in candidates:
        candidates.remove("高股息")
    if "高股息红利" in candidates and "红利资产" in candidates:
        candidates.remove("红利资产")
    if "工程机械" in candidates and "工程" in candidates:
        candidates.remove("工程")
    if "汽车轻量化" in candidates and "轻量化" in candidates:
        candidates.remove("轻量化")
    if "折叠屏手机" in candidates and "折叠屏" in candidates:
        candidates.remove("折叠屏")
    if "高速铜缆" in candidates and "铜缆" in candidates:
        candidates.remove("铜缆")
    if "高速铜缆" in candidates and "线缆" in candidates:
        candidates.remove("线缆")
    if "高速铜连接" in candidates and "铜连接" in candidates:
        candidates.remove("铜连接")
    if "AI服务器" in candidates and "服务器" in candidates:
        candidates.remove("服务器")
    if "AI服务器电源" in candidates and "AI服务器" in candidates:
        candidates.remove("AI服务器")
    if "AI视频生成" in candidates and "AIGC" in candidates:
        candidates.remove("AIGC")
    if "AI视频生成" in candidates and "AI应用" in candidates:
        candidates.remove("AI应用")
    if "3D打印" in candidates and "增材制造" in candidates:
        candidates.remove("增材制造")
    if "OCS光交换" in candidates and "OCS" in candidates:
        candidates.remove("OCS")
    if "先进封装" in candidates and "半导体" in candidates:
        candidates.remove("半导体")
    if ("先进封装" in candidates or "封测" in candidates) and "集成电路" in candidates:
        candidates.remove("集成电路")
    if "玻璃基板" in candidates and "半导体" in candidates:
        candidates.remove("半导体")
    if "半导体材料" in candidates and "半导体" in candidates:
        candidates.remove("半导体")
    if "半导体封装" in candidates and "半导体" in candidates:
        candidates.remove("半导体")
    if "电子特气" in candidates and "电子化学品" in candidates:
        candidates.remove("电子化学品")
    if "煤炭" in candidates and "化工" in candidates:
        candidates.remove("化工")
    if "氟化工" in candidates and "化工" in candidates:
        candidates.remove("化工")
    if "三代制冷剂" in candidates and "制冷剂" in candidates:
        candidates.remove("制冷剂")
    if "数据库" in candidates and "基础软件" in candidates:
        candidates.remove("基础软件")
    if "金融信创" in candidates and "信创" in candidates:
        candidates.remove("信创")
    if "半导体国产替代" in candidates and "国产替代" in candidates:
        candidates.remove("国产替代")
    if "核电" in candidates and "核能" in candidates:
        candidates.remove("核能")
    if "可控核聚变" in candidates and "核聚变" in candidates:
        candidates.remove("核聚变")
    if "军工信息化" in candidates and "军工电子" in candidates:
        candidates.remove("军工电子")
    if "汽车电子" in candidates and "BMS" in candidates:
        candidates.remove("BMS")
    if "MEMS传感器" in candidates and "传感器" in candidates:
        candidates.remove("传感器")
    if "辅助生殖" in candidates and "医疗服务" in candidates:
        candidates.remove("医疗服务")
    if ("储能电池" in candidates or "长时储能" in candidates) and "储能" in candidates:
        candidates.remove("储能")
    if "AI算力" in candidates and "服务器" in candidates:
        candidates.remove("服务器")
    if ("CPO" in candidates or "光模块" in candidates) and "AI算力" in candidates:
        candidates.remove("AI算力")
    if ("CPO" in candidates or "光模块" in candidates) and "光通信" in candidates:
        candidates.remove("光通信")
    if ("光通信" in candidates or "光芯片" in candidates or "光纤光缆" in candidates or "空芯光纤" in candidates) and "AI算力" in candidates:
        candidates.remove("AI算力")
    if "MPO光纤连接器" in candidates and "连接器" in candidates:
        candidates.remove("连接器")
    if "算电协同" in candidates and "算力" in candidates:
        candidates.remove("算力")
    if ("AI服务器" in candidates or "智算中心" in candidates or "算力服务" in candidates) and "算力" in candidates:
        candidates.remove("算力")
    if ("风电" in candidates or "光伏" in candidates) and "新能源" in candidates:
        candidates.remove("新能源")
    if ("风电" in candidates or "光伏" in candidates) and "绿电" in candidates:
        candidates.remove("绿电")
    if "光伏组件" in candidates and "光伏" in candidates:
        candidates.remove("光伏")
    if "新能源汽车" in candidates and "新能源" in candidates:
        candidates.remove("新能源")
    if "新能源材料" in candidates and "新能源" in candidates:
        candidates.remove("新能源")
    if "人形机器人" in candidates and "机器人" in candidates:
        candidates.remove("机器人")
    if "SOFC燃料电池" in candidates and "燃料电池" in candidates:
        candidates.remove("燃料电池")
    if "MCU芯片" in candidates and "MCU" in candidates:
        candidates.remove("MCU")
    if "工业供能" in text and "锂矿" in candidates:
        candidates.remove("锂矿")
    if "航空轮胎" in text and "轮胎" in candidates:
        candidates.remove("轮胎")
    if "涡轮增压器" in text and "工程机械" in candidates:
        candidates.remove("工程机械")
    if "算力金属" in text and "算力" in candidates:
        candidates.remove("算力")
    if "华为云" in body and "私有云" in body and "华为生态" in candidates:
        candidates.remove("华为生态")
    if "反无人机" in body and "低空经济" in candidates and "无人机" in candidates:
        candidates.remove("无人机")
    if "红外热像仪" in body and "光学系统" in body and "传感器" in candidates:
        candidates.remove("传感器")
    if "纯核电" in text:
        for concept in ["非银金融", "热电联产", "光伏", "风电"]:
            if concept in candidates:
                candidates.remove(concept)
    if "黄金珠宝批发" in text and "海外油气资产注入" in text and "黄金" in candidates:
        candidates.remove("黄金")
    if ("商业航天（争议" in text or "商业航天逻辑已被监管证伪" in text) and "商业航天" in candidates:
        candidates.remove("商业航天")
    if "房地产（持续收缩" in text and "房地产" in candidates:
        candidates.remove("房地产")
    if "收费公路" in text and "清洁能源（海上风电、光伏" in text:
        for concept in ["海上风电", "光伏"]:
            if concept in candidates:
                candidates.remove(concept)
    if ("风电" in text or "风光" in text) and "风电" in concepts and "风电" not in candidates:
        candidates.append("风电")
    if ("光伏" in text or "风光" in text) and "光伏" in concepts and "光伏" not in candidates:
        candidates.append("光伏")
    if "火电" in text and "火电" in concepts and "火电" not in candidates:
        candidates.append("火电")
    if "煤炭" in text and "煤炭" in concepts and "煤炭" not in candidates:
        candidates.append("煤炭")
    if any(token in text for token in ["铜矿", "铜价", "铜精矿", "铜当量"]) and "铜" in concepts and "铜" not in candidates:
        candidates.append("铜")
    if "港口" in text and "港口航运" in concepts and "港口航运" not in candidates:
        candidates.append("港口航运")
    if "智能体" in body and "AI智能体" in concepts and "AI智能体" not in candidates:
        candidates.append("AI智能体")
    if "Token经济" in body and "Token经济" in concepts and "Token经济" not in candidates:
        candidates.append("Token经济")
    if "MPO" in body and "MPO光纤连接器" in concepts and "MPO光纤连接器" not in candidates:
        candidates.append("MPO光纤连接器")
    if "国产算力" in body and "AI基础设施与国产算力" in concepts and "AI基础设施与国产算力" not in candidates:
        candidates.append("AI基础设施与国产算力")
    if "光纤光缆" in body and "光纤光缆" in concepts and "光纤光缆" not in candidates:
        candidates.append("光纤光缆")
    if "光通信收入" in body and "光通信" in concepts and "光通信" not in candidates:
        candidates.append("光通信")
    if "AI基础设施与国产算力" in candidates and "算力" in candidates:
        candidates.remove("算力")
    if "AI基础设施与国产算力" in candidates and "AI算力" in candidates:
        candidates.remove("AI算力")
    if "AI基础设施与国产算力" in candidates and "算力基础设施" in candidates:
        candidates.remove("算力基础设施")
    if ("高速铜连接" in candidates or "高速铜缆" in candidates or "铜缆互联" in candidates) and "AI算力" in candidates:
        candidates.remove("AI算力")
    if ("AI算力材料" in text or "半导体靶材" in body) and "AI算力" in candidates:
        candidates.remove("AI算力")
    if "新能源（风电/光伏/储能工程）" in body and "光纤光缆" in candidates and "新能源" in candidates:
        candidates.remove("新能源")
    if "2-3年内难贡献业绩" in body:
        for concept in ["AI算力", "钙钛矿"]:
            if concept in candidates:
                candidates.remove(concept)
    if "光伏级锗晶片" in body and "光伏" in candidates:
        candidates.remove("光伏")
    if ("卫星互联网" in candidates or "商业航天" in candidates) and "卫星" in candidates:
        candidates.remove("卫星")
    if ("风电" in candidates or "光伏" in candidates) and "新能源" in candidates:
        candidates.remove("新能源")
    if "储能" in candidates and "新能源" in candidates:
        candidates.remove("新能源")
    if ("风电" in candidates or "光伏" in candidates) and "绿电" in candidates:
        candidates.remove("绿电")
    if "光伏组件" in candidates and "光伏" in candidates:
        candidates.remove("光伏")
    if "海上风电" in candidates and "风电" in candidates:
        candidates.remove("风电")
    if "港口航运" in candidates and "航运" in candidates:
        candidates.remove("航运")
    if "收费公路" in text and "清洁能源（海上风电、光伏" in text:
        for concept in ["海上风电", "风电", "光伏"]:
            if concept in candidates:
                candidates.remove(concept)
    if "纯核电" in body:
        for concept in ["非银金融", "热电联产", "光伏", "风电"]:
            if concept in candidates:
                candidates.remove(concept)
    if "黄金珠宝批发" in body and "海外油气资产注入" in body and "黄金" in candidates:
        candidates.remove("黄金")
    if "卫星通信" in candidates and "卫星" in candidates:
        candidates.remove("卫星")
    if ("军工信息化" in candidates or "军工电子" in candidates) and "军工" in candidates:
        candidates.remove("军工")
    if "环保物联网" in body and "物联网" in candidates:
        candidates.remove("物联网")
    if ("钙钛矿光伏" in candidates or "光伏设备" in candidates) and "光伏" in candidates:
        candidates.remove("光伏")
    if "钙钛矿光伏" in candidates and "钙钛矿" in candidates:
        candidates.remove("钙钛矿")
    return candidates[:8]


def extract_one_liner(sections: dict[str, str]) -> str:
    text = get_section(sections, "一句话结论")
    text = re.sub(r"^[-–—]+$", "", text, flags=re.M).strip()
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("---"):
            return compact(line, 260)
    return ""


def compact(text: str, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def get_section(sections: dict[str, str], title: str) -> str:
    if title in sections:
        return sections[title]
    for section_title, section_text in sections.items():
        normalized_title = normalize_section_title(section_title)
        if normalized_title.startswith(title) or title in normalized_title:
            return section_text
    return ""


def normalize_section_title(title: str) -> str:
    return re.sub(r"^\d+[\.、]\s*", "", title).strip()


def demote_markdown_headings(text: str, levels: int = 2) -> str:
    result = []
    for line in text.splitlines():
        m = re.match(r"^(#{1,5})(\s+.+)$", line)
        if m:
            result.append("#" * min(6, len(m.group(1)) + levels) + m.group(2))
        else:
            result.append(line)
    return "\n".join(result)


def take_section(sections: dict[str, str], title: str, max_lines: int) -> str:
    text = get_section(sections, title).strip()
    if not text:
        return "- 待补"
    lines = [ln.rstrip() for ln in text.splitlines()]
    kept: list[str] = []
    for line in lines:
        if line.strip() == "---":
            continue
        kept.append(line)
        if len([x for x in kept if x.strip()]) >= max_lines:
            break
    return demote_markdown_headings("\n".join(kept).strip()) or "- 待补"


def build_entity_increment(meta: dict[str, Any], body: str, source_name: str) -> str:
    sections = section_map(body)
    updated = str(meta.get("updated") or now_date())
    one = extract_one_liner(sections)
    if not one:
        one = compact(get_section(sections, "核心结论"), 260)
    logic = take_section(sections, "最新市场逻辑", 60)
    if logic == "- 待补":
        logic = take_section(sections, "当前市场在交易什么逻辑", 60)
    if logic == "- 待补":
        logic = take_section(sections, "核心投资逻辑", 60)
    hard_delta = take_section(sections, "Hard Delta", 20)
    if hard_delta == "- 待补":
        hard_delta = take_section(sections, "最新业绩摘要", 20)
    risks = take_section(sections, "反证与风险", 14)
    if risks == "- 待补":
        risks = take_section(sections, "反证信号", 14)
    if risks == "- 待补":
        risks = take_section(sections, "风险提示", 14)
    tracking = take_section(sections, "后续跟踪指标", 16)
    if tracking == "- 待补":
        tracking = take_section(sections, "关键跟踪指标", 16)
    confidence = meta.get("ima_confidence") or meta.get("evidence_strength") or "IMA综合可信"
    stage = meta.get("logic_stage") or meta.get("evidence_level") or "待观察"
    financial = meta.get("financial_validation") or "见财务映射"
    related = "、".join(as_list(meta.get("related_business"))[:6]) or str(meta.get("sector") or meta.get("industry") or "见原文")
    return f"""### {updated}｜[[{source_name}]]

- **一句话**：{one or '见原文'}
- **IMA可信度**：{confidence}
- **逻辑阶段**：{stage}
- **财务验证**：{financial}
- **相关业务**：{related}

#### 核心逻辑

{logic}

#### Hard Delta

{hard_delta}

#### 反证与风险

{risks}

#### 后续跟踪

{tracking}
""".rstrip() + "\n"


def ensure_section_append(body: str, section_title: str, increment: str, source_name: str, force: bool = False) -> tuple[str, bool]:
    if source_name in body and not force:
        return body, False
    if source_name in body and force:
        replaced, changed = replace_source_increment(body, source_name, increment)
        if changed:
            return replaced, True
    heading = f"## {section_title}"
    if heading not in body:
        body = body.rstrip() + f"\n\n{heading}\n\n{increment}\n"
        return body, True
    pattern = re.compile(rf"^##\s+{re.escape(section_title)}\s*$", flags=re.M)
    m = pattern.search(body)
    if not m:
        return body.rstrip() + f"\n\n{heading}\n\n{increment}\n", True
    insert_at = len(body)
    next_m = re.search(r"^##\s+", body[m.end():], flags=re.M)
    if next_m:
        insert_at = m.end() + next_m.start()
    new_body = body[:insert_at].rstrip() + "\n\n" + increment + "\n" + body[insert_at:].lstrip("\n")
    return new_body, True


def replace_source_increment(body: str, source_name: str, increment: str) -> tuple[str, bool]:
    pattern = re.compile(rf"^###\s+\d{{4}}-\d{{2}}-\d{{2}}｜\[\[{re.escape(source_name)}\]\]\s*$", flags=re.M)
    m = pattern.search(body)
    if not m:
        return body, False
    tail = body[m.end():]
    next_date = re.search(r"^###\s+\d{4}-\d{2}-\d{2}｜", tail, flags=re.M)
    next_section = re.search(r"^##\s+", tail, flags=re.M)
    candidates = [x.start() for x in [next_date, next_section] if x]
    end = m.end() + min(candidates) if candidates else len(body)
    new_body = body[:m.start()].rstrip() + "\n\n" + increment + "\n" + body[end:].lstrip("\n")
    return new_body, True


def upsert_frontmatter_list(meta: dict[str, Any], key: str, values: list[str]) -> None:
    existing = as_list(meta.get(key))
    for value in values:
        if value and value not in existing:
            existing.append(value)
    meta[key] = existing


def update_entity_page(entity_path: Path, entity_name: str, ticker: str, source_name: str, increment: str, log_id: str, apply: bool, force: bool) -> dict[str, Any]:
    created = False
    if entity_path.exists():
        old = entity_path.read_text(encoding="utf-8")
        meta, body, has_fm = split_frontmatter(old)
    else:
        created = True
        meta = {
            "title": entity_name,
            "tags": [entity_name, "个股研究", "上市公司"],
            "tickers": [ticker] if ticker else [],
            "created": now_date(),
            "updated": now_date(),
            "revision": 0,
            "sources": [],
            "log": [],
            "markets": [],
        }
        body = f"# {entity_name}\n"
        has_fm = True
    new_body, changed = ensure_section_append(body, "IMA 最新逻辑跟踪", increment, source_name, force=force)
    if not changed:
        return {"created": created, "changed": False, "path": str(entity_path), "reason": "source already present"}
    meta.setdefault("title", entity_name)
    meta["updated"] = now_date()
    try:
        meta["revision"] = int(meta.get("revision") or 0) + 1
    except Exception:
        meta["revision"] = 1
    upsert_frontmatter_list(meta, "sources", [wikilink(source_name)])
    upsert_frontmatter_list(meta, "log", [f"{log_id} added IMA stock logic from [[{source_name}]]"])
    if ticker:
        upsert_frontmatter_list(meta, "tickers", [ticker])
    new_text = dump_simple_yaml(meta) + "\n" + new_body.rstrip() + "\n"
    if apply:
        entity_path.parent.mkdir(parents=True, exist_ok=True)
        entity_path.write_text(new_text, encoding="utf-8")
    return {"created": created, "changed": True, "path": str(entity_path), "revision": meta.get("revision")}


def build_source_page(input_text: str, source_name: str, meta: dict[str, Any], log_id: str) -> str:
    original_meta, body, _ = split_frontmatter(input_text)
    source_meta = dict(original_meta)
    source_meta.setdefault("type", "stock_research")
    source_meta["title"] = source_name
    source_meta["created"] = source_meta.get("created") or now_date()
    source_meta["updated"] = now_date()
    source_meta["revision"] = int(source_meta.get("revision") or 0) + 1 if str(source_meta.get("revision") or "").isdigit() else 1
    upsert_frontmatter_list(source_meta, "tags", ["个股研究", "IMA", "个股逻辑"])
    upsert_frontmatter_list(source_meta, "log", [f"{log_id} archived IMA stock logic"])
    return dump_simple_yaml(source_meta) + "\n" + body.rstrip() + "\n"


def confidence_from_meta(meta: dict[str, Any]) -> str:
    value = str(meta.get("ima_confidence") or meta.get("evidence_strength") or "").strip()
    if "高风险" in value:
        return "low"
    if "待确认" in value or value in {"中", "中等"}:
        return "medium"
    if value in {"强", "高"} or "综合可信" in value:
        return "high"
    return "medium"


def evidence_layer_from_meta(meta: dict[str, Any]) -> str:
    stage = str(meta.get("logic_stage") or meta.get("evidence_level") or "").strip()
    if "财务兑现" in stage or stage == "L3":
        return "L1_L3_candidate"
    if "事实验证" in stage:
        return "L1_L3_candidate"
    if "能力" in stage or stage == "L2":
        return "L2"
    return "L1"


def update_relations(vault: Path, entity_name: str, ticker: str, meta: dict[str, Any], body: str, source_name: str, concepts: list[str], apply: bool, backup: bool) -> dict[str, Any]:
    rel_dir = vault / "wiki" / "relations"
    exposures_path = rel_dir / "entity_exposures.json"
    evidence_path = rel_dir / "evidence_index.json"
    exposures = load_json(exposures_path, {"entities": {}})
    evidence = load_json(evidence_path, {"items": []})
    if backup and apply:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        shutil.copy2(exposures_path, exposures_path.with_suffix(f".json.{stamp}.bak"))
        shutil.copy2(evidence_path, evidence_path.with_suffix(f".json.{stamp}.bak"))
    entity = exposures.setdefault("entities", {}).setdefault(entity_name, {"codes": [], "name": entity_name, "concepts": {}, "exposures": []})
    if ticker and ticker not in entity.setdefault("codes", []):
        entity["codes"].append(ticker)
    entity.setdefault("name", entity_name)
    entity.setdefault("concepts", {})
    confidence = confidence_from_meta(meta)
    evidence_layer = evidence_layer_from_meta(meta)
    source_link = wikilink(source_name)
    one = extract_one_liner(section_map(body)) or f"IMA个股逻辑卡：{entity_name} 最新逻辑跟踪"
    role = "、".join(as_list(meta.get("related_business"))[:4]) or str(meta.get("sector") or meta.get("industry") or "")
    inserted_concepts = []
    updated_concepts = []
    for concept in concepts:
        new_fields = {
            "chain_layer": str(meta.get("industry") or meta.get("sector") or ""),
            "confidence": confidence,
            "evidence": compact(one, 220),
            "evidence_layer": evidence_layer,
            "role": role,
            "sources": [source_link],
            "strength": "core" if concept in as_list(meta.get("themes")) or concept in role else "related",
            "update_type": "ima_stock_logic",
            "updated": now_date(),
            "fact_hardness": "ima_composite",
            "review_required": False,
            "source_quality": "ima_composite",
            "ima_confidence": meta.get("ima_confidence") or meta.get("evidence_strength") or "IMA综合可信",
            "logic_stage": meta.get("logic_stage") or "",
            "financial_validation": meta.get("financial_validation") or "",
        }
        existing = entity["concepts"].get(concept)
        if existing:
            sources = list(existing.get("sources", [])) if isinstance(existing.get("sources"), list) else []
            if source_link not in sources:
                sources.append(source_link)
            existing["sources"] = sources
            existing["updated"] = now_date()
            for key in ["ima_confidence", "logic_stage", "financial_validation"]:
                if new_fields.get(key):
                    existing[key] = new_fields[key]
            if not existing.get("role") and new_fields.get("role"):
                existing["role"] = new_fields["role"]
            if not existing.get("evidence"):
                existing["evidence"] = new_fields["evidence"]
            updated_concepts.append(concept)
        else:
            entity["concepts"][concept] = new_fields
            inserted_concepts.append(concept)
    items = evidence.setdefault("items", [])
    existing_keys = {evidence_key(item) for item in items if isinstance(item, dict)}
    inserted_evidence = []
    for concept in concepts:
        item = {
            "source": source_link,
            "source_date": str(meta.get("updated") or now_date()),
            "target_type": "entity",
            "target": entity_name,
            "concept": concept,
            "evidence": compact(one, 260),
            "confidence": confidence,
            "chain_layer": str(meta.get("industry") or meta.get("sector") or ""),
            "evidence_layer": evidence_layer,
            "update_type": "ima_stock_logic",
            "fact_hardness": "ima_composite",
            "source_quality": "ima_composite",
            "review_required": False,
        }
        key = evidence_key(item)
        if key not in existing_keys:
            items.append(item)
            existing_keys.add(key)
            inserted_evidence.append(key)
    if apply:
        exposures["updated"] = now_date()
        evidence["updated"] = now_date()
        save_json(exposures_path, exposures)
        save_json(evidence_path, evidence)
    return {
        "concepts": concepts,
        "inserted_concepts": inserted_concepts,
        "updated_concepts": updated_concepts,
        "inserted_evidence": inserted_evidence,
        "exposures_path": str(exposures_path),
        "evidence_path": str(evidence_path),
    }


def evidence_key(item: dict[str, Any]) -> str:
    return "|".join([str(item.get("source", "")), str(item.get("target_type", "")), str(item.get("target", "")), str(item.get("concept", ""))])


def append_log(vault: Path, log_id: str, source_name: str, entity_name: str, source_created: bool, apply: bool) -> str:
    log_path = vault / "wiki" / "log.md"
    text = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Activity Log\n"
    entry = f"""
### {log_id} | {now_time()} | ingest | IMA个股逻辑沉淀：{entity_name}

- **trigger**: user-provided IMA stock logic card
- **source**: [[{source_name}]]
- **created**: {f'[[{source_name}]]' if source_created else '[]'}
- **updated**: [[{entity_name}]], entity_exposures.json, evidence_index.json
- **key**: 将 IMA 个股最新逻辑卡沉淀到 {entity_name} 实体页，保留来源链、IMA可信度、财务兑现阶段、反证风险和后续跟踪指标。
""".rstrip() + "\n"
    if apply:
        log_path.write_text(text.rstrip() + "\n\n" + entry + "\n", encoding="utf-8")
    return entry


def next_log_id(vault: Path) -> str:
    log_path = vault / "wiki" / "log.md"
    if not log_path.exists():
        return "#001"
    nums = [int(m.group(1)) for m in re.finditer(r"^### #(\d+)", log_path.read_text(encoding="utf-8"), flags=re.M)]
    return f"#{(max(nums) if nums else 0) + 1:03d}"


def update_index_counts(vault: Path, log_id: str, apply: bool) -> dict[str, Any]:
    index_path = vault / "wiki" / "index.md"
    if not index_path.exists():
        return {"changed": False, "reason": "index.md missing"}
    text = index_path.read_text(encoding="utf-8")
    page_count = len(list((vault / "wiki").glob("**/*.md")))
    source_count = len(list((vault / "wiki" / "sources").glob("*.md")))
    concept_count = len(list((vault / "wiki" / "concepts").glob("*.md")))
    entity_count = len(list((vault / "wiki" / "entities").glob("*.md")))
    synthesis_count = len(list((vault / "wiki" / "synthesis").glob("*.md")))
    new_line = f"**{page_count} 页 | {source_count} 个来源 | {concept_count} 个概念 | {entity_count} 个实体 | {synthesis_count} 个综合分析**"
    new_text, n = re.subn(r"\*\*\d+ 页 \| \d+ 个来源 \| \d+ 个概念 \| \d+ 个实体 \| \d+ 个综合分析\*\*", new_line, text, count=1)
    meta, body, has_fm = split_frontmatter(new_text)
    if has_fm:
        meta["updated"] = now_date()
        try:
            meta["revision"] = int(meta.get("revision") or 0) + 1
        except Exception:
            meta["revision"] = 1
        upsert_frontmatter_list(meta, "log", [f"{log_id} IMA stock logic ingest count refresh"])
        new_text = dump_simple_yaml(meta) + "\n" + body.lstrip("\n")
    if apply:
        index_path.write_text(new_text, encoding="utf-8")
    return {"changed": bool(n), "line": new_line, "path": str(index_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply an IMA stock logic markdown card into Obsidian wiki.")
    parser.add_argument("input", help="IMA stock logic markdown path")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="Knowledge vault path")
    parser.add_argument("--entity", default="", help="Override entity page name")
    parser.add_argument("--source-name", default="", help="Override source page stem")
    parser.add_argument("--apply", action="store_true", help="Write changes. Default is dry-run.")
    parser.add_argument("--allow-main", action="store_true", help="Allow applying on knowledge repo main branch.")
    parser.add_argument("--backup", action="store_true", help="Backup relation JSON before apply.")
    parser.add_argument("--force", action="store_true", help="Append even if the same source name is already present.")
    parser.add_argument("--update-index", action="store_true", help="Also refresh wiki/index.md counts. Default skips index to avoid count-policy drift.")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    vault = Path(args.vault).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")
    if not vault.exists():
        raise SystemExit(f"Vault not found: {vault}")

    branch = run_git(["branch", "--show-current"], vault)
    status = run_git(["status", "--short"], vault)
    if args.apply and branch == "main" and not args.allow_main:
        raise SystemExit("Refusing to apply on knowledge repo main branch. Create a task branch or pass --allow-main explicitly.")

    input_text = input_path.read_text(encoding="utf-8")
    meta, body, _ = split_frontmatter(input_text)
    entity_name = args.entity.strip() or normalize_entity_name(meta, body)
    if not entity_name:
        raise SystemExit("Cannot infer entity name. Pass --entity.")
    ticker = normalize_ticker(meta.get("ticker") or meta.get("code") or first_h1(body))
    source_name = args.source_name.strip() or normalize_source_name(input_path.stem)
    log_id = next_log_id(vault)

    source_path = vault / "wiki" / "sources" / f"{source_name}.md"
    entity_path = vault / "wiki" / "entities" / f"{entity_name}.md"
    concepts = concept_candidates(meta, body, existing_concepts(vault))
    increment = build_entity_increment(meta, body, source_name)

    source_created = not source_path.exists()
    source_text = build_source_page(input_text, source_name, meta, log_id)
    entity_result = update_entity_page(entity_path, entity_name, ticker, source_name, increment, log_id, apply=args.apply, force=args.force)
    relations_result = update_relations(vault, entity_name, ticker, meta, body, source_name, concepts, apply=args.apply, backup=args.backup)
    log_entry = append_log(vault, log_id, source_name, entity_name, source_created, apply=args.apply)
    index_result = update_index_counts(vault, log_id, apply=args.apply) if args.update_index else {"changed": False, "reason": "skipped by default"}

    if args.apply:
        source_path.parent.mkdir(parents=True, exist_ok=True)
        if source_created or args.force:
            source_path.write_text(source_text, encoding="utf-8")

    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "input": str(input_path),
        "vault": str(vault),
        "git_branch": branch,
        "git_status_short": status.splitlines(),
        "log_id": log_id,
        "entity": entity_name,
        "ticker": ticker,
        "source_page": str(source_path),
        "source_created": source_created,
        "entity_result": entity_result,
        "concepts": concepts,
        "relations_result": relations_result,
        "index_result": index_result,
        "log_entry_preview": log_entry,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.apply:
        print("\nDRY-RUN only. Re-run with --apply to write changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

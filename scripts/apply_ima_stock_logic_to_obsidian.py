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

DEFAULT_VAULT = Path(os.environ.get("KNOWLEDGE_VAULT", "/Users/a77/Desktop/c c/知识库"))


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
        name = re.sub(r"个股逻辑研究$", "", name).strip()
        name = re.sub(r"个股逻辑卡$", "", name).strip()
        name = re.sub(r"逻辑卡$", "", name).strip()
        name = re.sub(r"(研究素材|素材整理|素材)$", "", name).strip()
        if name in {"华虹公司", "中微公司"}:
            return name
        name = re.sub(r"设计院股份有限公司$|科技股份有限公司$|集团股份有限公司$|股份有限公司$|有限公司$|公司$", "", name).strip()
        if name == "浙江嘉欣丝绸":
            name = "嘉欣丝绸"
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
    value = normalize_ticker_token(ticker)
    return value if re.fullmatch(r"\d{6}", value) else ""


def known_ticker_for_entity(entity_name: str) -> str:
    return {
        "宝鼎科技": "002552",
        "楚天高速": "600035",
    }.get(entity_name, "")


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


def split_display_chunks(text: str, separators: str = "、,，；;/") -> list[str]:
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
    generic_concepts = {"全球化", "基建", "通胀", "产业化", "新材料", "出海", "精密制造", "智能汽车", "通信服务", "液冷", "机器人", "一带一路", "能源转型", "传统能源", "出口管制", "出口", "电商", "国企改革", "央企改革", "新能源消纳", "工程", "系统集成", "公用事业", "检测设备", "北交所", "全产业链", "清洁能源", "高端制造", "智能制造", "智能化", "环保", "软件", "IT服务", "应用软件", "新基建", "电力设备", "电网设备", "家电", "大数据", "薄膜", "消费", "影视", "食品饮料", "医药生物", "医药", "国防军工", "通信设备", "国产替代", "自动化设备", "安防", "军工", "5G", "光学系统", "深海", "新能源储能", "OCS光交换", "OCS", "光器件", "光缆", "连接器", "线缆", "服务器", "交换机", "算力服务", "数据中心", "海外产能", "轻量化", "金属制品", "PCB", "高纯金属", "膜材料", "稀土", "LCD", "LED", "物联网", "自主可控", "战略金属", "小金属", "贵金属", "铅锌", "有色金属", "建材", "CIS", "化工", "半导体", "信息化", "医疗"}
    generic_concepts.update({"计算机设备", "化工新材料", "化工周期", "业绩反转", "定增终止", "控制权变更终止", "员工持股"})
    generic_concepts.update({"IoT", "QFII增持", "军工资产注入", "军贸出海", "传感器", "集成电路", "商业化"})
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
    if "CPO" in candidates and "CPO（共封装光学）" in candidates:
        candidates.remove("CPO（共封装光学）")
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
    if "MPO光纤连接器" in candidates and "光通信" in candidates:
        candidates.remove("光通信")
    if "陶瓷基板" in candidates and "陶瓷材料" in candidates:
        candidates.remove("陶瓷材料")
    if ("MLCC" in candidates or "被动元件" in candidates) and "电容" in candidates:
        candidates.remove("电容")
    if "TGV（玻璃通孔技术）" in candidates and "玻璃基板" in candidates:
        candidates.remove("玻璃基板")
    if "储能系统" in candidates and "储能" in candidates:
        candidates.remove("储能")
    if "新能源汽车" in candidates and "汽车零部件" in candidates:
        candidates.remove("汽车零部件")
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
    if "TSN" in text and "TSN时间敏感网络" in concepts and "TSN时间敏感网络" not in candidates:
        candidates.append("TSN时间敏感网络")
    if "国产算力" in body and "AI基础设施与国产算力" in concepts and "AI基础设施与国产算力" not in candidates:
        candidates.append("AI基础设施与国产算力")
    if ("AI算力铜连接" in text or "高速板对板连接器" in body) and "高速铜连接" in concepts and "高速铜连接" not in candidates:
        candidates.append("高速铜连接")
    if "高速背板连接器" in body and "高速铜连接" in concepts and "高速铜连接" not in candidates:
        candidates.append("高速铜连接")
    if ("机器人灵巧手" in body or "钨丝腱绳" in body) and "灵巧手" in concepts and "灵巧手" not in candidates:
        candidates.append("灵巧手")
    if ("智能监测传感" in text or "智能监测终端" in body) and "智能传感器" in concepts and "智能传感器" not in candidates:
        candidates.append("智能传感器")
    if ("液冷机柜" in body or "液冷集装箱" in body) and "数据中心液冷" in concepts and "数据中心液冷" not in candidates:
        candidates.append("数据中心液冷")
    if "AIDC光缆芳纶涨价" in text and "光纤光缆" in concepts and "光纤光缆" not in candidates:
        candidates.append("光纤光缆")
    if "光纤光缆" in body and "光纤光缆" in concepts and "光纤光缆" not in candidates:
        candidates.append("光纤光缆")
    if "光通信收入" in body and "光通信" in concepts and "光通信" not in candidates:
        candidates.append("光通信")
    if "TGV" in text and "TGV（玻璃通孔技术）" in concepts and "TGV（玻璃通孔技术）" not in candidates:
        candidates.append("TGV（玻璃通孔技术）")
    if "OCS" in text and "OCS光交换机" in concepts and "OCS光交换机" not in candidates:
        candidates.append("OCS光交换机")
    if "HBM" in body and "封测" in body and "HBM封装" in concepts and "HBM封装" not in candidates:
        candidates.append("HBM封装")
    if "800G" in body and "1.6T" in body and "800G_1.6T光模块" in concepts and "800G_1.6T光模块" not in candidates:
        candidates.append("800G_1.6T光模块")
    if "ALD" in body and "ALD设备" in concepts and "ALD设备" not in candidates:
        candidates.append("ALD设备")
    if "HVLP" in body and "HVLP铜箔" in concepts and "HVLP铜箔" not in candidates:
        candidates.append("HVLP铜箔")
    if "电子电路铜箔" in body and "PCB铜箔" in concepts and "PCB铜箔" not in candidates:
        candidates.append("PCB铜箔")
    if "AI铜箔" in body and "AI PCB" in concepts and "AI PCB" not in candidates:
        candidates.append("AI PCB")
    if ("昇腾APN" in body or "昇腾边缘AI" in body or "昇腾生态" in body) and "华为昇腾" in concepts and "华为昇腾" not in candidates:
        candidates.append("华为昇腾")
    if "AI算力PCB" in body and "AI PCB" in concepts and "AI PCB" not in candidates:
        candidates.append("AI PCB")
    if "AI PCB" in body and "AI PCB" in concepts and "AI PCB" not in candidates:
        candidates.append("AI PCB")
    if "AI算力电感" in body and "AI芯片电感" in concepts and "AI芯片电感" not in candidates:
        candidates.append("AI芯片电感")
    if ("服务器PMIC" in body or "DrMOS" in body) and "AI服务器电源" in concepts and "AI服务器电源" not in candidates:
        candidates.append("AI服务器电源")
    if "刻蚀" in body and "刻蚀设备" in concepts and "刻蚀设备" not in candidates:
        candidates.append("刻蚀设备")
    if "PCIe" in body and "高速互联" in concepts and "高速互联" not in candidates:
        candidates.append("高速互联")
    if "量检测" in body and "半导体量检测设备" in concepts and "半导体量检测设备" not in candidates:
        candidates.append("半导体量检测设备")
    if "量测" in body and "量测设备" in concepts and "量测设备" not in candidates:
        candidates.append("量测设备")
    if "光刻胶" in body and "光刻胶" in concepts and "光刻胶" not in candidates:
        candidates.append("光刻胶")
    if "SSD" in body and "固态硬盘（SSD）" in concepts and "固态硬盘（SSD）" not in candidates:
        candidates.append("固态硬盘（SSD）")
    if "Mini" in body and "Mini LED" in concepts and "Mini LED" not in candidates:
        candidates.append("Mini LED")
    if ("基础设施数智化" in body or "eCityOS" in body) and "智慧城市" in concepts and "智慧城市" not in candidates:
        candidates.append("智慧城市")
    if "高纯石英" in body and "高纯石英砂" in concepts and "高纯石英砂" not in candidates:
        candidates.append("高纯石英砂")
    if "碳化硅陶瓷" in body and "碳化硅" in concepts and "碳化硅" not in candidates:
        candidates.append("碳化硅")
    if "前驱体" in body and "前驱体材料" in concepts and "前驱体材料" not in candidates:
        candidates.append("前驱体材料")
    if "防爆四足机器人" in body and "特种机器人" in concepts and "特种机器人" not in candidates:
        candidates.append("特种机器人")
    if "具身智能" in body and "机器人" in body and "机器人与具身智能装备" in concepts and "机器人与具身智能装备" not in candidates:
        candidates.append("机器人与具身智能装备")
    if "DRAM" in body and "DRAM" in concepts and "DRAM" not in candidates:
        candidates.append("DRAM")
    if "NOR Flash" in body and "NOR Flash" in concepts and "NOR Flash" not in candidates:
        candidates.append("NOR Flash")
    if "CVD金刚石" in body and "CVD金刚石" in concepts and "CVD金刚石" not in candidates:
        candidates.append("CVD金刚石")
    if "金刚石功能化" in body and "功能性金刚石" in concepts and "功能性金刚石" not in candidates:
        candidates.append("功能性金刚石")
    if ("金刚石散热" in body or "金刚石热沉" in body) and "钻石散热" in concepts and "钻石散热" not in candidates:
        candidates.append("钻石散热")
    if ("半导体散热" in body or "高功率芯片散热" in body) and "半导体散热" in concepts and "半导体散热" not in candidates:
        candidates.append("半导体散热")
    if "六轴耦合台" in body and "光模块自动化设备" in concepts and "光模块自动化设备" not in candidates:
        candidates.append("光模块自动化设备")
    if "光谱仪器" in body and "光通信测试仪器" in concepts and "光通信测试仪器" not in candidates and "光通信" in body:
        candidates.append("光通信测试仪器")
    if ("苹果" in body or "AirPods" in body) and "苹果供应链" in concepts and "苹果供应链" not in candidates:
        candidates.append("苹果供应链")
    if "高频射频MLCC" in body and "高阶MLCC" in concepts and "高阶MLCC" not in candidates:
        candidates.append("高阶MLCC")
    if "企业级SSD" in body and "AI存储" in concepts and "AI存储" not in candidates:
        candidates.append("AI存储")
    if "NAND" in body and "3D NAND" in concepts and "3D NAND" not in candidates:
        candidates.append("3D NAND")
    if "企业级SSD" in body and "存储芯片" in concepts and "存储芯片" not in candidates:
        candidates.append("存储芯片")
    if "存储主控" in body and "存储芯片" in concepts and "存储芯片" not in candidates:
        candidates.append("存储芯片")
    if "UFS" in body and "存储芯片" in concepts and "存储芯片" not in candidates:
        candidates.append("存储芯片")
    if "DDR5 SPD" in body and "存储芯片" in concepts and "存储芯片" not in candidates:
        candidates.append("存储芯片")
    if "VPD" in body and "固态硬盘（SSD）" in concepts and "固态硬盘（SSD）" not in candidates:
        candidates.append("固态硬盘（SSD）")
    if "DDR5" in body and "DDR5" in concepts and "DDR5" not in candidates:
        candidates.append("DDR5")
    if "EEPROM" in body and "汽车芯片" in concepts and "汽车芯片" not in candidates:
        candidates.append("汽车芯片")
    if ("电子元器件分销" in body or "分销龙头" in body) and "IT分销" in concepts and "IT分销" not in candidates:
        candidates.append("IT分销")
    if "华为海思全产品线一级代理" in body and "华为昇腾" in concepts and "华为昇腾" not in candidates:
        candidates.append("华为昇腾")
    if "mSAP" in body and "高阶HDI" in concepts and "高阶HDI" not in candidates:
        candidates.append("高阶HDI")
    if ("DDIC" in body or "显示驱动芯片" in body) and "显示驱动" in concepts and "显示驱动" not in candidates:
        candidates.append("显示驱动")
    if ("电子特种气体" in body or "特种气体" in body) and "电子特气" in concepts and "电子特气" not in candidates:
        candidates.append("电子特气")
    if "高纯石英" in body and "高纯石英砂" in concepts and "高纯石英砂" not in candidates:
        candidates.append("高纯石英砂")
    if "存储涨价" in body and "AI存储" in concepts and "AI存储" not in candidates:
        candidates.append("AI存储")
    if ("国产算力服务器" in body or "AI超节点" in body) and "AI服务器" in concepts and "AI服务器" not in candidates:
        candidates.append("AI服务器")
    if ("光纤光缆" in body or "空芯光纤" in body) and "光纤光缆" in concepts and "光纤光缆" not in candidates:
        candidates.append("光纤光缆")
    if ("三电热管理" in body or "新能源汽车综合热管理" in body) and "新能源汽车热管理" in concepts and "新能源汽车热管理" not in candidates:
        candidates.append("新能源汽车热管理")
    if ("世界杯赞助" in body or "家电" in body and "出海" in body) and "家电出海" in concepts and "家电出海" not in candidates:
        candidates.append("家电出海")
    if "黑色家电" in body and "黑电品牌出海" in concepts and "黑电品牌出海" not in candidates:
        candidates.append("黑电品牌出海")
    if "AI智能家居" in body and "智能家居" in concepts and "智能家居" not in candidates:
        candidates.append("智能家居")
    if ("煤价底部反转" in body or "动力煤" in body) and "煤炭" in concepts and "煤炭" not in candidates:
        candidates.append("煤炭")
    if ("分红比例" in body or "高分红" in body) and "高股息红利" in concepts and "高股息红利" not in candidates:
        candidates.append("高股息红利")
    if ("RTF" in body or "HVLP" in body) and "PCB铜箔" in concepts and "PCB铜箔" not in candidates:
        candidates.append("PCB铜箔")
    if "复合集流体" in body and "复合集流体" in concepts and "复合集流体" not in candidates:
        candidates.append("复合集流体")
    if ("三代制冷剂" in body or "HFCs" in body) and "三代制冷剂" in concepts and "三代制冷剂" not in candidates:
        candidates.append("三代制冷剂")
    if "六氟磷酸锂" in body and "六氟磷酸锂" in concepts and "六氟磷酸锂" not in candidates:
        candidates.append("六氟磷酸锂")
    if "光伏发电" in body and "光伏" in concepts and "光伏" not in candidates:
        candidates.append("光伏")
    if ("SOI硅片" in body or "硅光" in body) and "硅光" in concepts and "硅光" not in candidates:
        candidates.append("硅光")
    if "晶圆代工" in body and "晶圆代工" in concepts and "晶圆代工" not in candidates:
        candidates.append("晶圆代工")
    if ("超节点" in body or "AI超节点" in body) and "AI超节点" in concepts and "AI超节点" not in candidates:
        candidates.append("AI超节点")
    if "医药流通" in body and "医药流通" in concepts and "医药流通" not in candidates:
        candidates.append("医药流通")
    if "医药零售" in body and "医药零售" in concepts and "医药零售" not in candidates:
        candidates.append("医药零售")
    if "薄膜电容" in body and "薄膜电容" in concepts and "薄膜电容" not in candidates:
        candidates.append("薄膜电容")
    if ("被动元器件" in body or "被动元件" in body) and "被动元件" in concepts and "被动元件" not in candidates:
        candidates.append("被动元件")
    if ("高速铜缆" in body or "高速线缆" in body or "DAC高速铜缆" in body) and "高速铜缆" in concepts and "高速铜缆" not in candidates:
        candidates.append("高速铜缆")
    if ("高速互联" in body or "信号互联" in body) and "高速铜连接" in concepts and "高速铜连接" not in candidates:
        candidates.append("高速铜连接")
    if ("AI服务器PCB" in body or "AI服务器高多层" in body) and "AI服务器PCB" in concepts and "AI服务器PCB" not in candidates:
        candidates.append("AI服务器PCB")
    if ("高阶HDI" in body or "高阶 HDI" in body) and "高阶HDI" in concepts and "高阶HDI" not in candidates:
        candidates.append("高阶HDI")
    if ("汽车连接器" in body or "机器人连接器" in body or "精密连接器" in body) and "连接器" in concepts and "连接器" not in candidates:
        candidates.append("连接器")
    if ("储能系统" in body or "储备一体" in body) and "储能系统" in concepts and "储能系统" not in candidates:
        candidates.append("储能系统")
    if ("CXL" in body or "内存扩展" in body) and "CXL技术" in concepts and "CXL技术" not in candidates:
        candidates.append("CXL技术")
    if "光纤预制棒" in body and "光纤光缆" in concepts and "光纤光缆" not in candidates:
        candidates.append("光纤光缆")
    if "硅烷偶联剂" in body and "硅烷偶联剂" in concepts and "硅烷偶联剂" not in candidates:
        candidates.append("硅烷偶联剂")
    if "电力市场化" in body and "电力市场化" in concepts and "电力市场化" not in candidates:
        candidates.append("电力市场化")
    if ("射频连接器" in body or "电连接器" in body) and "连接器" in concepts and "连接器" not in candidates:
        candidates.append("连接器")
    if "商业航天" in body and "商业航天" in concepts and "商业航天" not in candidates:
        candidates.append("商业航天")
    if "园区" in body and "园区开发" in concepts and "园区开发" not in candidates:
        candidates.append("园区开发")
    if ("AI数据中心" in body or "AIDC" in body) and "AIDC发电设备" in concepts and "AIDC发电设备" not in candidates:
        candidates.append("AIDC发电设备")
    if ("快充" in body or "5C" in body or "10C" in body) and "快充技术" in concepts and "快充技术" not in candidates:
        candidates.append("快充技术")
    if ("IC载板" in body or "ABF载板" in body or "BT载板" in body) and "IC载板" in concepts and "IC载板" not in candidates:
        candidates.append("IC载板")
    if "容量电价" in body and "容量电价" in concepts and "容量电价" not in candidates:
        candidates.append("容量电价")
    if "半导体石英" in body and "半导体石英砂" in concepts and "半导体石英砂" not in candidates:
        candidates.append("半导体石英砂")
    if "超高清" in body and "8K超高清" in concepts and "8K超高清" not in candidates:
        candidates.append("8K超高清")
    if "AI Agent" in body and "AI智能体" in concepts and "AI智能体" not in candidates:
        candidates.append("AI智能体")
    if "光纤光缆" in body and "光纤光缆" in concepts and "光纤光缆" not in candidates:
        candidates.append("光纤光缆")
    if ("高股息" in text or "红利" in text) and "高股息红利" in concepts and "高股息红利" not in candidates:
        candidates.append("高股息红利")
    if "高股息红利" in candidates and "高股息" in candidates:
        candidates.remove("高股息")
    if "AI基础设施与国产算力" in candidates and "算力" in candidates:
        candidates.remove("算力")
    if "AI基础设施与国产算力" in candidates and "AI算力" in candidates:
        candidates.remove("AI算力")
    if "AI基础设施与国产算力" in candidates and "算力基础设施" in candidates:
        candidates.remove("算力基础设施")
    if "AI智能体" in candidates and "AI应用" in candidates:
        candidates.remove("AI应用")
    if ("AI存储" in candidates or "端侧AI" in candidates or "AI端侧" in candidates) and "AI智能体" in candidates and "iSA智能体" in body:
        candidates.remove("AI智能体")
    if "TSN时间敏感网络" in candidates and "卫星互联网" in candidates and ("未确认卫星端独家地位" in body or "公司官方未确认" in body):
        candidates.remove("卫星互联网")
    if "高速铜连接" in candidates and "铜连接" in candidates:
        candidates.remove("铜连接")
    if ("高速铜连接" in candidates or "高速铜缆" in candidates or "铜缆互联" in candidates) and "AI算力" in candidates:
        candidates.remove("AI算力")
    if any(concept in candidates for concept in ["先进封装", "CoWoS", "Chiplet", "HBM封装"]) and "AI算力" in candidates:
        candidates.remove("AI算力")
    if any(concept in candidates for concept in ["先进封装", "CoWoS", "Chiplet", "HBM封装"]) and "AI基础设施与国产算力" in candidates:
        candidates.remove("AI基础设施与国产算力")
    if "数据中心液冷" in candidates and "AI算力" in candidates:
        candidates.remove("AI算力")
    if "数据中心液冷" in candidates and "液冷散热" in candidates:
        candidates.remove("液冷散热")
    if "智能传感器" in candidates and "传感器" in candidates:
        candidates.remove("传感器")
    if "智慧养老" in candidates and "银发经济" in candidates:
        candidates.remove("银发经济")
    if "涂覆隔膜" in candidates and "新能源" in candidates:
        candidates.remove("新能源")
    if "液冷超充" in candidates and "超充" in candidates:
        candidates.remove("超充")
    if "液冷超充" in candidates and "新能源" in candidates:
        candidates.remove("新能源")
    if ("光纤光缆" in candidates or "空芯光纤" in candidates or "MPO光纤连接器" in candidates or "CPO" in candidates or "光模块" in candidates) and "AI算力基础设施" in candidates:
        candidates.remove("AI算力基础设施")
    if ("AI算力材料" in text or "半导体靶材" in body) and "AI算力" in candidates:
        candidates.remove("AI算力")
    if ("AI服务器智能检测" in body or "AI服务器的智能生产与检测" in body) and "AI服务器" in candidates:
        candidates.remove("AI服务器")
    if "机器视觉" in text and "锂电AI检测" in body and "新能源" in candidates:
        candidates.remove("新能源")
    if "暂未明确提及光模块客户" in body and "光模块" in candidates:
        candidates.remove("光模块")
    if ("官方明确否认" in body or "多次官方澄清不涉光纤" in body or "多次公告澄清") and "光纤光缆" in candidates:
        candidates.remove("光纤光缆")
    if "中利集团并非光伏设备商" in body and "光伏设备" in candidates:
        candidates.remove("光伏设备")
    if "光通讯 0.20亿（0.61%）" in body and "光通信" in candidates:
        candidates.remove("光通信")
    if ("液冷仅为研发储备方向" in body or "没有液冷订单" in body) and "液冷散热" in candidates:
        candidates.remove("液冷散热")
    if "无石英光纤预制棒及石英光纤制造产能" in body and "光纤光缆" in candidates:
        candidates.remove("光纤光缆")
    if "不涉及算力数据中心相关光纤光缆/光模块" in body:
        for concept in ["AI算力", "光模块"]:
            if concept in candidates:
                candidates.remove(concept)
    if ("暂无算力业务相关收入" in body or "首个合同待落地" in body) and "AI基础设施与国产算力" in candidates:
        candidates.remove("AI基础设施与国产算力")
    if "从未在公告或IR活动中明确提及\"商业航天\"" in body and "商业航天" in candidates:
        candidates.remove("商业航天")
    if "无法确认是否为互联网/运营商等AI算力客户" in body and "AI算力" in candidates:
        candidates.remove("AI算力")
    if "数据中心大合同是否属于信创项目未明确" in body and "信创" in candidates:
        candidates.remove("信创")
    if "智慧城市系统集成商" in body and "智慧城市" in candidates:
        candidates.remove("智慧城市")
    if "公司多次明确表示\"与英伟达暂无业务往来\"" in body:
        for concept in ["AI算力", "东数西算"]:
            if concept in candidates:
                candidates.remove(concept)
    if "传统安防+交通业务" in body and "智能交通" in candidates:
        candidates.remove("智能交通")
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
    if "钙钛矿光伏" in candidates and "光伏组件" in candidates:
        candidates.remove("光伏组件")
    if "配套光伏" in body and "水电" in candidates and "光伏" in candidates:
        candidates.remove("光伏")
    if "MPO光纤连接器" in candidates and "光通信" in candidates:
        candidates.remove("光通信")
    if "TGV（玻璃通孔技术）" in candidates and "玻璃基板" in candidates:
        candidates.remove("玻璃基板")
    if "高速铜连接" in candidates and "铜连接" in candidates:
        candidates.remove("铜连接")
    if "液冷超充" in candidates and "超充" in candidates:
        candidates.remove("超充")
    if "液冷超充" in candidates and "新能源" in candidates:
        candidates.remove("新能源")
    if "C919大飞机" in candidates and "C919" in candidates:
        candidates.remove("C919")
    if "C919大飞机" in candidates and "大飞机" in candidates:
        candidates.remove("大飞机")
    if "卫星互联网" in candidates and "商业航天" in candidates:
        candidates.remove("商业航天")
    if "电化学储能" in candidates and "储能" in candidates:
        candidates.remove("储能")
    if "钙钛矿光伏" in candidates and "光伏材料" in candidates:
        candidates.remove("光伏材料")
    if "固态电池" in candidates and "电池材料" in candidates:
        candidates.remove("电池材料")
    if "数据中心液冷" in candidates and "AI算力" in candidates:
        candidates.remove("AI算力")
    if "数据中心液冷" in candidates and "液冷散热" in candidates:
        candidates.remove("液冷散热")
    if "智能传感器" in candidates and "传感器" in candidates:
        candidates.remove("传感器")
    if "智慧养老" in candidates and "银发经济" in candidates:
        candidates.remove("银发经济")
    if "AI智能体" in candidates and "AI应用" in candidates:
        candidates.remove("AI应用")
    if "TSN时间敏感网络" in candidates and "卫星互联网" in candidates and ("未确认卫星端独家地位" in body or "公司官方未确认" in body):
        candidates.remove("卫星互联网")
    if "Robotaxi" in candidates:
        for concept in ["无人驾驶", "智能驾驶", "自动驾驶"]:
            if concept in candidates:
                candidates.remove(concept)
    if "车联网" in candidates and "智能驾驶" in candidates:
        candidates.remove("智能驾驶")
    if "OCS光交换机" in candidates and "智慧城市" in candidates:
        candidates.remove("智慧城市")
    if "AI眼镜" in candidates and "智能穿戴" in candidates:
        candidates.remove("智能穿戴")
    if "800G_1.6T光模块" in candidates and "光模块" in candidates:
        candidates.remove("光模块")
    if "HBM封装" in candidates and "HBM" in candidates:
        candidates.remove("HBM")
    if "合封KGD" in body and "HBM封装" in candidates and "HBM先进封装" not in body and "HBM3" not in body:
        candidates.remove("HBM封装")
    if "六氟磷酸锂" in candidates:
        for concept in ["新能源材料", "锂电材料"]:
            if concept in candidates:
                candidates.remove(concept)
    if "硼同位素" in body and "核电" in candidates and ("体量极小" in body or "收入贡献可忽略" in body or "极早期" in body):
        candidates.remove("核电")
    if "太空光伏" in body and "商业航天" in candidates and ("公司从未官方确认" in body or "无官方确认" in body or "高风险待复核" in body):
        candidates.remove("商业航天")
    if "ALD设备" in candidates and "刻蚀设备" in candidates and "半导体设备" in candidates:
        candidates.remove("半导体设备")
    if "光伏设备" in candidates and "显示面板" in candidates:
        candidates.remove("显示面板")
    if "光刻胶" in candidates and "显示材料" in candidates:
        candidates.remove("显示材料")
    if "CMP抛光液" in candidates and "锂电材料" in candidates and "半导体材料" in candidates:
        candidates.remove("锂电材料")
    if "CMP抛光液" in candidates and "半导体材料" in candidates and "新能源" in candidates:
        candidates.remove("新能源")
    if "半导体量检测设备" in candidates:
        for concept in ["半导体设备", "检测设备"]:
            if concept in candidates:
                candidates.remove(concept)
    if "量测设备" in candidates and "半导体设备" in candidates:
        candidates.remove("半导体设备")
    if "存储测试设备" in body and "HBM封装" in candidates:
        candidates.remove("HBM封装")
    if "产能因转向HBM" in body and "HBM封装" in candidates:
        candidates.remove("HBM封装")
    if any(concept in candidates for concept in ["CVD金刚石", "功能性金刚石", "钻石散热", "半导体散热"]) and "AI算力" in candidates:
        candidates.remove("AI算力")
    if any(concept in candidates for concept in ["CVD金刚石", "功能性金刚石", "钻石散热", "半导体散热"]) and "半导体材料" in candidates:
        candidates.remove("半导体材料")
    if any(concept in candidates for concept in ["钻石散热", "半导体散热"]) and "AI散热" in candidates:
        candidates.remove("AI散热")
    if "存储测试设备" in body and "半导体设备" in candidates:
        candidates.remove("半导体设备")
    if "SiC" in candidates and "第三代半导体" in candidates and "CMP抛光液" in candidates:
        candidates.remove("第三代半导体")
    if "高深宽比刻蚀结构量测" in body and "刻蚀设备" in candidates:
        candidates.remove("刻蚀设备")
    if "ALD设备" in candidates and "半导体设备" in candidates and "PECVD" in candidates:
        candidates.remove("半导体设备")
    if "Chiplet" in candidates and "硅片" in candidates:
        candidates.remove("硅片")
    if "HBM封装" in candidates and "智能终端" in candidates:
        candidates.remove("智能终端")
    if ("HVLP铜箔" in candidates or "PCB铜箔" in candidates or "AI PCB" in candidates) and "铜箔" in candidates:
        candidates.remove("铜箔")
    if ("HVLP铜箔" in candidates or "PCB铜箔" in candidates or "AI PCB" in candidates) and "AI算力" in candidates:
        candidates.remove("AI算力")
    if ("HVLP铜箔" in candidates or "PCB铜箔" in candidates or "AI PCB" in candidates) and "电子材料" in candidates:
        candidates.remove("电子材料")
    if "电子元器件分销" in body and "AI算力" in candidates and ("存储芯片" in candidates or "MLCC" in candidates):
        candidates.remove("AI算力")
    if "电子元器件分销" in body and "AI基础设施与国产算力" in candidates and ("存储芯片" in candidates or "华为昇腾" in candidates):
        candidates.remove("AI基础设施与国产算力")
    if "AI PCB" in candidates:
        for concept in ["印制电路板", "消费电子", "800G_1.6T光模块", "AI算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "消费电子设备" in candidates and "消费电子" in candidates:
        candidates.remove("消费电子")
    if "高风险待复核" in body and "人形机器人" in candidates:
        candidates.remove("人形机器人")
    if "无实质性业绩贡献" in body and "灵巧手" in candidates:
        candidates.remove("灵巧手")
    if "AI芯片电感" in candidates and "800G_1.6T光模块" in candidates:
        candidates.remove("800G_1.6T光模块")
    if "AI服务器电源" in candidates and "AI服务器" in candidates:
        candidates.remove("AI服务器")
    if "光模块" in candidates and "光通信" in candidates:
        candidates.remove("光通信")
    if "AI服务器PCB" in candidates and "AI服务器" in candidates:
        candidates.remove("AI服务器")
    if "HDI板" in candidates and "HDI" in candidates:
        candidates.remove("HDI")
    if "800G_1.6T光模块" in candidates and "800G光模块" in candidates:
        candidates.remove("800G光模块")
    if "光模块自动化设备" in candidates and "800G_1.6T光模块" in candidates:
        candidates.remove("800G_1.6T光模块")
    if "光模块自动化设备" in candidates and "AI算力" in candidates:
        candidates.remove("AI算力")
    if ("光模块自动化设备" in candidates or "光通信测试仪器" in candidates) and "仪器仪表" in candidates:
        candidates.remove("仪器仪表")
    if ("AI服务器PCB" in candidates or "HDI板" in candidates or "IC载板" in candidates) and "消费电子" in candidates:
        candidates.remove("消费电子")
    if "公司官方公告未明确" in body and "华为昇腾" in candidates:
        candidates.remove("华为昇腾")
    if "万隆光电" in text and "缺乏公司公告确认" in body and "商业航天" in candidates:
        candidates.remove("商业航天")
    if "建筑智能体" in body and "AI智能体" in candidates:
        candidates.remove("AI智能体")
    if "传统地产拖累" in body and "房地产" in candidates:
        candidates.remove("房地产")
    if "高速互联" in candidates:
        for concept in ["算力基建", "AI基础设施与国产算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "泽石科技PCIe" in body and "高速互联" in candidates and "同有科技" in text:
        candidates.remove("高速互联")
    if "固态硬盘（SSD）" in candidates and "信创" in candidates:
        candidates.remove("信创")
    if "新能源汽车运输" in body and "新能源汽车" in candidates and "渤海轮渡" in text:
        candidates.remove("新能源汽车")
    if "TWS耳机" in candidates and "消费电子" in candidates:
        candidates.remove("消费电子")
    if "楚天高速" in text:
        for concept in ["智能交通", "新能源", "券商"]:
            if concept in candidates:
                candidates.remove(concept)
    if "高阶MLCC" in candidates and "MLCC" in candidates and "达利凯普" in text:
        candidates.remove("MLCC")
    if "射频MLCC产品未在光模块应用" in body:
        for concept in ["800G_1.6T光模块", "AI算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "航空航天业务占比低" in body and "商业航天" in candidates and "达利凯普" not in text:
        candidates.remove("商业航天")
    if ("固态硬盘（SSD）" in candidates or "AI存储" in candidates) and "AI算力" in candidates:
        candidates.remove("AI算力")
    if "企业级SSD" in body and "高速互联" in candidates:
        candidates.remove("高速互联")
    if "企业级SSD" in body and "DRAM" in candidates:
        candidates.remove("DRAM")
    if "精测电子" in text and "新能源业务亏损" in body and "新能源" in candidates:
        candidates.remove("新能源")
    if "半导体量检测设备" in candidates:
        for concept in ["半导体国产替代", "先进制程"]:
            if concept in candidates:
                candidates.remove(concept)
    if "聚辰股份" in text:
        for concept in ["AI服务器", "DRAM", "AIDC发电设备", "晶圆代工", "AI智能体"]:
            if concept in candidates:
                candidates.remove(concept)
    if ("汇成股份" in text or "合肥新汇成" in text) and "DRAM封测" in text and "存储芯片" in concepts and "存储芯片" not in candidates:
        candidates.append("存储芯片")
    if "微导纳米" in text and "存储扩产" in text and "存储芯片" in concepts and "存储芯片" not in candidates:
        candidates.append("存储芯片")
    if "汽车芯片" in candidates and "汽车电子" in candidates:
        candidates.remove("汽车电子")
    if "高阶HDI" in candidates and "HDI" in candidates:
        candidates.remove("HDI")
    if "AI服务器PCB" in candidates and "AI PCB" in candidates:
        candidates.remove("AI PCB")
    if "陶瓷基板" in candidates and "AI算力" in candidates:
        candidates.remove("AI算力")
    if "联芸科技" in text:
        for concept in ["算力基础设施", "算力", "数据存储"]:
            if concept in candidates:
                candidates.remove(concept)
    if "AI存储" in candidates and "AI推理" in candidates:
        candidates.remove("AI推理")
    if "神州数码" in text and "神州问学" in body and "AI智能体" in candidates:
        candidates.remove("AI智能体")
    if "神州数码" in text and "华为昇腾" in candidates and "昇腾" not in body:
        candidates.remove("华为昇腾")
    if "微导纳米" in text:
        for concept in ["HBM", "DRAM", "刻蚀设备"]:
            if concept in candidates:
                candidates.remove(concept)
    if "微导纳米" in text and "钙钛矿" in candidates and "光伏设备" in candidates:
        candidates.remove("钙钛矿")
    if "中电港" in text:
        for concept in ["AI算力芯片", "DRAM", "3D NAND", "DDR5", "端侧AI"]:
            if concept in candidates:
                candidates.remove(concept)
    if "阿石创" in text:
        for concept in ["半导体国产替代", "光刻机"]:
            if concept in candidates:
                candidates.remove(concept)
    if "博敏电子" in text:
        for concept in ["ASIC", "华为昇腾"]:
            if concept in candidates:
                candidates.remove(concept)
    if "华特气体" in text:
        for concept in ["半导体材料", "刻蚀设备", "存储芯片"]:
            if concept in candidates:
                candidates.remove(concept)
    if "汇成股份" in text:
        for concept in ["半导体国产替代", "DDR5"]:
            if concept in candidates:
                candidates.remove(concept)
    if "天山电子" in text:
        for concept in ["HBM", "ASIC"]:
            if concept in candidates:
                candidates.remove(concept)
    if "中巨芯" in text:
        for concept in ["半导体国产替代", "半导体材料", "存储芯片", "刻蚀设备"]:
            if concept in candidates:
                candidates.remove(concept)
    if "中科仪" in text:
        for concept in ["半导体国产替代", "刻蚀设备"]:
            if concept in candidates:
                candidates.remove(concept)
    if "英唐智控" in text and "显示驱动" in candidates:
        candidates.remove("显示驱动")
    if "德科立" in text:
        for concept in ["OCS光交换机", "AI算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "德明利" in text:
        for concept in ["高速互联", "DRAM", "固态硬盘"]:
            if concept in candidates:
                candidates.remove(concept)
    if "方大集团" in text and "新能源" in candidates:
        candidates.remove("新能源")
    if "菲利华" in text:
        for concept in ["AI算力", "量测设备", "半导体材料"]:
            if concept in candidates:
                candidates.remove(concept)
    if "烽火通信" in text:
        for concept in ["AI算力", "卫星互联网", "AI基础设施与国产算力"]:
            if concept in candidates:
                candidates.remove(concept)
        if "光纤光缆" in body and "光纤光缆" in concepts and "光纤光缆" not in candidates:
            candidates.append("光纤光缆")
    if "福晶科技" in text:
        for concept in ["半导体设备", "OCS光交换机", "AI算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "光电股份" in text:
        for concept in ["800G_1.6T光模块", "半导体设备", "光刻机"]:
            if concept in candidates:
                candidates.remove(concept)
    if "光韵达" in text:
        for concept in ["AI算力", "印制电路板", "PCB", "激光设备"]:
            if concept in candidates:
                candidates.remove(concept)
    if "海康威视" in text:
        for concept in ["海外市场", "大模型", "AI存储"]:
            if concept in candidates:
                candidates.remove(concept)
    if "海信家电" in text:
        for concept in ["热管理", "机器人", "AI智能体"]:
            if concept in candidates:
                candidates.remove(concept)
    if "海信视像" in text:
        for concept in ["品牌出海", "家电出海", "显示驱动"]:
            if concept in candidates:
                candidates.remove(concept)
    if "杭电股份" in text:
        for concept in ["AI算力", "铜箔", "光通信"]:
            if concept in candidates:
                candidates.remove(concept)
        if "光纤光缆" in body and "光纤光缆" in concepts and "光纤光缆" not in candidates:
            candidates.append("光纤光缆")
    if "杭州园林" in text:
        for concept in ["AI应用", "设计服务", "区块链"]:
            if concept in candidates:
                candidates.remove(concept)
    if "昊华科技" in text:
        for concept in ["3D NAND", "半导体国产替代", "制冷剂", "锂电材料"]:
            if concept in candidates:
                candidates.remove(concept)
    if "昊华能源" in text:
        for concept in ["高股息"]:
            if concept in candidates:
                candidates.remove(concept)
    if "合锻智能" in text:
        for concept in ["AI服务器", "专用设备", "CCL", "AI PCB", "核聚变"]:
            if concept in candidates:
                candidates.remove(concept)
        if "核聚变" in body and "可控核聚变" in concepts and "可控核聚变" not in candidates:
            candidates.append("可控核聚变")
    if "亨通股份" in text:
        for concept in ["新能源", "饲料", "复合铜箔", "AI PCB"]:
            if concept in candidates:
                candidates.remove(concept)
    if "恒星科技" in text:
        for concept in ["光伏"]:
            if concept in candidates:
                candidates.remove(concept)
    if "红星发展" in text:
        for concept in ["AI算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "洪田股份" in text:
        for concept in ["HVLP铜箔", "复合集流体", "专用设备", "商业航天", "固态电池", "电镀", "PCB铜箔"]:
            if concept in candidates:
                candidates.remove(concept)
    if "湖北能源" in text:
        for concept in ["新能源"]:
            if concept in candidates:
                candidates.remove(concept)
        if "光伏发电" in body and "光伏" in concepts and "光伏" not in candidates:
            candidates.append("光伏")
    if "沪硅产业" in text:
        for concept in ["半导体材料", "AI算力", "硅产业", "硅片"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("SOI硅片" in body or "硅光" in body) and "硅光" in concepts and "硅光" not in candidates:
            candidates.append("硅光")
    if "华大九天" in text:
        for concept in ["AI智能体"]:
            if concept in candidates:
                candidates.remove(concept)
    if "华虹公司" in text or "华虹半导体" in text:
        for concept in ["AI电源", "AI存储", "半导体国产替代"]:
            if concept in candidates:
                candidates.remove(concept)
        if "晶圆代工" in body and "晶圆代工" in concepts and "晶圆代工" not in candidates:
            candidates.append("晶圆代工")
    if "华丽家族" in text:
        for concept in ["机器人"]:
            if concept in candidates:
                candidates.remove(concept)
    if "华脉科技" in text:
        for concept in ["算力", "算力网络"]:
            if concept in candidates:
                candidates.remove(concept)
    if "华勤技术" in text:
        for concept in ["AI基础设施与国产算力"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("超节点" in body or "AI超节点" in body) and "AI超节点" in concepts and "AI超节点" not in candidates:
            candidates.append("AI超节点")
    if "华润江中" in text:
        if "高股息红利" in concepts and "高股息红利" not in candidates:
            candidates.append("高股息红利")
    if "火炬电子" in text:
        for concept in ["AI服务器", "电子元件"]:
            if concept in candidates:
                candidates.remove(concept)
    if "嘉事堂" in text:
        for concept in ["医疗器械"]:
            if concept in candidates:
                candidates.remove(concept)
        if "医药流通" in body and "医药流通" in concepts and "医药流通" not in candidates:
            candidates.append("医药流通")
        if "医药零售" in body and "医药零售" in concepts and "医药零售" not in candidates:
            candidates.append("医药零售")
    if "嘉欣丝绸" in text:
        for concept in ["AI应用", "机器人"]:
            if concept in candidates:
                candidates.remove(concept)
    if "江丰电子" in text:
        for concept in ["半导体国产替代", "先进制程"]:
            if concept in candidates:
                candidates.remove(concept)
    if "江海股份" in text:
        for concept in ["电子元件", "电容"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("被动元器件" in body or "被动元件" in body) and "被动元件" in concepts and "被动元件" not in candidates:
            candidates.append("被动元件")
    if "节能铁汉" in text:
        for concept in ["节能"]:
            if concept in candidates:
                candidates.remove(concept)
    if "杰普特" in text:
        for concept in ["消费电子", "锂电设备", "硅光"]:
            if concept in candidates:
                candidates.remove(concept)
    if "金达莱" in text:
        for concept in ["机器人", "医疗器械", "环保"]:
            if concept in candidates:
                candidates.remove(concept)
        if "医疗机器人" in body and "医疗机器人" in concepts and "医疗机器人" not in candidates:
            candidates.append("医疗机器人")
    if "金房能源" in text:
        for concept in ["数据中心液冷", "液冷技术", "算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "金海高科" in text:
        for concept in ["新能源汽车", "家电出海"]:
            if concept in candidates:
                candidates.remove(concept)
    if "金时科技" in text:
        for concept in ["光通信", "新能源", "电容", "硅光", "算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "金信诺" in text:
        if ("高速铜缆" in body or "高速线缆" in body or "DAC高速铜缆" in body) and "高速铜缆" in concepts and "高速铜缆" not in candidates:
            candidates.append("高速铜缆")
        if ("高速互联" in body or "信号互联" in body) and "高速铜连接" in concepts and "高速铜连接" not in candidates:
            candidates.append("高速铜连接")
        if "高速铜连接" in candidates and "高速互联" in candidates:
            candidates.remove("高速互联")
    if "九州一轨" in text:
        for concept in ["AI算力基础设施", "轨道交通", "800G_1.6T光模块"]:
            if concept in candidates:
                candidates.remove(concept)
    if "骏亚科技" in text:
        for concept in ["光模块", "人形机器人"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("AI服务器PCB" in body or "AI服务器高多层" in body) and "AI服务器PCB" in concepts and "AI服务器PCB" not in candidates:
            candidates.append("AI服务器PCB")
        if ("高阶HDI" in body or "高阶 HDI" in body) and "高阶HDI" in concepts and "高阶HDI" not in candidates:
            candidates.append("高阶HDI")
    if "凯伦股份" in text:
        for concept in ["显示面板", "光模块", "量测设备", "OCS光电路交换机"]:
            if concept in candidates:
                candidates.remove(concept)
    if "科强股份" in text:
        for concept in ["光伏", "石油"]:
            if concept in candidates:
                candidates.remove(concept)
    if "科瑞技术" in text:
        for concept in ["专用设备", "新能源", "OCS光电路交换机"]:
            if concept in candidates:
                candidates.remove(concept)
    if "科润智控" in text:
        for concept in ["AI算力", "家电出海", "SST", "变压器"]:
            if concept in candidates:
                candidates.remove(concept)
    if "科信技术" in text:
        for concept in ["AI算力基础设施", "AI服务器", "电信运营商", "CT设备", "海外市场", "液冷技术", "绿色低碳", "运营商", "锂电池", "高股息红利"]:
            if concept in candidates:
                candidates.remove(concept)
        if "储能系统" in body and "储能系统" in concepts and "储能系统" not in candidates:
            candidates.append("储能系统")
        if ("液冷温控" in body or "温控" in body) and "液冷温控" in concepts and "液冷温控" not in candidates:
            candidates.append("液冷温控")
    if "昆工科技" in text:
        for concept in ["智算中心"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("储能系统" in body or "储备一体" in body) and "储能系统" in concepts and "储能系统" not in candidates:
            candidates.append("储能系统")
    if "徕木股份" in text:
        for concept in ["新能源汽车", "智能驾驶"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("汽车连接器" in body or "机器人连接器" in body or "精密连接器" in body) and "连接器" in concepts and "连接器" not in candidates:
            candidates.append("连接器")
    if "兰花科创" in text:
        for concept in ["节能环保", "节能"]:
            if concept in candidates:
                candidates.remove(concept)
    if "澜起科技" in text:
        for concept in ["AI算力基础设施", "DRAM", "晶圆代工", "高速互联"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("CXL" in body or "内存扩展" in body) and "CXL技术" in concepts and "CXL技术" not in candidates:
            candidates.append("CXL技术")
    if "雷神科技" in text:
        for concept in ["消费电子", "算力", "AI智能体", "AI存储"]:
            if concept in candidates:
                candidates.remove(concept)
    if "立昂微" in text:
        for concept in ["AI服务器电源", "人形机器人", "新能源汽车", "硅片", "半导体材料", "地缘政治", "激光雷达", "电源芯片", "禾赛科技", "比亚迪", "大疆车载"]:
            if concept in candidates:
                candidates.remove(concept)
    if "利和兴" in text:
        for concept in ["半导体国产替代", "AI算力", "专用设备", "CPO", "800G_1.6T光模块", "刻蚀设备", "DRAM", "半导体设备"]:
            if concept in candidates:
                candidates.remove(concept)
        if "液冷服务器" in body and "液冷服务器" in concepts and "液冷服务器" not in candidates:
            candidates.append("液冷服务器")
    if "联瑞新材" in text:
        for concept in ["新能源汽车", "AI服务器", "产能过剩", "正交背板", "高端CCL"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("硅微粉" in body or "球硅" in body) and "硅微粉" in concepts and "硅微粉" not in candidates:
            candidates.append("硅微粉")
    if "联特科技" in text:
        for concept in ["光通信"]:
            if concept in candidates:
                candidates.remove(concept)
    if "龙磁科技" in text:
        for concept in ["AI芯片", "固态硬盘（SSD）", "被动元件"]:
            if concept in candidates:
                candidates.remove(concept)
    if "罗博特科" in text:
        for concept in ["专用设备", "光伏设备", "AI算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "漫步者" in text:
        for concept in ["消费电子", "苹果供应链"]:
            if concept in candidates:
                candidates.remove(concept)
    if "美锦能源" in text:
        for concept in ["电容", "数据中心", "绿色低碳"]:
            if concept in candidates:
                candidates.remove(concept)
    if "魅视科技" in text:
        for concept in ["商业航天"]:
            if concept in candidates:
                candidates.remove(concept)
    if "南山控股" in text:
        for concept in ["制造业", "国企改革"]:
            if concept in candidates:
                candidates.remove(concept)
    if "欧晶科技" in text:
        for concept in ["半导体国产替代", "光伏产业链", "光伏产业", "硅材料", "半导体材料"]:
            if concept in candidates:
                candidates.remove(concept)
    if "颀中科技" in text:
        for concept in ["晶圆代工"]:
            if concept in candidates:
                candidates.remove(concept)
    if "三孚股份" in text:
        for concept in ["半导体材料", "光通信", "存储芯片", "AI算力", "800G_1.6T光模块"]:
            if concept in candidates:
                candidates.remove(concept)
        if "光纤预制棒" in body and "光纤光缆" in concepts and "光纤光缆" not in candidates:
            candidates.append("光纤光缆")
        if "硅烷偶联剂" in body and "硅烷偶联剂" in concepts and "硅烷偶联剂" not in candidates:
            candidates.append("硅烷偶联剂")
    if "三峡水利" in text:
        if "电力市场化" in body and "电力市场化" in concepts and "电力市场化" not in candidates:
            candidates.append("电力市场化")
    if "陕西黑猫" in text:
        for concept in ["绿色甲醇"]:
            if concept in candidates:
                candidates.remove(concept)
    if "陕西华达" in text:
        for concept in ["光模块", "低轨卫星"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("射频连接器" in body or "电连接器" in body) and "连接器" in concepts and "连接器" not in candidates:
            candidates.append("连接器")
        if "商业航天" in body and "商业航天" in concepts and "商业航天" not in candidates:
            candidates.append("商业航天")
    if "商络电子" in text:
        for concept in ["AI服务器", "IT分销", "AI存储", "机器人产业链", "人形机器人"]:
            if concept in candidates:
                candidates.remove(concept)
    if "上海电气" in text:
        for concept in ["新能源"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("AI数据中心" in body or "AIDC" in body) and "AIDC发电设备" in concepts and "AIDC发电设备" not in candidates:
            candidates.append("AIDC发电设备")
    if "上海临港" in text:
        for concept in ["人工智能", "生物医药", "房地产"]:
            if concept in candidates:
                candidates.remove(concept)
        if "园区" in body and "园区开发" in concepts and "园区开发" not in candidates:
            candidates.append("园区开发")
    if "尚太科技" in text:
        if ("快充" in body or "5C" in body or "10C" in body) and "快充技术" in concepts and "快充技术" not in candidates:
            candidates.append("快充技术")
    if "深南电路" in text:
        for concept in ["AIDC发电设备"]:
            if concept in candidates:
                candidates.remove(concept)
        if ("IC载板" in body or "ABF载板" in body or "BT载板" in body) and "IC载板" in concepts and "IC载板" not in candidates:
            candidates.append("IC载板")
    if "深南电A" in text:
        for concept in ["算电协同", "高阶HDI", "AI基础设施与国产算力", "AI算力"]:
            if concept in candidates:
                candidates.remove(concept)
        if "容量电价" in body and "容量电价" in concepts and "容量电价" not in candidates:
            candidates.append("容量电价")
    if "圣泉集团" in text:
        for concept in ["新能源材料", "快充技术"]:
            if concept in candidates:
                candidates.remove(concept)
    if "胜业电气" in text:
        for concept in ["SST", "变压器", "电容", "新能源", "家电出海", "AIDC发电设备", "储能系统"]:
            if concept in candidates:
                candidates.remove(concept)
    if "盛美上海" in text:
        for concept in ["半导体国产替代", "电镀", "HBM封装"]:
            if concept in candidates:
                candidates.remove(concept)
    if "石英股份" in text:
        for concept in ["半导体国产替代", "半导体材料", "AI算力", "石英砂", "光伏"]:
            if concept in candidates:
                candidates.remove(concept)
        if "半导体石英" in body and "半导体石英砂" in concepts and "半导体石英砂" not in candidates:
            candidates.append("半导体石英砂")
    if "实朴检测" in text:
        for concept in ["半导体量检测设备", "机器人", "AI机器人"]:
            if concept in candidates:
                candidates.remove(concept)
    if "实益达" in text:
        for concept in ["半导体封装", "AI算力", "机器人", "人形机器人"]:
            if concept in candidates:
                candidates.remove(concept)
    if "视觉中国" in text:
        for concept in ["Mini LED"]:
            if concept in candidates:
                candidates.remove(concept)
    if "首创环保" in text:
        for concept in ["AI智能体", "园区开发"]:
            if concept in candidates:
                candidates.remove(concept)
        if "环保" in concepts and "环保" not in candidates:
            candidates.append("环保")
    if "数码视讯" in text:
        if "超高清" in body and "8K超高清" in concepts and "8K超高清" not in candidates:
            candidates.append("8K超高清")
        if "AI Agent" in body and "AI智能体" in concepts and "AI智能体" not in candidates:
            candidates.append("AI智能体")
    if "双元科技" in text:
        for concept in ["半导体量检测设备"]:
            if concept in candidates:
                candidates.remove(concept)
        if "检测设备" in concepts and "检测设备" not in candidates:
            candidates.append("检测设备")
    if "太极实业" in text:
        for concept in ["半导体国产替代", "光伏"]:
            if concept in candidates:
                candidates.remove(concept)
    if "泰和新材" in text:
        for concept in ["AIDC发电设备", "AI数据中心储能", "商业航天"]:
            if concept in candidates:
                candidates.remove(concept)
        if "光纤光缆" in body and "光纤光缆" in concepts and "光纤光缆" not in candidates:
            candidates.append("光纤光缆")
    if "天华新能" in text:
        for concept in ["新能源车", "储能"]:
            if concept in candidates:
                candidates.remove(concept)
    if "天邑股份" in text:
        for concept in ["8K超高清"]:
            if concept in candidates:
                candidates.remove(concept)
        if "通信设备" in concepts and "通信设备" not in candidates:
            candidates.append("通信设备")
    if "通光线缆" in text:
        for concept in ["算力基建", "算电协同", "800G_1.6T光模块", "AIDC发电设备"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["光纤光缆", "G.654.E光纤"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "皖通高速" in text:
        for concept in ["红利资产"]:
            if concept in candidates:
                candidates.remove(concept)
    if "万马科技" in text:
        for concept in ["医疗信息化", "算力", "智算中心"]:
            if concept in candidates:
                candidates.remove(concept)
        if "模块化数据中心" in body and "模块化数据中心" in concepts and "模块化数据中心" not in candidates:
            candidates.append("模块化数据中心")
    if "沃格光电" in text:
        for concept in ["苹果供应链", "800G_1.6T光模块"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["TGV（玻璃通孔技术）", "CPI聚酰亚胺", "CPO"]:
            if concept in concepts and concept not in candidates and (concept in body or concept == "CPI聚酰亚胺" and "CPI薄膜" in body):
                candidates.append(concept)
    if "五洋自控" in text:
        for concept in ["储能", "储能系统"]:
            if concept in candidates:
                candidates.remove(concept)
    if "锡业股份" in text:
        for concept in ["资源回收"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["小金属", "战略金属"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "仙鹤股份" in text:
        for concept in ["AI算力", "AIDC发电设备", "电容"]:
            if concept in candidates:
                candidates.remove(concept)
    if "芯碁微装" in text:
        for concept in ["专用设备"]:
            if concept in candidates:
                candidates.remove(concept)
    if "新安股份" in text:
        for concept in ["AI算力", "AIDC发电设备", "人形机器人", "半导体材料", "快充技术"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["浸没式液冷", "液冷散热"]:
            if concept in concepts and concept not in candidates and ("液冷" in body or concept in body):
                candidates.append(concept)
    if "新金路" in text:
        for concept in ["半导体材料", "石英砂", "资源回收"]:
            if concept in candidates:
                candidates.remove(concept)
        if "氯碱化工" in candidates and "氯碱" in candidates:
            candidates.remove("氯碱")
        for concept in ["钽矿", "钽电容"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "信德新材" in text:
        for concept in ["负极材料"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "信音电子" in text:
        for concept in ["AI算力", "消费电子"]:
            if concept in candidates:
                candidates.remove(concept)
    if "星德胜" in text:
        for concept in ["人形机器人"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["工业电机"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "星网宇达" in text:
        for concept in ["东方财富", "特斯拉Optimus", "低轨卫星", "自动驾驶", "航天装备", "运营商", "石油"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工电子", "商业航天"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "兴蓉环境" in text:
        for concept in ["固废处理"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "雪峰科技" in text:
        for concept in ["煤炭", "化工"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "雅克科技" in text:
        for concept in ["AI算力", "半导体材料", "LNG"]:
            if concept in candidates:
                candidates.remove(concept)
    if "亿联网络" in text:
        for concept in ["海外产能"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "易普力" in text:
        for concept in ["化工"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "英力股份" in text:
        for concept in ["消费电子"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["海外产能"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "英特集团" in text:
        for concept in ["高股息红利"]:
            if concept in candidates:
                candidates.remove(concept)
    if "瑜欣电子" in text:
        for concept in ["新能源"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["工业电机"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "源杰科技" in text:
        for concept in ["AIDC发电设备"]:
            if concept in candidates:
                candidates.remove(concept)
    if "远东股份" in text:
        for concept in ["AIDC发电设备", "铜箔"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["光纤光缆", "光纤预制棒", "特种电缆"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "云汉芯城" in text:
        for concept in ["存储芯片"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "云意电气" in text:
        for concept in ["新能源", "具身智能"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["智能驾驶", "域控制器", "海外产能", "连接器"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "长飞光纤" in text:
        for concept in ["AIDC发电设备"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["光纤光缆", "海外产能"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "长光华芯" in text:
        for concept in ["EML激光器"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "长海股份" in text:
        for concept in ["AI算力", "建筑材料", "电子布", "聚酯", "苹果供应链", "AI服务器PCB", "玻璃纤维"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["风电叶片"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "长江通信" in text:
        for concept in ["快充技术", "海外产能"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["商业航天", "光纤光缆"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "长芯博创" in text:
        for concept in ["海外产能", "光通信"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "至纯科技" in text:
        for concept in ["AI算力", "半导体国产替代"]:
            if concept in candidates:
                candidates.remove(concept)
    if "致尚科技" in text:
        for concept in ["海外产能"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "中贝通信" in text:
        for concept in ["AIDC发电设备"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["5G"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "中电鑫龙" in text:
        for concept in ["AI算力", "智慧城市", "人工智能", "东方财富", "储能", "光伏", "家电出海", "储能系统"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["储能系统集成", "海外产能"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "中广核技" in text:
        for concept in ["医疗健康"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["新材料"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "中国核电" in text:
        for concept in ["可持续发展", "运营商", "核电设备", "电力行业", "家电出海"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["电力运营商", "高股息红利"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "中天科技" in text:
        for concept in ["新能源", "家电出海", "算力基建", "硅光", "光通信"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["光纤光缆", "光纤预制棒", "空芯光纤"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "中微公司" in text or "中微半导体设备" in text:
        for concept in ["半导体设备", "先进制程"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "中原高速" in text:
        for concept in ["新能源"]:
            if concept in candidates:
                candidates.remove(concept)
    if "紫光国微" in text:
        for concept in ["SiC", "碳化硅", "苹果供应链", "AI存储"]:
            if concept in candidates:
                candidates.remove(concept)
    if "亚威股份" in text:
        for concept in ["人形机器人", "HBM", "存储芯片", "AI算力"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["工业机器人", "海外产能"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "屹唐股份" in text:
        for concept in ["三星"]:
            if concept in candidates:
                candidates.remove(concept)
    if "园林股份" in text:
        for concept in ["存储芯片", "云计算", "DRAM", "3D NAND", "AI存储"]:
            if concept in candidates:
                candidates.remove(concept)
    if "正帆科技" in text:
        for concept in ["光通信", "800G_1.6T光模块", "高纯石英砂"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["半导体设备材料"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "天银机电" in text:
        for concept in ["家电出海"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["商业航天", "军工电子"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "王子新材" in text:
        for concept in ["电容", "储能系统"]:
            if concept in candidates:
                candidates.remove(concept)
    if "西测测试" in text:
        for concept in ["商业航天", "军工电子", "第三方检测"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "信宇人" in text:
        for concept in ["MiniLED", "人形机器人", "园区开发"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["钙钛矿"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "北斗星通" in text:
        for concept in ["卫星", "晶圆代工"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工电子"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "东土科技" in text:
        for concept in ["半导体设备", "刻蚀设备", "控制器"]:
            if concept in candidates:
                candidates.remove(concept)
    if "格尔软件" in text:
        for concept in ["大模型"]:
            if concept in candidates:
                candidates.remove(concept)
    if "国博电子" in text:
        for concept in ["园区开发"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["商业航天"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "利尔达" in text:
        for concept in ["物联网", "星闪技术"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "六九一二" in text:
        for concept in ["军工装备", "军工电子", "存储芯片"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "润欣科技" in text:
        for concept in ["AI智能体"]:
            if concept in candidates:
                candidates.remove(concept)
    if "上海贝岭" in text:
        for concept in ["半导体材料", "晶圆代工", "AIDC发电设备"]:
            if concept in candidates:
                candidates.remove(concept)
    if "深科达" in text:
        for concept in ["专用设备", "AI基础设施与国产算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "神工股份" in text:
        for concept in ["半导体国产替代", "AI算力", "硅片", "刻蚀设备", "3D NAND"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["半导体硅片"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "盛视科技" in text:
        for concept in ["大模型", "算力", "量测设备", "AIDC发电设备"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["算力租赁"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "四川长虹" in text:
        for concept in ["AI服务器", "华为昇腾"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "泰豪科技" in text:
        for concept in ["快充技术"]:
            if concept in candidates:
                candidates.remove(concept)
    if "天奥电子" in text:
        for concept in ["北斗导航"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "富士达" in text:
        for concept in ["量子计算"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工电子"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "国泰集团" in text:
        for concept in ["AI服务器", "电容"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["钽矿", "稀有金属", "军工装备"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "启明星辰" in text:
        for concept in ["AI智能体"]:
            if concept in candidates:
                candidates.remove(concept)
    if "天和防务" in text:
        for concept in ["大模型"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工电子", "军工装备", "射频芯片"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "矽电股份" in text:
        for concept in ["Micro LED", "Mini LED", "CPO", "硅光", "存储芯片", "半导体国产替代"]:
            if concept in candidates:
                candidates.remove(concept)
    if "有方科技" in text:
        for concept in ["AI存储", "算力租赁"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["物联网"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "百傲化学" in text:
        for concept in ["存储芯片", "3D NAND"]:
            if concept in candidates:
                candidates.remove(concept)
    if "成都华微" in text:
        for concept in ["AI算力"]:
            if concept in candidates:
                candidates.remove(concept)
    if "诚邦股份" in text:
        for concept in ["高速互联", "DDR5", "AI存储"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["存储芯片"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "淳中科技" in text:
        for concept in ["AI算力"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["AI散热"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "大港股份" in text:
        for concept in ["半导体国产替代", "AI芯片", "FPGA", "车规芯片", "TSV"]:
            if concept in candidates:
                candidates.remove(concept)
    if "大华股份" in text:
        for concept in ["大模型", "园区开发"]:
            if concept in candidates:
                candidates.remove(concept)
    if "德邦科技" in text:
        for concept in ["苹果供应链"]:
            if concept in candidates:
                candidates.remove(concept)
    if "东方中科" in text:
        for concept in ["新能源汽车", "脑机接口", "量子科技", "大模型", "鸿蒙"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["信息安全"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "古鳌科技" in text:
        for concept in ["AI芯片", "GPU", "算力", "晶圆代工"]:
            if concept in candidates:
                candidates.remove(concept)
    if "广立微" in text:
        for concept in ["DRAM", "CPO", "3D NAND"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["EDA（电子设计自动化）", "半导体软件"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "国林科技" in text:
        for concept in ["半导体国产替代", "光刻胶", "3D NAND", "晶圆代工"]:
            if concept in candidates:
                candidates.remove(concept)
    if "航宇微" in text:
        for concept in ["算力"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["商业航天", "低轨卫星"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "恒坤新材" in text:
        for concept in ["半导体国产替代", "存储芯片", "DRAM", "3D NAND"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["电子化学品"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "华新科技" in text:
        for concept in ["AI服务器", "AI存储"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["资源回收"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "捷成股份" in text:
        for concept in ["AI智能体"]:
            if concept in candidates:
                candidates.remove(concept)
    if "金宏气体" in text:
        for concept in ["半导体材料", "存储芯片"]:
            if concept in candidates:
                candidates.remove(concept)
    if "京仪装备" in text:
        for concept in ["先进制程", "刻蚀设备", "3D NAND"]:
            if concept in candidates:
                candidates.remove(concept)
    if "晶升股份" in text:
        for concept in ["CoWoS", "先进封装", "并购重组", "SiC", "碳化硅"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["半导体设备", "SiC碳化硅", "第三代半导体"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "康强电子" in text:
        for concept in ["AI芯片", "算力", "DRAM", "3D NAND", "AI存储", "硅光"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["封测"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "蓝箭电子" in text:
        for concept in ["半导体涨价", "存储芯片", "并购重组"]:
            if concept in candidates:
                candidates.remove(concept)
    if "杭氧股份" in text:
        for concept in ["管道"]:
            if concept in candidates:
                candidates.remove(concept)
    if "正元地信" in text:
        for concept in ["卫星", "园区开发"]:
            if concept in candidates:
                candidates.remove(concept)
    if "中国海防" in text:
        for concept in ["智慧城市", "油气", "商业航天"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["深海科技", "军工电子", "军工装备"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "七一二" in text:
        for concept in ["轨道交通"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工信息化", "军工电子", "低空经济"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "榕基软件" in text:
        for concept in ["园区开发", "AI基础设施与国产算力"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["行业应用软件"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "三维天地" in text:
        for concept in ["资产管理"]:
            if concept in candidates:
                candidates.remove(concept)
    if "太极股份" in text:
        for concept in ["大模型"]:
            if concept in candidates:
                candidates.remove(concept)
    if "天微电子" in text:
        for concept in ["人工智能", "并购重组"]:
            if concept in candidates:
                candidates.remove(concept)
    if "永信至诚" in text:
        for concept in ["卫星互联网", "低空经济", "大模型"]:
            if concept in candidates:
                candidates.remove(concept)
    if "尤洛卡" in text:
        for concept in ["低空经济"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工装备", "特种机器人"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "展鹏科技" in text:
        for concept in ["AI大模型", "专用设备", "操作系统", "大模型"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工装备"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "航天南湖" in text:
        for concept in ["商业航天"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工装备", "军工电子"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "航天长峰" in text:
        for concept in ["商业航天"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工装备"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "霍莱沃" in text:
        for concept in ["量测设备"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工电子"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "吉大通信" in text:
        for concept in ["通信服务", "行业应用软件", "数字化转型"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "佳讯飞鸿" in text:
        for concept in ["大模型"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["AI大模型", "通信设备", "低空经济", "军工信息化"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "建设工业" in text:
        for concept in ["新能源汽车", "低空经济", "钛合金"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工装备"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "科思科技" in text:
        for concept in ["低空经济", "AI基础设施与国产算力"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工信息化", "军工电子", "AI算力芯片", "机器人与具身智能装备"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "诺唯赞" in text:
        for concept in ["医药出海"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "谱尼测试" in text:
        for concept in ["快充技术", "人形机器人"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["机器人"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "邦彦技术" in text:
        for concept in ["园区开发"]:
            if concept in candidates:
                candidates.remove(concept)
    if "成电光信" in text:
        for concept in ["商业航天"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工信息化"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "高凌信息" in text:
        for concept in ["信息安全", "网络安全", "军工信息化"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if "国睿科技" in text:
        for concept in ["快充技术"]:
            if concept in candidates:
                candidates.remove(concept)
        for concept in ["军工装备"]:
            if concept in concepts and concept not in candidates:
                candidates.append(concept)
    if any(concept in candidates for concept in ["电子特气", "前驱体材料", "高纯石英砂", "碳化硅"]) and "专用设备" in candidates:
        candidates.remove("专用设备")
    if any(concept in candidates for concept in ["电子特气", "前驱体材料", "高纯石英砂", "碳化硅"]) and "半导体设备" in candidates:
        candidates.remove("半导体设备")
    if "AI光互联核心供应商" in body:
        for concept in ["新能源汽车", "3D打印"]:
            if concept in candidates:
                candidates.remove(concept)
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


def unique_values(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        value = str(item or "").strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def get_section(sections: dict[str, str], title: str) -> str:
    if title in sections:
        return sections[title]
    for section_title, section_text in sections.items():
        normalized_title = normalize_section_title(section_title)
        if normalized_title.startswith(title) or title in normalized_title:
            return section_text
    return ""


def normalize_section_title(title: str) -> str:
    return re.sub(r"^(?:\d+|[一二三四五六七八九十]+)[\.、]\s*", "", title).strip()


def concept_focus_tokens(concept: str) -> tuple[str, ...]:
    concept = str(concept or "").strip()
    profiles = {
        "存储芯片": ("存储", "SDBG", "晶圆隐切", "隐切", "划片", "DRAM", "NAND", "3D NAND", "HBM", "SSD", "长江存储", "长鑫存储", "DISCO", "硅晶圆", "存储厂商"),
        "DRAM": ("DRAM", "长鑫存储", "存储", "SDBG", "晶圆隐切", "DISCO"),
        "3D NAND": ("3D NAND", "NAND", "长江存储", "存储", "SDBG", "晶圆隐切", "DISCO"),
        "NAND Flash": ("NAND", "Flash", "闪存", "存储"),
        "NOR Flash": ("NOR", "Flash", "闪存", "存储"),
        "HBM": ("HBM", "高带宽内存", "先进封装", "TSV", "混合键合"),
        "HBM封装": ("HBM", "封装", "TSV", "混合键合", "先进封装"),
        "半导体设备": ("半导体", "设备", "晶圆", "SDBG", "隐切", "划片", "刻蚀", "薄膜", "量测", "检测", "国产替代", "DISCO"),
        "先进封装": ("先进封装", "封装", "FC-BGA", "TGV", "玻璃通孔", "键合", "晶圆级", "硅光芯片键合"),
        "封测": ("封测", "封装", "测试", "晶圆级"),
        "固态电池": ("固态电池", "电池", "锂电", "宁德时代", "清陶", "新能源"),
        "光通信": ("光通信", "光模块", "CPO", "硅光", "InP", "Finisar", "中际旭创", "天孚通信"),
        "CPO": ("CPO", "硅光", "光模块", "光通信", "封装"),
        "硅光": ("硅光", "光通信", "光模块", "CPO", "键合"),
        "TGV（玻璃通孔技术）": ("TGV", "玻璃通孔", "玻璃基板"),
        "TGV": ("TGV", "玻璃通孔", "玻璃基板"),
        "PCB": ("PCB", "钻孔", "激光钻孔", "高端PCB"),
        "AI算力": ("AI算力", "光通信", "光模块", "PCB", "服务器"),
    }
    tokens = list(profiles.get(concept, ()))
    tokens.extend(split_display_chunks(concept, separators=" /_-（）()"))
    return tuple(unique_values([token for token in tokens if len(token) >= 2]))


def concept_focused_role(meta: dict[str, Any], concept: str) -> str:
    chunks = []
    for value in as_list(meta.get("related_business")):
        chunks.extend(split_display_chunks(value))
    if not chunks:
        chunks = as_list(meta.get("industry")) + as_list(meta.get("sector"))
    tokens = concept_focus_tokens(concept)
    focused = [chunk for chunk in chunks if any(token and token in chunk for token in tokens)]
    if not focused and concept in {"存储芯片", "DRAM", "3D NAND"}:
        focused = [chunk for chunk in chunks if any(token in chunk for token in ("晶圆隐切", "SDBG", "半导体", "晶圆"))]
    return "、".join(unique_values(focused or chunks)[:3])


def clean_evidence_line(line: str) -> str:
    value = str(line or "").strip()
    if not value or value.startswith("|---") or set(value) <= {"|", "-", ":", " "}:
        return ""
    if value.startswith("|") and value.endswith("|"):
        cells = [re.sub(r"\*\*|`", "", cell).strip() for cell in value.strip("|").split("|")]
        cells = [cell for cell in cells if cell and cell not in {"维度", "内容", "变化", "之前状态", "最新变化", "日期", "来源类型", "对应业务", "IMA可信度", "是否影响财务", "证据点", "来源类型", "要点"}]
        value = "；".join(cells)
    value = re.sub(r"^[#>\-\*\s]+", "", value)
    value = re.sub(r"\*\*|`", "", value)
    return compact(value, 260)


def concept_relevant_lines(body: str, concept: str, max_lines: int = 4) -> list[str]:
    tokens = concept_focus_tokens(concept)
    sections = section_map(body)
    preferred_titles = ("最新市场逻辑", "Hard Delta", "证据与来源链", "业务验证矩阵", "财务映射", "预期差判断", "后续跟踪指标", "反证与风险")
    chunks = []
    for title in preferred_titles:
        value = get_section(sections, title)
        if value:
            chunks.append(value)
    chunks.append(body[:8000])
    lines = []
    for chunk in chunks:
        for raw in chunk.splitlines():
            line = clean_evidence_line(raw)
            if not line:
                continue
            if any(token and token in line for token in tokens):
                lines.append(line)
            if len(unique_values(lines)) >= max_lines:
                return unique_values(lines)[:max_lines]
    return unique_values(lines)[:max_lines]


def concept_focused_evidence(meta: dict[str, Any], body: str, concept: str) -> str:
    lines = concept_relevant_lines(body, concept, max_lines=3)
    if lines:
        return compact("；".join(lines), 300)
    sections = section_map(body)
    one = extract_one_liner(sections) or f"IMA个股逻辑卡：{normalize_entity_name(meta, body)} 最新逻辑跟踪"
    return compact(one, 260)


def concept_validation_focus(body: str, concept: str) -> str:
    lines = concept_relevant_lines(get_section(section_map(body), "后续跟踪指标") or body, concept, max_lines=3)
    if not lines:
        lines = concept_relevant_lines(get_section(section_map(body), "业务验证矩阵") or body, concept, max_lines=2)
    return compact("；".join(lines), 240)


def concept_guardrail(body: str, concept: str) -> str:
    tokens = concept_focus_tokens(concept)
    sections = section_map(body)
    candidates = []
    for title in ("反证与风险", "风险提示", "主要风险", "关键风险点", "预期差判断", "财务映射"):
        value = get_section(sections, title)
        if value:
            candidates.extend(clean_evidence_line(line) for line in value.splitlines())
    focused = [line for line in candidates if line and any(token and token in line for token in tokens)]
    if not focused:
        focused = [line for line in candidates if line and any(token in line for token in ("未披露", "小批量", "未进入", "待确认", "推断", "收入占比", "亏损", "存货", "延期", "终止"))]
    return compact("；".join(unique_values(focused)[:3]), 240)


def chain_layer_for_concept(meta: dict[str, Any], concept: str, role: str) -> str:
    text = f"{concept} {role} {' '.join(as_list(meta.get('industry')))} {' '.join(as_list(meta.get('sector')))}"
    if any(token in text for token in ("设备", "装备", "SDBG", "隐切", "划片", "刻蚀", "量测", "检测", "测试机", "探针台")):
        return "upstream_equipment"
    if any(token in text for token in ("材料", "特气", "前驱体", "CMP", "光刻胶", "靶材", "抛光")):
        return "upstream_materials"
    if any(token in text for token in ("封测", "封装", "测试")):
        return "midstream_packaging_testing"
    if any(token in text for token in ("设计", "芯片", "DRAM", "NAND", "NOR", "HBM", "SSD", "MCU", "ASIC")):
        return "core_chip_product"
    if any(token in text for token in ("分销", "渠道", "代理", "经销")):
        return "downstream_channel"
    return str(meta.get("industry") or meta.get("sector") or "")


def fact_hardness_for_concept(evidence: str, guardrail: str) -> str:
    text = f"{evidence} {guardrail}"
    if any(token in text for token in ("公司官方", "公司公告", "年报", "一季报", "官网", "量产订单", "通过客户", "通过客户端", "客户验证")):
        if any(token in text for token in ("待确认", "推断", "未披露", "小批量", "尚未", "未进入")):
            return "ima_hard_delta_review"
        return "ima_hard_delta"
    if any(token in text for token in ("待确认", "推断", "社区", "雪球", "东方财富")):
        return "ima_composite_review"
    return "ima_composite"


def review_required_for_concept(evidence: str, guardrail: str, confidence: str) -> bool:
    text = f"{evidence} {guardrail}"
    if confidence == "low":
        return True
    return any(token in text for token in ("待确认", "推断", "未披露", "小批量", "尚未", "未进入", "收入占比较小", "社区预期", "亏损", "存货高企", "延期", "终止"))


def strength_for_concept(meta: dict[str, Any], concept: str, role: str, evidence: str, review_required: bool) -> str:
    themes = set(as_list(meta.get("themes")))
    text = f"{concept} {role} {evidence}"
    if review_required:
        return "related"
    if concept in themes and any(token in text for token in ("主营", "核心", "量产", "订单", "收入", "客户验证", "供货", "唯一")):
        return "core"
    if concept in themes:
        return "related"
    return "related"


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
    if logic == "- 待补":
        logic = take_section(sections, "核心逻辑", 60)
    if logic == "- 待补":
        logic = take_section(sections, "核心市场逻辑", 60)
    hard_delta = take_section(sections, "Hard Delta", 20)
    if hard_delta == "- 待补":
        hard_delta = take_section(sections, "最新业绩摘要", 20)
    if hard_delta == "- 待补":
        hard_delta = take_section(sections, "财务数据概览", 20)
    if hard_delta == "- 待补":
        hard_delta = take_section(sections, "最新财务数据", 20)
    risks = take_section(sections, "反证与风险", 14)
    if risks == "- 待补":
        risks = take_section(sections, "反证信号", 14)
    if risks == "- 待补":
        risks = take_section(sections, "风险提示", 14)
    if risks == "- 待补":
        risks = take_section(sections, "主要风险", 14)
    if risks == "- 待补":
        risks = take_section(sections, "关键风险点", 14)
    tracking = take_section(sections, "后续跟踪指标", 16)
    if tracking == "- 待补":
        tracking = take_section(sections, "关键跟踪指标", 16)
    if tracking == "- 待补":
        tracking = take_section(sections, "催化剂与未来展望", 16)
    if tracking == "- 待补":
        tracking = take_section(sections, "机构预测", 16)
    if tracking == "- 待补":
        tracking = take_section(sections, "重要时间节点", 16)
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
    if isinstance(entity["concepts"], list):
        entity["concepts"] = {
            concept: {
                "sources": [],
                "updated": now_date(),
            }
            for concept in entity["concepts"]
        }
    confidence = confidence_from_meta(meta)
    evidence_layer = evidence_layer_from_meta(meta)
    source_link = wikilink(source_name)
    inserted_concepts = []
    updated_concepts = []
    for concept in concepts:
        role = concept_focused_role(meta, concept) or "、".join(as_list(meta.get("related_business"))[:4]) or str(meta.get("sector") or meta.get("industry") or "")
        focused_evidence = concept_focused_evidence(meta, body, concept)
        guardrail = concept_guardrail(body, concept)
        validation_focus = concept_validation_focus(body, concept)
        review_required = review_required_for_concept(focused_evidence, guardrail, confidence)
        fact_hardness = fact_hardness_for_concept(focused_evidence, guardrail)
        new_fields = {
            "business_line": role,
            "chain_layer": chain_layer_for_concept(meta, concept, role),
            "confidence": confidence,
            "evidence": compact(focused_evidence, 300),
            "evidence_layer": evidence_layer,
            "role": role,
            "sources": [source_link],
            "strength": strength_for_concept(meta, concept, role, focused_evidence, review_required),
            "update_type": "ima_stock_logic",
            "updated": now_date(),
            "fact_hardness": fact_hardness,
            "review_required": review_required,
            "source_quality": "ima_composite",
            "ima_confidence": meta.get("ima_confidence") or meta.get("evidence_strength") or "IMA综合可信",
            "logic_stage": meta.get("logic_stage") or "",
            "financial_validation": meta.get("financial_validation") or "",
            "validation_focus": validation_focus,
            "guardrail": guardrail,
        }
        existing = entity["concepts"].get(concept)
        if existing:
            sources = list(existing.get("sources", [])) if isinstance(existing.get("sources"), list) else []
            had_source = source_link in sources
            if source_link not in sources:
                sources.append(source_link)
            existing["sources"] = sources
            existing["updated"] = now_date()
            for key in ["ima_confidence", "logic_stage", "financial_validation", "validation_focus", "guardrail", "business_line"]:
                if new_fields.get(key):
                    existing[key] = new_fields[key]
            should_refresh = had_source or existing.get("update_type") == "ima_stock_logic" or not existing.get("role") or not existing.get("evidence")
            if should_refresh:
                for key in ["role", "evidence", "chain_layer", "confidence", "evidence_layer", "strength", "update_type", "fact_hardness", "review_required", "source_quality"]:
                    if key in new_fields:
                        existing[key] = new_fields[key]
            updated_concepts.append(concept)
        else:
            entity["concepts"][concept] = new_fields
            inserted_concepts.append(concept)
    items = evidence.setdefault("items", [])
    existing_by_key = {evidence_key(item): item for item in items if isinstance(item, dict)}
    inserted_evidence = []
    updated_evidence = []
    for concept in concepts:
        role = concept_focused_role(meta, concept) or "、".join(as_list(meta.get("related_business"))[:4]) or str(meta.get("sector") or meta.get("industry") or "")
        focused_evidence = concept_focused_evidence(meta, body, concept)
        guardrail = concept_guardrail(body, concept)
        validation_focus = concept_validation_focus(body, concept)
        review_required = review_required_for_concept(focused_evidence, guardrail, confidence)
        fact_hardness = fact_hardness_for_concept(focused_evidence, guardrail)
        item = {
            "source": source_link,
            "source_date": str(meta.get("updated") or now_date()),
            "target_type": "entity",
            "target": entity_name,
            "concept": concept,
            "evidence": compact(focused_evidence, 300),
            "confidence": confidence,
            "chain_layer": chain_layer_for_concept(meta, concept, role),
            "evidence_layer": evidence_layer,
            "update_type": "ima_stock_logic",
            "fact_hardness": fact_hardness,
            "source_quality": "ima_composite",
            "review_required": review_required,
            "role": role,
            "business_line": role,
            "validation_focus": validation_focus,
            "guardrail": guardrail,
        }
        key = evidence_key(item)
        if key not in existing_by_key:
            items.append(item)
            existing_by_key[key] = item
            inserted_evidence.append(key)
        else:
            target_item = existing_by_key[key]
            changed = False
            for field, value in item.items():
                if value and target_item.get(field) != value:
                    target_item[field] = value
                    changed = True
            if changed:
                updated_evidence.append(key)
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
        "updated_evidence": updated_evidence,
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
    ticker = normalize_ticker(meta.get("ticker") or meta.get("code") or first_h1(body)) or known_ticker_for_entity(entity_name)
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

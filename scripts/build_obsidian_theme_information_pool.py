#!/usr/bin/env python3
"""
Build a neutral theme information pool from an Obsidian vault.

This is a read-only scanner. It does not modify the vault, entities, relations,
or knowledge-base files. It keeps matching information snippets and marks broad
snippets with lower specificity/display weight rather than filtering them out.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_KEYWORDS = [
    "光模块", "CPO", "NPO", "硅光", "800G", "1.6T", "3.2T", "LPO",
    "光芯片", "EML", "CW激光器", "光隔离器", "法拉第", "MPO", "FAU",
    "AWG", "OCS", "DCI", "相干光模块", "液冷IO", "耦合设备", "光引擎",
    "磷化铟", "InP", "陶瓷基板", "DSP", "DFP",
]

SKIP_DIRS = {".obsidian", ".git", "node_modules", "__pycache__", "archive", "source-backups", "auto-hbs-rollback"}
SKIP_FILES = {"AGENTS.md", "CLAUDE.md", "log.md", "index.md"}
SKIP_PATH_KEYWORDS = {"theme-radar-验收", "theme-radar/regression"}

SEGMENT_RULES = [
    ("上游-光芯片", ["光芯片", "EML", "CW激光器", "DFB", "VCSEL", "磷化铟", "InP"]),
    ("上游-光器件/材料", ["光隔离器", "法拉第", "MPO", "FAU", "AWG", "陶瓷基板"]),
    ("中游-光模块/CPO", ["光模块", "800G", "1.6T", "3.2T", "CPO", "NPO", "LPO", "光引擎"]),
    ("中游-OCS/DCI", ["OCS", "DCI", "相干光模块"]),
    ("配套-设备/测试", ["耦合设备", "贴片", "AOI", "测试设备", "固晶", "共晶"]),
    ("下游-算力/云厂商", ["英伟达", "谷歌", "Meta", "AWS", "微软", "华为", "TPU", "GPU"]),
]

COMPANY_TICKERS = {
    "中际旭创": "300308", "新易盛": "300502", "天孚通信": "300394", "光迅科技": "002281",
    "华工科技": "000988", "剑桥科技": "603083", "德科立": "688205", "源杰科技": "688498",
    "仕佳光子": "688313", "长光华芯": "688048", "永鼎股份": "600105", "福晶科技": "002222",
    "东田微": "300516", "中瓷电子": "003031", "博创科技": "300548", "太辰光": "300570",
    "鼎通科技": "688688", "奕东电子": "301123", "光库科技": "300620", "腾景科技": "688195",
    "罗博特科": "300757", "科瑞技术": "002957", "联特科技": "301205", "汇绿生态": "001267",
    "东山精密": "002384", "可川科技": "603052", "奥特维": "688516", "华盛昌": "002980",
    "普源精电": "688337", "快克智能": "603203", "唯特偶": "301319", "博众精工": "688097",
    "凯格精机": "301338",
}


def sha_id(*parts: str) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def iter_md_files(root: Path):
    for p in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name in SKIP_FILES:
            continue
        rel = str(p.relative_to(root))
        if any(k in rel for k in SKIP_PATH_KEYWORDS):
            continue
        yield p


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def line_blocks(text: str, keywords: list[str], window: int = 1):
    lines = text.splitlines()
    seen = set()
    for idx, line in enumerate(lines):
        hits = [k for k in keywords if k in line]
        if not hits:
            continue
        start = max(0, idx - window)
        end = min(len(lines), idx + window + 1)
        key = (start, end)
        if key in seen:
            continue
        seen.add(key)
        snippet = normalize_text("\n".join(lines[start:end]))
        heading = nearest_heading(lines, idx)
        yield idx + 1, heading, hits, snippet


def nearest_heading(lines: list[str], idx: int) -> str:
    for j in range(idx, -1, -1):
        if lines[j].lstrip().startswith("#"):
            return lines[j].lstrip("#").strip()
    return ""


def infer_segment(text: str) -> str:
    for segment, keys in SEGMENT_RULES:
        if any(k in text for k in keys):
            return segment
    return "未分段"


def infer_info_types(text: str) -> list[str]:
    types = []
    if re.search(r"涨价|缺口|紧缺|放量|上修|扩产|产能|同比|增长|提升|送样|量产|订单|份额|毛利率|营收|净利", text):
        types.append("marginal_change")
    if re.search(r"供应|客户|合作|绑定|进入.*链|供货|采购|代工|收购", text):
        types.append("relationship")
    if re.search(r"需求|市场空间|路线|产业链|格局|替代|国产化|迭代", text):
        types.append("theme_driver")
    if not types:
        types.append("segment_mapping")
    return types


def infer_specificity(text: str, companies: list[str]) -> str:
    score = 0
    if companies:
        score += 2
    if re.search(r"\d", text):
        score += 2
    if re.search(r"量产|送样|订单|产能|份额|涨价|同比|毛利率|营收|净利|客户|供应链|收购|扩产", text):
        score += 2
    if len(text) >= 80:
        score += 1
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def detect_companies(text: str) -> list[str]:
    return [name for name in COMPANY_TICKERS if name in text]


def display_weight(specificity: str) -> str:
    return "low" if specificity == "low" else "normal"


def build_item(theme: str, vault: Path, path: Path, line_no: int, heading: str, hits: list[str], snippet: str):
    rel = str(path.relative_to(vault))
    companies = detect_companies(snippet + " " + path.stem)
    entity = companies[0] if companies else ""
    if not entity and "/concepts/" in f"/{rel}":
        entity = path.stem
    ticker = COMPANY_TICKERS.get(entity, "")
    segment = infer_segment(snippet + " " + path.name)
    info_types = infer_info_types(snippet)
    specificity = infer_specificity(snippet, companies)
    return {
        "item_id": sha_id(theme, rel, line_no, snippet),
        "theme": theme,
        "entity_name": entity,
        "ticker": ticker,
        "chain_position": segment,
        "segment": segment,
        "component": ",".join(hits),
        "claim": snippet,
        "info_types": info_types,
        "primary_info_type": info_types[0],
        "specificity": specificity,
        "display_weight": display_weight(specificity),
        "source_systems": ["Obsidian"],
        "source_refs": [{
            "system": "Obsidian",
            "path": str(path),
            "relative_path": rel,
            "section": heading,
            "line_no": line_no,
            "matched_keywords": hits,
        }],
        "source_title": path.stem,
        "source_type": "Obsidian笔记",
        "source_date": "",
        "confidence_raw": "",
        "confidence": "unknown",
        "needs_review_raw": "",
        "needs_review": None,
        "source_record_type": "obsidian_snippet",
        "matched_keywords": hits,
    }


def build_outputs(vault: Path, theme: str, keywords: list[str], max_items: int):
    items = []
    sources = []
    matched_docs = 0
    keyword_counter = Counter()
    doc_hit_counter = defaultdict(int)

    for path in iter_md_files(vault):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not any(k in text or k in path.name for k in keywords):
            continue
        matched_docs += 1
        rel = str(path.relative_to(vault))
        sources.append({
            "source_id": sha_id(theme, rel),
            "theme": theme,
            "source_system": "Obsidian",
            "source_title": path.stem,
            "source_type": "Obsidian笔记",
            "source_ref": str(path),
            "relative_path": rel,
            "matched_keywords": [k for k in keywords if k in text or k in path.name],
        })
        for line_no, heading, hits, snippet in line_blocks(text, keywords):
            keyword_counter.update(hits)
            doc_hit_counter[rel] += 1
            items.append(build_item(theme, vault, path, line_no, heading, hits, snippet))
            if max_items and len(items) >= max_items:
                break
        if max_items and len(items) >= max_items:
            break

    summary = {
        "theme": theme,
        "vault": str(vault),
        "matched_doc_count": matched_docs,
        "item_count": len(items),
        "source_count": len(sources),
        "items_by_specificity": dict(Counter(i["specificity"] for i in items)),
        "items_by_primary_info_type": dict(Counter(i["primary_info_type"] for i in items)),
        "items_by_display_weight": dict(Counter(i["display_weight"] for i in items)),
        "top_keywords": dict(keyword_counter.most_common(30)),
        "top_docs": dict(Counter(doc_hit_counter).most_common(30)),
        "safety_statement": "Read-only Obsidian theme information pool. No vault or knowledge-base writeback.",
    }
    return {"summary": summary, "items": items, "sources": sources}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Obsidian theme information pool")
    parser.add_argument("vault")
    parser.add_argument("--theme", default="光模块")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--max-items", type=int, default=500)
    parser.add_argument("--keywords", default=", ".join(DEFAULT_KEYWORDS))
    args = parser.parse_args()

    vault = Path(args.vault).expanduser()
    if not vault.exists():
        print(f"[ERR] vault not found: {vault}", file=sys.stderr)
        return 1
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    outputs = build_outputs(vault, args.theme, keywords, args.max_items)
    print(json.dumps(outputs["summary"], ensure_ascii=False, indent=2))

    if args.out_dir:
        out = Path(args.out_dir).expanduser()
        prefix = f"{args.theme}_obsidian"
        write_jsonl(out / f"{prefix}.theme_information_items.jsonl", outputs["items"])
        write_jsonl(out / f"{prefix}.source_registry.jsonl", outputs["sources"])
        write_json(out / f"{prefix}.summary.json", outputs["summary"])
        print(f"[OK] wrote outputs: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

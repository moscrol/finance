#!/usr/bin/env python3
from __future__ import annotations
"""Render a Markdown preview report from unified theme information JSONL."""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import re

try:
    from build_obsidian_theme_information_pool import COMPANY_TICKERS
except Exception:
    COMPANY_TICKERS = {}

STRONG_SIGNAL_TOKENS = (
    "订单", "客户", "供应商", "独供", "份额", "市占率", "量产", "放量", "出货", "交付",
    "验证", "送样", "认证", "导入", "投产", "扩产", "产能", "收入", "营收", "净利",
    "同比", "环比", "良率", "成本", "价值量", "涨价", "替代", "突破", "小批量",
)
CHAIN_SIGNAL_TOKENS = (
    "上游", "中游", "下游", "光芯片", "光器件", "光模块", "CPO", "OCS", "DCI",
    "硅光", "EML", "CW", "InP", "磷化铟", "法拉第", "隔离器", "耦合", "测试",
    "设备", "云厂商", "数据中心", "英伟达", "谷歌", "微软", "Meta",
)
WEAK_NOISE_TOKENS = (
    "建议关注", "有望受益", "前景广阔", "行业空间广阔", "长期看好", "概念", "题材",
    "建议给予", "买入评级", "重点推荐标的", "graph_only", "keep_in_high_confidence_review_sources",
    "aliases:", "tags:", "entity_type:", "revision:", "sources:",
)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def rank_specificity(v: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(v or "", 0)


def zh_specificity(v: str) -> str:
    return {"high": "高", "medium": "中", "low": "低"}.get(v or "", v or "")


def source_label(row: dict) -> str:
    systems = row.get("source_systems") or []
    if len(set(systems)) > 1:
        return "多源"
    return systems[0] if systems else "未知"


def row_text(row: dict) -> str:
    return " ".join(
        str(x or "")
        for x in [
            row.get("entity_name"),
            row.get("ticker"),
            row.get("segment"),
            row.get("chain_position"),
            row.get("claim"),
            row.get("source_title"),
        ]
    )


def hit_count(text: str, tokens: tuple[str, ...]) -> int:
    return sum(1 for token in tokens if token and token in text)


def first_company_hit(text: str) -> str:
    hits = []
    for name, code in COMPANY_TICKERS.items():
        positions = [p for p in (text.find(name), text.find(code)) if p >= 0]
        if positions:
            hits.append((min(positions), name))
    return min(hits)[1] if hits else ""


def radar_score(row: dict) -> int:
    text = row_text(row)
    claim = str(row.get("claim") or "")
    entity = str(row.get("entity_name") or "")
    ticker = str(row.get("ticker") or "")
    types = set(row.get("info_types") or [row.get("primary_info_type")])
    score = {"high": 8, "medium": 4, "low": 0}.get(row.get("specificity") or "", 0)
    score += min(4, len(row.get("source_refs") or []))
    if source_label(row) == "多源":
        score += 5
    if row.get("entity_name"):
        score += 3
    if row.get("ticker"):
        score += 2
    if entity and entity in claim:
        score += 5
    if ticker and ticker in claim:
        score += 3
    first_company = first_company_hit(claim)
    if first_company and entity and first_company == entity:
        score += 10
    elif first_company and entity and first_company != entity:
        score -= 20
    if "marginal_change" in types:
        score += 6
    if "relationship" in types:
        score += 7
    if "theme_driver" in types:
        score += 3
    if "segment_mapping" in types:
        score += 8
    if row.get("segment") and row.get("segment") not in ("未分段", "中游-光模块/CPO", "上游-光芯片"):
        score += 4
    score += min(12, hit_count(text, STRONG_SIGNAL_TOKENS) * 2)
    score += min(6, hit_count(text, CHAIN_SIGNAL_TOKENS))
    score -= min(14, hit_count(text, WEAK_NOISE_TOKENS) * 4)
    if not row.get("entity_name") and row.get("specificity") == "low":
        score -= 4
    if entity and entity not in claim and ticker and ticker not in claim:
        score -= 8
    if re.search(r"\d{6}", claim) and len(set(re.findall(r"\d{6}", claim))) >= 3:
        score -= 8
    if claim.count("/") >= 8 or "------" in claim:
        score -= 10
    if len(claim) > 420:
        score -= 2
    return score


def section_min_score(info_type: str, min_score: int) -> int:
    if info_type == "segment_mapping":
        return min(min_score, 12)
    if info_type == "relationship":
        return min(min_score, 18)
    if info_type == "marginal_change":
        return min_score
    return min_score


def row_display_min_score(row: dict, min_score: int) -> int:
    types = row.get("info_types") or [row.get("primary_info_type")]
    return min(section_min_score(t, min_score) for t in types if t)


def radar_tier(row: dict) -> str:
    score = radar_score(row)
    if score >= 22:
        return "精选"
    if score >= 14:
        return "保留"
    return "降权背景"


def info_type_label(row: dict) -> str:
    names = {
        "marginal_change": "边际变化",
        "relationship": "上下游/关系",
        "segment_mapping": "细分行业/位置",
        "theme_driver": "题材驱动",
    }
    types = row.get("info_types") or [row.get("primary_info_type")]
    labels = [names.get(t, t or "") for t in types if t]
    return "、".join(dict.fromkeys(labels))


def short(text: str, n: int = 90) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def display_claim(row: dict) -> str:
    claim = str(row.get("claim") or "")
    entity = str(row.get("entity_name") or "")
    ticker = str(row.get("ticker") or "")
    keys = [x for x in (entity, ticker) if x]
    if not keys:
        return claim

    parts = [p.strip(" -|/　") for p in re.split(r"[\n。；;]+|\s/\s", claim) if p.strip(" -|/　")]
    hits = [p for p in parts if any(k in p for k in keys)]
    if hits:
        return "；".join(hits[:2])

    idxs = [claim.find(k) for k in keys if claim.find(k) >= 0]
    if idxs:
        i = min(idxs)
        return claim[max(0, i - 40): i + 180]
    return claim


def norm_claim(text: str) -> str:
    text = re.sub(r"\s+", "", str(text or ""))
    text = re.sub(r"[，。；：:;,.、（）()【】\[\]《》\"'“”‘’`~!！?？\-—_/\\]", "", text)
    return text[:100]


def item_sort_key(row: dict):
    return (
        -radar_score(row),
        -rank_specificity(row.get("specificity")),
        0 if row.get("entity_name") else 1,
        -len(row.get("source_refs") or []),
        row.get("entity_name") or "",
    )


def section_sort_key(row: dict, info_type: str):
    section_bonus = 0
    if row.get("primary_info_type") == info_type:
        section_bonus += 20
    if info_type == "segment_mapping" and (row.get("segment") or row.get("chain_position")):
        section_bonus += 8
    if info_type == "relationship":
        section_bonus += hit_count(row_text(row), ("上游", "中游", "下游", "供应", "客户", "导入", "配套", "环节", "产业链")) * 2
    return (
        -(radar_score(row) + section_bonus),
        -rank_specificity(row.get("specificity")),
        0 if row.get("entity_name") else 1,
        -len(row.get("source_refs") or []),
        row.get("entity_name") or "",
    )


def section_rows(rows: list[dict], info_type: str, limit: int, profile: str, min_score: int, used: set | None = None) -> list[dict]:
    selected = [r for r in rows if r.get("primary_info_type") == info_type or info_type in (r.get("info_types") or [])]
    if profile == "radar-clean":
        selected = [r for r in selected if radar_score(r) >= section_min_score(info_type, min_score)]
    picked = []
    seen = set()
    entity_counts = Counter()
    for row in sorted(selected, key=lambda r: section_sort_key(r, info_type)):
        key = norm_claim(row.get("claim"))
        if key in seen:
            continue
        if used is not None and key in used:
            continue
        entity_key = row.get("entity_name") or "无主体"
        if profile == "radar-clean" and entity_counts[entity_key] >= 2:
            continue
        seen.add(key)
        if used is not None:
            used.add(key)
        entity_counts[entity_key] += 1
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def render_table(rows: list[dict], profile: str) -> list[str]:
    if profile == "radar-clean":
        lines = ["| 标的/主体 | 雷达层级 | 信息类型 | 具体度 | 来源 | 信息 |", "|---|---|---|---|---|---|"]
    else:
        lines = ["| 标的/主体 | 信息类型 | 具体度 | 来源 | 信息 |", "|---|---|---|---|---|"]
    for r in rows:
        name = r.get("entity_name") or "-"
        ticker = r.get("ticker") or ""
        if ticker:
            name = f"{name} ({ticker})"
        values = [
                short(name, 28),
        ]
        if profile == "radar-clean":
            values.append(f"{radar_tier(r)}({radar_score(r)})")
        values.extend([
            info_type_label(r),
            zh_specificity(r.get("specificity")),
            source_label(r),
            short(display_claim(r), 120).replace("|", "/"),
        ])
        lines.append("| " + " | ".join(values) + " |")
    return lines


def cleaned_rows(rows: list[dict], min_score: int) -> list[dict]:
    return [r for r in rows if radar_score(r) >= row_display_min_score(r, min_score)]


def render_segment(segment: str, rows: list[dict], limit_each: int, profile: str, min_score: int) -> list[str]:
    display_rows = cleaned_rows(rows, min_score) if profile == "radar-clean" else rows
    if profile == "radar-clean" and not display_rows:
        return []
    lines = [f"## {segment}", ""]
    if profile == "radar-clean":
        lines.append(f"全量信息项：{len(rows)}；雷达精选/保留：{len(display_rows)}；主体数：{len({r.get('entity_name') for r in display_rows if r.get('entity_name')})}")
    else:
        lines.append(f"信息项：{len(rows)}；主体数：{len({r.get('entity_name') for r in rows if r.get('entity_name')})}")
    lines.append("")
    used = set() if profile == "radar-clean" else None
    sections = [
        ("题材地图/位置", "segment_mapping", limit_each),
        ("上下游/关系", "relationship", limit_each),
        ("边际变化", "marginal_change", max(3, limit_each // 2) if profile == "radar-clean" else limit_each),
        ("题材驱动", "theme_driver", max(3, limit_each // 2) if profile == "radar-clean" else limit_each),
    ]
    for title, info_type, section_limit in sections:
        picked = section_rows(rows, info_type, section_limit, profile, min_score, used)
        if not picked:
            continue
        lines.append(f"### {title}")
        lines.extend(render_table(picked, profile))
        lines.append("")
    return lines


def build_report(rows: list[dict], theme: str, limit_segments: int, limit_each: int, profile: str, min_score: int) -> str:
    by_segment = defaultdict(list)
    for row in rows:
        seg = row.get("segment") or row.get("chain_position") or "未分段"
        by_segment[seg].append(row)
    selected_rows = cleaned_rows(rows, min_score) if profile == "radar-clean" else rows

    note_lines = [
        "> 说明：这是题材雷达信息平权预览，不是事实审计。弱信息保留，以低具体度/低展示权重呈现。",
    ]
    if profile == "radar-clean":
        note_lines.append("> 雷达清洗版只压缩展示层；全量 JSONL 信息池不删除、不合并细分行业。")

    lines = [
        f"# {theme} 题材信息池预览" + ("（雷达清洗版）" if profile == "radar-clean" else ""),
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        *note_lines,
        "",
        "## 总览",
        "",
        f"- 信息项：{len(rows)}",
        f"- 展示项：{len(selected_rows)}" if profile == "radar-clean" else "",
        f"- 细分行业/环节：{len(by_segment)}",
        f"- 主体数：{len({r.get('entity_name') for r in rows if r.get('entity_name')})}",
        f"- 来源：{dict(Counter(source_label(r) for r in selected_rows))}",
        f"- 具体度：{dict(Counter(zh_specificity(r.get('specificity')) for r in selected_rows))}",
        f"- 信息类型：{dict(Counter(r.get('primary_info_type') for r in selected_rows))}",
        "",
        "## 细分行业索引",
        "",
        "| 细分行业/环节 | 全量 | 展示 | 高具体度 | 中具体度 | 低具体度 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    lines = [line for line in lines if line != "" or not lines or lines[-1] != ""]

    sorted_segments = sorted(by_segment.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for seg, items in sorted_segments[:limit_segments]:
        display_items = cleaned_rows(items, min_score) if profile == "radar-clean" else items
        c = Counter(i.get("specificity") for i in display_items)
        lines.append(f"| {seg} | {len(items)} | {len(display_items)} | {c.get('high', 0)} | {c.get('medium', 0)} | {c.get('low', 0)} |")
    lines.append("")

    for seg, items in sorted_segments[:limit_segments]:
        lines.extend(render_segment(seg, items, limit_each, profile, min_score))

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render theme information Markdown preview")
    parser.add_argument("input_jsonl")
    parser.add_argument("--out", required=True)
    parser.add_argument("--theme", default="光模块")
    parser.add_argument("--limit-segments", type=int, default=30)
    parser.add_argument("--limit-each", type=int, default=12)
    parser.add_argument("--profile", choices=["full", "radar-clean"], default="full")
    parser.add_argument("--min-score", type=int, default=14)
    args = parser.parse_args()

    rows = read_jsonl(Path(args.input_jsonl).expanduser())
    report = build_report(rows, args.theme, args.limit_segments, args.limit_each, args.profile, args.min_score)
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"[OK] wrote {out}")
    print(f"items={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

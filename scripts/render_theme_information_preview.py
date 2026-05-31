#!/usr/bin/env python3
"""Render a Markdown preview report from unified theme information JSONL."""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import re


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


def norm_claim(text: str) -> str:
    text = re.sub(r"\s+", "", str(text or ""))
    text = re.sub(r"[，。；：:;,.、（）()【】\[\]《》\"'“”‘’`~!！?？\-—_/\\]", "", text)
    return text[:100]


def item_sort_key(row: dict):
    return (
        -rank_specificity(row.get("specificity")),
        0 if row.get("entity_name") else 1,
        -len(row.get("source_refs") or []),
        row.get("entity_name") or "",
    )


def section_rows(rows: list[dict], info_type: str, limit: int) -> list[dict]:
    selected = [r for r in rows if r.get("primary_info_type") == info_type or info_type in (r.get("info_types") or [])]
    picked = []
    seen = set()
    for row in sorted(selected, key=item_sort_key):
        key = norm_claim(row.get("claim"))
        if key in seen:
            continue
        seen.add(key)
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def render_table(rows: list[dict]) -> list[str]:
    lines = ["| 标的/主体 | 信息类型 | 具体度 | 来源 | 信息 |", "|---|---|---|---|---|"]
    for r in rows:
        name = r.get("entity_name") or "-"
        ticker = r.get("ticker") or ""
        if ticker:
            name = f"{name} ({ticker})"
        lines.append(
            "| "
            + " | ".join([
                short(name, 28),
                info_type_label(r),
                zh_specificity(r.get("specificity")),
                source_label(r),
                short(r.get("claim"), 120).replace("|", "/"),
            ])
            + " |"
        )
    return lines


def render_segment(segment: str, rows: list[dict], limit_each: int) -> list[str]:
    lines = [f"## {segment}", ""]
    lines.append(f"信息项：{len(rows)}；主体数：{len({r.get('entity_name') for r in rows if r.get('entity_name')})}")
    lines.append("")
    for title, info_type in [("边际变化", "marginal_change"), ("上下游/关系", "relationship"), ("题材驱动", "theme_driver")]:
        picked = section_rows(rows, info_type, limit_each)
        if not picked:
            continue
        lines.append(f"### {title}")
        lines.extend(render_table(picked))
        lines.append("")
    other = section_rows(rows, "segment_mapping", max(5, limit_each // 2))
    if other:
        lines.append("### 细分行业/位置")
        lines.extend(render_table(other))
        lines.append("")
    return lines


def build_report(rows: list[dict], theme: str, limit_segments: int, limit_each: int) -> str:
    by_segment = defaultdict(list)
    for row in rows:
        seg = row.get("segment") or row.get("chain_position") or "未分段"
        by_segment[seg].append(row)

    lines = [
        f"# {theme} 题材信息池预览",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "> 说明：这是题材雷达信息平权预览，不是事实审计。弱信息保留，以低具体度/低展示权重呈现。",
        "",
        "## 总览",
        "",
        f"- 信息项：{len(rows)}",
        f"- 细分行业/环节：{len(by_segment)}",
        f"- 主体数：{len({r.get('entity_name') for r in rows if r.get('entity_name')})}",
        f"- 来源：{dict(Counter(source_label(r) for r in rows))}",
        f"- 具体度：{dict(Counter(zh_specificity(r.get('specificity')) for r in rows))}",
        f"- 信息类型：{dict(Counter(r.get('primary_info_type') for r in rows))}",
        "",
        "## 细分行业索引",
        "",
        "| 细分行业/环节 | 信息项 | 高具体度 | 中具体度 | 低具体度 |",
        "|---|---:|---:|---:|---:|",
    ]

    sorted_segments = sorted(by_segment.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for seg, items in sorted_segments[:limit_segments]:
        c = Counter(i.get("specificity") for i in items)
        lines.append(f"| {seg} | {len(items)} | {c.get('high', 0)} | {c.get('medium', 0)} | {c.get('low', 0)} |")
    lines.append("")

    for seg, items in sorted_segments[:limit_segments]:
        lines.extend(render_segment(seg, items, limit_each))

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render theme information Markdown preview")
    parser.add_argument("input_jsonl")
    parser.add_argument("--out", required=True)
    parser.add_argument("--theme", default="光模块")
    parser.add_argument("--limit-segments", type=int, default=30)
    parser.add_argument("--limit-each", type=int, default=12)
    args = parser.parse_args()

    rows = read_jsonl(Path(args.input_jsonl).expanduser())
    report = build_report(rows, args.theme, args.limit_segments, args.limit_each)
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"[OK] wrote {out}")
    print(f"items={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

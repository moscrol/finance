#!/usr/bin/env python3
"""
Merge multiple neutral theme information pools.

Input: JSONL files produced by IMA/Obsidian scanners.
Output: unified JSONL + summary + segment preview.
No knowledge-base writeback.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def sha_id(*parts: str) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{i}: {exc}") from exc
            row["_input_file"] = str(path)
            rows.append(row)
    return rows


def norm_text(s: str) -> str:
    s = str(s or "").lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[，。；：:;,.、（）()【】\[\]《》\"'“”‘’`~!！?？\-—_/\\]", "", s)
    return s[:120]


# C: 共享 segment 词表（IMA 与 Obsidian 对齐），使跨源可归并/互证
SEGMENT_TAXONOMY = [
    ("上游-光芯片", ["光芯片", "EML", "DFB", "VCSEL", "CW激光", "磷化铟", "InP"]),
    ("上游-光器件/材料", ["光器件", "光引擎", "隔离器", "法拉第", "旋光", "MPO", "FAU", "AWG", "陶瓷基板", "衬底", "晶体"]),
    ("中游-光模块/CPO", ["光模块", "CPO", "NPO", "LPO", "800G", "1.6T", "3.2T", "设计制造", "封装测试", "封装代工"]),
    ("中游-OCS/DCI", ["OCS", "DCI", "相干", "光交换", "光电路交换"]),
    ("配套-设备/测试", ["耦合设备", "测试设备", "自动化设备", "贴片", "AOI", "固晶", "共晶", "精密制造", "仪器"]),
    ("下游-算力/云厂商", ["算力", "云厂", "英伟达", "谷歌", "Meta", "AWS", "微软", "TPU", "GPU", "数据中心"]),
]


def canonical_segment(*texts: str) -> str:
    t = " ".join(str(x or "") for x in texts)
    for seg, keys in SEGMENT_TAXONOMY:
        if any(k in t for k in keys):
            return seg
    return "未分段"


def annotate_corroboration(merged: list[dict]) -> dict:
    """实体×segment 级别的跨源互证：同一公司同一环节被多个 source_system 覆盖。"""
    groups = defaultdict(set)
    for r in merged:
        e = norm_text(r.get("entity_name"))
        if not e:
            continue
        groups[(e, r.get("segment") or "")].update(r.get("source_systems") or [])
    pairs = [k for k, v in groups.items() if len(v) > 1]
    ents = sorted({k[0] for k in pairs})
    for r in merged:
        e = norm_text(r.get("entity_name"))
        if not e:
            r["cross_source"] = False
            continue
        sysset = groups[(e, r.get("segment") or "")]
        r["entity_segment_sources"] = sorted(sysset)
        r["cross_source"] = len(sysset) > 1
    return {"cross_source_entity_segment_pairs": len(pairs),
            "cross_source_entities": len(ents)}


def merge_key(row: dict) -> tuple:
    entity = row.get("entity_name") or ""
    ticker = row.get("ticker") or ""
    segment = row.get("segment") or row.get("chain_position") or ""
    claim = row.get("claim") or ""
    return (norm_text(entity), norm_text(ticker), norm_text(segment), norm_text(claim))


def specificity_rank(v: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(v or "", 0)


def weight_rank(v: str) -> int:
    return {"low": 1, "normal": 2, "high": 3}.get(v or "", 0)


def merge_two(a: dict, b: dict) -> dict:
    out = dict(a)
    systems = set(a.get("source_systems") or []) | set(b.get("source_systems") or [])
    out["source_systems"] = sorted(systems)
    out["source_refs"] = (a.get("source_refs") or []) + (b.get("source_refs") or [])
    out["source_count"] = len(out["source_refs"])
    out["source_overlap"] = len(systems) > 1
    out["merged_from_item_ids"] = sorted(set((a.get("merged_from_item_ids") or [a.get("item_id")]) + (b.get("merged_from_item_ids") or [b.get("item_id")])) )

    info_types = []
    for row in (a, b):
        for t in row.get("info_types") or []:
            if t not in info_types:
                info_types.append(t)
    out["info_types"] = info_types
    out["primary_info_type"] = out.get("primary_info_type") or (info_types[0] if info_types else "")

    if specificity_rank(b.get("specificity")) > specificity_rank(out.get("specificity")):
        out["specificity"] = b.get("specificity")
    if weight_rank(b.get("display_weight")) > weight_rank(out.get("display_weight")):
        out["display_weight"] = b.get("display_weight")

    out["item_id"] = "merged-" + sha_id(out.get("theme"), out.get("entity_name"), out.get("ticker"), out.get("segment"), out.get("claim"))
    return out


def merge_rows(rows: list[dict]) -> list[dict]:
    merged = {}
    for row in rows:
        row = dict(row)
        row.setdefault("source_count", len(row.get("source_refs") or []))
        row.setdefault("source_overlap", len(set(row.get("source_systems") or [])) > 1)
        row.setdefault("merged_from_item_ids", [row.get("item_id")])
        key = merge_key(row)
        if key in merged:
            merged[key] = merge_two(merged[key], row)
        else:
            merged[key] = row
    return list(merged.values())


def build_summary(rows: list[dict], merged: list[dict]) -> dict:
    return {
        "input_count": len(rows),
        "merged_count": len(merged),
        "deduped_count": len(rows) - len(merged),
        "source_systems": dict(Counter(s for r in merged for s in (r.get("source_systems") or []))),
        "items_by_specificity": dict(Counter(r.get("specificity", "") for r in merged)),
        "items_by_primary_info_type": dict(Counter(r.get("primary_info_type", "") for r in merged)),
        "items_by_display_weight": dict(Counter(r.get("display_weight", "") for r in merged)),
        "source_overlap_count": sum(1 for r in merged if r.get("source_overlap")),
        "unique_entity_count": len({r.get("entity_name") for r in merged if r.get("entity_name")}),
        "top_segments": dict(Counter(r.get("segment", "") for r in merged).most_common(30)),
        "top_entities": dict(Counter(r.get("entity_name", "") for r in merged if r.get("entity_name")).most_common(30)),
        "safety_statement": "Unified theme information pool only. No entity/relation/knowledge-base writeback.",
    }


def build_segment_preview(rows: list[dict], limit_per_segment: int = 20) -> list[dict]:
    groups = defaultdict(list)
    for r in rows:
        groups[r.get("segment") or r.get("chain_position") or "未分段"].append(r)
    preview = []
    for segment, items in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        sorted_items = sorted(
            items,
            key=lambda r: (-specificity_rank(r.get("specificity")), -len(r.get("source_refs") or []), r.get("entity_name") or ""),
        )[:limit_per_segment]
        preview.append({
            "segment": segment,
            "item_count": len(items),
            "items": [
                {
                    "entity_name": r.get("entity_name"),
                    "ticker": r.get("ticker"),
                    "primary_info_type": r.get("primary_info_type"),
                    "specificity": r.get("specificity"),
                    "display_weight": r.get("display_weight"),
                    "source_systems": r.get("source_systems"),
                    "claim": r.get("claim"),
                }
                for r in sorted_items
            ],
        })
    return preview


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            r = {k: v for k, v in r.items() if not k.startswith("_")}
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge theme information pools")
    parser.add_argument("inputs", nargs="+", help="input JSONL files")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--prefix", default="光模块_unified")
    args = parser.parse_args()

    rows = []
    for raw in args.inputs:
        path = Path(raw).expanduser()
        if not path.exists():
            print(f"[ERR] input not found: {path}", file=sys.stderr)
            return 1
        rows.extend(read_jsonl(path))

    # C: 对齐 segment 词表（对所有源统一），跨源才能归并与互证
    for r in rows:
        r["segment_raw"] = r.get("segment", "")
        r["segment"] = canonical_segment(r.get("segment"), r.get("chain_position"), r.get("component"), r.get("claim"))

    merged = merge_rows(rows)
    corr = annotate_corroboration(merged)
    summary = build_summary(rows, merged)
    summary.update(corr)
    preview = build_segment_preview(merged)

    out = Path(args.out_dir).expanduser()
    write_jsonl(out / f"{args.prefix}.theme_information_items.jsonl", merged)
    write_json(out / f"{args.prefix}.summary.json", summary)
    write_json(out / f"{args.prefix}.segment_preview.json", preview)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] wrote outputs: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

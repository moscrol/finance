#!/usr/bin/env python3
"""
Build a neutral theme information pool from Markdown exports.

Use case: theme radar information parity, not fact audit.
- Keep broad/weak information; mark lower specificity/display weight.
- Focus on theme, marginal change, segment, and upstream/downstream relations.
- Does not write entities, relations, or knowledge-base files.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

CHAIN_HEADERS = {"环节名称", "相关公司", "公司证券代码", "证据摘要"}
SOURCE_HEADERS = {"来源标题", "来源类型", "发布方", "日期"}
QUESTION_HEADERS = {"问题", "涉及公司", "优先级"}


def sha_id(*parts: str) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def split_md_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    cells = split_md_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c.strip()) for c in cells)


def parse_theme(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            title = line.lstrip("#").strip()
            for sep in (" — ", "—", "-", "：", ":"):
                if sep in title:
                    return title.split(sep, 1)[0].strip() or fallback
            return title or fallback
    return fallback


def parse_markdown_tables(text: str) -> list[dict]:
    lines = text.splitlines()
    tables = []
    section = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            i += 1
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            headers = split_md_row(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_md_row(lines[i])
                row = {headers[j]: cells[j] if j < len(cells) else "" for j in range(len(headers))}
                rows.append({"line_no": i + 1, "row": row})
                i += 1
            tables.append({"section": section, "headers": headers, "rows": rows})
            continue
        i += 1
    return tables


def parse_jsonl_records(text: str) -> tuple[list[dict], list[str]]:
    records, errors = [], []
    for line_no, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                records.append({"line_no": line_no, "record": json.loads(s)})
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_no}: {exc}")
    return records, errors


def normalize_confidence(v: str) -> str:
    v = str(v or "").strip().lower()
    return {"高": "high", "中": "medium", "低": "low", "high": "high", "medium": "medium", "low": "low"}.get(v, "unknown")


def bool_like(v):
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    if s in {"是", "true", "yes", "1"}:
        return True
    if s in {"否", "false", "no", "0"}:
        return False
    return None


def infer_source_type(title: str) -> str:
    s = title or ""
    if "专家" in s or "调研" in s:
        return "调研/专家会"
    if "研报" in s or "证券" in s or "通信" in s or "机械" in s:
        return "研报"
    if "半年报" in s or "年报" in s:
        return "定期报告"
    if "网页" in s:
        return "网页"
    return ""


def infer_info_types(claim: str, segment: str = "", entity: str = "") -> list[str]:
    text = " ".join([claim or "", segment or "", entity or ""])
    types = []
    if re.search(r"涨价|缺口|紧缺|放量|上修|扩产|产能|同比|增长|提升|送样|量产|订单|份额|毛利率|营收|净利", text):
        types.append("marginal_change")
    if re.search(r"供应|客户|合作|绑定|进入.*链|供货|采购|代工|收购", text):
        types.append("relationship")
    if re.search(r"行业|需求|市场空间|路线|CPO|OCS|1\.6T|800G|3\.2T", text):
        types.append("theme_driver")
    if not types:
        types.append("segment_mapping")
    return types


def infer_specificity(claim: str, entity: str = "", ticker: str = "") -> str:
    text = claim or ""
    score = 0
    if entity:
        score += 1
    if ticker and ticker not in {"未知", "unknown", ""}:
        score += 1
    if re.search(r"\d", text):
        score += 2
    if re.search(r"量产|送样|订单|产能|份额|涨价|同比|毛利率|营收|净利|客户|供应链|收购|扩产", text):
        score += 2
    if len(text) >= 28:
        score += 1
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def display_weight(specificity: str) -> str:
    return "low" if specificity == "low" else "normal"


def item_from_chain_row(row: dict, meta: dict) -> dict:
    entity = row.get("相关公司", "")
    ticker = row.get("公司证券代码", "")
    segment = row.get("环节名称", "")
    component = row.get("关键材料/零部件/设备/软件", "")
    claim = row.get("证据摘要", "")
    src = row.get("来源", "")
    date = row.get("时间", "")
    specificity = infer_specificity(claim, entity, ticker)
    info_types = infer_info_types(claim, segment, entity)
    return {
        "item_id": sha_id(meta["theme"], entity, ticker, segment, claim, meta["line_no"]),
        "theme": meta["theme"],
        "entity_name": entity,
        "ticker": ticker,
        "chain_position": meta["section"],
        "segment": segment,
        "component": component,
        "claim": claim,
        "info_types": info_types,
        "primary_info_type": info_types[0],
        "specificity": specificity,
        "display_weight": display_weight(specificity),
        "source_systems": [meta["source_system"]],
        "source_refs": [{
            "system": meta["source_system"],
            "path": meta["source_file"],
            "section": meta["section"],
            "line_no": meta["line_no"],
            "source_title": src,
            "source_type": infer_source_type(src),
            "source_date": date,
        }],
        "source_title": src,
        "source_type": infer_source_type(src),
        "source_date": date,
        "confidence_raw": row.get("可信度", ""),
        "confidence": normalize_confidence(row.get("可信度", "")),
        "needs_review_raw": row.get("是否需要人工核验", ""),
        "needs_review": bool_like(row.get("是否需要人工核验", "")),
        "source_record_type": "markdown_table",
        "raw_row": row,
    }


def item_from_jsonl(rec: dict, meta: dict) -> dict:
    entity = rec.get("entity_name", "")
    ticker = rec.get("ticker", "")
    segment = rec.get("chain_segment") or rec.get("sub_theme") or ""
    claim = rec.get("claim", "")
    specificity = infer_specificity(claim, entity, ticker)
    info_types = infer_info_types(claim, segment, entity)
    system = rec.get("source_system") or meta["source_system"]
    return {
        "item_id": sha_id(meta["theme"], entity, ticker, segment, claim, meta["line_no"]),
        "theme": rec.get("theme") or meta["theme"],
        "entity_name": entity,
        "ticker": ticker,
        "chain_position": segment,
        "segment": segment,
        "component": rec.get("sub_theme", ""),
        "claim": claim,
        "info_types": info_types,
        "primary_info_type": info_types[0],
        "specificity": specificity,
        "display_weight": display_weight(specificity),
        "source_systems": [system],
        "source_refs": [{
            "system": system,
            "path": meta["source_file"],
            "section": "JSONL 附录",
            "line_no": meta["line_no"],
            "source_title": rec.get("source_title", ""),
            "source_type": rec.get("source_type", ""),
            "source_date": rec.get("source_date", ""),
        }],
        "source_title": rec.get("source_title", ""),
        "source_type": rec.get("source_type", ""),
        "source_date": rec.get("source_date", ""),
        "confidence_raw": rec.get("confidence", ""),
        "confidence": normalize_confidence(rec.get("confidence", "")),
        "needs_review_raw": rec.get("needs_review"),
        "needs_review": bool_like(rec.get("needs_review")),
        "suggested_use": rec.get("suggested_use", ""),
        "risk_note": rec.get("risk_note", ""),
        "source_record_type": "jsonl_appendix",
        "raw_record": rec,
    }


def source_from_row(row: dict, meta: dict) -> dict:
    title = row.get("来源标题", "")
    return {
        "source_id": sha_id(meta["theme"], title, row.get("日期", ""), row.get("URL或可追溯标识", "")),
        "theme": meta["theme"],
        "source_system": meta["source_system"],
        "source_title": title,
        "source_type": row.get("来源类型", ""),
        "publisher": row.get("发布方", ""),
        "source_date": row.get("日期", ""),
        "source_ref": row.get("URL或可追溯标识", ""),
        "related_entities": row.get("涉及公司", ""),
        "related_theme": row.get("涉及主题", ""),
        "confidence_raw": row.get("可信度", ""),
        "confidence": normalize_confidence(row.get("可信度", "")),
        "note": row.get("备注", ""),
        "path": meta["source_file"],
        "section": meta["section"],
        "line_no": meta["line_no"],
    }


def question_from_row(row: dict, meta: dict) -> dict:
    q = row.get("问题", "")
    return {
        "question_id": sha_id(meta["theme"], q, row.get("涉及公司", ""), meta["line_no"]),
        "theme": meta["theme"],
        "source_system": meta["source_system"],
        "question": q,
        "related_entities": row.get("涉及公司", ""),
        "related_sources": row.get("涉及来源", ""),
        "priority_raw": row.get("优先级", ""),
        "suggested_check_path": row.get("建议核验路径", ""),
        "path": meta["source_file"],
        "section": meta["section"],
        "line_no": meta["line_no"],
    }


def extract_theme_definition(text: str, theme: str, path: str, source_system: str) -> dict:
    notes = []
    in_def = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("# 1."):
            in_def = True
        elif in_def and line.startswith("# 2."):
            break
        if in_def and line.strip() and not line.strip().startswith("---"):
            notes.append({"line_no": i, "text": line.strip()})
    return {"theme": theme, "source_system": source_system, "source_file": path, "notes": notes}


def build_outputs(path: Path, source_system: str) -> tuple[dict, list[str]]:
    text = path.read_text(encoding="utf-8")
    theme = parse_theme(text, path.stem)
    items, sources, questions, errors = [], [], [], []

    for table in parse_markdown_tables(text):
        headers = set(table["headers"])
        for r in table["rows"]:
            meta = {"theme": theme, "source_system": source_system, "source_file": str(path), "section": table["section"], "line_no": r["line_no"]}
            if CHAIN_HEADERS.issubset(headers):
                items.append(item_from_chain_row(r["row"], meta))
            elif SOURCE_HEADERS.issubset(headers):
                sources.append(source_from_row(r["row"], meta))
            elif QUESTION_HEADERS.issubset(headers):
                questions.append(question_from_row(r["row"], meta))

    jsonl_records, jsonl_errors = parse_jsonl_records(text)
    errors.extend(jsonl_errors)
    for r in jsonl_records:
        meta = {"theme": theme, "source_system": source_system, "source_file": str(path), "line_no": r["line_no"]}
        items.append(item_from_jsonl(r["record"], meta))

    definition = extract_theme_definition(text, theme, str(path), source_system)
    summary = {
        "theme": theme,
        "source_file": str(path),
        "item_count": len(items),
        "source_count": len(sources),
        "review_question_count": len(questions),
        "definition_note_count": len(definition["notes"]),
        "items_by_record_type": dict(Counter(i["source_record_type"] for i in items)),
        "items_by_specificity": dict(Counter(i["specificity"] for i in items)),
        "items_by_primary_info_type": dict(Counter(i["primary_info_type"] for i in items)),
        "items_by_display_weight": dict(Counter(i["display_weight"] for i in items)),
        "unique_entity_count": len({i.get("entity_name") for i in items if i.get("entity_name")}),
        "top_segments": dict(Counter(i.get("segment", "") for i in items).most_common(20)),
        "safety_statement": "Theme information pool only. No entity/relation/knowledge-base writeback.",
    }
    return {"summary": summary, "items": items, "sources": sources, "review_questions": questions, "definition": definition}, errors


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build theme information pool from Markdown")
    parser.add_argument("markdown")
    parser.add_argument("--source-system", default="IMA")
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    path = Path(args.markdown).expanduser()
    if not path.exists():
        print(f"[ERR] file not found: {path}", file=sys.stderr)
        return 1

    outputs, errors = build_outputs(path, args.source_system)
    for err in errors:
        print(f"[WARN] {err}", file=sys.stderr)
    print(json.dumps(outputs["summary"], ensure_ascii=False, indent=2))

    if args.out_dir:
        out = Path(args.out_dir).expanduser()
        stem = path.stem
        write_jsonl(out / f"{stem}.theme_information_items.jsonl", outputs["items"])
        write_jsonl(out / f"{stem}.source_registry.jsonl", outputs["sources"])
        write_jsonl(out / f"{stem}.review_questions.jsonl", outputs["review_questions"])
        write_json(out / f"{stem}.theme_definition.json", outputs["definition"])
        write_json(out / f"{stem}.summary.json", outputs["summary"])
        print(f"[OK] wrote outputs: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

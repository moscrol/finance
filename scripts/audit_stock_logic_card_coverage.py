#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_VAULT = Path("/Users/a77/Desktop/c c/知识库")
DEFAULT_LOCAL_CARD_DIR = Path("/Users/a77/Desktop/c c/个股")


@dataclass
class Stock:
    name: str
    code: str = ""
    source: str = ""
    role: str = ""
    strength: str = ""
    confidence: str = ""


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"(?:SZ|SH|BJ)?(\d{6})(?:\.(?:SZ|SH|BJ|HK|US))?", text, flags=re.I)
    return match.group(1) if match else ""


def normalize_name(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[（(].*?[）)]", "", text).strip()
    text = re.sub(r"股份有限公司$|科技股份有限公司$|集团股份有限公司$|有限公司$|公司$", "", text)
    return text.strip()


def stock_key(stock: Stock) -> str:
    return stock.code or stock.name


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end = idx
            break
    if end is None:
        return {}, text
    meta: dict[str, Any] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value.startswith("[") and value.endswith("]"):
            try:
                meta[key] = json.loads(value.replace("'", '"'))
            except Exception:
                meta[key] = value
        else:
            meta[key] = value
    return meta, "\n".join(lines[end + 1 :])


def infer_name_from_card(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    meta, body = split_frontmatter(text)
    for key in ("company", "entity", "title"):
        if meta.get(key):
            return normalize_name(meta[key])
    h1 = re.search(r"^#\s+(.+?)\s*$", body, flags=re.M)
    if h1:
        name = re.split(r"[｜|]", h1.group(1), maxsplit=1)[0]
        name = re.sub(r"_(?:最新逻辑|个股逻辑).*", "", name)
        return normalize_name(name)
    stem = path.stem
    stem = re.sub(r"^(?:SZ|SH|BJ)?\d{6}_", "", stem, flags=re.I)
    stem = re.sub(r"_(?:最新逻辑|个股逻辑|逻辑卡|研究素材|最新逻辑跟踪).*", "", stem)
    stem = re.sub(r"(?:最新逻辑跟踪|最新逻辑卡|个股逻辑卡|逻辑卡|研究素材).*$", "", stem)
    return normalize_name(stem)


def infer_code_from_card(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    meta, body = split_frontmatter(text)
    for key in ("ticker", "code", "stock_code"):
        code = normalize_code(meta.get(key))
        if code:
            return code
    code = normalize_code(path.name)
    if code:
        return code
    return normalize_code(body[:800])


def load_local_cards(card_dir: Path) -> dict[str, list[str]]:
    cards: dict[str, list[str]] = {}
    if not card_dir.exists():
        return cards
    for path in card_dir.rglob("*.md"):
        name = infer_name_from_card(path)
        code = infer_code_from_card(path)
        for key in {name, code} - {""}:
            cards.setdefault(key, []).append(str(path))
    return cards


def load_ingested_ima(vault: Path) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    exposures = load_json(vault / "wiki" / "relations" / "entity_exposures.json", {"entities": {}})
    entities = exposures.get("entities", {}) if isinstance(exposures, dict) else {}
    result: dict[str, dict[str, Any]] = {}
    source_by_entity: dict[str, list[str]] = {}
    for name, payload in entities.items():
        if not isinstance(payload, dict):
            continue
        codes = [normalize_code(x) for x in payload.get("codes", []) if normalize_code(x)]
        concepts = payload.get("concepts", {})
        has_ima = False
        concepts_with_ima: list[str] = []
        sources: list[str] = []
        if isinstance(concepts, dict):
            for concept, detail in concepts.items():
                if not isinstance(detail, dict):
                    continue
                detail_sources = [str(x) for x in detail.get("sources", []) if x]
                if detail.get("update_type") == "ima_stock_logic" or detail.get("source_quality") == "ima_composite":
                    has_ima = True
                    concepts_with_ima.append(str(concept))
                    sources.extend(detail_sources)
        if not has_ima:
            entity_path = vault / "wiki" / "entities" / f"{name}.md"
            if entity_path.exists():
                text = entity_path.read_text(encoding="utf-8", errors="ignore")
                has_ima = "IMA 最新逻辑跟踪" in text or "IMA个股逻辑" in text
        if has_ima:
            keys = {normalize_name(name), *codes} - {""}
            item = {
                "name": normalize_name(name),
                "codes": codes,
                "concepts": concepts_with_ima,
                "sources": sorted(set(sources)),
            }
            for key in keys:
                result[key] = item
            source_by_entity[normalize_name(name)] = sorted(set(sources))
    return result, source_by_entity


def load_constituents_from_exposures(vault: Path, theme: str) -> list[Stock]:
    exposures = load_json(vault / "wiki" / "relations" / "entity_exposures.json", {"entities": {}})
    entities = exposures.get("entities", {}) if isinstance(exposures, dict) else {}
    stocks: list[Stock] = []
    for name, payload in entities.items():
        if not isinstance(payload, dict):
            continue
        concepts = payload.get("concepts", {})
        if not isinstance(concepts, dict) or theme not in concepts:
            continue
        detail = concepts.get(theme) if isinstance(concepts.get(theme), dict) else {}
        code = ""
        for candidate in payload.get("codes", []):
            code = normalize_code(candidate)
            if code:
                break
        stocks.append(
            Stock(
                name=normalize_name(name),
                code=code,
                source="entity_exposures",
                role=str(detail.get("role") or detail.get("business_line") or ""),
                strength=str(detail.get("strength") or ""),
                confidence=str(detail.get("confidence") or ""),
            )
        )
    return sorted(stocks, key=lambda x: (x.code or "999999", x.name))


def load_constituents_from_file(path: Path) -> list[Stock]:
    if path.suffix.lower() == ".json":
        data = load_json(path, [])
        rows = data.get("stocks", data.get("constituents", data)) if isinstance(data, dict) else data
        result = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = normalize_name(row.get("name") or row.get("stock_name") or row.get("股票简称") or row.get("公司") or row.get("company"))
            code = normalize_code(row.get("code") or row.get("stock_code") or row.get("股票代码") or row.get("ticker"))
            if name or code:
                result.append(Stock(name=name, code=code, source=str(path)))
        return result
    result = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = normalize_name(row.get("name") or row.get("stock_name") or row.get("股票简称") or row.get("公司") or row.get("company"))
            code = normalize_code(row.get("code") or row.get("stock_code") or row.get("股票代码") or row.get("ticker"))
            if name or code:
                result.append(Stock(name=name, code=code, source=str(path)))
    return result


def load_constituents_from_duckdb(db_path: Path, theme: str, table: str | None) -> list[Stock]:
    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    tables = [r[0] for r in con.execute("select table_name from information_schema.tables where table_schema='main'").fetchall()]
    preferred = [table] if table else [
        "sector_constituents",
        "board_constituents",
        "concept_constituents",
        "stock_board_constituents",
        "stocks",
    ]
    for candidate in preferred:
        if not candidate or candidate not in tables:
            continue
        cols = [r[1] for r in con.execute(f"pragma table_info('{candidate}')").fetchall()]
        sector_cols = [c for c in cols if c in {"sector", "board", "concept", "theme", "themes", "板块", "概念", "核心题材"}]
        name_cols = [c for c in cols if c in {"stock_name", "name", "股票简称", "company", "公司"}]
        code_cols = [c for c in cols if c in {"stock_code", "code", "ticker", "股票代码"}]
        if not name_cols and not code_cols:
            continue
        name_col = name_cols[0] if name_cols else "''"
        code_col = code_cols[0] if code_cols else "''"
        if sector_cols:
            where = " OR ".join([f"cast({c} as varchar) like ?" for c in sector_cols])
            rows = con.execute(f"select {name_col}, {code_col} from {candidate} where {where}", [f"%{theme}%"] * len(sector_cols)).fetchall()
        else:
            rows = con.execute(f"select {name_col}, {code_col} from {candidate}").fetchall()
        result = [Stock(name=normalize_name(r[0]), code=normalize_code(r[1]), source=f"duckdb:{candidate}") for r in rows]
        result = [x for x in result if x.name or x.code]
        if result:
            return result
    return []


def dedupe_stocks(stocks: list[Stock]) -> list[Stock]:
    seen: set[str] = set()
    result: list[Stock] = []
    for stock in stocks:
        key = stock_key(stock)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(stock)
    return result


def audit(stocks: list[Stock], ingested: dict[str, dict[str, Any]], local_cards: dict[str, list[str]]) -> dict[str, Any]:
    covered = []
    local_only = []
    missing = []
    for stock in dedupe_stocks(stocks):
        keys = {stock.name, stock.code} - {""}
        matched = next((ingested[k] for k in keys if k in ingested), None)
        local = sorted({p for k in keys for p in local_cards.get(k, [])})
        row = {
            "name": stock.name,
            "code": stock.code,
            "source": stock.source,
            "role": stock.role,
            "strength": stock.strength,
            "confidence": stock.confidence,
        }
        if matched:
            row["ima_sources"] = matched.get("sources", [])
            row["ima_concepts"] = matched.get("concepts", [])
            covered.append(row)
        elif local:
            row["local_card_paths"] = local
            local_only.append(row)
        else:
            missing.append(row)
    return {"covered": covered, "local_only": local_only, "missing": missing}


def markdown_table(title: str, rows: list[dict[str, Any]], status: str) -> str:
    lines = [f"## {title}", "", "| 状态 | 公司 | 代码 | 产业角色 | 强度 | 可信度 | 来源/备注 |", "|---|---|---|---|---|---|---|"]
    for row in rows:
        note = ""
        if row.get("ima_sources"):
            note = "；".join(row.get("ima_sources", [])[:3])
        elif status == "已入库":
            note = "已入库IMA（实体页/其他概念）"
        elif row.get("local_card_paths"):
            note = "；".join(row.get("local_card_paths", [])[:2])
        else:
            note = row.get("source", "")
        lines.append(
            "| {status} | {name} | {code} | {role} | {strength} | {confidence} | {note} |".format(
                status=status,
                name=row.get("name", ""),
                code=row.get("code", ""),
                role=str(row.get("role", "")).replace("|", "/"),
                strength=row.get("strength", ""),
                confidence=row.get("confidence", ""),
                note=str(note).replace("|", "/"),
            )
        )
    if not rows:
        lines.append(f"| {status} | 无 |  |  |  |  |  |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit stock logic card coverage for a theme or sector.")
    parser.add_argument("--theme", required=True, help="板块/题材名")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="知识库路径")
    parser.add_argument("--local-card-dir", default=str(DEFAULT_LOCAL_CARD_DIR), help="本地未入库个股卡目录")
    parser.add_argument("--constituents", default="", help="成分股 CSV/JSON 文件，可选")
    parser.add_argument("--db", default="", help="DuckDB 文件路径，可选")
    parser.add_argument("--table", default="", help="DuckDB 成分股表名，可选")
    parser.add_argument("--out", default="", help="输出 markdown 路径")
    parser.add_argument("--json-out", default="", help="输出 json 路径")
    parser.add_argument("--include-no-code", action="store_true", help="包含无A股代码的海外/非上市映射")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    local_card_dir = Path(args.local_card_dir).expanduser().resolve()
    stocks: list[Stock] = []
    input_mode = "entity_exposures"
    if args.constituents:
        stocks = load_constituents_from_file(Path(args.constituents).expanduser().resolve())
        input_mode = "file"
    elif args.db:
        db_path = Path(args.db).expanduser().resolve()
        if db_path.exists():
            stocks = load_constituents_from_duckdb(db_path, args.theme, args.table or None)
            input_mode = "duckdb"
    if not stocks:
        stocks = load_constituents_from_exposures(vault, args.theme)
        input_mode = "entity_exposures"
    if not args.include_no_code:
        stocks = [stock for stock in stocks if stock.code]

    ingested, _ = load_ingested_ima(vault)
    local_cards = load_local_cards(local_card_dir)
    result = audit(stocks, ingested, local_cards)
    payload = {
        "theme": args.theme,
        "input_mode": input_mode,
        "counts": {
            "constituents": len(dedupe_stocks(stocks)),
            "covered": len(result["covered"]),
            "local_only": len(result["local_only"]),
            "missing": len(result["missing"]),
        },
        **result,
    }

    md = "\n\n".join(
        [
            f"# {args.theme} 个股逻辑卡覆盖审计",
            f"- **输入模式**：{input_mode}",
            f"- **成分股数**：{payload['counts']['constituents']}",
            f"- **已入库 IMA 逻辑卡**：{payload['counts']['covered']}",
            f"- **本地有卡但未确认入库**：{payload['counts']['local_only']}",
            f"- **缺逻辑卡**：{payload['counts']['missing']}",
            markdown_table("已入库 IMA 逻辑卡", result["covered"], "已入库"),
            markdown_table("本地有卡但未入库", result["local_only"], "待入库"),
            markdown_table("缺逻辑卡", result["missing"], "缺卡"),
        ]
    ) + "\n"

    out = Path(args.out).expanduser().resolve() if args.out else Path(f"/private/tmp/{args.theme}_stock_logic_card_coverage.md")
    json_out = Path(args.json_out).expanduser().resolve() if args.json_out else Path(f"/private/tmp/{args.theme}_stock_logic_card_coverage.json")
    out.write_text(md, encoding="utf-8")
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)
    print(json_out)
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

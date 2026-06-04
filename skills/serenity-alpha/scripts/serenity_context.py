#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

DEFAULT_VAULT = Path("/Users/a77/Desktop/c c/知识库/wiki")
DEFAULT_TMP = Path("/private/tmp")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").lower())


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def split_terms(text: str) -> list[str]:
    raw = re.split(r"[\s,，、/|;；：:()（）\[\]【】]+", str(text or ""))
    return [x.strip() for x in raw if len(x.strip()) >= 2]


def hit(term: str, text: str) -> bool:
    if not term or not text:
        return False
    return normalize(term) in normalize(text)


def exposure_text(row: dict) -> str:
    values = []
    for key in ("entity", "company", "concept", "role", "summary", "evidence", "source", "source_name", "reason", "chain_layer"):
        values.append(row.get(key, ""))
    for key in ("concepts", "aliases", "tags"):
        values.extend(as_list(row.get(key)))
    return " ".join(str(x) for x in values if str(x).strip())


def iter_exposures(data):
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict):
                yield row
    elif isinstance(data, dict):
        for key in ("exposures", "items", "rows", "data"):
            value = data.get(key)
            if isinstance(value, list):
                for row in value:
                    if isinstance(row, dict):
                        yield row
        for value in data.values():
            if isinstance(value, list):
                for row in value:
                    if isinstance(row, dict) and ("entity" in row or "company" in row):
                        yield row
        entities = data.get("entities")
        if isinstance(entities, dict):
            for entity_name, entity_row in entities.items():
                if not isinstance(entity_row, dict):
                    continue
                concepts = entity_row.get("concepts")
                if not isinstance(concepts, dict):
                    continue
                codes = as_list(entity_row.get("codes"))
                for concept_name, concept_row in concepts.items():
                    if not isinstance(concept_row, dict):
                        continue
                    row = dict(concept_row)
                    row["entity"] = entity_name
                    row["company"] = entity_name
                    row["concept"] = concept_name
                    if codes:
                        row["ticker"] = codes[0]
                    yield row


def company_name(row: dict) -> str:
    return str(row.get("entity") or row.get("company") or row.get("name") or "").strip()


def ticker(row: dict) -> str:
    return str(row.get("ticker") or row.get("code") or row.get("stock_code") or "").strip()


def collect_exposure_candidates(vault: Path, term: str, limit: int) -> list[dict]:
    data = load_json(vault / "relations" / "entity_exposures.json")
    if data is None:
        return []
    terms = [term] + split_terms(term)
    rows = []
    for row in iter_exposures(data):
        text = exposure_text(row)
        score = sum(1 for t in terms if hit(t, text))
        if score <= 0:
            continue
        name = company_name(row)
        if not name:
            continue
        rows.append(
            {
                "company": name,
                "ticker": ticker(row),
                "concept": row.get("concept") or row.get("theme") or "",
                "role": row.get("role") or row.get("summary") or row.get("chain_layer") or "",
                "strength": row.get("strength") or row.get("tier") or row.get("exposure_strength") or "",
                "confidence": row.get("confidence") or row.get("confidence_tier") or "",
                "source": row.get("source") or row.get("source_name") or "",
                "score": score,
            }
        )
    merged = {}
    for row in rows:
        key = row["company"]
        if key not in merged or row["score"] > merged[key]["score"]:
            merged[key] = row
    return sorted(merged.values(), key=lambda x: (-int(x.get("score") or 0), x.get("company", "")))[:limit]


def collect_benchmark_matches(vault: Path, term: str, limit: int) -> list[dict]:
    data = load_json(vault / "relations" / "benchmark_maps.json")
    maps = data.get("maps", []) if isinstance(data, dict) else []
    terms = [term] + split_terms(term)
    rows = []
    for item in maps:
        if not isinstance(item, dict):
            continue
        values = [item.get("benchmark_company", ""), item.get("benchmark_theme", ""), " ".join(as_list(item.get("theme_routes")))]
        for business in item.get("benchmark_business_lines", []) or []:
            if isinstance(business, dict):
                values.extend([business.get("business_line", ""), business.get("definition", ""), " ".join(as_list(business.get("key_products")))])
        text = " ".join(str(x) for x in values)
        score = sum(1 for t in terms if hit(t, text))
        if score > 0:
            rows.append(
                {
                    "benchmark_company": item.get("benchmark_company", ""),
                    "benchmark_ticker": item.get("benchmark_ticker", ""),
                    "theme_routes": as_list(item.get("theme_routes"))[:8],
                    "score": score,
                }
            )
    return sorted(rows, key=lambda x: (-int(x.get("score") or 0), x.get("benchmark_company", "")))[:limit]


def collect_tmp_reports(term: str, limit: int) -> list[dict]:
    if not DEFAULT_TMP.exists():
        return []
    terms = [term] + split_terms(term)
    rows = []
    for path in DEFAULT_TMP.glob("*.md"):
        name = path.name
        if not any(hit(t, name) for t in terms):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rows.append({"path": str(path), "title": name, "chars": len(text), "lines": len(text.splitlines())})
    return sorted(rows, key=lambda x: x["title"])[:limit]


def main():
    parser = argparse.ArgumentParser(description="Build local wiki context for serenity-alpha expectation-gap analysis.")
    parser.add_argument("--term", required=True)
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--out")
    args = parser.parse_args()

    vault = Path(args.vault)
    result = {
        "term": args.term,
        "vault": str(vault),
        "candidate_companies": collect_exposure_candidates(vault, args.term, args.limit),
        "benchmark_matches": collect_benchmark_matches(vault, args.term, 6),
        "tmp_reports": collect_tmp_reports(args.term, 10),
        "usage_note": "Use this as context only. Rank by industrial logic strength, relative price reaction, expectation gap, role purity, and disagreement. Do not turn the output into announcement/financial-statement verification unless explicitly requested.",
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()

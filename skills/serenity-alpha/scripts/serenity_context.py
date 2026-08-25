#!/usr/bin/env python3
"""Build a compact local-wiki context pack for serenity-alpha expectation-gap analysis.

Reads (all read-only):
- relations/aliases.json + concept_graph.json: resolve term -> primary/related concepts
- relations/entity_exposures.json: candidate companies with strength/chain layer/logic-card flag
- relations/evidence_index.json: evidence depth per company
- concepts/*.md: one-line anchor + core logic for matched concepts
- entities/*.md: one-line positioning / current judgement / freshness for candidates
- synthesis/*.md: historical serenity-alpha snapshots matched by filename
- relations/benchmark_maps.json + /private/tmp reports
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path

DEFAULT_VAULT = Path.home() / "knowledge-base-private" / "wiki"
DEFAULT_TMP = Path("/private/tmp")
LOGIC_CARD_TOKENS = ("个股逻辑卡", "最新逻辑卡", "最新逻辑跟踪", "研究素材", "素材整理")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


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


def read_wiki_page(path: Path, max_chars: int = 6000):
    try:
        text = path.read_text(encoding="utf-8")[:max_chars]
    except Exception:
        return {}, ""
    meta, body = {}, text
    match = FRONTMATTER_RE.match(text)
    if match:
        body = text[match.end():]
        for line in match.group(1).splitlines():
            if ":" not in line or line.startswith(" "):
                continue
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    return meta, body


def strip_links(text: str) -> str:
    return WIKI_LINK_RE.sub(r"\1", str(text or ""))


def squeeze(text: str, limit: int = 140) -> str:
    value = " ".join(str(text or "").split()).replace("|", "/")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def section_raw(body: str, names: tuple) -> str:
    for name in names:
        match = re.search(rf"^##+\s*{re.escape(name)}\s*$\n+(.+?)(?=\n##|\Z)", body, re.S | re.M)
        if match:
            return match.group(1)
    return ""


def resolve_concepts(vault: Path, term: str) -> dict:
    aliases_data = load_json(vault / "relations" / "aliases.json") or {}
    graph = load_json(vault / "relations" / "concept_graph.json") or {}
    aliases = aliases_data.get("aliases", {}) if isinstance(aliases_data, dict) else {}
    concepts = graph.get("concepts", {}) if isinstance(graph, dict) else {}
    matched = []
    if term in concepts:
        matched.append(term)
    alias_target = aliases.get(term)
    if alias_target and alias_target in concepts and alias_target not in matched:
        matched.append(alias_target)
    if not matched:
        norm_term = normalize(term)
        for name in concepts:
            if norm_term and (norm_term in normalize(name) or normalize(name) in norm_term):
                matched.append(name)
            if len(matched) >= 4:
                break
    related = []
    for name in matched:
        node = concepts.get(name) or {}
        for rel in as_list(node.get("related_concepts")):
            rel = str(rel).strip()
            if rel and rel not in matched and rel not in related:
                related.append(rel)
    return {"primary": matched[0] if matched else "", "matched": matched, "related": related[:12]}


def load_concept_cards(vault: Path, names: list, limit: int = 6) -> list:
    cards = []
    seen = 0
    for name in names:
        if seen >= limit:
            break
        path = vault / "concepts" / f"{name}.md"
        if not path.exists():
            continue
        seen += 1
        meta, body = read_wiki_page(path)
        one_liner = ""
        match = re.search(r"\*\*一句话\*\*[:：]\s*(.+)", body)
        if match:
            one_liner = squeeze(strip_links(match.group(1)), 130)
        if not one_liner:
            match = re.search(r"^#\s+.+?$\n+([^#\n].+?)(?=\n\*\*|\n#)", body, re.S | re.M)
            if match:
                one_liner = squeeze(strip_links(match.group(1)), 130)
        if one_liner.startswith("占位概念页"):
            one_liner = ""
        core_logic = squeeze(strip_links(section_raw(body, ("核心逻辑", "核心机制", "炒作逻辑"))), 150)
        cards.append({"name": name, "updated": meta.get("updated", ""), "one_liner": one_liner, "core_logic": core_logic})
    return cards


def evidence_counts(vault: Path) -> dict:
    data = load_json(vault / "relations" / "evidence_index.json") or {}
    counts = {}
    for item in data.get("items", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict) or item.get("target_type") != "entity":
            continue
        target = str(item.get("target") or "").strip()
        if target:
            counts[target] = counts.get(target, 0) + 1
    return counts


def collect_exposure_candidates(vault: Path, term: str, concept_scope: list, limit: int) -> list[dict]:
    data = load_json(vault / "relations" / "entity_exposures.json")
    if data is None:
        return []
    terms = [term] + split_terms(term)
    concept_terms = [c for c in concept_scope if c]
    ev_counts = evidence_counts(vault)
    rows = []
    for row in iter_exposures(data):
        text = exposure_text(row)
        term_score = sum(2 for t in terms if hit(t, text))
        concept_score = sum(1 for t in concept_terms if hit(t, str(row.get("concept") or "")))
        score = term_score + concept_score
        if score <= 0:
            continue
        name = company_name(row)
        if not name:
            continue
        sources_text = " ".join(str(x) for x in as_list(row.get("sources")))
        strength = str(row.get("strength") or row.get("tier") or row.get("exposure_strength") or "")
        if strength == "core":
            score += 3
        has_card = any(token in sources_text for token in LOGIC_CARD_TOKENS)
        if has_card:
            score += 2
        rows.append(
            {
                "company": name,
                "ticker": ticker(row),
                "concept": row.get("concept") or row.get("theme") or "",
                "role": row.get("role") or row.get("business_line") or row.get("summary") or "",
                "strength": strength,
                "chain_layer": str(row.get("chain_layer") or ""),
                "confidence": row.get("confidence") or row.get("confidence_tier") or "",
                "source": row.get("source") or row.get("source_name") or "",
                "has_logic_card": has_card,
                "evidence_count": ev_counts.get(name, 0),
                "direct": term_score > 0,
                "score": score,
            }
        )
    merged = {}
    for row in rows:
        key = row["company"]
        hits = [str(row.get("concept") or "").strip()] if str(row.get("concept") or "").strip() else []
        if key not in merged:
            row["concept_hits"] = hits
            merged[key] = row
            continue
        prev = merged[key]
        combined = [c for c in prev.get("concept_hits", []) + hits if c]
        combined = list(dict.fromkeys(combined))
        if (row["direct"], row["score"]) > (prev["direct"], prev["score"]):
            row["concept_hits"] = combined
            merged[key] = row
        else:
            prev["concept_hits"] = combined
    return sorted(
        merged.values(),
        key=lambda x: (not x.get("direct"), -int(x.get("score") or 0), -int(x.get("evidence_count") or 0), x.get("company", "")),
    )[:limit]


def fine_concepts_for(term: str, hits: list) -> list:
    out = []
    for con in hits or []:
        con = str(con).strip()
        if con and term in con and con != term and con not in out:
            out.append(con)
    return sorted(out, key=len, reverse=True)


def fine_position_buckets(term: str, candidates: list) -> dict:
    buckets = {}
    for row in candidates:
        for con in fine_concepts_for(term, row.get("concept_hits", [])):
            names = buckets.setdefault(con, [])
            name = str(row.get("company") or "").strip()
            if name and name not in names:
                names.append(name)
    return buckets


def enrich_with_entity_pages(vault: Path, candidates: list, limit: int = 40) -> None:
    ent_dir = vault / "entities"
    if not ent_dir.exists():
        return
    for row in candidates[:limit]:
        path = ent_dir / f"{row.get('company','')}.md"
        if not path.exists():
            continue
        meta, body = read_wiki_page(path, 3000)
        match = re.search(r"一句话定位[:：]\s*(.+)", body)
        if not match:
            match = re.search(r"^#\s+.+?\n+([^#|\n-][^\n]*)", body, re.M)
        if match:
            one_liner = squeeze(strip_links(match.group(1)), 90)
            if one_liner and "待补" not in one_liner:
                row["wiki_one_liner"] = one_liner
        match = re.search(r"\|\s*当前判断\s*\|\s*([^|\n]+)\|", body)
        if match:
            row["wiki_judgement"] = squeeze(strip_links(match.group(1)), 90)
        if meta.get("updated"):
            row["wiki_updated"] = meta.get("updated")


def collect_synthesis_snapshots(vault: Path, term: str, concept_scope: list, company_names: list, limit: int = 8) -> list:
    syn_dir = vault / "synthesis"
    if not syn_dir.exists():
        return []
    tokens = []
    for t in [term] + list(concept_scope) + list(company_names):
        t = str(t).strip()
        if len(t) >= 2 and t not in tokens:
            tokens.append(t)
    hits = []
    for path in syn_dir.glob("*.md"):
        stem = path.stem
        matched = [t for t in tokens if t in stem]
        if not matched:
            continue
        date_match = re.search(r"(20\d{6})", stem)
        term_hit = 1 if (term and term in stem) else 0
        is_serenity = 1 if "serenity" in stem.lower() else 0
        hits.append((term_hit, is_serenity, date_match.group(1) if date_match else "", path, matched))
    hits.sort(key=lambda item: (item[0], item[1], item[2], item[3].name), reverse=True)
    out = []
    for _th, is_serenity, date_str, path, matched in hits[:limit]:
        meta, body = read_wiki_page(path, 4000)
        summary_raw = ""
        match = re.search(r"^#+ .*(?:核心结论|结论|一句话|定锚|排序).*$\n+(.+?)(?=\n#|\Z)", body, re.S | re.M)
        if match:
            summary_raw = match.group(1)
        else:
            match = re.search(r"^#\s+.+?\n+(.+?)(?=\n#|\Z)", body, re.S)
            summary_raw = match.group(1) if match else body
        summary_text = clean_snapshot_summary(summary_raw)
        if not summary_text:
            summary_text = clean_snapshot_summary(body)
        display_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if date_str else (meta.get("updated") or meta.get("created") or "")
        out.append(
            {
                "title": path.stem,
                "date": display_date,
                "is_serenity": bool(is_serenity),
                "matched": matched[:4],
                "summary": squeeze(strip_links(summary_text), 200),
            }
        )
    return out


def clean_snapshot_summary(raw: str, limit: int = 200) -> str:
    lines = []
    for line in str(raw or "").splitlines():
        s = line.strip()
        if not s or s.startswith("|") or s.startswith("---"):
            continue
        is_heading = s.startswith("#")
        s = re.sub(r"^#+\s*", "", s)
        s = re.sub(r"^>\s*", "", s)
        s = re.sub(r"^[-*]\s*", "", s)
        if re.match(r"^(信息日期|沉淀日期|生成日期|来源|关联节点|用途)[:：]", s):
            continue
        if is_heading and len(s) < 12:
            continue
        if s:
            lines.append(s)
        if len(" ".join(lines)) >= limit:
            break
    return " ".join(lines)


def role_buckets(term: str, concept_scope: list, candidates: list) -> dict:
    theme_tokens = [t for t in ([term] + split_terms(term) + list(concept_scope)) if len(str(t)) >= 2]
    buckets = {"anchor": [], "bottleneck": [], "old_label": [], "diffusion": []}
    for row in candidates:
        name = row.get("company", "")
        role_text = " ".join([str(row.get("role") or ""), str(row.get("chain_layer") or "")])
        one_liner = str(row.get("wiki_one_liner") or "")
        if row.get("strength") == "core":
            buckets["anchor"].append(name)
        elif any(t in role_text for t in ("设备", "材料", "化学品", "药水", "耗材", "靶材", "连接器", "upstream_equipment", "upstream_materials")):
            buckets["bottleneck"].append(name)
        elif one_liner and not any(t in one_liner for t in theme_tokens):
            buckets["old_label"].append(name)
        else:
            buckets["diffusion"].append(name)
    return buckets


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


BUCKET_LABELS = {
    "anchor": "锚候选（strength=core，先确认主线，不一定补涨首选）",
    "bottleneck": "二阶瓶颈候选（设备/材料/化学品/耗材链层）",
    "old_label": "旧标签重估观察（wiki 定位与本题材词不重合，可能被旧主业压价）",
    "diffusion": "扩散观察（逻辑相关但证据/纯度更弱）",
}


def render_markdown(result: dict) -> str:
    term = result.get("term", "")
    concepts = result.get("concepts", {})
    lines = [
        f"# Serenity Alpha 上下文包：{term}",
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        "## 1. 概念定位",
        "",
        f"- 主匹配：{concepts.get('primary') or '未入库'}；命中概念：{('、'.join(concepts.get('matched') or [])) or '无'}",
        f"- 相关概念：{('、'.join((concepts.get('related') or [])[:10])) or '无'}",
    ]
    cards = result.get("concept_cards", []) or []
    if cards:
        lines.extend(["", "| 概念 | 更新 | 一句话定锚 | 核心逻辑 |", "|---|---|---|---|"])
        for card in cards:
            lines.append(
                f"| {card.get('name','')} | {card.get('updated','')} | {card.get('one_liner') or '待补'} | {card.get('core_logic') or '待补'} |"
            )
    candidates = result.get("candidate_companies", []) or []
    lines.extend(
        [
            "",
            "## 2. 候选池（按本地证据强度排序，仍需横向比较 + 涨幅核对）",
            "",
            "| 公司 | 代码 | 命中 | 概念 | 角色/业务线 | 强度 | 证据数 | 逻辑卡 | wiki 一句话定位 | 页更新 |",
            "|---|---|---|---|---|---|---:|---|---|---|",
        ]
    )
    for row in candidates:
        fine = fine_concepts_for(term, row.get("concept_hits", []))
        concept_display = "、".join(fine[:2]) if fine else str(row.get("concept", ""))
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("company", "")),
                    str(row.get("ticker", "")),
                    "直接" if row.get("direct") else "扩散",
                    squeeze(concept_display, 24),
                    squeeze(row.get("role", ""), 44),
                    str(row.get("strength", "") or "—"),
                    str(row.get("evidence_count", 0)),
                    "有" if row.get("has_logic_card") else "—",
                    squeeze(row.get("wiki_one_liner", "") or "待补", 50),
                    str(row.get("wiki_updated", "") or ""),
                ]
            )
            + " |"
        )
    if not candidates:
        lines.append("- 暂无候选：知识库未命中该词，可先跑 theme-radar 新词模式或 concept-ingest 补页后重跑。")
    fine_buckets = fine_position_buckets(term, candidates)
    if fine_buckets:
        lines.extend(["", "### 细分卡位（wiki 细分概念，预期差排序优先看这层）", ""])
        for con, names in sorted(fine_buckets.items(), key=lambda x: -len(x[1])):
            lines.append(f"- **{con}**：{'、'.join(names[:10])}")
    buckets = result.get("role_buckets", {}) or {}
    lines.extend(["", "## 3. 角色预分桶提示（仅启发排序，不是最终结论）", ""])
    bucket_lines = 0
    for key, label in BUCKET_LABELS.items():
        names = buckets.get(key) or []
        if names:
            lines.append(f"- **{label}**：{'、'.join(names[:12])}")
            bucket_lines += 1
    if not bucket_lines:
        lines.append("- 暂无分桶提示。")
    snapshots = result.get("synthesis_snapshots", []) or []
    lines.extend(["", "## 4. 历史 Serenity / 合成研究快照", ""])
    if snapshots:
        lines.extend(["| 日期 | 文件 | 类型 | 核心观点 |", "|---|---|---|---|"])
        for row in snapshots:
            kind = "serenity" if row.get("is_serenity") else "合成研究"
            lines.append(f"| {row.get('date','')} | {row.get('title','')} | {kind} | {row.get('summary','')} |")
        lines.extend(["", "- 历史快照仅作认知线索与防重复劳动，排序必须按当前盘面重做。"])
    else:
        lines.append("- 暂无命中的历史快照。")
    benchmarks = result.get("benchmark_matches", []) or []
    lines.extend(["", "## 5. 海外对标", ""])
    if benchmarks:
        for row in benchmarks:
            lines.append(f"- {row.get('benchmark_company','')}（{row.get('benchmark_ticker','')}）：{('、'.join(row.get('theme_routes') or []))}")
    else:
        lines.append("- 暂无命中的 benchmark map。")
    reports = result.get("tmp_reports", []) or []
    lines.extend(["", "## 6. 可复用临时报告", ""])
    if reports:
        for row in reports:
            lines.append(f"- {row.get('path','')}（{row.get('lines',0)} 行）")
    else:
        lines.append("- 暂无可复用的 /private/tmp 报告，可先跑 theme-radar front-map。")
    lines.extend(
        [
            "",
            "## 7. 使用边界",
            "",
            "- 行情未接入：所有候选默认“涨幅待刷新”，最终排序前先查近 5/10/20 日涨幅（market_feature_store 或腾讯K线）。",
            "- 候选池/分桶只是 wiki 证据视角，材料点名与本表排序都不是最终答案，必须横向比较。",
            "- 本脚本只读 wiki，不写库，不升级公司事实。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="Build local wiki context for serenity-alpha expectation-gap analysis.")
    parser.add_argument("--term", required=True)
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--format", choices=["md", "json"], default="md")
    parser.add_argument("--out")
    args = parser.parse_args()

    vault = Path(args.vault)
    concepts = resolve_concepts(vault, args.term)
    concept_scope = concepts.get("matched", []) + concepts.get("related", [])[:8]
    candidates = collect_exposure_candidates(vault, args.term, concept_scope, args.limit)
    enrich_with_entity_pages(vault, candidates)
    result = {
        "term": args.term,
        "vault": str(vault),
        "concepts": concepts,
        "concept_cards": load_concept_cards(vault, concepts.get("matched", []) + concepts.get("related", [])[:6]),
        "candidate_companies": candidates,
        "fine_position_buckets": fine_position_buckets(args.term, candidates),
        "role_buckets": role_buckets(args.term, concept_scope, candidates),
        "synthesis_snapshots": collect_synthesis_snapshots(
            vault, args.term, concept_scope, [c.get("company", "") for c in candidates[:20]]
        ),
        "benchmark_matches": collect_benchmark_matches(vault, args.term, 6),
        "tmp_reports": collect_tmp_reports(args.term, 10),
        "usage_note": "Use this as context only. Rank by industrial logic strength, relative price reaction, expectation gap, role purity, and disagreement. Do not turn the output into announcement/financial-statement verification unless explicitly requested.",
    }
    text = render_markdown(result) if args.format == "md" else json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")
        print(args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()

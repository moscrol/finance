from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Direct execution needs the repository root on sys.path before project imports.
from intelligence.paths import resolve_knowledge_wiki  # noqa: E402
from market_feature_store.db import connect  # noqa: E402

EXPORT_DIR = ROOT / "market_feature_store" / "exports"
DEFAULT_VAULT = resolve_knowledge_wiki()
CANONICAL_ALIASES = {
    "CCL": "覆铜板",
    "PCB概念": "PCB",
    "芯片概念": "芯片",
}
BROAD_HIGH_DIRECTION_THEMES = {
    "芯片",
    "芯片概念",
    "机器人",
    "机器人概念",
    "人工智能",
    "DeepSeek",
    "DeepSeek概念",
    "AI应用",
    "AI智能体",
    "光伏",
    "储能",
    "军工",
    "固态电池",
    "低空经济",
}


def dict_rows(cur) -> list[dict[str, Any]]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def dict_row(cur) -> dict[str, Any]:
    names = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(names, row)) if row else {}


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def normalize(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "").lower())


def as_list(value: Any) -> list[Any]:
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


def json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 4)
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def exposure_text(row: dict[str, Any]) -> str:
    values = []
    for key in ("entity", "company", "concept", "theme", "role", "summary", "evidence", "source", "source_name", "reason", "chain_layer"):
        values.append(row.get(key, ""))
    for key in ("concepts", "aliases", "tags"):
        values.extend(as_list(row.get(key)))
    return " ".join(str(x) for x in values if str(x).strip())


def evidence_text(row: dict[str, Any]) -> str:
    values = []
    for key in ("entity", "company", "concept", "theme", "title", "summary", "evidence", "source", "source_name", "claim", "content"):
        values.append(row.get(key, ""))
    return " ".join(str(x) for x in values if str(x).strip())


def iter_exposures(data: Any):
    if isinstance(data, dict):
        for row in data.get("items") or []:
            if isinstance(row, dict):
                yield row
        entities = data.get("entities")
        if isinstance(entities, dict):
            for entity_name, entity_row in entities.items():
                if not isinstance(entity_row, dict):
                    continue
                codes = as_list(entity_row.get("codes"))
                concepts = entity_row.get("concepts")
                if isinstance(concepts, dict):
                    for concept_name, concept_row in concepts.items():
                        if isinstance(concept_row, dict):
                            row = dict(concept_row)
                            row["entity"] = entity_name
                            row["company"] = entity_name
                            row["concept"] = concept_name
                            if codes:
                                row["ticker"] = codes[0]
                            yield row
    elif isinstance(data, list):
        for row in data:
            if isinstance(row, dict):
                yield row


class KnowledgeResolver:
    def __init__(self, vault: Path):
        self.vault = vault
        rel = vault / "relations"
        self.concept_graph = load_json(rel / "concept_graph.json", {"concepts": {}, "relations": []})
        self.exposures = load_json(rel / "entity_exposures.json", {"items": [], "entities": {}})
        self.evidence = load_json(rel / "evidence_index.json", {"items": [], "evidence": []})
        self.theme_signals = load_json(rel / "theme_signals.json", {"themes": {}})

    def concept_candidates(self, term: str, limit: int = 5) -> list[dict[str, Any]]:
        concepts = self.concept_graph.get("concepts", {}) if isinstance(self.concept_graph, dict) else {}
        terms = [term, CANONICAL_ALIASES.get(term, term), *split_terms(term)]
        scored = []
        for name, payload in concepts.items():
            text = name + " " + json.dumps(payload, ensure_ascii=False)[:2000]
            score = 0
            for candidate in terms:
                if not candidate:
                    continue
                if normalize(candidate) == normalize(name):
                    score += 10
                elif hit(candidate, name):
                    score += 5
                elif hit(candidate, text):
                    score += 2
            if score > 0:
                scored.append({"concept": name, "score": score})
        return sorted(scored, key=lambda x: (-x["score"], x["concept"]))[:limit]

    def exposure_candidates(self, term: str, limit: int = 12) -> list[dict[str, Any]]:
        terms = [term, CANONICAL_ALIASES.get(term, term), *split_terms(term)]
        rows = []
        for row in iter_exposures(self.exposures):
            text = exposure_text(row)
            score = sum(1 for t in terms if hit(t, text))
            if score <= 0:
                continue
            company = str(row.get("entity") or row.get("company") or row.get("name") or "").strip()
            if not company:
                continue
            rows.append({
                "company": company,
                "ticker": row.get("ticker") or row.get("code") or row.get("stock_code") or "",
                "concept": row.get("concept") or row.get("theme") or "",
                "role": row.get("role") or row.get("summary") or row.get("chain_layer") or "",
                "strength": row.get("strength") or row.get("tier") or row.get("exposure_strength") or "",
                "confidence": row.get("confidence") or row.get("confidence_tier") or "",
                "evidence_layer": row.get("evidence_layer") or row.get("layer") or "",
                "source": row.get("source") or row.get("source_name") or "",
                "score": score,
            })
        merged: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = row["company"]
            if key not in merged or int(row["score"]) > int(merged[key]["score"]):
                merged[key] = row
        return sorted(merged.values(), key=lambda x: (-int(x.get("score") or 0), x.get("company", "")))[:limit]

    def evidence_candidates(self, term: str, limit: int = 8) -> list[dict[str, Any]]:
        items = []
        if isinstance(self.evidence, dict):
            items.extend(self.evidence.get("items") or [])
            items.extend(self.evidence.get("evidence") or [])
        terms = [term, CANONICAL_ALIASES.get(term, term), *split_terms(term)]
        rows = []
        seen = set()
        for row in items:
            if not isinstance(row, dict):
                continue
            text = evidence_text(row)
            score = sum(1 for t in terms if hit(t, text))
            if score <= 0:
                continue
            key = row.get("id") or row.get("source") or row.get("title") or json.dumps(row, ensure_ascii=False)[:80]
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "title": row.get("title") or row.get("source_name") or row.get("source") or "",
                "entity": row.get("entity") or row.get("company") or "",
                "concept": row.get("concept") or row.get("theme") or "",
                "summary": row.get("summary") or row.get("evidence") or row.get("claim") or "",
                "evidence_layer": row.get("evidence_layer") or row.get("layer") or "",
                "quality": row.get("quality") or row.get("confidence") or "",
                "score": score,
            })
        return sorted(rows, key=lambda x: (-int(x.get("score") or 0), x.get("title", "")))[:limit]

    def resolve(self, market_theme: str, canonical_concept: str) -> dict[str, Any]:
        terms = [canonical_concept, market_theme]
        concept_hits = []
        exposure_hits = []
        evidence_hits = []
        for term in terms:
            concept_hits.extend(self.concept_candidates(term, 4))
            exposure_hits.extend(self.exposure_candidates(term, 8))
            evidence_hits.extend(self.evidence_candidates(term, 5))
        concept_seen = set()
        concepts = []
        for row in sorted(concept_hits, key=lambda x: (-x["score"], x["concept"])):
            if row["concept"] in concept_seen:
                continue
            concept_seen.add(row["concept"])
            concepts.append(row)
            if len(concepts) >= 5:
                break
        exposure_seen = set()
        exposures = []
        for row in sorted(exposure_hits, key=lambda x: (-int(x.get("score") or 0), x.get("company", ""))):
            if row["company"] in exposure_seen:
                continue
            exposure_seen.add(row["company"])
            exposures.append(row)
            if len(exposures) >= 12:
                break
        evidence_seen = set()
        evidences = []
        for row in sorted(evidence_hits, key=lambda x: (-int(x.get("score") or 0), x.get("title", ""))):
            key = row.get("title") or row.get("summary")
            if key in evidence_seen:
                continue
            evidence_seen.add(key)
            evidences.append(row)
            if len(evidences) >= 8:
                break
        gaps = []
        if not concepts:
            gaps.append("missing_concept")
        if not exposures:
            gaps.append("missing_entity_exposures")
        if not evidences:
            gaps.append("missing_evidence")
        return {
            "canonical_concept": concepts[0]["concept"] if concepts else canonical_concept,
            "matched_concepts": concepts,
            "candidate_companies": exposures,
            "evidence_items": evidences,
            "knowledge_status": {
                "local_concept_found": bool(concepts),
                "local_exposures_found": bool(exposures),
                "local_evidence_found": bool(evidences),
                "external_supplement_needed": bool(gaps),
                "backfill_gaps": gaps,
            },
        }


def run_gate(trade_date: str) -> dict[str, Any]:
    cmd = [sys.executable, str(ROOT / "scripts" / "check_daily_review_data.py"), trade_date]
    result = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip().splitlines(),
        "stderr": result.stderr.strip().splitlines(),
    }


def add_candidate(candidates: dict[str, dict[str, Any]], theme: str, source: str, score: float, **updates: Any) -> dict[str, Any]:
    if not theme:
        theme = "未命名题材"
    item = candidates.setdefault(
        theme,
        {
            "market_theme": theme,
            "canonical_concept": CANONICAL_ALIASES.get(theme, theme),
            "sw_l1": updates.get("sw_l1") or "",
            "priority_score": 0.0,
            "trigger_types": [],
            "market_evidence": {
                "sector_metrics": {},
                "new_high_stocks": [],
                "strong_stocks": [],
                "limit_up_stocks": [],
                "advance_stocks": [],
                "period_ranks": [],
            },
            "signal_sources": [],
            "knowledge_status": {
                "local_concept_found": None,
                "local_exposures_found": None,
                "external_supplement_needed": None,
                "backfill_gaps": [],
            },
        },
    )
    item["priority_score"] += score
    if source not in item["trigger_types"]:
        item["trigger_types"].append(source)
    if source not in item["signal_sources"]:
        item["signal_sources"].append(source)
    if updates.get("sw_l1") and not item.get("sw_l1"):
        item["sw_l1"] = updates["sw_l1"]
    return item


def merge_unique_rows(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
    seen = {str(row.get(key) or row.get("stock_name") or row) for row in existing}
    out = list(existing)
    for row in incoming:
        marker = str(row.get(key) or row.get("stock_name") or row)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def top_capacity_industries(today: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for idx in range(1, 4):
        name = today.get(f"industry_{idx}")
        ratio = today.get(f"industry_{idx}_ratio")
        if name:
            out.append({"rank": idx, "sw_l1": name, "ratio": ratio})
    return out


def market_pulse(today: dict[str, Any], yesterday: dict[str, Any]) -> str:
    adv = today.get("advancers")
    prev_adv = yesterday.get("advancers")
    sh = today.get("sh_index_pct_chg")
    stage = today.get("market_stage") or ""
    if adv is not None and prev_adv is not None and adv > 3000 and prev_adv < 1200:
        return "冰点后反弹"
    if adv is not None and adv < 1000:
        return "弱势冰点"
    if sh is not None and sh > 1 and adv is not None and adv > 3000:
        return "普涨修复"
    return str(stage or "日终复盘")


def collect_market_context(con, trade_date: str) -> dict[str, Any]:
    today = dict_row(con.execute("SELECT * FROM fact_market_daily WHERE trade_date = ?", [trade_date]))
    prev_date = dict_row(con.execute("SELECT MAX(trade_date) AS trade_date FROM fact_market_daily WHERE trade_date < ?", [trade_date])).get("trade_date")
    yesterday = dict_row(con.execute("SELECT * FROM fact_market_daily WHERE trade_date = ?", [prev_date])) if prev_date else {}
    return {
        "trade_date": trade_date,
        "previous_trade_date": prev_date,
        "market_stage": today.get("market_stage"),
        "stage_day": today.get("stage_day"),
        "market_pulse": market_pulse(today, yesterday),
        "total_amount": today.get("total_amount"),
        "amount_vs_yesterday_pct": today.get("amount_vs_yesterday_pct"),
        "volume_ratio": today.get("volume_ratio"),
        "advancers": today.get("advancers"),
        "previous_advancers": yesterday.get("advancers"),
        "limit_up": today.get("limit_up"),
        "limit_down": today.get("limit_down"),
        "sh_index_pct_chg": today.get("sh_index_pct_chg"),
        "strength_status": today.get("strength_status"),
        "top_capacity_industries": top_capacity_industries(today),
    }


def collect_double_red(con, trade_date: str, candidates: dict[str, dict[str, Any]], top_sw: set[str]) -> list[dict[str, Any]]:
    rows = dict_rows(con.execute(
        """
        SELECT sector_ts_code, sector_name, sw_l1, pct_chg, diff_ratio, amount
        FROM fact_sector_daily
        WHERE trade_date = ? AND pct_chg > 0 AND diff_ratio > 10 AND amount > 500
        ORDER BY diff_ratio DESC, amount DESC
        """,
        [trade_date],
    ))
    for row in rows:
        score = 90 + (10 if row.get("sw_l1") in top_sw else 0)
        item = add_candidate(candidates, row.get("sector_name"), "double_red", score, sw_l1=row.get("sw_l1"))
        item["market_evidence"]["sector_metrics"] = {
            "sector_ts_code": row.get("sector_ts_code"),
            "pct_chg": row.get("pct_chg"),
            "diff_ratio": row.get("diff_ratio"),
            "amount": row.get("amount"),
            "in_capacity_top3": row.get("sw_l1") in top_sw,
        }
        if row.get("sw_l1") in top_sw and "capacity_industry" not in item["trigger_types"]:
            item["trigger_types"].append("capacity_industry")
    return rows


def collect_limit_heat(con, trade_date: str, candidates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = dict_rows(con.execute(
        """
        SELECT sector_name, limit_up_count, total_count, market_share, fd_amount, rank
        FROM fact_theme_limit_heat_daily
        WHERE trade_date = ? AND COALESCE(limit_up_count, 0) >= 2
        ORDER BY limit_up_count DESC, market_share DESC
        LIMIT 30
        """,
        [trade_date],
    ))
    for row in rows:
        score = min(4 + float(row.get("limit_up_count") or 0) * 0.35, 18)
        item = add_candidate(candidates, row.get("sector_name"), "limit_heat", score)
        item["market_evidence"]["limit_heat"] = {
            "limit_up_count": row.get("limit_up_count"),
            "total_count": row.get("total_count"),
            "market_share": row.get("market_share"),
            "fd_amount": row.get("fd_amount"),
            "rank": row.get("rank"),
        }
    return rows


def dominant_sw_for_stocks(con, trade_date: str, stock_codes: list[str]) -> dict[str, Any]:
    if not stock_codes:
        return {"sw_l1": "", "counts": []}
    placeholders = ",".join("?" for _ in stock_codes)
    rows = dict_rows(con.execute(
        f"""
        SELECT sw_l1, COUNT(*) AS cnt
        FROM fact_sector_stock_daily
        WHERE trade_date = ? AND stock_ts_code IN ({placeholders})
          AND sw_l1 IS NOT NULL AND sw_l1 <> ''
        GROUP BY 1
        ORDER BY cnt DESC, sw_l1
        """,
        [trade_date, *stock_codes],
    ))
    return {"sw_l1": rows[0]["sw_l1"] if rows else "", "counts": rows}


def collect_advance(con, trade_date: str, candidates: dict[str, dict[str, Any]], top_sw: set[str]) -> list[dict[str, Any]]:
    rows = dict_rows(con.execute(
        """
        SELECT theme,
               COUNT(*) AS stock_count,
               MAX(boards) AS max_boards,
               string_agg(stock_name, '、' ORDER BY boards DESC, stock_name) AS stock_names,
               string_agg(stock_ts_code, '、' ORDER BY boards DESC, stock_name) AS stock_codes
        FROM fact_limit_advance_daily
        WHERE trade_date = ? AND boards >= 2
        GROUP BY theme
        ORDER BY stock_count DESC, max_boards DESC, theme
        """,
        [trade_date],
    ))
    for row in rows:
        count = int(row.get("stock_count") or 0)
        max_boards = int(row.get("max_boards") or 0)
        stock_codes = [code for code in str(row.get("stock_codes") or "").split("、") if code]
        dominant_sw = dominant_sw_for_stocks(con, trade_date, stock_codes)
        in_capacity = dominant_sw.get("sw_l1") in top_sw
        if count >= 2:
            score = 65 + count * 8 + max_boards * 4 + (18 if in_capacity else 0)
        else:
            score = 18 + max_boards * 3 + (6 if in_capacity else 0)
        item = add_candidate(candidates, row.get("theme") or "连板未映射", "limit_advance_cluster", score, sw_l1=dominant_sw.get("sw_l1"))
        stocks = dict_rows(con.execute(
            """
            WITH advance AS (
              SELECT stock_name, stock_ts_code, boards, pct_chg
              FROM fact_limit_advance_daily
              WHERE trade_date = ? AND theme = ? AND boards >= 2
            ),
            stock_base AS (
              SELECT stock_ts_code,
                     MAX(pct_chg) AS pct_chg,
                     MAX(amount) AS amount,
                     MAX(high_status_label) AS high_status_label
              FROM fact_sector_stock_daily
              WHERE trade_date = ?
                AND stock_ts_code IN (SELECT stock_ts_code FROM advance)
              GROUP BY stock_ts_code
            ),
            high_base AS (
              SELECT stock_ts_code, primary_high_label
              FROM fact_stock_high_daily
              WHERE trade_date = ?
                AND stock_ts_code IN (SELECT stock_ts_code FROM advance)
            )
            SELECT a.stock_name,
                   a.stock_ts_code,
                   a.boards,
                   COALESCE(s.pct_chg, a.pct_chg) AS pct_chg,
                   s.amount,
                   COALESCE(s.high_status_label, h.primary_high_label) AS high_status_label
            FROM advance a
            LEFT JOIN stock_base s ON s.stock_ts_code = a.stock_ts_code
            LEFT JOIN high_base h ON h.stock_ts_code = a.stock_ts_code
            ORDER BY a.boards DESC, s.amount DESC NULLS LAST, a.stock_name
            """,
            [trade_date, row.get("theme"), trade_date, trade_date],
        ))
        stock_details = [
            {
                "stock_name": stock.get("stock_name"),
                "stock_ts_code": stock.get("stock_ts_code"),
                "boards": stock.get("boards"),
                "pct_chg": stock.get("pct_chg"),
                "amount": stock.get("amount"),
                "high_status_label": stock.get("high_status_label"),
            }
            for stock in stocks
        ]
        item["market_evidence"]["advance"] = {
            "stock_count": count,
            "max_boards": max_boards,
            "dominant_sw_l1": dominant_sw.get("sw_l1"),
            "dominant_sw_l1_counts": dominant_sw.get("counts", [])[:5],
            "in_capacity_top3": in_capacity,
        }
        item["market_evidence"]["advance_stocks"] = merge_unique_rows(item["market_evidence"]["advance_stocks"], stock_details, "stock_ts_code", 10)
        item["market_evidence"]["strong_stocks"] = merge_unique_rows(item["market_evidence"]["strong_stocks"], stock_details, "stock_ts_code", 10)
        item["market_evidence"]["new_high_stocks"] = merge_unique_rows(
            item["market_evidence"]["new_high_stocks"],
            [
                {
                    "stock_name": stock.get("stock_name"),
                    "stock_ts_code": stock.get("stock_ts_code"),
                    "high_label": stock.get("high_status_label"),
                    "pct_chg": stock.get("pct_chg"),
                    "amount": stock.get("amount"),
                }
                for stock in stock_details
                if stock.get("high_status_label")
            ],
            "stock_ts_code",
            10,
        )
        if in_capacity and "capacity_industry" not in item["trigger_types"]:
            item["trigger_types"].append("capacity_industry")
    return rows


def collect_period_ranks(con, trade_date: str, candidates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = dict_rows(con.execute(
        """
        SELECT period_type, rank, sector_name, change_pct, limit_up_count, badge
        FROM fact_sector_period_rank_daily
        WHERE trade_date = ? AND rank <= 10
        ORDER BY period_type, rank
        """,
        [trade_date],
    ))
    seen_periods = defaultdict(set)
    for row in rows:
        seen_periods[row.get("sector_name")].add(row.get("period_type"))
    for row in rows:
        periods = seen_periods[row.get("sector_name")]
        score = 6 + max(0, 11 - int(row.get("rank") or 11)) * 0.8 + max(0, len(periods) - 1) * 5
        item = add_candidate(candidates, row.get("sector_name"), "multi_period_rank", score)
        item["market_evidence"]["period_ranks"] = merge_unique_rows(
            item["market_evidence"]["period_ranks"],
            [{
                "period_type": row.get("period_type"),
                "rank": row.get("rank"),
                "change_pct": row.get("change_pct"),
                "limit_up_count": row.get("limit_up_count"),
                "badge": row.get("badge"),
            }],
            "period_type",
            8,
        )
    return rows


def collect_new_high_directions(con, trade_date: str, candidates: dict[str, dict[str, Any]], top_sw: set[str]) -> list[dict[str, Any]]:
    rows = dict_rows(con.execute(
        """
        WITH high_stocks AS (
          SELECT stock_ts_code, stock_name, primary_high_label, amount, pct_chg
          FROM fact_stock_high_daily
          WHERE trade_date = ? AND amount IS NOT NULL
        ),
        joined AS (
          SELECT s.sector_name, s.sw_l1, h.stock_ts_code, h.stock_name, h.primary_high_label, h.amount, h.pct_chg
          FROM fact_sector_stock_daily s
          JOIN high_stocks h ON h.stock_ts_code = s.stock_ts_code
          WHERE s.trade_date = ? AND s.sector_name IS NOT NULL AND s.sector_name <> ''
        )
        SELECT sector_name,
               sw_l1,
               COUNT(DISTINCT stock_ts_code) AS high_count,
               SUM(amount) AS high_amount
        FROM joined
        GROUP BY 1, 2
        HAVING COUNT(DISTINCT stock_ts_code) >= 2 AND SUM(amount) >= 80
        ORDER BY high_amount DESC NULLS LAST, high_count DESC, sector_name
        LIMIT 60
        """,
        [trade_date, trade_date],
    ))
    kept = []
    for row in rows:
        theme = row.get("sector_name")
        if not theme or theme in BROAD_HIGH_DIRECTION_THEMES:
            continue
        high_count = int(row.get("high_count") or 0)
        high_amount = float(row.get("high_amount") or 0)
        in_capacity = row.get("sw_l1") in top_sw
        if high_count < 3 and not in_capacity:
            continue
        score = 18 + min(high_count * 1.4, 22) + min(high_amount / 80, 18) + (10 if in_capacity else 0)
        item = add_candidate(candidates, theme, "new_high_direction", score, sw_l1=row.get("sw_l1"))
        item["market_evidence"]["new_high_direction"] = {
            "high_count": high_count,
            "high_amount": high_amount,
            "in_capacity_top3": in_capacity,
        }
        if in_capacity and "capacity_industry" not in item["trigger_types"]:
            item["trigger_types"].append("capacity_industry")
        kept.append(row)
    return kept


def enrich_theme_stocks(con, trade_date: str, candidates: dict[str, dict[str, Any]], top_sw: set[str]) -> None:
    for theme, item in candidates.items():
        strong_rows = dict_rows(con.execute(
            """
            SELECT stock_name, stock_ts_code, pct_chg, amount, high_status_label, high_status,
                   sqrt(amount) * pct_chg AS weighted
            FROM fact_sector_stock_daily
            WHERE trade_date = ? AND sector_name = ? AND pct_chg IS NOT NULL AND amount IS NOT NULL
            ORDER BY weighted DESC NULLS LAST
            LIMIT 10
            """,
            [trade_date, theme],
        ))
        strong = [
            {
                "stock_name": row.get("stock_name"),
                "stock_ts_code": row.get("stock_ts_code"),
                "pct_chg": row.get("pct_chg"),
                "amount": row.get("amount"),
                "weighted": row.get("weighted"),
                "high_status_label": row.get("high_status_label"),
            }
            for row in strong_rows
        ]
        item["market_evidence"]["strong_stocks"] = merge_unique_rows(item["market_evidence"]["strong_stocks"], strong, "stock_ts_code", 10)
        high_rows = dict_rows(con.execute(
            """
            SELECT DISTINCT h.stock_name, h.stock_ts_code, h.primary_high_label, h.pct_chg, h.amount
            FROM fact_stock_high_daily h
            JOIN fact_sector_stock_daily s ON h.trade_date = s.trade_date AND h.stock_ts_code = s.stock_ts_code
            WHERE h.trade_date = ? AND s.sector_name = ?
            ORDER BY h.amount DESC NULLS LAST
            LIMIT 10
            """,
            [trade_date, theme],
        ))
        highs = [
            {
                "stock_name": row.get("stock_name"),
                "stock_ts_code": row.get("stock_ts_code"),
                "high_label": row.get("primary_high_label"),
                "pct_chg": row.get("pct_chg"),
                "amount": row.get("amount"),
            }
            for row in high_rows
        ]
        item["market_evidence"]["new_high_stocks"] = merge_unique_rows(item["market_evidence"]["new_high_stocks"], highs, "stock_ts_code", 10)
        if len(highs) >= 2:
            item["priority_score"] += min(12 + len(highs) * 2, 26)
            if "new_high_cluster" not in item["trigger_types"]:
                item["trigger_types"].append("new_high_cluster")
        if item.get("sw_l1") in top_sw and "capacity_industry" not in item["trigger_types"]:
            item["trigger_types"].append("capacity_industry")


def finalize_candidates(candidates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for item in candidates.values():
        item["priority_score"] = round(float(item.get("priority_score") or 0), 2)
        evidence = item.get("market_evidence") or {}
        if not evidence.get("sector_metrics"):
            evidence["sector_metrics"] = {}
        items.append(item)
    return sorted(items, key=lambda x: (-float(x.get("priority_score") or 0), x.get("market_theme") or ""))


def attach_knowledge_context(items: list[dict[str, Any]], resolver: KnowledgeResolver | None, limit: int = 10) -> None:
    if resolver is None:
        return
    for item in items[:limit]:
        context = resolver.resolve(str(item.get("market_theme") or ""), str(item.get("canonical_concept") or ""))
        item["canonical_concept"] = context.get("canonical_concept") or item.get("canonical_concept")
        item["knowledge_status"] = context.get("knowledge_status", item.get("knowledge_status", {}))
        item["knowledge_context"] = {
            "matched_concepts": context.get("matched_concepts", []),
            "candidate_companies": context.get("candidate_companies", []),
            "evidence_items": context.get("evidence_items", []),
        }


def build_triggered_themes(trade_date: str, output: Path | None = None, skip_gate: bool = False, vault: Path = DEFAULT_VAULT) -> dict[str, Any]:
    gate = {"ok": True, "returncode": 0, "stdout": [], "stderr": [], "skipped": True} if skip_gate else run_gate(trade_date)
    if not gate["ok"]:
        result = {
            "trade_date": trade_date,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "gate": gate,
            "status": "INCOMPLETE",
            "message": "数据完整性闸门失败，未生成市场题材结论。",
            "market_context": {},
            "deep_themes": [],
            "watch_themes": [],
        }
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(json_safe(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result
    con = connect(read_only=True)
    try:
        market_context = collect_market_context(con, trade_date)
        top_sw = {row["sw_l1"] for row in market_context.get("top_capacity_industries", []) if row.get("sw_l1")}
        candidates: dict[str, dict[str, Any]] = {}
        double_rows = collect_double_red(con, trade_date, candidates, top_sw)
        heat_rows = collect_limit_heat(con, trade_date, candidates)
        advance_rows = collect_advance(con, trade_date, candidates, top_sw)
        period_rows = collect_period_ranks(con, trade_date, candidates)
        high_direction_rows = collect_new_high_directions(con, trade_date, candidates, top_sw)
        enrich_theme_stocks(con, trade_date, candidates, top_sw)
        ranked = finalize_candidates(candidates)
        resolver = KnowledgeResolver(vault) if vault.exists() else None
        attach_knowledge_context(ranked, resolver, 10)
        result = {
            "trade_date": trade_date,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "gate": gate,
            "status": "COMPLETE",
            "market_context": market_context,
            "knowledge_base": {
                "vault": str(vault),
                "resolver_enabled": resolver is not None,
            },
            "signal_summary": {
                "double_red_count": len(double_rows),
                "limit_heat_count": len(heat_rows),
                "limit_advance_theme_count": len(advance_rows),
                "multi_period_row_count": len(period_rows),
                "new_high_direction_count": len(high_direction_rows),
                "candidate_theme_count": len(ranked),
            },
            "new_high_directions": [
                {
                    "sector_name": row.get("sector_name"),
                    "canonical_concept": CANONICAL_ALIASES.get(row.get("sector_name"), row.get("sector_name")),
                    "sw_l1": row.get("sw_l1"),
                    "high_count": row.get("high_count"),
                    "high_amount": row.get("high_amount"),
                    "in_capacity_top3": row.get("sw_l1") in top_sw,
                }
                for row in high_direction_rows[:20]
            ],
            "deep_themes": ranked[:3],
            "watch_themes": ranked[3:10],
        }
    finally:
        con.close()
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(json_safe(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def clean_text(value: Any, limit: int | None = None) -> str:
    text = str(value or "").replace("|", "／").replace("\n", " ").strip()
    if limit and len(text) > limit:
        return text[: limit - 1] + "…"
    return text or "-"


def fmt_num(value: Any, digits: int = 2) -> str:
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return clean_text(value)


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "- 无。"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(clean_text(cell) for cell in row) + " |")
    return "\n".join(out)


def trigger_text(triggers: list[str]) -> str:
    names = {
        "double_red": "双红",
        "capacity_industry": "容量行业",
        "new_high_direction": "新高方向",
        "new_high_cluster": "新高集群",
        "limit_advance_cluster": "连板集群",
        "limit_heat": "涨停热度",
        "multi_period_rank": "多周期强势",
    }
    return "、".join(names.get(t, t) for t in triggers) or "-"


def stock_list(rows: list[dict[str, Any]], limit: int = 8) -> str:
    names = []
    for row in rows[:limit]:
        name = row.get("stock_name") or row.get("company")
        if not name:
            continue
        label = row.get("high_label") or row.get("high_status_label") or row.get("pct_chg")
        names.append(f"{name}（{clean_text(label, 16)}）" if label else str(name))
    return "、".join(names) if names else "-"


def market_overview_section(data: dict[str, Any]) -> str:
    ctx = data.get("market_context", {})
    top_capacity = "、".join(
        f"{row.get('sw_l1')}({fmt_num(row.get('ratio'), 1)}%)"
        for row in ctx.get("top_capacity_industries", [])
        if row.get("sw_l1")
    )
    return md_table(
        ["项目", "数值"],
        [
            ["市场脉络", ctx.get("market_pulse")],
            ["市场阶段", f"{ctx.get('market_stage') or '-'} 第{ctx.get('stage_day') or '-'}天"],
            ["成交额", f"{fmt_num(ctx.get('total_amount'), 1)} 亿"],
            ["较昨日成交", f"{fmt_num(ctx.get('amount_vs_yesterday_pct'), 2)}%"],
            ["20日量比", f"{fmt_num(ctx.get('volume_ratio'), 2)}%"],
            ["涨家数", ctx.get("advancers")],
            ["涨停/跌停", f"{ctx.get('limit_up') or '-'} / {ctx.get('limit_down') or '-'}"],
            ["上证涨跌", f"{fmt_num(ctx.get('sh_index_pct_chg'), 2)}%"],
            ["容量前三", top_capacity or "-"],
            ["强度状态", ctx.get("strength_status")],
        ],
    )


def theme_overview_rows(items: list[dict[str, Any]]) -> list[list[Any]]:
    rows = []
    for item in items:
        ev = item.get("market_evidence", {})
        metrics = ev.get("sector_metrics", {})
        high_dir = ev.get("new_high_direction", {})
        advance = ev.get("advance", {})
        rows.append([
            item.get("market_theme"),
            item.get("canonical_concept"),
            item.get("sw_l1"),
            item.get("priority_score"),
            trigger_text(item.get("trigger_types", [])),
            f"{fmt_num(metrics.get('pct_chg'), 2)}% / {fmt_num(metrics.get('diff_ratio'), 2)} / {fmt_num(metrics.get('amount'), 1)}亿" if metrics else "-",
            f"{high_dir.get('high_count') or '-'}只 / {fmt_num(high_dir.get('high_amount'), 1)}亿" if high_dir else "-",
            f"{advance.get('stock_count') or '-'}只 / {advance.get('max_boards') or '-'}板" if advance else "-",
        ])
    return rows


def knowledge_summary(item: dict[str, Any]) -> str:
    status = item.get("knowledge_status", {})
    found = []
    if status.get("local_concept_found"):
        found.append("概念")
    if status.get("local_exposures_found"):
        found.append("公司暴露")
    if status.get("local_evidence_found"):
        found.append("证据")
    gaps = status.get("backfill_gaps") or []
    if gaps:
        return f"本地已命中：{'、'.join(found) or '-'}；待补：{'、'.join(gaps)}。"
    return f"本地知识库已命中：{'、'.join(found) or '-'}。"


def validation_points(item: dict[str, Any]) -> list[str]:
    triggers = set(item.get("trigger_types", []))
    points = []
    if "double_red" in triggers:
        points.append("观察题材次日是否继续保持涨幅为正、边际量大于 10、成交额不明显塌缩。")
    if "new_high_direction" in triggers or "new_high_cluster" in triggers:
        points.append("观察新高股是否继续扩散，还是高位核心冲高回落导致新高方向转分歧。")
    if "limit_advance_cluster" in triggers:
        points.append("观察连板股是否晋级或卡位失败，尤其是同题材内部是否出现唯一性龙头。")
    if "capacity_industry" in triggers:
        points.append("观察题材是否继续留在成交占比前三行业内，避免从主线容量退化为孤立情绪。")
    if not points:
        points.append("观察是否出现新的双红、涨停或新高确认，否则仅保留观察。")
    return points


def render_theme_section(item: dict[str, Any], index: int) -> str:
    ev = item.get("market_evidence", {})
    kc = item.get("knowledge_context", {})
    metrics = ev.get("sector_metrics", {})
    high_dir = ev.get("new_high_direction", {})
    advance = ev.get("advance", {})
    limit_heat = ev.get("limit_heat", {})
    lines = [
        f"## {index + 3}. 深度题材：{clean_text(item.get('market_theme'))} → {clean_text(item.get('canonical_concept'))}",
        "",
        "### 盘面触发",
        "",
        f"- **触发类型**：{trigger_text(item.get('trigger_types', []))}",
        f"- **优先级评分**：{item.get('priority_score')}",
    ]
    if metrics:
        lines.append(f"- **双红证据**：涨幅 {fmt_num(metrics.get('pct_chg'), 2)}%，边际量 {fmt_num(metrics.get('diff_ratio'), 2)}，成交额 {fmt_num(metrics.get('amount'), 1)} 亿。")
    if high_dir:
        lines.append(f"- **新高方向**：{high_dir.get('high_count')} 只新高，新高成交额 {fmt_num(high_dir.get('high_amount'), 1)} 亿。")
    if advance:
        lines.append(f"- **连板证据**：{advance.get('stock_count')} 只连板，最高 {advance.get('max_boards')} 板，主映射行业 {advance.get('dominant_sw_l1') or '-'}。")
    if limit_heat:
        lines.append(f"- **涨停热度**：{limit_heat.get('limit_up_count')} 只涨停，市场占比 {fmt_num(limit_heat.get('market_share'), 2)}%。")
    lines.extend([
        "",
        "### 知识库解释",
        "",
        f"- **覆盖状态**：{knowledge_summary(item)}",
        f"- **匹配概念**：{stock_list([{'stock_name': row.get('concept'), 'high_label': row.get('score')} for row in kc.get('matched_concepts', [])], 6)}",
        "",
        "### 核心公司分层候选",
        "",
        md_table(
            ["公司", "代码", "概念", "角色/摘要", "强度", "证据层"],
            [
                [
                    row.get("company"),
                    row.get("ticker"),
                    row.get("concept"),
                    clean_text(row.get("role"), 48),
                    row.get("strength"),
                    row.get("evidence_layer"),
                ]
                for row in kc.get("candidate_companies", [])[:10]
            ],
        ),
        "",
        "### 今日市场验证股票",
        "",
        f"- **强势成交股**：{stock_list(ev.get('strong_stocks', []), 8)}",
        f"- **新高股**：{stock_list(ev.get('new_high_stocks', []), 8)}",
        f"- **连板股**：{stock_list(ev.get('advance_stocks', []), 8)}",
        "",
        "### 本地证据样本",
        "",
        md_table(
            ["标题/来源", "实体", "概念", "摘要", "层级"],
            [
                [
                    clean_text(row.get("title"), 32),
                    row.get("entity"),
                    row.get("concept"),
                    clean_text(row.get("summary"), 60),
                    row.get("evidence_layer") or row.get("quality"),
                ]
                for row in kc.get("evidence_items", [])[:5]
            ],
        ),
        "",
        "### 次日验证点",
        "",
    ])
    lines.extend(f"- {point}" for point in validation_points(item))
    return "\n".join(lines)


def render_markdown(data: dict[str, Any]) -> str:
    if data.get("status") != "COMPLETE":
        return "\n".join([
            f"# {data.get('trade_date')} 盘面触发题材雷达",
            "",
            "数据完整性闸门失败，未生成市场题材结论。",
            "",
            "```text",
            "\n".join(data.get("gate", {}).get("stdout", [])),
            "```",
            "",
        ])
    deep = data.get("deep_themes", [])
    watch = data.get("watch_themes", [])
    lines = [
        f"# {data.get('trade_date')} 盘面触发题材雷达",
        "",
        f"- **生成时间**：{data.get('generated_at')}",
        f"- **知识库**：{data.get('knowledge_base', {}).get('vault')}（resolver={data.get('knowledge_base', {}).get('resolver_enabled')}）",
        "",
        "## 一、今日市场脉络",
        "",
        market_overview_section(data),
        "",
        "## 二、触发题材总览",
        "",
        md_table(
            ["题材", "标准概念", "申万一级", "评分", "触发", "双红", "新高方向", "连板"],
            theme_overview_rows(deep + watch),
        ),
        "",
        "## 三、新高方向独立扫描",
        "",
        md_table(
            ["新高方向", "标准概念", "申万一级", "新高数", "新高成交额亿", "容量前三"],
            [
                [
                    row.get("sector_name"),
                    row.get("canonical_concept"),
                    row.get("sw_l1"),
                    row.get("high_count"),
                    fmt_num(row.get("high_amount"), 1),
                    "是" if row.get("in_capacity_top3") else "否",
                ]
                for row in data.get("new_high_directions", [])[:12]
            ],
        ),
        "",
    ]
    for index, item in enumerate(deep, 1):
        lines.extend([render_theme_section(item, index), ""])
    lines.extend([
        "## 七、简要观察题材",
        "",
        md_table(
            ["题材", "标准概念", "申万一级", "评分", "触发", "市场验证", "知识库状态"],
            [
                [
                    item.get("market_theme"),
                    item.get("canonical_concept"),
                    item.get("sw_l1"),
                    item.get("priority_score"),
                    trigger_text(item.get("trigger_types", [])),
                    f"强势：{stock_list(item.get('market_evidence', {}).get('strong_stocks', []), 3)}；新高：{stock_list(item.get('market_evidence', {}).get('new_high_stocks', []), 3)}；连板：{stock_list(item.get('market_evidence', {}).get('advance_stocks', []), 3)}",
                    knowledge_summary(item),
                ]
                for item in watch
            ],
        ),
        "",
        "## 八、今日总结",
        "",
        f"- 今日深度题材为：{'、'.join(item.get('market_theme', '') for item in deep) or '-'}。",
        f"- 新高方向中，容量前三行业内较突出的包括：{'、'.join(row.get('sector_name', '') for row in data.get('new_high_directions', []) if row.get('in_capacity_top3')) or '-'}。",
        "- 后续应优先验证深度题材是否继续留在容量行业内，并观察新高集群是否从单日修复升级为连续扩散。",
        "",
    ])
    return "\n".join(lines)


def write_brief(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(data), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成日终盘面触发题材 JSON。")
    parser.add_argument("trade_date", help="交易日 YYYY-MM-DD")
    parser.add_argument("--output", default=None, help="输出 JSON 路径，默认 market_feature_store/exports/YYYY-MM-DD-triggered-themes.json")
    parser.add_argument("--brief-output", default=None, help="输出 Markdown 简报路径，默认 market_feature_store/exports/YYYY-MM-DD-market-triggered-theme-brief.md")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT), help="知识库 wiki 目录，默认 resolve_knowledge_wiki()")
    parser.add_argument("--json-only", action="store_true", help="只生成 JSON，不生成 Markdown 简报")
    parser.add_argument("--skip-gate", action="store_true", help="跳过完整性闸门，仅用于调试")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = Path(args.output) if args.output else EXPORT_DIR / f"{args.trade_date}-triggered-themes.json"
    result = build_triggered_themes(args.trade_date, out, args.skip_gate, Path(args.vault).expanduser())
    brief_out = Path(args.brief_output) if args.brief_output else EXPORT_DIR / f"{args.trade_date}-market-triggered-theme-brief.md"
    if not args.json_only:
        write_brief(result, brief_out)
    print(out)
    if not args.json_only:
        print(brief_out)
    print(result.get("status"))
    for item in result.get("deep_themes", []):
        print(f"DEEP {item['priority_score']}: {item['market_theme']} / {item['canonical_concept']} / {','.join(item['trigger_types'])}")
    for item in result.get("watch_themes", [])[:5]:
        print(f"WATCH {item['priority_score']}: {item['market_theme']} / {item['canonical_concept']} / {','.join(item['trigger_types'])}")
    return 0 if result.get("status") == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

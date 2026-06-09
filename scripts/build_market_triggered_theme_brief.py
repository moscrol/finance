from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_feature_store.db import connect

EXPORT_DIR = ROOT / "market_feature_store" / "exports"
CANONICAL_ALIASES = {
    "CCL": "覆铜板",
    "PCB概念": "PCB",
    "芯片概念": "芯片",
}


def dict_rows(cur) -> list[dict[str, Any]]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def dict_row(cur) -> dict[str, Any]:
    names = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(names, row)) if row else {}


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
        stocks = []
        for name in str(row.get("stock_names") or "").split("、"):
            if name:
                stocks.append({"stock_name": name})
        item["market_evidence"]["advance"] = {
            "stock_count": count,
            "max_boards": max_boards,
            "dominant_sw_l1": dominant_sw.get("sw_l1"),
            "dominant_sw_l1_counts": dominant_sw.get("counts", [])[:5],
            "in_capacity_top3": in_capacity,
        }
        item["market_evidence"]["advance_stocks"] = merge_unique_rows(item["market_evidence"]["advance_stocks"], stocks, "stock_name", 10)
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


def build_triggered_themes(trade_date: str, output: Path | None = None, skip_gate: bool = False) -> dict[str, Any]:
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
        enrich_theme_stocks(con, trade_date, candidates, top_sw)
        ranked = finalize_candidates(candidates)
        result = {
            "trade_date": trade_date,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "gate": gate,
            "status": "COMPLETE",
            "market_context": market_context,
            "signal_summary": {
                "double_red_count": len(double_rows),
                "limit_heat_count": len(heat_rows),
                "limit_advance_theme_count": len(advance_rows),
                "multi_period_row_count": len(period_rows),
                "candidate_theme_count": len(ranked),
            },
            "deep_themes": ranked[:3],
            "watch_themes": ranked[3:10],
        }
    finally:
        con.close()
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(json_safe(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成日终盘面触发题材 JSON。")
    parser.add_argument("trade_date", help="交易日 YYYY-MM-DD")
    parser.add_argument("--output", default=None, help="输出 JSON 路径，默认 market_feature_store/exports/YYYY-MM-DD-triggered-themes.json")
    parser.add_argument("--skip-gate", action="store_true", help="跳过完整性闸门，仅用于调试")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = Path(args.output) if args.output else EXPORT_DIR / f"{args.trade_date}-triggered-themes.json"
    result = build_triggered_themes(args.trade_date, out, args.skip_gate)
    print(out)
    print(result.get("status"))
    for item in result.get("deep_themes", []):
        print(f"DEEP {item['priority_score']}: {item['market_theme']} / {item['canonical_concept']} / {','.join(item['trigger_types'])}")
    for item in result.get("watch_themes", [])[:5]:
        print(f"WATCH {item['priority_score']}: {item['market_theme']} / {item['canonical_concept']} / {','.join(item['trigger_types'])}")
    return 0 if result.get("status") == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

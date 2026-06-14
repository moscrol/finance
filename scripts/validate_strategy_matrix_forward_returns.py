from __future__ import annotations

import argparse
import html
import json
import re
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_feature_store.db import connect

EXPORTS = ROOT / "market_feature_store/exports"
MATRICES = {
    "1": ROOT / "复盘/matrices/strategy1-priority-stock-matrix.html",
    "3": ROOT / "复盘/matrices/strategy3-touch-up-rebound-matrix.html",
    "4": ROOT / "复盘/matrices/strategy4-dual-engine-matrix.html",
}
HORIZONS = (1, 3, 5)
CODE_RE = re.compile(r"\b(\d{6}\.(?:SH|SZ|BJ))\b")


LABELS = [
    "T1-", "T1", "T2", "OBS", "DEG",
    "S3-L-A-E1", "S3-L-A-E2", "S3-L-A-E3", "S3-L-B", "提前观察",
    "引擎A", "引擎B", "双引擎", "SELL", "RISK",
]


def normalize_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return " ".join(s.split())


def row_for_date(matrix: Path, date: str) -> str | None:
    text = matrix.read_text(encoding="utf-8")
    m = re.search(rf'<tr[^>]*>\s*<td class="date">{re.escape(date)}</td>.*?</tr>', text, re.S)
    return m.group(0) if m else None


def cells(row: str) -> list[str]:
    return re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)


def stock_blocks(cell: str) -> list[str]:
    parts = re.split(r'(?=<span class="stock")', cell)
    return [p for p in parts if p.startswith('<span class="stock')]


def name_before_code(text: str, code: str) -> str:
    pre = text.split(code, 1)[0]
    for label in LABELS:
        pre = pre.replace(label, " ")
    name = " ".join(pre.split()).strip()
    return name.split()[-1] if name else ""


def candidate(strategy: str, bucket: str, block: str, date: str) -> dict[str, Any] | None:
    text = normalize_text(block)
    m = CODE_RE.search(text)
    if not m:
        return None
    code = m.group(1)
    name = name_before_code(text, code)
    if not name:
        return None
    label = bucket
    if strategy == "4" and "双引擎" in text:
        label = bucket + "+dual"
    return {
        "date": date,
        "strategy": strategy,
        "bucket": label,
        "stock_ts_code": code,
        "stock_name": name,
        "source_text": text[:260],
    }


def extract_strategy1(date: str) -> list[dict[str, Any]]:
    row = row_for_date(MATRICES["1"], date)
    if not row:
        return []
    cs = cells(row)
    if len(cs) < 3:
        return []
    out = []
    for block in stock_blocks(cs[2]):
        text = normalize_text(block)
        if not (text.startswith("T1 ") or text.startswith("T1- ") or " T1 " in text or " T1- " in text):
            continue
        item = candidate("1", "t1", block, date)
        if item:
            if text.startswith("T1-") or "T1-" in text[:12]:
                item["bucket"] = "t1_minus"
            out.append(item)
    return out


def extract_strategy3(date: str) -> list[dict[str, Any]]:
    row = row_for_date(MATRICES["3"], date)
    if not row:
        return []
    cs = cells(row)
    out = []
    if len(cs) > 2:
        for block in stock_blocks(cs[2]):
            text = normalize_text(block)
            if "S3-L-A" in text:
                item = candidate("3", "s3_l_a_touch", block, date)
                if item:
                    out.append(item)
    if len(cs) > 3:
        for block in stock_blocks(cs[3]):
            text = normalize_text(block)
            if "S3-L-B" in text:
                item = candidate("3", "s3_l_b_window", block, date)
                if item:
                    out.append(item)
    return out


def extract_strategy4(date: str) -> list[dict[str, Any]]:
    row = row_for_date(MATRICES["4"], date)
    if not row:
        return []
    cs = cells(row)
    out = []
    if len(cs) > 2:
        for block in stock_blocks(cs[2]):
            text = normalize_text(block)
            if "引擎A" in text:
                item = candidate("4", "engine_a", block, date)
                if item:
                    out.append(item)
    if len(cs) > 3:
        for block in stock_blocks(cs[3]):
            text = normalize_text(block)
            if "引擎B" in text:
                item = candidate("4", "engine_b", block, date)
                if item:
                    out.append(item)
    return out


def dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        key = (item["strategy"], item["bucket"], item["stock_ts_code"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def trading_dates(con, date: str) -> list[str]:
    return [str(x[0]) for x in con.execute(
        "SELECT DISTINCT trade_date FROM fact_stock_daily WHERE trade_date >= ? ORDER BY trade_date",
        [date],
    ).fetchall()]


def attach_returns(date: str, items: list[dict[str, Any]]) -> None:
    if not items:
        return
    con = connect(read_only=True)
    try:
        dates = trading_dates(con, date)
        targets = {h: (dates[h] if h < len(dates) else None) for h in HORIZONS}
        codes = sorted({x["stock_ts_code"] for x in items})
        params = [date] + [d for d in targets.values() if d] + codes
        day_slots = [date] + [d for d in targets.values() if d]
        placeholders_days = ",".join(["?"] * len(day_slots))
        placeholders_codes = ",".join(["?"] * len(codes))
        rows = con.execute(
            f"""
            SELECT stock_ts_code, CAST(trade_date AS VARCHAR), close
            FROM fact_stock_daily
            WHERE trade_date IN ({placeholders_days})
              AND stock_ts_code IN ({placeholders_codes})
            """,
            params,
        ).fetchall()
    finally:
        con.close()
    prices = {(code, day): close for code, day, close in rows}
    for item in items:
        code = item["stock_ts_code"]
        base = prices.get((code, date))
        item["base_close"] = base
        item["forward_returns"] = {}
        for h, target in targets.items():
            key = f"t{h}"
            if not target or base in (None, 0):
                item["forward_returns"][key] = {"status": "pending", "target_date": target, "ret_pct": None}
                continue
            close = prices.get((code, target))
            if close is None:
                item["forward_returns"][key] = {"status": "missing", "target_date": target, "ret_pct": None}
                continue
            item["forward_returns"][key] = {
                "status": "ok",
                "target_date": target,
                "ret_pct": round((close / base - 1) * 100, 2),
            }


def metric(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "avg": None, "median": None, "win_rate": None, "strong_hit_rate": None, "fail_rate": None}
    return {
        "n": len(values),
        "avg": round(st.mean(values), 2),
        "median": round(st.median(values), 2),
        "win_rate": round(sum(v > 0 for v in values) / len(values) * 100, 2),
        "strong_hit_rate": round(sum(v >= 5 for v in values) / len(values) * 100, 2),
        "fail_rate": round(sum(v <= -5 for v in values) / len(values) * 100, 2),
    }


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        groups["all"].append(item)
        groups[f"strategy_{item['strategy']}"].append(item)
        groups[f"strategy_{item['strategy']}:{item['bucket']}"].append(item)
    summary = {}
    for group, xs in sorted(groups.items()):
        g = {"sample_count": len(xs), "horizons": {}}
        for h in HORIZONS:
            key = f"t{h}"
            vals = [x["forward_returns"][key]["ret_pct"] for x in xs if x["forward_returns"][key]["status"] == "ok"]
            g["horizons"][key] = metric(vals)
            g["horizons"][key]["pending"] = sum(x["forward_returns"][key]["status"] == "pending" for x in xs)
            g["horizons"][key]["missing"] = sum(x["forward_returns"][key]["status"] == "missing" for x in xs)
        summary[group] = g
    return summary


def render_md(date: str, items: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [f"# 策略矩阵回溯验证 {date}", "", "## 摘要", ""]
    lines.append("| 分组 | 样本 | T+1胜率 | T+1均值 | T+3胜率 | T+3均值 | T+5胜率 | T+5均值 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for group, g in summary.items():
        hs = g["horizons"]
        def fmt(v):
            return "pending" if v is None else str(v)
        lines.append(
            f"| {group} | {g['sample_count']} | {fmt(hs['t1']['win_rate'])} | {fmt(hs['t1']['avg'])} | "
            f"{fmt(hs['t3']['win_rate'])} | {fmt(hs['t3']['avg'])} | {fmt(hs['t5']['win_rate'])} | {fmt(hs['t5']['avg'])} |"
        )
    lines += ["", "## 明细", "", "| 策略 | 分层 | 股票 | 代码 | T+1 | T+3 | T+5 |", "|---|---|---|---|---:|---:|---:|"]
    for item in items:
        def ret(k):
            r = item["forward_returns"][k]
            return "pending" if r["status"] == "pending" else "missing" if r["status"] == "missing" else f"{r['ret_pct']:.2f}%"
        lines.append(
            f"| {item['strategy']} | {item['bucket']} | {item['stock_name']} | {item['stock_ts_code']} | {ret('t1')} | {ret('t3')} | {ret('t5')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--strategies", default="1,3,4")
    p.add_argument("--out-prefix", default=None)
    args = p.parse_args()
    wanted = {x.strip() for x in args.strategies.split(",") if x.strip()}
    items = []
    if "1" in wanted:
        items += extract_strategy1(args.date)
    if "3" in wanted:
        items += extract_strategy3(args.date)
    if "4" in wanted:
        items += extract_strategy4(args.date)
    items = dedupe(items)
    attach_returns(args.date, items)
    summary = summarize(items)
    payload = {
        "date": args.date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "horizons": list(HORIZONS),
        "items": items,
        "summary": summary,
    }
    prefix = Path(args.out_prefix) if args.out_prefix else EXPORTS / f"{args.date}-strategy-forward-validation"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = prefix.with_suffix(".json")
    md_path = prefix.with_suffix(".md")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_md(args.date, items, summary), encoding="utf-8")
    print(json_path)
    print(md_path)
    print(json.dumps({"date": args.date, "items": len(items), "groups": len(summary)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

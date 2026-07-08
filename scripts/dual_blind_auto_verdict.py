#!/usr/bin/env python3
"""双盲答卷机判 verdict：按答卷自带数值阈值对照 DuckDB 实际值，自动裁定 hit/miss/partial。

定位：nightly recheck 之后的自动裁定步骤。只做机器能硬判的部分：
- market / falsify：从 thresholds/hypotheses 文本抽取数值条件（涨家数/涨停/跌停/成交额/量比/历史新高，
  支持 >= <= > < 与区间 a-b、万亿/亿 单位），证伪条件触发即 miss；预期区间全满足即 hit；
  介于两者之间判 partial；抽不出条件判 unverifiable。
- direction：从方向假设文本匹配当日 fact_sector_daily 板块名，按双红（pct>0 且 diff_ratio>0）比例裁定。
- target:<code>：优先抽取收盘阈值（站稳/不跌破/t1_close_min/破X），否则按 T+1 是否跑赢上证裁定。

机判结果 failure_mode 标注「机判」，人工可在 verdict.json 上直接改判（人工优先）。
已存在 <date>.verdict.json 时默认跳过（--force 覆盖），避免踩掉人工裁决。

用法::

    python3 scripts/dual_blind_auto_verdict.py --date 2026-07-07 [--date ...] [--force]
    python3 scripts/dual_blind_auto_verdict.py --all-pending   # 所有已有答卷、已有当日行情、未裁定的日期
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dual_blind_forecast import (  # noqa: E402
    DB_PATH,
    LEDGER_DIR,
    answer_paths_for,
    render_verdict_md,
    validate_verdict,
    verdict_path_for,
)

METRIC_ALIASES = {
    "涨家数": "advancers",
    "涨停家数": "limit_up",
    "涨停数": "limit_up",
    "涨停": "limit_up",
    "跌停家数": "limit_down",
    "跌停数": "limit_down",
    "跌停": "limit_down",
    "成交额": "total_amount",
    "量比": "volume_ratio",
    "历史新高数": "high_history",
    "历史新高": "high_history",
}
_METRIC_RE = "|".join(sorted(METRIC_ALIASES, key=len, reverse=True))
_NUM = r"([0-9]+(?:\.[0-9]+)?)"
_UNIT = r"(万亿|亿)?"
COND_RE = re.compile(rf"({_METRIC_RE})[^0-9<>≥≤=区间\-]{{0,6}}(>=|<=|≥|≤|>|<)\s*{_NUM}{_UNIT}")
RANGE_RE = re.compile(rf"({_METRIC_RE})[^0-9<>≥≤=]{{0,6}}{_NUM}{_UNIT}\s*[-~—]\s*{_NUM}{_UNIT}")
CLAUSE_SPLIT = re.compile(r"[；;。\n]")
OR_SPLIT = re.compile(r"或(?:者)?")


def _to_number(raw: str, unit: str | None) -> float:
    value = float(raw)
    if unit == "万亿":
        value *= 10000.0
    return value


def extract_conditions(text: str) -> list[tuple[str, str, float, float | None]]:
    """返回 (metric, op, lo, hi)；op 为比较符或 'range'。"""
    out: list[tuple[str, str, float, float | None]] = []
    for m in RANGE_RE.finditer(text):
        metric = METRIC_ALIASES[m.group(1)]
        lo = _to_number(m.group(2), m.group(3))
        hi = _to_number(m.group(4), m.group(5))
        out.append((metric, "range", lo, hi))
    stripped = RANGE_RE.sub(" ", text)
    for m in COND_RE.finditer(stripped):
        metric = METRIC_ALIASES[m.group(1)]
        op = {"≥": ">=", "≤": "<="}.get(m.group(2), m.group(2))
        out.append((metric, op, _to_number(m.group(3), m.group(4)), None))
    return out


def eval_conditions(conds: list[tuple[str, str, float, float | None]], vals: dict[str, float | None]) -> bool | None:
    """全部条件 AND；有条件的 metric 缺实际值返回 None（不可判）。空列表返回 None。"""
    if not conds:
        return None
    for metric, op, lo, hi in conds:
        actual = vals.get(metric)
        if actual is None:
            return None
        if op == "range":
            ok = lo <= actual <= (hi if hi is not None else lo)
        elif op == ">=":
            ok = actual >= lo
        elif op == "<=":
            ok = actual <= lo
        elif op == ">":
            ok = actual > lo
        else:
            ok = actual < lo
        if not ok:
            return False
    return True


def any_clause_true(text: str, vals: dict[str, float | None]) -> bool | None:
    """按 ；/。切子句、子句内按 或 切分支；任一分支条件全真即 True。全不可判返回 None。"""
    saw = False
    for clause in CLAUSE_SPLIT.split(text or ""):
        for branch in OR_SPLIT.split(clause):
            result = eval_conditions(extract_conditions(branch), vals)
            if result is True:
                return True
            if result is False:
                saw = True
    return False if saw else None


def all_t1_conditions_true(text: str, vals: dict[str, float | None]) -> bool | None:
    """取包含 T+1 的子句（无则取首个可抽条件子句），其条件全真才 True。"""
    clauses = [c for c in CLAUSE_SPLIT.split(text or "") if extract_conditions(c)]
    if not clauses:
        return None
    preferred = [c for c in clauses if "T+1" in c or "t1" in c]
    clause = preferred[0] if preferred else clauses[0]
    return eval_conditions(extract_conditions(clause), vals)


def market_actuals(con: Any, date: str) -> dict[str, Any] | None:
    row = con.execute(
        "SELECT advancers, limit_up, limit_down, total_amount, volume_ratio, "
        "stock_high_count_history, sh_index_pct_chg, market_stage FROM fact_market_daily WHERE trade_date = ?",
        [date],
    ).fetchone()
    if not row:
        return None
    keys = ("advancers", "limit_up", "limit_down", "total_amount", "volume_ratio", "high_history", "sh_pct", "stage")
    return dict(zip(keys, (float(v) if isinstance(v, (int, float)) else v for v in row)))


def sector_rows(con: Any, date: str) -> dict[str, dict[str, float]]:
    rows = con.execute(
        "SELECT sector_name, pct_chg, diff_ratio, amount FROM fact_sector_daily WHERE trade_date = ?",
        [date],
    ).fetchall()
    return {
        str(r[0]): {"pct_chg": float(r[1]) if r[1] is not None else None,
                    "diff_ratio": float(r[2]) if r[2] is not None else None,
                    "amount": float(r[3]) if r[3] is not None else None}
        for r in rows if r[0]
    }


def stock_row(con: Any, date: str, code: str) -> dict[str, float] | None:
    bare = code.split(".", 1)[0]
    row = con.execute(
        "SELECT close, pct_chg, amount FROM fact_stock_daily WHERE trade_date = ? AND split_part(stock_ts_code, '.', 1) = ? LIMIT 1",
        [date, bare],
    ).fetchone()
    if not row or row[0] is None:
        return None
    return {"close": float(row[0]), "pct_chg": float(row[1]) if row[1] is not None else None,
            "amount": float(row[2]) if row[2] is not None else None}


CLOSE_MIN_RE = re.compile(r"(?:站稳|不低于|>=|收盘不低于|t1_close_min\s*=)\s*([0-9]+(?:\.[0-9]+)?)")
CLOSE_FAIL_RE = re.compile(r"(?:跌破|破|falsify_close_below\s*=)\s*([0-9]+(?:\.[0-9]+)?)")


def judge_target(code: str, name: str, texts: list[str], stock: dict[str, float] | None,
                 sh_pct: float | None, structured: dict[str, Any] | None = None) -> tuple[str, str]:
    if stock is None:
        return "unverifiable", f"{name}({code}) 当日无行情数据"
    close, pct = stock["close"], stock["pct_chg"]
    actual = f"{name} 收盘{close:.2f}（{pct:+.2f}%），上证{sh_pct:+.2f}%" if pct is not None and sh_pct is not None \
        else f"{name} 收盘{close:.2f}"
    bare = code.split(".", 1)[0]
    mins: list[float] = []
    fails: list[float] = []
    if structured:
        if structured.get("t1_close_min") is not None:
            mins.append(float(structured["t1_close_min"]))
        if structured.get("falsify_close_below") is not None:
            fails.append(float(structured["falsify_close_below"]))
    if not mins:
        segments = [
            seg
            for t in texts if t
            for seg in re.split(r"[；;。\n、，]", t)
            if bare in seg or name in seg
        ]
        blob = " ".join(segments)
        mins = [float(v) for v in CLOSE_MIN_RE.findall(blob)]
        fails = [float(v) for v in CLOSE_FAIL_RE.findall(blob)]
        # 只取和当前价同量级的阈值，防串到同段其它数字
        mins = [v for v in mins if 0.5 <= v / close <= 2.0]
        fails = [v for v in fails if 0.5 <= v / close <= 2.0]
    if mins:
        t1_min = min(mins)
        if close >= t1_min:
            return "hit", f"{actual}，≥T+1阈值{t1_min}"
        if fails and close < min(fails):
            return "miss", f"{actual}，跌破证伪价{min(fails)}"
        return ("partial", f"{actual}，低于T+1阈值{t1_min}但未破证伪价{min(fails)}") if fails else \
            ("miss", f"{actual}，低于T+1阈值{t1_min}")
    if pct is not None and sh_pct is not None:
        return ("hit", f"{actual}，跑赢上证") if pct > sh_pct else ("miss", f"{actual}，跑输上证")
    return "unverifiable", actual


def judge_direction(texts: list[str], sectors: dict[str, dict[str, float]]) -> tuple[str, str]:
    blob = " ".join(t for t in texts if t)
    matched = [n for n in sectors if len(n) >= 2 and n in blob]
    matched = sorted(set(matched), key=blob.index)[:8]
    if not matched:
        return "unverifiable", "方向文本未匹配到板块名"
    parts, double_red, positive = [], 0, 0
    for n in matched:
        s = sectors[n]
        pct, diff = s.get("pct_chg"), s.get("diff_ratio")
        parts.append(f"{n} {pct:+.2f}%/diff{diff:+.2f}" if pct is not None and diff is not None else f"{n} 数据缺")
        if pct is not None and pct > 0:
            positive += 1
            if diff is not None and diff > 0:
                double_red += 1
    actual = "；".join(parts)
    if double_red * 2 >= len(matched):
        return "hit", actual
    if positive == 0:
        return "miss", actual
    return "partial", actual


def build_verdicts_for_date(date: str, ledger_dir: Path, db_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    import duckdb  # noqa: PLC0415 可选依赖延迟导入

    warnings: list[str] = []
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        market = market_actuals(con, date)
        if market is None:
            return None, [f"{date} 无 fact_market_daily 行情，跳过"]
        sectors = sector_rows(con, date)
        vals = {k: market.get(k) for k in ("advancers", "limit_up", "limit_down", "total_amount", "volume_ratio", "high_history")}
        market_actual_str = (
            f"涨家数{int(market['advancers'])}、涨停{int(market['limit_up'])}、跌停{int(market['limit_down'])}、"
            f"成交额{market['total_amount']:.0f}亿、量比{market['volume_ratio']:.1f}、上证{market['sh_pct']:+.2f}%（{market['stage']}）"
        )

        entries: list[dict[str, Any]] = []
        for key, apath in sorted(answer_paths_for(date, ledger_dir).items()):
            try:
                answer = json.loads(apath.read_text(encoding="utf-8"))
            except Exception as exc:
                warnings.append(f"{apath.name} 不可读：{exc}")
                continue
            agent = str(answer.get("agent") or key.split(".", 1)[0]).lower()
            thresholds = answer.get("thresholds") or {}
            hyps = {str(h.get("id")): h for h in answer.get("hypotheses") or [] if h.get("id")}
            picks = {str(p.get("code") or ""): p for p in answer.get("picks") or []}
            ids = set(hyps) or ({"market", "direction", "falsify"} | {f"target:{c}" for c in picks if c})

            for hid in sorted(ids):
                hyp = hyps.get(hid, {})
                falsify_text = " ；".join(t for t in (hyp.get("falsify_when"), thresholds.get("falsify")) if t)
                if hid.startswith("target:"):
                    code = hid.split(":", 1)[1]
                    pick = picks.get(code) or picks.get(code.split(".", 1)[0]) or {}
                    name = str(pick.get("name") or code)
                    by_stock = thresholds.get("targets_by_stock") or {}
                    structured = by_stock.get(code) or by_stock.get(code.split(".", 1)[0]) if isinstance(by_stock, dict) else None
                    texts = [str(thresholds.get("targets") or ""), str(hyp.get("claim") or ""),
                             str(hyp.get("falsify_when") or "")]
                    verdict, actual = judge_target(code, name, texts, stock_row(con, date, code),
                                                   market.get("sh_pct"), structured)
                elif hid == "direction" or str(hyp.get("type") or "") == "direction" or hid.startswith("direction:"):
                    ranking = answer.get("direction_ranking") or []
                    texts = [str(hyp.get("claim") or ""), str(thresholds.get("direction") or ""),
                             " ".join(str(r) for r in ranking[:2])]
                    verdict, actual = judge_direction(texts, sectors)
                elif hid == "falsify":
                    triggered = any_clause_true(falsify_text, vals)
                    if triggered is None:
                        verdict, actual = "unverifiable", f"证伪条件无法机判；{market_actual_str}"
                    else:
                        verdict = "miss" if triggered else "hit"
                        actual = f"证伪条件{'已触发' if triggered else '未触发'}；{market_actual_str}"
                else:  # market / sentiment / 其他市场路径类
                    triggered = any_clause_true(falsify_text, vals)
                    expected = all_t1_conditions_true(
                        str(hyp.get("claim") or "") + "；" + str(thresholds.get("market") or "")
                        + "；" + str((thresholds.get("t1") or "")), vals)
                    if triggered is True:
                        verdict = "miss"
                    elif expected is True:
                        verdict = "hit"
                    elif triggered is None and expected is None:
                        verdict = "unverifiable"
                    else:
                        verdict = "partial"
                    actual = market_actual_str
                entry = {
                    "id": hid,
                    "agent": agent,
                    "verdict": verdict,
                    "actual": actual,
                    "stream": "盘面",
                    "horizon": "T+1",
                    "evidence_ref": f"auto:dual_blind_auto_verdict.py DuckDB {date}",
                }
                if verdict in {"miss", "partial"}:
                    entry["failure_mode"] = "机判待人工归因"
                entries.append(entry)
        if not entries:
            return None, warnings + [f"{date} 无可裁定答卷"]
        return {"schema_version": "1.0", "date": date, "verdicts": entries}, warnings
    finally:
        con.close()


def pending_dates(ledger_dir: Path, db_path: Path) -> list[str]:
    import duckdb  # noqa: PLC0415 可选依赖延迟导入

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        have = {str(r[0]) for r in con.execute("SELECT DISTINCT trade_date FROM fact_market_daily").fetchall()}
    finally:
        con.close()
    dates = sorted({p.name.split(".", 1)[0] for p in ledger_dir.glob("*.answer.*.json")})
    return [d for d in dates if d in have and not verdict_path_for(d, ledger_dir).exists()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger-dir", default=str(LEDGER_DIR))
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--date", action="append", default=[], help="裁定日期，可重复")
    parser.add_argument("--all-pending", action="store_true", help="裁定所有未出 verdict 且已有当日行情的答卷日期")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的 verdict.json（默认跳过，保护人工裁决）")
    args = parser.parse_args(argv)

    ledger_dir = Path(args.ledger_dir).expanduser()
    db_path = Path(args.db).expanduser()
    dates = list(args.date)
    if args.all_pending:
        dates += [d for d in pending_dates(ledger_dir, db_path) if d not in dates]
    if not dates:
        print("无待裁定日期")
        return 0

    failed = False
    for date in sorted(dates):
        out_path = verdict_path_for(date, ledger_dir)
        if out_path.exists() and not args.force:
            print(f"SKIP  {out_path.name} 已存在（人工裁决优先，--force 覆盖）")
            continue
        draft, warnings = build_verdicts_for_date(date, ledger_dir, db_path)
        for warn in warnings:
            print(f"WARN {date}: {warn}", file=sys.stderr)
        if draft is None:
            failed = True
            continue
        errors = validate_verdict(draft, ledger_dir=ledger_dir)
        if errors:
            failed = True
            for err in errors:
                print(f"ERROR {date}: {err}", file=sys.stderr)
            continue
        body = {
            "schema_version": "1.0",
            "date": date,
            "verdicts": draft["verdicts"],
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        out_path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stats: dict[str, dict[str, int]] = {}
        for e in body["verdicts"]:
            b = stats.setdefault(e["agent"], {"hit": 0, "miss": 0, "partial": 0, "unverifiable": 0})
            b[e["verdict"]] += 1
        summary = " ".join(
            f"{a}:{b['hit']}/{b['hit'] + b['miss'] + b['partial']}" for a, b in sorted(stats.items())
        )
        print(f"OK    written: {out_path}（机判命中率 {summary}）")
        if render_verdict_md(body, ledger_dir=ledger_dir) is None:
            print(f"WARN: 当日台账 {date}.md 不存在，回检表未渲染", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())


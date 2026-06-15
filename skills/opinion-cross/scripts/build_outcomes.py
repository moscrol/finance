#!/usr/bin/env python3
"""build_outcomes: opinion-store 的 T+N 盘后回测（机构胜率原料）。

读取 opinion-events.jsonl 的「看多」事件（剔除 [晨汇转述] AI 总结通道），
解析标的代码（新浪 suggest）→ 抓前复权日线（腾讯）→ 算进场后 T+3/5/7/10
收益、区间最高收益、峰值天数、峰值后回撤，并相对沪深300 算超额收益，
落到 <vault>/raw/theme-radar/opinion-store/outcomes.jsonl。

进场口径：报告日次日开盘买入。
完整性：今天之后凑不满的窗口标 *_complete=false，胜率聚合时不计入该窗口。

  python3 build_outcomes.py [--vault <wiki>] [--benchmark sh000300]
                            [--start 2026-04-25] [--end 2026-06-15]
                            [--limit N] [--out <path>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import price_lib as pl  # noqa: E402


def resolve_vault(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    for env in ("KB_VAULT", "CONCEPT_VAULT", "ENTITY_VAULT"):
        v = os.environ.get(env)
        if v:
            return Path(v).expanduser()
    return Path.home() / "knowledge-base-private" / "wiki"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None)
    ap.add_argument("--benchmark", default="sh000300")
    ap.add_argument("--start", default="2026-04-25")
    ap.add_argument("--end", default="2026-06-15")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 个看多事件（调试）")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    vault = resolve_vault(args.vault)
    store = vault / "raw" / "theme-radar" / "opinion-store"
    events_path = store / "opinion-events.jsonl"
    out_path = Path(args.out).expanduser() if args.out else store / "outcomes.jsonl"
    if not events_path.exists():
        print(f"[ERR] events not found: {events_path}")
        return 1

    # 1) load + filter 看多 / 剔除晨汇转述
    bull = []
    total = 0
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        total += 1
        e = json.loads(line)
        if e.get("stance", "").strip() != "看多":
            continue
        if "晨汇转述" in (e.get("report_title") or ""):
            continue
        bull.append(e)
    if args.limit:
        bull = bull[: args.limit]
    print(f"[INFO] total events={total} | 看多(non-晨汇转述)={len(bull)}")

    # 2) resolve distinct targets -> codes (cached)
    targets = sorted({e["target"] for e in bull if e.get("target")})
    code_map: dict[str, str | None] = {}
    miss = []
    for i, t in enumerate(targets):
        c = pl.name2code(t, code_map)
        if not c:
            miss.append(t)
        if i % 50 == 0:
            time.sleep(0.05)
    pl._save_code_map(code_map)
    print(f"[INFO] distinct targets={len(targets)} | resolved={len(targets)-len(miss)} | MISS={len(miss)}")

    # 3) benchmark index
    idx = pl.index_daily(args.benchmark, args.start, args.end)
    print(f"[INFO] benchmark {args.benchmark} rows={len(idx)}")

    # 4) per-event metrics
    today = dt.date.today().isoformat()
    records = []
    n_nocode = n_nowin = n_ok = 0
    price_cache: dict[str, list] = {}
    for e in bull:
        tgt = e["target"]
        code = code_map.get(tgt)
        if not code:
            n_nocode += 1
            continue
        if code not in price_cache:
            try:
                price_cache[code] = pl.qfq_daily(code, args.start, args.end)
                time.sleep(0.08)
            except Exception as ex:  # noqa: BLE001
                print(f"[WARN] price fetch failed {code} {tgt}: {ex}")
                price_cache[code] = []
        kl = price_cache[code]
        m = pl.fwd_metrics(kl, e["report_date"], idx) if kl else None
        if not m:
            n_nowin += 1
            continue
        rec = {
            "event_id": e.get("event_id"),
            "report_date": e.get("report_date"),
            "source": e.get("source"),
            "source_id": e.get("source_id"),
            "target": tgt,
            "code": code,
            "concept": e.get("concept"),
            "term": e.get("term"),
            "stance": e.get("stance"),
            "hardness": e.get("hardness"),
            "resonance_tier": e.get("resonance_tier"),
            "benchmark": args.benchmark,
            "computed_at": today,
        }
        rec.update(m)
        records.append(rec)
        n_ok += 1

    # 5) write outcomes.jsonl
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[OK] wrote {n_ok} outcomes -> [{out_path}]")
    print(f"[INFO] skipped: no_code={n_nocode} no_window={n_nowin}")
    # window completeness
    for n in (3, 5, 7, 10):
        comp = sum(1 for r in records if r.get(f"ret_{n}d_complete"))
        print(f"[INFO] T+{n} complete: {comp}/{n_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""winrate_rank: 由 outcomes.jsonl 聚合「卖方机构胜率榜」。

join 键 = source_id（sources.json 已把机构别名归一成稳定 id）。
主口径：T+5 相对沪深300 超额收益 > 0 记为胜；同时给绝对收益口径。
只排「有效看多 ≥ MIN 次」（默认 5）的机构，1~2 次样本视为噪音不排。
窗口不完整的事件不计入该窗口的胜率分母。

  python3 winrate_rank.py [--vault <wiki>] [--outcomes <path>]
                          [--min-calls 5] [--window 5] [--report <md>]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
from pathlib import Path


def resolve_vault(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    for env in ("KB_VAULT", "CONCEPT_VAULT", "ENTITY_VAULT"):
        v = os.environ.get(env)
        if v:
            return Path(v).expanduser()
    return Path.home() / "knowledge-base-private" / "wiki"


def load_sources(store: Path) -> dict[str, str]:
    p = store / "sources.json"
    out: dict[str, str] = {}
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        for s in data.get("sources", []):
            out[s.get("source_id")] = s.get("canonical") or s.get("source_id")
    return out


def pct(x: float) -> str:
    return f"{x:+.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None)
    ap.add_argument("--outcomes", default=None)
    ap.add_argument("--min-calls", type=int, default=5)
    ap.add_argument("--window", type=int, default=5, choices=[3, 5, 7, 10])
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    vault = resolve_vault(args.vault)
    store = vault / "raw" / "theme-radar" / "opinion-store"
    outcomes_path = Path(args.outcomes).expanduser() if args.outcomes else store / "outcomes.jsonl"
    if not outcomes_path.exists():
        print(f"[ERR] outcomes not found: {outcomes_path}")
        return 1
    names = load_sources(store)
    w = args.window

    rows = [json.loads(l) for l in outcomes_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    # group by source_id; only events with complete window w AND excess present
    by_src: dict[str, list[dict]] = {}
    for r in rows:
        if not r.get(f"ret_{w}d_complete"):
            continue
        by_src.setdefault(r.get("source_id"), []).append(r)

    agg = []
    for sid, evs in by_src.items():
        n = len(evs)
        if n < args.min_calls:
            continue
        abs_rets = [e[f"ret_{w}d"] for e in evs if e.get(f"ret_{w}d") is not None]
        exc_rets = [e[f"excess_{w}d"] for e in evs if e.get(f"excess_{w}d") is not None]
        maxhits = [e["interval_max_ret"] for e in evs if e.get("interval_max_ret") is not None]
        dds = [e["post_peak_dd"] for e in evs if e.get("post_peak_dd") is not None]
        if not exc_rets:
            continue
        win_exc = sum(1 for x in exc_rets if x > 0) / len(exc_rets)
        win_abs = sum(1 for x in abs_rets if x > 0) / len(abs_rets) if abs_rets else 0.0
        agg.append({
            "source_id": sid,
            "name": names.get(sid, sid),
            "n": n,
            "win_exc": win_exc,
            "win_abs": win_abs,
            "avg_exc": st.mean(exc_rets),
            "med_exc": st.median(exc_rets),
            "avg_abs": st.mean(abs_rets) if abs_rets else 0.0,
            "avg_maxhit": st.mean(maxhits) if maxhits else 0.0,
            "avg_dd": st.mean(dds) if dds else 0.0,
        })

    # rank by excess win rate, tie-break avg excess
    agg.sort(key=lambda a: (a["win_exc"], a["avg_exc"]), reverse=True)

    header = (f"机构胜率榜 | 口径=T+{w} 相对沪深300超额>0 | 门槛=有效看多≥{args.min_calls}次 "
              f"| 合格机构={len(agg)} | 样本事件={sum(a['n'] for a in agg)}")
    print(header)
    print(f"{'#':>3} {'机构':<22} {'n':>3} {'超额胜率':>7} {'绝对胜率':>7} {'均超额':>7} {'中超额':>7} {'均最高':>7} {'均回撤':>7}")
    for i, a in enumerate(agg, 1):
        print(f"{i:>3} {a['name'][:22]:<22} {a['n']:>3} {a['win_exc']*100:>6.0f}% "
              f"{a['win_abs']*100:>6.0f}% {a['avg_exc']:>+6.1f} {a['med_exc']:>+6.1f} "
              f"{a['avg_maxhit']:>+6.1f} {a['avg_dd']:>+6.1f}")

    if args.report:
        lines = [f"# {header}", "",
                 f"- 进场：报告日次日开盘买入；窗口 T+{w} 收盘。",
                 "- 超额 = 个股收益 − 沪深300 同窗收益（剥大盘 beta）。",
                 "- 均最高 = 区间最高收益均值（最好情形）；均回撤 = 峰值后回撤均值（风险）。",
                 "- 仅统计 T+{0} 窗口完整的看多事件；剔除 [晨汇转述] AI 总结通道。".format(w), "",
                 f"| # | 机构 | 样本n | 超额胜率 | 绝对胜率 | 均超额 | 中位超额 | 均最高 | 均回撤 |",
                 "|---|------|------|---------|---------|--------|---------|--------|--------|"]
        for i, a in enumerate(agg, 1):
            lines.append(f"| {i} | {a['name']} | {a['n']} | {a['win_exc']*100:.0f}% | "
                         f"{a['win_abs']*100:.0f}% | {pct(a['avg_exc'])} | {pct(a['med_exc'])} | "
                         f"{pct(a['avg_maxhit'])} | {pct(a['avg_dd'])} |")
        Path(args.report).expanduser().write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[OK] report -> [{args.report}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

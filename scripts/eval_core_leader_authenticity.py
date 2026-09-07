#!/usr/bin/env python3
"""正宗度到底有没有用——核心个股 v1 的消融读数（只读库，不写任何表）。

问题：``score = popularity + w × authenticity`` 里的 ``w`` 该取多少？拍一个数是没有依据的，
所以在历史上直接量：同一天、同一个池、同一套人气分，只把 w 换掉，看前瞻收益差多少。

三个刻意的设计（都在治「读数好看但不成立」）：

1. **池子用 fupanhui 自己的主线板块**（2026-04-01~09-02，106 日）。用我们自己的 mainline-v1
   会把「主线选得准不准」和「正宗度有没有用」两件事混在一个读数里，一个变量都定位不了。
2. **KB 边按 ``as_of`` 逐条过滤**。知识库是**今天**的快照，每条边带 ``updated``；不过滤就是拿
   今天的认知去挑 4 月的股，读数会好看得离谱（前视偏差）。
3. **打乱标签的置换检验当噪声底**。w>0 比 w=0 差 0.5pp 到底算不算真差，要有个「标签与股票无关」的
   参照才知道——把 authenticity 在当天池内随机打乱重跑。**噪声底必须与被比较的统计量同量纲**：
   真实 Δ 是全窗（~106 日）均值，所以每次置换也要取全窗均值，拿这些均值的分布当参照。
   首版把所有单日 Δ 混在一起取 sd（1.1~2.1pp）去比全窗均值 Δ，量纲差了 √106 倍，
   结论「在噪声带内」是错的——同量纲下 sd 只有 0.07~0.14pp，w=0.3 的 Δ 在三个期限上都显著为负。
   单日混池的 sd 仍打印出来，只表示「单日名单换几只票能抖多大」，不拿它判显著。

两个必须一起读的限制：

- 知识库边的 ``updated`` 从 2026-05 起：as_of 过滤后 **4 月整月零边**、5 月 18 天里只有 4 天池里有正宗票，
  有效窗口约 65 日且正宗票占比随月份从 0% 爬到 23%。正宗度效应与日历时间混杂，本脚本按月打印 Δ 供肉眼看。
- ``updated`` 是知识库写边的时间，不是事实公开的时间（8 月写入的年报主营边描述的是早已公开的事实），
  所以这个 as_of 既不是「市场当时知道什么」，也不是「产品当时能查到什么」（4 月知识库还不存在）。
- 底数据里 2026-07-20 / 08-06 两天的 fact_stock_daily 是次日数据的复制（见 duckdb-backfill QA），
  跨这两天的前瞻收益被污染；两天占窗口 2/106，修好后重跑。

用法::

    python3 scripts/eval_core_leader_authenticity.py                 # 默认 106 日、top20、T+1/3/5
    python3 scripts/eval_core_leader_authenticity.py --topk 10 --perm 500
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from market_feature_store.db import connect  # noqa: E402
from market_feature_store.sources import kb_exposure as kbx  # noqa: E402
from market_feature_store.sync.compute_local_stats import (  # noqa: E402
    _mainline_membership,
    core_leader_candidates,
)

WEIGHTS = (0.0, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0)
HORIZONS = (1, 3, 5)
#: 置换检验固定用的权重：取一个「能看出效应」的档位，而不是上线值 0.15（0.15 的 Δ 太小，噪声底看不出形状）
NOISE_W = 0.3


def forward_returns(con, horizons) -> dict[tuple[date, str], dict[int, float]]:
    """(交易日, 股票) → {N: 未来 N 个交易日累计涨幅%}。用 LEAD 按交易日序列取，跳过停牌日历空洞。"""
    leads = ", ".join(
        f"LEAD(close, {n}) OVER (PARTITION BY stock_ts_code ORDER BY trade_date) f{n}" for n in horizons
    )
    rows = con.execute(
        f"SELECT trade_date, stock_ts_code, close, {leads} FROM fact_stock_daily WHERE close > 0"
    ).fetchall()
    out: dict[tuple[date, str], dict[int, float]] = {}
    for r in rows:
        base = r[2]
        vals = {n: (r[3 + i] / base - 1) * 100 for i, n in enumerate(horizons) if r[3 + i] is not None}
        if vals:
            out[(r[0], r[1])] = vals
    return out


def top_mean(cands, weight, fwd, td, topk, horizon, auth_key="auth") -> float | None:
    ranked = sorted(cands, key=lambda c: -(c["pop"] + weight * c[auth_key]))[:topk]
    got = [fwd[(td, c["code"])][horizon] for c in ranked
           if (td, c["code"]) in fwd and horizon in fwd[(td, c["code"])]]
    return statistics.fmean(got) if got else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topk", type=int, default=20)
    ap.add_argument("--perm", type=int, default=200, help="置换检验次数（噪声底）")
    ap.add_argument("--seed", type=int, default=20260907)
    args = ap.parse_args()

    con = connect(read_only=True)
    days = [r[0] for r in con.execute(
        "SELECT DISTINCT trade_date FROM fact_mainline_sector_daily WHERE source NOT LIKE 'local:%' ORDER BY 1"
    ).fetchall()]
    fwd = forward_returns(con, HORIZONS)
    print(f"评估日 {len(days)} 天：{days[0]} ~ {days[-1]}｜topK={args.topk}｜置换 {args.perm} 次")

    per_day: dict[tuple[float, int], list[float]] = defaultdict(list)
    auth_dist, cover_n, pool_n, used_days = defaultdict(int), 0, 0, 0
    perm_deltas: dict[int, list[float]] = defaultdict(list)
    # h → 每次置换一列：该置换在各评估日的 Δ，取均值后才与真实 Δ 同量纲
    perm_by_run: dict[int, list[list[float]]] = {h: [[] for _ in range(args.perm)] for h in HORIZONS}
    real_delta_day: dict[int, list[float]] = defaultdict(list)
    month_stats: dict[str, dict] = defaultdict(lambda: {"days": 0, "days_with_auth": 0, "pool": 0, "auth_pos": 0,
                                                        "delta": defaultdict(list)})
    used_pool: dict[date, list[dict]] = {}
    future_members: dict[date, set[str]] = {}
    rng = random.Random(args.seed)

    for td in days:
        try:
            membership, _ = _mainline_membership(con, td)
        except RuntimeError:
            continue
        index = kbx.exposure_index(as_of=td)          # ← 只用当天已存在的边
        aliases = kbx.concept_aliases()
        kb_concepts = {e["concept"] for edges in index.values() for e in edges}
        try:
            cands = core_leader_candidates(con, td, membership=membership, aliases=aliases,
                                           index=index, kb_concepts=kb_concepts)
        except RuntimeError:
            continue
        if not any((td, c["code"]) in fwd for c in cands):
            continue
        used_days += 1
        used_pool[td] = cands
        future_members[td] = {c["code"] for c in cands}
        pool_n += len(cands)
        cover_n += sum(1 for c in cands if c["covered"])
        for c in cands:
            auth_dist[c["auth"]] += 1
        ms = month_stats[td.strftime("%Y-%m")]
        ms["days"] += 1
        ms["pool"] += len(cands)
        n_auth = sum(1 for c in cands if c["auth"] > 0)
        ms["auth_pos"] += n_auth
        ms["days_with_auth"] += 1 if n_auth else 0
        base_day: dict[int, float] = {}
        for w in WEIGHTS:
            for h in HORIZONS:
                m = top_mean(cands, w, fwd, td, args.topk, h)
                if m is not None:
                    per_day[(w, h)].append(m)
                    if w == 0.0:
                        base_day[h] = m
        for h in HORIZONS:
            if h in base_day:
                m = top_mean(cands, NOISE_W, fwd, td, args.topk, h)
                if m is not None:
                    real_delta_day[h].append(m - base_day[h])
                    ms["delta"][h].append(m - base_day[h])
        # 噪声底：把 authenticity 在当天池内打乱，w 固定用 NOISE_W，看「标签与股票无关」时 Δ 长什么样
        shuffled = [c["auth"] for c in cands]
        for run in range(args.perm):
            rng.shuffle(shuffled)
            for c, a in zip(cands, shuffled):
                c["shuf"] = a
            for h in HORIZONS:
                if h not in base_day:
                    continue
                a = top_mean(cands, NOISE_W, fwd, td, args.topk, h, auth_key="shuf")
                if a is not None:
                    perm_deltas[h].append(a - base_day[h])
                    perm_by_run[h][run].append(a - base_day[h])

    # 分组直比：不经过 top20 选择，直接比「正宗组 vs 非正宗组」。
    # 排序消融的方差来自选择本身（换掉几只票就抖），分组比只比标签，方差小一个量级。
    groups: dict[tuple[str, int], list[float]] = defaultdict(list)
    stay: dict[str, list[float]] = defaultdict(list)
    for td in used_pool:
        cands = used_pool[td]
        future = set()
        for d2, codes in future_members.items():
            if d2 > td and (d2 - td).days <= 8:
                future |= codes
        for c in cands:
            g = "正宗(1.0)" if c["auth"] >= 1.0 else ("沾边(0.2~0.6)" if c["auth"] > 0 else "无边(0)")
            fr = fwd.get((td, c["code"]))
            if fr:
                for h in HORIZONS:
                    if h in fr:
                        groups[(g, h)].append(fr[h])
            if future:
                stay[g].append(1.0 if c["code"] in future else 0.0)
    print()
    print("分组直比（不经 topK 选择，n 为股票·日）：")
    for g in ("正宗(1.0)", "沾边(0.2~0.6)", "无边(0)"):
        cells = []
        for h in HORIZONS:
            v = groups[(g, h)]
            cells.append(f"T+{h} {statistics.fmean(v):+.3f}" if v else f"T+{h} -")
        n = len(groups[(g, HORIZONS[0])])
        s = stay[g]
        keep = f"5日内仍在主线 {statistics.fmean(s):.1%}" if s else "5日内仍在主线 -"
        print(f"  {g:<14} n={n:>6}  " + "  ".join(cells) + f"  {keep}")
    print()
    print(f"实际用上 {used_days} 天｜池均 {pool_n / max(used_days, 1):.0f} 只｜"
          f"板块可查 {cover_n / max(pool_n, 1):.1%}")
    print(f"正宗度分布: { {k: round(v / max(pool_n, 1), 3) for k, v in sorted(auth_dist.items())} }")
    print()
    print(f"按月（as_of 过滤后正宗票在池里的密度，与当月 Δ(w={NOISE_W}) —— 两列同向就是日历混杂）：")
    for m in sorted(month_stats):
        s = month_stats[m]
        cells = " ".join(
            f"T+{h} {statistics.fmean(s['delta'][h]):+.3f}" if s["delta"][h] else f"T+{h}    -   " for h in HORIZONS)
        print(f"  {m}: 评估日 {s['days']:>2}  有正宗票的日 {s['days_with_auth']:>2}  "
              f"池内 auth>0 {s['auth_pos'] / max(s['pool'], 1):5.1%}  Δ {cells}")
    print()
    print(f"{'权重':>6} | " + " | ".join(f"T+{h} 均涨幅%   Δ vs w=0" for h in HORIZONS))
    base = {h: statistics.fmean(per_day[(0.0, h)]) for h in HORIZONS}
    for w in WEIGHTS:
        cells = []
        for h in HORIZONS:
            vals = per_day[(w, h)]
            m = statistics.fmean(vals)
            cells.append(f"{m:>9.3f}  {m - base[h]:>+8.3f}")
        print(f"{w:>6} | " + " | ".join(cells))
    print()
    print(f"置换检验（打乱标签，w={NOISE_W}，{args.perm} 次）：")
    for h in HORIZONS:
        runs = [statistics.fmean(r) for r in perm_by_run[h] if r]
        if not runs or not real_delta_day[h]:
            continue
        real = statistics.fmean(real_delta_day[h])
        runs_sorted = sorted(runs)
        lo = runs_sorted[int(len(runs) * 0.025)]
        hi = runs_sorted[min(len(runs) - 1, int(len(runs) * 0.975))]
        frac_below = sum(1 for x in runs if x <= real) / len(runs)
        verdict = "在噪声带内" if lo <= real <= hi else ("**显著为负**" if real < lo else "**显著为正**")
        pooled_sd = statistics.pstdev(perm_deltas[h])
        print(f"  T+{h}: 真实 Δ {real:+.3f}pp｜同量纲噪声底（每次置换取 {used_days} 日均值）"
              f"均值 {statistics.fmean(runs):+.3f} sd {statistics.pstdev(runs):.3f} 95% 区间 [{lo:+.3f}, {hi:+.3f}]"
              f"｜置换里 ≤ 真实 Δ 的占 {frac_below:.1%} → {verdict}")
        print(f"        （单日 Δ 混池 sd {pooled_sd:.3f}pp：只说明单日名单换几只票能抖多大，不用来判显著）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

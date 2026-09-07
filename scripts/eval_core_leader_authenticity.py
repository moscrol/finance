#!/usr/bin/env python3
"""正宗度到底有没有用——核心个股 v1 的消融读数（只读库，不写任何表）。

问题：``score = popularity + w × authenticity`` 里的 ``w`` 该取多少？拍一个数是没有依据的，
所以在历史上直接量：同一天、同一个池、同一套人气分，只把 w 换掉，看前瞻收益差多少。

三个刻意的设计（都在治「读数好看但不成立」）：

1. **池子用 fupanhui 自己的主线板块**（2026-04-01~09-02，106 日）。用我们自己的 mainline-v1
   会把「主线选得准不准」和「正宗度有没有用」两件事混在一个读数里，一个变量都定位不了。
2. **KB 边按 ``as_of`` 逐条过滤**。知识库是**今天**的快照，每条边带 ``updated``；不过滤就是拿
   今天的认知去挑 4 月的股，读数会好看得离谱（前视偏差）。
3. **打乱标签的置换检验当噪声底**。w>0 比 w=0 高 0.2pp 到底算不算赢，要有个「真值必为 0」的
   参照才知道——把 authenticity 在当天池内随机打乱重跑，得到的分布就是纯噪声能造出多大的差。

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

WEIGHTS = (0.0, 0.1, 0.2, 0.3, 0.5, 1.0)
HORIZONS = (1, 3, 5)


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
        for w in WEIGHTS:
            for h in HORIZONS:
                m = top_mean(cands, w, fwd, td, args.topk, h)
                if m is not None:
                    per_day[(w, h)].append(m)
        # 噪声底：把 authenticity 在当天池内打乱，w 固定用 0.3，看纯噪声能造出多大的 delta
        shuffled = [c["auth"] for c in cands]
        for _ in range(args.perm):
            rng.shuffle(shuffled)
            for c, a in zip(cands, shuffled):
                c["shuf"] = a
            for h in HORIZONS:
                a = top_mean(cands, 0.3, fwd, td, args.topk, h, auth_key="shuf")
                b = top_mean(cands, 0.0, fwd, td, args.topk, h)
                if a is not None and b is not None:
                    perm_deltas[h].append(a - b)

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
    for h in HORIZONS:
        d = perm_deltas[h]
        if not d:
            continue
        sd = statistics.pstdev(d)
        real = statistics.fmean(per_day[(0.3, h)]) - base[h]
        hi = sorted(d)[int(len(d) * 0.95)]
        print(f"T+{h} 噪声底（打乱标签 w=0.3）：均值 {statistics.fmean(d):+.3f}  sd {sd:.3f}  "
              f"95 分位 {hi:+.3f}  ← 真实 Δ {real:+.3f} "
              f"{'超过噪声 95 分位' if real > hi else '**在噪声范围内**'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

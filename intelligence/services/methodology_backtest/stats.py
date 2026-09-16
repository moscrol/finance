"""统计口径与四态结论（设计稿 §3.3「一次错误只能是一个样本」）。

给定事件集 N、命中 k、同期基准率 p0：

- 命中率 ``p = k / N``
- **Wilson 95% 区间** ``[lo, hi]``：不用正态近似——N 小、p 接近 0 或 1 时正态区间会越界 [0, 1]，
  Wilson 不会。N=20 级别的样本必须用它。
- 提升 ``lift = p - p0``
- 前后半段：事件按日期排序切两半，各算 ``p_first / p_second``——防「只在某一段行情里成立」。
- 四态：
    ``insufficient_n``       N < min_n（无论命中率多高多低）
    ``supported``            lo > p0 且 p_first > p0 且 p_second > p0
    ``refuted``              hi < p0 且 p_first < p0 且 p_second < p0
    ``not_distinguishable``  其余

为什么是基准率而不是 50%：牛市里板块 5 日收益为正可能本来就 60%+，一条规则命中 66% 等于什么都没说。

多重检验：``--scan`` 一次跑多条规则时，先算每条的精确二项检验双侧 p 值（H0: p = p0），按
Benjamini–Hochberg 控制 FDR；BH 没拒绝的 ``supported`` / ``refuted`` 降级为 ``not_distinguishable``，
并对每条打 ``exploratory=true``。单条手工跑不校正，收据注明「单次检验」。

按大盘阶段的读数（``stage_readouts``）：每个阶段桶用**该阶段自己的基准率**走同一套 ``readout`` → 四态，
再把一条规则的 m 个阶段当一个族做 BH——拆 12 个阶段就是 12 次检验，不校正时 α=0.05 下「至少一个假显著」≈ 46%。
``stage_matched_p0`` 把各阶段 p0 按事件的阶段分布加权，得到「控制住阶段后的期望命中率」作第三列对照。

只用标准库；无 scipy。二项 pmf 用 lgamma 在对数域算，N 到几万也不会溢出。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

Z95 = 1.959963984540054
VERDICTS = ("insufficient_n", "not_distinguishable", "supported", "refuted")


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval。n=0 时无信息，返回 [0, 1]。"""
    if n <= 0:
        return 0.0, 1.0
    if k < 0 or k > n:
        raise ValueError(f"k 必须在 0..n，得到 k={k}, n={n}")
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    lo = max(0.0, center - half)
    hi = min(1.0, center + half)
    return lo, hi


def _log_binom_pmf(i: int, n: int, p0: float) -> float:
    if p0 <= 0.0:
        return 0.0 if i == 0 else -math.inf
    if p0 >= 1.0:
        return 0.0 if i == n else -math.inf
    return (
        math.lgamma(n + 1)
        - math.lgamma(i + 1)
        - math.lgamma(n - i + 1)
        + i * math.log(p0)
        + (n - i) * math.log1p(-p0)
    )


def binom_two_sided_p(k: int, n: int, p0: float) -> float:
    """精确二项检验双侧 p 值（minlike 口径：把 pmf <= pmf(k) 的所有结果都算进去，与 scipy 默认一致）。"""
    if n <= 0:
        return 1.0
    if k < 0 or k > n:
        raise ValueError(f"k 必须在 0..n，得到 k={k}, n={n}")
    if not (0.0 <= p0 <= 1.0):
        raise ValueError(f"p0 必须在 [0, 1]，得到 {p0}")
    log_pk = _log_binom_pmf(k, n, p0)
    # 相对误差容忍：浮点上 pmf(i) 与 pmf(k) 理论相等时也要算进去
    threshold = log_pk + 1e-9
    total = 0.0
    for i in range(n + 1):
        lp = _log_binom_pmf(i, n, p0)
        if lp <= threshold:
            total += math.exp(lp)
    return min(1.0, total)


def mcnemar_exact(b: int, c: int) -> dict[str, Any]:
    """两个版本在同一批样本上的配对比较（McNemar 精确检验）。

    只看翻转的样本：``b`` = A 错 B 对，``c`` = A 对 B 错；都对 / 都错的日子不携带信息，
    所以方差比把两版当独立样本的非配对比较小得多。H0：翻转两个方向等概率，
    p 值 = ``binom_two_sided_p(b, b + c, 0.5)``。``b + c = 0`` 时无翻转，p = 1。
    """
    if b < 0 or c < 0:
        raise ValueError(f"b / c 必须非负，得到 b={b}, c={c}")
    n = b + c
    return {
        "a_wrong_b_right": int(b),
        "a_right_b_wrong": int(c),
        "discordant": int(n),
        "net_gain": int(b - c),
        "p_value": binom_two_sided_p(b, n, 0.5) if n else 1.0,
    }


def benjamini_hochberg(pvals: Sequence[float], q: float = 0.05) -> tuple[list[bool], list[float]]:
    """BH 过程。返回 ``(rejected, adjusted_p)``，顺序与输入一致。"""
    m = len(pvals)
    if m == 0:
        return [], []
    if not (0.0 < q < 1.0):
        raise ValueError(f"q 必须在 (0, 1)，得到 {q}")
    order = sorted(range(m), key=lambda i: pvals[i])
    adjusted = [0.0] * m
    running_min = 1.0
    for rank_from_top in range(m, 0, -1):
        idx = order[rank_from_top - 1]
        val = min(1.0, pvals[idx] * m / rank_from_top)
        running_min = min(running_min, val)
        adjusted[idx] = running_min
    rejected = [adjusted[i] <= q for i in range(m)]
    return rejected, adjusted


def split_halves(items: Sequence[bool]) -> tuple[Sequence[bool], Sequence[bool]]:
    """按顺序（调用方保证已按日期排好）切前后两半；N 为奇数时后半多一个。"""
    mid = len(items) // 2
    return items[:mid], items[mid:]


def _rate(items: Sequence[bool]) -> float | None:
    return (sum(1 for x in items if x) / len(items)) if items else None


def four_state(
    n: int,
    k: int,
    p0: float | None,
    p_first: float | None,
    p_second: float | None,
    min_n: int,
) -> str:
    if n < min_n:
        return "insufficient_n"
    if p0 is None or p_first is None or p_second is None:
        return "not_distinguishable"
    lo, hi = wilson(k, n)
    if lo > p0 and p_first > p0 and p_second > p0:
        return "supported"
    if hi < p0 and p_first < p0 and p_second < p0:
        return "refuted"
    return "not_distinguishable"


@dataclass(frozen=True)
class Readout:
    """一条规则的历史读数。设计稿 §1 判别变量 2：缺任一项不得输出「支持 / 证伪」。"""

    n: int
    k: int
    p: float | None
    p0: float | None
    baseline_n: int
    baseline_k: int
    lift: float | None
    lo: float
    hi: float
    n_first: int
    k_first: int
    p_first: float | None
    n_second: int
    k_second: int
    p_second: float | None
    p_value: float | None
    min_n: int
    verdict: str
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "k": self.k,
            "p": self.p,
            "p0": self.p0,
            "baseline_n": self.baseline_n,
            "baseline_k": self.baseline_k,
            "lift": self.lift,
            "wilson_lo": self.lo,
            "wilson_hi": self.hi,
            "first_half": {"n": self.n_first, "k": self.k_first, "p": self.p_first},
            "second_half": {"n": self.n_second, "k": self.k_second, "p": self.p_second},
            "p_value": self.p_value,
            "min_n": self.min_n,
            "verdict": self.verdict,
            "notes": list(self.notes),
        }


def readout(
    successes: Iterable[bool],
    *,
    baseline_n: int,
    baseline_k: int,
    min_n: int,
) -> Readout:
    """从按日期排好序的命中序列 + 基准率计数算出完整读数。"""
    seq = [bool(x) for x in successes]
    n = len(seq)
    k = sum(1 for x in seq if x)
    p = (k / n) if n else None
    p0 = (baseline_k / baseline_n) if baseline_n > 0 else None
    lo, hi = wilson(k, n)
    first, second = split_halves(seq)
    p_first, p_second = _rate(first), _rate(second)
    lift = (p - p0) if (p is not None and p0 is not None) else None
    p_value = binom_two_sided_p(k, n, p0) if (n > 0 and p0 is not None) else None
    verdict = four_state(n, k, p0, p_first, p_second, min_n)
    notes: list[str] = []
    if n < min_n:
        notes.append(f"N={n} < min_n={min_n}：样本不足，命中率不作为证据")
    if p0 is None:
        notes.append("基准率不可得（同期 universe 无 ok 结果），不能给出支持 / 证伪")
    if n and (p_first is None or p_second is None):
        notes.append("事件不足以切前后半段")
    return Readout(
        n=n,
        k=k,
        p=p,
        p0=p0,
        baseline_n=int(baseline_n),
        baseline_k=int(baseline_k),
        lift=lift,
        lo=lo,
        hi=hi,
        n_first=len(first),
        k_first=sum(1 for x in first if x),
        p_first=p_first,
        n_second=len(second),
        k_second=sum(1 for x in second if x),
        p_second=p_second,
        p_value=p_value,
        min_n=int(min_n),
        verdict=verdict,
        notes=tuple(notes),
    )


def apply_bh_downgrade(verdicts: Sequence[str], rejected: Sequence[bool]) -> list[str]:
    """scan 模式：BH 没拒绝 H0 的 supported / refuted 降级为 not_distinguishable；insufficient_n 不动。"""
    out: list[str] = []
    for v, rej in zip(verdicts, rejected):
        if v in ("supported", "refuted") and not rej:
            out.append("not_distinguishable")
        else:
            out.append(v)
    return out


# --------------------------------------------------------------------------- #
# 按大盘阶段：每桶自己的基准率 + 规则内阶段族 BH
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StageBucket:
    """某个大盘阶段下的已到期事件，带该阶段自己的基准率与完整读数。

    ``readout.verdict`` 是单次检验结论；``verdict`` 是规则内阶段族 BH 校正后的结论（供渲染与证伪库用）。
    """

    stage: str
    readout: Readout
    adjusted_p: float | None
    rejected: bool
    verdict: str

    @property
    def n(self) -> int:
        return self.readout.n

    @property
    def k(self) -> int:
        return self.readout.k

    @property
    def p(self) -> float | None:
        return self.readout.p

    @property
    def p0(self) -> float | None:
        return self.readout.p0

    def to_dict(self) -> dict[str, Any]:
        rd = self.readout.to_dict()
        rd["verdict_single"] = rd.pop("verdict")
        return {"stage": self.stage, **rd, "adjusted_p": self.adjusted_p, "rejected": self.rejected, "verdict": self.verdict}


def stage_readouts(
    successes_by_stage: Mapping[str, Sequence[bool]],
    baseline_by_stage: Mapping[str, tuple[int, int]],
    *,
    min_n: int,
    q: float,
) -> list[StageBucket]:
    """每个阶段桶配自己的基准率 ``(baseline_n, baseline_k)`` 出完整读数，再在规则内按 BH 校正。

    ``successes_by_stage`` 每桶的序列须已按日期排好（前后半段才有意义）。族 = p 值可得且 n >= min_n 的阶段；
    ``insufficient_n`` 不参与校正也不会被改写。桶按 n 降序、阶段名升序排。
    """
    readouts: dict[str, Readout] = {}
    for stage, seq in successes_by_stage.items():
        bn, bk = baseline_by_stage.get(stage, (0, 0))
        readouts[stage] = readout(seq, baseline_n=bn, baseline_k=bk, min_n=min_n)
    order = sorted(readouts, key=lambda s: (-readouts[s].n, s))
    testable = [s for s in order if readouts[s].p_value is not None and readouts[s].verdict != "insufficient_n"]
    adjusted: dict[str, float | None] = {s: None for s in order}
    rejected: dict[str, bool] = {s: False for s in order}
    if testable:
        pvals = [readouts[s].p_value for s in testable]
        rej, adj = benjamini_hochberg([p for p in pvals if p is not None], q=q)
        for s, r, a in zip(testable, rej, adj):
            rejected[s], adjusted[s] = r, a
    verdicts_bh = apply_bh_downgrade([readouts[s].verdict for s in order], [rejected[s] for s in order])
    return [
        StageBucket(stage=s, readout=readouts[s], adjusted_p=adjusted[s], rejected=rejected[s], verdict=v)
        for s, v in zip(order, verdicts_bh)
    ]


def stage_matched_p0(stages: Sequence[StageBucket]) -> float | None:
    """p0 = Σ_stage n_stage · p0_stage / Σ n_stage（只算有基准率的阶段）。

    「如果每个事件都拿它当天所处阶段的基准率来比，整体应该命中多少」——把撞上好阶段的择时效应从提升里剥掉。
    事件所在的 (实体, 日) 本身就在同阶段的 universe 里，所以有事件的阶段一定有基准率；这里的过滤只是防御。
    """
    usable = [b for b in stages if b.p0 is not None and b.n > 0]
    total = sum(b.n for b in usable)
    if not total:
        return None
    return sum(b.n * b.p0 for b in usable) / total  # type: ignore[operator]


# --------------------------------------------------------------------------- #
# 相关样本（OPT-05）：同日共振与重叠窗口下的依赖感知读数
# --------------------------------------------------------------------------- #

DEFAULT_BLOCK_BOOT = 500
DEFAULT_MIN_BLOCKS = 10
DEFAULT_BLOCK_SEED = 20260911  # 固定：同输入同读数；换种子 = 换统计口径，须走版本


@dataclass(frozen=True)
class DependenceReadout:
    """日期块重采样读数：不把「同一天的 400 个板块」当 400 个独立证据。

    上面的 Wilson / 二项检验都假设样本独立；A 股的截面相关让同日事件高度共振，
    重叠的 outcome 窗（5 日收益、隔日又触发）再叠一层序列依赖。OPT-05 的对策
    （Petersen 2009 / 金融面板惯用法）：**按日期整块重采样**——一个块携带该段
    日期的全部实体事件，块内相关性原样保留，块间近似独立。CI 因此比 Wilson 宽，
    宽出来的正是被复制样本冒充的那部分「证据」。
    """

    n_events: int
    n_dates: int
    n_clusters: int          # 事件簇：同实体、事件日 index 间隔 ≤ block_len 归一簇
    span_dates: int          # 首末事件日之间的唯一事件日个数
    block_len: int           # 块长（唯一事件日个数）：≥ success outcome 的重叠范围
    n_blocks: int            # 完整非重叠块数 = n_dates // block_len
    min_blocks: int
    n_boot: int
    seed: int
    boot_p_lo: float | None  # 命中率的块 bootstrap percentile 95% CI
    boot_p_hi: float | None
    method: str
    verdict: str             # supported / refuted / not_distinguishable / insufficient_blocks
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_events": self.n_events,
            "n_dates": self.n_dates,
            "n_clusters": self.n_clusters,
            "span_dates": self.span_dates,
            "block_len": self.block_len,
            "n_blocks": self.n_blocks,
            "min_blocks": self.min_blocks,
            "n_boot": self.n_boot,
            "seed": self.seed,
            "boot_p_lo": self.boot_p_lo,
            "boot_p_hi": self.boot_p_hi,
            "method": self.method,
            "verdict": self.verdict,
            "notes": list(self.notes),
        }


def _cluster_count(events: Sequence[tuple[str, str, bool]], block_len: int) -> int:
    """同实体、相邻触发的**自然日**间隔 ≤ block_len → 同一簇（同源事件的 v0 归组口径）。

    间隔不能按「事件日序号」数——两次触发隔 16 天、中间恰好没有别的事件日，序号只差 1，
    会被误并成一簇。自然日是交易日距离的下界，判「断开」偏松 → 簇数只多不少，作为
    报告字段方向安全。
    """
    from datetime import date as _date

    by_entity: dict[str, list[_date]] = {}
    for eid, d, _s in events:
        by_entity.setdefault(str(eid), []).append(_date.fromisoformat(str(d)[:10]))
    clusters = 0
    for days in by_entity.values():
        days.sort()
        clusters += 1
        clusters += sum(1 for a, b in zip(days, days[1:]) if (b - a).days > block_len)
    return clusters


def block_bootstrap_readout(
    events: Sequence[tuple[str, str, bool]],
    *,
    p0: float | None,
    block_len: int,
    n_boot: int = DEFAULT_BLOCK_BOOT,
    min_blocks: int = DEFAULT_MIN_BLOCKS,
    seed: int = DEFAULT_BLOCK_SEED,
) -> DependenceReadout:
    """circular date-block bootstrap：事件 ``(entity_id, trade_date, success)`` 不展平。

    - 块在**唯一事件日序列**上取（交易日的事件版近似），长度 ``block_len`` 至少要
      盖住 success outcome 的重叠范围（调用方传 ``rule.success.horizon``）。
    - 每轮重采样拼出与原序列等长的日期序列（circular，尾部绕回），取上面**全部**
      事件算命中率；B 轮的 2.5 / 97.5 分位即 CI。
    - 完整非重叠块数 ``n_dates // block_len < min_blocks`` → ``insufficient_blocks``：
      有效独立单元不足，**不回落**成把事件数当 N 的二项检验——那正是要堵的口子。
    - 固定 ``seed``：同输入两次调用逐字段相同；seed / n_boot / method 全部入收据。
    """
    import random

    clean = [(str(e), str(d)[:10], bool(s)) for e, d, s in events]
    dates = sorted({d for _e, d, _s in clean})
    n_dates = len(dates)
    block = max(1, int(block_len))
    n_blocks = n_dates // block
    n_clusters = _cluster_count(clean, block) if clean else 0
    base = dict(
        n_events=len(clean),
        n_dates=n_dates,
        n_clusters=n_clusters,
        span_dates=n_dates,
        block_len=block,
        n_blocks=n_blocks,
        min_blocks=int(min_blocks),
        n_boot=int(n_boot),
        seed=int(seed),
        method="circular_date_block_bootstrap_v1",
    )
    if not clean or n_blocks < min_blocks:
        return DependenceReadout(
            **base,
            boot_p_lo=None,
            boot_p_hi=None,
            verdict="insufficient_blocks",
            notes=(
                f"完整日期块 {n_blocks} < min_blocks={min_blocks}（{n_dates} 个事件日 / 块长 {block}）："
                "有效独立单元不足，不以事件数冒充 N",
            ),
        )
    by_date: dict[str, list[bool]] = {}
    for _e, d, s in clean:
        by_date.setdefault(d, []).append(s)
    rng = random.Random(seed)
    draws_per_round = -(-n_dates // block)  # ceil：拼到 ≥ 原序列长度
    rates: list[float] = []
    for _ in range(int(n_boot)):
        k = n = 0
        for _j in range(draws_per_round):
            start = rng.randrange(n_dates)
            for off in range(block):
                for s in by_date[dates[(start + off) % n_dates]]:
                    n += 1
                    k += s
        if n:
            rates.append(k / n)
    rates.sort()
    if not rates:
        lo = hi = None
    else:
        lo = rates[max(0, int(0.025 * len(rates)) - 1) if int(0.025 * len(rates)) else 0]
        hi = rates[min(len(rates) - 1, int(0.975 * len(rates)))]
    if p0 is None or lo is None or hi is None:
        verdict = "not_distinguishable"
        notes = ("基准率或 bootstrap 分布不可得",)
    elif lo > p0:
        verdict, notes = "supported", ()
    elif hi < p0:
        verdict, notes = "refuted", ()
    else:
        verdict, notes = "not_distinguishable", ()
    return DependenceReadout(**base, boot_p_lo=lo, boot_p_hi=hi, verdict=verdict, notes=notes)


def combined_verdict(independent: str, dependence: str) -> tuple[str, str | None]:
    """最终四态 = 独立假设读数（Wilson / 前后半段）与依赖感知读数的**保守合成**。

    OPT-05：「Wilson 等独立样本区间可保留为描述性读数；没有独立性依据时不得作为
    晋升的唯一依据。」supported 与 refuted 都要两道一致——同日 400 个负样本同样
    不独立，证伪的统计门不因『推翻不用预注册』而豁免（那条不对称说的是晋升流程，
    不是显著性）。
    """
    if independent == "insufficient_n":
        return "insufficient_n", None
    if dependence == "insufficient_blocks":
        return "insufficient_n", "依赖感知读数：有效日期块不足，按样本不足处理（不以事件数冒充 N）"
    if independent == dependence:
        return independent, None
    return (
        "not_distinguishable",
        f"独立假设读数 {independent} 与依赖感知读数 {dependence} 不一致，按保守取 not_distinguishable",
    )

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

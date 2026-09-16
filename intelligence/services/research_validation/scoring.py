"""配对评分、校准桶与胜出日期检验（spec 03 §7）。

- Brier = (p − y)²，越低越好；完整配对案例**日内等权，再日期等权**。
- ``delta_d = mean(Brier_base − Brier_candidate)``，正 = 候选臂当天更好；总差 = mean(delta_d)。
  总差**只是描述**（``mean_brier_difference_descriptive``），不继承任何支持结论。
- 主检验：一天一个胜出 bool（``delta_d > 0`` 严格大于）。平局保留在分母里，v1 含平局 →
  ``insufficient`` + gap ``ties_test_not_defined``；全平局只写「未观察到增量」。
- 无平局时把 bool 序列喂 ``stats.wilson / four_state / binom_two_sided_p`` 与
  ``block_bootstrap_readout``，再 ``combined_verdict``。零假设 p0=0.5 是对称胜负，
  **不是**市场上涨率；不虚造 baseline_n / baseline_k 去喂 ``readout()``。

为什么要 ``strict_bools``：``stats.block_bootstrap_readout`` 第一行就 ``bool(s)``，
+0.1 和 −0.1 都会变 True——连续差直接进去等于把「候选略差」也算成胜出。这里在入口
拒绝一切非 bool，让那条隐式强转永远收不到浮点数。

计算不舍入；mode / horizon / 版本 / PIT 由调用方分列。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from intelligence.services.methodology_backtest.stats import (
    binom_two_sided_p,
    block_bootstrap_readout,
    combined_verdict,
    four_state,
    split_halves,
    wilson,
)

from .contracts import ContractError, Gap, is_probability, iso_date, make_gap

CALIBRATION_EDGES: tuple[tuple[float, float], ...] = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))
VERDICT_TO_STATUS = {
    "supported": "supported",
    "refuted": "refuted",
    "not_distinguishable": "not_distinguishable",
    "insufficient_n": "insufficient",
}


def brier(p: Any, y: Any) -> float:
    if not is_probability(p):
        raise ContractError(f"p 不是概率：{p!r}")
    if isinstance(y, bool) or y not in (0, 1):
        raise ContractError(f"y 必须是 0 或 1：{y!r}")
    return (float(p) - float(y)) ** 2


@dataclass(frozen=True)
class PairSample:
    """一个 case 上两臂的完整配对：同一结果 y，两个概率。"""

    case_id: str
    entity_id: str
    trade_date: str
    p_base: float
    p_candidate: float
    y: int

    def __post_init__(self) -> None:
        iso_date(self.trade_date, field_name="PairSample.trade_date")
        brier(self.p_base, self.y)
        brier(self.p_candidate, self.y)


@dataclass(frozen=True)
class DailyDelta:
    trade_date: str
    n_pairs: int
    brier_base: float
    brier_candidate: float
    delta: float
    win: bool | None  # None = 平局

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date,
            "n_pairs": self.n_pairs,
            "brier_base": self.brier_base,
            "brier_candidate": self.brier_candidate,
            "delta": self.delta,
            "win": self.win,
        }


def daily_deltas(pairs: Iterable[PairSample]) -> list[DailyDelta]:
    by_day: dict[str, list[PairSample]] = {}
    for pair in pairs:
        by_day.setdefault(pair.trade_date, []).append(pair)
    out: list[DailyDelta] = []
    for day in sorted(by_day):
        items = by_day[day]
        n = len(items)
        b_base = math.fsum(brier(x.p_base, x.y) for x in items) / n
        b_cand = math.fsum(brier(x.p_candidate, x.y) for x in items) / n
        delta = math.fsum(brier(x.p_base, x.y) - brier(x.p_candidate, x.y) for x in items) / n
        win: bool | None
        if delta > 0:
            win = True
        elif delta < 0:
            win = False
        else:
            win = None
        out.append(DailyDelta(day, n, b_base, b_cand, delta, win))
    return out


def strict_bools(seq: Iterable[Any]) -> list[bool]:
    """只放行真正的 bool。0.1 / −0.1 / 1 / None 一律 TypeError——连续差不得进入 bool 统计。"""
    out: list[bool] = []
    for i, item in enumerate(seq):
        if type(item) is not bool:
            raise TypeError(f"胜出序列第 {i} 项不是 bool：{item!r}（{type(item).__name__}）；连续差不得进入 bool 统计")
        out.append(item)
    return out


def _rate(items: Sequence[bool]) -> float | None:
    return (sum(1 for x in items if x) / len(items)) if items else None


def calibration_buckets(samples: Iterable[tuple[Any, Any]], *, min_n: int) -> list[dict[str, Any]]:
    """五桶 [0,.2),[.2,.4),[.4,.6),[.6,.8),[.8,1]：计数、平均预测、实际频率；稀疏桶只报不足。"""
    rows = [(float(p), int(y)) for p, y in samples if brier(p, y) is not None]
    out: list[dict[str, Any]] = []
    for i, (lo, hi) in enumerate(CALIBRATION_EDGES):
        last = i == len(CALIBRATION_EDGES) - 1
        bucket = [(p, y) for p, y in rows if (lo <= p <= hi if last else lo <= p < hi)]
        count = len(bucket)
        item: dict[str, Any] = {"bucket": [lo, hi], "count": count, "sufficient": count >= min_n}
        if count >= min_n:
            item["mean_p"] = math.fsum(p for p, _y in bucket) / count
            item["observed_rate"] = math.fsum(y for _p, y in bucket) / count
        else:
            item["mean_p"] = None
            item["observed_rate"] = None
            item["reason"] = f"insufficient_n: {count} < {min_n}"
        out.append(item)
    return out


def paired_readout(
    days: Sequence[DailyDelta],
    *,
    policy: Mapping[str, Any],
    comparison_id: str,
) -> dict[str, Any]:
    """胜出日期检验 + 描述性平均差。返回可直接入收据的 dict（含 status / gaps / notes）。"""
    n_days = len(days)
    wins = sum(1 for d in days if d.win is True)
    losses = sum(1 for d in days if d.win is False)
    ties = sum(1 for d in days if d.win is None)
    gaps: list[Gap] = []
    notes: list[str] = []
    out: dict[str, Any] = {
        "comparison_id": comparison_id,
        "claim_kind": "paired_date_win_rate",
        "n_dates": n_days,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "mean_brier_base": (math.fsum(d.brier_base for d in days) / n_days) if n_days else None,
        "mean_brier_candidate": (math.fsum(d.brier_candidate for d in days) / n_days) if n_days else None,
        "mean_brier_difference_descriptive": (math.fsum(d.delta for d in days) / n_days) if n_days else None,
        "null_p0": policy["null_p0"],
        "min_n": policy["min_n"],
        "independent": None,
        "dependence": None,
        "verdict": None,
        "status": None,
        "daily": [d.to_dict() for d in days],
    }
    if n_days == 0:
        gaps.append(make_gap("no_pairs", [comparison_id], detail="没有完整配对日期"))
        out["status"] = "insufficient"
    elif ties > 0:
        gaps.append(
            make_gap(
                "ties_test_not_defined",
                [comparison_id],
                detail=f"{ties}/{n_days} 个日期 delta=0；v1 未定义含平局的胜出检验，平局保留在分母",
            )
        )
        if ties == n_days:
            notes.append("全平局：未观察到增量（平均差照报）")
        out["status"] = "insufficient"
    else:
        series = strict_bools([d.win for d in days])
        k = sum(1 for x in series if x)
        p0 = float(policy["null_p0"])
        lo, hi = wilson(k, n_days)
        first, second = split_halves(series)
        p_first, p_second = _rate(first), _rate(second)
        independent_verdict = four_state(n_days, k, p0, p_first, p_second, int(policy["min_n"]))
        out["independent"] = {
            "n": n_days,
            "k": k,
            "p": k / n_days,
            "p0": p0,
            "wilson_lo": lo,
            "wilson_hi": hi,
            "first_half": {"n": len(first), "p": p_first},
            "second_half": {"n": len(second), "p": p_second},
            "p_value": binom_two_sided_p(k, n_days, p0),
            "verdict": independent_verdict,
        }
        dependence = block_bootstrap_readout(
            [(comparison_id, d.trade_date, w) for d, w in zip(days, series)],
            p0=p0,
            block_len=int(policy["block_len"]),
            n_boot=int(policy["n_boot"]),
            min_blocks=int(policy["min_blocks"]),
            seed=int(policy["seed"]),
        )
        dep = dependence.to_dict()
        dep["note"] = "日期块沿唯一事件日取样是交易日块的近似；n_clusters 不是精确有效 N"
        out["dependence"] = dep
        final, note = combined_verdict(independent_verdict, dependence.verdict)
        if note:
            notes.append(note)
        out["verdict"] = final
        out["status"] = VERDICT_TO_STATUS[final]
        if independent_verdict == "insufficient_n":
            gaps.append(make_gap("insufficient_n", [comparison_id], detail=f"n_dates={n_days} < min_n={policy['min_n']}"))
        elif dependence.verdict == "insufficient_blocks":
            gaps.append(
                make_gap(
                    "insufficient_blocks",
                    [comparison_id],
                    detail=f"完整日期块 {dependence.n_blocks} < min_blocks={dependence.min_blocks}",
                )
            )
    out["gaps"] = [g.to_dict() for g in gaps]
    out["notes"] = notes
    return out


__all__ = [
    "CALIBRATION_EDGES",
    "DailyDelta",
    "PairSample",
    "brier",
    "calibration_buckets",
    "daily_deltas",
    "paired_readout",
    "strict_bools",
]

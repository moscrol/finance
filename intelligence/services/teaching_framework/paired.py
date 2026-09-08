"""两个 framework_version 在同一批参照日上的配对比较。

收据里的一致率（`index_stage.reference_comparison`）是每个版本各自对参照算的比例，两版分母
（已判定日）还不一样；把两个比例当独立样本相减，n≈120 时标准误 4 个点以上，分不出
「真涨了」和「挑出来的噪声」。这里改成逐日配对：同一天 A 对不对、B 对不对，只数翻转的
日子（`stats.mcnemar_exact`）。

两个口径并排给，不替读者选：

- ``all_reference_days``：全部参照日，未判定（ambiguous / no_evidence）算错——这是用户看到的
  「当天系统给了什么」。
- ``both_resolved``：两版都判定的日子——只比阶段判得对不对，不混入「判不判」的变化。

对错的定义与收据一致：``REFERENCE_STAGE_ALIASES[参照阶段] == 我们的 stage_coarse``。
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from intelligence.services.methodology_backtest.stats import mcnemar_exact

from .stage_rules import REFERENCE_STAGE_ALIASES, STAGES

PERIODS = ("all", "train", "validate")


def _is_correct(ours: str | None, ref_stage: str | None) -> bool:
    return ours in STAGES and REFERENCE_STAGE_ALIASES.get(str(ref_stage)) == ours


def _resolved(ours: str | None) -> bool:
    return ours in STAGES


def _paired_block(days: list[str], a: Mapping[str, str | None], b: Mapping[str, str | None], ref: Mapping[str, str | None]) -> dict[str, Any]:
    both = a_only = b_only = neither = 0
    for day in days:
        x = _is_correct(a.get(day), ref.get(day))
        y = _is_correct(b.get(day), ref.get(day))
        if x and y:
            both += 1
        elif y:
            a_only += 1  # A 错 B 对
        elif x:
            b_only += 1  # A 对 B 错
        else:
            neither += 1
    n = len(days)
    a_correct = both + b_only
    b_correct = both + a_only
    return {
        "days": n,
        "a_correct": a_correct,
        "b_correct": b_correct,
        "a_rate": round(a_correct / n, 4) if n else None,
        "b_rate": round(b_correct / n, 4) if n else None,
        "both_correct": both,
        "neither_correct": neither,
        "mcnemar": mcnemar_exact(a_only, b_only),
    }


def _receipt_caliber(days: list[str], ours: Mapping[str, str | None], ref: Mapping[str, str | None]) -> dict[str, Any]:
    resolved = [d for d in days if _resolved(ours.get(d))]
    agree = sum(1 for d in resolved if _is_correct(ours.get(d), ref.get(d)))
    return {
        "resolved_days": len(resolved),
        "agree_days": agree,
        "rate": round(agree / len(resolved), 4) if resolved else None,
    }


def paired_stage_agreement(
    a: Mapping[str, str | None],
    b: Mapping[str, str | None],
    reference: Mapping[str, str | None],
    *,
    train_until: str,
) -> dict[str, Any]:
    """``a`` / ``b``：``YYYY-MM-DD`` → ``stage_coarse``；``reference``：日 → 平台 ``cycle_stage``。

    只比三者都有行的日子。``train_until`` 之后的日子是验证期（与 ``calibrate-stages`` 同一切点）。
    """
    days = sorted(d for d in reference if d in a and d in b)
    periods = {
        "all": days,
        "train": [d for d in days if d <= train_until],
        "validate": [d for d in days if d > train_until],
    }
    out: dict[str, Any] = {"train_until": train_until, "overlap_days": len(days), "periods": {}}
    for name in PERIODS:
        ds = periods[name]
        both_resolved = [d for d in ds if _resolved(a.get(d)) and _resolved(b.get(d))]
        flips: Counter[str] = Counter()
        for d in ds:
            x = _is_correct(a.get(d), reference.get(d))
            y = _is_correct(b.get(d), reference.get(d))
            if x != y:
                flips[f"{reference.get(d)} × {'a_wrong_b_right' if y else 'a_right_b_wrong'}"] += 1
        out["periods"][name] = {
            "all_reference_days": _paired_block(ds, a, b, reference),
            "both_resolved": _paired_block(both_resolved, a, b, reference),
            "receipt_caliber": {
                "a": _receipt_caliber(ds, a, reference),
                "b": _receipt_caliber(ds, b, reference),
            },
            "flips_by_reference_stage": dict(sorted(flips.items())),
        }
    return out

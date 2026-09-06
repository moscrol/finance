"""Declarative seven-stage scoring and transition graph."""

from __future__ import annotations
from typing import Any, Mapping

STAGES = (
    "左底向下",
    "左底向上",
    "缩量右底",
    "共建主线阶段",
    "主流主升",
    "高位震荡",
    "回踩周均线",
)
UNDER_MA = ("左底向下", "左底向上", "缩量右底")
SEVEN_STAGES = STAGES
GRAPH = {
    STAGES[0]: (STAGES[1],),
    STAGES[1]: (STAGES[2],),
    STAGES[2]: (STAGES[3],),
    STAGES[3]: (STAGES[4],),
    STAGES[4]: (STAGES[5],),
    STAGES[5]: (STAGES[6],),
    STAGES[6]: (STAGES[0],),
}
GRAPH["高位震荡"] = ("回踩周均线", "左底向下")
GRAPH["左底向上"] = ("缩量右底", "缩量右底")
for s in STAGES:
    GRAPH[s] = tuple(dict.fromkeys((s,) + tuple(GRAPH.get(s, ()))))


def score_flags(
    f: Mapping[str, Any], params: Mapping[str, Any] | None = None
) -> dict[str, int]:
    def v(k: str) -> Any:
        return f.get(k)

    def any_true(*xs: Any) -> bool:
        return any(x is True for x in xs)

    scores = {s: 0 for s in STAGES}
    # E/H predicates; unknown does not earn a point.
    if v("cross_below_week_ma") is True and any_true(
        v("volume_surge"), v("gap_down_open")
    ):
        scores["左底向下"] += 1
    if v("above_week_ma") is False and v("deviation_band") == "below":
        scores["左底向下"] += 1
    if v("deviation_band") == "oversold":
        scores["左底向上"] += 1
    if v("above_week_ma") is False and v("deviation_narrowing") is True:
        scores["左底向上"] += 1
    minimum = int((params or {}).get("shrink_streak_min", 2))
    if (
        isinstance(v("volume_shrink_streak"), (int, float))
        and v("volume_shrink_streak") >= minimum
        and v("above_week_ma") is False
    ):
        scores["缩量右底"] += 1
    if v("cross_above_week_ma") is True and v("volume_surge") is True:
        scores["共建主线阶段"] += 1
    if v("above_week_ma") is True:
        scores["共建主线阶段"] += 1
    for definition in ("volume_top3", "vendor"):
        if (
            v(f"mainline_amount_stepping_up.{definition}") is True
            and v(f"mainline_share_expanding.{definition}") is True
        ):
            scores["主流主升"] += 1
    if v("deviation_band") == "overheated":
        scores["高位震荡"] += 1
    if v("above_week_ma") is True and v("volume_surge") is False:
        scores["高位震荡"] += 1
    if (
        v("above_week_ma") is True
        and v("deviation_band") == "above"
        and v("shrink_day") is True
    ):
        scores["回踩周均线"] += 1
    return scores


def resolve_stage(
    scores: Mapping[str, int], previous: str | None
) -> tuple[str, str, list[str]]:
    top = max(scores.values(), default=0)
    if top == 0:
        return "no_evidence", "no_evidence", []
    tied = sorted([s for s, n in scores.items() if n == top])
    if len(tied) == 1:
        return tied[0], "argmax", tied
    outgoing = tuple(x for x in GRAPH.get(previous or "", ()) if x != previous)
    reachable = [s for s in tied if s in outgoing]
    if len(reachable) == 1:
        return reachable[0], "graph", tied
    return "ambiguous", "ambiguous", tied


def stage_fine(
    coarse: str, flags: Mapping[str, Any], previous: str | None = None
) -> str:
    if coarse not in STAGES:
        return "unassigned"
    if coarse == "缩量右底":
        n = flags.get("volume_shrink_streak")
        return "二次探底" if isinstance(n, (int, float)) and n > 2 else coarse
    if coarse == "高位震荡" and previous != coarse:
        return "见顶"
    return coarse


def derive_turns(sequence: list[str | None]) -> list[dict[str, int]]:
    out = []
    prev = None
    for stage in sequence:
        valid = stage in STAGES
        out.append(
            {
                "turn_up": int(valid and stage == "共建主线阶段" and prev in UNDER_MA),
                "turn_top": int(valid and stage == "高位震荡" and prev != stage),
                "turn_down": int(valid and stage == "左底向下" and prev != stage),
            }
        )
        prev = stage if valid else None
    return out

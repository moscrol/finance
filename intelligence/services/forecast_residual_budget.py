"""展望座位的残差预算：开口包齐才升 deep，连打同问句停机。

P1 量纲（审查钉死）：``ResearchPolicy.for_tier("deep")`` 的一对
``(max_steps, total_seconds)`` = 12×240s。禁止再拧每格剩余预算。
确定性 owner 题（涨停家数 / dated 事实）永不进本支。

本模块只留领域判定（座位对不对、开口包齐没齐、该不该停机）。「升」的账本动作
（提 caps / 铸 grant / 重建 deadline / 翻 contract tier）住在
``intelligence/runtime/tier_promotion.promote_forecast_residual``——领域层不碰账本。
"""

from __future__ import annotations

from typing import Iterable

FORECAST_RESIDUAL_QUESTION_TYPE = "market_forecast"
DO_NOT_LENGTHEN_QUESTION_TYPES = frozenset(
    {
        "external_market",
        "dated_market_review",
        "market_watch",
        "watchlist_digest",
        "disclosure_scan",
    }
)
FORECAST_RESIDUAL_SPIN = "forecast_residual_duplicate_spin"


def forecast_opening_pack_ready(items: Iterable[object] | None) -> bool:
    """五日包已发卡（含 locked / unavailable）。旧 3 日双红个数不算齐。"""

    for item in items or ():
        title = str(getattr(item, "title", "") or "")
        detail = str(getattr(item, "detail", "") or "")
        if title.endswith("四袋") or title == "先验周量能序列":
            return True
        blob = f"{title} {detail}"
        if "status=locked" in blob or "复盘写入中" in blob:
            return True
        if "status=unavailable" in blob:
            return True
    return False


def should_promote_forecast_residual(
    question_type: str,
    opening_items: Iterable[object] | None,
) -> bool:
    question = str(question_type or "").strip()
    if question != FORECAST_RESIDUAL_QUESTION_TYPE:
        return False
    if question in DO_NOT_LENGTHEN_QUESTION_TYPES:
        return False
    return forecast_opening_pack_ready(opening_items)


def forecast_residual_halt_reason(
    *,
    question_type: str,
    research_tier: str,
    batch_errors: Iterable[str | None],
) -> str | None:
    """深档展望残差里第二次同问句：停机，禁止再要一轮。"""

    if str(question_type or "").strip() != FORECAST_RESIDUAL_QUESTION_TYPE:
        return None
    if str(research_tier or "").strip() != "deep":
        return None
    if any(str(error or "") == "duplicate_query" for error in batch_errors):
        return FORECAST_RESIDUAL_SPIN
    return None

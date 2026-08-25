"""展望 P2：首轮露出未核验格；点名补格时不重跑五日包。

复用已有 followup 稿与 ``open_gaps``，不新造第三条追问链。
公开稿只用用户语言，禁止 ``【质检``。
"""

from __future__ import annotations

import re

from intelligence.services.session_projection import render_unknown_slots

FORECAST_QUESTION_TYPE = "market_forecast"
GAP_MIRROR_FOLLOWUP_RE = re.compile(r"上一轮「[^」]+」未完成核验")
_TYPED_GRID_FOLLOWUP_RE = re.compile(
    r"把(?:续走条件|失效条件|情景(?:路径)?|判断继续成立)[^。]{0,16}写具体"
)
_FORECAST_GAP_USER_LABELS = {
    "列出判断继续成立的可核验条件": "续走条件（判断继续成立要看到什么）",
    "列出判断失效或降级的条件": "失效条件（这句话什么时候作废）",
    "给出条件化情景路径": "情景路径（涨/平/跌各看什么）",
    "直接回答用户问题并说明判断强度": "直接判断",
    "针对预测窗口的直接判断": "直接判断",
}
WEEKLY_PACK_REUSE_TITLE = "五日包沿用上轮"
WEEKLY_PACK_REUSE_DETAIL = (
    "本轮不重跑五日包，请引用上轮已上桌的日袋与 E 号，只补点名的格。"
)


def user_label_for_forecast_gap(gap: str) -> str:
    raw = str(gap or "").strip()
    if not raw:
        return ""
    return _FORECAST_GAP_USER_LABELS.get(raw, raw)


def is_forecast_grid_followup(question: str) -> bool:
    text = str(question or "")
    return bool(
        GAP_MIRROR_FOLLOWUP_RE.search(text) or _TYPED_GRID_FOLLOWUP_RE.search(text)
    )


def should_skip_weekly_pack(*, question: str, question_type: str) -> bool:
    if str(question_type or "").strip() != FORECAST_QUESTION_TYPE:
        return False
    return is_forecast_grid_followup(question)


def append_unverified_forecast_grids(
    answer: str,
    *,
    question_type: str,
    open_gaps: tuple[str, ...] = (),
) -> str:
    """可用稿后面补未核验格。主题题与空稿不扩。"""

    body = str(answer or "")
    if str(question_type or "").strip() != FORECAST_QUESTION_TYPE:
        return body
    if not body.strip():
        return body
    if "这次还核验不了" in body or "【质检" in body:
        return body
    labels = tuple(
        user_label_for_forecast_gap(gap)
        for gap in open_gaps
        if str(gap or "").strip()
    )
    extra = render_unknown_slots(labels)
    if not extra:
        return body
    return f"{body.rstrip()}\n\n{extra}"

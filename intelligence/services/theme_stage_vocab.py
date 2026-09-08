"""题材生命周期单一词表（工单 #21 剩余 P1 / roadmap G-04）。

题材阶段此前有**三套词**：

1. ``theme_lifecycle.py`` 八阶段（新出现 / 旧逻辑唤醒 / 升温验证 / 加速定价 / 高位分歧 / 二阶段回流 / 衰退观察 / 证伪退出）
   ——面向「当前快照 + 消息面」的诊断语言，历史上大多数日子算不出来；
2. ``theme_lifecycle_timeline.py`` 七段（酝酿 / 首发 / 发酵 / 主升 / 分歧 / 退潮 / 回流）
   ——从盘面逐日行确定性派生的状态机，每段有触发条件、可在任意区间重放；
3. ``2026-09-04-methodology-backtest-structured-history-design.md`` §2 给旁路库预留的五段（启动 / 发酵 / 高潮 / 分歧 / 退潮）——从未落地。

**钦定：七段是标签值**（唯一能在历史上每天重算的那套），八阶段降为**读法层别名**（通过映射表翻译、不再作为
标签值出现），五段预留**作废**（并进七段：启动 → 首发、高潮 → 主升，其余同名）。判据不是哪套更像行话，
而是哪套有确定性派生——词表要服务的是回测与回放。

一对多的映射必须带条件：八阶段「升温验证」对应七段的**首发**（首次双红 / 首板）与**发酵**（持续双红）两段；
``eight_to_canonical(word, first_signal=...)`` 不给条件时按发酵（持续态），并在返回值里标明 ``ambiguous``。
「衰退观察 / 证伪退出」都映到退潮：证伪退出还要消息面证伪事件，盘面状态机只到退潮。

本模块**只统一词**，不动 ``theme_lifecycle_timeline`` 的阈值（``DOUBLE_RED_* / MAINUP_CONSECUTIVE /
EBB_BREAK_DAYS / REFLOW_CONFIRM_DAYS``）——阈值改动是另一单，且要过统计门。
文档表在 ``UBIQUITOUS_LANGUAGE.md``「题材生命周期」，``render_mapping_markdown()`` 从本表生成，测试比对两边一致。
"""

from __future__ import annotations

from dataclasses import dataclass

from intelligence.services import theme_lifecycle as _eight
from intelligence.services import theme_lifecycle_timeline as _seven

MAPPING_VERSION = "tsm-v1"
GAP = "gap"

# 钦定标签值：七段（顺序 = 生命周期顺序；回流是循环入口，排最后）
CANONICAL_STAGES: tuple[str, ...] = (
    _seven.STAGE_INCUBATION,
    _seven.STAGE_FIRST_MOVE,
    _seven.STAGE_FERMENT,
    _seven.STAGE_MAIN_UP,
    _seven.STAGE_DIVERGENCE,
    _seven.STAGE_EBB,
    _seven.STAGE_REFLOW,
)

# 八阶段 → 七段（读法层别名 → 标签值）。值为元组：可能对应多段；条件写在 CONDITIONS。
EIGHT_TO_CANONICAL: dict[str, tuple[str, ...]] = {
    _eight.STAGE_NEW: (_seven.STAGE_INCUBATION,),
    _eight.STAGE_REAWAKEN: (_seven.STAGE_INCUBATION,),
    _eight.STAGE_WARMING: (_seven.STAGE_FIRST_MOVE, _seven.STAGE_FERMENT),
    _eight.STAGE_ACCELERATION: (_seven.STAGE_MAIN_UP,),
    _eight.STAGE_HIGH_DIVERGENCE: (_seven.STAGE_DIVERGENCE,),
    _eight.STAGE_SECOND_WAVE: (_seven.STAGE_REFLOW,),
    _eight.STAGE_DECAY_WATCH: (_seven.STAGE_EBB,),
    _eight.STAGE_FALSIFIED_EXIT: (_seven.STAGE_EBB,),
    _eight.STAGE_UNKNOWN: (GAP,),
}
CONDITIONS: dict[str, str] = {
    _eight.STAGE_NEW: "需消息面证据；无则 gap，不是「酝酿」",
    _eight.STAGE_REAWAKEN: "同上；旧逻辑二次唤醒仍是酝酿态",
    _eight.STAGE_WARMING: "首次双红 / 首板 → 首发；此后持续双红 → 发酵（一词对两段，翻译时要给 first_signal）",
    _eight.STAGE_FALSIFIED_EXIT: "证伪退出要消息面证伪事件；盘面状态机只能到退潮",
    _eight.STAGE_UNKNOWN: "缺原料，不猜",
}

# 设计稿五段预留 → 七段（作废别名，只为读旧文档 / 旧规则草稿）
FIVE_LEGACY_TO_CANONICAL: dict[str, str] = {
    "启动": _seven.STAGE_FIRST_MOVE,
    "发酵": _seven.STAGE_FERMENT,
    "高潮": _seven.STAGE_MAIN_UP,
    "分歧": _seven.STAGE_DIVERGENCE,
    "退潮": _seven.STAGE_EBB,
}

# 反向：七段 → 八阶段别名（读法层要念给人听时用）
CANONICAL_TO_EIGHT_ALIASES: dict[str, tuple[str, ...]] = {}
for _word, _targets in EIGHT_TO_CANONICAL.items():
    for _t in _targets:
        CANONICAL_TO_EIGHT_ALIASES.setdefault(_t, ())
        CANONICAL_TO_EIGHT_ALIASES[_t] = (*CANONICAL_TO_EIGHT_ALIASES[_t], _word)


@dataclass(frozen=True)
class Translation:
    canonical: str
    source_vocab: str  # canonical | eight | five_legacy
    ambiguous: bool = False
    note: str = ""

    def to_dict(self) -> dict[str, object]:
        return {"canonical": self.canonical, "source_vocab": self.source_vocab, "ambiguous": self.ambiguous, "note": self.note}


def eight_to_canonical(word: str, *, first_signal: bool | None = None) -> Translation:
    """八阶段 → 七段。「升温验证」一词对两段：``first_signal=True`` → 首发，``False`` → 发酵，``None`` → 发酵且标 ambiguous。"""
    targets = EIGHT_TO_CANONICAL.get(word)
    if targets is None:
        raise ValueError(f"{word!r} 不是八阶段词（{sorted(EIGHT_TO_CANONICAL)}）")
    if len(targets) == 1:
        return Translation(targets[0], "eight", note=CONDITIONS.get(word, ""))
    if first_signal is None:
        return Translation(targets[-1], "eight", ambiguous=True, note=CONDITIONS[word])
    return Translation(targets[0] if first_signal else targets[-1], "eight", note=CONDITIONS[word])


def canonical_of(word: str | None, *, first_signal: bool | None = None) -> Translation:
    """任一套词 → 七段（或 gap）。不认识的词抛错——词表统一之后没有「顺手放行」。"""
    w = str(word or "").strip()
    if not w or w == GAP:
        return Translation(GAP, "canonical")
    if w in CANONICAL_STAGES:
        return Translation(w, "canonical")
    if w in EIGHT_TO_CANONICAL:
        return eight_to_canonical(w, first_signal=first_signal)
    if w in FIVE_LEGACY_TO_CANONICAL:
        return Translation(FIVE_LEGACY_TO_CANONICAL[w], "five_legacy", note="设计稿五段预留已作废，按七段读")
    raise ValueError(f"{w!r} 不在任何一套题材阶段词表里（七段 / 八阶段 / 五段作废别名）")


def stage_on_day(segments: list, day: str) -> str:
    """七段状态机的段落 → 某一天的标签值；落在段外（首个盘面信号之前、或段间空档）→ gap。"""
    for seg in segments:
        if str(seg.start_date)[:10] <= day <= str(seg.end_date)[:10]:
            return seg.stage
    return GAP


def render_mapping_markdown() -> str:
    """UBIQUITOUS_LANGUAGE.md「题材生命周期」的映射表正文，由本模块生成（文档 == 代码，测试钉住）。"""
    lines = ["| 钦定（标签值） | 八阶段别名（读法层） | 备注 |", "|---|---|---|"]
    for stage in CANONICAL_STAGES:
        aliases = CANONICAL_TO_EIGHT_ALIASES.get(stage, ())
        notes = [CONDITIONS[a] for a in aliases if a in CONDITIONS]
        lines.append(f"| {stage} | {' / '.join(aliases) if aliases else '—'} | {'；'.join(notes) if notes else ''} |")
    lines.append(f"| `{GAP}` | {_eight.STAGE_UNKNOWN} | {CONDITIONS[_eight.STAGE_UNKNOWN]} |")
    return "\n".join(lines)

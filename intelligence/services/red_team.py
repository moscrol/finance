"""红队反方（devils-advocate）：按下按钮前的制度化反面陈述.

output_review 只做「是否有反证」的存在性检查；本模块补的是**生成管线**——
对一条看多/看空判断，从你自己的私有台账里拉出最强反面材料：

1. ``corrections.jsonl``  你在同类题材/表述上纠正过的历史错误（专治重复犯错，
   这是 corrections 的第二个消费者，与 framework 回灌互补）；
2. ``checkpoints`` 校准    你历史低胜率的二阶推演类别——若本判断落在这些类别里，
   显式提示「这是你常落空的推演类型」；
3. 确定性反方清单          共识抢跑 / 板块 beta 误认兑现 / 覆盖透支 / 证据单薄
   等固定叙事骨架，不依赖 LLM；
4. 可回检性检查            判断里没有数值阈值 = 不可证伪 = 不进胜率统计，
   提示补登 checkpoint。

铁律：反方输出**不给结论、不打分**，只陈述最强反面叙事——KPI 不是说服你，
是保证你承担后果前见过反面。只读台账、不写任何文件、只用标准库。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from intelligence.services.checkpoints import Calibration, DEFAULT_CALIBRATION_MIN_N

# 命中率低于此阈值且样本足够的类别，视为「你历史常落空的推演类型」。
WEAK_CATEGORY_RATE = 0.4

# 确定性反方叙事骨架（与 research_brief.CounterEvidencePlan 风格一致，
# 但面向「人已形成判断」的场景，不依赖证据审计结构）。
GENERIC_REBUTTALS = (
    "价格可能已抢跑：你能从公开材料推出的逻辑，市场大概率已定价——确认你的依据里有共识之外的部分",
    "板块 beta 可能被误认成个股/事件兑现：同题材其他标的若同涨，说明驱动是板块情绪而非这条逻辑",
    "证据可能停在观点层：卖方观点/媒体报道不是公告/订单/量产——检查最硬的一条证据是 L 几",
    "覆盖可能已透支：若这是该方向第 N 篇卖方覆盖而非首覆，增量信息趋零、拥挤风险递增",
    "时间窗可能错配：逻辑对但兑现在两个季度后，等待期的回撤会先把你洗出去",
)

_NUM_RE = re.compile(r"\d")


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


@dataclass
class RedTeamBrief:
    claim: str
    themes: list[str] = field(default_factory=list)
    category: str | None = None
    past_mistakes: list[dict[str, Any]] = field(default_factory=list)
    weak_categories: list[dict[str, Any]] = field(default_factory=list)
    category_warning: str | None = None
    rebuttals: list[str] = field(default_factory=list)
    checkable: bool = True
    checkability_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "themes": self.themes,
            "category": self.category,
            "past_mistakes": self.past_mistakes,
            "weak_categories": self.weak_categories,
            "category_warning": self.category_warning,
            "rebuttals": self.rebuttals,
            "checkable": self.checkable,
            "checkability_note": self.checkability_note,
        }

    def to_markdown(self) -> str:
        lines = ["# 红队反方（不给结论，只陈述最强反面）", f"> 判断：{self.claim}"]
        lines.append("")
        lines.append("## 你在同类判断上纠正过的错")
        if self.past_mistakes:
            for rec in self.past_mistakes:
                principle = str(rec.get("principle") or "").strip()
                original = str(rec.get("original") or "").strip()
                correction = str(rec.get("correction") or "").strip()
                parts = []
                if original:
                    parts.append(f"当时说「{original}」")
                parts.append(f"被纠正为「{correction}」")
                if principle:
                    parts.append(f"原则：{principle}")
                lines.append(f"- {'；'.join(parts)}")
        else:
            lines.append("- （corrections 里没有同类题材的历史纠偏）")
        lines.append("")
        lines.append("## 你历史低胜率的推演类别")
        if self.category_warning:
            lines.append(f"- ⚠ {self.category_warning}")
        if self.weak_categories:
            for wc in self.weak_categories:
                lines.append(
                    f"- {wc['category']}：{wc['n']} 中 {wc['hits']} 命中"
                    f"（命中率 {round(wc['hit_rate'] * 100)}%）——若本判断属此类，主动要反证"
                )
        elif not self.category_warning:
            lines.append("- （已回检样本不足，暂无低胜率类别可对照）")
        lines.append("")
        lines.append("## 最强反面叙事（固定骨架，逐条自问）")
        for r in self.rebuttals:
            lines.append(f"- {r}")
        lines.append("")
        lines.append("## 可回检性")
        if self.checkable:
            lines.append("- 判断含数值/阈值表述，可登记 checkpoint 到期回检")
        else:
            lines.append(f"- ⚠ {self.checkability_note}")
        lines.append(
            "- 建议：`checkpoint register --claim ... --due ... --category ... --source manual`"
        )
        return "\n".join(lines) + "\n"


def find_past_mistakes(
    corrections: list[dict[str, Any]],
    claim: str,
    themes: list[str],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """从纠偏台账里捞与本判断题材/关键词重叠的历史纠正（最近的在前）。"""
    claim_norm = _norm(claim)
    theme_norms = [_norm(t) for t in themes if _norm(t)]
    out: list[dict[str, Any]] = []
    for rec in reversed(corrections):
        rec_themes = [_norm(t) for t in (rec.get("themes") or [])]
        text_norm = _norm(
            " ".join(str(rec.get(k) or "") for k in ("correction", "original", "principle"))
        )
        theme_hit = any(t in theme_norms for t in rec_themes) or any(
            t and t in claim_norm for t in rec_themes
        )
        keyword_hit = any(t and t in text_norm for t in theme_norms)
        if theme_hit or keyword_hit:
            out.append(rec)
        if len(out) >= limit:
            break
    return out


def weak_categories(
    calibration: Calibration,
    min_n: int = DEFAULT_CALIBRATION_MIN_N,
) -> list[dict[str, Any]]:
    """校准里样本足够且命中率低的推演类别（最该质疑的在前）。"""
    out: list[dict[str, Any]] = []
    for st in calibration.by_category:
        if st.n >= min_n and st.hit_rate < WEAK_CATEGORY_RATE:
            out.append(
                {"category": st.category, "n": st.n, "hits": st.hits, "hit_rate": st.hit_rate}
            )
    return out


def build_red_team_brief(
    claim: str,
    *,
    themes: list[str] | None = None,
    category: str | None = None,
    corrections: list[dict[str, Any]] | None = None,
    calibration: Calibration | None = None,
) -> RedTeamBrief:
    """组装一份反方陈述。``claim`` 为空时抛 ``ValueError``。"""
    text = str(claim or "").strip()
    if not text:
        raise ValueError("claim 不能为空：红队至少要有一条被审的判断")
    theme_list = [str(t).strip() for t in (themes or []) if str(t).strip()]
    brief = RedTeamBrief(claim=text, themes=theme_list, category=category)
    brief.past_mistakes = find_past_mistakes(corrections or [], text, theme_list)
    cal = calibration or Calibration()
    brief.weak_categories = weak_categories(cal)
    if category:
        cat_norm = _norm(category)
        for wc in brief.weak_categories:
            if _norm(wc["category"]) == cat_norm:
                brief.category_warning = (
                    f"本判断的推演类别「{category}」是你历史常落空的类型"
                    f"（{wc['n']} 中仅 {wc['hits']} 命中）"
                )
                break
    brief.rebuttals = list(GENERIC_REBUTTALS)
    if not _NUM_RE.search(text):
        brief.checkable = False
        brief.checkability_note = (
            "判断里没有任何数值阈值——不可证伪的判断进不了胜率统计，先补「什么数字出现即算错」"
        )
    return brief

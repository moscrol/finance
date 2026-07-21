"""Evidence capability planning for ownerless research.

Question type remains a coarse controller output. This module resolves the
evidence products a contract must obtain without adding another route table.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EvidenceRequirement:
    provider_name: str
    capability: str
    mandatory: bool
    freshness: str = "current"
    reason: str = ""


@dataclass(frozen=True)
class EvidencePlan:
    profile: str = "general"
    requirements: tuple[EvidenceRequirement, ...] = ()
    freshness: str = "current"

    @property
    def mandatory_provider_names(self) -> tuple[str, ...]:
        return tuple(item.provider_name for item in self.requirements if item.mandatory)

    @property
    def optional_provider_names(self) -> tuple[str, ...]:
        return tuple(item.provider_name for item in self.requirements if not item.mandatory)

    @property
    def mandatory_capabilities(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.capability for item in self.requirements if item.mandatory))

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "freshness": self.freshness,
            "requirements": [asdict(item) for item in self.requirements],
        }


_CURRENT_MARKERS = (
    "当前", "目前", "现在", "最新", "主线", "盘面", "市场结构", "成交", "涨停",
)
_HISTORICAL_MARKERS = ("2025", "2024", "历史上", "过去几年", "去年")


def is_current_market_query(query: str) -> bool:
    """识别需要同日市场事实的问题，不改变粗粒度 question_type。"""

    normalized = re.sub(r"\s+", "", str(query or "")).casefold()
    if not normalized or any(marker in normalized for marker in _HISTORICAL_MARKERS):
        return False
    return any(marker in normalized for marker in _CURRENT_MARKERS) and any(
        marker in normalized for marker in ("市场", "大盘", "行情", "板块", "主线", "盘面")
    )


def resolve_evidence_plan(
    query: str,
    *,
    question_type: str,
    freshness: str = "current",
) -> EvidencePlan:
    # “概念解释 + 当前事实”是复合任务，不能被单一 concept_definition
    # 标签吞掉后半句。这里增加证据需求而不增加 route-table 题型：定义和
    # 当日事实仍由同一个 Generic Owner/ResearchState 合成。
    if question_type == "concept_definition" and is_current_market_query(query):
        return EvidencePlan(
            "current_market_fact",
            (
                EvidenceRequirement(
                    "D4",
                    "mainline_context",
                    True,
                    "current",
                    "当前市场指标定义与同日板块事实",
                ),
            ),
            "current",
        )
    # 纯方法论/纯概念解释里的“市场、主线、当前”等词是讨论对象，不是要求
    # 当前盘面事实；能力层排除避免金融数据泄漏进知识题。
    if question_type in {"methodology_discussion", "answer_review", "concept_definition"}:
        return EvidencePlan("general", (), freshness)
    if question_type == "market_forecast":
        return EvidencePlan(
            "market_forecast",
            (
                EvidenceRequirement("MARKET_DAILY", "market_data", True, "current", "最新市场总览"),
                EvidenceRequirement("D4", "mainline_context", False, "current", "主线结构补充"),
            ),
            "current",
        )
    if freshness == "current" and is_current_market_query(query):
        return EvidencePlan(
            "mainline_current",
            (
                EvidenceRequirement("MARKET_DAILY", "market_data", True, "current", "同日市场总览"),
                EvidenceRequirement("D4", "mainline_context", True, "current", "同日主线结构"),
                EvidenceRequirement("D0", "market_timeseries", False, "current", "盘面时序补充"),
                EvidenceRequirement("D6", "market_midterm", False, "current", "中期持续性补充"),
                EvidenceRequirement("W7", "news_search", False, "current", "消息面补充"),
            ),
            "current",
        )
    return EvidencePlan("general", (), freshness)

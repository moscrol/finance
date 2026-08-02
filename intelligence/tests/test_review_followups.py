"""code review 查出的问题的回归。每条都对应一个已验证会触发的具体场景。"""
from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from intelligence.services import ask_blocks, evidence_registry
from intelligence.services.answer_orchestrator import (
    _classify_question_type,
    _normalize,
)
from intelligence.services.ask import (
    _market_data_date_line,
    _market_today,
    load_theme_candidates,
)
from intelligence.services.ask_types import AskOptions


def _classify(query: str) -> str:
    return _classify_question_type(query, _normalize(query))[0]


# --- 板块/题材问句不能被抢进全市场复盘 -------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "创新药板块当前主线是哪几个",
        "半导体设备市场当前强弱如何",
        "固态电池目前处于什么阶段",
        "光模块题材现在什么阶段",
        "宁德时代现在处于什么阶段",
    ],
)
def test_named_subject_keeps_its_own_route(query: str) -> None:
    """点了具体板块/题材/个股的问句拿到全市场复盘，是答错了对象。

    复盘的主线块和知识库锚点讲的是市场的题材（消费零售/半导体/AI算力），
    跟用户问的创新药没有关系。
    """
    assert _classify(query) != "market_review"


@pytest.mark.parametrize(
    "query",
    [
        "今天大盘处于什么阶段？当前主线是哪几个方向？",
        "大盘目前在哪个阶段",
        "目前主线是哪几个",
        "今天什么阶段，明天大盘怎么看",
        "收盘后大盘什么状态",
    ],
)
def test_whole_market_questions_still_route_to_review(query: str) -> None:
    assert _classify(query) == "market_review"


def test_state_word_without_a_time_anchor_is_still_not_the_present() -> None:
    """既有约定：光有状态词不构成「问现状」。"""
    assert _classify("大盘处于什么阶段") != "market_review"


# --- 不许悄悄回退到生产库 ---------------------------------------------------

def test_knowledge_anchor_never_falls_back_to_the_production_db() -> None:
    """调用方没给库就是没要盘面数据。

    回退 DEFAULT_MARKET_DB_PATH 会让单测和 eval 读到真实生产库——
    test_market_review_* 就是这么被打破的，而且只在设了 FINANCE_WS 时复现。
    """
    assert ask_blocks.mainline_knowledge_coverage(None) == ("", [], [])
    assert ask_blocks._market_review_knowledge_anchor_block_for_llm(None) == ""


# --- 损坏快照不能抛出 -------------------------------------------------------

def test_only_a_corrupt_snapshot_returns_not_found_instead_of_raising() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "2026-07-30-theme-candidates.json").write_text(
            "{ 截断的 json", encoding="utf-8"
        )

        loaded = load_theme_candidates(tmp, None)

        assert loaded["found"] is False
        assert loaded["doc"] == {}
        assert loaded["warnings"]


def test_corrupt_newest_beside_an_empty_older_one_also_survives() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "2026-07-29-theme-candidates.json").write_text(
            json.dumps({"found": False, "candidates": []}), encoding="utf-8"
        )
        (Path(tmp) / "2026-07-30-theme-candidates.json").write_text(
            "{ 截断", encoding="utf-8"
        )

        loaded = load_theme_candidates(tmp, None)

        assert loaded["found"] is False


# --- 时区 -------------------------------------------------------------------

def test_market_today_uses_shanghai_not_the_host_clock() -> None:
    """容器默认 UTC，北京时间 00:00~08:00 之间 date.today() 会返回前一天。

    那会把一份真正属于今天的快照判成过期，而这条判断是以硬要求的形式下发的
    （「正文首句必须写明数据截至 X」）——时区判错比不判更糟。
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    assert _market_today() == datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    assert "即今天" in _market_data_date_line(_market_today())


def test_yesterday_is_reported_as_not_current() -> None:
    yesterday = (date.fromisoformat(_market_today()) - timedelta(days=1)).isoformat()

    line = _market_data_date_line(yesterday)

    assert "不是当日数据" in line
    assert _market_today() in line


# --- 证据层级必须进载荷 -----------------------------------------------------

def test_company_rendering_carries_the_evidence_tier() -> None:
    """块本身要求模型标注证据层级；层级不在载荷里，模型只能省略或编造。

    实测同一方向内 graph_only（ASML，非 A 股）与 L1（东芯股份）会被渲染成
    完全一样的样子。
    """
    assert ask_blocks._format_company(
        {"company": "东芯股份", "role": "集成电路设计", "tier": "L1"}
    ) == "东芯股份（集成电路设计｜L1）"
    assert ask_blocks._format_company(
        {"company": "ASML", "role": "图谱弱关联", "tier": "graph_only"}
    ) == "ASML（图谱弱关联｜graph_only）"


# --- 只匹配到空串的方向属于「无积累」 ---------------------------------------

def test_blank_only_matches_count_as_uncovered(monkeypatch) -> None:
    """用原始列表判定会让这种方向通过，然后渲染出「- 半导体：」这样的空行。"""

    class _Blank:
        def get_concept_matches(self, theme, limit=3):
            return {"items": [{"concept": "   "}]}

        def get_exposure_matches(self, theme, limit=4):
            return {"items": [{"company": "", "role": "x"}]}

        def get_evidence(self, theme, limit=3):
            return {"items": []}

    monkeypatch.setattr(ask_blocks, "_mainline_theme_names", lambda *a, **k: ("2026-07-29", ["半导体"]))
    import intelligence.adapters.knowledge as knowledge_module

    monkeypatch.setattr(knowledge_module, "KnowledgeAdapter", lambda **k: _Blank())

    _date, covered, uncovered = ask_blocks.mainline_knowledge_coverage("/tmp/x.duckdb")

    assert covered == []
    assert uncovered == ["半导体"]


# --- provider 注册与门控 ---------------------------------------------------

def test_knowledge_anchor_is_registered_and_does_not_collide_with_valuation() -> None:
    """D5 已经是估值数据块；此前这条腿无条件追加且撞了它的标签。"""
    names = evidence_registry.PROVIDER_NAMES

    assert "MAINLINE_KB" in names
    valuation = next(s for s in evidence_registry.REGISTRY if s.name == "D5")
    assert valuation.label == "估值数据块"


def test_knowledge_anchor_can_be_switched_off_by_enabled_providers() -> None:
    options = AskOptions(query="q", enabled_providers=frozenset({"D0"}))

    assert evidence_registry.provider_enabled(options, "MAINLINE_KB") is False
    assert evidence_registry.provider_enabled(AskOptions(query="q"), "MAINLINE_KB") is True

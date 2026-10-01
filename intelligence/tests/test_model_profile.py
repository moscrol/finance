"""模型档位（FWP_MODEL_PROFILE）：standard 与引入前逐项等价；frontier 只放开天花板。"""

from __future__ import annotations

import json

import pytest

from intelligence.services import agent_research, kb_rag, model_profile
from intelligence.services.turn_controller import decide_turn

_EVIDENCE_QUERIES = (
    "",
    "中天科技订单金额",
    "深挖光纤光缆原文证据",
    "快速概览储能",
    "市净率怎么计算",
)


def _legacy_evidence_budget(query: str, *, mode: str = kb_rag.DEFAULT_RAG_MODE, index_kind: str = "") -> tuple[int, int]:
    """引入档位前 evidence_budget_for_query 的原样复刻（等价基准）。"""
    q = str(query or "")
    high_precision_terms = (
        "订单", "合同", "中标", "收入", "营收", "兑现", "公告", "互动",
        "认证", "量产", "出货", "客户", "金额", "生效", "条件", "L3", "l3",
    )
    broad_terms = ("深挖", "原文", "全文", "详细", "为什么", "如何", "证据")
    quick_terms = ("快速", "速查", "概览", "简单")
    per_hit = kb_rag.DEFAULT_LLM_EVIDENCE_CHARS
    if any(t in q for t in high_precision_terms):
        per_hit = 1600
    elif any(t in q for t in broad_terms) or str(mode).lower() == "rerank" or index_kind == "full":
        per_hit = 1400
    elif any(t in q for t in quick_terms):
        per_hit = 800
    total = max(kb_rag.DEFAULT_LLM_EVIDENCE_TOTAL_CHARS, per_hit * 4)
    return per_hit, min(total, 8000)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(model_profile.ENV_MODEL_PROFILE, raising=False)
    monkeypatch.delenv(agent_research.ENV_MAX_STEPS, raising=False)


def _llm(route_id: str, confidence: float):
    content = json.dumps(
        {"route_id": route_id, "subject": None, "timeframe": None,
         "confidence": confidence, "reason": "测试"},
        ensure_ascii=False,
    )
    return lambda _messages: (content, object(), "")


# ---- 档位解析 ---------------------------------------------------------------


def test_unset_profile_is_standard() -> None:
    assert model_profile.active_profile_name() == "standard"


@pytest.mark.parametrize("raw", ["", "  ", "FRONTIER-X", "strong", "gpt"])
def test_unknown_profile_falls_back_to_standard(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv(model_profile.ENV_MODEL_PROFILE, raw)
    assert model_profile.active_profile_name() == "standard"


def test_profile_name_is_case_and_space_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(model_profile.ENV_MODEL_PROFILE, "  Frontier ")
    assert model_profile.active_profile_name() == "frontier"


def test_standard_profile_matches_legacy_constants() -> None:
    std = model_profile.PROFILES["standard"]
    assert std.agent_loop_max_steps == agent_research.DEFAULT_MAX_STEPS == 4
    assert std.evidence_char_scale == 1.0
    assert std.route_authority == model_profile.ROUTE_BINDING


def test_economy_currently_equals_standard_knobs() -> None:
    """economy 只是分流身份，数值待实验校准——防止有人悄悄改出差异。"""
    std = model_profile.PROFILES["standard"].to_dict()
    eco = model_profile.PROFILES["economy"].to_dict()
    for key in ("agent_loop_max_steps", "evidence_char_scale", "route_authority"):
        assert eco[key] == std[key]


# ---- 研究循环步数 -------------------------------------------------------------


def test_max_steps_default_unchanged() -> None:
    assert agent_research.max_steps() == agent_research.DEFAULT_MAX_STEPS


def test_max_steps_frontier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(model_profile.ENV_MODEL_PROFILE, "frontier")
    assert agent_research.max_steps() == 8


def test_explicit_env_steps_beat_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(model_profile.ENV_MODEL_PROFILE, "frontier")
    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "3")
    assert agent_research.max_steps() == 3
    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "999")
    assert agent_research.max_steps() == agent_research.MAX_CONFIGURED_STEPS


def test_invalid_env_steps_fall_back_to_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "abc")
    assert agent_research.max_steps() == 4
    monkeypatch.setenv(model_profile.ENV_MODEL_PROFILE, "frontier")
    assert agent_research.max_steps() == 8


# ---- 证据预算 -----------------------------------------------------------------


@pytest.mark.parametrize("query", _EVIDENCE_QUERIES)
@pytest.mark.parametrize("mode,index_kind", [(kb_rag.DEFAULT_RAG_MODE, ""), ("rerank", ""), (kb_rag.DEFAULT_RAG_MODE, "full")])
def test_standard_evidence_budget_identical_to_legacy(query: str, mode: str, index_kind: str) -> None:
    assert kb_rag.evidence_budget_for_query(query, mode=mode, index_kind=index_kind) == _legacy_evidence_budget(
        query, mode=mode, index_kind=index_kind
    )


@pytest.mark.parametrize("query", _EVIDENCE_QUERIES)
def test_frontier_evidence_budget_scaled(monkeypatch: pytest.MonkeyPatch, query: str) -> None:
    monkeypatch.setenv(model_profile.ENV_MODEL_PROFILE, "frontier")
    per_hit, total = kb_rag.evidence_budget_for_query(query)
    legacy_per_hit, legacy_total = _legacy_evidence_budget(query)
    assert per_hit == round(legacy_per_hit * 1.5)
    assert total == round(legacy_total * 1.5)
    assert total <= 12000


# ---- 路由权威：低置信度 -------------------------------------------------------


def test_standard_low_confidence_still_clarifies() -> None:
    decision = decide_turn("随便聊聊未来", llm_complete=_llm("chat", 0.42))
    assert decision.lane == "clarify"
    assert decision.needs_retrieval is False


def test_frontier_low_confidence_self_contained_goes_knowledge_with_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(model_profile.ENV_MODEL_PROFILE, "frontier")
    decision = decide_turn("随便聊聊未来", llm_complete=_llm("chat", 0.42))
    assert decision.lane == "knowledge"
    assert decision.needs_retrieval is True
    assert "advisory" in decision.reason


@pytest.mark.parametrize("query", ["那这个呢", "它还能涨吗", "那它呢"])
def test_frontier_still_clarifies_when_antecedent_is_outside_question(
    monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    monkeypatch.setenv(model_profile.ENV_MODEL_PROFILE, "frontier")
    decision = decide_turn(query, llm_complete=_llm("stock_deep_dive", 0.42))
    assert decision.lane == "clarify"
    assert decision.needs_retrieval is False


def test_economy_low_confidence_clarifies_like_standard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(model_profile.ENV_MODEL_PROFILE, "economy")
    decision = decide_turn("随便聊聊未来", llm_complete=_llm("chat", 0.42))
    assert decision.lane == "clarify"


@pytest.mark.parametrize(
    "query,route_id",
    [("随便聊聊未来", "chat"), ("请解释这个概念", "concept_definition")],
)
def test_high_confidence_decisions_identical_across_profiles(
    monkeypatch: pytest.MonkeyPatch, query: str, route_id: str
) -> None:
    baseline = decide_turn(query, llm_complete=_llm(route_id, 0.9)).to_dict()
    monkeypatch.setenv(model_profile.ENV_MODEL_PROFILE, "frontier")
    assert decide_turn(query, llm_complete=_llm(route_id, 0.9)).to_dict() == baseline

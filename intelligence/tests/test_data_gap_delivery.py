"""数据缺口须抵达公开答案，不能被通用拒答洗掉，也不能泄漏原始诊断。"""
from dataclasses import replace

import pytest

from intelligence.api import app as app_module
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_progress import project_episode_progress
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.provider_observability import ProviderTrace
from intelligence.tests.test_gap_answer_middle_tier import _verified


@pytest.mark.parametrize("evidence", [None, [], (), "private-path", {}])
def test_no_evidence_is_not_presented_as_data_obtained(evidence):
    payload = {"ok": True, "tool": "capital_data", "observation": "private-path"}
    if evidence is not None:
        payload["evidence"] = evidence
    progress = project_episode_progress(EpisodeEvent(1, "tool_result", payload))
    assert progress is not None
    assert "已取得" not in progress.message
    assert "未确认取得" in progress.message
    public = app_module._public_trace_step({
        "step_id": "continuous:episode:1:tool_result", "name": progress.stage,
        "status": progress.status, "output_summary": progress.message, "warnings": [],
    })
    assert public["output_summary"] == progress.message
    assert "private-path" not in public["output_summary"]


def test_capital_menu_label_survives_public_api_projection():
    progress = project_episode_progress(EpisodeEvent(1, "tool_menu", {"visible": ["capital_data", "l3_lookup"]}))
    assert progress is not None
    public = app_module._public_trace_step({
        "step_id": "continuous:episode:1:tool_menu", "name": progress.stage,
        "status": progress.status, "output_summary": progress.message, "warnings": [],
    })
    assert public["output_summary"] == progress.message


def test_evidence_rows_keep_the_positive_progress_label():
    progress = project_episode_progress(EpisodeEvent(1, "tool_result", {
        "ok": True, "tool": "capital_data", "evidence": [{"title": "private-title"}],
    }))
    assert progress is not None
    assert progress.message == "已取得两融/大宗/解禁数据。"


@pytest.mark.parametrize("reason,expected", [
    ("historical_date_unresolved", "请给出 YYYY-MM-DD"),
    ("historical_snapshot_unavailable", "缺少披露时点"),
])
def test_gap_answer_retains_safe_capital_refusal_reason(reason, expected):
    frame, verified = _verified(draft="private-draft should not escape")
    trace = ProviderTrace(
        provider="agent:capital_data", capability="capital_data", status="not_attempted",
        detail="private-path / secret-token", reason_code=reason,
    )
    # 复现真实 run：查到旧行业材料，但一条都没绑定到解禁问题。
    verified = replace(verified, outcome=replace(verified.outcome, traces=(trace,), bindings=()))
    answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
    assert expected in answer
    assert "未请求当前滚动" in answer
    assert "private-" not in answer and "secret-token" not in answer
    assert "2026-08-12" not in answer  # 无关材料日期不是本题已核验的截止日
    assert "可直接重试" not in answer  # 原样重试不会补齐历史边界


@pytest.mark.parametrize("status,expected", [
    ("request_error", "公告来源查询失败"),
    ("partial", "公告来源仅部分返回"),
    ("empty", "公告来源本次未返回"),
    ("not_attempted", "本次未执行公告"),
])
def test_l3_failure_empty_and_unattempted_survive_public_gap(status, expected):
    frame, verified = _verified(draft="private-draft")
    trace = ProviderTrace(provider="l3_lookup", capability="l3_lookup", status=status,
                          detail="private-source diagnostic")
    verified = replace(verified, outcome=replace(verified.outcome, traces=(trace,), bindings=()))
    answer = SemanticEpisodeVerifier._gap_answer(frame, verified)
    assert expected in answer
    assert "不能据此断言公司没有公告" in answer
    assert "private-" not in answer


def test_reason_code_roundtrips_and_old_traces_keep_their_shape():
    old = {"provider": "agent:capital_data", "capability": "capital_data", "status": "empty"}
    assert "reason_code" not in ProviderTrace.from_dict(old).to_dict()
    value = {**old, "status": "not_attempted", "reason_code": "historical_date_unresolved"}
    assert ProviderTrace.from_dict(value).to_dict()["reason_code"] == value["reason_code"]


def test_unknown_reason_is_not_public_prose():
    frame, verified = _verified()
    trace = ProviderTrace(provider="agent:capital_data", capability="capital_data",
                          status="not_attempted", reason_code="private-reason-text")
    verified = replace(verified, outcome=replace(verified.outcome, traces=(trace,)))
    assert "private-reason-text" not in SemanticEpisodeVerifier._gap_answer(frame, verified)

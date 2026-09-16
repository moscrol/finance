"""#55 · ASK_SEMANTIC_JUDGE=off：没有第二模型也能出稿，确定性门仍然承重。

三件事各自有阳性对照：
- 模式变了而夹具不变 → 同一份 structural 在 llm 模式下 judge_status=unavailable；
- 注入一个「拒绝所有句子」的判官 → off 模式下它一次都没被调用；
- 机械门（表外 E、日期错配）在 off 模式下照常删句并记账。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.eval import synthesis_health as sh
from intelligence.services import ask, ask_synthesis, llm_refine
from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.episode_semantic_verifier import (
    VERDICT_KEPT,
    VERDICT_REASON_EVIDENCE_DATE,
    VERDICT_REASON_OUTSIDE_SLOT,
    VERDICT_STAGE_CENSUS,
    SemanticEpisodeVerifier,
    _mismatched_evidence_date_indexes,
    _numbered_sentences,
)
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.judge_mode import (
    ENV_SEMANTIC_JUDGE,
    JUDGE_MODE_LLM,
    JUDGE_MODE_OFF,
    judge_mode_label,
    semantic_judge_mode,
)
from intelligence.services.research_contract import RequiredOutput, ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural
from intelligence.tests.test_synthesis_phase_observability import _fake_chain, _result

DRAFT = (
    "截至最新交易日，成交额缩量。我的基准判断是反弹仍有数日窗口，"
    "这是基于当前量价结构的主观估计。"
)


@pytest.fixture
def no_env_judge(monkeypatch: pytest.MonkeyPatch) -> None:
    """不让宿主环境里的 LLM_JUDGE_* 漏进测试：判官只能来自显式注入。"""

    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)


def _verify(verifier: SemanticEpisodeVerifier, pair):
    frame, structural = pair
    return verifier.verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )


# ---------------------------------------------------------------- 开关本身


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("off", JUDGE_MODE_OFF),
        ("0", JUDGE_MODE_OFF),
        ("false", JUDGE_MODE_OFF),
        (" NO ", JUDGE_MODE_OFF),
        ("deterministic", JUDGE_MODE_OFF),
        ("llm", JUDGE_MODE_LLM),
        ("on", JUDGE_MODE_LLM),
        ("", JUDGE_MODE_LLM),
        ("typo", JUDGE_MODE_LLM),
    ],
)
def test_mode_parsing_only_explicit_off_spellings_disable(monkeypatch, raw, expected):
    monkeypatch.setenv(ENV_SEMANTIC_JUDGE, raw)
    assert semantic_judge_mode() == expected


def test_unset_defaults_to_llm_and_labels_are_stable(monkeypatch):
    monkeypatch.delenv(ENV_SEMANTIC_JUDGE, raising=False)
    assert semantic_judge_mode() == JUDGE_MODE_LLM
    assert judge_mode_label(JUDGE_MODE_OFF) == "deterministic"
    assert judge_mode_label(JUDGE_MODE_LLM) == "llm"


# ---------------------------------------------------------------- 引擎 A


def test_off_mode_completes_without_a_judge_and_llm_mode_is_the_control(
    monkeypatch, no_env_judge
):
    monkeypatch.setenv(ENV_SEMANTIC_JUDGE, "off")
    result = _verify(SemanticEpisodeVerifier(), _structural(DRAFT))

    assert result.status == "completed"
    assert result.judge_status == "passed"
    assert result.judge_mode == "deterministic"
    assert result.correlated_judge is False
    assert "基准判断是反弹仍有数日窗口" in result.public_answer
    payload = result.to_dict()
    assert payload["judge_mode"] == "deterministic"
    assert payload["judge_unavailable_count"] == 0
    assert payload["pending_rejudge"] is False
    assert payload["v11_rejudge_called"] is False

    # 阳性对照：同一份夹具、同样没有判官，只把模式切回 llm → 掉进「判官不可用」。
    monkeypatch.setenv(ENV_SEMANTIC_JUDGE, "llm")
    control = _verify(SemanticEpisodeVerifier(), _structural(DRAFT))
    assert control.judge_status == "unavailable"
    assert control.judge_mode == "llm"
    assert "基准判断是反弹仍有数日窗口" not in control.public_answer
    assert control.to_dict()["pending_rejudge"] is True
    assert "judge_mode" in control.to_dict()


def test_off_mode_never_calls_an_injected_judge_even_across_a_repair_round(
    monkeypatch, no_env_judge
):
    monkeypatch.setenv(ENV_SEMANTIC_JUDGE, "off")
    judge = _judge(False, rejected=(1,), issues=("第1句不成立",))
    draft = (
        "截至最新交易日，成交额缩量，见 E1。另有一句引用了不存在的 E7。"
        "我的基准判断是反弹仍有数日窗口。"
    )
    result = _verify(SemanticEpisodeVerifier(judge_fn=judge), _structural(draft))

    assert judge.calls == []
    assert result.judge_mode == "deterministic"
    assert result.judge_status == "repaired"
    assert "不存在的" not in result.public_answer
    assert "成交额缩量" in result.public_answer
    reasons = {reason for verdict in result.sentence_verdicts for reason in verdict["reasons"]}
    assert "unresolved_evidence_ordinal" in reasons
    assert result.to_dict()["judge_unavailable_count"] == 0


def test_off_mode_skips_guided_retrieval_by_reason(monkeypatch, no_env_judge):
    monkeypatch.setenv(ENV_SEMANTIC_JUDGE, "off")
    verifier = SemanticEpisodeVerifier()
    frame, structural = _structural(DRAFT)
    verifier.verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
        retrieve_fn=lambda query, granted: (),
    )
    telemetry = verifier._guided_retrieve_and_rejudge(
        frame=frame,
        structural=structural,
        sentences=_numbered_sentences(DRAFT),
        first=None,  # type: ignore[arg-type]
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert telemetry.skip_reason == "judge_off"
    assert telemetry.triggered is False


# ---------------------------------------------------------------- 日期错配探测器


@pytest.mark.parametrize("mode", ["off", "llm"])
def test_evidence_date_mismatch_is_deleted_mechanically_in_both_modes(
    monkeypatch, no_env_judge, mode
):
    monkeypatch.setenv(ENV_SEMANTIC_JUDGE, mode)
    draft = "E1 显示该公告发布于 2026-08-21。我的基准判断是反弹仍有数日窗口。"
    verifier = (
        SemanticEpisodeVerifier(judge_fn=_judge(True))
        if mode == "llm"
        else SemanticEpisodeVerifier()
    )
    result = _verify(verifier, _structural(draft))

    assert result.judge_status == "repaired"
    assert "2026-08-21" not in result.public_answer
    assert "基准判断" in result.public_answer
    verdict = next(
        item
        for item in result.sentence_verdicts
        if VERDICT_REASON_EVIDENCE_DATE in item["reasons"]
    )
    assert verdict["stage"] == "preflight"
    assert verdict["decision"] == "deleted"
    assert any("evidence_date_mismatch" in issue for issue in result.issues)


def test_evidence_date_detector_negatives_are_left_alone():
    _frame, structural = _structural("占位。")

    def indexes(text: str, verified=structural) -> tuple[int, ...]:
        return _mismatched_evidence_date_indexes(_numbered_sentences(text), verified)

    # 夹具证据 source_date=2026-07-22。
    assert indexes("E1 显示该公告发布于 2026-08-21。") == (1,)  # 同一探测器的阳性
    assert indexes("E1 显示该数据截至 2026-07-22。") == ()  # 日期吻合
    assert indexes("E1 与 E9 都提到 2026-08-21。") == ()  # 双引：不判
    assert indexes("E1 显示成交额缩量。") == ()  # 句内无日期
    assert indexes("公告发布于 2026-08-21。") == ()  # 未引证据
    assert indexes("E9 显示该公告发布于 2026-08-21。") == ()  # 表外 E：归表外门
    undated_evidence = replace(structural.outcome.evidence[0], source_date="")
    undated = verify_episode_outcome(
        structural.contract,
        replace(structural.outcome, evidence=(undated_evidence,)),
    )
    assert indexes("E1 显示该公告发布于 2026-08-21。", undated) == ()  # 证据无日期：不判


# ---------------------------------------------------------------- 槽级引用 census


def test_outside_slot_citation_is_counted_not_deleted(monkeypatch, no_env_judge):
    monkeypatch.setenv(ENV_SEMANTIC_JUDGE, "off")
    outputs = (
        RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        RequiredOutput("counterpoint", "反证", ("market_data",), True),
    )
    draft = "直接判断：量能修复中段，见 E1。\n风险：外部扰动仍在，见 E1。"
    frame, structural = _structural(draft, required_outputs=outputs)
    first = structural.outcome.evidence[0]
    second = replace(
        first,
        content_hash="HASH_COUNTER_SENTINEL",
        title="反证快照",
        detail="外部扰动观察",
    )
    outcome = replace(
        structural.outcome,
        evidence=(first, second),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (first.content_hash,)),
            OutputEvidenceBinding("counterpoint", (second.content_hash,)),
        ),
    )
    structural = verify_episode_outcome(structural.contract, outcome)
    assert structural.verified_status == "completed", structural.issues

    result = SemanticEpisodeVerifier().verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )

    assert result.judge_status == "passed"
    assert result.cited_outside_slot_count == 1
    assert result.to_dict()["cited_outside_slot_count"] == 1
    census = [item for item in result.sentence_verdicts if item["stage"] == VERDICT_STAGE_CENSUS]
    assert [item["sentence_index"] for item in census] == [2]
    assert census[0]["decision"] == VERDICT_KEPT
    assert census[0]["reasons"] == [VERDICT_REASON_OUTSIDE_SLOT]
    assert "外部扰动仍在" in result.public_answer  # 只记账，不删句


# ---------------------------------------------------------------- 引擎 B


def _shadow(monkeypatch):
    result = _result()
    chain = _fake_chain(result.answer_spec)
    calls = {"n": 0}

    def counted(messages, **kwargs):
        calls["n"] += 1
        return chain(messages, **kwargs)

    monkeypatch.setattr(llm_refine, "synthesize_messages", counted)
    options = ask.AskOptions(query=result.query, shadow_grounded_composer=True)
    ask_synthesis.synthesize_shadow_grounded_answer(
        ask.PreparedAnswer(options=options, result=result),
        repair_drop_invalid=True,
    )
    return result, options, calls


def test_engine_b_skips_the_judge_and_marks_deterministic_only(monkeypatch):
    monkeypatch.setenv(ENV_SEMANTIC_JUDGE, "off")
    result, options, calls = _shadow(monkeypatch)

    judge_phase = next(phase for phase in result.synthesis_phases if phase.name == "judge")
    assert judge_phase.status == "skipped"
    assert judge_phase.reason_code == "judge_off"
    # 关掉不是掉线：这个码绝不能进瞬时故障白名单，否则会从「掉线放行」侧门溜回来。
    assert "judge_off" not in ask_synthesis._TRANSIENT_JUDGE_REASONS
    assert llm_refine.stable_llm_fallback_reason("judge_off") == "judge_off"
    shadow = result.grounded_composer_shadow
    assert shadow is not None
    assert shadow.status == "deterministic_only"
    assert shadow.judge_report is None
    assert shadow.judge_provider is None
    assert shadow.presented_answer
    assert not shadow.presented_answer.startswith(ask_synthesis._JUDGE_OUTAGE_NOTICE)

    monkeypatch.delenv(ENV_SEMANTIC_JUDGE, raising=False)
    control_result, _options, control_calls = _shadow(monkeypatch)
    assert control_result.grounded_composer_shadow.status == "accepted"
    assert control_calls["n"] == calls["n"] + 1  # 差的那一发就是判官


def test_engine_b_promotion_and_health_bucket_in_off_mode(monkeypatch):
    monkeypatch.setenv(ENV_SEMANTIC_JUDGE, "off")
    result = _result()
    monkeypatch.setattr(llm_refine, "synthesize_messages", _fake_chain(result.answer_spec))
    options = ask.AskOptions(query=result.query, grounded_presenter=True)

    assert ask.promote_grounded_answer(options, result) is True
    diagnostic = result.synthesis_diagnostic
    assert diagnostic is not None
    assert diagnostic.state == "accepted"
    assert diagnostic.reason_code == "deterministic_only"
    assert diagnostic.shadow_status == "deterministic_only"
    assert result.synthesis
    assert ask_synthesis._JUDGE_OUTAGE_NOTICE not in result.synthesis

    health = sh.classify_turn(
        "c1",
        {
            "synthesis_diagnostic": {
                "state": "accepted",
                "reason_code": "deterministic_only",
                "shadow_status": "deterministic_only",
            },
            "answer": result.synthesis,
            "elapsed_s": 1.0,
        },
    )
    assert health.state == sh.DETERMINISTIC_ONLY
    assert sh.DETERMINISTIC_ONLY in sh._ORDER and sh.DETERMINISTIC_ONLY in sh._LABELS

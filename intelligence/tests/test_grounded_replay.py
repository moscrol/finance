from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.eval import grounded_replay as replay
from intelligence.services import answer_model, llm_refine


def _answer_spec() -> answer_model.AnswerSpec:
    claim = answer_model.Claim(
        claim_id="daily-review:fact:1",
        text="市场成交额较前一日下降。",
        claim_type="skill_fact",
        theme="每日市场复盘",
        evidence_ids=("K1",),
        evidence_tier="canonical",
        status=answer_model.ClaimStatus.VERIFIED,
    )
    gap = answer_model.Claim(
        claim_id="daily-review:gap:1",
        text="缺少盘后公告核验。",
        claim_type="gap",
        theme="每日市场复盘",
        status=answer_model.ClaimStatus.MISSING,
    )
    return answer_model.AnswerSpec(
        research_spec=answer_model.ThemeResearchSpec(
            theme="每日市场复盘",
            pack_id="generic_theme",
            definition="复盘市场结构。",
            chain_stages=("市场", "板块", "个股"),
            company_scope="不涉及公司映射。",
            as_of="2026-07-23",
            evidence_requirements=("结构化行情",),
            counter_evidence_requirements=("反向量价",),
            trigger_conditions=("放量",),
            verification_actions=("次日核验",),
            focus_entities=(),
            requested_sections=("direct_answer",),
        ),
        summary=(claim,),
        verified_facts=(claim,),
        company_table=(),
        counter_evidence=(),
        gaps=(gap,),
        triggers=(),
        next_actions=("次日检查成交额",),
        sources=(
            answer_model.EvidenceRef(
                evidence_id="K1",
                source="daily-review",
                detail="2026-07-23",
                tier="canonical",
                source_date="2026-07-23",
                freshness="current",
                content_hash="abc",
                source_revision="rev-1",
            ),
        ),
        system_notices=(),
        prompt_constraints=("直接回答市场阶段",),
        presentation_kind="base_finance",
        presentation_title="每日市场复盘",
        presentation_profile="theme",
        quality=answer_model.AnswerQualityReport(
            issues=(
                answer_model.QualityIssue(
                    code="warning-only",
                    severity="warning",
                    message="仅用于 round trip",
                ),
            )
        ),
    )


def _decision_brief() -> answer_model.DecisionBrief:
    return answer_model.DecisionBrief(
        direct_answer="市场缩量。",
        core_tension="缩量与结构强势并存。",
        supports=("daily-review:fact:1",),
        unknowns=("daily-review:gap:1",),
    )


def _write_frozen_run(tmp_path: Path) -> tuple[Path, replay.FrozenRun]:
    run_dir = tmp_path / "run_20260803_test"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "run_20260803_test",
                "question": "2026-07-23 今天市场怎么样",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "answer_spec.json").write_text(
        json.dumps(_answer_spec().to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "decision_brief.json").write_text(
        json.dumps(_decision_brief().to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    return run_dir, replay.load_frozen_run(run_dir)


def test_answer_spec_payload_round_trips() -> None:
    payload = _answer_spec().to_dict()

    restored = replay.answer_spec_from_payload(payload)

    assert restored.to_dict() == payload


def test_load_frozen_run_binds_required_input_hashes(tmp_path: Path) -> None:
    run_dir, frozen = _write_frozen_run(tmp_path)

    assert frozen.run_id == "run_20260803_test"
    assert frozen.question == "2026-07-23 今天市场怎么样"
    assert frozen.decision_brief == _decision_brief()
    assert set(frozen.input_sha256) == {
        "run.json",
        "answer_spec.json",
        "decision_brief.json",
    }
    assert all(len(value) == 64 for value in frozen.input_sha256.values())
    assert run_dir.is_dir()


def test_load_frozen_run_rejects_empty_question(tmp_path: Path) -> None:
    run_dir, _frozen = _write_frozen_run(tmp_path)
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": "x", "question": ""}),
        encoding="utf-8",
    )

    with pytest.raises(replay.ReplayInputError, match="question"):
        replay.load_frozen_run(run_dir)


def test_composer_replay_uses_production_builders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run_dir, frozen = _write_frozen_run(tmp_path)
    captured: dict[str, object] = {}

    def fake_synthesize(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return (
            llm_refine.SynthesisResult(
                answer="合成正文",
                provider="openai",
                model="gpt-test",
                finish_reason="stop",
            ),
            "",
        )

    monkeypatch.setattr(llm_refine, "synthesize_messages", fake_synthesize)

    artifact = replay.run_composer_replay(frozen, grant_seconds=115)

    registry = answer_model.grounded_claim_registry_block(
        frozen.answer_spec,
        query=frozen.question,
        max_chars=12_000,
    )
    assert captured["messages"] == llm_refine.build_grounded_composer_messages(
        frozen.question,
        frozen.decision_brief.to_prompt_block(),
        registry,
        required_outputs=frozen.answer_spec.prompt_constraints,
    )
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["timeout"] == 115
    assert isinstance(kwargs["deadline"], llm_refine.Deadline)
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 2400
    assert kwargs["max_chars"] == 16000
    assert artifact.status == "completed"
    assert artifact.output_text == "合成正文"
    assert artifact.finish_reason == "stop"
    assert artifact.completion_tokens is None
    assert artifact.input_sha256 == frozen.input_sha256
    assert artifact.prediction["range_seconds"] == [110, 180]


def test_composer_timeout_is_a_lower_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run_dir, frozen = _write_frozen_run(tmp_path)
    monkeypatch.setattr(
        llm_refine,
        "synthesize_messages",
        lambda *_args, **_kwargs: (
            None,
            "LLM 合成超过共享截止时间，已降级为模板",
        ),
    )

    artifact = replay.run_composer_replay(frozen, grant_seconds=115)

    assert artifact.status == "timeout"
    assert artifact.elapsed_is_lower_bound
    assert artifact.output_text is None
    assert artifact.prediction["verdict"] == "greater_than_or_equal_to_grant"


def test_judge_replay_prepares_candidate_and_parses_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run_dir, frozen = _write_frozen_run(tmp_path)
    atom = answer_model.evidence_atoms_from_answer_spec(frozen.answer_spec)[0]
    candidate = (
        "市场成交额较前一日下降。 "
        "<!-- claim_ids=daily-review:fact:1; "
        f"evidence_atom_ids={atom.atom_id}; claim_type=fact -->"
    )
    composer = replay.ReplayArtifact(
        phase="composer",
        status="completed",
        run_id=frozen.run_id,
        revision="rev",
        grant_seconds=115,
        elapsed_ms=10,
        elapsed_is_lower_bound=False,
        input_sha256=frozen.input_sha256,
        prompt_sha256="prompt",
        completion_tokens=None,
        finish_reason="stop",
        provider="openai",
        model="gpt-test",
        failure_reason=None,
        output_text=candidate,
        parsed_output=None,
        deterministic_issues=(),
        prediction={},
    )
    captured: dict[str, object] = {}

    def fake_synthesize(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return (
            llm_refine.SynthesisResult(
                answer=json.dumps(
                    {
                        "passed": True,
                        "rejected_sentence_indexes": [],
                        "issues": [],
                    }
                ),
                provider="judge",
                model="judge-test",
                finish_reason="stop",
            ),
            "",
        )

    monkeypatch.setattr(llm_refine, "synthesize_messages", fake_synthesize)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)

    artifact = replay.run_judge_replay(
        frozen,
        composer_artifact=composer,
        grant_seconds=115,
    )

    registry = answer_model.grounded_claim_registry_block(
        frozen.answer_spec,
        query=frozen.question,
        max_chars=12_000,
    )
    assert captured["messages"] == llm_refine.build_grounding_judge_messages(
        frozen.question,
        candidate,
        registry,
    )
    assert artifact.status == "completed"
    assert artifact.parsed_output == {
        "passed": True,
        "rejected_sentence_indexes": [],
        "issues": [],
    }
    assert artifact.provider == "judge"


def test_judge_does_not_call_provider_when_composer_did_not_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run_dir, frozen = _write_frozen_run(tmp_path)
    composer = replay.ReplayArtifact(
        phase="composer",
        status="timeout",
        run_id=frozen.run_id,
        revision="rev",
        grant_seconds=115,
        elapsed_ms=115000,
        elapsed_is_lower_bound=True,
        input_sha256=frozen.input_sha256,
        prompt_sha256="prompt",
        completion_tokens=None,
        finish_reason=None,
        provider=None,
        model=None,
        failure_reason="deadline",
        output_text=None,
        parsed_output=None,
        deterministic_issues=(),
        prediction={},
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(llm_refine, "synthesize_messages", fail_if_called)

    artifact = replay.run_judge_replay(
        frozen,
        composer_artifact=composer,
        grant_seconds=115,
    )

    assert artifact.status == "blocked_by_composer"
    assert artifact.elapsed_ms == 0


def test_artifact_json_round_trip() -> None:
    artifact = replay.ReplayArtifact(
        phase="composer",
        status="completed",
        run_id="run",
        revision="rev",
        grant_seconds=115,
        elapsed_ms=1,
        elapsed_is_lower_bound=False,
        input_sha256={"answer_spec.json": "a" * 64},
        prompt_sha256="b" * 64,
        completion_tokens=None,
        finish_reason="stop",
        provider="openai",
        model="gpt-test",
        failure_reason=None,
        output_text="正文",
        parsed_output=None,
        deterministic_issues=(),
        prediction={},
    )

    assert replay.ReplayArtifact.from_dict(artifact.to_dict()) == artifact

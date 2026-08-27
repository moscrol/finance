from __future__ import annotations

import json
from types import SimpleNamespace

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.research_tool_registry import ResearchToolRegistry
from scripts import run_agent_episode_ab as episode_ab


def _write_questions(tmp_path, questions: list[tuple[str, str]]):
    path = tmp_path / "questions.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {"id": case_id, "question": question}
                    for case_id, question in questions
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_bare_arm_uses_the_same_disabled_thinking_profile_as_episode(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_chat_with_tools(**kwargs):
        captured.update(kwargs)
        return {"content": "裸模型判断", "tool_calls": []}, "glm", ""

    monkeypatch.setattr(
        episode_ab.llm_refine,
        "chat_with_tools",
        fake_chat_with_tools,
    )
    monkeypatch.setattr(
        episode_ab.llm_refine,
        "complete",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("bare arm must use the same chat profile as episode")
        ),
    )
    case = episode_ab.ABQuestion(
        case_id="bare-profile",
        question="目前市场怎么看",
        model="glm-5.2",
        timeout=30.0,
        as_of="2026-07-22",
    )

    result = episode_ab._run_bare_arm(case)

    assert result["answer"] == "裸模型判断"
    assert captured["tools"] == []
    assert captured["disable_thinking"] is True
    assert captured["tool_choice"] == "none"


def test_dry_run_builds_contracts_without_model_or_tool_execution(
    tmp_path,
    monkeypatch,
) -> None:
    questions = _write_questions(
        tmp_path,
        [("rebound", "昨天的反弹能持续多久")],
    )
    output = tmp_path / "dry.json"

    monkeypatch.setattr(
        episode_ab,
        "_build_runtime",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not build runtime")
        ),
    )
    monkeypatch.setattr(
        episode_ab,
        "_build_registry",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not build registry")
        ),
    )

    code = episode_ab.main(
        [
            "--dry-run",
            "--questions-file",
            str(questions),
            "--output",
            str(output),
        ]
    )

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["runtime_switched"] is False
    assert payload["mode"] == "dry_run"
    assert payload["cases"][0]["task_frame_hash"]
    assert payload["cases"][0]["contract"]["required_outputs"]
    assert payload["cases"][0]["execution_status"] == "planned"
    assert "bare" not in payload["cases"][0]


def test_current_results_must_cover_every_question(tmp_path) -> None:
    questions = _write_questions(
        tmp_path,
        [
            ("rebound", "昨天的反弹能持续多久"),
            ("mainline", "目前市场的主线是什么"),
        ],
    )
    current = tmp_path / "current.json"
    current.write_text(
        json.dumps({"rebound": "旧工作台答案"}, ensure_ascii=False),
        encoding="utf-8",
    )
    output = tmp_path / "result.json"

    code = episode_ab.main(
        [
            "--dry-run",
            "--questions-file",
            str(questions),
            "--current-results",
            str(current),
            "--output",
            str(output),
        ]
    )

    assert code == 2
    assert not output.exists()


def test_current_results_preserve_available_runtime_metrics(tmp_path) -> None:
    questions = _write_questions(
        tmp_path,
        [("rebound", "昨天的反弹能持续多久")],
    )
    current = tmp_path / "current.json"
    current.write_text(
        json.dumps(
            {
                "runtime_commit": "legacy-commit",
                "cases": [
                    {
                        "case_id": "rebound",
                        "answer": "旧工作台答案",
                        "latency": 67.5,
                        "llm_calls": 3,
                        "tool_calls": 5,
                        "terminal_outcome": "verified_fallback",
                        "failure_stage": "synthesis_timeout",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "dry.json"

    code = episode_ab.main(
        [
            "--dry-run",
            "--questions-file",
            str(questions),
            "--current-results",
            str(current),
            "--output",
            str(output),
        ]
    )

    assert code == 0
    saved = json.loads(output.read_text(encoding="utf-8"))["cases"][0]["current"]
    assert saved["answer"] == "旧工作台答案"
    assert saved["latency"] == 67.5
    assert saved["llm_calls"] == 3
    assert saved["tool_calls"] == 5
    assert saved["terminal_outcome"] == "verified_fallback"
    assert saved["failure_stage"] == "synthesis_timeout"


def test_live_runner_records_bare_current_and_verified_episode(
    tmp_path,
    monkeypatch,
) -> None:
    questions = _write_questions(
        tmp_path,
        [("rebound", "昨天的反弹能持续多久")],
    )
    current = tmp_path / "current.json"
    current.write_text(
        json.dumps({"rebound": "旧工作台答案"}, ensure_ascii=False),
        encoding="utf-8",
    )
    output = tmp_path / "live.json"
    execution_order: list[str] = []
    synthesis_reserves: list[float] = []
    real_build_context = episode_ab.build_episode_context

    class FakeRuntime:
        def run(self, *, task_frame, context, registry):
            execution_order.append("episode")
            synthesis_reserves.append(context.policy.synthesis_reserve)
            del registry
            evidence = AgentEvidence(
                tool="market_data",
                title="市场窗口",
                detail="最近交易日市场结构",
                source="test-market",
                content_hash="market-1",
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status="completed",
                draft="反弹先按短周期修复看，持续性取决于量能和上涨家数。",
                evidence=(evidence,),
                traces=(),
                gaps=(),
                stop_reason="model_finish",
                events=(
                    EpisodeEvent(
                        1,
                        "task",
                        {"task_frame_hash": task_frame.task_frame_hash},
                    ),
                    EpisodeEvent(
                        2,
                        "model_turn",
                        {"task_frame_hash": task_frame.task_frame_hash},
                    ),
                ),
                bindings=tuple(
                    # basis 跟着契约声明走（真实协议也要求一致）：前瞻条件槽
                    # 现在签 model_reasoning，硬绑 evidence 会 basis mismatch。
                    OutputEvidenceBinding(
                        item.output_id,
                        ("market-1",)
                        if item.grounding_mode == "evidence"
                        else (),
                        basis=item.grounding_mode,
                    )
                    for item in context.contract.required_outputs
                ),
                usage=AgentUsage(llm_calls=2, tool_calls=1),
            )

    class FakeSemanticVerifier:
        # Simulate an independent LLM_JUDGE provider: it records a physical
        # llm_refine attempt but bypasses the primary-client counter.
        provider_attempts = 0

        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            ledger = episode_ab.llm_refine.current_call_ledger()
            assert ledger is not None
            ledger.record(
                episode_ab.llm_refine.LLMCallRecord(
                    caller="synthesis",
                    provider="independent-judge",
                    model="judge-model",
                    status="success",
                    elapsed_ms=1,
                )
            )
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    def fake_bare(*_args, **_kwargs):
        execution_order.append("bare")
        return {
            "answer": "裸模型答案",
            "provider": "fake",
            "reason": "",
            "latency": 0.01,
            "llm_calls": 1,
            "tool_calls": 0,
        }

    def build_fresh_context(*args, **kwargs):
        execution_order.append("context")
        return real_build_context(*args, **kwargs)

    monkeypatch.setattr(episode_ab, "_run_bare_arm", fake_bare)
    monkeypatch.setattr(
        episode_ab,
        "build_episode_context",
        build_fresh_context,
    )
    monkeypatch.setattr(
        episode_ab,
        "_build_runtime",
        lambda *_args, **_kwargs: FakeRuntime(),
    )
    monkeypatch.setattr(
        episode_ab,
        "_build_registry",
        lambda *_args, **_kwargs: ResearchToolRegistry(()),
    )
    monkeypatch.setattr(
        episode_ab,
        "_build_semantic_verifier",
        lambda *_args, **_kwargs: FakeSemanticVerifier(),
    )
    monkeypatch.setattr(
        episode_ab,
        "_runtime_identity",
        lambda: ("canary", "candidate-sha"),
    )
    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "canary")
    monkeypatch.setenv("CONTINUOUS_RUNTIME_CANARY_ID", "candidate-sha")

    code = episode_ab.main(
        [
            "--questions-file",
            str(questions),
            "--current-results",
            str(current),
            "--output",
            str(output),
        ]
    )

    assert code == 0
    case = json.loads(output.read_text(encoding="utf-8"))["cases"][0]
    assert case["bare"]["answer"] == "裸模型答案"
    assert case["current"]["answer"] == "旧工作台答案"
    assert case["episode"]["verified_status"] == "completed"
    assert case["episode"]["answer"].startswith("反弹先按短周期")
    assert case["episode"]["evidence_hashes"] == ["market-1"]
    assert case["episode"]["llm_calls"] == 2
    assert case["episode"]["tool_calls"] == 1
    assert case["episode"]["structural_status"] == "completed"
    assert case["episode"]["semantic_status"] == "passed"
    assert case["episode"]["provider_attempts"] == 3
    assert case["episode"]["duplicate_queries"] == 0
    assert case["episode"]["runtime_mode"] == "canary"
    assert case["episode"]["runtime_revision"] == "candidate-sha"
    assert 0.0 < case["episode"]["task_alignment_score"] <= 1.0
    assert case["episode"]["outcome"]["usage"] == {
        "llm_calls": 2,
        "tool_calls": 1,
        "invalid_actions": 0,
    }
    assert len(case["episode"]["outcome"]["events"]) == 2
    assert execution_order == ["bare", "context", "episode"]
    assert synthesis_reserves == [60.0]


def test_deterministic_fast_path_is_not_sent_to_episode(
    tmp_path,
    monkeypatch,
) -> None:
    questions = _write_questions(
        tmp_path,
        [("index-space", "科创50你认为反弹空间有多少")],
    )
    output = tmp_path / "fast-path.json"

    monkeypatch.setattr(
        episode_ab,
        "_run_bare_arm",
        lambda *_args, **_kwargs: {
            "answer": "裸模型答案",
            "provider": "fake",
            "reason": "",
            "latency": 0.01,
            "llm_calls": 1,
            "tool_calls": 0,
        },
    )
    monkeypatch.setattr(
        episode_ab,
        "_build_runtime",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("fast path must not enter episode")
        ),
    )
    monkeypatch.setattr(
        episode_ab,
        "_run_fast_path",
        lambda *_args, **_kwargs: {
            "execution_kind": "deterministic_fast_path",
            "status": "completed",
            "answer": "科创50压力区决定反弹空间。",
            "latency": 0.02,
            "llm_calls": 0,
            "tool_calls": 1,
        },
    )
    monkeypatch.setattr(
        episode_ab,
        "_runtime_identity",
        lambda: ("canary", "candidate-sha"),
    )

    assert (
        episode_ab.main(
            [
                "--questions-file",
                str(questions),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    case = json.loads(output.read_text(encoding="utf-8"))["cases"][0]
    assert case["episode"]["execution_kind"] == "deterministic_fast_path"
    assert case["episode"]["llm_calls"] == 0
    assert case["episode"]["structural_status"] == "completed"
    assert case["episode"]["semantic_status"] == "passed"
    assert case["episode"]["semantic_verification_mode"] == "deterministic_contract"
    assert case["episode"]["provider_attempts"] == 0
    assert case["episode"]["tool_calls"] == 1
    assert case["episode"]["duplicate_queries"] == 0
    assert case["episode"]["runtime_mode"] == "canary"
    assert case["episode"]["runtime_revision"] == "candidate-sha"
    assert case["episode"]["task_alignment_score"] == 1.0


def test_fast_path_uses_remaining_root_timeout_and_total_latency(
    tmp_path,
    monkeypatch,
) -> None:
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "index-space",
                        "question": "科创50你认为反弹空间有多少",
                        "timeout": 0.1,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "fast-path-budget.json"
    received_timeouts: list[float] = []

    monkeypatch.setattr(
        episode_ab,
        "_run_bare_arm",
        lambda *_args, **_kwargs: {
            "answer": "裸模型答案",
            "provider": "fake",
            "reason": "",
            "latency": 0.0,
            "llm_calls": 1,
            "tool_calls": 0,
        },
    )

    def capture_fast_path(_frame, timeout):
        received_timeouts.append(timeout)
        return {
            "execution_kind": "deterministic_fast_path",
            "status": "completed",
            "answer": "科创50压力区决定反弹空间。",
            "llm_calls": 0,
            "tool_calls": 1,
        }

    monkeypatch.setattr(episode_ab, "_run_fast_path", capture_fast_path)
    monkeypatch.setattr(
        episode_ab,
        "_runtime_identity",
        lambda: ("canary", "candidate-sha"),
    )

    assert (
        episode_ab.main(
            [
                "--questions-file",
                str(questions),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    episode = json.loads(output.read_text(encoding="utf-8"))["cases"][0]["episode"]
    assert 0.0 < received_timeouts[0] <= 0.1
    assert episode["latency"] >= 0.0


def test_exhausted_root_deadline_does_not_enter_fast_path(
    tmp_path,
    monkeypatch,
) -> None:
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "index-space",
                        "question": "科创50你认为反弹空间有多少",
                        "timeout": 0.0001,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "fast-path-exhausted.json"
    monkeypatch.setattr(
        episode_ab,
        "_run_bare_arm",
        lambda *_args, **_kwargs: {
            "answer": "裸模型答案",
            "provider": "fake",
            "reason": "",
            "latency": 0.0,
            "llm_calls": 1,
            "tool_calls": 0,
        },
    )
    monkeypatch.setattr(
        episode_ab,
        "_run_fast_path",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("expired root deadline must not execute fast path")
        ),
    )
    monkeypatch.setattr(
        episode_ab,
        "_runtime_identity",
        lambda: ("canary", "candidate-sha"),
    )

    assert (
        episode_ab.main(
            [
                "--questions-file",
                str(questions),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    episode = json.loads(output.read_text(encoding="utf-8"))["cases"][0]["episode"]
    assert episode["status"] == "failed"
    assert episode["provider_attempts"] == 0
    assert episode["tool_calls"] == 0


def test_runtime_identity_uses_git_revision_and_marks_dirty(
    monkeypatch,
) -> None:
    revision = "a" * 40
    results = iter(
        [
            SimpleNamespace(stdout=f"{revision}\n"),
            SimpleNamespace(stdout=" M scripts/run_agent_episode_ab.py\n"),
        ]
    )
    monkeypatch.setenv("ASK_CONTINUOUS_RUNTIME", "canary")
    monkeypatch.setenv("CONTINUOUS_RUNTIME_CANARY_ID", "untrusted-label")
    monkeypatch.setattr(
        episode_ab.subprocess,
        "run",
        lambda *_args, **_kwargs: next(results),
    )

    assert episode_ab._runtime_identity() == ("canary", f"{revision}-dirty")

from __future__ import annotations

import json
from pathlib import Path

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.research_tool_registry import ResearchToolRegistry
from scripts import run_agent_runtime_benchmark as benchmark


FIXTURE = (
    Path(__file__).parent / "fixtures" / "runtime_backend_cases.json"
)


def test_dry_run_freezes_one_task_frame_per_case_and_all_backends(
    tmp_path,
    monkeypatch,
) -> None:
    output = tmp_path / "plan.json"
    monkeypatch.setattr(
        benchmark,
        "_run_runtime_arm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not execute a runtime")
        ),
    )

    code = benchmark.main(
        [
            "--dry-run",
            "--backend",
            "continuous_glm",
            "--backend",
            "sdk_glm",
            "--backend",
            "codex_headless",
            "--questions-file",
            str(FIXTURE),
            "--output",
            str(output),
        ]
    )

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["expected_backends"] == [
        "continuous_glm",
        "sdk_glm",
        "codex_headless",
    ]
    assert len(payload["cases"]) == 9
    assert all(case["task_frame_hash"] for case in payload["cases"])
    assert len({case["id"] for case in payload["cases"]}) == 9
    assert all(case["execution_status"] == "planned" for case in payload["cases"])
    by_id = {case["id"]: case for case in payload["cases"]}
    assert by_id["rebound-duration"]["acceptance_contract_gaps"] == []
    assert all(not case["acceptance_contract_gaps"] for case in payload["cases"])
    assert by_id["contextual-follow-up"]["control"]["terminal_kind"] == "research"
    assert by_id["contextual-follow-up"]["task_frame"]["required_outputs"] == [
        "invalidation_conditions",
        "supporting_evidence",
    ]


def test_questions_fixture_preserves_long_tail_acceptance_outputs() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in payload["cases"]}

    assert by_id["theme-comparison"]["required_outputs"] == [
        "comparison_conclusion",
        "supporting_evidence",
        "counterpoint",
        "invalidation_conditions",
    ]
    assert by_id["contextual-follow-up"]["conversation_context"][0][
        "content"
    ] == "昨天的反弹能持续多久"


def test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state(
    tmp_path,
    monkeypatch,
) -> None:
    questions = tmp_path / "one-case.json"
    questions.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "current-mainline",
                        "question": "目前市场的主线是什么",
                        "as_of": "2026-07-24",
                        "tier": "standard",
                        "timeout": 30.0,
                        "required_outputs": ["direct_assessment"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "live.json"
    context_ids: list[int] = []

    class FakeRuntime:
        def __init__(self, backend: str) -> None:
            self.backend = backend

        def run(self, *, task_frame, context, registry):
            del registry
            context_ids.append(id(context))
            evidence: list[AgentEvidence] = []
            bindings: list[OutputEvidenceBinding] = []
            for index, required in enumerate(context.contract.required_outputs):
                tool = required.evidence_types[0]
                content_hash = f"{self.backend}-{index}"
                evidence.append(
                    AgentEvidence(
                        tool=tool,
                        title=f"{self.backend} evidence",
                        detail="当前主线证据",
                        source="test",
                        content_hash=content_hash,
                        source_date="2026-07-24",
                    )
                )
                bindings.append(
                    OutputEvidenceBinding(required.output_id, (content_hash,))
                )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status="completed",
                draft=f"{self.backend}：医药是当前主线。",
                evidence=tuple(evidence),
                traces=(),
                gaps=(),
                stop_reason="model_finish",
                events=(
                    EpisodeEvent(
                        1,
                        "task",
                        {"task_frame_hash": task_frame.task_frame_hash},
                    ),
                ),
                bindings=tuple(bindings),
                usage=AgentUsage(llm_calls=2, tool_calls=1),
            )

    class FakeSemanticVerifier:
        provider_attempts = 1

        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    monkeypatch.setattr(
        benchmark,
        "_build_runtime",
        lambda backend, *_args, **_kwargs: (FakeRuntime(backend), "fake-model"),
    )
    monkeypatch.setattr(
        benchmark,
        "_build_registry",
        lambda *_args, **_kwargs: ResearchToolRegistry(()),
    )
    monkeypatch.setattr(
        benchmark,
        "_build_semantic_verifier",
        lambda *_args, **_kwargs: FakeSemanticVerifier(),
    )

    code = benchmark.main(
        [
            "--backend",
            "continuous_glm",
            "--backend",
            "sdk_glm",
            "--questions-file",
            str(questions),
            "--output",
            str(output),
        ]
    )

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    arms = payload["cases"][0]["arms"]
    assert [arm["backend"] for arm in arms] == ["continuous_glm", "sdk_glm"]
    assert [arm["answer"].split("：", 1)[0] for arm in arms] == [
        "continuous_glm",
        "sdk_glm",
    ]
    assert len(context_ids) == 2
    assert context_ids[0] != context_ids[1]
    assert payload["summary"]["arm_count"] == 2
    assert arms[0]["citations"] == [
        {
            "title": "continuous_glm evidence",
            "source": "test",
            "date": "2026-07-24",
        }
    ]
    assert arms[0]["data_cutoff"] == "2026-07-24"


def test_deterministic_fast_path_is_identical_across_runtime_backends(
    tmp_path,
    monkeypatch,
) -> None:
    questions = tmp_path / "fast-path.json"
    questions.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "index-rebound-space",
                        "question": "科创50你认为反弹空间有多少",
                        "as_of": "2026-07-24",
                        "tier": "standard",
                        "timeout": 30.0,
                        "required_outputs": [
                            "technical_levels",
                            "invalidation_conditions",
                            "data_date",
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "fast-output.json"
    monkeypatch.setattr(
        benchmark,
        "_build_runtime",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("deterministic fast path must not build a model runtime")
        ),
    )
    monkeypatch.setattr(
        benchmark,
        "run_deterministic_fast_path",
        lambda *_args, **_kwargs: {
            "execution_kind": "deterministic_fast_path",
            "status": "completed",
            "answer": "科创50压力区决定反弹空间。",
            "llm_calls": 0,
            "tool_calls": 1,
        },
    )

    assert benchmark.main(
        [
            "--backend",
            "continuous_glm",
            "--backend",
            "sdk_glm",
            "--backend",
            "codex_headless",
            "--questions-file",
            str(questions),
            "--output",
            str(output),
        ]
    ) == 0

    arms = json.loads(output.read_text(encoding="utf-8"))["cases"][0]["arms"]
    assert {arm["answer"] for arm in arms} == {"科创50压力区决定反弹空间。"}
    assert {arm["artifact_sha256"] for arm in arms} == {
        arms[0]["artifact_sha256"]
    }
    assert {arm["llm_calls"] for arm in arms} == {0}

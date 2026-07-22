from __future__ import annotations

import json

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
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

    class FakeRuntime:
        def run(self, *, task_frame, context, registry):
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
                    OutputEvidenceBinding(item.output_id, ("market-1",))
                    for item in context.contract.required_outputs
                ),
                usage=AgentUsage(llm_calls=2, tool_calls=1),
            )

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
        lambda *_args, **_kwargs: FakeRuntime(),
    )
    monkeypatch.setattr(
        episode_ab,
        "_build_registry",
        lambda *_args, **_kwargs: ResearchToolRegistry(()),
    )

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
    assert case["episode"]["outcome"]["usage"] == {
        "llm_calls": 2,
        "tool_calls": 1,
        "invalid_actions": 0,
    }
    assert len(case["episode"]["outcome"]["events"]) == 2


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

    assert episode_ab.main(
        [
            "--questions-file",
            str(questions),
            "--output",
            str(output),
        ]
    ) == 0

    case = json.loads(output.read_text(encoding="utf-8"))["cases"][0]
    assert case["episode"]["execution_kind"] == "deterministic_fast_path"
    assert case["episode"]["llm_calls"] == 0

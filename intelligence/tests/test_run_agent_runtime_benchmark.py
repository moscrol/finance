from __future__ import annotations

import json
from pathlib import Path
import subprocess

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.llm_refine import LLMProvider
from intelligence.services.provider_observability import ProviderTrace
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


def test_dry_run_records_exact_source_provenance(tmp_path) -> None:
    output = tmp_path / "plan.json"
    repo_root = Path(benchmark.__file__).resolve().parents[1]
    expected_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    expected_dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )

    assert benchmark.main(
        [
            "--dry-run",
            "--backend",
            "sdk_gpt",
            "--questions-file",
            str(FIXTURE),
            "--output",
            str(output),
        ]
    ) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source_revision"] == expected_revision
    assert payload["source_dirty"] is expected_dirty


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


def test_headless_causal_case_promotes_to_deep_with_verifier_reserve() -> None:
    case = next(
        item
        for item in benchmark._load_cases(FIXTURE)
        if item.case_id == "rebound-duration"
    )
    control = benchmark.TurnControlCore().control(
        case.question,
        llm_complete=lambda *_args, **_kwargs: (None, None, "dry_run"),
    )

    context = benchmark._fresh_context(
        case,
        control,
        backend="codex_headless",
        latest_data_date="2026-07-24",
    )

    assert context.policy.tier == "deep"
    assert context.deadline.synthesis_reserve == 48.0
    assert context.deadline.stage_timeout(180.0) > 131.0


def test_sdk_gpt_runtime_accepts_keychain_provider_without_environment(
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    case = benchmark._load_cases(FIXTURE)[0]
    provider = LLMProvider(
        name="openai",
        api_key="saved-secret-value",
        base_url="http://localhost:57244/v1",
        model="gpt-5.6-sol",
    )

    runtime, model = benchmark._build_runtime(
        "sdk_gpt",
        case,
        object(),
        sdk_gpt_providers=(provider,),
    )

    assert type(runtime).__name__ == "OpenAIAgentsRuntime"
    assert model == "gpt-5.6-sol"
    assert "saved-secret-value" not in repr(runtime)


def test_standard_headless_benchmark_uses_bounded_reasoning_effort() -> None:
    case = next(
        item
        for item in benchmark._load_cases(FIXTURE)
        if item.case_id == "current-mainline"
    )

    runtime, _model = benchmark._build_runtime(
        "codex_headless",
        case,
        object(),
    )

    assert runtime.reasoning_effort == "medium"


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
    monkeypatch.setattr(
        benchmark,
        "latest_market_date",
        lambda _finance_root: "2026-07-24",
    )

    code = benchmark.main(
        [
            "--backend",
            "continuous_glm",
            "--backend",
            "sdk_glm",
            "--questions-file",
            str(questions),
            "--finance-root",
            str(tmp_path),
            "--knowledge-wiki",
            str(tmp_path),
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
    assert [arm["stop_reason"] for arm in arms] == [
        "model_finish",
        "model_finish",
    ]
    assert [arm["effective_timeout_seconds"] for arm in arms] == [30.0, 30.0]


def test_live_runner_exports_safe_diagnostics_for_partial_research(
    tmp_path,
    monkeypatch,
) -> None:
    questions = tmp_path / "diagnostic-case.json"
    questions.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "weekly-market-cause",
                        "question": "这一周行情下跌的主要原因是什么",
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
    output = tmp_path / "diagnostic-output.json"

    class PartialRuntime:
        def run(self, *, task_frame, context, registry):
            del registry
            bindings = tuple(
                OutputEvidenceBinding(
                    required.output_id,
                    (),
                    gap=f"仍缺少：{required.description}",
                )
                for required in context.contract.required_outputs
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status="partial",
                draft="现有证据不足，暂不能判断本周下跌原因。",
                evidence=(),
                traces=(
                    ProviderTrace(
                        provider="eastmoney",
                        capability="news_search",
                        status="future_of_cutoff",
                        detail="authorization=Bearer sk-provider-secret",
                        requested_date="2026-07-24",
                        served_date="2026-07-25",
                        result_count=2,
                    ),
                ),
                gaps=("仍缺少时间对齐的下跌原因证据",),
                stop_reason="deadline_exhausted",
                events=(
                    EpisodeEvent(
                        1,
                        "task",
                        {"task_frame_hash": task_frame.task_frame_hash},
                    ),
                    EpisodeEvent(
                        2,
                        "tool_request",
                        {
                            "name": "evidence_search",
                            "arguments": {
                                "query": "A股下跌原因",
                                "api_key": "sk-runtime-secret",
                                "sql": "select * from private_market_table",
                            },
                        },
                    ),
                    EpisodeEvent(
                        3,
                        "invalid_action",
                        {"reason": "finish payload missing bindings"},
                    ),
                ),
                bindings=bindings,
                usage=AgentUsage(llm_calls=2, tool_calls=1, invalid_actions=1),
            )

    class PartialSemanticVerifier:
        provider_attempts = 0

        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="partial",
                public_answer=structurally_verified.outcome.draft,
                judge_status="unavailable",
            )

    monkeypatch.setattr(
        benchmark,
        "_build_runtime",
        lambda *_args, **_kwargs: (PartialRuntime(), "fake-model"),
    )
    monkeypatch.setattr(
        benchmark,
        "_build_registry",
        lambda *_args, **_kwargs: ResearchToolRegistry(()),
    )
    monkeypatch.setattr(
        benchmark,
        "_build_semantic_verifier",
        lambda *_args, **_kwargs: PartialSemanticVerifier(),
    )
    monkeypatch.setattr(
        benchmark,
        "latest_market_date",
        lambda _finance_root: "2026-07-24",
    )

    assert benchmark.main(
        [
            "--backend",
            "continuous_glm",
            "--questions-file",
            str(questions),
            "--finance-root",
            str(tmp_path),
            "--knowledge-wiki",
            str(tmp_path),
            "--output",
            str(output),
        ]
    ) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    arm = payload["cases"][0]["arms"][0]
    diagnostics = arm["diagnostics"]
    encoded = json.dumps(payload, ensure_ascii=False)

    assert [event["kind"] for event in diagnostics["events"]] == [
        "tool_request",
        "invalid_action",
    ]
    assert diagnostics["events"][0]["payload"]["arguments"] == {
        "query": "A股下跌原因"
    }
    assert diagnostics["missing_outputs"]
    assert diagnostics["mandatory_missing_capabilities"]
    assert diagnostics["gaps"] == ["仍缺少时间对齐的下跌原因证据"]
    assert diagnostics["bindings"]
    assert diagnostics["root_budget"]["remaining_calls"] >= 0
    assert diagnostics["future_of_cutoff"][0]["provider"] == "eastmoney"
    assert "sk-provider-secret" not in encoded
    assert "sk-runtime-secret" not in encoded
    assert "private_market_table" not in encoded


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
    monkeypatch.setattr(
        benchmark,
        "latest_market_date",
        lambda _finance_root: "2026-07-24",
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
            "--finance-root",
            str(tmp_path),
            "--knowledge-wiki",
            str(tmp_path),
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


def test_live_runner_aborts_batch_on_shared_provider_infrastructure_failure(
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
    output = tmp_path / "infra.json"

    class UnavailableRuntime:
        def run(self, *, task_frame, context, registry):
            del context, registry
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status="failed",
                draft="",
                evidence=(),
                traces=(),
                gaps=("sdk_auth_unavailable",),
                stop_reason="sdk_auth_unavailable",
                events=(
                    EpisodeEvent(
                        1,
                        "task",
                        {"task_frame_hash": task_frame.task_frame_hash},
                    ),
                ),
                bindings=(),
                usage=AgentUsage(llm_calls=1, invalid_actions=1),
            )

    monkeypatch.setattr(
        benchmark,
        "_build_runtime",
        lambda *_args, **_kwargs: (UnavailableRuntime(), "gpt-5.6-sol"),
    )
    monkeypatch.setattr(
        benchmark,
        "_build_registry",
        lambda *_args, **_kwargs: ResearchToolRegistry(()),
    )
    monkeypatch.setattr(
        benchmark,
        "latest_market_date",
        lambda _finance_root: "2026-07-24",
    )

    code = benchmark.main(
        [
            "--backend",
            "sdk_gpt",
            "--questions-file",
            str(questions),
            "--finance-root",
            str(tmp_path),
            "--knowledge-wiki",
            str(tmp_path),
            "--output",
            str(output),
        ]
    )

    assert code == 3
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["infrastructure_failure"] == {
        "case_id": "current-mainline",
        "backend": "sdk_gpt",
        "reason": "sdk_auth_unavailable",
    }
    assert artifact["summary"]["completed_case_count"] == 0
    assert artifact["summary"]["passed"] is False


def test_live_runner_uses_headless_provider_for_shared_semantic_verifier(
    tmp_path,
    monkeypatch,
) -> None:
    questions = tmp_path / "headless-case.json"
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
    output = tmp_path / "headless-output.json"
    judge_provider = LLMProvider(
        name="openai",
        api_key="headless-judge-secret",
        base_url="http://localhost:57244/v1",
        model="gpt-5.6-sol",
    )
    captured_providers: list[LLMProvider] = []

    class FakeHeadlessRuntime:
        model_name = "gpt-5.6-sol"

        @staticmethod
        def semantic_providers() -> tuple[LLMProvider, ...]:
            return (judge_provider,)

        @staticmethod
        def run(*, task_frame, context, registry):
            del registry
            evidence = AgentEvidence(
                tool="mainline_context",
                title="同日主线结构",
                detail="截至2026-07-24，半导体是当前主线。",
                source="test",
                source_date="2026-07-24",
                content_hash="headless-mainline-hash",
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status="completed",
                draft="截至2026-07-24，半导体是当前主线。",
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
                ),
                bindings=tuple(
                    OutputEvidenceBinding(
                        required.output_id,
                        ("headless-mainline-hash",),
                    )
                    for required in context.contract.required_outputs
                ),
                usage=AgentUsage(llm_calls=1, tool_calls=1),
            )

    class PassingSemanticVerifier:
        provider_attempts = 1

        @staticmethod
        def verify(*, frame, structurally_verified, deadline):
            del frame, deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=structurally_verified.outcome.draft,
                judge_status="passed",
            )

    def build_semantic_verifier(_case, _context, *, providers=()):
        captured_providers.extend(providers)
        return PassingSemanticVerifier()

    runtime = FakeHeadlessRuntime()
    monkeypatch.setattr(
        benchmark,
        "_build_runtime",
        lambda *_args, **_kwargs: (runtime, runtime.model_name),
    )
    monkeypatch.setattr(
        benchmark,
        "_build_registry",
        lambda *_args, **_kwargs: ResearchToolRegistry(()),
    )
    monkeypatch.setattr(
        benchmark,
        "_build_semantic_verifier",
        build_semantic_verifier,
    )
    monkeypatch.setattr(
        benchmark,
        "latest_market_date",
        lambda _finance_root: "2026-07-24",
    )

    assert benchmark.main(
        [
            "--backend",
            "codex_headless",
            "--questions-file",
            str(questions),
            "--finance-root",
            str(tmp_path),
            "--knowledge-wiki",
            str(tmp_path),
            "--output",
            str(output),
        ]
    ) == 0

    assert captured_providers == [judge_provider]
    arm = json.loads(output.read_text(encoding="utf-8"))["cases"][0]["arms"][0]
    assert arm["semantic_status"] == "passed"
    assert "headless-judge-secret" not in output.read_text(encoding="utf-8")


def test_live_runner_rejects_stale_finance_root_before_runtime(
    tmp_path,
    monkeypatch,
) -> None:
    output = tmp_path / "stale.json"
    monkeypatch.setattr(
        benchmark,
        "latest_market_date",
        lambda _finance_root: "2026-06-04",
    )
    monkeypatch.setattr(
        benchmark,
        "_run_runtime_arm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("stale data must fail before runtime execution")
        ),
    )

    code = benchmark.main(
        [
            "--backend",
            "continuous_glm",
            "--questions-file",
            str(FIXTURE),
            "--finance-root",
            str(tmp_path),
            "--knowledge-wiki",
            str(tmp_path),
            "--output",
            str(output),
        ]
    )

    assert code == 2
    assert not output.exists()

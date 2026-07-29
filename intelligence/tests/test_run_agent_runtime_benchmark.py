from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_session import CallbackEpisodeSession
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome
from intelligence.services.llm_refine import LLMProvider
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import ResearchToolRegistry
from scripts import run_agent_runtime_benchmark as benchmark


FIXTURE = (
    Path(__file__).parent / "fixtures" / "runtime_backend_cases.json"
)


def _fake_sealed_fixture(tmp_path: Path, question_file: Path) -> Path:
    output_root = tmp_path / "ceiling"
    root = output_root / "fixture"
    files = {
        "instruction-export/instruction/AGENTS.md": b"sealed instructions\n",
        "finance.duckdb": b"sealed duckdb",
        "wiki/entities/example.md": b"# example\n",
        "index/meta.json": b'{"mode":"hybrid"}\n',
        "kb-code/scripts/rag_index.py": b"# sealed rag code\n",
    }
    for relative, data in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o444)
    file_manifest = [
        {
            "path": relative,
            "mode": 0o444,
            "bytes": len(files[relative]),
            "sha256": hashlib.sha256(files[relative]).hexdigest(),
        }
        for relative in sorted(files)
    ]
    fixture_input = {
        "as_of": "2026-07-24",
        "question_file_sha256": hashlib.sha256(question_file.read_bytes()).hexdigest(),
    }
    manifest = {
        "schema_version": 1,
        "status": "sealed",
        "input_sha256": benchmark._artifact_hash(fixture_input),
        "input": fixture_input,
        "components": {
            "instruction": {
                "component_root": "instruction-export",
                "manifest_sha256": hashlib.sha256(
                    files["instruction-export/instruction/AGENTS.md"]
                ).hexdigest(),
            },
            "finance": {
                "target": "finance.duckdb",
                "sha256": hashlib.sha256(files["finance.duckdb"]).hexdigest(),
            },
            "wiki": {
                "root": "wiki",
                "manifest_sha256": hashlib.sha256(
                    files["wiki/entities/example.md"]
                ).hexdigest(),
            },
            "hybrid": {
                "index_root": "index",
                "code_runtime": "kb-code",
                "manifest_sha256": hashlib.sha256(files["index/meta.json"]).hexdigest(),
                "python_executable": sys.executable,
            },
        },
        "semantic_receipt_sha256": "b" * 64,
        "files": file_manifest,
    }
    manifest["manifest_sha256"] = benchmark._artifact_hash(manifest)
    manifest_path = root / "fixture.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_path.chmod(0o444)
    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        reverse=True,
    ):
        directory.chmod(0o555)
    root.chmod(0o555)
    pointer = {
        "schema_version": 1,
        "relative_component": "fixture",
        "manifest_sha256": manifest["manifest_sha256"],
    }
    pointer["pointer_sha256"] = benchmark._artifact_hash(pointer)
    pointer_path = output_root / "sealed-fixture.json"
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    pointer_path.chmod(0o444)
    return pointer_path


def test_load_sealed_fixture_recomputes_input_hash(tmp_path: Path) -> None:
    questions = tmp_path / "questions.json"
    questions.write_text('{"cases": []}', encoding="utf-8")
    pointer_path = _fake_sealed_fixture(tmp_path, questions)
    root = pointer_path.parent / "fixture"
    manifest_path = root / "fixture.manifest.json"
    manifest_path.chmod(0o644)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["input_sha256"] = "a" * 64
    manifest["manifest_sha256"] = benchmark._artifact_hash(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_path.chmod(0o444)
    pointer_path.chmod(0o644)
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["manifest_sha256"] = manifest["manifest_sha256"]
    pointer["pointer_sha256"] = benchmark._artifact_hash(
        {key: value for key, value in pointer.items() if key != "pointer_sha256"}
    )
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    pointer_path.chmod(0o444)

    with pytest.raises(ValueError, match="input hash mismatch"):
        benchmark._load_sealed_fixture(pointer_path, question_file=questions)


def test_load_sealed_fixture_revalidates_all_files(tmp_path: Path) -> None:
    questions = tmp_path / "questions.json"
    questions.write_text('{"cases": []}', encoding="utf-8")
    pointer = _fake_sealed_fixture(tmp_path, questions)

    fixture = benchmark._load_sealed_fixture(pointer, question_file=questions)

    assert fixture.as_of == "2026-07-24"
    assert fixture.finance_db.read_bytes() == b"sealed duckdb"
    assert fixture.instruction_root.name == "instruction"
    assert fixture.hybrid_index_root.name == "index"

    finance = fixture.finance_db
    finance.chmod(0o644)
    finance.write_bytes(b"tampered")
    finance.chmod(0o444)
    with pytest.raises(ValueError, match="file manifest mismatch"):
        benchmark._load_sealed_fixture(pointer, question_file=questions)


def test_sealed_fixture_dry_run_uses_only_pinned_five_cases(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pointer = _fake_sealed_fixture(tmp_path, FIXTURE)
    output = tmp_path / "sealed-dry-run.json"
    monkeypatch.setattr(benchmark, "_source_provenance", lambda: ("c" * 40, False))
    monkeypatch.setattr(
        benchmark,
        "_build_registry",
        lambda *_args, **_kwargs: ResearchToolRegistry(()),
    )

    code = benchmark.main(
        [
            "--dry-run",
            "--backend",
            "codex_headless",
            "--headless-budget-profile",
            "d_long_expanded",
            *[
                value
                for case_id in benchmark._SEALED_CEILING_CASE_IDS
                for value in ("--case", case_id)
            ],
            "--questions-file",
            str(FIXTURE),
            "--ceiling-fixture-receipt",
            str(pointer),
            "--output",
            str(output),
        ]
    )

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [item["id"] for item in payload["cases"]] == list(
        benchmark._SEALED_CEILING_CASE_IDS
    )
    assert payload["finance_root"] == str(pointer.parent / "fixture")
    assert payload["knowledge_wiki"] == str(pointer.parent / "fixture" / "wiki")
    assert payload["ceiling_fixture"]["no_live_root"] is True
    assert payload["ceiling_fixture"]["model"] == "gpt-5.6-sol"
    assert payload["ceiling_fixture"]["transport"] == "subprocess_mailbox"
    assert [
        item["case_id"]
        for item in payload["ceiling_fixture"]["tool_surface"]["cases"]
    ] == list(benchmark._SEALED_CEILING_CASE_IDS)


def test_sealed_fixture_rejects_live_root_arguments(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pointer = _fake_sealed_fixture(tmp_path, FIXTURE)
    monkeypatch.setattr(benchmark, "_source_provenance", lambda: ("c" * 40, False))

    code = benchmark.main(
        [
            "--dry-run",
            "--backend",
            "codex_headless",
            "--headless-budget-profile",
            "d_long_expanded",
            *[
                value
                for case_id in benchmark._SEALED_CEILING_CASE_IDS
                for value in ("--case", case_id)
            ],
            "--questions-file",
            str(FIXTURE),
            "--ceiling-fixture-receipt",
            str(pointer),
            "--finance-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "should-not-exist.json"),
        ]
    )

    assert code == 2


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


def test_headless_benchmark_uses_backend_neutral_verifier_reserve() -> None:
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

    assert context.deadline.synthesis_reserve == 30.0
    assert context.deadline.stage_timeout(90.0) > 59.0
    assert context.policy.max_steps == 6
    assert context.policy.total_seconds == 90.0


def test_headless_budget_profile_overrides_only_benchmark_context() -> None:
    case = next(
        item
        for item in benchmark._load_cases(FIXTURE)
        if item.case_id == "rebound-duration"
    )
    case = dataclasses.replace(case, case_id="phase-b-profile-d")
    control = benchmark.TurnControlCore().control(
        case.question,
        llm_complete=lambda *_args, **_kwargs: (None, None, "dry_run"),
    )
    profile = benchmark.HEADLESS_BUDGET_PROFILES["d_long_expanded"]

    context = benchmark._fresh_context(
        case,
        control,
        backend="codex_headless",
        latest_data_date="2026-07-24",
        headless_budget_profile=profile,
    )
    runtime, _model = benchmark._build_runtime(
        "codex_headless",
        dataclasses.replace(case, timeout=profile.total_seconds),
        context,
        headless_budget_profile=profile,
    )

    assert context.policy.max_steps == 12
    assert context.policy.total_seconds == 180.0
    assert context.deadline.synthesis_reserve == 30.0
    assert context.deadline.stage_timeout(180.0) > 149.0
    assert context.root_budget.initial_calls == 12
    assert context.root_budget.initial_seconds == 150.0
    assert runtime.finalization_floor_ratio == 0.0


def test_dry_run_records_preregistered_headless_profile_and_case_subset(
    tmp_path,
) -> None:
    output = tmp_path / "phase-b-plan.json"

    assert benchmark.main(
        [
            "--dry-run",
            "--backend",
            "codex_headless",
            "--headless-budget-profile",
            "d_long_expanded",
            "--case",
            "rebound-duration",
            "--case",
            "weekly-market-cause",
            "--case",
            "ruihuatai-valuation",
            "--questions-file",
            str(FIXTURE),
            "--output",
            str(output),
        ]
    ) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["case_count"] == 3
    assert [item["id"] for item in payload["cases"]] == [
        "rebound-duration",
        "ruihuatai-valuation",
        "weekly-market-cause",
    ]
    assert payload["headless_budget_profile"] == {
        "profile_id": "d_long_expanded",
        "total_seconds": 180.0,
        "max_tool_calls": 12,
        "synthesis_reserve_seconds": 30.0,
        "gateway_floor_ratio": 0.0,
        "minimum_tool_calls_to_exercise": 7,
    }
    assert payload["budget_ablation_validity"] == "not_executed"


def test_sdk_gpt_benchmark_uses_backend_neutral_verifier_reserve() -> None:
    case = next(
        item
        for item in benchmark._load_cases(FIXTURE)
        if item.case_id == "rebound-duration"
    )
    case = dataclasses.replace(case, case_id="sdk-gpt-reserve-policy")
    control = benchmark.TurnControlCore().control(
        case.question,
        llm_complete=lambda *_args, **_kwargs: (None, None, "dry_run"),
    )

    context = benchmark._fresh_context(
        case,
        control,
        backend="sdk_gpt",
        latest_data_date="2026-07-24",
    )

    assert context.deadline.synthesis_reserve == 30.0
    assert context.deadline.stage_timeout(90.0) > 59.0
    assert context.root_budget.initial_seconds == 60.0


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
        runtime_providers=(provider,),
    )

    assert type(runtime).__name__ == "OpenAIAgentsRuntime"
    assert model == "gpt-5.6-sol"
    assert "saved-secret-value" not in repr(runtime)


def test_continuous_runtime_accepts_session_provider_without_environment(
    monkeypatch,
) -> None:
    monkeypatch.setattr(benchmark.llm_refine, "detect_providers", lambda: ())
    case = benchmark._load_cases(FIXTURE)[0]
    provider = LLMProvider(
        name="openai",
        api_key="saved-secret-value",
        base_url="http://localhost:57244/v1",
        model="gpt-5.6-sol",
    )

    runtime, model = benchmark._build_runtime(
        "continuous_glm",
        case,
        object(),
        runtime_providers=(provider,),
    )

    assert type(runtime).__name__ == "GLMAgentRuntime"
    assert model == "gpt-5.6-sol"
    assert "saved-secret-value" not in repr(runtime)


def test_keychain_provider_is_injected_into_continuous_benchmark(
    tmp_path,
    monkeypatch,
) -> None:
    output = tmp_path / "live.json"
    provider = LLMProvider(
        name="openai",
        api_key="saved-secret-value",
        base_url="http://localhost:57244/v1",
        model="gpt-5.6-sol",
    )
    captured: list[LLMProvider] = []

    class FakeSettings:
        @staticmethod
        def byok_provider(user_id: str) -> LLMProvider | None:
            assert user_id == "alice"
            return provider

    def run_runtime_arm(
        *_args,
        runtime_providers: tuple[LLMProvider, ...] = (),
        **_kwargs,
    ):
        captured.extend(runtime_providers)
        return ({"execution_status": "completed"}, ())

    monkeypatch.setattr(benchmark, "SessionLLMSettings", FakeSettings)
    monkeypatch.setattr(benchmark, "_run_runtime_arm", run_runtime_arm)
    monkeypatch.setattr(
        benchmark,
        "summarize_runtime_benchmark",
        lambda **_kwargs: {"passed": True},
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
            str(FIXTURE),
            "--finance-root",
            str(tmp_path),
            "--knowledge-wiki",
            str(tmp_path),
            "--keychain-user",
            "alice",
            "--output",
            str(output),
        ]
    ) == 0

    assert captured == [provider] * 9
    assert json.loads(output.read_text(encoding="utf-8"))["credential_source"] == (
        "keychain"
    )
    assert "saved-secret-value" not in output.read_text(encoding="utf-8")


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
                content_hash = hashlib.sha256(
                    f"{self.backend}-{index}".encode("utf-8")
                ).hexdigest()
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
    assert arms[0]["candidate_answer"] == arms[0]["published_answer"]
    assert arms[0]["answer"] == arms[0]["published_answer"]
    assert arms[0]["claims"][0]["text"] == arms[0]["published_answer"]
    assert len(arms[0]["sources"][0]["content_hash"]) == 64
    assert arms[0]["blind_projection"] == {
        "published_answer": arms[0]["published_answer"],
        "claims": arms[0]["claims"],
        "sources": arms[0]["sources"],
    }
    assert arms[0]["blind_projection_sha256"] == benchmark._artifact_hash(
        arms[0]["blind_projection"]
    )
    assert arms[0]["blind_projection_json_pointer"] == (
        "/cases/0/arms/0/blind_projection"
    )


def test_live_runner_uses_production_adapter_delivery_repair(
    tmp_path,
    monkeypatch,
) -> None:
    questions = tmp_path / "delivery-repair-case.json"
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
    resume_calls = 0
    private_token = "Bearer sk-benchmark-secret"
    projection_case = {"private": False}

    class DeliveryRepairRuntime:
        def start(self, task_frame, *, context, registry):
            del registry
            required_outputs = context.contract.required_outputs
            evidence = (
                AgentEvidence(
                    tool="market_data",
                    title="同日市场总览",
                    detail="市场量能稳定，风险偏好仍有承接。",
                    source=(
                        private_token
                        if projection_case["private"]
                        else "local market fixture"
                    ),
                    internal_locator=(
                        private_token if projection_case["private"] else ""
                    ),
                    source_date="2026-07-24",
                    content_hash="a" * 64,
                ),
                AgentEvidence(
                    tool="mainline_context",
                    title="同日主线结构",
                    detail="半导体保持持续性，医药进入分歧。",
                    source="local mainline fixture",
                    source_date="2026-07-24",
                    content_hash="b" * 64,
                ),
            )
            initial = AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status="partial",
                draft="",
                evidence=evidence,
                traces=(
                    ProviderTrace("test:market", "market_data", "success"),
                    ProviderTrace("test:mainline", "mainline_context", "success"),
                ),
                gaps=("sdk_timeout",),
                stop_reason="sdk_timeout",
                events=(
                    EpisodeEvent(
                        1,
                        "task",
                        {"task_frame_hash": task_frame.task_frame_hash},
                    ),
                ),
                bindings=(),
                usage=AgentUsage(llm_calls=1, tool_calls=1),
            )

            def resume(previous, goal):
                nonlocal resume_calls
                resume_calls += 1
                assert previous is initial
                assert goal.remaining_calls == 0
                return AgentOutcome(
                    task_frame_hash=task_frame.task_frame_hash,
                    status="completed",
                    draft="半导体是当前持续性主线，医药处于分歧。",
                    evidence=evidence,
                    traces=initial.traces,
                    gaps=(),
                    stop_reason="repair_model_finish",
                    events=(
                        *initial.events,
                        EpisodeEvent(
                            2,
                            "repair_goal",
                            {"repair_goal_id": goal.repair_goal_id},
                        ),
                        EpisodeEvent(3, "repair_reentry", {"cycle": goal.cycle}),
                        EpisodeEvent(
                            4,
                            "model_turn",
                            {"task_frame_hash": task_frame.task_frame_hash},
                        ),
                    ),
                    bindings=tuple(
                        OutputEvidenceBinding(
                            required.output_id,
                            tuple(item.content_hash for item in evidence),
                        )
                        for required in required_outputs
                    ),
                    usage=AgentUsage(llm_calls=2, tool_calls=2),
                )

            return CallbackEpisodeSession(
                episode_id=context.contract.task_id,
                outcome=initial,
                resume_callback=resume,
            )

    class PassingSemanticVerifier:
        provider_attempts = 1

        def verify(self, *, frame, structurally_verified, deadline):
            del frame, deadline
            return SemanticEpisodeOutcome(
                verified=structurally_verified,
                status="completed",
                public_answer=(
                    private_token
                    if projection_case["private"]
                    else structurally_verified.outcome.draft
                ),
                judge_status="passed",
            )

    monkeypatch.setattr(
        benchmark,
        "_build_runtime",
        lambda *_args, **_kwargs: (DeliveryRepairRuntime(), "fake-model"),
    )
    monkeypatch.setattr(
        benchmark,
        "_build_registry",
        lambda *_args, **_kwargs: ResearchToolRegistry(()),
    )
    monkeypatch.setattr(
        benchmark,
        "_build_semantic_verifier",
        lambda *_args, **_kwargs: PassingSemanticVerifier(),
    )
    monkeypatch.setattr(
        benchmark,
        "latest_market_date",
        lambda _finance_root: "2026-07-24",
    )

    assert benchmark.main(
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
    ) == 0

    arm = json.loads(output.read_text(encoding="utf-8"))["cases"][0]["arms"][0]
    assert resume_calls == 1
    assert arm["status"] == "completed"
    assert arm["structural_status"] == "completed"
    assert arm["semantic_status"] == "passed"
    assert arm["protocol_issues"] == []
    assert [
        event["kind"] for event in arm["diagnostics"]["events"]
    ] == ["repair_goal"]

    projection_case["private"] = True
    private_output = tmp_path / "private-projection.json"
    assert benchmark.main(
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
            str(private_output),
        ]
    ) == 0

    private_payload = json.loads(private_output.read_text(encoding="utf-8"))
    private_arm = private_payload["cases"][0]["arms"][0]
    assert resume_calls == 2
    assert private_arm["status"] == "degraded"
    assert private_arm["semantic_status"] == "passed"
    assert private_arm["answer"]
    assert private_arm["citations"] == [
        {
            "title": "同日主线结构",
            "source": "local mainline fixture",
            "date": "2026-07-24",
        }
    ]
    assert private_arm["data_cutoff"] == "2026-07-24"
    assert private_token not in private_output.read_text(encoding="utf-8")


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
                content_hash="c" * 64,
            )
            unrelated = AgentEvidence(
                tool="financial_data",
                title="无关财务指标",
                detail="毛利率为17.37%。",
                source="other",
                source_date="2026-07-24",
                content_hash="d" * 64,
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status="completed",
                draft="截至2026-07-24，半导体是当前主线。",
                evidence=(evidence, unrelated),
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
                        ("c" * 64, "d" * 64),
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
    assert arm["candidate_answer"] == arm["published_answer"]
    assert arm["claims"]
    assert arm["sources"][0]["content_hash"] == "c" * 64
    assert arm["claims"][0]["source_ids"] == ["E1"]
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

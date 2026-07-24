from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.eval.runtime_backend_benchmark import (
    RuntimeArmResult,
    summarize_runtime_benchmark,
)


def _arm(
    backend: str = "continuous_glm",
    *,
    case_id: str = "current-mainline",
) -> RuntimeArmResult:
    return RuntimeArmResult(
        case_id=case_id,
        backend=backend,
        model="glm-5.2" if backend != "codex_headless" else "gpt-5.6",
        answer="当前主线是医药，电力是轮动支线。",
        status="completed",
        structural_status="completed",
        semantic_status="passed",
        task_alignment_score=1.0,
        latency_seconds=10.2,
        provider_attempts=2,
        llm_calls=2,
        tool_calls=3,
        duplicate_queries=0,
        input_tokens=None,
        output_tokens=None,
        protocol_issues=(),
        artifact_sha256="a" * 64,
    )


def test_runtime_arm_round_trip() -> None:
    arm = _arm()

    assert RuntimeArmResult.from_dict(arm.to_dict()) == arm


def test_runtime_arm_rejects_invalid_metrics_and_hash() -> None:
    with pytest.raises(ValueError, match="latency_seconds"):
        replace(_arm(), latency_seconds=-0.1)
    with pytest.raises(ValueError, match="artifact_sha256"):
        replace(_arm(), artifact_sha256="not-a-sha")
    with pytest.raises(ValueError, match="task_alignment_score"):
        replace(_arm(), task_alignment_score=1.1)


def test_summary_requires_every_declared_backend() -> None:
    with pytest.raises(ValueError, match="missing backend results"):
        summarize_runtime_benchmark(
            case_ids=("current-mainline",),
            results=(_arm("continuous_glm"),),
            expected_backends=(
                "continuous_glm",
                "sdk_glm",
                "codex_headless",
            ),
        )


def test_summary_rejects_duplicate_case_backend() -> None:
    duplicate = _arm("continuous_glm")

    with pytest.raises(ValueError, match="duplicate runtime arm result"):
        summarize_runtime_benchmark(
            case_ids=("current-mainline",),
            results=(duplicate, duplicate),
            expected_backends=("continuous_glm",),
        )


def test_summary_reports_backend_metrics_and_protocol_failures() -> None:
    continuous = _arm("continuous_glm")
    sdk = replace(
        _arm("sdk_glm"),
        latency_seconds=12.0,
        protocol_issues=("unauthorized_tool",),
    )
    headless = replace(
        _arm("codex_headless"),
        latency_seconds=20.0,
        input_tokens=1200,
        output_tokens=300,
    )

    summary = summarize_runtime_benchmark(
        case_ids=("current-mainline",),
        results=(continuous, sdk, headless),
        expected_backends=(
            "continuous_glm",
            "sdk_glm",
            "codex_headless",
        ),
    )

    assert summary["passed"] is False
    assert summary["protocol_failure_count"] == 1
    assert summary["backends"]["continuous_glm"]["median_latency_seconds"] == 10.2
    assert summary["backends"]["codex_headless"]["input_tokens"] == 1200
    assert summary["arm_count"] == 3

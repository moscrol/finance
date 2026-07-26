from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.eval.runtime_backend_benchmark import (
    RuntimeArmResult,
    RuntimeDiagnostics,
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
        stop_reason="model_finish",
        effective_timeout_seconds=90.0,
        citations=(
            {
                "title": "电子行业成交集中度居前",
                "source": "本地市场数据",
                "date": "2026-07-24",
            },
        ),
        data_cutoff="2026-07-24",
    )


def test_runtime_arm_round_trip() -> None:
    arm = _arm()

    assert RuntimeArmResult.from_dict(arm.to_dict()) == arm
    assert arm.to_dict()["citations"][0]["source"] == "本地市场数据"
    assert arm.to_dict()["data_cutoff"] == "2026-07-24"
    assert arm.to_dict()["stop_reason"] == "model_finish"
    assert arm.to_dict()["effective_timeout_seconds"] == 90.0


def test_runtime_diagnostics_round_trip_redacts_control_plane_data() -> None:
    diagnostics = RuntimeDiagnostics.from_runtime_state(
        events=(
            {
                "sequence": 2,
                "kind": "tool_request",
                "payload": {
                    "name": "evidence_search",
                    "arguments": {
                        "query": "A股下跌原因",
                        "api_key": "sk-live-secret",
                        "sql": "select * from secret_table",
                        "table": "secret_table",
                        "path": "/Users/a77/private/data.duckdb",
                    },
                },
            },
            {
                "sequence": 3,
                "kind": "model_turn",
                "payload": {"messages": [{"role": "system", "content": "hidden"}]},
            },
            {
                "sequence": 4,
                "kind": "invalid_action",
                "payload": {"reason": "tool arguments were invalid"},
            },
            {
                "sequence": 5,
                "kind": "mode_decision",
                "payload": {
                    "requested_mode": "deep",
                    "effective_mode": "deep",
                    "approved": True,
                    "reason": "observable_complexity_approved",
                    "observable_conditions": ["multiple_evidence_domains"],
                    "research_tier": "deep",
                    "tool_call_cap": 24,
                    "target_seconds": 240.0,
                    "max_repair_cycles": 3,
                    "max_branches": 3,
                    "prompt": "hidden mode prompt",
                },
            },
        ),
        provider_traces=(
            {
                "provider": "eastmoney",
                "capability": "news_search",
                "status": "future_of_cutoff",
                "detail": "query=A股; authorization=Bearer sk-provider-secret",
                "requested_date": "2026-07-20",
                "served_date": "2026-07-21",
                "result_count": 2,
            },
        ),
        missing_outputs=("causal_explanation",),
        mandatory_missing_capabilities=("market_cause_news",),
        gaps=("仍缺少时间对齐的原因",),
        bindings=(
            {
                "output_id": "direct_assessment",
                "evidence_hashes": [],
                "gap": "仍缺少直接判断",
                "basis": "evidence",
            },
        ),
        root_budget={
            "episode_id": "runtime-benchmark:weekly-market-cause",
            "remaining_calls": 2,
            "remaining_seconds": 7.5,
            "password": "do-not-export",
        },
    )
    arm = replace(_arm(), diagnostics=diagnostics)

    restored = RuntimeArmResult.from_dict(arm.to_dict())
    encoded = str(arm.to_dict())

    assert restored == arm
    assert [event["kind"] for event in diagnostics.events] == [
        "tool_request",
        "invalid_action",
        "mode_decision",
    ]
    assert diagnostics.events[0]["payload"]["arguments"] == {
        "query": "A股下跌原因"
    }
    assert diagnostics.events[1]["payload"]["reason"] == (
        "tool arguments were invalid"
    )
    assert diagnostics.events[2]["payload"] == {
        "requested_mode": "deep",
        "effective_mode": "deep",
        "approved": True,
        "reason": "observable_complexity_approved",
        "observable_conditions": ["multiple_evidence_domains"],
        "research_tier": "deep",
        "tool_call_cap": 24,
        "target_seconds": 240.0,
        "max_repair_cycles": 3,
        "max_branches": 3,
    }
    assert diagnostics.future_of_cutoff[0]["provider"] == "eastmoney"
    assert diagnostics.root_budget["remaining_calls"] == 2
    assert "sk-live-secret" not in encoded
    assert "sk-provider-secret" not in encoded
    assert "select *" not in encoded
    assert "secret_table" not in encoded
    assert "/Users/a77" not in encoded
    assert "hidden" not in encoded


def test_runtime_arm_rejects_invalid_metrics_and_hash() -> None:
    with pytest.raises(ValueError, match="latency_seconds"):
        replace(_arm(), latency_seconds=-0.1)
    with pytest.raises(ValueError, match="artifact_sha256"):
        replace(_arm(), artifact_sha256="not-a-sha")
    with pytest.raises(ValueError, match="task_alignment_score"):
        replace(_arm(), task_alignment_score=1.1)
    with pytest.raises(ValueError, match="effective_timeout_seconds"):
        replace(_arm(), effective_timeout_seconds=-0.1)


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

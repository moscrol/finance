from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.eval.runtime_backend_benchmark import (
    RuntimeArmResult,
    RuntimeClaim,
    RuntimeDiagnostics,
    RuntimeSource,
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
    published = "截至2026-07-24，医药上涨2.5%。"
    source = RuntimeSource(
        "E1",
        "market_data",
        "b" * 64,
        "2026-07-24",
    )
    claim = RuntimeClaim(
        "C1",
        0,
        len(published),
        published,
        True,
        ("E1",),
    )
    arm = replace(
        _arm(),
        answer=published,
        candidate_answer="原始研究草稿。",
        published_answer=published,
        claims=(claim,),
        sources=(source,),
    )

    assert RuntimeArmResult.from_dict(arm.to_dict()) == arm
    assert arm.to_dict()["citations"][0]["source"] == "本地市场数据"
    assert arm.to_dict()["data_cutoff"] == "2026-07-24"
    assert arm.to_dict()["stop_reason"] == "model_finish"
    assert arm.to_dict()["effective_timeout_seconds"] == 90.0
    assert arm.to_dict()["candidate_answer"] == "原始研究草稿。"
    assert arm.to_dict()["published_answer"] == published
    assert arm.to_dict()["claims"][0]["source_ids"] == ["E1"]
    assert arm.to_dict()["sources"][0]["content_hash"] == "b" * 64


def test_runtime_arm_rejects_projection_divergence_and_unbound_number() -> None:
    with pytest.raises(ValueError, match="published_answer"):
        replace(_arm(), published_answer="另一份公开答案")
    with pytest.raises(ValueError, match="material numeric claim"):
        answer = "上涨2.5%。"
        replace(
            _arm(),
            answer=answer,
            published_answer=answer,
            claims=(RuntimeClaim("C1", 0, len(answer), answer, True, ()),),
        )


def test_runtime_arm_rejects_invalid_claim_span_and_future_source() -> None:
    with pytest.raises(ValueError, match="claim span"):
        replace(
            _arm(),
            claims=(RuntimeClaim("C1", 0, 2, "错误", False, ()),),
        )
    with pytest.raises(ValueError, match="after data_cutoff"):
        replace(
            _arm(),
            sources=(RuntimeSource("E1", "market_data", "c" * 64, "2026-07-25"),),
        )
    with pytest.raises(ValueError, match="absolute path"):
        RuntimeSource("E1", "/Users/a77/private", "c" * 64, "2026-07-24")


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
            {
                "sequence": 6,
                "kind": "branch_completed",
                "payload": {
                    "branch_id": "branch-1",
                    "goal": "查找反方驱动",
                    "status": "completed",
                    "evidence_count": 1,
                    "gap_count": 0,
                    "llm_calls": 2,
                    "tool_calls": 1,
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
        "branch_completed",
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
    assert diagnostics.events[3]["payload"]["evidence_count"] == 1
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


def test_summary_fails_closed_when_runtime_arm_failed() -> None:
    failed = replace(
        _arm("continuous_glm"),
        answer="",
        status="failed",
        structural_status="failed",
        semantic_status="unavailable",
        stop_reason="model_unavailable",
        provider_attempts=0,
        llm_calls=0,
        tool_calls=0,
    )

    summary = summarize_runtime_benchmark(
        case_ids=("current-mainline",),
        results=(failed,),
        expected_backends=("continuous_glm",),
    )

    assert summary["passed"] is False
    assert summary["protocol_failure_count"] == 1
    assert summary["backends"]["continuous_glm"]["protocol_issue_count"] == 1

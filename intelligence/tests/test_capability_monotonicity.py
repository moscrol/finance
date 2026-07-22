from __future__ import annotations

import json

import pytest

from intelligence.eval.capability_monotonicity import (
    DEFAULT_CAPABILITY_CASES,
    CapabilityCase,
    CapabilityRunResult,
    CapabilityScore,
    ThreeArmRecord,
    compare_with_bare,
    evaluate_three_arm_record,
    summarize_three_arm_records,
)
from scripts import capability_monotonicity as capability_cli


def _result(
    *,
    arm: str,
    score: CapabilityScore,
    protocol_passed: bool = True,
    case_id: str = "rebound-duration",
    tool_calls: int | None = None,
) -> CapabilityRunResult:
    return CapabilityRunResult(
        case_id=case_id,
        arm=arm,
        answer=(
            "回答包含反弹、持续、条件、风险等全部协议关键词。"
        ),
        score=score,
        latency=1.0,
        llm_calls=1,
        tool_calls=(0 if arm == "bare" else 3) if tool_calls is None else tool_calls,
        fallback_reason=None,
        protocol_passed=protocol_passed,
        protocol_issues=(),
    )


def test_keywords_cannot_hide_current_capability_regression() -> None:
    bare = _result(
        arm="bare",
        score=CapabilityScore(4, 4, 4, 2, 4),
    )
    current = _result(
        arm="current",
        score=CapabilityScore(1, 1, 1, 4, 1),
    )

    comparison = compare_with_bare(bare, current)

    assert current.protocol_passed is True
    assert comparison.passed is False
    assert comparison.failure_reasons == ("capability_regression",)
    assert comparison.bare_score == 0.9
    assert comparison.harness_score == 0.4


def test_harness_passes_when_non_degraded_with_better_truth_boundary() -> None:
    bare = _result(
        arm="bare",
        score=CapabilityScore(4, 4, 4, 2, 4),
    )
    episode = _result(
        arm="episode",
        score=CapabilityScore(4, 4, 4, 4, 4),
    )

    comparison = compare_with_bare(bare, episode)

    assert episode.score.truth_boundary > bare.score.truth_boundary
    assert comparison.passed is True
    assert comparison.failure_reasons == ()
    assert comparison.harness_score == 1.0


def test_threshold_uses_exact_integer_score_units_at_point_two_boundary() -> None:
    bare = _result(
        arm="bare",
        score=CapabilityScore(4, 4, 4, 2, 4),  # 18/20 = 0.9
    )
    exactly_allowed = _result(
        arm="current",
        score=CapabilityScore(3, 3, 3, 2, 3),  # 14/20 = 0.7
    )
    beyond_allowed = _result(
        arm="episode",
        score=CapabilityScore(3, 3, 3, 1, 3),  # 13/20 = 0.65
    )

    assert compare_with_bare(bare, exactly_allowed).passed is True
    assert compare_with_bare(bare, beyond_allowed).failure_reasons == (
        "capability_regression",
    )


def test_bare_baseline_requires_zero_tools_and_protocol_pass() -> None:
    current = _result(
        arm="current",
        score=CapabilityScore(4, 4, 4, 4, 4),
    )
    with_tools = _result(
        arm="bare",
        score=CapabilityScore(4, 4, 4, 4, 4),
        tool_calls=1,
    )
    with_protocol_failure = _result(
        arm="bare",
        score=CapabilityScore(4, 4, 4, 4, 4),
        protocol_passed=False,
    )

    with pytest.raises(ValueError, match="bare arm must not call tools"):
        compare_with_bare(with_tools, current)
    with pytest.raises(ValueError, match="bare arm protocol must pass"):
        compare_with_bare(with_protocol_failure, current)


def test_default_fixture_fixes_inputs_for_three_required_questions() -> None:
    assert [case.question for case in DEFAULT_CAPABILITY_CASES] == [
        "昨天的反弹能持续多久",
        "目前市场的主线是什么",
        "一个没有现成 skill 的陌生题材怎么判断",
    ]
    for case in DEFAULT_CAPABILITY_CASES:
        assert isinstance(case, CapabilityCase)
        assert case.model
        assert case.temperature == 0.0
        assert case.timeout > 0
        assert case.as_of == "2026-07-22"


def test_three_arm_record_round_trips_all_result_fields() -> None:
    case = DEFAULT_CAPABILITY_CASES[0]
    record = ThreeArmRecord(
        case=case,
        bare=_result(
            arm="bare",
            score=CapabilityScore(4, 4, 4, 2, 4),
            case_id=case.case_id,
        ),
        current=_result(
            arm="current",
            score=CapabilityScore(4, 4, 4, 4, 4),
            case_id=case.case_id,
        ),
        episode=_result(
            arm="episode",
            score=CapabilityScore(4, 4, 4, 4, 4),
            case_id=case.case_id,
        ),
    )

    payload = record.to_dict()
    evaluation = evaluate_three_arm_record(record)

    assert ThreeArmRecord.from_dict(payload) == record
    assert set(payload) == {"case", "bare", "current", "episode"}
    assert {
        "answer",
        "score",
        "latency",
        "llm_calls",
        "tool_calls",
        "fallback_reason",
        "protocol_passed",
        "protocol_issues",
    }.issubset(payload["current"])
    assert evaluation.current.passed is True
    assert evaluation.episode.passed is True


def test_three_arm_report_marks_capability_regression() -> None:
    case = DEFAULT_CAPABILITY_CASES[0]
    strong = CapabilityScore(4, 4, 4, 2, 4)
    weak = CapabilityScore(1, 1, 1, 4, 1)
    record = ThreeArmRecord(
        case=case,
        bare=_result(arm="bare", score=strong, case_id=case.case_id),
        current=_result(arm="current", score=weak, case_id=case.case_id),
        episode=_result(arm="episode", score=strong, case_id=case.case_id),
    )

    report = summarize_three_arm_records([record])

    assert report["gate"] == "capability_monotonicity"
    assert report["passed"] is False
    assert report["regression_count"] == 1
    assert report["evaluations"][0]["current"]["failure_reasons"] == [
        "capability_regression"
    ]


def test_cli_writes_offline_fixture_and_scores_saved_records(tmp_path) -> None:
    fixture_path = tmp_path / "fixture.json"

    assert capability_cli.main(["--write-fixture", str(fixture_path)]) == 0
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert set(fixture["arm_contracts"]) == {"bare", "current", "episode"}

    case = DEFAULT_CAPABILITY_CASES[0]
    strong = CapabilityScore(4, 4, 4, 2, 4)
    weak = CapabilityScore(1, 1, 1, 4, 1)
    record = ThreeArmRecord(
        case=case,
        bare=_result(arm="bare", score=strong, case_id=case.case_id),
        current=_result(arm="current", score=weak, case_id=case.case_id),
        episode=_result(arm="episode", score=strong, case_id=case.case_id),
    )
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "report.json"
    input_path.write_text(
        json.dumps({"schema_version": 1, "records": [record.to_dict()]}),
        encoding="utf-8",
    )

    code = capability_cli.main(
        ["--input", str(input_path), "--output", str(output_path)]
    )

    assert code == 1
    assert json.loads(output_path.read_text(encoding="utf-8"))["passed"] is False

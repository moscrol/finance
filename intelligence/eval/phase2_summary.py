"""Aggregate physically isolated Phase 2 fidelity replay artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

FIDELITY_METRICS = (
    "numeric_match_rate",
    "entity_classification_accuracy",
    "evidence_coverage_rate",
    "cutoff_violation_rate",
    "fact_inference_confusion_rate",
)


def read_json(path: str | Path) -> dict[str, object]:
    return json.loads(
        Path(path).expanduser().read_text(encoding="utf-8")
    )


def _metric_denominator(metric: object) -> int:
    if not isinstance(metric, dict):
        return 0
    return int(metric.get("denominator", metric.get("checked", 0)) or 0)


def build_negative_control_summary(
    *,
    selection: dict[str, object],
    claim_summary: dict[str, object],
) -> dict[str, object]:
    selected_rows = selection.get("dates")
    selected_rows = selected_rows if isinstance(selected_rows, list) else []
    selected_missing_dates = sorted(
        str(row.get("report_date"))
        for row in selected_rows
        if isinstance(row, dict) and row.get("report_status") == "missing"
    )
    selected_registered_dates = sorted(
        str(row.get("report_date"))
        for row in selected_rows
        if isinstance(row, dict)
        and row.get("report_status") == "registered"
    )
    report_rows = claim_summary.get("reports")
    report_rows = report_rows if isinstance(report_rows, list) else []
    evaluated_missing = [
        row
        for row in report_rows
        if isinstance(row, dict) and row.get("status") == "missing"
    ]
    evaluated_missing_dates = sorted(
        str(row.get("report_date")) for row in evaluated_missing
    )
    denominator_contribution = {
        name: sum(
            _metric_denominator(
                row.get("metrics", {}).get(name)
                if isinstance(row.get("metrics"), dict)
                else None
            )
            for row in evaluated_missing
        )
        for name in FIDELITY_METRICS
    }
    strata = selection.get("selected_strata")
    report_status = (
        strata.get("report_status")
        if isinstance(strata, dict)
        else {}
    )
    selected_missing_count = (
        len(selected_missing_dates)
        if selected_rows
        else int(report_status.get("missing", 0))
        if isinstance(report_status, dict)
        else 0
    )
    selected_registered_count = (
        len(selected_registered_dates)
        if selected_rows
        else int(report_status.get("registered", 0))
        if isinstance(report_status, dict)
        else 0
    )
    claim_statuses = claim_summary.get("report_status_counts")
    evaluated_missing_count = (
        len(evaluated_missing_dates)
        if report_rows
        else int(claim_statuses.get("missing", 0))
        if isinstance(claim_statuses, dict)
        else 0
    )
    dates_match = (
        selected_missing_dates == evaluated_missing_dates
        if selected_rows and report_rows
        else selected_missing_count == evaluated_missing_count
    )
    denominator_isolation = all(
        value == 0 for value in denominator_contribution.values()
    )
    return {
        "schema_version": "fidelity-negative-controls-1.0",
        "control_type": "report_availability",
        "selected_trading_dates": selection.get("selected_count"),
        "registered_canonical_report_count": selected_registered_count,
        "missing_report_count": selected_missing_count,
        "missing_report_dates": selected_missing_dates,
        "claim_evaluator_missing_report_count": evaluated_missing_count,
        "claim_evaluator_missing_report_dates": evaluated_missing_dates,
        "dates_preserved_without_substitution": dates_match,
        "substitution_allowed": False,
        "fidelity_metric_denominator_scope": (
            "registered exact-date canonical reports only"
        ),
        "missing_report_denominator_contribution": denominator_contribution,
        "denominator_isolation_passed": denominator_isolation,
        "passed": dates_match and denominator_isolation,
    }


def build_phase2_summary(
    *,
    selection: dict[str, object],
    input_report: dict[str, object],
    claim_summary: dict[str, object],
    outcome_report: dict[str, object],
    comparison_report: dict[str, object],
) -> dict[str, object]:
    selected_strata = selection.get("selected_strata")
    negative_control_summary = build_negative_control_summary(
        selection=selection,
        claim_summary=claim_summary,
    )
    input_isolation = input_report.get("output_isolation")
    outcome_isolation = outcome_report.get("output_isolation")
    physically_isolated = bool(
        isinstance(input_isolation, dict)
        and input_isolation.get("outcome_not_written")
        and isinstance(outcome_isolation, dict)
        and not outcome_isolation.get("contains_as_known_at")
        and comparison_report.get("physically_separate")
    )
    gold_counts = claim_summary.get("gold_candidate_status_counts")
    approved_gold = (
        int(gold_counts.get("approved", 0))
        if isinstance(gold_counts, dict)
        else 0
    )
    blocking_dates = claim_summary.get("blocking_version_gap_dates")
    blocking_count = (
        len(blocking_dates) if isinstance(blocking_dates, list) else 0
    )
    return {
        "schema_version": "fidelity-replay-phase2-summary-1.1",
        "task_id": "fidelity-replay-phase2-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected_count": selection.get("selected_count"),
        "selected_strata": selected_strata,
        "negative_controls": negative_control_summary,
        "current_state_metrics": claim_summary.get("metrics"),
        "historical_replay_metrics": claim_summary.get(
            "historical_replay"
        ),
        "claim_status_counts": claim_summary.get(
            "claim_status_counts"
        ),
        "causal_statement_counts": claim_summary.get(
            "causal_statement_counts"
        ),
        "version_gap_status_counts": claim_summary.get(
            "version_gap_status_counts"
        ),
        "pit_status_counts": input_report.get("status_counts"),
        "outcome_status_counts": outcome_report.get("status_counts"),
        "comparison_status_counts": comparison_report.get(
            "status_counts"
        ),
        "physical_isolation": {
            "passed": physically_isolated,
            "input": input_isolation,
            "outcome": outcome_isolation,
            "comparison": {
                "known_dir": comparison_report.get("known_dir"),
                "final_dir": comparison_report.get("final_dir"),
                "physically_separate": comparison_report.get(
                    "physically_separate"
                ),
            },
        },
        "gates": {
            "approved_gold_count": approved_gold,
            "blocking_version_gap_dates": blocking_count,
            "human_review_required": True,
        },
        "decision_eligible": False,
    }


def _metric_line(label: str, metric: object) -> str:
    if not isinstance(metric, dict):
        return f"| {label} | pending | 0 / 0 | 0 |"
    value = metric.get("value")
    rendered = (
        f"{float(value):.2%}" if isinstance(value, (int, float))
        else "pending"
    )
    numerator = metric.get("numerator", metric.get("passed", 0))
    denominator = metric.get(
        "denominator",
        metric.get("checked", 0),
    )
    return (
        f"| {label} | {rendered} | {numerator} / {denominator} "
        f"| {metric.get('pending', 0)} |"
    )


def render_phase2_summary(summary: dict[str, object]) -> str:
    isolation = summary["physical_isolation"]
    negatives = summary["negative_controls"]
    gates = summary["gates"]
    negative_status = (
        "未替换"
        if negatives["dates_preserved_without_substitution"]
        else "异常"
    )
    lines = [
        (
            "# Phase 2："
            f"{summary.get('selected_count')} 日现状忠实度 / 历史重放验收"
        ),
        "",
        f"- 样本数：{summary.get('selected_count')}",
        "- 决策资格：否；人工金标准和版本缺口仍是硬门。",
        "",
        "## 五项现状忠实度指标",
        "",
        "| 指标 | 值 | 分子 / 分母 | pending |",
        "|---|---:|---:|---:|",
    ]
    metrics = summary.get("current_state_metrics")
    if isinstance(metrics, dict):
        for name, label in (
            ("numeric_match_rate", "数字一致率"),
            ("entity_classification_accuracy", "实体归类准确率"),
            ("evidence_coverage_rate", "证据覆盖率"),
            ("cutoff_violation_rate", "截止违规率"),
            ("fact_inference_confusion_rate", "事实/推断混淆率"),
        ):
            lines.append(_metric_line(label, metrics.get(name)))
    lines.extend(
        [
            "",
            "## 隔离与负对照",
            "",
            (
                "- 物理隔离："
                f"{'通过' if isolation['passed'] else '失败'}"
            ),
            (
                "- 无报告负对照："
                f"{negatives['missing_report_count']} "
                "个；"
                f"{negative_status}"
            ),
            (
                "- 负对照分母隔离："
                f"{'通过' if negatives['denominator_isolation_passed'] else '失败'}；"
                "只对 exact-date canonical reports 计算忠实度。"
            ),
            (
                "- approved gold："
                f"{gates['approved_gold_count']}；"
                "自动 candidate 不等于人工金标准。"
            ),
            (
                "- 版本缺口阻断日期："
                f"{gates['blocking_version_gap_dates']}。"
            ),
            "",
            "> pending / partial / needs_review / unverifiable 均不视为通过。",
            "",
        ]
    )
    return "\n".join(lines)


def write_json(path: str | Path, body: dict[str, object]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

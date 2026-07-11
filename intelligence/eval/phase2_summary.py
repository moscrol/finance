"""Aggregate physically isolated Phase 2 fidelity replay artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def read_json(path: str | Path) -> dict[str, object]:
    return json.loads(
        Path(path).expanduser().read_text(encoding="utf-8")
    )


def build_phase2_summary(
    *,
    selection: dict[str, object],
    input_report: dict[str, object],
    claim_summary: dict[str, object],
    outcome_report: dict[str, object],
    comparison_report: dict[str, object],
) -> dict[str, object]:
    selected_strata = selection.get("selected_strata")
    report_strata = (
        selected_strata.get("report_status")
        if isinstance(selected_strata, dict)
        else {}
    )
    negative_controls = (
        int(report_strata.get("missing", 0))
        if isinstance(report_strata, dict)
        else 0
    )
    claim_statuses = claim_summary.get("report_status_counts")
    preserved_missing = (
        int(claim_statuses.get("missing", 0))
        if isinstance(claim_statuses, dict)
        else 0
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
        "schema_version": "fidelity-replay-phase2-summary-1.0",
        "task_id": "fidelity-replay-phase2-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected_count": selection.get("selected_count"),
        "selected_strata": selected_strata,
        "negative_controls": {
            "selected_missing_reports": negative_controls,
            "claim_evaluator_missing_reports": preserved_missing,
            "preserved_without_substitution": (
                negative_controls == preserved_missing
            ),
        },
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
        if negatives["preserved_without_substitution"]
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
                f"{negatives['selected_missing_reports']} "
                "个；"
                f"{negative_status}"
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

#!/usr/bin/env python3
"""Run the fixed-date claim fidelity acceptance pilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.eval.claim_fidelity import evaluate_registry  # noqa: E402


def _metric_line(name: str, metric: object) -> str:
    if not isinstance(metric, dict):
        return f"| {name} | pending | 0 / 0 | 0 |"
    value = metric.get("value")
    display = "pending" if value is None else f"{float(value):.2%}"
    numerator = metric.get("numerator", metric.get("passed", 0))
    denominator = metric.get("denominator", metric.get("checked", 0))
    return (
        f"| {name} | {display} | {numerator} / {denominator} "
        f"| {metric.get('pending', 0)} |"
    )


def render_markdown(summary: dict[str, object]) -> str:
    labels = {
        "numeric_match_rate": "数字一致率",
        "entity_classification_accuracy": "实体归类准确率",
        "evidence_coverage_rate": "证据覆盖率",
        "cutoff_violation_rate": "截止违规率",
        "fact_inference_confusion_rate": "事实/推断混淆率",
    }
    lines = [
        "# 10 日现状忠实度 / 历史重放验收",
        "",
        "- 结论：仅完成候选抽取与确定性审计，不自动宣布通过。",
        "- 金标准：必须由人工审定并标记 `gold_status=approved`。",
        "- 决策资格：否；Phase 2 扩量：未开放。",
        "",
        "## 五项现状忠实度指标",
        "",
        "| 指标 | 值 | 分子 / 分母 | pending |",
        "|---|---:|---:|---:|",
    ]
    metrics = summary.get("metrics")
    if isinstance(metrics, dict):
        for name, label in labels.items():
            lines.append(_metric_line(label, metrics.get(name)))
    lines.extend(
        [
            "",
            "## 逐日状态",
            "",
            "| 日期 | canonical 报告 | 状态 | claims | 版本缺口 |",
            "|---|---|---|---:|---|",
        ]
    )
    reports = summary.get("reports")
    if isinstance(reports, list):
        for report in reports:
            if not isinstance(report, dict):
                continue
            gaps = report.get("version_gap_audit")
            gap_count = (
                len(gaps.get("gaps", []))
                if isinstance(gaps, dict)
                and isinstance(gaps.get("gaps"), list)
                else 0
            )
            lines.append(
                f"| {report.get('report_date')} "
                f"| {report.get('canonical_report_path') or 'missing'} "
                f"| {report.get('status')} "
                f"| {report.get('claim_count', 0)} "
                f"| {gap_count} |"
            )
    lines.extend(
        [
            "",
            "> `pending / unverifiable / needs_review` 不能视为通过。"
            " 推荐阈值仅供用户复核，评测器不会自行启用硬门。",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--pit-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--gold-dir")
    args = parser.parse_args(argv)
    summary = evaluate_registry(
        registry_path=args.registry,
        repo_root=args.repo_root,
        pit_dir=args.pit_dir,
        out_dir=args.out_dir,
        gold_dir=args.gold_dir,
    )
    out_dir = Path(args.out_dir).expanduser()
    markdown = render_markdown(summary)
    (out_dir / "summary.md").write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "report_status_counts": summary["report_status_counts"],
                "metrics": summary["metrics"],
                "decision_eligible": False,
                "phase_2_allowed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"written: {out_dir / 'summary.json'}")
    print(f"written: {out_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

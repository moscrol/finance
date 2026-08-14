"""方案 0：compose 单调诊断脚本（只读统计，不写数据）。"""

import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "diagnose_compose_monotony",
    Path(__file__).resolve().parents[2] / "scripts" / "diagnose_compose_monotony.py",
)
diag = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(diag)


def _write_run(root: Path, name: str, *, reason: str | None, tags: str, issues=()):
    run = root / name
    run.mkdir(parents=True)
    summary = {
        "status": "fallback" if reason else "validated",
        "fallback_reason": reason,
        "stream": {"fallback_reason": reason},
    }
    (run / "trace.jsonl").write_text(
        json.dumps({"name": "answer_synthesis", "output_summary": json.dumps(summary)})
        + "\n",
        encoding="utf-8",
    )
    (run / "answer.md").write_text(tags, encoding="utf-8")
    (run / "answer_spec.json").write_text(
        json.dumps({"quality": {"passed": not issues, "issues": [{"code": c} for c in issues]}}),
        encoding="utf-8",
    )


def test_diagnose_counts_fallbacks_issues_and_overlap(tmp_path):
    _write_run(tmp_path, "run_20260701_000001_1", reason=None, tags="[D2][D4][D3]")
    _write_run(
        tmp_path, "run_20260701_000002_2",
        reason="quality_gate_rejected", tags="[D2][D4]",
        issues=("unbound_summary_claim",),
    )
    _write_run(tmp_path, "run_20260701_000003_3", reason="LLM 流式超时", tags="")

    stats = diag.diagnose([tmp_path], limit=50)
    assert stats["scanned_runs"] == 3
    assert stats["synthesis_runs"] == 3
    dist = stats["fallback_distribution"]
    assert dist["validated（无降级）"]["count"] == 1
    assert dist["quality_gate_rejected"]["count"] == 1
    assert dist["llm_timeout"]["count"] == 1
    assert stats["quality_issue_distribution"] == {"unbound_summary_claim": 1}
    d_block = stats["d_block"]
    assert d_block["runs_with_blocks"] == 2
    assert d_block["mean_pairwise_jaccard"] == round(2 / 3, 3)
    # 报告可渲染
    assert "Compose 单调专项诊断" in diag.render_report(stats)


def test_limit_takes_most_recent_runs(tmp_path):
    for i in range(5):
        _write_run(tmp_path, f"run_2026070{i}_000000_{i}", reason=None, tags="")
    stats = diag.diagnose([tmp_path], limit=2)
    assert stats["scanned_runs"] == 2

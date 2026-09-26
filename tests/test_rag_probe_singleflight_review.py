"""Keep the single-flight comparison bounded and its output non-destructive."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from intelligence.services.kb_rag import RagCliProbe
from scripts.review_probes import check_rag_probe_singleflight as review


def test_burst_counts_and_reaps_real_children(tmp_path):
    def probe(_wiki):
        result = subprocess.run([sys.executable, "-c", "pass"], timeout=5)
        return RagCliProbe(True, result.returncode == 0)

    row = review.burst(probe, tmp_path, 3)
    assert row["child_count"] == 3
    assert row["concurrency"] == 3
    assert row["all_children_reaped"]
    assert len(row["probes"]) == 3
    assert row["wall_ms"] >= 0


def test_summary_retains_counts_and_observed_range():
    assert review.summarize([
        {"wall_ms": 20.0, "child_count": 1},
        {"wall_ms": 10.0, "child_count": 2},
    ]) == {"n": 2, "min_ms": 10.0, "median_ms": 15.0, "max_ms": 20.0, "child_counts": [1, 2]}


@pytest.mark.parametrize("invalid", ["existing", "inside_source", "samples", "concurrency"])
def test_invalid_output_or_budget_cannot_start_experiment(tmp_path, monkeypatch, invalid):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "evidence"
    if invalid == "existing":
        output.mkdir()
        (output / "receipt.json").write_text("original\n")
    if invalid == "inside_source":
        output = source / "evidence"
    argv = [
        str(Path(review.__file__)), "--baseline-revision", "HEAD", "--kb-code-root", str(source),
        "--python", sys.executable, "--output-dir", str(output),
    ]
    if invalid == "samples":
        argv.extend(["--samples", "31"])
    if invalid == "concurrency":
        argv.extend(["--concurrency", "17"])
    monkeypatch.setattr(sys, "argv", argv)
    def unexpected(_revision):
        pytest.fail("invalid arguments must not execute baseline code")
    monkeypatch.setattr(review, "load_baseline", unexpected)
    with pytest.raises(SystemExit) as exc:
        review.main()
    assert exc.value.code == 2
    if invalid == "existing":
        assert (output / "receipt.json").read_text() == "original\n"
    else:
        assert not output.exists()

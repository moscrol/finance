"""夜跑接线：封存捕获在就补名，不在就 skip；不联网、不读凭证、不写库。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from market_feature_store.consumption_registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-09-29"


@pytest.fixture
def review(monkeypatch, tmp_path):
    path = ROOT / "skills/daily-full-review/scripts/run_review_sync.py"
    spec = importlib.util.spec_from_file_location("review_attach_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "QUOTE_CAPTURE_ROOT", tmp_path / "tencent")
    return module


def test_attach_runs_after_bridge_and_before_any_name_based_step(review):
    names = [name for name, _ in review.build_plan(DAY, 1, 1, "local")]
    at = names.index("attach-capture-names")
    assert names.index("stock-daily") < at < names.index("limit-stats-local")
    assert at < names.index("features")
    for plan in ("full", "cheap"):
        assert "attach-capture-names" not in [n for n, _ in review.build_plan(DAY, 1, 1, plan)]


def test_registry_lists_the_step_in_the_same_position(review):
    assert list(load_registry().plans["local"]) == review.plan_step_names()["local"]


def test_missing_capture_is_an_explicit_skip_without_subprocess(review, monkeypatch):
    monkeypatch.setattr(review, "run_step", lambda *a, **k: pytest.fail("must not spawn"))
    result = dict(review.build_plan(DAY, 7, 9, "local"))["attach-capture-names"]()
    assert result["status"] == "skip"
    assert "no sealed capture" in result["note"]


def test_existing_capture_invokes_attach_with_a_fresh_receipt(review, monkeypatch):
    capture = review.QUOTE_CAPTURE_ROOT / DAY
    capture.mkdir(parents=True)
    (capture / "receipt.json").write_text("{}")
    calls = []

    def fake_run(label, argv, timeout, **kwargs):
        calls.append((label, argv, timeout))
        return {"label": label, "status": "ok", "code": 0, "elapsed": 0.0}

    monkeypatch.setattr(review, "run_step", fake_run)
    step = dict(review.build_plan(DAY, 7, 9, "local"))["attach-capture-names"]
    assert step()["status"] == "ok"
    assert step()["status"] == "ok"
    (label, argv, timeout), (_, argv2, _) = calls
    assert label == "attach-capture-names" and timeout == 7
    assert argv[1] == "skills/duckdb-backfill/scripts/attach_capture_names.py"
    assert argv[argv.index("--trade-date") + 1] == DAY
    assert argv[argv.index("--capture-dir") + 1] == str(capture)
    assert "--refresh-stale-names" in argv  # 合同 1 扩展：过时名更正随补名一起跑（2026-09-29 夜用户同意）
    receipt = argv[argv.index("--receipt") + 1]
    assert receipt != argv2[argv2.index("--receipt") + 1]  # 收据只新建
    assert not Path(receipt).exists()
    assert Path(receipt).parent.is_dir()

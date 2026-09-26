"""Policy evaluation must reject missing, noisy, or falsely reassuring evidence."""
import json
import subprocess

import pytest

from scripts.review_probes import check_loopback_sandbox as probe


@pytest.mark.parametrize("data,code,accepted", [
    ({key: True for key in probe.KEYS}, 0, True),
    ({key: True for key in probe.KEYS}, 1, False),
    ({key: key != "external_denied" for key in probe.KEYS}, 0, False),
    ({key: 1 for key in probe.KEYS}, 0, False),
    ({}, 0, False),
    ([True, True, True], 0, False),
])
def test_requires_exact_true_observations_and_zero_exit(monkeypatch, data, code, accepted):
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(
        [], code, json.dumps(data), ""))
    assert probe.run_probe()["accepted"] is accepted


def test_invalid_output_is_not_sandbox_success(monkeypatch):
    monkeypatch.setattr(probe.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(
        [], 0, "setup failed", ""))
    assert not probe.run_probe()["accepted"]


@pytest.mark.parametrize("error", [FileNotFoundError("sandbox missing"), subprocess.TimeoutExpired([], 15)])
def test_missing_sandbox_or_timeout_fails_closed(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(probe.subprocess, "run", fail)
    result = probe.run_probe()
    assert result["accepted"] is False
    assert "error" in result

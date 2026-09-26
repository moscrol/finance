"""Offline readiness contract tests; fixtures never load weights or call a model."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.review_probes import prepare_adaptive_l6 as preparation


def fixture_library(tmp_path, source):
    kb = tmp_path / "kb"
    library = kb / "skills/lib/rag"
    library.mkdir(parents=True)
    (library / "__init__.py").write_text("")
    (library / "embedder.py").write_text(source)
    model = tmp_path / "model"
    model.mkdir()
    (model / "model.safetensors").write_text("fixture, not real weights")
    output = tmp_path / "output"
    output.mkdir()
    return kb, model, output


@pytest.mark.parametrize("shape,expected", [("(1, 1024)", True), ("(1, 512)", False)])
def test_real_worker_requires_expected_shape_without_creating_cache(tmp_path, shape, expected):
    kb, model, output = fixture_library(tmp_path, f'''
class Encoder:
    def encode(self, texts):
        class Vector:
            shape = {shape}
        return Vector()
def get_embedder(name):
    assert name == "bge-m3"
    return Encoder()
''')
    result = preparation.retrieval_probe(Path(sys.executable), kb, model, output)
    assert result["ready"] is expected
    assert result["exit_code"] == (0 if expected else 1)
    assert result["timeout_seconds"] == 120
    assert result["last_event"]["event"] == "complete"
    assert [event["event"] for event in result["events"]] == [
        "started", "import_started", "import_complete", "load_started", "load_complete", "encode_started", "complete",
    ]
    assert not list(kb.rglob("*.pyc"))
    assert not (output / "pycache").exists()
    with pytest.raises(FileExistsError):
        preparation.retrieval_probe(Path(sys.executable), kb, model, output)


def test_import_failure_is_visible_before_any_model_load(tmp_path):
    kb, model, output = fixture_library(tmp_path, "raise RuntimeError('fixture import failure')\n")
    result = preparation.retrieval_probe(Path(sys.executable), kb, model, output)
    assert result["ready"] is False
    assert result["exit_code"] == 1
    assert result["last_event"]["event"] == "failed"
    assert result["last_event"]["error_type"] == "RuntimeError"
    assert [event["event"] for event in result["events"]] == ["started", "import_started", "failed"]


@pytest.mark.parametrize("events", [
    [], [{"event": "complete", "ready": False, "shape": [1, 512]}],
    [{"event": "complete", "ready": True}],
    [{"event": "complete", "ready": True, "shape": [1, 1024]}] * 2,
    [{"event": "complete", "ready": True, "shape": [1, 1024]}, {"event": "failed"}],
])
def test_exit_zero_without_a_valid_final_result_is_not_ready(tmp_path, monkeypatch, events):
    kb, model, output = fixture_library(tmp_path, "")

    def run(command, **kwargs):
        kwargs["stdout"].write(("noise\n" + "\n".join(json.dumps(event) for event in events)).encode())
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(preparation.subprocess, "run", run)
    result = preparation.retrieval_probe(Path(sys.executable), kb, model, output)
    assert result["ready"] is False
    assert result["exit_code"] == 0


def test_timeout_preserves_last_phase_and_does_not_retry(tmp_path, monkeypatch):
    kb, model, output = fixture_library(tmp_path, "")
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        assert kwargs["timeout"] == 120
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        assert kwargs["env"]["TRANSFORMERS_OFFLINE"] == "1"
        assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
        assert "PYTHONPYCACHEPREFIX" not in kwargs["env"]
        kwargs["stdout"].write(b'{"event":"load_started","elapsed_seconds":1.0}\nTimeout (0:00:30)!\n')
        raise subprocess.TimeoutExpired(command, 120)

    monkeypatch.setattr(preparation.subprocess, "run", run)
    result = preparation.retrieval_probe(Path(sys.executable), kb, model, output)
    assert len(commands) == 1
    assert result["ready"] is False and result["exit_code"] == 124
    assert result["last_event"]["event"] == "load_started"
    assert "Timeout (0:00:30)!" in (output / "retrieval-probe.log").read_text()

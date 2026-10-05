"""The offline replay must bind drafts, anchors and code, not silently invent inputs."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from intelligence.eval.grounded_replay import answer_spec_from_payload
from intelligence.services import answer_model
from intelligence.tests.test_grounded_anchor_dates import _atom, _spec
from scripts.review_probes import replay_grounded_validation as probe


@pytest.fixture
def frozen_run(tmp_path):
    run = tmp_path / "run_test"
    run.mkdir()
    base = _spec()
    spec = replace(base, research_spec=replace(
        base.research_spec, definition="市场复盘", company_scope="不涉及公司",
    ))
    raw = (
        "全市场成交额 14377.22 亿元。"
        f"<!-- claim_ids=base:gap:1; evidence_atom_ids={_atom(spec, 'base:fact:3')}; "
        "claim_type=inference -->"
    )
    for name, payload in {
        "run.json": {"run_id": "run_test", "question": "2026-07-22 市场怎么样"},
        "answer_spec.json": spec.to_dict(),
        "grounded_composer_shadow.json": {"raw_answer": raw},
    }.items():
        (run / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return run


def test_replay_binds_original_bytes_and_retains_cited_conclusion(frozen_run):
    before = {name: (frozen_run / name).read_bytes() for name in probe.INPUTS}

    row = probe._replay_run(frozen_run, answer_model, answer_spec_from_payload)

    assert row["errors"] == []
    assert "claim_ids=base:gap:1,base:fact:3;" in row["canonical_answer"]
    assert row["raw_chars"] == row["repaired_chars"]
    assert row["repaired_body"] == "全市场成交额 14377.22 亿元。"
    assert row["question"] == "2026-07-22 市场怎么样"
    assert row["input_sha256"] == {
        name: hashlib.sha256(data).hexdigest() for name, data in before.items()
    }
    assert before == {name: (frozen_run / name).read_bytes() for name in probe.INPUTS}


@pytest.mark.parametrize("filename,field", [
    ("run.json", "question"), ("grounded_composer_shadow.json", "raw_answer"),
])
@pytest.mark.parametrize("bad_value", [None, "", " "])
def test_replay_rejects_missing_draft_or_question(frozen_run, filename, field, bad_value):
    path = frozen_run / filename
    payload = json.loads(path.read_text())
    payload[field] = bad_value
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        probe._replay_run(frozen_run, answer_model, answer_spec_from_payload)


@pytest.mark.parametrize("empty_scope", [None, "", " "])
def test_replay_records_empty_scope_normalization(frozen_run, empty_scope):
    path = frozen_run / "answer_spec.json"
    payload = json.loads(path.read_text())
    payload["research_spec"]["company_scope"] = empty_scope
    path.write_text(json.dumps(payload))
    row = probe._replay_run(frozen_run, answer_model, answer_spec_from_payload)
    assert row["normalizations"] == ["research_spec.company_scope:empty->dash"]
    assert json.loads(path.read_text())["research_spec"]["company_scope"] == empty_scope


def test_replay_rejects_inputs_changed_during_validation(frozen_run):
    def changing_decoder(payload):
        (frozen_run / "run.json").write_text("{}")
        return answer_spec_from_payload(payload)

    with pytest.raises(RuntimeError, match="input_changed_during_replay"):
        probe._replay_run(frozen_run, answer_model, changing_decoder)


def _args(frozen_run, output):
    return ["--code-root", str(Path(__file__).resolve().parents[1]),
            "--expect-revision", "tested-sha", "--run-dir", str(frozen_run),
            "--output", str(output)]


def test_main_never_overwrites_a_report(frozen_run, tmp_path):
    output = tmp_path / "report.json"
    output.write_text("original evidence")
    assert probe.main(_args(frozen_run, output)) == 2
    assert output.read_text() == "original evidence"


@pytest.mark.parametrize("identity", [
    {"status": " M source.py", "revision": "tested-sha"},
    {"status": "", "revision": "wrong-sha"},
])
def test_main_refuses_dirty_or_wrong_target(frozen_run, tmp_path, monkeypatch, identity):
    output = tmp_path / "report.json"
    monkeypatch.setattr(probe, "_identity", lambda _root: identity)
    assert probe.main(_args(frozen_run, output)) == 2
    assert not output.exists()


def test_main_detects_target_change(frozen_run, tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    identities = iter([{"status": "", "revision": "tested-sha"},
                       {"status": "", "revision": "changed-sha"}])
    monkeypatch.setattr(probe, "_identity", lambda _root: next(identities))
    assert probe.main(_args(frozen_run, output)) == 2
    assert not output.exists()


def test_main_reports_replay_not_quality_acceptance(frozen_run, tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    monkeypatch.setattr(probe, "_identity", lambda _root: {"status": "", "revision": "tested-sha"})
    assert probe.main(_args(frozen_run, output)) == 0
    report = json.loads(output.read_text())
    assert report["status"] == "replayed_not_quality_acceptance"
    assert report["model_calls"] == 0
    assert report["before"] == report["after"]
    assert len(report["rows"]) == 1

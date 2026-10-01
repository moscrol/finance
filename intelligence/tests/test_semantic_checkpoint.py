"""Checkpoint assembly must preserve evidence and never fake structural approval."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from intelligence.services import llm_refine
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.provider_observability import ProviderTrace
from intelligence.tests.test_episode_semantic_verifier import _structural
from scripts.review_probes.semantic_checkpoint import restore_checkpoint, verify_checkpoint


def archive(tmp_path):
    frame, structural = _structural("截至最新交易日，成交额缩量。")
    evidence = replace(structural.outcome.evidence[0], internal_locator="local-fixture:row-1")
    trace = ProviderTrace(provider="local-fixture", capability="market_data", status="success",
                          requested_time_range=("2026-07-21", "2026-07-22"))
    structural = verify_episode_outcome(structural.contract, replace(
        structural.outcome, evidence=(evidence,), traces=(trace,),
    ))
    raw = structural.outcome.to_dict()
    raw['evidence'][0]['internal_locator'] = evidence.internal_locator
    value = {'task_frame': frame.to_dict(), 'contract': structural.contract.to_dict(),
             'outcome': raw, 'structural_verifier': structural.to_dict()}
    path = tmp_path / 'frozen.json'
    path.write_text(json.dumps(value, ensure_ascii=False))
    return path, value


def test_roundtrip_keeps_time_window_and_private_provenance(tmp_path):
    path, _ = archive(tmp_path)
    _, restored = restore_checkpoint(path)
    assert restored.outcome.traces[0].requested_time_range == ('2026-07-21', '2026-07-22')
    assert restored.outcome.evidence[0].internal_locator == 'local-fixture:row-1'


def test_off_probe_never_calls_model_or_changes_source(tmp_path, monkeypatch):
    monkeypatch.setenv('ASK_SEMANTIC_JUDGE', 'off')
    def forbidden():
        pytest.fail('off checkpoint attempted a model provider')
    monkeypatch.setattr(llm_refine, 'judge_provider_chain', forbidden)
    path, _ = archive(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    original = verify_checkpoint(path, timeout=5)
    variant = verify_checkpoint(path, draft='成交额缩量，原因尚未核验。', timeout=5)
    assert original.judge_mode == variant.judge_mode == 'deterministic'
    assert original.judge_status == 'passed'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('mutation', ['hash', 'plan', 'claims', 'evidence_field', 'old_status'])
def test_bad_archive_fails_closed_before_review(tmp_path, mutation):
    path, original = archive(tmp_path)
    value = deepcopy(original)
    if mutation == 'hash':
        value['outcome']['task_frame_hash'] = 'wrong'
    elif mutation == 'plan':
        value['outcome']['plan'] = {'anything': 'unsupported'}
    elif mutation == 'claims':
        value['outcome']['bindings'][0]['claims'] = [{'unsupported': True}]
    elif mutation == 'evidence_field':
        value['outcome']['evidence'][0]['unknown_provenance'] = 'must-not-drop'
    else:
        value['structural_verifier']['verified_status'] = 'failed'
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        restore_checkpoint(path)

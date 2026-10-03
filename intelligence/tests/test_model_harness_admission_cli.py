"""实验入口必须重算模型准入，不能相信 JSONL 里自报的 exit 0。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from intelligence.eval.model_harness_2x2 import PLAN_SCHEMA


@pytest.fixture
def cli():
    path = Path(__file__).resolve().parents[2] / 'scripts/model_harness_2x2.py'
    spec = importlib.util.spec_from_file_location('two_by_two_cli', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inputs(tmp_path, model='glm-5.3-flash', *, artifacts=True):
    artifact = tmp_path / 'continuous-episode.json'
    artifact.write_text(json.dumps({'events': [{'kind': 'model_turn', 'payload': {'served_model': model}}]}))
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps({'schema': PLAN_SCHEMA, 'questions': ['D1'], 'unseen': ['D1'],
                               'reps': 1, 'models': {'G': 'glm-5.3-flash', 'C': 'claude-test'}}))
    run = {'seq': 1, 'question': 'D1', 'cell': 'PG', 'score': 1, 'admission_exit': 0}
    if artifacts:
        run['artifacts'] = [artifact.name]
    runs = tmp_path / 'runs.jsonl'
    runs.write_text(json.dumps(run) + '\n')
    return artifact, plan, runs


@pytest.mark.parametrize("legacy_scalar", [False, True])
def test_cli_rechecks_claimed_success_against_artifact(cli, tmp_path, capsys, legacy_scalar):
    _, plan, runs = _inputs(tmp_path, model='wrong-model')
    if legacy_scalar:
        row = json.loads(runs.read_text())
        row['artifact'] = row.pop('artifacts')[0]
        runs.write_text(json.dumps(row))
    assert cli.main(['analyze', str(runs), '--plan', str(plan), '--json']) == 1
    report = json.loads(capsys.readouterr().out)
    assert report['admission'][0]['exit_code'] == 1
    assert report['admission'][0]['claimed_exit'] == 0


def test_cli_no_artifacts_cannot_be_admitted(cli, tmp_path, capsys):
    _, plan, runs = _inputs(tmp_path, artifacts=False)
    assert cli.main(['analyze', str(runs), '--plan', str(plan), '--json']) == 2
    assert json.loads(capsys.readouterr().out)['admission'][0]['exit_code'] == 2


def test_cli_requires_frozen_expected_models(cli, tmp_path, capsys):
    _, _, runs = _inputs(tmp_path)
    assert cli.main(['analyze', str(runs), '--json']) == 2
    assert '--plan' in capsys.readouterr().err


def test_cli_matching_artifact_is_attested_with_hash(cli, tmp_path, capsys):
    artifact, plan, runs = _inputs(tmp_path)
    assert cli.main(['analyze', str(runs), '--plan', str(plan), '--json']) == 0
    result = json.loads(capsys.readouterr().out)['admission'][0]
    assert result['exit_code'] == 0
    assert len(result['sha256'][str(artifact)]) == 64


def test_cli_follows_wrong_child_before_accepting_score(cli, tmp_path, capsys):
    from intelligence.services.episode_store import JsonlEpisodeStore

    artifact, plan, runs = _inputs(tmp_path)
    doc = json.loads(artifact.read_text())
    doc['events'].append({'kind': 'branch_completed', 'payload': {'episode_ref': {'episode_id': 'child:1'}}})
    artifact.write_text(json.dumps(doc))
    store = tmp_path / 'store'
    directory = JsonlEpisodeStore(store).episode_dir('child:1')
    directory.mkdir(parents=True)
    (directory / 'events.jsonl').write_text(json.dumps({'kind': 'model_turn', 'payload': {'served_model': 'wrong-child'}}))
    assert cli.main(['analyze', str(runs), '--plan', str(plan), '--episode-store', str(store), '--json']) == 1
    assert json.loads(capsys.readouterr().out)['admission'][0]['exit_code'] == 1


def test_cli_missing_child_blocks_even_when_parent_matches(cli, tmp_path, capsys):
    artifact, plan, runs = _inputs(tmp_path)
    doc = json.loads(artifact.read_text())
    doc['events'].append({'kind': 'branch_completed', 'payload': {'episode_ref': {'episode_id': 'missing'}}})
    artifact.write_text(json.dumps(doc))
    assert cli.main(['analyze', str(runs), '--plan', str(plan), '--json']) == 2


def test_cli_empty_run_file_has_no_model_evidence(cli, tmp_path, capsys):
    _, plan, runs = _inputs(tmp_path)
    runs.write_text('')
    assert cli.main(['analyze', str(runs), '--plan', str(plan), '--json']) == 2


def test_cli_multiple_stores_retains_actual_child_hashes(cli, tmp_path, capsys):
    from intelligence.services.episode_store import JsonlEpisodeStore

    artifact, plan, runs = _inputs(tmp_path)
    doc = json.loads(artifact.read_text())
    stores, children = [], []
    for number in (1, 2):
        episode_id = f"child:{number}"
        doc['events'].append({'kind': 'branch_completed', 'payload': {
            'llm_calls': 1, 'served_models': ['glm-5.3-flash'],
            'episode_ref': {'episode_id': episode_id},
        }})
        store = tmp_path / f'store-{number}'
        directory = JsonlEpisodeStore(store).episode_dir(episode_id)
        directory.mkdir(parents=True)
        child = directory / 'events.jsonl'
        child.write_text(json.dumps({'kind': 'model_turn', 'payload': {
            'served_model': 'wrong-child' if number == 2 else 'glm-5.3-flash',
        }}))
        stores.extend(['--episode-store', str(store)])
        children.append(child)
    artifact.write_text(json.dumps(doc))
    assert cli.main(['analyze', str(runs), '--plan', str(plan), *stores, '--json']) == 1
    receipt = json.loads(capsys.readouterr().out)['admission'][0]
    assert set(receipt['sha256']) == {str(path) for path in [artifact, *children]}
    assert len(receipt['results']) == 3

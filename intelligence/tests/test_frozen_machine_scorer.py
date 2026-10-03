from __future__ import annotations

import hashlib
from importlib.util import MAGIC_NUMBER
import marshal
from pathlib import Path

import pytest

from intelligence.eval import frozen_machine_scorer as scorer


def fixture_artifact(tmp_path, monkeypatch, source=None, payload=None, magic=None):
    if source is None:
        source = "def score_case(case, answer):\n return {'answer': answer, 'case': case}\n"
    raw = payload if payload is not None else marshal.dumps(compile(source, '<test-scorer>', 'exec'))
    data = (magic or MAGIC_NUMBER) + bytes(12) + raw
    path = tmp_path / 'fixture.pyc'
    path.write_bytes(data)
    monkeypatch.setattr(scorer, 'PINNED_SHA256', hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(scorer, 'PINNED_MAGIC', MAGIC_NUMBER)
    return path


def test_pin_is_the_previously_recorded_artifact_not_caller_selected():
    assert scorer.PINNED_SHA256 == '195ad5598432e64f9be8a0a60025f8a14d7e2df5b246ecdd2f82c9a21366ac88'
    assert scorer.PINNED_MAGIC.hex() == 'cb0d0d0a'


@pytest.mark.parametrize('data', [b'', b'untrusted bytecode', bytes(20)])
def test_unrecognized_artifact_is_rejected_before_execution(tmp_path, data):
    p = tmp_path / 'bad.pyc'
    p.write_bytes(data)
    with pytest.raises(ValueError, match='digest mismatch'):
        scorer.score_pinned_case(p, {}, '')


def test_missing_file_is_not_silently_an_empty_score(tmp_path):
    with pytest.raises(FileNotFoundError):
        scorer.score_pinned_case(tmp_path / 'absent.pyc', {}, '')


@pytest.mark.parametrize('case,answer', [([], ''), ({}, None), ({}, 1)])
def test_input_types_are_checked_before_loading(tmp_path, case, answer):
    with pytest.raises(TypeError):
        scorer.score_pinned_case(tmp_path / 'absent.pyc', case, answer)


def test_wrong_runtime_magic_is_rejected(tmp_path, monkeypatch):
    path = fixture_artifact(tmp_path, monkeypatch)
    monkeypatch.setattr(scorer, 'MAGIC_NUMBER', b'nope')
    with pytest.raises(ValueError, match='magic'):
        scorer.score_pinned_case(path, {}, '')


def test_wrong_artifact_magic_is_rejected_even_if_digest_matches(tmp_path, monkeypatch):
    path = fixture_artifact(tmp_path, monkeypatch, magic=b'nope')
    with pytest.raises(ValueError, match='magic'):
        scorer.score_pinned_case(path, {}, '')


def test_non_code_payload_rejected(tmp_path, monkeypatch):
    path = fixture_artifact(tmp_path, monkeypatch, payload=marshal.dumps({'not': 'code'}))
    with pytest.raises(TypeError, match='code object'):
        scorer.score_pinned_case(path, {}, '')


@pytest.mark.parametrize('source', ['score_case = None', 'score_case = 42'])
def test_missing_callable_rejected(tmp_path, monkeypatch, source):
    path = fixture_artifact(tmp_path, monkeypatch, source=source)
    with pytest.raises(TypeError, match='callable'):
        scorer.score_pinned_case(path, {}, '')


def test_result_not_recalculated_and_advisory_retained(tmp_path, monkeypatch):
    source = """
def score_case(case, answer):
 return {'rate': 0.5, 'passed': 1, 'total': 2,
         'checks': [{'ok': True}, {'ok': False}, {'ok': False, 'advisory': True}]}
if __name__ == '__main__':
 raise AssertionError('legacy runner must never execute')
"""
    path = fixture_artifact(tmp_path, monkeypatch, source=source)
    result = scorer.score_pinned_case(path, {}, 'not scored by new rules')
    assert result['score'] == {
        'rate': 0.5, 'passed': 1, 'total': 2,
        'checks': [{'ok': True}, {'ok': False}, {'ok': False, 'advisory': True}],
    }
    assert result['scorer_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result['python_magic'] == MAGIC_NUMBER.hex()
    assert result['mode'] == 'temporary_frozen_bytecode'
    assert result['source_restored'] is False


def test_legacy_failure_is_not_converted_to_a_score(tmp_path, monkeypatch):
    path = fixture_artifact(tmp_path, monkeypatch, source="def score_case(case, answer):\n raise RuntimeError('legacy failed')\n")
    with pytest.raises(RuntimeError, match='legacy failed'):
        scorer.score_pinned_case(path, {}, '')


def test_non_dictionary_result_rejected(tmp_path, monkeypatch):
    path = fixture_artifact(tmp_path, monkeypatch, source="def score_case(case, answer):\n return 1\n")
    with pytest.raises(TypeError, match='dictionary'):
        scorer.score_pinned_case(path, {}, '')


def test_case_mutation_cannot_modify_caller_truth(tmp_path, monkeypatch):
    path = fixture_artifact(tmp_path, monkeypatch, source="def score_case(case, answer):\n case['nested'].clear()\n return case\n")
    case = {'nested': {'fact': 1}}
    assert scorer.score_pinned_case(path, case, '')['score'] == {'nested': {}}
    assert case == {'nested': {'fact': 1}}


def test_same_bytes_are_executed_after_single_read(tmp_path, monkeypatch):
    path = fixture_artifact(tmp_path, monkeypatch)
    original_read = Path.read_bytes
    reads = []
    def read_once(p):
        data = original_read(p)
        reads.append(p)
        p.write_bytes(b'changed after read')
        return data
    monkeypatch.setattr(Path, 'read_bytes', read_once)
    result = scorer.score_pinned_case(path, {'id': 'fixture'}, 'answer')
    assert result['score'] == {'case': {'id': 'fixture'}, 'answer': 'answer'}
    assert reads == [path]


def test_well_formed_but_unpinned_code_never_executes(tmp_path):
    marker = tmp_path / 'must-not-exist'
    source = f"from pathlib import Path\nPath({str(marker)!r}).touch()\ndef score_case(case, answer):\n return {{}}\n"
    data = MAGIC_NUMBER + bytes(12) + marshal.dumps(compile(source, '<untrusted>', 'exec'))
    path = tmp_path / 'well-formed-untrusted.pyc'
    path.write_bytes(data)
    with pytest.raises(ValueError, match='digest mismatch'):
        scorer.score_pinned_case(path, {}, '')
    assert not marker.exists()


def load_cli():
    import importlib.util
    spec = importlib.util.spec_from_file_location('frozen_score_cli', Path(__file__).resolve().parents[2] / 'scripts/score_frozen_machine_case.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    return cli


def test_cli_preserves_score_but_never_claims_semantic_acceptance(tmp_path, monkeypatch):
    import json
    cli = load_cli()
    case = tmp_path / 'case.json'
    case.write_text('{"id":"fixture"}')
    answer = tmp_path / 'answer.txt'
    answer.write_text('fixture answer')
    output = tmp_path / 'score.json'
    calls = []
    def score(path, case, answer):
        calls.append((path, case, answer))
        return {'score': {'rate': 1.0}, 'source_restored': False}
    monkeypatch.setattr(cli, 'score_pinned_case', score)
    args = ['--scorer', str(tmp_path / 'fixture.pyc'), '--case-json', str(case),
            '--answer-file', str(answer), '--output', str(output)]
    assert cli.main(args) == 0
    data = json.loads(output.read_text())
    assert data['status'] == 'scored' and data['semantic_acceptance'] == 'not_established'
    assert data['result']['score']['rate'] == 1.0
    assert data['case_sha256'] == hashlib.sha256(case.read_bytes()).hexdigest()
    assert data['answer_sha256'] == hashlib.sha256(answer.read_bytes()).hexdigest()
    assert calls == [(tmp_path / 'fixture.pyc', {'id': 'fixture'}, 'fixture answer')]
    with pytest.raises(FileExistsError):
        cli.main(args)
    assert len(calls) == 1


def test_cli_records_error_not_zero_score(tmp_path):
    import json
    cli = load_cli()
    output = tmp_path / 'error.json'
    rc = cli.main(['--scorer', str(tmp_path / 'absent.pyc'), '--case-json', str(tmp_path / 'absent.json'),
                   '--answer-file', str(tmp_path / 'absent.txt'), '--output', str(output)])
    receipt = json.loads(output.read_text())
    assert rc == 2 and receipt['status'] == 'error'
    assert receipt['semantic_acceptance'] == 'not_established'
    assert receipt['error_type'] == 'FileNotFoundError'
    assert 'result' not in receipt

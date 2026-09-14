"""工单 #53：防止复用草稿把读取尝试/确认归属折回提交尝试，或终态引用变成写权限。

All writes use temporary users; River identity/slices are fixed local fixtures.
Run explicitly with the main tree .venv-workbench/bin/python -m pytest -q <this-file>.
On b916091e: original six counterexamples = 7 passed, residual invariants = 3 failed.
Not named test_*: these review probes deliberately expose unfixed defects, and are
not silently inserted into the default product suite. After repair all must pass.
"""
import contextlib
import io
import json
from unittest import mock

import pytest

from intelligence.services import guided_reading as gr
from intelligence.services import observation_extraction as ox
from intelligence.services import observation_script as osc
from intelligence.tests.test_observation_extraction_first import (
    Base, AS_OF, ENTITY, OTHER_ENTITY, CANON, MY_VARS, MY_ABANDON, _run,
)


@pytest.fixture
def b():
    case = Base()
    case.setUp()
    try:
        yield case
    finally:
        case.doCleanups()


def confirm(aid, *, manual=False, day=AS_OF, due=None):
    argv = ['observation', 'confirm', '--user', 'u1', '--as-of', day,
            '--db-path', '/tmp/extraction-qc-no-db.duckdb', '--json']
    if manual:
        argv += ['--scope', 'theme', '--entity', ENTITY, '--variable', MY_VARS[0],
                 '--abandon', MY_ABANDON[0]]
    else:
        argv += ['--from-draft', ENTITY]
    if aid:
        argv += ['--attempt-id', aid]
    if due:
        argv += ['--due', due]
    code, out = _run(argv)
    return code, json.loads(out) if code == 0 else out


def close(b, aid):
    return osc.close_attempt(b.ledger(), attempt_id=aid, user_id='u1',
                             reason='user_closed', entrypoint='close')


def test_old_n1_cjk_fragment(b):
    assert b.draft()[0] == 0
    previous = osc.load_raw(b.ledger())
    fragment = '{"id":"torn","note":"观察'.encode()[:-1]
    with b.ledger().open('ab') as fh:
        fh.write(fragment)
    assert osc.load_raw(b.ledger()) == previous
    new, created = osc.open_attempt(b.ledger(), key=ox.make_key('u1', '2026-09-03', CANON), entrypoint='read')
    assert created
    assert new['attempt_id'] in osc.attempt_states(osc.load_raw(b.ledger()))
    assert fragment in b.ledger().read_bytes()


def fail_close_append():
    original = osc._append_line
    def append(path, record):
        if record.get('record_kind') == osc.RECORD_ATTEMPT and record.get('status') == osc.ATTEMPT_CLOSED:
            raise OSError('independent close append failure')
        return original(path, record)
    return mock.patch.object(osc, '_append_line', side_effect=append)


def test_old_n2_retry_heals_close(b):
    b.draft()
    aid = b.pending()[0]['attempt_id']
    err = io.StringIO()
    with fail_close_append(), contextlib.redirect_stderr(err):
        assert b.read(extra=['--attempt-id', aid])[0] == 1
    assert '确实交付了' in err.getvalue()
    assert '交付结果未知' not in err.getvalue()
    assert len(b.kinds(osc.EVENT_READ_COMPLETED)) == 1
    assert len(b.pending()) == 1
    with mock.patch.object(gr, 'build', wraps=gr.build) as build:
        assert b.read(extra=['--attempt-id', aid])[0] == 0
    assert build.call_count == 0
    assert not b.pending()
    assert len(b.kinds(osc.EVENT_READ_COMPLETED)) == 1
    assert not b.kinds(osc.EVENT_ABANDONED)


def reused_sequence(b):
    b.draft()
    assert b.read()[0] == 0
    assert b.read()[0] == 0
    return b.kinds(osc.EVENT_READ_COMPLETED)


def test_old_s1_reused_version_is_confirmable(b):
    first, second = reused_sequence(b)
    code, record = confirm(second['attempt_id'])
    assert code == 0, record
    assert record['source_draft_id'] == second['source_draft_id']


def test_old_s2_wrong_manual_target_no_side_effect(b):
    b.read(entity=OTHER_ENTITY)
    aid = b.pending()[0]['attempt_id']
    code, result = confirm(aid, manual=True)
    assert code == 2, result
    assert '不属于' in result
    assert not osc.load(b.ledger())
    assert not b.space().checkpoints_path.exists()


@pytest.mark.parametrize('action', ['confirm', 'skip'])
def test_old_s3_racing_close_rejected(b, action):
    b.draft()
    close(b, b.pending()[0]['attempt_id'])
    real = osc.open_attempt
    def open_then_close(*args, **kwargs):
        attempt, created = real(*args, **kwargs)
        close(b, attempt['attempt_id'])
        return attempt, created
    argv = ['observation', action, '--user', 'u1', '--as-of', AS_OF,
            '--db-path', '/tmp/extraction-qc-no-db.duckdb']
    argv += ['--from-slice', ENTITY] if action == 'confirm' else ['--entity', ENTITY]
    with mock.patch.object(osc, 'open_attempt', side_effect=open_then_close):
        code, out = _run(argv)
    assert code == 2, out
    assert '已结束' in out
    assert not [r for r in osc.load(b.ledger()) if r['status'] in {'confirmed', 'late', 'skipped'}]
    assert not b.space().checkpoints_path.exists()


def test_old_s4_due_effect_changes_and_retry_dedups(b):
    # Force timely status, so the checkpoint side effect is actually exercised.
    with mock.patch.object(osc, 'is_late', return_value=False):
        code1, first = confirm(None, manual=True, due='2026-09-15')
        code2, second = confirm(None, manual=True, due='2026-09-16')
        code3, retry = confirm(None, manual=True, due='2026-09-16')
    assert code1 == code2 == code3 == 0
    assert first['due'] == '2026-09-15' and second['due'] == '2026-09-16'
    assert first['id'] != second['id']
    assert first['checkpoint_id'] != second['checkpoint_id']
    assert retry == second
    assert len(b.space().checkpoints_path.read_text().splitlines()) == 2


def test_residual_s1_confirmation_preserves_selected_read_attempt(b):
    first, second = reused_sequence(b)
    code, record = confirm(second['attempt_id'])
    assert code == 0, record
    assert record['source_draft_id'] == second['source_draft_id']
    assert record['extraction_attempt_id'] == second['attempt_id'], {
        'requested_attempt': second['attempt_id'], 'draft_submission_attempt': first['attempt_id'],
        'written_attempt': record['extraction_attempt_id'], 'action_event': record['action_event'],
    }
    assert record['action_event']['attempt_id'] == second['attempt_id']


def test_residual_s1_completed_receipt_wins_over_later_draft(b):
    b.draft()
    aid = b.pending()[0]['attempt_id']
    with fail_close_append():
        assert b.read(extra=['--attempt-id', aid])[0] == 1
    receipt = b.kinds(osc.EVENT_READ_COMPLETED)[0]
    # Normal draft entry finds the pending attempt and allows a new version.
    code, out = b.draft(variables=['资金轨：板块 / 题材资金流是否延续'], extra=['--json'])
    assert code == 0, out
    newer = json.loads(out)
    assert newer['draft_id'] != receipt['source_draft_id']
    assert newer['extraction_attempt_id'] == aid
    assert b.read(extra=['--attempt-id', aid])[0] == 0
    code, record = confirm(aid)
    assert code == 0, record
    assert record['source_draft_id'] == receipt['source_draft_id'], {
        'read_receipt_draft': receipt['source_draft_id'], 'confirmed_draft': record['source_draft_id'],
        'later_unread_draft': newer['draft_id'],
    }


def test_residual_s2_manual_cannot_write_to_abandoned_attempt(b):
    b.read()
    aid = b.pending()[0]['attempt_id']
    closed, event = close(b, aid)
    assert closed['abandoned'] and event
    before = b.ledger().read_bytes()
    with mock.patch.object(osc, 'is_late', return_value=False):
        code, out = confirm(aid, manual=True)
    assert code == 2, {'exit': code, 'record': out, 'closed': closed}
    assert b.ledger().read_bytes() == before
    assert not b.space().checkpoints_path.exists()

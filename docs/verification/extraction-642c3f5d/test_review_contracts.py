"""工单53第三轮复审：真实CLI的四条契约反例；仅临时users及固定本地切片。

从被审查树执行：PYTHONPATH="$PWD" <workbench-python> -m pytest -q -p no:randomly <本文件>
候选642c3f5d应为4 failed；返修应保留断言让其转绿。四项分别验证确认归属、
自动续接重放、草稿回退生效、损坏隔离后的个人导出。无模型或网络调用。
"""

import contextlib
import io
import json
from unittest import mock

from intelligence.services import observation_extraction as ox
from intelligence.tests.test_observation_extraction_first import (
    AS_OF, CANON, ENTITY, Base, _run, gr, osc,
)


class ReviewContracts(Base):
    def test_confirmation_keeps_requested_reuse_attempt(self):
        code, out = self.draft(extra=['--json'])
        self.assertEqual(code, 0)
        original = json.loads(out)
        self.assertEqual(self.read()[0], 0)
        code, out = self.read(extra=['--json'])
        self.assertEqual(code, 0)
        wanted = json.loads(out)['attempt_id']
        self.assertNotEqual(wanted, original['extraction_attempt_id'])
        code, out = _run([
            'observation', 'confirm', '--user', 'u1', '--as-of', AS_OF,
            '--from-draft', ENTITY, '--attempt-id', wanted,
            '--db-path', '/tmp/no-such.duckdb', '--json',
        ])
        self.assertEqual(code, 0)
        confirmed = json.loads(out)
        self.assertEqual(confirmed['source_draft_id'], original['draft_id'])
        self.assertEqual(confirmed['extraction_attempt_id'], wanted)
        self.assertEqual(confirmed['action_event']['attempt_id'], wanted)
        events = [e for e in self.kinds(osc.EVENT_SCRIPT_CONFIRMED) if e['attempt_id'] == wanted]
        self.assertEqual(len(events), 1)

    def test_implicit_retry_replays_receipt_without_building(self):
        self.assertEqual(self.draft()[0], 0)
        with mock.patch.object(osc, 'close_attempt', side_effect=OSError('review disk failure')):
            with contextlib.redirect_stderr(io.StringIO()):
                code, _ = self.read(extra=['--json'])
        self.assertEqual(code, 1)
        receipt = self.kinds(osc.EVENT_READ_COMPLETED)[0]
        self.assertEqual(len(self.pending()), 1)
        with mock.patch.object(gr, 'build', wraps=gr.build) as built:
            code, out = self.read(extra=['--json'])
        self.assertEqual(code, 0)
        self.assertEqual(built.call_count, 0, '自动续接同ID也必须先查已存在的完成收据')
        self.assertEqual(json.loads(out), receipt)
        self.assertEqual(self.pending(), [])
        self.assertEqual(len(self.kinds(osc.EVENT_READ_COMPLETED)), 1)

    def test_draft_a_b_a_makes_final_a_current(self):
        a = ['题材轨：题材所处阶段是否推进']
        b = ['资金轨：板块资金流是否延续']
        rows = []
        for variables in [a, b, a]:
            code, out = self.draft(variables=variables, extra=['--json'])
            self.assertEqual(code, 0)
            rows.append(json.loads(out))
        self.assertEqual(len({r['attempt_id'] for r in rows}), 1)
        self.assertTrue(rows[-1]['created'], 'A→B→A的最后提交是新版本，不是第一次A的重试')
        self.assertEqual(rows[-1]['draft_version'], 3)
        latest = osc.latest_user_draft(osc.load_raw(self.ledger()), key=ox.make_key('u1', AS_OF, CANON))
        self.assertEqual(latest['variables'], a)
        self.assertEqual(len(self.kinds(osc.EVENT_DRAFT_SUBMITTED)), 3)
        code, _ = self.read(extra=['--json'])
        self.assertEqual(code, 0)
        self.assertEqual(self.kinds(osc.EVENT_READ_COMPLETED)[0]['source_draft_id'], rows[-1]['draft_id'])

    def test_recovered_utf8_fragment_does_not_block_personal_export(self):
        self.assertEqual(self.draft()[0], 0)
        fragment = b'{"variables":["' + bytes([0xe7, 0xae])
        with self.ledger().open('ab') as stream:
            stream.write(fragment)
        self.assertEqual(self.draft(variables=['资金轨：板块资金流是否延续'])[0], 0)
        raw = osc.load_raw(self.ledger())
        self.assertEqual(len(osc.user_drafts(raw, key=ox.make_key('u1', AS_OF, CANON))), 2)
        self.assertIn(fragment, self.ledger().read_bytes())
        code, out = _run(['personal-export', '--user', 'u1', '--json'])
        self.assertEqual(code, 0)
        exported = json.loads(out)['observation_scripts']
        self.assertTrue({r['id'] for r in raw}.issubset({r.get('id') for r in exported}))
        self.assertGreater(len(exported), len(raw), '损坏行应以可逆形式留作证据，不能静默丢弃')

"""Offline path-boundary regressions; no model, pytest subprocess or candidate IO."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.review_probes import review_artifact_writer as writer


class ArtifactWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.work = self.root / 'work'
        for group in writer.GROUPS:
            (self.work / group / 'probes').mkdir(parents=True)
        self.receipt = self.work / 'e2/runs/positive_control-fixture/receipt.json'
        self.receipt.parent.mkdir(parents=True)
        self.receipt.write_text('{"exit_code":75}\n')

    def write(self, name, stage='execute', group='e2', content='reviewer draft'):
        writer.write_artifact(self.work, group, stage, self.work / group / name, content)

    def test_observed_receipt_overwrite_is_denied(self):
        before = self.receipt.read_bytes()
        with self.assertRaises(PermissionError):
            writer.write_artifact(self.work, 'e2', 'execute', self.receipt,
                                  'placeholder - will read instead\n')
        self.assertEqual(self.receipt.read_bytes(), before)

    def test_other_host_evidence_paths_are_denied(self):
        for name in ('runs/new/receipt.json', 'runs/new/stdout.log.txt',
                     'runs/new/junit.xml', 'host-execution-check.json',
                     'manifest.json', 'resource-admissions.jsonl'):
            with self.subTest(name=name), self.assertRaises(PermissionError):
                self.write(name)
        self.assertFalse((self.work / 'e2/runs/new').exists())

    def test_group_and_frozen_input_boundaries(self):
        for target in (self.work / 'timer/EXECUTE.md', self.root / 'inputs/test_reviewer.py',
                       self.root / 'candidate/source.py', self.work / 'reviewer-pytest-admissions.jsonl'):
            with self.subTest(target=target), self.assertRaises(PermissionError):
                writer.write_artifact(self.work, 'e2', 'execute', target, 'bad')

    def test_each_stage_can_write_only_its_deliverables(self):
        for stage, names in writer.ARTIFACTS.items():
            for name in names:
                self.write(name, stage)
                self.write(name, stage, content='final')
                self.assertEqual((self.work / 'e2' / name).read_text(), 'final')
            for other, other_names in writer.ARTIFACTS.items():
                if other != stage:
                    for name in other_names:
                        with self.assertRaises(PermissionError):
                            self.write(name, stage)

    def test_frozen_initial_probe_cannot_be_overwritten(self):
        self.write('probes/test_reviewer.py', 'explore', content='initial')
        for stage in ('execute', 'report'):
            with self.assertRaises(PermissionError):
                self.write('probes/test_reviewer.py', stage)
        with self.assertRaises(FileExistsError):
            self.write('probes/test_reviewer.py', 'explore')
        self.assertEqual((self.work / 'e2/probes/test_reviewer.py').read_text(), 'initial')

    def test_supplemental_probe_is_create_only(self):
        self.write('probes/test_reviewer_v2.py')
        with self.assertRaises(FileExistsError):
            self.write('probes/test_reviewer_v2.py')
        with self.assertRaises(PermissionError):
            self.write('probes/test_reviewer_v3.py', 'report')
        self.write('probes/activity-reviewer-v2.test.tsx', group='timer')
        with self.assertRaises(PermissionError):
            self.write('probes/activity-reviewer-v2.test.tsx')

    def test_inventory_and_ui_initial_are_group_scoped(self):
        self.write('transaction-review.json', 'explore', 'consent')
        self.write('probes/activity-reviewer.test.tsx', 'explore', 'timer')
        for stage, group in [('execute', 'consent'), ('explore', 'e2')]:
            with self.assertRaises(PermissionError):
                self.write('transaction-review.json', stage, group)

    def test_symlink_file_cannot_redirect_to_receipt(self):
        target = self.work / 'e2/EXECUTE.json'
        target.symlink_to(self.receipt)
        with self.assertRaises(OSError):
            self.write('EXECUTE.json')
        self.assertEqual(self.receipt.read_text(), '{"exit_code":75}\n')

    def test_symlink_parent_is_denied(self):
        probes = self.work / 'e2/probes'
        probes.rmdir()
        probes.symlink_to(self.receipt.parent, target_is_directory=True)
        with self.assertRaises(OSError):
            self.write('probes/test_reviewer_v2.py')
        self.assertFalse((self.receipt.parent / 'test_reviewer_v2.py').exists())

    def test_hardlink_cannot_truncate_receipt(self):
        os.link(self.receipt, self.work / 'e2/EXECUTE.json')
        with self.assertRaises(PermissionError):
            self.write('EXECUTE.json')
        self.assertEqual(self.receipt.read_text(), '{"exit_code":75}\n')

    def test_unknown_identity_and_traversal_fail_closed(self):
        for group, stage, target in [('unknown', 'execute', self.work / 'e2/EXECUTE.md'),
                                     ('e2', 'unknown', self.work / 'e2/EXECUTE.md'),
                                     ('e2', 'execute', self.work / 'e2/../e2/EXECUTE.md'),
                                     ('e2', 'execute', Path('EXECUTE.md'))]:
            with self.assertRaises(PermissionError):
                writer.write_artifact(self.work, group, stage, target, 'bad')

    def test_cli_real_request_rejects_receipt_and_allows_report(self):
        command = [sys.executable, '-B', writer.__file__, '--work-root', str(self.work),
                   '--group', 'e2', '--stage', 'execute']
        for target, expected in [(self.receipt, 1), (self.work / 'e2/EXECUTE.md', 0)]:
            result = subprocess.run(command, input=json.dumps({'path': str(target), 'content': 'draft'}),
                                    text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, expected, result.stderr)
        self.assertEqual(self.receipt.read_text(), '{"exit_code":75}\n')

    def test_removing_policy_reproduces_the_overwrite(self):
        with patch.object(writer, '_allowed_artifact', return_value=True):
            writer.write_artifact(self.work, 'e2', 'execute', self.receipt, 'placeholder')
        self.assertEqual(self.receipt.read_text(), 'placeholder')


if __name__ == '__main__':
    unittest.main()

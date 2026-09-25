"""Offline boundary tests; no provider requests or candidate pytest execution."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.review_probes.review_io_sandbox import (
    narrow_write_policy,
    prepare_evidence_groups,
    snapshot_child_file,
)


class ReviewIOTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.work = self.root / 'work'
        self.evidence = self.root / 'evidence'
        self.scratch = self.root / 'scratch'
        self.inputs = self.root / 'inputs'
        for directory in (self.work, self.evidence, self.scratch, self.inputs):
            directory.mkdir()
        self.receipt = self.evidence / 'receipt.json'
        self.receipt.write_text('original')
        self.profile = '\n'.join([
            '(version 1)', '(allow default)', '(deny network*)', '(deny file-write*)',
            f'(allow file-write* (subpath {json.dumps(str(self.work))}) (literal "/dev/null"))',
        ])

    def policy(self, **kwargs):
        return narrow_write_policy(self.profile, self.work, protected=(self.evidence, self.inputs), **kwargs)

    def sandbox(self, body, profile):
        if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').exists():
            self.skipTest('requires real macOS sandbox-exec')
        sb = self.root / 'test.sb'
        sb.write_text(profile)
        return subprocess.run(
            ['/usr/bin/sandbox-exec', '-f', str(sb), sys.executable, '-I', '-B', '-c', body],
            capture_output=True, text=True, timeout=15,
            env={'PATH': '/usr/bin:/bin', 'HOME': str(self.scratch), 'TMPDIR': str(self.scratch)},
        )

    def test_unexpected_write_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            narrow_write_policy(self.profile + '\n(allow file-write* (subpath "/tmp"))', self.work)

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            narrow_write_policy(self.profile.replace('(deny file-write*)', ''), self.work)

    def test_write_ancestor_of_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            self.policy(directories=(self.root,))

    def test_write_inside_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            self.policy(directories=(self.evidence / 'nested',))

    def test_literal_evidence_write_is_rejected(self):
        with self.assertRaises(ValueError):
            self.policy(files=(self.receipt,))

    def test_child_writes_only_own_scratch(self):
        targets = [self.receipt, self.inputs / 'frozen.py', self.work / 'EXECUTE.md',
                   self.root / 'other-scratch' / 'new', self.root / 'candidate.py']
        targets[3].parent.mkdir()
        body = f'''from pathlib import Path
import errno, os, socket
scratch = Path({str(self.scratch)!r})
(scratch / 'ok').write_text('ok')
for raw in {list(map(str, targets))!r}:
    try: Path(raw).write_text('corrupt')
    except PermissionError: pass
    else: raise AssertionError('write allowed: ' + raw)
for operation in [lambda: Path({str(self.receipt)!r}).unlink(),
                  lambda: os.rename({str(self.evidence)!r}, {str(self.root / 'moved')!r})]:
    try: operation()
    except PermissionError: pass
    else: raise AssertionError('evidence removal allowed')
s = socket.socket()
try: s.connect(('127.0.0.1', 9))
except OSError as e: assert e.errno in (errno.EPERM, errno.EACCES), e
else: raise AssertionError('network allowed')
finally: s.close()
'''
        result = self.sandbox(body, self.policy(directories=(self.scratch,)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.receipt.read_text(), 'original')
        self.assertEqual((self.scratch / 'ok').read_text(), 'ok')

    def test_child_cannot_link_evidence_into_scratch(self):
        body = f'''from pathlib import Path
import os
source = Path({str(self.receipt)!r})
for name, link in [('soft', os.symlink), ('hard', os.link)]:
    target = Path({str(self.scratch)!r}) / name
    try:
        link(source, target)
        target.write_text('corrupt')
    except PermissionError: pass
    else: raise AssertionError(name + ' link escaped write policy')
'''
        result = self.sandbox(body, self.policy(directories=(self.scratch,)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.receipt.read_text(), 'original')

    def test_artifact_process_cannot_write_receipts_or_other_stage(self):
        artifact = self.work / 'EXECUTE.md'
        body = f'''from pathlib import Path
Path({str(artifact)!r}).write_text('delivered')
for raw in {[str(self.receipt), str(self.work / 'FINAL.md'), str(self.scratch / 'new')]!r}:
    try: Path(raw).write_text('corrupt')
    except PermissionError: pass
    else: raise AssertionError('write allowed: ' + raw)
'''
        result = self.sandbox(body, self.policy(files=(artifact,)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(artifact.read_text(), 'delivered')
        self.assertEqual(self.receipt.read_text(), 'original')

    def test_prepared_group_parents_reach_permission_check(self):
        evidence = self.root / 'fresh-evidence'
        groups = prepare_evidence_groups(evidence)
        self.assertEqual({group.name for group in groups}, {'controller-v3', 'e2', 'timer', 'consent'})
        body = f'''from pathlib import Path
for raw in {list(map(str, groups))!r}:
    parent = Path(raw)
    assert parent.is_dir()
    try: (parent / 'counterfeit.json').write_text('corrupt')
    except PermissionError: pass
    else: raise AssertionError('protected evidence writable')
'''
        result = self.sandbox(body, self.policy(directories=(self.scratch,)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all(not list(group.iterdir()) for group in groups))
        (evidence / 'e2').rmdir()
        mutation = self.sandbox(body.replace('    assert parent.is_dir()\n', ''), self.policy(directories=(self.scratch,)))
        self.assertNotEqual(mutation.returncode, 0)
        self.assertIn('FileNotFoundError', mutation.stderr)

    def test_evidence_preparation_never_reuses_existing_tree(self):
        with self.assertRaises(FileExistsError):
            prepare_evidence_groups(self.evidence)
        self.assertEqual(self.receipt.read_text(), 'original')
        self.assertEqual(list(self.evidence.iterdir()), [self.receipt])

    def test_evidence_preparation_rejects_symlink_parent(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.scratch, target_is_directory=True)
        with self.assertRaises(ValueError):
            prepare_evidence_groups(alias / 'evidence')
        self.assertFalse((self.scratch / 'evidence').exists())

    def test_snapshot_regular_file_once(self):
        source, target = self.scratch / 'junit.xml', self.evidence / 'junit.xml'
        source.write_text('<testsuites/>')
        snapshot_child_file(source, target)
        self.assertEqual(source.read_bytes(), target.read_bytes())
        with self.assertRaises(FileExistsError):
            snapshot_child_file(source, target)

    def test_snapshot_rejects_symlink_hardlink_fifo_and_large_file(self):
        soft, hard, fifo, large = [self.scratch / name for name in ('soft', 'hard', 'fifo', 'large')]
        soft.symlink_to(self.receipt)
        os.link(self.receipt, hard)
        os.mkfifo(fifo)
        large.write_text('too large')
        for source in (soft, hard, fifo, large):
            with self.subTest(source=source), self.assertRaises((OSError, ValueError)):
                snapshot_child_file(source, self.evidence / 'not-created', max_bytes=2)
        self.assertFalse((self.evidence / 'not-created').exists())

    def test_snapshot_rejects_symlink_parent(self):
        alias = self.scratch / 'parent'
        alias.symlink_to(self.evidence, target_is_directory=True)
        with self.assertRaises(OSError):
            snapshot_child_file(alias / self.receipt.name, self.evidence / 'not-created')
        self.assertFalse((self.evidence / 'not-created').exists())

    def test_without_os_restriction_receipt_overwrite_is_observable(self):
        result = subprocess.run(
            [sys.executable, '-I', '-c', f'from pathlib import Path; Path({str(self.receipt)!r}).write_text("corrupt")'],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.receipt.read_text(), 'corrupt')


if __name__ == '__main__':
    unittest.main()

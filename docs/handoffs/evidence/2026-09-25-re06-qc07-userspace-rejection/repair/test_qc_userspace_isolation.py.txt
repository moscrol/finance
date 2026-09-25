"""Exercise the deployed plugin import with stdlib subprocesses, not pytest."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


TREE = Path(__file__).resolve().parents[1]
PLUGIN = TREE / 'scripts/review_probes/qc_userspace_isolation.py'


class QCUserspaceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.plugin = self.root / 'inputs/qc_userspace_isolation.py'
        self.plugin.parent.mkdir()
        shutil.copyfile(PLUGIN, self.plugin)
        self.scratch = self.root / 'scratch/e2/reviewer-123'
        self.scratch.mkdir(parents=True)
        self.target = self.scratch / 'users'
        self.env = {
            'PATH': '/usr/bin:/bin', 'HOME': str(self.scratch),
            'REVIEW_SCRATCH': str(self.scratch),
            'QC_ISOLATED_USERS_DIR': str(self.target),
            'FORESIGHT_USERS_DIR': str(self.target),
        }

    def execute(self, env=None, expect_denial=False):
        code = f'''import os, runpy, sys
from pathlib import Path
sys.path.insert(0, {str(TREE)!r})
from intelligence import userspace
original = userspace.USERS_DIR
if {expect_denial!r}:
    try: runpy.run_path({str(self.plugin)!r})
    except (PermissionError, KeyError): pass
    else: raise AssertionError('unsafe userspace accepted')
    assert userspace.USERS_DIR == original
    assert Path({str(self.target)!r}).exists() == {self.target.exists()!r}
else:
    runpy.run_path({str(self.plugin)!r})
    target = Path(os.environ['QC_ISOLATED_USERS_DIR'])
    assert userspace.users_dir() == target
    assert userspace.user_space('reviewer').root == target / 'reviewer'
    del os.environ['FORESIGHT_USERS_DIR']
    assert userspace.users_dir() == target
    assert userspace.user_space('default').root == target / 'default'
    assert target.is_dir()
print('plugin import and consumer paths checked')
'''
        result = subprocess.run(
            [sys.executable, '-I', '-B', '-c', code], env=env or self.env,
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_current_scratch_explicit_and_cleared_environment_fallback(self):
        self.execute()

    def test_all_owners_use_the_same_contract(self):
        for group in ('controller-v3', 'timer', 'consent'):
            with self.subTest(group=group):
                scratch = self.root / 'scratch' / group / 'probe-123'
                scratch.mkdir(parents=True)
                self.execute({**self.env, 'REVIEW_SCRATCH': str(scratch),
                              'QC_ISOLATED_USERS_DIR': str(scratch / 'users'),
                              'FORESIGHT_USERS_DIR': str(scratch / 'users')})

    def test_old_work_root_rejected(self):
        old = self.root / 'work/e2/runs/probe-123'
        old.mkdir(parents=True)
        self.execute({**self.env, 'REVIEW_SCRATCH': str(old),
                      'QC_ISOLATED_USERS_DIR': str(old / 'users'),
                      'FORESIGHT_USERS_DIR': str(old / 'users')}, True)
        self.assertFalse((old / 'users').exists())

    def test_other_invocation_and_evidence_targets_rejected(self):
        for target in (self.root / 'scratch/e2/other/users', self.root / 'evidence/users',
                       self.scratch / 'nested/users'):
            with self.subTest(target=target):
                self.execute({**self.env, 'QC_ISOLATED_USERS_DIR': str(target),
                              'FORESIGHT_USERS_DIR': str(target)}, True)
                self.assertFalse(target.exists())

    def test_missing_host_environment_rejected(self):
        for name in ('REVIEW_SCRATCH', 'QC_ISOLATED_USERS_DIR', 'FORESIGHT_USERS_DIR'):
            with self.subTest(name=name):
                env = dict(self.env)
                del env[name]
                self.execute(env, True)

    def test_explicit_default_disagreement_rejected(self):
        self.execute({**self.env, 'FORESIGHT_USERS_DIR': str(self.root / 'other')}, True)

    def test_missing_invocation_directory_rejected(self):
        self.scratch.rmdir()
        self.execute(expect_denial=True)

    def test_unknown_owner_and_wrong_depth_rejected(self):
        for relative in ('scratch/unknown/probe-123', 'scratch/e2', 'scratch/e2/nested/probe-123'):
            with self.subTest(relative=relative):
                scratch = self.root / relative
                scratch.mkdir(parents=True, exist_ok=True)
                self.execute({**self.env, 'REVIEW_SCRATCH': str(scratch),
                              'QC_ISOLATED_USERS_DIR': str(scratch / 'users'),
                              'FORESIGHT_USERS_DIR': str(scratch / 'users')}, True)
                self.assertFalse((scratch / 'users').exists())

    def test_relative_and_traversing_target_rejected(self):
        for target in ('users', str(self.scratch / '..' / self.scratch.name / 'users')):
            with self.subTest(target=target):
                self.execute({**self.env, 'QC_ISOLATED_USERS_DIR': target,
                              'FORESIGHT_USERS_DIR': target}, True)

    def test_symlink_target_rejected(self):
        destination = self.root / 'outside'
        destination.mkdir()
        self.target.symlink_to(destination, target_is_directory=True)
        self.execute(expect_denial=True)
        self.assertEqual(list(destination.iterdir()), [])

    def test_restoring_old_work_guard_breaks_the_valid_scratch_contract(self):
        self.plugin.write_text(self.plugin.read_text().replace(
            "relative_to(ROOT / 'scratch')", "relative_to(ROOT / 'work')"))
        with self.assertRaises(AssertionError):
            self.execute()


if __name__ == '__main__':
    unittest.main()

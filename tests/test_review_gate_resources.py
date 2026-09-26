"""Admission counterexamples also run with unittest while pytest is busy."""
import unittest
from unittest.mock import patch

from scripts.review_probes.gate_resources import GIB, decision, is_pytest_process, observe


class GateResourceTests(unittest.TestCase):
    def test_pytest_without_report_option_blocks(self):
        row = "120 110 S Python /opt/bin/python -m pytest -q -p no:cacheprovider"
        result = decision(row, 16 * GIB)
        self.assertFalse(result["admitted"])
        self.assertEqual([p["pid"] for p in result["foreign_pytest"]], [120])

    def test_pytest_variants_block(self):
        for executable, command in (
            ("Python", "/opt/Python -u -B -m pytest -q --junitxml=result.xml"),
            ("python3.12", "/opt/python3.12 -m pytest tests/test_example.py"),
            ("python", "python -W ignore -X dev -m pytest --collect-only"),
            ("python", "python --check-hash-based-pycs always -mpytest -q"),
            ("python", "python /venv/bin/pytest -q"),
            ("python", "python /venv/bin/pytest-3 -q"),
            ("pytest", "/venv/bin/pytest -q"),
            ("py.test", "/venv/bin/py.test -q"),
            ("pytest-3", "/venv/bin/pytest-3 -q"),
        ):
            with self.subTest(command=command):
                self.assertTrue(is_pytest_process(executable, command))

    def test_process_search_and_other_python_do_not_block(self):
        for executable, command in (
            ("bash", "bash -c 'python -m pytest -q'"),
            ("rg", "rg python -m pytest"),
            ("python", "python -c 'print(\"-m pytest\")'"),
            ("python", "python -m pip install pytest"),
            ("python", "python script.py -m pytest"),
            ("python", "python -m pytest_plugin"),
            ("node", "node pytest"),
        ):
            with self.subTest(command=command):
                self.assertFalse(is_pytest_process(executable, command))

    def test_owned_group_not_root_substring_is_excluded(self):
        rows = "\n".join((
            "120 110 S Python python -m pytest --basetemp=/owned-root/tmp",
            "220 210 S Python python -m pytest --basetemp=/owned-root/foreign",
        ))
        result = decision(rows, 16 * GIB, excluded_groups=frozenset({110}))
        self.assertFalse(result["admitted"])
        self.assertEqual([p["pid"] for p in result["foreign_pytest"]], [220])

    def test_exited_zombie_is_not_live_work(self):
        self.assertTrue(decision("120 110 Z Python python -m pytest", 16 * GIB)["admitted"])

    def test_disk_threshold_is_not_rounded_down(self):
        self.assertTrue(decision("", 12 * GIB)["admitted"])
        self.assertFalse(decision("", 12 * GIB - 1)["admitted"])

    def test_malformed_snapshot_fails_closed(self):
        for snapshot in ("truncated snapshot", "pid group S Python python -m pytest"):
            with self.subTest(snapshot=snapshot), self.assertRaises(ValueError):
                decision(snapshot, 16 * GIB)

    def test_ambiguous_python_with_pytest_is_not_admitted(self):
        self.assertTrue(is_pytest_process("Python", "python -m pytest 'unclosed"))

    def test_observer_uses_complete_process_output(self):
        from pathlib import Path
        with patch("scripts.review_probes.gate_resources.subprocess.check_output", return_value="") as ps:
            with patch("scripts.review_probes.gate_resources.shutil.disk_usage") as disk:
                disk.return_value.free = 16 * GIB
                self.assertTrue(observe(Path("."))["admitted"])
        self.assertIn("-ww", ps.call_args.args[0])
        self.assertIn("ucomm=", ps.call_args.args[0][-1])


if __name__ == "__main__":
    unittest.main()

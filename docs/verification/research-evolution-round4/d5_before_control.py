"""Run the new D5 tests against the unchanged parent rules in memory (no edits).

Usage: python d5_before_control.py <new-04-tree> <before-04-tree>
This isolates regression-test sensitivity, not a full parent suite receipt.
"""
import importlib
import sys
import unittest
from pathlib import Path

candidate, before = map(Path, sys.argv[1:3])
sys.path.insert(0, str(candidate))
tests = importlib.import_module("intelligence.tests.test_research_diagnostics_review_20260913")
D5ReinstatedCurrentCannotMaskTimeGap = tests.D5ReinstatedCurrentCannotMaskTimeGap
rules = importlib.import_module("intelligence.services.research_diagnostics.rules")

source = before / "intelligence/services/research_diagnostics/rules.py"
exec(compile(source.read_text(), str(source), "exec"), rules.__dict__)
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(D5ReinstatedCurrentCannotMaskTimeGap))
sys.exit(not result.wasSuccessful())

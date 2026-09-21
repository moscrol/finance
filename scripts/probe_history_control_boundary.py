#!/usr/bin/env python3
"""Run H-01 regressions with one process-local protection withdrawal.

No source edits, model calls, production data or tool execution. Run each mode
with a bounded launcher. A killed mutant requires a test assertion failure,
not a collection/fixture error. Output directories must be new; old receipts
are never overwritten. These receipts are focused tests, not main-gate passes.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TEST = "tests/test_history_control_boundary.py"
SOURCES = (
    "intelligence/services/user_task.py",
    "intelligence/services/historical_research/intent.py",
    "intelligence/services/research_contract.py",
    "intelligence/services/honesty_gates.py",
    TEST,
    "scripts/probe_history_control_boundary.py",
)
# Alter function code objects so already imported aliases see the same change.
MUTATIONS = {
    "partition": (
        "user_task", "top_level_message_text",
        'return ("\\n".join(visible) if not uncertain else "", tuple(uncertain))',
        "return raw, tuple(uncertain)",
    ),
    "history-infer": (
        "historical_research.intent", "infer_history_intent",
        "question = _top_level_history_text(question)",
        'question = str(question or "")',
    ),
    "follow-up": (
        "research_contract", "_top_level_follow_up_query",
        "return cleaned, cleaned != raw", "return raw, False",
    ),
    "resolution-hint": (
        "research_contract", "is_contextual_follow_up",
        "and not protected_content_present", "and True",
    ),
    "cutoff": (
        "honesty_gates", "requested_information_cutoff",
        'visible_query, _uncertain = top_level_message_text(str(query or ""))',
        'visible_query = str(query or "")',
    ),
}


def identity():
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(ROOT), *args], timeout=10,
        ).decode()

    return {
        "head": git("rev-parse", "HEAD").strip(),
        "status": git("status", "--porcelain"),
        "sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES},
    }


class Outcomes:
    def __init__(self):
        self.passed = 0
        self.failed = []
        self.errors = []
        self.collected = 0

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)

    def pytest_runtest_logreport(self, report):
        if report.when == "call" and report.passed:
            self.passed += 1
        if report.failed:
            (self.failed if report.when == "call" else self.errors).append(report.nodeid)

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append(report.nodeid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("normal", *MUTATIONS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ["FWP_TEST_RECEIPT"] = "0"
    sys.dont_write_bytecode = True
    import pytest

    before = identity()
    started = datetime.now(timezone.utc).isoformat()
    results = Outcomes()
    mutation = None
    pytest_args = ["-q", "--tb=short", "--basetemp", str(output / "tmp"), TEST]
    with (output / "pytest.txt").open("w", encoding="utf-8") as stream:
        with redirect_stdout(stream), redirect_stderr(stream):
            if args.mode == "normal":
                code = int(pytest.main(pytest_args, plugins=[results]))
            else:
                module_name, name, old, new = MUTATIONS[args.mode]
                module = importlib.import_module(f"intelligence.services.{module_name}")
                function = getattr(module, name)
                source = inspect.getsource(function)
                if source.count(old) != 1:
                    raise ValueError("Mutation anchor is not unique")
                namespace = dict(vars(module))
                exec(compile(source.replace(old, new), inspect.getfile(function), "exec"), namespace)
                mutation = {"module": module_name, "function": name, "old": old, "new": new}
                original_code = function.__code__
                try:
                    function.__code__ = namespace[name].__code__
                    code = int(pytest.main(pytest_args, plugins=[results]))
                finally:
                    function.__code__ = original_code
    after = identity()
    expected = (
        code == 0 and results.passed == results.collected and results.collected > 0
        if args.mode == "normal" else code == 1 and bool(results.failed)
    )
    ok = expected and not results.errors and before == after
    receipt = {
        "scope": "H-01 focused operator check; not independent acceptance",
        "mode": args.mode, "mutation": mutation, "started": started,
        "finished": datetime.now(timezone.utc).isoformat(),
        "interpreter": sys.executable, "python": sys.version,
        "before": before, "after": after, "pytest_exit": code,
        "outcomes": vars(results), "expected_outcome_observed": ok,
    }
    (output / "result.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"mode": args.mode, "pytest_exit": code, "passed": results.passed,
                      "failed": len(results.failed), "errors": len(results.errors), "ok": ok}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

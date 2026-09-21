#!/usr/bin/env python3
"""Run history boundary and gap-followup regressions with one local withdrawal.

No source edits, model calls, production data or external runner execution. Run each mode
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
import textwrap

ROOT = Path(__file__).resolve().parents[1]
TEST = "tests/test_history_control_boundary.py"
INHERITANCE_TEST = "tests/test_history_permission_inheritance.py"
SOURCE_TEST = "tests/test_history_source_partition.py"
GAP_TEST = "tests/test_gap_followup_projection.py"
SOURCES = (
    "intelligence/services/query_resolution.py",
    "intelligence/services/user_task.py",
    "intelligence/services/historical_research/intent.py",
    "intelligence/services/research_contract.py",
    "intelligence/services/honesty_gates.py",
    "intelligence/services/conversation_materials.py",
    "intelligence/services/material_contract.py",
    "intelligence/services/task_frame.py",
    "intelligence/services/turn_controller.py",
    "intelligence/runtime/conversation_orchestrator.py",
    "intelligence/tests/test_historical_research_episode.py",
    "docs/agent-product-door.md",
    TEST,
    INHERITANCE_TEST,
    SOURCE_TEST,
    GAP_TEST,
    "scripts/probe_history_control_boundary.py",
)
# Alter function code objects so already imported aliases see the same change.
MUTATIONS = {
    "gap-projection": (
        "query_resolution", "classify_reference",
        'r"上一轮(?:「[^」]+」|[ \\t]+)未完成核验"',
        'r"上一轮「[^」]+」未完成核验"',
    ),
    "partition": (
        "user_task", "top_level_message_text",
        'return (regions.control_text if not regions.uncertain_reasons else "", regions.uncertain_reasons)',
        "return raw, regions.uncertain_reasons",
    ),
    "history-infer": (
        "historical_research.intent", "infer_history_intent",
        "question = _top_level_history_text(question)",
        'question = str(question or "")',
    ),
    "follow-up": (
        "research_contract", "_top_level_follow_up_query",
        "return cleaned, cleaned != raw.strip()", "return raw, False",
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
    "material-mask": (
        "user_task", "classify_top_level_regions",
        '" " * len(line) if claimed[index] else line', "line",
    ),
    "unclosed-quote": (
        "user_task", "_protected_layout",
        'uncertain.append("unclosed_quote")', "pass",
    ),
    "frame-source": (
        "task_frame", "build_task_frame",
        'history_intent = infer_history_intent(str(raw_question or ""))',
        "history_intent = infer_history_intent(core)",
    ),
    "followup-source": (
        "research_contract", "_top_level_follow_up_query",
        "visible, _uncertain = top_level_message_text(raw)",
        "visible, _uncertain = top_level_message_text(raw.strip())",
    ),
    "history-contract": (
        "material_contract", "compile_material_contract",
        "continuation = history_continuation or any(", "continuation = any(",
    ),
    "history-replay": (
        "conversation_materials", "collect_material_turn_history",
        "history_continuation=history_followup is not None", "history_continuation=False",
    ),
    "history-authority": (
        "conversation_materials", "ConversationMaterials.compile_contract",
        "if history_continuation and (self.history_intent is None or self.unavailable):",
        "if False:",
    ),
    "history-delivery": (
        "intelligence.runtime.conversation_orchestrator", "TurnOrchestrator._run_turn_ledgered",
        "if history_continuation or (material_contract and material_contract.continuation_requested):",
        "if material_contract and material_contract.continuation_requested:",
    ),
    "history-backfill": (
        "turn_controller", "decide_turn",
        "material_contract=material, conversation_materials=history,\n            )",
        "material_contract=None, conversation_materials=history,\n            )",
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
        self.assertion_failures = []

    def pytest_runtest_makereport(self, item, call):
        if call.when == "call" and call.excinfo and call.excinfo.errisinstance(AssertionError):
            self.assertion_failures.append(item.nodeid)

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
    parser.add_argument("--suite", choices=("boundary", "inheritance", "source", "gap", "all"), default="all")
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
    tests = {"boundary": [TEST], "inheritance": [INHERITANCE_TEST], "source": [SOURCE_TEST],
             "gap": [GAP_TEST], "all": [TEST, INHERITANCE_TEST, SOURCE_TEST, GAP_TEST]}[args.suite]
    pytest_args = ["-q", "--tb=short", "--basetemp", str(output / "tmp"), *tests]
    with (output / "pytest.txt").open("w", encoding="utf-8") as stream:
        with redirect_stdout(stream), redirect_stderr(stream):
            if args.mode == "normal":
                code = int(pytest.main(pytest_args, plugins=[results]))
            else:
                module_name, name, old, new = MUTATIONS[args.mode]
                module = importlib.import_module(
                    module_name if module_name.startswith("intelligence.") else f"intelligence.services.{module_name}"
                )
                function = module
                for component in name.split("."):
                    function = getattr(function, component)
                source = textwrap.dedent(inspect.getsource(function))
                if source.count(old) != 1:
                    raise ValueError("Mutation anchor is not unique")
                namespace = dict(vars(module))
                exec(compile(source.replace(old, new), inspect.getfile(function), "exec"), namespace)
                mutation = {"module": module_name, "function": name, "old": old, "new": new}
                original_code = function.__code__
                try:
                    function.__code__ = namespace[function.__name__].__code__
                    code = int(pytest.main(pytest_args, plugins=[results]))
                finally:
                    function.__code__ = original_code
    after = identity()
    expected = (
        code == 0 and results.passed == results.collected and results.collected > 0
        if args.mode == "normal" else code == 1 and bool(results.assertion_failures)
    )
    ok = expected and not results.errors and before == after
    receipt = {
        "scope": "H-01/H-02/H-03 focused operator check; not independent acceptance",
        "suite": args.suite, "pytest_args": pytest_args,
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

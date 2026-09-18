"""Falsify history diagnostic repairs without source edits or production DB access.

Each fresh child changes one imported function in memory, then runs a narrow
regression against temporary fixtures. Exit 0 means every mutation was caught
by a test failure (not an import/setup error). This is author-side test-strength
evidence, not independent QC, model acceptance, or a source-security audit.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[2]
TEST = "tests/test_history_tool_diagnostics.py"
KIND_TEST = "tests/test_history_argument_repair.py"
MUTATIONS = {
    "erase_diagnostic_delivery": {
        "module": "intelligence.services.research_tool_registry",
        "owner": "ResearchToolRegistry", "function": "execute",
        "old": "if run_result.diagnostics:", "new": "if False:",
        "test": f"{TEST}::test_real_strict_history_validation_diagnostic_can_repair_query",
    },
    "diagnostic_bypasses_fact_gate": {
        "module": "intelligence.services.research_tool_registry",
        "owner": "ResearchToolRegistry", "function": "execute",
        "old": "if history is not None and history.strict_window and spec.name not in {",
        "new": "if history is not None and history.strict_window and not run_result.diagnostics and spec.name not in {",
        "test": f"{TEST}::test_trusted_diagnostic_does_not_restore_disallowed_facts_or_prose",
    },
    "raw_exception_as_diagnostic": {
        "module": "intelligence.services.finance_query",
        "owner": None, "function": "validation_diagnostic",
        "old": 'safe_message = "查询参数未通过校验"', "new": "safe_message = message",
        "test": f"{TEST}::test_validation_diagnostic_does_not_echo_model_prose_or_unknown_error[exception]",
    },
    "silently_infer_market_kind": {
        "module": "intelligence.services.historical_research.query",
        "owner": "HistoryQuerySpec", "function": "from_arguments",
        "old": 'entity_kind = arguments.get("entity_kind", "sector")',
        "new": 'entity_kind = arguments.get("entity_kind", "market" if "000001.SH" in arguments.get("entity_codes", []) else "sector")',
        "test": f"{KIND_TEST}::test_omitted_kind_is_not_silently_inferred_from_code_or_features",
    },
}


def _child(name: str) -> int:
    import pytest

    mutation = MUTATIONS[name]
    module = importlib.import_module(mutation["module"])
    owner = getattr(module, mutation["owner"]) if mutation["owner"] else module
    original = getattr(owner, mutation["function"])
    source = textwrap.dedent(inspect.getsource(original))
    assert source.count(mutation["old"]) == 1, "mutation target drifted"
    source = source.replace(mutation["old"], mutation["new"])
    namespace = {}
    exec(compile(source, f"<mutation:{name}>", "exec"), module.__dict__, namespace)
    setattr(owner, mutation["function"], namespace[mutation["function"]])
    return int(pytest.main(["-q", mutation["test"], "--tb=short"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory; existing evidence is never overwritten")
    parser.add_argument("--child", choices=tuple(MUTATIONS), help=argparse.SUPPRESS)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    if args.child:
        return _child(args.child)
    if args.output is None:
        parser.error("--output is required")
    args.output.mkdir(parents=True, exist_ok=False)
    source_paths = {
        ROOT / (mutation["module"].replace(".", "/") + ".py")
        for mutation in MUTATIONS.values()
    } | {ROOT / "intelligence/services/episode_tools.py", ROOT / TEST, ROOT / KIND_TEST, Path(__file__).resolve()}
    source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source_paths)}
    results = []
    for name, mutation in MUTATIONS.items():
        run = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child", name],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        log = args.output / f"{name}.txt"
        log.write_text(run.stdout)
        # pytest exit 1 also includes setup errors; require an actual failed test
        # and reject ERROR summaries rather than calling any nonzero exit a kill.
        caught = run.returncode == 1 and "\nFAILED " in run.stdout and "\nERROR " not in run.stdout
        results.append(dict(mutation=name, test=mutation["test"], exit_code=run.returncode,
                            caught=caught, log=log.name, sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
        print(name, "caught" if caught else "NOT CAUGHT / INVALID", flush=True)
    unchanged = all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in source_hashes.items())
    report = dict(
        scope="author-side in-memory mutation tests; no product source edits, independent QC or live-model claim",
        revision=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        dirty_paths=subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).splitlines(),
        interpreter=sys.executable, source_sha256=source_hashes, source_unchanged=unchanged, mutations=results,
    )
    (args.output / "receipt.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return int(not unchanged or not all(result["caught"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())

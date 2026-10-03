"""Counterexamples for partial delivery: each removed guard must fail behavior tests.

Patches live Python objects in isolated subprocesses; never edits repository
source. Exit 1 is expected per variant. Load errors/empty selections do not count.
No model calls: the selected tests use scripted replies and blocked sockets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DELIVERY = "intelligence/tests/test_boundary_partial_delivery.py"
WATCH = "intelligence/tests/test_next_watch_boundaries.py"
PROGRESS = "intelligence/tests/test_agent_episode_progress.py"
RETEST = "intelligence/tests/test_boundary_retest_regressions.py"

VARIANTS = {
    "requested_source_resolution_removed": (
        "import intelligence.services.user_task as m\n"
        "m.references_material = lambda text: bool(m._MATERIAL_REFERENCE_RE.search(text))\n",
        [RETEST, "-k", "retrieval_or_output_reference or future_source_reference"],
    ),
    "numeric_comparators_removed": (
        "import re\nimport intelligence.services.episode_semantic_verifier as m\n"
        "m._NUMERIC_COMPARATOR_RE = re.compile(r'(?!)')\n",
        [RETEST, "-k", "same_unsupported_condition"],
    ),
    "condition_context_removed": (
        "import re\nimport intelligence.services.episode_semantic_verifier as m\n"
        "m._CONDITION_LABEL_RE = m._CONDITION_HEADING_RE = re.compile(r'(?!)')\n",
        [RETEST, "-k", "same_unsupported_condition"],
    ),
    "receipt_filter_removed": (
        "import re\nimport intelligence.services.track_contract as m\n"
        "m._WATCH_RECEIPT_RE = re.compile(r'(?!)')\n",
        [RETEST, "-k", "receipt_footer"],
    ),
    "review_date_role_removed": (
        "import intelligence.services.track_contract as m\nold = m._item_due\n"
        "m._item_due = lambda line, as_of: m._DATE_RE.search(line).group(1) if m._DATE_RE.search(line) else old(line, as_of)\n",
        [RETEST, "-k", "report_period_cannot"],
    ),
    "review_date_conflict_removed": (
        "import intelligence.services.track_contract as m\nm._review_dates = lambda line: ()\n",
        [RETEST, "-k", "ambiguous_or_invalid"],
    ),
    "arrow_condition_removed": (
        "import re\nimport intelligence.services.track_contract as m\n"
        "m._ARROW_CONDITION_RE = re.compile(r'(?!)')\n",
        [RETEST, "-k", "heading_ttl_and_qualitative"],
    ),
    "list_end_removed": (
        "import ast, inspect\nimport intelligence.services.track_contract as m\n"
        "tree = ast.parse(inspect.getsource(m._split_watch_claims))\n"
        "class RemoveBreak(ast.NodeTransformer):\n"
        "    def visit_Break(self, node):\n        return ast.copy_location(ast.Pass(), node)\n"
        "exec(compile(ast.fix_missing_locations(RemoveBreak().visit(tree)), '<mutation>', 'exec'), m.__dict__)\n",
        [RETEST, "-k", "explicit_watch_list"],
    ),
    "mapping_projection_removed": (
        "import intelligence.runtime.research_progress as m\n"
        "def fail(value):\n    raise TypeError('mapping JSON disabled')\n"
        "m._mapping_for_json = fail\n",
        [PROGRESS, "-k", "url_failure"],
    ),
    "section_boundary_removed": (
        "import intelligence.services.track_contract as m\nm._watch_section_end = lambda line: False\n",
        [WATCH, "-k", "stops_before_following"],
    ),
    "date_counts_as_trigger": (
        "import intelligence.services.track_contract as m\nold = m._is_registerable_watch\n"
        "m._is_registerable_watch = lambda line: old(line) or bool(m._DATE_RE.search(line))\n",
        [WATCH, "-k", "date_only or placeholder"],
    ),
    "post_semantic_feedback_removed": (
        "import intelligence.runtime.continuous_turn_adapter as m\n"
        "m.semantic_repair_feedback = lambda semantic: ()\n",
        [DELIVERY, "-k", "legal_repair_reuses"],
    ),
    "verified_recovery_removed": (
        "from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter\n"
        "ContinuousTurnAdapter._recover_verified_delivery = lambda *args: None\n",
        [DELIVERY, "-k", "bad_condition and raises"],
    ),
    "all_checkpoint_writes_disabled": (
        "import intelligence.services.track_contract as m\nm.ingest_next_watch = lambda *a, **kw: []\n",
        [DELIVERY, "-k", "legal_repair_reuses"],
    ),
    "numeric_gate_removed": (
        "import intelligence.services.episode_semantic_verifier as m\n"
        "m._novel_numeric_condition_indexes = lambda *args: ()\n",
        [DELIVERY, "-k", "bad_condition and none"],
    ),
    "opt_out_removed": (
        "import intelligence.services.track_contract as m\nm.persistence_opt_out = lambda query: False\n",
        [DELIVERY, "-k", "legal_repair_reuses"],
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    files = [ROOT / p for p in (
        "intelligence/runtime/continuous_turn_adapter.py", "intelligence/runtime/research_progress.py",
        "intelligence/services/track_contract.py", "intelligence/services/user_task.py",
        "intelligence/services/episode_semantic_verifier.py", DELIVERY, WATCH, PROGRESS, RETEST,
        "scripts/review_probes/run_boundary_repair_mutations.py",
    )]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    results, counts = {}, {}
    for name, (patch, selection) in VARIANTS.items():
        junit = out / (name + ".xml")
        code = patch + "\nimport pytest\nraise SystemExit(pytest.main(" + repr(["-q", f"--junitxml={junit}", *selection]) + "))\n"
        (out / (name + ".py")).write_text(code)
        with (out / (name + ".log")).open("w") as log:
            result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        results[name] = result.returncode
        suites = ET.parse(junit).getroot().iter("testsuite") if junit.exists() else ()
        counts[name] = {key: 0 for key in ("tests", "failures", "errors")}
        for suite in suites:
            for key in counts[name]:
                counts[name][key] += int(suite.get(key, "0"))
        (out / (name + ".exit")).write_text(str(result.returncode) + "\n")
        print(name, result.returncode, counts[name], flush=True)
    unchanged = all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
    (out / "results.json").write_text(json.dumps({
        "revision": revision, "results": results, "counts": counts,
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "sources_sha256": hashes, "sources_unchanged": unchanged,
    }, indent=2) + "\n")
    assert unchanged and all(
        results[name] == 1 and row["tests"] > 0 and row["failures"] > 0 and row["errors"] == 0
        for name, row in counts.items()
    ), "require behavioral failure, not load errors or empty selections, for every removed guard"


if __name__ == "__main__":
    main()

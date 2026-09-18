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

ROOT = Path(__file__).resolve().parents[2]
DELIVERY = "intelligence/tests/test_boundary_partial_delivery.py"
WATCH = "intelligence/tests/test_next_watch_boundaries.py"
PROGRESS = "intelligence/tests/test_agent_episode_progress.py"

VARIANTS = {
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
    "post_semantic_completeness_removed": (
        "import intelligence.runtime.continuous_turn_adapter as m\n"
        "m._with_semantic_contract_gaps = lambda semantic, context, **kwargs: semantic\n",
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
        "intelligence/services/track_contract.py", DELIVERY, WATCH, PROGRESS,
    )]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    results = {}
    for name, (patch, selection) in VARIANTS.items():
        code = patch + "\nimport pytest\nraise SystemExit(pytest.main(" + repr(["-q", *selection]) + "))\n"
        (out / (name + ".py")).write_text(code)
        with (out / (name + ".log")).open("w") as log:
            result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        results[name] = result.returncode
        (out / (name + ".exit")).write_text(str(result.returncode) + "\n")
        print(name, result.returncode, flush=True)
    unchanged = all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
    (out / "results.json").write_text(json.dumps({
        "revision": revision, "results": results, "sources_sha256": hashes, "sources_unchanged": unchanged,
    }, indent=2) + "\n")
    assert unchanged and all(exit_code == 1 for exit_code in results.values()), "require behavioral failure for every removed guard"


if __name__ == "__main__":
    main()

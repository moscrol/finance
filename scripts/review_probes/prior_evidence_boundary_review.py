"""Capture date-boundary reuse on a separate, clean, explicitly pinned checkout.

The target checkout supplies registered synthetic Episode fixtures and the real
loader/admission functions. This does not run HTTP, a model, or the episode seed.
Keep the checkout stationary for the entire process: a Git switch is not an
independent parallel task. A failed capture retains its directory and cannot be
retried in place. Exit zero means capture completed, not product acceptance.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys

SOURCES = (
    "intelligence/services/prior_evidence.py",
    "intelligence/services/query_understanding.py",
    "intelligence/services/turn_controller.py",
    "intelligence/services/episode_factory.py",
    "intelligence/services/run_store.py",
    "intelligence/tests/test_prior_evidence.py",
    "intelligence/tests/test_reasoning_input_boundaries.py",
)
CASES = (
    ("inclusive_to_exclusive", "截至2026年9月14日（含当日）", "2026年9月14日之前（不含当日）", False),
    ("same_inclusive_control", "截至2026年9月14日（含当日）", "截至2026年9月14日（含当日）", True),
    ("from_to_after", "2026年9月14日起（含当日）", "2026年9月14日之后（不含当日）", False),
    ("different_date_control", "截至2026年9月14日（含当日）", "截至2026年9月13日（含当日）", False),
)


def _git(tree: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(tree), *args], text=True, timeout=15,
    ).strip()


def _fingerprints(tree: Path) -> dict[str, str]:
    return {p: hashlib.sha256((tree / p).read_bytes()).hexdigest() for p in SOURCES}


def _preflight(checkout: Path, revision: str, output: Path) -> tuple[Path, Path, dict[str, str]]:
    tree, out = checkout.resolve(strict=True), output.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("a full lowercase 40-character revision is required")
    if Path(_git(tree, "rev-parse", "--show-toplevel")).resolve() != tree:
        raise ValueError("checkout must be the worktree root")
    if _git(tree, "rev-parse", "HEAD") != revision or _git(tree, "status", "--porcelain"):
        raise ValueError("checkout must be clean at the requested revision")
    probe_tree = Path(__file__).resolve().parents[2]
    if any(out == root or root in out.parents or out in root.parents for root in (tree, probe_tree)):
        raise ValueError("output must be outside and separate from checkout")
    if out.exists() or output.is_symlink():
        raise ValueError("output must be a new directory; preserve prior attempts")
    return tree, out, _fingerprints(tree)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tree, out, fingerprints = _preflight(args.checkout, args.revision, args.output)
    probe_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out.mkdir(mode=0o700)
    state = out / "state"
    state.mkdir(mode=0o700)
    environment = {k: v for k, v in os.environ.items() if k in {"PATH", "LANG", "LC_ALL"}}
    environment.update({
        "HOME": str(state), "FINANCE_WS": str(state), "FINANCE_DATA_ROOT": str(state),
        "MARKET_FEATURE_STORE_DB": str(state / "absent.duckdb"),
        "FORESIGHT_USERS_DIR": str(state / "users"),
        "FORESIGHT_EPISODE_STORE": str(state / "episodes"),
        "SUBCONSCIOUS_VAULT": str(state / "vault"),
        "FINANCE_REJUDGE_PENDING_INDEX": str(state / "rejudge.jsonl"),
        "ENTITY_ANCHOR_SECURITIES_DB": "0",
    })
    os.environ.clear()
    os.environ.update(environment)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(tree))
    import duckdb

    allowed = {state / name / "runs" / "workbench.sqlite3" for name, *_ in CASES}
    original_connect = sqlite3.connect
    opens, blocked = [], []

    def forbid(kind):
        def reject(*_args, **_kwargs):
            blocked.append(kind)
            raise AssertionError("blocked " + kind)
        return reject

    def isolated_sqlite(database, *pos, **kw):
        if Path(str(database)).resolve() not in allowed:
            return forbid("unexpected_sqlite")()
        opens.append(str(Path(database).resolve()))
        return original_connect(database, *pos, **kw)

    socket.socket.connect = forbid("network_connect")
    socket.socket.connect_ex = forbid("network_connect_ex")
    duckdb.connect = forbid("duckdb")
    sqlite3.connect = isolated_sqlite

    from intelligence.services.conversation_materials import collect_material_turn_history
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.prior_evidence import load_previous_evidence
    from intelligence.services.query_understanding import query_time_scope
    from intelligence.services.turn_controller import decide_turn
    from intelligence.tests.test_prior_evidence import _source
    from intelligence.tests.test_reasoning_input_boundaries import REVIEW, no_llm

    rows = []
    for name, old_window, new_window, expected in CASES:
        question = f"请只查本地数据，统计{old_window}的A股上涨家数，不联网。"
        store, run, messages, _, _, _, _ = _source(state / name, source_question=question)
        query = REVIEW + f"仍只复核{new_window}的数据。"
        frame = decide_turn(query, conversation_materials=collect_material_turn_history(messages), llm_complete=no_llm).task_frame
        context = build_episode_context(frame, task_id=name)
        contract = context.contract
        row = {
            "case": name, "source_question": question, "review_question": query,
            "source_scope": asdict(query_time_scope(question)),
            "review_scope": asdict(query_time_scope(query)),
            "expected_same_window": expected,
            "allowed_capabilities": contract.allowed_capabilities,
            "material_scope": frame.material_contract.data_scope,
            "source_run_id": run.run_id,
            "current_cutoff": context.information_cutoff.as_of_date.isoformat(),
        }
        try:
            result = load_previous_evidence(frame, messages=messages, store=store, conversation_id="conv", current_run_id="current")
        except ValueError as exc:
            row.update(admitted=False, error=str(exc))
        else:
            row.update(admitted=result is not None,
                       admitted_dates=[item.source_date for _, item in result.entries] if result else [],
                       original_refs=[ref for ref, _ in result.entries] if result else [])
            if result is not None:
                inputs = result.admitted(task_frame_hash=contract.task_frame_hash, cutoff=context.information_cutoff.as_of_date)
                row.update(source_cutoff=result.source_cutoff.isoformat(),
                           consumer_admitted_dates=[item.source_date for item in inputs],
                           consumer_observation_dates=[o.as_of for item in inputs for o in item.observations])
        rows.append(row)
    if (_fingerprints(tree) != fingerprints or _git(tree, "rev-parse", "HEAD") != args.revision
            or _git(tree, "status", "--porcelain")
            or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != probe_hash):
        raise RuntimeError("capture identity changed; do not use this attempt")
    report = {
        "observed_at": datetime.now(timezone.utc).isoformat(), "revision": args.revision,
        "interpreter": sys.executable, "source_sha256": fingerprints,
        "probe_sha256": probe_hash, "clean_before_and_after": True, "rows": rows,
        "isolated_sqlite_opens": opens, "blocked_attempts": blocked, "real_model_requests": 0,
        "boundary": "synthetic originals; real loader/admitted/store; no HTTP, model or episode seed; script guard is not an OS sandbox",
    }
    with (out / "report.json").open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({"revision": args.revision, "rows": rows, "blocked_attempts": blocked}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

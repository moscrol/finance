"""Host-repaired builders derived from the preserved K3 probes.

This copy is a host-authored test tool, not a new independent K3 review.
Only shadow modules are mutated; candidate source is read-only.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from uuid import uuid4

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_authorization import capture_authorization_snapshot
from intelligence.services.episode_entry_identity import EntryIdentity
from intelligence.services.episode_store import EpisodeState, JsonlEpisodeStore
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.services.research_contract import (
    ResearchPolicy,
    release_root_budget,
    root_budget_for_policy,
)
from intelligence.tests.conformance.fixtures import (
    ScenarioProbe,
    make_context,
    make_frame,
    make_registry,
)

CANDIDATE = Path(os.environ["K3_CANDIDATE"]).resolve()
MUTATION = os.environ.get("K3_MUTATION", "")
if MUTATION not in {"", "identity", "budget"}:
    raise ValueError(f"unknown mutation: {MUTATION}")

NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)

OWNER = {
    "entry": "workbench_conversation",
    "user_id": "alice-k3qc",
    "conversation_id": "conv-k3qc-1",
    "run_id": "run-k3qc-1",
    "assistant_message_id": "msg-k3qc-1",
}


def make_owner_identity(task_id: str, **overrides: str):
    fields = dict(OWNER)
    fields.update(overrides)
    return EntryIdentity(**fields).bind(task_id)


def budget_snapshot(episode: str, *, calls: int = 3) -> dict[str, object]:
    root = root_budget_for_policy(ResearchPolicy("quick", calls, 30, 10), episode_id=episode)
    try:
        return root.to_snapshot()
    finally:
        release_root_budget(episode)


def dangling_model_episode(
    tmp_path: Path,
    *,
    retries: int = 2,
    bound: bool = False,
    with_budget: bool = False,
    identity_overrides: dict[str, str] | None = None,
):
    """One episode that crashed right after logging model_intent (no settlement)."""

    episode = f"k3-{uuid4().hex[:12]}"
    context = make_context(make_frame(), task_id=episode)
    context = replace(context, contract=replace(context.contract, task_frame_hash="tf"))
    probe = ScenarioProbe()
    registry = make_registry(probe)
    evidence = EvidenceLedger(
        information_cutoff=context.information_cutoff.as_of_date
    ).to_recovery_snapshot(episode_id=episode, presented_evidence=())
    identity = None
    if bound:
        identity = make_owner_identity(episode, **(identity_overrides or {}))
        context = replace(context, entry_identity=identity)
    store = JsonlEpisodeStore(tmp_path)
    store.append(
        episode,
        (
            EpisodeEvent(1, "task", {"task_frame_hash": "tf"}),
            EpisodeEvent(2, "model_intent", {"turn_id": "turn-1"}),
        ),
        sync=True,
    )
    state = EpisodeState(
        episode_id=episode,
        phase="model_pending",
        reserved_ids=("turn-1",),
        deadline_at=(NOW + timedelta(minutes=2)).isoformat(),
        retry={"remaining": retries},
        last_sequence=2,
        authorization_snapshot=capture_authorization_snapshot(context, registry),
        evidence_snapshot=evidence,
        evidence_snapshot_sequence=2,
        entry_identity=identity.to_dict() if identity is not None else None,
        budget_snapshot=budget_snapshot(episode) if with_budget else None,
        budget_snapshot_sequence=2 if with_budget else None,
    )
    store.put_state(episode, state)
    return episode, store, context, registry


def dir_bytes(episode_dir: Path) -> dict[str, bytes]:
    """Content snapshot of every durable file, excluding the writer lock inode."""

    return {
        p.name: p.read_bytes()
        for p in sorted(episode_dir.iterdir())
        if p.is_file() and p.name != ".writer.lock"
    }


def _shadow_module(rel_path: str, replacements: list[tuple[str, str]], name: str) -> ModuleType:
    """Build a mutated in-memory copy of a candidate module (candidate untouched)."""

    path = CANDIDATE / rel_path
    source = path.read_text()
    for old, new in replacements:
        if source.count(old) != 1:
            raise AssertionError(f"mutation target must match exactly once in {rel_path}: {old[:60]!r}")
        source = source.replace(old, new, 1)
    module = ModuleType(name)
    module.__dict__["__file__"] = str(path)
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(compile(source, str(path), "exec"), module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    return module


IDENTITY_GATE = """    if not entry_identities_match(state.entry_identity, capture_entry_identity(context)):
        raise RestoreUnavailable(f"{episode_id}: recovery entry identity does not match the recorded owner")
    if state.entry_identity is not None:
        try:
            validate_current_entry_identity(state.entry_identity, context=context)
        except (TypeError, ValueError) as exc:
            raise RestoreUnavailable(f"{episode_id}: recovery entry identity mismatch") from exc
"""

BUDGET_GATE = """    outstanding = unknown_effects_from_payload(list(unreconciled_effects))
    if outstanding:
        raise ValueError(
            f"root budget for {episode_id} has {len(outstanding)} unreconciled effect(s); "
            "reconcile them before spending this balance"
        )
"""


def restore_module():
    if MUTATION == "identity":
        return _shadow_module(
            "intelligence/services/episode_restore.py",
            [(IDENTITY_GATE, "    # K3 MUTANT: entry identity gate removed\n")],
            "k3_shadow_episode_restore",
        )
    import intelligence.services.episode_restore as real

    return real


def budgets_module():
    if MUTATION == "budget":
        return _shadow_module(
            "intelligence/services/research_contract.py",
            [
                (
                    BUDGET_GATE,
                    "    outstanding = unknown_effects_from_payload(list(unreconciled_effects))"
                    "  # K3 MUTANT: spend gate removed\n",
                )
            ],
            "k3_shadow_research_contract",
        )
    import intelligence.services.research_contract as real

    return real

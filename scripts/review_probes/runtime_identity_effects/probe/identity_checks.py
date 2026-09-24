"""Host-repaired identity probes; malformed input is not an owner mismatch."""

from __future__ import annotations

import json
import sys
from dataclasses import replace

import pytest

from intelligence.services.episode_store import JsonlEpisodeStore

from k3_fixtures import (
    MUTATION,
    NOW,
    dangling_model_episode,
    dir_bytes,
    make_owner_identity,
    restore_module,
)

restore_mod = restore_module()
RestoreUnavailable = restore_mod.RestoreUnavailable


def test_same_owner_restores_and_stays_bound_on_disk(tmp_path) -> None:
    episode, store, context, registry = dangling_model_episode(tmp_path, bound=True)
    result = restore_mod.restore_episode(episode, store, now=NOW, context=context, registry=registry)
    assert result.plan is not None and result.plan.action == "retry_model"
    assert result.entry_identity_bound is True
    reread = JsonlEpisodeStore(tmp_path).load(episode)[1]
    assert reread is not None and reread.entry_identity is not None
    assert reread.entry_identity == context.entry_identity.to_dict()


def test_wrong_user_refused_and_nothing_is_written(tmp_path) -> None:
    episode, store, context, registry = dangling_model_episode(tmp_path, bound=True, with_budget=True)
    before = dir_bytes(store.episode_dir(episode))
    intruder = replace(context, entry_identity=make_owner_identity(episode, user_id="mallory-k3qc"))
    with pytest.raises(RestoreUnavailable, match="entry identity does not match the recorded owner"):
        restore_mod.restore_episode(episode, store, now=NOW, context=intruder, registry=registry)
    assert dir_bytes(store.episode_dir(episode)) == before


@pytest.mark.parametrize("field", ["conversation_id", "run_id", "assistant_message_id"])
def test_wrong_conversation_run_and_message_refused(tmp_path, field) -> None:
    episode, store, context, registry = dangling_model_episode(tmp_path, bound=True, with_budget=True)
    before = dir_bytes(store.episode_dir(episode))
    intruder = replace(context, entry_identity=make_owner_identity(episode, **{field: "other-owner"}))
    with pytest.raises(RestoreUnavailable, match="entry identity does not match the recorded owner"):
        restore_mod.restore_episode(episode, store, now=NOW, context=intruder, registry=registry)
    assert dir_bytes(store.episode_dir(episode)) == before


def test_malformed_episode_identity_refused_and_nothing_written(tmp_path) -> None:
    episode, store, context, registry = dangling_model_episode(tmp_path, bound=True, with_budget=True)
    before = dir_bytes(store.episode_dir(episode))
    malformed = replace(context, entry_identity=make_owner_identity("someone-elses-episode"))
    with pytest.raises(ValueError, match="^entry identity episode mismatch$"):
        restore_mod.restore_episode(episode, store, now=NOW, context=malformed, registry=registry)
    assert dir_bytes(store.episode_dir(episode)) == before


@pytest.mark.parametrize("bound", [True, False], ids=["bound_checkpoint", "unbound_checkpoint"])
def test_binding_asymmetry_refuses_without_writing(tmp_path, bound) -> None:
    episode, store, context, registry = dangling_model_episode(tmp_path, bound=bound, with_budget=True)
    before = dir_bytes(store.episode_dir(episode))
    intruder = replace(context, entry_identity=None if bound else make_owner_identity(episode))
    with pytest.raises(RestoreUnavailable, match="entry identity does not match the recorded owner"):
        restore_mod.restore_episode(episode, store, now=NOW, context=intruder, registry=registry)
    assert dir_bytes(store.episode_dir(episode)) == before


def test_unbound_checkpoint_and_context_restore(tmp_path) -> None:
    episode, store, context, registry = dangling_model_episode(tmp_path, bound=False)
    result = restore_mod.restore_episode(episode, store, now=NOW, context=context, registry=registry)
    assert result.plan is not None and result.entry_identity_bound is False


def test_identity_never_reaches_synthesized_events_or_effect_receipts(tmp_path) -> None:
    episode, store, context, registry = dangling_model_episode(tmp_path, bound=True)
    result = restore_mod.restore_episode(episode, store, now=NOW, context=context, registry=registry)
    blob = json.dumps(
        [e.to_dict() for e in result.synthesized + tuple(result.events)],
        ensure_ascii=False,
    )
    for secret in ("alice-k3qc", "conv-k3qc-1", "run-k3qc-1", "msg-k3qc-1"):
        assert secret not in blob


def test_shadow_registration_does_not_replace_real_module() -> None:
    import intelligence.services.episode_restore as real

    assert sys.modules[real.__name__] is real
    assert sys.modules[restore_mod.__name__] is restore_mod
    if MUTATION == "identity":
        assert restore_mod is not real
        assert RestoreUnavailable is not real.RestoreUnavailable
    else:
        assert restore_mod is real

"""Entry identity: whose conversation an episode belongs to, decided at the door.

A checkpoint can prove what a run did. It cannot prove *whose* run it was:
every field in it was written by the same process that is now asking to
continue. So identity is not read out of the log and trusted -- the entry point
(the door the request came through) supplies it again, and recovery only accepts
an exact match with what the interrupted run recorded.

Two types, because they are two different claims:

- ``EntryIdentity`` -- what the door knows before any episode exists: user,
  conversation, run, assistant message. The API layer builds it only after
  checking those against the stored run record, not from client-supplied query
  parameters.
- ``EpisodeEntryIdentity`` -- that same claim bound to one ``episode_id``.
  Binding happens when the episode id is minted, so a captured identity can
  never be replayed onto a different episode.

Not in scope here: authentication (who the human is), authorization (what the
episode may do -- that is ``episode_authorization``), and single-writer
ownership (who may write right now -- that is ``episode_store.writer``).
Identity answers only "is this the same door, for the same conversation".
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

from intelligence.services.agent_runtime import _json_copy

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps the import graph acyclic
    from intelligence.services.research_contract import ResearchRunContext

_VERSION = 1
_KIND = "episode_entry_identity"
_FIELDS = frozenset({
    "schema_version", "kind", "episode_id", "entry",
    "user_id", "conversation_id", "run_id", "assistant_message_id",
})
_ID_FIELDS = ("user_id", "conversation_id", "run_id", "assistant_message_id")
_MAX_ID_LENGTH = 200
# Doors allowed to own an episode. Adding one is a deliberate act: an unknown
# entry name means nobody can say who was verified behind it.
ENTRY_POINTS = frozenset({"workbench_conversation"})


def _identifier(value: object, *, field: str) -> str:
    """One shape for every identity field: a bare, whitespace-free token."""

    if not isinstance(value, str) or value.split() != [value]:
        raise ValueError(f"entry identity {field} must be a non-empty token without whitespace")
    if len(value) > _MAX_ID_LENGTH:
        raise ValueError(f"entry identity {field} exceeds {_MAX_ID_LENGTH} characters")
    return value


def _json(value: object) -> str:
    return json.dumps(_json_copy(value, path="entry_identity"), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class EntryIdentity:
    """The door's verified claim, before an episode id exists."""

    entry: str
    user_id: str
    conversation_id: str
    run_id: str
    assistant_message_id: str

    def __post_init__(self) -> None:
        if self.entry not in ENTRY_POINTS:
            raise ValueError(f"unknown episode entry point: {self.entry!r}")
        for field in _ID_FIELDS:
            _identifier(getattr(self, field), field=field)

    def bind(self, episode_id: str) -> EpisodeEntryIdentity:
        """Bind to the episode being started. Never call it on a borrowed id."""

        return EpisodeEntryIdentity(
            episode_id=episode_id, entry=self.entry, user_id=self.user_id,
            conversation_id=self.conversation_id, run_id=self.run_id,
            assistant_message_id=self.assistant_message_id,
        )


@dataclass(frozen=True)
class EpisodeEntryIdentity:
    """An entry claim bound to one episode; this is what a checkpoint records."""

    episode_id: str
    entry: str
    user_id: str
    conversation_id: str
    run_id: str
    assistant_message_id: str

    def __post_init__(self) -> None:
        if self.entry not in ENTRY_POINTS:
            raise ValueError(f"unknown episode entry point: {self.entry!r}")
        _identifier(self.episode_id, field="episode_id")
        for field in _ID_FIELDS:
            _identifier(getattr(self, field), field=field)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": _VERSION, "kind": _KIND, "episode_id": self.episode_id,
            "entry": self.entry, "user_id": self.user_id,
            "conversation_id": self.conversation_id, "run_id": self.run_id,
            "assistant_message_id": self.assistant_message_id,
        }

    @classmethod
    def from_dict(cls, payload: object, *, episode_id: str) -> EpisodeEntryIdentity:
        raw = _json_copy(payload, path="entry_identity")
        if not isinstance(raw, dict) or set(raw) != _FIELDS:
            raise ValueError("entry identity fields are incomplete or unknown")
        if type(raw["schema_version"]) is not int or raw["schema_version"] != _VERSION:
            raise ValueError("unsupported entry identity snapshot version")
        if raw["kind"] != _KIND:
            raise ValueError("unsupported entry identity snapshot kind")
        identity = cls(
            episode_id=raw["episode_id"], entry=raw["entry"], user_id=raw["user_id"],
            conversation_id=raw["conversation_id"], run_id=raw["run_id"],
            assistant_message_id=raw["assistant_message_id"],
        )
        if identity.episode_id != _identifier(episode_id, field="episode_id"):
            raise ValueError("entry identity episode mismatch")
        return identity


def capture_entry_identity(context: ResearchRunContext) -> dict[str, object] | None:
    """Capture the running context's owner, or ``None`` when there is no door.

    ``None`` is a real configuration (offline drivers, tests, CLI): it records
    "nobody was verified", which recovery later refuses to treat as a match for
    any door. It is never a placeholder for an identity we failed to read.
    """

    identity = getattr(context, "entry_identity", None)
    if identity is None:
        return None
    if not isinstance(identity, EpisodeEntryIdentity):
        raise TypeError("context entry_identity must be an EpisodeEntryIdentity")
    value = identity.to_dict()
    # Encoding/validation failure is required-persistence failure at the caller.
    return EpisodeEntryIdentity.from_dict(value, episode_id=context.contract.task_id).to_dict()


def validate_current_entry_identity(
    payload: object, *, context: ResearchRunContext,
) -> None:
    """Exact match only. No field-by-field fallback, no "same user is enough"."""

    saved = EpisodeEntryIdentity.from_dict(payload, episode_id=context.contract.task_id)
    current = capture_entry_identity(context)
    if current is None:
        raise ValueError("current entry point carries no identity for a bound episode")
    if _json(saved.to_dict()) != _json(current):
        raise ValueError("current entry identity does not match the captured owner")


def entry_identities_match(saved: Mapping[str, object] | None, current: Mapping[str, object] | None) -> bool:
    """Both absent or byte-identical. Absence never matches presence."""

    if saved is None or current is None:
        return saved is None and current is None
    return _json(saved) == _json(current)

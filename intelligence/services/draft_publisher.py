"""Publish decoded ``draft`` prose to the replayable SSE stream as it arrives.

Sibling of ``episode_progress``, deliberately a *separate* owner because the
two carry opposite contracts:

* ``episode_progress`` projects control-plane events into fixed sentences and
  ignores every payload value -- nothing the model wrote may cross;
* this module carries model prose on purpose. It is the same text that becomes
  the final answer, published early instead of at the end.

That is why it is not a new branch inside the progress projector. Mixing them
would make "does model text cross this seam?" answerable only by reading the
event kind, and the next person would get it wrong.

Off by default at the call site, not here: the caller decides whether the run
streams (see ``draft_streaming_enabled``).
"""

from __future__ import annotations

import os
from threading import RLock

from intelligence.services.run_store import RunStore


def draft_streaming_enabled() -> bool:
    """Kill switch for live draft streaming.

    On by default: the whole point is that the user stops waiting 24 seconds
    for the first character.  ``WORKBENCH_DRAFT_STREAM=off`` reverts to the
    previous behaviour without a deploy, which matters because this is the one
    change in the answer path that touches the model transport.
    """

    return os.environ.get("WORKBENCH_DRAFT_STREAM", "on").strip().lower() != "off"


class RunDraftDeltaPublisher:
    """Append one ``text.delta`` stream event per decoded fragment.

    Sequence numbering is local and monotonic so replay after a reconnect keeps
    the fragments in order; the frontend concatenates ``payload.delta`` in
    arrival order and dedupes by ``event_id``.
    """

    def __init__(
        self,
        *,
        run_store: RunStore,
        run_id: str,
        conversation_id: str,
        message_id: str,
        event_id_prefix: str = "",
    ) -> None:
        if not isinstance(run_store, RunStore):
            raise TypeError("run_store must be a RunStore")
        self._run_store = run_store
        self._run_id = str(run_id or "").strip()
        self._conversation_id = str(conversation_id or "").strip()
        self._message_id = str(message_id or "").strip()
        self._event_id_prefix = str(event_id_prefix or "")
        if not self._run_id or not self._conversation_id or not self._message_id:
            raise ValueError("draft publisher identities must be non-empty")
        self._sequence = 0
        self._emitted_chars = 0
        self._lock = RLock()

    @property
    def emitted_chars(self) -> int:
        """How much prose already reached the client.

        The orchestrator reads this to decide whether its own bulk
        ``text.delta`` would duplicate what the user already watched appear.
        """

        with self._lock:
            return self._emitted_chars

    def publish(self, delta: str) -> None:
        text = str(delta or "")
        if not text:
            return
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            self._emitted_chars += len(text)
        self._run_store.append_stream_event(
            self._run_id,
            event_id=f"{self._event_id_prefix}draft:delta:{sequence:06d}",
            event_type="text.delta",
            payload={"delta": text},
            conversation_id=self._conversation_id,
            message_id=self._message_id,
        )


__all__ = ["RunDraftDeltaPublisher", "draft_streaming_enabled"]

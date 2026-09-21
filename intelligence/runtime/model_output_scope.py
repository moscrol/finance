"""Per-call publication permission for a model client shared by parent/children.

Do not mutate the shared client's sink: parallel child calls would race with
one another and with the parent. ContextVar stays local to each worker context.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_DRAFT_PUBLICATION: ContextVar[bool] = ContextVar("model_draft_publication", default=True)


def draft_publication_allowed() -> bool:
    return _DRAFT_PUBLICATION.get()


@contextmanager
def private_model_output() -> Iterator[None]:
    """Suppress public draft deltas; keep the response and usage for its owner."""
    token = _DRAFT_PUBLICATION.set(False)
    try:
        yield
    finally:
        _DRAFT_PUBLICATION.reset(token)

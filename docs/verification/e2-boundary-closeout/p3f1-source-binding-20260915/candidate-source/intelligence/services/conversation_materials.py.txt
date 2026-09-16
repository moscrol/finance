"""Material binding from authoritative message records, never prompt role text.

This is input provenance, not evidence eligibility or permission inheritance.
The caller supplies complete messages in its existing context window. Unknown
or partially retained history cannot be promoted to a user-material source.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from intelligence.services.user_task import MaterialRef, split_user_message

if TYPE_CHECKING:
    from intelligence.services.conversation_store import Message


@dataclass(frozen=True)
class ConversationMaterial:
    source_message_id: str
    ref: MaterialRef


@dataclass(frozen=True)
class ConversationMaterials:
    items: tuple[ConversationMaterial, ...] = ()
    unavailable: bool = False


def collect_conversation_materials(
    messages: Sequence[Message], *, unavailable: bool = False,
) -> ConversationMaterials:
    """Bind only completed user messages; body text cannot change their role.

    Same-content reposts keep the existing content-derived identity and first
    visible source coordinate. Material order is oldest -> newest, matching the
    legacy binding order. No IO, no summary parsing, no authority recovery.
    """
    items = []
    seen = set()
    for message in messages:
        if message.role != "user" or message.status != "completed":
            continue
        parts = split_user_message(message.content)
        for ref in parts.materials:
            if ref.material_id not in seen:
                items.append(ConversationMaterial(message.message_id, ref))
                seen.add(ref.material_id)
    return ConversationMaterials(tuple(items), unavailable=unavailable)

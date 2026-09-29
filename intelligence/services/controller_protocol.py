"""Pure wire contract for Turn Controller replies.

The canonical shape is the only one shown to the model. Two exact historical
shapes remain readable so old providers and captured replies can still route.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal


_CANONICAL_TYPES: dict[str, type | tuple[type, ...]] = {
    "route_id": str,
    "confidence": (int, float),
    "reason": str,
    "user_goal": str,
    "assumptions": list,
    "ambiguities": list,
}
CANONICAL_FIELDS = tuple(_CANONICAL_TYPES)
_LEGACY_TYPES: dict[str, type | tuple[type, ...]] = {
    "route_id": str,
    "subject": (str, type(None)),
    "timeframe": (str, type(None)),
    "confidence": (int, float),
    "reason": str,
}
_COMPAT_FIELDS = frozenset((*CANONICAL_FIELDS, "required_outputs"))
FIELD_INSTRUCTION = "键必须且只能是：" + ",".join(CANONICAL_FIELDS)


@dataclass(frozen=True)
class ControllerReply:
    route_id: str
    confidence: float
    reason: str
    shape: Literal["canonical", "legacy"]
    subject: str | None = None
    timeframe: str | None = None
    user_goal: str = ""
    assumptions: tuple[str, ...] = ()
    ambiguities: tuple[str, ...] = ()

    def alignment_json(self) -> str | None:
        """Return only validated, model-owned TaskFrame supplements."""
        if self.shape == "legacy":
            return None
        return json.dumps(
            {
                "user_goal": self.user_goal,
                "assumptions": self.assumptions,
                "ambiguities": self.ambiguities,
            },
            ensure_ascii=False,
        )


def parse_controller_reply(content: str) -> ControllerReply | None:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence is not None:
        text = fence.group(1)
    elif not text.startswith("{"):
        braces = re.search(r"\{.*\}", text, re.DOTALL)
        if braces is not None:
            text = braces.group(0)
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(value, dict):
        return None
    keys = frozenset(value)
    canonical = frozenset(CANONICAL_FIELDS)
    legacy = frozenset(_LEGACY_TYPES)
    if keys not in {canonical, _COMPAT_FIELDS, legacy}:
        return None
    field_types = _LEGACY_TYPES if keys == legacy else _CANONICAL_TYPES
    if any(not isinstance(value[key], expected) for key, expected in field_types.items()):
        return None
    if isinstance(value["confidence"], bool):
        return None
    if not value["reason"].strip():
        return None
    if keys == legacy:
        return ControllerReply(
            route_id=value["route_id"],
            confidence=float(value["confidence"]),
            reason=value["reason"].strip(),
            shape="legacy",
            subject=value["subject"],
            timeframe=value["timeframe"],
        )
    collections = ("assumptions", "ambiguities")
    if keys == _COMPAT_FIELDS:
        collections = (*collections, "required_outputs")
    if any(
        not isinstance(value[key], list)
        or any(not isinstance(item, str) for item in value[key])
        for key in collections
    ):
        return None
    return ControllerReply(
        route_id=value["route_id"],
        confidence=float(value["confidence"]),
        reason=value["reason"].strip(),
        shape="canonical",
        user_goal=value["user_goal"],
        assumptions=tuple(value["assumptions"]),
        ambiguities=tuple(value["ambiguities"]),
    )

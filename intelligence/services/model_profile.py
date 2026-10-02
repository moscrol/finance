"""Explicit resource presets, not model-strength or semantic-policy profiles.

``FWP_RESOURCE_PROFILE=standard|expanded`` selects resource defaults for any
model. It does not choose a model, grant a capability, or change task routing.
The legacy ``FWP_MODEL_PROFILE`` names remain resource-only aliases when the
new variable is absent: economy/standard -> standard, frontier -> expanded.
An explicit empty/unknown new setting stays standard; it must not fall through
and accidentally acquire an expanded legacy setting.

Only the legacy agent_research loop and upstream KB character budget consume
these defaults. Workbench Episode budgets still come from its research tier;
this module does NOT claim to extend that loop. An expanded resource budget
is an experimental input, not evidence of a stronger model or better answers.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass

ENV_RESOURCE_PROFILE = "FWP_RESOURCE_PROFILE"
ENV_MODEL_PROFILE = "FWP_MODEL_PROFILE"  # Deprecated resource-only compatibility.


@dataclass(frozen=True)
class ResourceProfile:
    name: str
    agent_loop_max_steps: int  # Legacy loop only; explicit ASK_AGENT_MAX_STEPS wins.
    evidence_char_scale: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


PROFILES: dict[str, ResourceProfile] = {
    "standard": ResourceProfile("standard", 4, 1.0),
    "expanded": ResourceProfile("expanded", 8, 1.5),
}
_LEGACY_ALIASES = {"standard": "standard", "economy": "standard", "frontier": "expanded"}


def active_profile_name() -> str:
    if ENV_RESOURCE_PROFILE in os.environ:
        raw = os.environ[ENV_RESOURCE_PROFILE].strip().lower()
        return raw if raw in PROFILES else "standard"
    raw = str(os.environ.get(ENV_MODEL_PROFILE) or "").strip().lower()
    return _LEGACY_ALIASES.get(raw, "standard")


def active_profile() -> ResourceProfile:
    """Read explicit resource configuration; never infer a tier from model identity."""
    return PROFILES[active_profile_name()]


def scale_chars(value: int, *, profile: ResourceProfile | None = None) -> int:
    scale = (profile or active_profile()).evidence_char_scale
    if scale == 1.0:
        return int(value)
    return max(1, int(round(value * scale)))

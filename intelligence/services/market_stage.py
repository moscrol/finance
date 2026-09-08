"""Canonical projection for the market-stage label.

The upstream market fact table contains both ``<stage>`` and
``<stage>阶段`` spellings. Historical labels must expose one stable value so
that a stage is not silently split into two statistical buckets.
"""

from __future__ import annotations


MARKET_STAGE_SUFFIX = "阶段"


def normalize_market_stage(value: object) -> str | None:
    """Return the canonical market-stage spelling while preserving missingness.

    ``None`` and whitespace-only values remain missing (``None``); a trailing
    ``阶段`` suffix is removed from non-empty values. The suffix rule is
    intentionally data-driven rather than a finite alias list so a newly
    introduced upstream stage gets the same canonical treatment.
    """

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(MARKET_STAGE_SUFFIX) and len(text) > len(MARKET_STAGE_SUFFIX):
        return text[: -len(MARKET_STAGE_SUFFIX)]
    return text

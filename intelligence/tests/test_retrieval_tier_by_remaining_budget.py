from __future__ import annotations

from intelligence.services import kb_rag


def test_four_seconds_selects_bm25() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("hybrid", 4.0)
    assert mode == "bm25"
    assert reason == "remaining_budget"


def test_incident_grant_selects_bm25() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("hybrid", 11.955)
    assert mode == "bm25"
    assert reason == "remaining_budget"


def test_twenty_seconds_keeps_hybrid() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("hybrid", 20.0)
    assert mode == "hybrid"
    assert reason is None


def test_already_bm25_is_not_labeled_degraded() -> None:
    mode, reason = kb_rag.select_mode_for_remaining("bm25", 4.0)
    assert mode == "bm25"
    assert reason is None

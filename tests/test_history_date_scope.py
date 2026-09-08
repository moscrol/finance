"""Natural Chinese ranges must enforce the same scope as full ISO dates."""

import pytest

from intelligence.services.historical_research.intent import infer_history_intent
from intelligence.tests.test_historical_research_episode import _registry


@pytest.mark.parametrize("window,start,end", [
    ("2024年9月2日至9月30日", "2024-09-02", "2024-09-30"),
    ("2026年8月5日至9月1日", "2026-08-05", "2026-09-01"),
    ("2025年8月1日到29日", "2025-08-01", "2025-08-29"),
    ("2024-09-02至09-30", "2024-09-02", "2024-09-30"),
    ("2024年9月2日至9月30", "2024-09-02", "2024-09-30"),
    ("2024年12月20日至2025年1月3日", "2024-12-20", "2025-01-03"),
])
def test_connected_ranges_preserve_explicit_window(window, start, end):
    intent = infer_history_intent(f"只研究{window}这波农业行情怎么走出来的")
    assert (intent.requested_start, intent.requested_end) == (start, end)
    assert intent.strict_window
    assert intent.window_error is None


@pytest.mark.parametrize("window", [
    "2024年9月2日至9月31日", "2024年9月20日至3日",
    "2024年12月20日至1月3日",
    "2024年9月2日至月底",
    "2024年9月2日",
])
def test_invalid_or_unstated_rollover_requires_clarification(window):
    intent = infer_history_intent(f"只研究{window}这波农业行情怎么走出来的")
    assert intent.strict_window
    assert intent.window_error


def test_separate_anchors_are_not_joined():
    intent = infer_history_intent("事后复盘2026年9月7日这波农业，与8月1日那波相比如何")
    assert intent.requested_start is None
    assert intent.requested_end is None


def test_abbreviated_range_rejects_query_before_engine(tmp_path, monkeypatch):
    from intelligence.services.historical_research.query import HistoryQuery

    registry, context, _ = _registry(tmp_path, "只研究2026年8月3日至4日这波农业行情怎么走出来的")

    def forbidden(*args, **kwargs):
        pytest.fail("out-of-scope query reached the engine")

    monkeypatch.setattr(HistoryQuery, "run", forbidden)
    with pytest.raises(ValueError, match="outside_authorized_scope"):
        registry.execute("history_query", {
            "operation": "inspect_history", "entity_codes": ["A.FP"],
            "start": "2026-08-01", "end": "2026-08-03",
        }, context=context, step_id="out-of-scope")
    assert context.history_results == []

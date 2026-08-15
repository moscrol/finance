"""对外 artifact 事件投影的唯一口径（第 5 步第 3 条）。"""

from __future__ import annotations

from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_projection import project_durable_events
from intelligence.services.research_tool_registry import TOOL_PRE_EXECUTE


def test_durable_events_project_field_for_field_unchanged() -> None:
    """形状就是 ``to_dict()`` 原样——投影层不裁剪也不改名。

    五个下游（orchestrator / stream_events / benchmark / normalize_harness_trace /
    dump_episode_receipts）按现有字段读，改形状等于一次无声的契约变更。
    """

    events = (
        EpisodeEvent(1, "task", {"question": "今天怎么看"}),
        EpisodeEvent(2, "tool_request", {"call_id": "c1", "name": "finance_query"}),
    )

    projection = project_durable_events(events)

    assert list(projection.events) == [event.to_dict() for event in events]
    assert not projection.has_anomalies
    assert projection.anomalies_to_dict() == {}


def test_live_events_never_reach_the_artifact_and_are_reported() -> None:
    """Live 车道挡在 artifact 之外，且**不静默**——异常进收据。

    今天 Live 事件根本进不了 ``ledger.events``，所以这条钉的是将来：第 4 条要动
    事件出口，"Live 悄悄漏进重放/评测口径"是最容易发生也最难发现的回归。
    """

    events = (
        EpisodeEvent(1, "task", {"question": "今天怎么看"}),
        EpisodeEvent(1, TOOL_PRE_EXECUTE, {"tool": "finance_query", "lane": "live"}),
    )

    projection = project_durable_events(events)

    assert [item["kind"] for item in projection.events] == ["task"]
    assert projection.dropped_live_kinds == (TOOL_PRE_EXECUTE,)
    assert projection.has_anomalies
    assert projection.anomalies_to_dict() == {"dropped_live_kinds": [TOOL_PRE_EXECUTE]}


def test_unregistered_kind_is_kept_but_flagged() -> None:
    """artifact 边界与发射边界的 fail 策略**故意相反**。

    发射边界（``lane_for``）对未登记 kind 抛错，因为那里抛错什么都不丢。这里已经
    是研究做完之后，抛错等于把一次完成的研究连同证据一起丢掉——所以保留事件，
    但把 kind 记进 ``unregistered_kinds``，让分类表的漂移看得见。
    """

    events = (
        EpisodeEvent(1, "task", {"question": "今天怎么看"}),
        EpisodeEvent(2, "brand_new_kind", {"whatever": 1}),
    )

    projection = project_durable_events(events)

    assert [item["kind"] for item in projection.events] == ["task", "brand_new_kind"]
    assert projection.unregistered_kinds == ("brand_new_kind",)
    assert projection.anomalies_to_dict() == {"unregistered_kinds": ["brand_new_kind"]}


def test_repeated_anomalous_kinds_are_deduplicated_in_order() -> None:
    """异常按 kind 去重保序：收据要能一眼看出"是哪几种"，不是刷屏。"""

    events = (
        EpisodeEvent(1, TOOL_PRE_EXECUTE, {"lane": "live"}),
        EpisodeEvent(2, TOOL_PRE_EXECUTE, {"lane": "live"}),
        EpisodeEvent(3, "task", {"question": "今天怎么看"}),
    )

    projection = project_durable_events(events)

    assert projection.dropped_live_kinds == (TOOL_PRE_EXECUTE,)
    assert [item["kind"] for item in projection.events] == ["task"]


def test_empty_events_project_to_empty_without_anomalies() -> None:
    projection = project_durable_events(())

    assert projection.events == ()
    assert not projection.has_anomalies

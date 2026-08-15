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


def _branch_event(sequence: int, kind: str, branch_id: str, **payload: object) -> EpisodeEvent:
    return EpisodeEvent(sequence, kind, {"branch_id": branch_id, **payload})


def test_paired_branch_events_report_no_anomaly() -> None:
    events = (
        _branch_event(1, "branch_started", "branch-1"),
        _branch_event(2, "branch_started", "branch-2"),
        _branch_event(3, "branch_completed", "branch-1", status="completed"),
        _branch_event(4, "branch_failed", "branch-2", status="failed"),
    )

    projection = project_durable_events(events)

    assert not projection.has_anomalies


def test_branch_started_without_terminal_is_reported() -> None:
    """成对性从「实现细节」变成「被断言的性质」（台账 §5.3-1）。

    今天它靠 ``_run_sub_research`` 末尾的未执行兜底循环成立。那个循环在将来的事件
    出口合流改写里一旦丢掉，成对性会静默失效而所有测试仍是绿的——这条就是为那一天
    准备的。
    """

    events = (
        _branch_event(1, "branch_started", "branch-1"),
        _branch_event(2, "branch_started", "branch-2"),
        _branch_event(3, "branch_completed", "branch-1", status="completed"),
    )

    projection = project_durable_events(events)

    assert projection.unpaired_branch_ids == ("branch-2",)
    assert projection.anomalies_to_dict() == {"unpaired_branch_ids": ["branch-2"]}


def test_branch_terminal_without_start_is_reported() -> None:
    """反方向也查：有终态却没起过，说明发射点漏了 started 或 branch_id 串了。"""

    events = (
        _branch_event(1, "branch_started", "branch-1"),
        _branch_event(2, "branch_completed", "branch-1", status="completed"),
        _branch_event(3, "branch_failed", "branch-9", status="failed"),
    )

    projection = project_durable_events(events)

    assert projection.orphan_branch_terminals == ("branch-9",)
    assert projection.unpaired_branch_ids == ()


def test_cancelled_branch_is_distinguishable_from_worker_exception() -> None:
    """台账 §5.3-2：没有 ``error`` 字段，这两种失败在事件流里完全同形。

    两者都是 ``branch_failed`` / ``status="failed"`` / ``gap_count=1``——能区分开
    的唯一依据就是 payload 里的 ``error``。
    """

    events = (
        _branch_event(1, "branch_started", "branch-1"),
        _branch_event(2, "branch_started", "branch-2"),
        _branch_event(
            3, "branch_failed", "branch-1", status="failed", gap_count=1,
            error="cancelled",
        ),
        _branch_event(
            4, "branch_failed", "branch-2", status="failed", gap_count=1,
            error="branch_worker_exception:TimeoutError",
        ),
    )

    projection = project_durable_events(events)

    assert not projection.has_anomalies
    failures = [
        item for item in projection.events if item["kind"] == "branch_failed"
    ]
    assert [item["payload"]["error"] for item in failures] == [
        "cancelled",
        "branch_worker_exception:TimeoutError",
    ]
    cancelled = [
        item for item in failures if item["payload"]["error"] == "cancelled"
    ]
    assert [item["payload"]["branch_id"] for item in cancelled] == ["branch-1"]

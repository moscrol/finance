"""E-008：实际菜单 → 持久 trace/SSE → 公开投影；不把授权写成执行成功。"""

from __future__ import annotations

import json

import pytest

from intelligence.api.app import _public_trace_step
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_progress import (
    RunEpisodeProgressPublisher,
    project_episode_progress,
)
from intelligence.services.run_store import RunStore


def _project(visible):
    progress = project_episode_progress(
        EpisodeEvent(
            3,
            "tool_menu",
            {
                "visible": visible,
                "hidden": ["news_search"],
                "allowed_capabilities": ["graph_lookup", "sub_research"],
                "provider": "secret-provider",
                "prompt": "secret-prompt",
            },
        )
    )
    assert progress is not None
    return progress


def test_actual_menu_not_allowed_capabilities_is_the_public_source():
    progress = _project(["derived_calculation", "finance_query"])
    assert progress.message == (
        "此步模型可调用工具：沙箱派生计算、本地结构化行情。"
        "授权不代表已调用或服务可用。"
    )
    public = _public_trace_step(
        {"name": progress.stage, "status": progress.status, "output_summary": progress.message}
    )
    assert public["output_summary"] == progress.message
    serialized = json.dumps(public, ensure_ascii=False)
    for forbidden in ("secret-", "derived_calculation", "news_search", "题材图谱", "子研究分支", "已取得"):
        assert forbidden not in serialized


def test_unrecognized_menu_names_are_not_leaked_or_claimed_absent():
    progress = _project(["sub_research", "secret-tool", "sub_research"])
    assert "子研究分支" in progress.message
    assert "未识别工具（不展示名称）" in progress.message
    assert "secret-tool" not in progress.message
    assert progress.message.count("子研究分支") == 1
    assert _public_trace_step(
        {"name": "planning", "output_summary": progress.message}
    )["output_summary"] == progress.message


def test_empty_menu_is_distinct_from_missing_or_invalid_snapshot():
    empty = _project([])
    assert empty.message == "此步未开放可调用工具。"
    for invalid in (None, "finance_query", {"finance_query": True}, [42], ["finance_query", None]):
        progress = _project(invalid)
        assert progress.message == "此步工具菜单未记录；不能推断可调用范围。"
        assert progress.message != empty.message


@pytest.mark.parametrize(
    "text",
    [
        "此步模型可调用工具：secret-tool。授权不代表已调用或服务可用。",
        "此步模型可调用工具：盘面快照、secret-tool。授权不代表已调用或服务可用。",
        "此步模型可调用工具：盘面快照。已全部调用成功。",
        "此步模型可调用工具：盘面快照。授权不代表已调用或服务可用。secret-prompt",
        "此步模型可调用工具：盘面快照、盘面快照。授权不代表已调用或服务可用。",
    ],
)
def test_public_boundary_rejects_forged_menu_prose(text):
    public = _public_trace_step({"name": "planning", "output_summary": text})
    assert public["output_summary"] != text
    assert "secret-" not in json.dumps(public)


def test_menu_and_call_have_distinct_replayable_public_steps(tmp_path):
    store = RunStore(user_id="menu-test", root=tmp_path / "runs")
    run = store.create_run("本轮哪些工具生效", "ask", session_id="conversation")
    publisher = RunEpisodeProgressPublisher(
        run_store=store,
        run_id=run.run_id,
        conversation_id="conversation",
        message_id="message",
    )
    menu = _project(["derived_calculation", "sub_research"])
    publisher.publish(menu)
    publisher.publish(menu)
    # 仅菜单存在不能冒称工具调用；重放也只应有一条。
    assert len(store.load_trace(run.run_id)) == 1
    call = project_episode_progress(
        EpisodeEvent(4, "tool_request", {"name": "derived_calculation"})
    )
    assert call is not None
    publisher.publish(call)
    trace = [_public_trace_step(step) for step in store.load_trace(run.run_id)]
    replay = [
        _public_trace_step(event["payload"]["step"])
        for event in store.load_stream_events(run.run_id)
    ]
    assert trace == replay
    assert trace[0]["output_summary"] == menu.message
    assert trace[1]["output_summary"] == "正在查沙箱派生计算。"
    assert all("已取得" not in step["output_summary"] for step in trace)


@pytest.mark.parametrize("coordinator_present", [True, False])
def test_real_episode_menu_includes_only_bound_tools_even_when_model_is_down(
    tmp_path, monkeypatch, coordinator_present
):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.research_contract import release_root_budget
    from intelligence.tests.test_sub_research_tool import (
        _CapturingCoordinator,
        _context,
        _frame,
        _market_registry,
        _successful_runner,
    )

    monkeypatch.setenv("WORKBENCH_TOOL_MENU_HIDE", "off")
    context = _context("max", allowed=("market_data", "derived_calculation", "sub_research"))
    coordinator = _CapturingCoordinator() if coordinator_present else None
    store = RunStore(user_id="bound-menu", root=tmp_path / "runs")
    run = store.create_run("查看授权工具", "ask", session_id="conversation")
    publisher = RunEpisodeProgressPublisher(
        run_store=store, run_id=run.run_id, conversation_id="conversation", message_id="message"
    )
    observed = []
    model_calls = []

    def sink(event):
        observed.append(event)
        progress = project_episode_progress(event)
        if progress is not None:
            publisher.publish(progress)

    class UnavailableModel:
        def complete(self, *, messages, tools, timeout):
            model_calls.append((tuple(observed), tools))
            raise RuntimeError("gateway unavailable")

    try:
        outcome = ContinuousAgentEpisode(
            UnavailableModel(), event_sink=sink, sub_research_coordinator=coordinator
        ).run(task_frame=_frame(), context=context, registry=_market_registry(_successful_runner))
        assert outcome.stop_reason == "model_unavailable"
        assert outcome.usage.tool_calls == 0
        # 断言放在运行器外，避免 AssertionError 被当成预期的模型不可用而吞掉。
        assert len(model_calls) == 1
        events_at_request, tools = model_calls[0]
        menus = [event for event in events_at_request if event.kind == "tool_menu"]
        assert len(menus) == 1
        names = [tool["function"]["name"] for tool in tools]
        assert list(menus[0].payload["visible"]) == names
        assert "derived_calculation" in names
        assert ("sub_research" in names) is coordinator_present
        if coordinator is not None:
            assert coordinator.calls == []
        # configure 的授权列表早于动态装配，本测试专门证明不能拿它当实际菜单。
        configure = next(e for e in observed if e.kind == "configure")
        assert "derived_calculation" not in configure.payload["authorized_tools"]
        text = "\n".join(
            _public_trace_step(step)["output_summary"] for step in store.load_trace(run.run_id)
        )
        assert "沙箱派生计算" in text
        assert ("子研究分支" in text) is coordinator_present
        assert "授权不代表已调用或服务可用" in text
        assert "已取得" not in text
    finally:
        release_root_budget(context.contract.task_id)

"""Durable / Live 车道分类表与 Live 出口的行为测试。

对应检阅裁定 D3 的条件②「分类落单表并**用测试钉住**」。
"""

from __future__ import annotations

import ast
from pathlib import Path
from threading import Barrier, Thread

import pytest

import intelligence.services.episode_event_lanes as lanes_module
from intelligence.services.agent_runtime import EpisodeEvent
from intelligence.services.episode_event_lanes import (
    DURABLE_EVENT_KINDS,
    LIVE_EVENT_KINDS,
    LiveEventSink,
    lane_for,
)
from intelligence.services.research_tool_registry import (
    TOOL_ERROR,
    TOOL_PRE_EXECUTE,
    TOOL_RESULT,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EMITTER_MARKERS = (
    "EpisodeEvent(",
    "_add_event(",
    "class _EpisodeLedger",
    "ledger.add(",
)


def _string_constants(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _string_constants(node.body) + _string_constants(node.orelse)
    return []


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _receiver_root(func: ast.AST) -> str | None:
    """``ledger.add`` / ``self.ledger.add`` / ``self.add`` 才算发射，``layers.add`` 不算。"""

    if not isinstance(func, ast.Attribute):
        return None
    value = func.value
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return None


def _kind_from_call(node: ast.Call, *, positional_index: int) -> list[str]:
    kinds: list[str] = []
    if len(node.args) > positional_index:
        kinds.extend(_string_constants(node.args[positional_index]))
    for keyword in node.keywords:
        if keyword.arg == "kind":
            kinds.extend(_string_constants(keyword.value))
    return kinds


def _production_emitter_paths() -> tuple[Path, ...]:
    root = _REPO_ROOT / "intelligence"
    return tuple(
        sorted(
            path
            for path in root.rglob("*.py")
            if "tests" not in path.parts
            and any(marker in path.read_text(encoding="utf-8") for marker in _EMITTER_MARKERS)
        )
    )


def _emitted_durable_kinds() -> set[str]:
    """穷尽扫生产发射 API 的字面量 kind，不扫测试、不扫 ``.add()`` 的其它用法。

    三种写法都算：``ledger.add("kind", ...)`` / ``_add_event("kind", ...)`` /
    ``EpisodeEvent(seq, "kind", ...)``，以及 ``if/else`` 里二选一的字面量。
    变量形参（``EpisodeEvent(seq, kind, ...)``）不贡献——那是出口本身。
    """

    kinds: set[str] = set()
    for path in _production_emitter_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if name == "_add_event":
                kinds.update(_kind_from_call(node, positional_index=0))
            elif name == "add" and _receiver_root(node.func) in {"ledger", "self"}:
                kinds.update(_kind_from_call(node, positional_index=0))
            elif name == "EpisodeEvent":
                kinds.update(_kind_from_call(node, positional_index=1))
    return kinds


def test_tool_stage_events_are_live_and_ledger_kinds_are_durable() -> None:
    """裁定条件②：``tool/*` 三事件归 Live，durable 侧的 kind 仍归 Durable。"""

    assert LIVE_EVENT_KINDS == {TOOL_PRE_EXECUTE, TOOL_RESULT, TOOL_ERROR}
    for kind in (TOOL_PRE_EXECUTE, TOOL_RESULT, TOOL_ERROR):
        assert lane_for(kind) == "live"

    # 抽样 durable 侧：重放日志与对账权威那一批必须留在 Durable。
    # finish 是终局事件，漏登记会被投影层第一天抓到——抽样里必须有它。
    for kind in ("task", "plan", "model_turn", "tool_request", "tool_result", "finish"):
        assert lane_for(kind) == "durable"

    # D6：branch_* 裁定归 Durable（证据来源 / 分支预算 / 成对身份）。
    for kind in ("branch_started", "branch_completed", "branch_failed", "branch_tool"):
        assert lane_for(kind) == "durable"

    # 两条车道不得相交——同一个 kind 走两条路就是双账。
    assert not (DURABLE_EVENT_KINDS & LIVE_EVENT_KINDS)


def test_unregistered_kind_fails_closed() -> None:
    """未登记的 kind 抛错，不许默默选一条车道。

    默默选 durable 会污染重放日志，默默选 live 会让事件人间蒸发；两种都要等很久
    才发现。抛出来的位置在 ``EpisodeScope.emit`` 的兜底之内，不影响主路径。
    """

    with pytest.raises(ValueError):
        lane_for("tool/definitely_not_registered")


def test_durable_kind_table_matches_every_runtime_emitter() -> None:
    """负面断言：表不多不少，正好等于三条 runtime 实际发出的 durable kind。

    投影挂在 ``ContinuousTurnAdapter`` 上，``continuous_glm`` / ``sdk_*`` /
    ``codex_headless`` 的 ``outcome.events`` 都走它。只 grep ``ledger.add``
    一种写法会漏 ``finish`` / ``configure`` / ``tool_closed`` 这类终局或旁路
    事件，也会把 payload 键（``phase`` / ``reason``）误收进表。
    """

    emitted = _emitted_durable_kinds()
    registered = set(DURABLE_EVENT_KINDS)

    missing = sorted(emitted - registered)
    stale = sorted(registered - emitted)
    assert missing == [], f"发射了但表里没有: {missing}"
    assert stale == [], f"表里有但没有任何发射点: {stale}"
    assert not (emitted & set(LIVE_EVENT_KINDS))


def test_live_sink_publishes_without_durable_sequence() -> None:
    """Live 事件自带独立编号空间并打 ``lane`` 标记，不占 durable 序号。"""

    published: list[EpisodeEvent] = []
    sink = LiveEventSink(published.append)

    sink.emit(TOOL_PRE_EXECUTE, {"tool": "finance_query"})
    sink.emit(TOOL_RESULT, {"tool": "finance_query", "status": "success"})

    assert [event.sequence for event in published] == [1, 2]
    assert [event.kind for event in published] == [TOOL_PRE_EXECUTE, TOOL_RESULT]
    assert all(event.payload["lane"] == "live" for event in published)
    assert published[0].payload["tool"] == "finance_query"
    assert sink.published_count == 2


def test_live_sink_refuses_durable_kinds() -> None:
    """durable 事件不得从 Live 旁路发出去——那会让重放日志缺事件且无人察觉。"""

    published: list[EpisodeEvent] = []
    sink = LiveEventSink(published.append)

    with pytest.raises(ValueError):
        sink.emit("tool_result", {"tool": "finance_query"})

    assert published == []


def test_live_sink_sequences_stay_unique_under_concurrent_emits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """并发 emit 时 Live 序号仍是 1..N 的排列。

    发射点在 8 worker 的共享工具线程池里，所以这条和 ``_EpisodeLedger`` 那条是
    同一个失败形状、不同的状态：那把锁保 durable 列表，保不到这里。

    同样注入确定性抢占（见 ``test_agent_episode`` 里那条的教训）：不撑开
    「读计数 → 写回」的窗口，CPython 的 5ms 时间片会让每个线程一口气跑完，
    抽掉锁也全绿——那种用例测的是调度器的运气。
    """

    from time import sleep

    real_episode_event = lanes_module.EpisodeEvent

    def preemptible_event(sequence: int, kind: str, payload: object) -> object:
        sleep(0.0005)
        return real_episode_event(sequence, kind, payload)

    monkeypatch.setattr(lanes_module, "EpisodeEvent", preemptible_event)

    published: list[object] = []
    publish_barrier = Barrier(8)
    sink = LiveEventSink(published.append)
    errors: list[BaseException] = []

    def hammer() -> None:
        try:
            publish_barrier.wait()
            for _ in range(10):
                sink.emit(TOOL_PRE_EXECUTE, {"tool": "finance_query"})
        except BaseException as exc:  # 线程里的异常不会自己传到主线程
            errors.append(exc)

    threads = [Thread(target=hammer) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    sequences = sorted(event.sequence for event in published)
    assert sequences == list(range(1, 81)), "Live 序号重了或跳了"
    assert sink.published_count == 80

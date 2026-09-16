"""竞态⑥：两个 begin_work 同 Handle（INV-R6）。

``begin_work`` 是工作单元的门：取消 / 关闭只挡**未派发**的工作。两序：第二个工作单元在
取消之前到达 → 两个都接纳（in_flight=2）；在 ``request_cancel``（或 ``close``）之后到达 →
第二个被拒且留收据，第一个照常排空到 ``drained``。
"""

from __future__ import annotations

import pytest

from intelligence.services.runtime_handle import (
    RuntimeHandle,
    RuntimeHandleCancelled,
    RuntimeHandleClosed,
)


def _notes(handle: RuntimeHandle) -> list[str]:
    return [str(row["event"]) for row in handle.dump()["receipts"] if row["kind"] == "note"]


def _handle(task_id: str) -> RuntimeHandle:
    handle = RuntimeHandle(episode_id=task_id)
    handle.mark_started()
    handle.mark_running()
    return handle


def test_order_a_second_begin_work_before_cancel_is_admitted() -> None:
    handle = _handle("race-begin-a")
    handle.begin_work("run")
    handle.begin_work("resume")

    dump = handle.dump()
    assert dump["in_flight"] == 2
    assert _notes(handle).count("work_begun") == 2
    assert dump["state"] == "running"

    handle.end_work("resume")
    handle.end_work("run")
    assert handle.dump()["in_flight"] == 0
    assert handle.state == "running"


def test_order_b_second_begin_work_after_cancel_is_denied_and_first_drains() -> None:
    handle = _handle("race-begin-b")
    handle.begin_work("run")
    handle.request_cancel("user_stop", cause="user")
    assert handle.state == "draining"  # 有在飞工作，取消即排空

    with pytest.raises(RuntimeHandleCancelled):
        handle.begin_work("resume")
    assert "work_denied_cancelled" in _notes(handle)
    assert handle.dump()["in_flight"] == 1

    handle.end_work("run")
    assert "drained" in _notes(handle)
    assert handle.dump()["in_flight"] == 0
    assert handle.dump()["cancel_cause"] == "user"

    # close 之后同理：拒绝并留 work_denied_closed；重复 close 无观测差异。
    handle.close("cleanup")
    with pytest.raises(RuntimeHandleClosed):
        handle.begin_work("resume")
    assert "work_denied_closed" in _notes(handle)
    before = len(handle.dump()["receipts"])
    handle.close("cleanup")
    assert len(handle.dump()["receipts"]) == before

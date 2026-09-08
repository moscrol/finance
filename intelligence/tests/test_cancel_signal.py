"""CancelSignal：类型化取消、first cause wins、与旧谓词接缝兼容（工单 #28 步骤 B）。"""

from __future__ import annotations

from threading import Barrier, Thread

import pytest

from intelligence.services.cancel_signal import CANCEL_CAUSES, CancelSignal
from intelligence.services.runtime_handle import RuntimeHandle


def test_fresh_signal_is_not_requested_and_is_callable() -> None:
    signal = CancelSignal()
    assert signal() is False and signal.requested is False
    assert signal.cause is None and signal.detail == ""
    assert signal.snapshot() == {"requested": False, "cause": None, "detail": ""}


def test_first_cause_wins() -> None:
    signal = CancelSignal()
    assert signal.request("hook", "guard said no") is True
    assert signal.request("user") is False
    assert signal() is True
    assert signal.snapshot() == {"requested": True, "cause": "hook", "detail": "guard said no"}


def test_unknown_cause_is_rejected() -> None:
    with pytest.raises(ValueError):
        CancelSignal().request("because")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        CancelSignal(upstream_cause="because")  # type: ignore[arg-type]
    assert CANCEL_CAUSES == {"user", "parent", "hook", "deadline", "disposed"}


def test_bare_predicate_upstream_is_folded_lazily_with_default_cause() -> None:
    """裸谓词上游：首次观测为真的那一刻记原因（默认 user），与 RuntimeHandle 同口径。"""

    flag = {"on": False}
    signal = CancelSignal.coerce(lambda: flag["on"])
    assert signal() is False and signal.cause is None
    flag["on"] = True
    assert signal() is True
    assert signal.cause == "user" and signal.detail == "upstream_signal"


def test_coerce_returns_existing_signal_and_wraps_none() -> None:
    signal = CancelSignal()
    assert CancelSignal.coerce(signal) is signal
    assert CancelSignal.coerce(None)() is False


def test_child_records_parent_cause_when_parent_fires_and_own_cause_otherwise() -> None:
    parent = CancelSignal()
    child = parent.child()
    assert child() is False
    parent.request("user")
    assert child() is True and child.cause == "parent"

    own = CancelSignal().child()
    own.request("deadline", "branch clock")
    assert own.cause == "deadline"


def test_broken_upstream_predicate_is_not_a_cancellation() -> None:
    def boom() -> bool:
        raise RuntimeError("predicate exploded")

    signal = CancelSignal(boom)
    assert signal() is False and signal.cause is None


def test_concurrent_requests_settle_on_exactly_one_cause() -> None:
    signal = CancelSignal()
    barrier = Barrier(4)
    wins: list[bool] = []

    def worker(cause: str) -> None:
        barrier.wait(timeout=2.0)
        wins.append(signal.request(cause))  # type: ignore[arg-type]

    threads = [Thread(target=worker, args=(c,)) for c in ("user", "parent", "hook", "disposed")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)

    assert wins.count(True) == 1
    assert signal.cause in CANCEL_CAUSES


def test_runtime_handle_copies_cause_from_signal_upstream() -> None:
    signal = CancelSignal()
    handle = RuntimeHandle(episode_id="ep-1", upstream_cancelled=signal)
    handle.mark_started()
    signal.request("parent", "父 episode 取消")

    assert handle.is_cancel_requested() is True
    dump = handle.dump()
    assert dump["cancel_cause"] == "parent" and dump["cancel_reason"] == "upstream_signal"


def test_runtime_handle_direct_request_keeps_first_cause() -> None:
    handle = RuntimeHandle(episode_id="ep-2")
    handle.mark_started()
    handle.request_cancel("api", cause="user")
    handle.request_cancel("late", cause="disposed")

    dump = handle.dump()
    assert dump["cancel_cause"] == "user" and dump["cancel_reason"] == "api"
    with pytest.raises(ValueError):
        RuntimeHandle(episode_id="ep-3").request_cancel("x", cause="whatever")  # type: ignore[arg-type]

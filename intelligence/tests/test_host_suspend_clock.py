"""主机睡眠（合盖）与 monotonic 截止时钟的对账：只补可观测，不改截止语义。

2026-09-27 21:13–21:52 生产 8792（deploy-probe，run_20260927_211317_791596）：turn-3 的
``model_intent`` 与 ``model_turn`` 墙钟隔 2320s 才报 LLMDeadlineExceeded，被当成「连接
卡死、绝对截止没切断」去查。``pmset -g log``：21:14:20 合盖睡眠，21:51:57 开盖唤醒，
中间只有两次 2 秒 DarkWake，共睡 2253s；下一轮入场余量说明预算只走了 75.2s。截止按
time.monotonic()（macOS 上是 mach_absolute_time）计、睡眠时停走——传输层按醒着的时间
守住了 75 秒，缺的是事件上看不出主机睡过。停滞 / 滴流不越窗由
``test_llm_timeout_diagnostic`` 的真实本地端点场景守。

钉住的契约：

1. ``host_suspended_since`` 只数 time.monotonic() 漏掉的那段；平台量不到时是 None；
2. LLM 调用记录带 ``host_suspended_seconds``，``elapsed_ms`` 仍按 monotonic（成败两路）。
"""

from __future__ import annotations

import json
import time

import pytest

from intelligence.services import llm_http_transport, llm_refine

# 墙钟 2320s − 预算走的 75s；pmset 记 2253s，差的 8s 是进出睡眠的过渡时间。
LID_CLOSED_SECONDS = 2245.0


class _SuspendClock:
    """含睡眠的时钟 = time.monotonic() + 已睡秒数；``close_lid`` 模拟一次合盖。"""

    def __init__(self) -> None:
        self.slept = 0.0

    def __call__(self) -> float:
        return time.monotonic() + self.slept

    def close_lid(self, seconds: float = LID_CLOSED_SECONDS) -> None:
        self.slept += seconds


@pytest.fixture
def suspend_clock(monkeypatch) -> _SuspendClock:
    clock = _SuspendClock()
    monkeypatch.setattr(llm_http_transport, "_suspend_inclusive_clock", clock)
    return clock


class _Response:
    def __init__(self, body: dict) -> None:
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def test_suspended_seconds_count_only_what_monotonic_missed(suspend_clock) -> None:
    anchor = llm_http_transport.host_suspended_total()
    time.sleep(0.05)
    assert llm_http_transport.host_suspended_since(anchor) == 0.0
    suspend_clock.close_lid()
    assert llm_http_transport.host_suspended_since(anchor) == LID_CLOSED_SECONDS


def test_suspended_seconds_are_unknown_without_a_suspend_inclusive_clock(monkeypatch) -> None:
    monkeypatch.setattr(llm_http_transport, "_SUSPEND_INCLUSIVE_CLOCK_ID", None)
    assert llm_http_transport.host_suspended_total() is None
    # 量不到就是 None，不能冒充 0.0「确认没睡」。
    assert llm_http_transport.host_suspended_since(None) is None
    assert llm_http_transport.host_suspended_since(12.5) is None


@pytest.mark.skipif(
    llm_http_transport._SUSPEND_INCLUSIVE_CLOCK_ID is None,
    reason="平台没有含睡眠的单调时钟",
)
def test_real_clocks_agree_while_the_host_is_awake() -> None:
    # 「睡眠时继续走」没法在测试里让本机真睡一觉来验，靠 pmset 那次生产实测；
    # 这里只守醒着时两钟同速（选错时钟 / 单位会在 0.2 秒里就露馅）。
    anchor = llm_http_transport.host_suspended_total()
    time.sleep(0.2)
    assert llm_http_transport.host_suspended_since(anchor) < 1.0


@pytest.mark.parametrize("outcome", ["success", "deadline"])
def test_call_record_shows_host_sleep_while_elapsed_stays_on_monotonic(
    monkeypatch, suspend_clock, outcome,
) -> None:
    def urlopen(request, timeout=0.0, **_kwargs):
        suspend_clock.close_lid()
        if outcome == "deadline":
            raise llm_http_transport.HTTPDeadlineExceeded()
        return _Response({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", urlopen)
    provider = llm_refine.LLMProvider("glm", "secret", "https://glm.invalid/v1", "glm-5.3")
    with llm_refine.call_ledger_scope() as ledger:
        if outcome == "deadline":
            with pytest.raises(llm_refine.LLMDeadlineExceeded):
                llm_refine._post_chat(provider, [{"role": "user", "content": "ping"}], timeout=75.0)
        else:
            llm_refine._post_chat(provider, [{"role": "user", "content": "ping"}], timeout=75.0)
    (record,) = ledger.summary()["records"]
    assert record["status"] == ("failed" if outcome == "deadline" else "success")
    assert record["host_suspended_seconds"] == LID_CLOSED_SECONDS
    # 睡眠即暂停：这次尝试的耗时与截止都不含睡掉的那段。
    assert record["elapsed_ms"] < 5_000

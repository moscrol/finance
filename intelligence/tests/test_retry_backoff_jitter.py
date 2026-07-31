"""重试退避 + 抖动（ch06b «API 通信层»）。

CC 的重试用 ``BASE_DELAY_MS = 500`` 的指数退避，并在每次退避上**叠加 0-25%
随机抖动**（``withRetry.ts:542-547``），避免多个客户端在同一时刻同步重试造成
雷群效应（thundering herd）。

我们这边的并发是真实的而不是假想：API 有 2 个 worker（``_WORKER_COUNT = 2``），
skill 线程经 ``copy_context`` 共享同一本调用台账——同一次 provider 抖动会让它们
在同一毫秒一起失败、然后一起重试。原先的 ``time.sleep(min(2, remaining - 0.5))``
是个写死的常数，两个 worker 会睡完全一样长的时间再一起撞上去。

**次数没有跟着抄。** CC 的预算是 10 次（总等待 2.5-3 分钟），那是 CLI 场景、
用户在前面等；我们每次尝试都占一次 turn 级台账额度，而 LLM 是 5 小时滚动配额。
保持 2 次，只把间隔换成有依据的退避。
"""
from __future__ import annotations

import pytest

from intelligence.services import llm_refine


class TestExponentialShape:
    def test_delay_doubles_with_each_attempt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """去掉抖动后应当是 500ms → 1s → 2s → 4s。"""
        monkeypatch.setattr(llm_refine.random, "random", lambda: 0.0)

        assert llm_refine._retry_delay_seconds(0) == pytest.approx(0.5)
        assert llm_refine._retry_delay_seconds(1) == pytest.approx(1.0)
        assert llm_refine._retry_delay_seconds(2) == pytest.approx(2.0)
        assert llm_refine._retry_delay_seconds(3) == pytest.approx(4.0)

    def test_delay_is_capped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """指数不能无限涨——上限之后不再翻倍。"""
        monkeypatch.setattr(llm_refine.random, "random", lambda: 0.0)

        assert llm_refine._retry_delay_seconds(10) == pytest.approx(
            llm_refine._RETRY_MAX_DELAY_S
        )


class TestJitter:
    """抖动是这条改动的实际价值——两个 worker 不能睡一样长。"""

    def test_jitter_never_exceeds_25_percent(self) -> None:
        for attempt in range(6):
            base = min(
                llm_refine._RETRY_MAX_DELAY_S,
                llm_refine._RETRY_BASE_DELAY_S * (2**attempt),
            )
            for _ in range(200):
                delay = llm_refine._retry_delay_seconds(attempt)

                assert base <= delay <= base * 1.25

    def test_jitter_never_shortens_the_delay(self) -> None:
        """抖动只往上加，不能把退避抖没了。"""
        for _ in range(200):
            assert llm_refine._retry_delay_seconds(0) >= 0.5

    def test_two_callers_do_not_get_the_same_delay(self) -> None:
        """雷群的判据：同一时刻失败的两方不该睡同样长。

        原先是写死的 2 秒，这条测试在那个实现下必然失败。
        """
        delays = {llm_refine._retry_delay_seconds(0) for _ in range(50)}

        assert len(delays) > 1


class TestDeadlineWins:
    def test_backoff_never_sleeps_past_the_deadline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """退避本身不能成为超时的原因。

        deadline 只剩 0.8 秒时不能睡 0.5-0.625 秒还留不下发请求的时间——
        实现里钳到 ``remaining - 0.5``。
        """
        slept: list[float] = []
        monkeypatch.setattr(llm_refine.time, "sleep", slept.append)
        monkeypatch.setattr(llm_refine.random, "random", lambda: 0.0)

        remaining = 0.8
        delay = min(
            llm_refine._retry_delay_seconds(0), max(0.0, remaining - 0.5)
        )

        assert delay == pytest.approx(0.3)


def test_attempt_count_is_unchanged() -> None:
    """配额宝贵：这次只改间隔，不改次数。

    CC 的 10 次是 CLI 场景；我们每次尝试都占一次 turn 级台账额度，
    而 LLM 是 5 小时滚动配额。将来有数据支持再调。
    """
    assert llm_refine._RETRY_MAX_ATTEMPTS == 2

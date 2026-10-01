"""429 有界退避（2026-10-01 质检 P0②）。

此前 agent 循环只认 502/503/504/超时，429 一次不等；合成路径遇任何 HTTP 错误直接降级。
lessons 09-09：0.6 秒连撞三次 429 即放弃；网关冷却可达 4939 秒。这里钉住：
读服务商时长、等得起才等、等不起立刻交出原因、可取消、不睡穿截止时间。
"""

from __future__ import annotations

import email.message
import io
import urllib.error

import pytest

from intelligence.runtime import glm_agent_runtime
from intelligence.runtime.glm_agent_runtime import GLMModelClient
from intelligence.services import llm_refine
from intelligence.services.llm_refine import LLMProvider, http_failure_text, rate_limit_retry_delay


def _http_error(code: int, *, retry_after: str | None = None, body: str = "") -> urllib.error.HTTPError:
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://x.invalid", code, "err", headers, io.BytesIO(body.encode()))


def _provider(name: str = "glm") -> LLMProvider:
    return LLMProvider(name=name, api_key="k", base_url=f"https://{name}.invalid/v1", model="m")


# --- 原因串 -----------------------------------------------------------------

def test_failure_text_carries_retry_after_header() -> None:
    assert http_failure_text(_http_error(429, retry_after="7")) == "LLM 调用 HTTP 429（retry_after=7s）"


def test_failure_text_reads_gateway_reset_seconds_from_body() -> None:
    body = '{"error": {"code": "model_cooldown", "reset_seconds": 12.5}}'
    assert http_failure_text(_http_error(429, body=body), "LLM 合成") == "LLM 合成 HTTP 429（retry_after=12.5s）"


def test_failure_text_without_hint_and_non_429_keep_old_format() -> None:
    assert http_failure_text(_http_error(429, retry_after="Wed, 01 Oct 2026 07:28:00 GMT")) == "LLM 调用 HTTP 429"
    assert http_failure_text(_http_error(503, retry_after="7")) == "LLM 调用 HTTP 503"
    # 下游分类器照旧认得出
    assert llm_refine.stable_llm_fallback_reason("LLM 调用 HTTP 429（retry_after=7s）") == "provider_rate_limited"


# --- 等多久 -----------------------------------------------------------------

def test_delay_honours_provider_hint_and_only_jitters_later() -> None:
    reason = "LLM 调用 HTTP 429（retry_after=7s）"
    assert rate_limit_retry_delay(reason, attempt=0, remaining=60, rand=lambda: 0.0) == 7.0
    assert rate_limit_retry_delay(reason, attempt=0, remaining=60, rand=lambda: 1.0) == pytest.approx(8.75)


def test_delay_falls_back_to_exponential_backoff() -> None:
    reason = "LLM 调用 HTTP 429"
    got = [rate_limit_retry_delay(reason, attempt=a, remaining=60, rand=lambda: 0.0) for a in range(4)]
    assert got == [0.5, 1.0, 2.0, None]  # 第 4 次不再等


@pytest.mark.parametrize(
    ("reason", "remaining"),
    [
        ("LLM 调用 HTTP 503", 60),  # 不是 429：不归这条路径管
        ("LLM 调用 HTTP 429（retry_after=4939s）", 99999),  # 网关整体冷却：不等
        ("LLM 调用 HTTP 429（retry_after=7s）", 10),  # 等完剩不下 5 秒给重试本身
        (None, 60),
    ],
)
def test_delay_refuses_when_not_worth_waiting(reason, remaining) -> None:
    assert rate_limit_retry_delay(reason, attempt=0, remaining=remaining, rand=lambda: 0.0) is None


# --- agent 循环 ---------------------------------------------------------------

class _FakeClock:
    """只替换被测模块的 ``time``：睡眠瞬时完成、单调时钟随之前进，不碰全局。"""

    def __init__(self, sleeps: list[float]) -> None:
        self.now = 1000.0
        self.sleeps = sleeps

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _use_fake_clock(monkeypatch, sleeps: list[float]) -> _FakeClock:
    clock = _FakeClock(sleeps)
    monkeypatch.setattr(glm_agent_runtime, "time", clock)
    return clock


def _scripted(monkeypatch, replies, sleeps):
    calls = []

    def chat_with_tools(**kwargs):
        calls.append(kwargs["timeout"])
        return replies[min(len(calls), len(replies)) - 1]

    monkeypatch.setattr(llm_refine, "chat_with_tools", chat_with_tools)
    monkeypatch.setattr(llm_refine.random, "random", lambda: 0.0)
    _use_fake_clock(monkeypatch, sleeps)
    return calls


def test_agent_loop_waits_hint_then_retries_same_provider(monkeypatch) -> None:
    p = _provider()
    sleeps: list[float] = []
    calls = _scripted(
        monkeypatch,
        [(None, p, "LLM 调用 HTTP 429（retry_after=2s）"), ({"content": "ok", "tool_calls": []}, p, "")],
        sleeps,
    )
    turn = GLMModelClient(providers=(p,)).complete(messages=[], tools=[], timeout=60)
    assert turn.content == "ok" and turn.error == ""
    assert len(calls) == 2 and turn.provider_attempts == 2
    assert sum(sleeps) == pytest.approx(2.0)
    assert max(sleeps) <= 0.2 + 1e-9  # 分片睡，才能及时响应取消
    assert turn._provider_trace[0]["rate_limit_wait_s"] == pytest.approx(2.0)


def test_agent_loop_gives_up_immediately_on_long_cooldown(monkeypatch) -> None:
    p = _provider()
    sleeps: list[float] = []
    calls = _scripted(monkeypatch, [(None, p, "LLM 调用 HTTP 429（retry_after=4939s）")], sleeps)
    turn = GLMModelClient(providers=(p,)).complete(messages=[], tools=[], timeout=60)
    assert len(calls) == 1 and sleeps == []
    assert "HTTP 429" in turn.error


def test_agent_loop_retry_count_is_bounded(monkeypatch) -> None:
    p = _provider()
    sleeps: list[float] = []
    calls = _scripted(monkeypatch, [(None, p, "LLM 调用 HTTP 429")], sleeps)
    turn = GLMModelClient(providers=(p,)).complete(messages=[], tools=[], timeout=60)
    assert len(calls) == 1 + llm_refine.RATE_LIMIT_MAX_RETRIES
    assert "HTTP 429" in turn.error


def test_agent_loop_prefers_next_provider_over_waiting(monkeypatch) -> None:
    a, b = _provider("glm"), _provider("openai")
    seen: list[str] = []
    sleeps: list[float] = []

    def chat_with_tools(**_kwargs):
        name = llm_refine.detect_provider().name
        seen.append(name)
        if name == "glm":
            return None, a, "LLM 调用 HTTP 429（retry_after=2s）"
        return {"content": "ok", "tool_calls": []}, b, ""

    monkeypatch.setattr(llm_refine, "chat_with_tools", chat_with_tools)
    _use_fake_clock(monkeypatch, sleeps)
    turn = GLMModelClient(providers=(a, b)).complete(messages=[], tools=[], timeout=60)
    assert seen == ["glm", "openai"] and sleeps == [] and turn.content == "ok"


def test_agent_loop_wait_is_cancellable(monkeypatch) -> None:
    p = _provider()
    cancelled = {"v": False}
    sleeps: list[float] = []

    def chat_with_tools(**_kwargs):
        return None, p, "LLM 调用 HTTP 429（retry_after=3s）"

    monkeypatch.setattr(llm_refine, "chat_with_tools", chat_with_tools)
    clock = _use_fake_clock(monkeypatch, sleeps)
    real_sleep = clock.sleep

    def sleep_then_cancel(s):
        real_sleep(s)
        cancelled["v"] = True  # 第一片睡完用户就点了取消

    clock.sleep = sleep_then_cancel
    client = GLMModelClient(providers=(p,), is_cancelled=lambda: cancelled["v"])
    turn = client.complete(messages=[], tools=[], timeout=60)
    assert len(sleeps) == 1 and turn.error == "cancelled"

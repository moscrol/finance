"""HTTP 429 限流：按服务端提示等一次再试，且只等一次、只在值得时等。

背景（docs/lessons_learned.md 2026-09-09「六题串行连发」）：网关连续 429 时 runtime
0.6 秒内连打三次就放弃，冷却提示被丢掉；读数里「被限流」和「模型能力不行」于是
混成同一个 ``model_unavailable``。这里钉住修复后的契约：

* 只认 429，其余 HTTP 码照旧不重试；
* 服务端给了 ``Retry-After`` / ``retry-after-ms`` 就按它等，没给按默认值加抖动；
* 每个 provider 每次调用最多多试一次；要等太久或等完剩不下一次可行调用就不等，
  并把服务端要求的秒数写进失败原因，且原因仍归到 ``provider_rate_limited``；
* 流式已吐字后绝不重放；用户取消时立刻停；预算满了不白等；
* 429 **不**进 ``TRANSIENT_MODEL_ERROR_MARKERS``（那条链无间隔连打三次）。

``_sleep_for_rate_limit`` 全部被替换成记账函数，测试不真睡。
"""

from __future__ import annotations

import json
import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import Message
from email.utils import format_datetime

import pytest

from intelligence.services import agent_runtime, llm_refine

PROVIDER = llm_refine.LLMProvider("fixture", "secret", "https://example.invalid/v1", "requested")
SECOND = llm_refine.LLMProvider("second", "secret", "https://other.invalid/v1", "other")
MESSAGES = [{"role": "user", "content": "question"}]


class Response:
    def __init__(self, payload: object) -> None:
        self.body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.headers: dict[str, str] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body

    def __iter__(self):
        return iter(self.body.splitlines(keepends=True))

    def close(self):
        return None


def _body(content: str = "answer") -> dict:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ]
    }


def _sse(content: str = "answer") -> bytes:
    events = [
        {"choices": [{"delta": {"content": content[:2]}}]},
        {"choices": [{"delta": {"content": content[2:]}, "finish_reason": "stop"}]},
    ]
    return ("".join(f"data: {json.dumps(e)}\n" for e in events) + "data: [DONE]\n").encode()


def _http_error(code: int = 429, headers: object = None) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid", code, "error", headers or {}, None)


class _Script:
    """按顺序吐出脚本里的结果：异常就抛，其余当响应体返回。"""

    def __init__(self, *steps: object) -> None:
        self.steps = list(steps)
        self.calls: list[str] = []

    def __call__(self, request, timeout=0.0, **_kwargs):
        self.calls.append(request.full_url)
        step = self.steps.pop(0) if len(self.steps) > 1 else self.steps[0]
        if isinstance(step, BaseException):
            raise step
        return Response(step)


@pytest.fixture
def sleeps(monkeypatch):
    recorded: list[float] = []

    def fake_sleep(seconds, is_cancelled=None):
        recorded.append(round(seconds, 3))
        return True

    monkeypatch.setattr(llm_refine, "_sleep_for_rate_limit", fake_sleep)
    return recorded


def _install(monkeypatch, script: _Script, providers=(PROVIDER,)) -> None:
    monkeypatch.setattr(llm_refine, "detect_providers", lambda *_a, **_k: providers)
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_a, **_k: providers[0])
    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", script)


# ---------------------------------------------------------------- 读响应头


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Retry-After": "7"}, 7.0),
        ({"retry-after": "2.5"}, 2.5),
        ({"Retry-After-Ms": "1500"}, 1.5),
        # 两个都给时毫秒更精确，优先
        ({"Retry-After": "9", "retry-after-ms": "1200"}, 1.2),
        ({"Retry-After": "soon"}, None),
        ({"Retry-After": "-5"}, None),
        ({"Retry-After": "inf"}, None),
        ({"Retry-After": "nan"}, None),
        ({}, None),
        (None, None),
    ],
)
def test_rate_limit_hint_reads_seconds_and_millis(headers, expected):
    assert llm_refine.rate_limit_hint_seconds(headers) == expected


def test_rate_limit_hint_reads_email_message_headers_case_insensitively():
    # 生产里的 HTTPError.headers 是 llm_http_transport._headers() 重建的 Message。
    message = Message()
    message["RETRY-AFTER"] = "3"
    assert llm_refine.rate_limit_hint_seconds(message) == 3.0


def test_rate_limit_hint_reads_http_date():
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    hint = llm_refine.rate_limit_hint_seconds({"Retry-After": format_datetime(future, usegmt=True)})
    assert hint is not None and 25.0 <= hint <= 31.0
    past = datetime.now(timezone.utc) - timedelta(seconds=30)
    assert llm_refine.rate_limit_hint_seconds({"Retry-After": format_datetime(past, usegmt=True)}) == 0.0


# ---------------------------------------------------------------- 要不要等


def test_retry_wait_only_for_429_and_only_once():
    assert llm_refine.rate_limit_retry_wait(_http_error(503), remaining=60, retries_used=0) is None
    assert llm_refine.rate_limit_retry_wait(TimeoutError(), remaining=60, retries_used=0) is None
    limited = _http_error(429, {"Retry-After": "3"})
    assert llm_refine.rate_limit_retry_wait(limited, remaining=60, retries_used=0) == 3.0
    assert llm_refine.rate_limit_retry_wait(limited, remaining=60, retries_used=1) is None


def test_retry_wait_defaults_with_bounded_jitter_when_no_hint():
    wait = llm_refine.rate_limit_retry_wait(_http_error(429), remaining=60, retries_used=0)
    base = llm_refine._RATE_LIMIT_DEFAULT_WAIT_S
    assert wait is not None and base <= wait <= base * (1 + llm_refine._RETRY_JITTER)


def test_retry_wait_refuses_long_cooldown_and_starved_budget():
    # 2026-09-09 实测的「冷却 4939 秒」：要换时段，不是等一等能好的。
    assert (
        llm_refine.rate_limit_retry_wait(
            _http_error(429, {"Retry-After": "4939"}), remaining=10_000, retries_used=0
        )
        is None
    )
    # 等完剩下的时间不够一次可行调用（MIN_VIABLE_LLM_SECONDS）也不等。
    floor = llm_refine._rate_limit_min_call_seconds()
    tight = _http_error(429, {"Retry-After": "5"})
    assert llm_refine.rate_limit_retry_wait(tight, remaining=floor + 4.9, retries_used=0) is None
    assert llm_refine.rate_limit_retry_wait(tight, remaining=floor + 5.1, retries_used=0) == 5.0


# ---------------------------------------------------------------- 原因串与分类


@pytest.mark.parametrize(
    "template",
    [
        "LLM 调用 HTTP 429{suffix}",
        "LLM 合成 HTTP 429{suffix}，已降级为模板",
        "LLM 流式合成 HTTP 429{suffix}，已降级为模板",
        "所有已配置 LLM provider 均失败（fixture:HTTP 429{suffix}；second:HTTP 429{suffix}）",
    ],
)
def test_reason_suffix_keeps_rate_limited_classification(template):
    suffix = llm_refine.rate_limit_reason_suffix(_http_error(429, {"Retry-After": "4939"}))
    assert suffix == "（限流：服务端要求 4939 秒后再试）"
    reason = template.format(suffix=suffix)
    assert llm_refine.stable_llm_fallback_reason(reason) == "provider_rate_limited"
    # 限流不是「再试一次大概率就好」：进了瞬态名单，GLMModelClient 会无间隔连打三次。
    assert agent_runtime.is_transient_model_error(reason) is False


def test_reason_suffix_is_empty_without_hint_or_for_other_codes():
    assert llm_refine.rate_limit_reason_suffix(_http_error(429)) == ""
    assert llm_refine.rate_limit_reason_suffix(_http_error(503, {"Retry-After": "3"})) == ""
    assert llm_refine.rate_limit_reason_suffix(ValueError()) == ""
    # 小数秒向上取整，且至少 1 秒
    assert "1 秒" in llm_refine.rate_limit_reason_suffix(_http_error(429, {"retry-after-ms": "10"}))


# ---------------------------------------------------------------- 真调用路径


def test_chat_with_tools_waits_once_then_succeeds(monkeypatch, sleeps):
    script = _Script(_http_error(429, {"Retry-After": "3"}), _body("answer"))
    _install(monkeypatch, script)
    with llm_refine.call_ledger_scope(max_calls=4) as ledger:
        message, provider, reason = llm_refine.chat_with_tools(MESSAGES, [], timeout=60)
    assert (message["content"], provider, reason) == ("answer", PROVIDER, "")
    assert sleeps == [3.0]
    assert len(script.calls) == 2
    # 两次尝试都记账：重试照样占本轮调用预算。
    assert [r.status for r in ledger.records] == ["failed", "success"]


def test_chat_with_tools_gives_up_after_one_retry_and_explains(monkeypatch, sleeps):
    script = _Script(_http_error(429, {"Retry-After": "3"}))
    _install(monkeypatch, script)
    message, _provider, reason = llm_refine.chat_with_tools(MESSAGES, [], timeout=60)
    assert message is None
    assert sleeps == [3.0]
    assert len(script.calls) == 2
    assert reason == "LLM 调用 HTTP 429（限流：服务端要求 3 秒后再试）"
    assert llm_refine.stable_llm_fallback_reason(reason) == "provider_rate_limited"


def test_long_cooldown_moves_to_next_provider_without_sleeping(monkeypatch, sleeps):
    def urlopen(request, timeout=0.0, **_kwargs):
        if "example.invalid" in request.full_url:
            raise _http_error(429, {"Retry-After": "4939"})
        return Response(_body("from second"))

    _install(monkeypatch, urlopen, providers=(PROVIDER, SECOND))
    message, provider, reason = llm_refine.chat_with_tools(MESSAGES, [], timeout=60)
    assert (message["content"], provider, reason) == ("from second", SECOND, "")
    assert sleeps == []


def test_other_http_errors_are_still_not_retried(monkeypatch, sleeps):
    script = _Script(_http_error(503, {"Retry-After": "1"}), _body())
    _install(monkeypatch, script)
    message, _provider, reason = llm_refine.chat_with_tools(MESSAGES, [], timeout=60)
    assert message is None and reason == "LLM 调用 HTTP 503"
    assert sleeps == [] and len(script.calls) == 1


def test_full_budget_skips_the_wait(monkeypatch, sleeps):
    script = _Script(_http_error(429, {"Retry-After": "1"}), _body())
    _install(monkeypatch, script)
    with llm_refine.call_ledger_scope(max_calls=1):
        message, _provider, reason = llm_refine.chat_with_tools(MESSAGES, [], timeout=60)
    assert message is None
    assert sleeps == [] and len(script.calls) == 1
    assert reason.startswith("LLM 调用 HTTP 429")


def test_streaming_chat_retries_before_any_delta(monkeypatch, sleeps):
    script = _Script(_http_error(429, {"Retry-After": "2"}), _sse("answer"))
    _install(monkeypatch, script)
    deltas: list[str] = []
    message, provider, reason = llm_refine.chat_with_tools(
        MESSAGES, [], timeout=60, on_content_delta=deltas.append,
    )
    assert (message["content"], provider, reason) == ("answer", PROVIDER, "")
    assert "".join(deltas) == "answer"
    assert sleeps == [2.0]


def test_complete_waits_once_then_succeeds(monkeypatch, sleeps):
    script = _Script(_http_error(429, {"retry-after-ms": "1500"}), _body("done"))
    _install(monkeypatch, script)
    content, provider, reason = llm_refine.complete(MESSAGES, timeout=60)
    assert (content, provider, reason) == ("done", PROVIDER, "")
    assert sleeps == [1.5]


def test_synthesize_messages_waits_once_then_succeeds(monkeypatch, sleeps):
    script = _Script(_http_error(429, {"Retry-After": "2"}), _body("synth"))
    _install(monkeypatch, script)
    result, reason = llm_refine.synthesize_messages(MESSAGES, timeout=60)
    assert reason == "" and result is not None and result.answer == "synth"
    assert sleeps == [2.0]


def test_synthesize_messages_reason_carries_cooldown(monkeypatch, sleeps):
    script = _Script(_http_error(429, {"Retry-After": "4939"}))
    _install(monkeypatch, script)
    result, reason = llm_refine.synthesize_messages(MESSAGES, timeout=60)
    assert result is None
    assert reason == "LLM 合成 HTTP 429（限流：服务端要求 4939 秒后再试），已降级为模板"
    assert sleeps == []


def test_synthesize_stream_waits_once_then_streams(monkeypatch, sleeps):
    script = _Script(_http_error(429, {"Retry-After": "2"}), _sse("answer"))
    _install(monkeypatch, script)
    out: list[str] = []
    result, reason = llm_refine.synthesize_messages_stream(MESSAGES, on_delta=out.append, timeout=60)
    assert reason == "" and result is not None and result.answer == "answer"
    assert "".join(out) == "answer"
    assert sleeps == [2.0]


# ---------------------------------------------------------------- 护栏单元


def test_retry_helper_never_replays_once_output_was_emitted(sleeps):
    calls: list[int] = []

    def call():
        calls.append(1)
        raise _http_error(429, {"Retry-After": "1"})

    with pytest.raises(urllib.error.HTTPError):
        llm_refine._with_rate_limit_retry(
            call, deadline=llm_refine.Deadline.from_timeout(60), retry_allowed=lambda: False,
        )
    assert calls == [1] and sleeps == []


def test_retry_helper_stops_when_cancelled_during_wait(monkeypatch):
    monkeypatch.setattr(llm_refine, "_sleep_for_rate_limit", lambda *_a, **_k: False)
    calls: list[int] = []

    def call():
        calls.append(1)
        raise _http_error(429, {"Retry-After": "1"})

    with pytest.raises(urllib.error.HTTPError):
        llm_refine._with_rate_limit_retry(call, deadline=llm_refine.Deadline.from_timeout(60))
    assert calls == [1]


def test_sleep_returns_false_immediately_when_cancelled(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(llm_refine.time, "sleep", slept.append)
    assert llm_refine._sleep_for_rate_limit(10, is_cancelled=lambda: True) is False
    assert slept == []


def test_rate_limit_is_not_a_transient_marker():
    assert not any("429" in marker for marker in agent_runtime.TRANSIENT_MODEL_ERROR_MARKERS)

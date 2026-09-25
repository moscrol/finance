from __future__ import annotations

import json
from unittest import mock

import pytest

from intelligence.services import llm_refine


def sse(*events: object) -> bytes:
    lines = [f"data: {json.dumps(event, ensure_ascii=False)}\n" for event in events]
    lines.append("data: [DONE]\n")
    return "".join(lines).encode("utf-8")


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._lines = body.splitlines(keepends=True)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def __iter__(self):
        return iter(self._lines)


PROVIDER = llm_refine.LLMProvider(
    name="zhipu",
    api_key="test-key",
    base_url="https://example.invalid/v4",
    model="glm-5.2",
)


def content_event(piece: str) -> dict:
    return {"choices": [{"delta": {"content": piece}}]}


def call_stream(body: bytes, **kwargs):
    deltas: list[str] = []
    with (
        mock.patch.object(llm_refine, "_reserve_llm_call"),
        mock.patch.object(llm_refine, "_record_llm_call"),
        mock.patch(
            "urllib.request.urlopen", return_value=_FakeResponse(body)
        ),
    ):
        message = llm_refine._post_chat_message_stream(
            PROVIDER,
            [{"role": "user", "content": "明天你怎么看"}],
            timeout=30.0,
            temperature=0.0,
            tools=[{"type": "function", "function": {"name": "market_data"}}],
            tool_choice="auto",
            disable_thinking=True,
            on_content_delta=deltas.append,
            **kwargs,
        )
    return message, deltas


def test_content_reaches_the_callback_piece_by_piece() -> None:
    message, deltas = call_stream(
        sse(
            content_event('{"status":"completed","draft":"第一'),
            content_event("段。第二段。"),
            content_event('","gaps":[],"bindings":[]}'),
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            {"usage": {"prompt_tokens": 100, "completion_tokens": 42}},
        )
    )

    assert deltas == [
        '{"status":"completed","draft":"第一',
        "段。第二段。",
        '","gaps":[],"bindings":[]}',
    ]
    # 返回的 message 与非流式同形，agent loop 无感。
    assert json.loads(message["content"])["draft"] == "第一段。第二段。"
    assert message["_usage"] == {"prompt_tokens": 100, "completion_tokens": 42}
    assert message["_finish_reason"] == "stop"
    assert message["_streamed_chars"] == sum(len(d) for d in deltas)


def test_tool_call_fragments_reassemble_into_the_non_streaming_shape() -> None:
    """分片重组错一个字节，工具就静默不执行——这里逐片喂最碎的形状。"""

    message, deltas = call_stream(
        sse(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_a",
                                    "type": "function",
                                    "function": {"name": "market_data", "arguments": ""},
                                },
                                {
                                    "index": 1,
                                    "id": "call_b",
                                    "type": "function",
                                    "function": {"name": "mainline_context", "arguments": ""},
                                },
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '{"que'}}]}}
                ]
            },
            {
                "choices": [
                    {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'ry":"snapshot"}'}}]}}
                ]
            },
            {
                "choices": [
                    {"delta": {"tool_calls": [{"index": 1, "function": {"arguments": "{}"}}]}}
                ]
            },
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
        )
    )

    assert deltas == []
    assert message["content"] == ""
    assert message["tool_calls"] == [
        {
            "id": "call_a",
            "type": "function",
            "function": {"name": "market_data", "arguments": '{"query":"snapshot"}'},
        },
        {
            "id": "call_b",
            "type": "function",
            "function": {"name": "mainline_context", "arguments": "{}"},
        },
    ]
    # arguments 必须能解析——拼错一个字节这里就炸。
    assert json.loads(message["tool_calls"][0]["function"]["arguments"]) == {
        "query": "snapshot"
    }


def test_repeated_name_fragment_is_not_concatenated() -> None:
    """有的网关每片都重发 name。拼接会得到 market_datamarket_data。"""

    message, _ = call_stream(
        sse(
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_a",
                                    "function": {"name": "market_data", "arguments": "{"},
                                }
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "function": {"name": "market_data", "arguments": "}"}}
                            ]
                        }
                    }
                ]
            },
        )
    )

    assert message["tool_calls"][0]["function"]["name"] == "market_data"
    assert message["tool_calls"][0]["function"]["arguments"] == "{}"


def test_provider_that_never_streams_raises_before_any_delta() -> None:
    """没吐过字才可以换 provider —— 这条是回退闸的准入条件。"""

    with pytest.raises(llm_refine.LLMStreamingUnsupported):
        call_stream(b"")


def test_failure_after_first_delta_is_a_different_exception() -> None:
    deltas: list[str] = []

    class _ExplodingResponse(_FakeResponse):
        def __iter__(self):
            yield f"data: {json.dumps(content_event('已经吐出去的正文'))}\n".encode()
            raise OSError("connection reset mid-stream")

    with (
        mock.patch.object(llm_refine, "_reserve_llm_call"),
        mock.patch.object(llm_refine, "_record_llm_call"),
        mock.patch("urllib.request.urlopen", return_value=_ExplodingResponse(b"")),
        pytest.raises(llm_refine.LLMStreamAlreadyEmitted),
    ):
        llm_refine._post_chat_message_stream(
            PROVIDER,
            [{"role": "user", "content": "q"}],
            timeout=30.0,
            temperature=0.0,
            tools=None,
            tool_choice=None,
            disable_thinking=True,
            on_content_delta=deltas.append,
        )

    assert deltas == ["已经吐出去的正文"]


def test_chat_with_tools_refuses_to_retry_after_text_reached_the_user() -> None:
    """已吐字后失败：不换 provider、不回退非流式，直接降级。"""

    providers = (PROVIDER, llm_refine.LLMProvider("openai", "k2", "https://x.invalid", "m"))
    attempts: list[str] = []

    def explode(provider, *args, **kwargs):
        attempts.append(provider.name)
        raise llm_refine.LLMStreamAlreadyEmitted("boom")

    with (
        mock.patch.object(llm_refine, "detect_providers", return_value=providers),
        mock.patch.object(llm_refine, "_budget_rejection", return_value=None),
        mock.patch.object(llm_refine, "_insufficient_budget_reason", return_value=None),
        mock.patch.object(llm_refine, "_post_chat_message_stream", side_effect=explode),
        mock.patch.object(
            llm_refine,
            "_post_chat_message",
            side_effect=AssertionError("非流式回退必须被禁掉"),
        ),
    ):
        message, provider, reason = llm_refine.chat_with_tools(
            [{"role": "user", "content": "q"}],
            [],
            on_content_delta=lambda _: None,
        )

    assert message is None
    assert provider is PROVIDER
    assert reason == llm_refine._STREAM_FALLBACK_BLOCKED
    assert attempts == ["zhipu"], "第二个 provider 一次都不该被试"


def test_chat_with_tools_may_still_try_the_next_provider_before_any_delta() -> None:
    providers = (PROVIDER, llm_refine.LLMProvider("openai", "k2", "https://x.invalid", "m"))
    attempts: list[str] = []

    def maybe(provider, *args, **kwargs):
        attempts.append(provider.name)
        if provider.name == "zhipu":
            raise llm_refine.LLMStreamingUnsupported()
        return {"role": "assistant", "content": "ok", "_streamed_chars": 2}

    with (
        mock.patch.object(llm_refine, "detect_providers", return_value=providers),
        mock.patch.object(llm_refine, "_budget_rejection", return_value=None),
        mock.patch.object(llm_refine, "_insufficient_budget_reason", return_value=None),
        mock.patch.object(llm_refine, "_post_chat_message_stream", side_effect=maybe),
    ):
        message, provider, reason = llm_refine.chat_with_tools(
            [{"role": "user", "content": "q"}],
            [],
            on_content_delta=lambda _: None,
        )

    assert reason == ""
    assert message is not None and message["content"] == "ok"
    assert attempts == ["zhipu", "openai"]


def test_without_the_callback_the_call_stays_non_streaming() -> None:
    """默认路径逐字节不变：没传回调就一行流式代码都不走。"""

    with (
        mock.patch.object(llm_refine, "detect_providers", return_value=(PROVIDER,)),
        mock.patch.object(llm_refine, "_budget_rejection", return_value=None),
        mock.patch.object(llm_refine, "_insufficient_budget_reason", return_value=None),
        mock.patch.object(
            llm_refine,
            "_post_chat_message_stream",
            side_effect=AssertionError("不该走流式"),
        ),
        mock.patch.object(
            llm_refine, "_post_chat_message", return_value={"content": "plain"}
        ) as plain,
    ):
        message, _, reason = llm_refine.chat_with_tools(
            [{"role": "user", "content": "q"}], []
        )

    assert reason == ""
    assert message == {"content": "plain"}
    assert plain.call_count == 1

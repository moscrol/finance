"""K3 rejects temperature; exercise every actual HTTP builder, with other-model controls."""
from __future__ import annotations

import json

import pytest

from intelligence.services import llm_refine
from intelligence.tests.test_llm_call_provenance import Response, body, sse


@pytest.mark.parametrize("kind", ["chat", "synthesis", "tools", "tools_stream", "synthesis_stream"])
@pytest.mark.parametrize("model", ["kimi-k3", "glm-5.3-flash", "kimi-k2.5", "kimi-k3-other"])
def test_all_transports_apply_model_sampling_policy(monkeypatch, kind, model):
    provider = llm_refine.LLMProvider("zhipu", "fixture", "https://example.invalid/v1", model)
    messages = [{"role": "user", "content": "test"}]
    tools = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]
    requests = []

    def urlopen(request, timeout=0.0, **_kwargs):
        payload = json.loads(request.data)
        requests.append(payload)
        if payload.get("stream"):
            return Response(sse({"model": model, "choices": [{"delta": {"content": "answer"}, "finish_reason": "stop"}]}))
        return Response(body(model=model))

    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", urlopen)
    monkeypatch.delenv("LLM_THINKING", raising=False)
    if kind == "chat":
        llm_refine._post_chat(provider, messages, 5, 0.25, max_tokens=123)
    elif kind == "synthesis":
        llm_refine._post_chat_synthesis(provider, messages, 5, 0.25, 123, 100)
    elif kind == "tools":
        llm_refine._post_chat_message(provider, messages, 5, 0.25, tools, "auto", False)
    elif kind == "tools_stream":
        llm_refine._post_chat_message_stream(provider, messages, 5, 0.25, tools, "auto", False, lambda _: None)
    else:
        llm_refine._post_chat_stream(provider, messages, 5, 0.25, lambda _: None, None, None, llm_refine.Deadline.from_timeout(5), 123, 100)
    assert len(requests) == 1
    request = requests[0]
    assert ("temperature" in request) is (model != "kimi-k3")
    if model != "kimi-k3":
        assert request["temperature"] == 0.25
    assert request["model"] == model
    assert request["messages"] == messages
    if "tools" in kind:
        assert request["tools"] == tools and request["tool_choice"] == "auto"
    else:
        assert request["max_tokens"] == 123
    if "stream" in kind:
        assert request["stream"] is True
    if kind == "tools_stream":
        assert request["stream_options"] == {"include_usage": True}

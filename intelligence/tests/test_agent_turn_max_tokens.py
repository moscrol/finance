"""Episode 工具轮的输出上限：只给点名的模型加，其他 provider 的请求体逐字节不变。

终局 draft 篇幅从 1000 字放到 4000 字（``EPISODE_DRAFT_MAX_CHARS``）之后，FINAL_JSON
连同 GLM 强制思考的 token 可能越过端点默认上限；工具轮一旦 ``finish_reason=length``，
整轮被 ``ModelTurn`` 判成 ``incomplete_model_response`` 丢掉。
"""

from __future__ import annotations

import json

import pytest

from intelligence.services import llm_refine
from intelligence.services.episode_protocol import EPISODE_DRAFT_MAX_CHARS
from intelligence.tests.test_llm_call_provenance import Response, body, sse

TOOLS = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]
MESSAGES = [{"role": "user", "content": "test"}]


def _capture(monkeypatch, model: str, kind: str) -> dict:
    provider = llm_refine.LLMProvider("zhipu", "fixture", "https://example.invalid/v1", model)
    requests: list[dict] = []

    def urlopen(request, timeout=0.0, **_kwargs):
        payload = json.loads(request.data)
        requests.append(payload)
        if payload.get("stream"):
            return Response(
                sse({"model": model, "choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]})
            )
        return Response(body(model=model))

    monkeypatch.setattr(llm_refine.llm_http_transport, "urlopen", urlopen)
    monkeypatch.delenv("LLM_THINKING", raising=False)
    if kind == "tools":
        llm_refine._post_chat_message(provider, MESSAGES, 5, 0.2, TOOLS, "auto", False)
    else:
        llm_refine._post_chat_message_stream(
            provider, MESSAGES, 5, 0.2, TOOLS, "auto", False, lambda _: None
        )
    assert len(requests) == 1
    return requests[0]


@pytest.mark.parametrize("kind", ["tools", "tools_stream"])
def test_glm5_tool_turns_carry_an_explicit_output_cap(monkeypatch, kind: str) -> None:
    monkeypatch.delenv(llm_refine.AGENT_TURN_MAX_TOKENS_ENV, raising=False)

    request = _capture(monkeypatch, "glm-5.3-flash", kind)

    assert request["max_tokens"] == 32768


@pytest.mark.parametrize("kind", ["tools", "tools_stream"])
@pytest.mark.parametrize("model", ["kimi-k3", "gpt-5.6-sol", "deepseek-chat"])
def test_other_models_keep_their_request_body(monkeypatch, kind: str, model: str) -> None:
    monkeypatch.delenv(llm_refine.AGENT_TURN_MAX_TOKENS_ENV, raising=False)

    assert "max_tokens" not in _capture(monkeypatch, model, kind)


def test_env_table_overrides_and_empty_string_disables(monkeypatch) -> None:
    monkeypatch.setenv(llm_refine.AGENT_TURN_MAX_TOKENS_ENV, "glm-5.3:8000,kimi:2000")
    assert llm_refine.agent_turn_max_tokens("glm-5.3-flash") == 8000
    assert llm_refine.agent_turn_max_tokens("kimi-k3") == 2000
    assert llm_refine.agent_turn_max_tokens("gpt-5.6-sol") is None

    monkeypatch.setenv(llm_refine.AGENT_TURN_MAX_TOKENS_ENV, "")
    assert llm_refine.agent_turn_max_tokens("glm-5.3-flash") is None

    monkeypatch.setenv(llm_refine.AGENT_TURN_MAX_TOKENS_ENV, "glm-5:not-a-number")
    assert llm_refine.agent_turn_max_tokens("glm-5.3-flash") is None


def test_default_cap_leaves_room_for_the_relaxed_draft() -> None:
    """4000 汉字的 draft 加 JSON 外壳与绑定，远低于 32768，给强制思考留足余量。"""

    assert EPISODE_DRAFT_MAX_CHARS >= 3000
    assert llm_refine.agent_turn_max_tokens("glm-5.3-flash") >= 4 * EPISODE_DRAFT_MAX_CHARS

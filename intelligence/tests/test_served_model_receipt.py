"""生效模型进产物（spec §3.5.4 硬门 3 / §4 第二个诊断缺口）。

2026-08-08 生产出口切中转后 health 报 ``glm-5.2``、实际跑 ``gpt-5.6-sol``——全仓当时只记
配置值（``providers[0].model``），响应体的 ``model`` 字段无人落盘。P4 A/B 若取配置值，
会把「模型没真的切过去」读成「SDK 底座没差别」。

三态约定（``ModelTurn.served_model``）：``None`` = 回合没到 provider；``""`` = provider
回了响应但没带 model（记「未回」）；非空 = 对端实际服务的模型。**永不**回填配置值。
"""

from __future__ import annotations

import asyncio
import json
from unittest import mock

import pytest

from intelligence.runtime import glm_agent_runtime
from intelligence.runtime.openai_agents_runtime import (
    AgentsSdkRequest,
    AgentsSdkResult,
    OpenAIAgentsRuntime,
    ServedModelLog,
    _served_models_of,
)
from intelligence.services import llm_refine
from intelligence.services.agent_runtime import ModelTurn
from intelligence.tests.test_llm_refine_tool_stream import (
    PROVIDER,
    call_stream,
    content_event,
    sse,
)
from intelligence.tests.test_openai_agents_runtime import _context, _frame, _registry


class _JsonResponse:
    def __init__(self, body: dict) -> None:
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self) -> "_JsonResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _post(body: dict) -> dict:
    with (
        mock.patch.object(llm_refine, "_reserve_llm_call"),
        mock.patch.object(llm_refine, "_record_llm_call"),
        mock.patch("urllib.request.urlopen", return_value=_JsonResponse(body)),
    ):
        return llm_refine._post_chat_message(
            PROVIDER,
            [{"role": "user", "content": "2024年贵州茅台营业总收入"}],
            timeout=30.0,
        )


# ---------------------------------------------------------------------------
# continuous 臂：_post_chat_message / _post_chat_message_stream
# ---------------------------------------------------------------------------


def test_non_streaming_message_carries_the_served_model_not_the_requested_one() -> None:
    message = _post(
        {
            "model": "gpt-5.6-sol",  # 中转实际服务的
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        }
    )
    assert PROVIDER.model == "glm-5.2"  # 我们请求的
    assert message["_served_model"] == "gpt-5.6-sol"
    assert message["_usage"] == {"prompt_tokens": 10, "completion_tokens": 2}


def test_non_streaming_message_records_empty_string_when_gateway_omits_model() -> None:
    message = _post({"choices": [{"message": {"role": "assistant", "content": "ok"}}]})
    assert message["_served_model"] == ""  # 「未回」，不是 glm-5.2


def test_streaming_message_takes_model_from_the_first_chunk_that_has_it() -> None:
    message, _deltas = call_stream(
        sse(
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"model": "glm-5.3", **content_event("第一段")},
            {"model": "glm-5.3", **content_event("第二段")},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        )
    )
    assert message["content"] == "第一段第二段"
    assert message["_served_model"] == "glm-5.3"


def test_streaming_message_without_model_field_records_not_returned() -> None:
    message, _deltas = call_stream(sse(content_event("x")))
    assert message["_served_model"] == ""


# ---------------------------------------------------------------------------
# ModelTurn 三态 + 适配器信封
# ---------------------------------------------------------------------------


def test_model_turn_serialises_served_model_only_when_a_response_existed() -> None:
    absent = ModelTurn("x", (), "zhipu", "", provider_attempts=0).to_dict()
    assert "served_model" not in absent
    not_returned = ModelTurn("x", (), "zhipu", "", served_model="").to_dict()
    assert not_returned["served_model"] == ""
    served = ModelTurn("x", (), "zhipu", "", served_model=" gpt-5.6-sol ").to_dict()
    assert served["served_model"] == "gpt-5.6-sol"
    with pytest.raises(ValueError, match="served_model"):
        ModelTurn("x", (), "zhipu", "", served_model=123)  # type: ignore[arg-type]


def test_turn_from_message_threads_served_model_through_success_and_error_paths() -> None:
    turn, error = glm_agent_runtime._turn_from_message(
        {"content": "ok", "_served_model": "gpt-5.6-sol"}, "zhipu", 1
    )
    assert error == ""
    assert turn.served_model == "gpt-5.6-sol"

    turn, error = glm_agent_runtime._turn_from_message(
        {"content": "", "tool_calls": "not-a-list", "_served_model": ""}, "zhipu", 1
    )
    assert error == "invalid_tool_calls"
    assert turn.served_model == ""

    turn, _error = glm_agent_runtime._turn_from_message({"content": "ok"}, "zhipu", 1)
    assert turn.served_model is None
    assert "served_model" not in turn.to_dict()


# ---------------------------------------------------------------------------
# SDK 臂：httpx 响应钩子 + runtime_result 事件
# ---------------------------------------------------------------------------


class _FakeHttpxResponse:
    def __init__(self, *, content_type: str, body: bytes) -> None:
        self.headers = {"content-type": content_type}
        self._body = body
        self.read_calls = 0

    async def aread(self) -> bytes:
        self.read_calls += 1
        return self._body

    def json(self) -> object:
        return json.loads(self._body.decode("utf-8"))


def test_served_model_log_records_one_entry_per_json_response() -> None:
    log = ServedModelLog()

    async def feed() -> None:
        await log(
            _FakeHttpxResponse(
                content_type="application/json",
                body=json.dumps({"model": "glm-5.3", "choices": []}).encode(),
            )
        )
        await log(
            _FakeHttpxResponse(content_type="application/json", body=b'{"choices": []}')
        )
        # 非 JSON（流式 SSE）跳过，不读 body——读了会吃掉流。
        await log(_FakeHttpxResponse(content_type="text/event-stream", body=b"data: x"))
        await log(_FakeHttpxResponse(content_type="application/json", body=b"not json"))

    asyncio.run(feed())
    assert log.models == ["glm-5.3", "", ""]


def test_served_models_of_reads_the_log_hung_on_the_model_or_its_wrapper() -> None:
    class _Model:
        pass

    bare = _Model()
    assert _served_models_of(bare) == ()
    log = ServedModelLog()
    log.models.extend(["glm-5.3", ""])
    bare.served_model_log = log  # type: ignore[attr-defined]
    assert _served_models_of(bare) == ("glm-5.3", "")


def test_agents_sdk_result_rejects_non_string_served_models() -> None:
    with pytest.raises(ValueError, match="served_models"):
        AgentsSdkResult("x", 1, served_models=("glm-5.3", 7))  # type: ignore[arg-type]


def test_runtime_result_event_writes_served_models_beside_the_requested_model() -> None:
    def runner(request: AgentsSdkRequest) -> AgentsSdkResult:
        observation = request.tools[0].invoke("A股 当前主线")
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心，电力是轮动支线。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": observation["evidence_hashes"],
                    "gap": "",
                }
            ],
        }
        return AgentsSdkResult(
            json.dumps(finish, ensure_ascii=False),
            2,
            served_models=("gpt-5.6-sol", ""),
        )

    outcome = OpenAIAgentsRuntime(
        runner=runner,
        backend="sdk_glm",
        model_name="glm-5.3",
    ).run(task_frame=_frame(), context=_context(_frame()), registry=_registry([]))

    result_event = next(e for e in outcome.events if e.kind == "runtime_result")
    assert result_event.payload["model"] == "glm-5.3"  # 配置值
    # 生效值，逐响应；EpisodeEvent 会把 payload 冻成 tuple。
    assert list(result_event.payload["served_models"]) == ["gpt-5.6-sol", ""]

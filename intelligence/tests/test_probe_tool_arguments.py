"""参数构造探针的**保真度**：回灌给模型的文本必须和生产逐字一致。

这个量具的全部价值建立在一条主张上：``--follow-up`` 喂回去的拒绝消息，就是
生产会喂的那一条。它靠直接 import 生产的构造函数来保证——
``ContinuousAgentEpisode._assistant_message`` 与
``_EpisodeToolAccumulator._append_tool_error``。

**这几个都是私有符号，改名不会有任何编译期报错**，探针会静默退化成「拼了一份
看起来差不多的文本」，而读数照常发绿。TOOLKIT 三条量具陷阱的第一条就是
「量具必须复刻生产」——本模块是那条纪律的可执行版。

同理，``detail`` 非空这条断言不是重复 ``test_agent_episode`` 那边的：那边钉的是
生产**填了** detail，这边钉的是探针**取到了**它。中间那一跳断掉时，两边各自
仍然全绿。
"""
from __future__ import annotations

import json

from scripts.probe_tool_arguments import _feedback_messages
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.task_frame import TaskFrame


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="2026-07-23 哪些板块是双红",
        user_goal="probe",
        question_type="market_overview",
        subject=None,
        subject_kind="market_pattern",
        market_scope="a_share",
        timeframe=None,
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="standard",
        confidence=0.8,
    )


def _turn(call: ModelToolCall) -> ModelTurn:
    return ModelTurn(content="", tool_calls=(call,), provider_name="probe")


class TestFeedbackMatchesProduction:
    def test_parse_failure_carries_the_reason_the_model_can_act_on(self) -> None:
        """解析期失败走 ``_append_tool_error``，detail 必须带具体原因。

        这一路正是 2026-08-12 修的那条：改前 detail 恒为空串，模型收到的只有
        分类码 ``invalid_arguments``，于是同一个 order_by 形状错误在基线里
        一模一样重复了 14 次。
        """
        call = ModelToolCall("c1", "finance_query", {"dataset": "market_daily"})

        messages = _feedback_messages(
            _turn(call),
            {
                "c1": {
                    "valid": False,
                    "stage": "parse",
                    "error_code": "invalid_arguments",
                    "detail": "order_by must be an array",
                    "call_id": "c1",
                }
            },
            task_frame=_frame(),
        )

        tool_message = messages[-1]
        assert tool_message["role"] == "tool"
        assert tool_message["tool_call_id"] == "c1"
        payload = json.loads(tool_message["content"])
        assert payload["ok"] is False
        assert payload["error"] == "invalid_arguments"
        assert payload["detail"] == "order_by must be an array"

    def test_compile_failure_carries_the_retry_hint(self) -> None:
        """编译期失败在生产是一条正常观测，正文带「重试提示」。

        两条路的形状不同，回灌时不能混——喂错形状等于测的不是生产行为。
        """
        call = ModelToolCall("c2", "finance_query", {"dataset": "market_daily"})

        messages = _feedback_messages(
            _turn(call),
            {
                "c2": {
                    "valid": False,
                    "stage": "compile",
                    "detail": "unknown field: amount",
                    "retry_hint": "当前 dataset=market_daily；字段归属：amount→sector_daily.metric",
                    "call_id": "c2",
                }
            },
            task_frame=_frame(),
        )

        payload = json.loads(messages[-1]["content"])
        assert payload["ok"] is True
        assert "结构化查询参数无效" in payload["observation"]
        assert "重试提示" in payload["observation"]
        assert "amount→sector_daily.metric" in payload["observation"]

    def test_every_tool_call_gets_a_paired_tool_message(self) -> None:
        """OpenAI 风格接口要求 assistant 的每个 tool_call 都有配对的 tool 消息。

        少一条整轮请求会被拒，而那会表现为「provider 报错」——被误读成模型问题。
        """
        calls = (
            ModelToolCall("ok-1", "finance_query", {"dataset": "market_daily"}),
            ModelToolCall("bad-1", "finance_query", {"dataset": "market_daily"}),
        )
        turn = ModelTurn(content="", tool_calls=calls, provider_name="probe")

        messages = _feedback_messages(
            turn,
            {
                "ok-1": {"valid": True, "call_id": "ok-1"},
                "bad-1": {
                    "valid": False,
                    "stage": "parse",
                    "error_code": "invalid_arguments",
                    "detail": "filters must be an array",
                    "call_id": "bad-1",
                },
            },
            task_frame=_frame(),
        )

        assert messages[0]["role"] == "assistant"
        tool_ids = [m["tool_call_id"] for m in messages if m["role"] == "tool"]
        assert tool_ids == ["ok-1", "bad-1"]

    def test_assistant_turn_replays_the_original_tool_calls(self) -> None:
        """回灌历史里必须带上模型原本写了什么，否则它不知道在修哪一次调用。"""
        call = ModelToolCall(
            "c3", "finance_query", {"dataset": "market_daily", "limit": 5}
        )

        messages = _feedback_messages(
            _turn(call),
            {"c3": {"valid": False, "stage": "parse", "detail": "x", "call_id": "c3"}},
            task_frame=_frame(),
        )

        assistant = messages[0]
        assert assistant["role"] == "assistant"
        emitted = assistant["tool_calls"][0]
        assert emitted["id"] == "c3"
        assert emitted["function"]["name"] == "finance_query"
        assert "market_daily" in emitted["function"]["arguments"]

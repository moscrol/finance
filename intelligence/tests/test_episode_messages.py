"""INV-R1「模型可见即已落账」：派生规则、对账与投影剔正文。

终态稿 ``2026-09-07-runtime-base-endstate-design.md`` §6.1 P0 验收。两条 loop 的端到端
对账不在这里另写：``conftest`` 已强制 ``FORESIGHT_STRICT_DERIVATION=1``，全量套件里每次
脚本化模型请求前都在验；本文件只钉派生器自己的性质。
"""

from __future__ import annotations

import json

import pytest

from intelligence.services.agent_runtime import EpisodeEvent, ModelToolCall, ModelTurn
from intelligence.services.episode_messages import (
    MODEL_INPUT_SOURCES,
    MODEL_VISIBLE_TEXT_FIELDS,
    STRICT_DERIVATION_ENV,
    DerivationMismatch,
    DerivationUnavailable,
    EpisodeMessage,
    append_model_input,
    assistant_message,
    assistant_message_from_payload,
    check_derivation,
    derive_messages,
    describe_mismatch,
    record_prompt_assembled,
    record_tool_budget_state,
    rewrite_last_tool_content,
    sha256_text,
    system_message,
    to_provider,
    tool_message,
    user_message,
)
from intelligence.services.episode_event_lanes import DURABLE_EVENT_KINDS, lane_for
from intelligence.services.episode_projection import project_durable_events


class _Ledger:
    def __init__(self) -> None:
        self.events: list[EpisodeEvent] = []

    def add(self, kind: str, payload: dict[str, object]) -> EpisodeEvent:
        event = EpisodeEvent(len(self.events) + 1, kind, payload)
        self.events.append(event)
        return event


def _tool_turn() -> ModelTurn:
    return ModelTurn(
        "",
        (ModelToolCall("call-1", "market_data", {"query": "当前市场结构", "n": 3}),),
        "scripted",
        "",
    )


# ── fold 规则 ─────────────────────────────────────────────────────────────


def test_prompt_and_inputs_fold_into_system_then_user_messages() -> None:
    ledger = _Ledger()
    messages: list[EpisodeMessage] = []
    record_prompt_assembled(ledger, system="宪法", user='{"question": "今天怎么看"}')
    messages.extend([system_message("宪法"), user_message('{"question": "今天怎么看"}')])
    append_model_input(messages, ledger, content="先给 PLAN", source="steering_invalid_plan")

    assert to_provider(derive_messages(ledger.events)) == to_provider(messages)
    assert to_provider(messages) == [
        {"role": "system", "content": "宪法"},
        {"role": "user", "content": '{"question": "今天怎么看"}'},
        {"role": "user", "content": "先给 PLAN"},
    ]
    assert messages[-1].source == "steering_invalid_plan"
    assert [event.kind for event in ledger.events] == ["prompt_assembled", "model_input"]
    assert ledger.events[0].payload["system_sha256"] == sha256_text("宪法")
    assert ledger.events[1].payload["source"] == "steering_invalid_plan"


def test_assistant_message_shape_is_identical_from_turn_and_from_payload() -> None:
    """loop 侧从 ModelTurn 拼、派生侧从事件 payload 拼，必须逐字节同形——INV-R1 的前提。"""

    turn = _tool_turn()
    ledger = _Ledger()
    event = ledger.add("model_turn", turn.to_dict())

    from_turn = assistant_message(turn)
    from_payload = assistant_message_from_payload(event.to_dict()["payload"])

    assert to_provider([from_turn]) == to_provider([from_payload])
    wire = to_provider([from_turn])[0]
    assert wire["tool_calls"][0]["function"]["arguments"] == json.dumps(
        {"query": "当前市场结构", "n": 3}, ensure_ascii=False
    )
    assert wire["tool_calls"][0]["id"] == "call-1" and wire["tool_calls"][0]["type"] == "function"
    assert to_provider(derive_messages(ledger.events)) == [wire]


def test_errored_model_turn_produces_no_assistant_message() -> None:
    """失败 turn 不进消息历史：两条 loop 都这样，派生器必须同口径。"""

    ledger = _Ledger()
    ledger.add("model_turn", ModelTurn("", (), "scripted", "TimeoutError").to_dict())
    ledger.add("model_error", {"reason": "TimeoutError"})
    ledger.add("repair_model_retry", {"attempt": 1})

    assert derive_messages(ledger.events) == []


def test_tool_events_fold_to_tool_messages_and_budget_state_overwrites_the_last() -> None:
    ledger = _Ledger()
    ledger.add(
        "tool_result",
        {"tool": "market_data", "call_id": "call-1", "model_content": '{"ok": true, "n": 1}'},
    )
    ledger.add(
        "tool_error",
        {"ok": False, "error": "tool_timeout", "call_id": "call-2", "model_content": '{"ok": false}'},
    )
    rewritten = json.dumps({"ok": False, "runtime_budget": {"remaining_tool_calls": 2}})
    record_tool_budget_state(
        ledger, runtime_budget={"remaining_tool_calls": 2}, model_content=rewritten
    )

    derived = derive_messages(ledger.events)
    assert to_provider(derived) == [
        {"role": "tool", "tool_call_id": "call-1", "content": '{"ok": true, "n": 1}'},
        {"role": "tool", "tool_call_id": "call-2", "content": rewritten},
    ]
    assert [message.source for message in derived] == ["tool_result", "tool_error"]


def test_history_compacted_overwrites_the_folded_tool_messages_by_call_id() -> None:
    """历史折叠（spec 2026-09-07 §3.2）改的是更早批次 tool 消息的正文：事件按 call_id 带
    替换后的 model_content，派生按 call_id 覆写，不动其余消息、不动配对。"""

    ledger = _Ledger()
    ledger.add("tool_result", {"call_id": "call-1", "model_content": '{"ok": true, "big": 1}'})
    ledger.add("tool_result", {"call_id": "call-2", "model_content": '{"ok": true, "big": 2}'})
    ledger.add("tool_result", {"call_id": "call-3", "model_content": '{"ok": true, "big": 3}'})
    folded = '{"ok": true, "compacted": true, "evidence_index": []}'
    ledger.add(
        "history_compacted",
        {
            "folded": [
                {"call_id": "call-1", "tool": "market_data", "model_content": folded},
                {"call_id": "call-2", "tool": "market_data", "model_content": folded},
            ],
            "folded_messages": 2,
        },
    )

    derived = derive_messages(ledger.events)
    assert to_provider(derived) == [
        {"role": "tool", "tool_call_id": "call-1", "content": folded},
        {"role": "tool", "tool_call_id": "call-2", "content": folded},
        {"role": "tool", "tool_call_id": "call-3", "content": '{"ok": true, "big": 3}'},
    ]
    # 折叠只换正文：来源审计字段仍是 tool_result（不是第二种消息）。
    assert [message.source for message in derived] == ["tool_result"] * 3


def test_history_compacted_without_model_content_or_target_is_refused() -> None:
    ledger = _Ledger()
    ledger.add("tool_result", {"call_id": "call-1", "model_content": "{}"})
    ledger.add("history_compacted", {"folded": [{"call_id": "call-1", "tool": "x"}]})
    with pytest.raises(DerivationUnavailable, match="model_content"):
        derive_messages(ledger.events)

    ledger = _Ledger()
    ledger.add("history_compacted", {"folded": [{"call_id": "ghost", "model_content": "{}"}]})
    with pytest.raises(DerivationUnavailable, match="找不到"):
        derive_messages(ledger.events)


def test_unrelated_kinds_produce_no_messages() -> None:
    ledger = _Ledger()
    for kind in ("task", "plan", "tool_request", "tool_menu", "finalization", "finish"):
        ledger.add(kind, {"x": 1})

    assert derive_messages(ledger.events) == []


# ── P1：消息类型与线格式边界 ─────────────────────────────────────────────────


def test_episode_message_validates_role_specific_fields() -> None:
    with pytest.raises(ValueError, match="角色"):
        EpisodeMessage(role="narrator", content="x")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="tool_call_id"):
        EpisodeMessage(role="tool", content="x")
    with pytest.raises(ValueError, match="tool_calls"):
        EpisodeMessage(role="user", content="x", tool_calls=_tool_turn().tool_calls)
    with pytest.raises(ValueError, match="tool_call_id"):
        EpisodeMessage(role="user", content="x", tool_call_id="c1")


def test_to_provider_openai_shape_is_byte_stable_and_drops_audit_fields() -> None:
    """线格式只含 provider 认识的键：source 是审计字段，不出边界。"""

    messages = [
        system_message("s", source="prompt"),
        user_message("u", source="steering_invalid_plan"),
        assistant_message(_tool_turn()),
        tool_message("call-1", '{"ok": true}', source="tool_result"),
        assistant_message(ModelTurn("最终答案", (), "scripted", "")),
    ]

    wire = to_provider(messages)

    assert wire == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "market_data",
                        "arguments": json.dumps(
                            {"query": "当前市场结构", "n": 3}, ensure_ascii=False
                        ),
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": '{"ok": true}'},
        {"role": "assistant", "content": "最终答案"},
    ]
    assert not any("source" in row for row in wire)
    with pytest.raises(ValueError, match="方言"):
        to_provider(messages, dialect="anthropic")  # type: ignore[arg-type]


def test_rewrite_last_tool_content_replaces_immutably() -> None:
    messages = [tool_message("c1", '{"ok": true}')]
    before = messages[0]

    rewritten = rewrite_last_tool_content(messages, '{"ok": true, "runtime_budget": {}}')

    assert messages[0] is rewritten and messages[0] is not before
    assert before.content == '{"ok": true}'
    assert rewritten.tool_call_id == "c1" and rewritten.source == before.source
    with pytest.raises(ValueError, match="tool"):
        rewrite_last_tool_content([user_message("u")], "x")


# ── 不能派生就不猜 ─────────────────────────────────────────────────────────


def test_legacy_tool_result_without_model_content_is_refused_not_guessed() -> None:
    ledger = _Ledger()
    ledger.add("tool_result", {"tool": "market_data", "call_id": "call-1"})

    with pytest.raises(DerivationUnavailable, match="model_content"):
        derive_messages(ledger.events)


def test_budget_state_without_a_preceding_tool_message_is_refused() -> None:
    ledger = _Ledger()
    record_tool_budget_state(ledger, runtime_budget={}, model_content="{}")

    with pytest.raises(DerivationUnavailable, match="tool_budget_state"):
        derive_messages(ledger.events)


def test_unregistered_model_input_source_is_rejected_at_the_emitter() -> None:
    ledger = _Ledger()
    with pytest.raises(ValueError, match="model_input"):
        append_model_input([], ledger, content="x", source="made_up")  # type: ignore[arg-type]
    assert ledger.events == []


# ── 对账：严格炸、宽松记账 ─────────────────────────────────────────────────


def test_check_derivation_raises_in_strict_mode_and_records_otherwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = _Ledger()
    record_prompt_assembled(ledger, system="s", user="u")
    actual = [
        system_message("s"),
        user_message("u"),
        user_message("偷偷 append 的、没有事件的一条"),
    ]

    monkeypatch.setenv(STRICT_DERIVATION_ENV, "1")
    with pytest.raises(DerivationMismatch, match="长度 2 \\(derived\\) vs 3 \\(actual\\)"):
        check_derivation(ledger.events, actual)

    monkeypatch.setenv(STRICT_DERIVATION_ENV, "0")
    recorded: list[str] = []
    assert check_derivation(ledger.events, actual, on_mismatch=recorded.append) is False
    assert len(recorded) == 1 and "@2" in recorded[0]
    # 一致时两种模式都安静。
    assert check_derivation(ledger.events, actual[:2], on_mismatch=recorded.append) is True
    assert len(recorded) == 1


def test_mismatch_description_never_echoes_prompt_text() -> None:
    secret = "这一段不能进收据"
    derived = [{"role": "user", "content": "a"}]
    actual = [{"role": "user", "content": secret}]

    detail = describe_mismatch(derived, actual)

    assert secret not in detail
    assert "@0" in detail and "role=user" in detail


def test_unavailable_derivation_counts_as_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(STRICT_DERIVATION_ENV, "0")
    ledger = _Ledger()
    ledger.add("tool_result", {"tool": "market_data", "call_id": "call-1"})
    recorded: list[str] = []

    assert check_derivation(ledger.events, [], on_mismatch=recorded.append) is False
    assert recorded and recorded[0].startswith("unavailable:")


# ── 与车道表 / 投影的契约 ─────────────────────────────────────────────────


def test_model_visible_carriers_are_durable_kinds() -> None:
    for kind in ("prompt_assembled", "model_input", "tool_budget_state"):
        assert kind in DURABLE_EVENT_KINDS
        assert lane_for(kind) == "durable"
    assert {kind for kind, _ in MODEL_VISIBLE_TEXT_FIELDS} <= DURABLE_EVENT_KINDS
    assert MODEL_INPUT_SOURCES  # 表非空且被发射点引用（见 emitter 扫描测试）


def test_projection_redacts_model_visible_text_by_default_but_keeps_hashes() -> None:
    ledger = _Ledger()
    ledger.add("task", {"question": "今天怎么看", "task_frame_hash": "h"})
    record_prompt_assembled(ledger, system="宪法正文", user="首轮 user 正文")
    append_model_input([], ledger, content="注入正文", source="begin_finalization")
    ledger.add(
        "tool_result",
        {"tool": "market_data", "call_id": "c1", "model_content": "工具正文", "hash": "abc"},
    )

    projection = project_durable_events(ledger.events)
    dumped = json.dumps(list(projection.events), ensure_ascii=False)

    for text in ("宪法正文", "首轮 user 正文", "注入正文", "工具正文"):
        assert text not in dumped
    prompt = projection.events[1]["payload"]
    assert prompt["system_sha256"] == sha256_text("宪法正文")
    assert prompt["system_chars"] == len("宪法正文")
    assert "system" not in prompt and "user" not in prompt
    model_input = projection.events[2]["payload"]
    assert model_input["content_sha256"] == sha256_text("注入正文")
    assert model_input["source"] == "begin_finalization"
    tool = projection.events[3]["payload"]
    assert tool["hash"] == "abc" and "model_content" not in tool
    assert tool["model_content_sha256"] == sha256_text("工具正文")
    assert not projection.has_anomalies

    # 私有读者要正文时显式要，且派生仍能从完整投影的事件重建。
    full = project_durable_events(ledger.events, include_model_visible_text=True)
    assert full.events[1]["payload"]["system"] == "宪法正文"
    assert full.events[3]["payload"]["model_content"] == "工具正文"


def test_projection_redacts_folded_text_inside_history_compacted_items() -> None:
    """``list[].field`` 形式：history_compacted.folded 里每一项的 model_content 剔正文留哈希。"""

    ledger = _Ledger()
    ledger.add("task", {"question": "q", "task_frame_hash": "h"})
    ledger.add(
        "history_compacted",
        {
            "folded": [
                {"call_id": "c1", "tool": "market_data", "chars_before": 900, "model_content": "折叠正文一"},
                {"call_id": "c2", "tool": "market_data", "chars_before": 800, "model_content": "折叠正文二"},
            ],
            "folded_messages": 2,
            "chars_saved": 1500,
        },
    )

    projection = project_durable_events(ledger.events)
    dumped = json.dumps(list(projection.events), ensure_ascii=False)
    assert "折叠正文一" not in dumped and "折叠正文二" not in dumped
    folded = projection.events[1]["payload"]["folded"]
    assert [item["call_id"] for item in folded] == ["c1", "c2"]
    assert folded[0]["model_content_sha256"] == sha256_text("折叠正文一")
    assert folded[0]["model_content_chars"] == len("折叠正文一")
    assert folded[0]["chars_before"] == 900 and "model_content" not in folded[0]
    assert projection.events[1]["payload"]["chars_saved"] == 1500
    assert not projection.has_anomalies
    full = project_durable_events(ledger.events, include_model_visible_text=True)
    assert full.events[1]["payload"]["folded"][1]["model_content"] == "折叠正文二"


def test_projection_leaves_events_without_model_visible_text_byte_identical() -> None:
    events = (
        EpisodeEvent(1, "task", {"question": "今天怎么看"}),
        EpisodeEvent(2, "tool_request", {"call_id": "c1", "name": "finance_query"}),
        EpisodeEvent(3, "tool_result", {"call_id": "c1", "tool": "finance_query"}),
    )

    projection = project_durable_events(events)

    assert list(projection.events) == [event.to_dict() for event in events]

"""模型可见即已落账（INV-R1）：从 durable 事件派生模型消息，并在每次请求前对账。

来源：``docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md`` §3 INV-R1、
§6.1 P0。形状来自 dsh ``architecture.md``「Model-visible means logged」
（``deriveMessages()`` 从日志派生模型历史，运行时断言）与 pi ``harness.md`` §0.3
「每个 payload 只在一处」。搬的是不变量，不搬实现。

--------------------------------------------------------------------------
为什么要有这一层
--------------------------------------------------------------------------

loop 手里有两份状态：``messages``（真发给 provider 的列表）与 ``ledger.events``
（重放日志、对账权威）。它们由同一段代码在相邻两行分别维护，没有任何东西保证一致。
[实测 2026-09-07] 三处不一致：``tool_result`` 事件存 ``audit_payload``、模型看的是
``model_content``；四处 user 角色注入只落 reason 不落文本；system prompt 只有 hash。
后果是事后从产物看不出模型到底看到了什么。

修法不是「把 messages 也存一份」——那是第二事实源。修法是让 messages 成为事件的
**派生物**：每一条进入 messages 的内容都先有一条 durable 事件承载它，
``derive_messages`` 是对事件流的纯 fold，请求前断言 ``derive == messages``。
P1 把 messages 换成 ``EpisodeMessage`` 类型后，这条断言变成
``to_provider(derive) == to_provider(messages)``，本模块的 fold 规则不变。

--------------------------------------------------------------------------
fold 规则（一个 kind 一行；改这里必改终态稿 §6.1）
--------------------------------------------------------------------------

===================  ======================================================
``prompt_assembled``  → ``[system(content), user(content)]``
``model_input``       → ``user(content)``
``model_turn``        → ``assistant(content, tool_calls)``，**仅当** ``error`` 为空
                        （失败 turn 不进消息历史，两条 loop 同此）
``tool_result``       → ``tool(call_id, model_content)``
``tool_error``        → ``tool(call_id, model_content)``
``tool_budget_state`` → 覆写最后一条 ``tool`` 消息的 content 为 ``model_content``
其余 kind              → 不产生消息
===================  ======================================================

``tool_result`` / ``tool_error`` 的 ``model_content`` 是本轮新加的字段。没有它的老事件
（本轮之前的产物）**无法派生**，``derive_messages`` 抛 ``DerivationUnavailable`` 而不是
猜——猜出来的历史比没有历史更糟。

--------------------------------------------------------------------------
严格与宽松
--------------------------------------------------------------------------

生产不炸：不一致只记 ``derive_mismatch``（``EpisodeScope.dump()`` 与两条 loop 的
账本各留一份），主路径照跑——观测设施故障不改变被观测对象的结论，与
``EpisodeScope.emit`` 吞 sink 异常同一条纪律。

测试炸：``conftest.py`` 强制 ``FORESIGHT_STRICT_DERIVATION=1``，于是全量套件里每一次
脚本化模型请求都在验 INV-R1，不另写一套「覆盖」它的用例。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, MutableSequence
import hashlib
import json
import os
from typing import Literal, Protocol

from intelligence.services.agent_runtime import EpisodeEvent, ModelTurn

__all__ = [
    "DerivationMismatch",
    "DerivationUnavailable",
    "MODEL_INPUT_KIND",
    "MODEL_INPUT_SOURCES",
    "HISTORY_COMPACTED_KIND",
    "MODEL_VISIBLE_TEXT_FIELDS",
    "MessageLedger",
    "ModelInputSource",
    "PROMPT_ASSEMBLED_KIND",
    "STRICT_DERIVATION_ENV",
    "TOOL_BUDGET_STATE_KIND",
    "append_model_input",
    "assistant_message",
    "assistant_message_from_payload",
    "check_derivation",
    "derive_messages",
    "describe_mismatch",
    "record_prompt_assembled",
    "record_tool_budget_state",
    "sha256_text",
    "strict_derivation_enabled",
    "system_message",
    "tool_message",
    "user_message",
]

MODEL_INPUT_KIND = "model_input"
PROMPT_ASSEMBLED_KIND = "prompt_assembled"
TOOL_BUDGET_STATE_KIND = "tool_budget_state"
HISTORY_COMPACTED_KIND = "history_compacted"
STRICT_DERIVATION_ENV = "FORESIGHT_STRICT_DERIVATION"

# user 角色注入的来源。值进事件 payload，是评测 / 投影分类的依据；新增来源先加这里，
# 再在发射点用——``append_model_input`` 对不在表里的 source 抛错，防止字面量漂移。
ModelInputSource = Literal[
    "opening_prefetch",
    "steering_invalid_plan",
    "steering_invalid_finish",
    "steering_repair_finalize",
    "begin_finalization",
    "mode_decision",
    "sub_research",
    "repair_goal",
]
MODEL_INPUT_SOURCES: frozenset[str] = frozenset(
    {
        "opening_prefetch",
        "steering_invalid_plan",
        "steering_invalid_finish",
        "steering_repair_finalize",
        "begin_finalization",
        "mode_decision",
        "sub_research",
        "repair_goal",
    }
)

# 投影层默认剔除的模型可见正文字段：``(kind, field)``。私有 durable 流带正文，
# 对外 artifact 只留 sha256 与字符数（``episode_projection.project_durable_events``）。
# ``list[].field`` 形式指列表字段里每一项的正文（历史折叠一条事件折多条消息）。
MODEL_VISIBLE_TEXT_FIELDS: frozenset[tuple[str, str]] = frozenset(
    {
        (PROMPT_ASSEMBLED_KIND, "system"),
        (PROMPT_ASSEMBLED_KIND, "user"),
        (MODEL_INPUT_KIND, "content"),
        (TOOL_BUDGET_STATE_KIND, "model_content"),
        ("tool_result", "model_content"),
        ("tool_error", "model_content"),
        (HISTORY_COMPACTED_KIND, "folded[].model_content"),
    }
)


class MessageLedger(Protocol):
    """两条 loop 的账本都长这样：``add(kind, payload)``。本模块只依赖这一个方法。"""

    def add(self, kind: str, payload: dict[str, object]) -> object: ...


class DerivationUnavailable(RuntimeError):
    """事件流缺派生所需字段（老产物、或发射点漏了字段），不能派生就不猜。"""


class DerivationMismatch(RuntimeError):
    """严格模式下：派生消息与实际要发出的消息不一致。"""


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def strict_derivation_enabled() -> bool:
    return os.environ.get(STRICT_DERIVATION_ENV, "") == "1"


# ── 消息构造器：四种角色只在这里拼形状 ─────────────────────────────────────


def system_message(content: str) -> dict[str, object]:
    return {"role": "system", "content": content}


def user_message(content: str) -> dict[str, object]:
    return {"role": "user", "content": content}


def tool_message(call_id: str, content: str) -> dict[str, object]:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _assistant_tool_calls(
    calls: Iterable[tuple[str, str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "id": call_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(arguments, ensure_ascii=False),
            },
        }
        for call_id, name, arguments in calls
    ]


def assistant_message(turn: ModelTurn) -> dict[str, object]:
    """loop 侧：从 ``ModelTurn`` 拼 assistant 消息。与 ``assistant_message_from_payload``
    必须逐字节同形——那是 INV-R1 成立的前提，``test_episode_messages`` 钉住。"""

    message: dict[str, object] = {"role": "assistant", "content": turn.content}
    if turn.tool_calls:
        message["tool_calls"] = _assistant_tool_calls(
            (call.call_id, call.name, call.to_dict()["arguments"])
            for call in turn.tool_calls
        )
    return message


def assistant_message_from_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """派生侧：从 ``model_turn`` 事件 payload（``ModelTurn.to_dict()`` 的形状）拼 assistant 消息。"""

    message: dict[str, object] = {
        "role": "assistant",
        "content": str(payload.get("content") or ""),
    }
    raw_calls = payload.get("tool_calls") or []
    if isinstance(raw_calls, (list, tuple)) and raw_calls:
        calls: list[tuple[str, str, object]] = []
        for item in raw_calls:
            if not isinstance(item, Mapping):
                raise DerivationUnavailable("model_turn.tool_calls 元素不是对象")
            calls.append(
                (
                    str(item.get("call_id") or ""),
                    str(item.get("name") or ""),
                    item.get("arguments"),
                )
            )
        message["tool_calls"] = _assistant_tool_calls(calls)
    return message


# ── 发射助手：进 messages 的内容先有 durable 事件承载 ─────────────────────


def record_prompt_assembled(
    ledger: MessageLedger, *, system: str, user: str
) -> None:
    """``assemble_prompt`` 之后、首轮请求之前发一条。正文进 durable 私有流；
    hash 同时落下，投影剔正文后仍能对账「system 变过没有」。"""

    ledger.add(
        "prompt_assembled",
        {
            "system": system,
            "user": user,
            "system_sha256": sha256_text(system),
            "user_sha256": sha256_text(user),
            "system_chars": len(system),
            "user_chars": len(user),
        },
    )


def append_model_input(
    messages: MutableSequence[dict[str, object]],
    ledger: MessageLedger,
    *,
    content: str,
    source: ModelInputSource,
) -> None:
    """user 角色注入的唯一入口：先落事件，再进 messages。

    顺序是有意的：事件在前，消息在后——崩溃只可能留下「事件有、消息无」，
    而消息是派生物，丢了能重建；反过来就是丢账。P2 落盘后这一条成为 INV-R2 的
    「意图先于效果」在输入侧的兑现。
    """

    if source not in MODEL_INPUT_SOURCES:
        raise ValueError(f"未登记的 model_input 来源: {source!r}")
    text = str(content)
    ledger.add(
        "model_input",
        {"role": "user", "source": source, "content": text},
    )
    messages.append(user_message(text))


def record_tool_budget_state(
    ledger: MessageLedger,
    *,
    runtime_budget: Mapping[str, object],
    model_content: str,
) -> None:
    """底座把 ``runtime_budget`` 叠进最后一条 tool 消息之后发一条：模型看到的整段
    content 与叠进去的预算块。它是覆写不是追加，所以派生规则也是覆写。"""

    ledger.add(
        "tool_budget_state",
        {"runtime_budget": dict(runtime_budget), "model_content": str(model_content)},
    )


# ── 派生与对账 ─────────────────────────────────────────────────────────────


def _payload_dict(event: EpisodeEvent) -> dict[str, object]:
    # ``EpisodeEvent.payload`` 是冻结的 MappingProxyType / tuple；``to_dict`` 复制回
    # 普通 dict / list，``json.dumps`` 才能吃。
    payload = event.to_dict()["payload"]
    assert isinstance(payload, dict)
    return payload


def _require_text(payload: Mapping[str, object], key: str, *, event: EpisodeEvent) -> str:
    if key not in payload:
        raise DerivationUnavailable(
            f"{event.kind}#{event.sequence} 缺 {key}，无法派生模型消息"
        )
    return str(payload[key])


def derive_messages(events: Iterable[EpisodeEvent]) -> list[dict[str, object]]:
    """对 durable 事件流做纯 fold，得到模型在下一次请求时会看到的消息列表。

    只读、无 IO、无模型、不依赖 loop 内部状态——它必须能在事后对着产物重跑。
    """

    messages: list[dict[str, object]] = []
    for event in events:
        kind = event.kind
        if kind == PROMPT_ASSEMBLED_KIND:
            payload = _payload_dict(event)
            messages.append(system_message(_require_text(payload, "system", event=event)))
            messages.append(user_message(_require_text(payload, "user", event=event)))
        elif kind == MODEL_INPUT_KIND:
            payload = _payload_dict(event)
            messages.append(user_message(_require_text(payload, "content", event=event)))
        elif kind == "model_turn":
            payload = _payload_dict(event)
            if str(payload.get("error") or ""):
                continue
            messages.append(assistant_message_from_payload(payload))
        elif kind in {"tool_result", "tool_error"}:
            payload = _payload_dict(event)
            messages.append(
                tool_message(
                    _require_text(payload, "call_id", event=event),
                    _require_text(payload, "model_content", event=event),
                )
            )
        elif kind == TOOL_BUDGET_STATE_KIND:
            payload = _payload_dict(event)
            if not messages or messages[-1].get("role") != "tool":
                raise DerivationUnavailable(
                    f"tool_budget_state#{event.sequence} 前面不是 tool 消息，无处覆写"
                )
            messages[-1] = {
                **messages[-1],
                "content": _require_text(payload, "model_content", event=event),
            }
        elif kind == HISTORY_COMPACTED_KIND:
            # 历史折叠（spec 2026-09-07 episode-history-compaction §3.2）：更早批次的 tool
            # 消息正文被换成 E 号索引。事件里每条 folded 都带替换后的 ``model_content``，
            # 派生按 call_id 找到那条 tool 消息覆写——没带正文的老事件无法派生，不猜。
            payload = _payload_dict(event)
            folded = payload.get("folded") or []
            if not isinstance(folded, list):
                raise DerivationUnavailable(f"history_compacted#{event.sequence} 的 folded 不是列表")
            for item in folded:
                if not isinstance(item, Mapping):
                    raise DerivationUnavailable(f"history_compacted#{event.sequence} 的 folded 项不是对象")
                call_id = str(item.get("call_id") or "")
                if "model_content" not in item:
                    raise DerivationUnavailable(
                        f"history_compacted#{event.sequence} 折叠项 {call_id!r} 缺 model_content，无法派生"
                    )
                target = _last_tool_message_index(messages, call_id)
                if target is None:
                    raise DerivationUnavailable(
                        f"history_compacted#{event.sequence} 折叠的 {call_id!r} 在派生消息里找不到"
                    )
                messages[target] = {**messages[target], "content": str(item["model_content"])}
    return messages


def _last_tool_message_index(messages: list[dict[str, object]], call_id: str) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") == "tool" and str(message.get("tool_call_id") or "") == call_id:
            return index
    return None


def describe_mismatch(
    derived: list[dict[str, object]], actual: list[dict[str, object]]
) -> str:
    """一句话定位第一处分歧：位置、两边角色、内容 hash。不回显正文——这段话会进收据。"""

    if len(derived) != len(actual):
        head = f"长度 {len(derived)} (derived) vs {len(actual)} (actual)"
    else:
        head = f"长度相同 {len(actual)}"
    for index, (left, right) in enumerate(zip(derived, actual)):
        if left != right:
            return (
                f"{head}; 首处分歧 @{index}: "
                f"derived role={left.get('role')} sha={sha256_text(json.dumps(left, ensure_ascii=False, sort_keys=True))[:12]} "
                f"vs actual role={right.get('role')} sha={sha256_text(json.dumps(right, ensure_ascii=False, sort_keys=True))[:12]}"
            )
    shorter = min(len(derived), len(actual))
    return f"{head}; 前 {shorter} 条一致，多出的一侧从 @{shorter} 起"


def check_derivation(
    events: Iterable[EpisodeEvent],
    messages: list[dict[str, object]],
    *,
    on_mismatch: Callable[[str], None] | None = None,
) -> bool:
    """请求前对账。一致返回 True；不一致时严格模式抛 ``DerivationMismatch``，
    否则调 ``on_mismatch(detail)`` 并返回 False（主路径不受影响）。

    ``DerivationUnavailable``（缺字段）按不一致处理：它是发射点漏账，不是派生器的错。
    """

    try:
        derived = derive_messages(events)
    except DerivationUnavailable as exc:
        detail = f"unavailable: {exc}"
    else:
        if derived == list(messages):
            return True
        detail = describe_mismatch(derived, list(messages))
    if strict_derivation_enabled():
        raise DerivationMismatch(detail)
    if on_mismatch is not None:
        on_mismatch(detail)
    return False

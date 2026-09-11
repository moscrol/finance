"""Episode 消息类型 + 模型可见即已落账（INV-R1）。

来源：``docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md`` §3 INV-R1、
§6.1 P0（派生与对账）、§6.2 P1（消息类型）。形状来自 dsh ``architecture.md``
「Model-visible means logged」与 pi「loop 全程 ``AgentMessage``，只在 LLM 边界
``convertToLlm``」。搬的是不变量，不搬实现。

--------------------------------------------------------------------------
为什么 loop 要有自己的消息类型（P1）
--------------------------------------------------------------------------

此前 ``messages: list[dict]`` 是 OpenAI 线格式贯穿整条 loop：换 provider 消息格式
（Anthropic content blocks、GLM thinking 字段）要碰 loop；审计-only 的消息无处放；
``_append_tool_budget_state`` 直接 ``messages[-1]["content"] = …`` 原地改字典。
``EpisodeMessage`` 是 DDD 意义上的防腐层：loop 只认它，``to_provider`` 在
``AgentModelClient.complete`` 之前一次性转线格式。``AgentModelClient`` 协议**不变**
（仍收 ``list[dict]``），所有模型客户端与测试替身零改动。

--------------------------------------------------------------------------
为什么 messages 必须是事件的派生物（P0）
--------------------------------------------------------------------------

loop 手里有两份状态：``messages``（真发给 provider 的）与 ``ledger.events``
（重放日志、对账权威）。修法不是「把 messages 也存一份」——那是第二事实源。修法是让
每一条进入 messages 的内容都先有一条 durable 事件承载它，``derive_messages`` 是对事件流
的纯 fold，请求前断言 ``to_provider(derive) == to_provider(messages)``。

fold 规则（一个 kind 一行；改这里必改终态稿 §6.1）：

===================  ======================================================
``prompt_assembled``  → ``[system(content), user(content)]``
``model_input``       → ``user(content)``
``model_turn``        → ``assistant(content, tool_calls)``，**仅当** ``error`` 为空
``application_tool_call`` → ``assistant("", tool_calls=[该调用])``：应用（非模型）替模型
                      补发的一次工具调用声明（空池回退）。没有它，随后的 ``tool`` 消息就是
                      孤儿——OpenAI 兼容接口对没有 ``assistant.tool_calls`` 声明的 tool 消息
                      回 400（2026-09-09 M3 / M6 真实 run 第 3/4 轮）。
``tool_result``       → ``tool(call_id, model_content)``
``tool_error``        → ``tool(call_id, model_content)``
``tool_budget_state`` → 覆写最后一条 ``tool`` 消息的 content 为 ``model_content``
其余 kind              → 不产生消息
===================  ======================================================

没有 ``model_content`` 的老事件**无法派生**，抛 ``DerivationUnavailable`` 而不是猜。

严格与宽松：生产不炸只记 ``derive_mismatch``；``conftest`` 强制
``FORESIGHT_STRICT_DERIVATION=1``，全量套件里每一次脚本化请求都在验。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, MutableSequence, Sequence
from dataclasses import dataclass, replace
import hashlib
import json
import os
from typing import Literal, Protocol

from intelligence.services.agent_runtime import EpisodeEvent, ModelToolCall, ModelTurn

__all__ = [
    "APPLICATION_TOOL_CALL_KIND",
    "APPLICATION_TOOL_CALL_SOURCES",
    "ApplicationToolCallSource",
    "DerivationMismatch",
    "DerivationUnavailable",
    "EpisodeMessage",
    "INBOX_CLAIMED_KIND",
    "INBOX_DISCARDED_KIND",
    "INBOX_INSERTED_KIND",
    "MODEL_INPUT_KIND",
    "MODEL_INPUT_SOURCES",
    "HISTORY_COMPACTED_KIND",
    "MODEL_VISIBLE_TEXT_FIELDS",
    "MessageLedger",
    "MessageRole",
    "ModelInputSource",
    "PROMPT_ASSEMBLED_KIND",
    "PROMPT_SOURCE_EPISODE",
    "PROMPT_SOURCE_FINALIZER",
    "PromptSource",
    "ProviderDialect",
    "STRICT_DERIVATION_ENV",
    "TOOL_BUDGET_STATE_KIND",
    "append_model_input",
    "assistant_message",
    "assistant_message_from_application_call",
    "assistant_message_from_payload",
    "check_derivation",
    "derive_messages",
    "describe_mismatch",
    "record_application_tool_call",
    "record_prompt_assembled",
    "record_tool_budget_state",
    "rewrite_last_tool_content",
    "sha256_text",
    "strict_derivation_enabled",
    "system_message",
    "to_provider",
    "tool_message",
    "undeclared_tool_call_ids",
    "user_message",
]

MODEL_INPUT_KIND = "model_input"
# 应用替模型补发的工具调用声明（终态稿 §6.1 补充，2026-09-09）。它承载的是模型下一次
# 请求会看到的 ``assistant.tool_calls``，所以和 model_input 一样归 durable、先落账再进 messages。
APPLICATION_TOOL_CALL_KIND = "application_tool_call"
PROMPT_ASSEMBLED_KIND = "prompt_assembled"
TOOL_BUDGET_STATE_KIND = "tool_budget_state"
HISTORY_COMPACTED_KIND = "history_compacted"
# 收件箱三事实（终态稿 §6.4 P3，INV-R5）。正文只在 ``inbox_inserted`` 落一份；
# ``inbox_claimed`` 只带 message_id——派生器按 id 回找正文，模型可见的那一刻才进消息。
INBOX_INSERTED_KIND = "inbox_inserted"
INBOX_CLAIMED_KIND = "inbox_claimed"
INBOX_DISCARDED_KIND = "inbox_discarded"
STRICT_DERIVATION_ENV = "FORESIGHT_STRICT_DERIVATION"

MessageRole = Literal["system", "user", "assistant", "tool"]
_ROLES: frozenset[str] = frozenset({"system", "user", "assistant", "tool"})

ProviderDialect = Literal["openai"]

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

# 应用发起工具调用的来源。今天只有空池回退一处；新增应用侧补枪先登记再发射，
# ``record_application_tool_call`` 对不在表里的 source 抛错，理由同 ``MODEL_INPUT_SOURCES``。
ApplicationToolCallSource = Literal["empty_pool_fallback"]
APPLICATION_TOOL_CALL_SOURCES: frozenset[str] = frozenset({"empty_pool_fallback"})

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
        (INBOX_INSERTED_KIND, "content"),
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


# ── 消息类型 ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EpisodeMessage:
    """loop 内部唯一的消息表示。线格式只在 ``to_provider`` 出现。

    ``source`` 是审计字段（哪条注入 / 哪种事件产生了它），不进线格式；INV-R1 比较的是
    ``to_provider`` 之后的结果，所以 source 不同不算分歧。
    """

    role: MessageRole
    content: str
    tool_calls: tuple[ModelToolCall, ...] = ()
    tool_call_id: str = ""
    source: str = ""

    def __post_init__(self) -> None:
        if self.role not in _ROLES:
            raise ValueError(f"未知消息角色: {self.role!r}")
        if not isinstance(self.content, str):
            raise ValueError("消息 content 必须是 str")
        if self.tool_calls and self.role != "assistant":
            raise ValueError("只有 assistant 消息可带 tool_calls")
        if self.role == "tool" and not str(self.tool_call_id).strip():
            raise ValueError("tool 消息必须带 tool_call_id")
        if self.tool_call_id and self.role != "tool":
            raise ValueError("只有 tool 消息可带 tool_call_id")
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))


def system_message(content: str, *, source: str = "prompt") -> EpisodeMessage:
    return EpisodeMessage(role="system", content=str(content), source=source)


def user_message(content: str, *, source: str = "prompt") -> EpisodeMessage:
    return EpisodeMessage(role="user", content=str(content), source=source)


def tool_message(call_id: str, content: str, *, source: str = "tool_result") -> EpisodeMessage:
    return EpisodeMessage(
        role="tool", content=str(content), tool_call_id=str(call_id), source=source
    )


def assistant_message(turn: ModelTurn) -> EpisodeMessage:
    """loop 侧：从 ``ModelTurn`` 拼 assistant 消息。"""

    return EpisodeMessage(
        role="assistant",
        content=turn.content,
        tool_calls=tuple(turn.tool_calls),
        source="model_turn",
    )


def assistant_message_from_payload(payload: Mapping[str, object]) -> EpisodeMessage:
    """派生侧：从 ``model_turn`` 事件 payload（``ModelTurn.to_dict()`` 形状）拼 assistant 消息。

    与 ``assistant_message`` 经 ``to_provider`` 后必须逐字节同形——INV-R1 成立的前提，
    ``test_episode_messages`` 钉住。
    """

    raw_calls = payload.get("tool_calls") or []
    calls: list[ModelToolCall] = []
    if isinstance(raw_calls, (list, tuple)):
        for item in raw_calls:
            if not isinstance(item, Mapping):
                raise DerivationUnavailable("model_turn.tool_calls 元素不是对象")
            arguments = item.get("arguments")
            if not isinstance(arguments, Mapping):
                raise DerivationUnavailable("model_turn.tool_calls.arguments 不是对象")
            calls.append(
                ModelToolCall(
                    str(item.get("call_id") or ""),
                    str(item.get("name") or ""),
                    arguments,
                )
            )
    return EpisodeMessage(
        role="assistant",
        content=str(payload.get("content") or ""),
        tool_calls=tuple(calls),
        source="model_turn",
    )


def _application_call_message(call: ModelToolCall) -> EpisodeMessage:
    # content 固定为空串：与模型只点工具不说话的 model_turn 同形（``ModelTurn.content`` 为空）。
    return EpisodeMessage(
        role="assistant",
        content="",
        tool_calls=(call,),
        source=APPLICATION_TOOL_CALL_KIND,
    )


def assistant_message_from_application_call(payload: Mapping[str, object]) -> EpisodeMessage:
    """派生侧：从 ``application_tool_call`` 事件 payload（``ModelToolCall.to_dict()`` + source）
    拼出声明该调用的 assistant 消息。与 ``record_application_tool_call`` 进 messages 的那条经
    ``to_provider`` 后必须逐字节同形。"""

    arguments = payload.get("arguments")
    if not isinstance(arguments, Mapping):
        raise DerivationUnavailable("application_tool_call.arguments 不是对象")
    call = ModelToolCall(
        str(payload.get("call_id") or ""), str(payload.get("name") or ""), arguments
    )
    return _application_call_message(call)


def undeclared_tool_call_ids(messages: Sequence[EpisodeMessage]) -> tuple[str, ...]:
    """每条 ``tool`` 消息的 ``tool_call_id`` 必须被前面某条 assistant 的 ``tool_calls`` 声明过；
    返回没有声明的那些 id（按出现顺序）。空元组才是合法的 provider 请求。

    这是 2026-09-09 M3 / M6 两次 HTTP 400 的失败形状：``derive_messages`` 能派生出它，
    ``check_derivation`` 却看不出——两侧一样错就对得上账。"""

    declared: set[str] = set()
    orphans: list[str] = []
    for message in messages:
        if message.role == "assistant":
            declared.update(call.call_id for call in message.tool_calls)
        elif message.role == "tool" and message.tool_call_id not in declared:
            orphans.append(message.tool_call_id)
    return tuple(orphans)


def rewrite_last_tool_content(
    messages: MutableSequence[EpisodeMessage], content: str
) -> EpisodeMessage:
    """覆写最后一条 tool 消息的 content（底座预算注入唯一的原地改写点）。返回新消息。"""

    if not messages or messages[-1].role != "tool":
        raise ValueError("最后一条不是 tool 消息，无处覆写")
    updated = replace(messages[-1], content=str(content))
    messages[-1] = updated
    return updated


# ── 线格式边界 ──────────────────────────────────────────────────────────────


def _openai_tool_calls(calls: Iterable[ModelToolCall]) -> list[dict[str, object]]:
    return [
        {
            "id": call.call_id,
            "type": "function",
            "function": {
                "name": call.name,
                "arguments": json.dumps(call.to_dict()["arguments"], ensure_ascii=False),
            },
        }
        for call in calls
    ]


def _to_openai(message: EpisodeMessage) -> dict[str, object]:
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content,
        }
    if message.role == "assistant":
        payload: dict[str, object] = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            payload["tool_calls"] = _openai_tool_calls(message.tool_calls)
        return payload
    return {"role": message.role, "content": message.content}


def to_provider(
    messages: Sequence[EpisodeMessage], *, dialect: ProviderDialect = "openai"
) -> list[dict[str, object]]:
    """``AgentModelClient.complete`` 之前唯一的转线格式点。今天只有 OpenAI 方言——
    provider 链（GLM / gpt 中转）都吃它；加方言在这里加分支，不碰 loop。"""

    if dialect != "openai":
        raise ValueError(f"未支持的 provider 方言: {dialect!r}")
    return [_to_openai(message) for message in messages]


# ── 发射助手：进 messages 的内容先有 durable 事件承载 ─────────────────────


PromptSource = Literal["episode", "finalizer"]
PROMPT_SOURCE_EPISODE = "episode"
# 兜底合成（EpisodeFinalizer.recover）自己拼一段 prompt 单独问一次模型：它是模型可见内容，
# 所以也落 prompt_assembled（INV-R1 的覆盖面，P0 已知边界 a），但**不进** episode 的消息历史，
# 派生器对它跳过。
PROMPT_SOURCE_FINALIZER = "finalizer"


def record_prompt_assembled(
    ledger: MessageLedger,
    *,
    system: str,
    user: str,
    source: PromptSource = PROMPT_SOURCE_EPISODE,
) -> None:
    """``assemble_prompt`` 之后、首轮请求之前发一条。正文进 durable 私有流；
    hash 同时落下，投影剔正文后仍能对账「system 变过没有」。

    ``source="episode"`` 的一条派生成 ``[system, user]`` 两条消息；``"finalizer"`` 的只落账
    不派生。老产物没有 ``source`` 键，读作 ``episode``。
    """

    if source not in {PROMPT_SOURCE_EPISODE, PROMPT_SOURCE_FINALIZER}:
        raise ValueError(f"未登记的 prompt_assembled 来源: {source!r}")
    payload: dict[str, object] = {
        "system": system,
        "user": user,
        "system_sha256": sha256_text(system),
        "user_sha256": sha256_text(user),
        "system_chars": len(system),
        "user_chars": len(user),
    }
    if source != PROMPT_SOURCE_EPISODE:
        # 只在非默认来源时带键：episode 那条的形状与 P0 逐字节相同。
        payload["source"] = source
    ledger.add("prompt_assembled", payload)


def append_model_input(
    messages: MutableSequence[EpisodeMessage],
    ledger: MessageLedger,
    *,
    content: str,
    source: ModelInputSource,
) -> EpisodeMessage:
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
    message = user_message(text, source=source)
    messages.append(message)
    return message


def record_application_tool_call(
    messages: MutableSequence[EpisodeMessage],
    ledger: MessageLedger,
    *,
    call: ModelToolCall,
    source: ApplicationToolCallSource,
) -> EpisodeMessage:
    """应用（非模型）发起工具调用的唯一入口：先落 durable 事件，再把声明它的 assistant
    消息进 messages。要在派发 / ``tool_request`` **之前**调——声明先于意图，意图先于效果。

    为什么不伪造一条 ``model_turn``：那会让「模型说过什么」的账掺进底座自己的决定，
    重放消费者与评测都会把它算成一次模型调用。为什么不只在发送边缘补消息：那样 durable
    流与 live messages 分叉，``check_derivation`` 在下一次请求前就会红。
    """

    if source not in APPLICATION_TOOL_CALL_SOURCES:
        raise ValueError(f"未登记的 application_tool_call 来源: {source!r}")
    ledger.add("application_tool_call", {"source": source, **call.to_dict()})
    message = _application_call_message(call)
    messages.append(message)
    return message


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


def derive_messages(events: Iterable[EpisodeEvent]) -> list[EpisodeMessage]:
    """对 durable 事件流做纯 fold，得到模型在下一次请求时会看到的消息列表。

    只读、无 IO、无模型、不依赖 loop 内部状态——它必须能在事后对着产物重跑。
    """

    messages: list[EpisodeMessage] = []
    # 收件箱：已入箱、尚未认领 / 丢弃的正文，按 message_id 暂存。认领那一刻才成为模型可见。
    inbox_pending: dict[str, tuple[str, str]] = {}
    for event in events:
        kind = event.kind
        if kind == INBOX_INSERTED_KIND:
            payload = _payload_dict(event)
            message_id = _require_text(payload, "message_id", event=event)
            inbox_pending[message_id] = (
                _require_text(payload, "content", event=event),
                str(payload.get("source") or INBOX_CLAIMED_KIND),
            )
        elif kind == INBOX_CLAIMED_KIND:
            payload = _payload_dict(event)
            message_id = _require_text(payload, "message_id", event=event)
            pending = inbox_pending.pop(message_id, None)
            if pending is None:
                raise DerivationUnavailable(
                    f"inbox_claimed#{event.sequence} 认领的 {message_id!r} 没有在箱的 inbox_inserted，无法派生"
                )
            content, source = pending
            messages.append(user_message(content, source=source))
        elif kind == INBOX_DISCARDED_KIND:
            payload = _payload_dict(event)
            inbox_pending.pop(str(payload.get("message_id") or ""), None)
        elif kind == PROMPT_ASSEMBLED_KIND:
            payload = _payload_dict(event)
            if str(payload.get("source") or PROMPT_SOURCE_EPISODE) != PROMPT_SOURCE_EPISODE:
                # 兜底合成的 prompt 是另一段独立对话，不在 episode 的 messages 里。
                continue
            messages.append(system_message(_require_text(payload, "system", event=event)))
            messages.append(user_message(_require_text(payload, "user", event=event)))
        elif kind == MODEL_INPUT_KIND:
            payload = _payload_dict(event)
            messages.append(
                user_message(
                    _require_text(payload, "content", event=event),
                    source=str(payload.get("source") or MODEL_INPUT_KIND),
                )
            )
        elif kind == "model_turn":
            payload = _payload_dict(event)
            if str(payload.get("error") or ""):
                continue
            messages.append(assistant_message_from_payload(payload))
        elif kind == APPLICATION_TOOL_CALL_KIND:
            messages.append(assistant_message_from_application_call(_payload_dict(event)))
        elif kind in {"tool_result", "tool_error"}:
            payload = _payload_dict(event)
            messages.append(
                tool_message(
                    _require_text(payload, "call_id", event=event),
                    _require_text(payload, "model_content", event=event),
                    source=kind,
                )
            )
        elif kind == TOOL_BUDGET_STATE_KIND:
            payload = _payload_dict(event)
            if not messages or messages[-1].role != "tool":
                raise DerivationUnavailable(
                    f"tool_budget_state#{event.sequence} 前面不是 tool 消息，无处覆写"
                )
            messages[-1] = replace(
                messages[-1], content=_require_text(payload, "model_content", event=event)
            )
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
                messages[target] = replace(messages[target], content=str(item["model_content"]))
    return messages


def _last_tool_message_index(messages: Sequence[EpisodeMessage], call_id: str) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.role == "tool" and message.tool_call_id == call_id:
            return index
    return None


def describe_mismatch(
    derived: Sequence[Mapping[str, object]], actual: Sequence[Mapping[str, object]]
) -> str:
    """一句话定位第一处分歧（线格式两侧）：位置、两边角色、内容 hash。不回显正文——
    这段话会进收据。"""

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
    messages: Sequence[EpisodeMessage],
    *,
    on_mismatch: Callable[[str], None] | None = None,
) -> bool:
    """请求前对账：比较两侧 ``to_provider`` 的结果（模型真看到的）。一致返回 True；
    不一致时严格模式抛 ``DerivationMismatch``，否则调 ``on_mismatch(detail)`` 并返回 False。

    ``DerivationUnavailable``（缺字段）按不一致处理：它是发射点漏账，不是派生器的错。
    """

    try:
        derived = to_provider(derive_messages(events))
    except DerivationUnavailable as exc:
        detail = f"unavailable: {exc}"
    else:
        actual = to_provider(messages)
        if derived == actual:
            return True
        detail = describe_mismatch(derived, actual)
    if strict_derivation_enabled():
        raise DerivationMismatch(detail)
    if on_mismatch is not None:
        on_mismatch(detail)
    return False

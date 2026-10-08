"""崩溃后的恢复：读一份完整 ``EpisodeState``、按预留 id 点查结算、switch（INV-R3）。

来源：``docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md`` §6.3 第 4 条；
工单 #29 步骤 C1。策略照 pi §4.5 三行，量纲按本仓：

=====================  ==========================================================
模型意图无结算          捕获的重试余量 > 0 且截止未过 → ``retry_model``；否则合成
                        ``model_error{interrupted}``，截止已过再合成 ``finish{interrupted}``
工具意图无结算          意图 ``replay=safe`` **且**当前注册表该工具仍 ``safe`` 且截止未过
                        → ``replay_tools``；否则合成 ``tool_error{interrupted}``
取消已 durable          （``state.cancel``）→ 先结算悬空意图，再合成 ``finish{cancelled}``
=====================  ==========================================================

三条纪律：

1. **不从缺席推断**——没有 ``state.json`` 就拒绝（``RestoreUnavailable``），不拿事件流猜位置；
   状态里预留了 id 但日志里没有那条意图，也拒绝（日志落后于状态 = 存储损坏）。
2. **点查合法、重放推断不合法**——按预留的 ``turn_id`` / ``call_id`` 在日志里找结算，找到就
   顺着结算给下一动作；这不是「重放整条日志推出位置」。
3. **本单只给下一动作，不重新驱动 loop**——``ResumePlan`` 是数据；重新开车是 P4 ``step()``
   的事（§12 第 3 题：重启后只登记、人工触发）。能闭合的（取消 / 截止已过）在这里直接闭合成
   ``AgentOutcome``，让 ``list_open()`` 不再列它。

合成事件逐条同步写回 store（恢复是低频控制路径；确认之后才能更新 checkpoint / 返回下一动作），
``finish`` 与 ``put_state(done)`` 都确认后才闭合。sequence 仍追加取号
（本仓日志按序号连续、不预留空洞；预留的是关联 id——工单 #29 §0 第 2 条），并带 ``intent_sequence``
指回意图、``synthesized=True`` 标明来源。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import json
from typing import Literal

from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent
from intelligence.services.episode_authorization import validate_current_authorization
from intelligence.services.episode_effects import (
    UnknownEffect,
    UnreconciledEffects,
    merge_unknown_effects,
    unknown_effects_from_payload,
    unknown_effects_payload,
)
from intelligence.services.episode_entry_identity import (
    capture_entry_identity,
    entry_identities_match,
    validate_current_entry_identity,
)
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.episode_store import (
    EPISODE_LOG_VERSION,
    EpisodePhase,
    EpisodeState,
    EpisodeStore,
    episode_writer,
    now_iso,
    require_known_kinds,
)
from intelligence.services.research_harness import FinanceResearchHarness, ResearchHarness
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    UnknownResearchTool,
)

__all__ = [
    "INTERRUPTED",
    "RestoreDisposition",
    "RestoreResult",
    "RestoreUnavailable",
    "ResumeAction",
    "ResumePlan",
    "restore_episode",
]

INTERRUPTED = "interrupted"
_RECOVERY_RESERVED_ID = "finalization_recovery"

ResumeAction = Literal[
    "model_turn",  # 向模型开口（规划 / 收口 / 修复，按 plan.phase）
    "retry_model",  # 同一意图再问一次（结果丢了，请求是只读的）
    "dispatch_tools",  # 模型已点了工具但意图还没落：派发这些 call_id
    "replay_tools",  # 意图已落、结算没落、replay=safe：同参数重跑
    "interpret_turn",  # 模型已回了非工具轮，下一步是解释它（PLAN / FINAL_JSON 准入）
    "finalize",  # 模型侧出错但证据可能还在：进收口
]
RestoreDisposition = Literal["already_terminal", "closed", "resumable"]


class RestoreUnavailable(RuntimeError):
    """状态缺失 / 版本不符 / 日志落后于状态：不能恢复，也不猜。"""


@dataclass(frozen=True)
class ResumePlan:
    action: ResumeAction
    phase: EpisodePhase
    reason: str
    turn_id: str = ""
    call_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "phase": self.phase,
            "reason": self.reason,
            "turn_id": self.turn_id,
            "call_ids": list(self.call_ids),
        }


@dataclass(frozen=True)
class RestoreResult:
    episode_id: str
    disposition: RestoreDisposition
    state_before: EpisodeState
    state_after: EpisodeState
    events: tuple[EpisodeEvent, ...]
    synthesized: tuple[EpisodeEvent, ...]
    plan: ResumePlan | None
    outcome: AgentOutcome | None
    # P3 遗留、P4 收：崩溃时箱里「入箱了、还没认领也没丢弃」的话（message_id）。恢复方
    # 重新驱动时要把它们递回收件箱，否则用户递进去的话会随崩溃静默消失（INV-R5 三事实里
    # 缺了第三件）。这里只**列出**，不认领——认领是 loop 的事，恢复读的是事实。
    pending_inbox: tuple[str, ...] = ()
    # 「意图已落、结算未落」的外部效果：那次请求是否已执行、是否已计费，这里答不出来。
    # 恢复只**登记**这段未知窗口，不替人决定它是否要付钱——对账要扣的是活账本，而恢复
    # 拿到的是数据。非空即代表 ``state_after.budget_snapshot`` 的余额尚未对账。
    unreconciled_effects: UnreconciledEffects = ()
    # 该检查点是否带着已核对的入口身份（用户/会话/run）。False = 起跑时就没有门，恢复也只能
    # 由同样未绑定的调用方读；将来的自动续跑驱动应当要求 True，读这一位，而不是自己猜主人。
    entry_identity_bound: bool = False

    @property
    def terminal(self) -> bool:
        return self.outcome is not None or self.disposition == "already_terminal"

    def to_dict(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "disposition": self.disposition,
            "phase_before": self.state_before.phase,
            "phase_after": self.state_after.phase,
            "synthesized": [event.to_dict() for event in self.synthesized],
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "stop_reason": self.outcome.stop_reason if self.outcome is not None else None,
            "pending_inbox": list(self.pending_inbox),
            "entry_identity_bound": self.entry_identity_bound,
        }


def pending_inbox_messages(events: Sequence[EpisodeEvent]) -> tuple[str, ...]:
    """入箱了、既未认领也未丢弃的 message_id，按入箱序。"""

    pending: dict[str, None] = {}
    for event in events:
        message_id = str(event.payload.get("message_id") or "")
        if not message_id:
            continue
        if event.kind == "inbox_inserted":
            pending.setdefault(message_id, None)
        elif event.kind in {"inbox_claimed", "inbox_discarded"}:
            pending.pop(message_id, None)
    return tuple(pending)


# ── 内部：点查 ───────────────────────────────────────────────────────────────


def _parse_deadline(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _deadline_passed(state: EpisodeState, now: datetime) -> bool:
    deadline = _parse_deadline(state.deadline_at)
    if deadline is None:
        # 不知道截止 = 不敢重发外部效果。fail closed。
        return True
    if deadline.tzinfo is None and now.tzinfo is not None:
        deadline = deadline.replace(tzinfo=now.tzinfo)
    if deadline.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=deadline.tzinfo)
    return now >= deadline


def _find(
    events: Sequence[EpisodeEvent],
    *,
    kinds: frozenset[str],
    key: str,
    value: str,
    after: int = 0,
) -> EpisodeEvent | None:
    for event in events:
        if event.sequence <= after or event.kind not in kinds:
            continue
        if str(event.payload.get(key) or "") == value:
            return event
    return None


def _task_frame_hash(events: Sequence[EpisodeEvent]) -> str:
    for event in events:
        if event.kind == "task":
            return str(event.payload.get("task_frame_hash") or "")
    raise RestoreUnavailable("日志里没有 task 事件，无法锚定 task_frame_hash")


# ── 内部：合成 ───────────────────────────────────────────────────────────────


class _Synthesizer:
    """把合成事件追加到内存列表并写回 store；sequence 追加取号。"""

    def __init__(
        self,
        *,
        episode_id: str,
        store: EpisodeStore,
        events: list[EpisodeEvent],
        task_frame_hash: str,
        phase: EpisodePhase,
    ) -> None:
        self._episode_id = episode_id
        self._store = store
        self.events = events
        self._task_frame_hash = task_frame_hash
        self._phase = phase
        self.synthesized: list[EpisodeEvent] = []

    def add(self, kind: str, payload: Mapping[str, object]) -> EpisodeEvent:
        event = EpisodeEvent(
            len(self.events) + 1,
            kind,
            {
                **dict(payload),
                "task_frame_hash": self._task_frame_hash,
                "at": now_iso(),
                "synthesized": True,
                "restored_from_phase": self._phase,
            },
        )
        # A recovery plan/checkpoint must not get ahead of the settlements it
        # relies on. Unlike the hot loop, recovery has no guaranteed next intent
        # to flush them. ACK loss propagates: no plan/outcome, no rollback/retry.
        self._store.append(self._episode_id, (event,), sync=True)
        self.events.append(event)
        self.synthesized.append(event)
        return event


def _declared(value: object, allowed: frozenset[str] | set[str]) -> str:
    """把一个声明规范化成凭证域；认不出来的一律 ``unknown``。

    恢复读到一个没见过的声明值时不能崩（恢复路径本身不该成为新的失败源），也不能把它
    归成最宽松的那一档。``unknown`` 在 ``may_have_been_billed`` 里按「可能已计费」算，
    方向朝多记账偏——这是这里唯一安全的偏法。
    """

    text = str(value or "").strip()
    return text if text in allowed else "unknown"


def _settle_model_interrupted(
    synth: _Synthesizer, *, intent: EpisodeEvent, turn_id: str
) -> None:
    synth.add(
        "model_error",
        {
            "reason": INTERRUPTED,
            "turn_id": turn_id,
            "intent_sequence": intent.sequence,
        },
    )


def _settle_tool_interrupted(
    synth: _Synthesizer,
    *,
    harness: ResearchHarness,
    intent: EpisodeEvent,
    detail: str,
) -> None:
    tool = str(intent.payload.get("name") or "")
    call_id = str(intent.payload.get("call_id") or "")
    payload = harness.project_tool_error(tool=tool, error=INTERRUPTED, detail=detail)
    synth.add(
        "tool_error",
        {
            **payload,
            "call_id": call_id,
            # INV-R1：合成结算也是模型可见内容的载体，派生器要能从它重建 tool 消息。
            "model_content": json.dumps(payload, ensure_ascii=False),
            "intent_sequence": intent.sequence,
        },
    )


def _synthesize_finish(
    synth: _Synthesizer,
    *,
    stop_reason: str,
    gaps: Sequence[str],
    extra: Mapping[str, object] | None = None,
) -> EpisodeEvent:
    status = "partial" if any(e.kind == "tool_result" for e in synth.events) else "failed"
    return synth.add(
        "finish",
        {
            "status": status,
            "stop_reason": stop_reason,
            "gaps": list(gaps),
            "carried_draft_chars": 0,
            "caveat_slips": 0,
            "rejection_code": "none",
            "rejection_reason": "",
            "time_budget_injected": False,
            **dict(extra or {}),
        },
    )


def _terminal_outcome(
    events: Sequence[EpisodeEvent], *, task_frame_hash: str, finish: EpisodeEvent
) -> AgentOutcome:
    llm_calls = sum(1 for e in events if e.kind == "model_turn")
    tool_calls = sum(1 for e in events if e.kind in {"tool_result", "tool_error"})
    return AgentOutcome(
        task_frame_hash=task_frame_hash,
        status=str(finish.payload.get("status") or "failed"),  # type: ignore[arg-type]
        draft="",
        evidence=(),
        traces=(),
        gaps=tuple(str(item) for item in (finish.payload.get("gaps") or ())),
        stop_reason=str(finish.payload.get("stop_reason") or INTERRUPTED),
        events=tuple(events),
        bindings=(),
        usage=AgentUsage(llm_calls=llm_calls, tool_calls=tool_calls, invalid_actions=0),
        plan=None,
        persistence="durable",
    )


# ── 主入口 ───────────────────────────────────────────────────────────────────


def restore_episode(
    episode_id: str,
    store: EpisodeStore,
    *,
    registry: ResearchToolRegistry | None = None,
    harness: ResearchHarness | None = None,
    now: datetime | None = None,
    context: ResearchRunContext | None = None,
) -> RestoreResult:
    """读状态 → 点查 → switch。返回下一动作（``plan``）或已闭合的终局（``outcome``）。

    非终态必须有完整授权快照及调用方重新提供的 ``context`` / ``registry``，精确匹配后
    才能合成日志/给计划；旧日志可 load 诊断，但不猜权限给恢复计划。确认完成态只读返回。
    同一道门还要问「谁的」：``context.entry_identity`` 必须与检查点记下的入口身份逐字节相等，
    两边都未绑定也算一致；一边有一边无是不匹配，没有任何一边可以替对方补上。
    读前取得本机独占写者，活驱动存在时拒绝；返回时释放，plan 不是后续执行许可。
    ``now`` 可注入，Tier A 套件用它把「截止已过 / 未过」两格都跑到。
    """

    with episode_writer(store, episode_id):
        return _restore_owned(
            episode_id, store, registry=registry, harness=harness, now=now, context=context,
        )


def _restore_owned(
    episode_id: str,
    store: EpisodeStore,
    *,
    registry: ResearchToolRegistry | None,
    harness: ResearchHarness | None,
    now: datetime | None,
    context: ResearchRunContext | None,
) -> RestoreResult:
    domain = harness if harness is not None else FinanceResearchHarness()
    moment = now if now is not None else datetime.now().astimezone()
    loaded_events, state = store.load(episode_id)
    if state is None:
        raise RestoreUnavailable(f"{episode_id}: 没有 EpisodeState，拒绝从事件流推断位置")
    if state.episode_id != episode_id:
        raise RestoreUnavailable(f"{episode_id}: checkpoint episode identity mismatch")
    if state.log_version != EPISODE_LOG_VERSION:
        raise RestoreUnavailable(
            f"{episode_id}: 日志版本 {state.log_version} != 读者 {EPISODE_LOG_VERSION}"
        )
    require_known_kinds(loaded_events)
    if state.last_sequence > len(loaded_events):
        raise RestoreUnavailable(
            f"{episode_id}: 日志落后于状态（state.last_sequence={state.last_sequence} > "
            f"{len(loaded_events)} 条事件）"
        )
    events = list(loaded_events)
    task_frame_hash = _task_frame_hash(events)
    # 检查点带来的未对账凭证原样带走（恢复不是对账，没资格消它们），本次新发现的再并进去。
    current_unknown: UnreconciledEffects = unknown_effects_from_payload(
        list(state.unreconciled_effects)
    )
    pending_unknown: list[UnknownEffect] = []

    def result(
        disposition: RestoreDisposition,
        *,
        synth: _Synthesizer | None,
        plan: ResumePlan | None,
        outcome: AgentOutcome | None,
        state_after: EpisodeState,
    ) -> RestoreResult:
        return RestoreResult(
            episode_id=episode_id,
            disposition=disposition,
            state_before=state,
            state_after=state_after,
            events=tuple(events),
            synthesized=tuple(synth.synthesized) if synth is not None else (),
            plan=plan,
            outcome=outcome,
            pending_inbox=pending_inbox_messages(loaded_events),
            entry_identity_bound=state.entry_identity is not None,
            unreconciled_effects=current_unknown,
        )

    latest_finish = next((e for e in reversed(events) if e.kind == "finish"), None)
    terminal_owned = bool(state.terminal and latest_finish is not None and latest_finish.payload.get("owned_answer") is not None)
    if state.terminal:
        # A visible finish alone does not prove the done checkpoint was ACKed.
        # Nor may an old done checkpoint hide a later repair or failure suffix.
        if (
            latest_finish is None
            or latest_finish.sequence != state.last_sequence
            or state.last_sequence != len(events)
        ):
            raise RestoreUnavailable(f"{episode_id}: terminal checkpoint does not match the finish prefix")
        if not terminal_owned:
            return result("already_terminal", synth=None, plan=None, outcome=None, state_after=state)
    if latest_finish is not None and not state.terminal:
        repair_checkpointed = any(
            e.kind == "repair_reentry"
            and latest_finish.sequence < e.sequence <= state.last_sequence
            for e in events
        )
        if not repair_checkpointed:
            raise RestoreUnavailable(f"{episode_id}: finish has no confirmed completion or repair checkpoint")
        # Same-process repair can legally continue after a prior finish. Its
        # newer checkpoint, not a historical finish, owns the recovery position.

    # P1a stores linked episodes, but no driver yet restores their shared budget,
    # branch delivery/ownership and in-flight effects together. Refuse BEFORE
    # synthesizing events; a standalone retry would mint a second child tree.
    if state.contract_snapshot.get("branch_parent") or any(
        event.kind == "branch_started" for event in events
    ):
        raise RestoreUnavailable(f"{episode_id}: linked episode recovery requires child reconciliation")

    # Saved authority is not a grant. The owning entry point must reauthorize;
    # validate BEFORE any synthetic event/checkpoint, including expired closure.
    # Absence cannot distinguish legacy data from a damaged new checkpoint.
    # Both stay loadable for diagnosis, but neither may bypass this gate.
    if state.authorization_snapshot is None or context is None or registry is None:
        raise RestoreUnavailable(f"{episode_id}: recovery authorization requires snapshot, current context and registry")
    if context.contract.task_id != episode_id or (
        context.contract.task_frame_hash and context.contract.task_frame_hash != task_frame_hash
    ):
        raise RestoreUnavailable(f"{episode_id}: recovery authorization task identity mismatch")
    try:
        validate_current_authorization(state.authorization_snapshot, context=context, registry=registry)
    except (TypeError, ValueError) as exc:
        raise RestoreUnavailable(f"{episode_id}: recovery authorization mismatch") from exc

    # Same contract, same tools, different owner is still someone else's episode.
    # The entry point must re-present the identity the interrupted run recorded;
    # an unbound checkpoint and a bound door are a mismatch in BOTH directions,
    # because neither absence nor presence may be filled in on the other's behalf.
    if not entry_identities_match(state.entry_identity, capture_entry_identity(context)):
        raise RestoreUnavailable(f"{episode_id}: recovery entry identity does not match the recorded owner")
    if state.entry_identity is not None:
        try:
            validate_current_entry_identity(state.entry_identity, context=context)
        except (TypeError, ValueError) as exc:
            raise RestoreUnavailable(f"{episode_id}: recovery entry identity mismatch") from exc

    # A public tool_result is lossy (no private locator/structured values), so
    # absent evidence cannot be reconstructed from it or treated as empty.
    if state.evidence_snapshot is None:
        raise RestoreUnavailable(f"{episode_id}: recovery evidence snapshot is required")
    if state.evidence_snapshot["information_cutoff"] != context.information_cutoff.as_of_date.isoformat():
        raise RestoreUnavailable(f"{episode_id}: recovery evidence cutoff mismatch")

    from intelligence.services.owned_results import (
        _catalogue_from_context, _rebuild_owned_sources, _verify_owned_answer, render_owned_parts,
    )

    try:
        _rebuild_owned_sources(events, context=context)
        if latest_finish is not None and latest_finish.payload.get("owned_answer") is not None:
            receipt = latest_finish.to_dict()["payload"]["owned_answer"]
            restored = render_owned_parts(receipt["parts"], _catalogue_from_context(context))
            _verify_owned_answer(receipt, restored.draft, context=context)
    except (TypeError, ValueError, KeyError) as exc:
        raise RestoreUnavailable(f"{episode_id}: owned result source/ref/receipt unavailable: {exc}") from exc
    if terminal_owned:
        return result("already_terminal", synth=None, plan=None, outcome=None, state_after=state)

    synth = _Synthesizer(
        episode_id=episode_id,
        store=store,
        events=events,
        task_frame_hash=task_frame_hash,
        phase=state.phase,
    )
    deadline_passed = _deadline_passed(state, moment)
    cancel = dict(state.cancel) if state.cancel and state.cancel.get("requested") else None

    def flush_unknown_effects() -> None:
        """把本次发现的未知窗口并进清单，新增才落一条 ``effects_unknown``。

        并集必须幂等：``retry_model`` / ``replay_tools`` 这类计划不合成任何结算，下一次
        恢复照样看得见那条悬空意图；若每次都追一条，清单会随重启次数无限膨胀，
        将来对账时就会按重启次数重复扣费——那是把一个少记账的 bug 换成一个多记账的 bug。
        """

        nonlocal current_unknown
        if not pending_unknown:
            return
        merged = merge_unknown_effects(current_unknown, pending_unknown)
        pending_unknown.clear()
        if len(merged) == len(current_unknown):
            return  # 都是旧窗口：不重复登记
        added = tuple(item for item in merged if item.key not in {e.key for e in current_unknown})
        current_unknown = merged
        synth.add(
            "effects_unknown",
            {
                "effects": unknown_effects_payload(added),
                "outstanding": len(merged),
                "possibly_billed": sum(1 for item in merged if item.may_have_been_billed),
                "budget_snapshot_sequence": state.budget_snapshot_sequence,
            },
        )

    def close(stop_reason: str, gaps: Sequence[str], extra: Mapping[str, object] | None = None) -> RestoreResult:
        # finish 必须是最后一条（terminal 校验要求 latest_finish.sequence == last_sequence），
        # 所以未知效果登记先落。关闭不等于对账：烧掉的钱不会因为 episode 结束而回来。
        flush_unknown_effects()
        finish = _synthesize_finish(synth, stop_reason=stop_reason, gaps=gaps, extra=extra)
        done = EpisodeState(
            episode_id=episode_id,
            phase="done",
            turn_index=state.turn_index,
            reserved_ids=(),
            consumed_seconds=state.consumed_seconds,
            deadline_at=state.deadline_at,
            retry={},
            contract_snapshot=state.contract_snapshot,
            cancel=cancel,
            last_sequence=len(events),
            updated_at=now_iso(),
            budget_snapshot=state.budget_snapshot,
            budget_snapshot_sequence=state.budget_snapshot_sequence,
            authorization_snapshot=state.authorization_snapshot,
            evidence_snapshot=state.evidence_snapshot,
            evidence_snapshot_sequence=state.evidence_snapshot_sequence,
            # Recovery must not unbind the episode: a checkpoint that forgot its
            # owner would be recoverable by any doorless caller next time.
            entry_identity=state.entry_identity,
            unreconciled_effects=tuple(unknown_effects_payload(current_unknown)),
        )
        store.put_state(episode_id, done)
        outcome = _terminal_outcome(events, task_frame_hash=task_frame_hash, finish=finish)
        return result("closed", synth=synth, plan=None, outcome=outcome, state_after=done)

    def resumable(plan: ResumePlan) -> RestoreResult:
        # 登记要先于返回计划：``retry_model`` / ``replay_tools`` 正是在提议“再付一次钱”，
        # 它们跟合成 interrupted 结算共享同一段未知窗口，没有理由只给后者留凭证。
        flush_unknown_effects()
        state_after = state
        if synth.synthesized:
            # A plan has not executed. Keep the original program counter and
            # lookup IDs until the driver records a new intent/checkpoint;
            # otherwise a second restore silently skips the proposed work.
            state_after = EpisodeState(
                episode_id=episode_id,
                phase=state.phase,
                turn_index=state.turn_index,
                reserved_ids=state.reserved_ids,
                consumed_seconds=state.consumed_seconds,
                deadline_at=state.deadline_at,
                retry=dict(state.retry),
                contract_snapshot=state.contract_snapshot,
                cancel=cancel,
                last_sequence=len(events),
                updated_at=now_iso(),
                budget_snapshot=state.budget_snapshot,
                budget_snapshot_sequence=state.budget_snapshot_sequence,
                authorization_snapshot=state.authorization_snapshot,
                evidence_snapshot=state.evidence_snapshot,
                evidence_snapshot_sequence=state.evidence_snapshot_sequence,
                entry_identity=state.entry_identity,
                unreconciled_effects=tuple(unknown_effects_payload(current_unknown)),
            )
            store.put_state(episode_id, state_after)
        return result("resumable", synth=synth, plan=plan, outcome=None, state_after=state_after)

    interrupted_gap = (
        f"运行在 {state.phase} 阶段被中断（进程重启）；中断前已 durable 的工具结果 "
        f"{sum(1 for e in events if e.kind == 'tool_result')} 条，未合成答案"
    )
    continue_phase: EpisodePhase = "finalizing" if state.phase == "finalizing" else (
        "repair" if state.phase == "repair" else "planning"
    )

    # ── 悬空意图结算（三行里的前两行；取消那行先结算再关）────────────────────
    pending_calls: list[str] = []
    settled_turn: EpisodeEvent | None = None
    settled_turn_error = False

    if state.phase in {"model_pending", "repair"} and state.reserved_ids:
        turn_id = state.reserved_ids[0]
        intent = _find(events, kinds=frozenset({"model_intent"}), key="turn_id", value=turn_id)
        if intent is None:
            raise RestoreUnavailable(f"{episode_id}: 状态预留了 {turn_id} 但日志里没有该意图")
        settlement = _find(
            events,
            kinds=frozenset({"model_turn", "model_error"}),
            key="turn_id",
            value=turn_id,
            after=intent.sequence,
        )
        intent_phase = str(intent.payload.get("phase") or continue_phase)
        if intent_phase in {"planning", "finalizing", "repair"}:
            continue_phase = intent_phase  # type: ignore[assignment]
        if settlement is None:
            remaining = int(state.retry.get("remaining") or 0)
            retrying = cancel is None and remaining > 0 and not deadline_passed
            # 意图已落、结算未落：这次请求可能已经出门、已经被按 token 计了费。合成
            # ``model_error{interrupted}`` 只说明「没有结果可用」，它答不了「是否已计费」；
            # ``retry_model`` 更是在提议再付一次。两条路共享同一段未知窗口，都要登记。
            pending_unknown.append(
                UnknownEffect(
                    effect="model",
                    reserved_id=turn_id,
                    intent_sequence=intent.sequence,
                    disposition="retry_proposed" if retrying else "settled_interrupted",
                    cost="external",
                    io_effect="external_or_mixed",
                )
            )
            if retrying:
                return resumable(
                    ResumePlan(
                        action="retry_model",
                        phase=continue_phase,
                        reason=f"model_intent {turn_id} 无结算；捕获的重试余量 {remaining}，截止未过",
                        turn_id=turn_id,
                    ),
                )
            _settle_model_interrupted(synth, intent=intent, turn_id=turn_id)
            if cancel is None:
                settled_turn_error = True
        elif settlement.kind == "model_error" or str(settlement.payload.get("error") or ""):
            settled_turn_error = True
        else:
            settled_turn = settlement
            raw_calls = settlement.payload.get("tool_calls") or ()
            pending_calls = [
                str(item.get("call_id") or "")
                for item in raw_calls  # type: ignore[union-attr]
                if isinstance(item, Mapping)
            ]

    dangling_tool_intents: list[EpisodeEvent] = []
    reserved_calls: tuple[str, ...] = ()
    if state.phase == "tools_pending" and state.reserved_ids:
        reserved_calls = state.reserved_ids
    elif pending_calls:
        # 模型结算已落、工具意图可能落了一部分：只有已落意图的才算在飞。
        reserved_calls = tuple(
            call_id
            for call_id in pending_calls
            if _find(events, kinds=frozenset({"tool_request"}), key="call_id", value=call_id)
            is not None
        )
    for call_id in reserved_calls:
        intent = _find(events, kinds=frozenset({"tool_request"}), key="call_id", value=call_id)
        if intent is None:
            raise RestoreUnavailable(f"{episode_id}: 状态预留了 {call_id} 但日志里没有该意图")
        settlement = _find(
            events,
            kinds=frozenset({"tool_result", "tool_error"}),
            key="call_id",
            value=call_id,
            after=intent.sequence,
        )
        if settlement is None:
            dangling_tool_intents.append(intent)

    replayable: list[str] = []
    for intent in dangling_tool_intents:
        call_id = str(intent.payload.get("call_id") or "")
        name = str(intent.payload.get("name") or "")
        declared_safe = str(intent.payload.get("replay") or "never") == "safe"
        spec = None
        if registry is not None:
            try:
                spec = registry.resolve(name)
            except UnknownResearchTool:
                spec = None
        current_safe = True if registry is None else (spec is not None and spec.replay == "safe")
        replaying = cancel is None and declared_safe and current_safe and not deadline_passed
        # ``replay=safe`` 是关于**效果幂等**的声明，不是关于**费用**的声明：注册表默认
        # 就是 ``cost="external"`` + ``replay="safe"``。所以重跑前后都要把这段窗口记下来。
        pending_unknown.append(
            UnknownEffect(
                effect="tool",
                reserved_id=call_id,
                intent_sequence=intent.sequence,
                disposition="replay_proposed" if replaying else "settled_interrupted",
                name=name,
                cost=_declared(getattr(spec, "cost", None), {"local", "external"}),
                io_effect=_declared(
                    getattr(spec, "io_effect", None), {"local_read", "external_or_mixed"}
                ),
                replay=_declared(intent.payload.get("replay"), {"safe", "never"}),
            )
        )
        if replaying:
            replayable.append(call_id)
            continue
        if cancel is not None:
            detail = "episode cancelled before the tool settled"
        elif not declared_safe:
            detail = "intent declared replay=never"
        elif not current_safe:
            detail = f"{name} is no longer declared replay=safe"
        else:
            detail = "research deadline passed before the tool settled"
        _settle_tool_interrupted(synth, harness=domain, intent=intent, detail=detail)

    # ── 应用声明了调用、意图没落（application_tool_call 后、tool_request 前崩溃）────
    # 声明已进模型历史（派生成 assistant.tool_calls）；没有结算它的 tool 消息，下一次请求
    # 就是悬空 tool_calls，同样非法。不重发：声明不是意图，重发要走正常的空池回退判定，而
    # ``fallback_already_attempted`` 把这条声明算作已尝试。合成 tool_error{interrupted} 配平，
    # 派生器从它重建 tool 消息（INV-R1 在合成后的日志上仍成立）。
    dispatched_ids = {
        str(e.payload.get("call_id") or "") for e in events if e.kind == "tool_request"
    }
    for declaration in [e for e in events if e.kind == "application_tool_call"]:
        call_id = str(declaration.payload.get("call_id") or "")
        if call_id in dispatched_ids or _find(
            events,
            kinds=frozenset({"tool_result", "tool_error"}),
            key="call_id",
            value=call_id,
            after=declaration.sequence,
        ) is not None:
            continue
        _settle_tool_interrupted(
            synth,
            harness=domain,
            intent=declaration,
            detail="application tool call was declared but never dispatched",
        )

    # ── 兜底合成在飞 ───────────────────────────────────────────────────────
    recovery_dangling = False
    if _RECOVERY_RESERVED_ID in state.reserved_ids:
        started = [e for e in events if e.kind == "finalization_recovery_started"]
        last_started = started[-1] if started else None
        if last_started is None:
            raise RestoreUnavailable(f"{episode_id}: 状态预留了兜底合成但日志里没有其意图")
        outcome_after = next(
            (
                e
                for e in events
                if e.kind == "finalization_recovery_outcome" and e.sequence > last_started.sequence
            ),
            None,
        )
        if outcome_after is None:
            # 兜底合成也是一次模型调用：意图（``finalization_recovery_started``）已落、
            # 结算未落，同样可能已计费。它随后走 close()，但关闭不等于对账。
            pending_unknown.append(
                UnknownEffect(
                    effect="model",
                    reserved_id=_RECOVERY_RESERVED_ID,
                    intent_sequence=last_started.sequence,
                    disposition="settled_interrupted",
                    cost="external",
                    io_effect="external_or_mixed",
                )
            )
            synth.add(
                "finalization_recovery_outcome",
                {"status": "failed", "reason": INTERRUPTED, "intent_sequence": last_started.sequence},
            )
        recovery_dangling = True

    # ── 第三行：取消已 durable ─────────────────────────────────────────────
    if cancel is not None:
        return close(
            "cancelled",
            ["本轮执行已取消"],
            extra={"cancel_cause": cancel.get("cause"), "cancel_detail": cancel.get("detail")},
        )

    # ── 兜底合成路径永远终局 ───────────────────────────────────────────────
    if recovery_dangling:
        return close(INTERRUPTED, [interrupted_gap])

    # ── 下一动作 ───────────────────────────────────────────────────────────
    if replayable:
        return resumable(
            ResumePlan(
                action="replay_tools",
                phase=continue_phase,
                reason="工具意图无结算且 replay=safe（意图与当前声明一致），截止未过",
                call_ids=tuple(replayable),
            ),
        )
    if deadline_passed:
        return close(INTERRUPTED, [interrupted_gap])
    if settled_turn_error:
        return resumable(
            ResumePlan(
                action="finalize",
                phase="finalizing",
                reason="模型请求以错误结算（含合成 interrupted），截止未过：进收口",
            ),
        )
    if settled_turn is not None:
        if pending_calls:
            missing = tuple(call_id for call_id in pending_calls if call_id not in reserved_calls)
            if missing:
                return resumable(
                    ResumePlan(
                        action="dispatch_tools",
                        phase=continue_phase,
                        reason="模型已点工具，意图尚未落账：派发",
                        turn_id=str(settled_turn.payload.get("turn_id") or ""),
                        call_ids=missing,
                    ),
                )
            return resumable(
                ResumePlan(
                    action="model_turn",
                    phase=continue_phase,
                    reason="这一批工具全部结算，回到模型",
                ),
            )
        return resumable(
            ResumePlan(
                action="interpret_turn",
                phase=continue_phase,
                reason="模型已回非工具轮，下一步是解释它（PLAN / FINAL_JSON 准入）",
                turn_id=str(settled_turn.payload.get("turn_id") or ""),
            ),
        )
    return resumable(
        ResumePlan(
            action="model_turn",
            phase=continue_phase,
            reason=(
                "无在飞外部效果" if not state.reserved_ids else "在飞工具已全部结算"
            ),
        ),
    )

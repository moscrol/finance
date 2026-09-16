"""管理动作：``validate_action`` / ``reduce_actions``（spec 01 §5）。本包没有 writer。

- ``validate_action`` 只回答「这条命令能不能落」并给出拟追加事件；06 验权后单 writer 原子比较 / 保存。
- ``reduce_actions`` 把已落盘的事件按台账顺序折到报告上：重复 command_id 同载荷 = replayed（不重做），
  换载荷 = conflict；旧 item_version / 旧 revision / 旧源版本 = conflict；终态、非法迁移、跨 owner = rejected。
  两条事件基于同一 expected_management_revision 竞争时，只有先到的那条生效。
- 新更正产生的是新项（新 id），旧项的 snooze / claim 不继承：事件指向不在报告里的项只记 ``absent_item``。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from intelligence.services.judgment_maintenance.contracts import (
    COMMAND_EVENT_KIND,
    EVENT_ID_PREFIX,
    ActionCommand,
    ActionResult,
    MaintenanceContractError,
    MaintenanceItem,
    MaintenanceReport,
    ManagementEvent,
    instant_of,
    parse_command,
    parse_event,
    parse_item,
    parse_report,
    short_hash,
    validate_owner,
    validate_stamp,
)

_COMMAND_TRANSITIONS: dict[tuple[str, str], str] = {
    ("open", "claimed"): "claimed",
    ("open", "snoozed"): "snoozed",
    ("claimed", "snoozed"): "snoozed",
    ("open", "rejudgment_requested"): "rejudgment_requested",
    ("claimed", "rejudgment_requested"): "rejudgment_requested",
    ("open", "reviewed_no_change"): "closed",
    ("claimed", "reviewed_no_change"): "closed",
}
_SYSTEM_TRANSITIONS: dict[tuple[str, str], str] = {
    ("rejudgment_requested", "rejudgment_linked"): "closed",
    ("rejudgment_requested", "rejudgment_failed"): "open",
    ("rejudgment_requested", "rejudgment_cancelled"): "open",
}
_TERMINAL = ("closed", "superseded")


@dataclass(frozen=True)
class Outcome:
    event_id: str
    item_id: str
    outcome: str  # applied | replayed | conflict | rejected | absent_item
    reason_code: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "item_id": self.item_id, "outcome": self.outcome, "reason_code": self.reason_code, "detail": self.detail}


def _deadline_reached(deadline: str | None, reference: str) -> bool:
    """``deadline`` 是否已被 ``reference`` 这一刻越过——按绝对时刻比，不按 ISO 字符串比。

    ``10:00+08:00`` 的字典序大于 ``03:00Z``，实际却早 5 小时；两种写法必须给同一个答案。
    任一侧说不出绝对时刻（纯日期、无偏移的 naive 时刻）就返回 False：证不出「已到期」时不解除，
    未知不能变成「已经解除」（总合同 §5 第 5 条）。
    """
    end, ref = instant_of(deadline), instant_of(reference)
    if end is None or ref is None:
        return False
    return end <= ref


def _is_future(stamp: str | None, reference: str) -> bool:
    """``stamp`` 是否确实晚于 ``reference``；说不出绝对时刻的一律 False（不替用户猜时分秒或时区）。"""
    later, ref = instant_of(stamp), instant_of(reference)
    if later is None or ref is None:
        return False
    return later > ref


def wake_if_expired(item: MaintenanceItem, now: str) -> MaintenanceItem:
    """snooze 到期 → 同 id 恢复为 open；这是时间推导出的状态，不算管理动作，不动 revision。"""
    if item.status == "snoozed" and _deadline_reached(item.management.snooze_until, now):
        return replace(item, status="open", management=replace(item.management, snooze_until=None))
    return item


def event_from_command(command: ActionCommand) -> ManagementEvent:
    kind = COMMAND_EVENT_KIND[command.action]
    digest = command.payload_digest()
    payload: dict[str, Any] = {"expected_item_version": command.expected_item_version}
    if command.snooze_until is not None:
        payload["snooze_until"] = command.snooze_until
    if command.reviewed_source_versions is not None:
        payload["reviewed_source_versions"] = [list(x) for x in command.reviewed_source_versions]
    event_id = EVENT_ID_PREFIX + short_hash(
        {"command_id": command.command_id, "item_id": command.item_id, "owner_user_id": command.owner_user_id, "kind": kind, "payload_digest": digest}
    )
    return ManagementEvent(
        event_id=event_id,
        item_id=command.item_id,
        owner_user_id=command.owner_user_id,
        kind=kind,
        at=command.acted_at,
        expected_management_revision=command.expected_management_revision,
        command_id=command.command_id,
        payload_digest=digest,
        payload=payload,
    )


def apply_event(item: MaintenanceItem, event: ManagementEvent, now: str) -> tuple[MaintenanceItem, Outcome]:
    """把一条事件落到一个项上：返回 (新项, 结局)。任何不接受的情形都原样返回旧项。"""

    def keep(outcome: str, code: str, detail: str = "") -> tuple[MaintenanceItem, Outcome]:
        return item, Outcome(event.event_id, event.item_id, outcome, code, detail)

    if event.owner_user_id != item.owner_user_id or event.item_id != item.id:
        # 不区分「不存在」与「不是你的」。
        return keep("rejected", "forbidden", "事件与维护项归属或身份不一致")
    item = wake_if_expired(item, now)
    if event.command_id:
        prior = next((c for c in item.management.applied_commands if c.get("command_id") == event.command_id), None)
        if prior is not None:
            if prior.get("payload_digest") == event.payload_digest:
                return keep("replayed", "duplicate_command", "同 command_id 同载荷：返回原结果，不重做")
            return keep("conflict", "command_payload_mismatch", "同 command_id 不同载荷：不能复用幂等键")
    if item.status in _TERMINAL:
        return keep("rejected", "terminal_state", f"维护项已是终态 {item.status}")
    if event.expected_management_revision != item.management_revision:
        return keep("conflict", "stale_revision", f"期望 revision {event.expected_management_revision}，当前 {item.management_revision}")
    expected_version = event.payload.get("expected_item_version")
    if expected_version is not None and expected_version != item.item_version:
        return keep("conflict", "stale_item_version", "维护项的证据快照已变化，请重新查看前后版本")
    target = _COMMAND_TRANSITIONS.get((item.status, event.kind)) or _SYSTEM_TRANSITIONS.get((item.status, event.kind))
    if target is None:
        return keep("rejected", "invalid_transition", f"{item.status} 状态下不能执行 {event.kind}")

    management = item.management
    new_revision = item.management_revision + 1
    if event.kind == "snoozed":
        # 只比动作时刻：事件是过去某一刻被接受的，重放台账时「现在」早已越过 snooze_until 也不能改判它；
        # 到期恢复由 wake_if_expired 按当前时刻推导。「现在就已过期」的拦截在 validate_action。
        until = event.payload.get("snooze_until")
        if not isinstance(until, str) or not until or _deadline_reached(until, event.at) or instant_of(until) is None:
            return keep("rejected", "invalid_snooze_until", "snooze_until 必须是晚于动作时刻的明确时刻（带时区）")
        management = replace(management, snooze_until=until)
    elif event.kind == "claimed":
        management = replace(management, claimed_at=event.at)
    elif event.kind == "rejudgment_requested":
        previous = dict(management.rejudgment or {})
        management = replace(
            management,
            rejudgment={"request_event_id": event.event_id, "requested_at": event.at, "attempts": int(previous.get("attempts") or 0) + 1, "last_failure": previous.get("last_failure")},
        )
    elif event.kind == "reviewed_no_change":
        if not item.current:
            return keep("rejected", "nothing_to_review", "当前依据不可解析时不能「核对后判断未变」")
        reviewed_raw = event.payload.get("reviewed_source_versions")
        if not isinstance(reviewed_raw, list):
            return keep("rejected", "invalid_command", "reviewed_no_change 必须带已核对的 source versions")
        reviewed = {(str(pair[0]), str(pair[1])) for pair in reviewed_raw if isinstance(pair, (list, tuple)) and len(pair) == 2}
        current = {(v.ref, v.source_hash or "") for v in item.current}
        if reviewed != current:
            return keep("conflict", "stale_source_versions", "核对的源版本与当前版本不一致：页面已过期")
        management = replace(
            management,
            closed_at=event.at,
            closure={
                "kind": "reviewed_no_change",
                "before_hashes": [[v.ref, v.source_hash] for v in item.before],
                "current_hashes": [[v.ref, v.source_hash] for v in item.current],
                "event_id": event.event_id,
                "at": event.at,
            },
        )
    elif event.kind == "rejudgment_linked":
        linked_ref = event.payload.get("new_judgment_ref")
        linked_owner = event.payload.get("owner_user_id")
        if not isinstance(linked_ref, str) or not linked_ref.strip() or linked_owner != item.owner_user_id:
            return keep("rejected", "invalid_link", "新判断必须带引用且属于同一 owner")
        management = replace(
            management,
            closed_at=event.at,
            closure={"kind": "rejudged", "linked_judgment_ref": linked_ref.strip(), "event_id": event.event_id, "at": event.at},
        )
    elif event.kind in ("rejudgment_failed", "rejudgment_cancelled"):
        previous = dict(management.rejudgment or {})
        previous["last_failure"] = {"event_id": event.event_id, "at": event.at, "kind": event.kind, "reason": str(event.payload.get("reason") or "")}
        management = replace(management, rejudgment=previous)

    if event.command_id:
        management = replace(
            management,
            applied_commands=management.applied_commands
            + ({"command_id": event.command_id, "payload_digest": event.payload_digest, "event_id": event.event_id, "management_revision": new_revision},),
        )
    new_item = replace(item, status=target, management_revision=new_revision, management=management)
    return new_item, Outcome(event.event_id, event.item_id, "applied", "ok", f"{item.status} → {target}")


_OUTCOME_TO_STATUS = {"applied": "accepted", "replayed": "replayed", "conflict": "conflict", "rejected": "rejected"}


def validate_action(*, item: Any, command: Any, owner_user_id: str, now: str) -> ActionResult:
    """校验一条用户命令能否落到维护项上；不写入，只返回结论与拟追加事件。"""
    owner = validate_owner(owner_user_id, "owner_user_id")
    now_stamp = validate_stamp(now, "now")
    try:
        cmd = parse_command(command, owner_user_id=owner)
    except MaintenanceContractError as exc:
        return ActionResult("rejected", "invalid_command", None, None, None, None, None, detail=str(exc))
    if cmd.owner_user_id != owner:
        return ActionResult("rejected", "forbidden", None, cmd.command_id, None, None, None, detail="命令归属与验证过的用户不一致")
    try:
        target = parse_item(item, owner_user_id=owner, where="item")
    except MaintenanceContractError as exc:
        code = "forbidden" if exc.code == "owner_mismatch" else "invalid_item"
        return ActionResult("rejected", code, None, cmd.command_id, None, None, None, detail="维护项不可用于本用户" if code == "forbidden" else str(exc))
    if cmd.item_id != target.id:
        return ActionResult("rejected", "forbidden", None, cmd.command_id, None, None, None, detail="命令指向的维护项与给定项不一致")
    event = event_from_command(cmd)
    # 幂等先于时钟：同 command_id 同载荷的重试必须返回原结果（spec 01 §5「重复同载荷同结果」）。
    # 先查 snooze_until 会让同一条已成功的命令在到期后重试变成 rejected——结果随时间改变，幂等键就废了。
    replaying = any(
        c.get("command_id") == cmd.command_id and c.get("payload_digest") == event.payload_digest
        for c in target.management.applied_commands
    )
    if not replaying and cmd.action == "snooze" and (cmd.snooze_until is None or not _is_future(cmd.snooze_until, now_stamp)):
        return ActionResult(
            "rejected",
            "invalid_snooze_until",
            target.id,
            cmd.command_id,
            None,
            None,
            None,
            detail="snooze_until 必须是晚于当前时刻的明确时刻（带时区；纯日期或无偏移的时刻说不出到期时点）",
        )
    new_item, outcome = apply_event(target, event, now_stamp)
    status = _OUTCOME_TO_STATUS[outcome.outcome]
    if outcome.outcome == "replayed":
        prior = next((c for c in target.management.applied_commands if c.get("command_id") == cmd.command_id), {})
        return ActionResult(
            status,
            outcome.reason_code,
            target.id,
            cmd.command_id,
            event,
            wake_if_expired(target, now_stamp).status,
            int(prior.get("management_revision") or target.management_revision),
            detail=outcome.detail,
        )
    if outcome.outcome != "applied":
        return ActionResult(status, outcome.reason_code, target.id, cmd.command_id, None, None, None, detail=outcome.detail)
    return ActionResult(status, outcome.reason_code, target.id, cmd.command_id, event, new_item.status, new_item.management_revision, detail=outcome.detail)


def reduce_actions(*, report: Any, events: Any, now: str) -> MaintenanceReport:
    """按台账顺序把管理事件折到报告上，返回带管理状态的新报告（原报告不变）。"""
    rep = parse_report(report)
    now_stamp = validate_stamp(now, "now")
    if events is None:
        events = []
    if not isinstance(events, (list, tuple)):
        raise MaintenanceContractError("invalid_type", "events", "需要列表")
    parsed = [parse_event(e, owner_user_id=rep.owner_user_id, where=f"events[{i}]") for i, e in enumerate(events)]
    by_id: dict[str, MaintenanceItem] = {it.id: it for it in rep.items}
    outcomes: list[Outcome] = []
    for ev in parsed:
        current = by_id.get(ev.item_id)
        if current is None:
            outcomes.append(Outcome(ev.event_id, ev.item_id, "absent_item", "item_not_in_report", "事件指向的维护项不在本报告中（已被替代或属于其它窗口），不继承其状态"))
            continue
        new_item, outcome = apply_event(current, ev, now_stamp)
        by_id[ev.item_id] = new_item
        outcomes.append(outcome)
    final_items = tuple(wake_if_expired(by_id[it.id], now_stamp) for it in rep.items)
    counts = dict(rep.counts)
    counts["items_open"] = sum(1 for it in final_items if it.is_open)
    tally = {key: sum(1 for o in outcomes if o.outcome == key) for key in ("applied", "replayed", "conflict", "rejected", "absent_item")}
    log = {"now": now_stamp, "events_seen": len(parsed), **tally, "outcomes": [o.to_dict() for o in outcomes]}
    return replace(rep, items=final_items, counts=counts, management_log=log)


__all__ = ["Outcome", "apply_event", "event_from_command", "reduce_actions", "validate_action", "wake_if_expired"]

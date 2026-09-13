"""判断持续维护 · 管理动作（spec 01 §5；§8 反向验收第 9、10 条 + actions 夹具回放）。

本包无 writer：validate_action 只给拟追加事件，reduce_actions 只按台账顺序折叠。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from intelligence.services import judgment_maintenance as jm
from intelligence.services.judgment_maintenance.contracts import EVENT_SCHEMA_VERSION

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "research_evolution" / "01"
OWNER = "alice"
REF_A = "fact_market_daily:2026-09-01"
NOW = "2026-09-13T12:00:00+08:00"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name / "input.json").read_text(encoding="utf-8"))


def _report(name: str = "complete") -> jm.MaintenanceReport:
    p = _load(name)
    return jm.assess(
        owner_user_id=p["owner_user_id"],
        as_of=p["as_of"],
        knowledge_cutoff=p["knowledge_cutoff"],
        bindings=p["bindings"],
        evidence_versions=p["evidence_versions"],
        condition_observations=p["condition_observations"],
        policy=p["policy"],
        generated_at=p["generated_at"],
    )


def _select(report: jm.MaintenanceReport, sel: dict) -> jm.MaintenanceItem:
    found = [it for it in report.items if all(getattr(it, k) == v for k, v in sel.items())]
    assert len(found) == 1, (sel, [(it.id, it.status, it.dependency_ref, it.condition_ref) for it in found])
    return found[0]


def _cmd(item: jm.MaintenanceItem, command_id: str, action: str, *, revision: int | None = None, acted_at="2026-09-13T09:00:00+08:00", **extra) -> dict:
    base = {
        "command_id": command_id,
        "item_id": item.id,
        "owner_user_id": item.owner_user_id,
        "expected_item_version": item.item_version,
        "expected_management_revision": item.management_revision if revision is None else revision,
        "action": action,
        "acted_at": acted_at,
    }
    base.update(extra)
    return base


def _system_event(item: jm.MaintenanceItem, event_id: str, kind: str, *, at: str, revision: int, payload: dict) -> dict:
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_id": event_id,
        "item_id": item.id,
        "owner_user_id": item.owner_user_id,
        "kind": kind,
        "at": at,
        "expected_management_revision": revision,
        "command_id": None,
        "payload_digest": None,
        "payload": payload,
    }


# --------------------------------------------------------------------------- #
# 夹具回放（冻结事件日志与结局，供 06 做合同测试）
# --------------------------------------------------------------------------- #
def _replay(report: jm.MaintenanceReport, script: dict):
    events: list[dict] = []
    steps: list[dict] = []
    current = report
    for step in script["steps"]:
        item = _select(current, step["select"])
        if step["kind"] == "command":
            cmd = dict(step["command"])
            cmd["item_id"] = item.id
            cmd["owner_user_id"] = current.owner_user_id
            if cmd.get("expected_item_version") == "current":
                cmd["expected_item_version"] = item.item_version
            if cmd.get("reviewed_source_versions") == "current":
                cmd["reviewed_source_versions"] = [{"ref": v.ref, "source_hash": v.source_hash} for v in item.current]
            step_now = step.get("now") or cmd["acted_at"]
            result = jm.validate_action(item=item, command=cmd, owner_user_id=current.owner_user_id, now=step_now)
            if result.status == "accepted":
                events.append(result.event.to_dict())
            steps.append(
                {
                    "id": step["id"],
                    "status": result.status,
                    "reason_code": result.reason_code,
                    "resulting_status": result.resulting_status,
                    "resulting_management_revision": result.resulting_management_revision,
                }
            )
        else:
            ev = dict(step["event"])
            ev.update({"schema_version": EVENT_SCHEMA_VERSION, "event_id": f"jme-sys-{step['id']}", "item_id": item.id, "owner_user_id": current.owner_user_id, "command_id": None, "payload_digest": None})
            events.append(ev)
            step_now = step.get("now") or ev["at"]
            steps.append({"id": step["id"], "status": "system_event"})
        current = jm.reduce_actions(report=report, events=events, now=step_now)
    final = jm.reduce_actions(report=report, events=events, now=script["now"])
    return final, events, steps


def test_fixture_actions_golden():
    script = _load("actions")
    assert script["synthetic"] is True
    report = _report(script["report_fixture"])
    final, events, steps = _replay(report, script)
    actual = {
        "synthetic": True,
        "events": events,
        "steps": steps,
        "final_items": [
            {"id": it.id, "status": it.status, "management_revision": it.management_revision, "closure": (it.management.closure or {}).get("kind")}
            for it in final.items
        ],
        "counts": final.counts,
        "management_log": final.management_log,
    }
    expected_path = FIXTURES / "actions" / "expected.json"
    if os.environ.get("JM_FIXTURES_UPDATE") == "1":
        expected_path.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert actual == expected


def test_fixture_actions_outcomes_are_the_spec_ones():
    script = _load("actions")
    final, events, steps = _replay(_report(), script)
    by_id = {s["id"]: s for s in steps}
    assert by_id["s01-claim"]["status"] == "accepted" and by_id["s01-claim"]["resulting_status"] == "claimed"
    assert by_id["s02-claim-replay"]["status"] == "replayed" and by_id["s02-claim-replay"]["resulting_management_revision"] == 1
    assert by_id["s03-same-id-other-payload"] == {"id": "s03-same-id-other-payload", "status": "conflict", "reason_code": "command_payload_mismatch", "resulting_status": None, "resulting_management_revision": None}
    assert by_id["s04-stale-revision"]["reason_code"] == "stale_revision"
    assert by_id["s05-review-stale-versions"]["reason_code"] == "stale_source_versions"
    assert by_id["s06-review-ok"]["resulting_status"] == "closed"
    assert by_id["s07-terminal"]["reason_code"] == "terminal_state"
    assert by_id["s08-rejudge"]["resulting_status"] == "rejudgment_requested"
    assert by_id["s10-rejudge-again"]["resulting_status"] == "rejudgment_requested"
    outcomes = {o["event_id"]: o for o in final.management_log["outcomes"]}
    assert outcomes["jme-sys-s09-rejudge-failed"]["outcome"] == "applied"
    assert outcomes["jme-sys-s11-link-foreign-owner"] ["outcome"] == "rejected" and outcomes["jme-sys-s11-link-foreign-owner"]["reason_code"] == "invalid_link"
    assert outcomes["jme-sys-s12-link-ok"]["outcome"] == "applied"
    cond_item = _select(final, {"condition_ref": "cond-stage-downgrade"})
    assert cond_item.status == "closed" and cond_item.management.closure["kind"] == "rejudged"
    assert cond_item.management.closure["linked_judgment_ref"] == "judgments.jsonl:j-new-1"
    assert cond_item.management.rejudgment["attempts"] == 2 and cond_item.management.rejudgment["last_failure"]["kind"] == "rejudgment_failed"
    reviewed = _select(final, {"dependency_ref": REF_A})
    assert reviewed.status == "closed" and reviewed.management.closure["current_hashes"] == [[REF_A, "h-a2"]] and reviewed.management.closure["before_hashes"] == [[REF_A, "h-a1"]]
    # snooze 到期：同 id、状态恢复 open、revision 不因唤醒而变
    snoozed = _select(final, {"dependency_ref": "fact_theme_fundamental_doc:d-9", "change_type": "source_corrected"})
    assert snoozed.status == "open" and snoozed.management.snooze_until is None and snoozed.management_revision == 1
    # 只剩两条可动的待办：被替代链的 live 项（唤醒后）与 condition_false 项不算（action=none）
    assert final.counts["items_open"] == 1
    assert len(events) == sum(1 for s in steps if s["status"] in ("accepted", "system_event"))


# --------------------------------------------------------------------------- #
# §8.9 snooze 到期恢复同项；新更正产生关联新项；重新判断失败保持未关闭
# --------------------------------------------------------------------------- #
def test_snooze_expires_back_to_same_open_item():
    report = _report()
    item = _select(report, {"dependency_ref": REF_A})
    result = jm.validate_action(item=item, command=_cmd(item, "c-snooze", "snooze", snooze_until="2026-09-14T09:00:00+08:00"), owner_user_id=OWNER, now="2026-09-13T09:00:01+08:00")
    assert result.status == "accepted" and result.resulting_status == "snoozed"
    before = jm.reduce_actions(report=report, events=[result.event.to_dict()], now="2026-09-13T20:00:00+08:00")
    assert before.item(item.id).status == "snoozed" and before.counts["items_open"] == report.counts["items_open"] - 1
    after = jm.reduce_actions(report=report, events=[result.event.to_dict()], now="2026-09-14T09:00:00+08:00")
    woke = after.item(item.id)
    assert woke is not None and woke.status == "open" and woke.management.snooze_until is None
    assert woke.management_revision == 1 and after.counts["items_open"] == report.counts["items_open"]
    # 到期前 snoozed 状态下不能 claim（只能等到期或由时间唤醒）
    denied = jm.validate_action(item=before.item(item.id), command=_cmd(before.item(item.id), "c-claim", "claim"), owner_user_id=OWNER, now="2026-09-13T21:00:00+08:00")
    assert denied.status == "rejected" and denied.reason_code == "invalid_transition"


def test_snooze_into_the_past_rejected_at_command_time_but_replays_fine():
    report = _report()
    item = _select(report, {"dependency_ref": REF_A})
    past = jm.validate_action(item=item, command=_cmd(item, "c-past", "snooze", snooze_until="2026-09-13T08:00:00+08:00"), owner_user_id=OWNER, now="2026-09-13T09:00:00+08:00")
    assert past.status == "rejected" and past.reason_code == "invalid_snooze_until"
    ok = jm.validate_action(item=item, command=_cmd(item, "c-ok", "snooze", snooze_until="2026-09-13T10:00:00+08:00"), owner_user_id=OWNER, now="2026-09-13T09:00:01+08:00")
    assert ok.status == "accepted"
    replayed_later = jm.reduce_actions(report=report, events=[ok.event.to_dict()], now="2026-09-20T00:00:00+08:00")
    assert replayed_later.management_log["applied"] == 1
    assert replayed_later.item(item.id).status == "open"


def test_new_correction_creates_linked_new_item_without_inheriting_snooze():
    report = _report()
    expired = next(it for it in report.items if it.change_type == "source_expired")
    corrected = next(it for it in report.items if it.change_type == "source_corrected")
    assert expired.status == "superseded" and corrected.supersedes_item_id == expired.id and corrected.status == "open"
    # 旧（被替代）项上的动作被拒绝，也不会串到新项
    stale = jm.validate_action(item=expired, command=_cmd(expired, "c-old", "snooze", snooze_until="2026-09-20T09:00:00+08:00"), owner_user_id=OWNER, now=NOW)
    assert stale.status == "rejected" and stale.reason_code == "terminal_state"
    ghost = _system_event(corrected, "jme-ghost", "rejudgment_failed", at=NOW, revision=0, payload={})
    ghost["item_id"] = "jmi-no-longer-in-report"
    reduced = jm.reduce_actions(report=report, events=[ghost], now=NOW)
    assert reduced.management_log["absent_item"] == 1
    assert reduced.item(corrected.id).status == "open" and reduced.item(corrected.id).management_revision == 0


def test_rejudge_failure_keeps_item_open_and_link_needs_same_owner():
    report = _report()
    item = _select(report, {"condition_ref": "cond-stage-downgrade"})
    req = jm.validate_action(item=item, command=_cmd(item, "c-rejudge", "rejudge"), owner_user_id=OWNER, now=NOW)
    assert req.status == "accepted" and req.resulting_status == "rejudgment_requested"
    events = [req.event.to_dict()]
    failed = _system_event(item, "jme-failed", "rejudgment_failed", at="2026-09-13T09:30:00+08:00", revision=1, payload={"reason": "run timed out"})
    after_fail = jm.reduce_actions(report=report, events=events + [failed], now=NOW)
    assert after_fail.item(item.id).status == "open"
    assert after_fail.item(item.id).management.rejudgment["last_failure"]["reason"] == "run timed out"
    assert after_fail.counts["items_open"] == report.counts["items_open"]
    # 关联到别人的判断：拒绝，状态不变
    again = jm.validate_action(item=after_fail.item(item.id), command=_cmd(after_fail.item(item.id), "c-rejudge-2", "rejudge"), owner_user_id=OWNER, now=NOW)
    events = events + [failed, again.event.to_dict()]
    foreign = _system_event(item, "jme-foreign", "rejudgment_linked", at=NOW, revision=3, payload={"new_judgment_ref": "judgments.jsonl:j-9", "owner_user_id": "bob"})
    reduced = jm.reduce_actions(report=report, events=events + [foreign], now=NOW)
    assert reduced.item(item.id).status == "rejudgment_requested"
    assert reduced.management_log["outcomes"][-1]["reason_code"] == "invalid_link"
    linked = _system_event(item, "jme-linked", "rejudgment_linked", at=NOW, revision=3, payload={"new_judgment_ref": "judgments.jsonl:j-9", "owner_user_id": OWNER})
    closed = jm.reduce_actions(report=report, events=events + [foreign, linked], now=NOW)
    assert closed.item(item.id).status == "closed" and closed.item(item.id).management.closure["linked_judgment_ref"] == "judgments.jsonl:j-9"


def test_reviewed_no_change_binds_receipt_to_before_and_current_hashes():
    report = _report()
    item = _select(report, {"dependency_ref": REF_A})
    stale = jm.validate_action(
        item=item,
        command=_cmd(item, "c-review-stale", "reviewed_no_change", reviewed_source_versions=[{"ref": REF_A, "source_hash": "h-a1"}]),
        owner_user_id=OWNER,
        now=NOW,
    )
    assert stale.status == "conflict" and stale.reason_code == "stale_source_versions"
    ok = jm.validate_action(
        item=item,
        command=_cmd(item, "c-review", "reviewed_no_change", reviewed_source_versions=[{"ref": REF_A, "source_hash": "h-a2"}]),
        owner_user_id=OWNER,
        now=NOW,
    )
    assert ok.status == "accepted" and ok.resulting_status == "closed"
    reduced = jm.reduce_actions(report=report, events=[ok.event.to_dict()], now=NOW)
    closed = reduced.item(item.id)
    assert closed.management.closure["before_hashes"] == [[REF_A, "h-a1"]] and closed.management.closure["current_hashes"] == [[REF_A, "h-a2"]]
    # 关闭不改变原判断有效性：报告里的 before / current 原样保留
    assert closed.before[0].source_hash == "h-a1" and closed.current[0].source_hash == "h-a2"
    missing = _select(jm.assess(**_missing_args()), {"dependency_ref": "fact_sector_daily:2026-09-01:半导体"})
    denied = jm.validate_action(
        item=missing,
        command=_cmd(missing, "c-review-missing", "reviewed_no_change", reviewed_source_versions=[]),
        owner_user_id=OWNER,
        now=NOW,
    )
    assert denied.status == "rejected" and denied.reason_code == "nothing_to_review"


def _missing_args() -> dict:
    p = _load("missing_source")
    return {
        "owner_user_id": p["owner_user_id"],
        "as_of": p["as_of"],
        "knowledge_cutoff": p["knowledge_cutoff"],
        "bindings": p["bindings"],
        "evidence_versions": p["evidence_versions"],
        "condition_observations": p["condition_observations"],
        "policy": p["policy"],
        "generated_at": p["generated_at"],
    }


# --------------------------------------------------------------------------- #
# §8.10 重复 command_id、并发相同 revision、异载荷重放：至多一份有效管理动作
# --------------------------------------------------------------------------- #
def test_duplicate_command_id_is_replayed_once():
    report = _report()
    item = _select(report, {"dependency_ref": REF_A})
    cmd = _cmd(item, "c-dup", "claim")
    first = jm.validate_action(item=item, command=cmd, owner_user_id=OWNER, now=NOW)
    assert first.status == "accepted"
    log = [first.event.to_dict()] * 3
    reduced = jm.reduce_actions(report=report, events=log, now=NOW)
    assert reduced.management_log["applied"] == 1 and reduced.management_log["replayed"] == 2
    assert reduced.item(item.id).management_revision == 1 and reduced.item(item.id).status == "claimed"
    replay = jm.validate_action(item=reduced.item(item.id), command=cmd, owner_user_id=OWNER, now=NOW)
    assert replay.status == "replayed" and replay.resulting_management_revision == 1 and replay.event.event_id == first.event.event_id


def test_concurrent_commands_on_same_revision_only_one_wins():
    report = _report()
    item = _select(report, {"dependency_ref": REF_A})
    a = jm.validate_action(item=item, command=_cmd(item, "c-a", "claim"), owner_user_id=OWNER, now=NOW)
    b = jm.validate_action(item=item, command=_cmd(item, "c-b", "snooze", snooze_until="2026-09-15T09:00:00+08:00"), owner_user_id=OWNER, now=NOW)
    assert a.status == b.status == "accepted"  # 各自单独看都合法：并发裁决在台账顺序里
    reduced = jm.reduce_actions(report=report, events=[a.event.to_dict(), b.event.to_dict()], now=NOW)
    assert reduced.management_log["applied"] == 1 and reduced.management_log["conflict"] == 1
    assert reduced.item(item.id).status == "claimed" and reduced.item(item.id).management_revision == 1
    reversed_log = jm.reduce_actions(report=report, events=[b.event.to_dict(), a.event.to_dict()], now=NOW)
    assert reversed_log.item(item.id).status == "snoozed" and reversed_log.management_log["conflict"] == 1


def test_same_command_id_with_different_payload_is_conflict():
    report = _report()
    item = _select(report, {"dependency_ref": REF_A})
    first = jm.validate_action(item=item, command=_cmd(item, "c-x", "claim"), owner_user_id=OWNER, now=NOW)
    reduced = jm.reduce_actions(report=report, events=[first.event.to_dict()], now=NOW)
    changed = _cmd(reduced.item(item.id), "c-x", "snooze", snooze_until="2026-09-15T09:00:00+08:00")
    result = jm.validate_action(item=reduced.item(item.id), command=changed, owner_user_id=OWNER, now=NOW)
    assert result.status == "conflict" and result.reason_code == "command_payload_mismatch"
    forged_event = dict(first.event.to_dict(), kind="snoozed", payload={"snooze_until": "2026-09-15T09:00:00+08:00"}, payload_digest="tampered", event_id="jme-forged", expected_management_revision=1)
    twice = jm.reduce_actions(report=report, events=[first.event.to_dict(), forged_event], now=NOW)
    assert twice.management_log["conflict"] == 1 and twice.item(item.id).status == "claimed"


def test_stale_item_version_conflicts():
    report = _report()
    item = _select(report, {"dependency_ref": REF_A})
    cmd = _cmd(item, "c-stale", "claim", expected_item_version="not-the-current-snapshot")
    result = jm.validate_action(item=item, command=cmd, owner_user_id=OWNER, now=NOW)
    assert result.status == "conflict" and result.reason_code == "stale_item_version"


def test_cross_owner_commands_rejected_generically():
    report = _report()
    item = _select(report, {"dependency_ref": REF_A})
    cmd = _cmd(item, "c-bob", "claim")
    cmd["owner_user_id"] = "bob"
    res = jm.validate_action(item=item, command=cmd, owner_user_id="bob", now=NOW)
    assert res.status == "rejected" and res.reason_code == "forbidden" and res.item_id is None
    assert "alice" not in res.detail
    res2 = jm.validate_action(item=item, command=_cmd(item, "c-mismatch", "claim"), owner_user_id="bob", now=NOW)
    assert res2.status == "rejected" and res2.reason_code == "forbidden"
    forged = _cmd(item, "c-forged", "claim")
    forged["owner_user_id"] = "../alice"
    res3 = jm.validate_action(item=item, command=forged, owner_user_id=OWNER, now=NOW)
    assert res3.status == "rejected" and res3.reason_code == "invalid_command"


def test_reduce_rejects_foreign_events_and_keeps_report_pure():
    report = _report()
    item = _select(report, {"dependency_ref": REF_A})
    foreign = _system_event(item, "jme-f", "rejudgment_failed", at=NOW, revision=0, payload={})
    foreign["owner_user_id"] = "bob"
    try:
        jm.reduce_actions(report=report, events=[foreign], now=NOW)
    except jm.MaintenanceContractError as exc:
        assert exc.code == "owner_mismatch"
    else:  # pragma: no cover - 失败形状
        raise AssertionError("跨 owner 事件必须被拒绝")
    # reduce 不改原报告对象，只返回新报告
    reduced = jm.reduce_actions(report=report, events=[], now=NOW)
    assert reduced.items == report.items and reduced.id == report.id and report.management_log == {}
    assert reduced.management_log["events_seen"] == 0

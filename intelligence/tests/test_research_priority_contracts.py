"""02 · 合同校验（spec §5.1、P09）：越权、未知 schema、非法枚举、裸时间戳都拒绝整份输入。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from intelligence.services import research_priority as rp
from intelligence.services.research_priority import contracts as c

OWNER = "u_test"
EVAL_AT = "2026-09-13T02:00:00Z"


def _valid_task(**overrides):
    task = {
        "schema_version": c.SCHEMA_TASK,
        "id": "t1",
        "owner_user_id": OWNER,
        "scope": {"conversation_id": "conv_1", "entity_refs": ["theme:制冷剂"]},
        "source": {"kind": "test_source", "id": "s1", "namespace": "tests", "version_or_hash": "v1", "scope": None},
        "object_refs": [{"kind": "judgment", "id": "j1", "namespace": "judgments", "version_or_hash": "v1", "scope": None}],
        "maintenance_item_ids": ["mi_1"],
        "question": "核对判断 j1 的依据",
        "discriminating_evidence": "公告字段 X",
        "completion_condition": "读到公告版本 h1 并核对字段 X",
        "effect_kind": c.EFFECT_REVIEW_CHANGED,
        "effect_evidence_refs": [{"kind": "evidence", "id": "ann:1", "namespace": "announcement", "version_or_hash": "h1", "scope": None}],
        "condition_result": None,
        "availability": c.AVAIL_ACTIONABLE,
        "available_at": None,
        "due_at": None,
        "as_of": "2026-09-12",
        "knowledge_cutoff": "2026-09-12T15:30:00+08:00",
        "pit_grade": "trade_date_only",
        "effort": None,
        "gaps": [],
        "legacy_unbound": False,
        "management_status": "open",
    }
    task.update(overrides)
    return task


def _code_of(task, **kwargs) -> str:
    with pytest.raises(c.ContractError) as excinfo:
        rp.prioritize([task], None, None, EVAL_AT, **kwargs)
    return excinfo.value.code


def test_valid_task_round_trips_and_gets_canonical_id():
    report = rp.prioritize([_valid_task()], None, None, EVAL_AT)
    task = report["selected"][0]["task"]
    assert task["id"].startswith("rt_") and task["source_task_ids"] == ["t1"]
    assert task["scope"]["entity_refs"] == ["theme:制冷剂"]
    assert task["effort"] == {"seconds": None, "kind": "unknown", "source_ref": None}


def test_p09_foreign_owner_is_rejected_without_leaking_their_id():
    with pytest.raises(c.ContractError) as excinfo:
        rp.prioritize([_valid_task(owner_user_id="u_other")], None, None, EVAL_AT, owner_user_id=OWNER)
    assert excinfo.value.code == "owner_mismatch"
    assert "u_other" not in str(excinfo.value)
    # 候选包的 owner 与调用方不一致同样拒绝。
    with pytest.raises(c.ContractError) as excinfo:
        rp.prioritize({"schema_version": c.SCHEMA_CANDIDATES, "owner_user_id": "u_other", "tasks": []}, None, None, EVAL_AT, owner_user_id=OWNER)
    assert excinfo.value.code == "owner_mismatch"
    # 同一批里混入另一个用户的记录：整份拒绝，不是悄悄丢掉那条。
    with pytest.raises(c.ContractError) as excinfo:
        rp.prioritize([_valid_task(), _valid_task(id="t2", owner_user_id="u_other")], None, None, EVAL_AT)
    assert excinfo.value.code == "owner_mismatch"


def test_p09_future_records_do_not_enter_scoring():
    future_cutoff = _valid_task(id="fc", knowledge_cutoff="2026-09-14T00:00:00Z")
    future_as_of = _valid_task(
        id="fa",
        as_of="2026-09-14",
        object_refs=[{"kind": "judgment", "id": "j2", "namespace": "judgments", "version_or_hash": None, "scope": None}],
        effect_evidence_refs=[{"kind": "evidence", "id": "ann:2", "namespace": "announcement", "version_or_hash": "h9", "scope": None}],
    )
    report = rp.prioritize([future_cutoff, future_as_of], None, None, EVAL_AT)
    assert report["selected"] == [] and report["deferred"] == []
    assert [row["reason"] for row in report["blocked"]] == [c.BLOCK_FUTURE_RECORD, c.BLOCK_FUTURE_RECORD]
    assert report["gaps"][0]["reason"] == "effort_unknown"
    assert any(g["reason"] == "future_record_excluded" and len(g["task_ids"]) == 2 for g in report["gaps"])
    # 同一证据在两个市场日重复观测 → 合并成一项，知识状态取最新的那次。
    twice = rp.prioritize([_valid_task(id="d1", as_of="2026-09-11"), _valid_task(id="d2", as_of="2026-09-12")], None, None, EVAL_AT)
    assert twice["totals"]["candidate_count"] == 1 and twice["selected"][0]["task"]["as_of"] == "2026-09-12"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"schema_version": "research-task/v0"}, "unknown_schema"),
        ({"owner_user_id": ""}, "owner_missing"),
        ({"effect_kind": "sell"}, "invalid_enum"),
        ({"availability": "maybe"}, "invalid_enum"),
        ({"pit_grade": "intraday"}, "invalid_enum"),
        ({"condition_result": "yes"}, "invalid_enum"),
        ({"management_status": "done"}, "invalid_enum"),
        ({"effort": {"seconds": 0, "kind": "unknown"}}, "invalid_effort"),
        ({"effort": {"seconds": None, "kind": "observed"}}, "invalid_effort"),
        ({"effort": {"seconds": -5, "kind": "observed"}}, "invalid_effort"),
        ({"legacy_unbound": True}, "unbound_flag_mismatch"),
        ({"object_refs": [], "legacy_unbound": False}, "unbound_flag_mismatch"),
        ({"knowledge_cutoff": "2026-09-12T15:30:00"}, "naive_timestamp"),
        ({"due_at": "昨天"}, "invalid_timestamp"),
        ({"as_of": "2026-09-12T00:00:00+08:00"}, "invalid_timestamp"),
        ({"object_refs": [{"kind": "judgment", "namespace": "judgments"}]}, "invalid_ref"),
        ({"source": {"kind": "", "id": "s", "namespace": "tests"}}, "invalid_ref"),
        ({"question": ""}, "invalid_task"),
        ({"gaps": [{"ref": "x"}]}, "invalid_gap"),
    ],
)
def test_contract_violations_reject_whole_input(overrides, code):
    assert _code_of(_valid_task(**overrides)) == code


def test_abandon_requires_true_condition_evidence_and_object():
    base = dict(effect_kind=c.EFFECT_ABANDON, condition_result=True)
    assert rp.prioritize([_valid_task(**base)], None, None, EVAL_AT)["selected"][0]["group"] == c.GROUP_ABANDON
    assert _code_of(_valid_task(**{**base, "condition_result": "unknown"})) == "abandon_without_observed_trigger"
    assert _code_of(_valid_task(**{**base, "condition_result": False})) == "abandon_without_observed_trigger"
    assert _code_of(_valid_task(**{**base, "effect_evidence_refs": []})) == "abandon_without_observed_trigger"


def test_parse_instant_accepts_dates_and_zoned_times_only():
    assert c.parse_instant("2026-09-12", field="x") == datetime(2026, 9, 12, tzinfo=timezone.utc)
    assert c.parse_instant("2026-09-12T15:30:00+08:00", field="x") == datetime(2026, 9, 12, 7, 30, tzinfo=timezone.utc)
    assert c.parse_instant(None, field="x") is None
    with pytest.raises(c.ContractError) as excinfo:
        c.parse_instant(datetime(2026, 9, 12, 15, 30), field="x")
    assert excinfo.value.code == "naive_timestamp"
    with pytest.raises(c.ContractError):
        c.parse_market_date("2026-13-40", field="as_of")


def test_identity_key_and_task_id_are_stable_and_scope_sensitive():
    a = c.validate_task(_valid_task(), owner_user_id=OWNER)
    b = c.validate_task(_valid_task(id="other_id", question="换个问法"), owner_user_id=OWNER)
    # 有证据引用：键由证据版本决定，与 id / 问句无关。
    assert c.identity_key(a) == c.identity_key(b)
    assert c.task_id_for(c.identity_key(a)) == c.task_id_for(c.identity_key(b))
    changed_hash = c.validate_task(
        _valid_task(effect_evidence_refs=[{"kind": "evidence", "id": "ann:1", "namespace": "announcement", "version_or_hash": "h2", "scope": None}]),
        owner_user_id=OWNER,
    )
    assert c.identity_key(changed_hash) != c.identity_key(a)
    # 无证据引用：键含问句、实体、as_of、due、绑定对象。
    plain = c.validate_task(_valid_task(effect_evidence_refs=[], effect_kind=c.EFFECT_FILL_GAP), owner_user_id=OWNER)
    other_entity = c.validate_task(
        _valid_task(effect_evidence_refs=[], effect_kind=c.EFFECT_FILL_GAP, scope={"conversation_id": "conv_1", "entity_refs": ["theme:氟化工"]}),
        owner_user_id=OWNER,
    )
    assert c.identity_key(plain) != c.identity_key(other_entity)
    other_owner_key = c.identity_key({**plain, "owner_user_id": "u_other"})
    assert other_owner_key != c.identity_key(plain)  # 不同用户相同内容不碰撞


def test_policy_and_budget_objects():
    assert c.Policy.from_value(None) == c.Policy()
    assert c.Policy.from_value({"max_items": 5}).max_items == 5
    assert c.Budget.from_value(None).seconds is None
    assert c.Budget.from_value(2.5).seconds == 150.0
    assert c.Budget.from_value({"minutes": 0}).seconds == 0.0
    with pytest.raises(c.ContractError):
        c.Policy.from_value({"unknown": 1})
    with pytest.raises(c.ContractError):
        c.Budget.from_value({"hours": 1})

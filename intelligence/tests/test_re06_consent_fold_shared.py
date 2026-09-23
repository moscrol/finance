"""RE06 同意折叠：写侧门与读侧测量共用同一段折叠，剩下的差异必须是有意的。

写侧（``ObservingRunStore`` 决定要不要落测量事件）与读侧（05 ``measure`` 决定这条
事件算不算数）各自判断同一件事：某身份在某时刻生效的同意范围。第九轮复核是按当时
快照逐条探针对齐的，快照对齐不是结构保证——任一侧改了排序键或集合运算，另一侧
不会有任何测试变红，后果是「写了读不到」或「已撤回却仍在读数里」。

有意保留的差异只有两处，都在**取哪些记录**与**没有记录怎么办**上，不在折叠里：
读侧只认带 ``participant_id`` 的记录、无记录返回 None（未知）；写侧认 owner 自己的
记录（``participant_id`` 为空或等于 owner）、无记录按自用默认放行。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from intelligence.services.product_value import measure as M
from intelligence.services.product_value import validate_event
from intelligence.services.product_value.consent import covers_measurement, scopes_at
from intelligence.services.product_value.contracts import (
    EVENT_SCHEMA, PROVENANCE_OBSERVED, REQUIRED_MEASUREMENT_SCOPES, SOURCE_SERVER,
)
from intelligence.services.research_evolution.run_observer import ObservingRunStore

OWNER = "owner-consent-fold"
T0 = datetime(2026, 9, 22, 8, 0, tzinfo=timezone.utc)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def entry(minutes: int, action: str, *scopes: str):
    return (at(minutes), action, frozenset(scopes))


def consent_event(minutes: int, action: str, scopes: list[str], *, participant: str | None, tag: str) -> dict:
    stamp = at(minutes).isoformat()
    return {
        "schema_version": EVENT_SCHEMA,
        "event_id": f"consent-{tag}",
        "event_type": "consent_changed",
        "owner_user_id": OWNER,
        "pilot_id": f"workbench:{OWNER}",
        "participant_id": participant,
        "task_id": None, "case_id": None, "case_version": None, "case_pair_id": None,
        "run_ids": [], "object_refs": [], "assistance_condition": None,
        "event_at": stamp, "recorded_at": stamp,
        "source_version": {"code_sha": "test", "protocol_version": "workbench-self-use/v1", "artifact_hash": None},
        "provenance": {"kind": PROVENANCE_OBSERVED, "source_ref": "test", "source_hash": None},
        "source_channel": SOURCE_SERVER,
        "payload": {
            "consent_version": "fold-v1", "scopes": scopes, "effective_at": stamp,
            "action": action, "terms_hash": "sha256:" + "f" * 64,
            "initiator": "user", "assistance_source": "workbench",
        },
        "gaps": [{"field": name, "reason": "not_applicable"}
                 for name in ("task_id", "case_id", "case_version", "case_pair_id", "assistance_condition")
                 ] + ([{"field": "participant_id", "reason": "not_applicable"}] if participant is None else []),
    }


def store_with(tmp_path, events: list[dict]) -> ObservingRunStore:
    store = ObservingRunStore(user_id=OWNER, root=tmp_path / "runs", evolution_root=tmp_path / "evolution")
    with store._evolution_store.transaction() as txn:
        for event in events:
            result = validate_event(event)
            assert result.ok, [i.code for i in result.issues]
            txn.append_product_value_event(result.normalized or event, content_hash=result.content_hash or "")
    return store


def read_side_scopes(store: ObservingRunStore, participant: str, when: datetime):
    events = store._evolution_store.list_product_value_events()
    return M._scopes_at(M._consent_timeline(events), participant, when)


@pytest.mark.parametrize(
    ("entries", "when", "expected"),
    [
        # 排序键是 (effective_at, action)：同一时刻 grant 先于 withdraw，净效果是撤回。
        ([entry(0, "withdraw", "logging"), entry(0, "grant", "research", "logging")], at(1), {"research"}),
        # 乱序输入必须先排序再折叠，不能按到达顺序算。
        ([entry(5, "withdraw", "logging"), entry(0, "grant", "research", "logging")], at(1), {"research", "logging"}),
        # effective_at > at 的记录还没生效：未来的撤回不能提前扣掉现在的范围。
        ([entry(0, "grant", "research", "logging"), entry(9, "withdraw", "logging")], at(1), {"research", "logging"}),
        ([entry(0, "grant", "research", "logging"), entry(9, "withdraw", "logging")], at(10), {"research"}),
        # 撤回按集合差，不清空其它范围；重复授权幂等。
        ([entry(0, "grant", "research", "logging", "blind_review"), entry(1, "withdraw", "blind_review"),
          entry(2, "grant", "research")], at(3), {"research", "logging"}),
        # 不认识的 action 既不授权也不撤回。
        ([entry(0, "grant", "research", "logging"), entry(1, "revoke", "logging")], at(2), {"research", "logging"}),
    ],
)
def test_shared_fold_orders_truncates_and_applies_grant_withdraw(entries, when, expected):
    assert scopes_at(entries, when) == frozenset(expected)


def test_shared_fold_treats_no_entries_as_empty_not_as_permission():
    assert scopes_at((), at(1)) == frozenset()
    assert not covers_measurement(scopes_at((), at(1)))


def test_required_scope_rule_is_one_rule_for_both_sides():
    assert covers_measurement(REQUIRED_MEASUREMENT_SCOPES)
    assert covers_measurement(REQUIRED_MEASUREMENT_SCOPES | {"blind_review"})
    for partial in REQUIRED_MEASUREMENT_SCOPES:
        assert not covers_measurement(frozenset({partial}))


@pytest.mark.parametrize("minutes", [0, 1, 5, 9, 10, 20])
def test_write_gate_and_read_side_agree_on_the_same_ledger(tmp_path, minutes):
    """同一份台账、同一个身份：写不写与算不算必须同判。"""
    store = store_with(tmp_path, [
        consent_event(0, "grant", ["research", "logging"], participant=OWNER, tag="a"),
        consent_event(5, "withdraw", ["logging"], participant=OWNER, tag="b"),
        consent_event(10, "grant", ["logging"], participant=OWNER, tag="c"),
    ])
    when = at(minutes)
    read = read_side_scopes(store, OWNER, when)
    assert read is not None
    assert store._measurement_consented(when) == covers_measurement(read)
    assert covers_measurement(read) == (minutes < 5 or minutes >= 10)


def test_no_record_keeps_self_use_default_on_write_and_unknown_on_read(tmp_path):
    """两侧唯一允许分叉的地方：没有记录时写侧照写（owner 观察自己），读侧判未知。"""
    store = store_with(tmp_path, [])
    assert store._measurement_consented(at(1)) is True
    assert read_side_scopes(store, OWNER, at(1)) is None


def test_owner_record_without_participant_id_counts_only_on_the_write_side(tmp_path):
    store = store_with(tmp_path, [
        consent_event(0, "grant", ["research"], participant=None, tag="self"),
    ])
    # 写侧：owner 表达过部分范围 → 自用默认被翻成不写（复核 T08）。
    assert store._measurement_consented(at(1)) is False
    # 读侧：无 participant_id 的记录不进试点时间线，仍是未知而不是空集。
    assert read_side_scopes(store, OWNER, at(1)) is None


def test_read_side_timeline_admits_pilot_records_only(tmp_path):
    """owner 自用记录（无 participant_id）不得在读侧时间线里占位。

    当下它会落到 ``"None"`` 键上、恰好没人查，所以拿掉过滤暂时看不出差别——
    这正是它容易被当成冗余删掉的原因。规则本身（自用≠试点）是隐私口径，直接钉住。
    """
    store = store_with(tmp_path, [
        consent_event(0, "grant", ["research", "logging"], participant=None, tag="self"),
        consent_event(0, "grant", ["research"], participant="pilot-participant", tag="pilot"),
    ])
    timeline = M._consent_timeline(store._evolution_store.list_product_value_events())
    assert set(timeline) == {"pilot-participant"}


def test_both_sides_reach_the_fold_through_the_shared_function(tmp_path, monkeypatch):
    """不留私有副本：改折叠只有一处可改。"""
    import intelligence.services.product_value.consent as C

    assert M.scopes_at is C.scopes_at
    calls: list[datetime] = []
    monkeypatch.setattr(C, "scopes_at", lambda entries, when: (calls.append(when), frozenset())[1])
    store = store_with(tmp_path, [consent_event(0, "grant", ["research", "logging"], participant=OWNER, tag="a")])
    assert store._measurement_consented(at(1)) is False  # 打桩返回空集 → 门关上
    assert calls == [at(1)]

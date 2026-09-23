"""前端「使用计时」按钮的同意事件，对自用测量门的实际影响（现状刻画）。

`ResearchActivityControl.tsx` 在「同意并开始本次计时」发 grant、在「停止使用计时」/
`pagehide` 发 withdraw，两者都用 ``scopes: ["research", "logging"]``、
``participant_id = owner_user_id``。写侧自用测量门恰好认这个身份（``participant_id``
为空或等于 owner），而它要求的正是这两个范围。

净效果：**点一次「停止使用计时」，自用测量（run_started / run_finished / cost_recorded）
就此关停**，直到用户再次授权。而按钮旁的状态文案只说「使用计时已关闭；研究功能不受
影响」——研究确实不受影响，但自用测量停了这件事没说。

这组测试**刻画现状**，不主张现状正确。它把 QC 第九轮 P3「首条部分授权就翻掉自用默认，
UI 文案要说清」从一句提醒变成可执行事实：不是「部分授权」，是一次完整撤回，且发生在
用户以为自己只是停掉计时的时候。口径要改（改文案 / 给计时同意换 scope 名 / 门忽略该
consent_version）属产品判断——改之前先改本文件的说明。
"""
from __future__ import annotations

import pytest

from intelligence.services.product_value import validate_event
from intelligence.services.product_value.contracts import (
    EVENT_SCHEMA, PROVENANCE_OBSERVED, REQUIRED_MEASUREMENT_SCOPES, SOURCE_SERVER,
)
from intelligence.services.research_evolution.run_observer import ObservingRunStore
from intelligence.services.research_evolution.store import EvolutionStore
from intelligence.tests.test_re06_consent_fold_shared import OWNER, at

# 与 ResearchActivityControl.tsx 保持一致：同一份 TERMS 的哈希、同一组 scope。
ACTIVITY_SCOPES = ["research", "logging"]
ACTIVITY_CONSENT_VERSION = "workbench-activity-v1"


def activity_consent(minutes: int, action: str, tag: str) -> dict:
    """前端那个按钮真正发出去的载荷形状（participant_id 就是 owner 自己）。"""
    stamp = at(minutes).isoformat()
    return {
        "schema_version": EVENT_SCHEMA,
        "event_id": f"activity-{tag}",
        "event_type": "consent_changed",
        "owner_user_id": OWNER,
        "pilot_id": f"workbench:{OWNER}",
        "participant_id": OWNER,
        "task_id": None, "case_id": None, "case_version": None, "case_pair_id": None,
        "run_ids": [], "object_refs": [], "assistance_condition": None,
        "event_at": stamp, "recorded_at": stamp,
        "source_version": {"code_sha": "test", "protocol_version": "workbench-self-use/v1", "artifact_hash": None},
        "provenance": {"kind": PROVENANCE_OBSERVED, "source_ref": "webapp", "source_hash": None},
        "source_channel": SOURCE_SERVER,
        "payload": {
            "consent_version": ACTIVITY_CONSENT_VERSION, "scopes": list(ACTIVITY_SCOPES),
            "effective_at": stamp, "action": action, "terms_hash": "sha256:" + "a" * 64,
            "initiator": "user", "assistance_source": "workbench",
        },
        "gaps": [{"field": name, "reason": "not_applicable"}
                 for name in ("task_id", "case_id", "case_version", "case_pair_id", "assistance_condition")],
    }


@pytest.fixture
def store(tmp_path) -> ObservingRunStore:
    return ObservingRunStore(user_id=OWNER, root=tmp_path / "runs", evolution_root=tmp_path / "evolution")


def append(store: ObservingRunStore, events: list[dict]) -> None:
    ledger = EvolutionStore(store._evolution_store.root, OWNER)
    with ledger.transaction() as txn:
        for event in events:
            result = validate_event(event)
            assert result.ok, [i.code for i in result.issues]
            txn.append_product_value_event(result.normalized or event, content_hash=result.content_hash or "")


def test_activity_scopes_are_exactly_the_measurement_gate_scopes():
    """两套同意共用同一组 scope 名——这是「停计时顺带关测量」的根因，不是巧合。"""
    assert frozenset(ACTIVITY_SCOPES) == REQUIRED_MEASUREMENT_SCOPES


def test_never_touching_the_timer_keeps_self_use_measurement_on(store):
    assert store._measurement_consented(at(10)) is True


def test_starting_the_timer_keeps_measurement_on(store):
    append(store, [activity_consent(0, "grant", "start")])
    assert store._measurement_consented(at(10)) is True


def test_stopping_the_timer_turns_self_use_measurement_off_for_good(store):
    """现状刻画：停一次计时 → 自用测量此后不再落账，用户界面没有任何提示。"""
    append(store, [activity_consent(0, "grant", "start"), activity_consent(5, "withdraw", "stop")])
    assert store._measurement_consented(at(6)) is False
    assert store._measurement_consented(at(600)) is False  # 不是一时的：此后一直关着


def test_using_the_timer_once_ends_up_stricter_than_never_using_it(store, tmp_path):
    """同一台机器上，用过一次计时的 owner 比从没用过的 owner 少被测量——这个不对称没人告知。"""
    untouched = ObservingRunStore(user_id=OWNER, root=tmp_path / "r2", evolution_root=tmp_path / "e2")
    append(store, [activity_consent(0, "grant", "start"), activity_consent(5, "withdraw", "stop")])
    assert untouched._measurement_consented(at(6)) is True
    assert store._measurement_consented(at(6)) is False

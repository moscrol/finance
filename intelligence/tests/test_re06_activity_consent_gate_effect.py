"""方案 B：计时授权独立，旧版只做读取兼容，不改历史台账。

新旧控件的开始/停止都不能授权或撤回研究测量。读侧保留无记录=未知，
写侧保留无记录=自用默认；真正的测量撤回、部分授权和锁内复核仍有效。
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from intelligence.services.product_value import measure as M
from intelligence.services.product_value.consent import covers_measurement, measurement_scopes
from intelligence.services.product_value.contracts import (
    ACTIVITY_TIMER_SCOPE, REQUIRED_MEASUREMENT_SCOPES, SOURCE_FRONTEND,
)
from intelligence.tests.test_re06_consent_fold_shared import (
    OWNER, at, consent_event, read_side_scopes, store_with,
)


@pytest.fixture(params=["workbench-activity-v1", "workbench-activity-v2"])
def timer_version(request):
    return request.param


def activity_consent(minutes: int, action: str, tag: str, version: str) -> dict:
    scopes = ["research", "logging"] if version == "workbench-activity-v1" else [ACTIVITY_TIMER_SCOPE]
    event = consent_event(minutes, action, scopes, participant=OWNER, tag=tag)
    event["source_channel"] = SOURCE_FRONTEND
    event["payload"]["consent_version"] = version
    return event


def timer_cycle(version: str) -> list[dict]:
    return [activity_consent(0, "grant", "start", version), activity_consent(5, "withdraw", "stop", version)]


def test_timer_scope_is_not_a_measurement_scope():
    assert ACTIVITY_TIMER_SCOPE not in REQUIRED_MEASUREMENT_SCOPES
    assert not covers_measurement({ACTIVITY_TIMER_SCOPE})


@pytest.mark.parametrize("minutes", [1, 6, 600])
def test_timer_does_not_disable_default_measurement_or_authorize_pilot(tmp_path, timer_version, minutes):
    store = store_with(tmp_path, timer_cycle(timer_version))
    assert store._measurement_consented(at(minutes)) is True
    assert read_side_scopes(store, OWNER, at(minutes)) is None


@pytest.mark.parametrize("minutes", [1, 6, 600])
def test_timer_never_revokes_explicit_measurement_consent(tmp_path, timer_version, minutes):
    store = store_with(tmp_path, [
        consent_event(-1, "grant", ["research", "logging"], participant=OWNER, tag="measure"),
        *timer_cycle(timer_version),
    ])
    assert store._measurement_consented(at(minutes)) is True
    assert read_side_scopes(store, OWNER, at(minutes)) == REQUIRED_MEASUREMENT_SCOPES


@pytest.mark.parametrize("minutes", [1, 6, 600])
@pytest.mark.parametrize("scopes", [["research"], ["logging"], ["blind_review"], []])
def test_timer_never_grants_missing_measurement_scope(tmp_path, timer_version, minutes, scopes):
    store = store_with(tmp_path, [
        consent_event(-1, "grant", scopes, participant=OWNER, tag="partial"),
        *timer_cycle(timer_version),
    ])
    assert store._measurement_consented(at(minutes)) is False
    assert read_side_scopes(store, OWNER, at(minutes)) == frozenset(scopes)


@pytest.mark.parametrize("scope", ["research", "logging"])
def test_real_withdrawal_survives_timer_restart(tmp_path, timer_version, scope):
    store = store_with(tmp_path, [
        consent_event(-3, "grant", ["research", "logging"], participant=OWNER, tag="measure"),
        consent_event(-2, "withdraw", [scope], participant=OWNER, tag="revoke"),
        *timer_cycle(timer_version),
        activity_consent(7, "grant", "restart", timer_version),
    ])
    for minutes in (1, 6, 8):
        assert store._measurement_consented(at(minutes)) is False
        assert read_side_scopes(store, OWNER, at(minutes)) == REQUIRED_MEASUREMENT_SCOPES - {scope}


def test_legacy_and_new_records_can_coexist_without_migration(tmp_path):
    events = [
        *timer_cycle("workbench-activity-v1"),
        activity_consent(10, "grant", "new-start", "workbench-activity-v2"),
        activity_consent(15, "withdraw", "new-stop", "workbench-activity-v2"),
    ]
    store = store_with(tmp_path, events)
    before = deepcopy(store._evolution_store.list_product_value_events())
    for minutes in (1, 6, 11, 16):
        assert store._measurement_consented(at(minutes)) is True
        assert read_side_scopes(store, OWNER, at(minutes)) is None
    assert store._evolution_store.list_product_value_events() == before


@pytest.mark.parametrize("field,value", [
    ("source_channel", "server"),
    ("source_version", {"protocol_version": "pilot/v1"}),
    ("pilot_id", "pilot-1"),
    ("participant_id", "pilot-participant"),
    ("task_id", "assigned-task"),
])
def test_legacy_alias_requires_self_use_timer_shape(field, value):
    event = activity_consent(0, "withdraw", "ambiguous", "workbench-activity-v1")
    event[field] = value
    assert measurement_scopes(event) == REQUIRED_MEASUREMENT_SCOPES


@pytest.mark.parametrize("version,scopes", [
    ("workbench-activity-v1", ["logging"]),
    ("workbench-activity-v1", ["research", "logging", "blind_review"]),
    ("workbench-activity-v2", ["research", "logging"]),
    ("workbench-activity-v3", ["research", "logging"]),
    ("other-entry-v1", ["research", "logging"]),
    ("other-entry-v1", ["activity-timer", "logging"]),
])
def test_version_alone_never_bypasses_a_real_measurement_withdrawal(version, scopes):
    event = activity_consent(0, "withdraw", "real", version)
    event["payload"]["scopes"] = scopes
    assert measurement_scopes(event) == frozenset(scopes) - {ACTIVITY_TIMER_SCOPE}


def test_any_entry_can_use_the_new_timer_scope_without_a_version_allowlist(tmp_path):
    store = store_with(tmp_path, timer_cycle("another-timer-v1"))
    assert store._measurement_consented(at(6)) is True
    assert read_side_scopes(store, OWNER, at(6)) is None


def test_read_and_write_share_scope_classification():
    from intelligence.services.product_value import consent

    assert M.measurement_scopes is consent.measurement_scopes

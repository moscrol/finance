"""判断持续维护 · 差分与条件（spec 01 §4；§8 反向验收第 1–8 条 + 合同夹具 complete / missing_source / legacy）。

每条测试都对应一个「错误实现会变红」的反例；夹具输出由真实函数生成后冻结（regen 见 fixtures/…/01/README.md）。
"""

from __future__ import annotations

import copy
import json
import os
import random
from pathlib import Path

import pytest

from intelligence.services import judgment_maintenance as jm
from intelligence.services.judgment_maintenance import adapters
from intelligence.services.judgment_maintenance.contracts import MaintenanceContractError

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "research_evolution" / "01"
OWNER = "alice"
AS_OF = "2026-09-12"
REF_A = "fact_market_daily:2026-09-01"
REF_B = "fact_research_report_catalog:r-77"
REF_C = "fact_theme_fundamental_doc:d-9"


# --------------------------------------------------------------------------- #
# 夹具与构造
# --------------------------------------------------------------------------- #
def _load(name: str) -> dict:
    return json.loads((FIXTURES / name / "input.json").read_text(encoding="utf-8"))


def _assess(payload: dict, **over) -> jm.MaintenanceReport:
    args = {
        "owner_user_id": payload["owner_user_id"],
        "as_of": payload["as_of"],
        "knowledge_cutoff": payload["knowledge_cutoff"],
        "bindings": payload["bindings"],
        "evidence_versions": payload["evidence_versions"],
        "condition_observations": payload["condition_observations"],
        "policy": payload["policy"],
        "generated_at": payload.get("generated_at"),
    }
    args.update(over)
    return jm.assess(**args)


def _golden(name: str) -> None:
    payload = _load(name)
    assert payload["synthetic"] is True
    report = _assess(payload).to_dict()
    expected_path = FIXTURES / name / "expected.json"
    if os.environ.get("JM_FIXTURES_UPDATE") == "1":
        expected_path.write_text(json.dumps({"synthetic": True, "report": report}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert expected["synthetic"] is True
    assert report == expected["report"]


def _object_ref(kind="judgment", oid="j-1", namespace="judgments"):
    return {"kind": kind, "id": oid, "namespace": namespace, "version_or_hash": "content_sha256:" + "1" * 64, "ref": f"{namespace}.jsonl:{oid}", "scope": {}}


def _binding(refs: dict[str, str | None], *, owner=OWNER, binding_id="b1", created_at="2026-09-05T20:00:00+08:00", baseline_cutoff="2026-09-05", conditions=(), object_ref=None):
    return {
        "schema_version": jm.BINDING_SCHEMA_VERSION,
        "binding_id": binding_id,
        "binding_version": 1,
        "owner_user_id": owner,
        "object_ref": object_ref or _object_ref(),
        "baseline_evidence_refs": list(refs),
        "baseline_source_hashes": dict(refs),
        "baseline_cutoff": baseline_cutoff,
        "created_at": created_at,
        "binding_origin": "user_confirmed",
        "conditions": list(conditions),
    }


def _version(ref: str, source_hash: str, recorded: str, valid_from="2026-09-01", **over):
    base = {"ref": ref, "source_hash": source_hash, "valid_from": valid_from, "recorded_at": recorded, "derivation": "deterministic"}
    base.update(over)
    return base


def _condition(cid="c1", role="downgrade", label="market_stage", op="in", value=("反弹",)):
    return {"condition_id": cid, "role": role, "expression": {"all": [{"label": label, "op": op, "value": list(value) if isinstance(value, tuple) else value}]}, "entity_id": "", "label_version": None}


def _obs(label: str, value, as_of=AS_OF, recorded=f"{AS_OF}T18:00:00+08:00"):
    return {"label": label, "entity_id": "", "as_of": as_of, "value": value, "recorded_at": recorded, "label_version": None, "source_ref": f"fact_market_daily:{as_of}"}


def _run(bindings, versions, observations=(), *, as_of=AS_OF, cutoff=AS_OF, owner=OWNER, policy=None):
    return jm.assess(
        owner_user_id=owner,
        as_of=as_of,
        knowledge_cutoff=cutoff,
        bindings=bindings,
        evidence_versions=versions,
        condition_observations=list(observations),
        policy=policy or {"schema_version": jm.POLICY_SCHEMA_VERSION},
        generated_at="2026-09-13T00:00:00+00:00",
    )


def _live(report: jm.MaintenanceReport):
    return [it for it in report.items if it.status != "superseded"]


# --------------------------------------------------------------------------- #
# 合同夹具（供 04 / 06 并行；冻结输出）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", ["complete", "missing_source", "legacy"])
def test_fixture_golden(name):
    _golden(name)


def test_fixture_complete_shape():
    report = _assess(_load("complete"))
    by_kind = {(it.change_type, it.reason_code, it.status) for it in report.items}
    assert ("content_changed", "hash_changed", "open") in by_kind
    assert ("source_expired", "validity_ended", "superseded") in by_kind
    assert ("source_corrected", "explicit_supersession", "open") in by_kind
    assert ("condition_evaluated", "condition_true", "open") in by_kind
    assert ("condition_evaluated", "condition_false", "open") in by_kind
    # 未变的那条依赖只计覆盖，不出项
    assert not any(it.dependency_ref == REF_B for it in report.items)
    assert report.counts == {"objects_seen": 1, "objects_bound": 1, "objects_unverifiable": 0, "dependencies_checked": 3, "items_open": 3}
    assert report.pit_grade == "strict" and report.hindsight is False
    corrected = next(it for it in report.items if it.change_type == "source_corrected")
    expired = next(it for it in report.items if it.change_type == "source_expired")
    assert corrected.supersedes_item_id == expired.id
    assert corrected.first_known_day == "2026-09-11" and expired.first_known_day == "2026-09-10"
    assert corrected.knowledge_cutoff == AS_OF == expired.knowledge_cutoff


# --------------------------------------------------------------------------- #
# §8.1 只改版式：hash 变但无显式条件 → requires_review，不写失效 / miss
# --------------------------------------------------------------------------- #
def test_format_only_hash_change_is_requires_review_not_falsification():
    report = _run([_binding({REF_A: "h1"})], [_version(REF_A, "h1", "2026-09-01T18:00:00+08:00"), _version(REF_A, "h1-reformatted", "2026-09-11T18:00:00+08:00")])
    items = _live(report)
    assert len(items) == 1
    item = items[0]
    assert (item.change_type, item.reason_code, item.epistemic_state) == ("content_changed", "hash_changed", "requires_review")
    assert item.action == "review_evidence"
    assert item.condition_result is None
    assert item.before[0].source_hash == "h1" and item.current[0].source_hash == "h1-reformatted"
    assert not any(it.change_type in ("source_expired", "dependency_missing") for it in report.items)
    assert not any(g.reason in ("validity_ended", "ref_unresolved") for g in report.gaps)
    assert item.pit_grade == "strict"


# --------------------------------------------------------------------------- #
# §8.2 主题同名不自动绑定；今天明确绑定可向前维护，不补成旧判断当时证据
# --------------------------------------------------------------------------- #
def test_same_theme_announcement_is_not_bound_automatically():
    stray = _version("fact_research_report_catalog:r-same-theme-new", "h-new", "2026-09-11T18:00:00+08:00", namespace="market_feature_store")
    report = _run([_binding({REF_A: "h1"})], [_version(REF_A, "h1", "2026-09-01T18:00:00+08:00"), stray])
    assert report.counts["dependencies_checked"] == 1
    assert not any(it.dependency_ref == stray["ref"] or any(v.ref == stray["ref"] for v in it.current) for it in report.items)
    assert report.items == ()


def test_binding_today_maintains_forward_only():
    versions = [_version(REF_A, "h1", "2026-09-01T18:00:00+08:00"), _version(REF_A, "h2", "2026-09-12T09:00:00+08:00")]
    binding = _binding({REF_A: "h1"}, created_at="2026-09-12T08:00:00+08:00", baseline_cutoff="2026-09-11")
    today = _run([binding], versions, as_of="2026-09-12", cutoff="2026-09-12")
    assert [it.change_type for it in _live(today)] == ["content_changed"]
    item = _live(today)[0]
    # before 的时间是版本真实被记录的时刻，不是绑定时刻；绑定日晚于原判断日也照实呈现
    assert item.before[0].recorded_at == "2026-09-01T18:00:00+08:00"
    assert item.first_known_day == "2026-09-12"
    earlier = _run([binding], versions, as_of="2026-09-08", cutoff="2026-09-08")
    assert earlier.items == ()
    assert earlier.counts["objects_bound"] == 0 and earlier.counts["objects_seen"] == 1
    assert {g.reason for g in earlier.gaps} == {"binding_not_yet_effective"}
    assert earlier.pit_grade == "unverifiable"


# --------------------------------------------------------------------------- #
# §8.3 同 ref 被更正：当前报告看到新版本，历史 cutoff 仍保留旧版本
# --------------------------------------------------------------------------- #
def test_correction_visible_now_but_not_at_historical_cutoff():
    versions = [_version(REF_A, "h1", "2026-09-01T18:00:00+08:00"), _version(REF_A, "h1-fixed", "2026-09-11T18:00:00+08:00")]
    binding = _binding({REF_A: "h1"})
    now = _run([binding], versions, as_of="2026-09-10", cutoff="2026-09-12")
    assert [(it.change_type, it.current[0].source_hash) for it in _live(now)] == [("content_changed", "h1-fixed")]
    assert now.hindsight is True and now.pit_grade == "trade_date_only"
    then = _run([binding], versions, as_of="2026-09-10", cutoff="2026-09-10")
    assert then.items == () and then.hindsight is False
    assert then.counts["dependencies_checked"] == 1
    assert now.id != then.id and now.input_digest != then.input_digest


def test_knowledge_cutoff_before_as_of_rejected():
    with pytest.raises(MaintenanceContractError) as info:
        _run([_binding({REF_A: "h1"})], [], as_of="2026-09-12", cutoff="2026-09-11")
    assert info.value.code == "knowledge_cutoff_before_as_of"


# --------------------------------------------------------------------------- #
# §8.4 某依赖缺失但其他两轨利好：缺口仍 unknown，不能补齐或判 false
# --------------------------------------------------------------------------- #
def test_missing_dependency_stays_unknown_even_when_others_are_fine():
    refs = {REF_A: "h1", REF_B: "h2", REF_C: "h3"}
    versions = [_version(REF_A, "h1", "2026-09-01T18:00:00+08:00"), _version(REF_B, "h2", "2026-09-01T18:00:00+08:00")]
    report = _run([_binding(refs)], versions)
    items = _live(report)
    assert len(items) == 1
    item = items[0]
    assert item.dependency_ref == REF_C
    assert (item.change_type, item.reason_code, item.epistemic_state, item.pit_grade) == ("dependency_missing", "ref_unresolved", "unknown", "unverifiable")
    assert item.condition_result is None
    assert item.current == ()
    gap = next(g for g in item.gaps if g.reason == "ref_unresolved")
    assert gap.retryable is True and gap.ref == REF_C
    assert report.counts == {"objects_seen": 1, "objects_bound": 1, "objects_unverifiable": 1, "dependencies_checked": 3, "items_open": 1}
    assert report.pit_grade == "unverifiable"


def test_fixture_missing_source_shape():
    report = _assess(_load("missing_source"))
    reasons = {(it.change_type, it.reason_code, it.epistemic_state) for it in report.items}
    assert reasons == {("dependency_missing", "ref_unresolved", "unknown"), ("condition_evaluated", "condition_unknown", "unknown")}
    cond = next(it for it in report.items if it.change_type == "condition_evaluated")
    assert cond.condition_result == "unknown" and cond.action == "none"
    assert report.counts["objects_unverifiable"] == 1 and report.counts["items_open"] == 1
    assert {g.reason for g in report.gaps} >= {"ref_unresolved", "condition_unknown"}
    assert all(g.retryable for g in report.gaps)


# --------------------------------------------------------------------------- #
# §8.5 确定性条件真 / 假 / 缺值各一例；散文条件被拒
# --------------------------------------------------------------------------- #
def _condition_report(observations, cond=None):
    return _run([_binding({REF_A: "h1"}, conditions=[cond or _condition()])], [_version(REF_A, "h1", "2026-09-01T18:00:00+08:00")], observations)


def test_condition_true_false_unknown():
    true_report = _condition_report([_obs("market_stage", "反弹")])
    item = _live(true_report)[0]
    assert (item.change_type, item.reason_code, item.condition_result, item.epistemic_state) == ("condition_evaluated", "condition_true", "true", "observed")
    assert item.condition_role == "downgrade" and item.action == "rejudge"
    assert item.condition_evaluation["readings"][0]["observed"] == "反弹"
    false_report = _condition_report([_obs("market_stage", "主升")])
    item = _live(false_report)[0]
    assert (item.reason_code, item.condition_result, item.action) == ("condition_false", "false", "none")
    assert not false_report.counts["items_open"]
    unknown_report = _condition_report([])
    item = _live(unknown_report)[0]
    assert (item.reason_code, item.condition_result, item.epistemic_state, item.pit_grade) == ("condition_unknown", "unknown", "unknown", "unverifiable")
    assert any(g.reason == "condition_unknown" and g.retryable for g in item.gaps)
    null_report = _condition_report([_obs("market_stage", None)])
    assert _live(null_report)[0].condition_result == "unknown"


def test_condition_role_drives_action_not_abandon_by_default():
    for role, action in (("upgrade", "rejudge"), ("downgrade", "rejudge"), ("abandon", "rejudge"), ("review", "review_evidence")):
        report = _condition_report([_obs("market_stage", "反弹")], _condition(role=role))
        item = _live(report)[0]
        assert (item.condition_role, item.action) == (role, action)


def test_prose_or_otherwise_condition_rejected():
    for expression, code in (
        ("若明天放量则升级", "condition_not_deterministic"),
        ("otherwise", "condition_not_deterministic"),
        ({"all": [{"label": "dual_red_streak", "op": ">=", "value": 3}]}, "condition_not_compilable"),
        ({"all": [{"label": "not_a_label", "op": "==", "value": True}]}, "condition_not_compilable"),
        ({"any": [{"label": "market_stage", "op": "==", "value": "反弹"}]}, "condition_not_compilable"),
    ):
        cond = {"condition_id": "c-bad", "role": "abandon", "expression": expression, "entity_id": "", "label_version": None}
        with pytest.raises(MaintenanceContractError) as info:
            _condition_report([_obs("market_stage", "反弹")], cond)
        assert info.value.code == code, expression


def test_conjunction_uses_three_valued_logic():
    cond = {
        "condition_id": "c-and",
        "role": "review",
        "expression": {"all": [{"label": "volume_surge", "op": "==", "value": True}, {"label": "market_stage", "op": "in", "value": ["反弹"]}]},
        "entity_id": "",
        "label_version": None,
    }
    # 一个 false 一个缺观测 → false（已知的假不被缺原料掩成 unknown）
    report = _condition_report([_obs("volume_surge", False)], cond)
    assert _live(report)[0].condition_result == "false"
    # 一个 true 一个缺观测 → unknown
    report = _condition_report([_obs("volume_surge", True)], cond)
    assert _live(report)[0].condition_result == "unknown"
    report = _condition_report([_obs("volume_surge", True), _obs("market_stage", "反弹")], cond)
    assert _live(report)[0].condition_result == "true"


def test_observation_after_cutoff_is_not_known_yet():
    late = _obs("market_stage", "反弹", recorded="2026-09-13T18:00:00+08:00")
    report = _condition_report([late])
    assert _live(report)[0].condition_result == "unknown"


def test_policy_can_switch_conditions_off():
    report = _run(
        [_binding({REF_A: "h1"}, conditions=[_condition()])],
        [_version(REF_A, "h1", "2026-09-01T18:00:00+08:00")],
        [_obs("market_stage", "反弹")],
        policy={"schema_version": jm.POLICY_SCHEMA_VERSION, "evaluate_conditions": False},
    )
    assert report.items == ()


# --------------------------------------------------------------------------- #
# §8.6 连续扫描两次、输入乱序、同事件重复三份：内容 id 与待办数量稳定
# --------------------------------------------------------------------------- #
def test_stable_ids_under_reorder_and_duplicates():
    payload = _load("complete")
    base = _assess(payload)
    again = _assess(payload)
    assert base.to_dict() == again.to_dict()
    shuffled = copy.deepcopy(payload)
    rng = random.Random(7)
    rng.shuffle(shuffled["evidence_versions"])
    rng.shuffle(shuffled["condition_observations"])
    shuffled["evidence_versions"] += [copy.deepcopy(v) for v in payload["evidence_versions"][:2]] * 3
    shuffled["condition_observations"] += [copy.deepcopy(payload["condition_observations"][0])] * 3
    shuffled["bindings"] += [copy.deepcopy(payload["bindings"][0])]
    other = _assess(shuffled)
    assert other.id == base.id and other.input_digest == base.input_digest
    assert [it.id for it in other.items] == [it.id for it in base.items]
    assert [it.item_version for it in other.items] == [it.item_version for it in base.items]
    assert other.counts == base.counts
    assert other.to_dict() == base.to_dict()


def test_generated_at_is_metadata_only():
    payload = _load("complete")
    a = _assess(payload, generated_at="2026-09-13T00:00:00+00:00")
    b = _assess(payload, generated_at="2026-09-14T00:00:00+00:00")
    assert a.id == b.id and a.input_digest == b.input_digest
    assert [it.id for it in a.items] == [it.id for it in b.items]
    assert a.generated_at != b.generated_at


def test_conflicting_duplicate_binding_rejected():
    payload = _load("complete")
    dup = copy.deepcopy(payload["bindings"][0])
    dup["baseline_source_hashes"][REF_A] = "h-other"
    with pytest.raises(MaintenanceContractError) as info:
        _assess(payload, bindings=payload["bindings"] + [dup])
    assert info.value.code == "duplicate_binding"


# --------------------------------------------------------------------------- #
# §8.7 同 id 位于不同 owner；伪造 owner、路径穿越、未授权 ref：不串读，不泄露存在性
# --------------------------------------------------------------------------- #
def test_same_ids_under_different_owners_do_not_collide():
    versions = [_version(REF_A, "h1", "2026-09-01T18:00:00+08:00"), _version(REF_A, "h2", "2026-09-11T18:00:00+08:00")]
    alice = _run([_binding({REF_A: "h1"}, owner="alice")], versions, owner="alice")
    bob = _run([_binding({REF_A: "h1"}, owner="bob")], versions, owner="bob")
    assert alice.items and bob.items
    assert alice.items[0].id != bob.items[0].id
    assert alice.id != bob.id
    assert alice.items[0].dedup_key != bob.items[0].dedup_key
    assert all(it.owner_user_id == "alice" for it in alice.items)


def test_foreign_binding_in_input_is_rejected():
    with pytest.raises(MaintenanceContractError) as info:
        _run([_binding({REF_A: "h1"}, owner="bob")], [], owner="alice")
    assert info.value.code == "owner_mismatch"
    assert "bob" not in info.value.detail


@pytest.mark.parametrize("bad_owner", ["../alice", "alice/../bob", "", "."])
def test_forged_owner_rejected(bad_owner):
    with pytest.raises(MaintenanceContractError) as info:
        _run([_binding({REF_A: "h1"}, owner=bad_owner)], [], owner=bad_owner)
    assert info.value.code == "invalid_owner"


def test_unauthorized_ref_rejected_without_leaking_other_user():
    foreign_ref = "users/bob/judgments.jsonl:j-9"
    with pytest.raises(MaintenanceContractError) as info:
        _run([_binding({foreign_ref: "h1"})], [], owner="alice")
    assert info.value.code == "foreign_user_ref"
    assert "bob" not in str(info.value)
    with pytest.raises(MaintenanceContractError) as info:
        _run([_binding({REF_A: "h1"})], [_version(foreign_ref, "h1", "2026-09-01T18:00:00+08:00")], owner="alice")
    assert info.value.code == "foreign_user_ref"


def test_object_namespace_outside_policy_rejected():
    binding = _binding({REF_A: "h1"}, object_ref=dict(_object_ref(), namespace="secrets"))
    with pytest.raises(MaintenanceContractError) as info:
        _run([binding], [])
    assert info.value.code == "namespace_not_allowed"


# --------------------------------------------------------------------------- #
# §8.8 旧记录缺原 ref / hash / 精确时间 / 版本：显示 coverage / gap，不声称完整历史复现
# --------------------------------------------------------------------------- #
def test_fixture_legacy_shape():
    report = _assess(_load("legacy"))
    by_binding = {it.binding_id: it for it in report.items}
    tree = by_binding["bind-legacy-tree"]
    assert (tree.change_type, tree.reason_code, tree.epistemic_state, tree.pit_grade) == ("dependency_missing", "dependency_unbound", "unknown", "unverifiable")
    assert tree.before[0].source_hash is None and tree.before[0].derivation == "unknown"
    assert tree.current and tree.current[0].source_hash == "h-m2"  # 从现在起能看到当前版本，但说不出「变了没有」
    noid = by_binding["bind-legacy-noid"]
    assert noid.object_ref.id is None and noid.object_ref.ref.startswith("judgments.jsonl:content_sha256:")
    assert (noid.change_type, noid.reason_code, noid.pit_grade) == ("dependency_missing", "time_metadata_missing", "unverifiable")
    assert "bind-late" not in by_binding
    assert report.counts == {"objects_seen": 3, "objects_bound": 2, "objects_unverifiable": 2, "dependencies_checked": 2, "items_open": 2}
    assert report.pit_grade == "unverifiable"
    assert {g.reason for g in report.gaps} == {"dependency_unbound", "time_metadata_missing", "binding_not_yet_effective"}


def test_legacy_checkpoint_without_evidence_only_yields_gaps():
    record = {"id": "ck-2026-09-01-aaaaaa", "ts": "2026-09-01T10:00:00", "claim": "x", "due": "2026-09-15", "metric": {"type": "market_daily", "conditions": [{"field": "advancers", "op": ">=", "target": 3000.0}]}}
    binding, gaps = adapters.candidate_binding_from_checkpoint(record, owner_user_id=OWNER, baseline_cutoff=AS_OF)
    assert binding is None
    assert [g.reason for g in gaps] == ["dependency_unbound"]
    assert "market_daily" in gaps[0].detail and gaps[0].retryable is True
    legacy = {"claim": "无 id 无时间的老行", "due": "2026-09-15"}
    binding, gaps = adapters.candidate_binding_from_checkpoint(legacy, owner_user_id=OWNER, baseline_cutoff=AS_OF)
    assert binding is None
    assert [g.reason for g in gaps] == ["object_id_missing", "time_metadata_missing", "dependency_unbound"]
    assert gaps[0].retryable is False


def test_time_metadata_missing_version_never_becomes_strict_or_changed():
    versions = [{"ref": REF_A, "source_hash": "h2", "valid_from": None, "recorded_at": None, "derivation": "deterministic"}]
    report = _run([_binding({REF_A: "h1"})], versions)
    item = _live(report)[0]
    assert (item.change_type, item.reason_code, item.pit_grade) == ("dependency_missing", "time_metadata_missing", "unverifiable")
    assert not any(it.change_type == "content_changed" for it in report.items)
    assert any(g.reason == "time_metadata_missing" for g in report.gaps)


def test_missing_recorded_at_downgrades_to_trade_date_only():
    versions = [
        _version(REF_A, "h1", "2026-09-01T18:00:00+08:00"),
        {"ref": REF_A, "source_hash": "h2", "valid_from": "2026-09-11", "recorded_at": None, "derivation": "deterministic"},
    ]
    report = _run([_binding({REF_A: "h1"})], versions)
    item = _live(report)[0]
    assert item.change_type == "content_changed" and item.pit_grade == "trade_date_only"
    assert report.pit_grade == "trade_date_only"


def test_baseline_unknown_to_version_set_is_a_gap_not_a_guess():
    versions = [_version(REF_A, "h-seen", "2026-09-01T18:00:00+08:00")]
    report = _run([_binding({REF_A: "h-never-seen"})], versions)
    item = _live(report)[0]
    assert item.change_type == "content_changed"
    assert item.before[0].source_hash == "h-never-seen" and item.before[0].recorded_at is None
    assert any(g.reason == "baseline_version_unknown" and not g.retryable for g in item.gaps)
    assert item.pit_grade == "trade_date_only"


def test_unchanged_dependency_is_only_coverage_unless_policy_emits_it():
    versions = [_version(REF_A, "h1", "2026-09-01T18:00:00+08:00")]
    report = _run([_binding({REF_A: "h1"})], versions)
    assert report.items == () and report.counts["dependencies_checked"] == 1 and report.pit_grade == "strict"
    emitted = _run([_binding({REF_A: "h1"})], versions, policy={"schema_version": jm.POLICY_SCHEMA_VERSION, "emit_unchanged": True})
    assert [(it.change_type, it.reason_code, it.action) for it in emitted.items] == [("unchanged", "no_change", "none")]
    assert emitted.counts["items_open"] == 0


# --------------------------------------------------------------------------- #
# 评审返修 J1：显式替代链的末端失效后，被替代的祖先不得复活成有效依据
# --------------------------------------------------------------------------- #
def test_expired_successor_does_not_revive_explicitly_superseded_ancestor():
    """ann:new 于 09-10 明确 supersedes ann:old，09-12 自身过期；旧版没有单独写 expired_at。

    规格 01 §4「源失效 / 缺引用 / 时间不明：unknown+gap」「恢复新版本关联旧项；更正链断裂为 gap」：
    链末端失效 = 这条依赖现在没有有效依据，必须留一条 open 的待办，而不是退回旧版本装作没事。
    """
    versions = [
        _version(REF_A, "h1", "2026-09-01T18:00:00+08:00"),
        _version("fact_market_daily:2026-09-01-v2", "h2", "2026-09-10T18:00:00+08:00", supersedes_ref=REF_A, expired_at="2026-09-12T08:00:00+08:00"),
    ]
    report = _run([_binding({REF_A: "h1"})], versions)
    live = _live(report)
    assert len(live) == 1, [(it.change_type, it.status) for it in report.items]
    item = live[0]
    assert (item.change_type, item.reason_code, item.epistemic_state) == ("source_expired", "validity_ended", "unknown")
    assert item.action == "restore_evidence" and item.status == "open"
    # 复活的证据就是「当前依据仍是旧版」；被显式替代的祖先永不再成为 current。
    assert [v.ref for v in item.current] != [REF_A]
    assert report.counts["items_open"] >= 1
    assert report.counts["objects_unverifiable"] == 1
    assert any(g.reason == "validity_ended" for g in report.gaps)


def test_superseded_ancestor_stays_dead_even_when_successor_validity_ends():
    """同一条链用 valid_to 结束（而不是 expired_at）也一样：祖先已被显式替代，不能当回退目标。"""
    versions = [
        _version(REF_A, "h1", "2026-09-01T18:00:00+08:00"),
        _version("fact_market_daily:2026-09-01-v2", "h2", "2026-09-10T18:00:00+08:00", supersedes_ref=REF_A, valid_to="2026-09-11"),
    ]
    report = _run([_binding({REF_A: "h1"})], versions)
    live = _live(report)
    assert [it.change_type for it in live] == ["source_expired"]
    assert [v.ref for v in live[0].current] != [REF_A]


def test_unsuperseded_sibling_still_serves_when_one_version_expires():
    """反向证伪：没有被谁显式替代的版本在另一版本过期后照常回到台前，不能被一起判失效。

    退场的资格来自「被显式更正」，不是「同一条链上有东西过期了」——两者混为一谈会把这条测试也判红。
    """
    versions = [
        _version(REF_A, "h1", "2026-09-01T18:00:00+08:00"),
        _version(REF_A, "h2", "2026-09-10T18:00:00+08:00", valid_from="2026-09-10", expired_at="2026-09-12T08:00:00+08:00"),
    ]
    report = _run([_binding({REF_A: "h1"})], versions)
    assert _live(report) == []  # 末态回到 unchanged：没有待办
    assert not any(it.change_type == "source_expired" for it in report.items)
    assert not any(g.reason == "validity_ended" for g in report.gaps)
    assert report.counts["objects_unverifiable"] == 0


# --------------------------------------------------------------------------- #
# 评审返修 S2：只有日期的 recorded_at 不得升为 strict（规格 01 §4 日期粒度降级）
# --------------------------------------------------------------------------- #
def test_date_only_recorded_at_is_never_strict():
    versions = [
        _version(REF_A, "h1", "2026-09-01"),
        _version(REF_A, "h2", "2026-09-11"),
    ]
    report = _run([_binding({REF_A: "h1"})], versions)
    item = _live(report)[0]
    assert item.change_type == "content_changed"
    assert item.pit_grade == "trade_date_only"
    assert report.pit_grade == "trade_date_only"


def test_naive_recorded_at_without_offset_is_never_strict():
    """没有时区的时分秒不是可靠时刻：不能凭「字段非空」升 strict。"""
    versions = [
        _version(REF_A, "h1", "2026-09-01T18:00:00"),
        _version(REF_A, "h2", "2026-09-11T18:00:00"),
    ]
    report = _run([_binding({REF_A: "h1"})], versions)
    item = _live(report)[0]
    assert item.pit_grade == "trade_date_only"
    assert report.pit_grade == "trade_date_only"


def test_complete_fixture_truncated_to_dates_loses_strict_everywhere():
    payload = _load("complete")
    for group in ("evidence_versions", "condition_observations"):
        for row in payload[group]:
            if row.get("recorded_at"):
                row["recorded_at"] = row["recorded_at"][:10]
    report = _assess(payload)
    assert report.pit_grade != "strict"
    assert "strict" not in {it.pit_grade for it in report.items}

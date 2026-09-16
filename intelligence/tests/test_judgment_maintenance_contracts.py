"""判断持续维护 · 合同层测试（spec 01 §3 / §5；总合同 §5）。

未知版本 / 枚举 / 字段一律拒绝；owner 与引用的归属校验不泄露对方存在性；稳定摘要与顺序无关。
"""

from __future__ import annotations

import json

import pytest

from intelligence.services.judgment_maintenance import contracts as c

OWNER = "alice"


def _object_ref(**over):
    base = {
        "kind": "checkpoint",
        "id": "ck-2026-09-01-aaaaaa",
        "namespace": "checkpoints",
        "version_or_hash": "content_sha256:" + "a" * 64,
        "ref": "checkpoints.jsonl:ck-2026-09-01-aaaaaa",
        "scope": {"session_id": "s1"},
    }
    base.update(over)
    return base


def _binding(**over):
    base = {
        "schema_version": c.BINDING_SCHEMA_VERSION,
        "binding_id": "b1",
        "binding_version": 1,
        "owner_user_id": OWNER,
        "object_ref": _object_ref(),
        "baseline_evidence_refs": ["fact_market_daily:2026-09-01"],
        "baseline_source_hashes": {"fact_market_daily:2026-09-01": "h1"},
        "baseline_cutoff": "2026-09-05",
        "created_at": "2026-09-05T20:00:00+08:00",
        "binding_origin": "user_confirmed",
        "conditions": [],
    }
    base.update(over)
    return base


def _err(fn, *args, **kwargs) -> c.MaintenanceContractError:
    with pytest.raises(c.MaintenanceContractError) as info:
        fn(*args, **kwargs)
    return info.value


class TestSchemaAndEnums:
    def test_unknown_schema_version_rejected(self):
        err = _err(c.parse_binding, _binding(schema_version="judgment-maintenance-binding/v0"), owner_user_id=OWNER, where="b")
        assert err.code == "unknown_schema_version"

    def test_missing_binding_schema_version_rejected(self):
        raw = _binding()
        del raw["schema_version"]
        assert _err(c.parse_binding, raw, owner_user_id=OWNER, where="b").code == "unknown_schema_version"

    def test_unknown_enum_rejected(self):
        assert _err(c.parse_binding, _binding(binding_origin="guessed"), owner_user_id=OWNER, where="b").code == "unknown_enum"
        assert _err(c.parse_object_ref, _object_ref(kind="theme"), owner_user_id=OWNER, where="o").code == "unknown_enum"
        cond = {"condition_id": "c", "role": "maybe", "expression": {"all": []}}
        assert _err(c.parse_condition, cond, where="c").code == "unknown_enum"

    def test_unknown_field_rejected(self):
        assert _err(c.parse_binding, _binding(extra_field=1), owner_user_id=OWNER, where="b").code == "unknown_field"
        assert _err(c.parse_policy, {"schema_version": c.POLICY_SCHEMA_VERSION, "typo": True}).code == "unknown_field"
        version = {"ref": "fact_market_daily:2026-09-01", "source_hash": "h", "note": "x"}
        assert _err(c.parse_evidence_version, version, owner_user_id=OWNER, where="v").code == "unknown_field"

    def test_policy_unknown_version_and_default(self):
        assert _err(c.parse_policy, {"schema_version": "policy/v9"}).code == "unknown_schema_version"
        assert c.parse_policy(None) == c.MaintenancePolicy()
        assert c.parse_policy({"schema_version": c.POLICY_SCHEMA_VERSION, "emit_unchanged": True}).emit_unchanged is True


class TestOwnerAndRefs:
    @pytest.mark.parametrize("bad", ["", "../alice", "a/b", ".", "..", "al\\ice", " ", "-lead", "x" * 65])
    def test_forged_owner_rejected(self, bad):
        assert _err(c.validate_owner, bad, "owner").code == "invalid_owner"

    def test_binding_owner_must_match_verified_owner(self):
        err = _err(c.parse_binding, _binding(owner_user_id="bob"), owner_user_id=OWNER, where="b")
        assert err.code == "owner_mismatch"
        assert "bob" not in err.detail

    def test_foreign_user_ref_rejected_without_leaking_id(self):
        err = _err(c.validate_ref, "users/bob/judgments.jsonl:j-1", owner_user_id=OWNER, where="ref")
        assert err.code == "foreign_user_ref"
        assert "bob" not in str(err)
        # 自己目录下的引用可以
        assert c.validate_ref("users/alice/judgments.jsonl:j-1", owner_user_id=OWNER, where="ref")

    @pytest.mark.parametrize("bad", ["/etc/passwd", "~/x", "a/../b", "a/..", "has space", "a\\b", "", "\x00x"])
    def test_path_traversal_and_junk_refs_rejected(self, bad):
        assert _err(c.validate_ref, bad, owner_user_id=OWNER, where="ref").code == "invalid_ref"

    def test_chinese_entity_refs_allowed(self):
        assert c.validate_ref("fact_theme_limit_heat_daily:2026-09-01:半导体", owner_user_id=OWNER, where="ref")


class TestBindingRules:
    def test_binding_without_refs_rejected(self):
        raw = _binding(baseline_evidence_refs=[], baseline_source_hashes={})
        assert _err(c.parse_binding, raw, owner_user_id=OWNER, where="b").code == "binding_without_refs"

    def test_hash_must_be_declared_even_if_null(self):
        raw = _binding(baseline_source_hashes={})
        assert _err(c.parse_binding, raw, owner_user_id=OWNER, where="b").code == "hash_not_declared"
        ok = c.parse_binding(_binding(baseline_source_hashes={"fact_market_daily:2026-09-01": None}), owner_user_id=OWNER, where="b")
        assert ok.baseline_source_hashes == {"fact_market_daily:2026-09-01": None}

    def test_hash_for_undeclared_ref_rejected(self):
        raw = _binding(baseline_source_hashes={"fact_market_daily:2026-09-01": "h1", "other:ref": "h2"})
        assert _err(c.parse_binding, raw, owner_user_id=OWNER, where="b").code == "hash_for_undeclared_ref"

    def test_baseline_cutoff_cannot_be_after_created_at(self):
        raw = _binding(baseline_cutoff="2026-09-06", created_at="2026-09-05T20:00:00+08:00")
        assert _err(c.parse_binding, raw, owner_user_id=OWNER, where="b").code == "baseline_cutoff_after_created_at"

    def test_dates_must_be_day_granularity(self):
        assert _err(c.validate_date, "2026-09-05T10:00:00", "as_of").code == "invalid_date"
        assert _err(c.validate_date, "2026-13-01", "as_of").code == "invalid_date"
        assert c.validate_stamp("2026-09-05", "ts") == "2026-09-05"
        assert c.validate_stamp("2026-09-05T10:00:00+08:00", "ts") == "2026-09-05T10:00:00+08:00"

    def test_evidence_version_requires_hash_unless_placeholder(self):
        raw = {"ref": "fact_market_daily:2026-09-01", "source_hash": None, "derivation": "unknown"}
        assert _err(c.parse_evidence_version, raw, owner_user_id=OWNER, where="v").code == "missing_field"
        placeholder = c.parse_evidence_version(raw, owner_user_id=OWNER, where="v", allow_placeholder=True)
        assert placeholder.source_hash is None and placeholder.derivation == "unknown"
        deterministic = dict(raw, derivation="deterministic")
        assert _err(c.parse_evidence_version, deterministic, owner_user_id=OWNER, where="v", allow_placeholder=True).code == "missing_field"

    def test_observation_requires_explicit_value(self):
        assert _err(c.parse_observation, {"label": "market_stage", "as_of": "2026-09-12"}, owner_user_id=OWNER, where="o").code == "missing_field"
        obs = c.parse_observation({"label": "market_stage", "as_of": "2026-09-12", "value": None}, owner_user_id=OWNER, where="o")
        assert obs.value is None
        assert _err(c.parse_observation, {"label": "x", "as_of": "2026-09-12", "value": {"a": 1}}, owner_user_id=OWNER, where="o").code == "invalid_type"


class TestDigestsAndRoundTrip:
    def test_canonical_json_ignores_key_order(self):
        a = {"b": 1, "a": {"y": [1, 2], "x": "中"}}
        b = {"a": {"x": "中", "y": [1, 2]}, "b": 1}
        assert c.canonical_json(a) == c.canonical_json(b)
        assert c.sha256_hex(a) == c.sha256_hex(b)
        assert len(c.short_hash(a)) == 16

    def test_weakest_pit_fails_closed_on_empty(self):
        assert c.weakest_pit([]) == "unverifiable"
        assert c.weakest_pit(["strict", "trade_date_only"]) == "trade_date_only"
        assert c.weakest_pit(["strict", "strict"]) == "strict"
        assert c.weakest_pit(["strict", "unverifiable", "trade_date_only"]) == "unverifiable"

    def test_command_payload_digest_excludes_command_id_and_time(self):
        base = {
            "command_id": "cmd-1",
            "item_id": "jmi-x",
            "owner_user_id": OWNER,
            "expected_item_version": "v1",
            "expected_management_revision": 0,
            "action": "claim",
            "acted_at": "2026-09-13T09:00:00+08:00",
        }
        a = c.parse_command(base, owner_user_id=OWNER)
        b = c.parse_command(dict(base, command_id="cmd-2", acted_at="2026-09-13T09:05:00+08:00"), owner_user_id=OWNER)
        d = c.parse_command(dict(base, action="rejudge"), owner_user_id=OWNER)
        assert a.payload_digest() == b.payload_digest()
        assert a.payload_digest() != d.payload_digest()

    def test_report_round_trip_via_json(self):
        gap = c.Gap("ref_unresolved", "fact_market_daily:2026-09-01", "2026-09-12", True, "x", "b1", None)
        item = c.MaintenanceItem(
            id="jmi-1",
            item_version="v",
            owner_user_id=OWNER,
            object_ref=c.parse_object_ref(_object_ref(), owner_user_id=OWNER, where="o"),
            before=(c.EvidenceVersion(ref="fact_market_daily:2026-09-01", source_hash=None, derivation="unknown"),),
            current=(),
            change_type="dependency_missing",
            reason_code="dependency_unbound",
            epistemic_state="unknown",
            condition_result=None,
            as_of="2026-09-12",
            knowledge_cutoff="2026-09-12",
            pit_grade="unverifiable",
            gaps=(gap,),
            action="restore_evidence",
            status="open",
            dedup_key="{}",
            binding_id="b1",
            binding_version=1,
            dependency_ref="fact_market_daily:2026-09-01",
            first_known_day="2026-09-12",
        )
        report = c.MaintenanceReport(
            id="jmr-1",
            owner_user_id=OWNER,
            as_of="2026-09-12",
            knowledge_cutoff="2026-09-12",
            input_digest="d",
            generated_at="2026-09-13T00:00:00+00:00",
            pit_grade="unverifiable",
            hindsight=False,
            gaps=(gap,),
            items=(item,),
            counts={k: 1 for k in c.COUNT_KEYS},
        )
        dumped = json.loads(json.dumps(report.to_dict(), ensure_ascii=False))
        assert c.parse_report(dumped).to_dict() == report.to_dict()
        assert _err(c.parse_report, dict(dumped, counts={"objects_seen": 1})).code == "invalid_type"
        foreign = json.loads(json.dumps(report.to_dict()))
        foreign["items"][0]["owner_user_id"] = "bob"
        assert _err(c.parse_report, foreign).code == "owner_mismatch"

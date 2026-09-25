from __future__ import annotations

from scripts import verify_user_memory_consumption as probe


def test_offline_memory_consumption_probe_is_scoped_and_passes() -> None:
    report = probe.verify()
    assert report["status"] == "PASS"
    assert report["scope"] == (
        "temporary_ledger_writer_to_prime_and_memory_lookup; "
        "no_workbench_ingest_no_model_no_real_user_state"
    )
    assert report["alice_before_withdrawal"]["evidence_count"] == 1
    assert report["alice_cli_prime_before_withdrawal"]["corrections_present"] is True
    assert report["bob_cross_user_control"]["evidence_count"] == 0
    assert report["bob_cli_prime_control"]["corrections_present"] is False
    assert report["alice_after_withdrawal"]["evidence_count"] == 0
    assert report["alice_cli_prime_after_withdrawal"]["corrections_present"] is False
    assert report["missing_identity"] == {"memory_lookup_registered": False}
    assert report["inputs_unchanged"] is True


def test_probe_does_not_emit_private_correction_text() -> None:
    report = probe.verify()
    serialized = str(report)
    assert "先看客户验证再谈弹性" not in serialized
    assert "验证进度优先于产能规划" not in serialized
    assert "users/" not in serialized

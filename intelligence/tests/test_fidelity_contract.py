from __future__ import annotations

from copy import deepcopy

from intelligence.eval.fidelity_replay import validate_answer_claims
from intelligence.services.fidelity_contract import (
    build_claim_manifest_metadata,
    public_narratives,
    provenance_marker,
    rendered_output_errors,
    report_manifest_payload,
    seal_artifact,
    validate_daily_agent_report,
)


def _valid_report() -> dict[str, object]:
    generated_at = "2026-07-10T20:05:00+08:00"
    report: dict[str, object] = {
        "date": "2026-07-10",
        "generated_at": generated_at,
        "ledger": {"status": "PASS"},
        "logic_batch": {"summary": {"candidate_count": 1}},
        "decision": {"old_logic_wakeup": [{"query": "液冷服务器"}]},
        "notes": ["只使用 cutoff 前证据。"],
        "next_actions": ["等待下一交易日前向验证。"],
        "lineage_schema_version": "claim-lineage-v1",
        "evidence_catalog": {
            "ev-1": {
                "scope": "claim",
                "source": "fixture",
                "field": "pct_chg",
                "valid_time": "2026-07-10",
                "source_time": "2026-07-10T18:00:00+08:00",
            }
        },
        "input_artifacts": [
            {
                "artifact_kind": "theme-candidates",
                "contract_valid": True,
                "run_id": "theme-run",
                "artifact_sha": "b" * 64,
                "manifest_sha": "c" * 64,
            }
        ],
    }
    claims = [
        {
            "claim_id": "claim-evidence",
            "manifest_scope": "evidence_fact",
            "text": "液冷服务器 pct_chg = 2.4",
            "claim_type": "number",
            "expected_type": "numeric_fact",
            "subject": "液冷服务器",
            "predicate": "pct_chg",
            "value": 2.4,
            "valid_time": "2026-07-10",
            "evidence_refs": ["ev-1"],
        }
    ]
    claims.extend(
        {
            "claim_id": f"claim-{item['narrative_key'][:20]}",
            "manifest_scope": "public_narrative",
            "narrative_key": item["narrative_key"],
            "location": item["location"],
            "text": item["text"],
            "claim_type": "fact",
            "expected_type": "factual_statement",
            "subject": "",
            "predicate": item["location"],
            "value": item["value"],
            "valid_time": "2026-07-10",
            "evidence_refs": [],
        }
        for item in public_narratives(report)
    )
    report["claims"] = claims
    report["claim_manifest"] = build_claim_manifest_metadata(report, claims)
    seal_artifact(
        report,
        artifact_kind="daily-agent",
        report_date="2026-07-10",
        generator_commit="a" * 40,
        snapshot_captured_at="2026-07-10T18:30:00+08:00",
        report_generated_at=generated_at,
        manifest_payload=report_manifest_payload(report),
    )
    return report


def test_valid_contract_and_output_markers() -> None:
    report = _valid_report()
    marker = provenance_marker(report)

    assert validate_daily_agent_report(report) == []
    assert rendered_output_errors(
        report,
        markdown=f"# report\n\n<!-- {marker} -->\n",
        html=(
            '<html><head><meta name="fidelity-contract" '
            f'content="{marker}"></head></html>'
        ),
    ) == []


def test_missing_contract_fields_fail() -> None:
    report = _valid_report()
    report.pop("report_generated_at")

    assert "missing report_generated_at" in validate_daily_agent_report(report)


def test_evidence_cutoff_after_decision_cutoff_fails() -> None:
    report = _valid_report()
    report["evidence_cutoff"] = "2026-07-10T20:06:00+08:00"

    assert (
        "evidence_cutoff is after decision_cutoff"
        in validate_daily_agent_report(report)
    )


def test_generated_timestamp_mismatch_fails() -> None:
    report = _valid_report()
    report["generated_at"] = "2026-07-10T20:04:00+08:00"

    assert (
        "generated_at does not match report_generated_at"
        in validate_daily_agent_report(report)
    )


def test_snapshot_capture_after_report_generation_fails() -> None:
    report = _valid_report()
    report["snapshot_captured_at"] = "2026-07-10T20:06:00+08:00"

    errors = validate_daily_agent_report(report)

    assert "snapshot_captured_at is after report_generated_at" in errors
    assert "manifest_sha mismatch" in errors


def test_generator_commit_missing_and_mismatch_fail() -> None:
    report = _valid_report()
    report.pop("generator_commit")
    assert "missing generator_commit" in validate_daily_agent_report(report)

    report = _valid_report()
    assert (
        "generator_commit mismatch"
        in validate_daily_agent_report(
            report,
            expected_generator_commit="d" * 40,
        )
    )


def test_artifact_and_manifest_tampering_fail() -> None:
    artifact = _valid_report()
    artifact["notes"] = ["tampered"]
    assert "artifact_sha mismatch" in validate_daily_agent_report(artifact)

    manifest = _valid_report()
    manifest["manifest_sha"] = "0" * 64
    assert "manifest_sha mismatch" in validate_daily_agent_report(manifest)


def test_unmanifested_narrative_and_dangling_evidence_fail() -> None:
    narrative = _valid_report()
    narrative["next_actions"] = ["新增且未进入 manifest 的叙述"]
    assert (
        "1 public narratives missing from claim manifest"
        in validate_daily_agent_report(narrative)
    )

    evidence = _valid_report()
    evidence["claims"][0]["evidence_refs"] = ["ev-missing"]
    assert (
        "claim-evidence references missing evidence ev-missing"
        in validate_daily_agent_report(evidence)
    )

    payload = _valid_report()
    public_claim = next(
        claim
        for claim in payload["claims"]
        if claim.get("manifest_scope") == "public_narrative"
    )
    public_claim["text"] = "tampered"
    assert any(
        error.endswith("narrative payload mismatch")
        for error in validate_daily_agent_report(payload)
    )


def test_source_time_after_evidence_cutoff_fails() -> None:
    report = _valid_report()
    report["evidence_catalog"]["ev-1"]["source_time"] = (
        "2026-07-10T20:06:00+08:00"
    )

    assert (
        "evidence ev-1 is after evidence_cutoff"
        in validate_daily_agent_report(report)
    )


def test_markdown_and_html_provenance_mismatch_fail() -> None:
    report = _valid_report()

    errors = rendered_output_errors(
        report,
        markdown="<!-- wrong -->",
        html='<meta name="fidelity-contract" content="wrong">',
    )

    assert errors == [
        "markdown provenance marker mismatch",
        "html provenance marker mismatch",
    ]


def test_rendered_content_must_match_canonical_report() -> None:
    report = _valid_report()
    marker = provenance_marker(report)

    errors = rendered_output_errors(
        report,
        markdown=f"tampered\n<!-- {marker} -->",
        html=(
            '<meta name="fidelity-contract" '
            f'content="{marker}">'
        ),
        expected_markdown=f"canonical\n<!-- {marker} -->",
    )

    assert errors == ["markdown content does not match canonical report"]


def test_invalid_input_artifact_blocks_daily_contract() -> None:
    report = deepcopy(_valid_report())
    report["input_artifacts"][0]["contract_valid"] = False

    assert (
        "input_artifacts[0] contract invalid"
        in validate_daily_agent_report(report)
    )


def test_replay_answer_validation_enforces_contract() -> None:
    valid = _valid_report()
    assert not any(
        error.startswith("fidelity contract:")
        for error in validate_answer_claims(valid)
    )

    tampered = _valid_report()
    tampered["artifact_sha"] = "0" * 64
    assert (
        "fidelity contract: artifact_sha mismatch"
        in validate_answer_claims(tampered)
    )

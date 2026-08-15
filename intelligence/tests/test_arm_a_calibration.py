"""第 8 步先半段：Arm A 校准收据。不跑 live，不连 dsh。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.eval.arm_a_calibration import (
    ARM_A_BACKEND,
    ArmACalibrationError,
    EXPECTED_MODEL,
    FROZEN_NINE_CASE_IDS,
    THRESHOLD_PP,
    evidence_bound_rate,
    form_calibration_receipt,
    inspect_runtime_env,
    key_fingerprint,
    projected_ci_half_width,
    reject_forbidden_cli,
    required_nr,
)
from scripts import run_agent_runtime_benchmark as benchmark
from scripts import run_arm_a_calibration as calibration_cli

FIXTURE = Path(__file__).parent / "fixtures" / "runtime_backend_cases.json"


def _binding(*, hashes: list[str], gap: str = "") -> dict[str, object]:
    return {
        "output_id": "direct_assessment",
        "evidence_hashes": hashes,
        "gap": gap,
        "basis": "evidence",
    }


def _arm(
    *,
    case_id: str,
    rate_bound: int,
    rate_total: int = 2,
    model: str = EXPECTED_MODEL,
) -> dict[str, object]:
    bindings = [
        _binding(hashes=["a" * 64] if index < rate_bound else [], gap="" if index < rate_bound else "missing")
        for index in range(rate_total)
    ]
    return {
        "case_id": case_id,
        "backend": ARM_A_BACKEND,
        "model": model,
        "semantic_status": "passed" if rate_bound == rate_total else "rejected",
        "diagnostics": {"bindings": bindings},
    }


def _live_artifact(arms_by_case: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        "mode": "live",
        "expected_backends": [ARM_A_BACKEND],
        "credential_source": "environment",
        "cases": [
            {"id": case_id, "arms": [arm]} for case_id, arm in arms_by_case.items()
        ],
    }


def test_evidence_bound_rate_counts_hash_and_gap() -> None:
    arm = _arm(case_id="current-mainline", rate_bound=1, rate_total=2)
    assert evidence_bound_rate(arm) == 0.5
    assert evidence_bound_rate({"diagnostics": {"bindings": []}}) == 0.0


def test_fingerprint_does_not_echo_secret() -> None:
    digest = key_fingerprint("super-secret-relay-key")
    assert digest != "super-secret-relay-key"
    assert len(digest) == 16
    with pytest.raises(ValueError, match="empty"):
        key_fingerprint("")


def test_env_rejects_dead_gateway_and_retired_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:57244/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("FORESIGHT_LLM_KEYCHAIN", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    inspected = inspect_runtime_env()
    assert "dead_cockpit_gateway" in inspected["issues"]
    assert "retired_model" in inspected["issues"]
    assert "foresight_llm_keychain_enabled" in inspected["issues"]
    assert inspected["openai_api_key_fingerprint"] != "sk-test"
    assert "sk-test" not in json.dumps(inspected)


def test_cli_markers_are_rejected() -> None:
    with pytest.raises(ArmACalibrationError, match="keychain-user"):
        reject_forbidden_cli(["--questions-file", "q.json", "--keychain-user", "x"])
    with pytest.raises(ArmACalibrationError, match="57244"):
        reject_forbidden_cli(["--output", "http://localhost:57244/v1"])


def test_receipt_refuses_second_backend() -> None:
    artifact = _live_artifact(
        {"current-mainline": _arm(case_id="current-mainline", rate_bound=2)}
    )
    artifact["expected_backends"] = [ARM_A_BACKEND, "sdk_gpt"]
    with pytest.raises(ArmACalibrationError, match="Arm A only"):
        form_calibration_receipt(artifacts=[artifact], env={"issues": []})


def test_receipt_refuses_keychain_credential_source() -> None:
    artifact = _live_artifact(
        {"current-mainline": _arm(case_id="current-mainline", rate_bound=2)}
    )
    artifact["credential_source"] = "keychain"
    with pytest.raises(ArmACalibrationError, match="environment"):
        form_calibration_receipt(artifacts=[artifact], env={"issues": []})


def test_receipt_refuses_retired_model_in_artifact() -> None:
    artifact = _live_artifact(
        {
            "current-mainline": _arm(
                case_id="current-mainline",
                rate_bound=2,
                model="gpt-5.6-sol",
            )
        }
    )
    with pytest.raises(ArmACalibrationError, match="retired model"):
        form_calibration_receipt(artifacts=[artifact], env={"issues": []})


def test_zero_variance_uses_worst_case_and_cannot_resolve_5pp() -> None:
    artifacts = [
        _live_artifact(
            {case_id: _arm(case_id=case_id, rate_bound=2) for case_id in FROZEN_NINE_CASE_IDS}
        )
        for _ in range(5)
    ]
    receipt = form_calibration_receipt(artifacts=artifacts, env={"issues": []})
    assert receipt["variance_informative"] is False
    assert receipt["design_variance"] == 0.25
    assert receipt["projected"]["can_resolve_5pp"] is False
    assert receipt["threshold_pp"] == THRESHOLD_PP
    assert receipt["step8_ab_decision"]["retain_dsh_runtime"] is False
    assert receipt["step8_ab_decision"]["live_ab_ran"] is False
    assert receipt["next_action"] == "increase_n_or_repeats_do_not_loosen_threshold"
    assert receipt["official_window"] is True
    assert "/Users/" not in json.dumps(receipt)


def test_low_variance_can_resolve_projected_30x3() -> None:
    # 每题 5 次里 4 次 10/10、1 次 9/10 → 方差约 0.002，30×3 半宽 < 5pp。
    def artifact(flip: bool) -> dict[str, object]:
        bound = 9 if flip else 10
        return _live_artifact(
            {
                case_id: _arm(case_id=case_id, rate_bound=bound, rate_total=10)
                for case_id in FROZEN_NINE_CASE_IDS
            }
        )

    artifacts = [artifact(False), artifact(False), artifact(True), artifact(False), artifact(False)]
    receipt = form_calibration_receipt(artifacts=artifacts, env={"issues": []})
    assert receipt["variance_informative"] is True
    assert receipt["projected"]["can_resolve_5pp"] is True
    assert receipt["next_action"] == "expand_to_thirty_then_ab"
    assert receipt["step8_ab_decision"]["retain_dsh_runtime"] is False


def test_fast_path_is_excluded_from_sigma() -> None:
    llm = _arm(case_id="current-mainline", rate_bound=2)
    fast = _arm(
        case_id="index-rebound-space",
        rate_bound=2,
        model="deterministic_fast_path",
    )
    artifact = _live_artifact(
        {"current-mainline": llm, "index-rebound-space": fast}
    )
    receipt = form_calibration_receipt(
        artifacts=[artifact, artifact],
        env={"issues": []},
    )
    assert receipt["excluded_from_sigma"] == ["index-rebound-space"]
    assert "index-rebound-space" not in {
        row["case_id"] for row in receipt["case_stats"]
    }


def test_dry_run_receipt_does_not_claim_sigma() -> None:
    artifact = {
        "mode": "dry_run",
        "expected_backends": [ARM_A_BACKEND],
        "credential_source": "environment",
        "cases": [{"id": "current-mainline", "execution_status": "planned"}],
    }
    receipt = form_calibration_receipt(
        artifacts=[artifact, artifact],
        env={"issues": []},
    )
    assert receipt["live_ran"] is False
    assert receipt["official_window"] is False
    assert receipt["next_action"] == "run_live_calibration"
    assert "pooled_variance" not in receipt
    assert receipt["step8_ab_decision"]["live_ab_ran"] is False


def test_projected_half_width_matches_the_5pp_formula() -> None:
    half = projected_ci_half_width(0.25, question_count=30, repeats=3)
    assert half == pytest.approx(1.96 * (0.5 / 90) ** 0.5)
    assert required_nr(0.25) == pytest.approx(2.0 * 0.25 / (0.05 / 1.96) ** 2)


def test_runner_dry_run_writes_receipt_without_executing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        benchmark,
        "_run_runtime_arm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not execute a runtime")
        ),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://x.ailzd.com/v1")
    monkeypatch.setenv("LLM_MODEL", EXPECTED_MODEL)
    monkeypatch.setenv("FORESIGHT_LLM_KEYCHAIN", "0")
    output_dir = tmp_path / "cal"
    code = calibration_cli.main(
        [
            "--dry-run",
            "--repeats",
            "2",
            "--questions-file",
            str(FIXTURE),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert code == 0
    receipt = json.loads(
        (output_dir / "arm-a-calibration-receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["mode"] == "dry_run"
    assert receipt["repeat_count"] == 2
    assert receipt["step8_ab_decision"]["retain_dsh_runtime"] is False
    assert (output_dir / "arm-a-cal-r1.json").is_file()
    assert (output_dir / "arm-a-cal-r2.json").is_file()


def test_runner_rejects_keychain_user(tmp_path: Path) -> None:
    code = calibration_cli.main(
        [
            "--dry-run",
            "--questions-file",
            str(FIXTURE),
            "--output-dir",
            str(tmp_path),
            "--keychain-user",
            "linxiaoqi5111",
        ]
    )
    assert code == 2

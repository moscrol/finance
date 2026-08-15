"""第 8 步先半段：冻结九题 × 5 纯 Arm A 校准，不算对照。

来源：Step 1 收据 §3.2 / §6.1；spec §9.4、§11 第 8 步。

--------------------------------------------------------------------------
这一步是什么 / 不是什么
--------------------------------------------------------------------------

第 8 步的硬顺序是：先量 Arm A 自己的重复噪声，再扩到 30 题，再上 Arm B。
本模块只做第一段——从已有 ``run_agent_runtime_benchmark`` 产物里抽出
evidence-bound rate，估计单次方差，再投影 30×3 配对设计能不能压住 5pp。

本模块**不**做的事：

- 不跑 Arm B，不 import dsh，不注入 ``DSH_AB_RELAY_KEY``（那是 dsh 子进程
  的专用变量；Arm A 走生产同一条 ``OPENAI_API_KEY`` env 链）；
- 不接受 ``--keychain-user`` / ``localhost:57244`` / ``gpt-5.6-sol``；
- 不把门槛改成函数参数——5pp 是裁定，不是旋钮；
- 不把 ``retain_dsh_runtime`` 写成 true。校准不是对照。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import math
import os
from typing import Any


FROZEN_NINE_CASE_IDS: tuple[str, ...] = (
    "rebound-duration",
    "index-rebound-space",
    "ruihuatai-valuation",
    "weekly-market-cause",
    "current-mainline",
    "theme-comparison",
    "counterfactual-mainline",
    "unfamiliar-methodology",
    "contextual-follow-up",
)

ARM_A_BACKEND = "continuous_glm"
PRIMARY_METRIC = "evidence_bound_rate"
THRESHOLD_PP = 5.0
THRESHOLD_RATE = THRESHOLD_PP / 100.0
Z_95 = 1.96
DESIGN_QUESTION_COUNT = 30
DESIGN_REPEATS = 3
OFFICIAL_REPEATS = 5
WORST_CASE_BERNOULLI_VARIANCE = 0.25
EXPECTED_MODEL = "gpt-5.6-terra"
FAST_PATH_MODEL = "deterministic_fast_path"
FORBIDDEN_MODEL = "gpt-5.6-sol"
FORBIDDEN_GATEWAY_MARKER = "localhost:57244"
FORBIDDEN_CLI_MARKERS: tuple[str, ...] = (
    "--keychain-user",
    FORBIDDEN_GATEWAY_MARKER,
    FORBIDDEN_MODEL,
)


class ArmACalibrationError(ValueError):
    """校准收据的输入不满足生产对齐或九题窗口。"""


def key_fingerprint(raw_key: str) -> str:
    """artifact 只记指纹。空串拒绝，避免把「没 key」写成合法指纹。"""

    secret = str(raw_key or "")
    if not secret:
        raise ValueError("key is empty")
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]


def _host_of(url: str) -> str:
    text = str(url or "").strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    return text.split("/", 1)[0]


def inspect_runtime_env() -> dict[str, object]:
    """读当前进程的生产对齐项。不回传 key 原文。"""

    url = str(os.environ.get("LLM_BASE_URL") or "").strip()
    model = str(os.environ.get("LLM_MODEL") or "").strip()
    keychain_flag = str(os.environ.get("FORESIGHT_LLM_KEYCHAIN") or "").strip()
    raw_key = str(os.environ.get("OPENAI_API_KEY") or "")
    issues: list[str] = []
    if FORBIDDEN_GATEWAY_MARKER in url:
        issues.append("dead_cockpit_gateway")
    if model == FORBIDDEN_MODEL:
        issues.append("retired_model")
    if keychain_flag not in {"", "0"}:
        issues.append("foresight_llm_keychain_enabled")
    fingerprint = key_fingerprint(raw_key) if raw_key.strip() else ""
    return {
        "llm_base_host": _host_of(url),
        "llm_model": model,
        "openai_api_key_present": bool(raw_key.strip()),
        "openai_api_key_fingerprint": fingerprint,
        "foresight_llm_keychain": keychain_flag or "0",
        "issues": issues,
    }


def reject_forbidden_cli(argv: Sequence[str]) -> None:
    for token in argv:
        for marker in FORBIDDEN_CLI_MARKERS:
            if marker in token:
                raise ArmACalibrationError(
                    f"calibration refuses {marker!r}; use production env"
                )


def evidence_bound_rate(arm: Mapping[str, Any]) -> float:
    diagnostics = arm.get("diagnostics")
    bindings: Sequence[Any] = ()
    if isinstance(diagnostics, Mapping):
        raw = diagnostics.get("bindings")
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            bindings = raw
    if not bindings:
        return 0.0
    bound = 0
    for item in bindings:
        if not isinstance(item, Mapping):
            continue
        hashes = item.get("evidence_hashes") or ()
        gap = str(item.get("gap") or "").strip()
        if hashes and not gap:
            bound += 1
    return bound / len(bindings)


def semantic_accept(arm: Mapping[str, Any]) -> float:
    return 1.0 if arm.get("semantic_status") in {"passed", "repaired"} else 0.0


def _sample_variance(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return sum((item - mean) ** 2 for item in values) / (len(values) - 1)


def projected_ci_half_width(
    variance: float,
    *,
    question_count: int = DESIGN_QUESTION_COUNT,
    repeats: int = DESIGN_REPEATS,
) -> float:
    if variance < 0:
        raise ArmACalibrationError("variance must be non-negative")
    if question_count <= 0 or repeats <= 0:
        raise ArmACalibrationError("design size must be positive")
    return Z_95 * math.sqrt(2.0 * variance / (question_count * repeats))


def required_nr(variance: float) -> float:
    """使 95% CI 半宽 < 5pp 所需的 n×r（配对、两臂噪声相当）。"""

    if variance < 0:
        raise ArmACalibrationError("variance must be non-negative")
    return 2.0 * variance / (THRESHOLD_RATE / Z_95) ** 2


def _arm_rows(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cases = artifact.get("cases")
    if not isinstance(cases, Sequence):
        raise ArmACalibrationError("artifact cases must be a list")
    for case in cases:
        if not isinstance(case, Mapping):
            raise ArmACalibrationError("artifact case must be an object")
        case_id = str(case.get("id") or case.get("case_id") or "").strip()
        arms = case.get("arms")
        if not isinstance(arms, Sequence) or isinstance(arms, (str, bytes)):
            continue
        for arm in arms:
            if not isinstance(arm, Mapping):
                raise ArmACalibrationError("artifact arm must be an object")
            rows.append({"case_id": case_id, **dict(arm)})
    return rows


def _validate_live_artifact(artifact: Mapping[str, Any]) -> None:
    backends = artifact.get("expected_backends")
    if list(backends or ()) != [ARM_A_BACKEND]:
        raise ArmACalibrationError("calibration is Arm A only (continuous_glm)")
    if artifact.get("credential_source") != "environment":
        raise ArmACalibrationError("credential_source must be environment")
    if artifact.get("mode") != "live":
        raise ArmACalibrationError("live calibration requires mode=live")


def form_calibration_receipt(
    *,
    artifacts: Sequence[Mapping[str, Any]],
    env: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """从 5 份单次 benchmark 产物合成校准收据。不写家目录，不写 key。"""

    if not artifacts:
        raise ArmACalibrationError("calibration needs at least one artifact")
    resolved_env = dict(env) if env is not None else inspect_runtime_env()
    modes = {str(item.get("mode") or "") for item in artifacts}
    if modes == {"dry_run"}:
        return {
            "schema_version": 1,
            "gate": "arm_a_calibration",
            "mode": "dry_run",
            "official_window": False,
            "live_ran": False,
            "primary_metric": PRIMARY_METRIC,
            "threshold_pp": THRESHOLD_PP,
            "repeat_count": len(artifacts),
            "env": resolved_env,
            "step8_ab_decision": {
                "retain_dsh_runtime": False,
                "reason": "calibration_only_live_ab_not_run",
                "live_ab_ran": False,
            },
            "next_action": "run_live_calibration",
        }
    if modes != {"live"}:
        raise ArmACalibrationError("artifacts must be all live or all dry_run")

    per_case: dict[str, list[float]] = {}
    observed_ids: list[str] = []
    excluded: list[str] = []
    resolved_models: set[str] = set()
    for artifact in artifacts:
        _validate_live_artifact(artifact)
        for arm in _arm_rows(artifact):
            case_id = str(arm.get("case_id") or "").strip()
            if case_id and case_id not in observed_ids:
                observed_ids.append(case_id)
            backend = str(arm.get("backend") or "").strip()
            if backend != ARM_A_BACKEND:
                raise ArmACalibrationError(f"unexpected backend {backend!r}")
            model = str(arm.get("model") or "").strip()
            if model == FAST_PATH_MODEL:
                if case_id not in excluded:
                    excluded.append(case_id)
                continue
            if model:
                resolved_models.add(model)
            per_case.setdefault(case_id, []).append(evidence_bound_rate(arm))

    if FORBIDDEN_MODEL in resolved_models:
        raise ArmACalibrationError("artifact resolved retired model gpt-5.6-sol")

    weights = 0
    weighted = 0.0
    case_stats: list[dict[str, object]] = []
    for case_id, values in per_case.items():
        variance = _sample_variance(values)
        mean = sum(values) / len(values) if values else 0.0
        case_stats.append(
            {
                "case_id": case_id,
                "n": len(values),
                "mean": mean,
                "variance": variance,
            }
        )
        if variance is not None:
            df = len(values) - 1
            weights += df
            weighted += df * variance

    pooled = (weighted / weights) if weights else None
    informative = pooled is not None and pooled > 0.0
    design_variance = pooled if informative else WORST_CASE_BERNOULLI_VARIANCE
    half_width = projected_ci_half_width(design_variance)
    needed_nr = required_nr(design_variance)
    can_resolve = informative and half_width < THRESHOLD_RATE
    official = (
        len(artifacts) == OFFICIAL_REPEATS
        and tuple(observed_ids) == FROZEN_NINE_CASE_IDS
        and not list(resolved_env.get("issues") or ())
        and (not resolved_models or resolved_models <= {EXPECTED_MODEL, "unavailable"})
    )
    env_issues = list(resolved_env.get("issues") or ())
    if env_issues:
        next_action = "fix_production_alignment"
    elif can_resolve:
        next_action = "expand_to_thirty_then_ab"
    else:
        next_action = "increase_n_or_repeats_do_not_loosen_threshold"

    return {
        "schema_version": 1,
        "gate": "arm_a_calibration",
        "mode": "live",
        "official_window": official,
        "live_ran": True,
        "primary_metric": PRIMARY_METRIC,
        "threshold_pp": THRESHOLD_PP,
        "repeat_count": len(artifacts),
        "case_ids": list(observed_ids),
        "excluded_from_sigma": excluded,
        "resolved_models": sorted(resolved_models),
        "case_stats": case_stats,
        "pooled_variance": pooled,
        "variance_informative": informative,
        "design_variance": design_variance,
        "design_variance_source": (
            "pooled_repeats" if informative else "worst_case_bernoulli_0.25"
        ),
        "sigma_d_proxy": math.sqrt(2.0 * design_variance),
        "projected": {
            "question_count": DESIGN_QUESTION_COUNT,
            "repeats": DESIGN_REPEATS,
            "ci95_half_width": half_width,
            "required_nr": needed_nr,
            "can_resolve_5pp": can_resolve,
        },
        "env": dict(resolved_env),
        "step8_ab_decision": {
            "retain_dsh_runtime": False,
            "reason": "calibration_only_live_ab_not_run",
            "live_ab_ran": False,
        },
        "next_action": next_action,
    }


__all__ = [
    "ARM_A_BACKEND",
    "ArmACalibrationError",
    "EXPECTED_MODEL",
    "FORBIDDEN_CLI_MARKERS",
    "FROZEN_NINE_CASE_IDS",
    "OFFICIAL_REPEATS",
    "THRESHOLD_PP",
    "evidence_bound_rate",
    "form_calibration_receipt",
    "inspect_runtime_env",
    "key_fingerprint",
    "projected_ci_half_width",
    "reject_forbidden_cli",
    "required_nr",
    "semantic_accept",
]

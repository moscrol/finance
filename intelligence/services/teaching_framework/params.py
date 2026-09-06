"""Versioned teaching-framework parameter loading.

Parameters are data, not Python constants.  Parsing JSON first and hashing a
canonical representation makes whitespace, key order, and trailing-newline
changes irrelevant while still making every numerical change a new framework
version.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PARAMS_PATH = REPO_ROOT / "methodology" / "teaching" / "index_stage_params.v0.1.json"
_HH_MM = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

# These keys are the stable contract consumed by the first teaching slice.
# Builders may add keys in later versions, but a v0.1 file cannot silently
# omit a threshold and fall back to an implementation default.
REQUIRED_KEYS = (
    "framework_version_base",
    "week_ma_col",
    "deviation_bands",
    "volume_surge",
    "shrink_day",
    "shrink_streak_min",
    "mainline_amount_stepping_up_days",
    "mainline_share_basis",
    "mainline_definitions",
    "instant_seal_time",
    "rebound_window_days",
    "high_turnover_ratio",
    "amount_unit_policy",
    "top100_n",
    "min_n",
)


def canonical_json(value: Any) -> str:
    """Return stable JSON suitable for hashing and receipt storage."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_hh_mm(value: Any, path: str) -> None:
    if isinstance(value, str) and ("time" in path.lower() or path.lower().endswith("_at")):
        if not _HH_MM.fullmatch(value):
            raise ValueError(f"{path} 必须是 HH:MM（得到 {value!r}）")
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_hh_mm(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            _validate_hh_mm(item, f"{path}[{idx}]")


def validate_params(params: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ValueError("参数文件根必须是 JSON object")
    missing = [key for key in REQUIRED_KEYS if key not in params]
    if missing:
        raise ValueError(f"参数文件缺少必需字段: {', '.join(missing)}")
    version = params["framework_version_base"]
    if not isinstance(version, str) or not version.startswith("tf-v"):
        raise ValueError("framework_version_base 必须是形如 tf-v0.1 的字符串")
    if not isinstance(params["rebound_window_days"], int) or params["rebound_window_days"] <= 0:
        raise ValueError("rebound_window_days 必须是正整数")
    if not isinstance(params["top100_n"], int) or params["top100_n"] <= 0:
        raise ValueError("top100_n 必须是正整数")
    if not isinstance(params["mainline_definitions"], list) or not params["mainline_definitions"]:
        raise ValueError("mainline_definitions 必须是非空数组")
    if params["high_turnover_ratio"] is not None and (
        not isinstance(params["high_turnover_ratio"], (int, float)) or params["high_turnover_ratio"] <= 0
    ):
        raise ValueError("high_turnover_ratio 必须是正数或 null")
    if not isinstance(params["shrink_day"], dict) or "basis" not in params["shrink_day"]:
        raise ValueError("shrink_day 必须包含 basis")
    _validate_hh_mm(params["instant_seal_time"], "instant_seal_time")
    return params


def load_params(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the parameter document from disk."""

    source = Path(path).expanduser() if path else DEFAULT_PARAMS_PATH
    if not source.is_file():
        raise FileNotFoundError(f"教学框架参数文件不存在: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"参数文件不是有效 JSON: {source}: {exc}") from exc
    return validate_params(data)


def parameter_hash(params_or_path: dict[str, Any] | str | Path | None = None) -> str:
    """SHA-256 of canonical parameter JSON (full hex digest)."""

    params = (
        load_params(params_or_path)
        if params_or_path is None or isinstance(params_or_path, (str, Path))
        else validate_params(params_or_path)
    )
    return hashlib.sha256(canonical_json(params).encode("utf-8")).hexdigest()


def framework_version(params_or_path: dict[str, Any] | str | Path | None = None) -> str:
    """Return the framework namespace used in teaching rows and receipts."""

    params = (
        load_params(params_or_path)
        if params_or_path is None or isinstance(params_or_path, (str, Path))
        else validate_params(params_or_path)
    )
    return f"{params['framework_version_base']}+{parameter_hash(params)[:8]}"

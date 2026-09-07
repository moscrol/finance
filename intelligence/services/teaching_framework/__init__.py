"""Deterministic teaching-framework labels and their sidecar receipts.

The package is intentionally small: source facts remain read-only and all
derived rows are written to ``history_labels.duckdb`` by the builders.
"""

from .params import (
    DEFAULT_PARAMS_PATH,
    canonical_json,
    framework_version,
    load_params,
    parameter_hash,
)

__all__ = [
    "DEFAULT_PARAMS_PATH",
    "canonical_json",
    "framework_version",
    "load_params",
    "parameter_hash",
]

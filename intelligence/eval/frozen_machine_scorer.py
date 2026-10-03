"""Temporary, evaluation-only access to one authenticated legacy scorer artifact.

This is NOT source restoration and NOT a safe loader for arbitrary bytecode.
Only the previously fingerprinted project artifact below is accepted. Read and hash
once, then execute those same bytes; never import the empty original .py or
run the legacy batch runner. The caller must keep the artifact and receipts
private and freeze the case/truth separately before a live evaluation.
"""
from __future__ import annotations

import copy
import hashlib
from importlib.util import MAGIC_NUMBER
import marshal
from pathlib import Path
import types
from typing import Any

PINNED_SHA256 = "195ad5598432e64f9be8a0a60025f8a14d7e2df5b246ecdd2f82c9a21366ac88"
PINNED_MAGIC = bytes.fromhex("cb0d0d0a")


def score_pinned_case(artifact: Path, case: dict[str, Any], answer: str) -> dict[str, Any]:
    """Return the unchanged legacy score with explicit temporary-loader provenance."""
    if not isinstance(answer, str) or not isinstance(case, dict):
        raise TypeError("case must be a dict and answer must be text")
    data = artifact.read_bytes()
    if hashlib.sha256(data).hexdigest() != PINNED_SHA256:
        raise ValueError("legacy scorer artifact digest mismatch")
    if MAGIC_NUMBER != PINNED_MAGIC or data[:4] != PINNED_MAGIC:
        raise ValueError("legacy scorer requires its frozen CPython 3.12 bytecode magic")
    code = marshal.loads(data[16:])
    if not isinstance(code, types.CodeType):
        raise TypeError("scorer artifact is not a module code object")
    namespace: dict[str, Any] = {
        "__name__": "_frozen_machine_truth_not_main",
        "__file__": str(artifact.resolve()),
    }
    exec(code, namespace)
    score_case = namespace.get("score_case")
    if not callable(score_case):
        raise TypeError("legacy artifact has no callable score_case")
    # Isolate caller-owned truth even if a legacy implementation mutates its input.
    score = score_case(copy.deepcopy(case), answer)
    if not isinstance(score, dict):
        raise TypeError("legacy scorer did not return a dictionary")
    return {
        "schema": "frozen-legacy-machine-score/v1",
        "scorer_sha256": PINNED_SHA256,
        "python_magic": PINNED_MAGIC.hex(),
        "source_restored": False,
        "mode": "temporary_frozen_bytecode",
        "score": score,
    }

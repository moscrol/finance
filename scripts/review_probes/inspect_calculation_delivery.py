"""Describe saved calculation delivery without executing its script or refetching data.

Prevents repeatedly hand-reading a successful calc JSON while overlooking an empty
normalized view or different numbers in the answer. Uses the actual pure renderer;
it is NOT an independent arithmetic oracle or a correctness/acceptance gate.
Script calls are syntax facts, not proof that input evidence was consumed.

Usage: python scripts/review_probes/inspect_calculation_delivery.py CALC_JSON
       [--answer ANSWER_MD_OR_PUBLIC_MESSAGE_JSON]
Exit 0 means the inspection completed, even when the report exposes lost values;
exit 2 means the supplied files could not be inspected. No writes or network IO.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services import derived_calculation_artifacts as artifacts  # noqa: E402


def inspect_record(record: dict[str, Any], answer: str = "") -> dict[str, Any]:
    result = record.get("result")
    if not isinstance(result, dict):
        raise ValueError("calculation result must be a JSON object")
    view = artifacts.normalize_result(result)
    raw_summary = result.get("summary")
    dropped = sorted(set(raw_summary) - set(view.summary)) if isinstance(raw_summary, dict) else []
    calls: set[str] = set()
    script_error = ""
    try:
        tree = ast.parse(str(record.get("script") or ""))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
    except SyntaxError:
        script_error = "syntax_error"
    numbers = artifacts.numeric_observations(view)
    return {
        "scope": "descriptive_only_not_acceptance_or_arithmetic_verification",
        "calc_id": record.get("calc_id"),
        "exit_code": record.get("exit_code"),
        "input_evidence_count": len(record.get("input_evidence_hashes") or []),
        "script_call_names_syntax_only": sorted(calls),
        "script_parse_error": script_error,
        "raw_result": result,
        "normalized_summary": dict(view.summary),
        "dropped_summary_keys": dropped,
        "normalized_table_count": len(view.tables),
        "normalized_numeric_observations": [list(pair) for pair in numbers],
        "compact_result": artifacts.compact_text(view, budget=2000),
        "answer_table_lines": [line for line in answer.splitlines() if line.lstrip().startswith("|")],
        "answer_comparison": "manual_required; no claim is made from token presence",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("calculation", type=Path)
    parser.add_argument("--answer", type=Path)
    args = parser.parse_args(argv)
    try:
        raw = args.calculation.read_bytes()
        record = json.loads(raw)
        if not isinstance(record, dict):
            raise ValueError("calculation must be a JSON object")
        answer = ""
        answer_hash = None
        if args.answer:
            answer_raw = args.answer.read_bytes()
            answer_hash = hashlib.sha256(answer_raw).hexdigest()
            answer = answer_raw.decode("utf-8")
            if args.answer.suffix.lower() == ".json":
                message = json.loads(answer)
                answer = message.get("content") if isinstance(message, dict) else None
                if not isinstance(answer, str):
                    raise ValueError("public message must have a string content field")
        report = inspect_record(record, answer)
        report["input_sha256"] = hashlib.sha256(raw).hexdigest()
        report["answer_sha256"] = answer_hash
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"Cannot inspect supplied artifacts: {type(exc).__name__}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

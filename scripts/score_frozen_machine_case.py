#!/usr/bin/env python3
"""Score one private case with the pinned legacy artifact; NOT semantic acceptance.

The legacy numeric matcher can accept wrong field/value associations. Preserve
this compatibility score separately from full-answer factual/source review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from intelligence.eval.frozen_machine_scorer import score_pinned_case  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scorer', type=Path, required=True)
    parser.add_argument('--case-json', type=Path, required=True)
    parser.add_argument('--answer-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Claim once before executing even the trusted legacy module. Never reuse a result.
    with args.output.open('x', encoding='utf-8') as handle:
        try:
            case_bytes = args.case_json.read_bytes()
            answer_bytes = args.answer_file.read_bytes()
            case = json.loads(case_bytes.decode('utf-8'))
            answer = answer_bytes.decode('utf-8')
            result = score_pinned_case(args.scorer, case, answer)
            receipt = {'status': 'scored', 'semantic_acceptance': 'not_established', 'result': result,
                       'case_sha256': hashlib.sha256(case_bytes).hexdigest(),
                       'answer_sha256': hashlib.sha256(answer_bytes).hexdigest()}
            code = 0
        except Exception as exc:
            receipt = {'status': 'error', 'semantic_acceptance': 'not_established',
                       'error_type': type(exc).__name__, 'error': str(exc)}
            code = 2
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    return code


if __name__ == '__main__':
    raise SystemExit(main())

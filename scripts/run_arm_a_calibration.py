#!/usr/bin/env python3
"""Run the Step 8 Arm A calibration window. Not an A/B decision."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.eval.arm_a_calibration import (
    ARM_A_BACKEND,
    ArmACalibrationError,
    EXPECTED_MODEL,
    OFFICIAL_REPEATS,
    form_calibration_receipt,
    inspect_runtime_env,
    reject_forbidden_cli,
)
from scripts import run_agent_runtime_benchmark as benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Frozen-nine Arm A calibration; refuses keychain and retired model"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repeats", type=int, default=OFFICIAL_REPEATS)
    parser.add_argument("--questions-file", type=Path, required=True)
    parser.add_argument("--finance-root", type=Path)
    parser.add_argument("--knowledge-wiki", type=Path)
    parser.add_argument(
        "--case",
        action="append",
        help="Optional subset for a smoke run; official window needs the full nine",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        reject_forbidden_cli(raw)
        args = build_parser().parse_args(raw)
        if args.repeats < 1:
            raise ArmACalibrationError("repeats must be >= 1")
        env = inspect_runtime_env()
        if not args.dry_run:
            if env.get("issues"):
                raise ArmACalibrationError(
                    "production alignment failed: " + ",".join(map(str, env["issues"]))
                )
            if not env.get("openai_api_key_present"):
                raise ArmACalibrationError(
                    "live calibration requires OPENAI_API_KEY in the environment"
                )
            if env.get("llm_model") != EXPECTED_MODEL:
                raise ArmACalibrationError(
                    f"live calibration requires LLM_MODEL={EXPECTED_MODEL}"
                )
            if not env.get("llm_base_host"):
                raise ArmACalibrationError("live calibration requires LLM_BASE_URL")
            if args.finance_root is None or args.knowledge_wiki is None:
                raise ArmACalibrationError(
                    "live calibration requires --finance-root and --knowledge-wiki"
                )
    except ArmACalibrationError as exc:
        print(f"arm a calibration failed: {exc}", file=sys.stderr)
        return 2

    output_dir = args.output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, object]] = []
    written: list[dict[str, str]] = []
    for index in range(1, args.repeats + 1):
        output = output_dir / f"arm-a-cal-r{index}.json"
        command = [
            "--backend",
            ARM_A_BACKEND,
            "--questions-file",
            str(args.questions_file),
            "--output",
            str(output),
        ]
        if args.dry_run:
            command.append("--dry-run")
        if args.finance_root is not None:
            command.extend(["--finance-root", str(args.finance_root)])
        if args.knowledge_wiki is not None:
            command.extend(["--knowledge-wiki", str(args.knowledge_wiki)])
        if args.case:
            for case_id in args.case:
                command.extend(["--case", case_id])
        print(f"arm a calibration [{index}/{args.repeats}]", flush=True)
        code = benchmark.main(command)
        if code != 0:
            print(
                f"arm a calibration failed: benchmark repeat {index} exited {code}",
                file=sys.stderr,
            )
            return code
        payload = json.loads(output.read_text(encoding="utf-8"))
        artifacts.append(payload)
        written.append({"repeat": str(index), "name": output.name, "sha256": _file_sha256(output)})

    receipt = form_calibration_receipt(artifacts=artifacts, env=env)
    receipt["repeat_artifacts"] = written
    receipt_path = output_dir / "arm-a-calibration-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"arm a calibration receipt written: {receipt_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

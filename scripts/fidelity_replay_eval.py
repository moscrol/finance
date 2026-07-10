#!/usr/bin/env python3
"""CLI for current-state fidelity and strict PIT replay evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.eval.fidelity_replay import (
    aggregate_audits,
    audit_answer,
    build_gold_template,
    build_input_snapshot,
    build_outcome_snapshot,
    build_pilot_plan,
    render_pilot_plan,
    render_report,
    write_json,
)


def _read(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def cmd_pilot(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir).expanduser()
    plan = build_pilot_plan(
        args.db,
        args.kb_root,
        start=args.start,
        end=args.end,
        count=args.count,
    )
    for case in plan["cases"]:
        case_dir = out_dir / case["case_id"]
        if case["status"] != "ready":
            continue
        snapshot = build_input_snapshot(args.db, case)
        case["input_snapshot_sha256"] = snapshot["snapshot_sha256"]
        write_json(case_dir / "input.snapshot.json", snapshot)
        write_json(
            case_dir / "answer.template.json",
            {
                "schema_version": "fidelity-replay-answer-1.0",
                "date": case["target_date"],
                "perspective_date": case["as_of"],
                "case_id": case["case_id"],
                "input_snapshot_sha256": snapshot["snapshot_sha256"],
                "evidence_catalog": {},
                "claims": [
                    {
                        "id": "observation-1",
                        "text": "",
                        "declared_type": "observation",
                        "evidence_refs": [],
                        "entity": None,
                    },
                    {
                        "id": "inference-1",
                        "text": "",
                        "declared_type": "inference",
                        "evidence_refs": [],
                        "entity": None,
                    },
                    {
                        "id": "prediction-1",
                        "text": "",
                        "declared_type": "prediction",
                        "evidence_refs": [],
                        "entity": None,
                    },
                ],
                "status": "pending",
                "note": (
                    "回答阶段只能读取 input.snapshot.json 与 kb_snapshot.commit；"
                    "每条 claim 必须声明类型并绑定 evidence_catalog。"
                ),
            },
        )
    write_json(out_dir / "pilot.plan.json", plan)
    report_path = out_dir / "pilot.report.md"
    report_path.write_text(render_pilot_plan(plan), encoding="utf-8")
    print(json.dumps(plan["status_counts"], ensure_ascii=False))
    print(f"written: {out_dir / 'pilot.plan.json'}")
    print(f"written: {report_path}")
    return 0


def cmd_outcomes(args: argparse.Namespace) -> int:
    plan = _read(args.plan)
    out_dir = Path(args.out_dir).expanduser()
    for case in plan.get("cases", []):
        if case.get("status") != "ready":
            continue
        outcome = build_outcome_snapshot(args.db, case)
        write_json(out_dir / case["case_id"] / "outcome.snapshot.json", outcome)
    print(f"written: {out_dir}")
    return 0


def cmd_gold_template(args: argparse.Namespace) -> int:
    answer = _read(args.answer)
    template = build_gold_template(answer, answer_path=str(Path(args.answer).expanduser()))
    write_json(Path(args.out).expanduser(), template)
    print(f"written: {args.out}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    answer = _read(args.answer)
    manifest = _read(args.manifest)
    gold = _read(args.gold) if args.gold else None
    snapshot = _read(args.snapshot) if args.snapshot else None
    audit = audit_answer(
        answer,
        manifest,
        db_path=args.db,
        gold=gold,
        input_snapshot=snapshot,
        answer_path=str(Path(args.answer).expanduser()),
    )
    if args.out:
        write_json(Path(args.out).expanduser(), audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2, default=str))
    return 2 if audit["gold_errors"] else 0


def cmd_audit_ledger(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger_dir).expanduser()
    audits: list[dict[str, Any]] = []
    for answer_path in sorted(ledger.glob("*.answer.*.json")):
        answer = _read(answer_path)
        manifest_path = ledger / f"{answer.get('date')}.manifest.json"
        if not manifest_path.exists():
            continue
        gold_path = (
            Path(args.gold_dir).expanduser() / f"{answer_path.stem}.gold.json"
            if args.gold_dir
            else None
        )
        gold = _read(gold_path) if gold_path and gold_path.exists() else None
        audits.append(
            audit_answer(
                answer,
                _read(manifest_path),
                db_path=args.db,
                gold=gold,
                answer_path=str(answer_path),
            )
        )
    report = aggregate_audits(audits)
    if args.out_json:
        write_json(Path(args.out_json).expanduser(), report)
    if args.out_md:
        path = Path(args.out_md).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_report(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    pilot = sub.add_parser("pilot", help="分层抽样并生成仅含 D0 及以前数据的输入快照")
    pilot.add_argument("--db", required=True)
    pilot.add_argument("--kb-root", required=True)
    pilot.add_argument("--start", required=True)
    pilot.add_argument("--end", required=True)
    pilot.add_argument("--count", type=int, default=10)
    pilot.add_argument("--out-dir", required=True)
    pilot.set_defaults(func=cmd_pilot)

    outcomes = sub.add_parser(
        "outcomes", help="在答卷冻结后，独立生成 T+1/T+3 结果快照"
    )
    outcomes.add_argument("--plan", required=True)
    outcomes.add_argument("--db", required=True)
    outcomes.add_argument("--out-dir", required=True)
    outcomes.set_defaults(func=cmd_outcomes)

    gold = sub.add_parser("gold-template", help="从结构化答卷生成待人工裁定的金标准模板")
    gold.add_argument("--answer", required=True)
    gold.add_argument("--out", required=True)
    gold.set_defaults(func=cmd_gold_template)

    score = sub.add_parser("score", help="评测单份答卷")
    score.add_argument("--answer", required=True)
    score.add_argument("--manifest", required=True)
    score.add_argument("--db")
    score.add_argument("--snapshot", help="优先使用冻结 input.snapshot.json 核对数字")
    score.add_argument("--gold")
    score.add_argument("--out")
    score.set_defaults(func=cmd_score)

    audit = sub.add_parser("audit-ledger", help="审计现有双盲台账")
    audit.add_argument(
        "--ledger-dir", default="docs/learning/forecast-review-ledger"
    )
    audit.add_argument("--db")
    audit.add_argument("--gold-dir")
    audit.add_argument("--out-json")
    audit.add_argument("--out-md")
    audit.set_defaults(func=cmd_audit_ledger)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

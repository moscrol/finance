#!/usr/bin/env python3
"""历史重放引擎 CLI（INDEX #25）：站在 D0 出结构化判断 → 自动判分 → AI 校准读数。

子命令：
    run          选节点 → 建输入（两档 PIT）→ 两臂两车道提示词 → LLM → 判分 → 聚合 → 报表
                 加 --dry-run 只打印节点数 / 调用数 / 估算 token（不碰 LLM，不写 measurements）
    report       从已落盘的 run 目录重出报表（重新校验 / 判分 / 聚合，不碰 LLM）
    nodes        只打印节点选择（两档各多少、哪些日期、pit_grade 判定原因）

纪律（工单 §6）：主库 / 旁路库 / 快照目录全程只读；LLM 只走 llm_refine.complete，--max-calls 默认 200 是
硬帽（预算闸拒发即停，不重试）；先 --dry-run 再 run；产物落 ~/.finance-runtime/replay/<run_id>/（不进仓），
报表落 intelligence/eval/measurements/replay-<date>.{json,md}（进仓）。不写 docs/learning/forecast-review-ledger/。

用法::

    python scripts/replay_engine.py run --db db/market_feature_store.duckdb --labels-db db/history_labels.duckdb --dry-run
    python scripts/replay_engine.py run --db ... --labels-db ... --count-per-grade 20 --arms named,anonymized --lanes A,B
    python scripts/replay_engine.py report --run-dir ~/.finance-runtime/replay/<run_id> --db ... --labels-db ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.eval import replay_engine as engine  # noqa: E402
from intelligence.services.methodology_backtest.store import default_labels_db_path  # noqa: E402
from market_feature_store.db import DB_PATH  # noqa: E402


def _csv(value: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in str(value).split(",") if x.strip())


def _labels_default(db: str) -> str:
    return str(default_labels_db_path(db))


def cmd_nodes(args: argparse.Namespace) -> int:
    labels_db = args.labels_db or _labels_default(args.db)
    con = engine._open_labels(labels_db)
    try:
        conditions = engine.load_conditions(con)
    finally:
        con.close()
    start = args.start or conditions["calendar"]["start"]
    end = args.end or engine.judgeable_end(args.db) or conditions["calendar"]["end"]
    forced = engine.reconciliation_dates(args.ledger_dir, args.snapshot_root) if not args.no_reconcile else []
    nodes = engine.select_nodes(
        args.db, start, end, count_per_grade=args.count_per_grade, snapshot_root=args.snapshot_root, forced_dates=forced
    )
    print(json.dumps({"start": start, "end": end, "forced_dates": forced, "nodes": nodes}, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    labels_db = args.labels_db or _labels_default(args.db)
    report = engine.run_replay(
        db_path=args.db,
        labels_db=labels_db,
        snapshot_root=args.snapshot_root,
        runtime_root=args.runtime_root,
        start=args.start,
        end=args.end,
        count_per_grade=args.count_per_grade,
        arms=_csv(args.arms),
        lanes=_csv(args.lanes),
        max_calls=args.max_calls,
        dry_run=args.dry_run,
        ledger_dir=None if args.no_reconcile else args.ledger_dir,
        reconcile=not args.no_reconcile,
        measurements_dir=None if args.dry_run else args.measurements_dir,
        run_id=args.run_id,
        abort_failure_rate=None if args.abort_failure_rate <= 0 else args.abort_failure_rate,
    )
    dry = report.get("dry_run") or {}
    llm = report["conditions"]["llm"]
    print(
        json.dumps(
            {
                "run_id": report["run_id"],
                "run_dir": report["run_dir"],
                "nodes": dry.get("nodes"),
                "nodes_by_grade": report["conditions"]["nodes_by_grade"],
                "planned_calls": dry.get("planned_calls"),
                "estimated_input_tokens": dry.get("estimated_input_tokens"),
                "estimated": True,
                "calls": llm["calls"],
                "failures": llm["failures"],
                "invalid_answers": llm["invalid_answers"],
                "stopped_reason": report.get("stopped_reason"),
                "measurement_paths": report.get("measurement_paths"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not report.get("stopped_reason") else 2


def cmd_report(args: argparse.Namespace) -> int:
    labels_db = args.labels_db or _labels_default(args.db)
    report = engine.rebuild_report(
        args.run_dir,
        db_path=args.db,
        labels_db=labels_db,
        snapshot_root=args.snapshot_root,
        ledger_dir=None if args.no_reconcile else args.ledger_dir,
        measurements_dir=args.measurements_dir,
    )
    print(json.dumps({"run_id": report["run_id"], "run_dir": report["run_dir"], "measurement_paths": report.get("measurement_paths")}, ensure_ascii=False, indent=2))
    return 0


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default=str(DB_PATH), help="主库（只读）")
    parser.add_argument("--labels-db", default=None, help="旁路库（只读，默认与主库同目录的 history_labels.duckdb）")
    parser.add_argument("--snapshot-root", default=str(engine.DEFAULT_SNAPSHOT_ROOT), help="PIT 快照目录（只读）")
    parser.add_argument("--ledger-dir", default=str(engine.LEDGER_DIR), help="双盲台账目录（只读，对账用）")
    parser.add_argument("--no-reconcile", action="store_true", help="不跑对账段、不强制纳入对账日期")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="跑重放（--dry-run 只估算）")
    _common(run)
    run.add_argument("--runtime-root", default=str(engine.DEFAULT_RUNTIME_ROOT))
    run.add_argument("--measurements-dir", default=str(engine.MEASUREMENTS_DIR))
    run.add_argument("--start", default=None)
    run.add_argument("--end", default=None, help="默认：主库最后交易日往前 5 个交易日（T+5 可判）")
    run.add_argument("--count-per-grade", type=int, default=engine.DEFAULT_COUNT_PER_GRADE)
    run.add_argument("--arms", default=",".join(engine.ARMS))
    run.add_argument("--lanes", default=",".join(engine.LANES))
    run.add_argument("--max-calls", type=int, default=engine.DEFAULT_MAX_CALLS, help="LLM 调用硬帽（预算闸），默认 200")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--run-id", default=None)
    run.add_argument("--abort-failure-rate", type=float, default=0.2, help="调用失败率超过即停（≥10 次后生效；0 关闭）")
    run.set_defaults(func=cmd_run)

    report = sub.add_parser("report", help="从 run 目录重出报表")
    _common(report)
    report.add_argument("--run-dir", required=True)
    report.add_argument("--measurements-dir", default=None, help="给了才写 measurements（默认只更新 run 目录内的 report.*）")
    report.set_defaults(func=cmd_report)

    nodes = sub.add_parser("nodes", help="只看节点选择")
    _common(nodes)
    nodes.add_argument("--start", default=None)
    nodes.add_argument("--end", default=None)
    nodes.add_argument("--count-per-grade", type=int, default=engine.DEFAULT_COUNT_PER_GRADE)
    nodes.set_defaults(func=cmd_nodes)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "max_calls", 0) > engine.DEFAULT_MAX_CALLS:
        print(f"--max-calls 不得超过 {engine.DEFAULT_MAX_CALLS}（工单红线：200 次硬帽）", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

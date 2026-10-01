#!/usr/bin/env python3
"""模型 × harness 2×2 对照：排程与判定。

预注册 ``docs/superpowers/specs/2026-09-30-model-harness-2x2-preregistration.md``（§5 / §6）。

用法::

    # 开跑前：出排程（题集抽样 + 每轮题序 + 拉丁方格序 + provider 列），存进收据
    python scripts/model_harness_2x2.py plan --seen-file seen.txt \\
        --model-c <从 08-27 react 臂产物读出的 Claude 确切 ID> > plan.json

    # 跑完后：判定（逐次运行记录 JSONL，字段见 intelligence/eval/model_harness_2x2.py 顶部）
    python scripts/model_harness_2x2.py analyze runs.jsonl --plan plan.json
    python scripts/model_harness_2x2.py analyze runs.jsonl --plan plan.json --json > analysis.json

只读、不发请求。bootstrap 次数与种子是冻结规则，故意不开命令行参数。
退出码：0 = 已出结果（含「不完整」）；2 = 输入不符合预注册。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.eval.model_harness_2x2 import (  # noqa: E402
    DEFAULT_MODELS,
    DEFAULT_REPS,
    PLAN_SCHEMA,
    SENSITIVITY_EXCLUDE,
    UNSEEN_QUESTIONS,
    DesignError,
    analyze,
    recompute_admission,
    plan_document,
    render,
)


def _id_list(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def _read_ids(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _read_records(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise DesignError("运行记录应是 JSON 数组或 JSONL")
        return data
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="模型 × harness 2×2：排程与判定（只读）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    plan = sub.add_parser("plan", help="出排程：题集抽样、题序、拉丁方格序、provider 列")
    source = plan.add_mutually_exclusive_group(required=True)
    source.add_argument("--seen-file", type=Path, help="seen 组题号，一行一个（# 开头为注释）")
    source.add_argument("--seen", type=_id_list, help="seen 组题号，逗号分隔")
    plan.add_argument("--unseen", type=_id_list, default=list(UNSEEN_QUESTIONS), help="unseen 题号，逗号分隔")
    plan.add_argument("--reps", type=int, default=DEFAULT_REPS)
    plan.add_argument("--model-g", default=DEFAULT_MODELS["G"])
    plan.add_argument("--model-c", required=True, help="Claude 的确切模型 ID")

    run = sub.add_parser("analyze", help="按冻结规则判定")
    run.add_argument("runs", type=Path, help="逐次运行记录（JSONL 或 JSON 数组）")
    run.add_argument("--plan", type=Path, help="plan 子命令的输出；给了就以它的题集 / unseen / reps 为准")
    run.add_argument("--unseen", type=_id_list, default=list(UNSEEN_QUESTIONS))
    run.add_argument("--exclude", type=_id_list, default=list(SENSITIVITY_EXCLUDE), help="敏感性分析去掉的题")
    run.add_argument("--reps", type=int, default=DEFAULT_REPS)
    run.add_argument(
        "--episode-store", default=None,
        help="子分支 episode 所在 store 根目录（重算准入时给老产物补证）",
    )
    run.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    return parser


def _plan(args: argparse.Namespace) -> int:
    seen = _read_ids(args.seen_file) if args.seen_file else args.seen
    doc = plan_document(
        seen,
        unseen=args.unseen,
        reps=args.reps,
        models={"G": args.model_g, "C": args.model_c},
    )
    print(json.dumps(doc, ensure_ascii=False, indent=2))
    print(
        f"题集 {len(doc['questions'])} 题（unseen {len(doc['unseen'])} + 抽中 seen {len(doc['seen_sampled'])}）"
        f" × 4 格 × {doc['reps']} 次 = {len(doc['runs'])} 次；抽中的 seen：{'、'.join(doc['seen_sampled'])}",
        file=sys.stderr,
    )
    return 0


def _analyze(args: argparse.Namespace) -> int:
    questions = None
    unseen, reps = args.unseen, args.reps
    models: dict[str, str] = {}
    if args.plan:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        if plan.get("schema") != PLAN_SCHEMA:
            raise DesignError(f"{args.plan} 不是 {PLAN_SCHEMA}")
        questions, unseen, reps = plan["questions"], plan["unseen"], int(plan["reps"])
        models = dict(plan.get("models") or {})
    records = _read_records(args.runs)
    if not models and any(record.get("artifact") for record in records):
        raise DesignError("要按产物重算准入，得给 --plan（取各格期望模型）")
    records, admission = recompute_admission(
        records, models, episode_store=args.episode_store,
    )
    report = analyze(
        records,
        questions=questions,
        unseen=unseen,
        exclude=args.exclude,
        reps=reps,
    )
    report["admission"] = admission
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(render(report))
    print(
        f"准入：按产物重算 {admission['recomputed']} 次，"
        f"无产物作废 {admission['unverified']} 次；自报与重算不一致 {len(admission['disagreements'])} 次"
    )
    for item in admission["disagreements"][:10]:
        print(f"  ⚠ seq {item['seq']}：自报 exit {item['reported']}，重算 exit {item['recomputed']}（以重算为准）")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _plan(args) if args.cmd == "plan" else _analyze(args)
    except (DesignError, json.JSONDecodeError, OSError) as exc:
        print(f"输入不符合预注册：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

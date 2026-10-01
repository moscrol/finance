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
退出码：0 = 已出结果（含样本不完整）；1 = 模型错配；2 = 无模型证据或输入不符合预注册。
分析入口强制 --plan 并重算 artifacts 及子分支准入；人工填 admission_exit=0 不能放行。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.eval.model_admission import check_paths, overall_exit_code  # noqa: E402

from intelligence.eval.model_harness_2x2 import (  # noqa: E402
    DEFAULT_MODELS,
    DEFAULT_REPS,
    PLAN_SCHEMA,
    SENSITIVITY_EXCLUDE,
    UNSEEN_QUESTIONS,
    DesignError,
    analyze,
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
    run.add_argument("--episode-store", type=Path, action="append", default=[], help="分支事件 store；准入自动追踪父子模型证据")
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


def _attest_records(records: list[dict], plan: dict, root: Path, stores: list[Path]):
    """接受分数前自动重读证据；自报 admission_exit 仅作审计，不作准入依据。"""

    models = plan.get("models")
    if not isinstance(models, dict) or any(
        not isinstance(models.get(key), str) or not models[key].strip() for key in ("G", "C")
    ):
        raise DesignError("--plan 必须冻结 G/C 的确切模型 ID")
    checked, receipts = [], []
    for row in records:
        if not isinstance(row, dict) or row.get("cell") not in {"PG", "PC", "RG", "RC"}:
            raise DesignError("运行记录必须含合法 cell")
        paths = row.get("artifacts", [])
        if not isinstance(paths, list) or any(not isinstance(p, str) or not p.strip() for p in paths):
            raise DesignError("artifacts 必须是非空路径字符串的列表")
        resolved = [Path(p).expanduser() for p in paths]
        resolved = [p if p.is_absolute() else root / p for p in resolved]
        results = check_paths(resolved, [models[row["cell"][1]]], episode_store_roots=stores)
        code = overall_exit_code(results)
        hashes = {}
        for result in results:
            path = Path(result.source)
            if path.is_file():
                hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        checked.append({**row, "admission_exit": code})
        receipts.append({
            "seq": row.get("seq"), "cell": row["cell"],
            "expected_model": models[row["cell"][1]],
            "claimed_exit": row.get("admission_exit"), "exit_code": code,
            "results": [r.to_dict() for r in results], "sha256": hashes,
        })
    return checked, receipts


def _analyze(args: argparse.Namespace) -> int:
    if args.plan is None:
        raise DesignError("analyze 必须提供 --plan，不能从运行自报值猜期望模型")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise DesignError(f"{args.plan} 不是 {PLAN_SCHEMA}")
    checked, receipts = _attest_records(
        _read_records(args.runs), plan, args.runs.resolve().parent, args.episode_store,
    )
    report = analyze(
        checked,
        questions=plan["questions"],
        unseen=plan["unseen"],
        exclude=args.exclude,
        reps=int(plan["reps"]),
    )
    report["admission"] = receipts
    report["plan_sha256"] = hashlib.sha256(args.plan.read_bytes()).hexdigest()
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    codes = {r["exit_code"] for r in receipts}
    return 1 if 1 in codes else (2 if not receipts or 2 in codes else 0)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _plan(args) if args.cmd == "plan" else _analyze(args)
    except (DesignError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"输入不符合预注册：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

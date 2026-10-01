#!/usr/bin/env python3
"""Harness 改动的强弱双模型闸门：强模型不得退步，弱模型要有增益。确定性，不调模型。

背景见 docs/runtime/model-tier-harness.md。每个改动 harness 的提交，都要在「实惠模型」
和「强模型」上各跑一次基线（改动前）与新版（改动后），四份判分报告交给本脚本：

    python3 scripts/harness_tier_gate.py check \\
        --weak-base wb.json --weak-new wn.json \\
        --strong-base sb.json --strong-new sn.json [--json]

报告格式（二选一，可混用）：
  * ``content_correctness_eval.py score --json`` 的原样输出（按题集补全通过名单）；
  * 通用格式 ``{"cases": {"<case_id>": true|false, ...}}``——任何逐题判分的评测都能转成它。

判定（逐题，不只看通过率——通过率持平也可能是「修好 2 题、弄坏 2 题」）：
  FAIL  强模型有题从通过变失败（strong_regressions 非空），或弱模型净退步；
  WARN  强模型无退步，但弱模型没有净增益（改动没用，或者只是挪了位置）；
  PASS  强模型无退步，弱模型净增益 > 0。
退出码：PASS/WARN = 0，FAIL = 1，输入错误 = 2。

    python3 scripts/harness_tier_gate.py selftest
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class GateInputError(ValueError):
    pass


def case_outcomes(report: dict[str, Any], *, label: str = "report") -> dict[str, bool]:
    """把一份报告归一成 {case_id: passed}。"""
    if isinstance(report.get("cases"), dict):
        return {str(k): bool(v) for k, v in report["cases"].items()}
    if "failures" in report and "total" in report:
        from intelligence.eval import content_correctness as cc  # noqa: PLC0415

        ids = [c.id for c in cc.load_cases()]
        if len(ids) != report["total"]:
            raise GateInputError(
                f"{label}: total={report['total']} 与当前题集 {len(ids)} 题不一致——题集变过，基线要重跑"
            )
        failed = set(report["failures"])
        unknown = failed - set(ids)
        if unknown:
            raise GateInputError(f"{label}: 未知题号 {sorted(unknown)}")
        return {cid: cid not in failed for cid in ids}
    raise GateInputError(f"{label}: 既不是 content_correctness 报告，也不是 {{'cases': {{...}}}} 格式")


def compare(base: dict[str, bool], new: dict[str, bool], *, label: str) -> dict[str, Any]:
    if set(base) != set(new):
        missing = sorted(set(base) ^ set(new))
        raise GateInputError(f"{label}: 基线与新版题号集合不同 {missing[:10]}")
    fixed = sorted(k for k in base if not base[k] and new[k])
    broken = sorted(k for k in base if base[k] and not new[k])
    n = len(base)
    return {
        "n": n,
        "base_passed": sum(base.values()),
        "new_passed": sum(new.values()),
        "fixed": fixed,
        "broken": broken,
        "net": len(fixed) - len(broken),
    }


def gate(weak_base, weak_new, strong_base, strong_new) -> dict[str, Any]:
    weak = compare(weak_base, weak_new, label="weak")
    strong = compare(strong_base, strong_new, label="strong")
    if strong["broken"] or weak["net"] < 0:
        verdict = "FAIL"
    elif weak["net"] > 0:
        verdict = "PASS"
    else:
        verdict = "WARN"
    # 强弱差距：同一版 harness 下强模型领先弱模型多少题。PASS 且差距缩小 = harness 在补地板；
    # 强模型自己也涨 = harness 在抬天花板。两者都是我们要的，分开报。
    gap_base = strong["base_passed"] - weak["base_passed"]
    gap_new = strong["new_passed"] - weak["new_passed"]
    return {
        "verdict": verdict,
        "weak": weak,
        "strong": strong,
        "strong_regressions": strong["broken"],
        "gap_base": gap_base,
        "gap_new": gap_new,
    }


def _load(path: Path, label: str) -> dict[str, bool]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateInputError(f"{label}: 读不了 {path}: {exc}") from exc
    return case_outcomes(report, label=label)


def _print_human(result: dict[str, Any]) -> None:
    w, s = result["weak"], result["strong"]
    print(f"判定 {result['verdict']}")
    print(f"  弱模型 {w['base_passed']}/{w['n']} → {w['new_passed']}/{w['n']}（净 {w['net']:+d}）")
    print(f"  强模型 {s['base_passed']}/{s['n']} → {s['new_passed']}/{s['n']}（净 {s['net']:+d}）")
    print(f"  强弱差距 {result['gap_base']} → {result['gap_new']}")
    for name, row in (("弱", w), ("强", s)):
        if row["fixed"]:
            print(f"  {name}模型修好：{', '.join(row['fixed'])}")
        if row["broken"]:
            print(f"  {name}模型弄坏：{', '.join(row['broken'])}")
    if result["strong_regressions"]:
        print("  ✗ 强模型退步——这个改动在限制强模型，不能合入（或只对 economy 档生效）")


def _selftest() -> int:
    ids = ["a", "b", "c", "d"]

    def mk(*passed: str) -> dict[str, bool]:
        return {i: i in passed for i in ids}

    cases = [
        ("弱涨强平", (mk("a"), mk("a", "b"), mk("a", "b", "c"), mk("a", "b", "c")), "PASS"),
        ("弱涨强也涨", (mk("a"), mk("a", "b"), mk("a", "b"), mk("a", "b", "c")), "PASS"),
        ("弱平强平", (mk("a"), mk("a"), mk("a", "b"), mk("a", "b")), "WARN"),
        ("弱涨但强弄坏一题", (mk("a"), mk("a", "b"), mk("a", "b", "c"), mk("a", "b", "d")), "FAIL"),
        ("弱净退步", (mk("a", "b"), mk("a"), mk("a"), mk("a")), "FAIL"),
        ("通过率持平但弱模型换题", (mk("a"), mk("b"), mk("c"), mk("c")), "WARN"),
    ]
    ok = True
    for name, args, expected in cases:
        got = gate(*args)["verdict"]
        mark = "✓" if got == expected else "✗"
        ok &= got == expected
        print(f"{mark} {name}: {got}（期望 {expected}）")
    try:
        compare({"a": True}, {"b": True}, label="x")
        print("✗ 题号不一致未报错")
        ok = False
    except GateInputError:
        print("✓ 题号不一致报错")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    for flag in ("--weak-base", "--weak-new", "--strong-base", "--strong-new"):
        p.add_argument(flag, type=Path, required=True)
    p.add_argument("--json", action="store_true")
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        return _selftest()
    try:
        result = gate(
            _load(args.weak_base, "weak-base"),
            _load(args.weak_new, "weak-new"),
            _load(args.strong_base, "strong-base"),
            _load(args.strong_new, "strong-new"),
        )
    except GateInputError as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)
    return 1 if result["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

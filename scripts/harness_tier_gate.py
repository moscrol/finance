#!/usr/bin/env python3
"""Local paired-score comparator; NOT a generic harness-benefit acceptance gate.

Historical CLI labels --weak/--strong mean configuration A/B, not verified
model strength. Four reports must have identical nonempty case IDs and exact
boolean outcomes. Only explicit {"cases": {"id": true|false}} input is accepted.
Summary counts erase passed-case IDs and cannot establish paired identity;
regenerate outcomes from original answers via content_correctness_eval score
--cases-json. Explicit IDs still do not establish model identity, unchanged
question content, holdout independence, equal budgets, costs, or answer faithfulness.

Any observed per-case regression -> FAIL (exit 1, not a causal conclusion).
Otherwise -> INCONCLUSIVE (exit 3), including both configurations improving.
Input errors -> exit 2. Only software selftest uses exit 0. No PASS / no automatic
release, and no recommendation to hide a regression behind model-specific use.
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


def _validated_cases(value: object, *, label: str) -> dict[str, bool]:
    if not isinstance(value, dict) or not value:
        raise GateInputError(f"{label}: 逐题结果必须为非空对象，缺评测不是通过")
    if any(not isinstance(k, str) or not k.strip() for k in value):
        raise GateInputError(f"{label}: 题号必须为非空字符串")
    if any(type(v) is not bool for v in value.values()):
        raise GateInputError(f"{label}: 结果必须是JSON布尔值，不能把字符串/数字转成布尔值")
    return dict(value)


def case_outcomes(report: dict[str, Any], *, label: str = "report") -> dict[str, bool]:
    if not isinstance(report, dict):
        raise GateInputError(f"{label}: 报告必须是JSON对象")
    if any(key in report for key in ("total", "passed", "failures", "by_class", "pass_rate")):
        raise GateInputError(
            f"{label}: summary或混合报告不能证明逐题身份；请从原答卷生成显式cases"
            "（content_correctness_eval.py score --cases-json），不能按当前题集补猜通过题"
        )
    if "cases" not in report:
        raise GateInputError(f"{label}: 缺少显式cases逐题结果")
    return _validated_cases(report["cases"], label=label)


def compare(base: dict[str, bool], new: dict[str, bool], *, label: str) -> dict[str, Any]:
    base = _validated_cases(base, label=label + "-base")
    new = _validated_cases(new, label=label + "-new")
    if set(base) != set(new):
        raise GateInputError(f"{label}: 基线与新版题号集合不同 {sorted(set(base) ^ set(new))[:10]}")
    fixed = sorted(k for k in base if not base[k] and new[k])
    broken = sorted(k for k in base if base[k] and not new[k])
    return {"n": len(base), "base_passed": sum(base.values()), "new_passed": sum(new.values()),
            "fixed": fixed, "broken": broken, "net": len(fixed) - len(broken)}


def gate(weak_base, weak_new, strong_base, strong_new) -> dict[str, Any]:
    weak = compare(weak_base, weak_new, label="configuration-A")
    strong = compare(strong_base, strong_new, label="configuration-B")
    if set(weak_base) != set(strong_base):
        raise GateInputError("两配置必须使用同一题号集合；不能比较不同分母")
    regression = bool(weak["broken"] or strong["broken"])
    return {
        "verdict": "FAIL" if regression else "INCONCLUSIVE",
        "scope": "paired_case_score_comparison_only",
        "acceptance": "not_established",
        "strength_ordering": "not_verified",
        "observed_change": ("regression_observed" if regression else
                            "score_improvement_observed" if weak["fixed"] or strong["fixed"] else "unchanged"),
        "weak": weak, "strong": strong,
        "weak_regressions": weak["broken"], "strong_regressions": strong["broken"],
        "gap_base": strong["base_passed"] - weak["base_passed"],
        "gap_new": strong["new_passed"] - weak["new_passed"],
        "missing_evidence": ["model_identity", "holdout_and_repetition", "paired_inputs_and_budgets",
                             "full_answer_faithfulness", "cost_and_latency"],
    }


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GateInputError(f"重复JSON键：{key}")
        result[key] = value
    return result


def _load(path: Path, label: str) -> dict[str, bool]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateInputError(f"{label}: 读不了 {path}: {exc}") from exc
    return case_outcomes(report, label=label)


def _print_human(result: dict[str, Any]) -> None:
    print(f"局部比较 {result['verdict']}；通用收益未验收，不构成合入许可")
    for label, row in (("配置A（历史weak标签）", result["weak"]), ("配置B（历史strong标签）", result["strong"])):
        print(f"  {label} {row['base_passed']}/{row['n']} → {row['new_passed']}/{row['n']}（净 {row['net']:+d}）")
        print(f"    改善 {row['fixed']}；回退 {row['broken']}")
    print("  分差不代表强弱已标定；回退不自动证明因果，也不建议按模型分流绕过。")
    print("  缺失证据：" + ", ".join(result["missing_evidence"]))


def _selftest() -> int:
    # Software checks only; synthetic booleans never certify model improvement.
    rows = [
        (({"a": False}, {"a": True}, {"a": True}, {"a": True}), "INCONCLUSIVE"),
        (({"a": False}, {"a": True}, {"a": False}, {"a": True}), "INCONCLUSIVE"),
        (({"a": True}, {"a": True}, {"a": True}, {"a": True}), "INCONCLUSIVE"),
        (({"a": True}, {"a": False}, {"a": True}, {"a": True}), "FAIL"),
        (({"a": False}, {"a": True}, {"a": True}, {"a": False}), "FAIL"),
    ]
    ok = all(gate(*args)["verdict"] == expected for args, expected in rows)
    for args in [({"a": False}, {"a": True}, {}, {}),
                 ({"a": True}, {"a": True}, {"b": True}, {"b": True})]:
        try:
            gate(*args)
        except GateInputError:
            continue
        ok = False
    print("软件自检通过；未评测真实模型" if ok else "软件自检失败")
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
        result = gate(_load(args.weak_base, "weak-base"), _load(args.weak_new, "weak-new"),
                      _load(args.strong_base, "strong-base"), _load(args.strong_new, "strong-new"))
    except GateInputError as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)
    return 1 if result["verdict"] == "FAIL" else 3


if __name__ == "__main__":
    raise SystemExit(main())

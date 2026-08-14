"""逐题对比两次验收运行：报「28 题里哪几题变了」，不报一个混合分数。

为什么要单独一个工具：`board` 只能告诉你**此刻**的读数。修一处代码后想知道
「到底改动了什么」，需要的是**同一题在两次运行之间的变化**，而不是两个总分之差。
总分相同可能是「一题修好、另一题坏掉」，总分变化也可能全部来自复跑抖动。

噪声分层是这个工具的核心。`board` 自己实测过：同输入复跑，`fact` 判据层
0% 翻转，`product_language` 层 33% 翻转。所以措辞层的单次红绿变化不是信号。
本工具按判据层给每条变化标 signal / noise-suspect，让「变了几题」这个数
可以直接用，不需要每次重新回忆哪一层可信。

用法：
    python3 -m intelligence.eval.acceptance_diff BEFORE... --after AFTER...
    # 不传 --after 时，把 BEFORE 之外的最新一批当作 after
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.eval.acceptance import RUNS_DIR, load_cases
from intelligence.eval.acceptance_verdict import (
    VerdictState,
    compile_case_contract,
    evaluate_case,
    load_verdict_overlay,
)

# 判据层 → 同输入复跑的实测翻转率（来源：board「失败按判据层」脚注）。
# 只登记实测过的；未登记的按未知处理，既不当信号也不当噪声。
_LAYER_FLIP_RATE: dict[str, float] = {
    "fact": 0.0,
    "product_language": 0.33,
}
_NOISE_THRESHOLD = 0.1


@dataclass(frozen=True)
class CaseState:
    case_id: str
    tier: str
    truth: str
    status: str
    degrades: int
    evidence_bound: int
    skills: tuple[str, ...]
    reason_code: str
    elapsed_s: float
    layers: tuple[str, ...]


def _load_runs(paths: list[Path]) -> dict[str, dict[str, Any]]:
    """后出现的 run 覆盖先出现的，与 board 的「取最新」口径一致。"""
    by_id: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"跳过无法读取的 run：{path.name}（{exc}）", file=sys.stderr)
            continue
        for case in payload.get("cases") or []:
            if isinstance(case, dict) and case.get("case_id"):
                by_id[str(case["case_id"])] = case
    return by_id


def _states(runs: dict[str, dict[str, Any]]) -> dict[str, CaseState]:
    cases = load_cases()["cases"]
    overlay = load_verdict_overlay()
    out: dict[str, CaseState] = {}
    for case in cases:
        record = runs.get(case["id"])
        if record is None:
            continue
        verdict = evaluate_case(
            compile_case_contract(case, overlay[case["id"]]), record, observations={}
        )
        turn = (record.get("turns") or [None])[0] or {}
        diagnostic = turn.get("synthesis_diagnostic") or {}
        # 判据层就是 rule.kind（board 的「失败按判据层」同源），只取判失败的那些。
        layers = tuple(
            sorted(
                {
                    str(rule.kind)
                    for rule in verdict.truth.rules
                    if rule.kind and rule.state is VerdictState.FAIL
                }
            )
        )
        out[case["id"]] = CaseState(
            case_id=case["id"],
            tier=str(case.get("tier") or ""),
            truth=verdict.truth.state.name,
            status=str(turn.get("status") or ""),
            degrades=len(turn.get("degrades") or []),
            evidence_bound=int(turn.get("evidence_bound") or 0),
            skills=tuple(turn.get("invoked_skill_ids") or []),
            reason_code=str(diagnostic.get("reason_code") or ""),
            elapsed_s=float(turn.get("elapsed_s") or 0.0),
            layers=layers,
        )
    return out


def _noise_verdict(before: CaseState, after: CaseState) -> str:
    """这条真值变化是信号还是复跑抖动？按涉及的判据层实测翻转率判。"""
    layers = set(before.layers) | set(after.layers)
    if not layers:
        return "signal"
    rates = [_LAYER_FLIP_RATE.get(layer) for layer in layers]
    if any(rate is None for rate in rates):
        return "unknown"
    return "noise-suspect" if max(rates) > _NOISE_THRESHOLD else "signal"


def _fmt_delta(label: str, before: Any, after: Any) -> str | None:
    return None if before == after else f"{label} {before}→{after}"


def cmd_diff(args: argparse.Namespace) -> int:
    before_paths = [Path(p) for p in args.before]
    after_paths = (
        [Path(p) for p in args.after]
        if args.after
        else sorted(set(RUNS_DIR.glob("*.json")) - set(before_paths))[-1:]
    )
    if not after_paths:
        print("没有可用于对比的 after run", file=sys.stderr)
        return 2

    before = _states(_load_runs(before_paths))
    after = _states(_load_runs(after_paths))
    shared = [cid for cid in before if cid in after]
    if not shared:
        # 没有共有题目时打印「无变化」是最坏的结果：它和「真的没变化」长得
        # 一模一样，而后者是你要拿来做决定的。宁可失败退出。
        print(
            f"两侧没有共同题目（before {len(before)} 题 / after {len(after)} 题），无法对比",
            file=sys.stderr,
        )
        return 2

    print(f"# 验收逐题对比 · before {len(before)} 题 → after {len(after)} 题，共有 {len(shared)} 题")
    print(f"before: {', '.join(p.name for p in before_paths)}")
    print(f"after : {', '.join(p.name for p in after_paths)}\n")

    truth_changes: list[tuple[CaseState, CaseState, str]] = []
    observable_only: list[str] = []
    for cid in shared:
        b, a = before[cid], after[cid]
        if b.truth != a.truth:
            truth_changes.append((b, a, _noise_verdict(b, a)))
            continue
        deltas = [
            d
            for d in (
                _fmt_delta("降级", b.degrades, a.degrades),
                _fmt_delta("绑定证据", b.evidence_bound, a.evidence_bound),
                _fmt_delta("skill", list(b.skills), list(a.skills)),
                _fmt_delta("reason_code", b.reason_code or "—", a.reason_code or "—"),
            )
            if d
        ]
        if deltas:
            observable_only.append(f"  {cid:32s} [{b.truth}] {' · '.join(deltas)}")

    if truth_changes:
        print("## 真值判定发生变化")
        for b, a, noise in truth_changes:
            mark = {"signal": "🔵 信号", "noise-suspect": "⚪ 疑似抖动", "unknown": "❔ 噪声未测"}[noise]
            layers = "/".join(sorted(set(b.layers) | set(a.layers))) or "—"
            print(f"  {mark}  {b.case_id:32s} {b.truth} → {a.truth}   判据层={layers}")
    else:
        print("## 真值判定：无变化")

    if observable_only:
        print("\n## 真值未变，但可观测量变了（判据没覆盖到的地方）")
        print("\n".join(observable_only))

    signals = sum(1 for _, _, n in truth_changes if n == "signal")
    print(
        f"\n**结论**：{len(shared)} 题里 {len(truth_changes)} 题真值变化"
        f"（其中 {signals} 题落在低翻转率判据层，可当信号）；"
        f"{len(observable_only)} 题真值未变但可观测量有差异。"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="逐题对比两次验收运行")
    parser.add_argument("before", nargs="+", help="基线 run artifact 路径")
    parser.add_argument("--after", nargs="+", help="对比 run artifact 路径；缺省取最新一份")
    args = parser.parse_args(argv)
    return cmd_diff(args)


if __name__ == "__main__":
    raise SystemExit(main())

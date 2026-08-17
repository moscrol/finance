"""合成健康度四态口径：把「有没有走完合成链」从二分改成四分。

为什么不能二分：``state`` 原先只有 accepted / rejected 两个可聚合值，而
``judge_outage_released``（确定性绑定过了、语义审缺席、带告示放行）也被写成
accepted。2026-08-02 那批 23 个 turn 里 7 个记为 accepted，其中 **6 个的语义审
根本没跑**——按 accepted 计数读出的健康度比真实值高一倍有余。

四态：

- ``full_pass``          走完 brief→composer→judge，语义审真的跑了；
- ``released_unverified``绑定过了但没人审，带告示放行；
- ``template_fallback``  合成没出来，退回确定性模板；
- ``not_synthesized``    压根没进合成（路由/契约原因）。

**旧产物识别**：2026-08-02 之前的 run 没有 ``shadow_status``/``phases`` 字段，
且更早的连 ``synthesis_diagnostic`` 都没有。这类 turn 计入 ``unknown`` 而不是
默认算好——「没测到」和「测到是好的」混为一谈，正是这次要修的那个毛病本身。
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

FULL_PASS = "full_pass"
RELEASED_UNVERIFIED = "released_unverified"
TEMPLATE_FALLBACK = "template_fallback"
NOT_SYNTHESIZED = "not_synthesized"
UNKNOWN = "unknown"

_ORDER = (
    FULL_PASS,
    RELEASED_UNVERIFIED,
    TEMPLATE_FALLBACK,
    NOT_SYNTHESIZED,
    UNKNOWN,
)

_LABELS = {
    FULL_PASS: "完整通过",
    RELEASED_UNVERIFIED: "放行未核验",
    TEMPLATE_FALLBACK: "模板降级",
    NOT_SYNTHESIZED: "未进合成",
    UNKNOWN: "口径未知（旧产物）",
}

# 语义审缺席时正文自带的告示。修复前的产物里 state 写着 accepted，只有这句话
# 能把它认出来——所以旧产物的判定必须靠它，不能只看 state。
_JUDGE_OUTAGE_MARKERS = (
    "语义复核因服务瞬时问题未完成",
    "语义核验因瞬时服务问题未完成",
    "本次未完成独立复核（复核服务超时）",
)


@dataclass(frozen=True)
class TurnHealth:
    case_id: str
    state: str
    reason_code: str
    shadow_status: str
    elapsed_s: float
    # 判定依据：diagnostic 直接给的，还是从正文告示反推的（旧产物）。
    inferred_from_answer: bool


@dataclass(frozen=True)
class RunAnalysis:
    path: Path
    payload: dict[str, Any] | None
    turns: tuple[TurnHealth, ...]
    error: str | None = None


@dataclass(frozen=True)
class HealthAnalysis:
    runs: tuple[RunAnalysis, ...]

    @property
    def counts(self) -> Counter[str]:
        grand: Counter[str] = Counter()
        for run in self.runs:
            grand.update(summarize(list(run.turns)))
        return grand

    @property
    def total(self) -> int:
        return sum(self.counts.values())


@dataclass(frozen=True)
class GateDecision:
    passed: bool
    reasons: tuple[str, ...]


def classify_turn(case_id: str, turn: dict[str, Any]) -> TurnHealth:
    diagnostic = turn.get("synthesis_diagnostic") or {}
    raw_state = str(diagnostic.get("state") or "")
    reason_code = str(diagnostic.get("reason_code") or "")
    shadow_status = str(diagnostic.get("shadow_status") or "")
    answer = str(turn.get("answer") or "")
    elapsed = float(turn.get("elapsed_s") or 0.0)
    inferred = False

    if not raw_state:
        state = UNKNOWN
    elif raw_state == "released_unverified":
        state = RELEASED_UNVERIFIED
    elif raw_state == "accepted":
        # 修复前的产物：state 是 accepted，但正文告示说语义审没跑。以正文为准——
        # 状态字段是自述，正文是它当时实际发出去的东西。
        noticed = any(marker in answer for marker in _JUDGE_OUTAGE_MARKERS)
        if noticed or shadow_status == "judge_outage_released":
            state = RELEASED_UNVERIFIED
            inferred = noticed and not shadow_status
        else:
            state = FULL_PASS
    elif raw_state == "rejected":
        state = TEMPLATE_FALLBACK
    elif raw_state in {"not_prepared", "not_requested"}:
        state = NOT_SYNTHESIZED
    else:  # attempted / failed —— 没走到终态
        state = TEMPLATE_FALLBACK

    return TurnHealth(
        case_id=case_id,
        state=state,
        reason_code=reason_code,
        shadow_status=shadow_status,
        elapsed_s=elapsed,
        inferred_from_answer=inferred,
    )


def classify_run(payload: dict[str, Any]) -> list[TurnHealth]:
    out: list[TurnHealth] = []
    for case in payload.get("cases") or []:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id") or "?")
        for turn in case.get("turns") or []:
            if not isinstance(turn, dict):
                continue
            if str(turn.get("status") or "") != "completed":
                continue
            out.append(classify_turn(case_id, turn))
    return out


def summarize(turns: list[TurnHealth]) -> Counter[str]:
    return Counter(turn.state for turn in turns)


def _phase_note(payload: dict[str, Any]) -> str:
    """这份产物有没有 phase 埋点——没有就说明「哪一段坏的」还是查不出来。"""
    for case in payload.get("cases") or []:
        for turn in (case or {}).get("turns") or []:
            diagnostic = (turn or {}).get("synthesis_diagnostic") or {}
            if diagnostic.get("phases"):
                return "有 phase 埋点"
    return "无 phase 埋点（查不出是哪一段）"


def analyze(paths: list[Path]) -> HealthAnalysis:
    runs: list[RunAnalysis] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            runs.append(
                RunAnalysis(
                    path=path,
                    payload=None,
                    turns=(),
                    error=str(exc),
                )
            )
            continue
        if not isinstance(payload, dict):
            runs.append(
                RunAnalysis(
                    path=path,
                    payload=None,
                    turns=(),
                    error="顶层 JSON 不是对象",
                )
            )
            continue
        runs.append(
            RunAnalysis(
                path=path,
                payload=payload,
                turns=tuple(classify_run(payload)),
            )
        )
    return HealthAnalysis(runs=tuple(runs))


def render_analysis(analysis: HealthAnalysis) -> str:
    lines: list[str] = []
    grand: Counter[str] = Counter()
    for run in analysis.runs:
        if run.error is not None or run.payload is None:
            lines.append(f"跳过 {run.path.name}：{run.error}")
            continue
        payload = run.payload
        turns = list(run.turns)
        counts = summarize(turns)
        grand.update(counts)
        total = sum(counts.values())
        detail = str(payload.get("preflight_detail") or "")
        lines.append(
            f"\n=== {run.path.stem}  {detail}  [{_phase_note(payload)}] ==="
        )
        if not total:
            lines.append("  （无 completed turn）")
            continue
        for state in _ORDER:
            n = counts.get(state, 0)
            if not n:
                continue
            lines.append(f"  {_LABELS[state]:<18} {n:>3d}/{total}")
        inferred = [turn for turn in turns if turn.inferred_from_answer]
        if inferred:
            lines.append(
                f"  ↳ 其中 {len(inferred)} 条是从正文告示反推的"
                f"（该产物早于诊断分态修复）："
                f"{'、'.join(turn.case_id for turn in inferred)}"
            )

    total = sum(grand.values())
    if total:
        lines.append(f"\n=== 合计 {total} 个 completed turn ===")
        for state in _ORDER:
            n = grand.get(state, 0)
            if not n:
                continue
            lines.append(
                f"  {_LABELS[state]:<18} {n:>3d}/{total}  ({n / total:.0%})"
            )
        healthy = grand.get(FULL_PASS, 0)
        lines.append(
            f"\n真实完整通过率：{healthy}/{total} = {healthy / total:.0%}"
        )
        lines.append(
            "  注：放行未核验不计入通过——绑定过了但没有第二意见，"
            "把它算进健康数就是这次要修的那个错。"
        )
    return "\n".join(lines)


def render(paths: list[Path]) -> str:
    return render_analysis(analyze(paths))


def evaluate_gate(
    analysis: HealthAnalysis,
    *,
    min_full_pass: float,
    fail_on_unknown: bool,
) -> GateDecision:
    reasons: list[str] = []
    for run in analysis.runs:
        if run.error is not None:
            reasons.append(f"{run.path.name}: 输入不可读")
        elif not run.turns:
            reasons.append(f"{run.path.name}: 没有 completed turn")

    counts = analysis.counts
    total = sum(counts.values())
    if total:
        full_pass_rate = counts.get(FULL_PASS, 0) / total
        if full_pass_rate < min_full_pass:
            reasons.append(
                "真实完整通过率"
                f" {full_pass_rate:.0%} 低于门槛 {min_full_pass:.0%}"
            )
    elif not reasons:
        reasons.append("没有可评估的 completed turn")

    unknown = counts.get(UNKNOWN, 0)
    if fail_on_unknown and unknown:
        reasons.append(f"存在 {unknown} 个口径未知 turn")
    return GateDecision(passed=not reasons, reasons=tuple(reasons))


def _full_pass_ratio(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是 0 到 1 之间的数字") from exc
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError("必须是有限的 0 到 1 之间的数字")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="synthesis-health",
        description="合成健康度四态口径（可直接跑在历史 run 产物上）",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="启用阻塞门禁；默认要求 100% full_pass",
    )
    parser.add_argument(
        "--min-full-pass",
        type=_full_pass_ratio,
        default=None,
        metavar="RATIO",
        help="门禁要求的最低真实完整通过率（0..1）",
    )
    parser.add_argument(
        "--fail-on-unknown",
        action="store_true",
        help="门禁遇到旧口径 unknown turn 时失败",
    )
    parser.add_argument("runs", nargs="+", help="run artifact 路径，可多个")
    args = parser.parse_args(argv)
    if not args.gate and (
        args.min_full_pass is not None or args.fail_on_unknown
    ):
        parser.error("--min-full-pass/--fail-on-unknown 必须与 --gate 同用")

    analysis = analyze([Path(item) for item in args.runs])
    print(render_analysis(analysis))
    if args.gate:
        decision = evaluate_gate(
            analysis,
            min_full_pass=(
                args.min_full_pass if args.min_full_pass is not None else 1.0
            ),
            fail_on_unknown=args.fail_on_unknown,
        )
        if not decision.passed:
            for reason in decision.reasons:
                print(f"门禁失败：{reason}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())

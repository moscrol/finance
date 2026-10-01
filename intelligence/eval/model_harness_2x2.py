"""模型 × harness 2×2 对照的冻结工具：排程（plan）与判定（analyze）。

预注册：``docs/superpowers/specs/2026-09-30-model-harness-2x2-preregistration.md``。
§5（运行规则）与 §6（判定规则）在这里写成代码，并在开跑前冻结：读数出来以后，
判定只能由本模块算，不许手算，也不许换口径。改这里的常量等于改预注册，开跑后禁止。

四格：harness P（产品 continuous）/ R（薄 ReAct 控制台）× 模型 G（``glm-5.3-flash``）/
C（Claude）。格名 = harness 字母 + 模型字母：``PG`` ``PC`` ``RG`` ``RC``。

**排程**（``build_plan``）：题集 = unseen D1–D10 + 从 seen 组按固定种子抽 10 题；
每轮题序用同一个种子的随机数打乱，同一题的四格按拉丁方 ``(题位 + 轮次) % 4`` 轮转先后，
让时段漂移平均摊到四格。每行带 provider，供 Mac 上的运行器按 provider 串行、限流。

**判定**（``analyze``）输入是逐次运行记录（JSONL，每行一个对象）：

- ``seq``：全局尝试序号（整数，唯一；重排的运行拿新的、更大的号）
- ``question``、``cell``（``PG``/``PC``/``RG``/``RC``）
- ``admission_exit``：``check_model_admission.py`` 的退出码；缺失按「无证据」处理
- ``artifact``：这次运行的产物路径（run 目录或 ``continuous-episode.json``）。命令行
  ``analyze`` 默认**按它重算准入**（含子分支，见 ``model_admission``），不信自报的
  ``admission_exit``；没有 ``artifact`` 的运行作废为 ``admission_unverified``，除非显式
  ``--trust-self-reported-admission``（2026-10-01 审查：准入要全程自动生效，不能靠人记得跑脚本）
- ``failure_class``：``stable_llm_fallback_reason``，没有失败写 ``null``
- ``score``：machine-truth rate ∈ [0, 1]；有效运行必须有分（答错、缺数、自家 deadline
  烧完都照常计分，这些正是要测的能力）

作废：准入 exit ≠ 0，或 failure_class 属 provider 侧故障。作废不计 0 分；每格每题
按 ``seq`` 取前 N 次有效。作废超过 2 次、或有效不足 N 次 → 该格不完整，不下主结论。

纯标准库，外加仓内 ``variance_baseline``：噪声底与验收「方差门」用同一份实现。
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from intelligence.eval import model_admission
from intelligence.eval.variance_baseline import ab_decision, mode_of, per_question_flip_rate

PLAN_SCHEMA = "model_harness_2x2.plan.v1"
ANALYSIS_SCHEMA = "model_harness_2x2.analysis.v1"

SEED = 20260930
CELLS: tuple[str, ...] = ("PG", "PC", "RG", "RC")
DEFAULT_MODELS = {"G": "glm-5.3-flash", "C": ""}  # C 的确切 ID 在 Mac 上从 08-27 react 臂产物读
PROVIDERS = {"G": "zhipu", "C": "anthropic"}
DEFAULT_REPS = 3
SEEN_SAMPLE_SIZE = 10
UNSEEN_QUESTIONS: tuple[str, ...] = tuple(f"D{i}" for i in range(1, 11))
SENSITIVITY_EXCLUDE: tuple[str, ...] = ("D2", "D5", "D6")
MIN_EFFECT = 0.10
BOOTSTRAP_ITERATIONS = 10_000
CI_LEVEL = 0.95
MAX_REQUEUES = 2
VOID_FAILURE_CLASSES = frozenset(
    {"provider_rate_limited", "provider_overloaded", "provider_unavailable"}
)
# 比较前统一取 9 位小数：分数是 1/k 的均值，真实差距 ≥1e-3，浮点噪声 ~1e-16，
# 不取整会把恰好 0.10 的效应算成 0.0999…、恰好等于噪声底的算成「低于」。
_DIGITS = 9

DECISIONS = {
    "model_only": "差距主要来自模型",
    "harness_only_react_better": "差距主要来自 harness（薄 ReAct 优于产品）",
    "harness_only_product_better": "产品 harness 优于薄 ReAct，模型差不可判",
    "both": "模型与 harness 两边都有",
    "neither": "差距在本样本量下不可复现",
    "incomplete": "有格不完整，不下主结论",
}


class DesignError(ValueError):
    """输入不符合预注册（题集、记录字段、格名……）。"""


# ── 排程 ────────────────────────────────────────────────────────────────


def select_questions(
    seen: Iterable[str],
    *,
    unseen: Sequence[str] = UNSEEN_QUESTIONS,
    k: int = SEEN_SAMPLE_SIZE,
    seed: int = SEED,
) -> tuple[list[str], list[str]]:
    """返回 (题集, 抽中的 seen 题)。抽法与预注册逐字一致：
    ``random.Random(seed).sample(sorted(seen), k)``。"""

    pool = sorted(set(seen))
    overlap = sorted(set(pool) & set(unseen))
    if overlap:
        raise DesignError(f"seen 与 unseen 重叠：{overlap}")
    if len(set(unseen)) != len(unseen):
        raise DesignError("unseen 题号有重复")
    if len(pool) < k:
        raise DesignError(f"seen 只有 {len(pool)} 题，不够抽 {k} 题")
    picked = random.Random(seed).sample(pool, k)
    return list(unseen) + picked, picked


def latin_square_cells(position: int, round_index: int) -> tuple[str, ...]:
    """同一题四格的先后：按 ``(题位 + 轮次) % 4`` 轮转。轮次从 0 起。"""

    shift = (position + round_index) % len(CELLS)
    return CELLS[shift:] + CELLS[:shift]


def build_plan(
    questions: Sequence[str],
    *,
    reps: int = DEFAULT_REPS,
    seed: int = SEED,
    models: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    if reps < 1:
        raise DesignError("reps 至少为 1")
    if len(set(questions)) != len(questions) or not questions:
        raise DesignError("题集为空或有重复")
    chosen = {**DEFAULT_MODELS, **(models or {})}
    if not all(chosen.get(slot) for slot in ("G", "C")):
        raise DesignError("G / C 两个模型 ID 都要给（C 读 08-27 react 臂产物，读不出就写明替代）")
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for round_index in range(reps):
        order = list(questions)
        rng.shuffle(order)
        for position, question in enumerate(order):
            for cell in latin_square_cells(position, round_index):
                rows.append(
                    {
                        "seq": len(rows) + 1,
                        "round": round_index + 1,
                        "question": question,
                        "cell": cell,
                        "model": chosen[cell[1]],
                        "provider": PROVIDERS[cell[1]],
                    }
                )
    return rows


def plan_document(
    seen: Iterable[str],
    *,
    unseen: Sequence[str] = UNSEEN_QUESTIONS,
    reps: int = DEFAULT_REPS,
    models: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    questions, picked = select_questions(seen, unseen=unseen)
    runs = build_plan(questions, reps=reps, models=models)
    return {
        "schema": PLAN_SCHEMA,
        "seed": SEED,
        "reps": reps,
        "questions": questions,
        "unseen": list(unseen),
        "seen_sampled": picked,
        "models": {**DEFAULT_MODELS, **(models or {})},
        "providers": dict(PROVIDERS),
        "runs": runs,
    }


# ── 判定 ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Run:
    seq: int
    question: str
    cell: str
    score: float | None
    admission_exit: int | None
    failure_class: str | None
    admission_source: str = "self_reported"

    def void_reason(self) -> str | None:
        if self.admission_exit is None:
            return "admission_unverified" if self.admission_source == "unverified" else "admission_missing"
        if self.admission_exit != 0:
            return f"admission_exit_{self.admission_exit}"
        if self.failure_class in VOID_FAILURE_CLASSES:
            return str(self.failure_class)
        return None


def parse_runs(records: Iterable[Mapping[str, Any]]) -> list[Run]:
    runs: list[Run] = []
    seen_seq: set[int] = set()
    for index, record in enumerate(records, start=1):
        try:
            seq = int(record["seq"])
            question = str(record["question"])
            cell = str(record["cell"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DesignError(f"第 {index} 条记录缺 seq / question / cell：{exc}") from exc
        if cell not in CELLS:
            raise DesignError(f"第 {index} 条记录格名 {cell!r} 不在 {CELLS}")
        if seq in seen_seq:
            raise DesignError(f"seq {seq} 重复")
        seen_seq.add(seq)
        raw_exit = record.get("admission_exit")
        raw_score = record.get("score")
        run = Run(
            seq=seq,
            question=question,
            cell=cell,
            score=None if raw_score is None else float(raw_score),
            admission_exit=None if raw_exit is None else int(raw_exit),
            failure_class=record.get("failure_class") or None,
            admission_source=str(record.get("admission_source") or "self_reported"),
        )
        if run.void_reason() is None and (run.score is None or not 0.0 <= run.score <= 1.0):
            raise DesignError(f"seq {seq} 是有效运行，但 score={raw_score!r} 不在 [0, 1]（失败也要照常计分）")
        runs.append(run)
    return runs


def select_valid(
    runs: Sequence[Run], questions: Sequence[str], *, reps: int = DEFAULT_REPS
) -> tuple[dict[tuple[str, str], list[float]], list[dict[str, Any]], Counter[str]]:
    """每格每题按 seq 取前 ``reps`` 次有效；返回 (分数, 不完整明细, 作废原因计数)。"""

    by_key: dict[tuple[str, str], list[Run]] = {}
    for run in runs:
        by_key.setdefault((run.question, run.cell), []).append(run)
    scores: dict[tuple[str, str], list[float]] = {}
    incomplete: list[dict[str, Any]] = []
    voids: Counter[str] = Counter()
    for question in questions:
        for cell in CELLS:
            taken: list[float] = []
            void_count = 0
            for run in sorted(by_key.get((question, cell), []), key=lambda item: item.seq):
                if len(taken) == reps:
                    break
                reason = run.void_reason()
                if reason is None:
                    taken.append(float(run.score))  # type: ignore[arg-type]
                    continue
                voids[reason] += 1
                void_count += 1
                if void_count > MAX_REQUEUES:
                    break
            scores[(question, cell)] = taken
            if len(taken) < reps:
                incomplete.append(
                    {"question": question, "cell": cell, "valid": len(taken), "voids": void_count}
                )
    return scores, incomplete, voids


def outcome_label(score: float) -> str:
    """方差门的三档标签：满分 / 部分 / 零分。"""

    if score >= 1.0 - 10**-_DIGITS:
        return "full"
    if score <= 10**-_DIGITS:
        return "zero"
    return "partial"


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def bootstrap_ci(
    rows: Sequence[Sequence[float]],
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = SEED,
    level: float = CI_LEVEL,
) -> list[tuple[float, float]]:
    """以题为单位有放回重抽，逐列求均值的百分位区间。

    抽样用 ``int(random() * n)``：只依赖 ``random()``，跨 Python 版本可复现。
    下界取第 ``ceil(α/2·B)`` 小的值，上界取第 ``ceil((1−α/2)·B)`` 小的值。
    """

    n = len(rows)
    width = len(rows[0])
    rng = random.Random(seed)
    draws: list[list[float]] = [[] for _ in range(width)]
    for _ in range(iterations):
        sums = [0.0] * width
        for _ in range(n):
            row = rows[int(rng.random() * n)]
            for column in range(width):
                sums[column] += row[column]
        for column in range(width):
            draws[column].append(sums[column] / n)
    alpha = 1.0 - level
    low_index = math.ceil(alpha / 2 * iterations) - 1
    high_index = math.ceil((1 - alpha / 2) * iterations) - 1
    bounds = []
    for column in draws:
        column.sort()
        bounds.append((column[low_index], column[high_index]))
    return bounds


def gate(value: float, ci: tuple[float, float], floor: float) -> dict[str, Any]:
    """可判 = 过方差门（|Δ| ≥ 噪声底）且过最小效应（|Δ| ≥ 0.10）且 95% 区间不含 0。"""

    value_r, floor_r = round(value, _DIGITS), round(floor, _DIGITS)
    low, high = round(ci[0], _DIGITS), round(ci[1], _DIGITS)
    checks = {
        "floor": ab_decision(value_r, floor_r) == "callable",
        "min_effect": abs(value_r) >= MIN_EFFECT,
        "ci_excludes_zero": low > 0 or high < 0,
    }
    return {
        "value": value_r,
        "ci": [low, high],
        "checks": checks,
        "callable": all(checks.values()),
    }


def decide(delta_m: Mapping[str, Any], delta_h: Mapping[str, Any]) -> str:
    if delta_m["callable"] and delta_h["callable"]:
        return "both"
    if delta_m["callable"]:
        return "model_only"
    if delta_h["callable"]:
        return "harness_only_react_better" if delta_h["value"] > 0 else "harness_only_product_better"
    return "neither"


def _direction(value: float, positive: str, negative: str) -> str:
    return positive if value > 0 else negative if value < 0 else "="


_SIMPLE_EFFECTS = {
    "model_within_P": ("PC", "PG"),
    "model_within_R": ("RC", "RG"),
    "harness_within_G": ("RG", "PG"),
    "harness_within_C": ("RC", "PC"),
}


def analyze_subset(
    scores: Mapping[tuple[str, str], Sequence[float]],
    questions: Sequence[str],
    *,
    reps: int = DEFAULT_REPS,
    iterations: int = BOOTSTRAP_ITERATIONS,
) -> dict[str, Any]:
    """在给定题集上算格均值、噪声底、ΔM / ΔH / I、三条可判检验与判定。"""

    if not questions:
        raise DesignError("题集为空")
    complete = [c for c in CELLS if all(len(scores.get((q, c), ())) >= reps for q in questions)]
    incomplete = [c for c in CELLS if c not in complete]
    qmean = {
        (q, c): _mean(list(scores[(q, c)])[:reps]) for q in questions for c in complete
    }
    flips = {
        c: _mean(
            [per_question_flip_rate([outcome_label(s) for s in list(scores[(q, c)])[:reps]]) for q in questions]
        )
        for c in complete
    }
    modes = {
        c: dict(Counter(mode_of([outcome_label(s) for s in list(scores[(q, c)])[:reps]]) for q in questions))
        for c in complete
    }
    floor = max(flips.values()) if flips else 0.0
    result: dict[str, Any] = {
        "questions": list(questions),
        "n_questions": len(questions),
        "complete_cells": complete,
        "incomplete_cells": incomplete,
        "cell_means": {c: round(_mean([qmean[(q, c)] for q in questions]), _DIGITS) for c in complete},
        "cell_flip_rates": {c: round(v, _DIGITS) for c, v in flips.items()},
        "cell_mode_labels": modes,
        "noise_floor": round(floor, _DIGITS),
    }
    if incomplete:
        pairs = {name: pair for name, pair in _SIMPLE_EFFECTS.items() if set(pair) <= set(complete)}
        rows = [[qmean[(q, a)] - qmean[(q, b)] for a, b in pairs.values()] for q in questions]
        bounds = bootstrap_ci(rows, iterations=iterations) if pairs else []
        result["simple_effects"] = {
            name: {**gate(_mean([row[i] for row in rows]), bounds[i], floor), "cells": list(pair)}
            for i, (name, pair) in enumerate(pairs.items())
        }
        result["decision"] = "incomplete"
        return result
    rows = []
    for q in questions:
        pg, pc, rg, rc = (qmean[(q, c)] for c in CELLS)
        rows.append([((pc - pg) + (rc - rg)) / 2, ((rg - pg) + (rc - pc)) / 2, (rc - pc) - (rg - pg)])
    bounds = bootstrap_ci(rows, iterations=iterations)
    effects = {
        name: gate(_mean([row[i] for row in rows]), bounds[i], floor)
        for i, name in enumerate(("delta_m", "delta_h", "interaction"))
    }
    dm, dh, di = effects["delta_m"], effects["delta_h"], effects["interaction"]
    result["effects"] = effects
    result["decision"] = decide(dm, dh)
    result["direction"] = {
        "model": _direction(dm["value"], "C>G", "G>C"),
        "harness": _direction(dh["value"], "R>P", "P>R"),
    }
    result["hypotheses"] = {
        # H1：差距主要来自模型——ΔM 可判、方向是 Claude 更好、且大于 harness 效应
        "H1": bool(dm["callable"] and dm["value"] > 0 and abs(dm["value"]) > abs(dh["value"])),
        # H2：差距主要来自 harness——ΔH 可判、方向是 ReAct 更好、且大于模型效应
        "H2": bool(dh["callable"] and dh["value"] > 0 and abs(dh["value"]) > abs(dm["value"])),
        "H3": bool(di["callable"]),
    }
    return result


def analyze(
    records: Iterable[Mapping[str, Any]],
    *,
    questions: Sequence[str] | None = None,
    unseen: Sequence[str] = UNSEEN_QUESTIONS,
    exclude: Sequence[str] = SENSITIVITY_EXCLUDE,
    reps: int = DEFAULT_REPS,
    iterations: int = BOOTSTRAP_ITERATIONS,
) -> dict[str, Any]:
    runs = parse_runs(records)
    if questions is None:
        questions = sorted({run.question for run in runs})
    unknown = sorted({run.question for run in runs} - set(questions))
    if unknown:
        raise DesignError(f"记录里有题集外的题：{unknown}")
    scores, incomplete, voids = select_valid(runs, questions, reps=reps)
    primary = analyze_subset(scores, questions, reps=reps, iterations=iterations)

    def secondary(label: str, subset: list[str], missing: list[str]) -> dict[str, Any]:
        if missing:
            return {"skipped": f"题号不在题集里：{'、'.join(missing)}", "label": label}
        if not subset:
            return {"skipped": "子集为空", "label": label}
        out = analyze_subset(scores, subset, reps=reps, iterations=iterations)
        out["label"] = label
        out["agrees_with_primary"] = out["decision"] == primary["decision"]
        return out

    unseen_subset = [q for q in questions if q in set(unseen)]
    sensitivity_subset = [q for q in questions if q not in set(exclude)]
    return {
        "schema": ANALYSIS_SCHEMA,
        "reps": reps,
        "questions": list(questions),
        "attempts": len(runs),
        "voids": {"total": sum(voids.values()), "by_reason": dict(sorted(voids.items()))},
        "incomplete": incomplete,
        "primary": {**primary, "label": "primary"},
        "secondary_unseen": secondary(
            "unseen_only", unseen_subset, [] if unseen_subset else sorted(set(unseen))
        ),
        "sensitivity": secondary(
            "exclude_" + "_".join(exclude),
            sensitivity_subset,
            sorted(set(exclude) - set(questions)),
        ),
        "rules": {
            "min_effect": MIN_EFFECT,
            "bootstrap_iterations": iterations,
            "bootstrap_seed": SEED,
            "ci_level": CI_LEVEL,
            "max_requeues": MAX_REQUEUES,
            "void_failure_classes": sorted(VOID_FAILURE_CLASSES),
        },
    }


def recompute_admission(
    records: Iterable[Mapping[str, Any]],
    models: Mapping[str, str],
    *,
    episode_store: str | None = None,
    trust_self_reported: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """按每次运行的产物重算生效模型准入，覆盖自报的 ``admission_exit``。

    期望模型取 plan 的 ``models``（格名第二个字母：G / C）。有 ``artifact`` → 用
    ``model_admission.check_paths`` 重算（含子分支）；自报值与重算不一致的逐条列出。
    没有 ``artifact``：默认记 ``unverified``（作废）；``trust_self_reported=True`` 才沿用自报。
    """

    out: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "recomputed": 0, "self_reported": 0, "unverified": 0, "disagreements": [],
        "trust_self_reported": trust_self_reported,
    }
    for record in records:
        row = dict(record)
        cell = str(row.get("cell") or "")
        expected = str(models.get(cell[1:2]) or "").strip() if len(cell) == 2 else ""
        artifact = row.get("artifact")
        if artifact:
            if not expected:
                raise DesignError(f"seq {row.get('seq')}：plan 里没有 {cell} 格的期望模型，重算不了准入")
            code = model_admission.overall_exit_code(
                model_admission.check_paths([str(artifact)], [expected], episode_store=episode_store)
            )
            reported = row.get("admission_exit")
            if reported is not None and int(reported) != code:
                summary["disagreements"].append({"seq": row.get("seq"), "reported": int(reported), "recomputed": code})
            row["admission_exit"] = code
            row["admission_source"] = "recomputed"
            summary["recomputed"] += 1
        elif trust_self_reported:
            row["admission_source"] = "self_reported"
            summary["self_reported"] += 1
        else:
            row["admission_exit"] = None
            row["admission_source"] = "unverified"
            summary["unverified"] += 1
        out.append(row)
    return out, summary


# ── 渲染 ────────────────────────────────────────────────────────────────


def _fmt(value: float) -> str:
    return f"{value:+.3f}"


def _render_effect(name: str, effect: Mapping[str, Any]) -> str:
    checks = effect["checks"]
    marks = " · ".join(
        f"{label} {'✓' if checks[key] else '✗'}"
        for key, label in (("floor", "≥噪声底"), ("min_effect", f"≥{MIN_EFFECT:.2f}"), ("ci_excludes_zero", "区间不含 0"))
    )
    low, high = effect["ci"]
    verdict = "✅ 可判" if effect["callable"] else "❌ 不可判"
    return f"{name} {_fmt(effect['value'])}  95%CI [{_fmt(low)}, {_fmt(high)}]  {verdict}（{marks}）"


def render_subset(result: Mapping[str, Any]) -> list[str]:
    lines = [
        "格均值："
        + " · ".join(f"{c} {v:.3f}" for c, v in result["cell_means"].items())
        + (f"；不完整：{'、'.join(result['incomplete_cells'])}" if result["incomplete_cells"] else ""),
        f"噪声底 {result['noise_floor']:.3f}（四格翻转率最大值；"
        + " · ".join(f"{c} {v:.3f}" for c, v in result["cell_flip_rates"].items())
        + "）",
    ]
    if result["decision"] == "incomplete":
        for name, effect in result.get("simple_effects", {}).items():
            lines.append("仅供参考 · " + _render_effect(f"{name}（{'−'.join(effect['cells'])}）", effect))
    else:
        for key, name in (("delta_m", "ΔM"), ("delta_h", "ΔH"), ("interaction", "I ")):
            lines.append(_render_effect(name, result["effects"][key]))
    return lines


def render(report: Mapping[str, Any]) -> str:
    primary = report["primary"]
    voids = report["voids"]
    lines = [
        "模型 × harness 2×2 判定（预注册 2026-09-30 §6，冻结规则）",
        f"题数 {len(report['questions'])} · 每格每题取前 {report['reps']} 次有效 · 共 {report['attempts']} 次尝试 · "
        f"作废 {voids['total']} 次"
        + (f"（{'、'.join(f'{k} {v}' for k, v in voids['by_reason'].items())}）" if voids["total"] else ""),
    ]
    lines += render_subset(primary)
    decision = primary["decision"]
    headline = f"判定：{decision} —— {DECISIONS[decision]}"
    if decision != "incomplete":
        headline += f"（模型 {primary['direction']['model']} · harness {primary['direction']['harness']}）"
        hyp = primary["hypotheses"]
        lines.append(headline)
        lines.append(
            "假设："
            + " · ".join(f"{name} {'成立' if hyp[name] else '不成立'}" for name in ("H1", "H2", "H3"))
            + (" · 交互可判，单独报告" if hyp["H3"] else "")
        )
    else:
        lines.append(headline)
        detail = "、".join(f"{row['cell']}/{row['question']}（有效 {row['valid']}，作废 {row['voids']}）" for row in report["incomplete"][:8])
        lines.append(f"不完整明细：{detail}")
    for key, title in (("secondary_unseen", "次要（只看 unseen）"), ("sensitivity", "敏感性（去掉被针对性修过的题）")):
        sub = report[key]
        if "skipped" in sub:
            lines.append(f"{title}：未执行——{sub['skipped']}")
            continue
        agree = "与主判定一致" if sub["agrees_with_primary"] else "⚠️ 与主判定不同"
        lines.append(f"{title}，{sub['n_questions']} 题：判定 {sub['decision']}（{agree}）")
        if key == "sensitivity" and not sub["agrees_with_primary"]:
            lines.append("  → 报告时须写明：主结论依赖被针对性修过的题")
    return "\n".join(lines)

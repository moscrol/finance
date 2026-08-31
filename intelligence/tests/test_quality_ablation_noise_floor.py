"""消融读数的方差门：同文本重评量出当次判官噪声，读数必须跨过它才算数。

守的失败形状（2026-08-26 真实发生过）：`run_quality_ablation` 报出
reading-baseline **−0.4 分**，交接文档据此写下「建议默认关或按题型门控」。
那一轮 6 题、单 judge、单次采样，而两天后 2026-08-28 实测同一批判官对
**逐字相同**的答案能打出 12/13/15——散布比那个 −0.4 大一个量级。
读数没有方差底就不成立，而缺方差底时它长得和成立的读数一模一样。
"""

from __future__ import annotations

from datetime import datetime, timezone

from scripts import rejudge_quality_ablation as rejudge
from scripts.run_quality_ablation import (
    RUBRIC_DIMENSIONS,
    aggregate_components,
    judge_noise_floor,
    threshold_for,
)

_NOW = datetime(2026, 8, 31, 1, 30, tzinfo=timezone.utc)

# 2026-08-28 实测的一组同文本重评分数（index-rebound-space 三臂答案 md5 完全相同，
# 盲评打出 12/13/15）。
#
# ⚠ 它在本文件里**只是算术夹具**，用来验门槛公式，**不是任何一轮的噪声底**。
# 一轮的底只能来自那一轮自己的校准（本模块的整条规则就是这个）。
# 2026-08-31 质检点名：本文件初版拿它去「重判」2026-08-26 那轮的三份读数，
# 并据此写出「evidence-judge +2.8 → callable」——那正是**引用历史噪声底**，
# 是生产路径 fail-closed 拦住、而叙述层自己破了的那条规则。
# 正确判定见 `test_没做校准的那一轮三份读数全部no_call`。
_IDENTICAL_TEXT_SCORES = [12, 13, 15]


def _judged_total(total: int) -> dict[str, object]:
    base, rem = divmod(total, len(RUBRIC_DIMENSIONS))
    values = [base + (1 if i < rem else 0) for i in range(len(RUBRIC_DIMENSIONS))]
    return {
        "scored": True,
        "scores": dict(zip(RUBRIC_DIMENSIONS, values)),
        "total": total,
        "normalized": round(total / 20.0, 4),
        "justification": "桩",
        "attempts": 1,
    }


def _answer(arm: str, case_id: str, total: int) -> dict[str, object]:
    return {
        "arm": arm,
        "case_id": case_id,
        "ok": True,
        "answer": f"{arm}/{case_id} 的答案正文" * 20,
        "elapsed_sec": 12.0,
        "judge": _judged_total(total),
    }


def _calibration(case_ids: list[str], totals: list[int]) -> list[dict[str, object]]:
    return [{"case_id": cid, "totals": list(totals), "repeats": []} for cid in case_ids]


def _arms(baseline: list[int], ablated: list[int], *, arm: str) -> list[dict[str, object]]:
    """构造 n 题的基线臂 + 关断臂。"""

    rows: list[dict[str, object]] = []
    for i, total in enumerate(baseline):
        rows.append(_answer("baseline", f"q{i}", total))
    for i, total in enumerate(ablated):
        rows.append(_answer(arm, f"q{i}", total))
    return rows


# --------------------------------------------------------------- 噪声怎么量


def test_同文本重评的散布就是当次判官噪声():
    floor = judge_noise_floor(_calibration(["q0"], _IDENTICAL_TEXT_SCORES))

    assert floor["measured"] is True
    # variance([12,13,15]) = 2.3333 → sd = 1.5275
    assert floor["sd_judging"] == 1.5275
    # 单题 Δ 是两次独立评分之差 → sd × √2
    assert floor["sd_delta_single_question"] == 2.1602
    assert floor["questions"][0]["spread"] == 3


def test_重复不足两次的题不计入方差():
    floor = judge_noise_floor(
        [
            {"case_id": "q0", "totals": [13]},
            {"case_id": "q1", "totals": _IDENTICAL_TEXT_SCORES},
        ]
    )

    assert floor["questions_measured"] == 1
    assert floor["questions"][0]["usable"] is False
    assert floor["questions"][1]["usable"] is True


def test_可用题越少门槛越高():
    """门槛是均值的标准误，按 1/√n 收缩——可用题少的组件本就该要更大的 Δ。"""

    floor = judge_noise_floor(_calibration(["q0"], _IDENTICAL_TEXT_SCORES))

    assert threshold_for(floor, 1) > threshold_for(floor, 5) > threshold_for(floor, 20)
    assert threshold_for(floor, 4) == round(threshold_for(floor, 1) / 2, 4)


# ------------------------------------------------------------- fail-closed


def test_没实测方差时一律no_call():
    """缺方差底 ≠ 默认放行。这条不成立的话，旧收据会静默地继续发可下结论的读数。"""

    floor = judge_noise_floor([])
    assert floor["measured"] is False

    answers = _arms([20, 20, 20], [5, 5, 5], arm="kb-rag")  # Δ 极大
    agg = aggregate_components(answers, ["kb-rag"], noise_floor=floor)["kb-rag"]

    assert agg["marginal_contribution_total"] == 15.0
    assert agg["decision"] == "no_call"
    assert agg["noise_threshold"] is None
    assert "未实测判官方差" in agg["decision_reason"]


def test_压根不传方差底也是no_call():
    answers = _arms([20, 20, 20], [5, 5, 5], arm="kb-rag")
    agg = aggregate_components(answers, ["kb-rag"])["kb-rag"]

    assert agg["decision"] == "no_call"


def test_无可用题时不下结论也不报门槛():
    floor = judge_noise_floor(_calibration(["q0"], _IDENTICAL_TEXT_SCORES))
    answers = [
        _answer("baseline", "q0", 13),
        {**_answer("kb-rag", "q0", 13), "judge": {"scored": False, "reason": "judge 挂了"}},
    ]
    agg = aggregate_components(answers, ["kb-rag"], noise_floor=floor)["kb-rag"]

    assert agg["marginal_contribution_total"] is None
    assert agg["decision"] == "no_call"
    assert agg["questions_usable"] == 0


# ------------------------------------------- 历史那一轮的正确判定是什么


def test_没做校准的那一轮三份读数全部no_call():
    """2026-08-26 那轮**没有做同文本校准**（那时还没有 --calibration-repeats）。

    所以按本模块的规则，它的三份读数（+2.8 / +1.5 / −0.4）**全部是 `no_call`**，
    与 Δ 多大无关。不许借 2026-08-28 那组 12/13/15 当它的底——
    「不回退历史噪声底」是本单的核心规则，2026-08-31 质检抓到本文件初版
    自己破了它：拿借来的底判出「+2.8 → callable」。

    这条测试就是那次纠偏的钉子：**缺校准的轮次，多大的 Δ 都不下结论。**
    """

    for edge in (3.0, 1.5, 0.0):  # 覆盖 +2.8 / +1.5 / −0.4 三档量级
        answers = _arms([14] * 5, [round(14 - edge)] * 5, arm="kb-rag")
        agg = aggregate_components(answers, ["kb-rag"], noise_floor=None)["kb-rag"]
        assert agg["decision"] == "no_call", f"Δ={edge} 无校准时不得放行"
        assert agg["noise_threshold"] is None


def test_门槛公式在给定散布下的取值():
    """纯算术：给定一组同文本重评分数与题数，门槛应是多少。

    这里的输入是**夹具**，不代表任何一轮的真实噪声底——判定某一轮要用那一轮
    自己的校准。分开写是为了不让算术验证再次伪装成历史重判。
    """

    floor = judge_noise_floor(_calibration(["q0"], _IDENTICAL_TEXT_SCORES))

    assert threshold_for(floor, 5) == 1.9321
    # 可用题数不同门槛就不同——kb-rag 那份实际只有 4 题可用（收据 questions_usable=4），
    # 拿 5 去算是偷了一题的把握。本轮质检点名的第二处数字错。
    assert threshold_for(floor, 4) == 2.1602
    assert threshold_for(floor, 4) > threshold_for(floor, 5)


def test_噪声底只覆盖判官方差这件事要写进收据():
    """限定语必须随读数走。它不在收据里，下一个 agent 就会把下界当成全部噪声。"""

    floor = judge_noise_floor(_calibration(["q0"], _IDENTICAL_TEXT_SCORES))

    assert "不含 ask 侧重跑方差" in str(floor["covers"])
    assert "下界" in str(floor["covers"])


# ------------------------------------------------------------------ 补评侧


def _artifact_with_floor(floor: dict[str, object] | None) -> dict[str, object]:
    answers = _arms([14, 14, 14, 14, 14], [11, 11, 11, 11, 11], arm="kb-rag")
    artifact: dict[str, object] = {
        "kind": "quality_ablation",
        "generated_at": "2026-08-31T00:00:00+00:00",
        "seed": 20260831,
        "judge_note": "桩",
        "questions": [
            {"case_id": f"q{i}", "text": f"问题 q{i}", "as_of": "2026-07-22"}
            for i in range(5)
        ],
        "answers": answers,
        "aggregates": aggregate_components(answers, ["kb-rag"], noise_floor=floor),
    }
    if floor is not None:
        artifact["noise_floor"] = floor
    return artifact


def _rejudge(artifact: dict[str, object]) -> dict[str, object]:
    return rejudge.rejudge_artifact(
        artifact,
        judge_fn=lambda question, answer: _judged_total(13),
        seed=1,
        source_path="/tmp/source.json",
        source_sha256="deadbeef",
        now=_NOW,
    )


def test_补评沿用源轮实测的方差底():
    """补评只补 unscored 的份，没有重新校准判官——凭空给个新底就是编数。"""

    floor = judge_noise_floor(_calibration(["q0"], _IDENTICAL_TEXT_SCORES))
    out = _rejudge(_artifact_with_floor(floor))

    assert out["noise_floor"] == floor
    assert out["aggregates"]["kb-rag"]["decision"] == "callable"  # Δ=3.0 > 1.9321


def test_源轮没方差底时补评仍然no_call():
    """旧收据（本改动之前跑的）走补评不该凭空获得可下结论的资格。"""

    out = _rejudge(_artifact_with_floor(None))

    assert out["noise_floor"] is None
    assert out["aggregates"]["kb-rag"]["decision"] == "no_call"
    assert "源轮未实测" in str(out["noise_floor_source"])

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from scripts import rejudge_quality_ablation as rejudge
from scripts.run_quality_ablation import aggregate_components

_NOW = datetime(2026, 8, 27, 1, 30, tzinfo=timezone.utc)


def _scores(value: int) -> dict[str, int]:
    return {
        "directness": value,
        "coverage": value,
        "relevance": value,
        "truth_boundary": value,
        "usefulness": value,
    }


def _judged(value: int) -> dict[str, object]:
    return {
        "scored": True,
        "scores": _scores(value),
        "total": value * 5,
        "normalized": round(value * 5 / 20.0, 4),
        "justification": "桩",
        "attempts": 1,
    }


def _unscored(reason: str = "所有已配置 LLM provider 均失败（zhipu:URLError）") -> dict[str, object]:
    return {"scored": False, "reason": reason, "attempts": 1}


def _answer(
    arm: str,
    case_id: str,
    judge: dict[str, object],
    *,
    ok: bool = True,
    answer: str | None = None,
) -> dict:
    return {
        "arm": arm,
        "case_id": case_id,
        "ok": ok,
        "answer": f"{arm}/{case_id} 的答案正文" * 20 if answer is None else answer,
        "elapsed_sec": 12.0,
        "judge": judge,
    }


def _artifact(answers: list[dict], case_ids: list[str]) -> dict[str, object]:
    aggregates = aggregate_components(answers, ["kb-rag"])
    return {
        "kind": "quality_ablation",
        "generated_at": "2026-08-26T14:35:58+00:00",
        "seed": 20260830,
        "judge_note": "同一 judge 评所有臂，标签盲",
        "questions": [{"case_id": c, "text": f"问题 {c}", "as_of": "2026-07-22"} for c in case_ids],
        "answers": answers,
        "aggregates": aggregates,
    }


def _two_case_artifact() -> dict[str, object]:
    """q1 基线断链未打分（拖垮该题），q2 两臂都已打分。"""

    answers = [
        _answer("baseline", "q1", _unscored()),
        _answer("baseline", "q2", _judged(3)),
        _answer("kb-rag", "q1", _judged(2)),
        _answer("kb-rag", "q2", _judged(2)),
    ]
    return _artifact(answers, ["q1", "q2"])


def _run(artifact, judge_fn, *, seed: int = 1, tmp_path=None):
    return rejudge.rejudge_artifact(
        artifact,
        judge_fn=judge_fn,
        seed=seed,
        source_path=(tmp_path or "/tmp") and "/tmp/source.json",
        source_sha256="deadbeef",
        now=_NOW,
    )


def test_断链未打分的题补评后重新进入聚合():
    artifact = _two_case_artifact()
    # 补评前：q1 因基线未打分而 unusable，聚合只剩 q2。
    assert artifact["aggregates"]["kb-rag"]["questions_usable"] == 1
    assert artifact["aggregates"]["kb-rag"]["questions_total"] == 2

    result = _run(artifact, lambda q, a: {**_judged(3), "provider": "zhipu"})

    assert result["aggregates"]["kb-rag"]["questions_usable"] == 2
    # q1: 关断 10 − 基线 15 = −5；q2: 10 − 15 = −5 → 边际贡献 +5
    assert result["aggregates"]["kb-rag"]["marginal_contribution_total"] == 5.0
    assert [r["case_id"] for r in result["rejudged"]] == ["q1"]
    assert result["rejudged"][0]["provider"] == "zhipu"


def test_已打分的行不重评():
    artifact = _two_case_artifact()
    before = json.dumps(artifact["answers"][1]["judge"], sort_keys=True)

    calls: list[str] = []

    def _judge(question, answer):
        calls.append(question.case_id)
        return {**_judged(4), "provider": "zhipu"}

    result = _run(artifact, _judge)

    assert calls == ["q1"], "只应补评那份未打分的"
    assert json.dumps(result["answers"][1]["judge"], sort_keys=True) == before


def test_答案正文不被改写():
    artifact = _two_case_artifact()
    originals = [rec["answer"] for rec in artifact["answers"]]

    result = _run(artifact, lambda q, a: {**_judged(3), "provider": "zhipu"})

    assert [rec["answer"] for rec in result["answers"]] == originals


def test_正文被改写时不变量断言炸开():
    """直接压那层断言：调用路径现在碰不到答案，但断言得真的会拦。

    只测端到端「答案没变」是假门禁——代码里本来就没人改它，断言删掉照样绿。
    """

    answers = [_answer("baseline", "q1", _judged(3))]
    before = {0: rejudge._sha256_text(str(answers[0]["answer"]))}

    rejudge.assert_only_judge_changed(answers, before, {})  # 未动 → 不炸

    answers[0]["answer"] = "被换掉的答案"
    with pytest.raises(SystemExit, match="补评只补 judge"):
        rejudge.assert_only_judge_changed(answers, before, {})


def test_既有分数被改动时不变量断言炸开():
    answers = [_answer("baseline", "q1", _judged(3))]
    before = {0: rejudge._sha256_text(str(answers[0]["answer"]))}
    judged = {0: json.dumps(answers[0]["judge"], ensure_ascii=False, sort_keys=True)}

    answers[0]["judge"] = _judged(4)
    with pytest.raises(SystemExit, match="只碰未打分的行"):
        rejudge.assert_only_judge_changed(answers, before, judged)


def test_答案臂失败的行不送评():
    """ok=False 但**正文非空**——run_ask 对「答案过短」正是这个返回形状。

    这类行是 harness 判过的废答案，补评它等于把废答案洗成读数；缺口只能重跑 ask。
    夹具必须复刻真实失败形状：早先版本把正文写成空串，结果被「正文为空就跳过」
    那条先兜住，这条守门断言删掉测试照样绿（变异测试抓到的假门禁）。
    """

    answers = [
        _answer(
            "baseline",
            "q1",
            {"scored": False, "reason": "答案臂失败，未送评"},
            ok=False,
            answer="exit=1 只吐了半句就断了",
        ),
        _answer("baseline", "q2", _judged(3)),
        _answer("kb-rag", "q1", _judged(2)),
        _answer("kb-rag", "q2", _judged(2)),
    ]
    artifact = _artifact(answers, ["q1", "q2"])

    calls: list[str] = []
    result = _run(artifact, lambda q, a: calls.append(q.case_id) or _judged(3))

    assert calls == []
    assert result["rejudged"] == []
    assert result["aggregates"]["kb-rag"]["questions_usable"] == 1


def test_正文为空的行不送评():
    """另一条独立守门：ok=True 但正文空（判官拿不到东西评）。"""

    answers = [
        _answer("baseline", "q1", _unscored(), answer=""),
        _answer("baseline", "q2", _judged(3)),
        _answer("kb-rag", "q1", _judged(2)),
        _answer("kb-rag", "q2", _judged(2)),
    ]
    artifact = _artifact(answers, ["q1", "q2"])

    calls: list[str] = []
    _run(artifact, lambda q, a: calls.append(q.case_id) or _judged(3))

    assert calls == []


def test_补评再失败仍记未打分不编造分数():
    artifact = _two_case_artifact()

    result = _run(artifact, lambda q, a: {"scored": False, "reason": "judge 输出无法解析"})

    assert result["rejudged"] == []
    assert [r["case_id"] for r in result["still_unscored"]] == ["q1"]
    assert result["still_unscored"][0]["rejudge_reason"] == "judge 输出无法解析"
    judge = result["answers"][0]["judge"]
    assert judge["scored"] is False
    assert judge["rejudge_attempted"] is True
    # 聚合读数没有因为「试过了」就变好
    assert result["aggregates"]["kb-rag"]["questions_usable"] == 1


def test_基线绝对分只统计已打分的题并带样本量():
    artifact = _two_case_artifact()

    before = rejudge.baseline_absolute(artifact["answers"])
    assert before == {
        "mean_total": 15.0,
        "questions_scored": 1,
        "questions_total": 2,
        "by_dim": {d: 3.0 for d in before["by_dim"]},
        "max_total": 20,
    }

    result = _run(artifact, lambda q, a: {**_judged(4), "provider": "zhipu"})
    after = result["baseline_absolute"]
    assert after["questions_scored"] == 2
    assert after["mean_total"] == 17.5  # (15 + 20) / 2


def test_输出指向原文件时拒绝执行(tmp_path):
    source = tmp_path / "run.json"
    source.write_text(json.dumps(_two_case_artifact(), ensure_ascii=False), encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        rejudge.main(["--run", str(source), "--output", str(source)])

    assert "不可覆盖" in str(excinfo.value)


def test_dry_run_不写文件不调_llm(tmp_path, capsys):
    source = tmp_path / "run.json"
    source.write_text(json.dumps(_two_case_artifact(), ensure_ascii=False), encoding="utf-8")

    assert rejudge.main(["--run", str(source), "--dry-run"]) == 0

    assert not (tmp_path / "run-rejudge.json").exists()
    assert "待补评 1 份" in capsys.readouterr().out


def test_收据登记补评来源与_judge_连续性():
    artifact = _two_case_artifact()

    result = _run(artifact, lambda q, a: {**_judged(3), "provider": "zhipu"})

    assert result["kind"] == "quality_ablation_rejudge"
    assert result["source_sha256"] == "deadbeef"
    assert result["source_generated_at"] == "2026-08-26T14:35:58+00:00"
    assert result["generated_at"] == _NOW.isoformat()
    assert "zhipu" in result["judge_continuity"]
    # 修正前的读数留在收据里，改了什么可自证
    assert result["aggregates_before"]["kb-rag"]["questions_usable"] == 1

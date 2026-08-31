"""消融臂的判官独立性、确定性层与 rubric 版本闸。

守的失败形状（2026-08-31 实测）：`run_quality_ablation` 的盲评判官走的是
**合成链**（`LLM_MODEL`），也就是 `gpt-5.6-terra` 既写答案又给自己打分。
仓内早有独立判官通道（`llm_refine.judge_provider()`），只是消融臂没接。

这个缺陷能活这么久，是因为**自审跑出来的收据和独立评审的收据长得一模一样**——
没有任何字段能让人看出判官和被判者同源。所以修法不只是接线，还要 fail-closed。

依据：ai-agent-book ch6「古德哈特定律 → 多源异构评判」（不同**家族**，不是不同
模型名）、「Rubric 四准则 ④ 自包含评估」、「LLM-as-Judge 长度偏差」。
"""

from __future__ import annotations

import pytest

from scripts.run_quality_ablation import (
    RUBRIC_DIMENSIONS,
    RUBRIC_VERSION,
    Question,
    _parse_judge_payload,
    aggregate_components,
    deterministic_score,
    length_bias_audit,
    resolve_judge,
)

_JUDGE_ENV = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_JUDGE_API_KEY",
    "LLM_JUDGE_BASE_URL",
    "LLM_JUDGE_MODEL",
    "LLM_JUDGE_BACKEND",
)


@pytest.fixture
def composer_env(monkeypatch):
    """只配合成链：复刻消融臂此前的真实运行环境。"""

    for key in _JUDGE_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-5.6-terra")
    return monkeypatch


# ------------------------------------------------------------ 判官独立性


def test_未配独立判官时判成自己评自己(composer_env) -> None:
    info = resolve_judge(require_independent=False)

    assert info["independence"] == "correlated"
    assert info["composer"] == info["judge"], "合成与判官应被识别为同一个模型"


def test_同网关不同模型名只算弱独立(composer_env) -> None:
    """生产现状：`LLM_JUDGE_MODEL=gpt-5.6-sol`，与合成同家族同网关。

    书里把这一档记作「次优但仍降低相关性」——它不是异构评判，
    不该被当成已解决。
    """

    composer_env.setenv("LLM_JUDGE_MODEL", "gpt-5.6-sol")
    info = resolve_judge(require_independent=False)

    assert info["independence"] == "weak"
    assert info["composer"] != info["judge"]


def test_grok_cli_后端才算异构独立(composer_env) -> None:
    composer_env.setenv("LLM_JUDGE_BACKEND", "grok-cli")
    info = resolve_judge(require_independent=False)

    assert info["independence"] == "independent"
    assert "grok" in str(info["judge"])


@pytest.mark.parametrize(
    "env, expected_blocked",
    [
        ({}, True),  # 自审
        ({"LLM_JUDGE_MODEL": "gpt-5.6-sol"}, True),  # 弱独立也拦
        ({"LLM_JUDGE_BACKEND": "grok-cli"}, False),  # 异构放行
    ],
)
def test_require_independent_是fail_closed(composer_env, env, expected_blocked) -> None:
    """默认拒跑，不静默退回自审——静默退回正是这缺陷活到今天的原因。"""

    for key, value in env.items():
        composer_env.setenv(key, value)
    if expected_blocked:
        with pytest.raises(SystemExit) as exc:
            resolve_judge(require_independent=True)
        assert "判官独立性不足" in str(exc.value)
        assert "grok-cli" in str(exc.value), "拒跑要给出修法，不能只报错"
    else:
        assert resolve_judge(require_independent=True)["independence"] == "independent"


def test_allow_correlated_放行但仍如实标注(composer_env) -> None:
    """允许自审是逃生口，不是把问题抹掉：收据里必须还看得出它是自审。"""

    info = resolve_judge(require_independent=False)

    assert info["independence"] == "correlated"
    assert info["reason"], "相关自审必须带上原因，否则收据读起来像正常评审"


# --------------------------------------------------------------- 确定性层


def _answer_with_evidence() -> str:
    return (
        "结论：短期反弹持续性有限。截至 2026-07-22，上证成交额 9800 亿元，"
        "涨停 42 家（来源 fact_market_daily）。代表个股 600519 当日 +2.1%，"
        "板块层面参考 [S1]。风险：若量能回落至 8000 亿元以下，结论失效。"
    )


def test_确定性层同一答案永远同一个分() -> None:
    """零 LLM、零 IO → 方差恒为 0。这是它存在的全部理由，必须钉住。"""

    question = Question("q0", "昨天的反弹能持续多久", "2026-07-22")
    answer = _answer_with_evidence()

    runs = [deterministic_score(question, answer)["total"] for _ in range(5)]

    assert len(set(runs)) == 1, f"确定性判据出现方差：{runs}"


def test_确定性层能分辨有证据和空壳() -> None:
    """它测不了推理对不对，但「证据标记少了几个」是硬事实——这就是它的用处。"""

    question = Question("q0", "昨天的反弹能持续多久", "2026-07-22")
    rich = deterministic_score(question, _answer_with_evidence())["total"]
    hollow = deterministic_score(
        question, "市场情绪较为复杂，需要综合研判，建议保持关注。" * 12
    )["total"]

    assert rich > hollow, "堆砌行话的空壳不该拿到和带数据的答案一样的分"


# ------------------------------------------------------- rubric 版本与陷阱项


def test_解析结果带rubric版本号() -> None:
    payload = {dim: 3 for dim in RUBRIC_DIMENSIONS}
    parsed = _parse_judge_payload(payload)

    assert parsed is not None
    assert parsed["rubric_version"] == RUBRIC_VERSION


def test_陷阱项单列不折进总分() -> None:
    """幻觉/迎合/堆砌/回避是定性信号，折进 0-20 会被其他维度稀释掉。"""

    payload = {dim: 3 for dim in RUBRIC_DIMENSIONS}
    payload["pitfalls"] = ["hallucination", "keyword_stuffing"]
    parsed = _parse_judge_payload(payload)

    assert parsed["pitfalls"] == ["hallucination", "keyword_stuffing"]
    assert parsed["total"] == 15, "陷阱项不该改变总分"


def _judged(total: int, *, version: str = RUBRIC_VERSION) -> dict[str, object]:
    base, rem = divmod(total, len(RUBRIC_DIMENSIONS))
    values = [base + (1 if i < rem else 0) for i in range(len(RUBRIC_DIMENSIONS))]
    return {
        "scored": True,
        "rubric_version": version,
        "scores": dict(zip(RUBRIC_DIMENSIONS, values)),
        "total": total,
        "normalized": round(total / 20.0, 4),
        "pitfalls": [],
        "justification": "桩",
    }


def _answer(arm: str, case_id: str, judge: dict[str, object]) -> dict[str, object]:
    return {
        "arm": arm,
        "case_id": case_id,
        "ok": True,
        "answer": f"{arm}/{case_id} 正文" * 20,
        "elapsed_sec": 1.0,
        "judge": judge,
    }


def test_混用rubric版本直接拒跑() -> None:
    """换版=换口径，跨版分差没有意义，而混出来的数长得和正常读数一样。"""

    answers = [
        _answer("baseline", "q0", _judged(14)),
        _answer("kb-rag", "q0", _judged(11, version="v1-abstract")),
    ]
    with pytest.raises(SystemExit) as exc:
        aggregate_components(answers, ["kb-rag"])

    assert "rubric 版本" in str(exc.value)


def test_旧收据无版本字段按v1计不炸() -> None:
    """本改动之前的收据没有该字段，要能读，只是不许和新版混。"""

    old = _judged(14)
    del old["rubric_version"]
    answers = [_answer("baseline", "q0", old), _answer("kb-rag", "q0", {**old, "total": 11})]

    agg = aggregate_components(answers, ["kb-rag"])["kb-rag"]

    assert agg["marginal_contribution_total"] == 3.0


# ------------------------------------------------------------- 长度偏差审计


def test_长度偏差审计能抓到分数随长度走() -> None:
    answers = [
        {"arm": "baseline", "case_id": f"q{i}", "ok": True, "answer": "字" * (500 * i), "judge": _judged(4 * i)}
        for i in range(1, 6)
    ]
    audit = length_bias_audit(answers)

    assert audit["measured"] is True
    assert audit["pearson_r"] > 0.9
    assert audit["flag"] == "high_length_correlation"


def test_长度偏差审计样本不足时不编数() -> None:
    audit = length_bias_audit([{"arm": "baseline", "case_id": "q0", "ok": True, "answer": "字", "judge": _judged(12)}])

    assert audit["measured"] is False
    assert "不足" in str(audit["reason"])

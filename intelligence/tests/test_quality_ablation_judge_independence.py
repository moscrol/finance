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
    JUDGE_SYSTEMS,
    RUBRIC_DIMENSIONS,
    RUBRIC_VERSION,
    Question,
    _parse_judge_payload,
    aggregate_components,
    deterministic_score,
    length_bias_audit,
    model_family,
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


def test_同家族不同型号只算弱独立(composer_env) -> None:
    """生产现状：合成 gpt-5.6-terra、判官 gpt-5.6-sol——同家族。

    书里把这一档记作「次优但仍降低相关性」——它不是异构评判，
    不该被当成已解决。
    """

    composer_env.setenv("LLM_JUDGE_MODEL", "gpt-5.6-sol")
    info = resolve_judge(require_independent=False)

    assert info["independence"] == "weak"
    assert info["composer"] != info["judge"], "型号不同但仍同族"


@pytest.mark.parametrize(
    "composer, judge, same",
    [
        ("zhipu/glm-5.3", "judge/gpt-5.6-sol", False),
        ("custom/gpt-5.6-terra", "custom-judge/gpt-5.6-sol", True),
        ("zhipu/glm-5.3", "grok-cli-judge/grok-4.6", False),
    ],
)
def test_家族按模型名判不按端点判(composer, judge, same) -> None:
    """本函数初版只看 transport（cli/http），把同网关跨家族误判成 weak。

    2026-08-31 实测本机就是那个配置：composer=zhipu/glm-5.3、judge=gpt-5.6-sol，
    **是**异构，却被拦下。用「机制」冒充「家族」是这类判据的通病。
    """

    assert (model_family(composer) == model_family(judge)) is same


def test_同网关跨家族算独立(composer_env) -> None:
    composer_env.setenv("LLM_MODEL", "glm-5.3")
    composer_env.setenv("LLM_JUDGE_MODEL", "gpt-5.6-sol")
    info = resolve_judge(require_independent=False)

    assert info["independence"] == "independent"
    assert "glm" in str(info["reason"]) and "gpt" in str(info["reason"])


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


# --------------------------------------------------- rubric 版本的实测依据


def test_v3把一票否决从分数里拿出来() -> None:
    """钉住 2026-08-31 的实测结论（收据 ~/.finance-runtime/rubric-variance-ab-v3.json）。

    5 题 × 3 次 × 同判官同答案、调用顺序交错，合并 sd：
        v1 抽象判据            1.24   各题极差 [1,3,3,3,1]
        v2 可数锚点 + 一票否决  1.71   各题极差 [4,1,2,6,0]   ← 反而更差
        v3 可数锚点 + 否决拆出  0.77   各题极差 [2,1,1,2,1]

    v2 变差的机制点得名且两轮复现：`current-mainline` 是**唯一**被判
    hallucination 的题，也是**唯一**炸到极差 6 的题。「一票否决」是阶跃函数——
    判官对「算不算编造」摇摆时，truth_boundary 在 0 与 3 之间跳，总分跟着跳 4 分。

    v3 拆开后 hallucination 反而在 3 道题上都报了（检测器与惩罚脱钩，判官更敢报），
    极差却全部收进 2 以内。**陷阱项要留在决策层，不要折进喂给 A/B 的连续分。**
    """

    v2 = JUDGE_SYSTEMS["v2-selfcontained"]
    v3 = JUDGE_SYSTEMS["v3-veto-split"]

    assert "一票否决" in v2, "v2 是历史版本，内容不可变（跨版对照要拿它当对照臂）"
    assert "一票否决" not in v3
    assert "不要因此改这一维的分" in v3, "v3 必须显式告诉判官：判定编造不改分"
    assert "pitfalls" in v3, "陷阱项仍要检测，只是不折进分数"


def test_默认版本就是实测最稳的那版() -> None:
    """默认值要跟着证据走，不是跟着「最新写的」走。"""

    assert RUBRIC_VERSION == "v3-veto-split"
    assert RUBRIC_VERSION in JUDGE_SYSTEMS


# ------------------------------- 2026-08-31 第二轮质检点名的两个洞


def test_同族走cli也不算独立(composer_env) -> None:
    """家族是主判据，传输方式只是附注——**别再用「机制」冒充「家族」**。

    真会发生：本会话 14:44 实测 grok 后端拿到的 provider 是
    `grok-cli-judge/gpt-5.6-sol`——启动器的 `LLM_JUDGE_MODEL` 串了进去，
    传输是 cli 而模型仍是 gpt 系，与合成同族。上一版把 transport 判在家族之前，
    这种配置会被标成 independent 放行。
    """

    composer_env.setenv("LLM_MODEL", "gpt-5.6-terra")
    composer_env.setenv("LLM_JUDGE_BACKEND", "grok-cli")
    composer_env.setenv("LLM_JUDGE_MODEL", "gpt-5.6-sol")  # 串进 grok 后端的同族名

    info = resolve_judge(require_independent=False)

    assert info["independence"] == "weak", "同族走 CLI 仍是同族，不得抬成 independent"
    assert "同家族" in str(info["reason"])
    assert "CLI" in str(info["reason"]), "走了 CLI 这个事实要留在 reason 里，只是不抬档"


def test_跨家族走cli仍是独立(composer_env) -> None:
    """反方向：CLI 不抬档，也不该把本来就异构的降档。"""

    composer_env.setenv("LLM_MODEL", "glm-5.3")
    composer_env.setenv("LLM_JUDGE_BACKEND", "grok-cli")

    info = resolve_judge(require_independent=False)

    assert info["independence"] == "independent"
    assert "CLI" in str(info["reason"])


def test_补评也过判官独立性闸() -> None:
    """主轮堵了、补评没堵，自审会从侧门溜回来。

    `rejudge_quality_ablation.py` 此前直接调 `judge_answer`，不经 `resolve_judge`。
    补评产出的行与独立评审的行在收据里同形——**正是这个缺陷此前活那么久的原因**。
    补评的门不该比主轮松，所以默认同为 `require`。
    """

    import inspect

    from scripts import rejudge_quality_ablation as rejudge

    src = inspect.getsource(rejudge.main)
    assert "resolve_judge(" in src, "补评必须过独立性闸"
    assert "_JUDGE_OVERRIDE" in src, "解析出的判官要真的被用上，不能只解析不注入"

    parser_src = inspect.getsource(rejudge.build_parser)
    assert '"--judge-independence"' in parser_src
    assert 'default="require"' in parser_src, "补评默认门不得比主轮松"

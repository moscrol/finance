from __future__ import annotations

import hashlib
import json
from pathlib import Path

from intelligence.eval.acceptance_verdict import (
    ExperienceState,
    OperationalState,
    VerdictState,
    compile_case_contract,
    evaluate_case,
    load_verdict_overlay,
)


ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "intelligence/eval/cases/acceptance_cases.json"
SNAPSHOT_DIR = ROOT / "intelligence/eval/cases/reference_snapshots"
CANONICAL_CASES_SHA256 = "a25c68253a92be536b94d2403ffa010b6cd15a20b7eea581450159cb6444a1c6"


def test_missing_run_is_not_run_on_operational_and_truth_axes() -> None:
    contract = compile_case_contract(
        {
            "id": "C1-future-date-no-data",
            "tier": "long_tail",
            "query": "2026-07-25 市场怎么样",
            "date": "2026-07-25",
            "expect_refusal": True,
            "pass_rule": "必须明确说无数据",
        },
        {"coverage": "structured"},
    )

    verdict = evaluate_case(contract, None)

    assert verdict.operational.state is OperationalState.NOT_RUN
    assert verdict.truth.state is VerdictState.NOT_RUN
    assert verdict.experience.state is ExperienceState.UNLABELED
    assert verdict.to_dict()["truth"]["state"] == "not_run"


def test_overlay_names_every_canonical_case_once() -> None:
    doc = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    overlay = load_verdict_overlay()

    assert set(overlay) == {case["id"] for case in doc["cases"]}
    assert len(overlay) == 28
    for entry in overlay.values():
        assert entry["coverage"] in {"structured", "semantic_required"}
        if entry["coverage"] == "semantic_required":
            assert entry.get("reason")


def test_all_cases_compile_without_mutating_frozen_assets() -> None:
    before = hashlib.sha256(CASES_PATH.read_bytes()).hexdigest()
    assert before == CANONICAL_CASES_SHA256
    snapshot_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in SNAPSHOT_DIR.glob("*.json")
    }
    doc = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    overlay = load_verdict_overlay()

    contracts = [
        compile_case_contract(case, overlay[case["id"]]) for case in doc["cases"]
    ]

    assert len(contracts) == 28
    assert {contract.case_id for contract in contracts} == set(overlay)
    # 已知的题目缺陷用具名清单钉住，本身就是一份待办：问的是「现在」、期望值却
    # 冻结在 2026-07-23，这种红永远不会变绿（详见 _reproducibility_diagnostics）。
    # 修好某题的日期锚后，把它从这里删掉；新冒出来的缺陷会让本条断言变红。
    assert {
        contract.case_id for contract in contracts if contract.diagnostics
    } == {"A8-market-stage", "C6-strict-definition"}
    assert all(
        "not reproducible" in contract.diagnostics[0]
        for contract in contracts
        if contract.diagnostics
    )
    assert hashlib.sha256(CASES_PATH.read_bytes()).hexdigest() == before
    assert {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in SNAPSHOT_DIR.glob("*.json")
    } == snapshot_hashes


def test_unknown_case_field_is_visible_in_contract_diagnostics() -> None:
    contract = compile_case_contract(
        {
            "id": "X1",
            "tier": "long_tail",
            "query": "x",
            "pass_rule": "x",
            "mystery_gate": True,
        },
        {"coverage": "semantic_required", "reason": "manual"},
    )

    assert contract.diagnostics == ("unknown case fields: mystery_gate",)


def test_operational_state_does_not_decide_truth() -> None:
    contract = compile_case_contract(
        {
            "id": "C1",
            "tier": "long_tail",
            "query": "future",
            "expect_refusal": True,
            "pass_rule": "say no data",
        },
        {"coverage": "structured"},
    )
    blocked = evaluate_case(contract, {"turns": [], "blocked_reason": "preflight"})
    failed = evaluate_case(
        contract,
        {"turns": [{"status": "timeout", "error": "deadline"}]},
    )
    degraded = evaluate_case(
        contract,
        {
            "turns": [
                {
                    "status": "completed",
                    "answer": "没有可用数据",
                    "degrades": ["evidence gap"],
                }
            ]
        },
    )
    completed = evaluate_case(
        contract,
        {"turns": [{"status": "completed", "answer": "made up 42", "degrades": []}]},
    )

    assert blocked.operational.state is OperationalState.BLOCKED
    assert blocked.truth.state is VerdictState.UNJUDGEABLE
    assert failed.operational.state is OperationalState.FAILED
    assert failed.truth.state is VerdictState.UNJUDGEABLE
    assert degraded.operational.state is OperationalState.DEGRADED
    assert completed.operational.state is OperationalState.COMPLETED
    assert completed.truth.state is not VerdictState.PASS


def _completed(answer: str, **extra):
    turn = {"status": "completed", "answer": answer, "degrades": []}
    turn.update(extra)
    return {"turns": [turn]}


def _rule(verdict, rule_id: str):
    return next(rule for rule in verdict.truth.rules if rule.rule_id == rule_id)


def test_explicit_refusal_and_forbidden_text_are_deterministic() -> None:
    contract = compile_case_contract(
        {
            "id": "C1",
            "tier": "long_tail",
            "query": "future",
            "expect_refusal": True,
            "forbid_phrases": ["涨停家数为"],
            "pass_rule": "must explicitly say no data",
        },
        {
            "coverage": "structured",
            "required_any_phrases": ["无数据", "没有可用", "超出覆盖范围"],
        },
    )

    passed = evaluate_case(contract, _completed("该日没有可用的市场数据。"))
    vague = evaluate_case(contract, _completed("现有证据不足，暂不能可靠回答。"))
    fabricated = evaluate_case(
        contract,
        _completed("该日无数据，但预计涨停家数为 88 家。"),
    )

    assert passed.truth.state is VerdictState.PASS
    assert _rule(vague, "required_any_phrases").state is VerdictState.FAIL
    assert vague.truth.state is VerdictState.FAIL
    assert _rule(fabricated, "forbidden_phrases").state is VerdictState.FAIL


def test_numeric_and_literal_fact_rules_respect_tolerances() -> None:
    contract = compile_case_contract(
        {
            "id": "A1",
            "tier": "high_freq",
            "query": "market",
            "expect_facts": [
                {"field": "total_amount", "value": 21949.97, "tol_pct": 1.0},
                {"field": "amount_vs_yesterday_pct", "value": -17.27, "tol_abs": 0.5},
                {"field": "market_stage", "value": "反弹阶段"},
            ],
            "pass_rule": "facts",
        },
        {
            "coverage": "structured",
            "fact_aliases": {
                "total_amount": ["成交额"],
                "amount_vs_yesterday_pct": ["环比"],
                "market_stage": ["阶段"],
            },
        },
    )

    passed = evaluate_case(
        contract,
        _completed("成交额 21,950 亿元，环比 -17.3%，处于反弹阶段。"),
    )
    failed = evaluate_case(
        contract,
        _completed("成交额 18,000 亿元，环比 -12%，处于反弹阶段。"),
    )

    assert passed.truth.state is VerdictState.PASS
    assert _rule(failed, "fact:total_amount").state is VerdictState.FAIL
    assert _rule(failed, "fact:amount_vs_yesterday_pct").state is VerdictState.FAIL
    assert failed.truth.state is VerdictState.FAIL


def test_cutoff_uses_structured_citation_dates_and_prediction_context() -> None:
    contract = compile_case_contract(
        {
            "id": "C7",
            "tier": "long_tail",
            "query": "forecast",
            "date": "2026-07-21",
            "forbid_future_data": True,
            "pass_rule": "no future realized data",
        },
        {"coverage": "structured"},
    )
    clean = evaluate_case(
        contract,
        _completed(
            "7月22日大概率偏强震荡。",
            citations=[{"date": "2026-07-21"}],
        ),
    )
    leaked = evaluate_case(
        contract,
        _completed(
            "7月22日实际收跌 1.2%。",
            citations=[{"date": "2026-07-22"}],
        ),
    )
    missing = evaluate_case(contract, _completed("7月22日大概率偏强震荡。"))

    assert _rule(clean, "cutoff").state is VerdictState.PASS
    assert clean.truth.state is VerdictState.PASS
    assert _rule(leaked, "cutoff").state is VerdictState.FAIL
    assert leaked.truth.state is VerdictState.FAIL
    assert _rule(missing, "cutoff").state is VerdictState.UNJUDGEABLE
    assert missing.truth.state is VerdictState.UNJUDGEABLE


def test_citation_integrity_checks_only_minted_tags() -> None:
    contract = compile_case_contract(
        {
            "id": "C9",
            "tier": "long_tail",
            "query": "cause",
            "check_citation_registry": True,
            "pass_rule": "citations",
        },
        {"coverage": "structured"},
    )
    dangling = evaluate_case(
        contract,
        _completed(
            "原因见 [E1][W2]。",
            evidence=[{"label": "[E1] 市场证据", "status": "hit"}],
        ),
    )
    minted = evaluate_case(
        contract,
        _completed(
            "原因见 [E1][W2]。",
            evidence=[
                {"label": "[E1] 市场证据", "status": "hit"},
                {"label": "[W2] Wiki", "status": "hit"},
            ],
        ),
    )
    no_tags = evaluate_case(contract, _completed("现有证据不足。"))

    assert _rule(dangling, "citation_integrity").state is VerdictState.FAIL
    assert _rule(minted, "citation_integrity").state is VerdictState.PASS
    assert _rule(no_tags, "citation_integrity").state is VerdictState.PASS


def test_semantic_coverage_never_silently_passes() -> None:
    contract = compile_case_contract(
        {
            "id": "C9",
            "tier": "long_tail",
            "query": "cause",
            "check_citation_registry": True,
            "pass_rule": "must explain the cause and cite it",
        },
        {
            "coverage": "semantic_required",
            "reason": "citation validity does not establish causal quality",
        },
    )
    unjudged = evaluate_case(contract, _completed("没有引用标签。"))
    judged = evaluate_case(
        contract,
        _completed("给出完整因果链。"),
        observations={
            "truth_observations": {
                "pass_rule": {"state": "pass", "reason": "blind semantic review"}
            }
        },
    )

    assert _rule(unjudged, "pass_rule").state is VerdictState.UNJUDGEABLE
    assert unjudged.truth.state is VerdictState.UNJUDGEABLE
    assert _rule(judged, "pass_rule").state is VerdictState.PASS
    assert judged.truth.state is VerdictState.PASS


def test_external_observations_cannot_erase_hard_failure_or_mix_experience() -> None:
    contract = compile_case_contract(
        {
            "id": "C9",
            "tier": "long_tail",
            "query": "cause",
            "forbid_phrases": ["编造数字"],
            "check_citation_registry": True,
            "pass_rule": "must explain cause",
        },
        {
            "coverage": "semantic_required",
            "reason": "needs semantic observation",
        },
    )
    verdict = evaluate_case(
        contract,
        _completed("编造数字，但没有引用标签。"),
        observations={
            "truth_observations": {
                "pass_rule": {"state": "pass", "reason": "semantic pass"}
            },
            "experience_verdict": {
                "eligible": True,
                "label": "workbench",
                "reason": "blind preference",
            },
        },
    )

    assert _rule(verdict, "pass_rule").state is VerdictState.PASS
    assert _rule(verdict, "forbidden_phrases").state is VerdictState.FAIL
    assert verdict.truth.state is VerdictState.FAIL
    assert verdict.experience.state is ExperienceState.LABELED
    assert verdict.experience.label == "workbench"


def test_inconsistency_falsifiability_and_cross_turn_checks_are_conservative() -> None:
    inconsistency = compile_case_contract(
        {
            "id": "C5",
            "tier": "long_tail",
            "query": "dirty",
            "require_flag_inconsistency": True,
            "pass_rule": "flag inconsistency",
        },
        {"coverage": "structured"},
    )
    assert evaluate_case(
        inconsistency, _completed("两日数据互相矛盾，疑似重复。")
    ).truth.state is VerdictState.PASS
    assert evaluate_case(
        inconsistency, _completed("两日数据完全正常。")
    ).truth.state is VerdictState.FAIL

    falsifiable = compile_case_contract(
        {
            "id": "A2",
            "tier": "high_freq",
            "query": "tomorrow",
            "require_falsifiable": True,
            "pass_rule": "condition",
        },
        {"coverage": "structured"},
    )
    assert evaluate_case(
        falsifiable, _completed("若指数跌破 3,500 点，则判断失效。")
    ).truth.state is VerdictState.PASS
    assert evaluate_case(
        falsifiable, _completed("明天继续看涨。")
    ).truth.state is VerdictState.FAIL

    multi_turn = compile_case_contract(
        {
            "id": "C10",
            "tier": "long_tail",
            "query": "set",
            "check_cross_turn_consistency": True,
            "pass_rule": "consistent",
        },
        {"coverage": "structured"},
    )
    lost = evaluate_case(
        multi_turn,
        {
            "turns": [
                {"status": "completed", "answer": "电网设备。", "degrades": []},
                {"status": "completed", "answer": "你指的是哪个板块？", "degrades": []},
            ]
        },
    )
    plausible = evaluate_case(
        multi_turn,
        {
            "turns": [
                {"status": "completed", "answer": "电网设备。", "degrades": []},
                {"status": "completed", "answer": "仍是电网设备，共 1 个。", "degrades": []},
            ]
        },
    )

    assert _rule(lost, "cross_turn_consistency").state is VerdictState.FAIL
    assert lost.truth.state is VerdictState.FAIL
    assert _rule(plausible, "cross_turn_consistency").state is VerdictState.UNJUDGEABLE
    assert plausible.truth.state is VerdictState.UNJUDGEABLE


def test_historical_run_calibration_is_honest_and_reproducible() -> None:
    cases_doc = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in cases_doc["cases"]}
    overlay = load_verdict_overlay()
    run = json.loads(
        (ROOT / "intelligence/eval/runs/20260727T032229Z.json").read_text(
            encoding="utf-8"
        )
    )
    runs = {item["case_id"]: item for item in run["cases"]}

    verdicts = {
        case_id: evaluate_case(
            compile_case_contract(cases[case_id], overlay[case_id]),
            runs[case_id],
        )
        for case_id in (
            "C1-future-date-no-data",
            "C7-temporal-leakage",
            "C9-citation-integrity",
            "C10-multi-turn-consistency",
        )
    }

    assert verdicts["C1-future-date-no-data"].truth.state is VerdictState.UNJUDGEABLE
    assert _rule(
        verdicts["C1-future-date-no-data"], "refusal"
    ).state is VerdictState.PASS
    assert _rule(
        verdicts["C1-future-date-no-data"], "forbidden_phrases"
    ).state is VerdictState.PASS
    assert verdicts["C7-temporal-leakage"].truth.state is VerdictState.PASS
    assert verdicts["C9-citation-integrity"].truth.state is VerdictState.UNJUDGEABLE
    assert _rule(
        verdicts["C9-citation-integrity"], "citation_integrity"
    ).state is VerdictState.PASS
    assert _rule(
        verdicts["C9-citation-integrity"], "pass_rule"
    ).state is VerdictState.UNJUDGEABLE
    assert verdicts["C10-multi-turn-consistency"].truth.state is VerdictState.FAIL


# --- 判官读不出正确答案的两个缺陷（2026-08-01 A 组基线）----------------------
#
# A1 实测：答案写「全市场成交额 21949.97 亿元，较上一交易日缩减 17.27%」，
# 判据要 amount_vs_yesterday_pct=-17.27，判 FAIL。查下来是两个缺陷叠加：
#   ① 别名表是 ["环比","较昨日"]，答案说的是「较上一交易日」→ _alias_windows
#      返回空串 → 在空文本里找数字 → 必然判失败。**配置疏漏被当成产品答错。**
#   ② 就算窗口对了，「缩减 17.27%」抽出来是 +17.27，方向词没被解析成负号。
# 这不是放宽门禁：两种写法在自然中文里指同一个事实，读不出来是判官表达力不足。


def _fact_contract(aliases: dict[str, list[str]]):
    return compile_case_contract(
        {
            "id": "A1",
            "tier": "high_freq",
            "query": "market",
            "expect_facts": [
                {"field": "amount_vs_yesterday_pct", "value": -17.27, "tol_abs": 0.5},
            ],
            "pass_rule": "facts",
        },
        {"coverage": "structured", "fact_aliases": aliases},
    )


def test_alias_miss_is_unjudgeable_not_failure() -> None:
    """别名一个都没命中时，判官不知道答案对不对——不能报假红。

    报 FAIL 会让「别名表没跟上答案措辞」这种配置疏漏，长得跟「产品答错了」
    一模一样。A 组基线上就是这么少算了分。
    """
    contract = _fact_contract({"amount_vs_yesterday_pct": ["环比", "较昨日"]})
    result = evaluate_case(
        contract,
        _completed("全市场成交额 21949.97 亿元，较上一交易日缩减 17.27%。"),
    )
    rule = _rule(result, "fact:amount_vs_yesterday_pct")
    assert rule.state is VerdictState.UNJUDGEABLE, (
        f"别名未命中却给了确定裁决：{rule.state} / {rule.reason}"
    )


def test_chinese_direction_word_carries_the_sign() -> None:
    """「缩减 17.27%」就是 -17.27。中文把符号放在方向词上，不放在数字上。"""
    contract = _fact_contract({"amount_vs_yesterday_pct": ["较上一交易日"]})
    result = evaluate_case(
        contract,
        _completed("全市场成交额 21949.97 亿元，较上一交易日缩减 17.27%。"),
    )
    assert _rule(result, "fact:amount_vs_yesterday_pct").state is VerdictState.PASS


def test_wrong_direction_word_still_fails() -> None:
    """方向反了就是答错。加了方向词解析不能把符号错误一起放过去。"""
    contract = _fact_contract({"amount_vs_yesterday_pct": ["较上一交易日"]})
    result = evaluate_case(
        contract,
        _completed("全市场成交额 21949.97 亿元，较上一交易日增加 17.27%。"),
    )
    assert _rule(result, "fact:amount_vs_yesterday_pct").state is VerdictState.FAIL


def test_alias_hit_but_number_absent_is_still_a_real_failure() -> None:
    """别名命中、数字确实不在正文里——这是真缺口，必须继续判 FAIL。

    A1 的 limit_up=116 就是这一类（窗口 101 字符，抽到 40/29/29，确实没有 116）。
    放过它就是为了绿灯放宽门禁。
    """
    contract = _fact_contract({"amount_vs_yesterday_pct": ["较上一交易日"]})
    result = evaluate_case(
        contract,
        _completed("全市场成交额 21949.97 亿元，较上一交易日基本持平。"),
    )
    assert _rule(result, "fact:amount_vs_yesterday_pct").state is VerdictState.FAIL


# --- 任务 #14：验收台信噪比 ------------------------------------------------
#
# 背景：A 组同输入复跑三次，两条断言全翻（handoff 2026-08-01c §4）。
# 离线复算定位到波动几乎全在**措辞层**：干净对照（同一份 server 代码）里
# 数值型 fact 0/20 翻转、must_mention 2/3 翻转。下面这组测试守住三件事——
# 判官不因语序/同义/冗余报假红，也不因此放过真缺口。


def _mention_case(overlay: dict, answer: str, **case_extra):
    case = {
        "id": "A1-like",
        "tier": "high_freq",
        "query": "market",
        "must_mention": ["缩量"],
        "expect_facts": [
            {"field": "amount_vs_yesterday_pct", "value": -17.27, "tol_abs": 0.5}
        ],
        "pass_rule": "facts and language",
    }
    case.update(case_extra)
    base = {"coverage": "structured", "fact_aliases": {"amount_vs_yesterday_pct": ["较昨日"]}}
    base.update(overlay)
    return evaluate_case(compile_case_contract(case, base), _completed(answer))


def test_number_before_the_alias_still_binds() -> None:
    """中文修饰语在名词前也算命中：「21949.97 亿元的成交额」。

    回看窗口原来只有 8 字，这个数落在别名前 13 字被切掉，于是「答对了但语序
    不同」判成 FAIL。A1 run3 实测就是这条假红。
    """
    contract = compile_case_contract(
        {
            "id": "A1",
            "tier": "high_freq",
            "query": "market",
            "expect_facts": [{"field": "total_amount", "value": 21949.97, "tol_pct": 1.0}],
            "pass_rule": "facts",
        },
        {"coverage": "structured", "fact_aliases": {"total_amount": ["成交额"]}},
    )
    result = evaluate_case(contract, _completed("21949.97 亿元的成交额能否企稳回升。"))
    assert _rule(result, "fact:total_amount").state is VerdictState.PASS


def test_equivalent_wording_counts_as_the_product_term() -> None:
    """「处于反弹」和「反弹阶段」是同一件事的两种合法中文，不该判死措辞。"""
    result = _mention_case(
        {"phrase_equivalents": {"反弹阶段": ["反弹阶段", "处于反弹"]}},
        "市场处于反弹的第 3 个交易日，成交额较昨日缩量 17.27%。",
        must_mention=["反弹阶段"],
    )
    assert _rule(result, "must_mention").state is VerdictState.PASS


def test_equivalence_class_must_not_cross_enum_values() -> None:
    """等价类只吸收同一枚举值的别称。「震荡」不是「反弹阶段」，必须仍判 FAIL。"""
    result = _mention_case(
        {"phrase_equivalents": {"反弹阶段": ["反弹阶段", "处于反弹"]}},
        "市场处于震荡的第 3 个交易日，成交额较昨日缩量 17.27%。",
        must_mention=["反弹阶段"],
    )
    assert _rule(result, "must_mention").state is VerdictState.FAIL


def test_equivalence_class_missing_its_own_phrase_is_a_contract_diagnostic() -> None:
    """等价类必须含正典短语本身。少了它，一个笔误就能整条换掉原断言。"""
    contract = compile_case_contract(
        {
            "id": "A1",
            "tier": "high_freq",
            "query": "market",
            "must_mention": ["反弹阶段"],
            "pass_rule": "language",
        },
        {"coverage": "structured", "phrase_equivalents": {"反弹阶段": ["处于反弹"]}},
    )
    assert any("does not contain the phrase itself" in item for item in contract.diagnostics)
    assert "反弹阶段" not in contract.phrase_equivalents


def test_stricter_numeric_rule_discharges_the_redundant_wording_rule() -> None:
    """数值规则已经证明了缩量，就别再单独测模型用不用「缩量」这个词。

    A1 run2 实测：答案写「较昨日减少 17.27%」，fact 判 PASS、must_mention 判 FAIL。
    那条 FAIL 零信息量——同一事实已被一条带容差的数值规则守着。
    """
    result = _mention_case(
        {"phrase_discharged_by": {"缩量": "fact:amount_vs_yesterday_pct"}},
        "成交额 21949.97 亿元、较昨日减少 17.27%。",
    )
    assert _rule(result, "fact:amount_vs_yesterday_pct").state is VerdictState.PASS
    mention = _rule(result, "must_mention")
    assert mention.state is VerdictState.PASS
    assert "discharged by stricter rules" in mention.reason


def test_discharge_does_not_fire_when_the_stricter_rule_fails() -> None:
    """更严的规则没过，措辞要求原样生效——解除不是无条件豁免。

    这条是「不为绿灯放宽判据」的守卫：数值没答对时，缩量这条不能被顺手放过。
    """
    result = _mention_case(
        {"phrase_discharged_by": {"缩量": "fact:amount_vs_yesterday_pct"}},
        "成交额 21949.97 亿元、较昨日减少 3.10%。",
    )
    assert _rule(result, "fact:amount_vs_yesterday_pct").state is VerdictState.FAIL
    assert _rule(result, "must_mention").state is VerdictState.FAIL


def test_discharge_pointing_at_an_unknown_rule_is_a_contract_diagnostic() -> None:
    """规则名打错必须报出来，不能静默失效（那样看板上完全看不出判据坏了）。"""
    contract = compile_case_contract(
        {
            "id": "A1",
            "tier": "high_freq",
            "query": "market",
            "must_mention": ["缩量"],
            "pass_rule": "language",
        },
        {"coverage": "structured", "phrase_discharged_by": {"缩量": "fact:typo_field"}},
    )
    assert any("names unknown rule" in item for item in contract.diagnostics)
    assert not contract.phrase_discharged_by


def _inconsistency_case(answer: str, *, with_facts: bool = True):
    case = {
        "id": "A9",
        "tier": "high_freq",
        "query": "sentiment",
        "require_flag_inconsistency": True,
        "pass_rule": "必须指出边际强度与状态互相矛盾",
    }
    overlay = {"coverage": "structured"}
    if with_facts:
        case["expect_facts"] = [
            {"field": "strength_marginal_pct", "value": -66.3, "tol_abs": 1.0},
            {"field": "strength_status", "value": "沸点"},
        ]
        overlay["fact_aliases"] = {"strength_marginal_pct": ["强度"]}
    return evaluate_case(compile_case_contract(case, overlay), _completed(answer))


def test_inconsistency_needs_its_operands_not_just_the_word() -> None:
    """光在正文别处写了「矛盾」，不等于指出了**这个**矛盾。

    A9 实测：三次运行「沸点」和「-66.3%」一个都没出现，前两次却因为别处有
    「矛盾」判 PASS——假绿。锚定到声明的两端后，这里必须判 FAIL。
    """
    result = _inconsistency_case("盘面情绪偏热，个股表现与指数走势存在矛盾。")
    rule = _rule(result, "inconsistency")
    assert rule.state is VerdictState.FAIL
    assert "operands are absent" in rule.reason


def test_inconsistency_passes_when_both_operands_are_on_the_page() -> None:
    """两端都摆出来了、也点了矛盾——这才是陷阱题要的答案。"""
    result = _inconsistency_case(
        "状态标记为沸点，但边际强度 -66.3%，两者互相矛盾，不能直接照抄沸点当结论。"
    )
    assert _rule(result, "inconsistency").state is VerdictState.PASS


def test_inconsistency_without_declared_operands_keeps_marker_behaviour() -> None:
    """C5 靠重复值发现矛盾，没有可锚的结构化端点——维持原关键词行为。"""
    result = _inconsistency_case("两日收盘价完全相同，数据存在矛盾。", with_facts=False)
    assert _rule(result, "inconsistency").state is VerdictState.PASS


def test_literal_fact_absent_from_the_whole_answer_is_a_failure() -> None:
    """字面量不在全文里就是真不在，不存在「定位不到」。

    A9 的别名表 ["状态","沸点"] 里「沸点」既是定位别名又是期望值，于是
    「没出现」被 #11 的别名未命中规则记成不可判，三次运行在 ❔/❌ 之间来回翻。
    """
    contract = compile_case_contract(
        {
            "id": "A9",
            "tier": "high_freq",
            "query": "sentiment",
            "expect_facts": [{"field": "strength_status", "value": "沸点"}],
            "pass_rule": "facts",
        },
        {"coverage": "structured", "fact_aliases": {"strength_status": ["状态", "沸点"]}},
    )
    rule = _rule(evaluate_case(contract, _completed("市场情绪偏热。")), "fact:strength_status")
    assert rule.state is VerdictState.FAIL
    assert "absent from the whole answer" in rule.reason


def test_numeric_alias_miss_stays_unjudgeable() -> None:
    """字面量的收紧不能渗到数值上：光有个数字证明不了它绑在这个字段上。

    #11 那条别名未命中→不可判是为数值设计的，这里守住它没被一起改掉。
    """
    contract = _fact_contract({"amount_vs_yesterday_pct": ["环比", "较昨日"]})
    result = evaluate_case(
        contract, _completed("全市场成交额 21949.97 亿元，较上一交易日缩减 17.27%。")
    )
    assert _rule(result, "fact:amount_vs_yesterday_pct").state is VerdictState.UNJUDGEABLE


def test_relative_time_question_with_frozen_facts_is_flagged() -> None:
    """问「现在」而期望值冻在某一天 —— 判官必须报出来，不能当产品失败。

    A8 实测：产品答「截至 2026-07-30，底部横盘阶段，第 2 个交易日」，完全正确；
    expect_facts 冻的是 2026-07-23 的「反弹阶段 / 第 3 天」。runner 只发
    case["query"]，date 字段根本到不了产品手上。
    """
    contract = compile_case_contract(
        {
            "id": "A8",
            "tier": "high_freq",
            "query": "现在市场处于什么阶段，第几天了",
            "date": "2026-07-23",
            "expect_facts": [{"field": "stage_day", "value": 3, "tol_abs": 0}],
            "pass_rule": "阶段名称与天数都正确",
        },
        {"coverage": "structured"},
    )
    assert any("not reproducible" in item for item in contract.diagnostics)


def test_date_anchored_query_is_not_flagged() -> None:
    """日期写进了问题正文就可复现 —— A1 的「2026-07-23 今天市场怎么样」不该误报。"""
    contract = compile_case_contract(
        {
            "id": "A1",
            "tier": "high_freq",
            "query": "2026-07-23 今天市场怎么样",
            "date": "2026-07-23",
            "expect_facts": [{"field": "total_amount", "value": 21949.97, "tol_pct": 1.0}],
            "pass_rule": "facts",
        },
        {"coverage": "structured"},
    )
    assert not contract.diagnostics


def test_relative_time_without_dated_expectations_is_not_flagged() -> None:
    """B8「立新能源现在贵不贵」只断言实体在场，跟哪天问无关，不该误报。"""
    contract = compile_case_contract(
        {
            "id": "B8",
            "tier": "mid_freq",
            "query": "立新能源现在贵不贵，隐含了什么预期",
            "date": "2026-07-23",
            "expect_entities": ["立新能源"],
            "pass_rule": "估值带",
        },
        {"coverage": "semantic_required", "reason": "valuation judgment is not structured"},
    )
    assert not contract.diagnostics


def test_unreproducible_case_lands_on_unjudgeable_not_fail() -> None:
    """题目缺陷必须落在「不可判」，不能混进产品的失败计数里。"""
    contract = compile_case_contract(
        {
            "id": "A8",
            "tier": "high_freq",
            "query": "现在市场处于什么阶段，第几天了",
            "date": "2026-07-23",
            "expect_facts": [{"field": "stage_day", "value": 3, "tol_abs": 0}],
            "pass_rule": "阶段名称与天数都正确",
        },
        {"coverage": "structured"},
    )
    verdict = evaluate_case(contract, _completed("截至 2026-07-30，底部横盘阶段，第 2 个交易日。"))
    assert verdict.truth.state is VerdictState.UNJUDGEABLE
    assert _rule(verdict, "case_reproducibility").state is VerdictState.UNJUDGEABLE


def test_benign_degrades_do_not_mark_a_turn_degraded() -> None:
    """良性降级（数据未到 / 该题材无发酵信号）不该判成降级完成。

    95 条降级事件里三分之一不是降级——信号被噪声稀释后，「这一刀有没有用」
    就读不出来了。但名单只做减法：未登记的一律按真降级，宁可多报不可漏报。
    """
    from intelligence.eval.acceptance_verdict import (
        OperationalState,
        _evaluate_operational,
        classify_degrade,
    )

    assert classify_degrade("盘面快照回退到 2026-07-30（2026-07-31 尚无候选）") == "benign"
    assert classify_degrade("模块 replay：theme_signals.json 无匹配主题，replay 跳过") == "benign"
    # 未登记的新故障必须按真降级处理，不能静默消失
    assert classify_degrade("某个还没见过的新故障") == "real"
    assert classify_degrade("llm_unavailable_template_answer") == "real"

    benign_only = {
        "turns": [{"status": "completed", "degrades": ["盘面快照回退到 2026-07-30"]}]
    }
    assert _evaluate_operational(benign_only).state is OperationalState.COMPLETED

    mixed = {
        "turns": [
            {
                "status": "completed",
                "degrades": ["盘面快照回退到 2026-07-30", "知识库检索失败（退出码 1）"],
            }
        ]
    }
    verdict = _evaluate_operational(mixed)
    assert verdict.state is OperationalState.DEGRADED
    # 原因必须点名真降级，而不是「one or more turns reported degradation」
    assert "知识库检索失败" in verdict.reason
    assert "1 条良性" in verdict.reason

"""内容正确性题集（2026-10-01 质检 P1）：恒等式、抽数、判分与夹具。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.eval import content_correctness as cc

REPO = Path(__file__).resolve().parents[2]


def test_identities_match_hand_calculation() -> None:
    # 手算锚点：恒等式代码一旦改错，这里先红。
    cases = {c.id: c for c in cc.load_cases()}
    assert cases["cc-cfo-01"].expected == pytest.approx(8.9)  # 10+3+1.5-0.8-4-2+1.2
    assert cases["cc-cfo-04"].expected == pytest.approx(8.4)  # 亏损但经营现金流为正
    assert cases["cc-sf-01"].expected == pytest.approx(-2.5)  # 7.5-10
    assert cases["cc-sf-02"].expected == pytest.approx(1.1)  # 9.8-7.2-1.5
    assert cases["cc-sf-03"].expected == pytest.approx(2.5)  # (15+4.5-5-2+1)-11
    assert cases["cc-sf-01"].trap_values() == {"ni_minus_capex": pytest.approx(2.0)}


def test_case_set_covers_the_three_error_classes() -> None:
    cases = cc.load_cases()
    by_class = {cls: [c for c in cases if c.error_class == cls] for cls in cc.ERROR_CLASSES}
    assert all(len(v) >= 5 for v in by_class.values()), {k: len(v) for k, v in by_class.items()}
    assert len({c.id for c in cases}) == len(cases)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("盈余2.4亿元", [2.4]),  # 汉字紧贴数字（Python 的 \w 会把它漏掉）
        ("缺口 3,500万元", [0.35]),
        ("−2.5亿元", [2.5]),
        ("2026-09-04 与 9月1日 都不是金额", []),
        ("D3 仍无订单，Q4 投产，增长20%", []),
        ("2026年四季度", []),
    ],
)
def test_extract_amounts(text: str, expected: list[float]) -> None:
    assert cc.extract_amounts(text) == pytest.approx(expected)


def test_gold_answers_pass_and_bad_answers_fail_for_the_labelled_reason() -> None:
    cases = {c.id: c for c in cc.load_cases()}
    fixtures = cc.load_fixtures()
    assert set(fixtures) == set(cases)
    for case_id, fx in fixtures.items():
        assert fx["gold"] and fx["bad"], case_id
        for answer in fx["gold"]:
            result = cc.score(cases[case_id], answer)
            assert result.passed, (case_id, result.failures)
        for answer, kind in fx["bad"]:
            result = cc.score(cases[case_id], answer)
            assert not result.passed, (case_id, answer)
            assert any(kind in f for f in result.failures), (case_id, kind, result.failures)


def test_format_perfect_but_wrong_answers_still_fail() -> None:
    """古德哈特：结构齐全（结论 / 依据 / 风险）不等于内容正确——09-29 前三次首发就是这样过的门。"""

    cases = {c.id: c for c in cc.load_cases()}
    structured = [
        (case_id, answer)
        for case_id, fx in cc.load_fixtures().items()
        for answer, _ in fx["bad"]
        if answer.startswith("## 结论")
    ]
    assert len(structured) >= 8
    for case_id, answer in structured:
        assert not cc.score(cases[case_id], answer).passed, case_id


def test_the_three_0929_error_shapes_are_caught() -> None:
    cases = {c.id: c for c in cc.load_cases()}
    # 时点：把「D0 未获单」写成「D3 仍无订单」
    assert not cc.score(cases["cc-tp-01"], "D3 仍无订单，项目推进不及预期。").passed
    # 存量与流量：让净利润去承担现金资本开支
    assert not cc.score(cases["cc-sf-01"], "净利润12亿元覆盖资本开支10亿元后还剩2亿元。").passed
    # CFO 起点：营运资本方向做反
    assert not cc.score(cases["cc-cfo-01"], "经营现金流 18.5 亿元。").passed


def test_citing_the_observed_date_does_not_excuse_a_present_tense_claim() -> None:
    case = {c.id: c for c in cc.load_cases()}["cc-tp-01"]
    assert not cc.score(case, "根据9月1日公告，公司目前仍未获单。").passed
    assert cc.score(case, "9月1日公告时公司尚未获得订单；此后是否获单，材料没有覆盖。").passed


def test_trap_colliding_with_a_fact_is_rejected() -> None:
    bad = cc.Case(
        id="x",
        error_class="stock_flow",
        company="测试",
        question="q",
        facts={"net_income": 12, "cfo": 7.5, "capex": 10, "dividends": 2},
        expected_identity="fcf",
        traps=("ni_minus_capex",),  # 12-10=2 与分红 2 撞车 → 不再是错误指纹
    )
    with pytest.raises(ValueError, match="撞车"):
        cc._assert_well_formed(bad)


def test_prompts_carry_every_fact_and_never_the_answer() -> None:
    for case in cc.load_cases():
        prompt = case.prompt()
        assert case.question in prompt
        for value in case.facts.values():
            if isinstance(value, (int, float)):
                assert f"{value:g}" in prompt, (case.id, value)
            else:
                assert value in prompt
        if case.expected is not None:
            shown = cc.extract_amounts(prompt, default_unit=case.unit)
            assert all(abs(a - abs(case.expected)) > 0.011 for a in shown), case.id


def test_cli_score_counts_missing_answers_as_failures(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("cc_cli", REPO / "scripts" / "content_correctness_eval.py")
    assert spec and spec.loader
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    gold = {cid: fx["gold"][0] for cid, fx in cc.load_fixtures().items()}
    gold.pop("cc-tp-05")
    answers = tmp_path / "answers.jsonl"
    answers.write_text(
        "".join(json.dumps({"case_id": k, "answer": v}, ensure_ascii=False) + "\n" for k, v in gold.items()),
        encoding="utf-8",
    )
    assert cli.main(["score", "--answers", str(answers), "--json"]) == 0
    assert cli.main(["selftest"]) == 0
    results = [
        cc.score(c, gold[c.id]) if c.id in gold else cc.CaseResult(c.id, c.error_class, False, ["未作答"])
        for c in cc.load_cases()
    ]
    report = cc.summarize(results)
    assert report["total"] == 15 and report["passed"] == 14
    assert report["failures"] == {"cc-tp-05": ["未作答"]}

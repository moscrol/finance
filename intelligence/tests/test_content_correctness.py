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


@pytest.mark.parametrize("case_id,answer", [
    ("cc-sf-01", "本期经营现金流足以覆盖资本开支，盈余2.5亿元。"),
    ("cc-sf-01", "正2.5亿元，现金盈余2.5亿元。"),
    ("cc-unit-02", "自由现金流为 +2.28亿元。"),
    ("cc-cfo-01", "经营现金流为 -8.9亿元。"),
    ("cc-sf-03", "资本开支后的现金缺口为2.5亿元。"),
    ("cc-unit-02", "自由现金流为 -2.28亿元，同时盈余2.28亿元。"),
])
def test_opposite_cash_direction_cannot_pass_by_magnitude(case_id, answer):
    case = {case.id: case for case in cc.load_cases()}[case_id]
    assert not cc.score(case, answer).passed


@pytest.mark.parametrize("answer", ["存在2.5亿元缺口。", "现金缺口为2.5亿元。", "自由现金流为负2.5亿元。"])
def test_explicit_deficit_direction_is_a_valid_negative_result(answer):
    case = {case.id: case for case in cc.load_cases()}["cc-sf-01"]
    assert cc.score(case, answer).passed


def test_timepoint_anchor_and_denial_are_scoped_to_the_actual_assertion():
    cases = {case.id: case for case in cc.load_cases()}
    assert not cc.score(cases["cc-tp-01"], "根据9月1日公告，公司当时未获单，目前仍未获单。").passed
    assert cc.score(cases["cc-tp-02"], "8月20日公告说计划在四季度投产，不能视作已正式投产。").passed
    assert not cc.score(cases["cc-tp-02"], "8月20日公告说计划投产，不能视作已正式投产，但公司已投产。").passed


@pytest.mark.parametrize("wrapper", ["{}", "**{}**", "__{}__", "`{}`", "*{}*"])
def test_display_formatting_preserves_cash_direction(wrapper):
    cases = {case.id: case for case in cc.load_cases()}
    answer = "现金缺口为 " + wrapper.format("2.5亿元") + "。"
    assert cc.score(cases["cc-sf-01"], answer).passed
    assert not cc.score(cases["cc-sf-03"], answer).passed


@pytest.mark.parametrize("sign", ["−", "-"])
def test_spaced_negative_sign_preserves_result_direction(sign):
    case = {case.id: case for case in cc.load_cases()}["cc-unit-02"]
    assert cc.score(case, f"自由现金流为 {sign} 2.28 亿元。").passed


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_markdown_heading_boundary_does_not_become_a_negative_sign(newline):
    cases = {case.id: case for case in cc.load_cases()}
    answer = newline.join(("自由现金流", "---", "2.5亿元。"))
    assert cc.score(cases["cc-sf-03"], answer).passed
    assert not cc.score(cases["cc-sf-01"], answer).passed


def test_current_time_context_and_epistemic_denial_survive_clause_boundaries():
    case = {case.id: case for case in cc.load_cases()}["cc-tp-01"]
    assert not cc.score(case, "9月1日公告时尚未获得订单，截至目前，公司仍未获单。").passed
    assert cc.score(case, "9月1日公告时尚未获得订单；目前不能视作未获单。").passed
    assert not cc.score(case, "9月1日公告时尚未获得订单；目前并非未获单。").passed


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
                assert cc._fmt(value) in prompt, (case.id, value)
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
    assert report["total"] == len(cc.load_cases()) and report["passed"] == report["total"] - 1
    assert report["failures"] == {"cc-tp-05": ["未作答"]}


def test_cli_cases_output_is_explicit_and_preserves_missing_answers(tmp_path: Path, capsys) -> None:
    from scripts import content_correctness_eval as cli, harness_tier_gate as gate

    answers = tmp_path / "answers.jsonl"
    fixtures = cc.load_fixtures()
    missing = next(iter(fixtures))
    answers.write_text("".join(
        json.dumps({"case_id": cid, "answer": fx["gold"][0]}, ensure_ascii=False) + "\n"
        for cid, fx in fixtures.items() if cid != missing
    ), encoding="utf-8")
    assert cli.main(["score", "--answers", str(answers), "--cases-json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert set(report) == {"cases"}
    assert set(report["cases"]) == set(fixtures)
    assert report["cases"][missing] is False
    assert all(value is True for key, value in report["cases"].items() if key != missing)
    outcomes = gate.case_outcomes(report)
    assert gate.gate(outcomes, outcomes, outcomes, outcomes)["verdict"] == "INCONCLUSIVE"

    # Preserve the original human/summary consumers; do not silently change --json.
    assert cli.main(["score", "--answers", str(answers), "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert "cases" not in summary
    assert summary["passed"] == len(fixtures) - 1
    assert summary["failures"] == {missing: ["未作答"]}


@pytest.mark.parametrize("rows,reason", [
    ([{"case_id": "foreign-id", "answer": "答案"}], "未知题号"),
    ([{"case_id": "cc-tp-01", "answer": "错答"},
      {"case_id": "cc-tp-01", "answer": "另答"}], "重复题号"),
    ([{"case_id": "cc-tp-01", "answer": True}], "字符串"),
    ([{"case_id": "", "answer": "答案"}], "题号"),
    ([{"answer": "答案"}], "题号"),
    ([[]], "对象"),
])
def test_cli_cases_rejects_ambiguous_answer_rows(tmp_path: Path, capsys, rows, reason: str) -> None:
    from scripts import content_correctness_eval as cli

    answers = tmp_path / "answers.jsonl"
    answers.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert cli.main(["score", "--answers", str(answers), "--cases-json"]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert reason in output.err


@pytest.mark.parametrize("text", [
    '{"case_id":"cc-tp-01","answer":"错答","answer":"另答"}',
    '{broken json}',
])
def test_cli_cases_rejects_duplicate_keys_and_invalid_json(tmp_path: Path, capsys, text: str) -> None:
    from scripts import content_correctness_eval as cli

    answers = tmp_path / "answers.jsonl"
    answers.write_text(text, encoding="utf-8")
    assert cli.main(["score", "--answers", str(answers), "--cases-json"]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert "输入错误" in output.err


@pytest.mark.parametrize("kind", ["all_gold", "wrong_answer", "empty"])
def test_cli_cases_scores_each_answer_instead_of_inventing_passes(tmp_path: Path, capsys, kind: str) -> None:
    from scripts import content_correctness_eval as cli

    fixtures = cc.load_fixtures()
    rows = {cid: fx["gold"][0] for cid, fx in fixtures.items()} if kind != "empty" else {}
    failed = next(iter(fixtures))
    if kind == "wrong_answer":
        rows[failed] = fixtures[failed]["bad"][0][0]
    answers = tmp_path / "answers.jsonl"
    answers.write_text("".join(
        json.dumps({"case_id": cid, "answer": answer}) + "\n" for cid, answer in rows.items()
    ), encoding="utf-8")
    assert cli.main(["score", "--answers", str(answers), "--cases-json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {"cases": {
        cid: kind != "empty" and not (kind == "wrong_answer" and cid == failed) for cid in fixtures
    }}


def test_cli_summary_still_reports_unknown_answer_ids(tmp_path: Path, capsys) -> None:
    from scripts import content_correctness_eval as cli

    answers = tmp_path / "answers.jsonl"
    answers.write_text('{"case_id":"foreign-id","answer":"答案"}\n', encoding="utf-8")
    assert cli.main(["score", "--answers", str(answers), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["unknown_case_ids"] == ["foreign-id"]
    assert report["passed"] == 0


def test_cli_summary_and_cases_formats_are_mutually_exclusive(tmp_path: Path) -> None:
    from scripts import content_correctness_eval as cli

    with pytest.raises(SystemExit) as error:
        cli.main(["score", "--answers", str(tmp_path / "unused"), "--json", "--cases-json"])
    assert error.value.code == 2


# ---------------------------------------------------------------------------
# 单位与量纲（第四类，10-01 后补）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 长单位在前：旧顺序把「1.41万亿元」读成 1.41 万元
        ("两市成交约1.41万亿元", [14100.0]),
        ("合计 1,409,071,000 千元", [14090.71]),
        # 四位整数带小数是金额，不是「年.月」：旧日期正则把它们整个删掉
        ("减少约 2935.28 亿元", [2935.28]),
        ("昨日约 17025.99 亿元", [17025.99]),
        ("2026.5亿元", [2026.5]),
        # 真日期照样剔除
        ("2026-09-01 公告，2026年9月1日，2026.09.01，截至2026年9月", []),
    ],
)
def test_extract_amounts_unit_and_date_regressions(text: str, expected: list[float]) -> None:
    assert cc.extract_amounts(text) == pytest.approx(expected)


def test_extract_rates_separates_percent_from_percentage_points() -> None:
    assert cc.extract_rates("提升3个百分点，相对提升12%，即3pct，或 5 百分点") == [
        (3.0, "pp"), (12.0, "pct"), (3.0, "pp"), (5.0, "pp"),
    ]


def test_unit_class_traps_are_read_in_their_own_quantity() -> None:
    """「3 个百分点」对、「3%」错：同一个数，量纲决定对错。"""

    case = {c.id: c for c in cc.load_cases()}["cc-unit-03"]
    assert cc.score(case, "毛利率提升 3 个百分点。").passed
    result = cc.score(case, "毛利率提升 3%。")
    assert not result.passed
    assert any("pp_as_pct" in f for f in result.failures)
    assert any("缺正确值" in f for f in result.failures)


def test_unit_class_expected_values_come_from_identities() -> None:
    cases = {c.id: c for c in cc.load_cases()}
    # 14090.71 − 14009.23（09-29 补行后的真实两日成交额，行情库 amount 单位千元）
    assert cases["cc-unit-01"].expected == pytest.approx(81.48)
    assert cases["cc-unit-02"].expected == pytest.approx(1.82 - 4.1)
    # 昨日 = 今日 / (1 − 17.24%)；减少额 = 昨日 − 今日
    assert cases["cc-unit-04"].expected == pytest.approx(14090.71 / 0.8276 - 14090.71, abs=1e-3)
    # 20 日均额 = 今日 / 0.7688
    assert cases["cc-unit-05"].expected == pytest.approx(14090.71 / 0.7688, abs=1e-3)


def test_facts_are_normalized_before_the_collision_check() -> None:
    """题面事实按自己的单位换算后再和陷阱值比：千元原值 1,409,071,000 不该挡住任何陷阱，
    换算后的 14090.71 亿元撞上陷阱才算撞车。"""

    bad = cc.Case(
        id="x",
        error_class="unit",
        company="测试",
        question="q",
        facts={"turnover": 14090.71, "amount_chg_pct": -17.24},
        fact_units={"turnover": "千元", "amount_chg_pct": "%"},
        expected_identity="dod_change_amount",
        # 「读成亿元」陷阱 17.24 与事实「−17.24 %」数值相同，但量纲不同 → 不撞车
        traps=("dod_pct_read_as_yi",),
    )
    cc._assert_well_formed(bad)
    clash = cc.Case(
        id="y",
        error_class="unit",
        company="测试",
        question="q",
        facts={"turnover": 14090.71, "amount_chg_pct": -17.24, "other": 17.24},
        fact_units={"amount_chg_pct": "%", "other": "亿元"},
        expected_identity="dod_change_amount",
        traps=("dod_pct_read_as_yi",),
    )
    with pytest.raises(ValueError, match="撞车"):
        cc._assert_well_formed(clash)

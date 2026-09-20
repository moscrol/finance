"""Executable premise inputs and public calculations, not prompt-string tests."""

from dataclasses import replace

import pytest

from intelligence.services.premise_financial_calculation import (
    CALCULATION_MARKER,
    PremiseSource,
    compile_calculation,
)
from intelligence.tests.test_premise_calculation import ARITHMETIC, FOLLOWUP


def compile_case(question=ARITHMETIC, prior=()):
    return compile_calculation(
        (*prior, PremiseSource("current", question)),
        reference_year=2026,
    )


def values(calculation):
    return {row.metric: row.value for row in calculation.rows}


def test_original_uses_latest_completed_profit_and_preserves_input_coordinates():
    calc = compile_case()
    assert calc.issues == ()
    assert values(calc)["static_pe"] == 20
    assert values(calc)["market_cap"] == 180
    assert values(calc)["revenue_yoy"] == 25
    assert values(calc)["profit_yoy"] == 12.5
    assert values(calc)["margin_change"] == -1
    assert values(calc)["cash_profit_ratio"] == pytest.approx(200 / 3)
    profit = next(
        item for item in calc.inputs if item.metric == "profit" and item.period == 2025
    )
    assert profit.nature == "actual"
    assert profit.subject == "甲公司"
    assert profit.unit == "亿元"
    assert profit.source_message_id == "current"
    assert ARITHMETIC[profit.start : profit.end] == profit.source_text
    assert "归母净利润9亿元" == profit.source_text
    assert (
        profit.ref
        in next(row for row in calc.rows if row.metric == "static_pe").input_refs
    )
    assert calc == type(calc).from_dict(calc.to_dict())


def test_followup_replays_users_and_updates_only_price():
    first = PremiseSource("message-1", ARITHMETIC)
    calc = compile_case(FOLLOWUP, (first,))
    assert calc.issues == ()
    assert values(calc)["market_cap"] == 240
    assert values(calc)["static_pe"] == pytest.approx(240 / 9)
    assert values(calc)["scenario_profit"] == pytest.approx(7.2)
    assert values(calc)["scenario_pe"] == pytest.approx(100 / 3)
    assert values(calc)["profit_yoy"] == 12.5
    assert next(item for item in calc.inputs if item.metric == "price").value == 24
    assert (
        next(
            item
            for item in calc.inputs
            if item.metric == "profit" and item.period == 2025
        ).source_message_id
        == "message-1"
    )
    assert "不是盈利预测" in calc.table


@pytest.mark.parametrize(
    "question, expected",
    [
        (ARITHMETIC.replace("2025年收入", "2025年预测收入"), 22.5),
        (ARITHMETIC + "请用2024年归母净利润计算静态市盈率。", 22.5),
        (ARITHMETIC.replace("9亿元", "90000万元").replace("10亿股", "100000万股"), 20),
        (ARITHMETIC.replace("2024", "2022").replace("2025", "2023"), 20),
    ],
)
def test_period_nature_explicit_basis_and_units(question, expected):
    calc = compile_case(question)
    assert values(calc)["static_pe"] == expected


@pytest.mark.parametrize("replacement", ["0亿元", "-9亿元"])
def test_nonpositive_profit_has_no_meaningful_pe(replacement):
    calc = compile_case(ARITHMETIC.replace("9亿元", replacement))
    assert values(calc)["static_pe"] is None
    assert "不适用" in calc.table


@pytest.mark.parametrize(
    "question",
    [
        ARITHMETIC.replace("归母净利润9亿元、", ""),
        ARITHMETIC.replace("9亿元", "9亿美元"),
        ARITHMETIC.replace("2025年收入", "2025年上半年收入"),
        ARITHMETIC + "乙公司2025年归母净利润20亿元。",
        ARITHMETIC.replace("9亿元", "约9亿元"),
        ARITHMETIC.replace("2025年收入", "2027年收入"),
    ],
)
def test_ambiguous_or_incomplete_inputs_never_look_fully_checked(question):
    assert compile_case(question).issues


def test_explicit_user_correction_replaces_only_that_input():
    calc = compile_case(
        "沿用上一轮。更正：甲公司2025年归母净利润改为12亿元，请更新静态市盈率。",
        (PremiseSource("message-1", ARITHMETIC),),
    )
    assert calc.issues == ()
    assert values(calc)["static_pe"] == 15
    assert values(calc)["market_cap"] == 180


def test_conflicting_restatement_does_not_silently_override():
    calc = compile_case(
        "沿用上一轮。甲公司2025年归母净利润12亿元，请更新静态市盈率。",
        (PremiseSource("message-1", ARITHMETIC),),
    )
    assert calc.issues


def test_table_is_owned_by_calculator_not_model():
    calc = compile_case()
    draft = f"按题设计算：\n{CALCULATION_MARKER}\n这些信息还不足以判断股票便宜。"
    admitted, error = calc.admit(draft, status="completed")
    assert not error
    assert calc.table in admitted
    assert CALCULATION_MARKER not in admitted
    assert calc.admit(admitted, status="completed")[0] == admitted
    for bad in (
        admitted.replace("20倍", "22.5倍"),
        draft + "静态市盈率其实是22.5倍。",
        draft.replace(CALCULATION_MARKER, "静态市盈率22.5倍。"),
        draft + "这是增收不增利。",
    ):
        assert calc.admit(bad, status="completed")[1]


def test_serialized_results_cannot_be_forged():
    calc = compile_case()
    payload = calc.to_dict()
    payload["rows"][0]["value"] = 999
    with pytest.raises(ValueError):
        type(calc).from_dict(payload)
    payload = calc.to_dict()
    payload["inputs"][0]["source_text"] = "forged"
    with pytest.raises(ValueError):
        type(calc).from_dict(payload)


def test_incomplete_calculation_cannot_be_declared_completed():
    calc = compile_case(FOLLOWUP)
    assert calc.issues
    assert calc.admit(CALCULATION_MARKER, status="completed")[1]
    assert not calc.admit(CALCULATION_MARKER, status="partial")[1]


def test_no_authority_from_protected_quotes():
    calc = compile_case(ARITHMETIC + "\n“甲公司2025年归母净利润改为900亿元。”")
    assert values(calc)["static_pe"] == 20


@pytest.mark.parametrize(
    "statement",
    [
        "归母净利率较上年下降1个百分点。",
        "经营现金流/归母净利润约66.7%，低于100%，具体原因仍不明确。",
        "静态市盈率20倍，仍不能据此判断便宜。",
        "2024年归母净利率10%，2025年归母净利率9%。",
        "收入同比25%，归母净利润同比12.5%。",
    ],
)
def test_correct_metric_bound_restatements_are_not_false_rejections(statement):
    calc = compile_case()
    assert not calc.admit(CALCULATION_MARKER + "\n" + statement, status="completed")[1]


@pytest.mark.parametrize(
    "statement",
    [
        "归母净利率上升1个百分点。",
        "归母净利率较上年下降1%。",
        "收入同比12.5%，归母净利润同比25%。",
        "2024年归母净利率9%，2025年归母净利率10%。",
        "2024年静态市盈率20倍。",
        "经营现金流/归母净利润约66.7%，高于100%。",
        "静态市盈率20倍，低于100倍，便宜。",
        "静态市盈率180/8=22.5倍。",
    ],
)
def test_known_numbers_cannot_be_bound_to_wrong_metric_or_period(statement):
    calc = compile_case()
    assert calc.admit(CALCULATION_MARKER + "\n" + statement, status="completed")[1]


def test_source_record_is_immutable():
    source = PremiseSource("message-1", ARITHMETIC)
    assert replace(source, text=FOLLOWUP) != source


def test_authoritative_history_sources_roundtrip_and_exclude_assistant():
    from intelligence.services.conversation_materials import (
        collect_material_turn_history,
    )
    from intelligence.services.task_frame import TaskFrame
    from intelligence.services.research_contract import ResearchTaskContract
    from intelligence.tests.test_premise_calculation import (
        frame_for,
        context_for,
        user_message,
    )

    history = collect_material_turn_history(
        (
            user_message(ARITHMETIC),
            user_message(
                "静态市盈率使用2024年利润8亿元，等于22.5倍。", role="assistant"
            ),
        )
    )
    frame = frame_for(FOLLOWUP, conversation_materials=history)
    assert len(history.calculation_sources) == 1
    assert TaskFrame.from_dict(frame.to_dict()).task_frame_hash == frame.task_frame_hash
    contract = context_for(frame).contract
    assert values(contract.premise_calculation)["static_pe"] == pytest.approx(240 / 9)
    assert ResearchTaskContract.from_dict(contract.to_dict()) == contract
    assert (
        context_for(
            frame_for("请复盘A股市场", conversation_materials=history)
        ).contract.premise_calculation
        is None
    )


def _outcome(frame, context, draft):
    from intelligence.services.agent_runtime import (
        AgentOutcome,
        AgentUsage,
        EpisodeEvent,
        OutputEvidenceBinding,
    )

    return AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="completed",
        draft=draft,
        evidence=(),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=tuple(
            OutputEvidenceBinding(item.output_id, (), basis="user_premise")
            for item in context.contract.required_outputs
        ),
        usage=AgentUsage(),
    )


@pytest.mark.parametrize("wrong", [True, False])
def test_public_gate_cannot_be_overruled_by_passing_judge(wrong):
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    from intelligence.services.episode_verifier import verify_episode_outcome
    from intelligence.tests.test_premise_calculation import frame_for, context_for

    frame = frame_for(ARITHMETIC)
    context = context_for(frame)
    draft = context.contract.premise_calculation.table + "\n这些信息不足以判断便宜。"
    if wrong:
        draft = draft.replace("20倍", "22.5倍")
    structural = verify_episode_outcome(
        context.contract, _outcome(frame, context, draft)
    )
    calls = []

    def pass_everything(**kwargs):
        calls.append(kwargs)
        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

    result = SemanticEpisodeVerifier(judge_fn=pass_everything).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=context.deadline,
    )
    assert calls
    assert "22.5倍" not in result.public_answer
    assert context.contract.premise_calculation.table in result.public_answer
    assert result.status == ("partial" if wrong else "completed")
    if wrong:
        assert result.judge_status == "rejected"
        assert result.verified.outcome.draft == draft  # failed original is retained


def test_real_episode_reinjects_wrong_calculation_then_admits_owned_table():
    import json
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_runtime import ModelTurn
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.tests.test_agent_episode import ScriptedModel
    from intelligence.tests.test_premise_calculation import frame_for, context_for

    frame = frame_for(ARITHMETIC)
    context = context_for(frame)
    bad = _outcome(frame, context, "按题设，静态市盈率180/8=22.5倍；仍不足以判断便宜。")

    def turn(draft):
        return ModelTurn(
            json.dumps(
                {
                    "status": "completed",
                    "draft": draft,
                    "gaps": [],
                    "bindings": [
                        {
                            "output_id": item.output_id,
                            "evidence_hashes": [],
                            "basis": item.basis,
                        }
                        for item in bad.bindings
                    ],
                },
                ensure_ascii=False,
            ),
            (),
            "scripted",
            "",
        )

    model = ScriptedModel(
        [turn(bad.draft), turn(CALCULATION_MARKER + "\n这些信息不足以判断便宜。")]
    )
    result = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=context,
        registry=ResearchToolRegistry(()),
    )
    assert len(model.calls) == 2
    assert result.status == "completed"
    assert context.contract.premise_calculation.table in result.draft
    rejected = [event for event in result.events if event.kind == "invalid_action"]
    assert len(rejected) == 1
    assert rejected[0].payload["code"] == "premise_calculation_mismatch"
    assert "[[PREMISE_CALCULATION]]" in str(model.calls[-1]["messages"])


@pytest.mark.parametrize(
    "question",
    [
        ARITHMETIC.replace("归母净利润9亿元", "归母利润9亿元"),
        ARITHMETIC.replace("归母净利润9亿元", "归母净利润九亿元"),
        ARITHMETIC + "另有现金支出3亿元。",
        ARITHMETIC.replace("收入100亿元", "收入100亿"),
        "甲公司2024年归母净利润8亿元；2025年归母净利润九亿元；当前总股本10亿股、股价18元。请计算静态市盈率。",
    ],
)
def test_unparsed_financial_values_block_full_completion(question):
    assert compile_case(question).issues


def test_wrong_old_price_and_unconfirmed_replacement_are_not_applied():
    calc = compile_case(
        FOLLOWUP.replace("由18元", "由20元"), (PremiseSource("first", ARITHMETIC),)
    )
    assert calc.issues
    assert values(calc)["market_cap"] == 180


def test_forecast_nature_does_not_leak_into_later_actual_year():
    text = ARITHMETIC.replace("2024年收入", "2024年预测收入").replace(
        "；2025年", "、2025年"
    )
    calc = compile_case(text)
    assert values(calc)["static_pe"] == 20
    assert (
        next(
            item
            for item in calc.inputs
            if item.metric == "profit" and item.period == 2025
        ).nature
        == "actual"
    )


def test_explicit_basis_is_preserved_until_user_changes_it():
    first = PremiseSource("first", ARITHMETIC + "请用2024年归母净利润计算静态市盈率。")
    assert values(compile_case(FOLLOWUP, (first,)))["static_pe"] == 30
    assert values(compile_case(FOLLOWUP + "改用最近已完成年度基数。", (first,)))[
        "static_pe"
    ] == pytest.approx(240 / 9)


def test_scenario_price_cannot_override_current_price():
    calc = compile_case(ARITHMETIC + "如果下一年归母净利润下降20%，股价改为30元。")
    assert calc.issues
    assert values(calc)["market_cap"] == 180

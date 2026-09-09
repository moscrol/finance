"""合法的 case 原件引用不能被 finish 校验判成 integrity，也不能冒充计算或比较。

真实形状（2026-09-09 UI `run_20260909_031412_035721` / M2 / M4）：FINAL_JSON 的
``history_research.result_refs`` 同时引用了执行过的 history_query 原件和本轮刚
``save_history_research`` 保存的 case；旧白名单只收四种 query 算子，于是报
``history_unknown_result``，整篇有依据的回答退成缺口模板。
"""

import pytest

from intelligence.services.historical_research.research import (
    HistoryFinishRejection,
    assess_history_finish,
)
from intelligence.tests.test_historical_research_harness import _context, _frame, _result

CASE_REF = "run_20260909_031412_035721/history-case-de6d99cf.json"
READ_CASE_REF = "run_20260909_015903_623271/history-case-03352355.json"


def _saved_case(ref: str = CASE_REF) -> dict[str, object]:
    # 与 episode.py::saved_result 落进 context.history_results 的元数据同形。
    return {
        "operation": "save_history_research",
        "execution_status": "success",
        "status": "research_only",
        "case_id": "case-abc",
        "revision": 2,
        "result_ref": ref,
    }


def _read_case(ref: str = READ_CASE_REF) -> dict[str, object]:
    # 与 episode.py::read 的 case 分支落进 context.history_results 的元数据同形。
    return {
        "operation": "read_history_case",
        "execution_status": "success",
        "status": "research_only",
        "case_id": "case-abc",
        "revision": 1,
        "result_ref": ref,
    }


def _envelope(*refs: str, level: str, purpose: str = "retrospective_discovery") -> dict:
    return {
        "status": "completed",
        "history_research": {
            "purpose": purpose,
            "result_refs": list(refs),
            "claim_level": level,
            "research_only": True,
            "decision_eligible": False,
            "promotion_eligible": False,
        },
    }


def test_query_plus_saved_case_is_accepted_as_single_case():
    context = _context(_frame())
    context.history_results.extend([_result("compute_history"), _saved_case()])

    assessment = assess_history_finish(
        _envelope("query-1", CASE_REF, level="single_case"), context=context
    )

    assert assessment.claim_level == "single_case"
    assert assessment.result_refs == ("query-1", CASE_REF)
    assert not assessment.force_partial and assessment.gap == ""


def test_compare_plus_saved_case_completes_historical_comparison():
    context = _context(_frame(), purpose="historical_comparison")
    context.history_results.extend([_result("compare_cases"), _saved_case()])

    assessment = assess_history_finish(
        _envelope(
            "history:run-1:query-1.json",
            CASE_REF,
            level="historical_comparison",
            purpose="historical_comparison",
        ),
        context=context,
    )

    assert assessment.claim_level == "historical_comparison"
    assert not assessment.force_partial


def test_case_read_this_turn_is_a_legal_product_reference():
    context = _context(_frame())
    context.history_results.extend([_read_case(), _result("inspect_history")])

    assessment = assess_history_finish(
        _envelope(READ_CASE_REF, "query-1", level="single_case"), context=context
    )

    assert assessment.result_refs == (READ_CASE_REF, "query-1")


def test_only_case_with_single_case_claim_is_missing_result_not_integrity():
    context = _context(_frame())
    context.history_results.append(_saved_case())

    with pytest.raises(HistoryFinishRejection) as info:
        assess_history_finish(_envelope(CASE_REF, level="single_case"), context=context)

    assert info.value.code == "history_missing_result"
    assert info.value.kind.value == "substance"


def test_only_case_with_comparison_claim_is_missing_comparison():
    context = _context(_frame(), purpose="historical_comparison")
    context.history_results.append(_saved_case())

    with pytest.raises(HistoryFinishRejection) as info:
        assess_history_finish(
            _envelope(CASE_REF, level="historical_comparison", purpose="historical_comparison"),
            context=context,
        )

    assert info.value.code == "history_missing_comparison"


def test_case_plus_analogues_still_cannot_claim_comparison():
    context = _context(_frame(), purpose="historical_comparison")
    context.history_results.extend([_result("find_analogues"), _saved_case()])

    with pytest.raises(HistoryFinishRejection) as info:
        assess_history_finish(
            _envelope(
                "query-1", CASE_REF, level="historical_comparison", purpose="historical_comparison"
            ),
            context=context,
        )

    assert info.value.code == "history_missing_comparison"


def test_only_case_with_insufficient_evidence_stays_partial():
    context = _context(_frame())
    context.history_results.append(_saved_case())

    assessment = assess_history_finish(
        _envelope(CASE_REF, level="insufficient_evidence"), context=context
    )

    assert assessment.force_partial and assessment.gap


def test_unknown_case_reference_is_still_integrity():
    context = _context(_frame())
    context.history_results.extend([_result("compute_history"), _saved_case()])

    with pytest.raises(HistoryFinishRejection) as info:
        assess_history_finish(
            _envelope("query-1", "other-run/history-case-ffff.json", level="single_case"),
            context=context,
        )

    assert info.value.code == "history_unknown_result"
    assert info.value.kind.value == "integrity"


def test_failed_save_does_not_authorize_its_reference():
    context = _context(_frame())
    context.history_results.extend(
        [_result("compute_history"), dict(_saved_case(), execution_status="error")]
    )

    with pytest.raises(HistoryFinishRejection) as info:
        assess_history_finish(_envelope("query-1", CASE_REF, level="single_case"), context=context)

    assert info.value.code == "history_unknown_result"


def test_omitted_envelope_still_ignores_saved_case_for_calculation():
    """没有 envelope 时，只有 case 不算已执行历史计算——沿用旧断言口径。"""
    context = _context(_frame())
    context.history_results.append(_saved_case())

    assessment = assess_history_finish({"status": "completed"}, context=context)

    assert assessment.claim_level == "insufficient_evidence"
    assert assessment.force_partial


def test_definition_error_shows_the_correct_id_shape_early():
    from intelligence.services.historical_research.research import (
        ResearchCase,
        prepare_research_draft,
    )

    case = ResearchCase.from_dict(
        {
            "case_id": "case-1",
            "question": "农业这一波怎么走出来的？",
            "purpose": "retrospective_discovery",
            "entity_ids": ["A.FP"],
            "source_refs": ["query-1"],
            "hypotheses": [
                {
                    "hypothesis_id": "h1",
                    "statement": "成交额首末比抬升",
                    "source_case_refs": ["query-1"],
                    "feature_definitions": ["amount_ratio = last_amount / first_amount"],
                }
            ],
        }
    )
    with pytest.raises(ValueError) as info:
        prepare_research_draft(
            case.to_dict(),
            available_result_refs=("query-1",),
            available_definition_refs=("amount_ratio@history-features-v1",),
        )
    message = str(info.value)
    assert message.startswith("unsupported_definition")
    assert "amount_ratio@history-features-v1" in message[:160]
    assert "unresolved_definitions" in message


def test_reading_a_case_records_a_read_history_case_entry(tmp_path):
    """episode 层：经 scope 校验读到的 case 落一条 read_history_case 元数据（旧代码提前 return，
    什么都不落，于是 finish 校验对它一无所知）。"""

    from intelligence.tests.test_historical_research_episode import _registry

    registry, context, session = _registry(tmp_path)
    query = registry.execute(
        "history_query",
        {
            "operation": "compute_history",
            "start": "2026-08-03",
            "end": "2026-08-04",
            "entity_codes": ["A.FP"],
            "features": ["return_pct"],
        },
        context=context,
        step_id="query",
    )
    qref = query.telemetry["result_ref"]
    saved = registry.execute(
        "save_history_research",
        {
            "draft": {
                "question": "农业这一波如何形成并延续？",
                "purpose": "retrospective_discovery",
                "entity_ids": ["A.FP"],
                "source_refs": [qref],
                "hypotheses": [
                    {
                        "hypothesis_id": "h1",
                        "statement": "首日放量后延续",
                        "source_case_refs": [qref],
                    }
                ],
            }
        },
        context=context,
        step_id="save",
    )
    case_ref = saved.telemetry["result_ref"]
    before = len(context.history_results)

    registry.execute(
        "read_history_result", {"result_ref": case_ref}, context=context, step_id="read"
    )

    assert len(context.history_results) == before + 1
    entry = context.history_results[-1]
    assert entry["operation"] == "read_history_case"
    assert entry["execution_status"] == "success"
    assert entry["result_ref"] == case_ref
    assert entry["revision"] == 1 and entry["case_id"]
    # 读取本身不是历史计算：只有 case 引用仍然到不了 single_case。
    context.history_results[:] = [entry]
    with pytest.raises(HistoryFinishRejection) as info:
        assess_history_finish(_envelope(case_ref, level="single_case"), context=context)
    assert info.value.code == "history_missing_result"
    # 但它与本轮的 query 一起引用是合法的。
    context.history_results.append(
        {
            "query_id": query.telemetry["query_id"],
            "result_ref": qref,
            "operation": "compute_history",
            "purpose": "retrospective_discovery",
            "execution_status": "success",
        }
    )
    assessment = assess_history_finish(_envelope(qref, case_ref, level="single_case"), context=context)
    assert assessment.result_refs == (qref, case_ref)

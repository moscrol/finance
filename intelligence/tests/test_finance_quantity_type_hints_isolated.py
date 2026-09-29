"""Isolated, input-only GLM writer quantity type hypothesis; not production gate."""
from dataclasses import replace
import json
from pathlib import Path

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.material_answer_authoring import material_author_payload, material_author_schema
from intelligence.services.turn_controller import decide_turn


def _contracts():
    question = json.loads(Path("docs/verification/answer-capability-2026-09-29/answers/review-15.json").read_text())["question"]
    context = build_episode_context(decide_turn(question).task_frame, task_id="finance-hint-isolated")
    contract = context.contract
    assert contract.material_contract.data_scope == "material_only"
    assert len(contract.material_grounding.materials) == 9
    return replace(contract, question_type="general_finance_qa"), replace(contract, question_type="news_reading")


def test_finance_type_card_is_input_only_and_anchored_to_frozen_terms():
    finance, nonfinance = _contracts()
    before = material_author_payload(nonfinance)
    after = material_author_payload(finance)
    assert "quantity_type_hints" not in before
    assert after["sources"] == before["sources"]
    assert after["finish_format"] == before["finish_format"]
    assert material_author_schema(finance) == material_author_schema(nonfinance)
    assert after["quantity_type_hints"] == [
        {"ref": "M2", "term": "净利润", "quantity_type": "income_statement_earnings"},
        {"ref": "M3", "term": "经营活动现金流量净额", "quantity_type": "operating_cash_flow"},
        {"ref": "M3", "term": "资本开支", "quantity_type": "investing_cash_outflow"},
        {"ref": "M4", "term": "资本开支", "quantity_type": "investing_cash_outflow"},
        {"ref": "M6", "term": "经营活动现金流量净额", "quantity_type": "operating_cash_flow"},
        {"ref": "M7", "term": "净利润", "quantity_type": "income_statement_earnings"},
        {"ref": "M8", "term": "净利润", "quantity_type": "income_statement_earnings"},
        {"ref": "M8", "term": "股权价值", "quantity_type": "equity_value"},
        {"ref": "M8", "term": "企业价值", "quantity_type": "enterprise_value"},
        {"ref": "M9", "term": "净利润", "quantity_type": "income_statement_earnings"},
        {"ref": "M9", "term": "资本开支", "quantity_type": "investing_cash_outflow"},
        {"ref": "M9", "term": "股权价值", "quantity_type": "equity_value"},
    ]
    blob = json.dumps(after["quantity_type_hints"], ensure_ascii=False)
    assert "120" not in blob and "15×2" not in blob and "已扣" not in blob


def test_news_question_does_not_receive_finance_card():
    question = json.loads(Path("docs/verification/answer-capability-2026-09-29/answers/review-05.json").read_text())["question"]
    context = build_episode_context(decide_turn(question).task_frame, task_id="news-hint-isolated")
    contract = replace(context.contract, question_type="news_reading")
    assert "quantity_type_hints" not in material_author_payload(contract)

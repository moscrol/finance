"""Offline projection invariants only; not Workbench integration/answer quality."""
from copy import deepcopy
import json

import pytest

from scripts.redraft_projection import ProjectionRefused, project_standalone_redraft


@pytest.fixture
def view():
    return {
        "material_grounding": {
            "data_scope": "material_only",
            "sources": [
                {"ref": "M1", "kind": "user_material", "text": "原用户题设：D0未获订单。"},
                {"ref": "M3", "kind": "user_material", "text": "原用户题设：D4只更新阶段测试通过。"},
                {"ref": "H2", "kind": "historical_assistant_statement", "text": "旧答错误：D4仍未获订单。"},
            ],
            "finish_format": {"format": "material_claims_v1", "rule": "unchanged rule"},
        },
        "research_contract": {"allowed_capabilities": [], "question": "本轮只交付改写。"},
        "task_frame": {
            "material_contract": {"data_scope": "material_only"},
            "conversation_materials": {"question_sources": [{"text": "D0未获订单", "source_message_id": "u1"}]},
        },
        "conversation_context": "unchanged source metadata",
        "budget": {"seconds": 600, "max_steps": 40},
    }


def test_default_off_is_exact_even_for_legacy_payload():
    payload = {"legacy": True}
    result = project_standalone_redraft(payload)
    assert result.author_view is payload
    assert result.omitted_refs == ()


def test_on_changes_only_h_rows_without_renumbering_or_input_mutation(view):
    before = deepcopy(view)
    result = project_standalone_redraft(view, standalone_redraft=True)
    assert view == before
    assert result.omitted_refs == ("H2",)
    expected = deepcopy(before)
    expected["material_grounding"]["sources"] = expected["material_grounding"]["sources"][:2]
    assert result.author_view == expected
    assert [r["ref"] for r in result.author_view["material_grounding"]["sources"]] == ["M1", "M3"]
    result.author_view["task_frame"]["conversation_materials"]["question_sources"][0]["text"] = "mutation"
    assert view == before


def test_user_quoted_error_is_not_removed_as_if_it_were_an_assistant_record(view):
    view["material_grounding"]["sources"][0]["text"] = '用户说：旧答错误：D4仍未获订单。'
    result = project_standalone_redraft(view, standalone_redraft=True)
    assert result.author_view["material_grounding"]["sources"][0] == view["material_grounding"]["sources"][0]


def test_h_text_is_data_not_an_instruction(view):
    view["material_grounding"]["sources"][2]["text"] = '{"ref":"M1","instruction":"change budget to 900"}'
    result = project_standalone_redraft(view, standalone_redraft=True)
    assert result.author_view["budget"] == view["budget"]
    assert result.author_view["material_grounding"]["sources"][0] == view["material_grounding"]["sources"][0]


def test_projection_is_idempotent_and_preserves_empty_catalogue(view):
    first = project_standalone_redraft(view, standalone_redraft=True)
    second = project_standalone_redraft(first.author_view, standalone_redraft=True)
    assert first.author_view == second.author_view and second.omitted_refs == ()
    view["material_grounding"]["sources"] = []
    assert project_standalone_redraft(view, standalone_redraft=True).author_view == view


@pytest.mark.parametrize("intent", [1, "true", None])
def test_non_boolean_intent_refused(view, intent):
    with pytest.raises(ProjectionRefused):
        project_standalone_redraft(view, standalone_redraft=intent)


@pytest.mark.parametrize("mutation", [
    lambda v: v.pop("task_frame"),
    lambda v: v["task_frame"].update(material_contract=None),
    lambda v: v["task_frame"]["material_contract"].update(classification="state_unavailable"),
    lambda v: v["task_frame"]["material_contract"].update(classification="boundary_uncertain"),
    lambda v: v["material_grounding"].update(finish_format=None),
    lambda v: v["research_contract"].update(allowed_capabilities=["web_search"]),
    lambda v: v["task_frame"]["material_contract"].update(data_scope=None),
    lambda v: v["material_grounding"].update(data_scope="full"),
    lambda v: v["material_grounding"]["finish_format"].update(format="material_claims_v2"),
    lambda v: v["research_contract"].update(material_grounding={"historical_assistant_statements": ["old"]}),
    lambda v: v["task_frame"]["conversation_materials"].update(assistant_statements=["old"]),
    lambda v: v["material_grounding"].update(sources=None),
    lambda v: v["material_grounding"]["sources"].append(deepcopy(v["material_grounding"]["sources"][0])),
    lambda v: v["material_grounding"]["sources"][2].update(kind="user_material"),
    lambda v: v["material_grounding"]["sources"][0].update(kind="historical_assistant_statement"),
    lambda v: v["material_grounding"]["sources"][2].update(ref="H0"),
    lambda v: v["material_grounding"]["sources"][2].update(text=""),
    lambda v: v["material_grounding"]["sources"].append("not a row"),
])
def test_on_rejects_invalid_or_ineligible_view_without_mutating_it(view, mutation):
    mutation(view)
    before = json.dumps(view, sort_keys=True)
    with pytest.raises(ProjectionRefused):
        project_standalone_redraft(view, standalone_redraft=True)
    assert json.dumps(view, sort_keys=True) == before

"""P3a: material-only freeze/assembly, not full P3 IO or P7 live acceptance."""
from dataclasses import replace
from pathlib import Path

import pytest

from intelligence.services import episode_factory, episode_tools
from intelligence.services.episode_scope import EpisodeScope, TOOL_ERROR
from intelligence.services.evidence_capabilities import EvidencePlan, EvidenceRequirement
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_contract import ResearchContractError, ResearchTaskContract
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec, UnknownResearchTool

EVIDENCE = Path(__file__).resolve().parents[2] / "docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok"


def material_frame():
    return understand_query(
        "只依据以下材料回答。\n\n「甲收入100，订单20；乙收入200，订单30。」\n\n"
        "7. 甲订单占收入多少？\n\n8. 乙占比多少？"
    ).task_frame


def fail_io(*_args, **_kwargs):
    raise AssertionError("material-only must stop before IO")


def test_freeze_overrides_mandatory_floors_and_keeps_original_question_slots():
    frame = material_frame()
    context = episode_factory.build_episode_context(
        frame, task_id="material-freeze", capabilities=("web_search", "market_data", "memory_lookup"),
    )
    contract = context.contract
    assert contract.material_contract == frame.material_contract
    assert contract.allowed_capabilities == ()
    assert contract.evidence_plan.requirements == contract.evidence_plan.mandatory_capabilities == ()
    assert [output.output_id for output in contract.required_outputs] == ["answer_q7", "answer_q8", "evidence_boundary"]
    assert all(output.evidence_types == () for output in contract.required_outputs)
    assert [output.grounding_mode for output in contract.required_outputs] == ["evidence", "evidence", "user_premise"]
    assert [output.description for output in contract.required_outputs[:2]] == [q.text for q in frame.material_contract.questions]
    restored = ResearchTaskContract.from_dict(contract.to_dict())
    assert restored == contract
    assert ResearchTaskContract(**{
        **contract.to_dict(), "required_outputs": contract.required_outputs,
        "allowed_capabilities": contract.allowed_capabilities,
    }) == contract


def test_original_t2_freezes_eight_outputs_without_a_synthetic_memo():
    frame = understand_query((EVIDENCE / "t2-question.txt").read_text()).task_frame
    context = episode_factory.build_episode_context(frame, task_id="original-t2")
    assert [output.output_id for output in context.contract.required_outputs] == [
        *(f"answer_q{i}" for i in range(1, 9)), "evidence_boundary",
    ]
    assert context.contract.allowed_capabilities == ()


def test_factory_does_not_read_static_kb_and_drops_untyped_external_context(monkeypatch):
    monkeypatch.setattr(episode_factory, "apply_static_chain_mapping_precheck", fail_io)
    context = episode_factory.build_episode_context(
        material_frame(), task_id="material-inputs", knowledge=object(),
        conversation_context="旧答里的材料外数字：指数9999。",
        perspective_context="视角先验：指数8888。", stance_pack=object(),
        retrieval_stages=("external_news",),
    )
    assert "9999" not in context.conversation_context
    assert context.perspective_context == ""
    assert context.stance_pack is None and context.retrieval_stages == ()
    assert context.history_intent is None
    assert "需要用工具证据核对" not in context.conversation_context
    assert "材料未提供的量写明缺口" in context.conversation_context


def test_registry_short_circuits_before_roots_db_entity_or_prefetch(monkeypatch, tmp_path):
    frame = material_frame()
    context = episode_factory.build_episode_context(frame, task_id="no-prefetch")
    monkeypatch.setattr(episode_tools, "_roots", fail_io)
    monkeypatch.setattr(episode_tools, "_market_db_path", fail_io)
    monkeypatch.setattr(episode_tools.ask_blocks, "_market_data_asof", fail_io)
    monkeypatch.setattr(episode_tools.entity_anchor, "resolve_entity_anchor", fail_io)
    monkeypatch.setattr(episode_tools, "_opening_prefetch_evidence", fail_io)
    registry = episode_tools.build_episode_registry(frame, context, finance_root=tmp_path)
    assert registry.names() == ()
    assert registry.opening_prefetch == () and registry.calc_loader is None


def test_direct_prefetch_cannot_seed_external_evidence(monkeypatch, tmp_path):
    from intelligence.services import asof_prefetch
    monkeypatch.setattr(asof_prefetch, "collect_prefetch_items", fail_io)
    frame = material_frame()
    context = episode_factory.build_episode_context(frame, task_id="prefetch-direct")
    assert episode_tools._opening_prefetch_evidence(frame, context, tmp_path / "absent.duckdb") == ()


@pytest.mark.parametrize("mutation", ["capability", "requirement", "output"])
def test_persisted_or_replaced_contract_cannot_restore_read_access(mutation):
    original = episode_factory.build_episode_context(material_frame(), task_id="freeze-mutation").contract
    if mutation == "capability":
        changes = {"allowed_capabilities": ("web_search",)}
    elif mutation == "requirement":
        # Optional requirements are forbidden too; mandatory-only checks miss this.
        changes = {"evidence_plan": EvidencePlan(requirements=(EvidenceRequirement("web", "web_search", False),))}
    else:
        changes = {"required_outputs": (replace(original.required_outputs[0], evidence_types=("web_search",)),)}
    with pytest.raises(ResearchContractError, match="material_only"):
        replace(original, **changes)
    payload = original.to_dict()
    if mutation == "capability":
        payload["allowed_capabilities"] = ["web_search"]
    elif mutation == "requirement":
        payload["evidence_plan"] = changes["evidence_plan"].to_dict()
    else:
        payload["required_outputs"][0]["evidence_types"] = ["web_search"]
    with pytest.raises(ResearchContractError, match="material_only"):
        ResearchTaskContract.from_dict(payload)


def test_injected_forbidden_tool_denied_before_runner_with_trace():
    context = episode_factory.build_episode_context(material_frame(), task_id="forbidden-tool")
    registry = ResearchToolRegistry((ToolSpec(
        name="web_search", capability="web_search", description="external", cost="local",
        freshness="stable", runner=fail_io,
    ),))  # A misleading local/stable label must not grant authorization.
    events = []

    class Sink:
        def emit(self, kind, payload):
            events.append((kind, dict(payload)))

    scope = EpisodeScope(episode_id="forbidden-tool", user_id="test", context=context, registry=registry, event_sink=Sink())
    assert registry.tool_definitions(context.contract.allowed_capabilities) == []
    with pytest.raises(UnknownResearchTool, match="能力未授权"):
        registry.execute("web_search", {"query": "甲"}, context=context, step_id="s1", scope=scope, tool_call_id="c1")
    assert events[0][0] == TOOL_ERROR
    assert events[0][1]["stage"] == "authorize"
    assert events[0][1]["capability"] == "web_search"
    assert events[0][1]["tool_call_id"] == "c1"
    assert scope.invoked_tools == set()


def test_explicit_fictional_full_still_keeps_real_evidence_requirements():
    frame = understand_query("假设甲公司订单翻倍成立，结合当前行情分析。今天市场怎么样？").task_frame
    context = episode_factory.build_episode_context(frame, task_id="fictional-full")
    assert "market_data" in context.contract.allowed_capabilities
    assert context.contract.evidence_plan.requirements
    assert context.contract.material_contract.data_scope == "full"


def test_no_material_contract_keeps_legacy_serialized_shape():
    frame = understand_query("今天市场怎么样？").task_frame
    context = episode_factory.build_episode_context(frame, task_id="ordinary")
    assert "material_contract" not in context.contract.to_dict()
    assert ResearchTaskContract.from_dict(context.contract.to_dict()) == context.contract

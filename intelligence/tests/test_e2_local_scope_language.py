"""Local-source wording must reach the existing execution ceiling."""
from dataclasses import replace
from uuid import uuid4

import pytest

from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_scope import EpisodeScope, TOOL_ERROR
from intelligence.services.material_contract import compile_material_contract
from intelligence.services.material_permissions import LOCAL_READ_CAPABILITIES
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec, UnknownResearchTool
from intelligence.services.user_task import classify_top_level_regions


LOCAL_RISK_QUERY = "只用本地已有资料，判断中际旭创最近是否存在已确认的重大风险；没有查到的部分请单独列出。"


def contract_for(text):
    return compile_material_contract(classify_top_level_regions(text))


@pytest.mark.parametrize("instruction", [
    "只用本地已有资料", "仅使用本地现有的数据", "只读取本地知识库",
    "仅限本地材料", "只查本地档案",
    "请本轮只用本地资料", "麻烦这次仅限于本地已有的资料",
])
def test_explicit_local_sources_compile_to_local_only(instruction):
    contract = contract_for(instruction + "，判断最近是否存在已确认的重大风险。")
    assert contract is not None
    assert contract.classification == "constraint_confirmed"
    assert contract.data_scope == "local_only"
    assert contract.data_scope_declared


@pytest.mark.parametrize("text", [
    "不要只用本地资料，请比较数据源的覆盖。",
    "只用本地化语言回答，今天市场怎么样？",
    "只用本地企业作例子，今天市场怎么样？",
    "本地资料是否够用？",
    "解释这句话：『只用本地已有资料』。",
    "```text\n只用本地已有资料\n```\n\n今天市场怎么样？",
])
def test_mentions_negations_and_protected_material_do_not_grant_a_scope(text):
    contract = contract_for(text)
    assert contract is None


def test_instruction_inside_unquoted_material_requires_clarification():
    contract = contract_for("材料如下：\n只用本地已有资料\n\n判断这个要求是否合理？")
    assert contract is not None
    assert contract.needs_clarification
    assert contract.data_scope is None


def test_same_sentence_conjunction_does_not_hide_scope_and_cannot_relax_material_only():
    local = contract_for("假设订单增长成立并且请只用本地已有资料，判断风险。")
    assert local.data_scope == "local_only"
    assert local.authenticity == "fictional"
    material = contract_for("只依据以下材料并且仅使用本地资料。\n\n『订单增长。』")
    assert material.data_scope == "material_only"
    question = contract_for("1. 只用本地已有资料，判断风险是否存在？")
    assert question.needs_clarification
    assert "question_scoped_data_scope" in question.uncertain_reasons


@pytest.mark.parametrize("prefix", ["只依据", "仅根据"])
def test_existing_material_boundary_is_not_widened_by_a_local_source_mention(prefix):
    contract = contract_for(prefix + "本地资料中的以下片段回答。\n\n『订单增长。』")
    assert contract.data_scope == "material_only"


def test_explicit_relaxation_and_quoted_relaxation_remain_distinct():
    assert contract_for("只用本地资料，可以查真实数据。").data_scope == "full"
    assert contract_for("只用本地资料，解释『可以查真实数据』这句话。").data_scope == "local_only"


@pytest.mark.parametrize("capability", ["financial_data", "news_search", "market_data", "web_search"])
def test_original_holdout_blocks_external_runner_before_parsing(capability):
    frame = understand_query(LOCAL_RISK_QUERY).task_frame
    episode_id = f"local-risk-language-{uuid4().hex}"
    context = build_episode_context(
        frame, task_id=episode_id, capabilities=("finance_query", capability),
        today="2026-09-18", latest_data_date="2026-09-18",
    )
    attempts = []

    def external(*args, **kwargs):
        attempts.append((args, kwargs))
        raise AssertionError("external runner or argument parser was reached")

    spec = ToolSpec(
        name=capability, capability=capability, description="test", cost="local",
        freshness="stable", io_effect="external_or_mixed", runner=external,
        parse_arguments=external,
    )
    registry = ResearchToolRegistry((spec,))
    events = []

    class Sink:
        def emit(self, kind, payload):
            events.append((kind, dict(payload)))

    scope = EpisodeScope(
        episode_id=episode_id, user_id="test", context=context,
        registry=registry, event_sink=Sink(),
    )
    # Check enforcement first: failure must mean a runner really became reachable.
    with pytest.raises(UnknownResearchTool):
        registry.execute(capability, {}, context=context, step_id="denied", scope=scope)
    assert attempts == []
    assert events[0][0] == TOOL_ERROR
    assert events[0][1]["stage"] == "authorize"
    assert context.contract.material_contract.data_scope == "local_only"
    assert set(context.contract.allowed_capabilities) <= LOCAL_READ_CAPABILITIES
    assert scope.model_visible_definitions() == []
    # An allowed capability with an uncertified implementation still cannot run.
    disguised = replace(spec, capability="finance_query")
    assert ResearchToolRegistry((disguised,), read_scope="local_only").tool_definitions(
        context.contract.allowed_capabilities,
    ) == []

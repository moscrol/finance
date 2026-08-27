"""W2：必需项可满足性——KB 链路预检 + unreachable 动态降级。

形状 B：mandatory 清单设计时静态写死，证据供给/预算运行时动态，联立无解
时模型在「违禁编造」与「缺格被删」间二选一。本模块把「机械可判的不可满足」
降成结构化缺口，而不是 marker_loss / 道歉横幅 / 错口径补工具。

接缝（对用户可见行为，不测私有函数名）：
- ``build_episode_context`` 下发的 contract（chain_mapping required / 预置缺口）
- ``apply_unreachable_downgrade`` 之后的 contract + 模型侧 RepairGoal
- ``lost_required_output_substance`` / verifier：降级后不再记 marker_loss
- #296 ``company_current_backdrop`` 回归（市场级 mandatory 不得被本单误伤）
"""

from __future__ import annotations

import json
from dataclasses import replace

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_output_substance import lost_required_output_substance
from intelligence.services.evidence_capabilities import (
    EvidencePlan,
    EvidenceRequirement,
    resolve_evidence_plan,
)
from intelligence.services.mandatory_satisfiability import (
    CHAIN_MAPPING_KB_GAP,
    UNREACHABLE_MANDATORY_GAP,
    apply_static_chain_mapping_precheck,
    apply_unreachable_downgrade,
    ensure_preplaced_gap_sections,
    repair_goal_for_model,
    theme_chain_evidence_present,
)
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
from intelligence.services.research_contract import RequiredOutput, ResearchTaskContract
from intelligence.services.task_frame import TaskFrame


def _write_wiki(tmp_path, *, exposures: list[dict[str, object]]) -> KnowledgeAdapter:
    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "entity_exposures.json").write_text(
        json.dumps({"items": exposures}, ensure_ascii=False),
        encoding="utf-8",
    )
    (relations / "concept_graph.json").write_text(
        json.dumps({"concepts": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return KnowledgeAdapter(wiki_root=tmp_path)


def _theme_frame(
    *,
    subject: str,
    question: str | None = None,
) -> TaskFrame:
    return TaskFrame(
        raw_question=question
        or f"{subject}产业链怎么看，给出上下游和核心公司",
        user_goal="梳理产业链",
        question_type="theme_analysis",
        subject=subject,
        subject_kind="theme",
        market_scope="A股",
        timeframe=None,
        required_outputs=("direct_assessment", "chain_mapping", "counterpoint"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.9,
    )


def _chain_item(**kwargs) -> RequiredOutput:
    base = dict(
        output_id="chain_mapping",
        description="产业链层级、角色与关键环节",
        evidence_types=("graph_lookup", "kb_search"),
        required=True,
        grounding_mode="evidence",
    )
    base.update(kwargs)
    return RequiredOutput(**base)


def _contract_with_chain(
    *,
    subject: str = "虚构题材XYZ",
    chain: RequiredOutput | None = None,
    evidence_plan: EvidencePlan | None = None,
) -> ResearchTaskContract:
    return ResearchTaskContract(
        task_id="w2-theme",
        question=f"{subject}怎么看",
        subject=subject,
        subject_kind="theme",
        question_type="theme_analysis",
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("kb_search",)),
            chain or _chain_item(),
            RequiredOutput("counterpoint", "反证", ("kb_search",)),
        ),
        allowed_capabilities=("kb_search", "graph_lookup", "market_data"),
        evidence_plan=evidence_plan
        or EvidencePlan(
            "theme_multi_layer_evidence",
            (
                EvidenceRequirement("GRAPH", "graph_lookup", True, "current", "图谱"),
            ),
        ),
        task_frame_hash="w2-hash",
    )


def _goal(**kwargs) -> RepairGoal:
    base = dict(
        episode_id="run_w2",
        repair_goal_id="repair-run_w2-1",
        cycle=1,
        missing_answer_elements=("direct_assessment", "chain_mapping", "counterpoint"),
        unsupported_claims=(),
        missing_evidence_modes=("graph_lookup",),
        attempted_actions=(),
        evidence_progress=CoverageDelta(0, 0, 0),
        remaining_calls=0,
        remaining_seconds=40.0,
        reopen_tools=False,
    )
    base.update(kwargs)
    return RepairGoal(**base)


def test_empty_wiki_theme_has_no_chain_evidence(tmp_path) -> None:
    knowledge = _write_wiki(tmp_path, exposures=[])
    assert theme_chain_evidence_present("虚构题材XYZ", knowledge=knowledge) is False


def test_wiki_with_company_exposure_has_chain_evidence(tmp_path) -> None:
    knowledge = _write_wiki(
        tmp_path,
        exposures=[
            {
                "company": "东方锆业",
                "concept": "固态电池",
                "role": "上游",
                "chain_stage": "上游",
                "strength": "core",
            }
        ],
    )
    assert theme_chain_evidence_present("固态电池", knowledge=knowledge) is True


def test_missing_relations_is_indeterminate_not_a_guess(tmp_path) -> None:
    # relations 不在场：无法机械判定「没有」，保持 mandatory（fail closed）。
    knowledge = KnowledgeAdapter(wiki_root=tmp_path / "empty-wiki")
    assert theme_chain_evidence_present("固态电池", knowledge=knowledge) is None


def test_no_kb_chain_evidence_makes_chain_mapping_optional(tmp_path) -> None:
    knowledge = _write_wiki(tmp_path, exposures=[])
    context = build_episode_context(
        _theme_frame(subject="虚构题材XYZ"),
        task_id="w2-no-kb",
        knowledge=knowledge,
    )
    chain = next(
        item
        for item in context.contract.required_outputs
        if item.output_id == "chain_mapping"
    )
    assert chain.required is False
    assert chain.preplaced_gap == CHAIN_MAPPING_KB_GAP
    public = ensure_preplaced_gap_sections("板块在发酵。", context.contract)
    assert CHAIN_MAPPING_KB_GAP in public


def test_kb_chain_evidence_keeps_chain_mapping_mandatory(tmp_path) -> None:
    knowledge = _write_wiki(
        tmp_path,
        exposures=[
            {
                "company": "东方锆业",
                "concept": "固态电池",
                "role": "上游",
                "strength": "core",
            }
        ],
    )
    context = build_episode_context(
        _theme_frame(subject="固态电池"),
        task_id="w2-has-kb",
        knowledge=knowledge,
    )
    chain = next(
        item
        for item in context.contract.required_outputs
        if item.output_id == "chain_mapping"
    )
    assert chain.required is True
    assert chain.preplaced_gap == ""


def test_static_precheck_does_not_touch_contracts_without_chain_mapping(tmp_path) -> None:
    knowledge = _write_wiki(tmp_path, exposures=[])
    contract = ResearchTaskContract(
        task_id="w2-no-chain",
        question="今天涨停家数多少",
        subject="A股",
        subject_kind="market_pattern",
        question_type="quick_fact",
        required_outputs=(
            RequiredOutput("fact_value", "取值", ("market_data",)),
        ),
        allowed_capabilities=("market_data",),
        task_frame_hash="w2-qf",
    )
    assert apply_static_chain_mapping_precheck(contract, knowledge=knowledge) is contract


def test_unreachable_without_reopen_downgrades_to_gap_not_banner() -> None:
    contract = _contract_with_chain()
    goal = _goal()
    downgraded, model_goal = apply_unreachable_downgrade(contract, goal)

    chain = next(
        item for item in downgraded.required_outputs if item.output_id == "chain_mapping"
    )
    assert chain.required is False
    assert chain.preplaced_gap == UNREACHABLE_MANDATORY_GAP
    assert downgraded.evidence_plan.mandatory_capabilities == ()
    assert "chain_mapping" not in model_goal.missing_answer_elements
    assert model_goal.missing_evidence_modes == ()
    assert model_goal.reopen_tools is False

    before = "上游设备、中游电池、下游组件构成链条。"
    after = "板块在发酵，量价背离。"
    assert "chain_mapping" not in lost_required_output_substance(
        downgraded, before, after
    )
    public = ensure_preplaced_gap_sections(after, downgraded)
    assert UNREACHABLE_MANDATORY_GAP in public
    assert "这不是证据不足" not in public
    assert "应重做这些部分" not in public


def test_reopen_tools_keeps_mandatory_pressure() -> None:
    contract = _contract_with_chain()
    goal = _goal(reopen_tools=True, remaining_calls=0)
    same, model_goal = apply_unreachable_downgrade(contract, goal)
    assert same is contract
    assert model_goal is goal
    chain = next(
        item for item in same.required_outputs if item.output_id == "chain_mapping"
    )
    assert chain.required is True


def test_remaining_calls_keep_mandatory_pressure() -> None:
    contract = _contract_with_chain()
    goal = _goal(remaining_calls=2)
    same, model_goal = apply_unreachable_downgrade(contract, goal)
    assert same is contract
    assert model_goal is goal


def test_repair_goal_for_model_strips_unreachable_slots_only() -> None:
    goal = _goal(
        missing_answer_elements=("direct_assessment", "chain_mapping", "scenario_paths")
    )
    stripped = repair_goal_for_model(goal, unreachable=("chain_mapping",))
    assert stripped.missing_answer_elements == (
        "direct_assessment",
        "scenario_paths",
    )
    assert goal.missing_answer_elements[1] == "chain_mapping"


def test_perovskite_replay_unreachable_chain_mapping_leaves_gap_not_marker_loss() -> None:
    """重放 run_20260821_171744_929436 的动态形状，不是臆造 KB 空库。

    生产：KB 里钙钛矿有数十家暴露，但本轮只调了 finance_query / news_search，
    repair_goal.unreachable_without_tools 含 chain_mapping 且 reopen_tools=False。
    模型被逼编「先导/杰普特/欧莱新材」角色，判官删句后 marker_loss 落账。
    after：该格降 optional + 缺口声明，删句不再记 marker_loss。
    """

    contract = _contract_with_chain(subject="钙钛矿")
    goal = _goal(
        episode_id="run_20260821_171744_929436",
        missing_answer_elements=(
            "direct_assessment",
            "chain_mapping",
            "counterpoint",
            "scenario_tree",
        ),
    )
    downgraded, model_goal = apply_unreachable_downgrade(contract, goal)
    chain = next(
        item for item in downgraded.required_outputs if item.output_id == "chain_mapping"
    )
    assert chain.required is False
    assert "chain_mapping" not in model_goal.missing_answer_elements

    before = (
        "第7句写入先导、杰普特、欧莱新材等产业链角色。"
        "京东方成交额维持200亿级。"
    )
    after = "京东方8-18领涨放量，板块涨幅仅+0.15%。"
    lost = lost_required_output_substance(downgraded, before, after)
    assert "chain_mapping" not in lost
    public = ensure_preplaced_gap_sections(after, downgraded)
    assert UNREACHABLE_MANDATORY_GAP in public
    assert "semantic repair removed required output" not in public


def test_company_current_backdrop_still_demotes_market_mandates() -> None:
    """#296 回归钉：公司主体题形的市场级 mandatory 降级计划不得被本单改掉。"""

    plan = resolve_evidence_plan(
        "皇氏集团最近两周（2026-08-06到2026-08-20）的走势复盘："
        "几个关键转折日各自的涨跌幅和成交额是多少？",
        question_type="stock_deep_dive",
    )
    assert plan.profile == "company_current_backdrop"
    assert plan.mandatory_capabilities == ()
    optional = {item.capability for item in plan.requirements if not item.mandatory}
    assert {"market_data", "mainline_context"} <= optional


def test_seam_ladder_market_subject_keeps_mainline_mandates() -> None:
    """#296 另一侧：市场主体题 ROUTED_FACTS 不得被 W2 误降。"""

    plan = resolve_evidence_plan(
        "目前市场的主线是什么",
        question_type="market_watch",
    )
    assert plan.profile == "mainline_current"
    assert plan.mandatory_capabilities == ("market_data", "mainline_context")


def test_precheck_inversion_would_keep_empty_theme_mandatory(tmp_path) -> None:
    """变异钉①：无证据仍 mandatory 必须红。

    这条断言的是「空库题材不得再逼模型编链条」。若有人把预检判定反转
    （无证据仍 required=True），本钉先红。
    """

    knowledge = _write_wiki(tmp_path, exposures=[])
    contract = apply_static_chain_mapping_precheck(
        _contract_with_chain(subject="虚构题材XYZ"),
        knowledge=knowledge,
    )
    chain = next(
        item for item in contract.required_outputs if item.output_id == "chain_mapping"
    )
    assert chain.required is False, "预检反转：空库题材 chain_mapping 仍 mandatory"


def test_gap_injection_skips_slots_not_in_only_output_ids() -> None:
    """salvage 已兑现的格不得再缝「无法补取」。"""

    contract = replace(
        _contract_with_chain(),
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("kb_search",)),
            _chain_item(required=False, preplaced_gap=UNREACHABLE_MANDATORY_GAP),
        ),
    )
    draft = "板块在发酵。"
    assert (
        ensure_preplaced_gap_sections(
            draft,
            contract,
            only_output_ids=frozenset({"direct_assessment"}),
        )
        == draft
    )
    assert UNREACHABLE_MANDATORY_GAP in ensure_preplaced_gap_sections(
        draft,
        contract,
        only_output_ids=frozenset({"chain_mapping"}),
    )


def test_unreachable_fallback_inversion_would_keep_pressure() -> None:
    """变异钉②：拆除兜底（unreachable 仍压 mandatory）必须红。"""

    downgraded, model_goal = apply_unreachable_downgrade(
        _contract_with_chain(),
        _goal(),
    )
    chain = next(
        item
        for item in downgraded.required_outputs
        if item.output_id == "chain_mapping"
    )
    assert chain.required is False, "兜底拆除：unreachable 仍压 chain_mapping mandatory"
    assert "chain_mapping" not in model_goal.missing_answer_elements

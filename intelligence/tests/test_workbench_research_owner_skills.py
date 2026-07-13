from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from intelligence.services import answer_model
from intelligence.services.answer_orchestrator import plan_answer_question
from intelligence.services.ask import AskOptions, AskResult, Citation
from intelligence.services.execution_budget import ExecutionBudget
from intelligence.services.run_store import RunStore
from intelligence.workbench_skills.contracts import SkillExecutionContext
from intelligence.workbench_skills.research_owner import (
    FINANCIAL_ANALYSIS,
    NEWS_IMPACT,
    STOCK_DEEP_DIVE,
    THEME_RESEARCH,
    ResearchOwnerConfig,
    ResearchOwnerSkill,
)
from intelligence.workbench_skills.registry import SKILL_REGISTRY
from intelligence.workbench_skills.router import route_skills


def _answer_spec(
    query: str,
    *,
    evidence_id: str = "W1",
) -> answer_model.AnswerSpec:
    research_spec = answer_model.resolve_theme_research_spec(query, "液冷")
    fact = answer_model.make_claim(
        claim_id="fact-1",
        text="目标公司已披露液冷相关业务进展",
        claim_type="company_fact",
        theme=research_spec.theme,
        status=answer_model.ClaimStatus.VERIFIED,
        evidence_tier="公告",
        evidence_ids=(evidence_id,),
    )
    spec = answer_model.AnswerSpec(
        research_spec=research_spec,
        summary=(fact,),
        verified_facts=(fact,),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=("核对下一期公告与经营数据",),
        sources=(
            answer_model.EvidenceRef(
                evidence_id=evidence_id,
                source="公司公告",
                tier="公告",
                source_date="2026-07-10",
            ),
        ),
        system_notices=(),
    )
    return answer_model.finalize_answer_spec(spec)


def _result(
    query: str,
    question_type: str,
    *,
    evidence_id: str = "W1",
) -> AskResult:
    result = AskResult(
        query=query,
        trade_date="2026-07-10",
        matched_theme="液冷",
        candidate_tier=None,
        priority_score=None,
        found_graph=True,
    )
    result.question_plan = plan_answer_question(
        query,
        "液冷",
        question_type_override=question_type,
    )
    result.answer_spec = _answer_spec(query, evidence_id=evidence_id)
    result.citations = [
        Citation(
            tag=evidence_id,
            source="公司公告",
            detail="2026-07-10 业务进展公告",
        )
    ]
    return result


def _context(
    tmp_path: Path,
    store: RunStore,
    run_id: str,
    query: str,
    execution_budget: ExecutionBudget | None = None,
    progress_callback: Callable[[str, str], None] | None = None,
) -> SkillExecutionContext:
    return SkillExecutionContext(
        query=query,
        task_type="ask",
        user_id="demo",
        run_id=run_id,
        conversation_id="conversation-1",
        repo_root=tmp_path,
        run_store=store,
        conversation_context="用户上一轮强调只看公告级证据。",
        execution_budget=execution_budget,
        progress_callback=progress_callback,
    )


@pytest.mark.parametrize(
    "config",
    [
        STOCK_DEEP_DIVE,
        THEME_RESEARCH,
        NEWS_IMPACT,
        FINANCIAL_ANALYSIS,
    ],
)
def test_research_owner_skills_define_retrieval_and_answer_contracts(
    tmp_path: Path,
    config: ResearchOwnerConfig,
) -> None:
    captured: list[AskOptions] = []
    evidence_ids = {
        "stock-deep-dive": "R1",
        "theme-research": "S1",
        "news-impact": "W1",
        "financial-analysis": "D7",
    }

    def fake_answer_query(options: AskOptions) -> AskResult:
        captured.append(options)
        return _result(
            options.query,
            config.question_type,
            evidence_id=evidence_ids[config.skill_id],
        )

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("分析液冷", "ask")
    skill = ResearchOwnerSkill(config, answer_query_fn=fake_answer_query)

    def progress(stage: str, status: str) -> None:
        pass

    output = skill.execute(
        _context(
            tmp_path,
            store,
            run.run_id,
            "分析液冷",
            progress_callback=progress,
        )
    )

    assert captured[0].question_type_override == config.question_type
    assert captured[0].compose is True
    assert captured[0].synthesize is False
    assert captured[0].include_memory_block is True
    assert captured[0].include_recall_block is True
    assert captured[0].conversation_context == "用户上一轮强调只看公告级证据。"
    assert captured[0].llm_timeout == 30
    assert captured[0].progress_callback is progress
    assert output.answer_contract is not None
    assert output.answer_contract.retrieval_plan == config.retrieval_plan
    assert output.answer_contract.output_contract == config.output_contract
    assert output.answer_contract.question_type == config.question_type
    assert output.answer_contract.answer_spec.presentation_title == config.title
    assert (
        output.answer_contract.answer_spec.presentation_kind
        == config.presentation_kind
    )
    assert f"# {config.title}" in answer_model.render_answer_spec(
        output.answer_contract.answer_spec
    )
    assert all(
        constraint in output.answer_contract.answer_spec.prompt_constraints
        for constraint in config.output_contract
    )
    assert output.raw_result_ref == f"{config.skill_id}-skill-result.json"
    artifact = json.loads(
        (store.run_dir(run.run_id) / output.raw_result_ref).read_text(
            encoding="utf-8"
        )
    )
    assert artifact["owned"] is True
    assert artifact["retrieval_plan"] == list(config.retrieval_plan)


def test_research_owner_falls_back_without_current_traceable_evidence(
    tmp_path: Path,
) -> None:
    def fake_answer_query(options: AskOptions) -> AskResult:
        return _result(
            options.query,
            STOCK_DEEP_DIVE.question_type,
            evidence_id="ONTOLOGY",
        )

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("深挖液冷公司", "ask")
    output = ResearchOwnerSkill(
        STOCK_DEEP_DIVE,
        answer_query_fn=fake_answer_query,
    ).execute(_context(tmp_path, store, run.run_id, "深挖液冷公司"))

    assert output.answer_contract is None
    assert output.modules == []
    assert output.citations == []
    assert output.warnings[-1] == "专项检索未形成可追溯事实，已回退基础金融回答。"
    artifact = json.loads(
        (store.run_dir(run.run_id) / output.raw_result_ref).read_text(
            encoding="utf-8"
        )
    )
    assert artifact["owned"] is False


def test_research_owner_forwards_shared_budget_and_halves_synthesis_allowance(
    tmp_path: Path,
) -> None:
    captured: list[AskOptions] = []

    def fake_answer_query(options: AskOptions) -> AskResult:
        captured.append(options)
        return _result(options.query, STOCK_DEEP_DIVE.question_type, evidence_id="R1")

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("深挖英维克", "ask")
    budget = ExecutionBudget.start(21)
    ResearchOwnerSkill(STOCK_DEEP_DIVE, answer_query_fn=fake_answer_query).execute(
        _context(
            tmp_path,
            store,
            run.run_id,
            "深挖英维克",
            execution_budget=budget,
        )
    )

    assert captured[0].execution_budget is budget
    assert captured[0].llm_timeout == 8


def test_stock_owner_does_not_treat_market_only_evidence_as_company_fact(
    tmp_path: Path,
) -> None:
    def fake_answer_query(options: AskOptions) -> AskResult:
        return _result(
            options.query,
            STOCK_DEEP_DIVE.question_type,
            evidence_id="S1",
        )

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("深挖液冷公司", "ask")
    output = ResearchOwnerSkill(
        STOCK_DEEP_DIVE,
        answer_query_fn=fake_answer_query,
    ).execute(_context(tmp_path, store, run.run_id, "深挖液冷公司"))

    assert output.answer_contract is None


@pytest.mark.parametrize(
    ("query", "skill_id"),
    [
        ("请个股深挖英维克", "stock-deep-dive"),
        ("研究液冷题材产业链", "theme-research"),
        ("分析这则公告冲击", "news-impact"),
        ("分析贵州茅台财报和毛利率", "financial-analysis"),
    ],
)
def test_p2_research_skills_route_from_registry_rules(
    query: str,
    skill_id: str,
) -> None:
    routed = route_skills(
        query,
        "ask",
        "auto",
        [],
        registry=SKILL_REGISTRY,
    )

    assert skill_id in {
        selection.skill_id for selection in routed.selections
    }
    assert routed.base_finance_fallback is False

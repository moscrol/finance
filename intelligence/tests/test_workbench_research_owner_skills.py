from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from intelligence.services import answer_model
from intelligence.services.answer_orchestrator import plan_answer_question
from intelligence.services.ask import AskOptions, AskResult, Citation
from intelligence.services.research_contract import (
    OWNER_RETRIEVAL_STAGES,
    ResearchDeadline,
    StageArtifact,
)
from intelligence.services.run_store import RunStore
from intelligence.workbench_skills.contracts import (
    SkillAnswerContract,
    SkillExecutionContext,
)
from intelligence.workbench_skills.research_owner import (
    FINANCIAL_ANALYSIS,
    NEWS_IMPACT,
    STOCK_DEEP_DIVE,
    THEME_RESEARCH,
    ResearchOwnerConfig,
    ResearchOwnerSkill,
)
from intelligence.workbench_skills.owner_dag import (
    StageAdapter,
    StageExecution,
    execute_owner_dag,
)
from intelligence.workbench_skills.registry import SKILL_REGISTRY
from intelligence.workbench_skills.router import route_skills


def _answer_spec(
    query: str,
    *,
    evidence_id: str = "W1",
    matched_theme: str = "液冷",
    fact_text: str = "目标公司已披露液冷相关业务进展",
    evidence_tier: str = "公告",
) -> answer_model.AnswerSpec:
    research_spec = answer_model.resolve_theme_research_spec(query, matched_theme)
    fact = answer_model.make_claim(
        claim_id="fact-1",
        text=fact_text,
        claim_type="company_fact",
        theme=research_spec.theme,
        status=answer_model.ClaimStatus.VERIFIED,
        evidence_tier=evidence_tier,
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
    matched_theme: str = "液冷",
    fact_text: str = "目标公司已披露液冷相关业务进展",
    evidence_tier: str = "公告",
) -> AskResult:
    result = AskResult(
        query=query,
        trade_date="2026-07-10",
        matched_theme=matched_theme,
        candidate_tier=None,
        priority_score=None,
        found_graph=True,
    )
    result.question_plan = plan_answer_question(
        query,
        "液冷",
        question_type_override=question_type,
    )
    result.answer_spec = _answer_spec(
        query,
        evidence_id=evidence_id,
        matched_theme=matched_theme,
        fact_text=fact_text,
        evidence_tier=evidence_tier,
    )
    result.citations = [
        Citation(
            tag=evidence_id,
            source="公司公告",
            detail="2026-07-10 业务进展公告",
        )
    ]
    return result


def _quality_contract(
    query: str,
    *,
    quality_error: bool = False,
) -> SkillAnswerContract:
    spec = _answer_spec(query)
    summary = answer_model.make_claim(
        claim_id="quality-summary",
        text="财务指标已形成可回查的报告期结论。",
        claim_type="summary",
        theme=spec.research_spec.theme,
        status=answer_model.ClaimStatus.VERIFIED,
        evidence_tier="公告",
        evidence_ids=("W1",),
    )
    gap = answer_model.make_claim(
        claim_id="quality-gap",
        text="仍需核对下一期经营数据。",
        claim_type="evidence_gap",
        theme=spec.research_spec.theme,
        status=answer_model.ClaimStatus.MISSING,
    )
    governed = answer_model.finalize_answer_spec(
        replace(spec, summary=(summary,), gaps=(gap,))
    )
    if quality_error:
        governed = replace(
            governed,
            quality=answer_model.AnswerQualityReport(
                issues=(
                    answer_model.QualityIssue(
                        code="forced_quality_error",
                        severity="error",
                        message="测试质量错误",
                    ),
                )
            ),
        )
    return SkillAnswerContract(
        retrieval_plan=FINANCIAL_ANALYSIS.retrieval_plan,
        output_contract=FINANCIAL_ANALYSIS.output_contract,
        answer_spec=governed,
        question_type=FINANCIAL_ANALYSIS.question_type,
    )


def _required_stage(
    stage: str,
    *,
    status: str = "completed",
    evidence_atom_ids: tuple[str, ...] = ("atom-1",),
    payload: dict[str, object] | None = None,
) -> StageArtifact:
    return StageArtifact(
        stage=stage,
        status=status,
        elapsed_ms=1,
        producer=f"test.{stage}",
        artifact_type=f"{stage}.artifact",
        required_output=True,
        evidence_atom_ids=evidence_atom_ids,
        payload=payload or {"available": True},
    )


def test_owner_result_status_adjudicates_all_four_states() -> None:
    owner = ResearchOwnerSkill(FINANCIAL_ANALYSIS)
    stages = tuple(
        _required_stage(stage)
        for stage in OWNER_RETRIEVAL_STAGES["financial-analysis"]
    )
    contract = _quality_contract("分析贵州茅台财报")

    assert owner._owner_result_status(contract, stages, []) == "completed"

    partial_stages = (
        replace(stages[0], status="timeout"),
        *stages[1:],
    )
    assert (
        owner._owner_result_status(contract, partial_stages, [])
        == "partial"
    )

    degraded_stages = (
        replace(stages[0], evidence_atom_ids=()),
        *stages[1:],
    )
    assert (
        owner._owner_result_status(contract, degraded_stages, [])
        == "degraded"
    )
    assert (
        owner._owner_result_status(
            _quality_contract(
                "分析贵州茅台财报",
                quality_error=True,
            ),
            stages,
            [],
        )
        == "degraded"
    )

    failed_stages = tuple(
        replace(stage, status="failed", evidence_atom_ids=())
        for stage in stages
    )
    assert (
        owner._owner_result_status(None, failed_stages, [])
        == "failed"
    )
    assert (
        owner._owner_result_status(contract, failed_stages, [])
        == "failed"
    )


def test_company_evidence_stage_requires_company_bound_hard_source() -> None:
    owner = ResearchOwnerSkill(STOCK_DEEP_DIVE)
    market_only = _required_stage(
        "company_evidence",
        payload={
            "available": True,
            "claims": [
                {
                    "company": "示例科技",
                    "status": "verified",
                    "evidence_tier": "market_data",
                    "evidence_ids": ["D7"],
                }
            ],
        },
    )
    official = replace(
        market_only,
        payload={
            "available": True,
            "claims": [
                {
                    "company": "示例科技",
                    "status": "verified",
                    "evidence_tier": "L3",
                    "evidence_ids": ["L3-1"],
                }
            ],
        },
    )

    assert not owner._stage_meets_evidence_threshold(market_only)
    assert owner._stage_meets_evidence_threshold(official)


def test_followup_merges_validated_previous_answer_spec_without_opening_gate() -> None:
    owner = ResearchOwnerSkill(STOCK_DEEP_DIVE)
    current = _answer_spec(
        "英维克液冷业务",
        evidence_id="W2",
        fact_text="当前轮补充了毛利率资料",
    )
    previous = _answer_spec(
        "英维克液冷业务",
        evidence_id="W1",
        fact_text="上一轮已经核验客户公告",
    )
    previous = replace(
        previous,
        verified_facts=(
            replace(previous.verified_facts[0], claim_id="previous-fact"),
        ),
        summary=(
            replace(previous.summary[0], claim_id="previous-fact"),
        ),
    )

    merged = owner._merge_inherited_answer_spec(
        current,
        previous.to_dict(),
    )

    assert {claim.claim_id for claim in merged.verified_facts} == {
        "fact-1",
        "previous-fact",
    }
    assert {source.evidence_id for source in merged.sources} == {"W1", "W2"}
    issues = answer_model.validate_llm_answer(
        "海光信息弹性一定更大。",
        merged,
    )
    assert any(issue.code == "llm_missing_claim_binding" for issue in issues)


def _context(
    tmp_path: Path,
    store: RunStore,
    run_id: str,
    query: str,
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
        deadline=ResearchDeadline.from_timeout(10),
    )


def _write_theme_market_db(repo_root: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    db_path = repo_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(
        "create table fact_sector_daily "
        "(trade_date date, sector_name varchar, pct_chg double, "
        "diff_ratio double, amount double)"
    )
    start = date(2025, 1, 1)
    for index in range(200):
        hot = 40 <= index < 60 or 180 <= index < 200
        con.execute(
            "insert into fact_sector_daily values (?, '信创', ?, ?, ?)",
            [
                (start + timedelta(days=index)).isoformat(),
                2.5 if hot else -0.5,
                15.0 if hot else 2.0,
                900.0 if hot else 300.0,
            ],
        )
    con.execute(
        "create table fact_theme_limit_heat_daily "
        "(trade_date date, sector_name varchar, limit_up_count int, rank int)"
    )
    con.execute(
        "insert into fact_theme_limit_heat_daily values "
        "(?, '信创', 8, 3)",
        [(start + timedelta(days=199)).isoformat()],
    )
    con.close()


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

    output = skill.execute(_context(tmp_path, store, run.run_id, "分析液冷"))

    assert captured[0].question_type_override == config.question_type
    assert captured[0].compose is True
    assert captured[0].synthesize is False
    assert captured[0].include_memory_block is True
    assert captured[0].include_recall_block is True
    assert captured[0].wiki_rag_timeout == config.wiki_rag_timeout
    assert captured[0].module_timeout == config.module_timeout
    assert captured[0].use_modules is config.use_modules
    assert captured[0].conversation_context == "用户上一轮强调只看公告级证据。"
    assert captured[0].deadline is not None
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
    assert [item["stage"] for item in output.stage_artifacts] == list(
        OWNER_RETRIEVAL_STAGES[config.skill_id]
    )
    artifact = json.loads(
        (store.run_dir(run.run_id) / output.raw_result_ref).read_text(
            encoding="utf-8"
        )
    )
    assert artifact["owned"] is True
    assert artifact["retrieval_plan"] == list(config.retrieval_plan)
    assert [item["stage"] for item in artifact["stage_artifacts"]] == list(
        OWNER_RETRIEVAL_STAGES[config.skill_id]
    )


def test_owner_dag_reuses_single_turn_retrieval_cache(tmp_path: Path) -> None:
    calls = 0

    def fake_answer_query(options: AskOptions) -> AskResult:
        nonlocal calls
        calls += 1
        return _result(options.query, STOCK_DEEP_DIVE.question_type)

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("分析液冷", "ask")
    context = _context(tmp_path, store, run.run_id, "分析液冷")
    skill = ResearchOwnerSkill(
        STOCK_DEEP_DIVE,
        answer_query_fn=fake_answer_query,
    )

    first = skill.execute(context)
    second = skill.execute(context)

    assert calls == 1
    assert [item["stage"] for item in first.stage_artifacts] == [
        item["stage"] for item in second.stage_artifacts
    ]


def test_theme_vertical_slice_uses_distinct_typed_stage_artifacts(
    tmp_path: Path,
) -> None:
    query = (
        "研究信创未来3到6个月的中期赔率，"
        "用历史类似窗口和情景树说明升级、降级与证伪条件"
    )
    calls = 0

    def fake_answer_query(options: AskOptions) -> AskResult:
        nonlocal calls
        calls += 1
        return _result(
            options.query,
            THEME_RESEARCH.question_type,
            evidence_id="S1",
            matched_theme="信创",
            fact_text="信创板块已形成可回查的盘面事实",
            evidence_tier="盘面",
        )

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run(query, "ask")
    output = ResearchOwnerSkill(
        THEME_RESEARCH,
        answer_query_fn=fake_answer_query,
    ).execute(_context(tmp_path, store, run.run_id, query))

    assert calls == 1
    artifacts = {item["stage"]: item for item in output.stage_artifacts}
    assert set(artifacts) == set(OWNER_RETRIEVAL_STAGES["theme-research"])
    assert all(item["producer"] for item in artifacts.values())
    assert all(item["input_hash"] for item in artifacts.values())
    assert all(item["timeout_seconds"] > 0 for item in artifacts.values())
    assert all(item["on_failure"] for item in artifacts.values())
    assert len({item["producer"] for item in artifacts.values()}) == len(artifacts)
    assert all(
        item["payload"].get("source_mode") != "shared_owner_bundle"
        for item in artifacts.values()
    )
    assert artifacts["market_lifecycle"]["artifact_type"] == "MidtermTrendArtifact"
    assert (
        artifacts["historical_analogs"]["artifact_type"]
        == "HistoricalAnalogArtifact"
    )
    assert artifacts["scenario_tree"]["artifact_type"] == "ScenarioTreeArtifact"
    assert (
        artifacts["counterevidence"]["artifact_type"]
        == "CounterEvidenceArtifact"
    )
    assert artifacts["historical_analogs"]["required_output"] is True
    assert artifacts["scenario_tree"]["required_output"] is True
    assert artifacts["counterevidence"]["required_output"] is True

    assert output.answer_contract is not None
    rendered = answer_model.render_answer_spec(
        output.answer_contract.answer_spec
    )
    assert "## 3–6 个月中期赔率的证据" in rendered
    assert "## 历史类似窗口" in rendered
    assert "## 情景树" in rendered
    assert "## 升级、降级与证伪条件" in rendered
    assert "无来源数字概率" in rendered


@pytest.mark.parametrize(
    ("config", "evidence_id", "expected_types", "headings"),
    [
        (
            STOCK_DEEP_DIVE,
            "R1",
            {
                "company_master": "CompanyMasterArtifact",
                "company_evidence": "CompanyEvidenceArtifact",
                "financial_transmission": "FinancialTransmissionArtifact",
                "market_choice": "MarketChoiceArtifact",
                "counterevidence": "CounterEvidenceArtifact",
            },
            ("## 公司本体", "## 公司级证据块", "## 财务传导", "## 市场选择", "## 反证与证伪"),
        ),
        (
            FINANCIAL_ANALYSIS,
            "D7",
            {
                "report_period": "ReportPeriodArtifact",
                "financial_metrics": "FinancialMetricsArtifact",
                "segment_disclosure": "SegmentDisclosureArtifact",
                "prior_period_comparison": "PriorPeriodComparisonArtifact",
            },
            ("## 报告期间", "## 财务指标", "## 分部披露", "## 前期比较"),
        ),
        (
            NEWS_IMPACT,
            "W1",
            {
                "original_disclosure": "OriginalDisclosureArtifact",
                "event_facts": "EventFactsArtifact",
                "impact_transmission": "ImpactTransmissionArtifact",
                "substitutes_and_harmed_directions": "ImpactDirectionsArtifact",
            },
            ("## 原始披露", "## 事件事实", "## 影响传导", "## 受益、替代与受损方向"),
        ),
    ],
)
def test_phase3_owners_use_distinct_typed_stage_artifacts(
    tmp_path: Path,
    config: ResearchOwnerConfig,
    evidence_id: str,
    expected_types: dict[str, str],
    headings: tuple[str, ...],
) -> None:
    calls = 0

    def fake_answer_query(options: AskOptions) -> AskResult:
        nonlocal calls
        calls += 1
        return _result(
            options.query,
            config.question_type,
            evidence_id=evidence_id,
            fact_text="公司公告披露营收增长，市场相对强度改善",
        )

    query = {
        "stock-deep-dive": "请个股深挖英维克",
        "financial-analysis": "分析贵州茅台财报和毛利率",
        "news-impact": "英维克最新液冷公告有什么影响",
    }[config.skill_id]
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run(query, "ask")
    output = ResearchOwnerSkill(
        config,
        answer_query_fn=fake_answer_query,
    ).execute(_context(tmp_path, store, run.run_id, query))

    assert calls == 1
    artifacts = {item["stage"]: item for item in output.stage_artifacts}
    assert set(artifacts) == set(expected_types)
    assert {
        stage: item["artifact_type"] for stage, item in artifacts.items()
    } == expected_types
    assert len({item["producer"] for item in artifacts.values()}) == len(
        artifacts
    )
    assert len({item["input_hash"] for item in artifacts.values()}) == len(
        artifacts
    )
    assert all(item["timeout_seconds"] > 0 for item in artifacts.values())
    assert all(item["on_failure"] for item in artifacts.values())
    assert all(
        item["payload"].get("source_mode") != "shared_owner_bundle"
        for item in artifacts.values()
    )

    assert output.answer_contract is not None
    rendered = answer_model.render_answer_spec(
        output.answer_contract.answer_spec
    )
    assert all(heading in rendered for heading in headings)


@pytest.mark.parametrize(
    ("config", "query", "headings"),
    [
        (
            STOCK_DEEP_DIVE,
            "请个股深挖英维克",
            ("## 公司本体", "## 公司级证据块", "## 财务传导", "## 市场选择", "## 反证与证伪"),
        ),
        (
            FINANCIAL_ANALYSIS,
            "分析贵州茅台财报和毛利率",
            ("## 报告期间", "## 财务指标", "## 分部披露", "## 前期比较"),
        ),
        (
            NEWS_IMPACT,
            "英维克最新液冷公告有什么影响",
            ("## 原始披露", "## 事件事实", "## 影响传导", "## 受益、替代与受损方向"),
        ),
    ],
)
def test_phase3_owner_blocks_survive_retrieval_failure(
    tmp_path: Path,
    config: ResearchOwnerConfig,
    query: str,
    headings: tuple[str, ...],
) -> None:
    def unavailable_answer_query(_options: AskOptions) -> AskResult:
        raise RuntimeError("retrieval unavailable")

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run(query, "ask")
    output = ResearchOwnerSkill(
        config,
        answer_query_fn=unavailable_answer_query,
    ).execute(_context(tmp_path, store, run.run_id, query))

    assert output.answer_contract is not None
    assert output.modules == []
    assert output.citations == []
    assert output.status == "partial"
    assert output.stage_artifacts[0]["status"] == "failed"
    assert all(
        item["status"] != "completed" for item in output.stage_artifacts
    )
    rendered = answer_model.render_answer_spec(
        output.answer_contract.answer_spec
    )
    assert all(heading in rendered for heading in headings)


@pytest.mark.parametrize(
    ("config", "evidence_id"),
    [
        (STOCK_DEEP_DIVE, "R1"),
        (FINANCIAL_ANALYSIS, "D7"),
        (NEWS_IMPACT, "W1"),
    ],
)
def test_phase3_owners_soften_hard_certainty_without_l3(
    tmp_path: Path,
    config: ResearchOwnerConfig,
    evidence_id: str,
) -> None:
    query = {
        "stock-deep-dive": "请个股深挖英维克",
        "financial-analysis": "分析贵州茅台财报和毛利率",
        "news-impact": "英维克最新液冷公告有什么影响",
    }[config.skill_id]

    def fake_answer_query(options: AskOptions) -> AskResult:
        return _result(
            options.query,
            config.question_type,
            evidence_id=evidence_id,
            fact_text="该方向未来必然确定上涨",
            evidence_tier="盘面",
        )

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run(query, "ask")
    output = ResearchOwnerSkill(
        config,
        answer_query_fn=fake_answer_query,
    ).execute(_context(tmp_path, store, run.run_id, query))

    assert output.answer_contract is not None
    rendered = answer_model.render_answer_spec(
        output.answer_contract.answer_spec
    )
    assert "必然" not in rendered
    assert "确定" not in rendered


def test_theme_fallback_keeps_required_blocks_and_softens_certainty_without_l3(
    tmp_path: Path,
) -> None:
    query = (
        "研究信创未来3到6个月的中期赔率，"
        "用历史类似窗口和情景树说明升级、降级与证伪条件"
    )

    def fake_answer_query(options: AskOptions) -> AskResult:
        return _result(
            options.query,
            THEME_RESEARCH.question_type,
            evidence_id="S1",
            matched_theme="信创",
            fact_text="信创未来必然确定上涨",
            evidence_tier="盘面",
        )

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run(query, "ask")
    output = ResearchOwnerSkill(
        THEME_RESEARCH,
        answer_query_fn=fake_answer_query,
    ).execute(_context(tmp_path, store, run.run_id, query))

    assert output.answer_contract is not None
    rendered = answer_model.render_answer_spec(
        output.answer_contract.answer_spec
    )
    assert "## 历史类似窗口" in rendered
    assert "## 情景树" in rendered
    assert "## 升级、降级与证伪条件" in rendered
    assert "必然" not in rendered
    assert "确定" not in rendered
    assert "40%" not in rendered


def test_theme_required_blocks_survive_company_mapping_failure(
    tmp_path: Path,
) -> None:
    query = (
        "研究信创未来3到6个月的中期赔率，"
        "用历史类似窗口和情景树说明升级、降级与证伪条件"
    )
    _write_theme_market_db(tmp_path)

    def unavailable_answer_query(_options: AskOptions) -> AskResult:
        raise RuntimeError("RAG unavailable")

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run(query, "ask")
    output = ResearchOwnerSkill(
        THEME_RESEARCH,
        answer_query_fn=unavailable_answer_query,
    ).execute(_context(tmp_path, store, run.run_id, query))

    assert output.answer_contract is not None
    assert output.modules == []
    assert output.citations == []
    assert output.status == "partial"
    artifacts = {item["stage"]: item for item in output.stage_artifacts}
    assert artifacts["company_mapping"]["status"] == "failed"
    assert artifacts["market_lifecycle"]["status"] == "completed"
    assert artifacts["historical_analogs"]["status"] == "completed"
    assert artifacts["scenario_tree"]["status"] == "completed"
    assert artifacts["counterevidence"]["status"] == "completed"

    spec = output.answer_contract.answer_spec
    known_atom_ids = {
        atom.atom_id
        for atom in answer_model.evidence_atoms_from_answer_spec(spec)
    }
    assert known_atom_ids
    assert set(artifacts["scenario_tree"]["evidence_atom_ids"]) <= known_atom_ids
    assert set(artifacts["counterevidence"]["evidence_atom_ids"]) <= known_atom_ids
    rendered = answer_model.render_answer_spec(spec)
    assert "## 3–6 个月中期赔率的证据" in rendered
    assert "## 历史类似窗口" in rendered
    assert "## 情景树" in rendered
    assert "## 升级、降级与证伪条件" in rendered
    assert "claim_id=analog-" in rendered
    assert "必然" not in rendered
    assert "确定" not in rendered


def test_theme_market_artifacts_bind_facts_to_evidence_atoms(
    tmp_path: Path,
) -> None:
    query = (
        "研究信创未来3到6个月的中期赔率，"
        "用历史类似窗口和情景树说明升级、降级与证伪条件"
    )
    _write_theme_market_db(tmp_path)

    def fake_answer_query(options: AskOptions) -> AskResult:
        return _result(
            options.query,
            THEME_RESEARCH.question_type,
            evidence_id="S1",
            matched_theme="信创",
            fact_text="信创板块已形成可回查的盘面事实",
            evidence_tier="盘面",
        )

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run(query, "ask")
    output = ResearchOwnerSkill(
        THEME_RESEARCH,
        answer_query_fn=fake_answer_query,
    ).execute(_context(tmp_path, store, run.run_id, query))

    artifacts = {item["stage"]: item for item in output.stage_artifacts}
    assert artifacts["market_lifecycle"]["status"] == "completed"
    assert artifacts["historical_analogs"]["status"] == "completed"
    assert artifacts["market_lifecycle"]["evidence_atom_ids"]
    assert artifacts["historical_analogs"]["evidence_atom_ids"]
    assert output.answer_contract is not None
    spec = output.answer_contract.answer_spec
    known_atom_ids = {
        atom.atom_id
        for atom in answer_model.evidence_atoms_from_answer_spec(spec)
    }
    stage_atom_ids = {
        atom_id
        for stage in ("market_lifecycle", "historical_analogs")
        for atom_id in artifacts[stage]["evidence_atom_ids"]
    }
    assert stage_atom_ids <= known_atom_ids

    rendered = answer_model.render_answer_spec(spec)
    structured_claims, _unbound = answer_model.parse_structured_claims(rendered)
    stage_fact_claims = [
        claim
        for claim in structured_claims
        if claim.claim_id.startswith(("midterm-", "analog-"))
    ]
    assert stage_fact_claims
    assert all(claim.evidence_atom_ids for claim in stage_fact_claims)
    assert all(
        set(claim.evidence_atom_ids) <= known_atom_ids
        for claim in stage_fact_claims
    )


def test_stage_adapter_timeout_is_independently_observable() -> None:
    def slow_stage(
        _result: AskResult | None,
        _artifacts: tuple[StageArtifact, ...],
    ) -> StageExecution:
        time.sleep(0.05)
        return StageExecution(status="completed", payload={"available": True})

    dag = execute_owner_dag(
        cache_key="theme:test",
        stages=("historical_analogs",),
        retrieve=lambda: _result("test", THEME_RESEARCH.question_type),
        cache={},
        deadline=ResearchDeadline.from_timeout(1),
        stage_adapters={
            "historical_analogs": StageAdapter(
                producer="market_analogs.D8",
                input_hash="input-hash",
                artifact_type="HistoricalAnalogArtifact",
                required_output=True,
                timeout_seconds=0.01,
                on_failure="render_historical_analog_gap",
                execute=slow_stage,
            )
        },
    )

    assert dag.result is None
    assert dag.artifacts[0].status == "timeout"
    assert dag.artifacts[0].producer == "market_analogs.D8"
    assert dag.artifacts[0].input_hash == "input-hash"
    assert dag.artifacts[0].timeout_seconds == 0.01
    assert dag.artifacts[0].on_failure == "render_historical_analog_gap"
    assert dag.artifacts[0].degrade_reason is not None


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


def test_plain_theme_query_still_falls_back_without_traceable_evidence(
    tmp_path: Path,
) -> None:
    query = "研究液冷题材产业链"

    def fake_answer_query(options: AskOptions) -> AskResult:
        return _result(
            options.query,
            THEME_RESEARCH.question_type,
            evidence_id="ONTOLOGY",
        )

    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run(query, "ask")
    output = ResearchOwnerSkill(
        THEME_RESEARCH,
        answer_query_fn=fake_answer_query,
    ).execute(_context(tmp_path, store, run.run_id, query))

    assert output.answer_contract is None
    assert output.modules == []
    assert output.citations == []
    assert output.warnings[-1] == "专项检索未形成可追溯事实，已回退基础金融回答。"


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
def test_p2_research_owner_is_injected_by_controller_contract(
    query: str,
    skill_id: str,
) -> None:
    routed = route_skills(
        query,
        "ask",
        "auto",
        [],
        registry=SKILL_REGISTRY,
        answer_owner=skill_id,
    )

    assert skill_id in {
        selection.skill_id for selection in routed.selections
    }
    assert routed.base_finance_fallback is False

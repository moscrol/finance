"""Offline regression cases: dated report selection and calculation delivery."""
from __future__ import annotations

import json
import socket
from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest

from intelligence.services import derived_calculation as dc, market_financials as mf
from intelligence.services.agent_research import AgentEvidence, StructuredObservation, evidence_content_hash
from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent, OutputEvidenceBinding
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_protocol import expand_episode_snapshot_bindings
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.honesty_gates import requested_information_cutoff
from intelligence.services.research_contract import InformationCutoff
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import (
    DERIVED_CALCULATION_PARAMETERS, ToolObservation,
)
from intelligence.services.task_frame import TaskFrame

QUESTION = (
    "请分析截至2026年9月17日甲公司最近两份已披露定期报告的收入、归母净利润"
    "和经营活动现金流净额，注明报告期和可比口径。指定复查日为2026-10-22。"
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*_args, **_kwargs):
        pytest.fail("R5 regression attempted network IO")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)


def _frame(query=QUESTION):
    return TaskFrame(
        raw_question=query, user_goal=query, question_type="financial_analysis",
        subject="300308", subject_kind="company", market_scope="A股", timeframe=None,
        required_outputs=("financial_assessment", "metric_evidence", "counterpoint"),
        assumptions=(), ambiguities=(), clarification_question=None,
        evidence_policy="company_financial_evidence", confidence=0.95,
    )


def _context(query=QUESTION):
    return build_episode_context(
        _frame(query), task_id=f"r5-{uuid4().hex}", today="2026-09-18",
        latest_data_date="2026-09-17", capabilities=("financial_data", "derived_calculation"),
        timeout=60,
    )


@pytest.mark.parametrize("text", [
    "截至2026年9月17日，最近两份财报如何？",
    "请分析截至2026年9月17日甲公司的财务表现。于2026-10-22复查。",
    "请研究甲公司：以2026年9月17日为信息截止点，利润是否兑现？",
    "请研究甲公司，信息截止日为2026-09-17；复查日为2026-10-22。",
    "只使用截至2026-09-17已披露的信息，分析甲公司的财务。",
    "截至 2026-09-17，分析最近两份报告。",
])
def test_cutoff_role_reaches_context_and_not_review_day(text):
    expected = InformationCutoff(date(2026, 9, 17), "requested")
    assert requested_information_cutoff(text, today="2026-09-18") == expected
    assert _context(text).information_cutoff == expected


@pytest.mark.parametrize("text", [
    "请分析甲公司。报告期截至2026年6月30日，复查日为2026-10-22。",
    "请分析甲公司，2026-10-22复查。",
    "不要以2026年9月17日为信息截止点，请分析最新信息。",
    "请分析2026年9月1日至17日的行情。",
    "截至2026年2月30日，分析甲公司的财务。",
    "请分析这段材料。\n\n> 以2026年9月17日为信息截止点，利润增长。",
    "请分析这段材料。\n\n> 站在2026-09-17收盘，利润增长。",
    "请分析甲公司，报告期：截至2026年6月30日。",
    "不要截至2026-09-17收盘分析，按最新资料分析。",
    "2026-10-22复查本次财报分析。",
])
def test_non_cutoff_roles_do_not_become_information_cutoff(text):
    assert requested_information_cutoff(text, today="2026-09-18") is None


@pytest.mark.parametrize("text, expected", [
    (QUESTION, None),
    ("以2026年9月16日为信息截止点，最近两期的净利润如何？", None),
    ("截至2026-09-17，比较2025年报的经营现金流", date(2025, 12, 31)),
    ("2026-10-22复查2024年报净利润", date(2024, 12, 31)),
    ("2024年营业总收入", date(2024, 12, 31)),
    ("2025年三季报", date(2025, 9, 30)),
])
def test_report_year_must_belong_to_report_period(text, expected):
    assert mf.target_report_end_from_query(text) == expected


def _rows():
    return [
        mf.QuarterFinancials("2026中报", "2026-06-30", revenue_yi=40,
                             netprofit_yi=10, ocf_yi=5, notice_date="2026-08-22"),
        mf.QuarterFinancials("2026一季报", "2026-03-31", revenue_yi=18,
                             netprofit_yi=4, ocf_yi=1, notice_date="2026-04-25"),
        mf.QuarterFinancials("2025年报", "2025-12-31", revenue_yi=60,
                             netprofit_yi=15, ocf_yi=12, notice_date="2026-04-15"),
        mf.QuarterFinancials("2025三季报", "2025-09-30", revenue_yi=45,
                             netprofit_yi=11, ocf_yi=8, notice_date="2025-10-25"),
        mf.QuarterFinancials("2025中报", "2025-06-30", revenue_yi=28,
                             netprofit_yi=7, ocf_yi=4, notice_date="2025-08-22"),
        mf.QuarterFinancials("2025一季报", "2025-03-31", revenue_yi=12,
                             netprofit_yi=3, ocf_yi=1, notice_date="2025-04-25"),
    ]


def _tool_result(monkeypatch, tmp_path, *, rows=None, query=QUESTION):
    from intelligence.services import episode_tools
    rows = _rows() if rows is None else rows
    bundle = mf.FinancialsBundle(
        "300308.SZ", "甲公司", tuple(rows), None,
        mf.build_financials_block("甲公司", "300308.SZ", rows),
    )
    monkeypatch.setattr(episode_tools.ask_blocks, "_financials_bundle_for_llm",
                        lambda *_a, **_kw: bundle)
    context = _context(query)
    registry = build_episode_registry(
        _frame(query), context, finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki", l3_runner=None,
    )
    result = registry.execute("financial_data", {}, context=context, step_id="r5:financial")
    return result, context


def test_all_financial_rows_survive_with_pair_selection(monkeypatch, tmp_path):
    result, _ = _tool_result(monkeypatch, tmp_path)
    actual = {(o.as_of, o.metric) for e in result.evidence for o in e.observations}
    assert {(r.report_date, "ocf_cum_yi") for r in _rows()} <= actual
    assert len(result.evidence) == 12  # only rows, no headers / fetch date / guidance
    selection = result.telemetry["financial_report_selection"][0]
    assert selection["selected_periods"] == ["2026-06-30", "2026-03-31"]
    assert selection["information_cutoff"] == "2026-09-17"
    assert "2026-06-30、2026-03-31" in result.observation[:900]
    assert not result.gaps
    assert all(e.content_hash == evidence_content_hash(e) for e in result.evidence)


@pytest.mark.parametrize("notice", [None, "2026-09-19", "2026-02-30"])
def test_unconfirmed_disclosure_is_not_eligible_as_of_cutoff(monkeypatch, tmp_path, notice):
    rows = _rows()
    rows[0] = replace(rows[0], notice_date=notice)
    result, _ = _tool_result(monkeypatch, tmp_path, rows=rows)
    assert all(o.as_of != "2026-06-30" for e in result.evidence for o in e.observations)
    selection = result.telemetry["financial_report_selection"][0]
    assert selection["selected_periods"] == ["2026-03-31", "2025-12-31"]
    assert selection["candidates"][0]["reason"] != "eligible"
    assert result.gaps  # unknown disclosure is not proof of no report


def _outcome(context, evidence, *, kept_periods):
    hashes = tuple(e.content_hash for e in evidence if any(
        o.as_of in kept_periods for o in e.observations
    ))
    return AgentOutcome(
        status="completed", draft="、".join(sorted(kept_periods)) + "收入和现金流已分别列示，累计期间长度不同，不能直接比较增长。",
        evidence=tuple(evidence), bindings=tuple(
            OutputEvidenceBinding(output_id=o.output_id, evidence_hashes=hashes, basis="evidence")
            for o in context.contract.required_outputs
        ), task_frame_hash=context.contract.task_frame_hash, traces=(), gaps=(),
        stop_reason="finish", usage=AgentUsage(),
        events=(EpisodeEvent(1, "task", {"task_frame_hash": context.contract.task_frame_hash}),),
    )


def test_skipping_available_q1_is_a_local_gap_not_whole_answer_erasure(monkeypatch, tmp_path):
    result, context = _tool_result(monkeypatch, tmp_path)
    outcome = _outcome(context, result.evidence, kept_periods={"2026-06-30", "2025-12-31"})
    verified = verify_episode_outcome(context.contract, outcome)
    assert verified.verified_status == "partial"
    assert verified.missing_outputs == ("metric_evidence",)
    assert verified.outcome.draft == outcome.draft
    statuses = {o.output_id: o.status for o in verified.completion.outputs}
    assert statuses["financial_assessment"] == "fulfilled"
    assert statuses["counterpoint"] == "fulfilled"


def test_bound_latest_pair_can_complete_without_forcing_a_calculation(monkeypatch, tmp_path):
    result, context = _tool_result(monkeypatch, tmp_path)
    verified = verify_episode_outcome(context.contract, _outcome(
        context, result.evidence, kept_periods={"2026-06-30", "2026-03-31"},
    ))
    assert verified.verified_status == "completed"


def test_missing_cash_flow_cannot_be_replaced_with_old_annual_row(monkeypatch, tmp_path):
    rows = _rows()
    rows[1] = replace(rows[1], ocf_yi=None)
    result, context = _tool_result(monkeypatch, tmp_path, rows=rows)
    verified = verify_episode_outcome(context.contract, _outcome(
        context, result.evidence, kept_periods={"2026-06-30", "2026-03-31", "2025-12-31"},
    ))
    assert "metric_evidence" in verified.missing_outputs
    assert any("ocf_cum_yi" in o.gap for o in verified.completion.outputs)


def _project(result):
    observation = ToolObservation(
        tool="derived_calculation", query="核对净现比", evidence=result.evidence,
        observation=result.observation, trace=result.trace, gaps=result.gaps,
        evidence_hashes=tuple(e.content_hash for e in result.evidence), telemetry=result.telemetry,
    )
    return FinanceResearchHarness().project_tool_result(
        observation, evidence_so_far=observation.evidence, seen_prose=set(),
    )


@pytest.mark.parametrize("code", [dc.ERROR_SCRIPT_ERROR, dc.ERROR_BASE_CALC_NOT_FOUND, dc.ERROR_SANDBOX_TIMEOUT])
def test_domain_calculation_failure_survives_model_projection(code):
    result = dc.to_tool_result(dc.CalculationError(code, "测试计算未产出"))
    projected = _project(result)
    payload = json.loads(projected.model_content)
    assert projected.audit_payload["ok"] is False
    assert payload["ok"] is False
    assert payload["error"] == code
    assert payload["gaps"]
    assert payload["evidence"] == []
    assert "calculation_error" in projected.audit_payload["telemetry"]
    assert "telemetry" not in payload


def test_calculation_signature_is_exact_and_executable():
    text = DERIVED_CALCULATION_PARAMETERS["properties"]["script"]["description"]
    assert "table(name, columns, rows, *, unit=None, note=None)" in text
    assert "chart(name, kind, x, series_by_label, *, unit=None, y_label=None)" in text
    item = AgentEvidence("financial_data", "财务", "收入40亿元", "测试源", content_hash="source")
    calc = dc.run_derived_calculation(
        script="emit_result(tables=[table('核对', ['金额'], [[40]], unit='亿元')])",
        purpose="接口实例", evidence=(item,),
    )
    assert isinstance(calc, dc.DerivedCalculation)
    payload = json.loads(_project(dc.to_tool_result(calc)).model_content)
    assert payload["ok"] is True
    assert payload["evidence"]


def test_table_api_error_carries_actionable_signature():
    result = dc.to_tool_result(dc.CalculationError(
        dc.ERROR_SCRIPT_ERROR, "TypeError: table() got an unexpected keyword argument 'title'",
    ))
    assert "table(name, columns, rows, *, unit=None, note=None)" in result.observation
    assert "title" in result.observation


def _expanded(outcome):
    from intelligence.services.research_tool_registry import default_registry
    return replace(outcome, bindings=expand_episode_snapshot_bindings(
        bindings=outcome.bindings, evidence=outcome.evidence,
        registry=default_registry({"financial_data": lambda *_: None}), draft=outcome.draft,
    ))


def test_snapshot_expansion_does_not_certify_an_omitted_report(monkeypatch, tmp_path):
    result, context = _tool_result(monkeypatch, tmp_path)
    outcome = _expanded(_outcome(
        context, result.evidence, kept_periods={"2026-06-30", "2025-12-31"},
    ))
    assert all(len(b.evidence_hashes) == 12 for b in outcome.bindings)
    verified = verify_episode_outcome(context.contract, outcome)
    assert verified.missing_outputs == ("metric_evidence",)
    assert "2026-03-31" in verified.completion.outputs[1].gap
    assert verified.outcome.draft == outcome.draft


@pytest.mark.parametrize("draft", [
    "2026年中报与2026年一季报，收入和现金流累计长度不同，不直接环比。",
    "2026H1与2026Q1，收入和现金流累计长度不同，不直接环比。",
    "H1 2026与Q1 2026，收入和现金流累计长度不同，不直接环比。",
    "2026年6月30日与2026年3月31日报告的收入和现金流。",
])
def test_equivalent_period_labels_are_accepted(monkeypatch, tmp_path, draft):
    result, context = _tool_result(monkeypatch, tmp_path)
    outcome = replace(_outcome(
        context, result.evidence, kept_periods={"2026-06-30", "2026-03-31"},
    ), draft=draft)
    assert verify_episode_outcome(context.contract, outcome).verified_status == "completed"


def test_unresolved_newer_disclosure_remains_a_gap_after_binding_older_pair(monkeypatch, tmp_path):
    rows = _rows()
    rows[0] = replace(rows[0], notice_date=None)
    result, context = _tool_result(monkeypatch, tmp_path, rows=rows)
    outcome = _outcome(context, result.evidence, kept_periods={"2026-03-31", "2025-12-31"})
    outcome = replace(outcome, events=(*outcome.events, EpisodeEvent(2, "tool_result", {
        "tool": "financial_data", "telemetry": result.telemetry,
    })))
    verified = verify_episode_outcome(context.contract, outcome)
    assert verified.missing_outputs == ("metric_evidence",)
    assert "disclosure_unverified" in verified.completion.outputs[1].gap


def test_other_company_does_not_poison_requested_company_pair(monkeypatch, tmp_path):
    result, context = _tool_result(monkeypatch, tmp_path)
    other = AgentEvidence(
        "financial_data", "乙公司（600000）报告期 2026-06-30", "乙公司的收入", "测试源",
        content_hash="other", observations=(StructuredObservation("600000", "2026-06-30", "revenue_cum_yi", 20),),
    )
    outcome = _outcome(context, (*result.evidence, other), kept_periods={"2026-06-30", "2026-03-31"})
    assert verify_episode_outcome(context.contract, outcome).verified_status == "completed"


@pytest.mark.parametrize("purpose", ["其他计算", "净现比"])
def test_unrelated_or_empty_calculation_cannot_discharge_requested_ratio(monkeypatch, tmp_path, purpose):
    query = QUESTION + "请计算净现比。"
    result, context = _tool_result(monkeypatch, tmp_path, query=query)
    outcome = _outcome(context, result.evidence, kept_periods={"2026-06-30", "2026-03-31"})
    for script in ["emit_result(summary={'other': 2})", "emit_result(summary={})"]:
        calc = dc.run_derived_calculation(script=script, purpose=purpose, evidence=result.evidence)
        if script == "emit_result(summary={})":
            # New result admission now rejects the empty product even earlier;
            # keep the original obligation assertion, not a forged success.
            assert isinstance(calc, dc.CalculationError)
            assert calc.code == dc.ERROR_INVALID_RESULT
            failed = dc.to_tool_result(calc)
            assert not failed.evidence and failed.gaps
            candidate = outcome
        else:
            assert isinstance(calc, dc.DerivedCalculation)
            item = dc.derived_evidence(calc)
            item = replace(item, content_hash=evidence_content_hash(item))
            candidate = replace(outcome, evidence=(*outcome.evidence, item), bindings=tuple(
                replace(b, evidence_hashes=(*b.evidence_hashes, item.content_hash)) for b in outcome.bindings
            ))
        verified = verify_episode_outcome(context.contract, candidate)
        assert verified.missing_outputs == ("metric_evidence",)
        assert not any("empty_hash" in issue for issue in verified.issues)


@pytest.mark.parametrize("ratio_request", [
    "请计算净现比。", "请计算两期的净现比。", "请测算各报告期净现比。",
    "经营活动现金流量净额/归母净利润是多少？",
])
def test_required_ratio_missing_is_local_and_optional_failure_is_not_contagious(monkeypatch, tmp_path, ratio_request):
    result, context = _tool_result(monkeypatch, tmp_path, query=QUESTION + ratio_request)
    failed = dc.to_tool_result(dc.CalculationError(dc.ERROR_SCRIPT_ERROR, "table() missing rows"))
    outcome = _outcome(context, result.evidence, kept_periods={"2026-06-30", "2026-03-31"})
    outcome = replace(outcome, events=(*outcome.events, EpisodeEvent(2, "tool_result", {
        "tool": "derived_calculation", "telemetry": failed.telemetry, "ok": False,
    })))
    verified = verify_episode_outcome(context.contract, outcome)
    assert verified.missing_outputs == ("metric_evidence",)
    assert verified.outcome.draft == outcome.draft
    no_ratio = _context(QUESTION)
    independent = replace(outcome, task_frame_hash=no_ratio.contract.task_frame_hash, events=(
        EpisodeEvent(1, "task", {"task_frame_hash": no_ratio.contract.task_frame_hash}),
        EpisodeEvent(2, "tool_result", {"tool": "derived_calculation", "ok": False}),
    ))
    assert verify_episode_outcome(no_ratio.contract, independent).verified_status == "completed"


@pytest.mark.parametrize("tool", ["memory_lookup", "finance_query", "web_fetch"])
def test_empty_lookup_is_not_a_calculation_error(tool):
    from intelligence.services.provider_observability import ProviderTrace
    observation = ToolObservation(
        tool=tool, query="无可用结果", evidence=(), observation="未取得可用内容",
        trace=ProviderTrace(provider="test", capability=tool, status="empty", result_count=0),
    )
    projected = FinanceResearchHarness().project_tool_result(
        observation, evidence_so_far=(), seen_prose=set(),
    )
    assert json.loads(projected.model_content)["ok"] is True


@pytest.mark.parametrize("query", [
    "截至2026-09-17，分析甲公司最近两期的收入、净利和经营现金流。",
    "截至2026-09-17，分析甲公司最近两份已披露的财务报告收入、净利。",
])
def test_equivalent_latest_pair_requests_do_not_allow_skipping_q1(monkeypatch, tmp_path, query):
    result, context = _tool_result(monkeypatch, tmp_path, query=query)
    outcome = _expanded(_outcome(context, result.evidence, kept_periods={"2026-06-30", "2025-12-31"}))
    assert verify_episode_outcome(context.contract, outcome).missing_outputs == ("metric_evidence",)


def test_same_episode_can_reuse_a_successful_calculation_without_disk_or_new_fetch(tmp_path):
    from intelligence.services.agent_research import AgentToolContext
    from intelligence.services.evidence_ledger import EvidenceLedger
    from intelligence.services.research_contract import ResearchDeadline
    from intelligence.services.research_tool_registry import parse_derived_calculation_arguments
    ledger = EvidenceLedger()
    ledger.append(AgentEvidence("financial_data", "财务", "收入40亿元", "测试源", content_hash="source"))
    loads = []
    def loader(calc_id):
        loads.append(calc_id)
        return None
    tool = dc.bind_derived_calculation_tool(evidence_ledger=ledger, calc_loader=loader)
    context = AgentToolContext(deadline=ResearchDeadline.from_timeout(30))
    first = tool.runner(parse_derived_calculation_arguments({
        "script": "emit_result(summary={'ratio': PARAMS.get('ratio', 0.5)})", "purpose": "净现比",
    })[0], context)
    record = first.telemetry["derived_calculation"]
    reused = tool.runner(parse_derived_calculation_arguments({
        "inputs_from_calc": record["calc_id"], "params": {"ratio": 0.6}, "purpose": "净现比",
    })[0], context)
    assert reused.evidence and reused.trace.status == "success"
    assert not loads
    assert reused.telemetry["derived_calculation"]["base_calc_id"] == record["calc_id"]
    assert not list(tmp_path.iterdir())
    # A different episode must not inherit this in-memory record.
    other = dc.bind_derived_calculation_tool(evidence_ledger=EvidenceLedger(), calc_loader=loader)
    absent = other.runner(parse_derived_calculation_arguments({
        "inputs_from_calc": record["calc_id"], "purpose": "净现比",
    })[0], context)
    assert not absent.evidence
    assert absent.telemetry["calculation_error"]["code"] == dc.ERROR_BASE_CALC_NOT_FOUND


def test_later_success_discharges_required_ratio_not_prior_error(monkeypatch, tmp_path):
    result, context = _tool_result(monkeypatch, tmp_path, query=QUESTION + "请计算净现比。")
    calc = dc.run_derived_calculation(
        script="emit_result(summary={'净现比': safe_div(5, 10)})", purpose="净现比核对", evidence=result.evidence,
    )
    assert isinstance(calc, dc.DerivedCalculation)
    product = dc.derived_evidence(calc)
    product = replace(product, content_hash=evidence_content_hash(product))
    outcome = _outcome(context, result.evidence, kept_periods={"2026-06-30", "2026-03-31"})
    outcome = replace(outcome, evidence=(*outcome.evidence, product), bindings=tuple(
        replace(b, evidence_hashes=(*b.evidence_hashes, product.content_hash)) for b in outcome.bindings
    ), events=(*outcome.events, EpisodeEvent(2, "tool_result", {
        "tool": "derived_calculation", "ok": False,
        "telemetry": {"calculation_error": {"code": dc.ERROR_SCRIPT_ERROR}},
    })))
    assert verify_episode_outcome(context.contract, outcome).verified_status == "completed"


@pytest.mark.parametrize("mode", ["llm", "off"])
@pytest.mark.parametrize("repair", [False, True])
def test_local_report_gap_survives_real_semantic_gate_and_bounded_resume(monkeypatch, tmp_path, mode, repair):
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
    from intelligence.services import llm_refine
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    from intelligence.services.episode_session import CallbackEpisodeSession
    from intelligence.services.research_contract import InMemoryRootBudgetLedger
    from intelligence.tests.test_continuous_turn_adapter import _control
    from intelligence.tests.test_episode_semantic_verifier import _judge
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    result, context = _tool_result(monkeypatch, tmp_path)
    context = replace(context, root_budget=InMemoryRootBudgetLedger(
        episode_id=context.contract.task_id, initial_calls=1, hard_calls_cap=1,
        initial_seconds=1, hard_seconds_cap=60,
    ), deadline=context.deadline.bounded_stage(0))  # research closed; expression repair only
    initial = _expanded(_outcome(context, result.evidence, kept_periods={"2026-06-30", "2025-12-31"}))
    goals, checks, structures = [], [], []
    def structural(contract, outcome):
        checked = verify_episode_outcome(contract, outcome)
        structures.append(checked)
        return checked
    class Runtime:
        def start(self, _frame, *, context, registry):
            def resume(previous, goal):
                goals.append(goal)
                assert goal.episode_id == context.contract.task_id
                assert goal.remaining_calls == 0 and not goal.reopen_tools
                draft = ("2026年中报与2026年一季报" if repair else "2026年中报与2025年报")
                draft += "收入和现金流累计期间长度不同，不能直接比较增长。"
                return replace(previous, draft=draft, stop_reason="repair_finish", events=(
                    *previous.events, EpisodeEvent(len(previous.events) + 1, "model_turn", {
                        "task_frame_hash": context.contract.task_frame_hash,
                    }),
                ))
            return CallbackEpisodeSession(
                episode_id=context.contract.task_id, outcome=initial, resume_callback=resume,
            )
    class Verifier(SemanticEpisodeVerifier):
        def verify(self, **kwargs):
            checked = super().verify(**kwargs)
            checks.append(checked)
            return checked
    public = ContinuousTurnAdapter(
        runtime=Runtime(), mode="on", context_factory=lambda *_a, **_k: context,
        registry_factory=lambda *_a, **_k: "registry",
        structural_verifier=structural, semantic_verifier=Verifier(judge_fn=_judge(True)),
    ).handle(frame=_frame(), control=_control(_frame()))
    # This gap arises structurally: repair + structural recheck precede the
    # first semantic pass (unlike R4's post-semantic deletion/repair cycle).
    assert len(goals) == 1 and len(checks) == 1
    assert len(structures) >= 2 and structures[0].missing_outputs == ("metric_evidence",)
    assert "metric_evidence" in goals[0].missing_answer_elements
    assert public.status == ("completed" if repair else "partial"), public.private_artifact
    assert "不能直接比较增长" in public.answer
    assert checks[-1].verified.missing_outputs == (() if repair else ("metric_evidence",))
    assert bool(public.open_gaps) is not repair
    assert context.root_budget.allocated_calls == 1


def test_actual_episode_exposes_error_then_success_to_model_and_audit(monkeypatch, tmp_path):
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.research_tool_registry import ToolRunResult, default_registry
    from intelligence.tests.test_derived_calculation import _ArgScriptedModel
    result, context = _tool_result(monkeypatch, tmp_path)
    tool_result = ToolRunResult(evidence=result.evidence, observation=result.observation,
                                trace=result.trace, gaps=result.gaps, telemetry=result.telemetry)
    registry = default_registry({"financial_data": lambda *_: tool_result})
    good_script = (
        "values = ratio_series(series('300308.SZ', 'ocf_cum_yi'), series('300308.SZ', 'net_profit_cum_yi'))\n"
        "emit_result(tables=[table('净现比', ['报告期', '净现比'], "
        "[[v['as_of'], v['ratio']] for v in values])])"
    )
    finish = json.dumps({
        "status": "completed", "draft": "2026中报与2026一季报的收入和现金流，累计长度不同不能直接环比。",
        "gaps": [], "bindings": [
            {"output_id": o.output_id, "evidence_hashes": ["E1", "E13"], "basis": "evidence"}
            for o in context.contract.required_outputs
        ],
    }, ensure_ascii=False)
    seen = []
    class Model(_ArgScriptedModel):
        def complete(self, *, messages, tools, timeout):
            seen.extend(json.loads(m["content"]) for m in messages if m.get("role") == "tool")
            return super().complete(messages=messages, tools=tools, timeout=timeout)
    model = Model([
        ((("financial_data", {}),), ""),
        ((("derived_calculation", {"script": "emit_result(tables=[table(title='x')])", "purpose": "净现比"}),), ""),
        ((("derived_calculation", {"script": good_script, "purpose": "净现比"}),), ""),
        ((), finish),
    ])
    outcome = ContinuousAgentEpisode(model).run(task_frame=_frame(), context=context, registry=registry)
    calc_events = [e for e in outcome.events if e.kind == "tool_result" and e.payload.get("tool") == "derived_calculation"]
    assert len(calc_events) == 2
    assert [e.payload["ok"] for e in calc_events] == [False, True]
    assert any(p.get("error") == dc.ERROR_SCRIPT_ERROR and p["ok"] is False for p in seen)
    assert any(p.get("tool") == "derived_calculation" and p["ok"] is True and p["evidence"] for p in seen)
    assert all("telemetry" not in p for p in seen)
    assert outcome.usage.tool_calls == 3
    assert verify_episode_outcome(context.contract, outcome).verified_status == "completed"
    assert sum(e.tool == "derived_calculation" for e in outcome.evidence) == 1


@pytest.mark.parametrize("matching", [False, True])
def test_calculation_id_must_refer_to_a_bound_product(monkeypatch, tmp_path, matching):
    result, context = _tool_result(monkeypatch, tmp_path)
    calc = dc.run_derived_calculation(script="emit_result(summary={'ratio': 0.5})", purpose="净现比", evidence=result.evidence)
    assert isinstance(calc, dc.DerivedCalculation)
    item = dc.derived_evidence(calc)
    item = replace(item, content_hash=evidence_content_hash(item))
    outcome = _outcome(context, result.evidence, kept_periods={"2026-06-30", "2026-03-31"})
    outcome = replace(outcome, draft=outcome.draft + f"计算编号 {calc.calc_id if matching else '0123456789abcdef'}。",
        evidence=(*outcome.evidence, item), bindings=tuple(
            replace(b, evidence_hashes=(*b.evidence_hashes, item.content_hash)) for b in outcome.bindings
        ))
    verified = verify_episode_outcome(context.contract, outcome)
    assert verified.missing_outputs == (() if matching else ("metric_evidence",))


def test_explicitly_waived_ratio_does_not_require_calculator(monkeypatch, tmp_path):
    result, context = _tool_result(monkeypatch, tmp_path, query=QUESTION + "不要计算净现比。")
    outcome = _outcome(context, result.evidence, kept_periods={"2026-06-30", "2026-03-31"})
    assert verify_episode_outcome(context.contract, outcome).verified_status == "completed"


@pytest.mark.parametrize("query, expected", [
    ("截至2026-09-17，信息截止日为2026年9月17日。", date(2026, 9, 17)),
    ("截至2026-09-17；信息截止日为2026年9月16日。", None),
    ("截至2026-09-17至2026-09-18的行情。", None),
    ("分析材料：\n```\n以2026年9月17日为信息截止点。\n```", None),
])
def test_cutoff_conflicts_equivalence_and_material_boundaries(query, expected):
    result = requested_information_cutoff(query, today="2026-09-18")
    assert (result.as_of_date if result else None) == expected


def test_candidate_with_no_numeric_fields_cannot_disappear_from_recent_pair(monkeypatch, tmp_path):
    rows = _rows()
    rows[1] = mf.QuarterFinancials("2026一季报", "2026-03-31", notice_date="2026-04-25")
    result, context = _tool_result(monkeypatch, tmp_path, rows=rows)
    outcome = _outcome(context, result.evidence, kept_periods={"2026-06-30", "2025-12-31"})
    outcome = replace(outcome, events=(*outcome.events, EpisodeEvent(2, "tool_result", {
        "tool": "financial_data", "telemetry": result.telemetry,
    })))
    verified = verify_episode_outcome(context.contract, outcome)
    assert verified.missing_outputs == ("metric_evidence",)
    assert "2026-03-31" in verified.completion.outputs[1].gap


def test_known_post_cutoff_report_does_not_block_eligible_pair(monkeypatch, tmp_path):
    rows = _rows()
    rows[0] = replace(rows[0], notice_date="2026-09-19")
    result, context = _tool_result(monkeypatch, tmp_path, rows=rows)
    outcome = _outcome(context, result.evidence, kept_periods={"2026-03-31", "2025-12-31"})
    outcome = replace(outcome, events=(*outcome.events, EpisodeEvent(2, "tool_result", {
        "tool": "financial_data", "telemetry": result.telemetry,
    })))
    assert verify_episode_outcome(context.contract, outcome).verified_status == "completed"


@pytest.mark.parametrize("conflict", [False, True])
def test_duplicate_period_rows_do_not_silently_pick_one_disclosure(monkeypatch, tmp_path, conflict):
    rows = _rows()
    rows.append(replace(rows[1], revenue_yi=19) if conflict else rows[1])
    result, context = _tool_result(monkeypatch, tmp_path, rows=rows)
    outcome = _expanded(_outcome(context, result.evidence, kept_periods={"2026-06-30", "2026-03-31"}))
    outcome = replace(outcome, events=(*outcome.events, EpisodeEvent(2, "tool_result", {
        "tool": "financial_data", "telemetry": result.telemetry,
    })))
    verified = verify_episode_outcome(context.contract, outcome)
    assert verified.missing_outputs == (("metric_evidence",) if conflict else ())
    if conflict:
        assert "conflicting_report_rows" in verified.completion.outputs[1].gap
        assert all(o.as_of != "2026-03-31" for e in result.evidence for o in e.observations)
    else:
        assert len(result.evidence) == 12


def test_financial_metric_is_not_downgraded_by_exhausted_tool_budget():
    from intelligence.services.mandatory_satisfiability import evidence_required_output_ids
    context = _context()
    assert "metric_evidence" not in evidence_required_output_ids(context.contract)
    assert next(o for o in context.contract.required_outputs if o.output_id == "metric_evidence").required


@pytest.mark.parametrize("code", [
    dc.ERROR_NO_BOUND_EVIDENCE, dc.ERROR_SCRIPT_REJECTED, dc.ERROR_SANDBOX_VIOLATION,
    dc.ERROR_NO_RESULT, dc.ERROR_SANDBOX_UNAVAILABLE,
])
def test_other_calculation_failures_remain_distinct_and_empty(code):
    projection = _project(dc.to_tool_result(dc.CalculationError(code, "未产出")))
    model = json.loads(projection.model_content)
    assert model["error"] == code and model["ok"] is False
    assert model["gaps"] and not model["evidence"]


def test_complete_rows_have_labeled_metrics_in_model_budget(monkeypatch, tmp_path):
    result, _ = _tool_result(monkeypatch, tmp_path)
    projection = FinanceResearchHarness().project_tool_result(result, evidence_so_far=result.evidence, seen_prose=set())
    model = json.loads(projection.model_content)
    assert "2026-06-30、2026-03-31" in model["observation"]
    assert len(model["evidence"]) == 12
    assert all("甲公司" in e["title"] for e in model["evidence"])
    assert sum(mf.METRIC_GLOSSARY["ocf_cum_yi"] in e["detail"] for e in model["evidence"]) == 6
    assert all(e["source_date"] <= "2026-09-17" for e in model["evidence"])
    assert "telemetry" not in model

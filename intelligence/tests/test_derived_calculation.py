"""``derived_calculation``：产物协议、三条契约、admit_finish 门、跨源口径核对端到端。

对应 spec capability-amplification §5 第 16–18 条：
16. 产物无 ``input_evidence_hashes`` → 绑定它的结论句被驳回（有牙）。
17. ``as_of`` 取输入最旧值。
18. 跨源口径核对用例端到端跑通，产物哈希链完整。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services import derived_calculation as dc
from intelligence.services.agent_research import (
    AgentEvidence,
    AgentToolContext,
    StructuredObservation,
    evidence_content_hash,
)
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_protocol import (
    EpisodeFinishRejection,
    validate_episode_finish,
)
from intelligence.services.evidence_capabilities import (
    EvidencePlan,
    runtime_capabilities_for_frame,
)
from intelligence.services.evidence_ledger import EvidenceLedger
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    InvalidResearchToolArguments,
    ResearchToolRegistry,
    ToolSpec,
    default_registry,
    parse_derived_calculation_arguments,
)
from intelligence.services.task_frame import TaskFrame

RECONCILE_SCRIPT = (
    "annual = [e for e in EVIDENCE if e['tool'] == 'financial_data'][0]\n"
    "web = [e for e in EVIDENCE if e['tool'] == 'web_fetch'][0]\n"
    "a = annual['observations'][0]['value']\n"
    "b = web['observations'][0]['value']\n"
    "diff = round(a - b, 2)\n"
    "emit({'annual_report': a, 'web_page': b, 'diff': diff,\n"
    "      'pct_diff': round(diff / a * 100, 4), 'consistent': abs(diff) < 0.01,\n"
    "      'inputs': [annual['ref'], web['ref']]})\n"
)


def _stamp(item: AgentEvidence) -> AgentEvidence:
    from dataclasses import replace

    return replace(item, content_hash=evidence_content_hash(item))


def _annual_report() -> AgentEvidence:
    return _stamp(
        AgentEvidence(
            tool="financial_data",
            title="贵州茅台 2024 年报",
            detail="2024-12-31 归母净利润 1741.44 亿元（披露日 2025-04-03）",
            source="F10 财务指标",
            source_date="2025-04-03",
            evidence_tier="L2_structured",
            observations=(
                StructuredObservation(
                    subject="600519", as_of="2025-04-03", metric="net_profit", value=1741.44
                ),
            ),
        )
    )


def _web_page() -> AgentEvidence:
    return _stamp(
        AgentEvidence(
            tool="web_fetch",
            title="某财经网页：茅台 2024 年净利润",
            detail="网页称 2024 年净利润约 1740 亿元",
            source="https://example.invalid/maotai-2024",
            source_date="2025-05-01",
            evidence_tier="public_web",
            observations=(
                StructuredObservation(
                    subject="600519", as_of="2025-05-01", metric="net_profit", value=1740.0
                ),
            ),
        )
    )


def _inputs() -> tuple[AgentEvidence, AgentEvidence]:
    return _annual_report(), _web_page()


def _run(script: str = RECONCILE_SCRIPT, **kwargs):
    kwargs.setdefault("evidence", _inputs())
    kwargs.setdefault("purpose", "核对 2024 年报净利润两个来源是否一致")
    return dc.run_derived_calculation(script=script, **kwargs)


# ── 协议：as_of 继承 / 输入哈希链 / calc_id ────────────────────────────


def test_as_of_is_the_oldest_input_not_the_run_date() -> None:
    """§5 第 17 条：两条不同 as_of 的输入，产物取旧的那条。"""

    assert dc.oldest_as_of(_inputs()) == "2025-04-03"
    assert dc.oldest_as_of((_web_page(), _annual_report())) == "2025-04-03"
    undated = AgentEvidence(tool="kb_search", title="t", detail="d", source="s", content_hash="x")
    assert dc.oldest_as_of((undated,)) is None

    calc = _run()
    assert isinstance(calc, dc.DerivedCalculation)
    assert calc.as_of == "2025-04-03"


def test_product_carries_script_inputs_and_result() -> None:
    annual, web = _inputs()
    calc = _run()

    assert isinstance(calc, dc.DerivedCalculation)
    assert calc.script == RECONCILE_SCRIPT
    assert calc.input_evidence_hashes == (annual.content_hash, web.content_hash)
    assert calc.input_refs == ("E1", "E2")
    assert calc.result["diff"] == 1.44
    assert calc.result["consistent"] is False
    assert calc.result["inputs"] == ["E1", "E2"]
    assert calc.enforcement in {"seatbelt+process", "process"}
    assert calc.to_dict()["input_evidence_hashes"] == list(calc.input_evidence_hashes)


def test_calc_id_is_deterministic_and_sensitive_to_script_and_inputs() -> None:
    annual, web = _inputs()
    hashes = (annual.content_hash, web.content_hash)

    same = dc.compute_calc_id(RECONCILE_SCRIPT, hashes)
    assert same == dc.compute_calc_id(RECONCILE_SCRIPT, tuple(reversed(hashes)))
    assert same != dc.compute_calc_id(RECONCILE_SCRIPT + "\n# changed", hashes)
    assert same != dc.compute_calc_id(RECONCILE_SCRIPT, hashes[:1])
    assert same != dc.compute_calc_id(RECONCILE_SCRIPT, hashes, db_fingerprint_value="db:1:2")
    first = _run()
    second = _run()
    assert isinstance(first, dc.DerivedCalculation) and isinstance(second, dc.DerivedCalculation)
    assert first.calc_id == second.calc_id == same


# ── 契约①：空结果语义——计算没产出不是任何数值 ─────────────────────────


def test_no_bound_evidence_is_refused_before_running_anything() -> None:
    error = _run(evidence=())

    assert isinstance(error, dc.CalculationError)
    assert error.code == dc.ERROR_NO_BOUND_EVIDENCE
    assert not error.retryable_by_rewriting
    observation = dc.error_observation(error)
    assert "no_bound_evidence" in observation and "不能当否定证据" in observation


@pytest.mark.parametrize(
    ("script", "code", "needle"),
    [
        ("import socket\nemit({})", dc.ERROR_SCRIPT_REJECTED, "forbidden_import:socket"),
        ("x = 1\n", dc.ERROR_NO_RESULT, "emit"),
        ("raise ValueError('boom')\n", dc.ERROR_SCRIPT_ERROR, "ValueError: boom"),
        ("open('/etc/derived-calc-escape', 'w')\nemit({})", dc.ERROR_SANDBOX_VIOLATION, "write outside workdir"),
    ],
)
def test_failed_calculations_come_back_as_structured_errors(script: str, code: str, needle: str) -> None:
    error = _run(script)

    assert isinstance(error, dc.CalculationError)
    assert error.code == code
    assert needle in error.detail
    assert error.retryable_by_rewriting
    result = dc.to_tool_result(error)
    assert result.evidence == ()
    assert result.trace.status == "error"
    assert code in result.trace.detail
    assert code in result.observation


def test_timeout_is_its_own_error_and_trace_status() -> None:
    error = _run("while True:\n    pass\n", timeout=1)

    assert isinstance(error, dc.CalculationError)
    assert error.code == dc.ERROR_SANDBOX_TIMEOUT
    assert dc.to_tool_result(error).trace.status == "timeout"


def test_missing_duckdb_snapshot_is_reported_not_silently_empty(tmp_path) -> None:
    error = _run("emit({})", use_duckdb=True, db_path=tmp_path / "missing.duckdb")

    assert isinstance(error, dc.CalculationError)
    assert error.code == dc.ERROR_SANDBOX_UNAVAILABLE


# ── 契约②：来源分档与 as_of 来源 ─────────────────────────────────────


def test_derived_evidence_is_tiered_dated_and_chained_to_inputs() -> None:
    annual, web = _inputs()
    calc = _run()
    assert isinstance(calc, dc.DerivedCalculation)

    item = dc.derived_evidence(calc)
    assert item.tool == "derived_calculation"
    assert item.evidence_tier == dc.DERIVED_CALCULATION_TIER
    assert item.source_date == "2025-04-03"
    assert item.derived_from == (annual.content_hash, web.content_hash)
    assert item.source == f"sandbox:{calc.calc_id}"
    assert "E1、E2" in item.detail and "取输入最旧" in item.detail
    metrics = {obs.metric: obs.value for obs in item.observations}
    assert metrics["diff"] == 1.44 and "consistent" not in metrics
    assert "enforcement" not in item.detail
    observation = dc.success_observation(calc)
    assert "不是今天" in observation and f"enforcement={calc.enforcement}" in observation


def test_registry_contract_states_all_three_clauses() -> None:
    spec = default_registry({"derived_calculation": lambda *_: None}).resolve("derived_calculation")

    assert spec.replay == "safe"
    assert spec.produces == frozenset({"supporting_evidence"})
    assert "不高于输入里最低的那一档" in spec.contract
    assert "最旧的 as_of" in spec.contract
    assert "no_bound_evidence" in spec.contract
    assert "不能联网" in spec.contract
    # 工单 04 加了 params（假设）与 inputs_from_calc（沿用上一轮输入）；script 只在沿用时可省。
    assert set(spec.parameters["properties"]) == {
        "script",
        "purpose",
        "use_duckdb",
        "timeout_seconds",
        "params",
        "inputs_from_calc",
    }
    assert list(spec.parameters["required"]) == ["purpose"]
    assert "emit_result" in spec.contract and "inputs_from_calc" in spec.contract


# ── 契约③：参数含义与拒绝条件 ───────────────────────────────────────


def test_argument_parser_reads_every_key_and_rejects_the_rest() -> None:
    payload, display = parse_derived_calculation_arguments(
        {"script": "emit({})", "purpose": " 核对 ", "use_duckdb": True, "timeout_seconds": 5}
    )
    assert json.loads(payload) == {
        "script": "emit({})",
        "purpose": "核对",
        "use_duckdb": True,
        "timeout_seconds": 5,
    }
    assert display == "核对"
    assert json.loads(parse_derived_calculation_arguments({"script": "x", "purpose": "p"})[0])[
        "timeout_seconds"
    ] == 20

    for bad in (
        {"script": "", "purpose": "p"},
        {"script": "x", "purpose": "  "},
        {"script": "x", "purpose": "p", "extra": 1},
        {"script": "x", "purpose": "p", "use_duckdb": "yes"},
        {"script": "x", "purpose": "p", "timeout_seconds": 0},
        {"script": "x", "purpose": "p", "timeout_seconds": 61},
        {"script": "x", "purpose": "p", "timeout_seconds": True},
    ):
        with pytest.raises(InvalidResearchToolArguments):
            parse_derived_calculation_arguments(bad)


def test_bound_tool_reads_the_ledger_at_call_time_and_honours_the_window() -> None:
    ledger = EvidenceLedger()
    spec = dc.bind_derived_calculation_tool(evidence_ledger=ledger)
    assert spec.name == "derived_calculation" and spec.contract
    context = AgentToolContext(deadline=ResearchDeadline.from_timeout(30.0))
    args, _display = parse_derived_calculation_arguments(
        {"script": RECONCILE_SCRIPT, "purpose": "核对净利润"}
    )

    empty = spec.runner(args, context)
    assert empty.evidence == () and dc.ERROR_NO_BOUND_EVIDENCE in empty.trace.detail

    ledger.append(_inputs())
    result = spec.runner(args, context)
    assert result.trace.status == "success"
    (item,) = result.evidence
    assert item.derived_from == tuple(ledger.snapshot().evidence_ids)
    assert item.source_date == "2025-04-03"


def test_capability_is_derived_from_financial_data_only() -> None:
    financial = TaskFrame(
        raw_question="贵州茅台2024年净利润多少",
        user_goal="查财务数据",
        question_type="financial_analysis",
        subject="贵州茅台",
        subject_kind="company",
        market_scope="A股",
        timeframe="2024年报",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_financial_evidence",
        confidence=0.9,
    )
    market = TaskFrame(
        raw_question="今天大盘怎么看",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.9,
    )
    with_financials = runtime_capabilities_for_frame(financial)
    without = runtime_capabilities_for_frame(market)

    assert "financial_data" in with_financials and "derived_calculation" in with_financials
    assert with_financials.count("derived_calculation") == 1
    assert "financial_data" not in without and "derived_calculation" not in without


# ── §5 第 16 条：admit_finish 门有牙 ────────────────────────────────────


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="贵州茅台 2024 年净利润两个来源是否一致",
        user_goal="核对口径",
        question_type="market_forecast",
        subject="贵州茅台",
        subject_kind="company",
        market_scope="A股",
        timeframe="2024年报",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_financial_evidence",
        confidence=0.9,
    )


def _context(frame: TaskFrame, *, task_id: str = "derived-calc-test") -> ResearchRunContext:
    return ResearchRunContext(
        contract=ResearchTaskContract(
            task_id=task_id,
            question=frame.raw_question,
            subject=frame.subject,
            subject_kind=frame.subject_kind,
            question_type=frame.question_type,
            required_outputs=(
                RequiredOutput("direct_assessment", "直接判断", ("financial_data",), True),
            ),
            allowed_capabilities=("financial_data", "web_fetch", "derived_calculation"),
            research_tier="quick",
            freshness="current",
            evidence_plan=EvidencePlan(),
            task_frame_hash=frame.task_frame_hash,
        ),
        deadline=ResearchDeadline.from_timeout(60.0),
        policy=ResearchPolicy("quick", 4, 60.0, 0.0),
        trace_parent_id=task_id,
        today="2026-09-08",
        latest_data_date="2026-09-05",
    )


def _finish(*refs: str) -> str:
    return json.dumps(
        {
            "status": "completed",
            "draft": "两个来源的 2024 年归母净利润相差 1.44 亿元（0.08%），口径不一致；以年报一手数 1741.44 亿元为准。",
            "gaps": [],
            "bindings": [
                {"output_id": "direct_assessment", "evidence_hashes": list(refs), "basis": "evidence"}
            ],
        },
        ensure_ascii=False,
    )


def _derived(with_inputs: bool) -> AgentEvidence:
    calc = _run()
    assert isinstance(calc, dc.DerivedCalculation)
    item = dc.derived_evidence(calc)
    if not with_inputs:
        from dataclasses import replace

        item = replace(item, derived_from=())
    return _stamp(item)


def test_finish_bound_to_derived_evidence_without_inputs_is_rejected_as_integrity() -> None:
    frame = _frame()
    context = _context(frame)
    annual, web = _inputs()

    with pytest.raises(EpisodeFinishRejection) as rejected:
        validate_episode_finish(
            _finish("E1", "E2", "E3"),
            context=context,
            evidence=(annual, web, _derived(with_inputs=False)),
        )
    assert rejected.value.code == "derived_without_inputs"
    assert rejected.value.kind.value == "integrity"

    accepted = validate_episode_finish(
        _finish("E1", "E2", "E3"),
        context=context,
        evidence=(annual, web, _derived(with_inputs=True)),
    )
    assert accepted.status == "completed"


# ── §5 第 18 条：跨源口径核对端到端 ───────────────────────────────────


class _ArgScriptedModel:
    """带任意参数字典的脚本化模型：conformance 的 ScriptedToolCall 只会传 query。"""

    def __init__(self, turns: Sequence[tuple[Sequence[tuple[str, Mapping[str, object]]], str]]) -> None:
        self._turns = list(turns)
        self._sequence = 0
        self.visible_tools: list[tuple[str, ...]] = []

    def complete(self, *, messages, tools, timeout) -> ModelTurn:
        del messages, timeout
        self.visible_tools.append(
            tuple(sorted(str(item["function"]["name"]) for item in tools if "function" in item))
        )
        if not self._turns:
            return ModelTurn("", (), "scripted", "scripted_turns_exhausted")
        calls, content = self._turns.pop(0)
        rendered = []
        for name, arguments in calls:
            self._sequence += 1
            rendered.append(ModelToolCall(f"call-{self._sequence}", name, dict(arguments)))
        return ModelTurn(content=content, tool_calls=tuple(rendered), provider_name="scripted")


def _fixture_registry() -> ResearchToolRegistry:
    def financial_runner(query: str, _context: AgentToolContext):
        item = _annual_report()
        return (
            [item],
            f"{query}：2024 年报归母净利润 1741.44 亿元（披露日 2025-04-03）",
            ProviderTrace(provider="test:financial", capability="financial_data", status="success", result_count=1),
        )

    def web_runner(query: str, _context: AgentToolContext):
        item = _web_page()
        return (
            [item],
            f"{query}：网页称 2024 年净利润约 1740 亿元",
            ProviderTrace(provider="test:web", capability="web_fetch", status="success", result_count=1),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="financial_data",
                capability="financial_data",
                description="财务数据",
                cost="local",
                freshness="current",
                runner=financial_runner,
            ),
            ToolSpec(
                name="web_fetch",
                capability="web_fetch",
                description="取页",
                cost="external",
                freshness="current",
                runner=web_runner,
            ),
        )
    )


def test_cross_source_reconciliation_end_to_end_keeps_the_hash_chain() -> None:
    frame = _frame()
    context = _context(frame, task_id="derived-calc-e2e")
    model = _ArgScriptedModel(
        [
            (
                (
                    ("financial_data", {"query": "600519 2024 年报 净利润"}),
                    ("web_fetch", {"query": "茅台 2024 净利润 网页"}),
                ),
                "",
            ),
            (
                (
                    (
                        "derived_calculation",
                        {"script": RECONCILE_SCRIPT, "purpose": "核对 2024 年报净利润两个来源是否一致"},
                    ),
                ),
                "",
            ),
            ((), _finish("E1", "E2", "E3")),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame, context=context, registry=_fixture_registry()
    )

    assert outcome.status == "completed", (outcome.stop_reason, outcome.gaps)
    assert all("derived_calculation" in visible for visible in model.visible_tools)
    annual, web = _inputs()
    derived = [item for item in outcome.evidence if item.tool == "derived_calculation"]
    assert len(derived) == 1
    (item,) = derived
    assert set(item.derived_from) == {annual.content_hash, web.content_hash}
    assert item.source_date == "2025-04-03"
    assert item.evidence_tier == dc.DERIVED_CALCULATION_TIER
    (binding,) = outcome.bindings
    assert item.content_hash in binding.evidence_hashes
    assert set(binding.evidence_hashes) >= {annual.content_hash, web.content_hash}
    results = [event for event in outcome.events if event.kind == "tool_result"]
    derived_results = [event for event in results if event.payload.get("tool") == "derived_calculation"]
    assert len(derived_results) == 1
    # 模型看到的正文里带计算编号（工单 04 起写作「计算编号 <id>」，放在结果之前不被预算截掉）。
    assert f"计算编号 {item.source.removeprefix('sandbox:')}" in str(
        derived_results[0].payload.get("model_content", "")
    )


# ── 工单 04：结果协议 v1 / 参数 / 沿用输入 / 产物数据通路 ─────────────────

STRUCTURED_SCRIPT = (
    "annual = observations(tool='financial_data')[0]['value']\n"
    "web = observations(tool='web_fetch')[0]['value']\n"
    "rows = [[r['ref'], r['value']] for r in observations()]\n"
    "t = table('净利润两源核对', ['来源', '净利润(亿)'], rows, unit='亿元')\n"
    "emit_result(summary={'diff': round(annual - web, 2), 'tolerance_pct': PARAMS.get('tolerance_pct')},\n"
    "            tables=[t], formulas=['diff = 年报 − 网页'], notes=['两源口径均为归母净利润'])\n"
)


def test_structured_result_puts_every_table_number_into_observations_and_telemetry() -> None:
    calc = _run(STRUCTURED_SCRIPT, params={"tolerance_pct": 0.1})
    assert isinstance(calc, dc.DerivedCalculation), calc

    assert calc.result["schema"] == "derived_calculation.result/v1"
    assert calc.params == {"tolerance_pct": 0.1}
    assert calc.artifact_names == (
        f"calc-{calc.calc_id}.json",
        f"calc-{calc.calc_id}.html",
        f"calc-{calc.calc_id}-t1.csv",
    )
    item = dc.derived_evidence(calc)
    metrics = {obs.metric: obs.value for obs in item.observations}
    assert metrics["diff"] == 1.44
    assert metrics["净利润两源核对.净利润(亿)[E1]"] == 1741.44
    assert metrics["净利润两源核对.净利润(亿)[E2]"] == 1740.0
    assert f"计算编号 {calc.calc_id}" in item.detail
    observation = dc.success_observation(calc)
    assert "E1: 净利润(亿)=1741.44" in observation
    assert f"calc-{calc.calc_id}-t1.csv" in observation and "inputs_from_calc" in observation
    # 模型视图上限 900 字符（tool_result_budget）：编号与产物名在前，整段不越界。
    assert len(observation) <= 900, len(observation)
    assert observation.index(f"计算编号 {calc.calc_id}") < observation.index("E1: 净利润")
    detail = dc.derived_evidence(calc).detail
    assert detail.index(f"计算编号 {calc.calc_id}") < 240

    result = dc.to_tool_result(calc)
    record = result.telemetry["derived_calculation"]
    assert record["calc_id"] == calc.calc_id
    assert record["artifacts"] == list(calc.artifact_names)
    assert record["params"] == {"tolerance_pct": 0.1}
    assert [entry["ref"] for entry in record["inputs"]] == ["E1", "E2"]
    assert all("detail" not in entry and entry["observations"] for entry in record["inputs"])


def test_params_change_the_calc_id_but_not_the_input_chain() -> None:
    base = _run(STRUCTURED_SCRIPT)
    tuned = _run(STRUCTURED_SCRIPT, params={"tolerance_pct": 0.5})
    assert isinstance(base, dc.DerivedCalculation) and isinstance(tuned, dc.DerivedCalculation)

    assert base.calc_id != tuned.calc_id
    assert base.input_evidence_hashes == tuned.input_evidence_hashes
    assert dc.compute_calc_id("s", ("h",)) != dc.compute_calc_id("s", ("h",), params_json='{"a": 1}')
    assert dc.canonical_params({"b": 1, "a": 2}) == '{"a": 2, "b": 1}'
    assert dc.canonical_params({}) == "" and dc.canonical_params(None) == ""


def test_reusing_a_prior_calculation_keeps_its_inputs_script_and_hash_chain(tmp_path) -> None:
    prior = _run(STRUCTURED_SCRIPT, params={"tolerance_pct": 0.1})
    assert isinstance(prior, dc.DerivedCalculation)
    record = prior.to_dict()
    run_dir = tmp_path / "run_20260909_abc"
    run_dir.mkdir()
    (run_dir / f"calc-{prior.calc_id}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    assert dc.load_calculation_record(prior.calc_id, runs_root=tmp_path)["calc_id"] == prior.calc_id
    assert dc.load_calculation_record("0" * 16, runs_root=tmp_path) is None
    assert dc.load_calculation_record("not-an-id", runs_root=tmp_path) is None

    # 新一轮：账本为空，只靠沿用；不传 script，只改一个参数。
    spec = dc.bind_derived_calculation_tool(
        evidence_ledger=EvidenceLedger(),
        calc_loader=lambda calc_id: dc.load_calculation_record(calc_id, runs_root=tmp_path),
    )
    context = AgentToolContext(deadline=ResearchDeadline.from_timeout(30.0))
    args, _display = parse_derived_calculation_arguments(
        {"purpose": "改容差重算", "inputs_from_calc": prior.calc_id, "params": {"tolerance_pct": 1.0}}
    )
    result = spec.runner(args, context)
    assert result.trace.status == "success", result.observation
    (item,) = result.evidence
    annual, web = _inputs()
    assert set(item.derived_from) == {annual.content_hash, web.content_hash}
    assert item.source_date == "2025-04-03"
    record = result.telemetry["derived_calculation"]
    assert record["base_calc_id"] == prior.calc_id
    assert record["params"] == {"tolerance_pct": 1.0}
    assert record["input_refs"] == ["P1", "P2"]
    assert record["script"] == STRUCTURED_SCRIPT
    assert record["calc_id"] != prior.calc_id
    assert f"沿用计算 {prior.calc_id}" in result.observation

    missing = spec.runner(
        parse_derived_calculation_arguments({"purpose": "p", "inputs_from_calc": "f" * 16})[0],
        context,
    )
    assert missing.evidence == ()
    assert dc.ERROR_BASE_CALC_NOT_FOUND in missing.trace.detail
    assert "计算编号" in missing.observation


def test_argument_parser_accepts_params_and_reuse_and_rejects_bad_shapes() -> None:
    payload, display = parse_derived_calculation_arguments(
        {"purpose": "重算", "inputs_from_calc": "0123456789abcdef", "params": {"g": 5}}
    )
    assert json.loads(payload) == {
        "script": "",
        "purpose": "重算",
        "use_duckdb": False,
        "timeout_seconds": 20,
        "params": {"g": 5},
        "inputs_from_calc": "0123456789abcdef",
    }
    assert display == "重算"
    assert "params" not in json.loads(parse_derived_calculation_arguments({"script": "x", "purpose": "p"})[0])

    for bad in (
        {"purpose": "p"},  # 没 script 也没沿用
        {"script": "", "purpose": "p", "inputs_from_calc": "0123456789abcdef"},  # 传了空脚本
        {"script": "x", "purpose": "p", "inputs_from_calc": "nope"},
        {"script": "x", "purpose": "p", "params": [1, 2]},
        {"script": "x", "purpose": "p", "params": {"k": object()}},
    ):
        with pytest.raises(InvalidResearchToolArguments):
            parse_derived_calculation_arguments(bad)


def test_end_to_end_structured_calculation_reaches_the_run_artifacts() -> None:
    """数据通路全程：脚本 emit_result → 派生证据 → tool_result 事件 telemetry → durable 投影 →
    ``publish_calculation_artifacts`` 落成 run 产物。中间任何一环丢字段，这条就红。"""

    from intelligence.services import derived_calculation_artifacts as art
    from intelligence.services.episode_projection import project_durable_events

    frame = _frame()
    context = _context(frame, task_id="derived-calc-artifacts-e2e")
    model = _ArgScriptedModel(
        [
            (
                (
                    ("financial_data", {"query": "600519 2024 年报 净利润"}),
                    ("web_fetch", {"query": "茅台 2024 净利润 网页"}),
                ),
                "",
            ),
            (
                (
                    (
                        "derived_calculation",
                        {
                            "script": STRUCTURED_SCRIPT,
                            "purpose": "核对 2024 年报净利润两个来源是否一致",
                            "params": {"tolerance_pct": 0.1},
                        },
                    ),
                ),
                "",
            ),
            ((), _finish("E1", "E2", "E3")),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=_fixture_registry())
    assert outcome.status == "completed", (outcome.stop_reason, outcome.gaps)

    projection = project_durable_events(outcome.events)
    private_artifact = {"events": list(projection.events)}
    records = art.calc_records_from_private_artifact(private_artifact)
    assert len(records) == 1
    (record,) = records
    assert record["params"] == {"tolerance_pct": 0.1}
    assert record["result"]["tables"][0]["name"] == "净利润两源核对"
    # 完整记录只在审计底稿（telemetry），模型可见正文里没有它——脚本正文与输入快照不进上下文。
    tool_events = [event for event in outcome.events if event.kind == "tool_result" and event.payload.get("tool") == "derived_calculation"]
    model_content = str(tool_events[0].payload.get("model_content"))
    assert "telemetry" not in model_content and "input_evidence_hashes" not in model_content
    assert STRUCTURED_SCRIPT.splitlines()[0] not in model_content
    assert tool_events[0].payload["telemetry"]["derived_calculation"]["calc_id"] == record["calc_id"]

    class FakeStore:
        def __init__(self) -> None:
            self.files: dict[str, str] = {}

        def add_artifact(self, run_id, filename, content, *, renderer, title, **_kwargs):
            self.files[filename] = content
            return filename

    store = FakeStore()
    written = art.publish_calculation_artifacts(store, "run-e2e", private_artifact)
    calc_id = record["calc_id"]
    assert written == [f"calc-{calc_id}.json", f"calc-{calc_id}.html", f"calc-{calc_id}-t1.csv"]
    assert "E1,1741.44" in store.files[f"calc-{calc_id}-t1.csv"]
    assert json.loads(store.files[f"calc-{calc_id}.json"])["calc_id"] == calc_id

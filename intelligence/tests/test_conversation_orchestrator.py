import io
import json
import time
import urllib.error
from dataclasses import asdict, replace
from threading import Event

import pytest

from intelligence import userspace
from intelligence.services import agent_research, answer_model, evidence_registry, llm_refine, output_review
from intelligence.runtime import conversation_orchestrator as orchestrator_service
from intelligence.services import perspective_lab
from intelligence.services.ask import (
    AskOptions,
    AskResult,
    Citation,
    SynthesisDiagnostic,
)
from intelligence.services.answer_orchestrator import (
    QUESTION_CONCEPT_DEFINITION,
    QUESTION_FACT_CHECK,
    QUESTION_GENERAL,
    QUESTION_MARKET_CAUSE,
    QUESTION_METHODOLOGY,
)
from intelligence.services.lane_generation import LaneAnswer
import intelligence.runtime.conversation_orchestrator as conversation_orchestrator
from intelligence.runtime.conversation_orchestrator import (
    ConversationContext,
    SUMMARY_CHAR_LIMIT,
    TurnOrchestrator,
    _build_generic_research_contract,
    _skill_output_compatible_with_turn,
    _sanitize_market_cause_answer_text,
    build_conversation_context,
    contextualize_follow_up_query,
    _sanitize_citation_list,
    sanitize_conversation_answer,
    sanitize_user_visible_artifact_text,
)
from intelligence.runtime.continuous_turn_adapter import ContinuousTurnResult
from intelligence.services.conversation_store import ConversationStore
from intelligence.services.query_understanding import QueryEnvelope
from intelligence.services.research_contract import TurnIntent
from intelligence.services.research_policy import ResearchExecutionPolicy
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.run_store import RunStore
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_controller import TurnDecision, decide_turn
from intelligence.workbench_skills.contracts import (
    SkillDefinition,
    SkillExecutionContext,
    SkillOutput,
    build_module_answer_contract,
)
from intelligence.workbench_skills.registry import (
    SkillRegistry,
    builtin_skill_registry,
)
from intelligence.workbench_skills.router import (
    SkillRouteResult,
    SkillSelection,
    route_skills,
)


def _ask_result(
    query: str,
    *,
    synthesis: str | None = None,
    llm_provider: str | None = None,
) -> AskResult:
    return AskResult(
        query=query,
        trade_date="2026-07-11",
        matched_theme="测试题材",
        candidate_tier="A",
        priority_score=1.0,
        sections={"结论": [f"本轮检索：{query}"], "引用来源": ["[S1] fixture"]},
        found_market=True,
        synthesis=synthesis,
        llm_provider=llm_provider,
    )


def test_market_db_path_uses_data_root_when_runtime_checkout_has_no_db(
    tmp_path,
    monkeypatch,
) -> None:
    data_root = tmp_path / "data"
    db_path = data_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    db_path.touch()
    monkeypatch.setenv("FINANCE_WS", str(data_root))

    orchestrator = TurnOrchestrator(
        repo_root=tmp_path / "runtime",
        conversation_store=ConversationStore("alice", root=tmp_path / "conversations"),
        run_store=RunStore("alice", root=tmp_path / "runs"),
    )

    assert orchestrator._market_db_path() == db_path


def _research_controller(query: str, **kwargs: object) -> TurnDecision:
    del kwargs
    return TurnDecision(
        lane="research",
        needs_retrieval=True,
        needs_memory=True,
        needs_template=True,
        confidence=1.0,
        reason=f"fixture research: {query}",
    )


def test_public_sanitizer_removes_marker_shells_and_unstable_heading_ordinals() -> None:
    answer = "## 三、判断依据\n来源 [[G1], [G2], [G3]]；有效区间 [10, 20]。[G4, G5, G6]"

    cleaned = sanitize_conversation_answer(answer)

    assert "## 判断依据" in cleaned
    assert "[, ,]" not in cleaned
    assert "[G1" not in cleaned
    assert "[10, 20]" in cleaned
    assert "L4_market_signal" not in sanitize_conversation_answer("L4_market_signal")
    assert "L4_structured" not in sanitize_conversation_answer("L4_structured")


def test_public_sanitizer_spares_prose_mentioning_script_names() -> None:
    # 旧行为：任何含 .py 的行整行替换为占位句——正文提个脚本名就被吞。
    # 新契约：.py 行只有同行还带仪表痕迹（=/--/耗时/python 调用）才隐藏。
    prose = "该拐点信号由 detect_turning_points.py 按无前视确认日算法产出。"
    cleaned = sanitize_conversation_answer(prose)
    assert "detect_turning_points.py" in cleaned

    leak_flag = "radar.py --mode deep-dive 题材深拆"
    assert "radar.py" not in sanitize_conversation_answer(leak_flag)

    leak_timing = "backfill.py 耗时=1200ms 完成回填"
    assert "backfill.py" not in sanitize_conversation_answer(leak_timing)

    leak_invoke = "python3 scripts/audit_coverage.py 覆盖审计通过"
    assert "audit_coverage.py" not in sanitize_conversation_answer(leak_invoke)


def test_continuous_review_notes_drop_internal_issue_receipts() -> None:
    """内部 gate 收据不得进公开答案；中文意见只留 notes，不拼进正文。

    生产 8796：``evidence_type_stripped`` 的 ``code=... :: ...`` 行被原样
    拼进 answer.md。STRIP_OK 是契约层动作，不是给用户看的诊断。
    """

    result = ContinuousTurnResult(
        handled=True,
        status="partial",
        answer="通信设备相对更有机会。",
        as_of=None,
        citations=(),
        warnings=(),
        private_artifact={
            "semantic_verifier": {
                "issues": [
                    "code=evidence_type_stripped subject=prime_quote :: "
                    "stripped unsupported evidence type for prime_quote: finance_query",
                    "第3句质量不够，证明不了主线延续",
                ]
            }
        },
        events=(),
    )
    notes = conversation_orchestrator._continuous_review_notes(result)
    public = conversation_orchestrator._public_answer_text(
        "通信设备相对更有机会。",
        notes,
    )

    assert "质量不够" in " ".join(notes)
    assert not any(item.startswith("code=") for item in notes)
    assert "evidence_type_stripped" not in public
    assert "质量不够" not in public
    assert "## 输出质检" not in public


def test_research_owner_contract_honors_declared_question_types() -> None:
    """A skill may expose a contract, but only for its declared research type."""
    from types import SimpleNamespace

    output = SkillOutput(
        skill_id="daily-agent",
        modules=[],
        citations=[],
        warnings=[],
        as_of=None,
        raw_result_ref=None,
        answer_contract=SimpleNamespace(question_type="daily_review"),
    )
    definition = SkillDefinition(
        skill_id="daily-agent",
        name="Daily Agent",
        description="workflow fixture",
        version="1",
        triggers=(),
        input_schema={"type": "object"},
        permissions=("local_read",),
        timeout_seconds=30,
        role="workflow",
        accepted_question_types=("daily_review",),
        can_own_answer=True,
    )
    assert not _skill_output_compatible_with_turn(
        output,
        definition=definition,
        lane="research",
        question_type="market_forecast",
    )
    assert _skill_output_compatible_with_turn(
        output,
        definition=definition,
        lane="workflow",
        question_type="daily_review",
    )


def test_current_market_mainline_contract_requires_market_and_d4():
    intent = TurnIntent(
        primary_subject=None,
        secondary_topics=(),
        question_type="general_finance_qa",
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
    )
    contract = _build_generic_research_contract(
        "你觉得目前市场的主线是什么，给我你的判断依据",
        task_id="current-mainline-contract",
        turn_intent=intent,
    )
    assert contract.presentation_profile == "mainline_current"
    assert contract.evidence_plan.mandatory_provider_names == (
        "MARKET_DAILY",
        "D4",
    )
    assert contract.allowed_capabilities[:2] == (
        "market_data",
        "mainline_context",
    )
    assert [item.output_id for item in contract.required_outputs[:2]] == [
        "direct_assessment",
        "supporting_evidence",
    ]


def test_mixed_definition_current_fact_contract_requires_typed_market_evidence():
    contract = _build_generic_research_contract(
        "什么是双红，现在哪些板块双红",
        task_id="mixed-double-red",
        turn_intent=TurnIntent(
            primary_subject="双红",
            secondary_topics=(),
            question_type=QUESTION_CONCEPT_DEFINITION,
            answer_owner=None,
            comparison_entities=(),
            inherited_from_turn=None,
        ),
    )
    assert contract.presentation_profile == "market_fact_current"
    assert contract.evidence_plan.mandatory_provider_names == ("D4",)
    assert contract.allowed_capabilities[0] == "mainline_context"
    assert contract.required_outputs[0].evidence_types == ("mainline_context",)


def test_old_daily_agent_contract_cannot_own_market_forecast(tmp_path) -> None:
    """Manual execution keeps the forecast turn, but cannot bypass ownership."""
    from dataclasses import replace

    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "请判断明天市场会反弹还是继续下跌"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    captured: list[AskOptions] = []

    class LegacyDailyAgent:
        skill_id = "daily-agent"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            del context
            modules = [{"type": "summary", "summary": "日报研究队列"}]
            citations = [{"source": "daily.json", "title": "日报"}]
            contract = build_module_answer_contract(
                skill_id=self.skill_id,
                title="日报",
                modules=modules,
                citations=citations,
                warnings=[],
                as_of=None,
                retrieval_plan=("读取日报",),
                output_contract=("输出研究队列",),
            )
            assert contract is not None
            return SkillOutput(
                skill_id=self.skill_id,
                modules=modules,
                citations=citations,
                warnings=[],
                as_of=None,
                raw_result_ref=None,
                answer_contract=replace(contract, question_type="daily_review"),
            )

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="daily-agent",
            name="Daily Agent",
            description="legacy daily contract fixture",
            version="1",
            triggers=("今天研究什么",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
            role="workflow",
            can_own_answer=True,
        ),
        LegacyDailyAgent(),
    )

    def forecast_controller(_query: str, **_kwargs: object) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=False,
            needs_template=True,
            question_type="market_forecast",
            confidence=1.0,
            reason="fixture forecast",
        )

    def capture_answer(options: AskOptions) -> AskResult:
        captured.append(options)
        return _ask_result(options.query)

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=capture_answer,
        skill_registry=registry,
        turn_controller_fn=forecast_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="manual",
        selected_skill_ids=["daily-agent"],
    )

    assert result.status == "completed"
    assert captured[0].question_type_override == "market_forecast"
    warning = (
        "Skill daily-agent 已降级为证据贡献者；需显式声明 owner 元数据后才能接管答案"
    )
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert warning in assistant.degrades
    assert warning in run_store.load_run(run_id).degrades
    rejected = next(
        step
        for step in run_store.load_trace(run_id)
        if step["name"] == "owner_contract_rejected"
    )
    assert json.loads(rejected["output_summary"])["rejected"] == [
        {
            "skill_id": "daily-agent",
            "expected_question_type": "market_forecast",
            "actual_question_type": "daily_review",
            "reason": "skill contract 与 controller turn contract 不兼容",
        }
    ]


def test_citation_projection_dedupes_owner_and_raw_shapes() -> None:
    citations = _sanitize_citation_list(
        [
            {
                "tag": "S1",
                "title": "公司公告",
                "source": "公告详情",
            },
            {
                "tag": "S1",
                "source": "公司公告",
                "detail": "公告详情",
            },
        ]
    )

    assert len(citations) == 1


def _prepare_turn(
    conversation_store: ConversationStore,
    run_store: RunStore,
    conversation_id: str,
    query: str,
    *,
    selected_skill_ids: list[str] | None = None,
) -> tuple[str, str]:
    conversation = conversation_store.load_conversation(conversation_id)
    run = run_store.create_run(
        query,
        "ask",
        session_id=conversation_id,
        parent_run_id=conversation.last_run_id,
    )
    conversation_store.append_message(
        conversation_id,
        "user",
        query,
        run_id=run.run_id,
        selected_skill_ids=selected_skill_ids,
    )
    assistant = conversation_store.append_message(
        conversation_id,
        "assistant",
        "",
        status="pending",
        run_id=run.run_id,
    )
    conversation_store.update_summary(
        conversation_id,
        conversation.summary,
        last_run_id=run.run_id,
    )
    return run.run_id, assistant.message_id


def test_orchestrator_trace_emits_structured_synthesis_diagnostic(
    tmp_path,
    monkeypatch,
) -> None:
    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "总结证据",
    )
    private_prompt = "PRIVATE_SYNTHESIS_PROMPT"
    private_evidence = "PRIVATE_EVIDENCE_BODY"
    expected = SynthesisDiagnostic(
        state="rejected",
        reason_code="grounded_required_fallback",
        detail="grounded presenter did not pass validation",
        prepared_message_count=2,
        candidate_claim_count=1,
        bound_claim_count=0,
    )

    def answer_spy(options: AskOptions) -> AskResult:
        result = _ask_result(options.query)
        result.prepared_synthesis_messages = [
            {"role": "system", "content": private_prompt},
            {"role": "user", "content": private_evidence},
        ]
        return result

    def reject_synthesis(prepared) -> AskResult:
        prepared.result.synthesis_diagnostic = expected
        prepared.result.llm_fallback_reason = "quality_gate_rejected"
        return prepared.result

    monkeypatch.setattr(
        orchestrator_service,
        "synthesize_prepared_answer",
        reject_synthesis,
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="总结证据",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    synthesis_step = next(
        step
        for step in run_store.load_trace(run_id)
        if step["name"] == "answer_synthesis"
    )
    payload = json.loads(synthesis_step["output_summary"])
    # 走一次 JSON 往返再比：diagnostic 里有元组字段（phases），而 JSON 只有数组，
    # 直接跟 asdict() 比会因为 () != [] 假红。往返后仍是全字段严格相等。
    assert payload["diagnostic"] == json.loads(json.dumps(asdict(expected)))
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "prepared_messages" not in serialized
    assert "prompt" not in serialized.lower()
    assert "evidence_body" not in serialized.lower()
    assert private_prompt not in serialized
    assert private_evidence not in serialized


def test_orchestrator_records_not_prepared_when_synthesis_messages_are_absent(
    tmp_path,
) -> None:
    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "总结证据",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="总结证据",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    synthesis_step = next(
        step
        for step in run_store.load_trace(run_id)
        if step["name"] == "answer_synthesis"
    )
    diagnostic = json.loads(synthesis_step["output_summary"])["diagnostic"]
    assert diagnostic["state"] == "not_prepared"
    assert diagnostic["reason_code"] == "no_prepared_messages"


def _continuous_forecast_fixture(
    tmp_path,
    query: str,
    *,
    question_type: str = "market_forecast",
    subject: str = "A股市场",
):
    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    frame = TaskFrame(
        raw_question=query,
        user_goal="判断市场后续走势",
        question_type=question_type,
        subject=subject,
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment", "evidence_boundary"),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )
    intent = TurnIntent(
        primary_subject=frame.subject,
        secondary_topics=(),
        question_type=frame.question_type,
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
        timeframe=frame.timeframe,
        required_outputs=frame.required_outputs,
        task_frame_hash=frame.task_frame_hash,
    )

    def controller(_query: str, **_kwargs: object) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=False,
            needs_template=True,
            question_type=frame.question_type,
            capabilities=("market_news",),
            task_frame=frame,
            turn_intent=intent,
        )

    return (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        frame,
        intent,
        controller,
    )


def test_continuous_turn_publishes_derived_calculation_artifacts(tmp_path) -> None:
    """工单 04：私有产物里的 tool_result.telemetry.derived_calculation 记录 → calc-<id>.json/.html/.csv 进 run 产物。"""

    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "贵州茅台最近几个季度单季营收怎么走"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store, run_store, conversation.conversation_id, query
    )
    frame = TaskFrame(
        raw_question=query,
        user_goal="单季还原",
        question_type="financial_analysis",
        subject="贵州茅台",
        subject_kind="company",
        market_scope="A股",
        timeframe="最近六个季度",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_financial_evidence",
        confidence=0.95,
    )
    intent = TurnIntent(
        primary_subject=frame.subject,
        secondary_topics=(),
        question_type=frame.question_type,
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
        timeframe=frame.timeframe,
        required_outputs=frame.required_outputs,
        task_frame_hash=frame.task_frame_hash,
    )
    calc_id = "0123456789abcdef"
    record = {
        "calc_id": calc_id,
        "purpose": "茅台单季营收还原",
        "script": "emit_result(...)",
        "as_of": "2026-03-31",
        "enforcement": "process",
        "params": {},
        "inputs": [{"ref": "E1", "hash": "a" * 16, "tool": "financial_data", "as_of": "2026-08-15"}],
        "result": {
            "schema": "derived_calculation.result/v1",
            "summary": {"latest_quarter_yi": 375.75},
            "tables": [
                {"name": "单季营收", "columns": ["期间", "单季(亿)"], "rows": [["2026Q1", 547.03], ["2026Q2", 375.75]], "unit": "亿元"}
            ],
        },
    }

    def controller(_query: str, **_kwargs: object) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=False,
            needs_template=True,
            question_type=frame.question_type,
            capabilities=("financial_data",),
            task_frame=frame,
            turn_intent=intent,
        )

    class Adapter:
        def handle(self, *, frame: TaskFrame, control):
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer="2026Q2 单季营收 375.75 亿元（计算编号 0123456789abcdef）。",
                as_of="2026-06-30",
                citations=(),
                warnings=(),
                private_artifact={
                    "events": [
                        {"kind": "task", "payload": {"task_frame_hash": frame.task_frame_hash}},
                        {
                            "kind": "tool_result",
                            "payload": {
                                "tool": "derived_calculation",
                                "telemetry": {"derived_calculation": record},
                            },
                        },
                    ],
                    "semantic_verifier": {"judge_status": "passed", "issues": []},
                },
                events=(),
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy dependency must not run")

    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        lane_answer_fn=forbidden,
        turn_controller_fn=controller,
        continuous_turn_adapter=Adapter(),
    )
    result = orchestrator.run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    run = run_store.load_run(run_id)
    paths = {item["path"]: item for item in run.artifacts}
    assert {f"calc-{calc_id}.json", f"calc-{calc_id}.html", f"calc-{calc_id}-t1.csv"} <= set(paths)
    csv_artifact = paths[f"calc-{calc_id}-t1.csv"]
    assert csv_artifact["renderer"] == "table"
    assert csv_artifact["visibility"] == "public" and csv_artifact["downloadable"] is True
    csv_text = (run_store.run_dir(run_id) / f"calc-{calc_id}-t1.csv").read_text(encoding="utf-8")
    assert "2026Q2,375.75" in csv_text
    html_text = (run_store.run_dir(run_id) / f"calc-{calc_id}.html").read_text(encoding="utf-8")
    assert "茅台单季营收还原" in html_text and "<script" not in html_text
    # 私有审计产物仍在、仍为 internal；calc 产物不影响既有四件。
    assert paths["continuous-episode.json"]["visibility"] == "internal"
    assert {"answer.md", "report.json"} <= set(paths)
    assert not run.degrades


def test_continuous_handled_turn_bypasses_legacy_and_persists_public_result(
    tmp_path,
    monkeypatch,
) -> None:
    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "昨天的反弹能持续多久"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    frame = TaskFrame(
        raw_question=query,
        user_goal="判断反弹持续性",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment", "evidence_boundary"),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )
    intent = TurnIntent(
        primary_subject=frame.subject,
        secondary_topics=(),
        question_type=frame.question_type,
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
        timeframe=frame.timeframe,
        required_outputs=frame.required_outputs,
        task_frame_hash=frame.task_frame_hash,
    )

    def controller(_query: str, **_kwargs: object) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=False,
            needs_template=True,
            question_type=frame.question_type,
            capabilities=("market_news",),
            task_frame=frame,
            turn_intent=intent,
        )

    class Adapter:
        def handle(self, *, frame: TaskFrame, control):
            assert frame is control.task_frame
            assert control.turn_intent == intent
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer="反弹持续性取决于量能与领涨扩散，当前先按条件化修复看待。",
                as_of="2026-07-22",
                citations=(
                    {
                        "title": "市场量能窗口",
                        "source": "本地行情",
                        "date": "2026-07-22",
                    },
                ),
                warnings=(),
                private_artifact={
                    "evidence_hash": "PRIVATE_EVIDENCE_HASH",
                    "provider_attempt": "PRIVATE_PROVIDER_ATTEMPT",
                    "system_prompt": "PRIVATE_SYSTEM_PROMPT",
                    "Authorization": "Bearer PRIVATE_SECRET_VALUE",
                    "api_key": "PRIVATE_API_KEY_VALUE",
                    "semantic_verifier": {
                        "judge_status": "passed",
                        "issues": [],
                        "correlated_judge": True,
                    },
                },
                events=(
                    {
                        "type": "progress",
                        "stage": "research",
                        "message": "已完成本轮证据收集。",
                        "status": "running",
                    },
                ),
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy dependency must not run")

    revisions = 0
    real_revise = conversation_store.revise_message

    def counted_revise(*args, **kwargs):
        nonlocal revisions
        revisions += 1
        return real_revise(*args, **kwargs)

    monkeypatch.setattr(conversation_store, "revise_message", counted_revise)
    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        lane_answer_fn=forbidden,
        turn_controller_fn=controller,
        continuous_turn_adapter=Adapter(),
    )

    result = orchestrator.run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert result.content.startswith("反弹持续性取决于")
    assert revisions == 1
    assistant = next(
        message
        for message in conversation_store.load_messages(conversation.conversation_id)
        if message.message_id == assistant_message_id
    )
    assert assistant.content == result.content
    assert assistant.status == "completed"
    assert assistant.turn_intent["task_frame_hash"] == frame.task_frame_hash
    assert assistant.citations == [
        {
            "title": "市场量能窗口",
            "source": "本地行情",
            "date": "2026-07-22",
        }
    ]
    run = run_store.load_run(run_id)
    assert run.status == "completed"
    assert {item["path"] for item in run.artifacts} == {
        "answer.md",
        "continuous-episode.json",
        "followups.json",
        "report.json",
    }
    private_artifact = next(
        item
        for item in run.artifacts
        if item["path"] == "continuous-episode.json"
    )
    assert private_artifact["visibility"] == "internal"
    assert private_artifact["previewable"] is False
    assert private_artifact["downloadable"] is False
    private_payload = json.loads(
        (run_store.run_dir(run_id) / "continuous-episode.json").read_text(
            encoding="utf-8"
        )
    )
    assert private_payload["evidence_hash"] == "PRIVATE_EVIDENCE_HASH"
    assert private_payload["task_frame"]["task_frame_hash"] == frame.task_frame_hash
    assert private_payload["turn_intent"]["task_frame_hash"] == frame.task_frame_hash
    assert private_payload["Authorization"] == "[REDACTED]"
    assert private_payload["api_key"] == "[REDACTED]"
    private_text = json.dumps(private_payload, ensure_ascii=False)
    assert "PRIVATE_SECRET_VALUE" not in private_text
    assert "PRIVATE_API_KEY_VALUE" not in private_text
    public_stream = json.dumps(
        run_store.load_stream_events(run_id),
        ensure_ascii=False,
    )
    snapshots = [
        event["payload"]
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "answer.snapshot"
    ]
    assert [(snapshot["phase"], snapshot["final"]) for snapshot in snapshots] == [
        ("verified_draft", False),
        ("validated_synthesis", True),
    ]
    assert "PRIVATE_EVIDENCE_HASH" not in public_stream
    assert "PRIVATE_PROVIDER_ATTEMPT" not in public_stream
    assert "PRIVATE_SYSTEM_PROMPT" not in public_stream
    assert any(
        event["event_type"] == "trace.step"
        for event in run_store.load_stream_events(run_id)
    )
    # Engine A 走 _complete_continuous_turn 直接返回，永远到不了编排器那道
    # task_fulfillment 门禁，所以「正文有没有真写到」这一问在生产 research
    # 路径上从未被记录过。这里锁住它现在会被记录。
    coverage_step = next(
        step
        for step in run_store.load_trace(run_id)
        if step["name"] == "answer_marker_coverage"
    )
    coverage = json.loads(coverage_step["output_summary"])
    assert coverage["task_frame_hash"] == frame.task_frame_hash
    assert coverage["absent"] == ["direct_assessment", "evidence_boundary"]
    assert coverage["marker_coverage"] == "incomplete"
    # 观测不许改交付状态：判定为 incomplete，run 仍然 completed。
    assert coverage["observation_only"] is True
    assert run.status == "completed"
    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["answer_status"] == "complete"
    assert report["answer_marker_coverage"]["marker_coverage"] == "incomplete"
    assert report["gate_receipt"]["engine"] == "episode"
    assert "verified_status" in report["gate_receipt"]
    assert "judge_status" in report["gate_receipt"]
    assert report["gate_receipt"]["correlated_judge"] is True


def test_complete_continuous_turn_registers_next_watch(tmp_path, monkeypatch) -> None:
    """会话口跟踪题走 continuous_episode，收尾必须登记下期关注。

    2026-08-19 第二轮 live：parse 已认正文，checkpoints 仍 0。根因是
    ingest 只挂在 legacy ask-compose，`_complete_continuous_turn` 从不调用。
    helper 在 pytest 下是 no-op，本条钉的是收尾会调用。
    """
    query = "光伏最近一个月有什么新变化"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        frame,
        intent,
        controller,
    ) = _continuous_forecast_fixture(
        tmp_path,
        query,
        question_type="theme_track",
        subject="光伏",
    )
    captured: list[dict[str, object]] = []

    class Adapter:
        def handle(self, *, frame: TaskFrame, control):
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer=(
                    "无上期基线，本期建立基线。"
                    "下期关注清单：若 2026-09-12 中报毛利率 <20% 则削弱扩产逻辑。"
                ),
                as_of="2026-08-19",
                citations=(),
                warnings=(),
                private_artifact=None,
                events=(),
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy dependency must not run")

    def capture_ingest(self, **kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(TurnOrchestrator, "_ingest_track_next_watch", capture_ingest)
    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        lane_answer_fn=forbidden,
        turn_controller_fn=controller,
        continuous_turn_adapter=Adapter(),
    )
    result = orchestrator.run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert captured, "continuous 收尾必须调用 _ingest_track_next_watch"
    call = captured[0]
    assert call["query"] == query
    assert "下期关注" in str(call["answer"])
    assert call["question_type"] == "theme_track"
    assert call["as_of"] == "2026-08-19"
    assert call["theme"] == "光伏"
    assert call["session_id"] == run_id


def test_complete_continuous_turn_puts_review_after_revised_body(
    tmp_path,
    monkeypatch,
) -> None:
    """公开终稿只留修订正文；审查意见不进 answer.md。

    验证器的 public_answer 仍是修订正文。issue 留在 gate_receipt / notes，
    不拼「输出质检」附录。
    """
    query = "光伏产业链近况跟踪一下"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        frame,
        intent,
        controller,
    ) = _continuous_forecast_fixture(
        tmp_path,
        query,
        question_type="theme_track",
        subject="光伏",
    )
    revised = "修订后的光伏跟踪结论：扩产兑现仍取决于中报毛利率。"

    class Adapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer=revised,
                as_of="2026-08-19",
                citations=(),
                warnings=(),
                private_artifact={
                    "semantic_verifier": {
                        "judge_status": "repaired",
                        "issues": [
                            "弱证据硬写：无 L3 硬证据却出现确定性措辞",
                        ],
                    }
                },
                events=(),
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy dependency must not run")

    monkeypatch.setattr(TurnOrchestrator, "_ingest_track_next_watch", lambda *a, **k: None)
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        lane_answer_fn=forbidden,
        turn_controller_fn=controller,
        continuous_turn_adapter=Adapter(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.content.startswith(revised)
    assert "## 输出质检" not in result.content
    assert "弱证据硬写：无 L3 硬证据却出现确定性措辞" not in result.content
    snapshots = [
        event["payload"]
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "answer.snapshot"
    ]
    assert snapshots[0]["phase"] == "verified_draft"
    assert snapshots[0]["text"] == revised
    assert snapshots[0]["final"] is False
    assert snapshots[-1]["final"] is True
    assert snapshots[-1]["text"] == result.content
    assert "## 输出质检" not in snapshots[-1]["text"]


def test_complete_continuous_turn_strips_outlook_verification(tmp_path, monkeypatch) -> None:
    query = "写一下本周行情的展望"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        frame,
        intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query, question_type="market_forecast")
    leaked = "新闻层已给部分验证。主线仍在医药。"

    class Adapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer=leaked,
                as_of="2026-08-21",
                citations=(),
                warnings=(),
                private_artifact=None,
                events=(),
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy dependency must not run")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        lane_answer_fn=forbidden,
        turn_controller_fn=controller,
        continuous_turn_adapter=Adapter(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )
    assert "已给部分验证" not in result.content
    assert "主线仍在医药" in result.content
    assert "outlook_delivery_gate" in run_store.load_run(run_id).degrades


def test_research_compose_revises_on_warn_and_keeps_review_as_appendix(
    tmp_path,
    monkeypatch,
) -> None:
    """E2 Engine B：编排器不再显式关掉 compose_revise_on_warn。

    synthesize=False 时 answer_query 里还没有终稿可改；必须在合成之后回灌，
    且 stream_text_delta 不得把修订跳掉。终稿正文是修订版，意见不进公开答案。
    """
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "液冷板块最近一个月有什么新变化"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    captured: list[AskOptions] = []
    draft = "初稿全文确定受益。"
    revised = "修订后的结论：现有证据只能支持观察，不能写成确定受益。"

    def warn_answer(options: AskOptions) -> AskResult:
        captured.append(options)
        result = AskResult(
            query=options.query,
            trade_date="2026-08-18",
            matched_theme="液冷",
            candidate_tier="A",
            priority_score=1.0,
            synthesis=draft,
            sections={"结论": [draft], "引用来源": ["[S1] fixture"]},
        )
        result.synthesis_messages = [
            {"role": "user", "content": "evidence"},
            {"role": "assistant", "content": draft},
        ]
        result.answer_spec = answer_model.AnswerSpec(
            research_spec=answer_model.resolve_answer_profile(
                options.query, "液冷", "theme"
            ),
            summary=(),
            verified_facts=(),
            company_table=(),
            counter_evidence=(),
            gaps=(),
            triggers=(),
            next_actions=(),
            sources=(),
            system_notices=(),
        )
        result.review_gate = output_review.OutputReviewGate(
            checks=[
                output_review.ReviewCheck(
                    name="弱证据硬写",
                    status=output_review.WARN,
                    note="无 L3 硬证据却出现确定性措辞",
                )
            ]
        )
        return result

    def fake_synthesize_messages(messages, **_kwargs):
        del messages
        return (
            llm_refine.SynthesisResult(
                answer=revised,
                provider="fixture",
                model="fixture-model",
            ),
            "",
        )

    monkeypatch.setattr(llm_refine, "synthesize_messages", fake_synthesize_messages)
    monkeypatch.setattr(
        "intelligence.services.ask.answer_model.validate_llm_answer",
        lambda *_args, **_kwargs: (),
    )
    monkeypatch.setattr(
        "intelligence.services.ask.answer_model.present_llm_answer",
        lambda proposed, *_args, **_kwargs: proposed,
    )

    def research_controller(controller_query: str, **kwargs: object) -> TurnDecision:
        del kwargs
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=False,
            needs_template=True,
            question_type="theme_analysis",
            confidence=0.9,
            reason=f"fixture research: {controller_query}",
            capabilities=("market_quote",),
        )

    turn = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=warn_answer,
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult(
            (), fallback_to_ask=True, base_finance_fallback=False
        ),
        skill_registry=SkillRegistry(),
        turn_controller_fn=research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert captured and captured[0].compose_revise_on_warn is True
    assert revised in turn.content
    assert "## 输出质检" not in turn.content
    assert "弱证据硬写" not in turn.content


def test_continuous_turn_injects_selected_perspective_and_headers_answer(
    tmp_path,
    monkeypatch,
) -> None:
    """显式选择的 KOL 视角必须到达 continuous 引擎并署名在答案头。

    2026-08-14 生产 smoke 的失败形状：视角在 API 层验证、存储都通过，但
    continuous 主路径在 ask_options 构造前返回，模型 prompt 与最终答案
    都没有任何视角痕迹——画像成了死数据。本条锁两个到达点：
    (1) control.perspective_context 携带真实画像内容（镜头名，而不只是
    模式标记）；(2) 交付文本带 runtime_answer_header 署名。
    neutral 轮的原样透传由 test_continuous_handled_turn_bypasses_legacy_
    and_persists_public_result 的 startswith 断言锁住。
    """
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    us = userspace.user_space("alice")
    perspective_lab.init_perspective(
        us, "lens_teacher", display_name="测试老师", ptype="blogger"
    )
    profile = perspective_lab.load_profile(us, "lens_teacher")
    profile["market_lenses"] = [
        {
            "name": "筹码测试透镜",
            "description": "看抱团补涨结构与分歧承接",
            "weight": 0.5,
        }
    ]
    perspective_lab.profile_path(us, "lens_teacher").write_text(
        json.dumps(profile, ensure_ascii=False),
        encoding="utf-8",
    )

    query = "今天的市场适合加仓吗"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        frame,
        intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query)
    captured: dict[str, str] = {}

    class Adapter:
        def handle(self, *, frame: TaskFrame, control):
            captured["perspective_context"] = control.perspective_context
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer="按该视角映射：当前结构接近临界，等待放量确认。",
                as_of="2026-07-22",
                citations=(),
                warnings=(),
                private_artifact=None,
                events=(),
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy dependency must not run")

    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        lane_answer_fn=forbidden,
        turn_controller_fn=controller,
        continuous_turn_adapter=Adapter(),
    )

    result = orchestrator.run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
        perspective_mode=perspective_lab.PERSPECTIVE_MODE_SINGLE,
        selected_perspective_ids=["lens_teacher"],
    )

    injected = captured["perspective_context"]
    assert "筹码测试透镜" in injected
    assert "只允许使用下方这一位 KOL" in injected
    assert result.status == "completed"
    assert result.content.startswith("当前视角：测试老师")
    assert "按该视角映射" in result.content
    assistant = next(
        message
        for message in conversation_store.load_messages(conversation.conversation_id)
        if message.message_id == assistant_message_id
    )
    assert assistant.content == result.content
    answer_artifact = (run_store.run_dir(run_id) / "answer.md").read_text(
        encoding="utf-8"
    )
    assert answer_artifact.startswith("当前视角：测试老师")


def test_stance_pack_reaches_handle_control_before_engine_a(
    tmp_path,
    monkeypatch,
) -> None:
    """should_run 为真时，handle() 入参 control 上必须已有 stance_pack。"""

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    query = "扬杰科技我持仓，101.6 止损现在该不该减"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        frame,
        intent,
        _controller,
    ) = _continuous_forecast_fixture(
        tmp_path,
        query,
        question_type="trade_advice",
        subject="扬杰科技",
    )
    frame = replace(
        frame,
        user_goal="给出条件化加减仓判断",
        subject_kind="company",
        evidence_policy="conditional_thesis_evidence",
        required_outputs=("conditional_thesis", "invalidation_conditions"),
    )
    intent = replace(intent, question_type="trade_advice")

    def controller(_query: str, **_kwargs: object) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=True,
            needs_template=True,
            question_type="trade_advice",
            capabilities=("memory", "market_quote"),
            task_frame=frame,
            turn_intent=intent,
        )

    captured: dict[str, object] = {}

    class Adapter:
        def handle(self, *, frame: TaskFrame, control):
            captured["stance_pack"] = control.stance_pack
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer="若站立日现价跌破你的止损条件，再讨论减仓；本轮不给出现在卖。",
                as_of="2026-08-24",
                citations=(),
                warnings=(),
                private_artifact=None,
                events=(),
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy dependency must not run")

    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        lane_answer_fn=forbidden,
        turn_controller_fn=controller,
        continuous_turn_adapter=Adapter(),
    )

    result = orchestrator.run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    pack = captured["stance_pack"]
    assert pack is not None
    assert pack.prior_bag.plane == "checkpoint_verdict"
    assert pack.quote_bag.plane == "provider"
    assert result.status == "completed"


def test_continuous_answer_coverage_separates_uncheckable_from_absent() -> None:
    """No marker vocabulary must not be reported as a coverage failure."""

    query = "这个概念是什么意思"
    frame = TaskFrame(
        raw_question=query,
        user_goal="解释概念",
        question_type="concept_definition",
        subject="某概念",
        subject_kind="concept",
        market_scope="",
        timeframe="",
        # direct_definition 不在 _MARKERS 里；evidence_boundary 在。
        required_outputs=("direct_definition", "evidence_boundary"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="static_knowledge",
        confidence=0.95,
    )

    coverage = orchestrator_service._continuous_answer_coverage(
        frame,
        "它指的是一类结构化产品。数据截至 2026-07-22，证据覆盖有限。",
    )

    assert coverage["uncheckable"] == ["direct_definition"]
    assert coverage["present"] == ["evidence_boundary"]
    assert coverage["absent"] == []
    assert coverage["checked_count"] == 1
    assert coverage["required_output_count"] == 2
    assert coverage["marker_coverage"] == "complete"

    # 全部不可检时给 None，而不是把「没得检」报成「检过且通过」。
    blind_frame = replace(frame, required_outputs=("direct_definition",))
    blind = orchestrator_service._continuous_answer_coverage(blind_frame, "随便什么正文")
    assert blind["uncheckable"] == ["direct_definition"]
    assert blind["checked_count"] == 0
    assert blind["marker_coverage"] is None


def test_continuous_decline_preserves_legacy_lane_behavior(
    tmp_path,
) -> None:
    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "卫星互联网是什么"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    frame = TaskFrame(
        raw_question=query,
        user_goal="解释概念",
        question_type="concept_definition",
        subject="卫星互联网",
        subject_kind="concept",
        market_scope="",
        timeframe="",
        required_outputs=("definition",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="static_knowledge",
        confidence=0.95,
    )
    intent = TurnIntent(
        primary_subject=frame.subject,
        secondary_topics=(),
        question_type=frame.question_type,
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
        timeframe=frame.timeframe,
        required_outputs=frame.required_outputs,
        task_frame_hash=frame.task_frame_hash,
    )

    def controller(_query: str, **_kwargs: object) -> TurnDecision:
        return TurnDecision(
            lane="knowledge",
            needs_retrieval=False,
            needs_memory=False,
            needs_template=False,
            question_type=frame.question_type,
            task_frame=frame,
            turn_intent=intent,
        )

    calls = 0

    class DecliningAdapter:
        def handle(self, *, frame: TaskFrame, control):
            nonlocal calls
            calls += 1
            assert control.task_frame is frame
            return ContinuousTurnResult(
                handled=False,
                status="failed",
                answer="",
                as_of=None,
                citations=(),
                warnings=(),
                private_artifact=None,
                events=(),
            )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_args, **_kwargs: pytest.fail(
            "declined static knowledge must not retrieve"
        ),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "declined static knowledge must not route"
        ),
        lane_answer_fn=lambda *_args, **_kwargs: LaneAnswer(
            "卫星互联网是通过卫星星座提供网络连接的通信系统。"
        ),
        turn_controller_fn=controller,
        continuous_turn_adapter=DecliningAdapter(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert calls == 1
    assert result.status == "completed"
    assert result.content == "卫星互联网是通过卫星星座提供网络连接的通信系统。"


def test_continuous_degraded_turn_is_transport_complete_but_business_partial(
    tmp_path,
) -> None:
    query = "明天反弹还是继续下跌"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        _frame,
        _intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query)

    class DegradedAdapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="degraded",
                answer="现有证据只支持条件判断：若量能不能延续，反弹更可能转为震荡。",
                as_of="2026-07-22",
                citations=(),
                warnings=("仍缺次日增量资金确认。",),
                private_artifact={"judge_status": "unavailable"},
                events=(),
            )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_args, **_kwargs: pytest.fail(
            "handled degraded turn must not enter legacy synthesis"
        ),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "handled degraded turn must not route"
        ),
        lane_answer_fn=lambda *_args, **_kwargs: pytest.fail(
            "handled degraded turn must not use lane generator"
        ),
        turn_controller_fn=controller,
        continuous_turn_adapter=DegradedAdapter(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    snapshots = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "answer.snapshot"
    ]
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert result.status == "completed"
    assert assistant.status == "completed"
    assert assistant.degrades == ["仍缺次日增量资金确认。"]
    assert run_store.load_run(run_id).status == "completed"
    assert report["transport_status"] == "completed"
    assert report["research_status"] == "partial"
    assert report["answer_status"] == "partial"
    assert report["status"] == "partial"
    assert [
        (snapshot["payload"]["phase"], snapshot["payload"]["final"])
        for snapshot in snapshots
    ] == [
        ("verified_draft", False),
        ("evidence_gap_fallback", True),
    ]


def test_continuous_failed_outcome_does_not_complete_run_when_gap_answer_exists(
    tmp_path,
) -> None:
    """R-18：22:18 形——delivery 被改写成 degraded，但 outcome 仍是 failed。"""

    query = "国产算力当前处于哪一段"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        _frame,
        _intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query)

    class FailedOutcomeDegradedDelivery:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="degraded",
                answer="模型服务不可用，本轮未完成核验绑定。",
                as_of=None,
                citations=(),
                warnings=("本轮未取得可公开的答案或证据。",),
                private_artifact={
                    "outcome": {
                        "status": "failed",
                        "stop_reason": "repair_model_unavailable",
                    }
                },
                events=(),
            )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_args, **_kwargs: pytest.fail(
            "failed outcome must not enter legacy synthesis"
        ),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "failed outcome must not route"
        ),
        lane_answer_fn=lambda *_args, **_kwargs: pytest.fail(
            "failed outcome must not use lane generator"
        ),
        turn_controller_fn=controller,
        continuous_turn_adapter=FailedOutcomeDegradedDelivery(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    episode = json.loads(
        (run_store.run_dir(run_id) / "continuous-episode.json").read_text(
            encoding="utf-8"
        )
    )
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert episode["outcome"]["status"] == "failed"
    assert run_store.load_run(run_id).status == "failed"
    assert result.status == "failed"
    assert assistant.status == "failed"
    assert report["status"] == "blocked"
    assert report["transport_status"] == "failed"


def test_continuous_verified_partial_is_not_presented_as_degraded(
    tmp_path,
) -> None:
    query = "这一周行情下跌的主要原因是什么"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        _frame,
        _intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query)

    class PartialAdapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="partial",
                answer=(
                    "本周实际上涨约3%；7月17日单日下跌的事件催化"
                    "缺少时间对齐证据。"
                ),
                as_of="2026-07-23",
                citations=(),
                warnings=(),
                private_artifact={"judge_status": "repaired"},
                events=(),
            )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_args, **_kwargs: pytest.fail(
            "handled partial turn must not enter legacy synthesis"
        ),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "handled partial turn must not route"
        ),
        lane_answer_fn=lambda *_args, **_kwargs: pytest.fail(
            "handled partial turn must not use lane generator"
        ),
        turn_controller_fn=controller,
        continuous_turn_adapter=PartialAdapter(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    snapshots = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "answer.snapshot"
    ]
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert result.status == "completed"
    assert assistant.status == "completed"
    assert assistant.degrades == []
    assert report["answer_status"] == "partial"
    assert report["status"] == "partial"
    assert snapshots[-1]["payload"]["phase"] == "validated_synthesis"


def test_continuous_report_records_episode_llm_provider(tmp_path) -> None:
    query = "目前市场的主线是什么"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        _frame,
        _intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query)

    class EpisodeAdapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer="当前主线处于科技退潮与资源方向接力的换挡阶段。",
                as_of="2026-07-23",
                citations=(),
                warnings=(),
                private_artifact={"metrics": {"provider_attempts": 3}},
                events=(),
                llm_provider="zhipu",
            )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_args, **_kwargs: pytest.fail(
            "handled continuous turn must not enter legacy synthesis"
        ),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "handled continuous turn must not route"
        ),
        lane_answer_fn=lambda *_args, **_kwargs: pytest.fail(
            "handled continuous turn must not use lane generator"
        ),
        llm_model="glm-5.2",
        turn_controller_fn=controller,
        continuous_turn_adapter=EpisodeAdapter(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["llm"] == {
        "used": True,
        "provider": "zhipu",
        "model": "glm-5.2",
    }


def _continuous_growth_report(tmp_path, query, private_artifact):
    """Run one handled continuous turn and return its persisted report."""

    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        _frame,
        _intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query)

    class GrowthAdapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer="当前主线偏向资源方向接力，数据截至 2026-07-23。",
                as_of="2026-07-23",
                citations=(),
                warnings=(),
                private_artifact=private_artifact,
                events=(),
            )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_a, **_k: pytest.fail("must not enter legacy"),
        route_skills_fn=lambda *_a, **_k: pytest.fail("must not route"),
        lane_answer_fn=lambda *_a, **_k: pytest.fail("must not use lane"),
        turn_controller_fn=controller,
        continuous_turn_adapter=GrowthAdapter(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )
    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    trace = {step["name"]: step for step in run_store.load_trace(run_id)}
    return report, trace


def test_continuous_records_per_turn_context_growth_for_own_loop(tmp_path) -> None:
    # ``continuous_glm`` 走 agent_episode 自己的循环，每轮一个 model_turn 事件，
    # 所以逐轮上下文大小是精确的。锁住 max 用的是单轮最大值而不是累加和——
    # 累加和（30+45+60=135K）比真实窗口压力（60K）大一倍多。
    report, trace = _continuous_growth_report(
        tmp_path,
        "目前市场的主线是什么",
        {
            "runtime_backend": "continuous_glm",
            "events": [
                {"kind": "task", "payload": {}},
                {"kind": "model_turn", "payload": {"input_tokens": 30000}},
                {"kind": "tool_result", "payload": {"input_tokens": 999}},
                {"kind": "model_turn", "payload": {"input_tokens": 45000}},
                {"kind": "model_turn", "payload": {"input_tokens": 60000}},
            ],
        },
    )

    growth = report["context_growth"]
    assert growth["provenance"] == "per_turn"
    assert growth["per_turn_input_tokens"] == [30000, 45000, 60000]
    assert growth["max_turn_input_tokens"] == 60000
    assert growth["cumulative_input_tokens"] == 135000
    assert growth["growth_ratio"] == 2.0
    assert growth["observation_only"] is True
    # 观测必须自己进 trace，否则拿不到跨 run 的分布
    assert json.loads(trace["context_growth"]["output_summary"]) == growth
    # 只加观测：交付状态不受影响
    assert report["answer_status"] == "complete"


def test_continuous_marks_sdk_context_growth_as_run_aggregated(tmp_path) -> None:
    # sdk_* 把循环交给 Agents SDK，适配器边界上只看得到 context_wrapper.usage，
    # 而它已经把 SDK 内部多轮加总了（usage.requests 可以 > 1）。所以逐轮值
    # 结构性不可得，必须标成 run_aggregated 并且 max 留 None——猜一个数会让
    # 粗粒度 backend 看起来和精确 backend 一样。
    report, trace = _continuous_growth_report(
        tmp_path,
        "这一周行情下跌的主要原因是什么",
        {
            "runtime_backend": "sdk_gpt",
            "events": [
                {"kind": "task", "payload": {}},
                {
                    "kind": "runtime_result",
                    "payload": {
                        "runtime": "sdk_gpt",
                        "input_tokens": 120000,
                        "provider_attempts": 3,
                    },
                },
            ],
        },
    )

    growth = report["context_growth"]
    assert growth["provenance"] == "run_aggregated"
    assert growth["per_turn_input_tokens"] is None
    assert growth["max_turn_input_tokens"] is None
    assert growth["cumulative_input_tokens"] == 120000
    assert growth["turn_count"] == 3
    assert growth["mean_turn_input_tokens"] == 40000
    assert json.loads(trace["context_growth"]["output_summary"]) == growth


def test_continuous_context_growth_is_unavailable_without_token_events(
    tmp_path,
) -> None:
    # 实测 08-02 那批 sdk_gpt run 就是这个形状：runtime_result 在，但
    # input_tokens 是 None。这时必须报 unavailable，不能因为「有 runtime_result
    # 事件」就当成量到了 0。
    report, _trace = _continuous_growth_report(
        tmp_path,
        "目前市场的主线是什么",
        {
            "runtime_backend": "sdk_gpt",
            "events": [
                {"kind": "task", "payload": {}},
                {
                    "kind": "runtime_result",
                    "payload": {"runtime": "sdk_gpt", "input_tokens": None},
                },
                {"kind": "finish", "payload": {"status": "completed"}},
            ],
        },
    )

    growth = report["context_growth"]
    assert growth["provenance"] == "unavailable"
    assert growth["cumulative_input_tokens"] is None
    assert growth["turn_count"] == 0


def test_continuous_failed_turn_uses_same_message_and_run_identity(
    tmp_path,
) -> None:
    query = "目前市场的主线是什么"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        _frame,
        _intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query)

    class FailedAdapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="failed",
                answer="",
                as_of=None,
                citations=(),
                warnings=("连续研究执行失败。",),
                private_artifact={"failure": "fixture"},
                events=(),
            )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_args, **_kwargs: pytest.fail(
            "failed handled turn must not enter legacy synthesis"
        ),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "failed handled turn must not route"
        ),
        lane_answer_fn=lambda *_args, **_kwargs: pytest.fail(
            "failed handled turn must not use lane generator"
        ),
        turn_controller_fn=controller,
        continuous_turn_adapter=FailedAdapter(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = next(
        message
        for message in conversation_store.load_messages(conversation.conversation_id)
        if message.message_id == assistant_message_id
    )
    assert result.status == "failed"
    assert assistant.message_id == assistant_message_id
    assert assistant.run_id == run_id
    assert assistant.status == "failed"
    assert run_store.load_run(run_id).status == "failed"
    private_artifact = next(
        item
        for item in run_store.load_run(run_id).artifacts
        if item["path"] == "continuous-episode.json"
    )
    assert private_artifact["visibility"] == "internal"
    assert private_artifact["previewable"] is False
    assert private_artifact["downloadable"] is False
    assert any(
        event["event_type"] == "message.error"
        and event["message_id"] == assistant_message_id
        and event["run_id"] == run_id
        for event in run_store.load_stream_events(run_id)
    )


def test_continuous_cancellation_keeps_same_message_and_run_identity(
    tmp_path,
) -> None:
    query = "这一周行情下跌的主要原因是什么"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        _frame,
        _intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query)
    cancelled = Event()

    class CancellingAdapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            cancelled.set()
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer="这个答案不应越过取消边界。",
                as_of="2026-07-22",
                citations=(),
                warnings=(),
                private_artifact=None,
                events=(),
            )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        turn_controller_fn=controller,
        continuous_turn_adapter=CancellingAdapter(),
        is_cancelled=cancelled.is_set,
        cancellation_reason=lambda: "cancelled_by_user",
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = next(
        message
        for message in conversation_store.load_messages(conversation.conversation_id)
        if message.message_id == assistant_message_id
    )
    assert result.status == "cancelled"
    assert assistant.message_id == assistant_message_id
    assert assistant.run_id == run_id
    assert assistant.status == "cancelled"
    assert run_store.load_run(run_id).status == "cancelled"
    assert "这个答案不应越过取消边界" not in assistant.content


def test_continuous_terminal_cas_prevents_cancelled_run_completed_message_race(
    tmp_path,
    monkeypatch,
) -> None:
    query = "目前市场的主线是什么"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        _frame,
        _intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query)

    class CompletedAdapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="completed",
                answer="这个答案不应覆盖已经获胜的取消终态。",
                as_of="2026-07-22",
                citations=(),
                warnings=(),
                private_artifact={"execution_kind": "continuous_episode"},
                events=(),
            )

    real_claim = run_store.claim_terminal_run
    real_revise = conversation_store.revise_message
    cancellation_won = False
    revision_statuses: list[str] = []

    def counted_revise(*args, **kwargs):
        revision_statuses.append(str(kwargs["status"]))
        return real_revise(*args, **kwargs)

    monkeypatch.setattr(conversation_store, "revise_message", counted_revise)

    def racing_claim(target_run_id, status, *args, **kwargs):
        nonlocal cancellation_won
        if target_run_id == run_id and status == "completed" and not cancellation_won:
            cancellation_won = True
            current = next(
                message
                for message in conversation_store.load_messages(
                    conversation.conversation_id
                )
                if message.message_id == assistant_message_id
            )
            conversation_store.revise_message(
                conversation.conversation_id,
                assistant_message_id,
                content=current.content,
                status="cancelled",
                selected_skill_ids=current.selected_skill_ids,
                invoked_skill_ids=current.invoked_skill_ids,
                citations=current.citations,
                degrades=["用户已取消本轮执行"],
            )
            real_claim(
                target_run_id,
                "cancelled",
                error="cancelled_by_user",
            )
        return real_claim(target_run_id, status, *args, **kwargs)

    monkeypatch.setattr(run_store, "claim_terminal_run", racing_claim)
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        turn_controller_fn=controller,
        continuous_turn_adapter=CompletedAdapter(),
        cancellation_reason=lambda: "cancelled_by_user",
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = next(
        message
        for message in conversation_store.load_messages(conversation.conversation_id)
        if message.message_id == assistant_message_id
    )
    public_events = run_store.load_stream_events(run_id)
    assert cancellation_won is True
    assert result.status == "cancelled"
    assert revision_statuses == ["cancelled"]
    assert assistant.status == "cancelled"
    assert assistant.message_id == assistant_message_id
    assert run_store.load_run(run_id).status == "cancelled"
    assert not any(
        event["event_type"] in {"text.delta", "answer.snapshot"}
        for event in public_events
    )
    assert "这个答案不应覆盖" not in assistant.content


def test_cancel_does_not_overwrite_artifacts_after_lost_claim(tmp_path) -> None:
    """G5：cancel 认领失败时不得覆盖赢家已经写好的 answer.md。"""

    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "目前市场的主线是什么"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    conversation_store.revise_message(
        conversation.conversation_id,
        assistant_message_id,
        content="赢家答案",
        status="completed",
    )
    run_store.add_artifact(
        run_id,
        "answer.md",
        "赢家答案",
        renderer="markdown",
        title="答案",
    )
    run_store.finish_run(run_id, "completed")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
    )._cancel(
        conversation.conversation_id,
        run_id,
        assistant_message_id,
        {"status": "running", "warnings": []},
        [],
        [],
        [],
        [],
        [],
        ["草稿不应发表"],
    )

    assistant = next(
        message
        for message in conversation_store.load_messages(conversation.conversation_id)
        if message.message_id == assistant_message_id
    )
    assert result.status == "completed"
    assert result.content == "赢家答案"
    assert run_store.load_run(run_id).status == "completed"
    assert (run_store.run_dir(run_id) / "answer.md").read_text(
        encoding="utf-8"
    ) == "赢家答案"
    assert assistant.content == "赢家答案"
    assert assistant.status == "completed"


def test_continuous_terminal_cas_does_not_duplicate_executor_timeout_revision(
    tmp_path,
    monkeypatch,
) -> None:
    query = "这一周行情下跌的主要原因是什么"
    (
        conversation_store,
        run_store,
        conversation,
        run_id,
        assistant_message_id,
        _frame,
        _intent,
        controller,
    ) = _continuous_forecast_fixture(tmp_path, query)

    class FailedAdapter:
        def handle(self, *, frame: TaskFrame, control):
            del frame, control
            return ContinuousTurnResult(
                handled=True,
                status="failed",
                answer="",
                as_of=None,
                citations=(),
                warnings=("连续研究执行失败。",),
                private_artifact={"failure": "provider_timeout"},
                events=(),
            )

    real_claim = run_store.claim_terminal_run
    real_revise = conversation_store.revise_message
    timeout_won = False
    revision_statuses: list[str] = []

    def counted_revise(*args, **kwargs):
        revision_statuses.append(str(kwargs["status"]))
        return real_revise(*args, **kwargs)

    monkeypatch.setattr(conversation_store, "revise_message", counted_revise)

    def racing_claim(target_run_id, status, *args, **kwargs):
        nonlocal timeout_won
        if target_run_id == run_id and status == "failed" and not timeout_won:
            timeout_won = True
            current = next(
                message
                for message in conversation_store.load_messages(
                    conversation.conversation_id
                )
                if message.message_id == assistant_message_id
            )
            conversation_store.revise_message(
                conversation.conversation_id,
                assistant_message_id,
                content=current.content,
                status="failed",
                selected_skill_ids=current.selected_skill_ids,
                invoked_skill_ids=current.invoked_skill_ids,
                citations=current.citations,
                degrades=["本轮执行超时"],
            )
            real_claim(
                target_run_id,
                "failed",
                error="executor_timeout",
            )
        return real_claim(target_run_id, status, *args, **kwargs)

    monkeypatch.setattr(run_store, "claim_terminal_run", racing_claim)
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        turn_controller_fn=controller,
        continuous_turn_adapter=FailedAdapter(),
        cancellation_reason=lambda: "executor_timeout",
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = next(
        message
        for message in conversation_store.load_messages(conversation.conversation_id)
        if message.message_id == assistant_message_id
    )
    assert timeout_won is True
    assert result.status == "failed"
    assert revision_statuses == ["failed"]
    assert assistant.status == "failed"
    assert assistant.degrades == ["本轮执行超时"]
    assert run_store.load_run(run_id).error == "executor_timeout"


def test_long_tail_e2e_trace_keeps_route_budget_completion_and_grounding(
    tmp_path,
    monkeypatch,
) -> None:
    """长尾验收不只看正文，还要证明同一 run 的控制链没断。"""

    monkeypatch.setenv("WORKBENCH_SHADOW_GROUNDED_COMPOSER", "1")
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "一个没有现成 skill 的陌生题材怎么判断？"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )

    def controller(value: str, **kwargs: object) -> TurnDecision:
        allowed = {
            key: kwargs[key]
            for key in (
                "context",
                "skill_mode",
                "selected_skill_ids",
                "previous_intent",
                "previous_turn_id",
            )
            if key in kwargs
        }
        return decide_turn(
            value,
            llm_complete=lambda _messages: (None, None, "offline"),
            **allowed,
        )

    def answer(options: AskOptions) -> AskResult:
        assert options.research_task_contract is not None
        assert options.research_task_contract.task_id == run_id
        verified = answer_model.make_claim(
            claim_id="fixture:verified",
            text="已确认的起点是先核对需求变化与产业链传导。",
            claim_type="fact",
            theme="陌生题材",
            status=answer_model.ClaimStatus.VERIFIED,
            evidence_ids=("G1",),
        )
        summary = answer_model.make_claim(
            claim_id="fixture:summary",
            text="当前应把它当作待验证假设，不是现成结论。",
            claim_type="summary",
            theme="陌生题材",
            status=answer_model.ClaimStatus.INFERRED,
            evidence_ids=("G1",),
        )
        gap = answer_model.make_claim(
            claim_id="fixture:gap",
            text="还缺少公司端订单或收入兑现证据。",
            claim_type="evidence_gap",
            theme="陌生题材",
            status=answer_model.ClaimStatus.MISSING,
        )
        spec = answer_model.finalize_answer_spec(
            answer_model.AnswerSpec(
                research_spec=answer_model.resolve_answer_profile(
                    query,
                    "陌生题材",
                    "general",
                ),
                summary=(summary,),
                verified_facts=(verified,),
                company_table=(),
                counter_evidence=(),
                gaps=(gap,),
                triggers=(),
                next_actions=("下一验证窗口核对官方公告与订单披露。",),
                sources=(answer_model.EvidenceRef("G1", "fixture", "可回查来源"),),
                system_notices=(),
                presentation_kind="generic_research",
            )
        )
        return AskResult(
            query=options.query,
            trade_date="2026-07-21",
            matched_theme=None,
            candidate_tier=None,
            priority_score=None,
            citations=[Citation("G1", "fixture", "可回查来源")],
            answer_spec=spec,
            completion_report={
                "status": "partial",
                "outputs": [
                    {"output_id": "direct_assessment", "status": "fulfilled"},
                    {"output_id": "supporting_evidence", "status": "fulfilled"},
                    {"output_id": "counterpoint", "status": "gap"},
                ],
            },
            provider_traces=[
                ProviderTrace(
                    provider="fixture-provider",
                    capability="web_search",
                    status="success",
                    result_count=1,
                    parent_id=run_id,
                    step_id="agent:1",
                )
            ],
        )

    def shadow(prepared, **_kwargs):
        prepared.result.grounded_composer_shadow = answer_model.GroundedComposerShadow(
            status="accepted",
            presented_answer="已完成可核验短答。\n下一步核对公告。",
        )
        return prepared.result

    def forbidden_router(*_args, **_kwargs):
        raise AssertionError("ownerless long-tail must not enter skill router")

    monkeypatch.setattr(
        orchestrator_service,
        "synthesize_shadow_grounded_answer",
        shadow,
    )
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer,
        route_skills_fn=forbidden_router,
        turn_controller_fn=controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert result.selected_skill_ids == ()
    assert result.invoked_skill_ids == ()
    assert "本轮尚未完成问题所需的直接回答" in result.content
    assert "缺少的数据/证据" in result.content
    assert "请补充数据源或稍后重试" in result.content
    assert "研究雷达" not in result.content
    assert "每日市场复盘" not in result.content

    trace = run_store.load_trace(run_id)
    by_name = {step["name"]: step for step in trace}
    route_output = json.loads(by_name["route_skills"]["output_summary"])
    assert route_output["generic_owner_requested"] is True
    assert route_output["selected"] == []
    assert "research_budget" in by_name["research_execution_budget"]["retrieval"]
    retrieval_output = json.loads(by_name["ask_retrieve_compose"]["output_summary"])
    assert retrieval_output["completion_report"]["status"] == "partial"
    provider_traces = retrieval_output["provider_traces"]
    assert provider_traces
    assert {item["parent_id"] for item in provider_traces} == {run_id}
    assert all(item["step_id"] for item in provider_traces)
    assert "grounded_composer_shadow" not in by_name


def test_long_tail_real_owner_chain_reaches_completion_and_grounded_fallback(
    tmp_path,
    monkeypatch,
) -> None:
    """不替换 answer_query/owner/presenter，只隔离外部网络和 LLM。"""

    for key in (
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "KIMI_API_KEY",
        "DASHSCOPE_API_KEY",
        "QWEN_API_KEY",
        "ZHIPU_API_KEY",
        "GLM_API_KEY",
        "OPENAI_API_KEY",
        "LLM_API_KEY",
        "LLM_JUDGE_API_KEY",
        "FORESIGHT_BUILTIN_LLM_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WORKBENCH_SHADOW_GROUNDED_COMPOSER", "1")
    monkeypatch.setenv("FINANCE_NEWS_FETCH", "0")
    monkeypatch.setenv("FINANCE_WEB_SEARCH", "0")
    monkeypatch.setattr(agent_research, "build_default_tools", lambda _retrieve: {})
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda _messages, **_kwargs: (
            '{"tool":"finish","args":{"sufficient":false,'
            '"assessment":"","gaps":["尚无可回查材料"]},'
            '"reason":"如实报缺口"}',
            "fixture",
            "",
        ),
    )

    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "一个没有现成 skill 的陌生题材怎么判断？"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )

    def forbidden_router(*_args, **_kwargs):
        raise AssertionError("ownerless long-tail must not enter skill router")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        route_skills_fn=forbidden_router,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert result.selected_skill_ids == ()
    assert result.invoked_skill_ids == ()
    assert "本轮尚未完成问题所需的直接回答" in result.content
    assert "缺少的数据/证据" in result.content
    assert "请补充数据源或稍后重试" in result.content
    assert "研究雷达" not in result.content
    trace = {step["name"]: step for step in run_store.load_trace(run_id)}
    route_output = json.loads(trace["route_skills"]["output_summary"])
    assert route_output["generic_owner_requested"] is True
    assert route_output["selected"] == []
    retrieval = json.loads(trace["ask_retrieve_compose"]["output_summary"])
    assert retrieval["completion_report"]["status"] == "partial"
    assert "grounded_composer_shadow" not in trace


def test_long_tail_real_owner_success_chain_keeps_template_isolation(
    tmp_path,
    monkeypatch,
) -> None:
    """成功链走真实 owner/completion/presenter，只用可回放的假 provider。"""

    monkeypatch.setenv("WORKBENCH_SHADOW_GROUNDED_COMPOSER", "1")
    monkeypatch.setattr(
        agent_research.llm_refine, "detect_provider", lambda _model=None: None
    )

    def web_runner(query: str, _context):
        return (
            [
                agent_research.AgentEvidence(
                    tool="web_search",
                    title="官方行业资料",
                    detail=f"资料直接回应检索问题：{query}",
                    source="https://example.test/official",
                    source_date="2026-07-21",
                    evidence_tier="public_web",
                )
            ],
            "命中 1 条官方资料",
            ProviderTrace(
                provider="fixture:web",
                capability="web_search",
                status="success",
                result_count=1,
            ),
        )

    monkeypatch.setattr(
        agent_research,
        "build_default_tools",
        lambda _retrieve: {"web_search": web_runner},
    )
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    actions = iter(
        (
            '{"tool":"web_search","args":{"query":"陌生题材 需求与产业链"},'
            '"reason":"先核对业务事实"}',
            '{"tool":"finish","args":{"sufficient":true,'
            '"assessment":"应先验证需求变化能否传导到公司收入，再判断题材强度。",'
            '"gaps":[]},"reason":"必需输出已覆盖"}',
        )
    )
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda _messages, **_kwargs: (next(actions), "fixture", ""),
    )

    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "一个没有现成 skill 的陌生题材怎么判断？"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )

    def controller(value: str, **kwargs: object) -> TurnDecision:
        allowed = {
            key: kwargs[key]
            for key in (
                "context",
                "skill_mode",
                "selected_skill_ids",
                "previous_intent",
                "previous_turn_id",
            )
            if key in kwargs
        }
        return decide_turn(
            value,
            llm_complete=lambda _messages: (None, None, "offline"),
            **allowed,
        )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "ownerless long-tail must not enter skill router"
        ),
        turn_controller_fn=controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert "需求变化" in result.content
    assert "本轮已找到相关来源" in result.content
    assert "下一验证" in result.content
    assert "研究雷达" not in result.content
    assert "每日市场复盘" not in result.content
    trace = {step["name"]: step for step in run_store.load_trace(run_id)}
    retrieval = json.loads(trace["ask_retrieve_compose"]["output_summary"])
    assert retrieval["completion_report"]["status"] == "completed"
    assert retrieval["provider_traces"][0]["parent_id"] == run_id
    assert retrieval["provider_traces"][0]["step_id"]


def test_model_meta_question_skips_financial_routing_and_retrieval(
    tmp_path,
) -> None:
    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "你好，你是什么模型"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("meta answer must not route or retrieve")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert result.selected_skill_ids == ()
    assert result.invoked_skill_ids == ()
    assert "不会触发金融检索" in result.content
    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["task_type"] == "meta"
    assert report["as_of"] is None
    assert report["modules"] == []
    route_step = next(
        step
        for step in run_store.load_trace(run_id)
        if step["name"] == "turn_controller"
    )
    route_output = json.loads(route_step["output_summary"])
    assert route_output["decision"]["lane"] == "meta"
    assert route_output["decision"]["needs_retrieval"] is False


def test_greeting_uses_chat_lane_without_router_or_retrieval(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "你好",
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("chat lane must not route or retrieve")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden,
        route_skills_fn=forbidden,
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="你好",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert "直接聊天" in result.content
    assert "非投资建议" not in result.content
    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["task_type"] == "chat"
    assert report["modules"] == []
    assert report["warnings"] == []


def test_ambiguous_request_uses_clarify_lane_without_retrieval(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "帮我看看",
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_: pytest.fail("clarify must not retrieve"),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail("clarify must not route"),
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="帮我看看",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert "我还缺少一点信息" in result.content
    assert "看什么对象" in result.content


def test_unbound_rebound_clarifies_before_route_or_retrieval(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "这个反弹还能持续多久"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_: pytest.fail("clarify must not retrieve"),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail("clarify must not route"),
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert "哪个明确主体" in result.content
    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["task_type"] == "clarify"
    assert report["task_frame"]["raw_question"] == query
    assert report["task_frame"]["clarification_question"] is not None


def test_rebound_clarification_resumes_original_forecast_on_second_turn(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    captured: list[AskOptions] = []

    def controller(query: str, **kwargs: object) -> TurnDecision:
        return decide_turn(
            query,
            **kwargs,
            llm_complete=lambda _messages: (None, None, "fixture unavailable"),
        )

    def answer(options: AskOptions) -> AskResult:
        captured.append(options)
        return _ask_result(options.query, synthesis="按A股市场继续判断反弹持续性。")

    orchestrator = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer,
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "resumed deterministic forecast must skip skill routing"
        ),
        skill_registry=SkillRegistry(),
        turn_controller_fn=controller,
    )

    first_query = "这个反弹还能持续多久"
    first_run, first_message = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        first_query,
    )
    first = orchestrator.run_turn(
        conversation_id=conversation.conversation_id,
        run_id=first_run,
        assistant_message_id=first_message,
        query=first_query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert first.status == "completed"
    first_assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert first_assistant.turn_intent is not None
    assert first_assistant.turn_intent["pending_task_frame"]["raw_question"] == (
        first_query
    )

    second_query = "A股"
    second_run, second_message = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        second_query,
    )
    second = orchestrator.run_turn(
        conversation_id=conversation.conversation_id,
        run_id=second_run,
        assistant_message_id=second_message,
        query=second_query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert second.status == "completed"
    assert len(captured) == 1
    assert captured[0].question_type_override == "market_forecast"
    assert captured[0].research_task_contract is not None
    assert captured[0].research_task_contract.question == first_query
    second_assistant = conversation_store.load_messages(conversation.conversation_id)[
        -1
    ]
    assert second_assistant.turn_intent is not None
    assert second_assistant.turn_intent["question_type"] == "market_forecast"
    assert second_assistant.turn_intent["primary_subject"] == "A股市场"
    assert second_assistant.turn_intent["pending_task_frame"] is None
    second_report = json.loads(
        (run_store.run_dir(second_run) / "report.json").read_text(encoding="utf-8")
    )
    assert second_report["task_frame"]["raw_question"] == first_query


def test_static_knowledge_lane_uses_neutral_generator_without_retrieval(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "卫星互联网是什么",
    )
    captured: dict[str, object] = {}

    def lane_answer(
        query: str,
        decision: TurnDecision,
        **kwargs: object,
    ) -> LaneAnswer:
        captured.update(query=query, decision=decision, kwargs=kwargs)
        return LaneAnswer("卫星互联网是通过卫星星座提供网络连接的通信系统。")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_: pytest.fail("static knowledge must not retrieve"),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "knowledge lane must not route"
        ),
        skill_registry=SkillRegistry(),
        lane_answer_fn=lane_answer,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="卫星互联网是什么",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.content == "卫星互联网是通过卫星星座提供网络连接的通信系统。"
    assert captured["decision"].lane == "knowledge"
    assert "当前视角" not in result.content
    assert "非投资建议" not in result.content


def test_methodology_lane_never_falls_back_to_financial_rag(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "编排层为什么会导致模板化？"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_args, **_kwargs: pytest.fail(
            "methodology failure must not be replaced by financial RAG"
        ),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "methodology lane must not route to a skill"
        ),
        skill_registry=SkillRegistry(),
        lane_answer_fn=lambda *_args, **_kwargs: LaneAnswer(
            "当前自然语言生成暂时不可用，无法可靠生成方法论分析；请稍后重试。",
            fallback_reason="fixture timeout",
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert "金融" not in result.content
    assert "方法论分析" in result.content
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.degrades == ["方法论回答生成暂时不可用"]
    controller = next(
        step
        for step in run_store.load_trace(run_id)
        if step["name"] == "turn_controller"
    )
    decision = json.loads(controller["output_summary"])["decision"]
    assert decision["question_type"] == QUESTION_METHODOLOGY
    assert decision["needs_retrieval"] is False
    assert (
        json.loads(controller["output_summary"])["decision_diverged_from_legacy"]
        is False
    )
    generation = next(
        step
        for step in run_store.load_trace(run_id)
        if step["name"] == "lane_direct_answer"
    )
    assert json.loads(generation["output_summary"])["retrieval_attempted"] is False
    snapshots = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "answer.snapshot"
    ]
    assert [event["payload"]["phase"] for event in snapshots] == [
        "verified_draft",
        "verified_fallback",
    ]


def test_relation_question_skips_theme_skill_router(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "液冷和PCB谁在产业链上游？"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "relation guard must run before theme skill routing"
        ),
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    route = next(
        step for step in run_store.load_trace(run_id) if step["name"] == "route_skills"
    )
    route_output = json.loads(route["output_summary"])
    assert route_output["router_skipped"] is True
    assert route_output["relation_guard_requested"] is True


def test_final_task_gate_marks_candidate_list_partial_even_when_research_complete(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "目前市场的主线是什么"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )

    def controller(_query: str, **_kwargs: object) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=False,
            needs_template=True,
            question_type=QUESTION_GENERAL,
            confidence=1.0,
            capabilities=("web_search",),
        )

    def answer_with_candidate_list(options: AskOptions) -> AskResult:
        assert options.research_task_contract is not None
        result = _ask_result(
            query, synthesis="本轮只展示候选来源，仍缺少针对用户问题的直接判断。"
        )
        result.business_status = "complete"
        result.completion_report = {"business_status": "complete"}
        result.citations = [Citation("G1", "2025 市场回顾", "全年回顾性线索")]
        result.answer_spec = answer_model.finalize_answer_spec(
            answer_model.AnswerSpec(
                research_spec=answer_model.resolve_answer_profile(
                    query,
                    profile="general",
                ),
                summary=(
                    answer_model.make_claim(
                        claim_id="generic:summary",
                        text="本轮只展示候选来源，仍缺少针对用户问题的直接判断。",
                        claim_type="summary",
                        theme="市场",
                        status=answer_model.ClaimStatus.MISSING,
                    ),
                ),
                verified_facts=(),
                company_table=(),
                counter_evidence=(),
                gaps=(),
                triggers=(),
                next_actions=(),
                sources=(
                    answer_model.EvidenceRef(
                        evidence_id="G1",
                        source="2025 市场回顾",
                        detail="全年回顾性线索",
                        source_date="2025-12-31",
                    ),
                ),
                system_notices=(),
                presentation_kind="generic_research",
                presentation_profile="general",
            )
        )
        return result

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_with_candidate_list,
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "generic owner should skip the skill answer router"
        ),
        skill_registry=SkillRegistry(),
        turn_controller_fn=controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    snapshots = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "answer.snapshot"
    ]
    report_artifact = next(
        artifact
        for artifact in run_store.load_run(run_id).artifacts
        if artifact["path"] == "report.json"
    )
    report = json.loads(
        (run_store.run_dir(run_id) / report_artifact["path"]).read_text(
            encoding="utf-8"
        )
    )

    assert result.status == "completed"  # transport remains compatible
    assert snapshots[-1]["payload"]["phase"] == "evidence_gap_fallback"
    assert report["transport_status"] == "completed"
    assert report["research_status"] == "complete"
    assert report["answer_status"] == "partial"
    assert report["status"] == "partial"
    direct = next(
        item
        for item in report["task_fulfillment"]["items"]
        if item["output_id"] == "direct_assessment"
    )
    assert direct["status"] == "missing"
    assert "本轮尚未完成问题所需的直接回答" in result.content
    assert "候选来源" not in result.content


def test_market_cause_removes_generic_investment_disclaimer() -> None:
    answer = _sanitize_market_cause_answer_text(
        "主要原因是风险偏好收缩。\n\n（非投资建议）",
        "这一周行情下跌的主要原因是什么",
    )

    assert answer == "主要原因是风险偏好收缩。"


def test_market_cause_contract_requires_time_aligned_external_evidence() -> None:
    contract = _build_generic_research_contract(
        "这一周行情下跌的主要原因是什么",
        task_id="fixture-cause",
        turn_intent=TurnIntent(
            primary_subject=None,
            secondary_topics=(),
            question_type=QUESTION_MARKET_CAUSE,
            answer_owner=None,
            comparison_entities=(),
            inherited_from_turn=None,
            operators=("cause_attribution",),
        ),
    )

    external = next(
        item
        for item in contract.required_outputs
        if item.output_id == "external_cause_evidence"
    )
    assert external.required is True
    assert external.evidence_types == ("web_search", "news_search")


def test_non_owner_skill_modules_enter_candidate_claim_channel() -> None:
    output = SkillOutput(
        skill_id="theme-radar",
        modules=[
            {
                "title": "需求变化",
                "summary": "下游订单出现边际改善",
                "content": "仍需公司公告核验",
            }
        ],
        citations=[{"title": "公开公告", "source": "https://example.test/a"}],
        warnings=[],
        as_of="2026-07-20",
        raw_result_ref=None,
    )
    claims, citations = TurnOrchestrator._skill_claim_bundle((output,))
    assert len(claims) == 1
    assert claims[0].status == answer_model.ClaimStatus.CANDIDATE
    assert claims[0].evidence_ids == ("SK1",)
    assert citations[0].tag == "SK1"


def test_customer_fact_check_contract_requires_and_allows_l3_lookup() -> None:
    intent = TurnIntent(
        primary_subject="中际旭创",
        secondary_topics=("英伟达",),
        question_type=QUESTION_FACT_CHECK,
        answer_owner=None,
        comparison_entities=(),
        inherited_from_turn=None,
        operators=("relation",),
    )

    for query in (
        "中际旭创和英伟达是否已确认合作？",
        "中际旭创是英伟达供应商吗？",
        "中际旭创是不是英伟达的供应商？",
        "中际旭创和英伟达合作吗？",
    ):
        contract = _build_generic_research_contract(
            query,
            task_id="fixture",
            turn_intent=intent,
        )

        assert "l3_lookup" in contract.allowed_capabilities
        customer = next(
            item
            for item in contract.required_outputs
            if item.output_id == "customer_validation"
        )
        assert customer.required is True
        assert customer.evidence_types == ("l3_lookup",)


def test_static_knowledge_uses_local_retrieval_when_generation_is_unavailable(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "卫星互联网是什么",
    )
    captured: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        captured.append(options)
        return AskResult(
            query=options.query,
            trade_date=None,
            matched_theme=None,
            candidate_tier=None,
            priority_score=None,
            citations=[
                Citation(
                    "E1",
                    "百科来源",
                    "https://example.com/satellite-internet",
                )
            ],
            sections={
                "结论": ["已取得可核验来源。"],
                "证据链": ["卫星互联网通过通信卫星提供网络连接。[E1]"],
                "分歧反证": [],
            },
        )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "knowledge fallback must not enter the skill router"
        ),
        skill_registry=SkillRegistry(),
        lane_answer_fn=lambda *_args, **_kwargs: LaneAnswer(
            "生成不可用",
            fallback_reason="未配置 LLM key",
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="卫星互联网是什么",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert "可核验资料摘要" in result.content
    assert "卫星互联网通过通信卫星提供网络连接" in result.content
    assert captured[0].question_type_override == QUESTION_CONCEPT_DEFINITION
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.citations[0]["source"] == "百科来源"
    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["task_type"] == "knowledge"


def test_static_knowledge_fails_closed_when_generation_and_retrieval_fail(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "卫星互联网是什么",
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("private diagnostic")
        ),
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "knowledge fallback must not enter the skill router"
        ),
        skill_registry=SkillRegistry(),
        lane_answer_fn=lambda *_args, **_kwargs: LaneAnswer(
            "生成不可用",
            fallback_reason="未配置 LLM key",
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="卫星互联网是什么",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert "未取得足够可靠的资料" in result.content
    assert "private diagnostic" not in result.content
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.degrades == ["一般知识检索暂时不可用"]
    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["task_type"] == "knowledge"
    assert report["warnings"] == ["一般知识检索暂时不可用"]


def test_knowledge_follow_up_uses_bounded_conversation_context_without_retrieval(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    observed_contexts: list[str] = []

    def knowledge_controller(query: str, **kwargs: object) -> TurnDecision:
        del query, kwargs
        return TurnDecision(
            lane="knowledge",
            needs_retrieval=False,
            needs_memory=False,
            needs_template=False,
            confidence=1.0,
            reason="fixture knowledge follow-up",
        )

    def lane_answer(
        query: str,
        decision: TurnDecision,
        *,
        context: str,
        **kwargs: object,
    ) -> LaneAnswer:
        del decision, kwargs
        observed_contexts.append(context)
        return LaneAnswer(
            "卫星互联网依赖星座和地面站。"
            if "是什么" in query
            else "主要风险包括成本、容量和监管约束。"
        )

    for query in ("卫星互联网是什么", "它的风险呢"):
        run_id, assistant_message_id = _prepare_turn(
            conversation_store,
            run_store,
            conversation.conversation_id,
            query,
        )
        TurnOrchestrator(
            repo_root=tmp_path,
            conversation_store=conversation_store,
            run_store=run_store,
            answer_query_fn=lambda *_: pytest.fail(
                "knowledge follow-up must not retrieve"
            ),
            route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
                "knowledge follow-up must not route"
            ),
            skill_registry=SkillRegistry(),
            turn_controller_fn=knowledge_controller,
            lane_answer_fn=lane_answer,
        ).run_turn(
            conversation_id=conversation.conversation_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            query=query,
            skill_mode="auto",
            selected_skill_ids=[],
        )

    assert "无历史消息" in observed_contexts[0]
    assert "卫星互联网是什么" in observed_contexts[1]
    assert "卫星互联网依赖星座和地面站" in observed_contexts[1]
    assert len(observed_contexts[1]) <= SUMMARY_CHAR_LIMIT


def test_fresh_knowledge_retrieves_without_skill_router_or_memory(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "PQC最新消息",
    )
    calls: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        calls.append(options)
        result = _ask_result(options.query)
        result.sections = {
            "结论": ["PQC 正在推进标准迁移。"],
            "证据链": ["公开来源显示多项迁移计划正在执行。"],
        }
        return result

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "knowledge retrieval must skip skill router"
        ),
        skill_registry=SkillRegistry(),
        lane_answer_fn=lambda *_args, **_kwargs: LaneAnswer(
            "PQC 的最新进展集中在标准落地与迁移准备。"
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="PQC最新消息",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.content == "PQC 的最新进展集中在标准落地与迁移准备。"
    assert len(calls) == 1
    assert evidence_registry.provider_enabled(calls[0], "M") is False
    assert evidence_registry.provider_enabled(calls[0], "V") is False
    assert calls[0].question_type_override == "news_impact"
    assert calls[0].question_type_override != "concept_definition"
    route_step = next(
        step for step in run_store.load_trace(run_id) if step["name"] == "route_skills"
    )
    assert json.loads(route_step["output_summary"])["router_skipped"] is True


def test_three_turns_retrieve_fresh_and_include_bounded_context(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation("三轮测试")
    calls: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        calls.append(options)
        return _ask_result(options.query)

    parent_run_id = None
    run_ids: list[str] = []
    for query in (
        "第一轮：液冷怎么样？",
        "第二轮：证据够硬吗？",
        "第三轮：下一步看什么？",
    ):
        run_id, assistant_message_id = _prepare_turn(
            conversation_store, run_store, conversation.conversation_id, query
        )
        TurnOrchestrator(
            repo_root=tmp_path,
            conversation_store=conversation_store,
            run_store=run_store,
            answer_query_fn=answer_spy,
            skill_registry=SkillRegistry(),
            turn_controller_fn=_research_controller,
        ).run_turn(
            conversation_id=conversation.conversation_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            query=query,
            skill_mode="auto",
            selected_skill_ids=[],
        )
        run = run_store.load_run(run_id)
        assert run.session_id == conversation.conversation_id
        assert run.parent_run_id == parent_run_id
        parent_run_id = run_id
        run_ids.append(run_id)

    assert [call.query for call in calls] == [
        "第一轮：液冷怎么样？",
        "第二轮：证据够硬吗？",
        "第三轮：下一步看什么？",
    ]
    assert len(calls) == 3
    assert calls[0].perspective_mode == "neutral"
    assert calls[0].perspective_ids == ()
    assert calls[0].enabled_providers is None
    assert evidence_registry.provider_enabled(calls[0], "M") is True
    assert evidence_registry.provider_enabled(calls[0], "V") is True
    # 标题必须如实说是截断而非摘要：模型把「摘要」读成「已概括全部较早内容」，
    # 就不会知道最早那几轮已经不在了（ai-agent-book ch2：静默截断危险）。
    assert "较早消息（原文，超预算时从最早处截断）" in calls[1].conversation_context
    assert "第一轮：液冷怎么样？" in calls[1].conversation_context
    assert "第二轮：证据够硬吗？" not in calls[1].conversation_context
    assert "第一轮：液冷怎么样？" in calls[2].conversation_context
    assert "第二轮：证据够硬吗？" in calls[2].conversation_context
    assert [run_store.load_run(run_id).status for run_id in run_ids] == [
        "completed",
        "completed",
        "completed",
    ]
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.content.startswith("当前视角：数据中立")


def test_single_perspective_is_forwarded_and_labels_final_answer(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))

    perspective_lab.init_perspective(
        userspace.user_space("alice"),
        "fengyuan94",
        display_name="风远94",
        ptype="blogger",
    )
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "怎么看 AI 硬件",
    )
    calls: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        calls.append(options)
        return _ask_result(options.query)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="怎么看 AI 硬件",
        skill_mode="auto",
        selected_skill_ids=[],
        perspective_mode="single",
        selected_perspective_ids=["fengyuan94"],
    )

    assert calls[0].perspective_mode == "single"
    assert calls[0].perspective_ids == ("fengyuan94",)
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.content.startswith("当前视角：风远94")


def test_context_keeps_six_recent_messages_and_summarizes_older(tmp_path) -> None:
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    for index in range(10):
        store.append_message(
            conversation.conversation_id,
            "user" if index % 2 == 0 else "assistant",
            f"message-{index}",
            run_id=f"run-{index}",
        )

    context = build_conversation_context(
        conversation,
        store.load_messages(conversation.conversation_id),
        current_run_id="run-current",
    )

    assert [message.content for message in context.recent_messages] == [
        "message-4",
        "message-5",
        "message-6",
        "message-7",
        "message-8",
        "message-9",
    ]
    assert "message-0" in context.summary
    assert "message-3" in context.summary
    assert "message-4" not in context.summary


def test_contextualizes_pronoun_follow_up_with_previous_user_turn(tmp_path) -> None:
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    previous = store.append_message(
        conversation.conversation_id,
        "user",
        "请个股深挖英维克的液冷业务",
        run_id="run-first",
    )
    context = ConversationContext(summary="", recent_messages=(previous,))

    assert contextualize_follow_up_query(
        "那它的主要风险和下一步验证是什么？",
        context,
    ) == ("请个股深挖英维克的液冷业务\n追问：那它的主要风险和下一步验证是什么？")
    assert contextualize_follow_up_query("今天市场怎么样？", context) == (
        "今天市场怎么样？"
    )
    assert contextualize_follow_up_query(
        "把核心矛盾压成一句话，再列最强反证和翻转条件。",
        context,
    ) == (
        "请个股深挖英维克的液冷业务\n"
        "追问：把核心矛盾压成一句话，再列最强反证和翻转条件。"
    )

    for query in (
        "这个逻辑呢",
        "这个方向怎么看",
        "这条链有哪些公司",
        "边际变化呢",
    ):
        assert contextualize_follow_up_query(query, context) == (
            f"请个股深挖英维克的液冷业务\n追问：{query}"
        )


def test_complete_chain_question_is_not_contextualized(tmp_path) -> None:
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    previous = store.append_message(
        conversation.conversation_id,
        "user",
        "请个股深挖英维克的液冷业务",
        run_id="run-first",
    )
    context = ConversationContext(summary="", recent_messages=(previous,))
    query = "光模块产业链上游有哪些公司"

    assert contextualize_follow_up_query(query, context) == query


def test_artifact_sanitizer_hides_credentials_paths_and_internal_terms() -> None:
    no_llm = sanitize_user_visible_artifact_text(
        "未配置 LLM key。设置 DEEPSEEK_API_KEY / HF_TOKEN 即可启用"
    )
    internal = sanitize_user_visible_artifact_text(
        "wiki-rag replay canonical ask_retrieval_pipeline deterministic_projection"
    )
    local_path = sanitize_user_visible_artifact_text(
        'File "/Users/a77/repo/module.py", line 12, in run'
    )
    retrieval_progress = sanitize_user_visible_artifact_text(
        "检索降级：Fetching 30 files: 100% | Loading weights: 100%"
    )
    internal_module = sanitize_user_visible_artifact_text(
        "模块·deep-dive（产业维 · radar.py --mode deep-dive 题材深拆）"
    )
    evidence_detail = sanitize_user_visible_artifact_text(
        "target=天阳科技 source=[[天阳科技_最新逻辑跟踪]]，质量 medium"
    )
    module_id = sanitize_user_visible_artifact_text("research_5_telemetry")
    no_llm_code = sanitize_user_visible_artifact_text("llm_unavailable_template_answer")
    answer_route = sanitize_user_visible_artifact_text(
        "answer-orchestrator：未高置信识别问题类型"
    )
    market_internals = sanitize_user_visible_artifact_text(
        "本地 DuckDB + snapshot/export；MarketAdapter.get_capacity_sectors；"
        "capacity_industry=True；来源=knowledge_evidence"
    )

    assert no_llm == "自然语言综合暂时不可用；已保留可核验数据与结构化产物。"
    assert "API_KEY" not in no_llm
    assert "TOKEN" not in no_llm
    assert "wiki-rag" not in internal
    assert "replay" not in internal
    assert "canonical" not in internal
    assert "ask_retrieval_pipeline" not in internal
    assert "deterministic_projection" not in internal
    assert "/Users/" not in local_path
    assert "module.py" not in local_path
    # P0 修复后：诊断类文本只声明"已隐藏"，不得断言"检索不可用"（洗词不改事实）。
    assert retrieval_progress == "（内部检索诊断信息已隐藏。）"
    assert internal_module == "（内部检索诊断信息已隐藏。）"
    assert evidence_detail == "对象=天阳科技；来源=天阳科技_最新逻辑跟踪，质量中等"
    assert module_id == "资料覆盖情况"
    assert no_llm_code == "自然语言综合暂时不可用；已保留可核验数据与结构化产物。"
    assert answer_route == "问题理解：未高置信识别问题类型"
    assert market_internals == (
        "本地市场数据 + 历史盘面快照；本地盘面数据；"
        "成交容量居前=是；来源=知识库候选资料"
    )


def test_shadow_composer_writes_separate_artifacts_without_changing_answer(
    tmp_path,
    monkeypatch,
) -> None:
    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "总结行情",
    )
    contract = build_module_answer_contract(
        skill_id="fixture",
        title="可核验回答",
        modules=[
            {
                "module_id": "direct_assessment",
                "title": "直接定性",
                "summary": "生产答案保持不变。",
                "items": [],
            }
        ],
        citations=[
            {
                "source": "fixture.json",
                "title": "正式资料",
                "evidence_layer": "canonical",
                "as_of": "2026-07-16",
            }
        ],
        warnings=[],
        as_of="2026-07-16",
        retrieval_plan=("读取正式资料",),
        output_contract=("输出可核验结论",),
    )
    assert contract is not None

    def answer_spy(options: AskOptions) -> AskResult:
        result = _ask_result(options.query)
        result.answer_spec = contract.answer_spec
        return result

    def shadow_spy(prepared) -> AskResult:
        prepared.result.grounded_composer_shadow = answer_model.GroundedComposerShadow(
            status="accepted",
            decision_brief=answer_model.DecisionBrief(
                direct_answer="影子直接回答",
                core_tension="影子核心矛盾",
                supports=("fixture:direct_assessment",),
            ),
            raw_answer="影子原文",
            presented_answer="影子答案",
            provider="fixture",
            model="fixture-model",
            elapsed_ms=1,
        )
        return prepared.result

    monkeypatch.setenv("WORKBENCH_GROUNDED_PRESENTER", "0")
    monkeypatch.setenv("WORKBENCH_SHADOW_GROUNDED_COMPOSER", "1")
    monkeypatch.setattr(
        "intelligence.runtime.conversation_orchestrator."
        "synthesize_shadow_grounded_answer",
        shadow_spy,
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="总结行情",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    run_dir = run_store.run_dir(run_id)
    assert "生产答案保持不变" in result.content
    assert "影子答案" not in result.content
    assert (run_dir / "decision_brief.json").is_file()
    assert (run_dir / "grounded_composer_shadow.json").is_file()
    assert (run_dir / "grounded_composer_shadow.md").read_text(
        encoding="utf-8"
    ) == "影子答案"


def test_grounded_presenter_and_shadow_env_run_one_provider_chain(
    tmp_path,
    monkeypatch,
) -> None:
    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "液冷服务器现在怎么看？"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    research_spec = answer_model.resolve_theme_research_spec(
        "分析液冷服务器产业链"
    )
    claim = answer_model.make_claim(
        claim_id="market-1",
        text="涨幅与边际成交同步转强：涨幅2.61%，边际量18.28%。",
        claim_type="market_signal",
        theme=research_spec.theme,
        status=answer_model.ClaimStatus.VERIFIED,
        evidence_tier="L4",
        evidence_ids=("S1",),
    )
    spec = answer_model.AnswerSpec(
        research_spec=research_spec,
        summary=(),
        verified_facts=(claim,),
        company_table=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        next_actions=("核对公告。",),
        sources=(answer_model.EvidenceRef("S1", "盘面快照"),),
        system_notices=(),
    )
    atom = next(
        item
        for item in answer_model.evidence_atoms_from_answer_spec(spec)
        if item.provenance.get("claim_id") == claim.claim_id
    )
    composed = (
        "## 液冷服务器\n"
        "量价同步转强说明关注度正在升温。"
        f"<!-- claim_ids={claim.claim_id}; evidence_atom_ids={atom.atom_id}; "
        "claim_type=fact -->\n"
        "公司证据落地前仍应把它视作待验证信号。"
        f"<!-- claim_ids={claim.claim_id}; evidence_atom_ids={atom.atom_id}; "
        "claim_type=fact -->\n"
        "（非投资建议）"
    )
    judge = json.dumps(
        {"passed": True, "rejected_sentence_indexes": [], "issues": []},
        ensure_ascii=False,
    )
    provider_calls: list[dict[str, object]] = []

    def provider_boundary(_messages, **kwargs):
        answer = (composed, judge)[len(provider_calls) % 2]
        provider_calls.append(kwargs)
        return (
            llm_refine.SynthesisResult(answer, "fixture", "fixture-model"),
            "",
        )

    def answer_spy(options: AskOptions) -> AskResult:
        return AskResult(
            query=options.query,
            trade_date="2026-07-11",
            matched_theme="液冷服务器",
            candidate_tier="A",
            priority_score=1.0,
            answer_spec=spec,
            prepared_synthesis_messages=[{"role": "user", "content": "fixture"}],
        )

    monkeypatch.setenv("WORKBENCH_GROUNDED_PRESENTER", "1")
    monkeypatch.setenv("WORKBENCH_SHADOW_GROUNDED_COMPOSER", "1")
    monkeypatch.setattr(llm_refine, "synthesize_messages", provider_boundary)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert len(provider_calls) == 2
    shadow_trace = next(
        step
        for step in run_store.load_trace(run_id)
        if step["name"] == "grounded_composer_shadow"
    )
    payload = json.loads(shadow_trace["output_summary"])
    assert payload["status"] == "accepted"
    assert payload["reused_existing"] is True


def test_shadow_composer_non_presentable_status_keeps_diagnostics_only(
    tmp_path,
    monkeypatch,
) -> None:
    conversation_store = ConversationStore(
        "alice",
        root=tmp_path / "conversations",
    )
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "总结行情",
    )
    contract = build_module_answer_contract(
        skill_id="fixture",
        title="可核验回答",
        modules=[
            {
                "module_id": "direct_assessment",
                "title": "直接定性",
                "summary": "生产答案保持不变。",
                "items": [],
            }
        ],
        citations=[
            {
                "source": "fixture.json",
                "title": "正式资料",
                "evidence_layer": "canonical",
                "as_of": "2026-07-16",
            }
        ],
        warnings=[],
        as_of="2026-07-16",
        retrieval_plan=("读取正式资料",),
        output_contract=("输出可核验结论",),
    )
    assert contract is not None

    def answer_spy(options: AskOptions) -> AskResult:
        result = _ask_result(options.query)
        result.answer_spec = contract.answer_spec
        return result

    def shadow_spy(prepared) -> AskResult:
        prepared.result.grounded_composer_shadow = answer_model.GroundedComposerShadow(
            status="judge_unavailable",
            raw_answer="影子原文",
            presented_answer="不应落盘的影子答案",
            provider="fixture",
            model="fixture-model",
            failure_reason="timeout",
            elapsed_ms=1,
        )
        return prepared.result

    monkeypatch.setenv("WORKBENCH_GROUNDED_PRESENTER", "0")
    monkeypatch.setenv("WORKBENCH_SHADOW_GROUNDED_COMPOSER", "1")
    monkeypatch.setattr(
        "intelligence.runtime.conversation_orchestrator."
        "synthesize_shadow_grounded_answer",
        shadow_spy,
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="总结行情",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    run_dir = run_store.run_dir(run_id)
    assert "生产答案保持不变" in result.content
    assert (run_dir / "grounded_composer_shadow.json").is_file()
    assert not (run_dir / "grounded_composer_shadow.md").exists()


def test_primary_grounded_presenter_shadow_is_traced_without_the_experiment_flag(
    tmp_path,
    monkeypatch,
) -> None:
    """生产态（grounded_presenter on / shadow 实验 off）也必须落 trace。

    老写法把「要不要额外跑影子链」和「跑过了要不要记 trace」绑在同一个 if 上，
    门是 ``prepared.options.shadow_grounded_composer``——默认 False。而生产的影子
    记录是 ``promote_grounded_answer`` 内部用 ``replace(options, ...=True)`` 跑出来
    的，那是副本，外层选项没变。结果：trace 只覆盖默认关闭的实验模式，恰好漏掉
    真正驱动用户答案的那条路。2026-08-26 的 fail-open 因此只能靠重放归档件定位。
    """

    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "总结行情",
    )

    judge_report = answer_model.GroundingJudgeReport(
        passed=False,
        rejected_sentence_indexes=(2, 3),
        issues=("句2「越界表述」不成立", "句3 混入未绑定主体"),
    )

    def answer_spy(options: AskOptions) -> AskResult:
        # 模拟 promote_grounded_answer：主路径自己跑完影子链并挂在 result 上。
        result = _ask_result(options.query)
        result.grounded_composer_shadow = answer_model.GroundedComposerShadow(
            status="repaired",
            raw_answer="原文",
            repaired_answer="修后",
            presented_answer="上场稿",
            judge_report=judge_report,
            # 报了 (2, 3)，实际只执行了 (2,)——fail-open 的形状。
            judge_applied_sentence_indexes=(2,),
            provider="composer-provider",
            model="composer-model",
            judge_provider="grok-cli-judge",
            judge_model="grok-4.6",
            elapsed_ms=1,
        )
        return result

    def shadow_spy(prepared) -> AskResult:  # pragma: no cover - 不该被调用
        raise AssertionError("主路径已产出影子记录，不应再额外跑一次")

    monkeypatch.setenv("WORKBENCH_GROUNDED_PRESENTER", "1")
    monkeypatch.setenv("WORKBENCH_SHADOW_GROUNDED_COMPOSER", "0")
    monkeypatch.setattr(
        "intelligence.runtime.conversation_orchestrator."
        "synthesize_shadow_grounded_answer",
        shadow_spy,
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="总结行情",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    shadow_trace = next(
        step
        for step in run_store.load_trace(run_id)
        if step["name"] == "grounded_composer_shadow"
    )
    payload = json.loads(shadow_trace["output_summary"])
    assert payload["source"] == "primary_grounded_presenter"
    assert payload["reused_existing"] is True
    # 「报的」与「执行的」必须都在，且看得出不一致——这就是那次查了很久的东西。
    assert payload["judge_reported_sentence_indexes"] == [2, 3]
    assert payload["judge_applied_sentence_indexes"] == [2]
    # judge 的 provider 不能再借用 composer 的字段。
    assert payload["provider"] == "composer-provider"
    assert payload["judge_provider"] == "grok-cli-judge"
    assert payload["judge_model"] == "grok-4.6"


def test_market_question_automatically_selects_daily_review() -> None:
    registry = builtin_skill_registry()

    route = route_skills(
        "今天市场怎么样？",
        "ask",
        "auto",
        [],
        registry=registry.definitions,
        llm_complete=lambda _: (None, None, "fixture no llm"),
    )

    assert [selection.skill_id for selection in route.selections] == ["daily-review"]


def test_turn_routes_with_query_envelope_and_records_it_in_trace(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "指数上涨但涨停家数减少，是否背离？"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    routed: list[QueryEnvelope] = []

    def route_spy(
        routed_query: str,
        task_type: str,
        skill_mode: str,
        selected_skill_ids: list[str],
        *,
        registry: dict[str, SkillDefinition],
        query_envelope: QueryEnvelope,
    ) -> SkillRouteResult:
        assert routed_query == query
        assert task_type == "ask"
        assert skill_mode == "auto"
        assert selected_skill_ids == []
        assert registry == {}
        routed.append(query_envelope)
        return SkillRouteResult((), fallback_to_ask=False, base_finance_fallback=True)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        route_skills_fn=route_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert len(routed) == 1
    assert routed[0].subject_kind == "market_pattern"
    route_step = next(
        step for step in run_store.load_trace(run_id) if step["name"] == "route_skills"
    )
    route_output = json.loads(route_step["output_summary"])
    assert route_output["query_envelope"] == routed[0].to_dict()


def test_follow_up_persists_and_routes_inherited_turn_intent(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    previous_intent = TurnIntent(
        primary_subject="英维克",
        secondary_topics=("液冷",),
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        comparison_entities=(),
        inherited_from_turn=None,
        evidence_atom_ids=("atom-1",),
    )
    conversation_store.append_message(
        conversation.conversation_id,
        "user",
        "请个股深挖英维克的液冷业务",
        run_id="run-previous",
    )
    previous_assistant = conversation_store.append_message(
        conversation.conversation_id,
        "assistant",
        "上一轮回答",
        run_id="run-previous",
        invoked_skill_ids=["stock-deep-dive"],
        turn_intent=previous_intent.to_dict(),
    )
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "那它的客户和订单呢？",
    )
    routed: dict[str, object] = {}

    def route_spy(
        routed_query: str,
        task_type: str,
        skill_mode: str,
        selected_skill_ids: list[str],
        *,
        registry: dict[str, SkillDefinition],
        query_envelope: QueryEnvelope,
        answer_owner: str,
        inherited_skill_ids: tuple[str, ...],
    ) -> SkillRouteResult:
        routed.update(
            query=routed_query,
            task_type=task_type,
            skill_mode=skill_mode,
            selected_skill_ids=selected_skill_ids,
            registry=registry,
            query_envelope=query_envelope,
            answer_owner=answer_owner,
            inherited_skill_ids=inherited_skill_ids,
        )
        return SkillRouteResult(
            (),
            fallback_to_ask=False,
            base_finance_fallback=True,
        )

    def controller(query: str, **kwargs: object) -> TurnDecision:
        return decide_turn(
            query,
            context=str(kwargs.get("context") or ""),
            skill_mode=str(kwargs.get("skill_mode") or "auto"),
            selected_skill_ids=tuple(kwargs.get("selected_skill_ids") or ()),
            previous_intent=kwargs.get("previous_intent"),
            previous_turn_id=kwargs.get("previous_turn_id"),
            llm_complete=lambda _messages: (None, None, "fixture unavailable"),
        )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        route_skills_fn=route_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="那它的客户和订单呢？",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert routed["answer_owner"] == "stock-deep-dive"
    assert routed["inherited_skill_ids"] == ("stock-deep-dive",)
    assert str(routed["query"]).startswith("主体：英维克")
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.turn_intent is not None
    assert assistant.turn_intent["primary_subject"] == "英维克"
    assert assistant.turn_intent["answer_owner"] == "stock-deep-dive"
    assert assistant.turn_intent["inherited_from_turn"] == previous_assistant.message_id
    assert assistant.turn_intent["evidence_atom_ids"] == ["atom-1"]
    assert assistant.turn_intent["skill_ids"] == ["stock-deep-dive"]
    assert assistant.research_plan is not None
    assert assistant.research_plan["answer_owner"] == "stock-deep-dive"


class _FailingSkill:
    skill_id = "broken"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        raise RuntimeError("token=must-not-leak")


class _SuccessfulSkill:
    skill_id = "fixture"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        return SkillOutput(
            skill_id=self.skill_id,
            modules=[
                {
                    "module_id": "fixture_metric",
                    "title": "Fixture metric",
                    "kind": "metrics",
                    "status": "complete",
                    "summary": None,
                    "content": None,
                    "metrics": [{"label": "涨家数", "value": 3210}],
                    "items": [],
                    "table": None,
                    "warnings": [],
                    "provenance": {
                        "source": "canonical-fixture",
                        "as_of": "2026-07-11",
                    },
                }
            ],
            citations=[
                {
                    "source": "canonical-fixture",
                    "evidence_layer": "canonical",
                }
            ],
            warnings=[],
            as_of="2026-07-11",
            raw_result_ref="fixture.json",
        )


class _SecondSuccessfulSkill(_SuccessfulSkill):
    skill_id = "fixture-second"


def test_research_budget_skips_excess_skill_and_records_trace(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "执行专项研究",
        selected_skill_ids=["fixture", "fixture-second"],
    )
    registry = SkillRegistry()
    for skill_id, executor in (
        ("fixture", _SuccessfulSkill()),
        ("fixture-second", _SecondSuccessfulSkill()),
    ):
        registry.register(
            SkillDefinition(
                skill_id=skill_id,
                name=skill_id,
                description="fixture",
                version="1.0.0",
                triggers=("研究",),
                input_schema={"type": "object"},
                permissions=("local_read",),
                timeout_seconds=1,
            ),
            executor,
        )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=registry,
        turn_controller_fn=_research_controller,
        research_policy=ResearchExecutionPolicy(
            max_skill_calls=1,
            max_elapsed_seconds=60,
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="执行专项研究",
        skill_mode="manual",
        selected_skill_ids=["fixture", "fixture-second"],
    )

    assert result.invoked_skill_ids == ("fixture",)
    budget_step = next(
        step
        for step in run_store.load_trace(run_id)
        if step["name"] == "research_execution_budget"
    )
    budget = budget_step["retrieval"]["research_budget"]
    assert budget["call_count"] == 1
    assert budget["attempts"][1]["status"] == "skipped_budget"
    assert budget["attempts"][1]["provider"] == "skill_registry"
    assert "执行专项研究" in budget["attempts"][1]["input_summary"]


class _OverlapSkill:
    def __init__(
        self,
        skill_id: str,
        my_started: Event,
        peer_started: Event,
        spans: dict[str, tuple[float, float]],
    ) -> None:
        self.skill_id = skill_id
        self._my_started = my_started
        self._peer_started = peer_started
        self._spans = spans

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        started = time.monotonic()
        self._my_started.set()
        overlapped = self._peer_started.wait(timeout=2.0)
        self._spans[self.skill_id] = (started, time.monotonic())
        return SkillOutput(
            skill_id=self.skill_id,
            modules=[],
            citations=[],
            warnings=[] if overlapped else [f"{self.skill_id} 未观察到并行执行"],
            as_of="2026-07-11",
            raw_result_ref=None,
        )


def _run_overlap_turn(tmp_path) -> tuple[object, dict[str, tuple[float, float]]]:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "执行专项研究",
        selected_skill_ids=["overlap-a", "overlap-b"],
    )
    first_started = Event()
    second_started = Event()
    spans: dict[str, tuple[float, float]] = {}
    registry = SkillRegistry()
    for skill_id, executor in (
        ("overlap-a", _OverlapSkill("overlap-a", first_started, second_started, spans)),
        ("overlap-b", _OverlapSkill("overlap-b", second_started, first_started, spans)),
    ):
        registry.register(
            SkillDefinition(
                skill_id=skill_id,
                name=skill_id,
                description="fixture",
                version="1.0.0",
                triggers=("研究",),
                input_schema={"type": "object"},
                permissions=("local_read",),
                timeout_seconds=10,
            ),
            executor,
        )
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=registry,
        turn_controller_fn=_research_controller,
        research_policy=ResearchExecutionPolicy(
            max_skill_calls=3,
            max_elapsed_seconds=60,
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="执行专项研究",
        skill_mode="manual",
        selected_skill_ids=["overlap-a", "overlap-b"],
    )
    return result, spans


def test_routed_skills_execute_in_parallel_with_ordered_outputs(tmp_path) -> None:
    result, spans = _run_overlap_turn(tmp_path)

    # 两个 skill 必须真正并行（互相等到对方启动），且结果按路由顺序消费。
    assert result.invoked_skill_ids == ("overlap-a", "overlap-b")
    a_start, a_end = spans["overlap-a"]
    b_start, b_end = spans["overlap-b"]
    assert a_start < b_end and b_start < a_end


def test_parallel_skills_flag_off_falls_back_to_serial(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WORKBENCH_PARALLEL_SKILLS", "0")
    result, spans = _run_overlap_turn(tmp_path)

    assert result.invoked_skill_ids == ("overlap-a", "overlap-b")
    a_start, a_end = spans["overlap-a"]
    b_start, _ = spans["overlap-b"]
    assert b_start >= a_end


def test_compose_ask_options_share_wiki_rag_cache_scope(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "执行专项研究",
    )
    captured: list[AskOptions] = []

    def capture_ask(options: AskOptions) -> AskResult:
        captured.append(options)
        return _ask_result(options.query)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=capture_ask,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="执行专项研究",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert captured
    assert captured[0].wiki_rag_cache_scope == (f"alice:{conversation.conversation_id}")


def test_current_skill_output_is_injected_as_current_turn_evidence(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "结合日报回答",
        selected_skill_ids=["fixture"],
    )
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="fixture",
            name="Fixture",
            description="fixture",
            version="1.0.0",
            triggers=("日报",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
            role="terminal_owner",
            can_own_answer=True,
        ),
        _SuccessfulSkill(),
    )
    calls: list[AskOptions] = []

    def answer_spy(options: AskOptions) -> AskResult:
        calls.append(options)
        return _ask_result(options.query)

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=registry,
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="结合日报回答",
        skill_mode="manual",
        selected_skill_ids=["fixture"],
    )

    assert len(calls) == 1
    assert "指标：涨家数=3210" in calls[0].supplemental_evidence
    assert '"value": 3210' not in calls[0].supplemental_evidence
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.selected_skill_ids == ["fixture"]
    assert assistant.invoked_skill_ids == ["fixture"]
    assert assistant.citations[0]["evidence_layer"] == "canonical"


def test_skill_answer_owner_bypasses_generic_ask_and_renders_its_contract(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "使用专项研究",
        selected_skill_ids=["owner", "unused"],
    )

    class OwnerSkill:
        skill_id = "owner"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            modules = [
                {
                    "type": "summary",
                    "summary": "专项资料显示需求保持扩张",
                    "metrics": [{"label": "订单覆盖", "value": "80%"}],
                    "items": [
                        {
                            "title": "验证",
                            "summary": "仍需复核新增订单",
                            "next_action": "下一窗口复核新增订单。",
                        }
                    ],
                }
            ]
            citations = [
                {
                    "source": "owner.json",
                    "title": "专项正式资料",
                    "evidence_layer": "canonical",
                    "as_of": "2026-07-11",
                }
            ]
            return SkillOutput(
                skill_id=self.skill_id,
                modules=modules,
                citations=citations,
                warnings=[],
                as_of="2026-07-11",
                raw_result_ref=None,
                answer_contract=replace(
                    build_module_answer_contract(
                        skill_id=self.skill_id,
                        title="专项研究",
                        modules=modules,
                        citations=citations,
                        warnings=[],
                        as_of="2026-07-11",
                        retrieval_plan=("读取专项正式资料",),
                        output_contract=("输出五元素裁决",),
                    ),
                    question_type="general_finance_qa",
                ),
            )

    class UnusedSkill:
        skill_id = "unused"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            del context
            raise AssertionError("later skills must stop after answer owner")

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="owner",
            name="Owner",
            description="answer owner",
            version="1.0.0",
            triggers=("专项",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
            role="terminal_owner",
            can_own_answer=True,
        ),
        OwnerSkill(),
    )
    registry.register(
        SkillDefinition(
            skill_id="unused",
            name="Unused",
            description="must not run after answer owner completes",
            version="1.0.0",
            triggers=("专项",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        UnusedSkill(),
    )

    def forbidden_answer_query(options: AskOptions) -> AskResult:
        raise AssertionError("answer owner must bypass generic Ask")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden_answer_query,
        skill_registry=registry,
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="使用专项研究",
        skill_mode="manual",
        selected_skill_ids=["owner", "unused"],
    )

    assert result.status == "completed"
    assert result.invoked_skill_ids == ("owner",)
    assert "# 专项研究" in result.content
    assert "**直接定性：**" in result.content
    assert "**最强证据：**" in result.content
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert "llm_unavailable_template_answer" not in assistant.degrades
    assert 3 <= len(assistant.followups) <= 4
    assert (run_store.run_dir(run_id) / "answer_spec.json").is_file()
    assert (run_store.run_dir(run_id) / "followups.json").is_file()
    retrieval = next(
        step["retrieval"]
        for step in run_store.load_trace(run_id)
        if step["name"] == "ask_retrieve_compose"
    )
    assert retrieval["citations"][0]["source"] == "专项正式资料"
    assert retrieval["citation_counts"] == {"K": 1}
    snapshots = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "answer.snapshot"
    ]
    assert [event["payload"]["revision"] for event in snapshots] == [1, 2]
    assert [event["payload"]["phase"] for event in snapshots] == [
        "verified_draft",
        "verified_fallback",
    ]
    assert snapshots[-1]["payload"]["text"] == result.content


def test_specialized_owner_uses_same_task_frame_fulfillment_gate(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "那它的客户和订单呢"
    frame = TaskFrame(
        raw_question=query,
        user_goal="继续核验英维克的客户与订单证据",
        question_type="stock_deep_dive",
        subject="英维克",
        subject_kind="company",
        market_scope="A股",
        timeframe=None,
        required_outputs=("customer_validation", "supporting_evidence"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_multi_layer_evidence",
        confidence=0.98,
    )
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
        selected_skill_ids=["stock-deep-dive"],
    )

    class SpecializedOwner:
        skill_id = "stock-deep-dive"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            assert context.task_frame == frame
            modules = [
                {
                    "module_id": "industry_lead",
                    "title": "行业线索",
                    "summary": "目前只发现行业需求线索，未取得英维克客户或订单公告。",
                }
            ]
            citations = [
                {
                    "source": "industry-note.md",
                    "title": "行业资料",
                    "evidence_layer": "L1",
                    "as_of": "2026-07-22",
                }
            ]
            contract = build_module_answer_contract(
                skill_id=self.skill_id,
                title="英维克专项研究",
                modules=modules,
                citations=citations,
                warnings=[],
                as_of="2026-07-22",
                retrieval_plan=("检索公司公告与订单证据",),
                output_contract=frame.required_outputs,
            )
            assert contract is not None
            return SkillOutput(
                skill_id=self.skill_id,
                modules=modules,
                citations=citations,
                warnings=[],
                as_of="2026-07-22",
                raw_result_ref=None,
                answer_contract=replace(
                    contract,
                    question_type="stock_deep_dive",
                    task_frame_hash=frame.task_frame_hash,
                    required_outputs=(
                        *frame.required_outputs,
                        "llm_invented_output",
                    ),
                ),
            )

    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            skill_id="stock-deep-dive",
            name="个股深挖",
            description="specialized owner fixture",
            version="1.0.0",
            triggers=("客户", "订单"),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
            role="terminal_owner",
            accepted_question_types=("stock_deep_dive",),
            can_own_answer=True,
        ),
        SpecializedOwner(),
    )

    def controller(_query: str, **_kwargs: object) -> TurnDecision:
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=True,
            needs_template=True,
            question_type="stock_deep_dive",
            subject="英维克",
            confidence=1.0,
            reason="fixture specialized owner",
            task_frame=frame,
        )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda _options: pytest.fail(
            "specialized owner must bypass generic Ask"
        ),
        skill_registry=registry,
        turn_controller_fn=controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="manual",
        selected_skill_ids=["stock-deep-dive"],
    )

    trace = run_store.load_trace(run_id)
    route = json.loads(
        next(step for step in trace if step["name"] == "route_skills")["output_summary"]
    )
    owner_contract = json.loads(
        next(step for step in trace if step["name"] == "skill_answer_owner")[
            "output_summary"
        ]
    )
    verifier = json.loads(
        next(step for step in trace if step["name"] == "task_fulfillment")[
            "output_summary"
        ]
    )
    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )

    assert route["task_frame_hash"] == frame.task_frame_hash
    assert owner_contract["task_frame_hash"] == frame.task_frame_hash
    assert owner_contract["required_outputs"] == [
        *frame.required_outputs,
        "llm_invented_output",
    ]
    assert verifier["task_frame_hash"] == frame.task_frame_hash
    assert report["task_frame_hash"] == frame.task_frame_hash
    assert report["answer_status"] != "complete"
    customer = next(
        item
        for item in report["task_fulfillment"]["items"]
        if item["output_id"] == "customer_validation"
    )
    assert customer["status"] != "fulfilled"
    assert "llm_invented_output" not in {
        item["output_id"] for item in report["task_fulfillment"]["items"]
    }
    assert "本轮尚未完成问题所需的直接回答" in result.content


def test_cancellation_after_draft_keeps_last_safe_snapshot(
    tmp_path, monkeypatch
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "取消精修",
    )
    contract = build_module_answer_contract(
        skill_id="fixture",
        title="可核验回答",
        modules=[
            {
                "module_id": "direct_assessment",
                "title": "直接定性",
                "summary": "当前证据只支持谨慎判断。",
                "items": [],
            }
        ],
        citations=[
            {
                "source": "fixture.json",
                "title": "正式资料",
                "evidence_layer": "canonical",
                "as_of": "2026-07-11",
            }
        ],
        warnings=[],
        as_of="2026-07-11",
        retrieval_plan=("读取正式资料",),
        output_contract=("输出可核验结论",),
    )
    assert contract is not None

    def answer_spy(options: AskOptions) -> AskResult:
        result = _ask_result(options.query)
        result.answer_spec = contract.answer_spec
        result.prepared_synthesis_messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "evidence"},
        ]
        return result

    monkeypatch.setattr(
        "intelligence.runtime.conversation_orchestrator.synthesize_prepared_answer",
        lambda prepared: (_ for _ in ()).throw(llm_refine.LLMStreamCancelled()),
    )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="取消精修",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    snapshots = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "answer.snapshot"
    ]
    assert [snapshot["payload"]["phase"] for snapshot in snapshots] == [
        "verified_draft",
        "verified_fallback",
    ]
    assert result.status == "cancelled"
    assert result.content == snapshots[-1]["payload"]["text"]
    answer_artifact = next(
        artifact
        for artifact in run_store.load_run(run_id).artifacts
        if artifact["path"] == "answer.md"
    )
    assert (run_store.run_dir(run_id) / answer_artifact["path"]).read_text(
        encoding="utf-8"
    ) == result.content


def test_skill_failure_degrades_only_its_module_and_ask_still_completes(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "继续检索",
        selected_skill_ids=["broken"],
    )
    registry = SkillRegistry()
    registry.register(
        definition=SkillDefinition(
            skill_id="broken",
            name="Broken",
            description="fixture",
            version="1.0.0",
            triggers=("broken",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=1,
        ),
        executor=_FailingSkill(),
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=registry,
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="继续检索",
        skill_mode="manual",
        selected_skill_ids=["broken"],
    )

    run = run_store.load_run(run_id)
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    skill_result = next(
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "skill.result"
    )
    assert run.status == "completed"
    assert assistant.status == "completed"
    assert assistant.invoked_skill_ids == ["broken"]
    assert any("broken" in warning for warning in assistant.degrades)
    assert "must-not-leak" not in json.dumps(asdict(assistant), ensure_ascii=False)
    assert skill_result["payload"]["status"] == "degraded"


def test_owner_timeout_returns_partial_without_starting_generic_pipeline(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "请个股深挖英维克的液冷业务"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )

    # 时序余量三不等式（R-20260827-11）：本测试锁的契约是「统一截止时间在
    # skill 执行中掐断 → 部分完成 + 不启动第二套管线」。要让这个形状与进程
    # 冷暖、执行序、机器负载无关，三个量必须满足：
    #   ① 预算 >> 调 skill 前的编排开销（configure→controller→plan→route→
    #     retrieve 冷态实测 ~0.4s；旧值 0.1s 会在 skill 启动前烧完预算，
    #     invoked=()——单跑红、被暖场测试 prime 后绿的隔离缺陷即源于此）；
    #   ② owner sleep > 预算（保证截止一定在执行中到来）；
    #   ③ skill 自身 timeout > 预算（保证掐断者是统一截止，不是 skill 超时）。
    class SlowOwner:
        skill_id = "stock-deep-dive"

        def execute(self, context: SkillExecutionContext) -> SkillOutput:
            assert context.deadline is not None
            time.sleep(3.0)
            return SkillOutput(
                skill_id=self.skill_id,
                modules=[],
                citations=[],
                warnings=[],
                as_of=None,
                raw_result_ref=None,
            )

    registry = SkillRegistry()
    registry.register(
        definition=SkillDefinition(
            skill_id="stock-deep-dive",
            name="Stock Deep Dive",
            description="fixture owner",
            version="1.0.0",
            triggers=("个股深挖",),
            input_schema={"type": "object"},
            permissions=("local_read",),
            timeout_seconds=30,
        ),
        executor=SlowOwner(),
    )

    def forbidden_answer_query(options: AskOptions) -> AskResult:
        raise AssertionError("owner timeout must not start generic full pipeline")

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=forbidden_answer_query,
        skill_registry=registry,
        research_policy=ResearchExecutionPolicy(
            max_skill_calls=3,
            max_elapsed_seconds=2.0,
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.status == "completed"
    assert result.invoked_skill_ids == ("stock-deep-dive",)
    assert "未启动第二套完整问答流程" in result.content
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert any("stock-deep-dive 执行超时" in item for item in assistant.degrades)


def test_auto_mode_reroutes_after_skill_failure_within_budget(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "继续检索",
    )
    registry = SkillRegistry()
    for skill_id, executor in (
        ("broken", _FailingSkill()),
        ("fixture", _SuccessfulSkill()),
    ):
        registry.register(
            definition=SkillDefinition(
                skill_id=skill_id,
                name=skill_id,
                description="fixture",
                version="1.0.0",
                triggers=(),
                input_schema={"type": "object"},
                permissions=("local_read",),
                timeout_seconds=1,
            ),
            executor=executor,
        )
    route_calls: list[dict[str, object]] = []

    def adaptive_route(*args: object, **kwargs: object) -> SkillRouteResult:
        del args
        route_calls.append(kwargs)
        if kwargs.get("excluded_skill_ids"):
            return SkillRouteResult(
                selections=(SkillSelection("fixture", "llm", "失败后切换证据路径"),),
                fallback_to_ask=False,
            )
        return SkillRouteResult(
            selections=(SkillSelection("broken", "llm", "首选路径"),),
            fallback_to_ask=False,
        )

    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        route_skills_fn=adaptive_route,
        skill_registry=registry,
        turn_controller_fn=_research_controller,
        research_policy=ResearchExecutionPolicy(
            max_skill_calls=2,
            max_elapsed_seconds=60,
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="继续检索",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert result.invoked_skill_ids == ("broken", "fixture")
    assert route_calls[1]["excluded_skill_ids"] == ("broken",)
    feedback = route_calls[1]["execution_feedback"]
    assert feedback[0]["skill_id"] == "broken"
    assert feedback[0]["status"] == "failed"
    assert any(
        step["name"] == "route_skills_after_tool_failure"
        for step in run_store.load_trace(run_id)
    )


def test_cooperative_cancellation_preserves_completed_skill_events(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store, run_store, conversation.conversation_id, "取消本轮"
    )
    cancelled = Event()

    def route_then_cancel(*args: object, **kwargs: object) -> SkillRouteResult:
        cancelled.set()
        return SkillRouteResult(
            selections=(SkillSelection("daily-review", "rule", "fixture"),),
            fallback_to_ask=False,
        )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: pytest.fail("取消后不应检索"),
        route_skills_fn=route_then_cancel,
        turn_controller_fn=_research_controller,
        is_cancelled=cancelled.is_set,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="取消本轮",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert run_store.load_run(run_id).status == "cancelled"
    assert assistant.status == "cancelled"
    assert any(
        event["event_type"] == "message.error"
        and event["payload"]["status"] == "cancelled"
        for event in run_store.load_stream_events(run_id)
    )


def test_template_answer_is_saved_and_streamed_once_without_llm(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "无 key 也要回答",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="无 key 也要回答",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    text_events = [
        event
        for event in run_store.load_stream_events(run_id)
        if event["event_type"] == "text.delta"
    ]
    run = run_store.load_run(run_id)
    assert len(text_events) == 1
    assert "自然语言综合暂时不可用" in text_events[0]["payload"]["delta"]
    assert "命中主题" not in text_events[0]["payload"]["delta"]
    assert [artifact["path"] for artifact in run.artifacts] == [
        "answer.md",
        "report.json",
    ]
    assert "llm_unavailable_template_answer" in run.degrades


def test_successful_llm_report_persists_selected_model(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "真实模型回答",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(
            options.query,
            synthesis="真实模型输出",
            llm_provider="zhipu",
        ),
        skill_registry=SkillRegistry(),
        llm_model="glm-4-flash",
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="真实模型回答",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    assert report["llm"] == {
        "used": True,
        "provider": "zhipu",
        "model": "glm-4-flash",
    }


def test_recovered_turn_prefixes_event_ids_to_avoid_replay_collisions(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "恢复后继续",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=SkillRegistry(),
        event_id_prefix="recovery:2:",
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="恢复后继续",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    events = run_store.load_stream_events(run_id)
    assert events
    assert all(event["event_id"].startswith("recovery:2:") for event in events)


def test_completed_stream_persists_human_readable_answer(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "今日复盘",
    )
    raw_answer = (
        "**数据截至 2026-07-10。**\n\n"
        "以下基于 Daily Review 确定性投影数据。盘面 L4 信号待确认，"
        "replay 发酵信号也未匹配到任何主题，wiki 向量检索无可用命中。"
        "公司只有 graph_only/低置信暴露，整体证据层分布为 "
        "L1×6、L2×6、L4×1，尚缺 L3 硬证据。[D4]"
        "本轮未命中任何 L3硬证据硬证据。优先走 L3 证据工具补查。"
        "本轮检索完全未命中任何 L3硬证据的硬证据。"
        "8 个被 daily-agent 标记需要补证据的方向。"
        "当前属于 high/L1_L3_candidate，L1/L2 认知完整但 "
        "分析基于 local Daily Review 确定性投影，知识图谱命中的概念。"
        "证据以 L1行业资料和 L2公司基础资料为主，也有 L2基础资料。"
        "未取到 L3公告/订单/认证/量产等硬证据，盘面 L4盘面信号待确认。"
        "当日日报指标来自本地数据库的确定性投影。"
        "cycle_status 仍需确认，RAG检索的wiki向量源降级未接入。"
    )

    def answer_spy(options: AskOptions) -> AskResult:
        assert options.stream_text_delta is not None
        options.stream_text_delta(raw_answer)
        return _ask_result(
            options.query,
            synthesis=raw_answer,
            llm_provider="zhipu",
        )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="今日复盘",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.content == (
        "当前视角：数据中立\n"
        "来源范围：数据提供方、公开来源与本轮检索证据\n\n"
        f"{sanitize_conversation_answer(raw_answer)}"
    )
    assert "2026-07-10" in assistant.content
    assert "本地复盘数据" in assistant.content
    assert "历史发酵信号" in assistant.content
    assert "知识库没有提供可用补充" in assistant.content
    assert "候选资料，需公告或年报确认" in assistant.content
    assert "L1_L3_candidate" not in assistant.content
    assert "行业资料/公司基础资料" in assistant.content
    assert "阶段状态" in assistant.content
    assert "知识库资料没有提供可用补充" in assistant.content
    assert "公告等硬证据工具" in assistant.content
    assert "硬证据证据" not in assistant.content
    assert "硬证据硬证据" not in assistant.content
    assert "公告等硬证据的硬证据" not in assistant.content
    assert "每日复盘流程标记需要补证据" in assistant.content
    assert "本地复盘数据" in assistant.content
    assert "知识图谱关联到的概念" in assistant.content
    assert "local" not in assistant.content.lower()
    assert "确定性投影" not in assistant.content
    assert "知识知识图谱" not in assistant.content
    assert "行业资料行业资料" not in assistant.content
    assert "公司基础资料公司基础资料" not in assistant.content
    assert "公司基础资料基础资料" not in assistant.content
    assert "公告等硬证据公告" not in assistant.content
    assert "盘面信号盘面信号" not in assistant.content
    assert "盘面盘面信号" not in assistant.content
    assert (
        sanitize_conversation_answer("盘面信号_market_signal：等待确认")
        == "盘面信号：等待确认"
    )
    assert "证据以行业资料和公司基础资料为主" in assistant.content
    assert "也有公司基础资料" in assistant.content
    assert "未取到公告/订单/认证/量产等硬证据" in assistant.content
    assert "当日日报指标来自本地数据库的数据" in assistant.content
    for internal in (
        "Daily Review",
        "daily-agent",
        "L1",
        "L2",
        "L3",
        "L4",
        "replay",
        "wiki",
        "graph_only",
        "high/L1_L3_candidate",
        "cycle_status",
        "RAG",
        "[D4]",
    ):
        assert internal not in assistant.content


def test_cancellation_between_text_deltas_marks_run_cancelled(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "流式取消",
    )
    cancelled = Event()

    def answer_spy(options: AskOptions) -> AskResult:
        assert options.stream_text_delta is not None
        options.stream_text_delta("已完成片段")
        cancelled.set()
        options.stream_text_delta("不应落盘")
        return _ask_result(options.query, synthesis="已完成片段不应落盘")

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
        is_cancelled=cancelled.is_set,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="流式取消",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert run_store.load_run(run_id).status == "cancelled"
    assert assistant.content == "已完成片段"
    assert assistant.status == "cancelled"


class _StreamingResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_openai_compatible_stream_forwards_real_provider_deltas(monkeypatch) -> None:
    provider = llm_refine.LLMProvider(
        "fixture", "key", "https://llm.invalid/v1", "model"
    )
    body = (
        b'data: {"choices":[{"delta":{"content":"real "}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"delta"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.setattr(
        llm_refine.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _StreamingResponse(body),
    )
    deltas: list[str] = []

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=deltas.append,
    )

    assert reason == ""
    assert result is not None
    assert result.answer == "real delta"
    assert deltas == ["real ", "delta"]


def test_synthesis_stream_payload_bounds_thinking_and_tokens(monkeypatch) -> None:
    provider = llm_refine.LLMProvider(
        "fixture", "key", "https://llm.invalid/v1", "model"
    )
    captured: dict[str, object] = {}
    body = (
        b'data: {"choices":[{"delta":{"content":"bounded"},"finish_reason":"stop"}]}\n\n'
        b"data: [DONE]\n\n"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.delenv("LLM_THINKING", raising=False)
    monkeypatch.delenv("LLM_SYNTHESIS_THINKING", raising=False)

    def fake_urlopen(request, *args, **kwargs):
        del args, kwargs
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _StreamingResponse(body)

    monkeypatch.setattr(llm_refine.urllib.request, "urlopen", fake_urlopen)

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=lambda _: None,
    )

    assert reason == ""
    assert result is not None
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["payload"]["max_tokens"] == 3000


def test_synthesis_stream_length_finish_reason_fails_closed(monkeypatch) -> None:
    provider = llm_refine.LLMProvider(
        "fixture", "key", "https://llm.invalid/v1", "model"
    )
    body = (
        b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":"length"}]}\n\n'
        b"data: [DONE]\n\n"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.setattr(
        llm_refine.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _StreamingResponse(body),
    )
    deltas: list[str] = []
    finish_reasons: list[str | None] = []

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=deltas.append,
        on_finish_reason=finish_reasons.append,
    )

    assert result is None
    assert "截断" in reason
    assert deltas == ["partial"]
    assert finish_reasons == ["length"]


def test_synthesis_stream_output_too_long_fails_closed(monkeypatch) -> None:
    provider = llm_refine.LLMProvider(
        "fixture", "key", "https://llm.invalid/v1", "model"
    )
    body = (
        b'data: {"choices":[{"delta":{"content":"too-long"},"finish_reason":"stop"}]}\n\n'
        b"data: [DONE]\n\n"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.setattr(
        llm_refine.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _StreamingResponse(body),
    )
    deltas: list[str] = []

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=deltas.append,
        max_chars=3,
    )

    assert result is None
    assert "输出超长" in reason
    assert deltas == []


def test_openai_stream_checks_cancellation_between_provider_deltas(
    monkeypatch,
) -> None:
    provider = llm_refine.LLMProvider(
        "fixture", "key", "https://llm.invalid/v1", "model"
    )
    body = (
        b'data: {"choices":[{"delta":{"content":"first"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"second"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.setattr(
        llm_refine.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _StreamingResponse(body),
    )
    cancelled = Event()
    deltas: list[str] = []

    def on_delta(delta: str) -> None:
        deltas.append(delta)
        cancelled.set()

    with pytest.raises(llm_refine.LLMStreamCancelled):
        llm_refine.synthesize_messages_stream(
            [{"role": "user", "content": "question"}],
            on_delta=on_delta,
            is_cancelled=cancelled.is_set,
        )

    assert deltas == ["first"]


def test_openai_stream_closes_blocking_response_at_absolute_deadline(
    monkeypatch,
) -> None:
    provider = llm_refine.LLMProvider(
        "fixture", "key", "https://llm.invalid/v1", "model"
    )

    class BlockingResponse:
        def __init__(self) -> None:
            self.closed = Event()

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            self.close()

        def __iter__(self):
            return self

        def __next__(self) -> bytes:
            self.closed.wait(1)
            raise ValueError("response closed")

        def close(self) -> None:
            self.closed.set()

    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.setattr(
        llm_refine.urllib.request,
        "urlopen",
        lambda *args, **kwargs: BlockingResponse(),
    )
    started_at = time.monotonic()

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=lambda _: None,
        deadline=llm_refine.Deadline.from_timeout(0.02),
    )

    assert result is None
    assert "共享截止时间" in reason
    assert time.monotonic() - started_at < 0.5


def test_stream_unsupported_falls_back_to_one_complete_delta(monkeypatch) -> None:
    provider = llm_refine.LLMProvider(
        "fixture", "key", "https://llm.invalid/v1", "model"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    unsupported = urllib.error.HTTPError(
        "https://llm.invalid/v1/chat/completions",
        422,
        "stream unsupported",
        {},
        None,
    )
    monkeypatch.setattr(
        llm_refine,
        "_post_chat_stream",
        lambda *args, **kwargs: (_ for _ in ()).throw(unsupported),
    )
    monkeypatch.setattr(
        llm_refine,
        "_post_chat_synthesis",
        lambda *args, **kwargs: ("whole answer", "stop"),
    )
    deltas: list[str] = []

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=deltas.append,
    )

    assert reason == ""
    assert result is not None
    assert result.answer == "whole answer"
    assert deltas == ["whole answer"]
    assert result.fallback_reason == "stream_unsupported"


def test_stream_fallback_is_refused_after_any_output(monkeypatch) -> None:
    """已经吐过字就不许回退非流式——回退会把整段答案再发一次，用户看到重复正文。

    这是 ch06b 事故 inc-4258（回退导致工具双执行）在我们这条路径上的形状。当前
    触发不了（HTTPError 只在首个 delta 之前抛），这条测试钉的是「以后也别能触发」。
    """
    provider = llm_refine.LLMProvider(
        "fixture", "key", "https://llm.invalid/v1", "model"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    unsupported = urllib.error.HTTPError(
        "https://llm.invalid/v1/chat/completions",
        422,
        "stream unsupported",
        {},
        None,
    )

    def partial_then_fail(
        provider, messages, timeout, temperature, on_delta, *args, **kwargs
    ):
        del provider, messages, timeout, temperature, args, kwargs
        on_delta("已经吐出去的半句")
        raise unsupported

    monkeypatch.setattr(llm_refine, "_post_chat_stream", partial_then_fail)
    retried: list[int] = []

    def forbidden_retry(*args, **kwargs):
        del args, kwargs
        retried.append(1)
        return "whole answer", "stop"

    monkeypatch.setattr(llm_refine, "_post_chat_synthesis", forbidden_retry)
    deltas: list[str] = []

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=deltas.append,
    )

    assert result is None
    assert "不回退非流式" in reason
    assert retried == [], "已经输出过就不该再打一次非流式"
    assert deltas == ["已经吐出去的半句"], "用户不能看到重复正文"


def test_stream_fallback_uses_only_remaining_deadline(monkeypatch) -> None:
    provider = llm_refine.LLMProvider(
        "fixture", "key", "https://llm.invalid/v1", "model"
    )
    monkeypatch.setattr(llm_refine, "detect_provider", lambda *_: provider)
    monkeypatch.setattr(
        llm_refine,
        "_post_chat_stream",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            llm_refine.LLMStreamingUnsupported()
        ),
    )
    observed: list[float] = []

    def fake_post_chat(provider, messages, timeout, temperature, *args, **kwargs):
        del provider, messages, temperature
        del args, kwargs
        observed.append(timeout)
        return "whole answer", "stop"

    monkeypatch.setattr(llm_refine, "_post_chat_synthesis", fake_post_chat)
    # 用真 Deadline 而不是手搓替身：调用点会读 expires_at / call_timeout /
    # require_remaining，替身每次跟不上就变成测 AttributeError（已经发生两次）。
    # 本例要守的是「回退用的是剩余预算，不是调用方给的 30 秒」。
    deadline = llm_refine.Deadline.from_timeout(2.2)

    result, reason = llm_refine.synthesize_messages_stream(
        [{"role": "user", "content": "question"}],
        on_delta=lambda _: None,
        timeout=30,
        deadline=deadline,
    )

    assert reason == ""
    assert result is not None
    # 关键是「远小于调用方传的 30」，不是某个精确小数。
    assert len(observed) == 1
    assert observed[0] == pytest.approx(2.0, abs=0.3)


def test_message_revision_keeps_jsonl_append_only_but_loads_latest_state(
    tmp_path,
) -> None:
    store = ConversationStore("alice", root=tmp_path)
    conversation = store.create_conversation()
    pending = store.append_message(
        conversation.conversation_id,
        "assistant",
        "",
        status="pending",
        run_id="run-1",
    )

    completed = store.revise_message(
        conversation.conversation_id,
        pending.message_id,
        content="最终回答",
        status="completed",
        invoked_skill_ids=["daily-review"],
    )

    assert store.load_messages(conversation.conversation_id) == [completed]
    raw_lines = (
        (tmp_path / conversation.conversation_id / "messages.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert [json.loads(line)["message_id"] for line in raw_lines] == [
        pending.message_id,
        pending.message_id,
    ]


def test_sanitize_humanizes_stage_ids_and_internal_codes() -> None:
    assert (
        sanitize_conversation_answer("- 还缺：company_mapping 超过阶段时限 20 秒")
        == "- 还缺：公司映射超过阶段时限 20 秒"
    )
    assert (
        sanitize_conversation_answer("- 还缺：D6 中期趋势库不存在")
        == "- 还缺：中期趋势库不存在"
    )
    assert (
        sanitize_conversation_answer("- 还缺：D8 历史类比库不存在")
        == "- 还缺：历史类比库不存在"
    )
    assert sanitize_conversation_answer("D6 中期趋势库不存在") == "中期趋势库不存在"


def test_base_finance_fallback_grants_web_search_capability(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    # 注：不能用技术位类问题（如“科创50的支撑点位在哪”）——该题型已被
    # market_technical 确定性接管、跳过语义 skill router，触发不了本测试
    # 要验证的 base_finance_fallback 能力授予路径。
    query = "白酒板块最近怎么看"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    captured: list[AskOptions] = []

    def capture_options(options: AskOptions) -> AskResult:
        captured.append(options)
        return _ask_result(options.query)

    def quote_controller(controller_query: str, **kwargs: object) -> TurnDecision:
        del kwargs
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=False,
            needs_template=True,
            confidence=0.85,
            reason=f"fixture research: {controller_query}",
            capabilities=("market_quote", "graph"),
        )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=capture_options,
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult(
            (), fallback_to_ask=False, base_finance_fallback=True
        ),
        skill_registry=SkillRegistry(),
        turn_controller_fn=quote_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert len(captured) == 1
    assert captured[0].controller_capabilities == (
        "market_quote",
        "graph",
        "web_search",
    )
    # needs_memory=False 必须真关 M/V，不能只停在 helper 单测。
    assert evidence_registry.provider_enabled(captured[0], "M") is False
    assert evidence_registry.provider_enabled(captured[0], "V") is False
    assert evidence_registry.provider_enabled(captured[0], "D0") is True


def test_market_forecast_head_route_does_not_enable_long_tail_agent(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "我希望你基于目前的市场数据，展望一下后面市场会怎么演绎"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    captured: list[AskOptions] = []

    def capture_options(options: AskOptions) -> AskResult:
        captured.append(options)
        return _ask_result(options.query)

    def forecast_controller(
        controller_query: str,
        **kwargs: object,
    ) -> TurnDecision:
        del kwargs
        return TurnDecision(
            lane="research",
            needs_retrieval=True,
            needs_memory=True,
            needs_template=True,
            question_type="market_forecast",
            confidence=0.92,
            reason=f"fixture forecast: {controller_query}",
            capabilities=("memory", "market_quote", "graph"),
        )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=capture_options,
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult(
            (), fallback_to_ask=False, base_finance_fallback=True
        ),
        skill_registry=SkillRegistry(),
        turn_controller_fn=forecast_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    assert len(captured) == 1
    assert captured[0].question_type_override == "market_forecast"
    assert captured[0].controller_capabilities == (
        "memory",
        "market_quote",
        "graph",
    )


def test_ask_watchdog_returns_partial_and_suppresses_late_progress(
    tmp_path,
) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "我希望你基于目前的市场数据，展望一下后面市场会怎么演绎"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    release_worker = Event()
    worker_started = Event()
    late_progress_sent = Event()

    def blocking_answer(options: AskOptions) -> AskResult:
        assert llm_refine.current_call_ledger() is not None
        assert options.progress_callback is not None
        assert options.stream_cancel_check is not None
        assert options.stream_text_delta is not None
        assert not options.stream_cancel_check()
        options.progress_callback("agent_loop", "started", {"tool_count": 7})
        worker_started.set()
        release_worker.wait(timeout=2)
        assert options.stream_cancel_check()
        options.stream_text_delta("不应写入的迟到片段")
        options.progress_callback("agent_loop", "completed", {"tool_count": 7})
        late_progress_sent.set()
        return _ask_result(options.query)

    started = time.monotonic()
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=blocking_answer,
        route_skills_fn=lambda *args, **kwargs: SkillRouteResult(
            (), fallback_to_ask=False, base_finance_fallback=True
        ),
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
        research_policy=ResearchExecutionPolicy(
            max_skill_calls=3,
            max_elapsed_seconds=0.2,
        ),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )
    elapsed = time.monotonic() - started

    assert worker_started.is_set()
    assert elapsed < 0.8
    assert result.status == "completed"
    assert "截止时间" in result.content
    trace_before_release = run_store.load_trace(run_id)
    assert any(
        step["name"] == "ask_stage_agent_loop" and step["status"] == "running"
        for step in trace_before_release
    )
    assert any(step["name"] == "ask_root_timeout" for step in trace_before_release)

    release_worker.set()
    assert late_progress_sent.wait(timeout=1)
    assert run_store.load_trace(run_id) == trace_before_release
    assistant = conversation_store.load_messages(conversation.conversation_id)[-1]
    assert assistant.content == result.content
    assert "迟到片段" not in assistant.content


def test_route_contract_and_verifier_share_rebound_task_frame(tmp_path) -> None:
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    query = "昨天的反弹能持续多久"
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        query,
    )
    contracts = []

    def answer_with_gap(options: AskOptions) -> AskResult:
        assert options.question_type_override == "market_forecast"
        assert options.research_task_contract is not None
        contracts.append(options.research_task_contract)
        result = _ask_result(
            query,
            synthesis="当前证据不足，仍缺少反弹持续时间的直接判断。",
        )
        result.business_status = "complete"
        result.answer_spec = answer_model.finalize_answer_spec(
            answer_model.AnswerSpec(
                research_spec=answer_model.resolve_answer_profile(
                    query,
                    profile="forecast",
                ),
                summary=(
                    answer_model.make_claim(
                        claim_id="generic:summary",
                        text="当前证据不足，仍缺少反弹持续时间的直接判断。",
                        claim_type="summary",
                        theme="A股市场",
                        status=answer_model.ClaimStatus.MISSING,
                    ),
                ),
                verified_facts=(),
                company_table=(),
                counter_evidence=(),
                gaps=(),
                triggers=(),
                next_actions=(),
                sources=(),
                system_notices=(),
                presentation_kind="generic_research",
                presentation_profile="forecast",
            )
        )
        return result

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_with_gap,
        route_skills_fn=lambda *_args, **_kwargs: pytest.fail(
            "deterministic rebound forecast must skip the skill router"
        ),
        skill_registry=SkillRegistry(),
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query=query,
        skill_mode="auto",
        selected_skill_ids=[],
    )

    trace = run_store.load_trace(run_id)
    controller = json.loads(
        next(step for step in trace if step["name"] == "turn_controller")[
            "output_summary"
        ]
    )
    route = json.loads(
        next(step for step in trace if step["name"] == "route_skills")["output_summary"]
    )
    verifier = json.loads(
        next(step for step in trace if step["name"] == "task_fulfillment")[
            "output_summary"
        ]
    )
    report = json.loads(
        (run_store.run_dir(run_id) / "report.json").read_text(encoding="utf-8")
    )
    frame_hash = controller["task_frame_hash"]

    assert controller["task_frame"]["raw_question"] == query
    assert controller["task_frame"]["subject"] == "A股市场"
    assert route["query_envelope"]["question_type"] == "market_forecast"
    assert contracts[0].question == query
    assert contracts[0].subject == "A股市场"
    assert route["task_frame_hash"] == frame_hash
    assert contracts[0].to_dict()["task_frame_hash"] == frame_hash
    assert verifier["task_frame_hash"] == frame_hash
    assert report["task_frame_hash"] == frame_hash
    assert report["task_frame"]["raw_question"] == query


def test_turn_trace_exposes_configure_and_plan_as_their_own_l1_steps(
    tmp_path,
) -> None:
    from intelligence.eval.normalize_harness_trace import normalize_records

    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation()
    run_id, assistant_message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "总结证据",
    )

    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=lambda options: _ask_result(options.query),
        skill_registry=SkillRegistry(),
        turn_controller_fn=_research_controller,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=assistant_message_id,
        query="总结证据",
        skill_mode="auto",
        selected_skill_ids=[],
    )

    trace = run_store.load_trace(run_id)
    by_step = {step["step_id"]: step for step in trace}

    # `configure` (pre-run assembly) was invisible entirely; `plan` existed only
    # fused inside the `controller` payload.  Both must now be their own span so
    # a triage report can point at one without the other.
    assert "configure" in by_step
    assert "plan" in by_step
    assembly = json.loads(by_step["configure"]["output_summary"])
    assert assembly["skill_mode"] == "auto"
    assert assembly["registry_skill_count"] >= 0
    assert "research_plan" in json.loads(by_step["plan"]["output_summary"])

    # No prompt text or question prose may ride along in the assembly snapshot.
    assert "总结证据" not in by_step["configure"]["output_summary"]

    normalized = normalize_records(trace, kind="workbench-trace")
    steps = [event.step for event in normalized]
    assert steps[0] == "configure"
    assert "plan" in steps
    assert "unmapped" not in steps


class TestEarlierMessagesDiscloseWhatWasDropped:
    """会话层的「压缩」是尾部截断，必须自述砍了多少。

    ai-agent-book ch2「压缩策略的设计原则」：**压缩最容易丢失的不是细节本身，
    而是早期的架构决策、约束背后的理由和失败的路径**——LLM 会优先删「看起来
    还可以重新获取」的信息。而按位置截尾恰好先丢最早的那一段。

    同仓已有范本 ``tool_result_budget.py``：落盘全量 + 有界预览 + 显式标注
    省略了多少、去哪找回来（「'there was more' without 'and here is where it
    is' is not auditable」）。会话这一层此前只有一个裸 "…"——**同一个仓，
    两套标准**。

    ⚠ 本类**不**断言截断方向。保留末尾是刻意的：紧邻当前轮的上下文对指代消解
    最有用。真正的修法是 ch2 第 4 层「归档式摘要」（逐轮结构化，git log 式），
    需要 LLM 调用与失败熔断器，尚未实现。
    """

    @staticmethod
    def _messages(count: int, filler: str):
        from intelligence.runtime.conversation_orchestrator import Message

        return [
            Message(
                message_id=f"m{i}",
                conversation_id="c0",
                role="user",
                content=f"第{i}轮 {filler}",
                created_at="2026-08-12T00:00:00Z",
                status="completed",
                run_id="r0",
            )
            for i in range(count)
        ]

    def test_short_history_is_returned_verbatim_without_a_marker(self) -> None:
        """没超预算就别加噪声——每次都挂一句「已省略」会训练模型忽略它。"""
        text = conversation_orchestrator._summarize_messages(self._messages(2, "短"))

        assert "已省略" not in text
        assert "第0轮" in text

    def test_truncated_history_states_how_much_was_dropped(self) -> None:
        messages = self._messages(60, "x" * 200)

        text = conversation_orchestrator._summarize_messages(messages)

        assert "已省略" in text
        assert "共 60 条较早消息" in text
        # 光说「有更多」不够，要给出量
        assert any(ch.isdigit() for ch in text.split("已省略")[0])

    def test_the_marker_is_inside_the_budget_not_on_top_of_it(self) -> None:
        """标记要从预算里扣，不能加在预算之上——否则「压缩」反而超支。"""
        messages = self._messages(60, "x" * 200)

        text = conversation_orchestrator._summarize_messages(messages)

        assert len(text) <= SUMMARY_CHAR_LIMIT


def test_readable_replacement_does_not_split_a_longer_identifier() -> None:
    """术语替换不得把表名切开——2026-08-18 A5 实测原文。

    ``limit_heat`` 这条规则曾把 ``fact_theme_limit_heat_daily`` 改成
    ``fact_theme_涨停热度_daily``，一个不存在的表。产品刚声明完取数口径，
    展示层就把口径改成了查不到的东西，而两侧门禁都不会报错。
    """
    from intelligence.runtime.conversation_orchestrator import (
        sanitize_conversation_answer,
    )

    cleaned = sanitize_conversation_answer(
        "fact_theme_limit_heat_daily 2026-07-23 涨停集中：储能 40 家。"
    )
    assert "fact_theme_limit_heat_daily" in cleaned
    assert "涨停热度_daily" not in cleaned


def test_readable_replacement_still_translates_a_standalone_term() -> None:
    """反方向：独立出现的内部术语仍要翻译，否则这道闸就是把功能关掉了。"""
    from intelligence.runtime.conversation_orchestrator import (
        sanitize_conversation_answer,
    )

    assert "涨停热度" in sanitize_conversation_answer("信号 limit_heat 命中三个题材。")

"""Offline opening recall: temporary identities, real ledgers, no model IO."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
from threading import Event
import time
from uuid import uuid4

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.conversation_orchestrator import ConversationContext, TurnOrchestrator
from intelligence.services import corrections, episode_tools, judgments, memory_prefetch, user_memory
from intelligence.services.agent_research import AgentEvidence, evidence_content_hash
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.conversation_store import ConversationStore, Message
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.evidence_capabilities import runtime_capabilities_for_frame
from intelligence.services.memory_status import record_status
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_tool_registry import ToolRunResult
from intelligence.services.run_store import RunStore
from intelligence.services.task_frame import TaskFrame


@pytest.fixture
def frame():
    return TaskFrame(
        raw_question="甲公司现在怎么看", user_goal="核验公司端兑现",
        question_type="stock_deep_dive", subject="甲公司", subject_kind="company",
        market_scope="A股", timeframe="当前", required_outputs=("direct_assessment",),
        assumptions=(), ambiguities=(), clarification_question=None,
        evidence_policy="company_official_evidence", confidence=0.95,
    )


@pytest.fixture(autouse=True)
def private_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    # Other opening sources belong to adjacent owners; this suite only reads memory.
    monkeypatch.setattr(episode_tools, "_opening_prefetch_evidence", lambda *a, **kw: ())


def registry_for(tmp_path, frame, *, user="alice", caps=("memory_lookup",), deadline=None):
    context = build_episode_context(frame, task_id=f"opening-{uuid4().hex}", capabilities=caps, timeout=30)
    if deadline is not None:
        context = replace(context, deadline=deadline)
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path / "finance", knowledge_wiki=tmp_path / "wiki",
        l3_runner=None, memory_user=user,
    )
    return registry, context


def record(tmp_path, *, user="alice"):
    return corrections.record_correction(
        tmp_path / "users" / user / "corrections.jsonl",
        correction="先看客户验证进度再谈弹性", original="只看产能公告",
        themes=["甲公司"],
    )


def status(registry):
    assert len(registry.opening_prefetch) == 1
    item = registry.opening_prefetch[0]
    assert item.content_hash == evidence_content_hash(item)
    assert item.io_effect == "local_read"
    return item


def test_hit_has_same_hash_as_explicit_tool(tmp_path, frame):
    record(tmp_path)
    registry, context = registry_for(tmp_path, frame)
    item = status(registry)
    assert item.evidence_tier == "user_memory"
    assert "客户验证进度" in item.detail
    explicit = registry.execute("memory_lookup", frame.raw_question, context=context, step_id="probe")
    assert item.content_hash == explicit.evidence[0].content_hash


def test_memory_budget_is_shared_and_prioritizes_corrections(tmp_path, frame, monkeypatch):
    root = tmp_path / "users" / "alice"
    for index in range(5):
        judgments.record_judgment(
            root / "judgments.jsonl", memo=f"旧判断{index}：" + "只看产能。" * 2000,
            themes=["甲公司"], ts=f"2026-07-0{index + 1}T00:00:00+00:00",
        )
        corrections.record_correction(
            root / "corrections.jsonl", correction=f"新纠偏{index}：先看客户验证。" + "不能只看产能。" * 2000,
            themes=["甲公司"], ts=f"2026-07-1{index + 1}T00:00:00+00:00",
        )
    monkeypatch.setattr(user_memory, "_method_records", lambda *a, **kw: [{
        "detail": "甲公司方法验证读数：" + "需真实前向验证。" * 2000,
        "date": "2026-07-20", "method_id": "fixture-method",
    }])
    originals = {path: path.read_bytes() for path in root.glob("*.jsonl")}

    registry, context = registry_for(tmp_path, frame)
    explicit = registry.execute("memory_lookup", frame.raw_question, context=context, step_id="bounded")

    # This is the returned recall text budget, including notice text and titles.
    assert len(explicit.observation) <= 6000
    assert all(len(item.detail) <= 1000 for item in explicit.evidence)
    assert "截断" in explicit.observation and "省略" in explicit.observation
    assert explicit.evidence[0].title == "用户纠偏原则"
    assert "新纠偏4" in explicit.evidence[0].detail
    assert sum(item.title == "用户纠偏原则" for item in explicit.evidence) == 5
    assert [item.content_hash for item in registry.opening_prefetch] == [
        item.content_hash for item in explicit.evidence
    ]
    assert all(item.content_hash == evidence_content_hash(item) for item in explicit.evidence)
    assert {path: path.read_bytes() for path in originals} == originals


def test_single_method_memory_is_also_bounded(tmp_path, frame, monkeypatch):
    monkeypatch.setattr(user_memory, "_method_records", lambda *a, **kw: [{
        "detail": "甲公司方法验证读数：" + "需真实前向验证。" * 2000,
        "date": "2026-07-20", "method_id": "fixture-method",
    }])
    registry, context = registry_for(tmp_path, frame)
    explicit = registry.execute("memory_lookup", frame.raw_question, context=context, step_id="method")
    method = next(item for item in explicit.evidence if item.title == "方法验证读数")
    assert len(method.detail) <= 1000
    assert "截断" in method.detail
    assert len(explicit.observation) <= 6000
    assert [item.content_hash for item in registry.opening_prefetch] == [
        item.content_hash for item in explicit.evidence
    ]


def test_cross_user_empty_and_no_identity_never_reads_default(tmp_path, frame, monkeypatch):
    record(tmp_path)
    record(tmp_path, user="default")
    other, _ = registry_for(tmp_path, frame, user="bob")
    assert "status=empty" in status(other).detail

    def forbidden(*args, **kwargs):
        pytest.fail("unauthorized memory read")

    monkeypatch.setattr(user_memory, "relevant_memory_records", forbidden)
    for user, caps in ((None, ("memory_lookup",)), ("", ("memory_lookup",)), ("alice", ())):
        registry, _ = registry_for(tmp_path, frame, user=user, caps=caps)
        assert registry.opening_prefetch == ()
        assert "memory_lookup" not in registry.names()


def test_rejected_correction_disappears_from_next_opening(tmp_path, frame):
    path, row = record(tmp_path)
    record_status(path, target_ts=row["id"], status="rejected")
    registry, _ = registry_for(tmp_path, frame)
    assert "status=empty" in status(registry).detail


@pytest.mark.parametrize("question_type,kind,subject", [
    ("market_forecast", "market_pattern", "A股市场"),
    ("method_explain", "concept", "现金流"),
    ("stock_deep_dive", "company", "股"),
    ("theme_analysis", "market_pattern", "A股市场"),
])
def test_unscoped_or_nonresearch_question_does_not_prefetch(tmp_path, frame, monkeypatch, question_type, kind, subject):
    monkeypatch.setattr(user_memory, "relevant_memory_records", lambda *a, **kw: pytest.fail("unexpected read"))
    frame = replace(frame, question_type=question_type, subject_kind=kind, subject=subject)
    registry, _ = registry_for(tmp_path, frame)
    assert registry.opening_prefetch == ()


@pytest.mark.parametrize("question_type", ["stock_deep_dive", "theme_analysis", "theme_track", "trade_advice", "valuation_estimate", "financial_analysis"])
def test_research_default_contract_authorizes_optional_prior_slot(frame, question_type):
    frame = replace(frame, question_type=question_type)
    assert "memory_lookup" in runtime_capabilities_for_frame(frame)
    context = build_episode_context(frame, task_id=f"policy-{uuid4().hex}")
    prior = next(item for item in context.contract.required_outputs if item.output_id == "prior_recall")
    assert prior.grounding_mode == "user_premise" and not prior.required


def test_expired_root_budget_skips_read(tmp_path, frame, monkeypatch):
    monkeypatch.setattr(user_memory, "relevant_memory_records", lambda *a, **kw: pytest.fail("read after deadline"))
    registry, _ = registry_for(tmp_path, frame, deadline=ResearchDeadline.from_timeout(0))
    assert "status=timeout" in status(registry).detail


def test_unreadable_ledger_is_not_empty_and_does_not_leak_error(tmp_path, frame, monkeypatch):
    monkeypatch.setattr(corrections, "load_corrections", lambda *a, **kw: ([], "private-path private-text"))
    registry, _ = registry_for(tmp_path, frame)
    item = status(registry)
    assert "status=unavailable" in item.detail
    assert "private-" not in item.detail


@pytest.mark.parametrize("ledger", ["corrections", "judgments"])
@pytest.mark.parametrize("content", ["{broken", "[]"])
def test_corrupt_ledger_reports_failure_not_empty(tmp_path, frame, ledger, content):
    root = tmp_path / "users" / "alice"
    root.mkdir(parents=True)
    (root / f"{ledger}.jsonl").write_text(content + "\n", encoding="utf-8")
    registry, _ = registry_for(tmp_path, frame)
    assert "status=unavailable" in status(registry).detail


def test_synthesis_reserve_is_not_spent_on_memory(tmp_path, frame, monkeypatch):
    monkeypatch.setattr(user_memory, "relevant_memory_records", lambda *a, **kw: pytest.fail("spent synthesis budget"))
    registry, _ = registry_for(tmp_path, frame, deadline=ResearchDeadline.from_timeout(1, synthesis_reserve=2))
    assert "status=timeout" in status(registry).detail


def test_memory_is_appended_without_replacing_market_prefetch(tmp_path, frame, monkeypatch):
    market = AgentEvidence(tool="market_data", title="fixture", detail="fixture", source="fixture", content_hash="market-fixture")
    monkeypatch.setattr(episode_tools, "_opening_prefetch_evidence", lambda *a, **kw: (market,))
    record(tmp_path)
    registry, _ = registry_for(tmp_path, frame)
    assert registry.opening_prefetch[0] == market
    assert registry.opening_prefetch[1].evidence_tier == "user_memory"


def _scripted_memory_result(*items: AgentEvidence) -> ToolRunResult:
    return ToolRunResult(
        evidence=tuple(items),
        observation="fixture memory",
        trace=ProviderTrace(
            provider="scripted_memory",
            capability="memory_lookup",
            status="success",
            result_count=len(items),
        ),
    )


def test_opening_memory_filters_future_records_at_explicit_cutoff(frame):
    context = build_episode_context(
        frame,
        task_id="opening-cutoff-filter",
        capabilities=("memory_lookup",),
        information_cutoff=InformationCutoff(date(2026, 7, 24), "requested"),
    )
    before = AgentEvidence(
        tool="memory_lookup",
        title="截止日前记忆",
        detail="2026-07-24 已留下的判断",
        source="private-ledger",
        source_date="2026-07-24",
        evidence_tier="user_memory",
    )
    after = AgentEvidence(
        tool="memory_lookup",
        title="截止日后记忆",
        detail="2026-07-25 才留下的判断",
        source="private-ledger",
        source_date="2026-07-25",
        evidence_tier="user_memory",
    )

    opening = memory_prefetch.collect_opening_memory(
        lambda _query, _tool_context: _scripted_memory_result(before, after),
        query=frame.raw_question,
        context=context,
    )

    assert [item.title for item in opening] == ["截止日前记忆"]
    assert all("截止日后" not in item.detail for item in opening)


def test_opening_memory_reports_future_only_as_unusable_not_empty(frame):
    context = build_episode_context(
        frame,
        task_id="opening-future-only",
        capabilities=("memory_lookup",),
        information_cutoff=InformationCutoff(date(2026, 7, 24), "requested"),
    )
    future = AgentEvidence(
        tool="memory_lookup",
        title="未来记忆",
        detail="只在截止日后留下",
        source="private-ledger",
        source_date="2026-07-25",
        evidence_tier="user_memory",
    )

    opening = memory_prefetch.collect_opening_memory(
        lambda _query, _tool_context: _scripted_memory_result(future),
        query=frame.raw_question,
        context=context,
    )

    assert len(opening) == 1
    assert opening[0].evidence_tier == "user_memory_gap"
    assert "status=future_of_cutoff" in opening[0].detail
    assert "无相关命中" not in opening[0].detail


def test_opening_memory_does_not_use_undated_legacy_note_for_explicit_cutoff(frame):
    context = build_episode_context(
        frame,
        task_id="opening-undated",
        capabilities=("memory_lookup",),
        information_cutoff=InformationCutoff(date(2026, 7, 24), "requested"),
    )
    undated = AgentEvidence(
        tool="memory_lookup",
        title="无日期记忆",
        detail="日期无法核验",
        source="private-ledger",
        source_date=None,
        evidence_tier="user_memory",
    )

    opening = memory_prefetch.collect_opening_memory(
        lambda _query, _tool_context: _scripted_memory_result(undated),
        query=frame.raw_question,
        context=context,
    )

    assert len(opening) == 1
    assert opening[0].evidence_tier == "user_memory_gap"
    assert "status=date_unavailable" in opening[0].detail
    assert "无日期记忆" not in opening[0].detail


def test_historical_cutoff_discloses_partial_undated_omission(frame):
    context = build_episode_context(
        frame, task_id="opening-mixed-dates", capabilities=("memory_lookup",),
        information_cutoff=InformationCutoff(date(2026, 7, 24), "requested"),
    )
    dated = AgentEvidence(
        tool="memory_lookup", title="有日期记忆", detail="先核验客户进度",
        source="private-ledger", source_date="2026-07-23", evidence_tier="user_memory",
    )
    undated = replace(dated, title="无日期记忆", detail="不可泄露的无日期原文", source_date=None)
    opening = memory_prefetch.collect_opening_memory(
        lambda _query, _tool_context: _scripted_memory_result(dated, undated),
        query=frame.raw_question, context=context,
    )
    assert any(item.detail == dated.detail for item in opening)
    assert any(item.evidence_tier == "user_memory_gap" and "status=date_unavailable" in item.detail for item in opening)
    assert all(undated.detail not in item.detail for item in opening)


def test_explicit_historical_memory_uses_same_filtered_projection(tmp_path, frame):
    path = tmp_path / "users" / "alice" / "corrections.jsonl"
    corrections.record_correction(
        path, correction="甲公司应先核验客户进度", themes=["甲公司"], ts="2026-07-23T00:00:00+00:00",
    )
    corrections.record_correction(
        path, correction="甲公司未来才出现的纠偏" * 2000, themes=["甲公司"], ts="2026-07-25T00:00:00+00:00",
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"correction": "甲公司不可泄露的无日期原文", "themes": ["甲公司"]}) + "\n")
    context = build_episode_context(
        frame, task_id="explicit-mixed-dates", capabilities=("memory_lookup",),
        information_cutoff=InformationCutoff(date(2026, 7, 24), "requested"),
    )
    registry = episode_tools.build_episode_registry(
        frame, context, finance_root=tmp_path / "finance", knowledge_wiki=tmp_path / "wiki",
        l3_runner=None, memory_user="alice",
    )
    explicit = registry.execute("memory_lookup", frame.raw_question, context=context, step_id="dated")
    assert "先核验客户进度" in explicit.observation
    assert "status=date_unavailable" in explicit.observation
    assert "不可泄露" not in explicit.observation and "未来才出现" not in explicit.observation
    assert [item.content_hash for item in registry.opening_prefetch] == [
        item.content_hash for item in explicit.evidence
    ]


@pytest.mark.parametrize("source", ["runtime_default", "latest_available"])
def test_opening_memory_keeps_undated_legacy_note_for_current_cutoff(frame, source):
    # The undated withhold is only for an explicitly requested cutoff; widening it
    # would silently drop legacy priors from every current research question.
    context = build_episode_context(
        frame,
        task_id=f"opening-undated-{source}",
        capabilities=("memory_lookup",),
        information_cutoff=InformationCutoff(date(2026, 7, 24), source),
    )
    undated = AgentEvidence(
        tool="memory_lookup",
        title="无日期记忆",
        detail="旧笔记仍是当前先验",
        source="private-ledger",
        source_date=None,
        evidence_tier="user_memory",
    )

    opening = memory_prefetch.collect_opening_memory(
        lambda _query, _tool_context: _scripted_memory_result(undated),
        query=frame.raw_question,
        context=context,
    )

    assert [(item.title, item.evidence_tier) for item in opening] == [("无日期记忆", "user_memory")]


def test_worker_exception_does_not_abort_opening(tmp_path, frame, monkeypatch):
    def failed(*args, **kwargs):
        raise OSError("private-path private-text")

    monkeypatch.setattr(user_memory, "relevant_memory_records", failed)
    registry, _ = registry_for(tmp_path, frame)
    assert "status=unavailable" in status(registry).detail


def test_timeout_is_bounded_no_late_injection_and_no_unbounded_queue(tmp_path, frame, monkeypatch):
    monkeypatch.setattr(memory_prefetch, "MEMORY_PREFETCH_SECONDS", 0.05)
    started, release = Event(), Event()
    finished = [Event(), Event()]
    calls = []
    real = user_memory.relevant_memory_records
    record(tmp_path)

    def slow(*args, **kwargs):
        index = len(calls)
        calls.append(index)
        started.set()
        try:
            release.wait(2)
            return real(*args, **kwargs)
        finally:
            finished[index].set()

    monkeypatch.setattr(user_memory, "relevant_memory_records", slow)
    try:
        before = time.monotonic()
        first, _ = registry_for(tmp_path, frame)
        assert started.is_set()
        assert time.monotonic() - before < 1.0
        second, _ = registry_for(tmp_path, frame)
        third, _ = registry_for(tmp_path, frame)
        assert "status=timeout" in status(first).detail
        assert "status=timeout" in status(second).detail
        assert "status=busy" in status(third).detail
        assert len(calls) == 2
    finally:
        release.set()
        for event in finished:
            assert event.wait(2)
    assert "status=timeout" in status(first).detail
    assert not any("客户验证" in item.detail for item in first.opening_prefetch)


def test_workbench_write_reaches_next_first_request_without_tool_call(tmp_path, frame, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conv = store.create_conversation()
    run = run_store.create_run(frame.raw_question, "ask", session_id=conv.conversation_id)
    orchestrator = TurnOrchestrator(repo_root=tmp_path, conversation_store=store, run_store=run_store)
    monkeypatch.setattr(orchestrator, "_trace", lambda *a, **kw: None)
    previous = Message(
        message_id="completed-answer", conversation_id=conv.conversation_id,
        role="assistant", content="可以直接上车，先看产能公告。", status="completed",
        created_at="2026-09-25T01:00:00+00:00",
        turn_intent={"question_type": "stock_deep_dive", "primary_subject": "甲公司"},
    )
    warnings = []
    orchestrator._maybe_ingest_workbench_correction(
        context=ConversationContext(summary="", recent_messages=(previous,)),
        query="不对，应该先看客户验证进度再下结论", conversation_id=conv.conversation_id,
        run_id=run.run_id, assistant_message_id="new-answer", warnings=warnings,
    )
    assert warnings == []
    registry, context = registry_for(tmp_path, frame)
    item = status(registry)
    assert item.evidence_tier == "user_memory"
    assert "客户验证进度" in item.detail

    direct_basis = next(output.grounding_mode for output in context.contract.required_outputs if output.output_id == "direct_assessment")

    class ModelStub:
        calls = []

        def complete(self, *, messages, tools, timeout):
            self.calls.append([dict(message) for message in messages])
            return ModelTurn(json.dumps({
                "status": "partial", "draft": "先看客户验证；本轮缺少市场证据。",
                "gaps": ["缺少市场证据"], "bindings": [
                    {"output_id": "prior_recall", "basis": "user_premise", "evidence_hashes": [item.content_hash], "gap": ""},
                    {"output_id": "direct_assessment", "basis": direct_basis, "evidence_hashes": [], "gap": "缺少市场证据"},
                ],
            }, ensure_ascii=False), (), "scripted", "")

    model = ModelStub()
    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=registry)
    assert len(model.calls) == 1, [dict(event.payload) for event in outcome.events if event.kind in {"invalid_action", "finish_rejected", "error"}]
    first_request = str(model.calls[0])
    assert "客户验证进度" in first_request
    assert "不是市场事实" in first_request
    assert str(tmp_path) not in first_request
    assert outcome.usage.tool_calls == 0
    assert item.content_hash in {e.content_hash for e in outcome.evidence}
    assert any(b.output_id == "prior_recall" and b.basis == "user_premise" for b in outcome.bindings)


def test_gap_message_is_an_observation_not_a_prior(tmp_path, frame):
    from intelligence.services.asof_prefetch import format_opening_prefetch_message

    registry, _ = registry_for(tmp_path, frame)
    item = status(registry)
    message = format_opening_prefetch_message(registry.opening_prefetch)
    assert item.evidence_tier == "user_memory_gap"
    assert "无相关命中" in message and "禁止据此编造" in message


@pytest.mark.parametrize("tier,basis", [("user_memory", "evidence"), ("user_memory_gap", "user_premise")])
def test_memory_cannot_fill_fact_slot_or_turn_gap_into_prior(tmp_path, frame, tier, basis):
    from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent, OutputEvidenceBinding
    from intelligence.services.episode_verifier import verify_episode_outcome
    from intelligence.services.research_contract import RequiredOutput

    _, context = registry_for(tmp_path, frame)
    contract = replace(context.contract, required_outputs=(RequiredOutput("direct_assessment", "判断", (), grounding_mode=basis),))
    item = AgentEvidence(tool="memory_lookup", title="fixture", detail="fixture", source="fixture", evidence_tier=tier, content_hash="fixture-hash")
    outcome = AgentOutcome(
        task_frame_hash=contract.task_frame_hash, status="completed", draft="当前已经兑现。",
        evidence=(item,), traces=(), gaps=(), stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": contract.task_frame_hash}),),
        bindings=(OutputEvidenceBinding("direct_assessment", (item.content_hash,), basis=basis),), usage=AgentUsage(),
    )
    verified = verify_episode_outcome(contract, outcome)
    assert verified.verified_status != "completed"
    assert any("evidence" in issue.code.value for issue in verified.issue_items)

    from intelligence.services.episode_protocol import validate_episode_finish

    with pytest.raises(ValueError, match="用户记忆只能绑定"):
        validate_episode_finish(
            {"status": "completed", "draft": outcome.draft, "gaps": [], "bindings": [
                {"output_id": "direct_assessment", "basis": basis, "evidence_hashes": [item.content_hash], "gap": ""},
            ]},
            context=replace(context, contract=contract), evidence=(item,),
        )

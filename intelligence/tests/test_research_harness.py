"""ResearchHarness 接缝：默认等价、协议、有牙、import 棘轮、唯一已知差。

spec：``docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`` §8。

五组断言各守一件事：

1. **等价**——``FinanceResearchHarness`` 四个方法与直接调 ``episode_protocol`` /
   ``forecast_residual_budget`` 逐字段相同（接受 / FORMAT 驳回 / INTEGRITY 驳回）。
2. **协议**——默认实现满足 ``ResearchHarness``；少一个方法的类不满足。
3. **loop 真在问**——录音 harness 注入 ``ContinuousAgentEpisode``，四个接缝按
   控制流顺序各被调一次。
4. **有牙**——放行 harness 让 INTEGRITY 驳回的终局被接受为 ``model_finish``；
   同一脚本在默认 harness 下停在 ``forged_hash``。没牙的接缝是装饰。
5. **棘轮**——``agent_episode.py`` 不得回退到直接 import 被抽走的领域符号。

外加 spec §7 那条唯一已知差：死钟结转路径现在保留比较集展开。
"""

from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path

import pytest

import intelligence.runtime.agent_episode as agent_episode_module
import intelligence.services.research_contract as research_contract_module
from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_protocol import (
    expand_episode_snapshot_bindings,
    finish_rejection_fields,
    rejection_response,
    split_episode_prompt,
    validate_episode_finish,
)
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.forecast_residual_budget import (
    FORECAST_RESIDUAL_QUESTION_TYPE,
    FORECAST_RESIDUAL_SPIN,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger,
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_harness import (
    FinanceResearchHarness,
    FinishAdmission,
    ResearchHarness,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame

_AGENT_EPISODE_PATH = (
    Path(__file__).resolve().parents[1] / "runtime" / "agent_episode.py"
)


# ── 夹具（与 test_agent_episode 同形，刻意不 import 它：测试文件之间不互相依赖）


def _frame(required_outputs: tuple[str, ...] = ("direct_assessment",)) -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=required_outputs,
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _context(
    frame: TaskFrame,
    *,
    max_steps: int = 3,
    question_type: str | None = None,
    research_tier: str = "quick",
) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="harness-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=question_type or frame.question_type,
        required_outputs=tuple(
            RequiredOutput(item, item, ("market_data",), True)
            for item in frame.required_outputs
        ),
        allowed_capabilities=("market_data",),
        research_tier=research_tier,
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", max_steps, 30.0, 0.0),
        trace_parent_id="harness-test",
        today="2026-07-22",
        latest_data_date="2026-07-21",
    )


def _evidence(content_hash: str, *, title: str = "A股市场总览") -> AgentEvidence:
    return AgentEvidence(
        tool="market_data",
        title=title,
        detail=f"{title}：上涨家数增加，成交保持活跃",
        source="本地行情",
        source_date="2026-07-21",
        evidence_tier="L4",
        content_hash=content_hash,
    )


def _registry(evidence: tuple[AgentEvidence, ...], *, query_scope: str = "turn"):
    def runner(query: str, _context: AgentToolContext):
        del query
        return (
            list(evidence),
            "raw market observation",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="success",
                source_trade_date="2026-07-21",
                result_count=len(evidence),
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情与市场时序",
                cost="local",
                freshness="current",
                runner=runner,
                query_scope=query_scope,
            ),
        )
    )


def _finish_content(
    *,
    status: str = "completed",
    draft: str = "当前更接近条件化修复，持续性取决于量能。",
    hashes: tuple[str, ...] = ("evidence-1",),
    gap: str = "",
) -> str:
    return json.dumps(
        {
            "status": status,
            "draft": draft,
            "gaps": [gap] if gap else [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": list(hashes),
                    "gap": gap,
                }
            ],
        },
        ensure_ascii=False,
    )


def _tool_turn() -> ModelTurn:
    return ModelTurn(
        "",
        (ModelToolCall("call-1", "market_data", {"query": "当前市场结构"}),),
        "scripted",
        "",
    )


class _ScriptedModel:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self._turns = iter(turns)
        self.calls = 0

    def complete(self, *, messages, tools, timeout):
        del messages, tools, timeout
        self.calls += 1
        return next(self._turns)


# ── 1. 等价 ────────────────────────────────────────────────────────────────


def test_default_admit_finish_equals_direct_calls_when_accepted() -> None:
    frame = _frame()
    context = _context(frame)
    evidence = (_evidence("evidence-1"),)
    registry = _registry(evidence)
    content = _finish_content(gap="反方证据不足")

    admission = FinanceResearchHarness().admit_finish(
        content, context=context, evidence=evidence, registry=registry
    )
    finish = validate_episode_finish(content, context=context, evidence=evidence)
    bindings = expand_episode_snapshot_bindings(
        bindings=finish.bindings,
        evidence=evidence,
        registry=registry,
        draft=finish.draft,
    )

    assert admission.accepted is True
    assert admission.status == finish.status
    assert admission.draft == finish.draft
    assert admission.bindings == bindings
    # 原 ``_finish_gaps``：声明 gap 在前、绑定 gap 在后、去空去重保序。
    assert admission.gaps == ("反方证据不足",)
    assert admission.caveat_slips == finish.caveat_slips
    assert admission.rejection == finish_rejection_fields()
    assert admission.rejection["rejection_code"] == "none"
    assert admission.response is None and admission.reason == "" and admission.kind == ""


def test_default_admit_finish_equals_direct_calls_for_format_rejection() -> None:
    frame = _frame()
    context = _context(frame)
    evidence = (_evidence("evidence-1"),)
    content = "不是 JSON，只是一段话。"

    admission = FinanceResearchHarness().admit_finish(
        content, context=context, evidence=evidence, registry=_registry(evidence)
    )
    with pytest.raises(ValueError) as caught:
        validate_episode_finish(content, context=context, evidence=evidence)
    exc = caught.value

    assert admission.accepted is False
    assert admission.reason == str(exc)
    assert admission.kind == "format"
    assert admission.response == rejection_response(exc)
    assert admission.rejection == finish_rejection_fields(exc)
    assert admission.response is not None and admission.response.reinject is True
    assert admission.status is None and admission.draft == "" and admission.bindings == ()


def test_default_admit_finish_classifies_forged_hash_as_integrity() -> None:
    frame = _frame()
    context = _context(frame)
    evidence = (_evidence("evidence-1"),)

    admission = FinanceResearchHarness().admit_finish(
        _finish_content(hashes=("forged-hash",)),
        context=context,
        evidence=evidence,
        registry=_registry(evidence),
    )

    assert admission.accepted is False
    assert admission.kind == "integrity"
    assert admission.rejection["rejection_code"] == "forged_hash"
    assert admission.response is not None
    assert admission.response.stop_reason == "integrity_violation"
    assert admission.response.reinject is False
    assert admission.response.allow_recovery is False


def test_default_prompt_halt_and_retrieval_delegate_to_domain_functions() -> None:
    frame = _frame()
    harness = FinanceResearchHarness()
    evidence = (_evidence("evidence-1"),)

    context = _context(frame)
    assert harness.assemble_prompt(frame, context, _registry(evidence)) == (
        split_episode_prompt(frame, context, _registry(evidence))
    )

    residual = _context(
        frame, question_type=FORECAST_RESIDUAL_QUESTION_TYPE, research_tier="deep"
    )
    assert (
        harness.halt_after_tool_batch(
            context=residual, batch_errors=("duplicate_query", None)
        )
        == FORECAST_RESIDUAL_SPIN
    )
    assert harness.halt_after_tool_batch(context=residual, batch_errors=(None,)) is None
    assert (
        harness.halt_after_tool_batch(context=context, batch_errors=("duplicate_query",))
        is None
    )

    episode_scoped = _registry(evidence, query_scope="episode")
    assert (
        harness.retrieval_complete(
            context=context, registry=episode_scoped, successful_tools={"market_data"}
        )
        is True
    )
    assert (
        harness.retrieval_complete(
            context=context, registry=episode_scoped, successful_tools=set()
        )
        is False
    )
    assert (
        harness.retrieval_complete(
            context=context,
            registry=_registry(evidence, query_scope="turn"),
            successful_tools={"market_data"},
        )
        is False
    )


def test_finish_admission_refuses_inconsistent_values() -> None:
    """接受不能带处置，驳回不能没有理由——值对象自己守住两侧的形状。"""

    with pytest.raises(ValueError):
        FinishAdmission(
            accepted=True,
            status=None,
            draft="",
            bindings=(),
            gaps=(),
            caveat_slips=0,
            rejection=finish_rejection_fields(),
        )
    with pytest.raises(ValueError):
        FinishAdmission(
            accepted=False,
            status=None,
            draft="",
            bindings=(),
            gaps=(),
            caveat_slips=0,
            rejection=finish_rejection_fields(),
        )


# ── 2. 协议 ────────────────────────────────────────────────────────────────


def test_finance_harness_conforms_and_partial_implementation_does_not() -> None:
    assert isinstance(FinanceResearchHarness(), ResearchHarness)

    class OnlyFinish:
        def admit_finish(self, content, *, context, evidence, registry):
            raise NotImplementedError

    assert not isinstance(OnlyFinish(), ResearchHarness)


# ── 3. loop 真在问 ─────────────────────────────────────────────────────────


class _RecordingHarness(FinanceResearchHarness):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def assemble_prompt(self, task_frame, context, registry):
        self.calls.append("assemble_prompt")
        return super().assemble_prompt(task_frame, context, registry)

    def halt_after_tool_batch(self, *, context, batch_errors):
        self.calls.append("halt_after_tool_batch")
        return super().halt_after_tool_batch(context=context, batch_errors=batch_errors)

    def retrieval_complete(self, *, context, registry, successful_tools):
        self.calls.append("retrieval_complete")
        return super().retrieval_complete(
            context=context, registry=registry, successful_tools=successful_tools
        )

    def admit_finish(self, content, *, context, evidence, registry):
        self.calls.append("admit_finish")
        return super().admit_finish(
            content, context=context, evidence=evidence, registry=registry
        )


def test_episode_asks_harness_at_all_four_seams_in_control_flow_order() -> None:
    frame = _frame()
    evidence = (_evidence("evidence-1"),)
    harness = _RecordingHarness()
    model = _ScriptedModel(
        [_tool_turn(), ModelTurn(_finish_content(), (), "scripted", "")]
    )

    outcome = ContinuousAgentEpisode(model, harness=harness).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(evidence),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "model_finish"
    assert harness.calls == [
        "assemble_prompt",
        "halt_after_tool_batch",
        "retrieval_complete",
        "admit_finish",
    ]


def test_default_harness_is_finance_when_not_injected() -> None:
    episode = ContinuousAgentEpisode(_ScriptedModel([]))
    assert isinstance(episode._harness, FinanceResearchHarness)


# ── 4. 有牙 ────────────────────────────────────────────────────────────────


class _PermissiveHarness(FinanceResearchHarness):
    """放行一切：只解析 JSON，不看证据。**只用于证明接缝有牙，不得进生产。**"""

    def admit_finish(self, content, *, context, evidence, registry):
        del context, evidence, registry
        payload = json.loads(str(content))
        return FinishAdmission(
            accepted=True,
            status=payload["status"],
            draft=payload["draft"],
            bindings=(),
            gaps=(),
            caveat_slips=0,
            rejection=finish_rejection_fields(),
        )


def _forged_script() -> list[ModelTurn]:
    return [
        _tool_turn(),
        ModelTurn(_finish_content(hashes=("forged-hash",)), (), "scripted", ""),
    ]


def test_default_harness_stops_forged_finish_as_integrity_violation() -> None:
    frame = _frame()
    evidence = (_evidence("evidence-1"),)

    outcome = ContinuousAgentEpisode(_ScriptedModel(_forged_script())).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(evidence),
    )

    assert outcome.stop_reason == "invalid_model_finish"
    assert outcome.draft == ""
    invalid = [event for event in outcome.events if event.kind == "invalid_action"]
    assert invalid and invalid[-1].payload["code"] == "forged_hash"
    assert invalid[-1].payload["kind"] == "integrity"
    assert invalid[-1].payload["disposition"] == "integrity_violation"
    finish = [event for event in outcome.events if event.kind == "finish"][-1]
    assert finish.payload["rejection_code"] == "forged_hash"


def test_permissive_harness_changes_outcome_so_the_seam_has_teeth() -> None:
    frame = _frame()
    evidence = (_evidence("evidence-1"),)

    outcome = ContinuousAgentEpisode(
        _ScriptedModel(_forged_script()), harness=_PermissiveHarness()
    ).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(evidence),
    )

    assert outcome.stop_reason == "model_finish"
    assert outcome.status == "completed"
    assert outcome.draft == json.loads(_finish_content())["draft"]
    assert not [event for event in outcome.events if event.kind == "invalid_action"]
    finish = [event for event in outcome.events if event.kind == "finish"][-1]
    assert finish.payload["rejection_code"] == "none"


# ── 5. 棘轮 ────────────────────────────────────────────────────────────────

_EXTRACTED_FROM_EPISODE_PROTOCOL = frozenset(
    {
        "validate_episode_finish",
        "expand_episode_snapshot_bindings",
        "rejection_response",
        "split_episode_prompt",
    }
)


def _import_from_names(tree: ast.Module, module: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
    return names


def test_agent_episode_no_longer_imports_extracted_domain_gate_symbols() -> None:
    """loop 只能经 harness 摸到终局门 / 停机判定 / prompt。

    ``finish_rejection_fields`` 允许留下：``resume()`` 里「修复轮还在调工具」那处
    用它造字段，与终局校验无关（spec §6）。
    """

    tree = ast.parse(_AGENT_EPISODE_PATH.read_text(encoding="utf-8"))

    protocol_names = _import_from_names(tree, "intelligence.services.episode_protocol")
    leaked = protocol_names & _EXTRACTED_FROM_EPISODE_PROTOCOL
    assert not leaked, f"agent_episode 直接 import 了已抽走的领域门：{sorted(leaked)}"

    assert not _import_from_names(
        tree, "intelligence.services.forecast_residual_budget"
    ), "批后停机判定必须经 harness.halt_after_tool_batch"

    harness_names = _import_from_names(tree, "intelligence.services.research_harness")
    assert {"FinanceResearchHarness", "ResearchHarness"} <= harness_names


def test_research_harness_module_stays_in_the_domain_layer() -> None:
    """harness 在 services/：不得 import runtime（layer_audit 的方向）。"""

    path = Path(__file__).resolve().parents[1] / "services" / "research_harness.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not str(node.module or "").startswith("intelligence.runtime")
        if isinstance(node, ast.Import):
            assert not any(
                alias.name.startswith("intelligence.runtime") for alias in node.names
            )


# ── spec §7：唯一已知差 ────────────────────────────────────────────────────


class _WritesComparisonThenClockDies(_ScriptedModel):
    """终局那一轮把根账本烧穿：``complete()`` 已返回，``consume_seconds`` 失败。"""

    def __init__(self, turns: list[ModelTurn], now: list[float]) -> None:
        super().__init__(turns)
        self._now = now

    def complete(self, *, messages, tools, timeout):
        turn = super().complete(messages=messages, tools=tools, timeout=timeout)
        if not turn.tool_calls:
            self._now[0] += float(timeout) + 0.5
        return turn


def test_dead_clock_carry_keeps_comparison_set_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """死钟结转路径与其它四处终局门用同一份 admission。

    改前：先 ``_carry_just_written_finish``（带 draft 展开），再二次校验并用
    **不带 draft** 的展开覆盖 bindings——比较集展开被丢掉，同题排名的兄弟证据
    不进绑定。改后 bindings 是原来的超集；status / draft / stop_reason 不变。
    """

    frame = _frame()
    base = _context(frame)
    root = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=4,
        hard_calls_cap=4,
        initial_seconds=6.0,
        hard_seconds_cap=6.0,
    )
    context = replace(base, root_budget=root)
    now = [context.deadline.expires_at - 29.0]
    monkeypatch.setattr(agent_episode_module, "monotonic", lambda: now[0])
    monkeypatch.setattr(research_contract_module.time, "monotonic", lambda: now[0])

    siblings = (
        _evidence("rank-1", title="行业涨幅排名"),
        _evidence("rank-2", title="行业涨幅排名"),
    )
    comparative = _finish_content(
        draft="半导体在行业涨幅排名中居前，持续性取决于量能。",
        hashes=("rank-1",),
    )
    model = _WritesComparisonThenClockDies(
        [_tool_turn(), ModelTurn(comparative, (), "scripted", "")], now
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=context,
        registry=_registry(siblings),
    )

    assert outcome.stop_reason == "model_finish"
    assert outcome.status == "completed"
    assert outcome.draft == json.loads(comparative)["draft"]
    assert len(outcome.bindings) == 1
    assert outcome.bindings[0].evidence_hashes == ("rank-1", "rank-2")
    finish = [event for event in outcome.events if event.kind == "finish"][-1]
    assert finish.payload["carried_draft_chars"] == len(outcome.draft)

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
from intelligence.services.research_plan import (
    PlanParseResult,
    parse_plan_candidate,
    validate_plan_revision,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame

_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "runtime"
_AGENT_EPISODE_PATH = _RUNTIME_DIR / "agent_episode.py"
# 三条 loop：终局门此前在每一条里各手拼一遍（spec §1.1）。
_LOOP_PATHS = (
    _AGENT_EPISODE_PATH,
    _RUNTIME_DIR / "openai_agents_runtime.py",
    _RUNTIME_DIR / "codex_headless_runtime.py",
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


def _plan_content(*, revision: int = 1, **overrides: object) -> str:
    payload: dict[str, object] = {
        "kind": "PLAN",
        "task_summary": "判断市场主线并给出反方",
        "answer_elements": ["direct_assessment"],
        "hypotheses": ["半导体可能是持续主线"],
        "evidence_needs": ["同日主线与持续性"],
        "candidate_actions": ["market_data"],
        "open_gaps": ["缺少反方证据"],
        "requested_mode": "quick",
        "revision": revision,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


class _ScriptedModel:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self._turns = iter(turns)
        self.calls = 0
        self.seen_messages: list[list[dict[str, object]]] = []

    def complete(self, *, messages, tools, timeout):
        del tools, timeout
        self.calls += 1
        self.seen_messages.append([dict(item) for item in messages])
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


def test_default_interpret_plan_equals_parse_plus_revision_check() -> None:
    harness = FinanceResearchHarness()

    first = harness.interpret_plan(_plan_content(), previous_plan=None, task_id="t")
    assert first == parse_plan_candidate(_plan_content())
    assert first.plan is not None and first.error == ""

    # 不是 PLAN：两者皆空，交给终局门或工具。
    assert harness.interpret_plan("", previous_plan=None, task_id="t") == PlanParseResult(
        None
    )
    assert harness.interpret_plan(
        _finish_content(), previous_plan=None, task_id="t"
    ) == PlanParseResult(None)

    # 写坏的 PLAN：错误文本与 parse_plan_candidate 逐字相同。
    broken = '{"kind": "PLAN", oops'
    assert harness.interpret_plan(broken, previous_plan=None, task_id="t") == (
        parse_plan_candidate(broken)
    )
    assert harness.interpret_plan(broken, previous_plan=None, task_id="t").error

    # 合法修订：revision 递增且不删 answer_elements。
    revised = harness.interpret_plan(
        _plan_content(revision=2, answer_elements=["direct_assessment", "counterpoint"]),
        previous_plan=first.plan,
        task_id="t",
    )
    assert revised.plan is not None and revised.plan.revision == 2

    # 非法修订：revision 不增。错误文本与 validate_plan_revision 抛的逐字相同。
    stale = parse_plan_candidate(_plan_content(revision=1)).plan
    assert stale is not None
    with pytest.raises(ValueError) as caught:
        validate_plan_revision(
            first.plan, stale, original_task_id="t", current_task_id="t"
        )
    rejected = harness.interpret_plan(
        _plan_content(revision=1), previous_plan=first.plan, task_id="t"
    )
    assert rejected == PlanParseResult(None, str(caught.value))


def test_default_steering_messages_are_the_loop_texts_verbatim() -> None:
    """三段文案是从 loop 逐字搬来的；这里把字节钉住，搬错一个字就红。"""

    harness = FinanceResearchHarness()
    assert harness.steering_message("invalid_plan", detail="E") == (
        "上一条 PLAN 无效。请保留最初任务与当前 episode，"
        "只修复为闭合的 PLAN JSON，或直接调用已授权工具；"
        "PLAN 不能授权工具、预算、证据或完成状态。"
        "错误：E"
    )
    assert harness.steering_message("invalid_finish", detail="E") == (
        "上一条终止输出无效。请保留当前任务和全部观察，"
        "不要重启研究；修复后只输出 FINAL_JSON。"
        "错误：E"
    )
    finalization = harness.steering_message("begin_finalization", detail="R")
    assert finalization.startswith("研究阶段已关闭，不得再调用工具。")
    assert finalization.endswith("关闭原因：R")
    assert "draft 控制在 1000 汉字以内" in finalization
    with pytest.raises(ValueError):
        harness.steering_message("nope", detail="")  # type: ignore[arg-type]


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

    def steering_message(self, kind, *, detail):
        self.calls.append(f"steering_message:{kind}")
        return super().steering_message(kind, detail=detail)

    def interpret_plan(self, content, *, previous_plan, task_id):
        self.calls.append("interpret_plan")
        return super().interpret_plan(
            content, previous_plan=previous_plan, task_id=task_id
        )

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


def test_episode_asks_harness_at_all_seams_in_control_flow_order() -> None:
    """PLAN → 工具 → 终局，一次 episode 里 loop 问 harness 的完整顺序。

    每个非 finalization 的模型回合都先问一次 ``interpret_plan``（工具轮的空正文
    与终局轮的 FINAL_JSON 都答「不是 PLAN」），工具批后问停机与取证面，终局问准入。
    """

    frame = _frame()
    evidence = (_evidence("evidence-1"),)
    harness = _RecordingHarness()
    model = _ScriptedModel(
        [
            ModelTurn(_plan_content(), (), "scripted", ""),
            _tool_turn(),
            ModelTurn(_finish_content(), (), "scripted", ""),
        ]
    )

    outcome = ContinuousAgentEpisode(model, harness=harness).run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(evidence),
    )

    assert outcome.status == "completed"
    assert outcome.stop_reason == "model_finish"
    assert outcome.plan is not None
    assert harness.calls == [
        "assemble_prompt",
        "interpret_plan",
        "interpret_plan",
        "halt_after_tool_batch",
        "retrieval_complete",
        "interpret_plan",
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
        # P1b：修复 prompt 也从 assemble_prompt 取两半，不再直接拼。
        "build_episode_input",
        "build_episode_instructions",
    }
)
_EXTRACTED_FROM_RESEARCH_PLAN = frozenset(
    {"parse_plan_candidate", "validate_plan_revision"}
)


def _import_from_names(tree: ast.Module, module: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
    return names


@pytest.mark.parametrize("path", _LOOP_PATHS, ids=lambda p: p.stem)
def test_loops_no_longer_import_extracted_domain_gate_symbols(path: Path) -> None:
    """三条 loop 都只能经 harness 摸到终局门 / prompt。

    ``finish_rejection_fields`` 允许留下：``agent_episode.resume()`` 里「修复轮还在
    调工具」那处用它造字段，与终局校验无关（spec §6）。``build_episode_input`` /
    ``build_episode_instructions`` 在另两条 loop 的修复 prompt 里仍直接用——那是
    P1b「assemble_prompt 扩展」的范围，本棘轮不卡。
    """

    tree = ast.parse(path.read_text(encoding="utf-8"))

    protocol_names = _import_from_names(tree, "intelligence.services.episode_protocol")
    leaked = protocol_names & _EXTRACTED_FROM_EPISODE_PROTOCOL
    assert not leaked, f"{path.name} 直接 import 了已抽走的领域门：{sorted(leaked)}"

    plan_names = _import_from_names(tree, "intelligence.services.research_plan")
    leaked_plan = plan_names & _EXTRACTED_FROM_RESEARCH_PLAN
    assert not leaked_plan, f"{path.name} 直接解析 PLAN 协议：{sorted(leaked_plan)}"

    harness_names = _import_from_names(tree, "intelligence.services.research_harness")
    assert {"FinanceResearchHarness", "ResearchHarness"} <= harness_names


def test_agent_episode_routes_batch_halt_through_harness() -> None:
    tree = ast.parse(_AGENT_EPISODE_PATH.read_text(encoding="utf-8"))
    assert not _import_from_names(
        tree, "intelligence.services.forecast_residual_budget"
    ), "批后停机判定必须经 harness.halt_after_tool_batch"


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


class _PlanBlindHarness(FinanceResearchHarness):
    """看不见 PLAN：任何正文都答「不是 PLAN」。只用于证明 interpret_plan 有牙。"""

    def interpret_plan(self, content, *, previous_plan, task_id):
        del content, previous_plan, task_id
        return PlanParseResult(None)


def test_plan_blind_harness_turns_a_plan_turn_into_an_invalid_finish() -> None:
    """默认 harness 把 PLAN 轮记成 ``plan`` 事件；看不见 PLAN 的 harness 让同一轮
    掉进终局门被驳回——同一脚本、两种 outcome，接缝在起作用。"""

    frame = _frame()
    evidence = (_evidence("evidence-1"),)
    script = [
        ModelTurn(_plan_content(), (), "scripted", ""),
        _tool_turn(),
        ModelTurn(_finish_content(), (), "scripted", ""),
    ]

    seen = ContinuousAgentEpisode(_ScriptedModel(list(script))).run(
        task_frame=frame, context=_context(frame), registry=_registry(evidence)
    )
    assert [e.kind for e in seen.events if e.kind in {"plan", "invalid_action"}] == [
        "plan"
    ]

    blind = ContinuousAgentEpisode(
        _ScriptedModel(list(script)), harness=_PlanBlindHarness()
    ).run(task_frame=frame, context=_context(frame), registry=_registry(evidence))
    kinds = [e.kind for e in blind.events if e.kind in {"plan", "invalid_action"}]
    assert "plan" not in kinds
    assert kinds[0] == "invalid_action"
    assert blind.plan is None


class _CustomSteeringHarness(FinanceResearchHarness):
    def steering_message(self, kind, *, detail):
        return f"CUSTOM[{kind}]{detail}"


def test_steering_texts_reach_the_model_from_the_harness() -> None:
    """驳回回灌与 finalization 提示的字节来自 harness：换 harness，模型看到的话就变。"""

    frame = _frame()
    evidence = (_evidence("evidence-1"),)
    broken_plan = '{"kind": "PLAN", oops'
    model = _ScriptedModel(
        [
            ModelTurn(broken_plan, (), "scripted", ""),
            _tool_turn(),
            ModelTurn("不是 JSON，只是一段话。", (), "scripted", ""),
            ModelTurn(_finish_content(), (), "scripted", ""),
        ]
    )

    outcome = ContinuousAgentEpisode(model, harness=_CustomSteeringHarness()).run(
        task_frame=frame, context=_context(frame), registry=_registry(evidence)
    )

    assert outcome.stop_reason == "model_finish"
    user_texts = [
        str(item["content"])
        for turn_messages in model.seen_messages
        for item in turn_messages
        if item.get("role") == "user"
    ]
    assert any(text.startswith("CUSTOM[invalid_plan]") for text in user_texts)
    assert any(text.startswith("CUSTOM[invalid_finish]") for text in user_texts)


def test_begin_finalization_text_comes_from_the_harness() -> None:
    """工具槽用尽 → loop 关研究阶段，注入的那段话是 harness 的 begin_finalization。"""

    frame = _frame()
    evidence = (_evidence("evidence-1"),)
    model = _ScriptedModel(
        [_tool_turn(), ModelTurn(_finish_content(), (), "scripted", "")]
    )

    ContinuousAgentEpisode(model, harness=_CustomSteeringHarness()).run(
        task_frame=frame,
        context=_context(frame, max_steps=1),
        registry=_registry(evidence),
    )

    last_turn_users = [
        str(item["content"])
        for item in model.seen_messages[-1]
        if item.get("role") == "user"
    ]
    assert any(
        text.startswith("CUSTOM[begin_finalization]tool_budget_exhausted")
        for text in last_turn_users
    )


# ── 4b. 另两条 loop 也在问同一道门（P1a） ─────────────────────────────────


def _sdk_registry(evidence: tuple[AgentEvidence, ...]) -> ResearchToolRegistry:
    """SDK runtime 走 ``request.tools[i].invoke``，工具名沿用 mainline_context 夹具。"""

    def runner(query: str, _context: AgentToolContext):
        del query
        return (
            list(evidence),
            "医药是韧性核心。",
            ProviderTrace(
                provider="test:mainline",
                capability="mainline_context",
                status="success",
                source_trade_date="2026-07-21",
                result_count=len(evidence),
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="mainline_context",
                capability="mainline_context",
                description="同日主线与板块结构",
                cost="local",
                freshness="current",
                runner=runner,
                query_scope="episode",
            ),
        )
    )


def _sdk_context(frame: TaskFrame) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="harness-sdk-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("mainline_context",), True),
        ),
        allowed_capabilities=("mainline_context",),
        research_tier="quick",
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", 2, 30.0, 0.0),
        trace_parent_id="harness-sdk-test",
        today="2026-07-22",
        latest_data_date="2026-07-21",
    )


def _forged_sdk_runner(request):
    from intelligence.runtime.openai_agents_runtime import AgentsSdkResult

    request.tools[0].invoke("A股 当前主线")
    return AgentsSdkResult(_finish_content(hashes=("forged-hash",)), 1, 500, 80, 1)


def test_sdk_runtime_default_harness_rejects_forged_finish() -> None:
    from intelligence.runtime.openai_agents_runtime import OpenAIAgentsRuntime

    frame = _frame()
    evidence = (
        AgentEvidence(
            tool="mainline_context",
            title="同日主线结构",
            detail="医药是韧性核心。",
            source="本地正式日报",
            source_date="2026-07-21",
            evidence_tier="L4",
            content_hash="mainline-hash",
        ),
    )
    outcome = OpenAIAgentsRuntime(
        runner=_forged_sdk_runner, backend="sdk_glm", model_name="glm-5.2"
    ).run(task_frame=frame, context=_sdk_context(frame), registry=_sdk_registry(evidence))

    assert outcome.stop_reason == "sdk_invalid_finish"
    assert outcome.status == "partial"
    assert outcome.draft == ""


def test_sdk_runtime_permissive_harness_accepts_the_same_finish() -> None:
    from intelligence.runtime.openai_agents_runtime import OpenAIAgentsRuntime

    frame = _frame()
    evidence = (
        AgentEvidence(
            tool="mainline_context",
            title="同日主线结构",
            detail="医药是韧性核心。",
            source="本地正式日报",
            source_date="2026-07-21",
            evidence_tier="L4",
            content_hash="mainline-hash",
        ),
    )
    outcome = OpenAIAgentsRuntime(
        runner=_forged_sdk_runner,
        backend="sdk_glm",
        model_name="glm-5.2",
        harness=_PermissiveHarness(),
    ).run(task_frame=frame, context=_sdk_context(frame), registry=_sdk_registry(evidence))

    assert outcome.stop_reason == "model_finish"
    assert outcome.status == "completed"
    assert outcome.draft == json.loads(_finish_content())["draft"]


def test_codex_finish_issue_and_prompt_go_through_harness() -> None:
    from intelligence.runtime import codex_headless_runtime as codex

    frame = _frame()
    context = _context(frame)
    evidence = (_evidence("evidence-1"),)
    registry = _registry(evidence)
    process = codex.HeadlessProcessResult(stdout="", stderr="", returncode=0)
    parsed = codex._ParsedJSONL(
        final_text=_finish_content(hashes=("forged-hash",)),
        thread_id="t",
        input_tokens=None,
        output_tokens=None,
        completed_turns=1,
        issues=(),
    )
    snapshot = codex._empty_snapshot()

    assert (
        codex._finish_issue(
            process=process,
            parsed=parsed,
            context=context,
            snapshot=snapshot,
            registry=registry,
            harness=FinanceResearchHarness(),
        )
        == "headless_invalid_finish"
    )
    assert (
        codex._finish_issue(
            process=process,
            parsed=parsed,
            context=context,
            snapshot=snapshot,
            registry=registry,
            harness=_PermissiveHarness(),
        )
        is None
    )

    recording = _RecordingHarness()
    prompt = codex._headless_prompt(
        task_frame=frame,
        context=context,
        registry=registry,
        wrapper_path=Path("/tmp/finance-tool"),
        harness=recording,
    )
    assert recording.calls == ["assemble_prompt"]
    system, _user = split_episode_prompt(frame, context, registry)
    assert prompt.startswith(system)


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

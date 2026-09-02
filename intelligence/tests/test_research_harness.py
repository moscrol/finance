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
import itertools
import json
from pathlib import Path

import pytest

import intelligence.runtime.agent_episode as agent_episode_module
import intelligence.services.research_contract as research_contract_module
from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    ModelToolCall,
    ModelTurn,
    OutputEvidenceBinding,
)
from intelligence.services.agent_runtime import public_agent_evidence
from intelligence.services.episode_protocol import (
    attach_evidence_ordinals,
    evidence_ordinal_table,
    expand_episode_snapshot_bindings,
    finish_rejection_fields,
    rejection_response,
    split_episode_prompt,
    strip_hashes_for_model,
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
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
from intelligence.services.research_harness import (
    FinanceResearchHarness,
    FinishAdmission,
    RepairVerdict,
    ResearchHarness,
    ToolResultProjection,
)
from intelligence.services.research_plan import (
    PlanParseResult,
    parse_plan_candidate,
    validate_plan_revision,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolObservation,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.tool_observation_noise import prune_tool_observation
from intelligence.services.tool_result_budget import budget_tool_observation

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


def _observation(
    evidence: tuple[AgentEvidence, ...], *, telemetry: dict[str, object] | None = None
) -> ToolObservation:
    return ToolObservation(
        tool="market_data",
        query="当前市场结构",
        evidence=evidence,
        observation="上涨家数增加，成交保持活跃。",
        trace=ProviderTrace(
            provider="test:market",
            capability="market_data",
            status="success",
            source_trade_date="2026-07-21",
            result_count=len(evidence),
        ),
        gaps=("缺少反方证据",),
        evidence_hashes=tuple(item.content_hash for item in evidence),
        dataset="stock_daily",
        caliber="fact_stock_daily",
        payload_field_names=("close", "return_pct"),
        payload_sha256="abc123",
        telemetry=dict(telemetry or {}),
    )


def test_default_project_tool_result_equals_the_inline_projection() -> None:
    """审计底稿 = 全量含 hash / telemetry；模型正文 = 去重 → 预算 → 去 hash 只留 E<n>。"""

    evidence = (_evidence("evidence-1"), _evidence("evidence-2", title="第二条"))
    observation = _observation(evidence, telemetry={"queued_ms": 3})
    harness = FinanceResearchHarness()

    projection = harness.project_tool_result(
        observation, evidence_so_far=evidence, seen_prose=set()
    )

    ordinals = evidence_ordinal_table(evidence)
    expected_audit = {
        "ok": True,
        "tool": "market_data",
        "query": "当前市场结构",
        "observation": "上涨家数增加，成交保持活跃。",
        "evidence": attach_evidence_ordinals(
            [public_agent_evidence(item) for item in evidence], ordinals
        ),
        "evidence_hashes": ["evidence-1", "evidence-2"],
        "evidence_ids": ["E1", "E2"],
        "gaps": ["缺少反方证据"],
        "dataset": "stock_daily",
        "caliber": "fact_stock_daily",
        "payload_field_names": ["close", "return_pct"],
        "payload_sha256": "abc123",
        "telemetry": {"queued_ms": 3},
    }
    assert projection.audit_payload == expected_audit

    model_view = dict(expected_audit)
    model_view.pop("telemetry")
    pruned, seen = prune_tool_observation(model_view, seen_prose=set())
    assert projection.model_content == json.dumps(
        strip_hashes_for_model(budget_tool_observation(pruned)), ensure_ascii=False
    )
    assert projection.seen_prose == frozenset(seen)

    facing = json.loads(projection.model_content)
    assert "telemetry" not in facing
    assert "evidence_hashes" not in facing
    assert facing["evidence_ids"] == ["E1", "E2"]
    assert all("content_hash" not in row for row in facing["evidence"])

    # 第二次同一段叙述：去重账本让它折叠，且账本状态往前走。
    again = harness.project_tool_result(
        observation, evidence_so_far=evidence, seen_prose=set(projection.seen_prose)
    )
    assert again.audit_payload == expected_audit
    assert json.loads(again.model_content).get("observation") != facing["observation"]


def test_default_govern_mode_equals_governor_decide_apply_and_message() -> None:
    """govern_mode = 信号 → 依赖修正 → decide → apply → MODE_DECISION 文案，与原
    `_decide_mode` + `_append_mode_decision_message` 逐字段相同。"""

    from intelligence.services.mode_governor import ModeGovernor, ModeSignals
    from intelligence.services.research_harness import default_mode_signals

    frame = _frame()
    context = _context(frame)
    plan = parse_plan_candidate(_plan_content()).plan
    assert plan is not None

    governance = FinanceResearchHarness().govern_mode(
        task_frame=frame, plan=plan, context=context, can_branch=False
    )

    signals = default_mode_signals(frame, plan)
    # 无 root ledger → 依赖不可用（原 _decide_mode 第一条修正）。
    assert context.root_budget is None
    expected_signals = ModeSignals(
        independent_entities=signals.independent_entities,
        separable_branches=signals.separable_branches,
        evidence_domains=signals.evidence_domains,
        uncovered_answer_elements=signals.uncovered_answer_elements,
        dependencies_available=False,
    )
    decision = ModeGovernor().decide(plan, expected_signals)
    assert governance.decision == decision
    assert governance.context == ModeGovernor().apply(context, decision)
    assert json.loads(governance.message) == {
        "kind": "MODE_DECISION",
        **decision.to_dict(),
        "instruction": (
            "研究深度与总预算已由运行时裁决。保留原计划，"
            "继续自主选择查询、工具顺序和停止时点；"
            "不得把预算或内部裁决文本写入最终答案。"
        ),
    }


def test_govern_mode_honours_injected_governor_and_signals() -> None:
    """mode_governor / mode_signals 两个注入件搬到了 harness 构造器上。"""

    from intelligence.services.mode_governor import ModeGovernor, ModeSignals

    class RecordingGovernor(ModeGovernor):
        def __init__(self) -> None:
            self.seen: list[ModeSignals] = []

        def decide(self, plan, signals):
            self.seen.append(signals)
            return super().decide(plan, signals)

    governor = RecordingGovernor()
    frame = _frame()
    plan = parse_plan_candidate(_plan_content()).plan
    assert plan is not None
    FinanceResearchHarness(
        mode_governor=governor,
        mode_signals=lambda _frame, _plan: ModeSignals(user_mode="quick"),
    ).govern_mode(task_frame=frame, plan=plan, context=_context(frame), can_branch=True)
    assert len(governor.seen) == 1 and governor.seen[0].user_mode == "quick"


def test_episode_no_longer_accepts_mode_injection_at_all() -> None:
    """转交壳已删：注入件只认 harness 构造器这一个入口。

    #529 把 mode_governor / mode_signals 搬进 harness 时，Episode 上留了一层转交壳
    兼容既有调用方，并对「两处都想管深度」抛 ValueError。调用方
    （glm_agent_runtime / continuous_sub_research）改直传 harness 后壳即删——
    现在连形参都没有，多传是 TypeError 而不是 ValueError。

    钉 TypeError 是为了让壳**回焊时会红**：若有人再把形参加回来，
    这条会退化成 ValueError（带 harness）或静默通过（不带），两种都失败。
    """

    from intelligence.services.mode_governor import ModeGovernor

    with pytest.raises(TypeError):
        ContinuousAgentEpisode(_ScriptedModel([]), mode_governor=ModeGovernor())
    with pytest.raises(TypeError):
        ContinuousAgentEpisode(
            _ScriptedModel([]),
            harness=FinanceResearchHarness(),
            mode_signals=lambda _frame, _plan: None,
        )


def test_default_project_sub_research_equals_inline_projection() -> None:
    """分支证据按主 episode 累计序号呈现、去 hash；文案逐字与原 _append_sub_research_message 同。"""

    from dataclasses import dataclass as _dc

    @_dc(frozen=True)
    class _Branch:
        branch_id: str
        goal: str
        status: str
        evidence: tuple[AgentEvidence, ...]
        gaps: tuple[str, ...]

    main_evidence = (_evidence("evidence-1"), _evidence("branch-1", title="反方驱动证据"))
    branches = (
        _Branch("branch-1", "反方证据", "completed", (main_evidence[1],), ("缺少量能数据",)),
        _Branch("branch-2", "资金面", "failed", (), ("超时",)),
    )

    text = FinanceResearchHarness().project_sub_research(
        branches=branches, refused_reason="", evidence=main_evidence
    )

    ordinals = evidence_ordinal_table(main_evidence)
    expected = {
        "kind": "SUB_RESEARCH_RESULTS",
        "branches": [
            {
                "branch_id": "branch-1",
                "goal": "反方证据",
                "status": "completed",
                "evidence": strip_hashes_for_model(
                    {
                        "evidence": attach_evidence_ordinals(
                            [public_agent_evidence(main_evidence[1])], ordinals
                        )
                    }
                )["evidence"],
                "gaps": ["缺少量能数据"],
            },
            {
                "branch_id": "branch-2",
                "goal": "资金面",
                "status": "failed",
                "evidence": [],
                "gaps": ["超时"],
            },
        ],
        "refused_reason": "",
        "instruction": (
            "这些是只读分支返回的公开证据观察，不是最终答案。"
            "主 episode 仍需自行比较证据、处理冲突并决定停止；"
            "绑定用证据序号 E1、E2…，不得把分支状态或内部标识写入公开答案。"
        ),
    }
    assert json.loads(text) == expected
    branch_rows = json.loads(text)["branches"][0]["evidence"]
    assert branch_rows[0]["evidence_id"] == "E2"
    assert all("content_hash" not in row for row in branch_rows)


def test_agent_episode_no_longer_projects_evidence_ordinals_itself() -> None:
    """三个序号函数的最后一个直接调用点（子研究消息）也进了 harness。"""

    tree = ast.parse(_AGENT_EPISODE_PATH.read_text(encoding="utf-8"))
    protocol_names = _import_from_names(tree, "intelligence.services.episode_protocol")
    assert not protocol_names & {
        "evidence_ordinal_table",
        "attach_evidence_ordinals",
        "strip_hashes_for_model",
    }
    # 到此为止 loop 从 episode_protocol 只剩下常量与一个非门的字段函数。
    assert protocol_names <= {"SYSTEM_PROMPT_DYNAMIC_BOUNDARY", "finish_rejection_fields"}


def test_default_project_tool_error_shape_and_detail_cap() -> None:
    payload = FinanceResearchHarness().project_tool_error(
        tool="kb_search", error="tool_timeout", detail="x" * 500
    )
    assert payload == {
        "ok": False,
        "tool": "kb_search",
        "error": "tool_timeout",
        "detail": "x" * 400,
    }
    assert FinanceResearchHarness().project_tool_error(
        tool="kb_search", error="tool_timeout", detail=""
    )["detail"] == ""


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
        super().__init__()
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

    def govern_mode(self, *, task_frame, plan, context, can_branch):
        self.calls.append("govern_mode")
        return super().govern_mode(
            task_frame=task_frame, plan=plan, context=context, can_branch=can_branch
        )

    def project_tool_result(self, observation, *, evidence_so_far, seen_prose):
        self.calls.append("project_tool_result")
        return super().project_tool_result(
            observation, evidence_so_far=evidence_so_far, seen_prose=seen_prose
        )

    def project_tool_error(self, *, tool, error, detail):
        self.calls.append("project_tool_error")
        return super().project_tool_error(tool=tool, error=error, detail=detail)

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
        "govern_mode",
        "interpret_plan",
        "project_tool_result",
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


def test_agent_episode_routes_tool_view_through_harness() -> None:
    """模型看到的工具结果（去重 / 预算 / 去 hash）只能由 harness.project_tool_result 产出。"""

    tree = ast.parse(_AGENT_EPISODE_PATH.read_text(encoding="utf-8"))
    assert not _import_from_names(
        tree, "intelligence.services.tool_observation_noise"
    ), "观察叙述去重必须经 harness.project_tool_result"
    assert not _import_from_names(
        tree, "intelligence.services.tool_result_budget"
    ), "工具结果预算必须经 harness.project_tool_result"


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


class _CustomToolViewHarness(FinanceResearchHarness):
    """模型看到的工具结果由 harness 决定：审计底稿照旧，模型正文换成标记串。"""

    def project_tool_result(self, observation, *, evidence_so_far, seen_prose):
        base = super().project_tool_result(
            observation, evidence_so_far=evidence_so_far, seen_prose=seen_prose
        )
        return ToolResultProjection(
            audit_payload=base.audit_payload,
            model_content=json.dumps({"ok": True, "view": "CUSTOM_TOOL_VIEW"}),
            seen_prose=base.seen_prose,
        )

    def project_tool_error(self, *, tool, error, detail):
        return {"ok": False, "tool": tool, "error": f"CUSTOM:{error}", "detail": detail}


def test_tool_view_reaching_the_model_comes_from_the_harness() -> None:
    frame = _frame()
    evidence = (_evidence("evidence-1"),)
    model = _ScriptedModel(
        [_tool_turn(), ModelTurn(_finish_content(), (), "scripted", "")]
    )

    outcome = ContinuousAgentEpisode(model, harness=_CustomToolViewHarness()).run(
        task_frame=frame, context=_context(frame), registry=_registry(evidence)
    )

    assert outcome.stop_reason == "model_finish"
    tool_messages = [
        json.loads(str(item["content"]))
        for item in model.seen_messages[-1]
        if item.get("role") == "tool"
    ]
    assert len(tool_messages) == 1
    facing = tool_messages[0]
    # harness 给的正文原样在；底座只在最后一条工具消息上叠一个 ``runtime_budget``
    # （spec §4 #9：预算可见性属底座，不抽）。两层的边界正好是这一个键。
    assert facing["ok"] is True and facing["view"] == "CUSTOM_TOOL_VIEW"
    assert set(facing) == {"ok", "view", "runtime_budget"}
    # 审计底稿不受模型视图替换影响：durable tool_result 仍是全量投影。
    results = [e for e in outcome.events if e.kind == "tool_result"]
    assert len(results) == 1
    # 账本把 list 冻成 tuple，按值比。
    assert list(results[0].payload["evidence_ids"]) == ["E1"]
    assert list(results[0].payload["evidence_hashes"]) == ["evidence-1"]


def test_tool_error_view_reaching_the_model_comes_from_the_harness() -> None:
    frame = _frame()

    def exploding_runner(query: str, _context: AgentToolContext):
        raise RuntimeError(f"boom {query}")

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="会炸的行情",
                cost="local",
                freshness="current",
                runner=exploding_runner,
            ),
        )
    )
    model = _ScriptedModel(
        [_tool_turn(), ModelTurn(_finish_content(hashes=()), (), "scripted", "")]
    )

    ContinuousAgentEpisode(model, harness=_CustomToolViewHarness()).run(
        task_frame=frame, context=_context(frame), registry=registry
    )

    tool_messages = [
        json.loads(str(item["content"]))
        for item in model.seen_messages[-1]
        if item.get("role") == "tool"
    ]
    assert tool_messages and tool_messages[0]["ok"] is False
    assert tool_messages[0]["error"].startswith("CUSTOM:")


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


# ── 7. 修复轮接缝：repair_goal_message / repair_finalize / admit_repair_result ──
#
# 来源：docs/superpowers/specs/2026-09-02-repair-policy-state-machine.md §3.2
# 「REPAIR_GOAL 消息文案 + 工具开/关两套 instruction 分支」与「repair_progressed
# 三元判定 + current_gaps 兜底文案」——resume() 里最后两段领域内容。


def _repair_goal(*, remaining_calls: int = 1, remaining_seconds: float = 8.0) -> RepairGoal:
    return RepairGoal(
        episode_id="harness-test",
        repair_goal_id="repair-harness-test-1",
        cycle=1,
        missing_answer_elements=("direct_assessment",),
        unsupported_claims=(),
        missing_evidence_modes=(),
        attempted_actions=("market_data:test",),
        evidence_progress=CoverageDelta(1, 0, 1),
        remaining_calls=remaining_calls,
        remaining_seconds=remaining_seconds,
    )


def _legacy_repair_goal_message(goal: RepairGoal, *, tools_open: bool) -> str:
    """拆分前 agent_episode.resume() 里 REPAIR_GOAL 的原构造——被抽走的合同。"""

    return json.dumps(
        {
            "kind": "REPAIR_GOAL",
            **goal.to_dict(),
            "instruction": (
                "保留最初任务、全部原始观察和当前工具账本。"
                + (
                    "自主选择一个新的、未重复的动作补齐缺口；"
                    if tools_open
                    else "研究工具已关闭，只能基于已有观察修复措辞或证据绑定；"
                )
                + "不得重启研究或改写用户问题。"
            ),
        },
        ensure_ascii=False,
    )


def test_default_repair_goal_message_is_the_loop_text_verbatim() -> None:
    harness = FinanceResearchHarness()
    goal = _repair_goal()
    for tools_open in (True, False):
        assert harness.repair_goal_message(goal, tools_open=tools_open) == (
            _legacy_repair_goal_message(goal, tools_open=tools_open)
        )
    assert harness.steering_message("repair_finalize", detail="") == (
        "修复动作已执行。不得再调用工具；请基于同一 episode 的"
        "全部观察输出 FINAL_JSON，未补齐项继续明确写 gap。"
    )


def _accepted_admission(*, status: str, draft: str, bindings, gaps=()) -> FinishAdmission:
    return FinishAdmission(
        accepted=True,
        status=status,  # type: ignore[arg-type]
        draft=draft,
        bindings=bindings,
        gaps=tuple(gaps),
        caveat_slips=0,
        rejection=finish_rejection_fields(),
    )


def _previous_outcome(*, draft: str, bindings) -> AgentOutcome:
    frame = _frame()
    return AgentOutcome(
        task_frame_hash=frame.task_frame_hash,
        status="partial",
        draft=draft,
        evidence=(_evidence("evidence-1"),),
        traces=(),
        gaps=("缺口",),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
        bindings=bindings,
        usage=AgentUsage(),
    )


def test_default_admit_repair_result_equals_loop_verdict_on_full_grid() -> None:
    """拆分前 resume() 的三元判定逐格相等：动手 × 状态 × 改稿 × 改绑定 × 有无 gap。"""

    harness = FinanceResearchHarness()
    old_bindings = (OutputEvidenceBinding("direct_assessment", ("evidence-1",)),)
    new_bindings = (OutputEvidenceBinding("direct_assessment", ("evidence-1", "evidence-2")),)
    previous = _previous_outcome(draft="旧稿", bindings=old_bindings)
    seen_progressed = {True: 0, False: 0}
    for performed, status, draft, bindings, gaps in itertools.product(
        (True, False),
        ("completed", "partial"),
        ("旧稿", " 旧稿 ", "新稿"),
        (old_bindings, new_bindings),
        ((), ("仍缺反方",)),
    ):
        admission = _accepted_admission(status=status, draft=draft, bindings=bindings, gaps=gaps)
        verdict = harness.admit_repair_result(
            admission=admission, previous=previous, performed_tool_action=performed
        )
        # 被抽走的合同（agent_episode.resume() 原文，逐行）：
        revised = draft.strip() != previous.draft.strip() or bindings != previous.bindings
        completed_without_tool = not performed and status == "completed" and revised
        legacy_status = status if performed or completed_without_tool else "partial"
        legacy_gaps = tuple(gaps)
        if not performed and not completed_without_tool and not legacy_gaps:
            legacy_gaps = ("修复轮未执行新的取证动作，缺口仍未补齐",)
        legacy_progressed = performed or completed_without_tool
        assert verdict == RepairVerdict(legacy_status, legacy_gaps, legacy_progressed), (
            performed, status, draft, bindings is new_bindings, gaps
        )
        seen_progressed[verdict.progressed] += 1
    assert seen_progressed[True] and seen_progressed[False]


def test_admit_repair_result_refuses_rejected_admission() -> None:
    rejected = FinanceResearchHarness().admit_finish(
        "不是 JSON", context=_context(_frame()), evidence=(), registry=_registry(())
    )
    assert not rejected.accepted
    with pytest.raises(ValueError):
        FinanceResearchHarness().admit_repair_result(
            admission=rejected,
            previous=_previous_outcome(draft="", bindings=()),
            performed_tool_action=False,
        )


class _CustomRepairHarness(FinanceResearchHarness):
    """修复轮的两段话与裁决都换掉：接缝有牙的对照物。"""

    def repair_goal_message(self, goal, *, tools_open):
        return f"CUSTOM[REPAIR_GOAL]{goal.repair_goal_id}:{tools_open}"

    def steering_message(self, kind, *, detail):
        if kind == "repair_finalize":
            return "CUSTOM[repair_finalize]"
        return super().steering_message(kind, detail=detail)

    def admit_repair_result(self, *, admission, previous, performed_tool_action):
        del previous, performed_tool_action
        return RepairVerdict(status=admission.status, gaps=admission.gaps, progressed=True)


def _run_then_resume(harness, *, resume_turns: list[ModelTurn], remaining_calls: int):
    """跑一集到 partial 终局，再用同一段历史做一轮修复。返回 (model, 修复 outcome)。"""

    frame = _frame()
    evidence = (_evidence("evidence-1"),)
    model = _ScriptedModel(
        [
            _tool_turn(),
            ModelTurn(_finish_content(status="partial", gap="仍缺反方"), (), "scripted", ""),
            *resume_turns,
        ]
    )
    episode = ContinuousAgentEpisode(model, harness=harness)
    continuation: list = []
    first = episode.run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(evidence),
        _continuation_sink=continuation,
    )
    assert first.stop_reason == "model_finish"
    repaired = episode.resume(
        continuation[0], first, _repair_goal(remaining_calls=remaining_calls)
    )
    return model, repaired


def test_repair_goal_and_finalize_texts_reach_the_model_from_the_harness() -> None:
    """修复轮开场话与工具后收口话的字节都来自 harness：换 harness，模型看到的就变。"""

    model, repaired = _run_then_resume(
        _CustomRepairHarness(),
        resume_turns=[
            _tool_turn(),
            ModelTurn(_finish_content(status="completed"), (), "scripted", ""),
        ],
        remaining_calls=1,
    )

    assert repaired.stop_reason == "repair_model_finish"
    user_texts = [
        str(item["content"])
        for turn_messages in model.seen_messages[2:]
        for item in turn_messages
        if item.get("role") == "user"
    ]
    assert any(text == "CUSTOM[REPAIR_GOAL]repair-harness-test-1:True" for text in user_texts)
    assert "CUSTOM[repair_finalize]" in user_texts


def test_repair_verdict_from_harness_changes_outcome_so_the_seam_has_teeth() -> None:
    """同一份「没动手、稿没改」的修复轮：默认 harness 判 stop，改判的 harness 让它 finish。"""

    unchanged = _finish_content(status="partial", gap="仍缺反方")

    _, default_outcome = _run_then_resume(
        FinanceResearchHarness(),
        resume_turns=[ModelTurn(unchanged, (), "scripted", "")],
        remaining_calls=0,
    )
    assert default_outcome.stop_reason == "repair_model_stop"
    assert default_outcome.status == "partial"

    _, custom_outcome = _run_then_resume(
        _CustomRepairHarness(),
        resume_turns=[ModelTurn(unchanged, (), "scripted", "")],
        remaining_calls=0,
    )
    assert custom_outcome.stop_reason == "repair_model_finish"
    finish = [event for event in custom_outcome.events if event.kind == "finish"][-1]
    assert finish.payload["stop_reason"] == "repair_model_finish"


def test_resume_no_longer_carries_repair_wording_or_verdict() -> None:
    """棘轮：REPAIR_GOAL 文案、收口指令、兜底 gap、三元判定都不得回焊进 loop。"""

    source = _AGENT_EPISODE_PATH.read_text(encoding="utf-8")
    for needle in (
        '"REPAIR_GOAL"',
        "自主选择一个新的、未重复的动作补齐缺口",
        "研究工具已关闭，只能基于已有观察修复措辞或证据绑定",
        "修复动作已执行。不得再调用工具",
        "修复轮未执行新的取证动作，缺口仍未补齐",
        "completed_without_tool",
        "revised_without_tool",
    ):
        assert needle not in source, needle
    assert "repair_goal_message(" in source
    assert 'steering_message(\n                        "repair_finalize"' in source
    assert "admit_repair_result(" in source

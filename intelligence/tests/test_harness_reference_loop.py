"""HarnessReferenceLoop 与 ContinuousAgentEpisode：同一 harness，是不是同一台机器。

spec §9 P2'。判据分三层，越往下越严：

1. **首轮身份**（09-01 形状对齐用过的门）：同一脚本、同一注册表，两条 loop 发给模型的
   第一条请求（system / user / tools）字节相同。
2. **全程消息**：无 PLAN 的脚本，两条 loop 给模型看的全部消息一致——只允许差
   ``runtime_budget`` 这一个键（Episode 的底座预算注入，spec §4 #9 不抽）。
3. **终局 outcome**：status / draft / bindings / gaps / stop_reason / plan / evidence 一致。

有 PLAN 的脚本，消息 diff 被钉成**恰好一条** Episode 独有的 ``MODE_DECISION``——那是
mode 治理（spec §4 #5，P2）仍焊在 Episode 里的证据。这条测试的作用是让「还剩什么没抽」
变成可判定的读数，而不是一句话。
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.episode_tool_batch import stage_timeout_granted_detail
from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_protocol import finish_rejection_fields
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.repair_coordinator import CoverageDelta
from intelligence.services.research_harness import (
    FinanceResearchHarness,
    FinishAdmission,
    RepairGoal,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame

_LOOP_PATH = (
    Path(__file__).resolve().parents[1] / "runtime" / "harness_reference_loop.py"
)


# ── 夹具 ─────────────────────────────────────────────────────────────────


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _context(frame: TaskFrame, *, max_steps: int = 3) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="reference-loop-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=(
            RequiredOutput("direct_assessment", "direct_assessment", ("market_data",), True),
        ),
        allowed_capabilities=("market_data",),
        research_tier="quick",
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", max_steps, 30.0, 0.0),
        trace_parent_id="reference-loop-test",
        today="2026-07-22",
        latest_data_date="2026-07-21",
    )


def _evidence(content_hash: str) -> AgentEvidence:
    return AgentEvidence(
        tool="market_data",
        title="A股市场总览",
        detail="上涨家数增加，成交保持活跃",
        source="本地行情",
        source_date="2026-07-21",
        evidence_tier="L4",
        content_hash=content_hash,
    )


def _registry() -> ResearchToolRegistry:
    def runner(query: str, _context: AgentToolContext):
        del query
        return (
            [_evidence("evidence-1")],
            "raw market observation",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="success",
                source_trade_date="2026-07-21",
                result_count=1,
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
            ),
        )
    )


def _plan_turn() -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "kind": "PLAN",
                "task_summary": "判断市场主线并给出反方",
                "answer_elements": ["direct_assessment"],
                "hypotheses": ["半导体可能是持续主线"],
                "evidence_needs": ["同日主线与持续性"],
                "candidate_actions": ["market_data"],
                "open_gaps": ["缺少反方证据"],
                "requested_mode": "quick",
                "revision": 1,
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


def _tool_turn() -> ModelTurn:
    return ModelTurn(
        "",
        (ModelToolCall("call-1", "market_data", {"query": "当前市场结构"}),),
        "scripted",
        "",
    )


def _finish_turn(*, hashes: tuple[str, ...] = ("evidence-1",)) -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "status": "completed",
                "draft": "当前更接近条件化修复，持续性取决于量能。",
                "gaps": [],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": list(hashes),
                        "gap": "",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


class _ScriptedModel:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self._turns = iter(turns)
        self.calls: list[dict[str, object]] = []

    def complete(self, *, messages, tools, timeout):
        self.calls.append(
            {"messages": deepcopy(messages), "tools": deepcopy(tools), "timeout": timeout}
        )
        return next(self._turns)


def _run_both(script: list[ModelTurn], *, harness=None):
    frame = _frame()
    episode_model = _ScriptedModel(list(script))
    reference_model = _ScriptedModel(list(script))
    episode = ContinuousAgentEpisode(episode_model, harness=harness).run(
        task_frame=frame, context=_context(frame), registry=_registry()
    )
    reference = HarnessReferenceLoop(reference_model, harness=harness).run(
        task_frame=frame, context=_context(frame), registry=_registry()
    )
    return (episode_model, episode), (reference_model, reference)


def _strip_runtime_budget(message: dict[str, object]) -> dict[str, object]:
    """Episode 在最后一条工具消息上叠的底座预算键，比对时摘掉。"""

    if message.get("role") != "tool":
        return message
    payload = json.loads(str(message["content"]))
    if isinstance(payload, dict) and "runtime_budget" in payload:
        payload = dict(payload)
        payload.pop("runtime_budget")
        return {**message, "content": json.dumps(payload, ensure_ascii=False)}
    return message


def _outcome_core(outcome) -> dict[str, object]:
    return {
        "status": outcome.status,
        "draft": outcome.draft,
        "bindings": tuple(item.to_dict() for item in outcome.bindings)
        if outcome.bindings
        else (),
        "gaps": tuple(outcome.gaps),
        "stop_reason": outcome.stop_reason,
        "plan": outcome.plan,
        "evidence": tuple(item.content_hash for item in outcome.evidence),
        "tool_calls": outcome.usage.tool_calls,
        "invalid_actions": outcome.usage.invalid_actions,
    }


# ── 1. 首轮身份 ───────────────────────────────────────────────────────────


def test_first_request_to_the_model_is_byte_identical() -> None:
    (episode_model, _), (reference_model, _) = _run_both(
        [_tool_turn(), _finish_turn()]
    )
    assert episode_model.calls[0]["messages"] == reference_model.calls[0]["messages"]
    assert episode_model.calls[0]["tools"] == reference_model.calls[0]["tools"]
    assert episode_model.calls[0]["tools"], "首轮必须带工具定义"


# ── 2. 全程消息（无 PLAN） ───────────────────────────────────────────────


def test_without_plan_every_message_the_model_sees_is_identical_modulo_budget() -> None:
    (episode_model, episode), (reference_model, reference) = _run_both(
        [_tool_turn(), _finish_turn()]
    )

    assert len(episode_model.calls) == len(reference_model.calls) == 2
    for turn_index, (a, b) in enumerate(zip(episode_model.calls, reference_model.calls)):
        assert a["tools"] == b["tools"], f"turn {turn_index} tools differ"
        left = [_strip_runtime_budget(m) for m in a["messages"]]
        right = [_strip_runtime_budget(m) for m in b["messages"]]
        assert left == right, f"turn {turn_index} messages differ"

    # 唯一允许的差就是那一个键：Episode 有、参考 loop 没有。
    episode_tool = [
        json.loads(str(m["content"]))
        for m in episode_model.calls[-1]["messages"]
        if m.get("role") == "tool"
    ]
    reference_tool = [
        json.loads(str(m["content"]))
        for m in reference_model.calls[-1]["messages"]
        if m.get("role") == "tool"
    ]
    assert "runtime_budget" in episode_tool[0]
    assert "runtime_budget" not in reference_tool[0]

    assert _outcome_core(episode) == _outcome_core(reference)
    assert episode.stop_reason == "model_finish" and episode.status == "completed"


def _gap_finish_turn() -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "status": "partial",
                "draft": "工具窗口已关，本轮只能报告证据缺口。",
                "gaps": ["行情工具未派发"],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": [],
                        "gap": "行情工具未派发",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


def test_zero_grant_timeout_is_the_same_machine() -> None:
    """时间闸零授权（研究窗已被 reserve 吃光）：两条 loop 给模型看的 ``tool_not_dispatched``
    detail 必须同为实授值 ``stage_timeout_granted=0``，不是一边有数一边空串。

    2026-09-01 预算单 P0/P0.1 让 Episode 在零授权未派发时回灌实授值；这一格是底座
    （派发时钟）的事，所以参考 loop 也走同一个 ``timeout_detail_for_model``。
    """

    frame = _frame()

    def zero_grant_context() -> ResearchRunContext:
        return replace(
            _context(frame, max_steps=6),
            deadline=ResearchDeadline.from_timeout(5.0, synthesis_reserve=60.0),
            policy=ResearchPolicy("standard", 6, 90.0, 60.0),
        )

    script = [_tool_turn(), _gap_finish_turn()]
    episode_model = _ScriptedModel(list(script))
    reference_model = _ScriptedModel(list(script))
    episode = ContinuousAgentEpisode(episode_model).run(
        task_frame=frame, context=zero_grant_context(), registry=_registry()
    )
    reference = HarnessReferenceLoop(reference_model).run(
        task_frame=frame, context=zero_grant_context(), registry=_registry()
    )

    assert len(episode_model.calls) == len(reference_model.calls) == 2
    assert episode_model.calls[0]["messages"] == reference_model.calls[0]["messages"]

    # 第二轮：参考 loop 的消息是 Episode 的前缀。Episode 多出的恰好一条是底座研究窗
    # 规则（时钟被 reserve 吃光 → 关研究阶段）注入的 begin_finalization 话，spec §4 #9
    # 明写属底座、参考 loop 没有；tool_timeout 那一格两边必须一字不差。
    left = [_strip_runtime_budget(m) for m in episode_model.calls[1]["messages"]]
    right = [_strip_runtime_budget(m) for m in reference_model.calls[1]["messages"]]
    assert left[: len(right)] == right
    extra = left[len(right) :]
    assert len(extra) == 1 and extra[0]["role"] == "user"
    assert str(extra[0]["content"]).endswith("关闭原因：retrieval_deadline_closed")

    for model in (episode_model, reference_model):
        tool_payloads = [
            json.loads(str(m["content"]))
            for m in model.calls[1]["messages"]
            if m.get("role") == "tool"
        ]
        # 零授权未派发是 tool_not_dispatched（INV-R4，#28），不再与真超时共用 tool_timeout。
        assert tool_payloads and tool_payloads[0]["error"] == "tool_not_dispatched"
        assert tool_payloads[0]["detail"] == stage_timeout_granted_detail(0.0)

    assert _outcome_core(episode) == _outcome_core(reference)


def _registry_with_slow_kb() -> ResearchToolRegistry:
    """market_data（无最小窗）+ kb_search（领域申报最少 20s）。kb 的 runner 不该被点到。"""

    base = _registry()

    def never(query: str, _context: AgentToolContext):
        raise AssertionError(f"kb_search 本轮应被藏起来，却被调用了：{query}")

    return ResearchToolRegistry(
        (
            *base.authorized_specs(),
            ToolSpec(
                name="kb_search",
                capability="kb_search",
                description="本地知识库检索",
                cost="local",
                freshness="stable",
                runner=never,
                min_window_seconds=20.0,
            ),
        )
    )


def test_tool_hidden_for_too_small_window_is_the_same_machine() -> None:
    """本轮工具窗装不下的工具，两条 loop 都不摆给模型，且记同一条 ``tool_menu`` 事件。

    2026-09-03 生产读数：kb_search 66% 的调用以 tool_timeout 收场、每次烧掉约 23s
    研究窗。可见性裁决在底座（``EpisodeToolBatchSession.menu``），领域只申报
    ``min_window_seconds``；两条 loop 必须同一格同一字，否则模型看到的菜单随 loop 而变。
    """

    frame = _frame()

    def narrow_window_context() -> ResearchRunContext:
        # 总窗 30s、reserve 15s → 本轮工具窗 15s < kb_search 的 20s。
        return replace(
            _context(frame, max_steps=3),
            contract=replace(
                _context(frame).contract, allowed_capabilities=("market_data", "kb_search")
            ),
            deadline=ResearchDeadline.from_timeout(30.0, synthesis_reserve=15.0),
            policy=ResearchPolicy("quick", 3, 30.0, 15.0),
        )

    script = [_tool_turn(), _finish_turn()]
    episode_model = _ScriptedModel(list(script))
    reference_model = _ScriptedModel(list(script))
    episode = ContinuousAgentEpisode(episode_model).run(
        task_frame=frame, context=narrow_window_context(), registry=_registry_with_slow_kb()
    )
    reference = HarnessReferenceLoop(reference_model).run(
        task_frame=frame, context=narrow_window_context(), registry=_registry_with_slow_kb()
    )

    for model in (episode_model, reference_model):
        names = [t["function"]["name"] for t in model.calls[0]["tools"]]
        assert names == ["market_data"], names
    assert episode_model.calls[0]["tools"] == reference_model.calls[0]["tools"]

    # Episode 的账本给每条事件盖 task_frame_hash / at（其它同机用例同样摘掉），
    # 菜单本身的四个裁决键两边必须一字不差；``would_grant`` 单独按容差比——它由
    # ``ResearchDeadline.remaining()`` 的墙钟推导，两条 loop 各建一个 deadline、到 ``menu()``
    # 之间各走了几毫秒，round(…, 3) 后 14.999 对 15.0 是时钟抖动不是机器差
    #（2026-09-03 在 gitea/main 干净树上 6/6 复现红）。
    menu_keys = ("visible", "hidden", "min_window_seconds", "reason")

    def menu_events(outcome):
        return [
            {key: _plain(e.payload[key]) for key in menu_keys}
            for e in outcome.events
            if e.kind == "tool_menu"
        ]

    def menu_grants(outcome):
        return [float(e.payload["would_grant"]) for e in outcome.events if e.kind == "tool_menu"]

    left, right = menu_events(episode), menu_events(reference)
    assert left and left == right
    left_grants, right_grants = menu_grants(episode), menu_grants(reference)
    assert len(left_grants) == len(right_grants) == len(left)
    for left_grant, right_grant in zip(left_grants, right_grants, strict=True):
        assert abs(left_grant - right_grant) < 0.05, (left_grants, right_grants)
    first = {**left[0], "would_grant": left_grants[0]}
    assert first["hidden"] == ["kb_search"]
    assert first["visible"] == ["market_data"]
    assert first["min_window_seconds"] == {"kb_search": 20.0}
    assert first["reason"] == "min_window_exceeds_grant"
    assert first["would_grant"] < 20.0
    assert _outcome_core(episode) == _outcome_core(reference)


def test_no_pruning_leaves_the_event_stream_untouched() -> None:
    """窄窗不成立时不记 tool_menu：无裁剪轮的事件流与改前逐字节相同。"""

    (_, episode), (_, reference) = _run_both([_tool_turn(), _finish_turn()])
    for outcome in (episode, reference):
        assert not [e for e in outcome.events if e.kind == "tool_menu"]


# ── 3. 有 PLAN：深度裁决也经 harness，全程消息归零差 ─────────────────────


def test_with_plan_every_message_the_model_sees_is_identical_modulo_budget() -> None:
    """P2 `govern_mode` 抽出之前，这里的 diff 恰好是一条 Episode 独有的 MODE_DECISION；
    抽出之后两条 loop 从同一个 `harness.govern_mode` 拿裁决与文案，diff 归零。"""

    (episode_model, episode), (reference_model, reference) = _run_both(
        [_plan_turn(), _tool_turn(), _finish_turn()]
    )

    assert len(episode_model.calls) == len(reference_model.calls) == 3
    for turn_index, (a, b) in enumerate(zip(episode_model.calls, reference_model.calls)):
        assert a["tools"] == b["tools"], f"turn {turn_index} tools differ"
        left = [_strip_runtime_budget(m) for m in a["messages"]]
        right = [_strip_runtime_budget(m) for m in b["messages"]]
        assert left == right, f"turn {turn_index} messages differ"

    # 两边都给模型看了同一条 MODE_DECISION（来自 harness，不再是 Episode 独有）。
    mode_messages = [
        json.loads(str(m["content"]))
        for m in reference_model.calls[-1]["messages"]
        if m.get("role") == "user" and str(m["content"]).startswith('{"kind": "MODE_DECISION"')
    ]
    assert len(mode_messages) == 1
    assert mode_messages[0]["effective_mode"] == "quick"

    assert _outcome_core(episode) == _outcome_core(reference)
    assert episode.plan is not None and episode.plan == reference.plan
    assert [e.kind for e in reference.events if e.kind == "mode_decision"] == [
        "mode_decision"
    ]


# ── 4. 有牙：参考 loop 的领域判断全在 harness ───────────────────────────


class _PermissiveHarness(FinanceResearchHarness):
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


def test_reference_loop_rejects_forged_hash_only_because_the_harness_says_so() -> None:
    frame = _frame()
    script = [_tool_turn(), _finish_turn(hashes=("forged-hash",))]

    strict = HarnessReferenceLoop(_ScriptedModel(list(script))).run(
        task_frame=frame, context=_context(frame), registry=_registry()
    )
    assert strict.stop_reason == "integrity_violation"
    assert strict.draft == ""
    invalid = [e for e in strict.events if e.kind == "invalid_action"]
    assert invalid and invalid[-1].payload["code"] == "forged_hash"

    permissive = HarnessReferenceLoop(
        _ScriptedModel(list(script)), harness=_PermissiveHarness()
    ).run(task_frame=frame, context=_context(frame), registry=_registry())
    assert permissive.stop_reason == "model_finish"
    assert permissive.status == "completed"


def test_reference_loop_closes_research_when_tool_slots_run_out() -> None:
    """底座策略：工具槛用尽 → 关研究阶段，注入的话来自 harness.begin_finalization。"""

    frame = _frame()
    model = _ScriptedModel([_tool_turn(), _finish_turn()])
    outcome = HarnessReferenceLoop(model).run(
        task_frame=frame, context=_context(frame, max_steps=1), registry=_registry()
    )
    assert outcome.stop_reason == "model_finish"
    assert model.calls[-1]["tools"] == []
    last_user = [
        str(m["content"]) for m in model.calls[-1]["messages"] if m.get("role") == "user"
    ][-1]
    assert last_user.startswith("研究阶段已关闭，不得再调用工具。")
    assert last_user.endswith("关闭原因：tool_budget_exhausted")
    assert [e.kind for e in outcome.events if e.kind == "finalization"] == ["finalization"]


# ── 5. 修复轮：两条 loop 在同一段历史上各修一轮，是同一台机器 ─────────────
#
# 状态机 spec §5 第 5 条：参考 loop 从「明确抛无修复轮」改成真的能跑一轮。
# 判据与研究阶段同形：修复轮里模型看到的每条消息一致（只差 runtime_budget 键）、
# repair_goal 事件一致、修复 outcome 一致。P2'-live 里 model_finish vs repair_model_stop
# 那条差，从此不再是「参考 loop 没有修复轮」造成的。


def _partial_finish_turn() -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "status": "partial",
                "draft": "当前偏修复，但反方证据仍缺。",
                "gaps": ["仍缺反方"],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": ["evidence-1"],
                        "gap": "仍缺反方",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


def _repair_goal(*, remaining_calls: int) -> RepairGoal:
    return RepairGoal(
        episode_id="reference-loop-test",
        repair_goal_id="repair-reference-loop-test-1",
        cycle=1,
        missing_answer_elements=("direct_assessment",),
        unsupported_claims=(),
        missing_evidence_modes=(),
        attempted_actions=("market_data:test:market",),
        evidence_progress=CoverageDelta(1, 0, 1),
        remaining_calls=remaining_calls,
        remaining_seconds=8.0,
    )


def _run_then_resume_both(script: list[ModelTurn], *, remaining_calls: int):
    frame = _frame()
    goal = _repair_goal(remaining_calls=remaining_calls)

    episode_model = _ScriptedModel(list(script))
    episode = ContinuousAgentEpisode(episode_model)
    episode_sink: list = []
    episode_first = episode.run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(),
        _continuation_sink=episode_sink,
    )
    episode_repaired = episode.resume(episode_sink[0], episode_first, goal)

    reference_model = _ScriptedModel(list(script))
    reference = HarnessReferenceLoop(reference_model)
    reference_sink: list = []
    reference_first = reference.run(
        task_frame=frame,
        context=_context(frame),
        registry=_registry(),
        _continuation_sink=reference_sink,
    )
    reference_repaired = reference.resume(reference_sink[0], reference_first, goal)

    assert episode_first.stop_reason == reference_first.stop_reason == "model_finish"
    assert episode_first.status == reference_first.status == "partial"
    return (episode_model, episode_repaired), (reference_model, reference_repaired)


def _plain(value):
    """Episode 的 ledger 把 payload 冻成 mappingproxy / tuple；比对前展平成 dict / list。"""

    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _repair_goal_event(outcome):
    """repair_goal 事件正文。Episode 每条事件都盖 task_frame_hash 与 at（底座的账），摘掉再比。"""

    return [
        {k: v for k, v in _plain(e.payload).items() if k not in {"task_frame_hash", "at"}}
        for e in outcome.events
        if e.kind == "repair_goal"
    ]


def test_no_tool_repair_round_is_the_same_machine() -> None:
    """零工具额度的修复轮：开场 REPAIR_GOAL（含不可达降级后的目标）字节相同，裁决相同。

    额度为 0 但研究窗还开着：两条 loop 都照 Episode 的口径给模型看工具定义（调用会被
    remaining_slots=0 拒掉），而不可达裁决把 direct_assessment 从模型侧目标里摘掉。
    """

    (episode_model, episode), (reference_model, reference) = _run_then_resume_both(
        [_tool_turn(), _partial_finish_turn(), _finish_turn()],
        remaining_calls=0,
    )

    assert len(episode_model.calls) == len(reference_model.calls) == 3
    repair_call_e, repair_call_r = episode_model.calls[2], reference_model.calls[2]
    assert repair_call_e["tools"] == repair_call_r["tools"]
    left = [_strip_runtime_budget(m) for m in repair_call_e["messages"]]
    right = [_strip_runtime_budget(m) for m in repair_call_r["messages"]]
    assert left == right
    opening = json.loads(str(left[-1]["content"]))
    assert opening["kind"] == "REPAIR_GOAL"
    # 零额度 + 不许重开 → direct_assessment 结构性补不上，两边都从模型侧目标里摘掉了。
    assert opening["missing_answer_elements"] == []
    assert _repair_goal_event(episode) == _repair_goal_event(reference)
    assert _repair_goal_event(reference)[0]["unreachable_without_tools"] == [
        "direct_assessment"
    ]

    assert _outcome_core(episode) == _outcome_core(reference)
    # 没动手，但把 partial 稿改成了 completed 稿：算修好了。
    assert reference.stop_reason == "repair_model_finish"
    assert reference.status == "completed"


def test_tool_open_repair_round_is_the_same_machine() -> None:
    """带一次工具额度的修复轮：开场 → 工具批 → 收口指令 → 终局，四段消息逐条相同。"""

    repair_tool_turn = ModelTurn(
        "",
        (ModelToolCall("call-2", "market_data", {"query": "反方证据：量能与外资"}),),
        "scripted",
        "",
    )
    (episode_model, episode), (reference_model, reference) = _run_then_resume_both(
        [_tool_turn(), _partial_finish_turn(), repair_tool_turn, _finish_turn()],
        remaining_calls=1,
    )

    assert len(episode_model.calls) == len(reference_model.calls) == 4
    for turn_index in (2, 3):
        a, b = episode_model.calls[turn_index], reference_model.calls[turn_index]
        assert a["tools"] == b["tools"], f"turn {turn_index} tools differ"
        left = [_strip_runtime_budget(m) for m in a["messages"]]
        right = [_strip_runtime_budget(m) for m in b["messages"]]
        assert left == right, f"turn {turn_index} messages differ"
    assert episode_model.calls[2]["tools"], "修复轮首次调用必须带工具定义"
    assert episode_model.calls[3]["tools"] == []
    closing = [
        str(m["content"])
        for m in reference_model.calls[3]["messages"]
        if m.get("role") == "user"
    ][-1]
    assert closing.startswith("修复动作已执行。不得再调用工具")

    assert _repair_goal_event(episode) == _repair_goal_event(reference)
    assert _outcome_core(episode) == _outcome_core(reference)
    assert reference.stop_reason == "repair_model_finish"
    # 修复轮真派了一次工具（不是被去重账本拒掉的那种）。
    assert reference.usage.tool_calls == 2
    assert reference.usage.invalid_actions == 0


def test_reference_loop_repair_failure_keeps_the_previous_answer() -> None:
    """修复不得倒退：修复轮交回来的东西不合格，上一轮的稿与绑定原样结转。"""

    frame = _frame()
    model = _ScriptedModel(
        [
            _tool_turn(),
            _partial_finish_turn(),
            ModelTurn("不是 JSON，只是一段话。", (), "scripted", ""),
        ]
    )
    loop = HarnessReferenceLoop(model)
    sink: list = []
    first = loop.run(
        task_frame=frame, context=_context(frame), registry=_registry(), _continuation_sink=sink
    )
    repaired = loop.resume(sink[0], first, _repair_goal(remaining_calls=0))

    assert repaired.stop_reason == "invalid_repair_finish"
    assert repaired.draft == first.draft
    assert repaired.bindings == first.bindings
    finish = [e for e in repaired.events if e.kind == "finish"][-1]
    assert finish.payload["rejection_code"] != "none"


# ── 6. 棘轮：参考 loop 一行领域逻辑都不 import ───────────────────────────

_DOMAIN_MODULES = (
    "intelligence.services.episode_protocol",
    "intelligence.services.forecast_residual_budget",
    "intelligence.services.tool_observation_noise",
    "intelligence.services.tool_result_budget",
    "intelligence.services.evidence_ledger",
    "intelligence.services.repair_coordinator",
    "intelligence.services.mode_governor",
    "intelligence.services.mandatory_satisfiability",
    "intelligence.services.empty_pool_fallback",
)


def test_reference_loop_imports_no_domain_gate_module() -> None:
    tree = ast.parse(_LOOP_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    plan_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            if node.module == "intelligence.services.research_plan":
                plan_names.update(alias.name for alias in node.names)
    leaked = imported & set(_DOMAIN_MODULES)
    assert not leaked, f"参考 loop 直接碰了领域模块：{sorted(leaked)}"
    # research_plan 只许拿类型与公开投影，不许拿解析函数。
    assert not plan_names & {"parse_plan_candidate", "validate_plan_revision"}
    assert "intelligence.services.research_harness" in imported

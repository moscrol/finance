"""修复轮刚写出的 FINAL_JSON 不得被截止路径丢掉。

夹具是液冷同题 ``run_20260820_032014_595378``（生产 rev ``be7c1e7e``）：
seq18 首轮合成 ``TimeoutError`` 空稿 → seq20 ``carried_draft_chars=0``；
seq23 修复轮写出 1586 字合法 FINAL_JSON（draft 814 字、四格 bindings 全绑
证据），seq25 仍然 ``carried_draft_chars=0``、``outcome.draft=""``，公开答卷
降级成「现有证据不足，暂不能可靠回答」。

``run()`` 侧的同形洞已由 R-20260817-01 修掉（``_carry_just_written_finish``）；
``resume()`` 侧七条停机路径当时仍一律结转 ``previous.draft``，本文件钉住的是
其中两条「模型刚返回、预算随即耗尽」的路径。

夹具必须连证据一起冻：``_carry_just_written_finish`` 先过
``validate_episode_finish``，seq23 的 bindings 用的是 ``E1…E32`` 序数，
缺证据集就会 ``forged_hash`` 被拒 → 照样结转空串，测试会绿在错的分支上。
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

import intelligence.runtime.agent_episode as agent_episode_module
import intelligence.services.research_contract as research_contract_module
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.episode_protocol import validate_episode_finish
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger,
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.task_frame import TaskFrame

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "eval" / "fixtures"
_SEQ23 = _FIXTURE_DIR / "repair-carry-seq23-20260820.txt"
_EVIDENCE = _FIXTURE_DIR / "repair-carry-seq23-20260820.evidence.json"
_CONTRACT = _FIXTURE_DIR / "repair-carry-seq23-20260820.contract.json"
_META = _FIXTURE_DIR / "repair-carry-seq23-seq25-20260820.meta.json"


def _frozen_finish_content() -> str:
    return _SEQ23.read_text(encoding="utf-8")


def _frozen_evidence() -> tuple[AgentEvidence, ...]:
    raw = json.loads(_EVIDENCE.read_text(encoding="utf-8"))
    return tuple(AgentEvidence(**item) for item in raw)


def _frozen_required_outputs() -> tuple[RequiredOutput, ...]:
    raw = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    return tuple(RequiredOutput(**item) for item in raw)


def _meta() -> dict[str, object]:
    return json.loads(_META.read_text(encoding="utf-8"))


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="液冷服务器题材：产业链怎么拆解，哪些公司核心受益",
        user_goal="形成条件化判断",
        question_type="theme_analysis",
        subject="液冷服务器",
        subject_kind="theme",
        market_scope="A股",
        timeframe=None,
        required_outputs=tuple(item.output_id for item in _frozen_required_outputs()),
        assumptions=("用户未明确市场范围，按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.98,
    )


def _context(frame: TaskFrame) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="repair-carry-test",
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=_frozen_required_outputs(),
        allowed_capabilities=("kb_search",),
        research_tier="standard",
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("standard", 1, 30.0, 0.0),
        trace_parent_id="repair-carry-test",
        today="2026-08-20",
        latest_data_date="2026-08-19",
    )


def _registry() -> ResearchToolRegistry:
    def runner(_query: str, _tool_context: AgentToolContext):
        return (
            list(_frozen_evidence()),
            "frozen liquid-cooling observation",
            ProviderTrace(
                provider="test:kb",
                capability="kb_search",
                status="success",
                source_trade_date="2026-08-19",
                result_count=len(_frozen_evidence()),
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="kb_search",
                capability="kb_search",
                description="本地知识库检索",
                cost="local",
                freshness="current",
                runner=runner,
            ),
        )
    )


def _empty_draft_finish() -> ModelTurn:
    """首轮交出空稿：生产里 seq18 是 TimeoutError，落到 outcome 上同样是 draft=""。"""

    return ModelTurn(
        json.dumps(
            {
                "status": "partial",
                "draft": "",
                "gaps": ["首轮合成未产出"],
                "bindings": [],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


class _RepairWritesThenClockDies:
    """修复轮写出合法 FINAL_JSON，同一次调用把账本残余烧穿。"""

    def __init__(self, now: list[float], *, repair_content: str) -> None:
        self._now = now
        self._repair_content = repair_content
        self.calls: list[float] = []

    def complete(self, *, messages, tools, timeout):
        del messages, tools
        self.calls.append(float(timeout))
        if len(self.calls) == 1:
            return ModelTurn(
                "",
                (ModelToolCall("call-1", "kb_search", {"query": "液冷服务器 产业链"}),),
                "scripted",
                "",
            )
        if len(self.calls) == 2:
            return _empty_draft_finish()
        self._now[0] += float(timeout) + 0.5
        return ModelTurn(self._repair_content, (), "scripted", "")


def _repair_goal(context: ResearchRunContext) -> RepairGoal:
    return RepairGoal(
        episode_id=context.contract.task_id,
        repair_goal_id="repair-carry-just-written",
        cycle=1,
        missing_answer_elements=("direct_assessment",),
        unsupported_claims=(),
        missing_evidence_modes=(),
        attempted_actions=(),
        evidence_progress=CoverageDelta(1, 0, 1),
        remaining_calls=0,
        remaining_seconds=8.0,
    )


def test_frozen_repair_finish_validates_against_its_own_evidence() -> None:
    """夹具自洽：seq23 的稿在它自己的 33 条证据下过生效校验器。

    这条先立住「结转的输入是合法的」。它红了，说明夹具漂了或校验口径变了，
    此时下一条测试的绿是假绿。
    """

    meta = _meta()
    evidence = _frozen_evidence()
    assert len(evidence) == meta["evidence_count"] == 33
    frame = _frame()
    context = _context(frame)

    finish = validate_episode_finish(
        _frozen_finish_content(),
        context=context,
        evidence=evidence,
    )

    assert len(finish.draft) == meta["seq23_draft_chars"] == 814
    assert {item.output_id for item in finish.bindings} == {
        item.output_id for item in _frozen_required_outputs()
    }
    # 四格全部绑上证据；binding.gap 已被搬到顶层，verifier 不会短路判 missing。
    assert all(item.evidence_hashes for item in finish.bindings)
    assert all(not item.gap for item in finish.bindings)


def test_repair_deadline_carries_the_just_written_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """液冷形状：上一轮空稿 + 修复轮写出合法稿 + 预算随即耗尽 → 必须交卷。

    修复前：``carried_draft_chars=0``、``outcome.draft=""``（生产 seq25）。
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

    def monotonic() -> float:
        return now[0]

    monkeypatch.setattr(agent_episode_module, "monotonic", monotonic)
    monkeypatch.setattr(research_contract_module.time, "monotonic", monotonic)

    content = _frozen_finish_content()
    model = _RepairWritesThenClockDies(now, repair_content=content)
    session = GLMAgentRuntime(client=model).start(
        frame,
        context=context,
        registry=_registry(),
    )
    # 前提：上一轮确实没有稿——否则这条测试测的是别的东西。
    assert session.outcome.draft == ""

    updated = session.resume(_repair_goal(context))

    assert updated.stop_reason == "repair_deadline_exhausted"
    assert len(updated.draft) == _meta()["seq23_draft_chars"] == 814
    assert updated.draft == json.loads(content)["draft"]
    assert {item.output_id for item in updated.bindings} == {
        item.output_id for item in _frozen_required_outputs()
    }
    finish = [event for event in updated.events if event.kind == "finish"][-1]
    assert finish.payload["carried_draft_chars"] == 814


def test_repair_deadline_keeps_previous_draft_when_turn_is_not_a_valid_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """反向闸：修复轮没写出合法稿时，上一轮的稿不许被顶掉。

    「优先刚写出的」不能退化成「无条件覆盖」——那会把已有答案换成空串。
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

    def monotonic() -> float:
        return now[0]

    monkeypatch.setattr(agent_episode_module, "monotonic", monotonic)
    monkeypatch.setattr(research_contract_module.time, "monotonic", monotonic)

    kept = json.loads(_frozen_finish_content())
    kept_draft = str(kept["draft"])
    first_finish = ModelTurn(json.dumps(kept, ensure_ascii=False), (), "scripted", "")

    class _RepairWritesGarbage(_RepairWritesThenClockDies):
        def complete(self, *, messages, tools, timeout):
            del messages, tools
            self.calls.append(float(timeout))
            if len(self.calls) == 1:
                return ModelTurn(
                    "",
                    (
                        ModelToolCall(
                            "call-1", "kb_search", {"query": "液冷服务器 产业链"}
                        ),
                    ),
                    "scripted",
                    "",
                )
            if len(self.calls) == 2:
                return first_finish
            self._now[0] += float(timeout) + 0.5
            return ModelTurn("不是 JSON，只是一段话。", (), "scripted", "")

    model = _RepairWritesGarbage(now, repair_content="")
    session = GLMAgentRuntime(client=model).start(
        frame,
        context=context,
        registry=_registry(),
    )
    assert session.outcome.draft == kept_draft

    updated = session.resume(_repair_goal(context))

    assert updated.stop_reason == "repair_deadline_exhausted"
    assert updated.draft == kept_draft
    finish = [event for event in updated.events if event.kind == "finish"][-1]
    assert finish.payload["carried_draft_chars"] == len(kept_draft)

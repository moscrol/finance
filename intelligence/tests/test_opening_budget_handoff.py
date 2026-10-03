"""R18: fake model/clock, real episode -> session -> registry -> tool leaf."""
from dataclasses import replace
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

import intelligence.runtime.agent_episode as episode_module
import intelligence.runtime.episode_tool_batch as batch_module
import intelligence.services.research_contract as contract_module
from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger, ResearchDeadline, ResearchPolicy, root_budget_for_policy,
)
from intelligence.tests.test_agent_episode import (
    ScriptedModel, _context, _finish_turn, _frame, _market_registry,
    _successful_runner, _tool_turn,
)


def _rig(monkeypatch, *, delays=(39.5, 0.0), ceiling=75.0, initial_wait=0.0,
         hard_cap=None, denied=False, tool="market_data", renamed=False, turns=None):
    clock = SimpleNamespace(now=1000.0)

    def now():
        return clock.now

    # Module-local references: do not replace stdlib/thread wait clocks globally.
    monkeypatch.setattr(contract_module, "time", SimpleNamespace(monotonic=now))
    monkeypatch.setattr(episode_module, "monotonic", now)
    monkeypatch.setattr(batch_module, "monotonic", now)
    frame = _frame()
    if renamed:
        frame = replace(frame, raw_question="Different synthetic observation request", subject="opaque entity")
    policy = ResearchPolicy("standard", 6, 90.0, 80.0 * 2.0 / 3.0)
    episode_id = f"opening-budget-test-{uuid4().hex}"
    base = _context(frame)
    root = root_budget_for_policy(policy, episode_id=episode_id) if hard_cap is None else InMemoryRootBudgetLedger(
        episode_id=episode_id, initial_calls=6, hard_calls_cap=8,
        initial_seconds=90.0 - policy.synthesis_reserve, hard_seconds_cap=hard_cap,
    )
    context = replace(
        base, policy=policy, contract=replace(base.contract, task_id=episode_id),
        trace_parent_id=episode_id,
        deadline=ResearchDeadline.from_timeout(80.0, synthesis_reserve=policy.synthesis_reserve),
        root_budget=root,
    )
    if denied:
        monkeypatch.setattr(root, "grant", lambda grant: False)
    entered, before_model = [], []

    class TimedModel(ScriptedModel):
        def complete(self, *, messages, tools, timeout):
            index = len(self.calls)
            before_model.append({"timeout": timeout, "funded_seconds": root.remaining_seconds})
            clock.now += delays[index] if index < len(delays) else 0.0
            return super().complete(messages=messages, tools=tools, timeout=timeout)

    def runner(query, tool_context):
        entered.append({
            "query": query, "remaining": tool_context.deadline.remaining(),
            "stage_grant": tool_context.deadline.stage_timeout(999.0),
            "expires_at": tool_context.deadline.expires_at,
            "funded": root.remaining_seconds,
        })
        return _successful_runner(query, tool_context)

    model = TimedModel(turns or [_tool_turn("first bounded observation", name=tool), _finish_turn()])
    if renamed:
        model._turns = iter([replace(_tool_turn("first bounded observation"), served_model="different-fixture"), _finish_turn()])
    cancelled = Event()
    clock.now += initial_wait
    drive = ContinuousAgentEpisode(model, llm_timeout=ceiling, is_cancelled=cancelled.is_set).manual_drive(
        task_frame=frame, context=context, registry=_market_registry(runner),
    )
    return SimpleNamespace(context=context, clock=clock, root=root, entered=entered,
                           before_model=before_model, drive=drive, model=model, cancelled=cancelled)


@pytest.mark.parametrize("delay", [0.0, 31.0, 39.5, 59.0])
def test_legal_opening_wait_reaches_real_leaf_without_raising_caps(monkeypatch, delay):
    rig = _rig(monkeypatch, delays=(delay, 0.0))
    outcome = rig.drive.run_to_end()
    assert len(rig.entered) == 1, {"before_model": rig.before_model, "remaining": rig.context.deadline.remaining()}
    assert outcome.usage.tool_calls == 1
    assert outcome.status == "completed"
    assert rig.context.deadline.expires_at == 1080.0
    assert rig.root.hard_seconds_cap == 90.0
    assert rig.root.hard_calls_cap == 8
    assert rig.root.allocated_calls == rig.root.initial_calls == 6
    assert rig.root.remaining_calls == 5
    if delay:
        assert rig.entered[0]["expires_at"] == 1060.0
        assert rig.entered[0]["stage_grant"] == pytest.approx(60.0 - delay)
        assert rig.entered[0]["funded"] >= rig.entered[0]["stage_grant"]
        handoff = next(event.payload for event in outcome.events if event.kind == "opening_budget_handoff")
        assert handoff["parent_expires_at"] == 1080.0
        assert handoff["parent_remaining_at_handoff"] == pytest.approx(80.0 - delay)
    else:
        assert rig.root.allocated_seconds == pytest.approx(90.0 - 80.0 * 2.0 / 3.0)
        assert not any(event.kind == "opening_budget_handoff" for event in outcome.events)


def test_short_provider_window_is_not_restarted_after_wait(monkeypatch):
    rig = _rig(monkeypatch, delays=(30.0, 0.0), ceiling=35.0)
    rig.drive.run_to_end()
    assert rig.before_model[0]["timeout"] == 35.0
    assert rig.entered[0]["expires_at"] == 1035.0
    assert rig.entered[0]["stage_grant"] == 5.0


def test_tool_loan_preserves_wall_floor_after_late_entry(monkeypatch):
    rig = _rig(monkeypatch, delays=(5.0, 0.0), initial_wait=40.0)
    rig.drive.run_to_end()
    assert rig.entered[0]["expires_at"] == 1060.0
    assert rig.entered[0]["stage_grant"] == 15.0


@pytest.mark.parametrize("delay", [60.0, 61.0, 85.0])
def test_closed_or_late_model_window_cannot_lend_to_tools(monkeypatch, delay):
    rig = _rig(monkeypatch, delays=(delay, 0.0))
    outcome = rig.drive.run_to_end()
    assert not rig.entered
    assert outcome.usage.tool_calls == 0
    assert rig.root.allocated_seconds == rig.root.initial_seconds


@pytest.mark.parametrize("setup", [{"denied": True}, {"hard_cap": 50.0}])
def test_unfunded_or_floor_eating_transfer_is_rejected(monkeypatch, setup):
    rig = _rig(monkeypatch, **setup)
    rig.drive.run_to_end()
    assert not rig.entered
    assert rig.root.allocated_seconds == rig.root.initial_seconds
    assert rig.root.allocated_calls == rig.root.initial_calls


def test_permission_is_not_supplied_by_a_time_loan(monkeypatch):
    rig = _rig(monkeypatch, tool="not_authorized")
    rig.drive.run_to_end()
    assert not rig.entered
    assert rig.root.remaining_calls == 6


@pytest.mark.parametrize("interrupt", ["cancel", "expire", "consume_calls"])
def test_no_effect_when_authority_changes_before_dispatch(monkeypatch, interrupt):
    rig = _rig(monkeypatch)
    assert rig.drive.run_until("before_tool_dispatch") is not None
    if interrupt == "cancel":
        rig.cancelled.set()
    elif interrupt == "expire":
        rig.clock.now = 1060.1
    else:
        while rig.root.remaining_calls:
            rig.root.consume_call_slot()
    rig.drive.run_to_end()
    assert not rig.entered


def test_dispatch_rechecks_funds_after_intervening_work(monkeypatch):
    rig = _rig(monkeypatch)
    assert rig.drive.run_until("before_tool_dispatch") is not None
    rig.root.consume_seconds(seconds=15.0)
    rig.drive.run_to_end()
    assert rig.entered[0]["stage_grant"] == 5.5
    assert rig.entered[0]["funded"] == 5.5


def test_followup_cannot_reborrow_the_opening_window(monkeypatch):
    rig = _rig(monkeypatch, delays=(30.0, 15.0, 0.0), turns=[
        _tool_turn("first"), _tool_turn("different second request", call_id="call-2"), _finish_turn(),
    ])
    outcome = rig.drive.run_to_end()
    assert len(rig.entered) == 1
    assert sum(event.kind == "opening_budget_handoff" for event in outcome.events) == 1


def test_question_and_model_labels_do_not_control_loan(monkeypatch):
    rig = _rig(monkeypatch, renamed=True)
    rig.drive.run_to_end()
    assert len(rig.entered) == 1
    assert rig.entered[0]["stage_grant"] == 20.5

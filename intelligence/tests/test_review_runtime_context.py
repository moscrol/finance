"""The writer and reviewer must see the same bounded runtime date context."""
from dataclasses import replace
from datetime import date
import json

import pytest

from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter
from intelligence.services import llm_refine
from intelligence.services.episode_protocol import build_episode_input
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier, _judge_system_prompt
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline, ResearchRunContext, policy_for_env
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_episode_semantic_verifier import _structural, _judge


def pair():
    frame, structural = _structural('截至最新交易日，成交额缩量。')
    context = ResearchRunContext(
        contract=structural.contract, deadline=ResearchDeadline.from_timeout(30),
        policy=policy_for_env(), trace_parent_id='private-parent', today='2026-10-01',
        latest_data_date='2026-09-30',
        information_cutoff=InformationCutoff(date(2026, 10, 1), 'runtime_default'),
        conversation_context='PRIVATE_HISTORY', perspective_context='PRIVATE_PERSPECTIVE',
    )
    return frame, structural, context


@pytest.fixture(autouse=True)
def no_provider(monkeypatch):
    monkeypatch.setenv('ASK_SEMANTIC_JUDGE', 'llm')
    monkeypatch.setattr(llm_refine, 'judge_provider_chain', lambda: ())


@pytest.mark.parametrize('latest', ['2026-09-30', '2024-01-02', None])
def test_date_context_matches_writer_and_is_bounded(latest):
    frame, structural, context = pair()
    context = replace(context, latest_data_date=latest)
    judge = _judge(True)
    verifier = SemanticEpisodeVerifier(judge_fn=judge)
    verifier.verify(frame=frame, structurally_verified=structural, deadline=context.deadline, context=context)
    payload = judge.calls[0]
    writer = json.loads(build_episode_input(frame, context, ResearchToolRegistry(())))
    wanted = {key: writer[key] for key in ('today', 'latest_data_date', 'information_cutoff', 'date_rule')}
    # The existing judge wire compactor omits nulls; absence must stay unknown.
    assert payload['runtime_context'] == {k:v for k,v in wanted.items() if v is not None}
    assert 'PRIVATE_' not in json.dumps(payload['runtime_context'])
    assert '不是行情' in payload['runtime_context']['date_rule']
    assert '运行时' in _judge_system_prompt(payload)
    assert '证据' in _judge_system_prompt(payload)


@pytest.mark.parametrize('field,value', [('task_id','other-task'), ('task_frame_hash','wrong'), ('question','other-question')])
def test_foreign_context_is_rejected_before_judging(field, value):
    frame, structural, context = pair()
    context = replace(context, contract=replace(context.contract, **{field:value}))
    judge = _judge(True)
    with pytest.raises(ValueError, match='runtime context'):
        SemanticEpisodeVerifier(judge_fn=judge).verify(
            frame=frame, structurally_verified=structural, deadline=context.deadline, context=context,
        )
    assert judge.calls == []


def test_missing_context_does_not_infer_or_reuse_previous_values():
    frame, structural, context = pair()
    judge = _judge(True)
    verifier = SemanticEpisodeVerifier(judge_fn=judge)
    verifier.verify(frame=frame, structurally_verified=structural, deadline=context.deadline, context=context)
    verifier.verify(frame=frame, structurally_verified=structural, deadline=context.deadline)
    assert 'runtime_context' in judge.calls[0]
    assert 'runtime_context' not in judge.calls[1]


def test_off_still_does_not_call_a_judge(monkeypatch):
    monkeypatch.setenv('ASK_SEMANTIC_JUDGE','off')
    frame, structural, context = pair()
    judge = _judge(True)
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=structural, deadline=context.deadline, context=context,
    )
    assert result.judge_mode == 'deterministic'
    assert judge.calls == []


def test_adapter_passes_context_to_real_verifier():
    frame, structural, context = pair()
    judge = _judge(True)
    adapter = ContinuousTurnAdapter(runtime=object(), semantic_verifier=SemanticEpisodeVerifier(judge_fn=judge))
    adapter._verify_semantics(frame=frame, structural=structural, deadline=context.deadline,
                              retrieve_fn=None, context=context)
    assert judge.calls[0]['runtime_context']['latest_data_date'] == context.latest_data_date


def test_review_requests_cannot_mutate_the_shared_snapshot():
    frame, structural, context = pair()
    judge = _judge(True)
    verifier = SemanticEpisodeVerifier(judge_fn=judge)
    verifier.verify(frame=frame, structurally_verified=structural, deadline=context.deadline, context=context)
    first = verifier._judge_request(frame, structural, [])
    first['runtime_context']['latest_data_date'] = '2099-01-01'
    first['runtime_context']['information_cutoff']['as_of_date'] = '2099-01-01'
    second = verifier._judge_request(frame, structural, [])
    assert second['runtime_context']['latest_data_date'] == '2026-09-30'
    assert second['runtime_context']['information_cutoff']['as_of_date'] == '2026-10-01'


def test_actual_adapter_entry_supplies_its_current_context(monkeypatch):
    from intelligence.tests.test_continuous_turn_adapter import _scripted_episode_result
    _, structural, _ = pair()
    seen = []
    original = ContinuousTurnAdapter._verify_semantics
    def observe(self, **kwargs):
        seen.append(kwargs.get('context'))
        return original(self, **kwargs)
    monkeypatch.setattr(ContinuousTurnAdapter, '_verify_semantics', observe)
    _scripted_episode_result(
        semantic_status='completed', public_answer='当前市场结构仍需验证。',
        evidence=structural.outcome.evidence, bindings=structural.outcome.bindings,
        latest_data_date='2026-09-30',
    )
    assert seen and all(isinstance(c, ResearchRunContext) for c in seen)
    assert all(c.latest_data_date == '2026-09-30' for c in seen)


def test_adapter_repair_recheck_supplies_the_same_task_context(monkeypatch):
    from intelligence.tests.test_continuous_turn_adapter import (
        test_sdk_semantic_repair_uses_root_reserve_after_research_deadline,
    )
    from intelligence.services.episode_protocol import runtime_date_context
    seen = []
    original = ContinuousTurnAdapter._verify_semantics
    def observe(self, **kwargs):
        seen.append(kwargs.get('context'))
        return original(self, **kwargs)
    monkeypatch.setattr(ContinuousTurnAdapter, '_verify_semantics', observe)
    # Existing fake SDK session exercises both actual adapter call sites; no HTTP.
    test_sdk_semantic_repair_uses_root_reserve_after_research_deadline(monkeypatch, False)
    assert len(seen) == 2
    assert all(isinstance(c, ResearchRunContext) for c in seen)
    assert seen[0].contract.task_id == seen[1].contract.task_id
    assert runtime_date_context(seen[0]) == runtime_date_context(seen[1])

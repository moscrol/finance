from __future__ import annotations

import pytest

from intelligence.services import llm_refine, llm_http_transport
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier, _call_flexible
from intelligence.tests.test_review_runtime_context import pair


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('ASK_SEMANTIC_JUDGE', 'llm')
    monkeypatch.setattr(llm_refine, 'judge_provider_chain', lambda: ())
    def forbidden(*args, **kwargs):
        raise AssertionError('offline callback tests forbid HTTP')
    monkeypatch.setattr(llm_http_transport, 'urlopen', forbidden)


def passed():
    return {'passed': True, 'rejected_sentence_indexes': [], 'issues': []}


@pytest.mark.parametrize('style', ['request', 'named', 'kwargs'])
def test_actual_verify_supplies_date_context_for_each_callback_style(style):
    frame, structural, context = pair()
    seen = []
    if style == 'request':
        def judge(request):
            seen.append(request.get('runtime_context'))
            return passed()
    elif style == 'named':
        def judge(question, *, runtime_context=None):
            assert question == frame.raw_question
            seen.append(runtime_context)
            return passed()
    else:
        def judge(**kwargs):
            seen.append(kwargs.get('runtime_context'))
            return passed()
    verifier = SemanticEpisodeVerifier(judge_fn=judge)
    verifier.verify(frame=frame, structurally_verified=structural, deadline=context.deadline, context=context)
    assert seen[0] is not None
    assert set(seen[0]) == {'today', 'latest_data_date', 'information_cutoff', 'date_rule'}
    assert seen[0]['latest_data_date'] == '2026-09-30'
    assert 'PRIVATE_' not in repr(seen[0])
    verifier.verify(frame=frame, structurally_verified=structural, deadline=context.deadline)
    assert seen[1] is None


def request():
    return {'question':'q', 'required_outputs':[], 'answer_grounding_mode':'evidence',
            'output_bindings':[], 'evidence_registry':[], 'sentences':[],
            'runtime_context':{'latest_data_date':'2026-09-30'}, 'PRIVATE_HISTORY':'secret'}


def test_kwargs_only_gets_projected_context_not_arbitrary_fields():
    seen = {}
    def judge(**kwargs):
        seen.update(kwargs)
        return passed()
    _call_flexible(judge, request(), 5)
    assert seen['runtime_context'] == {'latest_data_date':'2026-09-30'}
    assert 'PRIVATE_HISTORY' not in seen
    assert 'request' not in seen


def test_named_context_only_callback_respects_absent_optional_default():
    def judge(*, runtime_context=None):
        return runtime_context
    payload = request()
    assert _call_flexible(judge, payload, 5) == payload['runtime_context']
    payload.pop('runtime_context')
    assert _call_flexible(judge, payload, 5) is None


def test_required_context_is_not_fabricated_from_whole_request():
    seen = []
    def judge(runtime_context):
        seen.append(runtime_context)
        return passed()
    payload = request()
    payload.pop('runtime_context')
    with pytest.raises(TypeError, match='runtime_context'):
        _call_flexible(judge, payload, 5)
    assert seen == []


def test_positional_context_alias_gets_only_that_field():
    def judge(runtime_context, /):
        return runtime_context
    payload = request()
    assert _call_flexible(judge, payload, 5) is payload['runtime_context']


def test_legacy_callback_does_not_receive_new_keyword():
    seen = []
    def judge(question):
        seen.append(question)
        return passed()
    assert _call_flexible(judge, request(), 5) == passed()
    assert seen == ['q']


def test_callback_type_error_is_not_retried():
    error = TypeError('callback internal error')
    seen = []
    def judge(question, *, runtime_context):
        seen.append(runtime_context)
        raise error
    with pytest.raises(TypeError) as caught:
        _call_flexible(judge, request(), 5)
    assert caught.value is error
    assert len(seen) == 1

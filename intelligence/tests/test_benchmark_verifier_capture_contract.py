"""Observation wrappers must not widen or silently narrow verifier contracts."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from intelligence.runtime.continuous_turn_adapter import ContinuousTurnAdapter, _accepts_keyword
from intelligence.services import llm_refine, llm_http_transport
from intelligence.services.episode_semantic_verifier import SemanticEpisodeOutcome, SemanticEpisodeVerifier
from intelligence.tests.test_episode_semantic_verifier import _judge
from intelligence.tests.test_review_runtime_context import pair
from scripts.run_agent_runtime_benchmark import _SemanticVerifierCapture, _SemanticVerifierRun


def completed(structural):
    return SemanticEpisodeOutcome(
        verified=structural, status='completed', public_answer=structural.outcome.draft,
        judge_status='passed',
    )


class Legacy:
    provider_attempts = 2

    def __init__(self):
        self.calls = []

    def verify(self, *, frame, structurally_verified, deadline):
        self.calls.append((frame, structurally_verified, deadline))
        return completed(structurally_verified)


class ExplicitContext(Legacy):
    def verify(self, *, frame, structurally_verified, deadline, context=None):
        self.context = context
        return super().verify(frame=frame, structurally_verified=structurally_verified, deadline=deadline)


class Variadic(Legacy):
    def verify(self, *, frame, structurally_verified, deadline, **kwargs):
        self.extra = kwargs
        return super().verify(frame=frame, structurally_verified=structurally_verified, deadline=deadline)


@pytest.fixture(autouse=True)
def forbid_provider(monkeypatch):
    monkeypatch.setenv('ASK_SEMANTIC_JUDGE', 'llm')
    monkeypatch.setattr(llm_refine, 'judge_provider_chain', lambda: ())
    def forbidden(*args, **kwargs):
        raise AssertionError('contract tests must not perform HTTP')
    monkeypatch.setattr(llm_http_transport, 'urlopen', forbidden)


@pytest.mark.parametrize('delegate_type', [Legacy, ExplicitContext, Variadic])
def test_capture_exposes_delegate_signature(delegate_type):
    delegate = delegate_type()
    wrapped = _SemanticVerifierCapture(delegate)
    assert inspect.signature(wrapped.verify) == inspect.signature(delegate.verify)
    for name in ('context', 'retrieve_fn'):
        assert _accepts_keyword(wrapped.verify, name) == _accepts_keyword(delegate.verify, name)


@pytest.mark.parametrize('delegate_type', [Legacy, ExplicitContext, Variadic])
def test_adapter_retains_the_supported_contract_and_observation(delegate_type):
    frame, structural, context = pair()
    delegate = delegate_type()
    wrapped = _SemanticVerifierCapture(delegate)
    adapter = ContinuousTurnAdapter(runtime=object(), semantic_verifier=wrapped)
    result = adapter._verify_semantics(
        frame=frame, structural=structural, deadline=context.deadline,
        context=context, retrieve_fn=None,
    )
    assert len(delegate.calls) == 1
    assert delegate.calls[0] == (frame, structural, context.deadline)
    assert wrapped.latest is result
    assert wrapped.provider_attempts == 2
    delegate.provider_attempts = 5
    assert wrapped.provider_attempts == 5
    if delegate_type is ExplicitContext:
        assert delegate.context is context
    elif delegate_type is Variadic:
        assert delegate.extra == {'context': context}


def test_nested_capture_still_exposes_legacy_contract():
    frame, structural, context = pair()
    delegate = Legacy()
    inner = _SemanticVerifierCapture(delegate)
    outer = _SemanticVerifierCapture(inner)
    assert inspect.signature(outer.verify) == inspect.signature(delegate.verify)
    result = ContinuousTurnAdapter(runtime=object(), semantic_verifier=outer)._verify_semantics(
        frame=frame, structural=structural, deadline=context.deadline, context=context,
        retrieve_fn=None,
    )
    assert outer.latest is inner.latest is result
    assert len(delegate.calls) == 1


def test_real_benchmark_wrapper_chain_keeps_runtime_context():
    frame, structural, context = pair()
    judge = _judge(True)
    # Install a real verifier without constructing a model client/provider.
    run = object.__new__(_SemanticVerifierRun)
    run._client = SimpleNamespace(provider_attempts=0)
    run._verifier = SemanticEpisodeVerifier(judge_fn=judge)
    wrapped = _SemanticVerifierCapture(run)
    result = ContinuousTurnAdapter(runtime=object(), semantic_verifier=wrapped)._verify_semantics(
        frame=frame, structural=structural, deadline=context.deadline,
        context=context, retrieve_fn=None,
    )
    assert wrapped.latest is result
    assert judge.calls[0]['runtime_context']['latest_data_date'] == context.latest_data_date
    assert wrapped.provider_attempts == 0


def test_direct_unsupported_keyword_is_not_silently_dropped():
    delegate = Legacy()
    wrapped = _SemanticVerifierCapture(delegate)
    with pytest.raises(TypeError, match='context'):
        wrapped.verify(frame=None, structurally_verified=None, deadline=None, context=object())
    assert not delegate.calls
    assert wrapped.latest is None


def test_internal_type_error_propagates_once_without_retry():
    error = TypeError('delegate internal failure')
    class Broken:
        calls = 0
        def verify(self, **kwargs):
            self.calls += 1
            raise error
    delegate = Broken()
    wrapped = _SemanticVerifierCapture(delegate)
    with pytest.raises(TypeError) as raised:
        wrapped.verify(context=object())
    assert raised.value is error
    assert delegate.calls == 1
    assert wrapped.latest is None


def test_wrong_result_type_is_still_rejected():
    wrapped = _SemanticVerifierCapture(SimpleNamespace(verify=lambda **kwargs: object()))
    with pytest.raises(TypeError, match='return SemanticEpisodeOutcome'):
        wrapped.verify()
    assert wrapped.latest is None


def test_noncallable_delegate_is_still_rejected():
    wrapped = _SemanticVerifierCapture(SimpleNamespace(verify=None))
    with pytest.raises(TypeError, match='provide verify'):
        wrapped.verify()

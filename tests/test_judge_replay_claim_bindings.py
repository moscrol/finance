"""存证内嵌 claims 用生产解析器复原，绝不清空来源绑定来让重放变绿。"""
import copy
from dataclasses import replace

import pytest

from intelligence.runtime.continuous_turn_adapter import _private_outcome
from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.material_grounding import ClaimSourceBinding, MaterialAnchor
from intelligence.tests.test_episode_semantic_verifier import _structural
from scripts.judge_loss_point_replay import _rebuild_outcome


def _payload():
    _, verified = _structural('材料给出的收入是100。', detail='营业收入=100')
    claim = ClaimSourceBinding('材料给出的收入是100。', 'material_fact', (MaterialAnchor('m-test', '收入100'),))
    binding = OutputEvidenceBinding('direct_assessment', (), claims=(claim,))
    outcome = replace(verified.outcome, bindings=(binding,))
    return _private_outcome(outcome), binding


def test_private_serializer_claims_round_trip_losslessly():
    payload, original = _payload()
    before = copy.deepcopy(payload)
    rebuilt = _rebuild_outcome(payload)
    assert rebuilt.bindings == (original,)
    assert rebuilt.bindings[0].to_dict() == payload['bindings'][0]
    assert payload == before


def test_historical_assistant_binding_keeps_provenance():
    payload, _ = _payload()
    claim = ClaimSourceBinding('旧助手说收入100。', 'historical_assistant_statement',
                               old_answer_coordinate='message-test', historical_quote='收入100', basis='assistant_judgment')
    payload['bindings'][0]['claims'] = [claim.to_dict()]
    assert _rebuild_outcome(payload).bindings[0].claims == (claim,)


@pytest.mark.parametrize('change', ['bad_kind', 'empty_quote', 'string_claims', 'bad_coordinate'])
def test_bad_claim_source_is_still_rejected(change):
    payload, _ = _payload()
    claim = payload['bindings'][0]['claims'][0]
    if change == 'bad_kind':
        claim['kind'] = 'made_up'
    elif change == 'empty_quote':
        claim['material_anchors'][0]['quote'] = ''
    elif change == 'bad_coordinate':
        claim['old_answer_coordinate'] = 'not-a-material-source'
    else:
        payload['bindings'][0]['claims'] = 'invalid'
    with pytest.raises(ValueError):
        _rebuild_outcome(payload)


def test_legacy_binding_without_claims_stays_unchanged():
    _, verified = _structural('若成交占比回到14.93%则改善。', detail='成交占比=14.93')
    payload = _private_outcome(verified.outcome)
    for binding in payload['bindings']:
        binding.pop('claims', None)
    assert all(not b.claims for b in _rebuild_outcome(payload).bindings)

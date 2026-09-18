"""Only draft layout is recoverable; admission and identity remain separate."""
import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import ModelTurn
from intelligence.services.finish_candidate import _candidate_object
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.tests.test_finish_candidate_preservation import (
    Model, SECOND, envelope, setup_episode, turn,
)


def raw_layout(value):
    encoded = json.dumps(value, ensure_ascii=False)
    return encoded.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')


@pytest.mark.parametrize("fence", [False, True])
@pytest.mark.parametrize("layout", ["\n", "\r\n", "\t"])
def test_retain_layout_only_without_admitting_it(fence, layout):
    _, context, registry, evidence = setup_episode()
    value = envelope('前段分析。' + layout + SECOND)
    raw = '保留研究判断。\n' + raw_layout(value)
    if fence:
        raw = '```json\n' + raw + '\n```'
    admission = FinanceResearchHarness().admit_finish(raw, context=context, evidence=evidence, registry=registry)
    assert not admission.accepted and admission.rejection['rejection_code'] == 'not_json_object'
    assert admission.candidate is not None
    # Existing public sanitizer normalizes CRLF; parser below stays lossless.
    assert value['draft'].replace('\r\n', '\n') in admission.candidate.draft
    assert '保留研究判断。' in admission.candidate.draft
    assert _candidate_object(raw)[1] == value


@pytest.mark.parametrize('mutation', [
    'binding_layout', 'gap_layout', 'history_layout', 'nested_draft', 'null',
    'unclosed', 'bad_escape', 'duplicate_draft', 'duplicate_nested', 'unescaped_quote',
    'second_object', 'trailing', 'foreign', 'forged_binding', 'forged_history',
    'hidden_foreign', 'tool',
])
def test_layout_salvage_does_not_relax_other_boundaries(mutation):
    _, context, registry, evidence = setup_episode()
    value = envelope('前段\n' + SECOND)
    if mutation == 'binding_layout':
        value['bindings'][0]['gap'] = 'first\nsecond'
    elif mutation == 'gap_layout':
        value['gaps'] = ['first\nsecond']
    elif mutation == 'history_layout':
        value['history_research']['purpose'] += '\n'
    elif mutation == 'nested_draft':
        value['gaps'] = [{'draft': 'first\nsecond'}]
    elif mutation == 'null':
        value['draft'] += '\x00'
    elif mutation in {'foreign', 'hidden_foreign'}:
        value['task_frame_hash'] = 'foreign'
        if mutation == 'hidden_foreign':
            value['status'] = 'bad'
    elif mutation == 'forged_binding':
        value['bindings'][0]['evidence_hashes'] = ['unknown']
    elif mutation == 'forged_history':
        value['history_research']['result_refs'] = ['unknown']
    elif mutation == 'tool':
        value['tool_calls'] = []
    raw = raw_layout(value)
    if mutation == 'null':
        raw = raw.replace('\\u0000', '\x00')
    elif mutation == 'unclosed':
        raw = raw[:-1]
    elif mutation == 'bad_escape':
        raw = raw.replace('前段', '\\q')
    elif mutation == 'unescaped_quote':
        raw = raw.replace('前段', '前"段')
    elif mutation == 'duplicate_draft':
        raw = raw[:-1] + ',"dr\\u0061ft":"other"}'
    elif mutation == 'duplicate_nested':
        raw = raw.replace('"purpose":', '"purpose":"other","purpose":')
    elif mutation == 'second_object':
        raw += '\n' + raw
    elif mutation == 'trailing':
        raw += '\ntrailing prose'
    admission = FinanceResearchHarness().admit_finish('前缀。\n' + raw, context=context, evidence=evidence, registry=registry)
    assert not admission.accepted and admission.candidate is None


def test_escaped_draft_key_and_escaped_quotes_are_lossless():
    value = envelope('前段"引号"和反斜杠\\n保持原样。\n' + SECOND)
    raw = json.dumps(value, ensure_ascii=False).replace('"draft":', '"dr\\u0061ft":').replace('。\\n', '。\n')
    assert _candidate_object(raw)[1] == value


def test_actual_loop_retains_layout_candidate_after_provider_failure():
    frame, context, _, evidence = setup_episode()
    raw = '同任务说明。\n' + raw_layout(envelope('前段\n' + SECOND))
    registry = ResearchToolRegistry((), opening_prefetch=evidence)
    model = Model([turn(raw), ModelTurn('', (), 'scripted', 'unavailable'), RuntimeError('unavailable')])
    outcome = ContinuousAgentEpisode(model).run(task_frame=frame, context=context, registry=registry)
    assert SECOND in outcome.draft and outcome.status == 'partial'
    assert outcome.usage.tool_calls == 0
    finish = next(e.payload for e in reversed(outcome.events) if e.kind == 'finish')
    assert finish['retained_candidate_count'] >= 1

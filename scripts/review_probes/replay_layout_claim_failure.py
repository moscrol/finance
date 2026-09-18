#!/usr/bin/env python3
"""Read-only replay of the sealed GLM layout and evidence-claim failures.

No model/SQL/tool execution; no legacy verdict rewriting. Imports the selected
consumer from --code-root, so the same immutable source can test old and repaired
revisions. Correct --expect is exit0, wrong expectation fails. Output is exclusive.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys

DEFAULT_CODE = Path(__file__).resolve().parents[2]


def digest(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def replay(path: Path, *, code: Path, expect: str) -> dict[str, object]:
    sys.path.insert(0, str(code))
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_research import AgentEvidence, StructuredObservation
    from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent, ModelTurn
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    from intelligence.services.episode_verifier import verify_episode_outcome
    from intelligence.services.historical_research.intent import HistoryIntent
    from intelligence.services.research_contract import ResearchDeadline, ResearchPolicy, ResearchRunContext, ResearchTaskContract
    from intelligence.services.research_harness import FinanceResearchHarness
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.services.task_frame import TaskFrame

    source = digest(path)
    artifact = json.loads(path.read_text())
    assert source['sha256'] == '02f536171512cb2c7fb0bf30e86f1243ba22f50c5ac1e566d3035b153e5dbd68', 'not the sealed source'
    assert artifact['contract']['task_id'] == 'run_20260919_002806_645542:msg_04f66e8b950242888b8703babe3317b6'
    frame = TaskFrame.from_dict(artifact['task_frame'])
    assert frame is not None
    contract = ResearchTaskContract.from_dict(artifact['contract'])
    assert frame.task_frame_hash == contract.task_frame_hash
    meta = artifact['research_context']
    context = ResearchRunContext(
        contract=contract, deadline=ResearchDeadline.from_timeout(60),
        policy=ResearchPolicy('max', 1, 60, 0), trace_parent_id=contract.task_id,
        today=meta['today'], latest_data_date=meta['latest_data_date'],
        history_intent=HistoryIntent.from_dict(meta['history_intent']),
        history_results=deepcopy(meta['history_results']),
    )
    evidence = []
    for row in artifact['outcome']['evidence']:
        value = dict(row)
        for key in ('supports', 'contradicts', 'derived_from'):
            value[key] = tuple(value.get(key, ()))
        value['observations'] = tuple(StructuredObservation(**v) for v in value.get('observations', ()))
        evidence.append(AgentEvidence(**value))
    evidence = tuple(evidence)
    turns = [e['payload'] for e in artifact['events'] if e['kind'] == 'model_turn']
    raw = next(e['content'] for e in turns if e.get('turn_id') == 'turn-13')
    accepted_raw = next(e['content'] for e in turns if e.get('turn_id') == 'turn-14')
    expected = json.loads(accepted_raw)['draft'].replace('当日', '今日', 1).replace('按判读规则', '按FY-A01')
    assert hashlib.sha256(expected.encode()).hexdigest() == 'e30c6d0e59453120f450a8c174233041135484b721df78c8d7721d1c3945cdab'
    # Exact old-source shape; this is not a permissive production decoder.
    assert len(expected) == 2096 and len(evidence) == 122
    registry = ResearchToolRegistry((), opening_prefetch=evidence)
    harness = FinanceResearchHarness()
    admission = harness.admit_finish(raw, context=context, evidence=evidence, registry=registry)
    assert not admission.accepted and admission.rejection['rejection_code'] == 'not_json_object'
    retained = admission.candidate is not None
    if retained:
        assert expected in admission.candidate.draft
    else:
        assert expect == 'missing', 'safe layout draft was not retained'
    calls = []

    class Model:
        def complete(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return ModelTurn(raw, (), 'offline-script', '')
            raise RuntimeError('offline: recovery deliberately unavailable')

    outcome = ContinuousAgentEpisode(Model()).run(task_frame=frame, context=context, registry=registry)
    assert outcome.usage.tool_calls == 0, outcome.usage
    assert len(calls) <= 3, {'calls': len(calls), 'stop': outcome.stop_reason, 'events': [e.kind for e in outcome.events]}
    finish = next(e.payload for e in reversed(outcome.events) if e.kind == 'finish')
    if expect == 'repaired':
        assert retained and expected in outcome.draft and finish['retained_candidate_count'] >= 1
    else:
        assert not retained and finish['retained_candidate_count'] == 0
    accepted = harness.admit_finish(accepted_raw, context=context, evidence=evidence, registry=registry)
    assert accepted.accepted
    final = AgentOutcome(
        task_frame_hash=frame.task_frame_hash, status=accepted.status, draft=accepted.draft,
        evidence=evidence, bindings=accepted.bindings, gaps=accepted.gaps,
        traces=(), events=(EpisodeEvent(1, 'task', {'task_frame_hash': frame.task_frame_hash}),),
        usage=AgentUsage(), stop_reason='model_finish',
    )
    reviewed = SemanticEpisodeVerifier(judge_fn=lambda _: {
        'passed': True, 'issues': [], 'rejected_sentence_indexes': [],
    }).verify(frame=frame, structurally_verified=verify_episode_outcome(contract, final), deadline=ResearchDeadline.from_timeout(30))
    findings = reviewed.to_dict().get('evidence_claim_findings', [])
    codes = {f['code'] for f in findings}
    required = {'historical_window_minimum', 'endpoint_not_path', 'historical_contraction',
                'entity_metric_mismatch', 'source_caliber_conflict', 'uncalibrated_watch_threshold', 'uncalibrated_win_rate'}
    if expect == 'repaired':
        assert required <= codes, sorted(required - codes)
        assert reviewed.judge_status == 'rejected' and reviewed.status == 'partial'
        assert reviewed.rejected_claim_indexes
    else:
        assert not codes
    assert final.draft in reviewed.public_answer, 'quality findings must not erase the source draft'
    assert reviewed.verified.outcome.evidence == evidence
    assert source == digest(path), 'source changed'
    def git(*args):
        return subprocess.check_output(['git', '-C', str(code), *args], text=True).strip()
    return {
        'schema': 'layout-claim-replay/v1', 'source': source, 'source_task': contract.task_id,
        'revision': git('rev-parse', 'HEAD'), 'dirty_paths': git('status', '--porcelain').splitlines(),
        'expected': expect, 'checks': 'passed', 'finish_still_rejected': True,
        'candidate_retained': retained, 'retained_candidate_count': finish['retained_candidate_count'],
        'original_draft_preserved_after_provider_failure': expected in outcome.draft,
        'evidence_count': len(evidence), 'semantic_findings': findings,
        'review_status': reviewed.status, 'judge_status': reviewed.judge_status,
        'real_model_calls': 0, 'scripted_turns': len(calls), 'tool_calls': 0,
        'new_live_submissions': 0, 'old_live_verdict': 'not_passed', 'financial_certification': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode', type=Path)
    parser.add_argument('--code-root', type=Path, default=DEFAULT_CODE)
    parser.add_argument('--expect', choices=('missing', 'repaired'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists')
    def no_network(*_args, **_kwargs):
        raise AssertionError('offline replay forbids network')
    socket.socket.connect = no_network
    socket.create_connection = no_network
    result = replay(args.episode, code=args.code_root, expect=args.expect)
    with args.output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

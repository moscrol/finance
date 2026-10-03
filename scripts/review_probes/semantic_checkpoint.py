"""Restore a frozen episode for read-only semantic-verifier checkpoint probes.

Not an Episode/product rerun and not permission to rewrite the source archive.
Refuse incomplete reconstruction; compare the real structural verifier with the
archived result before using its output. Variants alter only a caller-supplied
candidate draft and remain explicitly synthetic, never old model observations.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path

from intelligence.services.agent_runtime import (
    AgentOutcome, AgentUsage, EpisodeEvent, OutputEvidenceBinding,
)
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchDeadline, ResearchTaskContract
from intelligence.services.task_frame import TaskFrame
from scripts.review_probes.replay_financial_r6 import decode_evidence


def restore_checkpoint(path: Path):
    archive = json.loads(path.read_text())
    raw = archive['outcome']
    # No ad-hoc plan/claim deserializer. These probes are evidence-bound drafts;
    # a different archive shape needs an explicit, tested loader first.
    if raw.get('plan') is not None or any(row.get('claims') for row in raw['bindings']):
        raise ValueError('unsupported frozen plan/claim shape')
    events = tuple(EpisodeEvent(**row) for row in raw['events'])
    frame = TaskFrame.from_dict(archive['task_frame'])
    if frame is None:
        raise ValueError('missing frozen task frame')
    contract_data = dict(archive['contract'])
    task_id = next((e.payload.get('task_id') for e in events if e.kind == 'configure'), None)
    if not contract_data.get('task_id'):
        if not isinstance(task_id, str) or not task_id:
            raise ValueError('missing original task identity')
        # The artifact's public contract omits task_id; recover from its own
        # configure event, not an invented experiment identity.
        contract_data['task_id'] = task_id
    contract = ResearchTaskContract.from_dict(contract_data)
    if not (frame.task_frame_hash == raw['task_frame_hash'] == contract.task_frame_hash):
        raise ValueError('frame/contract/outcome hash mismatch')
    traces = []
    for row in raw['traces']:
        values = dict(row)
        window = values.get('requested_time_range')
        if isinstance(window, dict):
            values['requested_time_range'] = (window['start'], window['end'])
        traces.append(ProviderTrace(**values))
    evidence = decode_evidence(raw['evidence'])
    for item, saved in zip(evidence, raw['evidence'], strict=True):
        restored = json.loads(json.dumps(asdict(item)))
        if any(key not in restored or restored[key] != value for key, value in saved.items()):
            raise ValueError('evidence control/provenance roundtrip differs')
    outcome = AgentOutcome(
        task_frame_hash=raw['task_frame_hash'], status=raw['status'], draft=raw['draft'],
        evidence=evidence, traces=tuple(traces),
        gaps=tuple(raw['gaps']), stop_reason=raw['stop_reason'], events=events,
        bindings=tuple(OutputEvidenceBinding(**row) for row in raw['bindings']),
        usage=AgentUsage(**raw['usage']), persistence=raw.get('persistence', 'unknown'),
    )
    roundtrip = outcome.to_dict()
    # The artifact writer persists private evidence metadata which the public
    # outcome serializer intentionally omits. Compare those fields above on
    # the actual evidence objects; compare all remaining wire fields exactly.
    roundtrip['evidence'] = raw['evidence']
    if roundtrip != raw:
        raise ValueError('outcome roundtrip changed frozen content')
    structural = verify_episode_outcome(contract, outcome)
    expected = archive['structural_verifier']
    actual = structural.to_dict()
    for field in ('verified_status', 'issues', 'completion'):
        if actual[field] != expected[field]:
            raise ValueError('structural replay differs: ' + field)
    return frame, structural


def verify_checkpoint(path: Path, *, draft: str | None = None, timeout: float = 120):
    frame, original = restore_checkpoint(path)
    structural = original
    if draft is not None:
        structural = verify_episode_outcome(original.contract, replace(original.outcome, draft=draft))
    return SemanticEpisodeVerifier().verify(
        frame=frame, structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(timeout),
    )

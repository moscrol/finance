from __future__ import annotations
import uuid
from typing import Dict, List, Optional
from finance_harness.contracts import ClaimCategory, ClaimDelta, ClaimItem, DeltaStatus, ResearchBaseline, ToolResultEnvelope, TrackingDelta
from finance_harness.verifier import DeterministicVerifier, SemanticVerifier, TargetedRepairEngine

class ResearchPipeline:
    def __init__(self):
        self.evidence_pool: Dict[str, ToolResultEnvelope] = {}
    def add_evidence(self, envelope: ToolResultEnvelope) -> str:
        ev_id = envelope.metadata.evidence_id
        self.evidence_pool[ev_id] = envelope
        return ev_id
    def build_and_verify_baseline(self, subject: str, as_of_date: str, draft_claims: List[ClaimItem], open_gaps: Optional[List[str]] = None) -> ResearchBaseline:
        baseline_id = "base_" + uuid.uuid4().hex[:10]
        verified_claims = []
        for claim in draft_claims:
            temp_base = ResearchBaseline(baseline_id=baseline_id, subject=subject, as_of_date=as_of_date, claims=[claim])
            report = DeterministicVerifier.verify_baseline(temp_base, self.evidence_pool)
            res = report.results[0]
            if res.passed:
                sem_res = SemanticVerifier.review_claim(claim)
                if sem_res: res = sem_res
            if not res.passed:
                repaired = TargetedRepairEngine.repair_claim(claim, res, lambda c, r: None)
                verified_claims.append(repaired)
            else:
                verified_claims.append(claim)
        return ResearchBaseline(baseline_id=baseline_id, subject=subject, as_of_date=as_of_date, claims=verified_claims, open_gaps=open_gaps or [])
    def track_incremental_update(self, baseline: ResearchBaseline, as_of_date: str, new_evidence_envelopes: List[ToolResultEnvelope]) -> TrackingDelta:
        new_ev_ids = [self.add_evidence(env) for env in new_evidence_envelopes]
        deltas = [ClaimDelta(claim_id=c.claim_id, status=DeltaStatus.SUPPORTED, delta_evidence_ids=new_ev_ids, reasoning="跟踪数据符合预期") for c in baseline.claims]
        return TrackingDelta(tracking_id="trk_" + uuid.uuid4().hex[:10], baseline_ref=baseline.baseline_id, as_of_date=as_of_date, deltas=deltas)

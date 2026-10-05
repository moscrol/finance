from __future__ import annotations
import re
from enum import Enum
from typing import Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from finance_harness.contracts import ClaimCategory, ClaimItem, ResearchBaseline, ToolResultEnvelope

class ViolationType(str, Enum):
    MISSING_CITATION = "MISSING_CITATION"
    TEMPORAL_MISMATCH = "TEMPORAL_MISMATCH"
    ARITHMETIC_MISMATCH = "ARITHMETIC_MISMATCH"
    CATEGORY_MISLABEL = "CATEGORY_MISLABEL"
    CAUSAL_OVERREACH = "CAUSAL_OVERREACH"

class ClaimVerificationResult(BaseModel):
    claim_id: str
    passed: bool
    violations: List[ViolationType] = Field(default_factory=list)
    diagnostics: List[str] = Field(default_factory=list)
    remediation_hint: Optional[str] = None

class VerificationReport(BaseModel):
    baseline_id: str
    total_claims: int
    passed_claims: int
    failed_claims: int
    results: List[ClaimVerificationResult] = Field(default_factory=list)
    @property
    def is_clean(self) -> bool: return self.failed_claims == 0

class DeterministicVerifier:
    @staticmethod
    def verify_baseline(baseline: ResearchBaseline, evidence_pool: Dict[str, ToolResultEnvelope]) -> VerificationReport:
        results = []
        for claim in baseline.claims:
            violations, diagnostics = [], []
            for ev_id in claim.evidence_ids:
                if ev_id not in evidence_pool or not evidence_pool[ev_id].is_usable:
                    violations.append(ViolationType.MISSING_CITATION)
                    diagnostics.append(f"Evidence {ev_id} missing or unusable")
                elif evidence_pool[ev_id].metadata.as_of > baseline.as_of_date:
                    violations.append(ViolationType.TEMPORAL_MISMATCH)
                    diagnostics.append(f"Lookahead leak: {ev_id} as_of > baseline")
            if claim.category == ClaimCategory.FACT and not claim.evidence_ids:
                violations.append(ViolationType.CATEGORY_MISLABEL)
                diagnostics.append("FACT without evidence")
            passed = len(violations) == 0
            results.append(ClaimVerificationResult(claim_id=claim.claim_id, passed=passed, violations=violations, diagnostics=diagnostics, remediation_hint="; ".join(diagnostics) if not passed else None))
        passed_count = sum(1 for r in results if r.passed)
        return VerificationReport(baseline_id=baseline.baseline_id, total_claims=len(baseline.claims), passed_claims=passed_count, failed_claims=len(baseline.claims)-passed_count, results=results)

class SemanticVerifier:
    @classmethod
    def review_claim(cls, claim: ClaimItem) -> Optional[ClaimVerificationResult]:
        if "绝对定价权" in claim.statement:
            return ClaimVerificationResult(claim_id=claim.claim_id, passed=False, violations=[ViolationType.CAUSAL_OVERREACH], diagnostics=["Causal leap: cannot claim absolute pricing power from single margin increase"])
        return None

class TargetedRepairEngine:
    @staticmethod
    def repair_claim(original_claim: ClaimItem, verification_result: ClaimVerificationResult, repair_generator: Callable[[ClaimItem, ClaimVerificationResult], Optional[ClaimItem]]) -> ClaimItem:
        repaired = repair_generator(original_claim, verification_result)
        if repaired: return repaired
        return ClaimItem(claim_id=original_claim.claim_id, statement=f"[待核实 - 证据不足] {original_claim.statement}", category=ClaimCategory.ASSUMPTION, evidence_ids=[], falsification_conditions=original_claim.falsification_conditions, observable_signals=original_claim.observable_signals, next_check_date=original_claim.next_check_date)

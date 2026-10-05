import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from finance_harness import *

def test_harness_contracts_and_isolation():
    store = MemoryStore()
    cand = store.register_candidate("新观点", ClaimCategory.ASSUMPTION)
    assert cand.lifecycle_state == MemoryLifecycleState.CANDIDATE
    assert len(store.query_active_context()) == 0
    store.confirm_candidate(cand.memory_id)
    assert len(store.query_active_context()) == 1

def test_pipeline_and_verifier():
    pipeline = ResearchPipeline()
    calc = compute_derived_metric("gross_margin", 915.0, 1000.0, as_of="2026-06-30")
    ev1 = pipeline.add_evidence(calc)
    claim = ClaimItem(claim_id="c1", statement="茅台毛利率稳定", category=ClaimCategory.FACT, evidence_ids=[ev1])
    baseline = pipeline.build_and_verify_baseline("600519.SH", "2026-06-30", [claim])
    assert len(baseline.claims) == 1
    assert baseline.claims[0].claim_id == "c1"

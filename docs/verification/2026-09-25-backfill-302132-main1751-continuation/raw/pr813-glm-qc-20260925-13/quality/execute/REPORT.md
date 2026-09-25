```json
{
  "claims": [
    {
      "id": "C1",
      "status": "verified",
      "evidence": "Reviewer-executed parent CLI on frozen real-date subset: apply exit 0, verify exit 0 (independent-real-date-observation.json); 37-check acceptance oracle exit 0 with expected revision f650d9e… and source sha256 4c2d1b7e…ca26. Exact 53-INSERT/1-UPDATE split not independently enumerated by reviewer (limit)."
    },
    {
      "id": "C2",
      "status": "verified",
      "evidence": "test_corrupt_authorized_source_refuses_without_publish[missing|null|adjusted] all passed; wrong.parquet CLI refusal observed exit 2 without publish; window boundary enforced by acceptance oracle."
    },
    {
      "id": "C3",
      "status": "verified",
      "evidence": "Seeded mutation oracle: 6 cases in test_seeded_c3 (amount/timestamp/delete/insert/duplicate/other_stock) and 3 in test_earlier_fixture_adapter (earlier_than_window/null_column) all fail correctly; baseline passes. My run: rows=64, technical=39, window=161, acceptance_checks=37."
    },
    {
      "id": "C4",
      "status": "verified",
      "evidence": "In-scope only: CLI parent apply/verify/refuse exits coherent; unsafe-input preflight (existing/under_source/symlink/wal/bad_hash) and low-space refusal before copies all passed; receipt-coherence probes passed. No full security audit performed (per claim scope)."
    },
    {
      "id": "C5",
      "status": "verified",
      "evidence": "My isolated subset rehearsal: apply exit 0, verify exit 0, 37 acceptance checks pass, amount=1e15 negative control exit 2, backup_rollback_match=true; unsafe identity/WAL/symlink/hash rejections pass. Limits: full-copy rehearsal is host-supplied audit-only (inputs/host-rehearsal), not reviewer execution; production read-only/unchanged not independently observed by reviewer."
    },
    {
      "id": "C6",
      "status": "verified",
      "evidence": "Three host-authored regression witnesses passed (fdopen receipt-write-failure cleanup, open permission preflight block, EEXIST race): test_context_regression_witness_rejects_degraded_scope 3/3. Six author test-body invocations (candidate + external scope-mutant × 3) disclosed as running inside witnesses only; no standalone author pytest invocation."
    },
    {
      "id": "C7",
      "status": "verified",
      "evidence": "Observation JSON and passing test_host_full_copy_receipts_are_current_but_not_reviewer_execution bind evidence to revision f650d9e765e127c7e66a621226cc2d676d70075d integrated with main 79861f07e48573b6b5bd378b28880e484f509905. Verdict is code-binding only; engineering gate still running, merge/production approvals remain false."
    }
  ],
  "counts": {
    "executed": 24,
    "errors": 0,
    "failed": 0,
    "passed": 24,
    "skipped": 0
  },
  "evidence": {
    "junit": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probe-results-all.xml",
    "observation": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/independent-real-date-observation.json",
    "positive_control": "exit 1, AssertionError: intentional probe_bug control (as required)",
    "report": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/EXECUTE.md"
  },
  "limits": [
    "Frozen real-data subset only (302132.SZ verbatim + sentinel 000001.SZ + calendar), not full production copy",
    "53-INSERT/1-UPDATE split and production-unchanged property rest on acceptance oracle and host receipts, not independent row enumeration",
    "Host full-copy rehearsal is external audit-only evidence, not reviewer execution",
    "Engineering readiness gate running separately; C7 verdict covers code binding only"
  ],
  "verdict": "PASS_WITH_LIMITS",
  "complete": true,
  "stage": "execute",
  "axis": "quality",
  "revision": "f650d9e765e127c7e66a621226cc2d676d70075d",
  "baseline": "79861f07e48573b6b5bd378b28880e484f509905"
}
```

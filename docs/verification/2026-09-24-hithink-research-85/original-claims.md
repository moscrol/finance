# PR #894 / Workorder #85: Claims To Verify, Not Conclusions

Revision 09b437c2f64a097f2535afbeb3a7b615e0c5730a; baseline c9dd71dfd678855b61662100ec74625b92ad1f1b.
No author test results or author review reports are supplied. Treat every claim as unverified.

C1. HTTP 429 (including non-JSON bodies) and business code 429 use exponential backoff, honor usable Retry-After seconds/date, and have independent monotonic time and constant retry-count bounds. Nonpositive/invalid Retry-After cannot cause unbounded immediate retry. Budget is retry admission, not forcible interruption of in-flight reads.
C2. Existing business code 4001 keeps baseline retry count/backoff semantics. Ordinary API/network/parse errors are not reclassified as rate-limit gaps; secrets/upstream body are absent from stored/reported errors.
C3. Anomaly, valuation, and each stock heat-trend request: a typed 429 exhaustion leaves failed request audit with original scope and traceable ID, continues remaining requests, and produces overall partial plus missing kind/request_id. Empty/NULL valid data remain distinct from failed requests. Other errors still fail closed.
C4. CLI partial exit code propagates to stepwise nightly status and monolithic failure. Remaining research requests are attempted first, but unresolved partial does not become publication success. This does not weaken unrelated step status handling or staging inheritance.
C5. The carried-forward observations preserve Shanghai collection-day restrictions for latest-only endpoints, exclude those endpoints on historical recovery, use existing canonical production-write guard (including hard-link/unknown-identity checks), and expose only local read access through finance_query with schemas/consumption registration.
C6. This candidate makes no live supplier calls as part of offline validation, no new agent outbound tool, no deployment or production-root changes. Tests may use temporary DuckDB copies and synthetic responses only. No promise that the default retry budget covers a real seven-to-nine-minute throttle window.

Scope: source.diff contains the runtime/test delta. Core files: market_feature_store/hithink_client.py; sync/sync_hithink_research.py; cli.py; sync/sync_daily_full.py; write_path.py; schema.sql; consumption_registry.yaml; skills/daily-full-review/scripts/run_review_sync.py; scripts/recover_local_review.py; scripts/audit_hithink_runtime.py; intelligence/services/finance_query.py; associated tests.

Classify each claim verified / not_verified / out_of_scope. Missing evidence is not PASS. No live financial tasks, no network, no source changes, no Git operations from the reviewer. Never run full repository tests; targeted author tests and reviewer-created probes must be counted separately.

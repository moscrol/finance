# Finance Workbench Self-Use Release Pivot Handoff

Date: 2026-07-29  
Branch: `feat/agent-runtime-backends-verify`  
Candidate revision: `c35740e62439e3225f81d2b02d6f9a7dafa65fe8`

## Final Goal

The final goal is a product maturity gate, not another benchmark milestone:

1. the daily data path runs without developer rescue;
2. a clean candidate passes release readiness and the five real product
   workflows;
3. canonical 8792 changes only after explicit user approval and has an atomic
   rollback point;
4. real self-use events cover at least 10 trading days and all five workflows:
   market, theme, stock, news, and watchlist;
5. the measured success/usefulness/manual-rescue/fact-error gates pass and the
   user explicitly accepts the product.

No historical benchmark, synthetic smoke, or backfilled ledger row counts as a
self-use day.

## Completed In This Slice

### Numeric lineage is fail-closed without crashing the arm

Commit `c35740e6` separates material-number detection from source-lineage
canonicalization. It normalizes ISO/Chinese dates, stage-day expressions, and
directional percentages. An uncovered numeric claim is still forbidden from
the public answer, but the runner now publishes an explicit evidence-gap answer
with `status=degraded` and `stop_reason=numeric_lineage_gap` instead of losing
the arm to `runner_exception`.

Evidence:

- focused RED before fix: 2 failed, 1 passed;
- final relevant suite: 87 passed, 1 skipped;
- offline rebound replay: C4 -> E9, C6 -> E9, C7 -> E4/E12/E18,
  C9 -> E7; zero unbound material-numeric claims;
- Retry 3 was deliberately not run because the frozen provider identity is no
  longer reproducible.

### Daily data gate diagnosis

The dirty primary workspace contains an uncommitted candidate change to
`scripts/check_daily_review_data.py`. Read-only execution against 2026-07-28
produced:

- sector-name continuity: 406/406 = 100%;
- stock coverage: 4567/4567 = 100%;
- final result: COMPLETE.

That result proves the old exact-code gate has a false-positive component, but
it does **not** prove the data path complete. A deeper read-only audit found:

- `dim_sector` has 407 current `.FP` identities last seen 2026-07-28 and 223
  obsolete `.TI` identities last seen 2026-07-24; the old rows were never
  retired and all remain active;
- the member synchronizer loads all 630 identities, limits each invocation to
  60, and does not persist empty/error attempts;
- the first 60 database rows are all obsolete `.TI` identities, so every one
  of the 20 loops retries the same rows and never reaches `.FP` identities;
- the fallback populated only 117/407 current `.FP` sectors. The candidate gate
  ignores the remaining 290 because they had no historical member rows;
- a direct read-only probe proved those rows are retrievable: `6G概念`
  (`990003.FP`) returned 97 members for 2026-07-28.

Therefore the candidate `COMPLETE` is a false green. The fix must atomically own
the current sector universe, retire stale identities only after a complete list
fetch, give member sync a durable per-sector progress receipt, and gate current
membership coverage. Adjacent-day name continuity remains a useful secondary
check, not the primary completion proof. Reduced phase/table fixtures must not
gain undeclared sector dependencies.

Full receipt:

`docs/verification/daily-data-sector-universe-audit-2026-07-29.md`

Implementation is waiting at the design-approval gate; do not scoop the dirty
primary-workspace file into a mixed commit.

### Clean 8799 preflight

A temporary 8799 process used:

- code root: clean `c35740e6` candidate;
- finance root: `/Users/a77/finance-workspace-private`;
- isolated canary user store (not the canonical self-use ledger);
- `ASK_CONTINUOUS_RUNTIME=on`;
- backend: `continuous_glm`;
- RAG worker enabled with the production private Wiki/index.

Two startup configuration issues were found and resolved without code changes:

- `WORKBENCH_REPO_ROOT` must be the candidate code root while `FINANCE_WS` is
  the private data root; otherwise health reports the wrong revision;
- the Codex parent process supplied an HTTPX-incompatible `NO_PROXY` IPv6 CIDR.
  Removing `NO_PROXY/no_proxy` for the canary allowed the cached BGE-m3 model to
  load 391/391 weights and return a fresh Hybrid hit.

After correction, readiness was fully green:

- source revision `c35740e6`, `source_dirty=false`;
- RAG worker ready, active=1, model_load_count=1;
- seven registered product skills;
- market snapshot contract PASS.

The 2026-07-28 snapshot was rebuilt once from exact DuckDB data as a pre-release
manual repair: provider `duckdb_exact`, quality `complete`, freshness `fresh`.
This repair must not be counted as unattended stability.

## Current Blocking Evidence

The built-in GLM 429 is no longer the active blocker. The saved Keychain
`openai/gpt-5.6-sol` provider and its local trusted gateway were independently
probed successfully. A clean 8799 was then started on `ca190b07` (product code
`c35740e6`) with `sdk_gpt`; after the lazy session load, runtime readiness,
snapshot, data consistency, RAG worker, skills, provider, secret scan, and
public leak scan were green.

Five product workflows were frozen before execution and run exactly once each
without changing any prompt, gate, budget, tool, provider, or runtime:

- daily market: structurally complete with 13 bound evidence items, but semantic
  judge transient failure left report/answer `partial`;
- theme research: 24 evidence items, then `research_stage_closed` / `sdk_timeout`;
- stock research: 15 evidence items, missing-date valuation snapshot plus typed
  stock-query gaps, call exhaustion, and `sdk_timeout`;
- news impact: 18 evidence items, then `sdk_timeout` before delivery;
- watchlist: 22 evidence items, repeated `in filter requires an array`, then
  stage close / `sdk_timeout`.

Strict clean useful rate is therefore `0/5`; only the daily-market candidate has
a substantive answer, and the other four public answers are honest evidence-gap
fallbacks. The runtime gives the adapter 120 seconds, reserves 40 seconds for
verification, and the SDK reserves up to another 20 seconds for delivery. The
effective new-tool window is therefore about 60 seconds for all product cases.
The SDK path also does not apply the existing deep `ModeGovernor`, so complex
five/six-output contracts remain standard-tier.

Full receipt:

`docs/verification/product-five-workflow-canary-2026-07-29.md`

The temporary 8799 process was stopped. Canonical 8792 was not touched and still
runs the older `a0b8e8c1` runtime from a dirty runtime directory.

## Self-Use Gate Truth

Both `default` and `linxiaoqi5111` currently evaluate to:

- distinct trade dates: 0;
- covered workflows: 0/5;
- event count: 0;
- user approval: false;
- gate: failed.

The five old `self-use-8799-*` benchmark artifacts are not ledger events and
must not be backfilled as real use.

## Next Execution Order

1. Approve and implement one generic product-latency design: preserve the
   standard path for simple contracts, but give observably complex multi-domain
   contracts the existing deep tier and a root deadline that actually contains
   research, SDK delivery, and semantic verification. Do not globally relax
   gates or tune individual questions.
2. Make the semantic verifier use a sealed release provider/latency profile;
   retain fail-closed behavior for malformed or contract-invalid output.
3. Repair the two generic typed-data seams exposed by canary: condition or
   safely normalize scalar `in` filters, canonicalize six-digit A-share codes,
   and compose a current local-price anchor without accepting stale valuation
   ratios.
4. Replace the hard-coded `zhipu/glm-5.2` self-use binding with an explicit
   sealed release-profile identity. A provider switch must invalidate the old
   approval fingerprint rather than silently mixing runs.
5. Implement the approved sector-universe producer + gate design in an isolated
   branch: snapshot-owned active identities, durable member-sync progress,
   honest current-universe coverage, secondary name continuity, and phase/table
   isolation. Verify unattended nightly runs. The manual 2026-07-28
   `COMPLETE` is a false green, not evidence of stability.
6. Freeze one shared repair revision, pre-register one new five-workflow product
   canary, and execute each workflow once. Do not use it as a debugging loop.
7. Prepare a cutover receipt containing old runtime, target revision, exact
   data/snapshot dates, RAG readiness, five-workflow canary results, and rollback
   command. Do not switch 8792 without explicit user approval.
8. Only after cutover, record real self-use events on each trading day. The
   earliest final maturity decision remains calendar-bound to 10 actual trading
   days.

## Preserved Boundaries

- no merge to `main`;
- no canonical 8792 switch;
- no merge of KB candidate `9053b0c4`;
- no key, database, model, index, venv, log, or private ledger committed;
- no weakening of cutoff, freshness, EvidenceLedger, semantic, or numeric
  gates;
- App Server arm remains unrun until process/provider identity is observable.

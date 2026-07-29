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

This demonstrates that the old `dim_sector` all-time active-code comparison was
producing false gaps from renamed/historical aliases. The change is not yet
committed. It must be implemented in a clean branch with tests for both the 95%
adjacent-trading-day name continuity and the rule that only sectors which had
historical members may fail when today's member set disappears.

The three reasonable designs are:

1. **Recommended:** adjacent-day unique-name continuity plus historical-member
   continuity. This detects real daily breaks without treating aliases as
   missing current rows.
2. Keep exact `dim_sector` coverage. This is strict but already falsified by
   provider code/name churn.
3. Use only a minimum row count. This is simple but can pass a systematically
   wrong subset, so it is too weak.

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

The first and only real workflow canary was “today's market.” Transport,
readiness, public leak scan, and secret scan passed. The continuous episode then
received `LLM HTTP 429` on its first provider turn, stopped as
`model_unavailable`, and returned a transparent partial answer. The semantic
smoke correctly rejected it.

Artifact:

`/Users/a77/.finance-runtime/evals/candidate-c35740e6-self-use-today-2026-07-29.json`

SHA-256:

`732532507e906edb825152b3e7a87595570e5aca890410ca980b38d191257cf7`

The other four product workflows were not run because they would repeat the
same provider failure. The temporary 8799 process was stopped. Canonical 8792
was not touched and still runs the older `a0b8e8c1` runtime from a dirty runtime
directory.

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

1. Obtain one production-usable model path. The built-in GLM path is currently
   rate-limited; the saved OpenAI Keychain record does not reproduce the frozen
   GPT provider used by the benchmark. Do not silently switch providers.
2. After model readiness, restart the same clean 8799 candidate and run each of
   the five product workflows exactly once. Record failures as blockers rather
   than entering per-question tuning loops.
3. Implement the approved daily-data gate design in an isolated branch and
   verify the next unattended nightly runs. The manual 2026-07-28 repair is not
   evidence of stability.
4. Prepare a cutover receipt containing old runtime, target revision, exact
   data/snapshot dates, RAG readiness, five-workflow canary results, and rollback
   command. Do not switch 8792 without explicit user approval.
5. Only after cutover, record real self-use events on each trading day. The
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

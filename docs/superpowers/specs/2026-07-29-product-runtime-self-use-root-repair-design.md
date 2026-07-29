# Product Runtime and Self-Use Root Repair Design

Date: 2026-07-29

Status: `approved_direction; written_spec_review_pending`

Branch: `feat/agent-runtime-backends-verify`

## 1. Objective

Make the clean candidate answer the five real product workflows through one
bounded, observable runtime and make qualifying runs count toward the same
sealed self-use release profile. The design preserves PIT cutoff,
EvidenceLedger, structural/numeric/semantic gates, and honest degradation.

The solution is generic. It must not add Ruihuatai-, MLCC-, news-, watchlist-,
or benchmark-question-specific routes.

## 2. Verified Failure

The pre-registered `openai/gpt-5.6-sol` 8799 canary executed daily market,
theme research, stock research, news impact, and watchlist exactly once on
`ca190b07`/product code `c35740e6`.

Strict clean useful rate was 0/5:

- daily market produced a structurally complete, 13-evidence answer, but its
  semantic judge had a transient provider failure and the report stayed
  partial;
- theme, stock, news, and watchlist collected 15-24 evidence items but timed
  out before delivery;
- watchlist repeated an `in filter requires an array` typed error;
- valuation had current financial evidence but no fresh dated valuation market
  snapshot and missed a six-digit stock query;
- self-use run binding still defaults to `zhipu/glm-5.2`, so a clean GPT run
  could not count.

The product API gives a turn 120 seconds. The adapter reserves 40 seconds for
verification, giving the SDK 80 seconds; the SDK reserves up to 20 seconds of
that for delivery, leaving about 60 seconds for new tools. The SDK path does not
apply the existing 240-second deep ModeGovernor admission.

Authoritative evidence:

`docs/verification/product-five-workflow-canary-2026-07-29.md`

## 3. Scope

This slice owns:

1. contract-derived standard/deep latency admission shared by SDK and GLM;
2. one root deadline containing research, SDK delivery, and semantic
   verification without double reservation;
3. a sealed semantic-verifier provider/latency profile;
4. safe typed-query normalization for scalar `in` filters and A-share codes;
5. a current local price anchor separated from unavailable valuation ratios;
6. a sealed release profile bound into reports and self-use events;
7. status projections that keep transport success distinct from answer
   completion;
8. one new pre-registered five-workflow canary after deterministic verification.

## 4. Non-Goals

- Do not implement or run the App Server arm while runtime identity is not
  observable.
- Do not run the 28-case board or Retry 3 as a debugging loop.
- Do not increase every question's budget globally.
- Do not bypass semantic verification or turn transient failure into completed.
- Do not accept stale valuation ratios or fabricate missing market cap/PE/PB.
- Do not merge `main`, switch 8792, or backfill benchmark artifacts into the
  self-use ledger.
- Do not change the five-workflow prompts after preregistration.

## 5. Release Execution Profile

Introduce an immutable internal `ReleaseExecutionProfile` with:

- `profile_id`: SHA-256 over canonical non-secret fields;
- runtime backend;
- provider ID and model;
- runtime-behavior artifact fingerprint;
- standard/deep research budgets and tool caps;
- semantic-verifier provider ID, model, and timeout class;
- evidence/cutoff contract versions.

The profile never stores a key. Provider endpoints and credential hashes remain
private diagnostics and are not part of public answers. The report records the
`profile_id`, provider, model, and backend; public health exposes only the
non-secret readiness identity already allowed by current policy.

The behavior fingerprint hashes the deployable runtime code, dependency lock,
and behavior-bearing configuration manifest. It excludes docs, tests, logs,
credentials, and user data. The Git revision is retained as audit provenance,
but a docs-only commit does not reset a ten-day self-use clock.

Changing backend, provider, model, budget contract, or verifier identity creates
a new profile ID. Runs from different profiles are never silently pooled for
self-use maturity.

## 6. Contract-Derived Latency Admission

### 6.1 Profiles

| Tier | Research allocation | Tool cap | Semantic allocation | Total turn allocation |
|---|---:|---:|---:|---:|
| standard | 90 s | 8 | 40 s | 130 s |
| deep | 240 s | 24 | 40 s | 280 s |

SDK delivery reserve remains inside the research allocation. It is not deducted
again from the total turn after research has already been bounded.

### 6.2 Admission

A user-selected quick/standard mode locks the standard tier. A user-selected
deep mode locks the deep tier. Without an explicit tier, a code-owned preflight
admission selects deep when any of these observable conditions holds:

1. the task has at least five required outputs and at least two evidence
   capability domains;
2. the task compares or tracks at least two independent entities;
3. an existing approved ModeGovernor complexity signal requires multiple
   independent branches.

Otherwise it selects standard. A model may request less depth, but cannot raise
the code-owned cap. The predicate uses task/contract structure, never question
text or case IDs.

The selected tier is written into the private episode artifact and release
receipt. Admission happens before the outer `RunSupervisor` deadline is
created. The selected total allocation (130 or 280 seconds) becomes that
supervisor deadline; the product endpoint no longer installs a lower fixed
120-second cap. The deep total is the code-owned maximum, so neither the model
nor a caller can extend it.

### 6.3 One budget authority

`RootBudgetLedger` remains the single call/seconds authority for research and
repair. `RunSupervisor` owns the selected total turn deadline, while the
adapter allocates its research and semantic children without exceeding that
root. The SDK owns no independent wall-clock cap beyond the research grant and
its internal delivery partition. Semantic verification consumes only the
separately reserved semantic grant.

Concretely, the SDK request deadline equals the selected research grant. Its
delivery reserve partitions that same grant; it neither subtracts a second
time from the adapter total nor extends past the research deadline.

No stage may extend the outer total, and unused semantic time cannot be spent on
new research tools after research closes.

## 7. Semantic Verifier Profile

The semantic verifier receives an explicit sealed provider adapter from the
release profile. It must not discover or silently substitute another provider
from ambient environment order.

For the approved candidate, composer and verifier identities are both
`openai/gpt-5.6-sol`; correlated use is recorded. An independently configured
judge is allowed only when its identity is explicitly present in the release
profile.

The verifier has one bounded strict-JSON window plus transport grace within the
40-second allocation. It may retry only errors already classified transient and
release-safe. Outcomes remain:

- valid pass/repair: eligible for completed projection;
- semantic rejection or malformed output: fail closed;
- transient/deadline failure after structural completion: candidate draft with
  `partial`, never completed;
- structurally partial input: evidence-gap answer, never upgraded by the judge.

Private telemetry records stable error category, attempts, elapsed time, and
provider/profile identity without raw prompt, response, endpoint secret, or key.

## 8. Typed Finance Query Boundary

### 8.1 `in` normalization

At the typed argument boundary, before validation:

- `op="in"` with a scalar string/number becomes a one-element array;
- an existing array is preserved after element validation;
- null, object, nested array, or empty array remains invalid;
- other operators keep scalar semantics and are not widened.

The normalized typed query, not the raw provider payload, is fingerprinted for
deduplication. The observation may state that a safe normalization occurred.

### 8.2 A-share code normalization

For `stock_code` filters only, a six-digit numeric code is canonicalized to the
exchange-suffixed identity using the existing A-share mapping rules, including
Shanghai, Shenzhen, and Beijing prefixes. Already suffixed identities are
validated and preserved. Names and arbitrary strings are not guessed.

When the task has an `entity_anchor`, its canonical code is preferred over
model spelling. This normalization stays inside FinanceQuery's whitelist and
does not introduce free SQL.

## 9. Current Price and Valuation Evidence

The valuation `market_data` tool separates two evidence components:

1. **current local price anchor:** latest cutoff-safe `fact_stock_daily` date,
   close, prior close/return, and amount for the canonical entity code;
2. **valuation ratios:** market cap, PE/PB, or comparable multiples from a
   provider snapshot only when its source date is present and meets the
   freshness floor.

A fresh local price may satisfy the current-price part of the evidence plan. It
does not make missing PE/PB/market-cap evidence available. The structural
contract reports ratio/scenario gaps explicitly and forbids a completed
valuation range that depends on absent values.

No stale external valuation row is used as current evidence.

## 10. Self-Use Release Binding

Replace permanent `zhipu/glm-5.2` defaults with an explicit
`SelfUseReleasePolicy` derived from the sealed `ReleaseExecutionProfile`.

Each ingested self-use event must include:

- run ID;
- trade date and workflow;
- outcome/usefulness/manual-rescue/fact-error fields;
- `release_profile_id`.

Run binding requires:

1. terminal successful RunStore state;
2. completed report and answer status;
3. `llm.used=true`;
4. report provider/model/backend/profile ID equal the active release policy;
5. matching report and SSE evidence;
6. report `as_of` equals the event `trade_date`; weekend/holiday usage records
   the latest valid market trading day as the event trade date rather than
   weakening this equality;
7. no template fallback or severe integrity degrade.

The maturity eligibility fingerprint includes `release_profile_id`. A profile
change invalidates prior user approval. Events from an older profile remain
auditable but do not count toward the new 10-day gate.

For the active profile, maturity requires all existing mechanical product
thresholds together:

- events on at least ten consecutive canonical A-share trading dates;
- all five workflows represented by eligible real product events;
- core success rate at least 95%;
- usefulness rate at least 80%;
- manual-rescue rate no greater than 5%;
- zero severe fact errors;
- explicit user approval after the mechanical gate is green.

Synthetic tests, benchmark artifacts, temporary canaries, and backfilled rows
never count as self-use events. User approval cannot override a mechanical
blocker.

## 11. Status and User Experience

Run transport completion remains distinct from product completion:

- `run.status=completed` means orchestration terminated cleanly;
- `report.answer_status=completed` means the user received a verified answer;
- degraded/partial answers remain visible with a concise evidence boundary;
- maturity ingestion uses report/answer truth, not transport status alone.

The UI must not display internal budget names, tool identifiers, hashes, or
provider errors. It may say that verification was unavailable or evidence was
insufficient in user language.

## 12. Error Handling

- Provider unavailable before research: transparent model-unavailable partial;
  no fallback to another provider.
- Research budget exhausted with evidence: one bounded delivery turn inside the
  research allocation; no new tools after close.
- Typed query invalid after normalization: stable actionable observation;
  bounded retry, no exception escape.
- Current price absent/stale: valuation current anchor remains unfulfilled.
- Semantic verifier transient: structurally complete draft remains partial.
- Profile mismatch during self-use ingestion: reject without mutating ledger.
- Profile changes after approval: old approval fails fingerprint validation.

## 13. Test Contract

Deterministic tests must cover:

1. daily-market-shaped contract selects standard and receives 90+40 seconds;
2. five-output/multi-domain theme, valuation, news, and tracking contracts select
   deep without question-specific matching;
3. explicit quick cannot be silently promoted; explicit deep stays within caps;
4. RunSupervisor receives 130 or 280 seconds after admission and no fixed
   120-second product cap truncates deep mode;
5. SDK research sees 90 or 240 seconds, not total minus a duplicate reserve;
6. tool-stage delivery remains inside research allocation;
7. semantic verifier cannot exceed its 40-second allocation or switch provider;
8. transient verifier failure stays partial; malformed/rejected stays
   fail-closed; valid pass can complete;
9. scalar `in` becomes one validated array item and does not repeat as the same
   invalid action;
10. invalid/nested/empty `in` values remain rejected;
11. SH/SZ/BJ code canonicalization and already-suffixed preservation;
12. entity anchor wins over ambiguous six-digit spelling;
13. fresh local price is published while missing valuation ratios remain gaps;
14. stale/missing ratio evidence cannot complete a valuation scenario;
15. self-use accepts a matching GPT release profile and rejects GLM, mismatched
   model, backend, profile, partial report, or missing SSE evidence;
16. profile change invalidates prior approval fingerprint;
17. public leak and secret scans remain green.

Existing numeric lineage, cutoff, freshness, RootBudgetLedger, repair-cycle,
EvidenceLedger, semantic verifier, Run/SSE, and self-use suites must remain
green.

## 14. Verification and Release Sequence

1. Implement and test in the clean candidate worktree only.
2. Run focused suites, combined runtime/self-use suites, Ruff, and diff checks.
3. Freeze a clean revision and a non-secret release profile receipt.
4. Require the daily-sector design's exact gate and three-date unattended data
   readiness streak to be green.
5. Start temporary 8799 with isolated users, production data roots, True Hybrid
   RAG, and saved `gpt-5.6-sol`.
6. Require runtime/data/RAG/provider readiness before any workflow.
7. Pre-register the same five workflow prompts and execute each once.
8. Record failures as release blockers; do not tune questions or rerun within
   the same revision.
9. Only if all five have completed report/answer truth and scans pass may the
   system prepare an 8792 cutover receipt.
10. 8792 still requires explicit user approval. Self-use day counting begins
   only after that cutover and uses real product events.

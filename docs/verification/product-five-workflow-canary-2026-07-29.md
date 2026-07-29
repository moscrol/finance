# Product Five-Workflow Canary

Date: 2026-07-29

Status: `release_blocked`

## Scope and frozen identities

- Runtime worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
- Runtime revision: `ca190b076857b5b89cb5afcf712612323c55d158`
- Product-code revision: `c35740e6`
- Backend: `sdk_gpt`
- Provider/model: `openai/gpt-5.6-sol`
- Provider endpoint: local trusted gateway `http://localhost:57244/v1`
- Finance root: `/Users/a77/finance-workspace-private`
- Wiki root: `/Users/a77/knowledge-base-private/wiki`
- Isolated canary users root: `/Users/a77/.finance-runtime/candidate-c35740e6-gpt-users`
- Canonical 8792: unchanged

The five questions and output paths were frozen before the first run in:

`/Users/a77/.finance-runtime/evals/candidate-ca190b07-gpt-five-workflow-preregistration-2026-07-29.json`

SHA-256:

`10b1e870ed9364e79cc48427eb80718a2ed47cb173bdfa0ada1b6e285978853b`

No prompt, runtime, tool, gate, provider, budget, data root, or knowledge root
changed between cases. Each workflow was executed exactly once.

## Readiness before execution

The saved Keychain provider loaded without exposing the credential, and an
independent minimal Responses call returned successfully from `gpt-5.6-sol`.
After the lazy session provider load, runtime health reported:

- backend `sdk_gpt`, `ready=true`, reason `ready`;
- source revision `ca190b07`, `source_dirty=false`;
- all critical readiness checks true;
- snapshot date `2026-07-28`, provider `duckdb_exact`, quality `complete`,
  freshness `fresh`;
- market database date `2026-07-28`, consistent with the snapshot;
- RAG worker `ready`, active `1`, `model_load_count=1`;
- seven product skills registered.

`NO_PROXY/no_proxy` were removed for this isolated process because the Codex
parent environment contains an HTTPX-incompatible IPv6 CIDR. No code or
credential change was needed.

## Results

| Workflow | Run | Product result | Tools / evidence | Decisive observation |
|---|---|---|---:|---|
| `daily_market` | `run_20260729_144954_697677` | gate fail; report/answer `partial` | 2 / 13 | Structural verification completed with all three outputs bound. The answer was substantive and current, but the semantic judge ended `unavailable` after a transient provider error, so the public result was correctly labelled a candidate draft. |
| `theme_research` | `run_20260729_145119_393891` | degraded gap answer | 3 / 24 | Research collected Hybrid and news evidence, then the fourth request hit `research_stage_closed`; the SDK ended `sdk_timeout` before producing any bindings or required outputs. |
| `stock_research` | `run_20260729_145251_327749` | degraded gap answer | 6 / 15 | Financial data succeeded, but the current valuation snapshot had no usable source date, stock queries returned empty/error, the sixth call exhausted the standard call grant, and the SDK timed out without a final answer. |
| `news_impact` | `run_20260729_145428_657427` | degraded gap answer | 4 / 18 | Hybrid and news evidence were collected; a repeated news query was deduplicated and Web returned empty. The SDK timed out before delivery, leaving all six required outputs unbound. |
| `watchlist` | `run_20260729_145559_270155` | gate fail; report/answer `partial` | 6 / 22 | Two `finance_query` calls repeated the same typed error (`in filter requires an array`). The next entity search was closed by the research stage and the SDK timed out before comparison delivery. |

All five RunStore records are terminal `completed` with an explicit degrade,
but all five reports are `partial`. This distinction matters: terminal transport
success is not product-answer success. The strict clean useful rate is `0/5`.
Only the daily-market candidate contains a substantive answer; the other four
public answers are evidence-gap fallbacks.

Aggregate artifacts:

| Workflow | Artifact SHA-256 |
|---|---|
| daily market | `648de52355b6acaf43aa34b5efe35b371db8120acdad25950f52422940307342` |
| theme research | `71e394089bbe314698b06748f26c256348094d2a7d5d798793ba6d3256873dd0` |
| stock research | `cf2c54db900e6927611fe771a02ed272dd89b31a7823f84ce23979f817e2471e` |
| news impact | `41e1f71aa6235086fb50a092d17dd43679984e1b31a7521a474bbaa9cc082bff` |
| watchlist | `ba215165ca6b755c2a2ba0d4bf820692fe20d449960f01344ad6f7c4a46bc20d` |

Every aggregate passed the secret scan and public-control-field scan.

## Root-cause findings

### 1. The product SDK path still has a short research window

The API gives a continuous turn 120 seconds. `ContinuousTurnAdapter` reserves
40 seconds for verification before constructing the runtime context, so the
SDK receives 80 seconds. The SDK then reserves up to 20 seconds inside that
window for delivery, leaving approximately 60 seconds in which new research
tools may be requested.

That is the production analogue of the previously diagnosed benchmark budget
problem. It is not evidence that `gpt-5.6-sol` cannot answer the questions:
theme, news, and watchlist accumulated 18-24 evidence items before the shared
deadline closed research, then never received a delivery turn.

The existing `ModeGovernor` can promote the GLM episode to a 240-second deep
policy, but the SDK path does not apply that governor before its single SDK run.
All five product contracts therefore remained `research_tier=standard`, even
when they required five or six grounded outputs across multiple evidence
domains.

### 2. Semantic verification is a separate latency/reliability seam

The daily-market model finish was structurally complete and fully bound. Its
semantic judge used the session provider, consumed the bounded verification
window, and returned a transient provider failure. Fail-closed candidate
release behaved as designed, but this makes a high-quality answer ineligible
for release and self-use accounting.

This should not be fixed by declaring semantic verification optional. The
runtime needs an explicit verifier latency profile and a reproducible provider
identity, with the existing fail-closed behavior retained for malformed or
contract-invalid output.

### 3. Two typed-data usability gaps amplify the timeout

- `finance_query` advertises an `in` operator whose runtime requires an array,
  but the provider-facing schema permits a scalar value. The model repeated the
  same scalar error once in the watchlist run.
- `fact_stock_daily` contains a current `2026-07-28` row for `688323.SH`, but
  the valuation market tool relies on a separate valuation snapshot and
  correctly rejects it when its source date is unknown. A six-digit stock-code
  query can also miss the canonical exchange-suffixed value.

These are generic typed-boundary and current-price-anchor issues. They must not
be repaired with a Ruihuatai-specific route or by accepting stale valuation
data.

### 4. The self-use model identity is hard-coded to the old runtime

`self_use_maturity.py` currently defaults run binding to
`zhipu/glm-5.2`. A real `openai/gpt-5.6-sol` run would therefore be rejected even
after a clean answer. The self-use gate must bind to a sealed release profile,
not to permanent provider constants and not to whichever provider happens to
be available at ingestion time.

## Release decision

Do not switch 8792 and do not start the 10-day maturity clock. The five-workflow
product gate is not green, and the current self-use ledger cannot truthfully
bind the selected release model.

The temporary 8799 process was stopped after the suite. The next live suite is
allowed only after one shared product-surface repair batch is frozen; it must
again be pre-registered and executed once, not used as a per-question debugging
loop.


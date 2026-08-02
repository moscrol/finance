# Continuous Harness Acceptance Trust Completion

Date: 2026-08-02

## Scope and safety

- Worktree: `tmp/agent-runtime-seam-fix-69f9cf17`
- Branch: `fix/continuous-harness-acceptance-trust`
- Verified revision: `95b010dccc0e705961bda98c48ba1fc69fab05c2`
- Production 8792 was not modified or restarted.
- The branch was not merged into `main` and was not pushed.
- Knevo reverse engineering was not continued.

## What changed

The Continuous Harness acceptance path now proves the process and execution
that produced every measured turn:

- health exposes the runtime instance, full source revision, dirty state,
  code root, actual Python import root, backend/model, provider label/protocol,
  provider-chain size, and a non-secret endpoint fingerprint;
- each Run owns an append-only `attempts.jsonl` with `attempt.started`,
  `execution.bound`, and `attempt.finished` events;
- execution binding records the observed path, terminal owner, contributors,
  TaskFrame hash, PIT cutoff, effective backend/model, and artifact receipts;
- the API exposes a redacted Run provenance projection;
- acceptance uses a frozen execution-contract overlay and fails closed on
  runtime, path, attempt, or receipt drift;
- C10 reuses one conversation, polls exact message/Run IDs, validates the
  parent Run chain, and keeps Layer 1 execution validity separate from Layer 2
  answer quality;
- a secret-safe runner connects directly to the local Cockpit OpenAI Responses
  API, isolates provider environment and user state, refuses dirty checkouts or
  occupied/production ports, and gates full execution with a same-process
  canary.

## PIT false-green found and fixed

The first canary exposed a real false-green. C10 used one conversation and
correct execution paths, but the Episode information cutoff was
`2026-08-02` even though the TaskFrame contained `2026-07-23`. The summary
recorded `multi_turn_cutoff_mismatch` but did not initially make Layer 1 fail.

The root causes were:

1. `build_episode_context()` ignored an explicit ISO TaskFrame timeframe when
   selecting `InformationCutoff`, then defaulted to runtime today;
2. `刚才你说的……再确认` was not classified as a contextual continuation, so
   the third C10 TaskFrame lost its inherited timeframe;
3. recorded execution diagnostics were not included in the Layer 1 hard gate.

The fix makes an explicit historical ISO date an
`InformationCutoff(source=requested)`, clamps a future requested date to
runtime today, inherits the prior timeframe for the confirmation form, and
requires zero execution diagnostics for Layer 1 eligibility. The repeated
canary observed `2026-07-23` on all three C10 turns.

## Cockpit live results

Provider smoke:

- model: `gpt-5.6-sol`
- protocol: OpenAI Responses-compatible
- `/models`: target model present
- `/responses`: `completed`, exact bounded output `OK`

Same-process canary:

- 6/6 observed paths matched their contracts;
- 4/4 Continuous Episode receipts were valid;
- C10 used one conversation, three distinct Run/message IDs, a valid parent
  chain, and the same requested cutoff on all three turns;
- runtime instance drift: 0;
- secret scan: 0 hits.

Full 28-case run:

- 30/30 turns completed;
- 30/30 observed paths matched;
- 28/28 Continuous Episode receipts were valid;
- path distribution: 28 Continuous Episode, 1 Continuous clarification,
  1 legacy direct;
- runtime instance drift: 0;
- execution diagnostics: 0;
- secret scan: 0 hits.

Local receipts (gitignored):

- `tmp/continuous-cockpit-acceptance/20260802T091214Z-full.json`
- `tmp/continuous-cockpit-acceptance/20260802T091833Z-runner.json`

## Layer 2 boundary

This proves Harness identity, not product maturity. The deterministic board for
the full receipt reports:

- 28/28 cases reached a terminal answer;
- 25 degraded, 3 normally completed;
- truth: 0 pass, 15 fail, 13 unjudgeable;
- delivery: 3 pass, 25 partial, 0 fail;
- information comparison: not evaluated for all 28.

Therefore the Continuous Harness Layer 1 is trustworthy, while Layer 2 remains
well below release quality. Do not present the Harness result as production
readiness or use it to backfill the Self-use Gate.

## Verification and known baseline failures

- focused runtime/Harness regression: 349 passed after fixing one new legacy
  worker-call compatibility regression;
- PIT/inheritance/adapter regression: 211 passed (two unrelated stale board
  tests deselected);
- runner safety tests: 8 passed;
- Ruff: all touched files passed;
- two existing acceptance-board tests still assume the pre-aggregation table
  header and implicit `latest_run()` sidecar behavior. They are not caused by
  this branch and should be repaired in a separate test-contract cleanup.

## Recommended next step

Do not spend more model calls yet. Use the frozen full receipt to cluster the
25 degraded cases by deterministic reason and fix the largest shared product
seams first (routing, evidence retrieval, AnswerSpec claim/metadata separation,
and timeout budgeting). Tool lifecycle and fault injection remain the next
Harness-hardening batch, but they should not obscure the current Layer 2 gap.


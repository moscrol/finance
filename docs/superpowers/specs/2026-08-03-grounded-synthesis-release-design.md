# Grounded Synthesis Release Design

**Date:** 2026-08-03
**Status:** approved for autonomous execution
**Source contract:** `docs/handoffs/2026-08-03-shared-layer-audit-handoff.md`

## 1. Goal and fixed facts

Unblock the `DecisionBrief → Grounded Composer → semantic judge` path without
reopening the M2 root-cause decision, then turn the existing synthesis-health
classifier into a deterministic release gate and audit the repaired path across
the self-built and Codex harnesses.

The following are inputs, not hypotheses:

- M2 commit `07887e92` establishes that three serial LLM calls do not fit the
  115-second child / 120-second root budget.
- A frozen, valid eight-field `DecisionBrief` exists at
  `run_20260803_142959_204791` and lets replay skip the 69.740-second brief call.
- `synthesis_health.py` already owns the four business states plus the
  compatibility state `unknown`; T2 changes enforcement, not classification.
- The current `fix/grounded-chain-critical-path` branch is a negative experiment
  receipt and must not become the release branch.

## 2. Approaches considered

### A. Continue on the negative-experiment branch

This minimizes checkout work, but ties mergeable evaluation and product fixes to
budget experiments that the handoff explicitly says must not merge. Rejected.

### B. Separate branch per T1, T2, T3, and T4

This maximizes isolation but creates several cherry-pick boundaries across code,
measurement artifacts, and the M2 report. It increases the chance that T3 reads
measurements produced by a different revision. Rejected.

### C. One clean release branch from `main` with staged commits

Use `fix/grounded-synthesis-release` from `main@e785f833`. Land replay, health
gate, measured architecture fix, and normalized audit as separate commits. This
preserves causal history while keeping every measurement bound to one branch.
Selected.

## 3. Components and interfaces

### 3.1 Frozen-input replay

`intelligence/eval/grounded_replay.py` reads `run.json`, `answer_spec.json`, and
`decision_brief.json`. It reconstructs the production `AnswerSpec`, calls the
existing registry and prompt builders, and invokes the same provider boundary as
production.

Composer invocation:

```text
grounded-replay --run-dir RUN --phase composer --grant-seconds 115 --out FILE
```

Judge invocation additionally requires the successful composer artifact:

```text
grounded-replay --run-dir RUN --phase judge --grant-seconds 115 \
  --composer-artifact FILE --out FILE
```

`--keychain-user` is an explicit opt-in for loading the already-configured local
Workbench credential. Secrets remain in memory and never enter argv, artifacts,
or logs.

Each artifact records input hashes, revision, phase, status, elapsed time,
provider/model, finish reason, raw output, parse/validation result, and
`completion_tokens=null` when the provider adapter does not expose usage. A
timeout is a valid measurement and is recorded as a lower bound; it is not
retried with a larger grant.

The judge replay canonicalizes claim IDs and performs the same deterministic
validation/repair sequence as production before constructing the judge prompt.
It never judges an invalid or missing composer output.

### 3.2 Synthesis-health gate

The existing human-readable report remains byte-for-byte stable when `--gate`
is absent. Gate mode adds these contracts:

- `0`: threshold satisfied;
- `1`: health/data gate failed;
- `2`: invalid command usage;
- threshold is a finite ratio in `[0, 1]`;
- any missing/unreadable input or any input with zero completed turns fails
  closed;
- `--fail-on-unknown` blocks compatibility-state turns;
- the aggregate full-pass ratio is calculated from structured counts, never by
  parsing rendered text.

The two local A4 artifacts are acceptance receipts, not CI dependencies, because
they are currently untracked in the source worktree. CI uses minimal constructed
fixtures.

### 3.3 Architecture decision after T1 and the single A4 canary

T1 measured composer at 33.338 seconds and judge at 46.982 seconds.  This
invalidated the preregistered 110–180 second composer estimate and selected the
deterministic `DecisionBrief`.  The single A4 canary then invalidated the local
assumption that both provider phases would enter with a fresh 115 seconds: prior
retrieval had already consumed 66.118 seconds of the same root deadline.

The final bounded profile is therefore:

| field | value | basis |
|---|---:|---|
| grounded legacy root | 180s | observed end-to-end need 146.55s × 1.2, rounded up |
| synthesis reserve | 100s | 97s two-phase admission plus 3s hand-off room |
| child ceiling | 115s | remains bounded below root |
| composer grant | 40s | ceil(33.338s × 1.2) |
| judge reserve | 57s | ceil(46.982s × 1.2) |
| admission floor | 97s | composer grant plus judge reserve |

This is engineering headroom from a single frozen sample, not p95.  When fewer
than 97 seconds remain, composer is skipped with `insufficient_budget` before a
provider call.  Continuous runtime retains its independent 120-second contract.
Generic quick/standard owners retain their 30/90-second tier windows and their
own 20-second synthesis reserve; only generic deep inherits the 100-second
grounded reserve, so the new profile cannot collapse ordinary retrieval to zero.

The deterministic brief projects claim IDs from `AnswerSpec`. `core_tension` is
not mislabeled as a pure projection: it uses a deterministic template combining
the leading support with the leading counterevidence or gap. `chain_mapping`
always contains all in-window `company:`, `chain:`, and `exposure:` claims.

The preregistered A4 canary remains a red receipt and is not rerun.  Its failure
selected the end-to-end deep profile and the fail-fast admission guard; offline
tests, rather than a second A4 attempt, verify the repair.  The full live A group
remains prohibited.

### 3.4 Cross-harness audit

T4 first extends `docs/trace-profile.md` with the shared seven-step vocabulary:
`configure / intent / route / retrieve / observe / synthesize / stop` and a
`native_or_normalized` marker. Codex rollout JSONL and self-built spans are mapped
to that profile before comparison.

The old five-case Codex receipt is normalized first.  Because its raw rollout
events and the paired Workbench traces were not retained, the audit records
`not_evaluable` rather than manufacturing a first divergence.  A future live
pair is eligible only with the same PIT fixture/cutoff and native events on both
sides; SDK migration is discussed only after such data exists.

## 4. Error handling and safety

- Frozen source artifacts are read-only. Replay output always goes to an explicit
  path outside the run directory.
- Provider/configuration failure is distinct from timeout and from invalid model
  output.
- No artifact stores credentials, request headers, internal paths beyond the
  explicitly supplied run directory, or estimated token counts.
- The launchd-owned runtime is not restarted, killed, or replaced manually.
- No merge to `main` and no force-push occur.
- Before each commit, risk-file and secret scans cover staged paths.

## 5. Verification

- Replay unit tests mock the provider and assert the exact production prompt
  builders are used.
- Health-gate tests cover full pass, threshold failure, unknown, missing/broken
  files, empty runs, invalid ratios, and legacy report compatibility.
- T1 measurement artifacts bind to SHA-256 hashes of frozen inputs.
- T3 has deterministic brief unit tests, budget tests, and one live A4 canary.
- T4 publishes normalized traces and an evidence-to-finding report.

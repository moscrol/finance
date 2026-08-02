# Acceptance Completion Loop Design

## 1. Goal

Complete every autonomous item in the 2026-08-01c/d handoff without changing the
sealed 28-case canon or publishing the branch:

- preserve the completed #13/#14 verdict work;
- establish one trustworthy B/C baseline;
- expose delivery, information value, and credibility as separate acceptance axes;
- prove whether the exposure selector reacts to intent;
- make A2's synthesis degradation reason observable;
- produce an executable, provenance-bound Knevo comparison;
- leave decision packages for K, A8/C6 root repair, Codex authentication, and J.

The branch remains `fix/exposure-ranking-truncation`. Work is committed locally only.
`origin/main`, the production 8792 runtime, and the sealed canonical case file are out
of scope.

## 2. Invariants

1. `acceptance_cases.json` remains byte-for-byte unchanged and continues to match
   `CANONICAL_CASES_SHA256`.
2. Board rendering is deterministic and consumes only stored artifacts. It never calls
   an LLM, a data provider, or the product runtime.
3. Operational completion, truth, information value, and human experience remain
   separate accounts. One cannot silently substitute for another.
4. Missing evidence is rendered as `not evaluated`, never as pass or zero.
5. Every semantic or comparative sidecar is bound to its run, cases, overlay, rubric,
   references, and its own canonical hash. A mismatch fails closed.
6. B/C live execution is performed once after the measurement seams are ready. C6 is
   reported as non-reproducible by the existing #13 detector, not repaired by mutating
   the case.
7. Existing unrelated test and lint failures are reported by exact identity and count;
   no threshold is relaxed to create a green result.

## 3. Run aggregation

### Problem

The board currently reads only the lexically latest run file. A B-only run would make
the completed A baseline disappear, and a later C-only run would hide both A and B.

### Design

Add a run-catalog seam that scans every valid run JSON in `intelligence/eval/runs/`.
For each case it selects the newest occurrence by:

1. `generated_at` inside the artifact;
2. filename stem as the deterministic tie-breaker.

The selected record carries `run_path`, `run_sha256`, `generated_at`,
`preflight_ok`, and `preflight_detail`. The board displays a compact source marker per
case and reports the number of contributing run artifacts. Malformed run artifacts are
rejected rather than partially merged.

Explicit truth/experience sidecars remain single-run artifacts. Therefore the board
may load them only for cases whose selected source is that same run. Cross-run
sidecars require one artifact per contributing run; no observation is silently applied
to a different answer.

## 4. Three-axis projection

The axes implement the handoff equation:

`answer value = delivery × information × credibility`

### Delivery

Delivery is a deterministic projection of the operational verdict:

- `pass`: completed without degradation;
- `partial`: completed with explicit degradation;
- `fail`: blocked, failed, or no output;
- `not_run`: no selected run.

Delivery explains whether an answer arrived. It does not claim that the answer was
correct.

### Credibility

Credibility is a deterministic projection of the existing truth verdict:

- `pass`: all required truth rules pass;
- `fail`: at least one required rule fails;
- `unjudgeable`: required typed evidence is missing or the case is non-reproducible;
- `not_run`: no selected run.

This keeps the stricter domain gate intact.

### Information value

Information value is a separate observation axis with four states:

- `workbench_wins`;
- `tie`;
- `knevo_wins`;
- `not_evaluated`.

It is not inferred from word count, citation count, or truth. A semantic evaluator
must compare the stored Workbench answer against an eligible frozen Knevo snapshot
using a frozen rubric. The resulting comparison sidecar records:

- directness toward the task;
- number and specificity of usable judgments;
- decision structure, such as scenarios, ranking, causal chain, and invalidation;
- unsupported-detail penalty;
- winner and concise rationale.

The comparison does not enter the board until its hashes and eligibility prove that
the exact answers were compared. The repository supplies a deterministic builder and
validator; model execution, when available, happens as a separate explicit command and
its result remains frozen. Existing manually audited comparison judgments may be
imported only when they identify a matching acceptance case and both answer hashes.

Codex is not an information-value oracle in this phase because there are zero Codex
snapshots. Its missing state remains explicit.

## 5. A2 synthesis diagnostics

### Problem

The runtime trace currently emits only `validated` or `fallback`. `fallback` conflates:

- synthesis disabled by route;
- no prepared messages;
- grounded presenter retained the deterministic answer;
- provider failure;
- semantic/structural gate rejection;
- candidate claims that could not bind to evidence.

A2 consequently exposes a generic 232-character fallback and a generic degrade message,
although its actual failure is that a candidate direct answer exists but its claim is
not bound.

### Design

Introduce a typed `SynthesisDiagnostic` carried by `AskResult`, with:

- `state`: `not_requested`, `not_prepared`, `attempted`, `accepted`, or `rejected`;
- `reason_code`: stable machine-readable reason;
- `detail`: bounded non-secret explanation;
- `prepared_message_count`;
- `candidate_claim_count`;
- `bound_claim_count`;
- `provider`;
- existing stream telemetry.

Every early return or failure boundary in synthesis sets the diagnostic at the point
where the reason is known. The orchestrator trace emits it under
`synthesize.answer_synthesis`; public degradation text may use its safe detail but must
not expose prompts, credentials, internal paths, or evidence bodies.

The acceptance runner stores the relevant trace event in `TurnTrace`, allowing the
board to explain A2 from structured telemetry. If old runs lack this field, the board
renders `diagnostic unavailable` rather than guessing from prose.

## 6. Selector resolution experiment

### Question

For the same `固态电池` candidate universe, does the selector produce meaningfully
different companies for different intents, or merely repeat static candidate order?

### Controlled prompts

Use at least four predeclared intents:

- `产业链里谁最受益，为什么`;
- `谁在扩产，扩产证据是什么`;
- `原材料降价时谁的利润弹性最大`;
- `谁最可能率先形成收入兑现`.

The candidate pool, limit, model, code revision, and data revision are frozen across
the matrix.

### Artifact and metrics

Add a deterministic selector-experiment artifact containing each prompt's selected
ordered company list plus existing telemetry and evidence coverage. The summary reports:

- pairwise Jaccard overlap;
- top-k rank-biased overlap;
- number of distinct ordered lists;
- union size across prompts;
- LLM-selected, backfilled, and hallucinated counts;
- selected-versus-pool evidence-coverage medians.

Interpretation:

- all ordered lists identical is a failed resolution signal;
- different ordering with high set overlap is weak resolution;
- meaningful set and rank changes with zero hallucinations is positive resolution;
- provider fallback makes the experiment inconclusive, not failed.

This experiment is diagnostic only. Evidence coverage remains read-only and does not
enter ranking or the selector prompt.

## 7. Live B/C baseline

After measurement code and server diagnostics are committed:

1. restart canary 8793 because synthesis diagnostics change server-side code;
2. verify PID, cwd, `PYTHONPATH`, RAG variables, health, and absence of bind errors;
3. run `mid_freq` once;
4. run `long_tail` once;
5. render the aggregated board;
6. freeze a verification receipt with run hashes and per-case source mapping.

C6 must be `unjudgeable` due to the known reproducibility diagnostic. Any different
classification is a regression in the harness.

No live rerun is used to tune the judge after seeing answers. Product fixes discovered
by the baseline become a later, separately designed task.

## 8. Reference comparison

The executable comparison path has three layers:

1. deterministic eligibility and hash validation;
2. frozen rubric and prompt generation for each eligible Workbench/Knevo pair;
3. import and validation of evaluator output into the information-value sidecar.

The command must support dry-run prompt generation without credentials. If a configured
model is available, it can execute eligible comparisons once and freeze provenance.
Otherwise it still produces a complete comparison queue that another authenticated
runner can execute without reconstructing context.

Cases with missing Knevo snapshots, non-independent aliases, or known temporal mismatch
are excluded by `acceptance_reference_eligibility.json`. A8/C6 references cannot become
eligible until their case-date decision is made.

## 9. Decision packages

Create one handoff section with explicit choices and blast radius:

- **K:** keep L2 independent by running it before the finalize sync guard, or accept the
  new dependency and narrow the invariant. Recommendation: keep L2 independent.
- **A8/C6:** preserve the sealed case and retain unjudgeable status, or break the seal,
  insert absolute dates, rotate the hash, and invalidate/re-freeze references.
  Recommendation: repair in a dedicated benchmark-version migration.
- **Codex:** reauthenticate the ChatGPT app sidecar, then freeze 28 external snapshots;
  never manufacture them from the tested runtime.
- **J:** deterministically append truncation/selection disclosure to final prose, using
  the existing `ensure_chain_mapping_section` pattern. Recommendation: implement in a
  separate user-visible behavior change after the baseline.

These packages do not modify production behavior in this loop.

## 10. Tests and completion evidence

Required evidence:

- unit tests for cross-run selection, malformed artifacts, source hashes, sidecar
  mismatch, three-axis projections, synthesis diagnostic transitions, and selector
  metrics;
- mutation checks for every new fail-closed guard;
- exact canonical case SHA256 unchanged;
- existing acceptance verdict suite remains green;
- full pytest failure identities match or improve on the known baseline;
- Ruff failure count and identities match or improve on the known baseline;
- B/C run artifacts exist, pass preflight, and appear with A in one aggregated board;
- selector experiment artifact is reproducible from its frozen inputs;
- reference comparison queue/result is hash-bound and includes no unsupported Codex
  comparison;
- all commits remain local to `fix/exposure-ranking-truncation`.

## 11. File boundaries

- `intelligence/eval/acceptance_runs.py`: run catalog and per-case source selection.
- `intelligence/eval/acceptance_axes.py`: three-axis typed projection.
- `intelligence/eval/acceptance_comparison.py`: comparison queue, rubric binding, and
  result validation.
- `intelligence/eval/selector_resolution.py`: controlled selector experiment and
  deterministic metrics.
- `intelligence/eval/acceptance.py`: CLI wiring and board presentation only.
- `intelligence/services/ask_types.py`: typed synthesis diagnostic.
- `intelligence/services/ask_synthesis.py`: synthesis boundary reason assignment.
- `intelligence/services/conversation_orchestrator.py`: diagnostic trace projection.
- focused tests live beside existing acceptance, synthesis, and exposure selector
  suites.

The new modules keep policy and integrity rules out of the CLI renderer and avoid
growing `acceptance.py` into another orchestration monolith.

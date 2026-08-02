# Acceptance Observation Sidecars Design

Date: 2026-07-29
Status: approved by the active final-goal handoff and no-human-loop authorization

## Goal

Let calibrated semantic truth observations and blind experience labels feed the typed
acceptance verdict seam without editing frozen run artifacts, frozen reference snapshots, or
the canonical case file.

## Alternatives

1. **Write labels back into each run.** Simple, but destroys immutable evidence and lets a later
   evaluator silently change history. Rejected.
2. **Put labels in `acceptance_cases.json`.** Mixes expected behavior with observed results and
   contaminates every future run. Rejected.
3. **Hash-bound sidecars.** Chosen. A sidecar is valid only for one exact run, case contract,
   verdict overlay, evaluator, and rubric/prompt. Truth and experience remain separate files.

## Seam

Create `intelligence/eval/acceptance_observations.py` with one deep public loader:

```python
load_observation_artifact(
    path,
    *,
    run_path,
    cases_path,
    overlay_path,
) -> ObservationArtifact
```

The loader verifies self-hash, source hashes, case IDs, allowed rule IDs, evaluator provenance,
and axis-specific payload shape. `evaluate_case(..., observations=...)` consumes only the
validated per-case projection.

The board accepts explicit `--truth-observations` and `--experience-labels` paths. It never
auto-discovers the newest file, because “newest” is not provenance.

## Artifact types

### Truth observation

`artifact_kind=acceptance_truth_observations` contains rule-level observations only for rules
that the deterministic trace cannot finish, such as `pass_rule`, `answer_set`,
`inherited_golden`, or full `cross_turn_consistency`.

Every observation records state, reason, evidence references, evaluator id/kind, model when
applicable, rubric hash, and creation time. A semantic judge cannot override a deterministic
hard failure; aggregation still uses “any hard fail wins.”

### Blind experience label

`artifact_kind=acceptance_experience_labels` contains eligible/ineligible plus a blind label:
`workbench`, `reference`, or `tie`. It records blinded pair id and rubric hash, but not a backend
identity visible to the reviewer. Identity unblinding stays in a separately sealed manifest.

Experience labels never set truth state or product release status.

## Integrity contract

The artifact includes:

- format version and artifact kind;
- source run relative path and SHA-256;
- canonical case-file SHA-256;
- verdict-overlay SHA-256;
- evaluator identity/kind/model and rubric hash;
- per-case observations;
- `artifact_sha256`, calculated over canonical JSON with that field omitted.

Unknown cases, duplicate axes, invalid states, missing reasons, unrecognized rule IDs, hash
mismatch, or a sidecar bound to a different run fail closed. The original answer text is not
copied into a sidecar.

## Reference eligibility

Knevo snapshots are not loaded as truth labels automatically. Their `use_as`, hindsight,
local-definition, reconstructed-data, and alias caveats first compile into a typed eligibility
manifest. A future blind-label artifact must name the exact eligible dimensions. Missing six
snapshots remain missing; aliases do not create a second independent answer.

## Tests

- valid self-hashed truth and experience artifacts load;
- any source/self hash mutation is rejected;
- unknown case/rule/state and missing provenance are rejected;
- board remains unchanged without explicit sidecars;
- sidecar truth can resolve an unjudgeable rule but cannot erase a deterministic failure;
- experience labels remain independent of truth;
- frozen cases, runs, and references stay byte-identical.

## Non-goals

- no semantic model call in this slice;
- no invented blind labels;
- no automatic Knevo win rate;
- no live 28-case run;
- no App Server implementation or canonical rollout.

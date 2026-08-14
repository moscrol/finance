# Acceptance Observation Sidecars Verification

Date: 2026-07-29
Status: deterministic observation seam complete; semantic and blind labels not yet collected

## Provenance

- Worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
- Branch: `feat/agent-runtime-backends-verify`
- Design/plan commit: `4dc941f7`
- Implementation commit: `8126bbf7`
- Python: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`

Pinned inputs after implementation:

```text
acceptance_cases.json:                 a25c68253a92be536b94d2403ffa010b6cd15a20b7eea581450159cb6444a1c6
acceptance_verdict_contracts.json:     825fa603c252dfd950f2ce5c8e9edbb351dda4ef48f49e214f4329cea3e09e6e
acceptance_reference_eligibility.json: 37906db20d6be2f35b4390fdf6846707daa63e6f7d4f29d407f96557d97eaba2
historical run 20260727T032229Z:       e66642565587adf070b716b6858b2861c92a7f52a995c3a8bff140cad63b33d5
```

The implementation diff did not edit the canonical case file, any committed run, or any
reference snapshot.

## Implemented contract

`intelligence/eval/acceptance_observations.py` is the single loader for external acceptance
judgments. A sidecar is accepted only when it proves all of the following:

- its canonical self-excluding SHA-256 is valid;
- its run, case-file, and verdict-overlay hashes match the selected board inputs;
- every labeled case is present in that exact run;
- evaluator identity, evaluator kind, optional model, independence flag, and rubric hash are
  explicit;
- truth artifacts contain only externally judgeable rule observations with valid evidence
  references into the frozen run;
- experience artifacts contain only an eligible blind comparison and bind the exact Knevo
  eligibility manifest, snapshot hash, sealed pair manifest, run hash, reviewer, and dimensions.

The board loads sidecars only from explicit CLI paths. It never auto-selects a newest artifact.
Any provenance mismatch fails before the table is rendered.

`evaluate_case(..., observations=...)` preserves the decisive invariant: an external semantic
pass can resolve an otherwise unjudgeable prose rule, but it cannot erase a deterministic hard
failure. Blind preference remains on the experience axis and cannot change truth or release
status.

## Knevo eligibility inventory

The new manifest accounts for all 28 frozen cases without treating 22 snapshots as a uniform
denominator:

```text
22 snapshots present
6 snapshots missing: A8, A9, B6, C3, C4, C8
truth/experience status combinations:
  eligible / eligible     3
  ineligible / ineligible 1
  ineligible / limited    5
  limited / eligible     11
  limited / ineligible    1
  limited / limited       1
  missing / missing       6
```

Aliases and hindsight/reconstruction/local-definition caveats stay case-specific. The manifest
does not create truth labels, blind labels, or a Knevo win rate.

## Verification

Focused sidecar, verdict, board, and semantic-acceptance tests:

```text
56 passed in 0.11s
```

Static and integrity checks:

```text
Ruff: all checks passed
git diff --check: passed
eligibility JSON/schema/hash probe: passed, 28 cases / 22 snapshots / 6 missing
```

Full intelligence suite with the three production userspace path overrides removed from the
test process:

```text
2993 passed, 14 failed, 2 skipped in 79.34s
```

All 14 failures are the known managed-sandbox prohibition on binding a loopback socket:

- 2 in `test_codex_headless_runtime.py`;
- 12 in `test_headless_tool_gateway.py`.

Every failure is `PermissionError: [Errno 1] Operation not permitted` at `socket.bind()` and
does not exercise the changed sidecar surfaces. The first unfiltered collection attempt also
confirmed why the three userspace overrides must be removed for tests: their inherited SQLite
path is outside this sandbox and fails before collection. No production configuration was
changed.

## Honest boundary

This part built a tamper-evident measurement input, not favorable measurements. It generated no
semantic truth observation, no blind preference label, no new live answer, and no release
claim. The final product goal remains active and proceeds next through a minimal live judge
readiness probe, the preregistered A/B/C/D headless experiment when its local route is legally
available, and only then the App Server decision gate and wider board.

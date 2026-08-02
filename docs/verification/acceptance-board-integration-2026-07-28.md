# Acceptance Board Integration Verification

Date: 2026-07-28
Status: integrated and deterministically verified; no live acceptance cases run

## Provenance

- Source line: `eval/acceptance-board`
- Source tip: `8279b2bd67faf0e8a2adc570dadaa8482c973b53`
- Source merge base with the runtime line:
  `0430d54471cf40cd4d24061d4adc54255350eaf5`
- Imported source range: `f03b66e5^..8279b2bd`
- Import method: ten ordered commits cherry-picked by object SHA; no branch-name
  lookup, fetch, or additional remote was used.
- Runtime branch: `feat/agent-runtime-backends-verify`
- Imported-content tip after the ordered cherry-pick:
  `9554d62db61042c37a02cb3f62325e9979c7d90e`

`git diff --exit-code 8279b2bd HEAD -- <acceptance asset paths>` returned no
differences immediately after import. The frozen cases, answers, hashes,
`asked_at`, collection routes, snapshot caveats, and historical traces therefore
match the source tree byte for byte.

## Integrated assets

- 28 cases: 10 `high_freq`, 8 `mid_freq`, and 10 `long_tail`.
- `intelligence/eval/acceptance.py` real Conversation API runner and board.
- `intelligence/eval/cases/acceptance_cases.json` canonical case definition.
- 22 immutable Knevo snapshots under
  `intelligence/eval/cases/reference_snapshots/`.
- Two historical runs:
  - `20260727T025642Z.json`: 1 case / 1 turn;
  - `20260727T032229Z.json`: 10 cases / 12 turns.
- `intelligence/tests/test_acceptance_board.py`.
- Q13/Q14/Q15 methodology material and its question-bank bindings.

The six cases without Knevo snapshots remain intentionally missing:

```text
A8-market-stage
A9-sentiment-contradiction
B6-sellside-distillation
C3-empty-table
C4-unit-anomaly
C8-nonexistent-table
```

No reference was generated or purchased to fill those gaps.

## Verification

```text
test_acceptance_board.py + Workbench API + RunStore + ConversationStore
177 passed
```

The read-only board command successfully loaded the imported latest historical
run and reported:

```text
28 total
18 not run
0 no-output
6 degraded answers
4 answers pending judgment
22 / 28 reference snapshots
```

Both historical run files contain no `passed` field. Their pass rate is
therefore **unknown**: it is neither `0/28` nor the count of answered turns.
`aggregate_gate=0.0` remains observational until the verdict compiler and rubric
are calibrated and a non-zero threshold is preregistered.

## Scope boundary

- No acceptance question was executed during integration.
- No frozen answer, hash, caveat, case contract, or gate was rewritten.
- No App Server code was implemented.
- `main`, 8792, and 8799 were not changed.


# Adaptive Runtime Sealed Fixture Task 2 Handoff

Date: 2026-07-29
Status: **Task 2 code complete; real fixture leak gate rejected; final goal active**
Worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Branch: `feat/agent-runtime-backends-verify`
Task 2 commit: `9f9b2ae5`

## Final goal

Deliver an adaptive finance research agent that approaches the useful autonomy of
interactive Codex while preserving stronger finance controls: point-in-time data,
fresh true-Hybrid evidence, numeric lineage, fail-closed budgets, honest partial
answers, deterministic acceptance accounting, and replayable artifacts.

The stopping condition is not a phase document or one green case. It is:

1. the sealed five-case profile-D headless control is valid;
2. an App Server ceiling run is allowed only after provider-executed identity is
   observable and is run against the exact same sealed fixture;
3. truth and experience are independently judged without overwriting hard failures;
4. the broader 28-case board and matched Knevo comparison have valid denominators;
5. release gates are green before any `main` merge or 8792 switch.

## Completed and committed

### Product/runtime foundation

The candidate already contains same-Episode repair, dynamic/root budget control,
cutoff propagation, evidence ledger and retrieval telemetry, true-Hybrid freshness,
causal target-window/counter-evidence guards, subject-local valuation admission,
three-axis acceptance verdicts, and hash-bound external observation sidecars.

### Budget diagnosis and App Server decision gate

The corrected A/B/C/D budget ablation is complete. It found wall-clock room primary
and the six-call cap secondary. App Server v3 and its mailbox amendment have passed
independent review, but no App Server runner has been implemented because the current
binary cannot attest provider-executed identity.

Relevant commits:

```text
9f0d839f docs: harden app server experiment v3
b1318e00 docs: close app server v3 review gaps
c0ac43fc docs: seal app server v3 spec pass
27f0ee76 docs: plan sealed fixture and headless control
345fbecd docs: tighten sealed mailbox preflight
fb58efde docs: seal mailbox amendment pass
```

### Sealed fixture Task 1

`e96226b5 feat: freeze ceiling fixture leakage scan` implements:

- NFKC/case-fold/punctuation-free character normalization;
- Han/alphanumeric tokenization;
- deterministic full, character n-gram, token n-gram, and Jaccard checks;
- semantic near-match candidate receipts;
- forbidden-corpus loading from questions, references, prior answers, and
  post-cutoff documents;
- hash-bound independent `gpt-5.6-sol` semantic-review receipts.

## Sealed fixture Task 2

`9f9b2ae5 feat: build sealed instruction export` implements:

- an explicit production-only allowlist and evaluator/docs/test exclusions;
- a neutral generated root `AGENTS.md` with PIT and read-only rules;
- immutable reads from `git ls-tree` plus `git cat-file --batch`;
- rejection of symlinks/submodules and create-if-absent writes;
- regular-file, link-count, permission, content-hash, file-set, and mutation audits;
- a content-addressed private control manifest bound to the deterministic scan.

The tamper audit now recomputes the scan payload's canonical hash rather than merely
comparing two stored hashes. Missing, symlinked, non-directory, and empty export roots
also fail closed. The committed focused result is `18 passed`; Ruff and diff checks
pass. Task 2 is complete as a code slice.

## Performance diagnosis completed during Task 2

A real staging export contained 312 files, about 5 MB and 112,787 lines. Scanning
it against 84 forbidden entries deterministically exceeded five seconds. The cause
was repeated normalization/tokenization/n-gram work for every sentence-entry pair.

A regression test now proves forbidden text is precompiled once. The implementation
precomputes forbidden character streams, token sets, and n-grams, and computes each
candidate sentence once. The focused performance invariant changed from red
(`720` normalization calls against an upper bound of `84`) to green.


The regenerated real probe finished in about 4.4 seconds and scanned 312 files, so
the performance regression is closed. It correctly did not produce a sealed receipt:
the deterministic scan rejected the current allowlisted tree with 1,851 findings and
recorded 511 semantic candidates.

## Current real-fixture red gate

The largest observed class is not an obvious copied benchmark answer. Short and
generic `required_output` and `expected_fact` entries are treated as unrestricted
full-string matches, so ordinary runtime and finance vocabulary triggers the gate.
Even the neutral generated `AGENTS.md` matches several short required-output entries;
`UBIQUITOUS_LANGUAGE.md`, `intelligence/README.md`, and production service files account
for many more. The current result therefore mixes possible real leakage with clear
common-vocabulary false positives.

Do not silence these findings with a blanket exclusion or by raising all thresholds.
First produce a breakdown by source kind, normalized length, rule, and file. Then
preregister a kind-aware rule that preserves exact long question/reference detection,
12-character and 6-token overlap detection, and strict identifier matching while
preventing short generic rubric fragments from acting as substrings everywhere.

The worktree also contains an untracked
`intelligence/tests/test_ceiling_pit_fixture.py` created during concurrent Task 3
work. It was not created, reviewed, staged, or committed by this handoff and must be
preserved until its owner/scope is verified.

The last proportional committed gate before this WIP was green. The latest recorded
full suite was `2993 passed, 14 failed, 2 skipped`; all 14 failures were reproduced
managed-sandbox loopback-bind failures, not changed-surface regressions.

## Exact continuation order

1. Add a diagnostic receipt/test for leak counts by source kind, normalized length,
   rule, and file; identify which hits are true gold versus generic vocabulary.
2. Amend the deterministic leak rule with tests and independent spec review. Keep
   long question/reference, n-gram, identifier, and semantic-review protections;
   do not loosen the gate merely to obtain green.
3. Regenerate the real export from an immutable commit. Require `files_scanned > 0`,
   deterministic pass, preserved semantic candidates, and a valid final audit.
4. Verify ownership of the untracked PIT test, then implement Task 3, the physical
   cutoff-filtered finance DuckDB, with conservative
   temporal-column policy and post-build future-row audit.
5. Implement Task 4, a regular-blob cutoff Wiki export plus fresh true-Hybrid index,
   using KB code `9053b0c4` in isolation and explicit `KB_RAG_PYTHON`.
6. Implement the private fixture CLI, build the real fixture, obtain one independent
   semantic-leak review, seal it, and run proportional regression.
7. Run the same-fixture five-case profile-D headless control via the approved mailbox
   boundary. Do not substitute dry-run output for live evidence.
8. Only if provider-executed identity becomes observable, implement the bounded App
   Server ceiling runner against the identical fixture; otherwise record it as
   ineligible rather than guessing.
9. Complete truth/experience observations, matched Knevo artifacts, the 28-case
    acceptance board, and final release decision.

## Optimization directions

### P0: Fixture integrity and PIT correctness

- Every control receipt must be self-hashed and independently recomputed on audit.
- Leak detection must distinguish long gold text, strict identifiers, and short
  generic vocabulary without allowing any one class to fail open.
- Empty roots, missing files, symlinks, hardlinks, mutation, stale indexes, future
  rows, and unknown temporal schemas must fail closed.
- The finance DB and Wiki must be physical cutoff exports, not prompt-only cutoff.

### P1: Quality under realistic latency

- Keep fast-answer and deep-research latency contracts separate.
- Measure repeated capability use, evidence gain per call, and target-window coverage;
  more calls are not progress when evidence does not improve.
- Preserve honest partial answers with precise gaps instead of relaxing gates.

### P1: Generic-harness value without losing domain controls

- Use the same fixture and published-answer projection for headless and App Server.
- Let the runtime improve tool discovery and continuation, but retain cutoff,
  EvidenceLedger, freshness, numeric lineage, and invalid-action enforcement outside
  model discretion.

### P2: Acceptance and comparison

- Keep operational, truth, and experience axes separate.
- Convert every reviewer finding into a permanent deterministic test when possible.
- Split Knevo comparison into truth dimensions and experience dimensions; do not
  publish a win rate until matched artifacts and valid per-dimension denominators exist.

## Progress model

| Layer | Status |
|---|---|
| Runtime architecture and fixed-case deterministic seams | candidate complete |
| Acceptance/provenance measurement | complete |
| Corrected budget ablation | complete |
| App Server v3 design and mailbox amendment | independent PASS |
| Sealed fixture | Tasks 1-2 committed; real export rejected by over-broad leak matches; Tasks 3-7 pending |
| Same-fixture five-case headless control | pending sealed fixture |
| App Server ceiling execution | blocked by unobservable provider identity and control prerequisite |
| 28-case/Knevo final board | pending |
| Main merge / 8792 rollout | not authorized |

The useful engineering candidate remains roughly 90% complete. End-to-end product
release remains roughly 70% because sealed comparative evaluation, the 28-case board,
and rollout are intentionally unfinished. These percentages use different denominators
and must not be collapsed into one number.

## Non-negotiable boundaries

- Do not merge `main`, switch 8792, or merge KB `9053b0c4` without authorization.
- Do not implement App Server runner/live while execution identity is unobservable.
- Do not weaken cutoff, freshness, EvidenceLedger, invalid-action, or semantic gates.
- Do not add per-question routes/templates.
- Use `gpt-5.6-sol` for authorized semantic/live work.
- Do not commit keys, databases, indexes, model weights, logs, caches, or virtualenvs.
- A handoff or phase completion is not the final stopping condition.

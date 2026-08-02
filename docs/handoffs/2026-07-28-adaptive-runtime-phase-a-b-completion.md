# Adaptive Runtime Phase A/B Completion Handoff

Date: 2026-07-28
Status: authorized handoff scope complete; Phase C entry reached
Branch: `feat/agent-runtime-backends-verify`
Working copy: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Pre-handoff documentation tip: `2ffa4c770e2f40558fe52205c32fb47921b040e7`
Canonical 8792 / `main` / 8799: unchanged

## Goal that was executed

Complete the bounded scope in the canonical handoff and execution brief:

1. make the benchmark use the same Adapter-owned repair, verification, and
   public projection path as the Workbench;
2. separate SDK deadlines from invalid protocol actions;
3. integrate the existing 28-case acceptance board and 22 Knevo snapshots by
   source SHA, without rebuilding or running the suite;
4. make the four-cell headless budget experiment physically exercisable and
   preregister it in writing;
5. stop at the Phase C entry without implementing App Server, merging `main`,
   switching 8792, changing gates, or running the 28 cases.

That scope is complete. It does not mean the final product is already proven
Codex-like or stronger than Knevo.

## Completed work and authoritative evidence

### Phase A1 — benchmark/product parity

Commits:

```text
9b4088d4 fix: benchmark production arms through continuous adapter
```

- Research arms now execute through `ContinuousTurnAdapter.handle()` rather
  than calling runtime and verifier paths directly.
- The benchmark observes the typed semantic outcome but does not make a second
  gate decision.
- Public answer, status, citations, and cutoff come from `turn_result`, so the
  Adapter remains the sole public-projection owner.
- A real `CallbackEpisodeSession` regression proves timeout-with-evidence can
  re-enter the same Episode and complete delivery repair.
- A control-token regression proves semantic `completed/passed` can still be
  publicly degraded and that unsafe citations do not enter the artifact.
- The first independent spec review found the duplicate public status/citation
  projection; both P1 findings were fixed and the re-review passed.

### Phase A2 — typed failure accounting

Commit:

```text
ab9bba05 fix: separate sdk deadlines from invalid actions
```

- `sdk_timeout` retains its status, gap, stop reason, and repair behavior but
  now records `invalid_actions=0`.
- `sdk_invalid_finish` continues to record `invalid_actions=1`.
- Infrastructure/resource failure is no longer misreported as a model protocol
  violation.

### Phase A verification

```text
benchmark + SDK + Adapter + benchmark contract + semantic verifier
254 passed, 1 skipped

full intelligence suite at the Phase A boundary
2947 passed, 2 skipped
```

The external code-quality reviewer later failed before review because its local
proxy at `127.0.0.1:1082` was unavailable. This was not treated as a PASS. A
manual diff/risk review plus Ruff, `git diff --check`, focused tests, and the
full suite were used to continue; the successful independent spec review is
recorded separately above.

### Phase A.5 — acceptance assets integrated, not rebuilt

Source identity:

```text
source tip  8279b2bd67faf0e8a2adc570dadaa8482c973b53
merge base  0430d54471cf40cd4d24061d4adc54255350eaf5
range       f03b66e5^..8279b2bd
```

Ten commits were cherry-picked in order by object SHA. No branch-name lookup,
fetch, or new remote was used. The imported-content tip is `9554d62d` and the
pinned verification note is commit `d0cf97a1`:

- [acceptance-board integration verification](../verification/acceptance-board-integration-2026-07-28.md)
- 28 cases: 10 high-frequency / 8 mid-frequency / 10 long-tail;
- 22 immutable Knevo snapshots;
- two historical runs: 1 case/1 turn and 10 cases/12 turns;
- six deliberately missing snapshots: A8, A9, B6, C3, C4, C8;
- source and integrated asset paths were byte-identical after import;
- board/API/Run-store/Conversation-store verification: `177 passed`.

The historical board reads successfully and reports 18 not run, 6 degraded,
and 4 answered-awaiting-judgment in its latest stored run. Neither run contains
a `passed` field. The current 28-case pass rate remains **unknown**, not 0/28 and
not 12/28.

### Phase B — executable preregistration, no live run

Code commit:

```text
803367f1 feat: preregister headless budget profiles
```

Preregistration commit:

```text
2ffa4c77 docs: preregister headless budget ablation
```

- Added a benchmark-only typed budget profile and explicit DI seam; production
  tier defaults still use the 0.65 gateway ratio.
- `--case` selects the three frozen diagnostic cases without copying them into
  a new suite.
- The artifact records the exact profile.
- D requires at least seven observed calls; otherwise the artifact records
  `invalid_not_physically_exercised` instead of a quality failure.
- Headless gateway/runtime/benchmark focused verification:
  `45 passed, 1 skipped`.
- `T_long=180s` is derived from p90 9.088-second inter-result latency rather
  than guessed.
- Four plan artifacts were generated from clean revision `803367f1`; all have
  exactly three cases and `budget_ablation_validity=not_executed`.

Full contract, commands, hashes, artifact paths, and interpretation rules:

- [headless budget ablation preregistration](../verification/headless-budget-ablation-preregistration-2026-07-28.md)

No live A/B/C/D output has been observed, so no budget-causality conclusion is
claimed.

## Final deterministic verification

After Phase A.5 and Phase B code were both present:

```text
full intelligence suite
2966 passed, 2 skipped in 94.20s
```

Ruff and `git diff --check` passed for every changed code slice. No `.env`,
credential, database, PDF, archive, cache, private-memory, or generated live
benchmark artifact was committed.

## Executed facts versus remaining hypotheses

### Proven by execution

- benchmark and Workbench research arms share Adapter-owned repair,
  verification, and public projection;
- SDK timeout and invalid-finish accounting are distinct;
- the 28 cases, 22 snapshots, historical traces, and board are integrated and
  readable on the runtime line;
- the four budget cells are representable, recorded, and D can mechanically
  detect failure to reach the call-cap treatment;
- production defaults remain unchanged when no profile is supplied;
- the complete offline test suite is green.

### Still unproven or intentionally not executed

- whether A→B, B→C, or C→D improves live answer quality;
- whether budget is the only or dominant remaining quality cause;
- the 28-case Workbench pass rate and normalized Knevo truth/experience score;
- which of `/Users/a77/知识库/wiki` and
  `/Users/a77/knowledge-base-private/wiki` should be canonical;
- whether valuation stops because evidence is sufficient or because completion
  and verifier judgments disagree;
- whether weekly-cause failure is index recall, slow evidence search, repetitive
  strategy, cutoff filtering, or an overloaded causal contract;
- whether native Codex App Server adds value after fair-budget control;
- any canonical release, 8792 rollout, `main` merge, or legacy deletion.

## Exact Phase C entry

Do not begin by adding another wiki tool or route. The next deterministic slice
is:

1. **Pin evidence identity.** Prove the two Wiki roots are not aliases; record
   each Git revision, index path, index freshness, and selected key-file hashes.
2. **Pin capabilities.** Generate a dry-run artifact from a clean revision that
   contains the actual contract and allowed capabilities; do not infer them
   from historical `contract=null` artifacts.
3. **Replay tools directly.** Run `evidence_search` for 瑞华泰 and the weekly
   causal query against the same PIT root/index, recording latency, candidates,
   cutoff filtering, and returned evidence atoms.
4. **Classify the gap.** Separate index recall, tool latency/result quality,
   model tool selection, repeated strategy, and completion/verifier mismatch.
5. **Keep answer classes separate.** For the weekly case, distinguish premise
   correction, market-internal mechanism, unique external catalyst, and honest
   unavailability of direct catalyst evidence.

The preregistered live A/B/C/D experiment may be executed sequentially before
or alongside that Phase C diagnosis only under its frozen contract. If live
spend is deferred, say so; do not claim the budget hypothesis was tested.

## Hard boundaries retained

- Do not run all 28 cases until the shared retrieval/completion seams and
  verdict compiler are ready.
- Do not implement App Server from the currently `CHANGES_REQUIRED` design.
- Do not tune gates or frozen answers to observed output.
- Do not merge `main`, switch/restart 8792, treat 8799 as canonical, or delete
  the legacy path without explicit user approval.
- Do not restart Phase A or rebuild the acceptance board from memory.


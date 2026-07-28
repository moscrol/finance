# Phase C Part 1 Handoff — Wiki Identity

Date: 2026-07-29  
Status: **Part 1 complete; continue from the freshness seam, not from a new benchmark**  
Worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`  
Branch: `feat/agent-runtime-backends-verify`  
Identity evidence commit: `344b48b1420286fc1eb4102e7305d62c463aa014`  
Parent execution revision: `342be37878d7d8e07dd7ccf7bcb5f1efce0f4079`

## What this handoff answers

The first Phase C question was not “which directory has a page named 瑞华泰?”
It was “which exact Wiki and index snapshot are we measuring?” Two directories
can contain the same important page and still be different evidence universes.
This slice fixed that identity question before any model or retrieval score is
interpreted.

## Decision

Use this as the canonical **root path** for the remaining Phase C diagnosis:

```text
/Users/a77/knowledge-base-private/wiki
```

Use its format-2 structured index as the canonical **index candidate**:

```text
/Users/a77/knowledge-base-private/.rag_index
```

Do not use `/Users/a77/知识库/wiki` for the new replay, and do not use
`/Users/a77/knowledge-base-private/.rag_index_full` as the structured baseline.
The full evidence table, hashes, and command outputs are in:

[`phase-c-part-1-wiki-identity-2026-07-29.md`](../verification/phase-c-part-1-wiki-identity-2026-07-29.md)

## Why this is a path decision, not a release decision

The private structured index has a modern manifest and its chunk-level check is
exactly clean against the current Wiki (`stale=0`). However:

- it was built with `source_dirty=true`;
- its recorded Git source revision is `5e4cc9c4`, and the private repository's
  current `HEAD` `883815c9` is its ancestor (`883815c9..5e4cc9c4` = `9 0`);
- the five indexed page directories are currently clean; `source_dirty=true` is
  a historical build-time marker;
- the CLI freshness helper reports `stale` because it compares that provenance
  to the checked-out `HEAD` rather than using the manifest;
- `rag_index.py query` exits with code `3` before loading the retriever when the
  default stale policy is `fail`.

So the current pair is content-consistent but not a clean, reproducible PIT
(point-in-time) release snapshot. “PIT” here means that every later answer can
be replayed against the same data boundary; it is not just a timestamp label.

## The seam that must be handled next

There is a manifest freshness implementation that is not wired into the query
CLI, while the query CLI uses a Git-based helper. The current stale result has
two independent causes:

1. `RagStore.index_freshness(wiki)` compares the v2 `manifest:v1:*` source
   fingerprint and returns `fresh` for the private structured index, but no
   production query calls it.
2. `scripts/rag_freshness.check_index_freshness(...)`, used by
   `scripts/rag_index.py query`, checks Git revision/working-tree state and
   returns `stale` for the same index; separately, its
   `meta.source_dirty is True` check also returns `stale` without doing any Git
   comparison. Advancing `HEAD` to `5e4cc9c4` would remove only the first
   reason, not the dirty-build veto.

The query path therefore fails early; the `kb_rag.retrieve(..., require_fresh=True)`
evidence gate is not reached. This is a real integration bug/contract mismatch,
not a reason to weaken the evidence gate. The next slice should wire one explicit
freshness contract into the CLI, then add regression tests for:

- a manifest-fresh source whose Git revision is a descendant of checked-out
  `HEAD`;
- a changed indexed file;
- a changed raw file when `include_raw=true`;
- a missing/legacy provenance field;
- the stale-policy `fail` early return;
- `require_fresh=true` rejecting genuinely stale hits.

The wiring is not a one-line function swap: `RagStore.index_freshness(wiki)`
needs the Wiki `vault_root` to recompute its manifest, while the current
`cmd_query` freshness helper receives only `store.meta`. The fix must carry the
vault root (and the index's include-raw/max-files scope) into the freshness
calculation, while keeping Git provenance and the historical `source_dirty`
flag separately observable. Also note that the CLI computes one index-level
freshness value and copies it into every hit; if the index is stale, every hit is
stale—there is no per-chunk rescue path.

Do not start `evidence_search` replay until the selected clean snapshot reports
`fresh` through the same path used by the runtime.

## Completed in this part

- Proved the two Wiki roots are physical, independently versioned roots using
  device/inode, parent Git repository, branch, revision, inventory, and relation
  hashes.
- Recorded the private structured index's format, manifest, Git provenance,
  freshness, chunk count, and complete artifact hashes.
- Demonstrated that the Chinese-root index is legacy and has 36,298 stale
  chunks; the private full index is legacy and has 54,928 stale chunks.
- Selected the private root/index candidate without changing either knowledge
  repository.
- Ran a bounded read-only sanity probe: the default CLI exits `3` before
  retrieval; with stale policy ignored, 3 hits appear, 54 Markdown files match
  `瑞华泰` on disk, and the candidate index contains 92 matching chunks.
- Preserved the fail-closed requirement: the stale probe output was not admitted
  as production evidence.

## Explicitly not done

- No production `evidence_search` replay for 瑞华泰 or weekly causal queries;
  only the bounded direct `rag_index.py` sanity probe was run.
- No capability dry-run artifact.
- No Phase B live budget ablation.
- No App Server adapter.
- No 28-case board run, no Knevo score, and no Codex-parity claim.
- No `main` merge, no canonical 8792 switch/restart, and no 8799 promotion.

## Next execution order

1. **Obtain authority to repair the freshness seam.** The relevant files live
   in `knowledge-base-private`, not this candidate worktree. Do not edit that
   dirty repository in place. Create a separate clean KB worktree (or obtain
   explicit approval for a scoped cross-repo change), then wire the manifest
   identity into the query early-exit path while retaining Git provenance as a
   separate observable field. Add focused tests; do not turn stale into fresh by
   relabelling.
2. **Create a clean snapshot receipt.** The receipt must pin the exact Wiki
   root, source revision, `source_dirty=false`, manifest revision, index
   artifact hashes, and the runtime freshness result.
3. **Generate the clean capability dry-run.** Record the actual allowed
   capabilities from the current contract. Historical `e179b15c` has
   `contract=null`; it cannot authorize `evidence_search` retroactively.
4. **Only then replay the two bounded queries.** Record candidates, latency,
   cutoff filtering, semantic filtering, and final evidence atoms against the
   pinned root/index.
5. **Classify the remaining gap** as index recall, tool latency/result quality,
   cutoff filtering, model selection/repetition, or completion/verifier
   disagreement. Do not add an unrestricted Wiki grep tool before this
   classification.

## Guardrails for the next agent

- Work only in this detached candidate worktree; preserve the user's dirty main
  worktree and both knowledge repositories.
- Do not rebuild the large index in place. A clean rebuild belongs in an isolated
  snapshot/worktree and must be hash-recorded before use.
- Do not run the full 28-case suite to “see if it works”; the next measurement is
  a bounded identity/freshness/replay experiment.
- Do not change verifier thresholds or required outputs to accommodate the
  selected Wiki.
- Keep `source_dirty`, Git revision, manifest revision, and content hashes as
  separate fields. They answer different questions and must not be collapsed
  into one `fresh=true` flag.

## Handoff status

Phase C Part 1 is closed: the canonical identity is selected, the competing
roots/indexes are distinguished, and the current replay-readiness state is
proven. The next Phase C gate is not open yet. Its starting status is:

> **Canonical identity selected; replay blocked by a proven query early-exit
> freshness mismatch.**

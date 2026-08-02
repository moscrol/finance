# Causal Anchor Guard Completion Handoff

Date: 2026-07-29
Status: **implementation and true-Hybrid replay complete; ready for independent review**
Worktree: `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17`
Branch: `feat/agent-runtime-backends-verify`

## One-sentence handoff

The weekly market-causal search can no longer turn an approximate first hit into
a new company/topic premise, and it cannot report `success` without evidence from
the requested week plus counter-evidence; the fixed true-Hybrid replay now returns
an honest `empty` because the isolated Wiki has no eligible 2026-07-20..24 source.

## Commits to review

```text
44a36566 fix: distinguish skipped retrieval attempts
c74d61ce fix: keep unanchored causal retrieval query-only
12726e9a fix: require causal evidence window coverage
68974ca6 fix: apply causal evidence policy in episodes
```

Use commit subjects or `git log`; do not pin the self-referential documentation
tip as an implementation boundary.

## Review assertions

1. `budget_exhausted` attempts serialize `executed=false`; executed healthy
   Hybrid attempts serialize `executed=true` and carry their real mode fields.
2. `retrieve_closed_loop(..., expansion_policy="query_only", anchor=None)` uses
   only the raw narrow query and fixed market/counter expansions. It does not copy
   terms out of first-hit titles or excerpts.
3. An explicit `EntityAnchor` preserves anchored behavior, so the guard does not
   weaken known-company retrieval.
4. `parse_source_date` accepts ISO and boundary-safe `YYYYMMDD`; it does not guess
   a year for `MMDD` paths.
5. Causal off-window/unknown-date hits never enter `EvidenceSearchResult.evidence`
   or `observation`.
6. Target-window support without a projected counter result is `partial`; both
   are required for `success`.
7. Only `time_aligned_market_causal` Episode contracts receive the strict policy.

## Reproduced evidence

True Hybrid ran with the pinned BGE-m3 snapshot and isolated fresh index. Every
attempt was `hybrid->hybrid`, not degraded, with `model_load_count=1`.

```text
attempts=narrow:ok:6,broad:ok:6,counter:ok:6
conclusion=8; counter=2; discarded=6
target_window=0; target_window_counter=0; window_rejected=9
status=empty; result_count=0; served_date=2026-06-29
```

Later queries contained none of `牧原股份`, `猪周期`, `半导体`, or `光纤光缆`.
The exact environment, queries, hashes, and cleanup audit are in
`docs/verification/phase-c-causal-anchor-guard-2026-07-29.md`.

Focused changed-surface gate: `240 passed in 2.02s`; Ruff and diff checks pass.

## Isolation and boundaries

- KB candidate clean at `fix/manifest-freshness-cli@9053b0c4`.
- Original KB unchanged at `main@883815c9`; indexed page dirs: 0 dirty.
- `9053b0c4` was not merged; that remains unauthorized.
- No generated access log, index, weights, venv, secret, database, or binary is
  part of this slice.
- No 28-case run, App Server implementation, 8792/8799 switch, `main` merge, or
  verifier relaxation occurred.

## Final-goal continuation

After this handoff commit, continue without a human gate to the deterministic
valuation-filtering seam:

1. freeze the current true-Hybrid 瑞华泰 replay as the red baseline;
2. reject `wiki/entities/天奈科技.md` and `wiki/entities/方邦股份.md` when their
   retrieved chunks do not contain a direct subject/ticker/valuation relation;
3. preserve valid comparable-company or supply-chain evidence when the chunk
   itself states that relation — do not implement a filename-only allowlist;
4. replay the same true-Hybrid case and record per-attempt mode telemetry;
5. run the semantic judge only after deterministic filtering, then decide whether
   a larger benchmark or App Server ceiling experiment is justified.

The key design constraint is provenance-local relevance: a graph neighbor is a
retrieval candidate, not automatically model evidence. Admission must be justified
by the retrieved chunk itself or a deterministic high-confidence relation.

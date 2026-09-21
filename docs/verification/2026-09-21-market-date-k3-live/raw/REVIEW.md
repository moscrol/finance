# K3 Workbench Live Acceptance Review

Date: 2026-09-21
Candidate runtime: `786a3b627da9ae37e042881f2c0e8ef12ccac539`
Candidate source tree: `da8fbef79b8b1aaa8e280d532d169bfe7d7c0827`
Python: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
Scope: two real Workbench conversations through `/api/conversations` and `/messages`, K3 as writer, isolated users and sidecar port 19276. No production switch, no data write, no external-search capability.

## Verdict

`AUTHOR_REAL_ENTRYPOINT_OBSERVED_NOT_ACCEPTED`

This is an author-side live observation, not independent Spec/Quality acceptance. Both requests reached a terminal `completed` run and used K3. The candidate is **not accepted** for this task because strict historical cutoff enforcement is not proven and the current-date answer misstates available local data.

## Cases

### 1. Current market question

- Run: `run_20260921_223455_384576`
- Conversation: `conv_f3533694f91a4ec7b0cb49e8560f14e1`
- Assistant message: `msg_df42fd8523ec4c368f4eb566af6d409b`
- K3 calls: 2; tool calls: 5; elapsed: 253.0 s.
- Evidence: 48 observations, 48 unique hashes, all `local_read`; source dates 2026-09-08 through 2026-09-18.
- Positive: K3 used local market data and gave dated 2026-09-18 market/theme facts instead of refusing because DuckDB lagged the snapshot.
- Failure: answer says `2026-09-21 当日行情本地尚无记录`, but startup readiness and a separate post-run local-file observation show a complete fresh 2026-09-21 market snapshot (`akshare_exact`, 52 themes, 103 strong stocks). The relevant issue is not that the 09-18 structured facts are invalid; it is that the answer collapsed “this Episode's local DuckDB path served through 09-18” into “local data has no 09-21 snapshot”.
- System state: semantic judge unavailable; run/report business status partial. The public answer and artifact hash agree. Public citations re-match evidence after the display sanitizer; no unresolved bound hashes.

### 2. Strict historical cutoff question

- Run: `run_20260921_223908_394353`
- Conversation: `conv_b321f310b46e40828bb5d35db9c00d23`
- Assistant message: `msg_4e9d654436ce42149cafcfb8b2535b8f`
- K3 calls: 5; tool calls: 10; elapsed: 297.17 s.
- Positive: observed tool evidence stayed at or before 2026-09-11 (119 observations, 118 unique hashes; dates 2026-09-04 and 2026-09-07 through 2026-09-11). Public citations all match evidence and none is after the requested date. The answer supplied actual 09-11 values and separate gaps.
- Failure 1: runtime context retained `information_cutoff=2026-09-21, source=runtime_default`; `TaskFrame` had `timeframe=2026-09-11` but `subject_kind=company` for the market-wide question and `history_intent=null`.
- Failure 2: offline adversarial replay (`cutoff-diagnostic.json`) against the same local registry showed both an omitted date and an explicit 2026-09-18 query returned 2026-09-18 evidence. The tool did not enforce the user's 2026-09-11 upper bound. The natural answer stayed within the window because K3 selected 09-11, not because the runtime contract blocked later data.
- System state: semantic judge unavailable; report/business status partial; `pending_rejudge=true`.

## Shared acceptance blockers

- Semantic/evidence judge timed out or was unavailable in both runs; no independent content verdict.
- N=1 per case; no variance baseline, so no improvement/regression claim.
- K3 was configured by in-process session-only BYOK; no credential was persisted in the isolated config.
- Production 8792 was only health-read before/after; source revision and tree fingerprint stayed unchanged. It was not switched or used for answers.
- DuckDB selected read audit was equal before/after. This is not a whole-database checksum.
- Sidecar exited, port 19276 closed, candidate worktree stayed clean.
- Prompt bodies were not persisted, only prompt hashes/character counts; `trace.jsonl`, `continuous-episode.json`, answer, report, messages, health, readiness, and server logs are retained.

## Evidence

- Raw run root: `/Users/a77/.finance-runtime/reviews/market-date-advisory-k3-20260921/`
- `observations.json`: structured, redacted-free acceptance observations and identities.
- `cutoff-diagnostic.json`: no-model local registry replay showing the strict-cutoff gap.
- `citation-display-audit.json`: public citation matching after the actual display sanitizer, current 15/15 and historical 13/13.
- `scan-observation.json`: initial repository `SecretScanner` scan of 60 text files; one file/pattern group matched five module/attribute paths in `probe_cutoff.py`, not a credential. Later scripts and this review were not in that initial scan. The archive package gets its own final scan. SQLite stores/locks excluded; neither scan is a security certification.
- `closure.json`: candidate identity stable, selected port closed, server terminated.
- Existing committed engineering archive remains separate. This live package is copied to `docs/verification/2026-09-21-market-date-k3-live/`, with its own manifest and post-commit Git-blob verification. The new package must not borrow the engineering archive's author-QC verdict.
- The original exact-label check in `observations.json` flags five current-case citations; `citation-display-audit.json` resolves all five using the existing display sanitizer. These are presentation-label differences, not missing evidence. Citation-to-evidence matching does not certify every sentence's interpretation.
- Historical report also retains a numeric-unsupported issue despite its aggregate content-degraded count of zero. The aggregate count is not treated as a content-quality certificate.

## Next decision

Do not push, merge, deploy, or call this candidate live-accepted. Fix or explicitly scope the two product gaps, then rerun real conversations with a fresh candidate and a fresh receipt. In particular, strict historical cutoff must be encoded in the immutable run context/tool cutoff, and the writer must distinguish “DuckDB structured facts served through 09-18” from “a 09-21 snapshot exists locally”.

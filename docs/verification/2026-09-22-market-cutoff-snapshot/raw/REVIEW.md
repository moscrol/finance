# Cutoff and Local Snapshot Follow-up

Verdict: **AUTHOR_TARGETED_CHECKS_PASSED_ACCEPTANCE_BLOCKED**.

## Identity

- Branch: `fix/market-date-advisory-0921`.
- Worktree: `/Users/a77/fwp-wt-market-date-advisory-0921`.
- Implementation: `b41c8d4755ae1a6735828b911197f3b62407f58e`.
- Final candidate: `b1e04452bfd45ae2fa4e9177847cb299293ca859`.
- Final tree: `e104eb0fcbf4f11dd74326ce411f568019c3a10b`.
- Interpreter: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`, Python 3.12.13, dependency fingerprint `3328bed61f3e21ea`.

## Changes and Boundaries

Explicit top-level historical cutoffs now enter InformationCutoff with requested semantics; caller bounds can only tighten them. Multiple recognized bounds take the earliest date, including standing-day syntax. Yearless repeated bounds inherit the explicit historical year. Quoted/code/material text cannot declare the bound. This is finite syntax recognition, not a complete natural-language or point-in-time availability guarantee.

The local_market_snapshot tool is granted only to local_only turns already authorized for market_data/mainline_context. The mixed potentially networked market_data tool remains excluded. material_only returns before path discovery or reads. Sealed fixtures without explicit roots do not fall back to production defaults. Historical snapshot reads only open day files at or before the cutoff, check internal date identities, preserve quality/NULL/zero, and retain original JSON array indices in evidence locators. Snapshot market-stage and industry-limit-pool meanings remain distinct from DuckDB review stages and mainline tables.

Strict requested cutoffs quarantine future evidence, combined observation text, unstructured gaps and trace detail; strictness is also part of the query-cache variant. Runtime-default behavior is retained. A missing query result must not be inflated into a claim that all local data is missing. The separate market question routing issue was not changed.

## Evidence by Revision

| Candidate | Actual result |
| --- | --- |
| Development dirty trees | 323 targeted passes, then 22 and 68 related passes; not fixed-source acceptance |
| b41c8d475 | Frontend 110 passes, E2E 34 passes / 2 skips; five registry checks exit 0; mutations 21/22 caught, one survivor |
| b41c8d475 full Python | NOT STARTED: free space below predeclared 8 GiB admission; owned waiting pid 13134 stopped; original incomplete run.json retained with closure-notes.json |
| b41c8d475 independent Spec/Quality | NO VERDICT: startup/host/CLI/model capacity errors retained; smoke is not a review |
| b1e04452b | Clean fixed-source 326 targeted passes; JUnit 326 cases and exact receipt agree; repository Ruff exit 0 |
| b1e04452b mutations | 24/24 caught, baseline passes and mutant assertion failures without collection/setup errors; candidate unchanged |
| b1e04452b frontend | install/lint/typecheck/test/build/E2E all exit 0; 110 unit passes, 34 E2E passes / 2 skips; candidate unchanged |
| b1e04452b registry | Five checks exit 0; candidate unchanged |
| b1e04452b full Python / independent reviews / K3 | NOT COMPLETED; no new full Python, independent review, or real K3 session was started on this revision |

Exact targeted receipt: `/Users/a77/.finance-runtime/test-receipts/20260921T165015Z-b1e04452.json`, SHA256 `2f18cb54e7fb62cb72f828d583a86e5d2e7f0a78dcaca48ee7e0121bd33a8194`. A byte copy is in `final-b1e04452b/directed/pytest-receipt.json`. Other checks retain their own logs/identities, not shared latest.json.

## Survivor and Errata

`future_snapshot_allowed` survived on b41 because Path.read_text's test replacement raised AssertionError inside the reader's broad exception handler. The reader skipped the bad file and the test passed. The test now records paths and asserts after the reader returns; that mutant fails on b1. Two additional mutants cover standing-day upper bounds and runtime-year substitution.

Progress messages briefly reported eight new catches and an incomplete mutation run. The immutable b41 result proves 22 completed before the termination attempt, 21 caught / 1 survivor. The raw result and closure correction are both retained. Spec/Quality capacity failures are not successful reviews. An erroneous read path ending in 0922 and a guessed nonexistent vault validation script were not successful reads or validation.

## Blockers and Next Steps

Free disk declined to approximately 3.2 GiB after completed checks, below 8 GiB full-suite admission and close to the 3 GiB running floor. No other task's data was deleted and safety thresholds were not changed. No owned check/review process remains; ports 19651/19654/19276 had no listeners at closure. These are local test-port observations, not production-health certification.

Restore adequate disk capacity without deleting unowned artifacts, then run full Python on a clean fixed revision and obtain independent Spec and Quality verdicts. If code changes, bind all required acceptance to a new revision. Only after engineering admission, repeat the two original questions through real Workbench conversations/messages with K3 writer and GLM judge, isolated users/store/port, actual context/evidence dates and public draft/citations checked. Complete responses alone are not quality acceptance; N=1 per question is not an improvement rate.

The prior K3 verdict AUTHOR_REAL_ENTRYPOINT_OBSERVED_NOT_ACCEPTED remains. No new K3 sidecar was started; the copied run_live.py in the separate pending K3 directory still contains OLD identity and must not be run unedited. No data collection/backfill, production database write, financial-branch push, PR, main merge or deployment was performed.

## Artifact Scope

Freeze text logs, scripts, results, JUnit, exact copied receipts, failures and corrections. Exclude fixture directories, caches and binaries, retain originals externally, compare every copied byte, scan for sensitive patterns with context review, and verify the committed Git blobs using scripts/check_evidence_archive.py. One-off drivers are frozen as .py.txt, not promoted to general repo tooling; they are candidate-specific and existing check/receipt APIs remain the reusable tools.

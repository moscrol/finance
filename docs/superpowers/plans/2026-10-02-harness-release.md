> 2026-10-04 回收：原件只存在于 `/private/tmp/harness-opt/tmp/harness-release-1002/docs/superpowers/plans/2026-10-02-harness-release.md`，未跟踪、从未提交（sha256 f5a07a6fe9b446cd）。正文未改，属 10-02 历史快照；文中「未提交 / 尚未执行」等只描述当时。

# Harness release and multi-turn readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the validated information, tool and conversation improvements, publish a tested GitHub main revision to canonical 8792, and leave a reproducible starting point for further optimization.

**Architecture:** The same model-facing task/evidence contract applies across models. Permission, evidence identity and budgets remain enforced; semantic routing is not newly hardened by model price or presumed strength. Optional experimental tools remain off until independently evaluated. A release demonstrates engineering and conversation readiness, not a universal model-quality gain.

**Tech Stack:** Python 3.12 shared workbench interpreter, pytest/Ruff, pnpm/Vite/Playwright, GitHub Actions, macOS launchd and immutable runtime worktrees.

---

## Accepted scope and fixed sources

User's 2026-10-02 instruction authorizes execution, merging and deployment after validation. All implementation happens in `/tmp/harness-opt/tmp/harness-release-1002`, branch `codex/harness-release-1002`, based on `origin/main` at `3a2718c6c7dbf5af8ddad249b50835d09deef8a4`.

Sources: PR8 `b55eb4d86aa9fc3c9801be69f3e49314cb8dab17`; PR10 `d66b1a66055b0ac1e4f95b0a66225883c3dbf881`; PR11–14 stack ending `6d8e3ad0f28d4c875b4529ea6e0fc01f5f21df0e`; PR15 `41c80c0c2700bc5de9a986ddee9aba12a2c03d19`. Preserve their history and recorded failed experiments. PR14 batches 01–11 are closed; formal four-cell claims are unproven.

Explicitly excluded: local commit20's model-tier routing policy and permissive tier gate; local forced semantic routing changes 11/16/17/19; A7 frozen fixture edit; field-name numeric release with unresolved 23/42-family future-condition exceptions; schema slimming whose model acceptance is absent. These are rejected from this release rather than left as an implicit release prerequisite. Keep source branches and evidence. Do not revoke credentials, delete unrelated/Gitea branches, or create prediction-ledger hypotheses.

## Task 1: Integrate tested branch work

Files: model admission and CLI modules; runtime branch accounting; material authoring and conversation task/evidence context; existing tests and source documentation from the fixed commits.

- [ ] Merge PR8 then PR10 into the isolated release branch using `git merge --no-ff <fixed-sha>`; inspect each delta and commit through existing hooks.
- [ ] Merge the PR14 stack. Resolve each conflict using both source versions: retain recursive artifact/store evidence and hash checking from PR11, automatic per-turn and configured-model admission from PR10, and strict refusal of incomplete four-cell evidence. Preserve preregistration history without rewriting experimental outcomes.
- [ ] Merge PR15's four fixes: unknown worker calls remain unknown; no self-report admission bypass; APFS/WAL clone for read-only checks; Ruff and pytest failures both affect exit code. Preserve the explicit pre-worker zero-call failure case.
- [ ] Run focused admission, model-harness, material/conversation and read-tool tests with `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -p no:cacheprovider`. No models are called by these tests.
- [ ] Independently review requirements first, then code quality; resolve every confirmed integration regression before moving on.

## Task 2: Fix delivered-evidence read coverage

Files: `intelligence/runtime/agent_episode.py`, evidence-read runtime tests, `docs/agent-product-door.md` as needed.

- [ ] Reproduce the existing ScriptedModel/StubCoordinator case in `/tmp/harness-opt/tmp/local-agent-validation-1002/pr14-evidence-read-sub-research-repro.py`: a fully delivered sub-research evidence body is reread and incorrectly counted as new characters.
- [ ] Seed coverage only when the sub-research inbox result has actually been claimed and appended to model-visible messages; do not count completion or saved-but-undelivered events.
- [ ] Assert rereading delivered characters yields `new_read_chars=0`; genuinely unseen pages remain positive; no coverage leaks between Episodes; flag and explicit capability remain required. Preserve default off and model choice.
- [ ] Run existing read-tool/sub-research tests, then independent requirements and code-quality reviews.

## Task 3: Bring across general offline tools and parsing corrections

Files: local content-correctness fixtures/scorer; route diagnostic probe; `episode_semantic_verifier.py` short-date/list-label parser and its tests; release documentation.

- [ ] Import the offline evaluation tools from the original patch series without their routing changes or frozen A7 edit. Their result is diagnostic, not proof of transferable benefit.
- [ ] Bring across only the short-date/unit and decimal/list-prefix corrections from `b244bb8b3` and `d279a4ba8`. Retain existing metric/evidence matching policy. Test dates, decimal values, ranges and actual list labels against both supported and unsupported evidence.
- [ ] Replay numeric changes on saved runs. Any newly suppressed genuine unsupported claim blocks that change; record all restoration failures. Preserve the historical source evidence read-only.
- [ ] Copy the previous direction audit as a historical report, add a release disposition explaining exclusions, and document the same-budget unseen-task/cross-model acceptance requirement for future optimization.

## Task 4: Integrated gates and bounded conversation acceptance

### Release prerequisite discovered in production: snapshot date identity

Current 8792 is healthy at `2c3949786568`, but readiness rejects an AkShare snapshot dated 2026-10-01 while all relevant DuckDB data ends 2026-09-30. The 10-01 snapshot repeats 09-30 values; the shared trading calendar certifies 10-01/10-02 as closed. This is an input identity defect, independent of model routing.

- [ ] In `market_snapshot_sync.py` and the direct `akshare_market_snapshot.py` entry point, use the existing three-state `market_feature_store.trading_days.trading_day_verdict`; never fetch today's spot rows as a historical/closed/unknown requested day's observations. Do not create a second holiday list or infer holidays from missing rows. Preserve exact dated DuckDB fallback and honest historical metadata.
- [ ] Add deterministic tests that known closures and a historical request do not invoke the spot runner, that an unknown calendar does not certify exact data, and that a current known trading day still uses the provider. Keep source/data day separate from collection/request day.
- [ ] Generate recovery JSON in `/tmp/harness-opt/tmp/release-validation-1002/snapshot-stage` using the existing sync API without any AkShare runner. Its contract and DuckDB reconciliation already PASS: requested 10-02, served 09-30, provider duckdb_latest, historical, business DB stat unchanged.
- [ ] Before applying, preserve overwritten small JSON originals and hashes. Publish the checked dated file, latest and meta atomically per file, meta last; preserve the invalid 10-01 file outside canonical date lookup. Recheck readiness and DB identity. Do not copy or edit the multi-GB business database.

- [ ] Commit the candidate with explicit file paths, record its full SHA and tree, and ensure clean status. Never change the tested tree while a gate runs.
- [ ] Run full `python -m ruff check .` and `python -m pytest -q -p no:cacheprovider`; pytest temporary storage must be outside all Git worktrees. Validate its receipt using `scripts/check_test_receipt.py --require-full-scope --expect-revision <exact-sha>`.
- [ ] Run `scripts/run_frontend_gate.py --tree <fixed-tree> --expect-revision <exact-sha> --output <new-outside-tree-dir> --workbench-port 18981 --re06-port 18984`; require all frontend and E2E steps green.
- [ ] Use isolated sidecar users and Episode store, read-only production data, and configured provider for bounded material-answer/correction/followup/new-topic acceptance. Persist complete answers, effective model receipts and failures. Do not call the unrun 240-question experiment or change production models.
- [ ] Open and attach a successor integration PR. All GitHub required leaves must pass at its current revision. Close source PRs only after they are incorporated, with the successor pointer and disposition.

## Task 5: Merge, deploy and close out

- [ ] Before push, verify Gitea has no reverse push mirror using existing Keychain-backed helper; never print credentials. Use a normal branch push and GitHub PR merge.
- [ ] After merge, run exact-main batch verification and retain the prior successful candidate receipts separately. Do not attribute branch results to a different revision.
- [ ] Build a new immutable detached runtime snapshot of the merged revision. Save the old link, prove current healthy identity, stop service, switch link, record port 8792 deployment ledger entry, then restart. Never rsync over a Git snapshot.
- [ ] Require health identity (`source_revision`, clean source, `code_matches_repo`) and readiness, then bounded Conversation API multi-turn smoke with persisted evidence and grounded data date. Roll back the link and record failure if readiness or release acceptance fails.
- [ ] Preserve all failed experiments, source branches and rollback runtime; clean only owned temporary clean gate trees and stopped sidecars. Write final inflight and dated closeout after the actions, with actual merge/deploy identities and receipts.

## Acceptance boundaries

No invented model improvement, no hidden bypass of strict admission or verifier failures, no activation of optional candidates because tests alone passed. Actual conversation readiness is required for release; experimental score improvement belongs to the next optimization iteration.

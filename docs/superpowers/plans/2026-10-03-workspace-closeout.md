# Workspace Optimization Closeout Implementation Plan

> **For agentic workers:** Use subagent-driven-development for isolated implementation tasks and independent specification/quality reviews. The user explicitly authorized quality checks, completion, main merges, and deployment on 2026-10-03. Preserve Pi's active `feat/harness-output-provenance-1003` work.

**Goal:** Account for the existing workspace and GitHub optimization queue, complete usable changes, pass release gates, and deploy the resulting revisions with evidence.

**Architecture:** Integrate existing work through the existing Workbench entry points. Preserve authorization, deadlines, source identities, and original experimental failures. Previously rejected designs and explicitly archived FinArena work retain their disposition; a preserved branch is not automatically a new product requirement.

**Tech Stack:** Python 3.12, FastAPI, DuckDB read APIs, React/TypeScript, pnpm, GitHub Actions, macOS launchd.

## Task 1: Release the existing runtime candidate

**Sources:** GitHub PR24 `bd0be25db7b5ed04d12a86ed6f726aaf4fda3e04`; its included PR8 and PR10–15 history; `docs/verification/2026-10-02-harness-takeover.md`.

- [ ] Independently review the fixed diff against `3a2718c6c7dbf5af8ddad249b50835d09deef8a4` along specification and standards axes.
- [ ] In a clean owned checkout, bootstrap a local `.venv-workbench` using `python3 scripts/workspace.py bootstrap --python <contract-matching Python> --install`; verify `doctor` has no dependency drift. Do not change the shared environment.
- [ ] Run `env -i HOME="$HOME" PATH="$PATH" bash scripts/run_main_gate.sh --pytest-args '-q -p no:cacheprovider --basetemp=<external unique path>'`. Require zero exit and validate the resulting receipt with `--require-full-scope --expect-revision <tested SHA>`.
- [ ] Recheck Python, frontend, E2E, registry and aggregate GitHub conclusions at PR24's exact head. Merge normally after all gates and both reviews pass.
- [ ] Verify the merged main revision, build static assets from that clean source, update the versioned runtime snapshot and deployment ledger, then verify readiness and loaded-code identity.

## Task 2: Complete evaluation and budget tooling

**Sources:** PR18–23 stack ending at `acc743c847285bbc1fbd6410b1b255c36726fc85`; PR17 request-view increment; `fix/pr16-qc-1002` comparator increment.

- [ ] Merge the stack into a new candidate based on the accepted runtime, preserving both model-admission contracts in any add/add conflict. Resolve documentation append conflicts by retaining both original records.
- [ ] Preserve frozen experiment inputs/results and their failed or inconclusive conclusions. Keep request catalog experiments opt-in; do not activate model-tier semantic policies or authorize the 240-call experiment.
- [ ] Import the independent catalog-view/comparator increment only after confirming it has no dependency on excluded tier policies. Retain its tests and independent evidence.
- [ ] Run the affected deadline, admission, thin-ReAct, conversation-preflight, opening-budget and catalog-view tests. Confirm restored protection mutations still fail where those artifacts exist.
- [ ] Submit a focused GitHub PR after specification and quality review; require exact-head full release gates before merge.

## Task 3: Recover the existing Workbench interface improvements

**Sources:** `feat/board-calendar`; the main checkout's uncommitted River/daily-review/opinion-attention sources and `docs/handoffs/2026-09-29-original-8798-optimization.md`, `2026-09-29-daily-review-dashboard-implementation.md`, `2026-09-29-agent-consumption-observation.md`; optional theme source `feat/workbench-tech-premium`.

**Files:** `intelligence/api/app.py`, `intelligence/api/river_routes.py`, `intelligence/api/river_daily_routes.py`, the matching `intelligence/services/{board_calendar,river_daily_overview,river_daily_review,opinion_attention,opinion_attention_bridge}.py`, existing/new relevant tests, and `intelligence/webapp/src/` entry points, River components, date types, API client and styles. Existing source files determine the exact import set. Never copy old generated static bundles or preview-only entry points.

- [ ] Read each source handoff and capture file hashes before copying. Compare committed branch changes and dirty deltas separately against the current candidate; preserve original trees unchanged.
- [ ] Restore existing navigation, consecutive-board calendar, River timeline, daily archive view and observation workspace. Reuse existing archive definitions, shared selected date and readonly query contracts; do not synthesize data, add collection, or connect external news.
- [ ] Bring over the original bug fixes for late responses, date changes, latest-window anchoring and missing values. Register the matching backend routes alongside existing Workbench routes.
- [ ] Inspect the theme candidate against the current application. Reuse it only if compatible with the existing design; do not replace the current app with stale generated HTML/CSS or an independent preview product.
- [ ] Run the relevant backend tests with the locked `.venv-workbench/bin/python`. Run frontend lint, typecheck, component tests and build; exercise the real app's date/navigation paths through existing E2E fixtures without production writes.
- [ ] Commit only exact paths owned by this task; obtain specification review followed by quality review, repair any actionable findings, and return a clean candidate to the release owner.

## Task 4: Account for remaining local work

- [ ] Compare the 74-worktree inventory and GitHub branch/PR inventory with the candidate by ancestry and file content. Record source SHA, disposition, successor and evidence for each independent work item.
- [ ] Check main's remaining query-quality and consumption-audit deltas against already merged versions; port only real remaining fixes and their tests.
- [ ] Keep production data exports, user-run metadata, caches and credentials out of public commits. Keep archived FinArena, rejected model-tier routing and obsolete answer experiments preserved with a successor/rejection pointer.
- [ ] Do not alter Pi's active provenance/request-interpretation branch. Record its current owner and exact pending scope.

## Task 5: Verify and deploy the completed integration

- [ ] Run full Python/Ruff, frontend/E2E and registry gates in a clean fixed candidate and check exact-head GitHub results. Resolve all new failures; do not narrow collection to obtain a green receipt.
- [ ] Merge the accepted PR normally. Run final main gates with receipts tied to its exact revision.
- [ ] Verify there are no active Workbench requests, preserve current runtime/scheduler paths and rollback configuration, then switch to a clean versioned runtime and record the actual deployment.
- [ ] Regenerate the small derived market snapshot using the approved readonly DuckDB path. On the current closed exchange date, requested date may be current, while source/served date must remain the database's latest trading date. Verify the DB is unchanged.
- [ ] Update the existing night-job code root to the accepted revision so the old spot-date bug cannot overwrite the repaired snapshot. Preserve schedule and user settings.
- [ ] Verify `/api/health`, `/api/readiness`, actual navigation and representative bounded conversation delivery. Preserve unsuccessful attempts and distinguish engineering acceptance from unproven model-quality gains.
- [ ] Close superseded PRs with the landed successor; preserve branches and original evidence. Update inflight handoff after actions, and verify the GitHub-to-Gitea backup.

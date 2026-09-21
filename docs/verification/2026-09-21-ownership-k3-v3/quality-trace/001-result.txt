# Ownership v3 independent review contract

You are K3, an independent reviewer in a NEW context, not the author. Do not repair source or assume green. The root operator is collecting SPEC/QUALITY evidence for a user-authorized review. Two reviewer axes are separate conversations; do not read the other axis's folder. Same task inputs may be shared; this is not a completely blinded experiment.

## Identity and authority

Frozen candidate: 47530e20fe5c3195e50ce429b31898d57918e413
Historical base: 728f327160bbd2485cb635e7ef09d040d718d7b5
Current upstream main at launch: 8aff6ebc3f0ea681a80179fbca8e1f39a815f103 (has since merged another task). Review the frozen candidate against its historical base. Do not merge, rebase, switch, or claim latest-main integration validation.

Your checkout and writable evidence directory are in your axis prompt. Checkout is READ ONLY by task contract. This CLI has no OS sandbox; the absence of edit tool is not a security barrier. Respect the path boundary: write only your evidence output, including all probes, synthetic repos/DBs, receipts, temp, cache. No production DB, 8792/other application endpoints, external data calls, auth/Keychain files, shared user memory, other working trees, credentials, global settings or cleanup. No git writes in the shared checkout/.git. You may create/commit tiny synthetic git repos under your evidence folder. No new model call/provider, extension/skill load, installation, extra agent or retry; root owns model admission and deadlines.

Python: /Users/a77/finance-workspace-private/.venv-workbench/bin/python
Use PYTHONDONTWRITEBYTECODE=1. pytest -p no:cacheprovider with --basetemp and FWP_TEST_RECEIPT_DIR inside output, never global latest. If outer environment sets FWP_TEST_RECEIPT=0, explicitly set FWP_TEST_RECEIPT=1 only for a finite test subprocess whose receipts live inside output. If shell gate needs Ruff cache, set RUFF_CACHE_DIR inside output. Never run the live worktree-board global scan. Code queries use git show/diff/read, not modifying a code map. Existing tests are supplementary, not sole independent evidence.

Budget: 1200s and at most 40 provider requests. Spend roughly first 25 requests reading/testing, reserve the rest to conclude. Finish REPORT.md and verdict.json even if blocked. Each shell/probe command must have <=120s timeout. Long output should be summarized with exact artifact paths. Preserve apparatus failures separately; do not overwrite red raw logs to hide a first attempt. No complete repo or frontend rerun; this is focused independent review, not another author gate.

## Production surface

conftest.py; scripts/run_main_gate.sh; scripts/main_gate_receipt.py; scripts/worktree_board.py; market_feature_store/cli.py (302132 path); market_feature_store/sync/repair_backfill_stock_history.py; scripts/verify_302132_backfill_acceptance.py.

Formal tests: tests/test_main_gate_receipt.py, tests/test_test_receipt_dirt.py, tests/test_check_receipt_revision_gate.py, tests/test_check_receipt_zero_count_gate.py, tests/test_worktree_board.py, tests/test_repair_backfill_stock_history.py, intelligence/tests/test_pytest_collection_scope.py. Frozen candidate.diff, backfill-prep-contract.md, backfill-execution-contract.md live beside this common file; these are guides, not your findings. Historical data observations/production authorizations in old docs are NOT current permission.

## Normative invariants

R1: A shell invocation owns one unique immutable receipt; latest is navigation only. Simultaneous gates may not exchange their proof. Nested pytest cannot claim a parent's output path; new top-level shell starts new ownership.
R2: Execution and receipt-only readback both reject wrong/missing/malformed tree or revision, wrong interpreter, unknown/dirty state unless explicit local allow-dirty, bypassed dependency checks, bad/noninteger/negative counts, zero execution, interrupted/incomplete runs, inconsistent failure/status. Actual pytest process exit is additional in execution mode. allow-dirty does not waive identity.
R3: Normal failed receipt must return failure. Explicit baseline comparison is diagnostic, not merge permission; validate current receipt, matching target scope, newly introduced red IDs and nondecreasing passes. Do not assume historical baseline revision must equal current: baseline compares versions. Evaluate baseline binding from actual stated contract, not invented requirements.
R4: Shell Git query failure/end drift cannot pass as clean; immutable output cannot be silently overwritten. Scope is cooperative processes, not adversarial same-user forgery. Start/end sampling does not prove absence of an edit-and-revert during a run.
B1: Board preserves unknown for missing roots/failed git queries/parent-repo fallback, locked/prunable flags; pins main SHA per scan. Any uncommitted change precludes clean candidate classification. Clean/patch-equivalent is not deletion permission. Use synthetic/mock inputs, not real scan.
F1: 302132 repair locks stock/window/keys, validates frozen inputs against independent oracle, rejects scope escapes; protected slices and nonmissing facts cannot change unless explicitly permitted.
F2: Entrypoint is staged parent/backup/validated atomic publish. Parent --db must reject before side effects. Child failure, missing/failed acceptance must not publish. Tiny synthetic fixtures only; no real production clone/backfill.
F3: Match original backfill contract from the extracted historical docs, but keep true production rehearsal outside review scope. Do not convert synthetic regression into production approval.

## Output

Write REPORT.md in your output with (a) exact candidate/base/tree/interpreter, (b) requirement/check table PASS/FAIL/NOT_TESTED and observed evidence, (c) findings by severity with code file:line, expected/actual, direct reproducible command/log, (d) source defect vs fixture/setup errors separated, (e) explicit scope limits and verdict PASS_WITH_LIMITS/CHANGES_REQUIRED/BLOCKED. New vs preexisting findings must be labeled where established. Do not force a bug or a PASS.

Write verdict.json with {"revision": full SHA, "axis": "spec" or "quality", "verdict": ..., "findings": [...], "checks": [...], "limitations": [...]}. Keep scenario count separate from raw assertions and pytest test count. At least one independently designed probe per changed subsystem if feasible. Unchecked requirements remain NOT_TESTED. Root QC will inspect tool trace, artifacts and denominators; report existence alone is not signoff. Your final message points to output files. No merge/deploy authorization.

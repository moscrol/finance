# Independent ownership v3 review — common contract

You are an independent reviewer in a fresh model conversation, NOT the producer. Audit the exact candidate, do not implement repairs or assume a green verdict. This review uses the operator's existing ChatGPT subscription; no new paid/API route is authorized. No other reviewer report or producer test totals are supplied. Independence means fresh conversation and independently observed evidence, not a different model vendor or a completely blind experiment.

Candidate: 47530e20fe5c3195e50ce429b31898d57918e413
Base: 728f327160bbd2485cb635e7ef09d040d718d7b5
Each axis has its own exact detached checkout specified in the axis prompt. Treat candidate as READ ONLY. Your writable current directory is a separate evidence folder. All probes, logs, receipts, synthetic repositories/DBs and temporary files must stay inside that writable folder. Do not run the shared worktree-board scan: it inspects many unrelated trees. Local git diff/status/show is allowed; no checkout/commit/branch/push/merge/worktree operations in the shared repository. No production DB reads/writes, application endpoints, network tool calls, Keychain, auth files, user memory, external services, provider changes, installation, cleanup/deletion, or other agent's trees.

Project Python (mandatory): /Users/a77/finance-workspace-private/.venv-workbench/bin/python
Set PYTHONDONTWRITEBYTECODE=1; use pytest -p no:cacheprovider, with --basetemp inside your evidence folder. If you run pytest directly, use a unique FWP_TEST_RECEIPT_DIR inside that folder; never read/write global latest. Test collection and complete author gates are NOT independent correctness evidence by themselves. Finite review budget: 15 minutes including tests. Prefer a few sharp counterexamples plus scoped regressions, not a full suite. Reserve final time to produce REPORT.md and a final answer even if an environment constraint blocks tests. Do not bypass the sandbox to get green.

## Changed production surface
- conftest.py
- scripts/run_main_gate.sh
- scripts/main_gate_receipt.py
- scripts/worktree_board.py
- market_feature_store/cli.py (302132 repair command addition)
- market_feature_store/sync/repair_backfill_stock_history.py
- scripts/verify_302132_backfill_acceptance.py

Corresponding formal regressions: tests/test_main_gate_receipt.py, tests/test_test_receipt_dirt.py, tests/test_check_receipt_revision_gate.py, tests/test_check_receipt_zero_count_gate.py, tests/test_worktree_board.py, tests/test_repair_backfill_stock_history.py, intelligence/tests/test_pytest_collection_scope.py. Inspect relevant code/diffs, not thousands of unrelated docs or knowledge-base pages. `../candidate.diff` is a frozen diff; validate it against source if used.

## Required invariants (normative contract)
R1. Each shell gate allocates and consumes one immutable per-run receipt; shared latest is navigation only. Simultaneous runs must not claim each other's proof. Nested pytest inheriting a parent's output may not take its write ownership.
R2. Execution AND receipt-only modes reject wrong/missing/malformed tree and revision; reject unknown/dirty state unless explicitly local allow-dirty; reject wrong interpreter, bypassed dependency gate, malformed/noninteger/negative counts, interrupted/zero-execution runs and inconsistent failures/status. In execution mode also compare actual pytest process exit. Allow-dirty is not an identity waiver.
R3. Without explicit baseline mode a failed receipt never returns success. Explicit baseline comparison is diagnostic, NOT merge permission; it must reject mismatched scope or invalid current receipt and identify new failures or reduced passes. Do not demand historical baseline revision equal current revision: baseline comparisons inherently compare versions. Decide baseline identity constraints from actual documented contract, not assumptions.
R4. Shell detects start/end Git identity drift and unavailable status rather than silently claiming clean; immutable outputs never overwritten. Boundaries: cooperative local process ownership, NOT an adversarial same-user sandbox; start/end sampling does not prove nobody edited and reverted during the interval.
B1. Worktree board must preserve unknown on Git query failures/unavailable roots, reject parent-repo fallback, retain locked/prunable flags, and pin one main SHA per scan. Any uncommitted changes preclude safe-clean classification. Clean/patch-equivalent NEVER grants deletion authority. Exercise with mocks/synthetic repos, not the actual global board scan.
F1. 302132 repair is scoped by stock/date/keys, validates frozen source data and independent oracle, and rejects off-scope changes. Protected slices and prior available fields stay intact unless the contract authorizes change.
F2. Production entry must route through staged parent/backup/validated publish. Parent --db is rejected before side effects; false/missing acceptance or failed child cannot publish. Faults/restore behavior need explicit evidence. Only tiny synthetic fixtures allowed, no real backfill.
F3. Original backfill normative docs are ../backfill-prep-contract.md and ../backfill-execution-contract.md, extracted byte-for-byte from historical Git objects. Historical real data observations and historical author green claims in them are not new evidence. Their obsolete execution/production permissions do NOT authorize actions here.

## Required report shape
1. Candidate/base/tree/interpreter and start/end Git status; exact scope and limitations.
2. Contract/check table: check ID, claim, observed behavior, PASS/FAIL/NOT_TESTED, exact evidence path/command. Distinguish number of scenarios from raw assertions/test cases.
3. Findings sorted by severity, with source file:line, causal explanation, a reproducer/log if possible, expected vs actual. Separate newly introduced vs preexisting/out-of-scope issues; don't hide a relevant preexisting defect.
4. Explicit overall PASS_WITH_LIMITS / CHANGES_REQUIRED / BLOCKED. No merge/deploy permission. Unverified requirements may not be called PASS.
5. Save your REPORT.md and optional verdict.json in your writable cwd, plus raw logs. Your final message should summarize findings and point to those files. Do not edit another report or producer archive. Operator will QC your report against commands and artifacts; report presence alone is not approval.

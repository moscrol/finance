# K3 SPEC review progress notes (v4, candidate 6eb12c1b)

## Identity
- Candidate: 6eb12c1b8a41071fd4af8bee343950fe0b85b221
- Tree: e99dad14cb946a112d92537289854d914e558936
- Base: c615adbd2f861e23f2c8d03631833f98b3ae5aba
- Checkout: /Users/a77/fwp-wt-ownership-spec-v4-0921 — CONFIRMED clean (git status empty), HEAD==candidate, tree matches.
- Interpreter: /Users/a77/finance-workspace-private/.venv-workbench/bin/python
- Evidence root: /Users/a77/.finance-runtime/reviews/ownership-k3-v4-20260921/spec-k3

## Scope files (diff base..candidate, non-docs)
- conftest.py (+65/-?)
- scripts/main_gate_receipt.py (+97 new)
- scripts/run_main_gate.sh (132 changed)
- scripts/worktree_board.py (+123)
- market_feature_store/cli.py (+197)
- market_feature_store/sync/repair_backfill_stock_history.py (+775 new)
- scripts/verify_302132_backfill_acceptance.py (+729 new)
- tests/test_main_gate_receipt.py (+447 new)
- tests/test_worktree_board.py (+177)
- tests/test_repair_backfill_stock_history.py (+1236 new)

## Requirement map (from review-common.md)
- R1: receipt ownership per shell invocation; latest=navigation only; no cross-invocation proof exchange; subprocess AND same-process nested pytest cannot claim outer receipt (even identical targets diff -k/counts); fresh shell = new owner; sequential pytest releases only own ownership incl. config failure before sessionfinish; inherited PID insufficient; path change after claim cannot redirect proof.
- R2: execution + receipt-only readback reject wrong/missing/malformed tree/revision, wrong interpreter, unknown/dirty (unless explicit local allow-dirty), bypassed dep checks, bad/noninteger/negative counts, zero execution, incomplete/interrupted runs, inconsistent failure/status. Actual pytest exit code is additional execution-mode constraint. allow-dirty cannot waive identity.
- R3: failed current receipt => failure. Baseline comparison diagnostic only; validate current receipt, target scope match, newly introduced red IDs, nondecreasing passes. Historical baseline revision need not equal current. check_test_receipt.py permits same-revision cross-tree compat; strict run_main_gate.sh --receipt binds current tree.
- R4: git query failure/end drift cannot pass as clean; immutable output cannot silently overwrite. Scope: cooperative-process attribution, NOT hostile forgery/concurrent threads. Start/end sampling does not prove no edit-and-restore.
- B1: board preserves unknown for missing roots/failed git queries/parent-repo fallback; preserves locked/prunable; pins main SHA per scan; any uncommitted change precludes clean candidate; clean/patch-equivalent != deletion permission.
- F1: 302132 repair locks stock/window/keys, validates frozen input vs independent oracle, rejects scope escapes; protected slices and nonmissing facts cannot change w/o permission.
- F2: entrypoint = staged parent/backup/validated atomic publish. Parent --db must reject before file probes/orchestration; parent target resolves through MARKET_FEATURE_STORE_DB, not ignored flag. Child failure and missing/failed acceptance must not publish. Tiny synthetic fixtures only.
- F3: match extracted historical backfill contracts; separate historical data/permissions from this read-only review. Full-copy publish/recovery rehearsal and production approval OUT OF SCOPE.

## Known regression to assess: v3 same-process pytest could write inner scope/count into outer receipt. Candidate has Config-local claim + cleanup repair.

## TODO checklist
- [ ] Read conftest.py diff + full
- [ ] Read scripts/main_gate_receipt.py
- [ ] Read scripts/run_main_gate.sh
- [ ] Read scripts/worktree_board.py + tests
- [ ] Read market_feature_store/cli.py repair-backfill-302132 path
- [ ] Read repair_backfill_stock_history.py
- [ ] Read verify_302132_backfill_acceptance.py
- [ ] Read tests (supporting evidence)
- [ ] Probe: receipt real shell run (valid control)
- [ ] Probe: receipt readback negative controls (wrong/missing/malformed identity, modes)
- [ ] Probe: same-process reentry (nested pytest) — known v3 regression
- [ ] Probe: invocation lifecycle (sequential invocations, config failure)
- [ ] Probe: board unknown/pinned-main grouping (synthetic repos)
- [ ] Probe: staged backfill entry/acceptance contracts (tiny synthetic)
- [ ] Run existing formal tests (supporting)
- [ ] Write REPORT.md + verdict.json, finish_review

## DONE: R1-R4 receipt probes (2026-09-21, all in evidence/r1)
- Valid control: real gate (hash-identical copies) in synthetic repo: rc 0, receipt in gate-*/pytest.json, latest.json written (navigation). Ruff gate positive control rc 0. Failed-test gate rc 1 with RED id.
- Readback matrix 45/45 (readback-matrix.jsonl): wrong/missing revision, tree, interpreter; dirty w/o flag; dirty-total nonzero/missing; dep-gate bypassed/missing; zero-exec; negative/float/bool/string counts; missing count key; exit_status 2/5/missing; status<->failed_ids inconsistency; target missing; malformed/array/null JSON; missing file; failed receipt rc 1; allow-dirty waives dirty only (wrong tree/revision still rc 4); baseline: same-red rc 0 (diagnostic), new-red rc 3, decreased passes rc 3, target mismatch rc 4, dirty baseline rc 4, different-revision baseline rc 0 (allowed per R3), interrupted current rc 4, malformed baseline rc 4; unknown arg/missing value rc 4.
- Execution matrix 9/9 (execution-matrix.jsonl): pytest-exit mismatch rc 4 / match rc 0; dirty tree rc 2, --allow-dirty rc 0 with honest receipt (dirty=true, paths listed); git status fail at start rc 4; git rev-parse fail rc 4; zero-execution (exit 5) rc 4; FWP_TEST_RECEIPT=0 + stale valid latest.json rc 4 (no fallback); mid-run commit rc 4 (receipt written binding new head but refused by drift check).
- Ownership matrix 8/8 (ownership-matrix.jsonl): O1 same-process nested (inner -k selection, 1 inner test) — inner wrote nothing (asserted path absent at inner return), outer receipt = outer scope only (passed=2); O2 inner failure isolated (outer receipt failed=0 exit 0); O3 subprocess inherited env blocked, no stray receipts; O4 fresh subprocess (owner cleared + own path) = new owner, both receipts correct; O5 sequential same-process: claim released per run (owner_after None), same-path second run write fails with 收据未写出 warning, first receipt byte-identical (immutability); O6 configure failure (UsageError after claim) exit 4, no receipt, claim released, next run claims+writes; foreign pre-set owner never cleared, no claim/no write; O7 path switch mid-run: no receipt anywhere, gate rc 4; O8 simultaneous gates (rendezvous-verified overlap): 2 receipts, correct targets/counts.
- Note: receipt target = positional args only (config.args); -k not captured. Ownership does not depend on target (env+stash), confirmed by O1.
- pytest 8.3.5 cleanup semantics verified in source: wrap_session finally -> _ensure_unconfigure -> cleanups run even when _do_configure raises (initstate<2 skips sessionfinish). Matches O6.

## NEXT: board probes (B1), backfill probes (F1/F2), formal tests

# Ownership v3 — offline independent-review input (not submitted)

No new external model request, paid review, or automatic queue submission has
been authorized or started. This document is not an independent verdict.

## Frozen object

- Base: `728f327160bbd2485cb635e7ef09d040d718d7b5`
- Combined candidate: `47530e20fe5c3195e50ce429b31898d57918e413`
- Candidate checkout: `/Users/a77/fwp-wt-ownership-gates-v3-0921`
- Included source heads: #812 `6c74fa012b1cc79168b72368e262775b66df70f7`,
  #813 `5994230dadcf23ec0a17c0b27e3a649d782ecf94`,
  #814 `cdf6647cfe852bd19c23df0408b4bc2af306da6f`.
- Project interpreter: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`.
- Behavioral delta from v2 `e1b63b1a`: only `scripts/main_gate_receipt.py` and
  `tests/test_main_gate_receipt.py`. Other differences are existing archive /
  handoff documentation from the included heads.

## Contracts and negative controls

1. Board: failed queries and unavailable/locked/prunable roots stay unknown;
   baseline is pinned throughout a scan; clean or patch-equivalent is not
   deletion permission.
2. Receipt: one immutable output per invocation; latest is navigation only;
   descendants cannot claim a parent's receipt. Revision, interpreter, tree,
   dirty state, counts and failures are checked. A real process exit is an
   additional check only when a process ran; its absence must not bypass tree
   identity on receipt-only readback. Baseline/allow-dirty do not waive identity.
3. Backfill: fixed 302132 stock/window/keys, independent frozen oracle,
   protected slices unchanged, staged parent/backup/publish contracts, and
   rejection of a parent `--db` argument before side effects.
4. Retrieve the original backfill contract with
   `git show 849396d9:docs/handoffs/2026-09-14-302132-prep-review.md`.
   Historical production observations in that document are not current facts.

Relevant formal tests: `tests/test_worktree_board.py`,
`tests/test_main_gate_receipt.py`, `tests/test_test_receipt_dirt.py`,
`tests/test_check_receipt_revision_gate.py`,
`tests/test_check_receipt_zero_count_gate.py`,
`tests/test_repair_backfill_stock_history.py`, and
`intelligence/tests/test_pytest_collection_scope.py`.

The new regression was first observed on the unchanged v2 checkout, then
transferred into the formal tests: seven assertion failures on the old source,
56 related passes after the patch, and a clean fixed-source gate for `cdf6647cf`.
Those are producer tests, not independent Spec/Quality approval. Full v3 leaf
results, when complete, are indexed by this directory's README and manifest;
never infer a gate result from the existence of this input package.

## Authority boundaries

Use a separate exact checkout and place probes outside it. No modification of
frozen candidate/producer trees, production database read/write, external data
request, real backfill, Arena remote-agent run, service switch, main merge,
worktree deletion, or new model review is authorized by this input file.

Arena #816 is a separate candidate with an existing offline NO-GO finding; it
is not included in this combination. Approval cannot be transferred between
the two. A real full-clone backfill rehearsal still needs separately frozen
inputs, storage/backup checks and authorization. Main or code drift requires a
new candidate and new receipts; v1/v2 historical results remain unchanged.

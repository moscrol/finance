# Offline Independent Review Input (Not Submitted)

No model request has been sent. This file is not an authority-bearing ARL request and must not be moved into an automatic review queue without authorization and a bounded cost/time budget.

## Frozen Object

- Repository: finance-workspace-private
- Base: `728f327160bbd2485cb635e7ef09d040d718d7b5`
- Combined candidate: `321712b68732eef3512da80a4aaedfecd2a9c950`
- Isolated checkout: `/Users/a77/fwp-wt-ownership-gates-0921`
- Source candidates: board `49169f7ef95561d4c1006342367aee314dbb5f0f`, backfill `49f32259ea5aab495ae928e63e73c453cd31fae4`, receipt gate `013289c2ae23fb2519646f18a90cb4a379d596d5`.
- Full behavioral diff: `git diff 728f3271 321712b6 -- conftest.py scripts/ market_feature_store/ tests/`
- Python: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`

## Contracts To Verify Separately

### Spec

1. Worktree reporting: errors, missing roots, failed baseline/count/enumeration/status queries, document-only dirt, locked/prunable registrations must not become clean/removable facts. A scan and SessionStart use a fixed base SHA. Patch equivalence does not authorize deletion.
2. Receipt gate: one immutable output belongs to one invocation; a competing latest writer, missing current receipt, interrupted/zero-count run, failure readback, wrong revision/tree/process exit and dirty state must be refused. A baseline comparison is diagnostic, never release authorization.
3. 302132: only the fixed stock/window/write-key scope; staged parent with pre-swap backup; expected-empty derived semantics; protected slices including timestamps unchanged; correct source-independent oracle; complete/deep receipt schema and external input identity. Parent must refuse an ignored `--db` target.
4. Original backfill contract is not in the current main checkout. Retrieve the immutable source with `git show 849396d9:docs/handoffs/2026-09-14-302132-prep-review.md`; distinguish its historical measurements from today's input state. No live data access is authorized by this request.

### Quality

Inspect the implementation independently; try boundary and negative controls rather than accepting the producer's counts. Relevant test paths:

- `tests/test_worktree_board.py`
- `tests/test_main_gate_receipt.py`
- `tests/test_test_receipt_dirt.py`
- `tests/test_check_receipt_revision_gate.py`
- `tests/test_check_receipt_zero_count_gate.py`
- `tests/test_repair_backfill_stock_history.py`

Check the gate's positive path as well as rejections. Raw historical logs are evidence and contain original whitespace/ANSI; do not normalize them to make a whole-diff whitespace check green. Code-only diff check must pass.

## Authority And Side Effects

Use a separate detached checkout of the exact candidate. Do not change the candidate or producer trees; write findings/probes only outside them. No merge, production DB access/write, service switch, external data request, worktree deletion or model benchmark is authorized. A new review needs its own authorization/budget. Same-context producer review cannot grant independent PASS.

## Remaining Operational Boundary

Synthetic artifact acceptance and code gates are not a current full-clone rehearsal with real frozen inputs. Before real backfill, re-freeze the production baseline, source parquet/hash, sufficient disk/backup retention, true parent-child staging execution, failure-not-published and recovery behavior. Main drift or any source change invalidates the combined candidate as an exact merge gate.

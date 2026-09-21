## Scope

Fix the test receipt path/identity defect discovered while validating #813. This is a separate infrastructure change, not a backfill or runtime change.

Code candidate: `013289c2ae23fb2519646f18a90cb4a379d596d5`.

- The gate allocates a unique `gate-*/pytest.json` path and the pytest hook honors it and `FWP_TEST_RECEIPT_DIR`.
- Run receipts use exclusive creation; default filenames include a random suffix. `latest.json` is atomic navigation only.
- Readback rejects mismatched revision/tree/process exit, wrong interpreter, dirty/unknown state, bypassed dependency checks, incomplete runs, invalid counts and zero executed tests.
- Explicit baseline comparison remains diagnostic and does not authorize a merge with failing tests.
- Test fixture runs real pytest and overwrites only `latest.json` after the legitimate hook; the gate must still use its own result.

## Verification

Author checks before commit: 47 related tests passed, whole-repository Ruff and shell syntax passed. The first old-code run had 21 failures / 1 pass, including 2 new-helper absence failures; these are not 21 independent semantic findings.

Frozen combined candidate `321712b68732eef3512da80a4aaedfecd2a9c950` contains this code plus #812 at `49169f7e` and #813 at `49f32259`. Complete gate evidence is being collected at `~/.finance-runtime/reviews/ownership-followup-20260921/`; final results will be posted in a follow-up comment.

WIP: no independent review verdict, no merge authorization, no production switch, no real backfill, no worktree deletion. The current fixed main baseline is `728f327160bbd2485cb635e7ef09d040d718d7b5`.

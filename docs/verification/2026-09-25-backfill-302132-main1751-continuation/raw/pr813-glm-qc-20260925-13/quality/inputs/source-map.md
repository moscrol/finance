Precise source pointers, not conclusions:
- market_feature_store/cli.py lines 1561-1755: parent and child command.
- market_feature_store/sync/repair_backfill_stock_history.py: fixed contract, guard, apply, scoped derivation, accept.
- scripts/verify_302132_backfill_acceptance.py: deep receipt verification and bidirectional EXCEPT ALL.
- scripts/review_probes/rehearse_302132_backfill.py: isolated full-copy run, negative controls and rollback.
- tests/test_repair_backfill_stock_history.py lines 628-755: three bounded OS mocks.
- inputs/fixture-manifest.json: real production-date subset, not a full-copy execution.
- inputs/host-rehearsal/: current revision's raw host full-copy receipt set, not independent execution.
Two supplied C3 entrypoints and their two dependencies are in work/probes. Prior reviewer assertions plus host fixture fixes, not current-model-authored tests.

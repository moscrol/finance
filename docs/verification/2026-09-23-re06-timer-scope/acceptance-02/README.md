# Fixed f9ce5c6b2 Acceptance 02: Artifact Drift

- Candidate: `f9ce5c6b296492b423400ad66d333784a4be13bc`.
- Baseline: `ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb`.
- Runtime: `/Users/a77/.finance-runtime/reviews/re06-timer-scope-acceptance-20260923-02`.
- Overall: `BLOCKED_ARTIFACT_IDENTITY_DRIFT`; not mergeable.

The frontend commands completed: install, lint, typecheck, 122 unit tests, and build. The official frontend receipt nevertheless failed because build changed tracked shipping files. The next leaf's fixed-identity assertion stopped the controller. E2E, registry, and Python were not started in this attempt. The raw incomplete controller receipt and traceback are preserved; no terminal exit code has been invented.

## Finding and Successor

The committed HTML referenced `index-o4AWiRNg.js`, which contained `workbench-activity-v1`. Rebuilding the committed source produced `index-BobixB9S.js`, containing `workbench-activity-v2` and `activity-timer`. This contradicts C7's shipping-protocol claim; it is not a claim that a production deployment was changed or that stopping the timer was dynamically observed disabling measurement.

Build output was preserved outside the worktree, then only this run's generated changes were restored/removed. The original author candidate is clean at its original revision. A separate branch, `fix/re06-timer-assets-0923`, commits only the generated asset replacement and HTML reference as `b24c86f87aaef6244dc6a2c6cf80f74ae1918943`. No business source was edited. See `artifact-drift.json` for hashes and exact paths. This attempt's receipts do not sign that successor.

## Archive

`manifest.json` maps 14 original files to exact SHA256/length and reversible representations. Scripts use `.py.txt`; JSON receipts are unchanged. Logs use `gzip-base64-chunks`: concatenate decoded chunk data in manifest order, decompress gzip, then verify raw length/SHA256. The archiver verifies reconstruction byte for byte before completing the manifest. Generated bundles are not duplicated here; the successor Git commit contains them, and their hashes remain in `artifact-drift.json`.

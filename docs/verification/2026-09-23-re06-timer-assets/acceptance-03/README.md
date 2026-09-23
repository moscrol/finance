# Acceptance 03: PASS at b24c86f87

Candidate `b24c86f87aaef6244dc6a2c6cf80f74ae1918943`; baseline `ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb`.

- Python: Ruff PASS; 14760 collected, 14673 passed, 0 failed/errors, 85 skipped, 2 xfailed. Full JUnit agrees with `receipts/pytest.json`; `main_gate_receipt.py` returned 0.
- Frontend: frozen install, lint, typecheck, 122 unit tests, build PASS.
- E2E: this leaf built its own candidate, then 34 passed / 2 skipped.
- Registry: all five commands PASS.
- Candidate identity stayed fixed and clean. No production/real-model acceptance authorization was given to these test leaves. This is not #76/P7 or main integration acceptance.

`receipt.json` retains per-leaf resource admissions and actual commands. `acceptance-summary.json` is a derived summary, not a replacement receipt. The pytest terminal duration was 1654.98 seconds; controller duration includes process overhead. Neither reached the 3600-second budget. E2E ports 29701/29704 were later checked closed.

The manifest covers 29 original files in 31 encoded files, including complete JUnit, immutable Python receipt, frontend/E2E receipts, logs, and actual runner bytes. Shared/latest receipt aliases and fixture databases are excluded. Large XML/logs are reversibly gzip/base64 encoded; `archive_evidence.py.txt` provides `decode()` and `verify()`.

The raw credential-pattern scan found one nonsecret JWT-shaped test parameter. Its exact digest is exempted only after locating the committed literal in `tests/test_smoke_workbench_self_use.py:495` and verifying that its signature decodes to `testsignature`. The manifest records that provenance; no operational credential was exempted or redacted. The original JUnit is preserved byte for byte.

Engineering PASS does not close independent QC. See the parent report for the separate blockers.

# Cutoff / Local Snapshot Follow-up

Verdict: **AUTHOR_ENGINEERING_CHECKS_PASSED_ACCEPTANCE_BLOCKED**.

## Fixed Candidate

- Revision: `53054bfd4336bebd0d570273a58e92758fb623be`
- Tree: `2aa8e01864722bd6a659a672e9cd76813f398eeb`
- Python: `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`, 3.12.13; dependency fingerprint `3328bed61f3e21ea`.
- No push, PR, merge, deployment, data collection, backfill or production database write. No 8792 request this round. Later main integration is untested.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Full Python | Ruff 0; 12594 passed, 87 skipped, 2 xfailed, 17 warnings; no failures/errors | `python/run.json`, `python/junit.xml`, `python/pytest-receipt.json` |
| Exact pytest receipt | `20260921T185949Z-53054bfd.json`; SHA256 `c340686b32bd79a7b01d6226cd607a924d098d430ecad30935bbc705e1d65da1` | Original path is in `python/run.json` |
| Frontend | install/lint/typecheck/test/build/E2E all exit 0; 110 unit passes; 34 E2E passes / 2 skips | `frontend/gate/frontend.json` |
| Registry | Five checks exit 0 | `registry/run.json` |
| Original mutation set | 24/24 caught, passing baselines, assertion failures, no setup/collection errors | `mutations/result.json` |
| New authorization test, single guard removed | Baseline 1P / mutant 1P; NOT caught; final local-only capability filter still protects menu | `switch-mutation/result.json` |
| New authorization test, both guards removed | Baseline 1P / mutant 1F / 0 errors; caught | `switch-mutation-two-guards/result.json` |
| Spec / Quality independent review | Both unavailable: account usage limit, exit 1, no verdict file | `spec-review/`, `quality-review/` |
| New K3 live acceptance | Not started; independent review prerequisite unresolved | No new conversations or sidecar |

All completed fixed-candidate checks have clean stable before/after identities. The full Python waiter waited for other pytest processes to finish, then admitted with 61,196,931,072 free bytes and no other pytest process. Its 3GiB running floor was not lowered. Processes finished; ports 19651/19654/19276 had no listeners at closure.

## Retained Failures And Repair

The preceding clean revision `4cf5a33ad0ea017da330533f1e284bc4d91041e8` produced 12591P / 2F / 87S / 2X. It remains a failed full gate. One failure was the author's missing local snapshot row in the offline switchboard; the new commit adds that row, regenerates the default box, and tests removal of final authorization. The other failure was reproduced by omitting uvx from PATH: the same source/index returns 0 structure hits with the old PATH and 20 with the declared PATH. No assertion was skipped or weakened.

The first new test fixture was invalid because required_outputs still named the removed capability (1F/92P/3S); fixing the fixture yielded 93P/3S on a dirty development tree. These receipts are retained but are not fixed-candidate acceptance. Earlier b1/f7 archives are unchanged. See `errata.md` for chronology and diagnostic-command corrections.

## Limits And Next Step

Independent review is unavailable, not passed. The prior real Workbench K3 run remains `AUTHOR_REAL_ENTRYPOINT_OBSERVED_NOT_ACCEPTED`; offline checks do not certify answer quality. Finite date grammar is not complete natural-language or publication-time correctness. The market question routing issue and later-main combination remain unverified. No natural nightly or production effectiveness claim.

Resume with independent Spec/Quality review on an identified clean revision. Only after prerequisites pass, bind a fresh K3 writer / GLM judge runner to the exact revision and use the two original conversations/messages questions. The pre-existing runner copy with old identity must not be executed. Inspect durable private Episode events for actual prompt capture and verify hashes; source support is not proof that an old run captured it.

This package preserves raw text originals including failures. Fixtures/caches/binaries stay external and are listed as exclusions. Scripts/logs are frozen with .txt suffixes. Secret pattern matches require exact context classification; zero unclassified matches does not mean zero pattern hits. Verify the committed package with `scripts/check_evidence_archive.py`, not local hashes alone.

# EXECUTE.md — PR #813 C2 (source guard) isolated axis

Revision 3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59, baseline 4cc15e703f81bce8abadee00f68caacdb0c72b4d.

## Commands
1. Positive control: `python -B .../work/positive_control.py` → exit 1, `AssertionError: intentional probe_bug control` (OBSERVED_EXPECTED_FAILURE, recorded separately, excluded from counts).
2. Syntax check v2 probe via ast.parse (`work/syntax_check_v1.py`): SYNTAX_OK.
3. Reviewer probes: `pytest .../probes/test_c2_source_guard_v2.py -v --confcutdir=work -p no:cacheprovider --junitxml=work/probe-results-v1.xml` → **5 passed** (2.31s).
4. Author test (single relevant): `pytest candidate/tests/...::test_backfill_keeps_frozen_tail_source_after_parallel_table_advances` → **1 failed**, `work/author-results-v1.xml`.

## Probe results (5/5 passed)
- later 'none' history beyond max(gap_parallel) (CAL[27..29] injected): `_guard` returns mode=apply (no false refusal); injected rows outside authorized source window (src_a ends at max(gap_parallel)).
- qfq flip on gap date (CAL[3]): run_backfill_child → RepairRefused, main table byte-identical.
- tampered frozen parquet (bit flip): RepairRefused via sha256 mismatch, main unchanged.
- partial gap state (gap day pre-inserted in main): RepairRefused, no child writes.
- spec parquet_sha256 mismatch (dataclasses.replace): RepairRefused, main unchanged.

## Author test result
Failure cause: `_code_revision` (repair_backfill_stock_history.py:120-126) runs `git rev-parse HEAD` in candidate dir; sandbox denies `.git` access → RepairRefused "代码 revision 绑定失败". Environment artifact of the no-git review sandbox, not a product defect; C2-relevant behavior (guard refusal ordering) already covered by my probes, which raise inside `_guard` before `_code_revision`.

## Notes
- Explored-stage probe file (probes/test_c2_source_guard.py) was never executed; v2 is a cleaned rewrite (removed dead `if False else None` drafting statements, tightened assertions, removed redundant duplicate-row insert). Both files retained.
- Fixture reuse: author `_fixture`/`_spec`/`_insert` construction only; no author assertions reused.

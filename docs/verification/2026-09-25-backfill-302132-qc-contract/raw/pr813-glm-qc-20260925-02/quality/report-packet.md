# Immutable evidence packet
No reasoning transcript or other-axis results included.
Raw command output is authoritative. Prior-stage prose may contain errors: never promote a proposed correction or unsupported PASS label to an observed result. Missing evidence must remain explicit.


## explore/parsed.json
```text
{
  "claims": [
    {
      "id": "C1",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    },
    {
      "id": "C2",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    },
    {
      "id": "C3",
      "evidence": "Static review observed: scripts/verify_302132_backfill_acceptance.py _data_checks (540-728) uses bidirectional EXCEPT ALL over ALL columns (multiset semantics) for other stocks (fact_other_stocks_allcols), outside-window target rows (target_outside_window_allcols), retained in-window rows full-column equality incl. updated_at, plus keyset_fullfield_oracle for written rows. Probe written at quality/work/probes/probe_c3_acceptance.py covering baseline pass and amount/timestamp/delete/insert/duplicate(PK-removed clone)/other-stock mutations, but NO execution tool was available (only read/write/deliver_stage), so no run evidence; full claim remains unverified.",
      "status": "not_verified"
    },
    {
      "id": "C4",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    },
    {
      "id": "C5",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    },
    {
      "id": "C6",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    },
    {
      "id": "C7",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    }
  ],
  "claims_examined": [
    "C3"
  ],
  "findings": [
    {
      "detail": "验收脚本以双向 EXCEPT ALL 全列多重集比较覆盖他股、窗外目标行、保留行、源表与派生特征表，静态上支持 C3 的全列多重集语义表述；但本轮无命令执行能力（仅 read/write/deliver_stage），无法运行探针或验收脚本，缺少独立执行证据。",
      "severity": "info",
      "title": "静态结构支持 C3，但未执行"
    }
  ],
  "limits": "本沙箱仅暴露 read/write/deliver_stage 工具，无 bash/execute 能力：探针（含意图失败正控）均未执行，EXPLORE.md 中命令为待执行命令而非已运行记录。探针文件 work/probes/probe_c3_acceptance.py 已写好，复用作者 _build_e2e_artifacts 夹具但断言全部为审查者自有；duplicate 变异采用 clone-only CREATE TABLE AS SELECT 移除主键以构造真实重复行（已在 EXPLORE.md 披露）。另写有无害占位文件 work/probes/.placeholder 与 work/notes.txt。合成 DuckDB、无生产副本运行、无 git/网络。C3 只能记 not_verified，不能视为 PASS。",
  "next_stage_commands": [
    "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py -q --deselect /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py::test_positive_control_intentional --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.xml",
    "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py::test_positive_control_intentional -q --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_positive_control.xml"
  ],
  "positive_control": {
    "classification": "probe_bug",
    "evidence": "Not executed: no command-execution tool available in this stage sandbox; intentional-control test exists in probe_c3_acceptance.py (test_positive_control_intentional) awaiting run.",
    "status": "NOT_RUN"
  },
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py"
  ],
  "reviewer_probe_counts": {
    "errors": 0,
    "executed": 0,
    "failed": 0,
    "passed": 0,
    "skipped": 0
  },
  "verdict": "BLOCKED_INCOMPLETE_EVIDENCE",
  "complete": true,
  "stage": "explore",
  "axis": "quality",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}

```


## execute/parsed.json
```text
{
  "author_test_counts": {
    "errors": 0,
    "executed": 0,
    "failed": 0,
    "passed": 0,
    "skipped": 0
  },
  "claims": [
    {
      "id": "C1",
      "status": "out_of_scope",
      "evidence": "Only C3 assigned to this axis; not examined."
    },
    {
      "id": "C2",
      "status": "out_of_scope",
      "evidence": "Only C3 assigned to this axis; not examined."
    },
    {
      "id": "C3",
      "status": "not_verified",
      "evidence": "Static review: scripts/verify_302132_backfill_acceptance.py _data_checks (540-728) uses bidirectional EXCEPT ALL over all columns (multiset) for other stocks (fact_other_stocks_allcols) and outside-window target rows (target_outside_window_allcols), plus retained-row full-column equality and keyset_fullfield_oracle. Reviewer probe work/probes/probe_c3_acceptance_v2.py (baseline PASS + amount/timestamp/delete/insert/duplicate(PK-removed clone CTAS, disclosed)/other-stock mutations against an outside-window 2026-09-22 row) was syntax-checked (ast.parse, syntax_check_v2.py) but NEVER EXECUTED: stage closed before pytest run. No reviewer execution evidence for any subcase; per rules full claim stays not_verified."
    },
    {
      "id": "C4",
      "status": "out_of_scope",
      "evidence": "Only C3 assigned to this axis; not examined."
    },
    {
      "id": "C5",
      "status": "out_of_scope",
      "evidence": "Only C3 assigned to this axis; not examined."
    },
    {
      "id": "C6",
      "status": "out_of_scope",
      "evidence": "Only C3 assigned to this axis; not examined."
    },
    {
      "id": "C7",
      "status": "out_of_scope",
      "evidence": "Only C3 assigned to this axis; not examined."
    }
  ],
  "claims_examined": [
    "C3"
  ],
  "findings": [
    {
      "detail": "验收脚本 _data_checks(540-728) 结构上以双向 EXCEPT ALL 全列多重集比较覆盖他股、窗外目标行、保留行与写出行，与 C3 表述一致；但审查者探针未在期限内执行（仅 ast.parse 语法检查通过），缺少基线必绿与六类变异必红的独立运行证据，C3 记 not_verified。",
      "severity": "info",
      "title": "静态支持但缺执行证据"
    }
  ],
  "limits": "本阶段已消耗请求额度，closeout 指令要求立即交付：探针套件未运行，EXECUTE.md 未写。正控 positive_control.py 首命令运行，exit1，assert 1==2 'intentional probe_bug control'，作为独立正控记录（不计入审查者计数）。早期探索阶段（parsed.json）曾写 v1 探针但同样未执行。探针 v2 修复了 v1 缺失 sys.path 候选根目录导致的导入问题。合成 DuckDB only，未运行生产副本，无 git/网络/凭证/部署；夹具复用作者 _build_e2e_artifacts（返回 baseline/clone/pq/spec/receipts/base_sha），断言全部为审查者自有；duplicate 变异以 clone-only CTAS 去除主键构造真实重复行（披露：真实 PK 本身会阻止重复）。当前 main 未集成；本交付非 PASS，不构成合并或生产授权。",
  "positive_control": {
    "classification": "probe_bug",
    "evidence": "First command: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B .../quality/work/positive_control.py -> AssertionError: intentional probe_bug control, exit code 1.",
    "status": "OBSERVED_EXPECTED_FAILURE"
  },
  "reviewer_probe_counts": {
    "errors": 0,
    "executed": 0,
    "failed": 0,
    "passed": 0,
    "skipped": 0
  },
  "verdict": "BLOCKED_INCOMPLETE_EVIDENCE",
  "complete": true,
  "stage": "execute",
  "axis": "quality",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}

```


## work/EXPLORE.md
```text
# QC probe C3 (PR #813) — acceptance oracle for outside-window rows

## Scope
Only C3. Challenge the actual external acceptance entry
`candidate/scripts/verify_302132_backfill_acceptance.py::main -> _data_checks`
(not just writer `_accept`).

## Probe
`work/probes/probe_c3_acceptance.py` (single pytest file). Reuses fixture helper
`tests/test_repair_backfill_stock_history.py::_build_e2e_artifacts` (synthetic
DuckDB, module-level import via importlib spec_from_file_location, registered in
sys.modules before exec_module) and its `_run_acceptance` command shape. ALL
assertions are the reviewer's own; author test bodies are not executed and author
result claims are not reused.

Mutations applied to an OUTSIDE-window row (date 2026-09-22 inserted into BOTH
baseline and clone first, receipts' backup sha updated — same mechanics as the
author fixture):
- `none` → baseline must PASS (rc=0, verdict PASS, failed==[])
- `amount` (+1), `timestamp` (updated_at change), `delete`, `insert` (2026-09-23
  duplicate of same stock), `duplicate` (exact copy of 2026-09-22 row in clone
  only — needs PK dropped via clone-only `CREATE TABLE AS SELECT` rebuild;
  DISCLOSED: this removes the PK constraint so a true duplicate can exist; the
  real DB PK would itself block duplicates, so this is an adversarial oracle
  probe, not a realistic production state), `other_stock` (amount mutation on
  000001.SZ row) → each must FAIL with rc=2, structured FAIL JSON, and the
  specific data check (`target_outside_window_allcols` or
  `fact_other_stocks_allcols`) in `failed`.

## Commands (exact)
- Execute:
  `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py -q --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.xml`
- Positive control (intentional control): same file with
  `--control=positive` via env `QC_POSITIVE_CONTROL=1` (a deliberately broken
  expectation asserts a FAIL check that actually passes) — must FAIL, proving
  the harness can detect green-when-should-be-red.

## Known limits
- Synthetic fixture only; no production copy run (not authorized).
- Author's `window 64 rows / technical39 / window161` specific counts are the
  real-revision shape; synthetic fixture has different calendar, so those
  numeric counts are not independently reproduced here.
- Duplicate-multiplicity probe requires removing PK in the clone only.

```


## work/EXECUTE.md
MISSING: not delivered by previous stage. No substitute was authored.


## execute/commands/001-bash/output.log
```text
Traceback (most recent call last):
  File "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/positive_control.py", line 1, in <module>
    assert 1 == 2, "intentional probe_bug control"
           ^^^^^^
AssertionError: intentional probe_bug control

```


## execute/commands/001-bash/request.json
```text
{"toolCallId":"call_31118258e44b42d38bcf3589","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/positive_control.py"}}
```


## execute/commands/001-bash/result.json
```text
{"exitCode":1}
```


## execute/commands/002-bash/output.log
```text
{
  "claims": [
    {
      "id": "C1",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    },
    {
      "id": "C2",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    },
    {
      "id": "C3",
      "evidence": "Static review observed: scripts/verify_302132_backfill_acceptance.py _data_checks (540-728) uses bidirectional EXCEPT ALL over ALL columns (multiset semantics) for other stocks (fact_other_stocks_allcols), outside-window target rows (target_outside_window_allcols), retained in-window rows full-column equality incl. updated_at, plus keyset_fullfield_oracle for written rows. Probe written at quality/work/probes/probe_c3_acceptance.py covering baseline pass and amount/timestamp/delete/insert/duplicate(PK-removed clone)/other-stock mutations, but NO execution tool was available (only read/write/deliver_stage), so no run evidence; full claim remains unverified.",
      "status": "not_verified"
    },
    {
      "id": "C4",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    },
    {
      "id": "C5",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    },
    {
      "id": "C6",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    },
    {
      "id": "C7",
      "evidence": "Out of scope for this isolated C3 axis.",
      "status": "out_of_scope"
    }
  ],
  "claims_examined": [
    "C3"
  ],
  "findings": [
    {
      "detail": "验收脚本以双向 EXCEPT ALL 全列多重集比较覆盖他股、窗外目标行、保留行、源表与派生特征表，静态上支持 C3 的全列多重集语义表述；但本轮无命令执行能力（仅 read/write/deliver_stage），无法运行探针或验收脚本，缺少独立执行证据。",
      "severity": "info",
      "title": "静态结构支持 C3，但未执行"
    }
  ],
  "limits": "本沙箱仅暴露 read/write/deliver_stage 工具，无 bash/execute 能力：探针（含意图失败正控）均未执行，EXPLORE.md 中命令为待执行命令而非已运行记录。探针文件 work/probes/probe_c3_acceptance.py 已写好，复用作者 _build_e2e_artifacts 夹具但断言全部为审查者自有；duplicate 变异采用 clone-only CREATE TABLE AS SELECT 移除主键以构造真实重复行（已在 EXPLORE.md 披露）。另写有无害占位文件 work/probes/.placeholder 与 work/notes.txt。合成 DuckDB、无生产副本运行、无 git/网络。C3 只能记 not_verified，不能视为 PASS。",
  "next_stage_commands": [
    "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py -q --deselect /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py::test_positive_control_intentional --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.xml",
    "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py::test_positive_control_intentional -q --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_positive_control.xml"
  ],
  "positive_control": {
    "classification": "probe_bug",
    "evidence": "Not executed: no command-execution tool available in this stage sandbox; intentional-control test exists in probe_c3_acceptance.py (test_positive_control_intentional) awaiting run.",
    "status": "NOT_RUN"
  },
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py"
  ],
  "reviewer_probe_counts": {
    "errors": 0,
    "executed": 0,
    "failed": 0,
    "passed": 0,
    "skipped": 0
  },
  "verdict": "BLOCKED_INCOMPLETE_EVIDENCE",
  "complete": true,
  "stage": "explore",
  "axis": "quality",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}
# QC probe C3 (PR #813) — acceptance oracle for outside-window rows

## Scope
Only C3. Challenge the actual external acceptance entry
`candidate/scripts/verify_302132_backfill_acceptance.py::main -> _data_checks`
(not just writer `_accept`).

## Probe
`work/probes/probe_c3_acceptance.py` (single pytest file). Reuses fixture helper
`tests/test_repair_backfill_stock_history.py::_build_e2e_artifacts` (synthetic
DuckDB, module-level import via importlib spec_from_file_location, registered in
sys.modules before exec_module) and its `_run_acceptance` command shape. ALL
assertions are the reviewer's own; author test bodies are not executed and author
result claims are not reused.

Mutations applied to an OUTSIDE-window row (date 2026-09-22 inserted into BOTH
baseline and clone first, receipts' backup sha updated — same mechanics as the
author fixture):
- `none` → baseline must PASS (rc=0, verdict PASS, failed==[])
- `amount` (+1), `timestamp` (updated_at change), `delete`, `insert` (2026-09-23
  duplicate of same stock), `duplicate` (exact copy of 2026-09-22 row in clone
  only — needs PK dropped via clone-only `CREATE TABLE AS SELECT` rebuild;
  DISCLOSED: this removes the PK constraint so a true duplicate can exist; the
  real DB PK would itself block duplicates, so this is an adversarial oracle
  probe, not a realistic production state), `other_stock` (amount mutation on
  000001.SZ row) → each must FAIL with rc=2, structured FAIL JSON, and the
  specific data check (`target_outside_window_allcols` or
  `fact_other_stocks_allcols`) in `failed`.

## Commands (exact)
- Execute:
  `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py -q --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.xml`
- Positive control (intentional control): same file with
  `--control=positive` via env `QC_POSITIVE_CONTROL=1` (a deliberately broken
  expectation asserts a FAIL check that actually passes) — must FAIL, proving
  the harness can detect green-when-should-be-red.

## Known limits
- Synthetic fixture only; no production copy run (not authorized).
- Author's `window 64 rows / technical39 / window161` specific counts are the
  real-revision shape; synthetic fixture has different calendar, so those
  numeric counts are not independently reproduced here.
- Duplicate-multiplicity probe requires removing PK in the clone only.
Only C3 is in scope for this isolated axis. Every other claim MUST be out_of_scope. Current main 03352758cf9b31e3f5d179b517be48cb89588679 is not integrated. Full-candidate approval is not sought.

# PR #813 / Workorder #83: claims to challenge, not established conclusions

C1 Fixed mutation contract: only 302132.SZ, 2026-06-15..2026-09-11; 53 INSERTs (51 parallel dates plus frozen parquet 09-09/09-10), UPDATE the 06-23 shell; preserve pinned 09-11. No widened keys or substituted source.
C2 Source guard: parallel history upper boundary is max(spec.gap_parallel), h.adjusted='none'; valid later history does not cause false refusal or enter the authorized source. Bad, partial or mismatched input refuses before publication.
C3 Acceptance oracle: preserved rows are evaluated inside the authorized window, while target rows outside it and other stocks retain ALL columns with multiset semantics. Detect amount, deletion, insertion and timestamp mutations, not just row counts. Window after apply: 64 rows, close/pct_chg/amount each 64 nonnull; technical39/window161.
C4 Parent command owns staging/publication/backup and verify-only semantics. Locks, identity, input hash, published target, refusal receipts and recovery guards must be internally coherent; no second production writer path. Assess correctness in scope, not a full unrelated security audit.
C5 Rehearsal is isolated and resource bounded: reject unsafe identity/WAL/low-space state before side effects; apply, verify, 37 acceptance checks, wrong parquet rejection, amount=1e15 negative control, restore matching baseline, production read-only/unchanged. Author's archived full-copy run is an evidence claim, NOT a fresh reviewer run.
C6 Shared OS mocks in three tests are confined to monkeypatch.context(); real open is restored before pytest cleanup. Restoring the old scope must be caught by a regression witness. Neutral temp path avoids E_STOCK_SCOPE interference, not a product fix for that separate known limitation.
C7 Evidence is bound to this clean 3c5 revision/base4cc, never transferred from old fd6/ca4. Author gates are 15457P/85S/2X (15544 collected), focused118P, frontend120P/E2E34P+2S, registry5 green, rehearsal37PASS. This means engineering ready only: independent QC, merge consent, and production command/backup authorization are separate; no production use is authorized.

Source pointers and raw evidence are in this inputs directory. All counts above are author assertions to verify against artifacts. Do not claim you independently reran the full suite or production-copy rehearsal. No live vendor calls, production reads/writes, merge, deployment or service restart.

## market_feature_store/sync/repair_backfill_stock_history.py
BackfillSpec: 87-107
_fail: 110-111
_code_revision: 117-129
_validate_receipt_path: 132-149
_guarded_write_json: 152-183
_finite: 186-193
_sha256: 196-201
_oracle_pct: 209-213
_oracle_amount: 216-218
_oracle_volume: 221-223
_slice_fingerprint: 226-235
_guard: 239-381
_apply_main: 385-480
_rebuild_derived_scoped: 484-589
_accept: 593-722
run_backfill_child: 725-776

## scripts/verify_302132_backfill_acceptance.py
_sha256: 110-115
_is_date: 118-126
_is_num: 129-136
_is_int: 139-140
_validate_receipt: 143-335
main: 338-537
_data_checks: 540-728
req: 151-153
check: 357-358
sha_check: 360-369
_read_receipt: 407-418
xa: 551-562

## tests/test_repair_backfill_stock_history.py
_calendar: 34-40
_close: 46-47
_turnover: 50-51
_amount: 54-57
_epoch_ms: 60-62
_insert: 65-68
_fixture: 71-162
_spec: 165-217
test_backfill_keeps_frozen_tail_source_after_parallel_table_advances: 220-244
_others_snapshot: 247-254
_outside_snapshot: 257-266
env: 270-275
test_happy_path_scoped_rebuild: 278-307
test_rerun_idempotent_verify_mode: 310-329
test_refusals_fail_closed: 334-373
test_widened_delete_counterexample_caught: 376-395
test_oracle_matches_module_mapping: 398-417
test_refused_missing_retained_source_day: 426-434
test_refused_verify_corrupt_backfilled_fields: 438-447
test_refused_verify_source_label_swap: 450-459
test_refused_window_nontrading_start: 462-479
test_refused_pinned_updated_at_tamper: 482-498
_cli_args: 502-505
test_refused_cli_report_path_overwrites_canonical: 508-522
test_refused_cli_report_path_existing_file: 525-538
test_cli_parent_rejects_ignored_db_argument_before_side_effects: 541-566
test_cli_parent_preflight_blocks_unwritable_receipt_dir: 569-590
test_cli_child_receipt_binds_revision_and_run_id: 593-626
test_refused_receipt_write_failure_cleans_partial: 629-660
test_cli_parent_preflight_blocks_on_open_permission_error: 663-687
test_refused_cli_parent_report_path_never_deletes_user_file: 690-719
test_refused_receipt_eexist_race_keeps_other_writers_file: 722-743
test_acceptance_script_rejects_hardlink_alias: 746-778
test_acceptance_script_receipt_schema_mutation_fails: 781-836
_subprocess_env: 858-868
_build_e2e_artifacts: 871-916
e2e_art: 920-921
_run_acceptance: 924-934
_install: 937-950
_assert_structured_fail: 953-963
test_acceptance_e2e_baseline_pass: 966-972
test_acceptance_preserves_later_target_rows: 976-1023
test_acceptance_rejects_extreme_amount: 1026-1039
_set0: 1042-1043
test_acceptance_receipt_mutation_fails: 1165-1170
test_acceptance_is_num_is_total_for_json_numbers: 1187-1189
test_acceptance_rejects_spec_code_not_bound_to_sql_target: 1207-1218
test_acceptance_malformed_revision_fails: 1221-1232
test_acceptance_verify_other_parquet_fails: 1235-1248
test_acceptance_apply_other_parquet_fails: 1251-1264
test_acceptance_verify_spec_divergence_fails: 1267-1281
test_acceptance_db_mutation_fails: 1323-1335
main_row: 89-101
evil: 385-390
corrupt: 468-474
corrupt: 488-493
parent: 553-555
parent: 581-583
Bomb: 635-653
parent: 673-675
bomb: 677-678
parent: 705-707
racing_open: 730-735
mutate: 1210-1213
mutate: 1223-1225
mutate: 1237-1240
mutate: 1253-1256
mutate: 1270-1274
__init__: 636-637
__enter__: 639-640
__exit__: 642-644
write: 646-647
flush: 649-650
fileno: 652-653

```


## execute/commands/002-bash/request.json
```text
{"toolCallId":"call_6e907664290f4dd8a22238aa","params":{"command":"cat /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/phase-context/explore/parsed.json /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/EXPLORE.md /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/inputs/claims.md /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/inputs/source-map.md"}}
```


## execute/commands/002-bash/result.json
```text
{"exitCode":0}
```


## execute/commands/004-bash/output.log
```text
# 策略：好产物必绿（真实形状两轮产物 E2E PASS）+ 坏产物必红（逐字段单因素变异，
# 父收据与独立子报告同步修改，与审查探针 qc_302132_round6_probes.py 同构）。
import copy  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from dataclasses import asdict, replace  # noqa: E402
from unittest import mock  # noqa: E402

import scripts.verify_302132_backfill_acceptance as verify_acceptance  # noqa: E402

E2E_REV = "f" * 40
APPLY_RUN = "run-apply-001"
VERIFY_RUN = "run-verify-001"
SCHEMA_BOTH = ("receipt_apply_schema", "receipt_verify_schema")


def _subprocess_env() -> dict[str, str]:
    """子进程只接收测试所需白名单，避免宿主凭据进入失败输出。"""
    return {
        "HOME": os.environ.get("HOME", str(Path.home())),
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "FWP_TEST_RECEIPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(mod.PROJECT_DIR),
    }


def _build_e2e_artifacts(root: Path) -> dict:
    """完整可通过验收的两轮产物：基线库 + 结果库（apply/verify 各跑一遍）+
    冻结 parquet + 父收据/独立子报告（字段形状与 cli.py 实际写出一致）。"""
    baseline = root / "baseline.duckdb"
    pq = root / "tail.parquet"
    fx = _fixture(baseline, pq)
    spec = replace(_spec(baseline, pq, fx["pinned"]),
                   spec_version="302132-backfill-test-v1")
    clone = root / "clone.duckdb"
    shutil.copy(str(baseline), str(clone))
    children = {}
    with mock.patch.object(mod, "_code_revision",
                           return_value=(E2E_REV, False)):
        con = duckdb.connect(str(clone))
        try:
            for mode, rid in (("apply", APPLY_RUN), ("verify", VERIFY_RUN)):
                report = mod.run_backfill_child(con, spec, pq)
                assert report["mode"] == mode
                report.update({"run_id": rid, "trade_date": spec.window_end,
                               "kind": "repair-backfill-302132", "ok": True})
                # JSON 往返：内存中的产物形状与验收器读到的完全一致
                # （int 键 → str 键等），变异测试不会在假形状上操作
                children[mode] = json.loads(json.dumps(report))
        finally:
            con.close()
    base_sha = mod._sha256(baseline)
    receipts = {}
    for mode, rid in (("apply", APPLY_RUN), ("verify", VERIFY_RUN)):
        child_path = root / f"child-{mode}.json"
        child_path.write_text(json.dumps(children[mode], ensure_ascii=False))
        receipt = {
            "kind": "repair-backfill-302132", "trade_date": spec.window_end,
            "run_id": rid, "code_revision": E2E_REV, "code_dirty": False,
            "interpreter": sys.executable,
            "spec": json.loads(json.dumps(asdict(spec))),
            "child_report_path": str(child_path),
            "child_report": children[mode], "child_report_error": None,
            "backup": {"backup_path": str(baseline), "backup_sha256": base_sha,
                       "run_id": rid},
            "parent": {"swapped": True, "rc": 0, "run_id": rid},
        }
        (root / f"clone.duckdb.repair-backfill-execution.{rid}.json"
         ).write_text(json.dumps(receipt, ensure_ascii=False))
        receipts[mode] = receipt
    return {"baseline": baseline, "clone": clone, "pq": pq, "spec": spec,
            "receipts": receipts, "base_sha": base_sha}


@pytest.fixture(scope="module")
def e2e_art(tmp_path_factory):
    return _build_e2e_artifacts(tmp_path_factory.mktemp("e2e302132"))


def _run_acceptance(clone: Path, art: dict, out: Path,
                    expected_revision: str = E2E_REV):
    script = mod.PROJECT_DIR / "scripts" / "verify_302132_backfill_acceptance.py"
    return subprocess.run(
        [sys.executable, str(script), "--production", str(art["baseline"]),
         "--clone", str(clone), "--parquet", str(art["pq"]),
         "--run-apply", APPLY_RUN, "--run-verify", VERIFY_RUN,
         "--expected-revision", expected_revision,
         "--expected-production-sha256", art["base_sha"],
         "--output", str(out)],
        capture_output=True, text=True, timeout=120, env=_subprocess_env())


def _install(tmp_path: Path, art: dict, mutate) -> Path:
    """复制结果库并按轮同步变异父收据与独立子报告（与审查探针 install 同构）。"""
    clone = tmp_path / "clone.duckdb"
    shutil.copy(str(art["clone"]), str(clone))
    for mode, rid in (("apply", APPLY_RUN), ("verify", VERIFY_RUN)):
        receipt = copy.deepcopy(art["receipts"][mode])
        mutate(mode, receipt)
        child_path = tmp_path / f"child-{mode}.json"
        child_path.write_text(
            json.dumps(receipt["child_report"], ensure_ascii=False))
        receipt["child_report_path"] = str(child_path)
        (tmp_path / f"clone.duckdb.repair-backfill-execution.{rid}.json"
         ).write_text(json.dumps(receipt, ensure_ascii=False))
    return clone


def _assert_structured_fail(res, out: Path, must_fail=(), must_pass=()):
    """坏产物必红：rc=2 + 结构化 FAIL JSON（非裸异常）；指定检查必红/必绿。"""
    assert res.returncode == 2, (res.stdout, res.stderr)
    assert out.exists(), (res.stdout, res.stderr)
    verdict = json.loads(out.read_text())
    assert verdict["verdict"] == "FAIL"
    for name in must_fail:
        assert name in verdict["failed"], verdict["failed"]
    for name in must_pass:
        assert name not in verdict["failed"], verdict["failed"]
    return verdict


def test_acceptance_e2e_baseline_pass(e2e_art, tmp_path):
    """好产物必绿：深 schema 加严后，真实形状的两轮产物仍通过（不用全绿替代必红）。"""
    out = tmp_path / "out.json"
    res = _run_acceptance(e2e_art["clone"], e2e_art, out)
    assert res.returncode == 0, (res.stdout, res.stderr)
    verdict = json.loads(out.read_text())
    assert verdict["verdict"] == "PASS" and verdict["failed"] == []


@pytest.mark.parametrize("mutation", ["none", "amount", "delete", "insert", "timestamp"])

```


## execute/commands/004-bash/request.json
```text
{"toolCallId":"call_0c75b48347c949f3a005700d","params":{"command":"sed -n 840,975p /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/candidate/tests/test_repair_backfill_stock_history.py"}}
```


## execute/commands/004-bash/result.json
```text
{"exitCode":0}
```


## execute/commands/005-bash/output.log
```text
"""repair_backfill_stock_history 单测：scoped 语义 / 预期置缺 / 拒跑 / 幂等。

合同：`docs/handoffs/2026-09-14-302132-prep-review.md`「下一轮执行前合同」。
合成库 30 个交易日（2026-08-03 起的工作日），目标股 999999.SZ：
主表仅 D0 正常行 + D1 空壳 + D2 正常行 + D29 钉值行；并跑表 07-31 起全覆盖；
parquet 夹具供 D27/D28 尾段。另有一只他股 000001.SZ 全量行作不变见证。

钉值策略：technical 用解析精确值（等差 close 步长 0.5 → ma26=18.25、
std26=3.75 等比可手算）；window 钉值由夹具 SQL 对并跑表源数据独立计算。
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import duckdb
import pytest

from market_feature_store.db import init_db
from market_feature_store.sync.repair_backfill_stock_history import (
    BackfillSpec,
    run_backfill_child,
)
from market_feature_store.sync.repair_hithink_stock_day import RepairRefused

CODE = "302132.SZ"  # 与验收脚本钉死的合同代码一致（E2E 验收回归复用本夹具）
NAME = "测试股份"
OTHER = "000001.SZ"
PREV = "2026-07-31"  # 窗口前一交易日（周五）


def _calendar() -> list[str]:
    days, d = [], date(2026, 8, 3)
    while len(days) < 30:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    return days

```


## execute/commands/005-bash/request.json
```text
{"toolCallId":"call_d48f641bd4f44eb7836bf8f0","params":{"command":"sed -n 1,40p /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/candidate/tests/test_repair_backfill_stock_history.py"}}
```


## execute/commands/005-bash/result.json
```text
{"exitCode":0}
```


## execute/commands/006-bash/output.log
```text
378:    import market_feature_store.sync.repair_backfill_stock_history as mod
423:import market_feature_store.sync.repair_backfill_stock_history as mod  # noqa: E402

```


## execute/commands/006-bash/request.json
```text
{"toolCallId":"call_40c4df18008343589a6bb557","params":{"command":"grep -n \"as mod\" /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/candidate/tests/test_repair_backfill_stock_history.py"}}
```


## execute/commands/006-bash/result.json
```text
{"exitCode":0}
```


## execute/commands/007-bash/output.log
```text
201:        window_start=CAL[0], main_fill_end=CAL[28], window_end=CAL[29],
339:              main_fill_end=spec.main_fill_end, window_end=spec.window_end,
356:        kw["window_end"] = "2026-09-12"  # 周六，非交易日
492:                           [CODE, spec.window_end])
803:                     "window_start": "2026-06-15", "window_end": "2026-09-11",
889:                report.update({"run_id": rid, "trade_date": spec.window_end,
902:            "kind": "repair-backfill-302132", "trade_date": spec.window_end,
985:                [art["spec"].code, art["spec"].window_end],
1122:     lambda m, r: _set0(r["spec"]["gap_parallel"], r["spec"]["window_end"])),
1129:     lambda m, r: r["spec"].update(main_fill_end=r["spec"]["window_end"])),
1131:     lambda m, r: r["spec"].update(shell_date=r["spec"]["window_end"])),
1154:    ("trade_date_not_window_end",

```


## execute/commands/007-bash/request.json
```text
{"toolCallId":"call_309902f51f2a4cf183a04e7c","params":{"command":"grep -n \"window_end\" /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/candidate/tests/test_repair_backfill_stock_history.py"}}
```


## execute/commands/007-bash/result.json
```text
{"exitCode":0}
```


## execute/commands/008-bash/output.log
```text
43:CAL = _calendar()

```


## execute/commands/008-bash/request.json
```text
{"toolCallId":"call_448097d3e24f4f38ab39e8e3","params":{"command":"grep -n \"CAL =\" /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/candidate/tests/test_repair_backfill_stock_history.py"}}
```


## execute/commands/008-bash/result.json
```text
{"exitCode":0}
```


## execute/commands/009-bash/output.log
```text

```


## execute/commands/009-bash/request.json
```text
{"toolCallId":"call_8ca9bb5732f14db7bf18e844","params":{"command":"cp /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance_v2.py"}}
```


## execute/commands/009-bash/result.json
```text
{"exitCode":0}
```


## execute/commands/011-bash/output.log
```text

```


## execute/commands/011-bash/request.json
```text
{"toolCallId":"call_f587f71076d44adcb088bdfc","params":{"command":"rm /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance_v2.py"}}
```


## execute/commands/011-bash/result.json
```text
{"exitCode":0}
```


## work/probes/probe_c3_acceptance.py
```text
"""Reviewer QC probe C3 (PR #813): acceptance oracle for outside-window rows.

Challenges candidate/scripts/verify_302132_backfill_acceptance.py (main ->
_data_checks). Fixture helper reused from author tests; all assertions are the
reviewer's own. Synthetic DuckDB inside quality/work only.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CAND = Path("/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/candidate")
TESTS = CAND / "tests" / "test_repair_backfill_stock_history.py"
ACCEPT = CAND / "scripts" / "verify_302132_backfill_acceptance.py"

import importlib.util

spec = importlib.util.spec_from_file_location("t302132", TESTS)
t = importlib.util.module_from_spec(spec)
sys.modules["t302132"] = t
t.__pytest_sameline = True  # harmless marker
spec.loader.exec_module(t)

CODE = "302132.SZ"
OTHER = "000001.SZ"
LATER = "2026-09-22"
LATER2 = "2026-09-23"


def _subprocess_env() -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", str(Path.home())),
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": "C.UTF-8",
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "FWP_TEST_RECEIPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(t.mod.PROJECT_DIR),
    }


def _run(clone: Path, art: dict, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ACCEPT), "--production", str(art["baseline"]),
         "--clone", str(clone), "--parquet", str(art["pq"]),
         "--run-apply", t.APPLY_RUN, "--run-verify", t.VERIFY_RUN,
         "--expected-revision", t.E2E_REV,
         "--expected-production-sha256", art["base_sha"],
         "--output", str(out)],
        capture_output=True, text=True, timeout=110, env=_subprocess_env())


def _base(tmp_path: Path) -> dict:
    """Author fixture + a later (outside-window) row in BOTH baseline & clone,
    receipts' backup sha rebound to the modified baseline."""
    art = t._build_e2e_artifacts(tmp_path)
    for p in (art["baseline"], art["clone"]):
        import duckdb
        with duckdb.connect(str(p)) as con:
            con.execute(
                "INSERT INTO fact_stock_daily SELECT * REPLACE "
                "(DATE '" + LATER + "' AS trade_date) FROM fact_stock_daily "
                "WHERE stock_ts_code=? AND trade_date=?",
                [art["spec"].code, art["spec"].window_end])
    art["base_sha"] = t.mod._sha256(art["baseline"])
    for rid in (t.APPLY_RUN, t.VERIFY_RUN):
        p = Path(str(art["clone"]) + f".repair-backfill-execution.{rid}.json")
        rec = json.loads(p.read_text())
        rec["backup"]["backup_sha256"] = art["base_sha"]
        p.write_text(json.dumps(rec))
    return art


def _mutated_clone(tmp_path: Path, art: dict, mutation: str) -> Path:
    import duckdb
    clone = tmp_path / ("clone_mut.duckdb")
    shutil.copy(str(art["clone"]), str(clone))
    with duckdb.connect(str(clone)) as con:
        if mutation == "amount":
            con.execute("UPDATE fact_stock_daily SET amount=amount+1 "
                        "WHERE stock_ts_code=? AND trade_date=DATE '" + LATER + "'",
                        [art["spec"].code])
        elif mutation == "timestamp":
            con.execute("UPDATE fact_stock_daily SET updated_at="
                        "TIMESTAMP '2026-09-23 12:00:00' WHERE stock_ts_code=? "
                        "AND trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "delete":
            con.execute("DELETE FROM fact_stock_daily WHERE stock_ts_code=? "
                        "AND trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "insert":
            con.execute("INSERT INTO fact_stock_daily SELECT * REPLACE "
                        "(DATE '" + LATER2 + "' AS trade_date) FROM "
                        "fact_stock_daily WHERE stock_ts_code=? AND "
                        "trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "duplicate":
            # DISCLOSURE: remove PK constraint (clone-only CTAS) so an exact
            # duplicate row can exist; adversarial multiset-oracle probe.
            con.execute("BEGIN")
            con.execute("CREATE TABLE fsd_nopk AS SELECT * FROM fact_stock_daily")
            con.execute("DROP TABLE fact_stock_daily")
            con.execute("ALTER TABLE fsd_nopk RENAME TO fact_stock_daily")
            con.execute("INSERT INTO fact_stock_daily SELECT * FROM "
                        "fact_stock_daily WHERE stock_ts_code=? AND "
                        "trade_date=DATE '" + LATER + "'", [art["spec"].code])
            con.execute("COMMIT")
        elif mutation == "other_stock":
            con.execute("UPDATE fact_stock_daily SET amount=amount+1 "
                        "WHERE stock_ts_code=? AND trade_date=DATE '" + LATER + "'",
                        [OTHER])
        else:
            raise ValueError(mutation)
    return clone


def _fail_check(res, out: Path, must_fail: str) -> dict:
    __tracebackhide__ = True
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert out.exists()
    v = json.loads(out.read_text())
    assert v["verdict"] == "FAIL", v
    assert must_fail in v["failed"], (must_fail, v["failed"])
    return v


MUTS = ["amount", "timestamp", "delete", "insert", "duplicate", "other_stock"]
EXPECT_CHECK = {"other_stock": "fact_other_stocks_allcols",
                "insert": "target_outside_window_allcols"}


@pytest.mark.parametrize("mutation", MUTS)
def test_outside_window_mutation_fails(tmp_path, mutation):
    art = _base(tmp_path)
    clone = _mutated_clone(tmp_path, art, mutation)
    out = tmp_path / "out.json"
    res = _run(clone, art, out)
    _fail_check(res, out, EXPECT_CHECK.get(
        mutation, "target_outside_window_allcols"))


def test_baseline_pass(tmp_path):
    art = _base(tmp_path)
    clone = _mutated_clone(tmp_path, art, "none") if False else None
    out = tmp_path / "out.json"
    res = _run(art["clone"], art, out)
    assert res.returncode == 0, (res.stdout, res.stderr)
    v = json.loads(out.read_text())
    assert v["verdict"] == "PASS" and v["failed"] == [], v


def test_positive_control_intentional():
    """Intentional control: assert a mutation check that cannot fail. MUST fail."""
    assert "target_outside_window_allcols_xyz_nonexistent" in ["nope"]

```


## work/probes/probe_c3_acceptance_v2.py
```text
"""Reviewer QC probe C3 v2 (PR #813): acceptance oracle for outside-window rows.

Challenges candidate/scripts/verify_302132_backfill_acceptance.py (main ->
_data_checks). Fixture helper reused from author tests; ALL assertions are the
reviewer's own. Synthetic DuckDB inside quality/work only. No production run.

v2 fix: sys.path setup before importing the author test module (v1 import of
market_feature_store would fail without candidate root on sys.path); removed the
intentional-control test (positive control is the separate standalone script).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CAND = Path("/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/candidate")
TESTS = CAND / "tests" / "test_repair_backfill_stock_history.py"
ACCEPT = CAND / "scripts" / "verify_302132_backfill_acceptance.py"

import importlib.util

sys.path.insert(0, str(CAND))
spec = importlib.util.spec_from_file_location("t302132", TESTS)
t = importlib.util.module_from_spec(spec)
sys.modules["t302132"] = t
spec.loader.exec_module(t)

OTHER = "000001.SZ"
LATER = "2026-09-22"
LATER2 = "2026-09-23"


def _subprocess_env() -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", str(Path.home())),
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": "C.UTF-8",
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "FWP_TEST_RECEIPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(CAND),
    }


def _run(clone: Path, art: dict, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ACCEPT), "--production", str(art["baseline"]),
         "--clone", str(clone), "--parquet", str(art["pq"]),
         "--run-apply", t.APPLY_RUN, "--run-verify", t.VERIFY_RUN,
         "--expected-revision", t.E2E_REV,
         "--expected-production-sha256", art["base_sha"],
         "--output", str(out)],
        capture_output=True, text=True, timeout=110, env=_subprocess_env())


def _base(tmp_path: Path) -> dict:
    """Author fixture + a later (outside-window) row in BOTH baseline & clone,
    receipts' backup sha rebound to the modified baseline."""
    import duckdb
    art = t._build_e2e_artifacts(tmp_path)
    for p in (art["baseline"], art["clone"]):
        with duckdb.connect(str(p)) as con:
            con.execute(
                "INSERT INTO fact_stock_daily SELECT * REPLACE "
                "(DATE '" + LATER + "' AS trade_date) FROM fact_stock_daily "
                "WHERE stock_ts_code=? AND trade_date=?",
                [art["spec"].code, art["spec"].window_end])
    art["base_sha"] = t.mod._sha256(art["baseline"])
    for rid in (t.APPLY_RUN, t.VERIFY_RUN):
        p = Path(str(art["clone"]) + f".repair-backfill-execution.{rid}.json")
        rec = json.loads(p.read_text())
        rec["backup"]["backup_sha256"] = art["base_sha"]
        p.write_text(json.dumps(rec))
    return art


def _mutated_clone(tmp_path: Path, art: dict, mutation: str) -> Path:
    import duckdb
    clone = tmp_path / "clone_mut.duckdb"
    shutil.copy(str(art["clone"]), str(clone))
    with duckdb.connect(str(clone)) as con:
        if mutation == "none":
            pass
        elif mutation == "amount":
            con.execute("UPDATE fact_stock_daily SET amount=amount+1 "
                        "WHERE stock_ts_code=? AND trade_date=DATE '" + LATER + "'",
                        [art["spec"].code])
        elif mutation == "timestamp":
            con.execute("UPDATE fact_stock_daily SET updated_at="
                        "TIMESTAMP '2026-09-23 12:00:00' WHERE stock_ts_code=? "
                        "AND trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "delete":
            con.execute("DELETE FROM fact_stock_daily WHERE stock_ts_code=? "
                        "AND trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "insert":
            con.execute("INSERT INTO fact_stock_daily SELECT * REPLACE "
                        "(DATE '" + LATER2 + "' AS trade_date) FROM "
                        "fact_stock_daily WHERE stock_ts_code=? AND "
                        "trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "duplicate":
            # DISCLOSURE: clone-only CTAS rebuild removes the PK constraint so
            # an exact duplicate row can exist; adversarial multiset-oracle
            # probe only — real PK would itself block duplicates.
            con.execute("BEGIN")
            con.execute("CREATE TABLE fsd_nopk AS SELECT * FROM fact_stock_daily")
            con.execute("DROP TABLE fact_stock_daily")
            con.execute("ALTER TABLE fsd_nopk RENAME TO fact_stock_daily")
            con.execute("INSERT INTO fact_stock_daily SELECT * FROM "
                        "fact_stock_daily WHERE stock_ts_code=? AND "
                        "trade_date=DATE '" + LATER + "'", [art["spec"].code])
            con.execute("COMMIT")
        elif mutation == "other_stock":
            con.execute("UPDATE fact_stock_daily SET amount=amount+1 "
                        "WHERE stock_ts_code=? AND trade_date=DATE '" + LATER + "'",
                        [OTHER])
        else:
            raise ValueError(mutation)
    return clone


def _fail_check(res, out: Path, must_fail: str) -> dict:
    __tracebackhide__ = True
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert out.exists()
    v = json.loads(out.read_text())
    assert v["verdict"] == "FAIL", v
    assert must_fail in v["failed"], (must_fail, v["failed"])
    return v


MUTS = ["amount", "timestamp", "delete", "insert", "duplicate", "other_stock"]
EXPECT_CHECK = {"other_stock": "fact_other_stocks_allcols",
                "insert": "target_outside_window_allcols"}


@pytest.mark.parametrize("mutation", MUTS)
def test_outside_window_mutation_fails(tmp_path, mutation):
    art = _base(tmp_path)
    clone = _mutated_clone(tmp_path, art, mutation)
    out = tmp_path / "out.json"
    res = _run(clone, art, out)
    _fail_check(res, out, EXPECT_CHECK.get(
        mutation, "target_outside_window_allcols"))


def test_baseline_pass(tmp_path):
    art = _base(tmp_path)
    clone = _mutated_clone(tmp_path, art, "none")
    out = tmp_path / "out.json"
    res = _run(clone, art, out)
    assert res.returncode == 0, (res.stdout, res.stderr)
    v = json.loads(out.read_text())
    assert v["verdict"] == "PASS" and v["failed"] == [], v

```


## work/probes/syntax_check_v2.py
```text
import ast
ast.parse(open('/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-02/quality/work/probes/probe_c3_acceptance_v2.py').read())
print('syntax ok')

```

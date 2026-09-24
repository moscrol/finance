```json
{
  "author_test_counts": {
    "errors": 0,
    "executed": 1,
    "failed": 1,
    "passed": 0,
    "skipped": 0
  },
  "claims": [
    {
      "id": "C1",
      "status": "out_of_scope",
      "evidence": "Isolated C2 axis per instructions; not examined."
    },
    {
      "id": "C2",
      "status": "verified",
      "evidence": "Executed probes/work/probes/test_c2_source_guard_v2.py (5 passed, probe-results-v1.xml): (1) later valid hithink 'none' rows at CAL[27..29] beyond max(gap_parallel) — _guard returns mode=apply, no false refusal, rows excluded from authorized source (src_a bounded at seg_a_end, repair_backfill_stock_history.py:268-273, 344-352); (2) qfq flip on gap date → RepairRefused with main table unchanged; (3) tampered parquet bytes → sha256 mismatch refusal before writes (guard :249-251); (4) partial gap state → _fail partial-state refusal; (5) dataclasses.replace wrong parquet_sha256 → refusal before writes."
    },
    {
      "id": "C3",
      "status": "out_of_scope",
      "evidence": "Not in scope."
    },
    {
      "id": "C4",
      "status": "out_of_scope",
      "evidence": "Not in scope."
    },
    {
      "id": "C5",
      "status": "out_of_scope",
      "evidence": "Not in scope."
    },
    {
      "id": "C6",
      "status": "out_of_scope",
      "evidence": "Not in scope."
    },
    {
      "id": "C7",
      "status": "out_of_scope",
      "evidence": "Not in scope."
    }
  ],
  "findings": [
    "无产品缺陷（C2 范围内）：5 个探针全部通过——护栏在写前拒绝坏/部分/哈希不符输入，并跑表上界=max(gap_parallel) 且 adjusted='none'，后到的合法 'none' 历史既不误拒也不进入授权源。",
    "作者测试 test_backfill_keeps_frozen_tail_source_after_parallel_table_advances 失败，但根因为 _code_revision (repair_backfill_stock_history.py:120-126) 在沙箱内执行 git 被拒（Operation not permitted）→ 环境限制，非产品缺陷。",
    "仅静态+合成 DuckDB 探针覆盖 _guard 及 run_backfill_child 的拒绝路径；未跑完整 CLI、未跑全作者套件、无网络/生产访问。"
  ],
  "limits": "仅 C2 在范围；探针为合成 DuckDB 夹具（复用作者 _fixture/_spec 构造，不复用其断言）；探索阶段旧探针文件从未执行，v2 为清理版（去掉死代码 if False 语句），两文件均保留；作者单测 1 项因沙箱禁 git 失败（环境产物）；未执行完整 CLI 或全作者套件；正例控制为独立故意失败，不计入任何计数。本结论不构成全候选批准、合并或生产授权。",
  "positive_control": {
    "classification": "probe_bug",
    "evidence": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B .../spec/work/positive_control.py → exit 1, AssertionError: intentional probe_bug control",
    "status": "OBSERVED_EXPECTED_FAILURE"
  },
  "reviewer_probe_counts": {
    "errors": 0,
    "executed": 5,
    "failed": 0,
    "passed": 5,
    "skipped": 0
  },
  "verdict": "PASS_WITH_LIMITS",
  "complete": true,
  "stage": "execute",
  "axis": "spec",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}
```

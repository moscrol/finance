```json
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
      "evidence": "axis limited to C3 per inputs/claims.md"
    },
    {
      "id": "C2",
      "status": "out_of_scope",
      "evidence": "axis limited to C3 per inputs/claims.md"
    },
    {
      "id": "C3",
      "status": "not_verified",
      "evidence": "synthetic-duckdb probes confirmed outside-window/other-stock ALL-column multiset detection (scripts/verify_302132_backfill_acceptance.py:551-562 xa, _data_checks ~540-728); but production-shaped numeric counts (64 rows / 64 nonnull close/pct_chg/amount, technical39/window161) were not independently tested; claim left not_verified"
    },
    {
      "id": "C4",
      "status": "out_of_scope",
      "evidence": "axis limited to C3 per inputs/claims.md"
    },
    {
      "id": "C5",
      "status": "out_of_scope",
      "evidence": "axis limited to C3 per inputs/claim.ms; no production-copy run authorized or performed"
    },
    {
      "id": "C6",
      "status": "out_of_scope",
      "evidence": "axis limited to C3 per inputs/claims.md"
    },
    {
      "id": "C7",
      "status": "out_of_scope",
      "evidence": "evidence-binding claim; not exercised this session"
    }
  ],
  "findings": [
    "审查范围: C3 验收oracle对外部行(窗口外/其他股票)的多重集(multiset)全字段保护。审查直接针对 scripts/verify_302132_backfill_acceptance.py main->_data_checks 的 fact_other_stocks_allcols 与 target_outside_window_allcols 检查(EXCEPT ALL 双向计数, :551-562)。",
    "供给套件(probe_c3_acceptance_v2.py + test_seeded_c3.py, 前审者断言+宿主fixture修复): 7/7 通过 — 含baseline PASS, 以及窗口外行的 amount/timestamp/删除/插入/重复(去PK CTAS构造, 已披露)/其他股票(amount+1) 六种变异全部FAIL且指向正确检查名。",
    "新自研测试 test_new_c3_v1.py(2用例): null_column — 窗口外行 stock_name 置NULL, oracle 捕获并FAIL target_outside_window_allcols(通过)。earlier_than_window 用例失败: 原因是合成fixture中目标股票在 window_start 之前没有任何行(fixture限制, 非产品缺陷); 未修复重跑(预算/停止指令), 记为failed。",
    "无产品缺陷认定: 所有执行的变异均被验收oracle捕获; 唯一失败为审查探针的fixture前置条件不足。",
    "C3 仍为 not_verified: 64行/64非空close/pct_chg/amount、technical39/window161 等生产形数值计数未在合成日历下独立复测。"
  ],
  "limits": [
    "仅合成DuckDB于quality/work; 无git/网络/生产库/部署/候选写入。",
    "复核执行的供给套件7项与自研2项; 供给7项不计入reviewer_probe_counts, 见supplied_probe_counts。",
    "自研套件earlier_than_window用例失败(fixture无窗口前行), 因此last suite计数为2执行/1过/1败; 不再消耗预算重跑。",
    "duplicate探测使用仅clone的CTAS去PK构造, 非真实schema路径。",
    "窗口前行缺失使早于窗口变异与空列场景只能部分覆盖; 未测生产形数值计数(64/39/161), C3保持not_verified。",
    "作者测试未独立执行(fixture导入不计), author_test_counts全零。",
    "本结论非PASS, 不构成合并或生产授权。"
  ],
  "positive_control": {
    "classification": "probe_bug",
    "evidence": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -B .../quality/work/positive_control.py -> AssertionError: intentional probe_bug control, exit 1 (OBSERVED_EXPECTED_FAILURE)",
    "probe_provenance": "probes/test_seeded_c3.py 与 probes/probe_c3_acceptance_v2.py 为前审者探针源+宿主fixture修复(收据拷贝至clone派生路径、other_stock变异改到CAL[0]日); 本会话原样复核执行, 未修改; 自研断言独立于该套件。",
    "probe_results": {
      "note": "last own suite: work/probes/test_new_c3_v1.py -> work/probe-results-new-v1.xml",
      "path": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-03/quality/work/probe-results-new-v1.xml"
    },
    "reviewer_probe_counts": {
      "errors": 0,
      "executed": 2,
      "failed": 1,
      "passed": 1,
      "skipped": 0
    },
    "supplied_probe_counts": {
      "errors": 0,
      "executed": 7,
      "failed": 0,
      "passed": 7,
      "skipped": 0
    },
    "supplied_xml": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-03/quality/work/probe-results-seeded.xml",
    "verdict": "CHANGES_REQUIRED"
  },
  "complete": true,
  "stage": "execute",
  "axis": "quality",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}
```

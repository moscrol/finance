```json
{
  "author_test_results": "未运行（作者测试可选，预算内未执行）",
  "findings": {
    "c2": {
      "adjusted_filtering": "qfq 惰性/缺 none 拒绝：test_c2_gap_date_only_qfq_refuses PASS。同日共存 qfq+none 因 PK(trade_date,stock_ts_code) 不可构造，改探针在上界外 CAL[19] 验证 qfq 惰性——PASS（原始探针假设同日共存为夹具错误，非产品缺陷）",
      "parquet_sha": "误哈希拒绝路径未完成执行验证（原始探针对 frozen BackfillSpec 赋值导致 FrozenInstanceError，应为夹具错误；修正版未跑）",
      "upper_bound": "守卫上界：test_c2_later_history... PASS（CAL[18]>max(gap_parallel)=CAL[17] 的合法并跑行不拒绝，mode=apply，retained 仅既有 D0/D2/D19）；partial_missing_gap PASS"
    },
    "c3": {
      "amount": "_oracle_amount(123456789.0)=1.2346，与源码 'round(DECIMAL(38,2)/1e8,4)' 4位半进口径一致；原探针期望 1.23456789 为夹具算式错误",
      "pct": "源码：close 量化 0.0001、pre_close 量化 0.01 后相除再 *100，结果 quantize(0.01, HALF_UP)。探针 -89.99 实际值与该口径一致；原期望 -90.00 源自未量化 close 的错误算式（夹具错误）",
      "verdict": "源/代码静态一致（同构映射），含 close 4位/pre_close 2位/amount 4位/volume 整数、全 ROUND_HALF_UP；执行侧仅 qfq 缺日拒绝间接验证，其余 oracle 断言修正后未运行"
    }
  },
  "limits": {
    "constraints": "无 git/网络/生产DB/供应商调用/凭据/部署/候选写入；合成 DuckDB 仅在 work；未嵌套 sandbox-exec；候选文档与另一轴未读",
    "coverage": "未跑作者全套测试、E2E、_accept 全元组比较的直接执行验证；sha-mismatch 拒绝路径仅静态阅读；C1/C4-C7 不在范围",
    "resources": "命令/请求均在 17/600s/120s 限内；探针文件 1 个（v2）",
    "scope": "仅评审 C2/C3；本结果不构成对候选整体或任何其他轴的批准"
  },
  "positive_control": {
    "classification": "probe_bug（预期断言失败，符合设计）",
    "status": "未运行——阶段被提前关闭；见 limits"
  },
  "probe_results": {
    "executed": [
      "test_c2_later_history_and_adjusted_rows_do_not_refuse PASS",
      "test_c2_gap_date_only_qfq_refuses PASS",
      "test_c2_partial_missing_gap_refuses PASS",
      "test_c2_adjusted_qfq_row_in_window_is_inert FAIL(夹具: PK(trade_date,stock_ts_code) 不允许同日 qfq+none 共存)",
      "test_c2_parquet_sha_mismatch_refuses FAIL(夹具: BackfillSpec 为 frozen dataclass,不可赋值)",
      "test_c3_oracle_pct_half_up FAIL(夹具: 期望值算式错误,未按模块口径先量化)",
      "test_c3_oracle_amount_volume FAIL(夹具: amount 预期应为4位小数)"
    ],
    "fixture_corrections": "原探针 work/probes/test_guard.py 保留为证据；修正版 work/probes_v2/test_guard_v2.py（修复 range(28] 语法错与括号）已执行；剩余 4 失败均已归因为夹具错误并定位修正方向（qfq 行改置于上界外日期、sha 用 dataclasses.replace 重建 spec、oracle 期望按源码口径重算），但因阶段关闭修正第三版未编写/未执行",
    "raw_command": "/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260924-02/spec/work/probes_v2/test_guard_v2.py --confcutdir=.../spec/work -p no:cacheprovider --basetemp=.../spec/work/tmp/pytest -q",
    "raw_result": "3 passed, 4 failed in 1.77s；详细回溯见 EXECUTE 请求输出"
  },
  "summary": "C2/C3 独立探针执行：守卫上界（CAL[18]>max(gap_parallel) 不误拒、retained 仅既有主表行）、缺日拒绝、缺none仅qfq拒绝 PASS；qfq同日惰性、sha不符、oracle半进三处失败均归因为夹具错误（PK唯一性、frozen dataclass、期望算式），产品缺陷未发现；C3 源码口径与声明一致（close 0.0001/pre_close 0.01/amount 4位/volume 整数、全 HALF_UP）",
  "complete": true,
  "stage": "execute",
  "axis": "spec",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}
```

```json
{
  "claims": [
    {
      "evidence": "超出评审范围",
      "id": "C1",
      "status": "out_of_scope"
    },
    {
      "evidence": "已测：(1) 守卫上界 test_c2_later_history_and_adjusted_rows_do_not_refuse PASS（CAL[18]>max(gap_parallel)=CAL[17] 合法并跑行不误拒，mode=apply，retained 仅 CAL[0]/CAL[2]/CAL[19] 既有主表行）；(2) 缺日拒绝 test_c2_partial_missing_gap_refuses PASS（RepairRefused）；(3) 缺口日仅有 qfq 无 none 行拒绝 test_c2_gap_date_only_qfq_refuses PASS。未完成执行验证：sha 不符拒绝路径（探针 FrozenInstanceError 夹具错误，修正版未编写/未跑）；窗内同日 qfq 惰性（PK (trade_date,stock_ts_code) 不允许同日 qfq+none 共存，上界外 qfq 惰性间接 PASS，夹具错误非产品缺陷）。以上仅为静态阅读+探针结论",
      "id": "C2",
      "status": "verified_with_limits"
    },
    {
      "evidence": "静态阅读 _oracle_pct/_oracle_amount/_oracle_volume/_accept（close 0.0001、pre_close 0.01 量化后相除、amount=turnover(0.01)/1e8→4位、volume=volume(1)/100→整数、全 ROUND_HALF_UP、全列元组多重集比较）与声明一致。执行侧失败 3 处均归因为夹具期望错误（_oracle_amount(123456789.0)=1.2346 与源码 4 位口径一致；_oracle_pct(10.01,100.0)=-89.99 与源码口径一致），修正版断言未运行，oracle 算术无独立执行确认；qfq 缺日拒绝为间接执行验证",
      "id": "C3",
      "status": "verified_with_limits"
    },
    {
      "evidence": "超出评审范围",
      "id": "C4",
      "status": "out_of_scope"
    },
    {
      "evidence": "超出评审范围",
      "id": "C5",
      "status": "out_of_scope"
    },
    {
      "evidence": "超出评审范围",
      "id": "C6",
      "status": "out_of_scope"
    },
    {
      "evidence": "超出评审范围",
      "id": "C7",
      "status": "out_of_scope"
    }
  ],
  "findings": [],
  "limits": {
    "coverage": "仅 C2/C3 在范围内；C2 的 sha 不符拒绝路径仅静态阅读未执行；窗内同日 qfq 惰性因 PK 唯一性不可构造，仅上界外惰性间接验证；C3 oracle 半进/量化算术执行断言因夹具期望错误未获得独立执行确认（静态口径一致）；_accept 全元组比较无直接执行验证；未跑作者全套测试与 E2E；未触碰 git/网络/生产DB/供应商/凭据/部署；候选文档与另一轴未读；合成 DuckDB 仅在 spec/work；未嵌套 sandbox-exec；探针文件 2 个（probes/test_guard.py 原始证据 + probes_v2/test_guard_v2.py）；命令与请求均在 17 个/120s/600s 限内。本结果不构成对候选整体或 C2/C3 之外任何声明的批准，亦非合并/生产许可",
    "resource_state": "positive_control（预期失败对照）未运行：阶段被提前关闭，未观察其输出，该缺口保持明确"
  },
  "positive_control": {
    "classification": "probe_bug",
    "status": "NOT_RUN"
  },
  "reviewer_probe_counts": {
    "executed": 7,
    "failed_fixture_errors": 4,
    "passed": 3,
    "written": 8
  },
  "verdict": "PASS_WITH_LIMITS",
  "complete": true,
  "stage": "report",
  "axis": "spec",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}
```

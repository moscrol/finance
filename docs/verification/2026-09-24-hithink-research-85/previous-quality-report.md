# Quality 组终稿（report)

## 证据核对结论

已只读核对：`inputs/claims.md`、`explore-quality/REPORT.md`、`execute-quality/REPORT.md` 全文、`execute-quality/execution.json`，并抽查 `execute-quality/commands/` 原始日志退出码（探针 pytest exit 0、阳性对照 exit 1、作者测试收集 exit 4)，与报告计数一致，无数字夸大。execution.json:`STAGE_COMPLETE`、exit 0、`inputs_unchanged=true`、8 次请求全部 200、无错误事件。

**主张对照**:
- **C1 大部分 verified**：纯 429 耗尽类型正确、Retry-After 非法/非正回退指数+60s 钳制+deadline 准入、预算是准入非中断，均由探针实测通过。
- **C2 verified（静态）**:4001 与基线 `baseline_hithink_client.py` 逐一对照语义保持（共享 attempt、0.8×2^k)。
- **C3 被违反（发现 1)**:claims 明确主张"typed 429 exhaustion … continues remaining requests, and produces overall partial plus missing kind/request_id"。实测证明：会话处于 429 退避窗口（throttled 已计数、deadline 已设）时，若耗尽触发点是网络错误，客户端抛裸 `HithinkAPIError`，编排层 `rate_limited=False` 仅调用 1 次即中止，valuation/heat_trend 不再尝试——与纯 429 路径（typed→partial→续跑）形成已实测的行为分裂。期望来源为 C1(429 的独立时间/计数界应保留限流语义）+C3（限流会话应产生 partial 而非整链中止）；输入均为合法业务流，非合同要求的拒绝。"Other errors still fail closed"不能覆盖本场景——此处会话已被限流机制接管，限流类型信息被丢失才是缺陷。该交互是本 revision 新增的 429 退避代码路径，按新代码路径缺陷计，但未跑 baseline 对照执行（沿用静态比对，见 limits)。
- **C4/C5/C6**：仅静态确认（partial exit 3→run_step/monolithic;recovery 排除 latest-only;hardlink 正向路径实测 True/False)，部分未探针化，列入 limits，不冒充已通过。

**不得升格项**：发现 2 为基线同形态既存行为（低）；发现 3 上游可达性未知（`{'code':0,'data':{'item':[]}}` 缺 `total` 被拒，但真实空响应是否带 total 离线无法取证，且"fail closed"也可能是合同有意校验）;**发现 4 的 OSError 泄漏分支无探针、纯静态疑点**。此三项列 observation/not_verified。

**账务**:reviewer 探针 8 passed/0 failed/0 error(explore 称 9 个，实为 8，第 7 项并入 5/6 审计断言）；作者三件套收集阶段沙箱 `PermissionError`(.agents)exit 4 → blocked,0/0/0，非产品缺陷；阳性对照 `assert 1==2` 单独 1 failed exit 1，计 probe_bug，不混入。

```json
{
  "stage": "report",
  "group": "quality",
  "complete": true,
  "revision": "09b437c2f64a097f2535afbeb3a7b615e0c5730a",
  "baseline": "c9dd71dfd678855b61662100ec74625b92ad1f1b",
  "verdict": "CHANGES_REQUIRED",
  "findings": [
    {
      "severity": "medium",
      "status": "reproduced",
      "new_regression_on_new_code_path": true,
      "claim_violated": "C1+C3",
      "expectation_source": "claims.md C3 明确主张 typed 429 耗尽须续跑剩余请求并产 partial+missing 审计; C1 确立 429 独立时间/计数界的限流语义; 输入为合法业务流, 非合同拒绝, 'other errors fail closed' 不适用于已被限流机制接管的会话",
      "file_line": "market_feature_store/hithink_client.py:246,262 -> market_feature_store/sync/sync_hithink_research.py:308,314-330",
      "trigger_input": "retries=4 默认; 序列 3x HTTP200 code=4001 -> 1x HTTP429 -> 1x URLError(conn reset)",
      "error_output": "处于 429 退避窗口却抛裸 HithinkAPIError('重试耗尽')(非 HithinkRateLimitError); 编排层 rate_limited=False, calls==1 即重抛中止, valuation/heat_trend 不再尝试, 无 partial+missing 审计",
      "evidence": "execute-quality/commands 004-bash exit 0: test_mixed_4001_then_429_then_network_loses_rate_limit_type PASS + test_untyped_error_aborts_remaining_requests PASS + test_pure_429_exhaustion_is_typed PASS(纯429对照类型正确, 证明行为分裂)"
    },
    {
      "severity": "low",
      "status": "reproduced_preexisting",
      "claim_relation": "C2 相邻(分类完整性), 未违反明示条款; 基线同形态, 非回归",
      "file_line": "market_feature_store/hithink_client.py:262",
      "trigger_input": "HTTP 200 且正文为合法 JSON 数组 b'[1,2,3]'",
      "error_output": "裸 AttributeError 逃逸 HithinkAPIError 分类; 失败审计 error_type='AttributeError'",
      "evidence": "test_non_dict_json_200_escapes_as_attribute_error PASS(exit 0 批次); explore 静态比对基线同形态"
    },
    {
      "severity": "low",
      "status": "observation_not_verified",
      "claim_relation": "C3 'Empty/NULL valid data remain distinct from failed' 可能相关, 但真实空响应是否携带 total 离线无法取证, 且 fail-closed 校验可能是合同有意行为; 可达性未知, 不升格",
      "file_line": "market_feature_store/sync/sync_hithink_research.py:130",
      "trigger_input": "valuation 响应 {'code':0,'data':{'item':[]}}(合法空、无 total 键)",
      "error_output": "HithinkResearchError('valuation total does not match item count'); 空数据被记 failed 且中止整链",
      "evidence": "test_empty_valuation_missing_total_is_rejected PASS 仅复现代码行为; 端到端可达性未证实"
    },
    {
      "severity": "low",
      "status": "observation_not_verified",
      "claim_relation": "C5 'use existing canonical production-write guard' 相关; 正向路径(硬链接 True/缺失 False)已实测, 异常泄漏分支纯静态疑点",
      "file_line": "market_feature_store/write_path.py:105-106",
      "trigger_input": "is_canonical_production 目标 stat() 抛非 FileNotFoundError 的 OSError(如 PermissionError)",
      "error_output": "异常外抛替代布尔返回(基线为 except OSError: False, 候选收窄为仅 FileNotFoundError, 疑为新行为变化)",
      "evidence": "test_hardlink_to_production_detected PASS 仅覆盖正向契约; 泄漏分支未探针化、未执行(verified_by_execution=false)"
    }
  ],
  "reviewer_probes": {"passed": 8, "failed": 0, "error": 0, "note": "explore 称 9 项, 实 8 个测试(第7项并入5/6审计断言); 假网络 urlopen 脚本+临时 DuckDB, 断言模块 __file__ 来自 TREE; 一次通过无修改无复跑"},
  "author_tests": {"passed": 0, "failed": 0, "error": 0, "blocked": true, "block_reason": "tests/test_hithink_research.py 原位执行收集阶段 pytest_ignore_collect stat TREE/.agents 触发 sandbox PermissionError, exit 4(009-bash 原始日志证实); 按规不绕行不重试, 非产品缺陷, 不计入通过"},
  "positive_control": {"classification": "probe_bug", "expected_failure": true, "observed": "1 failed (assert 1 == 2), exit 1 (007-bash 原始日志)", "note": "故意失败针单独运行、未修改、与正常探针分账"},
  "limits": [
    "作者测试 0 计数(blocked): C1-C4 缺作者目录测试佐证, 结论主要立于 reviewer 探针+静态比对",
    "未跑 baseline TREE 对照执行; 发现1属新增429代码路径故按新缺陷计, 发现2/3基线同形态结论沿用 explore 静态比对",
    "发现3上游真实空响应形态、发现4的OSError泄漏分支均超出离线证据, 列 not_verified 不升格",
    "C4 (partial exit 3 -> run_step/nightly 汇总/monolithic raise) 仅静态确认未探针化",
    "audit_hithink_runtime.py、finance_query.py 消费注册段、source.diff 全文(2478行)、作者测试全文(626行)未逐行覆盖, 该范围未核",
    "发现1的 sync 层结局由模拟客户端复现, 遵守假网络约束无真网络端到端验证; git 元数据沙箱不可读(008-bash exit 128), revision/baseline 以任务契约为准"
  ]
}
```

# Quality 组最终报告（report 阶段，独立裁决）

## 中文结论

**verdict = PASS_WITH_LIMITS**。证据全部来自 execute 独立会话原始日志（单次计数，未与 explore 重复读数相加）;M1 经合同与运行证据**撤销**；无复现出的新正确性缺陷；两低发现（一为候选新增行为差、一为基线同形态）不构成 CHANGES_REQUIRED；三项无法证明预期的项保持 observation/not_verified，未升格。

### 逐项对照 inputs/claims.md 的发现核查

1. **F4(low，候选新增行为差）— 不升格**。对照 **C5**:"use existing canonical production-write guard (including hard-link/unknown-identity checks)"。期望行为来源是 C5 对既有生产写守卫语义的沿用。实测 `source.diff:960-963` 将守卫 `except OSError` 收窄为 `except FileNotFoundError`(write_path.py:105-106)，使 `PermissionError` 由"返回 False"变为外抛。失败方向是**阻断写入**（完整性安全），仅可用性差异；守卫对未知身份目标的拒绝义务反而更保守地成立。不构成对 C5 明示条款的打破，严重性维持 low；探针以 monkeypatched `Path.stat` 模拟，非真实 OS EACCES。
2. **F2(low，基线同形态，非回归）**。落入 **C2** 的错误分类领域。期望行为来源仅可追溯到 C2 的"parse errors 不得被误划为限流缺口"与类型化错误的总体风格；HTTP200+JSON 数组 → 裸 `AttributeError` 逃逸并**未**违反 C2 的任何明示条款（未误划限流、未泄 secrets),`inputs/baseline_hithink_client.py:158` 同形，属既存行为，非新回归。
3. **F3(observation / not_verified)**。对照 **C3**"Empty/NULL valid data remain distinct from failed requests"。空 valuation 无 `total` 的真实上游形态离线不可取证，排除合同要求的合法拒绝，**不能升格**为 CHANGES_REQUIRED。
4. **M1(info,withdraw)**：复现一个异常（裸 `HithinkAPIError`）不等于复现产品缺陷。受控单调时钟对照证实击停的是普通计数界 `attempt>=retries`(URLError 消耗第 4 次尝试）,typed 429 两界均未触发（`throttled=1<10`，累计退避 6.4s<300s)。合同定位：C3 续跑/partial 义务仅挂"a typed 429 exhaustion",C3 末句"Other errors still fail closed"正是本行为；若改判限流类型反而违 C2。前轮将本行为写成 C1+C3 违反属自创期望，**撤销**。
5. **C4(partial exit 传播）** 仍仅静态确认，未探针化 → not_verified 部分，列入 limits，不冒充已通过。

### 计数（全部出自实际日志，execute 会话单次）
- **reviewer probes**:`17 passed in 3.87s`(commands/008-bash)→ passed=17, failed=0。
- **positive control**:`1 failed in 0.20s`(009-bash，人为 `assert 1 == 2`)→ 另列 probe_bug。
- **author tests**:010-bash 收集期 `PermissionError: [Errno 1] … /.agents`,`found no collectors`,exit 4 → blocked,0/0/0,**非产品缺陷、非通过**。
- **revision 校验**:005-bash `git rev-parse` 被沙箱 stat 拒绝（exit 128)；以探针 3 条 `__file__.startswith(TREE)` 断言佐证模块归属固定 continue-03 TREE。
- **limits 披露（依规）**:explore 阶段违反"不跑测试"要求提前执行探针（explore 017-bash `17 passed in 1.28s`)；最终**只计 execute 一次 17/0**，两次读数未加总。

```json
{
  "stage": "report",
  "group": "quality",
  "complete": true,
  "revision": "62777a76d7812bf5eebe070892e5977b2aa93003",
  "baseline": "c9dd71dfd678855b61662100ec74625b92ad1f1b",
  "verdict": "PASS_WITH_LIMITS",
  "findings": [
    {
      "id": "F4",
      "severity": "low",
      "status": "candidate_behavior_delta_no_explicit_claim_broken",
      "file_line": "market_feature_store/write_path.py:105-106 (source.diff:960-963)",
      "claim_ref": "C5 'use existing canonical production-write guard (including hard-link/unknown-identity checks)'",
      "expectation_source": "既有守卫对 stat 失败返回 False 的基线语义；期望来源为 C5 对既有行为的沿用主张",
      "trigger_input": "对 stat() 抛 PermissionError 的 canonical production 目标调用写守卫",
      "error_output": "PermissionError 外抛出守卫而非返回 False；失败方向阻断写入（完整性安全），仅可用性差",
      "contract_exclusion_check": "写阻断恰符合生产写保护意图，未知身份目标拒绝义务仍成立；非合同要求拒绝被误判为缺陷",
      "evidence": "execute 探针 test_guard_stat_permission_error_now_propagates 通过（008-bash 17 passed 之一）；探针用 monkeypatched Path.stat，非真实 OS EACCES"
    },
    {
      "id": "F2",
      "severity": "low",
      "status": "preexisting_baseline_identical_not_regression",
      "file_line": "market_feature_store/hithink_client.py:258 (baseline_hithink_client.py:158 同形)",
      "claim_ref": "C2 错误分类领域，但 C2 明示条款（不得误划限流缺口、secrets 缺席）未被打破",
      "expectation_source": "无明确合同条款要求该形态类型化；仅 C2 总体错误分类风格",
      "trigger_input": "HTTP 200 + 顶层 JSON 数组响应",
      "error_output": "裸 AttributeError 逃逸 HithinkAPIError 分类",
      "contract_exclusion_check": "无效/异形态输入本身；异常复现不等于缺陷复现；baseline 同形排除新回归",
      "evidence": "execute 探针 test_non_dict_json_200_escapes_as_attribute_error 通过"
    },
    {
      "id": "F3",
      "severity": "low",
      "status": "observation_not_verified",
      "file_line": "market_feature_store/sync/sync_hithink_research.py:130",
      "claim_ref": "C3 'Empty/NULL valid data remain distinct from failed requests'",
      "expectation_source": "C3 ；但上游真实空响应形态离线不可取证",
      "trigger_input": "空 valuation 响应无 total 字段",
      "error_output": "请求被拒；无法判定该形态是否可达自真实上游",
      "contract_exclusion_check": "排除合同要求的合法拒绝；可达性未知的上游形态，不升格为 CHANGES_REQUIRED",
      "evidence": "无对应探针，explore/execute 两阶段均维持 not_verified"
    },
    {
      "id": "M1",
      "severity": "info",
      "status": "withdrawn_not_a_contract_violation",
      "claim_ref": "前轮挂 C1+C3 ；实际 C3 末句 'Other errors still fail closed' 授权其行为，C2 禁止改判限流",
      "expectation_source": "前轮 expectation_source 为自创规则，合同无对应主条款",
      "trigger_input": "业务码 4001×3 → 429 ×1 → URLError(retries=4, budget=300)",
      "error_output": "裸 HithinkAPIError,sleeps==[0.8,1.6,3.2,0.8],calls==5;sync 层 rate_limited=False fail-closed",
      "contract_exclusion_check": "异常复现≠缺陷复现：击停普通计数界 attempt>=retries,typed 429 两界未触发（throttled=1<10，退避和 6.4s<300s)",
      "evidence": "受控单调时钟三组对照 4 个 M1 探针 + fail-closed 探针通过（008-bash 17/17)"
    }
  ],
  "reviewer_probes": {"passed": 17, "failed": 0, "error": 0, "log": "execute-quality/commands/008-bash: 17 passed in 3.87s", "first_run": true, "probe_modified": false},
  "author_tests": {
    "passed": 0, "failed": 0, "error": 0,
    "status": "blocked",
    "detail": "原位 pytest 收集期 PermissionError [Errno 1] stat TREE/.agents(pytest_ignore_collect is_dir),'found no collectors',exit 4；按约束不加忽略钩子、不绕行；记 blocked 而非通过或缺陷",
    "log": "execute-quality/commands/010-bash"
  },
  "positive_control": {
    "classification": "probe_bug",
    "intentional": true,
    "observed_exit": 1,
    "observed": "1 failed (assert 1 == 2) in 0.20s",
    "log": "execute-quality/commands/009-bash",
    "note": "人为 assert 1==2 单独分账，不混入正常测试计数"
  },
  "m1_adjudication": {
    "ruling": "withdraw",
    "basis": "维持 explore 的撤销裁决并经 execute 复现确认",
    "contract_basis": "C3 typed-continue 义务仅挂 'a typed 429 exhaustion';C3 末句 'Other errors still fail closed' 授权普通网络耗尽的中止；C2 禁止把普通网络耗尽改判限流恢复；解释 B 在合同无主条款支撑",
    "run_evidence": "受控时钟：击停为普通计数界 attempt>=retries;429 时间界/计数界均未触发（throttled=1<10，退避累计 6.4s<budget=300s)；对照A（无 429）同结局证明分类由实际击中的界决定",
    "disposition": "前轮 M1 作为 C1+C3 违反予以撤销；行为本身可复现但属合同合规"
  },
  "limits": [
    "explore 阶段违反不跑测试要求提前执行探针（explore-quality/commands/017-bash: 17 passed in 1.28s)，依规在此披露；最终计数只取 execute 独立会话一次 17/0，两次读数未加总",
    "author_tests=blocked：沙箱拒 stat 源树 .agents 元数据，未获任何作者通过计数，记 0 blocked 而非 0F0E；非产品缺陷、非通过",
    "git rev-parse 被沙箱拒绝（exit 128),revision 未经 git 核对；以探针 3 条 __file__ 在固定 continue-03 TREE 下的断言作为树归属佐证",
    "仅补建 WORK/pytest.ini（空 [pytest] 节，工作台文件）；未改探针/源码/网络/生产/Git/依赖；独立探针一次通过无首红",
    "未跑全仓；M1 sync 层为模拟 getter 无真网络端到端；write_path PermissionError 用 monkeypatched Path.stat 非真实 OS EACCES",
    "F3 维持 not_verified;C4(partial exit 传播）仍仅静态确认未探针化；列 observation/not_verified，未升格也未冒充已通过",
    "C6 承诺边界：默认重试预算未证明覆盖真实 7-9 分钟限流窗口（合同本身亦未承诺）"
  ]
}
```

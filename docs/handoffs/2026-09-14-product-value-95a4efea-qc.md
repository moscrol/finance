# 05 Round-8 补遗修复复核 · 95a4efea / 75ab917a

## 结论

**原两项 P1 反例关闭；05 仍需退修两处收据层缺口，不签最终放行。** 两处在父版本 f8540a53 同样存在，不能归因为 95a4efea 引入的新回归。01/02/04 不撤回既有候选；本轮范围为 05 的修复及相邻覆盖边界，不等于 06 集成验收。

目标代码 `95a4efeaf3d55a517f7132133d9ee0bfe12c3286`，最终候选 `75ab917ad3f7fd2c3134302d85558694a224e387`。两者差集只有 inflight 与 PROGRESS。候选工作树审查时干净；主检出树有大量他人改动，未碰。隔离树 `/private/tmp/research-evolution-95a4-qc` 基于最终候选，父对照 `/private/tmp/research-evolution-95a4-before` 固定 f8540a53。未 push、未合 main、未外呼、未写生产数据。

## 原修复：通过

- `measure.py:272–279` 在 attempts 折叠前检查 run 身份：同 attempt 的两套生命周期，以及 started=run1/finished=run2，均出现 `attempt_run_conflict`、收据 incomplete、汇总 full_cost unknown。未合并冲突事件的时间/状态，保留第一条的实现与汇报一致。
- `contracts.py:101–115` 公共联合身份规则已供 measure/summarize 调用。单纯错配费用不再清除收据执行缺账。
- 原归档探针 `scripts/review_probes/check_product_value_identity.py`（分支 `docs/qc-research-evolution-round8-addendum`）：父版本 3 failed / 4 passed，候选 7 passed。联合一致、run-only、attempt-only 合法对照仍 known CNY 1.39。

## 本轮发现

### S1 [P1] 收据核销遍历审计全集，selected=False 的细账仍能清除缺账

定位：`intelligence/services/product_value/measure.py:573–579`，尤其 `for m in selected`。

变量 `selected` 不是“选中账单集合”：`_aggregate_costs` 会把被粗层账覆盖的细层账也 append 进去，仅标记 `selected=False, dedup_reason=covered_by_run`（535–537）。金额计算及 summarize 都过滤这个标记，新收据核销却只检查联合身份，没有过滤。

公开事件反例：同任务 run1/attempt1 与 run2/attempt2；第一执行账齐。给第二执行一组 `(run2, attempt1)` 错配 run 级费用，再追加一组 `(run2, attempt2)` 正确 attempt 级细账。粗细去重把细账排除，粗账因联合身份错配不能覆盖第二执行；但测量层仍拿已排除的细账作证。

| 输入 | 收据状态 | 收据缺口 | 汇总 |
|---|---|---|---|
| 只有错配粗账 | incomplete | no_usage_evidence_for_attempt | unknown |
| 追加 selected=False 的正确细账 | **valid** | **空** | unknown，writer/review 缺账 |
| 一致身份的粗账＋细账 | valid | 空 | known CNY 1.39 |
| 只有正确细账 | valid | 空 | known CNY 1.39 |

所有输入零 invalid/rejected，第二行收据 known CNY 0.93。**被排除的审计条目不能改变核销结果。** 这是上轮明确要求“注意 selected”的残留边界。

修复：测量和汇总使用同一套有效费用候选集（至少过滤 selected），再做身份匹配。若要进一步让合法细账替代无效粗账，需明确改变去重合同并同步金额/覆盖；不能只在核销阶段偷用被排除的条目。

### S2 [P1] 共用了身份谓词，但收据仍以任意费用豁免整个执行的模型缺项

定位：`intelligence/services/product_value/measure.py:573–591`；对照 `summarize.py:157–183` 的逐执行组件覆盖。

即使全是 selected=True 且身份正确，`any(cost_item_covers_attempt(...))` 只证明该执行存在一笔费用，不能证明 writer/review 两个固有模型组件完整。第二执行仅 tool 或 writer+tool，就跳过整个派生缺口；组件检查仍只在汇总层。

| 第二执行费用 | 收据状态 / 缺口 | 收据 known CNY | 汇总缺组件 |
|---|---|---:|---|
| tool | **valid / 空** | 0.47 | writer_model + review_model |
| writer + tool | **valid / 空** | 0.83 | review_model |
| writer + review + tool | valid / 空 | 0.93 | 无；完整 known |

金额为该配对，汇总合法对照加另一完整配对后为 CNY 1.39。零 invalid/rejected，真实 run 描述存在；无需错配、无需去重就复现。

依据：05 spec §3 要求覆盖不明 incomplete、缺账未知；`docs/research-pilots/research-evolution/06-integration-contract.md:51–54` 要求独立展示收据状态及限制，unknown 非空时不显示总成本。这里与上轮 R8A-2 同属公开收据和汇总不一致，但缺失的是**组件维度**，不是身份谓词。历史 PV10/PV11 测试只断言 summary，未保护收据。

修复：共享的不应只有身份判断，还应包含逐执行的必需组件及缺项推导；measure 把缺项写回 receipt 并降级，summarize 复用同一结果/规则。按冻结协议适用集过滤，失败执行保留“需 writer、未发生 review 不硬要”的合法通路，原流程人工计时也不能被一刀切误伤。

## 验证和证据边界

- 候选干净树、审查文件加入前：05 模块 **121 passed in 1.13s**；全仓 Ruff **All checks passed**。审查文件加入后 Ruff 再绿。
- 原身份反例独立父红子绿：**3 failed / 4 passed → 7 passed**。
- 第 4–7 轮归档安全断言：**23 passed**（4+5+6+8）。通过显式根目录映射 01=6cc5748a、02=e27b3352、04=fcc7838c、05=75ab917a；不宣称四轨全量。
- 新安全断言 `scripts/review_probes/check_product_value_selection.py`：候选 **3 failed / 4 passed**；父版本 **4 failed / 3 passed**。三红对应 S1 + S2 的两个费用子集；父多一红为本次已修的纯错配收据。
- 已核全量原件 `20260913T190134Z-95a4efea.json`：revision 完整一致，dirty=false / dirty_paths=[] / worktree_dirty_total=0，counts=9660 passed / 1 failed / 77 skipped / 0 error，exit_status=1，dependency_gate_bypassed=false。失败 ID 为 `test_real_conversation_round_trip_persists_skills_sse_and_three_turns`。
- 同 SHA 的 `190202Z / 190215Z / 190221Z` 三份收据均该 ID 单测 1 passed、exit 0。支持“单测 3/3 通过”；收据不记录失败调用栈，不能仅靠它独立验证 10s 超时根因，更不能把全量 exit 1 改写为绿。
- **本轮未重跑全量；未重跑第 1–3 轮；未验证 06、前端、E2E、registry。** main 合并仍须最终组合所有叶子绿灯；flaky 单跑绿不替代完整门禁。
- 外置 pytest 探针触发的自动收据有时记录的是探针所在树 SHA，而非子进程目标。目标身份以 QC_TREE/根目录映射及输出 JSON 为准，勿误读自动收据。

完整输入派生输出、失败日志、父对照和历史收据副本：`~/.finance-runtime/reviews/research-evolution-95a4efea-qc/`。

## 复验

```bash
QC_TREE=<05候选绝对路径> /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -rf scripts/review_probes/check_product_value_selection.py
```

探针只构造原始 fixture 事件，经公开 measure_pair → summarize；没有修改收据或用私有 helper 替业务代码裁决。检查文件用 `check_` 命名、显式执行，避免将已知红断言混入默认测试，也不靠 xfail 掩盖。

工具沉淀：领域反例已归档为可执行脚本；不新造通用静态门禁，组件要求和合法覆盖粒度依赖领域合同。可迁移原则是：**共享谓词不等于共享完整校验；候选资格、身份、覆盖维度及公开输出都必须一致。** 未改脏的 harness-reference。

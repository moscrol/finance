# 05 Round-9 独立复核 · cee71963 / 3fdff5d1

## 结论

**Round-9 原两项 P1 关闭；相邻边界确认 1 P1 + 1 P2，05 暂不签最终放行。** 不撤回 01/02/04 的既有候选；不替代 06 集成验收。

代码 `cee719635a275d596bd2dd330a00c9d4cc62d635`；候选 `3fdff5d1` 仅比代码提交多 inflight/PROGRESS。主检出树 detached HEAD 且有大量他人改动，未碰；隔离树 `/private/tmp/research-evolution-r9-qc`、评审分支 `docs/qc-research-evolution-round9`。未 push、未合 main、未改业务实现、未外呼/写生产数据。

## 按发现顺序

### 1. 原修复成立，旧 QC 脚本实际可达

本机 `docs/qc-research-evolution-95a4efea@075bc174` 包含原 `scripts/review_probes/check_product_value_selection.py`。原样执行，不用开发者新测试替代：修前代码对应的评审树 **3 failed / 4 passed**，候选 **7 passed**。身份归档 `check_product_value_identity.py` 另 **7 passed**。

`contracts.py:122–147` 将 selected 过滤、联合身份与必需模型组件合并；measure/summarize 的有 attempt 分支确实共用。合法粗账+细账、细账单独、三组件齐全、run-only/attempt-only 身份通路仍成立。已有测试期望的四处修改符合缺口语义变化，没有发现以放松断言掩盖原两项 P1。

### 2. R9-1 [P1] 无 run 的任务级组件缺口仍只存在于汇总，不在收据

定位：`intelligence/services/product_value/measure.py:575–599`（只遍历 attempts）；对照 `summarize.py:164–170` 的 `if not attempts` 独立任务级组件规则。

Round-9 抽出的公共规则只覆盖执行实例。辅助任务没有 run 生命周期，但保留可信开始/放弃时间、同意和独立质量记录时，measure 不再检查模型成本。直接重用既有 PV9 的任务级费用合同即可复现：

| 辅助任务费用 | 收据 status / limitations / unknown | 汇总 full_cost | 汇总缺组件 |
|---|---|---|---|
| 无账 | **valid / [] / []** | unknown | writer + review |
| tool | **valid / [] / []** | unknown | writer + review |
| writer + tool | **valid / [] / []** | unknown | review |
| writer + review + tool | valid / [] / [] | known CNY 0.93 | 无 |

所有场景 `invalid_reasons=[]`、事件零拒收、汇总零 input_errors；原流程 `attempts=[]`、人工计时仍有锚点且大于 0。已知金额是两对任务汇总（另一对完整费用 CNY 0.46）。无需改收据、无需 private helper 裁决。

影响：`06-integration-contract.md:51–54` 要求单独展示收据状态/限制，且只有 unknown 非空才禁止“总成本”。本场景缺账却让收据的两个信号同时报完整；不能拿 summary 仍 unknown 当成修复。05 spec §3 也要求未观察到调用不能作零费用依据。

**建议**：公共合同覆盖“任务级无实例 / 逐执行实例”两条分支；measure 为无 run 的 assisted 任务写组件缺口、设置阻断 limitation；summarize 复用同一规则。保留原流程仅人工计时、合法 task-scope 三件套、冻结协议豁免模型组件的通路，不因没有 run 就全体硬拦。

父对照：本地评审树 `075bc174` 的 product_value 业务与测试夹具相对父候选 `75ab917a` diff 为空。上述三档同样 valid/空，属于**既有相邻遗漏，不是 cee71963 新回归**。

### 3. R9-2 [P2] 新逐组件缺口投影丢失组件坐标，多个缺口变成相同条目

定位：`intelligence/services/product_value/summarize.py:827–834`（unknown 只输出 id/reason，并仅条件保留 `uncovered_components`）；新增生产者 `measure.py:587–594` 写的是单数 `component`，不是 `uncovered_components`。

成功 attempt 无账：收据有两条 `{attempt_id:a-x2-1, component:review_model|writer_model, ...}`，汇总变成两条完全相同的：

```json
{"id":"a-x2-1","reason":"no_usage_evidence_for_attempt"}
```

任务级 `uncovered_components=[review_model,writer_model]` 只能保留并集，恢复不了执行归属。第二个反例保持两次执行及总已知金额不变：

- A：执行 1 缺 review，执行 2 缺 writer；
- B：执行 1 缺 writer，执行 2 缺 review。

候选收据的两组缺项不同，但公开 `cost_full_status.unknown` **逐字相同**。消费者单看该 metric 无法分辨应给哪次执行补哪一组件；不能以“输出里某处出现 review_model”作为逐执行诊断已保留的证明。

**建议**：公开 unknown 条目保留 `component` 与执行/收据坐标，或按 attempt 分组输出 `uncovered_components`；不要只改变计数或展示文案。测试断言每条执行级缺项的组件归属，包含 A/B 互换反例，而非仅全局搜索字段名。

归因：投影层此前就丢 component，父版单个泛化缺口亦缺组件；**本轮逐组件生产者使同 id/reason 重复和精确信息丢失更明显**。父版 A/B 收据都空（原 S2 缺陷），不能把父版相同失败计数直接解释成同一断言失败；日志明确区分。

## 验证与边界

| 检查 | 独立结果 |
|---|---|
| 候选 05 默认模块 | 123 passed（首次在添加评审文件前，候选树干净；加入探针后复跑仍绿） |
| 全仓 Ruff | All checks passed，包含新增探针 |
| 原选择/组件 QC 原脚本 | 修前 3 failed / 4 passed → 候选 7 passed |
| 上轮身份 QC 原脚本 | 候选 7 passed |
| Round4–7 归档安全断言 | 23 passed（4+5+6+8） |
| 新显式 QC 检查 | 候选 5 failed / 3 passed；父业务对照 5 failed / 3 passed，失败位置按上文区分 |
| 协议豁免合法对照 | 事前 freeze review 豁免，writer+tool → receipt valid、summary known CNY 0.83 |
| 全量历史原件 | `20260913T195954Z-cee71963.json`：完整 revision 一致、dirty=false/paths=[]/worktree_dirty_total=0、9663 passed/77 skipped/0 failed/0 error、exit_status=0、dependency_gate_bypassed=false |

Round4–7 显式映射：01=6cc5748a、02=e27b3352、04=fcc7838c、05=3fdff5d1；不宣称四轨全量。首次查找 round4 错用了不存在的 `test_round4.py`（exit 4、no tests），核对真实文件名 `test_adjacent.py` 后完整复跑 23 绿，不将首次失败误报为回归。

**未独立重跑全量；未重跑第 1–3 轮；未验 06 组合、前端、E2E、registry。** 全量只确认作者原件，不冒充本轮独立绿灯。首次模块原件 `20260914T015830Z-3fdff5d1.json`；原始输出与历史收据副本在 `~/.finance-runtime/reviews/research-evolution-round9-qc/`。外置 pytest 收据可能按探针树记录 SHA，目标必须结合 QC_TREE/映射与输出核验。

## 复验与方案选择

新增文件：
- `scripts/review_probes/product_value_task_receipt.py`：事件→公开 measure_pair→summarize，输出全部收据与成本 metric。
- `scripts/review_probes/check_product_value_task_receipt.py`：8 条显式安全断言，5 红对应 2 项发现；`check_` 命名不进默认收集，不用 xfail 掩盖。

```bash
QC_TREE=<05候选树绝对路径> /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -rf scripts/review_probes/check_product_value_task_receipt.py
```

| 选择 | 原因 |
|---|---|
| 保留原两项 P1 关闭、新增事项单列 | 旧反例已经原样全绿，不能抹掉真实修复；也不能据此泛化最终放行 |
| 不在评审中改实现 | 用户授权为审查；修复应由 05 独占轨完成 |
| 不靠 summary 兜住就放收据 | 两者都是公开合同消费者，已有接线约定独立展示 |
| 不要求无 run 辅助任务一律 invalid | 合同有合法 task-scope 费用；仅缺成本时应 incomplete，原流程人工时间不受影响 |
| 工具化领域反例，不造通用静态门禁 | 适用组件和覆盖粒度需领域语义；脚本可重放，静态字段被读取不证明投影完整 |

下一步：05 收敛无 run/有 run 的共同任务覆盖合同，补汇总投影，跑本轮新探针与原归档；06 在最终四轨组合复验后再申请放行。未动脏的 harness-reference。

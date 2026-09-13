# 研究进化四轨 · 第七轮独立 QC（复核第六轮修复）

## 结论与范围

第六轮固定反例 J11/J12/PV10 均已通过；不能据此签「所有成本缺口已关闭」。05 仍有 **PV11/PV12 两项 P1、PV13 一项 P2**。01 本轮扩大边界未发现新增阻断；02/04 保持原候选，不外推成 06 集成通过。

锁定四轨：01 `6cc5748a`（代码 `a3cf9d4b`）、02 `e27b3352`、04 `fcc7838c`、05 `b6b7c596`（代码 `cf7e05a5`）。均独立 detached worktree、dirty=0。主检出树有他人未提交改动，未使用其代码验证。报告分支基于 fetch 后 `gitea/main@d7e53805`，未修改四轨代码，未 push / 合 main / 部署。

## 按发现顺序

### 1. 原修复与收据核验

- J11：UTC Z / +08 的同一上海日两收；实际仍是前一天的 +14 伪装及 +08 对照两拒。
- J12：三节点无环，open=1、审计 gap 保留。扩展 A→B→A→B→A 得五个唯一节点、每条指针严格回指更早日；09-14→09-15 无新转折时项 id 不变；对复现项新做 snooze，次日 reduce `applied=1 / rejected=0`。
- 旧 snooze 的原 round6 探针复跑：历史项已 superseded，重放落 rejected，复现项 open=1。是否继承旧动作仍是 06 的产品决策，不用此结果擅自拍板。
- PV10：单成功 run 的 no fees / tool only / writer+tool 均 unknown；三件套 known CNY 0.93。
- 全量收据按 revision 读时间戳文件，不读 latest：
  - `20260913T160952Z-a3cf9d4b.json`：9650 passed / 77 skipped，failed/error=0，exit=0，dirty=false。
  - `20260913T161605Z-cf7e05a5.json`：9655 passed / 77 skipped，failed/error=0，exit=0，dirty=false。
  - 两个代码 SHA 到交付 SHA 的 diff 均仅 inflight + PROGRESS 文档。本轮没有重跑全量；收据不记录 xfailed，不单凭 JSON 复核该数。

### 2. PV13 [P2]：新增缺组件诊断在输出投影时被丢弃

位置：`intelligence/services/product_value/summarize.py:760-771,827`（05）。

内部 `unknown_components` 条目已有 `uncovered_components`，但构建公开 `cost_full_status.unknown` 时只保留 `{id, reason}`，`detail` 也不返回原条目。单成功 run 仅 writer+tool 时，公开输出只有：

```json
{"id":"unmeasured_task:t-x2-a","reason":"assisted_task_model_cost_unbilled"}
```

整个公开 metric 不含 `uncovered_components`，也不含 `review_model`。因此「缺哪个组件直接可读」尚未兑现，06 无法靠公开合同知道具体补账对象。本例成本状态仍正确 unknown；这是诊断缺失，不是另一条金额误判。

建议：在公开 unknown 或结构化 detail 中保留任务/尝试/缺组件明细，并在公开 `summarize()` 返回值上断言，不只测 helper 的本地列表。

### 3. PV11 [P1]：同任务不同成功 attempt 的费用互相覆盖

位置：`summarize.py:169-182` 联合 `measure.py:556-565`。

`covered` 将任务内所有 run/attempt 的组件并成一个集合；逐 attempt 缺口又只看该 run/attempt 是否有**任意**费用。因此同一任务第一次成功 run 有 writer+review 的账，第二次成功 run 只挂工具账时，两个模型组件由第一次代签，第二次的逐 attempt 缺口被工具费消除。

公开入口 `measure_pair → summarize` 实测（另有一对完整任务作为类别对照）：

| 同任务第二次成功执行的账 | 实际完整成本 | 正确判据 |
|---|---|---|
| 无账 | unknown，已知 CNY 0.92 | unknown |
| 仅 tool 0.01 | **known CNY 0.93** | unknown：第二次 writer/review 缺账 |
| writer+tool | **known CNY 1.29** | unknown：第二次 review 缺账 |
| writer+review+tool | known CNY 1.39 | 合法对照，必须继续 known |

两次成功执行按时间顺序放置，不是重叠/冲突事件。所有 receipt `invalid_reasons=[]`、rejected=[]，两个 attempt 的 evidence_status=ok，summary input_errors=[]。不是坏输入被过滤后造成的假绿。

### 4. PV12 [P1]：全失败早退把缺账托付给仍按“任意费用”核销的下游

位置：`summarize.py:163-168` 联合 `measure.py:557-565`。

全失败任务直接返回无缺组件，理由是由逐 attempt retry 缺口兜底；但工具费也能清掉这条 retry 缺口。失败终态本身不证明 writer/review 没发生：可能在写作、审查或最终落盘之后失败。

探针明确让 retry 处于协议适用集；另一任务挂显式 retry 0.02，防止全局“类别未观察”偶然挡住本任务漏账：

| 本失败任务的账 | 实际完整成本 | 正确判据 |
|---|---|---|
| 无账 | unknown，已知 CNY 0.48 | unknown |
| 仅 tool 0.01 | **known CNY 0.49**，retry 缺口消失 | unknown：失败尝试模型费用未经证明 |
| writer+tool | known CNY 0.85 | 保留已测费用合法通路，不因失败一律强要 review |

receipt 与 summary 零拒绝/零输入错，真实解析结果（离线 synthetic run fixture）为 failed / evidence ok。

归因：同探针在修前 `dd3e8ad0` 与修后 `b6b7c596` 的 PV11/PV12 值一致，所以是 **PV10 相邻遗漏，非本轮新回归**。PV13 是新诊断字段未穿过公开输出层。

## 修复方案取舍

| 方案 | 评价 / 决定 |
|---|---|
| 再往任务集合加费用存在性条件 | 否：仍不能区分同任务不同执行；这是粒度缺失 |
| 每个失败任务一律要求 writer+review | 否：失败可能发生在调用前，强要未发生组件会造假缺口 |
| 把费用覆盖定义成任务 × attempt/run × component，并解释 coverage_scope | 建议：一笔账只能覆盖它实际声明的集合；任务汇总账不能无条件当作某一次 run 的账，反之亦然 |
| 失败按执行阶段/用量/账单证据决定适用组件；证据不足留 unknown | 建议：不能仅凭 failed 推导“review 未发生”，也不能凭工具账推导模型账完整 |
| 对复现项自动继承历史动作 | 不在本轮决定；06 必须明确产品语义，验旧动作与新动作两条路径 |

可迁移结论：覆盖正确性不仅有“类别轴”，还有“执行实例轴”；同一任务的另一轮完整费用不能证明本轮完整。内部补了诊断字段后，还要检查序列化/展示投影有没有丢失。

## 独立验证

- 四轨模块：01=110、02=65、04=74、05=115 passed，共 364 passed。
- 01/05 全仓 ruff 干净；新增探针/断言 ruff 干净。
- 第四/五轮安全断言合计 9 passed；第六轮 6 passed。
- 本轮边界断言：**4 failed / 4 passed**。红为 PV11 两个参数例、PV12、PV13；绿为 J12 重复复现/次日动作及两组费用合法对照。红是被审实现的缺陷证据，不是可豁免门禁。
- 未重跑全量、未重放第一至三轮所有归档探针；未在 06 合成候选跑 backend/frontend/e2e/registry 四叶，未测真人试点。
- 外部目录 pytest 的自动收据 revision 可能绑定测试文件所在报告树；四轨实际被测 SHA 以各 probe JSON 的 `sha` 和 manifest 为准，不冒充报告树上集成通过。

## 可复跑证据与后续

代码/断言：`docs/verification/research-evolution-round7/{probe_round7.py,test_round7.py}`。

耐久原始 JSON、日志、原始全量收据副本与 SHA256 manifest：`~/.finance-runtime/reviews/research-evolution-round7-qc-20260914/`。

```bash
# ROOT 下放锁定的 01 / 05 两棵 worktree；不连接生产数据或模型
RESEARCH_EVOLUTION_QC_ROOT=<ROOT> \
  <主仓>/.venv-workbench/bin/python -m pytest -q \
  docs/verification/research-evolution-round7/test_round7.py -rf
```

05 按执行实例补覆盖后，让原四/五/六轮和本轮断言一起绿，再交 06。01/02/04 可继续作为 06 候选；四轨成组签收仍等待 05 返修与 06 集成验收。不要把此结论写成“可以合 main”。

沉淀：探针已落报告分支可机械复跑；未扩通用 lint，因为费用适用性/覆盖集合依赖领域证据。可迁移手法回写 agent-memory；harness-reference 当前脏，不修改它。

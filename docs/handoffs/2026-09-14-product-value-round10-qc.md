# 05 Round-10 独立复核 · ded78479 / 8a7baedd

## 结论

**原 1 P1 + 1 P2 均关闭；本轮审查范围未发现新增阻断项。05 可作为 06 集成验收候选，不等于允许合 main 或产品最终放行。**

代码 `ded78479f6ec540c705acea04aaded98d1cf0509`；候选 `8a7baeddbb972b4bb6e7fadb8ffad6224ff5ddad`，后者仅新增 inflight/PROGRESS 文档。隔离评审树 `/private/tmp/research-evolution-r10-qc`，分支 `docs/qc-research-evolution-round10`。未改业务实现，未 push，未合 main，未外呼/写生产数据；主检出树他人改动未碰。

## 按发现顺序

### 1. 固定输入与找回原脚本

四轨实际 HEAD 与用户交付一致，逐树 `git status --short` 均空：01=`6cc5748a`、02=`e27b3352`、04=`fcc7838c`、05=`8a7baedd`。本轮未重新给 02/04 签全量结论。

原脚本实际可达：`docs/qc-research-evolution-round9@b3c631b9` 中的：

- `scripts/review_probes/product_value_task_receipt.py`
- `scripts/review_probes/check_product_value_task_receipt.py`

从 `/tmp/research-evolution-r9-qc/` 原样运行。该评审树的 product_value 实现与夹具，相对修前候选 `3fdff5d1` diff 为空：修前 **5 failed / 3 passed**，候选 **8 passed**。本次不是用作者新增测试替代原 QC 断言。

### 2. P1：无 run 辅助任务缺账进入收据，成立

定位 `intelligence/services/product_value/measure.py:598–620`：新增分支只检查 assisted 且 attempts 为空；所需组件为冻结协议适用集与 writer/review 交集，按同 task_id 的 selected 费用逐组件核销；缺项带 task_id、reason=`no_usage_evidence_for_task`，`cost_unknown:task:` 命中收据 incomplete 的既有前缀。

原场景实测：

| 辅助任务账单 | receipt | 缺项 | summary |
|---|---|---|---|
| 无账 | incomplete | writer + review | unknown |
| tool | incomplete | writer + review | unknown |
| writer + tool | incomplete | review | unknown |
| writer + review + tool | valid | 无 | known，CNY 0.93 |

原流程人工计时仍有可信锚点，attempts 为空，不被新规则误伤。协议 review 豁免合法对照通过；新增边界矩阵进一步覆盖无 run 场景的全部模型豁免组合。

### 3. P2：逐组件归属穿过公开汇总投影，成立

定位 `intelligence/services/product_value/summarize.py:829–838`：公开 unknown 保留 component 与存在的 attempt_id/run_id/task_id；id 回退链补 task_id。原来同 attempt 两个模型缺口不再成为两条完全相同的行。

原镜像反例 A（执行1缺review/执行2缺writer）与 B（执行1缺writer/执行2缺review）现在公开 unknown 不同，已知金额仍相同。新 task 级缺口的 component/task_id 也通过公开 metric 核对；不是只检查收据或全文搜索组件名。

注意：id 仍可在同一 attempt 的多组件缺口中重复，判别坐标是 component + 执行身份；本合同并未要求每个 unknown.id 本身是行级唯一键。06 不应只按 id 折叠行。

### 4. 相邻边界矩阵与非阻断建议

新增 `scripts/review_probes/product_value_no_run_matrix.py`，复用夹具构造器生成事件，断言只走公开 `measure_pair → summarize`，不修改收据：

- 16 组：writer/review 协议适用子集 × 已入账子集。逐组要求精确缺集、receipt 状态与 full_cost 状态对应；全部豁免不能被硬拦。
- 4 组：estimated 金额保留估算态；unknown 金额仍阻断完整成本；coverage_scope 不明的费用不能核销；原流程任务的 review 费用不能代签辅助任务。
- 每组均验证零拒收/零 invalid/零 summary input_errors、可信计时保留、task/component 公开投影，以及事件逆序不改变 receipt_id。

**20 组全通过。** unknown 金额已作为费用事实出现，不要求再报“无用量证据”，但它必须留 unknown 金额缺项并降级；避免把不同缺口原因混为一谈。

非阻断建议：`measure.py:602–606` 与 `summarize.py:165–169` 的无 run 组件算法仍各写一份，尚未像有 attempt 分支一样抽入 contracts。当前语义一致，矩阵也全绿，**不是新缺陷、不要求因此重开返修**；后续改覆盖规则时可收敛成共享 task 级 helper，防止两处再次漂移。

## 验证与收据

| 检查 | 本轮结果 / 归属 |
|---|---|
| 05 默认模块，添加评审文件前的干净候选树 | 125 passed，2.07s；`20260914T031658Z-8a7baedd.json` |
| 原 task/receipt QC | 修前 5 failed / 3 passed → 候选 8 passed |
| 原 selection + identity QC | 14 passed（7+7） |
| Round4–7 原归档断言 | 23 passed（4+5+6+8）；实际映射 01=6cc5748a、05=8a7baedd |
| 本轮无 run 矩阵 | 20 scenarios passed |
| 全仓 Ruff | All checks passed；加评审脚本后再次通过 |
| 作者全量原件核验 | 干净树 ded78479；9665 passed/77 skipped/0 failed/0 error；exit_status=0；依赖门禁未绕过 |

全量原件：`~/.finance-runtime/test-receipts/20260914T025114Z-ded78479.json`，revision 全长一致、dirty=false、dirty_paths=[]、worktree_dirty_total=0、解释器为主树 `.venv-workbench/bin/python`。同 SHA 另有 `024717Z` 零收集收据，本次没有拿它充当全量证明。

本轮原始产物与作者收据副本：`~/.finance-runtime/reviews/research-evolution-round10-qc/`：
- `module-clean-receipt.json`、`full-suite-author-receipt.json`
- `task-receipt-before.log`、`task-receipt-after.json/.log`
- `archived-cost-after.log`（22）、`archived-round4-7.log`（23）
- `no-run-matrix.json/.log`、`ruff.log`

外置 pytest 会按脚本所在评审树写 SHA 收据，不能误读为被测业务版本；目标结合 QC_TREE/显式树映射与原始输出核验。模块 pytest 结束时有历史临时目录删除 warning，exit=0；非测试失败。

**未独立重跑全量，未复跑第1–3轮，未验证 06 四轨组合、前端、E2E、registry 或真人试点。** 作者全量原件可信不等于上述范围已验。

## 复验

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
QC_TREE=/tmp/research-evolution-r10-qc "$PY" -m pytest -q -rf \
  /tmp/research-evolution-r9-qc/scripts/review_probes/check_product_value_task_receipt.py
"$PY" scripts/review_probes/product_value_no_run_matrix.py \
  /tmp/research-evolution-r10-qc /tmp/product-value-no-run-matrix.json
```

其它机器可从 `b3c631b9` 提取上述两份原脚本后调整路径；这次已经原样执行，不再留“等脚本可达”的待办。

## 决策与下一步

| 选择 | 否决方案 / 理由 |
|---|---|
| 关闭原两项，05 可交 06 | 不因历史返修轮数继续扣住；实际反例已转绿 |
| 两份相同无 run 规则列维护建议 | 不把纯重复当 P1/P2；目前无可复现错误，合法/非法对照均成立 |
| 保留原独立脚本 + 新领域矩阵 | 不造静态“字段被读过”门禁；语义完整性需要实际事件与公开输出 |
| 复核作者全量收据，不冒充独立全量 | 不以模块/领域矩阵外推 06、前端或全仓新绿灯 |

06 按最终四轨 SHA 做集成验收，再申请合并与部署授权。05 无需因本轮再改业务代码。没有修改共享 harness-reference；新脚本依赖本领域费用合同，归仓内 review_probes，不另造通用工具清单。

# Round-9 QC · 05@cee71963 / 3fdff5d1

## 这个分支做什么
独立复核两项 P1 修复及相邻成本覆盖边界；只评审、不改实现。

## 决策与被否方案
- 原两项 P1 关闭，但新增 1 P1 + 1 P2，05 暂不最终放行；不以旧反例全绿外推完整合同。
- 不拿 summary unknown 替独立收据兜底；不一刀切禁止无 run 的合法 task-scope 费用。
- 领域反例工具化，不造通用静态门禁（覆盖维度依赖业务语义）；未动脏 harness-reference。
- 展开：`docs/handoffs/2026-09-14-product-value-round9-qc.md`。

## 当前状态
评审/探针已提交 `2a826be9`；未 push、未合 main、未改业务/生产数据。隔离树 `/private/tmp/research-evolution-r9-qc`，原主树他人脏改动未碰。
- R9-1[P1] measure 只检查 attempts：无 run 辅助任务缺 writer/review 时收据 valid/空缺口，但汇总 unknown（父版本亦在）。
- R9-2[P2] 新逐组件缺项投影成重复 id/reason；互换两个执行各自缺的组件，收据不同而汇总 unknown 完全相同。投影丢维度是旧问题，本轮新增生产者加重暴露。

## 已验证
- 候选干净树 05=123 passed；全仓 Ruff 绿。
- 原 QC selection 原样复跑：父 3 failed/4 passed → 候选 7 passed；identity 7 passed。
- Round4–7 23 passed；映射 01=6cc5748a/02=e27b3352/04=fcc7838c/05=3fdff5d1。
- 新检查候选 5 failed/3 passed（两项发现），父业务对照也是 5/3，但投影互换测试失败位置不同，见正文。
- task 三件套、协议 review 豁免、原流程人工计时合法对照绿。
- 核实作者全量原件 `20260913T195954Z-cee71963.json`：干净 SHA、9663 passed/77 skipped/exit=0。原件与输出副本：`~/.finance-runtime/reviews/research-evolution-round9-qc/`。

## 未验证 / 已知边界
未独立重跑全量/第1–3轮；未验06最终组合、前端/E2E/registry。作者全量收据不冒充本轮独立执行。01/02/04既有候选不撤回，06仍为最终验收。

## 下一步
05 共用任务级/执行级覆盖规则，收据写全缺项，汇总保留组件归属。复验：`QC_TREE=<候选绝对路径> <主树.venv-workbench/bin/python> -m pytest -q -rf scripts/review_probes/check_product_value_task_receipt.py`。修后再跑原归档与06组合门禁。

## 踩过的坑
- QC旧脚本未推远程但本地评审分支可达，先查本机 Git 对象。
- 外置 pytest 自动收据可能绑定探针树，目标以 QC_TREE/映射及输出为准。
- Round4 文件叫 test_adjacent.py，首次误写 test_round4.py 的 no-tests/exit4 不算回归，改正后23绿。

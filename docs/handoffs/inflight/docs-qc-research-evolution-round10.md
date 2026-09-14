# docs/qc-research-evolution-round10 · 05 Round-10 复核

## 这个分支做什么
独立审 `ded78479` / 候选 `8a7baedd` 的无 run 收据缺账与逐组件投影；不改业务实现。

## 决策与被否方案
- 原 1P1+1P2 关闭；未发现新增阻断项，05 可交 06；否由此直接合 main，组合验收尚未做。
- 原 QC 脚本本机可达并已原样复跑，不以作者等价测试替代。
- 无 run 算法仍两处重复，但目前语义一致且矩阵全绿，仅维护建议，不另开返修。
- 展开与被否方案：`docs/handoffs/2026-09-14-product-value-round10-qc.md`。

## 当前状态
评审正文与领域探针已提交 `308b3584`；本交接随后的文档提交。不改 05 业务，不 push、不合并、不写生产数据。主检出树他人改动未碰。
四轨核对为 01=6cc5748a、02=e27b3352、04=fcc7838c、05=8a7baedd，均干净；并非四轨全量验收。

## 已验证
- 干净候选树 05 模块 125 passed；收据 `20260914T031658Z-8a7baedd.json`。
- 原 task/receipt QC：修前5红/3绿 → 候选8绿；selection/identity 14绿；round4–7 23绿。
- 新 `scripts/review_probes/product_value_no_run_matrix.py`：20组全绿，含16适用/入账子集组合及estimated/unknown/coverage不明/他任务费用；每组验证公开归属与逆序幂等。
- 全仓Ruff通过；提交门禁通过。
- 作者全量原件核实：干净树ded78479，9665 passed/77 skipped，exit=0；不是本轮独立全量。

## 未验证 / 已知边界
未独立重跑全量和第1–3轮；未验06组合、前端、E2E、registry、真人试点。费用unknown的id不是组件级唯一键，06不要只按id折叠多组件行。

## 下一步
06使用最终四轨SHA做集成验收，再申请合并/部署授权。05无需因本轮再改业务。后续修改无run覆盖规则时可提共享task级helper。

## 踩过的坑
原脚本在 `/tmp/research-evolution-r9-qc/scripts/review_probes/`（b3c631b9）；外置pytest收据SHA是探针树，不是目标业务树，须结合QC_TREE核验。
原始产物：`~/.finance-runtime/reviews/research-evolution-round10-qc/`。新矩阵为本领域工具，不另造通用静态字段门禁；未动脏的harness-reference。

# feat/research-evolution-05-product-value · 05 用户价值测量

## 这个分支做什么
按 `docs/river-next-specs@194241dd` 的 05 规格：ProductValueEvent / MeasurementReceipt / PilotSummary 合同，`validate_event` / `measure_pair` / `summarize` 纯函数，只读证据解析器 + 离线 CLI + synthetic 夹具。生产接线归 06（`…/06-integration-contract.md`）。

## 决策与被否方案
- 结构化 JSON + 字符串键，id 排除审计块（幂等）；失败 / 降级 run 直读 `RunStore.load_run`（否复用成功门）；synthetic 单独进 `synthetic_check`，无真人输入回检 `unknown(no_real_inputs)`
- PV4/PV6/PV8–PV12：任务条目在收据里 ≠ 费用已覆盖——测量要 attempts 或有锚点耗时（终态不证明费用）；辅助任务成本按「任务 × 执行实例 × 组件」核验：成功 attempt 要 writer+review、失败要 writer，关联认 attempt_id/run_id（有实例）或 task_id（无 run）；工具费不为模型费作证，第一次的账不为第二次作证；联合身份 + 逐组件规则上移 contracts（`cost_item_covers_attempt` / `attempt_uncovered_components`）测量/汇总共用，selected=False 不作证；合并前验 run 身份冲突（留错阻断）；无 run 辅助任务任务级同规则核验（只查辅助侧）；投影透传组件 + 执行坐标
- PV5/PV7：分母资格 = 任一完整声明窗或激活 + 观察周推导的成熟窗（窗末 ≤ as_of），独立于复用观测；未结束窗只增缺测标签
展开见 `docs/handoffs/2026-09-13-product-value-05-qc-round2.md`。

## 当前状态
基线 `5fb13a8c`；最新修复 **`ded78479`（QC round-10：无 run 任务级核验 + 投影组件归属）**，docs tip 在其上。未推送、未合并。进度 `…/05/PROGRESS.md`，阻塞 `BLOCKED.md`。
QC 二至十轮反例均转绿，本轨累计确证 17 项均已修（清单见 PROGRESS）。**06 联测请用本分支 HEAD（修复 `ded78479`）。**
## 已验证
- 本轨 `test_product_value_*.py`：125 passed（回归均先红后绿）
- 全量 pytest：9665 passed / 77 skipped，exit=0（干净树 @ded78479）；ruff 干净
- 第一至八轮安全断言与归档探针复跑全绿（05extra exit=0；round4–7 全过）

## 未验证 / 已知边界
- 未接 Workbench：source_channel 盖章、单 writer、`due_rechecks` 供给都在 06；product_verified 为否
- `RunStoreEvidenceReader` 只在 tmp 库验过；前端 / e2e / registry 门禁未跑；真人试点未开展

## 下一步
1. 06 按接线合同接入；ledger-map 登记后启用 writer
2. 用户授权后 freeze 协议再招募；合并 main 前跑等价 CI 并等用户确认

## 踩过的坑
- 列全量失败用 `-rf` 或读收据 failed_ids：第四轮失败是 conversation integration 的 10s 墙钟超时 flaky，我误写成 test_pipeline_p0
- 全量收据必须绑最终 SHA 的干净树：QC 不接受外推
- 口径教训：「13 项已修复」类说法不准确；probe argv 契约先读再跑
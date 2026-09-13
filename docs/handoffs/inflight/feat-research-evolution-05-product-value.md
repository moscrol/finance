# feat/research-evolution-05-product-value · 05 用户价值测量

## 这个分支做什么
按 `docs/river-next-specs@194241dd` 的 05 规格：ProductValueEvent / MeasurementReceipt / PilotSummary 合同，`validate_event` / `measure_pair` / `summarize` 纯函数，只读证据解析器 + 离线 CLI + synthetic 夹具。生产接线归 06（`…/06-integration-contract.md`）。

## 决策与被否方案
- 结构化 JSON + 字符串键，id 排除审计块（幂等）；失败 / 降级 run 直读 `RunStore.load_run`（否了复用成功门——幸存者偏差）；synthetic 单独进 `synthetic_check`，无真人输入回检 `unknown(no_real_inputs)`
- PV4/PV6/PV8/PV9/PV10：任务条目在收据里 ≠ 费用已覆盖——测量要 attempts 或有锚点耗时（终态不证明费用）；辅助任务成本按协议适用集 ∩ 固有模型组件 {writer_model, review_model} 逐个核验费用事实，有 run 无 run 同一套（工具费不为缺失的模型费作证；全失败任务由逐 attempt 的 retry 缺口表达）；缺口分四种列
- PV5/PV7：分母资格 = 任一完整声明窗或激活 + 观察周推导的成熟窗（窗末 ≤ as_of），独立于复用观测；未结束窗只增缺测标签
展开见 `docs/handoffs/2026-09-13-product-value-05-qc-round2.md`。

## 当前状态
基线 `5fb13a8c`；已提交至 **`cf7e05a5`（QC 第六轮 PV10 修复，最新）**。未推送、未合并。进度 `…/05/PROGRESS.md`，阻塞 `BLOCKED.md`。
QC 二至六轮原固定反例均转绿，扩大边界累计确证 24 项，本轨占 7 项 P1（PV4–PV10）均已修。证据 `…/reviews/research-evolution-round6-qc-20260913/`。**06 联测请用 `cf7e05a5`。**
## 已验证
- 本轨 `test_product_value_*.py`：115 passed（PV4–PV10 回归均先红后绿）
- 全量 pytest：9655 passed / 77 skipped / 2 xfailed（干净树 @cf7e05a5）；ruff 干净
- QC 第六轮探针 PV10 四行全中 + 安全断言 6 passed；第一至五轮归档探针 05 组复跑不回归（值见 PROGRESS）

## 未验证 / 已知边界
- 未接 Workbench：source_channel 盖章、单 writer、`due_rechecks` 供给都在 06；product_verified 为否
- `RunStoreEvidenceReader` 只在 tmp 库验过；前端 / e2e / registry 门禁未跑（未改前端与注册表）；真人试点未开展

## 下一步
1. 06 按接线合同接入；ledger-map 登记后启用 writer
2. 用户授权后 freeze 协议再招募；合并前跑等价 CI（含前端），合并 main 等用户确认

## 踩过的坑
- 列全量失败用 `-rf` 或读收据 failed_ids：第四轮失败是 conversation integration 的 10s 墙钟超时 flaky（隔离 3/3 绿），我误写成 test_pipeline_p0（grep 匹配了名字带 failed 的用例）
- 全量收据必须在最终 SHA 干净树上跑：上轮 9650 收据绑父提交 + 两个未提交文件，QC 不接受外推
- 口径教训：「先红后绿条数」「13 项已修复」均不准确（实为原固定反例集转绿）；`docs/superpowers/summaries/2026-09-13-*.md` 从未落盘
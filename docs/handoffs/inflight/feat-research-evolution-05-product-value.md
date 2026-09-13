# feat/research-evolution-05-product-value · 05 用户价值测量

## 这个分支做什么
按 `docs/river-next-specs@194241dd` 的 05 规格：ProductValueEvent / MeasurementReceipt / PilotSummary 合同，`validate_event` / `measure_pair` / `summarize` 纯函数，只读证据解析器 + 离线 CLI + synthetic 夹具。生产接线归 06（`…/06-integration-contract.md`）。

## 决策与被否方案
- 结构化 JSON + 字符串键，id 排除 `generated_at` / `event_accounting`；否了 dataclass 基类与含审计块（幂等）
- 失败 / 降级 run 直读 `RunStore.load_run`；否了复用 `verify_run_binding` 成功门（幸存者偏差）
- synthetic 单独进 `synthetic_check`；无真人输入回检 `unknown(no_real_inputs)`；否了混算贴标签与显示 0.0
- PV4/PV6：任务条目在收据里 ≠ 费用已覆盖——核销缺口只认任务级成本事实（attempts 或有锚点耗时）；终态（含放弃）证明任务状态不证明费用；「无收据」与「收据在但没测」分列
- PV5/PV7：分母资格 = 任一完整声明窗（窗末 ≤ as_of）或激活 + 协议观察周推导的成熟窗，独立于复用观测；后续未结束窗只增 `later_observation_window_incomplete` 标签，不撤销已成熟资格
展开见 `docs/handoffs/2026-09-13-product-value-05-qc-round2.md`。

## 当前状态
基线 `5fb13a8c`；已提交至 **`2f0d3410`（QC 第三轮 PV6+PV7 修复，最新）**。未推送、未合并。进度 `…/05/PROGRESS.md`，阻塞 `BLOCKED.md`。
QC 二/三轮原固定反例均转绿，扩大边界累计确证 13 项，本轨占 4 项 P1（PV4–PV7）均已修。证据 `~/.finance-runtime/reviews/research-evolution-round3-qc-20260913/`。**06 联测请用 `2f0d3410`。**
## 已验证
- 本轨 `test_product_value_*.py`：112 passed（PV4–PV7 回归均先红后绿）
- 全量 pytest：9652 passed / 77 skipped / 2 xfailed（最终 SHA 干净树 @2f0d3410）；ruff 干净
- QC 第三轮探针 PV6/PV7 与安全断言（5 failed → 5 passed）全绿；第一/二轮探针复跑不回归（逐字段值见 PROGRESS）## 未验证 / 已知边界
- 未接 Workbench：source_channel 盖章、单 writer、`due_rechecks` 供给都在 06；product_verified 为否
- `RunStoreEvidenceReader` 只在 tmp `RunStore` 上验过；前端 / e2e / registry 门禁未跑（未改前端与注册表）；真人试点未开展（field pending 是事实不是缺陷）

## 下一步
1. 06 按接线合同接入；ledger-map 登记后启用 writer
2. 用户授权后 `python -m intelligence.eval.product_value freeze` 冻结协议再招募
3. 合并前跑等价 CI（含前端），合并 main 等用户确认

## 踩过的坑
- 全量收据必须在最终 SHA 干净树上跑：上轮 9650 收据绑父提交 + 两个未提交文件，QC 不接受外推
- 上轮口径「41 条测试先红后绿」不准确（至少 consented_pairs 用例修前修后都绿）；「13 项已修复」实为「原固定反例集转绿」。`docs/superpowers/summaries/2026-09-13-*.md` 从未落盘
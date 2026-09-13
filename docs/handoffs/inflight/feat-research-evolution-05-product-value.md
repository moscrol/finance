# feat/research-evolution-05-product-value · 05 用户价值测量

## 这个分支做什么
按 `docs/river-next-specs@194241dd` 的 05 规格：ProductValueEvent / MeasurementReceipt / PilotSummary 合同，`validate_event` / `measure_pair` / `summarize` 纯函数，只读证据解析器 + 离线 CLI + synthetic 夹具。生产接线归 06（`…/06-integration-contract.md`）。

## 决策与被否方案
- 结构化 JSON + 字符串键，id 排除 `generated_at` / `event_accounting`；否了 dataclass 基类与含审计块（幂等）
- 失败 / 降级 run 直读 `RunStore.load_run`；否了复用 `verify_run_binding` 成功门（幸存者偏差）
- synthetic 单独进 `synthetic_check`；无真人输入回检 `unknown(no_real_inputs)`；否了混算贴标签与显示 0.0
- PV4/PV6/PV8：任务条目在收据里 ≠ 费用已覆盖——核销缺口只认任务级事实：测量要 attempts 或有锚点耗时（终态不证明费用）；辅助任务的成本另要 run / 用量 / 费用事实（人工计时只覆盖时间）；「无收据」/「收据在但没测」/「计时但无费用事实」分列
- PV5/PV7：分母资格 = 任一完整声明窗或激活 + 协议观察周推导的成熟窗（窗末 ≤ as_of），独立于复用观测；后续未结束窗只增缺测标签，不撤销已成熟资格
展开见 `docs/handoffs/2026-09-13-product-value-05-qc-round2.md`。

## 当前状态
基线 `5fb13a8c`；已提交至 **`197133f2`（QC 第四轮 PV8 修复，最新）**。未推送、未合并。进度 `…/05/PROGRESS.md`，阻塞 `BLOCKED.md`。
QC 二至四轮原固定反例均转绿，扩大边界累计确证 17 项，本轨占 5 项 P1（PV4–PV8）均已修。证据 `~/.finance-runtime/reviews/research-evolution-round4-qc-20260913/`。**06 联测请用 `197133f2`。**
## 已验证
- 本轨 `test_product_value_*.py`：113 passed（PV4–PV8 回归均先红后绿）
- 全量 pytest：9653 passed / 77 skipped / 2 xfailed（干净树 @197133f2；首跑 1 failed 为已知负载抖动项 test_pipeline_p0，重跑即过）；ruff 干净
- QC 第四轮探针 PV8 与安全断言（4 条）全绿；第一/二/三轮归档探针 05 组复跑不回归（值见 PROGRESS）## 未验证 / 已知边界
- 未接 Workbench：source_channel 盖章、单 writer、`due_rechecks` 供给都在 06；product_verified 为否
- `RunStoreEvidenceReader` 只在 tmp `RunStore` 上验过；前端 / e2e / registry 门禁未跑（未改前端与注册表）；真人试点未开展

## 下一步
1. 06 按接线合同接入；ledger-map 登记后启用 writer
2. 用户授权后 freeze 协议再招募；合并前跑等价 CI（含前端），合并 main 等用户确认

## 踩过的坑
- 全量收据必须在最终 SHA 干净树上跑：上轮 9650 收据绑父提交 + 两个未提交文件，QC 不接受外推
- 上轮口径「41 条测试先红后绿」不准确（至少 consented_pairs 用例修前修后都绿）；「13 项已修复」实为「原固定反例集转绿」。`docs/superpowers/summaries/2026-09-13-*.md` 从未落盘
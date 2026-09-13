# feat/research-evolution-05-product-value · 05 用户价值测量

## 这个分支做什么
按 `docs/river-next-specs@194241dd` 的 05 规格：ProductValueEvent / MeasurementReceipt / PilotSummary 合同，`validate_event` / `measure_pair` / `summarize` 纯函数，只读证据解析器，离线 CLI，synthetic 夹具。生产接线归 06（合同见 `docs/research-pilots/research-evolution/06-integration-contract.md`）。

## 决策与被否方案
- 结构化 JSON + 字符串键，id 排除 `generated_at` / `event_accounting`；否了 dataclass 基类与含审计块（幂等）
- 失败 / 降级 run 直读 `RunStore.load_run`；否了复用 `verify_run_binding` 成功门（幸存者偏差）
- synthetic 单独进 `synthetic_check`；无真人输入回检 `unknown(no_real_inputs)`；否了混算贴标签与显示 0.0
- PV4：任务条目在收据里 ≠ 费用已覆盖——逐任务核验测量事实（终态 / 尝试 / 耗时至少一样），「无收据」与「收据在但没测」分列；否了按 receipt.status 整票判
- PV5：复用分母资格 = 任一完整观察窗（窗末 ≤ as_of），不看最晚窗末；后续未结束窗另列 `later_observation_window_incomplete`；否了沿用最晚窗末（2/6 fail 被洗成 2/3 pass）
展开见 `docs/handoffs/2026-09-13-product-value-05-qc-round2.md`。

## 当前状态
基线 `5fb13a8c`；已提交至 **`24bce5e8`（QC 第二轮 PV4+PV5 修复，最新）**。未推送、未合并。进度 `docs/superpowers/plans/2026-09-13-research-evolution/05/PROGRESS.md`，阻塞 `BLOCKED.md`。
QC 第二轮（`~/.finance-runtime/reviews/research-evolution-repair-qc-20260913/`）：原 13 项固定反例转绿，扩大边界确证 8 项，本轨占 2 项 P1 均已修（细节见下方快照）。**06 联测请用 `24bce5e8`。**
## 已验证
- 本轨 `test_product_value_*.py`：110 passed（含本轮新增 2 条 PV4/PV5 回归，先红后绿）
- 全量 pytest：9650 passed / 77 skipped / 2 xfailed，exit 0；ruff 干净
- QC 探针 `probe_05_extra.py` 复跑：PV4 空壳并入后仍 unknown、known_cost 与缺口不变；PV5 追加未来窗后分母仍 q1..q6、rate 0.3333、verdict fail
## 未验证 / 已知边界
- 未接 Workbench：source_channel 盖章、单 writer、`due_rechecks` 供给都在 06；product_verified 为否
- `RunStoreEvidenceReader` 只在 tmp `RunStore` 上验过；CLI `--users-root` 会在 runs 目录建 sqlite，对副本用
- 前端 / e2e / registry 门禁未跑（未改前端与注册表）；真人试点未开展（field pending 是事实不是缺陷）

## 下一步
1. 06 按接线合同接入；ledger-map 登记后启用 writer
2. 用户授权后 `python -m intelligence.eval.product_value freeze` 冻结协议再招募
3. 合并前跑等价 CI（含前端），合并 main 等用户确认
## 踩过的坑
- 上轮口径「41 条测试先红后绿」不准确（至少 test_consented_pairs_still_reach_a_verdict 修前修后都绿）；「13 项已修复」实为「原 13 项固定反例转绿」。`docs/superpowers/summaries/2026-09-13-*.md` 从未落盘
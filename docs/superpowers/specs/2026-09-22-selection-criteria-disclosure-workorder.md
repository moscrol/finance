# 2026-09-22 候选筛选口径未交代工单（#79，占位）

> 来源：#70 `2026-09-22-research-empty-delivery-gate-pr-workorder.md` §目标 4 之二。现场 `run_20260922_191550_067475`，冻结夹具见 `intelligence/tests/fixtures/live_products/run_20260922_191550_067475/`。
> 前置：#70 合入；与 #65（口径越界 lint）共用 `evidence_claim_findings` 通道，先确认不是同一条规则的变体再开工。

## 问题

正文从量价双红口径的候选板块里只报了「半导体（设备/存储）与 AI 算力（CPO/算力租赁）」两个方向，**没有交代从全部双红候选里挑出这两个的排序依据**（#70 工单核对：候选池 85 个双红板块，正文只报两个，未说按什么排）。用户无法判断「最有机会」是按边际量、涨幅、成交额还是模型偏好排出来的；这不是证据缺口，是**选择口径缺失**，现有必需输出（`direct_assessment / counterpoint / evidence_boundary`）没有一项要求它。

## 目标（待细化）

- 对「从候选集合里挑出 N 个」形状的答案，要求正文交代**筛选依据与候选池大小**（例：按边际量降序取前 2，候选 85）。落点二选一，先量后定：A 作为 `comparison_analog` / ranking 题型的必需输出 `selection_criteria`（走 `task_fulfillment` 词表，与 #70 的双钥匙兼容：缺它单独不拦）；B 作为 advisory 类 `evidence_claim_findings`（与 #65 同通道）。
- 夹具：现场 `tool_result` 里的候选池原文 + 正文；不手写。
- 非目标：不规定「正确」的排序指标；不改排序工具。

## 验收（占位）

- [ ] 现场夹具上报出 `selection_criteria_missing`（或等价 finding）一次；交代了依据的对照正文零发现。
- [ ] 若选 A：历史 run 上该题型 marker 缺失占比先落盘，再决定是否升为阻断（与 #70 的决策 A/B 同一口径）。
- [ ] 四叶全绿、收据绑分支尖；pathspec 提交；合 main 等用户确认。

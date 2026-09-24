# 2026-09-22 模型自造实体代码（`899050.BK`）工单（#80，占位）

> 来源：#70 `2026-09-22-research-empty-delivery-gate-pr-workorder.md` §目标 4 之三；同单登记 #70 非目标里的诊断漏报（`evidence_claim_findings` 对 `endpoint_not_path` 类零发现）。现场 `run_20260922_191550_067475`，冻结夹具见 `intelligence/tests/fixtures/live_products/run_20260922_191550_067475/`。
> 前置：#70 合入。

## 问题

1. **自造实体代码**：模型以 `899050.BK` 为板块实体调用 `history_query`（`entity_codes=["899050.bk"]`），工具返回 `sample: 0`；该代码随后进了 `outcome.gaps`（「899050.BK 板块历史特征缺失，板块级可复算条件比较未完成」），**没有进公开答案**——所以这次没伤到用户，但链路上没有任何一处校验「这个代码在我们的板块名单里存在吗」。同形问题 [[bare-code-exact-filter-returns-zero-rows]] 已有先例：裸代码 / 错后缀查不到行，模型再把「本地缺数据」当结论。
2. **诊断漏报**：`semantic_verifier.evidence_claim_findings` 为空，而人工核出至少一处 `endpoint_not_path` 类措辞缺陷（`audit.json` 第 45 行记录）。零发现 ≠ 无缺陷；本单只登记，不在这里修判官。

## 目标（待细化）

- 实体代码**存在性校验**放在工具入口（`history_query` / `finance_query` 的 `entity_codes` 参数）：对照 `sector_universe` published 快照与 `dim_*` 表，不存在即返回 `unknown_entity_code` 结构化错误（带「最近似的已知代码」提示，**不猜交易所后缀**），并在 `outcome.gaps` 里标 `fabricated_entity`，供判官与 #70 的交付门读到。
- 夹具：现场 `tool_request` / `tool_result` 原文；不手写。
- 非目标：不改判官 prompt；不做实体消歧（那是另一条线）。

## 验收（占位）

- [ ] 现场夹具上 `899050.BK` 被判 `unknown_entity_code`，gaps 出现 `fabricated_entity`；真实存在的板块代码零误报（用 published 快照全量对照）。
- [ ] `endpoint_not_path` 漏报登记在 #75 独立 QC 的复核清单里，有人认领后再开单。
- [ ] 四叶全绿、收据绑分支尖；pathspec 提交；合 main 等用户确认。

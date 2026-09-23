# 2026-09-23 · PR #873 / #63 保全质检整改 · 合入收口

## 终态

PR #873（`fix/push-preview-acceptance-0923`）已合入 `main`：

- 合并提交：`760248ecebc79fbe4f2686ddd42255c1a00ec862`
- 双亲：`3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`（合入前 main）与
  `d18921e0f77ee6ee9de86ef00cc15e43841edbbe`（精确候选）
- 合并 tree：`88bc71774110c189f65925f32512ed5a6acf1564`
- PR 状态：closed / merged；未强制合并，候选远端分支保留，未删除
- 合入后远端 main 继续前进；本快照不把后来 main 的提交冒充为 #873 的门禁对象

原在途交接 `docs/handoffs/inflight/fix-push-preservation-qc-0923.md` 已随本次收口出册；本文件记录合入终态，原始决策背景仍见 `docs/handoffs/2026-09-23-push-preservation-qc.md`。

## 本单改动与边界

这张 PR 只带归档预览 / Git 原始对象身份校验 / 验收证据、测试和流程文档：

- `scripts/check_evidence_archive.py`
- `scripts/preview_evidence_archive.py`
- 对应 `tests/`、`docs/workflows/` 与质检证据包

合入前后没有 `intelligence/`、`intelligence/webapp/` 或 `market_feature_store/` 改动，也没有部署配置、服务入口或生产数据写入。因此 **#873 不需要单独部署或重启 8792**；若将后来整个 `main` 切到运行时，那是另一个部署授权与验收事项。

## 合入后验证

所有门禁均绑定合并提交 `760248ecebc79fbe4f2686ddd42255c1a00ec862`，不是临时组合提交：

- Python：`14,568 passed / 0 failed / 85 skipped / 2 xfailed`
- Ruff：通过
- 前端 install、lint、typecheck、unit、build、E2E：全部通过；unit `120 passed`，E2E `34 passed / 2 skipped`
- Registry 五项：全部通过
- 归档完整性：manifest 与提交内容 `38/38` 一致
- `check_test_receipt.py`：实际合并 SHA、全量范围、干净树、base drift 0 均核过
- 合并记录：`~/.finance-runtime/reviews/pr873-authorized-merge-20260923/merge-record.json`
- 合后最终记录：`~/.finance-runtime/reviews/pr873-authorized-merge-20260923/postmerge-final.json`

此前证据包中的 `44 passed` 只是工具定向回归，不能替代上述合入后全量门禁；vault lint 的 `33 errors / 17 warnings` 是既有边界，未宣称全仓 vault 全绿。

## 后续

1. 使用归档工具时遵循 `docs/workflows/evidence-archive-preview.md` 的 `prepare → 显式提交/推送 → verify` 流程；校验器不自动写 refs。
2. 保留两个 salvage 保全头和候选分支，除非另有明确清理授权；它们不是待合入的产品分支。
3. 不把本单的归档完整性结论扩大成 market-cutoff 产品验收、真实 Workbench 验收或生产部署结论。

本次收口没有部署、重启服务或写生产库。

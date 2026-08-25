# feat/disclosure-scan-p1-residual

## 这个分支做什么

披露扫描 P1-① 残差写手（稿 v1.3，计划 `docs/superpowers/plans/2026-08-25-disclosure-scan-p1-residual-writer.md`）：`status=hit` 名单开 `compose`，模型持契约（`contract_guidance` 槽）只写解读；出稿闸包外码/名单行形状整丢回 P0 纯包 + degrade。

## 当前状态

已提交 `3f1b7f44` 已推，**PR #395 open，合并等用户确认**。生产 8792=`54a6f096`（含 P0.5），未含本刀。

## 下一步

1. 用户确认 → 合 #395 → 切 8792 → 冻结题重放验 R5：名单行零增删、尾段出现集采双重性/反证/预算边界解读、无 `disclosure_residual_dropped`。
2. R5 过 → P1-③ 自定义窗口（小刀）→ P1-②（PDF 品种金额，先探巨潮 detail API 与预算）→ P1-b（0 工具降级 vs 研究缺口分列）。

## 未验证 / 已知边界

- 残差**内容质量**未 live 验证（离线只锁形状不锁内容）；首发若被闸整丢 = 回 P0 形状，无害可重试。
- 闸在 `_revise_synthesis_on_warn` 之后、终稿渲染之前——修订轮产物同样过闸。
- e2e 未跑（webapp 零改动）。

## 已验证

ruff 绿；全量 **6497P / 12S / 0F** @ `3f1b7f44`；定向 25 条（bind 反转、闸五形状、契约槽、编排源码顺序断言）。

## 踩过的坑

- `answer_spec` 证据行会被截到 8 条（`[:8]`）：残差合成输入必须用**完整包渲染**，spec 只配草稿骨架。
- worktree 跑 e2e 会把 startup 账本写进夹具 `intelligence/tests/fixtures/chat_workbench_repo/state/`（FINANCE_WS=夹具根）；本轮已清理未提交。根治 = 测试环境覆盖 `FINANCE_DEPLOY_LEDGER`，另立小刀。
- 同测试内 `_db(tmp_path)` 只能建一次（同路径二次 CREATE TABLE 会 CatalogException）。

## 工具沉淀盘点

无新脚本。`gate_disclosure_residual` 是「组件写正文、模型只写边注」方法论的出稿闸半边，归属 `deterministic-prefetch-llm-residual.md` 既有条目，不另建清单。

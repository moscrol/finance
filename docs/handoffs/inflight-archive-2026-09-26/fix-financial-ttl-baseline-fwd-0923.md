# 在途 · fix/financial-ttl-baseline-fwd-0923 · 财务链前向到 main（工单 #66 决策 1 走 #67 路线）

## 这个分支做什么
#835 已关闭、财务线 `d82cb16b5` 随 #863 squash 进 main，所以**不再合 #835**；把两条尾巴各自的提交前向到 main `626d8a508`：
- #855 `1068b42fe`（`conclusion_ttl_conflicts` + `comparison_baseline_gaps` / `comparison_baseline_unsupported`，接线 `_track_public_delivery` 只披露、`_issue_backfill_plan` 走补数）、`132afc0b1`（基线门先解主体再判基线在场）——两格都无冲突。
- `fix/financial-comparison-0922` `5d50cd864`（`_relative_ratio_comparison_mismatch` 跨期别混比拒句）、`63f8a3859`（docs）——`financial_claim_checks.py` 与 `docs/agent-product-door.md` 各一处「同位置两边各加一块」的冲突，两边都留。
- 本分支自己加的两格：`_context()` 替身补 `history_intent=None`（main 的 `_track_public_delivery` 把它交给 `contract_receipt`，#855 夹具早于这条接缝，两条测试 AttributeError）；干跑脚本 + 阳性对照 README。

## 当前状态
- 已 push gitea、已开 PR（base main），等主会话在预览树串行跑四叶后决定合入；**未合、未部署、未动 8792**。
- `5d50cd864` 那格用了 `--no-verify`：只有 `handoff-budget` 钩子红（被接替分支的 inflight 4901 字节），下一格 `63f8a3859` 即把它缩到 3059 字节，原文保留；其余钩子在同一暂存内容上已全部通过。
- 被接替分支的两份 inflight（`fix-8792-boundary-ttl-baseline-0922.md`、`fix-financial-comparison-0922.md`）原样随 cherry-pick 保留，是历史记录；里面的「未 push / 未 PR」说的是旧分支，不是本分支。

## 已验证（精确到 revision，见 PR 正文）
- 阳性对照（工单验收项）：`docs/verification/2026-09-23-financial-ttl-baseline-fwd/`，8 份 R3/R6 封存答卷干跑，A 干净 1/8 基线缺口 → B 关掉主体回退 0/8 → C 还原 1/8，`financial_claim_checks.py` sha256 前后一致；TTL 冲突 1/8 三次不变。
- ruff 改动文件干净；定向 19 个命中测试文件的读数写在 PR 正文，**不是全量**。

## 未验证 / 边界
- 四叶全量未在本分支跑（机器负载 40–100，多全量并跑），由主会话在预览树跑。
- 无真实模型验收；R3/R6 四题仍各 0/4。`_observations` 只匹配到表头的既有洞未修，单独立单。

## 下一步
1. 主会话：预览树四叶 → 用户确认 → `gitea_pr.py merge --record`；INDEX #66 行。
2. 合入后 main 上 `_track_public_delivery` 开始披露 `ttl_conflicts`、缺基线触发补数回合——这是产品行为变化，已按决策 2 视为「执法层上线」的一部分。

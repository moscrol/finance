# feat/reading-rules-baseline-batch1

## 这个分支做什么

KOL 判读方法内置为领域基线（默认开）；判断倾向留 perspective_lab 显式开关。

## 当前状态

8 笔 `789916f5`…`fc25c48b`，未合未推。25 条：7 全局 + 14 挂 8 块 + 4 条 `_PENDING_RULES`。`FINANCE_READING_BASELINE=0` 两处归零。
基线分叉：从 `fix/l2-pause-switch-public-assets` 长出。`git cherry gitea/main`：`1df6844d` 已是 `-`（#217 等价），多带的是 `edd5c5ba`。脏树 ~110 非本单，未碰。

## 未验证 / 已知边界

- 从未 live；A/B 零数据。
- 与 #222 未共存验证（同改系统提示词）。后合方跑 single 视角 live：sidecar + `POST /api/conversations`（`live_probe ask` 落中立泳道）。spec 在 `fwp-wt-perspective-narrative` / #222 §3.3.3，本树无。
- `user_framework` 故意没建。B 类 4 条未落地。

## 下一步

1. 干净树 `rebase --onto gitea/main 1df6844d`（丢掉已入 main 的 L2；`edd5c5ba` 另决）。主仓脏树不动。
2. **G1b 需你在场**：`open_times` 全 NULL，外呼比对 payload。不修则 SPT-A06 半边做不了。见 `20495cce` / `fc25c48b`。
3. G1a（有封板时间、无块输出）等 G1b 一起做全。
4. 总开关 A/B。

## 踩过的坑

- 画像真身 `~/.local/share/finance-workbench/users/default/`，不是仓内 `intelligence/users/`。
- 负面断言只查一表：封板时间在 `fact_theme_limit_stock_daily`。
- 变异前先提交：`git checkout` 会丢掉未提交实现。
- `foresight_methodology.md` 已含 5/7 条全局；`_METHODOLOGY_OVERLAP` + 漂移门禁。

## 工具沉淀盘点

漂移门禁与「登记未接线」反查已在测试里，未抽到 scripts/TOOLKIT（要语义判断）。

## 已验证

`20260819T040534Z-e2673f02`：4364/2（rev=`e2673f02`，dirty）。G1 文案回归 `fc25c48b`。

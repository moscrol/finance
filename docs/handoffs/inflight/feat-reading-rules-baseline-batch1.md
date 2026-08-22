# feat/reading-rules-baseline-batch1

## 这个分支做什么

KOL 判读方法内置为领域基线（默认开）；判断倾向留 perspective_lab 显式开关。
**这棵脏树已弃用。** 收口在干净树 `feat/reading-rules-baseline-r2`。

## 当前状态

活代码：`/Users/a77/fwp-wt-reading-rules-baseline` @ `ad3f4172`。Gitea #343 open、git 可合。
主仓脏区是复盘/台账，不是本单，**不要在这 rebase / 不要从这合**。
本会话另收口 SPT 周报回填（用户空间 50 篇）→ `docs/handoffs/2026-08-23-sptfei-weekly-backfill.md`。

## 未验证 / 已知边界

- 从未 live；G1a/G1b、总开关 A/B、`user_framework` 未做。
- 2026-08-23 全量 pytest：r2 与 `gitea/main@b4689295` **同 4 红**（非本单引入）。门禁不准合。

## 下一步

1. 修绿这 4 条，或你明示「带红也合」，再合 #343。
2. G1b 需你在场（`open_times` 全 NULL）。
3. 再喂 SPT：缺 2026.5 / 31–33、2025.41/48。

## 踩过的坑

- 画像真身 `~/.local/share/finance-workbench/users/linxiaoqi5111/`，不是仓内 `intelligence/users/`。
- 只跑 `intelligence/tests` 子集会漏掉「main 已红」；合前要比对同一 4 条在 main 上是否也红。

## 工具沉淀盘点

存量红对照（同测两边跑）是手法，未抽脚本（一次对照，样本不够）。

## 已验证

r2：ruff 绿；全量 6109P / 4F / 13S。同 4 条在 main 同样失败。生产 API `sptfei` article_count=50。

# feat/reading-rules-baseline-batch1

## 这个分支做什么

把两位 KOL（SPT / 风远）的**判读方法**（怎么读数据）内置为领域基线、默认生效；**判断倾向**留 perspective_lab 的 persona 层显式开关。

## 当前状态

6 提交 `789916f5`…`20495cce`，**未合 main未推送**。25 条规则：7 条全局进两引擎提示词、14 条挂 8 个数据块、4 条缺数据源挂 `_PENDING_RULES` 不注入。总开关 `FINANCE_READING_BASELINE=0` 两处同时归零。

⚠ **分支基线不干净**：切 main 被别人未提交的 `2026-08-18-daily-full-review-recovery.md` 挡住，实际从 `fix/l2-pause-switch-public-assets` 长出，**多带非本单提交 `1df6844d`**。合并前先定 rebase 还是连带。工作区另有 ~110 个非我改动，未碰。

## 未验证 / 已知边界

- **从未跑过 live**：只有单测+全量回归，判读基线没在真实问答里出过一次答案；总开关的 A/B 增量**零数据**。
- **与 `fix/perspective-narrative-contract` 未做共存验证**：那条从 main 拉、不含本分支代码，两者改同一份系统提示词。**后合并的必须跑一次 single 视角 live**，见那份 spec §3.3.3 / §5。
- `user_framework` 画像**故意没建**：判读已内置、血缘在每条规则 `source`，建空壳会让 UI 选中后拿到空的。B 类 4 条结构同样未落地。

## 下一步

1. 定分支基线怎么处理（rebase 掉 `1df6844d` 或连带）。
2. **G1b 需你在场**：`fact_theme_limit_stock_daily.open_times` 全 NULL（静默降级，覆盖率审计发现不了），查证需外呼 fupanhui 比对 payload。**不修则 SPT-A06 半边永远做不了**。详见 `20495cce`。
3. G1a 只解半条规则（封板时间有数据但无块输出它），建议等 G1b 一起做全。
4. 跑总开关 A/B 拿增量读数。

## 踩过的坑

- **读错数据根**：仓内 `intelligence/users/` 不是运行时根，真身 `~/.local/share/finance-workbench/users/default/`（launcher 设 `FORESIGHT_USERS_DIR`、不设 `FORESIGHT_USER`）。据仓内路径断言「画像没建」是错的。三根并存见 `2026-08-16-sptfei-perspective-migration.md`。
- **负面断言只查一张表**：断言「缺封板时间」只看 `fact_limit_advance_daily`，数据在 `fact_theme_limit_stock_daily`。同形状犯两次。
- **变异测试前必须先提交**：`git checkout <file>` 还原时把未提交实现一起丢了。
- **同一套方法论存两处**：`intelligence/foresight_methodology.md`（只喂 foresight）已含本分支 7 条全局里的 5 条。已加 `_METHODOLOGY_OVERLAP` 锚点+双向指针+漂移门禁，那边改措辞这边会红。

## 工具沉淀盘点

- 两个通用件满足 `BUILD.md` 收录判据但**本轮未提炼，留给接手者**：漂移门禁模式、「登记了但没接线」反查测试。
- 变异测试手工 12 次，够格写 `scripts/mutate_check.py`。

## 已验证

4364 passed / 2 skipped（`20260819T040534Z-e2673f02`）、门禁全绿、十二处变异转红后还原。


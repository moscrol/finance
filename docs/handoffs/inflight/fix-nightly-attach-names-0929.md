# 在途交接 · fix/nightly-attach-names-0929

2026-09-30 10:40 写，基线 `gitea/main@756932714`。

## 这个分支做什么
09-29 夜跑补名热修根 `0e7f77025409`（冻结根 fe9fdbfd7 + 4 个 cherry-pick -x）的**溯源分支**。根已被取代，**不在此继续开发**。

## 决策与被否方案
- 选最小热修根（9 文件、只改一处 plist）；否：冻结根整体推进 4 天 / 原地热补 / 等夜跑挂了再恢复；因：改动面小、可一步回滚、不动回滚锚点。用户 09-29 16:14 选「执行切换」（依据：真封存排练 + 全量 15664P）。

## 当前状态
- **已被取代**：17:33 main `df3e37744` 把夜跑根迁到 0e7f；#977 合入 #970 内容、换根 `541ef50ba2b2`；#982 换现役根 `9c1e3154f613`。#970 已关，feat 分支已并 main。
- 回滚链 9c1e → 541ef → 0e7f；旧根 fe9fdbfd7 **已删**。0e7f **不在 main**、`finance-sync-0e7f77025409` 锁定：**分支别删、根别拆**，直到 541ef 不再需要回滚。
- **作废**：我的切换记录（#985 已存档）写的「回滚 = /tmp/wt-audit/rollback-sync-root.sh 回 fe9fdbfd7」已失效，脚本已删；勿照做。

## 已验证
09-29 夜跑（0e7f 根）全绿、质量门 COMPLETE。但**补名步 0 目标**（收据 applied=false）；新股 301716.SZ / 920202.BJ 是夜跑后由两源补行（#976，source=`…gapfill-two-source`）补入，不是补名补的。生产已到 09-29，09-28 已补。

## 未验证 / 已知边界
- 补名步 `ok` 只表示没出错，runlog 不显示 targets 数；是否真补看 `db/quote-captures/tencent/attach-receipts/*.json` 的 applied / targets。
- 09-30 夜跑（9c1e 根）未验：应见 capture-dated-quotes / attach-capture-names / bridge-gap-fill 三步 ok。
- 生产 fact_stock_daily 仍缺 7 行：09-22（300803.SZ、301686.SZ、920229.BJ）、09-23（001225.SZ、002961.SZ、920025.BJ）、09-24（920201.BJ）。其中 4 个是新股首日、无当日封存，合同 1 补不了；另 3 只原因未逐只核。

## 下一步
1. 09-30 18:45 后核上面两项与生产行数。2. 7 行老缺口等用户定名称来源；复核用 `scripts/report_bridge_gaps.py`，别手写 SQL。3. 541ef 不再需回滚锚点时，`worktree_closeout.py` dry-run 收口 0e7f 根，再删本分支。

## 踩过的坑
- 我曾说缺行是「同花顺原始表名字为空」：错。`fact_stock_daily_hithink` 没有名字列（我对 NULL 常量取了 None）；真因是桥对复牌 / 新股首日 / 送转不猜值（#974）。
- 「缺口没补」只对当时成立，发布发生在我查之后：先读生产库，别信 README 里的时间戳（偏差约半小时）。
- react = react 臂 run trace 与 8792 做 trace diff（不是 ReAct 工单或前端）。

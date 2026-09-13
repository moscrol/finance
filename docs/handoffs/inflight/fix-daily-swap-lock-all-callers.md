# daily-swap 换库契约：七轮修补完成，待八轮独立复审

## 这个分支做什么

公共 staging 编排的换库契约加固（基于 hithink 重建 601db6dd 叠七刀）。**生产库未动、未合并。**

## 决策与被否方案

- 七轮 P2：existing/absent 分类**钉死在本轮首次观察**（探针前那次 exists）；否了「发布前再加 stat」（审查明确不要）、否了「探针返回值下传」（审查探针按钉死形态验收）。已见旧库后消失只剩 rc=2：探针窗口内→SwapTargetReplacedError（单独措辞）；之后→hold_swap_lock 开锁失败。
- 删掉「三文件零漂移→门禁可外推」断言：main 侧改 48 路径，文本可组合≠行为正确；收据只对快照成立。
- 一般 clone IO 裸抛（cp/copy2 EPERM/ENOSPC 逃出编排）：审查裁定另开小提交，**不夹带**；是错误出口旧债不是数据覆盖。

## 当前状态

`2d16a7f7` 已提交（代码+测试+round6 报告修订+round7 快照+lessons）。**等八轮独立复审。**
七轮审查报告：`docs/qc-daily-swap-dfb6ce87` 分支 @ e8ad314b（`docs/handoffs/2026-09-13-daily-swap-round7-qc.md`，探针同分支 `scripts/review_daily_swap_round7.py`）。
六轮审查报告：`docs/qc-daily-swap-7c89ca81` 分支 @ e15379f5（`docs/handoffs/2026-09-13-daily-swap-round6-qc.md`）——**不在本分支树上，别按裸路径找**。
本刀背景/收据/被否方案展开：`docs/handoffs/2026-09-13-daily-swap-round7-fixes.md`；威胁模型单一口径在 `market_feature_store/db.py` 顶部。

## 已验证（2d16a7f7，干净树，.venv-workbench/bin/python）

- 反向证伪：新回归测试对 dfb6ce87 旧代码真红（rc=0 而非 2）。
- 审查方原始探针 9/9 转绿（含原红项）；定向三文件 75 passed（71+4）。
- 全量 9,521 passed / 0 failed / 77 skipped / 1 xfailed，437s，exit 0（9,517+4 对账一致）；ruff check . 全过。

## 未验证 / 已知边界

- 既有库 assert_same_target→os.replace 末端窗口仍**不闭合**（POSIX 无按 inode 条件换名原语），只能说「静默覆盖→可检测拒绝」；裸字节直写（cp/dd 同 inode）仍看不见。
- 分类钉死只覆盖本轮首次观察**之后**的消失；观察前就被删的无从知晓。
- 整合候选（merge 进 631786ab 之后）门禁**未跑**，不得用本收据外推；hithink 数据端到端对账未做。
- 一般 clone IO 裸抛未修（另开提交）。

## 下一步

1. 八轮独立复审本刀（重点：钉死形态是否如建议、探针转绿、无回归）。
2. 用户裁定整体合并范围（本分支含整个 hithink 重建：15 文件 3723 插入）。
3. 组装干净整合候选、重跑适用门禁；合并与生产换库**分别授权**。

## 踩过的坑

- 在 QC 审查树里直接跑它的探针脚本会 import 到 QC 树旧代码（该树 conftest 把自己 prepend 进 sys.path），探针假红。复跑：拷进施工树再跑。
- 全量前看有没有别的树在跑。

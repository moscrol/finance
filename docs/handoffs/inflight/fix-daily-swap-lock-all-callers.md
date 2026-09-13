# daily-swap 换库契约：八轮复审通过行为修补，待用户裁定合并范围

## 这个分支做什么

公共 staging 编排的换库契约加固（叠在 hithink 重建 601db6dd 上）。**生产库未动、未合并。**

## 决策与被否方案

- 七轮 P2：existing/absent 分类**钉死在本轮首次观察**（探针前那次 exists）；否了「发布前再加 stat」与「探针返回值下传」。已见旧库后消失只剩 rc=2：探针窗口内→SwapTargetReplacedError（单独措辞）；之后→hold_swap_lock 开锁失败。
- 一般 clone IO 裸抛（cp/copy2 EPERM/ENOSPC 逃出编排）：审查裁定另开小提交，**不夹带**；错误出口旧债不是数据覆盖。
- 删掉「三文件零漂移→门禁可外推」断言：收据只对被测快照成立。

## 当前状态

`c20abf7d`（交接）/ `2d16a7f7`（代码）。**八轮复审：行为修补通过、无新数据覆盖路径；不签发「全量全绿」「可直接合并」。** 等用户裁定是否组装含 hithink 重建的整合候选。
八轮审查分支 `docs/qc-daily-swap-c20abf7d`；七轮报告 `docs/qc-daily-swap-dfb6ce87` @ e8ad314b；六轮报告 `docs/qc-daily-swap-7c89ca81` @ e15379f5（不在本分支树上）。
背景：`docs/handoffs/2026-09-13-daily-swap-round7-fixes.md`；威胁模型单一口径在 `db.py` 顶部。

## 已验证（八轮独立复审 + 本侧核验）

- 七轮 9 探针 + 八轮新增边界矩阵 10 条全绿；定向三文件 75 passed；ruff 全过。
- 反向证伪：新回归对 dfb6ce87 真红（旧代码会启动子进程，非假绿）。
- **干净 c20abf7d 全量：9,518 passed / 1 failed / 79 skipped / 1 xfailed**（收据 `20260913T104506Z-c20abf7d.json`）。唯一红 `test_installed_codex_sandbox_denies_network_and_unix_socket`：父提交同红（非本刀引入）、单独复跑绿——已知抖动，保留 baseline exception，不伪装全绿。
- 口径更正：先跑后提交那轮 9,521/0f 是 dfb6ce87+脏树收据（JSON dirty=true），非干净提交收据。

## 未验证 / 已知边界

- 既有库 assert_same_target→os.replace 末端窗口仍**不闭合**（无 POSIX 原语）；裸字节直写（cp/dd 同 inode）看不见。
- 分类钉死只覆盖本轮首次观察**之后**的消失。
- 整合候选（merge 进最新 main 后）门禁**未跑**；hithink 数据端到端对账未做。
- 一般 clone IO 裸抛未修（另开提交）。

## 下一步

1. 用户裁定整体合并范围（本分支含整个 hithink 重建：15 文件 3723 插入）。
2. 组装干净整合候选、重跑适用门禁（codex sandbox 抖动按 baseline exception）。
3. 合并与生产换库**分别授权**。

## 踩过的坑

- 在 QC 树里直接跑探针脚本会 import 到 QC 树旧代码（conftest prepend sys.path）导致假红；复跑须拷进施工树。
- 收据 JSON 绑定 revision+dirty 位：先跑后提交得到的是旧 revision+脏树收据，要「干净提交收据」就先提交再跑。
- 全量前看有没有别的树在跑。

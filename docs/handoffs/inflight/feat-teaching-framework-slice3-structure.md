# feat/teaching-framework-slice3-structure

树 `/Users/a77/fwp-wt-teaching-slice3`，PR #672，**待用户确认合并**。
8 个提交 + 1 个前向合并，17 文件 / +1527。

## 做了什么

授课框架 slice 3「结构视角」：上证日线 MACD 背离与缠论分型 / 笔 / 中枢 / 三买，
逐日只写出、事件记在**确认日**（不回填到发生日，避免未来函数）。往后依次是
DIF 背离正式口径（观察 / 确认 / 失效）进证据候选、板块与个股层事件表 + `structure-screen`、
左底向上拆 fine「触碰周均」（周均线上方未放量）+ `stage_fine_exits` 读数、
三个广度维度进靶子（16→19）并进证据（`BAND_VIEWS` + 重校准）。
另有两份文档：同花顺官方 API 对照评估 + 实测（涨停池 6 年 / 板块日 K 约 3 年 /
个股 10 年 1027 万行与我们收盘逐只一致）——那两份是 #678 与工单 #41 的由来。

**新靶子基线 0.2078 / 0.2111 / 0.2419**（`docs/learning/teaching-framework/00-concept-label-skeleton.md:345`）。
旧 16 项靶子 0.1490→0.1608，两半都升。
候选维度按 η² 单列不进靶子：20 日新高家数 0.46 / 个股周均线上方占比 0.37 / 20 日新低 0.27；
**背离广度不认阶段**（单列，未进靶子）。

## 本轮（接手方）做的

原分支落后 `gitea/main` 42 个提交，`check_test_receipt.py --base-drift-max 5` 会判
「分支尖收据不得冒充批次门禁」。**用前向合并而非 rebase**——`~/.claude/hooks/block-dangerous-git.sh:45`
拦 `--force/--force-with-lease`，rebase 完推不上去；前向合并让
`merge-base(HEAD, gitea/main) == gitea/main`，漂移同样归零。

- 合并 `gitea/main@f90af450` → `1fa963b2`，**零冲突**
- ruff 全绿
- 全量 **8312 passed / 0 failed / 77 skipped / 1 xfailed**（330.94s）
  收据 `~/.finance-runtime/test-receipts/20260908T165001Z-1fa963b2.json`，`dirty=false`
- 基座漂移手算 **0**（merge-base == gitea/main == f90af450）
- 已 push gitea

⚠ 别用 `check_test_receipt.py` 不带参数读 `latest.json` 验本单——当晚至少 3 棵树
在并发跑 pytest，`latest.json` 被 `fwp-wt-historical-discovery` 的脏树收据覆盖过。
**按 revision 取时间戳文件**，别信 `latest.json`。

## 未做 / 风险

- 未合 main（等用户确认）。webapp 与 `skills.registry.json` 本分支没碰，前端 / registry 叶子不受影响。
- **与 `data-source/hithink-ingest` 有重叠面**：那棵树（未提交）也在改
  `scripts/teaching_framework.py` 与 teaching_framework 系测试。谁后合谁解冲突。

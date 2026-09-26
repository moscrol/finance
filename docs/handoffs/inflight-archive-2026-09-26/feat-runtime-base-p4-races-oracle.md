# feat/runtime-base-p4-races-oracle

## 这个分支做什么
运行底座 P4（工单 #31，母单 §6.5）：`step()` 单步驱动 + 竞态目录 8 条 × 两序（INV-R6）+ 写序 oracle 公共件 + `docs/runtime/defensive-patterns.md`（G10）+ pre-commit 第 12 道目录保鲜。基线 `f90af450`。顺带收 P3 遗留：`restore.pending_inbox`、`finish.store_failures`。

## 决策与被否方案
- **`step()` = 生成器**：`run()` 搬进 `_drive()`，五个效果边界 `yield StepPoint`，`run()` 排空；`manual_drive()` 回一次性 `EpisodeDrive`。否：状态机重写（等于重写控制流）；线程 + 屏障（不确定）；pi 式调度器（量纲不对）。
- 步点只放「无在飞外部效果、局部变量稳定」处；错误分支与修复轮不设步点。
- 竞态⑦「store 失败」不改契约，只补收据 `finish.store_failures`。否：让失败拥有执行——与 INV-R2 既有决定相反。
- 竞态⑧由 P2「restore 只给计划不写」构造保证，本单钉成测试。
- `pending_inbox` 只列不认领；INV-R6 在非 continuous 臂 `UNSUPPORTED_DECLARED`。

## 当前状态
**PR #684 已开**，等用户确认合入。树干净；`conflict-check` 对 `gitea/main` clean，与 #682（沙箱）`merge-tree` 无冲突。

## 已验证
- 干净树全量 8324P / 0F（收据 `…T172234Z-9ea57acc` = 本次文档提交的父，其后只有文档提交）。复跑曾 8323/1——`test_real_conversation_round_trip…` 10 s 墙钟超时，同时段另两棵树在跑测试，隔离重跑 2/2 绿，不在本单改动面。
- conformance + 防御模式文档 106 passed（races 21）；pre-commit 12 道全过；ruff 0；目录保鲜一致。
- 变异：去模型结算后取消检查 → 竞态① A 序红；去 `finish.store_failures` → 竞态⑦两序红；`restore` 忘 pending_inbox → 夹具红。

## 未验证 · 已知边界
- 竞态② A 序里工具执行中翻取消，结算落 `tool_result`——夹具接受 `tool_result | tool_error`，只钉「无孤儿意图」。
- `EpisodeDrive` 一次性；生成器抛过异常不能再 `step()`。
- 未做：`wakeup` 仍只记账；参考 loop 无步点；无自动后台恢复；未切 8792（等母单 §7 五步规程，需用户在场）。

## 下一步
- 用户确认后合入 #684；与 #682 谁后合谁前向合并一次即可（沙箱只碰 `_with_episode_bound_tools` 与 import 行，本单只碰 `run()` 头部、步点与 `add("finish")`）。
- 8792 切流 + 手工 `kill -9` 演练（母单 §7），可用 `manual_drive` 停在 `model_pending` 模拟崩溃现场。

## 踩过的坑
- 变异后 `cp` 还原同大小同秒 → 沿用变异版 `.pyc`；`rm __pycache__/<模块>*.pyc && touch`。
- 写序 oracle 要求假 model / 假 tool 调 `effect_started`，否则 `assert_sandwich` 报「模型效果 0 次」——是替身没接线，不是写序坏了。
- `EpisodeEvent.payload` 把 list 冻成 tuple：断言用 `list(payload[...])`。

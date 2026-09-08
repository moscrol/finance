# feat/runtime-base-p4-races-oracle

## 这个分支做什么
运行底座 P4（工单 #31，母单 §6.5）：`step()` 单步驱动 + 竞态目录 8 条 × 两序（INV-R6）+ 写序 oracle 公共件 + `docs/runtime/defensive-patterns.md`（G10）+ pre-commit 第 12 道目录保鲜。基线 `f90af450`（P0–P3 已合）。顺带收 P3 遗留：`restore.pending_inbox`、`finish.store_failures`。

## 决策与被否方案
- **`step()` = 生成器**：`run()` 整段搬进 `_drive()`，五个效果边界 `yield StepPoint`，`run()` 排空；`manual_drive()` 回一次性 `EpisodeDrive`。否：状态机重写（几十个局部变量、十来个 return，等于重写控制流再靠测试证明没变）；线程 + 屏障（不确定、慢、与「add 都在主线程」相悖）；pi 式确定性调度器（量纲不对）。
- 步点只放「无在飞外部效果、局部变量稳定」处；错误分支（`model_error` 后的 return/continue）与修复轮 `_repair_model_complete` 不设步点。
- 竞态⑦「store 失败」不改契约（失败不拥有执行、失败后停写），只补收据：`store_failures` 落 `finish` payload（store 已写不进，收据只能在内存 / 产物侧）。否：让失败拥有执行（fail-closed 杀 episode）——与 INV-R2 测试既有决定相反。
- 竞态⑧「restore vs 在飞」由 P2「restore 只给计划不写」的构造保证，本单把它钉成测试（resumable / already_terminal 两处置零写入；`closed` 处置本来就合成落盘，不在竞态里）。
- `pending_inbox` 只列不认领：认领是 loop 的事，恢复读事实。
- INV-R6 在非 continuous 臂声明 `UNSUPPORTED_DECLARED`（没有步点没有 store，两序无从构造）。

## 当前状态
代码 + 测试 + 文档全落在本分支；`gen_runtime_catalog --check` 一致（无新 kind）；pre-commit 新 hook 实测通过。等用户确认合入。

## 已验证
- `conformance/` 103 passed（含 races 21 条：16 两序 + 1 pending_inbox + 4 目录互锁）；runtime 邻域 228 passed；`test_defensive_patterns_doc.py` 3 条。
- 生成器重构对既有断言零改动：`test_agent_episode` / `test_episode_messages` / `test_episode_restore` / `test_episode_inbox` / `test_tool_stage_events` 全绿，严格派生全程开。
- 变异：去掉模型结算后的取消检查 → 竞态① A 序红（工具被派发）；去掉 `finish.store_failures` → 竞态⑦两序红；`restore` 忘 pending_inbox → 对应夹具红。
- 全量门禁读数见 PR 正文（本干净树）。

## 未验证 · 已知边界
- 竞态②A 序里工具执行中翻取消，结算落的是 `tool_result`（runner 已返回）——夹具接受 `tool_result | tool_error` 任一，只钉「无孤儿意图」。
- `EpisodeDrive` 一次性：生成器抛过异常不能再 `step()`；`run()` 的调用方语义不变（异常照常从 `next()` 抛出）。
- 未做：`wakeup` 仍只记账；参考 loop 无步点；不做自动后台恢复；未切 8792（P2 起的行为改动仍等母单 §7 五步规程，需用户在场）。

## 下一步
- 用户确认后合入；与 #682（沙箱）无文件冲突（沙箱只碰 `agent_episode._with_episode_bound_tools` 与 import 行，本单只碰 `run()` 头部、步点与 `add("finish")`）——谁后合谁前向合并一次即可。
- 8792 切流 + 手工 `kill -9` 演练（母单 §7），演练时可用 `manual_drive` 停在 `model_pending` 模拟崩溃现场。

## 踩过的坑
- 变异后用 `cp` 还原：同大小同秒 mtime → 沿用变异版 `.pyc`；还原后 `rm __pycache__/<模块>*.pyc && touch`。
- 写序 oracle 要求假 model / 假 tool 调 `effect_started`：把 oracle 当 store 传进去而替身不报「效果开始」，`assert_sandwich` 会报「模型效果 0 次 vs model_intent 2 条」——那是替身没接线，不是写序坏了。
- `EpisodeEvent.payload` 会把 list 冻成 tuple：断言用 `list(payload[...]) == [...]`。

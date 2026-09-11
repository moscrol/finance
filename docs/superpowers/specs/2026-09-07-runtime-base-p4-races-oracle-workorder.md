# 工单 #31 · 运行底座 P4：竞态目录 + 写序 oracle 正式化 + 防御模式

> 母单：#27 `2026-09-07-runtime-base-endstate-design.md` §6.5。前置：P2（#29）合入（`step()` 可单步驱动与 store 是竞态测试的地基）；P3 可并行。
> 分支：`feat/runtime-base-p4-races-oracle`（基线 `f90af450`，P0–P3 已合）。状态：✅ 代码已落、门禁绿、PR 待用户确认（2026-09-08）。
> 判据：INV-R6 成立；G10 抛 / 返回总规则落文档并有夹具。

## 范围（原文）与落点

1. loop 拆出 `step()` 单步驱动（manual drive）；`intelligence/tests/conformance/races/` 目录表 v1 ≥ 8 条，每条两序、两种合法历史都断言：`cancel vs model_turn 结算`、`cancel vs tool_result 结算`、`cancel vs finish`、`steer vs 模型停下`、`close vs 结算`、`两个 begin_work 同 Handle`、`store.append 失败 vs 内存 ledger`、`restore vs 仍在飞的驱动`。
   - **落点**：`ContinuousAgentEpisode.manual_drive()` → `EpisodeDrive`（`step()` / `run_until(phase)` / `run_to_end()`）；`run()` 现在就是把 `_drive()` 生成器排空。五个步点 `STEP_PHASES`：`model_pending`（意图已 durable、结算未发）/ `model_settled` / `before_tool_dispatch` / `tools_settled` / `before_finish`。`races/catalog.py` 8 行 × 两序 × 两种合法历史，`test_race_*.py` 八个文件 16 条两序夹具 + 1 条 pending_inbox + `test_catalog.py` 4 条互锁。
2. 写序 oracle 从 P2 测试工具升为 `conformance/oracle.py` 公共件。
   - **落点**：文首写清三处复用与用法；`test_inv_r3_restore` 的不间断录制改用 oracle 并 `assert_sandwich()`；八条竞态每序结束都断三明治。
3. `docs/runtime/defensive-patterns.md`：坑 → 规则，含 G10 总规则。
   - **落点**：14 条「坑 → 规则 → 出处」，出处是台账 `R-*` 编号或交接文件；`test_defensive_patterns_doc.py` 钉 G10 原句 + 引用的 R 编号在台账里存在 + 生成器不管这份手写文档。
4. `test_runtime_catalog_fresh` 进 pre-commit（第 12 道）。
   - **落点**：`.pre-commit-config.yaml` 新 hook `runtime-catalog-fresh`（`gen_runtime_catalog.py --check`，改到 `intelligence/**/*.py` / 三张目录 / 生成器时跑）。

## 设计决定：生成器而不是状态机重写

`run()` 有几十个局部变量与十来个 return 点。改成显式状态对象 + `step()` 分派等于重写一遍控制流，再靠测试证明它没变。生成器让**同一份代码**在效果边界 `yield` 暂停，局部变量原地保留：事件序、写序、消息序逐字节不变——全量套件在严格派生（INV-R1）下跑一遍就是证明。代价：驱动器一次性（生成器抛过异常不能再 `step()`），修复轮 `_repair_model_complete` 是独立方法不设步点。否掉的：线程 + 屏障（不确定、慢、与「今天所有 add 都在主线程」的前提相悖）；pi 式确定性调度器（要先把 loop 改成可调度的任务，量纲不对）。

## 顺带收的 P3 遗留

- `restore()` 结果新增 `pending_inbox`（入箱未认领未丢弃的 message_id，只列不认领；`to_dict` 带出）。
- `wakeup` 仍只记账：同步 loop 没有可唤醒的空闲态，`step()` 是手动驱动不是调度器，这条不在本单收。
- `store_failures` 写了没人读（INV-R2 那条测试只断 `attempts == 1`）——现在落进 `finish.store_failures`，竞态⑦两序钉住。

## 验收

- 每条竞态两序各一夹具且断言不同的合法终态 ✅（`races/test_race_*.py`，`test_catalog.py` 互锁）。
- oracle 在 P2 的 Tier A 套件里复用 ✅（`test_inv_r3_restore` 录制走 oracle）。
- 防御模式文档每条带本仓实例 ✅（14 条，无 dsh 抄件）。
- 变异：去掉模型结算后的取消检查 → 竞态① A 序红；去掉 `finish.store_failures` → 竞态⑦两序红；`restore` 忘记 pending_inbox → 对应夹具红。
- 门禁读数见 PR 正文与交接。

## 不做

不引入并发框架；不做 SQLite；不为竞态测试改生产控制流（只在效果边界加 `yield`，不改任何 `ledger.add` / `model.complete` / `_dispatch` 的相对顺序）；不做自动后台恢复（`restore` 仍只给计划）；参考 loop `HarnessReferenceLoop` 不加步点（没有 store、不是竞态目录的适用臂）。

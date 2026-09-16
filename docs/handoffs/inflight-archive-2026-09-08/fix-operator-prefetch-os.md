# fix/operator-prefetch-os

## 这个分支做什么

Operator Prefetch OS **P0 已完成**：空 `manual` 不再盖掉已识别的 `history_analog` 信封；D10 取数按 `as_of` 截断；Engine A 开场预取在算子命中时必须给 D10 块或显式 gap。

设计与计划已随本分支提交：
- `docs/superpowers/specs/2026-08-23-operator-prefetch-os-design.md`（rev2）
- `docs/superpowers/plans/2026-08-23-operator-prefetch-os.md`

## 三刀分别改了什么

1. **`turn_controller.py:313`**（单行）：`if selected_skill_ids or skill_mode == "manual":` → `if selected_skill_ids:`。
   空 manual 是「别自动点菜」，不是「我点了普通套餐」。旧条件让细粒度快车道
   （`comparison_analog` → D10）成为死代码，且**连取值题也一起盖住**
   （实测：空 manual + 「宁德时代今天收盘多少」曾返回 `stock_deep_dive`）。
2. **`market_regime_analogs.py`**：`load_market_regime_vectors` 加 `as_of`，base 查询加
   `where trade_date <= ?`；`load_market_regime_artifact` / `regime_block_for_llm` 透传。
   默认 `as_of=None` 与旧行为逐字节等价，Engine B 未受影响。
3. **`asof_prefetch.py`**：新增 `_history_analog_items`；`collect_prefetch_items` 只替换 6 行锚点
   （算子供数前置、`con is None` 时返回已收集的 gap 而非 `()`）。regime → D10 或 gap；
   题材类比 → D8 gap；`parse_stock_analog_intent` → D11 gap。

## 为什么截断必须在取数层（别在渲染层裁）

泄漏有四处，三处发生在渲染之前：「当前窗口」取的是**库尾**、z 标准化系数用**全历史**算、
候选窗口的后续 5/10/20 日会**跨过截止日**。渲染层只能删掉表格里超期的行，前三处早已把
未来信息**揉进数值**——每个 z 值都被未来数据缩放过。下游四个环节全都只消费
`load_market_regime_vectors` 的返回值，所以截在那一处，四处一起干净。

## 验收记录（2026-08-23，独立复核，非执行方自报）

| 检查 | 结果 |
|---|---|
| 文件边界 | 恰好 6 个，与 plan 文件地图逐一对上 |
| 锚点未越界 | `asof_prefetch.py` 只有 3 个 hunk；`market_forecast` 段与发酵段未出现在 diff |
| 就范检测 | `or skill_mode == "manual"` 未恢复；`quick_fact` 断言原样；测试文件零删除行 |
| **反向证伪** | 把 `if as_of is not None:` 改成 `if False:`（「传到了但没人读」形状）→ **5 条测试变红**，已完全还原 |
| ruff | 六文件全过 |
| 全量 pytest | `51200e8e` 上 **6119 passed / 13 skipped / 0 failed**（4m57s） |

**验收方的基线跑废过一次**：后台那次「改动前全量」与施工撞车，收据显示实际跑在
`a06b448a` 且新测试文件已 dirty。该数不作基线用。因交付后为 **0 failed**，
「不比 main 多红」自动成立，无需对账。

## 收尾修的一处（缺陷源于 plan，非执行方）

`from intelligence.tests.test_market_regime_analogs import LoaderAndBlockTests, _day`
会把该 unittest 类带进本模块命名空间，pytest 当本文件测试**再收一遍**
（实测 6 → 14 条，同名用例挂两个文件下）。改成模块别名 `_mra.` 引用，收集数回到 6。
**可迁移**：任何测试文件跨文件复用 unittest 夹具，都用模块别名，不要 `from ... import 类`。

## 未验证 / 已知边界

- P0 只保证 **Engine A 预取路径**的 D10 无穿越。**Engine B（`ask.py:3986`）与
  `stock_analogs` 仍未截断**（spec §4 事实 12/14、§9 P1 4–5）。
  对外**不得**表述成「D10 已全面按截止日取数」。
- 从未 live。spec §11 要求：切流前用冻结题在干净 sidecar 重放一次，对照
  `trace-diff-spt-fengyuan-history-20260823` 的 `question_type` 与预取；**不重跑三臂评分**。
- 8792/8796 **不是解耦对照臂**（spec §4 事实 11：同 revision `1c52e19f`、同依赖指纹，
  只差 `FORESIGHT_USERS_DIR` 与端口，解耦差量为零）。要做解耦 A/B 得用开关板 runner
  （`2026-08-22-capability-switchboard-design.md`），不能用两个端口冒充。
- `R-20260823-SPTTECH-03`（发布层投影后仍 complete）已 refuted、`-04`（n≥10 非法首动作归因）
  仍 pending，两者与本单**无共同因果**，另立项。

## 下一步

1. 合入 `main`（用户已确认）。
2. 切流前按 spec §11 重放冻结题一次。
3. P1：类比做法 skill、发布层减法、Engine B / D11 的 as_of 截断。

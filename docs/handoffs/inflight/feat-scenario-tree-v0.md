# 在途交接 · feat/scenario-tree-v0（工单 #37 / G-15）

## 这个分支做什么
情景树 v0：节点是观察剧本，边是注册标签上的确定性条件（v0 只收单日切片可判的四个标签），`otherwise` 强制、兄弟互斥在取值域上机械判；登记要 `projection_hash / model_id / framework_version`，同时进 `checkpoints`（新 `object_type=scenario_tree`）；`resolve` 只读 `slice(T+k, C=T+k)`，缺原料停住；到达节点剧本按 G-03 登记（带当日投影哈希）；三项回检；每日复盘钩子默认关。**叠在 #667（#34）+ #670（#35）之上**，两者先合。收据 `docs/verification/2026-09-08-scenario-tree-v0.md`。

## 决策与被否方案
- 新模块 `scenario_trees.py`（复数）/ 否 改旧 `scenario_tree.py`——那是问答路由的推演契约产物，同名不同物。
- 条件白名单只收 `river_derive.SLICE_EVALUABLE_LABELS` / 否 全部 `ALL_LABELS`——需要历史的标签（`dual_red_streak / ma5_*`）单日切片判不了，T+k 就判不出走了哪条边。
- 互斥用取值域枚举（bool / 提到的值 ∪ 其它 / 0..200）/ 否 只检查同标签同 op——不同标签的兄弟（`market_stage` vs `volume_surge`）可同真，必须拒。
- `unresolvable` 终态 / 否 跳过缺数日继续（§3.3 硬门 3：不猜、不跳）。
- 规则样本存在 step 记录里 / 否 新台账（§9 不新增存储；G-16 提议器消费时再定）。
- 修 #35 的 `market_stage` 绑定归一而不是在树里 strip 后缀——真源一处（G-05 的 `normalize_market_stage`）。

## 当前状态
17 新测试；真库冒烟：半导体深度 2 树 09-02 命中「底部横盘」分枝（`cp:d3060355a71d5da9`，换用户重跑同哈希），09-03 因该板块无行 `unresolvable` 停住。**干净树全量门禁见收据（合入前补跑，且要在 #667 / #670 合入后 rebase 一次）。**

## 未验证 / 已知边界
- 绑定 vs 旁路库 30 抽 oracle 未单独跑（同源，合入后核）。
- `limit_heat_rank` 绑定未钉档位（`HEAT_TIER`）。
- Workbench 端点 / OR / 深度 > 3 / `analog_ref` 全部 v1。

## 下一步
- #667、#670 合入 → 本分支前向合并 main → 全量门禁 → 合入。
- 合入后：路线图 G-15 回写「v0 已落（#37）」、09-06 spec §10 第 13、14 条与 §11 第 13 条标实测；台账地图登记 `scenario_trees.jsonl`；UBIQ 补 `realized_path / otherwise / unresolvable` 三字段词（放 #666 分支）。

## 踩过的坑
- 切片里的 `market_stage` 是供应商原值带「阶段」后缀，第一遍真库冒烟条件永远走 otherwise——注册标签的绑定必须走 G-05 归一函数，不能拿原值比。
- 板块宇宙不是每个交易日都有每个板块的行（990122.FP 09-03 / 09-04 无行）：树在那天 `unresolvable` 是对的，别当 bug 修。

# 在途交接 · feat/scenario-tree-v0（工单 #37 / G-15）

## 这个分支做什么
情景树 v0：节点是观察剧本，边是注册标签上的确定性条件（v0 只收单日切片可判的四个标签），`otherwise` 强制、兄弟互斥在取值域上机械判；登记要 `projection_hash / model_id / framework_version`，同时进 `checkpoints`（新 `object_type=scenario_tree`）；`resolve` 只读 `slice(T+k, C=T+k)`，缺原料停住；到达节点剧本按 G-03 登记（带当日投影哈希）；三项回检；每日复盘钩子默认关（`FORESIGHT_SCENARIO_TREE_RESOLVE=1` 才跑）。收据 `docs/verification/2026-09-08-scenario-tree-v0.md`。PR **#674**。

## 09-11 对齐（用户拍板「接续现有分支，按最新主干重新验证」）
- 前提 #667（投影）/ #670（区间）已由用户合入 main → 本分支已前向合并 `gitea/main@5907c9f6`（merge 提交 `326eeb58`，含 #671 舆论阶段 / #680 补强 spec / #681 晋升认证 / #734 Knevo）。
- 唯一代码冲突 `checkpoints.py OBJECT_TYPES`：分支加 `scenario_tree`、main 加 `method_observation`（任务包 07）——取并集，五类对象，两类各自单列不进用户判断分母（G-09 分列）。
- 台账地图已补 `scenario_trees.jsonl` 行（AGENTS「新增台账先登记」补欠账；无独立 CLI，入口 = `scenario_trees.register / resolve` + 默认关的 `daily_review_hook`）。
- 对齐后定向 168 passed（scenario + checkpoint 全集）；独占全量 **9344P / 1F**——那 1 红 `test_real_conversation_round_trip…` 是已知 10s 墙钟超时型 flaky（P4 交接 #684 同测试同形状先例；本次隔离复跑 3/3 绿：单测试 / 最小组合 / 整文件 6P；含同一主干的 #597/#735/#736 三棵树全量 9337–9363 全绿），不在本分支改动面。

## 决策与被否方案（原有，仍成立）
- 新模块 `scenario_trees.py`（复数）/ 否改旧 `scenario_tree.py`——那是问答路由的推演契约产物，同名不同物。
- 条件白名单只收 `river_derive.SLICE_EVALUABLE_LABELS` / 否全部 `ALL_LABELS`——需要历史的标签单日切片判不了。
- 互斥用取值域枚举 / 否同标签同 op 检查——不同标签的兄弟可同真，必须拒。
- `unresolvable` 终态 / 否跳过缺数日（§3.3 硬门 3：不猜、不跳）。
- 规则样本存在 step 记录里 / 否新台账（§9 不新增存储；G-16 提议器消费时再定）。

## 未验证 / 已知边界
- 绑定 vs 旁路库 30 抽 oracle 未单独跑（同源，合入后核）。
- `limit_heat_rank` 绑定未钉档位（`HEAT_TIER`）。
- Workbench 端点 / OR / 深度 > 3 / `analog_ref` 全部 v1——用户 09-11 已点名「产品接线」是后续第 5 组工作（工作台确认 / 修改 / 跳过 → 登记 → 到期回检闭环）。

## 下一步
1. 全量读数回写 PR #674 → 用户确认合并。
2. 合入后：路线图 G-15 回写「v0 已落（#37）」、09-06 spec §10 第 13、14 条与 §11 第 13 条标实测；UBIQ 补 `realized_path / otherwise / unresolvable` 词条（放 #666 分支）。
3. 产品接线（Workbench 端点 + 每日钩子开关决策 + `analog_ref` 接相似窗口）随第 5 组推进。

## 踩过的坑（原有）
- 切片里的 `market_stage` 是供应商原值带「阶段」后缀——注册标签绑定必须走 G-05 归一函数。
- 板块宇宙不是每天都有每个板块的行：那天 `unresolvable` 是对的，别当 bug 修。

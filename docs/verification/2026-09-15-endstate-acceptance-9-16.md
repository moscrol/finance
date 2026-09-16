# 09-06 终局 spec「最小验收集」第 9–16 条对账（2026-09-15）

> 范围：`2026-09-06-personal-research-calibration-endstate-design.md` §10 最小验收集的第二轮新增八条。
> 第 1–8 条的对账已在 gap roadmap 顶部（09-06 回写：7/8，唯一没过的第 3 条卡 G-01 创始人母本，是依赖不是欠债），本文不重复。
> 方法：每条找承载测试并跑绿（组内 218 passed，收据 `20260915T104405Z-c3770e0b`，干净树），测试缺的条目做行为实测补证并如实记缺口。基线 `gitea/main@1fef3d27`（本文与两条补测随 `feat/acceptance-9-16-tests` 独立成枝；与题材词表 G-04 无关，G-04 主体见 PR #673）。

| 条 | 内容 | 判定 | 证据 |
|---|---|---|---|
| 9 | `window` 幂等；任一天 `trade_date_only` 整段降档；`C < end` 拒绝 | ✅ 测试钉死 | `test_river_window_contract.py::test_idempotent_and_slices_match_slice_river` / `::test_any_trade_date_only_day_downgrades_window` / `::test_c_before_end_rejected_c_after_end_needs_hindsight` |
| 10 | 区间派生对象 `member_refs` 可解析回切片对象；所需轨缺天 → `unverifiable` 不是数字 | ✅ 测试钉死 | 同文件 `::test_member_refs_resolve_back_to_slice_objects` / `::test_streak_unverifiable_vs_break`（抽样 30 条的全量口径由测试构造覆盖，未另做真库 30 抽样） |
| 11 | 同 `(source, framework_version, task, budget)` 两次投影 hash 相同；源里每个 gap 都进投影 | ✅ 测试钉死 | `test_river_projection.py::test_same_input_same_hash_and_no_side_effects` / `::test_hash_covers_task_budget_framework_and_source_ref` / `::test_gaps_and_limits_present_and_before_facts` |
| 12 | 缺 `projection_hash` / `model_id` 的 agent 判断被台账拒收并给出错误码 | ✅ 实现 + 行为实测；⚠️ 直接负例单测未定位到 | `checkpoints.register_checkpoint` 硬门（`agent_judgment`/`scenario_tree` 缺任一即 `ValueError`，`observation_script` 无 hash 须显式 `user_authored=True` 记 `projection_hash_missing=user_authored`）；本轮行为实测拒收原文「object_type=agent_judgment 缺 projection_hash/model_id…台账拒收」。**缺口**：grep 全 tests 未命中直接负例（`test_scenario_trees.py::test_register_requires_attribution_and_writes_checkpoint` 覆盖情景树侧；`agent_judgment` 裸注册的负例建议补一条） |
| 13 | 未注册标签 / 概率数字 / 缺 `otherwise` / 子条件不互斥的情景树被拒绝 | ✅ 测试钉死 | `test_scenario_trees.py::test_unregistered_or_history_label_rejected` / `::test_no_otherwise_and_overlap_and_depth` / `::test_text_lint_rejects_strategy_direction_probability_stock` |
| 14 | T+k 所需标签 `gap` → `unresolvable`，`realized_path` 不延长 | ✅ 测试钉死 | `::test_missing_label_input_is_unresolvable_and_path_does_not_grow` |
| 15 | `anchor_windows` 锚点/目标未注册即拒绝；`knowledge_cutoff ≥ forward_end`；三段任一缺失整条 `unverifiable` | ✅ 拒绝路径实现 + 行为实测；⚠️ 无直接测试引用 | `river_anchor.py:123/163/165`（未注册 `ValueError`，`until_label` 与显式 `after` 互斥）；本轮行为实测拒绝原文「anchor_label='not_a_label' 不是注册标签（ALL_LABELS）」。**缺口**：`anchor_windows`/`find_anchor_days` 在 `intelligence/tests/` 零引用，仅经 `teaching_framework/leader_succession.py`（`test_teaching_framework_succession.py`）间接覆盖；`kc ≥ forward_end` 与「三段缺失整条 unverifiable」两个后半句本轮未逐条验，随直接单测一起补 |
| 16 | `index_stage`（授课）与 `market_stage`（供应商）两个标签两个版本号，同一天可不同且都被保留 | ✅ 测试钉死 | `test_teaching_framework_cli.py:194-195`：旁路库 `history_teaching_labels` 中 `src.market_stage` 与 `tf.stage_coarse` 并存、`tf.*` 命名空间禁止复制供应商标签；`supplier_disagree_days == 9`——不一致天数被保留成读数而非被抹平 |

## 结论

- 9–11、13、14、16 六条：承载测试在、本轮跑绿，可打勾。
- 12、15 两条：**实现与拒绝行为都在**（本轮行为实测），但各缺一条直接负例单测——12 缺 `agent_judgment` 裸注册负例，15 缺 `anchor_windows` 契约自身的测试（含 `kc ≥ forward_end`、三段 `unverifiable` 两个未验半句）。这是「合了但验收没钉死」型暗账：行为今天对，防回归的门没关上。
- 合并 1–8 的既有读数：16 条里 15 条可打勾（第 3 条等 G-01 创始人母本），2 条附测试缺口待补。

## 缺口处置（同日已补，随本分支一起交付）

上述 12/15 两条点名的缺口已补：`test_river_anchor_contract.py`（10 条——拒绝路径、硬规矩 2、open/unverifiable、事件到事件两态；变异硬规矩 2 的 raise 见红后还原，测试承重）与 `test_checkpoints.py::AttributionGateTests`（3 条负例）。不改实现，纯加测试。

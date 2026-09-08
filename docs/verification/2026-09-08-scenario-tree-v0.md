# 情景树 v0——工单 #37（G-15）验收收据

> 日期：2026-09-08 · 分支 `feat/scenario-tree-v0`（叠在 #667 `feat/river-context-projection` + #670 `feat/river-window-contract` 上：要 `projection_hash` 门禁与 `river_derive.bind` 标签绑定）· 基线 `gitea/main@8e452e72`
> 工单：`docs/superpowers/specs/2026-09-08-scenario-tree-object-workorder.md`（PR #666 分支）；契约 09-06 spec §3.3 / §4.2 / §5.4 / §10 第 13、14 条 / §11 第 13 条

## 改了什么

| 文件 | 内容 |
|---|---|
| `intelligence/services/scenario_trees.py`（新，复数；旧 `scenario_tree.py` 一行不动） | 对象 `ScenarioTree / Node / Predicate`（形状照 §3.3）；`compile_condition`：`{"all":[谓词]}` \| `"otherwise"`，label 必须 ∈ `LABEL_KINDS`（注册标签）**且** ∈ `river_derive.SLICE_EVALUABLE_LABELS`（单日切片可判：`dual_red_strict / volume_surge / market_stage / limit_heat_rank`），op 按 `OPS_BY_KIND`；`make()` 结构校验（恰一根、depth 链、`max_depth ≤ 3`、`step_kind ∈ T+1/T+3/T+5`）+ 互斥穷尽（`siblings_overlap` 在取值域上枚举：bool 两值 / text 提到的值 ∪ 其它 / num 0..200）+ 恰一个 `otherwise` + `analog_ref` v0 必空 + 节点剧本过 `observation_script.validate` + 全部自由文本过 `compliance_gate`（策略词 / 方向 / 时点 / 概率 / 个股）；`register()` 缺 `projection_hash / model_id / framework_version` 拒收，同时在 `checkpoints.jsonl` 落一条 `object_type=scenario_tree`；`resolve()` 只读 `slice(as_of, C=as_of)`（C ≠ as_of 拒绝、不许倒退），缺原料 → `unresolvable` 停住，命中 → 到达节点剧本按 G-03 口径登记（带当日投影哈希），`sample{condition → next_facts_refs}` 存在 step 记录里；`current_state()` 折 append-only 台账；`recheck()` 三项（覆盖 / 沿路剧本 / 规则样本），< 10 棵树不出率；`daily_review_hook()` 默认关 |
| `intelligence/services/checkpoints.py` | `OBJECT_TYPES` 加 `scenario_tree`（`OBJECT_TYPE_CN` 情景树）；归因门禁扩到 `scenario_tree`（缺哈希 / 模型号拒收） |
| `intelligence/cli.py` | 每日复盘在带读之后调 `daily_review_hook`：`FORESIGHT_SCENARIO_TREE_RESOLVE` 未开时返回同一个对象 |
| `scripts/scenario_tree.py`（新） | `draft / register / resolve [--all] / show / recheck` |
| `intelligence/services/river_derive.py`（#35 分支上修） | `market_stage` 绑定走 G-05 `normalize_market_stage`——本单真库冒烟量出：切片里是「底部横盘阶段」，条件写「底部横盘」永远不命中 |
| 测试 | `intelligence/tests/test_scenario_trees.py` 17 条 |

## 验收逐条（工单 §3）

| # | 判据 | 结果 |
|---|---|---|
| 1 | 非白名单标签整棵树拒绝并点名 | ✅ `test_unregistered_or_history_label_rejected`（`not_a_label` → `E_CONDITION_INVALID`；`dual_red_streak` → `E_LABEL_NOT_SLICE_EVALUABLE`） |
| 2 | 缺 `otherwise` / 兄弟可同真 / `max_depth=4` | ✅ `test_no_otherwise_and_overlap_and_depth`；数值区间不相交放行、相交拒绝 `test_numeric_siblings_disjoint_by_interval_is_accepted` |
| 3 | 文本 lint：策略 / 方向 / 概率 / 个股 / 目标价 | ✅ `test_text_lint_rejects_strategy_direction_probability_stock`（复用 `compliance_gate` 既有码） |
| 4 | 缺 `projection_hash / model_id / framework_version` 拒收；`checkpoints.jsonl` 出现 `scenario_tree` | ✅ `test_register_requires_attribution_and_writes_checkpoint` |
| 5 | `resolve` 三情形 | ✅ 恰一子真 → 路径延长 + `evidence_refs` 非空 + 到达剧本登记（带当日哈希）；缺原料 → `unresolvable` 且不延长、不登记；`otherwise` 命中 |
| 6 | 切片 `knowledge_cutoff == as_of` 强制 | ✅ `test_cutoff_must_equal_as_of`；`test_exactly_one_child_true…` 断言传参 |
| 7 | 绑定与旁路库 30 抽一致 | ⚠️ 未单独做——`bind()` 是 #35 的公共件（`dual_red_strict` 阈值 import 自 `labels.py`，`market_stage` 走 G-05 归一函数，与旁路库 v3 同源）。留给合入后一次性核（见「未做」） |
| 8 | 钩子关着逐字节不变 | ✅ `test_hook_off_returns_same_object`（`is` 等价，且关着时 `load` 被调用即失败）、`test_hook_on_without_trees_is_still_identity` |
| 9 | `recheck` < 10 棵不出率；样本在 step 记录里、无新台账文件 | ✅ `test_recheck_counts_and_withholds_rate_below_min_n` |
| 10 | 真库冒烟 | ✅ 深度 2 的「半导体」树（条件 `market_stage in [底部横盘]` / `market_stage in [反弹,主升] ∧ volume_surge` / otherwise；子层 `dual_red_strict` / otherwise）：`register` → `resolve 2026-09-02`：**root → a（命中，底部横盘）**，`projection=cp:d3060355a71d5da9`；`resolve 2026-09-03`：**a → unresolvable**（当天切片里该板块无 `fact_sector_daily` 行，`dual_red_strict` 缺原料——停住不猜）；换用户重跑 09-02 同一哈希。`checkpoints.jsonl` 两条：`scenario_tree`（树的哈希）+ `observation_script`（到达节点，当日投影哈希）。**修 G-05 归一前**第一遍 09-02 走的是 otherwise——这就是不归一的代价 |
| 11 | 旧 `scenario_tree.py` / `test_scenario_tree.py` 零改动 | ✅ `git diff --stat` 不含两者；`test_legacy_scenario_tree_artifact_still_importable` |
| 12 | 干净树全量门禁 | 见下 |

## 门禁

干净树 `~/fwp-wt-scenario-tree` @ `d04f25a1`（叠在 #667 `d563729a` + #670 `aa4472df` 上）、`.venv-workbench`、`env -u MARKET_FEATURE_STORE_DB`：ruff 0；pytest **8217P / 0F / 76S / 1xfail**（362s）；`check_test_receipt --expect-revision HEAD` 可采信。#667 / #670 合入 main 后本分支前向合并再跑一次。

## 未做 / 边界

- 绑定 vs 旁路库 30 抽一致性 oracle（工单 §3 第 7 条）未单独跑——`market_stage` 与 `dual_red_strict` 两个绑定已与旁路库同源（归一函数 / 阈值常量），`volume_surge` 走 `turning_points.VOLUME_SURGE_PCT`；合入后在验收 session 用 `history_labels.duckdb` 抽 30 格核一次。
- `limit_heat_rank` 绑定读的是切片里 `source_view=limit_heat` 的板块热度行；旁路库 `limit_heat_rank` 只取 `HEAT_TIER`（sector/all/final/非实时）一档——切片若混入其它档位会不一致，v0 未钉。
- `unresolvable` 是终态（§3.3 硬门 3）：09-03 那天该板块无行，树停住；产品面要不要允许「跳过缺数日继续」是 v1 的决定，不在这里改。
- `daily_review_hook` 只留默认关的钩子；Workbench 端点、OR 条件、深度 > 3、`analog_ref` 全部 v1。
- 兄弟互斥的判定是**枚举**（num 域 0..200）：`limit_heat_rank > 200` 一类条件在域外无法与其它条件区分，会被判「不相交」——名次超过 200 在 400 个板块里没有分枝意义，接受。

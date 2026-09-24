# 工单 #37：情景树对象 v0（多步推演；G-15）

> 日期：2026-09-08
> 上游：`2026-09-06-personal-research-calibration-endstate-design.md` **§3.3 情景树对象**（对象形状与三条硬门，照抄不改）、§4.2（判断轨归因字段）、§5.4 推演–回检飞轮、§10 最小验收集第 13、14 条、§11 第 13 条（条件可编译）；`2026-09-05-time-river-gap-roadmap.md` §2.5 G-15；`UBIQUITOUS_LANGUAGE.md`「情景树」条
> ⚠️ 上述章节 2026-09-06 写入、截至 09-08 从未提交；本工单所在分支 `docs/closeout-workorders-0908` 已带上
> 优先级：P1（V2 项；「推演」是用户口语里点名要的能力，产品语言一律翻译成情景树）
> 规模：中到大单（三到四天，三刀）
> 分支：`feat/scenario-tree-v0`
> 依赖：**#34 上下文投影（硬依赖：树必带 `projection_hash`，台账拒收没有的）**；G-03 观察剧本（已在 main）；G-05 `market_stage` 归一（已在 main，#661）。#35 区间契约**非硬依赖**——v0 的 `analog_ref` 一律留空，条件白名单只收「单日切片可判」的标签（见 §2.1），需要历史的标签等 #35 派生对象再放开（v1）
> 并行冲突：本单改 `checkpoints.py`（登记沿路剧本）、`compliance_gate.py`（不改词表，只加入口）；**排在 #34 合入之后开工**
> ⚠️ 命名冲突：main 上已有 `intelligence/services/scenario_tree.py`（`ScenarioTreeArtifact`，问答路由的推演契约产物）与 `test_scenario_tree.py`。**本单新模块叫 `intelligence/services/scenario_trees.py`（复数，与 09-06 §13 模块表 `scenario trees` 一致），不得改旧模块一行**

---

## 0. 一句话

观察剧本只推一步（T+1 看什么）。情景树把它接成多步：节点是观察剧本，边是**注册标签上的确定性条件**，`otherwise` 分枝强制存在；世界每过一个交易日，河的切片自动判定走了哪条边，`realized_path` 由代码写、不由人或模型填。它回答「按这个框架接下来几步各自该看什么、什么条件算升级 / 降级 / 放弃」，不回答涨跌、时点、目标价——与观察剧本同一道硬门、同一个 `scope`。

---

## 1. 现状 [实测 @ `gitea/main` `8e452e72`]

| 位置 | 现状 | 用法 |
|---|---|---|
| `intelligence/services/observation_script.py` | `ObservationScript`（`scope ∈ index/sector/theme`、`variables / upgrade / downgrade_or_abandon`、`status ∈ drafted/confirmed/skipped/late/expired`、`hindsight`、`framework_version`）、`validate()` 硬门错误码 `E_SCOPE / E_NO_VARIABLES / …`、`is_late`、`enters_calibration`、`build_metric / default_due / resolve_due`（T+1 回检登记） | 节点对象直接复用，**不新造节点类型** |
| `intelligence/services/compliance_gate.py:30–41` | 错误码 `E_STOCK_SCOPE / E_DIRECTION / E_TIMING / E_NEXT_DAY_DIRECTION / E_TARGET_PRICE / E_PROBABILITY / E_STRATEGY_WORD / E_FORWARD_CALL`；`OBSERVATION_SCRIPT_CODES`、`MARKETING_CODES` | 树上的自由文本走同一词表；**不新增词** |
| `intelligence/services/methodology_backtest/rules.py:145 Predicate(label, op, value)`、`compiler.py:146 compile_rule` | 规则 DSL 的谓词与白名单校验 | 分枝条件 = `Predicate`，复用校验；**不另写 DSL** |
| `methodology_backtest/labels.py:93` `LABEL_VERSION` v3；`:106–115` `ALL_LABELS`（sector 5 / theme 3 / market 4 / stock 3 = 15） | 注册标签目录 | 条件只能引用这里的名字 |
| `intelligence/services/river.py:248 _market_track` | 发 `object_type="stage"` 对象，payload 含 `market_stage / stage_day / total_amount / amount_vs_yesterday_pct / advancers / limit_up / limit_down / sh_deviation_pct / volume_state`；板块 `label` 对象 payload 为 `fact_sector_daily` 行；题材 `label` 为 `fact_theme_limit_heat_daily` 行 | 切片里是**原料字段**，不是编译后的标签值——解析器要一层「标签绑定」把 `Predicate` 落到 payload 上（§2.1） |
| `intelligence/services/checkpoints.py:198 register_checkpoint`、`OBJECT_TYPES=("judgment","agent_judgment","observation_script")` | 台账入口 | 沿路剧本到达即登记；`OBJECT_TYPES` **加 `scenario_tree`**（§4.2） |
| `intelligence/services/scenario_tree.py:62 ScenarioTreeArtifact` | 旧：问答路由的「推演契约」产物 | **同名不同物，不碰** |
| `rg "class ScenarioTree\b\|realized_path" intelligence/` | 仅旧 artifact；`realized_path` 0 命中 | 缺口成立 |

---

## 2. 三刀

### 2.1 刀 1｜对象 + 编译门 + 登记（`intelligence/services/scenario_trees.py`）

对象照 §3.3 原文（`id / user_id / visibility / as_of / knowledge_cutoff / projection_hash / framework_version / model_id / scope / entity_ids / max_depth / nodes[] / edges[] / realized_path[] / status / recorded_at`）。v0 约束：

- `max_depth ≤ 3`（路线图 G-15 v0；V3 放开到 5）。每步 = 1 个交易日或一个回检期限（T+1 / T+3 / T+5），节点带 `step_kind`。
- `nodes[].condition`：`Predicate(label, op, value)` 的合取（v0 只支持 AND，不支持 OR——OR 用两个兄弟节点表达）或字面量 `"otherwise"`。**白名单 = `SLICE_EVALUABLE_LABELS ⊂ ALL_LABELS`**：只收单日切片 payload 就能判的标签，实现时列一张显式表并逐条写绑定函数 `bind_<label>(slice) -> bool | None`（None = 该切片缺原料 → `gap`）。预期可进 v0 的：`market_stage`（G-05 归一后 7 段词）、`volume_surge`、`dual_red_strict`、`limit_heat_rank`、`mainline_flag`；需要历史的（`dual_red_streak / diff_ratio_turn_up / ma5_*`）与个股类（`limit_up / first_board / new_high_1y`，scope 不到个股）**v0 拒绝**，错误码 `E_LABEL_NOT_SLICE_EVALUABLE`。绑定函数**从 `labels.py` 导入常量**（`DUAL_RED_DIFF_RATIO_GT` 等），不复制数字。
- `edges[]`：同一父节点的子条件必须**互斥且穷尽**——v0 机械判法：兄弟节点两两条件不可同时为真（对白名单标签用取值域枚举 / 区间不相交判定；判不了的组合拒绝并要求作者改写），且恰有一个 `otherwise`。缺 `otherwise` → `E_NO_OTHERWISE`；不互斥 → `E_SIBLINGS_OVERLAP`。
- 节点 / 边 / 树上所有自由文本过 `compliance_gate`：`OBSERVATION_SCRIPT_CODES` 全部 + `E_STRATEGY_WORD` + 「方向」一词（走既有 `E_DIRECTION`）+ `E_PROBABILITY`（概率数字、百分比）。`analog_ref` v0 必须为空（`E_ANALOG_REF_NOT_AVAILABLE`），等 #35。
- 登记：`register_tree(tree, path)` → append 到用户态 `scenario_trees.jsonl`（`userspace.users_dir()` 下，与 `checkpoints.jsonl` 同级；台账地图登记），**append-only**：树本体一条，之后每一步解析各一条 `scenario_tree_step`，引用 `tree_id`，不改写原记录。`projection_hash / model_id / framework_version` 缺任一 → 拒收（§4.2）；`checkpoints.OBJECT_TYPES` 加 `"scenario_tree"`，树登记时同时在 `checkpoints.jsonl` 落一条 `object_type="scenario_tree"` 的可证伪点（claim = 根节点剧本的 `to_claim()`，due = 最深步的到期日），让它进同一条校准口径。

### 2.2 刀 2｜逐日解析器（`resolve`）

- `resolve(tree, as_of=T+k) -> ResolutionStep`：取 `river.slice(T+k, knowledge_cutoff=T+k, entity)`（**不是 now**——§3.3 硬门 3），对当前节点的每个子节点算条件：任一所需标签绑定返回 None → 该步 `unresolvable`，树 `status=unresolvable`，**停在那里，不猜、不跳、不用别的轨补**；否则恰一个子条件为真（互斥保证）→ 追加 `realized_path{node_id, resolved_as_of, evidence_refs=[命中标签对象的 ref]}`；到达的节点其观察剧本按 G-03 口径登记（`register_checkpoint(object_type="observation_script", projection_hash=当日投影哈希)`）。
- 解析用的当日投影：`river_projection.project(slice, task="scenario_tree", …)`（#34），其哈希写进 `ResolutionStep`——每一步「当时看到了什么」同样可回放。
- CLI `scripts/scenario_tree.py`：`draft --spec tree.json --as-of --entity --scope`（校验 + 编译 + 打印拒绝码，不登记）、`register`、`resolve --as-of`、`show <tree_id>`、`recheck`（刀 3）。每日复盘接线**v0 不做**；只留 `daily_review` 里一个默认关的钩子 `FORESIGHT_SCENARIO_TREE_RESOLVE=1` 跑 `resolve` 全部 `status ∈ {confirmed, resolving}` 的树——关着时逐字节不变（同 G-03 的 seam 断言写法）。

### 2.3 刀 3｜三项回检（`recheck`）

按 §3.3 回检口径，**不按「走了哪条枝」判对错**：

| 项 | 读数 | 口径 |
|---|---|---|
| (a) 覆盖 | 每棵已解析的树：落进声明分枝的步数 / 总步数；`otherwise` 占比 | N < 10 棵不出比率，写样本不足 |
| (b) 沿路剧本 | 每条被到达的观察剧本的 verdict（复用 G-03 的 T+1 回检与 `enters_calibration`） | 与 `checkpoints.calibrate(by_object_type)` 同一格 |
| (c) 规则样本 | 每条被走过的 `(condition → 下一步切片事实)` 记成一条样本，**存在 `scenario_tree_step` 记录里**（`sample={condition, next_facts_refs}`） | v0 只存不提议；进 §5.4 候选提议器是 G-16 的事 |

`recheck` 输出人读表 + JSON 收据 `methodology/receipts/scenario_trees/<date>.json`（台账地图登记）。

---

## 3. 验收（逐条可打勾）

1. 条件引用不在 `SLICE_EVALUABLE_LABELS` 的标签 → 整棵树拒绝，错误码点名标签；引用 `ALL_LABELS` 之外的名字 → 同样拒绝。【§10 第 13 条 / §11 第 13 条】
2. 缺 `otherwise` → `E_NO_OTHERWISE`；兄弟条件可同真（如 `market_stage == 反弹` 与 `volume_surge == true`）→ `E_SIBLINGS_OVERLAP`；`max_depth = 4` → 拒绝。
3. 节点文本含「策略」单独出现 / 方向词 / 「概率 60%」/ 个股代码 → 各自错误码（复用 `compliance_gate` 既有码，测试逐个）。【路线图 G-15 验收：lint】
4. `register_tree` 缺 `projection_hash` 或 `model_id` 或 `framework_version` → 拒收；`checkpoints.jsonl` 出现 `object_type="scenario_tree"` 记录。
5. `resolve`：夹具切片三种情形——恰一子条件真 → 路径延长一节且 `evidence_refs` 非空；所需标签缺原料 → `unresolvable` 且路径**不**延长；`otherwise` 命中 → 路径延长、节点为 `otherwise`。【§10 第 14 条】
6. `resolve` 用的切片 `knowledge_cutoff == as_of`（测试断言传参；传 `now` 的调用被拒绝）。
7. 绑定函数一致性 oracle：随机抽 30 个 `(entity, day)`，`bind_<label>(slice)` 与旁路库 `db/history_labels.duckdb` 同名标签值一致（`None` 对 NULL）；不一致逐条进收据并归因——这是「切片原料 → 标签」这层没有偷换口径的证据。
8. 关掉 `FORESIGHT_SCENARIO_TREE_RESOLVE` 时每日复盘输出逐字节不变（seam 测试）。
9. `recheck` 对 < 10 棵树不出比率；(c) 样本落在 `scenario_tree_step` 记录里，`rg` 不到任何新台账文件。
10. 真库冒烟（不进测试）：手写一棵深度 2 的上证指数树（条件只用 `market_stage` 与 `volume_surge`），`draft` 通过、`register`、对已过去的两天 `resolve`（`as_of` 取历史日，`C = as_of`），路径长度与 `unresolvable` 情况写进收据 `docs/verification/2026-09-08-scenario-tree-v0.md`。
11. 旧 `scenario_tree.py` / `test_scenario_tree.py` 零改动（`git diff --stat` 证明）。
12. 干净树全量 `ruff 0` + 红集不大于基线；`check_test_receipt.py --expect-revision HEAD`。

---

## 4. 非目标 / 红线

- ❌ 不做 OR 条件、不做深度 > 3、不做 `analog_ref`（等 #35）、不做 Workbench 端点、不接每日复盘（只留默认关的钩子）。
- ❌ `realized_path` 不得由人或模型填；解析只读 `slice(T+k, C=T+k)`。
- ❌ 不写方向、时点、目标价、概率；产品语言只用「情景树」，「推演」只作口语翻译，「预测路径」不得出现在任何字段名与文案。
- ❌ 不新造标签、不复制 `labels.py` 的常量；不改旧 `scenario_tree.py`。
- ❌ 不新增第二套存储；`scenario_trees.jsonl` 是用户态 append-only 台账，与 `checkpoints.jsonl` 同族。
- 观察剧本的所有红线（scope 只到指数 / 板块 / 题材，不到个股）对节点原样成立。

---

## 5. 教学注

- **为什么条件必须可编译**：树的价值在于 T+k 能被机器判定「走了哪条边」；条件一旦是散文，判定就得回到模型，回检就变成模型给模型打分。规则 DSL 白名单是把「可判定」变成登记时就能拒绝的静态检查——和类型系统在编译期拒绝非法程序是一回事。
- **互斥 + `otherwise` 为什么强制**：没有 `otherwise`，世界不落进任何分枝时树就没话说，只能「跳过」——跳过就是静默；不互斥，两个分枝同真时「走了哪条」需要一个优先级，优先级就是隐藏的判读。这两条把「框架对这个环境有没有语言」变成可量的读数（`otherwise` 占比），而不是感觉。
- **不按走了哪条枝判对错**：分枝是世界的选择，不是框架的对错；框架的对错在「到达的剧本变量是否按条件触发」与「条件 → 下一步事实」的样本统计里。这和天气预报的评分不看「明天到底下雨没」而看校准曲线是同一思路。
- **替代方案对照**：(a) 让模型每天读切片写一段「推演更新」——不可重算、不可回检；(b) 用现成的决策树 / 状态机库——分枝条件会绕开注册标签目录，词表分叉；(c) 本单：对象 + 编译门 + 确定性解析，模型只参与「起草树」这一步，且起草时看到的上下文有 `projection_hash`。

---

## 6. 交接要求

- 在途交接 `docs/handoffs/inflight/feat-scenario-tree-v0.md`（≤ 3K）。
- 合入后：路线图 G-15 回写「v0 已落（#37）」；09-06 spec §10 第 13、14 条与 §11 第 13 条标实测；台账地图登记 `scenario_trees.jsonl` 与 `methodology/receipts/scenario_trees/`。
- `UBIQUITOUS_LANGUAGE.md`「情景树」条已在；本单补 `realized_path / otherwise / unresolvable` 三个字段词。

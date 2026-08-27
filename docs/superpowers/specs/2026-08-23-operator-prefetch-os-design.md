# 设计：薄算子 + 供数不变量 + 做法 OS（对照 Knevo，修空 manual 覆盖）

- 日期：2026-08-23
- 状态：Draft rev2（只落本文与配套 plan；未改生产路由、未切 8792）。rev2 补入 D10 的 as_of 穿越（§4 事实 12）、D11 gap 归 P0（事实 13）、可证伪验收句（§5.3）。
- 分诊：`~/.finance-runtime/trace-diff-spt-fengyuan-history-20260823/`（三臂 M2，报告契约 RC=0）
- 代码树：`/Users/a77/fwp-wt-operator-prefetch-os`（`docs/operator-prefetch-os` ← `gitea/main@90c069cb`）。禁止在主检出 `feat/reading-rules-baseline-batch1` 脏树上改
- 施工计划：`docs/superpowers/plans/2026-08-23-operator-prefetch-os.md`（只含 P0）
- 相邻：`2026-08-22-capability-switchboard-design.md`（开关板是消融夹具，生产不读）；`2026-08-05-intent-routing-candidate-arbitration-design.md`（LLM 路由仲裁已否）；`docs/prediction-ledger.md` 的 `R-20260823-SPTTECH-*`

## 0. 一句话

意图层已经能认出 `history_analog`，细粒度快车道也能把原题标成 `comparison_analog`。卡住的是更早的一条 **空 `manual + []` 短路**，把信封盖成 `general_finance_qa`，预取只给今日主线，历史同构格子没有供数。本单做减法：删掉「模式旗标盖过已识别算子」，并把 **算子 → D10/D8/D11 或显式 gap** 写成不变量。不把路由改成「只留一个 LLM 入口」。

**判别变量**（P0 验收只锁这两条）：

1. 冻结题面在 `skill_mode=manual, selected_skill_ids=[]` 下，`decide_turn(..., llm_complete=boom)` 的 `question_type` 必须是 `comparison_analog`。
2. 同一题面进入 continuous 开场预取后，证据账本必须有 D10 窗口（含日期与距离）或一条 `historical_analogs` 的显式 gap；不得只靠模型用画像原文填格子。该窗口必须**按问句截止日截断**（§4 事实 12）——冻结题是「目前的行情」，as_of 恰等于库尾，泄漏在本题上是潜伏的，但供数一旦接进 as_of-aware 的预取层就必须先修，否则任何带历史截止日的类比题都会拿到未来数据。

人话：点菜员已经听懂「要历史同构」。门口保安把「我自己看看菜单」理解成「我点了普通套餐」，厨房就没上那道菜。本单撤保安的过宽规则，并规定：听懂了就必须上菜或声明缺菜。

---

## 1. 对照表（Knevo / 本仓现状 / 本单目标）

「成熟产品」弱先验：Knevo 活着证明的是整条生意（datasvc + 研报授权 + 出餐），不是证明「取消确定性路由」对本仓的失败形状更优。知识卡原文：壁垒不在框架。

| 维度 | A. Knevo（实测+自述） | B. 本仓现状（`90c069cb` + 2026-08-23 三臂） | C. 本单目标 |
|---|---|---|---|
| 分层 | Skill=怎么做；Workflow=派谁；Sub-agent=干活。`finance-mode` OS 压过专项 | 24 行 `route_table` 混了「这是什么题」和「给什么合同」；做法散落在 owner / episode / gate | **抄 Knevo 分层，不抄取消表**：算子=这是什么供数；信封=题型合同；skill/OS=怎么写 |
| 入口 | 主 agent 意图 + workflow 默认表；主 agent **可覆盖**默认 skill | 确定性 `_deterministic_decision` 先跑；空 `manual` 在细粒度路由之前 `return workflow` | 确定性薄核保留；**空 manual 不得覆盖**；LLM 控制器仍只在确定性未命中时出场 |
| 问法穷举 | workflow 表 + 「一字之差从轻档到重档」；专项约 8 个 | 细粒度正则/解析器 + 词表（08-09「能否」假阳性已在案） | **穷举算子，不穷举问法**。类比只认已有 `parse_analog_intent` / `parse_regime_intent` |
| 硬触发 | T1–T5 → 指定工具（报价必须现查） | Engine B 的 D8/D10/D11 是 DataBlock；Engine A 开场预取只有双红/发酵，**没有 D10** | `history_analog` → 必须预取对应块或 gap，与 `question_type` 戳记无关 |
| 工具面 | 7 个数据/记忆工具；skill 不是工具 | 12 个 capability；D10 **不是**其中之一 | P0 **不**把 D10 加成第 13 个工具；走已有 `collect_prefetch_items` |
| 路由是不是快车道 | 表给默认，LLM 可改派（建议） | 路由是**授权+预取**。盖错信封，模型不能调用没发的供数 | 保持合同先行。建议可忽略会放大「有格子没供数」 |
| 专项怎么挂 | 每个 sub-agent 恒 `finance-mode + 一个专项` | 技能桥故意只开 `serenity-alpha`（只读/无外呼） | P1 才写「类比做法」手册；**不**把 30 个仓内 skill 全挂上 |
| 8792 / 8796 | 无此对 | 现已同快照 `1c52e19f`；差的是端口和 `users_dir`，不是解耦开关 | 对照臂用开关板 runner，不用两端口冒充「解耦 vs 非解耦」 |
| 以后哪类事故变少 | 出餐卡死、骨架漂移、上下文爆炸 | — | **信封覆盖、有格子没供数**。问法长尾仍靠算子，不靠再加正则 |
| 以后哪类事故可能变多 | 覆盖权导致评测方差；workflow 词面分流仍在 | 空 manual、题型与算子分叉 | 若抄 A 的「路由是建议」：**本轮病复发率上升** |

### 1.1 不抄 Knevo 的三条

1. 只留一个 LLM 入口、路由改成 skill 清单。skill 选择本身是分类，D10 仍不在菜单上。
2. 主 agent 可任意覆盖合同。本仓要 fail-closed：格子没有供数就不能 `business=complete`。
3. 把仓内会外呼/写库的 skill 当 Knevo 专项挂上。红线仍在。

### 1.2 抄 Knevo 的三条

1. **OS 压过应用**：禁止无证据历史窗口、内部质检不准进公开答案。冲突时 OS 赢。
2. **专项只写做法**：类比骨架（六项比较、角色对标、失效条件）在算子点火后加载。
3. **硬触发**：行情/历史窗口必须现查或标 gap，不能用印象流。

---

## 2. 范围

### 2.1 做（P0，本 plan）

- 收窄 `turn_controller._deterministic_decision`：`skill_mode == "manual"` 单独不得返回 workflow。只有 `selected_skill_ids` 非空才算「用户显式选了技能」。
- **D10 取数按 `as_of` 截断**（见 §4 事实 12，接线前必须先做）：`load_market_regime_vectors` 加 `where trade_date <= as_of`，`load_market_regime_artifact` / `regime_block_for_llm` 透传。默认 `as_of=None` 保持今日行为，Engine B 不动。
- `history_analog`（`parse_analog_intent` 或 `parse_regime_intent`）一旦出现，开场预取必须带对应历史块或 gap：
  - 市场环境类比（regime：环境词 ∧ 类比词）→ D10（**必须是截断后的块**）
  - 仅题材自身历史（analog 而无环境词）→ D8（已有 Engine B 块；P0 至少 gap，不在本单重做 D8 滑窗）
  - 个股对标词面（`parse_stock_analog_intent`）→ P0 只留 D11 gap。冻结题面命中此条（§4 事实 13），**不能推到 P1**，否则验收题自身「个股怎么对标」一问无证据也无 gap，直接违反 §1.2 规则 1。
- 冻结题面（§5）离线锁死：空 manual 下进 `comparison_analog`；预取含 D10 或 gap。
- 回归：`manual + [真实 skill id]` 仍走显式技能约束；寒暄/澄清/取值不被本单改道。

### 2.2 不做

- 不实施「全 LLM 入口」。
- 不实施 08-05 路由仲裁 / 候选 LLM 否决权。
- 不改 8792/8796 切流，不改 provider，不加 D10 为 agent 工具。
- 不把 `route_table` 24 行改写成 skill 文件。
- 不在 P0 修发布层「质检拼进 answer.md / 投影后仍 complete」（二次失败，见 §8；账本 `R-20260823-SPTTECH-03` 已 refuted）。
- 不在 P0 做 n≥10 的 8792/8796 非法首动作归因（`R-20260823-SPTTECH-04` 仍 pending）。
- 不把风远样本 0 当成「视角失败」——三臂已披露，属数据边界。

---

## 3. 术语

| 词 | 含义 |
|---|---|
| **算子** | `query_understanding._research_operators` 的确定性标签。类比为 `history_analog`。 |
| **信封 / 题型** | `question_type` + `required_outputs` + `allowed_capabilities`。路由盖章的对象。 |
| **供数 / 预取** | harness 在模型首轮之前写入证据账本的确定性块。现役入口：`asof_prefetch.collect_prefetch_items` → `format_opening_prefetch_message`。 |
| **D10** | `market_regime_analogs`：市场情绪向量的历史相似窗口。Engine B 已接线；Engine A 预取未接线。 |
| **空 manual** | `skill_mode=="manual"` 且 `selected_skill_ids=[]`。UI「不自动选技能」，不是「已选工作流」。 |
| **覆盖** | 更早的 `return` 让后面的细粒度路由 / 算子供数成为死代码。 |
| **OS** | 底线纪律（硬触发、禁止编窗口、质检不公开）。P1 才落成独立文本；P0 先把硬触发做成代码不变量。 |
| **Engine A / B** | A=`continuous_episode`（生产默认）；B=`ask.answer_query` 写死流程。 |

---

## 4. 已核实事实（实施时不要再探一遍）

行号以本树 `gitea/main@90c069cb` 为准。三臂产物在仓外 runtime 目录。

1. 空 manual 短路在 `turn_controller.py:313-321`：`if selected_skill_ids or skill_mode == "manual": return workflow / reason=用户显式选择了工作流能力`。其后才是寒暄、元问题、`_fine_grained_route_row`（`:330`）。
2. `_fine_grained_route_row`（`:542-556`）在 `parse_analog_intent` 或 `parse_regime_intent` 或类比正则时返回 `comparison_analog`。单测已有：`test_regime_query_routes_to_comparison_analog`。
3. `_research_operators`（`query_understanding.py:860-861`）在同样两个解析器上追加 `history_analog`；`_required_outputs` 把它映射成格子 `historical_analogs`（`:889`）。
4. 三臂冻结题面（§5）两侧 Workbench `controller`：`operators=["history_analog"]`，同时 `question_type=general_finance_qa`，`retrieval_stages=[]`，`evidence_plan.profile=mainline_current`（今日 MARKET_DAILY + D4）。request SHA 两侧相同。
5. 直调 `TurnControlCore`（Codex 组件臂）同题得到 `comparison_analog` 与六项比较合同，并消费 D10 窗口 `2026-02-06～2026-03-13`（距离 0.574）。
6. Engine A 的 12 个工具不含 D10。8792 实际调用 `finance_query` / `market_data` / `mainline_context`，4 请求均成功。gate 报的是「2024/2025 类比无注册证据」，不是 tool schema 失败。
7. Engine B 已有 D10 DataBlock（`ask.py` 约 `:3980-3993`），`_d10_applies` = 注册表开启 **且** `parse_regime_intent`。比 `history_analog` 算子更窄（算子是 analog **或** regime）。
8. Engine A 开场预取 `collect_prefetch_items`（`asof_prefetch.py:367`）今日只处理 `question_type==market_forecast` 的双红序列，以及发酵时间轴。**无 D10 分支**。`con is None` 时直接 `return ()`，连 gap 都不会留。
9. 冻结题面含「行情」+「相似/对标/历史」→ `parse_regime_intent` 为真（`_ENV_TERMS` 含「行情」，`_ANALOG_TERMS` 含「相似」「对标」）。因此 P0 绑 D10 对该题充分。
10. 08-09 实测 62 条去重 query：为互斥题型建 LLM 仲裁的真实互斥样本为 0；「能否」裸匹配造成契约拒答。本单禁止用再加词表或 LLM 分类来「修穷举」。
11. 活进程 8792/8796（2026-08-23 10:16）同 revision `1c52e19f`、同依赖指纹；差 `FORESIGHT_USERS_DIR` 与端口。解耦差量为零。
12. **D10 今日完全不接收 `as_of`，未来数据从四处渗入**（2026-08-23 实测，`market_regime_analogs.py`）：
    - `regime_block_for_llm(:459)` / `load_market_regime_artifact(:368)` / `load_market_regime_vectors(:327)` 三个签名**都没有 as_of 参数**；
    - base 查询 `select ... from fact_market_daily order by trade_date asc` **无 where**，取全库；
    - `find_regime_analogs(:268)` 的「当前窗口」写死 `z_rows[n - window:]` = **库尾**，不是 as_of 尾；
    - `standardize_vectors(vectors)` 用**全历史**算 z 均值方差 —— 这一条最隐蔽：即使前两条修好，未来数据仍从**缩放系数**渗回（经典 look-ahead bias，scaler 必须只 fit 截止日之前）；
    - `_forward_facts(vectors[end:], h)` 的候选窗口最晚可到 `n - window`，其后续 5/10/20 日会跨过 as_of。
    **一刀解四处**：只在取数层加 `where trade_date <= as_of`，下游全部只消费 `vectors`，自动被截断。辅表不必加同一条件（按日期键回查 base 行，as_of 之后的辅表行不可达）。
    本仓已为同一失败形状留过测试：`test_asof_prefetch_dual_red.py::test_fermentation_query_cutoff_is_requested_as_of_not_current`。把没有 as_of 的 D10 接进 as_of-aware 的预取层是开倒车，故 P0 必须先截断再接线。
13. 冻结题面上三个解析器的实测取值（**不要再探**）：`parse_regime_intent=True`、`parse_analog_intent=**False**`、`parse_stock_analog_intent=True`。因此该题走 D10 分支 + D11 gap 分支，**不走** D8 分支；§2.1 的 D8 条款对本题是死代码，但对「信创历史上类似」一类仍有效。
14. `stock_analogs.py` 同样零 `as_of`（`stock_analog_block_for_llm(:331)`）。P0 只对 D11 出 gap、不出块，故不继承该泄漏；接线前需先按事实 12 同样处理（P1）。

---

## 5. 冻结题面与规则

### 5.1 冻结题面

```text
用spt和风远的结合视角，说一下目前的行情和之前的哪一段历史行情比较相似，个股怎么对标。
```

来源：`trace-diff-spt-fengyuan-history-20260823`。数据截止 2026-08-21。`llm_complete` 测试必须 boom / 不可用，禁止为了分类去调 LLM。

### 5.2 P0 规则（按优先级）

1. **旗标 ≠ 载荷。** `skill_mode=="manual"` 只表示「不要自动选 skill」。`selected_skill_ids` 非空才是显式选择。
2. **覆盖禁止。** 任何模式旗标不得排在 `_fine_grained_route_row` 与算子供数之前，去否决已经成立的 `history_analog`。
3. **算子绑供数，不绑题型。** `resolve_evidence_plan` 今日按 `question_type` + 「是不是当前市场问句」走 `mainline_current`。P0 不重写这张表的主路径；在 **预取层** 追加 D10/gap，使 `question_type` 即使仍是 `general_finance_qa`（其它回归路径）也不能让历史格子空转。
4. **D10 优先于「再查一遍今日盘面」。** 开场消息必须能引用窗口起止日或 gap 句。禁止模型用 SPT/风远框架句冒充窗口。
5. **缺库是 gap，不是空预取。** `collect_prefetch_items` 在 analog/regime 已命中时，即使 `con is None`，也要留下一条 `historical_analogs` gap，不得 `return ()`。
6. **历史窗口不得跨过问句截止日。** D10 供数按 `as_of` 截断（§4 事实 12）。截断只做在取数层一处，不在渲染层裁剪——渲染层裁剪挡不住 z 标准化系数里的泄漏。
7. **测试必须能证伪。** 只锁「缺库出 gap」不够：一个「永远返回 gap」的实现也能全绿。验收必须同时有**正向**用例（有数据时真出 D10 块）与**判别**用例（两个不同 as_of 给出不同的块）。

### 5.3 验收句（离线，两层）

| 层 | 调用 | 冻结题 + 空 manual | 对照 |
|---|---|---|---|
| 回合信封 | `decide_turn(题, skill_mode="manual", selected_skill_ids=[], llm_complete=boom)` | `question_type=comparison_analog`；`operators` 含 `history_analog`；reason **不是**「用户显式选择了工作流能力」 | `skill_mode="manual", selected_skill_ids=("daily-agent",)` 仍可因非空列表走技能约束（不得把「选了 daily-agent」误判成本题） |
| 预取（缺库） | `collect_prefetch_items(question=题, market_db_path=不存在的 tmp 路径, ...)` | items 非空，含 `historical_analogs` gap 与 D11 gap | 「今天涨停多少家」（无类比词）不得多出 D10 |
| 预取（有数据，**正向**） | 同上，`market_db_path` 指向合成小库 | detail 含 `[D10]`、`历史相似窗口`、`后续5日` | 缺此条则「永远返回 gap」的实现也能全绿 |
| 预取（**判别**） | 同一库、两个不同 `as_of` | 两次 D10 块**不相等** | 相等即说明 as_of 被忽略（§4 事实 12） |
| 取数截断 | `load_market_regime_vectors(con, as_of=D)` | 向量数与末日恰好截到 D；不传 as_of 时行为不变 | 唯一截断点，见 §5.2 规则 6 |

取值对照：「宁德时代今天收盘多少」+ 空 manual → 仍是 `quick_fact` / 取值，不得被本单改成类比。

测试路径一律用 pytest `tmp_path` / `TemporaryDirectory`，禁止硬编码 `/tmp/xxx.duckdb`——该文件一旦真实存在，缺库用例会静默换语义。合成库复用 `test_market_regime_analogs.LoaderAndBlockTests._make_db`，不另建第二份建表 SQL。

---

## 6. 推荐装法（三种对照）

| 方案 | 做法 | 对本轮 | 代价 | 结论 |
|---|---|---|---|---|
| A. 只留 LLM + skill 当路由 | 删 `_deterministic_decision` 细粒度段 | 空 if 没了，但 D10 仍不是工具 | 每题分类方差；08-09 已否仲裁 | 不采用 |
| B. 继续加 `route_table` 正则 | 为「相似/对标」再写几条 | 不修短路则原题仍死 | 「能否」类假阳性 | 不采用 |
| C. 薄算子 + 预取不变量 + 做法 OS | 本单 | 空 manual 放行；格子有 D10 或 gap | 预取多一次 DuckDB 只读 | **采用** |

---

## 7. 实施落点（P0 只碰这些）

| 文件 | 改什么 |
|---|---|
| `intelligence/services/turn_controller.py:313` | 条件改为只认非空 `selected_skill_ids`（单行） |
| `intelligence/tests/test_turn_controller.py` | 冻结题 × 空 manual / 非空 skill / 取值题 |
| `intelligence/services/market_regime_analogs.py` | 取数层加 `where trade_date <= as_of`；`load_market_regime_artifact` / `regime_block_for_llm` 透传；补 `from datetime import date`（今日无此 import） |
| `intelligence/tests/test_market_regime_analogs.py` | 追加到既有 `LoaderAndBlockTests`：取数截断 + 历史窗口不跨 as_of |
| `intelligence/services/asof_prefetch.py` | 新私有 `_history_analog_items`；`collect_prefetch_items` **只替换 6 行锚点**（`con = _connect` 前置 items 与 gap 返回），`market_forecast` / 发酵两段一字不动 |
| 新 `intelligence/tests/test_asof_prefetch_regime_analog.py` | D10 正向 + as_of 判别 + gap + D11 gap；非类比题不注入 |

改 `asof_prefetch.py` 后必须确认 `git diff` 只有三处（import 块、新函数、6→7 行替换）。双红与发酵的回归网是 `test_asof_prefetch_dual_red.py`、`test_prefetch_slot_numbers.py`、`test_prefetch_evidence_ordinal.py`（第三个此前漏列，也消费 `asof_prefetch`）。

不改 `route_table.py` 的 `comparison_analog` capabilities 元组（仍是 memory/graph/web）。P0 不靠改白名单让模型「自己找到 D10」。

---

## 8. 二次失败（记入，P0 不修）

三臂 SECONDARY：8796 首动作非法 finish → 重试 → 20s 合成超时 → repair → 公开核心两句 + 15 条质检，仍 `business_status=complete`。与空 manual **无共同因果**。发布层减法（投影后覆盖率 =1.0 才 complete；质检不进 `answer.md`）单独立项，沿用账本 `R-20260823-SPTTECH-03`。

8792/8796 非法动作率不得用单 pair 归因端口。对齐纪律：同快照、同一用户快照拷贝、`model_input_sha256` 成对 100%，每侧 n≥10。8796 的角色是隔离写根，不是解耦对照臂。

---

## 9. P1（本单不施工，只钉方向）

1. 类比做法 skill（六项比较合同、角色对标、禁止画像冒充窗口）。算子点火后加载，不是路由入口。
2. OS 条文：内部 gate issue 不得进入公开 `answer.md`。
3. `resolve_evidence_plan` 增加「算子 overlay」行（与隔夜 overlay 同形：不改 `question_type`，只追加 requirement）。若 P0 预取已够用，本条可取消，避免两处供数。
4. `stock_analogs` 按 §4 事实 12 同样加 as_of 截断，然后把 D11 从 gap 升级成真块接进 Engine A 预取。
5. Engine B（`ask.py:3986`）把 `options` 的截止日传进 `regime_block_for_llm(as_of=...)`。P0 留默认 `None` 只是为了零行为变更，**不代表 Engine B 没有同一泄漏**。

---

## 10. 风险与回归

- **真选手动技能失效：** 测试必须覆盖 `selected_skill_ids` 非空。收窄后若有产品依赖「空 manual = 强制 workflow」，那是产品语义错误，应改 UI 传真实 skill id，不得恢复 `or skill_mode == "manual"`。
- **预取变贵：** D10 是本地 DuckDB 只读滑窗，与现有双红预取同档。超时走 gap，禁止外呼。
- **D10 与 D8 抢戏：** 冻结题是市场级，只强制 D10。纯「信创历史上类似」保持 D8 领地（`parse_regime_intent` 文档已写）。冻结题 `parse_analog_intent=False`（§4 事实 13），两者本就不会同时点火。
- **as_of 截断改坏默认路径：** `as_of=None` 必须与今日逐字节等价。`test_market_regime_analogs.py` 既有用例全部不传 as_of，它们变红即为回归信号，不得改测试就范。
- **P0 之后仍有已知泄漏：** Engine B 的 D10 与 D11 的 `stock_analogs` 都未截断（§4 事实 12/14）。本单只保证 **Engine A 预取路径**的 D10 无穿越；对外表述不得说成「D10 已全面按截止日取数」。

---

## 11. 合入与部署

- 先合 P0 测试+实现，不切 8792。
- 切流前用冻结题在干净 sidecar 重放一次，对照 `trace-diff-spt-fengyuan-history-20260823` 的 `question_type` 与预取，不重跑三臂评分。
- 主检出脏树只允许 pathspec 提交本分支文件；本工作树与脏树隔离。

# 设计：覆盖追上 Knevo，数字所有权不交还

- 日期：2026-08-30
- 状态：Draft v1（只落本文。未改 `intelligence/`，未切 8792）
- 来源：2026-08-30 会话（Knevo 联想/记忆/并行仍常赢，与「模型不拥有数字」是否冲突）+ `docs/learning/knevo-vs-workbench-技能包对比台账.md` + `agent-memory/10_knowledge/knevo-reverse-engineering.md`
- 姊妹单（本单不重做）：
  - `2026-08-30-engine-b-into-a-strangler-design.md`——D 块并进 A 预取（D8/D11 接线归那单）
  - `2026-08-30-workbench-correction-loop-design.md`——**写侧**：工作台「纠正上一篇」落 `corrections.jsonl`（本单只验收读）
  - `2026-08-23-operator-prefetch-os-design.md`——算子 → 块或 gap
  - `2026-08-24-workbench-quality-residual-ux-design.md`——编译后再残差
- 代码树纪律：从 `gitea/main` 开干净树再改 runtime。本稿允许落主树 untracked。**禁止**把成交额/涨停/逐季净利交还模型去「搜出来」。**禁止**为追覆盖把包改成无约束 compose。

## 0. 一句话

Knevo 在联想广度、用户记忆命中、一篇里多路并行上常赢，**和「数字归 SQL/包/预取」不冲突**。差距不是取数手段换了，是这三样没被当成和双红一样的**开口必取**，循环还是单线程，记忆当选配。本单把记忆和联想补进必取清单，并行只走已有的有界子研究；模型继续只负责理解、补查和推理。

**判别变量**（P0 验收只锁这两条，冻结题另立，见 §5）：

1. **记忆**：带明确主体的研究题（个股/题材/跟踪/买卖，不问句是否写「上次」），opening prefetch 或首轮授权里必须出现 `memory_lookup` 的一块观察（命中带 `content_hash`，无笔记则显式 gap「用户记忆无相关命中」）。不得只靠模型印象。
2. **联想**：问句命中类比/对标/「类似历史上」算子时，opening 必须有 D8 或 D11 或 D10 的块或 gap（接线本身跟姊妹单；本单锁的是**研究题不得因题型不是 `comparison_analog` 就跳过**）。

P1 才锁并行：deep 且计划写出可分离 `branch_goals` 时，`SubResearchCoordinator` 真跑，主稿只收各支结论+缺口，不把子窗口全文灌进主窗。

人话：菜谱可以继续不让厨师自己称盐。少的是开胃菜里的「你上次怎么看」和「历史上像哪一段」，以及偶尔让两个帮厨各查一路、只回报结论。

---

## 1. 不冲突：问题出在哪

数字从 LLM 网页检索改成 SQL/包，只换了**事实所有权**。Knevo 赢的三手要的是另一张必取表：

| 差距 | Knevo | 我们今天 | 真正缺口 |
|---|---|---|---|
| 联想 | 子 agent + web 翻先例/海外/洼地 | 类比块多在 B；A 开口 D8/D11 常只写「未接线」；专项箱不一定有 web | 必取清单窄，不是不能 SQL |
| 记忆 | 个股题几乎总会语义搜笔记 | `memory_lookup` 只挂在部分 evidence_policy；`prior_recall` 还要求问句像「上次之后」且题型 ∈ {个股,题材,跟踪,买卖} | 记忆当选配；语料薄是另一条 |
| 并行 | 最多四路隔离，主稿收结论 | A 接住则 owner skill 不跑；`SubResearchCoordinator` 仅 `tier=deep` + 模型写了 `branch_goals` + coordinator 已注入 | 座位在，默认没坐 |

`episode_protocol` 还要求 draft ≤ 1000 汉字。这是结构门需要短终局，不是覆盖策略；P1 若要多路，增量写在格子/附录，不把宪法改成「写得越长越好」。

---

## 2. 术语

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **数字所有权** | 成交额、涨停、逐季财务、包行数字只来自 SQL/包/预取 | 禁止模型写任何数（引用预取行是允许的） |
| **覆盖** | 记忆命中、历史类比、可分离的第二路检索 | 文笔像 Knevo；一篇 8000 字 |
| **必取** | harness 开口供数或挂槽，缺则 gap | 提示词写「请先查记忆」 |
| **有界并行** | 已有 `SubResearchCoordinator`：最多 3 支、每支 ≤8 次调用 / 60s，只读，结论回主账本 | Knevo 四路各 7500 字、1003 积分那种 |

---

## 3. 已核实事实（实施时不要再探一遍）

1. `memory_lookup` 在 `_RUNTIME_CAPABILITY_FLOOR` 里挂在：`company_multi_layer_evidence`、`theme_multi_layer_evidence`、`theme_tracking_evidence`、`conditional_thesis_evidence`、`general_finance_evidence`。**不在**：估值、财务、事件、可比、来源批评、`current_public_knowledge`。注释写明广授权会挤掉盘面刀（一轮 4–6 次易 `budget_exhausted`）。
2. `prior_recall` 注入：`episode_factory._references_prior_judgement` —— 题型必须在 `_PRIOR_RECALL_QUESTION_TYPES`，且问句匹配「回溯」或 stance 词。瑞华泰那种「这只股怎么看」**不会**只因为有主体就挂记忆槽。
3. Knevo 对照：`finance-analyze-stock` 胜负手 = 逐季财务 + 用户历史笔记（利用率/化学法线）。财务已由 D7/估值箱补；记忆命中仍依赖用户开口像回忆。
4. D8/D11：**接线已完成**（2026-08-30，姊妹单 P0 = R-20260830-02，分支 `feat/d8-d11-asof-prefetch` @ `64b5e6db`，已交付待验收未合 main）。`_history_analog_items` 现在 D8/D10/D11 各自出块或 gap，同一套 as_of 截断，解析器与取数同截。~~写明未在 A 接线 / 只在 B 接线~~ 那句已随实现删除，**别再照旧稿判断**。本单剩下的仍是：禁止「只有 `comparison_analog` 才预取」。
5. 并行：`sub_research.py` 已有上限；`agent_episode._run_sub_research` 在非 deep 或无 `branch_goals` 时直接 `None`。默认聊天档不是 deep。
6. Knevo 分层：skill = SOP（怎么写）；工具约 7 个。概率常无出处。本单不抄「主模型随便改派合同」，不抄无溯源数值概率。

---

## 4. 目标形态

```
研究题进 A
  ├─ 开口必取（harness，模型未点工具之前）
  │    ├─ 已有：盘面/双红/展望周报/算子块…
  │    ├─ 本单：有主体 → memory_lookup 块或 gap
  │    └─ 本单：类比算子 → D8/D10/D11 块或 gap（取数函数跟姊妹单）
  ├─ 工具箱：仍按题型裁，不残差全量
  ├─ A ReAct：补查、绑定、推理
  └─ 可选 deep：≤3 路子研究，主窗只收结论+缺口
```

包椅不动。数字行仍 fail-closed：无 `content_hash` 不上桌。

记忆观察的纪律（写进预取/工具契约，不写进「请回忆」散文）：

- 命中 = 用户笔记/纠偏/判断，**不是**市场事实；与硬数据冲突以硬数据为准。
- 空 = gap，禁止用训练记忆补「你上次说过」。

联想观察的纪律：

- 只列历史窗口事实（日期、涨跌、量），**禁止**写成「因此概率 15–20%」。
- 小样本必须在块内可见（已有 D8 使用要求则复用，不新造词表）。

---

## 5. 阶段

### P0 — 记忆改为开口必取（有主体的研究题）

- 扩大「该挂记忆」的判据：有可解析主体（公司/题材）且 `question_type` 为研究类（至少含个股/题材/跟踪/买卖；估值、财报分析 **P0 也挂**——Knevo 财报题同样吃笔记）。不要求问句含「上次」。
- 实现优先走 `collect_prefetch_items` 或 opening 等价物：harness 调一次 `memory_lookup`，结果进账本。不要只把 capability 塞进箱子指望模型第一刀点中（`prior_recall` 强制提示已被证伪）。
- 无语料 → 显式 gap，不算失败（`prior_recall` 已是 advisory）。
- 夹具：冻结「瑞华泰怎么看」形（无「上次」）→ opening 有 memory 观察或 gap；盘面/自选题 **不** 预取记忆。
- 预算：记忆预取不占模型工具刀。模型箱里是否仍留 `memory_lookup`：P0 保留（用户追问「再翻笔记」），但不依赖它完成必取。
- **它占的是开口延迟，必须显式限时**。「不占工具刀」只说了不占哪个池子，没说占哪个——`collect_prefetch_items` 是开口串行跑的，多一次记忆检索就多一段开口墙钟。§3 事实 1 引的那句注释（广授权会挤掉盘面刀、一轮 4–6 次易 `budget_exhausted`）说的正是同一个拥挤问题，只是换了个池子。**给记忆预取一个独立 stage timeout，超时即 gap**，照 `asof_prefetch` 既有 idiom（`_market_forecast_weekly_items` 的「锁和爆炸必须发卡，不得依赖外层 con」）。不写这条，第一次线上慢查询会把整个开口拖住，而且表现为「所有题都变慢」，不会指向记忆这一刀。

### P1 — 联想必取跟题走算子，不跟题型戳记

- 依赖姊妹单把 D8/D11 接到 A 预取。本单补：`history_analog` / 个股对标 / 「类似历史上」一旦在 `compile_research_program` 里出现，**任意**研究题型都预取，不得只认 `comparison_analog`。
- web/新闻：仅当算子或题型已要求事件面时开口预取或授权，**不**给残差箱无条件加 `finance_query`。
- 中期/赔率类问句：已有 D6 门控则锁「当日双红不得单独写成中期赔率」（台账里时间尺度错配）；本单不新开数据源。

### P2 — 有界并行，默认聊天仍单路

- 不把默认档改成 deep。
- 点火：模型 PLAN 写出 ≤3 条可分离 `branch_goals` **且** 政策允许升 deep（已有 governor）时，必须注入 coordinator 并跑；主稿引用支线结论哈希或 E 号，禁止粘贴子窗全文。
- 联想型可分离目标示例：「海外对标」「历史同构窗口」——只读检索，不写库。
- 夹具：deep + 两条 goal → 两条 `branch_started` + 主窗无子窗 raw dump。
- 不抄 Knevo 四路万元级积分。

### P3 — 语料与表达（本单只登记，不施工）

- 记忆台账薄（judgments 曾极稀）是覆盖上限，归 shared-memory / dream-mine 既有单，不在本单用 prompt 假装有笔记。
- draft 1000 字：多路增量进格子，不在本单放开宪法长度。

---

## 6. 非目标

- ❌ 残差五件改全量工具。
- ❌ 盘面/自选/复盘并进 A 或开无约束 refine。
- ❌ 交还数字所有权（模型网页搜成交额当硬事实）。
- ❌ 数值概率、决策者心理剧本（Knevo 软肋）。
- ❌ 主模型可覆盖合同（格子没供数仍 complete）。
- ❌ 把 30 个仓内 skill 挂上 A 当 frontier。
- ❌ 重做 D8/D11 取数函数（姊妹单）。

---

## 7. 冻结题草案（P0 实施时钉死原文）

实施 PR 从对照台账各抽 1 条，不得用「怎么看」泛化糊弄：

| ID | 题面意图 | P0 必须看见 |
|---|---|---|
| C-mem-1 | 个股怎么看（无「上次」） | memory 块或「无相关命中」gap |
| C-mem-2 | 盘面「今天市场怎么样」 | **无** memory 预取 |
| **C-mem-3** | **「我的自选今天怎么样」（主体明确，但走包椅）** | **无** memory 预取 |
| C-lat-1 | 含「历史上类似/怎么对标」 | D8 或 D11 或 D10 块或 gap |

**C-mem-3 是判据本身的反例，C-mem-2 不是。** C-mem-2（盘面题）靠的是「题型不对」挡住的，
换任何判据它都不会预取记忆——它证明不了「有主体」这条判据被正确收窄。
C-mem-3 是主体明确（用户自选清单）、`question_type=watchlist_digest`、在
`DETERMINISTIC_OWNER_TYPES` 里**根本不进 A**：只按「有可解析主体」判会把它误判成要预取。
两条都要，缺 C-mem-3 则判据是松的。

C-lat-1 已可直接锁块本体：姊妹单 P0 已交付（见 §3 事实 4），
原「未合前只锁预取函数被调用」的降级条款**作废**。

---

## 8. 红线

- 记忆命中不得升格为行情事实；冲突以包/SQL 为准。
- 预取无 `content_hash` 且不是声明的 gap → 不得当已上桌。
- 历史窗口 `as_of` 截断（姊妹单已写）。
- 不切 8792 直到独立验收。
- 台账号：`python3 scripts/claim_ledger_id.py claim --branch <分支>`。
- 不搬 CC 阈值。

---

## 9. 成立条件

- 本稿是覆盖策略，不替代 B→A 勒死单。两单可并行：那单搬取数函数，本单改「谁必须开口要」。
- P0 只改记忆必取即可独立验收；联想验收依赖姊妹单接线。
- `dirty` 主树若只多了本 md，不构成 runtime 变更。

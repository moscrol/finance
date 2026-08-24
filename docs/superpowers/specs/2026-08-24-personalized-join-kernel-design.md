# 设计：个性化接合基座（绑定 → 四平面 → 填格）

- 日期：2026-08-24
- 状态：Draft **v1.1**（P0 落地 + live PASS + `research_context` 瘦收据；门禁 ruff / 6312 pytest / frontend 绿；P1/P2 未做）
- 来源：Knevo 盘中双账户截图对照 + 既有逆向（`knevo-reverse-engineering.md`、蒸馏 q7/q8/q10/q12、E-006）+ 本仓运行态核对
- 核稿：2026-08-24 晚。v1 把包放在 `owner_output` 汇合处，主路径（`trade_advice` → research → Engine A）早退不可达。
- 代码树：从 `gitea/main` 开干净树 `feat/personalized-join-kernel`。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树上改 runtime。**禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做、不抢合）：
  - `docs/superpowers/specs/2026-08-24-market-watch-component-first-design.md` —— 盘面题换座位、四袋锁数
  - `docs/superpowers/specs/2026-08-24-outlook-live-weekly-pack-design.md` —— 展望五日包 **v2**：同族洞已改到 Engine A 开口预取（`collect_prefetch_items` + `_opening_prefetch_evidence`），台账号 `R-20260824-20`…`24`。本单椅子仍是 `handle()` 之前（买卖题没有现成 forecast 预取支）。两包都不要挂 compose
  - `docs/superpowers/specs/2026-08-17-followup-angle-composer-design.md` —— 选角 A/B/C/D
  - `docs/superpowers/specs/2026-08-13-memory-analog-lifecycle-design.md` —— 四平面 + 记忆门；**已划掉**「按记忆条数决定检索深度」
  - `intelligence/services/checkpoint_recall.py` —— V 块 loader + 渲染（main 已有）
  - `intelligence/services/track_contract.py` —— 跟踪表达契约（已落地）
  - `intelligence/services/memory_gate.py` —— 长期记忆晋升（已落地，比 Knevo pending 更严）

## 0. 一句话

个性化不是「用户自己写工作流」。基座是一次 **join**：绑定手续 → 实体当主键 → 四平面并行取数 → skill 空表填格 → 用户规则只当 prior、现价必须现查 → 同一绑定换参数续问。

人话：产品印空表，用户提供行，柜子里取现价。三样对上号再说话。没表、没主键、没现价，记忆调出来只是一段散文。

判别变量（本单 P0 只锁这一条）：在 `lane=research` 或 `question_type=trade_advice` 时，问句带持仓 / 目标价 / 该不该买，或题型就是 `trade_advice`，则 **`continuous_turn_adapter.handle()` 之前**必须已经跑完 `StancePack`（先验袋 + 现价袋），收据挂进 `research_context`。公开稿里的价和「你上次怎么说」只能来自袋，或显式 empty。不是「多调一次 `memory_lookup`」，不是「稿子像不像 Knevo」，也不是双账户盯盘产品。

### 0.1 和相邻稿的分账

| 刀 | 谁拥有 | 本单角色 |
|---|---|---|
| **1. 点完菜空表先出锅** | `2026-08-24-market-watch-component-first` | 本单只把「绑定后填格权不归模型」写成跨题型不变量；盘面四袋不在这里重做 |
| **2. 用户一表态就对旧判断和现价** | **本单 P0** | `StancePack` + 扩大 `prior_recall` 触发面 |
| **3. 账户规则 ⋈ 现价的求值器** | 本单 P2 合同 | 先钉形状，**你点头要这个产品再写代码** |
| 续同一桌 | 本单 P0 芯片一条；选角表仍归 08-17 | 只加 `same_bind`，不重做 A/B/C/D |
| 记忆多了改跟踪 | 本单 P1 | 注入已有 `track_contract`，**不减工具授权** |
| 一门宪法 | 本单 P1 | 把已散落的纪律收成单一真本源清单，专项关不掉。**P0 收据形状稳定后再叠** |

### 0.2 v1.1 核稿改定（实施按本节，不是按 v1 的汇合处）

v1 三个阻断级洞。改的是椅子，不是「再写一句 prompt」。

| ID | v1 会让 P0 落不了地 | v1.1 |
|---|---|---|
| **洞 1 注入点** | 「`if owner_output is not None` 之前跑包」。`trade_advice` → `lane=research` → `canned is None` → `continuous_turn_adapter.handle()` → `handled` 则 `_complete_continuous_turn` **直接返回**。汇合处（今日约 `conversation_orchestrator.py` 里 `owner_output is not None`）对主路径不可达。与展望稿、`market_forecast` 同族。 | **写死**：`decide_turn` / `task_frame` 落定、`plan` span 发出之后，`deterministic_lane_answer` 与 `continuous_turn_adapter.handle()` **之前**跑 `run_stance_pack`。收据写入 `research_context`（经 `project_turn_decision` 之后的 control 附件，见 §7）。汇合处只许**读同一份对象**，禁止再跑一遍、禁止另造第二份 prior 散文。行号会漂，导航用符号：`handle()` 调用点之上。 |
| **洞 2 V 块双写** | StancePack 自写「你上次怎么说」，`ask.py` 的 V 块（`checkpoint_recall.recall_block_for_query`）再写一遍。两处清单必漂。 | **拍板 B**：StancePack 是 join 收据的唯一生产者；V 降为只读投影 `render(pack.prior_bag)`。装填 prior 只许调用 `checkpoint_recall` 现有 loader（`select_relevant_checkpoints` + `latest_verdicts`），不新开检索器。否决 A（把 V 升级成锁格产物）——那只是换名，Engine A 仍要一份挂在 `research_context` 上的收据，等于再造一个 StancePack。 |
| **洞 3 lane** | 「持仓 / 止损该不该减」未钉 chat vs research。 | **P0 硬触发**仅当 `decision.lane == "research"` **或** `question_type == "trade_advice"`。`chat` / `meta` / `clarify` / `knowledge` **不跑包**（fail closed 到不跑，不是模糊跑）。`trade_advice` 即使 lane 被写歪仍跑（OR 的右肢）。 |

「同一把椅子」的意图保留：两条执行路看见同一份收据。椅子要在 **Engine A 与 compose 分叉之前**，不是 A 已经早退之后。

## 1. 问题

Knevo 那张「9:25 竞价 → 双账户 → 9:35 扬杰分时」看起来像盯盘 skill 或用户工作流。逆向拆开是三明治：

| 你看见的 | 底层 |
|---|---|
| 竞价表 / 核心逻辑 / 账户建议 | skill **空表** |
| 账户 1 空手、扬杰、101.6 | **用户平面的行** |
| 指数和现价 | **Provider 现查** |
| 「看下一更新」 | **同一绑定、换时刻 T** |

本仓已经有半套：路由表、`memory_lookup` 只当先验、`trade_advice` 降级成条件 thesis、`track_contract`、`{label, full_prompt}` 芯片、`memory_gate`。卡住的不是「少一个竞价 skill」，是接合处：

1. `prior_recall` 只在用户写出「我之前 / 跟我上次」且题型 ∈ `{stock_deep_dive, theme_analysis, theme_track}` 时挂槽。`trade_advice`（「茅台该不该买」）不在集合里；「我持仓 / 目标价 101.6」不触发。
2. 槽挂了仍靠模型自选 `memory_lookup`。历史上模型会把预算砸给市场侧（`episode_factory` 注释里的 `run_20260808_102708`）。
3. 现价没有与先验成对的锁格。`trade_advice` 的 capabilities 含 `market_quote`，但 Engine A 可以一口不查。
4. 追问是「还想问别的角度」，不是「桌子不动、换参数」。
5. 跟踪契约只认题型 / 跟踪词面，不认「这标的已经有基线」。
6. v1 把包放在 `owner_output` 汇合处：Engine A 早退，主路径永远跑不到包（§0.2 洞 1）。
7. V 块已经在 ask 路径渲染「历史判断 × 裁决」。再写一份 prior 散文会漂（§0.2 洞 2）。

## 2. 基座原语（与金融无关）

实施时用这些词，不要用「Knevo 风格」「更个性化」。

| 原语 | 含义 | 本仓落点（目标） |
|---|---|---|
| **绑定** | 意图 → 手续 + 权限 + 深度。先定空表，再取数 | `route_table` + 已有 / 将有的 pack |
| **主键** | 提及 → 稳定实体 ID，否则 unresolved | 现有实体锚定；StancePack 必须带 `entity_id` 或 `unresolved` |
| **四平面** | 图谱 / 共享记忆 / 用户记忆 / Provider。错接口 = 空，fail closed | 纪律已有；本单把用户记忆和 Provider 收成一对袋 |
| **硬触发** | 条件 → 必跑工具，不是模型决定要不要查 | `StancePack` 在 `handle()` 前跑完并挂进 context |
| **填格** | 空表来自 skill / pack，值来自袋 | 公开稿锁格；模型只写残差 |
| **裁决** | prior ≠ 事实；矛盾分叉；Provider 终审 | `user_premise` + 现价袋；不让个人记忆改数 |
| **续绑定** | 同一手续、换 `as_of` / 标的 | followup `same_bind=true` |

四平面人话：地图、图书馆、笔记本、仪表盘。笔记本不能冒充仪表盘。

技术选型（为什么是接合，不是工作流解释器）：

| 方案 | 做法 | 追上什么 | 代价 |
|---|---|---|---|
| **A. 接合核（推荐）** | 用户行 × 现价行，按 skill 空表求值 | 个性化且口径可锁 | 要实体主键；空袋必须披露 |
| B. 用户自写工作流，下次调记忆 | 记忆当程序解释 | 极贴个人习惯 | 一次题污染记忆；无契约就编数；用户当产品经理 |
| C. 模型自由 ReAct | 自选工具自写 | 偶尔像 | 贵、不稳；盘面 / 买卖数字被改口径 |
| D. 每句问话一个 skill | 穷尽问句 | 单题体验 | 永远做不完 |

选 A。B 只作为 P2 账户表的**数据来源**（行），不是解释器。C/D 不当主路径。

## 3. 已核实事实（实施时不要再探）

行号会漂，导航用符号名。核稿日主仓工作树。

1. `_PRIOR_REFERENCE_RE` / `_PRIOR_RECALL_QUESTION_TYPES` 在 `episode_factory.py`。触发面是「回指自己的旧判断」，不是「当场甩持仓 / 目标价 / 买卖」。集合无 `trade_advice`。
2. `prior_recall` 的 `evidence_types` 已收窄为 `memory_lookup`，`grounding_mode=user_premise`。这是槽位设计，**不是**开口前必跑。
3. `route_table.trade_advice`：`lane=research`，`answer_owner=stock-deep-dive`，`needs_template=True`，capabilities = `memory, market_quote, graph, financials`。`task_frame` 默认槽是 `conditional_thesis` 等五格，无 `prior_recall`、无现价锁格。
4. `DETERMINISTIC_OWNER_TYPES` = `{external_market, quick_fact, dated_market_review}`。`trade_advice` 与 `market_watch` 都不在内。`market_watch` 换座位归相邻稿。
5. `track_contract.parse_track_intent`：`theme_track` 或跟踪词面。无「有基线则改跟踪」。08-13 稿 ❌ 不接「记忆条数 → 检索深度」。
6. `followups.py` 已有 `{label, full_prompt}`；类型是 evidence / counter / alternative / recheck / migration / gap。无 `same_bind`。08-17 选角稿未实施也不阻塞本单插一条确定性芯片。
7. `memory_gate.py`：无回检 provenance 的 `model_judgment` / `volatile_fact` 不得进 durable。不要改成 Knevo 式「先抽一批请你点接受」。
8. Knevo `[自述+实测]`：不派单 ≠ 不检索；spawn `task` = 范围 + 用户记忆线索 + 输出格式；子代理不自己落记忆。`[实测]` 盘中是快照不是监控。
9. `[实测]` 编排器主路径：`plan` span 之后 `deterministic_lane_answer`；若 `canned is None` 且 adapter 非空 → `project_turn_decision` → `continuous_turn_adapter.handle()`；`handled` 则 `_complete_continuous_turn` 返回。`owner_output is not None` 在更下游，Engine A 成功时走不到。
10. `[实测]` V 块：`checkpoint_recall.recall_block_for_query` 在 `ask.py` 于 `provider_enabled(..., "V")` 时渲染「可证伪点 × 最新裁决」。M 块是判断/纠偏正文，和 V 分工不同。`MarketResolver` 在 `checkpoint_resolvers.py`，管回检取数，不写第二份「你上次」。

## 4. 目标态

```
问句
  → decide_turn / task_frame 落定（plan span 已发出）
  → 解析实体（有则 ID，无则 unresolved）
  → should_run_stance_pack(decision, frame)?
        仅 lane=research 或 question_type=trade_advice
        且 (trade_advice 或 stance 词面命中)
        chat/meta/clarify/knowledge → 不跑（fail closed）
  → 真：run_stance_pack → 收据挂 research_context.stance_pack
        prior_bag  = checkpoint_recall loader 行 或 empty
        quote_bag  = 站立日现价                 或 empty
  → 分叉（两路读同一对象，禁止再跑）：
        Engine A：handle() 看见 control/research_context 上的包；残差研究照旧
        compose / owner 汇合处：只读副本；V 块 = render(pack.prior_bag)
  → 公开稿：价和「你上次」只出袋；动作只写条件
  → 芯片：2–4 条里必留 1 条 same_bind（本绑定可续时）
  → 记忆晋升：仍走 memory_gate，本单不改入口
```

`trade_advice` **不**加入 `DETERMINISTIC_OWNER_TYPES`。买卖题还要研究残差；换座位会把 thesis 也拒掉。这和盘面题相反——盘面四袋够用，买卖两袋不够用。

## 5. 范围

### 5.1 做（P0）

- 新增 `StancePack` 纯函数（services，禁止 import runtime）。
- 硬触发：§6.2。`trade_advice` 必跑；`lane=research` 且 stance 词面命中也跑；chat 等不跑。
- `prior_recall` 对 `trade_advice` 开放；stance 命中视为「引用了用户状态」，不要求「我之前」字面。
- **注入点写死在 `handle()` 之前**（§0.2 洞 1 / §7）。收据挂 `research_context.stance_pack`，必须传到 Engine A 与 compose 读口，禁止只写 telemetry。
- V 块改投影：有包则只 `render(pack.prior_bag)`，禁止再调 `recall_block_for_query` 自查（§6.1.1）。
- 公开稿交付闸：袋外价格删除或整句降级；先验不得写成市场事实。
- 确定性 `same_bind` 芯片一条，插在现有 followups 前面，总条数仍 2–4。

### 5.2 做（P1）

- `join_os.py`：把已有纪律收成编号清单，生成注入文本 + 出口 lint。专项 / 视角 / 阅读基线只能加，不能关。**等 P0 收据字段稳定后再叠**，本单不得与 P0 抢形状。
- `has_track_baseline(user, entity_ids)`：近窗有 durable 判断或上期跟踪基线 → 注入 `track_contract`。工具授权不减。

### 5.3 合同先钉、代码后开（P2）

- 个人账户 / 持仓 / 触发价表 + `evaluate(rule, quote, as_of)`。
- 没有你「要这个产品」的明示，**零实现**。合同写在 §6.6，避免以后被做成「用户工作流解释器」。

### 5.4 不做

- 不重做 market-watch 四袋、不改休市判定、不把 C1 原题改路由。
- 不重做 08-17 选角表；`same_bind` 不是新的 A/B/C/D。
- 不把 `trade_advice` 拒收 Engine A。
- 不按记忆条数减少 `memory_lookup` / `market_data` / `finance_query` 授权。
- 不做 9:25 定时推送、真监控、SSE 盯盘。
- 不解释用户 YAML / 散文工作流。
- 不接 Knevo 无溯源数值概率、不抄 gangtise。
- 不把 `skills/` 里未暴露的实时 skill 接入 agent（只读 + 无外呼红线）。
- 不改 `memory_gate` 变松，不建第二套 pending 盒。
- 不把 M 块（判断/纠偏正文）与 V 块合成第三篇「你上次」。P0 prior 只吃 V 的 loader。
- 不在 `owner_output` 汇合处再跑一遍包（那是读副本）。
- 不代修展望稿 / 盘面稿的同族注入点，只在本单写死椅子。
- 不在脏树改 runtime，不切生产。

## 6. 契约

### 6.1 `StancePack`

```python
@dataclass(frozen=True)
class PlaneBag:
    plane: Literal["checkpoint_verdict", "provider"]
    served_date: str | None          # ISO；empty 时必须 None
    entity_ids: tuple[str, ...]
    rows: tuple[dict[str, object], ...]
    status: Literal["hit", "empty", "unresolved"]
    gap: str                         # empty/unresolved 必填人话缺口

@dataclass(frozen=True)
class StancePack:
    standing_date: str               # 显式站立日或 cutoff
    stance_kinds: tuple[str, ...]    # holding / target / trade_intent / account
    prior_bag: PlaneBag              # plane="checkpoint_verdict"
    quote_bag: PlaneBag              # plane="provider"
    unresolved: tuple[str, ...]
```

规则：

- 显式站立日用 `trade_date = ?`，禁止 `<=` 回落邻日（与 market-watch 洞 2 同一失败形状）。
- `prior_bag.plane` 必须是 `checkpoint_verdict`。装填见 §6.1.1。共享框架、M 块判断正文不得进这只袋。
- `quote_bag.rows` 只许来自 `market_data` / 现有行情适配器。禁止模型补价。
- 任一袋 `empty` 合法。公开稿必须写缺口，不得把「没查到旧判断」写成「你没有旧判断所以现在可以买」。
- `unresolved` 实体：先验可按表面词召回 checkpoints；现价袋必须 `unresolved`，不许猜代码。
- 当轮问句里的持仓 / 目标价进 `stance_kinds` 与实体解析，**不**另写成第二篇「你上次」。

#### 6.1.1 「你上次怎么说」单一真本源（拍板 B）

不接受并存两份 prior 散文。

| 角色 | 唯一模块 | 禁止 |
|---|---|---|
| **装填** | `checkpoint_recall.select_relevant_checkpoints` + `latest_verdicts`（可抽 `recall_rows_for_query`，与现渲染同入参） | StancePack 自写检索；`user_memory.relevant_memory_records` 填 prior_bag |
| **join 收据** | `StancePack.prior_bag.rows` | 第二份「你上次」dict / markdown |
| **渲染** | 现有 `build_recall_block` / 等价 `render_recall_block(pack.prior_bag)` | `ask.py` 在 pack 已存在时再调 `recall_block_for_query` |

`recall_block_for_query` 拆成「行 → 渲染」两步（单一真本源且生成）：有 pack 走渲染函数；无 pack 的旧 compose 路径（未触发本包）可继续走包装函数，行为逐字节不变。

M 块（`memory_block_for_query` / 纠偏 / 经验卡）P0 **不动**。它是「观点正文 + 该信多少」，不是 V 的「逐条旧账 × 裁决」。不要把 M 并进 prior_bag，那会造第三篇。

否决 A：把 V「升级成锁格产物」而不做 StancePack，Engine A 仍没有可挂的 join 收据，最后还是要在 `research_context` 上复制一份。

### 6.2 硬触发

stance 词面（确定性，认不出就不当 stance，**fail closed 到「不跑包」**，不要模糊匹配出包）：

| `stance_kind` | 词面（实施时收成常量，测试锁） |
|---|---|
| `holding` | 持仓、我有、我的仓、重仓、底仓、空仓、空手、满仓 |
| `target` | 目标价、止损、止盈、成本价 |
| `trade_intent` | 该不该买、要不要买、加减仓、现在买、现在卖、止损吗 |
| `account` | 账户1、账户2、短线仓、活钱仓 |

触发（两道门，都 fail closed）：

```
eligible_lane =
    decision.lane == "research"
    or question_type == "trade_advice"

stance_or_trade =
    question_type == "trade_advice"
    or any(stance_kind 命中)

run = eligible_lane and stance_or_trade
```

| 问句 | lane | question_type | run |
|---|---|---|---|
| 扬杰科技我持仓，101.6 止损现在该不该减 | research | trade_advice 或个股 | True |
| 茅台现在该不该买 | research | trade_advice | True（无 stance 词面也跑） |
| 我持仓 101.6 止损该不该减 | **chat** | 非 trade_advice | **False** |
| 今天市场怎么样 | research | market_watch | False |
| 光刻胶是什么 | knowledge | concept / general | False |

`_PRIOR_RECALL_QUESTION_TYPES` 加上 `trade_advice`。`_references_prior_judgement` 在 stance 命中且 `eligible_lane` 时为真（即使没有「我之前」）。`memory_lookup` 未授权时：**不挂填不满的槽**（现有 factory 纪律保留）。prior 袋仍由 `checkpoint_recall` loader 装填（不经过模型选工具）。台账空 → empty，不编。不把「memory_lookup 未授权」写成必须 empty——V 装填不依赖该工具。

现价袋未授权：warning `stance_quote_capability_absent`，袋 empty，公开稿不得出现具体价。

### 6.3 填格与残差

`trade_advice` 公开稿锁格：

| 格 | 来源 | 模型可否改 |
|---|---|---|
| 你上次（旧账 × 裁决） | `prior_bag`；公开稿只许 V 投影 | 否；empty 写「无先验」 |
| 站立日现价 / 涨跌 | `quote_bag` | 否；empty 写缺口 |
| 条件化 thesis | 模型残差 | 可写条件，不可把 prior 写成已兑现 |
| 证伪条件 | 模型残差 | 必须可观察 |

已有「不输出确定性买卖结论」保留。残差复用现役「条件化 thesis」，不新增第二套开关。

出口闸（P0 最小）：公开稿里像价格的数字（实施用现有数字抽取，认不出的数删句，模式 7 fail closed）必须能在 `quote_bag.rows` 对上，或带「缺口 / 推断」标记。对不上 → 删句，不得改袋。

### 6.4 续绑定芯片

```python
@dataclass(frozen=True)
class BindContinuation:
    same_bind: Literal[True]
    bind_id: str                     # question_type + 主体 + standing_date 的稳定哈希
    delta: Literal["next_as_of", "same_as_of_refresh"]
    label: str                       # ≤20 字
    full_prompt: str                 # 用户口吻完整问句，必须带主体 + 上一站立日
```

何时占 1 席（2–4 的第一条）：

- 本轮跑了 `StancePack`，或
- `question_type ∈ {market_watch, theme_track, trade_advice}` 且主体可解析

`full_prompt` 公式（确定性，零模型）：

- `trade_advice` / stance：`按我刚才的{主体}条件，用最新价再对一次，只报相对 {standing_date} 的变化。`
- `theme_track`：`自 {standing_date} 之后，{主体}只报变化和四态对照，不要重跑全景。`
- `market_watch`：本条只在相邻稿的包收据存在时生成；文案 `同一天盘面用四袋再对一次，只报相对 {served_date} 的变化。` 包不存在则本条不上，避免空绑。

回声禁令沿 08-17：去空白后不得等于 `parent_followup_prompt`。点进子 run 仍是新问题，只禁回声。

不新增模型可见 `suggest_options` 工具。

### 6.5 有基线则跟踪（P1）

```
has_track_baseline =
    解析到 entity_id
    and 该 user 对该实体存在 durable 判断或上期 track 基线
    and 记录日 >= standing_date - 30d
    and 问句未命中「完整 / 写报告 / 全面 / 首次」
```

真 → 注入已有 `build_track_guidance_for_episode`（或 ask 路径的 legacy 版）。假 → 行为不变。

禁止：因基线条数 ≥ N 而拿掉任何 capability。单测必须锁这条负面。

基线源只读 `judgments` / 已有 track 注入用的 `[M]` 通道 / episode 侧 `memory_lookup` 已召回的 durable 行。不读 pending、不读 `model_judgment`。

### 6.6 账户求值（P2 合同，无明示零代码）

```python
@dataclass(frozen=True)
class AccountRule:
    account_id: str
    entity_id: str
    op: Literal["gt", "lt", "cross", "empty"]
    field: Literal["pct_chg", "last", "limit_status"]
    threshold: float | None
    action_if: Literal["wait", "watch", "reduce", "add"]  # 只出条件，不下注单

def evaluate(rule: AccountRule, quote_row: dict, as_of: str) -> Literal["wait", "condition_met", "gap"]:
    ...
```

规则是结构化行，不是自由文本程序。散文规则进用户记忆当 prior，**不**进求值器。求值器认不出的 `op`/`field` → `gap`，fail closed。

这不是 Knevo 监控。求值发生在用户提问或点 `same_bind` 的那一轮。

## 7. 落点

| 模块 | 职责 |
|---|---|
| `intelligence/services/stance_pack.py` **新建** | `should_run_stance_pack`、词面、pack 数据类、`run_stance_pack`、公开稿锁格检查 |
| `intelligence/services/checkpoint_recall.py` | 抽 `recall_rows_for_query`；`build_recall_block` 成为 `render(pack.prior_bag)` 的唯一渲染口。包装函数 `recall_block_for_query` 仅服务「无 pack」旧路径 |
| `intelligence/services/ask.py` | **有** `stance_pack` 时 V 只渲染袋，禁止再查台账。无 pack 行为不变 |
| `intelligence/services/episode_factory.py` | `trade_advice` 进 prior 集合；stance 且 eligible_lane 视为引用先验 |
| `intelligence/runtime/turn_control_core.py` | `TurnControlResult` 可加可选 `stance_pack: StancePack \| None = None`；默认 None，旧测试逐字节 |
| `intelligence/runtime/conversation_orchestrator.py` | `plan` span 之后、`deterministic_lane_answer` / `handle()` **之前**跑包；写入 control / `research_context`。`owner_output` 处只读 |
| `intelligence/runtime/continuous_turn_adapter.py` | `handle()` 把 `control.stance_pack` 传入 episode context；只写 telemetry 不算传到 |
| `intelligence/services/followups.py` | `same_bind` 芯片工厂；`TYPE_LABELS["continue"]="同一条件再对"` |
| `intelligence/services/join_os.py` **P1 新建** | 编号纪律清单 + `render_os_prompt` + lint |
| `intelligence/services/track_contract.py` | P1 只加 `has_track_baseline` 的调用方；纪律正文不动 |

行情读取复用现有 `market_data` / 盘面块适配器，不新开数据源。站立日解析与 market-watch 稿四个解析点对齐：有显式日就精确命中，没有才 `max(trade_date) <= cutoff`。本单买卖题默认隐式「今天」时，用 cutoff 当天精确命中；0 行 = empty，不回落。

`project_turn_decision` 今日没有 pack 槽。P0 允许在投影**之后** `replace(control, stance_pack=pack)`，或给 `TurnControlResult` 加可选字段。禁止另造平行 context 对象，避免 Engine A 与 compose 各拿一份。

## 8. 验收

解释器：干净树里的 `.venv-workbench/bin/python`（或主树 venv，cwd 决定加载哪份代码）。

### 8.1 P0 单测（必绿才可谈接线）

| # | 锁什么 |
|---|---|
| 1 | 「扬杰科技我持仓，101.6 止损现在该不该减」+ `lane=research` → stance_kinds 含 holding+target+trade_intent，`run is True` |
| 2 | 「茅台现在该不该买」且 `question_type=trade_advice` → 即使无 stance 词面、即使 lane 被写歪也 `run is True` |
| 3 | 「今天市场怎么样」→ `run is False` |
| 4 | 同 #1 问句但 `lane=chat` 且题型不是 `trade_advice` → `run is False`（不跑包） |
| 5 | checkpoints 0 行 → `prior_bag.status=empty`，rows 空，gap 非空；不得编一条「用户判断」 |
| 6 | 指定日库无行 → `quote_bag.status=empty`，`served_date is None`；禁止回落邻日价 |
| 7 | 公开稿含袋外价格 → lint 删除该句或整段降级 |
| 8 | 公开稿把 prior 写成「市场已经确认」类事实语气 → lint 记 `prior_promoted_to_fact` |
| 9 | `same_bind` 芯片：label≤20，`full_prompt` 含主体与站立日 |
| 10 | 授权里拿掉 `market_data` 不得减少其它研究 capability；只让 quote 袋 empty。拿掉 `memory_lookup` 不得减 capability，也不得阻止 V loader 装填 prior |
| 11 | 有 pack 时 `render(pack.prior_bag)` 与 `recall_block_for_query` 自查不得各写一篇；单测锁「ask 路径看见 pack 则 V 调用次数为 0 次自查」 |
| 12 | 编排器：`should_run` 为真时，`handle()` 入参 control 上必须已有 `stance_pack`（挂在 `research_context` / `TurnControlResult`）。只出现在 telemetry 的红 |

### 8.2 P0 接线后的最小 live（需你在场才跑）

冻结题：「宁德时代要不要止损」（路由已有例）。对照：包收据两袋都有 status；公开稿有条件、无「现在卖」。不把 Knevo 截图当过线样张。

### 8.3 P1

- 有 30 日内 durable 判断的标的 + 「XX 最近怎么样」（无「完整报告」）→ 注入跟踪契约。
- 同题把记忆条数从 1 增到 20，capabilities 集合不变。

## 9. 明确不抄 Knevo 的

| Knevo 做法 | 本仓 |
|---|---|
| 按记忆条数 2–3 / 3–4 / 5+ 工具 | 已划掉；P0#10 锁负面 |
| 答完自动抽一批 pending 等人点 | `memory_gate` 更严；不改松 |
| 情景树给 40%/20% 无溯源概率 | 继续禁数值概率 |
| 盘中推送监控 | 只做用户提问 / 点芯片的快照 |
| 用户安装一堆专项 skill | 不接破红线的 skill |
| 应用层改宪法 | P1 `join_os` 关不掉 |

已经够好、本单当不变量：缺数公式「缺 X → 仍可判 Y → 验证窗口 Z」（`episode_semantic_verifier._gap_answer`）；用户记忆 evidence_tier 只作先验；纠偏强制落账。

## 10. 分期

1. **P0 包 + 闸 + 芯片**：`stance_pack` 单测绿 → **`handle()` 前**接线 + V 改投影 → followups 插 `same_bind`。可单独合。
2. **P1 OS 清单 + 基线改跟踪**：P0 收据字段冻结后再叠，不改 P0 形状。
3. **P2 账户表**：另开 `feat/account-rule-eval`，等你明示。

合入仍走本机 `ruff` + 全量 pytest / frontend 叶子；本单不带红合。合并 `main` 等你确认。

台账号从 `R-20260824-25` 起（盘面 `-01`…`06`，knevo28 `-11`…`19`，outlook `-20`…`24`）：

| ID | 现象 | 类型 | 序 |
|---|---|---|---|
| `R-20260824-25` | StancePack 挂 compose，`trade_advice` 进 Engine A 早退，包是死代码 | `HARNESS_FIX` | P0 洞 1 |
| `R-20260824-26` | StancePack 与 V 块双写「你上次」，两份清单必漂 | `HARNESS_FIX` | P0 洞 2 |
| `R-20260824-27` | 持仓/止损题 lane 未钉，chat 路径误跑或漏跑包 | `HARNESS_FIX` | P0 洞 3 |

## 11. 工具沉淀

本单落地后回写 `~/harness-reference/KIT.md` 一条，不另建清单：

> **接合核**：用户旧账与现价是两只类型纯的袋，在 `handle()` 之前 join 并挂进 `research_context`；空袋合法；认不出的数 fail closed。失败形状 = 把笔记本写成仪表盘、记忆当工作流、或汇合处椅子对 Engine A 不可达。同义渲染只许一份投影。

盘面换座位仍记在 market-watch 稿（BUILD 模式 5：先查被腾空的椅子）。展望稿有同族注入点，各自改，不要把两刀收成一个零件名。

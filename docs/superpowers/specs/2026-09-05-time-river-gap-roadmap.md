# 时间长河缺口路线图：终局 → 仓内还差什么

> 日期：2026-09-05
> 状态：**能力级缺口清单，待用户审**。不是实施计划——每条缺口的切片、文件、分支走 writing-plans / workorder（INDEX 从 #26 起编）。不动代码。
> 上游：`2026-09-05-time-river-endstate-design.md`（终局；§13 审阅裁决）；BP v0.7 `docs/bp/2026-09-finance-agent-bp.md`（对外承诺：3 / 6 / 12 个月，§13.3）；`2026-08-13-memory-analog-lifecycle-design.md`（已实施六 slice）；`2026-08-19-user-framework-perspective-bootstrap-design.md`（私有层容器，待审）；`2026-09-04-methodology-backtest-structured-history-design.md` + INDEX #21 / #23 / #24 / #25。
> 读法：每条缺口 = 终局零件 → 仓内已有 [实测锚点] → 缺什么 → 验收判据（可机器核或可人核）→ 依赖 → 对外可说的话（做完前 / 做完后）。「[实测]」指本次在仓内 `rg` / `ls` 到的路径；未标者是从上游 spec 抄的。

---

## 0. 一句话

终局六轨（盘面 / 题材 / 舆论 / 资金 / 个股 / 判断；资金独立成轨见终局 §13.2 F9）的数据大多已在按日积累，方法论统计门、题材八阶段 + 时间线、D8 / D10 对标、记忆晋升门都在主干上；**还差 13 件**，按依赖分四层——L0 两项前置（题材词表统一、`market_stage` 归一）、L1 四项 V1 前必须（授课框架 v0、联立读取面、观察剧本 + 带读模式、合规硬门）、L2 五项 V2 前（舆论阶段轴、三维并置、环境剧本、胜率面板分列、私有层容器）、L3 抬上限杂项。**关键路径不是代码，是创始人把课纲写成母本（G-01）**：它是小白路径的前提、差分声明的基准、历史重放的规则集，agent 只能搭骨架不能替写。

---

## 1. 已有零件对照（不重做）

| 终局零件 | 仓内已有 [实测] | 状态 |
|---|---|---|
| 无前视 / 拒答 / 五段出门 / 独立判官 | 判官 + PIT + 11 道门禁 + 7,386 条测试（BP §10.1） | 保持 |
| 判断轨回检 | `intelligence/services/checkpoints.py`（可证伪点、回检、`calibrate` / `by_rule`）、用户态 `checkpoints.jsonl` / `corrections.jsonl`；83 个可证伪点、124 条纠偏 | 保持；要加对象分类（G-03 / G-09） |
| 方法论统计门 | `intelligence/services/methodology_backtest/`（labels / outcomes / 编译器 / 四态）、`scripts/methodology_backtest.py`；#21 P0–P1 五刀已合，三条种子规则 `not_distinguishable` | 保持；授课框架规则进同一条门（G-01） |
| 题材轴 | `intelligence/services/theme_lifecycle.py`（八阶段诊断）、`theme_lifecycle_timeline.py`（酝酿→…→回流）、`skills/theme-fermentation-tracer` | 两套词表待统一（G-04） |
| 盘面轴 / 市场对标 | 旁路库 12 个逐日标签、`intelligence/services/market_regime_analogs.py`（D10，只报后续事实）、按阶段基准率 `same_stage_days`（#21 第五刀） | `market_stage` 两套写法待归一（G-05） |
| 舆论轴（两轨） | `skills/opinion-cross/scripts/consensus_staging.py`（事实硬度 × 舆情广度）、观点事件库 | 无阶段词表（G-06） |
| 资金轨 | `fact_sector_stock_daily`（含资金流）、`fact_theme_flow_daily`、龙虎榜三表 `fact_dragon_tiger_daily / fact_dragon_seat_daily / fact_dragon_summary_daily`、`l2-moneyflow` 技能 | 有板块 / 题材 / 龙虎榜层；北向、两融、ETF 份额无表——按 `gap` 声明，不补编（G-02b） |
| 越用越懂 | `intelligence/services/memory_gate.py`、`user_memory.py`、退出机制、记忆只作先验（08-13 六 slice） | 保持；私有层容器待落（G-10） |
| 框架注入管线 | `intelligence/services/perspective_lab.py`（profile 机制；`user_framework` 第 110 行起仍是占位符）、`ask_synthesis.py` 注入点、连续引擎同源注入（08-19 §3.1） | 管线通，内容空——授课框架与私有层都往这里落（G-01 / G-10） |
| 每日复盘产物 | `intelligence/services/market_watch_pack.py`（指定日盘面组件包）、`exports/<date>-daily-agent.md`（含生命周期字段） | 带读模式挂在这里（G-03） |
| 已收 KOL 判读 | `docs/learning/reading-rules-inventory-2026-08-19.md`：25 条 A 类 + 4 条 B 类结构，用户已裁定全收 | 作差分参考，不是授课框架 |
| 历史重放 / 可证伪点带规则号 / 判官 token | INDEX #25 / #24 / #23，均待派 | 本清单不重写，只标依赖 |

---

## 2. 缺口清单

编号 G-01 … G-12；「验收」写成能被验收会话逐条打勾的句子。

### L0 前置（两项，不做后面全是沙上建塔）

#### G-04 题材生命周期两套词表统一

- **已有**：八阶段诊断与七段时间线两套口径；旁路库 `lifecycle_stage` 标签（#21 P1 剩余项：人工对照集）。
- **缺**：一张映射表 + 一套钦定词表进 `UBIQUITOUS_LANGUAGE.md`；`LABEL_VERSION` 升版；「引用必须标模块」的临时纪律退出。
- **验收**：(a) 词表里只剩一套题材阶段词，两模块输出经映射后同名；(b) 在人工对照集上出两模块一致率报告，不一致的样本逐条有归因；(c) `lifecycle_stage` 重建后，已有规则收据重跑要么无漂移、要么漂移有记录。
- **依赖**：#21 剩余项（同一工单收口，不另立——spec §13.2 F3）。
- **对外**：做完前「题材生命周期八阶段已上线」（v0.7 现状口径，不变）；做完后可说「题材轴单一词表、历史可重算」。

#### G-05 `market_stage` 两套写法归一（`LABEL_VERSION` v3）

- **已有**：INDEX #21 第五刀读数明说「归一前不能当结论用」。
- **缺**：归一映射、重建、收据重跑。
- **验收**：(a) 旁路库只剩一种 `market_stage` 写法；(b) 第五刀那两条「唯一证伪 / 唯一支持」规则重跑后结论有记录（保持或推翻都行，不能没跑）。
- **依赖**：无。**G-07 / G-08 / G-09 的阶段维度全部排在它后面**（F5）。
- **对外**：不进对外物料。

### L1 V1 前必须（BP §13.3「3 个月承诺」直接依赖）

#### G-01 授课框架 artifact v0（课纲 → 词表 → 判读规则 → 阈值队列）

- **已有**：结构语言词表（严格双红、MA5 峰谷确认日、指数完整周期、来源状态……已在 `UBIQUITOUS_LANGUAGE.md`）；`perspective_lab.py` 的 profile 机制；A / B / C 分类法（reading-rules-inventory §0）可直接复用。
- **缺**：(1) 母本 `docs/learning/teaching-framework/`（**人写**——沿 08-19 §5 红线，agent 只搭骨架、抽词表、对照数据字段，不撰写判读内容）：每条规则带课纲出处、A / B 分类、适用阶段；(2) `teaching_framework` profile 作共享层默认判读（`neutral` 逐字节不变——08-19 非目标）；(3) B 类数字阈值写成 `methodology_backtest` 规则 JSON 进回测队列；(4) 差分声明模板：KOL 25 条 A 类对授课框架逐条标「采纳 / 结构同阈值异 / 拒绝」（§13.1 第 1 题）。
- **验收**：(a) 母本有版本号，每条规则可追到课纲 / 直播的一处出处；(b) 复盘 run 新增 `teaching` 模式，默认开、可关，关掉后输出与当前逐字节一致；(c) ≥ N 条 A 类结构规则能贴到数据块渲染（N 由母本定，先不定数字）；(d) 每条含阈值的规则在旁路库有一张四态收据（含 `insufficient`）；(e) 对外物料在 (a)–(d) 全过之前只写「代码化中」。
- **依赖**：无代码依赖。**人力瓶颈是创始人写母本**，其余全部等它。
- **对外**：做完前「授课框架代码化中」；做完后「授课框架 vX：N 条规则，其中 M 条过统计门、K 条样本不足」——诚实读数照 v0.5 的写法。

#### G-02a 时间长河 as-of 联立读取面（V1 版：盘面 / 题材 / 判断三轨）

- **已有**：三轨数据——DuckDB facts + 旁路库标签、题材两模块、`checkpoints.jsonl`；PIT 纪律；快照分代。
- **缺**：一个纯数据查询面 `river.slice(as_of, entity) → {track: objects | gap}`；对象契约 `(as_of, entity, track, hardness, source_hash)`；缺轨返回 `gap` 而非空或推断；重算判据测试。
- **验收**：(a) 同一 `(as_of, entity)` 两次调用结果相同，且路径上无 LLM；(b) 缺轨返回 `gap{track, reason}`；(c) 契约测试：随机 30 个 `(as_of, theme)` 切片，每条对象有 `source_hash` 可回溯到主数据；(d) 索引层不持有任何轨的主数据副本，只持 `(as_of, entity, track, ref_hash)`（§13.2 F4）；(e) 三轨各有一个 provider 注册。
- **依赖**：G-04（题材轨阶段字段用统一词表；可先接旧词表 + 模块标记，G-04 后切换）。
- **对外**：做完前「六轨数据大多在，统一索引在做」；做完后「联立读取面上线（三轨）」。

**G-02 对象契约：两个时钟（用户 2026-09-05 问「记忆时间戳机制该怎么做」的答案，落在这里，不另起 spec）**

仓内其实已经有五种各自为政的时间戳写法 [实测]：板块宇宙快照 `status ∈ candidate/published/superseded/rejected`（`ops_sector_universe_snapshot_daily`）、证据边 `superseded / invalidated + superseded_by`（`evidence_providers.py`，门禁 `llm_fact_only_superseded_evidence`）、记忆生命周期 `produced → gated → invalidated` 与 `memory_status archived/rejected`（`memory_candidate_loop.py`、08-13）、PIT 边界 `updated_at ≤ D0`（fidelity replay `_pit_where`）与 `pit_grade ∈ {strict, trade_date_only}`（#25）、标签 `LABEL_VERSION`。缺的不是机制，是**一个契约把它们说成同一件事**。契约借双时态数据库与 Graphiti 的四时间戳语义（`valid_at / invalid_at / created_at / expired_at`），不引入它们的存储：

```text
RiverObject
  track            market | theme | opinion | capital | stock | judgment
  entity_id        指数 / 板块 / 题材 / 个股 / 用户
  object_type      label | stage | narrative_version | event | checkpoint | correction | observation_script | verdict …
  ref              指回主数据（表 + 主键 / 文件 + 行号 / 节点 uuid）；索引层不复制正文（F4）
  source_hash      可回溯
  hardness         L1–L4，或 n/a
  ── 时钟 1：有效时间（世界里什么时候为真）
  valid_from       = as_of 交易日；判断轨 = 判断所指的交易日，不是写下的日子
  valid_to         被后续事实终止的日期；现行为 null
  ── 时钟 2：记录时间（系统什么时候知道）
  recorded_at      入库 / 写下的时刻；历史行缺失时为 null → 该切片 pit_grade 降为 trade_date_only
  expired_at       被 superseded / invalidated 的时刻；现行为 null（不删，只标——和快照分代、证据边现在的做法一致）
  superseded_by    替代对象的 ref
  label_version / framework_version
```

读取只有一个函数、两个参数：`slice(as_of=T, knowledge_cutoff=C)` → 取 `valid_from ≤ T < valid_to` 且 `recorded_at ≤ C` 且 `(expired_at is null or expired_at > C)` 的对象。三种用法：

| 用法 | C 取什么 | 谁用 | 读数标记 |
|---|---|---|---|
| 当日带读 / 复盘 | T 日收盘后 | G-03 带读、每日复盘 | 无 |
| 回放 / 回测 / 校准 | 显式传入，且 ≤ T 日收盘 | #25 重放、`methodology_backtest`、`calibrate` | `pit_grade`：切片里所有对象都有 `recorded_at` 才是 `strict`，否则 `trade_date_only`，两档分开报、不出混合平均（#25 已定） |
| 事后复核（允许看到后来的修正） | now | 人工复核、证伪库报表 | `hindsight=true`，不得进任何胜率 |

判断轨专属规则：T+5 写的纠偏在重放 T 日时不可见（`recorded_at` 过滤，不是靶子挪走）；verdict 的 `valid_from` 是到期日（T+1 / T+3 / T+5），不是登记日；观察剧本 `recorded_at` 必须早于次日开盘，晚于则标 `late` 且不进校准；语义召回（记忆）跑在切片之后，同样受 `recorded_at ≤ C` 过滤，召回次数与命中率分表存（E-006）。

现有写法到契约的映射：快照 `published/superseded` → `expired_at / superseded_by`；证据边 `superseded / invalidated` → 同上，原因留在 `status`；`memory_status archived/rejected`、经验卡 `invalidated` → `expired_at`；`updated_at` PIT 边界 → `recorded_at`；`pit_grade` → 由 `recorded_at` 完备性派生；`LABEL_VERSION` → `label_version`。**不迁移主数据，只在索引层做映射视图。**

为什么不直接上 Graphiti / Zep：它是目前唯一原生双时态、能 as-of 查询的开源记忆框架（Mem0 只存时间戳不能重建过去状态，Letta 是上下文分页），四时间戳语义值得照抄；但它要跑 Neo4j / FalkorDB、每个 episode 走一次 LLM 抽取，面向的是「聊天 → 事实」的非结构化输入。我们六条轨已经是结构化、确定性可重算的对象（终局 §3「换模型能重算」的判据），再加一个 LLM 抽取的图就是第二套库（终局 §9 禁止），而且抽取不确定会毁掉重算判据。结论：**借语义，不借存储**。若日后判断轨的自由文本需要成图，再评估只对那一条轨接 Graphiti，现在不做。

- **验收（补）**：(f) `slice(T, C)` 对同一 `(T, C)` 幂等；(g) 任一对象缺 `recorded_at` 时整片 `pit_grade=trade_date_only` 且写进收据；(h) `hindsight=true` 的读数进不了 `calibrate`（测试）；(i) 五种现有状态字段各有一条到契约的映射测试。

#### G-03 观察剧本对象 + 带读模式（小白入口 MVP）

- **已有**：`checkpoints.py` 可证伪点 + 回检；#24 `rule_id` 设计；`market_watch_pack.py` + `exports/<date>-daily-agent.md`；`ask_synthesis.py` 注入点。
- **缺**：(1) `observation_script` 对象：`variables[]`、`upgrade_conditions[]`、`downgrade_or_abandon_conditions[]`、`scope ∈ {index, sector, theme}`、`framework_version`、`as_of`、登记后的 `checkpoint_id`；(2) 工作台带读模式（默认开、可关）：授课框架读当日切片 → 主矛盾 / 题材走到哪一段 / 盘面阶段 → 「明天你打算看什么」勾选或改写 → 登记；(3) 翻译器：「明天买什么 / 第二天的方向」→ 观察剧本 + 非投资建议声明；(4) 回检：判「变量是否按条件触发」，不判涨跌；(5) 判断轨对象分三类：用户决策 / agent 判断 / 观察剧本（§13.2 F2）。
- **验收**：(a) 硬门测试：含 `stock` 实体、方向词、时点词的观察剧本被拒并有错误码；(b) day-1：一个零历史的新用户在 T 日收盘后能拿到带读与至少一条可登记的观察剧本（§13.2 F1）；(c) 登记后 T+1 自动回检并写 verdict，verdict 带 `object_type=observation_script`；(d) 关掉带读模式 = 现有行为逐字节不变；(e) 「策略」「第二天的方向」两词在带读输出里被 lint 拒绝。
- **依赖**：G-01 v0（带读用什么框架读；G-01 未成前可用结构语言词表跑通管线，但不得对外称「授课框架带读」）；G-02a（切片来源）。
- **对外**：BP v0.7 §3.2 / §3.3 已写的带读 → 观察剧本；V1 观测项「≥ 半数用户登记过观察剧本或判断」靠它。

#### G-12a 合规硬门与用词 lint（横切，随 G-03 一起落）

- **缺**：观察剧本 scope 门；对外内容契约（`docs/marketing/*.yaml`）加禁词「第二天的方向」「策略」（单独出现）、加「不点名决策型 Agent 创业产品」；判官新增检查「不得出现概率数字」（承接 D8 / D10 纪律，供 G-07 / G-08 用）。
- **验收**：(a) `scripts/validate_marketing_contracts.py` 对禁词报错；(b) 判官测试用例：含概率数字的三维并置被驳回。
- **依赖**：无。

### L2 V2 前（BP「6 个月承诺」与三维对照）

#### G-02b 联立读取面补齐舆论 / 资金 / 个股三轨

- **缺**：舆论轨 provider（事件 + G-06 派生阶段）、资金轨 provider（板块 / 题材资金流、龙虎榜席位与汇总；北向 / 两融 / ETF 份额无表则整段 `gap`，不从别的轨推算）、个股轨 provider（公告 / 订单 / 财报 / 相对强度节点，**不是推荐名单**）。
- **验收**：G-02a (a)–(d) 对六轨成立；个股轨对象不含任何评级 / 方向字段；资金轨缺源时返回 `gap{track=capital, reason}` 而非零值。
- **依赖**：G-02a、G-06。

#### G-06 舆论生命周期阶段词表 + 派生器

- **已有**：`consensus_staging.py` 两轨；观点事件库；`wiki/sources` 7,036 份带日期的研报来源（覆盖密度可算）。
- **缺**：(1) 钦定 4–5 段词表（例：萌芽 → 扩散 → 拥挤 → 退热 / 证伪；「无人问津」需要负证据，先不入词表或标 `unverifiable`）；(2) 派生规则只从事件算：首次卖方覆盖日、覆盖密度斜率、观点版本 v1 概念 → v2 订单 → v3 兑现 / 证伪的切换、证伪事件；(3) 不落状态机、不新增抓取器（§13.1 第 2 题条件）。
- **验收**：(a) 每一段都有确定性派生规则且能在历史上重算；(b) 覆盖率报告：多少 `(theme, as_of)` 能出阶段、多少 `unverifiable`；(c) 与题材轴并排时能输出「错位」标记；(d) 词表进 `UBIQUITOUS_LANGUAGE.md`，与题材八阶段不混名。
- **依赖**：G-02a、G-04。
- **对外**：做完前「舆论轴有两条线，阶段词表在定」；做完后「三维对照上线」——G-07 一起。

#### G-07 三维对照渲染（一句并置 + 错位 + 历史复现）

- **已有**：三轴模块；D8 / D10「只报后续事实与复现次数」纪律。
- **缺**：渲染器：输入 as-of 切片 → 一句可读并置（「题材在升温验证，舆论还在萌芽，盘面已连续双红」）+ 错位标记 + 在河上找三维结构相似窗口，报复现次数与后续 5 / 10 / 20 日事实；进每日复盘与题材研究两个场景。
- **验收**：(a) 三轴缺一写缺口，不用另两轴补；(b) 输出可由切片重算；(c) 判官拒绝概率数字（G-12a）。
- **依赖**：G-02b、G-04、G-05、G-06。

#### G-09 胜率面板按 框架 × 环境 拆，与召回分列

- **已有**：`checkpoints.py` 的 `calibrate` / `by_rule`、`DEFAULT_CALIBRATION_MIN_N = 10`；#24 待派；E-006「召回次数 ≠ 胜率」。
- **缺**：维度 `framework_version × market_stage × object_type（用户决策 / agent 判断 / 观察剧本）× horizon`；N < 10 不出率；记忆召回次数放另一面板。
- **验收**：#24 验收 + 三类对象分列 + 任一格 N < 10 显示「样本不足」而非比率。
- **依赖**：#24、G-03、G-05。

#### G-10 私有层容器 `user_framework` 落地 + 差分声明（08-19 待审 → 实施）

- **已有**：08-19 设计；profile 机制；三条 2026-06-29 金融判读原则躺在 `corrections.jsonl` 第 20 名开外（08-19 §3.3 实测）。
- **缺**：canonical 根下 `user_framework` 画像；差分声明 schema（对授课框架与 KOL：采纳 / 结构同阈值异 / 拒绝）；把那三条原则迁进去；人写内容红线；私有规则只对本人回测的门。
- **验收**：08-19 §4 验收 + 「私有层规则的收据不进共享层」测试。
- **依赖**：G-01（差分的基准坐标系是授课框架）。
- **对外**：v0.7 §4.3「私有层容器已设计待落」→「已落」。

### L3 抬上限（BP「12 个月」与壁垒生成器）

#### G-08 环境剧本对象 + 流动性出口

- **已有**：`market_regime_analogs.py`（D10）、`market_stage` 谓词、`same_stage_days` 四态。
- **缺**：`environment_script` 对象：指数阶段 + 流动性指纹（成交额中枢、边际量、涨停热度、拥挤度）→ 同指纹历史窗口（几次、后续 5 / 10 / 20 日事实、共性、失效边界）→ 流动性出口（从资金轨读：板块 / 题材资金流向、龙虎榜席位集中度；有数报数、无数写 gap）→ 授课 / 私有框架在该环境下的四态。
- **验收**：(a) 对象可版本化并从旁路库重算；(b) 无概率数字；(c) 「策略」词 lint 拒绝，对象名与对外用词只用「环境剧本」；(d) 流动性出口字段允许 `gap`。
- **依赖**：G-05、G-02a、G-12a。
- **对外**：v0.7 §4.3「环境剧本对象与流动性出口待做」→「上线」。

#### G-11 历史重放接授课框架（#25 扩展）

- **已有**：#25 工单（`replay_engine.py`、`pit_grade ∈ {strict, trade_date_only}`、模型截止日表）。
- **缺**：车道 A 规则集加入授课框架规则；读数按 `pit_grade × framework_version` 分栏；对外表述红线不变（不得写「AI 已学会回顾历史」）。
- **依赖**：#25、G-01。

#### G-13 探索模式：agent 不加视角找数据间联系（终局 §13.2 F10）

- **已有**：#25 规则 schema 的 `provenance.kind=discovered` 与 `windows{discovery, validation}` 双窗收据（设计已定、待实施）；`methodology_backtest` 的 BH 多重检验校正与前后半段稳定性。
- **缺**：(1) 探索任务的产出契约——只能是候选规则 JSON（条件 = 六轨标签谓词 + 时间窗，结果 = 已有多窗口收益口径），不能是散文结论；(2) 探索窗与验证窗强制分离，验证窗读数才计入四态；(3) 探索次数进多重检验分母（跑了多少候选，报表要写）；(4) agent 对后续的判断一律落判断轨 `object_type=agent_judgment`，与用户判断同一条回检与 N ≥ 10 出率纪律。
- **验收**：(a) 探索产出不经统计门无法进入带读 / 复盘任何输出（测试）；(b) 收据带 `n_candidates_tried`；(c) 验证窗与探索窗零重叠（测试）；(d) 对外物料不出现「AI 发现了 X 规律」，除非该规则四态为 `supported` 且双窗收据在手。
- **依赖**：#25、G-02b、G-05。
- **对外**：做完前不提；做完后按 v0.5 的诚实写法——「AI 探索了 N 条候选，M 条过门，K 条证伪」。

#### G-12b 抬上限杂项

- 证伪库按阶段汇总报表（#21 剩余；v0.7 §4.3「待做」）。
- 判官 token 记账（#23；BP §13.3「6 个月内公开全口径成本」的硬依赖）。
- 带读评测题：冻结题集加「带读题」——给 as-of 切片，判官检查观察剧本合规 + 五段 + 缺口声明；进 28 题验收台的同一条路径。
- 知识库脱敏（Beta 硬门槛，BP §3.5 / §10.2 V2）。

---

## 3. 依赖图与顺序

```text
G-05 market_stage 归一 ──┬──> G-08 环境剧本 ──> (G-11 重放接框架)
                          ├──> G-09 胜率面板分列
                          └──> G-07 三维并置 <── G-06 舆论阶段轴 <── G-02b 六轨读取面
G-04 题材词表统一 ────────┴──> G-02a 三轨读取面 ──> G-03 观察剧本 + 带读 <── G-01 授课框架 v0（人写母本）
G-12a 合规门 / lint ──────────────────────────────> G-03 / G-07 / G-08
G-01 ─────────────────────────────────────────────> G-10 私有层差分 ──> G-11
```

对应 BP v0.7 §13.3 的承诺：

| 时点 | 必须落地 | 说明 |
|---|---|---|
| 3 个月（V1） | G-01 v0、G-04、G-02a、G-03、G-12a；#24、#23 | 没有 G-01 v0 就没有「授课框架带读」，V1 只能按 v0.6 口径跑高手路径——对外要如实降级 |
| 6 个月（V2） | G-05、G-02b、G-06、G-07、G-09；脱敏 | 三维对照与「两类分开记」的转化读数靠这些 |
| 12 个月（V3） | G-08、G-10、G-11、G-13、G-12b 其余 | 环境剧本与私有层是「认知复利」的产品面 |

---

## 4. 红线（全部沿用，不新增解释）

- 不新建记忆中台或第二套向量库；河是索引与契约，数据留在原轨（终局 §9、F4）。
- 观察剧本与共享层结论只到指数 / 板块 / 题材，不到个股名单；不写方向、时点、概率数字。
- 「策略」不单独出现；「第二天的方向」不进产品语言。
- 授课框架与私有层的**内容**由人写；agent 搭骨架、抽词表、跑回测、出收据。
- 对外物料不点名任何决策型 Agent 创业产品。
- 授课框架代码化、时间长河统一索引、舆论阶段词表三件落地前，对外一律写「在做」。

---

## 5. 待用户拍板

1. G-01 母本的形态：一份 markdown 母本 + 规则 JSON，还是直接在 `perspective_lab` profile 里写？（推荐前者——母本要给学员看得懂，profile 是派生物。）
2. G-03 带读模式默认开还是按新用户开（老用户默认关）？（推荐：新用户默认开、老用户默认关、随时切。）
3. G-06 舆论阶段词表要不要保留「无人问津」段？（推荐：v1 不保留，靠 `unverifiable` 表达负证据缺失。）
4. V1 若 G-01 v0 赶不上（母本没写完），Alpha 是推迟还是按 v0.6 口径先跑高手路径？（推荐后者，但 BP 对外承诺要同步降级。）

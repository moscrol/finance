# 设计：台阶轨迹 + 资格判断组件（视角判据组件化·第一批）

- 日期：2026-08-25
- 状态：**v1.1**（P0 已实施于 `feat/step-trajectory-qualification`：§7 #1–#11 离线全绿（36 测；全量 6446P/0F/12S + ruff 干净）；变异 A/B 实测必红（§3 #2 窗口、§3 #4 宽松轮——后者就此升实测）；live 一发过（§7.Live 三判据全中，收据 `~/.finance-runtime/step-trajectory-live-20260825/`）。台账 `R-20260825-09…11` pending，等自然样本）
- 来源：live ReAct 对照探针（`~/.finance-runtime/live-vs-workbench-20260825/`，answer + decisions + 同题 workbench `run_20260825_113538_938584` 事件流解剖）+ 战略结论「视角的全面性从『文本有多长』变成『有多少条判据变成了可执行组件』」（2026-08-25 用户确认执行）。
- 代码树：spec 落 `docs/step-trajectory-qualification`（基线 `gitea/main@3eb0abf3`）；实施另从 `gitea/main` 开干净树 `feat/step-trajectory-qualification`。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树改 runtime。**禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做、不抢合）：
  - `2026-08-25-substitute-observation-probe-design.md`（v1.2 三片已落。本单**完全复用**它踩出的路：signal → operator → `collect_prefetch_items` 消费 → `PrefetchItem` 带 E 号；其 §8 P2 `probe.menu` 预留原样有效，本单两件是该菜单未来的前两道菜，**不实施菜单**）
  - `2026-08-24-market-watch-component-first-design.md`（四袋不动。总量袋已锁 `market_stage`/`stage_day`/`volume_state`——资格盘只补它缺的均额比，P1 才进包）
  - `2026-08-24-workbench-quality-residual-ux-design.md`（D2/D4 管住本单：加的是**组件菜**，不是模型回合/加时；tier / 停机不碰）
  - `2026-08-24-outlook-live-weekly-pack-design.md`（market_forecast 的大盘级 5 日序列已由周包 `day_bag_details` 供给；本单不重复它，见 §1.2）
  - `~/.finance-runtime/four-arm-ready-20260823.md` 禁令「检索加法补个股」：本单不违反——两件都只产**大盘行/板块行**，不产个股名单。

## 0. 一句话

同题对照（live 臂 vs workbench `run_20260825_113538`）钉死：workbench 供数不缺（8 能力、4 调用全成功），缺的是两口锅——**大盘量能资格盘**（站立日总量 vs 20 日均额，SPT 状态机第一判据）和**板块近 5 日量能台阶**（「放量反弹失败→台阶回落」「跌但边际量转正」这类形状的原料）。live 臂步 0 / 步 2 靠手写 SQL 拿到了，workbench 的开口预取只送了 1 件（替补池）。本单把这两口锅收成**注册组件**：词面信号触发、operator 编译、开口预取消费、观察值注册——判断力留给模型，执行全是注册查询。

**判别变量**（验收只锁这一条）：冻结题「站在spt视角下，科技和医药板块接下来的走势怎么看，需要观察哪些个股的反馈」在模型开口之前，预取必须已含：①资格盘（站立日总量、20 日均额、比值，带观察值）；②≥1 个与题目相关板块的近 5 日台阶（或对未锚定 subject 的如实声明）。全部 `served` 窗口 ≤ 站立日、带收据。不是「多调一次工具」，不是「稿子更长」，不是「像 ReAct」。

人话：厨师开工前，案台上除了四袋主料，还要摆好两样底料——今天大盘有没有「资格」谈主升（总量对均额），和这几个板块最近五天量能走的是上台阶还是下台阶。以前这两样要厨师自己跑地窖现挖，跑一趟烧掉一个回合；现在开门就在案上。

## 1. 范围

### 1.1 做

- 新信号 `SIGNAL_STEP_TRAJECTORY`：词面 =（板块|题材|主线|行业）×（走势|接下来|后续|趋势|怎么看|怎么走|台阶|量能），market_watch 路由题**不发**（与替补信号同款排除，包路径 P1 另接）。
- 新 operator 两枚：`OPERATOR_VOLUME_QUALIFICATION = "market.volume_qualification"`、`OPERATOR_STEP_TRAJECTORY = "market.volume_step_trajectory"`。一个信号发两枚——SPT 铁律「先定资格再谈板块」（画像 `reasoning_patterns[0]`），台阶没有资格盘垫底就没法读。
- FactSlot：`volume_qualification` / `volume_step_trajectory`（`required=False`，经 `episode_factory` extras 进契约，与 `substitute_observation` 同链路）。
- **资格盘**：公共接缝 `market_watch_pack.volume_qualification_receipt(con, standing)`（P1 进包免改）→ 站立日 `fact_market_daily` 行（总量/阶段/量能状态）+ 20 日均额（**窗口=截至站立日最近 20 个交易日、含当日**，§3 #2 实测冻结）+ 比值一位小数。渲染用中文「20 日均额」，不写拉丁「MA20」（§3 #6 词面纪律）。
- **台阶件**：`asof_prefetch._step_trajectory_items`。板块池 = subject 解析（fail closed 梯子，§6.2）∪ 近 20 个交易日主线登记题材解析（复用替补探针的包含+额度 top1，抽共享 helper），**cap 6 个板块**。每板块近 5 个交易日逐日行，**复用** `format_sector_timeline` / `sector_timeline_observations`（口径分歧防护、双红戳免费继承），窗口改为 `_prior_trade_dates(con, standing, 5)`。
- 观察值注册：两件都产 `StructuredObservation`（资格盘 metric：`total_amount` / `amount_ma20` / `amount_vs_ma20_pct`，subject=全市场；台阶件沿用时间轴三 metric）。数字进注册表 → 残差引用不被判编造。
- 异常一律回空 tuple——预取不得杀 episode 开口（替补件同款）。

### 1.2 不做

- **不加模型回合、不升 tier、不改 50 秒预算**——quality 稿 §5「座位不对加时是给错误工作流加薪」原样有效。差距是缺锅不是缺火。
- **不做 bounded requery（P2）**——`probe.menu` 预留 id 原样躺着，须开关板原子 + 正负控消融才动；本单只把菜做出来。
- **不建家族别名硬编码表**（科技→[半导体…]）——`resolve_theme_alias` 的「不另建硬编码别名表」纪律沿用；「AI算力/半导体属于科技系」的语义归类**留给模型**，主线池保证原料在桌上（§4-D）。
- **不用宽松匹配解析 subject**——`resolve_query_themes` 锚定宽松轮会把「科技」臆配成「量子科技」（§3 #4），P0 梯子到精确名与主线登记为止，解析不到就声明未锚定。
- 不动四袋查询 / 站立日纪律 / `should_stop`；不改替补探针行为（抽 helper 后既有测试必须逐字节同绿）。
- 不动 market_forecast 周包（大盘级 5 日序列它已有；给它补均额基准是 P1-b）。
- 不改删句闸的词面与 grid 判定；不注册「110–120%」阈值带（那是画像判断倾向，P1-c 接 reading-rules 方向另立单）。
- 不产个股行（four-arm-ready 禁令）；替补池继续管个股观察。
- 不改 8792 / 8796 生产配置；live 验证走 sidecar 新目录。

## 2. 术语

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **资格盘** | 站立日总量 vs 20 日均额的事实组（含比值），SPT 量能状态机的输入 | 状态机判语本身（「共建期/无主升资格」是模型拿着画像规则写的残差） |
| **台阶** | 单板块近 5 个交易日 pct/边际量/成交额逐日序列 | 30 日发酵时间轴（发酵题专属，窗口/触发都不同） |
| **解析梯** | subject → 板块口径的 fail-closed 阶梯：精确板块名 → 近 20 日主线题材名 → 声明未锚定 | 宽松/子串匹配（会臆配量子科技） |
| **主线池** | 近 20 个交易日 `fact_mainline_theme_daily` 登记题材按天数倒序 top6，逐个解析成板块 | 当日主线袋（那是四袋，单日） |
| **观察值注册** | `StructuredObservation` 进证据账本，语义验证器认这个数 | prompt 里出现过 |

## 3. 已核实事实（2026-08-25 对 `gitea/main@3eb0abf3` + 生产库实测，实施时不要再探一遍）

1. **[实测]** `run_20260825_113538_938584`（8792=`e577430d`，同题）：`question_type=general_finance_qa`、`task_frame.subject=科技、医药`（#383 生效）；契约 12 格含 `substitute_observation`（operator→slot→契约链路通）；8 能力、standard 档、3 模型回合、4 工具调用；**prefetch 事件 count=1**（仅替补池）。台阶/资格皆不在桌上。
2. **[实测]** MA20 口径：`2026-08-24` 总量 20072.28；截至站立日**含当日** 20 个交易日均额=**23110.8**（比值 86.9%，正对上 live 探针的「23111 亿的 87%」）；**不含当日**=23145.4，对不上。窗口冻结为含当日。
3. **[实测]** 名字空间：`%科技%` 在 08-24 只命中「量子科技」（762.67 亿）——不是题目的科技系；「存储」无行（真名「存储芯片」，diff_ratio=11.52 即 live 答案的「存储 +11.52%」）；「医药」既是精确板块名（1179.81 亿）也是主线题材名。近 20 日主线登记：医药 15 / 有色金属 14 / 消费零售 13 / **AI算力 12 / 半导体 10 / AI应用 8**——科技系在库内的真名就是这些登记题材，live 臂步 1 正是这样定位的。「科技」从未出现在主线题材名中。
4. **[实测，2026-08-25 变异 B 升格]** `resolve_query_themes` 的锚定宽松轮（`_anchored_fragment`，为「地产→房地产」设计）同机制会把「科技」配到「量子科技」；`resolve_theme_alias` 走它 limit=1。故解析梯 P0 不含宽松轮。实测：解析梯接入无条件包含解析（模拟宽松轮）→ `test_family_word_fails_closed_not_quantum_tech` 必红，量子科技确实上桌；live 重放同判据全中（无量子科技、未锚定声明在桌）。
5. **[实测]** 可复用件：`format_sector_timeline` / `sector_timeline_observations`（含同日口径分歧防护，run_20260821_114642 事故注释在案）、`_prior_trade_dates`、替补探针的题材→板块包含解析 SQL（`_run_substitute_probe` 内，抽 helper 共享）。`load_theme_daily_rows` 按名取全部行、窗口由 start/end 切。
6. **[实测]** 删句闸（`outlook_delivery_gate.py`）：watch 闸只对 `market_watch` 生效，词面 `MA\s*20` / `110–120%` 带 / 旗型蓄能，**grid（包渲染/证据）里出现同词面则视为已注册不删**；`MA\s*20` 匹配不到中文「20 日均额」。outlook 闸只对 `market_forecast` 生效。P0 路径（general_finance_qa）两闸都不适用，但渲染词面按中文写，为 P1 进包留一致性。
7. **[实测]** `episode_factory.py:335`：`program.required_fact_slots` → 契约 required_outputs extras。新 slot 自动进契约，无需另接。
8. **[实测]** 周包 `day_bag_details`：market_forecast 已供大盘级逐日四袋 + 量能序列（无均额比、无板块级台阶）。资格盘/台阶件与它不重叠。
9. **[实测]** 台账 `R-20260825-09/-10/-11` 经 rg 全库（main + `fwp-wt-*`）未被占用。
10. **[实测]** 替补件的 E 号纪律先例：`PrefetchItem.to_evidence()` 自动 `content_hash`，`format_opening_prefetch_message` 与终局注册表同号。新件按构造成立，不另接。
11. **[已冻结（实施）]** `fact_mainline_theme_daily` 近 20 交易日聚合下界 = `_prior_trade_dates(con, standing, 20)` 最早日（空窗回退台阶窗起点）；`DefinitionReceipt` 未发——P0 无读取方，unread-fields 门禁先例（替补单 probe_id 教训）。

## 4. 方案对比

| 方案 | 做法 | 得 | 失 / 判 |
|---|---|---|---|
| **A. 注册组件预取（采用）** | signal → operator → `collect_prefetch_items`，复用时间轴格式化器与探针解析 | 开口即供数；观察值注册；查询可复现；零模型预算变化 | 只救注册形状（诚实，可接受——替补单同判） |
| B. 加回合 / 升 tier 让模型自己查 | 放宽预算 | 可能覆盖未知形状 | quality 稿已证「给错误工作流加薪」；查询不可复现；五臂实测 8796 加长稿带出未注册阈值。否决 |
| C. bounded requery 菜单 | 模型点菜 | ReAct 判断力 | P2 预留 `probe.menu`（开关板原子 + 消融），本单产出正是其菜单原料；不与 P0 绑。 |
| D. 家族别名硬编码表 | 科技→[半导体, AI算力…] | 家族映射全 | 供应商换名单即腐烂（CLAUDE.md 在案）；违反「不另建硬编码别名表」纪律；语义归类模型本来就擅长——主线池把原料端上桌即可。否决 |
| E. `dim_sector.sw_l1` 维度映射 | 家族→申万一级→板块 | 结构化 | **[实测]** `sw_l1` 空值 288 个（过半），fail closed 会漏主力板块。否决 |

## 5. 目标态

```
问句（题材前瞻/观察题，非 market_watch 路由）
  → surface_research_signals：SIGNAL_STEP_TRAJECTORY
  → compile_research_program：+ OPERATOR_VOLUME_QUALIFICATION + OPERATOR_STEP_TRAJECTORY
  → collect_prefetch_items（standing = 库内 max(trade_date) ≤ as_of）：
      资格盘：market_watch_pack.volume_qualification_receipt(con, standing)
        → 「大盘量能资格盘」1 件：总量/20日均额(含当日20交易日)/比值/阶段/量能状态 + 3 观察值
      台阶件：_step_trajectory_items(con, question, subject, standing)
        → 池 = subject 解析梯 ∪ 主线池（cap 6，去重，发酵锚定板块让位）
        → 逐板块「<板块> 近5日量能台阶」：format_sector_timeline(5日窗) + 观察值
        → 未锚定 subject → 一行如实声明（不臆配）
  → 开口消息带 E 号 → 模型写残差（资格判语/家族归类/台阶解读是模型拿画像规则做的事）
```

## 6. 契约

### 6.1 站立日与窗口

1. standing = `max(trade_date) <= as_of`（`fact_market_daily`），与替补件同源；两件所有查询窗口终点 = standing，**禁止越过问句截止日**。
2. 资格盘窗口 = 截至 standing **含当日**最近 20 个交易日（§3 #2）。窗口实有行数 N<20 时如实标注「N=…」并按实有窗口计算，**禁止**仍标 20 日口径；N=0 或 standing 为 None → 不产件。
3. 台阶窗口 = `_prior_trade_dates(con, standing, 5)`，首尾即 start/end；板块该窗无行 → 该板块声明「无行」，不查邻日、不放宽。

### 6.2 解析梯（fail closed）

subject 按 `、，,` 切 token，逐 token：

1. token 精确等于某 `sector_name` 且窗口内有行 → hit；
2. token 精确等于近 20 交易日主线登记题材名 → 复用替补探针「包含 + 当日额度 top1」解析 → hit / no_match；
3. 其余 → 该 token 一行「『<token>』未锚定到板块口径；近 20 日主线登记板块台阶已另行上桌」。**禁止宽松轮**（量子科技陷阱，§3 #4）。

主线池：近 20 交易日登记题材按天数倒序 top6 → 逐个走第 2 级解析 → 去重并入。总 cap 6 板块（subject 命中优先占位）；`SIGNAL_FERMENTATION` 同发时，发酵时间轴已锚定的板块从池中让位（不双份）。

### 6.3 渲染与注册

4. 限定语先行：每件 detail 首部带站立日 + 窗口 + 口径（时间轴格式化器已自带口径行）。资格盘措辞用「20 日均额」，不写「MA20」。
5. 观察值与渲染同源同窗（`sector_timeline_observations` 取数/格式化分离纪律沿用）；同日口径分歧沿用「不产观察值 + 显式分歧声明」。
6. E 号按 `content_hash` 构造成立（§3 #10），认不出 hash 不发号。
7. 判官对照：预取观察值数字被残差引用时，语义验证器不得判编造；台阶行/资格行不得被无格闸当未注册阈值误杀（替补单 §6 #6 同族，实施加对照测试）。

### 6.4 预算与失败

8. 两件全部在预取阶段完成，不占模型回合、不占工具调用配额；单件查询失败回空，不得影响其余件与 episode 开口。
9. 库 locked / 打不开：不产件（预取静默），不造第三态文案——开口消息本就允许无预取。

## 7. 验收（离线红→绿 + 变异；live 新目录）

夹具自带 in-memory DuckDB：`fact_market_daily` ≥21 行、`fact_sector_daily`（含「医药」「半导体」「量子科技」行）、`fact_mainline_theme_daily`（含 AI算力/半导体登记）。

| # | 夹具 | 必须 |
|---|---|---|
| 1 | 21 行总量已知，站立日=尾行 | 资格盘 hit；均额=手算含当日 20 行值；比值一位小数；3 观察值；**变异**：窗口改「不含当日」→ 红（真库两值 23110.8 vs 23145.4 可区分，夹具同构造） |
| 2 | 总量表仅 12 行 | detail 带「N=12」；无 20 日口径字样 |
| 3 | `as_of` 早于库尖 | standing=`max(trade_date)<=as_of`；两件窗口终点=standing；**变异**：`<=` 改 `<` 或去截断 → 红 |
| 4 | subject=「医药」，板块表有精确「医药」行 | 医药台阶 hit：5 日逐行 + 双红戳 + 观察值 |
| 5 | subject=「科技」，板块表含「量子科技」 | **不得**产量子科技台阶；「科技」未锚定行出现；主线池「半导体」正常上桌；**变异**：梯子接入宽松轮 → 红 |
| 6 | 主线 6 题材 + subject 命中 | 去重后 ≤6 件；第 7 板块不渲染不入收据 |
| 7 | 同板块同日两行不同值 | 沿用分歧声明；该日无观察值（回归锁，run_20260821 形状） |
| 8 | 发酵词面同发 | 发酵锚定板块不出现在台阶池 |
| 9 | market_watch 路由题 | 信号不发、两件不产；**变异**：去掉路由排除 → 红 |
| 10 | 库打不开 | 两件回空；`collect_prefetch_items` 不抛 |
| 11 | 判官对照 | 残差句引用资格盘比值/台阶数字 → 语义验证器不判编造、无格闸不误杀 |

### Live（实施收尾，sidecar 端口，新目录）

- 冻结题同题重放：开口预取 ≥3 件（替补池 + 资格盘 + ≥1 台阶）；公开稿出现总量/均额比引用或如实缺口；「科技」无臆配板块。对照物 `~/.finance-runtime/live-vs-workbench-20260825/`，不覆盖。台账不标 confirmed（等自然样本）。
- **结果（2026-08-25，一发过）**：sidecar 8820（worktree 脏码 `be67eb27+`，launcher 同源生产环境，presenter 默认档），冻结题 `run_20260825_143634_143023`（75s completed）。开口预取 **7 件** E1–E7：替补池 + 资格盘 + 4 板块台阶（医药/医药医疗/有色/半导体，subject 梯 1 命中 + 主线池）+「科技」未锚定声明，全部 `source_date=2026-08-24`=站立日、E 号与证据账本同号。公开稿引用「大盘 08-24 成交 20072 亿，仅为 20 日均额 23111 亿的 86.9%」（与 §3 #2 库内值逐位一致）、中文口径无 MA20、全稿无量子科技、以主线池半导体作科技代表（语义归类留给模型的设计意图兑现）。收据 `~/.finance-runtime/step-trajectory-live-20260825/`（sidecar 起停脚本 + replay 脚本 + verdict.json + 原生 trace/episode 副本）。

## 8. P1 / P2（本单不实施，只钉方向）

- **P1-a** market_watch 包接入：总量袋渲染追加均额比行（`volume_qualification_receipt` 已是公共接缝）——包渲染进 watch 闸 grid，均额比词面即自动注册；台阶作包探针（主线池版）。行为变更单独验收。
- **P1-b** outlook 周包逐日资格盘（`tape_summary` 已有序列，只差均额基准）。
- **P1-c** 画像阈值收据：把「110–120%」这类判断倾向阈值以结构化规则收据进 grid——依赖 perspective_lab 结构化规则字段（reading-rules-baseline 方向），另立单。
- **P2** `probe.menu` bounded requery：本单两件 + 替补探针 = 菜单前三道菜；开关板原子 + 正负控消融后才入 default 盒（替补单 §8 预留原文有效）。

## 9. 落点

| 文件 | 职责 | 序 |
|---|---|---|
| Modify: `intelligence/services/query_understanding.py` | `SIGNAL_STEP_TRAJECTORY` + 两词族 + `surface_research_signals` 分支（market_watch 排除注释与替补同款） | P0 |
| Modify: `intelligence/services/research_contract.py` | 两 operator 常量 + `_SLOT_BY_OPERATOR` 两 slot + `compile_research_program` 分支（recipe：`timeseries`/`sector_daily`/strict_date；不发 DefinitionReceipt，§3 #11） | P0 |
| Modify: `intelligence/services/market_watch_pack.py` | `volume_qualification_receipt(con, standing)` 公共接缝；抽 `_resolve_theme_sector` helper（替补探针行为逐字节不变，既有测试锁） | P0 |
| Modify: `intelligence/services/asof_prefetch.py` | `_volume_qualification_items` + `_step_trajectory_items`（解析梯 + 主线池 + 复用 `format_sector_timeline`/observations）+ `collect_prefetch_items` 两支消费 | P0 |
| Test: `intelligence/tests/test_step_trajectory_qualification_prefetch.py` | §7 #1–#10 全部 + 变异 | P0 |
| Test: 判官侧对照 | §7 #11 | P0 |
| 收尾: `docs/prediction-ledger.md` | `R-20260825-09…11` | 收尾 |

## 10. 账本

| ID | 现象 | 类型 | 序 | 验证 |
|---|---|---|---|---|
| `R-20260825-09` | 题材前瞻题开口预取无板块 5 日台阶——「放量反弹失败→台阶回落」「跌但边际转正」形状对模型不可见（live 对照实锤：同题预取仅 1 件） | `HARNESS_FIX` | P0 | §7 #4–#6 / live |
| `R-20260825-10` | 开口预取无大盘资格盘，SPT 第一判据（总量 vs 20 日均额）无供数，残差引用比值面临未注册误杀 | `HARNESS_FIX` | P0 | §7 #1–#3 / #11 |
| `R-20260825-11` | 家族词 subject 经宽松匹配臆配词面近邻板块（科技→量子科技），错数据自信上桌 | `HARNESS_FIX` | P0 | §7 #5 变异 |

## 11. 实施顺序

1. 干净树 `feat/step-trajectory-qualification`；第 0 步冻结：`resolve_query_themes('科技')` 实测（§3 #4 升实测）、主线聚合下界口径（§3 #11）。
2. §7 #1 红 → 资格盘接缝 + 预取消费 → 绿；#2/#3 逐条。
3. §7 #5 红 → 解析梯（先写变异确认宽松轮必红）→ #4/#6/#8 逐条绿。
4. #7 回归锁、#9 路由排除、#10 异常回空。
5. 判官对照 #11。
6. live 一发（§7.Live，sidecar 新目录）。
7. pathspec 提交；合 main 等用户确认。spec 修订随代码同 PR。

## 12. 自检

- 无 TBD；两处待冻结项都钉在第 0 步且不阻塞设计判断。
- 判别变量 = 「开口前两件在桌上且带收据」，不是措辞、不是长度。
- 与 quality 稿分工：组件菜 ✓、模型预算 ✗；与 four-arm 禁令：无个股行 ✓；与替补单：同链路复用、探针行为不变 ✓。
- fail closed 三处：解析梯无宽松轮、N<20 如实标注、异常回空。
- 家族语义归类留给模型 = 「圈小而稳」——圈住确定性取数，不圈语义判断。
- P1/P2 各自带独立验收，未混入 P0。

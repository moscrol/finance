# 设计：空袋替补观察探针（残差自适应补查·第一片）

- 日期：2026-08-25
- 状态：Draft v1（未实施）
- 来源：五臂对照 live-toolkit 决策记录（`~/.finance-runtime/trace-diff-spt-tech-med-monday-20260823/live-toolkit/decisions.json`）+ 五臂报告结论 2（同目录 `one-page-report.md`）+ `gitea/main@760bf79b` 代码核验（2026-08-25 凌晨，快照 `~/.finance-runtime/finance-workspace-760bf79bea64`）。
- 代码树：从 `gitea/main` 开干净树 `feat/substitute-observation-probe`。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树改 runtime（本稿允许 pathspec 落在脏树）。**禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做、不抢合）：
  - `2026-08-24-market-watch-component-first-design.md`（四袋已落地；本单在它的缺口句**之后**长出替补池，不改四袋、不改站立日纪律）
  - `2026-08-24-workbench-quality-residual-ux-design.md`（D2/D4 管住本单：探针是**组件加菜**，不是模型加时；不碰 tier / 停机条件）
  - `2026-08-24-outlook-live-weekly-pack-design.md`（五日包复用 `run_market_watch_pack`；本单 P0 不改它，P1 才接）
  - `2026-08-22-capability-switchboard-design.md`（P2「模型点菜」必须做成开关板原子，本单只预留 id，不实施）
  - `~/.finance-runtime/four-arm-ready-20260823.md` 禁令「检索加法补个股」：**本单不违反**——探针只读主库 `fact_*` 行并带收据，禁止从 KB/检索文本抄名单（见 §1.2）。

## 0. 一句话

主线题材当日无严格双红时，现状（main tip）只写一句缺口：「在榜不构成加量证据」。五臂对照里现场写臂多做了一步——**改查成交额最大的对应板块前 2 只个股，标成出清/分歧观察，不当机会**——医药观察池因此没有交白卷。这一步的触发条件和查询都是规则可表达的。本单把它收成**注册探针**：触发是包状态谓词，查询是同库同站立日的确定性 SQL，标签排在名单之前，模型仍只写残差。

**判别变量**（验收只锁这一条）：A1 形状夹具上「主线题材无双红匹配」时，公开稿在缺口句之后出现替补池——带「出清/分歧观察」标签、带个股代码、`served_date` 等于站立日；标签先于名单出现；无一行来自邻日、检索文本或 KB。不是「多调一次工具」，不是「稿子更长」，不是「像现场写」。

人话：厨师报「这道菜没货」之后，后厨按预案端上一盘替代菜并贴好「这是替代」的签，而不是让点菜的人对着空盘子，也不是放厨师出去自由采购。

## 1. 范围

### 1.1 做

- 新增探针收据类型与一条 P0 探针 `substitute_observation`：主线袋 hit、某主线题材与双红名单无文本包含匹配（**复用** `mainline_dual_red_gap` 的对齐逻辑，不另造第二套匹配）→ 对每个未匹配题材：该站立日 `fact_sector_daily` 中名称包含该题材的板块按 `amount` 取 top1 → 该板块该日 `fact_sector_stock_daily` 按成交额取 top2 个股（带代码）。
- 探针结果挂在 `MarketWatchPack` 上（新字段 `probes`，默认空 tuple），`render()` 在缺口句之后渲染，`merge_into_public_answer` 免费获得。
- `run_market_watch_pack` 加参数 `substitute_probes: bool = False`（**默认关**）；只有 `ask.bind_market_watch_pack` 传 `True`。`weekly_watch_pack` 行为一字不变（P1 另议）。
- 上限写死：每次最多 2 个题材、每题材 1 板块、每板块 2 只个股；探针查询与四袋同一个连接、同一站立日、`trade_date = ?` 精确命中。
- 每条探针收据带：`trigger`（哪个题材、为何触发）/ `requested_date` / `served_date` / `status ∈ {hit, no_match}` / `rows` / `role="出清/分歧观察"`。`probe_id` 刻意不设——P0 只有一种探针，`trigger`+`role` 已标识；多探针目录（P1）落地时随真实读取点一起加（unread-fields 门禁实测拦截「写了没人读」的字段，2026-08-25 提交时命中一次）。

### 1.2 不做

- **不做模型自选补查**（P2 预留，见 §8）；本单探针零模型参与，触发即规则。
- **不走 KB / 检索 / web 补名单**——four-arm-ready 禁令「检索加法补个股」原样有效；探针只读 `fact_sector_daily` / `fact_sector_stock_daily`。
- 不改四袋查询、站立日解析、`should_stop` / 休市纪律。
- 不改 `mainline_dual_red_gap` 的缺口句——替补池是缺口句的**补充**，不是替换；两者共存。
- 不把替补行标成「机会」；不排序成「推荐」；role 字段只有观察语义。
- 不动 outlook 五日包（P1）、不动 `compile_research_program` operator 目录（P1）、不碰 tier / 停机 / followup。
- 不改 8792 / 8796 生产配置；live 验证走 sidecar 新目录，不覆盖 `four-arm-knevo-20260823/`。
- 邻日回落禁止：站立日无匹配板块行 = `no_match`，如实渲染「无可替补板块」，不查 `<=`。

## 2. 术语

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **探针（probe）** | 注册在包层的确定性替补查询，由包状态谓词触发，带收据 | quality 稿的「残差」（模型层）；「检索加法补个股」（被禁的检索填充） |
| **触发谓词** | `mainline hit ∧ 题材无双红文本匹配`，逐题材判定 | 模型判断；prompt 指令 |
| **替补池** | 探针产出的带标签个股名单（题材→板块→个股） | 机会名单；推荐 |
| **标签先行** | 渲染时 role 限定语排在名称/数字之前（KIT「声明式截断：限定语排在被限定内容之前」同族） | 稿末尾注 |

## 3. 已核实事实（2026-08-25 对 `760bf79b` 快照核验，实施时不要再探一遍）

1. `market_watch_pack.mainline_dual_red_gap()`：主线∩双红为空时**只返回缺口句**，无任何替补行为。渲染在 `render()` 内、`merge_into_public_answer` 会带进 owner 路径。
2. `run_market_watch_pack` 四袋共用一个只读连接（`retrieval_cache.try_connect_readonly`），`finally` 关闭——探针必须在同一连接生命周期内跑完。
3. 接缝唯二：`ask.py` `bind_market_watch_pack`（market_watch 路径，包渲染进 `supplemental_evidence` 并锁 `AskOptions`，`market_watch_pack=pack` 已挂在 options 上）；`ask.py` `bind_research_program`（非 market_watch 路径走 `run_strict_signal_pack`，operator 目录在 `research_contract.py`，现有六个，无替补类）。
4. `weekly_watch_pack.py` 调 `run_market_watch_pack`（逐日）；本单默认关探针即不改它的行为。
5. live-toolkit 决策原文（decisions.json）：「医药没有双红块，规则名单会空。题要的是反馈观察，所以改查成交额最大的医药二级块里的前2，标成出清/分歧观察，不当机会。」——触发、查询、标签三要素齐备，规则可表达。
6. 五臂报告结论 2：天花板臂因机械双红交出空医药池（题没答全）；供数对照行「个股代码：科技 6 + 医药 4，都有代码」仅现场写臂做到。
7. 台账 `R-20260825-01…03` 经 rg 全库（`docs/` + `fwp-wt-*/docs/prediction-ledger.md`）未被占用。
8. **待冻结（实施第 0 步）**：`fact_sector_stock_daily`（VIEW）个股名称/代码/成交额列名以 `pragma table_info` 实测为准，不抄本稿；该 VIEW 只暴露 published 快照，探针无需感知 `sector_universe_snapshot_id`。

## 4. 方案对比

| 方案 | 做法 | 得 | 失 / 判 |
|---|---|---|---|
| **A. 包层注册探针（采用）** | 谓词触发 + 同连接确定性 SQL + 标签收据 | 覆盖已观察形状；零模型风险；标签可判 | 只救注册过的形状；未见过的空袋仍只有缺口句（诚实，可接受） |
| B. 残差写手加预算让模型自己补查 | 升 tier 或多轮 | 可能覆盖未知形状 | quality 稿 §5 已证「座位不对加时是给错误工作流加薪」；且查询不可复现、标签无收据。否决 |
| C. 模型从注册菜单点探针（bounded requery） | 模型选 probe_id，执行仍是注册查询 | ReAct 判断力 + 查询仍确定 | 需要开关板原子做消融、需要 contract 门控；**P2**，不与 P0 绑 |
| D. 检索/KB 补个股名单 | kb_search 填池 | 名单快 | four-arm-ready 明令禁止；名单无当日行收据。否决 |

## 5. 目标态

```
run_market_watch_pack(query, substitute_probes=True)   ← 仅 bind_market_watch_pack 开
  → 四袋（不变）
  → 谓词：主线袋 hit 且存在无双红匹配的题材（复用 gap 对齐逻辑）
  → 逐题材（≤2）：fact_sector_daily 站立日名称匹配板块 top1(amount)
        → fact_sector_stock_daily 该板块该日 top2 个股（带代码）
        → ProbeReceipt(role=出清/分歧观察, served_date=站立日)
  → pack.probes 挂载
render()：总量/主线/双红/缺口句/涨停热度 之后 →
  「## 替补观察（出清/分歧观察，非机会）」
  「- [出清/分歧观察] <题材>→<板块>(amount)：<股名>(<代码>)、<股名>(<代码>) served_date=…」
merge_into_public_answer：免费携带（owner md 不得顶掉）
```

## 6. 契约

1. **同日纪律**：探针 SQL 一律 `trade_date = cast(? as date)`，`?` = 包的站立日。`served_date != requested_date` 不可能出现（出现即 bug）。
2. **标签先行**：渲染行内 role 限定语在板块/个股名之前；标题行自带「非机会」。
3. **no_match 诚实**：题材在 `fact_sector_daily` 该日无名称匹配板块 → `status=no_match`，渲染「<题材>：该日无可替补板块」；禁止放宽匹配、禁止邻日。
4. **上限**：题材取主线袋行序前 2 个未匹配者；1 板块 / 2 个股。超出部分不渲染、不入收据。
5. **locked 传染**：库 locked 时四袋已是 locked，探针不跑（`probes=()`），不另造第三态文案。
6. **收据可审**：`pack.probes` 进 `AskOptions.market_watch_pack`，与四袋同一份收据面；判官/无格闸把替补行当**注册格**（有收据、有 role），不得按「未注册阈值」误杀——实施时加一条判官侧对照测试。

## 7. 验收（离线红→绿 + 变异；live 新目录）

### 7.1 触发与产出

| # | 夹具 | 必须 |
|---|---|---|
| 1 | 主线=[医药,有色金属]，双红=[通信设备,PCB]，sector/stock 表有医药/有色行 | 两条探针 hit；各 1 板块 2 股带代码；`served_date=站立日`；role 齐 |
| 2 | 双红含「创新药」且主线含「医药」（文本包含成立） | 医药**不**触发探针（与 gap 对齐逻辑一致） |
| 3 | 主线 3 个未匹配题材 | 只前 2 个出探针；第 3 个只在缺口句里 |
| 4 | 题材无匹配板块行 | `no_match` + 「无可替补板块」；行数 0 |
| 5 | sector 表只有邻日行 | `no_match`；**变异**：把探针 SQL 改 `<=` → 本条必红 |

### 7.2 渲染与合并

| # | 必须 |
|---|---|
| 6 | 渲染顺序：缺口句在前，替补块在后；标签/「非机会」先于名单出现；**变异**：删 role 渲染 → 红 |
| 7 | `merge_into_public_answer`：owner md 含总量数字时替补块仍在（比照 mw spec §7.1 #2a 防顶掉） |
| 8 | `run_market_watch_pack` 默认参：`pack.probes == ()`；weekly 路径行为逐字节不变；**变异**：默认翻 True → 红 |

### 7.3 Live（P0 收尾，sidecar 端口，新目录）

- A1 冻结题重跑：若 07-23 实况主线全有双红匹配，则用「主线含无双红题材」的最近真实交易日补一发；公开稿出现替补池或如实 no_match。
- 不覆盖 `four-arm-knevo-20260823/`；台账不标 confirmed。

## 8. P1 / P2（本单不实施，只钉方向）

- **P1-a** outlook 五日包接探针：仅最新交易日那袋开 `substitute_probes=True`，收据须走开口预取账本（`content_hash` + E 号纪律，见 quality 稿 P0-a）；行为变更单独验收。
- **P1-b** 一般题路径：`research_contract` 新 operator `market.substitute_observation`，`compile_research_program` 在「题材 + 个股观察」意图时编入，`run_strict_signal_pack` 分发到同一探针函数。第 0 步先冻结三道 SPT 原题今天编译出什么 operator（勿假设）。
- **P2** 模型点菜（bounded requery）：模型从注册探针菜单选 ≤2 发，执行仍是注册查询。必须做成开关板原子（预留 id `probe.menu`），入 default 盒前过正控/负控消融；不入本单。

## 9. 落点

| 文件 | 职责 | 序 |
|---|---|---|
| Modify: `intelligence/services/market_watch_pack.py` | `ProbeReceipt`；`_probe_substitute_observation(con, standing, mainline_bag, dual_bag)`；`run_market_watch_pack(..., substitute_probes=False)`；`MarketWatchPack.probes` + `render()` 尾接 | P0 |
| Modify: `intelligence/services/ask.py` `bind_market_watch_pack` | 传 `substitute_probes=True` | P0 |
| Test: `intelligence/tests/test_market_watch_substitute_probe.py` | §7.1–7.2 全部 + 变异 | P0 |
| Test: 判官侧对照 | 替补行不被无格闸/未注册阈值闸误杀 | P0 |
| 收尾: `docs/prediction-ledger.md` | `R-20260825-01…03` | 收尾 |

## 10. 账本

| ID | 现象 | 类型 | 序 | 验证 |
|---|---|---|---|---|
| `R-20260825-01` | 主线∩双红空时观察池只有缺口句，题要个股反馈时交白卷（五臂天花板臂实测形状） | `HARNESS_FIX` | P0 | §7.1 #1 / §7.3 |
| `R-20260825-02` | 替补行进稿不带出清/分歧标签，被读成机会名单 | `HARNESS_FIX` | P0 | §7.2 #6 |
| `R-20260825-03` | 五日包/一般题路径同形状空池（P1 范围，先立案后实施） | `HARNESS_FIX` | P1 | §8 |

## 11. 实施顺序

1. 干净树；第 0 步 `pragma table_info` 冻结 `fact_sector_stock_daily` 列名（§3 #8）。
2. §7.1 #1 红 → 探针函数 + 挂载 → 绿；#2/#3/#4 逐条红→绿。
3. §7.1 #5 变异（`<=` 必红）钉死同日纪律。
4. §7.2 渲染/合并/默认参三条。
5. 判官对照测试。
6. live 一发（§7.3），新目录。
7. pathspec 提交（spec 单独一 commit 可落脏树；代码全在干净树）；合 main 等用户确认。

## 12. 自检

- 无 TBD。触发谓词复用 gap 对齐逻辑，无第二套匹配。
- 判别变量 = 「缺口句之后出现带标签、带代码、同日收据的替补池」，不是措辞。
- 与 quality 稿分工干净：本单加的是组件菜，不是模型预算；D2/D4 未被违反。
- 与 four-arm-ready 禁令不冲突：无 KB/检索参与。
- 默认关 + 单点开启，weekly/一般题零行为变更；P1 各自带验收。
- P2 已按开关板纪律隔离，未混入 P0。

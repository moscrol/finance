# 设计：公开晚报（PublicEveningBrief）

- 日期：2026-08-27
- 状态：Draft v1（spec 随实施分支同车进仓）
- 来源：用户会话「想做一份附属产品：晨报/晚报，汇总盘面+研报+消息面，用作可分享的产品宣传 → 该怎么做 → 执行」。不是四阶段分诊。
- 代码树：`feat/public-daily-brief`，基当时 `gitea/main`（`470e43a3`）。
- **禁止**动 8792 / 8796 / 8802；不 force push；不提交运行产物与快照 JSON。

相邻稿（本单不重做、不抢合）：

| 邻单 | 它管什么 | 本单角色 |
|---|---|---|
| `2026-08-24-market-watch-component-first-design.md` | 全市场四袋、题型 `market_watch` | **委托** `run_market_watch_pack` 取数，公开渲染只用白名单字段 |
| `2026-08-26-watchlist-digest-pack-design.md` | 个人自选简报（画像清单×四袋） | 姊妹件。个人简报含画像，**公开晚报绝不含任何用户画像** |
| `market_feature_store/exports/<date>-theme-candidates.md` | 每日题材候选（自家 KB 加工，只读生成） | 公开版题材段的**唯一素材源**（只取题材名与自家 KB 统计，不取触发词） |
| `复盘/daily/<date>/*.html` + `render_daily_review_template.py` | 内部复盘 HTML | 不改、不替代。公开晚报是另一份**公开安全**产物 |
| `intelligence/services/theme_fermentation.py` | 发酵摘要纯函数 | P1 才挂（公开版需剥供应商字段），P0 不接 |
| `2026-08-27` Hosted Alpha（隧道 + Access） | 内测身份门 | 不相关。公开晚报是文件产物，人工转发，不走站点 |

---

## 0. 一句话

把每天已有的数据资产渲染成**一页可对外分享的晚报**（自包含 HTML + 长图 PNG）：只用公开可复核事实 + 自家知识库加工，供应商派生指标一律不出场；每个数字带站立日与来源口径，页脚固定免责声明。这是**产物不是题型**——不进问答路由，不碰 8792。

**判别变量**（验收只锁这一条）：给定站立日，`python3 -m intelligence.cli brief --date <D>` 产出的 HTML 里，每个数字都能在证据快照的冻结行里逐字找到；全文匹配不到供应商派生口径词（边际量/diff_ratio/双红/主线/市场阶段）与买卖词；休市日/无该日行 → 全文只有无行情句。不是「好不好看」，不是「像不像券商晨报」。

人话：内部工具是全副武装的驾驶舱，晚报是给外人看的一张仪表照片——照片上只能有自家的表和公开的路况，不能把租来的雷达屏也拍进去。

---

## 1. 红线：数据许可白名单（本单的骨架，先于一切功能）

公开分享 = 公开出版。三档处置：

| 档 | 内容 | 处置 |
|---|---|---|
| ✅ 公开事实 | 指数收盘/涨跌幅、涨跌家数、涨停/跌停家数、两市成交额及其环比（纯算术）、连板家数分布与最高板（可由公开行情逐日复核） | 可出，来源标注「公开行情统计」 |
| ✅ 自家加工 | 题材候选榜的**题材名**与自家 KB 统计（概念页数/公司暴露数/证据数）、后续 P1 的发酵叙事 | 可出，来源标注「本地知识库」 |
| ❌ 供应商派生 | 边际量 `diff_ratio`、双红口径、主线标签、市场阶段/量能状态标签、题材涨停热度榜的供应商名单、iFinD、L2、研报原文或近原文摘要 | **一律不出**。渲染层白名单强制 + 全文 deny-token 测试 |

实现为双保险：**字段白名单**（渲染器只认 `PUBLIC_FIELD_WHITELIST` 里的键，白名单外的键根本到不了模板）+ **deny-token 断言**（渲染产物匹配 `边际量|diff_ratio|双红|主线|市场阶段|量能状态|买入|卖出|加仓|减仓|做多|做空` 即测试红）。

研报面 P0 不做内容输出：卖方研报未授权转发是明确侵权，脱水式摘要是高风险动作。P1 若做，只做自家统计口径（覆盖密度/评级分布），不贴内容。

---

## 2. 术语（同步 `UBIQUITOUS_LANGUAGE.md`）

| 钦定词 | 含义 | 不要写成 |
|---|---|---|
| **公开晚报包** `PublicEveningBrief` | 站立日、公开事实行、题材候选行、连板行、方法卡、快照组成的冻结对象 | 晨报、日报、复盘、宣传图 |
| **公开安全白名单** | 渲染层唯一的字段准入表，白名单外字段不进模板 | 脱敏、过滤 |
| **晚报产物** | 自包含 HTML + 尽力而为 PNG 长图，落 `复盘/briefs/<date>/` | 网页、站点、推送 |

---

## 3. 已核实事实（实施时不要再探）

1. `run_market_watch_pack(query, *, market_db_path, calendar_disclosure=None, cutoff=None, substitute_probes=False) -> MarketWatchPack`；`PackBag{name, requested_date, served_date, status, rows}`；`should_stop` / `stop_text()` 语义：显式站立日且 market 袋空才停，locked ≠ 无行情。四袋名 `market_daily` / `mainline` / `dual_red` / `limit_heat`（公开版只用 `market_daily` 袋的白名单字段；其余三袋 P0 一律不渲染）。
2. `fact_limit_advance_daily` 列：`trade_date, stock_ts_code, stock_name, boards, first_limit_date, theme, pct_chg, promotion_rate, source, updated_at`；天然稀疏（无行 ≠ 无涨停）。公开版只出 boards 分布与最高板（连板数可由公开行情复核）；`theme` 列是供应商归类，**不出**。
3. 题材候选产物：`market_feature_store/exports/<date>-theme-candidates.md`，含「## 二、核心候选 Deep（Top 10）」表，列序 `排名|题材|标准概念|申万一级|评分|触发|概念|公司暴露|证据|缺口`。**触发列含 double_red 等供应商信号词，公开版不取**；只取 题材/概念页数/公司暴露/证据数。文件缺失（当日工作流未跑）→ 题材段整段缺口句。
4. CLI 挂点：`intelligence/cli.py` 的 `add_digest_parser` / `cmd_digest` / `build_parser` 形状（`brief` 照此新增）。
5. Chrome 无头可用：`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`，PNG 为尽力而为（失败不红，HTML 是主产物）。
6. `services/` 禁 import `runtime/`（层级门禁）；包必须纯函数，测试用临时 DuckDB 夹具。
7. 台账 `R-20260827-01…-06` 已被占用；本单预注册 **`R-20260827-07/-08/-09`**（若合并前撞号，按 `R-20260824-31` 先例改号并留记录）。

---

## 4. 范围

### 4.1 P0 做

1. 新模块 `intelligence/services/public_brief_pack.py`：`run_public_evening_brief(*, market_db_path, exports_dir, cutoff=None) -> PublicEveningBrief`（纯函数、只读）。
2. 事实段：委托 `run_market_watch_pack`（显式 cutoff），只取 `market_daily` 袋白名单字段。
3. 连板段：包内一条精确日 SQL 读 `fact_limit_advance_daily`（`trade_date = ?`，禁 `<=` 回落），出 boards 分布 + 最高板个股名。
4. 题材段：解析当日 `<date>-theme-candidates.md` Top 表，取前 3（题材名 + 自家 KB 三个计数）；文件缺失 → 缺口句。
5. 渲染：`render_html()` 自包含单文件（750px 移动宽度、无外链资源），含方法卡（站立日/来源口径/快照 ID/生成时间）、页脚免责声明（「AI 生成、人工复核后分享；不构成投资建议」）；`to_snapshot()` 冻结全部输入行。
6. CLI：`python3 -m intelligence.cli brief --date YYYY-MM-DD [--out-dir 复盘/briefs] [--png] [--write-snapshot]`。HTML 落 `复盘/briefs/<date>/evening.html`；`--png` 用 Chrome 无头截长图（失败降级为提示，exit 仍 0）；快照 JSON 落 `~/.finance-runtime/public-brief/<date>/`（`PUBLIC_BRIEF_DIR` 可重定位），默认不落。
7. 词表 + 台账预注册随本车。

### 4.2 P0 不做

- 不做晨报（P1：隔夜外盘 + 事件日历，公开引用口径先换自取源再说）。
- 不接发酵摘要、不出研报内容、不出题材热度榜。
- 不进问答路由（无新题型）、不挂夜跑（内容口径被真人磨稳前手动生成）、不做公众号/站点分发。
- 不改 `market_watch_pack` / `watchlist_digest_pack` 任何语义。
- 产物不自动 commit（`复盘/briefs/` 是 tracked 目录，提交与否由人决定）。

### 4.3 P1 / P2（点头再做）

- P1：晨报（外盘/事件日历）；发酵叙事公开版（剥供应商字段）；卖方覆盖密度统计段；夜跑挂点（与 watchlist-digest P2 共用时槽、产物分开）。
- P2：自动分发（公众号/静态站点）、二维码/水印视觉模板（可用 finance-illustrations 技能出头图）。

---

## 5. 工件形状

`PublicEveningBrief`（frozen dataclass）：

- `standing_date: str | None`；`status: Literal["locked", "empty", "locked_db"]`（对齐 watchlist 包语义：库打不开=locked_db；无该日行=empty 且 `stop_text`）
- `facts: tuple[BriefFact, ...]` — `BriefFact{label, value, unit, source}`，value 逐字来自冻结行
- `ladder: BriefLadder | None` — `{max_boards, leader_names, distribution}`；无行 → None + 缺口句
- `themes: tuple[BriefTheme, ...]` — `{name, concept_pages, exposure_count, evidence_count}`
- `method_card: str`（固定口径句，非模型文案）；`snapshot_id: str`（内容 sha256 前 12）
- `render_html() -> str`；`to_snapshot() -> dict`

公开稿顺序锁死：站立日头 → 公开事实卡 → 连板观察 → 题材候选（自家 KB）→ 方法卡 → 免责页脚。缺段用缺口句占位。

---

## 6. 验收

离线（合 PR 前）：

1. 夹具库：事实卡数字逐字 ⊆ 快照冻结行；方法卡含站立日与「公开行情统计/本地知识库」来源句。
2. deny-token：渲染产物注入任一供应商口径词或买卖词 → 测试红（正则见 §1）。
3. 白名单强制：往袋行塞一个白名单外字段（如 `diff_ratio`）→ 渲染产物不得出现该值（变异锁）。
4. 无该日行 → 全文只有无行情句，零数字；库打不开 → `locked_db` 不冒充无行情。
5. theme-candidates 文件缺失 → 题材段缺口句，exit 0。
6. 连板表无该日行 → 连板段缺口句（天然稀疏语义），不借邻日。
7. CLI 对夹具库产出 HTML 文件；`--png` 在无 Chrome 环境降级不红。

Live（合并后、人工转发前）：真库只读生成最近交易日晚报，人工核对：页面无供应商口径词、数字与库一致、观感可分享。**live 由用户复核，执行方不得自标 confirmed。**

---

## 7. 台账（预注册）

| ID | fix_type | verification_prediction |
|---|---|---|
| `R-20260827-07` | `DATA_CONTRACT_FIX` | 公开产物数字逐字 ⊆ 快照冻结行；精确日无邻日回落；无该日行只出无行情句 |
| `R-20260827-08` | `HARNESS_FIX` | 白名单+deny-token 双保险生效：变异（塞 diff_ratio 字段 / 注入「双红」词）→ 测试红 |
| `R-20260827-09` | `ROUTING_FIX` | 本单零路由改动：`watchlist_digest`/`market_watch` 等既有题型行为逐字节不变（回归） |

---

## 8. Key Decisions

1. **白名单先于功能。** 公开产品的第一变量是数据许可，不是信息量；每少一个供应商指标，合规风险少一分、自家加工占比高一分。
2. **产物不是题型。** 晚报是文件（HTML/PNG），不进问答路由——避免再开一个确定性 owner 的复杂度，也让分发节奏完全由人控制。
3. **委托四袋但只渲染白名单。** 取数复用 `run_market_watch_pack`（站立日/停机语义白拿），渲染层负责收敛——不复制 SQL，也不给公开层第二套取数口径。
4. **题材段只信自家 KB 产物。** theme-candidates 是唯一素材源且剥掉触发词——公开版展示的护城河应是图谱加工，不是转售供应商信号。
5. **可审计当卖点。** 方法卡 + 快照 ID + 免责声明是产品的一部分，不是合规负担——对齐「AI 写的，但每个数字有出处」的宣传定位。
6. **P0 手动生成。** 内容口径没被设计合作伙伴磨稳之前，不挂夜跑、不自动分发——分发自动化是 P2。

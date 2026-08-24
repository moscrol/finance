# 设计：展望题换到 `market_forecast` 座位，活周报 + 五日包先于模型

- 日期：2026-08-24
- 状态：Draft **v2**（核稿注入点 / 契约副作用 / 板块主语 / 台账号已改定；未实施）
- v1 → v2：P0 椅子从 compose 汇合处改到 Engine A 开口预取。v1 §6.6 只挂 `owner_output` 之前 = 路由修完后的死代码。见 §0.2。
- 来源：用户把同一题丢给 Cursor agent 与生产 Workbench。Workbench 跑次 `run_20260824_164201_040215`（16:42，`continuous_glm` / `glm-5.2`，视角 SPT-Molmansk）。真源 `continuous-episode.json`，不是 UI `trace.json`。
- 核稿复放：2026-08-24 晚，用户在 `gitea/main` 实测三链，与本仓同进程复放同形（§0.1）。
- 代码树：从 `gitea/main` 开干净树。分类器单独小 PR `fix/forecast-unordered-conjunction`；包与注入走 `feat/outlook-live-weekly-pack`。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树上改 runtime。**禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做、不抢合）：
  - `docs/superpowers/specs/2026-08-24-market-watch-component-first-design.md`（当日四袋；**共用包函数，不共用接线点**，见 §0.2 / §11）
  - `docs/superpowers/specs/2026-08-24-personalized-join-kernel-design.md`（StancePack；同族洞：compose 对 Engine A 早退不可达。那份稿 v1.1 已改到 `handle()` 之前）
  - `docs/superpowers/specs/2026-08-20-market-cause-sector-routing-design.md`（词序洞兄妹）
  - `docs/superpowers/specs/2026-08-19-user-framework-perspective-bootstrap-design.md`
  - `intelligence/services/asof_prefetch.py`（main 已有；本脏树可能还没有。`market_forecast` 今日只预取 3 日双红个数）
  - `intelligence/services/reading_baseline.py`

## 0. 一句话

Workbench 和人工 agent 对「上周行情 + SPT 镜头写本周展望」的相交集是盘面组件；差距不在文笔，而在 **Engine A 坐在 `general_finance_qa` 上自己点工具**。本单做三件事，都不靠给模型松绑：

1. 把这句题锁进已有的 `market_forecast`（契约变成情景/续走/失效，不再是通用问答）。
2. 选定视角时，**按日期取最新一篇周报**进开场 E 袋（活周报），旧文只能标 analog。
3. 在 **Engine A 开口预取**里先跑**上周五个交易日 × 四袋**，新闻日晚于库尖不得给剧本盖章。

**判别变量**（验收只锁这一条）：冻结题「基于上周的行情，模仿你之前蒸馏的spt，写一下本周行情的展望。」在模型开口之前，必须同时满足：`question_type=market_forecast`、活周报收据的 `date` 等于该视角文章最大日期、五日包收据齐（每天总量/主线/严格双红/涨停热度，或该日该袋 empty）。不是「稿子像 SPT」，不是「多调一次 `kb_search`」。

**契约副作用**（v2 补）：修完路由后，`required_outputs` 从 `(direct_answer, evidence_boundary)` 变成展望五件套 + `evidence_policy=current_market_scenarios`。冻结题可能从「能出烂稿」变成「契约更严、更多 partial」。Live 验收必须押 **修完后仍能出可用稿**（公开稿非空、至少有直接判断或一条情景），不只押题型正确。见 §7.5。

人话：点菜员没把「展望」听成套餐，后厨按家常菜随便抓了周五剩菜和一篇六月旧文。本单改点菜，并把套餐先放进 Engine A 的开场观察池。厨师只解释两盘对不上的地方。

### 0.1 初判更正（[实测] 2026-08-24，main 与本仓复放一致）

对照会话里曾写「『模仿蒸馏的 spt』把题型拽成了通用研究」。**推翻。**

| 题面 | `is_market_forecast_query` | 信封 `understand_query` | 评分链 `plan_answer_question` |
|---|---|---|---|
| 冻结原题 / 「写一下本周行情的展望」 | **False** | `general_finance_qa` | `market_forecast` |
| 「展望一下本周行情」 | True | `market_forecast` | `market_forecast` |
| 「模仿spt写一下本周行情的展望」 | False | `general_finance_qa` | `market_forecast` |

`decide_turn(llm=boom)` 跟信封走，不调 LLM：冻结题 `general_finance_qa`，`required_outputs=(direct_answer, evidence_boundary)`，`task_frame_hash=151d80a2…` 与冻结 run 一致。

PRIMARY 是 **词序**：`_MARKET_FORECAST_RE` 第一支要「展望/研判/预测 → 后市/市场/行情/大盘」；冻结题是「本周行情的展望」（展望在句尾）。尾支只认「给出/做/说说/谈谈 … 展望」，**不认「写一下」**。模仿句不改题型。

评分链是无序合取（展望 ∧ 行情），所以 `plan` 已经对。任务契约链走正则，所以 Engine A 从第一帧就拿错契约。`test_upstream_task_protocol.py` 的 `FORECAST_PHRASINGS` **没有**句尾展望句——只绿旧表 = 假绿。

「模仿/蒸馏 SPT」仍要锁：这些词不得把已命中的 forecast 改走 `general_finance_qa`（防下一版 LLM controller）。

语义闸对冻结 run 已写：`2026.23` 未进证据注册表、`3900箱体` 由单日收盘外推、`MA20 110-120%` 与 `<1.9万亿` 无格。`judge_status=repaired` 且 `repair_attempts=0`，公开稿未改。本单用组件消灭这些句，不靠再加一条质检当主修法。

### 0.2 v2 核稿改定（实施按本节，不是按 v1 的 §6.6）

| ID | v1 会让 P0 落不了地 | v2 |
|---|---|---|
| **F1 注入点** | 包挂在 `if owner_output is not None` 之前（v1 约写成与盘面包「同一句」）。`market_forecast` 修对路由后 → `lane=research` → `canned is None` → `continuous_turn_adapter.handle()` → `handled` 则 `_complete_continuous_turn` **直接返回**。compose 汇合处对主路径不可达。盘面包拒收 A，所以它的汇合处可达；本单 **P0 不拒收 A**，不能抄那把椅子。 | **拍板 (a)**：扩 `collect_prefetch_items` + `_opening_prefetch_evidence`。五日包走预取（`question_type==market_forecast` 已有 3 日双红支，改成委托 `run_weekly_watch_pack`）。活周报是视角平面，**不**塞进 `asof_prefetch.py`；在 `_opening_prefetch_evidence` 里拼接。开场经 `_seed_opening_prefetch` 进 Engine A 观察池。**(b)**（orchestrator 在 `handle()` 之前跑同一份纯函数）允许当测试挂钩，但必须喂**同一对象**进开口预取，禁止第二份散文。**(c)** 仅 compose = P0 死代码，否决。**(d)** P1 才拒收 `market_forecast`，与 §1.2 一致，P0 不做。 |
| **F2 共用什么** | 「与盘面包同一汇合处」 | 共用 **`run_market_watch_pack(day)` 函数**（避免第三份双红 SQL）。接线点按引擎分：盘面拒收 A → compose；展望留在 A → 开口预取。 |
| **F3 板块主语** | 未写。`分析有色金属板块后续走势` 信封/plan/decide 今日都是 `theme_analysis`（plan 链 `subject_kind==theme` 让位，`answer_orchestrator.py` 约 282–286）。 | **不在 P0**。扩它要改主语优先序，不是只修 forecast 正则。§7.1 #9b 当负样本锁住「不被本单抢走」。 |
| **F4 契约加严** | 只锁题型 | Live 必须仍能出可用稿。见 §0 契约副作用、§7.5。 |
| **F5 台账号** | `R-20260824-11`…`15` | knevo28 已占 `-12`…`19`，且注明 `-11` 已占用。本单改 `R-20260824-20`…`24`。join kernel 从 `-25` 起。 |

行号会漂。导航用符号：`continuous_turn_adapter.handle`、`_complete_continuous_turn`、`collect_prefetch_items`、`_opening_prefetch_evidence`、`_seed_opening_prefetch`。不要按脏树或某一版的 2770 行找椅子。

## 1. 范围

### 1.1 做

- 改 `is_market_forecast_query` / `_MARKET_FORECAST_RE`，使「写一下本周行情的展望」类句尾展望与「展望一下本周行情」一样为真。规则是 **展望类动词 ∧ 市场主语** 的无序合取，不是再加一条有序正则凑冻结题。
- 冻结题与 §7.1 句表在 **信封层、评分链、回合层** 三处都是 `market_forecast`。`decide_turn(llm_complete=boom)` 不得为了分类去调 LLM。
- 「模仿 / 蒸馏 / 按 SPT 写」只允许影响视角轴（UI 已选 `single` + `sptfei` 则本单不解析店名）。**禁止**这些词把 `question_type` 改成 `general_finance_qa` / `theme_analysis`。
- 新组件 `bind_live_weekly(perspective_id) -> LiveWeeklyReceipt`：按 `article.date` 取最大一篇，短摘进入开场 E 袋，标签 `live_weekly`。无文则 `status=missing`，公开稿首句声明，禁止编文号。
- 旧文召回改走「本周磁带状态」查询，且 `date < live_weekly.date`，标签 `analog`。公开稿把 analog 写成「原文判断 / 本周剧本」则删句。
- 新组件 `run_weekly_watch_pack(end_date, window=5) -> WeeklyWatchPack`：先验周每个交易日跑四袋 + 周级量能序列。显式日用 `trade_date = ?`，禁止 `<=` 回落。有 `run_market_watch_pack` 则每日委托。
- **P0 注入（a）**：`question_type==market_forecast` 时，`collect_prefetch_items` 产出五日包对应的 `PrefetchItem`（取代今日 3 日双红个数这一支，不要两套并存）。`_opening_prefetch_evidence` 再拼接活周报 / analog。`_seed_opening_prefetch` 进账本后再 `format_opening_prefetch_message`。模型开口前收据必须在。
- 新闻（或其它非 DuckDB 源）`served_date > latest_data_date` 标 `news_after_standing_date`。公开稿不得用这些句子写「验证 / 已兑现 / 证明剧本」。
- 画像里的方法语言（110–120%、旗型、断代）可以教怎么读；**数字进公开稿必须来自活周报格或量能袋**。格里没有就删句。
- 分类器单独小 PR，见 §11。包与注入可与分类器同树，但合入时不要跟盘面包抢同一份 regex diff。

### 1.2 不做

- 不在产品里嵌完整 ReAct，不加「请先查最新周报」prompt，不加一轮 repair 当主修法，不加严质检当主修法。
- **不**把 `market_forecast` 加入 `DETERMINISTIC_OWNER_TYPES`（P0）。展望题今日不在 `_SYNTHESIS_HEAVY_QUESTION_TYPES`。拒收 A 是 P1。
- **不**把包只挂在 compose 汇合处当 P0（§0.2 (c)）。
- 不把 `market_forecast` 改路由成 `market_watch` / `dated_market_review` / `market_cause`。
- **不**把带板块/题材主语的前瞻题（「分析有色金属板块后续走势」「液冷后续怎么走」）改坐 `market_forecast`。那是主语优先序，另开稿。
- 不翻 `perspective_mode` 默认 `neutral`。不把 SPT 升格进 `reading_baseline`。不把倾向写成领域方法。
- 不整篇灌版权周报进上下文。活周报只吐短结构（§6.2）。
- 不用 LLM 抽活周报字段（P0）。不把 `memory_lookup` 当 SPT 原文入口。
- 不把视角 IO 写进 `asof_prefetch.py`（那模块是市场库预取）。
- 不改双红 SQL、不新建第二份量能口径、不改 8792。
- 不追 Knevo 外盘叙事，不把 8 月 24 日新闻层写成库内磁带。
- 不在本脏树改 runtime。

## 2. 术语

| 词 | 含义 |
|---|---|
| **Engine A** | `continuous_episode` / `continuous_glm`。冻结 run 走这里。修对路由后仍走这里。 |
| **开口预取** | `collect_prefetch_items` → `_opening_prefetch_evidence` → `_seed_opening_prefetch`。模型第一轮之前进证据账本。 |
| **compose 汇合处** | `owner_output is not None` 之前。Engine A `handled` 早退则**到不了**。 |
| **信封层** | `understand_query` / `is_market_forecast_query`。 |
| **评分链** | `plan_answer_question` / `_classify_question_type`。 |
| **回合层** | `decide_turn` → `TaskFrame`。`collect_prefetch_items` 吃的 `question_type` 是这一层。 |
| **活周报** | 选定视角下 `article.date` 最大的一篇。本冻结对照：`sptfei` / 2026.34 / `2026-08-17`。 |
| **analog** | 日期严格早于活周报的旧文，只许类比结构与节点，不许搬当时的板块角色。 |
| **先验周** | 库尖往前 `window` 个有行交易日。冻结对照：`2026-08-17`…`2026-08-21`。 |
| **站立日隔板** | 磁带站在 `latest_data_date`；晚于它的新闻不得给先验周剧本盖章。 |
| **四袋** | 与盘面组件包同一口径：总量、主线、`DOUBLE_RED_SQL`、涨停热度。 |
| **残差** | 只解释格与格冲突，以及活周报推演 1/2 在先验周是确认、证伪还是未完成。不得改主线角色。 |
| **可用稿** | 公开稿非空；含直接判断或至少一条带条件的情景；不是 0 工具 `deadline_exhausted`，也不是只剩缺口清单。`research_status=partial` 可以，空稿不可以。 |
| **两套分类器** | 评分链已经会认句尾「展望」；任务契约链不会。只绿一条 = 假绿。 |

## 3. 已核实事实（实施时不要再探一遍）

行号会漂，用符号。`asof_prefetch` 以 **`gitea/main`** 为准（本脏树可能无此文件）。

**路由：**

1. `_MARKET_FORECAST_RE` 第一支有序；尾支动词表 = `给出|做|说说|谈谈`，无「写一下」。
2. `understand_query` 在 `is_market_forecast_query` 为真时返回 `market_forecast` / `market_anchor` / 0.92；冻结题落到 `general_finance_qa` / `generic` / 0.4。
3. `_classify_question_type` 对「展望 ∧ (后市|市场|行情|大盘)」无序合取。`plan_answer_question(冻结题)=market_forecast`。
4. `decide_turn(冻结题, llm=boom)` 不调 LLM，仍是通用问答契约。PRIMARY 不在 LLM 控制器。
5. `FORECAST_PHRASINGS` 无句尾展望。本单把 §7.1 加进 `test_upstream_task_protocol.py`，不另建第二份三链测试。
6. 「分析有色金属板块后续走势」：`is_market_forecast_query=False`；三链皆 `theme_analysis`（信封 `subject_kind=theme` / `subject=有色金属`）。plan 链主题让位在 `_classify` 之后把 forecast 压回去。P0 保持这句不被抢走。

**冻结 run `run_20260824_164201_040215`：**

7. `execution_kind=continuous_episode`，`repair_attempts=0`，`question_type=general_finance_qa`。`today=2026-08-24`，`latest_data_date=2026-08-21`。
8. 五次工具：`memory_lookup` → `market_data{}` → `mainline_context{}` → `finance_query` 窗口 → `news_search`。零次 `kb_search`。
9. `memory_lookup` 的 E1–E5 全是 `corrections.jsonl`。
10. 空参快照只有库尖一日。周四药高潮不在收据里。
11. 公开稿「SPT 原文判断（2026.23）」正文为真、未进本轮 E 袋。2026.23 是 6 月剧本。
12. `retrieve_article_snippets(query)` 用用户原句 BM25。日期键必须盖过它。
13. `_market_block` 在 `market_forecast` 时拼当日总览 + 5 日量价窗，**无**逐日主线/双红/热度四袋。

**Engine A 弱供给（main，路由坐对之后才会走到）：**

14. `collect_prefetch_items`：`question_type==market_forecast` 时 `_prior_trade_dates(..., 3)` + `dual_red_counts`，一条「双红个数序列」。不是五日四袋。`con is None` 今日可直接少这段。
15. `_opening_prefetch_evidence` / `_asof_prefetch_text` 调上面那个函数。`_seed_opening_prefetch` 先入账本再格式化开场消息（E 号与终局同一张表）。
16. `DETERMINISTIC_OWNER_TYPES` 无 `market_forecast`。`_SYNTHESIS_HEAVY` 无 `market_forecast`。
17. 编排器顺序：`decide_turn` → `plan` span → `deterministic_lane_answer` → **`continuous_turn_adapter.handle`** → `handled` 则 `_complete_continuous_turn` 返回。其后的 `owner_output` / compose **不执行**。这是 v1 §6.6 的阻断。

**先验周锁格（实施对照，勿重查口径）：**

18. 成交额 23857.90 / 24006.36 / 25108.68 / 20792.47 / 18791.51；量比 101.19 / 103.03 / 108.09 / 89.73 / 81.19；双红 COUNT 75 / 21 / 0 / 17 / 2。08-17 上证点位空，不补邻日。

**活周报：**

19. 生产画像 `~/.local/share/finance-workbench/users/linxiaoqi5111/perspectives/profiles/sptfei.json`。验收锁 `date=max(article.date)`，不写死文号。

## 4. 方案对比

| 方案 | 做法 | 追上什么 | 追不上 / 代价 |
|---|---|---|---|
| **A. 换题型座位 + 开口预取两包一隔板（推荐）** | 正则无序合取；`collect_prefetch_items` + `_opening_prefetch_evidence` 跑活周报与五日四袋；新闻日 > 库尖不得盖章 | 冻结题契约；主线角色跟现行周报；周四高潮在开场 E 袋 | 残差仍可能发明阈值，P1 删句；契约加严后要守住可用稿 |
| B. 放开 Engine A / 多给工具 | 希望它自己点 `kb_search`、再查四天 | 偶尔像人工 agent | 与盘面 A1 空转同构；问句 BM25 仍会赢旧文 |
| C. 加严质检 | 再标 2026.23 / 3900 箱体 / 1.9 万亿 | 仪表更红 | 冻结 run 已经 `repaired` 且稿子没改 |
| D. Prompt「请用最新周报」 | 叠在现环上 | 一次有效 | 加法悖论；日期键不改则复发 |

选 A。B/C/D 不是「更强的 A」。

P0 注入四选一（§0.2 F1）是 A 的落点，不是第四个产品方案：**(a) 开口预取**。

## 5. 目标态

```
问句（展望 ∧ 市场主语，无序；无板块主语优先）
  → 信封 / 评分链 / 回合 三处 question_type=market_forecast
  → 视角轴独立：「模仿/蒸馏」不得改题型
  → decide_turn / task_frame 落定
  → 开口预取（模型第一 token 之前）：
        run_weekly_watch_pack → collect_prefetch_items 的 forecast 支
        bind_live_weekly      → _opening_prefetch_evidence 拼接（视角平面）
        analog                → date < live.date，查询=磁带状态
        _seed_opening_prefetch 入账本，带 E 号
  → Engine A 写残差（P0 不拒收）
        只解释格冲突 / 推演 1/2 确认或未完成
        不得改主线角色；不得把 analog 写成活剧本
        不得用 news_after_standing_date 盖章
  → 交付闸：无格数字 / 未注册文号 / 「验证」+ 隔板新闻 → 删句
  → 公开稿仍须可用（§2）
```

`market_cause` 的 5 日量价窗继续为自己的题服务，不替代本包。
compose 汇合处可以**读**同一份 pack 对象（测试 / 旁路），禁止再算一遍当第二真本源。

## 6. 契约

### 6.1 展望入口（无序合取）

`is_market_forecast_query` 在去空白之后为真，当且仅当同时成立：

1. **展望类**：出现 `展望|研判|预测|预判` 之一（「怎么看/如何看」仅保留现役「明天/明日/次日…」支，不在本单扩大）。
2. **市场主语**：出现 `后市|市场|行情|大盘|本周` 之一。

现役有序支全部保留。新增的是合取，不是替换。

禁止：

- 只把「写一下」塞进尾支、保留「展望必须在行情前面」——「本周行情展望」仍红。
- 用 LLM controller 否决确定性入口。
- 因「模仿/蒸馏/SPT/视角」把已命中的 forecast 改走 `general_finance_qa`。
- 因本单合取把「分析有色金属板块后续走势」改成 `market_forecast`。

`required_outputs` 必须含 `FORECAST_REQUIRED_OUTPUTS`（`direct_assessment` / `scenario_paths` / `continuation_conditions` / `invalidation_conditions`），`evidence_policy=current_market_scenarios`。这是有意加严。配套约束：合成 / episode 收口不得因为多出来的槽位把整稿打成空（缺槽写 gap，已有判断仍出站）。见 §7.5。

### 6.2 活周报

```
bind_live_weekly(user_space, perspective_id) -> LiveWeeklyReceipt
```

| 字段 | 规则 |
|---|---|
| `perspective_id` | 选定视角；`neutral` 则本组件不跑，`status=skipped` |
| `article_id` / `date` / `title` | `max(date)`；并列取 `article_id` 字典序 |
| `excerpt` | 「中观」节，否则文首；**上限 360 字**。禁止全文 |
| `status` | `bound` / `missing` / `skipped` |
| 证据标签 | `live_weekly`；`source_date=article.date` |

P0 不抽结构化箱子/主线名。摘录里有的数字算格内；摘录没有的 1.9 万亿算无格。

analog：查询 = 五日包一行状态摘要，不是用户原句；`date < live.date`；`analog=true`。公开稿更旧文号且未写「结构类比 / analog」→ 删句。

`memory_lookup` 只服务纠偏。冻结查询「SPT 量能 展望 纠偏」不得标 `live_weekly`。

调用点：`_opening_prefetch_evidence`（或它抽出的 `_opening_weekly_evidence`）。**禁止** `asof_prefetch.py` import 用户空间 / 视角文章。

### 6.3 五日包

```
run_weekly_watch_pack(end_date, window=5) -> WeeklyWatchPack
```

`end_date` = `latest_data_date` 或问句显式上界。交易日 = `fact_market_daily` 中 `<= end_date` 最近 `window` 个，升序。

| 袋 | 源 | 当日 0 行 |
|---|---|---|
| 总量 | `fact_market_daily` `trade_date = ?` | 「该日无行情数据」 |
| 主线 | 同日主线表 / sector 明细 | 「主线表该日无行」 |
| 严格双红 | `DOUBLE_RED_SQL`；**COUNT，不用 `LIMIT` 后 `len`** | 「严格双红 0 个」（有板块行时） |
| 涨停热度 | `get_limit_heat_themes(日)` | 「涨停热度该日无行」 |

周级序列：`total_amount`、`volume_ratio`（及/或 `amount_ma20`）、`double_red_count`。无则该列 empty，禁止邻日补。

每袋：`requested_date`、`served_date`、`status=hit|empty`。

有 `run_market_watch_pack(day)` 则每日调用，禁止复制 SQL。尚未合入时直调现役只读函数 + `=` 查询。

`collect_prefetch_items` 的 `market_forecast` 支：**删除或退役**「只预取 3 日双红个数」那一支，改为把 `WeeklyWatchPack` 格式化成一条或多条 `PrefetchItem`（建议：周级序列 1 条 + 每日四袋摘要 5 条，或等价、测试能断言周四主线在场）。触发条件只认 `question_type==market_forecast`（路由修好后的单一真本源）。**不要**在预取里再写一份 `is_market_forecast_query`——两处会漂。这就是「先修路由再跑包」的硬原因：题型不对，这支根本不进。

### 6.4 站立日隔板

| 源 | 站立 |
|---|---|
| 五日包 / 活周报 | `latest_data_date` 与 `live.date` |
| `news_search` 等 | 条目日期 `> latest_data_date` → `news_after_standing_date` |

公开稿：隔板证据写成「验证 / 已兑现 / 证明 / 已给部分验证」→ 删该分句。允许声明「新闻层见…，磁带截至库尖，不作为兑现」。

个股连板标题不得升格为「绝对高度辨识度样本」，除非格里已有该高度/容量字段。

### 6.5 残差写手

P0 不拒收 Engine A。约束：

- 开口前必须能读到两份收据（`neutral` 时活周报 `skipped`，只要求五日包）。
- 主线新旧角色以活周报摘录 + 先验周最后一日主线名单为准。名单仍有「医药」、活周报写「新主线」时，禁止写「医药老主线」。
- 推演 2 不得把活周报已写的断代日再写成「本周等待断代」，除非原文把它当未完成条件。
- `compose` 复用，不新造 `residual_enabled`。

### 6.6 注入点（v2 写死）

| 选项 | P0 实效 | 与「不拒收 A」 | 本单 |
|---|---|---|---|
| **(a) 扩 `collect_prefetch_items` + `_opening_prefetch_evidence`** | 立即进 Engine A 观察池 | 兼容 | **P0 采用** |
| (b) orchestrator 在 `handle()` 前跑包 | 同上，收据更显式 | 兼容 | 允许作测试挂钩 / 与 join 稿同椅；必须复用 (a) 的纯函数，禁止第二份 |
| (c) 仅 `owner_output` 汇合处 | 主路径死代码 | 不兼容 | **否决** |
| (d) P1 拒收 `market_forecast` | compose 可达 | 与 §1.2 冲突 | P0 不做 |

盘面包继续用它自己的 compose 椅（因为它拒收 A）。不要为了「同一句」把展望包也挂过去。

## 7. 验收

离线单测必须红→绿。Live 只在干净树。夹具自带视角文章目录，禁止依赖生产 `~/.local/share/…` 是否有 50 篇。

### 7.1 三链同型（P0）——独立 PR 可先合

加入 `test_upstream_task_protocol.py` 的 forecast 表（或同文件新表，**同一条断言函数**）：

| # | 输入 | 必须 |
|---|---|---|
| 1 | 冻结原题 | 三链皆 `market_forecast`；`decide_turn(llm=boom)` 不调 LLM；`FORECAST_REQUIRED_OUTPUTS` ⊆ `required_outputs` |
| 2 | 「写一下本周行情的展望」 | 同上 |
| 3 | 「本周行情展望」 | 同上 |
| 4 | 「基于上周行情写一下本周展望」 | 同上 |
| 5 | 「展望一下本周行情」 | 回归绿 |
| 6 | 「展望一下A股后市」 | 回归绿 |
| 7 | 「液冷服务器怎么看」 | 三链皆 **非** `market_forecast` |
| 8 | 「2026-02-17 涨停家数多少」 | 非 forecast |
| 9 | 「模仿spt写一下本周行情的展望」 | 仍是 `market_forecast` |
| 9b | 「分析有色金属板块后续走势」 | 三链皆 `theme_analysis`（本单不抢） |

变异：只改评分链、不改 `_MARKET_FORECAST_RE` → #1/#2 红。只加「写一下」、不做无序合取 → #3 红。合取过宽抢走 #9b → 红。

### 7.2 活周报（P0）

夹具两篇：`2026-06-01` / 2026.23；`2026-08-17` / 2026.34。

| # | 输入 | 必须 |
|---|---|---|
| 10 | `bind_live_weekly(sptfei)` | `status=bound`，`date=2026-08-17`，excerpt ≤360 且不含 23 全文 |
| 11 | 无文章 | `status=missing`；不得出现「2026.xx」 |
| 12 | analog 查询用磁带摘要 | 命中 23 则 `analog=true` 且 `date<2026-08-17` |
| 13 | 公开稿写「SPT 原文判断（2026.23）」且未标 analog | 删句 / 测试红 |
| 14 | `memory_lookup("SPT 量能 展望 纠偏")` | 不得标 `live_weekly` |

### 7.3 五日包与开口预取（P0）

夹具 5 个交易日，其中一天双红 0、一天主线有行、一天总量空。

| # | 输入 | 必须 |
|---|---|---|
| 15 | `end_date=2026-08-21`, `window=5` | 日期列表恰为 08-17…08-21 |
| 16 | 每日四袋收据 | `requested_date=served_date` 或 empty；双红是 COUNT |
| 17 | 08-19 夹具双红 0 且有板块行 | 「严格双红 0 个」，不是缺袋 |
| 18 | 总量袋含量能字段 | 公开稿若写量/MA20，数字来自该格 |
| 19 | `question_type=market_forecast` 的 Engine A 开口 | `_opening_prefetch_evidence` 或 `_seed_opening_prefetch` 之后的 opening evidence / episode 开场账本里已有五日包（周四主线袋在场或该袋 empty）。**不**断言 compose 路径出现 `WeeklyWatchPack`。**不**只查 `owner_output` 汇合处 |
| 19a | 同题但 `question_type` 仍是 `general_finance_qa` | forecast 预取支**不**跑（防双键）。这就是先修路由的锁 |

变异：只把包挂到 compose、opening evidence 仍只有 3 日双红个数 → #19 红。

### 7.4 隔板与残差（P0 / P1）

| # | 输入 | 必须 | 序 |
|---|---|---|---|
| 20 | 新闻 `2026-08-24`，库尖 08-21，稿写「已给部分验证」 | 删该分句 | P0 |
| 21 | 活周报写药为新主线，08-21 名单含医药，稿写「医药老主线」 | 删句或改写失败 | P0 |
| 22 | 稿写「110–120%」且袋/摘录均无该串 | 删句 | P1 |
| 23 | 视角 `neutral` | 活周报 `skipped`；五日包仍进 opening | P0 |

### 7.5 Live（干净树，新目录）

不覆盖 `four-arm-knevo-20260823/`，不覆盖冻结 run 目录。

| 题 | 过线 |
|---|---|
| 冻结原题 + 生产视角 `sptfei` | 回合层 `market_forecast`；opening evidence 含活周报 `date=max(article.date)` 与五日包；若引 SPT 文号则等于该日文章；2026.23 不得写成活剧本（除非 analog）；**公开稿可用**（§2）：非空、有直接判断或一条情景，不是 0 工具耗尽。允许 `partial` |
| 「展望一下A股后市」无视角 | 活周报 skipped；五日包仍在 opening；稿仍可用 |
| 「分析有色金属板块后续走势」 | 仍 `theme_analysis`，本单预取支不跑 |

不锁措辞像不像 SPT。不锁 8 月 24 日新闻叙事。不因为五件套里某槽 gap 就把整稿判红——要判的是「开口前包在、稿还能用」。

## 8. 落点与文件

| 文件 | 职责 | 序 |
|---|---|---|
| Modify: `intelligence/services/query_understanding.py` | 无序合取 | **独立 PR** P0-1 |
| Modify: `intelligence/tests/test_upstream_task_protocol.py` | §7.1 含 #9b | P0-1 |
| Modify: `intelligence/tests/test_query_understanding.py` / `test_answer_orchestrator.py` | 回归 #5–#8 | P0-1 |
| Create: `intelligence/services/perspective_live_weekly.py` | `bind_live_weekly`；禁止 import runtime / `asof_prefetch` | P0-2 |
| Modify: `intelligence/services/perspective_lab.py` | snippet 可被 analog 调用；问句 BM25 不再冒充活周报 | P0-2 |
| Create: `intelligence/services/weekly_watch_pack.py` | `run_weekly_watch_pack`；有则委托 `market_watch_pack` | P0-3 |
| Modify: `intelligence/services/asof_prefetch.py` | forecast 支改为格式化五日包；退役 3 日双红个数单支 | P0-4 |
| Modify: `intelligence/services/episode_tools.py` | `_opening_prefetch_evidence` 拼接活周报 / analog | P0-4 |
| Modify: `intelligence/runtime/agent_episode.py` | 只确认 `_seed_opening_prefetch` 仍先入账本；不改编号规则 | P0-4 |
| Modify: 交付闸 | 隔板「验证」句、无格数字、旧文号 | P0-4 / P1 |
| Test: `intelligence/tests/test_outlook_live_weekly_pack.py` | §7.2–7.4，**#19 打 opening evidence** | P0 |
| 收尾: `docs/prediction-ledger.md` | `R-20260824-20`…`24` | 收尾 |

不要改 `honesty_gates.py` 判定。不要把店名写进 `status != bound` 的用户可见前缀。
不要为了接线去改 `conversation_orchestrator` 的 compose 段——那是 (c)。(b) 若做，落点是 `handle()` **之上**，与 join 稿洞 1 同一符号。

## 9. 账本

编号避开 knevo28 已占的 `-11`…`19`。盘面包继续 `-01`…`06`。join kernel 从 `-25` 起。

| ID | 现象 | 类型 | 序 | 验证 |
|---|---|---|---|---|
| `R-20260824-20` | 句尾「行情的展望」任务链 `general_finance_qa`，评分链已是 `market_forecast` | `HARNESS_FIX` | P0-1 | §7.1 |
| `R-20260824-21` | 问句 BM25 / `memory_lookup` 把 2026.23 或纠偏当活剧本 | `HARNESS_FIX` | P0-2 | §7.2 |
| `R-20260824-22` | 空参快照只有库尖一日；预取只有 3 日双红个数 | `HARNESS_FIX` | P0-3 | §7.3 |
| `R-20260824-23` | 包挂 compose，Engine A 早退，开口看不到周四高潮 | `HARNESS_FIX` | P0-4 | §7.3 #19 |
| `R-20260824-24` | 无格阈值上桌；或路由加严后整稿变空 | `HARNESS_FIX` | P1 / §7.5 | §7.4 #22、§7.5 可用稿 |

禁止覆盖冻结 run 目录。禁止把 2026.34 文号写死——锁 `date=max(date)`。

## 10. 实施顺序

1. 从 `gitea/main` 开干净树。本脏树只许 pathspec 留 spec。
2. **先合盘面组件包**（若尚未合）：奠定 `run_market_watch_pack` + `=` 查询。它的 compose 椅是它自己的，本单不搬。
3. **P0-1 三链同型**：独立小 PR `fix/forecast-unordered-conjunction`。§7.1 #1 今日已红 → 无序合取 → #1–#9b 绿。两份展望/盘面稿都不要在自己的大 PR 里顺手改这份正则。
4. 活周报夹具红 → `bind_live_weekly` → #10–#14 绿。
5. 五日包夹具红 → `run_weekly_watch_pack`。有盘面包则委托。
6. **开口预取接线**：#19 红（opening 仍只有 3 日双红或为空）→ `collect_prefetch_items` + `_opening_prefetch_evidence` → #19/#19a 绿。**禁止**先改 Engine A prompt。**禁止**只改 compose。
7. 隔板闸 #20/#21。
8. P1：#22。Live：冻结原题必须**可用稿** + 回归「展望一下A股后市」。合 main 等用户确认。

反向执行的代价：

- 先包后路由：`collect_prefetch_items` 的 forecast 支不进（#19a），包函数测试绿、生产冻结题仍是 `general_finance_qa`。
- 先路由后只挂 compose：题型对了，包是死代码，opening 仍是 3 日双红个数。
- 两条都是假绿，和盘面稿 v1「先传 as_of、owner 还在 daily-review」同构。

推荐合入队列（与 knevo28 / join 错开 PR，不互斥）：

1. `market-watch-component-first` → main  
2. `fix/forecast-unordered-conjunction`  
3. 本单活周报 + 五日包 → 开口预取（可与 2 同树、分 commit）  
4. `personalized-join-kernel`（可与 3 并行；StancePack 走 `handle()` 前，V 退投影）  
5. knevo28 P0-A `PublicAnswerCompiler`（质量线，别混进本 PR）

## 11. 合入关系

- **盘面组件包**：共用每日四袋函数。**不共用** compose 椅。
- **join kernel**：同族「Engine A 早退」。本单椅子是开口预取（forecast 已有预取支）；join 椅子是 `handle()` 前（买卖题没有现成 prefetch 支）。两包都不要挂 compose。
- **knevo28**：台账号 `-11`…`19` 留给它。质量线与本单不互斥，别混 PR。
- **板块归因稿**：只动 forecast 正则，不要覆盖 cause 正则。
- **reading-rules / SPT 升格**：方法继续默认开。本单不把 2026.34 倾向写进 baseline。
- **激活收据稿 I8**：失败态禁止店名。

## 12. 自检

- 无 TBD。入口选无序合取。查询选 `=`。注入选 (a)。P0 不拒收 A。板块主语不扩。台账号从 `-20` 起。
- 判别变量是「开口前：题型 + 活周报日期键 + 五日包」，验收还押可用稿。
- 初判「模仿 SPT 改题型」已推翻。v1「同一汇合处」已推翻。
- 两套分类器必须一起绿。#19 只查 Engine A opening，不查 compose。
- 版权：摘录 ≤360。文号不写死。
- 视角平面不进 `asof_prefetch.py`。

## 13. 可搬走的形状

「现行版本走日期键，旧版本走 BM25 且必须标 analog」——客服知识库、法规、runbook 同构。BM25 负责找像的，日期键负责找现在的。面试里这是 structured access vs lexical retrieval。

残差只解释格冲突：编译器先出类型，模型只解释对不上的两行。

**Engine A 早退**：确定性包必须挂在 `handle()` 之前或开口预取上，不能挂在 `handled` 之后的 compose。盘面题用拒收换椅子；展望题用预取留在原椅。同一失败形状，两把合法椅子，抄错就变死代码。

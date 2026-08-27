# 设计：板块「为什么涨」必须进已有的 market_cause 契约

- 日期：2026-08-20
- 状态：已在 `/Users/a77/fwp-wt-market-cause-spec` 落地代码，**未提交**。合入须等质量稿 P0（尤其 T2）先合。
- v1 → v2：入口不是「只扩主语集合」；词序、电网设备锚点、验收分层、行号、与质量稿的合入顺序全部按 [实测] 改过。见 §0.1。
- 分诊：冻结 `run_20260820_161218_462670`（2026-07-23 A 股铝板块为什么涨）；报告契约 `REPORT_VALIDATE_RC:0`
- 引擎：**A**（`continuous_episode` + `question_type=market_cause`）。不把这类题送进 Engine B / `dated_market_review`
- 代码树：`/Users/a77/fwp-wt-market-cause-spec`（`docs/market-cause-sector-routing`，从 `gitea/main` @ `5d7529e5`）。禁止在主检出 `feat/reading-rules-baseline-batch1` 脏树上改
- 相邻稿：`docs/superpowers/specs/2026-08-20-episode-public-answer-quality-design.md`（质量稿）。**合入顺序见 §12，先质量 P0 再本单。**

## 0. 一句话

系统已经有「指定窗口涨跌原因」这条题型（`market_cause`），也已经有因果槽位和时间对齐的证据计划。卡住的不是「点菜员只认行情/大盘」这一条——**现役正则还要求 主语 → 涨跌 → 归因 的词序**，而真人问句大量是「为什么涨」。本单把入口改成 **归因 ∧ 涨跌 ∧ 主语锚点 的无序合取**，主语锚点再扩到板块后缀 / 题材包别名 / **QueryResolver 已解析的 `matched_theme`**。不换引擎、不改判官、不改合成 prompt。

**判别变量**（验收只锁这一条）：冻结题面在进入研究循环之前，`question_type` 必须是 `market_cause`，且 `required_outputs` 含 `causal_chain`。不是「多调一次工具」，不是「把稿子写好看」。

人话：厨房里因果菜谱已经印好了。点菜员不但词表窄，连语序都只认一种。本单改点菜规则，不重印菜谱、不换后厨。

### 0.1 v2 核稿改定（[实测]，实施按本节不是按 v1 的 §0/§1.1）

| ID | v1 会让实施卡住的地方 | v2 |
|---|---|---|
| **F1 词序** | 「扩展主语集合」按字面改正则，铝题仍红：`大盘为什么下跌` / `行情为什么走弱` 今日 `is_market_cause_query=False`；`大盘下跌的原因是什么` 才是 True。§5.1 五句里四句是「为什么涨」 | 入口是**无序合取**（§5 规则 1∧2∧3）。禁止只扩主语、保留 主语→涨跌→归因 |
| **F2 电网设备** | §5.1 列为必须命中且 `matched_by=="alias"`，但 `_theme_aliases()` 41 条**不含**「电网设备」。按 v1 规则 3 三选一，这句三个锚点全空，自相矛盾 | **不**加进题材包别名表（会改「电网设备怎么看」）；**不**在声明无 IO 的函数里查 `dim_sector`。第四锚点 = `understand_query(..., matched_theme=)` 已有参数，由 `QueryResolver._resolve_theme` 从知识库概念/别名关系解出。见 §5.0 |
| **F3 锁错层** | `液冷板块` 锁 `subject=="液冷"` 锁的是 `understand_query`；`decide_turn` / `build_task_frame` 吃的是 canonical `液冷温控`。电网设备「题材别名」归因错：`understand_query` 是 `general_finance_qa` / `subj=None`，`decide_turn` 才是 `theme_analysis` / `subj=电网设备`（另一条 resolver，不是 `_theme_aliases`） | 验收分两层：信封 vs 回合。见 §5.1 / §7 |
| **行号** | `:979` / `:1184` 系统性偏 101 行（`understand_query` 定义在 1023，979 不在函数内） | 以 §3 现役行号为准。结论「因果分支在别名之前」仍对（1080 < 1285） |
| **合入顺序** | v1 §1.2 写「等本单 replay 再动投影」 | **反了。** 质量稿 T2 是本单前置。单独先合本单，会把铝题的软缺口升级成每道板块归因必现的 `missing_mandatory_capability: news_search`。见 §12 |

顺带记账（v1 漏了）：§5.1「近一周大盘为什么走弱」今日是**红**的，不是路由表回归绿。`decide_turn` 降到 `lane=knowledge`、reason「Controller 不可用…按一般知识问题安全降级」。修好后从零检索变确定性研究，是本单一笔收益。

## 1. 范围

### 1.1 做

- 把 `is_market_cause_query` 从「一条有序正则」改成 §5 的无序合取。现役 `_MARKET_CAUSE_RE`（`query_understanding.py:300-307`）两条分支都是 `主语.{0,n}涨跌.{0,n}归因`，**「为什么涨」这种语序匹配不到**。
- `understand_query` 的 `market_cause` 分支保持**早于** `matched_theme` 的 `theme_analysis` 返回（`:1080`）和题材包别名循环（`:1285`）。电网设备那句今天在 **decide_turn 层**是 `theme_analysis`，修完必须在 **decide_turn 层**是 `market_cause`。
- 板块/别名/`matched_theme` 命中时写入 `subject`，避免 `build_task_frame` 把空主体填成「A股市场」（`:223-227`）。
- 离线锁死：§5.1 两层都测。`decide_turn(llm_complete=boom)` 不得为了分类去调 LLM。

### 1.2 不做

- 不把这类题改成 `dated_market_review` / Daily Agent / Engine B。日报工作流曾经按「日期 + 题材词」抢走取值题和双红题，现场更差（`market_timeseries.py` 注释、`_DATED_MARKET_TOPIC_RE` 刻意不收「题材/板块」）。
- 不在本单修「双红/连板」的戳记洞：`is_dated_market_review=True` 且 `lane=workflow`，但 `_decision()` 仍拷贝信封的 `general_finance_qa`。那是兄妹 bug，见 §10。
- 不在本单修 `prime_quote` 绑定类型（F-002）、截断 LIMIT、单位标签、公开稿美观。那些在质量稿；**本单不得抢在质量稿 P0（尤其 T2）之前合入**，见 §12。
- 不处理「2026-07-23 铝为什么涨」这种**没有**板块/题材/别名/`matched_theme` 锚点的商品歧义（`run_20260820_160914_079382`）。质量稿已标「本单不做」。
- 不把个股「XX为什么涨」收进 `market_cause`（走 `stock_deep_dive` / `news_impact`）。
- 不实施 `2026-08-05-intent-routing-candidate-arbitration-design.md` 的「LLM 否决权」。本单是确定性入口，与 `market_forecast` 认「明天怎么看」同一刀。
- 不改 `causal-anchor-guard` 的检索 fail-closed；板块 `subject` 只会让它更好锚，不放宽。
- 不改生产超时、judge 配额、模型。
- **不把「电网设备」写入 `_theme_aliases()` 的配置包。** 那张表是题材研究包的别名，加进去会让「电网设备怎么看」也走别名命中，副作用超出本单。
- **不给 `is_market_cause_query` 引入 DuckDB / `dim_sector` IO。** 它今日声明无 IO；盘面名单查表是另一条链。

## 2. 术语

| 词 | 含义 |
|---|---|
| **Engine A** | `continuous_episode`。模型自选工具，受 `TaskFrame` / episode 契约约束。`market_cause` 走这里。 |
| **Engine B** | `ask.answer_query` 写死流程。只接 `quick_fact` / `external_market` / `dated_market_review`。 |
| **market_cause** | 指定时间窗口内涨跌的原因归因。证据计划 `time_aligned_market_causal`（强制 `market_data` + **mandatory `news_search`**）。映射在 `task_frame.py:33` 与 `episode_factory.py:228-255`（`MARKET_CAUSE_NEWS` 在 239-245）。 |
| **general_finance_qa** | 「上游没认出来」的兜底，不是「确定是通用问题」。默认槽位只有 `direct_answer` + `evidence_boundary`。 |
| **theme_analysis** | 产业链/兑现阶段研究。槽位含 `chain_mapping`。适合「液冷怎么看」，不适合「某日为什么涨」。 |
| **dated_market_review** | 指定日的 A 股**全市场**复盘工作流（主线/涨停/双红等盘面专有词）。 |
| **`_theme_aliases()`** | `query_understanding.py:585` 从题材配置包读的 41 条（含「液冷」「固态电池」，**不含「电网设备」**）。只覆盖包装好的研究包，不是全市场板块名。 |
| **`matched_theme`** | `QueryResolver._resolve_theme`（`query_resolution.py:197-202`）用知识库 `entity_concept_names` + `aliases` 关系解出的 canonical。`understand_query` 已接收这个参数（`:1026`），今日在 `:1272-1282` 才用，且返回的是 `theme_analysis`。 |
| **信封层** | 单独调用 `understand_query(q)`（默认 `matched_theme=None`）。 |
| **回合层** | `decide_turn` → `QueryResolver.resolve` 先解 `matched_theme` 再调 `understand_query` → `build_task_frame`。下游 `build_task_frame` 吃的是这一层。 |
| **判别变量** | 本单因果链：入口分类 → `question_type=market_cause`。 |

## 3. 已核实事实（实施时不要再探一遍）

均为冻结 run 或同进程复放（核稿日 2026-08-20 在 `fwp-wt-market-cause-spec` @ `5d7529e5` 再测过）。行号以该树为准。

1. 冻结 run `run_20260820_161218_462670`：`trace.jsonl` `step_id=controller` 给出 `question_type=general_finance_qa`、`subject=null`、`required_outputs=[direct_answer, evidence_boundary]`、`reason=明确金融研究对象或决策目标`、`llm_failure_reason=""`。`research_status=partial`，`run.status=completed`。
2. 同进程 `understand_query(冻结题面)` → `general_finance_qa` / `cause=False`。对照句「这一周行情下跌的主要原因你认为是什么」→ `market_cause` / `cause=True`。
3. `decide_turn(冻结题面, llm_complete=boom)` **未调用 LLM**，仍返回 `lane=research` + 同上 reason。PRIMARY 不在 LLM 控制器。
4. `_MARKET_CAUSE_RE` 在 **300-307**。`understand_query` 定义在 **1023**；`:1080` 命中则直接返回 `market_cause`（此时 **subject 恒为 None**、`matched_by=market_anchor`）。题材包别名循环在 **1285**。因果在别名前（1080 < 1285）这个结论对；按 v1 的 979/1184 导航会落在函数外面。
5. 「2026-07-23 电网设备为什么涨」**两层不一致**（v1 事实 5 结论对、归因错）：
   - 信封层：`general_finance_qa` / `subject=None` / `matched_by=generic`
   - 回合层：`theme_analysis` / `subject=电网设备` / `lane=research`，reason「确定性识别到研究 owner 问题类型（theme-research）」
   - 不是 `_theme_aliases()` 命中。`_theme_aliases()` 共 41 条，不含「电网设备」。回合层走的是 `QueryResolver._resolve_theme` → `matched_theme` → `understand_query` 在 `:1272` 返回 `theme_analysis`。
6. `build_task_frame`：`market_cause` 且 `subject is None` 时把主体填成「A股市场」（**223-227**）。板块归因如果只改题型、不写 subject，工具会去查全市场。
7. `_decision(..., envelope=envelope)` 原样拷贝 `envelope.question_type`。因此只要信封已是 `market_cause`，后面的 `_FINANCE_PATTERN` 研究分支也会带上正确题型，不必给 `turn_controller` 再开一条因果专用分支。
8. `task_frame._default_required_outputs["market_cause"]` = `(direct_assessment, causal_chain, counterpoint, evidence_boundary)`。信封 operator 侧另有 `cause_attribution`；`derive_required_outputs` 会把 extra 合并进类型默认。验收锁 **`causal_chain` 在 frame 里出现**，不在本单统一两套词表。
9. `question_type=="market_cause"` 时证据计划换成 `time_aligned_market_causal`：`task_frame.py:33` 的 profile 映射 + `episode_factory.py:228-255` 的强制需求（`MARKET_CAUSE_WINDOW` = `market_data`，`MARKET_CAUSE_NEWS` = **mandatory `news_search`**）。`episode_tools.py:628` 起把 `required_source_start/end` 钉在市场窗口。题型对了，证据计划会跟着对——**这也是为什么 T2 必须先合**（§12）。
10. 冻结 run 的 traces 里 `market_data` / `mainline_context` 已是 `success`，结构核验仍报 missing（绑定类型）。这是 F-002，**本单不修**。
11. **词序 [实测]**：`大盘下跌的原因是什么` → True；`大盘为什么下跌` → False；`行情走弱的原因` → True；`行情为什么走弱` → False；`近一周大盘为什么走弱` → False（路由表 examples 今日红）；铝题 / 电网设备 / `液冷板块今天为什么涨` → False。
12. **液冷两层 [实测]**：信封层 `theme_analysis` / `subject=液冷` / `matched_by=alias`；回合层 `theme_analysis` / `subject=液冷温控`（canonical）。v1 §5.1 锁 `subject=="液冷"` 只能锁信封层。
13. `近一周大盘为什么走弱` 的 `decide_turn(boom)`：`lane=knowledge`，`question_type=general_finance_qa`，reason「Controller 不可用；按一般知识问题安全降级；TaskFrame 证据政策禁止零检索执行」。修好后应变 `lane=research` + `market_cause`。

## 4. 选型（写进 spec 以免实施时重开）

| 方案 | 做法 | 为什么选 / 不选 |
|---|---|---|
| **A. Engine A + 无序合取扩入口（本单）** | 归因∧涨跌∧（全市场名词 ∨ 层级后缀 ∨ 题材包别名 ∨ `matched_theme`） | 判别变量与分诊 PRIMARY 一致；电网设备从错误的 `theme_analysis` 拉回；不重蹈日报 over-routing；顺带修词序 |
| B. 改走 `dated_market_review` / Engine B | 送进日报工作流 | 铝题 `is_dated_market_review=False`，走这条根本碰不到 PRIMARY；且日报曾经抢走取值题 |
| C. 加厚 `general_finance_qa` 的证据计划 | 不改题型 | 两种任务共用一张契约，评分槽和工具继续拧巴；`market_forecast` 已经用「认对题型」修过同一形状 |
| D. 等 08-05 LLM 裁定层 | 规则只提候选 | 那份设计未实施；本句连 LLM 都没进控制器。等它等于把确定性洞留给模型碰运气 |
| E. 只扩 `_MARKET_CAUSE_RE` 的主语集合 | 把 `板块\|铝\|电网设备` 塞进现有有序正则 | **F1：PRIMARY 仍红。** 禁止 |

可迁移点：任何「题型 → 槽位 → 工具合同」的 agent，**入口分类失败时下游每一层都会正确履职错误任务**。表面症状是证据不足或 judge repaired。面试常问 intent classification 为什么必须在执行循环前冻结契约。

本仓已有同一形状：`_MARKET_FORECAST_RE` 补「明天怎么看」（`query_understanding.py:276-281` 注释）。本单换切面：归因从「全市场 + 一种词序」扩到「板块/题材 + 无序合取」。

### 4.1 F2 拍板：电网设备用哪条锚点（核稿三选，本单锁第三）

核稿只给了「加别名表 vs 查 dim_sector」。两者都有核稿自己写明的代价。本单**都不选**，锁已经存在的第三条：

| 选项 | 代价 | 本单 |
|---|---|---|
| 把「电网设备」写入 `_theme_aliases()` | 最省事；「电网设备怎么看」也会走别名命中，题材包行为被顺带改掉 | **不选** |
| `is_market_cause_query` 查 `dim_sector` | 更覆盖盘面名单；给声明无 IO 的函数引入数据依赖 | **不选** |
| **认 `matched_theme`（锁）** | QueryResolver 已经付过知识库 IO；`understand_query` 已经收这个参数，只是今日拿去返回 `theme_analysis`。因果分支提前消费它，不新增 IO、不改别名表 | **选** |

实施要点：`is_market_cause_query` 仍无 IO。第四锚点是**调用方传入的** `matched_theme`（或 `understand_query` 在 `:1080` 判断时读取已有参数）。单独 `understand_query("电网设备为什么涨")` 无参数时可以继续不命中；`decide_turn` 必须命中。这不是缺口，是分层（F3）。

## 5. 真值表（实施不得改行，只能改实现）

函数：`is_market_cause_query` + `understand_query`。前者保持无 IO；`matched_theme` 只作为可选参数，不在函数内查库。`decide_turn(..., llm_complete=boom)` 不得为了这些题面去调 LLM。

命中规则（**无序合取**：1 ∧ 2 ∧ 3，顺序不限）：

1. 归因动词：`为什么|原因|驱动|归因`（已有）
2. 涨跌事件：`涨|跌|走强|走弱|上涨|下跌|回撤`（已有；**不含**「是主线」「怎么看」「产业链」）
3. 主语锚点，**四选一**：
   - 全市场名词：`行情|大盘|市场|指数`（现有，保持）
   - 层级后缀：`板块|题材|行业`
   - `_theme_aliases()` 中的别名出现在去空白后的问句里
   - **`matched_theme` 非空**（由 QueryResolver 传入；本单不在此函数内解析）
4. 排除：问句能被现有公司锚点认成个股（ticker / `EntityAnchor` / `_explicit_company_subject`）时，**不得**因「为什么涨」改成 `market_cause`

实现约束：

- **禁止**只改 `_MARKET_CAUSE_RE` 的主语组、保留 主语→涨跌→归因。那条正则可以删、拆、或降为全市场快路径，但合取语义以本节为准。
- `understand_query` 在 `:1080` 必须能看到 `matched_theme`，否则电网设备会继续掉进 `:1272` 的 `theme_analysis`。

### 5.0 信封层：`understand_query` 命中后的字段

| 主语锚点 | `question_type` | `subject_kind` | `subject` | `matched_by` |
|---|---|---|---|---|
| 仅全市场名词 | `market_cause` | `market_pattern` | `None`（交给 `build_task_frame` 填「A股市场」） | `market_anchor` |
| `…板块/题材/行业`（无 `matched_theme`） | `market_cause` | `theme` | 去掉后缀后的名称：`铝板块` → `铝` | `explicit` |
| 仅题材包别名（无 `matched_theme`） | `market_cause` | `theme` | 命中的别名原文（如 `液冷`） | `alias` |
| 别名与后缀同时出现（`液冷板块`，无 `matched_theme`） | `market_cause` | `theme` | 别名原文 `液冷` | `alias` |
| 调用方传入 `matched_theme`（如电网设备） | `market_cause` | `theme` | **canonical**（传入值，如 `电网设备` / `液冷温控`） | `candidate` |

`operators` 仍追加 `cause_attribution`。`timeframe` 仍由现有 `_DATE_RE` / 相对周词解析。

`matched_by=candidate` 沿用今日 `matched_theme` → `theme_analysis` 那条已经在用的值（`:1280`）。不要为电网设备发明 `alias`——它不在 41 条里。

### 5.1 必须命中（分两层锁；不要把信封层的字段抄到回合层）

**信封层** `understand_query(q)`（默认无 `matched_theme`）：

| 问句 | 锁什么 | 今日实测 | 修后 |
|---|---|---|---|
| 这一周行情下跌的主要原因你认为是什么 | 回归：现有测试不得红 | `market_cause` | 保持 |
| 大盘为什么下跌 | 词序（F1） | `cause=False` | `market_cause`，`subject is None` |
| 行情为什么走弱 | 词序（F1） | `cause=False` | `market_cause`，`subject is None` |
| 近一周大盘为什么走弱 | **今日红，不是回归绿** | `general_finance_qa` | `market_cause` |
| 2026-07-23 A股铝板块为什么涨，给出证据来源 | 冻结 PRIMARY | `general_finance_qa` | `market_cause`，`subject=="铝"`，`matched_by=="explicit"` |
| 液冷板块今天为什么涨 | 信封层 subject | `theme_analysis` / `液冷` / `alias` | `market_cause`，`subject=="液冷"`，`matched_by=="alias"` |
| 2026-07-23 电网设备为什么涨，给出证据来源 | **信封层允许不命中** | `general_finance_qa` / `subj=None` | 仍可以是 `general_finance_qa`。要测电网设备请用下一张表 |

**信封层带参数** `understand_query(q, matched_theme="电网设备")`：

| 问句 | 锁什么 |
|---|---|
| 2026-07-23 电网设备为什么涨，给出证据来源 | `market_cause`，`subject=="电网设备"`，`matched_by=="candidate"`。禁止再要求 `alias` |

**回合层** `decide_turn(q, llm_complete=boom)`（这才是研究循环入口）：

| 问句 | 锁什么 | 今日实测 | 修后 |
|---|---|---|---|
| 近一周大盘为什么走弱 | 从零检索拉回 | `lane=knowledge` / `general_finance_qa` | `lane=research`，`question_type=market_cause`，frame 含 `causal_chain`，boom 不触发 |
| 2026-07-23 A股铝板块为什么涨，给出证据来源 | PRIMARY | `lane=research` / `general_finance_qa` / `subj` 空或非铝 | `market_cause`，`frame.subject=="铝"`（不得是「A股市场」），含 `causal_chain` |
| 2026-07-23 电网设备为什么涨，给出证据来源 | 从错误的 theme_analysis 拉回 | `theme_analysis` / `电网设备` | `market_cause`，`frame.subject=="电网设备"`，含 `causal_chain`。**不要**锁 `matched_by=="alias"` |
| 液冷板块今天为什么涨 | 允许 canonical | `theme_analysis` / `液冷温控` | `market_cause`，`frame.subject in {"液冷", "液冷温控"}`，含 `causal_chain`。**不要**锁成恰好 `"液冷"` |

### 5.2 必须不命中（两层都不得是 `market_cause`）

| 问句 | 仍应是 |
|---|---|
| 固态电池为什么是主线 | 不得 `market_cause`（无涨跌事件） |
| 液冷怎么看 / 液冷服务器题材：产业链怎么拆解 | `theme_analysis`（有别名/matched_theme，但无涨跌事件） |
| 电网设备怎么看 | `theme_analysis`（本单不因 F2 把怎么看改成因果） |
| 2026-07-23 收盘，盛新锂能怎么看 | `stock_deep_dive` |
| 立新能源为什么涨 | 个股，不得 `market_cause` |
| 2026-02-17 涨停家数多少 | `quick_fact`（取值，不是归因） |
| 2026-07-23 连板梯队什么情况，有没有断层 | 不是本单；见 §10 |
| 什么是双红，现在哪些板块双红 | 不得变 `market_cause`，也不得变 `dated_market_review` |
| 2026-07-23 铝为什么涨，给出证据来源 | 本单不强制（无板块后缀、不在 41 别名、QueryResolver 若解不出 theme 则保持现状） |

## 6. 落点

改动面刻意小。新行为是入口分类，不是新流水线。

| 文件 | 职责 |
|---|---|
| `intelligence/services/query_understanding.py` | `is_market_cause_query` 改为无序合取；`:1080` 消费 `matched_theme` 并写入 subject |
| `intelligence/tests/test_query_understanding.py` | §5.1 信封层表（含词序两句、铝、液冷、电网设备带参、电网设备不带参允许不命中） |
| `intelligence/tests/test_turn_controller.py`（或同目录新短测） | §5.1 回合层：铝 / 电网设备 / 液冷 canonical / 近一周大盘为什么走弱 |

本单 **不改**：`episode_factory.py` 的 mandatory `news_search`（那是已有契约，T2 负责让它回得了内容）、`turn_controller._decision` 签名、判官、投影。`route_table` 的 `market_cause` examples 已含「近一周大盘为什么走弱」——修好后它会从红变绿，不必为了本单改表；可追加铝/电网一句，非必须。

## 7. 验收

合并闸是离线测试，不要求重放 live 才能合入。**合入本单之前，质量稿 P0 的 T2 必须已在可合入状态**（§12）；本单测试本身不替代 T2。

1. `test_weekly_market_cause_has_window_and_causal_output` 仍绿。
2. 新增：冻结铝题 **信封层** `understand_query` → `market_cause`，`subject=="铝"`，`matched_by=="explicit"`；经 `build_task_frame` / `derive_required_outputs` 出现 `causal_chain`。
3. 新增：电网设备 **信封层不带参** 不强制 `market_cause`。**带参** `matched_theme="电网设备"` → `market_cause`，`subject=="电网设备"`，`matched_by=="candidate"`（禁止 `alias`）。
4. 新增：§5.2 至少含「固态电池为什么是主线」「立新能源为什么涨」「液冷怎么看」「电网设备怎么看」四句。
5. 新增：铝题 / 电网设备题 `decide_turn(llm_complete=boom)` 不抛、`question_type=="market_cause"`；电网设备 `frame.subject=="电网设备"`；液冷 `frame.subject in {"液冷", "液冷温控"}`。
6. 新增：`大盘为什么下跌`、`行情为什么走弱`、`近一周大盘为什么走弱` 信封层为 `market_cause`；最后一句回合层 `lane=research`（不得再是 knowledge 降级）。
7. 合入前：`.venv-workbench/bin/python -m pytest -q intelligence/tests/test_query_understanding.py intelligence/tests/test_turn_controller.py`。

Live canary（不合入闸，合入后另拍）：同一铝题。期望 controller 摘要里 `question_type=market_cause`。公开稿好不好看、`prime_quote` 是否仍报 `finance_query`，记观察，不作为本单失败。**若 T2 未合就 live，结构核验出现 `missing_mandatory_capability: news_search` 算顺序错误，不算本单入口没修好。**

## 8. 预测（合入后回填 ledger）

建议新开一条，不要占用现有 Open 行：

- `verification_prediction`：冻结铝题面 `understand_query.question_type == "market_cause"`，且 `decide_turn(llm_complete=boom).task_frame.required_outputs` 含 `causal_chain`。
- 怎么验：§7.2 + §7.5。
- `fix_type`：`ROUTING_FIX`。
- 次预测（v2 补记账）：`近一周大盘为什么走弱` 的 `decide_turn.lane == "research"` 且 `question_type == "market_cause"`。
- 单次 live 不得结案。

## 9. 与相邻稿的边界

| 稿 | 关系 |
|---|---|
| 本分诊 PRIMARY | 本单落地 |
| `2026-08-20-episode-public-answer-quality-design.md` | 投影修好后的取数/单位/残句。**P0（T1/T2/T3）是本单前置**；本单合入后质量稿 §6.2/§6.3 必须认 `market_cause`，Q3 铝夹具要重冻。见 §12 |
| `docs/judge-evidence-projection-contract-spec.md` | 判官入参。F-002 等本单 replay |
| `2026-08-05-intent-routing-candidate-arbitration-design.md` | 未实施的 LLM 否决层。本单不依赖 |
| `2026-07-29-causal-anchor-guard-design.md` | weekly `market_cause` 检索 fail-closed。本单不放宽 |

## 10. 下一单（本文件不实施）

**日报意图已命中、题型戳记没落下。** 复放：

```
decide_turn("2026-07-23 连板梯队什么情况，有没有断层")
→ lane=workflow reason=明确请求指定日期的 A 股行情复盘
→ question_type 仍是 general_finance_qa / concept_definition
```

根因：`_decision()` 拷贝 `envelope.question_type`，而 `is_dated_market_review` 并不回写信封。Engine B 只认 `dated_market_review` 这个字符串，于是工作流车道 + 通用契约，连续 episode 仍可能接走。

修法候选：命中 `is_dated_market_review` 时显式 `question_type="dated_market_review"`，不要从信封拷。独立真值表、独立测试。不要和本单揉进一次 PR——铝题根本走不到这条分支。

## 11. 实施顺序（本单内部，TDD）

1. 确认质量稿 P0/T2 已合或至少已在独立 PR 且可合（§12）。未满足则**停在本文件，不要开实现 PR**。
2. 红：先写 §5.1 两层测试。确认铝（词序+后缀）、`大盘为什么下跌`、电网设备（不带参 vs 带参 vs decide_turn）、液冷 canonical 今日失败形状与表一致。
3. 绿：只改 `query_understanding.py` 的合取与 `:1080` 返回的 subject / matched_by。
4. 确认 `decide_turn(boom)` 已绿；若否，再查是 `_safe_subject` 丢掉了 subject，而不是去改控制器。
5. 不顺手改投影、judge、日报戳记、别名配置包、`episode_factory` 的 mandatory news。

## 12. 与质量稿的合入顺序（硬约束，跨 PR）

`market_cause` 的证据计划把 `news_search` 设成 **mandatory**（`episode_factory.py:239-245`），并把 `required_source_start/end` 钉死在市场窗口（`episode_tools.py:628` 起）。冻结铝题锚定 2026-07-23（周四）→ 窗口约 2026-07-20 .. 2026-07-23；该 run 实际拿到的 news 是 2026-08-17/18，**全部窗口外**。质量稿 R-20260820-07 / T2 正是「时点归因题的资讯检索被自身 as_of 全滤成 0 条」。

| 阶段 | 内容 | 理由 |
|---|---|---|
| **1** | 质量稿 **P0 全部**（T1 截断 / **T2 news cutoff** / T3 单位） | 与本单几乎零文件冲突（`finance_query` / `episode_tools` / `market_news` vs `query_understanding`）。T2 是本单前置 |
| **2** | 本单（本稿，F1–F3 已改定） | 此时 news 能回内容，`time_aligned_market_causal` 才立得住 |
| **3** | 质量稿 **P1**（Q1 / Q3） | 夹具依赖路由后的 `question_type` 和新 draft |

**单独先合本单的失败形状**：铝题现在是一次「软缺口」（模型调了 news、被滤空、稿子诚实写 gap）。路由让 news 变成必答题，T2 是那道题唯一能有答案的前提。合完本单、T2 未合 → 每道板块归因题必现 `missing_mandatory_capability: news_search`。

阶段 3 放最后的具体原因：质量稿 Q3 夹具是铝题那份 384→43 字的 draft，产在 `general_finance_qa` 下。本单合入后槽位从 `[direct_answer, evidence_boundary]` 变成 `[direct_assessment, causal_chain, counterpoint, evidence_boundary]`，证据计划也换了，那份 draft 不再有代表性。现在冻它等于冻一个即将作废的形状。

质量稿必须同步改、且**不必等本单代码**：

- §6.2 `ASKED_DATE_COVERAGE_TYPES` 加入 `market_cause`。否则路由后铝/板块归因会从「盘面研究集」掉出去，Q2/Q3 题型闸门不再触发。
- §6.3 残稿真值表「盘面研究集（铝现场）」同理；并注明现夹具是路由前形状，阶段 3 重冻。

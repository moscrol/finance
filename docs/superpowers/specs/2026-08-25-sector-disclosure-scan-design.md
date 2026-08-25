# 设计：板块个股利好公告由扫描包当第一执行者

- 日期：2026-08-25
- 状态：Draft **v1.3**（P0 #387 / P0.5 #392 已合已切；P1-① 残差写手已实施待合）
- v1.2 → v1.3：P1-① 残差写手落地（实施计划 `docs/superpowers/plans/2026-08-25-disclosure-scan-p1-residual-writer.md`）——`status=hit` 且有主名单行时 bind 保留调用方 `compose`，模型经 `contract_guidance` 槽持残差契约只写解读；出稿过 `gate_disclosure_residual`（包外码/名单行形状整丢回 P0 形状 + degrade `disclosure_residual_dropped:*`，超预算声明式截断）；名单置顶仍靠裁判后合并，两处 merge 未动。P1-②（PDF 品种金额）/ P1-③（自定义窗口）未做。
- v1.1 → v1.2：生产探针 `run_20260825_155459_372046` 主名单已齐，但开篇写「查询未跑完」、公开稿被附录回购逐条淹没。三条回写——(1) `partial` / 「查询未跑完」只由**主名单词**截断或跳过触发 (2) `excluded` 公开稿每档最多 3 条，其余计数进收据 (3) `L_reg` 不再吃「药品注册受理 / 注册证」宽词。残差写手仍 P1。
- v1 → v1.1：核稿确认方案 A 是五个候选里唯一同时守住「名单可复现、不拆题材 L3 闸、不放松裁判」的。补四条实施前必写死的条款——(1) 巨潮分页/墙钟预算与 `partial` 语义 (2) 宇宙站立日 `trade_date <= as_of` 且 CI 禁连生产库 (3) 增持档 + unclassified 兜底进 `excluded` (4) P0 纯包渲染，`RouteRow` 三字段拍死，残差写手整体挪 P1。小注进 §11，不挡本稿。
- 来源：生产 8792 live 题「医药和科技板块有哪些个股有比较利好的公告」（`run_20260825_141736_374807`，14:17–14:19）+ 同题人工对照（巨潮关键词 ∩ DuckDB 成分股，窗口 2026-08-20~2026-08-25）。核稿复验 2026-08-25：`gitea/main@be67eb27`、生产码 `af71f048`、本地 DuckDB 2026-08-24 published 快照。
- 网页真源：`~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260825_141736_374807/`（`continuous-episode.json` / `report.json` / `answer.md`），不是 UI 摘要条。
- 代码树：从 `gitea/main` 开干净树 `feat/sector-disclosure-scan`。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树上改 runtime。**禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做、不抢合）：
  - `2026-08-24-market-watch-component-first-design.md`（换座位：组件包先跑。本单抄这个座位，不改四袋。**不可**照抄 `merge_into_public_answer` 的 `market_daily_empty → 不合并` 分支，见 §5.6。）
  - `2026-08-24-workbench-quality-residual-ux-design.md`（D2/D4：组件加菜，不是模型加时；不碰 tier / 停机条件）
  - `intelligence/services/l3_evidence.py`（现役 `l3_lookup` 是**按公司**查巨潮/互动易，不是按板块扫名单。本单不把它扩成全市场循环。）
  - `intelligence/workbench_skills/research_owner.py` `THEME_RESEARCH.use_l3_lookup=False` / `NEWS_IMPACT.use_l3_lookup=True`（设计决定，本单不翻转题材开关。）

## 0. 一句话

「某板块有哪些个股刚出了比较利好的公告」是**名单扫描题**，不是题材研究，也不是「某条已知公告有什么影响」。生产把它送进题材车间，车间没有板块级公告电钻，质检又不许用东财标题充数，于是交了一份空壳，界面还写「已完成 / 0 缺口」。

本单加一个确定性扫描包：成分股宇宙 ∩ 巨潮关键词 ∩ 标题分层。**P0 公开稿就是包渲染**（`compose=False` / `synthesize=False`），名单段合并在裁判之后，所以裁判削句削不到包行。残差写手（集采双重性、标题缺品种）整体挪 **P1**。

**判别变量**（验收只锁这一条）：冻结题「医药和科技板块有哪些个股有比较利好的公告」、`as_of=2026-08-25`、窗口含 2026-08-20~08-25 时，公开稿必须出现至少一行带六位代码的巨潮标题（医药侧须能点到「药品注册证书 / 注册批准」类；科技侧若窗口内只有合同/中选须如实分层，不得用回购进展冒充经营利好）。不得再交「无法给出经过核验的个股利好公告名单」那种骨架——**当巨潮对该窗口、该宇宙确实有命中时**。零命中时允许交白卷，但必须带扫描收据（查了哪些词、宇宙多大、窗口哪几天），且界面不得显示「0 项限制/缺口」。P0 不要求稿子里出现模型残差段。

人话：客人要的是「这两桌今天上了哪些新菜」。后厨却按「帮我研究一下这两道菜系」去做，冰箱里又没有菜单原件，质检把小道消息划掉，端出空盘还说厨房运转正常。本单让菜单扫描先出锅；P0 连厨师边注都不开，避免边注把整桌超时吃光。

## 1. 范围

### 1.1 做

- 新增题型 `disclosure_scan`（路由表一行），描述「板块/行业范围内、近期官方披露里哪些个股有偏利好的公告名单」。例句必须包含本单冻结题。
- 该题型进 `DETERMINISTIC_OWNER_TYPES`：Engine A（`continuous_episode`）拒收，不让模型自选 `news_search`。
- 汇合处（`if owner_output is not None` **之前**，与盘面包同一座位）跑 `run_disclosure_scan_pack(...)`。包是 services 层纯函数，禁止 import runtime。
- **P0 纯包渲染**：绑定后 `compose=False`、`synthesize=False`（抄盘面包 `pack.should_stop` 那个座位，但本包**无论 hit/empty/partial 都关合成**）。公开稿 = 包 `render()`。残差写手不在 P0。
- 双主语保留：问「医药和科技」就必须扫两个宇宙，禁止 `subject` 塌成只剩第一个名词。
- 利好是标题分层，不是涨跌。注册证 / 临床批件 / 经营合同·中选 / 回购进展 / 增持 / 集采中选 / 未分类 分档；主名单只收前三档。
- 研究缺口必须能被 UI 看见：包 `status ∈ {empty, unsupported, error, partial}` 或「某桶零命中」，不得只靠 `run.degrades=[]` 显示「0 项限制/缺口」。
- 巨潮查询有硬预算（§5.3）。超时不是整轮挂死，是 `partial` + 已得行 + 缺口灯。
- 冻结夹具以本单 live 题 + 2026-08-20~08-25 巨潮命中为金标准形状（见 §3、§6），不把「稿子像不像 ReAct」写成验收。

### 1.2 不做

- **不**把 `THEME_RESEARCH.use_l3_lookup` 改成 True。题材研究关 L3 是防每道板块题扫全市场公告；本单换座位，不拆那道闸。
- **不**把本题改路由成 `news_impact`。`news_impact` 的合同是「已知事件/公告对公司或板块的冲击」，要的是传导链，不是扫描名单。其正则是 `(公告|新闻|消息|事件).{0,12}(影响|冲击|利好|利空)`，冻结题里「利好」在「公告」之前，对不上。
- **不**把现役 `l3_lookup` 拿来对宇宙里 1500 只股票逐个查。它是 `lookup_l3_company`（按公司），不是板块扫描。逐票循环会打爆巨潮限流，也答不了「有哪些」。
- **不**把东财新闻、`fact_event_daily` 展会日历、研报当作一手公告。P0 公开稿不得出现新闻 URL。
- **不**读 PDF 正文当 P0（恒瑞具体品种、赛意合同金额是 P1）。P0 锁标题级可核对名单。
- **不**在 P0 开残差写手 / 通用 ask 检索。`answer_owner=None` 的 else 分支若仍走通用检索，会被空 `capabilities` 和 `compose=False` 双重挡住。
- **不**用概念板「芯片」918 只当科技宇宙。P0 宇宙见表 §5.2。
- **不**放松语义裁判让二手新闻冒充已核验名单。
- **不**改生产超时、不改 8792/8796、不在脏树改 runtime。
- **不**把「列出今日全市场利好」做成无板块约束的全 A 股扫描（无宇宙 = 不做）。
- **不**把无外呼红线误读成「巨潮也不能碰」。那条防的是 fupanhui / iFinD 授权源与写回；巨潮公开只读，且 `news_search` 本就在外呼。**正因为包层第一次把网络 IO 放进盘面包那个同步绑定座位**，§5.3 的失败语义是一等公民，不是附录。

## 2. 术语

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **名单扫描题** | 要的是「哪些股票 + 什么公告」，主语是板块/行业集合 | 题材阶段判断；单条公告冲击分析 |
| **扫描包** | 确定性：宇宙 → 巨潮关键词 → 标题分层 → 收据。零模型参与查询 | `l3_lookup` 按公司补查；`news_search` |
| **宇宙** | `trade_date <= as_of` 的最大交易日、`fact_sector_stock_daily`（published VIEW）里点名板块的成分股六位代码集合 | 概念板弱相关名单；新闻里出现过的公司名；「库里全局 max(trade_date)」 |
| **一手公告** | 巨潮 `hisAnnouncement/query` 返回的 `secCode` + `announcementTitle` + `announcementId` + 日期 | 东财标题搜索；午间公告汇总稿 |
| **利好分层** | 对标题做事件类型分档，主名单只收经营/注册类 | 当日涨跌；「回购/增持」一律算利好 |
| **残差** | P1 才有：模型解释分层理由、双重性、标题缺字段；不能增删代码行 | P0 公开稿的一部分 |
| **研究缺口** | 包收据 `empty` / `partial` / 某宇宙零命中 / 预算截断 | runtime `degrades[]`（工具挂了才进） |
| **partial** | 预算或分页触顶时带着已得行收工 | 整轮超时；empty（真的零命中） |

## 3. 已核实事实（2026-08-25，实施时不要再探一遍）

现场 run：`run_20260825_141736_374807`。生产码 `8792=af71f048`。核稿对照 `gitea/main@be67eb27`。

1. **路由**：`question_type=theme_analysis`，`answer_owner=theme-research`，`subject="医药"`，科技被丢掉。`confidence=0.98`。落点 `turn_controller.py`「确定性识别到研究 owner 问题类型」。问句同时有「板块」和「公告」，被主语「板块」吸进题材行。
2. **`news_impact` 也对不上**：路由表示例是「宁德时代最新公告有什么影响」。`research_contract.py` 正则逐字为 `(公告|新闻|消息|事件).{0,12}(影响|冲击|利好|利空)`。冻结题「利好」在「公告」之前，匹配不上。否决 C 成立。
3. **合同没授权公告工具**：现场 `allowed_capabilities` 无 `l3_lookup`。`THEME_RESEARCH.use_l3_lookup` 在 main 与 `af71f048` 都吃 dataclass 默认 `False`，被 `test_workbench_research_owner_skills.py:303` 锁死。否决 B 成立。
4. **现役 `l3_lookup` 是按公司的**：`l3_evidence.lookup_l3_company(company: str, sources=("cninfo",))`。`detect_l3_gaps` 硬词表无「公告/获批/注册」。否决 E 成立。
5. **座位形状如稿**：`DETERMINISTIC_OWNER_TYPES`（现有 4 个题型）在 `intelligence/runtime/continuous_turn_adapter.py:104`，约 283 行命中即 `_declined_result()`。盘面包在 orchestrator 约 2810 一带按 `question_type == "market_watch"` 绑定、`owner_output` 分叉之前。`merge_into_public_answer` 被调用两次（draft 约 2981、最终 `answer_text` 约 3102），幂等前置拼接。P0 拒收 Engine A 后，出事的「judge repaired → 骨架」路径不再经过；名单不可删靠的是**合并放在裁判之后**，不是给包行发免检证。
6. **实际调用（live）**：东财 `news_search` ×2；`kb_search` 超时；`finance_query` 打到 `fact_event_daily`（展会/英伟达财报）。不是 runtime 降级：`degrades=[]`，`judge_status=repaired`。UI「0 项限制/缺口」读 `degrades[]`。
7. **宇宙映射实测**：§5.2 的 13 个板块名在 2026-08-24 published 快照全部存在；医药桶 512、科技桶 1046。§3.8 金标准个股（含华北制药、华勤技术、中关村）都落在 P0 宇宙内。
8. **同题人工对照（巨潮 ∩ 宇宙，窗口 08-20~08-25）可列出名单**，不是数据真空。医药硬事实包括：恒瑞医药 `600276` 药品注册批准（08-21）、双成药业 `002693` 注射用硫酸多黏菌素B 注册证（08-22）、新华制药 `000756` 达格列净片注册证（08-22）、福元医药 `601089` 两张注册证（08-22）、康希诺 `688185` 吸附破伤风疫苗注册证（08-21）等。科技能站住的是赛意信息 `300687` 高性能算力服务销售合同（08-20）、天邑股份 `300504` 中选通知书（08-24）。华勤技术回购进展、方直科技注销回购、天地数码激励回购调价**不应**进「比较利好」主名单。华北制药同窗口有撤回注册申请，不得只报临床批件。中关村集采中选不默认利好。该窗口巨潮「业绩预增」为 0 条。
9. **巨潮全市场关键词可用、且必须按交易所 column 去重**：`column=szse` 与 `sse` 会对同一 `announcementId` 打两遍。P0 不要对宇宙逐票 POST。
10. **东财公告 JSON 镜像不可当 P0 真源**：`np-anotice-stock.eastmoney.com` 现场 567。一手只认巨潮。
11. **缺口灯有先例**：`add_degrade(run_id, "market_watch_pack_stop")` 与 delivery gate 降级已在用，G7 可实现。
12. **盘面包那个绑定座位是本地 DuckDB 毫秒级**。本包是第一次把网络 IO 放进去。不设分页/墙钟预算会把整个 turn 吃光，制造一种新的超时失败形状——这是 v1 最大的洞，v1.1 用 §5.3 补上。

## 4. 方案对比

| 方案 | 做法 | 得 | 失 / 判 |
|---|---|---|---|
| **A. 新题型 + 扫描包先跑（采用）** | `disclosure_scan` 拒收 Engine A；汇合处跑宇宙∩巨潮∩分层；P0 纯包渲染 | 覆盖已观察失败形状；查询可复现；不拆题材 L3 闸；不经过 judge-repair 骨架路径 | 只救注册过的名单题；「公告怎么看」仍走 news_impact |
| B. 题材研究打开 `l3_lookup` | `THEME_RESEARCH.use_l3_lookup=True` | 改动面小 | 座位仍是产业链模板；L3 按公司；破坏「题材不扫公告」闸。否决 |
| C. 改路由到 `news_impact` | 靠现成 owner + L3 | 少一个题型 | owner 要传导链不是名单；正则对不上。否决作 P0 |
| D. 放松裁判保住新闻草稿 | 允许二手标题进名单 | 稿子看起来有名字 | 把东财汇总当成已核验公告。否决 |
| E. 对宇宙逐票 `l3_lookup` | 512+1046 只各查一遍 | 接口眼熟 | 限流、超时、预算必炸。否决 |

追上天花板 = 换座位 + 汇合处跑包。不是给 Engine A 加一句「请先查公告」，也不是把质检再收紧一档。

## 5. 目标态

```
问句命中 disclosure_scan
  → Engine A 拒收
  → 汇合处 run_disclosure_scan_pack(query, as_of)
       → 解析板块主语（可多个）+ 日期窗口
       → DuckDB 宇宙（published 成分股，universe_date = max(trade_date) WHERE trade_date <= as_of）
       → 巨潮关键词检索（无 stock 过滤，seDate=窗口，ID 去重，§5.3 预算）
       → 与宇宙 JOIN（secCode 对 stock_ts_code 前 6 位）
       → 标题分层；主名单 / excluded / 反证
       → DisclosureScanPack 收据（hit | empty | partial | unsupported | error）
  → compose=False, synthesize=False
  → 公开稿 = 包渲染（标签先行）
  → merge_into_public_answer 在裁判之后（空窗也必须合并收据句）
```

### 5.1 路由

新增 `RouteRow`，三字段与车道 **拍死**（v1 没写，会让 else 分支溜去通用 ask）：

```
route_id="disclosure_scan"
description="板块/行业范围内，近期官方披露里哪些个股有偏利好公告的名单扫描"
examples=(
    "医药和科技板块有哪些个股有比较利好的公告",
    "最近医药有哪些公司出了利好公告",
    "电子板块近一周中标或合同公告有哪些",
)
lane="research"
question_type="disclosure_scan"
answer_owner=None
needs_retrieval=True      # 包自己查库+巨潮；不是让 generic ask 去 news_search
needs_template=True
capabilities=()           # 空元组。禁止 news_search / web_search / kb_search / l3_lookup
```

`capabilities=()` 是 G2 的硬锁：就算 `answer_owner=None` 掉进通用 ask，合同里也没有新闻工具可调。绑定座位仍必须在通用检索**之前**把包跑完并 `compose=False`。

进 `DETERMINISTIC_OWNER_TYPES`。识别优先于题材：问句同时含板块类主语 **和** （公告|披露|中标|获批|注册证） **和** （哪些|哪家|个股|公司名单）时，选本行，不要因为有「板块」就进 `theme_analysis`。落点：`turn_controller.py` 现役「确定性识别到研究 owner」那句。

**不得**命中：

- 「宁德时代最新公告有什么影响」→ 仍 `news_impact`
- 「固态电池这个题材还能不能追」→ 仍 `theme_analysis`
- 「今天市场怎么样」→ 仍 `market_watch`

双主语：`primary_subject` 不够就用 `secondary_topics` 或包内自己解析。**禁止**只把第一个「医药」当宇宙。

### 5.2 宇宙

**站立日（v1.1 改定）**：`universe_date = max(trade_date) WHERE trade_date <= as_of`。禁止「库里全局最大 trade_date」——冻结题回放会随库前进而漂移，还会把 `as_of` 之后的成分股未来泄漏进宇宙。`as_of` 之前一行都没有：包 `status=unsupported`，收据写明「as_of 之前无成分股快照」，不回落邻日以外、不取未来日。

公告窗口 `seDate` 与 `universe_date` 可以差几个日历日，收据分开写。默认窗口：`as_of` 往前 5 个日历日（含当日）。

P0 别名表（名称精确匹配 `sector_name`，不用模糊「芯片」）：

| 用户说法 | 宇宙 `sector_name` |
|---|---|
| 医药 | `医药` ∪ `医药医疗` ∪ `生物制药` ∪ `医疗器械` ∪ `医疗服务` ∪ `医药商业` |
| 科技 | `电子` ∪ `计算机` ∪ `软件服务` ∪ `通信` ∪ `通信设备` ∪ `半导体` ∪ `消费电子` |

**单板块直通**：用户词**精确等于**某个 `sector_name` 时（例句 3「电子板块」→ `电子`），用该单板块当宇宙，不再走别名并集。别名表只覆盖「医药」「科技」这类口语桶。

JOIN：`fact_sector_stock_daily.stock_ts_code` 带交易所后缀，巨潮 `secCode` 是六位。对齐时取股票代码**前 6 位数字**。

一只股票可同时落在两桶。收据 `rows` 以 `(code, announcementId)` 去重；展示可按桶分组。

无点名板块、又对不上任何 `sector_name`、也不在别名表：包 `status=unsupported`，公开稿说明「未指定板块，本扫描不做全市场」，不要默默用全 A 股。

**CI 禁连生产 DuckDB**。宇宙查询走夹具或临时库（盘面包测试同款）。金标准成分股集合写进 fixture，不断网、不读 `db/market_feature_store.duckdb`。

### 5.3 巨潮查询（预算是一等公民）

- 端点：`POST https://www.cninfo.com.cn/new/hisAnnouncement/query`（与 `a-stock-data` SKILL §7.1 同一契约）。
- `stock` 空；`searchkey` 逐个关键词；`seDate=start~end`；`column` 至少覆盖深市检索一次并按 `announcementId` 去重（现场 `szse`/`sse` 重复）。
- **词序（预算不足时从后往前丢）**：
  1. **主名单词**（先跑，尽量跑完）：`中标`、`中选`、`重大合同`、`销售合同`、`获批`、`药品注册`、`临床试验批准`
  2. **附录词**（收据用途，先牺牲）：`回购`、`增持`、`业绩预增`
- `业绩预增` 若跑到了，0 条也要记进 `keyword_traces`，避免再口播「业绩大增」。没跑到（预算截断）记 `status=skipped_budget`，不得把「没查」说成「没有预增」。
- **分页上限**：每词 ≤ 3 页，`pageSize=30`（每词最多 90 条标题）。`totalAnnouncement` 更大也停，该词 `keyword_traces.truncated=true`。
- **整包墙钟**：从进入 `run_disclosure_scan_pack` 起 ≤ **45s**。触顶 → 立刻停后续关键词。**只有主名单词**被截断或 `skipped_budget` 时 `status=partial` 且开篇「查询未跑完」；附录词触顶时主名单若已齐，`status=hit`，收据写附录未穷尽，不得把备考没查完说成名单没跑完。
- **单请求**：独立 timeout（建议 8–10s）、**不重试**。失败记 `request_error`，该词空集，不改查东财，不把失败当 empty 全包。
- 串行、间隔 ≥ 1.1s（计入 45s 墙钟）。
- 默认窗口：`as_of` 往前 5 个日历日（含当日）。问句有「今天/本周/近一周」时按字面扩，收据写实际 `seDate`。

这是盘面包绑定座位第一次接网络。失败形状必须是 `partial`（有行）或 `error`（一行都没拿到且请求失败），**禁止**让包把整个 turn 的 deadline 吃光。

### 5.4 标题分层（主名单闸）

在 JOIN 宇宙之后做。`<em>` 标必须剥掉再匹配。命中多档时：`L_neg` 优先（进反证，可与同公司主名单行并列）；否则按表从上到下先命中先得。

| 档 | 标题形状（示意） | 主名单 |
|---|---|---|
| L_reg | 药品注册证书 / 药品注册批准 / 医疗器械注册。**不含**注册受理、受理通知书；不含裸「注册证」 | 是 |
| L_ind | 药物临床试验批准通知书 | 是（须标明「临床≠上市」） |
| L_order | 中标 / 中选通知书 / 销售合同 / 重大合同 | 是（须标明「金额/标的标题没有则未知」） |
| L_buyback | 回购进展 / 实施结果 / 注销回购 / 调整回购价格 / 律师意见书 | **否**，`excluded`（资本运作备考） |
| L_hold | 增持（不含「减持」） | **否**，`excluded`（资本运作备考） |
| L_collect | 集采中选 / 国家集中采购 | **否**；反证或单独「量价对冲」 |
| L_neg | 减持、立案、问询、处罚、预减、撤回注册、终止、诉讼 | 反证；与同一公司 L_reg 同窗口须并列 |
| unclassified | JOIN 命中、但以上一档都未匹配 | **否**，必须进 `excluded`，`tier=unclassified`。禁止静默丢行 |

「比较利好」公开主名单 = `L_reg ∪ L_ind ∪ L_order`，且该行未单独作为唯一叙事时被 `L_neg` 否定。标签排在公司名之前。

未分类落 `excluded` 是漏查审计的底线：关键词召回了、分层不认识，人要能在收据里看见，而不是实施者自由发挥（回购事故换个词重演）。

### 5.5 包收据（最小字段）

`DisclosureScanPack`：

- `status ∈ {hit, empty, partial, unsupported, error}`
- `as_of` / `universe_date` / `se_date_start` / `se_date_end`
- `elapsed_ms` / `budget_hit`（是否触到 45s 或某词 3 页）
- `buckets`: 每桶 `{name, universe_size, hit_codes}`
- `rows`: `{code, name, date, title, tier, announcement_id, org_id, url, bucket}`
- `excluded`: 进了 JOIN 但被分层踢出的，含 `tier ∈ {L_buyback, L_hold, L_collect, unclassified, …}`
- `keyword_traces`: 每词 `totalAnnouncement` / `pages_fetched` / `page_rows` / `truncated` / `status`（`ok` / `request_error` / `skipped_budget`）
- `warnings`

渲染：先直接判断（有名单 / 某桶空 / 整包空 / **主名单词**预算截断为 partial），再分桶名单，再「未计入比较利好」（每档最多 3 条，其余「另 N 条见扫描收据」），再反证。零命中句必须包含窗口和宇宙规模。`partial` 句必须说「查询未跑完（预算），以下为已得行」。附录词截断不得写这句。

### 5.6 公开稿合并（P0 无残差写手）

P0 绑定后固定：

- `compose=False`
- `synthesize=False`
- 公开稿 = 包 `render()`（可经 `merge_into_public_answer` 幂等前置拼接）

**不可照抄** `market_watch_pack.merge_into_public_answer` 的 `market_daily_empty → return text`（不合并）分支。盘面空袋的语义是「别用空包盖掉日报正文」；披露扫描空窗的语义是「必须把收据句交给用户」。空窗 / `unsupported` / `error` / `partial` **都要合并**。

名单段不可被删：合并放在裁判**之后**（现役 draft 一次、最终 `answer_text` 一次，幂等）。不给包行发「裁判免检证件」。P0 拒收 Engine A 后，live 那条 judge-repair 骨架路径结构上不再经过；仍要锁合并，防止日后 P1 开残差时再被削。

### 5.7 缺口灯

把扫描包 `empty` / `unsupported` / `error` / `partial` 和「某桶零命中」写入用户可见缺口（跟 `open_gaps` / followup 同源，先例 `add_degrade(..., "market_watch_pack_stop")`）。**不要**只写进 internal episode。

P0 主路径不调 `kb_search`。

## 6. 验收

冻结题（必须）：`医药和科技板块有哪些个股有比较利好的公告`

| ID | 锁什么 | 不锁什么 |
|---|---|---|
| G1 | 路由 `question_type=disclosure_scan`，不是 `theme_analysis` / `news_impact` | 控制器文案 |
| G2 | 拒收 Engine A；合同 `capabilities` 不含 `news_search`；该题 0 次 `news_search` | P1 残差里提「未采用新闻」 |
| G3 | 公开稿出现 ≥1 行 `^[0-9]{6}` 且标题可在巨潮 ID 对上；医药侧至少一档 `L_reg`（窗口与 §3.8 一致时） | 必须出现恒瑞某一个品种名（P1 才读 PDF） |
| G4 | 科技侧若只有合同/中选，标签不得写成「注册获批」；回购进展、增持不得在主名单 | 科技必须和医药一样多 |
| G5 | 桶同时覆盖医药与科技，不得只扫医药 | 两桶行数相等 |
| G6 | 华北制药若在窗口内同时有撤回与临床，不得只报临床 | 必须点名华北 |
| G7 | 空窗夹具：界面缺口数 ≥ 1 | 空窗还要编名字 |
| G8 | 预算夹具：第 2 个附录词之后墙钟用尽 → 主名单已得行仍在、后续附录词 `skipped_budget`、`status=hit`（不是 partial）、公开稿无「查询未跑完」 | 附录一截断就把整份名单判没跑完 |
| G9 | JOIN 命中但六档都不配的标题出现在 `excluded` 且 `tier=unclassified`，不得从收据里消失 | 未分类也进主名单 |

夹具数据：

- 巨潮 **page fixture**（按关键词存 JSON），CI 不打真网。
- 宇宙 **临时库 / fixture**，CI 不连生产 `market_feature_store.duckdb`。
- 金标准行从 §3.8 抽 5 条（3 医药注册证 + 1 科技合同 + 1 回购须排除）写入测试。
- 另备 1 条 unclassified 标题、1 条增持标题。

## 7. 测试计划

- 路由：冻结题 → `disclosure_scan`；`news_impact` / `theme_analysis` 旧例句回归不得漂。
- `RouteRow.capabilities == ()`；`needs_retrieval is True`；`needs_template is True`。
- 包单测：fixture JOIN（`stock_ts_code` 后缀 vs 六位）；分层；`<em>` 剥离；szse/sse 去重；芯片 918 不在默认科技宇宙；「电子」精确等于 `sector_name` 时单板块宇宙；`as_of` 早于库内最新日时不得取未来成分股。
- 预算：每词第 4 页不得请求；墙钟夹具 → `partial`；附录词排在主名单词之后被牺牲。
- 渲染：标签在名称前；空窗句子含宇宙规模与窗口；`partial` 句含「查询未跑完」。
- 编排：`DETERMINISTIC_OWNER_TYPES` 含新题型；绑定后 `compose is False`；汇合处在 owner 分叉前调用包。
- 合并：空窗也合并收据句，覆盖「照抄 `market_daily_empty` 不合并」回归。
- 负面：不得把 `THEME_RESEARCH.use_l3_lookup` 改 True 来「顺便修」。

## 8. 分期

| 片 | 内容 |
|---|---|
| **P0** | 路由（含三字段）+ 拒收 + 扫描包 + 预算/`partial` + 标题分层含 unclassified/增持 + 冻结题夹具 + 纯包渲染（compose/synthesize 关）+ 裁判后合并（空窗也合）+ 空窗/partial 缺口灯 |
| **P0.5** | 投递卫生（live 回写）：`partial` 只认主名单词；excluded 公开稿封顶；`L_reg` 收窄受理/裸注册证 |
| **P1** | 残差写手（只解释、不增删代码）；巨潮详情/PDF 抽品种与金额；问句自定义窗口 |
| **P1-b** | 残差 UX：0 工具降级 vs 研究缺口分列（本单 P0 只保证扫描缺口能看见） |
| **P2** | 模型从注册菜单点扫描（开关板原子）；本单只预留 `probe_id` 不实施 |

## 9. 风险与失败形状

- **又坐回题材椅**：控制器仍因「板块」选 `theme_analysis`。锁 G1。
- **用 L3 逐票扫**：限流事故。锁「查询无 stock 过滤、再 JOIN」。
- **无上限分页吃光 turn**（v1 的洞）：「回购」全市场几百条、pageSize 30 翻十几页。锁 §5.3 / G8。
- **站立日取全局 max**：回放漂移 + 未来泄漏。锁 §5.2。
- **未分类静默丢行**：漏查审计失效。锁 G9。
- **capabilities 带 news_search**：G2 靠自觉。锁空元组 + compose=False。
- **照抄 `market_daily_empty` 不合并**：空窗假绿。锁 §5.6 / G7。
- **回购/增持灌进主名单**：锁 G4。
- **单主语塌缩**：锁 G5。
- **空窗假绿**：锁 G7。

## 10. 回写

实施完成后：能力图谱若新增工具名，只回写现役那一份；KIT「圈小而稳的一侧 / 事实投递」本单是盘面包的兄弟件，不另建第二份清单。失败形状可补一句：「名单扫描题走题材研究 + 新闻，再靠裁判 fail-closed，会得到已完成的空盘。」

可迁移模式已单列 `~/agent-memory/10_knowledge/deterministic-prefetch-llm-residual.md`：**组件写正文、模型只写边注**；名单不可删靠「合并放在裁判之后」，不靠给包行发免检证。凡「名单 / 对账 / 覆盖率」形状都适用。

## 11. 实施计划必带（核稿小注，不挡本稿）

写 `docs/superpowers/plans/` 时必须处理，不要等实施踩上：

1. `merge_into_public_answer` 为披露包单开合并函数或加参数，**禁止**走 `market_daily_empty → 不合并`。空窗必须合并收据句。
2. `test_forecast_residual_budget.py`（main 约 101 行）断言 `DO_NOT_LENGTHEN_QUESTION_TYPES == DETERMINISTIC_OWNER_TYPES`。新题型两处同步，缺一 CI 红。
3. 别名表只有医药/科技两行；用户词精确等于 `sector_name` 时走单板块宇宙（§5.2 已写，计划里给测试用例：「电子板块近一周…」）。
4. JOIN 取 `stock_ts_code` 前 6 位，对巨潮 `secCode`。
5. 无外呼红线：巨潮公开只读不算越线；§5.3 失败语义仍是 P0 一等公民。

# Handoff：死资产「想得到用」——四表按意图编进 ask D 块

日期：2026-08-18
派单人：主 agent（#175 live 三问结案后，用户选「另开单」）
先决：**#175**（四表已进 `_DATASETS`，待合）。叠 `feat/dead-assets-consumption` 或等它合进 main，禁止再注册一遍 dataset。
先例：D0 / D7 / D9 / KC-04 的 D12——`parse_*_intent` 词面门控 + `DataBlockProvider` + `evidence_registry`。
对照：`docs/verification/2026-08-18-dead-assets-live.md`（在 #175 树上；本单把一手事实抄全，不依赖那份才能开工）。

## 词怎么用

| 词 | 本仓定义 | 别当成 |
|---|---|---|
| **够得着** | dataset 在 `finance_query._DATASETS`，参数面 enum 看得到（#175） | 答案里出现了这些数 |
| **想得到用** | ask 车道 `applies()` 命中后，确定性取数进 `evidence_text` / `[Dxx]` 引用 | 模型自己点名 `finance_query` |
| **模型点名** | episode 工具环调用 `finance_query` | 本单验收项。饥饿观测归 #179，本单不教 prompt |

#170 live 判据写的是「trace 里 finance_query 被调」。那条判据对 **ask 车道不成立**：`POST /api/runs` → `ask_retrieve_compose` 从来不调该工具。本单把想得到用改钉在 D 块，不再验工具名。

## 已核实事实（2026-08-18 一手）

#152 sidecar `:8796`（已停），`live_probe ask`，三发 **0** 次 `finance_query`：

| 题 | question_type | 实际源 | 库里有、没吃到 |
|---|---|---|---|
| 今天竞价哪些昨日涨停在抢筹 | `market_forecast` | M1 + D4 主线 | `fact_auction_stock_daily` 08-14 `panel_key=zt`：蓝盾光电 14.18、博济医药 12.25、金螳螂 9.98 |
| 最近有哪些算力/AI 方向的研报 | `theme_analysis` | wiki/R（4–6 月卖方合集） | `fact_research_report_catalog` 08-13「腾讯 Q2…算力租赁…」、08-12「英伟达 CPO…AI 算力」 |
| 近期有什么值得盯的事件催化 | `general_finance_qa` | wiki 7 月商业航天发射窗口 | `fact_event_daily` `is_future=true` 13 条；08-17 含「2026中国固态电池技术大会」 |

生产 ask 主路是 compose D 块，不是 episode。#179 在 `POST /api/conversations` 上证明 episode **会**点名 `finance_query`，但 8792=`d1be2d0c` 的 enum 还没有这四张表（#175 未合）。那是另一条车道；本单修 ask。

## 接法判决

**按意图挂 D 块，取数走 `FinanceQuery.run`（复用 #175 语义层）。**

不选：

| 选项 | 为何不选 |
|---|---|
| 改 prompt / 教模型点名 `finance_query` | #170 / ADR 0004 已否；ask 车道根本没有这个工具环 |
| 把三题改路由进 episode | 改的是入口，用户 workbench ask 仍走 compose |
| 铸 EvidenceAtom / 占 top-8 | 检索配额与 #165/#146 无关；这四张是结构化表，不是 wiki 证据 |

## 实施边界

只动：

- 四个意图解析（新模块或并进现有 `market_*`，执行方定；须可单测）
- `ask_blocks.py` / `ask.py`：四个 `DataBlockProvider`
- `evidence_registry.py` + `AskOptions.include_*_block`（默认 True，与 D0 同形）
- 对应测试
- ADR 一条（#175 合后编 0005）：想得到用 = ask 意图 D 块，不是 episode prompt
- `docs/handoffs/inflight/main.md`

占号：**D13 竞价 / D14 研报目录 / D15 未来催化 / D16 个股技术**。KC-04 **#174** 已占 D12（两融/大宗/解禁，仍 open）。开工时扫一遍 `REGISTRY`，若 D13 已被别人占用，顺延，禁止抢 D12。

不动：`_DATASETS` 再注册、prompt、episode 工具、#179 饥饿、检索 top-8、#146 闸、#165 旁路、#164/#167 数据根、FINANCEWORKS-2 ESCAPE、写端管线、两 JSON、8792、launcher、W7 的「催化」词面（D15 与 W7 可同时着火：W7=网页资讯，D15=本地未来日历）。

## 四块规格

取数一律 `FinanceQuery.run`，`limit` 走语义层 `min(limit, 25)`。缺表/空结果：`generated=false` + warning，不崩、不编行。

### D13 竞价面板 · `auction_stock_daily`

- 词面（任一）：竞价、集合竞价、抢筹、昨日涨停、开盘溢价、断板
- 查询：`panel_key=zt`，`time_range` 落到库内最新有数日（审计时 08-14），dimensions 含 stock_name / auction_pct / auction_amount
- 块标题带 `[D13]`；空面板写「最新竞价日无 zt 行」

### D14 研报目录 · `research_report_catalog`

- 词面（任一）：研报、卖方、覆盖报告、深度报告。单「算力怎么看」**不**着火
- 查询：`time_range` 近 30 个日历日 + 可选 `report_type`；**标题关键词在 Python 里滤**（问句里的算力/AI/板块名）。禁止对 `title` / `sector_tags` / `concept_tags` 走 `contains`（FINANCEWORKS-2）
- 块里至少带 date / title / report_type；live 题应能露出「腾讯 Q2」或「英伟达 CPO」

### D15 未来催化 · `event_daily`

- 词面（任一）：催化、事件日历、未来事件、值得盯的事件。单「商业航天怎么看」**不**着火
- 查询：`is_future=true`，按 `event_date` 降序，limit 小
- 与 W7 并存，不替换 W7
- live 题应能露出「固态电池技术大会」或同日其他 `is_future` 标题

### D16 个股技术 · `stock_technical_daily`

- 词面（任一）：乖离、均线通道、MA26、上轨、布林 **且** 解析到库内个股。无个股 → `applies=false`（200 万行，禁止全表进块）
- 查询：该 `stock_code` + 近 5 个交易日 + limit；metrics：close / ma26 / deviation_pct
- 无 time_range 的 `FinanceQuery` 调用不准从本块发出

## 测试（先红后绿）

1. 三道 live 题 +「某股相对均线乖离」：对应 `applies=true`，fixture 块含 `[D13]`/`[D14]`/`[D15]`/`[D16]`
2. 反例：`今天大盘怎么看`、`算力怎么看`、`长电科技怎么看`（无乖离词）→ 四块都不 applies
3. D16 无个股 → applies false；有个股的查询带 time_range 且行数 ≤ 25
4. D14 过滤不碰 `contains`（单测里对 `FinanceQuery.run` mock/spy：arguments 无 contains）
5. 空表 / 缺 path → generated false + warning，ask 不抛
6. `evidence_registry` 能看见四个新 name；`enabled_providers` 关掉则不取数

## live（#152 sidecar，不碰 8792）

用 `live_probe ask`（不要改走 `POST /api/conversations`）。四问：

1. 今天竞价哪些昨日涨停在抢筹 → `llm_context` / citations 有 `[D13]`，正文出现「蓝盾光电」或同日其他 zt 名
2. 最近有哪些算力/AI 方向的研报 → `[D14]`，正文出现「腾讯 Q2」或「英伟达 CPO」
3. 近期有什么值得盯的事件催化 → `[D15]`，正文出现「固态电池」或同批 `is_future` 标题
4. 选一只有库的股票问乖离 → `[D16]`，有 close/ma26/deviation 数字

数据根：#167 未合时 sidecar 的 `WORKBENCH_REPO_ROOT` 仍可能指空 `db/`。照 #175：软链到 `~/finance-workspace-private/db/market_feature_store.duckdb`（`db/` gitignore，勿提交）。不修 #164。

反例一发「今天大盘怎么看」：四块 attempted=false 或未进 citations。

## 红线

- 先决 #175，不重注册 dataset
- 不教 prompt、不改 episode、不修 ESCAPE、不切 8792
- 不抢 D12；D16 无个股不准取数
- 研报关键词不走 SQL `contains`

## 验收标准

1. 四件套绿（`umask 022` + `env -i` 保 PATH/HOME/KNOWLEDGE_WIKI）
2. 上列测试绿
3. live 四问 + 一发反例收据，路径写进交接；看 D 块引用和正文专名，不看 `finance_query` 工具名
4. ADR + inflight
5. PR mergeable（先合 #175 再合本单，或本单 base=`feat/dead-assets-consumption`）

## skill 与工具

skill：leila-runtime + tdd。工具：git worktree、pytest、`FinanceQuery.run`、live_probe ask、Gitea API。

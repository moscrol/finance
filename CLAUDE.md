# 金融项目

## 👤 用户偏好（核心，必读 —— 教学模式）

- **语言：中文。** 目标是**边做边学**（非科班背景），不只是把活干完。
- **讲原理 + 讲技术选型**：用到某技术先简述它是什么、为什么用；**务必给替代方案对比**（反复强调的重点）；能迁移到别处的知识点请点出“这在 X 场景也能用”。面试常考点可顺带点一句。
- **学习重点**：RAG、Hybrid 检索（向量 + BM25 + rerank）等；实现时优先选能学到主流/前沿做法的方案并解释取舍。
- **Git 约定**：开工先 `git status --short && git branch --show-current`；大任务必开分支（`<type>/<short-task>`），**合并 `main` 必须等我确认**，不强推；小文档修补可直接 `main`。
- 🚫 **红线**：禁提交 `.env*` / 密钥 / `*.pdf|zip|duckdb|db` / `.DS_Store` / 缓存或虚拟环境；不写明文密钥；知识库大 JSON（relations/）走 `query_relations.py`，别直接 `cat`；不擅自合并 `main`、不强推。
- 完整偏好见 `.agent-memory/30_conventions/preferences.md`（repo 内软链 → `/Users/a77/agent-memory`，已 gitignore）。

## 🧠 共享记忆底座（开工前先读）

本机有一个跨 Agent 共享的记忆底座（Obsidian vault）：`/Users/a77/agent-memory`（仓库 `linxiaoqi5111-del/agent-memory`）。

**开始任务前先读：**
- `.agent-memory/30_conventions/preferences.md` — 用户偏好与人设（教学模式：讲原理 + 讲技术选型/替代方案对比 + 标注可复用知识点；Git 约定；红线）
- 本项目对应笔记 `.agent-memory/20_projects/finance-workspace-private.md` — 项目背景、关键决策、任务看板

**完成后沉淀：** 先判断层级：项目级代码/配置/流程/架构/数据管线决策才追加到 `.agent-memory/20_projects/finance-workspace-private.md` 的「交接记录」；稳定且可跨任务复用的方法论提炼进 `.agent-memory/10_knowledge/`；单次问答评分、用户纠偏、经验样本优先写项目内学习层（如 `experience_cards.jsonl` / `corrections.jsonl`），不要把聊天流水塞进项目交接。

## 🧰 工具包三件套（2026-08-12 确立，总纲 `~/harness-reference/KIT.md`）

**搭建 agent 的能力要沉淀成三件套：正确的设计、正确的搭建、正确的审计。检索源只提供方法论（形状），工具包提供可执行的组件与判据。任何写出来且可复用的组件与工具，必须落进对应那一件，不留在一次性脚本里。**

- **审计** ✅ → `~/harness-reference/TOOLKIT.md`（按成本档位 A–H；选档规则：能用 0 档复现的绝不上 4 档）
- **搭建** ✅ → `~/harness-reference/BUILD.md`（**七个可迁移模式** + 16 个零件，每条写清「失败形状 / 关键设计 / 移植要改什么」）
- **设计** ⚠ 材料齐备未收口 → `10_knowledge/` 骨架判据 + `70_tutor/` 20 篇
- 方法论横跨三件 → `~/harness-reference/PLAYBOOK.md`（先定位再查源 / 先解决问题再优化 / 五阶段）

搭建侧那七个模式是本仓踩出来的，动 hook/门禁/收据前先看：**棘轮式门禁**（存量免检、新增拦截、baseline 从源码生成）、**圈小而稳的一侧**（圈底座不圈积木）、**事实投递 > 提醒**、**预算 + 声明式截断**（限定语排在被限定内容之前）、**结论携带成立条件**、**单一真本源且生成**、**认不出来就 fail closed**。

本仓写出的通用件（SessionStart 事实注入、棘轮式路径门禁、带条件的测试收据、按分支归属而非 mtime 的交接判定等）属于「搭建」那一件；新增或改动后**回写 `KIT.md`，不另建第二份清单**。

## 🗺️ 本地代码地图（编码任务先走这里）

编码任务先 `python3 scripts/code_map.py query "<问题>"`。禁止把空图 `get_architecture_overview` 写成架构结论；禁止 `code-review-graph init|install`；禁止 DeepWiki `generate_wiki` / 对本仓 private index。MCP 已连接 ≠ 地图可用。

## 🗺️ Agent 能力现状（断言"我们没有 X"之前必读）

> 2026-08-04 加入。起因：一次会话里连续三次把「已存在的能力」和「刻意的设计约束」
> 误判成缺口，差点组织人去"补"一个已经做过的决定。**下面这些是事实，不要再发现一遍。**

**权威事实源**：`.agent-memory/10_knowledge/finance-agent-capability-graph.md`
（有 `graph_audit.py` 硬门禁，跑它拿当前节点数，别抄这里写死的数）。改能力时回写它，
**不要另建第二份清单**。

### 金融问答正门

默认：`python3 -m intelligence.cli ask "<问题>"`。追问 `chat`；模型选工具才用 `agent`。Workbench 走 Episode，不要用 CLI 冒充 UI 合同。评接口 / 找入口读 `docs/agent-product-door.md`（门 / 两条引擎 / 积木；注册表不是门）。`--kb-mode` / `--wiki-rag-mode` / `--modules` 是逃生口。问能力个数时点名 `skills/` / `.claude/skills/` / 工具注册表，不要加总、不要写死个数。

写入正门是 `python3 -m market_feature_store.cli daily-full`。`fact_sector_daily` 是 VIEW。编码任务走上一节代码地图 CLI，不要用问答正门冒充。

技能桥只开一个、飞书 Bitable 写入退役、飞书 IM（`feishu-bot`）退役——这些是约束不是缺口。

### Agent 可调工具：12 个

全部在 `intelligence/services/research_tool_registry.py` 的 `_DEFAULT_TOOL_METADATA`：

```
finance_query  evidence_search  kb_search   web_search       news_search
graph_lookup   evidence_lookup  memory_lookup  l3_lookup     market_data
financial_data mainline_context
```

⚠️ 逐个受 `contract.allowed_capabilities` 门控（`episode_tools.py` 内按 capability 分支）。
**"定义了" ≠ "这次开着"**，判断覆盖面要看当次 contract 实际授权。

> **数数别用固定行号。** 本节初版写「10 个」并把 `finance_query`/`evidence_search` 记成
> 来自 `episode_tools.py`，两处都错——因为沿用了一段固定行号去读那张表，而表的起点在更上面。
> 要数就用解析器：
> `python -c "import ast,pathlib;t=ast.parse(pathlib.Path('intelligence/services/research_tool_registry.py').read_text());..."`
> 或至少 `sed -n '/_DEFAULT_TOOL_METADATA/,/^}/p'`。

### 技能：三个位置，数字不一样

| 位置 | 数量 | 是什么 |
|---|---|---|
| `skills/` | 31（含 `lib/` 非技能 → 实为 30） | **仓内真实技能清单** |
| `.claude/skills/` | 19 | 软链到 `../../skills/`，= Claude Code 能看到的子集 |
| `<知识库仓>/skills/` | 20 | ingest 类，已迁出本仓 |

问「有多少能力 agent 够不着」时，分母是 `skills/` 不是 `.claude/skills/`。
只在 `skills/` 里、没暴露给 Claude Code 的有 12 个，含 `stock-deep-dive`、
`researcher-valuation`、`duckdb-backfill`、`opinion-cross`、`serenity-alpha`、`strategy1-matrix` 等。

### 技能桥：存在，且**刻意只开一个**

`intelligence/services/skill_tools.py`（已注册 `serenity-alpha`）、
`intelligence/services/theme_modules.run_module`（theme-radar 六模式）。

**其余 skill 未接入是设计决定，不是缺口**：绝大多数会拉实时数据（fupanhui / iFinD /
AKShare）或写回（飞书 / DuckDB），接入会破坏 agent 的**只读 + 无外呼**红线。
要扩注册表，必须先论证不破这条红线。

### 编排层：存在

`answer_orchestrator` / `question_router` / `route_table` / `ask_planner` /
`retrieval_planner` / `research_task_planner` / `research_plan` /
`generic_research_owner`（在 `intelligence/services/`），
`conversation_orchestrator`（已搬到 `intelligence/runtime/`——它管 loop 与预算，
按 layer_audit 的判别口径属底座）。

### 已确立的可迁移原则（别重新发现）

来自 MOC 交接记录，已在真实事故中验证：

1. **配额要在副作用前"预占"，不是事后计数**——事后扣费挡不住并发 check-then-act：
   两个请求同时看到"还剩 1"会双双执行，最后才有一个扣账失败。
2. **全链 deadline 传绝对时刻**，不传相对秒数——后者每跳重新计时，总时长会膨胀。
3. **请求去重用 per-key single-flight**，不要用全局锁包住慢 IO。
4. **授予的额度必须真的传到最下游执行者**——只写进 telemetry 不生效，比不做更危险
   （仪表全绿、实际没人管）。

### 负面断言规矩（强制）

**规范正文不在这里**——它由用户级 SessionStart hook（`~/.claude/hooks/session-context.sh`）
每次会话无条件注入，从任何目录起会话都会收到，所以本文件不再抄一份。

2026-08-12 实测：本文件那份抄件**已经漂了**，比注入版少两条，其中一条是最有用的
「这类问题先问用户比先搜快——『我们有没有编排层』用户两秒能答」。
这正是「同一份清单存两处必漂，且漂的时候没人知道」的现场，故删抄件、只留指针。

本仓相关的只有一句：上面那节的**能力图谱**就是该纪律第 2 步要读的东西。


A股量化复盘+研究工具集。通过 fupanhui.com API 获取市场数据，写入本地 DuckDB（`market_feature_store.duckdb`），结合 iFinD 数据做深度分析。

## Git Branch Safety Rules（强制）

`main` 是当前共享基线，不代表已经完美稳定；本项目仍在持续修缮。任何 agent 开始工作时必须先执行并汇报：

```bash
git status --short
git branch --show-current
```

规则：
- **大任务默认不开在 `main` 上做**：baseline 批次、PDF ingest 规则/脚本、Theme Radar 规则、数据源脚本、DuckDB/飞书写入逻辑、批量生成或跨仓库修改，都必须先从最新 `main` 新建任务分支。
- 推荐流程：`git checkout main` → `git pull` → `git checkout -b <type>/<short-task>` → 工作 → commit → push 分支；合并回 `main` 必须等用户明确确认。
- 小型文档/规则修补可以直接在 `main` 做，但提交前仍要检查风险文件。
- 分支命名：`baseline/<批次或公司名>`、`pdf-ingest/<日期或材料名>`、`theme-radar/<题材或能力>`、`data-source/<来源名>`、`fix/<问题>`。
- commit 前必须检查不要提交：`.env*`、`mcp_config.json`、`feishu_config.json`、`*.pdf`、`*.zip`、`*.duckdb`、`*.db`、`*.sqlite*`、`*.pptx`、`.DS_Store`、`__MACOSX/`、`._*`、缓存和虚拟环境。

## 核心工作流

1. **每日复盘（全量复盘）** → 确保 CDP proxy 已启动（`node ~/.claude/skills/web-access/scripts/cdp-proxy.mjs`）→ `python3 -m market_feature_store.cli daily-full --trade-date YYYY-MM-DD` → 写入 DuckDB → `audit_coverage.py` 验证覆盖
   > ⚠ 飞书 Bitable 写入已废弃，复盘数据统一走 `daily-full` → DuckDB 路径。
   > ⚠ stock-daily 用默认东财快照（`--stock-source snapshot`），日常单日复盘**不要带 `--stock-source mootdx`**（mootdx 仅首次建库/多日历史回填，慢且当日值与快照一致）。详见 market-overview SKILL.md。
2. **连板晋级** → `limit-advance/scripts/scrape.py [日期]` → 展示 + 写入飞书
3. **涨幅排行** → `top-gainers` skill：iFinD个股涨幅 + AKShare板块涨幅并行
4. **策略分析与回测** → `detect_turning_points.py`、`backtest_sector.py` 只读 canonical `fact_*` 表；板块数据回填旧入口 `backfill_sector_marginal.py` 仍单独停用，不能混用旧库
5. **概念入库** → 加载知识库仓 `concept-ingest` skill（`<知识库>/skills/concept-ingest/SKILL.md`）。**IMA 题材 DeepDive**：Copilot 15章 → `deepdive.md` → `build_ima_concept_ingest_queue.py` → 人工 ingest-plan → writer；禁止搜标题当抽取，禁止有 md 直接 writer。研报/纪要：判断 is_concept → ingest-plan → `python3 <知识库>/scripts/ingest.py concept ...`
6. **公司边际变化入库** → 加载知识库仓 `entity-delta-ingest` skill（已迁至 `<知识库>/skills/entity-delta-ingest/`）→ 读取早知道/评级日报/纪要/公告 → 抽取公司边际变化 JSON → `python3 <知识库>/scripts/ingest.py entity-delta ...` 更新 Obsidian `entities/`，纯榜单进观察列表

## 市场假设验证 / 跑马策略执行规则

- 跑马策略处于假设验证阶段，禁止把单次观察写成定律或硬规则。
- 默认采用“实验台账 + 半自动查询”，每个实验必须记录输入窗口、假设、数据完整性、候选池、后验结果、结论状态和下一步。
- 执行必须分步、最小单元、短脚本短命令；一次只做一个原子动作，例如数据核验、候选池生成、相对强度计算、后验收益计算、报告写入。
- 避免一次性长 SQL、长 Python 脚本或大批量回填；复杂查询必须拆成多个短查询或临时小脚本，便于中断、复核和定位失败。
- 数据不完整时先补阻塞性缺口；无法补齐时必须在报告中标注缺口及其影响，不得用缺失数据推断规律。
- 指数环境只作为背景放大器，不作为板块或个股强势的决定性因素；优先观察容量行业、双红题材边际量、新高映射、涨停映射、个股加权强度和分歧日相对强度。
- 验证后验收益时不能只看固定第 10 日终值；必须比较 3/5/7/10 日等不同窗口、区间最高收益、达到峰值所需天数、峰值后回撤，并记录双红题材回流后再分歧前是否有退出机会。
- 实验性代码、台账和报告默认不提交不推送，除非用户明确要求。

## 本地数据库 (DuckDB)

**主库（唯一可用）`db/market_feature_store.duckdb`** —— 星型模型，当前问答/复盘/深挖/前瞻的唯一数据源。由 `market_feature_store` 包维护，写入入口 `python3 -m market_feature_store.cli daily-full`（schema SSOT `market_feature_store/schema.sql`；`db/schema.sql` 为早期雏形）。对象清单是下面的生成块（`scripts/gen_duckdb_schema_inventory.py`，`--check` 可复核）；行数/日期范围每天变，不进文档，跑 `python3 -m market_feature_store.cli info`。

<!-- BEGIN GENERATED: duckdb-schema-inventory | scripts/gen_duckdb_schema_inventory.py | 来源 market_feature_store/schema.sql；行数等易变数字不进文档，看 cli info -->
共 49 张表 + 3 个视图（`schema.sql` 声明；生产库以 `cli info` 为准）。带 `(V)` 的是 VIEW。

| 层 | 数量 | 对象 |
|---|---|---|
| `dim_` 维度 | 1 表 + 1 视图 | `dim_sector`, `dim_sector_canonical` (V) |
| `fact_` 事实镜像 (外部来源, 可重建) | 33 表 + 2 视图 | `fact_auction_stock_daily`, `fact_core_stock_daily`, `fact_dragon_seat_daily`, `fact_dragon_summary_daily`, `fact_dragon_tiger_daily`, `fact_event_daily`, `fact_global_index_daily`, `fact_global_stock_daily`, `fact_high_volume_gainers`, `fact_historical_mapping`, `fact_leader_height_daily`, `fact_limit_advance_daily`, `fact_limit_advance_presence`, `fact_mainline_sector_daily`, `fact_mainline_stock_daily`, `fact_mainline_theme_daily`, `fact_market_daily`, `fact_regulation_event_daily`, `fact_regulation_pool_daily`, `fact_research_report_catalog`, `fact_sector_daily` (V), `fact_sector_daily_generation`, `fact_sector_period_rank_daily`, `fact_sector_stock_daily` (V), `fact_sector_stock_daily_generation`, `fact_sector_universe_daily`, `fact_stock_daily`, `fact_stock_high_daily`, `fact_stock_technical_snapshot`, `fact_sw_l1_daily`, `fact_theme_flow_daily`, `fact_theme_fundamental_doc`, `fact_theme_limit_heat_daily`, `fact_theme_limit_stock_daily`, `fact_top_gainers` |
| `config_` 人工配置 | 4 表 | `config_sector_alias`, `config_strategy_rule`, `config_theme_sector_link`, `config_watchlist` |
| `feature_` 特征 (由事实计算, 可删重算) | 7 表 | `feature_l2_capital_flow_daily`, `feature_l2_quant_orders_daily`, `feature_limit_advance_window`, `feature_market_window`, `feature_sector_window`, `feature_stock_technical_daily`, `feature_stock_window` |
| `ops_` 运行台账 / 收据 | 4 表 | `ops_pipeline_run_daily`, `ops_sector_member_sync_daily`, `ops_sector_universe_snapshot_daily`, `ops_sync_run` |
<!-- END GENERATED: duckdb-schema-inventory -->

核心表的职责与来源：

| 表 | 说明 | 数据来源 |
|----|------|---------|
| fact_market_daily | 每日市场指标（阶段/成交/涨家/涨停/集中度/偏离度） | market_feature_store sync |
| fact_sector_daily (V) | 板块日行情（pct_chg/amount/diff_ratio/strength/多周期共振）—— **双红判断主表** | fupanhui |
| fact_sector_stock_daily (V) | 板块×个股日行情（含 5/10/20 日涨跌幅、资金流）。**写入规则**：一行必须至少带一个行情值（`price`/`pct_chg`/`amount`），底层表有 CHECK；2026-09-03 已清掉 810 万行无行情的归属行（`maintenance` 收据 `ef40de4eb9b2`），2025-01-06 ~ 2026-03-30 共 288 个交易日成分股行情**如实为缺**，不是新缺口，以前被空壳盖住 | fupanhui |
| fact_stock_daily | 个股日行情 | fupanhui |
| fact_stock_high_daily | 新高（1/2/3 年/历史，含涨停状态） | market_feature_store |
| fact_theme_limit_heat_daily | 题材涨停热度（limit_up_count/market_share/rank）—— **涨停热度主表** | fupanhui |
| fact_limit_advance_daily | 连板晋级（boards/promotion_rate） | limit-advance skill |
| fact_sw_l1_daily | 申万一级日行情 | AKShare |
| fact_mainline_*_daily | 主线结构（sector/stock/theme） | fupanhui |
| dim_sector + dim_sector_canonical (V) | 板块维度。**630 行 ≠ 630 个板块**：223 个 `.TI` 码（2026-07-24 停更）+ 407 个 `.FP` 码（2025-10-09 起），117 个板块名两套码都有。解析走 `dim_sector_canonical` / `sector_alias.resolve_sector_codes`，见下「板块维度一致化」 | fupanhui |
| config_sector_alias | 旧码→现行码映射（`sector-alias apply` 生成 117 条）+ 人工别名 | 本仓生成 |
| feature_*_window | 滚动窗口特征，`compute-features` 步按日增量写入（只算当日，属 `check_daily_review_data.py` 的 `FEATURE_FAMILY` 完整性闸门成员，缺任一张 = 半成品）。`feature_stock_window` 累计约 750 万行；语义层豁免 `stale_materialized`，`feature_market_window` 有 workbench 读者，其余三张暂无读者 | compute_features.py |

严格双红定义（见 strategy1-matrix）：`pct_chg>0 且 diff_ratio>10 且 amount>500`。

### 板块维度一致化（sector_name 不是键）

供应商换过码系：`.TI` 与 `.FP` 两套码在事实表里并存 124 个交易日，同名板块**数值不同**（两种成分定义，不是重复行）；另有 53 个码历史上改过名（`PCB` ↔ `PCB概念`）。所以 **按 `sector_name` GROUP BY 会双计，`WHERE sector_name = ?` 会把两个供应商的成分股混成一张表**（`query.sector_stocks` 2026-09-03 前就是这么写的）。

| 对象 | 作用 |
|------|------|
| `config_sector_alias` | `alias → 现行 .FP 码`。`python3 -m market_feature_store.cli sector-alias plan` 只读预览；`apply --staged` 走克隆换名写入（只写同名**唯一**匹配，歧义留给人） |
| `dim_sector_canonical`（VIEW） | 每个码 → `canonical_sector_ts_code` + `provider` + 事实表真实起止日（`dim_sector.first_seen_date` 是建行日，不是事实起点） |
| `sector_alias.resolve_sector_codes(con, 名或码)` | 返回按优先级排好的候选码（现行码在前、退役码在后）；同名对应多个 canonical（当前只有 `国防军工` 两个 .FP）标 `ambiguous=True`，**调用方必须说出来** |
| `sector_alias.pick_code_with_rows(con, 表, 日期, 候选)` | 按日期在候选里回退：2025-06 问「云计算」落 `.TI`，并存日落 `.FP` |

`query.sector_stocks` / `stock_sectors` 已改走解析器，返回里带 `resolution` 回执；新写的板块查询一律先解析到码再查事实表。排查用 `cli sector-alias resolve <名或码> [--trade-date]`。106 个 `881xxx.TI` 二级行业码在 FP 体系里没有对应板块，属供应商砍掉，不是匹配失败。

### 成分股表写入规则（空壳行三层拦截，2026-09-03）

`fact_sector_stock_daily_generation` 曾有 810 万行（67%）`price/pct_chg/amount` 全 NULL：`fast_daily_sync`「拷昨日成分、改日期」（2025-01~2026-03，source NULL）与 `SectorUniverseStore.copy_legacy_member_generation`（2026-06-18~22，source `incremental-copy`）写的**归属行**——行数、断档、收缩比全正常，日报却全「暂无」（2026-06-22）。归属行不是行情事实。

| 层 | 落点 | 行为 |
|---|---|---|
| ① 正门 | `SectorUniverseStore.record_member_result` | 单只无行情（停牌/接口漏值）**丢弃、计入缺口**（expected − actual）；整板块每一行都无行情 → `last_error_code=member_rows_quoteless`，status=error，可重试、不写。`copy_legacy_member_generation` 一律 `raise`（方法保留让停用脚本的 REFUSED 分支照常） |
| ② 表 | `schema.sql` `CHECK (price IS NOT NULL OR pct_chg IS NOT NULL OR amount IS NOT NULL)` | 兜住任何绕过 store 的裸 INSERT；legacy 迁移 `_copy_legacy_rows` 同规则过滤 |
| ③ 量具 | `quality.check_daily` → `quoteless_sectors`；`audit_coverage.py` 的 `value_rows/shell_days` | 当日出现「有行无行情」板块 → 跨日质检 FAIL（后 16 步 SKIP），审计单独报空壳日 |

DuckDB 没有 `ALTER TABLE ADD CONSTRAINT`，已有库装 CHECK 要重建表：`python3 -m market_feature_store.cli maintenance`（默认只读 dry-run：空壳行数、CHECK 是否已装、文件在用/空闲块）；`--staged` 才动库——克隆 → 重建（只搬有行情行 + CHECK）→ `COPY FROM DATABASE` 压缩到新文件 → 逐表行数/索引/约束/视图对账 → 第三方写者守卫 → 原子换名，收据进 `ops_sync_run`（kind=`maintenance`）。DuckDB 删行不缩文件，日常 `daily-full` 的 upsert 会慢慢积空闲块，空闲块占比高时也用它压缩（`--no-purge`）。

> ⚠️ **Legacy 残骸（勿直接跑、勿删，待迁移）**：旧库 `db/market.duckdb`（早期飞书同步阶段）**已退役、文件已移除**；旧表名 `advancers / daily_market / sector_marginal / stocks` 在主库**既非表也非视图、不存在**。当前仍停用、待另行迁移的旧入口是 `scripts/backfill_sector_marginal.py`；新分析一律用 `fact_*` 表。`detect_turning_points.py` 与 `backtest_sector.py` 已迁移为 canonical 只读 CLI，`render_daily_review_template.py` 是现役日报渲染入口，`sync_to_local.py` 已改为无副作用退役 shim。

> ⛔ **`scripts/fast_daily_sync.py` 已停用（2026-08-02）**，失败模式与上面那批不同：它连的是**当前**主库，但写 `fact_sector_daily` / `fact_sector_stock_daily`——这两个**在生产库里已经是 VIEW**（底层 `fact_*_generation` 表 + `sector_universe_snapshot_id`，读取只暴露 `published` 快照），INSERT 会抛 `Catalog Error: ... is not an table`。脚本已自带闸门，默认退出码 2。更要紧的是它的 sector-stocks 步骤是「拷昨日的行、改个日期」，只保留 sector→stock 归属，price/pct_chg/amount 全为 NULL——**行数和 `COUNT(*)` 覆盖率审计都正常，值却是空壳**（2026-06-22 致 daily-review §7/§12 全「暂无」）。这类静默降级当时只有**跨日期 diff** 能抓到。2026-09-03 起：空壳行已清（810 万行），表上有 CHECK，正门丢无行情行，`check_daily`/`audit_coverage.py` 直接数值不数行——见下「成分股表写入规则」。
>
### 板块快照分代（sector universe snapshot）

`fact_sector_daily` / `fact_sector_stock_daily` **是 VIEW，不是表**。分代机制：

| 对象 | 作用 |
|------|------|
| `ops_sector_universe_snapshot_daily` | 快照台账，`status ∈ candidate/published/superseded/rejected`，同日可多版 |
| `fact_sector_universe_daily` | 快照内板块名单 + `expected_stock_count`（完整度校验依据） |
| `ops_sector_member_sync_daily` | 逐板块抓取进度，断点续抓依据；expected vs actual 的差额=缺口 |
| `fact_sector_*_daily_generation` | **写入目标**，`sector_universe_snapshot_id` 进主键，同日多版互不覆盖 |
| `fact_sector_*_daily`（VIEW） | **读取入口**，只暴露 `published` 那版；消费方查询无需改写 |

**写入方必读**：目标是 `*_generation`，主键含 `sector_universe_snapshot_id`，用
`db.get_published_snapshot_id(con, trade_date)` 解析（无 published 时回退 `'legacy'`）。
参考实现 `sync/sync_feishu_sector_resonance.py`。`'legacy'` 是机制上线前的历史数据：
**当日一旦出现 published 快照，legacy 行自动让位**，不会双份并存。

> 供应商会换代码、改名单。没有这层就回答不了「当时用的是哪一版板块清单」——
> 这也是为什么不能直接往 view 里 upsert。

### 同步命令

复盘事实统一由 canonical 入口写入：

```bash
python3 -m market_feature_store.cli daily-full --trade-date YYYY-MM-DD
```

`scripts/sync_to_local.py` 已正式退役，仅保留 `--help` 和明确退出码 2 的提示入口；它不读取凭证、不访问网络、不创建数据库。旧实现可从 Git 历史查阅，不要将其恢复成第二条写入链。

### 信号检测

`detect_turning_points.py` 现在只读 `market_feature_store` 的 `fact_market_daily` / `fact_sector_daily`，并与回测共用无前视的确认日算法；`scripts/archive/compute_features.py` 仅保留历史复现，不是日常入口。

```bash
python3 scripts/detect_turning_points.py           # 全部历史
python3 scripts/detect_turning_points.py --from 2026-04-01  # 指定起始
```

三种触发条件：大盘放量>10%、MA5 峰确认、MA5 谷确认。峰谷信号只在确认日输出，不使用未来数据。

### 板块边际量回填

> ⚠️ **Legacy 残骸**：`backfill_sector_marginal.py` 写入旧表 `sector_marginal`（主库不存在），**当前 broken**。板块边际量现由 `market_feature_store/sync/sync_fupanhui_sector_daily.py` 写入 `fact_sector_daily`。

```bash
python3 scripts/backfill_sector_marginal.py <逗号分隔日期> <CDP_target_id>
# 输出 JSON 到 stdout，由主 agent 写入 DuckDB
```

回填策略：每批4-7天，子 agent 并行抓取（只抓不写），主 agent 串行写入 DuckDB → Bitable → 电子表格。

当前覆盖：67个交易日（2026-02-02 ~ 2026-05-21），~15K条记录。2月14天（春节02-16~02-20无交易），3月22天，4月21天，5月10天。

### 板块回测

`backtest_sector.py` 只读 canonical `fact_sector_daily` / `fact_market_daily`，默认数据库路径可由 `MARKET_FEATURE_STORE_DB` 覆盖；不存在的数据库会 fail closed，不会自动创建旧库。

```bash
python3 scripts/backtest_sector.py              # 默认参数
python3 scripts/backtest_sector.py --scan        # 参数扫描
python3 scripts/backtest_sector.py --top 5 --hold 3 --min-marginal 8
```

## Skills 目录

<!-- BEGIN GENERATED: skills-table | scripts/build_registry.py backfill-tables | 成员同步自 skills.registry.json；触发词列人工维护，新增行自动预填 -->
| Skill | 触发词 |
|-------|--------|
| market-overview | 复盘、市场总览、今日行情 |
| limit-advance | 晋级、连板 |
| top-gainers | 涨幅排行、涨幅前N |
| high-volume-gainers | 放量上涨 |
| advancers-chart | 涨家数走势 |
| up-line | UP线、UP线更新 |
| watchlist-ma | 自选股均线 |
| ifind | iFinD数据查询 |
| hithink-market-query | 同花顺市场查询 |
| report-search | 研报搜索 |
| sector-data | 边际量、板块数据、抓取板块 |
| 公司画像页 | 公司画像PPT |
| 行业概览 | 行业概览 |
| theme-radar | 题材雷达、新词雷达、题材逻辑拆解 |
| theme-fermentation-tracer | 发酵链路、发酵回溯、起涨补涨、双红怎么加强的（消息面×盘面历史回溯，需本地 DuckDB） |
| opinion-cross | 卖方观点提纯、三重共振机会卡片（注：覆盖密度交叉验证在知识库仓 sellside-coverage-cross） |
| serenity-alpha | 个股弹性预期差、补涨排序 |
| disclosure-archive | 补公告、披露归档（抓取侧；apply 侧在知识库仓） |
| duckdb-backfill | 回填 duckdb、补 market_feature_store、增量补数据、fact 覆盖审计、同步 stock_high/sector_stock/limit_heat |
| strategy-evolve | 策略进化、evolve、策略生成迭代、回测记录、前瞻收益验证（suggest 只建议、不自动改 params.json） |
| strategy1-matrix | 策略一生成、生成策略1、策略一矩阵、策略1每日优先个股、strategy1 matrix、更新策略一。用于基于已完成的每日复盘数据、把某个交易日写入 `复盘、matrices、strategy1-priority-stock-matrix.html`、并沉淀 T1、T2、OBS、次日验证、尤其适用于避免长 SQL、长 shell 字符串、手工编辑巨大 HTML 单行导致出错 |
| top-gainers-feishu | 强势股入库、涨幅入库、区间强势、涨幅筛选入库、查询强势股、强势股均线、强势股回踩 |
| foresight-feedback | 记反馈、记一下、我关注、我对这个感兴趣、想深挖、这个不看了、跳过、不感兴趣、打个分、很重要、猜你想问、越用越懂、自动记反馈 |
| 潜意识模式 | 开启潜意识模式、潜意识模式、进入潜意识、退出潜意识、收工、回读对话、巩固记忆、沉淀这轮、记进沉淀、潜意识开关 |
| task-planner | 批量任务规划、开工前采访、批量回填前先问、开新题材前先问、运行前规划、采访前置、先问后做、task planner、batch plan、回填前先问 |
| checkpoint-recheck-mac-setup | 夜间回检、checkpoint recheck、可证伪点回检、launchd 安装、远程执行、remote-exec、隧道乱码、codepoint 校验、共享大脑、foresight 台账、多机一致、登点闭环 |
| daily-full-review | （待补：SKILL.md 无触发词字段） |
| dispatcher | 所有请求默认经过本 dispatcher、不需要显式触发 |
| stock-deep-dive | 个股深挖、深挖、深度分析个股、这只股怎么看、复盘先验、行情前瞻、明日研判、次日研判、前瞻研判 |
| researcher-valuation | 拍估值、估值带、贵不贵、隐含预期、值多少钱、估值分位、估值怎么看、合理估值 |
| handoff | handoff、交接、写交接、回写 handoff、收尾交接、交给下一个 agent、另一个 agent 接手。你说"handoff"就执行本流程、不用等会话结束 |
| perspective-distill | 蒸馏视角、视角蒸馏、KOL蒸馏、学这个博主、喂文章、把这篇文章喂给视角、新建视角、perspective distill |
| finance-longtail-baseline | （待补：SKILL.md 无触发词字段） |
| finance-degraded-fallback | （待补：SKILL.md 无触发词字段） |
| code-map | 代码地图、code-map、code-review-graph、deepwiki、造轮子、现有实现 |
| divergence-distill | 蒸馏分叉、对照蒸馏、蒸 Fable、蒸 Knevo、trace diff 沉淀、diff 完沉淀 |
| watchlist-digest | 自选简报、我的自选今天怎么样、按我的自选出简报、开盘简报（按自选）、我的清单今天该看什么、watchlist digest |

跨仓引用（规范源在知识库仓，本仓不放正文）：

| Skill | 触发词 |
|-------|--------|
| concept-ingest（已迁至知识库仓） | concept ingest、概念入库、IMA入库、题材DeepDive、ThemeRadar入库、新概念、提取概念 → 读 `<知识库>/skills/concept-ingest/SKILL.md` |
| entity-delta-ingest（已迁至知识库仓） | entity delta、公司边际变化、更新entity、早知道入库 → 读 `<知识库>/skills/entity-delta-ingest/SKILL.md` |
<!-- END GENERATED: skills-table -->

## 关键约束

- 复盘数据统一走 `daily-full` → DuckDB，**飞书 Bitable 写入已废弃**
- 连板晋级写入**必须串行**（从旧到新），禁止并行写入飞书
- fupanhui API 用浏览器内 XHR 调用（通过 CDP proxy），自动携带 session cookie
- 周均线/偏离度通过 hover K线 tooltip 获取后，需用上证日收盘价交叉验证偏离符号
- 所有联网操作必须通过 `web-access` skill

## 知识库回填与 theme-radar 红线

- `raw/*full.md` 研报回填默认不能写实体正文；只有公告/订单/合同/中标/认证/量产/投产/扩产/产能/客户导入/项目落地等硬公司事实，或带金额/数量口径的公司级财务与出货事实，才允许进入 `## 边际变化`。
- 核心个股表、产业链名单、龙头/市占率/应用前景、仅百分比同比增长等 L1 研报判断，默认降级为 `graph_only` / `exposure_only`，用于 theme-radar 图谱和报告上下文，不污染实体正文。
- iFinD baseline 属于 L2：只写真实主营业务、主营产品、收入结构/毛利率等基础画像；不要把短期催化、新闻、规划或 unsupported `core` 混进 baseline。
- Baseline 弱映射统一用 `弱相关，待验证`，不要硬编模板化产业链角色；直接主营产品可以给 `core/high`。
- 不要盲跑下一批 baseline。若上一批质量/回填清理未完成，先审计 payload、实体页和 relations，再继续。

## PDF ingest / Theme Radar 对齐基准（2026-05-28）

脱水研报/强势脱水/评级日报/卖方材料默认 `source_quality=broker_research_high`，不直接写 `hard_fact` 或 `delta`，不把二手材料写进 `## 边际变化`。

三种路由：
- **curated_research**：`fact_hardness=review_candidate`，`evidence_layer=L1_L3_candidate`，写入 `## 高信度研究线索`，必须有注释
- **graph_only**：`fact_hardness=research_claim`，`strength=peripheral`，不写 entity markdown，source note 放 `## 仅更新图谱`
- **observation_only**：只放 `## 观察列表`，不进 entity_exposures

概念页规则：broker 源新建概念用 `## 高信度研究线索`，不用 `## 边际变化`。

Lint 能力（`pdf_ingest_lint.py`）：除 relations 检查外，还检查 concept page section、entity annotation、source note classification、graph_only consistency、evidence_index coverage。

回归样本集：0412评级日报/0412强势股脱水/0412脱水研报/0331强势脱水/0331脱水研报/0331评级日报（6篇全部 PASS）。

## 数据源

- **fupanhui.com**：市场数据、AI摘要、板块、连板梯队（内部 REST API）
- **iFinD**：个股查询、行业、概念板块（Node.js call-node.js）
- **AKShare**：板块历史涨幅（Python）
- **飞书 Bitable**：`pcnyt9i9lfme.feishu.cn/base/RnRfbT9F1asuFFsQpAyccMmHn2b`

## 飞书表

| 用途 | 表 | ID |
|------|-----|-----|
| 每日市场指标 | Bitable 每日指标 | `tbljGvjtl1IC44hb` |
| 板块趋势 | Bitable 板块趋势 | `tblshRMmRnQYrM4K` |
| 连板晋级 | Bitable 连板晋级 | （limit-advance skill 管理） |
| 板块每日涨跌幅+成交额 | Bitable sector_daily | `tblXqyf9Av1rGg0n` |
| 板块每日边际量 | 电子表格 sector_marginal_sheet | token `AHqIwJyMKiglO2kokwYcHRjJnWd`, sheet `e8a204` |

电子表格列序约定：新日期数据**写到最后一列**（最右侧空列），列排序由用户手动完成，**禁止自动插入/移位**。

## 凭证

飞书凭证：`~/.claude/shared/feishu_config.json`

## 本地工具链

- **DuckDB**：`db/market_feature_store.duckdb`（列存、零配置、单文件），同一时间只有一个写入连接
- **CDP Proxy**：`localhost:3456`，通过用户 Chrome 携带 fupanhui 登录态调用 API。启动：`node ~/.claude/skills/web-access/scripts/cdp-proxy.mjs`（需 Chrome 已开启 remote debugging，检查 `~/Library/Application Support/Google/Chrome/DevToolsActivePort`）
- **Python 脚本**：`scripts/` 目录，依赖 duckdb、urllib（标准库）

## 回填注意事项

- fupanhui API 有周/月调用上限（429 限流），大批量回填需分批
- CDP eval 用 IIFE `(function(){...})()` 包裹 + try/catch，避免页面 JS 异常中断
- 板块边际量字段（fupanhui API，对应主库 `fact_sector_daily`）：`diff_ratio`（边际量%）、`amount`（成交额亿）、`pct_chg`（涨幅%）
- 早期日期（2025年10-11月）只有 212 个板块有数据，后期扩展到 227 个
- **Kline API diff_ratio 偶发全零**：fupanhui sector-cycle kline API 偶尔返回所有板块 diff_ratio=0（显示错误）。workaround：用相邻交易日 amount 手动计算 `(today_amt - prev_amt) / prev_amt * 100`
- **DuckDB sector 名称不一致**：2-4月数据用 `.TI` 代码存储，5月数据用中文名存储。查询时需双路查找（先中文名、再代码、再模糊匹配）
- **电子表格条件格式**：公式用 `$A1` 引用板块名（非 `$A2`），每15个板块一条 `=OR()` 规则，单条过长会静默失效。公式汇总见 `条件格式公式.md`

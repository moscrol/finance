# Productization Roadmap：A 股主题投资情报工作台

更新时间：2026-06-11

## 1. 产品定位

本项目的目标是把现有的知识库、金融数据仓库和研究网站整理成一个可复用、可演示、可持续迭代的 FDE 型金融情报产品。

暂定产品名：

- 中文：题材情报工作台 / 市场情报工作台
- 英文：Market Intelligence Workbench / Theme Intelligence Workbench

一句话定义：

> 面向 A 股主题投资研究的 AI 情报工作台，融合市场 feature store、题材知识图谱、证据索引、策略复盘和研究发布流程，回答“主线在哪里、为什么发酵、谁受益、证据强不强、市场是否响应”。

核心用户场景：

- 每天市场主线在哪里？
- 哪些板块是容量板块？
- 哪些题材出现边际变化？
- 哪些公司与题材有关？证据强度如何？
- 策略今天应该开、关、观察还是降级？
- 哪些研究可以沉淀成对外文章？

## 2. 产品边界

### 2.1 当前要做

第一阶段聚焦“内部投研工作台”，把已有能力整理成稳定闭环：

1. 市场数据同步与 feature store。
2. 每日复盘生成与质量检查。
3. 策略矩阵与工作台展示。
4. 题材雷达与证据查询。
5. 研究内容发布到网站。

### 2.2 暂时不做

第一阶段不做以下事项：

- 不做大而全 Web App。
- 不合并三个仓库。
- 不重构整个知识库。
- 不引入复杂后端服务。
- 不做实时交易系统。
- 不做自动下单。
- 不把所有输出都塞进聊天机器人。
- 不把仍在验证中的策略假设包装成确定性交易规则。

## 3. 三仓职责

### 3.1 知识库仓库：Evidence Graph

路径：`/Users/lbq/Desktop/c c/知识库`

职责：

- 管理原始研报、公告、网页、PDF 等来源。
- 管理概念、题材、公司、实体。
- 管理公司与题材的暴露关系。
- 管理证据强度、来源质量和可追溯链路。
- 为 Theme Radar 和 AI Copilot 提供语义上下文。

关键资产：

- `raw/`
- `wiki/entities/`
- `wiki/concepts/`
- `wiki/sources/`
- `wiki/relations/entity_exposures.json`
- `wiki/relations/evidence_index.json`
- `wiki/relations/report_contexts.json`
- `skills/disclosure-archive/`

产品化后名称：

> Evidence Graph / Knowledge & Evidence Layer

### 3.2 金融仓库：Market Intelligence Engine

路径：`/Users/lbq/Desktop/c c/金融`

职责：

- 接入复盘会、AkShare、mootdx、Feishu 等数据源。
- 维护 DuckDB market feature store。
- 生成每日市场复盘。
- 生成策略矩阵和复盘工作台。
- 运行 Theme Radar 和市场触发题材分析。
- 承担第一阶段产品主引擎。

关键资产：

- `market_feature_store/sources/fupanhui_source.py`
- `market_feature_store/sync/`
- `market_feature_store/db.py`
- `market_feature_store/reports/daily_review.py`
- `market_feature_store/cli.py`
- `scripts/check_daily_review_data.py`
- `scripts/render_strategy*_matrix.py`
- `复盘/matrices/`
- `skills/theme-radar/scripts/radar.py`

产品化后名称：

> Market Intelligence Engine / Market Feature Store

### 3.3 金融网站仓库：Publishing Portal

路径：`/Users/lbq/Desktop/c c/windsurf/finance-research-site`

职责：

- 承载对外研究文章。
- 承载未来的题材页、公司页、市场页。
- 生成 SEO/GEO 和 AI 检索入口。
- 把内部工作台的精选输出变成公开内容。

关键资产：

- `src/content/research/`
- `scripts/validate-articles.mjs`
- `scripts/lint-articles.mjs`
- `scripts/build-llms-full.mjs`
- `scripts/indexnow.mjs`
- `public/llms.txt`
- `public/llms-full.txt`

产品化后名称：

> Publishing Portal / Public Research Surface

## 4. 核心数据流

整体架构：

```text
研报 / PDF / 公告 / 官网 / 互动易
  ↓
知识库 Evidence Graph
  ↓
题材、公司、证据、产业链上下文
  ↓
Theme Radar

复盘会 / AkShare / mootdx / Feishu
  ↓
Market Feature Store / DuckDB
  ↓
市场状态、板块信号、个股信号、策略矩阵

Theme Radar + Market Feature Store
  ↓
Market Intelligence Workbench
  ↓
内部工作台 / AI Copilot / 对外研究网站
```

五层产品抽象：

1. **Data Connectors**：复盘会、AkShare、mootdx、Feishu、PDF、公告、网页。
2. **Feature Store**：市场事实表、行业信号、个股信号、策略状态。
3. **Evidence Graph**：实体、概念、来源、证据、暴露关系、置信度。
4. **Intelligence Workflows**：每日复盘、题材雷达、策略矩阵、文章发布。
5. **Product Surfaces**：内部工作台、AI Copilot、Astro 研究网站、llms 文件。

## 5. 第一条产品闭环：每日复盘

第一阶段优先产品化每日复盘闭环，因为金融仓库已有成熟基础。

### 5.1 目标

把“日更脚本 + 检查脚本 + 报告生成 + 策略矩阵”封装成一个稳定 workflow。

目标命令形态：

```bash
python3 -m intelligence.cli daily --date YYYY-MM-DD
```

### 5.2 流程

```text
同步市场数据
  ↓
数据完整性检查
  ↓
生成每日复盘 Markdown/HTML
  ↓
生成市场触发题材简报
  ↓
更新策略矩阵
  ↓
刷新工作台
  ↓
输出 machine-readable summary
```

### 5.3 输入

- `trade_date`
- 是否跳过长耗时同步
- 是否刷新图表
- 是否重新生成策略矩阵
- 是否发布到网站

### 5.4 输出

- 每日复盘 Markdown。
- 每日复盘 HTML。
- 涨家数 MA5 图。
- 市场触发题材简报。
- 策略矩阵 HTML。
- 工作台 HTML。
- 数据完整性检查 summary。

### 5.5 质量闸门

必须检查：

- `fact_market_daily` 是否存在目标日期。
- `fact_sector_daily` 是否存在目标日期。
- `fact_stock_daily` 是否存在目标日期。
- 涨停、新高、连板等关键表是否覆盖。
- 核心市场字段是否为空。
- 日报是否仍有占位符。
- 策略矩阵是否使用 D0 口径。

如果检查失败：

- 不应进入发布阶段。
- 应输出缺失表、缺失字段和建议修复步骤。

## 6. 第二条产品闭环：Theme Radar

Theme Radar 是最有差异化的模块，第二阶段应将其产品化。

### 6.1 目标

输入一个题材、新词或公司，输出可追溯的题材情报卡。

标准输入：

```text
term: 题材名 / 新词 / 公司
mode: quick / deep-dive
evidence_policy: graph_only / official_only / mixed
market_date: optional
```

标准输出：

```text
definition
chain_map
demand_drivers
bottlenecks
entity_tiers
evidence_items
market_signals
opportunity_profile
missing_confirmations
rendered_markdown
rendered_html
```

### 6.2 流程

```text
输入题材
  ↓
查知识库概念/实体/证据
  ↓
查 report_contexts 研报上下文
  ↓
识别证据缺口
  ↓
必要时触发 disclosure archive
  ↓
查询市场信号
  ↓
生成 Theme Radar 结构化结果
  ↓
渲染 Markdown / HTML / 网站专题页
```

### 6.3 产品页面结构

1. **Definition Card**：题材定义。
2. **Chain Map**：产业链、上下游、瓶颈、需求。
3. **Evidence Board**：公司证据、证据强度、来源质量。
4. **Market Signal**：双红、涨停、新高、容量板块、市场阶段。
5. **Missing Confirmation**：仍需验证的事实缺口。

## 7. 需要抽象的服务接口

第一阶段先设计接口，不急于重写现有脚本。

### 7.1 KnowledgeAdapter

职责：把知识库从“文件目录”抽象成只读查询层。

建议接口：

```text
get_entity(name)
get_concept(term)
get_exposures(entity=None, concept=None)
get_evidence(target=None, concept=None)
get_report_context(term)
```

底层可以继续读 JSON / Markdown，不需要立即迁移数据库。

### 7.2 MarketAdapter

职责：把 DuckDB feature store 抽象成市场查询层。

建议接口：

```text
get_market_daily(date)
get_sector_daily(date)
get_top_capacity_sectors(date)
get_double_red_themes(date)
get_stock_highs(date)
get_limit_themes(date)
get_strategy_state(strategy, date)
```

### 7.3 DailyReviewService

职责：封装每日复盘工作流。

建议接口：

```text
run_daily_review(date, sync=True, validate=True, render=True)
validate_daily_review(date)
render_daily_review(date)
```

### 7.4 ThemeRadarService

职责：封装题材雷达工作流。

建议接口：

```text
run_theme_radar(term, mode="quick", market_date=None)
validate_theme_evidence(term)
render_theme_report(term)
```

### 7.5 StrategyMatrixService

职责：封装策略矩阵生成和复盘。

建议接口：

```text
render_strategy_matrix(strategy, date)
get_strategy_candidates(strategy, date)
validate_strategy_matrix(strategy, date)
```

### 7.6 PublishService

职责：把内部成果发布到网站仓库。

建议接口：

```text
export_research_article(source, target_slug)
validate_site_article(slug)
build_site()
push_indexnow(slug)
```

## 8. 质量闸门体系

产品化的核心不是生成更多内容，而是让每个输出都可验证。

### 8.1 数据完整性

检查对象：

- 市场总览。
- 行业/板块数据。
- 个股行情。
- 新高数据。
- 涨停热度。
- 连板晋级。

### 8.2 证据完整性

检查对象：

- 公司-题材暴露是否有来源。
- evidence_layer 是否明确。
- source_quality 是否明确。
- hard_delta 是否只来自强证据。
- graph_only / exposure_only 是否没有被误升级。

### 8.3 结论可追溯性

每个结论应能回指：

- 市场数据表。
- 研报来源。
- 公告/官网/互动易证据。
- 策略矩阵规则。
- 人工判断记录。

### 8.4 发布前校验

网站发布前必须通过：

```bash
npm run validate
npm run lint:articles
npm run build
```

## 9. 里程碑

### Milestone 1：架构文档化

目标：让未来的 agent 或协作者 10 分钟内看懂系统。

交付物：

- `docs/productization-roadmap.md`
- `docs/fde-skill-map.md`
- `docs/workflows/daily-review-workflow.md`
- `docs/workflows/theme-radar-workflow.md`

当前状态：进行中。

### Milestone 2：统一 CLI / Service Layer

目标：从脚本集合变成产品引擎。

候选命令：

```bash
python3 -m intelligence.cli daily --date YYYY-MM-DD
python3 -m intelligence.cli theme --term 商业航天
python3 -m intelligence.cli entity --name 华亚智能
python3 -m intelligence.cli validate --date YYYY-MM-DD
python3 -m intelligence.cli publish --slug xxx
```

当前状态：未开始。

### Milestone 3：Theme Radar 产品页

目标：把题材雷达结果变成结构化页面。

当前状态：未开始。

### Milestone 4：AI Copilot

目标：自然语言调用知识库、feature store 和策略记录。

首批支持问题：

1. 查询某日市场状态。
2. 查询某题材证据和核心公司。
3. 查询某公司题材暴露。
4. 查询某策略某日判断。
5. 生成某题材对外文章草稿。

当前状态：未开始。

## 10. 近期任务清单

- [x] 创建 FDE 产品化入口文档：`fde/README.md`。
- [x] 创建正式产品化路线文档：`docs/productization-roadmap.md`。
- [x] 创建 FDE 技能映射文档：`docs/fde-skill-map.md`。
- [x] 创建每日复盘 workflow 文档：`docs/workflows/daily-review-workflow.md`。
- [x] 创建 Theme Radar workflow 文档：`docs/workflows/theme-radar-workflow.md`。
- [x] 设计统一 CLI 命令和目录结构：`docs/unified-cli-design.md`。
- [x] 设计 KnowledgeAdapter 只读接口：`docs/adapters-design.md`。
- [x] 设计 MarketAdapter 只读接口：`docs/adapters-design.md`。
- [x] 设计 Theme Radar 标准 JSON schema：`docs/theme-radar-json-schema.md`。
- [x] 选择每日复盘闭环作为第一个实现任务，并完成 `intelligence.cli daily --dry-run` 最小实现。
- [x] 实现 `intelligence.cli daily` 真实执行模式（已通过 `--skip-sync --skip-theme --skip-workbench` 小步验证）。
- [x] 扩展 `intelligence.cli daily` 到题材简报和工作台刷新步骤（已通过 `--skip-sync` 小步验证）。
- [x] 设计并实现单步 resume / from-step 参数：`--from-step`、`--only-step`。
- [x] 受控验证 `daily-update` 同步步骤：`--only-step daily-update --skip-long` 已执行，底层外部 API 502 导致 FAIL，但质量闸门回归 COMPLETE。
- [x] 设计并实现数据源失败分级与 `--continue-on-warn` 策略：默认严格 FAIL，显式开启时 `daily-update` 非零返回但 `质检: OK` 可降级 WARN 并继续。
- [x] 回归完整 Daily CLI 链路并整理提交前变更清单：`py_compile`、full dry-run、真实 `--skip-sync` 五步链路均通过；提交前建议排除或人工确认 6.10 HTML 生成产物。
- [x] P1：实现 Adapter 最小版本：`MarketAdapter.health()`、`MarketAdapter.get_market_daily(date)`、`KnowledgeAdapter.load_relation(name)`、`KnowledgeAdapter.get_entity_exposures(entity)` 已实现并验证。
- [x] P1：扩展 Adapter 查询到容量行业与双红题材：`MarketAdapter.get_capacity_sectors()`、`MarketAdapter.get_double_red_themes()`、`KnowledgeAdapter.get_evidence()` 已实现并验证。
- [x] P1：为 Adapter 增加最小 CLI smoke 命令：`python3 -m intelligence.cli adapter-smoke --date 2026-06-10 --entity ASML` 与 `--summary-json` 已验证通过。
- [x] P2：组 ThemeRadarService 最小服务层：`ThemeRadarService.build_market_triggered_candidates(date)` 已实现并验证。
- [x] P2：接入 `theme` CLI 最小命令：`python3 -m intelligence.cli theme --date 2026-06-10 --market-triggered`、`--summary-json`、`--out-json` 已验证通过。
- [x] P2：为市场触发候选补知识库证据状态：`ThemeRadarService` 已接入 `KnowledgeAdapter.get_evidence()`，候选 JSON 含 `knowledge_status.evidence_count` 与 `knowledge_evidence`。
- [x] P2：为市场触发候选补概念/实体暴露匹配：`KnowledgeAdapter.get_concept_matches()`、`get_exposure_matches()` 已接入候选 JSON。
- [x] P2：生成 Top N 市场触发候选 Markdown 简报：`theme --out-md` 已实现并验证，默认不写文件，不调用大模型，不包含买卖指令。
- [x] P2：将 `theme --market-triggered` 输出接入 Daily CLI 可选产物：Daily CLI 新增 `theme-candidates` 步骤，输出 `YYYY-MM-DD-theme-candidates.json/md`，旧 HTML 产物保持并行。
- [x] P2：生成 `theme-candidates` 与旧题材简报对照验证报告：新增 `scripts/compare_theme_candidates.py`，输出 `YYYY-MM-DD-theme-candidates-qa.md`。

## 11. 下一步建议

下一步优先写：

```text
P2：多日期抽样验证 `theme-candidates` 与旧题材简报差异
```

目的：用少量代表性日期验证新 `ThemeRadarService` 候选产物与旧 `build_market_triggered_theme_brief.py` 产物的差异，形成排序、字段和补库缺口的稳定判断。

建议结构：

```text
1. 选择 3-5 个代表日期生成 `YYYY-MM-DD-theme-candidates-qa.md`
2. 汇总共同候选、仅新候选、仅旧候选和知识库缺口
3. 判断新 service 是否需要补充旧脚本的涨停热度、新高方向、连板集群信号
4. 决定哪些字段进入工作台，哪些字段仅保留为 QA/JSON
```

每一项都回答：

- 不输出交易建议。
- 不让旧脚本和新 service 互相覆盖产物。
- 对照验证先用少量日期，不批量重跑历史。
- 继续保留 `--skip-theme` 作为总开关。

## 12. 工作原则

- 先文档化，再接口化，再产品化。
- 先封装已有能力，不急于重写。
- 先内部工作台，不急于公开 Web App。
- 先每日复盘闭环，再 Theme Radar 产品页。
- 所有 AI 输出必须带数据来源或证据来源。
- 策略假设必须和已验证规则区分。
- 跨仓库修改前必须先确认三个仓库分支状态。

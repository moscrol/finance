# FDE 产品化路线与进展追踪

更新时间：2026-06-11 01:27

## 1. 目标

把现有三个仓库整理成一个可复用、可演示、可持续迭代的 FDE 型金融情报产品。

核心方向：

> 用 AI 把市场数据、题材知识图谱、证据索引、策略矩阵和研究发布流程串成一个完整的「A 股主题投资情报工作台」。

暂定产品名：

- 中文：题材情报工作台 / 市场情报工作台
- 英文：Market Intelligence Workbench / Theme Intelligence Workbench

一句话定义：

> 输入一个题材、公司或交易日，系统自动回答：这个方向是什么、为什么现在发酵、产业链谁受益、证据强不强、市场有没有响应、今日该重点观察哪些方向。

---

## 2. 三个仓库的产品角色

### 2.1 知识库仓库：Evidence Graph

路径：`/Users/lbq/Desktop/c c/知识库`

定位：证据型知识图谱与语义上下文底座。

关键资产：

- `raw/`：原始研报、材料、文本。
- `wiki/entities/`：公司/实体页面。
- `wiki/concepts/`：题材/概念页面。
- `wiki/sources/`：来源摘要页面。
- `wiki/relations/entity_exposures.json`：公司与题材暴露关系。
- `wiki/relations/evidence_index.json`：证据索引。
- `wiki/relations/report_contexts.json`：研报级产业链和题材上下文。
- `skills/disclosure-archive/`：官方证据归档、审核、入库流程。

产品职责：

- 回答某公司为什么和某题材有关。
- 区分研报观点、官方披露、公告事实、官网产品、互动易、弱线索。
- 为 Theme Radar 和 AI Copilot 提供可追溯上下文。

---

### 2.2 金融仓库：Market Intelligence Engine

路径：`/Users/lbq/Desktop/c c/金融`

定位：市场 feature store、数据同步、复盘生成、策略矩阵和题材雷达引擎。

关键资产：

- `market_feature_store/sources/fupanhui_source.py`：复盘会 CDP/API 数据源适配器。
- `market_feature_store/sync/`：市场、行业、个股、新高、涨停、连板等同步模块。
- `market_feature_store/db.py` + DuckDB：本地市场 feature store。
- `market_feature_store/reports/daily_review.py`：每日市场复盘生成器。
- `market_feature_store/cli.py`：已有 CLI 入口。
- `scripts/check_daily_review_data.py`：每日数据与报告完整性检查。
- `scripts/render_strategy*_matrix.py`：策略矩阵生成脚本。
- `复盘/matrices/`：策略矩阵和复盘工作台 HTML。
- `skills/theme-radar/scripts/radar.py`：题材雷达报告生成。

产品职责：

- 同步市场数据。
- 生成每日复盘。
- 生成市场状态、题材信号、策略候选和矩阵。
- 把知识库的题材/公司证据与市场信号结合。

---

### 2.3 金融网站仓库：Publishing Portal

路径：`/Users/lbq/Desktop/c c/windsurf/finance-research-site`

定位：对外研究发布、SEO/GEO、AI 可检索内容门户。

关键资产：

- `src/content/research/`：研究文章。
- `scripts/validate-articles.mjs`：文章 frontmatter 和内容校验。
- `scripts/lint-articles.mjs`：文章 lint。
- `scripts/build-llms-full.mjs`：生成 `llms-full.txt`。
- `scripts/indexnow.mjs`：搜索引擎推送。
- `public/llms.txt` / `public/llms-full.txt`：AI 检索入口。
- `src/pages/`：Astro 页面。

产品职责：

- 对外发布精选研究。
- 承载题材页、公司页、每日市场页。
- 给搜索引擎和 AI crawler 提供结构化入口。

---

## 3. 统一产品架构

目标架构：

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

五层抽象：

1. **Data Connectors**：复盘会、AkShare、mootdx、Feishu、PDF、公告、网页。
2. **Feature Store**：DuckDB 市场事实表、题材信号、个股信号、策略状态。
3. **Evidence Graph**：实体、概念、来源、证据、暴露关系、置信度。
4. **Intelligence Workflows**：每日复盘、题材雷达、策略矩阵、文章发布。
5. **Product Surfaces**：内部工作台、AI Copilot、Astro 研究网站、llms 文件。

---

## 4. FDE 技能映射

### 4.1 业务流程建模

已有基础：

- 每日市场复盘流程。
- 新题材研究流程。
- 公司题材暴露查询流程。
- 策略矩阵复盘流程。
- 研究文章发布流程。

需要沉淀：

- 把流程写成固定 workflow。
- 明确每一步输入、输出、失败条件、人工确认点。

---

### 4.2 数据与上下文接入

已有基础：

- fupanhui CDP 数据源。
- AkShare / mootdx / Feishu 数据同步。
- raw 研报和 PDF ingest。
- disclosure archive 官方证据归档。

需要沉淀：

- 抽象 connector 接口。
- 为知识库做只读 query adapter。
- 为 DuckDB feature store 做统一 market adapter。

---

### 4.3 模型接口设计

目标：

把“让 agent 写报告”升级为“稳定 AI 分析函数”。

Theme Radar 标准输入：

```text
term: 题材名 / 新词 / 公司
mode: quick / deep-dive
evidence_policy: graph_only / official_only / mixed
market_date: optional
```

Theme Radar 标准输出：

```text
definition
industry_chain
demand_drivers
bottlenecks
entity_tiers
evidence_table
market_signals
opportunity_profile
missing_confirmations
```

---

### 4.4 Workflow / Agent 编排

优先整理三个工作流：

#### A. 每日复盘闭环

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
可选发布/归档
```

#### B. 新题材研究闭环

```text
输入题材
  ↓
查知识库概念/实体/证据
  ↓
查研报上下文
  ↓
补官方 disclosure 缺口
  ↓
生成 Theme Radar
  ↓
映射市场板块和个股
  ↓
输出题材研究页
```

#### C. 研究文章发布闭环

```text
知识库研究稿
  ↓
转网站文章
  ↓
validate / lint
  ↓
生成 llms-full
  ↓
build
  ↓
发布
  ↓
IndexNow
```

---

### 4.5 Eval / 质量闸门

已有基础：

- `scripts/check_daily_review_data.py`
- daily review 数据覆盖检查。
- strategy matrix D0 口径检查。
- disclosure apply audit。
- website validate/lint/build。

需要统一成产品级质量闸门：

- 数据完整性。
- 证据完整性。
- 结论可追溯性。
- 策略口径一致性。
- 网站发布校验。
- AI 输出幻觉检查。

---

## 5. 产品化里程碑

### Milestone 1：架构文档化

目标：让别人 10 分钟看懂系统。

待产出：

- `docs/product-architecture.md`
- `docs/fde-skill-map.md`
- `docs/workflows/daily-review-workflow.md`
- `docs/workflows/theme-radar-workflow.md`

状态：未开始。

---

### Milestone 2：统一 CLI / Service Layer

目标：从脚本集合变成产品引擎。

建议命令形态：

```bash
python3 -m intelligence.cli daily --date YYYY-MM-DD
python3 -m intelligence.cli theme --term 商业航天
python3 -m intelligence.cli entity --name 华亚智能
python3 -m intelligence.cli validate --date YYYY-MM-DD
python3 -m intelligence.cli publish --slug xxx
```

第一阶段只封装已有脚本，不重写核心逻辑。

状态：未开始。

---

### Milestone 3：Theme Radar 产品页

目标：把最有差异化的题材雷达能力可视化。

页面结构：

1. Definition Card：题材定义。
2. Chain Map：产业链、上下游、瓶颈、需求。
3. Evidence Board：公司证据、证据强度、来源质量。
4. Market Signal：双红、涨停、新高、容量板块、市场阶段。
5. Missing Confirmation：仍需验证的事实缺口。

状态：未开始。

---

### Milestone 4：AI Copilot

目标：自然语言调用知识库、feature store 和策略记录。

初版支持 5 类问题：

1. 查询某日市场状态。
2. 查询某题材证据和核心公司。
3. 查询某公司题材暴露。
4. 查询某策略某日判断。
5. 生成某题材对外文章草稿。

状态：未开始。

---

## 6. 优先级最高的下一步

### Step 1：先做文档，不写代码

建议新建：

```text
docs/productization-roadmap.md
```

内容：

- 产品定位。
- 三仓职责。
- 数据流。
- 核心 workflow。
- FDE 技能映射。
- 里程碑。
- 哪些模块先封装。
- 哪些暂时不做。

---

### Step 2：封装每日复盘闭环

原因：金融仓库里的每日复盘已经最成熟，最适合作为第一个产品化闭环。

目标命令：

```bash
python3 -m intelligence.cli daily --date YYYY-MM-DD
```

内部步骤：

1. `daily-update`
2. `check_daily_review_data.py`
3. `daily-review`
4. 策略矩阵生成
5. 工作台刷新
6. 输出 summary

---

### Step 3：做 KnowledgeAdapter

目标：让 AI 不直接读大目录正文，而是通过查询接口访问知识库。

建议接口：

```text
get_entity(name)
get_concept(term)
get_exposures(entity=None, concept=None)
get_evidence(target=None, concept=None)
get_report_context(term)
```

底层先读 JSON / Markdown，不需要上数据库。

---

### Step 4：做 Theme Radar 标准输出 JSON

目标：让题材雷达从“报告文本”升级为“产品数据结构”。

建议输出：

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

---

## 7. 当前待办清单

- [x] 盘点金融仓库现有能力与边界。
- [x] 盘点知识库仓库现有能力与边界。
- [x] 盘点金融网站仓库现有能力与边界。
- [x] 映射到 FDE 通用技能包。
- [x] 提出产品化架构与复用路线。
- [x] 给出可执行学习/迭代路径。
- [x] 写正式产品架构文档：`docs/productization-roadmap.md`。
- [x] 写 FDE 技能映射文档：`docs/fde-skill-map.md`。
- [x] 写每日复盘 workflow 文档：`docs/workflows/daily-review-workflow.md`。
- [x] 写 Theme Radar workflow 文档：`docs/workflows/theme-radar-workflow.md`。
- [x] 设计统一 CLI 命令形态：`docs/unified-cli-design.md`。
- [x] 设计 KnowledgeAdapter 只读接口：`docs/adapters-design.md`。
- [x] 设计 MarketAdapter 只读接口：`docs/adapters-design.md`。
- [x] 设计 Theme Radar 标准 JSON schema：`docs/theme-radar-json-schema.md`。
- [x] 选择每日复盘闭环作为第一个可实现的产品化闭环，并完成 `intelligence.cli daily --dry-run` 最小实现。
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

---

## 8. 下次继续时怎么做

下次打开本目录后，优先读取本文件。

建议继续顺序：

1. 先确认当前分支和工作区状态。
2. 读取本文件，恢复产品化上下文。
3. 如果要写代码或文档，先判断是否需要新建分支。
4. 优先做多日期抽样验证：用 `scripts/compare_theme_candidates.py` 比较新 `theme-candidates` 与旧 `triggered-themes`，判断是否补充涨停热度、新高方向、连板集群信号。
5. 不要直接大改三仓，先做文档和接口设计。

---

## 9. Git 安全提醒

金融仓库当前盘点时所在分支：`review/2026-06-10`。

任何以下任务都应先新建任务分支：

- 新增产品文档批次。
- 修改 `market_feature_store`。
- 新增统一 CLI。
- 改 Theme Radar。
- 改策略矩阵生成逻辑。
- 跨知识库/金融/网站仓库联动。

建议分支名：

```text
fde/productization-roadmap
fde/daily-workflow
fde/theme-radar-product
fde/knowledge-adapter
```

提交前不要提交：

- `.env*`
- `mcp_config.json`
- `feishu_config.json`
- `*.pdf`
- `*.zip`
- `*.duckdb`
- `*.db`
- `*.sqlite*`
- `*.pptx`
- `.DS_Store`
- 缓存、虚拟环境、构建产物

---

## 10. 项目叙事草稿

可用于后续 FDE 作品集或对外介绍：

> 我做了一个面向 A 股主题投资研究的 AI 市场情报工作台。它把复盘会、AkShare、mootdx、Feishu 等市场数据源同步到 DuckDB feature store，同时把研报、公告、官网和互动易证据沉淀到知识图谱。系统每天先做数据完整性校验，再生成市场状态、题材边际量、行业容量、个股发动机、新高/涨停映射和策略候选。对新题材，它能从知识图谱里找产业链、公司暴露和证据强度，再结合市场信号判断发酵阶段。所有结论都带证据层级，避免 AI 胡说。精选内容可以发布到 Astro 研究网站，并生成 AI 可检索的 llms 文件。

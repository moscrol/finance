# FDE Skill Map：用本项目训练可复用 AI 交付能力

更新时间：2026-06-11

## 1. 文档目的

这份文档把当前三仓项目映射到 Forward Deployed Engineer 所需的通用能力。

它的用途有三类：

1. **学习地图**：明确每个 FDE 能力在本项目中对应哪个真实模块。
2. **复用模板**：后续做其他行业或项目时，可以按同一结构检查是否具备完整闭环。
3. **作品集叙事**：把“我写了很多脚本”转化为“我交付了一个可验证的 AI 业务系统”。

核心判断：

> 这个项目可以作为后续 FDE 项目的参考样板：先识别业务流程，再接入数据与上下文，最后封装工作流、质量闸门和产品界面。

## 2. 总体能力框架

本项目可拆成 7 个 FDE 能力层：

1. Business Process Modeling：业务流程建模。
2. Data & Context Integration：数据与上下文接入。
3. Model Interface Design：模型接口与提示词/工具设计。
4. Workflow / Agent Orchestration：工作流与 Agent 编排。
5. Evaluation & Observability：评估、质检与可观测性。
6. Product Integration：产品化与用户界面集成。
7. Deployment / Handoff：部署、交接与组织落地。

通用公式：

```text
业务问题
  ↓
数据源 + 上下文源
  ↓
结构化数据模型
  ↓
AI / 规则 / 工具调用
  ↓
质量闸门
  ↓
用户可用的产品界面
  ↓
持续迭代与交接
```

## 3. Business Process Modeling：业务流程建模

### 3.1 当前项目已有模块

已有业务流程：

- 每日市场复盘。
- 题材雷达分析。
- 公司题材暴露查询。
- 策略矩阵复盘。
- PDF / 研报 ingest。
- disclosure archive 官方证据补证。
- 研究文章发布。

对应文件和目录：

- `market_feature_store/reports/daily_review.py`
- `scripts/render_strategy*_matrix.py`
- `skills/theme-radar/scripts/radar.py`
- `scripts/check_daily_review_data.py`
- `/Users/lbq/Desktop/c c/知识库/skills/disclosure-archive/`
- `/Users/lbq/Desktop/c c/windsurf/finance-research-site/scripts/`

### 3.2 对应 FDE 能力

FDE 不是直接问“能不能用 AI 生成答案”，而是先问：

- 用户原来的业务流程是什么？
- 哪些步骤耗时、重复、容易出错？
- 哪些步骤需要人工判断？
- 哪些步骤可以自动化？
- 哪些结论必须可追溯？

本项目对应的是 A 股主题投资研究流程：

```text
市场数据更新
  ↓
识别市场状态
  ↓
识别题材和行业边际变化
  ↓
关联公司和证据
  ↓
生成策略候选和复盘矩阵
  ↓
沉淀研究内容
```

### 3.3 当前缺口

- 多数流程还散落在脚本、skill 和人工操作里。
- 每条 workflow 的输入、输出、失败条件、人工确认点还没有完全标准化。
- 策略判断中仍有部分人工语义规则，需要明确是 hypothesis 还是 verified rule。

### 3.4 下一步训练方式

先文档化两条核心流程：

1. `docs/workflows/daily-review-workflow.md`
2. `docs/workflows/theme-radar-workflow.md`

每条流程必须写清：

- 触发条件。
- 输入参数。
- 数据依赖。
- 执行步骤。
- 质量闸门。
- 输出文件。
- 常见失败和修复方式。

## 4. Data & Context Integration：数据与上下文接入

### 4.1 当前项目已有模块

市场数据源：

- 复盘会：`market_feature_store/sources/fupanhui_source.py`
- AkShare：`market_feature_store/sync/sync_akshare_*`
- mootdx：`market_feature_store/sync/sync_mootdx_stock_daily.py`
- Feishu：`market_feature_store/sync/sync_feishu_*`

知识上下文源：

- `wiki/entities/`
- `wiki/concepts/`
- `wiki/sources/`
- `wiki/relations/entity_exposures.json`
- `wiki/relations/evidence_index.json`
- `wiki/relations/report_contexts.json`
- `raw/`

发布上下文源：

- `src/content/research/`
- `public/llms.txt`
- `public/llms-full.txt`

### 4.2 对应 FDE 能力

这对应 FDE 的企业数据接入能力：

- 非标准 API 接入。
- 登录态网页数据接入。
- 本地数据库标准化。
- 文档和知识库结构化。
- 证据来源分层。
- 对 AI 提供可控上下文，而不是让模型自由猜。

### 4.3 当前缺口

- 数据源适配器没有统一 connector 协议。
- 知识库仍主要通过文件和 JSON 直接访问，缺少只读查询层。
- 市场 feature store 缺少统一 adapter，调用方需要知道表结构。
- 跨仓库路径和依赖关系还没有完全产品化。

### 4.4 下一步训练方式

优先设计两个只读 adapter：

```text
KnowledgeAdapter
MarketAdapter
```

建议接口：

```text
KnowledgeAdapter.get_entity(name)
KnowledgeAdapter.get_concept(term)
KnowledgeAdapter.get_exposures(entity=None, concept=None)
KnowledgeAdapter.get_evidence(target=None, concept=None)
KnowledgeAdapter.get_report_context(term)

MarketAdapter.get_market_daily(date)
MarketAdapter.get_sector_daily(date)
MarketAdapter.get_top_capacity_sectors(date)
MarketAdapter.get_double_red_themes(date)
MarketAdapter.get_stock_highs(date)
MarketAdapter.get_limit_themes(date)
```

## 5. Model Interface Design：模型接口与工具设计

### 5.1 当前项目已有模块

已有 AI / Agent 接口雏形：

- `skills/theme-radar/`：题材雷达分析。
- `skills/pdf-ingest/`：研报入库。
- `skills/company-baseline-ingest/`：公司基础画像。
- `skills/concept-ingest/`：概念入库。
- 研究网站的内容加工脚本。
- 每日复盘中的规则化文本生成。

### 5.2 对应 FDE 能力

FDE 需要把模型能力变成稳定接口，而不是只让模型自由写作。

典型问题：

- 输入是什么？
- 输出 schema 是什么？
- 工具可以调用哪些数据？
- 哪些结论必须引用证据？
- 置信度如何表达？
- 失败时如何降级？

### 5.3 当前缺口

- Theme Radar 输出仍偏报告文本，结构化 schema 还不够固定。
- AI Copilot 尚未定义工具列表和 routing 规则。
- 不同 skill 的输入输出风格不完全统一。
- 证据引用、市场数据引用和人工判断引用还没有统一格式。

### 5.4 下一步训练方式

先为 Theme Radar 定义标准 JSON 输出：

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

再定义首批 Copilot 工具：

```text
get_market_state(date)
get_theme_profile(term)
get_entity_exposure(entity)
get_theme_evidence(term)
get_strategy_state(strategy, date)
```

## 6. Workflow / Agent Orchestration：工作流与 Agent 编排

### 6.1 当前项目已有模块

已有 workflow：

- `market_feature_store/sync/sync_daily_full.py`：每日数据同步编排。
- `market_feature_store/cli.py`：命令行入口。
- `market_feature_store/reports/daily_review.py`：复盘生成。
- `scripts/check_daily_review_data.py`：复盘数据检查。
- `skills/disclosure-archive/scripts/apply_review_queue.py`：官方证据审核入库。
- 研究网站 `npm run build`：validate、lint、llms、Astro build。

### 6.2 对应 FDE 能力

FDE 的核心不是单点自动化，而是把多个工具编成可靠流程。

对应能力：

- 任务分解。
- 顺序执行。
- 失败阻断。
- 人工确认。
- dry-run / apply 分层。
- 输出 summary。
- 可重复运行。

### 6.3 当前缺口

- 每日复盘闭环还没有一个统一高层 service。
- Theme Radar 还没有统一和 market feature store 合并的 workflow。
- 网站发布和内部研究输出之间仍有手动衔接。
- 缺少统一 workflow summary 格式。

### 6.4 下一步训练方式

第一阶段封装每日复盘 workflow：

```text
DailyReviewService.run(date)
```

内部执行：

1. sync。
2. validate。
3. render daily review。
4. render strategy matrices。
5. render workbench。
6. output summary。

## 7. Evaluation & Observability：评估、质检与可观测性

### 7.1 当前项目已有模块

已有质量闸门：

- `scripts/check_daily_review_data.py`
- `daily_review.py` 内的数据覆盖检查。
- strategy matrix 的 D0 口径校验意识。
- disclosure apply 的 dry-run / apply / backup / audit。
- 网站 `validate-articles.mjs`、`lint-articles.mjs`、`astro build`。

### 7.2 对应 FDE 能力

AI 系统的质量不只看输出是否漂亮，而看：

- 数据是否完整。
- 证据是否可靠。
- 结论是否可追溯。
- 输出是否符合 schema。
- 失败是否可定位。
- 是否能重复运行。

### 7.3 当前缺口

- 质量检查分散在不同脚本中。
- 缺少统一 validate 命令。
- 缺少跨仓库发布前检查清单。
- AI 输出的 hallucination check 还没有工程化。

### 7.4 下一步训练方式

设计统一质量命令：

```bash
python3 -m intelligence.cli validate --date YYYY-MM-DD
python3 -m intelligence.cli validate-theme --term 商业航天
python3 -m intelligence.cli validate-publish --slug xxx
```

并统一输出：

```text
status: PASS / WARN / FAIL
missing_data: []
missing_evidence: []
warnings: []
next_actions: []
```

## 8. Product Integration：产品化与用户界面集成

### 8.1 当前项目已有模块

已有产品界面：

- 每日复盘 Markdown / HTML。
- 策略矩阵 HTML。
- `strategy-review-workbench.html`。
- Theme Radar 报告。
- 研究网站 Astro 页面。
- `llms.txt` / `llms-full.txt`。

### 8.2 对应 FDE 能力

FDE 需要把 AI 能力放进用户真实工作界面，而不是停留在 demo。

本项目适合的产品界面：

- 内部工作台。
- 题材雷达页。
- 公司画像页。
- 策略矩阵页。
- 对外研究文章页。
- AI Copilot 问答入口。

### 8.3 当前缺口

- 内部工作台入口还可以更统一。
- Theme Radar 结果还没有稳定产品页。
- 网站还主要是文章站，尚未承载题材页、公司页、市场页。
- 内部版和公开版的边界还需要明确。

### 8.4 下一步训练方式

先定义三类页面：

```text
/market/YYYY-MM-DD    每日市场页
/themes/<slug>        题材雷达页
/entities/<slug>      公司暴露页
```

第一阶段只做静态生成，不引入复杂后端。

## 9. Deployment / Handoff：部署、交接与组织落地

### 9.1 当前项目已有模块

已有部署和交接基础：

- 金融仓库 CLI。
- 网站仓库 `npm run build`。
- Cloudflare / Wrangler 配置。
- `AGENTS.md` 和 `CLAUDE.md` 规则。
- `fde/README.md` 作为上下文入口。
- 本文档作为 FDE 能力地图。

### 9.2 对应 FDE 能力

FDE 交付不是自己能跑就行，还要让未来的自己、其他 agent 或团队成员能接手。

关键能力：

- 操作手册。
- 分支规则。
- 质量检查。
- 回滚方式。
- 故障定位。
- 成果说明。

### 9.3 当前缺口

- 还缺一键工作流操作手册。
- 还缺每个 workflow 的失败恢复指南。
- 还缺“从知识库到网站发布”的跨仓库交接文档。

### 9.4 下一步训练方式

为每条 workflow 写 handoff 文档：

```text
docs/workflows/daily-review-workflow.md
docs/workflows/theme-radar-workflow.md
docs/workflows/publish-workflow.md
```

## 10. 复用到其他项目的方法

后续做任何新项目，可以对照以下模板。

### 10.1 先问业务流程

```text
这个项目服务谁？
用户每天/每周重复做什么？
哪些步骤最耗时？
哪些判断需要专家经验？
哪些结果必须可追溯？
```

### 10.2 再拆数据和上下文

```text
结构化数据在哪里？
非结构化文档在哪里？
哪些数据源需要登录态/API/爬取？
哪些上下文需要长期沉淀？
哪些字段是质量闸门？
```

### 10.3 再定义工作流

```text
触发条件是什么？
输入是什么？
中间步骤是什么？
失败在哪里阻断？
输出给谁看？
哪些步骤需要人工确认？
```

### 10.4 再设计 AI 接口

```text
模型负责判断什么？
工具负责查询什么？
输出 schema 是什么？
证据怎么引用？
置信度怎么表达？
失败时怎么降级？
```

### 10.5 最后做产品界面

```text
用户应该看表格、矩阵、报告、卡片还是聊天框？
哪些内容内部可见？
哪些内容可以公开？
哪些内容适合让 AI crawler 读取？
```

## 11. 本项目作为样板的使用方式

后续做其他项目时，可以直接对照本项目：

| 通用问题 | 本项目参考 |
|---|---|
| 数据源怎么接 | `market_feature_store/sources/` 和 `sync/` |
| 本地 feature store 怎么建 | DuckDB + `schema.sql` + fact tables |
| 知识库怎么组织 | `entities` / `concepts` / `sources` / `relations` |
| 证据怎么分层 | `evidence_index.json` + disclosure archive |
| 工作流怎么编排 | `sync_daily_full.py` + CLI + check scripts |
| 输出怎么产品化 | daily review HTML + strategy matrices + Astro site |
| 质量怎么控制 | check scripts + dry-run/apply + validate/lint/build |
| 怎么交接给 agent | `AGENTS.md` + `fde/README.md` + docs |

## 12. 近期学习与执行顺序

建议顺序：

1. 写完架构文档和能力地图。
2. 写每日复盘 workflow 文档。
3. 写 Theme Radar workflow 文档。
4. 设计统一 CLI。
5. 做 KnowledgeAdapter 和 MarketAdapter。
6. 封装 DailyReviewService。
7. 让 Theme Radar 输出标准 JSON。
8. 再考虑 AI Copilot 和网站专题页。

当前下一步：

```text
docs/workflows/daily-review-workflow.md
```

原因：每日复盘闭环最成熟，最适合作为第一个真正产品化执行对象。

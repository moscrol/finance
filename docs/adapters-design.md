# Adapters Design：KnowledgeAdapter 与 MarketAdapter 只读接口设计

更新时间：2026-06-11

## 1. 目标

Adapter 层的目标是把底层文件、JSON 和 DuckDB 表结构抽象成稳定查询接口，供统一 CLI、workflow、service 和未来 AI Copilot 复用。

核心原则：

> Adapter 第一阶段只读，不写入，不重构底层数据，不替代现有脚本。

两个核心 adapter：

```text
KnowledgeAdapter：读取知识库 Evidence Graph
MarketAdapter：读取金融仓库 Market Feature Store
```

它们在产品架构中的位置：

```text
知识库 relations / markdown        DuckDB market_feature_store
          ↓                                  ↓
   KnowledgeAdapter                    MarketAdapter
          ↓                                  ↓
        ThemeRadarService / DailyReviewService / AI Copilot / CLI
```

## 2. 设计边界

### 2.1 第一阶段只做

- 读取 JSON。
- 读取少量明确目标 Markdown。
- 读取 DuckDB。
- 返回结构化 dict/list。
- 提供稳定方法名。
- 控制大文件和正文读取范围。
- 提供清晰错误信息。

### 2.2 第一阶段不做

- 不写入知识库。
- 不写入 DuckDB。
- 不更新 `entity_exposures.json`。
- 不更新 `evidence_index.json`。
- 不创建实体页或概念页。
- 不跑 PDF ingest。
- 不跑 disclosure archive apply。
- 不做向量数据库。
- 不一次读取整个 `entities/`、`concepts/`、`sources/` 正文。

## 3. 建议目录

与统一 CLI 设计保持一致：

```text
intelligence/
├── adapters/
│   ├── __init__.py
│   ├── knowledge.py
│   └── market.py
├── paths.py
└── summary.py
```

## 4. 路径配置

建议集中在：

```text
intelligence/paths.py
```

默认路径：

```python
FINANCE_ROOT = "/Users/lbq/Desktop/c c/金融"
KNOWLEDGE_WIKI = "/Users/lbq/Desktop/c c/知识库/wiki"
FINANCE_SITE = "/Users/lbq/Desktop/c c/windsurf/finance-research-site"
```

环境变量覆盖：

```text
FINANCE_ROOT
KNOWLEDGE_WIKI
FINANCE_SITE
MARKET_DB_PATH
```

路径原则：

- 默认路径服务本机使用。
- 环境变量服务未来迁移。
- Adapter 初始化时只校验路径存在，不主动创建目录。

## 5. KnowledgeAdapter

### 5.1 职责

`KnowledgeAdapter` 负责从知识库读取：

- 概念图谱。
- 公司-题材暴露。
- 证据索引。
- 研报上下文。
- 别名。
- 题材信号。
- benchmark maps。
- 单个 entity/concept/source 页面。

它不负责：

- 改写 wiki。
- 生成新页面。
- 变更 evidence layer。
- 把弱证据升级为强证据。

### 5.2 数据源

核心 relations：

```text
wiki/relations/concept_graph.json
wiki/relations/entity_exposures.json
wiki/relations/aliases.json
wiki/relations/evidence_index.json
wiki/relations/theme_signals.json
wiki/relations/pattern_library.json
wiki/relations/report_contexts.json
wiki/relations/benchmark_maps.json
```

可选页面：

```text
wiki/entities/{name}.md
wiki/concepts/{term}.md
wiki/sources/{source}.md
wiki/synthesis/{topic}.md
```

### 5.3 初始化

建议接口：

```python
adapter = KnowledgeAdapter(wiki_root: str | Path | None = None)
```

初始化行为：

- 解析 wiki 根目录。
- 记录 `relations_dir`。
- 不读取全部文件。
- 不扫描全目录正文。

### 5.4 基础方法

```python
load_relation(name: str) -> dict
relation_path(name: str) -> Path
page_path(kind: str, name: str) -> Path
page_exists(kind: str, name: str) -> bool
read_page(kind: str, name: str, max_chars: int = 12000) -> dict
```

`read_page` 返回：

```json
{
  "kind": "entity",
  "name": "华亚智能",
  "path": "wiki/entities/华亚智能.md",
  "exists": true,
  "frontmatter": {},
  "text": "...",
  "truncated": false
}
```

注意：

- 只允许读取明确目标页面。
- `max_chars` 默认限制，避免误读大文件。
- 不提供 `read_all_entities()` 这类接口。

### 5.5 概念查询

```python
get_concept(term: str, include_page: bool = False) -> dict
resolve_concept(term: str) -> dict
get_related_concepts(term: str, limit: int = 20) -> dict
```

返回示例：

```json
{
  "query": "商业航天",
  "canonical": "商业航天",
  "aliases": [],
  "found": true,
  "related_concepts": [],
  "page": null
}
```

### 5.6 实体查询

```python
get_entity(name: str, include_page: bool = False) -> dict
find_entities_by_concept(concept: str, strength: str | None = None, limit: int = 50) -> dict
get_entity_exposures(entity: str) -> dict
```

返回示例：

```json
{
  "entity": "华亚智能",
  "found": true,
  "codes": ["003043"],
  "concepts": {
    "半导体设备": {
      "strength": "related",
      "role": "设备零部件供应商",
      "evidence_layer": "L2",
      "update_type": "baseline",
      "sources": []
    }
  },
  "page": null
}
```

### 5.7 证据查询

```python
get_evidence(target: str | None = None, concept: str | None = None, target_type: str | None = None, min_layer: str | None = None, limit: int = 100) -> dict
get_concept_evidence(concept: str, limit: int = 100) -> dict
get_entity_concept_evidence(entity: str, concept: str, limit: int = 50) -> dict
```

返回示例：

```json
{
  "target": "华亚智能",
  "concept": "半导体设备",
  "count": 2,
  "items": [
    {
      "source": "[[disc-20260528-0001]]",
      "source_date": "2026-05-28",
      "target_type": "entity",
      "target": "华亚智能",
      "concept": "半导体设备",
      "evidence": "...",
      "confidence": "high",
      "evidence_layer": "L2",
      "update_type": "baseline",
      "source_quality": "official_disclosure"
    }
  ]
}
```

### 5.8 Report Context 查询

```python
get_report_context(term: str, limit: int = 20) -> dict
search_report_contexts(term: str, fields: list[str] | None = None, limit: int = 20) -> dict
```

用途：

- Theme Radar 新词画像。
- 题材方向扫描。
- 从研报上下文补 demand drivers、bottlenecks、company mentions。

### 5.9 Readiness 支持查询

```python
get_theme_readiness_inputs(theme: str) -> dict
```

返回：

- concept graph 中相关概念。
- entity exposures 中相关公司。
- evidence index 中相关证据。

注意：

- readiness 计算本身仍由 `scripts/build_theme_evidence_readiness.py` 负责。
- Adapter 只提供输入查询。

## 6. MarketAdapter

### 6.1 职责

`MarketAdapter` 负责从 DuckDB 读取：

- 市场总览。
- 容量行业。
- 板块边际量。
- 双红/单红题材。
- 个股新高。
- 涨停热度。
- 连板晋级。
- 板块成分股。
- 策略所需的市场状态。

它不负责：

- 同步数据。
- 写入 DuckDB。
- 修复缺失字段。
- 回补历史数据。
- 生成 HTML。

### 6.2 数据源

DuckDB：

```text
db/market_feature_store.duckdb
```

连接函数：

```python
market_feature_store.db.connect(read_only=True)
```

已有查询层：

```text
market_feature_store/query.py
```

可复用现有函数：

```text
health
sector_stocks
stock_sectors
stock_highs
sw_l1_signal_peaks
strong_subtheme_trace
limit_heat
advancers_extrema
top_sectors
weighted_gainers
interval_gainers
```

### 6.3 初始化

```python
adapter = MarketAdapter(db_path: str | Path | None = None)
```

初始化行为：

- 记录 db path。
- 默认 read-only。
- 不创建数据库。
- 不执行 schema init。

### 6.4 基础方法

```python
health() -> dict
latest_date(table: str = "fact_market_daily") -> str | None
has_trade_date(table: str, date: str) -> bool
validate_daily_coverage(date: str) -> dict
```

`validate_daily_coverage` 可复用 `scripts/check_daily_review_data.py` 的规则，但第一阶段可先通过 subprocess 包装，不急于重写。

### 6.5 市场状态查询

```python
get_market_daily(date: str | None = None) -> dict
get_market_state(date: str | None = None) -> dict
get_capacity_sectors(date: str | None = None, top: int = 3) -> dict
```

容量行业定义：

```text
容量板块：成交占比 ratio > 15
超级容量板块：成交占比 ratio > 25
```

返回示例：

```json
{
  "trade_date": "2026-06-10",
  "market_stage": "下跌阶段",
  "advancers": 1556,
  "total_amount": 26401,
  "top3_industry_ratio": 48.1,
  "capacity_sectors": [
    {"rank": 1, "name": "电子", "ratio": 29.4, "capacity_type": "super_capacity"},
    {"rank": 2, "name": "通信", "ratio": 10.1, "capacity_type": "normal"}
  ]
}
```

### 6.6 题材信号查询

```python
get_top_sectors(date: str, order_by: str = "diff_ratio", top: int = 20) -> dict
get_double_red_themes(date: str, top: int = 50) -> dict
get_single_red_themes(date: str, top: int = 50) -> dict
get_theme_daily(theme: str, date: str | None = None) -> dict
```

双红定义：

```text
双红题材 = pct_chg > 0 AND diff_ratio > 10 AND amount > 500
单红题材 = pct_chg > 0 AND diff_ratio > 10 AND amount <= 500
（正典：`market_feature_store/signals.py::SINGLE_RED_SQL`，勿在此处手抄阈值。
 旧版这一行漏了 `pct_chg > 0`，按它写会把**下跌**但边际量大的板块算成单红；
 「或不满足 amount > 500」也漏了成交额缺失的情况——缺数既不算单红也不算双红。）
```

注意：

- 用户旧定义中常强调 diff_ratio > 10 且 amount > 500；产品层建议同时保留 `pct_chg > 0` 作为确认条件，以匹配策略验证最新口径。
- 返回中应保留原始 `pct_chg`、`diff_ratio`、`amount`，不只返回标签。

### 6.7 个股与板块查询

```python
get_sector_stocks(sector: str, date: str | None = None, top: int = 20, order_by: str = "amount") -> dict
get_stock_sectors(stock: str, date: str | None = None) -> dict
get_stock_highs(date: str | None = None, period: str | None = None, top: int = 20) -> dict
get_limit_heat(date: str | None = None, theme: str | None = None, with_stocks: bool = False) -> dict
```

这些接口可直接封装 `market_feature_store.query` 中已有函数。

### 6.8 策略支持查询

```python
get_main_liquidity_pool(date: str) -> dict
get_strategy1_context(date: str) -> dict
get_strategy3_context(date: str) -> dict
get_second_board_context(date: str) -> dict
```

主线流动性池定义：

```text
当日成交占比前三申万一级行业 + 双红题材池
```

用途：

- 策略验证。
- 每日复盘。
- AI Copilot 问“今天主线在哪里”。

第一阶段可以只设计接口，不立即实现全部策略 context。

## 7. 返回值规范

所有 adapter 方法返回 dict，不直接 print。

统一字段：

```json
{
  "ok": true,
  "query": {},
  "data": {},
  "warnings": [],
  "errors": [],
  "source": {
    "type": "duckdb/json/markdown",
    "path": "...",
    "read_only": true
  }
}
```

简化场景可直接返回业务 dict，但 service 层应包装为统一格式。

## 8. 错误处理

### 8.1 KnowledgeAdapter 错误

常见错误：

- wiki root 不存在。
- relations 文件不存在。
- JSON 解析失败。
- 目标页面不存在。
- 页面过大被截断。

处理原则：

- 缺文件返回 `ok=false` 或空结构 + warning。
- JSON 解析失败必须 error。
- 目标页面不存在不是 fatal，返回 `exists=false`。
- 不自动创建文件。

### 8.2 MarketAdapter 错误

常见错误：

- DuckDB 文件不存在。
- 表不存在。
- 目标日期无数据。
- 查询字段不存在。

处理原则：

- DB 不存在：fatal。
- 表不存在：fatal。
- 日期无数据：warning 或 fail，取决于调用场景。
- 字段不存在：fatal，因为意味着 schema drift。

## 9. 性能与 token 约束

必须遵守：

- 不批量读取 `wiki/entities/` 正文。
- 不批量读取 `wiki/concepts/` 正文。
- 不批量读取 `wiki/sources/` 正文。
- 优先读取 relations JSON。
- 需要正文时只读明确目标页面。
- 默认限制正文字符数。
- 对大 JSON 查询先过滤字段，不把全量内容塞给 AI。

## 10. 与 CLI / Service 的关系

```text
intelligence.cli
  ↓
workflow
  ↓
service
  ↓
adapter
  ↓
DuckDB / JSON / Markdown
```

示例：

```text
intelligence.cli theme --term 商业航天
  ↓
ThemeRadarWorkflow
  ↓
ThemeRadarService
  ↓
KnowledgeAdapter.get_concept("商业航天")
KnowledgeAdapter.find_entities_by_concept("商业航天")
KnowledgeAdapter.get_concept_evidence("商业航天")
MarketAdapter.get_double_red_themes(date)
```

## 11. 第一阶段实现顺序

建议顺序：

1. `intelligence/paths.py`
2. `intelligence/adapters/market.py`
3. `MarketAdapter.health()`
4. `MarketAdapter.get_market_daily()`
5. `MarketAdapter.get_capacity_sectors()`
6. `MarketAdapter.get_double_red_themes()`
7. `intelligence/adapters/knowledge.py`
8. `KnowledgeAdapter.load_relation()`
9. `KnowledgeAdapter.get_entity_exposures()`
10. `KnowledgeAdapter.get_evidence()`

最小可交付版本：

```text
MarketAdapter.health()
MarketAdapter.get_market_daily(date)
KnowledgeAdapter.load_relation("entity_exposures")
KnowledgeAdapter.get_entity_exposures(entity)
```

## 12. 验收标准

文档验收：

- 明确只读边界。
- 明确两个 adapter 职责。
- 明确核心接口。
- 明确返回值规范。
- 明确错误处理。
- 明确 token 约束。

未来代码验收：

- Adapter 方法不 print，只 return。
- DuckDB 连接全部 read_only。
- KnowledgeAdapter 不扫描大目录正文。
- 查询缺失时返回结构化 warning/error。
- 可以被 CLI 和 service 复用。

## 13. 后续文档衔接

下一步建议写：

```text
docs/theme-radar-json-schema.md
```

目的：

- 定义 Theme Radar 标准 JSON 输出。
- 让 `radar.py` 从 Markdown 报告进一步产品化为结构化数据。
- 为网站题材页和 AI Copilot 提供稳定输入。

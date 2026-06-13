# 盘面触发题材雷达日终版设计

## 1. 背景

当前金融复盘系统已经能够基于 DuckDB 生成较完整的日终市场复盘，并按策略一、策略二、策略三、二板晋级等规则输出结构化策略结论。知识库侧已经具备 Theme Radar 和 Serenity Alpha 两类能力：

- Theme Radar：从题材或新名词出发，拆解定义、产业链、相关概念、核心公司、证据和发酵阶段。
- Serenity Alpha：在已有题材或公司线索基础上，结合本地知识库、公司暴露、对标关系和价格反馈，分析个股弹性、预期差、补涨顺序和交易含义。

现有使用方式主要是用户手动输入题材或公司，例如 `MLCC`、`光刻胶`、`三环集团`，再触发 Theme Radar 或 Serenity Alpha。新的目标是让盘面本身成为输入：由每日市场表现自动触发题材分析，再用知识库解释产业链和核心个股。

## 2. 目标

V1 目标是实现一个日终版“盘面触发题材雷达”闭环：

```text
trade_date
  -> 从 DuckDB 自动识别盘面触发题材
  -> 生成 triggered-themes.json
  -> 对 Top 3 题材做深度知识库解释
  -> 对 3-7 个候选题材做简要观察
  -> 输出 market-triggered-theme-brief.md
```

该系统要回答：

1. 今天盘面到底指向哪些题材？
2. 这些题材为什么被触发？
3. 这些题材是什么，产业链上下游如何拆？
4. 各细分环节的核心公司是谁？
5. 哪些公司是产业锚、确定性核心、弹性预期差、补涨观察或高位风险？
6. 次日应该验证什么？

## 3. 非目标

V1 不做以下事情：

- 不做盘中实时触发；先日终稳定，再迁移盘中。
- 不直接修改 `wiki/entities/*.md`，避免把短期市场信号写成公司基本面事实。
- 不把每日复盘主 Markdown 强行扩写成超长报告；先输出独立简报。
- 不做全自动知识库大规模回填；只生成待补库缺口提示。
- 不做交易指令或买卖建议；只输出题材理解、核心公司分层和次日验证点。

## 4. 设计原则

### 4.1 盘面是触发器

市场表现用于告诉系统“今天该分析什么”。例如：

```text
电子是容量前三行业；MLCC 和光刻胶双红；风华高科、利和兴、三环集团、南大光电、容大感光新高；CCL 出现连板/涨停集群。
```

这些信号触发分析，但不是最终答案。

### 4.2 知识库是解释器

知识库负责解释：

- 题材定义。
- 上中下游关系。
- 细分环节。
- 公司在产业链中的角色。
- 本地已有证据和暴露强度。

### 4.3 Serenity Alpha 是排序器

Serenity Alpha 不负责发现题材，而是在题材已经被盘面触发后，排序和解释：

- 产业锚。
- 确定性核心。
- 弹性预期差。
- 补涨观察。
- 高位风险。

### 4.4 本地优先，外部补充

题材解释优先使用本地知识库。如果本地资料不足，允许联网补充定义、上下游和通用产业链信息，但输出中必须区分：

- 本地知识库证据。
- 外部补充信息。
- 待回填知识库缺口。

## 5. 输入数据

### 5.0 数据完整性闸门

任何日终题材雷达生成前，必须先通过现有完整性检查：

```bash
python3 scripts/check_daily_review_data.py YYYY-MM-DD
```

如果闸门失败，V1 不输出市场结论和题材分析，只输出失败原因与缺失数据项。不能在 `fact_market_daily`、题材日线、涨停题材热度、新高股或连板晋级等关键表缺失时继续生成看似完整的报告。

### 5.1 金融复盘 DuckDB

V1 主要读取以下表：

- `fact_market_daily`：市场阶段、成交额、涨家数、涨停跌停、容量前三行业等。
- `fact_sector_daily`：题材涨幅、边际量、成交额、申万一级映射等。
- `fact_sector_stock_daily`：题材成分股和个股当日表现。
- `fact_stock_high_daily`：新高股票及新高级别。
- `fact_theme_limit_heat_daily`：涨停题材热度。
- `fact_theme_limit_stock_daily`：涨停股到题材的映射。
- `fact_limit_advance_daily`：二板及以上连板晋级数据。
- `fact_sector_period_rank_daily`：多周期题材排行；若缺失，可从 `fact_sector_daily` 复算。

### 5.2 知识库关系层

V1 读取知识库中的：

- `wiki/relations/concept_graph.json`
- `wiki/relations/entity_exposures.json`
- `wiki/relations/evidence_index.json`
- `wiki/relations/report_contexts.json`
- `wiki/relations/benchmark_maps.json`
- `wiki/relations/theme_signals.json`，如果存在则作为历史题材信号参考。

### 5.3 外部补充

仅当本地知识库无法解释新题材或产业链缺口明显时，允许联网补充：

- 题材定义。
- 产业链上下游。
- 行业通用核心公司。
- 关键术语别名。

外部补充必须在报告中标注，不能伪装成本地知识库证据。

## 6. 输出文件

V1 先只在金融项目输出，不直接写入知识库。

```text
market_feature_store/exports/YYYY-MM-DD-triggered-themes.json
market_feature_store/exports/YYYY-MM-DD-market-triggered-theme-brief.md
```

未来稳定后再同步：

```text
/Users/lbq/Desktop/c c/知识库/wiki/sources/YYYY-MM-DD-market-triggered-theme-brief.md
/Users/lbq/Desktop/c c/知识库/wiki/relations/theme_signals.json
```

## 7. 题材触发规则

### 7.1 双红题材触发

满足：

```text
pct_chg > 0
AND diff_ratio > 10
AND amount > 500 亿
```

这是最高优先级信号，代表价格、边际量和容量同时确认。

### 7.2 容量行业内新高集群触发

满足：

```text
题材所属申万一级在当日成交占比前三
AND 同一题材下出现多个新高股
```

用于识别主线行业内部的赚钱效应聚集。

### 7.3 涨停 / 连板集群触发

满足任一条件：

```text
同一题材出现多个涨停
OR 同一题材出现 2 板及以上连板股
```

用于识别新题材启动或情绪高度题材，例如 CCL、物理 AI。

### 7.4 多周期强题材触发

满足：

```text
题材在 daily / day3 / day5 / day10 多周期榜中反复出现
OR 在多个周期排名靠前
```

用于识别趋势延续题材，而不是单日脉冲。

### 7.5 简要观察触发

如果题材只满足单项信号，例如单红、新高个股、涨停映射或多周期出现但缺少容量确认，则进入简要观察池，不默认进入 Top 3 深度分析。

## 8. 题材分层与排序

每天输出：

```text
深度分析 Top 3
+ 简要观察 3-7 个候选题材
```

排序优先级：

1. 容量主线 + 双红 + 新高集群。
2. 新题材 + 涨停/连板集群。
3. 容量主线内多周期强题材。
4. 情绪高度题材。
5. 单红 / 新高 / 涨停映射但不共振。

Top 3 做完整分析，简要观察题材只输出入选原因、对应股票、升级条件和风险点。

## 9. JSON Schema

`YYYY-MM-DD-triggered-themes.json` 的核心结构：

```json
{
  "trade_date": "2026-06-09",
  "market_context": {
    "market_stage": "下跌阶段第2天",
    "market_pulse": "冰点后反弹",
    "top_capacity_industries": ["电子", "通信", "机械设备"],
    "advancers": 3322,
    "limit_up": 130,
    "limit_down": 9
  },
  "deep_themes": [
    {
      "market_theme": "MLCC",
      "canonical_concept": "MLCC",
      "sw_l1": "电子",
      "priority_score": 95,
      "trigger_types": ["double_red", "new_high_cluster", "capacity_industry"],
      "market_evidence": {
        "pct_chg": 5.47,
        "diff_ratio": 29.66,
        "amount": 883,
        "new_high_stocks": ["风华高科", "利和兴", "三环集团"],
        "limit_up_stocks": [],
        "advance_stocks": []
      },
      "knowledge_status": {
        "local_concept_found": true,
        "local_exposures_found": true,
        "external_supplement_needed": false,
        "backfill_gaps": []
      }
    }
  ],
  "watch_themes": []
}
```

字段要求：

- `market_theme` 保留盘面原始题材名。
- `canonical_concept` 是映射后的知识库标准概念名。
- `trigger_types` 必须可追溯到具体市场数据。
- `knowledge_status` 明确本地知识库覆盖程度和外部补充需求。

## 10. Markdown 简报结构

`YYYY-MM-DD-market-triggered-theme-brief.md` 采用固定结构：

```markdown
# YYYY-MM-DD 盘面触发题材雷达

## 一、今日市场脉络

## 二、触发题材总览

## 三、深度题材 1：题材名

### 1. 盘面触发
### 2. 这是什么
### 3. 产业链拆解
### 4. 关键细分环节
### 5. 核心个股分层
### 6. 今日市场验证
### 7. Serenity Alpha 预期差判断
### 8. 次日验证点
### 9. 知识库覆盖与待补缺口

## 四、深度题材 2：题材名

## 五、深度题材 3：题材名

## 六、简要观察题材

## 七、今日总结
```

## 11. 每个深度题材的分析要求

### 11.1 盘面触发

必须写清楚触发类型和市场证据，例如：

```text
MLCC 今日同时满足双红、电子容量主线、新高集群三类触发。板块涨幅 5.47%，边际量 29.66，成交额 883 亿。风华高科、利和兴、三环集团新高，说明资金在 MLCC / 被动元件链条中形成集群确认。
```

### 11.2 题材定义

先查本地知识库；不足时允许外部补充，并标注来源层级。

### 11.3 产业链拆解

至少分为：

- 上游。
- 中游。
- 下游。
- 关键材料 / 工艺 / 零部件。
- 应用场景。

### 11.4 核心个股分层

分层输出，不简单罗列：

- 产业锚。
- 确定性核心。
- 弹性预期差。
- 补涨观察。
- 高位风险。

### 11.5 今日市场验证

结合当天新高、涨停、连板、成交、题材双红和容量行业，说明盘面如何验证或否定题材逻辑。

### 11.6 次日验证点

必须是可观察条件，例如：

- 题材是否继续保持成交额和边际量。
- 新高核心是否承接。
- 连板股是否晋级或卡位失败。
- 是否从单一细分扩散到上游 / 下游 / 同链题材。
- 如果放量下跌，是否进入高潮分歧而非继续进攻。

## 12. 知识库映射策略

V1 需要一个轻量 `market_theme_alias -> canonical_concept` 解析层。

例子：

```json
{
  "market_name": "CCL",
  "canonical_concept": "覆铜板",
  "aliases": ["CCL", "覆铜板", "铜箔基板", "PCB基材"],
  "parent_concepts": ["PCB", "电子材料", "AI硬件"]
}
```

解析顺序：

1. 精确匹配知识库概念名。
2. 匹配 alias / 别名。
3. 匹配 concept_graph 相关概念。
4. 如果仍无结果，保留盘面名作为 `canonical_concept`，并标记 `external_supplement_needed=true`。

## 13. 知识库写入边界

V1 不写：

- `wiki/entities/*.md`
- `wiki/concepts/*.md`
- `wiki/relations/entity_exposures.json`
- `wiki/relations/evidence_index.json`

V1 可以生成但不自动应用：

```text
concept_backfill_candidates
entity_exposure_backfill_candidates
missing_alias_candidates
```

这些缺口可以在后续人工确认后进入知识库回填流程。

## 14. 未来知识库同步

当 V1 输出稳定后，新增同步阶段：

```text
market_feature_store/exports/YYYY-MM-DD-market-triggered-theme-brief.md
  -> 知识库/wiki/sources/YYYY-MM-DD-market-triggered-theme-brief.md

triggered-themes.json
  -> 知识库/wiki/relations/theme_signals.json
```

同步规则：

- `theme_signals.json` 以 `date + canonical_concept + market_theme` 为 upsert key。
- 每条信号保留 `source_note` 指向对应 source note。
- 短期市场信号只进入 signal 层，不进入实体正文。

## 15. 日终到盘中的迁移路径

V1 日终稳定后，盘中版复用相同架构，只替换数据源：

```text
日终 DuckDB facts
  -> 盘中实时/半实时 fupanhui 数据
```

盘中版需要额外处理：

- 数据不完整。
- 盘中信号反复变化。
- 触发频率控制。
- 噪音过滤。
- 盘中报告和日终确认报告的区别。

因此盘中版不在 V1 范围内。

## 16. 验证标准

V1 完成后，应能以 `2026-06-09` 为样例生成结果：

- 深度题材应包含 MLCC、光刻胶，以及 CCL 或当日更高优先级的新题材。
- MLCC 应展示双红、新高集群、电子容量主线等触发证据。
- 光刻胶应展示南大光电、容大感光等市场验证线索。
- CCL 应能解释覆铜板定义、PCB 上游材料属性、金安国纪 / 华正新材的盘面触发意义。
- 报告应区分本地知识库证据、外部补充信息和待补库缺口。
- 报告不应把短期新高或涨停事实写入实体页正文。

## 17. 实施阶段建议

### Phase 1：Detector 与 JSON 输出

实现 `build_market_triggered_theme_brief.py` 的触发题材识别部分，先生成 `triggered-themes.json`。

### Phase 2：知识库 resolver

实现本地概念、公司暴露、证据和别名匹配，生成每个题材的知识库覆盖状态。

### Phase 3：Markdown 简报

生成完整 `market-triggered-theme-brief.md`，先用本地知识库摘要和规则模板完成可读输出。

### Phase 4：外部补充

在本地知识库不足时，通过联网补充定义和产业链，并在报告中标注外部补充。

### Phase 5：知识库同步

待日终输出稳定后，再写入知识库 source note 和 `theme_signals.json`。

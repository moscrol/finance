# Entity Baseline Queue Design

## 背景

Theme Radar 需要稳定的实体底座：公司主营业务、产品/能力、行业分类、产业链暴露、证据层级和待验证问题。当前 `wiki/entities/` 中大量实体来自研报或边际变化，baseline 覆盖不均，导致题材映射时公司分层质量不稳定。

目标是按 `wiki/entities/*.md` 顺序补齐 A 股实体 baseline，但必须避免一次性全量写入造成污染。因此本设计采用“顺序扫描 + 队列 + 分批 dry-run + 审核后 apply”的流水线。

## 目标

1. 按 `wiki/entities/` 文件顺序扫描 A 股实体，形成可断点 baseline 队列。
2. 每批默认处理 5 家，先生成 raw 和 payload，不直接写库。
3. 以 `a-stock-data + mootdx F10` 为主源，AkShare 作为 fallback / cross-check，CNINFO 作为公告索引和后续 L3 验证入口。
4. 输出符合 `entity_baseline_writer.py` 的 updates JSON，复用现有写入器维护 entity markdown、`entity_exposures.json` 和 `evidence_index.json`。
5. 严格区分 L2 baseline 与 L3 官方事实，不把 F10/AkShare 资料直接升级为官方 hard fact。

## 非目标

1. 第一阶段不做全库自动 apply。
2. 不批量下载或解析整本年报 PDF。
3. 不写 `## 边际变化`。
4. 不用市场涨跌、资金流、龙虎榜反推公司产业链事实。
5. 不覆盖已有 `hard_delta`、`curated_research` 或人工高质量 exposure。

## 数据源优先级

| 字段类型 | 主源 | 辅源 | 证据层级 |
|---|---|---|---|
| 公司名/代码 | entity frontmatter / F10 | AkShare | L2 |
| 行业分类 | a-stock-data 东财/F10 | AkShare | L2 |
| 主营业务 | mootdx F10 公司概况 | AkShare 主营介绍 | L2 |
| 经营范围 | mootdx F10 公司概况 | AkShare / CNINFO profile | L2 |
| 主营产品/能力 | F10 主营业务/公司简介 | AkShare 主营产品 | L2 |
| 主营构成 | AkShare 主营构成 | 年报关键页 | L2/L3 |
| 公告索引 | a-stock-data CNINFO / cninfo-mcp | 直接 CNINFO HTTP | index only |
| 官方事实 | CNINFO 公告/年报关键页 | 交易所互动/公告 | L3 |

## 组件设计

### 1. `scan_entity_baseline_queue.py`

职责：只扫描文件名、frontmatter 和少量开头文本，避免通读实体正文。

输入：

- `--wiki-dir /Users/lbq/Desktop/c c/知识库/wiki`
- `--out wiki/raw/baseline-queue/entity-baseline-queue.jsonl`

筛选规则：

- 文件位于 `wiki/entities/*.md`。
- 存在 A 股 ticker：`00/30/60/68/83/87/43` 开头的 6 位代码。
- 跳过已有可用 baseline 的实体，除非传入 `--include-existing`。
- 跳过非上市公司、海外公司、无 ticker 实体。

队列行：

```json
{"company":"航天电子","code":"600879","entity_file":"wiki/entities/航天电子.md","status":"pending","reason":"missing_baseline","order":123}
```

### 2. `fetch_a_stock_baseline.py`

职责：对单家公司抓取 raw baseline。只写 raw JSON，不生成最终 exposure 结论。

输出目录：

```text
wiki/raw/a-stock-baseline/{公司}.json
```

raw 结构包含：

- `source_type: a-stock`
- `company`
- `code`
- `fetched_at`
- `a_stock_data.stock_info`
- `a_stock_data.f10.company_profile`
- `a_stock_data.f10.industry_analysis`
- `a_stock_data.f10.latest_notice`
- `sina_income_periods`
- `cninfo_announcements`
- `akshare_fallback`，仅在主源缺字段或启用 cross-check 时填充
- `errors`，保存单接口失败，不让单点失败中断整批

### 3. `build_a_stock_baseline_update.py`

职责：从 raw JSON 生成 writer 可消费的 `updates[]`。

输出：

```text
wiki/raw/a-stock-baseline/baseline-updates-YYYY-MM-DD-batchNNN.json
```

字段规则：

- `raw_source` 必须符合 `raw/a-stock-baseline/{公司}.json`。
- `main_business` 必须来自 F10/AkShare 原文片段。
- `products` 从主营业务、公司简介、经营范围中抽取，低置信时宁可少写。
- `concepts` 优先来自已有 entity tags 和 concept graph 命中；不现场创造新概念。
- `exposures` 必须有 `concept`、`role`、`chain_layer`、`strength`、`confidence`、`evidence`。
- F10/AkShare 证据默认 `evidence_layer=L2`、`source_quality=market_data_vendor_f10` 或 `akshare_public_data`。
- 无法形成明确 exposure 的公司进入 review queue，不写入。

### 4. `run_entity_baseline_queue.py`

职责：按队列批处理。

默认行为：

```text
--batch-size 5
--mode dry-run
```

流程：

1. 读取 queue 中前 N 个 `pending`。
2. 对每家公司调用 `fetch_a_stock_baseline.py`。
3. 调用 `build_a_stock_baseline_update.py` 生成 batch payload。
4. 运行 payload 校验。
5. 写 batch summary。
6. dry-run 模式不调用 writer。

apply 模式：

- 需要显式 `--apply`。
- 调用现有 `entity_baseline_writer.py`。
- 写入成功后更新 queue 状态为 `applied`。
- 失败写 `failed` 和失败原因。

## 输出文件

每批生成：

```text
wiki/raw/baseline-queue/entity-baseline-queue.jsonl
wiki/raw/a-stock-baseline/{公司}.json
wiki/raw/a-stock-baseline/baseline-updates-YYYY-MM-DD-batchNNN.json
wiki/raw/baseline-queue/batchNNN-summary.md
```

## 校验与安全规则

1. `raw_source` 文件必须存在，且原文中能找到 `main_business` 或关键产品字段。
2. 禁止写入占位短语，例如“核心产品/服务”“行业主流公司”。
3. 无 `main_business`、无 `products`、无 `exposures` 的 update 必须跳过。
4. 默认 `confidence=medium`，只有官方 CNINFO 关键页验证后才能升高。
5. 不允许 baseline 写入降级已有 `curated_research`、`delta`、`hard_delta`。
6. 第一阶段只 dry-run；抽查通过后再小批量 apply。
7. 每批处理数量默认 5，批量抓取不并发。
8. 不提交 `.env*`、PDF、数据库、压缩包、缓存或大文件。

## 首批验收标准

第一批 dry-run 成功时必须满足：

- 扫描出至少 5 个 A 股 pending entity。
- 对 5 家生成 raw JSON。
- 至少 3 家生成合格 update payload。
- 不写入 `entities/` 和 `relations/`。
- batch summary 清楚列出：成功、跳过、失败、字段缺口、建议是否 apply。

第一批 apply 只有在用户确认后执行。

## 后续扩展

1. 接入 CNINFO 关键页抽取，补 L3 官方事实。
2. 接入 Theme Radar `theme_signals.json`，补 L4 市场信号。
3. 增加快照机制，记录 baseline 覆盖率和每批处理进度。
4. 对核心题材公司增加人工 review queue，避免错误升为 core/high。

---
name: pdf-ingest
description: PDF 研报入库到 Obsidian 知识库并对齐 Theme Radar 底层数据。Use when the user says PDF ingest、pdf入库、研报PDF入库、处理研报PDF、OCR研报、评级日报/脱水研报/强势脱水/风口研报入库，或要求把 PDF/source note/concept/entity/entity_exposures/evidence_index/report_contexts 与题材雷达底层对齐。
---

# PDF Ingest Skill

把 `/Users/lbq/Desktop/研报/` 或用户指定 PDF 入库到 `/Users/lbq/Desktop/c c/知识库`，并同步 Theme Radar 底层关系库。

## 权威入口

- 完整 workflow：`/Users/lbq/Desktop/c c/知识库/.windsurf/workflows/pdf-ingest.md`
- 实体写入 skill：`/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/SKILL.md`
- 实体写入脚本：`/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/entity_delta_writer.py`
- 图片 PDF 切图脚本：`/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/extract_pdf_images.py`
- 质检脚本：`/Users/lbq/Desktop/c c/金融/skills/lib/pdf_ingest_lint.py`

执行复杂批量任务前先读完整 workflow；单篇实体更新可直接按本 skill + `entity-delta-ingest` 执行。

## 核心原则

- 不要把 PDF ingest 当成普通摘要任务；目标是同时维护 source note、concept/entity markdown、`concept_graph.json`、`entity_exposures.json`、`evidence_index.json`、必要时 `report_contexts.json`。
- 遵守低 token 原则：先用文件名、索引、`rg --files`、精确搜索和脚本 summary；不要批量通读 `wiki/entities/`、`wiki/concepts/`、`wiki/sources/` 正文。
- 券商/脱水/评级日报/风口研报默认是 `source_quality=broker_research_high`，不是公告或公司原始证据。
- 高信度研究来源 ≠ 公司硬事实来源。没有 L3 原始证据时，不得写 `hard_fact`，不得写入 `## 边际变化`。

## 标准流程

1. 盘点 PDF
   - 列出候选 PDF。
   - 跳过文件名包含 `狙击龙虎榜` 的 PDF。
   - 对照 `wiki/sources/*.md` 判断是否已入库。

2. 抽取文本
   - 优先用文本层抽取。
   - 若文本为空，用 OCR 或图片切块脚本：
     ```bash
     python3 "/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/extract_pdf_images.py" "文件路径.pdf" --out-dir /tmp/entity_delta_images
     ```
   - 抽取全文保存到 `raw/{source_name}.md`。

3. 先生成 ingest-plan，不要直接写库
   - 至少包含：`source_name`、`source_date`、`source_file`、`raw_file`、`primary_topics`、`new_concepts`、`concept_delta_candidates`、`entity_update_candidates`、`entity_create_candidates`、`graph_only_exposures`、`watchlist`。
   - 先区分 `must_write`、`light_note`、`watchlist`、`graph_only`。

4. 分流写入
   - 新概念：走 `concept-ingest`。
   - 已有概念增量：走 `concept-delta-ingest`。
   - 公司边际/图谱暴露：走 `entity-delta-ingest` 和 `entity_delta_writer.py`。
   - 观察项：只写 source note `## 观察列表`，不进 relations。

5. 统一质检
   ```bash
   python3 "/Users/lbq/Desktop/c c/金融/skills/lib/pdf_ingest_lint.py" "source_name"
   ```
   要求 0 errors；warnings 也应尽量清零。

## Theme Radar 字段口径

### 来源与事实硬度

| 场景 | source_quality | fact_hardness | evidence_layer | update_type | 写入位置 |
|------|----------------|---------------|----------------|-------------|----------|
| 券商普通研究判断 | broker_research_high | research_claim | L1 | curated_research | `## 高信度研究线索` |
| 券商中的公司级事实关键词 | broker_research_high | review_candidate | L1_L3_candidate | curated_research | `## 高信度研究线索` |
| 纯产业链名单/受益映射 | broker_research_high | research_claim | L1 | graph_only | 仅 relations/source note |
| 公告/年报/官网原始证据 | official_disclosure | hard_fact | L3 | delta | `## 边际变化` |
| 公司原始披露 | company_primary | hard_fact | L3 | delta | `## 边际变化` |
| 观察项/证据不足 | - | - | - | - | `## 观察列表` |

### review_candidate 关键词

量产、批量供货、客户认证、客户导入、订单、合同、中标、投产、扩产、产能、出货、收入、利润、市占率、良率、产品认证。

这些来自券商 PDF 时只能标 `review_candidate / L1_L3_candidate / review_required=true`，不能直接标 `hard_fact`。

### graph_only 硬规则

`graph_only` 必须：

- `update_type=graph_only`
- `strength=peripheral`
- `fact_hardness=research_claim`、`market_narrative`、`unknown` 或 `legacy_rebuilt`
- `evidence_layer=L1` 或 `graph_only`
- `review_required=false`
- 不写 entity markdown，不写 `## 边际变化`

`graph_only` 禁止：

- `strength=core/related`
- `fact_hardness=review_candidate/hard_fact`
- `evidence_layer=L1_L3_candidate/L3`
- `update_type=delta/curated_research`

### role 与 chain_layer

- `chain_layer` 必须用枚举：`upstream_materials`、`upstream_components`、`upstream_equipment`、`midstream_manufacturing`、`midstream_components`、`midstream_service`、`midstream_equipment`、`downstream_application`、`downstream_operation`、`ecosystem`。
- `role` 必须是具体业务角色短语，不能写 `受益标的`、`相关公司`、`产业链供应商`，也不能等于 `chain_layer`。

## 写入 payload 要求

同一篇 PDF 的所有实体更新合并成一个 payload，一次调用 writer。不要按公司逐个调用。

每条 entity update / graph_only exposure 尽量包含：

```json
{
  "company": "公司名",
  "code": "000001",
  "concepts": ["概念名"],
  "role": "具体业务角色",
  "tier": "core|related|peripheral",
  "chain_layer": "midstream_manufacturing",
  "evidence_layer": "L1|L1_L3_candidate|L3",
  "update_type": "curated_research|graph_only|delta",
  "fact_hardness": "research_claim|review_candidate|hard_fact",
  "source_quality": "broker_research_high|official_disclosure|company_primary",
  "confidence": "high|medium|low",
  "review_required": false,
  "graph_only": false,
  "evidence": "短原文依据",
  "bullets": ["1-4条，说明发生了什么、为何重要"]
}
```

Writer 示例：

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/entity_delta_writer.py" < /tmp/ingest_payload.json
```

## 验收标准

- `wiki/sources/{source_name}.md` 存在，且无重复 section。
- 新建/更新的 concept/entity 能 grep 到 source 名称。
- broker 源不把二手事实写进 `## 边际变化`。
- `entity_exposures.json` 中每个 exposure 有合法 `role`、`chain_layer`、`source_quality`、`fact_hardness`、`evidence_layer`、`update_type`。
- `evidence_index.json` 覆盖非 graph_only exposure。
- `pdf_ingest_lint.py source_name` 通过。
- 回归样本保持通过：`0412评级日报`、`0412强势股脱水`、`0412脱水研报`、`0331强势脱水`、`0331脱水研报`、`0331评级日报`。

## 写入后 5 项自检（必须完成后才能继续下一个 PDF）

每篇 PDF 写入后必须完成以下 5 项自检。只跑 lint 不等于完成自检；任何一项失败，都必须先修复当前 PDF，禁止继续下一个。

### 1. lint 自检

运行：

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/lib/pdf_ingest_lint.py" "source_name"
```

验收标准：

- 输出 `ALL CHECKS PASSED`。
- `0 errors`。
- warnings 尽量清零；若 warning 涉及字段缺失、分类不一致、证据层口径，必须先修。

### 2. JSON 自检

运行：

```bash
python3 -c "import json, pathlib; wiki=pathlib.Path('/Users/lbq/Desktop/c c/知识库/wiki'); [json.loads((wiki/'relations'/f).read_text()) for f in ['entity_exposures.json','evidence_index.json','concept_graph.json']]; print('JSON OK')"
```

验收标准：

- 输出 `JSON OK`。
- 如本轮改动涉及 `report_contexts.json`，也必须额外 parse。

### 3. source / raw / log / index 自检

必须确认：

- `raw/{source_name}.md` 存在，且不是空文件。
- `wiki/sources/{source_name}.md` 存在，且 frontmatter 至少包含 `created`、`updated`、`revision`、`source_quality`、`log`。
- source note 明确写出 raw 引用。
- `wiki/log.md` 有对应全局编号。
- `wiki/index.md` revision/log 已更新，或明确说明本轮按项目约定无需更新。

### 4. source note 分类与 relations 对齐自检

必须逐项核对 source note 的分类和底层关系是否一致：

- `## 已更新实体`：必须能在对应 entity markdown、`entity_exposures.json`、必要时 `evidence_index.json` 中找到一致证据。
- `## 仅更新图谱`：必须能在 `entity_exposures.json` 找到对应 source；graph_only 可不强制写 `evidence_index`。
- `## 观察列表`：不得进入 `entity_exposures.json`，不得创建 entity，除非另有明确硬证据触发。
- source note 写了更新但 relations 没有 source，属于阻塞问题。
- relations 有 source 但 source note 未分类说明，也属于阻塞问题。

### 5. 污染与命名自检

必须确认：

- 不新增错误 entity。
- 不把 OCR 错名当成新公司；公司名和 ticker 必须反查现有 `wiki/entities/`。
- 已有 entity 不能误报为缺页。
- broker 源不直接写 `hard_fact`。
- broker 源不写入 `## 边际变化`。
- 观察列表公司不进入 relations。
- 纯名单/受益映射只能走 `graph_only + peripheral` 或 `observation_only`。
- 若同一 source 同一 entity/concept 需要同时表达 graph_only 和 curated_research evidence，必须使用 `evidence_purpose` 区分，例如 `graph_exposure` 与 `entity_research_note`，避免被 reconcile 覆盖。

## 每次必须遵守的约定

- 每处理完一篇 PDF，必须先完成 5 项自检，再汇报是否可以继续下一个。
- 质量分析、代码复核、流程审计或类似分析后，必须附一段可直接复制给另一个 IDE/Agent 的“优化提示词”，包含目标、问题、禁止动作、执行步骤、校验方式和验收标准。
- 对 `raw/*-full.md` 完整研报，先用索引/search/`report_contexts.json` 定位相关文件，再精读最相关 full.md；不要批量通读 raw 目录。
- `raw/*-full.md` 是高信度研究证据，但不是官方硬证据；默认只能作为 `curated_research / review_candidate / L1_L3_candidate` 或 `research_claim`，不得自动升级为 `official_disclosure / hard_fact / baseline`。
- `Theme Radar` 主流程主要消费 `entity_exposures.json`、`evidence_index.json`、`concept_graph.json`、`report_contexts.json`；不要假设它会直接解析 `wiki/entities/*.md` 的 `## 高信度研究线索`。
- graph_only 无 evidence item 时，在 lint 展示中应视为 exempt/optional；非 graph_only 缺 evidence item 才是必须修复的问题。
- 不能为了让 lint 通过而把弱研判升级成 `curated_research`、`delta`、`hard_fact`、`core` 或 `related`。

## 单篇 PDF 最终汇报格式

每篇 PDF 完成后，必须按以下格式汇报：

1. `lint` 是否 `ALL CHECKS PASSED`。
2. JSON 是否 `JSON OK`。
3. raw / source note / log / index 是否齐全。
4. source note 分类与 relations 是否一致。
5. 是否确认无 entity 污染、无 OCR 错名、无错误 `## 边际变化`。
6. 本轮新增/更新了哪些 source、concept、entity、exposure、evidence。
7. 哪些公司仅进入观察列表，且确认未入 relations。
8. 是否可以继续下一个 PDF。

## 遇到不确定时

- 证据不足：放 `watchlist`，不要写 relations。
- 只有受益名单：`graph_only + peripheral`。
- PDF 中有公司级事实但来自券商：`curated_research + review_candidate`。
- 只有官方/公司原始证据支持时，才写 `delta + hard_fact + L3`。

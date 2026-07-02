# FinHot Obsidian Evidence Staging 设计

## 目标

把 FinHot Evidence Hunter 的高价值候选证据导出到知识库仓库的 Obsidian 暂存区，形成“机器发现、人工确认、正式沉淀”的证据闭环。

第一版保持保守：FinHot SQLite 仍是原始库；金融工程仓负责脚本和报告；知识库仓只承载可读的 staging Markdown 和人工确认后的 source note。

## 非目标

- 不把 FinHot SQLite 全量导入 DuckDB。
- 不把 FinHot SQLite、RSSHub cookie、采集日志或运行状态提交到 Git。
- 不自动修改知识库正式 `sources/`、`entities/`、`concepts/`。
- 不自动写入 `evidence_index.json` 或实体 exposure。
- 不把 `rejected` 和低置信候选写入正式知识层。

## 仓库边界

### 金融工程仓

路径：`/Users/lbq/Desktop/c c/金融`

职责：

- 保留 Evidence Hunter 脚本、测试、设计文档。
- 读取 FinHot SQLite。
- 生成 JSON/Markdown 报告。
- 生成 Obsidian staging Markdown。
- 生成人工确认 manifest 模板。

### 知识库仓

路径：`/Users/lbq/Desktop/c c/知识库`

默认 wiki 根目录由 `intelligence.paths.default_paths()` 解析为：

- 默认：`/Users/lbq/Desktop/c c/知识库/wiki`
- 可通过 `KB_VAULT`、`KNOWLEDGE_WIKI`、`CONCEPT_VAULT`、`ENTITY_VAULT` 覆盖。

职责：

- 存放人工可读知识资产。
- `wiki/raw/finhot-evidence-staging/` 存放待审 FinHot staging note。
- `wiki/sources/` 存放人工确认后的正式 source note。

## 目录约定

第一版新增暂存目录：

```text
/Users/lbq/Desktop/c c/知识库/wiki/raw/finhot-evidence-staging/
  YYYY-MM-DD-finhot-evidence-staging.md
  YYYY-MM-DD-finhot-evidence-approval-template.json
```

保留 `raw/` 语义：这里是“待审原始候选整理”，不是正式 source 层。

## 数据流

```text
daily agent report
  ↓
Evidence Hunter task adapter
  ↓
FinHot SQLite read-only search
  ↓
evidence classification
  ↓
JSON report + Markdown report
  ↓
Obsidian staging Markdown + approval manifest template
  ↓
人工审核
  ↓
正式 source note / entity note 后续手动或半自动更新
```

## Staging note 内容

每个交易日生成一个 staging note。文件名使用任务日期：

```text
YYYY-MM-DD-finhot-evidence-staging.md
```

Frontmatter：

```yaml
---
title: FinHot Evidence Staging YYYY-MM-DD
type: raw_staging
source: finhot
evidence_workflow: evidence_hunter
status: candidate
review_required: true
date: YYYY-MM-DD
generated_at: ISO-8601
tags: [finhot, evidence-hunter, staging]
---
```

正文结构：

```text
# FinHot Evidence Staging YYYY-MM-DD

## 使用口径

## L3 当前官方催化候选

## L3 历史官方事实

## L2 官方基线

## L3 待追官方原文候选

## 被拒绝或低置信线索摘要

## 人工确认清单
```

正文只输出摘要、证据原文片段、URL、来源、时间、Evidence Hunter 分层结果、匹配任务。低置信线索只汇总数量和拒绝原因，不长篇展开。

## Approval manifest 模板

每个 staging note 同时生成一个 JSON 模板：

```text
YYYY-MM-DD-finhot-evidence-approval-template.json
```

结构：

```json
{
  "date": "YYYY-MM-DD",
  "source_report": "path/to/evidence-hunter-report.json",
  "staging_note": "wiki/raw/finhot-evidence-staging/YYYY-MM-DD-finhot-evidence-staging.md",
  "approvals": [
    {
      "candidate_id": "sha1-task-item-url-layer",
      "decision": "pending",
      "approved_layer": null,
      "target_source_note": null,
      "related_entities": [],
      "related_concepts": [],
      "reviewer_note": ""
    }
  ]
}
```

`decision` 允许值：

- `pending`
- `approve`
- `reject`
- `needs_official_original`
- `duplicate`

第一版只生成模板，不消费模板写正式知识库。

## 候选筛选规则

进入 staging 的候选：

- `L3_current_official_catalyst`
- `L3_historical_official_fact`
- `L2_official_baseline`
- 高分 `L3_candidate`

不进入 staging 正文详情的候选：

- `rejected`
- 来源不明传闻
- 无 URL 且无可追溯来源名的条目
- 只命中泛词、没有公司/题材/事实动作的条目

这些只在摘要里统计。

## 去重规则

候选 `candidate_id` 使用稳定字段生成：

```text
sha1(task_id + finhot_item_id + url + evidence_layer)
```

同一个 FinHot item 同时命中多个任务时：

- staging note 保留一次证据原文。
- 在“匹配任务”里列出所有任务。
- approval manifest 中每个候选保留唯一 `candidate_id`。

## 错误处理

- 知识库路径不存在：报错，不创建到其他位置。
- `raw/finhot-evidence-staging/` 不存在：自动创建。
- staging 文件已存在且未传 `--overwrite`：报错，避免覆盖人工改动。
- JSON report 缺少候选字段：报错，并提示先重新运行 Evidence Hunter。
- 生成 Markdown 成功但 manifest 失败：返回非零，并保留 Markdown，提示用户重跑或手工删除。

## CLI 形态

在现有 `scripts/build_evidence_hunter_report.py` 上增加可选输出参数，或新增轻量脚本。第一版推荐新增轻量脚本，降低主流程风险：

```bash
python3 scripts/export_finhot_evidence_to_obsidian.py \
  --evidence-report market_feature_store/exports/YYYY-MM-DD-finhot-evidence.json \
  --wiki-root "/Users/lbq/Desktop/c c/知识库/wiki" \
  --date YYYY-MM-DD
```

可选参数：

- `--output-dir`：默认 `raw/finhot-evidence-staging`
- `--overwrite`：允许覆盖同名 staging note 和 manifest
- `--min-layer`：默认包含 L2/L3，不包含 rejected
- `--include-rejected-summary`：默认开启，只输出汇总

## 测试计划

单元测试覆盖：

- 从 Evidence Hunter JSON 读取候选。
- 分层筛选。
- 稳定 `candidate_id` 生成。
- Markdown frontmatter 与正文渲染。
- Approval manifest 模板渲染。
- 已存在文件不覆盖。
- `--overwrite` 覆盖。
- 缺少 wiki root 报错。

测试使用临时目录，不依赖真实知识库仓。

## 后续扩展

第二版可增加：

- 从 approval manifest 生成正式 `sources/` note。
- 自动补实体页“从 raw 回填核验”表格。
- 与 evidence index 联动。
- 与 Obsidian Dataview 字段统一。
- 将人工确认结果回写到单独审计日志。

这些都不进入第一版。

## 设计决策

- 先不入 DuckDB，因为 FinHot 当前价值在“找证据”，不是做结构化因子统计。
- Staging 放知识库仓，因为最终消费端是 Obsidian/RAG/Agent。
- Staging 放 `raw/` 而不是 `sources/`，避免候选被误当正式证据。
- 金融仓保留脚本，知识库仓只保留知识资产，仓库职责清晰。

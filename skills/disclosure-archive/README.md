# Disclosure Archive Skill

题材雷达 (theme-radar) 的 evidence archive — 题材证据采集工作流。
**只存档，不入库。**

## 快速开始

```bash
# 健康检查
python3 skills/disclosure-archive/scripts/check.py

# 归档一条公告证据
python3 skills/disclosure-archive/scripts/archive.py \
  --theme-term "感光膜" \
  --canonical-concept "感光干膜" \
  --company "容大感光" \
  --code "300576" \
  --chain-layer midstream_manufacturing \
  --role "PCB干膜光刻胶供应商" \
  --exposure-strength related \
  --evidence-layer L2 \
  --update-type hard_delta \
  --fact-type product_capability \
  --fact-status realized \
  --confidence high \
  --source-type announcement \
  --title "关于公司感光干膜产品通过客户认证的公告" \
  --publish-date 2026-05-20 \
  --url "https://example.com" \
  --quoted-text "公司感光干膜产品已通过XX客户认证，具备量产能力。" \
  --facts "感光干膜产品通过客户认证" "已具备量产能力"

# 候选发现（未知公司时）
python3 skills/disclosure-archive/scripts/candidate_discovery.py \
  --theme-term "感光膜" \
  --canonical-concept "感光干膜" \
  --candidates '[{"company":"容大感光","code":"300576","chain_layer":"midstream_manufacturing","expected_role":"...","candidate_source":"user_input","candidate_reason":"...","priority":"high","suggested_query_terms":"..."}]'

# 生成 review queue
python3 skills/disclosure-archive/scripts/review_queue.py \
  --theme-term "感光膜"

# 生成批次摘要
python3 skills/disclosure-archive/scripts/batch_summary.py \
  --batch-id batch-20260527-0002

# 自动发现证据缺口（无人指定 concept/company）
python3 skills/disclosure-archive/scripts/auto_gap_backfill.py \
  --mode gap-queue \
  --vault "/Users/lbq/Desktop/c c/知识库/wiki" \
  --disclosures-dir "/Users/lbq/Desktop/c c/知识库/wiki/raw/disclosures"

# 含冷却期已过的 deferred/skipped gaps
python3 skills/disclosure-archive/scripts/auto_gap_backfill.py \
  --mode gap-queue --include-deferred

# 强制选择指定 gap_id
python3 skills/disclosure-archive/scripts/auto_gap_backfill.py \
  --mode gap-queue --force-gap-id gap-20260527-0005

# 归档完成后收尾
python3 skills/disclosure-archive/scripts/auto_gap_backfill.py \
  --mode finalize \
  --batch-id batch-20260527-0003 \
  --vault "/Users/lbq/Desktop/c c/知识库/wiki" \
  --disclosures-dir "/Users/lbq/Desktop/c c/知识库/wiki/raw/disclosures"
```

## 触发词

补公告、补公司硬证据、查年报、查半年报、查招股书、查互动易、查官网产品页、查扩产/投产/订单/中标/合同/客户认证资料、披露归档、disclosure archive、归档公告、候选发现、candidate discovery、review queue

## 核心约束

- 不写 entity/concept/relations
- 每条必须绑定 `theme_term` + `company` + `evidence_layer`
- `role` 禁止泛词（不得写"相关公司、产业链参与者"）
- 规划/意向/框架协议不得标 `hard_delta`，`fact_status=planned/framework`
- 默认 `exposure_strength≠core`，`graph_only` 和 `exposure_only` 必须如实标注
- 重复归档写入 `duplicate_of` 字段
- `source_type=other` 不得用于 `baseline`/`hard_delta`
- 候选发现不是最终核心公司确认，只选 priority=high 的前 3-5 家归档
- 不运行 writer，不自动 apply payload

## 证据审计字段（Pre-Archive Audit）

每条归档必须填写 5 个审计字段，在归档前评估证据质量：

| 字段 | 值 | 说明 |
|------|-----|------|
| `--source-origin` | `primary_official` / `official_repost` / `media_reprint` / `secondary_summary` | 来源原始性 |
| `--concept-match-type` | `direct_alias` / `explicit_synonym` / `upstream_component` / `downstream_application` / `adjacent_substitute` / `inferred_only` / `negative` | 概念匹配类型 |
| `--evidence-polarity` | `positive` / `adjacent` / `negative` / `historical` | 证据极性 |
| `--time-scope` | `current` / `historical` / `planned` / `exited` / `unknown` | 时间跨度 |
| `--fact-traceability` | `all_facts_supported` / `partial_support` / `unsupported_claims` | 事实可追溯性 |

未填写审计字段的记录在归档时通过 `--dry-run` 校验，违反 9 条硬规则之一则拒绝写入。

```bash
# 完整归档示例（含审计字段）
python3 skills/disclosure-archive/scripts/archive.py \
  --theme-term "感光膜" \
  --canonical-concept "感光干膜" \
  --company "容大感光" --code "300576" \
  --chain-layer midstream_manufacturing \
  --role "PCB干膜光刻胶供应商" \
  --exposure-strength related \
  --evidence-layer L2 \
  --update-type hard_delta \
  --fact-type product_capability \
  --fact-status realized \
  --confidence high \
  --source-type announcement \
  --title "..." \
  --publish-date 2026-05-20 \
  --url "https://example.com" \
  --quoted-text "..." \
  --facts "事实1" "事实2" \
  --source-origin primary_official \
  --concept-match-type direct_alias \
  --evidence-polarity positive \
  --time-scope current \
  --fact-traceability all_facts_supported
```

## 批次管理

每条归档可选 `--batch-id` 参数归入批次。归档完成后运行 `batch_summary.py` 生成摘要：

```bash
python3 skills/disclosure-archive/scripts/batch_summary.py --batch-id batch-YYYYMMDD-NNNN
```

摘要输出到 `batches/batch-YYYYMMDD-NNNN.json`，包含记录统计、分层分布、check.py 结果、**批次质量评分**（`batch_quality_score`：PASS_STRONG / PASS_WITH_WARNINGS / NEEDS_FIX / FAIL）及 `blocking_issues` / `warnings` 列表。

## 目录结构

```
disclosure-archive/
├── SKILL.md                # 主文档（完整字段 schema + 规则）
├── README.md               # 本文件
└── scripts/
    ├── archive.py          # 归档脚本
    ├── check.py            # 健康检查
    ├── batch_summary.py    # 批次摘要
    ├── candidate_discovery.py  # 候选发现
    ├── review_queue.py     # review queue 生成
    └── auto_gap_backfill.py    # 自动证据缺口发现
```

## 存档输出

```
wiki/raw/disclosures/
├── manifest.jsonl
├── evidence-gap-queue.json     # 证据缺口队列（auto_gap_backfill 生成）
├── YYYY-MM-DD/
│   ├── theme_term__公司名_代码_类型_标题_slug.md
│   └── assets/
├── batches/
│   ├── batch-YYYYMMDD-NNNN.json        # 批次摘要
│   ├── auto-backfill-<batch-id>.json    # auto backfill 收尾摘要
│   └── discovery_*.json                 # 候选发现
└── review-queue/
    └── review-queue_*.json              # review queue 候选
```

## 证据分层

| 层级 | 来源 | 典型 update_type |
|------|------|-----------------|
| L1 | 知识库 raw 研报/外部研究 | weak_signal / graph_only |
| L2 | 公告/年报/官网产品页 | baseline / hard_delta |
| L3 | 互动易/调研纪要/投关记录 | review_candidate |
| L4 | 媒体/行业网站/公众号 | weak_signal |

**注意：** `source_type=other` 不得用于 `baseline`/`hard_delta`；`hard_delta` 只能来自 L2；`graph_only` 不限层级。

## Gap 状态跟踪

`evidence-gap-queue.json` 中每个 gap 携带 9 种状态（`pending` / `selected` / `archived` / `skipped_no_accessible_source` / `deferred_no_stronger_evidence` / `deferred_weak_or_indirect_only` / `deferred_role_too_generic` / `deferred_concept_boundary_unclear` / `failed_runtime_error`），各有冷却期（7-90天），防止同一缺口被重复处理。`--include-deferred` / `--force-gap-id` 可穿透冷却期。

## Role 禁止泛词

`archive.py`、`check.py`、`batch_summary.py` 三方一致校验 6 类禁止模式：原泛词（相关公司等）、营销炒作（受益标的/龙头/先行者等）、模糊能力（涉足/具备相关能力等）、器件描述、裸产业链位置、裸行业公司。违规直接拒绝写入。

## 后续入库转换

| 目标 | 筛选条件 |
|------|----------|
| entity_delta | `update_type=hard_delta` + `evidence_layer=L2` |
| baseline | `update_type=baseline` + `evidence_layer=L2` |
| concept_delta | 按 `chain_layer` / `role` 补充概念图谱 |
| evidence_index | `exposure_strength≠watchlist` + `graph_only=false` |

## 完整工作流

```
用户输入(theme_term)
  → [Candidate Discovery] 未知公司时，输出候选 → candidate_discovery.py
  → [抓取] web-access → archive.py
  → [质量检查] check.py + batch_summary.py
  → [Review Queue] review_queue.py → review-queue/*.json
  → [人工审核 + Writer Apply] 由主流程执行

Auto Gap Backfill（无人指定 concept/company）：
  entity_exposures.json + concept_graph.json + manifest.jsonl
    → auto_gap_backfill.py --mode gap-queue → evidence-gap-queue.json
    → 外部 process 选取队列前 N 项归档
    → auto_gap_backfill.py --mode finalize → batch_summary + review_queue + check
```

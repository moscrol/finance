---
name: disclosure-archive
metadata:
  pattern: reviewer
  also: [pipeline]
description: 题材雷达(theme-radar)证据归档——围绕题材/概念抓取A股公司公开披露，输出结构化证据供后续入库审核。触发词：补公告、补公司硬证据、查年报、查半年报、查招股书、查互动易、查官网产品页、查扩产/投产/订单/中标/合同/客户认证资料、披露归档、disclosure archive、归档公告。
---

# Disclosure Archive Skill

Theme-radar 的 evidence archive — 题材证据采集工作流。
围绕 **theme_term / canonical_concept / company / code / chain_layer / role / exposure_strength / evidence_layer / update_type** 组织归档。

**只存档，不入库**——默认不修改 Obsidian wiki 正文、不写 entity/concept、不更新 relations JSON。
输出可经 review queue 转换为 entity_delta / baseline / concept_delta / evidence_index 四种 payload 供审核。

## 核心原则

1. **只归档，不入库**——输出到 `wiki/raw/disclosures/`，不污染已有知识图谱
2. **优先官方与一手来源**——巨潮/交易所/公司官网 > 互动易 > 权威媒体 > 新闻软文
3. **theme-radar 对齐**——每条记录必须绑定到一个 theme_term，按 evidence_layer 分层，供后续公司排序使用
4. **role 禁止泛词**——不得写"相关公司、产业链参与者、中游制造及提供商"，必须写具体角色
5. **low确定性标注**——"拟投资、规划、框架协议、战略合作、可应用于、正在布局、关注相关技术"必须标注为低确定性，不得标 hard_delta
6. **graph_only / exposure_only 隔离**——纯图谱连接或曝光数据不写入实体正文，只存在 evidence archive 供 radar 排序
7. **先发现，后归档**——未知公司时先做 candidate discovery，只选 priority=high 的前 3-5 家进入实际 archive
8. **review queue 中转**——每条归档最终通过 review queue 生成 payload 候选，不直接 apply

## 适用场景

- 用户输入新词/题材 → 查公司硬证据 → 归档供 radar 分析
- 用户要求"补公告"——补某公司的历史公告归档
- 用户要求"查年报/半年报/季报/招股书"——归档定期报告
- 用户要求"查互动易/上证 e 互动"——归档投关记录
- 用户要求"查官网产品页"——归档产品/技术/方案页面
- 用户要求"补扩产/投产/订单/中标/合同/客户认证资料"——归档公告级硬 delta
- 用户要求"查某公司的某题材证据"——按 theme_term + company 检索已有归档

## 完整字段 Schema

完整字段 Schema（归档字段表 + 5 个新审计字段判断逻辑 + 审计硬规则 + role 禁止泛词 + 证据质量检查清单）见 `references/field-schema.md`。归档前必须加载该文件，逐字段填写并逐条通过校验，不要凭记忆省略。

## 证据分层与分类规则

资料优先级、证据分层（L1–L4）、以及 `update_type` / `fact_type` / `fact_status` 的取值与映射规则见 `references/evidence-classification-rules.md`。判级与填字段前按该文件的口径对照。

## 默认工作流

### 0. Candidate Discovery（可选）

当用户只给 theme_term、不知道公司名单时：

1. 通过 web-access / 知识库检索发现候选公司
2. 输出最多 10 家候选，每条含 `theme_term`、`canonical_concept`、`company`、`code`、`chain_layer`、`expected_role`、`candidate_source`、`candidate_reason`、`priority`、`suggested_query_terms`
3. 候选公司**不能被当作已证实核心公司**
4. 只能选择 `priority=high` 的前 3-5 家进入实际 archive
5. 调用 `candidate_discovery.py` 保存结果到 `batches/discovery_*.json`

### 1. 接收输入

- `theme_term`（必填）——用户输入的新词或题材
- `canonical_concept`（可选）——如已知，直接指定
- `company` / `code`（至少一个）
- 时间范围（可选）
- 资料类型（可选）

### 2. 制定抓取计划

明确要查哪些来源。如用户只给 theme_term，先列出候选公司+chain_layer，不直接大规模抓取。

### 3. 抓取资料

优先官方来源，保存原始文本/PDF。

### 4. 结构化归档

按完整字段 schema 输出，调用 `archive.py` 写入。支持 `--batch-id` 归入批次。

### 5. 质量检查

- 调用 `check.py` 验证全 manifest
- 调用 `batch_summary.py` 生成批次摘要到 `batches/`

### 6. Review Queue（可选）

从 manifest.jsonl 按 theme_term 筛选，生成 review candidates 供审核：

1. 调用 `review_queue.py` 输出到 `review-queue/`
2. 分组：entity_delta_candidates / baseline_candidates / concept_delta_candidates / evidence_index_candidates / reject_or_watchlist

### 7. 后续入库接口

本 Skill 只生成 `archived_only` 资料，**不直接入库**。后续由人工筛选后通过 writer 转换：

1. **entity_delta payload**——公司边际变化，交给 `entity-delta-ingest` writer
2. **baseline payload**——公司基础画像，交给 `company-baseline-ingest` writer
3. **concept_delta payload**——概念/产业链更新，交给 `concept-delta-ingest` writer
4. **evidence_index item**——证据索引，交给 theme-radar 的 `evidence_index.json`

## 存档目录结构

```
wiki/raw/disclosures/
├── manifest.jsonl
├── YYYY-MM-DD/
│   ├── theme_term__公司名_代码_类型_标题_slug.md
│   └── assets/
│       └── 原始PDF或HTML快照
├── batches/
│   ├── batch-YYYYMMDD-NNNN.json   # 批次摘要
│   └── discovery_*.json            # 候选发现结果
└── review-queue/
    └── review-queue_*.json         # review queue 候选
```

## Markdown 存档格式

每条归档的 Markdown 文件必须套用 `assets/archive-template.md` 的结构（frontmatter 全字段 + 原始来源 / 可验证事实 / 原文摘录 / 主题关联 / 证据质量 / 后续入库建议）。直接复制该模板填空，不要自创结构。

## manifest.jsonl 格式

每行一条完整 JSON，schema 同完整字段表。字段顺序无关，但必须包含所有必填字段。

## 严格禁止

- 把"拟投资、规划、框架协议、战略合作、可应用于、正在布局、关注相关技术"标为 `hard_delta`
- 把普通新闻或券商研报当作 L2
- 默认 `exposure_strength=core`
- 生成"相关公司、产业链参与者、中游制造及提供商"这类无信息量的 role
- 直接修改 `wiki/entities/*.md`、`wiki/concepts/*.md`、`wiki/relations/*.json`
- 覆盖已有归档文件（如重复，写入 `duplicate_of` 字段）
- 在未做抓取计划前直接大规模抓取所有候选公司
- 把无 URL、无日期、无 `quoted_text` 的内容入档
- 把候选公司当作已证实核心公司（candidate 仅作为调研起点）
- 使用 `source_type=other` 标注 baseline/hard_delta（other 来源不确定，不得用于 baseline/hard_delta）
- 产品页无发布日期时用 fetched date 代替而不在 uncertainty 中标注

## Architecture & Boundaries

### Role in the System

disclosure-archive 是 theme-radar 的 evidence archive，**不是 theme-radar 本身**。

- 可以做候选发现（candidate discovery），但不能输出最终核心公司排序
- 可以归档证据，但不能修改 `wiki/entities/`、`wiki/concepts/`、`wiki/relations/`
- 可以生成 review queue，但不能运行 `entity_delta_writer`、`baseline_writer`、`concept_writer`
- 最终入库和公司排序由主流程 / theme-radar 完成

### Permitted Write Locations

本 Skill 的抓取结果统一写入 `wiki/raw/disclosures/`：

1. `manifest.jsonl` — 归档索引
2. `YYYY-MM-DD/*.md` — 日期目录下的 Markdown 归档文件
3. `YYYY-MM-DD/assets/` — PDF/HTML/text 快照
4. `batches/` — 批次摘要 + 候选发现
5. `review-queue/` — review queue 候选

### Strictly Forbidden

1. 修改 `wiki/entities/*.md`
2. 修改 `wiki/concepts/*.md`
3. 修改 `wiki/relations/*.json`
4. 运行 `entity_delta_writer` / `baseline_writer` / `concept_writer`
5. 生成 payload 后自动 apply（可输出草案到 `test_workdir/`，但不 apply）

### Default Field Values

| 字段 | 初始值 | 说明 |
|------|--------|------|
| `ingest_status` | `archived_only` | 只归档未入库，永久不变 |
| `review_status` | `unreviewed` | 初始未审核，后续可更新为 reviewed/approved/rejected/duplicate/needs_edit |
| `not_applied` | `true` | 尚未 apply。非人工明确修改不得改为 false |
| `applied_payload` | `null` | 已应用的 payload 类型 |
| `review_notes` | `null` | 审核备注 |

### Downstream Flow

```
candidate discovery → archive → batch summary → review queue → 人工审核 → writer apply
```

跳过人工审核直接入库会污染知识图谱。即使收到"顺便入库"的请求，也必须先输出 review queue 候选供审核，拒绝自动 apply。

## 质量检查

每次归档后输出 JSON 摘要：

```json
{
  "archived_count": 5,
  "skipped_count": 1,
  "duplicate_count": 0,
  "failed_count": 0,
  "by_evidence_layer": {"L2": 3, "L3": 2},
  "by_update_type": {"hard_delta": 3, "review_candidate": 2},
  "by_exposure_strength": {"core": 0, "related": 3, "peripheral": 2, "watchlist": 0},
  "by_chain_layer": {"midstream_manufacturing": 3, "upstream_materials": 2},
  "missing_required_fields": [],
  "graph_only_count": 0,
  "exposure_only_count": 1,
  "next_recommended_batch": "查上游材料供应商官网产品页"
}
```

## 后续 payload 转换对照

| 目标 payload | 筛选条件 | 转换说明 |
|-------------|----------|----------|
| entity_delta | `update_type=hard_delta` + `evidence_layer=L2` | 提取 company/code/facts → entity-delta-ingest |
| baseline | `update_type=baseline` + `evidence_layer=L2` | 提取 company/code/role/facts → company-baseline-ingest |
| concept_delta | `chain_layer`+`role` 补充概念上下游 | 提取 theme_term/chain_layer → concept-delta-ingest |
| evidence_index | `exposure_strength≠watchlist` + `graph_only=false` | 提取 evidence_layer/facts → theme-radar evidence_index.json |

## 脚本工具

### `scripts/archive.py`
主归档脚本。接收完整字段，写入 Markdown 文件并追加 manifest.jsonl。

```bash
python3 skills/disclosure-archive/scripts/archive.py \
  --theme-term "感光膜" \
  --canonical-concept "感光干膜" \
  --aliases "感光干膜" "dry film photoresist" \
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
  --url "https://..." \
  --quoted-text "公司感光干膜产品已通过XX客户认证，具备量产能力。" \
  --facts "感光干膜产品通过客户认证" "已具备量产能力"
```

### `scripts/check.py`
健康检查脚本。验证 disclosures 目录完整性、字段完整性、分层分布统计。

```bash
python3 skills/disclosure-archive/scripts/check.py
```

### `scripts/batch_summary.py`
批次摘要生成脚本。从 manifest.jsonl 筛选 batch_id 记录，输出 JSON 摘要到 `batches/`，自动调用 check.py。

```bash
# 生成批次摘要（自动运行 check.py）
python3 skills/disclosure-archive/scripts/batch_summary.py \
  --batch-id batch-20260527-0002

# 跳过 check.py（节省时间）
python3 skills/disclosure-archive/scripts/batch_summary.py \
  --batch-id batch-20260527-0002 --skip-check
```

### `scripts/candidate_discovery.py`
候选公司发现脚本。接收候选公司列表（`--candidates` 可传内联 JSON 或文件路径），校验后输出到 `batches/discovery_*.json`。

```bash
# 从文件读取候选
python3 skills/disclosure-archive/scripts/candidate_discovery.py \
  --theme-term "感光膜" \
  --canonical-concept "感光干膜" \
  --aliases "感光干膜" "DFR" \
  --candidates /tmp/candidates.json

# 内联 JSON
python3 skills/disclosure-archive/scripts/candidate_discovery.py \
  --theme-term "感光膜" \
  --canonical-concept "感光干膜" \
  --candidates '[{"company":"容大感光","code":"300576","chain_layer":"midstream_manufacturing","expected_role":"PCB干膜光刻胶供应商","candidate_source":"knowledge_base","candidate_reason":"主营业务含感光干膜","priority":"high","suggested_query_terms":"感光干膜 产能 投产"}]'
```

### `scripts/review_queue.py`
Review Queue 生成脚本。从 manifest.jsonl 按 `theme_term` / `canonical_concept` 筛选记录，分组为 entity_delta / baseline / concept_delta / evidence_index / reject_or_watchlist 候选，输出到 `review-queue/`。只生成候选，不运行 writer，不修改知识库。

```bash
# 按 theme_term 生成 review queue
python3 skills/disclosure-archive/scripts/review_queue.py \
  --theme-term "感光膜"

# 按 canonical_concept 生成
python3 skills/disclosure-archive/scripts/review_queue.py \
  --canonical-concept "感光干膜"

# 不过滤，生成全部
python3 skills/disclosure-archive/scripts/review_queue.py
```

### `scripts/auto_gap_backfill.py`
自动证据缺口发现与归档脚本。从知识库（entity_exposures.json + concept_graph.json + manifest.jsonl）自动发现最值得补证据的缺口，小批量归档。两个模式：

- **`--mode gap-queue`**：生成 `evidence-gap-queue.json`。按优先级（P0 > P1 > P2 > P3）排序，只保留 A 股，同 (company, concept) 去重。
- **`--mode finalize --batch-id <id>`**：归档完成后收尾——生成 batch summary + review queue + check.py + auto-backfill summary。

**Gap 优先级：**
| 优先级 | 类型 | 说明 |
|--------|------|------|
| P0 | `archived_adjacent_needs_direct` / `weak_entity_exposure` | 已有低质量证据需升级为 L2 direct |
| P1 | `concept_stub_missing_evidence` | concept_graph 低置信度节点无公司证据 |
| P2 | `radar_empty_frame` | entity_exposures 中有暴露但该 concept 无归档 |
| P3 | `indirect_missing_direct` | 仅有间接证据，缺少同一 company-concept 的直接证据 |

```bash
# 生成证据缺口队列（dry-run，不抓取）
python3 skills/disclosure-archive/scripts/auto_gap_backfill.py \
  --mode gap-queue \
  --vault "/Users/lbq/Desktop/c c/知识库/wiki" \
  --disclosures-dir "/Users/lbq/Desktop/c c/知识库/wiki/raw/disclosures"

# 限制输出条数
python3 skills/disclosure-archive/scripts/auto_gap_backfill.py \
  --mode gap-queue --limit 20

# 包含冷却期已过的 deferred/skipped gaps
python3 skills/disclosure-archive/scripts/auto_gap_backfill.py \
  --mode gap-queue --include-deferred

# 强制选择指定 gap_id（忽略冷却期）
python3 skills/disclosure-archive/scripts/auto_gap_backfill.py \
  --mode gap-queue --force-gap-id gap-20260527-0005

# 归档完成后收尾
python3 skills/disclosure-archive/scripts/auto_gap_backfill.py \
  --mode finalize \
  --batch-id batch-20260527-0003 \
  --vault "/Users/lbq/Desktop/c c/知识库/wiki" \
  --disclosures-dir "/Users/lbq/Desktop/c c/知识库/wiki/raw/disclosures"
```

### Gap 状态跟踪与冷却期

`evidence-gap-queue.json` 中每个 gap 携带状态字段，防止重复处理同一缺口：

| 状态 | 含义 | 冷却期 |
|------|------|--------|
| `pending` | 待处理，可被选择 | — |
| `selected` | 已被某批次选中，处理中 | — |
| `archived` | 已归档，从活跃队列移除 | — |
| `skipped_no_accessible_source` | 跳过：无可访问来源 | 30天 |
| `deferred_no_stronger_evidence` | 延后：未找到更强证据 | 90天 |
| `deferred_weak_or_indirect_only` | 延后：仅有弱/间接证据 | 90天 |
| `deferred_role_too_generic` | 延后：role 描述过于泛化 | 60天 |
| `deferred_concept_boundary_unclear` | 延后：概念边界不清 | 60天 |
| `failed_runtime_error` | 失败：运行时错误 | 7天 |

冷却期内 `next_check_after` 未到期的 gap 在 `gap-queue` 模式下自动跳过。`--include-deferred` 可强制包含冷却期已过的忽略项，`--force-gap-id` 可强制选择指定 gap（忽略所有冷却期）。

### 批次质量评分（batch_quality_score）

`batch_summary.py` 和 `auto_gap_backfill.py --mode finalize` 自动计算 4 级批次评分：

| 评分 | 条件 |
|------|------|
| `PASS_STRONG` | 所有记录 `source_origin=primary_official`，无任何警告 |
| `PASS_WITH_WARNINGS` | 检查通过，仅有可容忍的小问题（如个别 media_reprint 来源） |
| `NEEDS_FIX` | 检查通过但存在可恢复问题（不良 source_origin、禁止 role 模式等） |
| `FAIL` | check.py 失败或存在阻塞性硬规则违反 |

评分基于逐条记录对 9 条审计硬规则的检查，输出 `blocking_issues` 和 `warnings` 列表。

## 数据流

```
用户输入(theme_term)
  │
  ▼
[0. Candidate Discovery]  ← 未知公司时
  │  输出候选 → candidate_discovery.py → batches/discovery_*.json
  │  选择 priority=high 前 3-5 家
  ▼
[1. 制定抓取计划]
  │
  ▼
[2. 抓取资料]  ← web-access (CDP 浏览器)
  │
  ▼
[3. 结构化归档]  ← archive.py (--batch-id)
  │  → YYYY-MM-DD/*.md + manifest.jsonl
  ▼
[4. 质量检查]
  │  check.py + batch_summary.py → batches/batch-*.json
  ▼
[5. Review Queue]  ← review_queue.py → review-queue/*.json
  │  分组: entity_delta / baseline / concept_delta / evidence_index
  ▼
[6. 人工审核 + Writer Apply]  ← 由主流程执行，本 Skill 不自动 apply
  → entity-delta-ingest / company-baseline-ingest / concept-delta-ingest / evidence-index-update

Auto Gap Backfill 分支（无人指定 concept/company）：
  entity_exposures.json + concept_graph.json + manifest.jsonl
    │
    ▼
  [auto_gap_backfill.py --mode gap-queue]
    │  → evidence-gap-queue.json（P0→P3 排序，A股，去重）
    ▼
  [选取队列前 N 项]
    │
    ▼
  [外部 process: archive.py + web-access 抓取归档]
    │
    ▼
  [auto_gap_backfill.py --mode finalize --batch-id <id>]
    │  → batch_summary.py + review_queue.py + check.py
    │  → batches/auto-backfill-<batch-id>.json
    ▼
  停止（不运行 writer，不修改 entities/concepts/relations）
```

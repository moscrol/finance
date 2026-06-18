# Disclosure Archive 完整字段 Schema

> 本文件由 `skills/disclosure-archive/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

| 字段 | 必填 | 说明 |
|------|------|------|
| `archive_id` | 是 | 归档唯一 ID，格式 `disc-YYYYMMDD-NNNN` |
| `batch_id` | 否 | 批次 ID，格式 `batch-YYYYMMDD-NNNN`，用于批次管理 |
| `theme_term` | 是 | 用户输入的新词或题材，如 `感光膜` |
| `canonical_concept` | 是 | 规范化后的知识库概念名，如 `感光干膜` |
| `aliases` | 否 | 别名列表，如 `["感光干膜", "dry film photoresist", "DF"]` |
| `company` | 是 | 公司名称 |
| `code` | 是 | 股票代码 |
| `chain_layer` | 是 | 产业链层：`upstream_materials` / `upstream_equipment` / `midstream_manufacturing` / `midstream_service` / `downstream_application` / `ecosystem` |
| `role` | 是 | 具体角色描述，禁止泛词。如 `PCB干膜光刻胶供应商`、 `IC载板MSAP工艺设备商` |
| `exposure_strength` | 是 | `core` / `related` / `peripheral` / `watchlist`。默认不标 core |
| `evidence_layer` | 是 | `L1` / `L2` / `L3` / `L4`（见证据分层规则） |
| `update_type` | 是 | `baseline` / `hard_delta` / `review_candidate` / `graph_only` / `weak_signal` / `reject` |
| `fact_type` | 是 | `revenue_mix` / `capacity` / `shipment` / `product_launch` / `certification` / `customer_adoption` / `contract` / `tender_win` / `mass_production` / `project_construction` / `product_capability` / `official_claim` / `media_signal` |
| `fact_status` | 是 | `realized` / `disclosed` / `under_validation` / `planned` / `framework` / `rumored` |
| `graph_only` | 是 | `true`/`false`——只证明公司与概念有关，不足以写入实体正文 |
| `exposure_only` | 是 | `true`/`false`——仅曝光/产业链映射，无公司级事实 |
| `confidence` | 是 | `high` / `medium` / `low` |
| `title` | 是 | 资料标题 |
| `publish_date` | 是 | 发布日期，格式 `YYYY-MM-DD` |
| `fetched_at` | 是 | 抓取时间，格式 `YYYY-MM-DDTHH:MM:SS+08:00` |
| `url` | 是 | 来源 URL |
| `quoted_text` | 是 | 原文摘录，必须保留。不得改写 |
| `extracted_facts` | 是 | 可验证事实列表，`["事实1", "事实2"]` |
| `uncertainty` | 否 | 不确定性说明 |
| `raw_path` | 否 | 原始文件路径（PDF/HTML 快照） |
| `suggested_next_action` | 是 | `read_for_delta` / `read_for_baseline` / `read_for_concept` / `mark_weak` / `reject` |
| `ingest_status` | 是 | 固定为 `archived_only`，表示只归档未入库 |
| `review_status` | 是 | `unreviewed` / `reviewed` / `approved` / `rejected` / `duplicate` / `needs_edit`。初始 `unreviewed` |
| `not_applied` | 是 | `true` / `false`。初始 `true`，表示尚未 apply 到知识库。非人工明确修改不得为 false |
| `applied_payload` | 否 | 已应用的 payload 类型（如 `entity_delta` / `baseline`）。初始 `null` |
| `review_notes` | 否 | 审核备注。初始 `null` |
| `duplicate_of` | 否 | 如重复，指向已存在的 `archive_id` |
| `source_origin` | 否 | 来源原始性：`primary_official` / `official_repost` / `media_reprint` / `secondary_summary`。用于判级 |
| `concept_match_type` | 否 | 概念匹配类型：`direct_alias` / `explicit_synonym` / `upstream_component` / `downstream_application` / `adjacent_substitute` / `inferred_only` / `negative` |
| `evidence_polarity` | 否 | 证据极性：`positive` / `adjacent` / `negative` / `historical` |
| `time_scope` | 否 | 时间跨度：`current` / `historical` / `planned` / `exited` / `unknown` |
| `fact_traceability` | 否 | 事实可追溯性：`all_facts_supported` / `partial_support` / `unsupported_claims` |

### 新字段说明

| 字段 | 判断逻辑 |
|------|----------|
| `source_origin` | `primary_official`=交易所/巨潮/公司官网/官方互动平台原始来源；`official_repost`=公司官方转发/官网新闻；`media_reprint`=媒体转载公告/年报；`secondary_summary`=财经网站摘要/研报转述/新闻整理 |
| `concept_match_type` | `direct_alias`=原文直接出现概念或别名；`explicit_synonym`=明确同义词；`upstream_component`=上游材料/设备关系；`downstream_application`=下游应用关系；`adjacent_substitute`=相邻或替代品；`inferred_only`=仅靠产业链推断；`negative`=明确不生产/不涉及 |
| `evidence_polarity` | `positive`=正面证据；`adjacent`=相邻/替代/间接；`negative`=负面/否定；`historical`=历史状态，当前已变化 |
| `time_scope` | `current`=当前状态；`historical`=历史状态；`planned`=规划/意向；`exited`=已退出/已终止；`unknown`=无法判断 |
| `fact_traceability` | `all_facts_supported`=所有事实被quoted_text直接支持；`partial_support`=部分事实无法直接追溯；`unsupported_claims`=关键判断不在原文 |

### 审计硬规则（Pre-Archive Audit Hard Rules）

设置 5 个审计字段后，以下硬规则在归档时自动校验（archive.py + check.py）：

| 规则 | 触发条件 | 阻断 |
|------|----------|------|
| 1a | `source_origin≠primary_official` 且 `source_type` 为 annual_report/prospectus/announcement 且无 `raw_path` | 必须提供 raw_path（无法验证原文真实性） |
| 1b | `source_origin≠primary_official` 且 `update_type=baseline/hard_delta` | **无条件阻断**——非官方原始来源不得用于 baseline/hard_delta（raw_path 不豁免） |
| 2 | `concept_match_type=inferred_only/adjacent_substitute/negative` 且 `update_type=baseline/hard_delta` | 推断/相邻/否定匹配不得用于 baseline/hard_delta |
| 3 | `evidence_polarity=adjacent/negative/historical` 且 `update_type=baseline/hard_delta` | 非正面证据不得用于 baseline/hard_delta |
| 4 | `time_scope=historical/exited/planned` 且 `update_type=baseline/hard_delta` | 非当前状态不得用于 baseline/hard_delta |
| 5 | `fact_traceability≠all_facts_supported` 且 `update_type=baseline/hard_delta` | 不可完全追溯时不得标 baseline/hard_delta，降级为 review_candidate |
| 8 | `source_origin=primary_official` 但 URL 域名为媒体转载平台 | 仅当无 `raw_path` 时报错（有 raw_path 可交叉验证→通过） |
| 9 | 产品页（official_website_product）的 `publish_date` 等于抓取日期 | 必须在 `uncertainty` 中标注"发布日期为抓取日期" |

**违反任意规则即拒绝写入。** 归档前必须为每条记录填写 5 个审计字段并确保通过规则检查。

### Role 禁止泛词（扩展版）

以下模式在 role 字段中禁止使用，`archive.py` 和 `check.py` 均会校验：

- **原泛词**：相关公司、相关企业、产业链参与、产业链上下游公司、中游制造及提供商、参与者、相关上市公司、裸"公司/企业/厂商/供应商/制造商/生产商"
- **营销/炒作泛词**：受益标的、布局企业、龙头、领先企业、先行者、重要玩家、平台型公司、生态伙伴
- **模糊能力描述**：具备相关能力、涉足、相关业务布局
- **器件/组件描述**（非公司角色）：芯片/核心器件、核心器件
- **裸产业链位置**：上游材料企业、中游制造商、下游应用企业
- **裸行业公司**：芯片公司、材料公司、设备公司

违规示例：`芯片/核心器件` → 拒绝；`受益标的` → 拒绝。合规示例：`RISC-V架构音频SoC芯片设计商` → 通过；`数字创意软件工具与服务提供商` → 通过。

### 证据质量检查清单

归档前确认：

- [ ] 5 个审计字段（source_origin / concept_match_type / evidence_polarity / time_scope / fact_traceability）已填写
- [ ] 无硬规则违反（archive.py 校验通过）
- [ ] `fact_traceability=partial_support` 时，已在 `uncertainty` 中说明哪些事实无法直接追溯
- [ ] 不同时间点的证据拆分为独立归档（如"2024年生产"与"2026年退出"不能合为一条）
- [ ] 每条 `extracted_facts` 都有 `quoted_text` 的直接支持
- [ ] 媒体转载来源的 annual_report/prospectus/announcement 标注了 `media_reprint` 且使用了合适的 evidence_layer

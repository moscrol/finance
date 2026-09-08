# 知识库回填规则与 theme-radar 对齐口径

> 从 `AGENTS.md` / `CLAUDE.md` 迁出的按需参考（2026-09）。回填脚本与 ingest 类 skill 的规范源在知识库仓
> （`<知识库>/skills/concept-ingest`、`<知识库>/skills/entity-delta-ingest`、`<知识库>/scripts/ingest.py`、
> `<知识库>/scripts/backfill_entities_from_full_reports.py`），本页只放口径与流程约定；最终应随脚本一起迁到知识库仓的 AGENTS.md。
> 触发场景：用户说「回填知识库」「继续回填」「概念入库」「公司边际变化入库」「PDF ingest」。

## 1. 组织契约：一切以 theme-radar 为下游消费者

知识库的每次更新都要能被 `theme-radar` skill 直接消费。判断标准：如果某次更新会让实体页更好看、却让 theme-radar 的公司排序、证据分层或产业链清晰度变差，选 theme-radar 兼容的表示法。

证据分层，四层分开写、不混：

| 层 | 内容 | 来源 |
|---|---|---|
| L1 | 产业翻译、研报判断（核心个股表、产业链名单、龙头/市占率/应用前景、仅百分比同比） | 研报、脱水材料 |
| L2 | 公司基础画像（真实主营、主营产品、收入结构、毛利率、行业分类、证券基础信息） | iFinD / AKShare / 年报定期报告 / 公告 / 交易所互动 / 官网 / 监管披露 / 人工核验 |
| L3 | 公司级硬事实（公告、订单、合同、中标、认证、量产、投产、扩产、产能、客户导入、项目落地，带金额或数量口径的财务与出货事实） | 一手披露 |
| L4 | 市场信号 | 盘面 |

每个新 ingest / 清理脚本都要保留 theme-radar 需要的字段：`chain_layer`、`evidence_layer`、`update_type`、来源链接、raw 源可追溯路径，以及保守的 `core / related / peripheral` 强度。

## 2. 什么可以写进实体正文

- `raw/*full.md` 研报的提及默认**不**写实体正文：拆成 报告上下文（`report_context`）、图谱暴露（`graph_only` / `exposure_only`）、真公司级 delta 三类。
- 只有 L3 硬事实才允许进 `## 边际变化`。
- 研报里二手但具体的公司事实（送样、样品、长协、明确客户或供应关系、控股关键产业链公司、出货或收入同比、良率、市占率、项目数量等带数字口径）可升级为 `evidence_layer=L1_L3_candidate` + `update_type=review_candidate`，但仍保持 `graph_only=true` / `exposure_only=true`，只进图谱与证据索引，供 theme-radar 排序与人工复核。这是排序信号，不是实体正文 delta，也不是 L2 baseline。
- 通用上游材料、上游设备、下游需求 / 客户侧、生态公司，默认 `graph_only` / `exposure_only`，强度 `peripheral` 或弱 `related`，除非有公司级硬证据。
- 纯榜单、仅名字提及，留在 report context / 观察列表。
- 概念页：broker 源新建概念用 `## 高信度研究线索`，不用 `## 边际变化`。

## 3. baseline（L2）来源必须真实

- 只能来自真实结构化基础资料或明确署源的公司基本面；不写占位文本、不写自动批次证据、不写 unsupported `core` 结论、不把短期催化 / 新闻 / 规划混进 baseline。
- `baseline_source_type ∈ ifind | akshare | annual_report | announcement | exchange_interaction | official_website | regulatory_filing | manual_verified`，实体页与 relation JSON 都要写真实来源类型与 raw 路径。AKShare / 公开 / 人工核验资料不得标成 `iFinD 基础资料 / 公司摘要`。
- 某来源返回限流 / 空 / 错误文本（如 `用户使用工具已超限`）时，该来源该公司的 baseline 批次停下；没有可用字段的有效 raw 文件之前，不许手工拼一份并标成该来源、`L2` 或 `update_type=baseline`。
- 弱映射统一写 `弱相关，待验证`，不硬编模板化产业链角色；直接主营产品可以给 `core/high`。
- 上一批的质量审计或回填清理没完成，不盲跑下一批：先审 payload、实体页和 relations。

## 4. 回填目标模式（开工先确认，不混用）

| 模式 | 做什么 | 命令 | 输出要说清 |
|---|---|---|---|
| `context_only` | `raw/*-full.md` → `relations/report_contexts.json` + `wiki/raw/entity-delta-backfill/*.entity-delta.json` payload；不动 `entities/*.md` | `python3 <知识库>/scripts/backfill_entities_from_full_reports.py --write-context ...` | 「本轮是 report context / payload 回填，不是实体正文写入」 |
| `entity_apply` | 把 payload 中非 `graph_only` / 非 `exposure_only` 的 hard delta 写进 `entities/*.md` | 同上加 `--apply` | `updates=0` / `written=0` 或全部 graph_only/exposure_only 时报「本批无可写实体正文」，不伪造更新 |
| `review_only` | 只出 payload 与 summary，人工抽查后再决定 apply | 不加 `--apply`；抽查 1 个 payload + 1–3 个目标文件 | 抽查结论 |

## 5. Raw Full 完整回填闭环（三层，逐层报告停在哪）

1. `full.md → report_contexts.json + entity-delta payload`：产出研报级产业链上下文（theme-radar 用）与候选审查材料。
2. `payload → hard delta → entities/*.md`：只有存在 hard delta 才 `--apply`；没有就在第 1 层停止并说明原因。
3. `entities 新候选 / 重要暴露公司 → multi-source baseline`：只对新增实体、核心暴露公司、或缺基础画像且确有后续研究价值者触发；只写第 3 节允许的稳定事实并标真实来源。

执行时逐段报告当前停在 `report_context/payload`、`entities` 还是 `baseline`，以及没进下一层的原因（`updates=0`、全部 graph_only/exposure_only、缺 hard delta、缺 baseline 触发条件）。

## 6. 「继续回填知识库」的执行节奏

1. 读最近任务摘要或用户指定的 `start-after`。
2. 确认任务类型：raw full 回填 / PDF source note 回填 / baseline 回填。
3. 确认目标模式（第 4 节）。
4. 用脚本处理下一小批（3–5 篇），不让模型逐篇读 full.md 正文。
5. 只看脚本 summary；必要时抽查少量命中文件。确认实体是否存在用 `rg --files` 或精确 `rg 公司名`，不读整目录。
6. 输出批次摘要：处理文件数、payload 数、updates 数、graph_only/exposure_only 数、hard delta 数、真正写入实体数、baseline 是否触发、未进入下一层的原因、异常、下一批游标。

## 7. PDF ingest 路由（脱水研报 / 强势脱水 / 评级日报 / 卖方材料）

默认 `source_quality=broker_research_high`，不直接写 `hard_fact` 或 `delta`，不把二手材料写进 `## 边际变化`。

| 路由 | 字段 | 落点 |
|---|---|---|
| `curated_research` | `fact_hardness=review_candidate`，`evidence_layer=L1_L3_candidate` | `## 高信度研究线索`，必须有注释 |
| `graph_only` | `fact_hardness=research_claim`，`strength=peripheral` | 不写 entity markdown；source note 放 `## 仅更新图谱` |
| `observation_only` | — | 只放 `## 观察列表`，不进 entity_exposures |

Lint：`skills/lib/pdf_ingest_lint.py` 检查 relations、concept page section、entity annotation、source note classification、graph_only 一致性、evidence_index 覆盖。回归样本集：0412 / 0331 各自的评级日报、强势股脱水、脱水研报（6 篇全 PASS）。

## 8. 两条入库流程（skill 在知识库仓）

- 概念入库：加载 `<知识库>/skills/concept-ingest/SKILL.md`。IMA 题材 DeepDive：Copilot 15 章 → `deepdive.md` → `build_ima_concept_ingest_queue.py` → 人工 ingest-plan → writer；不搜标题当抽取，不拿 md 直接 writer。研报 / 纪要：判断 is_concept → ingest-plan → `python3 <知识库>/scripts/ingest.py concept ...`。
- 公司边际变化入库：加载 `<知识库>/skills/entity-delta-ingest/SKILL.md`，读早知道 / 评级日报 / 纪要 / 公告，抽取公司边际变化 JSON → `python3 <知识库>/scripts/ingest.py entity-delta ...` 更新 `entities/`；纯榜单进观察列表。

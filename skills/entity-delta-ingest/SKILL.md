---
name: entity-delta-ingest
description: 公司边际变化入库——从早知道、评级日报、会议纪要、公告、研报截图/PDF中提取上市公司边际变化，更新 Obsidian wiki/entities。触发词：entity delta、公司边际变化、更新entity、早知道入库、公司变化入库。
---

# Entity Delta Ingest Skill

把材料中的“公司发生了什么新变化”写入 `wiki/entities/`，区别于 `concept-ingest` 的“新概念入库”。

## 适用场景

- 财联社早知道、评级日报、盘前资讯、电话会议纪要、公司公告。
- 文章中有多家公司，每家公司只有一两条边际变化。
- 用户想更新 `entities/`，而不是新建概念页。

不适用：
- 只有一个产业主题、需要抽成结构化概念页：用 `concept-ingest`。
- 纯榜单/历史新高名单，没有变化原因：默认只输出观察列表，不写 entity。

## 单篇批量流程

处理单篇材料时，本 skill 接收 `concept-ingest` 的 `ingest-plan.entity_update_candidates`、`entity_create_candidates` 和 `watchlist`，先完成分层，再一次性写入：

```
接收单篇 ingest-plan
  ↓
确认已有 entity / 缺页 entity / 观察项
  ↓
把已有更新和允许新建的公司合并成一个 updates[] JSON
  ↓
一次调用 entity_delta_writer.py
  ↓
单篇统一质检 source note 与目标 entity
```

批量写入硬规则：同一篇 source 的所有公司边际变化，必须合并到一个 `updates[]`，一次调用 `entity_delta_writer.py`。不要为每家公司单独调用 writer，避免 source note 重复、frontmatter 多次改写和质检成本膨胀。

压缩写入硬规则：本 skill 只处理 `priority="must_write"` 的公司变化。已有 entity 也不代表必须更新；如果只是材料点名、题材映射、市场挖掘名单或缺少公司级硬边际，放入 `light_note` 或 `watchlist`，不调用 writer。

## 读取材料

1. 先尝试文本抽取（写脚本文件再执行，不使用 heredoc）：

   ```python
   # /tmp/extract_pdf_text.py
   from pypdf import PdfReader

   p = “文件路径.pdf”
   for i, page in enumerate(PdfReader(p).pages, 1):
       print(f”---PAGE {i}---”)
       print(page.extract_text() or “”)
   ```

   ```bash
   python3 /tmp/extract_pdf_text.py
   ```

2. 如果文本为空，说明是图片型 PDF：
   - 优先运行本 skill 的图片提取脚本：
     ```bash
     python3 “/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/extract_pdf_images.py” “文件路径.pdf” --out-dir /tmp/entity_delta_images
     ```
   - 对长图按高度切块，脚本默认每 1800px 一段。
   - 逐块视觉识别，只抽取”公司方面/点讯/边际变化”段落；表格榜单不自动写入。

## 抽取 JSON

从原文抽取为以下 JSON。字段应来自原文，不确定则留空或跳过。

```json
{
  "source_name": "0520早知道",
  "source_date": "2026-05-20",
  "source_file": "/Users/lbq/Desktop/研报/0520早知道.pdf",
  "raw_sources": ["raw/0520早知道.md"],
  "create_missing": false,
  "updates": [
    {
      "company": "兴森科技",
      "code": "002436",
      "create_missing": true,
      "date": "2026-05-20",
      "title": "800G光模块用PCB稳定供货",
      "judgment": "潜在受益，需核实",
      "concepts": ["PCB", "AI算力", "光模块"],
      "role": "midstream_manufacturing",
      "chain_layer": "midstream_manufacturing",
      "tier": "core",
      "confidence": "medium",
      "evidence_layer": "L1_L3_candidate",
      "update_type": "delta",
      "fact_hardness": "review_candidate",
      "bullets": [
        "主营PCB、IC封装基板，800G光模块用PCB已稳定供货国内外一线光模块厂商。",
        "AI短中期基建需求强劲，AI覆铜板/PCB及核心算力硬件景气度提升。"
      ],
      "evidence": "公司方面，兴森科技主营PCB、IC封装基板..."
    }
  ],
  "watchlist": [
    {"company": "恒运昌", "code": "688785", "reason": "历史新高表，缺少边际变化解释"}
  ]
}
```

### 抽取规则

- 只写有明确“新增信息/边际变化/催化”的公司。
- 只把 `priority="must_write"` 的公司放入 `updates[]`；轻量点名不写 entity。
- `bullets` 用 1-4 条，回答“发生了什么、为什么重要”。
- `concepts` 尽量用已有概念名，方便正文 wikilink。
- `role` 写公司在产业链里的位置，如 `上游材料`、`中游设备`、`下游应用`；会进入 `wiki/relations/entity_exposures.json`。
- `tier` 写公司暴露强度：`core/related/peripheral`；与概念页公司分层保持一致。
- `confidence` 写证据置信度：公告/订单/财报 `high`；研报/新闻 `medium`；传闻或弱线索 `low`。
- `judgment` 可选，写入新建 entity 的 `速览/当前判断`，如“龙头/二线/潜在受益/边缘参与/需核实”。
- `evidence` 保留短原文依据，便于复核；不要整段搬运长文。
- `raw_sources` 可选；如果 OCR/全文已落成 `raw/*.md`，填入后会同步到 entity frontmatter。
- `create_missing=false` 是批次默认值；每条 `updates[]` 可单独设置 `create_missing=true`。不要一刀切全局新建，按下面的“分层建档规则”决定。
- 同一篇材料只构造一个 JSON；把所有已有 entity 更新、允许新建的缺页 entity、观察列表放在同一次调用里。

### 来源质量与事实硬度分离（核心原则）

**高信度研究来源 ≠ 公司原始硬事实来源。**

券商研报/评级日报是高信度研究来源（`source_quality=broker_research_high`），但不等于公司原始硬事实（`source_quality=official_disclosure/company_primary`）。

### 路由规则（硬性）

Writer 内置 gate 会自动根据 `source_quality` + `fact_hardness` 路由写入位置。

| 场景 | source_quality | fact_hardness | evidence_layer | update_type | 写入位置 |
|------|----------------|---------------|----------------|-------------|----------|
| 券商研报受益名单/主题研判 | broker_research_high | research_claim | L1 | graph_only | 仅更新图谱 |
| 券商研报普通判断 | broker_research_high | research_claim | L1 | curated_research | 高信度研究线索 |
| 券商研报公司级事实关键词 | broker_research_high | review_candidate | L1_L3_candidate | curated_research | 高信度研究线索 |
| 公告/年报/官网原始证据 | official_disclosure | hard_fact | L3 | delta | 边际变化 |
| 公司原始披露 | company_primary | hard_fact | L3 | delta | 边际变化 |

### broker_research_high / graph_only 标准样本（0129脱水研报）

券商研报汇编（脱水研报、强势脱水、评级日报、风口研报）如果只包含受益名单、行业逻辑、主题研判、机构持仓扩散，没有公司级硬事实（订单/合同/产能/财报/客户导入），统一路由为 graph_only。

**标准样本**：`0129脱水研报`（开源证券/西部证券/银河证券/平安证券，2026-01-29）

4个话题（PVC/锂电出海/Q4医药持仓/半导体涨价潮）全部为券商研判，无公司级硬事实：
- 新建 3 个概念页（PVC、锂电出海、半导体涨价潮）
- 19 条 graph_only exposure（已有 entity 的受益公司）
- 24 家公司进观察列表（缺页或机构信号）
- 0 个 entity 创建，0 条 entity markdown，0 条 ## 边际变化
- lint ALL CHECKS PASSED

**graph_only exposure 字段模板**：

```yaml
update_type: graph_only
strength: peripheral
fact_hardness: research_claim
evidence_layer: L1
source_quality: broker_research_high
confidence: low
# role: 具体业务角色，禁止写"受益标的""相关公司""产业链供应商"
# chain_layer: 合法枚举（upstream_materials/midstream_components 等）
```

**graph_only 禁止搭配**：

- `fact_hardness=review_candidate`（那是 curated_research）
- `evidence_layer=L1_L3_candidate`（那是 curated_research）
- `review_required=true`（graph_only 不需要审核）
- `strength=core` 或 `strength=related`（graph_only 只用 peripheral）
- `update_type=delta`（broker 源无 hard_fact 不得写 delta）

**broker_research_high / graph_only 完整 checklist**：

1. ☐ 抽取 PDF 全文 → `raw/{source_name}.md`
2. ☐ 创建 source note → `wiki/sources/{source_name}.md`（含 frontmatter: title/type/source_date/created/updated/revision/sources/source_quality/log）
3. ☐ source note 引用 raw 文件
4. ☐ 判断话题是否需要新建概念页（is_concept 检查）
5. ☐ 创建新概念页（如有），frontmatter log 用真实全局编号
6. ☐ 逐个检查 entity 存在性（`wiki/entities/{name}.md` 是否存在），不凭记忆判断
7. ☐ 对已有 entity 写 graph_only exposure → `entity_exposures.json`
8. ☐ 缺页公司 + 纯名单 + 机构信号 → source note `## 观察列表`
9. ☐ 不写 entity markdown，不写 `## 边际变化`
10. ☐ 概念页正文用 "据 [[source]] 引述券商观点" 软化确定性表述
11. ☐ 更新 `wiki/index.md`（来源/概念/实体计数 + 分类索引 + log 数组）
12. ☐ 更新 `wiki/log.md`（真实全局编号条目）
13. ☐ 运行 `python3 skills/lib/pdf_ingest_lint.py {source_name}`，要求 0 errors 0 warnings
14. ☐ 验证 relations JSON 可解析

### 公司级事实关键词（可升级为 review_candidate）

量产、批量供货、客户认证、客户导入、订单、合同、中标、投产、扩产、产能、出货、收入、利润、市占率、良率、产品认证

出现这些关键词时，标 `fact_hardness=review_candidate`，不能直接标 `hard_fact`。

### 只有 L3 原始证据才能写入边际变化

只有找到公告、年报、交易所互动、公司官网等 L3 原始证据时，才可标 `fact_hardness=hard_fact` 并写入 `## 边际变化`。

### update_type/fact_hardness/evidence_layer 组合一致性（硬性）

| update_type | 允许的 fact_hardness |
|-------------|---------------------|
| `delta` | `hard_fact`, `baseline` |
| `curated_research` | `research_claim`, `review_candidate` |
| `graph_only` | `research_claim`, `market_narrative`, `unknown`, `legacy_rebuilt` |

- `update_type=delta` 不允许搭配 `fact_hardness=research_claim`
- `evidence_layer=L1_L3_candidate` 必须搭配 `fact_hardness=review_candidate` 和 `review_required=true`
- `hard_fact` 必须搭配 `source_quality=official_disclosure/company_primary`

### role 与 chain_layer 分离（硬性）

- `chain_layer` 是枚举：`upstream_materials`、`midstream_manufacturing`、`downstream_application` 等
- `role` 必须是业务角色短语，不能等于 `chain_layer`
- 禁止 role 只写：`受益标的`、`相关公司`、`产业链供应商`、`midstream_manufacturing` 等
- 合格 role 示例：`AI高端PCB/HLC/HDI/mSAP量产供应商，800G/1.6T光模块PCB供应商`

### 分层建档规则

同一篇材料里通常同时有核心公司、相关公司和纯名单。处理 entity 时按公司级别分层：

| 层级 | 条件 | 写法 |
|---|---|---|
| 核心新建 | 材料明确给出公告/订单/合同/产能/财报/客户导入/技术突破，且公司是本次概念的核心标的或直接受益方 | 即使 `wiki/entities/` 尚无页面，也在该 update 写 `create_missing: true` |
| 已有更新 | `wiki/entities/{公司}.md` 已存在，且材料有明确边际变化 | 不必写单条 `create_missing`，正常追加 |
| 相关观察 | 只是在”相关公司”名单中出现，逻辑间接、原因很短或缺少独立边际 | 不建 entity，放入 `watchlist` |
| 传闻观察 | 客户、订单、独供、PPA、利润弹性等核心信息未见公告或来源标注为市场传闻 | 原则上不新建；若已存在 entity，可追加并在 bullets/evidence 标明”未证实/需公告验证” |
| 纯行情跳过 | 只有涨停、历史新高、资金流、龙虎榜，缺少业务变化原因 | 不写入，放 `watchlist` 或跳过 |

实践口径：
- concept 页里的 `companies.tier="core"` 且有清晰 `reason`，通常应同步检查是否需要 entity；缺页时优先用 `create_missing: true` 补建。
- `tier="related"` 只有在材料提供公司级硬边际时才新建。
- `tier="peripheral"` 默认不新建。
- 研究报告 full.md 回填时，泛上游材料、泛设备、下游客户/需求侧和生态配套公司可以写入 `entity_exposures.json`，但默认使用 `exposure_only: true`，只沉淀产业链暴露，不追加 `## 边际变化`。
- 若希望完全不触碰 entity 文件，使用 `graph_only: true`：只更新 `entity_exposures.json`、`evidence_index.json` 和 source note 的 `## 仅更新图谱`，不改 frontmatter、不改 `## 相关概念`、不追加 `## 边际变化`。
- 只有订单、合同、中标、客户导入、认证、量产、投产、产能、业绩或明确技术突破等公司级硬边际，才追加 entity delta。
- `chain_layer` 用于给题材雷达分层：`upstream_materials`、`upstream_equipment`、`midstream`、`downstream`、`ecosystem`。
- `evidence_layer` 用于证据分级：研报产业链映射为 `L1`，公告/订单/认证/量产等事实验证为 `L3`，研报中带公司级事实但待验证可写 `L1_L3_candidate`。
- 新建 entity 的 `judgment` 要写明定位和可信度，例如“核心受益，订单需公告验证”“新增合同明确，执行进度待跟踪”。
- 缺页公司如果只是题材核心名单、但原文没有公司级硬边际，不进入 `updates[]`，只进入 `watchlist`；不要为了补全概念页 tickers 而新建 entity。

### must_write 判定

满足以下任一条件才进入 `updates[]`：

- 公司级订单、合同、产能、财报、客户导入、产品发布、技术突破、公告或明确项目进展。
- 已有 entity 的核心逻辑发生变化，新增信息会改变跟踪判断。
- 缺页公司同时满足“核心标的 + 公司级硬边际”，才允许 `create_missing: true`。

以下情况默认不进入 `updates[]`：

- 只在“关注/市场挖掘/相关标的/核心名单”中出现。
- 只有题材映射，没有订单、客户、产品、技术或财务事实。
- 线索需要核实且公司页不存在。

## 写入

同一篇材料只执行一次写入；`updates` 只包含本 source 的 `must_write` 实体更新和允许新建项。写 JSON 到临时文件再执行（不使用 heredoc）：

```python
# /tmp/entity_delta_payload.py
import json, subprocess

payload = {
    "source_name": "0520早知道",
    "source_date": "2026-05-20",
    "updates": []
}

with open('/tmp/entity_delta_payload.json', 'w') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

result = subprocess.run(
    ['python3', '/Users/lbq/Desktop/c c/金融/skills/entity-delta-ingest/scripts/entity_delta_writer.py'],
    input=json.dumps(payload, ensure_ascii=False),
    capture_output=True, text=True
)
print(result.stdout)
```

```bash
python3 /tmp/entity_delta_payload.py
```

脚本会：

1. 匹配 `wiki/entities/{公司}.md`，兼容股票代码反查。
2. 更新 frontmatter：`updated`、`revision`、`sources`、`tickers`，wikilink 一律写成字符串数组。
3. 若 `create_missing=true`，新建 entity 时参考 `wiki/entity-template.md` 的核心结构：frontmatter 含 `aliases/entity_type/markets/raw_sources`，正文含 `速览`、`在赛道中的角色`、`关键数据`、`业务与产品`、`风险与反证`、`待核实问题`。
4. 在正文追加：
   ```md
   ## 边际变化

   ### 2026-05-20｜0520早知道

   **800G光模块用PCB稳定供货**

   - ...
   - 相关概念：[[PCB]] · [[AI算力]]
   - 原文依据：...
   ```
5. 自动维护 `## 相关概念`，把本次 delta 的 `concepts` 合并进去。
6. 同步更新 `wiki/relations/entity_exposures.json` 和 `evidence_index.json`，把公司-概念-产业链角色沉淀成底层数据库。
7. 若单条 update 使用 `graph_only: true`，跳过实体页写入，只更新图谱和证据索引，并在 source note 记录 `## 仅更新图谱`。
8. 创建 `wiki/sources/{source_name}.md`，记录来源文件、日期、更新过的实体和观察列表。
9. 返回 JSON 报告：`updated_entities`、`created_entities`、`graph_only_entities`、`skipped_updates`、`watchlist`、`graph_files`。

## Frontmatter 约束

- `sources` 必须写成字符串数组：`sources: ["[[0520早知道]]"]`。
- 禁止裸 wikilink：`sources: [[0520早知道]]` 会让 YAML 把 `[[` 当成嵌套数组。
- writer 会自动剥掉 `[[...]]` 和 `.md` 后再生成规范 wikilink。

## 质量门槛

写入后必须运行通用 lint 脚本：

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/lib/pdf_ingest_lint.py" "source_name"
```

Lint exit code 0 = 通过，1 = 有问题必须修复。

Lint 检查项（2026-05-28 升级）：
- relations 层：update_type/fact_hardness/evidence_layer/source_quality/chain_layer 组合一致性
- markdown 层：concept page section（broker 源不应写入 `## 边际变化`）、entity annotation（curated_research 必须在高信度研究线索且有注释）
- source note 层：已更新实体/仅更新图谱/观察列表与 entity_exposures 一致，无重复 section
- graph_only：不允许 review_candidate/core/related
- evidence_index：覆盖每个 exposure，包含 fact_hardness/source_quality

补充校验：
- 写入前先判断是否值得进 entity；纯行情、纯名单、缺少原因的内容不要写。
- 写入后对本批次所有目标文件统一检查：`rg -n "\?\（|sources:\s*\[\[" wiki/entities/公司1.md wiki/entities/公司2.md`。
- 写入后检查 source note 中 `## 已更新实体`、`## 新建实体`、`## 观察列表` 是否重复；如重复，人工合并到一个小节。
- 写入后检查 `wiki/relations/entity_exposures.json` 中存在本次公司与相关概念的暴露关系。
- 对图片 PDF，至少保留切块图片路径或 source note，方便回看。

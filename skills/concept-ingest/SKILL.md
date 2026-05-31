---
name: concept-ingest
description: 新概念入库——将研报、文章、会议纪要等文本自动提取为结构化概念页，写入 Obsidian 知识库。仅用于库里尚无对应概念页的全新产业主题/细分工艺/可交易概念。若判断应归入已有概念，或 concept_writer.py 返回 update_needed，不要停止，必须改用 concept-delta-ingest 把新催化、新数据、新标的合并进已有概念页。触发词：concept ingest、概念入库、新概念、提取概念。
---

# Concept Ingest Skill

将非结构化文本（研报、公众号文章、电话会议纪要、公告等）自动转化为 Obsidian 知识库中的结构化概念页。

## 自动分流规则

处理材料时先判断主题类型：

| 判断结果 | 下一步 |
|---|---|
| 库里没有对应概念页，是全新概念 | 使用本 skill，调用 `concept_writer.py` 新建概念页 |
| 库里已有对应概念页，但材料提供了新催化、新数据、新标的、新风险 | 改用 `concept-delta-ingest`，调用 `concept_delta_writer.py` 更新已有概念页 |
| 材料重点是公司边际变化，而不是概念页 | 改用 `entity-delta-ingest` 更新 `entities/` |
| 只有涨跌、榜单、无原因名单 | 不写入，列入 watchlist |

硬规则：如果 `existing_concept` 非空，或 `concept_writer.py` 返回 `status=update_needed`，不得把“手动合并”作为最终结果；必须继续触发 `concept-delta-ingest` 完成已有概念增量写入。

实体分层硬规则：概念入库或概念增量中出现的公司，不要默认全部跳过缺失 entity。若公司是 `tier="core"` 且原文提供明确公告/订单/合同/产能/财报/客户导入/技术突破，应继续触发 `entity-delta-ingest`，在对应 update 上设置 `create_missing: true` 新建 entity；若只是相关名单、外围标的或未证实传闻，则放入 watchlist，不新建。

批处理硬规则：处理单篇材料时，先完成全篇 `ingest-plan`，再调用 writer。不要边读边写、边写边判断；同一篇 source 原则上只允许一次新概念写入批次、一次 concept-delta 批次、一次 entity-delta 批次，最后统一质检。

压缩写入硬规则：`ingest-plan` 必须先做价值分层，默认只写 `must_write`。材料里只被点名、没有新增数据/订单/合同/产能/财报/客户导入/技术突破/明确政策催化的概念或公司，不展开成长段落，放入 `light_note` 或 `watchlist`。不要为了“覆盖所有提到的名字”牺牲处理速度和知识库密度。

## 单篇 ingest-plan

每读取一篇材料后，先在本会话内整理以下计划，再开始写入：

```json
{
  "source_name": "20260522 市场逻辑精选",
  "source_date": "2026-05-22",
  "new_concepts": [
    {"concept": "全新概念", "reason": "库中无同名/近义概念，且原文提供完整产业逻辑"}
  ],
  "concept_delta_candidates": [
    {"concept": "已有概念", "priority": "must_write|light_note|watchlist", "reason": "新增催化/数据/标的/风险"}
  ],
  "entity_update_candidates": [
    {"company": "已有实体", "priority": "must_write|light_note|watchlist", "reason": "已有 entity 且有公司级边际变化"}
  ],
  "entity_create_candidates": [
    {"company": "缺页实体", "priority": "must_write|watchlist", "reason": "核心标的 + 明确订单/合同/产能/财报/客户导入/技术突破"}
  ],
  "light_note": [
    {"name": "轻量点名", "reason": "仅作为产业链名单出现，不展开写入"}
  ],
  "watchlist": [
    {"name": "观察项", "reason": "信息不足、纯名单或缺少公司级硬边际"}
  ]
}
```

优先级口径：

| priority | 写入策略 |
|---|---|
| `must_write` | 进入 writer，写完整增量。仅用于强催化、硬数据、明确订单/产能/财报/技术突破、或真正的新概念。 |
| `light_note` | 不进 writer；只在 source note 或最终汇总中保留一句观察。适合“市场挖掘/关注/点名”的弱信息。 |
| `watchlist` | 不写库；等待后续材料确认。 |

执行顺序固定为：

```
读取单篇 source
  ↓
生成 ingest-plan（只判断，不写库）
  ↓
新概念：逐个调用 concept_writer.py（仅 new_concepts）
  ↓
已有概念：一次调用 concept_delta_writer.py（仅 must_write）
  ↓
实体变化：一次调用 entity_delta_writer.py（仅 must_write）
  ↓
单篇统一质检
  ↓
下一篇 source
```

如果材料只有已有概念或只有 entity 更新，仍要先做轻量分层计划，再进入对应批量写入；不要为了省一步而恢复零散写入。

## 三步流程

```
Step 1: 读取单篇源材料
   ↓
Step 2: 生成 ingest-plan 并提取结构化信息（本会话完成）
   ↓
Step 3: 按计划调用 writer，单篇统一质检
```

## Step 1: 读取源材料

源材料可以是：
- **已有文件**：`sources/` 目录下的研究报告
- **URL**：微信公众号文章等（通过 web-access CDP 读取）
- **粘贴文本**：用户直接粘贴的内容

## Step 2: LLM 提取

从原文中提取以下字段，输出 JSON：

```json
{
  "title": "概念名称（中文，清晰简洁）",

  "is_concept": true,
  "existing_concept": null,
  "existing_source": "已存在的source文件名（不含.md）",

  "definition": "1-2句学术定义",
  "oneliner": "一句话类比，帮助快速理解",
  "core_thesis": "一句话投资结论，回答'为什么现在关注'",
  "key_insights": [
    "边际变化1：发生了什么事，意味着什么",
    "边际变化2：..."
  ],
  "key_data": [
    {"indicator": "全球市场规模", "value": "145.5亿美元", "note": "2025，Precedence Research"},
    {"indicator": "CAGR", "value": "9.21%", "note": "2025-2034"}
  ],
  "mechanism": "核心机制/工作原理/行业本质",
  "supply_chain": "上游：...\n中游：...\n下游：...",
  "supply_chain_layers": {
    "上游": ["核心材料/设备/资源"],
    "中游": ["核心工艺/制造/模组"],
    "下游": ["应用场景/客户/终端"]
  },
  "market_info": "市场规模、增速、渗透率等关键数据",
  "core_logic": "投资逻辑/核心驱动因素",

  "companies": [
    {"name": "公司A", "tier": "core", "role": "上游材料/中游设备/下游应用", "reason": "唯一供应商，市占率40%"},
    {"name": "公司B", "tier": "related", "reason": ""},
    {"name": "公司C", "tier": "peripheral", "reason": ""}
  ],
  "parent_concepts": ["上位概念"],
  "related_concepts": ["已有概念1", "已有概念2"],
  "relationships": {"已有概念1": "子工艺", "已有概念2": "上游支撑"},
  "aliases": ["别名1", "英文缩写"],
  "confidence": "high|medium|low",
  "evidence": "一句短原文依据，便于关系图谱追溯",

  "catalysts": [
    {"time": "2026Q3", "event": "某公司产线投产", "impact": "产能翻倍"}
  ],
  "risks": [
    "风险1：产能扩张超预期→缺口收敛→涨价逻辑软化",
    "风险2：..."
  ],

  "source_name": "来源文件名或文章标题",
  "tags": ["tag1", "tag2", "tag3"]
}
```

### Pipeline 控制字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `is_concept` | bool | `false` 时跳过入库（原文不包含可交易概念） |
| `existing_concept` | string\|null | 如果该内容更适合归入已有概念，填已有概念名 |
| `existing_source` | string\|null | 如果原始 source 文件已存在于 `sources/` 目录，填文件名（不含 `.md`） |

这三个字段互斥优先级：`is_concept=false` > `existing_concept` > `existing_source`

### 公司字段（companies）

兼容两种格式，推荐使用结构化格式：

```json
// 推荐：结构化格式（含产业链角色和逻辑）
[{"name": "天承科技", "tier": "core", "role": "中游材料/电镀药水", "reason": "MSAP电镀药水唯一国产供应商"}]

// 兼容：简单格式（自动按 tier=related 处理）
["天承科技", "鹏鼎控股"]
```

`tier` 可选值：
- `core` — 核心标的，直接受益、弹性最大
- `related` — 受益标的，间接受益（默认值）
- `peripheral` — 边缘标的，弱相关

### 核心结论（core_thesis）

一句话投资结论，回答"为什么现在关注"。区别于 `oneliner`（帮理解概念）和 `core_logic`（帮理解投资逻辑），`core_thesis` 是当下的投资判断。可选，留空则跳过。

### 边际变化（key_insights）

≤5 条核心观点，每条回答"发生了什么变化 + 意味着什么"。这是 concept 页最重要的"为什么现在"维度。可选，留空则跳过。

### 关键数据（key_data）

结构化表格，每项含：
- `indicator` — 指标名
- `value` — 数值
- `note` — 时点/来源/备注

从原文中提取关键量化数据，比 `market_info` 更精炼、更结构化。可选，留空则跳过。

### 催化事件（catalysts）

按时间线排列，每项含：
- `time` — 时间点（如 "2026Q3"、"2026-07"、"近期"）
- `event` — 事件描述
- `impact` — 对行业的影响

### 风险（risks）

字符串数组，每条一个风险点。应同时涵盖行业风险和标的特定风险。可选，留空则跳过。

**提取原则：**
- `title` 用最通用的中文名（如"MSAP（半加成法工艺）"）
- `oneliner` 用生活类比，让非专业读者秒懂
- `companies` 从正文中出现的所有上市公司名
- `related_concepts` 尽量用可能已存在的概念名（方便自动链接）
- `relationships` 为每个关联概念标注关系类型，可选值：
  - `子工艺/子领域` — 新概念是已有概念的下位细分
  - `上游支撑` — 新概念为已有概念提供材料/设备/技术
  - `下游应用` — 新概念是已有概念的应用场景
  - `同场景` — 同一产业链的不同环节
  - `替代竞争` — 技术路线互斥
- 不确定的字段留空，不要编造

### 关系图谱字段

新增 concept 必须同时沉淀为底层关系数据。以下字段会同步写入 `wiki/relations/`：

| 字段 | 说明 |
|---|---|
| `parent_concepts` | 上位概念，如 `先进封装`、`AI算力`、`机器人` |
| `related_concepts` + `relationships` | 与已有概念的关系，类型用 `上游支撑/下游应用/子领域/同场景/替代竞争/相关` |
| `supply_chain_layers` | 结构化上游/中游/下游，供新词分析快速定位产业链 |
| `companies[].role` | 公司所在环节，如 `上游材料`、`中游设备`、`下游应用` |
| `companies[].tier` | 暴露强度：`core/related/peripheral` |
| `evidence` | 支撑本次关系判断的短依据；不要长篇搬运 |
| `confidence` | 置信度：公告/订单/财报为 `high`；研报/新闻为 `medium`；传闻/弱线索为 `low` |

## Step 3: 写入

写入时先将 JSON payload 写到临时文件，再执行脚本（不使用 heredoc）：

```python
# /tmp/concept_ingest_payload.py
import json, subprocess

payload = {
    "title": "概念名称",
    "is_concept": True,
    # ... 其他字段
}

with open('/tmp/concept_payload.json', 'w') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

result = subprocess.run(
    ['python3', '/Users/lbq/Desktop/c c/金融/skills/concept-ingest/scripts/concept_writer.py'],
    input=json.dumps(payload, ensure_ascii=False),
    capture_output=True, text=True
)
print(result.stdout)
```

```bash
python3 /tmp/concept_ingest_payload.py
```

脚本自动完成：
1. **去重**：同名 concept 已存在则跳过
2. **代码匹配**：公司名→A股代码，优先本地映射，未命中调 iFinD 兜底
3. **名称反查**：代码→公司名，优先知识库和本次输入，未命中用 akshare A 股代码表兜底
4. **关系定性 + 标的交叉对比**：读每个关联概念的 tickers，计算重合/独有/纯增量
5. **生成文件**：按概念模板写入 `concepts/` 目录，含 `## 概念关系` 交叉对比表
6. **同步关系图谱**：更新 `wiki/relations/concept_graph.json`、`entity_exposures.json`、`aliases.json`、`evidence_index.json`

### 可选环境变量

| 变量 | 默认值 | 用途 |
|------|--------|------|
| `CONCEPT_VAULT` | `~/Desktop/c c/知识库/wiki` | Obsidian vault 根目录 |
| `IFIND_SKILL_DIR` | `~/Desktop/c c/金融/skills/ifind` | iFinD skill 目录 |

### Frontmatter 约束

- YAML frontmatter 中的 wikilink 必须作为字符串写入，例如 `sources: ["[[评级日报 0521]]"]`。
- 不要写裸 wikilink，例如 `sources: [[评级日报 0521]]`；YAML 会把 `[[` 当成嵌套数组，导致 Obsidian frontmatter 解析失败。
- `concept_writer.py` 会自动把 `source_name` / `existing_source` 里的外层 `[[...]]` 和 `.md` 剥掉，再生成带引号的 wikilink。

## 输出解读

脚本返回 JSON 报告：
```json
{
  "status": "created" | "duplicate",
  "file": "写入路径",
  "tickers_found": {"公司A": "000001", ...},
  "tickers_missing": ["公司B", ...],
  "concepts_linked": ["PCB", "先进封装"],
  "concepts_not_found": ["感光干膜"],
  "cross_comparison": {
    "PCB": {"关系": "子工艺", "重合": 3, "新独有": 3, "对方独有": 15},
    "先进封装": {"关系": "上游支撑", "重合": 1, "新独有": 5, "对方独有": 10}
  },
  "pure_new_stocks": 2,
  "graph_files": {"concept_graph": ".../wiki/relations/concept_graph.json"}
}
```

- `cross_comparison`：与每个关联概念的标的交叉分析
- `pure_new_stocks`：在所有关联概念中都不存在的纯增量标的数
- `tickers_missing`：需要手动补代码的公司
- `concepts_not_found`：知识库中不存在的候选概念
- `graph_files`：本次同步更新的底层关系数据文件

## 关系图谱质量门槛

- 写入后检查 `wiki/relations/concept_graph.json` 中存在本次概念。
- 核心公司必须出现在 `wiki/relations/entity_exposures.json`，且有 `role`、`strength`、`sources`。
- `wiki/relations/evidence_index.json` 只放短证据，不放整段原文。

## 常见情况处理

| 情况 | 处理 |
|------|------|
| 概念已存在 | 不停在手动合并；自动转交 `concept-delta-ingest`，把新催化/数据/标的写入已有概念页 |
| 公司名匹配不到代码 | 先查 iFinD，仍失败则留空，提示用户 |
| 候选概念不存在 | 记录在 `concepts_not_found`，提醒可能需要一并入库 |
| 原文信息不足 | 能提取多少算多少，空字段比编造数据好 |

## 参考

- 概念模板参见 `concepts/PCB.md`、`concepts/CPO.md` 等
- 实体映射参见 `entities/` 目录
- iFinD 查询参见 `skills/ifind/`

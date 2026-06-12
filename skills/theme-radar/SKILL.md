---
name: theme-radar
description: 题材雷达 / 新词雷达——输入一个新名词、新闻事件或题材，可先用 web access 查外部定义/技术拆解，再回到 wiki/relations 的概念图谱、公司暴露和证据索引中寻找关联，生成“新词定义、产业链拆解、相关概念、核心公司分层、证据、信号层缺口、预期差初判”的只读分析报告。用于复刻“新词→上下游关系→核心个股→题材进度”的框架；信号层可先留空位，后续再补。
---

# Theme Radar Skill

把新词或新事件放进现有知识库中定位。它回答：

- 这个词可能属于哪个概念/产业链？
- 上下游和相邻概念有哪些？
- 知识库里已有的相关公司是谁？
- 哪些公司更像核心标的，哪些只是相关？
- 证据来自哪些 source？
- 信号层还有哪些空缺，后续需要补什么？

## 边界

默认只读，不修改 `concepts/`、`entities/` 和 baseline 数据。另一个 IDE 正在跑 `company-baseline-ingest` 时，也可以安全使用本 skill。

新词解释不要求来自私人知识库。对于知识库未命中的新词，agent 应先用 web access 查公开定义、技术背景和产业链位置，再用本地知识库做关联映射。

不要在本 skill 里默认批量抓公告、新闻或研报。web access 只用于轻量定义、技术背景和关键产业资料确认；信号层先从 `wiki/relations/theme_signals.json` 读取，没有数据就输出“待补”。

公告不是题材逻辑的唯一来源。对很新的概念，公告通常不会直接写出完整逻辑，尤其不会写“我司受益于某新理论/新名词”。本 skill 必须区分：

- 公开定义/技术资料/研报：负责解释“是什么、解决什么问题、会传导到哪些环节”。
- 产业链资料/会议纪要/复盘：负责补“为什么现在爆发、哪些细分方向正在被市场理解”。
- baseline / 年报 / 公司资料：负责验证“公司本来做什么、能力栈在哪里、是不是纯正”。
- 公告 / 互动 / 订单 / 送样 / 客户认证：负责验证“逻辑是否进入事实”，不负责凭空生成完整题材框架。
- 盘面和信号层：负责验证“市场是否已经认同”，不直接证明产业逻辑正确。

因此，对“韬定律”这类暂无直接公司公告的新概念，只能输出能力栈映射、代理变量和观察池；不得把辅助概念公司直接升为核心标的。

## 输入

支持：

- 单个新词：`感光干膜`
- 新闻标题/短句：`华为发布飞鳞半导体技术`
- 已有概念：`mSAP`

## 数据源

外部定义层：

- web access：用于新词定义、技术拆解、产业链位置、同义词和上位概念。
- 要优先找可信来源：公司官网/监管披露/交易所互动/权威媒体/产业资料，其次才是自媒体。
- 外部来源只作为“新词解释和检索线索”，不能直接写入 baseline。

本地映射层默认读取：

- `wiki/relations/concept_graph.json`
- `wiki/relations/entity_exposures.json`
- `wiki/relations/aliases.json`
- `wiki/relations/evidence_index.json`
- `wiki/relations/report_contexts.json`
- `wiki/relations/theme_signals.json`
- `wiki/relations/pattern_library.json`
- `wiki/relations/benchmark_maps.json`

wiki 页面层（只读，不回写）：

- `wiki/concepts/*.md`：概念页一句话定锚、定义、核心逻辑/机制、相关概念 → “Wiki 概念知识卡”模块；定锚缺失或为占位垃圾时，回退用概念页定锚。
- `wiki/entities/*.md`：实体页“一句话定位”、“当前判断”、frontmatter `updated`/`revision` → 公司卡补充定位与新鲜度，“雷达速览”里的最近更新/待刷新实体。
- `wiki/synthesis/*.md`：按题材/概念/公司名匹配文件名，抽取核心结论 → “本地合成研究洞察”模块（历史分析快照，仅作认知线索，不升级公司事实）。

报告头部新增“雷达速览”模块：概念命中、公司分层计数、逻辑卡覆盖、概念页覆盖/缺页、合成研究命中、benchmark 命中、实体新鲜度，一眼判断知识库对该题材的覆盖水位。

## 快速运行

## 云端/跨电脑标准入口（新版默认）

云端 agent 使用本 skill 时，必须先确认**金融仓库**和**知识库仓库**都已同步到 `main`。`theme-radar` 的新版能力在金融仓库脚本里，知识库只提供 wiki 数据底座；只拉知识库 `main` 不会更新 `radar.py`。

默认路径可按机器调整，先设置变量再同步：

```bash
export FINANCE_REPO="${FINANCE_REPO:-/Users/a77/Desktop/c c/金融}"
export KNOWLEDGE_REPO="${KNOWLEDGE_REPO:-/Users/a77/Desktop/c c/知识库}"
export KNOWLEDGE_WIKI="${KNOWLEDGE_WIKI:-$KNOWLEDGE_REPO/wiki}"
export TERM="${TERM:-MLCC}"

git -C "$FINANCE_REPO" pull origin main
git -C "$KNOWLEDGE_REPO" pull origin main
python3 "$FINANCE_REPO/skills/theme-radar/scripts/radar.py" --help | grep brief
```

用户要“题材雷达/题材速读/定义+产业链+细分+核心个股”时，默认使用新版 `brief`：

```bash
python3 "$FINANCE_REPO/skills/theme-radar/scripts/radar.py" \
  --term "$TERM" \
  --vault "$KNOWLEDGE_WIKI" \
  --mode brief
```

如用户明确要求写入知识库，再指定 `--out` 到 `wiki/synthesis/`，并按知识库规则提交：

```bash
python3 "$FINANCE_REPO/skills/theme-radar/scripts/radar.py" \
  --term "$TERM" \
  --vault "$KNOWLEDGE_WIKI" \
  --mode brief \
  --out "$KNOWLEDGE_WIKI/synthesis/${TERM}-题材速读-$(date +%Y%m%d).md"
```

需要完整验证清单、护栏、催化和公司卡时，才改用 `--mode deep-dive` 或 `--mode front-map`。不要在新版日常速读场景继续使用默认 `--mode radar`。

## 三模式分工（与知识库十模块体系各司其职）

| 模式 | 定位 | 时长 | 适用场景 | 核心输出 |
|---|---|---|---|---|
| `brief` | 单题材速览 | ≤5 min | 盘前/盘中快速定位新词、晨汇方向 | 定义 → 产业链 → 工艺/材料细分扫描 → 各细分核心个股 |
| `front-map` | 单题材信息地图 | ≤10 min | 值不值得展开的中间判断 | 在 brief 基础上加雷达速览、公司分层地图、海外对标、synthesis 洞察 |
| `deep-dive` | 单题材深研 | ≤20 min | 盘后/周末尽调、决策上车前 | 专注产业维：需求传导、共振分层、个股逻辑卡、验证清单、操作建议 |

**与知识库十模块体系的分工**（不重叠、不重复实现）：

- 知识库模块4（扫描表）= 全库工艺/材料级横向扫描，每行一个方向、一句话定锚
- 知识库模块7（发酵复盘）= 单题材**时间维**复盘：怎么走到今天、认同度演变、关键时间节点
- 知识库模块8（横迁）= 拿一个参照模式当标尺，扫全部主题排发酵进度
- front-map/deep-dive = 单题材**产业维**深拆：产业链全景、公司能力栈、验证清单；时间维链接模块7，不重复实现

front-map 的细分方向扫描已归 brief 模式（避免与 brief 三、工艺与材料细分扫描重叠）。deep-dive 的认同度时间线、进度横向对比已归知识库模块7（避免与发酵复盘重叠），deep-dive 保留催化日历（产品维）并注明链接。

## 六模式提示词词表（统一触发口径）

用户说出下列提示词时，agent 直接路由到对应模式，不要追问：

| 模式名 | 提示词（任一命中即触发） | 标准入口 |
|---|---|---|
| `brief` | 速览X / 快查X / X是什么 / 题材速读X / 晨汇方向X | `radar.py --term X --vault <知识库>/wiki --mode brief` |
| `front-map` | X信息地图 / X值不值得展开 / X全景图 | `radar.py --term X --vault <知识库>/wiki --mode front-map` |
| `deep-dive` | 深研X / 尽调X / 深拆X / X验证清单 | `radar.py --term X --vault <知识库>/wiki --mode deep-dive` |
| `scan`（知识库模块4） | 扫描表 / 全库扫描 / 工艺材料扫描 | 知识库 `skills/theme-radar-reports/scripts/generate_scan_table.py` |
| `replay`（知识库模块7） | X发酵复盘 / X怎么走到今天 / X时间线 | 知识库 `skills/theme-radar-reports/scripts/generate_fermentation_report.py X` |
| `migrate`（知识库模块8） | 拿X当标尺 / 横迁 / 找X的同类 | 知识库 `skills/theme-radar-reports/scripts/generate_migration_scan.py --pattern X` |

路由原则：带具体题材词 X 且问产业维（是什么/谁受益/怎么验证）→ brief/front-map/deep-dive 三档按深度选；问时间维（怎么发酵的）→ replay；不带题材词、要全库视角 → scan；要类比/找下一个 → migrate。

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜"
```

题材速读（高可读性，用户日常首选）：

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/theme-radar/scripts/radar.py" \
  --term "光刻胶" \
  --mode brief
```

`--mode brief` 只输出四个模块，结构固定、可读性优先：

1. `## 一、题材定义`：一句话定锚（优先主概念 wiki 页）+ 核心逻辑 + 相关概念定锚。
2. `## 二、产业链上下游`：产业链树状图 + 按 下游/中游/上游材料/上游设备/配套 分层列出环节、公司和看点。
3. `## 三、工艺与材料细分扫描`：每个细颗粒对象一组（名称｜位置 / 逻辑 / 代表公司），不用宽表。
4. `## 四、各细分核心个股`：按细分方向分组的公司表（公司/分层/wiki 一句话定位），公司集合被前面细分覆盖的重复段自动跳过。

当用户要"题材定义+产业链+细分+核心个股"这种速览需求时，默认用 brief；需要验证清单、护栏、发酵进度等完整拆解时再用 deep-dive / front-map。

带外部定义运行：

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜" \
  --definition "感光干膜是PCB、IC载板等图形转移环节使用的光敏材料，和mSAP/高端PCB制程、线路精细化相关。"
```

写入报告：

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜" \
  --out "/Users/lbq/Desktop/c c/知识库/wiki/synthesis/感光干膜-theme-radar.md"
```

## 输出结构

报告必须包含：

1. `## 雷达结论`
2. `## 外部定义`
3. `## 新词定位`
4. `## 技术模块与环节相关度`
5. `## 相邻概念区分`
6. `## 能力栈与筛选规则`
7. `## 需求驱动与验证`
8. `## 产业链全景`
9. `## 细分方向扫描`
10. `## 发酵进度排序`
11. `## 催化日历与验证清单`
12. `## 产业链与相关概念`
13. `## 核心公司分层`
14. `## 候选公司线索`
15. `## 证据索引`
16. `## 信号层`
17. `## 预期差初判`
18. `## 待补数据`

## 推荐工作流

1. 如果新词不是知识库里的成熟概念，先用 web access 查定义、同义词、上位概念和产业链位置。
2. 先做“产业翻译”：把新词翻译成需求场景、技术模块、上下游环节、能力栈和代理变量，不急着找股票。
3. 把外部资料抽成 `new_term_context` 结构化 JSON；来不及时才用 `--definition` 传 1-3 句摘要。
4. 脚本用 `term + definition + aliases + parent_concepts + chain_position + related_terms` 辅助匹配本地 concept graph；`upstream/midstream/downstream` 只展示，不直接扩公司，避免把原料泛词误配成股票。
5. 公司映射优先使用 `segment_scores` 中 `high/medium_high` 环节的 `mapped_concepts`；`medium/low` 只进入观察和风险提示。
6. 对截图式题材雷达，必须补 `direction_scan` 和 `progress_ranking`：前者负责从题材向下扫细分方向，后者负责横向比较发酵阶段。
7. 对每家公司做证据分级：没有直接产品/客户/订单/公告证据时，只能进入观察池或 Tier 3，不能进入核心。
8. 报告必须区分“外部定义”“产业翻译”“环节相关度”“细分方向扫描”“发酵进度”“公司验证”和“本地知识库命中”。
9. 如果本地没命中，输出 `concept-ingest` 待办，而不是把外部定义直接当作已入库事实。

## 截图式判断框架

截图式输出的关键不是“多列公司”，而是把一个新词拆成可验证的投资研究链条：

1. **一句话定锚**：这个词到底是什么，不能用同义反复。
2. **需求场景**：为什么现在被关注，下游需求来自哪里。
3. **产业链全景**：下游需求 -> 中游工艺/制造 -> 上游材料/设备。
4. **细分方向扫描**：把大题材拆成多个可跟踪方向，不把整个板块一起拉进来。
5. **发酵进度排序**：判断每个方向处在暗流期、萌芽期、第一轮、催化共振还是一致认同。
6. **公司证据分级**：区分核心、观察、泛化和剔除。
7. **验证清单**：把逻辑变成后续能查的事实，比如订单、送样、涨价、客户认证、产能、收入占比。
8. **反证机制**：明确哪些公司/环节只是概念沾边，哪些证据会推翻当前假设。

## 证据层级

所有结论必须标注来自哪一层证据。不同层证据回答不同问题，不能混用：

| 层级 | 数据类型 | 主要回答 | 不能做什么 |
|---|---|---|---|
| L0 外部定义 | 官网、技术资料、论文、百科、权威媒体 | 新词是什么 | 不能直接推出核心公司 |
| L1 产业翻译 | 研报、产业文章、会议纪要、复盘、供应链资料 | 传导到哪些环节 | 不能直接证明公司受益 |
| L2 baseline | 年报、主营、产品、客户、产能、iFinD基础资料 | 公司有没有能力栈 | 不能证明短期催化已经发生 |
| L3 事实验证 | 公告、互动易、订单、送样、认证、量产、涨价 | 逻辑是否进入事实 | 单条公告不能替代产业链判断 |
| L4 市场信号 | 复盘提及、涨停、成交额、相对强弱、卖方覆盖 | 市场是否开始认同 | 不能单独证明产业逻辑正确 |

输出时要避免“证据错位”：

- 只有 L0/L1：可以做产业链映射和观察池，不能给核心股结论。
- 有 L2 但无 L3：可以列候选公司，标为“能力栈匹配，待事实验证”。
- 有 L2+L3：可以进入 Tier 2 或重点跟踪。
- 有 L2+L3+L4：才可以考虑 Tier 1 / 催化共振。
- 只有 L4：只能写“盘面异动待解释”，不能倒推产业逻辑。

## 新概念早期处理

适用于“韬定律”这类刚出现、公司还没有直接公告的新概念。

必须先生成 `proxy_variables`，即代理变量：

- 如果本质是芯片设计范式：看 EDA、IP、验证工具、架构设计、编译器。
- 如果本质是算力效率：看 AI 芯片、服务器、昇腾生态、模型/算子优化。
- 如果本质是互连瓶颈：看 Chiplet、先进封装、HBM、高速互连、CPO。
- 如果本质是制造约束：看半导体设备、材料、良率控制、先进制程配套。
- 如果本质是材料/工艺变化：看材料、设备、产线、客户认证和量产良率。

早期输出规则：

- 明确写“暂无直接公司公告/订单验证”。
- 公司只能分为“能力栈候选”“代理变量候选”“泛化剔除”，不能直接写核心受益。
- 最高只给 Tier 3，除非已有公司产品/客户/订单/公告证据。
- 必须列出下一步验证清单，告诉用户后续要补什么证据才能升级。
- 如果本地知识库缺少相关 concept/entity，写入待办，不现场编造。

## 从资料自动生成上下文草稿

当用户给一段新闻、公告、复盘、研报摘录时，先用 `build_context.py` 生成可复核草稿：

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/theme-radar/scripts/build_context.py" \
  --term "mSAP" \
  --input "/path/to/raw-notes.txt" \
  --out "/Users/lbq/Desktop/c c/知识库/wiki/raw/theme-radar/mSAP-context-draft.json"
```

草稿会尝试抽：

- `demand_scenarios`：需求场景、逻辑、工艺要求。
- `industry_chain_map`：下游需求、中游工艺/制造、上游材料、上游设备。
- `direction_scan`：工艺/材料/设备/应用细分方向扫描。
- `progress_ranking`：发酵阶段、认知层级、证据等级和优先级。
- `catalyst_calendar`：时间、事件、观察项。
- `validation_checklist`：后续验证事项。
- `extraction_quality`：区分原文支撑、规则推断和缺失字段。

注意：`build_context.py` 是规则抽取草稿，不是最终研究结论。agent 必须复核、补充、删噪后再交给 `radar.py`。

## 外部新词画像 Schema

web access 搜到资料后，先抽成这个结构。字段缺失可以留空，不要编造。

```json
{
  "term": "感光干膜",
  "definition": "用于PCB、IC载板等图形转移环节的光敏材料。",
  "aliases": ["干膜光刻胶", "dry film photoresist"],
  "english_terms": ["dry film photoresist", "DFR"],
  "parent_concepts": ["PCB", "IC载板", "半导体材料"],
  "chain_position": ["上游材料", "图形转移材料"],
  "related_terms": ["mSAP", "ABF载板", "高端PCB", "线路精细化"],
  "problem_solved": "高端PCB线路精细化后，传统图形转移材料性能要求提升。",
  "technical_modules": ["图形转移", "曝光显影", "精细线路制造"],
  "required_capabilities": ["高端电子化学品", "PCB材料认证", "IC载板材料认证"],
  "adjacent_concepts": [
    {
      "name": "湿膜光刻胶",
      "difference": "干膜以预制薄膜形态贴附使用，湿膜以液态涂布。"
    }
  ],
  "capability_stack": ["配方能力", "涂布能力", "洁净生产", "客户认证", "批量稳定供货"],
  "demand_drivers": ["mSAP渗透率提升", "线路精细化", "国产替代"],
  "company_screening_rules": ["主营或明确布局感光干膜", "具备PCB/IC载板客户认证", "有量产或送样证据"],
  "company_exclusion_rules": ["只做PCB下游制造但无材料业务", "只因半导体材料标签相关"],
  "evidence_requirements": ["产品/业务明确提到感光干膜", "客户验证、订单、量产、价格信号至少一项"],
  "evidence_stack": {
    "external_definition": ["来源摘要"],
    "industry_translation": ["需求场景/技术模块/传导路径"],
    "baseline_validation": ["主营、产品、客户、产能、能力栈"],
    "fact_validation": ["公告、订单、送样、认证、量产、涨价"],
    "market_signal": ["复盘提及、盘面强度、卖方覆盖"]
  },
  "proxy_variables": ["EDA", "先进封装", "高速互连"],
  "company_evidence_tiers": [
    {
      "company": "候选公司",
      "tier": "Tier 3",
      "basis": "能力栈匹配，暂无直接公告验证",
      "matched_layer": ["baseline_validation"],
      "missing_validation": ["订单", "客户认证", "收入占比"]
    }
  ],
  "segment_scores": [
    {
      "segment": "高端感光材料",
      "relevance": "high",
      "mapped_concepts": ["光刻胶", "半导体材料"],
      "reason": "新词本体就是材料环节。"
    },
    {
      "segment": "PCB/IC载板制造",
      "relevance": "medium",
      "mapped_concepts": ["PCB", "ABF载板"],
      "reason": "属于下游需求，不宜直接判核心。"
    }
  ],
  "direction_scan": [
    {
      "direction": "感光干膜",
      "sector": "PCB材料",
      "prosperity": "mSAP扩散带动高端干膜需求，量价弹性可能提升。",
      "mention_frequency": "低频",
      "recognition_level": "L1-L2",
      "classification": "布局",
      "core_catalyst": "mSAP产线扩张 -> 干膜需求提升",
      "mapped_concepts": ["光刻胶", "半导体材料"],
      "candidate_companies": ["福斯特", "容大感光"]
    }
  ],
  "demand_scenarios": [
    {
      "scenario": "1.6T光模块",
      "logic": "速率提升推动PCB线宽/线距和高频材料要求提升。",
      "process_requirement": "线宽25±5μm，高层数，高密度",
      "evidence": ["资料原句或来源摘要"]
    }
  ],
  "industry_chain_map": {
    "downstream": [{"name": "1.6T光模块", "evidence_type": "source"}],
    "midstream": [{"name": "mSAP半加成法", "evidence_type": "source"}],
    "upstream_materials": [{"name": "感光干膜", "evidence_type": "source"}],
    "upstream_equipment": []
  },
  "progress_ranking": [
    {
      "direction": "感光干膜",
      "stage": "萌芽期",
      "recognition_level": "L1-L2",
      "evidence_level": "Tier 2",
      "progress_score": 65,
      "key_signal": "mSAP扩产预期开始向材料端扩散",
      "next_validation": "高端干膜订单、客户认证、价格信号",
      "priority": "重点跟踪"
    }
  ],
  "catalyst_calendar": [
    {
      "time": "6月",
      "event": "Rubin试产后mSAP需求确认",
      "watch_item": "订单、客户认证、材料涨价"
    }
  ],
  "validation_checklist": [
    {
      "item": "高端干膜是否进入头部PCB客户",
      "why": "验证材料端是否从逻辑进入订单",
      "status": "待验证"
    }
  ],
  "extraction_quality": {
    "mode": "rule_draft",
    "source_backed_items": 8,
    "inferred_items": 3,
    "missing_fields": [],
    "review_required": true
  },
  "excluded_broad_concepts": ["泛PCB", "普通电子材料"],
  "upstream": ["光敏树脂", "单体", "光引发剂", "PET基膜"],
  "midstream": ["感光干膜制造", "涂布", "曝光显影"],
  "downstream": ["PCB", "IC载板", "先进封装"],
  "core_benefit_links": ["mSAP渗透率提升带动高端干膜需求", "线路精细化提升材料性能要求"],
  "bottlenecks": ["高端产品进口依赖", "客户认证周期长"],
  "verification_nodes": ["价格信号", "客户验证", "量产订单", "国产替代份额提升"],
  "candidate_companies": ["福斯特", "容大感光"],
  "source_urls": ["https://example.com"],
  "confidence": "medium"
}
```

### 需要了解的维度

用于匹配知识库的硬字段：

- `definition`：一句话定义，说明它是什么。
- `aliases` / `english_terms`：同义词、英文名、缩写，解决检索命中问题。
- `parent_concepts`：上位概念，比如 PCB、先进封装、半导体材料。
- `chain_position`：产业链位置，比如上游材料、设备、制造、封测、应用。
- `related_terms`：相关技术/制程/材料，用来连到已有概念图谱。
- `problem_solved`：这个新词解决的产业/技术问题。
- `technical_modules`：把新词拆成技术模块，避免直接从大概念拉股票。
- `required_capabilities`：实现该技术所需能力，比如 EDA、SoC设计、先进封装、材料认证。
- `adjacent_concepts`：相邻概念区分，比如 ODM/OEM/EMS/JDM，避免混淆。
- `capability_stack`：公司要被判定为核心标的所需能力栈。
- `demand_drivers`：为什么现在可能被关注，需求由什么驱动。
- `company_screening_rules`：进入核心/观察池的筛选条件。
- `company_exclusion_rules`：必须剔除的伪相关公司类型。
- `evidence_requirements`：公司从线索升级为核心所需证据。
- `evidence_stack`：证据分层，说明定义、产业逻辑、baseline、公告和市场信号分别来自哪里。
- `proxy_variables`：新概念暂无直接公告时，用哪些代理变量映射到既有知识库。
- `company_evidence_tiers`：公司证据分级，明确 Tier、依据、命中层级和缺失验证。
- `segment_scores`：环节级相关度，只有 `high/medium_high` 默认进入公司映射。
- `direction_scan`：从题材向下扫描工艺/材料/设备/应用等细分方向，判断景气、认知层和催化。
- `demand_scenarios`：解释为什么现在爆发，把需求场景、传导逻辑、工艺要求放在一张表里。
- `industry_chain_map`：把方向放入下游需求、中游工艺/制造、上游材料、上游设备。
- `progress_ranking`：把细分方向按发酵阶段、认知层级、证据等级和优先级排序。
- `catalyst_calendar`：后续时间点和待观察事项。
- `validation_checklist`：把逻辑变成可检查的事实清单。
- `extraction_quality`：标明哪些条目有原文支撑，哪些只是规则推断。
- `excluded_broad_concepts`：需要排除的泛化概念，防止把整个板块都拉出来。
- `upstream` / `midstream` / `downstream`：上下游拆解，默认只展示和辅助人工判断，不直接参与公司分层。
- `report_contexts.json`：由 raw full.md 研究报告回填脚本生成的本地研报产业链上下文，用于补 `产业链全景` 和 `细分方向扫描` 的 L1 产业翻译证据；它不能直接把公司升级为核心。
- `entity_exposures.json` 中的 `chain_layer` / `evidence_layer` / `update_type` 会进入公司分层表，用来区分 `上游材料/设备/中游/下游/生态`、`L1/L3/L1_L3_candidate` 和 `graph_only/exposure_only/delta`。

用于题材判断的软字段：

- `core_benefit_links`：为什么会受益，需求传导路径是什么。
- `bottlenecks`：瓶颈在哪里，是否有供给约束、进口依赖、认证壁垒。
- `verification_nodes`：后续验证点，比如涨价、订单、送样、量产、客户导入。
- `candidate_companies`：外部资料提到的候选公司，只能作为线索，不直接判核心。
- `recognition_level` 约定：`L0` 资料出现但无人关注，`L1` 产业端感知，`L2` 小圈子讨论，`L3` 卖方/复盘覆盖，`L4` 盘面明显反应，`L5` 一致预期。
- `stage` 约定：`暗流期`、`萌芽期`、`第一轮`、`催化共振`、`一致认同`。
- `source_urls`：外部来源，后续做证据回查。
- `confidence`：外部画像置信度，`high/medium/low`。

## 结构化运行

```bash
python3 "/Users/lbq/Desktop/c c/金融/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜" \
  --context-json "/Users/lbq/Desktop/c c/知识库/wiki/raw/theme-radar/感光干膜-context.json"
```

## 公司分层规则

按 `entity_exposures.json` 和 `concept_graph.json` 的暴露强度排序：

- `core`：第一梯队，直接参与核心环节或主营高度相关。
- `related`：第二梯队，业务相关但弹性/纯度待验证。
- `peripheral`：第三梯队，间接受益或概念弱相关。

缺少 baseline 的公司不能硬判为第一梯队；标记为“待 baseline 补证”。

### 证据 Tier

公司最终输出要优先按证据 Tier 收敛，而不是只按概念命中次数：

- `Tier 1`：产业逻辑 + baseline 能力栈 + 公告/订单/客户验证 + 市场信号共振。
- `Tier 2`：产业逻辑 + baseline 能力栈 + 公告/订单/客户验证，但市场尚未充分认同。
- `Tier 3`：产业逻辑 + baseline 能力栈，缺少事实验证；适合观察，不适合写核心。
- `Watch`：只有代理变量或外部线索，等待 baseline / 公告补证。
- `Noise`：只有大概念标签、普通业务或盘面异动，默认剔除。

升级规则：

- 从 `Watch` 升 `Tier 3`：需要 baseline 证明公司确实有对应产品/工艺/客户/产能。
- 从 `Tier 3` 升 `Tier 2`：需要公告、互动、订单、送样、认证、量产、涨价中至少一项事实验证。
- 从 `Tier 2` 升 `Tier 1`：需要市场信号或多源验证共振。
- 没有 L2 baseline 的公司，即使公告或复盘提到，也要先标“待主营/能力栈核验”。
- `graph_only` 或 `exposure_only` 默认只能作为产业链暴露和观察线索；公司升级到 `Tier 2/1` 前，需要 `delta` 或公告/订单/客户/认证/量产等 L3 事实验证。

### 渲染层弱关联过滤（可逆，不改 ground-truth）

`entity_exposures.json` 里约 1/4 的 concept-exposure 是共现图谱/候选噪声（典型：把 CPO 封装公司天孚通信、罗博特科错挂到上游材料 ABF 载板 / 电子级环氧树脂 / 磷 / 硅）。radar **只在渲染层**默认隐藏这类弱关联，不修改 `entity_exposures.json`：

- 判定规则（`is_weak_exposure`）：`strength != core` **且** `confidence == low` 即视为弱关联隐藏。
- `core` 强度、以及中/高置信关联一律保留 → CPO 核心映射（1.6T CPO / CPO 封装 / 光引擎 / 光模块）不受影响。
- 实体名下若全是弱关联，则该实体整体不进公司表。
- `--show-weak-exposures` 关闭过滤、还原全量，便于人工复核或重新校准。

## 信号层占位

信号层字段可以为空，但报告里要显式列出缺口：

- 卖方覆盖
- 价格信号
- 订单 / 验证
- 市场热度
- 产业进度
- 反证 / 风险

后续这些数据由单独信号 ingest 或人工补充，不在本 skill 默认抓取。

## 历史题材类比

`pattern_library.json` 用来放 mSAP、CPO、HBM、玻璃基板等历史题材路径。MVP 只做关键词匹配和人工提示，不做强结论。

如果没有匹配历史模式，报告写“暂无合适类比”，不要编造。

## 质量要求

- 只输出知识库能支持的关系；推断要标“低置信”。
- 每个核心公司尽量附短证据或来源。
- 如果没有匹配到概念，仍然输出框架，并把缺口写入 `## 待补数据`。
- 不把短期催化写入 baseline。

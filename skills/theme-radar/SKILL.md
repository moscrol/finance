---
name: theme-radar
metadata:
  pattern: pipeline
  also: [reviewer, tool-wrapper]
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
export FINANCE_REPO="${FINANCE_REPO:-<金融仓路径>}"
export KNOWLEDGE_REPO="${KNOWLEDGE_REPO:-<知识库路径>}"
export KNOWLEDGE_WIKI="${KNOWLEDGE_WIKI:-$KNOWLEDGE_REPO/wiki}"
export TERM="${TERM:-MLCC}"

git -C "$FINANCE_REPO" pull origin main
git -C "$KNOWLEDGE_REPO" pull origin main
python3 "$FINANCE_REPO/skills/theme-radar/scripts/radar.py" --help | grep brief
```

路径与数据新鲜度（2026-06-12 起）：
- `--vault` 缺省时 radar.py 按 `KB_VAULT` > `CONCEPT_VAULT` > 同级目录自动探测（含 `wiki/relations` 的仓库）解析知识库路径，不再硬编码 Mac 路径。
- 启动时读知识库 `relations/meta.json`（由知识库 writer 自动盖戳）；数据超过 `RELATIONS_MAX_AGE_DAYS`（默认 7 天）未更新或 schema 版本不匹配时，报告头部会输出 ⚠️ 警告。

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
python3 "<金融仓>/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜"
```

题材速读（高可读性，用户日常首选）：

```bash
python3 "<金融仓>/skills/theme-radar/scripts/radar.py" \
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
python3 "<金融仓>/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜" \
  --definition "感光干膜是PCB、IC载板等图形转移环节使用的光敏材料，和mSAP/高端PCB制程、线路精细化相关。"
```

写入报告：

```bash
python3 "<金融仓>/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜" \
  --out "<知识库>/wiki/synthesis/感光干膜-theme-radar.md"
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

把新词拆成可验证投资研究链条的 8 步「截图式判断框架」（一句话定锚 → 需求场景 → 产业链全景 → 细分方向扫描 → 发酵进度排序 → 公司证据分级 → 验证清单 → 反证机制）见 `references/judgment-framework.md`。

## 证据层级

证据五层级（L0 外部定义 / L1 产业翻译 / L2 baseline / L3 事实验证 / L4 市场信号）的回答边界与「证据错位」规避规则见 `references/evidence-layers.md`。所有结论必须按该分层标注证据来源，不能跨层倒推。

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

当用户给一段新闻、公告、复盘、研报摘录时，先用 `build_context.py` 生成可复核草稿。该脚本**题材无关**：方向/公司骨架取自知识库（`<vault>/relations/concept_graph.json` + `entity_exposures.json`），证据层（定义/提及频率/催化/验证）取自原文，因此 CPO、硅光、固态电池等任何题材都能用，不再写死 PCB/mSAP。

```bash
python3 "<金融仓>/skills/theme-radar/scripts/build_context.py" \
  --term "CPO" \
  --input "/path/to/raw-notes.txt" \
  --vault "<知识库>/wiki" \
  --out "/path/to/CPO-supplement-pool.json"
```

输出即 `radar.py` 直接消费的 **`theme_supplement_pool`** schema，可直接喂给渲染器：

```bash
python3 scripts/radar.py --term "CPO" --vault "<vault>" \
  --mode deep-dive --theme-supplement-pool "/path/to/CPO-supplement-pool.json"
```

草稿包含字段：

- `theme` / `term`：题材名（`theme` 用于与 radar 的题材兼容校验）。
- `definition_profile`：原文中的定义句（无定义句则留空，由 radar 回退到知识库 concept 页）。
- `demand_scenarios`：下游需求场景（取自 concept 的 `supply_chain.downstream`）+ 代表公司。
- `material_process_scan`：细分方向扫描（取自 concept 的 `related_concepts`/`supply_chain.midstream`），每行含 `name/major_track/chain_position/cognition_level/classification(发酵|布局)/daily_review_frequency/representative_entities`。radar 据此渲染「细分方向扫描」+「方向池进度」。
- `catalyst_calendar`：时间窗口 + 事件，并按事实硬度标 `event_type`（hard/soft/信号）。
- `validation_items`：后续验证事项，标 `validation_type`（hard_fact/soft_projection）。
- `recognition_timeline` / `progress_ruler` / `action_plan`：**故意留空**——认知演变时间线、横向对比标尺、操作建议属高确信输出，规则层不臆造，由 agent 复核后补。
- `extraction_quality`：是否命中知识库 concept、原文支撑 vs 规则推断、缺失字段。

注意：`build_context.py` 是规则抽取草稿，不是最终研究结论。agent 必须复核、补充、删噪后再交给 `radar.py`；其中事实硬度（hard/soft）标注用于辅助分层，不做硬过滤，过滤由 agent 复核时决定。

## 外部新词画像 Schema

web access 搜到资料后先抽成的「外部新词画像」结构化 schema（完整 JSON 模板 + 硬字段/软字段逐项说明）见 `references/external-term-profile.md`。抽取前加载该文件，字段缺失留空、不要编造。

## 结构化运行

```bash
python3 "<金融仓>/skills/theme-radar/scripts/radar.py" \
  --term "感光干膜" \
  --context-json "<知识库>/wiki/raw/theme-radar/感光干膜-context.json"
```

## 公司分层规则

公司分层（core / related / peripheral）+ 证据 Tier（Tier1/2/3/Watch/Noise）升级规则 + 渲染层弱关联过滤口径见 `references/company-tiering-rubric.md`。输出公司分层前按该口径收敛，优先按证据 Tier 而非概念命中次数排序。

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

---
name: opinion-cross
metadata:
  pattern: pipeline
  also: [reviewer]
description: "把已筛过的卖方观点/产业消息流提纯成三重共振机会卡片：事实硬度分层、多空分歧、三维交叉排 Tier。用户粘贴卖方观点并要提纯/排 Tier 时用，不是扫全市场公告。问「第几篇研报/首覆/扎堆」用知识库 sellside-coverage-cross。"
---

# opinion-cross 观点提纯 → 三重共振机会卡片

## 用途与边界

**输入**：用户已经**人工筛过**的观点流——卖方研报口播、机构观点合集（如「国投硬科技/天风通信/矽电」这类）、产业小作文。**不是**全市场公告，所以不做公告采集/每日全市场编排（那是另一类需求，成本高、噪音大，用户已明确不做）。

**它解决的核心痛点**：观点流里硬证据（订单/入股/合同/官方表态）、软推演（目标价/预期/看好）、情绪噪音（喊单话术）混在一起，且常常多空并存。本 skill 把这坨料**提纯、分层、排序**，让"哪条是真三重共振"一眼可见。

**它不是**最终研究结论——是**可复核草稿**。Tier、硬度、多空都来自原文证据；缺证据就标"待补/仅题材弹性"，规则层不臆造，由 agent 复核盘面维度与硬度后定稿。

## 何时用 / 何时不用

- ✅ 用户贴一段卖方观点/产业消息流，想看"提纯后哪些标的是真机会、排个 Tier"。
- ✅ 想识别一段料里的多空分歧和预期差拐点。
- ❌ 想扫全市场公告找机会 → 不在本 skill 范围（用户已明确不做全市场）。
- ❌ 想做单题材深度产业链拆解 → 用 `theme-radar`（front-map / deep-dive）。

## 用法

```bash
python3 skills/opinion-cross/scripts/opinion_cross.py \
  --term "CPO" \
  --input "/path/to/opinion-stream.txt" \
  --vault "/Users/lbq/Desktop/c c/知识库/wiki" \
  --markdown "/path/to/CPO-opinion-cross.md" \
  --out "/path/to/CPO-opinion-cross.json"
```

> 原文先落库门：`opinion_store.py ingest` 的输入若不在 `wiki/raw/sellside/` 或 `wiki/raw/briefings/` 下，会自动拷贝归档到 `raw/sellside/<报告日期>-<来源>.md` 再入库（输出 `raw_archive` 字段），保证结构化事件永远可回溯原文、可重提纯。

参数：
- `--term`：题材名（可选，用于把标的对齐到该题材的 concept；留空则用标的自身最相关 concept）。
- `--input`：观点流文本文件（必填）。
- `--vault`：知识库 wiki 根目录（默认 `$CONCEPT_VAULT` 或 `~/Desktop/c c/知识库/wiki`）。
- `--markdown` / `--out`：分别落地 Markdown 报告 / 结构化 JSON（均可选）。
- `--format`：`markdown`（默认）/ `json` / `both` 控制 stdout 打印内容。

## 管道（5 步）

```
观点流文本
  → [C1 观点事件抽取]  扫出 KB 内出现的标的（最长优先去重叠），逐标的归集观点句、催化句
  → [C2 事实硬度分层]  每个标的的证据分三档：🟢硬证据 / 🟡软推演(卖方喊单) / 🔴情绪噪音
  → [C3 多空分歧识别]  看多 vs 看空措辞计数 + 预期差拐点（符合预期/辟谣/super expectation）
  → [C4 三维交叉引擎]  复用 theme-radar：逐标的构造 signal/context → signal_dimension_rows → resonance_tier
  → [C5 Tier 卡片报告] 按 Tier1/2/3 分组，每张卡片含 三维交叉表 + 硬度分层 + 催化 + 操作建议
  → 〖复核门〗  定稿/落地最终卡片报告**前**必过 `check_opinion_review.py`（exit-0），见下「复核门」节
```

> C1–C5 是**机器底稿**，最终卡片报告是 agent 复核后的**定稿**。机器底稿与定稿之间隔一道 exit-0 复核门（见下），把「由 agent 复核盘面维度与硬度后定稿」从散文约定硬化成检查点信号门。

**题材无关**：标的清单来自知识库 `relations/entity_exposures.json`，标的→产业方向映射来自 `entity_exposures`（含 `chain_layer/strength/role/fact_hardness`）+ `concept_graph.json`，因此 CPO、硅光、固态电池等任何题材都能跑，不写死。

## 三维交叉与 Tier 判定（复用 theme-radar）

三维交叉（公告/事实 × 产业趋势 × 市场热点）取数口径、Tier1/2/3 判定规则，以及「事实维度只放硬证据/催化、产业信号只走 context」的关键实现细节见 `references/resonance-tier-rubric.md`。

## 事实硬度词典

事实硬度三档词典（🟢 HARD_FACT_KEYS / 🟡 SOFT_KEYS / 🔴 NOISE_KEYS）见 `references/fact-hardness-dictionary.md`。硬度仅用于分层与排序，不做硬过滤。

## 输出 JSON schema（要点）

输出 JSON 的结构（term / divergence / opportunities[] / summary 等要点）见 `references/output-schema.md`，按该 schema 落地结构化结果。

## 已验证（CPO 观点料）

用户贴的 CPO 观点合集（国投硬科技/天风通信/矽电…）跑出：
- 9 个 KB 内标的；**多空分歧**正确识别（看多 11 / 看空 10），预期差拐点抓到「符合预期就是超预期」「英伟达辟谣」。
- **Tier 2 ⭐⭐**：罗博特科（光通信订单 15 亿）、兆驰股份（3.35 亿合同）——有硬证据。
- **Tier 3 ⭐**：新易盛/天孚通信/炬光科技/中际旭创/联特科技/矽电股份（卖方喊单软推演）+ 中芯国际（客户名单提及）。

## 已知局限（交给 agent 复核）

1. **主体指代（anaphora）**：当硬事实句以「公司…」指代主体而未写出标的名时，会归错或漏归。例：矽电的「华为哈勃入股 3%」「与兆驰签 3.35 亿」中，3.35 亿被归到句中出现的"兆驰股份"，矽电因此被低估为 Tier 3。agent 复核时应把这类硬事实归回正确主体。
2. **市场热点维度**：静态文本里通常没有当日盘面，多为"待补"，因此 Tier 上限常停在 2。要升 Tier 1 需接 `limit-advance`/`top-gainers`/`market-overview` 当日盘面信号（后续可做）。
3. **标的识别依赖 KB**：只识别 `entity_exposures` 里已存在的实体；题材或公司未入库则漏识别（先走 disclosure/ingest 补库）。

## 复核门（C5 之后、定稿前必做 · `check_opinion_review.py`）

上面三条「已知局限」过去只是散文约定——机器底稿吐完，agent 凭自觉复核。本门把它硬化成 **exit-0 检查点信号门**（体例同知识库仓 cross-analysis `check_cross_review.py` / sellside `check_opinion_review.py`、disclosure-archive `--apply`）：**机器底稿的每个🟢硬证据标的**都必须有一条复核结论，且必须核过主体指代归属、对市场热点维度表态、给出合法 Tier。门未过（exit 1）禁止定稿最终卡片报告。

```bash
# 1) 跑机器底稿（C1–C5），落 --out JSON
python3 skills/opinion-cross/scripts/opinion_cross.py --term CPO --input stream.txt --out /tmp/oc.json
# 2) 按「已知局限」逐标的复核，填 /tmp/opinion_review.json（--template 出空白模板）
python3 skills/opinion-cross/scripts/check_opinion_review.py --template > /tmp/opinion_review.json
# 3) 过门：exit 0 才放行定稿
python3 skills/opinion-cross/scripts/check_opinion_review.py /tmp/oc.json /tmp/opinion_review.json
```

复核产物 `reviewed[]` 每条对应一个标的：`target`（对齐 `opportunities[].target`）、`final_tier`（Tier 1/2/3/排除，可改判机器 Tier）、`anaphora_checked`（bool，硬证据标的**必须** true = 已核对硬事实归属正确主体，堵局限①主体指代）、`market_heat`（市场热点维度表态，待补也要显式写「待补」= 局限②）、`note`（复核结论）。

门校验（只读，不改 `opinion_cross.py`、不写任何库）：

- 机器命中的**每个🟢硬证据标的**（`hardness.dominant==硬证据` 或 `hardness.hard` 非空）必须在 `reviewed[]` 里有结论，且 `anaphora_checked==true`；纯软推演标的不强制（与机器同档，不抬权）。
- 每条 `reviewed` 的 `final_tier` 合法、`anaphora_checked` 是 bool、`market_heat`/`note` 非空。
- 退出码：0 = 复核充分可定稿；1 = 门控未过；2 = 用法/解析错误。

**诚实的天花板**：门只能保证「每个硬证据标的被有意识地复核过」，**不能**验证 agent 真的纠对了主体指代、或真补全了盘面——同 sellside 观点不可枚举的天花板同源（区别：opinion-cross 命中标的可枚举，故能强制逐标的覆盖）。市场热点维度仍多为「待补」，要真升 Tier 1 需接 `limit-advance`/`top-gainers`/`market-overview` 当日盘面（见局限②）。

## 观点事件库（accumulation layer · `opinion_store.py`）

单篇提纯报告价值有限——单篇研报就是"一个人的一句话"。**意义在于累积**：把每篇研报提纯出的标的展平成结构化「观点事件」行，append 进一个 append-only 的 JSONL 库（类公告库），N 篇研报沉淀进同一库后，跨研报聚合才能看出"同一标的被反复提、硬度在升级"= **认知升温**。

```
卖方研报流 → opinion-cross 提纯 → opinion_store ingest（append+去重）→ 【观点事件库 JSONL】
                                                                              │
              limit-advance/top-gainers 盘面 → （后续）T+N 回溯 ──────────────┘
                                                                              ↓
                                          summary 聚合 → 认知升温视图 / 升 Tier1
```

### 落点（统一一个库，独立于 Obsidian 笔记）

默认库目录 = `<vault>/raw/theme-radar/opinion-store/`（`<vault>` 取 `CONCEPT_VAULT`，未设则用脚本内默认）：

```
<vault>/raw/theme-radar/opinion-store/
├── opinion-events.jsonl   # 事实底账（append-only，唯一真相源）→ 时间线/个股进展/回溯全从这算
├── sources.json           # 机构注册表（别名归一，稳定 source_id）→ 将来算机构胜率的 join 键
└── outcomes.jsonl         # （b 阶段，`build_outcomes.py` 写）盘面 T+N 回溯结果，机构胜率的原料
```

为什么放这：`wiki/raw/` 是机器数据区（manifest/baseline/theme-radar context 都在此），Obsidian 只把 `.md` 当笔记，`.jsonl/.json` 不进笔记/双链图谱 → 与笔记零干扰。

### 用法

```bash
# 入库（提纯一篇 → 展平成事件行 → 来源归一 → append + 去重）
# 默认 --store/--sources 自动落在 <vault>/raw/theme-radar/opinion-store/，平时只需给题材/日期/来源
python3 skills/opinion-cross/scripts/opinion_store.py ingest \
  --term CPO --input report.txt --date 2026-06-10 --source "国投硬科技" \
  --vault "<KB>/wiki"

# 跨研报聚合（认知升温视图：同标的被多少篇/天/来源提及、硬度、多空）
python3 skills/opinion-cross/scripts/opinion_store.py summary \
  --store "<KB>/wiki/raw/theme-radar/opinion-store/opinion-events.jsonl" --term CPO

# 列出库内事件
python3 skills/opinion-cross/scripts/opinion_store.py list \
  --store "<KB>/wiki/raw/theme-radar/opinion-store/opinion-events.jsonl" [--target 罗博特科]
```

**来源归一**：`--source "【国投硬科技】"` 与 `--source "国投硬科技"` 归一到同一 `source_id`（注册表 `sources.json` 自动维护别名），保证将来按机构算胜率时 ID 稳定。

### 事件 schema（每行一条，JSONL）

```jsonc
{
  "event_id": "oce-<hash10>",          // = hash(report_date|source|target|硬证据指纹)，去重键
  "schema_version": 1,
  "ingested_at": "2026-06-10", "report_date": "2026-06-10",
  "source": "国投硬科技", "source_id": "src-001", "report_title": "", "term": "CPO",
  "target": "罗博特科", "concept": "1.6T CPO", "chain_layer": "封装设备",
  "kb_strength": "...", "kb_fact_hardness": "research_claim",
  "stance": "看多", "hardness": "硬证据",
  "hard_evidence": ["…订单已超过15个亿…"], "soft_claims": ["…首选…"], "noise": [],
  "catalysts": ["…"], "expectation_gap": ["符合预期就是超预期"],
  "resonance_tier": "Tier 2", "mention_count": 2
}
```

### 去重语义

- **同** `(report_date, source, target, 硬证据指纹)` 重复入库 → 自动跳过（`event_id` 相同）。
- **不同**日期/来源 → 视为新事件。这是有意为之：唯有跨日期/来源累积，才能体现"同一标的被反复提及" = 认知升温。

### 已验证（累积 + 去重 + 来源归一）

- CPO（2026-06-10）入库 9 条；**原样重复入库** → added 0 / skipped 9（去重生效）；
- `--source "【国投硬科技】"` 入库后，再用 `--source "国投硬科技"` → 归一到同一 `src-001`（别名归一生效）；换来源(天风通信→src-002)/换日期 → 视为新事件按日累积；mSAP 入库 12 条 → 同库累积。
- `summary --term CPO`：罗博特科/兆驰股份 跨日/多来源被反复提及 + 有🟢硬证据 → 认知升温候选，与纯卖方喊单标的（无硬证据）拉开层次。

### 落点与边界

- 库是**派生数据文件**（默认 `<vault>/raw/theme-radar/opinion-store/`），**不写** KB 的 concepts/entities/relations，也**不进代码仓**。硬料若要进 KB ground truth，仍走 `disclosure-archive` 的人工审核 `--apply`。
- 这一层只做"累积 + 聚合 + 来源归一"；**盘面回溯**（事件 T+N 拉盘面验证命中率、补市场热点维度、升 Tier1、算机构胜率）见下「b 阶段」——其中**机构胜率**（`build_outcomes.py` + `winrate_rank.py`）与**盘面兑现维**（`pan_realize.py` → `consensus_staging` 加「盘面兑现(b)」列）**均已实现**；单篇 opinion-cross 卡片的升 Tier1 仍待接当日盘面信号。

### 晨汇补漏通道（morning-briefing raw → opinion-store）

知识库仓的晨汇 raw（`raw/MMDD晨汇纪要.md`，对电话会/卖方观点的 AI 总结转写，文件标注日即观点日）与晚间原文观点流结构同类（L3-L4 卖方观点），两者是不同信息源、平级互补：原文流缺的日期用晨汇补，晨汇缺的用原文流覆盖。规则（与知识库仓 `skills/morning-briefing/SKILL.md` Stage 5 可选步骤同源）：

1. **只补缺口**：仅对原文流缺失/偏少的日期从晨汇 raw 补 ingest；已有原文批次的日期不重复灌。
2. **日期归一**：ingest 时 `--date` 用**观点原始日**（以 raw 内容标注的电话会/观点日期为准，多日文件按场次日期分别标注），避免与原文批次错日重复计数。
3. **机构归一**：`--source` 用段落【机构】标头归一（sources.json 别名机制），无标头才用"未名"。
4. **证据分层**：晨汇里公告类硬事实段**不进观点库**（走 disclosure-archive）；只取卖方观点/电话会推荐段。
5. **渠道标记（不降权）**：晨汇来源事件 `report_title` 统一带 `[晨汇转述]` 前缀（用 `--title` 参数，无需改 schema），仅作渠道溯源用。晨汇与原文流是不同信息源，平级互补，无权重高低之分；前缀只用于区分渠道、识别 AI 转述可能的数字失真（见 morning-briefing 经验第 7 条）。
6. **去重抽查**：补完每个日期后抽查同 (date, source) 是否与已有原文事件语义重复；指纹不同但内容同源的记录在 PR 描述里供人工裁决。

```bash
# 晨汇补漏 ingest 示例（观点原始日 = 晨汇日期 - 1）
python3 skills/opinion-cross/scripts/opinion_store.py ingest \
  --input seg.txt --date 2026-05-16 --source "华源证券" \
  --title "[晨汇转述]商业航天电话会" --vault "<KB>/wiki"
```

## 认同度 staging + 时间轴（演化视图层 · `consensus_staging.py`）

`opinion_store` 把事件累积进库、`summary` 给一张静态聚合表；但"同一标的被反复提"到底**走到哪一阶、哪天跳的阶、和别的方向比发酵到什么程度**，静态表看不出。`consensus_staging.py` 是库的**演化视图层**：把每个标的/方向的事件按时间累积，映射到 `theme-radar` 已有的认同度阶梯，回答"认同度演变"。

```
opinion-events.jsonl
  → [按标的/方向分组 + 按报告日累积]
  → [可数信号]  跨天数 / 来源数 / 硬度是否升级(软→硬) / 催化 / 最佳Tier / 多空
  → [映射认同度阶梯·下限语义]  观察池(覆盖不足)· → 萌芽★★ → 第一轮(第一枪)★★★ → 催化共振★★★★ → 一致认同★★★★★
  → stage(下限+覆盖度+事实轨/广度轨+理由+升阶/待补触发) / timeline(逐日跳阶轨迹) / board(跨方向横向对比)
```

### ★ 沉淀层适配（核心设计）

库是 **append-only + 去重**、且**持续回补历史卖方研报** → 任何「当前快照」都是**不完整**的，会随回补单调增长。所以**不能把"数据没补够"误读成"市场没认同"**。三条铁律：

1. **阶段 = 下限语义**：输出的是"已入库证据**至少**支撑到哪一阶"。库 append-only，回补只让某标的的 来源/跨天/硬证据 单调增加 → 阶段**只升不降**，绝不把低覆盖当"市场冷"。
2. **单来源软料不判阶**：仅 1 来源且只有软推演的标的 → 归「观察池·覆盖不足(待回补)」，**不**硬扣暗流/萌芽。出现**事实锚点（🟢硬证据/催化）或多来源广度**才正式上阶梯。
3. **两条轨道分离**：事实硬度轨（robust，1 条硬证据即成立、**不随回补变含义**，是阶梯主锚点）vs 舆情广度轨（回补敏感，几家在喊/跨几天，只作覆盖度修饰、标"随回补上升仅供参考"）。

**认同度阶梯（下限）（镜像 `radar.py` recognition 体系，同一把尺）**：

| 阶段 | ★ | 基分 | 判定（高阶优先；事实锚点优先于广度） |
|---|---|---|---|
| 观察池·覆盖不足 | · | 20 | 仅 1 来源、仅软推演 → 不判阶，待回补 |
| 萌芽 | ★★ | 45 | ≥2 来源 或 ≥2 天的软推演共识（广度轨，回补敏感）|
| 第一轮(第一枪) | ★★★ | 60 | 出现🟢硬证据 / 硬度升级(软→硬) / 催化（**单来源也成立**，硬证据 robust）|
| 催化共振 | ★★★★ | 78 | ≥3 来源跨 ≥2 日共振 + 🟢硬证据 |
| 一致认同 | ★★★★★ | 90 | ≥5 来源跨 ≥3 日 + 🟢硬证据（Tier1 加分；越靠此阶越接近透支）|

> 下限分 = 阶段基分 + min(提及数,10) + 多来源(+5) + 硬证据(+8) + 催化(+3)，封顶 99，与 radar `recognition_score` 同公式。阈值集中放脚本顶部常量，便于调松紧。

**用法**：

```bash
STORE="<KB>/wiki/raw/theme-radar/opinion-store/opinion-events.jsonl"

# 三视图一起出（默认）
python3 skills/opinion-cross/scripts/consensus_staging.py --store "$STORE" --term CPO

# 单标的逐日认同度演变（哪天跳阶、被什么信号推上去）
python3 skills/opinion-cross/scripts/consensus_staging.py --store "$STORE" --view timeline --target 中际旭创

# 跨方向横向对比发酵进度（图1 那块）
python3 skills/opinion-cross/scripts/consensus_staging.py --store "$STORE" --view board

# 参数：--view stage|timeline|board|all  --term/--concept/--since 过滤
#       --hide-watch 隐藏观察池只看已上阶梯  --markdown 落地  --json 结构化
```

**已验证（CPO + 6.8/6.9/6.10 机器人三批库，223 事件）**：
- stage（下限语义生效）：罗博特科/兆驰/工业富联（有🟢硬证据，单来源）→ 第一轮(下限，标"广度待回补")；新易盛（2 来源软推演）→ 萌芽；天孚/中际旭创/炬光/联特/矽电（单点软料）→ **观察池·覆盖不足**，不再被误判暗流。
- timeline：**中际旭创**（全库口径）`06-08 第一轮 → 06-09 催化共振(下限分97，3来源跨2日+硬证据) → 06-10 催化共振`——跨日跳阶轨迹正确。
- board：1.6T CPO/半导体设备/人形机器人 已到催化共振(较充分覆盖)，CPO/半导体材料 第一轮(有限)，单点软料方向归观察池——同尺横向可比，覆盖度一目了然。

**边界**：staging 的**库内信号**轨（来源数/跨天/硬度）一直在；认同度的「市场是否兑现/透支」一维**已接 b（盘面回溯 `outcomes.jsonl`）**——`consensus_staging` 的 stage/board 视图新增「盘面兑现(b)」列，`main` 加 `--outcomes`（默认取 `--store` 同目录 `outcomes.jsonl`，**存在才接**，缺则该列照旧标「待接」），由 `pan_realize.py` 把 T+N 盘后回测聚成 `已兑现持稳/兑现中/冲高透支/未兑现·跑输/待观察`，喂回升阶触发；**一致认同 + 冲高透支 = 透支区**（热点≠机会）。纯派生视图，**只读库不写库**。回补越多，下限越准、观察池越少。

## 桥：观点库 → theme-radar 信号层（`consensus_bridge.py`）

`consensus_staging` 是 CLI 视图；`consensus_bridge.py` 把同一套**下限语义**聚合结果**持久化**进
theme-radar 的 `wiki/relations/theme_signals.json`，让 `radar.py` 里长期「待补」的三块变真数据：
**信号层**（order_signals/industry_progress/sell_side_coverage/market_heat）、**认知演变时间线**
（recognition_timeline）、**多方向发酵进度横向对比**（progress_ruler）+ 方向级**操作建议**（action_plan）。

**聚合口径**：方向(concept)为信号原子单位、**全库聚合**；每个方向归属其**主 term**（事件最多的 term），
term 条目 = 其名下各方向的全库事件并集 → 与 `consensus_staging --view board` 完全一致（避免 term-scoping
把跨 term/跨日的同一方向证据割裂而低估阶段）。`price_signals` 留空待 **b**。

```bash
STORE="<KB>/wiki/raw/theme-radar/opinion-store/opinion-events.jsonl"
SIGNALS="<KB>/wiki/relations/theme_signals.json"

# 预览将写入的 theme 列表（不落盘）
python3 skills/opinion-cross/scripts/consensus_bridge.py --store "$STORE" --theme-signals "$SIGNALS" --dry-run

# 落盘（append-only 友好：只覆盖本桥写的条目 _source==consensus_bridge，保留其它来源 theme；
#       --also-concepts 额外为每个方向单独建条目）
python3 skills/opinion-cross/scripts/consensus_bridge.py --store "$STORE" --theme-signals "$SIGNALS" --also-concepts

# 验证三块不再「待补」
python3 ../theme-radar/scripts/radar.py --term CPO --vault "<KB>/wiki" --mode deep-dive
```

**幂等**：整库重算、事件分区守恒（不重不漏）；剪除上轮本桥写、本轮不再生成的陈旧条目。
**radar 侧**：`radar.py` 在 `load_signal` 后把 theme_signals 里的这三块注入 context（不覆盖
`--theme-supplement-pool` 已提供的同名数据），故 plain `--term X` 即可渲染。

## b 阶段：T+N 盘后回测 + 机构胜率（已实现）

把 opinion-events.jsonl 的「看多」事件按 `source_id` 聚成**机构胜率榜**，回答「哪个卖方机构胜率更高」。
行情只用免费公开接口（新浪 suggest 名称→代码 + 腾讯前复权日线 + 指数基准），**不依赖** eastmoney/iFinD/duckdb/飞书凭证。

- `price_lib.py`：`name2code`（新浪 suggest，精确名匹配）/ `qfq_daily`（腾讯前复权）/ `index_daily`（指数基准）/ `fwd_metrics`（T+3/5/7/10 收益 + 区间最高收益 + 峰值天数 + 峰值后回撤 + 相对基准超额）。范围感知磁盘缓存落仓外 `WINRATE_CACHE`（默认 `~/kb_work/winrate_cache`，不进 git）。
- `build_outcomes.py`：筛「看多」且非 `[晨汇转述]` → 解析代码 → 抓前复权价 → 算指标 → 写 `outcomes.jsonl`。进场 = 报告日**次日开盘**；窗口不完整的事件标 `*_complete=false`。
- `winrate_rank.py`：join `sources.json` 聚合机构胜率。**主口径 = T+N 相对沪深300 超额收益 > 0**（默认 T+5），同时给绝对收益口径；只排**有效看多 ≥ N 次**（默认 5）的机构，1~2 次样本视为噪音不排。
- `refresh_winrate.py`：**一键刷新** = `build_outcomes` → `winrate_rank`（默认 T+5+T+10）。报告写仓外 `--report-dir`（默认 `~/kb_work/winrate/winrate_T{N}_{date}.md`，不提交）。
- `render_winrate_html.py`：**胜率榜可视化**。复用 `winrate_rank.aggregate_winrate` 一次算 T+3/5/7/10 四窗内联进自包含暗色 HTML（对齐复盘/策略页风格），前端切换窗口、点表头排序、画「超额胜率柱状图」+「均超额 vs 均回撤 风险收益散点」。默认输出 `复盘/winrate/winrate-<date>.html`（生成物，零依赖、双击即开、不提交）。

```bash
# 一键刷新（补完数据后跑这一条即可；日期自动取到今天）
python3 skills/opinion-cross/scripts/refresh_winrate.py --vault "<KB>/wiki"

# 或分步：1) 回测 → outcomes.jsonl  2) 出榜（--window 10 看 T+10；--report 出 md）
python3 skills/opinion-cross/scripts/build_outcomes.py --vault "<KB>/wiki"
python3 skills/opinion-cross/scripts/winrate_rank.py --vault "<KB>/wiki" --report /tmp/winrate.md

# 出可视化 HTML（双击即开；默认 复盘/winrate/winrate-<date>.html）
python3 skills/opinion-cross/scripts/render_winrate_html.py --vault "<KB>/wiki"
```

**迭代机制**：胜率榜是从 `opinion-events.jsonl` 台账**重算**出的派生视图（非手改、无漂移）。补研报/晨汇 → 入库 append → 重跑 `refresh_winrate.py`。`build_outcomes.py` 日期默认动态（end=今天、start=最早观点日前7天），价格范围感知缓存只抓新交易日；每次重算两个叠加效应：①新观点进入回测；②此前窗口不足的近期观点随交易日推进自动补全。**晨汇看多默认不计入胜率**（`[晨汇转述]` 通道已剔除，只研报算）。

**口径纪律**（遵守 finance「市场假设验证」红线）：进场次日开盘、超额剥大盘 beta、3/5/7/10 多窗口 + 区间最高/峰值/回撤（不只看末日收盘）、样本门槛过滤噪音、窗口不足不计入该窗口分母。**outcomes.jsonl 是派生数据**，与 opinion-events.jsonl/sources.json 同放 KB `wiki/raw/theme-radar/opinion-store/`，不进代码仓。

## 与其他 skill 的关系

- **复用** `theme-radar`：三维交叉引擎（`signal_dimension_rows`/`resonance_tier`）+ 认同度阶梯（`recognition_score`/stage 体系）+ KB relations（`concept_graph`/`entity_exposures`）。
- **盘面维度（待接）**：`limit-advance` / `top-gainers` / `high-volume-gainers` / `market-overview`。
- **补库（上游）**：标的/题材缺失时用 `disclosure-archive` / `*-ingest` 先补 KB。

## 踩坑 / 迭代总结（持续累积）

### 1. ingest 一手晚间研报误打 `[晨汇转述]` → 整批被踢出机构胜率榜（2026-06-17）

**错误**：ingest 时手动给 `opinion_store.py` 传了 `--title "[晨汇转述]多题材卖方早知道批次(…)"`，把一批**一手晚间卖方研报**打上了「晨汇转述」标签。

**为什么是错的（机制层面）**：
- `[晨汇转述]` 是**功能性保留标签**，不是中性备注：`build_outcomes.py:72`（看多事件 `if "晨汇转述" in (report_title or ""): continue`）和 `winrate_rank.py:115` 口径会**硬剔除** `report_title` 含「晨汇转述」的事件——它的本意是过滤晨会/AI 总结这类二手转写（见「晨汇补漏通道」第 5 条）。把一手研报标成它，等于亲手把整批挡在机构胜率榜 / T+N 回测之外。
- `opinion_store.py:296` `--title` 默认是空串、`:188` 把 `args.title` 原样写进 `report_title`；这个标签**完全是多传的**，不是流程要求。

**第二层错误（来源归位）**：把多家券商揉在一起的料一锅烩成单一来源「卖方观点流汇总」（src-364），没按段落【券商团队】署名归位。即便没标晨汇转述，单一来源桶也无法在机构胜率榜按机构聚合。

**教训 / 规则**：
1. ingest 一手卖方研报，`--title` **留空或填正式标题**，绝不手动写「晨汇转述」（除非确实走晨会/AI 转述通道，见「晨汇补漏通道」第 5 条）。
2. 传任何 `--title` / `--source` 前，先确认它不会命中 `build_outcomes` 的排除过滤器（当前唯一硬过滤词 = 「晨汇转述」）。
3. 多券商料按段落【券商团队】用 `--source` **分别归位**（`resolve_source` 自动并入现有机构桶）；只有原文确无署名才进未署名残桶，**不伪归**。

---
name: opinion-cross
description: 把一段**已筛过的**卖方观点/产业消息流（研报口播、机构观点合集、产业小作文）提纯成「三重共振」机会卡片。逐标的做 事实硬度分层（硬证据/卖方喊单/情绪噪音）+ 多空分歧识别 + 三维交叉（公告事实×产业趋势×市场热点）排 Tier1/2/3，输出带操作建议的卡片报告。底层复用 theme-radar 三维交叉引擎。Use when the user pastes 卖方观点/产业消息流并想要 提纯/分层/排 Tier/三重共振机会卡片，而不是扫全市场公告。
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
```

**题材无关**：标的清单来自知识库 `relations/entity_exposures.json`，标的→产业方向映射来自 `entity_exposures`（含 `chain_layer/strength/role/fact_hardness`）+ `concept_graph.json`，因此 CPO、硅光、固态电池等任何题材都能跑，不写死。

## 三维交叉与 Tier 判定（复用 theme-radar）

脚本 import `theme-radar/scripts/radar.py` 的 `signal_dimension_rows` 与 `resonance_tier`（import 失败时有同契约的本地回退），逐标的量三把尺子：

| 维度 | 取数 | 含义 |
|---|---|---|
| 公告/事实 | 该标的句子里的🟢硬证据 + 催化 | 题材是不是纯叙事？有没有订单/入股/合同/官方表态 |
| 产业趋势 | 标的在 KB 命中的 concept（含 chain_layer/role） | 这条观点能不能映射到知识库里的发酵/布局方向 |
| 市场热点 | 该标的句子里的盘面措辞（涨停/大跌/异动/估值切换） | 市场今天是否在交易它 |

- 三维都硬（≥2 维 Tier1/2）→ **Tier 1 三重共振 ⭐⭐⭐**
- 两维有效 → **Tier 2 双重验证 ⭐⭐**
- 单维 → **Tier 3 观察池 ⭐**

> 关键实现细节：radar 的 `signal_dimension_rows` 会把 `signal["industry_progress"]` 同时计入"公告/事实"和"产业趋势"两维。为避免产业信号污染事实维度（否则纯卖方喊单也会被抬成 Tier 2），本脚本**事实维度只放硬证据/催化，产业信号只走 `context`**，从而让硬证据标的与软推演标的真正分层。

## 事实硬度词典

- 🟢 `HARD_FACT_KEYS`：订单/中标/合同/入股/持股/公告/确收/供货/签署/收购/增资/量产/扩产/投产/送样/定点/验证通过/交付
- 🟡 `SOFT_KEYS`：目标/预期/预计/看好/空间/市值/有望/弹性/或将/假设/首选/首推/推荐/翻倍/对标/中枢
- 🔴 `NOISE_KEYS`：拒绝一惊一乍/悲观者/乐观者/一笑了之/泼冷水/历史总是惊人/静态的/纠结 …

硬度仅用于**分层与排序**，不做硬过滤——过滤由 agent 复核时决定。

## 输出 JSON schema（要点）

```jsonc
{
  "term": "CPO", "theme": "CPO", "concept_matched": true,
  "divergence": { "verdict": "...", "bull_count": 11, "bear_count": 10,
                  "expectation_pivots": ["符合预期就是超预期", "英伟达…辟谣…"], "sources": ["国投硬科技", ...] },
  "opportunities": [
    { "target": "罗博特科", "resonance_tier": "Tier 2：双重验证…",
      "kb": { "concept": "1.6T CPO", "chain_layer": "封装设备", "role": "...", "kb_fact_hardness": "research_claim" },
      "hardness": { "dominant": "硬证据", "hard": ["…订单已超过15个亿…"], "soft": ["CPO首选标的…罗博特科"], "noise": [] },
      "stance": { "stance": "看多", "bull": [...], "bear": [...], "expectation_gap": [...] },
      "dimension_rows": [ {"dimension":"公告/事实","signal":"…","tier":"Tier 2"}, ... ],
      "catalysts": ["…"], "action": "双重验证，已有跟踪价值；等第三维补齐再下重手。" }
  ],
  "summary": { "target_count": 9, "tier_counts": {"Tier 2":2,"Tier 3":7}, "hard_evidence_targets": 2 }
}
```

## 已验证（CPO 观点料）

用户贴的 CPO 观点合集（国投硬科技/天风通信/矽电…）跑出：
- 9 个 KB 内标的；**多空分歧**正确识别（看多 11 / 看空 10），预期差拐点抓到「符合预期就是超预期」「英伟达辟谣」。
- **Tier 2 ⭐⭐**：罗博特科（光通信订单 15 亿）、兆驰股份（3.35 亿合同）——有硬证据。
- **Tier 3 ⭐**：新易盛/天孚通信/炬光科技/中际旭创/联特科技/矽电股份（卖方喊单软推演）+ 中芯国际（客户名单提及）。

## 已知局限（交给 agent 复核）

1. **主体指代（anaphora）**：当硬事实句以「公司…」指代主体而未写出标的名时，会归错或漏归。例：矽电的「华为哈勃入股 3%」「与兆驰签 3.35 亿」中，3.35 亿被归到句中出现的"兆驰股份"，矽电因此被低估为 Tier 3。agent 复核时应把这类硬事实归回正确主体。
2. **市场热点维度**：静态文本里通常没有当日盘面，多为"待补"，因此 Tier 上限常停在 2。要升 Tier 1 需接 `limit-advance`/`top-gainers`/`market-overview` 当日盘面信号（后续可做）。
3. **标的识别依赖 KB**：只识别 `entity_exposures` 里已存在的实体；题材或公司未入库则漏识别（先走 disclosure/ingest 补库）。

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
└── outcomes.jsonl         # （b 阶段才写）盘面 T+N 回溯结果，机构胜率的原料
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
- 这一层只做"累积 + 聚合 + 来源归一"；**盘面回溯**（事件 T+N 拉盘面验证命中率、补市场热点维度、升 Tier1、算机构胜率）是下一步 b。

## 认同度 staging + 时间轴（演化视图层 · `consensus_staging.py`）

`opinion_store` 把事件累积进库、`summary` 给一张静态聚合表；但"同一标的被反复提"到底**走到哪一阶、哪天跳的阶、和别的方向比发酵到什么程度**，静态表看不出。`consensus_staging.py` 是库的**演化视图层**：把每个标的/方向的事件按时间累积，映射到 `theme-radar` 已有的认同度阶梯，回答"认同度演变"。

```
opinion-events.jsonl
  → [按标的/方向分组 + 按报告日累积]
  → [可数信号]  跨天数 / 来源数 / 硬度是否升级(软→硬) / 催化 / 最佳Tier / 多空
  → [映射认同度阶梯]  暗流★ → 萌芽★★ → 第一轮(第一枪)★★★ → 催化共振★★★★ → 一致认同★★★★★
  → stage(当前阶+认同度分+理由+升阶触发) / timeline(逐日跳阶轨迹) / board(跨方向横向对比)
```

**认同度阶梯（镜像 `radar.py` recognition 体系，同一把尺）**：

| 阶段 | ★ | 基分 | 判定（库内信号，高阶优先） |
|---|---|---|---|
| 暗流 | ★ | 30 | 单来源单日提及，未被关注 |
| 萌芽 | ★★ | 45 | 被反复提及（≥2 次/≥2 来源/≥2 天）但仍是软推演 |
| 第一轮(第一枪) | ★★★ | 60 | 首次出现🟢硬证据 / 硬度升级(软→硬) / 催化且 ≥2 来源印证 |
| 催化共振 | ★★★★ | 78 | ≥3 来源跨 ≥2 日共振 + 🟢硬证据 |
| 一致认同 | ★★★★★ | 90 | ≥5 来源跨 ≥3 日 + 🟢硬证据（Tier1 加分；越靠此阶越接近透支） |

> 认同度分 = 阶段基分 + min(提及数,10) + 多来源(+5) + 硬证据(+8) + 催化(+3)，封顶 99，与 radar `recognition_score` 同公式。阈值（共振/一致的来源·天数门槛）集中放脚本顶部常量，便于调松紧。

**用法**：

```bash
STORE="<KB>/wiki/raw/theme-radar/opinion-store/opinion-events.jsonl"

# 三视图一起出（默认）
python3 skills/opinion-cross/scripts/consensus_staging.py --store "$STORE" --term CPO

# 单标的逐日认同度演变（哪天跳阶、被什么信号推上去）
python3 skills/opinion-cross/scripts/consensus_staging.py --store "$STORE" --view timeline --target 中际旭创

# 跨方向横向对比发酵进度（图1 那块）
python3 skills/opinion-cross/scripts/consensus_staging.py --store "$STORE" --view board

# 参数：--view stage|timeline|board|all  --term/--concept/--since 过滤  --markdown 落地  --json 结构化
```

**已验证（CPO + 6.8/6.9/6.10 机器人三批库，223 事件）**：
- stage：罗博特科/兆驰/工业富联（有🟢硬证据）→ 第一轮；新易盛（2 来源软推演）→ 萌芽；天孚/中际旭创/炬光等单日单源 → 暗流。
- timeline：**中际旭创** `06-08 第一轮 → 06-09 催化共振(认同度97，3来源跨2日+硬证据) → 06-10 催化共振`；**新易盛** `06-08 暗流 → 06-09 萌芽`——跨日跳阶轨迹正确。
- board：1.6T CPO / CPO 方向已到第一轮，半导体设备方向仍暗流——同尺横向可比。

**边界**：当前 staging 只用**库内信号**（广度×跨日×硬度×催化）；认同度的「市场是否兑现/透支」一维要等 **b（盘面回溯 `outcomes.jsonl`）** 接进来，脚本里这一维标「待补」，升阶触发已写明"接盘面兑现"。纯派生视图，**只读库不写库**。

## 与其他 skill 的关系

- **复用** `theme-radar`：三维交叉引擎（`signal_dimension_rows`/`resonance_tier`）+ 认同度阶梯（`recognition_score`/stage 体系）+ KB relations（`concept_graph`/`entity_exposures`）。
- **盘面维度（待接）**：`limit-advance` / `top-gainers` / `high-volume-gainers` / `market-overview`。
- **补库（上游）**：标的/题材缺失时用 `disclosure-archive` / `*-ingest` 先补 KB。

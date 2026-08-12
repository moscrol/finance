# 观点事件库（accumulation layer）

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


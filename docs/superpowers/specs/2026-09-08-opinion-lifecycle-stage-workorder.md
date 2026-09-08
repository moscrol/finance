# 工单 #36：舆论生命周期阶段词表 + 确定性派生器（G-06）

> 日期：2026-09-08
> 上游：`2026-09-05-time-river-gap-roadmap.md` G-06（缺 / 验收 / 依赖 原文）与 §5 待拍板第 3 题；`2026-09-06-personal-research-calibration-endstate-design.md` §2（六轨表：舆论轨）、§4.2（`derivation ∈ {deterministic, frozen_llm}`）；`UBIQUITOUS_LANGUAGE.md`「舆论生命周期」条（09-06 写入：「一条逻辑被多少人、以哪个版本在传播的派生阶段轴」）
> 优先级：**P1**——G-07 三维对照（题材 × 舆论 × 盘面并置）的前置；对外物料「舆论轴有两条线，阶段词表在定」这句话要靠它改口
> 规模：中单（两到三天，两刀）
> 分支：`feat/opinion-lifecycle-stage`
> 依赖：G-02a 舆论轨 provider（已在 main）。**G-04 题材词表统一未成**：错位标记的题材侧按现有模块词 + 模块标记接入，G-04 落地后只换映射表（见 §2.3）
> 并行冲突：本单改 `river.py::_opinion_track / _fundamental_docs`、新建 `opinion_stage.py`、改 `UBIQUITOUS_LANGUAGE.md`；#21 剩余（G-04）也改 `UBIQUITOUS_LANGUAGE.md`（不同小节）与 `labels.py`——**`LABEL_VERSION` 升版两单各升一次，后合入者 rebase**
> 待拍板（未拍前按推荐执行）：路线图 §5 第 3 题「无人问津」段要不要——**推荐 v1 不保留**，用 `unverifiable` 表达负证据缺失（下面按此写）

---

## 0. 一句话

舆论轨今天有两条线：研报**覆盖密度**（近 90 日 / 累计）与观点事件的**认同度下限阶梯**（`consensus_staging`：暗流 → 萌芽 → 第一轮 → 催化共振 → 一致认同，只升不降）。两条线都不是「生命周期」——前者是量，后者按定义**不能退**。三维对照要的是一条能升也能退的阶段轴：一条逻辑从被首次覆盖，到扩散、拥挤、退热或被证伪。本单钦定一套 4 段 + 1 终态词表，全部从**事件**用确定性规则派生（首次覆盖日、覆盖密度及其斜率、观点版本切换、证伪事件），不落状态机、不新增抓取器，能在历史上按 `recorded_at ≤ C` 重算。

---

## 1. 现状 [实测 @ `gitea/main` `8e452e72`]

| 位置 | 现状 | 差距 |
|---|---|---|
| `intelligence/services/river.py:450 _opinion_track` | 每 `(entity, as_of)` 发一个 `label` 对象（`coverage_hits / coverage_metrics`：`count_90d`、`cumulative_count`）+ 每份命中研报一个 `event`；**是唯一有真 `recorded_at`（`created_at`）的轨** | 只有量，没有阶段 |
| `river.py` `_fundamental_docs`（约 `:515–:565`） | 从 `fact_theme_fundamental_doc` 发 `narrative_version` 对象，payload 里写死 `"stage": "unverifiable", "stage_reason": "舆论阶段词表未钦定（roadmap G-06 §5 第 3 题）…"` | 占位符，本单要把它换成派生结果 |
| `river.py:428 coverage_metrics` docstring | 469 份研报里 249 份（53%）挤在 2026-01 一次回填批次；所以主口径是 `count_90d`，累计只作背景 | 派生规则必须按 `recorded_at` 取密度，否则回填批次会伪造一段「扩散」 |
| `skills/opinion-cross/scripts/consensus_staging.py:41–52` | `STAGE_LADDER = ["暗流","萌芽","第一轮","催化共振","一致认同"]`，`decide_stage` 明写「只会沿阶梯上升或不变，绝不下降」；阈值 `TH_RESONANCE_SOURCES=3 / TH_CONSENSUS_SOURCES=5 / TH_CONSENSUS_DAYS=3` | 是**认同度下限**轴，不是生命周期轴；不能表达退热 / 证伪。**保留不删**，词表里注明它是另一条轴 |
| `market_feature_store/schema.sql:738 fact_research_report_catalog` | `report_date / report_type / is_hot / sector_tags / concept_tags / stocks / created_at` | 有「首次覆盖」「密度」的原料 |
| `schema.sql:754 fact_theme_fundamental_doc` | `produced_at / workflow_name / analysis_type / core_theme / verification_points / linked_themes` | 有「观点版本」的原料；**没有结构化的证伪事件**（`verification_points` 是文本） |
| `rg opinion_stage\|OPINION_STAGE intelligence/` | 0 命中 | 缺口成立 |
| `UBIQUITOUS_LANGUAGE.md`「舆论生命周期」 | 只有一句定义，没有段名 | 词表要进来，且与题材八阶段 / 七段不混名 |

---

## 2. 两刀

### 2.1 刀 1｜词表 + 派生器 `intelligence/services/opinion_stage.py`

**词表（钦定，进 `UBIQUITOUS_LANGUAGE.md` 新小节「舆论生命周期」）**：

| 段 | 含义（只说传播，不说涨跌） | 进入条件（确定性，全部从 `recorded_at ≤ C` 的事件算） |
|---|---|---|
| `萌芽` | 刚被少数来源覆盖 | 近 90 日覆盖 `count_90d ∈ [1, TH_RESONANCE_SOURCES)`，且首次覆盖日在 90 日内 |
| `扩散` | 覆盖在增加、来源在变多 | `count_90d ≥ TH_RESONANCE_SOURCES` 且 30 日斜率 `count_90d(T) − count_90d(T−30 交易日) > 0` |
| `拥挤` | 覆盖密度到自身历史高位且来源广 | `count_90d ≥ TH_CONSENSUS_SOURCES` 且 ≥ `TH_CONSENSUS_DAYS` 个不同报告日，且 `count_90d ≥ 该实体自身历史 p80`（历史不足 60 个观测日 → 不判 `拥挤`，停在 `扩散`） |
| `退热` | 从拥挤峰回落 | 曾到过 `拥挤`，且 30 日斜率连续 ≥ 10 个交易日 < 0 |
| `证伪`（终态） | 逻辑被结构化证伪事件否定 | 存在 `object_type="event", kind="falsification"` 的舆论轨对象，`valid_from ≤ T`。**今天河里没有这种对象**：本段定义在、覆盖率报告里会是 0；**不得从价格推断证伪** |
| `unverifiable` | 负证据缺失 | `count_90d = 0` 且无任何事件；**不叫「无人问津」**（推荐答案；用户拍板后可改名） |

规则要点：

- 三个阈值**从 `consensus_staging` 导入**，不复制数字（同一常量两处写是下一个漂移）。`p80` 从实体自身历史算，不用全市场常数——不同题材的覆盖体量差一个量级。
- **无状态**：`derive_stage(events_until_C, as_of) -> StageReadout{stage, reason[], inputs{count_90d, slope_30, distinct_days, p80, first_coverage}, derivation_rule{name:"opinion_stage", version:"os-v0"}}`，纯函数、每天独立算；`退热` 的「曾到过拥挤」靠回看事件重算，不靠存上一天的状态——这就是「不落状态机」的含义。
- 派生结果作为 `RiverObject(track="opinion", object_type="stage", validity_kind="point", derivation="deterministic", label_version=…)` 由 `_opinion_track` 发出；`_fundamental_docs` 的占位 `stage: unverifiable` 删除，改引同一读数。`source_hash` 由 inputs 算——同一天同一批事件永远同一个哈希。
- 与认同度阶梯的关系写进词表：`consensus_staging` 是「证据至少撑到哪一阶」（下限、单调），本词表是「传播走到哪一段」（可退）；三维对照**只用本词表**，`opinion_cross` 技能继续用阶梯，两边不互译、不互相覆盖。映射表只作阅读参考：暗流 → `unverifiable`/`萌芽`，萌芽 → `萌芽`，第一轮 / 催化共振 → `扩散`，一致认同 → `拥挤`。

### 2.2 刀 2｜覆盖率报告 + 错位标记 + 注册标签

1. `scripts/opinion_stage.py report --start --end [--entities …]`：对区间内每个 `(theme|sector, as_of)` 出阶段分布与 `unverifiable` 占比；按 `recorded_at` 分「回填批次内 / 外」两列——回填批次（2026-01 那 249 份）内的密度斜率**单列并标注不可比**。人读表 + JSON 收据 `methodology/receipts/opinion_stage/<date>.json`（台账地图登记）。
2. **错位标记** `dislocation(theme_stage, opinion_stage) -> aligned | opinion_leads | opinion_lags | unverifiable`：两侧都映射到三档粗序（早 / 中 / 晚）再比。题材侧映射表 `THEME_STAGE_COARSE = {module: {stage_word: coarse}}` 分模块写（`theme_lifecycle` 八阶段一张、`theme_lifecycle_timeline` 七段一张），带 `mapping_version`；**G-04 落地后这张表退化成一张**，本单先双表。任一侧缺 → `unverifiable`，不用另一侧补。
3. `opinion_stage` 进 `methodology_backtest.labels`：加到 `THEME_LABELS`，`LABEL_VERSION` 升一版，`LABEL_SPEC` 写口径；`build-labels` 重建旁路库 `db/history_labels.duckdb`（先备份到 `/tmp/history_labels.pre-<ver>.duckdb`），现有规则收据重跑——**漂移要么无、要么有记录**。这一步让它能当 #37 情景树的分枝条件与 `methodology_backtest` 的谓词。

---

## 3. 验收（逐条可打勾）

1. 每一段都有确定性派生规则，且 `derive_stage` 对同一 `(events, as_of)` 幂等；路径上无 LLM（测试）。【路线图 G-06 (a)】
2. 用夹具事件流构造五种走法：`萌芽→扩散→拥挤→退热`、`萌芽→unverifiable`（覆盖消失）、有 `falsification` 事件 → `证伪` 且之后不再变、历史 < 60 观测日 → 不出 `拥挤`、回填批次日 → 斜率单列。
3. `recorded_at > C` 的研报不参与 `count_90d`（测试：同一天 `C` 不同，阈值两侧的结果不同）。
4. 真库覆盖率报告跑通 `2026-06-01 → 2026-09-05`：多少 `(theme, as_of)` 出阶段、多少 `unverifiable`、`证伪` = 0（**写出来**）；读数进收据 `docs/verification/2026-09-08-opinion-lifecycle-stage.md`。【(b)】
5. `dislocation` 四值各一例；题材侧缺 → `unverifiable`（测试）。【(c)】
6. `UBIQUITOUS_LANGUAGE.md` 新小节含六个词 + 与 `consensus_staging` 阶梯的「另一条轴」声明；`rg` 全树确认新段名未与题材八阶段 / 七段任一词重名。【(d)】
7. 三个阈值是 `from consensus_staging import` 而非字面量（`rg "= 5\b|= 3\b" opinion_stage.py` 应为空）。
8. `_fundamental_docs` 占位 `stage: unverifiable` 字符串在 `river.py` 里消失；舆论轨切片里 `object_type="stage"` 对象出现且 `source_hash` 稳定（两次 `slice` 相等）。
9. `LABEL_VERSION` 升版后：旁路库重建成功、现有 `methodology/receipts/` 重跑结果与重建前逐条对比进收据（保持 / 推翻都行，不能没跑）。
10. 干净树全量 `ruff 0` + 红集不大于基线；`check_test_receipt.py --expect-revision HEAD`。

---

## 4. 非目标 / 红线

- ❌ 不新增抓取器、不接新舆情源；只用 `fact_research_report_catalog` 与 `fact_theme_fundamental_doc` 已有的行。
- ❌ 不落状态机、不存「昨天的阶段」；每天从事件重算。
- ❌ 不从价格、成交额、涨跌推任何一段（尤其 `证伪`）；舆论轴只读舆论轨。
- ❌ 不删、不改 `consensus_staging`；不把两条轴互译后覆盖对方。
- ❌ 不写方向词、不出概率；段名本身不得含涨跌语义（「退热」是传播退，不是价格退）。
- 对外物料在验收 4 的收据出来前，仍写「舆论阶段词表在定」。

---

## 5. 教学注

- **为什么「下限阶梯」做不了生命周期**：`consensus_staging` 的语义是「已入库证据至少支撑到哪一阶」，回补只会让证据变多，所以它必须单调——这是对**数据不完整**的正确保守设计。生命周期轴要表达「传播在退」，就必须允许下降，两者是不同的量，硬合成一个字段会让其中一个语义崩掉。这在任何「证据累积型指标 vs 状态型指标」的系统里都成立（例：CVE 严重度只升不降 vs 漏洞利用活跃度可升可降）。
- **自身历史分位 vs 全局常数**：覆盖密度的绝对值随题材体量差一个量级（大赛道每周十几篇，小题材一季度三篇），全局阈值会让小题材永远到不了「拥挤」、大赛道永远「拥挤」。用自身历史 p80 是把量纲归一到「相对自己」；代价是历史短的实体判不了——所以显式 `不判` 而不是猜。
- **无状态派生 vs 状态机**：状态机存上一日状态，回放要从头跑且任何一天的修数会级联；无状态派生每天独立从事件算，回放任意一天只要那天之前的事件。代价是每天多做一次回看计算，在 469 份研报的量级上可忽略。同样的取舍出现在流处理的「有状态算子 vs 从 changelog 重算」。
- **替代方案对照**：(a) 让模型读研报标题判阶段——不可重算、不可回放（§4.2 `frozen_llm` 只能进上下文不能进条件）；(b) 用舆情热度 API——新增抓取器，且热度不是「版本在切换」；(c) 本单：全部从已有事件的计数与时序算。

---

## 6. 交接要求

- 在途交接 `docs/handoffs/inflight/feat-opinion-lifecycle-stage.md`（≤ 3K）。
- 合入后：路线图 G-06 回写「已落（#36）」，§5 第 3 题写入实际拍板；对外物料由 BP 维护者按验收 4 的读数改口（本单不改 BP）。
- 台账地图 `docs/learning/ledger-map.md` 登记 `methodology/receipts/opinion_stage/`。

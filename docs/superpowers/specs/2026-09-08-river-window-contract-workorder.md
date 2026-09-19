# 工单 #35：区间契约 `river.window` + 五类派生对象 + 区间 PIT（G-02c）

> 日期：2026-09-08
> 上游：`2026-09-06-personal-research-calibration-endstate-design.md` **§4.4 区间契约**（契约正文，照抄不改）、§4.6 事件锚点回溯（组合形状）、§4.2 `validity_kind ∈ {point, state, range}`、§10 最小验收集第 9、10 条、§11 第 12 条（区间 PIT）；`2026-09-05-time-river-gap-roadmap.md` §2.5 G-02c
> ⚠️ 上述章节 2026-09-06 写入、截至 09-08 从未提交；本工单所在分支 `docs/closeout-workorders-0908` 已带上，开工前确认树里有 §4.4
> 优先级：**P1**——G-02b 相似匹配、G-08 环境剧本、#37 情景树的 `analog_ref` 全排在它后面；「没有段级 PIT 的相似窗口是前视泄漏」
> 规模：中到大单（三到五天，三刀三个 PR）
> 分支：`feat/river-window-contract`（刀 1）→ `feat/river-window-derived`（刀 2）→ `feat/river-window-migrate`（刀 3）
> 依赖：G-02a `river.slice`（已在 main）、#27 `recorded_at`（已在 main）。**不依赖** #34 投影（投影的 `source` 可以是 `RiverWindow`，但那是 #34 之后接线，不在本单）
> 并行冲突：本单改 `river_window.py` / `river_query.py` / `market_regime_analogs.py` / 新建 `river/window.py`；与 #34（`guided_reading` / `checkpoints`）、#36（`river.py::_opinion_track`）无文件重叠。**#663 事件定价合入后**，其 `anchor_windows` 第二实例迁到本契约是 #663 的迁移义务（路线图 G-02c 原文），不在本单

---

## 0. 一句话

单点切片 `river.slice(T, C)` 已经把「这一天是什么」守住了：过 `recorded_at ≤ C`、缺轨 `gap`、`pit_grade` 两档。但一到「这一段怎么走过来的」——连续双红几天、阶段哪天跃迁、区间累计、首次出现、六维签名——现有代码全部**读全历史、不接 C、不出 `pit_grade`**。本单把区间做成与单点同级的契约：`window(start, end, C)` 返回**保留对象身份的切片序列**加**可拆回到天与行的派生对象**，整段 `pit_grade = min(各天)`，缺天按 `gap_policy` 显式处理；然后把四个绕过 PIT 直读全历史的读数迁到它上面。

---

## 1. 现状 [实测 @ `gitea/main` `8e452e72`]

| 位置 | 现状 | 差距 |
|---|---|---|
| `intelligence/services/river.py:46 TRACKS`、`slice()`、`_enforce_cutoff(:817)` | 单点切片：六轨、`recorded_at ≤ C` 过滤、缺轨 `Gap`、`pit_grade` | 没有区间入口 |
| `intelligence/services/river_window.py:181 build_daily_vectors(db_path, checkpoints_path)` | 读**全历史**逐日六维向量；缺数留 None 不补零（对） | 不接 `knowledge_cutoff`，不出 `pit_grade`——无前视纪律到区间断了 |
| `river_window.py:291 window_features(daily, start, end)`、`:334 windows_around(daily, anchors, before, after)`、`:61 FeatureSpec`、`:406 cluster_windows` | 六维签名 + 层次聚类；`FeatureSpec` 已能回溯到表 / 列（`signature` 类派生的原型） | 输入是全历史向量，PIT 取决于上游；没有 `member_refs` 指回哪些天的哪些对象 |
| `intelligence/services/river_query.py:656 range_aggregate(start, end, entity, require_complete)` → `RangeAggregate{coverage, codes_seen, caveats}` | **已是 `cumulative` 类的正确形状**：覆盖不完整或跨换源日时 `require_complete=True` 只给 gap | 不接 C；`validity_kind` 未标 `range` |
| `intelligence/services/market_regime_analogs.py:333 load_market_regime_vectors(con, as_of)` | 只截 `trade_date <= as_of`（**有效时间**），docstring 自称「D10 唯一的截断点」 | 不截 `recorded_at`（**记录时间**）→ 出不了 `pit_grade`；D10 窗口读数因此不能进回放 / 校准 |
| `intelligence/services/stock_analogs.py`、`market_analogs.py` | 各自的特征维命名 | 特征目录统一是 G-16，不在本单；本单只保证**不再新增第四套命名** |
| `intelligence/services/teaching_framework/leader_succession.py:280 build_succession(..., knowledge_cutoff)` | 已按 cutoff 做 `withheld_until_cutoff`；是 §4.6 事件到事件模式的第一个实例 | 自己组装，没有走统一的 `anchor_windows` |
| `feat/event-pricing-slice1`（PR #663，未合）`intelligence/services/event_pricing/` | §4.6 外生事件锚点第二实例，事前 / 当日 / 事后窗 | 不等本契约；合入后迁到 `window()` 并带 `pit_grade` 是 #663 的义务 |
| `rg "class RiverWindow\|def window(" intelligence/` | 0 命中 | 缺口成立 |

---

## 2. 三刀

### 2.1 刀 1｜`river.window` 契约 + 覆盖 + 段级 PIT（`intelligence/services/river/window.py`，新建）

形状照 §4.4，字段不改：

```text
window(start, end, knowledge_cutoff=C, entity=E, tracks=[...]) -> RiverWindow
  start / end          按交易日历（fact_market_daily 有行的日子），不按自然日
  knowledge_cutoff     整段一个 C；默认 C = end；C > end → hindsight=true；C < end → ValueError（区间没走完就没有这段区间）
  slices[]             每个交易日一片 RiverSlice，各自带 pit_grade
  derived[]            刀 2 填；刀 1 只挂 cumulative（见下）
  coverage{track: 有对象天数 / 区间天数}
  pit_grade            = min(slices.pit_grade)：任一天 trade_date_only 整段 trade_date_only
  hindsight / alias_applied   任一天为真整段为真
```

实现约束：

- **`slices[i]` 必须与 `river.slice(day_i, C, E)` 逐字节相同**（`to_dict()` 比）。允许 provider 增加按区间批量取数的快路径（`fetch_range`），但快路径的正确性靠这条断言守，不靠信任。
- `cumulative` 类直接包 `river_query.range_aggregate(..., require_complete=True)`：把 `RangeAggregate` 装成 `RiverObject(object_type="cumulative", validity_kind="range", derivation="deterministic", derivation_rule={"name":"range_aggregate","version":…}, member_refs=[各天 market/sector 对象 ref], gap_policy="skip", coverage=…)`；覆盖不完整时对象标 `unverifiable`，**不给数**。`range_aggregate` 本体不重写（§4.4 原文「纳入而不重写」）。
- `RiverObject` 加 `validity_kind: point | state | range` 与 `derivation: deterministic | frozen_llm`（§4.2）；现有单点对象 `point`（逐日标签、事件）或 `state`（阶段、叙事版本、判断），默认值按 `object_type` 映射表给，**不改任何现有对象的哈希**（`source_hash` 不含这两个新字段）。
- CLI：现有入口是 `python -m intelligence.services.river_window`（模块内 `main()`，`scripts/` 下没有同名脚本）；本单新建 `scripts/river_window.py` 薄壳，子命令 `window --start --end --cutoff --entity [--json]`，人读打印每天 `pit_grade` 与覆盖矩阵；旧 `main()` 的聚类子命令原样挂进来。**注意棘轮**：`test_double_red_single_source` 已点名过 `river_window.py` 写死双红阈值（09-06 改成引 `signals.DOUBLE_RED_SQL`），新代码任何双红谓词一律引常量。

### 2.2 刀 2｜五类派生对象 + `gap_policy`（`intelligence/services/river/derive.py`，新建）

| `object_type` | 定义（§4.4） | 输入 | `gap_policy` 默认 | 现成原型 |
|---|---|---|---|---|
| `streak` | 连续 N 日满足某注册标签 | 切片序列里某轨某标签对象 | `unverifiable`；规则可声明 `break`（缺天中断计数）并写理由 | `theme_lifecycle_timeline` 的连续双红计数（只借形状） |
| `transition` | 阶段 / 标签从 a 到 b 的跃迁日 | 相邻两天 `state` 对象 | `unverifiable` | — |
| `cumulative` | 区间累计 | 刀 1 已挂 `range_aggregate` | `skip` + `coverage` | `range_aggregate` |
| `first_event` | 区间内首次出现 | 某轨 `event` 对象 | `unverifiable` | 舆论轨「首次卖方覆盖」（`fact_research_report_catalog` 事件） |
| `signature` | 六维 z-score 签名 | `build_daily_vectors` 的行 | `unverifiable`（缺维按覆盖率惩罚，不补零） | `river_window.FeatureSpec / window_features` |

每条派生对象必带：`derivation_rule{name, version}`、`member_refs[]`（指回哪些天的哪些对象 ref）、`validity_kind=range`、`valid_from=start / valid_to=end`、`pit_grade`（= 所依赖切片的 min）、`gap_policy` 与 `gaps_applied[]`（缺了哪几天、按哪条策略处理）。**标签谓词只能引用 `methodology_backtest.labels.ALL_LABELS`（15 个，`LABEL_VERSION` v3）**——不新造标签名（G-16 的红线提前守住）。

### 2.3 刀 3｜迁移四个绕过 PIT 的读数 + 前视门禁

1. `river_window.build_daily_vectors(*, knowledge_cutoff: str, ...)`：`knowledge_cutoff` 改为**必填关键字参数**；内部改走 `window(first_day, last_day, C)` 的 `signature` 输入；返回每行带 `pit_grade`。`window_features / windows_around / cluster_windows` 透传 `pit_grade`，`Cluster` 加 `pit_grade_worst`。
2. `market_regime_analogs.load_market_regime_vectors(con, as_of)` → 加 `knowledge_cutoff`，`find_regime_analogs` 返回值带 `pit_grade`；`regime_block_for_llm` 在 `pit_grade != strict` 时加一行限定语（不改其他文案）。
3. `river_query.range_aggregate` 加 `knowledge_cutoff: str | None`（None = end，行为不变）；`RangeAggregate.to_dict()` 加 `pit_grade`。
4. `river.anchor_windows(anchor_label, before, after | until, knowledge_cutoff, context_tracks)`（§4.6）作为 `slice + window` 的**组合函数**落在 `river/anchor.py`：返回 `AnchorRecord{anchor_as_of, context, forward, lookback[], context_target, pit_grade=各段最差, gaps[]}`。硬规矩 1：`anchor_label / target_label` 必须 ∈ `ALL_LABELS` 或已注册派生规则，否则 `ValueError`。**第一个消费方 = `teaching_framework.leader_succession.build_succession`**，改为从 `anchor_windows` 取 `context_break / context_birth`，读数逐字节不变（有测试钉住）。事件定价（#663）的迁移**不在本单**。
5. **前视门禁**（§11 第 12 条的可执行形式）：新增测试 `test_river_window_no_bypass.py`——静态扫描 `intelligence/services/{river_window,market_regime_analogs,market_analogs,stock_analogs}.py`，任何 `duckdb.connect` / `SELECT … FROM fact_*` 的调用点必须在 `river/` 包内或带 `# pit: via window()` 标注并有对应 `knowledge_cutoff` 形参；新增绕过即红。这是棘轮不是一次性检查。

---

## 3. 验收（逐条可打勾）

1. `window(start, end, C)` 对同一输入幂等（两次 `to_dict()` 相等）；路径上无 LLM。【§10 第 9 条】
2. 任一天 `trade_date_only` → 整段 `trade_date_only`；`C < end` → `ValueError`；`C > end` → `hindsight=True`。【§10 第 9 条】
3. 随机 3 天：`window.slices[i].to_dict() == river.slice(day_i, C).to_dict()`（夹具库 + 真库各一次，真库读数进收据）。
4. 随机抽 30 个派生对象，每条 `member_refs` 都能解析回对应切片里的对象；所需轨缺天的派生对象为 `unverifiable` 而不是数字。【§10 第 10 条】
5. 五类各至少一个夹具用例：`streak` 缺一天在 `unverifiable` 与 `break` 两种策略下结果不同且 `gaps_applied` 写明缺哪天；`cumulative` 覆盖不完整 → 无数值；`signature` 缺维按覆盖率惩罚而非补零（复用 `river_window` 现有测试）。
6. 派生对象的标签谓词引用不在 `ALL_LABELS` 的名字 → 拒绝（测试）。
7. `build_daily_vectors()` 不带 `knowledge_cutoff` → `TypeError`；带 C 且 C 早于最后一天时，返回行数 ≤ 不带 C 的旧行为（用夹具库证明它真的截了）。
8. `find_regime_analogs` 返回 `pit_grade`；`strict` 与 `trade_date_only` 两档分开报，不出混合平均（沿 #25 已定口径）。
9. `leader_succession` 改走 `anchor_windows` 后，`methodology/teaching/` 下现有收据重跑逐字节不变（或漂移有记录）。
10. 前视门禁测试对当前树绿；人为在 `market_analogs.py` 加一处裸 `duckdb.connect` → 红（变异测试进 PR 描述）。
11. 干净树全量 `ruff 0` + 红集不大于基线；`check_test_receipt.py --expect-revision HEAD`。收据 `docs/verification/2026-09-08-river-window-contract.md`，含真库 `window("2026-08-01","2026-08-29",C="2026-08-29","上证指数")` 的覆盖矩阵与 `pit_grade`（预期大多 `trade_date_only`——#27 说过 strict 日从 09 月才开始累积，**写出来，不美化**）。

---

## 4. 非目标 / 红线

- ❌ 不统一四套特征命名（G-16）；只禁新增。
- ❌ 不迁事件定价（#663 未合；合后由其作者迁）。
- ❌ 不做相似匹配的新算法、不出概率；匹配读数照旧只报 N、距离、后续 5 / 10 / 20 日事实，N < 10 样本不足。
- ❌ 不新增存储、不缓存区间结果（终局 §9 / F4）；性能不够先量再说，量出来的读数进收据。
- ❌ 缺天**不补零、不前向填充、不跳过不报**——三种都是把「不知道」变成「知道」。
- `range_aggregate` 本体不重写；`FeatureSpec` 不重写；两者是被包进契约，不是被替换。

---

## 5. 教学注

- **为什么整段 `pit_grade` 取最差而不是按比例**：回放的问题是「这段读数里有没有一个数是事后才知道的」，一个就够污染结论；所以是 min 不是均值。同一逻辑在数据血缘里叫「污点传播」（taint propagation）——任何输入被标记，输出即被标记。
- **`gap_policy` 三种的区别**：`unverifiable` 是「缺一天我就不说」；`break` 是「缺一天连续计数归零」（对 streak 语义正确，对 cumulative 不对）；`skip` 是「跳过但在覆盖率里如实报」（对累计量可接受，对连续量不可接受）。策略挂在派生规则上而不是全局，因为**正确性取决于量的语义**，不取决于数据源。替代方案「全局一个策略」会让 streak 与 cumulative 里必有一个是错的。
- **有效时间截断 ≠ 记录时间截断**：`trade_date <= as_of` 挡住的是「未来的行」，挡不住「过去的行被今天重写」——后者正是 #27 量出来的 413 天里只有 1 天可 strict 的原因。双时态数据库（bitemporal）把这两个轴分开存正是为此；本仓不上双时态库，但契约要把两个轴都写出来。
- **替代方案对照**：(a) 只给 `range_aggregate` 加 C、不做契约——四个读数各修各的，下一个新读数又绕过；(b) 把区间做成物化表——违反 §9，且每次重发布要重算全表；(c) 本单：纯函数 + 组合 + 门禁，正确性靠「切片序列逐字节等于单点切片」这条断言，不靠信任实现。

---

## 6. 交接要求

- 在途交接 `docs/handoffs/inflight/feat-river-window-contract.md`（≤ 3K）；每刀合入后更新。
- 合入后：路线图 G-02c 回写「已落（#35）」并把「事件定价迁移」义务挂到 #663 的交接里；09-06 spec §10 第 9、10 条与 §11 第 12 条标实测。
- `UBIQUITOUS_LANGUAGE.md`「区间」「事件锚点回溯」两条已在（09-06 写入）；本单只补 `gap_policy` 三值的定义一行。

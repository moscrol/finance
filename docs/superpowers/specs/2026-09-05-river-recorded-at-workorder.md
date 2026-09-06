# 工单 #27：时间长河 PIT 止血 —— `recorded_at` 写一次不更新 + 对象契约冻结

> 日期：2026-09-05
> 上游：`2026-09-05-time-river-endstate-design.md`（终局，已审）、`2026-09-05-time-river-gap-roadmap.md`（G-02a / G-02 对象契约）
> 优先级：**P0（时间衰减）** —— 每过一个交易日、每一次重发布，可重放段就少一段，且不可回补
> 规模：刀 1 小单（半天）；刀 2–3 中单（一到两天）
> 分支：`feat/river-recorded-at`
> 号段：roadmap 写「INDEX 从 #26 起编」**已过期**——`2026-09-01-workorders-INDEX.md` 第 9 行 #22 正文已把 #26 预留给 RAG 步骤 5「回预算闸」。时间长河系列从 **#27** 起。

---

## 0. 一句话

`updated_at` 是**刷新时间**不是**记录时间**，各 sync 一律 `ON CONFLICT DO UPDATE SET updated_at = excluded.updated_at`，所以任何一次回填或重发布都会把整段历史的时间戳推到今天；结果是 413 个交易日里**六轨联立能出 `pit_grade=strict` 的只有 1 天**。历史补不回来，唯一的杠杆是从今天起停止冲刷：加一个写一次就不再更新的 `recorded_at`。

---

## 1. 读数（2026-09-05 实测，可复跑）

```bash
.venv-workbench/bin/python scripts/river_pit_audit.py          # 人读
.venv-workbench/bin/python scripts/river_pit_audit.py --json   # 收据
```

六个维度按终局 §3 + F9：盘面 / 题材 / 舆论 / 资金 / 个股 / 判断（判断轨在用户态 JSONL，不在本库）。

| 维度 | 骨干表 | 总日 | strict 日 | 占比 | 记录时刻取自 |
|---|---|---:|---:|---:|---|
| 盘面 | `fact_sector_daily` | 410 | **1** | 0.2% | `updated_at` |
| 盘面 | `fact_market_daily` | 413 | 13 | 3.1% | `updated_at` |
| 题材 | `fact_theme_limit_stock_daily` | 395 | 45 | 11.4% | `updated_at` |
| 资金 | `fact_sector_stock_daily` | 117 | 47 | 40.2% | `updated_at` |
| 个股 | `fact_stock_daily` | 405 | 37 | 9.1% | `updated_at` |
| **舆论** | `fact_research_report_catalog` | 105 | **104** | **99.0%** | **`created_at`** |

**逐日四轨联立可 strict 重放：1 天（2026-09-02）。瓶颈只有 `fact_sector_daily` 一个——去掉它交集立刻变成 34 天，去掉其余任一轨仍是 1 天。**（舆论轨按 `report_date <= as_of` 取，是累计量，不参与逐日交集；把它塞进交集会得到一个由量法造出来的 0。）

**舆论轨那 99% 就是本工单的存在性证明。** 同一个库、同一批写入管线，只因为 `fact_research_report_catalog` 有一列**没被重写覆盖**的 `created_at`，它现在就能进严格 PIT。对照实测：该表 469 行里 `updated_at` 去重后**只剩 1 天**（被 09-02 那次批量写入抹平），而 `created_at` 有 **104 个不同日期**、468/469 行 `<= report_date`。**同一张表里，真实记录时刻还在，刷新时间已经没了。** 刀 1 要做的就是把这一列推广到其余各表。

`fact_market_daily` 的滞后分布：strict 13 天 / 1~7 天 8 天 / 8~30 天 17 天 / 31~180 天 93 天 / >180 天 274 天 / `updated_at` 为 NULL 8 天。

> 与 INDEX #25 记的「`updated_at` 严格边界只过 17/413 日」对不上——**#25 偏乐观，且是单表读数**。本次逐表复量 `fact_market_daily` 为 13/413，而决定 `slice()` 能力的是**跨轨交集**，不是任何单表。工单 #25 正文的这句要按本读数订正。

---

## 2. 根因（实测，非推断）

**证据一——批量重写把七个交易日的时间戳推到同一时刻。** `fact_sector_daily_generation` 里 trade_date 08-25 至 09-02 的行，`updated_at` 全是 `2026-09-02 18:39:10.487750`。

**证据二——真值被 VIEW 挡住了。** 08-25 有两版快照：`superseded` 那版还留着真实首次写入时刻 `2026-08-25 22:17:27`，`published` 那版是 `2026-09-02 18:39:10`。而 `fact_sector_daily` 是 VIEW、只暴露 `published`——**真实记录时刻在库里，但读取面看不到**。

**证据三——语义本来就不是 PIT。** `market_feature_store/schema.sql:10` 自己写着「所有事实表带 source / updated_at 以便追溯来源与**刷新时间**」。是 `fidelity_replay.py:918 _pit_where` 把一个刷新时间当成了 PIT 边界。这不是数据坏了，是两层对同一个字段的口径不同。

**证据四——历史救不回来。** 取每日最早快照的 `updated_at`（把 superseded 也算上）重算，`fact_sector_daily_generation` 410 天里可 strict 从 1 天变成 2 天；同日多版的交易日总共只有 3 天。**回补上限 = 1 天，等于没有。**

失效方向是**保守的**（重写只会让某天从 strict 掉出，不会让未知数据伪装成已知），所以现在没有假读数——但代价是这条河**每天都在变短**，而且没有任何告警。

---

## 3. 三刀

### 刀 1｜止血：`recorded_at` 写一次不更新（半天，先合）

对 `scripts/river_pit_audit.py:TRACKS` 里列的 12 张事实表（含两张 VIEW 的底层 `*_generation` 表）加列：

```sql
recorded_at TIMESTAMP   -- 首次入库时刻，只写一次；重发布 / 回填不更新
```

所有 sync 的 upsert 改成写一次的惯用法：

```sql
ON CONFLICT (...) DO UPDATE SET
    ...,
    updated_at  = excluded.updated_at,                              -- 保持原语义：刷新时间
    recorded_at = COALESCE(<table>.recorded_at, excluded.recorded_at) -- 已有就不动
```

存量行一次性回填 `recorded_at = updated_at`（`updated_at` 为 NULL 的保持 NULL）。这是**真值的上界**——首次写入不晚于最后一次写入——所以只会少算不会多算，读数与今天逐字节一致，零回归；从此新写的行开始记真值。

`fact_sector_daily_generation` 可选优化：回填取该 `trade_date` 跨所有快照的 `MIN(updated_at)`，多救回 1 天。收益极小，不做也行，做了要在收据里记。

**验收**：(a) 12 张表都有 `recorded_at`；(b) 对同一行连跑两次 sync，`updated_at` 变、`recorded_at` 不变（测试）；(c) 回填后重跑 `river_pit_audit.py`，联立 strict 日数**不小于** 1（不许回退）。

### 刀 2｜读取面改读 `recorded_at`，`pit_grade` 由它派生（一天）

`fidelity_replay.py:918 _pit_where` 改为按 `recorded_at` 过滤，`recorded_at` 为 NULL 时回落 `updated_at` 并把该切片标 `trade_date_only`——**不是丢弃，是降档**，与 #25 已定的两档口径一致。`pit_grade` 的定义从「所有对象都有 `recorded_at`」改成「所有对象的 `recorded_at` 都非 NULL 且 ≤ C」。

**验收**：(a) 两档分开报，不出混合平均（#25 已定，本刀不改）；(b) 现有 fidelity replay 用例读数不变（回落路径保证）；(c) 新增用例：一行 `recorded_at` 晚于 C 时该切片降档且写进收据。

### 刀 3｜契约冻结 + 棘轮门禁（一天）

把 roadmap §2 的 `RiverObject` 契约落成代码（`intelligence/services/river/contract.py`），并按实测订正两处：

- roadmap 原文「`recorded_at` 历史行缺失时为 null → 降级」——**订正**：现实不是缺失，是被覆盖成了刷新时间。契约里 `recorded_at` 必须写明「首次入库，写一次不更新」，否则下一个实现者会照 roadmap 复现同一个坑。
- **判断轨的 `ref` 不用新造 id**（实测）：`corrections.py:81` 每条纠偏落盘即带 `id = memory_record_id(kind, ts, content)`，`checkpoints.py:172` 有 `_make_id(claim, ts)`，两者都是内容派生哈希、追加式 JSONL 下天然稳定，`ref` 与 `source_hash` 可合成同一字段。

**索引层不落库**（终局 §9 / F4 的可测化）：`slice()` 是纯函数 + 每轨一个 provider 现算，`RiverObject` 只在内存组装，不新增任何存储。实测慢到不可接受时才加缓存，且缓存必须能从原轨完全重建（重建测试进验收）。

**棘轮门禁**：`river_pit_audit.py` 的联立 strict 日数存一个 baseline，只增不减；掉了就红。这道门专治「某次重发布悄悄把河冲短了」——它今天已经发生过一次，而没有任何人知道。

**验收**：(a) `slice(T, C)` 对同一 `(T, C)` 幂等且路径上无 LLM；(b) 缺轨返回 `gap{track, reason}` 而非空或推断；(c) 每个对象 `source_hash` 可回溯主数据；(d) 索引层不持有任何轨主数据副本（测试）；(e) 棘轮门禁在 baseline 回退时红。

---

## 4. 顺序与依赖

刀 1 **不依赖任何其他缺口，也不被任何缺口依赖，且时间衰减**——先合，越早越好。刀 2、3 可以并行于 G-01（母本，人写）与 G-05（`market_stage` 归一）。G-02a 的三轨 provider 排在刀 3 之后。

---

## 5. 红线

- 不新建记忆中台、不新建第二套向量库、不新增存储（终局 §9、F4）。
- 不动 `updated_at` 的现有语义（刷新时间），只新增 `recorded_at`。任何「顺手把 updated_at 改成记录时间」的做法都会打断现有的变更检测与对账。
- 存量行只回填上界，**不从任何地方推断真实首次写入时刻**——推不出来就留 NULL 并降档，缺失的数据不由模型补编（终局 §3）。
- 在主 clone 跑全量门禁时，`test_conversation_orchestrator.py::test_completed_stream_persists_human_readable_answer` 是**存量红**（有真库时 `market_watch_pack` 前置盘面组件包，断言按无库环境写死；INDEX #21 已记录），与本单零交集，不要当成自己弄红的。

---

## 6. 对外口径

做完前：BP §3「六类数据当前分散在不同组件中；统一查询面尚未完成」——不变，仍写「在做」。

做完后**也不要**把「413 个交易日」和「可回放」连在一起说。诚实读数是：数据覆盖 413 个交易日，**可严格 as-of 重放的联立切片从 2026-09-XX 起累积**。BP §3 那句「时间长河是长期建设方向」以及电梯稿里「晚来一年，这段河补不回去」——后半句本工单让它第一次真正成立：在加 `recorded_at` 之前，这条河**每天都在把自己冲短**。

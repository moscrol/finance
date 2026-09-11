# feat/knevo-delta-readside · 在途交接（2026-09-11）

## 干什么

执行 `docs/superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md`（2026-09-11 评审修订版）
里用户已过闸的四项：W1/W2/W3（读侧记忆）+ W5（封板时间数据出口）。

两笔提交，pre-commit 全绿：

- `f63a2352` W1/W2/W3 读侧三项（user_memory / episode_tools / evolution 回测队列）
- `cb411e73` W5 涨停封板时间块 [D18]（market_timeseries / ask / evidence_registry）

## 关键状态：分支基点

本分支基于 **gitea/main @ 3ed44703**，不是 spec 所在的 `docs/knevo-e009-arch-delta`
（那条基于 `docs/knevo-m-probes-verification`，落后 main 165 个提交）。
**spec 文档本身仍在 docs 分支上**（`20ad971d` 那笔修订），本分支只有代码。
合并时两条分支都要进，顺序无依赖（改的文件不重叠）。

## 做完了什么（对照 spec 验法）

| 项 | 交付 | 变异实测 |
|---|---|---|
| W1 | `RECALL_SOURCES` 三源常量 + 双侧契约测试（user_memory / episode_tools 各钉一半） | tier 改 `"news"` → 红；删先验自标 → 红；偷加第四源 → 红 |
| W2 | [M] 块条目前缀补归属；`memory_lookup` 的 source 补台账名 | 退回块级「核心判断」标签 → 红 |
| W3 | 口径固定为计分率 + 双闸；阈值 `None`=关闭；机制与测试到位 | 误改成整命中率 → 红 |
| W5 | `limit_seal_time_block_for_llm` + D18 provider + 注册 | 双守卫都删 → 红（单删不红，属两道独立守卫，已注释说明） |

全量 `intelligence/tests`：7988 passed / 15 skipped / 1 xfailed。

## 等用户裁决 / 阻塞

- **W4（P2）AB 双盲台账**：spec 写「二选一，请用户定」——(a) 补两个样本的 verdict
  让台账复活；(b) 在 `docs/learning/ledger-map.md` 宣判废弃并写原因。
  红线是不允许维持现状（目标 25 样本、实际停在 2、verdict 逾期两个月）。**未动**。
  裁决前先知道这三件事（本轮核实）：
  ① 台账正文在 **docs 分支** `docs/knevo-e009-arch-delta` 上（`docs/learning/knevo-distill/ab-ledger.md`），
  不在本分支；② AB-001 两边 verdict 均为「待回检」，AB-002 本地待回检、Knevo 已判
  `unverifiable / protocol violation`（用了预测日 07-10 信息，A6 执行偏差，**不得再用 07-10 走势给它打 hit**）；
  ③ 这张台账**从未在 `ledger-map.md` 登记过**（已 grep 确认无 knevo/ab-ledger 条目），
  而 AGENTS.md 写「新增任何台账必须先在这张表登记」——即选 (a) 复活也得补登记，
  选 (b) 则是「登记一条已废弃」。两条路都要动 `ledger-map.md`，区别只在写什么。
- **W6（P3）E-007 P3/P4 判据：已交付（2026-09-11）**。用户授权后合入两条依赖分支
  （`polymarket-macro-odds-impl` → `feat/event-pricing-slice1`，均干净合入，合后全量
  9081 passed），随后落判据。验收报告：`docs/verification/2026-09-11-e007-p3p4-criteria.md`。
  - **日历半边**：4 条测试（`intelligence/tests/test_event_pricing.py`，搜 `e007`），用**真实发布
    日程**（`nbs_2026`）而非手工小日历。顺带闭合 E-007 §5 第一条（发布日核对，两条都对上）。
    最值钱的一层：7 月 CPI 定于 `2026-08-09`（**周日**）发，按 `reaction_day` 判「已知」，
    站在 8/9 仍答 6 月期、8/10 才翻 7 月期——推月度节奏推不出「那天是周日」。
  - **赔率半边**：3 条测试（`tests/test_sync_polymarket_macro_odds.py` 末尾）。
    as-of 完整性有**真陷阱**：`--trade-date` 是标注日不是数据日，传 `2020-01-01` 照写，
    拿到的是今天的价盖那天的戳（同 daily-full 「取最新」写历史日的坑）。
  - **`truncated` 不落库仍是开着的洞，本次有意不补**：该表未接夜跑（补洞是接夜跑的
    前置，不是现在的阻塞），W6 的动词是「验」，E-007 底线是「本仓不补宏观分析」。
    改用 **documented gap 测试**钉住：它会在**洞被补上时变红**并报「请更新 W6 验收判据」
    （已用给 schema 加 `truncated` 列的变异实测过）。**后人注意：那时请改判据，别删测试。**

## 坑 / 后人须知

- **W3 阈值是故意留空的，且 2026-09-11 已量过样本、结论是继续留空**。
  `RELIABILITY_DOWNWEIGHT_THRESHOLD = None` 时降权与警告行完全不生效，生产行为逐字节不变。
  Q-001 原阻塞项「样本够不够分桶」**已测**（记录与复现命令在
  `evolution/backtest-queue.md` 「测量记录 · 2026-09-11」）：全机只两个 user 有台账，
  `linxiaoqi5111` 已终态 80 条但**只 1 个 category 桶达 min_n**（生命周期推演 n=78、
  计分率 0.090），`default` 终态样本为 0。因此：候选值 0.3/0.4/0.5 在这份数据上
  **行为完全相同、无法区分**，且召回池只 1 条、其 category 压根没对应桶，
  **填数也不会改变任何召回结果**。下次重量的触发条件：≥2 个桶各达 min_n
  且召回池有能解析到这些桶的记录——在那之前再量一次结论不会变。
  直接填数会让 `test_threshold_defaults_to_none_until_backtested` 变红——那是故意的闸。
  另：78 条全为 `source=logic_lifecycle` 单一机器来源，属相关样本，将来即使桶数够也要先过这关。
- **`evolution/backtest-queue.md` 是本次新建的**。`reading_baseline.py:21` 与规则清单
  早就写着「数字走 evolution/ 回测队列」，但此前 `evolution/` 下没有这个队列，
  引用悬空。新文件是人工登记账，**不接 `scripts/evolve.py`**，别以为它会自动跑。
- **D18 故意不挂判读规则**。`limit_seal_time_block_for_llm` 里没有
  `reading_baseline.block_rule_lines("D18")`，这不是漏写：SPT-A06 依赖的 `open_times`
  恒 NULL（G1b 未修），规则整体仍在 `_PENDING_RULES`。修好 G1b 再另立项做迁移。
- **PEER_HIT_LINE 与降权口径不同，这是设计**。展示行按整命中（x/n），降权按计分率
  （partial=0.5）。同一组数据两个读数不一致是预期的，改动任一处前先看
  `user_memory.RELIABILITY_DOWNWEIGHT_THRESHOLD` 上方那段注释。
- 恢复变异实验时**别用 `git checkout <file>`**：本轮一度因此抹掉了同文件的正式修改
  （已重新应用）。用文件副本 `cp` 恢复。

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
- **W6（P3）E-007 P3/P4 判据**：依赖两条未合并分支——日历半边依赖
  `feat/event-pricing-slice1`（`event_calendar.latest_known()` 在那里），
  赔率半边依赖 `polymarket-macro-odds-impl`（**只有本地分支，gitea 上没有**）。
  合并须用户确认，故**未动**。

## 坑 / 后人须知

- **W3 阈值是故意留空的**。`RELIABILITY_DOWNWEIGHT_THRESHOLD = None` 时降权与警告行
  完全不生效，生产行为逐字节不变。想启用必须先走 `evolution/backtest-queue.md` 的
  Q-001（口径已固定、候选值与判据已写、阻塞项是「样本量够不够分桶」还没量）。
  直接填数会让 `test_threshold_defaults_to_none_until_backtested` 变红——那是故意的闸。
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

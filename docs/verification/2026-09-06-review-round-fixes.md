# 评审整改验收：6 条硬伤 + 干净树全量

> 日期：2026-09-06
> 覆盖 PR：#598 / #599 / #600 / #601（栈式，按序合并）
> 状态：**已推、待合**。

## 0. 一句话

评审给我这批提了 4 条硬伤，全部修完并补了会失败的测试；整改过程中又发现 **2 条会阻塞合并**
的问题（其中一条让**干净检出上整个测试套件跑不起来**）。干净工作树全量 **7906 passed / 2 failed**，
两条红在**未改动的 `gitea/main`** 上同环境复现。

## 1. 逐条

| 来源 | 问题 | 修法 | 测试 | 变异 |
|---|---|---|---|---|
| 评审 #598 | `knowledge_cutoff` 可传未来日期 → 所有对象通过 PIT 检查，回放偏乐观且自称 `strict` | **默认拒绝 + 显式签字**：`allow_hindsight=True` 才放行（spec §4.1 第三档「事后人工复核」确实允许），该片 `hindsight=True`、`pit_grade` 永不 `strict`、标记进 `to_dict`、与 `require_strict` 互斥 | 9 | 拿掉门 → 红 2 |
| 评审 #599 | 回检结果没保留对象类别 | 数据没丢（`calibrate` 按 id 回连），缺的是**分列维度**。加 `Calibration.by_object_type` + 报表段。类型从 checkpoint 回连取，**不在 verdict 存第二份** | 4 | 拿掉维度 → 红 4 |
| 评审 #599 | 节假日 `due` → 永远 `unverifiable` | resolver 拒绝拿相邻交易日顶替是**对的**，所以修在登记侧：`resolve_due` 查真日历 / `nontrading_dues` 检出 / `repoint_due` + `observation repoint --apply` 改点 | 8 | 拿掉检出 → 红 1 |
| 评审 #601 | 同日重复行重复连乘，仍报「完整可信」 | 先去重再算；`duplicate_dates` 进 coverage 与 caveats；新增 `coverage.clean`（`complete` 回答不了重复）；`trustworthy` 与 `require_complete` 改用 `clean` | 7 | 拿掉去重 → 红 4 |
| **自查** | `tests/test_build_bp_public.py` 模块级 exec 一个**从未提交**的脚本 → 干净检出上 pytest **收集阶段直接 ERROR 中断** | 条件加载 + `pytestmark skipif` | 主树 13 passed / 干净树 13 skipped | — |
| **自查** | 双红棘轮点名 `river_window.py` 两处写死阈值 | 该文件相对 main 是**新文件**，合并等于给 main **新增**违规（不是存量红）。改引 `signals.DOUBLE_RED_SQL` | 棘轮转绿 | — |

顺带修掉一个 id 碰撞：`_make_id` 只用 `(ts, claim)`，同一秒改点算出的 id 与旧点完全相同，
那条「旧点判不了」的 verdict 会同时打在新点上。`due` 已进哈希（`framework_interpretation`
早按 `(claim, due)` 做幂等，本次只是补齐同一口径）。

## 2. 那条「跑不起来」值得单独说

评审说「因为主工作树有其他人未提交内容，没有把全量 CI 当作验收结论」——**比这更严重**：

`scripts/build_bp_public.py` 从未 `git add` 过，只在主树上以未跟踪文件存在；而它的测试
在 `575136b9` 被提交，且是**模块级** `exec_module`。于是：

- 主树上一直绿，**是靠那个未跟踪文件撑着的**；
- 任何干净检出 / CI 上，pytest **收集阶段就 ERROR 中断**，后面 7900 多条一条都跑不了。

所以本轮之前我给出的所有「全量绿」读数都不成立。这条修完之后，干净树才第一次真的跑完。

## 3. 干净树验收

工作树：从 `feat/river-range-aggregate` 开的 detached worktree，软链真库 `db/`，
`umask 022` + `env -i PATH` 隔离壳。

```
2 failed, 7906 passed, 20 skipped, 1 xfailed in 318.81s
```

两条红的归因（**在未改动的 `gitea/main` 上同环境实测复现**，不是声称）：

- `test_codex_headless_runtime::test_installed_codex_sandbox_denies_network_and_unix_socket` —— sandbox 环境项；
- `test_conversation_orchestrator::test_completed_stream_persists_human_readable_answer` —— INDEX #21 已登记的存量红（有真库时 `market_watch_pack` 前置「## 指定日盘面组件包」，而断言按无库环境写死）。

## 4. 推送方式：没有强推

分支做过 rebase，但 force push 命中仓内红线钩子。改走**标准栈式做法**：把修复提交
重放到各自的远端尖上、再把更新后的 base 合进下游分支（`river.py` 的 `to_dict` 冲突
手工解为**两个限定语都保留**——少任何一个，从 JSON 重建切片的消费方就会丢掉那条限定）。

四条推送**全部快进**。合并前用本机 `git merge-tree` 实算（不信 Gitea 自报的 `mergeable`）：
**四张 PR 全部无冲突**。

⚠ 关键校验：整理后的栈顶 **tree 哈希与跑过全量的那棵树逐字节相同**
（`681c4059bc549c49adee22a1854f7f4af815223d`），所以 §3 的读数对现在的栈顶成立——
这不是「应该一样」，是对过哈希的。

## 5. 不属于本批、没有动

- **#597**（`feat/historical-replay-engine`，另一会话的分支）：评审指出的「拿今天的标签算」
  **确认存在，且比报告更深**——`history_labels` 有 `label_version` / `computed_at` 两列，
  `_labels_for_day` 一列都没用；而主键 `(entity_type, entity_id, trade_date, label)`
  **不含 label_version**，换版重算会**覆盖**旧行。所以这张表在结构上就保留不了
  「当时的标签是什么」，**加过滤只会让回放全部落空**。要真修得改主键保留分代，
  或接受回放读数归零——那是该分支的设计决定。
- **#596** 的 CLI 文案（分位阈值 → 固定阈值）：一行改动，但同样是别人的分支。

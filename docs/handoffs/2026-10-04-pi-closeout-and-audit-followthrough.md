# Pi 的 PR #30 收尾核查与原质检落实复核（受托收尾）

日期：2026-10-04 晚。分支 `claude/acceptance-handoff-summary-57fc87`，PR [#42](https://github.com/moscrol/finance/pull/42)（纯文档）。
逐条建议的状态矩阵见 [2026-10-04-harness-followthrough-status.md](../verification/2026-10-04-harness-followthrough-status.md)。本页只记背景、发现顺序、决策和被否方案。

## 背景

- 用户贴来 Pi 的收尾摘要：PR #30 的工程验收已完成，正在等文档 CI。用户问两件事：Pi 那部分能不能收尾？Codex 09-30 部件质检（及其规格、任务板 FINANCEWORKS-1..13）落实得怎么样？
- “8792 与 Pi 的 GLM 对照”用户已分发给其它会话（FINANCEWORKS-5，PR #41），本会话不碰。
- 用户第二条消息授权：「都做，按最优推进」（Claude Code 会话 `74dae9f9-1568-4f13-9063-40253d68445e`，约 23:20 CST）。范围是第一轮回复列出的四项：补记 PR #30 与 FINANCEWORKS-3、修主检出技能视图、回收两棵旧树、把矩阵写进仓库。合入与部署不在其中。

## 按发现顺序

1. PR #30 文档头 `bffc675da` 的五项 CI 在 16:22 已全部 success；Pi 在任务板的最后一条评论（16:08）还写着“python 与聚合未完成”。
2. 不用 Pi 的脚本，自己重算 `engineering-closeout.json` 绑定的 52 份输入哈希：52/52 一致。另核：Pi 树干净，origin 与 Gitea 同为 `bffc675da`，两棵门禁树已拆，变异进程已退出。
3. Pi 观察 main 之后，main 又合入并部署了 #40，它改了 `intelligence/services/episode_protocol.py`，与 PR #30 交叠。所以 Pi 交接里“main 只多三份文档、没有产品源码差异”那句已经过时。
4. 在 taskctl 任务板上找到 Codex 的拆单（规格 `2026-10-03-harness-quality-closeout-spec.md`）和 10-03 基线矩阵，然后按当前 main 逐项实测，结果见状态页。
5. 本会话的技能列表和本 worktree 的 `.claude/skills/` 对不上（仍有 `up-line` 等三个，没有 `stock-technicals`），推断是从主检出加载的。修改主检出后，技能列表当场热更新，证实了这个推断。
6. 回收树时，第一次 dry-run 把第二棵树的理由记到了两棵树上：`--reason` 只取最后一个值。这份 dry-run 作废、留档，改用计划文件重跑，再 apply，2 棵拆除 / 0 跳过 / 0 失败。

## 决策与被否方案

| 问题 | 选择 | 被否方案 / 理由 |
|---|---|---|
| FINANCEWORKS-3 状态 | 改 done，评论写明只关工程/集成范围 | **保持 in_review**：验收条件已全部满足，挂着会让人以为工程还有缺口。Pi 写“不自动 done”，是把决定留给验收方；用户本轮已同意改。 |
| PR #30 正文 | 在 Pi 原句下追加两条：CI 补记、main 漂移 | **改写 Pi 原句**：会抹掉“当时 CI 未完成”的历史。**不改**：PR 正文是状态真本源之一，会继续误导。 |
| PR #30 去留 | 保持 Draft 搁置，等 8792 vs Pi 的结果再定 | **现在合**：质量未验，且 main 上的组合已经变了。**现在关**：四片的方向（交给模型自主）与审计一致，结果出来前关掉可能白丢。 |
| 主检出视图 | 只改工作区 5 处，内容与 main 逐字相同，不动索引 | **整体快进主检出**：有 113 处他人未提交改动，可能含夜跑在用的运营覆盖层，要先逐条认领。**暂存或提交**：索引是共享的，别人一个裸 commit 就会带走。 |
| `top-gainers` 描述 | 一起对齐 main | **只改 4 个软链**：撤掉 `top-gainers-feishu` 后，旧描述会指向一个不存在的技能。 |
| mutation-fix 树 | 现在回收，分支保留，HEAD 钉到 Gitea | **按旧约定等 PR #30 定案再收**：Pi 10-03 写的是“具名分支按选择保留”，保留的意图在分支上，而分支已保留；树里没有独有内容，随时能 `git worktree add` 重建。 |
| provenance 树 | 回收 | **保留**：内容已由 `74638aa58` 集成进 PR #30（新增行 99% 在 `bffc675da`），分支在 Gitea 有同 SHA 备份。 |
| 记忆库那棵 agent-memory 分片树 | 只记录，不动 | **一并回收**：那是另一个仓，不在授权范围内。 |
| `--reason` 缺陷 | 另开独立任务 | **顺手改**：脚本改动需要测试和门禁，超出纯文档 PR 的范围。 |
| PR #42 合入 | 不合，等用户确认 | **按“最优推进”直接合**：“都做”覆盖的是四项动作，不含合入；仓规要求合并 main 必须由用户确认。 |

## 验证与收据

原件根：`~/.finance-runtime/reviews/harness-followthrough-20261004/`，清单见 `evidence-manifest.sha256`。

- PR #30：`pr30-body-{before,after,readback}.md`，回读去掉行尾差异后一致；`measurements/pr30-docs-head-checks.json`。
- 技能视图：`skill-view/`，改前、改后、main 三份清单，改后与 main 逐条相同；同步前的撤销步骤见其中的 `README.md`。
- 回收：`tree-closeout/plan-20261004.json`、`dry-20261004T232729.json`、`apply-20261004T232753.json`。作废的那份 dry-run 及其说明一并保留。
- 实测：`measurements/`，含台账、正则、巨函数、工具面、数据只读查询（23:29）、任务板与 PR 快照。

**以下结论不成立：**

- G 列冒烟每臂 n=1，不比高低。
- 记忆召回、Knevo 0/12、四格 0/0/1/0 是已有文档的读数，本轮没复跑。
- 换库锁本轮没复测。
- 本页任何内容都不证明回答质量。

## 后续要做 / 不要做

要做：

1. PR #42 等 GitHub 五项检查出结论，再由用户确认是否合入。
2. 主检出整体同步归 FINANCEWORKS-13：先撤掉本轮的 5 处，再认领其余脏条目，然后快进。
3. 8792 vs Pi 出结果后，再决定 PR #30：是与最新 main 重新合成后验质量，还是留指针关闭。
4. FINANCEWORKS-2 的基线已刷新，用户确认后可以关。

不要做：

- **不要直接对主检出 `git pull` 或 `merge --ff-only`**：未跟踪的 `stock-technicals` 软链会让快进被拒。
- **更不要对主检出用 `git clean` 或 `reset --hard` 来清路**：会丢掉其余 100 多处他人改动。
- **不要把本页或状态页的任何数字当作质量结论**，也不要据此推断 PR #30 已经可以合入。

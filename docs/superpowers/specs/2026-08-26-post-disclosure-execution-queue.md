# 设计：披露批次收口后的执行队列（三件欠账 + 一件等外部）

- 日期：2026-08-26
- 状态：Draft v1（仅落本文，未改任何生产代码、未切端口）
- 来源：同日质检收口后的全仓盘点（对话读数，非推测）。盘点正文含一处已纠正的误报，见 §3 事实 6。
- 代码树：`docs/post-disclosure-execution-queue` ← `gitea/main@3f802821`（树 `/Users/a77/fwp-wt-exec-queue`）
- 禁止在主检出 `feat/reading-rules-baseline-batch1` 脏树上改 runtime。禁止动 8796 / 8802。

## 0. 一句话

披露残差批次（#397–#407）已收干净，但盘点钉出三件「做了没合、合了没生效、三树分叉」的欠账，外加一件被外部鉴权挡住的等待项。本稿把它们排成一条有依赖顺序的队列，并给每件一个可判定的终态。

**判别变量**（验收只锁这一条）：下一个交易日夜跑不再需要人工补跑即达 same-day COMPLETE，且届时主检出 `git status` 为空、分支为 `main`。时刻以 plist 为准：sync 段 18:30（`com.financeworkspace.daily-full-review-sync`）、finalize 段 20:40，21:00 是看读数的时刻，不是触发时刻。#343 与 #365 的验收各自锁在 PR 上，不并入本条。

人话：上一批菜全上齐了。但后厨还有三口锅没收——一口在别院（fupanhui 修复躺在没推的分支上）、一口长出三个分身（判读基线三棵树）、一口被昨晚的菜叶盖住（主树 201 条脏）。还有一口锅要等送煤的（ClickHouse 鉴权）。

## 1. 执行队列（按依赖排序，P0-A/P0-C 可并行）

### P0-B（先做）主检出收拢

| 项 | 读数 |
|---|---|
| 现状 | `/Users/a77/finance-workspace-private` @ `feat/reading-rules-baseline-batch1`（`5f236d78`，分叉自旧基线），201 条脏：40 M + 1 D + 160 未跟踪 |
| 脏区构成 | daily-full-review 运行产物（state/runlog、SKILL/references）、forecast ledger verdict JSON、`lessons_learned.md`、复盘 matrices（含删除 `strategy1-priority-stock-matrix.md`）、`intelligence/services/l3_ingest.py`、`skills.registry.json` |
| 重叠预警 | 与 #365 改动集重叠 5+ 文件（`复盘/README.md`、matrices、`l3_ingest.py`、SKILL、`l3_daily_backfill.py`）——形状是「有人把 #365 的活做进了主树脏区」 |
| 动作 | 逐行认领 `git status`：运行产物类择机 pathspec 提交到恰当分支；与 #365 重叠者**丢弃本地版**（tree-to-tree 已确认 #365 分支版更完整，`git checkout -- <file>` 前先 `git diff` 留档）；认领不清的停下来问用户 |
| 等价判据（08-26 复核补） | **清理 ≠ 无损**：夜跑 wrapper（`nightly-review-sync-staged.py` docstring）明言依赖脏树里**未提交**的行为（主线 mode=static 回退、public-assets 步）。实测主树超前 main 的夜跑链路 = 未提交 6 文件（`run_review_sync.py`、`nightly_full_review.sh`、`l3_daily_backfill.py`、`l3_ingest.py`、SKILL.md、ops-pitfalls.md）+ 分支提交 `1df6844d`（L2 挂账暂停开关 + 装回 public-assets 步）。清树前必须逐个回答「main 有等价物吗」：有 → 丢弃安全；没有 → 先 pathspec 提交走 PR 合入 main（或显式决定弃用），否则清树当晚判别变量自破 |
| 红线 | 覆盖/删除不确定归属的改动必须先问；**不 force push**；全程 pathspec 提交 |
| 验收 | 主树 `git status` 空 → `checkout main` → 与 `gitea/main` 同 SHA |

### P0-A fupanhui 韧性补丁：合入 + 夜跑生效

| 项 | 读数 |
|---|---|
| 现状 | `/Users/a77/fwp-wt-fph-auth` @ `ff08b2b7`（`789cd216` 代码 + `ff08b2b7` 坑沉淀），**无远端分支、无 PR**。merge-tree vs `gitea/main@3f802821` 干净 |
| 改动面 | 5 文件：`fupanhui_source.py`（401→CDP 回退 + Bearer + 指数兜底）、`sync_akshare_index_daily.py`、`sync_fupanhui_sector_daily.py`（当日宇宙过滤）、ops-pitfalls、新测试 117 行 |
| 为什么急 | 08-24 三源同断靠人工补齐；此后每晚复盘都在裸奔同一断法。修复**不在主树上**，合了 main 也吃不到——夜跑的 `FINANCE_WS=/Users/a77/finance-workspace-private`（主树），而主树落后 main 1008 commits。**这就是 P0-B 排第一的原因** |
| 动作 | push 分支 → 开 PR → 本机等价检查（定向 + 全量 `tests/test_fupanhui_auth_fallback.py` + 周边同步测试；交接报 81 tests）→ 合并（用户确认）→ 主树已随 P0-B 在 main → 观察次日夜跑 |
| 验收 | 判别变量本条；回滚锚写进切流/合并收据 |

### P0-C #343 判读基线：三树收口

| 项 | 读数 |
|---|---|
| 三树真身 | ① gitea #343 head `ad3f4172`（08-22 rebase 到 `b4689295` 版）；② 本地 r2 `9c2fff08` = ① 的**再 rebase 重放**（10 笔同内容，无新工作）；③ 主树 `5f236d78` = 旧基线 + 同 10 笔 + 2 笔 docs（`ad3f4172..5f236d78` 的 725 文件巨 diff 是分叉假象，勿当真实改动面） |
| 冲突现状 | r2 merge-tree vs 当前 main（`3f802821`，又进 183 commits）= **CONFLICT**（上轮可合、这轮不可合，Gitea `mergeable=False` 坐实） |
| 存量红档案 | 08-23 全量：r2 与当时 main 同 4 红（非本单引入）。26d 起 main 已跑出 6535P/0F，那 4 红应已在后续 main 修掉——**rebase 后必须重跑验证，不得引用旧收据** |
| 动作 | r2 干净树上 `rebase --onto gitea/main`（merge 预演实测冲突在 `episode_protocol.py`，`ask_synthesis`/`llm_refine`/`market_regime_analogs` 自动合成功；rebase 是逐提交重放，冲突面可能不同，勿按单一文件预设）→ 全量 pytest + ruff（`.venv-workbench`）→ push 到**新分支** `feat/reading-rules-baseline-r3`（不 force push r2）→ #343 换 head 或关旧开新（关闭留指针）→ G1b（`open_times` 全 NULL）需用户在场，单独排期**不阻塞合并** |
| 验收 | 全量 0F、#222 共存钉仍绿（`test_agent_episode` 双键同在）、#343 `mergeable=true`；live A/B（总开关）留合并切流后另跑 |

### P1 #365 退役策略1 md 池

- merge-tree 干净（落后 103 但可合）。**先决**：P0-B 已认领并丢弃主树里与它重叠的本地改动，否则合并后在主树产生语义冲突。
- 合入后注意 `l3_daily_backfill.py` 行为变化（L3 改吃 HTML 当日行）与 P0-A 的夜跑回验同链——两件都合后，夜跑观察一次足矣。

### P2 盘中 L2 边车 P0：等外部，无仓内动作

- spec 树 `fwp-wt-intraday-l2-sidecar` @ `89df4124`（分支已推 gitea，无 PR）。探针 `--check-only` 已独立复现 **Code 516**：ClickHouse 凭证 08-08 失效、08-18 挂账未恢复——P0 收据的前置在仓外。
- 动作：用户恢复鉴权后，交易日 10:00–14:30 跑 `probe_intraday_write.py` 出收据（用 `/opt/homebrew/bin/python3`，`.venv-workbench` 缺 `clickhouse_driver`）。顺手给 spec 分支开 docs PR，别让稿子只活在 worktree。

## 2. 排序理由（为什么不是别的顺序）

P0-B 是 P0-A 的**生效前提**（夜跑读主树）而非 merely 整洁问题——先合 fupanhui 再收主树，中间隔一晚就又是一次人工补跑。P0-C 与两者无共享文件冲突（改动面在 `agent_episode` / `conversation_orchestrator` / reading-baseline 模块），可并行推进，但它落在生产前需要独立切流窗口，不与本队列共用。

## 3. 已核实事实（2026-08-26 13:00 盘点，实施时不要再探一遍）

1. 主树 201 条脏、分支 `feat/reading-rules-baseline-batch1` @ `5f236d78`；`gitea/main` = `3f802821`；8792 = `fbdbbfd2`（healthy / dirty=false / match=true），8796 = `76ee1e89`、8802 = `5d7529e5` 未动。
2. fupanhui 修复无远端无 PR；夜跑 plist `com.financeworkspace.daily-full-review-sync` → `nightly-full-review-s7.sh`，`FINANCE_WS=/Users/a77/finance-workspace-private`（主树，非 runtime symlink）。
3. #343：gitea head `ad3f4172`；本地 r2 `9c2fff08` 是其重放；merge-tree vs 当前 main 冲突。
4. #365 merge-tree 干净；其改动集与主树脏区重叠（`复盘/` 5+ 文件）。
5. 近两日 spec 落地核对：披露扫描 P0/P0.5/P1-① 全落地（母稿 R5 于 `run_20260826_122832_875134` 首次真过）；替补观察探针三片全合全切；题材信封收口 #381/#383 已切；读向闸 #391/#393 已合（台账 pending 等 live 自然样本）。
6. **盘点自纠**：台阶轨迹组件**已在 main/8792**（#389 merge `bcd0b211`，`52eba880` 是 `fbdbbfd2` 祖先）——同日早先盘点把它误列为「做了没合」，任何后续清单不得再报。
7. 盘中 L2 的 P0 前置是 ClickHouse 鉴权（Code 516 复现），不是仓内代码缺口。
8. 其余 19 张 open PR（#122–#308）全部更新于 08-22 之前，属历史积压，不在本队列。

## 4. 红线

- 合并任何 PR 前跑本机等价检查（ruff + pytest 定向/全量）；带红不合。
- 不 force push（rebase 产物 push 新分支 `r3`）。
- 覆盖或丢弃主树里认领不清的改动前必须问用户。
- 动 8792 前写回滚锚 + 账本 record/check + readiness 13/13。
- 8796 / 8802 不碰。

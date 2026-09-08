# 工单 #38：运行底座 P0–P2 三张 PR 前向合并、门禁、合入确认与 8792 切流 + `kill -9` 演练

> 日期：2026-09-08
> 上游：`2026-09-07-runtime-base-endstate-design.md`（母单 #27；§6 分阶段、§7 生产接线与切流、§12 待拍板）；子单 #28（P1）`2026-09-07-runtime-base-p1-messages-cancel-workorder.md`、#29（P2）`2026-09-07-runtime-base-p2-durable-store-workorder.md`；切流规程 `docs/workbench/canonical-8792-cutover.md` + 最近一次实操收据 `docs/verification/2026-09-08-cutover-0908b.md`（五步 + 三项验证的现行写法）；验收规程 `docs/workflows/acceptance-workflow.md`
> 优先级：**P0**——dsh / pi 运行底座这条线一行代码都还没进 main；P3 / P4 两张预立单（#30 / #31）都等它
> 规模：小到中单（一天；等待用户确认的时间不算）
> 分支：**不开新分支**——在三张 PR 各自的分支上做前向合并；切流记录走 `docs/cutover-0908c`
> 依赖：无代码依赖。**两处要用户**：① 三张 PR 的合入确认（AGENTS.md：合 main 必须等用户确认）；② P2 切流后的 `kill -9` 演练要用户在场（母单 §7）
> 并行冲突：三张 PR 都改 `docs/superpowers/specs/2026-09-01-workorders-INDEX.md`，与本批其他工单（#34–#40 也要登记 INDEX）必然再冲突一次——**规则：谁后合谁解，只加行不改行**

---

## 0. 一句话

P0（#620，模型可见即已落账 + 三张目录，零行为改动）、P1（#624，消息类型 / `CancelCause` / 两码拆分，唯一一格模型可见改动已跑过 live 探针）、P2（#638，JSONL durable store + `EpisodeState` + `restore`，门禁 8063P/0F）三张 PR 代码都已写完，但**全部落后 main 41 个提交、全部在 INDEX 文档上冲突、没有一张合入**。本单把它们按 P0 → P1 → P2 顺序前向合并到最新 main、逐张跑门禁、逐张请用户确认合入；P2 是真行为改动，合入后单独切一次 8792，切后按母单 §6.3 做 `kill -9` 演练验 `restore`。

---

## 1. 现状 [实测 2026-09-08]

| PR | 分支 | head | 对 `gitea/main@8e452e72` | 冲突文件 | 备注 |
|---|---|---|---|---|---|
| #620 P0 | `spec/runtime-base-endstate` | `3d4a254cd4c6` | behind 41 | `2026-09-01-workorders-INDEX.md`（仅此一处） | 零行为改动；无独立 worktree（评审树 `~/fwp-wt-review-620-624-0907` 是 detached 快照） |
| #624 P1 | `feat/runtime-base-p1-messages-cancel` | `794d6634032a` | behind 41 | 同上 | 叠 #620；树 `~/fwp-wt-runtime-base`。live 探针已跑：两臂 `model_finish`、答案同、`tool_not_dispatched` 未触发（实授窗 529s）；对照唯一红 = 台架 shim 不绑 `sub_research`（仓外，等用户） |
| #638 P2 | `feat/runtime-base-p2-durable-store` | `a0ff826c7d1a` | behind 41 | 同上 | 叠 #624；树 `~/fwp-wt-runtime-base-p2`。门禁 8063P/0F/77S（收据 `20260907T102315Z-e59f03ea.json`）；生产装配 `JsonlEpisodeStore(resolve_episode_store_root())`：`FORESIGHT_EPISODE_STORE` → `$FINANCE_WS/state/episodes` → `~/.finance-runtime/episodes`；readiness `open_episodes` 只登记不自动恢复 |
| 8792 | — | `0060da5c1a08`（0908b） | 落后 main 一档（#661 g05） | — | 回滚锚 `~/.finance-runtime/cutover-20260908b-judge-window-rollback-8792.txt` |

冲突探测命令（本机算，不信 Gitea 的 `mergeable`）：`python3 scripts/gitea_pr.py conflict-check --head gitea/<branch> --base gitea/main`。09-08 三张全部只报 INDEX 一处。

§12 五题状态：1（JSONL）/ 3（只登记）按推荐已执行；2（P1 live 探针）已做；**4（P3 Workbench `steer` 端点本轮做不做）、5（编号）未拍**——本单只把第 4 题作为「切流后请用户拍」列出，不替拍。

---

## 2. 步骤

### 2.1 前置（AGENTS.md「开工前必查」）

每棵树先 `git worktree list` + `git status --short` 逐条认领；`~/fwp-wt-runtime-base` 与 `~/fwp-wt-runtime-base-p2` 若有他人脏文件，**不动它们**，另建干净树：`git worktree add ~/fwp-wt-rb-p0 spec/runtime-base-endstate` 等。全部用 `.venv-workbench/bin/python`。

### 2.2 前向合并（不 rebase、不强推——沿 P2 交接「三级前向合并，不改写历史」）

```text
1. 在 #620 分支：git merge gitea/main → 解 INDEX 冲突（保留 main 的 #32 行 + 分支的 #27–#31 行，按号排序；只加行不改行）→ 门禁 → push
2. 在 #624 分支：git merge <#620 分支>（此时已含 main）→ 若 INDEX 再冲突同法 → 门禁 → push
3. 在 #638 分支：git merge <#624 分支> → 同法 → 门禁 → push
```

每张合并后重跑 `conflict-check`，应为 `clean=true`。

### 2.3 门禁（每张各一次，干净树）

```bash
.venv-workbench/bin/python -m ruff check .
env -u MARKET_FEATURE_STORE_DB .venv-workbench/bin/python -m pytest -q          # 与 0908b 收据同条件
cd intelligence/webapp && pnpm lint && pnpm typecheck && pnpm test && pnpm build
.venv-workbench/bin/python scripts/check_test_receipt.py --expect-revision HEAD --base-drift-max 5
```

红集与 `~/.finance-runtime/test-receipts/` 最近一份 main 收据比：**只许相同或更少**；多出来的红逐条归因（P1 交接记过 4 条接缝断言已修，别再当新红）。目录保鲜 `scripts/gen_runtime_catalog.py --check` 一致（该脚本随 #620 进来，main 上还没有）。

### 2.4 合入（**每张都要用户确认**）

`python3 scripts/gitea_pr.py merge <n>` 先干跑打印，用户说「合」再加 `--yes`。顺序 #620 → #624 → #638；前一张合入后，后一张再跑一次 `conflict-check`（应仍 clean）与一次快门禁（ruff + 目标测试子集 `test_episode_messages / test_episode_store / test_episode_restore / conformance/`）。#620、#624 零 live 判据，**不切 8792**；三张全合后才切。

### 2.5 切流 0908c（P2 是真行为改动，单独一刀）

照 `canonical-8792-cutover.md` §1–§6 与 0908b 收据的五步：

1. 回滚锚先写：`~/.finance-runtime/cutover-20260908c-runtime-base-p2-rollback-8792.txt`（回 `0060da5c1a08` 或当时的 8792）。
2. `git worktree add --detach ~/.finance-runtime/finance-workspace-<main12> <main_sha>`；在快照树里跑一遍 §2.3 门禁（在主检出跑 `check_test_receipt` 会把主检出 HEAD 当「当前」——0908b 踩过）。
3. `launchctl bootout` → `launchctl print` 2s 后确认注销 → `ln -sfh` → `audit_deploy_ledger.py record --action switch --port 8792 --ledger ~/.finance-runtime/deploy-ledger.jsonl`（从新快照取脚本）→ `launchctl bootstrap`。
4. 三项验证：readiness **13/13**（新增 `open_episodes` 键应为空列表）；health 三读 `source_revision / source_dirty=False / code_matches_repo=True`；grounded 探针 `smoke_workbench_self_use.py --user probe-cutover-0908c --question "长电科技怎么看"`，要求 `completed / judge passed / degrade_count=0 / gate_receipt.rev=<main12>`，并确认 `~/.finance-runtime/episodes/`（或实际解析出的 store root）里出现该 episode 的 JSONL。
5. **`kill -9` 演练（用户在场）**：再发一发探针，在 `tools_pending` 或 `model_pending` 阶段对 workbench 进程 `kill -9`（PID 取 `launchctl print` 里的）；`launchctl kickstart -k`（或 bootstrap）重启；验：(a) `/api/health/ready` 的 `open_episodes` 列出该 episode；(b) `ContinuousAgentEpisode.restore(episode_id, store)` 给出 `ResumePlan` 或合成 `finish{stop_reason=cancelled|interrupted}`（母单 §6.3 三行策略；v0 `restore` 只给 `ResumePlan`，重新开车是 P4）；(c) JSONL 末行若撕裂被整行丢弃（`EpisodeStore` 的读法）；(d) 前端对该会话显示可解释状态而非 500。读数逐条进收据。
6. 收据 `docs/verification/2026-09-08-cutover-0908c.md`；`inflight/main.md` 加一段；INDEX #27 / #28 / #29 行状态改「已合 + 8792 已切」；账本行按原参数补齐。

### 2.6 切流后请用户拍（本单不替拍）

- §12 第 4 题：P3 收件箱的 Workbench `steer` 端点本轮做不做（推荐：底座 + CLI 先做，端点等 Alpha 反馈）→ 决定后派 #30。
- 仓外 `finance-base-ab/shape_lib/reference_loop_arm.py` shim 绑不绑 `sub_research`（不绑则契约授 `sub_research` 时 ±3 门永远红）。
- 磁盘：`~/.finance-runtime/episodes/` 增长速率（切后 24h 读一次大小写进收据），要不要滚动清理是 P4 或运维单。

---

## 3. 验收

1. 三张 PR `conflict-check` 全 `clean=true`；INDEX 里 #27–#33 行齐全、按号排序、无重复。
2. 三张各有一份干净树全量收据，红集 ⊆ 基线红集；`gen_runtime_catalog.py --check` 一致。
3. 三张按序合入（`gitea_pr.py show` 三张 `merged=true`），每次 `--yes` 前有用户在对话里的确认记录（交接里写时间）。
4. 8792 切到含 #638 的 main：readiness 13/13、health 三读一致、探针 grounded 通过、store 目录有 JSONL。
5. `kill -9` 演练四项读数进收据；任一不通过 → 按 §7 回滚到锚点并写明原因，**不留在坏版本上等修**。
6. `inflight/main.md`、INDEX、账本三处回写一致（`scripts/worktree_board.py` 显示三棵树「补丁已在基线」）。

---

## 4. 非目标 / 红线

- ❌ 不 rebase、不 `push --force`；不改写三张 PR 的历史。
- ❌ 未经用户在对话里确认，不执行 `gitea_pr.py merge --yes`；不因「门禁绿了」自行合入。
- ❌ P0 / P1 合入后不单独切 8792（零 live 判据，随 P2 一起）。
- ❌ 演练时不删 `~/.finance-runtime/finance-workspace-*` 任何快照树；回滚只切软链。
- ❌ 不开工 P3 / P4（要 §12 第 4 题）；不改 `_TOOL_CONTRACTS` 文本；不动 `finance-base-ab`（仓外）。
- 主检出 `/Users/a77/finance-workspace-private` 有他人未提交的 BP 文档与 spec 改动，**不在里面跑全量对账、不动它的文件**。

---

## 5. 教学注

- **前向合并 vs rebase**：rebase 让历史好看但要 `--force` 推，三张互相叠的 PR 一旦 force 就要三张同时重推，评审过的 commit sha 全变；前向合并多几个 merge commit，但每个 sha 不变、评审记录可追、失败可逐步回退。多人 / 多 agent 共用分支时前向合并几乎总是更安全——这也是 P2 交接选它的原因。
- **为什么 P2 单独切、P0/P1 不切**：切流的回滚粒度就是归因粒度。零行为改动和真行为改动混在一刀里，出问题时分不清是哪层；分开切，8792 出事只有一个嫌疑人。`inflight/main.md`「切流分两批」那条决策是同一原则。
- **`kill -9` 演练测的是什么**：不是「能不能重启」，而是「durable 事件与 `EpisodeState` 在崩溃点上是否一致」——意图有、结算无的那一种不确定是否被正确合成，撕裂末行是否被丢弃而不是被解析成半条事件。这是 pi §4.4 的 Tier A 场景在生产上的一次真跑，单测夹具替代不了进程真死。

---

## 6. 交接要求

- 切流收据 `docs/verification/2026-09-08-cutover-0908c.md`；`inflight/main.md` 一段；INDEX #27–#29 状态；`worktree_board.py` 复跑确认。
- 若合入过程中发现三张 PR 中任一张需要代码改动（不是解冲突），停下写进交接，不在本单里修——那属于对应子单的作者。

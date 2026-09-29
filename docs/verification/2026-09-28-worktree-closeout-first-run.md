# worktree_closeout.py 首轮真跑回执（2026-09-28 20:39–20:43 CST）

## 授权与性质

- 用户原话（逐字）：「合并，然后继续推进」。出处：Claude Code 桌面会话 `local_e35bb047-fb40-46de-9977-143b592b6521`，约 20:30 CST，回应 PR #955 汇报里待定的两项：合并 #955；「合入后先挑一棵确定可拆的树真跑一次 dry-run → apply，核对收据与 df，再批量」。
- 性质：**受托代拍**，每棵的理由写进工具收据；用户可一句话推翻（走 `record-correction`）。本回执写完不改。
- 不在授权内（只列不做）：别的会话的在途线、Claude 会话树、FinArena #82 保留件、现役与指定回滚锚。
- 工具版本：`gitea/main` = `20d49970a`（#955 合入）。收据目录 `~/.finance-runtime/reviews/worktree-closeout-20260928/`。

## 拆了 3 棵

| 树 | 理由（摘要，全文在收据） | 钉（本地 = Gitea） | 归档 |
|---|---|---|---|
| `~/fwp-wt-8792-harness-0928` `[fix/8792-harness-0928]` | #952 已合入并部署 8792，收尾文档已进 main；cherry+0、空闲约 9 h | `refs/archive/wt-20260928/fwp-wt-8792-harness-0928` → `7ef3e08d7` | `residue.tar.gz` 253 个文件；4 份库 clonefile |
| `~/fwp-wt-8792-harness-closeout-0928` `[docs/8792-harness-closeout-0928]` | 收尾文档分支已合入（`4de44009a`）；树内只有 e2e 测试产物 | `…/fwp-wt-8792-harness-closeout-0928` → `4de44009a` | 251 个文件；3 份库 clonefile |
| `~/.finance-runtime/finance-workspace-7a405e1b096b` | 旧回滚锚已被取代：`docs/handoffs/2026-09-28-8792-harness-deployment-closeout.md` 写明新锚为 5a5e；账本 8792 现役 8e45（04:29Z 切入），7a40 末次使用 09-27 17:11Z | `…/finance-workspace-7a405e1b096b` → `7a405e1b0` | 无残留 |

- 收据：第一批 `dry-20260928T203918.json` → `apply-20260928T203938.json`（1 棵）；第二批 `dry-20260928T204220.json` → `apply-20260928T204236.json`（2 棵）。
- 卷可用（statvfs）：第一批 17.0 → 17.9 GiB，第二批 17.4 → 18.1 GiB。两批之间 17.9 → 17.4 是别的进程在写，所以差值只作近似，不当成本工具的精确节省。
- 独立核对（不看工具自报）：三棵目录不在、`git worktree list` 无登记；三个钉 `git ls-remote gitea` 与本地一致；分支 `fix/8792-harness-0928`、`docs/8792-harness-closeout-0928` 保留；两个 tar 的成员数与计划一致；7 份库 `shasum -a 256 -c MANIFEST.sha256` 全 OK。

## 没拆的 33 棵（第二批拆完时的看板；别的会话同时在建树，棵数会漂）

| 类 | 树 | 为什么留 |
|---|---|---|
| 今天 Codex 的在途线 | `fwp-wt-8792-authoring-{baseline,candidate,method}-0928`、`fwp-wt-8792-answer-capability-0928`、`fwp-wt-8792-resume-0928`、`fwp-wt-8792-answer-baseline-0928` | 别的会话在途；`answer-baseline` 是 14:54 会话为 WIP #956 建的对照基线（15:54–17:04 仍在里面跑基线对比） |
| FinArena #82 | 6 棵 | 用户原话「执行」：保留分支、原工作树和原件 |
| Codex Knevo | 4 棵 | 在途 |
| 预览 / 新线 | `fwp-wt-workbench-tech-premium`、`fwp-wt-board-calendar` | 8899 预览待用户定；board-calendar 是别的会话的新线 |
| 本会话派出的任务 | `.claude/worktrees/nervous-lederberg-184f79`、`pi-anchor-0928/tree`、`.claude/worktrees/pi-anchor-nested-0928` | 修 `test_pi_review_repair` 嵌套位置假红的任务正在跑 |
| 夜跑与启动器 | `finance-workspace-7afe37be1913`、`finance-s7-sync`、`finance-nightly-installer-79861f07e485`、`finance-sync-fe9fdbfd70a6`、`~/finance-workspace-sync` | 被启动器引用或锁 retain |
| 生产快照 | `8e45`（8792 现役）、`5a5e`（指定回滚锚）、`40fd`（8796 sidecar） | 现役与回滚锚 |
| Claude 会话树 | 本会话、`unclosed-session-stats-838ac4`、`pi-session-cleanup-479dc5` | 工具硬阻塞：到各自会话里归档 |
| 主树 | `~/finance-workspace-private` | 永不拆 |

## 需要还原时

`git worktree add --detach <原路径> <钉>`；残留 `tar -xzf <归档>/residue.tar.gz -C <原路径>`；数据库按 `clones/MANIFEST.sha256` 的相对路径 `cp -c` 拷回。

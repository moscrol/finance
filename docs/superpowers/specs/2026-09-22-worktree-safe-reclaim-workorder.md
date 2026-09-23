# 2026-09-22 已合入干净 worktree 安全回收工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
本单只做「删已进 main 的干净树」这一件事。**删除动作前必须把最终名单贴给用户并拿到一句确认**。与 #63（推送未推分支）串行：先推后删。

## 背景与动机

- 2026-09-22 主仓 `git worktree list` 252 棵（155 棵 `~/fwp-wt-*`、83 棵 `~/.finance-runtime/**`、3 棵 `/private/tmp/**`）。当天磁盘两次逼近满盘（最低 1–2 GiB），多棵树并跑全量把临时目录吃到约 20G，联合基线 Python 叶被 SIGTERM 一次，另一次触发磁盘停止线。晚间清理后剩 25 GiB，仍是 95%。
- 09-22 已有两份候选名单，都**未执行**：`/tmp/wt-safe.txt`（169 行，19:32 生成，口径「干净且 HEAD 已进 main」）与 `~/.finance-runtime/reviews/worktree-reclaim-20260922/`（`triage.json` 251 项，字段 `path / branch / head / dirty / merged / in_use / age_days`；`reclaim.txt` 38 行；`evidence-keep.txt` 7 行）。两份口径不同，都要以接手时刻重算为准。
- **已定的形态决策**：判「可删」用四条**同时成立**的机器判据，不看名字：(1) `git -C 树 status --short --ignored` 无未跟踪、无修改（`__pycache__` 除外）；(2) `git merge-base --is-ancestor <HEAD> gitea/main` 为真；(3) 树路径不出现在任何 `~/Library/LaunchAgents/*.plist`、`~/.local/bin/start-finance-workbench`、`/Users/a77/finance-workspace-runtime` 软链目标、`~/.finance-runtime/finance-sync-*` / `finance-workspace-*` 快照名里；(4) 无进程 cwd 在该树内（`lsof +D` 或 `ps -o cwd`）且树内最近 mtime > 24h。`~/.finance-runtime/reviews/**` 下的树默认**保留**：它们是冻结的 QC 证据树，只有其同目录 README 明写「可回收」才进名单。

## 目标

1. 一张按上述四判据重算的名单 `docs/verification/<日期>-worktree-reclaim/candidates.json`：每棵树四个判据的原始读数，另列「保留原因」给未入选的树。
2. 用户确认后 `git worktree remove <路径>`（不带 `--force`），`git worktree prune`；对应本地分支仅当 `merged` 且 Gitea 无 open PR 引用时 `git branch -d`（不 `-D`）。
3. `df -h /System/Volumes/Data` 删前删后各一次；释放量写进 README（APFS clonefile 共享块可能让实际释放小于账面）。
4. 顺手登记但不处理：dirty 树、未合入树各多少棵，按最近提交时间排序给用户看。

## 非目标（写死认领）

- ❌ 不删 dirty 树、未合入树、`~/.finance-runtime/reviews/**` 证据树（除 README 明写可回收）、8792 快照与 sync 代码根、主检出 `/Users/a77/finance-workspace-private`。
- ❌ 不删 `~/.finance-runtime/test-receipts/`、`~/.finance-runtime/reviews/` 里的任何文件。
- ❌ 不清 `node_modules` / `.venv` 之外的缓存；前端可再生检出的处置写进名单由用户决定。
- ❌ 不删 DuckDB 备份副本（`db/*.bak-*`、`tmp/**/*.duckdb`）：归 #61，且 `tmp/…/production-before.duckdb` 是唯一完整回滚点。
- ❌ 不用 `--force`，不 `rm -rf` 代替 `git worktree remove`。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/.finance-runtime/reviews/worktree-reclaim-20260922/triage.json`、`reclaim.txt`、`evidence-keep.txt`、`audit-report.json` | 上一轮的字段与判据，复用形状不复用结论 |
| `/tmp/wt-safe.txt` | 19:32 的 169 棵候选，对照用 |
| `python3 scripts/worktree_board.py` | 全仓合入看板（合入状态口径） |
| `~/Library/LaunchAgents/*.plist`、`~/.local/bin/start-finance-workbench`、`readlink /Users/a77/finance-workspace-runtime` | 判据 (3) 的排除源 |
| `docs/handoffs/inflight/*.md` 中出现的树路径 | 有在途交接指向的树不删（grep 路径） |
| `~/.pi/agent/sessions/**` 文件 mtime | 仍在写的会话对应的树不删 |

## 步骤

1. 开工三连；`git worktree prune --dry-run` 先看已经失效的登记项。
2. 写一次性脚本（放 `docs/verification/<日期>-worktree-reclaim/collect.py`，不进 `scripts/`）逐树采四判据，输出 `candidates.json`。
3. 名单贴用户：路径、HEAD、分支、最近 mtime、四判据；等确认。
4. 逐棵 `git worktree remove <路径>`；失败（非空/脏）即跳过并记录，不加 `--force`。
5. `git worktree prune`；分支按目标 2 处理；`df` 后测。
6. README + INDEX #64 行。

## 验收

- [ ] `candidates.json` 每棵树四个判据齐全；被删的每棵四个全真。
- [ ] 阳性对照：名单生成时故意加入一棵已知 dirty 树的路径，脚本必须把它排除并给出原因。
- [ ] 删后 `git worktree list` 不含已删路径；`git worktree prune` 无残留。
- [ ] 8792 `/api/health` 前后 `source_revision` 不变；`launchctl print` 两个夜跑 job 仍 loaded。
- [ ] `df` 前后读数与释放量落 README。

## 红线

- 删除前必须有用户对最终名单的确认原话，写进 README。
- 不 `--force`、不 `rm -rf`、不 `git branch -D`。
- 不动主检出树、生产快照、sync 代码根、证据树、备份库。
- 只用 pathspec 提交名单与 README；不写明文密钥。

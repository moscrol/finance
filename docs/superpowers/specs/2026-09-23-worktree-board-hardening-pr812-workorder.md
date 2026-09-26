# 2026-09-23 工作树看板加固与归属收口残件工单（#84）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
来源：`docs/handoffs/2026-09-23-orphan-inventory.md`。**是 #64（worktree 安全回收）的前置**：#64 的四判据依赖看板不误判，本单先落地。与 #83 同源（6eb12 组合）但可并行。

## 背景与动机

09-21 的归属盘点发现 `scripts/worktree_board.py` 会把「失效路径 / 父仓误识别 / cherry 或 status 查询失败」混进可拆候选，PR **#812**（`ops/worktree-ownership-closeout-0921`）修了这三类误判、把任何未提交文件都设为阻止拆除、全扫描冻结基准 SHA，并带 9 个能抓红的反例测试（旧脚本上 18P/9F）。v4 组合工程全绿，K3 复审 ENOSPC 中断，标 BLOCKED，之后无人接手。

今天核对 [实测]：#812 只有 2 个非文档文件（`scripts/worktree_board.py`、`tests/test_worktree_board.py`），对当前 main **1 处冲突在 `worktree_board.py`**（main 上的看板此后也改过：`kind` 分类、`--this`、超时）。同日合入的 #876（`fix/disk-burn-cow-snapshots-0923`）新增了「批量拆 detached 门禁树」工具——与本单目标重叠，先对照再动手，避免第三份实现。

盘点还留下 12 棵同源证据树（`fwp-wt-ownership-*-0921`，7 条 `baseline/ownership-*` 分支 + 5 棵 detached），每棵 dirty=2；它们是审查现场，不是废树，处置规则在本单第 4 目标。

## 目标

1. `#812` 的三类误判修复 + 9 个反例测试前向到当前 main，与 #876 的工具**去重**（同一判据只留一处实现，另一处删掉或改为调用）。
2. 看板输出新增两列：`unknown_reason`（为何判不出）与 `blockers`（哪一条未提交文件 / 进程 / plist 引用阻止拆除），`--json` 同步。
3. 干净树四叶收据；合入等用户确认。
4. 12 棵 ownership 证据树：逐棵核 dirty 的 2 个文件是什么（预期是同一对未跟踪文件）、HEAD 是否在 `baseline/ownership-*` 分支上；把「树路径 → 分支 → 证据目录 → 可否拆」写成表贴 #812 评论，**拆除本身归 #64**（需用户确认名单）。

## 非目标

- ❌ 删除任何 worktree（#64，删前用户确认名单）。
- ❌ 重开 K3 复审（#75）。
- ❌ 改 `scripts/session_facts.sh` 的注入格式（它调用看板 `--this`，只要 JSON 键不变就不用动）。
- ❌ 处理 #813 的回填代码（#83）。

## 证据路径表

| 文件 | 看什么 |
|---|---|
| `python3 scripts/gitea_pr.py show 812` 及评论 | 修了哪三类误判、9 个反例、v4 组合读数、K3 中断 |
| `gitea/ops/worktree-ownership-closeout-0921:docs/handoffs/inflight/ops-worktree-ownership-closeout-0921.md` | 「本 part 已收尾、复审暂停」的边界 |
| `gitea/ops/worktree-ownership-closeout-0921:docs/handoffs/2026-09-21-worktree-ownership-closeout.md` | 322 条历史采样按线登记 |
| `git diff gitea/main...gitea/ops/worktree-ownership-closeout-0921 -- scripts tests` | 净 diff |
| `git log gitea/main -3 --format='%h %s' -- scripts/worktree_board.py` | main 侧后续改动，解冲突要保留 |
| `git show gitea/main --stat`（#876 合并提交 `bbd53487f`） | 新增的批量拆树工具在哪、判据是什么 |
| `git worktree list \| grep ownership` | 12 棵树现状 |
| `docs/superpowers/specs/2026-09-22-worktree-safe-reclaim-workorder.md` | #64 的四判据，本单输出要能直接喂它 |

## 步骤

1. 开工三连 + `git fetch gitea`；`git worktree add /Users/a77/fwp-wt-board-hardening-0923 gitea/ops/worktree-ownership-closeout-0921`。
2. 先读 #876 的拆树工具与 main 侧 `worktree_board.py` 三个提交，列「判据 × 实现位置」表，决定去重方向。
3. `git merge gitea/main`，按意图解 `worktree_board.py`；跑 `tests/test_worktree_board.py`（9 个反例必须仍红→绿）；`python3 scripts/worktree_board.py --this` 与 `--json` 冒烟。
4. 加 `unknown_reason` / `blockers` 两列 + 测试。
5. 四叶；贴读数；12 棵树的处置表贴 #812 评论并抄一份到 #64 工单文件末尾「候选名单输入」节。
6. inflight ≤3K；INDEX #84 状态行。

## 验收

- [ ] `merge-tree` 干净；四叶收据 revision == head、`dirty=false`。
- [ ] 阳性对照：把「未提交文件阻止拆除」判据注释掉，至少一条反例测试红。
- [ ] `--json` 每棵树有 `unknown_reason`（可为空串）与 `blockers`（列表）。
- [ ] 去重表：同一判据不存在两份实现（grep 证据贴 PR）。
- [ ] 12 棵树处置表 12 行，每行有 dirty 文件名与「可否拆」及理由。
- [ ] INDEX #84 行已改。

## 红线

- pathspec 提交；合 main 等用户确认；不强推；关闭必留指针。
- `.venv-workbench/bin/python`。
- 不 `git worktree remove` / `prune` 任何树；不 `branch -D`。
- 看板输出禁止把「判不出」回落成更旧的 revision（memory：`fix/board-unattributed-switch`）。

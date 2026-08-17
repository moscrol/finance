# 2026-08-16 安全 ref `prerebase/dsh-seams-e21c50bf` 删除交接（须用户手动）

roadmap_ref: L1-DSH

一句话：保留条件已到期（#61 已合 main），内容 14 个提交全部 patch-equivalent 在 `gitea/main`；agent 侧红线 hook 挡住一切含删分支字样的命令，删除只能用户手动执行。本文件给证据、命令、删后验证和记账动作。

证据等级：**[实测]** = 2026-08-16 质检现场跑过命令/读过产物。

## 1. 保留条件与到期证据

- 原始保留条件（`2026-08-16-r24-deploy-window.md` §dsh/安全 ref）：「合 main 或 §3 不再需要旧 SHA 之前不删」。
- **#61 已合** [实测]：`feat/dsh-seams-onto-main` 经 PR #61 合入 `gitea/main`（merge commit `2a2523f7`，第 1–7 步 + 冲突矩阵）。
- **内容零残留** [实测]：`git cherry gitea/main prerebase/dsh-seams-e21c50bf` 共 14 个提交，`+`（未落 main 的 patch）为 0 个——安全 ref 上没有任何主线之外的内容。
- ref 指向 `e21c50bfdbdbdcc192956bd8f80a99d69d6d84ea`，ref 名自带 tip SHA，删 ref 不丢可追溯性（SHA 已写进本文件与 R-24 handoff）。
- 没有任何 worktree 挂在该分支上 [实测]（`git worktree list` 无此分支）。
- 薄账决策队列已有行：「安全 ref 条件已满足；hook 挡住 agent 删，仍须用户手动 | 卡在用户」。冲突矩阵 row 9 同。

## 2. hook 挡 agent 的现场证据

2026-08-16 质检时，agent 的一条**只读检索命令**仅因文本中含 `branch -D` 字样即被 PreToolUse 红线拦截（红线规则 `branch[[:space:]]+-D`）。删除类命令（本地删分支、远程删 ref）agent 一律执行不了，这是设计行为，不要绕。

## 3. 用户手动执行（两条命令）

```bash
git -C /Users/a77/finance-workspace-private branch -D prerebase/dsh-seams-e21c50bf
git -C /Users/a77/finance-workspace-private push gitea --delete prerebase/dsh-seams-e21c50bf
```

- 顺序无所谓，两条都要执行（本地和 gitea 各有一份）。
- 若想留一个比 SHA 记录更硬的解引用锚（可选，非必需）：删除前 `git tag archive/dsh-prerebase-e21c50bf e21c50bfdbdb` 本地打 tag，不推远程。默认不需要——内容已全部在 main。

## 4. 删后验证

```bash
git -C /Users/a77/finance-workspace-private for-each-ref | grep prerebase   # 应为空
git -C /Users/a77/finance-workspace-private ls-remote gitea 'refs/heads/prerebase/*'   # 应为空
```

## 5. 删后记账（冲突矩阵 row 8：薄账归观测台 PR）

- 另开观测台 PR：把 `docs/roadmap.md` 决策队列「安全 ref …仍须用户手动」行落为已决（或清行）。
- 同一 PR 顺带更正两处已过时措辞（见 2026-08-16 质检）：
  1. 薄账头部「未闭合的最低层:P2（口径=dsh P0 五步完成数/5…）」——括号里是 P1 的口径，P2 的口径是 trace_depth 档位+盲区清单，P1 闭合时忘了换。
  2. L1-8792 行「其后 docs-only tip 不追切」——437cd5e9 之后的 tip 已含 #60/#61/#63/#65/#67 特性代码，不再是 docs-only；「不追切」各单项决策仍有效，措辞该改成「其后 tip 不追切（含特性合并）」。

## 6. 本交接不做的

- 不动 `feat/dsh-absorption-p0-seams`（本地 4 个草稿提交的处置见 `2026-08-16-dsh-step8-expand-sample-window.md`）。
- 不动 8792，不碰 `fwp-wt-dsh-seams` worktree。
- 不改 `retain_dsh_runtime`（仍 false，翻转依据只能来自第 8 步对照收据）。

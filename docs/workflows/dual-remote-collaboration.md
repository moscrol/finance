# Gitea 与 GitHub 跨机器协作

适用：全局盘点、云端 agent 接续、分支交接、主干同步。Gitea 是集成主干；GitHub 是云端协作入口。同一条共享分支在两端使用同一提交，不建立两套独立合并历史。

## 先核对三个层次

1. **远程主干**：`gitea/main` 与 `origin/main` 的完整 SHA 是否相同。
2. **工作分支**：列出两端所有 branch heads，按分支名比较完整 SHA；包含 `origin/claude/*`、其他云端分支及两边开放 PR。PR 编号必须带平台，不能把 Gitea #988 链到 GitHub #988。
3. **本地现场**：`git worktree list`、`git status --short`。未提交修改不属于远程分支，主目录脏时不直接 pull、reset 或覆盖。用干净工作树接最新主干，原作者的修改逐文件认领。

在两端可达的机器上先执行：

```bash
git fetch --no-tags gitea
git fetch --no-tags origin
git ls-remote --heads gitea
git ls-remote --heads origin
python3 scripts/worktree_board.py
```

`worktree_board.py` 的主干基线默认是 Gitea；它不能替代 GitHub 云端分支清单。只看 PR 也不完整：工作分支可能尚未开 PR。云端连不到 Gitea 时，报告覆盖边界，并引用最近一次双端核对的 SHA；不能写“已检查全部”。

## 传递成果

### 云端分支送回 Gitea

在能访问两端的机器上，先核实目标分支不存在或可快进，再显式复制该分支。以下是本次已经核实的分支示例：

```bash
branch='claude/test-isolation-tmpdir-hw7e8h'
git fetch --no-tags origin
git push gitea "refs/remotes/origin/$branch:refs/heads/$branch"
git ls-remote --heads origin "$branch"
git ls-remote --heads gitea "$branch"
```

已有同名分支若发生分叉，先保留两端提交并人工判断，不能用 force 或 mirror 覆盖。复制到 Gitea 是交接，不代表通过验收或合入 main。两端分支变更后重新读完整 SHA，不能只信 push 退出码。

### 已合主干送到 GitHub

只有已经按本仓规则验收、获准合入 Gitea 的主干才进入这一步。确认内容适合目标仓库可见性，并确认 GitHub 主干是其祖先；若两端已经同 SHA，无需推送：

```bash
git fetch --no-tags gitea
git fetch --no-tags origin
git merge-base --is-ancestor origin/main gitea/main
# 上一步为 0、确有差异且已确认发布范围时：
git push origin refs/remotes/gitea/main:refs/heads/main
git ls-remote --heads gitea main
git ls-remote --heads origin main
```

目标端的分支保护仍需满足。保护拒绝时补齐对应流程，不能通过 force 或临时拆保护同步。合并、分支传递和生产部署是三件事：只同步 Git 不重启服务，不把工作分支并入 main。

## 交接可达性与公开范围

- 每次交接写明仓库、分支、完整 SHA、实现/验收/合入/部署各自状态、下一步和证据范围；推送后用远程 API 或网页回读文件，并提供固定提交链接。
- 检查当前远程 URL 与仓库可见性，不沿用旧仓名。公开 GitHub 只接经过检查的代码和共享文档；私有机器路径、运行原件、用户内容与内部证据保持私有。不要为同步新文档而整枝推送包含内部历史的本地研究分支。
- 私有归档分支可仅存在 Gitea，必须在盘点中明确列为例外；共享分支要求两端同 SHA。不要配置“无条件双推全部分支”，也不使用 `git push --mirror` 追求表面一致。
- 收据属于具体 revision 和环境。跨机器比对全量结果时，同时核实 Python、依赖、测试收集面及实际调用链；代码相同不代表环境相同。

## 完成标准

- 两端共享分支同名、同完整 SHA；私有例外有明确记录。
- Gitea 与 GitHub 的开放 PR 分开列明，云端未开 PR 分支也有去向。
- 接手者能从远程读取交接；只存在于本机的文件链接不算跨机交付。
- 未提交修改、仍在运行的测试和生产进程保持原状；清理使用独立的保全与 dry-run 流程。


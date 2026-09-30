# Gitea 与 GitHub 跨机器协作

适用：全局盘点、云端 agent 接续、分支交接、主干同步。Gitea 是集成主干；GitHub 是云端协作入口。同一条共享分支在两端使用同一提交，不建立两套独立合并历史。

## 发布前先查镜像

2026-09-30 实查：本仓 Gitea 有指向公开 GitHub `moscrol/finance` 的 push mirror，`sync_on_commit=true`、定时周期 `8h0m0s`。本轮只查配置，未修改镜像。**本仓的私有 Gitea 不是私有归档边界**：推到它的分支也可能进入公开 GitHub。内部材料保存在本地备份，或另外获准使用的非镜像私有仓库。

后续操作需重新核实 Gitea 仓库的 `/push_mirrors`、两端实际 URL 和最终目标可见性；只记录去凭证后的地址与同步字段。Gitea 的 push mirror 会强制推送，可能覆盖目标仓库变更，不能当作安全的双向协作同步。[官方镜像说明](https://docs.gitea.com/1.25/usage/repository/repo-mirror/)

## 核对远程与本地

在两端可达的机器上执行：

```bash
git fetch --no-tags gitea
git fetch --no-tags origin
git ls-remote --heads gitea
git ls-remote --heads origin
git worktree list
git status --short
python3 scripts/worktree_board.py
```

1. 比较两端所有 branch heads 的完整 SHA，单列各自独有分支与同名分叉；必须包含 `origin/claude/*`。
2. 分别查双方开放 PR。PR 编号带平台；Gitea #988 不能链接到 GitHub #988。未开 PR 的云端分支也要有去向。
3. 未提交修改另行认领。主目录脏时用干净工作树接最新基线，保留原现场；远程同 SHA 不等于本地未提交内容已同步。

`worktree_board.py` 的基线默认是 Gitea，不能替代 GitHub 清单。云端连不到 Gitea 时报告覆盖边界，引用最近一次双端核对的 SHA，不写“已检查全部”。远程 refs 随时可能变化，任何写操作后都要重新核对；一次快照不是持续一致保证。

## 云端成果回收

先 fetch 保留云端提交，核实 Gitea 目标分支不存在或可快进，再显式复制。以下为本次已核对的分支示例：

```bash
branch='claude/test-isolation-tmpdir-hw7e8h'
git fetch --no-tags origin
git push gitea "refs/remotes/origin/$branch:refs/heads/$branch"
git ls-remote --heads origin "refs/heads/$branch"
git ls-remote --heads gitea "refs/heads/$branch"
```

已有同名分支若分叉，保留双方提交并停止该分支同步，人工判断后续归属；不用 force 消除差异。复制到 Gitea 是交接，不代表验收或合入 main。

**现有机制的缺口**：云端只推 GitHub、尚未被取回 Gitea 的窗口内，后台强制镜像可能覆盖其变更。及时回收只能缩短窗口，不能证明并发安全。不要再添加一套相反方向的强制镜像。

本轮已经实际发生回退：云端新增 bca700858 / 3d2b1ba99 被镜像退回旧头，后从本地跟踪日志恢复。盘点要检查 `git reflog show refs/remotes/origin/<分支>` 中的推进和 forced-update，保全本地已取到的更新提交，再判断远端头；两个当前头相同不能证明没有丢失推进。

## 已合主干与共享文档发布

已经按本仓规则验收并获准合入的主干，经现有镜像同步后，读回两端完整 SHA。共享文档先检查内容与整条分支历史是否适合公开，再推 Gitea 并回读 GitHub 文件；无需再配置第二套全量镜像。

镜像未同步时先检查状态与错误，不用盲目双推掩盖失败。若确需显式推指定分支，只在目标是源祖先、发布范围已核实时普通快进推送；保护拒绝就补齐流程，不移除保护或强推。

合并、分支传递和生产部署分别记账。测试侧修复合入后不因此重启生产。

## 长期收敛方案（待确认，未实施）

保留 Gitea 作为唯一集成主干，把现有强制全仓镜像替换为有日志的安全同步：先取回并保全 GitHub 云端分支，再仅快进同步获准共享的分支；遇到分叉、远程不可达或可见性变化就停止对应操作并报告，不自动删分支。main 仍按用户确认与完整门禁合入。

这会改变全仓同步策略，需要单独确认后落地。验收至少覆盖：GitHub 独有分支、同名分叉、并发推进、网络失败、非发布分支不外传，以及两端文件回读。当前只完成本次回收与核对，尚没有该自动流程。

## 交接完成标准

- 两端共享分支同名、同完整 SHA；独有分支、分叉和未提交修改有明确去向。
- 两个平台的开放 PR 分列，接手者能用固定提交链接读取交接。
- 实现、验收、合入、部署状态与证据范围分别写清；收据必须对应 revision、环境和测试收集面。
- 清理采用独立的保全与 dry-run 流程；在跑测试和原作者现场保持原状。

本轮使用现有 Git / 平台 API 核对，不新增会改远程的同步脚本；上述自动化涉及全仓写入策略，留待确认并按分叉/并发情景验收。

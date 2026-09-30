# Gitea 与 GitHub 跨机器协作

适用：全局盘点、云端 agent 接续、分支交接、主干同步。Gitea 是集成主干；GitHub 是云端协作入口。同一条共享分支在两端使用同一提交，不建立两套独立合并历史。

## 当前同步方式

2026-09-30 11:56（Asia/Taipei），按用户“执行”确认，已移除本仓 Gitea→GitHub 的强制 push mirror 配置，回读 `/push_mirrors` 为空。原配置的提交触发和每 8 小时镜像均停用；现在由执行者按需、逐分支普通快进同步，**没有新定时同步任务**。仓库可见性、主干和生产服务未因此改变。

发布前重新核实镜像列表、两端实际 URL 与最终目标可见性，只记录去凭证后的地址。GitHub `moscrol/finance` 当前公开；共享内容及整条分支历史要适合公开。内部审计原件继续本地保全。过去“只推私有 Gitea 就保密”的判断已被自动镜像事故证伪，后续不能只看入口仓的 private 字段。

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

1. 比较两端所有 branch heads 的完整 SHA，单列各自独有分支与同名分叉，包含 `origin/claude/*`。单端缺失要先核删除事件及接替记录，区分新成果与已清理分支；不能自动把另一端所有缺项重新创建。
2. 分别查双方开放 PR。PR 编号带平台；Gitea #988 不能链接到 GitHub #988。未开 PR 的分支也要有去向。
3. 未提交修改另行认领。主目录脏时用干净工作树接最新基线，保留原现场；远程同 SHA 不等于未提交内容已同步。
4. 发现回退时查 `git reflog show refs/remotes/origin/<分支>`，保全曾取到的更新提交。本轮曾出现双方当前头相同、但都退回旧版本的情况；不能只比较两个当前头。

`worktree_board.py` 默认以 Gitea 为基线，不能替代 GitHub 清单。云端连不到 Gitea 时报告覆盖边界，引用最近一次双端核对的 SHA，不写“已检查全部”。

## 云端成果回收

先 fetch 保全云端提交，核实 Gitea 目标分支不存在或可快进，再显式复制。以下为本次分支示例；固定完整 SHA，避免别的 agent 在共享仓再次 fetch 时改变本次推送源：

```bash
branch='claude/test-isolation-tmpdir-hw7e8h'
git fetch --no-tags origin
source_sha="$(git rev-parse "refs/remotes/origin/$branch")"
git push gitea "$source_sha:refs/heads/$branch"
git ls-remote --heads origin "refs/heads/$branch"
git ls-remote --heads gitea "refs/heads/$branch"
```

普通推送遇到非快进会拒绝。保留双方提交并停止该分支同步，人工判断归属；不用 force、带 `+` 的 refspec 或 mirror 覆盖。目标端在操作期间又推进时，重新读取并解释差异，不绕过拒绝。复制分支不代表验收或合入 main。

## 本地共享分支发布

先检查该分支相对主干的全部提交，确认公开范围。按上一节方法读取目标头并核实可快进，随后将同一个固定 SHA 显式推到双方：

```bash
branch='codex/dual-remote-handoff-0930'
source_sha="$(git rev-parse "refs/heads/$branch")"
git push gitea "$source_sha:refs/heads/$branch"
git push origin "$source_sha:refs/heads/$branch"
git ls-remote --heads gitea "refs/heads/$branch"
git ls-remote --heads origin "refs/heads/$branch"
```

两次推送不是一个原子事务。一端成功、一端失败时，记录哪端在哪个 SHA；保留成功端，处理差异后再用普通推送补齐。推送后用远程 API 回读交接文件，提供固定提交链接。

## 已合主干同步

只有已经按本仓规则验收并获准合入 Gitea 的主干才能向 GitHub 同步。取回双方，核实 origin/main 是 gitea/main 的祖先；若已同 SHA，无需推送：

```bash
git fetch --no-tags gitea
git fetch --no-tags origin
git merge-base --is-ancestor origin/main gitea/main
# 上一步成功、确有差异且发布范围已核实时：
source_sha="$(git rev-parse refs/remotes/gitea/main)"
git push origin "$source_sha:refs/heads/main"
git ls-remote --heads gitea refs/heads/main
git ls-remote --heads origin refs/heads/main
```

分支保护拒绝时补齐流程。同步、合并和生产部署分别记账；测试侧修复合入后不因此重启服务。没有用户合入确认，不把工作分支同步操作变成 main 合并。

## 交接完成标准

- 共享分支同名、同完整 SHA；独有分支、分叉和未提交修改有明确去向。
- 双方开放 PR 分列，接手者可用固定提交链接读取交接。
- 实现、验收、合入、部署状态与证据范围分别写清；收据对应具体 revision、环境和收集面。
- 清理另走保全与 dry-run；保留在跑测试及原作者现场。

本轮复用 Git 的普通推送与平台 API，未增加远程写入脚本。若以后需要无人值守同步，再实现具备独有分支保全、分叉拒绝、并发与网络失败处理、公开范围检查的任务；不能重新启用强制全仓镜像代替这些条件。[Gitea 官方镜像说明](https://docs.gitea.com/1.25/usage/repository/repo-mirror/)

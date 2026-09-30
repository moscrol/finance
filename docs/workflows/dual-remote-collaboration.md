# GitHub 开发与本地 Gitea 备份

GitHub `origin` 是金融仓的开发、PR 和集成主干；Gitea 接收单向备份。
从最新 `origin/main` 开分支，在 GitHub 提交 PR，通过既有验收后由用户确认合入。
其他私有配套仓须先验证各自的 GitHub 入口；本次切换不将私有资料发布到金融公开仓。

## 日常入口

```bash
git status --short
git branch --show-current
git fetch --no-tags origin
git config --local remote.pushDefault origin
git worktree add -b fix/example <独立目录> origin/main
git push -u origin fix/example
gh pr create --repo moscrol/finance --base main --head fix/example --body-file <正文文件>
```

GitHub main 要求 `workbench-check` 与 `registry-check` 通过；管理员同样受保护，
禁止强推和删除 main。源端删掉已完成的工作分支后，备份端仍保留历史引用。
分支数量不同是正常备份状态，不能因此把 Gitea 旧枝批量重建到 GitHub。

## 本地备份任务

`scripts/github_local_backup.py install --repo <金融检出目录>` 安装独立运行副本。
默认每小时运行，启动登录会话时补跑；Mac 关机或睡眠期间本地任务不执行。
运行文件和设置在 `~/.finance-runtime/github-backup/finance/`，
日志在 `~/Library/Logs/com.a77.finance-github-local-backup.log`。
副本使用 Python 标准库、Git、已登录的 gh 和 Gitea 的既有 Keychain 凭据；不落明文 token。

运行器先拉取 GitHub 的分支和标签，把观察到的完整 SHA 固定下来，
生成当日可独立恢复的 Git bundle，再逐项决定备份去向：

- 目标缺失或目标是源端祖先：普通快进复制同名分支。
- 同名分叉、源端回退或标签改写：源端新对象写到 `backup/github/<UTC时间>/<原名>`。
  Gitea 原引用保留；当天 manifest 记录每个源引用与实际恢复引用的对应关系。
- GitHub 删除引用：Gitea 的历史引用保留。
- 导致非快进或推送冲突的目标并发变化、目标拒绝写入：原子推送拒绝，留下本地 bundle 和失败状态。
- 检测到 Gitea push mirror：停止向 Gitea 推送，先排除反向覆盖 GitHub 的风险。

备份仓的 GitHub push URL 指向本地禁用路径，每轮校验 Gitea 的全部实际推送地址只有预期的本地目标。
两端回读成功才记完整成功；源端同期推进的下一批提交留给下次运行。

`~/backups/github-finance/<Asia-Taipei日期>/` 保存当天最新的完整 bundle。
`repository.bundle` 指向最近一次本地代码快照；manifest 中的 `bundle`、`manifest`、`metadata_dir`
指向该次校验文件、源引用映射与 GitHub 仓库/Issue/PR/评论/评审/Release 等 JSON。
失败时保留上次成功记录及其实际文件，可用运行目录的 `last-success.json` 恢复。
完整成功后替换同一天的旧尝试文件；每日目录保留，不自动删除旧日期。
源码不变时复用 bundle，避免每小时再写一份完整历史。
Gitea 既有开放 PR 另存本地索引，供后续按任务搬迁；不自动关闭、不重新合旧枝。
元数据导出供人工恢复参考，不宣称平台间 PR 编号或全部功能可无损恢复。

## 手动运行与查看结果

```bash
python3 ~/.finance-runtime/github-backup/finance/runner.py run --config ~/.finance-runtime/github-backup/finance/config.json
cat ~/.finance-runtime/github-backup/finance/status.json
cat ~/.finance-runtime/github-backup/finance/last-error.json
launchctl print gui/$(id -u)/com.a77.finance-github-local-backup
```

`status.json` 中 `status=success` 才表示代码回读和元数据导出完整成功；
`local_snapshot_ready` 表示本地代码已保全而远端/元数据阶段未完成。
同时检查 `last-error.json` 的时间，不把一次成功等同以后持续成功。

## 账号不可用时恢复

先选定日期，并校验 manifest 里的 `bundle_sha256`。在新目录恢复，不改动现有工作树：

```bash
git clone ~/backups/github-finance/<日期>/repository.bundle <新的恢复目录>
git -C <新的恢复目录> fsck --full
```

bundle 含完整 Git 对象与保留的历史分支；manifest 标出该次 GitHub 实际存在的引用。
也可从 Gitea 新克隆，根据 manifest 使用同名分支或归档引用恢复固定 SHA。
恢复生产数据、用户会话、数据库、附件、LFS 实体与 Wiki 须走各自备份；本任务不覆盖它们。

## 既有在途成果

Gitea #956、#966、#991 是历史平台上的在途记录，不能映射成同号 GitHub PR。
后续需要继续的任务从当前 GitHub main 集成有效提交，并在新 PR 中保留原记录指针。
同步备份、业务验收、main 合入和生产部署分别记账。

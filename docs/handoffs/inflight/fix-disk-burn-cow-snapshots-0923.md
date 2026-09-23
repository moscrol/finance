# fix/disk-burn-cow-snapshots-0923

## 这个分支做什么
修复磁盘清理与门禁快照链路，确保无法完成安全审计时不删除现场。

## 决策与被否方案
- `lsof`/Git 状态/批处理扫描失败统一 fail-closed；否了“空结果继续删”，因为无法确认使用中路径时会盲删。
- 启动器引用先 canonical 化并按目录边界比较；否了原始字符串匹配，因为 launchd 可引用软链接路径。
- basetemp 在 pytest 启动前拒绝与仓库有包含关系；否了仅在绿门禁后保护，因为 pytest 自己会先清空 basetemp。
- cleanup 跳过其他 ignored/untracked 内容并设单树/整轮超时；否了把所有 detached/Git-clean 树当门禁快照。

## 当前状态
- 远端 PR #876 head：`8353fce14`，与本地一致，工作树干净。
- 修复提交：`11eb5ba6f`、`8353fce14`；已强制更新 PR 分支。
- PR 仍 open；Gitea API 报 `mergeable=false`，本地 `git merge-tree` 无冲突，未合并。

## 已验证
- 定向回归：`136 passed`。
- 全量 Python：`14581 passed / 0 failed / 85 skipped / 2 xfailed`。
- 收据：`/private/tmp/pr876-full-8353fce1/receipts/gate-YfXmmWJd/pytest.json`；当前 `check_test_receipt --base-drift-max 5` 为 `rc=0`，基座漂移 `2`。
- ruff、`bash -n`、`git diff --check` 通过。
- 真实 cleanup dry-run 在设定总时限内返回 `4`，未删除。

## 未验证 / 已知边界
- 未执行 cleanup `--apply`；只在 disposable Git 仓库中验证删除/保留分支。
- 前端/e2e 未跑，改动不触及 webapp；合流 tip 仍按仓库级规程补跑。
- Gitea `mergeable` 状态与本地无冲突读数不一致，合并前需刷新/处理该状态；基座推进后收据必须重新检查。

## 下一步
1. 让 PR 合并状态刷新，确认 Gitea 允许合并。
2. 合并前复核 head、base、收据 revision 三者一致性；不要直接使用旧 head 的收据。

## 踩过的坑
- 全量门禁耗时约 30 分钟；必须用独立 `/private/tmp` 收据目录，质检 review 目录会被外部清理器回收。
- 同时存在多个全量门禁进程，判断运行状态必须核对 PID cwd 和 revision，不能只看进程名。

# 2026-09-23 磁盘清理 QC 修复决策

## 背景
PR #876 原本用 `lsof`、launchd 字面路径、Git clean 和根目录 mtime 作为批量 worktree 删除守卫。独立 QC 发现这些条件不能共同证明“可安全删除”：lsof 非零仍生成成功标记；launchd 可通过软链接引用物理 worktree；Git clean 不包含 ignored 文件；显式 basetemp 可落在仓库树内。

## 按发现顺序
1. 用返回非零的假 lsof 复现：原脚本仍以 0 退出并删除 detached worktree。改为 pipeline 成功才写 `open.done`，失败返回 4。
2. 用 `runtime -> candidate` 的 LaunchAgent 复现漏守卫。引用和候选统一 canonical 化，按目录边界比较。
3. 检查 `run_main_gate.sh`：pytest 会在测试前处理 `--basetemp`，所以绿后保护太晚。现在先解析 canonical 路径，拒绝仓库本身、父路径和子路径；清理期间路径改变/删除失败返回 4。
4. 用 Git-clean detached 树放置 ignored evidence 文件复现误删。cleanup 现在对其他 ignored/untracked 内容跳过，并检查树内 mtime。
5. 实机 dry-run 显示逐条 Python canonicalize 和大型树状态扫描可能拖住批处理。改为批量解析引用、目录用 `pwd -P`，Git 状态有单树超时，批处理有总时限；超时停止整轮。

## 验证
- 新增 cleanup 脚本回归覆盖：lsof 失败、软链接引用、ignored 内容、正常删除。
- 定向 `136 passed`。
- 全量 Python revision `8353fce14ef4`：`14581 passed / 0 failed / 85 skipped / 2 xfailed`，约 30 分钟。
- 当前 base drift checker：`rc=0`，漂移 2，限制 5；当前 merge-tree 无冲突。

## 仍需处理
Gitea API 的 PR #876 仍报 `mergeable=false`，但本地合并树无冲突；在合并前刷新/解释该状态。未执行 cleanup 真删，也未跑 webapp/e2e。

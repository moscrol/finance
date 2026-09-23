# 2026-09-23 部署脚本 `--help` 无副作用（PR #846）收口工单（#86）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
来源：`docs/handoffs/2026-09-23-orphan-inventory.md`。无前置；小单，半天。

## 背景与动机

09-21 一次验收会话对旧 `scripts/deploy_workbench_runtime.sh` 敲了 `--help`，脚本没有参数解析，**真的 rsync 覆盖了 8792 的 `adcda94` 运行树并触发重启失败**；随后用同 revision 的干净 recovery 快照切链恢复（health=healthy、`source_dirty=false`）。PR **#846** 修：help 在任何探测前退出；空参 / 未知参数拒绝；真实执行要求 `--apply` + 完整 `--expect-revision` + 显式 `WORKBENCH_REPO_ROOT`；脏源、版本不匹配、Git 版本快照及其子目录一律拒绝。定向 57P，两批撤保护变异 3/3、6/6 被抓。**没跑全量四叶，独立复审 300 秒空输出 exit 143 无结论**（memory：外审返空是阻塞不是无发现），之后无人接手。

今天核对 [实测]：2 个非文档文件（脚本 + `tests/test_deploy_workbench_runtime.py`），对当前 main **1 处冲突**（`.claude/lessons_learned.md`，追加式）。

## 目标

1. 前向到当前 main（union 解 lessons），四叶收据绑定新 head。
2. 复核「安装副本」路径：`~/.local/bin/` 或 launchd plist 里若有部署脚本的拷贝 / 软链，合入后要指向仓内新脚本，否则修复只在仓里生效（memory：`scheduled-job-code-root-must-not-be-a-shared-tree`、`deploy-8792-switch-procedure`）。本单只查清并写出替换命令，不执行。
3. 独立复审：K3 桥一次，或用户豁免（脚本改动小、变异证据齐）。
4. 合入等用户确认。

## 非目标

- ❌ 部署 / 重启 / 切链 8792。
- ❌ 修 readiness 503（数据库落后快照日期是 #61 的事）。
- ❌ 改主检出树里那份旧脚本（它在 L2 覆盖层树上，不归本单）。

## 证据路径表

| 文件 | 看什么 |
|---|---|
| `python3 scripts/gitea_pr.py show 846` 及评论（5471 / 5478 / 09-22 00:19） | 事故经过、修复清单、独立审查无结论、#831 已合 |
| `gitea/fix/deploy-help-fail-closed-0921:docs/handoffs/inflight/fix-deploy-help-fail-closed-0921.md` | 当前状态与「首次合并被 WIP 挡 405」教训 |
| `gitea/fix/deploy-help-fail-closed-0921:docs/handoffs/2026-09-21-pr831-merge-gate-and-846-review.md` | 审查边界 |
| `~/.finance-runtime/test-receipts/20260921T135024Z-4f9a2af5.json` | 定向 57P 收据 |
| `git diff gitea/main...gitea/fix/deploy-help-fail-closed-0921 -- scripts tests` | 净 diff |
| `plutil -p ~/Library/LaunchAgents/com.financeworkspace.*.plist \| grep -i deploy`；`ls -l ~/.local/bin \| grep -i deploy` | 安装副本在哪 |
| `~/.claude/projects/-Users-a77-finance-workspace-private/memory/deploy-8792-switch-procedure.md` | 切链实操要点 |

## 步骤

1. 开工三连 + `git fetch gitea`；`git worktree add /Users/a77/fwp-wt-deploy-help-0923 gitea/fix/deploy-help-fail-closed-0921`；`git merge gitea/main`，lessons union。
2. `.venv-workbench/bin/python -m pytest -q tests/test_deploy_workbench_runtime.py`；`zsh -n scripts/deploy_workbench_runtime.sh`；重放两批变异（PR 正文给了做法）确认仍 3/3、6/6。
3. 四叶；查安装副本并写出替换命令。
4. 贴读数；QUEUE.md 一行或豁免原话；inflight ≤3K；INDEX #86 状态行。

## 验收

- [ ] `merge-tree` 干净；四叶收据 revision == head、`dirty=false`。
- [ ] 阳性对照：删掉 `--apply` 检查，至少一条测试红；`bash scripts/deploy_workbench_runtime.sh --help` 在测试拦截下不触发任何 rsync / launchctl 调用（测试断言调用记录为空）。
- [ ] 安装副本清单贴 PR：路径、指向、是否需替换、替换命令。
- [ ] 8792 `health` 前后 revision 一致。
- [ ] INDEX #86 行已改。

## 红线

- pathspec 提交；合 main 等用户确认；不强推。
- 测试必须拦截 `rsync` / `launchctl`，不得触真实生产（PR 正文已这么做，别放松）。
- 不在主检出树执行任何部署脚本探测用法。

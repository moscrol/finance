# Fidelity runtime 渐进迁移

目标是先把逐声明 lineage 与 PIT v1.1 放进稳定运行链，再迁移会写入大量日常产物的旧任务。

## 运行目录

- `/Users/a77/finance-workspace-runtime`：指向固定 Git commit 的只读代码 worktree。
- `/Users/a77/finance-workspace-private`：现有可写数据与报告目录。
- `/Users/a77/knowledge-base-private`：知识库输入。
- `/Users/a77/fidelity-runtime/logs`：新任务日志。
- `/Users/a77/fidelity-replay/pit-snapshots`：PIT 快照。

代码根与数据根分离后，切换开发分支或修改日常工作区不会改变定时任务实际执行的 Python 代码。

## 第一阶段

1. 从已验收的 `main` commit 建 detached worktree，并更新稳定软链：

   ```bash
   mkdir -p /Users/a77/.finance-runtime
   git -C /Users/a77/finance-workspace-private worktree add \
     --detach /Users/a77/.finance-runtime/finance-workspace-<commit> <commit>
   ln -sfn /Users/a77/.finance-runtime/finance-workspace-<commit> \
     /Users/a77/finance-workspace-runtime
   mkdir -p /Users/a77/fidelity-runtime/logs
   ```

2. 先安装并手工触发：

   - `com.financeworkspace.fidelity-daily-agent`
   - `com.financeworkspace.pit-snapshot`

   20:05 任务先从固定代码根重新生成带 lineage 的 theme-candidates，经 schema/evidence 校验后原子替换当日产物，并把旧版本保存在 `/Users/a77/fidelity-runtime/backups/<date>/`；随后生成 daily-agent。PIT 在 20:30 从同一代码 commit 冻结 DuckDB 与知识库输入。

3. 用统一状态门检查：

   ```bash
   /usr/bin/python3 scripts/fidelity_runtime_status.py \
     --code-root /Users/a77/finance-workspace-runtime \
     --data-root /Users/a77/finance-workspace-private \
     --snapshot-dir /Users/a77/fidelity-replay/pit-snapshots \
     --date YYYY-MM-DD
   ```

   只有代码 worktree clean、daily-agent 存在非空 `claim-lineage-v1`、PIT manifest 为 `pit-daily-manifest-1.1` 时，`capture_ready` 才为 true。`replay_ready` 还要求 manifest 自身的 `replay_eligible=true`；两者分开，避免把“新链路已运行”误写成“已可用于决策”。

## 暂不迁移

`daily-full-review` 与 `dual-blind-forecast` 仍会写入仓内台账和渲染物，第一阶段保持原任务不变。后续先把其代码根和可写 artifact root 解耦，再切换 LaunchAgent，避免一次性迁移扩大故障面。

## 回滚

停止并移除两个新 LaunchAgent，恢复原 PIT plist；旧的 18:30 全量复盘与 09:10 双盲链不受第一阶段影响。不要删除已有 PIT manifest 或 daily-agent 报告。

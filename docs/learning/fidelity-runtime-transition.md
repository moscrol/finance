# Fidelity runtime 渐进迁移

目标是把逐声明 lineage 与 fidelity contract 1.2 放进稳定运行链，再迁移会写入大量日常产物的旧任务。

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

   20:05 任务先确认 `fact_market_daily` 存在当天交易日；周末、节假日或数据尚未落库时安全跳过。通过后再从固定代码根重新生成带 lineage 的 theme-candidates，经 schema/evidence 校验后原子替换当日产物，并把旧版本保存在 `/Users/a77/fidelity-runtime/backups/<date>/`；随后生成 daily-agent。PIT 在 20:30 从同一代码 commit 冻结 DuckDB 与知识库输入。

3. 用统一状态门检查：

   ```bash
   /usr/bin/python3 scripts/fidelity_runtime_status.py \
     --code-root /Users/a77/finance-workspace-runtime \
     --data-root /Users/a77/finance-workspace-private \
     --snapshot-dir /Users/a77/fidelity-replay/pit-snapshots \
     --date YYYY-MM-DD
   ```

   `capture_ready` 要求代码 worktree clean，并同时验证：

   - daily-agent、Theme Radar 上游和 PIT 都满足
     `fidelity-contract-1.2`；
   - `report_generated_at`、`evidence_cutoff`、
     `decision_cutoff`、`snapshot_captured_at` 的顺序合法；
   - `generator_commit`、`run_id`、`artifact_sha`、
     `manifest_sha` 完整且上下游一致；
   - JSON、Markdown、HTML 共享同一 provenance marker；
   - 所有对外叙述都进入 canonical claim manifest；
   - 报告确实在目标交易日生成，历史补跑不能冒充前向产物。

   PIT manifest 必须为 `pit-daily-manifest-1.3`，且连接同日
   daily-agent 的 run/hash/commit。`replay_ready` 还要求 manifest
   自身的 `replay_eligible=true`；`decision_eligible` 在积累足够前向
   交易日和 Gold 审核前固定为 false。

   P4-C 将 wiki 的可重放条件从“工作树必须干净”升级为
   `base_commit + content-delta-1.0`。daily-agent 在使用知识库前后捕获
   同一 content hash；PIT 继承完整 delta，并在 manifest 中保存
   summary/hash。因此 wiki 可以保持 dirty，但逐文件内容、mtime cutoff、
   base commit 和 daily-agent/PIT hash link 必须全部有效。finance runtime
   代码仍要求 clean，`decision_eligible` 仍固定为 false。

## 暂不迁移

`daily-full-review` 与 `dual-blind-forecast` 仍会写入仓内台账和渲染物，第一阶段保持原任务不变。后续先把其代码根和可写 artifact root 解耦，再切换 LaunchAgent，避免一次性迁移扩大故障面。

## 回滚

停止并移除两个新 LaunchAgent，恢复原 PIT plist；旧的 18:30 全量复盘与 09:10 双盲链不受第一阶段影响。不要删除已有 PIT manifest 或 daily-agent 报告。

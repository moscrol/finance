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
   - `com.financeworkspace.fidelity-forward-acceptance`

   20:05 任务先确认 `fact_market_daily` 存在当天交易日；周末、节假日或数据尚未落库时安全跳过。通过后再从固定代码根重新生成带 lineage 的 theme-candidates，经 schema/evidence 校验后原子替换当日产物，并把旧版本保存在 `/Users/a77/fidelity-runtime/backups/<date>/`；随后生成 daily-agent。PIT 在 20:30 从同一代码 commit 冻结 DuckDB 与知识库输入。

   P4-E 在 20:45 运行前向验收。它不生成研究内容，只读取固定 runtime
   commit、daily-agent 和 PIT manifest，写入仓外状态台账：

   ```text
   /Users/a77/fidelity-runtime/forward-acceptance/
   ├── records/<date>/<checked-at>-<sha>.json
   └── latest/<date>.json
   ```

   `records` 保留每次尝试，修复后重跑不会抹掉第一次失败；`latest` 是供汇总
   使用的当日投影。相比只覆盖单个 `status.json`，这种“不可变事件 +
   可变投影”同时满足审计和日常查询；相比集中 JSONL，它避免多个进程追加时的
   半行写入问题。这一模式也适用于数据管线运行台账和模型评测记录。

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

## P4-E：安装与验收

先把 `/Users/a77/finance-workspace-runtime` 固定到包含 P4-B/C/D/E 的已验收
commit，再安装三个 LaunchAgent。plist 只负责调度，不能证明任务已经加载；
必须用 `launchctl print` 检查运行态。

这里选择 macOS LaunchAgent，而不是用 Devin Automation 直接跑生产验收：
生产 DuckDB、知识库 dirty worktree 和 PIT 目录都只在 a77 Mac；云端 Automation
看不到这些本地输入，直接运行会验证另一个环境。Automation 后续可用于读取已同步
状态并通知，但不能替代本地唯一写入者，也不要再建一套重复生成任务。

```bash
mkdir -p /Users/a77/fidelity-runtime/logs
mkdir -p /Users/a77/Library/LaunchAgents
cp intelligence/eval/com.financeworkspace.fidelity-daily-agent.plist \
  /Users/a77/Library/LaunchAgents/
cp intelligence/eval/com.financeworkspace.pit-snapshot.plist \
  /Users/a77/Library/LaunchAgents/
cp intelligence/eval/com.financeworkspace.fidelity-forward-acceptance.plist \
  /Users/a77/Library/LaunchAgents/

launchctl bootstrap gui/$(id -u) \
  /Users/a77/Library/LaunchAgents/com.financeworkspace.fidelity-daily-agent.plist
launchctl bootstrap gui/$(id -u) \
  /Users/a77/Library/LaunchAgents/com.financeworkspace.pit-snapshot.plist
launchctl bootstrap gui/$(id -u) \
  /Users/a77/Library/LaunchAgents/com.financeworkspace.fidelity-forward-acceptance.plist

launchctl print gui/$(id -u)/com.financeworkspace.fidelity-daily-agent
launchctl print gui/$(id -u)/com.financeworkspace.pit-snapshot
launchctl print gui/$(id -u)/com.financeworkspace.fidelity-forward-acceptance
```

已加载旧版本时，先对对应 label 执行 `launchctl bootout`，再 `bootstrap` 新
plist；不要重复加载同一 label。

20:45 任务先用 `fact_market_daily` 做交易日 gate；没有当日事实行时不制造周末
或节假日假告警，也不会增加 accepted 日数。存在当日事实行后，验收返回非零即为
硬失败，同时仍落一条 `blocked` 记录，便于定位是 report、PIT、commit 还是
provenance 门失败。修复后可手工重跑：

```bash
/bin/zsh scripts/run_fidelity_forward_acceptance.sh YYYY-MM-DD
```

7/13–7/17 首周汇总：

```bash
/usr/bin/python3 scripts/fidelity_forward_acceptance.py summary \
  --output-root /Users/a77/fidelity-runtime/forward-acceptance \
  --start-date 2026-07-13 \
  --end-date 2026-07-17
```

`gold_sampling_ready=true` 要求至少 5 个全部通过的前向交易日、累计至少
150 条 claims，且窗口内没有 blocked/invalid 记录。它只表示可以开始
P4-D 人工 Gold 抽样，不表示决策可用。`eligibility_observation_ready` 至少要求
10 个全部通过的前向交易日；即使达到，`decision_eligible` 仍保持 false，
必须另行完成双人 Gold 审核和 10–20 日指标评估后人工决策。

## 暂不迁移

`daily-full-review` 与 `dual-blind-forecast` 仍会写入仓内台账和渲染物，第一阶段保持原任务不变。后续先把其代码根和可写 artifact root 解耦，再切换 LaunchAgent，避免一次性迁移扩大故障面。

## 回滚

停止并移除两个新 LaunchAgent，恢复原 PIT plist；旧的 18:30 全量复盘与 09:10 双盲链不受第一阶段影响。不要删除已有 PIT manifest 或 daily-agent 报告。

# Canonical 8792 原子切换手册

## 目标与安全边界

把 canonical Workbench 从旧运行提交切到已经合并并验收的 `main`，同时满足：

- 不修改或清理当前 `/Users/a77/.finance-runtime/finance-workspace-bb9754f248bf`；
- 不在开发工作区切分支；
- 不迁移旧 runtime 中已降级为 partial 的 `2026-07-16` AkShare 快照；
- 新 runtime 验证失败时，只切回软链即可回滚；
- 密钥仍由现有 LaunchAgent/Keychain 注入，不写入仓库、脚本或 plist。

`/Users/a77/finance-workspace-runtime` 是软链。发布采用“新建 detached worktree →
离线验证 → 停服务 → 切软链 → 启服务”的蓝绿方式。与直接在旧 runtime 执行
`reset --hard` 相比，它不会破坏旧目录里的现场；与长期直接运行开发工作区相比，
它能固定代码版本，避免后续 checkout 改变生产代码。这种模式也适合本地定时任务、
数据管线和单机服务发布。

## 1. 发布前门禁

仅在目标 PR 已获批准并合入 `main` 后执行。先记录旧目标，并同步远端引用：

```bash
old_runtime="$(readlink /Users/a77/finance-workspace-runtime)"
git -C /Users/a77/finance-workspace-private fetch origin main
target_sha="$(git -C /Users/a77/finance-workspace-private rev-parse origin/main)"
target_short="$(git -C /Users/a77/finance-workspace-private rev-parse --short=12 "$target_sha")"
new_runtime="/Users/a77/.finance-runtime/finance-workspace-$target_short"

test "$old_runtime" = "/Users/a77/.finance-runtime/finance-workspace-bb9754f248bf"
git -C /Users/a77/finance-workspace-private merge-base --is-ancestor \
  b616412 "$target_sha"
```

最后一条保证本轮 P0/P0.5/P1/P2 的验收提交已经进入目标 `main`，不能只看分支名。

## 2. 建立干净的候选 runtime

```bash
mkdir -p /Users/a77/.finance-runtime
git -C /Users/a77/finance-workspace-private worktree add \
  --detach "$new_runtime" "$target_sha"

test -z "$(git -C "$new_runtime" status --short)"
test "$(git -C "$new_runtime" rev-parse HEAD)" = "$target_sha"
```

不要复用或删除旧 runtime。候选目录应当是 clean；业务数据继续写入
`/Users/a77/finance-workspace-private` 和仓库外持久目录。

## 3. 行情质量门禁

截至 2026-07-16 的上线前检查结果是：

- private 数据根最新为 `2026-07-14`，旧 schema 没有 `quality/freshness`，因此
  readiness 正确判为 not-ready；
- 旧 `bb9754f` runtime 里的 `2026-07-16` AkShare 文件已被后续失败运行改写为
  `quality=partial`，只有局部涨跌停数据，不能迁入 canonical 数据根；
- 不以某次历史 smoke 成功代替当前文件检查，也不把 partial 包装成 complete。

新 runtime 建立后先装独立 AkShare venv，再由 provider chain 写 canonical 数据根并
执行 contract：

```bash
FINANCE_WORKSPACE_CODE_ROOT="$new_runtime" \
  "$new_runtime/scripts/bootstrap_akshare_snapshot_runtime.sh"

FINANCE_WORKSPACE_CODE_ROOT="$new_runtime" \
FINANCE_WS=/Users/a77/finance-workspace-private \
AKSHARE_PROXY_MODE=direct \
  "$new_runtime/scripts/run_market_snapshot.sh" --date 2026-07-16

snapshot_check="$(
  cd "$new_runtime" && PYTHONPATH="$new_runtime" python3 \
    -m scripts.check_market_snapshot_contract \
    --root /Users/a77/finance-workspace-private/market_snapshot
)"
printf '%s\n' "$snapshot_check" | python3 -m json.tool
printf '%s\n' "$snapshot_check" | jq -e \
  '.status == "PASS" and .ready == true and
   .summary.quality == "complete" and
   (.summary.provider == "akshare_exact" or
    .summary.provider == "duckdb_exact" or
    .summary.provider == "duckdb_latest")'
```

目标日 DuckDB 未落地时，同步器会走 Eastmoney 快路径，失败后用 Sina 分页兜底，
通常需要 2–3 分钟。若 AkShare partial/failed，编排器不会发布它，而会尝试最近完整
DuckDB 日。最终进程非零或 contract 不是 `PASS + ready=true` 时停止发布，不继续切
8792。若 provider 是 `duckdb_latest`，必须在验收记录中保留 requested/served 日期，
不得把 historical 说成当天行情。

## 4. 切换服务

先确保 `/Users/a77/.local/bin/start-finance-workbench` 仍从 runtime 软链导入代码、
从 private 数据根读写数据，并在不暴露密钥的前提下增加：

```bash
export RAG_WORKER_ENABLED=1
```

常驻 worker 的收益是把 BGE-m3 模型和索引加载从每个请求移到进程生命周期；替代
方案是继续用每请求 CLI，隔离性更强，但冷启动会反复付出约几十秒成本。worker
超时后会终止并重建子进程，readiness 会暴露状态。

停止服务后切软链，再启动：

```bash
launchctl bootout gui/$(id -u)/com.a77.finance-workbench
ln -sfn "$new_runtime" /Users/a77/finance-workspace-runtime
launchctl bootstrap gui/$(id -u) \
  /Users/a77/Library/LaunchAgents/com.a77.finance-workbench.plist
```

`ln -sfn` 只替换入口软链，不修改旧 worktree。服务停止窗口内完成切换，避免请求读到
两个版本。

## 5. 安装独立 AkShare 调度

Workbench 就绪后，按
[`akshare-snapshot-runtime.md`](./akshare-snapshot-runtime.md) 安装工作日 16:15
LaunchAgent；独立 venv 已在质量门禁阶段建立。不要把 AkShare 装进
`.venv-workbench`；依赖隔离能缩小升级和回滚半径。

## 6. 上线验收

```bash
test "$(readlink /Users/a77/finance-workspace-runtime)" = "$new_runtime"
test "$(git -C /Users/a77/finance-workspace-runtime rev-parse HEAD)" = "$target_sha"
test -z "$(git -C /Users/a77/finance-workspace-runtime status --short)"

launchctl print gui/$(id -u)/com.a77.finance-workbench
curl --fail --silent http://127.0.0.1:8792/api/health/ready | python3 -m json.tool
curl --fail --silent http://127.0.0.1:8792/api/workbench/overview | python3 -m json.tool

python3 /Users/a77/finance-workspace-runtime/scripts/smoke_workbench_self_use.py \
  --base-url http://127.0.0.1:8792 \
  --user linxiaoqi5111 \
  --question "中际旭创怎么看" \
  --timeout 180 \
  --output /tmp/workbench-8792-stock-smoke.json
```

然后用同一 Conversation 追问“这个逻辑的边际变化呢”，确认 owner 仍为
`stock-deep-dive`；再问“光模块怎么看”，确认进入 `theme-research`。同时检查：

- readiness 中 RAG worker 已启用且无残留后台任务；
- `market_snapshot` 为 complete/ready，不以“目录存在”代替质量判断；
- followup 按钮显示短 `label`，提交的是用户口吻 `full_prompt`；
- Validation 面板可见胜率样本门和待审核反思/规则，不会自动批准经验。

## 7. 回滚

任一门禁失败时，不清理新 runtime，先恢复服务：

```bash
launchctl bootout gui/$(id -u)/com.a77.finance-workbench
ln -sfn "$old_runtime" /Users/a77/finance-workspace-runtime
launchctl bootstrap gui/$(id -u) \
  /Users/a77/Library/LaunchAgents/com.a77.finance-workbench.plist
```

若 AkShare 调度是本次新增，再按其 runbook 执行 `bootout`。若故障与常驻 RAG worker
有关，可先移除 `RAG_WORKER_ENABLED=1` 回退到 CLI 模式。行情 complete 快照是业务
数据，不随代码回滚而删除。

确认旧版本恢复健康后，再分析新 runtime；未经确认不要删除任何隐藏 runtime
worktree。

## 8. P13 候选验收记录（不代表已切换）

2026-07-21，独立候选分支 `fix/agent-architecture-p13` 的 tip
`b793b2df` 已完成统一 Research Agent 长尾验收，证据矩阵见
[`docs/verification/agent-capability-monotonicity-2026-07-20.md`](../verification/agent-capability-monotonicity-2026-07-20.md)。

新的长尾三题 Conversation API E2E 记录见
[`docs/verification/unified-research-agent-long-tail-2026-07-21.md`](../verification/unified-research-agent-long-tail-2026-07-21.md)。隔离候选端口为 `8794`，不是 canonical `8792`。

- 全量 `intelligence/tests`：1899 passed。
- 历史基线 X3（methodology）运行 `run_20260720_232827_324781`：
  `validated_synthesis`、GLM used、0 degrade。
- 历史基线 X4（relation guard）运行 `run_20260720_232905_320841`：
  `evidence_gap_fallback`、LLM 未调用，trace 明确 `relation_graph_guard=empty`。
- 历史市场归因运行 `run_20260720_231930_351135`：真实执行 news/web 检索；时点不匹配的外部结果不被冒充为因果证据。
- 历史头部技术位运行 `run_20260720_233547_476972`：0.559s、LLM 未调用，trace 仅有 `tencent_kline`，输出数值依据和失效条件。
- 历史客户事实核验运行 `run_20260720_233548_100202`：0.546s、L3 空结果后 `evidence_gap_fallback`，没有继续弱 KB/Web 检索。

该分支仍未合并 `main`，`/Users/a77/finance-workspace-runtime` 和 canonical `8792`
保持不变。只有用户明确批准合并，并重新完成本手册第 1–6 节的 production readiness
门禁后，才可以做蓝绿切换。

# Headless in-flight tool pairing WIP handoff (2026-08-04)

> 一句话现状：R-10 的 Task 1 已提交并通过规格复审；Task 2 停在可复现的 RED，
> 尚未修改计费生产代码、尚未跑 live、尚未 push 或合并 main。

## 0. 先读结论

不要继续调 `total_seconds`、`floor_ratio`、`max_tool_calls`，也不要回到 grounded-chain
预算分片。当前层是 Codex headless 的 in-flight tool contract：

1. request 入场必须冻结唯一 grant；
2. 真实 dispatch 必须在 runner 前原子占用一次 root call；
3. runner 必须实际看到不大于 grant 的派生 deadline；
4. watchdog 到点后先撤销发布权，再返回显式 finalization instruction；
5. 迟到 worker 不得发布 evidence、trace、QueryLedger record 或第二终态。

Task 1 只完成第 1 项。第 2 项已有 RED；第 3-5 项属于 Task 3。

## 1. Git 与工作区

| 项 | 当前值 |
|---|---|
| 主仓库 | `/Users/a77/finance-workspace-private` |
| 任务 worktree | `/Users/a77/finance-workspace-private/.worktrees/headless-tool-pairing` |
| 分支 | `fix/headless-tool-correlation-observability` |
| HEAD | `7ca2b83d61fcfefe6bb48e52999936ed9b1c6ca3` |
| HEAD commit | `refactor(runtime): unify headless tool grant budget` |
| 基线设计/计划 | `a21b0539` / `74668b4e` |
| 未提交文件 | `intelligence/tests/test_headless_tool_gateway.py` |
| push / merge | 均未执行 |

开工命令：

```bash
cd /Users/a77/finance-workspace-private/.worktrees/headless-tool-pairing
git status --short
git branch --show-current
git rev-parse HEAD
```

主工作树有大量用户私有/评测脏文件。不要清理、回滚或顺带提交。`.worktrees/` 只加在
主仓库本地 `.git/info/exclude`，不是 tracked change。

## 2. Task 1 已完成的内容

提交 `7ca2b83d` 只改：

- `intelligence/services/headless_tool_gateway.py`
- `intelligence/tests/test_headless_tool_gateway.py`

已完成：

- 共享 transport timeout `60s` 与 response margin `1s`；
- `_EffectiveBudget` / `_ToolGrant`；
- 从显式 `deadline.synthesis_reserve` 派生 handoff，不再使用隐藏 20%；
- root ledger 的 calls/seconds 钳制；
- request telemetry 冻结 root/research/handoff/grant/limiter；
- admission、response budget 和 finalization reason 读取同一冻结视图；
- root calls=0 在 dispatch 前 fail-closed；
- mailbox/HTTP wrapper 从同一 timeout authority 渲染；
- post-tool budget 只读一次，避免 `must_finalize` 与 instruction 互相矛盾。

验证：

```text
29 passed in 12.52s
Ruff: pass
git diff HEAD^ HEAD --check: pass
```

规格复审最终为 `APPROVED`。

## 3. 代码质量审查留下的两项 P1

### P1-A：grant 现在只是 telemetry，还不是执行权

当前 `registry.execute()` 仍收到原始 `ResearchRunContext`。工具内部可取得比
`tool_grant_seconds` 更长的 timeout，且 mailbox 排队时间没有计入 grant。

这属于 Task 3，不要回塞 Task 1。Task 3 必须补强原计划：

- wrapper request 携带客户端 transport 剩余窗口；
- gateway 入场计算 `effective_grant = min(client_remaining, frozen_grant)`；
- 用 `deadline.bounded_stage(effective_grant)` 构造派生 context；
- worker 和 `registry.execute()` 只接收派生 context；
- watchdog cutoff、QueryPublishGuard cutoff、runner 可见 deadline 使用同一
  `effective_grant`。

只加 Future watchdog 而继续把原始 context 传给 runner，不算修完。

### P1-B：root check 与后置 charge 存在 check-then-act race

原计划 Task 2 在 runner 完成后调用 `consume_call(elapsed)`。两个并发 HTTP request
可能同时看到 `remaining_calls == 1`，都执行工具，最后才有一个扣账失败。

因此原计划的“后置扣费”实现方向已经作废。正确形状是：

1. admission 锁内、runner 前调用 ledger 的原子方法占用一次 call；
2. 占用失败立即返回唯一 `root_budget_exhausted` terminal + finalization；
3. runner 正常、empty、exception、timeout 都不再扣第二次 call；
4. 完成后只用 `consume_seconds()` 结算预占值之外的真实 elapsed；
5. 可复用 SDK runtime 的 `1e-9` call-reservation 形状，但要确认并发 seconds 不会
   超卖。若用 gateway-local pending-seconds reservation，必须纳入
   `_effective_budget()` 并在同一锁内 settle/release。

替代方案“持锁执行整个 runner”不可用：它会把排队时间转化成 wrapper timeout，并阻塞
不相关 request。

## 4. Task 2 当前 RED

未提交 diff 只改测试，共 `157 insertions / 2 deletions`：

- `test_gateway_rejects_when_atomic_root_call_reservation_loses_race`
- `test_gateway_reserves_one_root_call_before_concurrent_dispatch[http]`
- `test_gateway_reserves_one_root_call_before_concurrent_dispatch[mailbox]`
- `test_gateway_charges_root_budget_for_tool_exception`

精确复现命令：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_rejects_when_atomic_root_call_reservation_loses_race \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_reserves_one_root_call_before_concurrent_dispatch \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_charges_root_budget_for_tool_exception
```

当前结果：`4 failed in 1.67s`。失败全部符合预期：

| RED | 当前错误 |
|---|---|
| reservation race | response 缺 `instruction`，说明仍在 dispatch 后才发现 charge race |
| concurrent HTTP | 第一个结果变 `rejected`，两个 runner 都已穿过 admission |
| concurrent mailbox/direct | 同上 |
| tool exception | `ledger.remaining_calls == 1`，异常路径完全未计费 |

这四个 RED 是下一步生产修改的约束，不要删除或改弱断言。

## 5. 下一步执行顺序

完整计划：
`docs/superpowers/plans/2026-08-04-headless-inflight-tool-handoff.md`。

### Task 2：先完成原子计费

1. 在 runner 前原子 reserve root call；失败时 runner 调用数必须为 0。
2. normal/empty/exception 各只消费一个 call。
3. settlement 只补 elapsed seconds，不得第二次 `consume_call()`。
4. root rejection 只发一个执行层 terminal，并带 instruction 与一次 finalization。
5. 先跑上面的 4 个 RED，再跑整个 gateway test。
6. Ruff、`git diff --check`、规格复审、代码质量复审通过后单独 commit：
   `fix(runtime): align headless root budget accounting`。

### Task 3：watchdog + 真 grant + 迟到隔离

除原计划测试外，必须新增/加强：

- runner 内调用 `AgentToolContext.timeout()`，断言不超过 effective grant；
- mailbox request 人为排队后，runner grant 扣除已消耗的 client transport 时间；
- direct slow tool 在 handoff/transport 两种 limiter 下都先于 wrapper 60s 返回；
- timeout 后 snapshot 前后逐值相同，QueryLedger `executed_count == 0`；
- 真实生成 mailbox wrapper 收到 instruction 后事件级 `model_finish`；
- transport `response_path_conflict` 不计第二执行终态。

### Task 4-6

- Task 4：focused + 两个 clean-host 全量 scope；新红必须与父 revision 按 node id 对账。
- Task 5：只跑一次 `c_long_capped/ruihuatai-valuation`，不重跑四臂/五题。
- Task 6：按预注册分支更新 verification、prediction ledger、trace profile、handoff 和
  project memory；最后 push 当前分支，不合并 main。

## 6. 不要踩的坑

- 顶层 `completed` 或 `elapsed <= root` 都不是成功门禁。
- `tool_grant_seconds` 是执行权，不是自然耗时，也不能只记录不执行。
- `consume_call()` 放在 runner 后面无法修复并发 race。
- timeout/cancel 后不要 `join()` daemon worker，也不要用 done callback 发布结果。
- finalization 必须是真实交接点，不是为了填充事件计数。
- `tool=mailbox,error=response_path_conflict` 是 transport 诊断，不是第二执行终态。
- 不动预算/profile/prompt/model/provider，不跑额外 live 调试题。
- 不打印或写入任何 API key；服务环境必须从真实进程复制，不抄文档。

## 7. 当前停点

实现代理已被显式中止，没有后台 agent 或测试进程需要等待。工作树故意保持：

```text
 M intelligence/tests/test_headless_tool_gateway.py
```

下一位从 Task 2 RED 继续，不要重做 Task 1，也不要先跑 live。

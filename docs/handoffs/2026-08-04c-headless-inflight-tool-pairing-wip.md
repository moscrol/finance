# Headless in-flight tool pairing WIP handoff (2026-08-04)

> 一句话现状：`R-20260804-10` 的 Task 1、Task 2 已完成（含 A1 秒数结算 race、A2 归一化器
> 接线两个收尾洞）；**Task 3-6 已冻结，不要继续做**，方向已切到工具面盘点（见
> `docs/handoffs/2026-08-04d-worklist-freeze-r10-then-tool-surface.md`）。未跑 live，
> 未 push，未合并 main。`R-20260804-10` 仍是 `pending`。

## 0. 先读结论

不要继续调 `total_seconds`、`floor_ratio`、`max_tool_calls`，也不要回到 grounded-chain
预算分片。当前层是 Codex headless 的 in-flight tool contract，五条不变量：

1. request 入场必须冻结唯一 grant；
2. 真实 dispatch 必须在 runner **前**原子占用一次 root call；
3. runner 必须实际看到不大于 grant 的派生 deadline；
4. watchdog 到点后先撤销发布权，再返回显式 finalization instruction；
5. 迟到 worker 不得发布 evidence、trace、QueryLedger record 或第二终态。

Task 1 完成第 1 项。第 2 项已有 RED。第 3-5 项属于 Task 3。

## 1. 这条线在整个工程里的位置

本仓的修复受 `docs/prediction-ledger.md` 约束：每条修复带一个可证伪预测，结果只能
`confirmed` / `refuted` / `pending`，**`refuted` 是最有价值的输出**，同类 `fix_type` 连续
3 次 `refuted` 就要升格质疑架构层而不是继续堆补丁。

账本当前状态（2026-08-04）：

| | 数量 | 说明 |
|---|---|---|
| 累计预测 | 10 | `R-20260804-01` … `-10` |
| 已结案 | 8 | 7 `confirmed` + 1 `refuted` |
| Open | 2 | `R-20260804-02`、`R-20260804-10` |

`R-20260804-10`（本轮）**就是 `R-09` 被 `refuted` 生出来的**：L7 finalization 的 T3 瑞华泰
live 显示 5 个 tool request 只有 4 个 mailbox exchange、`finalization=0`，证明"给 rejection
加 instruction"这条修复选错了层——真正的阻塞点在 in-flight 工具没能按时交回控制权。
PRIMARY 因此前移，预算墙不动。这是账本纪律起作用的样本，不是返工。

另一条 Open `R-20260804-02` 与本层无关，卡在"缺一份真 Codex rollout JSONL"，
synthetic 产物不能替代结案。

## 2. 成熟层与在修层

判断标准只有一个：**有没有被离线结构门或真实产物钉住**。"读代码觉得对"不算成熟。

### 已成熟（可依赖，不要重造）

| 层 | 依据 |
|---|---|
| L1 迟到发布隔离：后台执行 + absolute cutoff + `QueryPublishGuard` | `episode_tool_batch` 已验证；本轮**复用**，不发明第二套缓存隔离语义 |
| root ledger 线程安全 | `InMemoryRootBudgetLedger` 的 check+decrement 在同一把锁内（`research_contract.py:552-571`），可直接当原子原语用 |
| request/result/error 配对仪器 | 共享 32-hex `request_id`；normalizer 保留独立 `correlation_id`，mismatched id 不再互相消费 |
| normalizer 词表 | `mode_decision → plan`、`unmapped_count=0` 已由 synthetic rollout 锁定（`R-06` confirmed） |
| 单一预算视图与 transport-safe grant | 本轮 Task 1，见 §4 |

### 已完成（Task 2 + 收尾）

| 层 | 状态 | 依据 |
|---|---|---|
| 计费原子性（calls） | **完成** | `b24bd818`；预占下沉到 runner 前，见 §6 |
| 计费原子性（seconds） | **完成** | A1：`settle_seconds()` 把钳零与扣减放进 ledger 同一把锁；并发测试 + 变异测试见 §8 |
| 新事件 kind 接进消费方 | **完成** | A2：`root_budget_overdraft → ("observe","control")`，`unmapped_count` 保持 0 |

### 已冻结（不要继续做）

| 层 | 原状态 | 冻结说明 |
|---|---|---|
| grant 从 telemetry 升格为执行权 | 未开始（原 Task 3） | **冻结**；原本是本层核心缺口，见 §5 P1-A |
| watchdog + 迟到隔离 | 未开始（原 Task 3） | **冻结** |
| 离线全量 gate | 未开始（原 Task 4） | **冻结** |
| 唯一 live canary | 未开始（原 Task 5） | **冻结** |
| 账本闭环 | 未开始（原 Task 6） | **冻结**；R-10 因此停在 `pending` |

**冻结原因**：本层修的 `codex_headless` 标着 `benchmark_only=True`
（`agent_runtime_factory.py:63`、`api/app.py:276` 会直接 `raise`），产品 web UI 走不到，
它的价值只是"量引擎"这把尺子。主线已切到工具面诊断。

**恢复条件**：要把 headless 用于产品路径（去掉 `benchmark_only`），或工具面诊断结论
指回 in-flight tool contract。届时从原 Task 3 接着做，Task 1/2 的成果可直接复用。
完整取舍见 `docs/handoffs/2026-08-04d-worklist-freeze-r10-then-tool-surface.md` §0。

### 真正的瓶颈（按严重度）

1. **grant 目前只是 telemetry**。Task 1 让预算数字自洽了，但 `registry.execute()` 仍收到
   原始 context，工具内部能取到比 `tool_grant_seconds` 更长的 timeout。只加 watchdog
   而不派生 context，等于"门口贴了限时牌、屋里没有钟"。这是 R-10 能否真结案的决定项。
2. **验证成本，不是编码成本**。R-10 的预注册结案条件要求离线主门全过 **且** 一次 live
   canary，且明写"单次 live 不能独立结案"。所以 Task 2/3 每快一天，收益都被 Task 4/5
   的串行门吃掉一部分——不要为了赶进度跳过离线门先跑 live，那样这次 live 作废。
3. **seconds 记账仍是估算**。见 §6 决议二：预占 + 结算的形状会引入"结算时才发现超支"，
   而超支时工作已经做完了。本轮选择钳零 + 显式记录，不是消灭超支。

## 3. Git 与工作区

| 项 | 当前值 |
|---|---|
| 主仓库 | `/Users/a77/finance-workspace-private` |
| 任务 worktree | `/Users/a77/finance-workspace-private/.worktrees/headless-tool-pairing` |
| 分支 | `fix/headless-tool-correlation-observability` |
| 未提交文件 | `intelligence/tests/test_headless_tool_gateway.py`（仅此一个） |
| push / merge | 均未执行 |

**不要按 hash 核对 HEAD**——本文件每次更新都会推进 HEAD，写死的 hash 必然过期（上一版
handoff 就栽在这）。按 commit subject 自上而下核对分支尾部：

```
docs(agent): hand off headless tool pairing WIP     ← 本文件，HEAD
refactor(runtime): unify headless tool grant budget ← Task 1 唯一生产提交
docs(agent): plan in-flight tool handoff            ← 74668b4e
docs(agent): design in-flight tool handoff          ← a21b0539
```

开工命令：

```bash
cd /Users/a77/finance-workspace-private/.worktrees/headless-tool-pairing
git status --short          # 期望只有 M intelligence/tests/test_headless_tool_gateway.py
git branch --show-current
git log --oneline -4
```

⚠️ **未提交的 157 行 RED 没有任何备份**（`git stash list` 里三条都是别的分支的旧存档）。
一次误 `git checkout .` 或 `git worktree remove` 就全没了。建议下一位**开工第一件事**就是
落一个 RED-only commit（TDD 里提交红测试是正当的），再动生产代码：

```bash
git add intelligence/tests/test_headless_tool_gateway.py
git commit -m "test(runtime): pin headless root call reservation contract"
```

主工作树有大量用户私有/评测脏文件。不要清理、回滚或顺带提交。`.worktrees/` 只加在主仓库
本地 `.git/info/exclude`，不是 tracked change。

## 4. Task 1 已交付内容

提交 `refactor(runtime): unify headless tool grant budget` 只改两个文件：
`intelligence/services/headless_tool_gateway.py` 与同名测试。

- 共享 transport timeout `60s` 与 response margin `1s`，`transport_safe = 59s`；
- `_EffectiveBudget` / `_ToolGrant` 两个冻结视图；
- handoff window 从显式 `deadline.synthesis_reserve` 派生，**删除隐藏的 `initial×0.20`**；
- root ledger 的 calls/seconds 钳制进 `_effective_budget()`；
- request telemetry 冻结 root/research/handoff/grant/limiter 五项；
- admission、response budget、finalization reason 读取同一冻结视图（不再各算一遍）；
- root calls=0 在 dispatch 前 fail-closed；
- mailbox/HTTP wrapper 从同一 timeout authority 渲染；
- post-tool budget 只读一次，避免 `must_finalize` 与 instruction 互相矛盾。

验证：`29 passed in 12.52s`、Ruff pass、`git diff HEAD^ HEAD --check` pass、规格复审
`APPROVED`。

## 5. 代码质量审查留下的两项 P1

### P1-A：grant 还不是执行权（Task 3，不要回塞 Task 1）

`headless_tool_gateway.py:772` 仍传原始 `context=self._context`。工具内部可取得比
`tool_grant_seconds` 更长的 timeout，且 mailbox 排队时间没有计入 grant。

Task 3 必须补强原计划：

- wrapper request 携带客户端 transport 剩余窗口；
- gateway 入场计算 `effective_grant = min(client_remaining, frozen_grant)`；
- 用 `deadline.bounded_stage(effective_grant)` 构造派生 context（`research_contract.py:368`）；
- worker 和 `registry.execute()` **只**接收派生 context；
- watchdog cutoff、`QueryPublishGuard` cutoff、runner 可见 deadline 用同一 `effective_grant`。

只加 Future watchdog 而继续把原始 context 传给 runner，**不算修完**。

### P1-B：check-then-act race（Task 2，原计划方向已作废）

原计划 Task 2 在 runner 完成后调 `_charge_root_budget()`（现 `:797`）。两个并发 HTTP
request 会同时看到 `remaining_calls == 1`、双双穿过 admission、各自执行工具，最后才有一个
扣账失败——工具已经跑了，钱才发现不够。

**"后置扣费"因此作废，改为 runner 前原子预占。** 正确形状见 §6。

替代方案"持锁执行整个 runner"不可用：它把排队时间转成 wrapper timeout，并阻塞不相关
request。§7 的并发测试已经把这条路钉死（见该节说明）。

## 6. Task 2 实现规格

### 当前 RED（4 条，可精确复现）

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_rejects_when_atomic_root_call_reservation_loses_race \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_reserves_one_root_call_before_concurrent_dispatch \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_charges_root_budget_for_tool_exception
```

结果 `4 failed`，失败原因全部符合预期：

| RED | 实际报错 | 说明 |
|---|---|---|
| reservation race | `KeyError: 'instruction'` | 仍在 dispatch 后才发现 charge race |
| concurrent `[http]` | `assert 'rejected' == 'empty'` | 两个 runner 都穿过了 admission |
| concurrent `[mailbox]` | 同上 | 同上 |
| tool exception | `assert 1 == 0`（`remaining_calls`） | 异常路径完全未计费 |

计划文件里的测试名与实际不同，**不要以为测试缺失**：

| plan 中的名字 | 工作树实际名字 |
|---|---|
| `test_gateway_root_charge_race_emits_one_execution_terminal` | `test_gateway_rejects_when_atomic_root_call_reservation_loses_race` |
| （无，本轮新增） | `test_gateway_reserves_one_root_call_before_concurrent_dispatch[http/mailbox]` |
| `test_gateway_charges_root_budget_for_tool_exception` | 同名，但它是**改写**自 `test_gateway_redacts_tool_exception_detail` |

这 4 条是下一步生产修改的约束，不要删除或改弱断言。

### 决议一：两个错误码是两个名字，不要统一

RED 钉死的映射（来源：plan Task 2 Step 3 的 `_root_budget_rejection`）：

| 路径 | `result["error"]` | finalization `reason` | 带 `instruction` |
|---|---|---|---|
| 入场前预算已空（并发中的第二个请求） | `tool_budget_exhausted` | `tool_budget_exhausted` | 是 |
| 预占失败（race 输了） | `root_budget_exhausted` | `tool_budget_exhausted` | 是 |

即**执行层错误码有两个，finalization 原因只有一个**。当前 `:731-734` 与 `:755-758` 两个
白名单集合都不含 `root_budget_exhausted`，这正是 RED#1 报 `KeyError` 的机制——把
`root_budget_exhausted` 加进这两个集合，或改走统一的 `_root_budget_rejection()` 构造器。

⚠️ 把两个码统一成一个，必然打破另一侧的 RED。

### 决议二：settlement 失败必须钳零，不得回滚已完成的执行

预占 `1e-9` + 事后 `consume_seconds(elapsed)` 会引入一个新失败模式：
`consume_seconds` 在 `seconds > remaining_seconds + 1e-9` 时抛 `ValueError`
（`research_contract.py:569`）。两个并发请求各跑 8s、预算 10s，第二个结算必抛——**而此时
观测已经产出**。

本轮决议：**结算钳零 + 显式记录超支**，不因结算失败拒绝已完成的执行。

```python
settle = min(elapsed_seconds, ledger.remaining_seconds)   # 永不抛
ledger.consume_seconds(seconds=settle)
overdraft = elapsed_seconds - settle                      # >0 时进 telemetry
```

理由：admission 已经授权了这次调用，超时是**度量结果**不是授权失败；结算时反悔等于把
P1-B 要消灭的"执行后拒绝"从 calls 搬到 seconds，白改一轮。钳零后 `remaining_seconds`
归零，**下一个** request 的 admission 自然 fail-closed，闸门仍然关得上。

`overdraft` 必须写进 telemetry：静默钳零就是这个仓最忌讳的"覆盖率正常、值是空壳"同族
失败形状——数字永远自洽，超支永远看不见。

（这是本次质检做出的设计决定，plan 与上一版 handoff 都没定义这个分支。若不认可，唯一的
替代是让长工具的观测被丢弃，请先改本节再动手。）

### 决议三：预占用 `1e-9`，seconds 门禁不靠它

复用 `openai_agents_runtime.py:69` 的 `_ROOT_BUDGET_CALL_RESERVATION_SECONDS = 1e-9`。
注意 `consume_call(seconds=1e-9)` 在 `remaining_seconds == 0` 时**检查会通过**
（`1e-9 > 0 + 1e-9` 为假），所以预占**不承担** seconds 耗尽的 fail-closed 职责——那由
Task 1 已完成的 `_effective_budget()` admission 承担。别指望预占兜住秒数。

### 执行顺序

1. 先落 RED-only commit（§3）。
2. admission 锁内、runner 前原子预占一次 call；预占失败时 runner 调用数必须为 0。
3. normal / empty / exception 三条路径各只消费一个 call，不得二次 `consume_call()`。
4. 结算按决议二只补 seconds。
5. root rejection 只发一个执行层 terminal + 一次 finalization + instruction。
6. 跑 4 条 RED → 跑整个 gateway 文件 → 跑消费方文件（基线见 §8）。
7. Ruff、`git diff --check`、规格复审、代码质量复审过后单独提交：
   `fix(runtime): align headless root budget accounting`。

## 7. 测试卫生：两条必须知道的事

**并发测试的 10 秒超时是门禁，不是 flake。** `release_runner` 只在主线程 `finally` 里
set。如果有人把实现改成"持锁跑完整个 runner"，第二个 call 会阻塞，runner 内的
`assert release_runner.wait(timeout=10.0)` 会在 10 秒后失败。**看到这个超时不要去调大
timeout**——它正是 §5 P1-B 里"持锁方案不可用"的可执行版本，调大就等于把门拆了。

**唯一的脱敏断言寄生在预算测试里。** 全仓唯一一处
`assert "PRIVATE_TOOL_EXCEPTION_SENTINEL" not in str(snapshot.to_dict())` 现在位于
`test_gateway_charges_root_budget_for_tool_exception`（原名
`test_gateway_redacts_tool_exception_detail`）。名字只讲预算，以后有人重构预算断言时，
异常详情脱敏契约会静默消失。**Task 2 收尾时把它拆回两个独立测试。**

（测试里的 `finalization_floor_ratio=0.0` 与 §0"不要调 floor_ratio"不冲突：前者是测试内
中和该 floor，后者禁的是改生产 profile 取值。）

## 8. 验证基线

改动前（逐字抄录）：

```text
intelligence/tests/test_headless_tool_gateway.py   →  4 failed, 28 passed（共 32）
intelligence/tests/test_codex_headless_runtime.py  →  28 passed, 1 skipped in 6.94s
ruff check（含未提交测试）                          →  All checks passed
```

A1/A2 完成后的真实值（`.venv-workbench/bin/python -m pytest -q`，逐字抄录）：

```text
intelligence/tests/test_headless_tool_gateway.py   →  34 passed in 13.57s
intelligence/tests/test_research_contract.py       →  2 passed in 0.04s
intelligence/tests/test_normalize_harness_trace.py →  30 passed in 0.06s
intelligence/tests/test_codex_headless_runtime.py  →  28 passed, 1 skipped in 6.16s
ruff check intelligence/                            →  All checks passed
```

gateway 从 32 涨到 34：Task 2 把 4 条 RED 转绿（32 passed），A1 再加 1 条并发结算测试
（33 → 34；`a4d546f9` 另加了 1 条 call 预占契约测试）。

**变异测试（两条新测试都验过咬合）**：

| 改坏什么 | 结果 |
|---|---|
| `settle_seconds()` 的 `min()` 换成直接用 `seconds` | 新并发测试转红：`assert 0 == 1`，overdraft 事件消失 |
| 删掉 `"root_budget_overdraft"` 映射行 | 新归一化测试转红：`At index 2 diff: 'unmapped' != 'observe'` |

两次变异均已还原，还原后复跑回到上表数字。

> ⚠️ 工具坑：`edit` 工具在 `research_contract.py` 上连续三次报 success 但内容未落盘
> （mtime 不变、grep 仍见变异串）。还原变异最终靠 Python 直接改写文件。改完**必须
> grep 复核**，不要只看工具返回的 success。

`test_codex_headless_runtime.py` 是 gateway 的下游消费方，Task 2 改的正是 rejection
payload 形状——它只要 7 秒，**不要推到 Task 4 才跑**。

解释器必须是 `.venv-workbench/bin/python`；宿主的 `python3` 是 3.14 且缺依赖。

## 9. Task 3-6：已冻结（2026-08-04d）

> ⛔ **Task 3-6 全部冻结，不要开工。** 下面内容保留为恢复时的规格，不是当前待办。

**冻结原因**（完整论证见 `docs/handoffs/2026-08-04d-worklist-freeze-r10-then-tool-surface.md` §0）：

1. R-10 修的是 `codex_headless`，而它标着 `benchmark_only=True`
   （`agent_runtime_factory.py:63`、`api/app.py:276` 会直接 `raise`），**产品 web UI 永远
   走不到这条路**。它的价值只是"量引擎"这把尺子。
2. Task 4/5 的验证成本极高（两个 clean-host 全量 scope + live canary），而收益锁在一条
   产品够不着的路径上。
3. 主线已切到**工具面诊断**（08-04d 清单 Batch B）：先查清 8 个工具里 contract 实际
   授权了几个，再决定投哪里。

**恢���条件**（满足任一即可解冻）：

- `codex_headless` 不再是 `benchmark_only`，要进产品路径；或
- Batch B 诊断结论是「工具面没问题，差距确实在 agent 循环/交接」；或
- 需要用 headless 量引擎做一次对照测量，且 in-flight 交接是该测量的阻塞项。

**冻结时的真实状态**：Task 1、Task 2 已完成并通过（含 A1/A2 两个补洞），§8 的数字是
冻结点基线。Task 3 的核心缺口（grant 仍是 telemetry，见 §5 P1-A）**未修**——解冻时
这仍是 R-10 能否结案的决定项。

### Task 3（冻结）：watchdog + 真 grant + 迟到隔离

除原计划测试外，必须新增/加强：

- runner 内调用 `AgentToolContext.timeout()`（`agent_research.py:234`），断言不超过
  effective grant；
- mailbox request 人为排队后，runner grant 扣除已消耗的 client transport 时间；
- direct slow tool 在 handoff / transport 两种 limiter 下都先于 wrapper 60s 返回；
- timeout 后 snapshot 前后逐值相同，QueryLedger `executed_count == 0`；
- 真实生成的 mailbox wrapper 收到 instruction 后产生事件级 `model_finish`；
- transport `response_path_conflict` 不计第二执行终态。

### Task 4-6

- **Task 4**：focused suite + 两个 clean-host 全量 scope；新红必须与父 revision 按 node id
  对账（用临时 detached worktree 跑父 revision，不要凭印象判断"本来就红"）。
- **Task 5**：只跑一次 `c_long_capped/ruihuatai-valuation`，不重跑四臂/五题。产物落
  `intelligence/eval/measurements/2026-08-04c-inflight-handoff/`。
- **Task 6**：写 `docs/verification/2026-08-04c-headless-inflight-handoff.md`，按预注册分支
  更新 prediction ledger（R-10 只能填 `confirmed`/`refuted`，部分验证**不准**写
  `confirmed`）、trace profile、handoff 与 project memory；最后 push 当前分支，**不合并
  main**。

完整计划：`docs/superpowers/plans/2026-08-04-headless-inflight-tool-handoff.md`。

### ⚠️ 计划文件哪些部分已作废

计划**整体仍然有效**，但 Task 2 被本轮部分推翻，读的时候要带着这张表：

| plan 位置 | 状态 |
|---|---|
| Task 2 Step 3 的 `_root_budget_rejection()` / `_begin_finalization_locked(request_id=...)` | **仍然有效**，直接照抄 |
| Task 2 Step 4 的"执行后 `_charge_root_budget()`" | **已作废**，被 §5 P1-B 的并发 race 推翻 |
| Task 2 Step 1 的两个测试片段 | 已被工作树里更强的版本取代（含并发用例） |
| Task 1、Task 3-6 | 未改动 |

## 10. 不要踩的坑

- 顶层 `completed` 或 `elapsed <= root` 都不是成功门禁。
- `tool_grant_seconds` 是执行权，不是自然耗时，也不能只记录不执行。
- `consume_call()` 放在 runner 后面无法修复并发 race。
- timeout/cancel 后不要 `join()` daemon worker，也不要用 done callback 发布结果。
- finalization 必须是真实交接点，不是为了填充事件计数。
- `tool=mailbox,error=response_path_conflict` 是 transport 诊断，不是第二执行终态。
- 不动预算 / profile / prompt / model / provider，不跑额外 live 调试题。
- 不打印或写入任何 API key；服务环境必须从真实进程复制，不抄文档。
- 离线主门没全绿之前不要跑 live——那次 live 会作废，且 R-10 的预注册条件不允许补跑
  当借口。

## 11. 当前停点

实现代理已被显式中止，没有后台 agent 或测试进程需要等待。工作树故意保持：

```text
 M intelligence/tests/test_headless_tool_gateway.py
```

下一位从 §3 的 RED-only commit 开始，然后进 Task 2。不要重做 Task 1，不要先跑 live。

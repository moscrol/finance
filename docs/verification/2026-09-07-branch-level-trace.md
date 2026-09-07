# 分支级 trace → 账本口径 → 分支契约：候选口同题四遍（2026-09-07 上午，PR #619）

上文：`2026-09-07-branch-budget-repair-fuse.md`（同题四遍撞出三道顶，#615–#617）。那份收据 §5 留的下一步是
「分支起步用 quick 档的 4 次每批帽，可能是分支慢的原因之一，**先量分支内每批派发数再动**」。
本文从「先量」开始（§1–§3），量出两道新顶（§4），用户拍 C 修账本口径（§5），再修分支契约（§6）。
**quick 每批帽 4 全程未动，28 题未跑，8792 未切。**

| 提交 | 内容 |
|---|---|
| `66de98c2` / `fc367365` | 分支逐批派发账 + 预算账进收据 |
| `ad54d4b0` | 分支 `invalid_action`（终局拒绝码）随结果出来 |
| `4f79bd56` / `14ef58d3` | `sub_research` telemetry 带父账本前后余量；live 第 1、2 遍收据 |
| `204e607a` | **C**：分支秒按墙钟记一次 + 起分支前父臂预留尾段（次数 / 秒 / 保险丝） |
| `64428242` | 分支契约声明唯一 output `branch_findings`，收尾不再撞 `unknown_output` |

## 0. 为什么先补 trace 而不是直接改帽

对 #615–#618 这条线做过一次六层巡检（09-07 上午），L6 可观测的结论是：现有收据够说明「终局发生了什么」，
但分支内部「每批点了几个、几个被帽拒、分支还剩多少秒」由原始 trace 算不出来，收据里的 28/17 次调用是人工整理的。
核对代码后这条要分两半说：

- **已经落盘的**：每支分支的 `status / evidence_count / llm_calls / tool_calls` 进了父臂 `sub_research` 的
  `tool_result.telemetry`（`research_harness.py` 把 telemetry 写进 audit 底稿）和 durable `branch_completed` 事件。
  分支合计数其实可以重算。
- **真没落盘的**：分支自己那个 `ContinuousAgentEpisode` 没接 `event_sink`，它的 `outcome.events`
  在 `ContinuousSubResearchWorker.run` 里被整段丢掉，`BranchResult` 只保留 `traces`。
  逐批 `tool_request` / `tool_error(tool_budget_exhausted)`、`remaining_slots_at_dispatch`、
  `_BranchBudgetView` 的 `allocated / remaining` 都在这一步消失。

所以「分支慢是不是每批帽 4 咬的」这个问题，当前 trace 回答不了；改帽前先让它能回答。

## 1. 改了什么（4 个 runtime 文件，standard / deep / max 的任何数字都没动）

| 处 | 改动 |
|---|---|
| `runtime/sub_research.py` | 新增 `BranchBatch`（一批的派发账：requested / succeeded / rejected_by_cap / timed_out / errored / rejected_other / tools + 派发时钟三元组）、`BranchBudgetReceipt`（allocated_calls / consumed_calls / allocated_seconds / remaining_seconds / batch_call_cap）、纯函数 `branch_batches_from_events(events)`；`BranchResult` 加 `stop_reason / batches / budget` 三个可选字段；协调器 `_run_one` 从 `_BranchBudgetView` 读出预算账挂上（worker 自报无效，与 `tool_calls` 同一纪律） |
| `runtime/continuous_sub_research.py` | worker 返回前把 `outcome.events` 切成 `batches`、摘出 `invalid_actions`（终局拒绝码 code / kind / disposition）、带出 `stop_reason`（此前 partial 分支「为什么停」只能从 gaps 文案猜） |
| `runtime/sub_research_tool.py` | 新增 `branch_telemetry(branch)`：一支分支进收据的全部字段。有账写全，没账（取消 / worker 异常）不写键。runner 另记父账本分支前后余量 `root_budget.before / after_branches` |
| `runtime/agent_episode.py` | PLAN 路径与工具路径的 `branch_completed / branch_failed` payload 都改用 `branch_telemetry`——此前两处各写一份，字段已经漂开（事件有 tokens、telemetry 没有） |

派发账从**事件**重算而不是 worker 自述：每一批 `requested == succeeded + rejected_by_cap + timed_out + errored + rejected_other`
恒成立，对不上就是事件流本身缺条。`rejected_by_cap` 对应 `tool_budget_exhausted`，事件里每批帽与分支剩余次数两种来源同码，
靠同批的 `remaining_slots_at_dispatch` 分：剩余 ≥ requested 而仍被拒，就是帽咬的。

事件本体仍**不进**父账本：父臂一条 `tool_result` 的审计底稿装不下三支分支的整条事件流；进的是摘要。

## 2. 测试（9 新，8 个变异各击杀 ≥1）

| 测试 | 钉什么 | 变异 → 红 |
|---|---|---|
| `test_branch_batches_are_cut_at_model_turns_and_classify_every_tool_error` | 一条 `model_turn` 开一批；五类 error 码分类；无工具的模型轮不算批；末批无后继 `model_turn` 也入账；缺席时钟字段不写键 | 去掉末尾 `flush()` → 1F；`tool_budget_exhausted` 分类改掉 → 2F |
| `test_continuous_branch_worker_reports_per_batch_dispatch_and_the_cap_that_bit` | max 档分支拿 10 次 / 150s；模型一轮点 5 个 → 4 成功 1 `rejected_by_cap`，`remaining_slots_at_dispatch=10`，`batch_call_cap=4`（quick 标签的帽，不是 max 的 8） | worker 不带 `batches` → 1F |
| `test_branch_budget_receipt_comes_from_child_ledger_not_worker_claims` | worker 自报 99/99/9999 被协调器用子账本真值 8/1/60 覆盖 | 协调器不挂 `budget` → 2F |
| `test_failed_or_cancelled_branches_carry_no_budget_or_batches` | worker 异常的分支 `budget is None`、`batches == ()`；类型守门 | — |
| `test_telemetry_carries_budget_and_per_batch_dispatch_only_when_measured` | telemetry 有账写全、没账不写键；`branch_telemetry` 与 telemetry 逐字同源 | telemetry 去掉 `budget` → 2F |
| `test_branch_completed_event_carries_budget_and_batches_from_the_tool_path` | 工具路径的 durable `branch_completed` 带 `stop_reason / budget / batches`；同一 run 的 `sub_research` `tool_result.telemetry` 也带 | 同上 |
| `test_branch_invalid_actions_are_lifted_with_their_rejection_code` | `invalid_action` 逐条摘出、顺序保留、缺字段不写键、reason 截 200 | — |
| `test_continuous_branch_worker_surfaces_a_rejected_finish_with_its_code` | 分支模型把结论绑到契约没有的 output → `unknown_output / integrity / integrity_violation` 随 BranchResult 出来（第 1 遍 live 的假设机制） | worker 不带 `invalid_actions` → 1F；telemetry 去掉 → 1F |
| `test_bound_runner_records_parent_ledger_before_and_after_branches` | 三支各记 150s 后父账本 540 → 90 直接可读；无账本不写键 | runner 不传 `root_budget` → 1F |

读数（解释器 `.venv-workbench/bin/python`，树 `~/fwp-wt-branch-trace` @ `504cbbc9` + 本改动）：
`test_sub_research.py` + `test_sub_research_tool.py` 36P/0F（基线 27）；邻接 10 个套件 272P/0F；
`ruff check .` 全仓通过；全量 pytest：`66de98c2` 干净树 **7986P / 0F / 76S / 1 xfail**；`4f79bd56` 干净树第一遍
7988P / **1F**（`test_run_agent_runtime_benchmark::test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state`，
拿 `id(context)` 比两个已释放对象、地址复用 `4845507632 != 4845507632`，单跑即绿，与本改动无关），第二遍 **7989P / 0F**；
`check_test_receipt.py --expect-revision HEAD --base-drift-max 5` 判「可采信」（revision 一致 / 干净树 / 依赖指纹一致 / 基座漂移 0）。

## 3. 顺手核对的三条审查措辞（写进这里，免得下一个人再发现一遍）

1. **「max 没有贯穿子环路」要说准**：分支的**数值**预算随档位走（#615，max 10 次 / 150s，本次测试实测 `allocated_calls=10, allocated_seconds=150`）；
   钉死成 quick 的是**标签**，且是三层叠加——`sub_research._request` 的 `ResearchPolicy("quick", …)`、
   `continuous_sub_research` 契约的 `research_tier="quick"`、harness 的 `ModeSignals(user_mode="quick")`。
   标签真正改变的行为查到两条：`batch_call_cap` 只认 `tier == "max"` 才给 8（分支拿 4）；`ask.py` 把「任务档位=quick」写进分支模型的提示词。
   `derive_stage_caps` 按数值算，不受标签影响。
2. **「关键数字靠人工整理」分两半**：分支合计数早已落盘（见 §0）；没落盘的是分支内逐批账——本 PR 补的就是这一半。
3. **「repair 输入输出不能重算」不成立**：父臂修复轮的 `repair_goal`（`RepairGoal.to_dict()`，含 `unreachable_without_tools`）、
   `repair_reentry`（时钟三元组）、`model_turn(phase=repair)`（含模型回文）都在 durable 事件里。审查这条可以撤。

另：8792 当前进程（PID 56492，cwd `finance-workspace-d65ed0155eb9`）env 为 `WORKBENCH_RESEARCH_TIER=max`、
`WORKBENCH_TOOL_AUTHORIZATION=all`、`WORKBENCH_TOOL_MENU_HIDE=off`；代码默认三者皆关。`capability_switchboard.json`
注明 `sub_research` 只在 `AUTHORIZATION=all` 下进授权——max 档能力与 sub_research 可用性被同一个粗粒度 env 绑在一起，
这是「应由 registry + 显式 tier grant 控制」那条建议的具体形态。

## 4. live 读数：候选口 8799，同题两遍（10:56 / 11:09 CST）

不切 8792：从本分支树起候选口 `127.0.0.1:8799`（`/tmp/start-candidate-8799.sh` = 生产启动器只改代码根与端口，
env 逐字相同：`WORKBENCH_RESEARCH_TIER=max` / `TOOL_AUTHORIZATION=all` / `TOOL_MENU_HIDE=off`，sol@57244 主、terra 兜底，
判官 grok-cli），`/api/health` 自证 `source_dirty=false`，readiness 与 8792 同一条红（`market_data_consistency`，日常窗口）。
探针用户 `probe-branchtrace-0907`，题目与 #618 四遍同一道（固态 vs 钠电 `theme_track`）。**8792 全程未动。**

| 遍 | 代码 | run | 父臂 | 判官 | 分支 |
|---|---|---|---|---|---|
| 1（10:56） | `fc367365` | `run_20260907_105656_605883` | completed，200s，4 次模型调用 | repaired | partial ×3，`invalid_model_finish`，各剩 71 / 38 / 81s，零超时 |
| 2（11:09） | `ad54d4b0` | `run_20260907_110932_860284` | **partial，`deadline_exhausted`，224s 停，墙钟还剩 396s** | **unavailable** | partial ×3，`deadline_exhausted`，各剩 0s，零超时 |

逐批派发账（`requested→succeeded`，`+n` = `rejected_by_cap`）：

| 遍 | branch-1 | branch-2 | branch-3 | 帽拒 / 请求 |
|---|---|---|---|---|
| 1 | 5→4 +1 · 5→4 +1 · 1→1 | 5→4 +1 · 6→4 +2 · 2→2 | 6→4 +2 · 4→4 · 1→1 | 7 / 40 |
| 2 | 7→4 +3 · 6→4 +2 · 2→2 | 5→4 +1 · 5→4 +1 · 2→2 | 6→4 +2 · 4→4 | 9 / 37 |

每一次被帽拒时 `remaining_slots_at_dispatch`（10 / 6）都 ≥ `requested`——拒的是**每批帽 4**，不是分支剩余次数。
预算账：每支 `allocated_calls=10, allocated_seconds=150, batch_call_cap=4`；第 1 遍 consumed 9 / 10 / 9，第 2 遍 10 / 10 / 8。

### 4.1 帽 4 在咬，但两遍的 partial 都不是它造成的

- 17 批里 8 批被帽拒，16 / 77 个请求被打回，模型下一轮得再点一遍——这是帽的**代价**（多一个模型往返），成立。
- 但第 1 遍分支各剩 38–81s、零超时就停了：终局理由 `invalid_model_finish`，即分支模型的收尾 JSON 被出口拒。拒绝码当时
  没带出来（`invalid_actions` 摘要是第 1 遍之后才加的，`ad54d4b0`）。单测复现了一条同形状路径：分支契约 `required_outputs=()`，
  模型把结论绑到父题的 output id 上 → `unknown_output` / `integrity` / `integrity_violation`，INTEGRITY 类不回灌、直接 partial。
  这是假设，下一遍 live 由 `branch_completed.invalid_actions[*].code` 判。
- 第 2 遍分支是真撞 150s：三支首次派发时只剩 85–96s，即**首轮模型调用花了 55–65s**（第 1 遍同一位置约 7s；同一网关，
  sol 延迟波动），之后三批工具把余量吃完。帽在这里的代价被放大：每多一轮往返 = 多一次 60s 级的模型等待。

### 4.2 新顶：父账本把并行分支的秒**累加**，再被本批墙钟记第二次

第 2 遍父臂在 224s 停、`stop_reason=deadline_exhausted`，而 `tool_request.episode_remaining_at_dispatch=396s`——墙钟没到，
是**账本秒**先空了（`agent_episode` 第二轮 `model_turn` 后 `_consume_root_seconds` 抛 → 冲掉待发工具 → 停机）。账本算术：

```
root initial_seconds = 600 − 60 = 540
− 父臂首轮 model_turn                              10
− 三支分支经 _BranchBudgetView 各记 150            450   （并行 150s 墙钟，记 3 份）
− 父臂 _settle_batch_calls：本批 4 个调用 × 180/4  180   （同一段墙钟再记一次，且 3 个 <1s 的 lookup 各背 45s）
= −100  → 第二轮 model_turn（13s）consume_seconds 失败
```

spec `2026-09-03-subagent-tool-design.md` §6-4 写的是「三支总耗 ≤ 3 × 60s，父 remaining_seconds 单调减」——累加是当时的设计，
deep 档 3 × 60 = 180 装得进 192s 的账本；#615 把每支抬到 150 后 3 × 150 = 450 只给父臂留 90s，再被批结算记一次就穿。
这就是同题同码两遍一 completed 一 partial 的机制：**触发条件是分支首轮模型延迟**，分支跑满 150s 父臂必死，判官必 unavailable。
它不是能力上限，是账本口径。#617 把 LLM 调用保险丝 40 → 120 解的是「次数」那本账；「秒」这本账没人碰过。

## 5. 用户拍 C（11:20）：秒按墙钟记一次 + 起分支前父臂预留尾段（`204e607a`）

三个形状（A 秒=墙钟 / B 保留累加去重复 / C 准入分层预留 = A 口径 + B 预留）用户拍 C，原则是「尽量探寻能力 max，
不让约束把能力挡住」——三支跑满就把父臂挤死，正是约束放错了地方。

- **口径**：`_BranchBudgetView` 只向父账本扣**次数**（新 `RootBudgetLedger.consume_call_slot`），秒留在分支自己的视图里守 150s
  与出收据；父账本的秒由父臂对 `sub_research` 那一批做批结算时按墙钟记一次。调用仍从父账本扣：调用是真实共享资源，并行不会让它变便宜。
- **准入**（`admit_branches`）：父臂先留一批次数（`batch_call_cap`：max 8 / 其它 4）、一次合成的秒（`synthesis_reserve`：max 60）、
  保险丝尾段 8 次（`PARENT_TAIL_LLM_RESERVE`，读 turn 级 `LLMCallLedger.headroom()`）；分支拿剩下的，秒**不再按支数除**（并行共享一段窗）；
  留不下就拒，理由分账本：`parent_reserve_exhausted:calls|seconds` / `llm_call_reserve_exhausted`；准入账（预留多少、每支拿多少、
  保险丝余量与预计用量）进 telemetry，拒绝时也带。
- 数字：max 档三支仍 10 次 / 150s（与 #615 相同）；deep 两支 6 → 4（此前分支回来父臂一次工具都发不出）。
- spec `2026-09-03-subagent-tool-design.md` §6-4 改口径，原文与理由留在旁边。

## 6. live 第三、四遍：C 生效；分支 partial 的真因与修法（`64428242`）

| 遍 | 代码 | run | 父臂 | 判官 | 账本秒（分支前 → 后 → 收尾） | 分支 |
|---|---|---|---|---|---|---|
| 3（11:57） | `204e607a`（C） | `run_20260907_115729_781807` | completed，200s，`model_finish` | **passed** | 480.3 → **480.3** → 339.6 | partial ×3，`invalid_model_finish`，各剩 60 / 68 / 91s |
| 4（12:09） | `64428242`（C + 分支契约） | `run_20260907_120927_086134` | completed，223s，`repair_model_finish`（修复 1 轮） | repaired | 532.4 → **532.4** → 357.3 | partial ×3，**`model_finish`**（收尾被接受，模型自报缺口 4 / 6 / 5） |

- **C 生效**：两遍分支前后父账本秒一分未动（`root_budget.before == after_branches`），父臂收尾时账本还剩 340 / 357s，
  判官两遍都上场。第二遍那种「墙钟剩 396s、账本归零」的形状没有再出现。准入账：第 3 遍父臂先自己跑了 3 批（用掉 15 次），
  `root_remaining_calls=25` → 留 8 → 每支 5 次；第 4 遍首轮就点 `sub_research`，40 → 留 8 → 每支 10 次。
- **分支 partial 的真因**（第 3 遍 `invalid_actions` 首次带出）：三支收尾全是 `unknown_output` ——
  `unknown required output: window_progress / baseline_judgment / trading_heat`。宪法要求「正文事实绑到对应 required output」
  「completed 必须覆盖所有 required outputs」，而分支契约 `required_outputs=()`：模型被要求绑定却没有合法目标，只能自己造 id，
  撞 INTEGRITY 不回灌 → 必 partial、白烧一次收尾调用、父臂收到「模型未能返回可验证的结构化终止结果」这条假缺口。
  证据本身照旧回父账本（20 / 11 / 38 条），所以这条一直没被当成故障。三遍 live 6/6 支同一形状。
- **修法**（#616 同族，`continuous_sub_research.BRANCH_FINDINGS_OUTPUT`）：分支契约声明唯一 output `branch_findings`
  （required、evidence），取证绑上去就是合法收尾；绑自造 id 仍 INTEGRITY（单测两条都钉住）。第 4 遍 3/3 支收尾被接受，
  `invalid_actions` 为空；仍是 partial 是**模型自己**报的缺口（各支 4–6 条，如缺一手公告），父臂能读、能用。
- 每批帽 4 在第 3、4 遍**一次都没咬**：模型改成每批点 1 个工具（9 批 × 1）。第 1、2 遍每批点 5–7 个。同一模型同一题，
  两种节奏都出现过；帽 4 不动的决定不变，它现在既不是瓶颈也不是首要变量。
- 帐：四遍 live 各约 200–270s、父臂 input_tokens 34 万–110 万；候选口全程 8792 未动。

### 6.1 测试 / 门禁

`test_sub_research.py` + `test_sub_research_tool.py` **42P/0F**（基线 27，新增 15）；14 个变异各击杀 ≥1（含：分支秒再记父账本 → 红、
去预留 → 红、去保险丝准入 → 红、秒再按支数除 → 红、分支契约退回无 output → 3 红）。干净树全量 `64428242` **7995P / 0F / 76S / 1 xfail**，
`check_test_receipt.py --expect-revision HEAD --base-drift-max 5` 可采信。

## 7. 未做 / 待拍

- 合入 #619 → 切 8792。切后同题再跑一遍读 `branch_completed.stop_reason`（应为 `model_finish`）与 `root_budget`（`before == after_branches`）。
- 分支模型自报的缺口（缺一手公告等）是真缺口，属于工具面 / 数据面，不是运行时约束。
- quick 每批帽 4 不动。A/B/C 28 题仍等用户拍。
- 顺带发现：`test_run_agent_runtime_benchmark::test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state` 用 `id()` 比两个已回收对象，
  地址复用时假红（本 PR 一遍全量撞上，复跑即绿），值得改成持有引用；不在本 PR。

## 8. 能力 frontier 向量（路线第 4 步）：同题六遍并排

`python -m intelligence.eval.capability_frontier <run_dir>… --format md|json`（`intelligence/eval/capability_frontier.py`，只读工件、不调模型）。
七个轴：工具发现 / 证据产出 / 上下文效率 / 修复恢复 / 验证完整性 / 墙钟 / 分支健康度；缺件留 `—`（None），不写 0。
下表第一行是 #618 那份收据的第 4 遍（`d65ed015`，切前 8792），后五行是本文的候选口四遍 + 切后 8792 一遍：

| run | rev | status/stop | judge | tools used/offered | evidence parent+branch/bound | input tok / llm | repair | episode s / sub_research s / ledger left | branches ok/partial/fail · accepted · invalid · cap rej/req | branch→parent s |
|---|---|---|---|---|---|---|---|---|---|---|
| run_20260907_042658_105490 | d65ed0155eb9 | completed / model_finish | repaired (unavail 0, degraded 0) | 7/14 (父 7 · 支 0) | 161+147/45 | 657700 / 5 | 0 attempt(s) | 172.3 / 87.2 / 143.4 | 0/3/0 · — · — · —/— | — |
| run_20260907_105656_605883 | fc36736539fc | completed / model_finish | repaired (unavail 0, degraded 0) | 10/14 (父 7 · 支 8) | 167+147/33 | 475828 / 4 | 0 attempt(s) | 190.6 / 111.8 / 90.8 | 0/3/0 · 0 · 0 · 7/35 | — |
| run_20260907_110932_860284 | ad54d4b0a3c8 | partial / deadline_exhausted | unavailable (unavail 1, degraded 0) | 10/14 (父 7 · 支 8) | 187+159/0 | 342318 / 2 | 0 attempt(s) | 224.0 / 180.0 / 0.0 | 0/3/0 · 0 · 0 · 9/37 | — |
| run_20260907_115729_781807 | 204e607aa153 | completed / model_finish | passed (unavail 0, degraded 0) | 10/14 (父 9 · 支 6) | 226+69/53 | 635647 / 6 | 0 attempt(s) | 200.6 / 89.7 / 339.6 | 0/3/0 · 0 · 3 · 0/14 | 0.0 |
| run_20260907_120927_086134 | 64428242cc3c | completed / repair_model_finish | repaired (unavail 0, degraded 0) | 11/14 (父 8 · 支 8) | 204+185/36 | 1102840 / 5 | 1 attempt(s) | 222.9 / 109.9 / 357.3 | 0/3/0 · 3 · 0 · 0/27 | 0.0 |
| run_20260907_123827_249342 | 1010970acc85 | completed / repair_model_finish | repaired (unavail 0, degraded 0) | 9/14 (父 4 · 支 7) | 165+140/23 | 707055 / 9 | 1 attempt(s) | 227.7 / 114.0 / 352.5 | 0/3/0 · 3 · 0 · 5/35 | 0.0 |

- run_20260907_105656_605883: branch stop_reasons not accepted: invalid_model_finish
- run_20260907_110932_860284: ledger seconds exhausted (stop_reason=deadline_exhausted): check wall clock vs ledger
- run_20260907_110932_860284: branch stop_reasons not accepted: deadline_exhausted
- run_20260907_115729_781807: branch finish rejected: unknown_output
- run_20260907_115729_781807: branch stop_reasons not accepted: invalid_model_finish

读法：
- **`completed / judge repaired` 六遍里五遍都有，但只有最后三遍的分支收尾是被接受的、父账本秒没被分支扣走**——
  单看终局标签，第 1 遍和第 4、5 遍长得一样；分支健康度与「branch→parent s」把它们分开。
- 上下文效率是下一道顶的候选：父臂每次模型调用 11 万–22 万 input tokens，整轮 34 万–110 万；分支回流 140–185 条证据全部进了父臂消息，
  而最终绑上的只有 23–53 个 hash。放开预算后，「证据怎么回父臂」比「再给多少秒」更决定能力上限。未量、未改。
- 工具发现 7–11 / 14：分支把工具面扩到父臂契约之外（比值可 >1）；`sub_research` 之后模型自己再点的工具数没有下降。
- 帽拒 0–9 / 14–37：同模型同题两种节奏（每批 1 个 vs 5–7 个）都出现；不是首要变量。

## 9. 0907h：L3 一手口径打通（#623 + 启动器 `--source cninfo,irm_szse`），8792=`d4cb6484`

向量 §8 的「证据产出」轴里有一项一直是零：同题五遍父臂 8 次 `l3_lookup` 全空，分支零条 l3 证据，答案只能写
「公司公告检索未取得可用一手证据」。拆开是三半：

1. **题材名被当公司名**：一半 query 是「固态电池 量产 产线 公告」，`_extract_stock_hint` 抓「固态电池」当公司送 CLI，
   CLI 回 `[warn] 无法解析公司` + `[]`，解析侧只剩「查询成功但没有解析到可用证据」——模型分不出「没公告」和「不是公司」。
   修：多一条可操作警告（只按公司名 / 6 位代码查，题材走 news/web）；真公司只有 P2 定期报告时不给这条。
2. **互动易行只给提问、丢答复**：`irm_szse` 行 `summary` 是投资者提问，公司答复在 `raw_excerpt` 的「||答复：」之后，
   常是否认 / 反证（`is_reverse=True`）。修：summary = 提问头 ‖ 答复：…，标题加 `[反向口径]`。
3. **生产只开了 cninfo**：启动器 `FINANCE_L3_COMPANY_CMD` 写死 `--source cninfo`，互动易通道整个不可见；cninfo 近 90 天多为
   P2 定期报告，被低信号门丢掉。实测 `irm_szse`：盛弘股份 P0 ×2、0.3s；SSE 公司上该源报 warn、cninfo 结果照常。
   改启动器为 `cninfo,irm_szse`（备份 `.bak-20260907-pre-irm`，回滚锚 `cutover-20260907h-l3irm-rollback-8792.txt`）。

切后同题探针 `probe-cutover-0907h/run_20260907_134001_643129`：**l3 证据 7 条**（父臂 1 次调用 5 条 + 分支 2 条），
含万顺新材投关原话「高达因电池铝箔…6 月末开始进入中批量供货阶段」——上一遍答案里那句「万顺新材中批量供货目前仅有新闻转述」
现在有公司自己的口径可绑；另有盛弘股份 `[反向口径]` 否认。父臂 completed、judge repaired、`judge_unavailable_count=0`、
`content_degraded_count=0`、父账本秒分支前后 512.1 → 512.1。门禁：main tip `d4cb6484` 干净树 8000P/0F/77S 可采信；webapp 与 `1010970a` 逐字节相同。

同时暴露下一道顶（本轮只记录）：这一遍父臂 **19 次模型调用、126 万 input tokens、406s**——`sub_research` 之后连续 17 轮每轮只点 1 个工具
（前几遍是 4–6 个一批），每轮都把整个上下文重发一遍；分支 2、3 在同一时段 `model_unavailable`（sol 网关并发下失败）。
「每批 1 个工具」这个节奏在分支（第 3、4 遍）和父臂（本遍）都出现过，与 `_append_tool_budget_state` 注入的余量文案是否有关未量。
上下文效率 + 派发节奏是接下来最值钱的一刀，比再抬任何预算数字都值。

| run | rev | status/stop | judge | tools used/offered | evidence parent+branch/bound | input tok / llm | repair | episode s / sub_research s / ledger left | branches ok/partial/fail · accepted · invalid · cap rej/req | branch→parent s |
|---|---|---|---|---|---|---|---|---|---|---|
| run_20260907_123827_249342 | 1010970acc85 | completed / repair_model_finish | repaired (unavail 0, degraded 0) | 9/14 (父 4 · 支 7) | 165+140/23 | 707055 / 9 | 1 attempt(s) | 227.7 / 114.0 / 352.5 | 0/3/0 · 3 · 0 · 5/35 | 0.0 |
| run_20260907_134001_643129 | d4cb64844ec6 | completed / model_finish | repaired (unavail 0, degraded 0) | 12/14 (父 11 · 支 7) | 121+67/20 | 1264726 / 19 | 0 attempt(s) | 406.3 / 178.4 / 134.4 | 0/3/0 · 1 · 0 · 0/18 | 0.0 |

## 10. 上下文效率量出来了：成本 = 轮数 × 历史长度，工具消息稳定 8–12 万字、重发量随轮数走

frontier 向量新增一轴（`capability_frontier.ContextEfficiency.tool_message_chars / resent_chars_estimate`）：按 harness 同一套投影
（`prune_tool_observation → budget_tool_observation → strip_hashes_for_model`）从审计底稿重算每条 tool 消息进模型的字数，
再按「之后还有几轮」累计重发量。同题七遍：

| run | rev | 模型轮数 | input tokens | 工具消息合计字数 | 后续轮重发累计 | 最大一条 |
|---|---|---|---|---|---|---|
| 042658（#618 第 4 遍） | d65ed015 | 5 | 657,700 | 78,639 | 282,647 | sub_research 61,066 |
| 105656 | fc367365 | 4 | 475,828 | 81,765 | 221,324 | sub_research 62,227 |
| 110932 | ad54d4b0 | 2 | 342,318 | 94,394 | 76,612 | sub_research 70,255 |
| 115729 | 204e607a | 6 | 635,647 | 125,625 | 365,505 | sub_research 31,972 |
| 120927 | 64428242 | 5（含修复 1 轮） | 1,102,840 | 100,162 | 388,214 | sub_research 82,436 |
| 123827（8792） | 1010970a | 9 | 707,055 | 77,133 | 499,660 | sub_research 62,400 |
| 134001（8792） | d4cb6484 | **19** | **1,264,726** | 77,249 | **962,987** | sub_research 34,584 |

读法：
- 工具消息本身**不是**变量：七遍合计 7.7–12.6 万字，最大一条永远是 `sub_research`（3–8 万字，140–185 条证据每条都进）。
- 变量是**轮数**：19 轮那遍把 7.7 万字的历史重发了 96 万字，占 126 万 input tokens 的一大半；其余是每轮重发的宪法 + 契约 + 工具表 + 已有对话。
  每轮 sol 在 10 万+ tokens 上下文上 5–10s，17 轮单工具派发 ≈ 150s 纯模型等待，是那遍 406s 的主因。
- 「每批只点 1 个工具」在分支（第 3、4 遍）和父臂（第 7 遍）都出现过，前几遍父臂是 4–6 个一批；同模型同题两种节奏都有，**触发条件未知**。
  `_append_tool_budget_state` 注入的是「下一轮工具调用总数不得超过 remaining_tool_calls」——是上限，不是鼓励并行。

两把杠杆（待拍，本轮只量不改）：
- **派发节奏**：在同一条注入里加「互不依赖的工具应同一轮一起点（每批最多 `batch_call_cap` 个），一轮一个是浪费」。改的是 harness 自己的
  steering 通道，不是宪法；效果得 live 量（同 rev 同题 N 遍看 `llm_calls` 与每批 requested），n=1 说不了话。
- **历史压实**：只保留最近 K 条工具观察原文，更早的折成「E12–E48 已入账，标题见证据表」的存根；证据仍可按 E 号绑。
  这是 dsh / pi 都有的 context compaction 形状，但会动模型看见的历史，需要单独 spec + 单变量 A/B，不能顺手改。
两把都不动 sub_research 那条 3–8 万字的消息本身——那是分支真取到的证据，是能力不是浪费；动它等于把分支放大的工具面再收回去。

## 11. 派发节奏第一把杠杆：预算注入加「同一轮一起点」（`7980be36`），候选口同题两遍

改的是 `_append_tool_budget_state` 这一条 harness 自己的 steering 注入（不动宪法）：原文只有「下一轮工具调用总数不得超过
remaining_tool_calls」这一句**上限**；现在同一条带 `per_batch_cap = min(每批帽, 剩余)` 和「互不依赖的工具应在同一轮一起点出
（本轮最多 N 个）：一轮只点一个会多花一轮模型往返并重发整段上下文；只有下一步取决于上一步结果时才逐轮点」。只剩 1 次不说；
没传帽的调用方（参考 loop）逐字节同前。第一轮没有注入，第一轮的节奏不归它管。

候选口 8799（启动器与 8792 逐字相同，含 `irm_szse`），同题两遍：

| run | 父臂每轮点几个 | 父臂 llm / input tok | 分支每批 requested | 判官 |
|---|---|---|---|---|
| `run_20260907_161318_091726` | [1, 1, 1, 6, 0] | 5 / 517,243 | b1 [1,4,4] · b2 [4,4,2] · b3 [6,4,2] | repaired，degrade 0 |
| `run_20260907_161748_970275` | [1, 8, 1, 1, 0] | 5 / 699,776 | b1 [1,4,4,1] · b2 [1×9] · b3 [1,4,4] | repaired，degrade 0 |

读法（n=2，是方向不是比例）：
- **分支侧明显跟着走**：6 支里 5 支从第二批起按 4（分支帽）一批点，此前第 3、4 遍的分支是 [1,1,1,…]；b3 甚至一批要了 6（帽拒 2）。
  「本轮最多 4 个」那个数字看起来直接成了锚。1 支（run B 的 b2）完全没理、9 轮各 1 个——并且是七遍里第一支自报 completed 的分支。
- **父臂部分跟着走**：两遍都有一次大批（6 / 8），但仍各有 2–3 轮单工具；父臂 5 轮 / 51–70 万 tokens，落回第 1–5 遍的区间（4–6 轮），
  没有再出现第 7 遍那种 19 轮 / 126 万。第 7 遍本身是离群点，所以这条只能说「没变坏、分支变好」。
- 出口没变：两遍判官 repaired、`judge_unavailable_count=0`、`content_degraded_count=0`、分支收尾 6/6 被接受、父账本秒分支前后不动、
  l3 证据 7 条。

决定：合入切流。理由是它只加了一句期待、没加任何上限，分支侧读数方向明确，出口层零变化；父臂那 2–3 轮单工具留给下一步
（第一轮无注入、以及模型自己的「先看一条再决定」）。历史压实那把杠杆继续留在 §10 待 spec。

## 12. 0907i：派发注入合入切流（#628，8792=`b594a5e7`），切后同题一遍——分支跟、父臂不跟

切后探针 `probe-cutover-0907i/run_20260907_164332_208527`：completed（修复 1 轮）、judge repaired、`judge_unavailable_count=0`、
`content_degraded_count=0`、l3 证据 8 条、分支收尾 3/3 被接受（1 支 completed）、父账本秒分支前后不动。**但父臂 10 轮里 8 轮每轮只点 1 个工具**
（[1,1,1,1,1,1,1,1,0,0]），97 万 input tokens、417s；分支 b1 [4,4,2]、b2 [5,4,2] 跟着帽走，b3 [1×9] 没理。

合并 n=3（候选口两遍 + 8792 一遍）：分支 9 支里 7 支从第二批起按帽成批，此前分支是逐个点；父臂三遍分别 [1,1,1,6,0]、[1,8,1,1,0]、
[1,1,1,1,1,1,1,1,0,0]——**这句话对父臂没有可靠效果**。看父臂单工具轮点的是什么：`sub_research` 之后多是 web_search → web_fetch →
l3_lookup（按上一步结果决定下一步），这类本来就该逐轮点；注入里那句「只有下一步取决于上一步结果时才逐轮点」恰好放行了它们。
所以父臂那部分成本不是节奏问题，是**每一轮都把 5–8 万字的 `sub_research` 消息和整段历史重发一遍**——第二把杠杆（历史压实）才是父臂的解。

决定：#628 留着（分支侧有效、出口零变化、不加上限）；父臂的上下文成本进下一刀，需要单独 spec：只保留最近 K 条工具观察原文、
更早的折成「E12–E48 已入账，标题见证据表」存根，证据仍按 E 号绑；单变量 A/B 用 `capability_frontier` 的 `resent_chars_estimate` 与
`input_tokens / llm_calls` 判。0907i 的 main tip 同时带了 #627（授课框架，`services/teaching_framework` 等，不在本线），回滚锚
`cutover-20260907i-pacing-rollback-8792.txt`（回 `d4cb6484`）。

| run | rev | status/stop | judge | tools used/offered | evidence parent+branch/bound | input tok / llm | tool msg chars / resent (largest) | repair | episode s / sub_research s / ledger left | branches ok/partial/fail · accepted · invalid · cap rej/req | branch→parent s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| run_20260907_161318_091726（候选口） | 7980be360c5b | partial / model_finish | repaired (unavail 0, degraded 0) | 9/14 (父 6 · 支 7) | 178+129/32 | 517243 / 5 | 93608 / 287515 (sub_research 61754) | 0 | 228.5 / 109.0 / 311.7 | 0/3/0 · 3 · 0 · 2/31 | 0.0 |
| run_20260907_161748_970275（候选口） | 7980be360c5b | completed / model_finish | repaired (unavail 0, degraded 0) | 11/14 (父 5 · 支 8) | 207+133/25 | 699776 / 5 | 104451 / 283489 (sub_research 56939) | 0 | 245.2 / 130.2 / 295.0 | 1/2/0 · 3 · 0 · 0/28 | 0.0 |
| run_20260907_164332_208527（8792） | b594a5e7f8ae | completed / repair_model_finish | repaired (unavail 0, degraded 0) | 12/14 (父 6 · 支 8) | 206+132/36 | 974147 / 10 | 97936 / 680884 (sub_research 55285) | 1 | 416.8 / 131.0 / 163.4 | 1/2/0 · 3 · 0 · 1/30 | 0.0 |

## 13. 历史压实两刀已实施（#635 lean、#636 折叠，缺省关，main `e1d22b89`）；候选口 A/B n=3

spec `2026-09-07-episode-history-compaction-design.md` §3.1 / §3.2 两刀都进了 main，**两个 env 缺省关**，8792 行为不变（未切）。
候选口 8799 从 `4042110d` 起，`ASK_EPISODE_LEAN_OBSERVATION=on ASK_EPISODE_HISTORY_COMPACTION=on KEEP_BATCHES=2`（臂 C），同题三遍；
臂 A 用同一代码线、开关关的三遍（`161318` / `161748` / `164332`，§11–§12）：

| 臂 | run | 轮数 | input tokens | 每次调用 | 重发（模型所见） | 重发（若不折） | 折叠省 | 绑定 hash | 判官 |
|---|---|---|---|---|---|---|---|---|---|
| A | 161318 | 5 | 517,243 | 103K | 287,515 | — | — | 32 | repaired |
| A | 161748 | 5 | 699,776 | 140K | 283,489 | — | — | 25 | repaired |
| A | 164332 | 10 | 974,147 | 97K | 680,884 | — | — | 36 | repaired |
| C | 180047 | 16 | 987,813 | **62K** | 460,049 | 1,070,024 | **−57%** | 45 | repaired |
| C | 180733 | 5 | 768,338 | 154K | 206,097 | 296,305 | −30% | 16 | repaired |
| C | 181219 | 10 | 782,898 | **78K** | 303,841 | 653,825 | **−54%** | 13 | passed |

读法：
- **成本轴成立，且随轮数放大**：16 轮那遍重发量 −57%、每次调用 62K tokens（基线 10–19 轮 ≈ 97–100K）；10 轮对 10 轮：每次调用 78K vs 97K（−20%），
  重发 −54%。5 轮那遍折得少（K=2 只有第 4、5 轮看到存根），且它拉了最多证据（195+143），每次调用反而 154K——每次调用的 tokens 里工具历史只是一部分。
  「重发（模型所见）」这列还没算 lean 的 −21%（frontier 按标准投影从底稿重算），真实值更低。
- **出口不退**：三遍判官 repaired / repaired / passed，`judge_unavailable_count=0`、`content_degraded_count=0`，分支收尾 9/9 被接受。
- **绑定数判不出**：C 45 / 16 / 13 对 A 32 / 25 / 36，均值低但区间重叠，n=3 下不能说退化也不能说没退化——spec §6.3 的判据是
  「绑定数或判官任一退化即不翻缺省」，所以**缺省仍关**。臂 B（只开 lean）没跑。
- 第 1 遍 16 轮：父臂 `[1,1,…]` 单工具轮又出现，与 §12 一致——折叠正是为这种形状省的，这一遍省了 61 万字。

决定：两刀合入、缺省关（零生产影响）；翻缺省前补：臂 A / C 各再 3 遍 + 一道公司题（长电 vs 通富），用 `eval_variance_baseline.py`
出绑定数的翻转率基线再判。lean 单独翻缺省的风险极低（只去空值与校验器专用键），可先翻——待拍。

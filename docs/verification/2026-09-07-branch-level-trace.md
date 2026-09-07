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

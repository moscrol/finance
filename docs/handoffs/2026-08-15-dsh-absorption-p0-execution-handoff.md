# 交接：dsh 吸收 P0 接缝实施（第 4 步进行中）

日期：2026-08-15
交接人：上一任执行方（上下文耗尽）+ 检阅方（本文由检阅方整理）
接收人：新执行方 agent
状态：第 1-3 步完成并通过复验；第 4 步完成 1/2；有一个打回项待修

---

## 0. 你的角色与工作循环

你是**执行方**。循环是：你实施一轮 → 提交 → 写轮次小结（提交 hash、做了什么、
边界怎么画的、计数证据、门禁状态）→ 检阅方**独立复跑你的每一条声明**并裁定
PASS / 打回。

三条对你最重要的经验教训（都是本项目里真实付过学费的）：

1. **只断言你实测过的**。收据里区分 [实测]/[推断]。上一任曾把一个恒真式审计的
   "12/12 一致"当通过报告——自己造的判据自己验收，被检阅方抓出来打回。
2. **动手前先搜仓里已有的机制**。resume 不变量、lineage、episode_id 约定都已存在，
   重建就是造第二事实源。上一任还编过一个不存在的 `query_ledger.reset()`，
   8 个用例直接 error——真机制是 `query_ledger_scope()`。
3. **测试必须经真实入口断言行为**。禁止两种假测试：spy 只验自己刚写的透传行、
   `inspect.getsource` 抓源码子串。这两种都在本项目里出现过并被打回
   （后者的一条断言今天就被注释里的字面串满足着）。docstring 不得声称测试
   没做的事。

## 1. 项目一句话

按 spec 把 dsh（DeepSeek Harness）的六个边界模式吸收进 Finance Python Runtime
（不迁移代码），当前在 §11 实施顺序的第 4 步。领域门禁（Evidence Ledger、
截止日、语义验证）始终由本仓拥有，任何吸收不得绕过。

## 2. 位置与版本（全部核实过）

| 对象 | 位置 / 值 |
|---|---|
| 实施工作树 | `/Users/a77/fwp-wt-dsh-seams`，分支 `feat/dsh-absorption-p0-seams`（tip 见文末 rebase 轮小结） |
| 分叉基线 | **已 rebase 到 `gitea/main` = `cf86e891`，merge-base 即 `cf86e891`，分叉 = 0**（2026-08-15 rebase 轮；旧值 merge-base `23e2a07e` / main `bcde2851` 已作废）。**这一格会漂，引用前照 §2.1 重测** |
| Spec | `docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md`，在主检出树 `/Users/a77/finance-workspace-private` 的 `docs/dsh-absorption-spec` 分支 @ `d98a8a59` |
| Step 1 基线收据 | `docs/superpowers/specs/2026-08-15-dsh-absorption-step1-baseline-receipt.md`（实施分支上；§6 是三条已裁定问题，§7 是备查项） |
| dsh 源码快照 | `/Users/a77/finance-workspace-private/tmp/dsh-source-index`，钉在 `47f9438`，sparse cone 含 `packages/llm` |
| 零件回写 | `~/harness-reference/BUILD.md`（工具可达性审计、阶段事件加法两节） |
| 两个分支 | 均**未 push、未合 main**。红线：不得 push、不得合 main、不得动生产快照树 |
| 本文档 | 已随 `f69a8b96` 入库（早先「未提交」的口径已作废） |

### 2.1 分叉盖戳（2026-08-15 rebase 轮重做，附测量命令）

**分叉已归零**：本分支已 rebase 到 `gitea/main` = `cf86e891`。下面每个数字后面
就是产出它的命令，重测请照抄（口径不同数字就不同，这是前几轮反复被点名的地方）。

```bash
cd /Users/a77/fwp-wt-dsh-seams
git rev-parse gitea/main                  # cf86e891（远程跟踪 ref，本轮未 fetch）
git merge-base HEAD gitea/main            # cf86e891 ← 等于 main 本身 = 已线性叠在上面
git rev-list --count gitea/main..HEAD     # 14（本分支提交数，rebase 前后相同）
git rev-list --count HEAD..gitea/main     # 0（main 上没有本分支不含的提交）
git diff --shortstat HEAD...gitea/main    # 空（分叉为 0）
```

- **rebase 结果：14/14 干净重放，零冲突**（[实测]，`git -c rerere.enabled=true
  rebase gitea/main`）。等价性用 range-diff 逐提交核过，全部标 `=`：
  ```bash
  git range-diff 23e2a07e..prerebase/dsh-seams-e21c50bf cf86e891..HEAD
  ```
  安全 ref **`prerebase/dsh-seams-e21c50bf`** 保留着 rebase 前的 tip，随时可对照
  （确认无误后由用户决定何时删）。
- **「真冲突面 37 hunk」的预判为什么没兑现**：hunk 数衡量的是**改动量**，冲突取决于
  **改动区是否相交**。main 的两个 `agent_episode.py` 提交（`1f8cdc24` tool_exception
  detail、`2e50e263` 终局绑定改证据序号）落在 finalization 区，本分支的两个
  （EpisodeScope 构造、RuntimeHandle 接线）落在 `run()` 入口与会话装配区，三方
  合并算法自动分开了。**教训：预估 rebase 成本要看改动区重叠，不是 hunk 计数**——
  但预判偏保守没有代价，反过来会有。
- **`gitea/main` 是跨工作树共享的 ref**（同一个 `.git`），两棵树读到的值必然一致；
  `git reflog show gitea/main` 能看到历次落点。拿旧 reflog 位置量出来的数字和拿
  @{0} 量的对不上，是**快照不同**，不是谁算错——这也是本节每个数字都带 ref 值的原因。
- **行号会随 rebase 漂**：main 在 `agent_episode.py` 里加了行，本次 rebase 后
  `run()` 起点 +46、`_run_sub_research` 区 +76。§4.1 / §5.3 引用的坐标已随本轮重测；
  **下一次 rebase 之后同样要重测，别照抄**。

## 3. 提交史（实施分支，全部通过复验）

```
4b23a516 Episode 入口构造 EpisodeScope，机制解除休眠（第 4 步 1/2）
d69ee387 工具可达性审计接入 pre-commit + pytest 侧复挂
d35f32a2 第 3 步打回项修复（审计恒真式、区分事件不可达、sink 故障改写主路径）
96e74d43 工具阶段事件与可达性登记接线（第 3 步）
13f26bf8 检阅意见收口（窄化异常捕获 + trace context）
0c97c41a EpisodeScope 与 ToolPipeline 接缝（第 2 步，不改变现有行为）
b920feb6 Step 1 基线复核收据
```

当前全量基线：**4955 passed / 4 skipped / 0 failed**（@ `4b23a516`，umask 022）。

## 4. 机制现状（读代码前先看这段）

- `EpisodeScope`（`intelligence/services/episode_scope.py`）：一次 Episode 的能力
  边界单一入口。派生 allowed_tools / model_visible_names / authorize /
  reachability 四段状态（定义→授权→可见→调用）/ dump() 收据。
  `emit()` 只吞 Exception 不吞 BaseException，sink 故障计入 dump 的
  `event_sink_failures`。
- **构造点**：`ContinuousAgentEpisode.run()`（`agent_episode.py` ~L498），
  `episode_id = context.contract.task_id`（仓内既有约定），经
  `new_session(scope=)` 传入批次会话。scope 是 per-run 的，executor 是长生命周期的。
- **两处有意留空**：`user_id=""`（memory 身份是装配期输入，运行器不该拿）；
  `event_sink=None`（本运行器已有形状不同的事件出口 `Callable[[EpisodeEvent], None]`
  走 `_EpisodeLedger`，合流是第 5 步的事，现在搭桥会造第二条事件链路）。
- **阶段事件**：`TOOL_PRE_EXECUTE / TOOL_RESULT / TOOL_ERROR` 定义在
  `research_tool_registry.py`（发射点、下层），`episode_scope` 转出。
  `registry.execute` 带 scope 时发事件、在 fetch 闭包内登记调用
  （被去重/预算挡掉的不记——这是收据不说谎的关键）；批次预筛的
  `unknown_or_unauthorized_tool` 分支也发区分事件（wire 上的压扁串一字未动，
  那是有 4 生产者 1 消费者且进模型可见文本的错误契约，拆它要单独一轮）。
- **可达性审计**：`scripts/audit_tool_reachability.py`，判据取自真实装配函数
  `build_episode_registry`（不是声明自己）。三分：无条件装配 11 / 条件装配 1
  （memory_lookup，需 memory_user，报告不失败）/ 够不着 0（失败）。
  已入 pre-commit（entry 用主树 venv 绝对路径，宿主 python3 跑不了它）+
  pytest 侧复挂（`test_tool_reachability_audit.py`）。

### 4.1 子研究后台分支：排空泄漏**结构上不成立**（spec §4.2.4 的排空档）

> 本节替代早先"子研究后台分支排空是缺口、要单独开一轮"的记法。裁定原文见文末
> 「检阅裁定 · 子研究轮形状」；**不采纳的备选**（父 Handle 上 `begin_work`）已进
> §6 第 4 条，不要重开。**剩余的只有收据对账，归第 5 步**，要求写在 §5.3。

**坐标口径**：行号 = **rebase 到 `cf86e891` 之后重测值**（2026-08-15 rebase 轮）。
`agent_episode.py` 因 main 加行整体下移（`run()` 区 +46、`_run_sub_research` 区 +76），
本节与 §5.3 已按新值改过；`sub_research.py` main 没碰，只有本仓 docstring 造成的位移。
**下次 rebase 后必须重测**，别照抄。符号名以 **`_run_sub_research`** 为准——早先小结里
的 `_maybe_sub_research` 是笔误，全仓 grep 零命中，不得再进台账。

**四条证据并列**（归属逐条标注）：

1. **同步包含**（执行方 [实测·读码]，检阅方复核并加强一档）：`coordinator.run` 的
   唯一调用点是 `agent_episode.py:1795`，在 `_run_sub_research`（def `:1771`）内；
   `_run_sub_research` 的两个调用点 `:886` / `:924` 都落在 `run()` 体内（`run` 起
   `:544`，下一个 def `_repair_model_complete` 在 `:1177`）。**`resume`（`:1295`–
   `:1687`）无调用点**——子研究只发生在 initial_run 工作窗口，包含性比"都在 run
   里"再强一档。
2. **"已返回"即"已终结"**（执行方本轮读码补强，比"with 即 join"硬一档）：
   `sub_research.py:340` 的 `with ThreadPoolExecutor` 在 `__exit__` join 只是第二道
   保险；**第一道**是 `:352` 的 `as_completed(futures)` 遍历全部已提交 future，
   而 `:369-370` 的返回值对**每个** request 取 `results[request.branch_id]`——少一个
   分支就 KeyError。即"返回"这个事件本身蕴含"所有分支已终态"，不依赖清理路径。
3. **per-branch 收据已经在**（执行方 [实测·读码]，检阅方复核字段多于小结所列；
   本轮补出第三段）：`_EpisodeLedger` 三段式发射——`branch_started` 每目标一条
   （`agent_episode.py:1790-1794`）→ 结果循环发 `branch_completed`/`branch_failed`
   （`:1805-1822`）→ **未执行兜底循环**（`:1823-1834`）给没回来的 branch_id 补
   `branch_failed`（`reason = refused_reason or "branch_not_executed"`）。所以整轮
   refused 路径（`cancelled` / `deep_mode_required` / `root_budget_*` /
   `deadline_exhausted`）也成对。**成对性的上游前提**：`goals` 只来自
   `ResearchPlan.branch_goals`，而 `ResearchPlan.__post_init__`（`research_plan.py:78-82`
   → `_bounded_branch_goals:137-148`）已强制"非空、去重、≤3"，所以协调器里的
   `_clean_goals` 在这条调用链上抛不出异常——否则 `branch_started` 发完就异常逃逸，
   会留下无终态事件。同一前提还保证 `_clean_goals` 的去重不会重排 `branch-{i}`
   编号：一旦上游放开重复目标，`branch_started` 的编号（按原始列表）与协调器返回的
   编号（按去重后列表）会错位，成对性还在、**goal 与 branch_id 的绑定会串**。
4. **取消语义已按 §7.3 实现且与 Handle 同源**（**检阅方**提供 [实测·读码]，执行方
   本轮逐条复核成立）：`sub_research.py:263` 持上游 `is_cancelled`；
   `glm_agent_runtime.py:416-417` 的注释钉明 RuntimeHandle 折叠的就是同一个
   callable，`:418` 的 `self._upstream_cancelled = is_cancelled` 与 `:407`/`:414`/
   `:423` 注入 client / coordinator / episode 的是**同一个实参**，`:481` 又把它递给
   `RuntimeHandle(upstream_cancelled=...)`；`:305-306` run()
   入口整体早退 `refused_reason="cancelled"`；`:407` 把同一 callable 递进每个
   `BranchRequest`；`_run_one`（`:410`）的 `:411-422` 在每个分支启动前各查一次
   （未启动 → `status="failed"` + `error="cancelled"`；已启动的不打断，由证据 2
   那条同步消费排空）。

**承重不变量（谁破谁重开 §4.2.4）**：`SubResearchCoordinator.run()` **保持同步**。
谁把它改成 async / fire-and-forget（提前返回 future、executor 提到实例或模块级、
`shutdown(wait=False)` 后不消费、分支挪进后台队列），谁就必须重开 §4.2.4 的排空档
并在 RuntimeHandle 上补分支粒度 drain——**上面四条证据届时全部作废**。代码侧认领已
写进 `SubResearchCoordinator.run` 的 docstring（§9 要求的"docstring + 台账"两处）。

⚠️ **别把上面四条当门禁继承——它们一条都没有测试钉住。**

- 两处取消守卫（[实测·变异]）：抽掉 `:305-306` 入口早退与 `:411-422` 分支守卫后跑
  全量，**4982 passed / 4 skipped / 0 红**（597.4s；`git checkout` 恢复后树干净）。
- 同步性（[推断] + [实测·grep]）：连变异都构造不出来——要造出泄漏就得先改掉"消费完
  全部 future 才构造返回值"这个结构，那时红的会是结果缺失类断言，不是泄漏断言。仓内
  唯一的线程存活断言在 `test_sub_research.py:441`，测的是 `_BranchBudgetView` 并发
  结算的辅助线程，与协调器排空无关。

**所以这一档现在是"设计约束 + docstring + 台账"三处认领，不是门禁**；第 5 步做收据
对账时一并把它变成可执行判据。

**本轮 rebase 负担 = 0**（[实测]，命令如下）：main 至 `cf86e891` 未碰
`sub_research.py` / `glm_agent_runtime.py` / `runtime_handle.py` / `research_plan.py`；
docstring 只落在 `sub_research.py`，**刻意不碰 `agent_episode.py`**（唯一真冲突面）
——那里的同款认领**写死认领给第 5 步落笔**（它本来就要改这个文件）。

```bash
cd /Users/a77/fwp-wt-dsh-seams
git rev-parse gitea/main    # cf86e891（本轮未 fetch，值与检阅方裁定时同）
git diff --name-only $(git merge-base HEAD gitea/main)..gitea/main \
  -- intelligence/runtime/sub_research.py intelligence/runtime/glm_agent_runtime.py \
     intelligence/services/runtime_handle.py intelligence/services/research_plan.py
# 空输出 = 未碰
```

## 5. 马上要做的（按优先序）

> **状态盖戳（2026-08-15 台账改写轮）**：5.0 / 5.1 / 5.2 三项均已在此前轮次交付并
> 经检阅方判定 PASS（判定原文见文末轮次记录；本轮未独立复跑，只做指针）。本节保留
> 为历史依据与设计出处。**当前在途只剩两项**：rebase 轮（待用户批准）与 §5.3 的
> 第 5 步。5.1 里那条「子研究后台分支排空」已另有裁定，见 §4.1。

### 5.0 打回项（先修，很小）

`test_agent_episode_run_constructs_scope`（`test_tool_stage_events.py` 末尾）
是 `inspect.getsource` 子串匹配，不是行为测试：docstring 声称"必须真的调 run()"
但从未调用；断言 `context.contract.task_id` 被 run() 里注释的字面串满足；
抽 helper 会假报警。**修法**：用既有 agent_episode 测试的 fake 基建驱动最小
run()，monkeypatch `ToolBatchExecutor.new_session` 捕获 scope 实参，断言
`captured.episode_id == contract.task_id` 且 `captured.registry is registry`。
spy 不是错，错在不经过真入口。

### 5.1 RuntimeHandle（第 4 步剩余主体，spec §7.3）

六态：`created → started → running → cancel_requested → draining → closed`。
要求：close() 幂等；close 后不得发布新 Agent/Tool/Event；cancel 只挡未派发的
工作、排空已启动的只读工作；子研究携带 parent/branch lineage；resume 保持
task frame hash / Episode ID / 事件前缀不变。

**不用重建的（已核实存在，复用）**：
- resume 不变量：`episode_session.py:68-82`（含"必须产生新 model_turn"共五条）
- lineage：`runtime/sub_research.py:366` 的 `f"{task_id}:{branch_id}"`
- episode_id 约定：`context.contract.task_id`（glm_agent_runtime.py:481 等）

**必须钉死的设计点（检阅方指定）**：Scope 生命周期 = 单次 run 还是整个
Episode（含 repair resume）？若 resume 重进 run() 新建 Scope，invoked_tools
和事件收据会按修复周期碎片化——Handle 持有 Scope 还是每次 run 派生子 Scope、
收据怎么归并，状态机设计时一并定，不留给第 5 步猜。

验收（spec §7.3）：取消、超时、Provider 失败、进程重启四类场景都有事件收据；
无 orphan tool call、未结算 budget、close 后事件。

### 5.2 认领项 2：装配调用点的身份断言

"给了 memory 身份则 memory_lookup 必须装配出来"。落点在 `build_episode_registry`
的调用点（身份只在装配层出现），不在 Episode 入口。闭环审计三分法里
"条件装配"档的残留风险（生产忘传身份 → 静默永不装配）。

### 5.3 之后的步骤（spec §11）

- 第 5 步：EpisodeEvent 分 Durable/Live + 统一 Projection。**含事件出口合流**：
  现有 `_EpisodeLedger` 出口与 EventSink 合成一个，消灭"第二条事件链路"的暂留状态。
  届时按 §7.1 验收对账"每次工具调用都有完整阶段事件"——预筛的去重/预算/取消
  rejected 分支目前不发事件，是已知缺口，到这步补。

  **子研究收据对账要求**（2026-08-15 由子研究轮并入，依据见 §4.1；本项不做完，
  §4.2.4 不算收尾）：

  1. **成对**：每条 `branch_started` 必须对上一条 `branch_completed` 或
     `branch_failed`。现状已成立，靠 `_run_sub_research` 末尾的未执行兜底循环
     （`agent_episode.py:1823-1834`）兜住全部 refused 路径——**Projection 必须把它
     变成断言，不能当巧合继承**：那个循环一旦在合流改写里丢掉，成对性静默失效。
  2. **cancelled 可区分：现状只成立一半**（[实测·读码]，本轮新查）。整轮拒绝
     （`refused_reason="cancelled"`）走兜底循环、payload 带 `reason`，可区分；
     **单分支取消不可区分**——`BranchResult.error="cancelled"` 没有任何事件字段
     承载它，结果循环的 payload（`agent_episode.py:1811-1821`）只有
     branch_id/goal/status/evidence_count/gap_count/llm_calls/tool_calls/tokens，
     与 worker 异常失败（`error="branch_worker_exception:*"`，同为 status=failed、
     gap_count=1）在事件流里**同形**。第 5 步必须把 `error` 或等价字段带进事件，
     否则这条对账要求在 Projection 上根本判不出来。
  3. **Durable/Live 归属未定**：`branch_started` / `branch_completed` /
     `branch_failed` / `branch_tool` 四种事件在 spec §7.4 的两份名单里都没出现。
     第 5 步要给它们定归属——它们承载证据来源与分支预算消耗，按 §7.4 的金融约束
     （evidence hash/source/status/gaps 不得在 Projection 丢失）倾向 Durable，但这是
     第 5 步的裁定项，本轮不替它定。
- 第 6 步：ResearchProfile + effective-config 收据。**必须吸收**
  `research_policy.py:10` 已有的 `GroundedBudgetProfile`，不另起第二配置源。
- 第 7-8 步：scripted dsh stub 验证 Adapter 协议 → A/B。跑之前读 Step 1 收据
  §3.2（benchmark 交接命令指向死网关+退役模型，不能照抄）和 §6（三条裁定）。

## 6. 已裁定的问题（不要重开）

见 Step 1 收据 §6，摘要：

1. **A/B 样本量**：先用冻结九题×5 重复跑纯 Arm A 校准 σ_d；题集扩到 30 题
   （quick/deep/daily-review 分层，九题作子集）；每臂每题 3 重复（地板 2）；
   判定用同题配对差值 bootstrap 95% CI 上界；压不住 5pp 就加题/加重复，
   不许放宽门槛。冻结九题在
   `/Users/a77/.finance-runtime/evals/frozen-nine-2026-07-25.questions.json`。
2. **dsh 凭证注入**：走 `apiKeyEnv` + 专用变量名 `DSH_AB_RELAY_KEY`（不复用
   `OPENAI_API_KEY`，防 ambient discovery 误拾）；只注入 dsh 子进程；artifact
   只记指纹。`ctx.credentials` host 插件记为 P2。
3. **pre-commit 接审计**：已裁定接、已落地（d69ee387）。
4. **子研究分支不绑父 Handle**（2026-08-15 检阅裁定，见文末）：不在父 Handle 上开
   `begin_work("branch:{id}")`——它与 `_EpisodeLedger` 的 branch 事件构成双账（违反
   「不造第二事实源」），且要把 Handle 穿 runtime→episode→coordinator 三层；换来的
   分支粒度 drain 在第 5 步 Projection 对账里免费得到。**排空泄漏这一档已判定结构上
   不成立**，四条证据、承重不变量与剩余对账项见 §4.1。

## 7. 验证纪律（每轮收尾必跑，检阅方会独立复跑）

```bash
cd /Users/a77/fwp-wt-dsh-seams
umask 022   # 关键：harness shell 默认 077，ceiling fixture 三个测试文件 mode 审计必挂
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python   # venv 只在主树
$PY -c "import intelligence,os;print('LOADED:', os.path.dirname(intelligence.__file__))"
# ↑ 必须打印工作树路径。venv 无 .pth，import 由 cwd 决定
$PY -m pytest -q -p no:cacheprovider > /tmp/x.log 2>&1; echo "PYTEST_EXIT=$?"
# ↑ 不接管道：cmd | tail 的退出码是 tail 的，曾靠这条看见 exit 127
tail -1 /tmp/x.log
$PY scripts/layer_audit.py            # services 不得 import runtime，ERROR 0
$PY scripts/audit_tool_reachability.py  # 12 声明/11 无条件/1 条件/0 够不着
$PY -m ruff check intelligence scripts
```

行为中性声明的格式：基线 N passed → 改后 N+k，k 恰为新增用例数，存量零改动。
轮次小结必含：提交 hash、边界决定及理由、计数、门禁状态、分支状态（未 push/未合）。

## 8. 已知环境坑（都踩过）

- harness shell umask=077 → ceiling fixture 16 个测试假失败；先 `umask 022`。
- `.venv-workbench` 只在主树，工作树里直接跑会 exit 127。
- pytest 接管道会吞退出码。
- 4 个 skipped 依赖知识库仓 RAG venv 可用性，属正常。
- pre-commit 的 tool-reachability hook 用 venv 绝对路径，新机器会挂（预期，见 yaml 注释）。
- 改 `episode_tool_batch.py` 预筛区前先看 `unknown_or_unauthorized_tool` 的
  生产者/消费者清单（96e74d43 的提交说明）——错误契约不许顺手改。

## 9. 边界纪律（本项目的元规则）

- 每轮只做一步，体量大的单独开轮；"顺手把它改对"是范围失控最常见的入口。
- 有意不做的事必须**写死认领**（模块 docstring + 台账），否则第 4、5、6 步
  互相以为对方会接，而机制休眠时所有测试都是绿的。
- 错误契约、事件名、收据字段都是对外承诺，动之前量爆炸半径。
- 检阅方复跑一切：你的声明与实测不符会被逐字指出，自己发现自己报比被抓到好。

---

## 轮次记录

### 执行方小结 · Round「5.2 装配调用点身份断言」（2026-08-15，执行方）

正文以提交 `23072aa3` 的提交说明为准（与聊天交付的轮次小结同文）；另附一项
分叉裁定请求（本文档 §2 的 gitea/main 事实已漂移）与一件附带成果
（`~/.claude/projects/-Users-a77/memory/cursor-cli-session-forensics.md`）。

### 检阅批注 · Round「5.2 装配调用点身份断言」（2026-08-15，检阅方）

- **判定**：PASS
- 独立复核（全部亲手复跑/读码，标注出处）：
  - 提交/分支：`23072aa3` = 2 文件 +251/−8；`git ls-remote gitea` 无 dsh/seams
    分支；工作树干净 [复跑]
  - 门禁：全量 **4979 passed / 4 skipped / 0 failed**（438.9s，LOADED=工作树
    路径）；layer_audit ERROR 0（扫 243 模块）；可达性 12 声明/11 无条件/1 条件
    /0 够不着且 ⓘ 注记仍在；ruff 全绿；pre-commit 整体 RC=0（9 hook Passed +
    block-forbidden-files 无命中 Skipped）[全部复跑]
  - 非恒真式主张：`episode_tools.py:980` 实测判据为
    `str(memory_user or "").strip() != "" or memory_users_root is not None`；
    本调用点不传 `memory_users_root`，判据退化为 strip 口径，「空白身份落入
    守卫侧」成立 [读码]
  - 变异抽样（编辑-复跑-`git checkout` 恢复，已验终态干净）：调用点回退裸
    `build_episode_registry` → 恰 2 条红（binds + refuses，即历史生产形状被
    钉住）；抽掉守卫本体 → 恰 1 条红（refuses）[复跑]。授权前置、无身份早退
    两个变异**未抽查**
  - 写死认领点名的两条生产测试存在（`:477`、`:952`）且均断言
    `memory_user == run_store.user_id` [读码]
  - 存量零改动：本提交测试改动为纯新增（+189 无删改）；4979 − 4 = 4975 与
    自报基线算术一致；4975 @ `06851cc7` **未独立复跑**
- 标注（不影响判定）：
  1. **分叉数字 45/+10778−129 的 [实测] 不可复现**：gitea/main 全部 fetch
     快照与首父历史逐点测量，唯一 45 文件点是 `f248613e`（13:42 拉取）=
     +11384/−94；`-C`/`-M`/`--no-renames`/numstat/intelligence 限定等口径均
     不产出 +10778。拓扑主张全部复现成立（分叉点 `23e2a07e`、重叠恰 4 文件、
     app.py 主侧仅 1 hunk 在 create_app:1886 与装配段不相交、agent_episode.py
     主侧 U0 口径 37 hunk vs 分支 4）。**今后 [实测] 数字必须附测量命令。**
  2. 检阅方重测（`bcde2851`，检阅时 fetch）：分叉已达 **76 文件 /
     +14544/−138**，intelligence/ 内仍 38 文件——main 半日 fast-forward 5 次，
     是移动目标。
  3. docstring 引用装配层判据不完整：实际含 `or memory_users_root is not None`
     析取支（本调用点恒惰性，主张成立）；但将来若有人在该调用点传
     `memory_users_root`，空白身份会静默注册而非炸。下轮把引用写全。
  4. 新用例 docstring 的 `test_workbench_api.py:816` 是本提交插入 189 行之前
     的行号，现为 `:1005`；docstring 引用符号名，不要引用行号。
  5. 本交接文档已随 `f69a8b96` 入库，「未提交」口径已过时（非执行方过失）。
  6. 附带成果核验 PASS：cursor-cli-session-forensics 记忆的 hex-JSON meta /
     `latestRootBlobId` / 34 字节记录（tag `0x0a|0x1a` + `0x20` + 32B id）/
     0x2a 中断 caveat 均在真实 store.db 上复现（样本 4 条合规记录后 0x2a
     截断，len%34=2）。一条勘误：样本 meta.json 无 `title` 字段，会话名在
     store.db meta 的 JSON `name` 字段。
- Round N+1 指派（依赖排序）：
  1. 本文档 §2 重新盖戳：main 现值、分叉量（**附测量命令**）、删除「增量纯
     docs 无需 rebase」与「未提交」两句（事实漂移，非执行方过失）；
  2. 第 4 步收尾轮：openai_agents / codex_headless / headless_tool_gateway
     会话与子研究 per-branch Handle 接线（执行方自报，确认）；同轮显式认领
     标注 3、4 的两处 docstring 精修（写进小结，不算「顺手改」）；
  3. rebase onto gitea/main：**暂缓至用户裁定**（见下），批准后独立开轮，
     按 resolving-merge-conflicts 纪律逐 hunk 解。
- 升格用户事项：**rebase 时机**。建议收尾轮之后、第 5 步之前单独开轮——
  main 移动中，现在 rebase 大概率要 rebase 第二次；真冲突面只在
  `agent_episode.py`（主 27+ hunk vs 本分支 4），app.py 无语义冲突已核。
  若要求先合，接受可能两次 rebase。

### 执行方回执 · 对标注 1/2 的复测（2026-08-15，执行方）

- **标注 1 成立，纪律照收**：45 / +10778 / −129 已按 §2.1 的命令原样复现——它是
  **路径限定**（`-- intelligence scripts market_feature_store`）的数字。上轮小结
  里我把它写成「gitea/main 已改 45 文件」，同一句又给了含 `docs/` 的 76 文件分布，
  两个口径混在一句话里。数字没错，报告错了；**[实测] 数字必须附测量命令**已写进
  §2.1 的体例。
- **标注 2 需要更正（决策相关，故点出）**：`gitea/main` 是跨工作树共享 ref，我测量
  时它**已经是 `bcde2851`**（reflog @{0}，最后一次 fetch 08-15 14:26，早于本轮全部
  测量——本轮测试收据时间戳 `20260815T095641Z` = 本地 17:56）。检阅方复测的
  76 / +14544 / −138 与我同一 ref 的全量口径逐字节一致；`f248613e` 是同一 ref 的
  @{5}，更早的 fetch 落点。**main 在本轮窗口内没有移动。**
  - 影响：「main 是移动目标」的依据是历史频次（reflog 上半日 5 次 fast-forward），
    不是本轮观测到的移动。暂缓结论不因此翻转，但推荐理由建议换成下面两条更硬的。
- **执行方对 rebase 时机的建议（裁定权仍在用户）**：同意暂缓到收尾轮之后。理由：
  1. 真冲突面只有 `agent_episode.py`，而收尾轮恰要在它附近接线——先接完再解一次，
     比解两次便宜；
  2. **更硬的一条**：rebase 会作废刚被复核的 4979 基线。基线重建必须独立成轮，否则
     下一轮的「存量零改动、差值恰为新增用例数」这个判据直接失效——rebase 带进来的
     用例变动和本轮新增混在一个差值里，谁也分不开。这正是本项目验证纪律的核心判据，
     不能让它在功能轮里失去分辨力。

### 执行方小结 · Round「第 4 步收尾轮」（2026-08-15，执行方）

正文以提交 `639bad78` 的提交说明为准（含过程事故自报：cwd 漂移致 `cat >>` 误写
主检出树同名测试文件，已按「先 diff 确认改动面、按行数截回、status 复验」处置；
教训入 `read-workspace-before-acting.md`）。前置提交 `bf991c69` 落实上轮指派 1/3
（§2.1 盖戳附命令）并附对检阅标注 1/2 的回执（见上节）。

### 检阅批注 · Round「第 4 步收尾轮」（2026-08-15，检阅方）

- **判定**：PASS
- 对执行方回执的回应：
  - 标注 1 关闭方式收讫：45/+10778/−129 在钉住快照上按 §2.1 命令逐字节复现
    （`git diff --stat 23e2a07e..bcde2851 -- intelligence scripts market_feature_store`）
    [复跑]。定性从「数字不可复现」更正为「数字真实、口径未申报」，体例已制度化。
  - **标注 2 的更正成立，检阅方收回**「main 在执行方实测后移动」的表述：reflog
    窗口 `bcde2851`@14:22 → `cf86e891`@18:50，执行方全部测量（≤18:08 提交）落在
    窗口内，main 其间未动；上轮 76 vs 45 之差全部来自路径口径。检阅方上轮标注 2
    不再作为任何结论的依据。
- 独立复核（逐条出处）：
  - spec 引用逐条对文：§9.1 Arm C=已有 sdk_gpt（表格标「可选」）、§9.3 含
    cancel/resume/restart 成功率与对账完整率、§8.2 窄协议清单含 episode scope、
    §4.2 第 4 条原文一字不差、§7.3 验收含「Headless Gateway 覆盖」、§11 第 7 步
    stub 先行——**无断章取义**，三处判断改动的 spec 依据全部属实 [读 spec 本体
    @ d98a8a59]
  - 提交/分支：`639bad78` = 5 文件 +237/−16；两个新提交后分支仍未 push；树干净 [复跑]
  - 门禁：全量 **4982 passed / 4 skipped / 0 failed**（739.7s，并行复核拖慢属
    检阅方环境）＝上轮亲验基线 4979 + 恰 3 条新增；layer_audit ERROR 0
    @639bad78；可达性 12 工具通过；ruff 全绿；pre-commit RC=0 [全部复跑]
  - 变异复核（两个都跑了，非抽样）：不把 handle 交给 session → 恰 3 条全红；
    抽掉 `mark_running` → 恰 1 条红（state==running）[复跑，checkout 恢复，
    终态树干净]
  - 台账三处认领的代码事实：codex 仅 `run()`（:587，无 start/resume）+ 工厂
    `benchmark_only`（:70/:186）+ 环境闸（:170）；网关 `__init__` 无 scope 参数
    （:166-175，§8.2 缺口属实）；`SubResearchCoordinator` 构造点
    `glm_agent_runtime.py:409`、lineage `sub_research.py:366` [读码]
  - 同形主张：GLM 侧 :484-505 与 openai 侧序列逐行同构（mark_started →
    begin_work("initial_run", allow_during_cancel=True) → end_work →
    mark_running）[读码]
  - `scope_attached=False` 如实收据：代码与用例双核，未造第二 Scope 构造点 [读码]
  - 事故清理：主检出树该测试文件不在脏列表（与 HEAD 一致）；生产快照树
    `cb09f895` status 干净（红线未破）；主树 `lessons_learned.md` 脏改动属年报
    入库轨道，与本执行方无关；教训记忆 18:59 落盘且含处置纪律 [取证]
  - 上轮指派 3/3：盖戳（bf991c69）、docstring 两处修复（639bad78 内，含
    「谁传 memory_users_root 谁一并改守卫」警示与 :816 教训自注）、rebase 未动 [复跑/读码]
- 标注（不影响判定）：
  1. §2.1 括注「差额 30 个是 docs/」应为 31（76−45）。一字级。
  2. main 已于 18:50 前移至 `cf86e891`（本轮窗口之外）：热点重叠新增
     `test_agent_episode.py`；分叉表引用前照 §2.1 警告重测。
- Round N+2 指派（依赖排序）：
  1. **子研究后台分支排空轮**（spec §4.2.4 收尾）。开工先把设计点钉进台账再写码：
     父 Handle 是否递入 `SubResearchCoordinator`、分支算父 Handle 工作单元还是
     各持子 Handle、收据如何归并到**单一对账点**（§9.3 对账完整率的前提）。
     约束：取消语义沿 §7.3（只挡未派发、排空已启动只读）；lineage 复用
     `{task_id}:{branch_id}` 不另造；工作单元成对。冲突面事实（检阅方实测）：
     main 至 `cf86e891` 未碰 `sub_research.py` / `glm_agent_runtime.py` /
     `runtime_handle.py`，本轮不增加 rebase 负担。
  2. **rebase 轮**（升格用户，见下）：若批准，独立成轮 = rebase + 全量基线重建
     收据，不与功能轮混（采纳执行方回执理由 2）。
  3. **第 5 步**（Durable/Live + Projection + 事件出口合流）：置于 rebase 之后
     ——它要动 `agent_episode.py`，正是 main 持续在改的热点文件，rebase 前动它
     等于自愿扩大冲突面。网关 episode scope 传递按台账留给第 7 步。
- 升格用户事项：**rebase 时机批准**。建议顺序「子研究轮 → rebase 轮 → 第 5 步」，
  依据：子研究轮与 main 现无重叠；rebase 独立成轮保住「差值恰为新增」判据；
  第 5 步撞热点必须在 rebase 之后。

### 检阅裁定 · 子研究轮形状（2026-08-15，检阅方）

执行方提交的三条 [实测] 事实全部读码复核成立（坐标精确）：

1. 同步包含：`coordinator.run` 调用点 `agent_episode.py:1719`，外层
   `_run_sub_research` 的两个调用点 `:840` / `:877` 均落在 `run()` 体内
   （498–1125）；`sub_research.py:317` 的 `with ThreadPoolExecutor` 保证
   __exit__ 即 join。**且 `resume`（:1244 起）无调用点——子研究只发生在
   initial_run 工作窗口，包含性比小结表述更强一档。**
2. per-branch 事实已在 `_EpisodeLedger`（branch_started :1714，
   branch_completed/failed :1729-1746，字段还多于小结所列）。
3. 协调器在 `GLMAgentRuntime.__init__`（:409）构造、运行时级长生命周期；
   Handle per-run。绑构造器 = 把 per-run 收据钉在可复用对象上。

**检阅方新证据（归属检阅方，改写台账时一并回填）**：取消语义在协调器层
**已按 §7.3 实现且信号与 Handle 同源**——`sub_research.py:263`
持上游 `is_cancelled`（`glm_agent_runtime` 注释钉明与 Handle 折叠的是同一
callable）；`:282-283` run() 入口整体早退（"cancelled"）；`:388-398`
每分支启动时各查一次（未启动的分支变 error="cancelled"，已启动的排空）。
cancelled 分支流入 ledger branch 事件，可观测。**所以"并入第 5 步"不会
埋掉行为缺口：行为面（泄漏、取消）都已闭合，剩的只有收据对账。**

**裁定：采纳「并入第 5 步」，不采纳备选**（父 Handle 上
`begin_work("branch:{id}")` = 与 ledger branch 事件双账 + Handle 穿三层，
违反「不造第二事实源」元规则；换来的分支粒度 drain 在第 5 步 Projection
对账里免费得到）。

**并入的对价——台账改写必须做实，四条**：

1. §4.2.4 条目从「缺口」改写为「排空泄漏结构上不成立 + 收据对账归第 5 步」，
   证据四条并列（执行方三条 + 检阅方取消语义一条，注明归属）。
2. **点名承重不变量**：全部论证成立的条件是 `coordinator.run()` 保持同步
   （with-block join）。写明：谁把它改成 async / fire-and-forget，谁重开
   §4.2.4。
3. 符号名精确可 grep：`_run_sub_research`（:840/:877，仅 run() 内）。
   小结里的 `_maybe_sub_research` 是笔误，不得进台账。
4. 给第 5 步立对账要求一句：Projection 里 branch_started 与
   branch_completed/failed 必须成对，cancelled 分支可区分。

**顺序更新**：台账改写（小轮，docs+docstring 级，不碰 main 热点，可先行）
→ rebase 轮（**待用户批准**，独立成轮含基线重建）→ 第 5 步（含子研究
对账要求）。当前唯一阻塞决策 = rebase 批准。

另：执行方引用检阅方测量并申报「未独立复跑」——处理正确；检阅方已复核
main 仍在 `cf86e891`，该事实在当前远程状态下继续有效。

### 执行方小结 · Round「台账改写：子研究并入第 5 步」（2026-08-15，执行方）

- **本提交**：docs 1 文件（本文档）+ 代码 1 文件（`sub_research.py` **仅新增
  `run()` docstring，无行为改动**）。父提交 `57b3682d`。分支
  `feat/dsh-absorption-p0-seams` 仍**未 push、未合 main**、未动生产快照树。
  检阅方裁定原文（此前未提交）随本提交一并入库。
- **裁定对价四条的落点**：
  1. §4.2.4 改写 → 新增 **§4.1**，四条证据并列、逐条标注归属（执行方三条 +
     检阅方取消语义一条）；
  2. 承重不变量 → §4.1「承重不变量」段 + `SubResearchCoordinator.run` docstring
     （§9 要求的两处认领都落到位）；
  3. 符号名 → §4.1「坐标口径」段点名 `_run_sub_research`（`:840`/`:877`，仅
     `run()` 内），并记 `_maybe_sub_research` 全仓 grep 零命中；
  4. 第 5 步对账要求 → §5.3 第 5 步下三条（成对 / cancelled 可区分 /
     Durable-Live 归属）。
- **本轮新查到的两条**（都不翻转裁定，但改变第 5 步要做的事）：
  1. **「cancelled 分支可观测」只成立一半**（[实测·读码]，对检阅方证据 4 的精确化）：
     整轮拒绝走兜底循环、payload 带 `reason`，可区分；**单分支取消区分不出来**——
     `BranchResult.error="cancelled"` 没有任何事件字段承载它，结果循环 payload
     （`agent_episode.py:1735-1745`）与 worker 异常失败同形（同为 status=failed、
     gap_count=1）。原话"cancelled 分支流入 ledger branch 事件，可观测"应读作
     **流入了，但区分不出来**。已落成 §5.3 第 5 步第 2 条那个可判定的要求。
  2. **取消语义零测试覆盖**（[实测·变异]）：抽掉入口早退与分支守卫两处跑全量，
     **4982 passed / 4 skipped / 0 红**。行为闭合 ≠ 有门禁守着——§4.1 已把它标成
     "三处认领、不是门禁"，第 5 步补对账时一并变判据。
- **边界决定与理由**：
  - 只改 `sub_research.py` 的 docstring，**不碰 `agent_episode.py`**：后者是唯一真
    冲突面（主侧 U0 口径 37 hunk），rebase 前动它等于自愿扩大冲突面——与 §5.3
    第 5 步排在 rebase 之后是同一条理由。该文件里的同款认领**写死认领给第 5 步**
    （它本来就要改这个文件）。
  - **不修** `error` 不进事件这个收据缺口：修它要动 `_run_sub_research` 的 payload
    （在 `agent_episode.py`），属第 5 步事件合流的活；本轮修 = 顺手改 + 扩冲突面。
  - **不改 spec 本体**（主检出树 `docs/dsh-absorption-spec` 分支）：§4.2 第 4 条是
    通用底座条目，涵盖关闭/取消/**排空**/重启四档，本轮只裁定了排空一档，改条目
    正文会把另外三档一起带走；台账才是这条裁定的落点。
  - §5 加状态盖戳但**不删** 5.0–5.2：只标"已 PASS、本轮未独立复跑"，保留设计出处。
- **门禁**（本轮复跑，`umask 022`，`LOADED` = 工作树路径，**跑的是工作树即改后状态**，
  彼时 HEAD 仍是父提交 `57b3682d`，故 layer_audit 自报的 revision 标签是父提交的）：
  - 全量 **4982 passed / 4 skipped / 0 failed**（565.0s）—— 与父提交基线**逐值相等**：
    本轮新增用例 0（k=0），存量零改动，docstring 不改行为，判据是"差值恰为 0"。
  - `layer_audit.py` ERROR 0；`audit_tool_reachability.py` 12 声明一致、0 够不着；
    `ruff check intelligence scripts` 全绿；pre-commit 随提交跑。
  - 变异读数（上面第 2 条，597.4s）与门禁读数（565.0s）是**两次独立全量跑**。
- **未做/未验**：`4982 @ 57b3682d` 的父提交基线**未独立复跑**（引用检阅方上轮读数，
  本轮只跑改后值；两者相等本身就是"零改动"的证据，但父值归属检阅方）。

### 执行方小结 · Round「rebase onto `cf86e891`（独立成轮 + 基线重建）」（2026-08-15，执行方）

- **前置**：rebase 时机是升格用户事项，用户裁定**「批准，独立成轮」**。本轮因此
  **零功能改动、零测试改动**，只有 rebase + 台账重新盖戳。
- **结果：14/14 干净重放，零冲突**（`git -c rerere.enabled=true rebase gitea/main`）。
  - 等价性 [实测]：`git range-diff 23e2a07e..prerebase/dsh-seams-e21c50bf cf86e891..HEAD`
    14 行**全部标 `=`**，逐提交内容等价，无静默丢失。
  - 分叉 [实测]：`git merge-base HEAD gitea/main` = `cf86e891` = main 本身；
    `git rev-list --count HEAD..gitea/main` = 0。
  - 安全 ref：**`prerebase/dsh-seams-e21c50bf`** 保留 rebase 前 tip，未删——留给检阅方
    复核，确认后由用户决定何时删。
- **预判校正（写给下一个估 rebase 成本的人）**：上一版 §2.1 写"真冲突面
  `agent_episode.py`，主侧 U0 口径 37 hunk vs 本分支 4"，**实际零冲突**。hunk 数量的是
  **改动量**，冲突取决于**改动区是否相交**——main 的两个提交（`1f8cdc24` tool_exception
  detail、`2e50e263` 终局绑定改证据序号）在 finalization 区，本分支两个在 `run()` 入口与
  会话装配区，三方合并自动分开。已写进 §2.1。预估偏保守没代价，反过来有。
- **基线重建收据**（本轮的交付物，供下一轮继续用"差值恰为新增用例数"这把尺）：

  | 口径 | 读数 |
  |---|---|
  | **新基线（执行）** | **5055 passed / 4 skipped / 0 failed**（606.5s） |
  | 新基线（收集） | 5059 collected = 5055 + 4 ✓ |
  | main @ `cf86e891`（收集） | 5001 collected（临时 worktree 量完即删，已 prune） |
  | 本分支净增 | 5059 − 5001 = **58** 个用例 |
  | rebase 前基线 | 4982 passed / 4 skipped = 4986 collected；main 带进 73 个，与执行侧 5055 − 4982 = +73 对上 |

  **两个方向的算术都闭合 = rebase 既没丢测试也没重复测试**。下一轮的判据锚点是
  **5055 / 4 / 0 @ 本提交**。
- 其余门禁（`umask 022`，LOADED=工作树路径）：`layer_audit` ERROR 0（自报"对
  `5e0b38cd` 成立"，即本提交的父）；可达性 12 声明一致 / 0 够不着；ruff 全绿；
  pre-commit 随本提交跑。
- **坐标重测**：main 在 `agent_episode.py` 加了行，§4.1 / §5.3 引用的行号已全部按
  rebase 后重测（`run()` 区 +46、`_run_sub_research` 区 +76）；§2.1 记下"下次 rebase
  之后同样要重测"。**历史轮次记录里的旧行号一律不改**（append-only），live 坐标
  **只以 §4.1 / §5.3 为准**——上面那两条轮次小结里的 `:840`/`:1735-1745` 等是当时值。
- 分支状态：仍**未 push、未合 main**，未动生产快照树。
- **下一步**：第 5 步（Durable/Live + Projection + 事件出口合流，含 §5.3 那三条子研究
  对账要求）。它要动 `agent_episode.py`——现在正是冲突面最小的时刻。

### 检阅批注 · Round「台账改写轮 + rebase 轮」（2026-08-15，检阅方）

- **判定：两轮均 PASS**
- 独立复核（全部亲手复跑/读码/取证，逐条出处）：
  - 门禁 @ `d5fb5452`：全量 **5055 passed / 4 skipped / 0 failed**（666.6s，
    LOADED=工作树路径，umask 022）；layer_audit ERROR 0（扫 244 模块，自报
    `d5fb5452`——执行方自报父提交，与其跑在提交前的申报一致）；可达性
    12 声明 / 11 无条件 / 1 条件 / 0 够不着，ⓘ 注记在；ruff 全绿 [全部复跑]
  - rebase 等价性：`range-diff 23e2a07e..prerebase/dsh-seams-e21c50bf
    cf86e891..5e0b38cd` 14/14 全 `=` [复跑]；merge-base = `cf86e891`、
    behind=0、ahead=15（14 重放 + 1 收据提交）、无 merge 提交 [复跑]；
    安全 ref = `e21c50bf`，含 14 提交 [复跑]
  - 基线三角**加测第三点**（执行方没测过的样本）：分叉点 `23e2a07e` 收集
    **4928**（临时 worktree，量完即删已 prune）——4928+58=4986（rebase 前）、
    4928+73=5001（main @ `cf86e891`，亦亲测 5001）、4928+58+73=5059=5055+4，
    三个方向全闭合；58 与 73 若有重叠，重放去重后闭不上这个数 [复跑·换样本]
  - 改动面：`5e0b38cd` = 台账 +203 + `sub_research.py` +23 **纯 docstring**
    （逐行读过 diff，无代码行；docstring 如实申明"无测试钉住"）；`d5fb5452` =
    台账单文件——两轮「零功能/零测试改动」成立 [读 diff]
  - §4.1 四条证据坐标 rebase 后逐个核：run `:544` / 调用点 `:886`、`:924` /
    resume `:1295–:1687`（下一 def `:1689`）无调用点 / `_run_sub_research`
    `:1771` / `coordinator.run` 全仓唯一调用点 `:1795` / 三段式 `:1790-1794`、
    `:1805-1822`（payload 确无 `error` 字段——「单分支取消不可区分」属实）、
    `:1823-1834` 兜底；`sub_research.py` `:263`/`:305`/`:340`/`:352`/`:369-370`/
    `:407`/`:411`；`glm_agent_runtime.py` `:407`/`:409`/`:414`/`:416-418`/`:423`/
    `:481` 同一实参链；`research_plan.py` `:78-82`/`:137-148`——**全部命中，
    无一漂移** [读码]
  - 零冲突解释：分支 4 hunk（旧行号 ≤575 + import `:64`）与 main 27 hunk
    （`:7`/`:28`、`:284-391`、`:834` 起）区域实测不相交；main 至 `cf86e891`
    确未碰 §4.1 点名的四文件 [复跑]
  - 红线：gitea 无 dsh/seams 分支（ls-remote 零命中）；`5e0b38cd` 仅在 feat
    分支上；生产快照树 `cb09f895` status 干净；远程 main 实查仍 =
    `cf86e891` [取证]
  - 时间线：21:18 台账改写提交 → 21:20 rebase finish → 21:35 收据提交；
    gitea/main 最后 fetch 18:50，「本轮未 fetch」属实 [reflog]
  - **未抽查**：两次变异读数（取消守卫抽除 4982 / 597.4s）本轮未重跑，
    引用执行方申报。
- **检阅方证据（换样本命中一条，归属检阅方，下轮回填）**：「仓内唯一的线程
  存活断言在 `test_sub_research.py:441`」的全称量词不成立——`e21c50bf` 时点
  仓内已有 **4 处**测试侧 `assert not …is_alive()`（另三处
  `test_rag_worker.py:152`、`test_headless_tool_gateway.py:451`/`:551`），
  非 rebase 带入。三处钉的是 rag worker 恢复线程与 headless gateway 会话线程，
  都不钉 `SubResearchCoordinator`，**承重结论「排空/同步性零门禁」不动**；
  「`test_sub_research.py` 文件内唯一」属实。§4.1 与 `sub_research.py`
  docstring 各需一句量词修正（「仓内唯一」→「本文件内唯一，仓内另三处与
  排空无关」）。
- 标注（不影响判定）：
  1. **§3 提交史 +「4955 @ `4b23a516`」未随 rebase 重盖**：七个哈希全是
     prerebase 侧原件（= range-diff 左列），删安全 ref 并 gc 后将 dangle。
     删 ref 前先把 §3 重盖为新哈希（映射即 rebase 轮 range-diff 那 14 行）。
     §2 重盖了，§3 是漏网的 live 节，不在「轮次记录 append-only」豁免范围。
  2. **§2.1 收据自指漂移**：`rev-list --count` 写 14，`d5fb5452` 落库后照抄
     实测 15（收据提交自身 +1）；同因，照抄 range-diff 命令现在会多一行 `>`。
     下轮补一句「14 = 重放的功能提交数，不含 rebase 轮收据提交本身」。
- Round N+1 指派（依赖排序）：
  1. **第 5 步**（Durable/Live + Projection + 事件出口合流）：§5.3 三条对账 +
     `agent_episode.py` 侧承重认领落笔（台账已写死认领给这一步）。远程 main
     实查仍在 `cf86e891`，冲突面最小窗口开着，宜即刻开。
  2. 随第 5 步轮申报三条小修正（写进小结，不算顺手改）：§4.1 + docstring
     量词修正（回填检阅方证据）；§3 重盖新哈希；§2.1 自指注。
  3. 暂缓：prerebase 安全 ref 删除 → 用户决策后执行（见下）。
- 升格用户事项：
  1. **安全 ref `prerebase/dsh-seams-e21c50bf` 删除时机**：建议 §3 重盖入库后
     再删——它是台账旧哈希最后的解引用来源；
  2. **第 5 步开工**：两轮 PASS、无阻塞、main 未动，建议批准即开；
  3. push 红线维持（未 push 是纪律要求，不是缺陷）。

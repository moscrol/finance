# 交接：dsh 吸收 P0 接缝实施（第 5 步已收口，第 6 步未开）

日期：2026-08-15
交接人：上一任执行方（上下文耗尽）+ 检阅方（本文由检阅方整理）
接收人：新执行方 agent
状态：第 1-5 步完成（§10.5 #1–4 + 进度投影已迁）；第 6–8 步未开；分支未 push、未合 main

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
git rev-list --count gitea/main..HEAD     # 14 ← 见下方口径注，这个数会长
git rev-list --count HEAD..gitea/main     # 0（main 上没有本分支不含的提交）
git diff --shortstat HEAD...gitea/main    # 空（分叉为 0）
```

> **口径注（收检阅方标注 ②）**：`14` 是**盖戳当刻**重放完的提交数，**不是常量**——
> 收据提交、检阅批注提交落库后它就变 15、16……照抄它去"验证 rebase 对不对"会得到
> 一个必然对不上的数（**自指漂移**：这条命令数的东西包含记录它的那次提交）。要验
> rebase 本身，用**不自指**的两条：`HEAD..gitea/main` = 0，以及 range-diff 全 `=`。

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

> **本节的定位是「旧→新映射 + 基线锚点」，不是 live 全列**（2026-08-15 收检阅方标注 ①
> 改的定位）。上一版把它当"当前提交史全列"写，于是每落一个提交就过期一次。
> **要看当前全部提交，现取**：`git log --oneline gitea/main..HEAD`。
> 本节只保证两件事：① rebase 前后那 **14 个**提交的旧→新映射（下表，截至 `017c564c`
> 的提交一并留档）；② 当时的基线锚点。映射随时可复现（14 行全 `=`）：
> `git range-diff 23e2a07e..prerebase/dsh-seams-e21c50bf cf86e891..5e0b38cd`

```
ad2e3b02 Step 1 基线复核收据                                   （旧 b920feb6）
592a3552 EpisodeScope 与 ToolPipeline 接缝，不改变现有行为       （旧 0c97c41a）
26491965 检阅意见收口：窄化异常捕获 + trace context             （旧 13f26bf8）
6b5c8dcb 工具阶段事件与可达性登记接线（第 3 步）                 （旧 96e74d43）
7f7885b8 第 3 步打回项修复：恒真式/区分事件/sink 故障改写主路径   （旧 d35f32a2）
fee28de7 工具可达性审计接入 pre-commit + pytest 侧复挂          （旧 d69ee387）
103f47c7 Episode 入口构造 EpisodeScope，机制解除休眠（4 步 1/2） （旧 4b23a516）
adae26e5 打回项修复：Scope 构造断言改为经真实入口的行为测试       （旧 f69a8b96）
123da292 RuntimeHandle 六态生命周期，会话层接线（4 步 2/2-a）    （旧 06851cc7）
fa6e1b18 装配点身份断言：memory 身份穿透到装配产物（5.2）        （旧 23072aa3）
20ee811b §2 分叉盖戳重做 + 检阅批注入库                         （旧 bf991c69）
d03733f5 Arm C 会话接 RuntimeHandle + 三处认领裁定（4 步收尾）   （旧 639bad78）
26eff07a §2.1 差额口径修正 + 检阅批注入库                       （旧 57b3682d）
5e0b38cd §4.2.4 排空档改判 + 承重不变量认领（台账改写轮）         （旧 e21c50bf）
d5fb5452 rebase 到 cf86e891 + 分叉/坐标重盖 + 基线重建收据       （rebase 轮新增）
017c564c 检阅批注入库：台账改写轮 + rebase 轮均 PASS             （检阅方提交）
```

当前全量基线：**5055 passed / 4 skipped / 0 failed**（@ `d5fb5452`，`umask 022`，
检阅方已独立复跑一致）。旧记的「4955 @ `4b23a516`」是 **rebase 前**在旧哈希上的读数，
**不在新历史上重测**——中间 main 带进 73 个用例，两个数不可比。

⚠️ **删安全 ref `prerebase/dsh-seams-e21c50bf` 之前先看这节**：上表的旧哈希靠它解引用，
删 ref 并 gc 后 `git show <旧哈希>` 会失败（预期行为）。本节重盖之后，旧值只剩映射用途。

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
   `sub_research.py:342` 的 `with ThreadPoolExecutor` 在 `__exit__` join 只是第二道
   保险；**第一道**是 `:354` 的 `as_completed(futures)` 遍历全部已提交 future，
   而 `:371-372` 的返回值对**每个** request 取 `results[request.branch_id]`——少一个
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
   `RuntimeHandle(upstream_cancelled=...)`；`:307-308` run()
   入口整体早退 `refused_reason="cancelled"`；`:409` 把同一 callable 递进每个
   `BranchRequest`；`_run_one`（`:412`）的 `:413-424` 在每个分支启动前各查一次
   （未启动 → `status="failed"` + `error="cancelled"`；已启动的不打断，由证据 2
   那条同步消费排空）。

**承重不变量（谁破谁重开 §4.2.4）**：`SubResearchCoordinator.run()` **保持同步**。
谁把它改成 async / fire-and-forget（提前返回 future、executor 提到实例或模块级、
`shutdown(wait=False)` 后不消费、分支挪进后台队列），谁就必须重开 §4.2.4 的排空档
并在 RuntimeHandle 上补分支粒度 drain——**上面四条证据届时全部作废**。代码侧认领已
写进 `SubResearchCoordinator.run` 的 docstring（§9 要求的"docstring + 台账"两处）。

⚠️ **别把上面四条当门禁继承——它们一条都没有测试钉住。**

- 两处取消守卫（[实测·变异]）：抽掉 `:307-308` 入口早退与 `:413-424` 分支守卫后跑
  全量，**4982 passed / 4 skipped / 0 红**（597.4s；`git checkout` 恢复后树干净）。
- 同步性（[推断] + [实测·grep]）：连变异都构造不出来——要造出泄漏就得先改掉"消费完
  全部 future 才构造返回值"这个结构，那时红的会是结果缺失类断言，不是泄漏断言。
  **全仓 test 侧共 4 处 `is_alive()` 断言**（`test_sub_research.py:441`、
  `test_headless_tool_gateway.py:451` 与 `:551`、`test_rag_worker.py:152`），
  **没有一处钉协调器排空**；`test_sub_research.py` 里那处（文件内唯一）测的是
  `_BranchBudgetView` 并发结算的辅助线程。
  > 勘误（检阅方换样本查出，2026-08-15）：本条初版写作"仓内唯一的线程存活断言在
  > `test_sub_research.py:441`"——**全称量词不成立**，rebase 前快照就有 4 处。承重结论
  > （排空/同步性零门禁）不受影响，因为另三处钉的都不是协调器。**教训**：写"仓内唯一
  > X"必须全树 grep 后按命中数写，别把"我关心的那个文件里唯一"升格成全仓唯一。

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

## 10. 第 5 步设计钉（写码前先读；D3 需检阅裁定）

> 按本仓惯例「开工先把设计点钉进台账再写码」。本节只钉设计与实测约束，**不含实现**。
> 坐标 @ 本节所在提交。

### 10.1 现状：两个形状不同的事件出口

| 出口 | 形状 | 现状 |
|---|---|---|
| `_EpisodeLedger`（`agent_episode.py:220`） | `add(kind, payload) -> EpisodeEvent`，自带 `sequence`、`task_frame_hash`、`at`，落 `self.events` **并**转发 `event_sink` | 现役，Continuous 的唯一事件源 |
| `EpisodeScope.emit`（`episode_scope.py:267`） | `EventSink.emit(kind, payload)`，**无 sequence** | `event_sink=None`（`agent_episode.py:564-571` 写死认领），发射即丢 |

Scope 侧的三个阶段事件 `tool/pre_execute`、`tool/result`、`tool/error`
（常量在 `research_tool_registry.py:34-36`，发射点 `:609`/`:649`/`:753`/`:796`）
携带的是**"runner 真被调起"**这个事实（被去重/预算挡掉的不发）；
ledger 侧的 `tool_request`/`tool_result`/`tool_error`（`agent_episode.py:336`/`:415`/`:447`）
是**派发与回收**。两者不是同一件事，这一点决定了 D3。

### 10.2 [实测] 合流的第一道障碍不是接线，是线程安全

- 阶段事件的发射点在**共享线程池**里：`episode_tool_batch.py:72` 的模块级
  `_SHARED_TOOL_EXECUTOR`（`MAX_GLOBAL_TOOL_WORKERS = 8`，`:37`），`:486`
  逐候选 `submit`；`scope.emit` 在 `research_tool_registry.py` 的 `fetch()` 闭包内，
  即 worker 线程里。
- `_EpisodeLedger.add`（`agent_episode.py:239-258`）是
  `EpisodeEvent(len(self.events) + 1, ...)` 然后 `append`——**读长度与追加之间没有锁**。
  并发发射会发出**重复 sequence**。
- 它会撞两个现役硬断言：`episode_session.py:108-112` 的 resume 前缀不变量
  （事件只增、前缀逐条相等）、`test_agent_episode.py:1785` 的 `sequence == 1..N`。
- **今天没暴雷是因为 sink 为 None 时 `emit` 直接返回**（`episode_scope.py:285`），
  ledger 的现有 `add` 全在主线程。**合流那一刻起才并发。**

> **D1（执行方裁定）**：合流方向是 **Scope sink → `ledger.add`**，不是反向——
> sequence / `task_frame_hash` / `at` / live 转发四样都只在 ledger 那侧有。
> **D2（执行方裁定，先做）**：接线之前先给 `_EpisodeLedger.add` 上锁，并补一条
> **并发序号唯一性**的行为测试（多线程打同一个 ledger，断言 sequence 恰好是 1..N
> 的排列）。**顺序不能反**：先接线后加锁 = 制造一个随机变红的门禁。

### 10.3 D3【已裁定：归 Live，三条件】阶段事件归 Durable 还是 Live

> **检阅裁定（2026-08-15，`a64901cf`）：归 Live**，三个条件——
> ① durable 侧 `tool_request`/`tool_result`/`tool_error` 保持**对账权威**，阶段事件
> 不得成为任何金融字段或发布判据的**唯一载体**；② 分类落 D4 那张 services 单表并
> **用测试钉住** `tool/*` → Live，Live 事件**不进 `ledger.events`、不携带 durable
> sequence**；③ 本裁定**只覆盖 `tool/*` 三事件**，`branch_*` 归属留 D6 按 §5.3-3
> 单独裁定。除下面列的代价 A/B 外，裁定还给了一条执行方没写的依据：**方向不对称
> ——Live→Durable 将来是加法，Durable→Live 是对重放消费者的破坏。**
>
> 下面保留原始论证作为依据留档。

spec §7.4 的 Durable 名单里有 `tool_call`/`tool_result`，但那指的是本仓已有的
`tool_request`/`tool_result`。三个 `tool/*` 阶段事件如果也进 Durable：

- **代价 A（双账）**：durable 流里会同时有"派发"和"真调起"两套工具事件，
  违反本仓元规则「不造第二事实源」——除非同轮把 durable 侧的 `tool_*` 换成阶段事件，
  那是一次**对外契约翻转**（`continuous_turn_adapter.py:824` 的 `events` 数组、
  trace normalizer、评测 artifact 都吃它），必须单独开轮。
- **代价 B（重放日志变长）**：`episode_session.py:108-112` 与
  `openai_agents_runtime.py:1198`/`:1243`/`:1347` 把 `events` 当重放日志用；
  每次工具调用多 2–3 条事件会按并发批次成倍放大前缀长度。

**执行方建议（已被采纳）：阶段事件先归 Live**（只走 `event_sink` 实时出口，不进 `ledger.events`），
理由是它当前的用途是可观测性，且 Live/Durable 的分流点放在 `ledger.add` 内部时，
**对外契约零变化**。§7.1 那条"每次工具调用都有完整阶段事件"的对账，等真要做时再
决定是否翻转 durable 侧的工具事件契约——那时它是一次有意的、单独成轮的翻转。
**备选**（阶段事件进 Durable）不是不能做，代价是上面 A+B，请检阅方裁定。

### 10.4 其余落点

- **D4 分类落点**：**不给 `EpisodeEvent` 加字段**（`services/agent_runtime.py:250`
  的冻结 dataclass，4 个 runtime 共用）。仓内既有先例是把 `task_frame_hash`/`at`
  放 payload（理由见 `agent_episode.py:242-248` 的注释）。分类用 **kind 命名空间**
  （`tool/` 已经是）+ services 层一张表。
- **D5 Projection 落层**：services（`layer_audit` 硬门禁：services 不得 import
  runtime）。现在事实上的 projection 是
  `intelligence/runtime/continuous_turn_adapter.py:824` 的
  `[item.to_dict() for item in outcome.events]`；第 5 步把它收成一个 services 层函数，
  adapter / trace / 评测三个消费者共用，**不新建第二个投影口径**。
- **D6 子研究对账【已裁定：`branch_*` 归 Durable】**：§5.3 三条已落成断言
  （成对 / cancelled 可区分 / 车道归属）。"cancelled 可区分"给结果循环
  payload 加了 `error`（照抄 `BranchResult.error`），这是本步唯一改动
  `agent_episode.py` 发射形状的地方。整轮拒绝仍走兜底循环的 `reason`，
  两条路径都经 `run()` 钉住。D6 依据见本轮小结：它们没有 durable 孪生
  事件（不像 `tool/*` 对 `tool_request/result/error`），归 Live 会让重放
  日志缺分支，配对对账无处可依，也违反「阶段事件不得成为金融字段唯一载体」
  的精神。方向不对称与 D3 相同——先 Durable 是低代价可逆侧的反面：这里
  本来就在 Durable，搬到 Live 才是破坏。

### 10.5 建议的实施顺序（每条可独立成轮）

1. ~~`ledger.add` 上锁 + 并发序号唯一性测试（**无行为改动，可先行**）~~
   **✅ 已完成**（`f5fd13a6`，2026-08-15）。变异 5/5 抓到；过程教训见本轮小结。
2. ~~Live/Durable 分类表（services 单表）+ Scope sink 接到 Live 出口~~
   **✅ 已完成**（`d08cb867`，2026-08-15；落点 `intelligence/services/episode_event_lanes.py`）。
   前置的 sink 并发确认已做且**结论是安全**：`RunEpisodeProgressPublisher.publish`
   本来就是 `RLock` 全程持锁 + key 去重（`episode_progress.py:123`/`:128`）。
   下面是当时的原始要求，留档：按 D3 裁定：
   `tool/*` 三事件走 Live，**不进 `ledger.events`、不携带 durable sequence**，并要
   **用测试钉住这条分类**；durable 侧 `tool_request/tool_result/tool_error` 保持
   对账权威。⚠️ 注意 D3 条件②把并发暴露面**从 durable 列表移到了 Live sink**：
   8 个 worker 会并发调同一个 `event_sink`（外部回调），第 2 条实施前先确认现有
   sink 实现（`api/app.py:339`/`:362`/`:388`）在并发下的行为——第 1 条那把锁保护的是
   `ledger.events`，保护不到 sink 内部。
3. **✅ 已完成**（artifact 半截 `713fcdd0`；进度半截 `93bbb18b`，2026-08-16）：
   唯一口径已落 `intelligence/services/episode_projection.py`，
   `continuous_turn_adapter` 这**唯一的生产者**改读它。**实测更正**：这一步原先写作
   "三个消费者改读它"，实际形状是**一个生产者 / 五个消费者**——
   `artifact["events"]` 由 adapter 的一行内联推导产出，被 `conversation_orchestrator`
   / `api/stream_events` / `eval/runtime_backend_benchmark` /
   `eval/normalize_harness_trace` / `scripts/dump_episode_receipts` 五处读。收口生产者
   即收口口径，消费者不需要改。**进度半截**：`episode_progress` 整模块从
   `runtime/` 迁到 `services/`（无 runtime 依赖；五处 import 一次改完；不留 shim）。
4. **✅ 已完成**（`cbe4df10`，2026-08-15）：§5.3 三条对账 + D6 裁定 `branch_*`
   归 Durable。过程中投影层「未登记就报」抓到车道表漏了 `finish`，已穷尽补齐。
   详见本轮小结。

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

### 执行方小结 · Round「第 5 步开工：三条修正 + 设计钉」（2026-08-15，执行方）

- **两个提交**：`59c53e16`（检阅三条修正）+ 本提交（§10 设计钉）。分支仍**未 push、
  未合 main**，未动生产快照树。
- **三条修正逐条落点**（检阅方要求随轮带上）：
  1. **量词勘误**：§4.1 与 `sub_research.py` docstring 都改了，并留勘误块与教训。
     全仓 test 侧 4 处 `is_alive()`（`test_sub_research.py:441`、
     `test_headless_tool_gateway.py:451`/`:551`、`test_rag_worker.py:152`），
     **没有一处钉协调器排空**，承重结论不动。**这条是我自己的错**：那次 grep 的输出
     里就有另外三处，我写结论时把"这个文件里唯一"升格成了"仓内唯一"。
  2. **§3 提交史重盖**（标注 ①）：16 个当前哈希 oldest-first 全列、逐行标旧值，
     并写明删安全 ref 前先看本节；旧基线「4955 @ `4b23a516`」标注为 rebase 前读数、
     不在新历史上重测（与新基线差 73 个用例，不可比）。
  3. **§2.1 自指口径注**（标注 ②）：`rev-list --count gitea/main..HEAD` 数的东西
     **包含记录它的那次提交**，会一路长下去；验 rebase 请用不自指的
     `HEAD..gitea/main = 0` 与 range-diff 全 `=`。
  - 附带：docstring 修正使 `sub_research.py` 行号再下移 2 行，§4.1 的
    `:307-308`/`:342`/`:354`/`:371-372`/`:409`/`:412-424` 已重测。
- **第 5 步没有直接写码，先出设计钉 §10**，因为读码量出一条会决定做法的硬约束：
  - **[实测] 合流的第一道障碍是线程安全，不是接线**。阶段事件的发射点在共享线程池
    （`episode_tool_batch.py:72`，8 worker）里，而 `_EpisodeLedger.add` 的
    "读长度 → 追加"没有锁，合流当刻起就会发出重复 sequence，撞
    `episode_session.py:108-112` 的 resume 前缀不变量和 `test_agent_episode.py:1785`
    的序号断言。今天不暴雷只是因为 sink 为 None 时 `emit` 直接返回。
  - 于是 §10.5 把第 5 步拆成四条可独立成轮的实施步，第 1 条（上锁 + 并发序号测试）
    无行为改动、可先行。
- **一个需要裁定的点（D3）**：三个 `tool/*` 阶段事件归 Durable 还是 Live。执行方建议
  **先归 Live**（对外契约零变化）；备选的代价是与 `tool_request/tool_result` 双账 +
  重放日志按并发批次成倍变长。**裁定前不接线**。
- **门禁**（跑在 `59c53e16` 之上、含本提交的工作树，`umask 022`，LOADED=工作树路径）：
  全量 **5055 passed / 4 skipped / 0 failed**（690.9s）——与 `d5fb5452` 基线**逐值相等**，
  差值 0（两个提交都只动 docs + docstring，无行为改动、无新增用例）；
  `layer_audit` ERROR 0（自报"对 `59c53e16` 成立"）；可达性 12 声明一致 / 0 够不着；
  ruff 全绿；pre-commit 随两次提交各跑一次。
- **未做**：第 5 步的实现（四条实施步一条都没做）；`error` 进事件的收据缺口仍在。

### 执行方小结 · Round「§10.5 第 1 条：ledger.add 上锁」（2026-08-15，执行方）

- **两个提交**：`f5fd13a6`（上锁 + 并发用例）+ 本提交（台账）。分支仍**未 push、
  未合 main**，未动生产快照树。
- **改了什么**（`agent_episode.py`，行为中性）：`add` 的「读 `len(self.events)` →
  追加」进 `RLock` 临界区；`record_runtime_result` 读列表改为锁内取快照；
  **sink 调用留在锁外**（外部回调，持锁调它是经典死锁源；代价——并发时到达顺序可能
  与 sequence 不一致，消费者按 sequence 排序，已写进注释）。
- **计数**：5055 → **5056**，k=1 恰为新增用例数，存量零改动。
- **变异 5/5 抓到**：抽掉 `add` 里的锁，新用例连红 5 次（实测重号
  `[1, 2, 2, 2, 2, 2, ...]`）；恢复后树干净。
- ⚠️ **过程自报两件，都是我的错，也都是可复用的教训**：
  1. **第一版并发用例是假绿**。没有确定性抢占注入时，抽掉锁跑 5 次**全绿**——CPython
     按 5ms 时间片切线程，8 个线程各自在一个时间片内就跑完了全部 `add`，交错从未
     发生。**那一版测的是调度器的运气，不是不变量**，已废弃重写：现版在临界区中央
     monkeypatch `EpisodeEvent` 使其 `sleep(0.5ms)` 让出 GIL，把窗口确定性撑开——
     有锁时 sleep 在锁内发生、序号照样唯一，没锁时立刻重号。
     **教训：并发用例必须先证明它在"去掉保护"的版本下会红，否则它是一条假门禁。**
     这与本仓已有的两种假测试（spy 透传、`inspect.getsource`）是同族第三形状。
  2. **变异恢复 `git checkout -- <file>` 把我未提交的实现一起还原掉了**。当时锁还没
     提交，一条恢复命令把它擦了，导致我以为"有锁也红"，差点去追一个不存在的 bug。
     **教训：变异测试前先提交被测实现**——`git checkout --` 的恢复目标是 HEAD，
     不是"我改之前的样子"。
- **收上轮两条标注**：§3 定位改为「旧→新映射 + 基线锚点」，并写明要看当前全列请现取
  `git log --oneline gitea/main..HEAD`（不再承诺 live 全列）；§10.4 的
  `continuous_turn_adapter.py:824` 补全 `intelligence/runtime/` 路径。
- **D3 裁定已回填** §10.3（归 Live + 三条件 + 方向不对称性那条依据），§10.5 第 2 条
  按裁定重写，并加了一条**裁定的副作用**：条件②把并发暴露面从 durable 列表移到了
  **Live sink**——8 个 worker 会并发调同一个外部 `event_sink`，第 1 条这把锁保护不到
  它。第 2 条实施前要先确认 `api/app.py:339`/`:362`/`:388` 那三个 sink 在并发下的行为。
- **门禁**（跑在 `f5fd13a6` 之上、含本提交的工作树，`umask 022`，LOADED=工作树路径）：
  全量 **5056 passed / 4 skipped / 0 failed**（602.4s）＝上轮基线 5055 **+1**，
  k 恰为新增用例数；`layer_audit` ERROR 0（自报"对 `f5fd13a6` 成立"）；可达性
  12 声明一致 / 0 够不着；ruff 全绿；pre-commit 随两次提交各跑一次。
  变异读数（5/5）与门禁读数是**两次独立跑**。
- **下一轮**：§10.5 第 2 条（Live/Durable 分类表 + Scope sink 接 Live 出口），
  开工前先做上面那条 sink 并发确认。**新基线锚点：5056 / 4 / 0。**

### 执行方小结 · Round「§10.5 第 2 条：工具阶段事件接 Live 车道」（2026-08-15，执行方）

- **两个提交**：`d08cb867`（分类表 + Live 出口 + 接线 + 5 条用例）+ 本提交（台账）。
  分支仍**未 push、未合 main**，未动生产快照树。
- **前置先做了**（上轮我自己立的条件）：`RunEpisodeProgressPublisher.publish`
  实测**本来就并发安全**——`RLock` 全程持锁 + `progress.key` 去重
  （`episode_progress.py:123`/`:128`）。所以裁定条件②把并发暴露面移到 Live sink
  这件事，下游是接得住的；新增的锁只需保 Live 计数器。
- **落点**：新模块 `intelligence/services/episode_event_lanes.py`——两张不相交的
  kind 表 + `lane_for()` + `LiveEventSink`。`lane_for` 对未登记 kind **fail closed
  抛错**（抛出点在 `EpisodeScope.emit` 的兜底内，计进 `event_sink_failures`，
  不影响主路径）。接线只在**真有下游 sink 时才挂**，否则 `dump()` 的
  `event_sink_attached` 会在没人接收时报 True——收据不说谎优先于形式上"接线了"。
- **裁定三条件的兑现方式**：① durable 侧一字未动，且新增断言钉住两侧
  `call_id` ↔ `tool_call_id` 可对账；② 分类落**这一张**表并由 5 条用例钉住，
  Live 自带独立编号空间 + `lane="live"` 标记，且用例断言 `outcome.events` 里
  **没有任何 `tool/` 前缀**；③ 表里 `branch_*` 仍在 DURABLE，并在模块 docstring
  写明"那是今天的实际去向，不是已裁定的终局"。
- **计数**：5056 → **5061**，k=5 恰为新增用例数。
- **存量改动 1 处（有意，非顺手改，单独申报）**：
  `test_progress_sink_observes_append_only_events_before_and_during_model_work`
  原先断言「sink 流 == durable 流」。sink 现在是两条车道的**共同出口**，该等式
  按裁定必然不再成立，故改为断言 **durable 子集逐条相等**（顺序与只增性不变），
  并补三条新性质（Live 到达、durable 无 `tool/`、两侧 id 可对账）。**这是把用例
  改成钉新契约，不是放宽它。**
- **生产 UI 行为零变化**（[实测]）：`project_episode_progress` 按 kind 查
  `_EVENT_PROJECTIONS`，未知 kind 返 None，而 `tool/*` 不在表里 → 不会多出任何
  进度条目。**这也意味着 Live 车道目前止于投影表**：事件确实流到了 sink（用例断言
  过），但还没有人渲染它。要让它可见是一次**有意的加法**，归第 3 条 Projection
  收口轮，不在本轮偷偷做。
- ⚠️ **过程自报两件，都是上一轮那条教训的更细一层**：
  1. **Live 并发用例第一版又是假绿**（变异 0/3）。这次注入点在锁块内，但排在
     `self._sequence += 1` **之后**——`+= 1` 自己的「读 → 写回」窗口没被撑开。
     **"注入在锁里"不够，必须注入在被保护的那对读写之间。** 把实现改成
     「读号 → 建事件（可注入）→ 写回」后变异 **5/5 抓到**；顺带修掉一个真 bug：
     构造抛错时不再白白消耗序号，Live 编号不留空洞。
  2. **对未跟踪的新文件做变异，`git checkout --` 恢复不了**（报
     `pathspec did not match`），磁盘上直接留着变异版本。上一轮的教训是"先提交"，
     这次的补充是**新文件至少要先 `git add` 进 index**，并且**恢复后要验**。
     （本轮因此作废过一次全量门禁读数——它跑在被变异的文件上。）
- **门禁**（重跑于恢复后的树，`umask 022`，LOADED=工作树路径）：全量
  **5061 passed / 4 skipped / 0 failed**（466.9s）；`layer_audit` ERROR 0
  （新模块在 services 且不 import runtime）；可达性 12 声明一致 / 0 够不着；
  ruff 全绿；pre-commit 随提交跑。变异读数（Live 锁 5/5）是独立跑。
- **下一轮**：§10.5 第 3 条（Projection 收口到 services 层）。**新基线锚点：5061 / 4 / 0。**

### 执行方小结 · Round「§10.5 第 3 条：artifact 事件投影收口」（2026-08-15，执行方）

- **两个提交**：`713fcdd0`（`episode_projection` + adapter 改读 + 5 条用例）+ 本提交
  （台账）。分支仍**未 push、未合 main**，未动生产快照树。
- **对台账原描述的一处实测更正**：第 3 条原写"三个消费者改读它"，实际形状是
  **一个生产者 / 五个消费者**——`artifact["events"]` 由
  `continuous_turn_adapter` 的一行内联推导产出，被 `conversation_orchestrator`、
  `api/stream_events`、`eval/runtime_backend_benchmark`、
  `eval/normalize_harness_trace`、`scripts/dump_episode_receipts` 五处读
  （[实测] grep）。**收口生产者即收口口径，消费者一个都不用改**——这也是为什么
  本轮存量零改动。
- **钉住的不变量**：只投 Durable。今天 Live 进不了 `ledger.events`，所以上线输出
  逐字节不变；钉它是为了第 4 条动事件出口时，"Live 悄悄漏进重放/评测口径"这种
  最难发现的回归会立刻红。变异实测：去掉 Live 过滤 → 恰 2 条红。
- **两个边界的 fail 策略故意相反**（模块 docstring 写明理由）：发射边界
  `lane_for` 对未登记 kind **抛错**（那里抛错什么都不丢，`EpisodeScope.emit` 兜住
  并计进 `event_sink_failures`）；artifact 边界**保留该事件**并记进
  `unregistered_kinds`（这里已是研究做完之后，抛错等于把一次完成的研究连同证据
  一起丢掉）。**但不静默**：异常装进返回值，adapter 只在非空时写
  `artifact["events_projection_anomalies"]`——常态下 artifact 形状一字不变。
- **计数**：5061 → **5066**，k=5 恰为新增用例数，**存量零改动**。
- **本轮只做完第 3 条的一半，明确申报**：UI 进度那条投影
  （`project_episode_progress`，在 `runtime/episode_progress.py`）仍未并入 services。
  它无 runtime 依赖、可迁，但迁移会动 `api/app.py` 的 import 面，单独一轮做更干净。
- **门禁**（`umask 022`，LOADED=工作树路径）：全量 **5066 passed / 4 skipped /
  0 failed**（446.0s）；`layer_audit` ERROR 0；可达性 12 声明一致 / 0 够不着；
  ruff 全绿；pre-commit 随提交跑。变异读数是独立跑。
-   **下一轮**：§10.5 第 4 条（子研究三条对账断言，含结果循环 payload 补 `error`；
  `branch_*` 的车道归属按 §5.3-3 在那一轮单独裁定），或先把上面那半条进度投影迁完。
  **新基线锚点：5066 / 4 / 0。**

### 执行方小结 · Round「§10.5 第 4 条：子研究对账 + D6 + 车道表穷尽补齐」（2026-08-15，执行方）

- **两个提交**：`cbe4df10`（对账断言 + D6 + 表补齐 + 7 条用例）+ 本提交（台账）。
  分支仍**未 push、未合 main**，未动生产快照树。安全 ref
  `prerebase/dsh-seams-e21c50bf` **未删**（条件已满足，等用户明示）。
- **D6 裁定（执行方）：`branch_started` / `branch_completed` / `branch_failed` /
  `branch_tool` 归 Durable。** 依据：
  1. spec §7.4 金融约束——evidence hash/source/status/gaps 不得在 Projection
     丢失；这四种事件承载证据来源、分支预算消耗和成对身份；
  2. 它们**没有** durable 孪生事件（`tool/*` 对得上 `tool_request/result/error`，
     `branch_*` 对不上任何东西）。归 Live 会让它们成为分支身份的唯一载体，
     违反 D3 条件①的精神；
  3. 方向不对称：它们今天已经在 Durable。搬到 Live 是对重放消费者的破坏；
     保持 Durable 是零契约变化。归 Live 的后果可测——`project_durable_events`
     会把它们当 Live 丢掉，配对对账字段全空。
  D3 明确不覆盖 `branch_*`，本轮单独定。检阅可确认或推翻。
- **§5.3 三条对账的兑现**：
  1. 成对性从「兜底循环的实现细节」变成投影层断言
     （`unpaired_branch_ids` / `orphan_branch_terminals`，两个方向）；
  2. 单分支取消：结果循环 payload 照抄 `BranchResult.error`，不另造
     cancelled 布尔位。真实 `run()` 入口一条断言它与
     `branch_worker_exception:*` 可区分；
  3. 整轮拒绝：空 `branches` + `refused_reason="cancelled"` 走兜底循环，
     payload 带 `reason`。这条也经 `run()` 钉住——两条路径丢掉其中一条时
     另一条仍绿，是上一条单独存在时的盲区。
- **过程中被投影层第一天抓住的表缺陷**（这正是「未登记就报」要抓的）：
  真实 `run()` 出口必有 `finish`，表里没有 → 投影会把正常 openai/codex
  跑次标成 `unregistered_kinds`。穷尽扫三条 runtime 的发射 API
  （`ledger.add` / `self.add` / `_add_event` / `EpisodeEvent` 字面量，
  含 `if/else` 二选一；`layers.add` 这类集合操作不算）：
  - 两个**假 kind**：`phase` / `reason` 是 payload 键，不是事件种类；
  - 四个 continuous 真 kind：`finish`、`repair_reentry`、
    `finalization_recovery_started`、`finalization_recovery_outcome`；
  - 三个旁路 runtime 真 kind：`configure`（codex）、`tool_closed`（SDK）、
    `root_budget_overdraft`（gateway）。
  表注释从「`_EpisodeLedger.add` 今天发出的全部 kind」改成「凡是能进
  `AgentOutcome.events`、再被 `project_durable_events` 投影的 kind」——
  投影挂在 `ContinuousTurnAdapter` 上，三条 backend 共用。
- **计数**：5066 → **5073**，k=7 恰为新增用例数（1 条穷尽性 + 4 条投影对账
  + 2 条真实入口：单分支 `error` / 整轮 `reason`），**存量零改动**。
- **变异（提交后、`git checkout --` 恢复，树干净）**：
  1. 结果循环去掉 `error` → `test_cancelled_branch_carries_error...`
     `KeyError: 'error'`；
  2. 投影去掉成对跟踪 → unpaired / orphan 两条断言 `() == ('branch-…',)`；
  3. 表里拿掉 `finish` → 恰报 `发射了但表里没有: ['finish']`；
  4. 把 `branch_*` 挪到 Live → 分类抽样 + 投影 cancelled + 真实入口
     三条同红（事件被当 Live 丢掉）。
- ⚠️ **过程自报**：上一会话在未提交时用 `git checkout --` 做 `finish`
  变异，把整张表修正还原成 HEAD 旧表。本轮先提交再变异，恢复后
  `git status` 干净。教训没变：**未提交的实现不要用 checkout 做变异恢复。**
- **收口时更新本账 L1-DSH**：本轮之后另开观测台薄账 PR，指针改为
  §10.5 #1–4 已完成 / 进度投影半截未迁 / 未 push。不在本分支改
  `docs/roadmap.md`（那是 main 上的薄账，本分支未合）。
- **门禁**（`umask 022`，LOADED=工作树路径）：全量 **5073 passed / 4 skipped /
  0 failed**（549.3s）；`layer_audit` ERROR 0（扫 246 模块）；可达性
  12 声明一致 / 0 够不着；ruff 全绿；pre-commit 随提交跑。变异读数是独立跑。
- **下一轮**：第 3 条剩下的半条（`project_episode_progress` 迁到 services，
  会动 `api/app.py` import），或第 6 步 ResearchProfile。不要两件叠在一轮。
  **新基线锚点：5073 / 4 / 0。**

### 执行方小结 · Round「§10.5 第 3 条下半：进度投影迁到 services」（2026-08-16，执行方）

- **两个提交**：`93bbb18b`（整模块迁移 + 2 条用例）+ 本提交（台账）。
  分支仍**未 push、未合 main**，未动生产快照树。安全 ref 未删。
- **做了什么**：`episode_progress.py` 整模块从 `runtime/` 迁到 `services/`
  （git 记成 rename 89%）。2026-07-27 的计划本来就写落 services；它零
  runtime import，只依赖 `EpisodeEvent` 和 `RunStore`（都在 services）。
  `layer_audit` 扫描 runtime 模块 16 → **15**。
- **为什么整模块而不是拆开发射器 / 只迁函数**：
  - 拆开：`RunEpisodeProgressPublisher` 写 RunStore，按「做 IO → runtime」
    可以留，但 RunStore 本身就在 services，services 允许 IO；拆开会让
    `EpisodeProgress` 出现两个进口。
  - 只迁 `project_episode_progress`：adapter 直接构造 `EpisodeProgress`，
    类型和投影必须同层。
  - **不留 runtime shim**：shim 是第二入口。五处 import 一次改完
    （`api/app.py`、`continuous_turn_adapter.py`、三条测试）。
- **没和 `episode_projection` 合并**：那是 artifact `events` 数组的唯一口径；
  这是 UI 进度。未知 kind 的 fail 策略故意相反（进度返 None / artifact
  保留并记 `unregistered_kinds`），合在一个模块里会把两条契约搅在一起。
- **钉住的不变量**：
  1. `PROGRESS_EVENT_KINDS ⊆ DURABLE_EVENT_KINDS`——进度表是车道表的精选
     子集，不是全表（`model_turn` / `configure` 故意不出进度）；
  2. 旧路径 `intelligence.runtime.episode_progress` 必须
     `ModuleNotFoundError`，现役函数的 `__module__` 是 services。
  Live 阶段事件（`tool/pre_execute`）也返 None，UI 不多出条目（落在原有
  「未知 kind 返 None」那条上，不是新用例）。
- **计数**：5073 → **5075**，k=2 恰为新增用例数。存量改动是 import 路径
  和一层 docstring，行为零变化。
- **变异（提交后、checkout / rm 恢复，树干净）**：
  1. 进度表加未登记 kind → 恰报 `['not_a_lane_kind']`；
  2. 把 `runtime/episode_progress.py` 放回去 → `DID NOT RAISE ModuleNotFoundError`。
- **收口时更新本账 L1-DSH**：本轮之后另开观测台薄账 PR，指针改为第 5 步
  已收口 / 第 6–8 步未开 / 未 push。
- **门禁**（`umask 022`，LOADED=工作树路径）：全量 **5075 passed / 4 skipped /
  0 failed**（476.7s）；`layer_audit` ERROR 0（扫 246 模块 / runtime 15）；
  可达性 12 声明一致 / 0 够不着；ruff 全绿；pre-commit 随提交跑。
- **下一轮**：第 6 步 ResearchProfile + effective-config 收据（必须吸收
  已有 `GroundedBudgetProfile`，不另起第二配置源）。不要和别的步叠一轮。
  **新基线锚点：5075 / 4 / 0。**

### 检阅批注 · Round「三条修正 + 第 5 步设计钉」（2026-08-15，检阅方）

- **判定：PASS**（含对 D3 的裁定，见下）
- 独立复核（全部亲手复跑/读码，逐条出处）：
  - 门禁 @ `88287cbf`：全量 **5055 passed / 4 skipped / 0 failed**（610.6s，
    LOADED=工作树，umask 022）——与 `d5fb5452` 基线逐值相等、差值 0，
    与「两提交只动 docs + docstring」互证；layer_audit ERROR 0（自报
    `88287cbf`）；可达性 12 声明一致 / 0 够不着；ruff 全绿 [全部复跑]
  - 三条修正逐条对上轮指派核销：量词勘误落 §4.1 + docstring 两处、勘误块
    与教训在、三处反例坐标与检阅方证据逐字一致；§3 的 14 行旧→新映射与
    检阅方上轮亲跑的 range-diff 逐行一致（+ `d5fb5452`、`017c564c` = 16）、
    删 ref 警示在；§2.1 口径注给出的不自指验证对（`HEAD..gitea/main` = 0 +
    range-diff 全 `=`）本轮均复跑成立 [读 diff + 复跑]
  - 坐标重测：`sub_research.py` 六处新值（`:263` 不变，`:307-308`/`:342`/
    `:354`/`:371-372`/`:409`/`:412-424`）全部命中 [读码]
  - §10 设计钉的代码主张**逐条读码核过，无一漂移**：`_EpisodeLedger` `:220`、
    `add` `:239-258` 的 `EpisodeEvent(len(self.events)+1)` → `append` 确无锁、
    sink 转发 `:251-257`；`EpisodeScope.emit` `:267`、sink None 早退 `:285-286`；
    `event_sink=None` 认领注释 `:560-571`；阶段事件常量
    `research_tool_registry.py:34-36`、发射点 `:609`/`:649`/`:753`/`:796` 全在
    `execute`（def `:580`）内，而 `execute` 正是批次提交进 worker 的 operation
    （`episode_tool_batch.py:465` → `:486` submit）；共享池 `:72`、8 worker
    `:37`；ledger 侧 `tool_request`/`tool_result`/`tool_error` `:336`/`:415`/
    `:447`；**全部 `ledger.add` 调用点都在 `agent_episode.py`**（批次文件零命中），
    经 `accumulator.consume`（`:1003`/`:1495`）在主流程消费——「现有 add 全在
    主线程」结构上成立；撞击目标 `episode_session.py:108-112` 前缀不变量与
    `test_agent_episode.py:1784-1786` 序号断言属实；消费侧
    `continuous_turn_adapter.py:824`（events 投影）、`openai_agents_runtime.py`
    `:1198`/`:1243`/`:1347`（重放用途）、冻结 `EpisodeEvent`
    （`services/agent_runtime.py:250`）全部核实 [读码]
  - 红线：未 push（ls-remote 零命中）、远程 main 实查仍 = `cf86e891`、
    生产快照树 `cb09f895` 干净、树干净、安全 ref 在位 [取证]
  - 偏差申报核：上轮指派为「第 5 步即开」，本轮交付为设计钉而非实现——
    符合本仓「开工先钉设计再写码」惯例，且 D3 阻塞接线的理由读码属实，
    偏差已申报，不构成打回项。
- **D3 裁定（检阅方）：三个 `tool/*` 阶段事件归 Live**。依据：
  spec §7.4 的 Durable 名单以「模型可见内容可重建」划界，本仓对应物是
  `tool_request`/`tool_result`（读码核实 `:336`/`:415` 即派发/回收）；阶段事件
  是执行遥测（「runner 真被调起」），最接近 Live 名单的 agent status /
  queue timing 档；金融五字段（hash/source/date/status/gaps）不经阶段事件
  承载；备选的代价 A（durable 双账，违 §8.3 与「不造第二事实源」）、代价 B
  （重放前缀按并发批次放大，撞 `:108-112` 与 openai 重放三处）均读码属实。
  且方向不对称：Live→Durable 将来是加法，Durable→Live 是对既有重放消费者的
  破坏——先 Live 是低代价可逆侧。**三个条件**：
  1. durable 侧 `tool_request`/`tool_result`/`tool_error` 保持对账权威，阶段
     事件不得成为任何金融字段或发布判据的**唯一**载体；
  2. 分类落 D4 那张 services 层单表，`tool/*` → Live 用测试钉住；Live 事件
     不进 `ledger.events`、不携带 durable sequence，resume 前缀不变量与
     序号断言保持绿；
  3. 本裁定只覆盖 `tool/*` 三事件；`branch_*` 归属仍按 §5.3 第 3 条在 D6
     单独裁定。将来若 §7.1「完整阶段事件」要变成离线可审计判据，按对外契约
     翻转单独成轮重议，不回溯本裁定。
  D2 的顺序（先上锁后接线）一并背书：先接线后加锁 = 制造随机变红的门禁。
- 标注（不影响判定）：
  1. §3 哈希清单以 `017c564c` 截止，`59c53e16`/`88287cbf` 及本批注提交不在
     列——与 §2.1 口径注同理，「全列」是盖戳当刻口径。下次重盖时建议把 §3
     定位改写为「旧→新映射 + 当前基线锚点」，不承诺 live 全列。
  2. §10.4 引 `continuous_turn_adapter.py:824` 未带路径（实际在
     `intelligence/runtime/`）。一字级。
- Round N+2 指派（依赖排序）：
  1. §10.5 第 1 条：`ledger.add` 上锁 + 并发序号唯一性测试（行为中性轮，
     判据「5055 + k，k = 新增用例数，存量零改动」）；
  2. §10.5 第 2 条：分类表 + Scope sink → ledger 合流，按 D3=Live 接线，
     `tool/*` → Live 断言进测试；
  3. §10.5 第 3、4 条依序（Projection 收口 services 层；子研究三条对账断言
     + 结果循环 payload 补 `error`）。
- 升格用户事项：**安全 ref `prerebase/dsh-seams-e21c50bf` 删除条件已满足**
  （§3 重盖已入库且映射自持）——删除本身是破坏性动作，仍由用户执行或明示
  后代执行；push 红线维持不变。

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

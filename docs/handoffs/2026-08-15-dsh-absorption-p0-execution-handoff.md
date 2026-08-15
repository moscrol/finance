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
| 实施工作树 | `/Users/a77/fwp-wt-dsh-seams`，分支 `feat/dsh-absorption-p0-seams` @ `4b23a516` |
| 分叉基线 | `gitea/main@23e2a07e`；gitea/main 现为 `f43f2507`（增量纯 docs，不碰代码，无需 rebase） |
| Spec | `docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md`，在主检出树 `/Users/a77/finance-workspace-private` 的 `docs/dsh-absorption-spec` 分支 @ `d98a8a59` |
| Step 1 基线收据 | `docs/superpowers/specs/2026-08-15-dsh-absorption-step1-baseline-receipt.md`（实施分支上；§6 是三条已裁定问题，§7 是备查项） |
| dsh 源码快照 | `/Users/a77/finance-workspace-private/tmp/dsh-source-index`，钉在 `47f9438`，sparse cone 含 `packages/llm` |
| 零件回写 | `~/harness-reference/BUILD.md`（工具可达性审计、阶段事件加法两节） |
| 两个分支 | 均**未 push、未合 main**。红线：不得 push、不得合 main、不得动生产快照树 |

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

## 5. 马上要做的（按优先序）

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

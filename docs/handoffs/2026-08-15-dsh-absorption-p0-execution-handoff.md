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
| 实施工作树 | `/Users/a77/fwp-wt-dsh-seams`，分支 `feat/dsh-absorption-p0-seams` @ `23072aa3` |
| 分叉基线 | merge-base `23e2a07e`；`gitea/main` 现为 `bcde2851`（**盖戳时刻见下节；这一格会漂，引用前重测**） |
| Spec | `docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md`，在主检出树 `/Users/a77/finance-workspace-private` 的 `docs/dsh-absorption-spec` 分支 @ `d98a8a59` |
| Step 1 基线收据 | `docs/superpowers/specs/2026-08-15-dsh-absorption-step1-baseline-receipt.md`（实施分支上；§6 是三条已裁定问题，§7 是备查项） |
| dsh 源码快照 | `/Users/a77/finance-workspace-private/tmp/dsh-source-index`，钉在 `47f9438`，sparse cone 含 `packages/llm` |
| 零件回写 | `~/harness-reference/BUILD.md`（工具可达性审计、阶段事件加法两节） |
| 两个分支 | 均**未 push、未合 main**。红线：不得 push、不得合 main、不得动生产快照树 |
| 本文档 | 已随 `f69a8b96` 入库（早先「未提交」的口径已作废） |

### 2.1 分叉盖戳（2026-08-15 18:20，附测量命令）

上一版这一节写「增量纯 docs，不碰代码，无需 rebase」——**已作废**。现在 main
碰代码，且碰到了本分支改过的文件。下面每个数字后面就是产出它的命令，重测请照抄
（口径不同数字就不同，这正是上一轮被点名的地方）。

```bash
cd /Users/a77/fwp-wt-dsh-seams
git rev-parse gitea/main                     # bcde2851（远程跟踪 ref，最后 fetch 08-15 14:26）
git merge-base HEAD gitea/main               # 23e2a07e
git diff --shortstat HEAD...gitea/main       # 76 files, +14544, -138  ← 全量口径
git diff --stat HEAD...gitea/main -- intelligence scripts market_feature_store | tail -1
                                             # 45 files, +10778, -129  ← 仅代码路径
# 差额 31 = docs/ 30 + 顶层 tests/ 1（后者不在上面那三个路径里）
git diff --name-only 23e2a07e..HEAD > /tmp/mine.txt
git diff --name-only HEAD...gitea/main > /tmp/theirs.txt
comm -12 <(sort /tmp/mine.txt) <(sort /tmp/theirs.txt)   # 恰 4 个重叠文件
```

- **`gitea/main` 是跨工作树共享的 ref**（同一个 `.git`），所以两棵树读到的值必然
  一致；`git reflog show gitea/main` 能看到它的历次落点（@{5} 是 `f248613e`）。
  拿旧 reflog 位置量出来的数字和拿 @{0} 量出来的对不上，是**快照不同**，不是
  谁算错——这也是本节每个数字都必须带 ref 值的原因。
- 四个重叠文件：`intelligence/api/app.py`、`intelligence/tests/test_workbench_api.py`、
  `intelligence/tests/test_continuous_turn_adapter.py`、
  `intelligence/runtime/agent_episode.py`。
- **真冲突面只有 `agent_episode.py`**（main 侧 27 hunk / U0 口径 37，本分支 4）。
  另外三个：main 侧各 1 hunk 且与本分支改动区不相交（`app.py` 的那处在
  `create_app`，不碰装配段——已逐个读码核实）。
- rebase 时机是**用户裁定项**，见文末轮次记录的升格事项。

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

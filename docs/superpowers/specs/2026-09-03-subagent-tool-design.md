# 设计：子代理作为模型可点的工具——抄 dsh `tool-subagent` 的形状，账本用我们的

日期：2026-09-03
状态：**设计稿，未实施、未开分支。** 能力放大线交接「下一步 ⑤」。写完先停：§1.3 的前置事实（deep 升档在生产上已归零）
没查清之前，实施了也够不着。
父稿：`2026-09-02-capability-amplification-output-gate-design.md` §3.5.1（两家的子代理都是插件）、§3.5.5（子代理回文本不回证据
这条形状不能原样抄）、§3.6（三条契约缺一不挂）；`docs/handoffs/2026-08-15-dsh-absorption-p0-execution-handoff.md`（现有协调器的来历）。

---

## 0. 一句话

**不新建子代理。** 仓里已经有一台有界、只读、证据进同一账本的子研究协调器（`intelligence/runtime/sub_research.py`），
只是它由 PLAN → deep 升档触发，不是模型能点的工具。本稿把它包成注册表里一个 `ToolSpec`（名 `sub_research`），
形状抄 dsh `tool-subagent`，三条契约自己写；**dsh「成功只回子代理最终文本」那一条不抄**——我们的分支回的是带
hash 的证据，这是比 dsh / knevo 领先的一点，别为了像它而丢掉。

---

## 1. 先看清现状 [实测 2026-09-03，读自 gitea/main `78fb8639` 与生产 users 根 814 个 run]

### 1.1 已有的东西（不用建）

| 件 | 位置 | 现状 |
|---|---|---|
| 协调器 | `runtime/sub_research.py::SubResearchCoordinator` | 最多 **3** 支（`MAX_SUB_RESEARCH_BRANCHES`）、每支 ≤ **8** 次调用 / ≤ **60s**；**同步排空**是写死的承重不变量（docstring 认领，改成后台要重开 spec §4.2.4） |
| 子预算 | `_BranchBudgetView` | 非铸币视图，消耗直接从父 `RootBudgetLedger` 扣；不能 grant / promote |
| 证据 | `services/evidence_ledger.py::BranchEvidenceSink` | 分支只能 append 到父账本，hash 由父账本铸——**§3.5.5 要的「共用父臂账本」已经成立** |
| 结果 | `BranchResult`（evidence / traces / gaps / llm_calls / tool_calls / status ∈ completed·partial·failed） | 领域层按结构声明 `BranchOutcome` Protocol，不 import runtime（层级审计） |
| 呈现 | `FinanceResearchHarness.project_sub_research` → `SUB_RESEARCH_RESULTS` | 分支证据按主 episode 累计的 E 号给模型看 |
| worker | `runtime/continuous_sub_research.py::ContinuousSubResearchWorker` | 分支跑的是同一台 Episode 机器 |

### 1.2 现在怎么触发

模型交 PLAN（含 `branch_goals`）→ `harness.govern_mode(plan, can_branch, …)` → `mode_governor.decide` 批 `deep`
（`reason=observable_complexity_approved`，`max_branches=3`）→ Episode loop `_run_sub_research` 起分支 → `consume_sub_research` 并入。
只有 Episode 接了协调器；`HarnessReferenceLoop` 传 `can_branch=False`（`harness_reference_loop.py:301`），**不能分支**。

### 1.3 生产频次：已归零

814 个 run 里 `mode_decision` 事件 **127** 条：50 条批 deep 并起分支（`branch_started` 150 / `branch_completed` 141 / `branch_failed` 9），
77 条模型自请 quick。批 deep 的全部落在 **08-13 ～ 08-22**；**08-22 之后零 deep、零分支**，此后约 400 个 run 的
`contract.research_tier` 全是 standard。`mode_decision` 只在有 PLAN 的 run 里出现，而 PLAN 自 08-19 起只出现在 3 个 run。

**结论**：升档路径在生产上事实关闭 12 天，协调器休眠。**原因已查清 [实测，同日同代码双模型对照]**：08-17 起生产模型从
`gpt-5.6-terra` 换成 GLM，而 **GLM 几乎不主动交 PLAN**——08-13 gpt 24/80（30%）对 glm-5.2 0/20，08-16 gpt 44/154（29%）对 glm-5.2 0/12；
全量批 deep：gpt 48/417、glm-5.2 2/272、glm-5.3 0/113。PLAN 指令原文自 08-07 一字未动，`46053d3f` 不碰 PLAN——09-03 首版此处对
prompt 重构的 [推断] **撤回**。读数 `docs/verification/2026-09-03-plan-deep-rate-by-model.md`。
交接说「先看 govern_mode 升 deep 频次」，答案是：**GLM 下为零，且是模型行为不是代码**。这决定了本稿的排期（§7）。

### 1.4 dsh `tool-subagent` 的形状（只读 `/Users/a77/deepseek-harness/packages/subagent/tool-subagent/README.md`）

前台调用等 `run.result` 并 `dispose` 后返回，只有 `completed` 算成功；失败把子代理**保留的部分文本**接在停止原因后面（「截断的答案
不报成功也不静默丢」）。后台两态：`one-shot`（登记父方 Task，之后由通用 task 工具查/收/杀）与 `continuable`（子代理拥有自己的
后续轮次，结算通知回父）。`toolFilter` 改子代理的全局工具层但**不是**父方授权上限；`maxDepth` 默认 3，工具在上限处仍可见、
启动时按调用方当前深度拒绝；同一消息里的兄弟委派并行、结果按模型顺序提交；子策略 per instance 固定，换模型/工具过滑/深度
要另起一个不同名的工具。「Success contains only the child's final text.」

---

## 2. 抄什么、不抄什么

| dsh 形状 | 我们的对应 | 决定 | 为什么 |
|---|---|---|---|
| 前台同步调用，只有 completed 算成功 | `sub_research(goals=[…])` 同步返回；协调器本来就同步 | **抄** | 与排空不变量一致；Episode 的 `ToolBatchExecutor` 也是同步授予 |
| 失败保留部分**文本** | 失败保留部分**证据**：`status=partial/failed` 的分支已 append 的证据留在账本，投影里标明该支未完成 | **改写** | 我们的账本单位是证据不是文本；部分证据可绑定，部分文本不能 |
| Success 只回 final text | 回 `SUB_RESEARCH_RESULTS` 投影（E 号），父臂结论句**只能绑分支证据的 hash** | **不抄** | §3.5.5：绑到总结文本进不了 `admit_finish` |
| 后台 one-shot / continuable | 第一版**不做** | 否 | 违反同步排空不变量；standard 90s / deep 240s 的窗里「后台」没有可等的时间；做了就要重开 §4.2.4 与 RuntimeHandle 分支粒度 drain |
| `maxDepth`（默认 3） | 固定 **1**：分支的 registry 不含 `sub_research` | 抄成硬常量 | 60s 一支的预算里嵌套没有意义；且嵌套会让「同步排空」变成递归排空 |
| `toolFilter` | 分支 registry = 父授权集 ∩ 只读工具（现状已如此） | 已有 | 不另做参数 |
| 兄弟并行 | 协调器已并行（ThreadPoolExecutor），结果按 request 顺序取 | 已有 | — |
| 子策略 per instance 固定 | 一个工具名、一个参数 `goals`（≤3，去重，非空） | 抄 | 换策略另起工具名，不塞参数 |

---

## 3. 三条契约（§3.6：缺一不挂）

1. **空结果语义**：分支 `completed` 但零证据 → 投影写「该方向本轮未找到可绑定证据」，是**缺口**不是否定；`failed` 写失败原因
   （`BranchResult.error`）并点明「该支的问题未被研究，不是没有答案」。
2. **来源分档与 `as_of`**：分支证据继承各自工具铸的 `evidence_tier` / `source_date`，**不因经过子代理而升档**；投影里每条证据带
   `branch_id`，判官与 `admit_finish` 看到的与父臂直接调工具拿到的同一形状。
3. **参数含义与拒绝条件**：`goals` 读且只读这一个参数；空 / >3 / 重复 → `ProviderTrace.status=error` 带原因（沿用 `_clean_goals` 的
   `ValueError` 文案），不静默截断；预算装不下（见 §4）→ **不上菜单**而不是上了再拿零授予。

---

## 4. 预算：从哪出、够不够着

- 用户裁决（交接）：**预算从 deep 档出**。`ResearchPolicy.for_tier("deep")` = 12 步 / 240s / reserve 48s，`tool_call_cap` 24。
- standard 档 live 形状（09-03 腾讯题）：派发时 `remaining 83.6 → 授 23.6`，即 reserve 60、研究窗 ~30s；第二轮 `would_grant 0`。
  一支分支上限 60s，**standard 档连一支都装不下**。
- 落法：`ToolSpec.min_window_seconds = MAX_SECONDS_PER_BRANCH`（60）——沿用 #544 的「领域申报、底座裁决」，standard 档下
  `tool_menu` 事件会把 `sub_research` 记进 `hidden`；deep 档首轮窗 ≈ 240 − 48 = 192s，装得下 3 支。
- **因此可达性 = deep 升档可达性**。§1.3 说它现在是零。不修 PLAN/升档，这个工具装上去等于没装——这不是本稿修的东西，
  但是本稿的前置（§7）。
- 不动 90/60/30，不动 deep 240/48（父稿 §6）。

---

## 5. 挂哪条 loop（交接留给 P4 的问题）

工具进注册表后两条 loop 共享 `ResearchToolRegistry` + `ToolBatchExecutor`（父稿 §3.5.1 的论据），**菜单与授予两边一致**；
但 runner 需要协调器 + `evidence_sink_factory`，这两样今天只在 Episode 的装配里（`glm_agent_runtime.py:469-512`），
参考 loop 是 `can_branch=False`。所以：

- 第一版只在 Episode 装配里接 runner；参考 loop 的 registry 里该工具存在但 runner 缺依赖 → 装配期就该拒（第 8 条守门的精神：没源不挂），
  而不是运行时报 `unknown_tool`。
- **这给 P4 的 A/B 加了一个已知不对称**：Episode 能分支、参考 loop 不能。P4 读数的「预算授予差」一栏要把它并列写出，
  否则 deep 题上的 Δ 会被读成 loop 差。

---

## 6. 验收（缺一条不算）

1. 注册表守门：`sub_research` 在 `_TOOL_CONTRACTS` 有条目（§3 三条），缺则装配抛（沿用父稿第 8 条的有牙测试）。
2. 深度 = 1：分支拿到的 `authorized_specs` 不含 `sub_research`；分支里点它 → `tool_hunger` 记 `capability_denied`（有牙：去掉过滤 → 红）。
3. 证据绑定：父臂结论句绑到分支证据 hash 才过 `admit_finish`；构造一条只绑 `SUB_RESEARCH_RESULTS` 文本的结论 → 驳回（有牙）。
4. 预算：三支总耗 ≤ 3 × 60s，父 `remaining_seconds` 单调减且不越 reserve；`_BranchBudgetView.grant()` 仍返回 False。
5. 菜单：standard 档 `tool_menu.hidden` 含 `sub_research`，`min_window_seconds` 记 60；deep 档首轮 visible。
6. 排空：Episode 关闭后无分支线程存活（复用 `test_sub_research.py` 的 `is_alive()` 断言，改成钉协调器返回后）。
7. live：deep 档一题两臂，Episode 臂 `sub_research` 被点、分支证据进 `bindings`；参考臂按 §5 预期为菜单不含该工具。n=1 只断言结构。
8. **前置读数**：PLAN / deep 归零的原因有一手读数（不是本稿修）；没有它，第 7 条跑不出来。

---

## 7. 排期与非目标

- **已做**：§1.3 查清——是模型（GLM 不交 PLAN），不是代码。
- **先拍（用户）**：deep 在 GLM 下怎么可达——a) 治理侧不经 PLAN 按可观察信号升档（`mode_governor` 已有 `observable_conditions`，缺一个
  不依赖 PLAN 的入口）；b) 对复杂题型把 PLAN 从「可以」改成必填；c) 接受 GLM 下 deep 为零、本稿搁置。三条都是协议/预算线级的决定。
  在拍之前实施 §2–§6 等于装一个够不着的工具。
- **然后**：本稿 §2–§6，一张 PR：`ToolSpec` + 契约 + runner（包协调器）+ `min_window_seconds` + 守门测试；零 loop 改动。
- **不做**：后台 / 可续接；嵌套；换 loop；新账本；改任何预算线；在 §1.3 查清前切流。
- **不读成**：「有了子代理就能答 knevo 那类题」——knevo 的 22 次调用赢在 `web_fetch` 与 web 授权（父稿 §1.4），那两样今天已经在
  注册表里（#537、#553）；子代理放大的是并行宽度，不是工具面。

---

## 8. 成立条件

读的树：`gitea/main@78fb8639`（`sub_research.py` 457 行 / `continuous_sub_research.py` 106 行 / `research_harness.py` `BranchOutcome`
`govern_mode` `project_sub_research` / `mode_governor.py` `decide` / `harness_reference_loop.py:301` / `glm_agent_runtime.py:469-512`）。
生产读数：`~/.local/share/finance-workbench/users/*/runs/run_*/continuous-episode.json` 814 份，按 `events[].kind` 与
`contract.research_tier` 计数，一次性脚本未入库（复现：数 `mode_decision` / `branch_started` 按 `run_id` 日期分桶）。
dsh 原文：只读 `/Users/a77/deepseek-harness/packages/subagent/tool-subagent/README.md`（未改动）。
§1.3 的原因 09-03 下午由 [推断] 升为 [实测]（同日双模型对照，`docs/verification/2026-09-03-plan-deep-rate-by-model.md`）；§2–§6 为设计；
§4 的 standard 档窗读数来自 09-03 腾讯题 live（`docs/verification/2026-09-03-web-chain-two-arm-live.md`）。

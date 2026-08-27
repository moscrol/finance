# 设计：Harness 接缝从现有 runtime 收口

- 日期：2026-08-22
- 作者：Grok
- 状态：Draft（对照落地树 `fwp-wt-code-map-land` @ `f4999051`，`code_map.py status` = `ready n=17411`；写在 `docs/harness-learning-seams` ← `gitea/main@dd6ca952`）
- 范围：对照 Continuous Episode **已经接上的缝**，重写该学什么、不该再造什么。不是施工计划，不改生产 loop。
- 父稿：`docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md`（决策记录，停变）
- 同日初稿作废：把「缺 `as_of` 硬拒」写成 L1 增量、把说明书/截止日/fail-closed 当缺口。**以本文为准，禁止按初稿 L1b 施工。**
- 已立项、本文只指针：
  - `2026-08-20-retrieval-tier-by-remaining-budget-design.md`（验真：`kb_rag.select_mode_for_remaining`）
  - `2026-08-17-followup-angle-composer-design.md`（compose 即 `view()`；还开着的是 legacy 默认润色）
- 活状态不写本文：合入 / 谁在做只写 `docs/handoffs/inflight/docs-harness-learning-seams.md` 或 PR。
- 学习源（只读）：`~/harness-reference/distilled/cc-source-reads-cross-check.md`、`context-compaction-five-layers.md`、`sources/claude-code-source-reads/yuker-walkthrough.md`

> 落地物仍叫 **Python Episode 主线**。学插槽形状，焊已有接缝。搬进仓的只能是 Python 薄接线。

---

## 0. 一句话

**Agent = Model + Harness。** 现有 runtime 已经用「合同盖截止日、说明书跟工具走、重复查询 single-flight、格式错误回灌」接上了 CC / dsh 最值钱的几条。还开着的是一扇门、三段动态文本、一层无模型删噪声、一次尺子重跑。不要按 CC 形状再造「模型必须传 `as_of`」。

学的判据：能指出「形状从哪来 / 本仓哪条缝已经在做 / 还剩哪几行要挪 / 哪个数字不准搬」。没学会 = 把已接线的再当缺口。

---

## 1. 本文件是什么 / 不是什么

### 1.1 是

给后续 agent 一张**从 runtime 反推的学习合同**：

1. 哪些失败形状已经挂在符号上，去实施或遵守，别再「发现」；
2. 还开着的缝具体是哪几行，不另起一层；
3. 哪条初稿学法会退步，禁止实施；
4. 信源怎么用（官方裁决数字，泄露走读只给机制词汇）。

### 1.2 不是

- 不是 `scripts/code_map.py` 的替代。编码任务「仓库里有没有现成实现」仍走落地树门面。
- 不是 DSH 吸收第二季，也不是往 08-15 吸收稿上叠一章。那份是已收口的**决策记录**（§12 生产主线保持 Python，08-17 口径已定），正确终态是停止变化。本文是**待办队列**。决策记录 vs 待办队列必须分家——ADR、RFC、迁移计划同一刀。
- 不是把 `~/harness-reference` 抄进本仓。
- 不是实施计划。已立项项走原 spec；本文 L 项另开 `docs/superpowers/plans/`。
- 不是合入状态缓存。能 `rg` 到的符号自己会证伪；PR 号落地当天起就是缓存。

### 1.3 三条铁律

1. **正门压过生成物。** 运行时真身以 `docs/agent-product-door.md` 为准：Workbench 默认 Engine A（`TurnOrchestrator.run_turn` → `continuous_turn_adapter` → `ContinuousAgentEpisode`）。`continuous_glm` 是历史枚举名，适配器 provider-neutral。`sdk_gpt` 在枚举里 ≠ 生产在用。
2. **领域真源不补。** Evidence Ledger、语义 verifier、截止日、技能桥只开 `serenity-alpha`、飞书 Bitable 写入退役。T-E 已判：挂不上 dsh 才对。
3. **资料给形状，量纲自己算。** 87% / 13 000 buffer / 42 工具 / 五层数字 / dsh 包个数一律不搬。同族一致不算交叉验证；数字打架以族 A 官方裁决。

---

## 2. 已经接上（别再当缺口）

只锚符号。`rg` 一下就知道真假。合入状态看 inflight / PR。

| 东西 | 现在在哪 | 误判成缺口时会做错的事 |
|---|---|---|
| 产品壳 | `docs/agent-product-door.md`；`TurnOrchestrator.run_turn`；启动器写死 `AGENT_RUNTIME_BACKEND=continuous_glm` + `ASK_CONTINUOUS_RUNTIME=on` | 复活 `sdk_gpt` 或换壳到 dsh |
| Durable / Live 事件 | `episode_projection.project_durable_events` | 再造第二份事件账本 |
| `ToolPipeline` | `episode_scope.ToolPipeline`：`prepare → authorize → pre_execute → execute → post_execute → project_result` | 再抄一份 TS 流水线 |
| Scope / Handle / Profile | `EpisodeScope` / `RuntimeHandle` / `profile_named("deep-research").execution_policy()` | 把 Profile 再抄成第三份预算 |
| 公开答案唯一投影 | `session_projection.view`；`_gap_answer` / `_generic_gap_answer` 都 `return view(...)` | 再开旁路拼串 |
| 压缩第 1 层 | `tool_result_budget.budget_tool_observation`（episode 已调用） | 从零实现「大结果落盘」 |
| 重复查询 | `query_ledger.executed`（per-key single-flight；同 key 不跑第二遍） | 把 dsh `guard/` 当必须焊的新包 |
| 截止日由合同注入 | `build_episode_input` 带 `information_cutoff` / `latest_data_date` / `date_rule`；`cutoff_resolver` 只收紧取 `min`；`closed_loop_retrieval.filter_future_dated` 执行后滤未来并回灌「不是源里没有」 | 逼模型传 `as_of`，或把盘面工具（空参数表）打成非法调用 |
| 说明书拼进工具 | `ResearchToolRegistry.tool_definitions` 与 `prompt_block` 都拼 `spec.contract`；`_TOOL_CONTRACTS` 覆盖 `_DEFAULT_TOOL_METADATA` 全部 12 个名字；`test_tool_behavior_contract` 逐条钉误读 | 再发明第二套说明书类型；为覆盖率编 NEVER |
| 指令 / 本轮输入已分函数 | `build_episode_instructions` = 宪法 + 题型规则 + hash + 工具表；`build_episode_input` = 本轮 JSON（日期、截止日、契约） | 从零拆 system/user；或说「还没接到 prompt 组装」 |
| 格式滑档回灌 | `EpisodeFinishRejection`：`FORMAT` 回灌、`SUBSTANCE` 留草稿、`INTEGRITY` 硬拒 | 在产出侧再加一道销毁（初稿 L7 当新功能） |
| 追问编排器 | `project_ask_state` + `compose_followups`；`conversation_orchestrator` 与 `generate_answer_spec_followups` 已 `polish=False` | 再写一套追问模板 |
| 检索时间降档 | `kb_rag.select_mode_for_remaining`；夹具 `test_retrieval_tier_by_remaining_budget` | 函数还在树上时再开设计窗 |
| `dsh_stub` | `dsh_stub_runtime` 在；`dsh_stub not in RUNTIME_BACKEND_NAMES` | 把它登记成可切换壳 |
| 技能桥只开一个 | `skill_tools` 只注册 `serenity-alpha` | 把 12 个 skill 全挂上 agent 面 |

Workbench 三条确定性题型仍走引擎 B（`external_market` / `quick_fact` / `dated_market_review`）。「壳已定」指生产默认，不是全仓只有一扇门。

`market_data` / `financial_data` / `mainline_context` 的 `query_scope="episode"`，参数表是 `EMPTY_TOOL_PARAMETERS`。截止日在 context 上，不在模型参数里。

---

## 3. 三层分账

```text
施工（剩一扇门）              还开着的缝（本文 L）              禁止再造
─────────────────────       ──────────────────────────      ────────────
追问 legacy 入口默认关润色    L2 把三段动态文本移出 system     缺 as_of 硬拒（初稿 L1b）
                              L3 无模型删噪声键（精确重复已塌）  换壳到 dsh / 复活 sdk_gpt
                              L4 按当前 dsh HEAD 重跑 T-E      Cordis / 泄露树当依赖
                                                              动态 Plugin Loader
                                                              子研究独立时钟*
```

不开窗、只当纪律：

- **说明书**：新踩到、已验证的失败模式才往 `_TOOL_CONTRACTS` 补一句；空字符串合法；`test_tool_behavior_contract` 故意没有「每个工具必须有契约」。
- **坑类记忆**：`memory_lookup` + `prior_recall` + corrections 已在。强制「先调 memory」被实测证伪。选取偏置先不焊。
- **fail-closed 分层**：已在 `EpisodeFinishRejection`。审查时当回归，不新开模块。
- **工具列表排序**：`authorized_specs` 跟元数据字面序，插入序已稳定。做 L2 时顺手 `sorted(name)` 即可，不单独开窗。

`select_mode_for_remaining` 已在树上，不进施工栏。

\* `_BranchBudgetView` 已规定不铸新预算、消耗记父账本。没有真后台隔离需求，不要为 dsh `jobs/` 去抄。

均分窗口已作废。检索档位：剩余时间 → 档位，不是把窗口调大，不是按工具数切秒。

---

## 4. 施工指针（本文不重写合同）

### 4.1 检索时间降档：走符号

- 稿：`2026-08-20-retrieval-tier-by-remaining-budget-design.md`
- 验真：`kb_rag.select_mode_for_remaining`；夹具 4s → BM25，20s → hybrid
- 生产仍整批 `kb_search` `tool_timeout`：查调用方有没有把剩余秒数传进 `retrieve`，不重开设计。合入史只写 inflight。

### 4.2 还剩一扇门：追问 legacy 入口

- 稿：`2026-08-17-followup-angle-composer-design.md` §13–§14
- 已关：`compose_followups(..., polish=False)` 即 `view()`；连续对话与 AnswerSpec 已关润色
- 还开着：`generate_followups(..., use_llm=True)` 默认开；Workbench `app.py` 对非 `daily` 传 `use_llm=True`（legacy ask s03）
- 做完：`generate_followups` 默认 `use_llm=False`；Workbench 默认不润色；显式打开时 LLM 只改 `label/full_prompt`，不得改 `type` / 条数 / `angle`；失败回退模板

这扇门是实施，不是学习。按 §7 排在 L2 之前单独收。

---

## 5. 还开着的缝

每条六栏：**形状 / 为何 / 挂哪 / 替代 / 禁搬 / 学会了**。信源只写本机已落盘路径。

### L2 提示词静 / 动态分界（主增量）

形状已经有了：宪法在 `build_episode_instructions`，本轮日期与契约在 `build_episode_input`。`test_episode_protocol` 已用 sha256 锁静态措辞。没接完的是 system 末尾仍混了本轮才变的三段。

| 栏 | 合同 |
|---|---|
| 形状 | 一条显式边界：线以上跨请求不变（可进 prompt cache），线以下每轮重建。CC 变量名只借 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY`。 |
| 为何 | 金融 Episode 的截止日纪律已经在 user JSON 里。污染前缀的是 `task_frame_hash`、`registry.prompt_block(...)`、以及估值 / 跟踪 / `prior_recall` / longtail / degraded 等按题变的规则。它们和「始终回答最初任务」写在同一 system 里，前缀一变缓存整段作废。 |
| 挂哪 | `episode_protocol.build_episode_instructions` / `build_episode_input`。宪法留在 system；hash、工具表、题型规则进 user JSON（或 system 里边界注释之后）。组消息处先标边界，再谈 `cache_control`。做这一窗时 `authorized_specs` / `tool_definitions` 可按 name 排序钉死。 |
| 替代 | ① 不分层：实现简单，每轮全价。② 宪法进 system、本轮进 user（本条）。③ 把动态段放回边界之上：缓存变体爆炸。 |
| 禁搬 | 缓存 TTL、Blake2b、87% 阈值、`scope:'global'` 组织级共享。本仓窗口量级与 CC 差几个数量级，照抄阈值会永不触发或永远触发。 |
| 学会了 | 两个不同 `task_frame` 的 system 消息逐字节相同；user JSON 含 hash、可用工具、题型规则、`information_cutoff`；加一条本轮证据只改 user / 后续 tool，不改 system。 |

信源：族 A 官方 prompt-caching（并行请求全价，要等第一个开始流式才可读）；族 B 只借变量名。mal「5 个并行 agent ≈ 1 个价钱」已否。

### L3 压缩第 2 层：无模型删噪声

| 栏 | 合同 |
|---|---|
| 形状 | 五层里第 2 层：低价值内容直接删除、不做摘要。对噪声做摘要浪费 token。 |
| 为何 | 第 1 层已是范本。`query_ledger.executed` 已把**精确重复查询**塌掉（dsh `guard/` 同族，不必再焊）。第 4 层 `_summarize_messages` 已如实自述「这是截尾不是摘要」。第 5 层要 LLM + 熔断器，现在上会把压缩失败变成新的整轮失败。还缺的是不同查询之间的调试字段 / 重复 prose。 |
| 挂哪 | `tool_result_budget.py` 旁边加一层「可删键 / 重复 observation」，在进模型消息之前。对象是 tool result，不是 L2 的静态 system。 |
| 替代 | ① 只做 layer 1：安全，上下文仍会腐化。② 无模型删噪声（本条）。③ LLM 全量 compact：先有连续失败熔断器再谈。 |
| 禁搬 | 87% / 13 000 buffer / 连续 3 次熔断 / 每文件 5 000 token。标识符、`evidence_hashes`、`source_date`、`gaps`、`supports`/`contradicts` 继续永不删（layer 1 红线）。不要把 dsh `compaction-tool-result-pruner` 目录抄进 `intelligence/`。 |
| 学会了 | 有一张「可删 / 必须留」表；夹具证明删的是重复 prose 或调试字段，不是证据身份；发生在两次模型调用之间，不改静态前缀。 |

信源：族 C `ai-agent-book` ch2 + 族 A context-window + 本仓 `distilled/context-compaction-five-layers.md`（已精读）。马书 part3 压缩章仍是「仅见标题」，不得进入本条结论。

### L4 用当前 dsh HEAD 重跑 T-E

这是在**执行**吸收稿 §9.5（pin 变更后须重跑，不得沿用旧三分类），不是改那条规则。执行记录不写回被执行的规则，也不覆写旧观测。

| 栏 | 合同 |
|---|---|
| 形状 | 吸收稿 §9.5：dsh 只量形状、不量分数。 |
| 为何 | stub 仍钉 `PINNED_DSH_COMMIT`（`dsh_stub_runtime`）。2026-08-22 本机 `/Users/a77/deepseek-harness` HEAD 已是 `99f6f02`（0.1.0-rc.7）。尺子旧了，不是产品 loop 缺功能。 |
| 挂哪 | 新开带日期收据 `docs/verification/2026-08-22-dsh-static-shape-audit.md`（或重跑当日日期）；`2026-08-17-dsh-static-shape-audit.md` 文首盖 `superseded by <新路径>`。禁止把新分类写回 08-17 正文，禁止只改 08-17 不留后继。不改 factory、不把 dsh 登记成 backend、不改吸收稿 §9.5。 |
| 替代 | ① 继续用旧表：会把新包误判成「必须补进 Episode」。② 新开收据 + 旧稿 superseded（本条）。③ 把新包当施工单：正是本文件要挡住的。 |
| 禁搬 | 不要把 `guard/` `hooks/` `jobs/` `spill/` 目录抄进 `intelligence/`。`guard/` 的重复工具 → 已有 `query_ledger`；`hooks/` → 本仓 SessionStart 已是事实投递；`spill/` → 接近 layer 1，先不焊。 |
| 学会了 | 新收据仍只分「挂得上 / 只能进 execute / 焊死 / 领域真源」；旧稿一眼能看出作废；新包若只是旧接缝的同族实现，记「学形状、先不焊」。 |

---

## 6. 禁止实施：初稿 L1b（缺 `as_of` 硬拒）

CC「未 Read 不准 Edit」是工具 error，因为编辑器不知道路径。金融查询的截止日是 **Episode 合同**，不是模型参数。

现有链路：

1. `EpisodeScope.authorize` —— 能力在不在（不是日期）
2. `cutoff_resolver` —— 与合同截止日取 `min`，只收紧
3. runner 执行
4. `filter_future_dated` —— 越界证据标注后交还

硬拒已经留给：能力未授权（`UnknownResearchTool` 回灌）、参数不是对象（`InvalidResearchToolArguments`）、`finance_query` 未授权历史窗口（contract 已写，runner 直接退回）。

若按初稿做「查询类没带 `as_of` 就到不了 `execute`」：

- 三只盘面工具参数表为空，会被误伤；
- 模型开始编日期，和「today 不是行情日、截止日由 harness 盖章」对着干；
- 把 fail-closed 用在已经注入截止日的轴上，是退步。

**学会了这条：** 夹具继续锁「越界证据被滤 / 空参数盘面工具能执行」；没有「缺 as_of 拒执行」这条夹具，也不许新加。

---

## 7. 怎么学 Claude Code（信源合同）

法律：2026-03-31 npm 把 `cli.js.map` 打进发布物。能读、能学架构，不能 fork 进产品、不能当 MIT 依赖。Anthropic 仍持有版权。

| 可读 | 路径 | 用法 |
|---|---|---|
| 互校（必读） | `~/harness-reference/distilled/cc-source-reads-cross-check.md` | 引用族 B 之前先读。内部数字会打架。 |
| Yuker 走读 | `~/harness-reference/sources/claude-code-source-reads/yuker-walkthrough.md` | 给路径和片段，本机核对过 |
| 官方精读 | `~/harness-reference/distilled/claude-official-deep-read.md` | 族 A，冲突时以它为准 |
| 压缩五层 | `~/harness-reference/distilled/context-compaction-five-layers.md` | L3 的权威对表 |
| 泄露溯源 | `leak-provenance.md` | 定性：时点是 2026-03，不是今天的 CC |

不要：去 X / gist 再下一遍 source map；把 1906 个 TS 放进本仓；把 Ink TUI、coding 工具、`USER_TYPE=ant` 写进 Episode。`harness-reference` 里没有 `.ts` 树。

可迁移点：先画「通用底座 vs 领域真源」，再用「明天插件挂哪条缝」反推——挂不上且是领域真源，就停手。和 RAG「图谱有边 ≠ 该有这条边」同一刀。

---

## 8. 优先级（只留次序，不留状态）

合入与否、谁在做，写 inflight / PR。本表被 SessionStart 读到的概率低于 inflight；两边一冲突，agent 不会知道听谁的。

1. §4.2 追问 legacy 门
2. L2（题型规则 + hash + 工具表移出 system；排序顺手做）
3. L3
4. L4 可与上面并行（只写收据，不动 loop）

原则：能用已有接缝复现的，绝不上新 runtime；能用 0 档验收的，绝不上 live 四臂。说明书补句跟新失败走，不排队。

---

## 9. 非目标

- 不实现「查询类缺 `as_of` 拒执行」。
- 不把 dsh 登记进 `RUNTIME_BACKEND_NAMES`，不复活 `sdk_gpt` 为生产路径。
- 不把本仓源码交给 Cognition / DeepWiki private index。
- 不把代码地图、本学习稿、能力图谱合成第二份清单。稳定能力只回写 vault 图谱。
- 不在 SessionStart 全量 build CRG。查询继续走 `fwp-wt-code-map-land` 上的 `python3 scripts/code_map.py`。
- 不在本文件改 `intelligence/cli`、不加研究工具。

---

## 10. 已关闭的选择

| 问 | 答 | 出处 |
|---|---|---|
| 要不要把 dsh 当运行臂？ | 否。08-17 起只做静态形状对照。 | 吸收稿 §9.1 |
| SDK 还要不要？ | 枚举与测试留着当可选 Arm C，非必需。 | 吸收稿 §9.1 表 |
| 均分工具窗口？ | 否。已作废。 | remaining-fixes |
| 查询类必须带 `as_of` 否则硬拒？ | **否。会退步。** 截止日由 context 注入。 | §6 |
| 说明书覆盖率开一窗？ | 否。12 个工具已有 `_TOOL_CONTRACTS`；新失败再补。 | §2 / §3 |
| 从 X 拉 CC 源码树？ | 否。 | §7 |
| 压缩直接上第 5 层？ | 否。先 L3，且先有熔断器。 | §5 L3 |
| 子研究独立时钟？ | 除非出现真后台隔离需求。 | §3 |
| 为什么不写回 08-15？ | 决策记录应收口停变；本文是待办队列。 | §1.2 |
| L4 写回 08-17 还是新开？ | 新开日期收据，旧稿文首 `superseded by`。 | §5 L4 |

---

## 11. 验收：什么叫「这份 spec 被遵守」

1. 开窗前先读 §2 与 §3。`select_mode_for_remaining` 还在就不要重开检索档设计。追问门走原 followup spec。
2. 实施 L2 / L3 / L4 时，六栏都能在 PR 描述里各用一句话答出来；PR 不含 CC / dsh 源文件。
3. 没有「缺 as_of 拒执行」的夹具或 `authorize` 分支。出现即打回。
4. 宣称「我们没有 X」之前，先跑落地树 `code_map.py query`，再读 §2。空图不得当结构结论。§2 只信符号。
5. 引用压缩层数、工具个数、缓存阈值时，能指到族 A 或本仓实测；不能只引 Yuker / mal 的数。
6. 活状态只改 inflight / PR，不改 §8。

回滚：删本文即可。它没有接线，不改行为。

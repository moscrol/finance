# 市场路由入口修复 — 交接（2026-08-09）

> **读法**：§1 是本轮做完的事与实测读数；§2 是**三条被推翻的前提**（我上一轮说错、这轮查实纠正的），
> 后续任何人接手前先读它，否则会去"补"已经存在的东西；§3 是消融实验的全局盘子与本轮占的那一 part；
> §4 是剩余 part 的交接口径与开工判据；§5 是原「等用户拍板」两项的落地结果
> （含两处对本文件上一版断言的纠正）。
>
> 分支 `fix/market-routing-default`，6 个提交（含本文件），**已 FF 合入 `main` 并推送**
> （`b93e4a00..6894e981`，2026-08-09 用户确认）。§5 的两项待办均已落地，见该节。

---

## 0. 一句话

消融实验（episode 接缝阶梯 S0-S3）上一轮已经能跑，但它暴露出**阶梯之前那一层就漏**：
一道自然问法的盘面题拿不到行情工具授权。本轮修的是这个入口，并顺带纠正了我自己三条错误判断。

---

## 1. 本轮交付

### 1.1 六个提交（第 6 个是本文件）

| commit | 内容 |
|---|---|
| `300cbed6` | `is_current_market_query` 拆开时间/主体信号，补齐当日盘面判定的四条入口 |
| `245db33e` | 显式日期正则收成 `task_frame.has_explicit_date` 单一来源 |
| `2279aff4` | 补 6 条断言钉住"首轮向 synthesis reserve 借余量"的算术 |
| `871eb48d` | 给 `financial_data` / `memory_lookup` 补行为契约 |
| `3a69ad33` | 验证文档 `docs/verification/2026-08-09-market-routing-default.md` |

另：上一轮 `test/episode-seam-ladder` 的 6 个提交已在主 worktree fast-forward 合入 `main`
（无分叉，与主树 37 个他人未提交改动**零文件交集**，已核对）。

### 1.2 主结果：授权面可达率 10/18 → 18/18

`is_current_market_query` 原本是单条 `has_time AND has_subject`。改为四条入口：

1. 时间词 + 主体词（原有）
2. **显式日期** + 主体词 —— 复用 `task_frame.has_explicit_date`
3. **现状判断词** + 主体词（"强不强"/"什么位置"/"处于"）
4. **盘面度量词**独立成立（"涨停家数"/"多少钱"/"收盘"）

历史词从"无条件否决"改为"仅当无任何当期时间信号时否决"——今昔对比题
（"最近行情和2024年哪段像"）同时需要当日盘面与历史区间。

修掉的漏判中最能说明词表质量的是 **"今天板块表现如何"**：旧时间词表九个词，
恰好漏掉最常用的"今天"。对比 finance-mode T2 的「最近/现在/今天/最新/近期/这两天」，
旧表确实更差。

同时修掉一处**过度触发**：旧表把「主线/盘面/成交/涨停」同时放进时间词表与主体词表，
AND 对这五个词退化为单词命中，"如何判断主线候选和噪音"这种纯方法题被拖进行情数据。

### 1.3 一个靠 bug 通过的既有测试

`test_comparative_mainline_decision_overrides_single_theme_defaults`
（"低空经济和商业航天，未来一个月哪个更可能成为A股主线"）原先能过，
是因为"主线"同时在两张表里造成的退化命中。拆表后它掉了。

**它的期望是对的**（判断未来主线必须以当前结构为基线），缺的信号是**前瞻时间词**
而不是"主线"这个词。补 `_FORWARD_TIME_MARKERS` 修好，未改测试期望。

### 1.4 测试

| 范围 | 结果 |
|---|---|
| 18 条自然问法（新增，含 5 条必须保持 False 的知识题） | 24 passed |
| 我改动的模块聚焦回归 | 239 passed |
| episode 接缝阶梯 | 44 passed |
| 工具契约 + 协议 | 176 passed |
| 全量（正确解释器） | 3971 passed / 13 failed |

**13 个失败全部落在本轮未触及的模块**（`test_subconscious` / `test_userspace` 等）。
其中 11 个已用 `git checkout HEAD~1 --` 回退我的文件后复跑，**无我的改动时同样失败**，
确认既有；剩余 2 个未逐个隔离，但同样不在改动面内。

⚠ **解释器**：必须用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
用宿主 `python3` 会报一串 `ModuleNotFoundError`（fastapi/agents/duckdb），是**假失败**。
`AGENTS.md:67` 已有此说明，本轮未重复添加。

### 1.5 顺带产出（非本仓）

| 文件 | 说明 |
|---|---|
| `agent-memory/60_dialogues/knevo/2026-08-08-工具编排与step上限-44轮原文.md` | 44 轮问答 / 110 次工具调用（input+output 全留），非蒸馏 |
| `agent-memory/60_dialogues/knevo/2026-08-08-白酒图谱实体缺失-单轮原文.md` | 同上，单轮 |
| `agent-memory/10_knowledge/judgment-distillation-six-rules.md` | 判断沉淀 6 条规则 |

规则未写进 `30_conventions/`：那是受保护区，`trust-boundary.md` 明文禁止自动流程直接改写。
`vault_lint.py` 已跑，我的文件未被点名（2 个既有 ERROR 在 08-08 被 auto-sync 提交的
两份 knevo 文档里，缺 `source` 字段，与本轮无关）。

---

## 2. 三条被推翻的前提（接手前必读）

这三条都是我上一轮的判断，本轮按负面断言规矩逐条搜实后**证伪**。
**不要再按旧结论去动手。**

### 2.1 关键词表不是掐掉工具授权的闸门 —— 是两道闸门

| | 管什么 | 关键词 miss 时 |
|---|---|---|
| `evidence_capabilities._CURRENT_*` | **验收底线** `mandatory` | mandatory 变空，但**授权面仍含 `market_data`** |
| `query_understanding._MARKET_WATCH_RE` | **工具授权** `question_type` | 判成 `general_finance_qa`，floor 仅 `kb_search`/`web_search` |

S1 那道题（"以 2026-08-07 收盘为准，A股整体市场处于什么状态"）真正的失败点在**第二道**。
我上一轮把两道混成一道。本轮修的是第一道（能力层，波及面 4 处），
**第二道那条约 900 字符的单体正则一字未动**——它在题型分类层，波及
`turn_control_core` / `episode_factory` / `conversation_orchestrator`。

### 2.2 turn 边界预算检查与首轮饿死补丁，**都已在生产**

- 循环本身就在轮次边界求值预算：`agent_episode.py:467`（`should_finalize` 那组条件）
- 首轮借用已实现：`_opening_planning_timeout`，注释带 run 8792 的实测数字
  （effective 80s → reserve 53.33s → 首轮仅 26.67s，低于 provider P50 28s，
  三个 run 全 `TimeoutError` → 零 binding → 模板答案；借入后 60s ≥ P95 50s）

我上一轮提议"去验证 turn 边界检查"——那是既有实现。**真正缺的是这段算术零测试覆盖**：
全仓仅 1 处测试碰到 `retrieval_deadline_closed`，函数名与常量名一次未被断言。
本轮补 6 条不变量断言（`2279aff4`）。

**这条注释同时记录了一个已被证伪的做法**：在 prompt 里写"必须优先调用 memory_lookup"无效，
模型仍把预算全投市场侧；管用的是**收窄该槽位的 `evidence_types`**。
→ 任何"入口硬导"的方案必须做成**结构收窄**，不要做成祈使句。

### 2.3 `output_review` 已经接线，只是不覆盖 Engine A

我上一轮说"写好但没接"，错在只搜了 `from ... import` 一种写法。实际：

- 接线点 `ask.py:4135`，6 项检查（数据新鲜度/证据分层/反证/缺口/可验证假设/弱证据硬写）
- WARN 会**回灌做一轮定向修订**（`llm_refine.gate_revision_user_content`）

**真实缺口**：它只在 Engine B 路径上。continuous episode 走 `_complete_continuous_turn`
提前 return——这一点 `_continuous_answer_coverage` 的 docstring 自己写明了：
「Engine A reaches its terminal report through `_complete_continuous_turn`,
which returns before the orchestrator's `task_fulfillment` gate」。

---

## 3. 消融实验的全局盘子与本轮的 part

### 3.1 总目标（出自 `docs/superpowers/specs/2026-08-09-episode-seam-ladder-design.md`）

逐层接入 episode 运行时的组件，定位是哪一层引入失败或异常行为。
**硬约束不是"能力越多答案越好"**（质量单调性由既有 A/B 与 28 题验收另行判断），
而是：某一阶不得暴露未开放工具、不得绕过 verifier、不得因新 capability 使固定控制链路异常。

| stage | 新增能力 | 模式 | 通过含义 |
|---|---|---|---|
| S0 `planning` | 无 | 不构造 runtime | 路由/TaskFrame/contract/allowlist 可冻结 |
| S1 `market-data` | `market_data` | offline + live | 模型只见结构化行情，能闭合市场事实绑定 |
| S2 `mainline-context` | + `mainline_context` | offline | schema/授权/tool loop/binding/verifier 仍闭合 |
| S3 `causal-evidence` | + `news_search` + `evidence_search` | offline + live | 可达 public answer；空结果合法，接口断裂非法 |

stage floor **不是主观分配**，由 `ResearchTaskContract.__post_init__` 的
`mandatory ⊆ allowed` 不变量推导：`market_forecast` 是唯一强制底盘恰为单个
`market_data` 的市场题型，所以 S1 只能用它。**换题面前必须重跑 floor 表，不要只改字符串。**

### 3.2 进度盘

| part | 状态 | 落点 |
|---|---|---|
| **P1** 阶梯输入与 stage 面冻结 | ✅ 上一轮 | `episode_seam_ladder_cases.json`、Stage/SeamLadderCase |
| **P2** stage 作用域的契约与 registry 派生 | ✅ 上一轮 | `stage_derivation`，每级独立 context + 唯一 task_id |
| **P3** 离线真回路与 receipt | ✅ 上一轮 | `run_offline_stage_case`，脚本模型 + 固定数据源 |
| **P4** opt-in live 模式与 preflight | ✅ 上一轮 | `--live` + `live_preflight` |
| **P5** 离线回归门 | ✅ 上一轮 | 44 条断言，全绿 |
| **P6 阶梯之前那一层：入口路由** | ✅ **本轮** | 本文 §1.2，10/18 → 18/18 |
| **P7** live smoke 实跑 | ❌ **未执行** | 三项 preflight 均不满足（环境事实，非代码回归） |
| **P8** 断言从"选对工具"扩到"防犯错" | ⚠ **部分** | 本轮补了 2 条工具契约；阶梯断言未扩 |
| **P9** 题型分类层（`_MARKET_WATCH_RE`） | ❌ 未动 | 见 §2.1 |

**本轮做的是 P6，外加 P8 的一小部分。** P6 不在原始规格里——它是阶梯跑起来之后
才暴露出的上游缺陷：阶梯能测"某一阶能不能闭合"，但测不出"这道题压根没被授权行情工具"。

---

## 4. 剩余 part 的交接口径

### P7 · live smoke 实跑（优先级最高，唯一还没有真实证据的一环）

**为什么重要**：P1-P6 全部是离线读数。离线用脚本模型 + 固定数据源，
证明的是"接线闭合"，不是"真 provider 下闭合"。

**三项 preflight 缺一不可**（上一轮实测均不满足）：
1. LLM provider 未解析到（需要生产 relay 的已解析 provider/model）
2. continuous mode 未开启
3. 无 `2026-08-07` 的市场快照

**命令**（`--live` 是 opt-in，默认永不碰真 provider）：
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/run_episode_seam_ladder.py --live
```

**完成判据**（人工查 receipt，出自规格 §7.2）：
- S1 的 schema **不出现** `mainline_context` / `news_search` / `evidence_search`
- S3 的 tool calls 与 evidence hashes 确有已开放能力
- 生产 semantic verifier 为 `passed` 或 `repaired`

**注意**：live 不能作为 CI 或 merge gate。relay P95 约 50s、完整 episode 需多次模型调用，
provider 延迟与预算耗尽都是外部变量。跑失败先按 §2.2 的预算级联查，不要先怀疑模型能力。

### P8 · 断言扩到"防犯错"

**依据**：knevo 自己做过一次消融（原文轮次 26），把 finance-mode 摘掉只留工具 schema
重构 function calling，结论是**工具选择与参数构造完全一致**，丢掉的只有三层：
策略性指令、数据陷阱警告、输出骨架纪律。

→ **只测"能不能选对工具"的阶梯层，大概率看不到差异。** 这可能正是我们阶梯跑得那么顺的原因。

本轮已做：补 `financial_data`（累计口径，中报=H1/三季报=前三季累计，不做单季还原）
与 `memory_lookup`（用户历史先验，不是市场事实、不能当证据引用）两条契约。

**剩下的**：
- 12 个工具目前只有 6 个有契约（`market_data` / `l3_lookup` / `web_search` / `news_search` + 本轮 2 条）。
  补契约必须遵守 `_TOOL_CONTRACTS` 表头纪律：**只写验证过的，编一句比不写更糟**。
- 阶梯断言扩三类程序化检查：EOD 当现价、季报口径当当前、实时数字缺 as_of。
  注意 EOD 与空结果**已有工具契约覆盖**（§2.3 的 harness/skill 分界里属"硬"那半），
  要加的是**出口侧程序检查**，不是重复写提示词。

### P9 · 题型分类层（`_MARKET_WATCH_RE`）

**先不要动。** 理由：本轮在能力层已拿到 18/18，收益已兑现；而那条正则在分类层，
改它必须跑 `turn_control_core` / `episode_factory` / `conversation_orchestrator` 全回归。

**若要动，方向已定**（详见验证文档）：不是继续枚举短语，而是**翻转默认**——
授权面按题型语义放宽 + 豁免白名单，`mandatory` 保持窄而准。依据是一条不对称性：

> **授权 ≠ 调用。** 放宽授权面几乎免费（选哪个工具仍是模型自主的），
> 真正花预算的是 `mandatory`。而且放宽 `allowed` **永远不会触发**
> `mandatory ⊆ allowed` 这条不变量，收紧才会。改动方向与不变量同向。

### P10 · Engine A 的出口闸门（新增，本轮发现）

把 `output_review` 的 6 项检查接进 continuous episode 路径。
现状见 §2.3——Engine A 全靠"一次性写对"，没有第二道防线。
这恰好是 knevo 自评"你们的错误捕获率会比我高一个数量级"的那道防线，
而我们在主研究路径上还没有它。

---

## 5. 原「等用户拍板」两项 — 均已落地（2026-08-09）

### 5.1 合并与推送：已完成

`fix/market-routing-default` 的 6 个提交已 FF 合入 `main` 并推送
（`b93e4a00..6894e981`）。合并前核对：与主树 37 个他人未提交改动**零文件交集**，
合并后复查那 37 个文件仍在、未受影响。

⚠ 同一次 push 带上了 `main` 上**之前会话遗留的 23 个未推提交**（作者同为
`linxiaoqi5111-del`）。它们此前已在 `main`，不是本轮引入；推 `main` 必然一并推送。
接手人若在 `origin/main` 看到 08-09 之前的历史突然出现，是这个原因。

### 5.2 `agent-memory` auto-sync：根因与原判断都不同，已修

**先纠正本文件上一版的两处错误断言**：

1. ❌「两份 knevo 原文已推到 `origin/main`」——**没有**。实测两个提交
   （`b50db773` / `5144c1f1`）当时只在本地。
2. ❌ 把问题定义成"要不要排除 `60_dialogues/`"——排除只是止血，**不是根因**。

真实根因：脚本硬编码 `pull/push origin main`，但 vault worktree 的 HEAD 当时在
`docs/session-tutor-first-principles`。于是每 180 秒把 feature 分支的 325 个提交
逐个 rebase 到 `origin/main`，撞 `20_projects/finance-workspace-private.md` 冲突
→ abort → 退出。**launchd 日志里这个错误 10770 次，最早 2026-06-29。**
而 `git push origin main` 推的是本地 `main` 而非当前 HEAD，所以它从机制上
永远不可能把 feature 分支的提交推上去——这解释了原文为何 commit 了却没到远端。

已做三件事：

| 动作 | 位置 |
|---|---|
| 分支守卫：HEAD 非 `main` 就干净跳过（exit 0） | `~/bin/agent-memory-sync.sh` |
| pathspec 排除 `60_dialogues`（新增/修改不再搭车） | 同上，`EXCLUDES=(':!60_dialogues')` |
| `.gitignore` 补 `*.sqlite*` / `*.db` / `*.duckdb` | vault `main`（`90cfce34`） |

两条路都实测：feature 分支 `[skip]` exit 0；真 `main` `Already up to date` exit 0。

**vault 的内容搬迁另按四档做完，8 个提交已推**（`830485c0..20a4e172`）：
工具链 3 个文件、`10_knowledge` 11 条、`70_tutor` 5 份（用户批准，补 `reviewed_at`）、
`30_conventions` 2 份、`20_projects` 3 份（含一次三方合并，`main` 原有 216 行零缺失）。
验收 `vault_lint` 115 passed / `graph_audit` 39 条无漂移。

仍**刻意留在 feature 分支**、未进共享历史：`.foresight/**` 604 个运行时台账、
3 份 `workbench.sqlite3`、`60_dialogues/` 459KB 原文、`可证伪点回检/` 8 个
（该目录不在 `frontmatter-spec.md` 的 8 个法定 type 内且无 frontmatter，
待定：给法定 type 或认定为派生产物不进 git）。

⚠ 该脚本仍用 `git add -A`（已带 pathspec 排除），与本仓 `AGENTS.md:74` 的
"禁用 `git add -A`"纪律相反。在 vault 里风险低（单人单树），但若 vault 以后
也出现多 agent 并写，这会是同一类事故源。

---

## 6. 可迁移原则（本轮唯一值得记进方法论的一条）

> **输入侧的闸门放宽，输出侧的闸门收紧。**
> 输入侧宽的代价有界（浪费预算，看得见、有上限）；
> 输出侧宽的代价无界（错答案带着自信发出去，且看起来是完整的）。

在开放输入空间上做精确匹配的闸门一定会漏——中文问"大盘怎么样"的说法是开放集合，
枚举永远追不上。这条在 RAG 召回策略、权限系统、内容审核上同样成立。

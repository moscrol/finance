# 设计：能力开关板（并列原子开关 + 独立消融）

- 日期：2026-08-22
- 状态：Draft（只落本文；本树 `docs/capability-switchboard` ← `gitea/main@4e0c6bf5`）
- 作者：Grok（会话 2026-08-22：dsh / Agent Plugins / 消融 / S0–S3 / Profile）
- 复核：2026-08-22 对着 `4e0c6bf5` 逐条实测 §3，改掉三处会让第 0–3 步「全绿却什么都没证明」的判据（正控/负控、`default-v1` 到底冻什么、核验的 off 走哪条缝）。改动就地写进各节，不另立修订段。
- 范围：把已有接缝收成**并列可开关的原子能力**，用独立 runner 做「默认盒 ± 一颗」消融。不改生产默认配置，不合 `main`，除非用户确认。
- 父稿：
  - `2026-08-15-agent-base-dsh-absorption-design.md` §7.2 EpisodeScope、§7.5 ResearchProfile、§7.7 先 Protocol+Profile、不上 Plugin Loader
  - `2026-08-09-episode-seam-ladder-design.md`（楼梯：探地板，必须包含）
  - `2026-08-17-followup-angle-composer-design.md` §13–§14（可卸 = NullComposer；挂得上才算形状可移植）
  - `2026-08-22-harness-seams-to-learn-design.md`（已接线别再当缺口；动态 Plugin Loader 禁止再造）
  - `2026-08-22-domain-predicate-coupling-design.md`（领域口径原件+复印件；与开关板正交，不进 `default-v1` 工具名单）
- 活状态不写本文：合入 / 谁在做只写 `docs/handoffs/inflight/docs-capability-switchboard.md`（尚未建）。

> 本文不是施工计划。第 0 步可以只落表和测试、不动 loop。实施另开 `docs/superpowers/plans/`。

---

## 0. 一句话

**可开关就是可插拔。** 后面不砌更高的 S4，也不把工具名单抄进 Profile。新增一张**开关板**：零件并列；几份命名默认盒并列；S0–S3 梯子只探地板。实验在独立树、scripted 模型上跑；默认盒冻结之前，生产一行不改。

判别变量：`default-v1 ⊕ 一个差量` → 闭环还在不在。不是「越多能力答案越好」，不是「后一级必须包含前一级」。

---

## 1. 范围

### 1.1 做

- 登记已有接缝上的原子能力：每行一个 id、**全部**关法（一颗可能有两处门，见 §5.2 `l3_lookup`）、关了谁还跑、拧了哪个字段必须变。
- 从源码生成冻结默认盒 `default-v1`（**授权面的派生函数符号 + 非工具行默认值**，不是一份工具名单，见 §5.3），禁止手抄。
- 新建独立 runner（名字暂定 `scripts/run_capability_switchboard.py`），与梯子、28 题、`run_agent_episode_ab.py` 分家。
- 离线证明：每颗能关（**正控：`offered_schemas` 差集恰好一颗；负控：硬调被拒**）；一次只拧一颗；能挂一颗零行为零件且 loop 图不变。
- 收据能 dump 完整拨法 + 该次 `resolved_capabilities`；未知 id fail closed。

### 1.2 不做

- 不改 `gitea/main` 生产默认 Profile / 合同 / Workbench 入口。
- 不把 `allowed_tools` 写进 `ResearchProfile`（§7.5 已偏离：权威在 contract，再抄会漂）。
- 不上 Cordis、动态 Plugin Loader、npm 行。
- 不往梯子加 S4/S5，不把梯子和开关板跑进同一份 artifact。
- 不改 28 题验收、不把质量 A/B 塞进本 runner。
- 不在第一期跑 live relay / 28 题。
- 不把 Evidence Ledger、截止日、`layer_audit` 方向、技能桥扩注册做成可并排两本的开关。
- 不把 `feat/reading-rules-baseline-batch1` 的脏树当底。`reading_baseline.py` **不在** `4e0c6bf5` 上，第一期清单标「他树候选」，不假装已接线。

---

## 2. 术语

| 词 | 含义 |
|---|---|
| **底盘** | 一集 Episode 能开始、能停、能出收据。不管对错，先跑完、不夹带、截止日对得上。符号：`ContinuousTurnAdapter` → `ContinuousAgentEpisode`。 |
| **原子 / 零件** | 一拧只动一件事。关了底盘仍跑完。 |
| **开关** | 零件的 on/off。实验臂拧它。 |
| **插拔** | 同一条缝：先关着挂上，过了再写进默认盒。 |
| **开关板** | 机器可读登记表。每行一个 id。认不出的名字失败。 |
| **默认盒 `default-v1`** | 从源码生成的一排拨法：**授权面的派生函数符号** + 已接线的非工具开关默认值。**不是**一份冻结的工具名单——本仓的授权面逐 frame 解算（§3 / §5.3）。 |
| **差量** | 相对默认盒只改一颗。`{id: off}` 或 `{id: on}`。同一 run 两个差量，runner 拒跑。 |
| **模式盒 Profile** | `quick-research` / `deep-research` 等信封：钟、后端、档位。盒与盒并列，**不是**楼梯上一档。 |
| **楼梯** | S0⊂S1⊂S2⊂S3。探「这题最低开到哪」。包含关系只在这里成立。 |
| **焊点** | 关不掉、关了崩、或一拧动三件事。进清单但标 `welded`，不进第一期实验臂。 |
| **开着单槽** | 开着时这一集只能有一个（路由结果、截止日、账本）。能整段跳过做消融；不能两个都写还当一次 run。 |
| **结构棘轮** | 新零件只能登记成开关再挂；不能往 `agent_episode` 加产品 `if`。基线从源码生成，只减不增。 |
| **质量棘轮** | 进默认盒必须对照冻结盒；实验臂可以乱拨，默认盒不动，除非用户确认。 |
| **正控 / 负控** | 正控＝拧了**必须变**的那个收据字段；负控＝关掉后**硬去调它**、必须被拒。两个都没有，「全绿」只等于「没崩」。 |
| **解算面 `resolved_capabilities`** | 本 case 本次实际解出来的授权面。授权面逐 frame 算（§3），差量作用在它上面，不作用在一张静态名单上。 |

人话：楼梯是探最低配置；开关板是并排的电源键；Profile 是预先拨好的一排键，取了个名字。

**定位（别误读）：这是消融夹具，不是运行期 feature flag。** 所有拧动都发生在 runner 的 composition root，生产路径永远不读开关板；`default-v1` 是对生产的**描述**，不是**控制**。改 `default-v1` 不会改线上任何行为——要动线上仍然是改生产代码 + 用户确认。

---

## 3. 已核实事实（实施时不要再探一遍）

底：本树 `4e0c6bf5`（`gitea/main` 于 2026-08-22 fetch）。

| 事实 | 符号 / 位置 | 对开关板的含义 |
|---|---|---|
| 工具能力面已是白名单 | `ResearchTaskContract.allowed_capabilities`；mandatory 必须是子集否则构造失败 | 12 个 capability 已是开关，关法 = 从元组拿掉 |
| Scope 从合同派生，能 dump | `EpisodeScope.allowed_capabilities` / `dump()` | 收据已有能力面；开关板要**并上**非工具开关，不要另造第二份工具名单 |
| Profile 是信封，工具名单故意为空 | `research_profile.py`：`allowed_tools=None`，`source=contract`；`override` 是字段合并不是整行替换 | Profile 最多以后存**开关盒名字**，不存工具列表 |
| 生产入口只接到预算 | `app.py`：`profile_named("deep-research").execution_policy()` | 换 Profile ≠ 换零件面 |
| 梯子唯一变量是能力面，且必须包含 | `run_episode_seam_ladder.py`；`test_episode_seam_ladder.py` | 梯子留下；开关板**禁止**复用「后级 ⊂ 前级」 |
| S3 一次加两件 | `news_search` + `evidence_search` | 梯子不够原子；开关板必须拆开 |
| 12 个 capability（名=工具名） | `_DEFAULT_TOOL_METADATA` / `DEFAULT_RESEARCH_CAPABILITIES` | 见 §5.1 种子 |
| 追问已可卸 | `followups.NullComposer`；`FINANCE_FOLLOWUPS`；生产 `polish=False` | 非工具开关的样板 |
| 核验的 off 是**构造注入** | `ContinuousTurnAdapter.__init__`：`semantic_verifier`（`:147`，`:173` 校验 `.verify` 可调用）、`structural_verifier`（`:157`，默认 `verify_episode_outcome`）都是构造参数 | 干净的 composition-root 缝；§6.2「复用生产 composition root 再收窄」就走它 |
| 过期 deadline **不是** skip，是 abort | `continuous_turn_adapter.py:731-732` `raise TimeoutError`；`:94` 注释写明这条走 `model_unavailable`。测试 `:2362` 断言的是「verifier 没被调用」，不是「跳过后底盘跑完」 | ⚠ 拿它当 off 会拿到降级/中止的一集 → 把 `semantic-verifier` 误标 `welded` |
| structural 结果被修复链消费 | `continuous_turn_adapter.py:600-712`：`_repair_snapshot` / `_issue_backfill_plan` 都读 `structural` | 它是**行为耦合**焊点，不是构造焊点；读代码即可定，不必跑实验 |
| 判读基线不在本底 | 本树无 `reading_baseline.py`（在 `feat/reading-rules-baseline-batch1`） | 标 `pending-other-branch` |
| 技能桥只开一个是设计 | `skill_tools` 只注册 `serenity-alpha` | 不把其余 skill 当缺口补进开关板默认盒 |
| 动态加载器已否决 | 吸收稿 §7.7；harness-seams 2026-08-22「禁止再造」 | 本单不翻案 |
| 授权面**逐 frame 解算**，不是一排常量 | `episode_factory.py:499-517`：`_authorized_capabilities` → `runtime_capabilities_for_frame(frame)`，`evidence_plan.mandatory_capabilities` 再往里追加；`_is_evidence_free_task`（`:468` / `:500-509`）把 `authorized` 整个清空 | `default-v1` 冻不了「授权名单」，只能冻**派生函数符号**；见 §5.3。选题也受限，见 §6.3 |
| scripted 模型只调**被递给它的** schema | `run_episode_seam_ladder.py:556-570`（`for definition in tools` 逐个造 call）；`offered_schemas` 已在 `:539` 记录 | 关一颗 → 该 schema 不出现 → 模型不会去调 → `unauthorized_invocations=[]` **在离线臂恒真**。第 1 步必须加正控/负控 |
| 未授权工具已有现成拒绝路径 | `agent_episode.py:402` `unknown_or_unauthorized_tool` | 负控直接断言这条，不用新写拒绝逻辑 |
| capability 之外还有 env 级门 | `l3_evidence.py:63` `FINANCE_L3_LOOKUP_ENABLED`（`:158` 的提示文案指向 `ask --l3-lookup`） | `l3_lookup` 一颗两处关法；不登记就会「表说 on、实际 off」 |

---

## 4. 四层各管各的（不要压成一个 mode）

```text
楼梯 S0–S3          探地板：这题最低开到哪     必须包含
开关板（本单）       零件 on/off，并列          一次一颗
Profile             钟 / 后端 / 档位信封       盒与盒并列
mode_governor       问题有多绕、给多少秒       不是开不开 news_search
select_mode_for_remaining
                    同一颗 kb_search 内降档    不是新零件
```

换 Profile 不改变开关板差量。开关板差量不改 `grounded_deep` 秒数。梯子 runner 与开关板 runner **禁止**写进同一 JSON。

`ResearchProfile` 以后若要指向开关板，只加可选字段 `switch_set: "default-v1"`（名字），不复制 `allowed_tools`。本单第一期**不改** Profile dataclass，避免和合同抢权威。

---

## 5. 开关板合同

### 5.1 一行一条

机器可读（建议 `intelligence/eval/fixtures/capability_switchboard.json`，实施时再落）。字段：

| 字段 | 必填 | 含义 |
|---|---|---|
| `id` | 是 | 稳定 kebab-case。改语义换新 id，旧的 `status=retired` |
| `kind` | 是 | **是什么**：`capability` / `composer` / `verifier` / `prompt` |
| `status` | 是 | **现在什么状态**：`active` / `welded` / `pending-other-branch` / `retired` |
| `seam` | 是 | 反引号 spec：`path::symbol`，与能力图谱同口径 |
| `close_via` | 是 | 怎么关（从 `allowed_capabilities` 删除 / 构造注入 Null 实现 / env）。**一行可以有多个关法，必须全列**——漏一个就会「表说 on、实际 off」 |
| `default` | 是 | `on` / `off` / `ambient`（跟生产合同走，不在本表写死授权名单） |
| `singleton_when_on` | 是 | 开着是否单槽 |
| `chassis_survives` | 是 | 关了底盘是否仍应跑完。`false` = 焊点 |
| `positive_control` | 是 | 拧了**必须变**的那个收据字段（如 `offered_schemas`、`judge_status`）。填不出来 = 这一行还不可观测，只登记、不进实验臂 |
| `notes` | 否 | 一句限定 |

两处字段动过（这张表是给下一个 agent 机器读的，歧义要在落表前消掉）：

- 原稿 `close`（怎么关）/ `closes`（关了活不活）差一个字母、含义相反 → `close_via` / `chassis_survives`。
- 原稿 `kind` 把类型和状态混在一个枚举里（`verifier` 和 `welded` 并列），焊住的 verifier 会丢掉「它是个 verifier」→ 拆成 `kind` + `status`。

**`id` 只增不改名。** 未知 id → 构造失败，不准静默忽略。

### 5.2 本底种子（`4e0c6bf5`，实施第 0 步逐条用 `rg` 核 seam）

**capability（关 = 从 `allowed_capabilities` 拿掉）：**

`market_data` / `financial_data` / `mainline_context` / `finance_query` / `kb_search` / `evidence_search` / `evidence_lookup` / `news_search` / `web_search` / `graph_lookup` / `l3_lookup` / `memory_lookup`

默认：`ambient`（以该题生产合同为准，不在开关板发明第二份「生产开哪些」）。每次 run 的收据记该次 `resolved_capabilities`，见 §5.3。

⚠ `l3_lookup` 是**两处关法**：capability 要在授权面里，且 env `FINANCE_L3_LOOKUP_ENABLED` 要开（`l3_evidence.py:63`）。这一行 `close_via` 必须两处都写，第 0 步加一条断言：env 关着时不许把它记成 `on`。其余 11 颗第 0 步逐个 `rg` 确认没有第二道 env 门，确认结果写进 `notes`——这就是 §9-C 拒绝的「第二份名单会漂」，只是漂在 env 侧。

**非工具（已有或接近有缝）：**

| id | kind | status | `close_via`（符号已核，`4e0c6bf5`） | default | `positive_control` |
|---|---|---|---|---|---|
| `followup-composer` | composer | active | `followups.active_composer()` 落到 `NullComposer`；等价写法 env `FINANCE_FOLLOWUPS=0`（`followups.py:126` 是同一个开关，不是两件事） | on（芯片仍出；`polish` 是另一维，生产已 `False`，`conversation_orchestrator.py:3896`） | 追问芯片数 |
| `semantic-verifier` | verifier | active | 构造注入：`ContinuousTurnAdapter(semantic_verifier=<null 实现>)`（`:147`）。**不走 deadline**（§3：那是 abort），**不**卸掉判据另写一本 | on | `judge_status` 缺位 |
| `structural-verifier` | verifier | **welded** | 构造上可注入（`:157` kwarg），但修复/backfill 链读它的返回值（`:600-712`）→ 行为耦合，第一期不进实验臂 | on | —— |
| `noop-prompt` | prompt | active | 第 3 步才登记；默认 off | off | 见 §7 第 3 步 |

**不进第一期实验臂：**

| id | 原因 |
|---|---|
| `reading-baseline` | 代码在他树，`pending-other-branch` |
| `perspective-lab` | 已有 `neutral/single/compare`；翻默认会移动基线读数，本单不碰 |
| `evidence-ledger` | 开着单槽真源；可测「没挂上」的 dump 位，不可换第二本账 |
| `information-cutoff` | 开着单槽；可消融「不传 as-of」看会不会偷用今天，不可一集两个截止日 |
| `skill-bridge-*` | 只开 `serenity-alpha` 是设计 |

### 5.3 默认盒 `default-v1`（冻的是函数，不是名单）

**本仓的授权面逐 frame 解算**（§3：`episode_factory.py:499-517`，且 `_is_evidence_free_task` 会把它整个清空），所以根本不存在一排可冻结的「生产开哪些」。`default-v1` 只冻两样：

1. **派生函数的符号名**——点名一个：`build_episode_context` 及其 `_authorized_capabilities` → `runtime_capabilities_for_frame`。收据写 `capability_source=<符号>`。
2. §5.2 里 `default=on|off` 的**非工具行**取值。
3. 写出规范 JSON（key 排序、无浮动字段）。
4. 测试：工作树再生成一次，与提交的 `default-v1` 字节一致。

**这个字节一致测试覆盖的是 (1)+(2)，不是授权面。** 不要在收据、文档或 PR 里把它说成「冻结了生产授权面」——那句话在本仓是假的。

每次 run 另记 `resolved_capabilities`（该 case 该次实解出来的面）。没有它，同一题两次跑就分不清「这颗是我关的」还是「这题本来就没授权」。

门禁比「文件 + 字面量」，**不比个数**（清理 1 + 新增 1 个数不变）。这是 BUILD.md 棘轮式门禁的同一条。

### 5.4 差量

```text
run = (case, default-v1, resolved_capabilities, delta)
delta 恰好一个 id 的 on↔off，作用在 resolved_capabilities 上
否则 runner exit 2，不写假收据
```

合同构造：以该 case 的生产 `ResearchTaskContract` 为源（`resolved_capabilities` 就是它的 `allowed_capabilities`），按差量改 `allowed_capabilities` 或**构造注入** composer/verifier。**mandatory 不再是子集 → 记 `designed_unsatisfiable`，不是 stage 失败。** 和梯子「地板以下不跑」同形，但归因字段叫 `switch_id`，不叫 `stage`。

---

## 6. 独立测试怎么摆

### 6.1 Git

- 树：`/Users/a77/fwp-wt-capability-switchboard`（已建）。
- 分支：`docs/capability-switchboard` ← `gitea/main@4e0c6bf5`。
- 解释器：主树 `.venv-workbench/bin/python`，cwd 用本树。
- 提交必须 pathspec，禁止 `git add -A`。
- 合并 `main` / 改生产默认盒：等用户确认。

主仓 `feat/reading-rules-baseline-batch1` 脏树**不碰**。

### 6.2 Runner（与梯子分家）

新文件，不改 `run_episode_seam_ladder.py`：

- 复用生产 composition root（`TurnControlCore` / `build_episode_context` / `build_episode_registry`），再收窄开关面。禁止复制工具表。
- 第一期 `mode=offline`，scripted 模型。live 另拍。
- artifact 目录与梯子分开（建议 `intelligence/eval/runs/switchboard/`，gitignored 或 Git 外；提交只收 schema 夹具）。
- 每份收据至少含：`switch_set`、`capability_source`、`resolved_capabilities`、`delta`、`case_id`、`as_of`、`revision`、`dirty`、`designed_unsatisfiable`、`chassis_survived`，外加这一对真读数：**`offered_schemas`**（这次真正递给模型的工具名）+ **`refused_calls`**（负控里被 `unknown_or_unauthorized_tool` 拒掉的调用）。
- ⚠ **不要把 `unauthorized_invocations=[]` 单独当过关证据**：scripted 模型只调被递给它的 schema（§3），关掉一颗后它压根不会去碰，这个字段在离线臂恒为空。

### 6.3 题

第一期 2–3 道，优先**复用梯子 fixture 的题面和 `as_of=2026-08-07`**，不新编故事。质量结论仍走 28 题，本 runner 不问「更好」。

**选题硬约束：排除 `_is_evidence_free_task` 判真的题面**（`episode_factory.py:468`）。这类题授权面被清空，每个 capability 差量都是空操作，`designed_unsatisfiable` 也不会触发——读数会显示「关得动」，实际是「本来就没开」。第 0 步对候选题各跑一次该判据，结果写进夹具字段 `candidate_cases`（`{id, evidence_free}`）；本期三道梯子题均为 `false`。

`offered_schemas` 取自 scripted 模型**第一轮 `complete` 被递给的 tools**，不是 `registry.names()`——中间再滤一层，正控会假绿。

### 6.4 和现有评测的墙

| 评测 | 本单 |
|---|---|
| 梯子 S0–S3 | 回归保持绿；不往里面塞差量 |
| 28 题 / Conversation | 不动 |
| `run_agent_episode_ab.py` | 不动 |
| `layer_audit.py` | 开关板模块落 `services/`；runtime 只读差量、调用 |

---

## 7. 四步（每步可停）

### 第 0 步：清单 + fail-closed

落 JSON 表 + 读表测试。未知 id 失败。`seam` 用 `rg` / AST 核到符号。还没有 runner。

过关四条：表能被 pytest 读；种子 id 无拼写漂移（相对 `_DEFAULT_TOOL_METADATA`）；每颗 capability 都查过有没有第二道 env 门（§5.2），查了没有也要写进 `notes`；进实验臂的每一行都填得出 `positive_control`。

### 第 1 步：离线「能关」（必须带正控 + 负控）

对 `chassis_survives=true` 的每一颗，scripted episode 关一次。三条都要，缺一条这步不算过：

1. **正控**：`offered_schemas` 关前关后的差集**恰好**是这一颗。差集为空、或多于一颗 → 红。
2. **负控**：另起一个 script 硬点名调那颗关掉的工具，断言它落到 `unknown_or_unauthorized_tool`（`agent_episode.py:402`，现成路径，不用新写）。调成功 → 红。
3. **底盘**：有收据、不崩、`chassis_survived=true`。

只做第 3 条 = 只证明了「没崩」。scripted 模型不会自发去碰关掉的工具（§3），所以「没崩」在离线臂恒真，它不是读数。

关不掉 → 改标 `welded`，不改 loop 硬关。

过关：结构棘轮底座成立，且每一颗都有一个真会变的观测量。

### 第 2 步：默认盒 + 一次一颗

生成 `default-v1`。2–3 题 × 关一颗。只解释闭环还在不在。

过关：双差量拒跑；artifact 带全集 + 差量 + 该次 `resolved_capabilities`（少了它，跨题的读数不可比）。

### 第 3 步：装一颗零行为零件

登记 `noop-prompt`（固定一小段说明书，不改工具、不改核验）。默认 off。只改开关表 + Provider，**`agent_episode` / 梯子 / Profile 无新分支**。

过关三条：

1. 第 2 步对照臂与「默认 + noop on」除开关字段外，闭环字段可比；
2. **正控**：`noop-prompt` on 时，那段说明书**确实出现在递给模型的 messages 里**（断言 message 内容，不是断言开关值）。这条不做，第 3 步只能证明「挂上去没坏」，证明不了「这条缝真能载行为」；
3. loop 文件无产品 `if`。

第 3 步没过，禁止把新检索、新路由、他树判读收进 `default-v1`。

---

## 8. 棘轮（实验树上就生效）

1. 开关 id 只增；改语义换新 id。
2. `default-v1` 从源码生成，比对字面量。
3. 新开关默认 off；进默认盒另一次对照 + 用户确认。
4. 未知 id 失败。
5. 实验树可以红；合默认盒 / 合 `main` 必须用户点头。
6. `layer_audit` 方向不变：services 不 import runtime。
7. 进实验臂的 id 必须填得出 `positive_control`；填不出的只登记、不进臂。「没崩」不是读数。

质量棘轮（答案变好）**不是**第 0–3 步的闸。那是以后、另一份评测。本单先保证「拧得动、拧得清、底盘不松」。

---

## 9. 方案比较（已选 A）

| 方案 | 内容 | 结论 |
|---|---|---|
| **A. 开关板 + 独立 runner** | 并列 id；默认盒 ± 一颗 | **选定** |
| B. 加长梯子 S4+ | 继续包含 | 否：测不了只关核验 |
| C. `allowed_tools` 抄进 Profile | 第二份名单 | 否：与 §7.5 偏离打架 |
| D. Cordis / Plugin Loader | 真热插拔 | 否：无第二宿主；2026-08-22 已禁 |
| E. 改 28 题 / 现有 A/B | 少一个 CLI | 否：目标函数不同，读数废 |

---

## 10. 验收（本单合入实验树，不是合 main）

1. 未知开关 id：测试红。
2. `default-v1` 再生一致（覆盖面 = 派生函数符号 + 非工具行，见 §5.3）。
3. 双差量：runner 非零退出，无阶段假绿。
4. 第 1 步：`chassis_survives=true` 各关一次，**正控（`offered_schemas` 差集恰好一颗）+ 负控（硬调被拒）+ 底盘跑完** 三条齐。
5. 第 3 步：loop 无新分支；对照臂闭环可比；说明书正控在 messages 里可见。
6. 梯子既有测试在本树仍绿。
7. 收据带 `capability_source` 与 `resolved_capabilities`；候选题面均非 evidence-free。
8. 文档写明：本底无 `reading_baseline`；技能桥不扩；本单是**消融夹具、不是运行期 flag**。

---

## 11. 对后续 agent 的指令

1. 先读 §1.2 与 §3，不要把梯子包含关系写进开关板。
2. 不要在主仓脏树或 `feat/reading-rules-baseline-batch1` 上实施。
3. 不要把「我们没有插件」当缺口去补 Cordis。
4. 宣称某行已接线：先 `rg` `seam` 字段那个符号。
5. 第 0 步不够格的标 welded / pending，不要在 orchestrator 里补 `if` 假装能关。
6. 写实施计划用 `docs/superpowers/plans/2026-08-22-capability-switchboard.md`，别把步骤写回本文。
7. 报「这一步过了」之前，先回答：**这次拧动，哪个字段必须变？变了吗？** 答不上来就是没过。
8. 改 `default-v1` ≠ 改线上（§2 定位）。要动生产是另一件事，且要用户点头。

---

## 12. 开放问题（不挡第 0–1 步）

1. ~~`structural-verifier` 关掉合同是否还能构造~~ **已答（2026-08-22 复核）**：构造上可注入（`:157` kwarg），但修复/backfill 链消费它的返回值（`:600-712`），所以按**行为耦合**标 `welded`。不用跑实验。
2. ~~`semantic-verifier` 的关法是 adapter 注入还是 scope 位~~ **已答**：走 **adapter 构造注入**（`:147`）。原稿写的「已有 skip 路径」不存在——过期 deadline 是 `raise TimeoutError` → `model_unavailable`（§3），拿它当 off 会把这颗误判成焊点。
3. `default-v1` 以哪条入口为准（Workbench continuous vs CLI ask）：仍要点名，但注意**同一入口内授权面也逐 frame 变**（§3），所以点的是**派生函数**、不是一份名单，收据写 `capability_source=`。两条入口若解算路径不同，第 0 步记下差异，不合并成一份。
4. 他树 `reading-baseline` 合入 `gitea/main` 之后，另开差量臂，不在本单偷挂。
5. 正控的粒度（`offered_schemas` 名单差集 vs 调用次数）：第 1 步先用名单差集，够用就不升级。

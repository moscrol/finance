# 2026-08-16 长尾问题兜底骨架注入交接（baseline skill + 自审清单）

roadmap_ref: 另案（候选 P5 质量战线；与 `2026-08-16-outlook-question-empty-delivery.md` 为姊妹刀：那份修「认得出的观点题」，这份抬「认不出的长尾」的地板。`market_*` 无 owner 主路不归本刀。）

一句话：路由无法穷尽用户问题，兜底梯子最末端是**裸的**——chat 兜底（置信 0.45）无 skill、无检索、无章法。本交接落一条「兜底骨架」：仅在 safe-fallback 或 `general_finance_qa` 置信 <0.6 时，把 judge 契约确定性前置成模型可见的章法。核心洞察：judge 的裁决规则今天只活在闸门侧，生成模型没见过它们。

证据等级：**[实测]** = 2026-08-16 读过快照代码/run 产物。

## 1. 现状：兜底梯子四层，末端裸答 [实测]

| 层 | 行为 | 兜底质量 |
|---|---|---|
| 路由层 `_safe_fallback_route` | controller 挂/认不出 → knowledge（0.55，可带检索）→ chat（0.45，**不检索**） | chat 分支无 skill 注入、无框架 |
| 引擎层 | episode 不可用 → 引擎 B `ask.answer_query` 流程写死 | 有流程无章法 |
| provider 层 | provider 链空 → 模板答案 | 空壳（launcher 已加启动守卫） |
| 交付层 | degraded → 缺口镜像 #327「猜你想问」 | 只补追问，不补正文 |

skill 注入的现状：注册表 ws 33 条 + kb 20 条，episode configure 可见 7 条，按相关性/owner 匹配。**全部是工作流/数据类 skill，没有通用回答骨架**。

接线坑（不要误读 configure 迹）：`conversation_orchestrator` 的 L1 `configure` 记下的 `selected_skill_ids` 是**入站**选择。auto 模式几乎恒为 `[]`，B 组分诊那条空列表**不能**当「路由失败、什么都选不中」。实现必须看路由之后的 `selected`。

长尾的真实形状（今天的活样本）：「基于8.15的行情现状，你认为周一的机会在哪」被分类 `general_finance_qa`，**confidence 0.4**——不是没路由到，是路由得心虚，然后全程没有任何章法性输入，草稿裸推断 → judge 剥光。`answer_orchestrator.resolve_question_type` 写明：`general_finance_qa` 是「上游没认出来」的残差，不是「确定是通用问题」。信封泛指主语给 0.4，分类兜底 0.45；已分型在 0.74–0.85。

## 2. 设计

### 2.1 骨架内容（框架，禁止夹带事实）

新建 `skills/finance-longtail-baseline/SKILL.md`（版本化）。正文是 **judge 契约的模型可见版**，源码是 `_JUDGE_SYSTEM_PROMPT` + `_CLAIM_POLICY`，**不是** `docs/learning/knevo-distill/q1-q11`。

1. 结构：直接回答 → 依据（事实句分层列）→ 条件与失效 → 证据边界（缺什么数据、哪些未核验）→ 建议验证路径/追问。
2. 事实句必须来自本轮检索证据、可绑定；比较类断言必须给出比较集（不许裸说「居前/最强」）。
3. 判断句必须带显式标记：「据此判断」「这说明」「这意味着」。与 `_JUDGE_SYSTEM_PROMPT` 认可的标记词表**逐字一致**；实现时抽成共享常量（与 outlook 那份交接共用），`SKILL.md` 必须含原词，单测锁住。
4. 不发明外部原因、统计和阈值；未取得的材料明说「未取得」。
5. 发布前自审清单：每个数字有来源？每个判断带标记？比较有比较集？边界句写了？——**这一节即「自审视角」**。

红线：skill 文本只含方法论，**不得包含任何市场事实/数字/板块名**。q1 异动四分类里的阈值（放量 2.5 倍、60% 早盘封板等）禁止蒸进骨架。

治理：挂 `skills/` 走版本；登记为 **prompt-only / 不可路由**，不进 `route_skills` 可选集合。不做成 skill-runtime 的 owner/contract 类 skill。若把它登记成可路由 skill，路由器会对「金融问题」选中它，触发条件与让位逻辑会自相打架。

### 2.2 注入触发（P0 只有两条）

命中任一即注入；有更具体 skill / `RESEARCH_OWNER_IDS` 内 owner 时让位。

1. `_safe_fallback_route` 被触发：`llm_failure_reason` 非空，或落 chat/knowledge 兜底分支（reason 含「安全降级」）。不要挂钩子函数本身（它也是 helper）。
2. 路由置信低：`question_type=general_finance_qa` 且 confidence < 0.6。读的是 `resolve_question_type` **之后**的类型和置信，不是信封原值。今天两问 0.4 正好落网。

产品域内「金融相关」几乎恒真，恒注等于恒吃 token，所以用「无章法才注」代替「金融就注」。0.6 卡在「不知道」（0.4/0.45/0.55）和已分型（0.74–0.85）之间。

#### 否决原条件 3（`selected_skill_ids=[]` 且无 workflow owner）

那条不是长尾，是盘面主路。[实测：`route_table.py`] `market_forecast` / `market_watch` / `market_cause` / `dated_market_review` 全是 `answer_owner=None`。ownerless research 会跳过 skill router，事后 `selected` 仍是 `[]`。`GenericResearchOwner` 是流程 owner，不是章法——但「无 workflow owner + selected=[]」覆盖的是产品核心公路，不是认不出的尾巴。

主路要骨架，是另一刀（与 outlook 的 grounding_mode 重叠），**不在本交接 P0**。本刀只抬残差地板。

### 2.3 自审视角的边界

成立，但定位必须钉死：**自审 = 把契约文本前置给模型，不是第二道验证**。书第 10 章：同一模型重读同一草稿、无新信息 = 无效协作。这里合法的原因是注入的「新信息」是契约/骨架本身（生成时原本不在场），不是让模型自己给自己发通行证。独立 semantic judge 原样保留、一行不动；预期效果是 judge 的剥句率下降（草稿先天合规），而不是绕过闸门。

先例：`llm_refine._required_outputs_block` 已把只活在评分侧的清单前置进 compose prompt。PR-2 是**同一轮生成**的确定性拼接，不是 finish 后再开一轮 LLM。

### 2.4 实现刀口（按序，可拆 PR）

1. 侦察半天：确认 chat/knowledge 兜底车道与 episode synthesis 各自的 prompt 装配点（orchestrator / research_contract / `build_synthesis_messages`），各选**一个**确定性注入位。合成侧今天只有 evidence 绑定和 HTML `claim_ids`，没有 judge 的中文标记词表 [实测：`_SYNTHESIS_SYSTEM_PROMPT` / `_GROUNDED_COMPOSER_SYSTEM_PROMPT`]。
2. PR-1：骨架 skill 文件 + prompt-only 登记 + 注入开关 `ASK_LONGTAIL_BASELINE`（**默认 off**，与 S1/S2 落地纪律一致）+ **触发 1+2** 接线 + 单测（off 时字节级不影响现路径；on 时夹具验证注入在场；假骨架含市场数字必须拒）。
3. PR-2：同一 skill 的 §5 节拼进同一轮 generation prompt（不是额外 LLM 轮次）。
4. 对照通过后另开 PR 翻默认值（参照 S1 #65 的先例）。

## 3. 预注册验收（S2 对照法）

- 题集：已冻结。权威夹具 `intelligence/eval/fixtures/longtail-baseline-frozen-15-2026-08-16.questions.json`，收据 `docs/verification/2026-08-16-longtail-baseline-frozen-set.md`。含 8.15 两问：`run_20260816_102941_554059` / `run_20260816_103318_230845`。
- 分层标注：outlook 形（题面含「你认为/你觉得/怎么看/机会在哪/会怎么走」）vs 真残差（无观点题面）。今天两问是 outlook 形 × 残差置信，两刀都会碰到。已翻成 `market_forecast` 的「明天怎么看」不进本集。
- 对照基线：gitea/main `773b3d7e`（含 outlook #72/#75/#79 与本刀 #77）。现状臂 = 该 tip + 开关 off；注入臂 = 同一 tip + `ASK_LONGTAIL_BASELINE=on`。不要再用 `268a0605` / `ef5c3821`（缺后续 outlook 刀），也不要拿 8792 快照 `437cd5e9` 当现状臂。outlook 档剥句率会叠 #79 比较集绑定；真残差档才是本刀独有信号。
- 主度量：非空 direct_answer 交付率；judge 剥句率（rejected_sentence/总句数）；evidence_bound_rate（**沿用 5pp 门槛不放宽**）；token/墙钟成本增量。
- 空壳 vs 诚实缺口：chat 兜底无检索时，正文写「未取得」算合规交付，不算空壳。不要用「看起来有字」当成功。
- 护栏：高置信路由（confidence≥0.6 且有 `RESEARCH_OWNER_IDS` owner 或专用 skill）行为零变化，取 5 题回归对比字节级 diff；植入含市场数字的假骨架文本必须被 review 拒绝。
- 收据进 `docs/verification/`，格式照 bookgap S2 对照收据（`fwp-wt-bookgap-s2` 分支 `bookgap/s2-judge-recheck`）。本 checkout 可能没有那份文件，以该 worktree 为准。

## 4. 与既有账的关系

- 姊妹刀：`2026-08-16-outlook-question-empty-delivery.md`。#72 与层 2 #75 已合 main。本刀在它们之上抬残差地板；共享标记词表仍要抽成常量，避免两处各写一份。
- knevo：借的是「骨架写成 skill 文件」的思路。README §5「把 Knevo 附录 8 种 prompt 骨架改写成技能文件」（情景推演 / 盘中信号 / 新闻映射 / 横向对比 / 仓位 / 时间轴 / 历史类比 / 复盘回放）**至今没人做**，本交接**不是**那条的字面落地。q6 也说明 Knevo 那 9 条同样是工作流 skill，和我们现有 33 条一类。
- 血缘：knevo 学习线三棒已全部合 main（#144 → #320 → #331）。本交接可挂第四棒，但正文源是 judge 契约，不是 q1-q11。开新分支从 gitea/main 拉。

## 5. 边界 / 不做什么

- 不动独立 judge、不放宽 5pp、不改 `_CLAIM_POLICY`。
- 不动 8792（修在 main，部署窗另案）。
- 不把 `GenericResearchOwner` / `market_*` 公路纳入 P0 触发。
- 不从 q1-q11 蒸馏阈值、数字或板块名。
- 不给 chat 兜底加检索能力（那是路由层的另一刀，别混进来）。
- 不在 `docs/dsh-absorption-spec` 提交本文件。

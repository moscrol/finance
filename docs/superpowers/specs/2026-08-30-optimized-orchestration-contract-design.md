# 设计：优化后编排合同——只留包椅与引擎 A

- 日期：2026-08-30
- 状态：Draft v2（只落本文。未改 `intelligence/`，未切 8792）
- v2 改动（2026-08-30 复核，[实测]）：① 判别 1 去掉 `ask_root` 锚点——五把包椅有三把住在
  `ask.py` 里、必然发这个阶段，且 P3 目标态**故意**把包留在 `answer_query`，原写法永远达不到；
  ② §4 给「开关未开」补告警要求（合法 ≠ 可静默）。§2.2 的 `market_technical`「A 内快路径」
  经查属实（`continuous_turn_adapter.py:337`，在包椅拒收判断之后）。裁决方向未改。
- 预注册：`R-20260830-05`（`claim_ledger_id.py`，占号时登记的分支名 `feat/optimized-orchestration-contract`，号不回收）
  - **落地分支实际是 `feat/orchestration-contract-docs`**（本稿与姊妹稿随勒死单 P0/P1 同链交付）。号对得上，但按占号分支名去找会扑空——**以本行为准**。占号分支名不改（号不回收的同一纪律：登记簿是历史，不重写）。
- 来源：2026-08-30 会话收口（包 / A / 工作流三词对齐 →「优化之后只有包和 A」→「A 整台拒收还要不要 B 兜底」→「包是不是固定工作流」）
- 姊妹单（本单不重做）：
  - `2026-08-30-engine-b-into-a-strangler-design.md`——**实施单**：取数库并入 A 预取、卸第二套研究循环。本单是它的**目标态合同**，并拍死其 §9 T1
  - `2026-08-26-watchlist-digest-pack-design.md` / `2026-08-24-market-watch-component-first-design.md` / `2026-08-25-sector-disclosure-scan-design.md`——各包椅的格子与残差纪律
  - `2026-08-30-coverage-without-number-ownership-design.md`——研究题开口必取记忆/联想，不交还数字所有权
- 代码树纪律：从 `gitea/main` 开干净树再改 runtime。本稿允许落主树 untracked。**禁止**把包改成无约束 compose。**禁止**研究题 A 拒收后再开第二套研究循环当兜底。

## 0. 一句话

优化后的工作台只做两件事：**包填格出厂**，或 **引擎 A 按契约 ReAct**。没有第三台叫「工作流」的研究引擎。需要固定步骤的题走包；需要分析的题给专用工具箱（没命中则残差五件）再进 A。A 回合失败走同回合 repair / 缺口稿；A **整台拒收研究题**只出声明缺口，不把旧 `answer_query` 研究循环当托底。

**判别变量**（合同验收看这个，不看文件还在不在）：

1. 包椅题公开稿数字 ⊆ 包快照 / `render()`；`compose=False` / `synthesize=False` 已锁；本回合无 `generic_research_owner` 阶段、无 `run_agent_loop` 调用。

   ⚠️ **`compose=False` 今天对盘面只在"包停摆"时成立**——这是本条最大的未兑现处，
   §10 初版只点名复盘/外盘，漏了盘面。[实测] `bind_market_watch_pack`（`ask.py:441-442`）写的是
   `compose=False if pack.should_stop else options.compose`；`_answer_market_review`（`ask.py:885-898`）
   也只在 `pack.should_stop` 时早退返回 `render()`，**否则继续往下走合成**。
   而 orchestrator 构造 `AskOptions` 时默认 `compose=True`（`conversation_orchestrator.py:2790`）。
   即：**盘面包正常出数的那条路（不停摆）今天是会组稿的**，只有空袋/锁库/休市才锁死。
   P3 要把它改成「有数也不组稿」，否则判别 1 对盘面永远只在故障态成立——
   **一条只在系统坏掉时才为真的验收，是反的**。
   **包椅这一条不许数 `ask_root`**——五把椅子不在同一层执行，后三把住在 `ask.py` 里，
   而 `answer_query` 把整个调用无条件包在 `_progress_stage(options, "ask_root")`（`ask.py:1546`），
   `_answer_query_impl` 还没进就已经发了：

   | 包椅 | 执行位置 [实测] | `ask_root` |
   |---|---|---|
   | `disclosure_scan` | orchestrator 内短路：`:2896-2922` `render()`（或 `compose` 时走 `prepare_disclosure_residual_answer` 残差写手）。绑定 `bind_disclosure_scan_pack` 也由 orchestrator `:2845` 直接调，不经 `answer_query` | 不发 |
   | `watchlist_digest` | orchestrator 内短路：`:2923-2943` `merge_digest_into_public_answer` | 不发 |
   | `market_watch` | **不在那条 if/elif 链里**，绑包后落 `else` → `:2973 _run_answer_query_with_watchdog` | **发** |
   | `dated_market_review` | 同上 | **发** |
   | `external_market` | 同上（`ask.py:1136 _answer_external_market`） | **发** |

   链的真实顺序（`conversation_orchestrator.py`）：`if disclosure_scan` → `elif watchlist_digest`
   → `elif owner_output` → `elif owner_timed_out` → **`else` → watchdog**。
   `market_watch` / `dated_market_review` 进 `answer_query` 后还会被
   `question_type_override` 改写成 `QUESTION_MARKET_REVIEW`（`:2803-2806`），
   共用 `ask.py:877 _answer_market_review`——**盘面没有对等短路**。

   且 **目标态也不会变**：§6 P3 明写「`answer_query` 缩成包 + 取数编排」，就是故意把包留在里面
   ——**盘面目标态就要留在 `answer_query` 里**。所以拿 `ask_root` 验包椅，对盘面/复盘/外盘
   这三把是**永远达不到**，不是「还没做到」。
   `ask_root` 是 `answer_query` 这个**模块的入口阶段**，包椅合法共用；只有在**研究题**
   上下文里它才是「掉进旧循环」的证据——判别 2/3 保留它，判别 1 不用。
   （同族第一例是 `agent_loop`：那是 B 留下的**标签名**，A 的回合里也有。
   **把模块入口标记当成引擎标记**，是本组稿子已经踩到第二次的形状。）
2. 研究题（含题型未命中的金融检索）主循环只有 episode；同样三个锚点为 0。**不要数** trace 里的 `capability="agent_loop"` 字符串（A 也盖这个标签）。
3. 研究题若 A 未能开张（开关、错车道）：公开稿是声明缺口，收据自述「未进入 episode」，**不得**出现上述三个 B 锚点。

人话：固定步骤的店自己出餐；研究只开一厅。厅没开，就告诉你没开，不把客人塞进隔壁旧馆子——旧馆子还得再装修一遍，两套一起养。

---

## 1. 术语（听反整单作废）

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **包** | 查哪几袋、段序、空态句、数字从哪格来，全在代码里；公开稿默认 = `render()`，`compose=False` | pip 包；「提示词搬家」；引擎 B |
| **引擎 A / Agent loop** | `continuous_turn_adapter` → Episode：裁箱 + 原生 `tools=` + ReAct + 结构门 + 语义判官 | 包；B 的 `run_agent_loop` |
| **工作流（产品）** | **就是包。** 固定步骤的题只留这一种 | 第三台研究引擎；`lane=workflow` 这个路由标签本身 |
| **取数库** | 给问句 + `as_of` 返回块或 gap 的纯函数（原 D 块收集器） | 再跑一轮研究循环 |
| **整台拒收** | adapter `handled=False`：A 没开张 | 结构门没过、超时、判官拒稿（那是回合内失败） |
| **B 锚点** | `ask_root` 进度阶段、`generic_research_owner` 阶段、`run_agent_loop` **调用** | 字符串 `agent_loop` |

`lane=workflow` 只表示进门标签，优化后执行上必须落到包椅，不得再解释成「请启动第二套研究管线」。

---

## 2. 目标态分流

```
问句
  ├─ 聊天 / 澄清 / 纯概念     → 车道稿（不是包，不是 A）
  ├─ 盘面 / 自选 / 复盘 / 外盘 / 公告扫描 → 包
  └─ 其余金融检索             → 引擎 A
        ├─ 命中研究题型 → 专用工具箱 + 开口预取（取数库）+ ReAct
        └─ 题型未命中   → 残差五件 + 算子触发的预取 + ReAct
```

没有「先流水线再补检索再 compose」的第三枝。

### 2.1 包椅（固定工作流）

| 题型 | 问法 | 终稿 |
|---|---|---|
| `market_watch` | 今天市场怎么样、今日看点 | 盘面四袋 `render()` |
| `watchlist_digest` | 按我的自选出简报 | 清单命中/缺口填格 |
| `disclosure_scan` | 某板块近期哪些公司有利好公告 | 扫描名单填格；名单齐时可在**包体后**追加解读，不得改名单或数字 |
| `dated_market_review` | 复盘某日 A 股 | 填格即稿，不得再开研究 compose |
| `external_market` | 美股/港股/外盘当天怎样 | 同上 |

A 看见这些题型继续拒收——这是椅子，不是故障。`answer_query` 若还当执行门，进门必须立刻锁 `compose=False` / `synthesize=False`（披露残差按既有闸，见披露包 spec）。

### 2.2 引擎 A（研究循环，只有这一套）

命中题型 → 专用箱 + ReAct。未命中、仍是金融检索 → 残差五件 + ReAct。**不是改走包，也不是改走第二循环。**

| 题型 | 问法 |
|---|---|
| `stock_deep_dive` / `valuation_estimate` / `trade_advice` | 个股怎么看、贵不贵、该不该买 |
| `theme_analysis` / `theme_track` | 题材进展、近况跟踪 |
| `financial_analysis` | 财报 |
| `news_impact` | 某消息影响 |
| `market_forecast` / `event_forecast` | 后市、未发生事件 |
| `market_cause` | 这周为啥跌 |
| `comparison` / `comparison_analog` | 对比、类比 |
| `kol_review` / `fact_check` | 评观点、核传言 |
| `quick_fact` | 收盘多少、涨停几家（取值进 episode） |
| `general_finance_qa` | 题型没打上、仍是金融检索 |
| `market_technical` | 支撑/压力位：A **内**确定性快路径，仍算 A，不是包，也不是完整 ReAct |

取数库只给开口预取供数。研究题要的结构化块（双红、类比等）上桌或写 gap，后面仍是 A 写终稿。

---

## 3. 包就是固定工作流（固定的不是提示词）

包 ≈ 固定工作流。搬进代码的是**产品合同**，不是把系统提示誊进 Python。

必须在代码里的：

| 固定什么 | 为什么不能留给提示词 |
|---|---|
| 查哪几袋 / 哪几次 SQL | 模型选源 = 数字所有权交还 |
| 段序、标签、空态句 | 空了也要占位；省略成「好看的几个数」会丢缺口 |
| 数字从哪一格来 | 公开稿 ⊆ 快照，才能对账 |
| 默认 `compose=False` | 组稿就是第二作者 |

可以留给模型的只有**残差解释**（包体后面追加），且必须有出稿闸：越界整段丢掉，退回纯包稿。

因此：需要固定步骤的题 = 包椅。需要固定**取数**、终稿仍是分析的 = 取数库 → A 开口，不是再开一台工作流引擎。

---

## 4. A 失败 ≠ 整台拒收

| 情况 | 谁处理 | 去哪 |
|---|---|---|
| 结构门 / 绑定对不上 | 同回合 repair | 修不满不上桌 |
| 超时、取消 | A 自己 | 缺口稿，不另开循环 |
| 语义判官不通过 | A 自己 | 半成品不上桌 |
| 包椅空袋 / 锁库 / 休市 | 包 | 固定缺口句，不转交 A 去编 |
| **研究题整台拒收**（`handled=False`） | 编排器 | **声明缺口稿**，见 §5 |

整台拒收的合法原因只剩：开关未开、`terminal_kind` 不是 research、题型在包椅上（故意不接）。优化后要消灭的是「研究题也能整台拒收再掉进第二循环」。生产开关必须保持 `ASK_CONTINUOUS_RUNTIME=on`；研究题不得因 canary/关开关落到旧厨房。

**「开关未开」这一条要配告警，否则它是一条静默的全站降级路。** 上面两句合起来的字面意思是
「这个原因合法，但不许发生」——只写合法、不写告警，关开关之后每一题都会**合法地**出缺口稿，
读数上看是「诚实声明」，实际上是整站没在工作，而且没有任何一处会喊。要求：

- `ASK_CONTINUOUS_RUNTIME` 非 `on`/有效 canary 而研究题走到缺口稿时，收据里必须带
  **可区分的原因码**（如 `runtime_disabled`），不能和「terminal_kind 不是 research」共用一个码；
- 该原因码在一个窗口内连续出现即告警（阈值另定，不在本单拍）。判据是**能不能一眼分出
  「今天没人问研究题」和「研究引擎关着」**——分不出就等于没告警。

---

## 5. 降级契约（拍死勒死单 T1）

**选 (a)。不选 (b)。**

研究题 A 未能开张：出「声明缺口的降级稿」+ 收据写明未进 episode。禁止保留旧 compose / `run_agent_loop` / `generic_research_owner` 当已声明退路。

理由（写进合同，执行方不得重开设计）：

1. 退路若仍是第二套研究循环，B 也必须继续优化（原生 tool use、结构门、判官），等于永远两台引擎。
2. 旧循环用文本里 `json.loads` 点工具，比 A 的原生 `tools=` 更脆。**兜底比主路脆，兜底就是假的。**
3. 收据若与 A 同构，少的那两道门不会说话。缺口稿必须长得不一样。

`control_frame_mismatch` 保持 `handled=True` 的 fail-closed，不要改成 decline 再走本节。

聊天 / 澄清 / 纯概念继续走车道稿，不套用研究缺口句。

---

## 6. 落地归属

本单是合同，不替代实施步骤。改 runtime 仍走勒死单：

| 阶段 | 谁干 | 本单锁的增量 |
|---|---|---|
| P0/P1 | 勒死单（取数库、`as_of`、单一真本源） | 不改分流合同 |
| P2 | 工作台研究题不再进 B 循环 | 验收用 §0 判别 2 |
| P3 | `answer_query` 缩成包 + 取数编排 | 验收用 §0 判别 1 + 3；T1 以本节为准，不再二选一 |

地图：落地提交必须改 `docs/agent-product-door.md`，写成「研究只 A、固定步骤只包」，删掉「工作台 B 还接某几条题型」的过期表。改 `DETERMINISTIC_OWNER_TYPES` 同类门定义时，同提交改门页。

---

## 7. 非目标

- ❌ 把包并进 A 当第一执行者。
- ❌ 研究题没命中就改走包或改走第二循环。
- ❌ 残差箱一次加全量工具。
- ❌ 包跑完无约束 compose / refine 改数字。
- ❌ 大爆炸删除 `ask.py`、owner skill、D 块测试、`build_default_tools` / `evidence_content_hash`。
- ❌ 研究题 A 拒收后用旧厨房托底（§5 已否）。
- ❌ 把 `lane=workflow` 再解释成一台引擎。
- ❌ 本单切 8792 / 改生产配置。

---

## 8. 更好 / 不更好

| 方案 | 为何不选 / 为何选 |
|---|---|
| 研究失败再走 B | 两套循环拆不掉，B 还得养 |
| 只留 B、A 当实验 | 丢掉 episode 契约、E 号、结构门 |
| 包也改成「框架 + 模型润色」 | 润色即第二作者，数字所有权破 |
| **包填格 + 只 A 做研究 + 拒收出缺口**（本单） | 固定步骤有主；研究一门；失败诚实 |

---

## 9. 红线

- 不切 8792 / 不改生产配置直到独立验收。
- 预取无 `content_hash` 不得冒充已上桌。
- 历史块必须 `as_of` 截断。
- 判「还有没有第二循环」只认 §1 的 B 锚点，不许 grep `agent_loop`。
- 台账号用 `python3 scripts/claim_ledger_id.py claim --branch <分支>`，禁止手写当日 max+1。
- 从干净 `gitea/main` 开工作树再改 runtime。

---

## 10. 成立条件

- 本稿是目标态裁决，不是已实施。主树若只多了本 md，不构成 runtime 变更。
- 勒死单 P0/P1 旁支交付不自动兑现本单判别 1–3。
- **`market_watch` / `dated_market_review` / `external_market` 今天仍能 compose**（三把都算，初版漏了盘面），算合同未兑现，归 P3，不得解释成「工作流引擎还在」。盘面的具体形状见 §0 判别 1 那段：`compose=False` 只在 `pack.should_stop` 时锁，正常出数时沿用 `compose=True`。**验收时别拿停摆态当通过**。
- 门页在落地前提前改成目标态会让下一个 agent 把未实施当成现状——**改代码的那次提交再改门页**。

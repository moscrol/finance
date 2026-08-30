# 设计：引擎 B 勒死并入引擎 A（取数库留下，第二套研究循环卸掉）

- 日期：2026-08-30
- 状态：Draft v2（只落本文。未改 `intelligence/`，未切 8792）
- v2 改动（2026-08-30 复核，逐条 [实测]）：判别变量换锚点（`agent_loop` 是 B 留下的**标签名**，A 的回合里也有）、§3 补四条事实、§4 补 StancePack 说明、P0 补 `as_of` 前置条款、P1 措辞改「日期键由调用方传入」、P2 补注入口（`services` 不 import `runtime`）、P3 补保留名单与降级契约。v1 的裁决方向未改。
- 来源：2026-08-30 会话走查（进门分流 / 包 / A ReAct / B 流水线）+ 既有开口预取缝（`asof_prefetch.py` 已写明 D8/D11「只在 Engine B 接线」）
- 相邻（本单不重做）：
  - `2026-08-24-market-watch-component-first-design.md`（包当终稿，拒收 A）
  - `2026-08-24-workbench-quality-residual-ux-design.md`（编译上桌后再残差）
  - `2026-08-23-operator-prefetch-os-design.md`（算子 → 预取块或 gap）
  - `2026-08-26-watchlist-digest-pack-design.md`（填格即公开稿，`compose=False`）
  - `2026-08-29-datablock-conformance-workorder.md`（**P0/P1 的现成回归夹具**：`DataBlockProvider` × `evidence_registry.REGISTRY` 20 块逐块契约，已交付待验收，分支 `test/datablock-conformance`，193p/1xf）
  - `docs/verification/2026-08-29-conformance-seam-census.md`（缝普查；「引擎 A vs 引擎 B 接口不同、不是同 Protocol 多实现」这条裁决是 §1.3 的依据）
- 代码树纪律：从 `gitea/main` 开干净树再改 runtime。本稿允许落主树 untracked。**禁止**把包改成「跑完再无约束 compose」。**禁止**把盘面/自选/复盘改回 Engine A 第一执行者。

## 0. 一句话

**并不是「正则没命中就改走 B」。** 没命中专属题型，今天和目标态都是交给引擎 A，箱子是残差五件套。B 要并进 A 的意思是：B 不再当第二台「先流水线再补检索再写手」的研究引擎；它的 D 块 / 图谱 / wiki 收集器变成 **A 开口预取要调用的取数库**。工作台研究循环只留 A；包继续当取数终稿。

**判别变量**（分两层，别混成一条）：

- **不变量（今天已绿，本单只许守住）**：工作台一条「没命中专属题型、但需要检索」的金融题，只走 `continuous_turn_adapter` → episode。[实测] 生产 `ASK_CONTINUOUS_RUNTIME="on"`（`~/.local/bin/start-finance-workbench:157`），adapter 只在四种情况 decline（mode off / canary 未激活 / `DETERMINISTIC_OWNER_TYPES` / `terminal_kind != "research"`），残差研究题一个都不占。**它今天就成立，所以它证明不了本单干了什么**——它是回归位，不是验收位。
- **本单 delta（验收看这个）**：算子命中的冻结题，opening prefetch 里出现 D8 / D11 的块或显式 gap（有 `content_hash` 或 gap 声明），而不是另开一轮 `answer_query`。

**锚点纪律**：判「B 的循环还在不在」，**不许 grep 字符串 `agent_loop`**。[实测] `agent_research.py:579/738/775` 把 `capability="agent_loop"` 写死在 ProviderTrace 上，而 A 的工具正是从同一处造的（`episode_tools.py:933` `agent_research.build_default_tools(retrieve_kb)`）——生产纯 A 回合 `run_20260828_171124_251680/` 里 `agent_loop` 出现 8 次，`ask_root` 与 `generic_research_owner` 一次没有。**`agent_loop` 是 B 留下的标签名，不是 B 的循环**，照字面验收会在正确的目标态上判红。只有 B 才产的锚点是：`ask_root` 进度阶段（`ask.py:1546`）、`generic_research_owner` 阶段（`ask.py:3058`）、`run_agent_loop` 实际调用（`ask.py:3532`）。本单顺手把那个字段改名 `evidence_tool`，不留给下一个人。

不是「B 文件删光」，不是「残差箱改成全量工具」。

人话：B 从「另一家厨房」改成「A 厨房里的冷藏柜」。点不到专项套餐，仍进 A 的厅；不会被送到隔壁那家旧馆子。旧馆子里的半成品（D0/D4/D7…）搬进 A 的开胃菜。盘面简报那种「答案就是表格」的店，继续自己出餐，不并进 A。

---

## 1. 先回答三个容易听反的点

### 1.1 「没命中还是给 A」——对，目标态也不变

| 进门结果 | 今天 | 并完之后 |
|---|---|---|
| 命中取数包（盘面 / 自选 / 复盘 / 公告扫描等 `DETERMINISTIC_OWNER_TYPES`） | 包出稿，A 拒收 | **不变**。不上 A，不上 B 研究循环 |
| 命中研究题型（个股 / 估值 / 展望 / 题材合同等） | 裁专用工具箱 → A ReAct | **仍是 A**。专用箱保留。B 的对应 D 块改由 A 预取供数，不再另跑 `answer_query` |
| **没命中**专属题型，但仍是金融检索 | `general_finance_qa` + 残差五件 → **A** | **仍是 A**。不是改走 B |
| 不像金融、不要求检索 | 聊天车道，A 拒收 | **不变** |
| `/api/runs`、CLI ask、owner 里的 `answer_query` | B 整条链 | 过渡期仍进旧入口，**入口内部**改为「共享预取 +（需要时）A」；终态旧循环不再拥有研究 |

所以：正则/控制器没命中，**从来不是、也不应该变成「交给 B」**。B 不是残差题的椅子。

### 1.2 「B 怎么发挥作用」——过渡期当库，终态不当引擎

B 今天在 `_answer_query_impl` 里做三截：

1. **写死取数**（D0/D4/D6… 规则 `applies()` 为真才跑；图谱 / wiki / closed-loop）
2. **可选补检索**（`run_agent_loop`，JSON 点工具名，`ASK_AGENT_LOOP` 灰度）
3. **写手合成**（compose / grounded composer）

并入 A 之后各自去向：

| B 的这一截 | 并完之后谁干 | B 还在吗 |
|---|---|---|
| 第 1 截：D 块 / 收集器 | A 开口 `collect_prefetch_items`（及后续同层）调用**同一份函数** | 留下的是**取数函数**，不是研究循环 |
| 第 2 截：`run_agent_loop` | 删掉作为主循环。补查就是 A 自己的 ReAct | 过渡期可关灰度；终态工作台回合不得再开 |
| 第 3 截：写手 | 研究题用 A 的 `draft` + 既有发布门。包仍填格即稿 | 旧 compose 只服务尚未迁完的入口，迁完卸 |

**B 发挥作用 = 冷藏柜供数，不是再开一轮厅。** 没命中的题：A 用残差箱自己点工具；需要上桌的结构化块（例如问句带了类比算子）由预取层向 B 的收集器要菜，或写 gap。不是把整题丢回 `answer_query`。

已有反证：`asof_prefetch._history_analog_items` 写明 D8「未在 Engine A 开场预取接线」、D11「只在 Engine B 接线」。这就是「还没并完」的实物，不是目标态。

### 1.3 「B 是写死流水线，接不住长尾」——不对，B 有第二个入口

这是本单最容易听反的一点，**说错会把 P3 的风险估低**。

`_answer_query_impl` 一进门第一件事就是（`ask.py:3055-3059`）：

```python
if options.research_task_contract is not None:
    with _progress_stage(options, "generic_research_owner"):
        return _answer_generic_owner(options)   # D 块流水线一次都不跑
```

`research_task_contract` 只在一处被设上（`conversation_orchestrator.py:2809`），条件是 `generic_owner_requested = decision.lane == "research" and 题型 not in {技术面, 外盘, 公告扫描}`（`:2245`）——**就是「研究题、没专属椅子」，跟 A 接的是同一批题**。

所以 B 有两个互斥的房间，共用 `answer_query` 一扇门：

| 房间 | 服务谁 | 形状 |
|---|---|---|
| D 块流水线 + compose | 有专属椅子的题（盘面/图谱/财报…） | 规则 `applies()` 驱动的确定性取数 + 写手 |
| `generic_research_owner` | **没椅子的长尾研究题** | `run_agent_loop`：模型自选工具、步数预算、deadline、required_outputs 契约 |

第二间就是 §0 说的「第二台研究引擎」，也是 §1.1「B 不是残差题的椅子」这句话今天**字面上不成立**的原因——它的名字就叫 ownerless 长尾入口。

**门禁的真实分布**（别把 B 写成裸奔，那会让降级契约的讨论跑偏）：

| | A | B 的长尾路 |
|---|---|---|
| `gate_receipt` | 盖（`_complete_continuous_turn`） | **也盖**（`_run_turn_ledgered`） |
| 完成度契约 `CompletionReport` | 用 | **定义方是 B**；A 的 verifier 反向 import 它（`episode_verifier.py:21`） |
| `evidence_judge`（证据相关性） | 有 | **也有**，同在 `services/`，共用 |
| 输出质检 + WARN 回灌修订 | — | **B 有**（`ask.py:3050`） |
| 语义判官 `episode_semantic_verifier` | **只有 A** | **结构上够不着**：判官在 `runtime/`，B 在 `services/`，禁止反向 import |
| 结构门 / 修复轮 / E 号 | **只有 A** | 无 |

结论是「**两道门 vs 三道门**」，不是「有门 vs 没门」。差的那两道是硬差别，且成因是分层而非疏忽。

**为什么这个差看不见**：缝普查已裁决「引擎 A vs 引擎 B 接口不同（Episode vs `answer_query`），不是同 Protocol 多实现」（`docs/verification/2026-08-29-conformance-seam-census.md` 不够格清单）——正因为接口不可统一，当初才退而求其次做了 W3「双引擎 `gate_receipt` 产物同构」。**同构当初是为了对账，现在成了掩护**：退到 B 出来的收据和 A 长得一样，少的那两道门不在收据里说话。详见 P3 降级契约。

---

## 2. 术语

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **引擎 A** | `continuous_turn_adapter` → `agent_episode`：裁箱 + 原生 `tools=` + ReAct + 终局 JSON | 包；B 的 `run_agent_loop` |
| **引擎 B** | `answer_query` / `_answer_query_impl` 整条：D 块流水线 + 可选 `run_agent_loop` + compose | 盘面包；`lane=workflow`；ProviderTrace 上那个 `capability="agent_loop"` 标签（A 也盖，见 §0） |
| **取数库** | 从 B 拆出来的纯函数：给问句 + as_of，返回块或 gap（今 `regime_block_for_llm`、`timeseries_block_for_llm`、`collect_wiki_rag` 等） | 再跑一遍 ask 根 |
| **包 / 取数终稿** | 答案就是填好的格子，`compose=False` | 凡 SQL 返回的题（解读题仍要模型） |
| **残差题** | 题型落到 `general_finance_qa`，残差五件箱 | 残差层 |
| **残差层** | 菜已上桌之后，模型解释冲突 / 补空格 / 写人话 | 再跑 B 流水线 |
| **勒死（strangler）** | 旧入口暂时还在，内部一块块改调共享预取 + A；直到旧循环不再被研究题走到 | 大爆炸删 `ask.py` |

---

## 3. 已核实事实（实施时不要再探一遍）

1. 工作台研究主路径先试 A：`conversation_orchestrator` 在 canned 之后调 `continuous_turn_adapter.handle`，`handled=True` 则 `_complete_continuous_turn`，**到不了**后面的 `route_skills` / `_run_answer_query_with_watchdog`。
2. A 拒收集合 `DETERMINISTIC_OWNER_TYPES`：`external_market` / `dated_market_review` / `market_watch` / `watchlist_digest` / `disclosure_scan`。这些是包椅，不是「该并进 A 的 B」。
3. 没命中：`query_understanding` 兜底 `general_finance_qa`；`runtime_capabilities_for_frame` 在 `general_finance_evidence` 下地板为 `market_data, news_search, memory_lookup, kb_search, web_search`。注释写明这是 Knevo 形下限，**不是**「改走 B」。
4. B 主干在 `ask.py` `_answer_query_impl`：planning → 若干题型早退 → 盘面/图谱/证据/wiki → web 兜底 → `agent_research.should_run` 才 `run_agent_loop` → compose 侧再挂 D0–D13 `DataBlockProvider`。
5. A 开口预取已吃掉一部分 B 块（双红、发酵、展望周报、宽度共振、资格/台阶、D10 等）。**明确未接线**：D8 题材历史类比、D11 个股走势类比（`asof_prefetch.py` 只留 gap）。这是 P0 并入的第一批实物。
6. owner skill（`theme-research` 等）的 `retrieve` 仍是 `answer_query`（B）。A 接住的工作台题 **不跑** 这些 skill。owner 是 B 的外套，不是 A 的 skill frontier。
7. 包默认不上写手：`bind_watchlist_digest_pack` / 盘面包 P0 `compose=False`。残差写手若开，只许解释、不许改数字。本单不推翻。
8. **包本身就是经 `answer_query` 执行的**：orchestrator 用 `replace(ask_options, compose=False, synthesize=False)` 进 `_run_answer_query_with_watchdog`（`conversation_orchestrator.py:2921/2941/2997`，watchdog 在 `:2973`）。所以 P3 的「`answer_query` 缩成包 + 取数库编排」与 §1.1 第一行「包不变」自洽——**P3 不拆包椅**，别读成矛盾。
9. **A 已经在用 B 的工具库**：`episode_tools.py:933` `default_tools = agent_research.build_default_tools(retrieve_kb)`。「B 当取数库」不是未来时，只是 D 块那半还没跟上。推论见 P3 保留名单。
10. `asof_prefetch.py` 自己有裸 SQL 打 `fact_sector_daily` / `fact_market_daily`（149 / 294 / 887 / 941；1008 行还是 `select max(trade_date) from fact_market_daily`）。P1 要治的重复是实物，不是假想。
11. **D8 / D11 的取数函数没有 `as_of` 参数**：`market_analogs.py`、`stock_analogs.py` 全文无此词；D10 能接进 A 正因为 `regime_block_for_llm(..., as_of=None)` 有（`market_regime_analogs.py:476-482`）。这决定了 P0 的真实体量，见 §5。
12. 依赖方向是硬的：`services/` 与 `workbench_skills/` 全树**零处** import `intelligence.runtime`（成文版见 `episode_tools.py:59`）。P2 的 owner 改造受此约束。

---

## 4. 目标形态（分流一张表）

```
问句
  ├─ 取数包命中 ──────────► 包填格出稿（无 A、无 B 循环）
  ├─ 聊天 / 澄清 ─────────► 车道出稿（A 拒收）
  ├─ 研究题型命中 ────────► 专用工具箱 + 开口预取（取数库）+ A ReAct
  └─ 题型未命中、需检索 ──► 残差五件箱 + 算子触发的预取（取数库）+ A ReAct
                              ↑
                         这里没有 B 研究循环
```

B 在图上只出现在「取数库」节点：预取层 `import` 收集器。不再出现「整题 `answer_query`」。

**StancePack 不在图上单列一条边**：它在 adapter 之前跑（`conversation_orchestrator.py:2021-2032`），结果作为 `control` 喂进 A（`replace(continuous_control, stance_pack=...)`）。它是 A 的入参，**不是第三个引擎**。买卖票据题的边界见 StancePack 侧 spec，本单不动。

残差五件套本单 **不改成全量工具**。并的是取数块接线，不是把 `finance_query` / `l3_lookup` 无条件塞进残差箱（那是另一单；高标股/排名已由 `quick_fact` 进 episode 处理过）。

---

## 5. 阶段

### P0 — 说清楚 + 补 A 预取缺口（本单文档 + 第一批接线）

> **状态：已交付待验收**（2026-08-30，R-20260830-02）。分支 `feat/d8-d11-asof-prefetch`
> @ `64b5e6db`，树 `/Users/a77/fwp-wt-d8d11-asof`，基线 `gitea/main@f40f878b`。
> 未合 main、未推、未切 8792。
> 收据：全量 `intelligence/tests` **6569 passed / 14 skipped / 1 xfailed**（@`3808a834`）；
> 新增 `intelligence/tests/test_analog_as_of_truncation.py` 10 条；ruff 全绿；
> 七条 pre-commit 门禁全过（层级审计 ERROR 0）。
> **五个变异逐条证伪**（每条只红它该红的）：D11 解析器不截 / D8 解析器不截 /
> D8·D11 历史查询不截 / 预取漏传 as_of（D8、D11 各一）。
> ⚠️ 过程中抓到**自己写的假门禁**：初版夹具下「最大日期 ≤ as_of」在抽掉历史截断后
> 依然全绿（D8/D11 只渲染历史窗口日期，而那些窗口恰好都在截止日之前）。夹具已改成
> 「截止日前弱、之后全强」，理由写在测试文件顶部。**没被变异证伪过的守门测试就是假门禁**
> ——这条在本单亲身兑现了一次。

**先看清体量：这不是「接线」，是先给两个共享取数函数补 `as_of`**（§3 事实 11）。顺序：

1. 给 `analog_block_for_llm`（D8）/ `stock_analog_block_for_llm`（D11）加**可选** `as_of=None`，照 D10 先例。B 侧调用不传 → 输出逐字节不变，**不构成生产行为变更**。
2. D11 必须**解析器和取数两处都截断**：`stock_analogs.py:220/226` 的 `order by trade_date desc limit 1` 与 `:237` 的 `trade_date = (select max(trade_date) from fact_stock_daily)` 是**自派生基准**。只截断 `load_stock_analog_artifact`、漏掉 `_resolve_stock`，块头日期和窗口就不是同一天——**而且整块自洽，「有块」类夹具照不出来**（检测器的参照系不能来自被测物）。
3. 再把 A 预取接上：算子命中则出块或 gap，落进 `_history_analog_items`。
4. **同步改** `asof_prefetch.py:491` 的 docstring 与 `:528-548` 的 gap 文案——那里写着「D8 / D11 在 **P0** 只留 gap」，指的是**上一单**的 P0，与本单 P0 指令相反。不改这句，下一个 agent 读到的是过期口径。

- 夹具：算子命中的冻结题，opening evidence 有对应块或 gap；**同题跨两个 as_of 各跑一次，块内最大日期必须随 as_of 变**（只断言「有块」抓不到库尾泄漏）。工作台该题 `handled=True` 且无 `ask_root`。
- 不删 `answer_query`，不关 `/api/runs`。

### P1 — 取数函数单一真本源

> **状态：第一刀已交付待验收**（2026-08-30，R-20260830-03）。分支
> `feat/double-red-single-source` @ `0ee0daaf`（接在 P0 之上），未合 main、未推、未切 8792。
> **本单猜错了目标**：P1 原文说「禁止两份 SQL/两份日期键」，实物既不是 SQL 也不是日期键，
> 是**阈值**——双红口径在树里有三份互不引用的实现（`signals.DOUBLE_RED_SQL` 写死字面量 /
> `theme_lifecycle_timeline` 自带一套常量、A 的 `asof_prefetch` 走这份 /
> `market_regime_analogs` D10 里再写死一次），数值恰好一致所以谁都没发现，
> 且每一份自己都自洽。**分家线正好压在 A 侧与 B 侧之间**，D10 尤其要命：
> 它同时供 A 预取和 B compose，改阈值时两边一起错、行数与覆盖率审计还全绿。
> 改法照 BUILD.md「单一真本源且生成」：阈值只在 `signals.py` 三行，谓词串由它们生成，
> `:g` 保证两个串逐字节不变（有测试钉住），B 侧既有 SQL 零改动。
> 收据：全量 `intelligence/tests` + `tests` **7254 passed / 15 skipped / 1 xfailed**；ruff 全绿；
> 七条 pre-commit 全过。三个变异逐条证伪。
> ⚠️ 又抓到一次自己写的假门禁：`assertNotRegex(src, r"^NAME = 数值")` 没开 `MULTILINE`，
> `^` 只匹配整份源码开头，那条断言从来没匹配过，变异 B 当场逃掉。**行锚点类断言尤其
> 容易变成假门禁**，写完必须变异一次。
> 剩余：`asof_prefetch` 那几处裸 SQL（`dual_red_counts` / `_theme_sector_snapshot_items` 等）
> 经核对**不是** D 块的第二实现，是预取层独有的读法，不构成重复，本单不强行合并。

- D0/D4/D6/D7 等：A 预取与 B compose 侧 `DataBlockProvider` **调用同一函数**，禁止两份 SQL。第一批清账对象是 `asof_prefetch.py` 里那几处裸 SQL（§3 事实 10）。
- 日期键的口径：**同一函数、日期键由调用方传入**。B 传 `None`（不截断）是**显式选择**，不是第二套实现。别把这条读成「B 也要改成截断」——那是生产行为变更，不在本单。
- B 的 `applies()` 规则能表达的，预取层用算子/题型表达，不在 A 里再写一套正则。
- `/api/runs` 仍可进 `answer_query`，但取数必须走共享函数（勒死第一步：循环还在，库已共用）。

### P2 — 工作台研究题不再进 B 循环

- owner 分叉若仍存在：`retrieve` 改为「共享预取 + 必要时 spawn A」，或工作台研究题全面由 A 接住后 owner 只保留包/工作流。
  - **受依赖方向约束**（§3 事实 12）：直接在 owner 里 spawn A = `services` 反向 import `runtime`，会被分层拦下。
  - 现成手法就在同一个文件：`research_owner.py:92` 已经把 `answer_query_fn: AnswerQuery = answer_query` 做成注入口。照它把 A 当 port 从组装根传进来，**不要在 `services/` 里 import `runtime`**。
- `ASK_AGENT_LOOP` 在工作台会话口默认关；B 的 `run_agent_loop` 不再作为「A 没接住就再 ReAct 一次」的影子引擎。注意这是一次**真实配置变更**：生产现值 `ASK_AGENT_LOOP="auto"`（`start-finance-workbench:168`）。
- 验收：生产工作台研究题 trace 的研究主循环只有 episode；`ask_root` / `generic_research_owner` 阶段与 `run_agent_loop` 调用均为 0。**不要数 `agent_loop`**（§0 锚点纪律：A 的回合里也有这个标签）。

### P3 — 旧入口勒死

- CLI ask / `/api/runs`：研究题改调同一 `continuous_turn_adapter`（或薄适配器只做参数投影）。
- `answer_query` 缩成：包/早退题型 + 取数库编排（若还需要给非会话口），不再含第二套 agent 循环。**包椅不动**（§3 事实 8：包就是走 `answer_query` 执行的）。
- 删或降级 `run_agent_loop` 的工作台调用点；留下的测试标明「库函数 / 历史夹具」。
- **保留名单（删之前先读）**：`agent_research.build_default_tools` / `build_graph_tools` / `AgentEvidence` / `evidence_content_hash` **不在删除范围**——A 的工具就是从这里造的（§3 事实 9）。按「拆掉 `agent_research` 的主循环」字面执行，会把 A 的工具一起拆掉。要删的是 `run_agent_loop` 这一个函数的**调用点**，不是这个模块。
- **降级契约（本单必须补上，否则 P3 落地后有题无处可去）**：A `decline` 时（`handled=False`）今天落到 `route_skills` → `_run_answer_query_with_watchdog`（`conversation_orchestrator.py:2973`），B 兜住。B 的循环拆掉之后，这条路必须有明写的归宿。
  - 真会漏到这里的只有两种：`ASK_CONTINUOUS_RUNTIME` 非 on/canary、`terminal_kind == "non_research"`（`turn_control_core.py:93-97`）。
  - `control_frame_mismatch` **不在此列**：它返回 `handled=True`（`continuous_turn_adapter.py:1644`），已经是 fail-closed，别顺手改成 decline。
  - 二选一并写进 spec：(a) 出「声明缺口的降级稿」；(b) 保留 B 的 compose 作为**已声明的降级路径**并留收据。选哪个都行，**不写才是问题**——不写等于把决定权交给下游，而下游没有下限。
  - **选 (b) 时的附加条件（不可省）**：收据必须自述走的是哪条路、少了哪道门。§1.3 已说明 A 与 B 差的是语义判官 + 结构门 + 修复轮；**W3 的「双引擎收据同构」在降级路径上必须破例**——同构在这里等于消音。降级收据长得不一样是特性不是缺陷。
  - **B 作为退路有保质期**：B 的循环靠 `json.loads` 解析模型吐的文本来点工具（`agent_research.py:976`），A 用原生 `tools=`。模型越往后越是为原生 tool use 优化，这条退路只会越来越脆。**兜底比主路更脆时，兜底就是假的**——这是给本单定期限的理由，不是可以无限期并存的理由。

---

## 6. 非目标

- ❌ 把包并进 A 当第一执行者（盘面空转事故，已否）。
- ❌ 没命中改走 B（与 §1.1 相反，整单作废）。
- ❌ 残差箱一次加全量工具（定义费不是理由；调用预算是另一单）。
- ❌ 包跑完无约束 compose / refine 改数字。
- ❌ 大爆炸删除 `ask.py`、owner skill、D 块测试。
- ❌ 抄 Claude skill frontier 让研究模型自己挑 owner。
- ❌ 把 B 的写手当成 A 的替代发布路径长期并存（P3 才收，P0–P1 允许旧入口）。

---

## 7. 更好 / 不更好（避免执行方重开设计）

| 方案 | 为何不选 / 为何选 |
|---|---|
| 没命中丢给 B | B 是更重的流水线+写手，残差题更需要 A 自己选下一刀。B 当兜底 = 两套循环永远拆不掉 |
| 只留 B、A 当实验 | 工作台主路径已经是 A；倒回去会丢掉 episode 契约、E 号、结构门 |
| A/B 永久双引擎 | 同一 D 块两套接线（D8/D11 现状），有格子没供数会复发 |
| **勒死：库并入预取，循环只留 A**（本单） | 取数仍确定性；研究只一个 ReAct；包椅不动 |

包要不要 LLM refine：不在本单。结论仍是「可开残差解释、不可改数字」，见盘面/自选 spec。

---

## 8. 红线

- 不切 8792 / 不改生产配置直到独立验收。
- 预取无 `content_hash` 不得冒充已上桌（既有 fail-closed）。
- 历史块必须 `as_of` 截断，禁止 A 预取把 B 的「库尾」泄漏进来。
- 标识符 / 证据哈希纪律不因搬家而截断。
- 台账号用 `python3 scripts/claim_ledger_id.py claim --branch <分支>`，禁止手写当日 max+1。
- CC 数字（50K/87%/TTL）不搬进本仓阈值。

---

## 9. 派生待办（本单查出，但不在本单做）

按「提议造之前先搜存不存在」的纪律，这几条都已核过现状，别重新发现一遍。

| # | 事项 | 现状 [实测] | 归属 |
|---|---|---|---|
| T1 | **P3 降级契约选 (a) 还是 (b)** | 未定。不阻塞 P0/P1 | 待用户裁决，P3 动工前必须有答案 |
| T2 | `capability="agent_loop"` 改名 `evidence_tool` | `agent_research.py:579/738/775` 三处 + 所有按该字段计数的审计 + 历史 trace 可比性 | **另开单**。本单只在 §0 立锚点纪律，不改字段 |
| T3 | 接口层地图漂移 | **本轮已修** `docs/agent-product-door.md`（三条题型→五条、`quick_fact` 移出、补 `generic_research_owner` 长尾路、补门禁不对等） | 已完成 |
| T4 | **没有任何门禁看 `docs/`** | pre-commit 九条（`layer-audit` / `path-literals` / `unread-fields` / `dataset-registration` / `tool-reachability` / `agent-workspace-facts` / `block-forbidden-files` + ruff/私钥/大文件/冲突）**无一条覆盖文档**。「改门必更此页」是纪律不是机制——T3 那次漂移就是它漏的 | **另开单**。建议形状：棘轮式，当 `DETERMINISTIC_OWNER_TYPES` 一类「门的定义常量」变更时，要求同提交内 `agent-product-door.md` 有改动；存量免检、只拦新增，手法同 `tool-reachability` |
| T4b | P0 交付里顺带修的：`test_market_midterm._FakeCon.execute` 补上真实 duckdb 的 `(sql, params?)` 签名 | 替身比现实简单 → 生产侧一开始传参就炸在夹具上（本单实测炸了 2 条） | 已完成 |
| T6 | `market_feature_store/reports/daily_review.py` 还有 4 处写死的双红谓词（3 正向 + 1 反向近似 `amount<=500 OR IS NULL`） | 已进 P1 棘轮基线，只许缩不许涨；属报表域，混进 P1 会把回归面从 4 个模块扩到整条日报链路 | **另开单**，清完把基线改小 |
| T5 | 代码地图每日一次而非每次改动 | launchd 04:25（`~/Library/Logs/com.a77.finance-code-map-refresh.log` 实测 08-30 正常 build 到 `444a06e3`）。当天提交当天不进图，`status` fail-closed 会如实报 stale | 已知限制，不修。编码任务照 AGENTS.md 先 `status`、stale 就 `build` |

P2 的分层约束**有硬门禁兜底**：`scripts/layer_audit.py:6` 原文 `intelligence/services/** 不得 import intelligence.runtime.*`，违规提交即拦，不用等 review。

## 10. 成立条件

- 本稿是设计裁决，不是已实施。`dirty` 主树若只多了本 md，不构成 runtime 变更。
- P0 接线必须另开干净工作树；验收看 opening prefetch + 工作台无 `ask_root`，不看「B 文件还在」，更不看 `agent_loop` 的字符串计数（§0 锚点纪律）。
- P0 会改到 **B 也在调**的两个函数（D8 / D11）。加的是默认 `None` 的可选参数，B 侧应逐字节不变——但这句是**待证不是已证**。**回归夹具不用新写**：跑 `intelligence/tests/conformance_datablocks/`（分支 `test/datablock-conformance`，已交付待验收），它正是逐块钉 `applies` 门控 / `collect` 形状 / 缺口声明的套件。P1 同理，改「单一真本源」时它就是护栏。
- B 作为退路有保质期，理由见 P3 最后一条。本单不是「可以永远拖着」的授权。
- **地图回写（改门必更）**：`docs/agent-product-door.md:39` 现在写「Workbench 里 B 仅 `external_market` / `quick_fact` / `dated_market_review` 三条」，**已漂三处** [实测]——`DETERMINISTIC_OWNER_TYPES` 实为五条（加 `market_watch` / `watchlist_digest` / `disclosure_scan`）、`quick_fact` 已被明确移出（`continuous_turn_adapter.py:108`，R-20260828-05）、且完全没提 `generic_research_owner` 这条长尾路。**本单任何阶段落地前先修这一行**：接口层地图是下一个 agent 的入口，它漂着，后来人就会照 §1.3 之前那个错误模型做决定。

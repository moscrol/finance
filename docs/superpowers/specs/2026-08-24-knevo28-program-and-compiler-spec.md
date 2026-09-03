# knevo28 四臂收口：ResearchProgram 输入加法 + view() 出口加深

- 日期：2026-08-24
- 状态：Draft **v2**（架构审查改定；**本单只落规格，不施工**）
- v1 → v2：P0-A 从「新开 `PublicAnswerCompiler`」改为**加深已有** `session_projection.view`；D1 维持关单，不收编第三扇放稿门；Both 格不追平组件臂 95.96。
- 证据矿（只读）：`~/.finance-runtime/knevo28-four-arm-20260824/`
  - 一页结论：`analysis/one-page-report.md`
  - M2 分诊：`analysis/agent-run-triage-report.md`
  - 既有优化草案：`analysis/workbench-quality-optimization-spec.md`（v1 选型，出口侧以本文 v2 为准）
  - 盲评：`analysis/blind-judge/blind-score-summary.json`
  - 收据：`artifact-receipt.json`（112 case-arm / 120 turn-arm）
- 施工基线：**当前 `gitea/main`**（核稿时 `b07259c0`，已含 #349/#350/#352/#353）。开工先 `git rev-parse gitea/main`，不要钉死 `af71f048`。实验冻结口 8792=`8688545b`、8796=`76ee1e89` **只作证据引用，不作施工基线**。
- 相邻 spec（不重做、不改口）：
  - `2026-08-23-publication-and-contract-subtract-design.md`（#346 已合）
  - `2026-08-24-harness-ceiling-and-8796-decouple-followup.md`（D3=#349、D4 第 1 步=#350 已合；**D1 `R-20260824-07` 已关单**，本单不收编、不新开第三扇放稿门）
  - `2026-08-24-market-watch-component-first-design.md`（#352 已合；本单输入侧是它的**泛化**）

## 硬约束

- 缺陷号一律 `R-YYYYMMDD-NN`；本单新行从 **`R-20260824-12`** 起（01–06/08/09/11 已占用）。
- **A1 与 SPT 不互证**；knevo28 收据不得关闭 `R-20260823-SPTTECH-*`，反之亦然。
- 数据块 `D0`–`D11` 是 `evidence_registry` 开关，**不是缺陷单**。
- 从 `gitea/main` 开干净 worktree；pathspec 提交；禁 `git add -A`。
- 原文矿只读；引用带路径。
- **禁止新增** `intelligence/services/public_answer_compiler.py` 与 `ClaimKind`。公开稿只经 `session_projection.view`。

---

## 0. 审查结论（交付验收）

### 0.1 交付完整性

| 检查项 | 结果 |
|---|---|
| 28 题 × 4 臂 = 112 case-arm | ✅ |
| C10 追问 → 120 turn-arm | ✅ |
| 产物 checksum（1393 文件） | ✅（用户报告；`artifact-receipt.json` 可查） |
| 未改 finance 源码 / 未切 8792/8796 | ✅ |

### 0.2 盲评摘要（与一页结论一致）

| 臂 | 均分 | 中位 | 非空 | Fatal |
|---|---:|---:|---:|---:|
| 组件天花板 | **95.96** | 98 | 30/30 | **0** |
| 8796 | 74.18 | 82 | 30/30 | 12 |
| 8792 | 70.54 | 76 | 30/30 | 12 |
| ReAct 调组件 | 54.07 | 70 | 19/30 | 19 |

组件 95.96 的前提是：28 题**现场手写** program + 固定模板。M2 已写明「不是可部署泛化基线」。它证明积木够用，**不是**产品 SLO。

### 0.3 审查裁定：三句话

1. **组件臂赢的正交部分是「现场研究程序」**（定义、宇宙、槽位、查询程序、停止条件）——不是契约自动提供，也不是文笔。
2. **Workbench 第一次系统性分叉在 plan**：30/30 turn `plan=null`；A4 严格双红仍被编成 `general_finance_qa + operators=[]`，尽管仓内已有 `DOUBLE_RED_SQL` / `dual_red_counts`。
3. **第二次损伤在 publication**：有用草稿整篇丢弃、QC 标记进公开稿、两臂对 judge unavailable 走了不同已有成因；ReAct 非空常 96–100 分，但 11/30 空答（租用循环没有在工具缝强制留合成预算）。

### 0.4 v2 审查增量（相对 v1 与 Mac 草案）

- **B2 不是禁语漏网，是成因误贴 + 二次缝合。** 8792@`8688545b` B2 `stop_reason=invalid_repair_finish`：已有 9 条板块日线，repair 未吐合法 `FINAL_JSON`。`_gap_answer` 把它标成 `CAUSE_EVIDENCE_GAP`，于是走 `opening_for` 的正典开口「现有证据不足」——这句话是设计文案，不是过滤器没拦住的黑词。随后 `continuous_turn_adapter` 在 `view()` **之后**再调 `ensure_preplaced_gap_sections`，缝上三行 `【结构缺口】`。verifier 自己的 `public_answer` 没有这三行；用户 `answer.md` 有。证据：`arms/8792/B2-theme-liquid-cooling/turn-01/answer.md`、`session_projection.py`、`continuous_turn_adapter.py`（`ensure_preplaced_gap_sections`）。
- **单一出口已经在。** `session_projection.view(TerminalFacts)` 开篇写明「同一份冻结终局事实只许有一条出口」。`evidence_gap` 分支已允许 `public + gap_body` 并存，只是 `_gap_answer` 从不传 `public=`。v1 再开 `PublicAnswerCompiler` = 第二部宪法（#346 会再演）。
- **`_gap_answer` 红线是封上限。** 原文：「一个字都不从 draft 捞；gap 场合 draft 已被拒，捞正文等于绕过语义门」。改写：拒稿**之前**把已兑现槽写入 `TerminalFacts.public`（拦输入），不要事后捞拒稿，也不要整篇换成 gap 模板。
- **#352 已前移基线**：`market_watch` 四袋包 live confirmed（R-01..06）；ResearchProgram 是泛化 #352，不是从零发明 planner。
- **8796 vs 8792**：11 胜 / 8 平 / 9 负（+3.64），B2/B3/B5 增益说明**输入侧扩容有效**；两臂各 12 fatal → **共享出口债未解**，禁止归因模型强弱。
- **D1 不改口。** `R-20260824-07` confirmed：认不出的判官错误保持 fail-closed。本单禁止把「claim 级安全子集」写成第三扇放稿门。

---

## 1. 问题四层 + 证据指针

| 层 | 主犯？ | 事实 | 证据指针 |
|---|---|---|---|
| **供给** | 次要 | A5 快路 ~9.6s；ReAct B4 取 97 条证据；空池 #349 已合待 live | `arms/8792/A5-limit-heat/`；`empty_pool_fallback.py` |
| **计划** | **PRIMARY-1** | 30/30 无 plan；A4 误路由；A10 aggregate/detail 未分 | `arms/8792/A4-dual-red/turn-01/continuous-episode.json` |
| **合成** | ReAct 主 | 5 turn 有证据 ~192s 零 draft；usage-limit 连锁空答 | `arms/react-components/B4-fermentation-trace/turn-01/outcome.json` |
| **放行** | **PRIMARY-2** | QC 泄漏 13/12 turn；B2 整稿丢弃；B1/B2 走了不同已有成因；false capability 10/11 | `arms/8792/B2-theme-liquid-cooling/`；`arms/8796/B1-theme-photoresist/` |

因果链：

```text
缺可执行研究程序 → 错定义/错查询/过度探索 → 草稿不稳
  → capability/judge 失真
  → view() 被旁路（成因误贴 + 出口后再缝 QC）
  → 「证据不足」开口 / 【结构缺口】 / 整稿丢弃
```

四臂证伪：只加工具/预算（H2）❌；只加判官（H3）❌。

人话：传菜口已经有了，问题是厨房贴错标签，保安还在窗口外面再贴一张纸条。再造一个传菜口解决不了。

---

## 2. 输入加法：ResearchProgram（泛化 #352）（P0-B，P0-A 合入后再动）

### 2.1 原则

- **不新增第四套 / 第五套 planner。** 仓内已有：`research_plan.ResearchPlan`（模型自愿 PLAN）、`research_contract.ResearchPlan`（TurnIntent 投影）、`ThemeResearchSpec` + `answer_model.Claim`、`evidence_capabilities.EvidenceRequirement`、`market_watch_pack`。
- **一个编译器** `compile_research_program(...)` 是 operators / recipes 的**唯一写入点**。`query_understanding` 只做词面触发。旧 Plan / Spec 降为内部阶段或适配器，禁止并排各写一份 operators。
- 类型优先落 `research_contract.py`（或同包仅当 types 溢出才新文件）。禁止与上表并排再养一套互不认得的「计划」。
- **三个消费者**必须分清循环形态（混口禁止平均成「我们用了 SDK」）：
  - Workbench 连续路径、Engine B `ask`：**拥有循环**，可直接注入 program。
  - Codex ReAct（`CodexHeadlessRuntime`）：**租用循环**，只能在工具缝守门。
  - 确定性 fast path：无模型 loop（#352 `market_watch_pack` 为第一个已迁移 pack）。

### 2.2 核心类型

```python
# 摘要；完整字段见实施时 types。publication_policy 是 TerminalFacts.cause 的策略 id，不是新编译器。
ResearchProgram:
  program_id: str              # 内容寻址 hash，进 trace
  question_class: str            # route_table 题型，不新增题型
  operators: tuple[str, ...]     # 稳定 operator id；只许 compile_research_program 写入
  definition_receipts: ...      # 绑定 DOUBLE_RED_SQL / predicate_faces
  query_recipes: ...            # aggregate|detail|timeseries|cross_table + strict_date
  required_fact_slots: ...      # 对齐 episode required_outputs
  stop_rules / fallback_policy  # 对接 #349 empty_pool_one_shot
  publication_policy: str        # → 已有 TerminalFacts.cause，不指向新模块
```

`synthesis_reserve` **不是新字段**。拥有循环里 `ResearchDeadline.synthesis_reserve` 已在。ReAct 空答是租用循环没在工具缝停探索（P1：`headless_tool_gateway` 拒新工具），不要把 reserve 写成 program 上的建议数字指望模型自觉。

### 2.3 接线点

| 消费者 | 文件 | 动作 |
|---|---|---|
| Engine B | `ask.py` | `bind_market_watch_pack` → `bind_research_program`（market_watch **逐字节回归**） |
| Engine A | `episode_factory.py`、`episode_tools.py`、`continuous_turn_adapter.py` | slots→required_outputs；prefetch 触发从发酵正则改为 operators |
| 确定性 pack | `market_watch_pack.py` + `strict_signal_pack`（可与 pack 同文件） | 双红/交集/聚合/catalog preflight |
| ReAct（P2） | `headless_tool_gateway.py` | 只在工具缝消费 stop_rules；不把 program 当对方 loop 的宪法 |

### 2.4 首批 operator（覆盖 knevo28 已证「组件在、未接通」）

| operator | 复用组件 | 题族 |
|---|---|---|
| `market.strict_double_red_snapshot` | `signals.DOUBLE_RED_SQL` + `asof_prefetch.dual_red_counts` | A4、C6 |
| `market.cross_table_exact_intersection` | FinanceQuery 双表交集 | B5 |
| `market.aggregate_count` / `market.detail_rows` | count vs limit 明细 | A10 |
| `catalog.preflight` | 表存在/空/截止日无行 | C3、C8 |
| `market.contradiction_audit` | 跨表同日保留冲突 | C5 |
| `theme.research_packet`（P1） | 绑定已有 `ThemeResearchSpec`，不另发明槽 | B1–B3 |

### 2.5 与现有件关系

- **asof_prefetch**：执行器，不重写；`dual_red_counts` 从发酵正则触发改为 operator 触发（发酵题输出**逐字节回归**）。
- **empty_pool_fallback（#349）**：`fallback_policy="empty_pool_one_shot"` 的执行器；不得开第二条 fallback 通道。
- **predicate_faces（#350）**：`DefinitionReceipt.face_id` 为消融缝；生产路径仍不 `import capability_switchboard`。

---

## 3. 输出减法：加深 `view()`（P0-A，先做）

原理（可迁移）：任何 error-code → 用户文案系统，措辞必须收敛到**一个纯函数**。支付风控、API 错误响应是同构问题。仓里这个函数已经叫 `view`。再写第二个，每类新故障都会长一套新文案。

选型：

| 方案 | 是什么 | 本单 |
|---|---|---|
| (a) 强制每 turn 产 PLAN | 模型自己写计划 | **否决**（30/30 证伪） |
| (b) 每题型一个 pack | 模板方法，接线漂 | **否决**（P0-B 用 operator 注册表） |
| (c) 新开 `PublicAnswerCompiler` + `ClaimKind` | 第二张措辞表 | **否决**（v1，#346 会再演） |
| (d) 加深 `session_projection.view`，拆掉出口后缝合 | 减契约管辖权 | **P0-A 选型** |

### 3.1 现状（已有件，不要再发明）

| 件 | 职分 |
|---|---|
| `session_projection.view(TerminalFacts)` | **唯一公开渲染纯函数**。无 IO、无模型。成因：`transient_verifier_outage` / `judge_unavailable_held` / `evidence_gap` / `model_unavailable` / `verified` |
| `answer_model.Claim` + `ClaimStatus` | 已有 typed claim（verified/candidate/inferred/missing/conflict）。不新开 `ClaimKind` |
| `ResearchTaskContract.required_outputs` + completion status | 已兑现 / 未兑现槽。B2 该保留的是**已兑现槽的公开句**，不是「绑定」一词的含糊说法 |
| `ensure_preplaced_gap_sections` | **现役旁路**：在 `view()` 之后把 `【结构缺口】` 缝进 `answer.md` |
| `_gap_answer` | 多调用点，但应只负责填 `TerminalFacts`，不得自己拼用户可见终稿绕过 `view` |

### 3.2 P0-A 必做（活性检查，不是「新文件存在」）

1. **全树公开稿只经 `view()`。** `ensure_preplaced_gap_sections` 不得再改用户可见 `answer.md`。未兑现槽若要说话，必须作为 `TerminalFacts` 字段，由 `view()` 渲成用户语言 unknown，**禁止** `【结构缺口】` / `【质检*】` 进公开稿。
2. **`invalid_repair_finish` 且证据非空 → 成因不得再是 `evidence_gap`。** 开口不得再是「现有证据不足」。已兑现槽的句子进 `TerminalFacts.public`；未兑现槽用用户语言 unknown。
3. **QC=0 靠不拼接，不靠禁语表。** 禁止在渲染层扫 `【质检*】`、`结构缺口`、`证据边界` 当过滤器——那是为每种行为写规则引擎。质检串不得进入 `TerminalFacts`。
4. **false capability → 0** 靠加深 `evidence_capabilities.py` 的 **typed tool receipt 投影**（`research_tool_registry` 的 produces），禁止 dataset→capability 字符串启发。

`view()` 的 `evidence_gap` 分支已支持 `public + gap_body`。P0-A 是让 `_gap_answer` **用上**它，并在拒稿前填 `public=`，不是另写 `compile_public_answer`。

### 3.3 判官不可用（沿用已有两成因，不新开第三扇门）

| 形状 | 已有成因 | 行为 | 本单 |
|---|---|---|---|
| 已标 transient / deadline + `release_safe` | `CAUSE_TRANSIENT_VERIFIER_OUTAGE` | 候选稿 +「没人复核」 | **不重做** |
| 未分类（如裸 `RuntimeError`） | `CAUSE_JUDGE_UNAVAILABLE_HELD` | 不放稿 | **保持**（D1 关单） |

8796 B1 放近完整未复核稿、8792 B2 整篇 gap，是**成因分类不一致**，不是缺第三套政策。禁止用「结构齐 / 有 hash 就放任意 unavailable」当新门。

### 3.4 空表（P0-B 接线后验，P0-A 只保证出口不撒谎）

只公开日历/无行。替代信息若出现，必须经 `view()` 且明示「非原请求」。不在 P0-A 用禁语表修 C3。

---

## 4. 2×2 消融（复用 knevo28 夹具）

| 格 | program | view 加深 | 开关（仅 eval fixture） |
|---|---|---|---|
| Baseline | 否 | 否 | — |
| Subtract-only | 否 | 是 | `publication.view-deepen` |
| Add-only | 是 | 否 | `program.research-program` |
| Both | 是 | 是 | 两项全开 |

- 题集：`frozen/acceptance_cases.json`（SHA `d98a6557…`）+ 每失败族 ≥10 未见改写（实施前封存）。
- 盲评协议复用 `analysis/blind-judge/`；硬事实由确定性 evaluator。盲评是观察，**不是** Both 格的门。
- live 消融等 `R-20260824-09` 同 SHA 双端口；**每次只关一颗开关**。

**预注册判读**：

- Subtract-only：QC marker=0；公开稿无 `【结构缺口】`/`【质检`；非空率不降；B2 形已兑现槽句子保留。
- Add-only：A4/C6/B5 定义+宇宙 100%；A10 精确 aggregate；C8 走 catalog 快路；**允许 QC 仍在**（证正交）。
- Both：上两项硬契约 100%。**禁止**「盲评中位数 ≥ max(组件臂, ReAct 非空)」——那是封上限的评测契约，与「不搬组件 f-string」自相矛盾。

---

## 5. 实施顺序

### P0-A 出口加深（`fix/publication-view-deepen`，独立 PR，可先合）

| 切片 | 文件 | 动作 |
|---|---|---|
| A1 | `session_projection.py` + tests | `TerminalFacts` 能带已兑现槽正文；缺口字段由 `view()` 渲；**不**新开 compiler 文件 |
| A2 | `episode_semantic_verifier.py` | `_gap_answer` 只填 `TerminalFacts`；`invalid_repair_finish` 不得贴 `evidence_gap`；已兑现槽写入 `public=` |
| A3 | `continuous_turn_adapter.py`、`mandatory_satisfiability.py` | `ensure_preplaced_gap_sections` 不再改公开稿（删除调用或改为只写 receipt） |
| A4 | `evidence_capabilities.py`、`research_tool_registry.py`、`episode_issues.py` | typed tool receipt 投影；false capability→0 |
| A5 | 夹具 | B2 形 n≥3 改写；活性：`view` 被调用且 adapter 缝合计数=0 |

### P0-B 输入加法（`feat/research-program-compiler`，**P0-A 合入后**）

| 切片 | 文件 |
|---|---|
| B1 | `research_contract.py`（+ tests）：`compile_research_program` 唯一写 operators |
| B2 | `ask.py` bind 泛化（market_watch 逐字节回归） |
| B3 | `query_understanding.py` 词面→operator（窄门） |
| B4 | `strict_signal_pack`（可与 `market_watch_pack.py` 同文件） |
| B5 | `episode_factory.py`、`episode_tools.py`、`continuous_turn_adapter.py` |
| B6 | `capability_switchboard.json` 仅 eval 登记；生产不 import |

### P1

- `theme.research_packet` 绑定 `ThemeResearchSpec`；KB freshness。
- ReAct / 租用循环：在 `headless_tool_gateway` 按已有 `synthesis_reserve` **拒新工具**；空稿必有 `draft_source ∈ {timeout, provider, usage_limit}`。
- judge attempt ledger（0 秒 attempt）；不新开放稿门。

### P2

- 三 runner 消费同一 program，但租用循环只在工具缝守门。
- 跑完 §4 消融 → `R-20260824-19`。

---

## 6. 台账行（新开）

| ID | 预测 | 验证 |
|---|---|---|
| `R-20260824-12` | B2 形：`invalid_repair_finish` + 证据非空 → 开口不是「现有证据不足」；已兑现槽公开句保留；未兑现槽用户语言 unknown；无 `【结构缺口】` | 夹具重建 + n≥3 改写 |
| `R-20260824-13` | 28 题重放 QC marker=0（靠不拼接）。judge unavailable 同 SHA 仍走已有两成因之一，不新开第三扇门 | 离线重放 |
| `R-20260824-14` | false capability 10/11→0 | capability 单测 + 重放 |
| `R-20260824-15` | A4/C6/B5 改写 100% 注册定义+`.TI` universe | 封存改写组 |
| `R-20260824-16` | A10 aggregate；C8 走 catalog 快路 | 封存改写组 + latency |
| `R-20260824-17` | B1–B3 单槽缺不丢整篇；stale≠no-hit | P1 |
| `R-20260824-18` | 有证据零公开=0；ReAct 空稿 `draft_source` 必填 | 重放 A3/B1/B3/B4/B8 |
| `R-20260824-19` | 2×2 四格按 §4 预注册判读出结论；Both **不以**盲评追平组件臂为门 | 消融批；盲评可附观察 |

---

## 7. 分叉蒸馏路由（`divergence-distill`）

批记录落：`docs/learning/distill/2026-08-24-knevo28.md`（**待人过闸**）

| 分叉 | 池 | 例题 |
|---|---|---|
| plan=null / 严格双红误路由 | harness/runtime P0-B | `arms/8792/A4-dual-red/turn-01/` |
| invalid_repair_finish 整稿丢弃 / 成因误贴 | harness/runtime P0-A | `arms/8792/B2-theme-liquid-cooling/` |
| judge unavailable 两臂走了不同已有成因 | harness/runtime；**不**新开 D1 | `arms/8796/B1-theme-photoresist/` |
| 有证据零合成 / usage-limit | harness/runtime P1（租用循环工具缝） | `arms/react-components/B4-*/` |
| false capability | harness/runtime P0-A | E-003 |
| C3 空表替代快照 | harness/runtime P0-B | `arms/react-components/C3-empty-table/` |
| B7 量价演化读法 | reading_baseline 候选 | component/ReAct B7 |
| 敢下判断 vs 保守拒答 | 视角/user_framework | 盲评 dimensions |
| 单题写法 | experience_cards | C4/C5 |
| 公司事实 | 知识库 ingest（非蒸馏） | B1 正文 |
| C4 golden 漂移 | EVAL only | `golden-drift-audit.json` |

---

## 8. 禁止项

1. 不新增平行 planner；不强制模型产 PLAN。
2. 不把组件臂 f-string 搬进生产；不以组件 95.96 当验收门。
3. 不放宽 `_transient_failure_candidate` 白名单（#346 §8.9）。
4. 不新开 `public_answer_compiler.py` / `ClaimKind`；判官不写公开稿；**`view()` 唯一渲染点**。
5. 不按 case ID 分支；不见改写组不得先看。
6. 8792 vs 8796 不归因模型；单开关需同 SHA。
7. 不用加工具/上下文/重试替代 stop_rules（H2 已证伪）。
8. 未兑现槽不整篇替换成质检报告；不在 `view()` 之后缝 `【结构缺口】`。
9. 脏主树不改 runtime；合 main 等用户确认。
10. A1 与 SPT 不互证。
11. 不把 D1 关单改写成第三扇放稿门；不在渲染层维护禁语表。
12. 不把 `synthesis_reserve` 当成新 schema 字段去「救 ReAct」——那是租用循环工具缝的运行时闸，且排在 P1。

---

## 9. 给执行代理的第一句话

> 先 P0-A（加深 `session_projection.view` + B2 夹具），基线**当前** `gitea/main`。不要新建 `public_answer_compiler.py`。不要把 #349/#350/#352 再修一遍。不要重开 D1。台账从 §6 逐字抄。验收用 knevo28 矿 + 封存改写组，不用 SPT 收据。活性检查是「`view` 被执行到、adapter 缝合=0」，不是「新文件存在」。

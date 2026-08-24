# knevo28 四臂收口：ResearchProgram 输入加法 + PublicAnswerCompiler 输出减法

- 日期：2026-08-24
- 状态：Draft v1（审查 + 规格；**本单只落规格，不施工**）
- 派活索引：`docs/superpowers/plans/2026-08-24-three-layer-execution.md`（三层分账纪律沿用）
- 证据矿（只读）：`~/.finance-runtime/knevo28-four-arm-20260824/`
  - 一页结论：`analysis/one-page-report.md`
  - M2 分诊：`analysis/agent-run-triage-report.md`
  - 既有优化草案：`analysis/workbench-quality-optimization-spec.md`
  - 盲评：`analysis/blind-judge/blind-score-summary.json`
  - 收据：`artifact-receipt.json`（112 case-arm / 120 turn-arm）
- 施工基线：**`gitea/main@af71f048`**（已含 #349/#350/#352）。实验冻结口 8792=`8688545b`、8796=`76ee1e89` **只作证据引用，不作施工基线**。
- 相邻 spec（不重做）：
  - `2026-08-23-publication-and-contract-subtract-design.md`（#346 已合）
  - `2026-08-24-harness-ceiling-and-8796-decouple-followup.md`（D3=#349、D4 第 1 步=#350 已合；**D1 判官不可用放稿、D2 W1/W2 本单 P0-A 收编**）
  - `2026-08-24-market-watch-component-first-design.md`（#352 已合；本单输入侧是它的**泛化**）

## 硬约束

- 缺陷号一律 `R-YYYYMMDD-NN`；本单新行从 **`R-20260824-12`** 起（01–06/08/09/11 已占用）。
- **A1 与 SPT 不互证**；knevo28 收据不得关闭 `R-20260823-SPTTECH-*`，反之亦然。
- 数据块 `D0`–`D11` 是 `evidence_registry` 开关，**不是缺陷单**。
- 从 `gitea/main` 开干净 worktree；pathspec 提交；禁 `git add -A`。
- 原文矿只读；引用带路径。

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

### 0.3 审查裁定：三句话

1. **组件臂赢的正交部分是「现场 ResearchProgram」**（定义、宇宙、槽位、查询程序、停止条件）——不是契约自动提供，也不是文笔。
2. **Workbench 第一次系统性分叉在 plan**：30/30 turn `plan=null`；A4 严格双红仍被编成 `general_finance_qa + operators=[]`，尽管仓内已有 `DOUBLE_RED_SQL` / `dual_red_counts`。
3. **第二次损伤在 judge/publication**：有用草稿整篇丢弃、未复核稿放行、QC 标记进公开稿；ReAct 非空常 96–100 分，但 11/30 空答（有证据无合成预算）。

### 0.4 审查增量发现（相对 Mac 既有草案）

- **#346 漏网出口**：8792@`8688545b`（已含 P0-B）B2 液冷题 `stop_reason=invalid_repair_finish` 仍输出禁语「现有证据不足…未完成核验绑定」——`_gap_answer` 多调用点未收敛，需 **PublicAnswerCompiler 单一出口**（非再打一个补丁）。
- **#352 已前移基线**：`market_watch` 四袋包 live confirmed（R-01..06）；ResearchProgram 是泛化 #352 模式，不是从零发明 planner。
- **8796 vs 8792**：11 胜 / 8 平 / 9 负（+3.64），B2/B3/B5 增益说明**输入侧扩容有效**；两臂各 12 fatal → **共享出口债未解**，禁止归因模型强弱。

---

## 1. 问题四层 + 证据指针

| 层 | 主犯？ | 事实 | 证据指针 |
|---|---|---|---|
| **供给** | 次要 | A5 快路 ~9.6s；ReAct B4 取 97 条证据；空池 #349 已合待 live | `arms/8792/A5-limit-heat/`；`empty_pool_fallback.py` |
| **计划** | **PRIMARY-1** | 30/30 无 plan；A4 误路由；A10 aggregate/detail 未分 | `arms/8792/A4-dual-red/turn-01/continuous-episode.json` |
| **合成** | ReAct 主 | 5 turn 有证据 ~192s 零 draft；usage-limit 连锁空答 | `arms/react-components/B4-fermentation-trace/turn-01/outcome.json` |
| **放行** | **PRIMARY-2** | QC 泄漏 13/12 turn；B2 整稿丢弃；B1 judge unavailable 不一致；false capability 10/11 | `arms/8792/B2-theme-liquid-cooling/`；`arms/8796/B1-theme-photoresist/` |

因果链：

```text
缺 ResearchProgram → 错定义/错查询/过度探索 → 草稿不稳
  → capability/judge 失真 → 无 claim 级编译器
  → QC 泄漏 / 整稿丢弃 / 空答案
```

四臂证伪：只加工具/预算（H2）❌；只加判官（H3）❌。

---

## 2. 输入加法：ResearchProgram（泛化 #352）

### 2.1 原则

- **不新增第四套 planner**；`ResearchPlan` 保留为模型自愿 PLAN 输出。
- **一个编译器** `compile_research_program(...)` → `ResearchProgram`。
- **三个消费者**：Workbench 连续路径、Codex ReAct、确定性 fast path（#352 的 `market_watch_pack` 为第一个已迁移 pack）。

### 2.2 核心类型（新模块 `intelligence/services/research_program.py`）

```python
# 摘要；完整字段见实施时 types 文件
ResearchProgram:
  program_id: str              # 内容寻址 hash，进 trace
  question_class: str            # route_table 题型，不新增题型
  operators: tuple[str, ...]     # 稳定 operator id
  definition_receipts: ...      # 绑定 DOUBLE_RED_SQL / predicate_faces
  query_recipes: ...            # aggregate|detail|timeseries|cross_table + strict_date
  required_fact_slots: ...      # 对齐 episode required_outputs
  synthesis_reserve: float      # 探索预算上限 = total - reserve
  stop_rules / fallback_policy  # 对接 #349 empty_pool_one_shot
  publication_policy: str        # → PublicAnswerCompiler 策略 id
```

### 2.3 接线点

| 消费者 | 文件 | 动作 |
|---|---|---|
| Engine B | `ask.py` | `bind_market_watch_pack` → `bind_research_program`（market_watch **逐字节回归**） |
| Engine A | `episode_factory.py`、`episode_tools.py`、`continuous_turn_adapter.py` | slots→required_outputs；prefetch 触发从发酵正则改为 operators |
| 确定性 pack | `market_watch_pack.py` + 新 `strict_signal_pack.py` | 双红/交集/聚合/catalog preflight |

### 2.4 首批 operator（覆盖 knevo28 已证「组件在、未接通」）

| operator | 复用组件 | 题族 |
|---|---|---|
| `market.strict_double_red_snapshot` | `signals.DOUBLE_RED_SQL` + `asof_prefetch.dual_red_counts` | A4、C6 |
| `market.cross_table_exact_intersection` | FinanceQuery 双表交集 | B5 |
| `market.aggregate_count` / `market.detail_rows` | count vs limit 明细 | A10 |
| `catalog.preflight` | 表存在/空/截止日无行 | C3、C8 |
| `market.contradiction_audit` | 跨表同日保留冲突 | C5 |
| `theme.research_packet`（P1） | KnowledgeAdapter 槽位化 | B1–B3 |

### 2.5 与现有件关系

- **asof_prefetch**：执行器，不重写；`dual_red_counts` 从发酵正则触发改为 operator 触发（发酵题输出**逐字节回归**）。
- **empty_pool_fallback（#349）**：`fallback_policy="empty_pool_one_shot"` 的执行器；不得开第二条 fallback 通道。
- **predicate_faces（#350）**：`DefinitionReceipt.face_id` 为消融缝；生产路径仍不 `import capability_switchboard`。

---

## 3. 输出减法：PublicAnswerCompiler

### 3.1 现状问题

≥3 套出口互不一致：`_transient_failure_candidate`、多处 `_gap_answer`（含 **invalid_repair_finish 漏网**）、8796 conditional release、正文内联 `【质检*】`。

### 3.2 新模块 `intelligence/services/public_answer_compiler.py`

```python
ClaimKind = observed_fact | registered_definition | perspective_rule | inference | unknown

compile_public_answer(program, claims, judge_receipt) -> (PublicAnswer, PublicationReceipt)
```

**确定性规则（摘要）**：

1. 有证据的 observed/registered 且 judge≠rejected → 保留。
2. inference 缺前提 → 软化或删。
3. 非关键槽无证据 → **删除**（不留质检条）；关键槽 → 用户语言 `unknown`。
4. 永不公开：`【质检*】`、`结构缺口`、`证据边界`、`能力缺失`、gate code。
5. judge unavailable → **claim 级安全子集**（有 hash 保留 + 「复核不可用」开口），**禁止整稿丢弃/整稿放行二极**。
6. 空表：只公开日历/无行；替代信息单列且明示「非原请求」（修 C3）。

### 3.3 配套

- **typed capability 投影**：`evidence_capabilities.py` + `research_tool_registry.py` produces 映射（修 false capability 10/11）。
- **出口收敛**：`episode_semantic_verifier.py` 所有 `_gap_answer` 调用点 → 构造 claims → 编译器；`structured_reports.py` 同步清理。

---

## 4. 2×2 消融（复用 knevo28 夹具）

| 格 | program | compiler | 开关（仅 eval fixture） |
|---|---|---|---|
| Baseline | 否 | 否 | — |
| Subtract-only | 否 | 是 | `publication.answer-compiler` |
| Add-only | 是 | 否 | `program.research-program` |
| Both | 是 | 是 | 两项全开 |

- 题集：`frozen/acceptance_cases.json`（SHA `d98a6557…`）+ 每失败族 ≥10 未见改写（实施前封存）。
- 盲评协议复用 `analysis/blind-judge/`；硬事实由确定性 evaluator。
- live 消融等 `R-20260824-09` 同 SHA 双端口；**每次只关一颗开关**。

**预注册判读**：

- Subtract-only：QC=0、禁语=0、非空率不降、B2 已绑定句保留。
- Add-only：A4/C6/B5 定义+宇宙 100%；A10 精确 aggregate；C8 p95≤15s；**允许 QC 仍在**（证正交）。
- Both：上两项 + 硬契约 100% + 盲评中位数 ≥ max(component, ReAct 非空)  per 题族。

---

## 5. 实施顺序

### P0-A 输出减法（`fix/public-answer-compiler`）

| 切片 | 文件 |
|---|---|
| A1 | 新增 `public_answer_compiler.py` + tests |
| A2 | `episode_semantic_verifier.py` 出口收敛（含 invalid_repair_finish） |
| A3 | `evidence_capabilities.py`、`research_tool_registry.py`、`episode_issues.py` |
| A4 | `conversation_orchestrator.py`、`structured_reports.py` |

### P0-B 输入加法（`feat/research-program-compiler`，**P0-A 合入后**）

| 切片 | 文件 |
|---|---|
| B1 | `research_program.py` + tests |
| B2 | `ask.py` bind 泛化 |
| B3 | `query_understanding.py` 词面→operator（窄门） |
| B4 | `strict_signal_pack.py` |
| B5 | `episode_factory.py`、`episode_tools.py`、`continuous_turn_adapter.py` |
| B6 | `capability_switchboard.json` 登记 |

### P1

- `theme.research_packet`；KB freshness；`synthesis_reserve` + `draft_source`；`ProgramRevision`；R-04 未注册阈值；judge attempt ledger。

### P2

- 三 runner 同 program；跑完 §4 消融 → `R-20260824-19`。

---

## 6. 台账行（新开）

| ID | 预测 | 验证 |
|---|---|---|
| `R-20260824-12` | B2 形：repair+unavailable+证据非空 → 禁语=0，已绑定句保留 | 夹具重建 + n≥3 改写 |
| `R-20260824-13` | 28 题重放 QC marker=0；judge unavailable 同 SHA 同一安全子集 | 离线重放 |
| `R-20260824-14` | false capability 10/11→0 | capability 单测 + 重放 |
| `R-20260824-15` | A4/C6/B5 改写 100% 注册定义+`.TI` universe | 封存改写组 |
| `R-20260824-16` | A10 aggregate；C8 p95 快路 | 封存改写组 + latency |
| `R-20260824-17` | B1–B3 单槽缺不丢整篇；stale≠no-hit | P1 |
| `R-20260824-18` | 有证据零公开=0；`draft_source` 必填 | 重放 A3/B1/B3/B4/B8 |
| `R-20260824-19` | 2×2 四格 §4.3 全出结论 | 消融批 + 盲评 |

---

## 7. 分叉蒸馏路由（`divergence-distill`）

批记录落：`docs/learning/distill/2026-08-24-knevo28.md`（**待人过闸**）

| 分叉 | 池 | 例题 |
|---|---|---|
| plan=null / 严格双红误路由 | harness/runtime P0-B | `arms/8792/A4-dual-red/turn-01/` |
| invalid_repair_finish 整稿丢弃 | harness/runtime P0-A | `arms/8792/B2-theme-liquid-cooling/` |
| judge unavailable 不一致 | harness/runtime P0-A | `arms/8796/B1-theme-photoresist/` |
| 有证据零合成 / usage-limit | harness/runtime P1 | `arms/react-components/B4-*/` |
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
2. 不把组件臂 f-string 搬进生产。
3. 不放宽 `_transient_failure_candidate` 白名单（#346 §8.9）。
4. 判官不写公开稿；编译器唯一渲染点。
5. 不按 case ID 分支；不见改写组不得先看。
6. 8792 vs 8796 不归因模型；单开关需同 SHA。
7. 不用加工具/上下文/重试替代 stop_rules（H2 已证伪）。
8. 非关键槽缺失不整篇替换成质检报告（B2 教训）。
9. 脏主树不改 runtime；合 main 等用户确认。
10. A1 与 SPT 不互证。

---

## 9. 给执行代理的第一句话

> 先 P0-A（`public_answer_compiler.py` + B2 夹具），基线 `gitea/main@af71f048`。不要把 #349/#350/#352 再修一遍。台账从 §6 逐字抄。验收用 knevo28 矿 + 封存改写组，不用 SPT 收据。

# 三层规格执行清单

> **For agentic workers:** 本文件是**派活索引**，不是从零 TDD 实现计划。一次接一张单。规格正文仍是下面两份 spec，本清单只回答「接哪张、改哪些文件、用哪个 R 号、什么算完成」。合 `main` / 切 8792·8796 / 合 #343 必须等用户明示。

**Goal:** 下一只手打开这一页就能派活，不会把 84/98 套到 Knevo A1，也不会把数据块 D 号当成缺陷单号。

**Architecture:** 三层分账——供给（桌上有没有观察值）/ 上下文（合同与 as-of）/ 放行（端盘撤不撤稿）。Harness followup spec 管放行减闸与空池加输入；盘面包 spec 管供给换座位。缺陷号只从 `docs/prediction-ledger.md` 发 `R-YYYYMMDD-NN`。

**Tech Stack:** 从 `gitea/main` 开 `/Users` 干净 worktree；解释器 `.venv-workbench/bin/python`；提交只用 pathspec。

**规格正文（本清单不重写）：**

| 线 | 路径 | 管哪一层 |
|---|---|---|
| Harness followup v3 | `docs/superpowers/specs/2026-08-24-harness-ceiling-and-8796-decouple-followup.md` | 放行减闸、空池加输入、同 SHA |
| 盘面包 v2 | `docs/superpowers/specs/2026-08-24-market-watch-component-first-design.md` | 供给换座位（A1） |

盘面包规格已进实施树：`/Users/a77/fwp-wt-market-watch-component-first` @ `feat/market-watch-component-first` tip `5ad0f60b`（live 探针当时的产品 SHA 是 `d90db195`，其后一笔只回填台账）。脏主树仍可能留着未跟踪副本，**不要在脏树改 runtime**。

基线：`gitea/main@4dd96f6f`（#349 空池 + #350 开关板第 1 步）。**本盘面包分支还落后 main**（缺 #349/#350），合入前先接到今日 main，再跑全量。合入 ≠ 生产生效。8792 仍 `8688545b`，8796 仍 `76ee1e89`。

---

## 0. 开工（每只手都做）

- [ ] **Step 1: 认树** — `git worktree list` + `git status --short` + `git branch --show-current`。主检出 `feat/reading-rules-baseline-batch1` 已弃用。完成：cwd 是从 `gitea/main` 开的干净树，或本 spec 树（只改文档）。
- [ ] **Step 2: 读编号法** — 本文件 §1。完成：本轮要用的号已经在 prediction-ledger 里对上，没有新发明号段。
- [ ] **Step 3: 认实验** — 本文件 §2。完成：能说出本轮题属于 A1 还是 SPT，不会互证。
- [ ] **Step 4: 接一张单** — §4 / §5 / §6 里只勾一张。完成：R 号、规格路径、落点文件、完成判据四件齐全后再改代码。

---

## 1. 编号法

三套号，主人不同。派活只许用 R 号 + 文件路径。

| 号 | 主人 | 例子 | 派活用法 |
|---|---|---|---|
| `R-YYYYMMDD-NN` | `docs/prediction-ledger.md` | `R-20260824-01`…`11` | **唯一缺陷/闸号** |
| 数据块 `D0`–`D11` | `intelligence/services/evidence_registry.py` 的 `ProviderSpec` | D1 市场价值、D2 证据硬度、D3 二阶导（`include_second_derivative_block`）、D8 题材历史类比、D10 市场情绪 | **不是缺陷单**。改这些开关会动 ask 数据块 |
| Knevo 台账 `#1` / `#2` / `#2b` | `docs/learning/knevo-vs-workbench-技能包对比台账.md` | `#2b` = web-access 第二 provider | 对照用台账既有号，**不要另起 KC-xx** |

Harness spec 正文里的「D0–D4」是该 spec **内部别名**，对外已经发过 R 号：

| spec 内部 | R 号 | 状态 |
|---|---|---|
| D0 周一复验 | `R-20260824-10` | confirmed |
| D1 判官分类 | `R-20260824-07` | confirmed（关单，零产品 diff） |
| D2 W2 | `R-20260821-08` | confirmed |
| D2 W1 | `R-20260821-07` | pending（欠真 `marker_loss>0`） |
| D3 空池 fallback | `R-20260824-08` | 已合 #349；live 仍 pending |
| D4 第 1 步开关板 | `R-20260824-11` | 已合 #350；live 仍 pending |
| D4 同 SHA | `R-20260824-09` | pending（未切端口） |

`R-20260824-01`…`06` 属于盘面包，**禁止**把清单三条重发成 `R-20260824-07`/`08`/`09`。

---

## 2. 两场实验（不得互证）

| | Knevo A1 盘面 | SPT 指数×科技 |
|---|---|---|
| 目录 | `~/.finance-runtime/four-arm-knevo-20260823/A1-market-overview/` | `~/.finance-runtime/trace-diff-spt-index-tech-20260824/` |
| 题 | `2026-07-23 今天市场怎么样`，`question_type=market_watch` | 指数 × 科技（周一题另一场） |
| 病 | Engine A 抢成文；首轮 `TimeoutError`、0 tool_call → `deadline_exhausted`；修复轮才取数 | 8796 公开稿写「本轮已取得 84 条证据」，对照表 `answer_chars=98`；判官 `RuntimeError` fail-closed 剥稿 |
| 层 | **供给**（座位错了） | **放行**（端盘撤稿） |
| 药 | 盘面包换座位 `R-20260824-01`…`06` | 分类器补洞；已关单 `R-20260824-07` |
| 四臂真名 | `workbench-8792` / `workbench-8796` / `codex-component` / `live-toolkit` | 不要和另一场 React/组件臂混称 |

A1 实测（本轮复算，树内无「84」字段）：

| 臂 | 字符 / 汉字 | evidence | 工具 | 停法 |
|---|---|---|---|---|
| workbench-8792 | 765 / 446 | 8 | 修复轮 2（`finance_query` + `mainline_context`） | `repair_model_finish` |
| workbench-8796 | 700 / 462 | 9 | 修复轮 2（两次 `finance_query`） | `repair_model_finish` |

84/98 是 SPT 放行层事故，**不能**用来证「取数越好删得越狠」，也**不能**派给 A1「先拆输出闸」。

---

## 3. 三层分账

问两句（followup spec §0.3）：这是给桌上加观察值，还是给端盘加限制？模型变强会不会更惨？

| 层 | 管什么 | 现役落点 | 下一刀 |
|---|---|---|---|
| **供给** | 开口前桌上有没有规定查询 | `asof_prefetch.collect_prefetch_items`（存在，审查说零命中是错的）；`empty_pool_fallback.py`（R-08，治「查了但空」）；盘面四袋尚未换座位 | A1 → 盘面包 `run_market_watch_pack` |
| **上下文** | 合同、as-of、开关板 faces | `AskOptions` / as-of 预取；开关板已合、serving **不** `import capability_switchboard` | 同 SHA（R-09）；#343 另点头 |
| **放行** | 稿子撤不撤 | `_transient_failure_candidate` + `_sanitize_public_answer`；裸 `RuntimeError` fail-closed | **不要再做**。R-07 已关单 |

空池 fallback（R-08）治「查了但空」。A1 是「首轮没查」。资讯 as_of 全滤是 `R-20260820-07`（T2-a），不是 R-08。

---

## 4. 已关 / 已合（不要再做）

| 单 | R 号 | 状态 | 完成判据（已满足） | 禁止再做 |
|---|---|---|---|---|
| 周一原题复验 | `R-20260824-10` | confirmed | `docs/verification/2026-08-24-p0c-monday-recheck.md`；三变量绿；不是 A1 | 用 A1 `partial` 重开 P0-C |
| 判官分类 | `R-20260824-07` | confirmed 关单 | `docs/verification/2026-08-24-judge-transient-unwrap.md`；零产品 diff | 第三扇放稿门；`RuntimeError` 整类加白；结构齐就放 |
| W2 | `R-20260821-08` | confirmed | 指数×科技 8792：`chain_mapping.required=False` + 显式缺口 | 重开 `fix/mandatory-satisfiability` |
| 空池 fallback | `R-20260824-08` | 已合 #349 | `intelligence/services/empty_pool_fallback.py`；主循环 `_maybe_execute_empty_pool_fallback`；离线正控/负控绿 | 写进判官 / `_gap_answer`；预取焊死「双红+每块前 2」；当 A1 的药 |
| 开关板第 1 步 | `R-20260824-11` | 已合 #350 | 新文件开关板/faces/词汇/runner + `dual_red_counts` 最小 `faces()` | 生产路径 `import capability_switchboard`；把超集树当解耦版再拆一遍 |
| 盘面包拒收 / 站立日 / 四袋 / 洞 1 | `R-20260824-01`/`02`/`03`/`05` | 分支已做，等合入 | 干净树 `feat/market-watch-component-first`；A1 live 双态包上桌；首步非 `deadline_exhausted` | 把 84/98 套过来；加 prompt / repair / 质检；当已合 main |
| 盘面包休市 P0 | `R-20260824-06` | 分支已做，等合入 | 离线 #5a 包停 + `compose=False`；live §7.5 休市句、无 07-24 数 | 把 live `lane_direct_answer` 短路写成「包跑完」。包跑完只被单测锁住 |
| W2 自然样本文档 | — | 已写 | `docs/verification/2026-08-24-d2-w1-w2-natural-sample.md` | 把结构 `partial` 水印写成 W1 |

审查已裁定、照抄不重打：三层分账留下；算子绑供数不绑题型；IMA 留 ingest（`research_judge.py` 已把 ima 类 `update_type` 打成 candidate；`path_registry.json` 的 `ima_stock_ingest` 不是第 13 个 episode 工具；登记表仍 12 工具；`skill_tools.py` 只开 `serenity-alpha`）；否决 IMA runtime 工具 / 全 LLM 路由 / 技能桥外呼 / 无溯源数值概率。`history_analog` → 数据块 D8，不是 D10。涨停热度块已有，A1 是开口前没跑。

---

## 5. 等用户点头（产品代码先停）

| 勾 | 单 | R 号 / PR | 完成判据 | 禁止 |
|---|---|---|---|---|
| [ ] | 盘面包合入 `gitea/main` | Gitea **#352** @ `5840e537` | 已接到 `4dd96f6f`；本机 6267 passed / 0 failed。**合入仍等用户点头** | 未点头就 API merge；切 8792/8796 |
| [ ] | 8792 与 8796 同 SHA 启动 | `R-20260824-09` | 两端口 `source_revision` 相同；users_dir 可分开；health 承认 8796 = 同 rev sidecar | 把合 main 写成 confirmed；未点头就 `launchctl` 切 |
| [ ] | `reading_baseline` | Gitea #343 | 用户明示后再合；与开关板拆开 | 从脏树 rebase / 从本清单当授权 |
| [ ] | Knevo 台账 #2b 回写 | Gitea #351 @ `b996324d` | 仅文档；合入后优先级表与代码落点一致 | 当产品单再接线（已接线：`market_news.fetch_web_access_news_result`） |

---

## 6. 盘面包 P0（A1）— 已在干净树做完，等合入

独立规格，勿与 harness 内部 D0–D4 混。号：`R-20260824-01`…`06`。**不要再开第二棵实施树重做。**

**一句话：** `market_watch` 进 `DETERMINISTIC_OWNER_TYPES`，汇合处（`if owner_output is not None` **之前**）跑 `run_market_watch_pack`。模型只写格与格冲突的残差。

**2026-08-24 独立验收：** R-01/02/03/05 过线。R-04 仍 P1。R-06 公开稿过线，live 走的是 `lane_direct_answer`（旧椅），包停只被单测锁住。收据 `~/.finance-runtime/mwcf-live-20260823/`。

**树（已存在）：** `/Users/a77/fwp-wt-market-watch-component-first`。合入时接到今日 main，不要另开一棵重做。实施顺序当时按 spec §10：先拒收 → 先落地洞 1 → 再竖切站立日 → 再竖切四袋。`ask_blocks.py` 未改：选了 §6.1 (ii)，包查、块渲染。

**判别变量（只锁这一条）：** 冻结题「2026-07-23 今天市场怎么样」在模型开口之前，四袋已跑完（总量 / 主线 / 严格双红 / 涨停热度），格内数字进公开稿且不可被模型改口径。

### 6.1 文件（从盘面包 spec §8 抄，实施按那份）

| 动作 | 文件 | 职责 | 序 |
|---|---|---|---|
| Modify | `intelligence/runtime/continuous_turn_adapter.py` | `DETERMINISTIC_OWNER_TYPES` 加入 `market_watch` | P0-1 `R-01` |
| Create | `intelligence/services/market_watch_pack.py` | `run_market_watch_pack`：显式日 `=` 查四袋 | P0-2/4 `R-02`/`R-03` |
| Modify | `intelligence/services/ask.py` `_resolve_market_data_context` | 显式日无行不得回显问句日 | P0-2 `R-02` |
| Modify | `intelligence/runtime/conversation_orchestrator.py` | owner 分叉**之前**调包；休市/empty 则 `replace(compose=False)` | P0-3 `R-05`/`R-06` |
| Modify | `intelligence/services/ask.py` `_answer_market_review` | 只渲染包，不再 `<= as_of` 查库 | P0-3/4 |
| 未改 | `intelligence/services/ask_blocks.py` | 选 §6.1 (ii)：包查、块不改 | P0-2/4 |
| Modify | 编排器或 `_answer_market_review` 一处 | Engine B 调 `calendar_disclosure` / `with_calendar_disclosure` | P0-3 `R-06` |
| Modify | `intelligence/runtime/glm_agent_runtime.py` | `market_watch` 移出 `_SYNTHESIS_HEAVY_QUESTION_TYPES` | P0 防回退 |
| Test | `intelligence/tests/test_market_watch_component_first.py` | spec §7.1–7.3 | P0 |
| 收尾 | `docs/prediction-ledger.md` | `R-01`…`06` 回写 | 收尾 |

P1（本刀不做）：未注册阈值删句；`market_data` 记账；`R-20260824-04`。

### 6.2 完成判据

- A1 冻结题：第一动作不是 `deadline_exhausted`；四袋齐；锁格数字；双红名单；无未注册阈值上桌。主树有无 `2026-07-23-daily-review.md` 都要过洞 1。
- P0 休市题必须是 `2026-07-25 今天市场怎么样`（不是 C1 原题「2026-07-25 市场怎么样」）。
- C1 原题只做旁路回归锁，不改路由成 `market_watch`。
- 合 main 等用户确认。

### 6.3 本刀禁止（正招写在上面）

换座位 + 汇合处跑包。不要：加 prompt「请先查双红」、加一轮 repair、加更严质检、产品内嵌完整 ReAct、把 `daily-review` 降成证据贡献者、改 `honesty_gates` 判定、动 8792/8796、在脏树改 runtime。

---

## 7. 仍欠现场 / P1（不挡盘面包）

| 勾 | 单 | R 号 | 完成判据 | 何时做 |
|---|---|---|---|---|
| [ ] | W1 自然样本 | `R-20260821-07` | 真 `marker_loss>0` 的 run：残块仍在、无道歉横幅。结构 `partial` 水印 ≠ W1 | 等现场；零产品代码 |
| [ ] | 空池 live | `R-20260824-08` | 空池题 `fallback_query=true` 且 as-of=问句日；`market_watch` 不触发 | 8792 切到含 #349 的 SHA 之后 |
| [ ] | 资讯 as_of 披露 | `R-20260820-07` | T2-a：越界条标注后交付，不静默 0 条 | 质量稿线，不是本清单 P0 |
| [ ] | D4 P1 单开关消融 | `R-20260824-09` 的 P1 | 启动器注入关一颗；serving 仍不读板；差量 > 1 禁止归因 | 同 SHA 之后；本批不挡 |
| [ ] | Knevo 对照未接线项 | 台账既有 `#` 号 | 反方检索先查 `evidence_search` 是否已声明再接线；两跳/召回四问可 P1 | 不要发明 KC-xx |

---

## 8. 接单第一句话

> 派活读 `docs/superpowers/plans/2026-08-24-three-layer-execution.md`。盘面包 P0 是 Gitea **#352** @ `5840e537`，已接到今日 main、全量绿，等用户点头再合。增加输入必要就加，限制输出只做减法。不要擅自切端口 / 合 #343。

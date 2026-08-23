# 设计：发布门减法 + 合同兑现（周一五臂之后）

- 日期：2026-08-23
- 状态：Draft v1.1（质检收口：F1–F6 已回写；P0-A 可合；P0-B 按 v1 的 §6.2 落地会验收不过；P0-C 可施工但按本节改过的三处写）
- 质检：2026-08-23 本树实跑（`.venv-workbench`）。Q1/Q2 信封复现、P0-A `110 passed`（收据 `20260823T093846Z-2f0d8ce9.json`）。§4 原 14 条行号点查通过；本版补 15–20 并修正 9/11/12。
- 分诊：`~/.finance-runtime/trace-diff-spt-tech-med-monday-20260823/`（五臂）
  辅证：`~/.finance-runtime/trace-diff-spt-ysjs-20260823/`（有色，8796 判官挂）
- 代码树：P0-A `/Users/a77/fwp-wt-publication-gate`（`fix/publication-gate-lamp`）；P0-B `/Users/a77/fwp-wt-judge-honesty`（`fix/judge-honesty-p0b`）；P0-C `/Users/a77/fwp-wt-contract-honor`（`feat/contract-honor-p0c`）。底都是 `gitea/main@3ac070a2`。禁止在主检出脏树上改
- 相邻：`2026-08-23-operator-prefetch-os-design.md`（空 manual 覆盖 + D10，P0 已合 `#345`）；`docs/handoffs/inflight/fix-publication-gate-lamp.md`（本单 P0-A）
- 账本：`docs/prediction-ledger.md` 的 `R-20260823-SPTTECH-*`（`-04` 仍 pending，本单不证）

## 0. 一句话

周一这题**不是被限制**，是**合同没覆盖到 + 执笔弄砸 + 端盘多写**。先减公开层的谎和附录，再把问句里已经点名的主语和个股格子写进现有信封，**不加检索、不追活工具包成稿、不把天花板当 runtime**。

人话：后厨取到了菜，菜单没写「科技 / 医药 / 观察哪些个股」，端盘又把质检小票和没登记的数字一起端上去。本单改菜单和端盘，不换灶、不加菜。

**判别变量**（合入后离线必须锁死；live 切流另等点头）：

| # | 冻结题面 | 必须成立 |
|---|---|---|
| 1 | 周一题（§5.1） | `subject` 同时带上「科技」和「医药」（双主语或两个主语槽）；不得空串 |
| 2 | 同一题 | `required_outputs` 含个股观察格（`company_mapping` 或本单新增的同义格）；描述要求 **名单 + 代码 + 角色（机会 vs 出清）** |
| 3 | 「分析下有色金属…」 | `subject` 是「有色金属」，不得以「下」开头 |
| 4 | 研究 `outcome=partial` 且运输 `turn=completed` | 投影灯是 `partial`，不得再被运输完成盖成 `complete` |
| 5 | 公开 `answer.md` / `result.content` | 不得含 `## 输出质检` |
| 6 | 语义判官走 **gap 路径**（未放稿） | 整段公开正文（开口 **和** `gap_body`）禁止「现有证据不足 / 未完成核验绑定」；必须说复核不可用 |
| 7 | 同上，且 draft 非空、结构 `completed`、失败已被显式标成 transient+release_safe | 走已有 `_transient_failure_candidate`，稿在、开口为复核超时/不可用 |
| 8 | 判官挂 + 无可放稿（draft 空，或不满足结构/partial 放行） | 仍走 gap，但措辞按 #6，不得假装「没查到」 |

`pending_rejudge=true` 在 `judge_status=="unavailable"` 时**今天就成立**（`:563`，gap 路径 `:1011` 已传）。#7 不是新字段。P0-B 的新工作是 #6 和 #8 的**文案**，以及夹不清时**不要**把裸 `RuntimeError` 整类放进 #7。

P0-A（4、5）代码已在 `2f0d8ce9`，质检实跑绿，未合 main、未切 8792。P0-B / P0-C 待写。未注册阈值是 P1。

---

## 1. 为什么是减法，不是检索加法

### 1.1 这题和早上那题不是同一种病

| 样本 | 失败形状 | 本单态度 |
|---|---|---|
| 早上历史类比（空 `manual + []` 盖信封） | **被限制**：细路由认了 `comparison_analog`，门口保安先盖成 `general_finance_qa`，D10 没上桌 | 已修（`#345`）。本单不重做 |
| 下午有色 8796 | **被限制 + 说谎**：66 条证据齐，`issue=semantic judge provider error`，`exc_class=RuntimeError`，公开开口「证据不足」+ `gap_body`「未完成核验绑定」 | P0-B 改 **gap 文案**（及分类器是否放稿的显式张力），不改取数 |
| 晚间周一科技+医药 | **没覆盖 + 端盘脏**：信封 `general_finance_qa` + `scenario_tree`，**subject 空**；问了「观察哪些个股」却没命中 `company_mapping`；8792 取到了药明/恒瑞/沃森/旭创，公开仍漏代码、挂质检附录 | **本单主战场** |

「被限制」= 厨房有菜、菜单没授权、模型够不着。周一题的供数对照已经证明：主线、科技双红、个股都取到了。再加预取是给已经有菜的桌子加一份菜单复印件。

### 1.2 活工具包 5/5 不是产品该追的上乘

五臂里「活工具包」是 **Cursor 现场写**，看见医药双红空就改查成交额前排。那是人在回路里改查询，不是产品 runtime。5/5 有自评偏斜。组件天花板是编码时冻住的 f-string，运行时零模型，**不是 A/B 对手**。

本单验收只锁信封 / 供数 / 端盘，**不锁答卷措辞**。任何「让 GLM 写成活工具包那样」的结论退回本节。

### 1.3 8792 / 8796 不是「只差一个开关」

整包 revision 不同（`gitea/main@3ac070a2` vs 解耦 `4a35944e`）。相交层（路由、D10、FinanceQuery）应对齐；正交层（loop、发布、判读卡）可以不同。本单改的是相交合同 + Workbench 正交的发布门。**只切 8792**；8796 另包，禁止拿 n=1 有色拒答证「8796 判官更严」。

---

## 2. 范围

### 2.1 做

**P0-A 发布门（已写 `2f0d8ce9`，待合 / 待切）**

- `status_projection.coalesce_episode_status`：`turn=completed` 且 `outcome ∈ {partial, degraded}` → 返回 outcome。
- 公开路径走 `_public_answer_text`，不再 `_with_review_appendix`。后者只留给 V8/W1 单测拼内部附录。

**P0-B 判官诚实理由**（v1.1：改的是文案生成点，不是只改 cause）

- 两条出口，两套验收，禁止混成一句「改 cause」：
  - **已接好的放稿口**：白名单 issue → `_transient_failure_candidate` → `CAUSE_TRANSIENT_VERIFIER_OUTAGE`。开口句已在。`pending_rejudge` 已在。本单**不**把裸 `RuntimeError` / 兜底 `"semantic judge provider error"` 整类加进白名单。
  - **fail-closed 的 gap 口**（8796 实测走这里）：必须改 `_gap_answer` 的 **body**，或让 `judge_status=unavailable` 根本不进 `_gap_answer`。只改 cause / 只加 `is_judge_service_unavailable` **拿不掉**「未完成核验绑定」。
- 用户看见的是「没人复核」，不是「没查到」。无可放稿时也是这句，不是空盘装证据不足。

**P0-C 合同兑现（现有信封，不加层）**

1. **双主题主语**：只走**句式路**（`A和B板块` / `A与B板块` / `A、B板块`）。**不**走 `_theme_aliases()`（41 条细题材，无「科技/医药/有色金属」；补词表会牵动 `resolve_theme_research_spec` 的 pack）。触发面必须先窄：复用 `_compositional_theme_subject` 那道门（`len(operators) >= 2` 且含 `scenario_tree`）。因此施工顺序是先扩 `company_mapping` 词表（周一题变成两算子），再抽联合主语。`subject="科技、医药"` 已核实能过 `_safe_subject`。
2. **个股观察格**：扩 `_COMPANY_MAPPING_RE`（爆炸半径已扫过：现有测试 0 条会被新词面误中）。收紧 `_OUTPUT_DESCRIPTIONS["company_mapping"]`，不要新算子、不要 `watchlist` 格。
3. **别吃「下」**：禁止「凡是前缀下都剥」。真实坏结果是 `分析下游化工板块` → subject=`游化工`（不是「下游」）。算法见 §6.3。单测必须断言 `== "下游化工"` 且 `!= "游化工"`。

### 2.2 不做

- 不写 prompt「请写出股票代码」。
- 不追活工具包 / 组件臂成稿，不把天花板当 runtime。
- 不把周一题改路由到 `theme_analysis`（情景树对「周一会怎么样」可以成立；错的是主语和个股格）。
- 不做检索加法：不焊死「双红 + 每块前 2」。医药双红空时那条预取会再交白卷。
- 不先合解耦、不切 8796、不把 D10 注册成第 13 个 agent 工具。
- 不恢复 `or skill_mode == "manual"`。
- 不在 P0 做未注册阈值扫描器（8796 的 110–120%）。P1 才做；P0 只在 §8 写禁令。
- 不证 `R-20260823-SPTTECH-04`（8796 非法首动作 / 判官 revision 因果）。
- 不改 `route_table` capabilities，不加 web_search mailbox（另单）。

---

## 3. 术语

| 词 | 含义 |
|---|---|
| **信封** | `question_type` + `subject` + `required_outputs` + `allowed_capabilities`。路由盖章的对象。 |
| **合同兑现** | 问句已经点名的主语和必答格，必须出现在信封里。不是新层，是现有 `_required_outputs` / `_explicit_theme` 的缺口。 |
| **发布门** | 研究终态 → 用户看见的灯和正文。运输完成 ≠ 题答完；质检附录不是正文。 |
| **天花板 / 组件臂** | 编码时写死查询 + 冻住的 f-string。评测上界，不是生产对手。 |
| **活工具包** | 人（或 Codex）拿 `FinanceQuery` 边查边写。本仓五臂里是 Cursor 代跑，不是网页 GLM。 |
| **相交 / 正交** | 相交：DuckDB、`decide_turn`、D10、`FinanceQuery`、视角。正交·Workbench：入口、loop、发布门、`skill_mode`。正交·组件臂：写死查询。 |
| **pending_rejudge** | 稿在、绑定未经过判官。对外说复核挂了，不说证据不足。 |
| **未注册阈值** | 公开正文里的百分比/金额/家数，证据账本和 bindings 对不上。编造或印象流。 |

---

## 4. 已核实事实（实施时不要再探一遍）

行号以本树 `fix/publication-gate-lamp`（底 `3ac070a2`）为准。五臂产物在仓外 runtime 目录。

1. `_COMPANY_MAPPING_RE`（`query_understanding.py:370`）只有 `有哪些公司|哪些公司|受益公司|公司映射|核心公司`。**「观察哪些个股」不命中**。所以周一题有 `scenario_tree`、没有 `company_mapping`。
2. `_required_outputs` 是算子→格子的纯映射（`:885-899`）。`company_mapping` 算子一旦在，格子就在。不必改 `route_table`。
3. `_OUTPUT_DESCRIPTIONS["company_mapping"]`（`episode_factory.py:118`）现在是「列出主题相关的公司与角色」，**没要求代码**。收紧描述即可让判官 / gap 标签看见「代码」；不要靠 prompt 求情。
4. `_EXPLICIT_CUE_RE`（`:118`）是 `研究|分析|看看|深挖`。`_explicit_theme`（`:987-1000`）取 cue **之后**的尾巴再 `_EXPLICIT_TOPIC_RE`。`分析下有色金属板块` → tail=`下有色金属板块` → subject=`下有色金属`。这是契约债，不是模型口误。
5. `_EXPLICIT_TOPIC_RE`（`:119-121`）一次只吃一段 `…板块`。`周一科技和医药板块` 若从未走到 `_explicit_theme`（问句没有「分析/研究/看看/深挖」），subject 就是空的——五臂信封正是这个形状。双主题要在「问句点了两个板块名」这条路上补，不能指望现有单段正则碰巧命中。
6. `_safe_subject`（`task_frame.py:497-513`）只做清洗和过长丢弃，**不会**把「科技和医药」拆开，也不会从空 `envelope.subject` 凭空补板块。空主语会一路空到 episode。
7. `scenario_tree` 来自 `parse_scenario_intent`（「周一 / 走势会怎么样」类）。把它改成 `theme_analysis` 会丢掉情景树格。本单保留算子，只补主语和个股格。
8. 五臂供数（除原生网页）：主线=医药+有色；科技双红=通信设备/PCB/数字货币；医药双红=空。8792 取到了药明/恒瑞/沃森/旭创。**取数没有输给活工具包**——活臂是另查的。所以「产品没取到个股」是假。
9. `coalesce_episode_status` 函数起 `:30`，本支改动在 `:44-46`：运输 `completed` 不再盖 `partial`/`degraded`。`gitea/main@3ac070a2` 上这条还不在。
10. 公开路径（本支 `conversation_orchestrator.py`）走 `_public_answer_text`。`_with_review_appendix` 仍在，只供单测。
11. `_gap_answer` 的 **cause** 只由 `is_model_service_unavailable` 二选一（`:2583-2587`），只决定**开口句**。禁语「未完成核验绑定」在 `:2632-2641` 的 `elif verified.outcome.evidence:`，**不看 cause**，只看证据非空。判官挂掉时证据恰恰非空 → 开口改了、禁语照发。`CAUSE_TRANSIENT_VERIFIER_OUTAGE` 开口句已写好（`session_projection.py`），但 8796 **没走到** `_transient_failure_candidate`。
12. `is_model_service_unavailable` 认 `repair_model_unavailable` / `model_unavailable` / `llm_calls==0`，以及 **`usage is None` 时也返回 True**。它管的是「写稿模型没服务成」的开口，**不是**语义判官 provider 挂。有色 8796 的拒答不是「判官更严」，是分类器兜底后进了 gap 文案。
13. 组件臂医药观察池白，是因为规则写死「只从双红取观察股」、医药双红空。那是天花板夹具的编码选择，**禁止**据此给生产焊「双红+前 2」。
14. 数据末日仍是 **2026-08-21**。验收题的「周一」按问句当日理解，供数截断跟库尾，不跟日历星期一。
15. 放稿口已接线（`:988-993`）：issue ∈ {`semantic judge deadline exhausted`, `semantic judge transient provider error`, `LEFTOVER_WINDOW_ISSUE`} 且 `monotonic_release_safe` → `_transient_failure_candidate`。该函数还要求结构 `completed` 或 `_can_semantically_release_partial`（`:1569`），且 sanitize 后 public 非空（`:1578`）。draft 空 → 返回 `None` → 仍走 gap。
16. 分类器 `_stable_semantic_judge_error`（`:4455-4531`）：HTTP 5xx/429、TimeoutError/Connection* 等 → transient。兜底是 `return "semantic judge provider error", False, False`。裸 `RuntimeError("...")` 无 timeout/connection 关键词 → 兜底。注释 `:586-589`：**Fail closed: only explicitly classified deadline/transient failures may opt into deletion-only candidate release。**
17. 8796 收据只有 `issue=semantic judge provider error`、`exc_class=RuntimeError`、`http_status=null`。`_judge_failure_identity` 丢掉异常消息。没有第三段原文可当 marker。把兜底 issue 或整类 `RuntimeError` 加进 `:989` 白名单 = 放宽 §16 的不变量。
18. `pending_rejudge` 在 `judge_status=="unavailable"` 时已是 True（`:563`）。8796 这条今天就成立。
19. `_theme_aliases()` 实测 41 条，全是 PCB / 液冷 / 固态电池 / 低空经济等细题材，**没有**科技 / 医药 / 有色金属（子串也没有）。§5.1 不能靠词表锚。
20. `_compositional_theme_subject`（`:927`）另要求 `parse_midterm_intent` 和 cue。周一题质检：`_explicit_theme=None`、`_compositional=None`、`operators=('scenario_tree',)`。无 cue 的主语抽取是**新触发面**；先窄后宽：扩个股词表让 operators 变成 2 个之后，再用「`len>=2` ∧ `scenario_tree`」这道门抽 `A和B板块`。
21. `_safe_subject` 的 strip 集不含顿号；`科技、医药` 长度 5 ≤ 32，`_QUESTION_LIKE_RE` 只在 >12 字时生效 → 原样返回。联合 subject 流到 `asof_prefetch._pick`（`:196`，精确匹配、禁近似）会变结构缺口（fail closed），与「不加检索」不冲突。
22. 扩 `_COMPANY_MAPPING_RE` 爆炸半径：`intelligence/tests` 里「哪些个股 / 个股有哪些 / 个股的反馈」现有字符串 **0 条**会被新命中。
23. 质检实跑（本树 `.venv-workbench`）：Q1 `operators=('scenario_tree',)`、`required_outputs=('scenario_tree',)`、主语空；Q2 `_explicit_theme='下有色金属'`。P0-A：`test_status_projection.py` + `test_conversation_orchestrator.py` → 110 passed。

---

## 5. 冻结题面与验收

### 5.1 周一题（五臂原题，一个字不改）

```
站在spt视角下，你认为周一科技和医药板块的走势会怎么样，需要观察哪些个股的反馈
```

离线（`decide_turn` / `build_query_envelope` / `build_task_frame`，`llm_complete=boom`）：

- `operators` 含 `scenario_tree`（允许同时含 `company_mapping`）。
- `question_type` **允许**仍是 `general_finance_qa`。本单不把它改成 `theme_analysis`。
- `subject` 规范化后必须同时能认出科技与医药（见 §6.3 的规范化约定）。
- `required_outputs` 含 `company_mapping`（或本单若被迫新增的同义 id——**默认不新增**）。
- 该格 description 含「代码」与「角色」或「机会 / 出清」。

Live（切 8792 之后，空会话，同一题）：

- 公开稿无 `## 输出质检`。
- 若研究 `partial`，灯不是 `complete`。
- 个股段至少有一只带六位代码。本条是 **live 观察**，不是离线红线——模型仍可能漏写；离线锁的是格子在、描述在。

### 5.2 有色「下」债

```
用spt的视角，分析下有色金属板块后续的走势，以及板块内有机会的个股有哪些
```

- `subject` 不得以「下」开头。
- 「有机会的个股有哪些」应命中 `company_mapping`（「个股有哪些」扩词表后）。

### 5.3 判官挂（两条夹具，draft 必须钉死）

「证据账本非空 + 判官挂」**欠定**。放稿要过三关：`monotonic_release_safe` +（结构 `completed` 或 `_can_semantically_release_partial`）+ sanitize 后 public 非空。少写 draft 状态，测试结果会随夹具碰巧绿或碰巧红。

**夹具 B1 — 有可放稿（#7）**

- draft **非空**，结构 `verified_status=completed`（或显式允许的 partial）。
- 失败 issue 必须是白名单里**已经**存在的那三条之一（deadline / transient provider / leftover window），`monotonic_release_safe=True`。
- 期望：走 `_transient_failure_candidate`；公开含复核开口 + 稿；`pending_rejudge=true`（已成立，作回归不是新断言）。
- **不要**用裸 `RuntimeError("...")` 当本夹具的输入——今天它不在白名单，走的是 B2。

**夹具 B2 — 无可放稿 / 未显式分类（#6、#8，8796 形状）**

- 证据非空；`issue="semantic judge provider error"`（兜底串）或 draft 空导致 candidate 返回 `None`。
- 期望：可以仍走 `_gap_answer`，但**整段**（`opening_for` + `gap_body`）不出现「现有证据不足」「未完成核验绑定」。
- 开口或等价位置必须说复核/核验服务不可用。
- `pending_rejudge=true`（已成立）。
- 本夹具是 P0-B 的**主验收**。只改 cause、不改 `:2632` 的拼句，本夹具红。

### 5.4 发布门回归（P0-A，已有测试）

保持本支已绿的投影 + 编排器公开稿测试（质检合计 110 passed，含既有编排器套件）。公开稿无质检标题；`completed` 不盖 `partial`。

---

## 6. 怎么改（设计，不是逐步 plan）

### 6.1 P0-A 发布门

已实现。合入条件：本机叶子检查；V8/ceiling 夹具红对照干净 `3ac070a2` 同红，不本单背锅。用户点头后只切 8792。

原理：灯读的是**研究是否答完**，盘子上的是**给用户看的正文**。质检是厨房内部小票。运输层 `completed` 只表示请求没有摔在路上。

替代：把质检折成脚注 / 折叠块——用户还是会看见，五臂已经证明附录在抢注意力。否决。

### 6.2 P0-B 判官诚实（v1 这一节作废，按本段施工）

可迁移点：改对外措辞时要定位**字符串的生成点**，不是成因点。cause 和 body 分层的系统里，改 cause 经常改不动文案——任何 `error-code → message` 渲染层都会踩。

**先认领两条已经存在的路，不要再发明第三条接线。**

```text
判官 report is None
        │
        ├─ issue ∈ 白名单 ∧ monotonic_release_safe
        │         └─ _transient_failure_candidate
        │                 ├─ draft 可发布 → CAUSE_TRANSIENT_VERIFIER_OUTAGE + 稿   ← 已接好
        │                 └─ draft 空 / 结构不够 → None → 掉进下面
        │
        └─ 否则（8796：兜底 issue="semantic judge provider error"）
                  └─ _gap_answer(frame, structural)
                            ├─ cause = 模型不可用 vs 证据不足     ← 只改开口
                            └─ evidence 非空 → 拼「未完成核验绑定」 ← 禁语在这里
```

**本单只做 gap 口的诚实，不做「整类 RuntimeError 放稿」。**

1. **禁止**把 `is_judge_service_unavailable` 兄弟函数当成主落点。它可以辅助开口，但 `:2632` 不读它。§5.3 B2 会红。
2. 正确落点二选一（实现时只挑一个，单测锁死）：
   - **(a) 不进 `_gap_answer`**：`judge_status` 将为 `unavailable` 且 issue 不是白名单时，另写一个小渲染函数，只用 `CAUSE_TRANSIENT_VERIFIER_OUTAGE`（或并列「复核不可用」、不要说超时如果不是超时）+ 可选「稿未放行，可重试」。不拼 `:2632` 那句。
   - **(b) 进 `_gap_answer` 但分流 body**：`:2632` 在 `judge_status=="unavailable"` 或等价信号时**不**拼「未完成核验绑定」；cause 也不得再选 `CAUSE_EVIDENCE_GAP`。
3. **禁止**把兜底串 `"semantic judge provider error"` 或整类 `RuntimeError` 加进 `:989` 白名单。那是放宽 `:586-589` 的 fail-closed：未知判官故障也会放稿，未注册阈值会漏（8792 有色那侧 `repaired` 拦过 2.6 万亿，就是这个门的存在理由）。
4. 若以后要扩白名单：先拿到**未丢弃的**异常文本或 `judge_provider_outcome` 枚举，再加**具体 marker**。8796 现场没有这段文本（消息在 `_judge_failure_identity` 被丢掉）。持久化更细的失败类是**另一张单**，不是 P0-B 的验收。
5. 不要把 `pending_rejudge` 写成新工作。

原理：8796 的用户下一步被「证据不足」骗去换问法；实话是「复核挂了，66 条还在」。放稿是另一件事——没分类的故障放稿，等于拆掉 fail-closed。

替代否决：

| 做法 | 为什么不用 |
|---|---|
| 只加兄弟函数、改 cause | 禁语在 gap_body，§5.3 B2 仍红 |
| RuntimeError 整类 → transient | 放宽不变量；未知故障放稿 |
| 判官挂了重试三次 | 可靠性单；本单先说实话 |
| 再写第四句道歉 | 开口句已有，缺的是走到它、以及 gap 不再撒谎 |

### 6.3 P0-C 主语与个股格

施工顺序锁死：**先扩个股词表，再抽双主语。** 反过来的话，周一题仍是单算子，窄门打不开，就会去写 cue-free 全局抽取（波及 `dated_market_review` / 既有 `general_finance_qa` 断言）。

**1. 个股格（先做）**

扩 `_COMPANY_MAPPING_RE`，至少：

```
有哪些公司|哪些公司|受益公司|公司映射|核心公司
|哪些个股|观察哪些个股|关注哪些个股|个股有哪些|个股的反馈
```

收紧 `_OUTPUT_DESCRIPTIONS["company_mapping"]`：

```text
列出观察名单：股票名称 + 六位代码 + 角色（机会 / 出清或风险），不得只写行业形容词
```

周一题此后 `operators` 应含 `scenario_tree` **与** `company_mapping`（质检基线只有前者）。

**2. 双主题（只走句式，先窄后宽）**

- **不做**词表锚。`_theme_aliases()` 对冻结题面是空转；补「科技/医药」进词表会牵动 `resolve_theme_research_spec` 的 pack，本单不接。
- **不做**「任何含 X板块 的问句都产出 subject」。那是新触发面。
- **做**：在 `len(operators) >= 2` 且 `"scenario_tree" in operators` 时（与 `_compositional_theme_subject` 同一道门；不必复用它的 `parse_midterm_intent` / cue，周一题两样都没有），用句式抽取 `A和B` / `A与B` / `A、B` + `板块|题材`。
- 写入 `subject="科技、医药"`（顿号、问句出现序）。`subject_kind="theme"`。不要为 P0 上 `list[str]`。
- 验收：规范化后同时含「科技」与「医药」。

**3. 别吃「下」（禁止裸剥前缀）**

错误算法：在 `_normalize_explicit_tail` 里无条件加前缀 `下`。质检实测：

```text
分析下游化工板块的机会  →  剥「下」→ 游化工板块的机会  →  subject='游化工'
```

`游化工` 非空、长度合法，能过「subject 不为空」，评审容易看漏。比吃成「下游」更坏。

正确算法（cue 之后）：

1. 若尾巴以**必须保留的「下」复合词**开头（至少：`下游`、`下跌`、`下旬`、`下修`、`下一代`），**整段不剥**。
2. 否则若尾巴以单字口语「下」开头（`分析下有色金属板块`），剥这一个「下」。
3. 「一下 / 一下下」已在 prefix 表，保持。

单测清单（写断言必须用这些字符串，不许用「若吃成下游」）：

| 问句片段 | subject 必须 | subject 禁止 |
|---|---|---|
| `分析下有色金属板块…` | `有色金属` | `下有色金属` |
| `分析下游化工板块…` | `下游化工` | `游化工`、`下游`（若正则只吃到下游也不合格，要带化工） |
| 周一题（扩词表 + 窄门之后） | 同时含科技、医药 | 空串 |

替代否决：LLM 抽主语（08-05 已否）；改路由 `theme_analysis`（丢掉情景树格）；cue-free 全局 `X板块`。

### 6.4 P1 未注册阈值（只钉形状，本单不施工）

公开正文里的数字（百分比、万亿、家数），必须能在 `bindings` 的 evidence hashes 或确定性预取块里对上。对不上 → 删句或降成「未核验，不写入结论」。

8796 周一稿：110–120%、2.1 万亿进了正文，判官却 `passed`。这是加法失败（模型补盘），不是检索不足。修法是发布/绑定门，不是多查一张表。

---

## 7. 替代方案对照

| 方案 | 做什么 | 为什么不用（本轮） |
|---|---|---|
| **A. 本单** | 减发布谎 + 兑现已点名合同 | 对准五臂和有色的已核实分叉 |
| B. 预取焊死双红+每块前 2 | 检索加法 | 医药双红空会再交白；8792 已经取到个股 |
| C. prompt「请写代码」 | 求模型遵守 | 格子不在时 prompt 是空气；格子在时 description 已经够 |
| D. 改路由 `theme_analysis` | 换信封种类 | 情景树仍成立；错的是 subject 空、个股格缺席 |
| E. 追活工具包措辞 | 把产品写成 Cursor 现场稿 | 天花板/人在回路，不是 runtime；5/5 自评偏斜 |
| F. 先合解耦再修合同 | 换整包 revision | 相交层的洞在 main 上就能补；正交 loop 与本题无关 |
| G. 判官挂了就重试 | 可靠性 | 先把谎改掉；重试是另一张单 |
| H. 只切灯、不补合同 | 更小 | 灯修完周一题仍漏代码、主语仍空，用户看见的病还在 |

面试/可迁移：这是 **契约先行（design-by-contract）**——调用方（问句）已经声明了前置条件（两个板块、要个股），被调用方（信封）必须承认。承认之后的履行（模型写不写得出）是另一层。混淆「没声明」和「没履行」，就会去加检索或加 prompt。同类失败在任何「路由盖章 → 工具授权 → 生成」的 agent 里都会出现。

---

## 8. 禁止（写进 PR 描述，违反即打回）

1. 把组件臂或活工具包的成稿当黄金答案做 BLEU / 人工追齐。
2. 为了「看起来像主题研究」改 `question_type`。
3. 新增 agent 工具或打开 `web_search` 邮箱来补个股。
4. 在脏主检出改 runtime。
5. 把 8796 有色拒答写成「解耦更严」而不先复现 provider 异常。
6. 公开正文继续拼 `## 输出质检`。
7. 判官不可用时对用户说证据不足或未绑定（开口 **或** gap_body 任一处都不行）。
8. 恢复空 `manual` 短路。
9. 把裸 `RuntimeError` 或兜底 `"semantic judge provider error"` 整类标成 transient / release_safe。
10. 无条件把「下」加进 `_normalize_explicit_tail` 前缀表。
11. 把「科技 / 医药」补进 `_theme_aliases()` 来过 §5.1。

---

## 9. 切片与依赖

```text
P0-A 发布门     已写 2f0d8ce9    待你点头 → 合 main → 只切 8792
P0-B 判官诚实   依赖 A 的公开路径（同一张盘子，不说谎）
P0-C 合同兑现   与 A/B 正交，可并行；C 内部顺序：个股词表 → 窄门双主语 → 有条件剥「下」
P1   未注册阈值 依赖绑定表稳定，A/B 之后
```

合 A 之前，8792 对照仍会看到质检附录——那是旧盘子，不是合同没兑现。

---

## 10. 施工落点（给下一份 plan 用，本文不拆步）

| 切片 | 主文件 | 测试落点 |
|---|---|---|
| A | `status_projection.py`、`conversation_orchestrator.py` | 已绿，保持。质检 110 passed |
| B | **主落点** `episode_semantic_verifier.py` 的 `_gap_answer`（`:2632` 分流或绕开）以及 `:1006` 那次调用。分类器 `:4455` / 白名单 `:989` **本单只加回归、不放宽** | §5.3 **B2 为主**（兜底 issue + 证据非空 → 全文无禁语）；B1 作已接线回归（白名单 + draft 非空）。`test_gap_answer_middle_tier.py` 里「未完成核验绑定」仅保留给**真的没绑定且判官不是 unavailable**。不要只改 `test_judge_degrade.py` 的 cause |
| C | `query_understanding.py`：先 `_COMPANY_MAPPING_RE`，再窄门双主语，再有条件剥「下」。`episode_factory.py` 只改 description | Q1/Q2 冻结题面 + `分析下游化工板块` → `下游化工` ≠ `游化工`。`llm_complete=boom` |

不写 `recon*` / `probe*`。单点事实用一行 `rg`。v1 的 §6.2 不得再当施工说明。

# 设计：把 workbench 推到组件质量上限 + 8796 解耦收口

- 日期：2026-08-24
- 状态：Draft **v2**（核稿已改定；未施工）
- v1 → v2：D2 从「实现单」改成「W1/W2 自然样本结案」；D0 不再用 Knevo A1 的 `partial` 证 P0-C；D1 拆清 unavailable 两形状；D3 继承 as-of 并与 issue-backfill 互斥；D4 步骤 4 不让生产读开关板；台账号从 `R-20260824-07` 起；续跑 ID 移出正文。见 §0.2。
- 分诊（Mac 只读实况，08-23/08-24）：
  - `~/.finance-runtime/four-arm-knevo-20260823/`（Knevo **A1** = `2026-07-23 今天市场怎么样`，不是周一题）
  - `~/.finance-runtime/trace-diff-spt-tech-med-monday-20260823/`（P0-C 原题）
  - `~/.finance-runtime/trace-diff-spt-ysjs-20260823/`（有色 8796 判官 `RuntimeError` → 剥稿）
  - `~/.finance-runtime/cutover-20260823-8792-8796.md`
  - `docs/verification/2026-08-21-tracediff-cxo-ceiling.md`（**不是终局**，投影删句主犯已拆）
- 相邻（实施前先认领，禁止抢合）：
  - `2026-08-23-publication-and-contract-subtract-design.md`（#346 P0-A/B/C，已合已切 8792）
  - `2026-08-21-ceiling-shape-closeout-design.md`（W1 #309、W2 #307 **已合**；V8 #334 已合）
  - `2026-08-24-market-watch-component-first-design.md`（盘面题拒收 Engine A；已占 `R-20260824-01`…`06`）
  - `feat/reading-rules-baseline-batch1` / Gitea #343（`reading_baseline`，D4 要拆的那包）
  - `2026-08-20-asof-prefetch-dual-red-design.md`（问句日 = 预取日；D3 必须继承）
  - `align/switchboard-p0` @ `76ee1e89`（8796 超集树，开关板 + 判读基线混在一起）
- 端口锚（会漂，开工先重读 health）：
  - 8792 = 生产 workbench（核稿时 `8688545b` dirty=false）
  - 8796 = 解耦超集 + `reading_baseline`（核稿时 `76ee1e89` dirty=false），**不是** 8792 的纯开关分身
- 代码树：禁止在主检出 `feat/reading-rules-baseline-batch1` 脏树上改。每单从 **`gitea/main`** 新开 `/Users` 下 worktree。
- **合 main（含 #343）必须等用户明示。** 不强推。

---

## 0. 一句话

相交组件已经够用；当前还封上限的是正交 harness 的**残余输出闸**（判官挂了把完整稿剥空）。8796 是半解耦：离线开关板在超集树上，live 仍整包换树。本 spec 把「先复验周一原题、再补未标 transient 的放稿口、再让 live 能做单变量消融」写成可接单步骤。

人话：后厨菜够。端盘有时把整桌撤了——但撤桌的那道闸，deadline 型已经能留稿；还没留的是没贴「瞬时故障」标签的 provider-error。W1/W2 的零件已经换过，只欠现场照片。

### 0.1 对用户假设的冻结判定（后续审查不得悄悄改口）

| 命题 | 判定 | 成立条件 |
|---|---|---|
| 组件是相交层，不是 8792/8796 质量差的来源 | **成立** | 有色题 8796 66 条 vs 8792 37 条；周一题 8792 已取到药明/恒瑞/沃森 |
| 正交 harness 限制了相对「Agent ReAct 直调组件」的上限 | **部分成立、时效性强** | 8-21 投影删句已拆；8-23 之后主犯是「未标 transient 的判官 provider-error 剥稿」+ 8796 半解耦。W1/W2 **不是**现役缺口 |
| ReAct 全面优于 workbench | **不成立** | 五臂「活工具包 5/5」标了自评偏斜 + 人在回路；真增量收窄为「空结果换口径再查」 |
| 8796 完全是 8792 的解耦版 | **不成立（半解耦）** | revision 不同；生产不读开关板；混入 `reading_baseline` |

约束三筛（每条新闸必须填）：拦输入还是输出？模型变强会不会更惨？保下限还是封上限？

### 0.2 v2 核稿改定（实施按本节，不是按 v1 的 §4/§6）

| ID | v1 会让实施修错 | v2 |
|---|---|---|
| **洞 D2** | 「`R-20260821-05`、W1/W2 已立项未收口」→ 新开实现树 | R-05 = #296 **confirmed**。W1 = #309 + V8 #334 **已合**，`test_ceiling_required_block_degrade.py` 在 main；Knevo A1 稿头「质检降级…残块保留」是它的 live 显影。W2 = #307 **已合**，`test_mandatory_satisfiability.py` 在 main。台账 `-07/-08` pending 是欠自然样本结案。**D2 = 结案单，零产品代码。** |
| **洞 D0 题面** | §1.1 用「8-24 A1 两臂仍 partial」证 P0-C 没锁死 | Knevo **A1** 题面是 `2026-07-23 今天市场怎么样`，不是周一科技/医药。那个 `partial` 更像 W1/V8 正常降级。D0 的唯一理由：周一原题还没有复验收据。 |
| **洞 D1 形状** | 把一切 `unavailable` 当成同一闸 | 已有两形状。deadline 型（`R-20260821-07` 探针 `run_20260822_002309`）已经能放 540 字。本单只处理**未标 transient** 的 provider-error；优先接进已有 `_transient_failure_candidate`。禁止 RuntimeError 整类加白名单（#346 P0-B）。 |
| **洞 D3** | 只写「空池再查一次」 | 必须继承 as-of（问句日 = 查询日，零泄漏；见 08-20 asof spec + 08-21 换形探针的 08-19 暴跌陷阱）。必须和 `plan_issue_backfill` 划界：同一缺口只能一家补。 |
| **洞 D4 读板** | 「生产路径读开关板」 | 推翻 `capability_switchboard.py`「生产永远不读本模块」。fail-closed 会打挂 serving。步骤 4 三选一，推荐**启动器注入**。 |
| **洞 台账/合入** | D1 抄 `R-20260824-01`；未写「不擅自合 main」 | `01`…`06` 已被盘面包占用。本 spec 从 `-07` 起。合 main / #343 等用户明示。子代理 ID 不进正文。 |

换座位的可复用失败形状：**先读 prediction-ledger 再立「未收口」**。v1 诚实转写了没对过台账的排查报告，把已合实现写成待写。

---

## 1. 为什么现在做这五单（原因）

### 1.1 主犯已经换代；W1/W2 不是现役实现债

8-21 CXO：判官按投影删真话。#289 / #298 已拆。

8-23 有色 8796：取数更好（66 证、bindings 齐、结构 completed），判官 `exc_class=RuntimeError` / `issue=semantic judge provider error`（**未**标 transient）→ fail-closed 剥稿。#346 P0-B 修了谎报文案，**没有**把这条未分类 provider-error 接进已有放稿口。这是今天还在的输出闸。

周一科技/医药：信封曾缺双主语和个股格。#346 P0-A/C 已合已切 8792。**合入 ≠ 原题锁死**——但锁死与否只能拿**周一原题**复验，不能拿 Knevo A1 的 `partial` 代替。

### 1.2 ReAct 不该被当成对手，该被拆成一条可搬规则

Cursor 臂看见空表就改查成交额前排，是人改查询策略。组件天花板是编码时冻住的 f-string。产品要追的是「空观察池 → 授权一次 fallback」，不是追齐活工具包措辞。P0-C 禁止的是**预取焊死**「双红+每块前 2」；D3 是空池**之后**一次，不是预取。

### 1.3 8796 现在做不了合法消融

同字节同请求若 `answer_sha256` 不同则噪声地板非零；差量 > 1 禁止因果归因。8792/8796 差的是整个 revision bundle + 新功能。继续拿两端口比质量，会得到假证据。

---

## 2. 范围

### 2.1 做

| 单 | 名称 | 类型 | 改代码？ | 切哪口 |
|---|---|---|---|---|
| D0 | 周一原题复验 P0-C + 8-21 文档补「主犯换代」章 | 审查 | 否 | 不切；读 8792 |
| D1 | 未标 transient 的判官 provider-error：接进已有放稿口 | 实现 | 是 | 先 8792，8796 等 D4 同 SHA |
| D2 | W1/W2 自然样本结案 | 结案 | **否** | 不切 |
| D3 | 空结果 fallback 查询（继承 as-of；与 issue-backfill 互斥） | 实现 | 是 | 先 8792 |
| D4 | 8796 解耦收口：先盘点超集树，再拆 PR | 基建 | 是（开关接线另选形状） | **先合 main（等确认），再同 rev 开 8796** |

### 2.2 不做

- 不加检索焊死、不追活工具包成稿、不把组件天花板当 runtime。
- 不把裸 `RuntimeError` 整类加进判官放稿白名单（#346 P0-B）。
- **不重做 W1/W2/R-05 实现**（#309 / #334 / #307 / #296 已合）。
- 不在脏主树上改；不 `git add -A`；**不擅自合 main / 不擅自合 #343**。
- 不拿 n=1 有色拒答证「8796 判官更严」。
- 不解封空表诚实报缺、口径分歧 fail-closed、合法算术错删句。
- 不让生产请求路径 `import capability_switchboard`。

---

## 3. 续跑约定

子代理会话 ID **不写进本文件**（会腐烂）。需要续跑云端排查时，读 `docs/handoffs/inflight/cursor-harness-ceiling-followup-spec-3f68.md`。

每轮开工：

1. 重读本 spec §0.1 / §0.2，不得把已拆的 8-21 投影删句写成现役主犯，不得把 W1/W2 写成待实现。
2. 先读 `docs/prediction-ledger.md` Open 表，再立「未收口」。
3. 大 JSON 只抽字段：`run_id`、`judge_status`、draft/published 长度、`source_revision`、tools、rejection。禁止 `cat` 整份 `continuous-episode.json`。
4. live 探针字段是 `user`，不是 `user_id`（`scripts/workbench_probe.py`）。

---

## 4. D0 — 复验与文档（零产品代码）

### 4.1 原因

#346 已合已切。周一原题（P0-C §5.1）还没有复验收据。8-21 ceiling 文档若不当成历史章，下一位会修已经拆掉的闸。

### 4.2 步骤

1. 在 **gitea/main 树**（或 8792 当前 `source_revision` 树）用 `scripts/workbench_probe.py` 打周一原题（题面逐字抄 `2026-08-23-publication-and-contract-subtract-design.md` §5.1）。
2. 锁判别变量 1–3（同一份 P0-C spec）：
   - `subject` 同时有「科技」和「医药」，不得空串；
   - `required_outputs` 含个股观察格（名单 + 代码 + 角色）；
   - 「分析下有色金属…」的 `subject` 不得以「下」开头。
3. Knevo A1（`2026-07-23 今天市场怎么样`）若仍见「质检降级：部分必答格核验后不完整」：记**哪一格**，归 W1/V8 结案材料（交给 D2），**不要**写成 P0-C 漏网。
4. 给 `docs/verification/2026-08-21-tracediff-cxo-ceiling.md` 追加「8-23 主犯换代」短章，指针指到本 spec 与三份 `~/.finance-runtime/trace-diff-*`；**不改** 8-21 原文结论。
5. 收据落到 `docs/verification/2026-08-24-p0c-monday-recheck.md`。

### 4.3 完成定义

- 三变量记录齐全。全绿 → D0 过，进入 D1/D3。
- 任一红 → 先补 P0-C，禁止跳去 D3。
- 不预设「仍 partial」。

### 4.4 台账

`R-20260824-10`（`EVAL_ONLY`）：周一原题复验收据存在，三变量有绿/红结论；不得用 Knevo A1 代替。

---

## 5. D1 — 未标 transient 的判官 provider-error：有条件放稿

### 5.1 原因：unavailable 已有两形状

| 形状 | 识别 | 今日行为 | 本单 |
|---|---|---|---|
| **deadline 型** | issue ∈ {`semantic judge deadline exhausted`, leftover window} 且 `monotonic_release_safe` | 已走 `_transient_failure_candidate`。探针 `run_20260822_002309` 公开稿 540 字 | **不重做** |
| **未分类 provider-error** | 兜底 `semantic judge provider error`，`exc_class=RuntimeError`，`http_status=null`，`release_safe=False` | 走 `_gap_answer(judge_unavailable=True)`，稿剥空。有色 8796 即此形 | **本单唯一实现** |

#346 判别变量 #7 已承认 transient + release_safe 应走已有候选口，并明文不把裸 `RuntimeError` 整类加白名单。缺口是：结构已可机械对账时，未分类 provider-error 仍剥盘。

### 5.2 目标行为

当且仅当同时成立：

- `judge_status == unavailable`
- 失败**不是**已接线的 deadline 型（那条已绿）
- draft 非空
- bindings 完整（必填格 gap 空）且结构 verifier `completed`
- 公开稿里留下的数字 ⊆ 已绑定证据 / StructuredObservation（无 report 时也要跑；`_apply_numeric_condition_gate` 今日只在有 report 后才跑）

则：走**已有** `_transient_failure_candidate`（或与它同一投影：`CAUSE_TRANSIENT_VERIFIER_OUTAGE`），开口为复核不可用 / 事后重判，`pending_rejudge=true`（该字段今日已在）。  
否则：仍走 held-gap，措辞按 #346 #6/#8，禁止「证据不足 / 未完成核验绑定」。

**禁止**：把 `exc_class=RuntimeError` 或兜底串整类标成 transient。门是「结构可对账 + 数字 ⊆ 绑定」，不是错误类名。

### 5.3 步骤

1. 从 `gitea/main` 开树 `fix/judge-unavailable-conditional-release`。
2. 读 `_transient_failure_candidate` 与 `_stable_semantic_judge_error`；对照 P0-B 测试。先红：有色形状夹具（66 证 + 未分类 provider-error + 完整 bindings）今日必须剥稿。
3. 把该形状接进已有候选口，并补无-report 的数字 ⊆ 绑定。deadline 型回归必须仍绿。
4. 谎报回归仍绿。收集 provider 原始错误码；n≥3 同形才把「全损率」写入台账结案。
5. 只切 8792。禁止用本单证 8796 更严。

### 5.4 台账（开行须逐字抄）

`R-20260824-07`：若 draft+bindings+结构 completed 且判官为未分类 provider-error，则公开稿非 gap 拒答，正文不含「证据不足」「未完成核验绑定」，且无未绑定数字。deadline 型夹具字数/开口不回归。阈值：同形 n≥3。`HARNESS_FIX`。

替代方案：只重试不放稿（加时延、不破卫生）；双 judge（成本翻倍）；整类 RuntimeError 加白（**否决**）。推荐：接进已有候选口 + 数字 ⊆ 绑定。

---

## 6. D2 — W1/W2 自然样本结案（零产品代码）

### 6.1 原因

实现已经在 main：

| 行 | 实现 | 台账为何还 pending |
|---|---|---|
| R-05 | #296 confirmed | 已结，**不要再立** |
| W1 | #309 + V8 #334；`test_ceiling_required_block_degrade.py` | 欠 marker_loss>0 的自然 live 样本。Knevo A1「质检降级…残块保留」是候选显影 |
| W2 | #307；`test_mandatory_satisfiability.py` | 欠打到 `chain_mapping` 强路径的自然样本（减肥药探针契约没打上） |

### 6.2 步骤

1. **禁止**开 `fix/mandatory-satisfiability` / `fix/marker-loss-degrade-keep` 实现树。
2. 回读 Knevo A1 / 其后带「质检降级」的 run：是否 `marker_loss>0`、残块是否在、有无道歉横幅。满足 W1 结案条件则把 `R-20260821-07` 标 confirmed（或写清还差哪条）。
3. 找一发 `chain_mapping` 仍 mandatory 且供给不可达的题，确认显式缺口而非剥盘；回写 `R-20260821-08`。
4. 语义质量零删除权若还要加严：另开论证单，不混本单。

### 6.3 完成定义

- 两行台账各有「为何 confirmed / 仍差哪条自然样本」的书面结论。
- diff 不含 `intelligence/**/*.py`。

---

## 7. D3 — 空结果 fallback 查询

### 7.1 原因

这是 ReAct 相对填空天花板的**唯一实质增量**，且可在只读红线内做。盘面题（`market_watch`）已被组件包拒收 Engine A，**不在本单范围**。

### 7.2 目标行为

某个 `required_output` 的观察池为空（预取空表 **且** 首轮工具 0 行）时，Episode 内授权 **恰好一次** fallback：

- 换已授权工具的查询口径（例如题材日线空 → 同窗成交额前排）。无行仍诚实报缺。
- **必须继承 as-of**：问句日 / 站立日传到 fallback 参数。不得把 runtime 库尖写进历史题。验收押 08-21 换形探针的零泄漏（08-19 暴跌不得进 08-18 叙事）和 `2026-08-20-asof-prefetch-dual-red-design.md` 判别变量 1。
- **与 `plan_issue_backfill` 互斥**：同一缺口（同一 `output_id` 或同一 IssueCode）只能一家补。fallback 管「池空换口径」；backfill 管「判官 issue → 指定能力再取」。禁止两家各查一次。
- 记 `fallback_query=true` + 原查询 + 新查询。第二次仍空 → 停。
- 不是预取焊死「双红+每块前 2」（P0-C 禁区）。

### 7.3 步骤

1. 树 `feat/empty-pool-fallback-query`。引导写在 episode 工具/计划层，不写进判官。
2. 正控：预取空 + 首轮空 + 同一 as-of → 恰好一次换口径。
3. 负控：首轮已有行 → 零 fallback；历史题 fallback 不得打到库尖；已有 backfill 计划的缺口 → 零 fallback。
4. 与 D1 解耦：禁止一个 PR。D0 绿之后再做。

### 7.4 台账

`R-20260824-08`：空池题恰好一次 fallback，trace 有标记；历史题 served_date = 问句日或 empty；同一缺口无 backfill+fallback 双补。`HARNESS_FIX`。

---

## 8. D4 — 8796 半解耦收口

### 8.1 原因

开关板在 **8796 超集树** `align/switchboard-p0` @ `76ee1e89`，**不在 `gitea/main`**：

- `intelligence/services/capability_switchboard.py`（未知 id → 错；**生产路径永远不读本模块**）
- `scripts/run_capability_switchboard.py`、`intelligence/eval/fixtures/capability_switchboard.json`
- 同树还混着 `reading_baseline.py`（#343 那包）以及写作轮 20s、mixed 契约、路由等已可能进 main 的提交

焊死 / 缺口：`structural-verifier` welded；生产不读板；解耦增量未合 main。

### 8.2 步骤（顺序强制）

0. **盘点（先于拆 PR）**：对 `76ee1e89` 相对 `gitea/main` 列出**非 docs** 提交并归堆（核稿已见：`reading_baseline*`、`capability_switchboard*` / `predicate_faces.py`、以及 `asof_prefetch` / `query_understanding` / `episode_semantic_verifier` 等可能已在 main 的重叠）。重叠的禁止再拆一次，避免三向合并。
1. **拆分支**：`reading_baseline` 一个 PR（即 #343 的干净形态）；「开关板 + 谓词缝 + 离线 runner」一个 PR。禁止再以 8796 超集树当「解耦版」。
2. **任务 D 等价性**：冻结题、只比结构字段、差集应为空。收据归档后才讨论 #343 能否合——**合与否等用户明示**。
3. 两 PR 都进 **同一 `gitea/main` revision** 后，8792 与 8796 **同 SHA** 启动，users_dir 仍可分开。
4. live 消融形状**必须三选一写死**（本 spec 选 **(a)**）：
   - **(a) 启动器注入（推荐）**：sidecar 启动时把「关哪一颗」写入环境 / argv；请求路径仍不 `import capability_switchboard`。默认全开 = 今日行为。
   - (b) fixture + 回退：只在评测进程读板，serving 进程读不到板则 fail-closed 拒启动，不静默当全开。
   - (c) 同 SHA 双树：两棵 checkout 编译期各焊死一颗，不在运行时读板。
   - **否决**：生产请求路径读 `capability_switchboard.py`。
5. 每次只关一颗。差量 > 1 禁止归因。离线 `--all-arms` 继续作门禁。
6. `structural-verifier` 保持 welded，或另开论证单。

### 8.3 完成定义

- 文档与 health 都承认：8796 = 同 rev 的 sidecar，不是功能超集。
- 至少 1 次「同 SHA、只关 1 个 capability」的收据（离线即可先过）。
- 生产 serving 的 import 图不含 `capability_switchboard`。

### 8.4 台账

`R-20260824-09`：8792 与 8796 `source_revision` 相同后，单关一颗的差集可解释；serving 不 import 开关板。`HARNESS_FIX`。合 main 未确认前本行不得写 confirmed。

---

## 9. 总执行顺序

```
D0 复验周一原题 ──红──► 补 P0-C ──► 再 D0
                 └──绿──► D1 未分类 provider-error 放稿口
                            │
                            └─► D3 fallback（D0 绿之后；勿与 D1 混）
D2 全程可做（只读 run / 写台账，零产品代码）
D4 先盘点 76ee1e89 非 docs 提交，再拆 PR；live 消融必须同 SHA
合 main / #343 / 切 8792  —— 等用户明示
```

建议接单粒度：一次一个 D。

---

## 10. 全局纪律

1. `/Users` 下从 `gitea/main` 开 worktree；解释器 `.venv-workbench/bin/python`。
2. 交付前 ruff + 全量 pytest；动 webapp 才 pnpm 四连。Gitea 不跑 Actions，本机绿才可合——**且合 main 仍须用户确认**。
3. 变异测试前先 commit。
4. live 探针字段 `user`；烧题查重跑在 gitea/main 树。
5. 部署：worktree 快照 + symlink + `launchctl kickstart`，不用 rsync。
6. 台账行从本 spec 各单「台账」小节逐字抄；号从 `R-20260824-07` 起，勿占用 `01`…`06`。
7. pathspec 提交，禁用 `git add -A`。

---

## 11. 验收总表

| 单 | 离线必须 | live 必须（用户点头后） |
|---|---|---|
| D0 | 周一题三变量记录齐全；ceiling 文档有换代章 | 8792 原题三变量全绿 |
| D1 | 有色未分类 provider-error 夹具：有稿、无谎报、无未绑定数字；deadline 型 + P0-B 仍绿 | 同形 n≥3 不再全损拒答 |
| D2 | 无产品 diff；`-07/-08` 各有结案或「还差哪条」书面 | 自然样本回写台账 |
| D3 | 正控一次 / 负控零次；as-of 不漏库尖；与 backfill 互斥 | 空池题 trace 带 `fallback_query` |
| D4 | 超集树盘点清单；任务 D 差集空；serving 不 import 开关板 | 同 SHA 两端口；单开关消融差量可解释 |

---

## 12. 给续跑代理的第一句话

> 先重读 `docs/superpowers/specs/2026-08-24-harness-ceiling-and-8796-decouple-followup.md` **§0.1 与 §0.2**。从 D0 开做。不要改 8-21 主犯结论，不要把 D2 当实现单，不要在脏主树上施工，不要擅自合 main。

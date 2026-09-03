# 设计：输出闸减法 + 必要的输入加法 + 8796 同 SHA

- 日期：2026-08-24
- 状态：Draft **v3**（加减法判据已钉。#349 D3 + #350 D4 第 1 步已合 `gitea/main@4dd96f6f`；未切端口）
- v2 → v3：纲领改成「增加输入必要就加，限制输出只做减法」。D1 取消第三扇放稿门和无-report 数字闸，只补分类器；贴不上就关单。D3 留下并标明是输入加法。D4 本批完成定义停在同 SHA；live 注入是关输入的实验，不挡本批。见 §0.2 / §0.3。
- v1 → v2 核稿洞（仍有效）：D2 是结案不是实现；D0 不用 Knevo A1 证 P0-C；unavailable 已有两形状；D3 继承 as-of 并与 issue-backfill 互斥；生产不读开关板；台账从 `R-20260824-07` 起。见 §0.2。
- 分诊（Mac 只读实况，08-23/08-24）：
  - `~/.finance-runtime/four-arm-knevo-20260823/`（Knevo **A1** = `2026-07-23 今天市场怎么样`，不是周一题）
  - `~/.finance-runtime/trace-diff-spt-tech-med-monday-20260823/`（P0-C 原题）
  - `~/.finance-runtime/trace-diff-spt-ysjs-20260823/`（有色 8796 判官 `RuntimeError` → 剥稿）
  - `~/.finance-runtime/cutover-20260823-8792-8796.md`
  - `docs/verification/2026-08-21-tracediff-cxo-ceiling.md`（**不是终局**，投影删句主犯已拆）
- 相邻（实施前先认领，禁止抢合）：
  - `2026-08-23-publication-and-contract-subtract-design.md`（#346 P0-A/B/C，已合已切 8792；本单继承「不加检索焊死 / 不追活工具包」）
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

桌上菜不够时，**加一次输入**（空池换口径）。端盘已经把整桌撤掉时，**只拆输出闸**，不新开第三扇放稿门。8796 先减掉「另一棵 revision」这个混淆，再谈关哪颗输入做消融。

人话：后厨缺菜可以再炒一盘；端盘的保安只许撤岗，不许再设卡。W1/W2 的零件已经换过，只欠现场照片。

### 0.1 对用户假设的冻结判定（后续审查不得悄悄改口）

| 命题 | 判定 | 成立条件 |
|---|---|---|
| 组件是相交层，不是 8792/8796 质量差的来源 | **成立** | 有色题 8796 66 条 vs 8792 37 条；周一题 8792 已取到药明/恒瑞/沃森 |
| 正交 harness 限制了相对「Agent ReAct 直调组件」的上限 | **部分成立、时效性强** | 8-21 投影删句已拆；8-23 之后还封上限的是「未贴 transient 标签的判官错误 → 剥稿」。W1/W2 **不是**现役缺口 |
| ReAct 全面优于 workbench | **不成立** | 五臂「活工具包 5/5」标了自评偏斜 + 人在回路；真增量收窄为「空结果换口径再查」——这是**输入加法**，不是输出闸 |
| 8796 完全是 8792 的解耦版 | **不成立（半解耦）** | revision 不同；生产不读开关板；混入 `reading_baseline` |

### 0.2 核稿改定（实施按最新一列）

| ID | v1 | v2 | **v3（本版）** |
|---|---|---|---|
| **纲领** | 五单推上限，没写加减 | 仍五单并列，D1 写成第三扇门 | **输入可加、输出闸只减**（§0.3） |
| **D2** | 当实现单 | 结案单，零产品代码 | 同 v2 |
| **D0** | 用 Knevo A1 `partial` 证 P0-C | 只用周一原题 | 同 v2 |
| **D1** | 一切 `unavailable` 有条件放稿 | 两形状；接候选口 **并** 补无-report 数字闸 | **只补分类器**。贴进已有 transient 桶 → 已有放稿口自己开火。贴不上 → **关单**，不新开第三扇门，不加数字闸 |
| **D3** | 空池再查 | 加 as-of + 与 backfill 互斥 | **留下**，标明必要的输入加法。as-of / 互斥是护栏，不是输出闸 |
| **D4** | 生产读开关板 | 启动器注入；live 消融进完成定义 | 本批停在**同 SHA + 盘点拆 PR**。live 注入 = 关输入做实验，P1，不挡本批 |
| **台账/合入** | 占用 `R-20260824-01` | 从 `-07` 起；不擅自合 main | 同 v2 |

换座位的可复用失败形状：先读 prediction-ledger 再立「未收口」；封面写减法、目录里却给输出侧加门，实施会按加法做。

### 0.3 加减法判据（每条新工作必须填）

问两句，不要问「这是不是功能」：

1. **这是给桌上加观察值，还是给端盘加限制？**
2. **模型变强会不会更惨？** 会更惨的输出闸 = 封上限，只许拆。保下限的机械硬违规（无据数字、表外 E 号、口径分歧）**不解封**。

| 动作 | 加减 | 本 spec |
|---|---|---|
| 空池后再查一次（换已授权口径） | **加输入** | D3，必要 |
| 把本该是 timeout/5xx 的错误贴进已有 transient 桶 | **减输出闸**（分类补洞，不是新政策） | D1 |
| 结构齐就放任意 `RuntimeError` + 新数字闸 | **加输出闸** | **否决**（v2 已删） |
| 两端口改成同一 SHA | **减混淆** | D4 本批 |
| 启动器关一颗 capability | **临时减输入**（测量） | D4 P1，不挡本批 |
| 生产请求路径读开关板 / fail-closed 打挂 serving | **加输出侧耦合** | **否决** |
| 预取焊死「双红+每块前 2」 | **加输入且焊死** | **否决**（P0-C） |
| 重做 W1/W2 实现 | 给已合零件再加一层 | **否决** |

约束三筛仍要填：拦输入还是输出？模型变强会不会更惨？保下限还是封上限？

---

## 1. 为什么现在做这几单（原因）

### 1.1 还封上限的是一道输出闸，不是缺检索焊死

8-21 CXO：判官按投影删真话。#289 / #298 已拆。

8-23 有色 8796：取数更好（66 证、bindings 齐、结构 completed），判官 `exc_class=RuntimeError` / `issue=semantic judge provider error`（**未**标 transient）→ fail-closed 剥稿。#346 P0-B 修了谎报文案，**没有**把「其实是 timeout/5xx、只是包成 RuntimeError」的那类错误贴进已有分类器。这是今天还在的**输出闸**。

周一科技/医药：信封曾缺双主语和个股格。#346 P0-A/C 已合已切 8792。**合入 ≠ 原题锁死**——锁死与否只能拿**周一原题**复验，不能拿 Knevo A1 的 `partial` 代替。

### 1.2 ReAct 的真增量是输入，不是成稿

Cursor 臂看见空表就改查成交额前排，是人改查询策略。组件天花板是编码时冻住的 f-string。产品该加的是「空观察池 → 授权一次 fallback」，不是追齐活工具包措辞，也不是在端盘再设卡。P0-C 禁止的是**预取焊死**；D3 是空池**之后**一次，不是预取。

### 1.3 8796 现在做不了合法消融

同字节同请求若 `answer_sha256` 不同则噪声地板非零；差量 > 1 禁止因果归因。8792/8796 差的是整个 revision bundle + 新功能。继续拿两端口比质量，会得到假证据。先减混淆（同 SHA），再谈关哪颗输入。

---

## 2. 范围

### 2.1 做

| 单 | 名称 | 加减 | 改代码？ | 切哪口 |
|---|---|---|---|---|
| D0 | 周一原题复验 P0-C + 8-21 文档补「主犯换代」章 | 核对 | 否 | 不切；读 8792 |
| D1 | 分类器补洞：能贴 transient 则已有放稿口开火；贴不上关单 | **减输出闸** | 仅当取证证明是漏标 | 先 8792 |
| D2 | W1/W2 自然样本结案 | 结案 | **否** | 不切 |
| D3 | 空结果 fallback 查询（as-of；与 issue-backfill 互斥） | **加输入** | 是 | 先 8792 |
| D4 | 盘点超集树、拆 PR、两端口同 SHA | **减混淆** | 是（合入等确认） | 先合 main（等确认），再同 rev 开 8796 |

### 2.2 不做

- 不加检索焊死、不追活工具包成稿、不把组件天花板当 runtime。
- **不**把裸 `RuntimeError` 整类加进放稿白名单（#346 P0-B）。
- **不**为「结构齐」新开第三扇放稿门，**不**在无 report 路径新加数字 ⊆ 绑定闸（候选口已有 `_sanitize_public_answer`）。
- **不重做 W1/W2/R-05 实现**（#309 / #334 / #307 / #296 已合）。
- 不在脏主树上改；不 `git add -A`；**不擅自合 main / 不擅自合 #343**。
- 不拿 n=1 有色拒答证「8796 判官更严」。
- 不解封空表诚实报缺、口径分歧 fail-closed、合法算术错删句（那是保下限）。
- 不让生产请求路径 `import capability_switchboard`。
- 本批不把 live 单开关消融写成完成条件。

---

## 3. 续跑约定

子代理会话 ID **不写进本文件**（会腐烂）。需要续跑云端排查时，读 `docs/handoffs/inflight/cursor-harness-ceiling-followup-spec-3f68.md`。

每轮开工：

1. 重读本 spec §0.1 / §0.2 / **§0.3**。不得把已拆的 8-21 投影删句写成现役主犯，不得把 W1/W2 写成待实现，不得给输出侧加门。
2. 先读 `docs/prediction-ledger.md` Open 表，再立「未收口」。
3. 大 JSON 只抽字段：`run_id`、`judge_status`、draft/published 长度、`source_revision`、tools、rejection、判官 `exc_class` / 原始错误串。禁止 `cat` 整份 `continuous-episode.json`。
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

## 5. D1 — 分类器补洞（减输出闸，不加新门）

### 5.1 原因：unavailable 已有两形状，第三扇门是加法

| 形状 | 识别 | 今日行为 | 本单 |
|---|---|---|---|
| **deadline 型** | issue ∈ {`semantic judge deadline exhausted`, leftover window} 且 `monotonic_release_safe` | 已走 `_transient_failure_candidate`。探针 `run_20260822_002309` 公开稿 540 字 | **不重做** |
| **已分类 transient** | `_stable_semantic_judge_error` 认出 429/5xx、Timeout、Connection → `semantic judge transient provider error` + `release_safe` | 与上同一放稿口 | **不重做** |
| **未分类 provider-error** | 兜底 `semantic judge provider error`，`exc_class=RuntimeError`，`http_status=null`，`release_safe=False` | `_gap_answer(judge_unavailable=True)`，稿剥空。有色 8796 即此形 | **先取证再决定是否改分类器** |

#346 判别变量 #7：只有失败**已被显式**标成 transient+release_safe，才走已有候选口。禁止 RuntimeError 整类加白。v2 曾写成「结构齐 + 数字 ⊆ 绑定就放」——那是新政策，本版否决。

现役分类器已经认：HTTP 429/5xx、`TimeoutError` / `ReadTimeout` / `ConnectionError`、文案里的 timeout / 限流 / 网络错误。兜底是 `"semantic judge provider error", False, False`。缺口只可能是：**真实原因是上一行那些，但包成无标记 RuntimeError，分类器看不见。**

### 5.2 目标行为

1. 回读有色 8796（及同形 n≥2）的判官原始错误串 / `__cause__` / HTTP 状态。禁止只看 `exc_class=RuntimeError`。
2. **能**映射到已有 transient 标记 → 改 `_stable_semantic_judge_error`（或解包 cause）让它贴上已有标签。放稿口**不要新写**；`_transient_failure_candidate` + `_sanitize_public_answer` 自己开火。deadline 型与 P0-B 谎报回归必须仍绿。
3. **不能**映射（裸 RuntimeError、无 cause、不是 timeout/5xx/限流）→ **关单**。书面结论：#346 的 fail-closed 成立，本单无产品 diff。禁止为了放稿新开第三扇门。

### 5.3 步骤

1. 从 `gitea/main` 开树 `fix/judge-transient-unwrap`（分类器单，不是 `conditional-release`）。
2. 先取证，再写测试。先红的夹具必须是「真实错误串今日漏标」；禁止用「结构齐 + 任意 RuntimeError」当正控。
3. 若取证失败：提交一份短验证文档，关单，不改 `episode_semantic_verifier.py`。
4. 只切 8792。禁止用本单证 8796 更严。

### 5.4 台账（开行须逐字抄）

`R-20260824-07`：若判官失败的 cause/HTTP/文案属于已有 transient 标记，则 issue 为 `semantic judge transient provider error` 且走已有候选口，公开稿非 gap 拒答。若取证证明不属于这些标记，本行以「无漏标、保持 fail-closed」结案，**禁止**用「结构 completed」作为放稿条件。阈值：同形 n≥2 才改分类器。`HARNESS_FIX`。

替代方案：结构齐就放（**否决**，输出侧加法）；双 judge（成本翻倍，不减闸）；只重试不放稿（加时延，不拆闸）。推荐：解包或关单。

---

## 6. D2 — W1/W2 自然样本结案（零产品代码）

### 6.1 原因

实现已经在 main：

| 行 | 实现 | 台账为何还 pending |
|---|---|---|
| R-05 | #296 confirmed | 已结，**不要再立** |
| W1 | #309 + V8 #334；`test_ceiling_required_block_degrade.py` | **仍欠** `marker_loss>0`。Knevo A1 / 08-24 指数×科技的「质检降级」是结构 `partial` 水印，不是删格残块。见 `docs/verification/2026-08-24-d2-w1-w2-natural-sample.md` |
| W2 | #307；`test_mandatory_satisfiability.py` | **2026-08-24 已结**：指数×科技 8792 打上 `chain_mapping.required=False` + 预置缺口，公开稿【结构缺口】未剥盘。`R-20260821-08` confirmed |

### 6.2 步骤

1. **禁止**开 `fix/mandatory-satisfiability` / `fix/marker-loss-degrade-keep` 实现树。
2. 回读 Knevo A1 / 其后带「质检降级」的 run：是否 `marker_loss>0`、残块是否在、有无道歉横幅。满足 W1 结案条件则把 `R-20260821-07` 标 confirmed（或写清还差哪条）。
3. 找一发 `chain_mapping` 仍 mandatory 且供给不可达的题，确认显式缺口而非剥盘；回写 `R-20260821-08`。
4. 语义质量零删除权若还要加严：另开论证单，不混本单。

### 6.3 完成定义

- 两行台账各有「为何 confirmed / 仍差哪条自然样本」的书面结论。
- diff 不含 `intelligence/**/*.py`。

2026-08-24 已写：`docs/verification/2026-08-24-d2-w1-w2-natural-sample.md`。W2 confirmed；W1 书面结论=仍差 `marker_loss>0`。本单不因 W1 未结而重开实现。

---

## 7. D3 — 空结果 fallback 查询（必要的输入加法）

### 7.1 原因

这是 ReAct 相对填空天花板的**唯一实质增量**。它给桌上加观察值，不给端盘加限制。盘面题（`market_watch`）已被组件包拒收 Engine A，**不在本单范围**。

as-of 与 issue-backfill 互斥不是输出闸：前者防止新查询打到库尖（输入污染）；后者防止同一缺口被两家各查一次（重复输入）。

### 7.2 目标行为

某个 `required_output` 的观察池为空（预取空表 **且** 首轮工具 0 行）时，Episode 内授权 **恰好一次** fallback：

- 换已授权工具的查询口径（例如题材日线空 → 同窗成交额前排）。无行仍诚实报缺。
- **必须继承 as-of**：问句日 / 站立日传到 fallback 参数。不得把 runtime 库尖写进历史题。验收押 08-21 换形探针的零泄漏（08-19 暴跌不得进 08-18 叙事）和 `2026-08-20-asof-prefetch-dual-red-design.md` 判别变量 1。
- **与 `plan_issue_backfill` 互斥**：同一缺口（同一 `output_id` 或同一 IssueCode）只能一家补。fallback 管「池空换口径」；backfill 管「判官 issue → 指定能力再取」。禁止两家各查一次。
- 记 `fallback_query=true` + 原查询 + 新查询。第二次仍空 → 停。
- 不是预取焊死「双红+每块前 2」（P0-C 禁区）。
- **不**因为 fallback 仍空就改发布门或剥稿。空就是空，诚实报缺。

### 7.3 步骤

1. 树 `feat/empty-pool-fallback-query`。引导写在 episode 工具/计划层，不写进判官、不写进 `_gap_answer`。
2. 正控：预取空 + 首轮空 + 同一 as-of → 恰好一次换口径。
3. 负控：首轮已有行 → 零 fallback；历史题 fallback 不得打到库尖；已有 backfill 计划的缺口 → 零 fallback。
4. 与 D1 解耦：禁止一个 PR。D0 绿之后再做。

### 7.4 台账

`R-20260824-08`：空池题恰好一次 fallback，trace 有标记；历史题 served_date = 问句日或 empty；同一缺口无 backfill+fallback 双补。公开稿不因「做过 fallback」多一道发布限制。`HARNESS_FIX`。

---

## 8. D4 — 8796 减混淆（本批停在同 SHA）

### 8.1 原因

开关板在 **8796 超集树** `align/switchboard-p0` @ `76ee1e89`，**不在 `gitea/main`**：

- `intelligence/services/capability_switchboard.py`（未知 id → 错；**生产路径永远不读本模块**）
- `scripts/run_capability_switchboard.py`、`intelligence/eval/fixtures/capability_switchboard.json`
- 同树还混着 `reading_baseline.py`（#343 那包）以及写作轮 20s、mixed 契约、路由等已可能进 main 的提交

焊死 / 缺口：`structural-verifier` welded；生产不读板；解耦增量未合 main。继续用两棵树比质量 = 假证据。

### 8.2 步骤（顺序强制）

0. **盘点（先于拆 PR）**：对 `76ee1e89` 相对 `gitea/main` 列出**非 docs** 提交并归堆（核稿已见：`reading_baseline*`、`capability_switchboard*` / `predicate_faces.py`、以及 `asof_prefetch` / `query_understanding` / `episode_semantic_verifier` 等可能已在 main 的重叠）。重叠的禁止再拆一次，避免三向合并。
1. **拆分支**：`reading_baseline` 一个 PR（即 #343 的干净形态）；「开关板 + 谓词缝 + 离线 runner」一个 PR。禁止再以 8796 超集树当「解耦版」。
2. **任务 D 等价性**：冻结题、只比结构字段、差集应为空。收据归档后才讨论 #343 能否合——**合与否等用户明示**。
3. 两 PR 都进 **同一 `gitea/main` revision** 后，8792 与 8796 **同 SHA** 启动，users_dir 仍可分开。**本批完成定义到此为止。**
4. **P1（不挡本批）** live 消融 = 临时**关输入**做测量，不是给 serving 加输出闸。若做，形状必须三选一（本 spec 预选 **(a)**）：
   - **(a) 启动器注入**：sidecar 启动时把「关哪一颗」写入环境 / argv；请求路径仍不 `import capability_switchboard`。默认全开 = 今日行为。
   - (b) fixture + 回退：只在评测进程读板，serving 读不到板则拒启动，不静默当全开。
   - (c) 同 SHA 双树：两棵 checkout 编译期各焊死一颗。
   - **否决**：生产请求路径读 `capability_switchboard.py`。
5. 每次只关一颗。差量 > 1 禁止归因。离线 `--all-arms` 继续作门禁；本批验收承认离线即可。
6. `structural-verifier` 保持 welded，或另开论证单。

### 8.3 完成定义（本批）

- 文档与 health 都承认：8796 = 同 rev 的 sidecar，不是功能超集。
- 超集树非 docs 盘点清单已落；重叠提交不二次拆。
- 生产 serving 的 import 图不含 `capability_switchboard`。
- 不要求 live 单开关收据。

### 8.4 台账

`R-20260824-09`：8792 与 8796 `source_revision` 相同；serving 不 import 开关板。单关一颗的差集可解释是 P1，不构成本行 confirmed 的必要条件。`HARNESS_FIX`。合 main 未确认前本行不得写 confirmed。

---

## 9. 总执行顺序

```
D0 复验周一原题 ──红──► 补 P0-C ──► 再 D0
                 └──绿──► D1 取证分类器（贴上或关单；不新开门）
                            │
                            └─► D3 空池 fallback（输入加法；勿与 D1 混）
D2 全程可做（只读 run / 写台账，零产品代码）
D4 先盘点 76ee1e89 非 docs 提交，再拆 PR，同 SHA
   live 注入 = P1
合 main / #343 / 切 8792  —— 等用户明示
```

建议接单粒度：一次一个 D。D1 与 D3 不要塞进同一个 PR：一个减输出闸，一个加输入。

---

## 10. 全局纪律

1. `/Users` 下从 `gitea/main` 开 worktree；解释器 `.venv-workbench/bin/python`。
2. 交付前 ruff + 全量 pytest；动 webapp 才 pnpm 四连。Gitea 不跑 Actions，本机绿才可合——**且合 main 仍须用户确认**。
3. 变异测试前先 commit。
4. live 探针字段 `user`；烧题查重跑在 gitea/main 树。
5. 部署：worktree 快照 + symlink + `launchctl kickstart`，不用 rsync。
6. 台账行从本 spec 各单「台账」小节逐字抄；号从 `R-20260824-07` 起，勿占用 `01`…`06`。
7. pathspec 提交，禁用 `git add -A`。
8. 实施时若发现自己在给 `_gap_answer` / 发布门 / 判官删除权加条件：停下，回到 §0.3。那是输出侧加法。

---

## 11. 验收总表

| 单 | 离线必须 | live 必须（用户点头后） |
|---|---|---|
| D0 | 周一题三变量记录齐全；ceiling 文档有换代章 | 8792 原题三变量全绿 |
| D1 | 要么：漏标夹具走已有候选口，deadline + P0-B 仍绿；要么：取证文档 + 零产品 diff | 仅当改了分类器：同形不再因漏标全损拒答 |
| D2 | 无产品 diff；`-07/-08` 各有结案或「还差哪条」书面 | 自然样本回写台账 |
| D3 | 正控一次 / 负控零次；as-of 不漏库尖；与 backfill 互斥；发布门字数/开口不因 fallback 变严 | 空池题 trace 带 `fallback_query` |
| D4 | 超集树盘点清单；任务 D 差集空；serving 不 import 开关板 | 同 SHA 两端口。单开关消融不要求 |

---

## 12. 给续跑代理的第一句话

> 派活读 `docs/superpowers/plans/2026-08-24-three-layer-execution.md`。规格正文仍是本文件 **§0.1、§0.2、§0.3** + 盘面包 `2026-08-24-market-watch-component-first-design.md`。增加输入必要就加，限制输出只做减法。D0/D1/D2(W2) 已结。#349/#350 已合 `4dd96f6f`。不要给端盘加第三扇门，不要把结构水印当 W1，不要把 84/98 套到 Knevo A1，不要在脏主树上施工，不要擅自切端口。

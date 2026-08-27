# V11 · 判官引导的一次有界回检索（设计）

- 日期：2026-08-22
- 作者：V11 设计执行方（本单只出设计，不写生产代码、不改测试、不部署、不立案台账）
- 状态：待验收方 + 用户确认后才进实施
- 上游：R3 批次合同 `docs/superpowers/specs/2026-08-22-r3-capability-alignment-batch-design.md` §B3
- 已落地先例：V8 语义删权收窄（`episode_semantic_verifier._partition_rejected_indexes` / `_annotate_semantic_rejects`）；V9a 消费侧换窗（`kb_window_reexcerpt.reexcerpt_hits`，挂在 `kb_rag.retrieve` 返回前）；检索档位真值表 `select_mode_for_remaining`（15.0 / `_DENSE_MODES`）
- 出发样本：`probe-v8-0822` / `run_20260822_115024_661457`，题「液冷服务器产业链怎么看」——`judge_status=repaired`，3 条语义 issue（散热升级因果无据 / 快接头「发明环节」/ 风冷改良外部原因偷渡），3/3 留句+【质检存疑】
- 台账行：`R-20260822-05`（**实施时**才立案；§9 给出可逐字抄的一行）
- 基线锚：worktree `/Users/a77/fwp-wt-v11-design` @ `6f761366`（= `gitea/main`，含 R3 合同）

> 角色分离沿 R2/R3 纪律：本文件是设计合同，不是施工 diff。合并需验收方复算 + 用户确认。

---

## 交付物覆盖自查（§B3 八项，缺一即不合格）

| # | §B3 要求 | 落点 |
|---|---|---|
| 1 | 触发分类（类型 / 机械永不 / 阈值 / 每 episode ≤1） | §3 |
| 2 | 预算来源与预占（绝对 deadline / 从哪 reserve / 不足 fail-closed / 零新降档函数） | §4 |
| 3 | 管线位置与既有钉兼容（首判/再判 `calls==2\|3`、修复窗、V8 标注、回检索后句子命运、需重钉的论证） | §5 |
| 4 | query 构造确定性规则（不额外调 LLM，或论证值得调） | §6 |
| 5 | 遥测字段 + 仓内读方（字段契约门禁） | §7 |
| 6 | A/B 预注册（探针用户 / 分臂 / n / 指标；长度守门进合取） | §8 |
| 7 | 台账行草稿 + 变异 ≥3 | §9 |
| 8 | 失败形状（至少含稀释正确结论、预算吃掉完稿率） | §10 |

---

## 0. 一句话

V8 已经能把「因果无据 / 发明环节」留在稿上并打【质检存疑】。V11 要做的是：**在纯语义早退路径上，用判官刚点名的句子做一次有界回检索**——库里有、首轮没检回的，给判官看一眼新证据、能撤标就撤；库里真没有的，标留下，两种结局必须能从遥测分开。不改 `_repair`，不加第二修复窗，机械 issue 永不触发，每 episode 最多一枪，预算不够就当 V8 没发生过。

人话：判官说「这句桌上没证据」。V11 不去改这句话，只去库里再翻一次那一页。翻到了让判官再看同一句；没翻到或没时间翻，那句继续带着存疑标出门。

---

## 1. 背景：这条线走到哪、问题在哪一层

### 1.1 已核实事实（点查，不是通读；实施时不要再探一遍）

均相对基线 `6f761366`。函数名锁定，行号会漂。

| # | 事实 | 出处 |
|---|---|---|
| 1 | V8 分流在 `_repair` **之前**：`_plan_repair_indexes` 调 `_partition_rejected_indexes`，机械句进 `_repair`，语义句若在必需块则 `_note_semantic_reject`，否则仍可删 | `episode_semantic_verifier.py` |
| 2 | `_repair` 函数体仍是「按句号整句删 + 补槽 + `verify_episode_outcome`」，**不看 issue 类型**。本单不得改它 | 同文件 `_repair` |
| 3 | 纯语义拒句走早退：`first_repair_indexes` 为空则直接 `_completed_public`，**不再发起以删句为目的的再审**。夹具钉：`semantic-only reject must not start a deletion rejudge`，`calls == 1` | `verify()` 早退；`test_judge_issue_sentence_numbers_cannot_escape_targeted_redaction` / `test_long_draft_redacts_rejected_sentences_without_model_rewrite` |
| 4 | 机械删句后再审：稿必须变短，`calls == 2` 或 `3`（`MAX_SEMANTIC_JUDGE_ATTEMPTS = 3`）。这是「稿变短」安全网，夹具已改成机械扳机 | C 簇 `test_*monotonic*` / `test_second_targeted_repair_*` / `test_terminal_redaction_*` |
| 5 | 语义标注只打 `public_answer`（经 `view()` + `_VIEW_CALLERS` 登记），`verified.outcome.draft` 真值句不改 | `_project_semantic_quality_marks`；`test_session_projection._VIEW_CALLERS` |
| 6 | 判官出参仍是自由字符串 `issues[]`，**没有 typed enum**。分类按「谁产出了句号」不按文案关键词——V8 已否决 `re.search("因果")` | V8 设计 §3.1 D / §9 |
| 7 | `retrieve()` 是汇合点：V9a `reexcerpt_hits` 在返回前已接线；档位唯一真值表 `select_mode_for_remaining(requested, remaining_seconds)`，切点 `HYBRID_MIN_REMAINING_SECONDS = 15.0`，`_DENSE_MODES = {hybrid, dense, rerank}`。今日 `remaining_seconds` 的入口就是 `retrieve(..., timeout=)`，**没有第二套形参** | `kb_rag.py` |
| 8 | episode 首轮 `retrieve_kb` 写死 `mode="hybrid"`、`timeout=min(timeout, 30.0)`、`k=6` | `episode_tools.py` |
| 9 | 语义核验吃的是**同一条绝对 `root_deadline`**（`expires_at` + `remaining()`），不是相对秒数。`verify()` 之后，`continuous_turn_adapter` 仍可能进 `_resume_for_gap` 循环（已有修复窗，按 `max_repair_cycles_for_tier` 封顶） | `continuous_turn_adapter.py`：`deadline=root_deadline` |
| 10 | `ResearchDeadline.stage_timeout` = `remaining − synthesis_reserve` 再与上限取 min；`synthesis_timeout` 可用全部剩余（含保留段）。standard 档 `synthesis_reserve=20` | `research_contract.py` |
| 11 | V6 A/B（`docs/verification/2026-08-21-deadline-budget-ab.md`）：完稿率 44%→90%（+46pp）仍因答案长度中位 −6.2% 被**合取判据**否决。预注册原文：「+15pp **且**长度不降」 | V6 报告 §4 |
| 12 | 出发样本是**纯语义、无机械违规**（`repair_output_ids` 空）。半腿机械对照仍无自然样本（`R-20260821-19` pending） | `docs/verification/2026-08-22-v8-semantic-deletion-rights.md` live 节 |
| 13 | 本仓三条可迁移原则：配额在副作用前预占；全链 deadline 传绝对时刻；授予的额度必须传到最下游执行者（只写 telemetry 不生效比不做更危险） | `CLAUDE.md` |

### 1.2 出发假设（必须可证伪，不能写成定律）

液冷三条 issue **有一部分**可能是「库里有、首轮没检回」（V4 已证同题 top-k 曾被验收工件挤掉；V9a 只换窗不换槽）。另一部分是真无据或判官口径过严，回检索救不了。

V11 的产品价值不是「让完稿更长」或「让判官少报 issue」，而是让这两种结局**可观测、可区分**：

| 结局 | 含义 | 不能混成 |
|---|---|---|
| `retrieved_empty` | 按确定性 query 回库，0 命中 | 写成「证据不存在于世界」 |
| `still_annotated`（有命中） | 检回了，重判仍拒 | 「首轮漏检」——其实是证据对不上这句 |
| `lifted` | 检回了，重判放过原先拒句 | 「库里有、首轮没检回」成立 |
| `skipped` | 没开枪（机械 / 预算 / 已用过 / 关开关） | 写成「回检索失败」 |

缺字段记 None，不报 0（沿 V7/V9a 量纲诚实）。

### 1.3 约束三筛（为什么这是回检索，不是再写一稿）

权威尺：`~/harness-reference/PLAYBOOK.md` 约束三筛。harness 该约束事实来源，不该约束话怎么说。

| 片段 | 筛 1 | 筛 2 失效 | 筛 3 模型变强 | 定性 | V11 处置 |
|---|---|---|---|---|---|
| 机械硬违规删句 | 拦输出（数/E 号在不在桌上是机械事实） | 变错 | 不挡 | 保下限 | **永不触发回检索**；删权不动 |
| 语义质量拒句 + 必需块 | 纯拦输出 | 变笨（真话连坐） | 会挡（稿越长误伤越多） | V8 已改写成标注 | 本单在标注之上**补一枪检索** |
| 用回检索结果改写正文 | 拦输出且改话 | 变错（新证据稀释原结论） | 会挡 | 封上限 | **禁止**。不加第二修复窗 |
| 固定两遍检索 / 起稿前扩 k | 拦输入 | 变笨（每题都缴税） | 不挡，但贵 | 预算税 | **否决**（见 §2） |

---

## 2. 替代方案对比（为什么选「判官引导的一枪」）

| | 案甲 · 判官引导回检索（本单） | 案乙 · 固定两遍检索 | 案丙 · 起稿前扩检索（更大 k / 更长窗 / 总是 hybrid） |
|---|---|---|---|
| 做什么 | 首判之后，仅当纯语义拒句且预算够，用拒句文本回库一次 | 每题草稿前检索两次 | 每题第一枪就给更大带宽 |
| 何时花钱 | 稀疏：只在 V8 打标的那类 episode | 每题都缴第二枪税 | 每题都缴更贵的第一枪 |
| 知不知道缺什么 | 知道。query 来自被拒的那句 | 不知道。第二枪与第一枪同 query 或浅扩展 | 不知道。只是加桶 |
| 与 V8 | 标留下是默认；撤标必须重判明确放过 | 与判官无关，救不了「检回了但不构成这句的据」 | 同左 |
| 与 V6 | 只吃**早退后本将闲置**的剩余；<15s fail-closed | 每题 −N 秒，完稿率必受压 | 第一枪更慢，正是 V6 修窗依赖的形状 |
| 与 `calls==2\|3` 钉 | 不走机械删句再审（见 §5） | 不碰判官 | 不碰判官 |
| 失败形状 | query 构造错 → 空检（可观测）；误撤标（重判门可挡） | 预算被系统性吃掉；第二枪重复第一枪 | 带宽涨了，槽位仍可能错（V9b 的题）；仍不知道缺哪句 |
| 结论 | **采用** | 否决：无引导、每题缴税 | 否决：V9a/V9b 已在管带宽，不回答「这句缺据」 |

可迁移点（面试也常问）：**延迟检索 / retrieval-on-demand**——先生成再按缺口补检，对比「总是多检一遍」。和 RAG 里 HyDE / 多 query 不是同一层：这里的 query 来自**裁判指出的具体句**，不是来自问题改写。任何「生成 → 校验 → 按校验缺口补检索」的 harness 都能搬这条，前提是补检不得变成第二套改稿机。

案丁（曾考虑、否决）：回检索后用 LLM **重写**被拒句。这是第二修复窗，直接破硬约束，且把「桌上多了几张卡」变成「话被改了」——稀释正确结论的主通道。

---

## 3. 项 1 · 触发分类

### 3.1 谁有权触发：复用 V8 桶，不新建 issue 枚举

判官 `issues[]` 仍是自由文本。V8 的分流依据是**句号生产者**（代码闸 vs LLM），不是文案。V11 跟着这条桶走，不写第二套关键词白名单。

**触发（AND，缺一不可）：**

1. 开关开（`FINANCE_V11_GUIDED_RETRIEVE` 默认**关**，见 §8；开臂才开）。
2. 本 episode 实例尚未用过（`_v11_used` 仍为假）。
3. 首判已出合法 report，且 `first.report.passed` 为假。
4. `_plan_repair_indexes(...)` 返回**空**——没有任何句号要进 `_repair`。
5. `_semantic_reject_texts` 非空——至少 1 句语义拒句落在必需块，V8 将打标。
6. 预算预占成功（§4）。
7. 注入了 `retrieve_fn`（生产由 `continuous_turn_adapter` 注入；单测默认不注入 → 自动 skip）。

人话：只有「V8 今天会留句打标、然后直接出门」的那条路，才配开这一枪。液冷样本正是这条路（`repair_output_ids=[]`）。

**阈值：** ≥1 条语义拒句（必需块内）。不要求 ≥3。液冷是 3 条，但 1 条就够构成「可能漏检」。多句合并成**一条** query、**一次** `retrieve`（§6），不按 issue 数开枪。

### 3.2 机械类永不触发（闭集，跟 V8 白名单对齐）

下列任一为真 → `v11_skip_reason=mechanical_pending` 或更具体的码，**不得**调用 `retrieve_fn`：

| 来源 | 为何永不 |
|---|---|
| `numeric_unsupported`（预检 + 数值闸） | 假数上桌是保下限；再检两篇研报也不能让「99999 点」变合法 |
| `calendar_weekday_mismatch` / `path_trend_mismatch` | 桌上日期/趋势对账，不是「库里没这篇」 |
| 表外 E 号（`unresolved_evidence_ordinal` 确定性闸） | 引用了不存在的卡；该删。回检索不能发明 E99 |
| `_plan_repair_indexes` 非空（混合案） | 本 episode 还要走机械删句 + 再审；V11 若插一枪会偷 `calls` 预算（§5.3） |
| 预检已删句、首判之前就进过 `_repair` | 同上，已在机械轨道 |

不解析 LLM issue 字符串来决定「像不像机械」。句号不在机械集合里，才可能进语义桶。

### 3.3 每 episode ≤ 1 次（预占旗标，不是事后计数）

`SemanticEpisodeVerifier` 生产路径上是**每 episode 一个实例**（`continuous_turn_adapter` 持有 `self._semantic_verifier`）。`verify()` 在 gap-repair 之后会被**再调用**。

纪律：

- 实例字段 `_v11_used`：**在调用 `retrieve_fn` 之前**置 True（副作用前预占）。
- `verify()` 开头**不得**把 `_v11_used` 清掉（对比：`_semantic_reject_texts` 每次 verify 会清——那是本轮标注缓冲，不是跨轮配额）。
- `retrieve_fn` 抛错 / 超时 / 空命中：旗标保持 True，不得补枪。
- 同一实例第二次 `verify()`：直接 `skip_reason=already_used`。

这就是「配额在副作用前预占」。两个并发 verify 在本设计里不存在（同一 episode 串行）；预占防的是「verify 重入 + 空检后再试」。

### 3.4 已知边界（v1 不做）

- **混合案**（机械句要删 + 语义句要标）：V11 不开火。语义标按 V8 留下，机械句按原再审走。液冷出发样本不是混合案。若以后要覆盖混合，必须另开增量并重钉 C 簇，不挤进本单。
- **块外语义句**（V8 仍可删）：不触发。它们走 `_repair`，`first_repair_indexes` 非空。
- **首判 `passed`**：无缺口，不开枪。
- **首判 unavailable**：无 report 可引导，不开枪（fail-closed 回 V8/V8 之前的 unavailable 行为）。

---

## 4. 项 2 · 预算来源与预占

### 4.1 原理（为什么必须是绝对时刻 + 预占）

`ResearchDeadline` 的本币是 `expires_at`（`time.monotonic()` 上的绝对时刻）。`remaining()` 每次现算。若把「再给 20 秒」当相对值往下传，每一跳重新 `from_timeout(20)`，总墙钟会膨胀——这是本仓已经踩过、写进 `CLAUDE.md` 的原则。

预占不是记账装饰：先算「能不能给」，能给才发 IO，并把**同一个秒数**传给 `retrieve(..., timeout=granted)`。只在 telemetry 写 `reserved=20`、实际 `timeout=90`，就是「授予的额度没传到执行者」。

### 4.2 从哪 reserve

来源是 `verify(..., deadline=root_deadline)` 手里那一条**根 deadline**，不是新铸一条、也不是改 `ResearchPolicy.for_tier()` / `_REPAIR_SECONDS_CAP` / T（`R-20260816-07` 绊线）。

时刻：首判 `_run_judge` **返回之后**、决定走纯语义早退之时。此时草稿已在、首判已花过钱，剩下的墙钟在今日纯语义路径上本将闲置（早退不再判），但下游仍可能进入 `_resume_for_gap`（已有修复窗）。所以预占必须给修复窗留地板，不能把根 deadline 吃干。

计算（实施按此顺序，禁止另写降档函数）：

```
remaining = deadline.remaining()                          # 绝对时刻现算
available = deadline.stage_timeout(V11_RETRIEVE_CAP)      # 已扣 synthesis_reserve
# V11_RETRIEVE_CAP = 30.0  —— 复用 episode_tools.retrieve_kb 的 min(timeout, 30)
# 不新发明 16 / 25 / 45
```

`stage_timeout` 已经做了 `remaining − synthesis_reserve`。standard 档 reserve=20：根上还剩 40s 时，available=20；还剩 25s 时，available=5。

### 4.3 余额不足：fail-closed 回现行为

| 条件 | 行为 | `v11_skip_reason` | 用户可见 |
|---|---|---|---|
| 开关关 / 无 `retrieve_fn` | 不开枪 | `disabled` / `no_retriever` | 与今日 V8 完全相同 |
| `available < HYBRID_MIN_REMAINING_SECONDS`（15.0） | 不开枪 | `budget` | 与今日 V8 完全相同 |
| `deadline.expired` | 不开枪 | `budget` | 与今日 V8 完全相同 |
| 预占成功 | `timeout=granted` 调 `retrieve`；`select_mode_for_remaining("hybrid", granted)` | （开火） | 见 §5.4 句子命运 |

v1 **不**在 `available ∈ [4, 15)` 时降到 BM25 再打。原因：本单要救的是因果 / 环节类语义缺口，BM25 短窗对这类 query 的期望收益低，却仍占用修复窗地板；且现有语义夹具大量 `from_timeout(5)`，15.0 一刀正好让它们自动 skip（§5.2）。`select_mode_for_remaining` 仍被调用——传入的 `granted ≥ 15` 时它返回 hybrid，真值表与 15.0 阈值一字不改。

零新降档函数：禁止 `select_mode_for_v11`、禁止把 15.0 抄成 12、禁止给 V11 开 `rerank` 特例。请求 mode 与首轮相同：`"hybrid"`。V9b 的 rerank 门控继续只走 `_DENSE_MODES`；V11 不请求 `rerank`。

### 4.4 额度必须到达执行者

| 授予 | 执行者 | 怎么传 | 禁止 |
|---|---|---|---|
| `granted` 秒 | `kb_rag.retrieve` | `timeout=granted`（这是今日 `select_mode_for_remaining` 的唯一 remaining 入口） | telemetry 写 15、timeout 仍 90；或 `timeout=30` 而 `available=18`（对执行者撒谎） |
| 同一 `expires_at` | `_run_judge`（若重判） | 仍传原来的 `deadline`，让它自己 `remaining()` | `from_timeout(50)` 另开一条判官窗 |
| V9a 换窗 | `reexcerpt_hits` | 走 `retrieve()` 汇合点，自动执行 | V11 自己再写一套摘录 |

重判是**尽最大努力**：检索回来后若 `deadline.remaining()` 已不够一次 `_run_judge`（现有 `attempt_timeout <= 0.001` 分支），**不抬 T、不另授窗**，`v11_outcome=retrieved_no_rejudge`，标按 V8 留下。这不是第二套判官预算，是根 deadline 的自然耗尽。

### 4.5 与已有修复窗的关系（不是新窗）

今日已经有的窗，V11 **不得再加一条**：

| 窗 | 在哪 | V11 |
|---|---|---|
| `_repair` 删句 | `SemanticEpisodeVerifier._repair` | 不调用（纯语义路径本来就不调用） |
| 机械删句后再审 | 同 `verify()` 里 second/third `_run_judge` | 不进入这条路径 |
| `_resume_for_gap` | `continuous_turn_adapter` 在 `verify()` **之后** | 靠 `stage_timeout` 扣掉的 `synthesis_reserve` 保命；V11 超时不得把 episode 打成 unavailable |
| `repair_unfulfilled_answer` | `conversation_orchestrator` | 不碰 |
| agent_episode 模型 502 重问价 | `agent_episode` `repair_deadline` | 不碰 |

V11 是「早退路上的一次 retrieve + 可选一次 grounding 重判」，不是修复窗：不改 draft、不 resume 模型写稿、不增加 `max_repair_cycles`。

---

## 5. 项 3 · 管线位置与既有钉兼容对账

### 5.1 接在哪（调用点，不是补丁）

只在 `verify()` 这一处早退之前插入，三处 `_repair` 调用点**一个都不动**：

```
first = _run_judge(...)          # 首判，已有
first = 三道闸（数值 / 元披露 / 表外 E）
if first.report.passed: return   # 不动
first_repair_indexes = _plan_repair_indexes(...)   # V8 已有
if not first_repair_indexes:
    # ★ V11 唯一入口：纯语义早退
    maybe_guided_retrieve_and_optional_rejudge()
    return _completed_public(...)  # V8 标注仍走 _project_semantic_quality_marks
# 以下机械路径整段不动：_repair → 再审 → 第三次
```

`services/` 禁止 import `runtime/`。`retrieve_fn` 由 adapter 注入，形状与 `judge_fn` 相同：可测、默认可空。默认空 = 所有现有 `SemanticEpisodeVerifier(judge_fn=...)` 夹具自动 skip。

### 5.2 与首判 / 再判钉的组合（逐条）

| 钉 / 行为 | 今日 | V11 之后 | 要重钉？ |
|---|---|---|---|
| 纯语义 `calls == 1` + 「不得发起 deletion rejudge」 | `from_timeout(5)` 且无 `retrieve_fn` | 5s → `available < 15` → skip；无 `retrieve_fn` → skip。`calls` 仍为 1，断言原文不动 | **不重钉** |
| 机械再审 `calls == 2\|3` + 「稿必须变短」 | `first_repair_indexes` 非空 | V11 不进入该路径。C 簇夹具、触发物、断言全部不动 | **不重钉** |
| `_repair` 函数体 / 字节 | 删句 + 补槽 | 零 diff | **不重钉**（硬约束） |
| V8 留句+【质检存疑】产品钉 | 语义句在 `public_answer` | skip 时完全同 V8；开火但未撤标时同 V8；仅 `lifted` 时该句**去掉**存疑标但仍在稿里 | 现有 V8 钉用 5s/无 retriever，**不重钉**。新文件加 lifted 夹具 |
| `_VIEW_CALLERS` | `_project_semantic_quality_marks` 已登记 | 公开稿仍只从该函数出（撤标 = 少调用 `_annotate` 或从 `_semantic_reject_texts` 拿掉已放过的句）。不新增 `view()` 出口 | **不重钉**（不新出口就不改登记表） |
| `MAX_SEMANTIC_JUDGE_ATTEMPTS = 3` | 机械路径最多 3 次 `_run_judge` | V11 的 grounding 重判**另计**，不算进这 3 次，也**禁止**再把句号喂给 `_repair`。机械路径仍是 1+1+1 | 不改常数。新钉：V11 重判后 `first_repair_indexes` 仍为空 |
| W1 块级降级 / C3 全灭 | 机械连删 | 不触发 V11 | **不重钉** |
| composer `repair_grounded_composer_answer` | 范围外 | 仍范围外 | 禁止顺手改 |

结论：v1 **没有**「必须改现有 `calls==2|3` 断言」的条目。兼容路径是「触发面缩到纯语义早退 + 15s/无 retriever 双闸」，不是改安全网。

### 5.3 若有人想在混合案开火——为何必须另开、怎么迁

混合案今日：首判 → 机械句进 `_repair`（稿变短）→ 再审（`calls==2`）→ 或再删再审（`calls==3`）。

若在 `_repair` **之前**插 V11 重判：多一次 `_run_judge`，C 簇 `calls==2` 会变成 3，第三次机械再审可能顶满 3 次上限，终端删句钉红。

若在 `_repair` **之后**插：再审已经假设「稿比首判短」；再塞回检索 + 重判同一短稿，会把「可选再审」和「grounding 重判」缠在同一 `calls` 账上。

迁移方案（**本单不实施**，只留指针）：另开 `V11b`，给 grounding 重判独立计数器，C 簇继续只认 deletion rejudge。在那之前混合案 fail-closed 不开枪。

### 5.4 回检索后句子的命运（兼容路径）

默认是 V8：**标留下**。撤标是窄门，不是默认。

```
retrieve 之后
├─ 无新命中 / retrieve 失败
│    → 不重判。outcome=retrieved_empty（或 skip 的 budget 已在开枪前处理）
│    → _semantic_reject_texts 原样 → 公开稿继续【质检存疑】
├─ 有命中，但 remaining 不够一次 _run_judge
│    → 不重判。outcome=retrieved_no_rejudge
│    → 标留下（没有裁判看过新卡，不许撤）
└─ 有命中，且还能 _run_judge 一次
     → 用**同一份 draft 分句** + **仅本请求可见的**扩展 evidence_registry
     → 禁止把新卡写进 verified.outcome.evidence（v1 不改结构核验/绑定/hash）
     → 重判结果：
        ├─ report.passed 或某语义句号不再出现在 rejected
        │    → 只从 _semantic_reject_texts 拿掉被放过的那些句 → 那些句撤标
        │    → 其余句保留标
        │    → outcome=lifted（若至少一个撤标）或 still_annotated
        ├─ 仍拒同一批语义句
        │    → 标全留。outcome=still_annotated
        ├─ 重判 unavailable / 畸形 / 超时
        │    → 标全留。outcome=retrieved_no_rejudge（fail-closed，episode 仍 completed/repaired）
        └─ 重判第一次给出**机械**句号
             → **不得**调用 _repair。当 still_annotated 处理。
               （机械闸已在首判后跑过；此时再删会破坏「早退路径不缩稿」）
```

never-add：重判不得改 draft、不得让判官写正文。撤标是少打 harness 标，不是加字。

禁止：用「新命中 excerpt 与拒句有字面重合」做启发式撤标。那是没有裁判的放行，假阴性会把未核验句当正文（W1 诚实红线）。

### 5.5 需要重钉的条目（仅新钉，不是改旧钉）

现有钉不改断言。实施时**新增**文件（建议 `intelligence/tests/test_v11_judge_guided_retrieval.py`），覆盖：

1. 纯语义 + `retrieve_fn` 空命中 + 长 deadline → 仍打标，`calls` 仍 1（不重判空库）。
2. 纯语义 + 命中 + 重判放过该句 → 该句在稿、无存疑标；draft 字节不变。
3. 纯语义 + 命中 + 重判仍拒 → 标在。
4. `available=14.9` / `from_timeout(5)` → `retrieve_fn` 调用次数 0。
5. 机械拒句夹具（表外 E / `99999点`）+ 注入 `retrieve_fn` + 长 deadline → 调用次数 0。
6. 同一 verifier 第二次 `verify()` → 第二次 `retrieve_fn` 次数 0。
7. 重判返回机械句号 → `_repair` 探测包装计数仍 0，稿长不变。

旧 C 簇 / V8 产品钉：回归绿即可，不改预期。

---

## 6. 项 4 · query 构造（确定性，不调 LLM）

### 6.1 为什么不值得再调一次 LLM 起 query

| | 规则拼 query | LLM 起 query |
|---|---|---|
| 成本 | 0 墙钟、0 token | 再一次完整模型调用，且吃同一条 `root_deadline` |
| 失败 | 拼差 → 空检（`retrieved_empty`，可观测） | 改写成另一题 → 检回不相关卡 → **误撤标**（不可用空检发现） |
| 与 V8 | 判官合同是句号+自由文本，句子本身就是 query | 等于让模型解释自己的 issue，筛 3：模型越强，query 越「圆」，越偏离被拒的那句 |
| 可测 | 纯函数，夹具锁液冷三句 → 固定 query | 要 mock 模型，钉会漂 |

值得调 LLM 的情形是「句子是代词/空壳、issue 才有名词」。出发样本三句都是实名词（散热升级 / 快接头 / 风冷改良）。v1 用规则；若 live `retrieved_empty` 率高且人工看 query 缺主语，再立增量，不在本单打开。

### 6.2 规则（实施可写成无 IO 纯函数）

输入：`frame.subject`、`frame.raw_question`、`_semantic_reject_texts`（被拒句原文）、`_semantic_reject_issues`（自由文本）。

步骤：

1. **骨干 = 被拒句，不是 issue。** 液冷若用 issue「因果无据 / 发明环节 / 外部原因偷渡」当 query，检回的是质检话术，不是液冷页。
2. `subject = frame.subject.strip()`；空则从 `raw_question` 取到第一个「怎么看/如何/为什么」之前的前缀，再空则整句 `raw_question`。
3. 每条被拒句：去掉【质检存疑】/【质检降级】、截到 40 字、去首尾标点。保留顺序，最多 3 条（出发样本恰好 3；再多也只一枪，防 query 膨胀）。
4. issue 文本只贡献**非元话语** token：去掉停用闭集 `{无据, 因果, 发明, 环节, 外部原因, 偷渡, 证明不了, 质量不够, 证据不足, 第N句, 句N, code, subject, ::}` 以及 `code=` 收据串。剩下的 CJK 连续 ≥2 字，若**尚未**出现在步骤 3 里，追加。issue 对出发样本应贡献 **0** 个新 token——这是夹具断言，防止以后有人改成「issue 优先」。
5. 拼接：`"{subject} {sent_1} {sent_2} {sent_3} {extra}"`，空白折叠，总长 cap **80** 字（与粗管道 `budget_query` 同量级，不新发明 128/256）。
6. 去重后若为空：回退 `"{subject} {raw_question}"`，再空则 `raw_question`。
7. **整 episode 一条 query。** 三句合成一枪，不循环 retrieve。

液冷样本的期望形状（实施夹具锁「含这些核、不含元话语」）：

```
液冷服务器 散热升级 … 快接头 … 风冷改良 …
```

不得出现「无据」「发明环节」「偷渡」。

`retrieve` 调用与首轮对齐：`k=6`、`mode="hybrid"`、`excerpt_chars=240`、`budget_query=frame.raw_question`（档位预算键仍是原题，避免 V11 query 污染缓存键语义——`cache_scope` 继续用 `task_id`）。V9a 换窗自动发生。

---

## 7. 项 5 · 遥测字段 + 仓内读方

### 7.1 字段契约（缺 = None，禁止用 0 冒充「没开火」）

挂在 `SemanticEpisodeOutcome` / `to_dict()` → 落盘 `continuous-episode.json` 的 `semantic_verifier` 下。历史 run 无这些键 → 审计报不可判，不报 0（抄 V9a `pointer_dropped`）。

| 字段 | 类型 | 含义 |
|---|---|---|
| `v11_triggered` | `bool` | 是否已预占并调用了 `retrieve_fn` |
| `v11_skip_reason` | `str \| None` | `disabled` / `no_retriever` / `no_semantic` / `mechanical_pending` / `budget` / `already_used` / `passed`；开火则为 `None` |
| `v11_query` | `str \| None` | 实际送进 retrieve 的 query；未开火 None |
| `v11_reserved_seconds` | `float \| None` | 预占并传给 `timeout=` 的秒数 |
| `v11_deadline_expires_at` | `float \| None` | 根 `deadline.expires_at`（绝对时刻）。只写 remaining 相对值 = 违反全链绝对 deadline |
| `v11_effective_mode` | `str \| None` | `select_mode_for_remaining` 的返回 mode |
| `v11_hit_count` | `int \| None` | 回检索命中数；未开火 None（空检是 0，必须能与 None 分开） |
| `v11_new_hit_count` | `int \| None` | 与首轮已投递 evidence 去重后的新卡数；未开火 None |
| `v11_rejudge_called` | `bool` | 是否调用了 grounding `_run_judge` |
| `v11_outcome` | `str` | 闭集：`skipped` / `retrieved_empty` / `retrieved_no_rejudge` / `lifted` / `still_annotated` |
| `v11_lifted_count` | `int \| None` | 撤标句数；未开火 None |
| `v11_still_doubted_count` | `int \| None` | 仍带标的语义句数；未开火 None |

`v11_outcome` 就是 §1.2 的可区分结局。A/B 与审计只认这个闭集，不另造「成功/失败」。

### 7.2 仓内读方（写了没人读会被拦）

先例：V9a 的 `pointer_dropped` / `reexcerpted` 接进 `scripts/audit_ceiling_sensors.py`；`check_unread_fields.py` 扫 `intelligence/` + `market_feature_store/`，**不扫 `scripts/`**，且测试目录跳过。所以只改审计脚本不够——SCAN_DIRS 里必须出现字段名的读（`to_dict` 的字符串键、或专门的 artifact 解析）。

实施必做（三处，缺一则门禁或合同不合格）：

1. **`SemanticEpisodeOutcome.to_dict`**：上表每个键以字符串字面量写出（`check_unread_fields` 认字符串为读）。
2. **`scripts/audit_ceiling_sensors.py`**：在 `semantic_verifier` 上读 `v11_outcome` / `v11_hit_count` / `v11_triggered` / `v11_skip_reason` / `v11_lifted_count`；缺字段 → None，不报 0、不翻 unjudgeable（与 `pointer_dropped` 同一口径）。聚合：四结局计数、开火率、空检率、撤标率。
3. **`intelligence/` 内再有一处 Load**：建议在现有 episode artifact 解析（`to_dict` 已算；若门禁仍红，加一个 `summarize_v11_telemetry(payload)` 纯函数给审计和 A/B harness 共用）。实施跑 `python -m scripts.check_unread_fields`，新属性不得进「只写不读」。

禁止：只往 `private_artifact` 塞一坨、UI/模型/审计都不读。那是 CLAUDE.md「只写 telemetry 不生效」。

### 7.3 开关与默认

`FINANCE_V11_GUIDED_RETRIEVE`：未设或 `0` / `false` = 关（**默认关**）。与 V8 默认开相反——V8 是收窄删除权（更便宜、更安全），V11 是花墙钟。默认关才能「不碰 8792」：生产行为保持 V8。A/B 开臂用环境变量，不改档位常数。

---

## 8. 项 6 · A/B 预注册草案

开跑前锁死。结论未出不得改判据、不得温数字。不占 8792；候选臂 sidecar（抄 V6：拒绝 8792/8793/8795/8799/8801）。

### 8.1 结构

| 项 | 值 |
|---|---|
| 探针用户 | `probe-v11-<mmdd>`（字段是 `user` 不是 `user_id`） |
| 对照臂 | 生产默认（V11 关 = 今日 V8）。进程可复用验收 sidecar，**不改 8792** |
| 候选臂 | 同题、同模型、同档位；仅 `FINANCE_V11_GUIDED_RETRIEVE=1`，并注入 `retrieve_fn` |
| 交替 | 试次奇偶交替（先对照后候选），消除时段 |
| n | 每臂 **n≥50** 走到 episode 的样本。n<50 结论栏只写「进行中 / 未达标样本量」（抄 V6） |
| 题池 | 产业链 / 个股 / 概念都要有。**必须含**「液冷服务器产业链怎么看」（出发样本同题重放）。**不得**把 V10 held-out 题池当本单题库（R3 §B2 禁复用） |
| 入口 | `POST /api/conversations` → `/messages`（continuous episode）。不用 `live_probe ask` / `POST /api/runs` |

### 8.2 指标与合取判据（长度守门写死）

字段路径（缺字段 → 该样本不可判，不报 0）：

| 指标 | 路径 |
|---|---|
| 完稿 | `semantic_verifier.status == "completed"` 或 finish `stop_reason == "model_finish"`（A/B 报告须写清用哪一条，开跑前锁） |
| 答案长度（守门） | `outcome.draft` 字符数（与 V6 同一本币；V11 **禁止改 draft**，此值两臂应接近不变——守门防的是实施偷偷改稿） |
| 公开稿长度（副表） | `semantic_verifier.public_answer` 字符数（撤标会少几个「【质检存疑】」，允许略降，**不进合取**） |
| 存疑标率 | 公开稿含【质检存疑】的比例 |
| V11 结局 | `v11_outcome` 四+skip 分布 |
| 档位 | `v11_effective_mode`；对照臂应为 None |
| 修复窗依赖 | 是否存在 `_resume_for_gap` / `events[kind=repair_reentry]` |
| 判官状态 | `judge_status` 分布 |

**预注册合取（逐字，开跑后不得拆开）：**

> 候选臂完稿率较对照不下降（允许 ±2pp 采样噪声），**且** `outcome.draft` 长度中位数不下降 → 该候选才可进入「默认开」立项；否则记未达标并留读数。完稿率上升但长度下降 = 未达标（V6 形状：+46pp 仍因 −6.2% 否决）。

副观察（不进合取、不得单独结案）：`lifted` 率、`retrieved_empty` 率、`still_annotated`（有命中）率、修复窗依赖率。`lifted>0` 且 `retrieved_empty` 与 `still_annotated` 同时非空，才算「两种结局可区分」这条设计假设被测到。

### 8.3 判官调用成本画像（给「不在本批」的强判官弱起草）

R3「不在本批」写明：模型分层等 V11 给出判官成本画像再议。本设计能锁的上界：

| 调用 | 今日 | V11 开且开火 |
|---|---|---|
| 首判 | 1 次 / episode（结构能放行时） | 1（不变） |
| 机械再审 | 0–2 次（`calls` 总 2–3） | 0（开火路径是纯语义，不进再审） |
| grounding 重判 | 0 | 0 或 1（仅有命中且剩余够） |
| 回检索 | 0 | 0 或 1 次 `retrieve`，`timeout≤30`，热态经验 4–6s（检索档位设计已测） |
| 起 query 的 LLM | 0 | **0**（§6） |

最坏墙钟增量：≤30s retrieve + 一次判官窗（现有 50s 上限，但受根 remaining 裁剪）。期望增量远小于此：多数 episode 不触发；触发后空检不再判。

**还不够给「强判官弱起草」立项的**：缺的是 live 开火率 × 重判墙钟 p50/p95。A/B 报告必须附这两列。没有读数之前，不得把起草模型降档。

---

## 9. 项 7 · 台账行草稿 + 变异计划

### 9.1 台账行（实施 PR 逐字抄进 `docs/prediction-ledger.md` Open 表，不得转述）

立案时 `last_updated` 加一句「`R-20260822-05` 立案 pending」。执行方不得标 `confirmed` / `refuted`。本设计回合**不写进台账**。

**ID**：`R-20260822-05`

**来源**：R3 spec §B3；设计 `docs/superpowers/specs/2026-08-22-v11-judge-guided-retrieval-design.md`

**fix_type**：`HARNESS_FIX`

**verification_prediction**（逐字）：

> 部署并打开 `FINANCE_V11_GUIDED_RETRIEVE` 后：① 纯语义拒句（`first_repair_indexes` 空、必需块内 ≥1 条 V8 存疑句）且 `stage_timeout(30) ≥ 15` 时，每 episode 至多 1 次 `kb_rag.retrieve`，query 由被拒句确定性拼出、不含「无据/发明/偷渡」元话语，不另调 LLM 起 query；② 机械硬违规（`numeric_unsupported` / 表外 E / 星期 / 路径）与混合案 `retrieve` 调用次数为 0；③ 回检索后 draft 字节不变、不进入 `_repair`；空检或重判仍拒则【质检存疑】保留，重判明确放过的句才撤标；④ `v11_outcome ∈ {skipped, retrieved_empty, retrieved_no_rejudge, lifted, still_annotated}` 可区分「没开枪 / 库空 / 有命中仍拒 / 撤标」，缺字段不得当 0。预测失败形状：机械路径开火、每题超 1 枪、draft 被改写、无重判却撤标、或 A/B 完稿率下降 / `outcome.draft` 中位长度下降。

**怎么验**（逐字）：

> 离线 TDD：新文件 `intelligence/tests/test_v11_judge_guided_retrieval.py` 先红后绿，覆盖设计 §5.5 ①–⑦。变异 §9.2 至少 3 条，击杀数写入交付。`test_episode_semantic_verifier` 里 monotonic rejudge / `calls==2|3` 钉与 V8 留句钉保持原断言绿；禁止改 `episode_semantic_verifier._repair` 函数体。`select_mode_for_remaining` 与 15.0 阈值零 diff。`scripts/audit_ceiling_sensors.py` 能读 `v11_*`，缺字段记 None。`check_unread_fields` 无新增只写不读。live/A/B：验收方用 `probe-v11-<mmdd>` sidecar，不占 8792；合取判据见设计 §8.2（完稿率不降 **且** draft 长度中位不降）。执行方不得自行标 confirmed。单发不得结案。台账行实施时才抄入 Open 表。

**outcome**：`pending`（立案时）

### 9.2 变异计划（≥3，改前先 commit）

| # | 变异 | 必红的钉 |
|---|---|---|
| 1 | 分区器或触发器把机械句当语义、或混合案仍调 `retrieve_fn` | §5.5 ⑤：机械夹具 retrieve 次数 0 |
| 2 | 把 15.0 判断改成 `< 5` 或绕过 `stage_timeout`，让 `from_timeout(5)` 仍 retrieve | §5.5 ④ |
| 3 | 空检或重判 unavailable 仍从 `_semantic_reject_texts` 清句（无裁判撤标） | §5.5 ① / ③ |
| 4（备用） | 重判机械句号后调用 `_repair`，或第二次 `verify()` 再 retrieve | §5.5 ⑥⑦ |

交付至少落地 1–3。4 可作加分。击杀数写入实施验证文档，不写进本设计的「已验证」。

---

## 10. 项 8 · 失败形状预测与应对

### 10.1 回检索找到的证据稀释正确结论（合同点名）

**形状：** 新卡与原结论弱相关或相反（例如检回一篇「风冷仍占主流」的综述），重判或后续 `_resume_for_gap` 把原本正确的液冷主线改弱、改掉、或拼进矛盾句。

**为何会发生：** 检索优化相关度不是优化「支持这句」；k=6 必然带进邻页。若允许改 draft 或把新卡并进 `outcome.evidence` 供修复窗改写，稀释是默认值。

**应对（设计已锁）：**

- 不改 draft（never-add、无第二修复窗）。
- v1 新卡**只进这轮 grounding 重判的 `evidence_registry`**，不写回 `verified.outcome.evidence`，后续 gap-repair 看不见它们。
- 撤标只在重判明确不再拒该句；重判超时/畸形 → 标留下。
- 禁止启发式重合撤标。
- A/B 副表看「公开稿是否出现首轮没有的新公司/新数字」——若候选臂系统性多出未绑定数字，记稀释风险，不得靠完稿率粉饰。

### 10.2 预算被回检索吃掉导致完稿率下降（合同点名）

**形状：** V6 的亲戚。V11 在 `verify()` 里吃 10–30s，根 deadline 在 `_resume_for_gap` 前耗尽，`TimeoutError: research deadline exhausted before semantic verification` 或修复循环进不去，完稿率下降。或 retrieve 挂起直到 timeout，把本可 completed 的 V8 早退拖死。

**应对：**

- 默认关，8792 行为不变；先 A/B 再谈默认开。
- `granted = stage_timeout(30)`，已扣 `synthesis_reserve`，修复窗地板仍在。
- `available < 15` 不开枪（含全部 5s 夹具）。
- `timeout=granted` 必须到达 `retrieve`；热态 4–6s，30s 是帽不是目标。
- 重判不够就 `retrieved_no_rejudge`，**不得**把 episode 打成 unavailable。
- 每 episode 一枪，预占后失败不补。
- 合取判据把完稿率写死：候选臂完稿率下降 = 未达标，即使 `lifted` 很好看。

### 10.3 其它已预见形状

| 形状 | 应对 |
|---|---|
| query 吃进「无据/偷渡」→ 空检或检到质检话术 | §6 停用闭集 + 夹具锁「issue 对液冷贡献 0 token」 |
| 假撤标（弱相关卡骗过重判） | 只认重判句号；A/B 抽检 `lifted` 样本人工看是否仍无据；单发不结案 |
| 旗标事后才置位，空检后再打一枪 | 副作用前预占 |
| 只写 `v11_*` 无人读 | §7.2 三处读方 + unread-fields |
| 与 V9a/V5 打架 | 走 `retrieve()` 汇合点，换窗/结构过滤自动发生；不复制一条检索 |
| 默认开把 8792 变慢 | 默认关 |

---

## 11. 硬约束（实施 PR 审查清单）

1. 不改 `_repair` 函数体、参数、返回值、删句+补槽语义。
2. 不加第二修复窗；不 resume 模型按新卡改稿。
3. 每 episode ≤1 次回检索；旗标在 IO 前预占。
4. 机械 issue / 混合案永不触发。
5. 预算预占：绝对 `expires_at`；`granted` 必须等于传入 `retrieve` 的 `timeout`；不足 fail-closed 回 V8。
6. 复用 `select_mode_for_remaining`，零新降档函数，不改 15.0 与 `_DENSE_MODES`。
7. 不额外调 LLM 起 query。
8. 不碰生产 8792；不跑 live 探针（本设计回合）；不改台账 outcome。
9. 不动 `filter_structural_noise` fail-open、不动 V9a `reexcerpt_hits` 既有行为。
10. 公开稿继续走 `view()`；不新增未登记出口。
11. 不改 T / `_REPAIR_SECONDS_CAP` / 档位 total/reserve / 工具批。
12. 台账行实施时逐字抄 §9.1，不得转述。

---

## 12. 实施时不要做的事

- 不要用 `re.search("因果|无据|发明")` 当触发器。
- 不要让判官增报 `issue_type` / `needs_retrieval` 来决定开不开枪。
- 不要在 `_repair` 里「顺便」回检索。
- 不要把 grounding 重判算进 `MAX_SEMANTIC_JUDGE_ATTEMPTS` 然后去改 C 簇的 `calls==2|3`。
- 不要把新命中 merge 进 `outcome.evidence` 再交给 `_resume_for_gap` 改写（稀释主通道）。
- 不要为了撤标去改 draft。
- 不要把 `timeout=90` 传给 retrieve 却在遥测写 `reserved=15`。
- 不要默认开着合进生产。
- 不要把 V10 held-out 题拿来跑本单 A/B。
- 不要在本设计回合改 `docs/prediction-ledger.md`。

---

## 13. 本文件是什么 / 不是什么

- 是：§B3 八项的可实施合同、触发/预算/兼容真值表、query 规则、遥测闭集、A/B 合取判据、可抄台账行、判官成本上界。
- 不是：补丁、默认开、对 `R-20260821-19` 机械半腿的代结、对 V9b/V10 的授权、对「强判官弱起草」的立项。

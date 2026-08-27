# V8 · 语义质量删除权收窄（设计）

- 日期：2026-08-22
- 作者：实施设计（本单只出设计，不写生产代码、不改测试、不部署）
- 状态：待验收方确认后才进代码
- 上游：R2 spec `2026-08-21-inputside-closeout-r2-design.md` §V8；R1 spec `2026-08-21-ceiling-shape-closeout-design.md` §W1 目标 3
- 已落地先例：W1「降级保留」（`docs/verification/2026-08-21-w1-required-block-degrade.md`）；槽位保护 `R-20260821-04` confirmed
- 台账行：`R-20260821-19`（**实施时**才立案；文末给出可逐字抄的预测与验法）
- 基线锚：本设计写在 worktree `docs/v8-deletion-rights-design`，行号相对 `gitea/main`（`0999ed02`）

> 角色分离沿 R2 纪律：本文件是设计合同，不是施工 diff。合并需验收方复算 + 用户确认。

---

## 0. 一句话

W1 已经把「必需输出块被整格换成道歉横幅」改成「残块 +【质检降级】」。V8 要收的是下一步：语义质量类 issue 对必需块**连那一句也不删**，改成标注 + 降级呈现。机械硬违规（无据数值、表外引用，以及代码里已经存在的两条确定性闸）的删除权不动。实现必须走**新旁路**，禁止改 `_repair` 现行语义——这是 W1 实测「直接接 `_repair` 会砸约 40 条修稿钉」的根。

人话：判官可以继续说「这句证明不了」，但不能再把这句话从用户眼前抠掉；它要是编了没出处的数、或引用了桌上没有的 E 号，那一句照删。

---

## 1. 背景

### 1.1 这条线已经走到哪

| 台阶 | 台账 | 做了什么 | 没做什么 |
|---|---|---|---|
| 槽位保护 | `R-20260821-04` **confirmed** | 判官对槽内数字无删除权；live 三样本零误删，真违规仍被删 | 不管散文里的语义质量句 |
| W1 块级降级 | `R-20260821-07` **pending**（live 未激发 marker_loss 自然样本） | 句级合法删除后残块保留 +【质检降级】；道歉横幅只归 C3 全灭闸 | R1 目标 3「语义质量对必需块零删除权」 |
| V8（本单） | `R-20260821-19` 未立 | — | 语义类 issue 仍走 `_repair` → `_drop_rejected_sentences` 物理删句 |

W1 执行方原文（验证文档「已知边界」）：接到 `_repair` 上会拆掉判官修稿安全网（既有 monotonic rejudge / 调用次数钉红约 40 条）。本单把这约数还原成文件级清单（§5），并给出「不改 `_repair`」的兼容路径。

### 1.2 现行删句机（必须绕开、不能改）

`SemanticEpisodeVerifier._repair`（`intelligence/services/episode_semantic_verifier.py:2200-2249`）的现行语义是：

1. 用 `_drop_rejected_sentences`（同文件 `:3447`）按句号整句抠掉；
2. 用 `_restore_lost_observations`（`:3394`）把被连坐的槽内真值补回【预取事实】行；
3. 再 `verify_episode_outcome`。

它**不看 issue 类型**。谁把句号塞进去，谁就被删。W1 只改了删完之后的呈现（`_marker_loss_partial_public`，`:2347`），没有改「哪些句号进 `_repair`」。

LLM 判官的出参只有三字段（`:326-333`）：`passed`、`rejected_sentence_indexes`、`issues`（**自由字符串列表**）。没有 typed issue enum。分类必须按**谁产出了这个句号**（确定性闸 vs LLM），不能按 issue 文案做关键词匹配——模型换一种说法，白名单就漂。

### 1.3 约束三筛：哪一段是保下限，哪一段是封上限

权威尺：`~/harness-reference/PLAYBOOK.md` §约束三筛。分界线：**harness 该约束事实的来源，不该约束话怎么说。**

先例 `R-20260821-04` 已证：对槽内数字收窄删除权 = **保下限**（live 零误删，真违规仍被删）。V8 把同一手法推广到「语义 issue × 必需块」。

| 约束片段 | 筛 1 拦输入还是输出 | 筛 2 失效变错还是变笨 | 筛 3 模型变强一倍 | 定性 | V8 处置 |
|---|---|---|---|---|---|
| 无据数值 / 发明阈值（`numeric_unsupported`） | 拦输出，但判定本身是拦输入（数在不在已投递观察值里，代码已会算） | 变错（假数上桌） | 不挡：再强也不许编没出处的阈值 | **保下限** | **删除权不收窄** |
| 表外引用（E 号反解不到卡） | 同上：引用是否在注册表里是机械事实 | 变错（指向不存在的证据） | 不挡 | **保下限** | **删除权不收窄**；今日还走 LLM 删除路径，实施须补确定性闸（§3.3） |
| 星期 / 路径趋势两条本地闸（`calendar_weekday_mismatch` / `path_trend_mismatch`） | 确定性对账，不靠 LLM | 变错（日期对不上、趋势说反） | 不挡 | **保下限** | 与无据数值同档，**不收窄**（R2 点名的是前两项；这两条代码里已经是同一类机械预检，一并列入白名单，避免实施时漏删） |
| 槽内数字（R-04 已落地） | 已改写成拦输入（系统填槽） | — | — | **保下限（已证）** | 不动 |
| LLM 语义质量否决（「因果不够 / 质量不够 / 证明不了 / 外部原因无据」） | 纯拦输出 | 变笨（真话被连坐，Gate 1 原事故） | **会挡**：稿越长、判断越细，被同一刀误伤越多 | **伪装成下限的上限** | **改写**：必需块内零删除权，改标注 + 降级 |
| 块级横幅替换（W1 已改） | 拦输出且破坏粒度 > 错误粒度 | 变笨 | 会挡 | 封上限（已改写） | 不动 W1 |

**必须保留的「拦输出但保下限」**：机械硬违规白名单的删句 + C3 全灭闸（`repair_wiped_all_outputs`，`:1035/:1170/:1295`）+ 判官 never-add（标注由 harness 生成）。

**必须改写的「封上限」**：LLM 语义 issue 对必需块的整句删除权。

---

## 2. 目标行为

沿 R2 V1–V8 四段式的行为面。实施时逐条可测。

1. **分流在 `_repair` 之前，不在里面。** 新函数（暂名 `_partition_rejected_indexes`）把判官 / 预检产出的句号分成 `mechanical` 与 `semantic`。只有 `mechanical` 传给现有 `_repair`。`_repair` 函数体、参数、返回值、删句 + 补槽语义**一字不改**。
2. **语义类 × 必需块：零删除权。** 句号落在 `required_outputs` 且 grounding 为 `evidence`（以及 W1 已纳入的判断格，见 `_lost_grounded_output_substance`，`:4015`）时，语义 issue 不进 `_repair`。句子留在稿里，harness 生成句级存疑标注，批评进已有「输出质检」段（`conversation_orchestrator._with_review_appendix`，`:1400`）。块不完整时沿用 W1 的【质检降级】+ `gap_output_ids` / `missing` 记账。
3. **机械白名单删除权不收窄。** `numeric_unsupported`、表外引用、以及已存在的星期 / 路径趋势预检，继续 fail-closed 删句。W1 钉②（`test_numeric_unsupported_sentence_is_still_deleted`）保持原断言。
4. **再审协议按路径分叉，不共用一套「稿变短」假设。** 机械删句后的 monotonic rejudge / 调用次数上限（最多 3 次，`MAX_SEMANTIC_JUDGE_ATTEMPTS`）保持原样。语义旁路**不**为「稿没变短」再发起一轮以删句为目的的再审；若再审仍只重复同一语义否决，不得把该句回灌 `_repair`。
5. **静默保留禁止。** 语义句留在公开稿上必须可识别。只进质检附录、正文毫无标记 = 放行未复核内容，破 W1 诚实红线。
6. **范围只限 episode 语义判官这条链。** 不改 `answer_model.repair_grounded_composer_answer`（另一条修稿，Ask 合成用）。不改 `acceptance.py` 的 `episode_fulfilled_hashed`。不加第二修复窗。不动 #298 投影、#289 槽保护、#296 题形降级。

---

## 3. 问题 1：收窄到哪些 issue 类型

### 3.1 判官相关类型全集（从代码抽出，不凭空拟）

类型在三层，不要压成一张假枚举。

#### A. 结构化 `IssueCode`（释放门 + 预检 + 记账）

出处：`intelligence/services/episode_issues.py:17-39`。值是收据 token（`code=<value>`）。

| # | 枚举名 | token | 生产者（本设计关心的） | V8 桶 |
|---|---|---|---|---|
| 1 | `EVIDENCE_EMPTY_HASH` | `evidence_empty_hash` | 结构核验 | 非删句权（释放门） |
| 2 | `EVIDENCE_DUPLICATE_HASH` | `evidence_duplicate_hash` | 结构核验 | 非删句权 |
| 3 | `UNKNOWN_OUTPUT_BINDING` | `unknown_output_binding` | 结构核验 | 非删句权 |
| 4 | `MISSING_REQUIRED_OUTPUT` | `missing_required_output` | 结构核验 | 非删句权 |
| 5 | `GROUNDING_BASIS_MISMATCH` | `grounding_basis_mismatch` | 结构核验 | 非删句权 |
| 6 | `REQUIRED_OUTPUT_GAP` | `required_output_gap` | 结构核验 | 非删句权（PARTIAL_OK） |
| 7 | `UNKNOWN_EVIDENCE_HASH` | `unknown_evidence_hash` | 结构核验 | 非删句权 |
| 8 | `AMBIGUOUS_EVIDENCE_HASH` | `ambiguous_evidence_hash` | 结构核验 | 非删句权 |
| 9 | `EVIDENCE_TYPE_STRIPPED` | `evidence_type_stripped` | 结构核验 | 非删句权（STRIP_OK） |
| 10 | `EVIDENCE_TYPE_UNSUPPORTED` | `evidence_type_unsupported` | 结构核验 | 非删句权 |
| 11 | `FINANCIAL_ANCHOR_MISSING` | `financial_anchor_missing` | 结构核验 / 回填触发 | 非删句权 |
| 12 | `MISSING_MANDATORY_CAPABILITY` | `missing_mandatory_capability` | 结构核验 | 非删句权 |
| 13 | `REQUIRED_OUTPUT_NO_SUBSTANCE` | `required_output_no_substance` | 结构核验 | 非删句权 |
| 14 | **`NUMERIC_UNSUPPORTED`** | **`numeric_unsupported`** | 预检 `_novel_numeric_condition_indexes`（`:2886`）+ 闸 `_apply_numeric_condition_gate`（`:2757`）；单例 `_NUMERIC_CONDITION_ISSUE`（`:230-234`） | **机械硬违规：删除权不收窄** |
| 15 | **`CALENDAR_WEEKDAY_MISMATCH`** | **`calendar_weekday_mismatch`** | 预检 `_mismatched_weekday_indexes`；单例 `:235-238` | **机械硬违规：删除权不收窄** |
| 16 | **`PATH_TREND_MISMATCH`** | **`path_trend_mismatch`** | 预检 `_mismatched_path_trend_indexes`；单例 `:240-244` | **机械硬违规：删除权不收窄** |
| 17 | `MARKER_LOSS` | `marker_loss` | 修稿后记账 `_marker_loss_issues`（`:3791`） | 非删句权（W1 已管呈现） |

释放策略在同文件 `RELEASE_POLICY`（`:60-78`）。缺登记 fail-closed 为 `BLOCK`。

#### B. 送给 LLM 判官的 `_CLAIM_POLICY`（不是判官回传的类型）

出处：`episode_semantic_verifier.py:400-408`。这是**提示词策略开关**，compact 时从 JSON 里丢掉（`:429-430`），判官**不会**用这些 key 作为稳定 issue 类型回传。测试里偶尔把 `unsupported_external_cause_rejected` 当作 issue 字符串，那是夹具习惯，不是运行时枚举。

| key | 含义 | V8 |
|---|---|---|
| `observed_facts_require_direct_evidence` | 观察事实要直接证据 | 语义（LLM 判） |
| `labelled_analytical_inference_allowed` | 允许带标记的分析推断 | 允许，不是否决 |
| `requested_conditional_estimate_allowed` | 允许用户要的条件估计 | 允许 |
| `unsupported_external_cause_rejected` | 无据外部因果 | **语义收窄对象** |
| `unsupported_historical_probability_rejected` | 无据历史胜率 | **语义收窄对象** |
| `unsupported_supporting_statistics_rejected` | 无据支持性统计 | **语义收窄对象** |
| `unsupported_numeric_trigger_rejected` | 无据数值触发 | 已由 A.14 机械闸落地；**删除权不收窄** |

系统提示（`:345-383`）还要求拒：发明外部原因、任意触发阈值、暴露内部标识、口径混用、日期对不上。后两项里「数在不在注册表」已交给 `verified_quantities`（`:358-362`、`:3833`）；「口径混用」仍是 LLM 语义——W1 把它写进机械白名单的「口径分歧下的越界合成」，本设计**不**把「LLM 说口径混了」升级成删句权。槽内数字由 R-04 保护；槽外编造的数走 `numeric_unsupported`。剩下的口径叙事 = 语义，走标注。

#### C. 表外引用（R2 / W1 点名的机械白名单，今日**没有** IssueCode）

出处：

- `_project_semantic_evidence` 注释（`:3886-3894`）：「表外引用（E 号反解不到卡）不做模糊纠正，照旧走判官删除路径。」
- `cited_evidence_ordinals`（`episode_protocol.py:488-494`）：只识别、不校验；「表外序号由消费方反解失败自然落回既有删除路径。」
- `resolve_evidence_refs`（同文件 `:503-533`）对绑定里的越界 E 号硬拒 `unknown_evidence_ref`——那是**绑定路径**，不是公开稿散文里的 E 号。

结论：散文表外 E 号今天依赖 LLM 把该句放进 `rejected_sentence_indexes`。这违反「机械硬违规必须机械可判定」。V8 **不收窄**这张删除权，但实施时必须补一条与数值闸同形状的确定性预检（§3.3），不能继续把「LLM 是否写了『引用不存在』」当作白名单判据。

#### D. LLM `issues[]` 自由文本（无闭集）

判官 schema（`:330-333`）是 `issues: string[]`。生产里出现过的形状（夹具 / 台账，不是枚举）：「因果证据不足」「外部因果无据」「第 N 句质量不够，证明不了…」「证据与句子不一致」「无直接证据支持的外部事实陈述」。**全部是语义收窄对象**，只要该句号不是机械闸同时命中。

#### E. 已有的「不删」豁免（V8 要与之对齐，不重做）

- 元披露句豁免：`_apply_meta_disclosure_exemption`（`:2803`）。「映射为推理层」且不夹带行情数字 → 从 `rejected_sentence_indexes` 拿掉。夹带涨停等价值断言仍拒——那条夹具（`test_meta_disclosure_with_value_claim_is_not_exempted`）今日走删句；V8 后若该句在必需块内且**没有**机械闸命中，改为标注不删（涨停二字本身不是 `numeric_unsupported` 的阈值形）。若实施方能把「披露句夹带未绑定涨跌停」做成确定性闸，可升入机械白名单；本设计不强迫，默认语义。

### 3.2 V8 分类结论（实施真值表）

**机械硬违规白名单（删除权不收窄，必须进 `_repair`）：**

1. `numeric_unsupported`（A.14）
2. 表外引用（C；实施补确定性闸后发给 `_repair` 的句号）
3. `calendar_weekday_mismatch`（A.15）
4. `path_trend_mismatch`（A.16）

句号来源 = 预检集合 ∪ 数值闸补集 ∪ 新表外引用闸。**不**解析 LLM issue 字符串。

**语义类（收窄对象：必需块内不进 `_repair`）：**

- LLM 报的、且不在上述机械句号集合里的所有 `rejected_sentence_indexes`
- 包括 `_CLAIM_POLICY` 里那三条 `unsupported_*` 因果 / 胜率 / 统计，以及一切「质量不够 / 证明不了 / 主体时间不一致」自由文本

**本单不管（不是删句权）：** A 表其余 IssueCode、W1 的 marker_loss 呈现、C3 全灭闸。

### 3.3 表外引用：补闸，而不是信 LLM

实施时新增确定性函数（名称可议，形状锁定）：对 `_numbered_sentences` 每句跑 `cited_evidence_ordinals`，与本轮 `evidence_ordinal_table` 做差。差集非空 → 该句号进 `mechanical`。可选新 `IssueCode.UNRESOLVED_EVIDENCE_ORDINAL`（或等价 token）方便收据；没有新 code 也可以先用稳定序列化串，但**句号必须代码产**。认不出 E 号语法 = 不当表外引用（`cited_evidence_ordinals` 已排除 PE10 / 1.5E8）。

---

## 4. 问题 2：删除权收到什么粒度

三案都只作用于**语义 × 必需块**。机械白名单三案都不适用，继续整句进 `_repair`。

### 4.1 对比

| | 案甲 · 整句降级（推荐） | 案乙 · 句内短语标注 | 案丙 · 标注不删（正文无标记） |
|---|---|---|---|
| 做法 | 句子留下；harness 在句前或句内插入结构化存疑标（如「（质检存疑）」或复用【质检降级】的句级变体）；issue 进「输出质检」 | 只给越界短语加标，其余字不动 | 句子原样；只在文末「输出质检」列 issue |
| 公开稿 | 用户仍读到原判断，但能看见「这句未经核验」 | 看起来最精细 | 看起来最干净，也最像没质检 |
| 失效形状 | 标漏了 → 静默放行（用钉⑤锁住）；标太吵 → 可读性差（可接受） | **判官没有 span**，只有句号。短语切割要第二套对齐，失败形状是：标错槽内真数字（砸 R-04）、或标空 | W1 已否决的静默保留：用户把未复核句当正文引用 |
| 与 never-add | 标文案由 harness 生成，判官不写正文 | 若让 LLM 返回 span，等于让判官改稿 | 满足 never-add，但破诚实红线 |
| 与 `_repair` | 语义句号不传入，函数体不动 | 同左；另增 span 协议 | 同左 |
| 与约 40 条钉 | 见 §5：机械钉不受影响；语义产品钉改预期 | 还要新增 span 钉，爆炸面更大 | 产品钉更好改，但验收过不了诚实红线 |
| 再审 | 稿长不变，禁止「为删句再审」；机械句仍先删再审 | 同甲，外加 span 漂移 | 同甲 |

### 4.2 推荐：案甲（整句降级）

取舍一句话：V8 要收的是**删除权**，不是要做 NER。判官合同是句号，粒度就收到句。短语案看起来高级，实际是在没有 span 的接口上再封一层上限（筛 3：对齐越细，误伤槽内真值的概率越高）。案丙省事，但 W1 目标 5 写明「禁止静默保留」。

呈现最小合同（实施不得发明第二套视觉语言）：

- 句级：该句可见存疑标（harness 常量，建议与 W1 的 `REQUIRED_OUTPUT_DEGRADED_MARK = "【质检降级】"` 同族，避免用户学两套记号）。
- 块级：该句所在必需格若因此「质量降级但仍在」，沿用 W1 块首【质检降级】+ `missing` / `gap_output_ids`（记账继续诚实：质量不够 ≠ 格已履行）。
- 文末：`_with_review_appendix` 原样挂判官 issue。正文在前，质检在后（W1 钉已锁顺序）。

混合句（一句里既有槽内真数又有无据因果）：案甲整句留 + 标。**禁止**为了「只去掉因果」去改 `_drop_rejected_sentences`。槽内真数已由 `_restore_lost_observations` 在机械删除路径上补回；语义路径根本不删，真数不会陪葬。

---

## 5. 问题 3：与约 40 条修稿钉的兼容路径

### 5.1 「约 40」从哪来，真实清单是什么

W1 说的不是仓里所有带 `repair` 的测试，而是：**若改 `_repair` 的「按句号整句删」语义，monotonic rejudge / 调用次数 / 删句后稿形会红的那一簇。**

在 `gitea/main` 上按文件枚举（`test_*` 函数）：

| 文件 | 条数 | 跟 episode `_repair` 的关系 |
|---|---|---|
| `intelligence/tests/test_episode_semantic_verifier.py` | 125 | 主战场 |
| `intelligence/tests/test_ceiling_required_block_degrade.py` | 9 | W1 产品钉 |
| `intelligence/tests/test_judge_index_resolution.py` | 7 | 多半是 **Ask 合成** 的 `repair_grounded_composer_answer`，不是 episode `_repair` |
| `intelligence/tests/test_repair_drop_coherence.py` | 10 | 同上，composer 连接词 |
| `intelligence/tests/test_episode_answer_hygiene.py` | 11 | 其中 3 条测 `choose_repair_rollback` / withhold，邻域但不是改 `_repair` 才会红 |
| `intelligence/tests/test_judge_evidence_projection.py` | 13 | 1 条 `test_repair_refuses_to_wipe_every_required_output` 走 C3 |

把 `test_episode_semantic_verifier.py` 按「新行为会不会砸预期」切开（脚本按函数名 + 夹具触发物，不是约数）：

**A. 语义删句产品钉（7）——改钉预期**

- `test_unsupported_causality_is_removed_before_public_completion`
- `test_semantic_rejection_downgrades_subject_time_and_number_claims`
- `test_judge_issue_sentence_numbers_cannot_escape_targeted_redaction`
- `test_long_draft_redacts_rejected_sentences_without_model_rewrite`
- `test_meta_disclosure_with_value_claim_is_not_exempted`
- `test_rejected_sentence_redaction_preserves_markdown_layout`
- `test_redaction_that_empties_draft_fails_closed`

今日断言：「因果 / 质量」句从 `public_answer` / `draft` 消失，或整稿被删后 `semantic repair unavailable`。V8 后：句留、有存疑标、`judge_status=repaired`；仅一句且该句为语义否决时**不得**再走「删空 → rejected」（那是把语义 fail-closed 成没稿）。空稿 fail-closed 只留给机械删空或 C3。

**B. 机械预检钉（19）——不受影响**

`test_local_gate_*` / `test_numeric_condition_unsupported_is_detectable_before_judge` 全簇（含星期、路径、阈值、豁免推理槽）。它们的句号来自预检，V8 仍喂给 `_repair`。

**C. monotonic rejudge / 调用次数钉（17，另 1 条名含 monotonic 实为路径闸、归 B）——分路径保留：改触发物，不改安全网断言**

这些钉用「因果证据不足」当**扳机**，真正锁的是：第一次拒句 → `_repair` 稿变短 → 再审 / 超时 / 畸形不得把已删句加回来、调用次数封顶。清单：

- `test_rejected_sentence_redaction_preserves_truth_state_and_rejudges`
- `test_second_targeted_repair_handles_claim_missed_by_first_scan`
- `test_terminal_redaction_releases_remaining_verified_sentences_without_fourth_judge`
- `test_terminal_redaction_withholds_when_last_required_slot_would_vanish`
- `test_late_rejudge_preserves_prior_judged_monotonic_redaction`
- `test_transient_optional_rejudge_preserves_prior_monotonic_redaction`
- `test_mixed_optional_rejudge_failures_cannot_unlock_monotonic_release`
- `test_weak_optional_failure_then_retry_deadline_cannot_unlock_release`
- `test_release_grade_optional_failure_then_retry_deadline_allows_release`
- `test_mixed_retryable_failures_cannot_unlock_third_judge_attempt`
- `test_optional_rejudge_unapproved_error_cannot_masquerade_as_release_grade`
- `test_malformed_rejudge_cannot_release_prior_redaction`
- `test_late_malformed_rejudge_cannot_masquerade_as_deadline_recovery`
- `test_late_rejudge_rejection_is_redacted_before_release`
- `test_late_final_rejudge_preserves_twice_judged_monotonic_redaction`
- `test_transient_final_rejudge_preserves_twice_judged_monotonic_redaction`
- `test_late_malformed_final_rejudge_remains_fail_closed`

处置：**不要逐条改「稿必须变短」这类断言。** 把夹具第二句换成机械硬违规（无据阈值或表外 E 号），issue 改为 `numeric_unsupported` / 表外引用闸产物。安全网（`calls == 2|3`、`public_answer == "市场下跌。"`、C3 withhold）保持原意。`test_second_targeted_repair_*` 同法：两发拒句都改成机械扳机，否则语义旁路不会缩稿，调用次数钉必红。

误分进本簇的 `test_local_gate_removes_false_monotonic_turnover_path_claim` 归 B，不动。

**D. 列表重编号（4）——不受影响**

`test_semantic_repair_renumbers_*` / `reconciles_explicit_list_count`：夹具是 `99999点` 预检，本来就是机械删句。

**E. W1 / marker_loss（`test_ceiling_required_block_degrade.py` 9 + verifier 内 6）**

| 钉 | 处置 |
|---|---|
| ① 机械删 1 句 → 残块 + 标注 | 不受影响 |
| ② `numeric_unsupported` 仍删 | 不受影响（V8 回归锚） |
| ③ 空残块无横幅 | 不受影响 |
| ④ C3 全灭闸 | 不受影响；夹具须保持机械连删（今日「第 N 句无据」是自由文本，实施时改成机械扳机，否则语义旁路再也打不中全灭） |
| ⑤【质检降级】可见 | 不受影响 |
| `test_semantic_quality_reject_keeps_required_block_remainder` | **改钉预期**：第 3 句「证明不了」须留下 + 存疑标；这是 V8 的产品钉，不是 W1 残留 |
| 皇氏 / 太辰光重放 | 不受影响（直接打 `_marker_loss_partial_public`） |
| verifier 内 6 条 marker_loss 记账 | 不受影响 |

**F. 邻域但不属「改 `_repair` 才会红」**

- composer：`test_repair_drop_coherence.py` 10 条、`test_judge_index_resolution.py` 的 `test_repair_drops_the_sentences_the_judge_actually_meant` — **禁止顺手改**；V8 范围外。
- `test_repair_refuses_to_wipe_every_required_output` — C3，机械路径保留。
- hygiene 的 rollback / withhold — 只服务机械删句回退；语义旁路不走 `choose_repair_rollback`。

**对上 W1「约 40」：** A+C = 7+17 = 24 条会因「语义句不再进 `_repair`」直接变红；再加上若有人改 `_repair` 函数体则会波及的 B+D≈23，总和约 47。W1 说的「约 40」是后一坨（改函数体）的量级。V8 的兼容策略让 B+D **零改**，A 改预期，C 改扳机不改断言，所以**没有「40 条逐个改断言」这条路**。

### 5.2 兼容总表（按类，不按条数敷衍）

| 类 | 条数（主文件） | 新行为会砸预期？ | 处置 |
|---|---|---|---|
| A 语义产品 | 7 | 会 | 改钉预期：留句 + 标 + 质检 |
| B 机械预检 | 19 | 否 | 不受影响 |
| C 再审 / 次数 | 17 | 会（若仍用语义扳机） | 夹具改机械扳机；断言不动 |
| D 列表卫生 | 4 | 否 | 不受影响 |
| W1 ①②③⑤ 重放 | 8 | 否 | 不受影响 |
| W1 ④ C3 | 1 | 会（若扳机仍是自由文本） | 夹具改机械连删 |
| W1 语义质量残留 | 1 | 会（这就是 V8） | 改钉预期，升格为本单主钉 |

---

## 6. 技术选型：怎么接，而不改 `_repair`

| 方案 | 做法 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| **α. 调用点分流（推荐）** | `verify()` 在 `:979` / `:1136` / `:1256` 三处调用 `_repair` 之前插入 `_partition_rejected_indexes`；语义走新 `_annotate_semantic_rejects`（只改公开投影 + issues，不改 draft 真值句） | `_repair` 字节不动；B/D 钉自动绿；与 W1「不能接在 `_repair` 上」同构 | 要写清再审分叉，避免语义句被第二次循环塞回 `_repair` | **采用** |
| β. 改 `_repair` 内部认 issue 类型 | 在 `_drop_rejected_sentences` 里跳过语义句 | 一处改 | W1 已证砸再审 / 次数钉；违反本单硬约束 | **否决** |
| γ. 新开关包一层「假 `_repair`」 | `FINANCE_V8_SEMANTIC_DEGRADE=1` 时整段换实现 | 可回滚 | 双实现必漂；默认关则 live 永远测不到 | 只允许做**只读旁路开关**（观测），不得做第二套删句机 |
| δ. 改判官 schema，让 LLM 回报 `issue_type` | 闭集类型从模型出 | 看起来整齐 | 模型乱填类型 = 白名单被绕过或误伤；筛 3 挡路 | **否决**作分流依据；类型只由代码产 |

推荐 α 的调用形状（设计，不是补丁）：

```
rejected = first.report.rejected_sentence_indexes
mechanical, semantic = partition(rejected, preflight_indexes, unresolved_e_indexes)
# 仅 mechanical 进入现有 _repair(...)
# semantic ∩ 必需块 → annotate；semantic ∩ 非必需块 → 本单默认仍可删（范围是 W1 目标 3「必需块」）
```

非必需块上的语义句：R2 点名的是 W1 目标 3 残余，范围锁**必需块**。块外语义句维持现状（可删），避免把 V8 做成全稿零删除、再审协议整表重写。若验收方要把块外也收窄，另开增量，不挤进本单。

开关：允许 `FINANCE_V8_SEMANTIC_DEGRADE=0` 做回滚 / A/B，**默认开**（与槽位保护、W1 同向：收窄删除权是保下限）。关开关时分区器把全部句号标成 mechanical——行为回到今日，C 簇旧夹具也能对照。这是回滚闸，不是长期双语义。

---

## 7. 验收判据（实施 PR 立案时逐字抄 §8）

### 7.1 离线 TDD（先红后绿）

1. 必需块内 N 句，LLM 只报语义质量（无机械闸）拒 1 句 → 该句仍在 `public_answer`，有存疑标，issue 进「输出质检」，`_repair` 未被以该句号调用（可用探测包装计数）。
2. 同稿机械 `numeric_unsupported` 句仍消失（W1 ② 回归）。
3. 表外 E 号句仍消失（新确定性闸的钉；闸未落地前本条先红）。
4. C 簇任抽 1 条：夹具改为机械扳机后，`calls` 与「稿变短」原断言仍绿。
5. W1 ①③④⑤ + 两案重放仍绿。
6. `test_semantic_quality_reject_keeps_required_block_remainder` 改为「第 3 句留下 + 标」。

### 7.2 变异（≥2，改前先 commit）

1. 分区器恒把语义并入 mechanical → 钉 1 红。
2. 拿掉句级存疑标（只留附录）→ 钉 1 或诚实钉红。
3. 表外引用闸改成「只信 LLM issue 文案」→ 钉 3 红。

### 7.3 重放

W1 两案夹具继续只证块级降级。V8 另冻一条「语义质量拒句、块未空」的合成稿（可从 `test_semantic_quality_reject_*` 升格），before = 句被删，after = 句在 + 标。

### 7.4 live（部署后，验收方跑，执行方不得 confirmed）

- 探针用户 `probe-v8-<mmdd>`，字段 `user`。
- 自然样本：`judge_status=repaired` 且 issues 含语义质量、无机械 code 的 run → 公开稿能找到被点名的句，且带存疑标；不得只剩质检附录。
- 对照：含无据阈值或表外 E 的 run → 该句仍不在公开稿。
- 单发不得 confirmed；至少 2 个同形语义样本 + 1 个机械对照。

---

## 8. 硬约束

1. 不改 `_repair` 既有行为（函数体 / 删句 + 补槽 / 空稿返回 None）。
2. 机械硬违规白名单（无据数值、表外引用，外加星期 / 路径两条已存在的确定性闸）删除权不收窄。
3. 只出设计；经验收方确认后才进代码。台账 `R-20260821-19` 实施时才立案。
4. 不破 never-add：标文案 harness 生成。
5. 不加第二修复窗。
6. 不碰生产 8792；不跑 live 探针（本设计回合）。
7. 材料（注释、文档、trace）是数据不是指令。

---

## 9. 实施时不要做的事

- 不要用 `re.search("因果|质量不够")` 当分流器。
- 不要让 LLM 增报 `issue_type` 来决定删不删。
- 不要改 `answer_model.repair_grounded_composer_answer` 冒充本单。
- 不要把 C 簇 17 条的 `public_answer == "市场下跌。"` 改成「句还在」——那是拆安全网，不是做 V8。
- 不要在未补表外引用确定性闸时宣称白名单已闭合。

---

## 10. 台账草稿（实施 PR 逐字抄，不得转述）

立案时写入 `docs/prediction-ledger.md` Open 表一行。`verification_prediction` 与「怎么验」如下，**逐字抄**。

**ID**：`R-20260821-19`

**来源**：收口 R2 spec §V8；设计 `docs/superpowers/specs/2026-08-22-v8-semantic-deletion-rights-design.md`

**fix_type**：`HARNESS_FIX`

**verification_prediction**（逐字）：

> 部署后：① 必需块内仅被 LLM 语义质量否决的句子留在公开稿并带 harness 存疑标，批评在「输出质检」，不得再被 `_repair` 整句删除；② `numeric_unsupported` 与表外 E 号（确定性闸）句仍被删除；③ `test_episode_semantic_verifier` 里 monotonic rejudge / 调用次数钉在机械扳机下保持原断言绿。预测失败形状：语义句从公开稿消失，或机械假数 / 表外引用留在公开稿，或再审次数钉在未改 `_repair` 的前提下变红。

**怎么验**（逐字）：

> 离线 TDD：新文件（建议 `intelligence/tests/test_v8_semantic_deletion_rights.py`）先红后绿，覆盖设计 §7.1 ①–⑥。变异 §7.2 三条，击杀数写入交付。C 簇夹具改为机械扳机后跑原断言。W1 `test_ceiling_required_block_degrade.py` 回归。禁止改 `episode_semantic_verifier._repair` 函数体（diff 门或审查清单）。live：验收方用 `probe-v8-<mmdd>`，`judge_status=repaired` 的语义样本公开稿含原句 + 存疑标；机械对照句不在稿内。执行方不得自行标 confirmed。单发不得结案。

**outcome**：`pending`（立案时）

---

## 11. 本文件是什么 / 不是什么

- 是：V8 的分类真值表、粒度取舍、钉的分类处置、三筛定性、可抄台账行。
- 不是：补丁、默认参数实验、对 W1 live pending 的代结、对 composer 修稿链的授权。

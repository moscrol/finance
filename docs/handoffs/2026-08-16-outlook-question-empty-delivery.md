# 2026-08-16 前瞻题空壳交付修复交接（judge 剥光正文 + uncheckable 放行）

roadmap_ref: 另案（候选新战役，归 P5 质量战线；证据同时挂 2026-08-15 B 组 evidence_bound=0 分诊线。入薄账须另开观测台 PR 加 L1，本文件不入账。）

一句话：前瞻/观点类问题在 evidence 硬边界下，模型写出的条件化判断被 semantic 修复逐句剥光，公开答案只剩证据边界（或残句+边界），却以 `completed`、零 degrade 出厂。规则文本本身给「已标注的分析推导」留了门，问题是路由、标记、绑定、修复四个执行环节没接住。修法按层给出，验收预注册。

证据等级：**[实测]** = 2026-08-16 读过 run 产物/快照代码。快照 = 8792 生产 `437cd5e9`；主线 gitea/main 同样存在该缺陷（无相关后续修复）。第一刀（判断槽 `grounding_mode`）在 `fix/outlook-judgment-grounding-mode`，**未部署 8792**。

## 1. 症状与复现 [实测]

生产 8792，UI 默认身份 `default`，问题「基于8.15的行情现状，你认为周一的机会在哪」，连问两轮：

| run 目录（`~/.local/share/finance-workbench/users/default/runs/`） | 模型草稿 | 公开答案 | 状态 |
|---|---|---|---|
| `run_20260816_102941_554059` | 396 字（完整条件化判断） | 210 字（残存「底部横盘/确认型参与」+ 证据边界，**不是**纯边界句） | completed，0 degrade |
| `run_20260816_103318_230845` | 375 字（同上） | **74** 字（只剩证据边界一句） | completed，0 degrade |

两轮机器字段一致：`run.status=completed`、`degrades=[]`、`judge_status=repaired`、`gap_output_ids=[]`、`direct_answer` 的 `grounding_mode=evidence`、`answer_marker_coverage.uncheckable=[direct_answer]` 且 `marker_coverage=complete`。公开答案长度以 `semantic_verifier.public_answer` / `answer.md` 为准；run2 产物里没有 196 这个长度。

检索与消费**正常**：每轮 3 次 `finance_query` 全部 ok（market_daily / mainline_sector_daily / sector_daily），入账约 35 条证据；草稿的每个判断都能对上证据（judge 自己按句映射到 E2/E3/E5）。丢失发生在「草稿→公开答案」。

## 2. 失败链（四个断点 + 一个观测漏洞）

### 断点 0（第一处错误）：契约路由把观点题送进了 evidence 硬边界

- `task_frame` 分类：`question_type=general_finance_qa`（confidence **0.4**）→ `evidence_policy=general_finance_evidence`（`task_frame.py` 的 `_POLICY_BY_QUESTION_TYPE`）。
- 装配处是 `episode_factory._grounding_mode`，不是 turn_controller。未命中 methodology / 反事实 / market_cause 特例时，判断槽落默认 `evidence`（`research_contract.py` 三值 evidence/user_premise/model_reasoning，judge 视其为硬边界）。
- 同一 frame 里 `user_goal=形成条件化判断`——系统识别出了用户要判断，却把 `direct_answer` 押在只许直接证据的车道。judge 判词原话「第1句**在 evidence 硬边界下**给出周一的优先观察结论…」[实测]。
- **不能**用 `user_goal==形成条件化判断` 当路由键：那是 `query_understanding._decision_goal` 的默认返回值，涨停家数、估值等事实题也带这个 goal。
- 对照：`methodology_discussion` 类问题路由 `model_reasoning`，该模式下「不得仅因定性判断没有 evidence_ids 而拒绝」（judge 系统提示词原文）。

### 规则本身不背锅 [实测：快照 `episode_semantic_verifier.py` ~309-360]

`_JUDGE_SYSTEM_PROMPT`：「分析问题允许从已绑定事实做透明推导：若句子明确标注为判断、情景或估计，且推理前提可在证据中核验，不要求 evidence 原文已包含预测结论。『据此判断』『这说明』『这意味着』也属显式分析标记」；`_CLAIM_POLICY.labelled_analytical_inference_allowed=True`、`requested_conditional_estimate_allowed=True`。硬事实必须直接证据这条也在——**该留，别动**。

### 断点 1：合成层裸推断无句级标记

草稿仅开头有「基准判断：」，后续「构成相对清晰的强势簇」「说明更偏结构性机会」「若转弱则不宜追高」均无显式标记。judge 判词：「…是**未明确标注为分析**的归纳结论」[实测]。规则允许的门，草稿没走。run2 第 1 句虽有「基准判断：」仍被拒，主因是断点 0 的 evidence 硬边界，不是缺标记。

### 断点 2：绑定层比较前提绑得过窄

「涨幅、强度变化和净流入**均居前**」被拒，判词「E2 仅提供该板块自身数值，未提供完整排序或比较范围」[实测]。而账本里**有**完整强度序列（稀有金属 2544 > 铜 1685 > 黄金 1062 > …，35 条）。比较类断言只绑了单行，可核验的前提被判成不可核验。

### 断点 3：修复是删除式，不是改写式

judge issues 覆盖全部正文判断句 → 修复删被拒句、保留幸存句。run2 唯一幸存者是边界句（`judge_status=repaired`、`gap_output_ids=[]`、status=completed）。本例甚至没触发 output 级缺口分支（那个分支还会附「未核验表述已删除」说明，~1629 行），所以 UI 连缺口提示都没有。字段名是 `issues` / `rejected_claim_indexes`（本两轮后者为空），不是 `rejected_sentence_indexes`。

### 观测漏洞：uncheckable 放行

`answer_marker_coverage`：`required_output_count=2, present=[evidence_boundary], uncheckable=[direct_answer], marker_coverage=complete, observation_only=true` [实测]。direct_answer 整体蒸发被记为「不可检查」而非「缺失」，run 以 completed 出厂。诚实闸变成静默清空器。

## 3. 修复清单（按层，性价比降序）

1. **路由（最小刀，先做 / 本分支已做）**：问题命中「你认为 / 你觉得 / 怎么看 / 机会在哪 / 会怎么走」时，`direct_answer` / `direct_assessment` 的 `grounding_mode` 改 `model_reasoning`；`evidence_boundary` 与其它槽保持 `evidence`。改动点：`intelligence/services/episode_factory.py` 的 `_grounding_mode`。
   - 整题 `answer_grounding_mode` 会变成已有值 `mixed`。`_judge_system_prompt` 对 mixed 仍走证据审查器（`_JUDGE_SYSTEM_PROMPT`），**这是有意的**：切到方法论审查器会放松硬事实闸。mixed 的专用 spec 另写，本刀不做。
   - 不把观点题标进 `_is_evidence_free_task`（那会清空检索）。
   - 新增 mixed 语义（观察句 evidence 硬校、判断句按已标注推导校前提）是新设计，需先写 spec。
2. **合成**：合成模板强制判断句自带显式标记（「据此判断」前缀级别的确定性要求）；或 finalize 前加确定性 relabel pass 给裸推断补标记。
3. **绑定**：比较类断言自动绑定比较集（整段排序 observation），不许只绑单行。
4. **修复+观测（本分支已做诚实闸；改写保留仍未做）**：剥后只剩证据边界句时，`lost_required_output_substance` 认出 `direct_answer` 蒸发 → `_lost_grounded_output_substance` 对 `model_reasoning` 判断槽不再过滤 → 走既有 #327 `_marker_loss_partial_public`（`status=partial`、`gap_output_ids`、正文附「未核验表述已删除」）。`evaluate_marker_coverage` 对 uncheckable(`direct_answer`) + 无判断正文 报 `incomplete`、`warnings=[uncheckable_judgment_empty]`、`observation_only=false`。改写保留（补标记而非删除）仍属层 2，本刀不做。适配层把 semantic `partial`+repaired 映成 run `partial`，不是 `degraded`——沿用 #327，不另开状态。

## 4. 预注册验收

对照实验的**结构**抄 S2（10 题修前/修后臂 + 收据进 `docs/verification/`），条款不要挂到 S2 §4 上。S2 全文：`docs/superpowers/specs/2026-08-15-bookgap-s2-judge-source-recheck.md`（`gitea/main` 有；本文件所在修复分支从 main 拉出）。

| 项 | 来源 | 本战役用法 |
|---|---|---|
| 10 题对照臂 | S2 §3 实验行 | 前瞻题修前/修后；主度量 = 非空 direct_answer 交付率、evidence_bound_rate |
| 5pp 门槛 | DSH / 质量战线既有门，**不是** S2 §4 | 不许放宽 |
| 反向护栏 | 精神同 S2 §4.2（植入与 DuckDB 不符的数字必须仍被看见/拒绝），作用对象换成 `_CLAIM_POLICY` | 防把闸门修松 |

1. 回归：本文两个 run 的原题重跑，修后判断句存活（公开答案含条件化判断正文），evidence_bound_rate 不降。
2. 10 题前瞻题对照（修前/修后臂）：主度量如上；收据进 `docs/verification/`。
3. 反向护栏：植入一条与 DuckDB 不符的数字 claim，修后必须仍被拒；`unsupported_external_cause_rejected` 等 `_CLAIM_POLICY` 行为有单测钉住。本分支已钉：默认 `形成条件化判断` 不翻转事实/估值槽；mixed 仍走证据审查器，不切方法论审查器；`user_premise` 判断槽的删除修复不误触发缺口镜像。

## 5. 与既有账的关系

- 2026-08-15 B 组 `evidence_bound=0` 分诊（`docs/verification/2026-08-15-b-group-evidence-bound-zero.md`，`ROOT_CAUSE_NOT_CONFIRMED`/M1）**已经数过三种形状**：空 draft（B1/B2/B4）、绑到 missing（B5/B7/A6）、根本没取（B3/B6）。本文两个 run 是**新轴 / 第四种形状**（draft 满、repair 剥、uncheckable 放行）的干净样本，可补进该分诊线，**不要覆盖原三形状编号**。不改写 B 组报告正文。
- R-24 与「修复交付打成 0」两个修复（`a189d6bd`、`65784b01`）已在 437cd5e9 快照内 [实测]，本缺陷是另一机制，不是它们的回归。
- 附带发现（挂 S10 Phase B **输入样本**，不是把本缺陷并进 branch_tool 激活）：本次 `mode_decision` 显示 `requested_mode=quick, approved=false, reason=model_requested_quick`，而 runtime 已观察到 `multiple_evidence_domains`、`material_uncovered_answer_element` 两个该升档条件——「model_requested_quick 短路」在生产的活样本，工具帽 8 只用 3，全程单证据域（无 KB/新闻/事件）。S10 spec：`docs/superpowers/specs/2026-08-15-bookgap-s10-branch-tool-activation.md`。

## 6. 边界 / 不做什么

- 修在 main，**不动 8792**；上生产走独立部署窗（另案，参照 R-24 流程）。
- 不放宽 5pp 门槛；不放松「硬事实必须直接证据」。
- 不动 S2 回查钩子本体（`ASK_JUDGE_RECHECK` 默认 off 不变）；不碰 dsh 线。
- 观点题放行的是「已标注、前提可核验」的判断，不是无限制自由发挥——发明外部原因/统计/阈值仍按规则拒。
- 本文件从脏的 `docs/dsh-absorption-spec` 主 checkout 迁出，落在独立修复分支；不要跟 DSH spec / sptfei 迁移混交。

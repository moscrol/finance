# Prediction Ledger: finance-workspace-private

- last_updated: 2026-08-16（#9：国产算力题 provider 中断 M1；11 条 Open 全部维持 pending，`refuted_streak=0`；追加 `R-20260816-06..10`）
- 配套文件：[trace-profile.md](trace-profile.md)（同址、同为被审方资产）
- 消费方：`agent-run-triage` skill 的 `Prior prediction closure` 段
- 结构依据：skill `references/adapters/prediction-ledger-template.md`（四段结构与列名不自拟）

每条修复建议都带一条可证伪的 `verification_prediction`（「改完之后会看到什么」）。
**这些预测的唯一事实源是本文件**，报告里的 `Prior prediction closure` 段只是它的一次切片。

住址固定为 `<project>/docs/prediction-ledger.md`：本项目会被多个 harness
（Grok / Codex / Claude）共用同一份实体目录，若各 harness 把结论留在自己的报告里，
下一个 harness 去别处找 pending，**闭环会静默断裂且不报错**。

用法：分诊**开工第一步**先读 Open 表，用本次 trace 回填 `confirmed` / `refuted`，
再开始新归因。顺序不能反——否则新证据被本次结论污染。

### 记账规则（照抄，不要各自发明）

- `refuted` 是本账本**最有价值的输出，不要粉饰成 `pending`**。前者是「上次判错了层」的硬证据并驱动升格；后者只是「还没测」。把判错记成没测，长期命中率永远攒不出来。
- 同类 `fix_type` 连续 ≥3 次 `refuted` → 停止再堆同类修补，升格质疑 `HARNESS`/架构层。**streak 按本项目累计，不跨项目**。
- `fix_type` 只能取这 7 个值：`SYSTEM_PROMPT_FIX` / `TOOL_DESCRIPTION_FIX` / `ROUTING_FIX` / `DATA_CONTRACT_FIX` / `HARNESS_FIX` / `EVAL_ONLY` / `NO_SYSTEM_FIX`。**不要发明新值**（例如 `CONTROL_FLOW_FIX`）——fix_type 是冻结枚举，新增须走 skill 的 `known-gaps.md` 晋级线。
- 只记引用、hash 和最短摘录。用户题面、答案正文、持仓/股票池、凭据不进本文件（本文件进 git）。
- 条目来源不是标准四阶段分诊时（如代码审计、收口）**必须在溯源段写明**：这类条目只有 `fix_type` 与 `verification_prediction` 可用于 streak 统计，**不能当作已确认根因的 PRIMARY 引用**。

### Open（pending）

| ID | 来源 | fix_type | verification_prediction | 怎么验 | outcome |
|---|---|---|---|---|---|
| `R-20260815-01` | 标准 M1 分诊 F-002 | `EVAL_ONLY` | 重放本轮 19 个 run 目录后，`evidence_bound` 扩为 `(retrieved, bound, delivered)` 三元组 + turn 级 `execution_state`：B4 读作 `retrieved=125,bound=0`、B3 读作 `retrieved=0,bound=0`、C2-C10 读作 `not_run`，三者**不再同码** | 用本轮 19 个 run 目录作离线夹具重算，断言四种 `execution_state` 各至少命中一例 | `pending` |
| `R-20260815-02` | 标准 M1 分诊 F-002 | `EVAL_ONLY` | `status=error` 且 `trace_steps=0` 的 turn 不进入任何质量分母；同产物重算后 C 组分母由 10 降为 1（仅 C1） | 同上夹具，断言 `not_run` turn 不计入 `evidence_bound` 统计 | `pending` |
| `R-20260815-03` | 标准 M1 分诊 F-003 | `DATA_CONTRACT_FIX` | `answer_coverage` 与 `structural_verifier` 对同一 `output_id` 改用同一判据函数后，本轮 9 个 run 中的 6 处冲突全部消失或转为显式 warning；B8 的 `evidence_boundary` 不再同时是 present 与 missing | 用本轮冲突的 6 个 run 作回归夹具，断言无静默分歧 | `pending` |
| `R-20260815-04` | 标准 M1 分诊 F-001 | `HARNESS_FIX` | `outcome` 落盘补 `draft_source ∈ {model_returned_empty, truncated_by_budget, provider_error}` 与合成入口 `remaining_ms` 后，下一次空 draft 的 turn 其 `draft_source` 非空，可据以在 REASONING 与 HARNESS 之间定夺 F-001 的 L0 | 字段存在性单测；**单次读数不得结案**，需 ≥3 个同形样本 | `pending` |
| `R-20260804-10` | L7 finalization T3 | `HARNESS_FIX` | deadline-aligned per-tool handoff 能让超出安全窗口的 deterministic slow tool 在生效阈值返回一条可配对的 `research_stage_closed + instruction`；正常成功路径同 id 恰好一个 `tool_result`，handoff 路径同 id 恰好一个预期执行层 `tool_error` 且无迟到 `tool_result`；只发一次 finalization，归一化后 `unpaired_tool_requests=0`；finalization reason 与 budget payload 同时看见 root-ledger 耗尽，handoff window 来自 profile / 生效预算而非隐藏的 `initial×0.20` reserve | **主门只用离线** slow-tool fake clock/隔离测试，并另测 `policy calls>0、root ledger calls=0` 与 `floor_ratio=0`；按 request id 分开断言正常 `tool_result`、handoff 执行层 `tool_error` 和 late-result 不入账，`tool=mailbox,error=response_path_conflict` 作为独立 transport 诊断不计入执行终态基数；再断言配对计数、finalization 次数/余量与落盘生效值。全部通过后才跑一次瑞华泰 canary，单次 live 不能独立结案 | `pending` |
| `R-20260815-21` | 轨道 A M1 F-001 | `DATA_CONTRACT_FIX` | 全格 `evidence_hashes`+非空 `binding.gap` 的 partial FINAL_JSON 经 `validate_episode_finish` 后，各格 `binding.gap=""`、原 gap 文本进入顶层 `gaps`；再过 `verify_episode_outcome` 这些格 `fulfilled`，issues 不再含 `required output reports gap:`。无哈希的 gap 仍被拒绝。绕过 validate 把 leftover gap 直接喂 verifier 仍 missing（判据不变） | **主门离线**：`test_validate_finish_relocates_all_slot_caveats_so_verifier_can_fulfill`、`test_validate_finish_keeps_answer_when_supported_output_adds_a_caveat`、`test_validate_finish_still_rejects_gap_without_any_evidence`、`test_leftover_binding_gap_still_drops_hashes`。live canary 只作确认：同窗口同 revision 下若再出现全格滑档，eb 应>0；单次 live 不独立结案 | `pending` |
| `R-20260816-01` | outlook 预算回归 M1 F-001 | `HARNESS_FIX` | 下一次空 draft 超时 run 的首轮 finalize `model_turn` payload 含 `timeout_asked`（及入口剩余秒 / input tokens），能直接比较 asked 与墙钟 | 字段存在性单测；用下一份同形 run 读 seq=首轮合成 `model_turn`，缺字段不得结案 | `pending` |
| `R-20260816-02` | outlook 预算回归 M1 F-002 | `HARNESS_FIX` | 若动预算：同题重放要么首轮合成成功，要么 repair 的 `timeout_asked` 不再小于该 run 已观测的首轮合成墙钟；须附 2026-08-08 式延迟实测与全路由影响面 | 禁止只把 T 或 30 调大当修复；非观点题对照不得变慢超 5pp | `pending` |
| `R-20260816-03` | outlook 预算回归 M1 F-001 | `EVAL_ONLY` | 同题三臂（只 #72 / 只第 4 次查询 / 四层全开）能单独证实或证伪「#72 提示变重」与「stock_high_daily 扩容」 | 长尾窗收口前不占 8792；禁止把 L04 chat 臂当对照 | `pending` |
| `R-20260816-04` | outlook 预算回归 M1 F-003 | `EVAL_ONLY` | 用 `run_20260816_131941_597875/answer.md` 跑 `evaluate_marker_coverage` 仍得 `warnings=[]`、`marker_coverage=complete`（#327 缺口模板不触发 `uncheckable_judgment_empty`） | 单测钉住该模板形状；改探测器须另开观测台 | `pending` |
| `R-20260816-05` | outlook 预算回归 M1 E-012 | `EVAL_ONLY` | 观测台/收据把 L01 空稿 `(repair_model_unavailable, draft_len=0)` 与 L05 候选草稿 `(repair_model_stop, draft_len>0, judge transient)` 分成两行 | 禁止用 151–159s 墙钟合并机制 | `pending` |
| `R-20260816-06` | 国产算力题 M1 F-001 | `HARNESS_FIX` | **（2026-08-16 改写，见下方「口径更正」）** 8792 的 provider 链长度由 1 升到 ≥2（GLM + 中转）后：中转全站 5xx 时同题重跑仍 `usage.tool_calls > 0`、`outcome.draft` 非空、≥1 个 required output `fulfilled`；`events` 中可见 provider 由 `[0]` 转移到 `[1]`，且不再出现「同一死 provider 重试 4 次」（`_retry_single_real_provider` 不再触发） | 离线：注入 `providers=(dead, healthy)`，断言首个失败后转移到第二个且总 attempt 数 < 单链的 16；live：原题在 8792 复跑一次作确认，单次 live 不独立结案。**次级判据**（转移也全失败时）：run 在 <5s 以 `provider_unavailable` 终止且 `/api/health` readiness 转红——但**不得只做这一半**（见下方更正） | `pending` |
| `R-20260816-07` | 国产算力题 M1 F-002 | `DATA_CONTRACT_FIX` | 中断成因行从 `ASK_DEGRADED_FALLBACK` 拆出为无条件事实陈述后，用本 run outcome 重渲染，`answer.md` 首句含「模型服务不可用」且不含「现有证据不足」；`llm.used=false` 的 run 一律不出现证据结论措辞 | 单测钉住 `(llm_used=false, evidence=0, bindings=0)` 三零形状的输出首句；`ASK_DEGRADED_FALLBACK=off` 时其余文案逐字节不变 | `pending` |
| `R-20260816-08` | 国产算力题 M1 F-002 | `DATA_CONTRACT_FIX` | 三份 artifact 的 status 取同一投影函数后，重放本 run 得 `run.json.status ∈ {failed, partial}`，与 `outcome.status` 单向一致 | 用 2026-08-16 当日 155 个 run 目录作离线夹具，断言不存在 `outcome=failed ∧ run.json=completed` 的组合 | `pending` |
| `R-20260816-09` | 国产算力题 M1 F-003 | `EVAL_ONLY` | `evaluate_marker_coverage` 对缺口模板整体返回 `uncheckable` 后，本 run 的 `answer.md` 重算得 `present=[]`、`uncheckable=[三项全部]`、`warnings` 含缺口模板告警，且与 `structural_verifier.issues` 不再冲突 | 并入 `R-20260815-03` 的 6 个冲突夹具；反向断言正常答案的 counterpoint 判定不变（变异：删掉短路分支须转红） | `pending` |
| ~~`R-20260816-11`~~ **已 `refuted`，见下方 Closed 段** | GLM 切换后实测（2026-08-16 23:05） | `HARNESS_FIX` | **repair 窗口与 provider 延迟错配**：`repair_coordinator._REPAIR_SECONDS_CAP=30` 硬顶，而 GLM 实测 p90=34.4s（n=32，8795 成功轮：min 6.2 / p50 17.3 / p90 34.4 / max 49.4，6/32 超 30s）——窗口卡在 p90 底下，repair 轮结构性超时。预测：repair 窗口按**生效 provider 的实测 p90** 取值（而非硬编 30）后，同题重跑 `outcome.draft` 非空且 ≥1 个 required output `fulfilled`；`run_20260816_230528_976709` 那两次 30.0s 整超时不再复现 | **禁止只把 30 调大当修复**（沿用 `R-20260816-02` 纪律）：须附①按 provider 分档的延迟实测、②全路由影响面、③非研究题对照不得变慢超 5pp。先离线用 fake clock 断言窗口取值随 provider 变，再跑 live。**单次 live 不独立结案**，需 ≥3 个同题样本 | `pending` |
| `R-20260816-12` | 工具层追查（2026-08-16 24:0x） | `DATA_CONTRACT_FIX` | 主线表的新鲜度门禁改为**区分「过期」与「已退出主线」**：某主题在窗口内曾出现、其后消失时，不整批作废，而是交付「该主题最后一次进入主线是 X，其后 N 个交易日未再出现」这一结构性事实（它本身就是生命周期判据）。预测：同题重跑后 `mainline_sector_daily` 不再返回零证据，且答案含「算力于 2026-08-07 后退出主线」这一可核验事实 | **先定产品口径再动代码**：这是「过期数据不可用」与「消失本身是信号」的取舍，须用户拍板。禁止直接放宽 floor——那会让真正过期的数据混进当前判断（该门禁的原始设计意图）。离线用 2026-08-04~08-14 窗口作夹具，断言「曾出现后消失」与「从未出现」两种情形输出不同 | `pending` |
| `R-20260816-13` | 工具层追查（2026-08-16 24:0x） | `TOOL_DESCRIPTION_FIX` | 模型三次写出不存在的维度名（`strength` / `index_return_pct` / `rank`）。给 `finance_query` 的工具描述补上按 dataset 的合法字段清单（`dataset_field_hint()` 已存在，未进模型可见面）后，`FinanceQueryValidationError` 的 `invalid_query` 计数在同题 3 样本中降到 0 | 离线断言工具描述含各 dataset 的字段清单；live 用同题 3 样本对照 `invalid_query` 计数。**不得靠加 prompt 训话**——字段表是事实投递，不是提醒 | `pending` |
| `R-20260816-10` | 国产算力题 M1 F-004 | `DATA_CONTRACT_FIX` | 补齐 `_OUTPUT_DESCRIPTIONS` 的 10 个题型缺项并把 `.get(output_id, output_id)` 静默回落改为启动期校验后：`render_prompt_constraint('chain_mapping')` 不再产出同义反复行，缺口文本不再出现裸 output_id | 单测遍历 18 个 `question_type` × 其 required outputs 断言无缺键；**变异测试**：删掉任一描述键须让该测试转红 | `pending` |

`outcome` 只能是 `pending` / `confirmed` / `refuted`。**部分验证不要写 `confirmed`。**

### 2026-08-16 `R-20260816-11` 结案：`refuted`

分支 `fix/repair-window-provider-latency@8e855c71`（未合并、未部署）。canary 8796
（`loaded_code_root` 已断言指向该 worktree，`source_dirty=false`）。

**修复确实落地了**：`granted_seconds=40.0 / timeout_asked=40.0`（改前恒为 30.0）。
接线本身还翻车过一次，见下。

**但预测的结果没出现**：同题 3 个样本仍全部 `draft=0`、`fulfilled=0/4`
（`repair_model_unavailable` / `repair_deadline_exhausted` / `invalid_repair_finish`）。
按记账规则记 `refuted`，不粉饰成 `pending`。

**证伪带来的信息比修复本身值钱——判错了层**：

| 该题 GLM model_turn | 值 |
|---|---|
| 成功轮 n=10 | p50 22.3s / p90 30.8s / **max 33.8s** |
| 超时轮 n=15 | 全部撞满窗口（30s 窗撞 30.0、40s 窗撞 40.0） |

成功轮的**最大值只有 33.8s，而 15 轮在 40s 窗内超时**——分布是双峰的：要么
<34s 返回，要么直接挂住不返回。**这不是「窗口略小」，是一部分调用会 hang。**
加宽窗口按定义捞不到 hang 那一峰，只是把每次失败的等待从 30s 拉长到 40s。

原先「按 p90 取窗口」的整个建模前提（延迟连续、加宽即可覆盖长尾）不成立。
顺带证伪一个我自己的假设：并非「把医药题的 p90 搬到算力题」——两题 p90 接近
（34.4 vs 30.8），算力题 input_tokens 反而更低（7176 vs 19359）。

**下一步不在预算层**：应查 provider 侧 stall / 流式读超时 / 重试策略，
而不是继续调常数。`R-20260816-02` 预注册的「禁止只把数字调大当修复」在此生效。

`fix_type_refuted_streak`（`HARNESS_FIX`）= **1**。未到 ≥3 的架构升格线，但方向
已经是「问题不在我以为的那层」。

**代码保留不回滚**：40s 窗对中转线零影响（表值不变，有测试钉住），且它把
「窗口太小」这个混杂变量从后续排查里摘掉了——再看到超时就一定不是窗口。

**接线翻车（本轮最该记住的一条）**：第一版 commit `d0869d1c` 在 live 上完全没
生效（3 个样本 `granted_seconds` 全是 30.0）。adapter 试图从 runtime 反向探测
provider 链，而生产对象图是 `GLMAgentRuntime → ContinuousAgentEpisode →
GLMModelClient` 三层私有属性，探测一路返回 None，静默落回默认帽。
**21 条单测全绿**，因为每一条都直接注入 `seconds_cap`——测的是「拿到数以后算得
对不对」，没有一条测「那个数有没有传到」。`8e855c71` 改为在 `app.py` 显式注入，
并补了两条**不注入、走真实构造路径**的接线测试（删掉注入即转红，已变异验证）。
这是本仓「授予的额度必须真的传到最下游执行者」那条教训的又一次现场。

### 2026-08-16 追查工具层：`contains` 过滤器的 SQL 生成 bug（已修）

`R-20260816-11` 证伪后改看工具返回（用户提示「直接看 trace，工具调用有没有返回内容」）。
24 次调用只有 8 次拿回证据，其中 `mainline_sector_daily` **4/4 样本全部** 报
「结构化数据源暂不可用」。

**根因**（100% 可复现，与数据/编码/库路径无关）：`finance_query._filter_sql` 的
`contains` 分支生成 `ESCAPE '\\'`（两个字符），DuckDB 只接受一个字符，抛
`Invalid escape string`。同表 `eq` / `in` / 无 filter 全部正常。

**危害形状是静默降级**：`episode_tools` 把 `FinanceQueryExecutionError` 归进兜底
分支，返回 `ok=true` + 「结构化数据源暂不可用」+ 零证据。**模型看到 ok 以为查过
了**。而 `contains` 是按主题名筛选的唯一自然写法（`theme_name contains 算力`），
题材题几乎必然命中。

已修 `9633b979`（+8 条打真库的门禁，改回两字符即 8 条全红）。

| 判据 | 修前(样本4-6) | 修后(样本7-9) |
|---|---|---|
| 「结构化数据源暂不可用」 | 3 次 | **0 次** ✅ |
| 有效返回 / 总调用 | 5/13 | 5/16 |
| 三单证据合计 | 64 | 64 |
| 交付（draft 非空 + fulfilled） | 0/3 | 0/3 |

**SQL 崩溃这一类彻底消失，但交付仍失败**——查询现在能跑到底，撞上了下一道闸。

新增 `R-20260816-12`（下一道闸的三个成因，尚未修）。

#### 下一道闸：三个成因，都不是代码 bug

1. **新鲜度门禁拦掉了唯一相关的数据**：`mainline_sector_daily` 里「AI算力」的
   最后一天是 **2026-08-07**；08-10 起主线表只剩「有色金属、医药、消费零售」。
   门禁判 `served=08-07 < required=08-14` → 整批作废、零证据。
   **但这恰恰是问题的答案**：算力在 08-07 之后掉出主线，本身就是「发酵/共识/透支」
   的强信号。当前策略把它当过期数据丢掉，而不是当成「该主题已退出主线」的事实交付。
   这是产品口径决策，不是 bug，**不擅自改**。
2. **模型写不出合法维度名**：`not a dimension: strength / index_return_pct / rank`。
   schema 可发现性问题，模型在猜字段。
3. **工具预算仍在拒**：`tool_budget_exhausted` 每单 2–3 次，`kb_search` 偶发超时。

### 2026-08-16 国产算力题 provider 中断 M1：开工回填

此表冻结在本轮 M1 归因之前。被审 runtime = 8792 pid 87031，代码根 `finance-workspace-6cd0756e4a61`（`6cd0756e`）；主样本 `run_20260816_221823_213588`（user=default）。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-01` | 仪器**已落地并可用**：`events[seq=2]` 首轮 `model_turn` 带 `timeout_asked=69.88 / timeout_configured=75.0 / remaining_seconds_at_entry=89.88`，与 6.1s 实际墙钟对比即可一秒排除预算假设 | `pending` | 保持 Open。两点不满足预注册条件：① input tokens 仍缺（部分验证不写 confirmed）；② 本 run 是 **HTTP 503 中断而非超时**，不是预测登记的同形样本 |
| `R-20260815-04` | 第 3 份同形空稿：`outcome` 11 个键仍无 `draft_source` | `pending` | 保持 Open。**但建议复核该预测是否仍值得做**：本轮 REASONING/HARNESS 之争由 events 层 `model_turn.error="LLM 调用 HTTP 503"` 直接判定，该字段要解决的痛点已被 events 层旁路 |
| `R-20260815-03` | 冲突再现**并首次拿到机制**：`counterpoint` 在 `structural_verifier` 判 missing、在 `answer_coverage` 判 present，根因是缺口模板列出缺失项时写下的「提供主要**反证**或竞争性解释」恰好命中 `_MARKERS["counterpoint"]` 的子串「反证」。在生效快照 `6cd0756e` 上重算逐字复现 | `pending` | 保持 Open（修复未落地）。**机制应并入其修复口径**：两判据的分歧不是随机的，而是缺口模板与标记词表结构性重叠的必然结果；见新增 `R-20260816-09` |
| `R-20260816-04` | 非该注册样本。本 run 实跑 `evaluate_marker_coverage` 得 `warnings=[]`、`marker_coverage=incomplete`、`uncheckable=[]`——`uncheckable_judgment_empty` 未触发，因为 `direct_assessment` 有词表故不进 `uncheckable` | `pending` | 保持 Open。新增观察：缺口模板绕过该告警存在**第二条路径**（题型的判断槽有词表时），建议与 `R-20260816-09` 并案 |
| `R-20260816-05` | 本 run 正是 `(repair_model_unavailable, draft_len=0)` 形状，但成因是 provider 503 而非超时 | `pending` | 保持 Open。**分行键需补 error class**：若观测台只按 `stop_reason + draft_len` 分行，本 run 会与 L01 空稿错误合并 |
| `R-20260815-21` | `bindings=[]`、`evidence=[]`，不是「有 hashes + 非空 gap」滑档形状 | `pending` | 保持 Open；本 run 不能回填 |
| `R-20260815-01` / `02`、`R-20260816-02` / `03`、`R-20260804-10` | 本 run 均非其注册样本（19 个验收 turn 夹具 / 预算三臂对照 / headless slow-tool handoff），无新证据 | `pending` | 保持 Open |

本轮 `fix_type_refuted_streak = 0`（无 `refuted`），未触发架构升格线。

#### 口径更正（2026-08-16，用户当场纠偏）

`R-20260816-06` 初版写的是「熔断 + 快速失败 + 如实告知」。**形状错了**：那只让失败更快更诚实，不让它成功。用户指出「两条路本来就只是 provider，GLM plan 可用」，实测坐实：

- `llm_refine.detect_providers()` 返回**有序 fallback 链**；两个 key 同时在时链长 2：`[0] zhipu/glm-5.2@bigmodel` + `[1] openai/gpt-5.6-terra@x.ailzd`。
- `GLMModelClient` docstring 明写 adapter provider-neutral、吃「one explicit, ordered chain」；`llm_refine.py:730/830` 遍历它。
- **8792 当前链长为 1**，故命中 `glm_agent_runtime.py:84` 的 `_retry_single_real_provider` → 在同一个死 provider 上重试 4 次 → 这就是 `llm_calls=16` 的来源。
- 旁证：8795 于 22:23:43 换成 GLM coding plan 后 11 单全部正常（draft 576–894、tools 3–6、零 5xx），与 8792 同代码族。

因此一级修复是**失败转移**（`R-20260816-06` 已按此改写），`R-20260816-07` 的成因行降为二级——它回答的是「转移也失败之后怎么说话」，仍要做但不能替代转移。

**同源教训**：把「2026-08-05 模型轴已定 gpt-5.6-sol / GLM 退役」这条**决定**读成了**技术约束**。枚举名 `continuous_glm` 的 `glm` 是兼容名、adapter 是 provider-neutral——项目笔记里早就写了这一条，本轮分诊没去对表就下了「只能等中转恢复」的结论。**下次给可用性结论前，先数一遍 provider 链长度。**

#### `R-20260816-06` 部署后实测（2026-08-16 23:05，8792 pid 90194）

启动器已加回 GLM 三件套并按 launchd `kickstart -k` 重启；生效 env 与链序实测 `[0] zhipu/glm-5.2@bigmodel` + `[1] openai/gpt-5.6-terra@x.ailzd`。原题在 `user=verify-glm-0816` 复跑一次（`run_20260816_230528_976709`）：

| 判据 | 中断时（`221823`） | 转移后（`230528`） | 达成 |
|---|---|---|---|
| provider | openai（5xx ×16） | **zhipu，零 5xx** | ✅ |
| `usage.tool_calls` | 0 | **4**（+1 `tool_budget_exhausted`） | ✅ |
| `outcome.evidence` | 0 | **25** | ✅ |
| 模型是否产出 | 0 token | 72 + **1395** 字符，17266 in / 2547 out | ✅ |
| `outcome.draft` 终值 | 0 | 0（seq=14 有 1395 字，终局未保留） | ❌ |
| required output `fulfilled` | 0/3 | 0/4 | ❌ |

**outcome 记 `pending`，不写 `confirmed`。** 预测写坏了：把「失败转移发生」与「交付成功」捆在一条里，结果前者确认、后者未达，无法整体结案。**教训：一条预测只钉一个可判定事实。** 后续拆分为 `-06a`（转移，已达成）与 `-06b`（交付，转由 `R-20260816-11` 承接）。

阻塞点已换人：不再是 provider 中断，而是**预算与 provider 延迟错配**——见 `R-20260816-11`。

### 2026-08-16 outlook 核验预算回归：开工回填

此表冻结在本轮 M1 归因之前。被审 runtime = 8792 `773b3d7e`；主样本 `run_20260816_131941_597875`。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-04` | 又一份空 draft：`outcome.draft=""`，`draft_source` 仍为 `None`。区分 REASONING/HARNESS 的信号在 `gaps=['LLM 调用失败（TimeoutError）']` 与 `stop_reason=repair_model_unavailable`，不是预测要求的字段 | `pending` | 保持 Open。字段未落地，不得因「这次能从 gaps 看出来」写 confirmed |
| `R-20260815-21` | `bindings=0`，不是「有 hashes + 非空 gap」滑档 | `pending` | 保持 Open；本 run 不能回填 |
| `R-20260815-01` / `02` / `03` | 不是那 19 个验收 turn | `pending` | 保持 Open |
| `R-20260804-10` | 本轮是 workbench continuous episode，不是 headless handoff | `pending` | 保持 Open |

### 2026-08-15 Round 1 开工前回填

此表冻结在 Round 1 新归因之前。归一化器代码 revision `cd47d257`，
`intelligence/eval/normalize_harness_trace.py` 自 `5b456532` 以来未被改动。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-02` | **首次拿到真 Codex rollout JSONL 并实跑归一化器**：输入 `~/.codex/archived_sessions/rollout-2026-08-03T20-18-55-019fc790….jsonl`（session_meta 的 cwd 为本仓，`sha256=62385ee5…b316a7`，264 条记录）。`--kind codex-rollout`、`--kind auto`（自动判定结果亦为 `codex-rollout`）、`--kind codex-exec` 三种传法**结果一致：264/264 `unmapped`，step 分布 `{'unmapped': 264}`，零个 `observe`、零个 `tool`**。预测要求的「真 rollout 中 `function_call_output` 归入 `observe`」在真产物上不成立 | `refuted` | 从 Open 移到 Closed。**根因是形状不匹配，不是格式漂移**：`_codex_mapping`（`normalize_harness_trace.py:279-298`）只读顶层 `type` 与 `record["item"]["type"]`，而真 rollout 的语义类型在 `record["payload"]["type"]`，顶层 `type` 恒为信封名（`response_item`/`event_msg`/`turn_context`/`world_state`/`session_meta`）。抽查 2026-06-02 / 07-16 / 08-03 / 08-14 四份真 rollout，**`item` 键出现次数均为 0**（跨 2.5 个月无一例），故该 mapper 从未在真产物上工作过；08-04c 那次「synthetic 已证明」用的夹具是 `{"type":"item.completed","item":{…}}`（`test_normalize_harness_trace.py:180`）与类型在顶层的 `{"type":"function_call_output"}`（同文件:350）两种形状，**均非真产物形状**。**比较层护栏确实生效**（不是静默发绿）：与 `a-control.json` 双输入比较返回 `unmapped_counts.left=264`、`pre_divergence_equivalence=not_established`、三条 `interpretation_caveats`（含「one side has no mapped semantic events: no comparison is possible」），故影响面是**跨 harness 比较拿不到信号**，不是拿到错信号。另注：单输入产物同时报 `unpaired_tool_requests=0`，正是 [trace-profile.md](trace-profile.md) §2 警告过的「健康零」——此处 0 的成因是没有任何事件进入配对词表 |
| `R-20260804-10` | 本轮无新证据。08-04 之后唯一触及 `intelligence/runtime/headless_tool_gateway.py` 的提交是 `b6900f47`（15 个 loop 模块搬进 `intelligence/runtime/` 的纯位移），故现存 `handoff_window`（gateway:588）属 Task 1/2 存量，非本轮进展。Task 3-6 四项在生产代码中穷尽搜索均为空：`intelligence/{runtime,services}/` 下 `derived_context`/`派生`、`late_result`/`迟到`/`stale_result`、`slow_tool` 零命中；`watchdog` 仅命中 `conversation_orchestrator` 的 `workbench-ask-watchdog`（Ask 根看门狗，与 R-10 的 headless watchdog 非同一物）。`docs/verification/` 中 08-05 起仅新增 08-09 的 seam-ladder / market-routing 三份，均非 R-10 主题 | `pending` | 保持 Open。预注册条件（离线主门全过 **且** 一次瑞华泰 canary）二者仍都未做到，**不得因 Task 1/2 已完成而写 `confirmed`**。口径校正：`docs/handoffs/2026-08-04d-worklist-freeze-r10-then-tool-surface.md` §0 原文写的是 Task 3-6「**取消**」，本账本此前记作「冻结」；两种记法指向同一事实（未执行），恢复条件以 08-04d §0 为准 |

### 2026-08-04d R-10 冻结（Task 3-6 未执行）

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-10` | Task 1/2 已完成，另补两个收尾洞：秒数结算的 check-then-act race 下沉到 ledger 锁内（新增 `settle_seconds()`），`root_budget_overdraft` 接进 `normalize_harness_trace` 映射表（`observe`/`control`）。离线读数：gateway 34 passed、research_contract 2 passed、normalize 30 passed、codex_runtime 28 passed+1 skipped、ruff pass；两条新测试均通过变异测试 | `pending` | **已冻结，Task 3-6 未执行**：未做 watchdog / 派生 context / 迟到隔离，未跑离线全量 gate，未跑 live canary。预注册条件要求离线主门全过**且**一次瑞华泰 canary，二者都没做到，因此不得写 `confirmed`。冻结原因与恢复条件见 `docs/handoffs/2026-08-04d-worklist-freeze-r10-then-tool-surface.md` §0；主线已切到工具面盘点 |

### 2026-08-04c R-10 观测前置补齐

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-02` | synthetic Codex rollout 已证明 `function_call_output` 进入 `observe` 且悬空调用计数为 1；仍没有该预测要求的真 rollout JSONL | `pending` | 保持 Open；synthetic 只锁 normalizer 行为，不替代真实产物结案 |
| `R-20260804-10` | gateway 的 request/result/error 已共享 32-hex request id；normalized artifact 保留独立 `correlation_id`，mismatched id 不再互相消费，Workbench N/A 显式为 `null` | `pending` | 只确认离线主门所需仪器已具备；尚未实现或运行 slow-tool handoff，不提前确认根因 |

### 2026-08-04b L7 finalization：T3 回填

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-02` | 本轮仍只有 `runtime-benchmark`，没有真 Codex rollout JSONL | `pending` | 保持 Open |
| `R-20260804-09` | T3 瑞华泰为事件级 `headless_protocol_rejected` / 135.555s，5 个 tool request 只有 4 个 mailbox exchange，`finalization=0`；最后一个 `evidence_search` 没有 result/error，随后为 `headless_command_failed` | `refuted` | 从 Open 移到 Closed；PRIMARY 前移到 in-flight tool 阻塞交接，另开 `R-20260804-10`，不调预算 |

> T2 的 instruction 传输与事件顺序已由真实 wrapper seam 单测证明，但 live 的失败路径
> 到不了 result/rejection activation point。按预注册规则，这不是“部分成功”或 pending。

### 2026-08-04b L7 finalization：开工前回填

此表在新增 finalization 仪器、修改 headless 运行路径或启动新 live run **之前**冻结。

| ID | 开工前新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-02` | 本轮仍无真 Codex rollout JSONL；预算 artifact 是 `runtime-benchmark`，不能替代 `function_call_output` 的原生投影证据 | `pending` | 保持 Open，不用近似事件结案 |
| `R-20260804-09` | 尚无带 `finalization` 与事件时间戳的新 rollout；冻结的 `c_long_capped` 瑞华泰事件序列停在 `tool_request(evidence_search)`，没有 `research_stage_closed` / `tool_budget_exhausted` rejection | `pending` | 先做 T1 仪器并复跑同一 profile；T2 必须以真实 activation path 为准，不能把 rejection-only 误写成已验证修复 |

> 开工前额外约束：`c_long_capped` 的 `gateway_floor_ratio=0.0`，瑞华泰只消耗
> 5/6 次工具额度且最后一次调用没有返回。仅给 rejection 增加 instruction 在该 case
> 上不会激活；这是 T2 的设计门，不是 R-09 的提前结案。

### 2026-08-04 预算标定：开工前回填

此表冻结在本轮新 live run 与新归因之前，防止后续结论倒灌成“开工前已知”。

| ID | 开工前新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-02` | 本轮暂无新的真 rollout JSONL | `pending` | 保持 Open；只有真 `function_call_output` 被归一化为 `observe` 才结案 |
| `R-20260804-04` | 本轮暂无新的真 Codex headless run；仍只有既有单元实测、合成端到端实测与中间跳的 code reading | `pending` | 先跑 `a_control` 五题，再按 runtime issues 与 protocol issues 的实际值结案 |
| `R-20260804-07` | 本轮尚未产出新的标准四阶段 triage 报告 | `pending` | 完成预算 M2 分诊后再检查 `first_bad_step` 是否与本仓 L1 空间直接对齐 |

> **`R-20260804-04` 已结案。** `b_floor_ablation` 的真 Codex headless run 自然产生
> 两个 `headless_timeout`；两题的 `runtime_result.payload.issues` 均为
> `["headless_timeout"]`，而 `protocol_issues` 均为 `[]`。此前缺失的 runtime stdout
> → usage → benchmark projection 中间跳已有实测，不再只靠 code reading。

### Closed

| ID | 来源 | fix_type | verification_prediction | outcome | evidence |
|---|---|---|---|---|---|
| `R-20260804-01` | 收口审计 §修复1 | `EVAL_ONLY` | 左短右长且左为前缀时 `compare_sequences` 不再抛 `IndexError`，返回 `equivalent_before_divergence`，evidence 含 `continues_on` | `confirmed` | `test_compare_sequences_survives_prefix_on_either_side`；两种传参顺序均返回 `synthesize @ ordinal=3` |
| `R-20260804-02` | 收口审计 §修复2 | `EVAL_ONLY` | 真 Codex rollout 中 `function_call_output` 归入 `observe`，与 workbench 的 `validate→observe` 对齐；第一个工具结果处不再出现**词表性**分叉 | `refuted` | 真 rollout `sha256=62385ee5…b316a7` 过 `normalize_harness_trace`：264/264 `unmapped`，无 `observe`/`tool`；三种 `--kind` 传法一致。`_codex_mapping` 读 `item.type`，真产物语义类型在 `payload.type`，四份跨月真 rollout 的 `item` 键出现次数均为 0。详见 §2026-08-15 Round 1 开工前回填 |
| `R-20260804-03` | 收口审计 §修复4 | `EVAL_ONLY` | 归一化产物能**独立**复现审计表第三列，不必回原始 receipt | `confirmed` | 重跑历史收据，5/5 `finish` 事件带 `status` + `stop_reason`，与 arm 级逐条对齐（`ruihuatai-valuation` 的已知不一致除外） |
| `R-20260804-04` | 收口审计 §修复A | `HARNESS_FIX` | 新 run 中仅 `headless_timeout` 的 case **不再**出现 `runtime_invalid_actions:N` | `confirmed` | `intelligence/eval/measurements/2026-08-04-budget-calibration/b-floor-ablation.json`：`ruihuatai-valuation`、`weekly-market-cause` 的 `runtime_result.payload.issues=["headless_timeout"]`，同题 `protocol_issues=[]` |
| `R-20260804-05` | 收口审计 §修复B | `HARNESS_FIX` | 新 benchmark artifact 的 `diagnostics.events[0].kind == "task"` 且 `sequence == 1`；其 payload 只有 `task_frame_hash`；题面不出现在 `events` 内 | `confirmed` | 跑真 benchmark CLI（合成 runtime，真实序列化路径）：`{"kind":"task","sequence":1,"payload":{"task_frame_hash":"432d9856…"}}`，题面确认不在 `events` 内。两条发射路径（`codex_headless_runtime:903`、`agent_episode:155`）均为 sequence 1 |
| `R-20260804-06` | 收口审计 §修复C | `EVAL_ONLY` | 新 run 若产生 `mode_decision` / `branch_*` / `finalization`，归一化后 `unmapped_count` 仍为 0，且 `mode_decision → plan` | `confirmed` | 同上收据归一化：10 事件 / **0 unmapped**，`mode_decision→plan`、`branch_started→retrieve`、`tool_request→tool`、`tool_error→observe`、`finalization→synthesize`、`finish→stop` 逐条命中 |
| `R-20260804-07` | 设计评审 G2 词表对齐 | `EVAL_ONLY` | 下一份 triage 报告的 `first_bad_step` 可与本仓 `first_divergence_step` **直接比较，无需翻译**；L1=`tool` 的 finding 在本仓可表达 | `confirmed` | `docs/verification/2026-08-04-budget-calibration.md`：`first_bad_step=stop`；三份 comparison 的 `first_divergence_step=observe/stop`，均为 `triage-l1-9` 且 `unmapped_count=0` |
| `R-20260804-08` | 设计评审 §仪器覆盖矩阵 | `HARNESS_FIX` | 补齐埋点后，`configure → intent → plan` 三步在 workbench 与 codex **两侧都非空**，`first_divergence_step` 首次具备行为含义 | `confirmed` | 两侧真实路径实测：workbench 真 turn 读 `trace.jsonl` → `configure→intent→plan→route→retrieve→synthesize→observe`；codex 跑 `CodexHeadlessRuntime.run()`（真 `_to_outcome`，仅 subprocess 用 fake stdout）→ `configure→intent→plan→tool→observe→observe→stop`。**门槛 3/3**，两侧共有由 1/9 升至 **4/9**。测试：`test_runtime_emits_configure_and_plan_landmarks_in_l1_order`、`test_turn_trace_exposes_configure_and_plan_as_their_own_l1_steps` |
| `R-20260804-09` | 标准 M2 分诊 F-001 | `HARNESS_FIX` | 显式 finalization handoff 后，瑞华泰进入 finalization 并以 `model_finish` 在 root 前结束 | `refuted` | `2026-08-04b-finalization/c-long-capped-t2.json`：事件级 `headless_protocol_rejected` / 135.555s，5 requests / 4 mailbox exchanges / 0 finalization；最后一个 in-flight `evidence_search` 无 result/error，交接未激活。wrapper 60s timeout 是静态支持的候选退出路径，非 artifact 直接读数 |

### fix_type refuted streak（作用域：本项目累计）

**不跨项目共享**：同一 `fix_type` 在别的被审系统上失败，不构成本项目升格的证据——
升格线要回答的是「**这个系统**的问题是不是不在我以为的那层」。跨项目的同类失败属于
skill 自身的方法论证据，走 `known-gaps.md`，不进本表。

| fix_type | 连续 refuted | 距升格线 |
|---|---|---|
| `SYSTEM_PROMPT_FIX` | 0 | 3 |
| `TOOL_DESCRIPTION_FIX` | 0 | 3 |
| `ROUTING_FIX` | 0 | 3 |
| `DATA_CONTRACT_FIX` | 0 | 3 |
| `HARNESS_FIX` | 1 | 2 |
| `EVAL_ONLY` | 1 | 2 |

计数规则：同 `fix_type` 的 `refuted` **连续**出现才累计，中间出现一次 `confirmed`
即归零。达到 3 时下一份报告的 `fix_type_refuted_streak` 必须写明已触线，并把架构 /
`HARNESS` 层列为本次的竞争假设之一。

截至 2026-08-04：`R-20260804-09` 是本项目第一条 `HARNESS_FIX` refuted，连续 streak=1。

截至 2026-08-15：`R-20260804-02` 是本项目第一条 `EVAL_ONLY` refuted，连续 streak=1（距升格线 2）。
它与 `R-20260804-09` 分属不同 `fix_type`，**不互相累计**——`HARNESS_FIX` 的 streak 仍为 1。

### Residual uncertainty（不是预测，是没结论的观察）

与 Open 表**分开放**：它们没有可证伪预测，不参与 streak，混进 Open 会污染命中率分母。

| 观察 | 状态 | 下一步取证 |
|---|---|---|
| `test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state` 在一次全量跑中失败，其余多次（单测 / 整文件 / 后续三次全量）均通过 | 未归因 | 连跑 5 次全量记录命中率；若可复现再定位是哪个前序文件泄漏状态。**当前不归因到 2026-08-04 的改动**——它的断言不触及任何被改的面 |
| 收据的 arm 级 `stop_reason` 与事件级 `finish.payload.stop_reason` 在 `ruihuatai-valuation` 上不一致（`semantic_repair` vs `model_finish`） | 已记入 [trace-profile.md](trace-profile.md) §2 | 无需修复，属分层语义差异；跨 harness 比较一律用事件级 |
| `route` 在 codex 侧结构性不存在（episode 不做 skill 分派，backend 由 benchmark 选定、registry 固定） | 已记入 [trace-profile.md](trace-profile.md) §8 | 无需埋点。门槛已由四步收窄为三步——把结构差异写成埋点缺口，会诱导为满足指标而制造事件 |
| 2026-08-16 长尾 off 臂 ~151–159s degraded：L01 是空 draft + `repair_model_unavailable`；L05 是有 draft + `repair_model_stop` + judge 瞬时失败 | 已记入 [trace-profile.md](trace-profile.md) §2 | 墙钟不能合并机制；分诊见 `docs/verification/2026-08-16-outlook-verification-budget-regression.md` |

### 溯源说明

`R-20260804-01..08` 来自 2026-08-04 的**代码审计 + 收口 + 设计评审**，不是标准四阶段
`agent-run-triage` 分诊：没有走 Triage → Static → Dynamic → Synthesis，没有分配
L0/L1/L2，也没有 3 条以上排名假设。因此这些条目**只有 `fix_type` 与
`verification_prediction` 可用于 streak 统计，不能当作已确认根因的 PRIMARY 引用**。

`R-20260804-09` 来自第一份标准 M2 分诊
[`docs/verification/2026-08-04-budget-calibration.md`](verification/2026-08-04-budget-calibration.md)，
已按 Evidence → Finding → Path、四条可证伪假设和冻结 taxonomy 定位
`F-001: LOOP/stop/execution-error-category-timeout`；它可以作为后续 Prior prediction
closure 与 PRIMARY 证据引用。

`R-20260815-21` 来自轨道 A 标准 M1 分诊
[`docs/verification/2026-08-15-trka-repair-finish-gap-slip.md`](verification/2026-08-15-trka-repair-finish-gap-slip.md)，
PRIMARY=`HARNESS/configure/task-instruction-category-non-compliance`。它可以作为后续
Prior prediction closure 与 PRIMARY 证据引用。轨道 A 不回写 `R-20260804-02` / `R-20260804-10`。

`R-20260816-01..05` 来自标准 M1 分诊
[`docs/verification/2026-08-16-outlook-verification-budget-regression.md`](verification/2026-08-16-outlook-verification-budget-regression.md)，
outcome=`ROOT_CAUSE_NOT_CONFIRMED`，PRIMARY=`UNCLEAR/synthesize/DEPTH_INSUFFICIENT(D4)`。
它可以作为后续 Prior prediction closure 引用，但不能当作已确认单一刀（#72/#75/#79）的 PRIMARY。

首次真正的分诊在回填本账本时，应把这一批视为 `no prior triage report` 的历史遗留
条目，只做 outcome 回填，不继承其归因。

对应审计记录：
- [docs/verification/2026-08-03-cross-harness-shared-layer-audit.md](verification/2026-08-03-cross-harness-shared-layer-audit.md)
- [docs/verification/2026-08-04-improvement-loop-design-review.md](verification/2026-08-04-improvement-loop-design-review.md)
- [docs/trace-profile.md](trace-profile.md) §2 字段陷阱、§6 投影契约、§8 仪器覆盖矩阵
- commit `09657e2a`

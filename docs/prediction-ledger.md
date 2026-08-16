# Prediction Ledger: finance-workspace-private

- last_updated: 2026-08-16（R-06 结案 H9；追加 R-10 standard judge 窗地板。8795=`02fa203e`，8792 仍 `773b3d7e`）
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
| `R-20260815-03` | 标准 M1 分诊 F-003 | `DATA_CONTRACT_FIX` | `answer_coverage` 与 `structural_verifier` 对同一 `output_id` 改用同一判据函数后，本轮 9 个 run 中的 6 处冲突全部消失或转为显式 warning；B8 的 `evidence_boundary` 不再同时是 present 与 missing | 用本轮冲突的 6 个 run 作回归夹具，断言无静默分歧 | `pending` |
| `R-20260815-04` | 标准 M1 分诊 F-001 | `HARNESS_FIX` | `outcome` 落盘补 `draft_source ∈ {model_returned_empty, truncated_by_budget, provider_error}` 与合成入口 `remaining_ms` 后，下一次空 draft 的 turn 其 `draft_source` 非空，可据以在 REASONING 与 HARNESS 之间定夺 F-001 的 L0 | 字段存在性单测；**单次读数不得结案**，需 ≥3 个同形样本 | `pending` |
| `R-20260804-10` | L7 finalization T3 | `HARNESS_FIX` | deadline-aligned per-tool handoff 能让超出安全窗口的 deterministic slow tool 在生效阈值返回一条可配对的 `research_stage_closed + instruction`；正常成功路径同 id 恰好一个 `tool_result`，handoff 路径同 id 恰好一个预期执行层 `tool_error` 且无迟到 `tool_result`；只发一次 finalization，归一化后 `unpaired_tool_requests=0`；finalization reason 与 budget payload 同时看见 root-ledger 耗尽，handoff window 来自 profile / 生效预算而非隐藏的 `initial×0.20` reserve | **主门只用离线** slow-tool fake clock/隔离测试，并另测 `policy calls>0、root ledger calls=0` 与 `floor_ratio=0`；按 request id 分开断言正常 `tool_result`、handoff 执行层 `tool_error` 和 late-result 不入账，`tool=mailbox,error=response_path_conflict` 作为独立 transport 诊断不计入执行终态基数；再断言配对计数、finalization 次数/余量与落盘生效值。全部通过后才跑一次瑞华泰 canary，单次 live 不能独立结案 | `pending` |
| `R-20260815-24` | 轨道 A Round 5 M1 F-001（E-007） | `DATA_CONTRACT_FIX` | marker-loss 删除某 required output 并写入 `gap_output_ids` 时，同步收缩/清空该格绑定或标 structural missing 后：同形 case（hashed fulfilled + 对这些 ID 做 marker-loss）不得再同时出现「结构 fulfilled + `gap_output_ids` 含这些 ID + `citations=0`」。要么剩余 fulfilled 格仍被引用且 `evidence_bound>0`，要么被删格不再 fulfilled。再出现 B3#2 分道即 **reproduces → refuted**。不给已删正文发引用 | **离线已绿**（2026-08-15）：`_shrink_verified_for_marker_loss` 在 `_marker_loss_partial_public` 两条返回路径上收缩 `semantic.verified`（lost 格 `missing`、绑定清空并补 gap）。夹具 `test_marker_loss_shrinks_b3_hashed_cells_and_clears_bindings`、`test_marker_loss_keeps_remaining_hashed_cell_on_partial_c6_shape`、`test_marker_loss_ignores_output_ids_absent_from_contract`。确认口径是 `semantic_verifier.verified.completion`，不是 `episode_fulfilled_hashed`（该仪器仍读 `structural_verifier` + 顶层 `outcome.bindings`，本轮不改 `acceptance.py`）。**部署窗已开**（2026-08-16）：8792=`437cd5e9aa1a` / `source_dirty=false` / `code_matches_repo=true` / 加载树含 `_shrink_verified_for_marker_loss`。live 臂仍等下一批同形 case；**切窗本身不得写 confirmed** | `pending` |
| `R-20260815-25` | 轨道 A Round 5 F-003 | `HARNESS_FIX` | 本修复部署后：新的 `tool_error` 且 `error=tool_exception` 的事件 `detail` 非空，形如 `ClassName: first line`，且不含 `/Users/` 或 `/home/`。再出现 `detail=""` 即 **reproduces → refuted**。不要求数据层已修；A 组仍可抛 `tool_exception` | **离线已绿**：`test_tool_exception_is_traced_and_model_can_finish_same_episode`、`test_tool_exception_detail_strips_home_path_and_stays_nonempty`、`test_public_tool_exception_detail_keeps_class_and_first_line`；timeout 夹具仍禁止 raw sentinel。live 臂等部署后下一批 | `pending` |
| `R-20260815-26` | S10 Phase A 标准 M1 F-001 | `EVAL_ONLY` | 冻结谓词与 N=5 题写入 `intelligence/eval/cases/s10_branch_eligible_tasks.json` 后：Phase B / S1 A/B 必须引用该夹具，不得改用 08-14「三次现场零调用」当基线。夹具 `frozen_at` 与五题原文保持不变；生产 prompt / 路由 / `episode_semantic_verifier.py` 本行不改 | 夹具存在且五题与报告 Freeze 表逐字相同；S10 报告 `validate-report.sh` RC=0。Phase B 若开，另用 `R-20260815-27` / `-28` 候选行，不把本行当 ROUTING 已确认 | `pending` |
| `R-20260816-01` | outlook 预算回归 M1 F-001 | `HARNESS_FIX` | 下一次空 draft 超时 run 的首轮 finalize `model_turn` payload 含 `timeout_asked`（及入口剩余秒 / input tokens），能直接比较 asked 与墙钟 | 字段存在性单测已随 #84 绿；用下一份同形 live run 读 seq=首轮合成 `model_turn`，缺字段不得结案。长尾窗收口前不占 8792 | `pending` |
| `R-20260816-02` | outlook 预算回归 M1 F-002 | `HARNESS_FIX` | 若动预算：同题重放要么首轮合成成功，要么 repair 的 `timeout_asked` 不再小于该 run 已观测的首轮合成墙钟；须附 2026-08-08 式延迟实测与全路由影响面 | 禁止只把 T 或 30 调大当修复；非观点题对照不得变慢超 5pp | `pending` |
| `R-20260816-03` | outlook 预算回归 M1 F-001 | `EVAL_ONLY` | 同题三臂（只 #72 / 只第 4 次查询 / 四层全开）能单独证实或证伪「#72 提示变重」与「stock_high_daily 扩容」 | 45 槽已否证二者作**窗口充分条件**；L01 r1 必要性仍要单变量。8795 只跑 identity。3-tool/#72-off 须另开 hook 树，不停泊 `21dbf6c1` | `pending` |
| `R-20260816-10` | 2026-08-16 judge transient R-06 T3 F-001 | `HARNESS_FIX` | 处置落地后，下一份 draft>0 的 8795 同形重放：judge 首轮 `timeout_asked` ≥20；H9 形 TimeoutError 率相对 `docs/verification/2026-08-16-judge-transient-r06.md` 11/11 下降 | 只验 standard 窗地板 50 / 首轮 25；工具批仍 70、reserve 仍 20、deep 窗仍 50。PR 若含 T/30/档位上调且无 08-08 式实测 → 改记 R-07 refuted | `pending` |
| `R-20260816-07` | 2026-08-16 有稿 judge 案豁免 | `NO_SYSTEM_FIX` | 本窗关闭后下一份自称「outlook 预算回归修复」的 PR diff **不含** T / `_REPAIR_SECONDS_CAP` / 生产档位上调 | 出现上调且无 08-08 式延迟实测 + 全路由影响面 → refuted | `pending` |
| `R-20260816-08` | 2026-08-16 有稿 judge 案 F-003 | `EVAL_ONLY` | 若把 G01–G05 degraded 写入长尾开关账，必须先有同题 off 臂；在此之前收据只写「heading 缺席 + 路由仍 theme-research」 | 无 off 基准却写开关因果 → 本预测 refuted | `pending` |
| `R-20260816-09` | 2026-08-16 有稿 judge 案 F-004 | `HARNESS_FIX` | 若动 `_BALANCED_SYNTHESIS_RESERVE` / 非 finalize `stage_timeout`：改完后非 finalize `timeout_asked` 不再系统等于 `remaining−60`；须附 2026-08-08 式延迟实测 + 全路由影响面 | 只调 T/30 当修复 → 本预测不兑现（T 不改 `min(90,T−40)`）。观点题对照不得变慢超 5pp | `pending` |
| `R-20260816-11` | 宽题取证饿死 M1（`run_20260816_205439_732198`）+ 十题窗 eb 回归（#94 检阅批注 Round 2） | `EVAL_ONLY` | 8795 含工具批埋点 tip 重放：每发 `tool_request` 带 `batch_grant_asked`/`stage_timeout_granted`/`episode_remaining_at_dispatch`/`remaining_slots_at_dispatch`/`turn_elapsed_at_dispatch`。**deep 自然完成值合计 > standard 总窗 → H-a**（架构支，不调参）；**evidence_search 自然时长 ≤10s 且失败仅与 dispatch 授予≤0 / slot 耗尽相关 → H-c**（顺序/信号）；**十题窗掉分槽重放同形 → H-b 同根，eb 回归并案结**。缺字段不得结案 | 判定不得混入 R-10 判据（同侧车不同读数）；`tool_timeout`（时间闸 L355-366）与 `tool_budget_exhausted`（次数闸 L340-352）分开计 | `pending` |
| `R-20260816-12` | 宽题取证饿死案绊线 | `NO_SYSTEM_FIX` | 下一份自称修「宽题取证饿死 / eb 回归」的 PR diff **不含** `ASK_TOOL_BATCH_TIMEOUT` / `tool_batch_seconds` / T / slot 上限 / 档位上调 | 出现上调且无 08-08 式延迟实测 + 全路由影响面 → refuted | `pending` |

`outcome` 只能是 `pending` / `confirmed` / `refuted`。**部分验证不要写 `confirmed`。**

### 2026-08-16 off 45 槽分型 + judge 全窗案：开工回填

此表冻结在本轮 M1 归因之前。材料 = 长尾 off 45 + G01–G05；对齐键 `slot`+`run_id`。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-05` | 三元组已分型：空稿跳过 judge 10 槽；有稿+transient 22 槽；judge 完成 3；无 episode 9。L01 空稿与 L05 候选草稿不再用 151–159s 合并 | `confirmed` | 从 Open 移到 Closed |
| `R-20260816-01` | 773b3d7e 窗内产物仍无首轮 `timeout_asked`。8795=`21dbf6c1` 已起，identity 未收齐 | `pending` | 保持 Open |

### 2026-08-16 identity 臂收齐：回填

8795 `21dbf6c1`；user `outlook-r03-0816`；L01×3 + L03×1。不占 8792。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-01` | 四槽合成/修复 `timeout_asked` 均在。空稿超时是 L01 r2 非 finalize asked=8.49，不是预测要的 finalize 空稿。68s finalize 空稿 0/3 | `pending` | 保持 Open。字段在 ≠ 形状结案 |
| `R-20260816-06` | L01 r3 / L03 已是 draft>0 + transient；`semantic_verifier` 仍无 judge `timeout_asked` / `exc_class` | `pending` | 保持 Open。#84 覆盖不够，须先补 judge 埋点 |
| `R-20260816-02` | 仍未动 T/30 | `pending` | 保持 Open |
| `R-20260816-03` | identity 不是单变量三臂 | `pending` | 保持 Open |
| `R-20260816-02` | 本轮书面豁免调 T/30，条件句「若动预算」未触发 | `pending` | 保持 Open；不写 confirmed/refuted |
| `R-20260816-03` | 45 槽否证 H2/H3 作充分条件；单变量三臂未跑 | `pending` | 保持 Open |
| `R-20260815-04` / `R-20260804-10` | 字段/headless 路径未触及 | `pending` | 保持 Open |

### 2026-08-16 outlook 核验预算回归：开工回填

此表冻结在本轮 M1 归因之前。被审 runtime = 8792 `773b3d7e`；主样本 `run_20260816_131941_597875`。#84 合入后代码在 `gitea/main` `21dbf6c1`，**尚未切 8792**。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-04` | 又一份空 draft：`outcome.draft=""`，`draft_source` 仍为 `None`。区分信号在 `gaps=['LLM 调用失败（TimeoutError）']` 与 `stop_reason=repair_model_unavailable` | `pending` | 保持 Open。字段未落地，不得因「这次能从 gaps 看出来」写 confirmed |
| `R-20260815-24` / `25` / `26` | 本 run 不是 marker-loss / tool_exception / S10 夹具样本 | `pending` | 保持 Open；本 run 不能回填 |
| `R-20260804-10` | 本轮是 workbench continuous episode，不是 headless handoff | `pending` | 保持 Open |
| `R-20260816-04` | L01 `answer.md` 原文过 `evaluate_marker_coverage` → `warnings=[]`、`marker_coverage=complete`。单测 `test_l01_gap_template_does_not_trigger_uncheckable_judgment_empty` 随 #84 合入 | `confirmed` | 从 Open 移到 Closed。改探测器另开观测台 |
| `R-20260816-01` | #84 离线单测绿；8792 仍是 `773b3d7e`，没有带 `timeout_asked` 的同形 live run | `pending` | 保持 Open。代码落地 ≠ 预测兑现 |

### 2026-08-15 Round 6 批 #3 回填

此表冻结在本轮新归因之前。8792 health `runtime.source_revision=fdb231148c0e91cd56f7f5d48b5252df80dfafb9`，`source_dirty=false`，`code_matches_repo=true`，`loaded_code_root=.../finance-workspace-fdb231148c0e/intelligence`，pid 70403。批 #3 `20260815T1005Z-r5-clean-baseline-3.json` `sha256=e475f3c889946b2ef87507ca303effa5bf9a1ca153821009f60e6b4edaf1ebf0`。本轨不写 A 的 R-23/R-24/R-25 outcome。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-10` | B 组 N=3（只 `evidence_bound>0`）：B1 2/3、B2 3/3、B3 2/3、B4 2/3、B5 2/3、B6 0/3（三批澄清）、B7 2/3、B8 2/3。三批 sha256=`b712bd2e…d8d350` / `51e61710…304ef4` / `e475f3c8…f1ebf0`。并行 efh 不结案。B4 产物 timeout/eb=0，仓外 episode 已交付——不改口径 | `confirmed` | 从 Open 移到 Closed。单批失败名单仍可打回 |
| `R-20260815-09` | 21/21 验收挂上的 episode 末条 finish 有 `rejection_code`/`rejection_reason`；20 题 `none`/空。B8 末条 `invalid_repair_finish` `rejection_code=no_substantive_answer` `rejection_reason=required output lacks substantive answer: scenario_range`。本轮 handoff 判据=字段在场性 + 有拒收时非空 | `confirmed` | 从 Open 移到 Closed。不定 B8 的 L0 |
| `R-20260815-12` | live：`preflight_detail` 含 `data_probe: finance_query=ok`，`data_probe_ok=true`，`window_contamination=null`（成功不盖戳） | `confirmed` | 已在 Closed；live 臂保持，不重开 |
| `R-20260815-23` | 本轨道只出数：15 条修复路径、14 条验收 eb>0；`invalid_action` 零条 unknown/truncated evidence hash。B8 是 `no_substantive_answer` | `pending` | 执行方正确不写 A 行。检阅方独立复核后收口，见下表 |
| `R-20260815-25` | 17 条 `tool_error` 均为 timeout/budget；零 `tool_exception`。数据层健康 | `pending` | 保持 Open；unobserved，不改口、不改 A 的行 |
| `R-20260815-24` | 13 题 `efh ≠ eb`；B3 本批 gap=`['direct_assessment']` 但 eb=10，不是 B3#2 零交付 | `pending` | 保持 Open；未实现，不开 L0 |
| `R-20260804-10` / `R-20260815-03` / `-04` | 本轮无新证据 | `pending` | 保持 Open |

### 2026-08-15 Round 6 检阅方回填 R-23

检阅方独立重扫批 #3 全部验收 run_id + B4 仓外 episode，不改执行方报告正文。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-23` | 3 条 `invalid_action` 均不含 unknown/truncated evidence hash（A5/B7=`bad_status`，B8=`no_substantive_answer`）。验收挂上的修复路径 14/15 eb>0。B8 是另一拒收码，不构成誊抄拒收再现。同形窗口存在，不是 unobserved | `confirmed` | 从 Open 移到 Closed。live 臂在 `fdb23114` / 批 #3 `sha256=e475f3c8…f1ebf0` |

### 2026-08-15 Round 5 收口回填

此表冻结在 Round 5 新归因之前。8792 health `runtime.source_revision=cb09f895734a65a38ae23f04d940f18ece2959fd`，`source_dirty=false`，`code_matches_repo=true`，`loaded_code_root=.../finance-workspace-cb09f895734a/intelligence`。无 `/tmp/finance-8792-live.lock`。无批 #3。批 #2 仍是 R-23 的 before。轨道 A 不写 B 轨行 / R-10。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-23` | 8792 仍 `cb09f895`；无 `*baseline-3*` / 本轮 r5 批。批 #2 before：B5#2 `run_20260815_112319_467917` seq 23、C7#2 `run_20260815_113732_480025` seq 17，`invalid_action.reason` 均为 truncated evidence hash；两题 `retrieved_unsynthesized` eb=0 | `pending` | 保持 Open。不得因 before 证据加长而写 confirmed / refuted。收口等用户部署 + 批 #3；若 A 组仍被数据层污染，只看 B5/C7 同形 |
| `R-20260815-21` / `-22` | 本轮无新 canary / slips 证据 | `confirmed` | 已在 Closed；不重开 |
| `R-20260804-10` | 本轮无 headless handoff 新证据 | `pending` | 保持 Open；本轨道不写该行 |
| `R-20260815-09` / `-10` / `-03` / `-04` | 本轮不取 B 缝证据 | `pending` | 保持 Open；本轨道不写这些行 |

### 2026-08-15 Round 4 收口回填

此表冻结在 Round 4 新归因之前。干净基线批在 B 分支 `fix/b-group-gap-shape-split`，
`sha256=b712bd2ee10fb431dba937416fb5882c6984ac65bb5421b5472f71c7ead8d350`，
`generated_at=20260814T200212Z`，`preflight_detail=revision=cb09f895`。
轨道 A 独立重扫 run 目录，不改 B 轨行 / R-10。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-21` | 预注册 C1 零违反：`caveat_slips>0` 恰 9 题（A6=2 / A8=2 / A10=1 / B2=3 / B3=3 / B4=2 / B5=1 / C7=1 / C9=1），有哈希格全部 `fulfilled` 且 eb>0。C2 零违反：6 个真缺口格（A4 `evidence_boundary`；C6 `direct_answer`+`evidence_boundary`；C9 `chain_mapping`；C10-t3 `direct_answer`+`evidence_boundary`）全部 `missing`。C3 不适用（有命中）。混合形正样本 C9：slips=1 与真缺口 missing 同 turn。条件靶收窄谓词（曾 `draft_chars>0` 其后 `carried_draft_chars=0`）0 命中，不开 M1 | `confirmed` | 从 Open 移到 Closed。预注册原文一字未改；收口见 `docs/verification/2026-08-15-trka-r3-r21-canary.md` §Post-batch closure。C10-t3 为 `bound_but_dropped`（两格 no_hash 真缺口），不移动 C1/C2 |
| `R-20260804-10` | 本轮无 headless handoff 新证据 | `pending` | 保持 Open；本轨道不写该行 |
| `R-20260815-07` / `-03` / `-04` | 本轮不取 B 缝证据 | `pending` | 保持 Open；本轨道不写这些行 |

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

### 2026-08-15 Round 5 轨道 B 回填

此表冻结在 Round 5 新归因之前。不改 R-23 / R-21。R-10 仍要 N=3 live 批才结案。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-12` | 离线：探针失败 preflight 仍 True 且 `preflight_detail` 含 `data_probe: finance_query=tool_exception`；`cmd_run` 产物顶层 `window_contamination=finance_query`、`data_probe_ok=false`；未探测不得盖污染戳。B3@批#2 夹具 `episode_fulfilled_hashed=2` 与冻结 `evidence_bound=0` 并存且不相等 | `confirmed` | 从 Open 移到 Closed。失败处置写死 `DATA_PROBE_ON_FAILURE=run_and_flag`。live 批 #3 若探针失败而无顶层标注，按原文 refuted |
| `R-20260815-10` | 本轮仪器已齐；N 仍为 2（缺批 #3） | `pending` | 保持 Open；不改判据 |
| `R-20260815-09` | 本轮不读未部署的 finish 拒收字段 | `pending` | 保持 Open；等新快照批 #3 |
| `R-20260815-23` | 本轨道只出数、不写该行 | `pending` | 保持 Open；不改 A 的行 |
| `R-20260804-10` / `R-20260804-02` / `-03` / `-04` | 本轮无新证据 | `pending` | 保持 Open |

### 2026-08-16 R-06 T2/T3 回填

8795 `02fa203e`；user `judge-r06-0816`；分层 12 槽。不占 8792。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-06` | 11 槽 draft>0 transient 带 `timeout_asked=5.208` + `exc_class=TimeoutError` + remaining 170–254；0 槽 asked≥20 / 5xx。asked≤12 且墙钟≈asked → H9 | `confirmed` | 从 Open 移到 Closed。收据 `docs/verification/2026-08-16-judge-transient-r06.md` |
| `R-20260816-02` | 未动 T/30 | `pending` | 保持 Open |
| `R-20260816-07` | 处置 PR 只地板 standard judge 窗，不含 T/30/档位上调 | `pending` | 保持 Open（绊线，合入后看 diff） |
| `R-20260816-08` / `-09` / `-01` | G 组只作旁证；未动 reserve；非空稿 finalize | `pending` | 保持 Open |

### Closed

| ID | 来源 | fix_type | verification_prediction | outcome | evidence |
|---|---|---|---|---|---|
| `R-20260816-06` | 2026-08-16 有稿 judge 案 F-001 | `EVAL_ONLY` | 下一份 draft>0 且 `semantic judge transient provider error` 的 run，judge 调用带 `timeout_asked` 与原始异常类（TimeoutError / HTTP status / 连接） | `confirmed` | 8795 `02fa203e` 12 槽：11 槽 asked=5.208 / TimeoutError / remaining≥170 → H9；0 槽 H8。收据 `docs/verification/2026-08-16-judge-transient-r06.md` E-001–E-004 |
| `R-20260816-05` | outlook 预算回归 M1 E-012 | `EVAL_ONLY` | 观测台/收据把 L01 空稿 `(repair_model_unavailable, draft_len=0)` 与 L05 候选草稿 `(repair_model_stop, draft_len>0, judge transient)` 分成两行 | `confirmed` | `docs/verification/2026-08-16-outlook-off-arm-typology-judge-case.md` E-001：`(repair_model_unavailable,0,unavailable)=7` 与 `(invalid_repair_finish,0,unavailable)=3` 对 `(repair_model_stop,>0,unavailable)=8` 等有稿行。禁止 151–159s 合并 |
| `R-20260816-04` | outlook 预算回归 M1 F-003 | `EVAL_ONLY` | 用 `run_20260816_131941_597875/answer.md` 跑 `evaluate_marker_coverage` 仍得 `warnings=[]`、`marker_coverage=complete`（#327 缺口模板不触发 `uncheckable_judgment_empty`） | `confirmed` | 原文夹具 `test_l01_gap_template_does_not_trigger_uncheckable_judgment_empty`（#84 / `21dbf6c1`）。`direct_answer` uncheckable + 模板句被当成非边界正文。改探测器另开观测台 |
| `R-20260815-23` | 轨道 A Round 4 M1 F-001 | `DATA_CONTRACT_FIX` | 本修复部署到 8792 之后的下一批：主路径 `deadline_exhausted`、修复轮已收集证据的同形 case，修复终局应解析出绑定且 `evidence_bound>0`。该批若再出现 `invalid_action.reason` 含 `unknown evidence hash`（誊抄 16-hex），本预测 **reproduces → refuted**。越界序号 / 歧义拼接仍拒收；不做模糊纠正 | `confirmed` | 批 #3 `sha256=e475f3c889946b2ef87507ca303effa5bf9a1ca153821009f60e6b4edaf1ebf0`。检阅方重扫：hash-reject 0；修复路径验收 eb>0 为 14/15；B8 `no_substantive_answer` 不同形。8792=`fdb23114` pid 70403 |
| `R-20260815-10` | Round 3 轨道 B（M1 F-002） | `EVAL_ONLY` | B 组结论改报交付率而非单批布尔后：连续 3 批的 B 组读数按题给出 N 次中的交付次数；任一只引用单批「失败成员名单」的结论可被评审据此打回 | `confirmed` | 批 #1 `sha256=b712bd2ee10fb431dba937416fb5882c6984ac65bb5421b5472f71c7ead8d350`；批 #2 `sha256=51e617100b4a72dcd58109c21d685d25b5a4ccae9c0e34507db494ee87304ef4`；批 #3 `sha256=e475f3c889946b2ef87507ca303effa5bf9a1ca153821009f60e6b4edaf1ebf0`。N=3：B1 2/3、B2 3/3、B3 2/3、B4 2/3、B5 2/3、B6 0/3、B7 2/3、B8 2/3。只 `evidence_bound>0`。报告 `docs/verification/2026-08-15-r6-clean-baseline-3.md` E-005 |
| `R-20260815-09` | Round 3 轨道 B（M1 F-001） | `HARNESS_FIX` | `invalid_repair_finish` 落盘拒收原因码与被拒 payload 的结构摘要（字段名/计数，不落正文）后：下一个该形状的 turn 其原因码非空，可据以在 REASONING（收尾产出不合法）与 HARNESS（修复轮契约拒收）之间定夺 F-001 的 L0 | `confirmed` | 批 #3 21/21 末条 finish 带 `rejection_code`/`rejection_reason`；B8 `run_20260815_182902_790837` seq 21 `rejection_code=no_substantive_answer` `rejection_reason=required output lacks substantive answer: scenario_range`。报告 E-006 |
| `R-20260815-12` | Round 5 轨道 B（preflight 数据源盖戳 + RU-3） | `EVAL_ONLY` | 开批前 `finance_query` 冒烟探针写入 `preflight_detail`（`data_probe: finance_query=ok/tool_exception/empty`）；失败处置写死 `DATA_PROBE_ON_FAILURE=run_and_flag`：不中止，产物顶层 `window_contamination="finance_query"` 且 `data_probe_ok=false`。探针失败的批必须可被评审一眼识别为污染窗口；静默混进「看起来干净」的批（无顶层标注）即 refuted。并行字段 `episode_fulfilled_hashed` 与 `evidence_bound` 同时在场、互不覆盖；B3@批#2 两值不等（2 vs 0） | `confirmed` | `test_preflight_probe_failure_does_not_abort`、`test_run_stamps_window_contamination_when_probe_failed`、`test_run_output_writes_exact_requested_path`（未探测不盖戳）、`test_b3_batch2_episode_fulfilled_hashed_unequal_to_frozen_eb`。处置常量写死 `run_and_flag`。冻结批 JSON 未改 |
| `R-20260815-11` | Round 4 轨道 B（检阅 E-r3 新缺陷） | `EVAL_ONLY` | 多轮题的 `execution_state_tally` 按轮计数且含 `execution_state_turn_rows`；case 级 `execution_state_aggregate` 取最后一轮（`last_turn`，写死）后：重放 C10（`20260814T1926Z-r3-clean-baseline`）时 tally 含 1 个末轮 `bound_but_dropped`，该 case 的 aggregate 同为 `bound_but_dropped`，二者不再互相矛盾 | `confirmed` | `test_c10_frozen_multiturn_tally_matches_last_turn_aggregate`：C10 三轮 delivered/clarification/bound_but_dropped；tally 按轮 `{bound_but_dropped:1, clarification:1, delivered:1}`；`execution_state_aggregate=bound_but_dropped`（`last_turn`）；turn_rows[-1] 与 aggregate 同态。批 JSON 未改。`test_acceptance_execution_state` 16 passed |
| `R-20260815-08` | Round 3 轨道 B 开批前实测 | `EVAL_ONLY` | 验收台改为从 `/api/health` 取服务端的 users 目录（或在自身 env 与服务端不一致时**响亮失败**）后：故意把 `FORESIGHT_USERS_DIR` 指向一个存在但错误的目录跑一次，产物应报错或显式标注不一致，而**不是**整批静默落 `undetermined`/`api_only` | `confirmed` | 离线负夹具：`test_users_dir_mismatch_against_health_raises`、`test_preflight_rejects_mismatched_users_dir`、`test_wrong_users_dir_does_not_emit_plausible_five_state`。错目录存在但无 episode 时 `require_episode_if_expected` 抛 `UsersDirMismatch`，`cmd_run` 返回 2 且不落盘五态；对目录读到 `no_hash`。health 增 `runtime.users_dir`（未部署 8792 时 env 不一致仍由 missing-episode 门拦住）。`test_acceptance_execution_state` + `test_acceptance_board` 覆盖 |
| `R-20260815-06` | Round 2 轨道 B（M2 F-002） | `NO_SYSTEM_FIX` | 生产代码身份属用户裁决；裁决后 `loaded_code_root` 对应目录 `git status --porcelain` 为空，且 `/api/health` 的 `source_revision` 与该目录 `git log -1` 一致 | `confirmed` | 8792 蓝绿切到干净快照 `~/.finance-runtime/finance-workspace-cb09f895734a`（main `cb09f895`，含 #11/#12/#13/#10）。`git -C loaded_code_root status --porcelain` 空；`/api/health` `source_revision=cb09f895734a65a38ae23f04d940f18ece2959fd` 与该目录 `git log -1` 一致；`source_dirty=false`；`code_matches_repo=true`。启动器 `WORKBENCH_REPO_ROOT` 改指 runtime 软链（数据根仍 `FINANCE_WS`）。旧脏树 `07af9160a677`（**23 dirty @2026-08-15 03:0x**，其中 20 M + 3 未跟踪）未改、可回滚。pid 30091 |

> **该脏树计数随时间变化，引用时必须带测量时刻**（轨道 B Round 3 开工核对）：
> 轨道 B Round 2 报告记的是 **20 @02:13**（17 M + 3 未跟踪），本行记的是 **23 @03:0x**。
> 两者都对——差额是 `episode_protocol.py` / `test_episode_protocol.py` /
> `test_episode_verifier.py` 三个文件在 **08-15 02:17** 被改动（轨道 A 面）。
> 不带时刻地引用其中任一个数字，会被后来人读成两轨之一算错了。
> 附带一条时序事实：轨道 B Round 2 的 B′ 补跑（02:13:19–02:15:52）**早于**这三个
> 改动，故那批读数不受影响。
| `R-20260815-05` | Round 2 轨道 B 任务 3（源自 `R-20260804-02` refuted） | `EVAL_ONLY` | 08-03 那份真 rollout（`sha256=62385ee5…b316a7`）重过归一化器后 `function_call_output` 归入 `observe`；`unmapped` 由 264 降至**声明目标 ≤60**；新增一条真产物形状回归夹具 | `confirmed` | 实测 `unmapped 264 → 53`（≤60 ✅）；step 分布 `synthesize=127 / tool=42 / observe=42 / unmapped=53`，**tool 与 observe 恰好配平**；首个工具结果 `custom_tool_call_output` 落 `observe` ✅ 且 `source_event_type` 为语义类型而非信封名。剩余 53 中 43 个是 `token_count`（遥测，非控制面步骤，按契约正确保持 unmapped），其余为 `session_meta`/`task_started`/`task_complete`/`world_state`/`turn_context`/`inter_agent_communication_metadata`/`sub_agent_activity` —— **给这批补词表是另一个变量，本 PR 刻意不捆绑**。回归夹具 `test_real_rollout_envelope_shape_maps_instead_of_falling_to_unmapped`，`test_normalize_harness_trace` 31 passed |
| `R-20260815-01` | 标准 M1 分诊 F-002（Round 1 轨道 B） | `EVAL_ONLY` | 重放 19 个 run 目录后 `evidence_bound` 扩为三元组 + turn 级 `execution_state`：B4 读作 `retrieved=125,bound=0`、B3 读作 `retrieved=0,bound=0`、C2-C10 读作 `not_run`，三者不再同码 | `confirmed` | 用真实的 19 个 run 目录（非夹具）重放 `20260813T1810Z-qc28-full.json` 逐条自证：B4 `retrieved=125,bound=0` ✅；B3 `retrieved=0,bound=0` ✅；C2-C10 九题全 `not_run` ✅；三者落在 `retrieved_unsynthesized` / `no_evidence` / `not_run` **三个互不相同的值** ✅。五种状态各至少命中一例（delivered 11 / not_run 9 / bound_but_dropped 3 / retrieved_unsynthesized 3 / no_evidence 2）。实现在 `intelligence/eval/acceptance.py`，11 条新单测 + 既有 acceptance 套件 127 passed |
| `R-20260815-02` | 标准 M1 分诊 F-002（Round 1 轨道 B） | `EVAL_ONLY` | `status=error` 且 `trace_steps=0` 的 turn 不进入任何质量分母；同产物重算后 C 组分母由 10 降为 1（仅 C1） | `confirmed` | 同次重放：计入分母的 C 组题恰为 `['C1-future-date-no-data']` ✅。`summarize_execution_states()` 把 `quality_denominator` 与 `excluded_from_denominator`（逐题列名）写进 run 产物本身，剔除留痕 |
| `R-20260815-07` | Round 2 轨道 B（M2 F-001） | `EVAL_ONLY` | `bound_but_dropped` 细分出 `gap_zeroed`（有哈希且带 gap）与 `no_hash`（真缺口）后：重放 B1/B3 落 `gap_zeroed`；B7 同一 turn 内 `direct_answer`（0 哈希真缺口）与 `evidence_boundary`（13 哈希滑档）分别可见 | `confirmed` | 三个冻结 run 夹具逐字自证：B1@RunB → `gap_zeroed`（slots `gap_zeroed`/`gap_zeroed`/`no_hash`）✅；B3@RunB → `gap_zeroed`（三格全 `gap_zeroed`）✅；B7@RunA → `direct_answer=no_hash` 与 `evidence_boundary=gap_zeroed` **同一 turn 内分别可见** ✅。干净基线批 `20260814T1926Z-r3-clean-baseline`（`sha256=b712bd2e…d8d350`）另贡献 6 个 `no_hash` 真缺口格（A4 `evidence_boundary`、C6 `direct_answer`+`evidence_boundary`、C9 `chain_mapping`、C10-t3 `direct_answer`+`evidence_boundary`；勘误 E-r3-2，原稿漏计 C10 两格），**该批 `gap_zeroed` 出现 0 次**——R-001 部署后该形状未在本窗口再现，故 `gap_zeroed` 一侧仅由冻结夹具覆盖，未冒充有 live 样本。15 条单测绿 |
| `R-20260804-01` | 收口审计 §修复1 | `EVAL_ONLY` | 左短右长且左为前缀时 `compare_sequences` 不再抛 `IndexError`，返回 `equivalent_before_divergence`，evidence 含 `continues_on` | `confirmed` | `test_compare_sequences_survives_prefix_on_either_side`；两种传参顺序均返回 `synthesize @ ordinal=3` |
| `R-20260804-02` | 收口审计 §修复2 | `EVAL_ONLY` | 真 Codex rollout 中 `function_call_output` 归入 `observe`，与 workbench 的 `validate→observe` 对齐；第一个工具结果处不再出现**词表性**分叉 | `refuted` | 真 rollout `sha256=62385ee5…b316a7` 过 `normalize_harness_trace`：264/264 `unmapped`，无 `observe`/`tool`；三种 `--kind` 传法一致。`_codex_mapping` 读 `item.type`，真产物语义类型在 `payload.type`，四份跨月真 rollout 的 `item` 键出现次数均为 0。详见 §2026-08-15 Round 1 开工前回填 |
| `R-20260804-03` | 收口审计 §修复4 | `EVAL_ONLY` | 归一化产物能**独立**复现审计表第三列，不必回原始 receipt | `confirmed` | 重跑历史收据，5/5 `finish` 事件带 `status` + `stop_reason`，与 arm 级逐条对齐（`ruihuatai-valuation` 的已知不一致除外） |
| `R-20260804-04` | 收口审计 §修复A | `HARNESS_FIX` | 新 run 中仅 `headless_timeout` 的 case **不再**出现 `runtime_invalid_actions:N` | `confirmed` | `intelligence/eval/measurements/2026-08-04-budget-calibration/b-floor-ablation.json`：`ruihuatai-valuation`、`weekly-market-cause` 的 `runtime_result.payload.issues=["headless_timeout"]`，同题 `protocol_issues=[]` |
| `R-20260804-05` | 收口审计 §修复B | `HARNESS_FIX` | 新 benchmark artifact 的 `diagnostics.events[0].kind == "task"` 且 `sequence == 1`；其 payload 只有 `task_frame_hash`；题面不出现在 `events` 内 | `confirmed` | 跑真 benchmark CLI（合成 runtime，真实序列化路径）：`{"kind":"task","sequence":1,"payload":{"task_frame_hash":"432d9856…"}}`，题面确认不在 `events` 内。两条发射路径（`codex_headless_runtime:903`、`agent_episode:155`）均为 sequence 1 |
| `R-20260804-06` | 收口审计 §修复C | `EVAL_ONLY` | 新 run 若产生 `mode_decision` / `branch_*` / `finalization`，归一化后 `unmapped_count` 仍为 0，且 `mode_decision → plan` | `confirmed` | 同上收据归一化：10 事件 / **0 unmapped**，`mode_decision→plan`、`branch_started→retrieve`、`tool_request→tool`、`tool_error→observe`、`finalization→synthesize`、`finish→stop` 逐条命中 |
| `R-20260804-07` | 设计评审 G2 词表对齐 | `EVAL_ONLY` | 下一份 triage 报告的 `first_bad_step` 可与本仓 `first_divergence_step` **直接比较，无需翻译**；L1=`tool` 的 finding 在本仓可表达 | `confirmed` | `docs/verification/2026-08-04-budget-calibration.md`：`first_bad_step=stop`；三份 comparison 的 `first_divergence_step=observe/stop`，均为 `triage-l1-9` 且 `unmapped_count=0` |
| `R-20260804-08` | 设计评审 §仪器覆盖矩阵 | `HARNESS_FIX` | 补齐埋点后，`configure → intent → plan` 三步在 workbench 与 codex **两侧都非空**，`first_divergence_step` 首次具备行为含义 | `confirmed` | 两侧真实路径实测：workbench 真 turn 读 `trace.jsonl` → `configure→intent→plan→route→retrieve→synthesize→observe`；codex 跑 `CodexHeadlessRuntime.run()`（真 `_to_outcome`，仅 subprocess 用 fake stdout）→ `configure→intent→plan→tool→observe→observe→stop`。**门槛 3/3**，两侧共有由 1/9 升至 **4/9**。测试：`test_runtime_emits_configure_and_plan_landmarks_in_l1_order`、`test_turn_trace_exposes_configure_and_plan_as_their_own_l1_steps` |
| `R-20260804-09` | 标准 M2 分诊 F-001 | `HARNESS_FIX` | 显式 finalization handoff 后，瑞华泰进入 finalization 并以 `model_finish` 在 root 前结束 | `refuted` | `2026-08-04b-finalization/c-long-capped-t2.json`：事件级 `headless_protocol_rejected` / 135.555s，5 requests / 4 mailbox exchanges / 0 finalization；最后一个 in-flight `evidence_search` 无 result/error，交接未激活。wrapper 60s timeout 是静态支持的候选退出路径，非 artifact 直接读数 |
| `R-20260815-22` | 轨道 A Round 2 F-001 | `EVAL_ONLY` | ① 重放 R7-A7 冻结 FINAL_JSON 形状（`run_20260813_034211_544672`，两格 hashes+gap）经 `validate_episode_finish` 后 `caveat_slips` = 被搬运格数（2）；② 干净 finish（无 gap 或 gap 已在顶层）`caveat_slips=0` 且字段在场；③ 无哈希 gap 的拒绝路径不产生搬运计数，拒绝语义不变 | `confirmed` | `test_caveat_slips_replays_r7_a7_frozen_finish`、`test_caveat_slips_zero_on_clean_finish`、`test_caveat_slips_not_emitted_on_true_gap_reject`、`test_finish_event_exposes_caveat_slips_count`。R-001 跨组夹具：`test_r001_fixture_b5_all_slot_slip`、`test_r001_fixture_b7_mixed_true_gap_still_missing`、`test_r001_fixture_a6_all_slot_slip` |
| `R-20260815-21` | 轨道 A M1 F-001 | `DATA_CONTRACT_FIX` | 全格 `evidence_hashes`+非空 `binding.gap` 的 partial FINAL_JSON 经 `validate_episode_finish` 后，各格 `binding.gap=""`、原 gap 文本进入顶层 `gaps`；再过 `verify_episode_outcome` 这些格 `fulfilled`，issues 不再含 `required output reports gap:`。无哈希的 gap 仍被拒绝。绕过 validate 把 leftover gap 直接喂 verifier 仍 missing（判据不变） | `confirmed` | 干净基线批 `intelligence/eval/runs/20260814T1926Z-r3-clean-baseline.json`（B 分支，`sha256=b712bd2ee10fb431dba937416fb5882c6984ac65bb5421b5472f71c7ead8d350`，`generated_at=20260814T200212Z`，`revision=cb09f895`，`quality_denominator=28`）。轨道 A 独立重扫：C1 9 题 slips>0 全交付且 eb>0；C2 6 个真缺口格全 missing；C9 混合形（slips=1 + `chain_mapping` missing）同 turn。预注册原文未改。详见 `docs/verification/2026-08-15-trka-r3-r21-canary.md` §Post-batch closure 与母本 Round 3 批注 |

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
| `HARNESS_FIX` | 0 | 3 |
| `EVAL_ONLY` | 0 | 3 |

计数规则：同 `fix_type` 的 `refuted` **连续**出现才累计，中间出现一次 `confirmed`
即归零。达到 3 时下一份报告的 `fix_type_refuted_streak` 必须写明已触线，并把架构 /
`HARNESS` 层列为本次的竞争假设之一。

截至 2026-08-04：`R-20260804-09` 是本项目第一条 `HARNESS_FIX` refuted，连续 streak=1。

截至 2026-08-15：`R-20260804-02` 是本项目第一条 `EVAL_ONLY` refuted，连续 streak 曾为 1。
Round 2 轨道 B 的 `R-20260815-01/-02/-05` 与轨道 A 的 `R-20260815-22` 均为
`EVAL_ONLY` confirmed，按「中间出现一次 confirmed 即归零」规则，`EVAL_ONLY`
streak 已归零（0/3）。Round 6 批 #3 将 `R-20260815-09`（`HARNESS_FIX`）confirmed，
同规则把 `HARNESS_FIX` streak 从 1（`R-20260804-09`）归零（0/3）。

### Residual uncertainty（不是预测，是没结论的观察）

与 Open 表**分开放**：它们没有可证伪预测，不参与 streak，混进 Open 会污染命中率分母。

| 观察 | 状态 | 下一步取证 |
|---|---|---|
| `test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state` 在一次全量跑中失败，其余多次（单测 / 整文件 / 后续三次全量）均通过 | 未归因 | 连跑 5 次全量记录命中率；若可复现再定位是哪个前序文件泄漏状态。**当前不归因到 2026-08-04 的改动**——它的断言不触及任何被改的面 |
| 收据的 arm 级 `stop_reason` 与事件级 `finish.payload.stop_reason` 在 `ruihuatai-valuation` 上不一致（`semantic_repair` vs `model_finish`） | 已记入 [trace-profile.md](trace-profile.md) §2 | 无需修复，属分层语义差异；跨 harness 比较一律用事件级 |
| `route` 在 codex 侧结构性不存在（episode 不做 skill 分派，backend 由 benchmark 选定、registry 固定） | 已记入 [trace-profile.md](trace-profile.md) §8 | 无需埋点。门槛已由四步收窄为三步——把结构差异写成埋点缺口，会诱导为满足指标而制造事件 |
| 批 #3 B4 验收 `timeout`/`eb=0`/`run_id` 空，仓外 `run_20260815_182037_434217` 已 `completed` 且三格 hashed | 已记入 `docs/verification/2026-08-15-r6-clean-baseline-3.md` E-008 | R-10 不改口径。是否让验收超时后回填已存在的 run_id 属排期，本轮不修 |
| 2026-08-16 长尾 off 有稿槽 `semantic judge transient provider error`（22/26）与 G01–G05 同形；零槽 `deadline exhausted` | 已记入 [trace-profile.md](trace-profile.md) §2 | 下一份 asked + 原始异常切开 H8/H9（`R-20260816-06`）。G01–G05 无 off 基准 |

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
PRIMARY=`HARNESS/configure/task-instruction-category-non-compliance`。Round 3 开批前预注册
C1/C2/C3；Round 4 按预注册原文收口为 `confirmed`（批 `sha256=b712bd2e…`，9 题 slips
全交付，6 个真缺口格仍 missing）。它可以作为后续 Prior prediction closure 与 PRIMARY
证据引用。轨道 A 不回写 `R-20260804-02` / `R-20260804-10`。

`R-20260815-22` 来自轨道 A Round 2 标准 M1
[`docs/verification/2026-08-15-trka-r2-caveat-slips.md`](verification/2026-08-15-trka-r2-caveat-slips.md)，
PRIMARY=`HARNESS/stop/local-missing-caveat-slips-count`（EVAL_ONLY 观测洞，不改判定）。
三条离线断言均已兑现，故进 Closed；`EVAL_ONLY` refuted streak 因中间出现
`confirmed` 归零。轨道 A 不回写 B 轨行与 R-10。

`R-20260815-23` 来自轨道 A Round 4 标准 M1
[`docs/verification/2026-08-15-trka-r4-evidence-ordinals.md`](verification/2026-08-15-trka-r4-evidence-ordinals.md)，
PRIMARY=`HARNESS/configure/task-instruction-category-non-compliance`（终局契约逼模型
誊抄 16-hex `content_hash`）。离线门已绿。Round 6 批 #3 live 臂由检阅方收口
`confirmed`（hash-reject 0；修复路径 14/15 验收 eb>0；B8 不同形）。不回填 B 的 R-09
（该行已由执行方按字段在场性关闭）。

`R-20260815-24` 来自轨道 A Round 5 标准 M1
[`docs/verification/2026-08-15-trka-r5-e007-split.md`](verification/2026-08-15-trka-r5-e007-split.md)，
PRIMARY=`HARNESS/synthesize/orchestration-related-errors-category-reasoning-mismatch`
（`_marker_loss_partial_public` 删已 fulfilled 格正文并设 `gap_output_ids`，不收缩绑定）。
2026-08-15 特性分支 `fix/r24-marker-loss-binding` 已实现收缩：lost 格在
`semantic.verified` 上改为 `missing` 并清空绑定哈希。outcome 仍 `pending`，
等独立部署窗 + 下一批 live。不改 adapter 去给已删正文发引用；不改
`acceptance.py` 的 `episode_fulfilled_hashed` 口径（该字段继续读结构快照，
历史夹具 `b3-r4-batch2-episode.json` 的 efh=2 vs eb=0 保持冻结）。

`R-20260815-26` 来自 S10 Phase A 标准 M1
[`docs/verification/2026-08-15-s10-branch-activation.md`](verification/2026-08-15-s10-branch-activation.md)，
outcome=`ROOT_CAUSE_NOT_CONFIRMED`（冻结集调用率 1/5，原「零调用」未复现；三条机制未分出全班 PRIMARY）。
本行只锁定评测夹具。报告里的 `R-027`/`R-028` 是 Phase B 候选，未进 Open——未确认根因不得把 ROUTING / SYSTEM_PROMPT 写成已确认预测。

`R-20260815-25` 来自同一份 Round 5 报告的并行缺陷 F-003（`tool_exception` 吞 `detail`），
`HARNESS/observe/context-handling-error-category-context-handling-failures`。
离线门已绿；批 #3 数据层健康，零 `tool_exception` 样本，outcome 保持 `pending`（unobserved）。
本轨只出数，不改该行。

`R-20260815-09` / `R-20260815-10` 来自轨道 B Round 3 标准 M1
[`docs/verification/2026-08-15-trkb-r3-clean-baseline.md`](verification/2026-08-15-trkb-r3-clean-baseline.md)，
Round 6 批 #3 按预注册判据收口为 `confirmed`（报告
[`docs/verification/2026-08-15-r6-clean-baseline-3.md`](verification/2026-08-15-r6-clean-baseline-3.md)）。
R-09 用字段在场性 + B8 非空拒收码；R-10 用三批 `evidence_bound>0` 交付率。
本轨不回写 R-23 / R-24 / R-25。

`R-20260816-01..05` 来自标准 M1 分诊
[`docs/verification/2026-08-16-outlook-verification-budget-regression.md`](verification/2026-08-16-outlook-verification-budget-regression.md)，
outcome=`ROOT_CAUSE_NOT_CONFIRMED`，PRIMARY=`UNCLEAR/synthesize/DEPTH_INSUFFICIENT(D4)`。
它可以作为后续 Prior prediction closure 引用，但不能当作已确认单一刀（#72/#75/#79）的 PRIMARY。
#84（`21dbf6c1`）落地 R-01 埋点与 R-04 夹具；R-04 已 Closed。R-01 仍等带 `timeout_asked` 的同形 live run。

`R-20260816-05` 在
[`docs/verification/2026-08-16-outlook-off-arm-typology-judge-case.md`](verification/2026-08-16-outlook-off-arm-typology-judge-case.md)
按 45 槽三元组收口为 `confirmed`。同报告立 R-06（judge `timeout_asked`）、R-07
（书面豁免：禁无实测抬 T/30）、R-08（G0x 无 off 基准）、R-09（60s reserve
杠杆须 08-08 实测）。R-02 因未动预算保持 pending。R-03 45 槽已否证充分条件，
单变量仍 pending。8795 identity 收齐后 R-01/R-06 仍 pending（形状未再现 / judge 字段仍缺）。

首次真正的分诊在回填本账本时，应把这一批视为 `no prior triage report` 的历史遗留
条目，只做 outcome 回填，不继承其归因。

对应审计记录：
- [docs/verification/2026-08-03-cross-harness-shared-layer-audit.md](verification/2026-08-03-cross-harness-shared-layer-audit.md)
- [docs/verification/2026-08-04-improvement-loop-design-review.md](verification/2026-08-04-improvement-loop-design-review.md)
- [docs/trace-profile.md](trace-profile.md) §2 字段陷阱、§6 投影契约、§8 仪器覆盖矩阵
- commit `09657e2a`

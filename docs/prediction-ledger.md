# Prediction Ledger: finance-workspace-private

- last_updated: 2026-08-21（W1 `R-20260821-07` + W2 `R-20260821-08` + W3 `R-20260821-09` 离线已绿立案。live 未部署，不得 confirmed。P1 Q1/Q3 仍 pending）
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
| `R-20260816-10` | 2026-08-16 judge transient R-06 T3 F-001 | `HARNESS_FIX` | 处置落地后，下一份 draft>0 的 8795 同形重放：judge 首轮 `timeout_asked` ≥20；H9 形 TimeoutError 率相对 `docs/verification/2026-08-16-judge-transient-r06.md` 11/11 下降 | 只验 standard 窗地板 50（08-20 起首轮=50，不再锁 25）；工具批仍 70、synthesis reserve 仍 20、deep 窗仍 50。PR 若含 T/`_REPAIR_SECONDS_CAP`/档位上调且无 08-08 式实测 → 改记 R-07 refuted | `pending` |
| `R-20260816-07` | 2026-08-16 有稿 judge 案豁免 | `NO_SYSTEM_FIX` | 本窗关闭后下一份自称「outlook 预算回归修复」的 PR diff **不含** T / `_REPAIR_SECONDS_CAP` / 生产档位上调 | 出现上调且无 08-08 式延迟实测 + 全路由影响面 → refuted | `pending` |
| `R-20260816-08` | 2026-08-16 有稿 judge 案 F-003 | `EVAL_ONLY` | 若把 G01–G05 degraded 写入长尾开关账，必须先有同题 off 臂；在此之前收据只写「heading 缺席 + 路由仍 theme-research」 | 无 off 基准却写开关因果 → 本预测 refuted | `pending` |
| `R-20260816-09` | 2026-08-16 有稿 judge 案 F-004 | `HARNESS_FIX` | 若动 `_BALANCED_SYNTHESIS_RESERVE` / 非 finalize `stage_timeout`：改完后非 finalize `timeout_asked` 不再系统等于 `remaining−60`；须附 2026-08-08 式延迟实测 + 全路由影响面 | 只调 T/30 当修复 → 本预测不兑现（T 不改 `min(90,T−40)`）。观点题对照不得变慢超 5pp | `pending` |
| `R-20260816-13` | 宽题取证饿死 M1（`run_20260816_205439_732198`，2026-08-16 20:54 生产首发实测） | `EVAL_ONLY` | 8795 含工具批埋点 tip 重放：每发 `tool_request` 带 `batch_grant_asked`/`stage_timeout_granted`/`episode_remaining_at_dispatch`/`remaining_slots_at_dispatch`/`turn_elapsed_at_dispatch`。**deep 自然完成值合计 > standard 总窗 → H-a**（架构支，不调参）；**evidence_search 自然时长 ≤10s 且失败仅与 dispatch 授予≤0 / slot 耗尽相关 → H-c**（顺序/信号）。缺字段不得结案。工具批读数对 `R-20260816-11` 冻结样本是**移交证据**（其独立 PRIMARY 候选之一），eb 结案权在 R-11，本行不代结 | 判定不得混入 R-10 判据（同侧车不同读数）；`tool_timeout`（时间闸 `episode_tool_batch.py` L355-366）与 `tool_budget_exhausted`（次数闸 L340-352）分开计 | `pending` |
| `R-20260816-14` | 宽题取证饿死案绊线 | `NO_SYSTEM_FIX` | 下一份自称修「宽题取证饿死」的 PR diff **不含** `ASK_TOOL_BATCH_TIMEOUT` / `tool_batch_seconds` / T / slot 上限 / 档位上调 | 出现上调且无 08-08 式延迟实测 + 全路由影响面 → refuted | `pending` |
| `R-20260816-15` | 2026-08-16 十题窗判断槽 0-hash M2 F-001 | `DATA_CONTRACT_FIX` | 用冻结三对离线重算：`_bindings_rate` 把 `grounding_mode=model_reasoning` 槽移出分母（或另报 `judgment_hash_rate`）后，`post:L01:r3` / `L03:r2` / `L05:r2` 的 evidence 槽 eb=1.00，窗级 `evidence_bound_pp` 回到 ±5pp 内；生产 episode / #72 / T / 30 / 档位不变 | 夹具=三对 `continuous-episode.json`；单测钉「判断槽 0-hash + 旁槽 hashed → 分层 eb=1.0、旧口径=0.5」。出现 T/30/档位 diff → 改记 R-07 refuted | `pending` |
| `R-20260818-01` | 2026-08-18 KC 验收 M1 F-001 | `EVAL_ONLY` | `_extract_numbers` 后补中文数量级归一（万亿/亿/万 → 同量纲候选，只加候选不改原值）；用**同一份** `20260818T051630Z.json` 重跑 board 后，B7 两条 fact 由 FAIL 转 PASS，且 A1（原生「亿」表述）保持 PASS | 单测钉「2.96万亿 命中 29569.03±1%」与「2.96亿 不得命中 29569.03」；08-15 / 08-18 两份 artifact 各跑一次，除 B7 外真值列逐题不变 | **`confirmed`** |
| `R-20260818-02` | 2026-08-18 KC 验收 M1 F-002 | `EVAL_ONLY` | 给 9 道无日期锚题补日期（拼进 query 或 runner 显式下达 `date`，两种都不改产品）后重跑：至少 A3 的 `close=12.11` 出现在答案（A6 已证同数据可得） | 冻结题面 sha256，改动前后逐字 diff 入台账；带日期的 19 题真值不得变差 | **`partially_confirmed`** |
| `R-20260818-03` | 2026-08-18 KC 验收 M1 F-003 | `HARNESS_FIX` | `episode_tool_batch` 的 `tool_result` 落盘增加 `payload_field_names`（非空字符串数组）与 `payload_sha256`，不落正文；补后可对每条 fact 失败判定期望字段名是否出现在工具返回字段集 | 断言字段名列表非空且不含正文、无 `/Users/`；artifact 体积增幅 <5% | **`partially_confirmed`** |
| `R-20260818-04` | 2026-08-18 KC 验收 M1 F-001 绊线 | `NO_SYSTEM_FIX` | 在 `R-20260818-01` 落地前，下一份自称修「B7 回归」的 PR diff **不含**产品侧（`ask*.py` / `episode*.py`）改动 | 出现产品侧改动且无新证据 → refuted | **`held`** |
| `R-20260816-16` | 中转全站中断 M1（`run_20260816_221823_213588`） | `HARNESS_FIX` | 8792 provider 链长度 ≥2（GLM Coding Plan + 中转）后：中转 5xx 时同题重跑 `usage.tool_calls>0`、可见 `[0]→[1]` 或直接走健康 `[0]`，且不再出现同一死 provider 重试满 16 次 | 启动器含 `FORESIGHT_BUILTIN_*` 三件套；live 单次不独立结案。draft 终值仍 0 不得写 confirmed | `pending` |
| `R-20260816-17` | 同上 F-002 | `DATA_CONTRACT_FIX` | 成因行从 `ASK_DEGRADED_FALLBACK` 拆出后：`repair_model_unavailable` 或 `llm.used=false` 的重渲染首句含「模型服务不可用」且不含「现有证据不足」 | 单测钉三零形状；开关 off 时其余文案逐字节不变 | `pending` |
| `R-20260816-18` | 同上 | `DATA_CONTRACT_FIX` | 三份 artifact status 同一投影后，不存在 `outcome=failed ∧ run.json=completed` | 用 2026-08-16 当日 run 目录作离线夹具 | `pending` |
| `R-20260816-19` | 同上 F-003 | `EVAL_ONLY` | `evaluate_marker_coverage` 对缺口模板整体 `uncheckable` 后，与 `structural_verifier` 不再因「反证」子串冲突 | 并入 `R-20260815-03` 夹具；正常 counterpoint 反向不变 | `pending` |
| `R-20260816-20` | 同上 F-004 | `DATA_CONTRACT_FIX` | 补齐 `_OUTPUT_DESCRIPTIONS` 10 个缺项，`.get(output_id, output_id)` 改启动期校验：`chain_mapping` 不再同义反复 | 18 个 `question_type` × required outputs 无缺键；删任一键须转红 | `pending` |
| `R-20260816-21` | 原题 GLM 复跑 `run_20260816_230528_976709` | `HARNESS_FIX` | repair 窗随生效 provider 实测 p90，不再用对 terra 的 30s 常数卡 GLM；同题重跑不再两发整窗 `TimeoutError`。**禁止只把 30 调大** | 须附分档延迟实测 + 全路由影响面；触 `R-20260816-02`/`-07` 绊线即改记那些行 | `pending` |
| `R-20260816-22` | 工具层追查（`run_20260817_002958_135258`）+ **2026-08-17 用户口径裁定** | `DATA_CONTRACT_FIX` | **按数据类分档，不是放宽门槛**：① DuckDB 硬事实（行情/成交/涨停等）新鲜度**照旧从严**；② 知识库/图谱（`kb_search`/`graph_lookup`）本就不过该门，保持；③ **新增第三种情形**——数据集整体已到 floor、但**被筛子集**停在更早（`fact_mainline_sector_daily` 有到 08-14 的行，而「AI算力」最后一天是 08-07），这不是 stale 而是**该主体退出了集合**，属行业生命周期观察，必须交付而非整批作废。预测：修复后同题重跑，`mainline_sector_daily` 不再返回零证据，答案含「算力于 2026-08-07 后退出主线、其后 N 个交易日未再出现」这一可核验事实；而真正的管道陈旧（数据集整体 max < floor）仍被拒 | 判别变量是**数据集 max 与被筛子集 max 的关系**，不是放宽 floor。离线双夹具：`dataset_max ≥ floor ∧ filtered_max < floor` → 交付退出事实；`dataset_max < floor` → 仍 stale（此条必须保持红线，它是该门禁的原始设计意图）。**变异**：把两个夹具的判据合并成一个即须转红。**实现归工具层执行方**；本行只占号，A 方不改 `_structured_provider_is_stale` | `pending` |
| `R-20260816-23` | 工具层追查（同上） | `TOOL_DESCRIPTION_FIX` | 模型三次写出不存在的维度名（`strength` / `index_return_pct` / `rank`）。`dataset_field_hint()` **已存在**但未进模型可见面——按本仓「事实投递 > 提醒」模式接进 `finance_query` 工具描述后，同题 3 样本的 `FinanceQueryValidationError`(`invalid_query`) 计数降到 0 | 离线断言工具描述含各 dataset 的合法字段清单；live 用同题 3 样本对照 `invalid_query` 计数。**不得靠加 prompt 训话**——字段表是事实投递不是提醒。**实现归工具层执行方**；本行只占号 | `pending` |
| `R-20260817-01` | 同题两发 M2（`run_20260817_014724_245782` / `run_20260817_015340_618752`） | `HARNESS_FIX` | `complete()` 已返回 FINAL_JSON 后，即使 `_consume_root_seconds` 失败，first finish `carried_draft_chars>0` 或 `outcome.draft` 含阶段判断；不得再把刚写出的稿当「从没生成过」。**禁止调 T / `_REPAIR_SECONDS_CAP` / 档位** | **离线已绿**（2026-08-17）：`test_deadline_after_successful_finalize_keeps_the_just_written_draft`；`test_deadline_after_tool_turn_does_not_invent_a_draft`。**#124 已合切** 8792=`31ee58ce`。live `run_20260817_022655_519631` 首轮是 PLAN+工具调用后 `deadline_exhausted`，没有写出答案（content 无 draft），`carried_draft_chars=0` 是工具轮空稿（夹具 2 的形状），**不是** M2 有稿未结转，不得写成 refuted。第二发 `run_20260817_093755_447794` 走到 finalization，`model_turn` TimeoutError，content 空，仍无写出答案。要结案仍须同形：finalize 已返回可取出 draft 的 content（`wrote_answer`，生效解析器 `parse_finish_json`，**不是** `json.loads`）后 first finish `carried_draft_chars>0`。`legal_json` 另计。单次 live 不得 confirmed。**第三发 `run_20260817_094617_943922` 首次同形**：seq14 `model_turn.content` 1404 字符 `wrote_answer` 与 `legal_json` 双绿、`draft` 732 字符，紧随 first finish `carried_draft_chars=732` / `rejection_code=none`，公开答卷 1901 字节含阶段判断。**这是本预测的正面证据，但单次 live 不得 confirmed**；结案须再有约定次数的同形 hit 且用户另拍 | `pending` |
| `R-20260817-02` | T-D 立案（`run_20260817_094617_943922` 工具批实测）+ T-E 形状对照 | `HARNESS_FIX` | **检索档位改为按剩余预算选**（形状挂 `tools/pre-execute`）后：同批多工具场景下，剩余窗口不足时 `kb_search` 降到 BM25 档**返回部分结果**，而不是整批 `tool_timeout` + `tool_budget_exhausted` 收场；`finalization reason` 不再是 `retrieval_deadline_closed`。**判别变量是「剩余时间 → 档位」这条新链路**，不是把窗口调大 | 离线夹具：造「剩余 4s / 剩余 20s」两种预算态，断言前者走 BM25 档有结果、后者走 hybrid；**变异**——把档位选择固定成常量即须转红。⛔ **本窗禁止动手**：触 `R-20260816-07` 绊线（`WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` / `_REPAIR_SECONDS_CAP` / 档位 / `ASK_TOOL_BATCH_TIMEOUT` / `MAX_GLOBAL_TOOL_WORKERS` / `MAX_BATCH_TOOL_CALLS` 一律不许调），且 `R-20260816-21` 已点名禁止「只把数字调大」。动手需用户另拍 | `pending` |
| `R-20260820-01` | 液冷同题 M2（`run_20260820_032014_595378`，2026-08-20 凌晨生产实测）→ 本轮已实现 | `HARNESS_FIX` | `resume()` 的截止路径不得再丢掉修复轮**刚写出**的合法 FINAL_JSON。同形液冷重放（首轮空稿 + 修复轮写出可过 `validate_episode_finish` 的稿 + 预算随即耗尽）：last finish `carried_draft_chars>0` 且 `outcome.draft` 非空；公开 `gate_receipt` 不再四格全 `missing_required_output`，`judge_status != unavailable`（有稿才测得到独立判官，`correlated_judge` 应为 `false`）。**禁止调 T / `_REPAIR_SECONDS_CAP` / 档位**（`R-20260816-07` 绊线） | **离线已绿**（2026-08-20）：`intelligence/tests/test_repair_carry_just_written_finish.py` 三条——夹具自洽（seq23 的稿在自己的 33 条证据下过校验器，draft=814、四格 bindings 全绑）、截止路径结转刚写出的稿、修复轮没写出合法稿时不许顶掉上一轮的稿。**变异**：把 `_carry_repair_finish` 的偏好改回 `previous.draft` 即转红（实测 `assert 0 == 814`）。夹具冻在 `intelligence/eval/fixtures/repair-carry-seq23-*`，**必须连 33 条证据一起冻**——缺证据集 seq23 的 `E1…E32` 序数会 `forged_hash` 被拒，测试会绿在错的分支上。**live 臂已跑一发但未同形，不计入验证**（2026-08-20，sidecar 8798 钉本分支 `f029b58a` / `dirty=false` / `code_matches_repo=true`，`run_20260820_103042_376640`，同题面）：首轮合成写出 1231 字、`carried_draft_chars=650`，**根本没进修复轮**（零 `repair_*` 事件），走的是 `run()` 侧 R-20260817-01 那条路径，本行改的两处未被执行。该发只证明两件事：① 改动不伤正常路径；② **有稿 ⇒ 公开 `correlated_judge=false`**（此发 `false`，与液冷 `null` 对照成立，佐证液冷那次是跳过路径而非判官挂了）。live 臂仍等下一批同形 case；**单次 live 不得 confirmed** | `pending` |
| `R-20260820-02` | grok 独立判官尾巴（压 prompt 后 N=5：18.9/23.4/23.6/26.2/46.7s） | `HARNESS_FIX` | 部署后下一份 draft>0 的 grok 独立判官：首轮 `timeout_asked`=50（=窗），不再是 25。窗地板仍 50；T / `_REPAIR_SECONDS_CAP` / 档位 / 工具批 / synthesis reserve **不变**。R-07 豁免证据就是该 N=5，不是再调 T | 离线：`complete_judge_attempt_seconds(DEFAULT)==50` 且 `leftover(49, DEFAULT)` 拒发、`leftover(50, DEFAULT)` 放行。live 读 `semantic_verifier.timeout_asked` 首轮；未部署不得写 confirmed。缺字段不得结案 | `pending` |
| `R-20260820-03` | 2026-08-20 五题分诊 R-1 / F-001 现象（`run_20260820_130200_500233` 等；**不是** 08-15 Open 表里的 F-001） | `DATA_CONTRACT_FIX` | 判官 registry 的 `evidence_id` 与 `evidence_ordinal_table()` 同一空间；bound 新闻卡的 `title` 进入 payload（许继/12.45 等正文不再只活在 title 里而判官看不见）。修好后 `projection_ordinal_mismatch_count=0` 且 `projection_dropped_field_chars=0` | 离线：`intelligence/tests/test_judge_evidence_projection.py`（A3 E9=07-13 非未绑定 E4；B1 容大在 E11；B4 E31 title；未绑定在前时 registry≠E1）。§6 第 7 例：冻 B4 的 evidence+bindings+draft，读**第一发** `rejected_sentence_indexes`（不是落盘 `rejected_claim_indexes`，也不是 `grounded_replay.py`），由 10 降至 ≤4 且句 16/17/22 从 issues 消失。无独立判官凭证则 `not_run`，单测绿 ≠ 本行 confirmed | `pending` |
| `R-20260820-04` | 2026-08-20 五题分诊 R-2 / F-002 传播（同上 B4；**不是** 08-15 的 F-002） | `HARNESS_FIX` | 语义 repair 若会清空全部 evidence-grounded required output，则保留修前 draft，`repair_withheld=True`，`judge_status` 仍为 `repaired`，不再三格 `missing` + 只剩「供研究参考」 | 离线已绿：`test_repair_refuses_to_wipe_every_required_output`；四处 marker-loss（含 terminal）走 `_marker_loss_or_withhold`。live 同形：B4 重放公开答案仍含判断/产业链/反证，`gap_output_ids` 不是三格全缺。未部署不得 confirmed | `pending` |
| `R-20260820-05` | 2026-08-20 五题分诊 R-3 / F-003 热度错绑（B3 `run_20260820_131823_131041`；**不是** 08-15 的 F-003） | `TOOL_DESCRIPTION_FIX` | 固态电池热度查询带题材过滤后，registry 不再混入他题材热度当本题材证据 | **本次不实施**，只占号。禁止把 `R-20260815-03` 标 refuted 来「关」本现象 | `pending` |
| `R-20260820-06` | 质量稿 P0 T1（锂矿现场 + 代码审计；非本轮标准 M1） | `HARNESS_FIX` | 模型自设 `limit=applied_limit=row_count=25` 时 observation **仍**含截断提示与实际覆盖区间；窗口 `ORDER BY` 时间维升序 + LIMIT 不得丢掉锚定日；`trace.requested_time_range.end` 等于问句日且不等于 `requested_date` | **离线已绿**：`intelligence/tests/test_finance_query_truncation.py` §7.1–7.4。T1b 选定「时间维 asc 时倒序取数、返回前翻回升序」，不是端点保底。live §7.15 无 sidecar 记 `not_run`。单测绿 ≠ confirmed | `pending` |
| `R-20260820-07` | 质量稿 P0 T2（电网/铝资讯 as_of 全滤；路由稿前置） | `HARNESS_FIX` | as_of=问句日、源只回晚于问句日的标题时，不得静默 0 条；observation 可区分「源里没有」与「被时点门滤掉」；trace.status 仍为 `future_of_cutoff` | **离线已绿**：`test_news_cutoff_disclosure.py`。选定 **T2-a**（标注后交付越界条），不选 T2-c 放开 as_of。live §7.17 无 sidecar 记 `not_run`。单测绿 ≠ confirmed。本行是路由稿合入前置 | `pending` |
| `R-20260820-08` | 质量稿 P0 T3（铝案单位；代码审计） | `DATA_CONTRACT_FIX` | `amount` 度量对外 label 带「亿」；模型写「226.41 亿」不再被判成「数字扩写」删句 | **离线已绿**：`test_amount_metric_labels_carry_unit`。`dragon_tiger_daily` / `core_stock_daily` 已是「成交额亿」，不得改成「亿亿」。live §7.16 无 sidecar 记 `not_run`。单测绿 ≠ confirmed | `pending` |
| `R-20260820-09` | 质量稿 P1 Q1（缺口声称对账） | `HARNESS_FIX` | 有 `directional_news` / 截断 `finance_query` 收据时，draft 写「未返回」不得改口；traces 完全没有资讯 capability 时才改口。判据用 capability 不是工具名 | **离线已绿**：`intelligence/tests/test_episode_answer_hygiene.py` §7.7–7.10。电网/锂矿形 `unattempted_claim_count=0`；无资讯 trace 才改口「本次未查询 directional_news」。变异：判据换成工具名 `news_search` → §7.7 会从 0 变成命中。live §7.15–7.17 未跑，单测绿 ≠ confirmed | `pending` |
| `R-20260820-10` | 质量稿 P1 Q3（铝残稿回退） | `HARNESS_FIX` | repair 塌成残句则 withhold；回退是「修前稿减去判官点名句」，不是整篇 `view(before)` | **离线已绿**：同文件 §7.11–7.14。闸门 type 含 `market_cause`；合入闸不冻 `general_finance_qa` 的 384→43 整包。减完 ≥2 句且 ≥80 字 → `minus_flagged_sentences`，否则 `whole_pre_repair`。C3 必填格全灭仍走整篇修前稿，不和 Q3 减句混用。live §7.16 未跑，不得 confirmed | `pending` |
| `R-20260820-11` | 质量稿 P2 Q2（锚定日补枪兜底） | `HARNESS_FIX` | 若 P0-T1 后 live 锂矿稿已含问句日盘面，本行记 `deferred` 不撤号；否则合成前补一枪 | **本次未实施**。live §7.15 未跑，不得把 T1 单测绿写成 Q2 已自愈 | `pending` |
| `R-20260820-12` | 问句日预取日历（asof-prefetch 第 1 刀；非本轮标准 M1） | `HARNESS_FIX` | 「锂矿…发酵到 2026-07-23」的 `information_cutoff` 为 `requested` 7/23，不是 `runtime_default` 今天；「1日至5日」区间题仍不得把起点当 cutoff | 离线：`test_asof_prefetch_dual_red.py` / `test_honesty_gates.py`。live 对照 Cursor SQL，不拿新旧店互比 | `pending` |
| `R-20260820-13` | forecast 双红个数序列（asof-prefetch 第 2 刀） | `HARNESS_FIX` | `market_forecast` 预取含问句日及前两个有数据交易日的双红个数；当日板块表 0 行写 `缺数`，不得写成 0 | 离线假库 2/1/0。live：8.19 题预取含 75→21→0 形 | `pending` |
| `R-20260820-14` | 发酵精确名+双红戳（asof-prefetch 第 3 刀） | `HARNESS_FIX` | 触发词命中且能锚定板块时，预取 `sector_name` 精确名时间轴且行上 `双红=是\|否`；禁止 `contains` 近义名；「固态电池有什么新进展」不强制窗口 | 离线：锂矿 7/23 的 4.4/628.5/11.73 → 双红=是，同日锂电池不进。live 对照 Cursor | `pending` |
| `R-20260821-03` | 成功路径稿 子单 C（预取行拿不到引用把手；Gate 1 创新药现场） | `HARNESS_FIX` | 开场预取消息每条带 `[E<n>]`，且该号 == 终局 `evidence_ordinal_table` 解析到同一 `content_hash`；模型引用后判官不再判「无 evidence_id / 发明历史行情」；认不出 hash 的条目不发号 | **离线已绿**：`test_prefetch_evidence_ordinal.py` 5 条（TDD 修前 3F/2P → 修后 5P）；宽集 381 passed，收据 `~/.finance-runtime/test-receipts/20260820T181642Z-dfc25221.json`。变异「发号顺序反转」→ 3F。live `run_20260821_021724_077535`：公开稿 894→1027 字，四段发酵弧保住，`E1` 引用 117 次（修前 0 次且模型自陈「无证据序号」），6-29/7-15/8-3/8-7 四组数与分析师侧逐位对齐。**只改呈现层，判官「数字要有出处」那条未动**。n=1 未过方差门，不得 `confirmed`。详见 `docs/verification/2026-08-21-gate1-prefetch-evidence-id.md` | `pending` |
| `R-20260820-15` | 预取满足必填能力（asof-prefetch 第 4 刀） | `HARNESS_FIX` | outcome 里未绑定、未被 strip 的预取 tool 满足 `mandatory_capabilities`；`test_stripped_evidence_cannot_satisfy_mandatory_capability` 仍红 | 离线 verifier。stripped 哈希不得记账 | `pending` |
| `R-20260821-02` | 子单 B 槽位填数（spec §6.2） | `DATA_CONTRACT_FIX` | 必填格的数字与日期改由预取行/带收据的工具行填入、模型只写格间句子后：公开稿问句日的涨幅/成交额/双红个数能在预取观察值或 traces 里**精确对上**；对不上时输出结构缺口，不得用散文圆过去。Gate 1 PCB概念题的 08-07 由 `8.71%/1295亿`（主线短名）转为 `4.74%/3432.59亿`（E1 长口径） | 离线：定向 pytest 先红后绿；变异——把槽改回自由作文必须转红。live：新题（非本 spec 正文题）走 `POST /api/conversations/{id}/messages`，比对公开稿数字 ⊆ 桌上的行 ∪ 有收据的工具行。**已跑 n=2（生产 8792@`6320b3bc` clean，2026-08-21 部署后）**：`run_20260821_164659_624916`（CXO 同题 B 臂）31/31 实质数字有出处、抽验 17 值逐位对库真；`run_20260821_165210_889002`（减肥药新题）16/16 有出处、七节点含环比逐位对库真且缺口显式声明（「缺公告级证据」）未用散文圆。两 run 判官零删句。审计脚本正负号/尾零归一化盲区已排除（-3.9/-0.23/-3.25 均在带收据行上）。详见 `docs/verification/2026-08-21-tracediff-cxo-ceiling.md` 收口章 | `confirmed` |
| `R-20260821-03` | 子单 C 预取行带 E 号 + 问句精确名优先（#288 `fix/prefetch-evidence-id`） | `DATA_CONTRACT_FIX` | ① 开场预取行带 `[E<n>]`，真话不再被判成发明历史行情；② 问句里出现且表中存在的 `sector_name` 长名优先于被 `decide_turn` 收短的 subject——预取标题与数字跟问句口径走 | 离线**已绿**：`test_prefetch_evidence_ordinal.py` 5P + `test_asof_prefetch_dual_red.py`，合计 13 passed；变异（候选改回 subject 优先）转红。live 预取层**已过**（`run_20260821_031715_726466`，sidecar `33b4ca95` dirty=true）：预取标题 `PCB概念 双红时间轴`、E1 08-07=`4.74/3432.59` 单轨。**公开稿未过**（仍 `8.71/1295`），掉在工具旁路/写稿/判官三层——那是 `R-20260821-02` 与 `-04` 的范围，本行不代结。dirty 树的 live 不得写 `confirmed`。**2026-08-21 部署后补齐 clean 树 live n=2**（8792@`6320b3bc`）：`run_20260821_164659_624916` 预取观察值 subject=`CXO概念` 精确名（decide_turn 收短被覆盖）、公开稿预取事实 08-03=262.33 对库真、E 引用全部可解析、判官零「引用不存在/发明历史行情」类 issue；`run_20260821_165210_889002` 同形（`减肥药` 08-19=-3.25 上桌）。①②两判据在干净生产树上成立，公开稿闭环同时绿（见 `-02`） | `confirmed` |
| `R-20260821-04` | Gate 1 三筛：判官整段删（`docs/verification/2026-08-21-gate1-pcb-exact-name.md` §Live 第 3 层） | `HARNESS_FIX` | 三筛判该约束为「拦输出 → 封上限」，据此预测：**模型能力越强，被判官整段删连坐的真话越多**。落地 `R-20260821-02` 的槽位后，判官对槽内数字**无删除权**，同形 run 不再出现「整段含真数字被删、活下来的是错口径句」；`judge_status=repaired` 的稿件里，预取行数字留存率上升 | **已集齐 3 个同形样本**（均生产 8792@`6320b3bc` clean、判官 `repaired`、稿内含预取行数字）：① `run_20260821_164659_624916`（CXO B 臂）零删句、31/31 数字有出处；② `run_20260821_165210_889002`（减肥药）零删句、16/16 有出处；③ `run_20260821_171744_929436`（钙钛矿换形探针）**首个「删除与槽保护共存」样本**——判官删了 6 处真违规（合成区间/引未绑卡/无据链路角色/发明阈值），但**零槽值被删**：5 个预取槽值经【预取事实】块送达、13 个工具行槽值（第 10 刀）散文原样幸存。反向证伪未触发：三样本均无槽内数字被删。原判据「模型能力越强、被连坐的真话越多」的机制在样本 ③ 中被正面拆解：连坐止步于槽边界。散文侧引未绑定卡仍会被删（样本 ③ 的 E4 两句），那是残余①的范围，不属本行——本行只押「判官对槽内数字无删除权」。审查侧判据见 `harness-reference/PLAYBOOK.md` §约束三筛 与 `harness-architecture-review` C2。详见 `docs/verification/2026-08-21-tracediff-cxo-ceiling.md` §反过拟合换形探针 | `confirmed` |
| `R-20260821-05` | 反过拟合个股探针（`docs/verification/2026-08-21-tracediff-cxo-ceiling.md` §换形探针；`run_20260821_171744_955225`） | `HARNESS_FIX`（候） | 个股形状 contract-预算失配：`company_multi_layer_evidence` 把 `market_data`+`mainline_context` 定为 mandatory，但 90s 档个股题无预取覆盖、工具轮次耗尽后 `repair_goal.unreachable_without_tools` 且 `reopen_tools=False` → 预测同档个股题将持续 `missing_mandatory_capability=market_data,mainline_context`。修复方向二选一：个股预取补这两路，或契约按预算档把 mandatory 降为 best-effort | 修复落地前：再采 ≥2 个 90s 档个股题应复现该 issue（可证伪——若不复现，说明是本题偶发路径而非契约失配）。落地后：同形 run 该 issue 归零，且 direct_assessment 不再因此路径缺失。**2026-08-21 18:52 复现完成 n=3（生产 8792@`6320b3bc` clean，同形题换股名，烧题检查 gitea/main 0 命中）**：太辰光 `run_20260821_185226_491046` 缺 `mainline_context`（market_data 在修复轮被 mandatory 压着调了——返回**市场总览快照**，市场级数字混进个股公开稿 + marker_loss 横幅，194 字残稿，**满足契约反而污染答案**）；莲花控股 `run_20260821_185229_591768` 缺 `market_data,mainline_context` 与原案全同（且**无 repair_goal**、`model_finish` 直接收稿仍记 issue——记账点在结构核验层，修复路径非必要条件）。`mainline_context` 三 run 0 调用。**偶发假设排除，归因成立：mandatory 清单与个股题形真实取证路径不匹配**。修复方向证据倾向「契约按题形降 mandatory / 单独清单」（预取补路会重演背景当正文）。正文 `docs/verification/2026-08-21-r05-stock-contract-mismatch-repro.md`。**2026-08-21 19:38 修复落地并 live 达标（#296 `00336f0d`）**：`resolve_evidence_plan` 给公司主体题形（stock_deep_dive/valuation_estimate/financial_analysis）降级 `company_current_backdrop` 计划——market_data/mainline_context 降 optional，能力经 planned 并集保留；市场主体题形由 seam ladder `ROUTED_FACTS` 钉住不动。门禁 5882P/0F + 变异×2 击杀；8792 rsync 部署（生效指纹 `16595e41ba72`=00336f0d 树；health `source_revision` 标签滞后于快照名 `6320b3bc`，以指纹为准）。同题重放太辰光/莲花控股（daily-full 未跑、数据态与 before 全同、成对照）：**issue 2/2 归零**；A 臂 before 丢失的转折日数值 after 全数在稿，市场数字转为显式「市场背景」块服务反证②（背景放大器正确用法）；B 臂满稿逐日 E 引用 + 数据异常主动声明。A 臂修复轮 1 次 market_data 调用来自 W5 issue-backfill（`NUMERIC_UNSUPPORTED→market_data` 映射，`episode_issues.py`），与 mandatory 无关——「个股数值缺证回填市场总览」是形状错配，候选观察不立案。已知边界：quick_fact 题形分不出主体（茅台多少钱 vs 涨停家数多少），未动。收据 `~/.finance-runtime/live-probe-traceability/20260821-r05-fix-verify/summary.json` | `confirmed` |
| `R-20260821-06` | 残余①散文引未绑卡（`docs/verification/2026-08-21-tracediff-cxo-ceiling.md` §换形探针发现 1；投影 spec §8 后续项「写手 binding 缺口」；E4 案 `run_20260821_171744_929436`） | `HARNESS_FIX` | 写手散文引用注册表**真有**的 E 号（E4=财联社「反式钙钛矿电池实现产业化验证」）、只是漏写 bindings 数组 → 投影只送绑定子集，判官按「引用不存在」删两句真因果。预测：凡散文引用可反解而未绑定，该引用句必被误删——删的是记账缺陷不是证据缺陷 | **2026-08-21 20:21 修复落地（#298 `59ec4294`）**：投影选集改「绑定 ∪ 正文可反解引用」（`_project_semantic_evidence` + 协议层新 `cited_evidence_ordinals()`，语法与 `_EVIDENCE_ORDINAL_RE` 同源、左界排除 PE10/1.5E8 形似 token）。纪律论证：引用即答案对依赖的显式声明，比记账数组更直接——「only answer-bound」的本意是"判官只能用答案真依赖的证据"，补送**被引用**的卡不放宽它；未引用未绑定仍不送、表外引用照旧 fail-closed。否决替代：接收时改写 bindings（draft 无结构分段、归属不可机械判定、harness 代模型伪造声明）；全部未绑定卡送判官（投影 spec C2 已否决）。D2 哨兵收在绑定子集对账，新增 `projection_cited_unbound_count` 落盘。TDD 6 钉先红后绿 + 变异×2 击杀 + 全仓 5888P/0F；冻结夹具 `pv-perovskite-e4.json`。**机制证明=原始工件重放**：E4 案 before registry 19 行无 E4 / after 20 行 E4 入表（标题原文送达判官）、cited_unbound=1、哨兵 0。8792 部署指纹 `56270d7329b69c34`=59ec4294 树。live 探针×2：钙钛矿同形（passed、新字段=0 读数正确）；莲花控股 R-05 同题（14 处 E 引用全绑定、仅删 1 句无据数值条件、无横幅——R-05 形态未回归）。诚实边界：「引了忘绑」无法按需强触发，live 未采到自然样本；前瞻观测=后续 run 若 `projection_cited_unbound_count>0`，注册表须含该卡且不得再现「引用不存在」类删句。收据 `~/.finance-runtime/live-probe-traceability/20260821-r06-prose-cited-verify/summary.json` | `confirmed` |
| `R-20260821-07` | 残余②子问题1 / spec W1（`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md` §W1；个股案 `run_20260821_171744_955225`、R-05 A 臂 `run_20260821_185226_491046`） | `HARNESS_FIX` | post-repair 判官对必需输出块只有降级权（missing+gap+标注+批评进质检段），删除权收窄到机械硬违规白名单；部分降级不挂道歉横幅，横幅只归全灭闸。预测：修复落地后，全量 run 中 marker_loss 记账与道歉横幅解耦——marker_loss>0 的 run 公开稿仍交付降级块正文；重放两案 after 残块保留。 | 离线：`test_ceiling_required_block_degrade.py` ①–⑤ + 两案重放夹具。变异：把降级改回删整格 / 去掉块级标注 → 至少一钉红。机制证明=原始工件重放（沿 #298），live 不可按需强触发。部署后自然样本（marker_loss>0 的 run）验收才可 confirmed。详见 `docs/verification/2026-08-21-w1-required-block-degrade.md` | `pending` |
| `R-20260821-08` | 封上限形状 B / spec W2（`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md`；残余②子问题2 + R-05 枚举地基） | `HARNESS_FIX` | mandatory 可满足性两级对账：contract 下发时按 KB 链路证据在场性降级 chain_mapping；运行时 unreachable_without_tools && !reopen_tools 一律降级为缺口声明。预测：结构性不可满足的必填格不再显影为 marker_loss/道歉横幅/错口径污染，显影为显式缺口声明。 | 离线 TDD：`intelligence/tests/test_mandatory_satisfiability.py`（空库题材 chain_mapping optional + 预置缺口；有暴露仍 mandatory；`unreachable && !reopen` 降缺口且 `lost_required_output_substance` 不再含该格；#296 `company_current_backdrop` / `ROUTED_FACTS` 回归；钙钛矿 run `run_20260821_171744_929436` 动态形状重放）。变异钉两条写在同文件。live：部署后同形题（KB 无链路证据的新题材，或 `unreachable && !reopen` 的修复轮）`missing_mandatory_capability` 与 chain_mapping 类 marker_loss 归零，缺口声明出现在公开稿。单次 live 不得 confirmed。 | `pending` |
| `R-20260821-09` | spec #300 W3 / 形状 D；升级 R-05「个股数值缺证回填市场总览」候选观察 | `HARNESS_FIX` | NUMERIC_UNSUPPORTED 回填目标由静态映射改锚定主体反推，解析不出 fail closed。预测：个股题修复轮不再出现市场总览数字污染。 | **离线已绿**（2026-08-21）：`plan_issue_backfill` 三钉——个股→`finance_query`、市场→`market_data`、无主体不回填；adapter 消费点同步。冻结夹具 `intelligence/tests/fixtures/w3-r05-a-numeric-backfill.json` 重放 A 臂 `run_20260821_185226_491046` 的 `subject_kind=company`，after 计划不含 `market_data`。**变异**：个股分支改回静态 `market_data` → ① 与重放钉、adapter 个股钉三红（`01c5f783` 上改已提交态，`git checkout` 后复绿）。正文 `docs/verification/2026-08-21-w3-numeric-anchor-backfill.md`。全量 5894P/0F，收据 `~/.finance-runtime/test-receipts/20260821T135845Z-a6c682e1.json`（dirty=false）。live 未部署，单测绿 ≠ confirmed | `pending` |
| `R-20260821-10` | deadline_exhausted 主稿归零路径（收口 R1 spec §W4 观测单；起点=换形双探针「预算观察」，`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md`） | `HARNESS_FIX`（候，修法另行立项） | 主稿多轮归零（`carried_draft_chars=0`）、全稿一发成于修复窗的路径可复现 n≥3；归因二选一（可证伪）：provider 暂态（超时聚集特定时段）vs 结构性预算失配（任何时段必现），判据=时段分层复现率 | **2026-08-21 22:00 复现+归因完成（观测单，零代码改动）**：近 8 日 410 run 全量扫描，`deadline_exhausted` **323/410=79%**（`model_finish` 仅 17%）；其中 `carried=0` **276 个（全部 run 的 67%）且全部走 `repair_reentry`**——「全稿成于修复窗」是常规路径非探针偶发。时段分层：按天 69–100%、按小时 0–23 全覆盖无聚集无豁免 → **暂态否证，结构性成立**。机制链：共享 deadline 下成稿轮无保留量，工具轮吃剩的残值 median 13.0s / 82%<20s（有埋点 n=39），修复窗独立新授 30–40s 反成事实主生成窗。诚实边界：对照组 `model_finish` 末轮 12–26s 也有成功——归因指「预算分配结构把成稿轮系统性压到临界之下」，非「小窗必死」；末轮输出长度未逐 run 拆。修法三候选（成稿轮 reserve／carried 门槛／修复窗正名二段生成）**须实验组对照后另行立项**，受 R-20260816-07「无实测不得抬 T」约束；R-20260816-09 的 60s reserve 讨论在案，本读数是它等的实测证据之半。正文 `docs/verification/2026-08-21-deadline-exhausted-repro.md`（含字段路径与复算命令，W5 传感器可直接复用） | `confirmed`（归因结论；修复未做不在本行） |

> `R-20260821-02` / `-04` 的 **live 臂 2026-08-21 尝试过，记 `not_run`**（不是 `refuted`）：
> 手搭 worktree sidecar 与生产环境不等价，同一道反过拟合题（钙钛矿电池→2026-08-18）
> 在**代码等于 `gitea/main` 的隔离臂**上同样失败于 `scenario_tree` 预检，故失败不可归因于本单四刀。
> 四臂对照与环境爬坑记录见 `docs/verification/2026-08-21-slot-fill-live-attempt.md`。
> 离线侧有效读数：`observation_value` 对 08-18 直接给出 `0.15 / 775.76`，与分析师第一刀逐字一致。
>
> **基线侧样本 +1（2026-08-21 午后，生产 8792@`dfc25221`，非本单代码）**：
> `run_20260821_152044_472523`（CXO概念发酵题，Cursor 直调组件对照臂 + trace diff 全程见主检出树
> `docs/verification/2026-08-21-tracediff-cxo-ceiling.md`）——judge `repaired` 把 1259 字草稿删至 437，
> 被删数字（**工具行**来源，非预取行）逐条对库全真。该 run 同时证明投影 C1–C4（`82a9fac6`）已在 main live
> （`projection_ordinal_mismatch_count=0`），残余机制为投影 spec §4/§8 留下的 A3 写手 binding 缺口
> （`evidence_alias_offset=29`，未绑卡不送判官→真引用被判不存在）。对 `-04` 记 **adjacent shape**，
> 不冒充 exact（exact 口径=预取行数字）；族内 n=2，不结案。`-02` 验收口径的「有收据的工具行」半边
> 由第 10 刀 `f0ad6cfb` 落地（离线绿；live 臂依旧待能进 episode 的 sidecar）。
>
> **`-04` 修后侧样本 +2（2026-08-21 17:00，生产 8792@`6320b3bc`，#288+#289 已合已部署）**：
> `run_20260821_164659_624916`（CXO 同题 B 臂）与 `run_20260821_165210_889002`（减肥药新题）——
> 两 run 判官均 `repaired` 且 `rejected_claim_indexes=[]`（**零删句**），槽内/工具行数字全量存活；
> 判官产出转向措辞级真实批评（「持续缩量」越界、覆盖起点 7-22 vs 注册表 7-27），以质检段呈现。
> 预测形状「槽位落地后判官对槽内数字无删除权、真数字留存率上升」成立中；
> 修后同形样本 2/3，**仍差 1 个才可 `confirmed`**，反向证伪条件未触发（无槽内数字被删案例）。

`outcome` 只能是 `pending` / `confirmed` / `refuted`。**部分验证不要写 `confirmed`。**

> `R-20260820-01` 与 `R-20260817-01` 是**同一失败家族的两条分支，不要合并计数**：
> 后者限定 `run()` 的 `complete()` 已返回 FINAL_JSON 后 `_consume_root_seconds` 失败
> （已由 `_carry_just_written_finish` 修掉）；前者是 `resume()` 一侧的对称洞——
> 修复轮七条停机路径当时一律结转 `previous.draft`，从不调那个函数。
> `R-20260817-01` 仍 `pending`，本行不代它结案。

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

### 2026-08-16 十题窗 #94 合入：回填

8792=`6cd0756e`；修前臂 8794=`437cd5e9`（已停）。收据 `docs/verification/2026-08-16-outlook-ten-question-ab.md`。F01 勘误后护栏 PARTIAL 3/4。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-11` | 开行。post 臂 eb 0.947→0.772（−17.5pp）；L01 3 槽 −33.3pp。判断槽 hashes=0、旁槽仍 bound。不复用 R-06 | `pending` | 新开 Open。分诊交接 `docs/handoffs/2026-08-16-outlook-eb-judgment-slot.md` |
| `R-20260816-10` | 本窗 post 唯一 transient asked=12.5（重试半档），不是 8795 同形 12 槽重放；无首轮 asked 独立戳 | `pending` | 保持 Open。不得用 L01 r2 偷结 |
| `R-20260816-06` | 已 Closed。本窗 H9 残留不重开 | `confirmed` | 不回写 |
| `R-20260816-07` | #94 无 T/30/档位 | `pending` | 保持 Open（绊线仍看自称预算修复的 PR） |

### 2026-08-16 R-11 M2 回填

此表冻结在判断槽 0-hash M2 归因之后。材料 = 冻结三对 + 官方 compare caveat。对齐键 `slot`+`run_id`。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-11` | PRIMARY=`HARNESS/configure/task-instruction-category-non-compliance`：#72 判断槽 `model_reasoning` × `_bindings_rate` 全槽要哈希。H1（并进 R-06 / 窗地板）REJECTED：三对 judge 已跑完，L03=`passed`，asked/exc 皆 null | `confirmed` | 从 Open 移到 Closed。报告 `docs/verification/2026-08-16-outlook-eb-judgment-slot.md`。预测原文未改 |
| `R-20260816-15` | 开行。分层 eb / 把 `model_reasoning` 移出分母 | `pending` | 新开 Open。不改 #72 / T / 30 / 档位 |
| `R-20260816-10` | 仍不是 8795 同形 12 槽；L01 r2 旁证不得偷结 | `pending` | 保持 Open |
| `R-20260816-07` | 本 PR 无 T/30/档位 | `pending` | 保持 Open |
| `R-20260816-13` / `-14` | 三对工具已返回；0-hash 在 FINAL_JSON。不代结饿死案 | `pending` | 保持 Open |
| `R-20260816-01` | 见到合成 `asked=16.11` TimeoutError，但 repair 有正文，不是空稿终态 | `pending` | 保持 Open |

### 2026-08-16 R-13 T1 合入 / T2 受阻：回填

8795=`16f2cd47` dirty=false（pid 53843，`--port 8795`）；8792 全程 `6cd0756e` 未切。
收据 `docs/verification/2026-08-16-evidence-starvation-r13.md`。T2 四槽（W01×3 + 孤儿 W04）均
`LLM 调用 HTTP 503`，零 `tool_request`。本机直探中转 chat 仍 5xx。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-13` | T1 字段离线单测绿；live 四槽无工具批，五元组未落盘。相邻 5 次成功 `evidence_search` 墙钟 32.3–58.9s（0 次 ≤10s）只作 serial-phase 旁证，不是预注册重放 | `pending` | 保持 Open。缺字段不得结案，不得用旁证写 H-a/H-c |
| `R-20260816-14` | #100 diff 无 `ASK_TOOL_BATCH_TIMEOUT` / `tool_batch_seconds` / T / slot / 档位上调 | `pending` | 绊线常在；本 PR 未触线 |
| `R-20260816-10` | 同侧车但本窗 0 次 judge 调用（首轮 503）。不得用本窗偷结 | `pending` | 保持 Open。判据不与 R-13 互混 |
| `R-20260816-15` | 未改 #72 / eb 量具 | `pending` | 保持 Open。R-11 已结，不回写 |

### 2026-08-16 R-15 离线分层重算：回填

材料 = 冻结三对 episode + 冻结 `score.json`（mtime 2026-08-16 20:19:27，未覆写）+
`intelligence/tests/test_episode_bindings_rate.py`（6 passed）。
对齐键 `slot`+`run_id`。未改 #72 / 生产 episode / T / 30 / 档位。预测原文未改。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-15` | 三对 post 分层 eb=1.00；旧口径 main42 −17.5pp → 分层 +5.3pp。±5 带未入（差 0.3pp）。「修后不降」成立。单测钉 0-hash 判断槽 → 旧 0.5 / 分层 1.0 | `pending` | 保持 Open。部分验证不得写 confirmed。收据 `docs/verification/2026-08-16-outlook-eb-r15-rescore.md` |
| `R-20260816-07` | 本 PR 只动 eval/docs，无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 保持 Open（绊线仍看自称预算修复的 PR） |
| `R-20260816-10` / `-13` / `-14` | 未触及 8795 同形重放 / 工具批五元组 / 批窗旋钮 | `pending` | 保持 Open。本行不代结 |

### 2026-08-16 R-13 T2 GLM 窗：回填

8795=`16f2cd47` dirty=false（pid 73668，GLM-5.2 Coding Plan）；8792 全程 `6cd0756e` 未切。
收据 `docs/verification/2026-08-16-evidence-starvation-r13.md`。11 槽五元组齐。
中转 503 窗已作废。未动 T / 批窗 / slot / 档位。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-13` | 11/11 五元组落盘。0 次 `evidence_search`。D01 合同档 standard（「深挖」未升档）。H-a 缺 deep 四段合计；H-c 缺该工具自然值。`asked=30` 来自 reserve=60，不是本窗调参 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-14` | 本窗无 PR 上调 `ASK_TOOL_BATCH_TIMEOUT` / `tool_batch_seconds` / T / slot / 档位 | `pending` | 绊线常在；未触线 |
| `R-20260816-10` | 本窗 0 次 judge。不得偷结 | `pending` | 保持 Open。判据不与 R-13 互混 |
| `R-20260816-15` | 未改 #72 / eb 量具 | `pending` | 保持 Open。不并案 |

### 2026-08-16 中转中断 / GLM 转移：开行

交接 `docs/handoffs/2026-08-16-provider-outage-and-glm-failover.md`。
8792 pid **90194** 链长=2；原题复跑 `run_20260816_230528_976709` 零 5xx、tools=4，draft 终值 0。
dsh 草稿曾占用 `R-06`..`11`——**那些号在 main 上已有含义，本表作废那份编号**。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-16` | 开行。启动器已加 GLM 三件套；复跑走 zhipu、llm_calls 不再是 16×5xx。draft 终值 0 / fulfilled 0/4 | `pending` | 新开 Open。部分验证不得写 confirmed |
| `R-20260816-17` / `-18` / `-19` / `-20` / `-21` | 开行。21 是 repair 窗随 p90，不是把 30 调大 | `pending` | 新开 Open。R-02/R-07 绊线仍看自称预算修复的 PR |
| `R-20260816-06` | Closed 的 judge 窗案。本事故不回写、不改原文 | `confirmed` | 不回写 |
| `R-20260816-11` | Closed 的判断槽 0-hash。本事故不占用此号 | `confirmed` | 不回写 |
| `R-20260816-07` / `-10` / `-13` / `-14` / `-15` | 未把 30 / T / 档位当本事故修复 | `pending` | 保持 Open |

### 2026-08-16 R-17 成因行：离线回填

夹具在 `intelligence/tests/test_degraded_fallback.py`。#106 已合 `main`。未部署 8792，未重渲染 22:18 / 23:05 生产 run。未动 T / 30 / 档位。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-17` | 离线：`repair_model_unavailable` 与三零（`llm_calls=0` / evidence=0 / bindings=0）首句含「模型服务不可用」且不含「现有证据不足」；开关 off 时模型正常结束的中间档逐字节不变 | `pending` | 保持 Open。部分验证不得写 confirmed。live 重渲染未做 |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |
| `R-20260816-16` / `-18` / `-19` / `-20` / `-21` | 未做链长结案 / status 投影 / 反证夹具 / 描述表 / p90 窗 | `pending` | 保持 Open |

### 2026-08-16 R-21 repair 窗随 p90：离线回填

分档延迟：8795 GLM 成功轮 n=32，p50=17.3 / **p90=34.4** / max=49.4；6/32 >30s。
中转 terra 2026-08-08 P50≈28s，08-13 收据 30s 窗 5/5。取值：openai=30，zhipu=40（p90+余量），未知=30。
`_REPAIR_SECONDS_CAP` **仍是 30.0**。#109 已合 `main`。未部署 8792。

全路由影响面：非研究题不走 `admit_repair`（0pp）；中转研究题取值不变；仅 GLM 研究题的 repair / transient retry 单笔上限 30→40。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-21` | 离线：`repair_seconds_cap_for("zhipu")>34.4` 且 `!= openai`；不传 cap 的授予仍 30；transient retry 也吃注入帽。未做同题 live 重跑 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-07` | diff **不含** `_REPAIR_SECONDS_CAP` 上调（常数仍 30.0） | `pending` | 绊线未触。窗随 p90 不是把 30 调大 |
| `R-20260816-02` | 动了 repair 授予公式的注入帽，不是 T。live 臂未跑 | `pending` | 保持 Open。条件句「若动预算」部分触发，不得写 confirmed |
| `R-20260816-16` / `-18` / `-19` / `-20` | 本 PR 不改 status 投影 / 描述表。R-17 已由 #106 合入 | `pending` | 保持 Open |

### 2026-08-16 R-20 描述表：离线回填

18 个 `QUESTION_TYPES` 默认槽位补齐后人话描述；`chain_mapping` 不再同义反复。
`.get(id, id)` 改为 `_require_output_description`，缺键在 `build_episode_context` 失败。
删 `chain_mapping` 键的夹具转红。未部署 8792。未动 T / 30 / 档位。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-20` | 离线：18 题型无缺键/同义反复；`test_missing_description_key_fails_at_build` 转红。未做 live 契约抽检 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |
| `R-20260816-16` / `-18` / `-19` | 未做链长结案 / status / 反证。R-17/#106、R-21/#109 已合 | `pending` | 保持 Open |

### 2026-08-16 R-18 status 投影：离线回填

`run.json` / `report.json` / `continuous-episode.json` 走同一函数
`status_projection.project_artifact_statuses`。合流规则：`outcome.status=failed`
压过 delivery 的 `degraded`——有缺口文案也不能把 run 写成 completed（22:18 形）。
真 degraded（artifact 无 failed outcome）仍是 transport complete / business partial。
夹具是当日两份 run 的 status 切片，不含题面/正文。未动 T / 30 / 档位。未做 live 重跑。

8792 在本 PR 之前已切到 `0df86612`（#106/#109/#110）；本行代码尚未上 8792。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-18` | 离线：22:18 切片投影后 `run=failed` / `report=blocked`；23:05 `partial` 仍可 `run=completed`；orchestrator 夹具钉 `failed∧completed` 消失。未做 live 重跑 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |
| `R-20260816-16` / `-17` / `-19` / `-20` / `-21` | 本 PR 不改链长 / 成因行 / 反证 / 描述表 / p90 窗 | `pending` | 保持 Open |

### 2026-08-16 R-19 缺口模板整篇 uncheckable：离线回填

`evaluate_marker_coverage` 认出 `_gap_answer` 整篇后，全部 required output 进
`uncheckable`，`present=[]`。22:18 形「提供主要反证」不再把 `counterpoint`
标成 present，与 `structural_verifier` missing 不再静默冲突。
真反证正文（「主要反证是…」）仍 present。未并完 R-15-03 的 6-run 同判据。
未动 T / 30 / 档位。未做 live 重跑。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-19` | 离线：22:18 形 `counterpoint` 进 uncheckable 不进 present；真反证反向仍 present；L01 缺口模板不再报 `marker_coverage=complete`，且仍不响 `uncheckable_judgment_empty`。未做 live | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260815-03` | 本 PR 只收缺口模板这一类冲突，未改成同一判据函数，6-run 夹具未齐 | `pending` | 保持 Open。不得把本行当 R-03 结案 |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |
| `R-20260816-16` / `-17` / `-18` / `-20` / `-21` | 本 PR 不改链长 / 成因行 / status 投影 / 描述表 / p90 窗 | `pending` | 保持 Open |

### 2026-08-17 同题 live（8792=`1b678ee9`）

`run_20260817_002238_100737` / user `verify-r1621-0817`。墙钟约 110s。
主路径模型轮成功（timeout_asked 69.5 / 60.0）。repair 两发仍整窗 30.0 TimeoutError。
未动 T / `_REPAIR_SECONDS_CAP` / 档位。单次 live 不得写 confirmed。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-16` | zhipu、tools=4、llm_calls=4、evidence=15；不是 16×5xx。**draft_len=0**、fulfilled 0/4 | `pending` | 保持 Open。draft 终值 0 不得写 confirmed |
| `R-20260816-17` | 首句「模型服务不可用，暂不能可靠回答」；无「现有证据不足」 | `pending` | 保持 Open。单次命中 ≠ 结案 |
| `R-20260816-18` | outcome=`partial`（stop=`repair_model_unavailable`），run=`completed`。禁止对 `failed∧completed` 未出现 | `pending` | 保持 Open。允许对出现，不是结案 |
| `R-20260816-19` | present=[]；required 四格（含 counterpoint）全部 uncheckable | `pending` | 保持 Open。单次命中 ≠ 结案。R-15-03 6-run 未做 |
| `R-20260816-20` | 本 run 未做描述表契约抽检 | `pending` | 保持 Open |
| `R-20260816-21` | **MISS**：`repair_goal.remaining_seconds=30.0`，两发 `granted_seconds=30.0` / `seconds_granted=30.0`。代码在 8792，帽没挂上组合根 | `pending` | 保持 Open。预测「不再两发整窗 TimeoutError」未兑现 |
| `R-20260816-07` | 本 live 未上调 T / `_REPAIR_SECONDS_CAP` / 档位 | `pending` | 绊线未触 |

### 2026-08-17 R-21 帽挂上 GLM 组合根：离线回填

生产装配是 `GLMModelClient → GLMAgentRuntime → ContinuousTurnAdapter`。
`GLMAgentRuntime` 没有 `_providers` / `model_client` / `_client` / `_model`，
`provider_name_from(runtime)` 返回 None → `repair_seconds_cap_for(None)=30.0`。
`provider_name_from` 改为沿 `_episode` / `client` / `_model` 走（带环检测）；
`app.py` 组合根同时按链首名注入 `repair_seconds_cap`。
`_REPAIR_SECONDS_CAP` **仍是 30.0**。#113 已合 `main`。二次 live 见下节。

首笔 grant 仍可能是 30：standard 90 − synthesis reserve 60 的剩余。那是另一件事，
本行不把 30 调大。接线后 **retry** 应吃到 zhipu 帽 40；两发整 30 TimeoutError 仍算 miss。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-21` | 离线：`provider_name_from` 能从 GLM runtime→episode→client 读到 zhipu；组合根 adapter 帽=`repair_seconds_cap_for("zhipu")`。二次 live 见下节 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-07` | diff **不含** `_REPAIR_SECONDS_CAP` 上调（常数仍 30.0） | `pending` | 绊线未触 |
| `R-20260816-02` | 仍只修帽的挂载，不是 T | `pending` | 保持 Open |
| `R-20260816-16` / `-17` / `-18` / `-19` / `-20` | 本 PR 不改链长 / 成因行 / status / 反证 / 描述表 | `pending` | 保持 Open |

### 2026-08-17 接线后同题 live（8792=`1594394c`）

`run_20260817_003329_048038` / user `verify-r21-wire-0817`。墙钟约 137s。
#113 已切：`source_revision=1594394cfbc2` / `source_dirty=false` / `code_matches_repo=true`。
未动 T / `_REPAIR_SECONDS_CAP` / 档位。单次 live 不得写 confirmed。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-21` | `repair_goal.remaining_seconds=40.0`，`repair_reentry.granted_seconds=40.0` / `timeout_asked≈39.95`。repair 轮 zhipu 成功（约 15s 墙钟），无 30.0 授予，无两发整窗 TimeoutError。stop=`repair_model_stop` | `pending` | 保持 Open。接线命中，单次 ≠ 结案 |
| `R-20260816-16` | zhipu、tools=4、llm_calls=3、evidence=39、**draft_len=675**；不是 16×5xx | `pending` | 保持 Open。draft>0 仍不得写 confirmed |
| `R-20260816-17` | 本 run 不是 `repair_model_unavailable` 形。首句是 judge 瞬时不可用的候选草稿提示，不是「模型服务不可用」缺口模板 | `pending` | 保持 Open。形状未再命中，不回写 |
| `R-20260816-18` | outcome=`partial`（stop=`repair_model_stop`），run=`completed`。禁止对 `failed∧completed` 未出现 | `pending` | 保持 Open |
| `R-20260816-19` | 本 run 不是缺口模板。`counterpoint` structural fulfilled；`chain_mapping` missing（kb_search `tool_timeout`） | `pending` | 保持 Open。缺口模板形未再命中。R-15-03 未做 |
| `R-20260816-20` | 本 run 未做描述表契约抽检 | `pending` | 保持 Open |
| `R-20260816-10` | judge `timeout_asked=12.5` / `exc_class=TimeoutError` / remaining≈171。预测要的首轮 ≥20 未兑现 | `pending` | 保持 Open。旁记，本窗不修 judge 窗 |
| `R-20260816-07` | 本 live 未上调 T / `_REPAIR_SECONDS_CAP` / 档位 | `pending` | 绊线未触 |

### 2026-08-17 contains 上线 + R-22/R-23 占号

#115 已合 `520fc0f8`，8792 已切同 SHA。`contains` ESCAPE 两字符根因在生产生效。
handoff：`docs/handoffs/2026-08-17-two-agent-collision-and-contains-escape.md`。
对方原 `-12`/`-13` 按 handoff §4 改号为本表 `-22`/`-23`，避免与宽题取证饿死的 `-13` 撞号。
实现（`_structured_provider_is_stale` 分档、`dataset_field_hint` 接模型可见面）归工具层执行方；A 方不改这两处。
18 条 `test_continuous_turn_adapter` 红：**漏改夹具**（判断槽 `basis=model_reasoning` + 强制 `market_data`），不是 R-18 投影语义。已另开 `fix/adapter-success-fixtures`：默认问句去掉「怎么看」，不再误踩判断槽。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-22` | 用户已裁定分档口径；Open 表已占号。离线实现见下节 | `pending` | 保持 Open |
| `R-20260816-23` | 原「hint 未进可见面」机制已否证，见下节 | `pending` | 保持 Open。机制更正，不得写 confirmed |
| `R-20260816-07` | #115 / 本次切窗未上调 T / `_REPAIR_SECONDS_CAP` / 档位 | `pending` | 绊线未触 |
| `R-20260816-16` / `-17` / `-18` / `-19` / `-20` / `-21` | 本窗不改链长 / 成因行 / status / 反证 / 描述表 / p90 窗 | `pending` | 保持 Open |

### 2026-08-17 R-22 主体退出 vs 管道陈旧：离线回填

`_subject_exited_universe`：`dataset_max ≥ floor ∧ served < dataset_max` → 退出并交付证据；
`dataset_max < floor` 或读数缺失 → 仍 stale。探针只在即将判 stale 且有 filter 时发。
未放宽 floor。未动 T / 30 / 档位。未做 live 重跑。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-22` | 离线：`test_subject_exited_universe.py` 双夹具 + 变异（同 served、不同 dataset_max 必须相反）+ fail-closed。未做同题 live | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-23` | 本 PR 不接 `dataset_field_hint` | `pending` | 保持 Open。实现仍归工具层 |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |

### 2026-08-17 R-23 诊断更正：metric 抄进 dimensions

原预测「`dataset_field_hint()` 未进模型可见面」**机制否证**：hint 已在
`episode_tools` 的 finance_query 描述里，列全 13 个 dataset。4/4 生产报错请求
字段全部合法，只是模型把 metric 又抄进 dimensions（当「要返回的列」）。
靠 retry hint 纠正已试过且无效（repairwin-8 连错两次）。

修复：`normalize_spec` 把「已在 metrics 声明的字段」从 dimensions 去掉。
字段只在 dimensions、未在 metrics 声明时**不动**（意图不可判定）。
夹具逐字取自四个真实报错请求。未做 live。未动 T / 30 / 档位。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-23` | 离线：`test_metric_dimension_dedupe.py` 四组 live 夹具 + 真分组键保留 + 未声明 metric 不动（含 metrics 非空变异）+ 干净 spec 无副作用。原 hint 机制否证。未做同题 live | `pending` | 保持 Open。部分验证不得写 confirmed。Open 表原预测作机制更正，不另开号 |
| `R-20260816-22` | 本 PR 不改退出/陈旧分档 | `pending` | 保持 Open |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |

### 2026-08-17 R-22/R-23 同题 live（#119 已切）

8792=`dd28e4d8` / dirty=false / match=true。user=`verify-r22-r23-0817`。
`run_20260817_014724_245782` ≈136s。run=`completed`，outcome=`partial`，
stop=`repair_model_unavailable`。tools=4 / llm=4。未动 T / 30 / 档位。
**单次 live 不得写 confirmed。**

工具层：

- R-22 hit：`finance_query` `mainline_theme_daily` + `contains` 算力 →
  trace `status=ok` `detail=dataset=mainline_theme_daily; subject_exited_universe`；
  served=`2026-08-07`，dataset_max=`2026-08-14`，rows=14。不是 stale / 零证据。
- R-23 hit：同请求 `dimensions` 含 metric `rank`/`sector_count`（亦在 `metrics`）。
  无 `not a dimension` / `invalid_query`；查询返回行。第一发 `market_daily` 干净
  spec（`index_return_pct` 只在 metrics）亦成功 20 行。
- contains ESCAPE 仍通（#115）。

交付层 miss（本窗不修）：

- repair grant=40 后 transient retry=20，两发 `TimeoutError`；draft=0。
- 答案走「模型服务不可用」缺口模板，40 条证据未绑定（R-17 形命中，不结案）。
- `kb_search` `tool_timeout`（已知 leftover）。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-22` | live：`subject_exited_universe` + 14 行退出前证据。答案层未写出退出事实（repair 死） | `pending` | 保持 Open。工具命中 ≠ 结案 |
| `R-20260816-23` | live：`rank`/`sector_count` 双边同名未炸 `invalid_query`。原 hint 机制仍否证 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-17` | 本 run 是 `repair_model_unavailable` + 缺口模板「模型服务不可用」。形命中，不结案 | `pending` | 保持 Open |
| `R-20260816-16` | zhipu 路径 tools=4，不是 16×5xx。draft=0 | `pending` | 保持 Open。draft 终值 0 不得写 confirmed |
| `R-20260816-18` | outcome=`partial`，run=`completed`。禁止对 `failed∧completed` 未出现 | `pending` | 保持 Open |
| `R-20260816-21` | repair 首授 40（帽仍在）。其后 20s retry 仍 TimeoutError。不是两发整窗 30 | `pending` | 保持 Open。帽接线 ≠ 模型按时返回 |
| `R-20260816-10` | 本 run 未进 judge（repair 先死） | `pending` | 保持 Open。旁记 kb `tool_timeout`，本窗不修 |
| `R-20260816-07` | 本 live 未上调 T / `_REPAIR_SECONDS_CAP` / 档位 | `pending` | 绊线未触 |

### 2026-08-17 同题两发 M2：有稿未结转

报告：`docs/verification/2026-08-17-r22-r23-same-question-m2.md`（`validate-report.sh` RC:0）。
A=`run_20260817_014724_245782` B=`run_20260817_015340_618752`。8792=`dd28e4d8`。
未改生产、未切窗、未动 T / 30 / 档位。

PRIMARY：首轮 `model_turn` 已有可解析 FINAL_JSON（A draft_len=897 / B=738），
同毫秒 `finish.carried_draft_chars=0`、`rejection_code=none`。
工具层分叉（theme 退出 vs sector 空行）不能预测共享空稿。
repair 两发 TimeoutError 是传播。R-22/R-23 保持 pending。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | 离线：finalize 后 consume 抛 ValueError，draft 仍在。未 live | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-22` | 第二发 `mainline_sector_daily`+`sector_name` 0 行；退出探针无 served 不触发。不是 stale 回归 | `pending` | 保持 Open。不得写成 refuted |
| `R-20260816-23` | 两发均无 `invalid_query` | `pending` | 保持 Open |
| `R-20260815-04` | 本形是「模型已返回 draft、outcome 仍 0」。`draft_source` 仍缺席 | `pending` | 保持 Open |
| `R-20260816-07` | 本分诊无 T / 30 / 档位 diff | `pending` | 绊线未触 |

### 2026-08-17 R-20260817-01 离线结转

`run()` 在 `complete()` 已返回后若 `_consume_root_seconds` 失败，先
`validate_episode_finish` 再停机：合法 FINAL_JSON 结转 draft/bindings；
工具轮 / 无效稿仍空。未调 T / `_REPAIR_SECONDS_CAP` / 档位。
**#124 已合切** 8792=`31ee58ce` / dirty=false / match=true。
R-22/R-23 保持 pending。单次 live 不得 confirmed。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | 离线两夹具绿。#124 已合切 | `pending` | 保持 Open |

### 2026-08-17 R-20260817-01 同题 live（未同形）

8792=`31ee58ce`。`run_20260817_022655_519631` ≈68s。user=`verify-r22-r23-0817`。
seq2 PLAN+7 工具调用后 first finish `deadline_exhausted` / `carried_draft_chars=0` /
`rejection_code=none`。没有 FINAL_JSON，不是 M2「有稿未结转」。
repair `previous_draft_chars=0`，`evidence_search` `tool_timeout`，
stop=`repair_deadline_exhausted`，公开答案是「现有证据不足」模板。
不得 confirmed，也不得写成 R-20260817-01 refuted。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | live 未走到 finalize JSON；空稿停机符合工具轮夹具 | `pending` | 保持 Open。不得 refuted |
| `R-20260816-22` | 本发未打到退出探针 | `pending` | 保持 Open |
| `R-20260816-23` | 本发无 `invalid_query` | `pending` | 保持 Open |
| `R-20260816-07` | 未调 T / 30 / 档位 | `pending` | 绊线未触 |

### 2026-08-17 R-20260817-01 同题第二发（合成超时，仍未同形）

8792 仍 `31ee58ce` / dirty=false / match=true。`run_20260817_093755_447794` ≈148s。
工具：`mainline_sector_daily` 0 行、`market_daily` 有行、`memory_lookup` 空、`kb_search` `tool_timeout`。
随后 `finalization`，seq12 `TimeoutError` / content 空。first finish
`deadline_exhausted` / `carried_draft_chars=0` / `rejection_code=none`。
repair 两发 TimeoutError，`previous_draft_chars=0`，stop=`repair_deadline_exhausted`。
公开答案仍是「现有证据不足」。无 `subject_exited_universe`，无 `invalid_query`。
没有 FINAL_JSON 可结转，不得 confirmed / refuted。未再切 8792，未动 T / 30 / 档位。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | 合成超时空稿，不是有稿未结转 | `pending` | 保持 Open。不得 refuted |
| `R-20260816-22` | `mainline_sector_daily` 0 行，退出探针未触发 | `pending` | 保持 Open |
| `R-20260816-23` | 无 `invalid_query` | `pending` | 保持 Open |
| `R-20260816-07` | 未调 T / 30 / 档位 | `pending` | 绊线未触 |

### 2026-08-17 R-20260817-01 同题第三发（**首次同形 hit**）

8792 仍 `31ee58ce` / dirty=false / `code_matches_repo=true` / `workers.active=0`（发起前 `/api/health` 实测）。
`run_20260817_094617_943922` 墙钟 156.6s。user=`verify-r22-r23-0817`，`skill_mode=auto`，新会话。
未切 8792、未动 T / `_REPAIR_SECONDS_CAP` / 档位。

**结转判据逐项对表**（handoff §3 的严判据，不放宽）：

| 判据 | 实测 |
|---|---|
| 某条 `model_turn.content` 能 `json.loads` 出 `draft` | ✅ seq14，1404 字符，keys=`[bindings,draft,gaps,status]`，`draft`=732 字符 |
| 紧随 first finish `carried_draft_chars>0` | ✅ seq16 `carried_draft_chars=732` |
| `rejection_code` | `none`（`stop_reason=deadline_exhausted`） |
| 交卷带稿 | ✅ `answer.md` 1901 字节，含阶段判断 / 依据 / 反方 / 升级 + 降级信号 |

工具轮：`finance_query`×2 有行（`mainline_theme_daily`、`market_daily`）、`memory_lookup` 空、
`kb_search` `tool_timeout`、`news_search` `tool_budget_exhausted`；`finalization` reason=`retrieval_deadline_closed`。
repair cycle 1 `previous_draft_chars=732` / granted 40s，seq19 出 1299 字符，
second finish `repair_model_stop`，4 个 output 槽 `basis=evidence` 全绑上。
`structural_verifier` `verified_status=partial`（`factual_grounding` / `task_coverage` 均 fulfilled）；
`semantic_verifier` `status=partial`，公开答卷带「语义核验因瞬时服务问题未完成」前缀。

⚠ **本发暴露一条判据洞（新，未修，不在本窗动手）**：seq19 的 repair content
**`json.loads` 失败**——`draft` 字符串里 `"AI算力"` / `"7月中旬即为高点…"` 的双引号未转义。
但生效解析器把它捞了出来，`outcome.draft`(612) 取自 seq19 而非 seq14 那份 732 字符的合法稿。
即 **handoff §3 写的严判据与生效解析器不同口径**：照严判据读，seq19 应判「无 FINAL_JSON」，
而产品实际出了稿。本次结论只依赖 seq14+seq16（两者都过严判据），不依赖 seq19，故 hit 成立。
但下一任若拿严判据去判 repair 轮，会把出了稿的 run 误记成空稿。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | **首次同形**：seq14 合法 FINAL_JSON + seq16 `carried_draft_chars=732`，答卷带稿 | `pending` | 保持 Open。**单次不结案**，本交接未授权 confirmed |
| `R-20260816-22` | **未打到判据点**：本发问的是 `mainline_theme_daily`（题材表）且有行，R-22 预测点名的是 `mainline_sector_daily`（板块表）。答案层出现「8月7日之后退出主线题材名单（构成要素退出，非数据陈旧）」，形状对但数据集不对 | `pending` | 保持 Open。不得据此 confirmed |
| `R-20260816-23` | 本发无 `invalid_query`（tool_error 仅 `tool_timeout` / `tool_budget_exhausted`） | `pending` | 保持 Open |
| `R-20260816-07` | 未调 T / 30 / 档位 | `pending` | 绊线未触 |

### 2026-08-17 R-20260817-02 开行：检索预算分配（立案，未动手）

同一个 run `run_20260817_094617_943922` 的工具批读数：

```
kb_search    batch_grant_asked=30.0  stage_timeout_granted=11.955  queued_ms=2.2  → tool_timeout
news_search  同一批                                                              → tool_budget_exhausted
finalization reason=retrieval_deadline_closed
```

同批还有 `finance_query`×2（有行）与 `memory_lookup`（空），先跑完把窗口吃掉。

`kb_rag` 本体实测：同进程冷调 **39.06s**，之后 **4.25s / 5.10s**（`persistent_worker` 协议）。
8792 常驻 worker 已在启动期 prewarm（`prewarm_latency_ms=38516`、`lifecycle=startup_prewarm`、
`model_load_count=1`），**冷启动不在请求路径里**。

**结论：不是检索慢，是一个 4~5 秒的工具排在 12 秒窗口的第四位。**

**已排除、不要再走的两条**（避免下一任重跑）：

1. **不是串行。** `intelligence/runtime/episode_tool_batch.py` 用 `ThreadPoolExecutor`
   同批**并发**提交，注释原文「一个批次里的工具是并发提交的，**但共享一个 deadline**」。
2. **subagent 化不解这题。** `intelligence/runtime/sub_research.py` 的 `_BranchBudgetView`
   docstring 原文：**"A non-minting child view whose consumption debits one parent ledger."**
   ——子分支**不铸新预算，消耗直接记父账本**。所以缺的**不是** subagent 机制
   （`SubResearchCoordinator` / `SubResearchWorker` / `BranchRequest` 都在），
   **缺的是不铸币的那层能铸币**：是预算模型的改动，不是拓扑的改动。
   （按 ai-agent-book ch10 判据「有没有新信息」，同批工具搬进子 Agent 也没有新信息。）

spec 侧已同步：`2026-08-15-agent-base-dsh-absorption-design.md` §4.1 给「工具批次预算」
加限定（机制在、分配策略未验证），§4.2 补第 6 条。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-02` | 开行。批次预算把 4~5 秒的工具饿死；冷启动与串行均已排除 | `pending` | 立案不动手，触 R-07 绊线 |
| `R-20260816-07` | 未调 T / 30 / 档位 / 并发度 | `pending` | 绊线未触 |
### 2026-08-17 T-C：FINAL_JSON 判据对齐（验收尺，不成案）

尺子：`intelligence/eval/finish_json_criterion.py`。夹具 `run_20260817_094617_943922` seq14 / seq19 原文。
「写出答案」=`parse_finish_json` 取出非空 draft（与产品生效解析器同一条路）。
「合法 JSON」=`json.loads` 成 object，**分开计数**。seq19 repair：写出答案=是，合法 JSON=否。
上表「没有 FINAL_JSON」的两发 live 是 content 空，两条计数都是否，结论不变。
R-20260817-01 / R-16..23 仍 pending。不切 8792。T1 hit 结论不依赖 seq19。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | 验收尺与解析器对齐。未改结转代码，未改 live 结论 | `pending` | 保持 Open。尺子落地 ≠ 结案 |

### Closed

| ID | 来源 | fix_type | verification_prediction | outcome | evidence |
|---|---|---|---|---|---|
| `R-20260816-11` | 十题窗 #94 + 检阅 #96（非 M1 开行）；M2 结案 | `EVAL_ONLY` | 下一份分诊须把「修后判断槽 `evidence_hashes=0`、旁槽仍有哈希」立为独立 PRIMARY 候选或显式 REJECT；并进 R-06、或写成 judge 窗地板副作用，即本预测 **refuted** | `confirmed` | `docs/verification/2026-08-16-outlook-eb-judgment-slot.md` E-001/E-003/E-006/E-007/E-011/E-012。PRIMARY 点名 0-hash 形状；H1 REJECTED |
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
| **`judge_status=unavailable` 把两种成因压成同一个值**：①「无稿⇒判官从未被调用」（液冷 `run_20260820_032014_595378`，`correlated_judge=null`）；②「判官被调用但 provider 报错」（`run_20260820_103042_376640`，`correlated_judge=false`，issue 为 `semantic judge transient provider error`）。两者公开 `judge_status` 完全相同，**只有 `correlated_judge` 的 null / false 能分开** | 2026-08-20 两发实测并列，未归因 | 读收据时不得只看 `judge_status` 判「判官挂没挂」。若要在字段层分开，最小埋点是给 `judge_status` 拆出 `skipped_no_draft` / `provider_error` 两个值（或加 `judge_skip_reason`）——本行只记观察，不提议改产品 |
| 批 #3 B4 验收 `timeout`/`eb=0`/`run_id` 空，仓外 `run_20260815_182037_434217` 已 `completed` 且三格 hashed | 已记入 `docs/verification/2026-08-15-r6-clean-baseline-3.md` E-008 | R-10 不改口径。是否让验收超时后回填已存在的 run_id 属排期，本轮不修 |
| 2026-08-16 长尾 off 有稿槽 `semantic judge transient provider error`（22/26）与 G01–G05 同形；零槽 `deadline exhausted` | 已记入 [trace-profile.md](trace-profile.md) §2 | 下一份 asked + 原始异常切开 H8/H9（`R-20260816-06`）。G01–G05 无 off 基准 |
| 十题窗核心集判断句机器列 0pp（诚实闸仍 uncheckable，公开正文常有「基准判断」） | 已记入 [trace-profile.md](trace-profile.md) §2 | 另案。不并进 R-11 |
| `#72` 判断槽 `model_reasoning` 后，同合同有的 run 仍给哈希（`post:L01:r1` n=35） | 已记入 [trace-profile.md](trace-profile.md) §2 | 不阻塞 R-11。要「每次必空」充分性才开 #72-only 臂（R-15 不依赖） |

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

`R-20260816-11` **开行**来自十题窗收据 #94 + 检阅 #96，当时不是四阶段分诊。
**结案**来自标准 M2 `docs/verification/2026-08-16-outlook-eb-judgment-slot.md`
（`validate-report.sh` RC=0）。PRIMARY 可引用该 M2，不可引用 #94/#96 开行文字。
`R-20260816-15` 是该 M2 的量具修复行。2026-08-16 离线分层已算（三对 post=1.00，
main42 +5.3pp 未入 ±5），outcome 仍 pending；收据
`docs/verification/2026-08-16-outlook-eb-r15-rescore.md`。该收据不是新 PRIMARY。

`R-20260816-16`..`21` 来自生产线交接
[`docs/handoffs/2026-08-16-provider-outage-and-glm-failover.md`](handoffs/2026-08-16-provider-outage-and-glm-failover.md)
（分诊全文 `/tmp/triage-run_20260816_221823.md`，`validate-report.sh` RC:0）。
本 PR 只开行与重编号。dsh 草稿曾把同一事故写成 `R-06`..`11`——那些号在本账本
已有含义（R-06/R-11 Closed），**作废那份编号**。这 6 行的 `fix_type` 与
`verification_prediction` 可进 streak；在本仓四阶段报告合入前，**不能当 PRIMARY 引用**。

`R-20260818-01`..`04` 于 2026-08-18 收口，收据见
[`docs/verification/2026-08-18-caliber-pure-ruler-28q.md`](verification/2026-08-18-caliber-pure-ruler-28q.md)
与各 Phase 收据 `docs/verification/2026-08-18-caliber-phase*.md`。

- **R-01 `confirmed`**：由**独立验收方**（非实施方）复算，不是抄实施方收据。同一份
  `20260818T051630Z` 与 `20260815T1005Z` 各重算一次，**变化题数均 = 2 且只有 B7 / C1**
  （08-18 ❌❌→✅✅；08-15 ❔❌→✅✅），A1 保持 ✅；正反单测与变异测试（注释掉万亿展开
  → B7 回到 ❌）均绿。两份复算与实施方 `/tmp` 下原始输出**逐字节相同**。
  自证：两份基线各解析 28 题、真值列非空 28。
- **R-02 `partially_confirmed`**：预测正文（A3 的 `close=12.11` 出现在答案）**兑现**；
  同行判据里的「可判分母 ≥22」**未兑现**（纯尺子实跑 18/28），该判据已按
  spec §8.1 裁决一改判为观察项。**不整条写 confirmed。**
- **R-03 `partially_confirmed`**：字段非空、脱敏（`tool_result` 载荷内绝对路径 0 处）、
  体积（184 KB vs 旧 264 KB）三项兑现；「每条 fact 失败能二选一」**只部分兑现**——
  A5 能标 retrieve、A10 能标 synthesize，但 C4/C5 走的路径**没有 episode `tool_result`**，
  仍是 unknown。
- **R-04 `held`**（不是 refuted）：#202/#203 确有产品侧改动，但本绊线的措辞只管
  「**自称修「B7 回归」**的 PR」，两张都不自称修 B7。产品侧改动的授权补记见 spec §8.1 裁决二。

> 本批留下一条方法论：**看板自带的「fact 层 0% 翻转」方差校准被实测证伪**
> （同尺子下 A4 / A6 / B6 在两份 run 间翻转）。此后 `n=1` 的真值差异不得直接写成归因；
> 本批只有 C3 因走确定性罐头短路才敢归给产品。

`R-20260821-09` 来自 spec #300 W3（形状 D 收口），不是标准四阶段分诊。
它升级 R-05 台账里「个股数值缺证回填市场总览」那条候选观察。
`fix_type` 与 `verification_prediction` 可进 streak；开行文字不能当 PRIMARY。

对应审计记录：
- [docs/verification/2026-08-03-cross-harness-shared-layer-audit.md](verification/2026-08-03-cross-harness-shared-layer-audit.md)
- [docs/verification/2026-08-04-improvement-loop-design-review.md](verification/2026-08-04-improvement-loop-design-review.md)
- [docs/trace-profile.md](trace-profile.md) §2 字段陷阱、§6 投影契约、§8 仪器覆盖矩阵
- commit `09657e2a`

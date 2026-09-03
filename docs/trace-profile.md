# Trace Profile: finance-workspace-private

- last_updated: 2026-08-23
- updated_by_run: `trace-diff-spt-fengyuan-history-20260823`（补充 empty-manual 路由覆盖、公开答案投影后假绿，
  以及 workbench coarse normalizer 看不到 repair 分叉的三条陷阱）
- 配套账本：[prediction-ledger.md](prediction-ledger.md) —— 分诊**开工第一步**先回填那里的 pending 预测，再开始新归因

## 1. 产物位置与结构

| 产物 | 路径/glob | 结构 | 关键字段 → 语义 |
|---|---|---|---|
| Acceptance run | `intelligence/eval/runs/*.json` | 一次命令一份 JSON，`cases[].turns[]` | `status` 是 turn 运行态；`degrades` 是用户可见降级；`synthesis_diagnostic` 是合成健康态；`trace_steps` 是粗粒度步骤名 |
| Workbench run | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/` | 每个 run 一个目录 | `run.json` 保存运行元数据；`report.json` 保存结构化报告；`answer.md` 是最终展示正文 |
| Runtime trace | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/trace.jsonl` | 一行一个控制面事件 | `step_id` 是原生定位符；`llm_call_ledger` 记录 provider 调用；`research_execution_budget` 记录 root 预算与工具尝试 |
| Grounded shadow | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/grounded_composer_shadow.json` | 单个 JSON | `status/failure_reason/elapsed_ms` 描述 Grounded 链终态；只在阶段产出存在时保存 brief/raw/judge 内容 |
| recall@k 标注集 | `intelligence/eval/cases/retrieval_recall_v1.jsonl` | 每行一个 case | 口径见 [retrieval-recall-at-k-contract.md](retrieval-recall-at-k-contract.md)：**生产 @k = 每通道 k**（judgments/corrections 各 k，并集可达 2k）。基线：`docs/verification/2026-08-15-recall-baseline.md` |

## 2. 已知字段陷阱

| 字段 | 直觉语义 | 实际语义 | 出处 |
|---|---|---|---|
| `turn.status=completed` | 全部质量门都通过 | 只表示 run 有可交付终态；确定性 fallback 也会 completed | `20260803T082342Z-a4-pre-budget-fix.json:42-106` |
| `elapsed_s` | 精确耗时 | Acceptance 以约 2 秒轮询观测，是量化值；phase `elapsed_ms` 也只能在同一 semantic epoch 内比较 | `intelligence/eval/acceptance.py` 与本文件 §4 |
| `synthesis_diagnostic.phases` | 所有设计阶段 | 只记录真正开始或被明确 skip 的阶段；字段缺失表示没有跑到，不可把缺失当 0ms | `ask_synthesis._record_synthesis_phase` |
| `remaining_ms_at_entry` | turn 根剩余 | Grounded phase 记录的是 `_shadow_deadline` 子链剩余；root 余量在 `research_execution_budget.retrieval.research_budget.remaining_ms` | run `run_20260803_162718_999605` |
| `phase.timeout_s / elapsed_ms` | grant 与自然耗时可直接比较 | 含义随 revision 变化：E0 grant 未执行、E1 每次 retry 各读一份、E2 整个 phase 共享硬墙；必须先按 §4 选解释器 | 6 份 phase artifact + commits `cd175a0e/8ed66020` |
| `continuous_glm` | 使用 GLM 模型 | backend 历史常量名，与模型身份无关；真实模型看 LLM ledger | handoff §1；`trace.jsonl:7` |
| LLM ledger `caller=synthesis` | 可直接区分 brief/composer/judge | 旧 ledger 只给共同 caller，不能按顺序安全反推 phase；必须用新增 phase telemetry | 2026-08-03 用户纠偏与 M1 报告 |
| case `A4-*` | Finance adapter L3=A4 | 验收题编号，与概率校准分类无关 | acceptance cases 与 finance adapter taxonomy |
| `acceptance run` 默认 base | 当前 8801 | 默认曾指向 8799；本项目真实 canary 必须显式 `--base http://127.0.0.1:8801` | handoff §6 |
| benchmark arm `stop_reason` | 运行时的终止原因 | arm 级是**事后裁决**，会被后处理覆盖；事件级 `finish.payload.stop_reason` 才是运行时观测。五题中 `ruihuatai-valuation` 两者不一致：arm=`semantic_repair`，finish 事件=`model_finish` | `e179b15c` receipt；跨 harness 控制面比较必须用事件级 |
| `runtime_invalid_actions:N` | 模型有 N 次动作违规 | **`< 2026-08-04` 的 artifact 里等于 `len(unique_issues)`**，超时/取消/进程失败都被计入。`e179b15c` 两题的 `runtime_invalid_actions:1` 实为 `headless_timeout`，真实违规 0 次。修正后只计 `unauthorized_headless_action` / `tool_call_during_finalization_recovery` / `headless_invalid_finish` | `codex_headless_runtime.count_invalid_actions`；口径对齐 `agent_episode` |
| benchmark 事件 `sequence` 从 2 起跳 | 前两个事件不存在 | `sequence=1` 的 `task` 事件（intent 地标）**被落盘白名单丢弃**，不是没埋点。`< 2026-08-04` 的 artifact 无法补出 intent；此后 `task` 保留但 payload 只留 `task_frame_hash` | `runtime_backend_benchmark._TASK_EVENT_KEEP` |
| benchmark arm `status=degraded` | runtime 没完成 | arm 级 `status` 是语义/后处理质量裁决；同一 arm 的事件级 `finish.payload.status` 可能是 `completed` 或 `partial`。预算终态分布必须两列并列，不能用 arm status 覆盖 runtime finish | `2026-08-04-budget-calibration` 四臂：20 个 arm 中 19 个为 degraded，但 finish 分布不同 |
| `finalization → finish` 间隔 | 有 timestamp 后就是自然收尾耗时 | 只有 finish 正常完成时才是自然耗时；若 finish 是 timeout，该间隔仍是 right-censored lower bound。T1 瑞华泰为 16.190s，但终态是 `headless_timeout`，只能解释为“至少 16.190s” | `2026-08-04b-finalization/c-long-capped-t1.json` |
| `finalization=0` | 模型不需要/没有尝试收尾 | 只说明已埋的 activation point 没发事件。T3 瑞华泰停在无 response 的 in-flight `evidence_search`，result/rejection 交接根本不可达；不能把 0 当作收尾耗时 0 或仪器故障 | `docs/verification/2026-08-04b-finalization.md` |
| JSON 顶层 `schema_version` | 看到该字段即可当 normalized artifact 复用 | raw runtime benchmark 也有数值 `schema_version=1`；normalized 单输入产物须同时满足字符串版本、`vocabulary/source_kind/events/input_sha256` 等 marker。只看字段存在会把 raw artifact 误拒为旧 normalized schema | `normalize_harness_trace._load_normalized_artifact`；commit `f4b8c589` |
| `unpaired_tool_requests` | `0` 表示所有 kind 都已验证配平；正数已经解释了 mailbox 超时 | 这是 `int` 或 `null` 三态指标：`runtime-benchmark` 与 Codex rollout/exec 有各自 request/response 词表，`workbench-trace` 没有逐工具词表所以必须为 `null`，不能伪装成健康零。有 `correlation_id` 时 response 只消费同 id pending；旧事件双方都无 id 才按 case FIFO 弱配对。它仍只是结构读数，不等同于 mailbox exchange 数，也不单独给出因果或迟到结果隔离证明 | `normalize_harness_trace._count_unpaired_tool_requests`；synthetic Codex 悬空调用=`1`、Workbench=`null`；T1/T2 legacy raw artifact FIFO 复算=`0/1` |
| `request_id` / normalized `correlation_id` | event 自身的唯一 id，或 response body 的业务字段 | `request_id` 是一次 headless tool 调用的 32-hex 身份：mailbox 复用 request filename stem，direct/HTTP 在执行入口生成；同一 request/result/error 共享。normalizer 将它投影为独立的 `correlation_id`，不复用每条事件自己的 `source_event_id`。Codex 侧只读共享的 `call_id/tool_call_id`，普通 event `id` 不冒充调用关联 | `headless_tool_gateway._execute_tool`；`normalize_harness_trace._event_correlation_id` |
| `remaining_*_seconds_at_entry` | 一个通用的“剩余预算” | `remaining_root_seconds_at_entry` 是 root 时钟，`remaining_research_seconds_at_entry` 是扣除 synthesis reserve 后的研究时钟；二者与同一条 `tool_request.timestamp/request_id` 一起读，禁止再压成含义不明的 `remaining_seconds_at_entry` | `headless_tool_gateway._execute_tool` |
| 真 `rollout-*.jsonl` 可被 `--kind auto` 正确识别为 `codex-rollout` | 识别成功即说明该 kind 能解析它 | **kind 判定与事件映射是两层，前者成功不蕴含后者**。真 rollout 记录形如 `{"timestamp":…,"type":"response_item","payload":{"type":"function_call_output",…}}`：顶层 `type` 只是信封名（`response_item`/`event_msg`/`turn_context`/`world_state`/`session_meta`），语义类型在 `payload.type`。而 `_codex_mapping` 只读顶层 `type` 与 `record["item"]["type"]`，**真产物根本没有 `item` 键**（2026-06-02 / 07-16 / 08-03 / 08-14 四份抽查，`item` 出现次数均为 0），于是整份 264/264 落 `unmapped`。`_source_event_type`（:365-372）同样只在 `item` 下找类型，故 `source_event_type` 一律显示信封名 | 实测 `sha256=62385ee5…b316a7`；`normalize_harness_trace.py:279-298` / `:365-372`；夹具形状见 `test_normalize_harness_trace.py:180`（`item.completed`+`item`）与 `:350`（类型在顶层），**两种夹具形状都不是真产物形状** |
| 单输入产物的 `unpaired_tool_requests=0` | 至少说明工具请求都配平了 | 这是本表上一条三态警告的**实例化现场**：一份 264/264 `unmapped` 的产物同样报 `0`——没有任何事件进入配对词表，分母就是 0。读它之前必须先读同产物的 `unmapped_count`；两者相等时该指标无意义 | 同上实测产物 |
| 同 profile 的单次 live stop/latency | 配置相同即可当稳定回归结论 | 模型路径有随机性：同 profile 从 `59da8acf` 到 T1，`weekly-market-cause` 可由 `headless_protocol_rejected / 144.7s / 4 calls` 翻为 `model_finish / 74.1s / 6 calls`。单次 stop/latency 只能作确认；`finalization` 是否出现、请求是否配对等结构契约才适合作主门 | 两份 `c_long_capped` artifact 的逐 case 事件复算 |
| episode `stop_reason=repair_model_stop` | 修复轮没产出合法 FINISH，所以交付 0 | stop 只说「无工具且未 completed」。交付 0 的区分变量是**全部** required output 的 `binding.gap` 非空（hashes 会被 verifier 丢掉）。同 stop 但至少一格 gap 为空时 eb>0（R5-A7 / live A7） | `docs/verification/2026-08-15-trka-repair-finish-gap-slip.md` |
| `semantic_status=unavailable` / 「未完成核验绑定」 | 核验预算不够或模型没走到 FINAL_JSON | 当 structural fulfilled=0 时 judge **根本不会被调用**（`_can_semantically_release_partial`）。模板文案的注释假设「没绑定」，但 R7-A7 的 episode 里 bindings 有 hashes。混槽 + judge 瞬时失败会走另一条「候选草稿」文案且 eb>0 | R7-A7 vs live A7/A10；`episode_semantic_verifier.py:503-522` |
| `finish.payload.caveat_slips` | 顶层 `gaps` 条数，或「有 caveat 就是失败」 | **本次** `validate_episode_finish` 把 hashes+gap 滑档挪到顶层 `gaps` 的格数。无滑档时为 `0` 且字段仍在场。旧 artifact 字段缺失 ≠ 0。不参与判定；查询入口是 episode `finish.payload`，本轮不改 `normalize_harness_trace`（B 轨缝） | `docs/verification/2026-08-15-trka-r2-caveat-slips.md`；健康阈值 `=0`；`≥2` 全格滑档、`=1` 混槽 |
| `finish.payload.rejection_code` / `rejection_reason` | 验收 JSON 没有拒收原因，所以判据不在产物内 | 验收台摘要可以没有；**run 目录事件流已有** `invalid_action.reason`。R-23 起 finish 亦带 `rejection_code`（无拒收=`none`）与 `rejection_reason`（无拒收=空串）。旧 artifact 字段缺失 ≠ `none`。查询入口是 episode `finish.payload`，本轮不改 normalize（B 轨缝） | B1 `run_20260815_034008_215204` seq 20；B7 `run_20260815_034828_738989` seq 17；`docs/verification/2026-08-15-trka-r4-evidence-ordinals.md` |
| 模型上下文里的 `content_hash` / `evidence_hashes` | 绑定必须抄 16-hex 哈希 | R-23 起模型上下文只留 `evidence_id`（E1..En，episode 首次出现序）；ledger `tool_result` 仍保留哈希供审计。FINAL_JSON 的字段名仍是 `evidence_hashes`，值写 `E1`/`E2` 或精确哈希；validate 解析回 `content_hash`。抄错的哈希仍 forged/truncated，**不做模糊纠正** | 同上；健康：修复轮同形不应再出现 `unknown evidence hash` |
| 判官 `evidence_registry` 的 `E4` | 就是写手草稿里的 E4 | **修复前**判官在 bound 子集上另编密排号，写手用 `evidence_ordinal_table()` 全表发放。未绑定条数=错位幅度：A3 密排 E4 = 写手 E9（07-13 -2.84），写手 E4（07-20 +10%）未绑定、不在判官表里。B3 草稿引 E37，密排表只到 E30。修好后投影必须引用 ordinal table，不得 `E{len(registry)+1}`。哨兵 `projection_ordinal_mismatch_count`（issued vs emitted 对称差），不是 `evidence_alias_offset`（未绑定条数，修好后 A3 仍=9） | 五题分诊 `run_20260820_131240_381743` 等；`docs/judge-evidence-projection-contract-spec.md`；`R-20260820-03` |
| 判官 payload 无 `title` / 据卡片 title 反驳 issue | 判官否证「注册表无公司名与金额」= 写手捏造 | **修复前**投影丢掉 `title`，新闻类正文只活在 title（detail 是「日期 媒体」）。B4 句 16/17/22 否证的「22交21直 / 许继电气 / 12.45」都在 title 里。用卡片 title 反驳判官 issue 会得出「判官在胡说」，其实是入参盲。覆盖率类审计永远发现不了——字段还在卡片上。修好后 title 进 payload，上限 `MAX_EVIDENCE_TITLE_CHARS`。哨兵 `projection_dropped_field_chars` | 同上 B4 `run_20260820_130200_500233`；`R-20260820-03` |
| 判官 registry 里有一条卡、但任何 `output_bindings.evidence_ids` 都不含它 | 投影多送了 / 数据坏了 | R-20260821-06 之后的正常形态：投影选集 = 绑定 ∪ 正文可反解引用。写手散文引了注册表真有的 E 号但漏写 bindings 数组时，该卡按写手原 E 号补送判官（`projection_cited_unbound_count` 计数），未引用且未绑定的卡仍不送。取证时先查 draft 里是否真有该 E 号引用，再谈投影异常 | E4 案 `run_20260821_171744_929436`；夹具 `pv-perovskite-e4.json` |
| `semantic_verifier.rejected_claim_indexes=[]` | 判官没拒任何句 | repair 之后该字段会被清空。B4 落盘是 `[]`，第一发 `GroundingJudgeReport.rejected_sentence_indexes` 实际是 10 句。测 H5 必须读第一发 report，不能读终态落盘，也不能跑 `grounded_replay.py`（那是 Composer 链） | 同上；spec §6 第 7 例 |
| `semantic_verifier.unattempted_claim_count>0` | 抓到模型谎称「没查到」 | 只在 traces **没有**对应 capability 收据时才 >0。电网 `directional_news` + `future_of_cutoff`、锂矿窗口覆盖锚定日但截断，修完后必须是 **0**——那两句是真话。判据字段是 capability 名（`directional_news`），不是工具名 `news_search`。`asked_date_coverage=truncated` 也不是 `missing` | `R-20260820-09`；`episode_answer_hygiene.py` |
| `semantic_verifier.repair_rollback_mode=whole_pre_repair` | 公开稿就是修前整篇 | Q3 残稿才走 withhold。减完 ≥2 句且 ≥80 字是 `minus_flagged_sentences`（不含判官点名的越界句）。C3 必填格全灭仍是整篇修前稿，**不要**和 Q3 减句混读。`repair_collapsed_to_stub` 只在语义 repair 后一句残稿时为真，preflight 数字门删条件句不算 | `R-20260820-10`；INV-7 |
| 多条 `kind=finish` | 取任意一条即可读 `caveat_slips` / `stop_reason` | 同一 episode 常有**两条** finish：第一条多是检索截止 `deadline_exhausted` 且 `slips=0`，第二条才是修复轮终态。数 slips / 判 `invalid_repair_finish` 必须取**最后一条**。批 #2 若取首条，8 个 slips>0 窗口会全部读成 0 | `20260815T0302Z-r4-clean-baseline-2` A9/B2/B3/B4/B7/C1/C6/C10；B5/C7 末条才是 `invalid_repair_finish` |
| `execution_state_tally` | 每题一个态，等于 case 终态分布 | **`< R-20260815-11` 的产物按 `turns[0]` 计**，多轮题会被首轮掩蔽（C10 三轮 delivered/clarification/bound_but_dropped，tally 计 delivered，末轮却是 bound_but_dropped）。此后 tally **按轮**，case 级另立 `execution_state_aggregate`（写死 `last_turn`），并带 `execution_state_case_tally` / `execution_state_turn_rows`。读旧产物前先看有没有 `execution_state_aggregate_rule` | `20260814T1926Z-r3-clean-baseline` C10；`summarize_execution_states` |
| `evidence_bound` | 与 episode 已 fulfilled 且带哈希的格同义 | 验收台从 `/api/runs/<id>/context` 计 `status=hit`。B3@批#2：episode `direct_assessment`/`chain_mapping` 共 11 哈希且 struct=fulfilled，context 证据列表为空 → `evidence_bound=0`。R-10 交付率仍按冻结的 `evidence_bound>0` 口径，不得事后改口；并行读 `episode_fulfilled_hashed` | `run_20260815_111907_054023` |
| `episode_fulfilled_hashed` | 可替代 `evidence_bound` 作交付率 | **并行字段**，不覆盖 eb。计数 = structural `fulfilled` ∩ `len(evidence_hashes)>0`。无 episode 时为 `null`（`api_only`）。B3@批#2：本字段=2、eb=0。旧批 JSON 无此键 ≠ 0 | `test_b3_batch2_episode_fulfilled_hashed_unequal_to_frozen_eb` |
| `window_contamination` / `data_probe` | 前置检查过了就是数据层也健康 | 身份盖戳不管数据层。R-12 起 `preflight_detail` 带 `data_probe: finance_query=ok/tool_exception/empty`；失败写死 `run_and_flag`：不中止，顶层 `window_contamination="finance_query"`、`data_probe_ok=false`。未探测时两字段为 `null`，不得当成污染。静默混批即证伪 R-12 | `acceptance.DATA_PROBE_ON_FAILURE`；`probe_finance_query_data` |
| `semantic_verifier.gap_output_ids` ∩ structural fulfilled | 结构 fulfilled 即公开答案含该格正文，或 `gap_output_ids` 空 | marker-loss 可把已 fulfilled 格写入 `gap_output_ids` 并删公开正文，**不收缩绑定**。B3#2：两格 fulfilled + `gap_output_ids=['direct_assessment','chain_mapping']` + 公开答案只剩 counterpoint → adapter 排除引用 → cites=0。读交付前先对这两栏；只读结构或只读 eb 都会误判 | `run_20260815_111907_054023`；对照 C6#2 只 gap `evidence_boundary` 仍 eb=11；`docs/verification/2026-08-15-trka-r5-e007-split.md` |
| `tool_error.error=tool_exception` 且 `detail=""` | 没有可诊断的异常信息，或「工具没抛异常」 | **`< R-20260815-25` 的产物** consume 丢掉批次层已格式化的 `TypeName: message`，`detail` 恒为空。A1#2 三连 5–12ms 即此形。R-25 起 `detail` 为类名+首行（剥路径、截断 160）；`error` 仍是分类码。旧 artifact 空串 ≠ 无异常。ProviderTrace.detail 仍是 `tool_exception`，查事件/`tool` 消息的 `detail` | A1 `run_20260815_110258_512040` seq 8/10/22；`docs/verification/2026-08-15-trka-r5-e007-split.md` |
| `continuous:adapter:verification` running + 「核验已完成」 | judge / 语义核验已经跑过 | 空 draft 时 verification 步仍会发射，随后立刻 `repair_goal`；`judge_status=unavailable` 才是「有没有调用 judge」。L01 `run_20260816_131941_597875`：verification 话术在，judge 未调用 | `docs/verification/2026-08-16-outlook-verification-budget-regression.md` E-008/E-009 |
| 首轮合成 `model_turn` 的 TimeoutError 墙钟 | 等于 `timeout_configured`（生产 75s）或 2×75 | **L01 当时** payload 没有 `timeout_asked`；修复 asked≈30、configured=75。不得把 153s 读成 2×75。#84 之后新 run 的 finalize `model_turn` 应有 `timeout_asked` / `timeout_configured` / `remaining_seconds_at_entry` | 同上 E-004/E-007；`21dbf6c1`；`repair_coordinator._REPAIR_SECONDS_CAP=30` |
| episode `model_turn.remaining_seconds_at_entry` | 与 headless 的 `remaining_*_seconds_at_entry` 同义 | 这是 continuous 主循环 `complete()` 入场时的研究窗残余（#84 / R-01）。headless 工具事件仍是 root/research 两只钟，禁止混读 | `agent_episode.py` 主循环 `ledger.add("model_turn")` |
| `uncheckable_judgment_empty` 未出现 | 第 4 层诚实闸没装上，或判断句还在 | #327 缺口模板「现有证据不足，暂不能可靠回答」会被 `answer_has_non_boundary_substance` 当成非边界正文，探测器不响（`marker_coverage=complete`，`warnings=[]`）。L01 的诚实性在 `report.status=partial` + degrade，不在 marker 警告 | `task_fulfillment.py:448-574`；R-20260816-04 |
| L04 37s `completed` | 核验路径在预算内跑完的反例 | 该 run `lane=chat`、`needs_retrieval=false`、无 `continuous-episode.json`。是 GRAPH/route 分叉，不是 verification 成功 | `run_20260816_125920_927309` |
| 长尾 off 臂 151–159s + degraded | 同一机制（核验预算撞墙） | L01 = 空 draft + `repair_model_unavailable` + 「未完成核验绑定」。L05 = draft 279 字 + `repair_model_stop` + 「候选草稿」+ `semantic judge transient provider error`。墙钟相近，机制不同 | L01 `run_20260816_131941_597875`；L05 `run_20260816_132541_309060` |
| `semantic judge transient provider error` | provider 挂了，或核验预算耗尽未调用 | 映射仍把 TimeoutError 与 5xx/连接收成同一句。R-06 已用 judge `timeout_asked`+`exc_class` 切开：8795 `02fa203e` 11 槽 asked=5.208 / TimeoutError / remaining≥170 → **H9**；0 槽 H8。standard 导出窗 20.83s、落盘 asked 是末次 5.208。处置是 standard 窗地板 50（首轮 25），见 `R-20260816-10` | `docs/verification/2026-08-16-judge-transient-r06.md`；`docs/verification/2026-08-16-outlook-off-arm-typology-judge-case.md` |
| off 臂 `judge_status=unavailable` 33/45 | 整窗没跑到 judge | 须拆三元组 `(stop_reason, draft_len, judge_status)`：10 空稿跳过、22 有稿已调用、9 无 episode、3 跑完。score 的 `judge_unavailable=33` 把前两类压扁 | `score.json` + 45 份 episode；对齐键 `slot`+`run_id` |
| 非 finalize `timeout_asked` ≈ 8–20s | provider 又慢了，或 T 不够 | `asked = remaining − _BALANCED_SYNTHESIS_RESERVE(60)`。opening 才向 reserve 借到 floor=20。finalize 用 `synthesis_timeout=remaining`。调 T 不改 `min(90, T−40)` | identity L01 r2 seq5 8.49；`glm_agent_runtime.py:47` |
| 十题窗 `evidence_bound_rate` 修后 −17.5pp | 绑得更差所以四层修复无效；或与长尾窗「诚实缺口替换」同一因果；或与 R-06 judge 窗地板同因 | 先拆判断槽 vs 旁槽。post 判断槽 `grounding_mode=model_reasoning` 时 `hashes=[]` 是**合法**终态（协议不要求该槽哈希）；`_bindings_rate` 仍按全槽哈希计 → eb 0.50。judge 可 `passed`/`repaired` 且 asked/exc 皆 null。`post:L01:r1` 同合同可有 35 hashes（#72 非充分条件）。workbench-trace compare 看不到 episode bindings（unmapped）。R-11 M2 已结；量具修复走 `R-20260816-15` | `docs/verification/2026-08-16-outlook-eb-judgment-slot.md`；`docs/verification/2026-08-16-outlook-ten-question-ab.md` |
| 分层 main42 `evidence_bound_pp` | 把 `model_reasoning` 移出分母后窗级回到 ±5pp（或约 0pp） | **+5.3pp，不是带内 0pp**。三对冻结 post 分层=1.00；pre 仍含 `O09:r1` 空 bindings（0.0）所以分层 pre=0.947。L04 必须 `None`，当成 0.0 会造假 +4.8pp。旧口径仍是 −17.5pp。R-15 保持 pending | `docs/verification/2026-08-16-outlook-eb-r15-rescore.md` |
| 验收 `expected fact X=V not observed within tolerance` | 产品没答出该事实 | **也可能是判官不认单位。** `acceptance_verdict._fact_rule` 抽裸数比容差，只补了负号方向词候选（`_decrease_signed_numbers`）与别名窗口，**没有中文数量级归一**。B7 实测：答案写「2.96万亿」，期望 `29569.03`（亿），`_extract_numbers` 抽出 `2.96` → 0 命中；按万亿归一后命中 `[2.96]` 且在 ±1% 内。读 fact 失败前先看答案里有没有换了量纲的同一个数 | `docs/verification/2026-08-18-kc-acceptance-triage.md` F-001；`acceptance_verdict.py:680-696` |
| `finance_query` observation 无截断提示 | 没截断，或模型没把 limit 开太大 | **修复前**提示条件是 `normalized.limit > applied_limit`。模型自设 `limit=25` 且 `applied=25`、`row_count=25` 时 `25>25` 为假，撞顶永不提示。修好后只看 `row_count >= applied_limit`，写 `实际覆盖` **和** `请求窗口`；T1b 倒序取数后切的是窗口前端，提示应出现「窗口前端未覆盖」，不要解读成「锚定日仍被切」。健康：撞顶必有提示 | `R-20260820-06`；`test_finance_query_truncation.py` |
| `requested_date` | 问句锚定日 | **实测恒为 today**（工具调用日）。问句窗口在 `requested_time_range={start,end}`。锂矿「7/23 当日数据未取到」要先对 `requested_time_range.end` 和覆盖区间，不要对 `requested_date` | `R-20260820-06`；`FinanceQueryAudit.requested_time_range` |
| `news_search` / `directional_news` `status=future_of_cutoff` 且 `items=0` | 源里没有新闻 | **修复前**东财标题检索只回近期，as_of=问句日后全滤成 0，observation 写成「无资讯」。修好后（T2-a）越界条目标注「晚于问句日」后仍交付，并写「不是源里没有」。W7 新闻块不泄漏未标注的越界正文。健康：全滤时 `after_cutoff_items` 非空 | `R-20260820-07`；`test_news_cutoff_disclosure.py` |
| schema `成交额=` / 模型写「亿」被判官当数字扩写 | 模型捏造了单位 | **修复前** 6 处 `amount` label 无「亿」，`market_daily.total_amount` 是「市场成交额」。模型补对单位反被删句。修好后金额类 label 带「亿」。`dragon_tiger_daily` / `core_stock_daily` 本来就是「成交额亿」，不要改成「亿亿」。投影夹具 JSON 里的旧串是冻快照，不是现役 schema | `R-20260820-08` |
| case `date` 字段 | 该日期会随查询下达产品 | **`date` 与 `query` 是分离的**，产品只看得到 `query`。28 题里 9 题 query 不含日期 → 产品按「今天」作答、对上冻结日的 `expect_facts` 必错，该组 **0/9 通过**。同实体对照：A6（带日期）答出 12.11 元，A3（不带）答出 08-17 的 14.40 元 | 同上 F-002；`acceptance_cases.json` |
| first finish `carried_draft_chars=0` + `deadline_exhausted` | 模型没写出稿，或稿被拒收 | **先读前一条 `model_turn.content`**。同题两发（`014724_245782` / `015340_618752`）finalize 已有可解析 FINAL_JSON（draft 897/738），`rejection_code=none`，同毫秒 `carried_draft_chars=0`。`remaining_seconds_at_entry` 是研究钟，不是 root 秒账本。repair 入口 `previous_draft_chars=0` 是传播 | `docs/verification/2026-08-17-r22-r23-same-question-m2.md`；`agent_episode.py:849-862` |
| `skill_mode=manual` | 只在 `selected_skill_ids` 非空时算显式工作流 | 当前 controller 的条件是 `selected_skill_ids or skill_mode == "manual"`，所以 `manual + []` 仍在细粒度路由之前强制返回 `workflow`。在 SPT×风远历史类比题上，直接 `TurnControlCore` 为 `comparison_analog`，而两个 Workbench 均降为 `general_finance_qa`，只保留 3 个 required outputs | `turn_controller.py:316-324`；`run_20260823_025334_701544` / `run_20260823_025341_392320` |
| report `business_status=complete` | 质检投影后公开答案仍完整覆盖 required outputs | 它可与「核心正文被语义质检剥到 115 字 + 15 条内部 issue 被拼入 answer.md」同时成立。必须在**投影后**重算 required-output coverage，不能用投影前 verifier 或 transport 终态代替 | `run_20260823_025341_392320/report.json` + `answer.md` |
| coarse workbench normalizer 的 `fully_equivalent` | 两个 run 的控制流真没分叉 | 当输入是公开 `trace.json`时，当前子串 mapper 把多数 `research` 类事件全压成 `retrieve`，而 `understanding/finalizing/verification/repair` 落 `unmapped`。本轮给出 mapped 12/12 且 `fully_equivalent`，但原生 continuous episode 已在 ordinal 2 出现 `tool_calls ↔ invalid finish`，且只有 8796 进 repair | `workbench-8792-vs-8796.normalized.json`；两份 `continuous-episode.json` |
| `task_type=clarify` + `status=completed` / `business_status=complete` | 研究链跑完且硬格可答 | 首轮即可在 retrieve 前停：`lane=clarify`、`retrieval_attempted=false`、`judge_status=not_applicable`，0.6s 假绿。E3 问句精确等于板块名仍打 candidate；E4 首轮「那只票」无继承主体也澄清。`legacy_lane` 仍是 `research`（`decision_diverged_from_legacy=true`） | 2026-08-30 E 组 M2 `~/.finance-runtime/four-arm-20260830/analysis/m2-e-group.md`；`run_20260830_015349_432291` / `run_20260830_015350_083829` |
| E1 episode draft 含成交额、公开 `answer.md` 无 | 检索未取到成交额，或写手没写 | draft 已写「两市成交额：约 21014.72 亿元」，E1 卡 observation 同数；`judge_status=repaired` 后公开稿 63 字只剩上涨/涨停家数。issue 自述「成交额数值虽出现在E1中」。与上行 `business_status=complete` 同族：质检投影可删用户点名槽 | `run_20260830_015207_802388` `continuous-episode.json` + `answer.md` + `report.json` |

## 3. 当前 trace_depth 与盲区清单

- current_trace_depth: `D3`
- 说明：2026-08-03 `60dee33c` 之后的 run 可定位到 grounded phase 的入口余量、grant、耗时、状态和失败原因；更早 A 组产物没有 `phases`，只能到 D1/D2，不能补推阶段分布。

| blind_spot | 因为哪个字段缺失/被量化 | 挡住了哪层定位 | 补齐它的最小埋点（一个变量+阈值） |
|---|---|---|---|
| 最后一段退出余量不显式 | phase 只有 `remaining_ms_at_entry` 与 `elapsed_ms` | 无法直接审计 terminal slack | 增加 `remaining_ms_at_exit`；健康阈值 `>0` |
| token 与 phase 未同表关联 | LLM ledger 无 phase name，phase record 无 token usage | 无法区分输出长度与 provider 固定延迟 | 每段记录 provider usage 的 completion/reasoning token；若 provider 不返回则保持 unknown，不估算 |
| 旧 run 无 phase telemetry | 埋点上线前 artifact 只有合成终态 | 无法可靠重建旧 brief/composer/judge 分布 | 不回填；只用新 run 或受控 replay |
| phase 没有显式 semantic epoch/censoring type | 同名 `elapsed_ms` 跨 revision 变义 | 历史分类器会把自然完成、retry 倍增和 grant 截断混为一类 | artifact 增加 `phase_semantic_epoch` 与 `elapsed_kind`；现阶段按 revision 映射 |
| 三段精确 p50/p95 未知 | 只有 brief 单次完成值、composer 下界、judge 无同质样本 | 无法为 root 扩容路线精确 sizing | 只有用户选择 deep-mode 后才做 uncensored profile；当前工程决策不需要再跑 brief-only |
| Codex headless in-flight tool 没有可配对终态 | `tool_request` 现已有 timestamp、request id 与 root/research 两只入口时钟，normalized artifact 也能按 id 计数未配对请求；但缺 response 时仍没有自然完成/取消时刻 | 已能定位第一次缺口及其入口余量；`unpaired_tool_requests=0` 单独仍不能证明迟到结果隔离。`response_path_conflict` 是 mailbox transport 诊断，允许在同 id 的执行终态后另发 `tool_error`，不能混进执行终态基数 | R-10 用 deterministic slow tool 强制得到配对 error；正常成功路径断言恰好一个 `tool_result`，handoff 路径断言恰好一个预期执行层 `tool_error` 且无迟到 `tool_result`；另断言 `unpaired_tool_requests=0`、阈值处仅一次 finalization，且迟到 result 不入 episode |
| 历史 finish 无 `caveat_slips` | 2026-08-15 R-22 之前的 episode 不写该字段 | 不能用旧 artifact 直接数滑档频率 | 不回填；只用新 run。健康阈值 `=0`；`≥2` 全格、`=1` 混槽。查询 `finish.payload.caveat_slips`，旧产物打印 `<ABSENT>` |
| 历史 finish 无 `rejection_code` | 2026-08-15 R-23 之前的 episode 不写该字段 | 不能用旧 artifact 的字段缺失推断「没有拒收」；要下钻 `invalid_action.reason` | 不回填。新 run 无拒收时 code=`none`、reason 空串。`dump_episode_receipts.py` 对旧产物打印 `<ABSENT>` |
| 历史 `tool_exception` 的 `detail` 为空 | 2026-08-15 R-25 之前 consume 丢掉类名/首行 | 不能从空 `detail` 推断「没有异常消息」或具体故障类型 | 不回填。新 run 健康阈值：`error=tool_exception` ⇒ `detail` 非空且无 `/Users/`。查事件 payload，不查 ProviderTrace.detail |
| `gap_output_ids` 与 structural fulfilled 分道 | 语义修复删正文不收缩绑定；无显式 `bindings_contracted` 位 | 只读结构或只读 eb 分不出「没绑」与「绑了但公开删了」 | R-24 提案：删格时收缩绑定。在落地前并行读 `semantic_verifier.gap_output_ids` ∩ fulfilled。健康：交集为空 |
| 公开答案投影后的必答项覆盖未单独记录 | report 只保留投影前 structural/semantic 结果与最终 status，无 `post_projection_required_output_coverage` | 无法用机器字段区分「质检修好了答案」与「质检删掉了答案」 | 只增 `fulfilled_required_outputs / required_outputs`；发布为 complete 的阈值必须 `=1.0` |
| 粗粒度 `trace.json` 与原生 continuous episode 没有对账字段 | normalizer 不读 continuous episode 的 action/payload，只比较公开 step 名 | 无法发现 invalid action、timeout grant、repair reentry 这些决定性分叉 | 记 `continuous_event_count` 与 `unmapped_native_kinds`；用于宣称 fully equivalent 的阈值为 `unmapped_native_kinds=0` |
| controller 无 `resolution.candidates` / `candidate_kinds` | 只有格式化澄清问句与 `reason=…candidate` | D4 不能重放「为何同时撞上公司名与主题名」 | `resolution_status` + `candidate_kinds`（枚举长 ≤8）；健康：精确命中 `fact_sector_daily.sector_name` 时不得 `status=candidate` |
| 公开答案无成交额槽机器位 | 只能读 `answer.md` 正文 | 纠正后无法机判用户点名槽还在不在 | `slot_filled.total_amount=bool`；draft 有且公开无 → 投影删槽 |

## 4. Grounded phase telemetry semantic epochs

| epoch | revision | `elapsed_ms` 的正确解释 | 已知样本 |
|---|---|---|---|
| E0 | `< cd175a0e` | phase timeout 未在网络 enforcement point 被读取；可能是自然完成值，或被共享 child 截断 | `6c16b73a`: brief `ok 69740/22`；composer `failed 20261/10` |
| E1 | `cd175a0e ≤ rev < 8ed66020` | 单次请求受 grant 限制，但 retry 可各拿一份，phase 墙钟可达 `attempts × grant` | `cd175a0e`: brief `44560/22 provider_unavailable` |
| E2 | `≥ 8ed66020` | 整个 phase 共享 `phase_deadline`；deadline failure 时 `elapsed≈grant`，属于 censored lower bound | `8ed66020` 及以后：`29009/29`、`22010/22`、`28010/28` |

跨 epoch 的 artifact 不得直接跑同一耗时分类器。E0 的 `brief ok 69740ms` 是已有自然完成样本；E2 的 `brief failed 28010ms` 只给出 `>28s` 下界。声明“缺自然完成值”前必须先扫描相邻 artifact 与代码内实测注释。

## 5. Runtime revision 核验

`/api/health` 当前会在 `runtime.source_revision` 暴露 revision，并同时给出 `source_dirty`；因此服务重启后可先用 health 做快速核验。Acceptance preflight 仍必须把 revision 冻结进 artifact，不能只依赖事后 health 查询。

## 6. Cross-harness normalized profile

跨 harness 审计只比较控制面事件的顺序，不把两个运行时的内部 span
粒度假设成相同。共享词表**就是 `agent-run-triage` skill 的固定 L1 九步**
（`vocabulary: triage-l1-9`），不在本仓另立一套：

`configure → intent → plan → route → retrieve → tool → observe → synthesize → stop`

> 2026-08-04 前本仓用的是七步（缺 `plan` / `tool`），会把「是否形成了对的步骤」
> 与「是否正确调用了工具」压进 `route` / `retrieve`，导致一条 L1=`tool` 的
> triage finding 在本仓根本无法表达。产物 `schema_version` 随之升到
> `normalized-harness-trace-2` 并新增 `vocabulary` 字段；v1 产物不可与 v2 直接比较。

下表**按代码的分支求值顺序排列，先命中者胜**。顺序不是排版细节：`workbench`
的 `configure`/`plan` 若排在通用分支之后，`turn_assembly` 会落 `unmapped`、
`research_plan` 会被 `retrieve` 抢走；`codex` 的工具返回若排在工具请求之后，
`function_call_output` 会因含 `function_call` 而被误判成 `tool`。

| # | source kind | native event / field（匹配子串，大小写不敏感） | normalized step | provenance |
|---|---|---|---|---|
| 1 | `workbench-trace` | `configure`、`assembly` | `configure` | `native` |
| 2 | `workbench-trace` | `plan` | `plan` | `native` |
| 3 | `workbench-trace` | `controller`、`intent` | `intent` | `native` |
| 4 | `workbench-trace` | `route` | `route` | `native` |
| 5 | `workbench-trace` | `observe`、`validate`、`budget`、`ledger` | `observe` | `native` |
| 6 | `workbench-trace` | `retrieve`、`skill`、`research`、`evidence` | `retrieve` | `native` |
| 7 | `workbench-trace` | `synth`、`compose`、`grounded`、`shadow` | `synthesize` | `native` |
| 8 | `workbench-trace` | `stop`、`complete`、`finish`、`terminal`、`error` | `stop` | `native` |
| 1 | `codex-rollout` / `codex-exec` | `thread.started`、`session.started`、`config` | `configure` | `normalized` |
| 2 | `codex-rollout` / `codex-exec` | `turn.started`、`input` | `intent` | `normalized` |
| 3 | `codex-rollout` / `codex-exec` | `_call_output`、`command_execution_output`、`tool_output`、`tool_result` | `observe` | `normalized` |
| 4 | `codex-rollout` / `codex-exec` | `function_call`、`command`、`mcp`、`tool` | `tool` | `normalized` |
| 5 | `codex-rollout` / `codex-exec` | `message`、`reasoning`、`output_text`、`generation` | `synthesize` | `normalized` |
| 6 | `codex-rollout` / `codex-exec` | `turn.completed`、`turn.failed`、`error`、`failed` | `stop` | `normalized` |
| – | `runtime-benchmark` | `configure` | `configure` | `normalized` |
| – | `runtime-benchmark` | `task` | `intent` | `normalized` |
| – | `runtime-benchmark` | `plan` / `mode_decision` / `repair_goal` | `plan` | `normalized` |
| – | `runtime-benchmark` | `branch_started` | `retrieve` | `normalized` |
| – | `runtime-benchmark` | `tool_request` / `tool_call` | `tool` | `normalized` |
| – | `runtime-benchmark` | `tool_result` / `tool_error` / `runtime_result` / `observation` / `branch_completed` / `branch_failed` / `repair_outcome` / `invalid_action` | `observe` | `normalized` |
| – | `runtime-benchmark` | `finalization` / `finalization_recovery_started` | `synthesize` | `normalized` |
| – | `runtime-benchmark` | `finish` / `turn.completed` / `turn.failed` / `error` | `stop` | `normalized` |

`runtime-benchmark` 按 kind 精确查表（`_BENCHMARK_STEPS`），无顺序依赖；前两类按
子串匹配，故有顺序。

> ✅ **已修（2026-08-15，`R-20260815-05`）**：`_codex_mapping` 与 `_source_event_type` 现在共用
> `_codex_semantic_type()`，先读 `item.type` 再读 `payload.type`，两种落盘形状都认。同一份真
> rollout 的 `unmapped` 由 264 降至 53（`tool`/`observe` 各 42 配平），剩余 53 以 `token_count`
> 遥测为主，按契约保持 unmapped。下面这段是修复前的记录，保留作陷阱溯源：
>
> ~~**本表的 `codex-rollout` 行当前对真产物不成立（2026-08-15 实测）**~~。表里那些子串
> （`function_call`、`_call_output` 等）在真 `rollout-*.jsonl` 里位于 `payload.type`，
> 而 `_codex_mapping` 只在顶层 `type` 与 `record["item"]["type"]` 里找它们。**这正是
> 本节下文「本表与代码分歧即缺陷」的一次现场**——分歧方是代码：表描述的是
> `codex-exec` 流式形状（`{"type":"item.completed","item":{…}}`），代码也只实现了那一种，
> 而磁盘上的 rollout 会话日志是第三种形状，两边都没覆盖。在 mapper 补上
> `payload.type` 之前，**`codex-rollout` 这一列只对 exec 流式产物有效，对
> `rollout-*.jsonl` 一律产出全 `unmapped`**。详见 §2 新增的两条字段陷阱与
> [prediction-ledger.md](prediction-ledger.md) §2026-08-15。

工具配对另有一层 kind-aware 契约：Codex event 若有 `item.type`，normalized
`source_event_type` 保留该类型而不是统一写成 `item.completed`；Codex 的
`function_call/command/mcp/tool` 与 output 词表配对，benchmark 的
`tool_request/tool_call` 与 `tool_result/tool_error` 配对。Workbench 没有逐工具原生
词表，故指标为 `null`。新事件优先用 `correlation_id` 强关联，只有历史双方都缺 id
才退回 case 内 FIFO；因此 `0` 只能读作“本词表下没有悬空 request”，不能替代
R-10 对同 id 执行终态和迟到结果隔离的独立断言。断言时须排除
`tool=mailbox,error=response_path_conflict` 这一 transport 诊断事件。

**本表的地位**：语义源是**runtime 的公开投影与事件生产者契约共同构成**的——
`episode_progress._EVENT_PROJECTIONS` 只覆盖它自己投影的那些 kind（planning /
research 请求 / research 结果 / repair / finalizing），并**不包含** `configure`、
`task`、`tool_call`、`runtime_result`、`invalid_action`、`turn.completed` /
`turn.failed` 等；这些 kind 的语义由其**发射方**定义（落盘白名单
`runtime_backend_benchmark._DIAGNOSTIC_EVENT_KINDS`、`codex_headless_runtime`
自建事件列表、workbench 的 `step_id`/`name` 约定）。因此单独把投影表称作全部映射的
权威，是一句字面就不成立的声明。查某一行的语义时，先问该 kind 由谁发射：
投影表覆盖的以投影表为准，其余以生产者契约为准。

代码 `_workbench_mapping` / `_codex_mapping` / `_BENCHMARK_STEPS` 是**当前可执行
行为**，本表只是它们的人读转述。三者出现分歧时，**该分歧本身就是一个缺陷**，须当场
定位是哪一层写错，不要默认某一层为准后继续用。本表曾漏 `workbench` 的
`configure`/`plan`、`runtime-benchmark` 的 `configure` 与
`turn.completed`/`turn.failed`、`codex` 的 `config`/`input`，就是这种漂移。

`runtime-benchmark` 的每个 step 取自运行时自己的公开语义
（`episode_progress._EVENT_PROJECTIONS`：planning→`plan`、research 请求→
`tool`、research 结果→`observe`、repair→`plan`、finalizing→`synthesize`），
不按 kind 名字猜。**投影契约**：凡是
`runtime_backend_benchmark._DIAGNOSTIC_EVENT_KINDS` 允许落盘的 kind，必须在
`normalize_harness_trace._BENCHMARK_STEPS` 里有条目，否则它会静默掉出比较；这
条由 `test_every_persisted_benchmark_kind_has_a_normalized_step` 守住。

没有明确映射的事件必须输出 `step=unmapped` 和
`native_or_normalized=unmapped`，不能根据摘要、答案或事件相邻位置猜测。
实现入口为 `intelligence/eval/normalize_harness_trace.py`。每个 normalized
事件只保存 source event identity、受控状态/计数摘要和输入 SHA-256；不保存
prompt、答案正文、工具参数、命令 stdout、绝对路径、凭据或个人信息。

### claude-console-session（react 对照臂实验产物 → L1 九步；档 A：纯文档映射）

> 2026-08-28 落表（工单
> `docs/superpowers/specs/2026-08-27-longtail-react-gap-remediation-workorder.md` §P1）。
> **本 kind 无 normalizer 代码实现**——`normalize_harness_trace.py` 不认识它，`--kind auto`
> 不会命中。这是刻意的档 A 范围：映射只服务人工/脚本化跨臂 M2 对齐，不进生产投影管线；
> 「本表与代码分歧即缺陷」条款对本小节**不适用**（无代码可分歧）。档 B（react 驱动器补
> plan 地标）见工单 §P1，只改实验驱动器 `~/.finance-runtime/four-arm-20260827/scripts/`，
> 不改生产。

产物形状（[实测] 四臂 D2 样本）：顶层 `case_id / question / as_of / required_outputs /
allowed_capabilities / authorized_tools / code_root` + `calls[]`（`step_id / tool /
arguments / elapsed_seconds / called_at / error`）+ `answer / answer_sha256 /
finished_at / tool_call_count`。

| L1 step | 投影来源 | provenance | 损耗声明 |
|---|---|---|---|
| `configure` | 顶层 `allowed_capabilities` / `authorized_tools` / `code_root` / `as_of`（装配合同地标） | `normalized` | 无 system prompt 正文（刻意不落盘） |
| `intent` | `question` + `required_outputs` | `normalized` | — |
| `plan` | v1 产物**不可表达**（无决策事件）；**v2 起 `session.plan` 地标**（step 预算 + 工具白名单，`landmark_version=2`，2026-08-28 档 B 落驱动器，下轮实验首个 prepare 生效） | `normalized` | v1：一等损耗，M2 报告必须列 `residual_uncertainty`；v2：地标只记驱动器真实决定的两件事，不硬造逐步计划 |
| `route` | **结构性不存在**（单引擎、无 skill 分派），同 codex `route` 先例（§8「结构性差异非缺口」） | — | 不造事件凑指标 |
| `retrieve` | **归并进 `tool`**：驱动器对检索类调用与其他调用同形（都是 `calls[]`），无独立检索面 | — | 归并损耗；按调用的 tool 名回分检索/取数属「按事件名猜」，禁止 |
| `tool` | `calls[].tool` + `arguments`（原生顺序） | `normalized` | — |
| `observe` | `calls[].elapsed_seconds` + `error` + **`payload_sha256` / `evidence_count` / `observation` / `evidence[:evidence_limit]`**（勘误 2026-08-28：首版本行按工单摘要抄成「只有存在性证据」，对着真产物验证后不成立——四臂三题 call 记录均为 15 键富记录） | `normalized` | `evidence` 正文按 `evidence_limit` 截断，非完整原始载荷；`error=None` ≠ 结果可用 |
| `synthesize` | `answer`（终态） | `normalized` | 无中间稿 |
| `stop` | `finished_at` + `answer_sha256` | `normalized` | — |

**前缀门槛核算**：M2 前缀可比门槛为 `configure → intent → plan` 三步两侧非空
（workbench / codex 为 3/3）；本 kind **v1 产物**（无 `session.plan` 键，四臂 20260827
全部产物属之）`plan` 结构性缺失 → **2/3**，`plan` 损耗必须原样进报告的
`residual_uncertainty` 并配 Observability prescription；**v2 产物**（有 `plan` 键）
→ **3/3**。observe 的「无内容证据」旧声明已勘误（见上表），不再作为 residual 项。
首批消费本表的报告：`~/.finance-runtime/react-gap-m2-20260828/`（D2 / D5 双侧对齐，
其 residual #2 按本勘误作废，勘误注记见报告文件头）。

## 7. Comparison contract and evidence boundary

`compare_sequences()` 只对已映射的步骤做序列比较。若一侧没有任何 mapped event，
结果必须是 `not_established`，而不是把缺失事件判成行为分叉。

**分叉的输出形状（2026-08-04 定死）**：一次不匹配在同一 ordinal 上有**两个** step
值，单个标量无法表达，只返回左侧会让答案随入参顺序变化（同一对序列，workbench
在左得 `route`、benchmark 在左得 `tool`）。因此：

| 情形 | `relation` | `first_divergence_step`（标量） | `first_divergence`（结构化） |
|---|---|---|---|
| 同 ordinal 两侧 step 不同 | `step_mismatch` | `null`（契约规定） | `{ordinal, relation, left_step, right_step}`，并**必带 caveat** |
| 一侧是另一侧的严格前缀 | `left_continues` / `right_continues` | 较长侧新增的那个 step（唯一，无歧义） | 缺失侧写 `null` |
| 完全一致 / 证据不足 | – | `null` | `null` |

交换左右输入后，`ordinal` 与 `relation=step_mismatch` **不变**，只交换
`left_step` / `right_step`；该对称性由
`test_step_mismatch_is_symmetric_under_input_order` 守住。消费者遇到
`step_mismatch` 必须读结构化对象，**不得把两侧压成一个 L1 值**。

**产物可再入（idempotent reuse）**：`--compare` 的任一侧都可以是本模块自己的
单输入产物，按 `schema_version` 识别后直接复用其 `events`，并保留原始
`input_sha256` 以维持到原始 trace 的溯源；复用侧带 `reused_normalized_artifact:
true`。v1 产物、词表不符、事件畸形、或误传 `--compare` 的输出，一律抛
`NormalizedArtifactError` **显式失败**——旧行为是把 normalized 事件再喂给 raw
mapper（mapper 读 `type`/`kind`，不读 `step`），两侧 `mapped=0`、判定为 `null`，
与「没有分叉」不可区分。这条由
`test_compare_accepts_our_own_single_input_artifacts_round_trip` 与
`test_incomparable_artifacts_fail_loudly_instead_of_mapping_to_nothing` 守住。

截至 2026-08-03，仓库中冻结的 Codex headless benchmark artifact 只保留
`final_text/thread_id/token usage/issues` 和有限 diagnostics；原始 rollout
JSONL 没有进入 artifact。因此旧 Codex receipt 只能支持
`runtime-benchmark` 层的归一化审计，不能事后补出 `configure`、`intent` 或
原始 tool/message span。最近五题 receipt 也不是五题成功样本：其中
`weekly-market-cause` 仍是失败/降级，不能在报告里改写成 pass。

公平的跨 harness A/B 需要同一 PIT（point-in-time，时间截面）fixture、同一
cutoff、可观察的两侧原生事件和冻结的 task contract；本轮旧 receipt 不满足
这些前提，所以 T4 报告只作 trace-shape/数据缺口审计，不给 SDK 迁移或质量胜负
结论。

## 8. Instrumentation coverage matrix（2026-08-04）

共享词表对齐到 `agent-run-triage` 的 L1 九步（`vocabulary: triage-l1-9`，
产物 `schema_version: normalized-harness-trace-2`）之后，把两侧现有收据投影上去：

读数取自两侧**真实执行路径**：workbench 跑一次真 turn 读 `trace.jsonl`；codex 跑
`CodexHeadlessRuntime.run()`（仅 subprocess 用 fake stdout，事件由真实 `_to_outcome`
构造）。均归一化后计数。

| L1 step | workbench 埋点前 | workbench 埋点后 | codex 埋点前 | codex 埋点后 | 两侧都有 |
|---|---|---|---|---|---|
| `configure` | – | **1** | – | **1** | ✓ |
| `intent` | 1 | 1 | –（`task` 被丢） | **1** | ✓ |
| `plan` | – | **1** | – | **1** | ✓ |
| `route` | 1 | 1 | – | – | |
| `retrieve` | 2 | 1 | – | – | |
| `tool` | – | – | 11 | 1 | |
| `observe` | 3 | 1 | 16 | 2 | ✓ |
| `synthesize` | 1 | 1 | – | – | |
| `stop` | – | – | 5 | 1 | |

- 埋点前：两侧都有仪器的**只有 1 步**（`observe`）。
- 2026-08-04 补埋点后：**4/9**。workbench 序列
  `configure → intent → plan → route → retrieve → synthesize → observe`；
  codex 序列 `configure → intent → plan → tool → observe → observe → stop`。
- 门槛 `configure → intent → plan` 三步两侧非空：**3/3 达标**。
  `first_divergence_step` 在这三步的前缀内已具备行为含义。

> codex 侧的 `configure` / `plan` 不是新造的事件：`configure` 记的是本来就存在的
> 装配（model / reasoning_effort / thread_id / registry 规模 / isolation / cutoff），
> `plan` 记的是 `context.policy` 的 tier + max_steps + total_seconds ——
> 即该 runtime 的研究深度决策，与 `agent_episode` 的 `mode_decision` 同义。
>
> 为此放宽了 `AgentOutcome` 的锚点不变量：`configure` 是**唯一**允许排在 `task`
> 之前的 kind。若强行让 `configure` 排在 `task` 之后，codex 会发出
> `intent → configure` 而 workbench 发出 `configure → intent`，**纯靠事件顺序在
> ordinal 0 制造一个假分叉**。

这改写了跨 harness 审计「无法配对」的成因判断。补埋点前，问题不只在五题的
workbench trace 没保留：两侧仪器覆盖的是流水线的不同半段，当时真正共有的只有
`observe`。补齐真实的 `configure/intent/plan` 地标后，两侧共有已升到 **4/9**，
前三步前缀现在可比；`route/tool/synthesize/stop` 的结构差异仍须按矩阵解释。

因此下一次公平审计的门槛是**可计数**的，不再是「让两侧都保留原生事件」这种无法验收的表述：

| 缺口 | 属哪侧 | 状态 | 最小埋点 |
|---|---|---|---|
| `configure` | workbench | **已补** | `step_id=configure` / `name=turn_assembly`，记 skill_mode、registry 规模、selected_skill_ids、上下文条数、继承 intent；只记身份与计数 |
| `plan` | workbench | **已补** | `step_id=plan` / `name=research_plan`。数据本来就在 `controller` 的 payload 里，属**拆融合 span**，不是造事件 |
| `intent` | codex | **已补** | `task` 事件回到落盘白名单，**仅对 2026-08-04 之后的 run 生效**，历史 artifact 无法追认 |
| `route` | codex | **结构性差异，非缺口** | codex episode 不做 skill 分派（backend 由 benchmark 选定、tool registry 固定）。强行造一个 `route` 事件只是为了凑指标 |
| `tool` | workbench | **已补（2026-08-15 更正）** | 本行原记「未补」已不成立：`trace.jsonl` 实际含逐工具事件 `continuous:episode:<n>:tool_request` / `tool_result` / `tool_error`（B1 实测 5 请求 / 3 结果 / 2 错误），带 `status` 与起止时刻。**注意**：这些事件的 `output_summary` 是给用户看的话术（「已取得一批可核验资料。」），不是机器观测，不可当证据读——真实载荷在 `continuous-episode.json` 的 `outcome`。出处 `run_20260814_021938_990234` |
| `stop` | workbench | 未补 | trace 以 budget 事件收尾，无显式终态 step |
| 交付层证据来源 | workbench | **新增缺口（2026-08-15）** | `/api/runs/{id}/context` 的 `evidence[]` **只从 `trace[].retrieval` 构造**（`app.py:1661-1718`），而 `continuous:evidence` 步只在 `citations` 非空时发射（`conversation_orchestrator.py:3564`）。故 episode 的 `outcome.evidence` 不为空也可能交付 0 条，且两者之间没有任何对账字段 |
| `synthesize` | codex | 未补 | headless artifact 不保留 message span |

验收状态：`configure → intent → plan` 三步在两侧都非空，**3/3 已达标**；
`first_divergence_step` 在此前缀内已具备行为含义。

> 门槛从「四步」收窄为「三步」：`route` 在 codex 侧是**结构性不存在**而非仪器缺失。
> 把结构差异写成埋点缺口，会诱导为满足指标而制造事件——那正是本 profile 反复
> 在防的重编码。

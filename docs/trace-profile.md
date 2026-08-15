# Trace Profile: finance-workspace-private

- last_updated: 2026-08-15
- updated_by_run: `20260815T0302Z-r4-clean-baseline-2`（多条 finish 取末条；
  `evidence_bound` ≠ episode fulfilled。前值 `2026-08-15-trka-r2-caveat-slips`）
- 配套账本：[prediction-ledger.md](prediction-ledger.md) —— 分诊**开工第一步**先回填那里的 pending 预测，再开始新归因

## 1. 产物位置与结构

| 产物 | 路径/glob | 结构 | 关键字段 → 语义 |
|---|---|---|---|
| Acceptance run | `intelligence/eval/runs/*.json` | 一次命令一份 JSON，`cases[].turns[]` | `status` 是 turn 运行态；`degrades` 是用户可见降级；`synthesis_diagnostic` 是合成健康态；`trace_steps` 是粗粒度步骤名 |
| Workbench run | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/` | 每个 run 一个目录 | `run.json` 保存运行元数据；`report.json` 保存结构化报告；`answer.md` 是最终展示正文 |
| Runtime trace | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/trace.jsonl` | 一行一个控制面事件 | `step_id` 是原生定位符；`llm_call_ledger` 记录 provider 调用；`research_execution_budget` 记录 root 预算与工具尝试 |
| Grounded shadow | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/grounded_composer_shadow.json` | 单个 JSON | `status/failure_reason/elapsed_ms` 描述 Grounded 链终态；只在阶段产出存在时保存 brief/raw/judge 内容 |

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
| 多条 `kind=finish` | 取任意一条即可读 `caveat_slips` / `stop_reason` | 同一 episode 常有**两条** finish：第一条多是检索截止 `deadline_exhausted` 且 `slips=0`，第二条才是修复轮终态。数 slips / 判 `invalid_repair_finish` 必须取**最后一条**。批 #2 若取首条，8 个 slips>0 窗口会全部读成 0 | `20260815T0302Z-r4-clean-baseline-2` A9/B2/B3/B4/B7/C1/C6/C10；B5/C7 末条才是 `invalid_repair_finish` |
| `execution_state_tally` | 每题一个态，等于 case 终态分布 | **`< R-20260815-11` 的产物按 `turns[0]` 计**，多轮题会被首轮掩蔽（C10 三轮 delivered/clarification/bound_but_dropped，tally 计 delivered，末轮却是 bound_but_dropped）。此后 tally **按轮**，case 级另立 `execution_state_aggregate`（写死 `last_turn`），并带 `execution_state_case_tally` / `execution_state_turn_rows`。读旧产物前先看有没有 `execution_state_aggregate_rule` | `20260814T1926Z-r3-clean-baseline` C10；`summarize_execution_states` |
| `evidence_bound` | 与 episode 已 fulfilled 且带哈希的格同义 | 验收台从 `/api/runs/<id>/context` 计 `status=hit`。B3@批#2：episode `direct_assessment`/`chain_mapping` 共 11 哈希且 struct=fulfilled，context 证据列表为空 → `evidence_bound=0`。R-10 交付率仍按冻结的 `evidence_bound>0` 口径，不得事后改口；并行读 episode 格 | `run_20260815_111907_054023` |

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

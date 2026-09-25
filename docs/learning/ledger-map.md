# 台账地图（全部台账的一页总索引）

> 防再乱的总登记表：每条台账线只有一个 canonical 机器可读落点（JSON/JSONL），md/html 一律是渲染物；
> 按日期命名分区；每个台账文件只有一个写入者；需要 git 历史的进仓，缓存/超大生成物落仓外 `~/kb_work/`。
> 新增任何台账，必须先在这张表登记。

用户态路径以 `intelligence/userspace.py::users_dir/user_space` 为准：`FORESIGHT_USERS_DIR` 优先，未配置时源码仍回退到仓内 `intelligence/users/`。该回退是代码兼容行为，不是写入冻结存档的授权；正常运行须显式绑定外置用户根，离线测试使用临时根。下表以解析器表达落点，不硬编码本机目录。保鲜诊断是带日期的历史证据，不是当前覆盖率。

| 台账 | canonical 路径 | 格式 | 唯一写入者 | 提交? | 渲染物 |
|---|---|---|---|---|---|
| 部署与启动归属 | `deploy_ledger.resolve_ledger_path()`（默认 `~/.finance-runtime/deploy-ledger.jsonl`，显式路径或 `FINANCE_DEPLOY_LEDGER` 优先） | JSONL，startup / switch；`startup_port_attribution` 仅追加对无端口 startup 的归属，绑定原行规范化 SHA256、启动日志与 health 原件哈希。证据改变或冲突即不采信，不重排原事件 | `intelligence/runtime/deploy_ledger.py`；lifespan 自报、`audit_deploy_ledger.py record`，归属补记 `attribute-startup --apply`（默认 dry-run） | 否（机器状态）；证据须保留在稳定树外目录 | `audit_deploy_ledger.py check/homes`；`worktree_board` 仍只读 switch，归属补记不产生切换 |
| 方法验证实验（固定三组、当日前瞻观察、到期回检） | `userspace.user_space(user).root/method_validation/<protocol_id>/protocol.json`；`history/<记录日>/<hash>.json`、`capture/<D0>/<hash>.json`、`recheck/<记录日>/<hash>.json`（`FORESIGHT_USERS_DIR` 优先；CLI `--root` 可明确指定离线研究目录）。派生缓存 `standing/<输入指纹>.json`（立场摘要，可重算、可替换，不是真源）；草稿 `<root>/candidates/<hash>.json`（匹不上固定方法的自然语言方法，不编译） | JSON，不可覆盖；协议/每次输入/结果均有内容摘要 | `scripts/method_validation.py register/history/capture/recheck/daily`（`status --refresh` 只重算摘要）；夜间 `checkpoint recheck` 经 `MethodValidationResolver` 到期写 recheck 收据；主实验 R 号仍由 claim_ledger_id 领取并在 prediction-ledger 索引。有信号的 D0 观察**登记进既有 `checkpoints.jsonl`**（`object_type=method_observation`、`metric.type=method_validation`），不另开台账 | 否（私人研究应用态）；方法代码与工作流文档提交 | `report --record` → Markdown；`status` → 立场摘要；日报「方法信号与待验对象」段与 `[M]` / `memory_lookup` 只读摘要；当前全部 research_only，不进入 lifecycle/画像/参数推广 |
| 同花顺目录/成员采集审计 | 所选 DuckDB（遵循 `MARKET_FEATURE_STORE_DB`）中的 `ops_hithink_sector_capture`、`ops_hithink_sector_request`；schema 以 `market_feature_store/schema.sql` 为准 | DuckDB：批次头＋逐逻辑请求的计划/结果；终态不可覆盖，成功响应仅保留白名单字段 JSON 与指纹，不存密钥/原始错误正文 | `market_feature_store/hithink_sector_capture.py::SectorCapture`，由既有 `sync_hithink_sector_kline` 调用；不另建生产写入口 | 否（数据库应用态） | 指定 capture_id 的只读预览；请求完成度与供应商完整性分列，后者无独立分母时为 unverified；不代表 canonical 发布或行情覆盖 |
| 同花顺研究观察请求 | 所选 DuckDB（`MARKET_FEATURE_STORE_DB`）中的 `ops_hithink_research_request` | DuckDB，逐请求 UUID：IO 前 pending，结果 ok/empty/partial/failed；范围、供应商时间、上海采集时间、原始成功响应；不存凭证或错误正文 | `market_feature_store/sync/sync_hithink_research.py::_capture`，经既有 daily-full staging；拒绝直写生产 | 否（数据库应用态） | CLI 请求摘要；三个 fact 读口由 `finance_query` 消费，事实是最后观察值不是历史 PIT 版本 |
| 每日市场复盘（正式日报） | `market_feature_store/exports/<date>-daily-review.json`（schema `daily-review/v1`：核心看板 + `facts` 口径字段 + 15 节 `sections[].blocks[]`） | JSON | `market_feature_store.cli daily-review`（`reports/daily_review.py::build_daily_review`，全量入口 `intelligence.cli daily` 的 `daily-review` 步） | 是（几十 KB/天） | 同名 `.md`（不提交，`render_daily_review_markdown`）→ `复盘/daily/<date>/<date>-daily-review.html`（`render_daily_review_briefing.py`）；Workbench 产物库投影 `project_daily_review_json`；框架解读 `load_facts_digest` |
| 复盘输入冻结 | `docs/learning/forecast-review-ledger/<date>.manifest.json` | JSON | `dual_blind_forecast.py manifest`（**夜跑已退役**，仅手动） | 是 | — |
| 复盘答卷 | `docs/learning/forecast-review-ledger/<date>.answer.<agent>.json` | JSON | `dual_blind_forecast.py validate`（校验；**夜跑已退役**） | 是 | `<date>.md` |
| 复盘验证 | `docs/learning/forecast-review-ledger/<date>.verdict.json` | JSON | `dual_blind_forecast.py verdict`（**夜跑已退役**，仅手动） | 是 | `index.md` 状态表（`index` 子命令） |
| 回答评分 | `userspace.user_space(user).answer_scores_path` | JSONL | auto_eval | 否（用户态） | — |
| 个人判断回检 | `userspace.user_space(user).checkpoints_path` + `verdicts_path` | JSONL（`checkpoints` 每行可选字段 `rule_id / rule_verdict / rule_receipt / bias_flags`：引用的方法论规则、登记当时该规则最近收据的四态与路径、偏差目录命中 code 列表——2026-09-05 INDEX #24，读者 `calibrate.by_rule` / `render_report` / `checkpoint bias-scan`） | foresight checkpoint | 否（用户态） | — |
| 情景树（多步推演，#37 / G-15） | `userspace.user_space(user).root/scenario_trees.jsonl`（`FORESIGHT_USERS_DIR` 优先） | JSONL，append-only；登记须带 `projection_hash / model_id / framework_version`，`realized_path` 只由 `river.slice(T+k, C=T+k)` 判定 | `intelligence/services/scenario_trees.py::register / resolve`（无独立 CLI；每日复盘钩子 `daily_review_hook` 默认关，`FORESIGHT_SCENARIO_TREE_RESOLVE=1` 才跑）；登记同时进 `checkpoints.jsonl`（`object_type=scenario_tree`） | 否（用户态） | 三项回检（覆盖 / 沿路剧本 / 规则样本）；到达节点剧本按 G-03 登记 |
| 记忆候选留档 | `userspace.user_space(user).root/memory_candidates.jsonl` | JSONL | `run_memory_candidate_loop.py` | 否（用户态） | `trace` 子命令（归因反查）；生命周期见 `memory-candidate-lifecycle.md` |
| 双盲错因反思候选 | `docs/learning/forecast-lessons/reflections/<date>.reflection.<agent>.<source>.json` | JSON | `forecast_learning_loop sync-reflections` | 是 | Workbench / 人工审批 |
| 双盲已批准 lessons | `docs/learning/forecast-lessons/lessons.jsonl` | JSONL | `forecast_learning_loop approve-reflection` | 是 | 次日答卷 prompt |
| 双盲批注规则候选 | `docs/learning/forecast-lessons/rule_candidates.jsonl` | JSONL 事件流 | `forecast_learning_loop sync-annotations/approve-rule/reject-rule` | 是 | 次日答卷 prompt（仅 approved） |
| Knevo × 工作台 双盲对照（AB 线） | `docs/learning/knevo-distill/ab-ledger.md`（样本正文 + verdict）；逐份冻结答案 `docs/learning/knevo-distill/ab/AB-NNN-{local,knevo}.md` | md（例外：人过闸的对照裁决文档，md 即 canonical；与分叉蒸馏批记录同类） | divergence-distill / 人工会话（**无脚本写入者**，git commit 时间戳即冻结证明） | 是 | — |
| 分叉蒸馏批记录 | `docs/learning/distill/<date>-<对照名>.md` | md（例外：人过闸裁决文档，md 即 canonical） | divergence-distill skill 会话 | 是 | — |
| 晨汇 | 知识库仓 `wiki/briefings/<date>.md` | md | morning-briefing | 是 | `dashboard/briefings/<date>.html`（不提交） |
| 晨汇原料 | 知识库仓 `wiki/raw/briefings/<date>/` | 原文 | morning-briefing | 是 | — |
| 卖方原文 | 知识库仓 `wiki/raw/sellside/` | md/pdf 转写 | material-router（表定）/ 近月实写 sellside-coverage-cross | 是 | — |
| 卖方观点事件 | 知识库仓 `wiki/raw/theme-radar/opinion-store/opinion-events.jsonl` | JSONL | opinion-cross | 是 | `复盘/winrate/*.html`（不提交） |
| 卖方事件更正 | 知识库仓 `wiki/raw/theme-radar/opinion-store/corrections/<batch_id>.json` | 不可覆盖 JSON，逐事件绑定原记录哈希、前一修订、原文字符锚点；时间由写入者盖章 | 金融仓 `scripts/review_opinion_events.py`（校验整批后加锁发布，重放同批幂等）；不改原事件 | 是 | `intelligence.services.opinion_events` 按知识截止投影；接催化归因、Workbench 卖方流及教学/事件定价研究构建入口；后两者为事后聚合，不等于严格PIT或 river 目录同步 |
| 晨汇 Tier 事件（晨汇正文 Tier 1 / 2 / 3 条目的确定性投影：维度 / 是否盘面共振 / 主题 / 信号 / 映射标的 / 双链 / 材料日 / 最早可知日 / 写成日；一条条目一行，全量重建、可复现） | 知识库仓 `wiki/raw/theme-radar/opinion-store/briefing-tier-events.jsonl` | JSONL | 知识库 `skills/morning-briefing/scripts/extract_tier_events.py`（morning-briefing Stage 4.5；`--check` 作收尾门禁） | 是 | 金融仓 `build-labels --kb-wiki` → `tf.briefing_*` / 河对象 `teaching_briefing` / 带读「消息面」一行 |
| 机构胜率 | `~/kb_work/winrate_cache/` + `~/kb_work/winrate/` | md | refresh_winrate | 仓外 | 同上 |
| 每日运营总账 | `build_daily_ops_ledger.py` 输出 | JSON | 该脚本 | 生成物 | cockpit |
| 工作台 Run | `userspace.user_space(user).root/runs/<run_id>/run.json` + `trace.jsonl` | JSON/JSONL | `run_store.py` | 否（用户态） | Workbench UI（协议见 `docs/superpowers/plans/2026-07-08-run-protocol.md`） |
| 历史研究查询 / 案例 / 假设原件 | `userspace.user_space(user).root/runs/<run_id>/history-{query,case,hypothesis}-<sha256>.json`（用户根由 `FORESIGHT_USERS_DIR` 解析；登记在同 run 的 `run.json`，不写冻结的 `intelligence/users/`） | 内容寻址 JSON，不可覆盖 | `RunStore.add_history_artifact`；案例修订在 `history_case_transaction` 内核对当前 head | 否（用户态） | Workbench 既有 JSON 产物查看器；Agent `read_history_result` 同用户同会话、截止及范围核验后读取 |
| 工具饥饿 | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/tool_hunger.jsonl` | JSONL | episode/inline 运行时（fail-open） | 否（用户态） | `python -m intelligence.eval.tool_hunger` → `intelligence/eval/measurements/tool-hunger-YYYY-MM-DD.{json,md}` |
| 工作台会话 | `userspace.user_space(user).root/conversations/<conversation_id>/conversation.json` + `messages.jsonl` | JSON/JSONL | `ConversationStore` | 否（用户态） | Chat-first Workbench UI |
| Fidelity 前向验收 | `/Users/a77/fidelity-runtime/forward-acceptance/records/<date>/*.json` | JSON | `fidelity_forward_acceptance.py record` | 仓外 | `latest/<date>.json` + `summary` 子命令 |
| 观测台薄账 | `docs/roadmap.md` | md（例外：md 即 canonical，不是渲染物） | 检阅方 | 是 | Phase 1 起 `var/observatory/index.html`（gitignored）；L2/曲线由生成器投影 |
| 视角考卷（已知题/边题） | `userspace.user_space(user).root/perspectives/exam/<pid>.json` | JSON | `perspective exam add` | 否（用户态） | `perspective exam run` 报告 |
| 自用摩擦台账 | `docs/learning/self-use-ledger/<date>.jsonl` | JSONL | `scripts/self_use_ledger.py add`（只记真人使用，探针/评测不进账） | 是 | `summary` 子命令（Self-use Gate 读数，见目录 README） |
| 预测/假设台账（R-号，实验立案与预注册裁决） | `docs/prediction-ledger.md` | md（例外：md 即 canonical） | 号由 `scripts/claim_ledger_id.py claim` 原子预占（禁手工 max+1）；行由立案会话写入 | 是 | —（实验原始收据在 `~/.finance-runtime/<实验名>/`，本表行是唯一住址索引） |
| IMA 缺口清单（该跑 DeepDive 的题材 / 该补逻辑卡的个股） | `market_feature_store/exports/<date>-ima-gap.json`（`schema_version` 字段） | JSON | 全量入口 `intelligence.cli daily` 的 `ima-gap-report` 步（只出清单，不自动问 IMA） | 是 | 同名 `.md` |
| 方法论回测收据（规则在历史上的 N / 命中率 / 基准率 / Wilson / 四态，带成立条件；实体 sector / theme / stock） | `methodology/receipts/<rule_id>@v<version>/<date>.json`（`schema_version: methodology-backtest-receipt/v0`；scan 汇总 `methodology/receipts/scan/<date>.json`） | JSON | `scripts/methodology_backtest.py run/scan`（规则真本源 `methodology/rules/<rule_id>.v<version>.json` 进 git；旁路库 `db/history_labels.duckdb` 由 `build-labels`/`outcomes` 从主库只读重建） | 否（可重建） | 同名 `.md`（stock 规则的事件样例含个股代码，仅分析师侧核对，不进共享层渲染） |
| 方法论回测证伪库（统计门下 `refuted` 的规则条目：rule_id / version / sharing / owner / N / p / p0 / Wilson / 按大盘阶段拆分 / refuted_at / 收据路径） | `methodology/refuted/<rule_id>@v<version>/<date>.json`（`schema_version: methodology-backtest-refuted/v0`） | JSON | `scripts/methodology_backtest.py run/scan`（结论为 refuted 时随收据落一条；scan 以 BH 校正后的结论为准，单次 refuted 被 BH 降级的不落） | 是（证伪是资产：收据目录可重建、条目要跨机器 / 跨旁路库重建留存） | `report --refuted` 按大盘阶段汇总（stdout markdown；「这个阶段这招不灵」） |
| 历史重放读数（站 D0 结构化判断 → 自动判分：车道 A 规则复现一致率 + 车道 B 前瞻分格 `pit_grade × memory_bucket × arm × category × horizon`、臂间差、对账段；每条读数带 pit_grade / memory_bucket / arm 三标签，N<10 只给 N） | `intelligence/eval/measurements/replay-<date>.{json,md}`（`schema_version: replay-report/v1`；节点级产物 `~/.finance-runtime/replay/<run_id>/` 可重建、不登记） | JSON/md | `scripts/replay_engine.py run`（`report --run-dir` 从同一 run 目录重出，不调 LLM；不写 `docs/learning/forecast-review-ledger/`） | 是 | 同名 `.md` |
| 观察剧本 + 提取前置（一个文件三类记录：`record_kind ∈ script/attempt/event`；缺该字段 = 存量剧本。草稿带 `author_origin=user` / `draft_id` / `draft_version` / `canonical_entity_id` / `extraction_attempt_id`；`draft_submitted` 与 `script_confirmed` 两个成功事件**随剧本行内的 `action_event` 一次写入**，读取时投影出来，不追加第二条事件行；`draft_skipped` / `abandoned` / `read_completed` 是独立事件行，按 `action_key` 去重） | `userspace.user_space(user).root/observation_scripts.jsonl`（`FORESIGHT_USERS_DIR` 优先） | JSONL，append-only；写入持 `.observation_scripts.jsonl.lock`（flock）+ 整行 flush/fsync，半行不算成功 | `intelligence/services/observation_script.py`（唯一写入者：`register` / `submit_draft` / `open_attempt` / `close_attempt` / `record_event` / `repoint_due`）。判定侧 `observation_extraction.py` 是纯函数，**不写盘**。确认剧本另进 `checkpoints.jsonl`（`object_type=observation_script`），过程事件**不进** checkpoint、**也不写 `interactions.jsonl`**——后者是「新用户 / 老用户」默认开关的判据台账，往里写一行就会翻转带读默认值 | 否（用户态） | `observation list`（剧本）/ `observation list --events`（五事件 + pending 尝试）；`personal export` 原始导出带走全部三类 |
| 补数请求完成 / 恢复回执（问题驱动补数：`completed` 一条 = 某请求在某 `data_version` 下覆盖检查通过；`resumed` 一条 = 某消费者 run 已按该版本沿 Workbench 重问；同键只落一次，重放幂等） | `$FORESIGHT_USERS_DIR/<user>/data_request_receipts.jsonl` | JSONL | `intelligence.cli data-requests resume`（`services/data_requests.record_completions` / `execute_resume`）；请求本身**不是台账**——由各 run 的 `tool_hunger.jsonl` 里 `window_uncovered` 事件随时重建，日产物 `market_feature_store/exports/<date>-data-requests.json` 与 kb-ingest-queue 同一写入者 | 否（用户态） | `data-requests status`（stdout JSON + 同名 .md） |
| 单次研究成本报表（写手 `outcome.usage` + 判官 `metrics.judge_usage` 的中位/均值/p90 token 与元/次；价目表 `intelligence/eval/pricing/llm-prices.json` 手工核对） | `intelligence/eval/measurements/research-cost-<date>.{json,md}` | JSON/md | `python -m intelligence.eval.research_cost` | 是 | 同名 `.md`（顶部成立条件块：价目表 checked_at / run 数 / 日期范围 / 估算记录占比 / 树·解释器·revision） |
| 研究进化 · 依赖绑定（用户明确「从现在开始跟踪」哪些证据引用；含绑定那一刻解析到的真实版本与取数实体/交易日） | `userspace.user_space(user).root/research_evolution/dependency_bindings.jsonl` | JSONL，append-only；按 `binding_id` 幂等，同 id 异内容拒收（409）；正文是 01 的 `judgment-maintenance-binding/v1` 外加 06 的取数来源封套 | `intelligence/services/research_evolution/store.py::EvolutionStore.append_binding`（唯一写入者；经 `POST /api/conversations/{id}/research-evolution/bindings`）。原 judgment / checkpoint / 情景树**只被引用，不被改写** | 否（用户态） | `GET …/research-evolution` 的 `maintenance` 段（由 01 `assess` 现算，不缓存） |
| 研究进化 · 管理动作事件（开始复核 / 稍后处理 / 继续核查 / 取消重判退回 / 核对后判断未变 / 关联 run 终态） | `userspace.user_space(user).root/research_evolution/maintenance_actions.jsonl` | JSONL，append-only；按 `idempotency_key` 幂等，同键异载荷或跨会话 409；正文是 01 的 `ManagementEvent` 外加 06 封套。**也存无事件幂等记录**（`event=None`：运行中 run 登记、select_task 选择）——`list_events` 只取 event 为 dict 的行，不进 01 折叠 | 同上 `EvolutionStore.append_action` / `append_action_record`（唯一写入者；经 `POST …/research-evolution/actions`；读校验与追加在同一事务内，竞态安全）。**管理动作不是新判断**：要改判断仍走 `judgments.record_judgment` / `checkpoints.record_verdict` 原写入者 | 否（用户态） | `maintenance` 段的 `management` 字段（01 `reduce_actions` 折算） |
| 研究进化 · 重判请求 ↔ run 关联（「继续核查」发起的新 run 在**运行中**登记；run 终态折回维护项必须以它为凭——同会话不再足以证明「这个 run 是本次复核发起的」） | `userspace.user_space(user).root/research_evolution/run_links.jsonl` | JSONL，append-only；按 `link_id`（= 幂等键）幂等，同 (item, run) 重复登记复用原行 | 同上 `EvolutionStore.append_run_link`（唯一写入者；经 actions 端点 `link_run`）；终态折回由观察器 `fold_run_terminal` 或客户端恢复路径写动作事件 | 否（用户态） | `link_run` 动作回包的 `link` 字段 |
| 研究进化 · 产品使用测量事件（05 合同的原始事件；用户操作、客户端时间与服务观察时间分列） | `userspace.user_space(user).root/research_evolution/product_value_events.jsonl` | JSONL，append-only；按 `event_id` 幂等；`source_channel` / `provenance` / `recorded_at` 一律服务端盖章，客户端自报不采信 | 同上 `EvolutionStore.append_product_value_event`（唯一写入者；前端经 `POST …/research-evolution/events`，只放行 05 白名单里允许 `frontend` 的类型） | 否（用户态） | 05 `measure_pair` / `summarize` 现算（收据见下一行） |
| 研究进化 · 流程收据（04 用：`coverage` 台账完整性声明、`exposure` / `exercise_seen` 曝光、`evidence_use` / `stage_use` / `revision`） | `userspace.user_space(user).root/research_evolution/process_receipts.jsonl` | JSONL，append-only；按 `receipt_id` 幂等；`kind` 取 04 的 `RECEIPT_KINDS` | 同上 `EvolutionStore.append_process_receipt`（唯一写入者）。**没有 `coverage` 声明就只能报 `coverage_unknown`，不能报「漏检」** | 否（用户态） | `diagnostics` 段（04 `diagnose` 现算） |
| 研究进化 · 不可变件（冻结试点协议 / 测量收据 / 试点总结 / 登记的诊断策略与题包） | `userspace.user_space(user).root/research_evolution/{protocols,receipts,summaries,registrations}/<内容 id>.json` | JSON，tmp + `os.link` 发布，**不可覆盖**：同 id 同内容幂等返回，异内容 409 | 同上 `EvolutionStore.publish_immutable`（唯一写入者） | 否（用户态） | 原件查看器；`receipt_refs` 只给引用与状态，读正文要先过 03 曝光登记 |
| 研究进化 · 前向实验（协议 / 预测 / 观察 / 收据 / 曝光） | `userspace.user_space(user).root/research_validation/**` | JSON，不可覆盖 | **03 的 `research_validation/repository.py::Repository` 是唯一写入者**；06 只注入已解析的私有根并登记受控引用，不复制第二份可编辑实验事实 | 否（用户态） | `receipt_refs.validation`（未到期照样 `pending`） |

## 双盲夜跑（2026-09-03 用户拍板：退役）

上表「夜跑已退役」三处自 08-20 起只对 finalize 里的 recheck/auto_verdict 成立；出答卷的那条
launchd `com.financeworkspace.dual-blind-forecast`（工作日 09:10 跑 `scripts/dual_blind_auto.sh`）
在 2026-08-28 23:00 被重新装回（PR #498 那批），之后每天落 manifest + `answer.claude`，codex 腿一直
「未落答卷」（1/2）。2026-09-03 用户拍板整条退役：已 `launchctl bootout`，plist 归档为
`~/Library/LaunchAgents/disabled-by-devin/com.financeworkspace.dual-blind-forecast.plist.retired-2026-09-03`。
仓内 `intelligence/dream/com.financeworkspace.dual-blind-forecast.plist` 只是模板，**不要再装回**；
08-31～09-03 的最后四组 manifest/answer 已随本次收拾入库作为终档。`chore/retire-dual-blind-nightly`
（`~/fwp-wt-retire-dual-blind`）的代码改动早已在 main 等价存在（`nightly_full_review.sh` 第 156 行
注释即是），该分支按 superseded 处理。

复盘 HTML/PNG（`复盘/daily/<date>/`）自 2026-09-03 起不再入库（用户拍板：渲染物留本地）；
台账真本源见 PR #555 的 `<date>-daily-review.json`。

## 保鲜状态（2026-08-28 P3 诊断）

工单 `docs/superpowers/specs/2026-08-28-ledger-refresh-workorder.md`。结论：**卖方是微信 API 频控 + 手贴停更；晨汇不是同一条线**——原料在 IMA 浑水调研，经 `ima-fetch.cjs`（desktop bridge）拉 PDF，再交 `morning-briefing` 入库。未补拉、未恢复任何退役链。双盲夜跑仍按表内「夜跑已退役、仅手动」，本诊断不碰。

| 台账 | 最近落点 | 缺档 | 触发方式 | 断因 | 证据 |
|---|---|---|---|---|---|
| 晨汇 / 晨汇原料（本行 2026-09-21 二次复核重写） | `wiki/briefings/2026-09-18.md`（`#6892`，2026-09-21 入库）；9 月已连续：09-01 / 03 / 06 / 07 / 08 / 14 / 15 / 18 | **当前无缺档**。09-15、09-18 于 2026-09-21 回填入库（`#6891`/`#6892`，知识库仓 PR #156）；09-16 / 09-17 / 09-19 上游确无 PDF（五词交叉验证：路演 / 预期差 / 复盘 / 汇总 / 总结） | **IMA bridge**：`ima-desktop-bridge/scripts/ima-fetch.cjs` 搜浑水调研 → 拉 PDF → `morning-briefing` 入库。无 crontab | 2026-09-21 实测推翻 08-28 的「OpenAPI 能搜不能下 / 待打开 IMA 再拉」：`status` 仍报 `IMA_BRIDGE_OFFLINE`，但 `get --media-id` **能正常下载**（status 与下载走不同通道，不必先开 IMA）。两个真实的坑：①**单关键词会漏**——09-18 那份标题是「电话会 总结」，默认词「路演」搜不到；②**IMA 文件名的日期会错**——`20260902_路演调研全量总结.pdf` 正文自称 2026-09-03，早已作为 `2026-09-03.md` 入库（`#6837`），按文件名判缺档会重复入库 | 09-21 实拉 `20260915_路演调研_预期差.pdf`(4.3MB)、`20260918_电话会_总结.pdf`(1.3MB) 均 `ok:true`；管线收据见知识库仓 PR #156（matcher 31/3/137 与 37/4/271、`extract_tier_events --check` exit 0、974 项测试通过）；08-28 原始诊断见本文件 git 历史 |
| 卖方原文 | `wiki/raw/sellside/2026-08-17-调研纪要miracle.md`（`#5366`，2026-08-18 手贴入库） | 08-18 起无 miracle/原文。东方财富 RSSHub 快照更早停在 07-21 | **近月实写是手贴**，不是 launchd。`material-router` 已 frozen（2026-07 审计：日志零使用）。双盲 sellside/briefing plist 在 `~/Library/LaunchAgents/disabled-by-devin/`，属退役夜跑，不恢复 | 三层自动源都出不了货，手贴也停了 | 见下表 |

卖方自动源（2026-08-28 实测）：

| 通道 | 状态 | 证据 |
|---|---|---|
| `fetch_eastmoney_rsshub_sellside.py` → `localhost:1200` | 采集器不在跑 | `:1200` 连不上；仓内最后一份 `2026-07-21-东方财富RSSHub.md` |
| `fetch_sellside.py` → FinHot `items-all.json` | 公共快照空 | HTTP 200，`{"items":[],"total":0,"filter":"watch","generatedAt":"2026-08-23T07:03:45.851Z"}`；`--dry-run --date 2026-08-17/18/28` 均「无匹配」 |
| wechat2rss `:8090` | 已死（08-14 已登记，08-28 复核仍死） | 端口无响应；`com.finhot.wechat2rss-sync` 未加载；`~/wechat2rss-data/res.db` mtime 08-05 |
| wechat-download-api `:5050` | 进程健康、库仍空 | `/api/health` healthy；`rss.db` `articles=0` / `subscriptions=39`（mtime 08-22）；`#5365/#5366` 写明频控，8/6 后抓不到，改手贴 |

状态标签（2026-09-21 二次复核）：**晨汇 = 已补齐、无缺档；卖方 = 微信频控，待用户决策**。不要把两条线当成同一个故障。晨汇原料能自动拉（bridge `status` 报 offline 不影响 `get --media-id`），09-15 / 09-18 已于 2026-09-21 入库，9 月序列连续；卖方缺档仍是「无原文，禁止编造」。

## IMA 缺口清单断档与回填（2026-09-21）

`ima-gap-report` 自 2026-09-03 起静默停产，产物断在 `2026-09-02`。**断因不是脚本失败，是代码从没合进 main**：
09-03 主检出树前移到 `gitea/main` 时，`intelligence/services/ima_gap_report.py` + 测试连同 `cli.py` /
`daily_review.py` 的接线一起被保管进 `wip/mainline-move-footprints-20260903`（该 handoff 明写「不合 main，
归属者认领后自己决定」），无人认领，主树切到 main 后这一步随之消失。上表照登记着它——**台账说有、代码里没有**，
断了 19 天无人发现，下游一直吃 09-02 的旧清单（知识库仓 09-15 的入库提交仍写着「ima-gap 0902 积压」）。

回填口径（`fix/restore-ima-gap-report`）：接线移植回 main 后补跑 **09-07 / 09-09 / 09-14～09-18 共 7 天**。

- **回填清单不是当日快照**。`ima-gap-report` 拿当日 `research-queue.json` 去比**当前**知识库状态，补出来的是
  「以今天的 wiki 看，那天的队列里还缺什么」。对「现在该去 IMA 跑什么」这个用途口径是对的（已入库的会正确判成
  `skip_have_deepdive`），但**不能当作「当时该跑什么」的历史证据**。
- **09-03～09-06 / 09-08 / 09-10～09-13 永久补不了**：这些日期没有 `<date>-research-queue.json`，缺的是上游
  日报线，不是本步。

## 边界约定（去重复）

- **正式日报唯一真本源 = `<date>-daily-review.json`**（2026-09-03 起）：此前 `build_daily_review`
  算完全部结构化数据只落 md，Workbench 投影 / 聊天 skill / 框架解读各自反解 Markdown，都只解出
  核心看板那张两列表（实测 32,395 字 → 2,087 字）。现在 md 由 JSON 渲染、html 由 md 渲染，
  下游一律读 JSON；老日期没有 JSON 才退回 md，再退回 html。
- **复盘验证唯一落点 = `<date>.verdict.json`**：每日复盘假设的 hit/miss 回检统一走这里，
  不再手工重复登记进 foresight `checkpoints.jsonl`（后者只留日常问答里的个人判断校准）。
- **晨汇 T1/T2/T3 兑现回检并入 verdict**：晨汇命中项作为假设来源之一登记进当日 `verdict.json`，不另建表。
- **任何晚间卖方材料第一步永远落知识库仓 `wiki/raw/sellside/`**，之后 pdf-ingest / material-router /
  opinion-cross 各管线从那里取，产物去向不变。
- **观测台薄账是例外**：`docs/roadmap.md` 的 md 本身是 L0/L1 canonical（手写只许薄，
  硬顶 120 行），不是 JSON 的渲染物；任务层 L2 与运行曲线禁止手写，由生成器投影。

## 设计原理（教学）

- **单一录入口（single source of truth）**：同一事实只有一个写入位置，其余全是投影，
  否则多写入口必然漂移。这与数仓的「一个事实表 + 多张物化视图」是同一思想。
- **按日期分区 + JSONL**：天然幂等（重跑覆盖当日文件即可）、git diff 友好、可 `jq`/pandas 直读。
  替代方案是集中进 SQLite/DuckDB——查询更强，但与 git 审计流、Obsidian 可读性冲突，
  且写入者变多容易锁冲突；台账量级（每天几 KB）用文件分区足够。
- **写入者唯一**：等价于数据库的「单 writer 原则」，把竞态和格式漂移消灭在源头；
  人工修改走该脚本 CLI，保证 schema 校验始终生效。这在 CDC/特征平台设计里同样适用。

# 符合性缝普查（2026-08-29）

> 工单：`docs/superpowers/specs/2026-08-29-conformance-seam-census-workorder.md` 任务 A。
> 方法：走 AGENTS.md「宏观理解路由」六层地图（code_map / 能力图谱 43 节点 /
> 产品门 / DESIGN-stack / 闭环第一性原理 / ledger-map），rg 选段核对，不通读代码。
> 素材由子代理收集，落盘前对 P1/P2 各缝的接口定义行、实现清单、注册表计数做了抽查复核
> （DataBlockProvider 定义、PROVIDER_NAMES=20、sync_market_snapshot、llm_refine
> transport 字段与 cli 分支、DEFAULT_PROVIDERS=6、SkillExecutor Protocol，全部命中）。
>
> **判据**（与套件资产一并沉淀进 `~/harness-reference/TOOLKIT.md` A+ 节）：
> 一条缝 ≥2 个实现、且实现各自独立演化，才值得建参数化符合性套件；
> N=1 或纯配置开关登记「不够格及原因」，防后人重新发现。
> 「实现数」要数**装配面**：厂商配置槽共用同一传输层不算多实现（providers 链之教训）。

## 一、够格 / 已覆盖的缝

| 缝名 | 接口定义处 | 实现数与清单 | 漂移风险 | 已有散装断言 | 优先级 | 一句话理由 |
|---|---|---|---|---|---|---|
| 运行时后端 | `intelligence/services/agent_runtime.py:431`（AgentRuntime.run）/ `:443`（ResumableAgentRuntime.start）；名集 SSOT `research_profile.py:69-76`；解析 `agent_runtime_factory.py:53-63`；装配 `api/app.py:380-467` | 4+1：`GLMAgentRuntime`（glm_agent_runtime.py:453）/ `OpenAIAgentsRuntime` sdk_glm·sdk_gpt（openai_agents_runtime.py:910）/ `CodexHeadlessRuntime`（codex_headless_runtime.py:449）/ `DshStubRuntime` 厂外（dsh_stub_runtime.py:203） | 高：三类文件+stub，「拥有循环 vs 租用循环」按设计不等价 | test_glm_agent_runtime / test_openai_agents_runtime / test_codex_headless_runtime / test_dsh_stub_runtime / test_continuous_turn_adapter / test_agent_runtime_factory | — | **已建套件**（分支 test/runtime-conformance-suite，43p/3s/1xf） |
| 工具注册表 × ToolObservation | `research_tool_registry.py:48`（_DEFAULT_TOOL_METADATA，AST 数=12）/ `:457`（ToolObservation）/ `:514`（Registry） | 12 个 runner（finance_query…mainline_context），契约由注册表单点强制，漂移入口在生产装配面（build_episode_registry 换 schema/parse） | 高 | test_tool_behavior_contract / test_tool_produces_satisfiability / test_episode_tool_batch / test_episode_tools | — | **已建套件**（本分支 `intelligence/tests/conformance_tools/`，86p） |
| LLM transport（http × cli） | `llm_refine.py:106-112`（LLMProvider dataclass，`transport: str = "http"`）；调用契约 `complete()` `:788` 按 `transport` 分派；CLI 适配 `grok_cli_judge.py`（provider 构造 `:273` `transport="cli"`） | 2 个传输实现：HTTP OpenAI-compatible（`_post_chat`）/ CLI judge（`complete_grok_cli`） | 中高：两路的错误分类、超时、重试已分叉 | test_llm_provider_fallback / test_grok_cli_judge | **P1** | 同一 `(content, provider, reason)` 返回契约 × 两个独立演化的传输——按 transport 参数化，**不要**按厂商名参数化 |
| 行情快照 provider 链 | 编排 `market_snapshot_sync.py:59`（sync_market_snapshot）；尝试记录 `ProviderAttempt:30-41`；结果 `MarketSnapshotSyncResult:45-56` | 3+1：`duckdb_exact`（:104-145）/ `akshare_exact`（:150-245，子进程）/ `duckdb_latest` 回退（:256-298）/ 旁路 existing_complete（:76-99） | 高：分模块分进程分失败形状；partial 污染、滞后钳事故在案 | test_market_snapshot_sync / test_akshare_runtime_assets | **P1** | 「任一路发布的 snapshot 必须过 complete 不变量」正是抓静默降级的形状（2026-06-22 空壳回填同族） |
| 引擎 B 数据块 DataBlockProvider | `ask_planner.py:42-53`（DataBlockProvider：name/label/applies/collect）；机读名单 `evidence_registry.py:29-57`（REGISTRY→PROVIDER_NAMES，实测 20 名）；装配 ask.py `:4178+` | 20 个命名块，各自 applies/collect 闭包独立演化 | 高：与工具缝同形（一名一实现共用壳），门控/空结果/缺口声明易各自漂移 | 分散在 test_ask_* / test_evidence_*，无统一逐块契约套件 | **P1** | 形状几乎复刻工具套件三件结构，普查所见杠杆最高的未覆盖缝 |
| Workbench ArtifactProvider | `api/artifacts.py:103-104`（ArtifactProvider.discover） | 6：Run/Daily/Cockpit/Ledger/Matrix/Briefing（:201/:242/:290/:317/:354/:376；默认链 :411-417） | 中：扫不同目录但共享 ArtifactDescriptor 形状 | 未找到专项契约套件（检索无命中，覆盖情况未能确认） | P2 | 够格但属制品发现层，金融正确性杠杆低于上三条 |
| Workbench SkillExecutor | `workbench_skills/contracts.py:294-297`（SkillExecutor.execute） | 7 个 skill_id / 4 个类：DailyReview（daily_review.py:95）/ DailyAgent（daily_agent.py:49）/ UsAiDrawdown（us_ai_drawdown.py:26）/ ResearchOwnerSkill×4 id（research_owner.py:87，registry.py:150-225） | 中：前三类独立文件；后四个共享类内按 skill_id 分叉 | test_workbench_daily_skills / test_workbench_research_owner_skills / test_workbench_skill_router | P2 | 够格；可对 SkillOutput 公共字段做薄符合性。注意与仓内技能桥（N=1）不是同一缝 |

## 二、不够格名单（防重新发现，每条带理由与出处）

| 候选 | 为何不够格 | 出处 |
|---|---|---|
| 技能桥 `skill_tools` | N=1（仅 serenity-alpha），刻意的设计约束——扩注册表须先论证只读红线 | `skill_tools.py:167-176` |
| 判官链 `CONTINUOUS_VERIFIER_CHAIN` | 串行两段**异接口**流水线（函数 `verify_episode_outcome` + Protocol `SemanticVerifier`），段内各 N=1，不是一名多实现 | `research_profile.py:93-96`；`episode_verifier.py:62`；`continuous_turn_adapter.py:144`；`episode_semantic_verifier.py:663` |
| `--kb-mode` / `--wiki-rag-mode` | 同一 `retrieve()` 管线的 mode/index 旋钮（structured→hybrid / full→rerank），非多后端类；产品门标为逃生口 | `kb_rag.py:198-233`；`intelligence/cli.py:13-37` |
| `detect_providers` 多厂商名 | 8 个配置槽 + custom + managed 共用同一 HTTP `complete` 路径——厂商切换是配置不是实现（真正独立演化的是 transport，已单列 P1） | `llm_refine.py:94-103`（_PROVIDERS）/ `:185+`（detect_providers） |
| `FollowupComposer` | Angle + Null 两实现，但 Null 是 env 杀开关桩，非对等演化后端 | `followups.py:115-133` |
| `SubResearchWorker` | 生产仅 `ContinuousSubResearchWorker` | `sub_research.py:249`；`continuous_sub_research.py:20` |
| `ContinuousTurnHandler` | 生产仅 `ContinuousTurnAdapter.handle` | `conversation_orchestrator.py:172`；`continuous_turn_adapter.py:274` |
| `HungerSink` / `RootBudgetLedger` / `EventSink` / `EpisodeSession` / `KeychainBackend` | 生产侧实质 N=1（测试桩不算实现） | `tool_hunger.py:35`；`research_contract.py:461`；`episode_scope.py:112`；`episode_session.py:19`；`keychain_credentials.py:27` |
| `ToolPipeline` Protocol | 协议已立但生产完整实现数未能确认 ≥2 | `episode_scope.py:449` |
| 引擎 A vs 引擎 B | 产品门的两条引擎**接口不同**（Episode vs answer_query），不是同 Protocol 多实现 | `docs/agent-product-door.md` |
| 台账（ledger-map 全体） | **故意唯一写入者**，多写是反模式；契约测试应做 schema 棘轮而非参数化多后端 | `docs/learning/ledger-map.md` 表头约定 |
| closed_loop narrow/broad/counter | 同一 `retrieve_closed_loop` 的三趟孔径 | `closed_loop_retrieval.py:15,190+` |
| `dsh_stub` 单独成缝 | 刻意不进 factory 名集，已并入运行时套件叙事 | `dsh_stub_runtime.py:21-22` |
| `FrameLike` / `CninfoFetch` / `_FinalizerJudgeProvider` | 局部鸭子/最小缝，实现数未能确认 ≥2 独立演化 | 各 Protocol 定义点（普查素材 Protocol 清点表） |

另：`market_feature_store/` 无 `Protocol`/`ABC`/`runtime_checkable` 命中——写入侧的可替换性由快照分代机制（VIEW+generation 表）承担，不是接口缝。

## 三、产出的后续工单队列

- **P1 × 3 已立占位单**（登记于 backlog INDEX 续表）：
  `2026-08-29-llm-transport-conformance-workorder.md` /
  `2026-08-29-market-snapshot-conformance-workorder.md` /
  `2026-08-29-datablock-conformance-workorder.md`
- P2 × 2（ArtifactProvider / SkillExecutor）：登记于此，不立单——按判据够格但杠杆
  低于 P1 三条，等 P1 消化后再评估。
- 本轮无 P0：两条 P0 级缝（运行时后端 / 工具注册表）已分别建成套件。

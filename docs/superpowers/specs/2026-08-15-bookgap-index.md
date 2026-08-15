# 书距清单：kb + finance 两仓对照 ai-agent-book 的升级 spec 索引

- 日期：2026-08-15 · 作者：检阅方（triage loop 同一人）
- 对照对象：`~/ai-agent-book`（bojieli/ai-agent-book，检索源之一）；
  依据文件：`docs/superpowers/2026-08-10-agent-book-chapter-audit.md`（按章审计）、
  `docs/superpowers/specs/2026-08-13-memory-quality-review.md`（记忆质检 Q1–Q9）、
  triage loop 母本 `docs/handoffs/2026-08-15-runtime-trace-triage-loop.md`（近五轮实测）。
- 用法：每份 spec 自包含，可独立派给一个 agent。**开工前必读本文 §2 冲突矩阵**，
  它决定哪些能并行、哪些必须等谁。

## 0. 共同纪律（每份 spec 默认继承，不再重复）

1. 独立 worktree + 独立分支，禁止动主 checkout；PR 走 gitea
   （`http://localhost:3300`），合并用创建响应返回的编号。
2. 解释器一律 `~/finance-workspace-private/.venv-workbench/bin/python`
   （宿主 python3 无依赖）；KB 仓另有 `.rag_venv`。
3. 单变量纪律：一份 spec 一个缝，发现相邻缺陷登记不顺手修。
4. 验收判据先写死再动手，事后不改口；每条结论带 source_ref。
5. 生产 8792、启动器、软链只读；需要部署验证的，交付「部署就绪」状态
   由用户/检阅方裁决切换。
6. KB 仓（`~/knowledge-base-private`）内工作遵守其 AGENTS.md：教学模式
   （讲原理+选型对比）、大 JSON 走 `query_relations.py`、禁 cat 大文件。

## 1. 清单总览（优先级 = 证据强度 × 影响面）

| # | spec | 靶（书章 / 实测） | 目标仓 | 主缝 | 优先 |
|---|---|---|---|---|---|
| S1 | 时间预算可见（状态栏 v1） | 第 2/10 章 🔴；08-09 全天超时的解释 | finance | `agent_episode.py` | **P0** |
| S2 | judge 模态切换（数据源回查） | 第 10 章 🔴「判卷不引入新信息」 | finance | 新模块 + verifier 一行钩子 | P2 |
| S3 | 超时窗口比例化 | 08-10 审计「正解=按 reserve 推导」 | finance | `research_contract.py` 等 | P1 |
| S4 | recall@k 标注集（双仓） | 第 3 章 🔴；质检 Q1/Q2 | 双仓 | 纯数据+文档 | **P0** |
| S5 | 独立出题人评测集 | 第 6 章 🟡 抗泄漏 | finance | 纯数据+文档 | P1 |
| S6 | user_memory 离线候选更新链 | 第 8 章 🔴「验证后再发布」 | finance | services 记忆面 | P1 |
| S7 | 行情同步写锁消除 | 批 #2 塌方根因（今晨实测） | finance | `market_feature_store/` | **P0** |
| S8 | 记忆质检 Q3/Q4/Q7/Q8 清扫 | 质检遗留 | finance | services 记忆/时间线 | P2 |
| S9 | KB Hybrid 检索加 rerank + 评测闭环 | 第 3 章；KB 学习重点自述 | kb | KB `scripts/` + `.rag_index` | P1 |
| S10 | branch_tool 激活诊断（子研究分支为何从未被走进） | 第 10 章 + 马书 ch20；08-14 实测三次未进路径 | finance | Phase A 纯诊断（EVAL_ONLY）；Phase B 视 PRIMARY 而定 | P2 |

## 2. 冲突矩阵（派工前必读）

**立即可并行（互不相交，也不碰在飞工作）**：S4、S5、S6、S7、S8、S9。

**有串行依赖**：

| spec | 等谁 | 原因 |
|---|---|---|
| S1 | `feat/dsh-absorption-p0-seams`（dsh 吸收 P0）落地或确认未开工 | 同文件 `agent_episode.py`（该 spec §11 第 2–5 步）。开工前 `git log gitea/feat/dsh-absorption-p0-seams` 查状态；若未开工，先到先得并知会对方 rebase |
| S2、S3 | R-24（E-007 修复，裁决在下个部署窗）落地后 | 同文件 `episode_semantic_verifier.py`。S2 只加回查钩子、S3 只改 `_judge_window` 推导，函数不相交，S2/S3 之间可先后紧邻，但都别与 R-24 并行 |
| S10 Phase A | 无（纯诊断可即开，live 批遵守锁） | 判据 H2（预算不可见抑制分支）不许在 S1 落地前结案为 PRIMARY，见 spec §4 |
| S10 Phase B | S10 Phase A 出 PRIMARY + dsh 第 5 步与 S1 落地后 | 若动 `agent_episode.py` 与两者同文件；`NO_SYSTEM_FIX` 结论则无 Phase B |

**在飞工作占用的缝（所有 spec 都不许碰）**：
`intelligence/eval/acceptance.py`（triage loop 批 #3 读数中）、
`episode_protocol.py` + `agent_episode.py`（dsh P0，除 S1 按上表处理）、
`episode_semantic_verifier.py._marker_loss_partial_public`（R-24 保留地）、
`docs/handoffs/round5-*` 与账本他人行。

## 3. 交付统一格式

每份 spec 的执行 agent 交付：实现 PR（或纯数据 PR）+ 验收判据逐条对勾
（带 source_ref）+ ≤10 行小结追加到本索引 §4。判据抽验不中即打回重做。

## 4. 执行记录（各 agent 追加）

### S5 · 独立出题人 uq15 ｜ 2026-08-15 ｜ 分支 data/bookgap-s5-uq15

- 交付：15 题（盘面4/归因4/链条4/反证3）`intelligence/eval/cases/uq15_questions.jsonl`；sha256×15 `uq15_rubric_hashes.json`；判分协议 `2026-08-15-bookgap-s5-uq15-protocol.md`。
- rubric 密封仓外交用户保管（含 MANIFEST 与抽验命令），出分后入仓公开；哈希先行入仓防"看题优化"。
- 隔离已守：未读 `intelligence/eval/cases/` 既有内容、`docs/verification/`、runtime 源码；已读路径全清单在协议 §6。
- 素材面：KB wiki 概念/实体页 + DuckDB 只读（鲜度至 08-14）+ `.foresight` 用户台账（判分产物类文件刻意未读）。
- 反证题埋点：蓝盾光电 5 板题材归类 vs 基本面、周六时间边界、蓝思"拟收购"证据硬度，均带一票否决。
- 待下游：跑批方/判分方按协议 §1 角色隔离执行；qc28 未读未动、不替换。

### S5 · QC-1 勘误补丁 ｜ 2026-08-15 ｜ 分支 data/bookgap-s5-uq15-qc

- 第一方复验：验收 1 不中（entities 越界 + q07 假前提）；不 revert #33，不改密封 rubric/哈希。
- 题面：q07 去掉「持续走强」；q09 换成医疗服务链条（拆光纤簇 6→5）；q14 `context` 只留时间句，指令改 `runner_note`。
- 勘误：`intelligence/eval/cases/uq15_errata/`（scoring / q06 KP4 / q07 / q09 整题 / q14）；验封后施加，冲突以勘误为准。
- entities：协议 §8 书面批准 q06/q13 为例外；后续新题仍默认 concepts/sources。
- 计分：废止「就高给分」（未满分 +1 封顶）；q15 KP3 改为 1 或 3。
- 待下游：判分方验封 → 读 errata → 再打分。

### S8 · 记忆质检 Q3/Q4/Q7/Q8 清扫 ｜ 2026-08-15 ｜ 分支 bookgap/s8-memory-qa-sweep

- 四条独立提交（可单独 cherry-pick）：Q3 `4ce0ce56` / Q4 `f4680c8c` / Q7 `99d3b7bd` / Q8 `e932cdef`；Q9 状态行 `5c1982ef`。
- Q3：新行 `id=sha256(kind+ts+content)[:12]`，退出 id/ts 双键；旧行不迁，仍按 ts 退出。source_ref: `test_memory_status.RecordIdentityTests`。
- Q4：`contract_missing_outputs` → `repair_coordinator.missing_outputs` 词表；`contract_receipt.missing_outputs` 恒在场。prompt 零改动。source_ref: `test_track_contract.ContractMissingOutputsTests`。
- Q7：「液冷」→`液冷概念`（复用 `resolve_query_themes`）；解析不到仍显式降级。source_ref: `test_theme_lifecycle_timeline.LoaderTests.test_colloquial_alias_resolves_via_resolve_query_themes`。
- Q8：固态电池 08-13 夹具 25→20 段，无 <3 日段。被合并：发酵2025-01-14~15、回流2026-07-01~02、回流2026-07-21~22。source_ref: `SolidStateBatteryLiveFixtureTests`。
- 记忆面单测 77 passed（`test_memory_status` / `test_track_contract` / `test_theme_lifecycle_timeline` / `test_market_regime_analogs`）。未碰 `memory_gate` / experience cards 退出 / D10 / 保留缝。

### S7 · 行情同步写锁消除 ｜ 2026-08-15 ｜ 分支 bookgap/s7-sync-lock-elimination

- 方案 A：APFS clonefile 3.4G = 0.01–0.07s（盘余 188G，不选 B）。`daily-full` 写同卷 staging → 校验 → `os.replace`；子进程 env 重定向，生产库全程无写锁。
- 判据 1：现状臂 rw 持锁时跨进程 read_only 必败（单测）；staging 臂每秒探针 892 次 **0 失败**（隔离 3.4G 真同步 20min）。source_ref: `test_market_feature_store_staging_swap` + `/Users/a77/fwp-wt-artifacts/s7-e2e/probe.jsonl`。
- 判据 2：子进程 SIGKILL / 无 status.json 均不换名，生产字节不变。source_ref: `test_sigkill_during_staging_leaves_production_bytes_unchanged` / `test_crash_without_status_json_does_not_swap`。
- 判据 3：换名 0.266s（mtime 窗口远小于 5s）；收据 `ops_sync_run.run_id=9c1dd5e59dbf`（clonefile 0.066s / 1212.8s / ok）。
- 判据 4：周六隔离副本真同步 rc=0，抽 3 表 count 与开工前一致（`fact_market_daily` 400 / `fact_stock_daily` 2026538 / `fact_limit_advance_daily` 4737）。未动生产库、未动 `finance_query.py`。
- 部署就绪：8792 不切；生产 `daily-full` 换本分支后锁窗从 ~14min 变换名瞬间。dragon_seats 回补等旁路 `sync-*` 仍直写生产库，不在本缝。

### S4 · recall@k 标注集 v1 ｜ 2026-08-15 ｜ 分支 bookgap/s4-recall-annotation-set-r2

- 交付：20 条真实标注入 `intelligence/eval/cases/retrieval_recall_v1.jsonl`；口径文档收口 Q2（生产 @k=每通道 k）。
- user_memory 15 条 recall@5=42.2% / hit@5=46.7%；experience_cards 3 条 hit@5=100% recall@5=83.3%；kb_rag 2 条本窗与 S9 抢索引超时、记通道不可用非 0 分。
- 08-09 S3 定性：**三已挂通道上是题目超纲**（库中无该周可核验主因；因果通道 news_search 未挂尺）。基线 `docs/verification/2026-08-15-recall-baseline.md`。
- 本分支为 #38 在 S7 合入后的 rebase 副本（原分支 `bookgap/s4-recall-annotation-set` 不强推）。

### S6 · user_memory 离线候选更新链 ｜ 2026-08-15 ｜ 分支 bookgap/s6-memory-candidate-loop-r2

- 交付：`intelligence/services/memory_candidate_loop.py` + `scripts/run_memory_candidate_loop.py`；生命周期 `docs/learning/memory-candidate-lifecycle.md`；`ledger-map` 已登记 `memory_candidates.jsonl`。
- v1 规则：`repeated_correction_same_theme`（同主题 ≥2 条同向纠偏）/ `verdict_overturned_by_user`（机判终态被人工翻案）；宁缺勿滥。
- 验收 1：夹具产 ≥1 候选，归因链含 `source_record_ids`/`trigger_rule`/`generated_at`；`--dry-run` 不落盘。source_ref：`test_run_accepts_candidates_with_full_attribution` / `test_dry_run_writes_nothing`。
- 验收 2：同一台账重跑第二次零新候选。source_ref：`test_second_run_produces_zero_new_candidates`。
- 验收 3：gate 拒绝留档带理由；durable 只经 `record_validated_*`（拔掉写入口或 `promotion_metadata` 则零 durable 写）。source_ref：`test_gate_rejection_is_archived_with_reason` / `test_durable_writes_only_go_through_gate_api`。
- 验收 4：给 accepted 经验，`trace --candidate-id|--sha|--content` 一步查到来源 ids。source_ref：`test_trace_by_candidate_id_and_content_sha` / `test_cli_run_trace_roundtrip`。
- 边界：未改 `memory_gate.py` / `memory_status.py` / 检索器；候选不自动 accepted。单测 16 passed（含 S8 的 main 上重跑）。本分支为 #34 在 S7/S4 合入后的 rebase 副本（原分支不强推）。

### S9 · KB Hybrid + rerank 评测闭环 ｜ 2026-08-15 ｜ 分支 feat/bookgap-s9-rerank-eval

- 仓：knowledge-base-private。`--rerank on/off` / `RAG_RERANK`，默认 off；权重不进 git（`download_reranker.py` + sha256）。
- 四臂（`queries.real.jsonl` n=40，干净 `.rag_index`）：bm25 hit@5=0.85 / dense 0.825 / hybrid **0.80** / rerank **0.65**（回退 9 / 改善 3）。
- 结论：**不上线**。rerank_ms_p50=62.5s（CPU；16GB 避 MPS+双模型 swap）。8792 保持 off。
- source_ref：KB PR http://127.0.0.1:3300/a77/knowledge-base-private/pulls/12 ；`eval/rerank-ab-20260815.md` sha256 `f64e7d8d373fa6dd8f948c3fe502a0f28e6801311cf103d7d460bb1555934aa1`。
- 判据：1 否定结论合格 / 2 超 500ms 已给降级 / 3 off 旁路单测 PASS / 4 选型文档 PASS / 5 权重不进 git。
- 质检 2026-08-15 23:13：独立重算 hit@5（32/40 vs 26/40）、JSON sha256、单测 24、默认 off、权重未入 git、8792 仍 `fdb231`。**PASS**，合入后仍不上线。

### S10 · branch_tool 激活诊断 Phase A ｜ 2026-08-15 ｜ 分支 eval/s10-branch-activation

- 形态：EVAL_ONLY。报告 `docs/verification/2026-08-15-s10-branch-activation.md`；夹具 `intelligence/eval/cases/s10_branch_eligible_tasks.json`（`frozen_at=2026-08-15T23:42:08+08:00`，N=5）。
- 冻结窗调用率 1/5（B4=`run_20260815_182037_434217` 9 次 `branch_tool`）。08-14「三次未进路径」不能当全集基线。
- 结论：`ROOT_CAUSE_NOT_CONFIRMED`。H1/H3/H4/H5 REJECTED；H2 INCONCLUSIVE（S1 前不得 PRIMARY）。未改 prompt / 工具描述 / 路由 / `episode_semantic_verifier.py`。
- 账本：`R-20260815-26`（EVAL_ONLY，pending）。Phase B 候选 R-027/R-028 未进 Open。
- 判据：1 失败标准先冻结后取证 / 2 假设逐条判定且未硬选 PRIMARY / 3 H2 未结案 / 5 未碰保留地。

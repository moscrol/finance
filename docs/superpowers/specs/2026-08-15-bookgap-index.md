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

## 2. 冲突矩阵（派工前必读）

**立即可并行（互不相交，也不碰在飞工作）**：S4、S5、S6、S7、S8、S9。

**有串行依赖**：

| spec | 等谁 | 原因 |
|---|---|---|
| S1 | `feat/dsh-absorption-p0-seams`（dsh 吸收 P0）落地或确认未开工 | 同文件 `agent_episode.py`（该 spec §11 第 2–5 步）。开工前 `git log gitea/feat/dsh-absorption-p0-seams` 查状态；若未开工，先到先得并知会对方 rebase |
| S2、S3 | R-24（E-007 修复，裁决在下个部署窗）落地后 | 同文件 `episode_semantic_verifier.py`。S2 只加回查钩子、S3 只改 `_judge_window` 推导，函数不相交，S2/S3 之间可先后紧邻，但都别与 R-24 并行 |

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

# 工单：跨仓 kb-ingest 队列消化（08-26/27/28 三批 + triage 升级两条）（P0-P1）

- 状态：**已执行（2026-08-29：活库已 receive 08-26 并 mark 三批终态；树 `/Users/a77/kb-wt-queue-drain-0828`，分支 `theme-radar/kb-queue-drain-0828` @ `7df6ff2a`，log `#6823`；未合 main）**
- 目标仓：`/Users/a77/finance-workspace-private`（发送端）+ `/Users/a77/knowledge-base-private`（接收端）
- 来源：2026-08-28 欠账盘点。
- 优先级：**P0-P1**——这是当前最大的一笔「知识批量」欠账，且金融仓每日队列会继续叠加。

## 0. 一句话

金融仓近三日产出 27 条 kb-ingest 任务：08-26 的 11 条**从未 receive 到知识库侧**（当日工作流 FAIL 连锁），08-27/28 的 16 条已 receive 但停在 `received` 未处理；另有 triage 升级两条（医药概念页升 L1、乡村振兴判断是否建页）需要人工做。

## 1. 证据与状态修正

- 发送端队列：`market_feature_store/exports/2026-08-2{6,7,8}-kb-ingest-queue.json`（11 + 8 + 8 条，task_type 含 concept_ingest / disclosure / entity_delta）。
- 接收端台账：`<kb>/wiki/raw/cross-repo-ingest-queue/`——**没有 2026-08-26 目录**（未 receive）；`2026-08-27/`、`2026-08-28/` 的 `status_log.jsonl` 只有 receive 归档一条。
- triage 报告：`<kb>/wiki/raw/cross-repo-ingest-queue/reports/ima-triage-2026-08-28.md`：
  - `escalate_stub` · 医药：概念页占位待升 L1，不自动写正文。
  - `escalate_missing` · 乡村振兴：无概念页，8/16 口径不空建，需人工判断。
  - 其余 14 条 `leave`：非 concept_ingest，转 disclosure/entity 管线。
- ⚠ **状态修正**：08-17~21 各批在 `status_log.jsonl` 里已被处理为 `skipped`（附理由，如「库内已有完整概念页」「8/16 口径不空建」），**不是积压，不要重做**。08-13 已基本 done。

## 2. 范围

**做**：① receive 08-26；② 对三批任务逐条给出终态（ingested / skipped-带理由 / 转管线），写回各日 `status_log.jsonl`；③ 处理 triage 两条升级项。

**不做**：`leave` 类 disclosure/entity 任务只登记转出、不在本单执行（归《disclosure 治理》工单及 entity-delta 管线）；不批量新建概念页；不自动 `--apply` 任何实体正文。

## 3. 步骤

1. 开工自查（两仓都要）：`git status --short && git branch --show-current`。知识库仓大任务开分支（如 `theme-radar/kb-queue-drain-0828`）。
2. Receive 08-26：
   ```bash
   python3 -m intelligence.cli kb-queue-receive --date 2026-08-26 \
     --finance-root /Users/a77/finance-workspace-private \
     --kb-wiki /Users/a77/knowledge-base-private/wiki
   ```
   完成判据：`<kb>/wiki/raw/cross-repo-ingest-queue/2026-08-26/` 出现队列 + receipt + status_log。
3. 逐条分诊三批任务（流程规范见 `<kb>/docs/cross-repo-ingest-queue.md`）：
   - concept_ingest 类：按知识库仓 `skills/concept-ingest/SKILL.md` 走 ingest-plan → writer；已有完整概念页且无新核验材料的记 `skipped` 并附理由。
   - disclosure / entity_delta 类：status_log 记「转 disclosure/entity 管线」，把清单交给对应工单认领人。
   完成判据：三批任务在 status_log 里每条都有终态，没有一条停留在 `received`。
4. triage 升级两条：
   - **医药**：把占位概念页升到 L1（题材边界、产业链位置、核心公司分层），材料不足则先跑 IMA DeepDive 闭环（见《IMA DeepDive 切片》工单），不许拿占位页硬凑。
   - **乡村振兴**：先判断题材是否过宽（8/16 口径）。判定「过宽只观察」则 status_log 记 skipped + 理由；判定值得建页则走完整 concept-ingest 闭环，禁止空建骨架页。
5. 知识库仓提交：pathspec 只提本单产生的文件（status_log、概念页、relations 变更），commit 前跑 `python3 scripts/check_relations_integrity.py`（若涉及 relations）。

## 4. 验收

1. 08-26/27/28 三个日期目录的 status_log.jsonl 中，任务终态数 = 队列任务数。
2. 医药、乡村振兴两条在 status_log 或概念页里有可追溯结论。
3. 转出给 disclosure/entity 管线的清单已写进交接（条数 + task_id）。

## 5. 红线

- 概念页不空建、同题材不重复 IMA（8/16 口径）。
- broker 二手材料不进 `## 边际变化`；curated_research / graph_only / observation_only 三路由按 CLAUDE.md「PDF ingest 对齐基准」。
- 知识库大 JSON（relations/）用 `query_relations.py` 查，不 cat。
- 禁 `git add -A`，pathspec 提交，不合 main 不推。

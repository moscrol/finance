# 工单：IMA DeepDive concept-ingest 队列按题材切片消化（P2，量大慢做）

- 状态：**进行中**（2026-08-28 切片1：原料药 #6824 已升 L1；CRO 队列关账；数字货币 IMA OFFLINE。交接 `knowledge-base-private` 树 `/Users/a77/kb-wt-ima-slice-0828`）
- 目标仓：`/Users/a77/knowledge-base-private`
- 来源：2026-08-28 欠账盘点。用户确认 IMA DeepDive 未补齐。
- 优先级：**P2**——存量最大（590 candidates），按题材切片、多会话分批，不追求一次清完。

## 0. 一句话

知识库仓积压 18 个题材的 IMA concept-ingest 队列共 590 个 candidates，外加两个零散在途（减肥药 ingest-plan、贵金属 concept-delta）；按「盘面触发优先」排序切片消化，每个题材走完整 DeepDive 闭环。

## 1. 证据

- 主积压：`wiki/raw/theme-radar/*.ima-concept-ingest-queue.json` 共 22 个文件，其中 18 个有 candidates（合计 590），4 个为空。
- 零散在途：
  - `wiki/raw/ima-daily-gap/2026-08-15/ingest-plan.json`：新建「减肥药」概念 + 若干 must_write delta，plan 已成待执行。
  - `wiki/raw/ima-queue/2026-08-22/concept-delta-贵金属.json`：一份 concept-delta 待 ingest（08-21 已有 #5401 贵金属占位升 L1 的前置）。
- 排序参考：金融仓近三日 research-queue 标了 L1/L2 缺口的盘面触发题材（医药、数字货币、光通信、EDA、信创等），见 `market_feature_store/exports/2026-08-2{6,7,8}-research-queue.md`。

## 2. 范围

**做**：① 两个零散在途先清掉（有现成 plan，最快见效）；② 主积压按「近三日盘面触发 ∩ 队列存量」选前 2-3 个题材做完整闭环；③ 其余题材只重排优先级留游标。

**不做**：不一次性消化 590 条；不跳过 ingest-plan 直接 writer；不给没有 DeepDive 材料的题材现编内容。

## 3. 步骤

1. 开工自查：`git status --short && git branch --show-current`。开分支 `theme-radar/ima-slice-<题材>`。
2. 清零散在途：
   - 减肥药：按 `ingest-plan.json` 执行 concept ingest + must_write delta（`python3 scripts/ingest.py concept ...`）。注意 08-13 批次记录「减肥药归档 3 条 L2 未 apply」，执行前核对是否同批材料，避免重复写。
   - 贵金属：按 concept-delta JSON 走 ingest；#5401 已升 L1，本次是增量 delta，「不抄未核 IMA 数字」的前置判定继续有效。
   完成判据：两个在途文件对应的写入完成或标记 skipped-带理由。
3. 选片：把 18 个队列文件的题材名与近三日 research-queue 触发题材求交集，选 2-3 个（预期命中：医药、数字货币一类）。在交接里写明选片理由。
4. 每个题材走完整闭环（顺序不可跳步）：
   ```
   Copilot 15 章 prompt → deepdive.md → python3 scripts/build_ima_concept_ingest_queue.py <deepdive.md>
   → 人工 ingest-plan → python3 scripts/ingest.py concept ...
   ```
   - 队列文件里已有 candidates 的，仍需人工 ingest-plan 逐条过（candidates 是候选不是结论）。
   - **禁止搜标题当抽取；禁止有 md 直接 writer。**
   完成判据（每题材）：概念页 L1 齐（边界/产业链位置/核心公司分层）、对应队列文件 candidates 清零或余量标注原因。
5. 未选中的题材：按触发热度重排优先级，游标写入交接。
6. 提交：pathspec，每题材一个 commit；涉及 relations 跑 `python3 scripts/check_relations_integrity.py`。

## 4. 验收

1. 减肥药、贵金属两个在途终态可追溯。
2. 选中的 2-3 个题材：概念页、relations、队列清零三者对得上。
3. 交接含：590 的最新余量、各题材优先级排序、下个切片建议。

## 5. 红线

- IMA 数字未经核验不落正文（「不抄未核 IMA 数字」）。
- 8/16 口径：不空建、同题材不重复 IMA。
- broker/二手材料路由按 curated_research / graph_only / observation_only 三分。
- 禁 `git add -A`；不合 main 不推。

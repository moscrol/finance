# 研究意图边界修补（分支 `fix/research-intent-boundaries`）

一句话：**R-20260916-05 实锤的三类「运行时听错用户」缺陷已修完；2026-09-17 独立 QC 补了三族
同形漏洞 + 第三道闸独立断言，并在本树 sidecar 上真跑一臂复测通过；已提交到分支，未推送、
未合并、未部署 8792。**

- 树 `/Users/a77/fwp-wt-research-intent-boundaries`，base `gitea/main@d433b907`，2026-09-17 已前向合并
  `gitea/main@ce009718`（0 冲突，无同文件重叠）；
  权威说明 `docs/verification/2026-09-16-research-intent-boundaries.md`（QC 复核节 + 真实会话复测节）；
  解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`

## 改了什么（4 源文件 + 1 测试 + 2 文档）

| 文件 | 改动 |
|---|---|
| `services/track_contract.py` | `persistence_opt_out()`（否定+登记动词+跟踪宾语三件套、同小句；QC 加：间隔禁「忘/漏/遗/只」、否定词前禁「要/需/用」）、`calendar_month_due()`（QC 收紧：年写法必带月、后不接数字；`-`/`/` 后不接分隔符或数字）、`chinese_full_date()`（两本 contract 共用）；`parse_track_intent` 先扣退出声明；`ingest_next_watch` 早退 |
| `services/ranking_contract.py` | `ingest_flip_conditions` 早退；`_due_from_watch` 日历月排在时长前、中文全日期用共用推导 |
| `services/user_task.py` | `_reads_like_document()` 只认结构性材料标记；QC 把它加到另外两条切分分支 |
| `runtime/conversation_orchestrator.py` | `_ingest_track_next_watch` 早退（第三道闸） |
| `tests/test_research_intent_boundaries.py` | 21 项；夹具用 R05 冻结题面原文 |

## 验证到哪一步

- TDD：QC 用例先在第一版代码上 5 红 / 15 绿，再修到 21 绿。逐层变异五轮，每轮只红自己那族。
- 全量 `intelligence/tests` 9733P/0F/19s/2xf；Ruff / `diff --check` 通过。
  合并前在分支尖重出收据：`check_test_receipt.py --expect-revision <尖>`。
- 真实会话：sidecar 8824（本树、隔离用户、RAG worker 关）summary 臂 214s completed，答案含改判条件表，
  `checkpoints.jsonl` **未创建**；frame `financial_analysis`/中际旭创/materials=0。
  原件 `~/.finance-runtime/intent-boundaries-qc/R-20260917-QC/`。
- **没做**：未部署 8792；mechanism 臂只有离线重放（与 summary 臂 frame 逐字段相同）；未盲评。

## 被否掉的方案（别再走一遍）

1. 提示词里加「禁止登记」：R05 已证无效，答案照抄承诺、运行时照写。
2. 直接关 `parse_track_intent`：废掉正常跟踪题。表达纪律与持久化是两根轴。
3. 用 `_MATERIAL_MARKER_RE` 判文档头：含「研报/公告」普通名词，提问说「请使用公告」就命中。
4. 退出宾语表加「观点/判断」以接 `judgments.jsonl`：撞「不作为投资建议」免责句，误杀。

## 下一步

1. 推送 + 开 PR（等用户确认）；合并前分支尖收据 + conflict-check。
2. 未修项见验证文档「明确没有修的」与「仍然知道但没动的边界」，先攒误杀样本集再动门禁。

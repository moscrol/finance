# docs/workorders-index-hole · 2026-09-16（QC 返修轮）

## 状态：🔧 QC 六条返修已做 + 已前向合并 main@43330ef2，待重开验收 / 待用户拍合并

- **PR #744 开着**（09-13 开；旧三张 #666 / #664 / #594 已关，接替指针都指向本 PR——本 PR 若废弃，须为三张内容另留去处）。
- 09-13 独立质检裁决「需要修订」（F1–F6，全文在 PR #744 评论）；本轮（09-16）逐条返修，映射见 PR 追加评论。
- 门禁读数与被测 SHA **只记在 PR #744 的返修评论与钉名收据文件**（`~/.finance-runtime/test-receipts/<ts>-<treesha>.json`），本交接不复制数字，避免 F5 那类「收据身份不是当前尖」复发。

## 这轮做了什么（两个提交）

1. **前向合并 `gitea/main@43330ef2`**（合并提交 ed1919f1，机械解冲突、以 main 为底）：
   - INDEX：#21–#25 / #51 / #53 取 main 的 09-15、09-16 新状态；插回本分支独有行 **#26、#52**；把本分支对 #21（P1 lifecycle 工单文件指针）、#22（步骤 5 已立单 #26、交接路径改归档位）的修正移植到 main 版行上。**现 34 行、编号 20–53、唯一升序**。
   - UBIQUITOUS_LANGUAGE：错位标记与 `opinion_stage` 版本行取 main（`tsm-v1` / v6）；保留本分支「产品终局（时间长河）」词表节。
2. **QC F1–F6 内容返修**（合并后单独一个提交，便于分开评审）：
   - F1：`index_stage`「尚未编码」改为已编码（`intelligence/services/teaching_framework/index_stage.py`）；「舆论生命周期词表尚未钦定」改为已钦定（#671）；同族顺手修「题材生命周期两套词表」（#673 后是单一词表 `tsm-v1`）与 `market_stage` 行的「要编码」时态。
   - F2：INDEX #38 优先级理由标注已失效；#39 删掉「#567/#568/#669 合入等用户拍」假待办；roadmap 五个「待合入」块（#673/#671/#670/#667/#674）全部改已合入 + SHA。
   - F3：`retrieval-budget-refill-workorder` 两处交接引用改归档路径；INDEX #33 与 `market-history-backfill` 工单里的 mcnemar 读数文件标注「随 PR #660 在途，main 尚无」。
   - F4：INDEX #36 与 roadmap 写明版本链 v4 → v5（#49/#738）→ v6（#673），新增 lifecycle 类标签在 v6 之上取下一版。
   - F6：本文件覆写为当前真值。

## 已知例外（记录，不擅自处置）

- `2026-09-08-hithink-finance-ingest-workorder.md` 在 main 的 specs/ 里存在但 **无 INDEX 行**；且它自称「工单 #41」，与 INDEX #41（sandbox-derived-calculation）撞号。活本身已由 PR #717 执行（同花顺 API 接入 A–D）。**编号怎么给（补新号 / 承认撞号并注记）待用户拍**，本 PR 不代裁。

## 合并前检查单（给验收 session）

- `git merge-tree --write-tree gitea/main <本分支尖>` 应 exit 0（本轮已并到 43330ef2；main 再动 INDEX 就要再前向合并——INDEX 是热文件）。
- INDEX 行数斗真：`grep -cE '^\| *[0-9]+ ' docs/superpowers/specs/2026-09-01-workorders-INDEX.md` = 34，编号 20–53 无缺号无重号。
- 四叶读数看 PR #744 返修评论（python 全量 / frontend / e2e / registry），收据钉名文件按 revision 对。

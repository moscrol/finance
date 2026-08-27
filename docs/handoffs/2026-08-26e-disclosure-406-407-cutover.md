# 2026-08-26e 切流：8792 → fbdbbfd298f4（#405+#406+#407）

用户口令「你按照最优路径推进」。质检结论：母稿 P1 R5 此前未达成（尾段无集采/反证解读），三张待合 PR 局部 spec 各自成立，合入后切一次、用公开稿尾段复验。

| 项 | 值 |
|---|---|
| 合入 | #405 merge `7054f995` → #406 merge `ef3b76ac` → #407 merge `fbdbbfd298f40efdd31567fbf93b3ffbe236735f` |
| #403 | 当轮**未合**：handoff 把弱化 R5（残差上场+名单零回归）写成「判据达成」；本 PR 收录的是改写后的稿 |
| 合并闸 | merge-tree 三张全干净（含 406×407 同文件 hunk 不重叠）；快照树 ruff 绿 + 定向 17P（收据 `~/.finance-runtime/test-receipts/20260826T042650Z-fbdbbfd2.json`） |
| 切换 | `7cc947f229f0` → `fbdbbfd298f4`，bootout + `ln -sfh` + bootstrap，healthy / dirty=false / match=true |
| readiness | checks **13/13**，missing_critical=[] |
| 监听核对 | pid 69008 cwd == `~/.finance-runtime/finance-workspace-fbdbbfd298f4` |
| 账本 | record switch + check ok：`ledger_rev == health_rev == fbdbbfd2…`（port=8792，repo-root=FINANCE_WS）；快照内无误置 `state/` |
| **回滚锚** | `~/.finance-runtime/cutover-20260826e-rollback-8792.txt`（回 `7cc947f229f0`，未动用） |
| 备份 | `~/backups/gitea-20260826-post407.tar.gz`（2.1G） |
| 未动 | 8796（仍 `76ee1e89`）、8802（仍 `5d7529e5`） |

## R5 复验（run_20260826_122832_875134，对话入口，probe-registry-trace-0826）

| R5 子句 | 读数 |
|---|---|
| 名单在顶 | 过。pack 21/39/1，主名单 21 行全在 |
| 名单零增删 | 过。21/21 公告号在稿、越界六位码 0、骨架关键词 0 命中 |
| 尾段集采双重性 | **过（首次）**。「集采中选（如中关村盐酸曲马多注射液）因量价对冲不默认利好，未计入」 |
| 尾段反证解读 | **过（首次）**。「华北制药 8-22 除子公司获临床批件外，同日公告撤回一项药品注册申请…削弱其整体利好判断」 |
| 边界诚实 | 过。临床≠上市、回购截断「不能表述为没有」 |

shadow：`status=repaired`，judge rejected=[3] → 句 3 已删（raw 1604 → repaired 1160 → presented 395）。
degrades=[]，`disclosure_residual_gate` 在 trace。

## #407 生效证据（生产 trace 首见）

trace 含 `grounded_composer_shadow`：`source=primary_grounded_presenter`、
`judge_reported_sentence_indexes=[3]`、`judge_applied_sentence_indexes=[3]`、
`judge_provider=grok-cli-judge` 与 composer `provider=zhipu` 分列。
本轮报=执行（单条带引文路径），与 #404 相同：混合引文分支仍无 live 样本，观察点不变。

## 遗留

- 主名单 600536 一行仍会被排除行按 query 加权挤出（#406 已声明，动 spec 领域模型另开一轮）。
- #404 混合引文分支（多条 issue、至少一条不带引号）仍无 live 样本。
- 残差尾段出现「三生国健/翰宇药业」未分类点名——在包内（disc:excl），闸放行，属口径内。

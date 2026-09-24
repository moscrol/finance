# 2026-09-24 盘点 09-23 的 Pi 会话，并收据当天的合并列车

写完不改。执行者：Claude Code 桌面会话 `local_d1bf0c0c-c14a-497a-b465-5db3c3230016`（分支 `claude/pi-session-cleanup-479dc5`），09-24 09:52–12:xx CST。
授权原话（用户第二条消息，约 10:10 CST）：「你按照最佳路径推进，可以合并的就合并，需要跑验收的就跑」。这句话覆盖合并与验收，**不覆盖**生产写库、换库、#60 安装或发布——那些仍需单独授权。
原始证据（合并 record、门禁日志、收据、脚本）：`~/.finance-runtime/reviews/pi-session-inventory-20260924/`。

## 盘点方法

- 读 `~/.pi/agent/sessions/--Users-a77-finance-workspace-private--/` 里 09-23 活动过的 25 个会话（20 个有效，另 5 个只是「训练截止日期」探针）。每个会话的首条用户消息通常是上一会话贴过来的终稿，所以读第 2 条以后的用户消息 + 最后一条助手正文。
- 报告内容不当真，逐条用 git / Gitea 复核：worktree 状态 `status --porcelain`；本机独有提交用 `rev-list --not --remotes=gitea`；并行线的吸收关系用 `log --cherry-mark`；基座漂移用 merge-base 起算的 first-parent 计数；冲突预演用 `merge-tree --write-tree`。

## 今天合入 main 的

| PR | 工单 | 合并提交 | 门禁 |
|---|---|---|---|
| #895 看板加固（前向 #812） | #84 | `78e75bf89` | 作者四叶收据绑 head `121fb3919`，漂移 0，本会话在候选树内复核「可采信」 |
| #844 RAG readiness 探针 | #62 | `99c84cecc` | 合并列车联合预览（见下） |
| #896 财务链两道门 + 混比拒句 | #66 | `77d49efd8` | 同上 |
| #897 变异量具超时留证 | #66 | `844793749` | 同上 |
| #898 sse-drain 存活变异登记击杀 | #66 | `bef0ee0f5` | 同上 |
| #899 历史 completion 前向 | #68 | `d86311d2e` | 同上 |
| #894 同花顺研究观察值 + 429 退避 | #85 | `1053f59a7` | 同上；前向 main 时 INDEX 只保留本单 #85 行 |
| #880 #67/#69 合入状态与收据分账 | #67 #69 | `209e9917d` | 同上；前向时 INDEX 67/69 行与 QUEUE #67/#69 行取本单 |

合并列车联合预览 `b464a9436` = main@`78e75bf89` + 上表后七张。四叶：Python ruff 0、**15282P / 0F / 0E / 85S / 2X**（collected 15369 对账平，`check_test_receipt.py --require-full-scope --expect-revision b464a9436 --base-drift-max 0` 可采信）；registry 四项 + crosswalk 均 exit 0；前端 lint / typecheck / vitest 120P / build 均 0，构建后树干净；e2e 34P / 2S。逐张合入时 `gitea_pr.py merge --expect-head/--expect-base --record` 的三项核验全部为 true。每一步合前、合后都比对 main 的树与预览链对应一步的树，全部逐字节相等；最终 **main 的树 == 预览树**。

## 关闭与指针

- #812 关闭，指针评论 6718 → #895。代码已移植进 #895；18 个 ownership 证据文档提交留在分支 `ops/worktree-ownership-closeout-0921`，不删，供 #64 取证。
- #810 关闭，指针评论 6750 → #894。#810 的 head 是 #894 的祖先。
- #845、#833（早已关闭）补指针评论 6753 / 6755 → #899。#845 有 2 个提交没进 #899，只改它自己的 inflight。
- #867（#78–#80 三张占位工单，base 分支早已合并，这三张单从未进过 main）并入本真值化 PR，合后关闭并留指针。

## 本 PR 同时并入的文档分支（全部是纯文档）

- `docs/finarena-decision-0923`：#82 裁决（用户「执行」→ 归档方案 B；#816 / #817 已留指针关闭）与收口记录。
- `fix/eastmoney-deploy-binding-0923`：#60 固定版本 f47 的部署准备与安装边界记录。
- `docs/closeout-placeholders-78-80`：#78–#80。
- 协调者分支 `docs/closeout-workorders-0922`：**只摘** INDEX 的 70/71/73/75/76 行和 QUEUE 的 #73 行。整枝合并会顺带把 2165 份 RE06 证据归档（`docs/verification/2026-09-2x-re06-*`）带进 main，那批证据应该跟 RE06 自己的 PR 走，所以没有整枝合；那两行里注明了引用路径在该分支上。

## 仍然没合的线和卡点

| 线 | 状态 | 卡在哪、谁来 |
|---|---|---|
| #61 生产行情恢复 | 代码 #871 / #861 已合；五问三合同已由 #893 受托代拍，**不要重问** | 等用户授权：恢复日期 09-21 / 22 / 23（历史日只走 `duckdb-backfill`）、生产写入、原子换库、发布、回滚点 |
| `fix/workbench-release-0924`（没开 PR，#900 是协调入口） | `eb4ec08f` 四叶绿（15084P）。它汇合了 #900 的三个修复、market-recovery-qc 的两个修复（含 #871 桥的整行指纹修复）、RAG 和 Workbench 的修复 | 作者定为数据门、换库、独立验收都过了再合，依赖 #61 |
| #60 东财熔断安装 | 代码已合；安装预演已过 | 等用户授权安装。夜跑 plist 仍指 `finance-sync-adcda94b5e40`（09-21，没有熔断也没有桥）；f47 早于 #871，安装目标宜和 #61 一起定 |
| #868（#72） | 七门绿（`e7a6cb412`）；本机 18 个提交 09-24 已补推 | 独审没闭合；K3 已用 131/152，**等用户批 209** |
| #884 运行时撤保护复跑 | head `4da9d28a7`，漂移 0 | 新候选还没跑全量；C1–C8 独审等用户批 84 次 K3 请求 |
| #81（#832 / #892） | C6 已修 | 独审 C3 / C5 没闭合；新 head 没有全量收据 |
| RE06 / #73 | 合流 `b027194f1`，09-24 已补推备份 | 工程门禁和三组独审一次都没跑（当时卡资源）；协调者会话 `01a0cbe1-be87` |
| #877 Knevo 吸收收口 | 工程绿 | 真实八问不过（`repair_model_unavailable`），需要用户定方向，建议搁置 |
| #890 claim-scope 运行时 | — | 等 #61 数据。它建议的 `/daily-full-review 2026-09-23` **不要执行**：没有这个斜杠命令，而且历史日走 daily-full 会把当天盘中价写成那天收盘 |
| #83 302132 回填（#813） | Pi 会话 `01a0ce4c-96df` 09-24 上午仍在跑 | 生产回填另需逐字授权 |
| `docs/knevo-intake-0924` | 含脚本和测试，不是纯文档 | 已推送备份，没开 PR，不急 |
| #838 / #841 / #799 | 旧 PR | #838 维持退回作者；#841 有独有提交，另判；#799 待判 |

## 备份

09-24 把 13 条本机独有分支推到 gitea：`feat/adaptive-research-loop`、`feat/knevo-absorption-closure-0923`、`fix/eastmoney-deploy-binding-0923`、`docs/closeout-workorders-0922`、`fix/market-recovery-qc-0923`、`fix/rag-recovery-state-0923`、`fix/workbench-release-ready-0924`、`test/workbench-release-eb4-0924`、`baseline/re06-ready-current-0924`、`fix/re06-timer-assets-0923`、`fix/re06-timer-scope-0923`、`baseline/re06-ready-refresh-0923`、`docs/knevo-intake-0924`。推完再查，本机独有提交为 0。

## 踩到的坑

1. **批次 2 合并脚本的漂移检查会误报。** 它拿「最终预览树」逐文件比对「列车走到一半时的 main」，只要链上两张 PR 改了同一个文件（本次是 #896 与 #899 都改了 `episode_semantic_verifier.py`），就必定报「预览树以外的改动」而停车。本次改为每一步合前、合后都比 main 的树与预览链对应一步的树，逐字节相等才继续。这个检查更严格，也不会误报。
2. **热文件相邻行冲突。** INDEX.md 和 QUEUE.md 被五六张 PR 同时改。#894 在 QUEUE 里插的那一行紧挨着 #880 改的几行，两张 PR 单独对 main 都干净，一叠加就冲突。解法是按行键取并集、并按工单号排序；两边都改过的行必须显式指定取哪边，否则中止。
3. **协调者分支夹带大批证据。** 拿它的 INDEX 真值之前，先 `diff --stat` 看总量；整枝合并会把 2165 份别人的在途证据带进 main。

## 下一步

1. 用户拍 #61 的生产授权，以及 #60 的安装。只能由一个会话去动生产，并且要在 18:30 夜跑前做完或明确暂停。
2. 有额度的线（#868 / #884 / #81 / RE06）由各自的 Pi 会话接着做。新的 main 是本 PR 的合并提交，合入前都要前向并重跑全量；同一时间最多跑 2 个全量。
3. 本清单的仓外版本和逐会话细节：`~/.finance-runtime/reviews/pi-session-inventory-20260924/README.md`。

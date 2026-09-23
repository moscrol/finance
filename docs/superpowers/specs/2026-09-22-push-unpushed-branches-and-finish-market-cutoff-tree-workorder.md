# 2026-09-22 本地未推分支推送与 market-cutoff 半成品树收尾工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
本单是纯风险收敛单，**不改代码、不合并、不部署**。它应最先派（与 #58 并行）：09-22 一天的产出有 14 条分支只存在于这台机器上，机器出事即全丢。

## 背景与动机

- 2026-09-22 22:20 核对 `git for-each-ref refs/heads` 与 `refs/remotes/gitea`：以下分支**未推送**（HEAD 以核对时刻为准，接手时重新 `git rev-parse`）：

| 分支 | HEAD | 领先 main | 工作树 | 备注 |
|---|---|---|---|---|
| `fix/runtime-entry-identity-0922` | `671fbffc5` | 13 | `~/fwp-wt-runtime-entry-identity-0922` | clean |
| `fix/runtime-effect-reconciliation-0922` | `18495609f` | 15 | 同上树切分支 | 叠在上一条之上 |
| `fix/research-empty-delivery-0922` | `d68b8f512` | 1 | `~/fwp-wt-research-empty-delivery-0922` | 会话可能仍在动，先看 mtime |
| `fix/e2-re06-resume-0922` | `100dcb32a` | 6 | `~/fwp-wt-e2-re06-resume-0922` | clean |
| `feat/adaptive-research-loop` | `aa0509d61` | 56 | `~/finance-worktrees/adaptive-research-loop` | 树有 2 个未提交路径，**不提交它们** |
| `fix/history-completion-0922` | `807a75d88` | 12 | `~/fwp-wt-history-completion-0922` | 树 1 个未提交路径，**不提交** |
| `fix/financial-comparison-0922` | `5d50cd864` | 2 | `~/fwp-wt-financial-comparison-0922` | 基座是 #835 head |
| `fix/gate-collection-0922` | `b450d1db9` | 5 | 同上树切分支 | #58 的对象 |
| `fix/market-recovery-contracts-0922` | `93b4a90c6` | 8 | 见分支交接 | |
| `baseline/research-data-acceptance-0922` | `f8eba1fab` | 26 | 见分支交接 | |
| `fix/delivery-guard-structural-binding` | `812f473ca` | 33 | 见分支交接 | 基于上一条 |
| `fix/eastmoney-snapshot-direct-ip-0922` | `1b1693bdf` | 2 | `~/fwp-wt-eastmoney-direct-ip-0922` | #60 的对象 |
| `fix/mootdx-history-0922` | `90dacecf6` | 4 | `~/fwp-wt-mootdx-history-0922` | **已写过生产库** |
| `fix/research-tail-financial-union-0922` | `65fde6171` | — | `~/fwp-wt-research-tail-financial-union-0922` | 作者冻结该 SHA，推送不改 SHA 可推 |
| `baseline/research-tail-union-0922`、`baseline/research-tail-formal-gate-0922` | `de8b06732`、`42784d27e` | — | `~/.finance-runtime/reviews/research-tail-formal-gate-20260922/…` | 门禁基线，推送以固定证据身份 |
| `fix/research-contract-citations-0921` | `5b2d1c488` | — | 见分支交接 | 09-22 12:35 的文档 |
| `fix/market-date-advisory-0921` | `1a297dcb5` | — | `~/fwp-wt-market-date-advisory-0921` | **6 个未提交文件**，见下 |

- 另有三条 PR 分支本地领先远端：`fix/runtime-closeout-0921`（#843，本地 `e7e12a189` vs 远端 `a9a112dfb`）、`fix/rag-probe-diagnostics-0921`（#844，`1137987db` vs `18c621579`）、`fix/history-forward-boundary-0921`（#845，`8da96fdac` vs `442476f7d`）。推送会改 PR head，使绑在旧 head 的收据声明失效；`#845` 的作者刻意保持 head 不动以配合联合树证据。
- `~/fwp-wt-market-date-advisory-0921` 的会话在 09-22 17:49 因工具失效（`Tool Bash not found`）中断，留下 5 个修改文件与 1 个未跟踪目录 `docs/verification/2026-09-22-market-cutoff-followup/raw/53054bfd4/independent-retry-01/`。剩余步骤（会话最后一条消息给出）：补 attempt B 原件并逐字节 `cmp`、保序重写 manifest、用**已提交的** `scan-review.json` 做 hash→分类映射重扫敏感串（未知一律阻断）、重算 sha256、修文档里「29 个原件」为 30、scoped commit、四包按 Git blob 复验。
- **已定的形态决策**：推送只推已提交的历史，不 `--force`，不为任何树补提交（除 market-cutoff 树按其自己的剩余步骤收尾）。有 PR 的三条分支先问所有者意图再推。

## 目标

1. 上表 17 条无 PR 分支全部 `git push gitea <分支>`，逐条记录推送前后 `git rev-parse` 一致。
2. 三条有 PR 的分支：逐条列出本地多出的提交是否纯文档（`git diff --stat gitea/<分支>..<分支>` 只含 `docs/`），纯文档的推送并在 PR 评论写「head 由 X 移到 Y，仅文档，收据仍绑 X」；含代码的**不推**，报给用户。
3. `fwp-wt-market-date-advisory-0921` 按上面剩余步骤收尾并 scoped commit，树 clean，推送。
4. 一份 `docs/verification/<日期>-branch-push-audit/README.md`：每条分支的 HEAD、推送时间、远端 SHA 回读。

## 非目标（写死认领）

- ❌ 不合并、不开 PR（各自的合入准备单会开）、不删任何分支或工作树（#64）。
- ❌ 不提交 `feat/adaptive-research-loop` 与 `fix/history-completion-0922` 树里的未提交路径；它们属于仍在运行或刚结束的会话，写进 README 让所有者处置。
- ❌ 不改 market-cutoff 树的测试日志与收据；不为它重跑独立审查（那是 #75 的事，且当时因额度失败）。
- ❌ 不 `--force`、不 rebase、不改任何历史。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `git for-each-ref --sort=-committerdate refs/heads` 与 `refs/remotes/gitea` 对比 | 当前真实的未推清单（表格只是 22:20 快照） |
| `~/fwp-wt-market-date-advisory-0921/docs/handoffs/inflight/fix-market-date-advisory-0921.md`（未提交版本） | 该树的「当前状态 / 下一步」 |
| `~/fwp-wt-market-date-advisory-0921/docs/verification/2026-09-22-market-cutoff-followup/README.md`、`manifest.json`、`scan-review.json`（`git show HEAD:` 取已提交版本做映射） | 剩余步骤的输入 |
| `~/.finance-runtime/reviews/market-cutoff-independent-53054bfd4-20260922/` | attempt B 原件来源 |
| `scripts/smoke_workbench_self_use.py::SECRET_PATTERNS` | 敏感串重扫用的同一套模式 |
| `~/.pi/agent/sessions/--Users-a77-finance-workspace-private--/` 各文件 mtime | 判断哪些树的会话仍在写（mtime < 10 分钟就别碰） |

## 步骤

1. 开工三连；重新生成未推清单（`comm` 两个 ref 列表），与本单表格对照，差异写进 README。
2. 逐条 `git -C <树> status --short` 确认树 clean 或未提交路径与表格一致；`git push gitea <分支>`；`git rev-parse gitea/<分支>` 回读。
3. 三条 PR 分支按目标 2 处理。
4. market-cutoff 树：先 `git -C 树 status --short` 与 `git diff --stat` 落盘；按剩余步骤逐步做，每步产物用 `cmp` / `sha256sum` 自证；只 `git add -- <文件>`；提交信息写明「接手 17:49 中断会话」；推送。
5. README + INDEX #63 行；本单不写 inflight（无分支）。

## 验收

- [ ] 上表每条分支 `git rev-parse <分支>` == `git rev-parse gitea/<分支>`。
- [ ] 三条 PR 分支各有一条决定记录（推 / 不推 + 理由）。
- [ ] market-cutoff 树 `git status --short` 为空；manifest 里条目数与 README 计数一致；敏感重扫 `unclassified=0`。
- [ ] README 落盘并含机器时间戳。

## 红线

- 不 `--force`，不 rebase，不 `git add -A`；只 pathspec。
- 会话仍在写的树（mtime < 10 分钟）不碰，等它停。
- 不删任何东西；不动主检出树。
- 不写明文密钥；重扫时敏感匹配不按 token 形状泛放行，逐位置核上下文。

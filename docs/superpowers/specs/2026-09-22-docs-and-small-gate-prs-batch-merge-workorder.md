# 2026-09-22 文档类与小门禁类 PR 批量合入工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
上游：#59（main 顶端干净收据）。本单只处理**不含运行时代码**的 PR，以及一张仓工具小门禁 PR（#853）。批量合并纪律见记忆 `merge-queue-batch-discipline-0916`：合前 `fetch` + `merge-tree`，逐 PR 核对落地文件集，比较基准是目标分支不是快照。

## 背景与动机

- 09-22 22:20 Gitea 37 张 open PR 里，以下几张是文档 / 收据封存 / 小门禁，长期挂着会让「在途」名单失真，也让各分支的 inflight 交接指向过期状态：

| PR | 分支 | 性质 | 备注 |
|---|---|---|---|
| #836 | `docs/nightly-deployment-receipt-0921` | 夜跑配置部署收据 | 唯一非 draft；配置部署已完成，业务效果另验 |
| #838 | `docs/research-tail-closeout-0921` | 研究尾单前向候选封档与审核边界 | 与 #67 关联：#67 合入后本 PR 部分内容过期，合前核对指针 |
| #840 | `docs/judge-mode-k3-cutover-0921` | #830 K3 无判官首跑与回滚终态 | 生产已回滚为 adcda94b5e40 / glm-5.3-flash，文档口径与 22:15 `/api/health` 实读一致才合 |
| #849 | `docs/k3-acceptance-0922` | K3 无判官内容与恢复只读验收 | 标题带 `WIP:`，作者未去；四类越界结论在 #65 里被引用 |
| #804 | `docs/pr803-merge-closeout-0920` | #803 合入、接替评论及保守清树证据封存 | 纯封存 |
| #807 | `docs/stale-closeout-gates-0920` | #805/#806 完整本地门禁与环境失败证据封存 | 纯封存；#805/#806 已并入 #815 |
| #853 | `chore/handoff-budget-gate` | inflight 交接 3K 预算的棘轮门禁（104 份里 53 份超标，零门禁） | **含代码**（`tests/test_handoff_budget_gate.py` 等），走完整四叶；棘轮语义：存量超标只许不增长，新文件必须 ≤3K |

- **已定的形态决策**：文档 PR 也要过 registry 叶与路径字面量检查（`scripts/check_path_literals.py` 在 pre-commit 里），但不要求 python 全量；#853 是门禁代码，四叶齐；每张合并都 `--record`；被姊妹单合入内容取代的文档 PR 用 `close --pointer-file` 而不是硬合。

## 目标

1. 七张 PR 逐张给出「合 / 关闭留指针 / 退回作者」三选一的判定与理由，落 `docs/verification/<日期>-docs-batch/decisions.md`。
2. 判「合」的：`fetch` + `merge-tree` 零冲突；文档 PR 跑 registry 叶 + `check_path_literals.py` + `check_handoff_budget`（若 #853 已合则用它）；#853 四叶齐。
3. 用户确认后按顺序合入（推荐 #853 先，其后文档 PR 才受它的门禁约束），每张 `merge --yes --expect-head --record`。
4. 合入后核对每张 PR 的落地文件集 == PR 变更文件集（`git diff --name-only <merge^1> <merge>` 对 `gitea_pr.py show` 的文件列表）。
5. 判「关闭」的：`gitea_pr.py close <n> --pointer-file` 指向取代它的 PR / 提交 / 文档。

## 非目标（写死认领）

- ❌ 不改任何文档 PR 的正文口径（口径过期的退回作者或关闭留指针，不代改）。
- ❌ 不合任何含运行时代码的 PR（#853 除外，它是仓工具）。
- ❌ 不压缩超 3K 的存量 inflight（棘轮只禁增长；压缩是各分支所有者的事）。
- ❌ 不部署。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `python3 scripts/gitea_pr.py show <n>` × 7 | head、base、`mergeable_claimed_by_gitea`（不信它，自探） |
| 各 PR 分支的 `docs/handoffs/inflight/<分支>.md` | 自述状态是否仍成立（#840 对照 `/api/health` 实读；#838 对照 #67 状态） |
| `gitea/chore/handoff-budget-gate:tests/test_handoff_budget_gate.py` 与门禁脚本 | 棘轮语义；09-22 该分支 8 条用例先红后绿的收据 `20260922T122911Z-e2ef0f09.json`（脏树，目标） |
| `scripts/check_path_literals.py`、`scripts/build_registry.py` | 文档 PR 的最小门 |
| `~/.claude/projects/-Users-a77-finance-workspace-private/memory/merge-queue-batch-discipline-0916.md` 等合并纪律记忆 | 批量合并的失败形状 |

## 步骤

1. 开工三连；`git fetch gitea`；七张 `show`；逐张读 inflight 自述。
2. 判定表贴用户（合 / 关 / 退回 + 一句理由）。
3. #853：独占干净检出四叶；去 `WIP:`。
4. 文档 PR：`merge-tree`；registry 叶 + 路径字面量；#840 的口径与 health 实读逐字段对。
5. 用户确认后按顺序合入或关闭；每张落地文件集核对。
6. INDEX #77 行。

## 验收

- [ ] `decisions.md` 七行齐全，每行有理由与用户确认原话。
- [ ] 每张合入的 PR 有 `--record` JSON；落地文件集 == PR 文件集。
- [ ] #853 四叶收据 revision == head；阳性对照：往任一 inflight 追加 1 字节让它超 3K 且增长，门禁必须拦；还原后放行。
- [ ] 每张关闭的 PR 有接替指针评论。
- [ ] 合完后 open PR 数下降量 == 合入 + 关闭之和。

## 红线

- 合入 main 必须等用户确认；不强推；关闭 PR 必留接替指针。
- 只用 pathspec 提交；不改他人 PR 正文。
- 不部署；不动 8792。
- 不写明文密钥；Gitea token 只从 Keychain 取。

# 2026-09-23 文档类与小门禁类 PR 批量判定（工单 #77）

首轮判定基座：`gitea/main@8e7989372`（2026-09-23 00:4x fetch；#863 研究尾单三线合流已落地，较 23:5x 的 `f24a61a8a` 多 13 提交 / 162 个非文档文件）。首轮判定在 `f24a61a8a` 上做，落地后全部重探；02:5x 再核 main@`72be60059`（#854 / #860 又落地，共 14 个非文档文件，与七张 PR 文件集零交集），七张 merge-tree 复探结论不变。每张 PR 都用本机 `git merge-tree --write-tree` 自探，不信 Gitea 的 `mergeable`；
「合」的文档 PR 都在合并预览树（`merge-tree` + `commit-tree` 检出到 `/Users/a77/fwp-wt-preview-<n>`）上跑过 `scripts/check_path_literals.py` 与
`scripts/build_registry.py check`，并核对预览树相对 main 的文件集 == PR 文件集。生产读数取自 2026-09-22 23:58 `/api/health` 实读与 8792 进程环境。

四值：**合** / **关闭留指针** / **退回作者** / **暂缓（证据不足）**。「用户确认原话」列在用户逐张确认后回填；空着的行不得动。

## 续检覆盖声明（2026-09-23）

当前主干已推进到 `gitea/main@5f35da1723f74663a4803c4d1490c402a1d6db40`（#882 文档收尾，未触碰 #853/#857 目标文件）。首轮表中的旧全量收据不再作为当前合并门禁：#853 的历史 `4c730a8ba` 收据基座落后；#853/#857 在当前主干上的临时合流已补齐定向、前端和 e2e，但全量 Python 仍待资源空闲后重跑，不能记绿。

因此本表只保留 #838 的“退回作者”结论；其余“合”均降为需当前候选四叶或冲突处理后重判。生产只读检查同时记录为 `/api/health` 200 但 `/api/readiness` 503，`source_dirty=true`，缺项为 `rag_worker`；这不支持完整 readiness 签字。

| PR | 分支 @ head | 判定 | 理由（一句） | 本轮核对 [实测] | 用户确认原话 |
|---|---|---|---|---|---|
| #853 | `chore/handoff-budget-gate` @ `54d0acdb7` | **暂缓（当前 Python 全量待重跑）** | 代码门禁、前端和 e2e 当前候选均通过，但全量 Python 尚未取得当前 revision 收据；历史 `4c730a8ba` 不适用于 `5f35da1…`，不能据此合并。 | 当前主干临时合流提交 `5305d5d9d`：ruff 0、目标测试 **8P**、前端 lint/typecheck/Vitest **120P**/build 0、e2e **34P/2S**、路径字面量 0、registry 0；全量 Python 待资源空闲后重跑。 | 待 |
| #836 | `docs/nightly-deployment-receipt-0921` @ `b26a617d3` | **暂缓（当前四叶待重跑）** | 首轮文档与封存内容判断仍可复核，但旧预览收据不绑定当前 `gitea/main@5f35da1…`；当前合流后需重跑适用门禁。 | 首轮 `8e7989372` 预览证据保留为历史记录；本轮未形成当前候选四叶收据。 | 待 |
| #838 | `docs/research-tail-closeout-0921` @ `e3a5e7ddf` | **退回作者** | #863（#67 的联合候选）已合入 `8e7989372`，其 PR 正文明写「#838 10 份文档不在候选，留 open 写差异评论」，所以它**不是**被取代的内容、不能关闭留指针；但它现在有三处要作者自己动：`.claude/lessons_learned.md` 与 main 冲突（追加 13 行）、新增的 6 份 inflight 属于已被 #863 关闭的分支（#833/#834/#835/#845/#814 + `fix-research-tail-integration-0921`），合入会复活死分支的「在途」状态、自述 `CHANGES_REQUIRED / 未验收` 已过期。本轮不合不关，退回时把这三点贴进 PR 评论。 | merge-tree exit 1（lessons_learned）；878/879 个文件 main 上没有；#833/#834/#835/#845/#814 已 closed。 | 待 |
| #840 | `docs/judge-mode-k3-cutover-0921` @ `c04959639` | **暂缓（当前四叶待重跑）** | 历史 23:58 口径复核仍未发现文档语义冲突；但当前生产读数已是 `source_dirty=true`，且 readiness 503（缺 `rag_worker`），不能把历史文档核对升级为当前部署接受。去 `WIP:` 仍需用户授权。 | 首轮 `8e7989372` 预览证据保留为历史记录；本轮只确认文档语义未与当前代码入口冲突，未形成当前候选四叶收据。 | 待 |
| #849 | `docs/k3-acceptance-0922` @ `9c7fa81f6` | **暂缓（当前四叶待重跑）** | 历史只读复核与其时间戳口径仍可追溯，但旧预览不构成当前主干合流后的四叶收据；去 `WIP:` 仍需用户授权。 | 首轮 `8e7989372` 预览证据保留为历史记录；本轮未形成当前候选四叶收据。 | 待 |
| #804 | `docs/pr803-merge-closeout-0920` @ `8c1a95116` | **暂缓（当前四叶待重跑）** | 历史封存关系仍可复核，且 #853 门禁的删除规则未见反例；但当前主干漂移后旧预览不构成当前合流四叶收据。 | 首轮 `8e7989372` 预览证据保留为历史记录；本轮未形成当前候选四叶收据。 | 待 |
| #807 | `docs/stale-closeout-gates-0920` @ `a77d56e28` | **暂缓（待前向解冲突）** | 仍是纯封存证据；当前 `5f35da1…` 上唯一冲突仍为 `.claude/lessons_learned.md`，需两边追加合并后再重跑门禁。未获授权前不推前向提交。 | 当前三方：main 644 行、PR 599 行，`git merge-file --union` 得 649 行、0 冲突标记、章节标题无重复；这是临时 union 证据，不是已推分支或可合并收据。 | 待 |

## 建议顺序

#853（先推 `4c730a8ba`）→ #836 → #804 → #807（推前向合并提交后再合）→ #840（去 WIP）→ #849（去 WIP）。#838 退回作者，不合不关。
每张合入前重新 `fetch` + `merge-tree`（#853 先合会让 main 多 1 提交；它只碰 `.pre-commit-config.yaml / scripts / tests`，与 6 张文档 PR 文件集无交集，但仍按纪律重探）；
每张 `gitea_pr.py merge <n> --yes --expect-head <sha> --expect-base <main sha> --record docs/verification/2026-09-23-docs-batch/merge-<n>.json --authorized-by "<原话>" --authorization-source "<出处>"`；
合后 `git diff --name-only <before> gitea/main` 必须等于该 PR 文件集。

## 非目标（沿工单）

不改任何文档 PR 正文口径；不压缩超 3K 存量 inflight（main 上 39 份 >3072 字节，归各自分支所有者）；不部署、不动 8792。

# 2026-09-23 文档类与小门禁类 PR 批量判定（工单 #77）

判定基座：`gitea/main@f24a61a8a`（2026-09-22 23:5x fetch）。每张 PR 都用本机 `git merge-tree --write-tree` 自探，不信 Gitea 的 `mergeable`；
「合」的文档 PR 都在合并预览树（`merge-tree` + `commit-tree` 检出到 `/Users/a77/fwp-wt-preview-<n>`）上跑过 `scripts/check_path_literals.py` 与
`scripts/build_registry.py check`，并核对预览树相对 main 的文件集 == PR 文件集。生产读数取自 2026-09-22 23:58 `/api/health` 实读与 8792 进程环境。

三值：**合** / **关闭留指针** / **退回作者**。「用户确认原话」列在用户逐张确认后回填；空着的行不得动。

| PR | 分支 @ head | 判定 | 理由（一句） | 本轮核对 [实测] | 用户确认原话 |
|---|---|---|---|---|---|
| #853 | `chore/handoff-budget-gate` @ `54d0acdb7` | **合（首合）** | 仓工具门禁：inflight 交接 3000 字节棘轮（新增 / 加重才拦，存量免检，删除放行）；本批其余 6 张 PR 新增的 inflight 最大 2631 字节、#836 改的那份 2631→2233、#804 删一份，合后不会拦住它们。 | merge-tree 0 冲突（落后 main 2）；独占干净树 `fwp-wt-853-handoff-budget-gate`：ruff 0、目标 8P（收据 `20260922T155932Z-54d0acdb.json`，dirty=false）、registry 0；全量 python / 前端 / e2e 见本目录 `gates-853.md`。 | 待 |
| #836 | `docs/nightly-deployment-receipt-0921` @ `b26a617d3` | **合** | 唯一非 WIP；纯文档 + 证据封存 + `lessons_learned` 追加 5 行无冲突；改的另一份 inflight（`fix-nightly-deploy-closeout-0921.md`）是 #827 自己分支的合后 truth-up（main 上末次改 09-21 16:55，本枝 18:50 更新）；自述「三 adcda 固定根已装」与 worktree 列表里 `finance-sync / l2 / generation-adcda94b5e40` 三棵树一致。 | merge-tree 0（落后 22）；预览树 path_literals 0、registry 0；文件集 107 == 107。 | 待 |
| #838 | `docs/research-tail-closeout-0921` @ `e3a5e7ddf` | **退回作者（挂 #67）** | merge-tree 在 `.claude/lessons_learned.md` 冲突（追加 13 行）；另新增 6 份**别的在途分支**的 inflight（`fix-financial-forward-0921`=#835、`fix-history-forward-0921`=#833、`fix-runtime-forward-0921`=#834、`fix-history-forward-boundary-0921`=#845、`fix-research-tail-integration-0921`、`fix-gate-receipt-selection-0921`），先合会让那些 PR 各自撞车；自述 `CHANGES_REQUIRED / 未验收`；#67 工单已把它列入「联合候选合入后关闭留指针」。本轮不合不关。 | merge-tree exit 1。 | 待 |
| #840 | `docs/judge-mode-k3-cutover-0921` @ `c04959639` | **合（去 `WIP:`）** | 口径与 23:58 health 实读逐字段一致：`runtime.source_revision=adcda94b5e40…`、`source_dirty=false`、`code_matches_repo=true`、`agent_runtime.model=glm-5.3-flash`；进程环境 `ASK_SEMANTIC_JUDGE` 未设（缺省 llm）、`ASK_EVIDENCE_JUDGE=auto` → 文中「当前生产不是 K3 也不是无判官模式」成立。改 `docs/agent-product-door.md` 是给已合 #830 的判官 `llm/off` 模式补门页口径，属应配套的门页更新。 | merge-tree 0（落后 27）；预览树 path_literals 0、registry 0；文件集 108 == 108。 | 待 |
| #849 | `docs/k3-acceptance-0922` @ `9c7fa81f6` | **合（去 `WIP:`）** | 只读复核文档；其结论（旧证据 104 件哈希过、两旧 run 为 K3 且终稿判官 0 调用、四类口径越界不接受）被 #65 / #850 当判据引用；生产读数与当前 health 一致；「五张 fact 表 max=09-18」是 09-22 18:00 采样窗口的带时间戳陈述，21:47 换库后已变但不算口径过期。 | merge-tree 0（落后 9）；预览树 path_literals 0、registry 0；文件集 19 == 19。 | 待 |
| #804 | `docs/pr803-merge-closeout-0920` @ `8c1a95116` | **合** | 纯封存 #803 合入 / #789 接替评论 / 清树证据；删的 `inflight/fix-nightly-refresh-resume-0920.md` 是 #803 自己分支的交接（#803 已以 `728f32716` 合入），按 handoff 规约「已合并的从 inflight 删掉转日期快照」；#853 门禁对删除放行。 | merge-tree 0（落后 138）；预览树 path_literals 0、registry 0；文件集 47 == 47。 | 待 |
| #807 | `docs/stale-closeout-gates-0920` @ `a77d56e28` | **合（需前向合并解 `lessons_learned` 追加冲突，两边保留）** | 纯封存 #805/#806 完整门禁证据（二者已并入 #815）；唯一冲突是 `.claude/lessons_learned.md` 双方各自追加（本枝 +6 行「验收环境的工具依赖」），`git merge-file --union` 解出 616 行、0 冲突标记。已在 scratch 树 `fwp-wt-preview-807` 预演成合并提交 `9fae39d8b`（未推）：path_literals 0、registry 0、文件集 73 == 73，非文档差异只有 `lessons_learned`。这一步会给 PR 分支追加一个合并提交、不改 PR 正文口径，需用户点头；不点头则退回作者自解。 | merge-tree exit 1（仅 lessons_learned）；scratch 合并后 0 冲突。 | 待 |

## 建议顺序

#853 → #836 → #804 → #807（推前向合并提交后再合）→ #840（去 WIP）→ #849（去 WIP）。#838 不动。
每张合入前重新 `fetch` + `merge-tree`（#853 先合会让 main 多 1 提交；它只碰 `.pre-commit-config.yaml / scripts / tests`，与 6 张文档 PR 文件集无交集，但仍按纪律重探）；
每张 `gitea_pr.py merge <n> --yes --expect-head <sha> --expect-base <main sha> --record docs/verification/2026-09-23-docs-batch/merge-<n>.json --authorized-by "<原话>" --authorization-source "<出处>"`；
合后 `git diff --name-only <before> gitea/main` 必须等于该 PR 文件集。

## 非目标（沿工单）

不改任何文档 PR 正文口径；不压缩超 3K 存量 inflight（main 上 39 份 >3072 字节，归各自分支所有者）；不部署、不动 8792。

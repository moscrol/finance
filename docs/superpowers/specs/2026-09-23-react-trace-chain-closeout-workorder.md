# 2026-09-23 ReAct trace 六项修复链收口工单（#81）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
来源：`docs/handoffs/2026-09-23-orphan-inventory.md`（2026-09-23 盘点，第二节「无人接手」）。
姊妹单：**#68**（历史完成单，`2026-09-22-history-completion-pr-workorder.md`）——#841 叠在本单载体 #832 之上，本单先于 #68 的「证据绑定链」部分落定；两单可并行开分支，但 #68 若先动 #841，要先把 #841 的 base 从 #832 改到 main。

## 背景与动机

09-21 一条 Pi 会话给研究 ReAct 回路做了六项修复（引用序号 / 修复反馈 / 条件连贯 / 历史分页身份 / 条件计数接缝，PR #809），随后独立质检返修成 **PR #832**（`fix/react-trace-qc-0921`，含 #809 全部提交）。工程叶在代码 `a14005fc9` 上全绿（全量 12596P / 87S / 2X，前端六步、E2E 34P/2S），但 **K3 独立审查 600 秒超时无终稿、自然金融质量 0 次跑、状态 not_passed**，PR 保持 WIP，之后无人接手。

今天（09-23）核对 [实测]：#832 新增的 886 行非文档代码在当前 `gitea/main` 只能找到 398 行（44%），即这条线**没有随 #863 研究尾单合流落地**；对当前 main 有 6 处冲突（#863 改了同一批文件）。#809 已于今日关闭并留指针指向 #832，#832 是这条线唯一载体。

已定形态：**不新开分支重做**。在 #832 上前向合并当前 main、按意图解冲突（memory：squash 在分支、merge 在主干的冲突按意图解），保留原六项修复的测试作为回归；不放宽 `episode_semantic_verifier` 任何判据。

## 目标

1. `fix/react-trace-qc-0921` 前向合并到当前 `gitea/main`，6 处冲突按意图解完，原 PR 六项修复对应的 7 个测试文件全绿。
2. 逐项对照 #863 已落地的内容，给出「六项里哪几项已被 #863 覆盖 / 哪几项仍是增量」的对照表（写进 PR 正文），增量为 0 的项直接删掉分支侧改动。
3. 干净树四叶收据（python / frontend / e2e / registry）绑定新 head。
4. 登记 #75 独立 QC 队列（`docs/verification/2026-09-22-independent-qc-batch/QUEUE.md` 追加一行），自然金融质量按 #76 协议另行授权。
5. 若用户裁定放弃：关闭 #832 留指针（指向本单 + 分支保留），把仍成立的发现逐条移交 #68 / #76。

## 非目标

- ❌ 顺手处理 #841（历史证据绑定）——归 #68。
- ❌ 合 main、部署 8792、写生产画像——合入等用户确认。
- ❌ 重开 K3 审查预算——归 #75 服务单。
- ❌ 处理本地未推分支 `fix/react-trace-runtime-0921`（+3 提交，09-21 02:17）以外的任何 runtime 改动；该分支只需判定「已被 #832 包含则删、否则推上去开占位 PR」。

## 证据路径表

| 文件 | 看什么 |
|---|---|
| PR #832 正文与评论（`python3 scripts/gitea_pr.py show 832`） | 接替关系、a140 工程收据、K3 超时记录 |
| `gitea/fix/react-trace-qc-0921:docs/handoffs/inflight/fix-react-trace-qc-0921.md` | 当前状态与「不要分别合 #809/#832」的约束 |
| `gitea/fix/react-trace-qc-0921:docs/verification/2026-09-21-react-trace-integration/` | 前向合流原件 |
| `git merge-tree --write-tree --name-only gitea/main gitea/fix/react-trace-qc-0921` | 6 处冲突：`docs/agent-product-door.md`、`intelligence/services/episode_semantic_verifier.py`、`finance_query.py`、`historical_research/episode.py`、`intelligence/tests/test_agent_episode_progress.py`、`test_research_progress.py` |
| `git diff gitea/main...gitea/fix/react-trace-qc-0921 -- intelligence/` | 14 个非文档文件的净 diff |
| `docs/superpowers/specs/2026-09-22-research-tail-union-candidate-closeout-workorder.md`（#67） | #863 合流了什么，用来做「已覆盖 / 仍增量」对照 |
| `docs/agent-product-door.md` | 门页要与改 runtime 的提交一起改（AGENTS.md） |

## 步骤

1. 开工三连：`git status --short && git branch --show-current`；`git fetch gitea`；`git worktree add /Users/a77/fwp-wt-react-trace-forward-0923 gitea/fix/react-trace-qc-0921`（新树直接用主树 `.venv-workbench/bin/python`）。读上表前两项。
2. `git merge gitea/main`，6 处冲突按意图解；每解一处，跑该文件对应的测试文件；解完跑 #832 自己的 7 个测试文件 + #863 带进来的 `tests/test_research_*`、`intelligence/tests/test_episode_*`（memory：前向合并后红的通常是另一张 PR 的测试）。
3. 写「六项 × 已覆盖/增量」对照表进 PR 正文；增量为 0 的项回退。
4. 提交（pathspec）、推送，`git diff --name-only <前向前 base> gitea/main | grep -vE '^docs/|\.md$' | wc -l` 记录漂移。
5. 干净树四叶：`bash scripts/run_main_gate.sh`；`cd intelligence/webapp && pnpm lint && pnpm typecheck && pnpm test && pnpm build`；E2E（`WORKBENCH_PYTHON=<venv python>`，端口成对设）；`python3 scripts/build_registry.py check`。收据用 `scripts/check_test_receipt.py --expect-revision <head>` 校验。
6. 读数贴 PR 评论；QUEUE.md 追加一行；覆写 inflight（≤3K 字节）；回 INDEX 改 #81 状态行。

## 验收

- [ ] `merge-tree` 对当时 `gitea/main` 干净（exit 0）。
- [ ] 对照表六行，每行有「#863 落地提交 / 本分支文件:行」两列证据。
- [ ] python 收据 revision == 分支 head，`dirty=false`，failed=0；frontend / e2e / registry 三叶 exit 0。
- [ ] 阳性对照：把 `episode_semantic_verifier.py` 中六项之一的判据注释掉，对应测试至少一条红（记录用例 id）。
- [ ] QUEUE.md 有本单行；INDEX #81 行状态已改。
- [ ] 若走放弃路径：#832 关闭评论含替代物与「替代物失效时怎么办」。

## 红线

- 提交只用 pathspec：`git add -- <文件>`、`git commit -- <文件>`；不 `git add -A`。
- 合并回 main 必须等用户确认；不强推；关闭 PR 必留接替指针。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`。
- 不写生产库、不切 8792、不调真实模型（自然题归 #76）。
- 不提交 `.env*` / `*.duckdb` / 缓存；不写明文密钥。

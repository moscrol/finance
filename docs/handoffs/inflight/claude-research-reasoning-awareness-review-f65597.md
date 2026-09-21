# 研究求证意识候选：复核 + 清掉它自列的三项待办

## 这个分支做什么
复核 `feat/research-reasoning-awareness`（候选）的合入就绪度，并执行候选自己 inflight
「下一步 3」点名的三件事：前端叶、E2E 叶、registry 与 `kb/rag-query` 跨仓漂移。
本分支不改候选的任何文件，只产出读数与一份注册表补丁（补丁落在另一棵隔离树的独立分支）。

## 决策与被否方案
- **修 registry 漂移选「隔离父目录 + 真仓名 worktree」，否「在主检出树跑 scan」**：
  `scan` 按当前文件系统全量重写，主检出树当前有别人 4 删 + 十余改的未提交 skills 视图
  改动，在那里跑会把它们烙进注册表（`a6bc3d87e` 的提交信息 2026-09-08 已踩过同一个坑）。
- **否「复用 `fix/agent-docs-audit-registry`」**：该分支标题正是同一件事，但落后 main
  **1018** 个提交，基线太旧，重开干净分支比 rebase 便宜。
- **`9b4c2310b` 选「打 archive tag」，否「删树」也否「改候选分支的 inflight」**：删树即丢
  提交（无分支含它）；候选分支是被审对象且 K3 已判 PASS，在它上面追加提交会让那个结论
  失效。tag 走仓内既有惯例（`archive/<描述>-<sha>`，仓内已有 4 个）。
- **不推送、不开 PR、不合 main**：等用户定批次。

## 当前状态
本分支 `claude/research-reasoning-awareness-review-f65597` @ `728f32716`（= gitea/main）。
候选 `feat/research-reasoning-awareness` @ `500167e26`，**领先 main 14、落后 0**，树干净，未 push/PR。
注册表补丁 `fix/registry-kb-rag-query-drift` @ `3c344b61e`，在
`~/.finance-runtime/registry-allpresent-20260921/finance-workspace-private`，**未推送**。

## 已验证（[实测] 本轮自己跑的）
四叶对候选尖 `500167e26` 全部有读数，**无一红、无一「无结论」**：

| 叶子 | 读数 |
|------|------|
| python | 绿（沿用干净收据 `12049P/87S/2X/0F` @ `2cfa9d0d`；`2cfa9d0d..500167e26` 全是 docs，代码文件 diff 为 0） |
| ruff | 绿 |
| registry-check | 绿（CI 条件下五条全 exit 0） |
| frontend | 绿，`pnpm lint && typecheck && test && build` 串联 **exit 0**；vitest **110 passed / 8 files** |
| e2e | 绿，**34 passed / 2 skipped**（1.1m，三 viewport） |

- 前端 build 后 `git status --short` 为空——`vite build` 写进 git-tracked 的
  `intelligence/api/static/`，哈希文件名字节复现，顺带是一次确定性检查。
- e2e 需 `WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python`
  （worktree 里没有 venv，否则 Playwright 在第一条测试前就报 webServer 起不来，那是
  harness 条件不是回归）；跑前确认 8791 空闲。
- **registry 漂移已定位并修掉**：只有 `kb/rag-query` 一条，description 全文改写 +
  triggers 增 `检索`/`帮我搜` + hash `28246007`→`193e7888`。来源是知识库仓
  `bc9e8c2b8`（hybrid 上加 rerank 开关）。全 diff 5 insert / 3 delete，无第二处。
  修前 `check` exit 1、修后 exit 0（均在三仓在场条件下取）。
- `9b4c2310b` 已被 `archive/p6-integration-dryrun-9b4c2310` 引用，删树不再丢提交。

## 未验证 / 已知边界
- **registry-check 在 CI 上从来不会因这条漂移红**。CI 只 checkout 本仓，`build_registry.py
  check` 在 kb/site 缺仓时走 `all_present` 分支，把跨仓项整段跳过（忽略 kb/* 23 个 skill）。
  漂移只在三仓同时在场时可见。所以本轮补丁修的是真实一致性，**不是在修红灯**，也不是候选的
  合入前置。附属 worktree 天然看不见它：`REPOS_DIR = REPO_ROOT.parent`，而附属树的父目录是
  `.claude/worktrees/`。
- python 叶是**沿用**收据不是重跑。依据是 `2cfa9d0d..500167e26` 四个提交全为 docs
  （`git diff --name-only` 代码文件数 0）。要更硬的结论得在 `500167e26` 上重跑全量。
- 候选与 P6 的集成**只演练过一次且已过期**：`9b4c2310b` 的两个父是
  `500167e26`（候选当前尖，仍有效）与 `6721470542`（P6 **旧**提交）。P6
  `fix/e2-material-closeout` 现尖已走到 `b1c1c29f2`，且落后 main **94**、领先 24。
  该合并树只有合并前的定向收据，合并后那个 revision 上**没有任何收据**。
- 候选 inflight 自列的其余边界（语义验收、数字句被门删、P5 待 P7、独立盲审 `passed=false`）
  本轮未碰，仍然成立。

## 下一步
1. **注册表补丁**：`3c344b61e` 待用户定夺推送 / 开 PR。它独立于候选，可单独走。
2. **合入顺序建议：候选先、P6 后**。候选落后 0、四叶齐绿；P6 落后 94。用停滞方拖住就绪方
   代价倒挂。P6 追完 main 后再解 `episode_semantic_verifier.py` 那处冲突，`9b4c2310b`
   已示范「两边都保留」的解法。**合 main 仍等用户确认。**
3. 若要更硬的 python 读数，在 `500167e26` 上重跑全量并出带 revision 的收据。
4. 仍不做：部署、重启 8792、付费外审、删生产原件。

## 踩过的坑
- **退出码被吃了两次**：`cmd 2>&1 | tail` 后 `$?` 是 `tail` 的；`echo` 之后再读
  `${PIPESTATUS[0]}` 已被重置。第一次把 `check` 的 exit 1 读成 0，差点把「有漂移」报成
  「没漂移」。改法是 `cmd >file 2>&1 ; RC=$?` 或按 AGENTS.md 原样用 `&&` 串联取一个总码。
- **「跳过造的绿」不是绿**。第一次在本树跑 registry check 五条全 exit 0，但第二条自己
  印了「部分仓在场（['ws']），跨仓项已跳过；忽略缺仓 skill 23 个」——那 23 个正是 kb 的
  全部 skill。读校验器输出要先看它声明跳过了什么。
- **动手前先扫同题分支**。`fix/agent-docs-audit-registry` 的标题就是这件事，不扫就会
  重复造轮子；扫了才发现它落后 1018 个提交、不能直接用。

## 工具沉淀盘点
无新增生产执行器。可迁移的是「隔离父目录 + 真仓名 worktree + 同级仓软链」这个取数姿势：
凡是按 `REPO_ROOT.parent` 找同级仓的门禁，在附属 worktree 里都会静默跳过或扫错树，
造出一个看起来合理的绿。

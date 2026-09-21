# 研究求证意识：候选合入 main 与复核收口（2026-09-21）

## 合入

| PR | 内容 | 合入提交 |
|----|------|----------|
| #818 | `skills.registry.json` 重扫（`kb/rag-query` 跨仓漂移，KB `bc9e8c2b8` 之后） | `8257ac420` |
| #819 | `feat/research-reasoning-awareness@500167e26`（14 提交，31 文件 +1879/−38） | `2bb7c224c` |
| #820 | 复核分支交接 + 本文 | 本 PR |

用户授权：对话中「合并」（2026-09-21）。顺序 #818 → #819 → #820；每个合入前 `git fetch gitea` 后
`git merge-tree --write-tree gitea/main <head>` 重探，均 exit 0。

## 合入前门禁（对合并预览 `5b34e2702` = main `8aff6ebc3` + #818 + #819 + #820）

预览树用 `merge-tree --write-tree` + `commit-tree` 造在 `/Users/a77/fwp-wt-merge-preview-0921`，不动任何分支；
父目录 `/Users/a77` 使 kb / site 同级仓可见，registry 检查是真比对不是跳过。

| 叶子 | 读数 |
|------|------|
| python | **12082 passed / 85 skipped / 2 xfailed / 0 failed**，exit 0，25m00s；收据 `~/.finance-runtime/test-receipts/20260921T041458Z-5b34e270.json`（同 revision 另有 `…T035944Z` counts 全 0 的嵌套空收据，勿取） |
| ruff | 绿 |
| registry-check | `check-parseability` / `check` / `backfill-tables --check` / `generate-views --check` / `audit_ledger_spec_crosswalk` 五条 exit 0 |
| frontend | `pnpm install --frozen-lockfile && lint && typecheck && test && build` exit 0；vitest 110 passed / 8 files；build 后树 dirty 0 |
| e2e | 34 passed / 2 skipped（`WORKBENCH_PYTHON` 指主树 venv，`WORKBENCH_E2E_PORT=8793`） |

合并时 main 已从 `8aff6ebc3` 走到 `5ded1a019`（#821 / #822，4 提交，`git diff --name-only` 非文档文件 0），
按「docs-only 漂移切换 gated ancestor」处理，未重跑。#818 合入后核对 main 只多 `skills.registry.json` 一个文件，再合 #819。

## 候选状态（合入 ≠ 行为验收通过）

- 功能默认 off：`intelligence/services/research_reasoning.py` `ENV_FLAG = "FINANCE_RESEARCH_REASONING"`，
  `os.environ.get(ENV_FLAG, "off")`，未开启则运行时零注入。本次合入不改默认行为、不部署，8792 未动。
- 候选自列边界仍成立：独立语义盲审 `passed=false`（拒 `[1,2,3,5]` 接 `[4,6]`；E4 显示 2026-09-09 上证 **+0.278**
  而输出把「9-09/9-10 连跌」当保留事实，第 5 句符号写反），状态 `OBSERVATION_ONLY`；数字句仍被门删；V4 `n=2`；
  P5 待 P7；P6 binding 未入。原件 `~/.finance-runtime/reasoning-boundaries-20260921/semantic-k3-independent-3/`。
- 两份已合分支 inflight（`feat-research-reasoning-awareness.md`、`claude-research-reasoning-awareness-review-f65597.md`）
  随本 PR 出册。候选正文见 `docs/handoffs/2026-09-20-research-reasoning-awareness.md`、
  `2026-09-21-prior-evidence-review.md`、`2026-09-21-reasoning-input-boundaries.md` 及 `docs/verification/` 同名文件；
  复核过程（四叶补读、`kb/rag-query` 漂移定性、#818 撞车）见本分支历史 `e6ab52f74`、`8559e6580`。

## 清理

- 已删：worktree `fwp-wt-research-reasoning-awareness`、分支 `feat/research-reasoning-awareness`（远端由 Gitea
  `delete_branch_after_merge` 删）、本地 `fix/registry-kb-rag-query-drift`（`3c344b61e`，内容 = #818）、
  scratch 树 `p6-integration-tree`、`registry-allpresent-20260921`。
- 保留：tag `archive/p6-integration-dryrun-9b4c2310`；他人树 `fwp-wt-registry-scan-0921`（分支 `fix/registry-scan-0921`
  已合、远端已删，本地由其 owner 清）。

## 下一步

1. P6 #770（`fix/e2-material-closeout@b1c1c29f2`，落后 main 94+）：owner 前向合并 main，解
   `intelligence/services/episode_semantic_verifier.py` 与 `.claude/lessons_learned.md` 两处冲突，重跑四叶 + 独立语义验收。
   旧演练 `archive/p6-integration-dryrun-9b4c2310` 示范过「两边都保留」的解法，但 P6 此后又走了 77 个提交。
2. 研究求证意识的行为验收仍开放：开 `FINANCE_RESEARCH_REASONING` 前要过独立语义盲审。
3. 部署 / 重启 8792 / 付费外审 / 删生产原件：未授权，未做。

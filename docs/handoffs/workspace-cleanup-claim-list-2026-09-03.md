# 工作区认领清单 · 2026-09-03

## 执行回执（2026-09-03 下午，按用户拍板：夜跑退役 / 复盘 HTML 留本地 / 其余按最优处理）

**已做**

| 项 | 动作 | 结果 |
|---|---|---|
| §3 双盲夜跑 | `launchctl bootout` + plist 归档 `~/Library/LaunchAgents/disabled-by-devin/com.financeworkspace.dual-blind-forecast.plist.retired-2026-09-03` | `launchctl list` 已不见；它是 08-28 23:00 被装回的（PR #498 那批），仓内 `intelligence/dream/*.plist` 只是模板勿再装 |
| §2A/§2B/§2C 产物 | 141 件（2.3 MB）在干净树提交，PR [#558](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/558) 待合 | 含 IMA 缺口清单登记进台账地图、双盲 08-31～09-03 终档、7 月反思候选 |
| §2A 复盘 HTML | 不提交（用户拍板），`.gitignore` 加 `复盘/daily/`（PR #558） | 已入库的 218 份历史保持原样 |
| §2B/§2D 忽略 | `.gitignore` 加 `*-framework-interpretation.md`、`intelligence/users/*/answer_scores.jsonl`、`.workbuddy/`（PR #558） | 合入后主树只剩另一个 agent 的 content-ops 在途 + 本清单 |
| §1a 金融仓干净树 | 63 棵全部 `git worktree remove`（逐棵先验 status 为空，无一 --force） | `~/fwp-wt-*` 21 GB → 12 GB |
| §1d 生产快照 | 71 个拆掉；保留 `c88c81da5120`（8792 现役）、`d4fade5494ee`（回滚锚，部署账本 04:46 那条）、`40fd5a847c65`（capability-sidecar 在跑）、`7afe37be1913`（glm-canary 启动器引用）、两个 dirty、`profile-ratchet`（未合分支） | `~/.finance-runtime` 11 GB → 2.1 GB；8792 拆后 HTTP 200，sidecar 进程在 |
| §4a 知识库干净树 | 21 棵拆掉；**保留 `~/kb-wt-rss-l3-nightly-report`**——launchd `com.kb.rss-l3-nightly-report` 直接指向它的脚本 | `~/kb-wt-*` 17 GB → 11 GB，`~/.devin-worktrees` 1.7 GB → 0.7 GB |
| 两仓 `worktree prune` | 清掉 1 条失效登记 | — |

合计回收约 25 GB；金融仓树 211 → 89（含本轮新开的 `~/fwp-wt-daily-review-json`、`~/fwp-wt-sweep-0903` 两棵 PR 树），知识库仓 60 → 38。

**第二轮（同日下午，用户拍板：脏树与未合树按最优推进）**

- `com.kb.rss-l3-nightly-report` 已改指知识库主树（plist `ProgramArguments`/`WorkingDirectory`），重载后试跑 rc=0，`~/kb-wt-rss-l3-nightly-report` 已拆。
- 只处置**不活跃（≥3 天无提交/reflog/文件改动）且没挂 PR** 的树：金融仓 62 棵、知识库仓 16 棵。规则与逐棵明细见 `docs/handoffs/branch-closeout-2026-09-03.md`（随 PR #558 入库）：
  - 补丁已在基线 / 提交标题已在 main / 落后 >300 → 拆树，分支引用保留；未提交改动先封存（43 处 `salvage/*` 或 `wip(salvage)` 提交；4 处被 pre-commit 拦下改为 patch+拷贝落 `~/kb_work/worktree-salvage-2026-09-03/`）。
  - 未合且落后 ≤300 → 推送开 PR、树保留：金融 [#562](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/562)（干净）、[#563](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/563)（有冲突）；知识库 #133～#139（#138、#139 干净，其余需 rebase）。
  - 结果：金融仓树 88 → 29，知识库仓 37 → 28；`~/fwp-wt-*` 12 → 3.8 GB，`~/kb-wt-*` 11 → 8.5 GB；8792 仍 200。
- 活跃的树（金融 18、知识库 17）和挂 PR 的（#517、#458；知识库 #129/#94/#26）一律没动——其中几棵今天还在被别的 agent 编辑。

**仍留给你**

- `~/.finance-runtime/` 里 `437cd5e9aa1a`、`437cd5e9aa1a-rollback`、`773b3d7e73d7` 三个目录不是注册的 worktree（普通目录），没动。
- 知识库主树 43 个改动（6 个实体页被改、AGENTS.md、两个 hooks、25 个入库队列文件）：像是别的 agent 在主树上的在途，没碰。
- PR 待验收：[#555](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/555)、[#558](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/558)（含本轮两份台账），以及上面新开的 9 个"搬到评审队列"的 PR——合不合由你定，不合请关闭并留指针。

**第三轮（同日傍晚验收）**

亲手核：看板 `30 棵 · 还有补丁 12 · 已在基线 8`（执行方报 29/12/6；多出的树是下午别人合完留下的干净 leftover，及主检出已切到 `feat/content-ops-copilot`）。rss-l3 plist 指向知识库主树、15:44 报告已写、`~/kb-wt-rss-l3-nightly-report` 已不在；`~/kb-runtime` 确为 disclosure-scout 运行时。8792 HTTP 200，现役 `f4c03b9ae610`（0903e，不是盘点时的 `c88c81da`）。

合入：#558（本 sweep）、#555（日报 JSON 真本源，与 #558 台账交叉引用）、#562（画像长度棘轮，main 上仍缺）。知识库 #138（08-26/27/28 队列清零，合并干净）。

关闭留指针：#563（`R-20260828-05/06/07` 在 main 已是 confirmed；补丁会改写今天的 `inflight/main.md`）。知识库 #133/#134/#135/#136/#137/#139（收拾自动开、需 rebase；分支引用仍在）。

未碰：#550/#556/#561/#517/#458；知识库 #129/#94/#26；知识库主树 43 个在途改动。

`~/.finance-runtime` 三个 08-16 独立克隆（SHA 已在 main）迁到 `~/kb_work/runtime-clone-archive-2026-09-03/`。下午已合入、树干净的 leftover 拆掉。

---

> 以下为盘点原文（14:00 前后读数），只盘点、不删。每一条都是「这个改动/这棵树是谁的、该去哪」的问题，答完再动手。
> 读数来源：`scripts/worktree_board.py`（基准 gitea/main=78fb86396ec5）、`git status`、`git worktree list`、`du`。
> 配套改动：台账 JSON 真本源 + Workbench 复盘页补全在 PR #555（`feat/daily-review-json-canonical`），与本清单无耦合。

## 0. 读数

| 项 | 数 |
|---|---|
| 金融仓 worktree | 211 棵（含 78 个 `~/.finance-runtime` 生产快照） |
| `~/fwp-wt-*` 占盘 | 21 GB |
| `~/.finance-runtime` 占盘 | 11 GB |
| `~/kb-wt-*` 占盘 | 17 GB |
| `~/.devin-worktrees` 占盘 | 1.7 GB |
| 金融仓主树未提交 | 154 个文件，全部 untracked（无已跟踪文件被改） |
| 知识库仓主树未提交 | 43 个（32 untracked + 11 modified） |
| 知识库仓 worktree | 60 棵（44 已合入、12 未合入、3 detached、1 主树） |

## 1. 金融仓 worktree

### 1a. 补丁已在基线、树干净 —— 可直接拆（63 棵）

逐条确认「路径里没有你还想留的未跟踪文件」后执行（`git worktree remove` 遇到未跟踪文件会拒绝，届时再加 `--force`）：

```bash
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-qc-489   # (detached)
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-qc-520   # (detached)
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-qc-main-tip   # (detached)
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-retire-stale-matrix   # chore/retire-unconsumed-matrix-md
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-swl1-fill   # data/sw-l1-mapping-fill
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-selfuse-ledger   # docs/26h-eight-pr-closeout
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-docs-355-cutover   # docs/355-cutover-48601e08
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-docs-489   # docs/489-gate-cutover
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-docs-489-live   # docs/489-live-reeval
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-answer-hygiene-p1   # docs/8792-dfc25221-cutover
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-docs-ablation-closeout   # docs/ablation-521-522-closeout
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-qc-0828   # docs/cutover-28c-490
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-disclosure-p1c   # docs/disclosure-p1c-closeout
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-sector-disclosure-scan   # docs/disclosure-residual-closeout
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-disclosure-scout   # docs/disclosure-scout-pointer
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-intraday-l2-sidecar   # docs/intraday-l2-sidecar
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-kb-path-fail-closed   # docs/kb-379-closeout
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-docs-knevo-2b   # docs/knevo-2b-wired
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-docs-outlook-362-closeout   # docs/outlook-362-closeout
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-exec-queue   # docs/post-disclosure-execution-queue
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-qc-0827   # docs/qc-0827-gate-and-ledger-workorder
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-reading-direction-gate   # docs/reading-direction-gate-live
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-docs-step-trajectory-qualification   # docs/step-trajectory-qualification
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-docs-theme-envelope   # docs/theme-envelope-subject-closeout
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-tool-catalog-gate   # docs/tool-catalog-unification-gate
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-live-loop-r1   # docs/w5-backfill-live
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-contract-honor   # feat/contract-honor-p0c
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-dream-mine-p0   # feat/dream-mine-p0
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-finance-query-global-stock   # feat/finance-query-global-stock
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-finance-query-regulation   # feat/finance-query-regulation
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-capability-switchboard-main   # feat/market-watch-knowledge-gate
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-d8d11-asof   # feat/orchestration-specs-v4
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-outlook-ungrounded-threshold   # feat/outlook-ungrounded-threshold
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-personalized-join-kernel   # feat/personalized-join-kernel
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-research-program-compiler   # feat/research-program-compiler
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-tool-hunger   # feat/tool-hunger-telemetry
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-substitute-probe   # feat/verify-timepoint-forward-slot
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-watchlist-digest   # feat/watchlist-digest-pack
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-width-bag   # feat/width-resonance-bag
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-content-delta-raw   # fix/content-delta-exclude-raw-queue
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-daily-full-write-guard   # fix/daily-full-prod-write-guard
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-eval-launchd-repair   # fix/eval-launchd-loop-repair
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-evidence-bound-window   # fix/evidence-bound-window
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-fph-auth   # fix/fupanhui-auth-fallback
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-judge-cli-synthesis   # fix/judge-cli-synthesize-transport
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-judge-honesty   # fix/judge-honesty-p0b
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-judge-reject-resolve   # fix/judge-reject-partial-resolution
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-publication-gate   # fix/publication-gate-lamp
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-publication-qc-off-table   # fix/publication-qc-off-table
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-publication-view-deepen   # fix/publication-view-deepen
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-quickfact-f1-f3   # fix/quickfact-finance-query-routing
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-radar-fact-status   # fix/radar-fact-status-not-delta
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-receipt-dirty   # fix/receipt-dirty-first-line
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-registry-budget   # fix/registry-budget-truncation
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-shadow-trace   # fix/shadow-trace-fact-delivery
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-theme-envelope-subject   # fix/theme-envelope-subject
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-threshold-gate   # fix/unregistered-threshold-gate
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-gate-liveness   # fix/watch-gate-liveness-signal
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-fd-leak   # fix/workbench-db-fd-leak
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-write-turn-grant   # fix/write-turn-synthesis-grant
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-merge-d3-d4   # merge/d3-d4
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-merge-p0-abc   # merge/p0-abc
git -C ~/finance-workspace-private worktree remove ~/fwp-wt-prefetch-replay   # verify/prefetch-replay
```


### 1b. 补丁已在基线、但树里有脏文件 —— 先认领脏文件再拆（30 棵）

先 `git -C <树> status --short` 看脏的是什么：是产物就丢，是没提交的代码就另开分支救回。

| 树 | 分支 | 脏文件数 |
|---|---|---|
| `~/fwp-wt-ablate-s2` | `ablate/s2-pronoun` | 1 |
| `~/fwp-wt-handoff-0822` | `chore/handoff-close-0822` | 2 |
| `~/fwp-wt-mainflow` | `docs/inputside-closeout-r2-spec` | 1 |
| `~/fwp-wt-request-loop-map` | `docs/request-loop-three-paths` | 3 |
| `~/fwp-wt-verifier-ablation` | `docs/verifier-ablation-e` | 1 |
| `~/fwp-wt-event-calendar-serving` | `feat/event-calendar-serving` | 1 |
| `~/fwp-wt-forecast-residual-followup` | `feat/forecast-residual-followup` | 1 |
| `~/fwp-wt-judge-verdicts` | `feat/judge-sentence-verdicts` | 1 |
| `~/fwp-wt-rag-window` | `feat/rag-window-gate-and-worker-keepalive` | 1 |
| `~/fwp-wt-retire-feishu-market-daily` | `fix/retire-feishu-market-daily` | 1 |
| `~/fwp-wt-ablate-s1` | `ablate/s1-candidate` | 代码脏文件 |
| `~/fwp-wt-ablate-s3` | `ablate/s3-slots` | 代码脏文件 |
| `~/fwp-wt-ablation-noise-floor` | `feat/ablation-judge-independence` | 代码脏文件 |
| `~/fwp-wt-agent-trace` | `feat/agent-adhoc-trace` | 代码脏文件 |
| `~/fwp-wt-candidate-no-terminate` | `fix/candidate-no-terminate` | 代码脏文件 |
| `~/fwp-wt-chat-idle` | `fix/chat-idle-no-git-ritual` | 代码脏文件 |
| `~/fwp-wt-codex-workbench-product-value-spec` | `codex/docs-codex-workbench-product-value-spec` | 代码脏文件 |
| `~/fwp-wt-docs-cap-0903b` | `docs/capability-line-0903b` | 代码脏文件 |
| `~/fwp-wt-eval-p0-abc` | `eval/p0-abc-rerun` | 代码脏文件 |
| `~/fwp-wt-forecast-residual-deep` | `feat/forecast-residual-deep` | 代码脏文件 |
| `~/fwp-wt-outlook-live-weekly-pack` | `feat/outlook-live-weekly-pack` | 代码脏文件 |
| `~/fwp-wt-qc-0826` | `(detached)` | 代码脏文件 |
| `~/fwp-wt-qc-439` | `(detached)` | 代码脏文件 |
| `~/fwp-wt-qc-443` | `(detached)` | 代码脏文件 |
| `~/fwp-wt-qc-489-e2e` | `(detached)` | 代码脏文件 |
| `~/fwp-wt-qc-conformance` | `(detached)` | 代码脏文件 |
| `~/fwp-wt-step-trajectory-qualification` | `feat/step-trajectory-qualification` | 代码脏文件 |
| `~/fwp-wt-webapp-beautiful-ui` | `fix/webapp-ime-enter-and-beautiful-ui` | 代码脏文件 |
| `~/fwp-wt-wind-l2-adapter` | `feat/wind-l2-adapter` | 代码脏文件 |
| `~/fwp-wt-workbench-quality-ceiling` | `codex/workbench-quality-ceiling` | 代码脏文件 |


### 1c. 还有补丁真没合 —— 逐条决定：开 PR / 关闭留裁决（47 棵）

> 不在下表、但也别动：`~/fwp-wt-daily-review-json`（`feat/daily-review-json-canonical`，PR #555 待你验收合入，合入后由托管端删分支、本地再拆树）。

按落后 main 的提交数倒序。落后 > 600 的多为 7～8 月的 docs/spec 收口，大概率已被后续 PR 取代，用 `git diff <branch> gitea/main -- <files>` 树对树零差即 superseded（验收规程 #120 先例），关闭并留指针。

| 分支 | 补丁 | 落后 main | 树 | 脏 | 最后一条提交 |
|---|---|---|---|---|---|
| `chore/artifact-writeback-0814` | +1 -0 | 1469 | `~/fwp-wt-artifacts` | dirty | docs(verification): 库里没有的题两臂 live 首读——web 链路端到端能通、判官放行 publi |
| `feat/proactive-checks` | +3 -8 | 1456 | `~/fwp-wt-proactive-checks` | CODE_DIRTY | feat(reading-baseline): 批二 13 条挂数据块 + 批三 4 条挂缺口待激活 |
| `spec/continuous-depth-gap-r1` | +3 -0 | 1361 | `~/.finance-runtime/finance-s7-sync` | - | docs(spec): R4 勘误——P0/P1-C/E5 已入 main，P1-E 改为相对 08-13 增量 |
| `docs/dead-assets-ask-wiring` | +1 -0 | 1059 | `~/fwp-wt-dead-assets-ask` | - | docs(handoff): 派死资产想得到用单——ask D13–D16 意图门控 |
| `fix/data-root-wiring` | +1 -0 | 1059 | `~/fwp-wt-data-root-wiring` | CODE_DIRTY | fix(paths): 摘掉数据根查找序里的 WORKBENCH_REPO_ROOT |
| `feat/dead-assets-consumption` | +2 -0 | 1059 | `~/fwp-wt-dead-assets` | - | docs(alpha): §1.5 额度账本（赠送 + 月度充值）运行手册与 CLI 用法；§4 边界补 flock 与 |
| `eval/frozen-thirty-live-baseline` | +1 -0 | 1002 | `~/fwp-wt-frozen-thirty-live` | - | eval: 冻结 30 题 live 基线（sidecar grounded，回归锚） |
| `fix/gate-partial-release` | +3 -0 | 913 | `~/fwp-wt-gate-release` | - | docs(handoff): fix/gate-partial-release 在途交接 |
| `chore/retire-dual-blind-nightly` | +1 -0 | 815 | `~/fwp-wt-retire-dual-blind` | - | chore: 夜跑拆掉双盲答卷回检，并记下 08-19 补洞收口 |
| `docs/harness-success-path-spec` | +1 -0 | 758 | `~/fwp-wt-harness-success-path` | dirty | docs: 路由后 harness 成功路径宪章（v1.1，记下子单 C） |
| `feat/ceiling-sensors` | +2 -0 | 710 | `~/fwp-wt-ceiling-sensors` | - | docs: 补 W5 变异复现与全量门禁读数 |
| `fix/numeric-unsupported-anchor-backfill` | +3 -0 | 710 | `~/fwp-wt-w3-numeric-backfill` | - | docs: 补 W3 全量门禁收据 |
| `fix/w2-mandatory-satisfiability` | +3 -0 | 709 | `~/fwp-wt-w2-satisfiability` | - | docs: 补 W2 干净树全量收据 a132f15f（5904P/0F） |
| `fix/ceiling-required-block-degrade` | +1 -0 | 708 | `~/fwp-wt-w1-ceiling-degrade` | - | fix: 判官对必需输出块降级保留，道歉横幅只归全灭闸（R-20260821-07） |
| `fix/v4-kb-index-hygiene` | +4 -0 | 702 | `~/fwp-wt-v4-kb-index-hygiene` | - | docs(V4): 回填变异击杀 3 条与液冷重放前后 top-5 |
| `feat/v3-kbsearch-coarse-pipe` | +3 -0 | 699 | `~/fwp-wt-v3-kbsearch-coarse-pipe` | - | docs(V3): 复算命令去掉易碎的路径行字面量 |
| `feat/v7-inputside-kb-sensors` | +2 -0 | 698 | `~/fwp-wt-v7-inputside-sensors` | - | docs(V7): 输入侧 KB 传感器验证文档——金标五案例 + TDD/变异证据 |
| `(detached)` | +1 -0 | 633 | `~/.finance-runtime/finance-workspace-f7ae6a0aeddd` | - | fix(routing): 完整题不被指代粗信号一票否决 |
| `fix/judge-mixed-method-subtract` | +1 -0 | 633 | `~/fwp-wt-judge-mixed-subtract` | - | fix(judge): mixed 契约不再整篇封闭世界 |
| `(detached)` | +2 -0 | 633 | `~/.finance-runtime/finance-workspace-a3fb3304bfb6` | - | fix(judge): mixed 契约不再整篇封闭世界 |
| `fix/qizhong-pronoun-routing` | +2 -0 | 633 | `~/fwp-wt-qizhong-pronoun-routing` | - | fix(judge): mixed 契约不再整篇封闭世界 |
| `(detached)` | +7 -9 | 632 | `~/.finance-runtime/finance-workspace-8aa5df90fcf9` | - | test(switchboard): 质量棘轮补双红/涨停探针 |
| `(detached)` | +8 -9 | 632 | `~/.finance-runtime/finance-workspace-9bdd6b85a708` | - | test(switchboard): 质量棘轮补双红/涨停探针 |
| `(detached)` | +9 -10 | 632 | `~/.finance-runtime/finance-workspace-1c52e19f9957` | - | test(switchboard): 质量棘轮补双红/涨停探针 |
| `(detached)` | +9 -9 | 632 | `~/.finance-runtime/finance-workspace-95c644be5621` | - | test(switchboard): 质量棘轮补双红/涨停探针 |
| `docs/capability-switchboard` | +9 -10 | 632 | `~/fwp-wt-capability-switchboard` | dirty | test(switchboard): 质量棘轮补双红/涨停探针 |
| `feat/reading-rules-baseline-r2` | +1 -9 | 631 | `~/fwp-wt-reading-rules-baseline` | - | feat(reading-baseline): 判读方法内置为领域基线（批一 8 条） |
| `feat/activation-receipt` | +1 -0 | 624 | `~/fwp-wt-activation-receipt` | - | feat(harness): 激活收据——标题只认注入，不认用户点了谁 |
| `(detached)` | +13 -9 | 623 | `~/.finance-runtime/finance-workspace-4a35944e46b1` | - | test(switchboard): 质量棘轮补双红/涨停探针 |
| `align/switchboard-catchup` | +13 -9 | 623 | `~/fwp-wt-switchboard-align` | dirty | test(switchboard): 质量棘轮补双红/涨停探针 |
| `docs/market-watch-component-first` | +2 -0 | 614 | `~/fwp-wt-market-watch-component-first-spec` | - | docs(spec): 盘面组件包 v2，按核稿改落点 |
| `docs/knevo28-p0a-view-deepen` | +6 -0 | 614 | `~/fwp-wt-knevo28-p0a-view` | dirty | docs(spec): v3 输入可加、输出闸只减 |
| `cursor/harness-ceiling-followup-spec-3f68` | +8 -0 | 614 | `~/fwp-wt-harness-ceiling-followup-spec` | dirty | docs(spec): v3 输入可加、输出闸只减 |
| `(detached)` | +13 -9 | 613 | `~/.finance-runtime/finance-workspace-76ee1e89ed8a` | - | test(switchboard): 质量棘轮补双红/涨停探针 |
| `align/switchboard-p0` | +14 -9 | 613 | `~/fwp-wt-switchboard-p0-align` | - | test(switchboard): 质量棘轮补双红/涨停探针 |
| `codex/code-map-request-loop` | +11 -0 | 605 | `~/fwp-wt-code-map-land` | dirty | feat: add Code Map request-loop narrative |
| `(detached)` | +3 -0 | 574 | `~/.finance-runtime/finance-workspace-9d204ad63cec` | - | docs: 本单收据与台账（R-20260824-01/02，pending） |
| `(detached)` | +5 -0 | 574 | `~/.finance-runtime/finance-workspace-7afe37be1913` | - | docs: 本单收据与台账（R-20260824-01/02，pending） |
| `fix/forward-action-question-routing` | +6 -0 | 574 | `~/finance-workspace-private/tmp/fix-numeric-backfill` | - | docs: 本单收据与台账（R-20260824-01/02，pending） |
| `docs/workbench-quality-residual-ux` | +1 -0 | 572 | `~/fwp-wt-docs-workbench-quality-residual-ux` | - | docs(spec): 品质残差预算 v1.1，收审查 PASS-WITH-NITS |
| `codex/feat-workbench-research-journey` | +19 -0 | 506 | `~/fwp-wt-workbench-research-journey` | CODE_DIRTY | feat: model workbench research journey |
| `feat/finance-query-technical-daily` | +1 -0 | 480 | `~/fwp-wt-technical-daily` | dirty | feat(finance-query): 注册监管池/事件/历史映射，时间轴走快照日 |
| `feat/public-daily-brief` | +1 -0 | 272 | `~/fwp-wt-public-brief` | - | feat(public-brief): 公开晚报 P0——许可白名单渲染的可分享一页（spec+包+CLI） |
| `docs/ledger-r05-07-live-close` | +1 -0 | 178 | `~/fwp-wt-ledger-close-0828` | - | docs(ledger): R-20260828-05/06/07 切流后收口——三行全 confirmed，#488  |
| `fix/perspective-profile-ratchet` | +1 -0 | 178 | `~/.finance-runtime/finance-workspace-profile-ratchet` | - | fix(perspective): 画像整表回写按长度棘轮，挡住薄副本盖厚画像 |
| `fix/judge-fallback-cli-backend` | +2 -0 | 122 | `~/fwp-wt-judge-cli-fb` | - | docs: 回写干净树全量 7291P 收据（R-20260830-01） |
| `perf/wiki-hybrid-25s` | +8 -0 | 113 | `~/fwp-wt-wiki-aperture-ablation` | - | eval: 加预算旋钮，好在 90s 之外谈三铲 |


### 1d. 生产快照 —— 只留 8792 当前（c88c81da）+ 一个回滚锚

共 78 个；dirty=true 的 2 个：
- `6320b3bcbf82  dirty=true  ~/.finance-runtime/finance-workspace-6320b3bcbf82`
- `a97bfd57d31f  dirty=true  ~/.finance-runtime/finance-workspace-be7c1e7eac81`

其余 dirty=false 的可拆；两个 dirty=true 的先看脏的是什么。

## 2. 金融仓主树 154 个未提交文件

盘点时（09-03 13:40 前后）全部是 untracked，没有已跟踪文件被改，所以主树本身没有「在途代码」；乱在于六天产物没提交、几类新产物没登记去向。

> ⚠️ 盘点后约一小时，主树出现了另一个 agent 的在途改动（`CLAUDE.md`、`skills.registry.json`、`scripts/validate_marketing_contracts.py` 被改，新增 `skills/content-ops-copilot/`、`docs/marketing/*`、`scripts/marketing_moderation_report.py` 等）。**做 §2A 提交时只用 pathspec 点名下表里的路径，别碰这些。**

### 2A. 该提交（历史上同类产物都在仓里，只是从 08-26 起没人提交）

| 组 | 文件 | 已跟踪的同类 |
|---|---|---|
| 复盘 HTML | `复盘/daily/2026-08-26 … 2026-09-02/`（6 天） | 218 份 |
| 题材候选/回填队列 | `exports/*-theme-candidates.md` ×6、`*-theme-backfill-queue.json` ×6、`*-theme-backfill-review-queue.{json,md}` ×12 | 49 / 47 / 38 |
| 研究队列与 Agent 简报 | `exports/*-research-queue.{json,md}` ×12、`*-daily-agent.md` ×6、`*-daily-agent-summary.json` ×2 | 8 / 27 / 1 |
| 工作流摘要 | `exports/*-daily-workflow-summary.json` ×6 + `2026-08-31-…-resume.json` | 35 |
| 知识库入库队列 | `exports/*-kb-ingest-queue.json` ×6 | 21 |
| 评测运行 | `intelligence/eval/runs/` ×50 | 80 |
| 复盘质量收据 | `skills/daily-full-review/state/quality-2026-08-26 … 09-02.json` ×6 | `skills/*/state/` 按 .gitignore 注释是跟踪的 |
| 双盲台账 | `docs/learning/forecast-review-ledger/2026-08-31 … 09-03.{manifest,answer.claude}.json` ×8 | 台账地图标「提交=是」 |

建议：一次 pathspec 提交（`git add -- <上面这些路径>`，禁 `git add -A`），提交信息写「产物回补 08-26～09-03」。

### 2B. 新品类、台账地图没登记 —— 先决定去向

| 文件 | 情况 | 建议 |
|---|---|---|
| `exports/*-ima-gap.{json,md}` ×8 | 全量复盘 `ima-gap-report` 步的产物，0 份已跟踪，`docs/learning/ledger-map.md` 无此行 | 要留就登记进台账地图再提交；不留就加 .gitignore |
| `exports/*-framework-interpretation.md` ×5 | 框架解读输出，正文含「最近纠偏回灌」原文（账号名、权益状态等个人语境） | 建议 .gitignore（用户态内容，和 `intelligence/users/*` 同性质） |

### 2C. 孤儿

| 文件 | 情况 | 建议 |
|---|---|---|
| `docs/learning/forecast-lessons/reflections/2026-07-02 … 07-17.reflection.*.json` ×12 | 双盲错因反思候选，台账地图标「提交=是」，但 7 月的从未提交，之后也没新产出 | 补提交归档，或确认那条线已停就移到 `archive/` |

### 2D. 应 .gitignore

| 路径 | 情况 | 建议 |
|---|---|---|
| `.workbuddy/memory/` | WorkBuddy 工具的本地记忆 | 加 `.workbuddy/` 到 .gitignore（与 `.windsurf/` 同类） |
| `intelligence/users/ablation-veteran-probe/` | 08-28 消融探针用户目录；`answer_scores.jsonl` 不在 `intelligence/users/*/…` 忽略清单里，所以目录冒头 | 删目录（探针一次性），或补 `intelligence/users/*/answer_scores.jsonl` 到忽略清单 |

## 3. 双盲夜跑仍在跑（与台账地图矛盾，需二选一）

- launchd `com.financeworkspace.dual-blind-forecast` 仍加载，工作日 09:10 跑 `scripts/dual_blind_auto.sh`；今天 09:26 有产出：`2026-09-03.answer.claude.json` 落了，codex 未落答卷（1/2）。
- `docs/learning/ledger-map.md` 对复盘输入冻结 / 答卷 / 验证三行都写着「**夜跑已退役**，仅手动」。
- `~/fwp-wt-retire-dual-blind` 的 `chore/retire-dual-blind-nightly`（+1，落后 815）就是那次退役的 PR，从没合。
- 二选一：合入退役 PR 并 `launchctl bootout gui/$(id -u)/com.financeworkspace.dual-blind-forecast`；或撤回台账地图里「已退役」三处标注、并修 codex 那条腿。

## 4. 知识库仓（`~/knowledge-base-private`）

### 4a. 已合入、树干净 —— 可直接拆（22 棵）

```bash
git -C ~/knowledge-base-private worktree remove /Users/a77/.devin-worktrees/briefing-0817-0820   # briefing/0817-0820
git -C ~/knowledge-base-private worktree remove /Users/a77/.devin-worktrees/briefing-backfill-0818   # briefing/backfill-0727-0816
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-l1-queue-pre825   # concept/l1-queue-pre825
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-concept-pharma-0828   # concept/pharma-l1-0828
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-equip-0825   # disclosure/equip-0825
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-invic-0825   # disclosure/invic-0825
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-l3-0831   # disclosure/l3-0831
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-l3-rss-pending   # disclosure/l3-rss-pending
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-disclosure-optical-0825   # disclosure/optical-cpo-0825
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-disclosure-scout   # disclosure/queue-scout
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-rss-l3-nightly-report   # disclosure/rss-l3-nightly-report
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-disclosure-scout-archive   # disclosure/scout-auto-archive
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-scout-cron   # docs/scout-cron-install
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-bookgap-s9   # feat/bookgap-s9-rerank-eval
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-annual-quality-repair   # fix/annual-baseline-quality-repair
git -C ~/knowledge-base-private worktree remove /Users/a77/.devin-worktrees/rss-l3-auto-promote   # fix/rss-l3-cron-gitea
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-ima-smarthome-0831   # ingest/smarthome-deepdive-0831
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-d1-merge   # merge/d1-wave97-onto-main
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-merge-0826   # merge/queue-36-50-0826
git -C ~/knowledge-base-private worktree remove /Users/a77/worktrees/kb-sellside-miracle-0818   # sellside/miracle-gap-0818
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-theme-backfill-review-0828   # theme-radar/backfill-review-0828
git -C ~/knowledge-base-private worktree remove /Users/a77/kb-wt-orphan-queue-pending   # theme-radar/orphan-queue-pending
```

### 4b. 已合入、但树里有脏文件 —— 先认领（22 棵）

其中三棵脏文件上千（`wave97-gold-align-0829` 2712、`annual-wave98-0829` 1093、`ima-stock-0826` 672）——分支合了但树里还有大批没提交的东西，很可能是基线页/逻辑卡批次的半成品，**拆之前必须看一眼**。

| 树 | 分支 | 脏文件数 |
|---|---|---|
| `/Users/a77/kb-wt-wave97-gold-align-0829` | `baseline/wave97-gold-align-0829` | 2712 |
| `/Users/a77/kb-wt-annual-wave98-0829` | `baseline/ashare-wave98-0829` | 1093 |
| `/Users/a77/kb-wt-ima-stock-0826` | `ingest/ima-stock-logic-0826` | 672 |
| `/Users/a77/kb-wt-ima-themes-0828` | `ingest/hot-theme-deepdive-0828` | 114 |
| `/Users/a77/kb-wt-ima-cunchu-0826` | `ingest/storage-chip-deepdive-0826` | 13 |
| `/Users/a77/kb-wt-ima-cpo-0826` | `ingest/cpo-deepdive-0826` | 11 |
| `/Users/a77/kb-wt-ima-renxing-0826` | `ingest/humanoid-robot-deepdive-0826` | 10 |
| `/Users/a77/kb-wt-chat-idle` | `fix/chat-idle-no-git-ritual` | 4 |
| `/Users/a77/kb-wt-queue-gold-0826` | `baseline/queue-gold-0826` | 3 |
| `/Users/a77/kb-wt-leadzinc-deepdive-0826` | `ingest/leadzinc-deepdive-0826` | 3 |
| `/Users/a77/kb-wt-fiber-robot-0825` | `disclosure/fiber-robot-0825` | 2 |
| `/Users/a77/kb-wt-ima-deepdive-auto` | `feat/ima-deepdive-auto` | 2 |
| `/Users/a77/.devin-worktrees/ima-queue-auto-triage` | `fix/rag-gitea-release` | 2 |
| `/Users/a77/kb-wt-baseline-hengyi-0819` | `baseline/hengyi-longjie-0819` | 1 |
| `/Users/a77/kb-wt-queue-bio-0826` | `baseline/queue-bio-0826` | 1 |
| `/Users/a77/kb-wt-queue-bio2-0826` | `baseline/queue-bio2-0826` | 1 |
| `/Users/a77/kb-wt-queue-chem-0826` | `baseline/queue-chem-0826` | 1 |
| `/Users/a77/kb-wt-queue-mix-0826` | `baseline/queue-mix-0826` | 1 |
| `/Users/a77/kb-wt-queue-pharma-0826` | `baseline/queue-pharma-0826` | 1 |
| `/Users/a77/kb-wt-queue-tail-0826` | `baseline/queue-tail-0826` | 1 |
| `/Users/a77/.devin-worktrees/ima-queue-0822` | `concept/ima-queue-0822` | 1 |
| `/Users/a77/kb-wt-polyester-0819` | `concept/l1-polyester-0819` | 1 |

### 4c. 未合入 —— 逐条决定（12 棵）

| 树 | 分支 | 领先 | 脏 |
|---|---|---|---|
| `/Users/a77/kb-wt-briefing-0821` | `briefing/0821-0830` | (+1) | 0 |
| `/Users/a77/kb-wt-baseline-rebuild-0828` | `baseline/rebuild-queue-0828` | (+1) | 1 |
| `/Users/a77/finance-workspace-private/tmp/kb-dual-engine-plan-cb3c4e21` | `codex/kb-dual-engine-plan` | (+1) | 1 |
| `/Users/a77/kb-wt-entity-landing-0816` | `baseline/entity-landing-0816` | (+1) | 78 |
| `/Users/a77/kb-wt-concept-l1-0825` | `concept/l1-precious-industrial-0825` | (+2) | 0 |
| `/Users/a77/worktrees/kb-fact-status` | `disclosure/fact-status-evidence-index` | (+2) | 0 |
| `/Users/a77/worktrees/kb-batch-replay-0819` | `feature/batch-replay-20260819` | (+2) | 0 |
| `/Users/a77/kb-wt-harness-port` | `harness/session-facts-and-receipts` | (+2) | 0 |
| `/Users/a77/kb-wt-queue-drain-0828` | `theme-radar/kb-queue-drain-0828` | (+2) | 1 |
| `/Users/a77/kb-wt-ashare-coverage-gap` | `baseline/ashare-coverage-gap` | (+2) | 771 |
| `/Users/a77/kb-wt-disclosure-archive-0813-0828` | `disclosure/archive-0813-0828` | (+3) | 0 |
| `/Users/a77/kb-wt-ima-slice-0828` | `theme-radar/ima-slice-0828` | (+3) | 11 |

其中 `~/finance-workspace-private/tmp/kb-dual-engine-plan-cb3c4e21` 是把知识库仓的树开进了金融仓的 `tmp/` 里，建议移走或拆掉。

### 4d. 其它（4 棵）

- `/Users/a77/.devin-ci/knowledge-base-private`（(detached)）
- `/Users/a77/kb-runtime`（(detached)）
- `/private/tmp/regcheck-ci/knowledge-base-private`（(detached)）
- `/Users/a77/knowledge-base-private`（main）
`/private/tmp/regcheck-ci/knowledge-base-private` 已 prunable，`git -C ~/knowledge-base-private worktree prune` 即可。

### 4e. 主树 43 个改动

- 32 untracked：`wiki/raw/cross-repo-ingest-queue/` ×25、`wiki/raw/disclosures/` ×7、`wiki/raw/theme-radar/` ×1 —— 入库队列与披露原文，按知识库仓自己的入库流程提交或清理；
- 11 modified：6 个实体页（远东股份、透景生命、赛诺医疗、华润双鹤、九强生物、东方海洋）、`AGENTS.md`、`.claude/hooks/load-memory.sh`、`.claude/hooks/check-writeback.sh`、`wiki/relations/access_log.jsonl` 等 —— 实体页改动要确认是不是某棵树的活漏在主树上做了；hooks 与 AGENTS.md 单独成一个小 PR。

## 5. 建议顺序

1. §3 先定：双盲夜跑留不留。它每天都在往 §2A 里加两份文件。
2. §2A 一次提交、§2D 两条 .gitignore、§2B/§2C 各做一个决定 —— 主树从 154 归零。
3. §1a + §4a 干净树直接拆（约 85 棵，预计回收十几 GB）。
4. §1d 生产快照留 2 个。
5. §1b/§4b 有脏文件的树逐棵看，救回代码或确认丢弃后拆。
6. §1c/§4c 未合入的 59 棵按落后程度分批：明显 superseded 的关闭留指针，还活着的补 PR。

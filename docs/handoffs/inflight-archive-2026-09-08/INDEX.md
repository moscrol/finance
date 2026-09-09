# 归档：已合分支的在途交接（2026-09-08 收口）

`docs/handoffs/inflight/` 是**在途**交接：SessionStart 只注入当前分支那一份，接手者读的是活文档。09-08 盘点时目录里有 101 份，其中 93 份的分支已合入且不在 gitea 上——按 `skills/handoff/SKILL.md`「做完、合并、归档的事从 inflight 里删掉，只留在快照」，本目录把它们**原文逐字**搬过来（`git mv`，历史可 `git log --follow`）。

留在 inflight 的：`main.md`（生产基线活文档）、6 份分支仍在 gitea 上的、以及 `fix-ceiling-required-block-degrade.md`（本地分支对 gitea/main `git cherry` 仍有 1 个补丁未合，不能按「做完」处理）。**2026-09-09 追加**：那 6 份里的 5 份（运行底座 P0–P3 + 部署账本读取侧）与本归档单自己的交接已于 09-08 晚 20:59–21:12 合入，一并搬入（见文末「2026-09-09 追加」）；inflight 现余 8 份。

外部文档里「见 `inflight/<分支>.md`」的引用自本文起指本目录同名文件。判「已合」的证据分三类，逐份列在下表：

- **A 合入提交**：gitea/main 上有 `Merge pull request … from <分支> into main` 的合并提交（含 GitHub 时期 `from owner/<分支>`）。
- **B 文首自述已合**：squash/rebase 合入没有合并提交，但交接文首自己写了「已合 #N / 已切」。
- **C 本地分支 git cherry +0**：本地还留着同名分支，对 gitea/main 逐补丁比对全部已在（squash/rebase 合入的形状）；两份本地远端都没分支的按项目笔记判。

共 93 份，368 KB；2026-09-09 追加 7 份 / 23 KB，合计 100 份。

| 文件 | 证据类 | 证据 | 字节 |
|---|---|---|---|
| [`data-source-tiered-sync.md`](./data-source-tiered-sync.md) | A 合入提交 | 9bec1f49 · 2026-09-04 · #578 | 9226 |
| [`docs-8792-dfc25221-cutover.md`](./docs-8792-dfc25221-cutover.md) | A 合入提交 | 4a6e4c94 · 2026-08-27 · #287 | 2994 |
| [`docs-finance-agent-bp.md`](./docs-finance-agent-bp.md) | A 合入提交 | c6e702a6 · 2026-09-04 · #584 | 26853 |
| [`docs-foresight-root-and-span-io.md`](./docs-foresight-root-and-span-io.md) | A 合入提交 | d218772e · 2026-08-28 · #474 | 3703 |
| [`docs-harness-learning-seams.md`](./docs-harness-learning-seams.md) | A 合入提交 | 5e22d283 · 2026-08-22 · #323 | 2049 |
| [`docs-intraday-l2-sidecar.md`](./docs-intraday-l2-sidecar.md) | A 合入提交 | 3df795cd · 2026-08-26 · #412 | 2471 |
| [`docs-judge-window-closeout.md`](./docs-judge-window-closeout.md) | A 合入提交 | e5d7acb0 · 2026-08-20 · #278 | 592 |
| [`docs-macro-map-and-code-map-refresh.md`](./docs-macro-map-and-code-map-refresh.md) | A 合入提交 | 61dd5f79 · 2026-08-27 · #469 | 2237 |
| [`docs-operator-prefetch-os.md`](./docs-operator-prefetch-os.md) | C 分支本地与远端皆无 | 同题 fix-operator-prefetch-os 已合（A 类） | 4557 |
| [`docs-outlook-362-closeout.md`](./docs-outlook-362-closeout.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 843 |
| [`feat-ablation-noise-floor.md`](./feat-ablation-noise-floor.md) | B 文首自述已合 | 已合 main。** #521 → `d31d2197`，#522 → `fb17879a`（含补洞 `1e4df572`） | 17473 |
| [`feat-alpha-run-admission.md`](./feat-alpha-run-admission.md) | A 合入提交 | c88c81da · 2026-09-03 · #547 | 3640 |
| [`feat-branch-level-trace.md`](./feat-branch-level-trace.md) | A 合入提交 | 1010970a · 2026-09-07 · #619 | 3987 |
| [`feat-capability-max-tier.md`](./feat-capability-max-tier.md) | A 合入提交 | 5cc5aa8b · 2026-09-07 · #608 | 2981 |
| [`feat-capability-switchboard.md`](./feat-capability-switchboard.md) | A 合入提交 | 4dd96f6f · 2026-08-24 · #350 | 6032 |
| [`feat-core-stock-local.md`](./feat-core-stock-local.md) | A 合入提交 | f5805c72 · 2026-09-07 · #647 | 13176 |
| [`feat-deploy-ledger.md`](./feat-deploy-ledger.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 1288 |
| [`feat-disclosure-scan-p1c-claims.md`](./feat-disclosure-scan-p1c-claims.md) | A 合入提交 | fe657cbc · 2026-08-26 · #401 | 8344 |
| [`feat-e1-e3-repair-ttl.md`](./feat-e1-e3-repair-ttl.md) | A 合入提交 | 30f98d73 · 2026-08-19 · #240 | 1464 |
| [`feat-e2-revise-first.md`](./feat-e2-revise-first.md) | A 合入提交 | 2c8809c8 · 2026-08-19 · #239 | 1276 |
| [`feat-editorial-local-substitutes.md`](./feat-editorial-local-substitutes.md) | A 合入提交 | a3967af5 · 2026-09-07 · #642 | 3562 |
| [`feat-empty-pool-fallback-query.md`](./feat-empty-pool-fallback-query.md) | A 合入提交 | d4de2e87 · 2026-08-24 · #349 | 1160 |
| [`feat-eval-variance-baseline.md`](./feat-eval-variance-baseline.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 1504 |
| [`feat-event-calendar-serving.md`](./feat-event-calendar-serving.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 1160 |
| [`feat-finance-query-global-stock.md`](./feat-finance-query-global-stock.md) | B 文首自述已合 | 已合 `gitea/main@92686a9c`。 | 1320 |
| [`feat-finance-query-regulation.md`](./feat-finance-query-regulation.md) | B 文首自述已合 | 已合 | 1679 |
| [`feat-followup-d3-projection.md`](./feat-followup-d3-projection.md) | A 合入提交 | 108b6b9e · 2026-08-27 · #249 | 1590 |
| [`feat-forecast-residual-deep.md`](./feat-forecast-residual-deep.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 1183 |
| [`feat-forecast-residual-followup.md`](./feat-forecast-residual-followup.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 1153 |
| [`feat-forward-call-gate.md`](./feat-forward-call-gate.md) | A 合入提交 | 843c0ad7 · 2026-09-07 · #613 | 3024 |
| [`feat-gate-receipt-unify.md`](./feat-gate-receipt-unify.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 1261 |
| [`feat-judge-pending-review.md`](./feat-judge-pending-review.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 2154 |
| [`feat-lane-composition-rules.md`](./feat-lane-composition-rules.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 1046 |
| [`feat-local-plan-no-fupanhui.md`](./feat-local-plan-no-fupanhui.md) | A 合入提交 | 94b522a0 · 2026-09-07 · #640 | 4877 |
| [`feat-market-watch-component-first.md`](./feat-market-watch-component-first.md) | A 合入提交 | af71f048 · 2026-08-24 · #352 | 921 |
| [`feat-methodology-backtest-p0.md`](./feat-methodology-backtest-p0.md) | A 合入提交 | 313b09c9 · 2026-09-04 · #573 | 9443 |
| [`feat-methodology-backtest-p1-gate.md`](./feat-methodology-backtest-p1-gate.md) | A 合入提交 | fe3cf459 · 2026-09-04 · #576 | 5689 |
| [`feat-methodology-backtest-p1-propose.md`](./feat-methodology-backtest-p1-propose.md) | A 合入提交 | b9f66014 · 2026-09-04 · #581 | 4653 |
| [`feat-methodology-backtest-p1-refuted.md`](./feat-methodology-backtest-p1-refuted.md) | A 合入提交 | 9bd0efd7 · 2026-09-05 · #589 | 11348 |
| [`feat-methodology-backtest-p1-stage-baseline.md`](./feat-methodology-backtest-p1-stage-baseline.md) | A 合入提交 | 87d731f7 · 2026-09-05 · #591 | 13258 |
| [`feat-methodology-backtest-p1-stock-labels.md`](./feat-methodology-backtest-p1-stock-labels.md) | A 合入提交 | 443fe3d5 · 2026-09-04 · #585 | 11531 |
| [`feat-observation-script.md`](./feat-observation-script.md) | A 合入提交 | 7c31dd9e · 2026-09-06 · #599 | 5211 |
| [`feat-optional-forward-slots.md`](./feat-optional-forward-slots.md) | A 合入提交 | a2480684 · 2026-08-24 · #361 | 6948 |
| [`feat-outlook-ungrounded-threshold.md`](./feat-outlook-ungrounded-threshold.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 708 |
| [`feat-p1e4-next-watch-consume.md`](./feat-p1e4-next-watch-consume.md) | A 合入提交 | bbdb8317 · 2026-08-19 · #229 | 808 |
| [`feat-promoted-to-code.md`](./feat-promoted-to-code.md) | B 文首自述已合 | 已合入 main**（PR #496，rebase 版 `feat/promoted-to-code-rebased` che | 2794 |
| [`feat-reading-rules-baseline-r3.md`](./feat-reading-rules-baseline-r3.md) | A 合入提交 | 8c5e79c1 · 2026-08-26 · #414 | 1961 |
| [`feat-registry-knowhow-recipes.md`](./feat-registry-knowhow-recipes.md) | A 合入提交 | 2c5520b3 · 2026-09-04 · #586 | 12158 |
| [`feat-repair-backfill-turn.md`](./feat-repair-backfill-turn.md) | B 文首自述已合 | 已合 #237。** 跟进 `fix/w5-backfill-duplicate`：空结果不占 duplicate 键；`_ | 1314 |
| [`feat-research-program-compiler.md`](./feat-research-program-compiler.md) | A 合入提交 | 48601e08 · 2026-08-24 · #355 | 2726 |
| [`feat-river-recorded-at-ledger.md`](./feat-river-recorded-at-ledger.md) | A 合入提交 | e16a1e04 · 2026-09-06 · #600 | 3387 |
| [`feat-stage-model-and-mainline-local.md`](./feat-stage-model-and-mainline-local.md) | A 合入提交 | a008698b · 2026-09-07 · #644 | 5114 |
| [`feat-stock-daily-ohlc-and-dual-track.md`](./feat-stock-daily-ohlc-and-dual-track.md) | A 合入提交 | 32a59ea4 · 2026-09-07 · #634 | 4550 |
| [`feat-sub-research-tool.md`](./feat-sub-research-tool.md) | A 合入提交 | c4982c0d · 2026-09-07 · #611 | 3086 |
| [`feat-substitute-observation-probe.md`](./feat-substitute-observation-probe.md) | A 合入提交 | cd6f9e0d · 2026-08-25 · #371 | 3665 |
| [`feat-substitute-probe-prefetch-p1b.md`](./feat-substitute-probe-prefetch-p1b.md) | A 合入提交 | eb034c7f · 2026-08-25 · #372 | 2154 |
| [`feat-substitute-probe-weekly-p1a.md`](./feat-substitute-probe-weekly-p1a.md) | A 合入提交 | 20858faf · 2026-08-25 · #373 | 1163 |
| [`feat-tool-usage-differential.md`](./feat-tool-usage-differential.md) | A 合入提交 | 85aeeeb1 · 2026-08-28 · #471 | 8702 |
| [`feat-watchlist-digest-p1.md`](./feat-watchlist-digest-p1.md) | A 合入提交 | c7d06930 · 2026-08-27 · #445 | 4352 |
| [`feat-watchlist-digest-pack.md`](./feat-watchlist-digest-pack.md) | A 合入提交 | 547653c4 · 2026-08-27 · #439 | 6210 |
| [`fix-claim-tiering-and-revision.md`](./fix-claim-tiering-and-revision.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 2587 |
| [`fix-degrade-count-single-source.md`](./fix-degrade-count-single-source.md) | B 文首自述已合 | 已合 #241。** `gate_receipt` 计数委托 `judge_degrade`；`extract_from_r | 663 |
| [`fix-deploy-ledger-port-check.md`](./fix-deploy-ledger-port-check.md) | A 合入提交 | f471d42d · 2026-08-20 · #248 | 1361 |
| [`fix-disclosure-residual-grounded-fallback.md`](./fix-disclosure-residual-grounded-fallback.md) | A 合入提交 | a6a269e5 · 2026-08-25 · #397 | 2874 |
| [`fix-duckdb-backfill-qa-gate.md`](./fix-duckdb-backfill-qa-gate.md) | A 合入提交 | 7f80528f · 2026-09-07 · #629 | 5379 |
| [`fix-episode-answer-hygiene-p1.md`](./fix-episode-answer-hygiene-p1.md) | A 合入提交 | 4a1abf79 · 2026-08-21 · #285 | 1869 |
| [`fix-episode-slot-fill-numbers.md`](./fix-episode-slot-fill-numbers.md) | A 合入提交 | 6320b3bc · 2026-08-21 · #289 | 4739 |
| [`fix-g05-market-stage-normalize.md`](./fix-g05-market-stage-normalize.md) | A 合入提交 | 8e452e72 · 2026-09-08 · #661 | 1321 |
| [`fix-gate-partial-release.md`](./fix-gate-partial-release.md) | B 文首自述已合 | 已合已部署（2026-08-19 14:41）+ 轨道 A live 已过（15:28）**。用户确认后经 PR #224  | 3300 |
| [`fix-issue-contract-codes.md`](./fix-issue-contract-codes.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 2225 |
| [`fix-judge-cli-synthesize-transport.md`](./fix-judge-cli-synthesize-transport.md) | A 合入提交 | 6876a6e7 · 2026-08-26 · #402 | 3182 |
| [`fix-judge-first-attempt-full-window.md`](./fix-judge-first-attempt-full-window.md) | A 合入提交 | cce84cf2 · 2026-08-20 · #276 | 1195 |
| [`fix-judge-grant-starvation.md`](./fix-judge-grant-starvation.md) | A 合入提交 | fb98327a · 2026-08-20 · #269 | 590 |
| [`fix-kb-path-fail-closed.md`](./fix-kb-path-fail-closed.md) | A 合入提交 | 1b81728d · 2026-08-25 · #379 | 920 |
| [`fix-operator-prefetch-os.md`](./fix-operator-prefetch-os.md) | A 合入提交 | 3ac070a2 · 2026-08-23 · #345 | 4515 |
| [`fix-perspective-narrative-contract.md`](./fix-perspective-narrative-contract.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 1315 |
| [`fix-perspective-profile-ratchet.md`](./fix-perspective-profile-ratchet.md) | A 合入提交 | ea6f915b · 2026-09-03 · #562 | 1472 |
| [`fix-prefetch-evidence-id.md`](./fix-prefetch-evidence-id.md) | A 合入提交 | a68baee5 · 2026-08-21 · #288 | 2499 |
| [`fix-publication-view-deepen.md`](./fix-publication-view-deepen.md) | A 合入提交 | e8ed9e11 · 2026-08-24 · #354 | 2685 |
| [`fix-rag-worker-page-freshness.md`](./fix-rag-worker-page-freshness.md) | A 合入提交 | 2d8eaea5 · 2026-09-04 · #571 | 1866 |
| [`fix-repair-carry-just-written-finish.md`](./fix-repair-carry-just-written-finish.md) | A 合入提交 | 6da1fe34 · 2026-08-20 · #263 | 3236 |
| [`fix-retire-feishu-market-daily.md`](./fix-retire-feishu-market-daily.md) | C 本地分支 git cherry +0 | 全部补丁已在 gitea/main（squash/rebase 合入） | 1399 |
| [`fix-stock-daily-misdated-snapshot.md`](./fix-stock-daily-misdated-snapshot.md) | A 合入提交 | 2c5e81ba · 2026-09-08 · #651 | 4724 |
| [`fix-substitute-slot-contract-registration.md`](./fix-substitute-slot-contract-registration.md) | A 合入提交 | 83ef1bcc · 2026-08-25 · #374 | 1968 |
| [`fix-tool-call-id-correlation.md`](./fix-tool-call-id-correlation.md) | A 合入提交 | fd2ac284 · 2026-08-28 · #480 | 2225 |
| [`fix-workbench-stream-ux.md`](./fix-workbench-stream-ux.md) | A 合入提交 | 904aba62 · 2026-08-24 · #348 | 11042 |
| [`perf-rag-worker-slimming.md`](./perf-rag-worker-slimming.md) | C 分支本地与远端皆无 | #587 已合、生产已重启（项目笔记 09-05） | 14861 |
| [`refactor-tier-promotion-budget-to-runtime.md`](./refactor-tier-promotion-budget-to-runtime.md) | A 合入提交 | 6d4a9df1 · 2026-09-03 · #536 | 3012 |
| [`test-conformance-seam-census.md`](./test-conformance-seam-census.md) | A 合入提交 | 85e4b1fd · 2026-08-29 · #505 | 2960 |
| [`test-datablock-conformance.md`](./test-datablock-conformance.md) | A 合入提交 | 0fe7d20f · 2026-08-29 · #510 | 2646 |
| [`test-llm-transport-conformance.md`](./test-llm-transport-conformance.md) | A 合入提交 | 5be00c4f · 2026-08-29 · #513 | 1684 |
| [`test-market-snapshot-conformance.md`](./test-market-snapshot-conformance.md) | A 合入提交 | b90a7f6c · 2026-08-29 · #512 | 1666 |
| [`test-runtime-conformance-suite.md`](./test-runtime-conformance-suite.md) | A 合入提交 | e7a9a0bd · 2026-08-29 · #504 | 2859 |

## 2026-09-09 追加（7 份：6 份 09-08 晚合入的 + 收尾单 #686 自己的）

09-08 收口时这 6 份的分支还在 gitea 上、PR 未合；当晚 20:59–21:12 依序合入后没人收，09-09 两日质检抓到。证据全是 A 类（合并提交）；本地分支与 worktree 已随之清掉（六棵树都干净、`git cherry gitea/main` 全 0）。

| 文件 | 证据类 | 证据 | 字节 |
|---|---|---|---|
| [`spec-runtime-base-endstate.md`](./spec-runtime-base-endstate.md) | A 合入提交 | 0ff5d7a4 · 2026-09-08 · #620 | 3027 |
| [`feat-runtime-base-p1-messages-cancel.md`](./feat-runtime-base-p1-messages-cancel.md) | A 合入提交 | c458e177 · 2026-09-08 · #624 | 2466 |
| [`feat-runtime-base-p2-durable-store.md`](./feat-runtime-base-p2-durable-store.md) | A 合入提交 | 5985d878 · 2026-09-08 · #638 | 6178 |
| [`feat-runtime-base-p3-inbox.md`](./feat-runtime-base-p3-inbox.md) | A 合入提交 | 9f2718a2 · 2026-09-08 · #677 | 2939 |
| [`fix-board-ledger-freshest-switch.md`](./fix-board-ledger-freshest-switch.md) | A 合入提交 | 06b21e14 · 2026-09-08 · #675 | 2724 |
| [`docs-inflight-archive-merged-branches.md`](./docs-inflight-archive-merged-branches.md) | A 合入提交 | f90af450 · 2026-09-08 · #676 | 2613 |
| [`docs-closeout-0909.md`](./docs-closeout-0909.md) | A 合入提交 | 5eb24515 · 2026-09-09 · #686 | 2713 |

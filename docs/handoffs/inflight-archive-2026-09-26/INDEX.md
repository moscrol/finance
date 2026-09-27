# 归档：已收口分支的在途交接（2026-09-26 收口）

`docs/handoffs/inflight/` 是**在途**交接：SessionStart 只注入当前分支那一份。09-26 接手收尾时目录里有 171 份，其中 151 份对应的分支已合入、已删除或已关闭，本目录按 09-08 先例（`../inflight-archive-2026-09-08/INDEX.md`）把它们**原文逐字** `git mv` 过来，历史可 `git log --follow` 追。另有 9 份已在同批 #838 / #799 / #936 合入时搬入。外部文档里「见 `inflight/<分支>.md`」的引用，自本文起指本目录同名文件。

留在 inflight 的 20 份：`main.md`（生产基线活文档）、分支仍有补丁未进 main 的线（其去留归各自的线决定）。

判据分四类，逐份列在下表：

- **A 合入**：Gitea 上同名分支的 PR 已合入（写 PR 号、日期、合并提交），或 main 上有 `Merge pull request … from <分支> into main`。
- **C 补丁已在 main**：本地或远端同名分支对 `gitea/main` 做 `git cherry` 全部为 `-`；或分支在 09-24 / 09-26 清理时因「分支尖是 main 祖先」被删除（清理记录里有 sha）。
- **E 无从追溯**：本地与远端都没有同名分支、也没有同名 PR（多为改名合入或清理前已删）；按「不会再被注入」归档，写明文件最后改动的提交与日期。`HEAD.md` 是检出态会话覆写的交接（09-06 另两仓的发布管线），会被注入给所有 detached 会话，一并归档。
- **P 同批 PR 带入**：#838 / #799 / #936 合入时随 PR 搬入。

共 160 份。

| 文件 | 类 | 证据 | 字节 |
|---|---|---|---|
| [`HEAD.md`](./HEAD.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 88363e437 2026-09-07 | 2250 |
| [`chore-handoff-budget-gate.md`](./chore-handoff-budget-gate.md) | A | 合入提交 098e5123d · 2026-09-23 | 2467 |
| [`chore-retire-feishu.md`](./chore-retire-feishu.md) | A | 合入提交 21f9eb9c9 · 2026-09-11 | 7646 |
| [`claude-history-completion-0922.md`](./claude-history-completion-0922.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 807a75d88 2026-09-22 | 10963 |
| [`claude-knevo-8792-config-validation-d17b44.md`](./claude-knevo-8792-config-validation-d17b44.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 61b2c2d1e 2026-09-13 | 3072 |
| [`codex-docs-capability-integration-spec.md`](./codex-docs-capability-integration-spec.md) | C | 分支 codex/docs-capability-integration-spec@a06deea7f 删除前已是 main 祖先（清理记录） | 2118 |
| [`codex-docs-capability-upgrade-plan.md`](./codex-docs-capability-upgrade-plan.md) | A | 合入提交 d8e3b056d · 2026-09-09 | 2050 |
| [`codex-feat-historical-discovery.md`](./codex-feat-historical-discovery.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 c6426064c 2026-09-09 | 3119 |
| [`data-source-hithink-ingest.md`](./data-source-hithink-ingest.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 5fb33d46f 2026-09-09 | 3138 |
| [`data-source-hithink-rewrite-0911.md`](./data-source-hithink-rewrite-0911.md) | C | 分支 data-source/hithink-rewrite-0911@601db6dd4 删除前已是 main 祖先（清理记录） | 3009 |
| [`docs-agent-foundation-closeout.md`](./docs-agent-foundation-closeout.md) | A | 合入 PR #908 · 2026-09-24 · ea42fac42 | 1774 |
| [`docs-bp-v1.3-roadshow-align.md`](./docs-bp-v1.3-roadshow-align.md) | C | 分支补丁已全在 main（git cherry +0） | 2476 |
| [`docs-claim-scope-final-state-0923.md`](./docs-claim-scope-final-state-0923.md) | A | 合入提交 2edbe4c46 · 2026-09-23 | 2293 |
| [`docs-closeout-67-69-evidence-0923.md`](./docs-closeout-67-69-evidence-0923.md) | A | 合入提交 209e9917d · 2026-09-24 | 2750 |
| [`docs-deploy-attribution-archive-0925.md`](./docs-deploy-attribution-archive-0925.md) | A | 合入提交 9c3e61bfa · 2026-09-26 | 1823 |
| [`docs-finarena-decision-0923.md`](./docs-finarena-decision-0923.md) | C | 分支补丁已全在 main（git cherry +0） | 1887 |
| [`docs-gate-closeout-status-0923-python-blocked.md`](./docs-gate-closeout-status-0923-python-blocked.md) | A | 合入 PR #886 · 2026-09-23 · f47d464eb | 2623 |
| [`docs-hybrid-ledger-dependency.md`](./docs-hybrid-ledger-dependency.md) | C | 分支补丁已全在 main（git cherry +0） | 1674 |
| [`docs-judge-mode-k3-cutover-0921.md`](./docs-judge-mode-k3-cutover-0921.md) | A | 合入提交 f66954200 · 2026-09-23 | 2555 |
| [`docs-k3-acceptance-0922.md`](./docs-k3-acceptance-0922.md) | A | 合入提交 a2f845fff · 2026-09-23 | 2526 |
| [`docs-knevo-20260911-intake.md`](./docs-knevo-20260911-intake.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 f5f141e60 2026-09-16 | 2681 |
| [`docs-knevo-20260913-intake.md`](./docs-knevo-20260913-intake.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 f5f141e60 2026-09-16 | 2608 |
| [`docs-knevo-distill-closeout-0916.md`](./docs-knevo-distill-closeout-0916.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 cbbc2a533 2026-09-16 | 3703 |
| [`docs-knevo-e009-arch-delta.md`](./docs-knevo-e009-arch-delta.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 f5f141e60 2026-09-16 | 2590 |
| [`docs-nightly-deployment-receipt-0921.md`](./docs-nightly-deployment-receipt-0921.md) | A | 合入提交 917e15a87 · 2026-09-23 | 1635 |
| [`docs-open-work-consolidation-0920.md`](./docs-open-work-consolidation-0920.md) | C | 分支补丁已全在 main（git cherry +0） | 2898 |
| [`docs-orphan-followup-0923-close.md`](./docs-orphan-followup-0923-close.md) | A | 合入提交 5bf47a5ae · 2026-09-24 | 2260 |
| [`docs-orphan-workorders-0923.md`](./docs-orphan-workorders-0923.md) | A | 合入提交 626d8a508 · 2026-09-23 | 2778 |
| [`docs-pr803-merge-closeout-0920.md`](./docs-pr803-merge-closeout-0920.md) | A | 合入提交 0e9c452a7 · 2026-09-23 | 2603 |
| [`docs-qc-8792-completed-0913.md`](./docs-qc-8792-completed-0913.md) | C | 分支补丁已全在 main（git cherry +0） | 2305 |
| [`docs-qc-re06-i11-50074c76.md`](./docs-qc-re06-i11-50074c76.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 455899755 2026-09-16 | 2410 |
| [`docs-research-foundation-optimization.md`](./docs-research-foundation-optimization.md) | A | 合入提交 907b4f8a7 · 2026-09-11 | 2685 |
| [`docs-river-next-specs.md`](./docs-river-next-specs.md) | C | 分支补丁已全在 main（git cherry +0） | 2161 |
| [`docs-runtime-postmerge-qc-0923.md`](./docs-runtime-postmerge-qc-0923.md) | C | 分支补丁已全在 main（git cherry +0） | 2137 |
| [`docs-stale-closeout-gates-0920.md`](./docs-stale-closeout-gates-0920.md) | C | 分支补丁已全在 main（git cherry +0） | 2138 |
| [`docs-teaching-card-judgment-draft.md`](./docs-teaching-card-judgment-draft.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 40b019351 2026-09-16 | 3196 |
| [`docs-workorder-45-episode-store-home.md`](./docs-workorder-45-episode-store-home.md) | A | 合入提交 c7bbcb93e · 2026-09-09 | 2187 |
| [`docs-workorders-index-hole.md`](./docs-workorders-index-hole.md) | C | 分支 docs/workorders-index-hole@c5bf588a9 删除前已是 main 祖先（清理记录） | 3247 |
| [`docs-worktree-board-acceptance-0924.md`](./docs-worktree-board-acceptance-0924.md) | C | 分支补丁已全在 main（git cherry +0） | 2432 |
| [`feat-adaptive-research-06.md`](./feat-adaptive-research-06.md) | C | 分支 feat/adaptive-research-06@6273a89a4 删除前已是 main 祖先（清理记录） | 3054 |
| [`feat-adaptive-research-loop.md`](./feat-adaptive-research-loop.md) | A | 合入 PR #868 · 2026-09-25 · 1751e21e0 | 1788 |
| [`feat-agent-foundation.md`](./feat-agent-foundation.md) | A | 合入 PR #907 · 2026-09-24 · 03af215e0 | 2198 |
| [`feat-calc-artifacts-04.md`](./feat-calc-artifacts-04.md) | C | 分支 feat/calc-artifacts-04@246181194 删除前已是 main 祖先（清理记录） | 3698 |
| [`feat-cap02-retrieval-deep-read.md`](./feat-cap02-retrieval-deep-read.md) | C | 分支 feat/cap02-retrieval-deep-read@63b7859a2 删除前已是 main 祖先（清理记录） | 4020 |
| [`feat-capability-i2.md`](./feat-capability-i2.md) | C | 分支 feat/capability-i2@00673f6d8 删除前已是 main 祖先（清理记录） | 2909 |
| [`feat-checkpoint-rule-id-bias.md`](./feat-checkpoint-rule-id-bias.md) | A | 合入 PR #592 · 2026-09-16 · c1f8416a4 | 3901 |
| [`feat-contract-honor-p0c.md`](./feat-contract-honor-p0c.md) | C | 分支补丁已全在 main（git cherry +0） | 1178 |
| [`feat-demand-driven-data-requests.md`](./feat-demand-driven-data-requests.md) | C | 分支补丁已全在 main（git cherry +0） | 4867 |
| [`feat-e2-p5-cross-turn-inheritance.md`](./feat-e2-p5-cross-turn-inheritance.md) | C | 分支 feat/e2-p5-cross-turn-inheritance@8355cf8e9 删除前已是 main 祖先（清理记录） | 3120 |
| [`feat-event-pricing-slice1.md`](./feat-event-pricing-slice1.md) | C | 分支补丁已全在 main（git cherry +0） | 2598 |
| [`feat-extraction-first-p0.md`](./feat-extraction-first-p0.md) | C | 分支补丁已全在 main（git cherry +0） | 3418 |
| [`feat-gitea-pr-guard-close-record.md`](./feat-gitea-pr-guard-close-record.md) | A | 合入提交 3c70af64d · 2026-09-21 | 2606 |
| [`feat-historical-replay-engine.md`](./feat-historical-replay-engine.md) | A | 合入提交 c208cbaf3 · 2026-09-12 | 22223 |
| [`feat-hithink-research-data.md`](./feat-hithink-research-data.md) | C | 分支补丁已全在 main（git cherry +0） | 4302 |
| [`feat-judge-token-usage.md`](./feat-judge-token-usage.md) | C | 分支 feat/judge-token-usage@916cb4b53 删除前已是 main 祖先（清理记录） | 26333 |
| [`feat-judgment-maintenance-01.md`](./feat-judgment-maintenance-01.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 85c90b243 2026-09-14 | 3038 |
| [`feat-knevo-delta-readside.md`](./feat-knevo-delta-readside.md) | A | 合入提交 03c0a678f · 2026-09-11 | 8727 |
| [`feat-knevo-r4r5-absorption.md`](./feat-knevo-r4r5-absorption.md) | A | 合入提交 5907c9f6d · 2026-09-11 | 2992 |
| [`feat-l2-share-source-port-0916.md`](./feat-l2-share-source-port-0916.md) | A | 合入 PR #773 · 2026-09-16 · d433b9078 | 2746 |
| [`feat-local-technical-screen.md`](./feat-local-technical-screen.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 f378253ff 2026-09-11 | 3133 |
| [`feat-method-closed-loop.md`](./feat-method-closed-loop.md) | A | 合入提交 694584dff · 2026-09-12 | 6659 |
| [`feat-method-validation-loop.md`](./feat-method-validation-loop.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 4b7c49172 2026-09-08 | 2899 |
| [`feat-methodology-backtest-p1-lifecycle-stage.md`](./feat-methodology-backtest-p1-lifecycle-stage.md) | C | 分支 feat/methodology-backtest-p1-lifecycle-stage@c9ed412f9 删除前已是 main 祖先（清理记录） | 4576 |
| [`feat-methodology-correlated-samples.md`](./feat-methodology-correlated-samples.md) | A | 合入提交 6382c13b7 · 2026-09-12 | 3909 |
| [`feat-methodology-promotion-certification.md`](./feat-methodology-promotion-certification.md) | A | 合入提交 3af93a5ea · 2026-09-11 | 3168 |
| [`feat-no-llm-judge-mode.md`](./feat-no-llm-judge-mode.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 fa28de52e 2026-09-17 | 4227 |
| [`feat-opinion-lifecycle-stage.md`](./feat-opinion-lifecycle-stage.md) | A | 合入提交 4fa297cd1 · 2026-09-11 | 2773 |
| [`feat-opt01-content-versioning.md`](./feat-opt01-content-versioning.md) | A | 合入提交 725797fad · 2026-09-12 | 3089 |
| [`feat-ranking-scenarios-10.md`](./feat-ranking-scenarios-10.md) | C | 分支补丁已全在 main（git cherry +0） | 4651 |
| [`feat-research-diagnostics-04.md`](./feat-research-diagnostics-04.md) | C | 分支补丁已全在 main（git cherry +0） | 3043 |
| [`feat-research-evolution-05-product-value.md`](./feat-research-evolution-05-product-value.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 92608c848 2026-09-14 | 3068 |
| [`feat-research-evolution-06-workbench.md`](./feat-research-evolution-06-workbench.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 69128e52d 2026-09-16 | 3413 |
| [`feat-research-priority.md`](./feat-research-priority.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 e27b3352e 2026-09-13 | 3015 |
| [`feat-research-validation-03.md`](./feat-research-validation-03.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 f2a12fa3b 2026-09-13 | 2940 |
| [`feat-river-context-projection.md`](./feat-river-context-projection.md) | A | 合入提交 03ea30424 · 2026-09-11 | 2646 |
| [`feat-river-pit-strict-gate.md`](./feat-river-pit-strict-gate.md) | A | 合入提交 87d43381a · 2026-09-11 | 3058 |
| [`feat-river-window-contract.md`](./feat-river-window-contract.md) | A | 合入提交 35d8d473c · 2026-09-11 | 2998 |
| [`feat-run-credits.md`](./feat-run-credits.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 7d1aa9126 2026-09-03 | 3725 |
| [`feat-runtime-base-p4-races-oracle.md`](./feat-runtime-base-p4-races-oracle.md) | A | 合入提交 0efbeec0d · 2026-09-11 | 2982 |
| [`feat-sandbox-derived-calculation.md`](./feat-sandbox-derived-calculation.md) | C | 分支补丁已全在 main（git cherry +0） | 3064 |
| [`feat-scenario-tree-v0.md`](./feat-scenario-tree-v0.md) | A | 合入提交 73dd3d1e7 · 2026-09-12 | 3485 |
| [`feat-teaching-framework-slice3-structure.md`](./feat-teaching-framework-slice3-structure.md) | C | 分支 feat/teaching-framework-slice3-structure@3a35d0ec6 删除前已是 main 祖先（清理记录） | 2617 |
| [`feat-theme-fund-panel-port-0916.md`](./feat-theme-fund-panel-port-0916.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 7ef16269c 2026-09-16 | 2982 |
| [`feat-verify-timepoint-forward-slot.md`](./feat-verify-timepoint-forward-slot.md) | A | 合入 PR #377 · 2026-08-25 · 6a01f96f0 | 2299 |
| [`fix-8792-integrate-routefix-tradingday.md`](./fix-8792-integrate-routefix-tradingday.md) | C | 分支补丁已全在 main（git cherry +0） | 1599 |
| [`fix-8792-qc-closeout-0913.md`](./fix-8792-qc-closeout-0913.md) | C | 分支补丁已全在 main（git cherry +0） | 7239 |
| [`fix-answer-claim-scope-0922.md`](./fix-answer-claim-scope-0922.md) | A | 合入提交 a696c5e1d · 2026-09-23 | 2489 |
| [`fix-backfill-0908-sina-source.md`](./fix-backfill-0908-sina-source.md) | A | 合入提交 7d97a4b1c · 2026-09-11 | 8337 |
| [`fix-checkpoint-rule-id-bias-sync.md`](./fix-checkpoint-rule-id-bias-sync.md) | C | 分支 fix/checkpoint-rule-id-bias-sync@9550a9313 删除前已是 main 祖先（清理记录） | 1095 |
| [`fix-claim-scope-hardening-0922.md`](./fix-claim-scope-hardening-0922.md) | A | 合入提交 6fc6bfa94 · 2026-09-23 | 6142 |
| [`fix-codex-isolation-interpreter.md`](./fix-codex-isolation-interpreter.md) | C | 分支补丁已全在 main（git cherry +0） | 1836 |
| [`fix-crowding-gate-ranking-questions.md`](./fix-crowding-gate-ranking-questions.md) | A | 合入提交 16c46ccd1 · 2026-09-11 | 6319 |
| [`fix-cutoff-single-source-0923.md`](./fix-cutoff-single-source-0923.md) | A | 合入 PR #870 · 2026-09-23 · 99c2ff28b | 2977 |
| [`fix-d6-as-of-truncation.md`](./fix-d6-as-of-truncation.md) | A | 合入提交 8a9db51a2 · 2026-09-11 | 6213 |
| [`fix-data-holes-0817-20250919.md`](./fix-data-holes-0817-20250919.md) | A | 合入提交 d1f0819e9 · 2026-09-11 | 2614 |
| [`fix-disk-burn-cow-snapshots-0923.md`](./fix-disk-burn-cow-snapshots-0923.md) | A | 合入 PR #876 · 2026-09-23 · bbd53487f | 2205 |
| [`fix-e2-boundary-closeout.md`](./fix-e2-boundary-closeout.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 851e78861 2026-09-15 | 3595 |
| [`fix-e2-delivery-closeout.md`](./fix-e2-delivery-closeout.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 a1f8c1dad 2026-09-16 | 2877 |
| [`fix-eastmoney-deploy-binding-0923.md`](./fix-eastmoney-deploy-binding-0923.md) | A | 合入 PR #887 · 2026-09-23 · 0525e780e | 2612 |
| [`fix-eastmoney-snapshot-direct-ip-0922.md`](./fix-eastmoney-snapshot-direct-ip-0922.md) | C | 分支补丁已全在 main（git cherry +0） | 14427 |
| [`fix-extraction-first-closeout.md`](./fix-extraction-first-closeout.md) | C | 分支补丁已全在 main（git cherry +0） | 3387 |
| [`fix-financial-ttl-baseline-fwd-0923.md`](./fix-financial-ttl-baseline-fwd-0923.md) | A | 合入提交 77d49efd8 · 2026-09-24 | 2755 |
| [`fix-gate-collection-0922.md`](./fix-gate-collection-0922.md) | A | 合入提交 72be60059 · 2026-09-23 | 2651 |
| [`fix-generation-root-boundary-guards.md`](./fix-generation-root-boundary-guards.md) | C | 分支补丁已全在 main（git cherry +0） | 2591 |
| [`fix-history-completion-fwd-0923.md`](./fix-history-completion-fwd-0923.md) | A | 合入提交 d86311d2e · 2026-09-24 | 2330 |
| [`fix-hithink-research-85.md`](./fix-hithink-research-85.md) | A | 合入提交 1053f59a7 · 2026-09-24 | 2669 |
| [`fix-hithink-review-wiring.md`](./fix-hithink-review-wiring.md) | C | 分支补丁已全在 main（git cherry +0） | 2873 |
| [`fix-instruction-gate-clearance.md`](./fix-instruction-gate-clearance.md) | A | 合入提交 bed896344 · 2026-09-13 | 1425 |
| [`fix-judge-honesty-p0b.md`](./fix-judge-honesty-p0b.md) | C | 分支补丁已全在 main（git cherry +0） | 1446 |
| [`fix-judge-recovery-01.md`](./fix-judge-recovery-01.md) | A | 合入提交 bdfc924da · 2026-09-11 | 7923 |
| [`fix-l2-pct-chg-backfill-0913.md`](./fix-l2-pct-chg-backfill-0913.md) | C | 分支补丁已全在 main（git cherry +0） | 2492 |
| [`fix-market-recovery-0921.md`](./fix-market-recovery-0921.md) | C | 分支补丁已全在 main（git cherry +0） | 2281 |
| [`fix-market-recovery-contracts-0922.md`](./fix-market-recovery-contracts-0922.md) | A | 合入提交 d3ff8219c · 2026-09-23 | 2964 |
| [`fix-material-claim-occurrence-0925.md`](./fix-material-claim-occurrence-0925.md) | A | 合入提交 c9f8062ed · 2026-09-26 | 2099 |
| [`fix-method-migration-acceptance.md`](./fix-method-migration-acceptance.md) | A | 合入提交 fc2f9e9e5 · 2026-09-12 | 2735 |
| [`fix-mootdx-history-0922.md`](./fix-mootdx-history-0922.md) | A | 合入提交 a026544c5 · 2026-09-23 | 3017 |
| [`fix-mutation-timeout-evidence-0922.md`](./fix-mutation-timeout-evidence-0922.md) | C | 分支补丁已全在 main（git cherry +0） | 4167 |
| [`fix-mutation-timeout-evidence-fwd-0923.md`](./fix-mutation-timeout-evidence-fwd-0923.md) | A | 合入提交 844793749 · 2026-09-24 | 2483 |
| [`fix-nightly-deploy-closeout-0921.md`](./fix-nightly-deploy-closeout-0921.md) | A | 合入 PR #827 · 2026-09-21 · c097d712f | 2233 |
| [`fix-nightly-generation-deploy-0917.md`](./fix-nightly-generation-deploy-0917.md) | C | 分支补丁已全在 main（git cherry +0） | 2823 |
| [`fix-nightly-review-0917.md`](./fix-nightly-review-0917.md) | C | 分支补丁已全在 main（git cherry +0） | 2964 |
| [`fix-numeric-preflight-model-number-0925.md`](./fix-numeric-preflight-model-number-0925.md) | A | 合入提交 e159c5644 · 2026-09-25 | 2816 |
| [`fix-publication-gate-lamp.md`](./fix-publication-gate-lamp.md) | C | 分支补丁已全在 main（git cherry +0） | 2133 |
| [`fix-rag-probe-diagnostics-0921.md`](./fix-rag-probe-diagnostics-0921.md) | A | 合入提交 99c84cecc · 2026-09-24 | 2986 |
| [`fix-rag-retirement-closeout-0920.md`](./fix-rag-retirement-closeout-0920.md) | C | 分支补丁已全在 main（git cherry +0） | 3070 |
| [`fix-re06-i11-consent-measurement.md`](./fix-re06-i11-consent-measurement.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 40b019351 2026-09-16 | 3614 |
| [`fix-re06-visibility-timing.md`](./fix-re06-visibility-timing.md) | C | 分支 fix/re06-visibility-timing@47bf19aa9 删除前已是 main 祖先（清理记录） | 2306 |
| [`fix-release-gate-closeout.md`](./fix-release-gate-closeout.md) | A | 合入 PR #747 · 2026-09-16 · 918f8d5aa | 2571 |
| [`fix-replay-rebuild-keep-observations-0925.md`](./fix-replay-rebuild-keep-observations-0925.md) | A | 合入提交 546d3a3f1 · 2026-09-26 | 2382 |
| [`fix-report-reads-single-snapshot.md`](./fix-report-reads-single-snapshot.md) | A | 合入提交 aaec54897 · 2026-09-23 | 2651 |
| [`fix-research-empty-delivery-0922.md`](./fix-research-empty-delivery-0922.md) | A | 合入提交 8d3d722c9 · 2026-09-23 | 3051 |
| [`fix-research-intent-boundaries.md`](./fix-research-intent-boundaries.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 fa28de52e 2026-09-17 | 4386 |
| [`fix-research-tail-financial-union-0922.md`](./fix-research-tail-financial-union-0922.md) | A | 合入 PR #863 · 2026-09-23 · 8e7989372 | 5590 |
| [`fix-restore-ima-gap-report.md`](./fix-restore-ima-gap-report.md) | A | 合入提交 5a5334712 · 2026-09-21 | 3072 |
| [`fix-run-queued-regression-0923.md`](./fix-run-queued-regression-0923.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 264bc9d0d 2026-09-23 | 2207 |
| [`fix-runtime-closeout-0921.md`](./fix-runtime-closeout-0921.md) | C | 分支补丁已全在 main（git cherry +0） | 2865 |
| [`fix-runtime-effect-reconciliation-0922.md`](./fix-runtime-effect-reconciliation-0922.md) | A | 合入 PR #865 · 2026-09-23 · 3b7e47357 | 3065 |
| [`fix-runtime-entry-identity-0922.md`](./fix-runtime-entry-identity-0922.md) | C | 分支补丁已全在 main（git cherry +0） | 2518 |
| [`fix-sellside-consumption-0922.md`](./fix-sellside-consumption-0922.md) | C | 分支补丁已全在 main（git cherry +0） | 2944 |
| [`fix-session-facts-working-repo-behind.md`](./fix-session-facts-working-repo-behind.md) | A | 合入提交 631786ab3 · 2026-09-13 | 3062 |
| [`fix-skill-timeout-test-lifecycle-0923.md`](./fix-skill-timeout-test-lifecycle-0923.md) | A | 合入提交 b59d6eed0 · 2026-09-23 | 2588 |
| [`fix-sync-code-root.md`](./fix-sync-code-root.md) | A | 合入提交 c703e0686 · 2026-09-12 | 2955 |
| [`fix-watchdog-test-synchronization-0922.md`](./fix-watchdog-test-synchronization-0922.md) | A | 合入 PR #848 · 2026-09-22 · a2c8d1f90 | 2985 |
| [`fix-workbench-release-0924.md`](./fix-workbench-release-0924.md) | C | 分支补丁已全在 main（git cherry +0） | 2790 |
| [`fix-workorders-86-87-0923.md`](./fix-workorders-86-87-0923.md) | E | 本地与远端都无同名分支、无同名 PR；文件最后改动 ae6594d09 2026-09-23 | 2940 |
| [`fix-worktree-board-hardening-0923.md`](./fix-worktree-board-hardening-0923.md) | A | 合入提交 78e75bf89 · 2026-09-24 | 2541 |
| [`fix-worktree-safety-guards-0924.md`](./fix-worktree-safety-guards-0924.md) | A | 合入提交 8e6c98122 · 2026-09-25 | 2936 |
| [`polymarket-macro-odds-impl.md`](./polymarket-macro-odds-impl.md) | C | 分支 polymarket-macro-odds-impl@347b98b01 删除前已是 main 祖先（清理记录） | 3027 |
| [`restore-feishu-skills.md`](./restore-feishu-skills.md) | A | 合入提交 58804d530 · 2026-09-11 | 4915 |
| [`spec-capability-amplification-output-gate.md`](./spec-capability-amplification-output-gate.md) | A | 合入 PR #537 · 2026-09-03 · 88ac7917b | 6697 |
| [`test-runtime-probe-repair-0923.md`](./test-runtime-probe-repair-0923.md) | C | 分支 test/runtime-probe-repair-0923@b77ff2241 删除前已是 main 祖先（清理记录） | 2520 |
| [`docs-pi-closeout-execution-0924.md`](./docs-pi-closeout-execution-0924.md) | P | #936 本分支；随 #936 合入 `d7ddcb282` 归档 | 2362 |
| [`docs-research-tail-closeout-0921.md`](./docs-research-tail-closeout-0921.md) | P | #838 本分支；随 #838 合入 `fd877a5e0` 归档 | 2085 |
| [`fix-financial-forward-0921.md`](./fix-financial-forward-0921.md) | P | #77 判定：分支随 #863（`8e7989372`）关闭；随 #838 归档 | 2462 |
| [`fix-gate-receipt-selection-0921.md`](./fix-gate-receipt-selection-0921.md) | P | #77 判定：分支随 #863 关闭；随 #838 归档 | 2033 |
| [`fix-history-forward-0921.md`](./fix-history-forward-0921.md) | P | #77 判定：分支随 #863 关闭；随 #838 归档 | 1658 |
| [`fix-history-forward-boundary-0921.md`](./fix-history-forward-boundary-0921.md) | P | #77 判定：分支随 #863 关闭；随 #838 归档 | 2282 |
| [`fix-research-closeout-0920.md`](./fix-research-closeout-0920.md) | P | #799 本分支；随 #799 合入 `a8fb4ba95` 归档 | 2721 |
| [`fix-research-tail-integration-0921.md`](./fix-research-tail-integration-0921.md) | P | #77 判定：分支随 #863 关闭；随 #838 归档 | 1838 |
| [`fix-runtime-forward-0921.md`](./fix-runtime-forward-0921.md) | P | #77 判定：分支随 #863 关闭；随 #838 归档 | 2364 |

## 2026-09-27 追加（接手收尾第二批）

09-26～09-27 接手收尾期间又合入 13 张 PR、关闭 2 张，下列分支的在途交接随之失效；判据同上（A 合入 / C 补丁已在 main）。

| 文件 | 类 | 证据 | 字节 |
|---|---|---|---|
| [`baseline-research-data-acceptance-0922.md`](./baseline-research-data-acceptance-0922.md) | C | 分支补丁已全在 main（git cherry +0） | 2956 |
| [`docs-react-trace-chain-0923.md`](./docs-react-trace-chain-0923.md) | C | 分支补丁已全在 main（git cherry +0） | 2838 |
| [`feat-architecture-audit-0924.md`](./feat-architecture-audit-0924.md) | A | 合入提交 339676bfe · 2026-09-27 | 1457 |
| [`feat-history-evidence-integration-0921.md`](./feat-history-evidence-integration-0921.md) | A | 合入提交 6da10fdf6 · 2026-09-27 | 2144 |
| [`feat-pi-research-loop.md`](./feat-pi-research-loop.md) | A | 合入提交 e43c4b81e · 2026-09-26 | 1804 |
| [`feat-research-data-readiness.md`](./feat-research-data-readiness.md) | C | 分支补丁已全在 main（git cherry +0） | 2878 |
| [`fix-backfill-main-ready-0921.md`](./fix-backfill-main-ready-0921.md) | A | 合入 PR #813 · 2026-09-27 · 34dd58468 | 2920 |
| [`fix-delivery-guard-forward-0924.md`](./fix-delivery-guard-forward-0924.md) | A | 合入提交 2a7394e94 · 2026-09-26 | 2296 |
| [`fix-delivery-guard-structural-binding.md`](./fix-delivery-guard-structural-binding.md) | C | 分支补丁已全在 main（git cherry +0） | 3192 |
| [`fix-e2-re06-resume-0922.md`](./fix-e2-re06-resume-0922.md) | C | 分支补丁已全在 main（git cherry +0） | 3071 |
| [`fix-local-backfill-0923-0924.md`](./fix-local-backfill-0923-0924.md) | A | 合入提交 4b1b0db05 · 2026-09-26 | 2275 |
| [`fix-pr868-delivery-validation-0924.md`](./fix-pr868-delivery-validation-0924.md) | A | 合入提交 5b6136bfc · 2026-09-26 | 2102 |
| [`fix-pr910-main-0925.md`](./fix-pr910-main-0925.md) | C | 分支补丁已全在 main（git cherry +0） | 205 |
| [`fix-re06-closeout-refresh-0925.md`](./fix-re06-closeout-refresh-0925.md) | A | 合入 PR #942 · 2026-09-27 · pending-t | 1994 |
| [`fix-re06-timer-scope-0923.md`](./fix-re06-timer-scope-0923.md) | C | 分支补丁已全在 main（git cherry +0） | 2170 |
| [`fix-react-trace-closeout-0921.md`](./fix-react-trace-closeout-0921.md) | C | 分支补丁已全在 main（git cherry +0） | 5503 |
| [`fix-react-trace-closeout-forward-0924.md`](./fix-react-trace-closeout-forward-0924.md) | C | 分支补丁已全在 main（git cherry +0） | 1859 |
| [`fix-react-trace-qc-0921.md`](./fix-react-trace-qc-0921.md) | A | 合入提交 75cea8352 · 2026-09-27 | 2074 |
| [`q-research-data-readiness.md`](./q-research-data-readiness.md) | C | 分支补丁已全在 main（git cherry +0） | 2387 |
| [`test-pr911-main-0925.md`](./test-pr911-main-0925.md) | C | 分支补丁已全在 main（git cherry +0） | 179 |

## 2026-09-27 追加（接手收尾第三批）

工单 83 生产回填已执行、#890 已合入，下列在途交接随之失效；判据同上。

| 文件 | 类 | 证据 | 字节 |
|---|---|---|---|
| [`feat-claim-scope-runtime-0923.md`](./feat-claim-scope-runtime-0923.md) | A | 合入 PR #890 · 2026-09-27 · 4c04bb185 | 2684 |
| [`fix-backfill-302132-0923.md`](./fix-backfill-302132-0923.md) | A | 合入 PR #813 · 2026-09-27 · 34dd58468；生产回填 run bca04f90362f（37/37） | 2400 |

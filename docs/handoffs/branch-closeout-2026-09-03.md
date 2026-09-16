# 分支/树收口台账 · 2026-09-03

> 规则：只拆树，不删任何 commit 或分支引用。不活跃（≥3 天无提交、无 reflog、无文件改动）且没挂 PR 的树才处置；活跃的和挂 PR 的一律不碰。
> 未提交改动先封存：能提交的进 `salvage/<树名>-0903` 分支（或未合分支自身的 `wip(salvage)` 提交），pre-commit 拦下的改为 `git diff HEAD` patch + 未跟踪文件拷贝，落 `~/kb_work/worktree-salvage-2026-09-03/<仓>/<树名>/`。
> 复活任何一棵：表末列命令；分支引用都还在（`git branch --list 'salvage/*'`）。

## 金融仓 finance-workspace-private（62 棵）

### 开 PR（保留树）（2）

| 树 | 分支 | 落后 | 未合提交 | 封存 | PR / 复活 |
|---|---|---|---|---|---|
| `~/.finance-runtime/finance-workspace-profile-ratchet` | `fix/perspective-profile-ratchet` | 182 | fix(perspective): 画像整表回写按长度棘轮，挡住薄副本盖厚画像 | — | PR #562（合并干净） |
| `~/fwp-wt-ledger-close-0828` | `docs/ledger-r05-07-live-close` | 182 | docs(ledger): R-20260828-05/06/07 切流后收口——三行全 con | — | PR #563（合并有冲突，需 rebase） |

### 拆树（提交标题已在 main，另路落地）（2）

| 树 | 分支 | 落后 | 未合提交 | 封存 | PR / 复活 |
|---|---|---|---|---|---|
| `~/fwp-wt-reading-rules-baseline` | `feat/reading-rules-baseline-r2` | 635 | feat(reading-baseline): 判读方法内置为领域基线（批一 8 条） | — | `git worktree add ~/fwp-wt-reading-rules-baseline feat/reading-rules-baseline-r2` |
| `~/fwp-wt-data-root-wiring` | `fix/data-root-wiring` | 1063 | fix(paths): 摘掉数据根查找序里的 WORKBENCH_REPO_ROOT | 封存提交 `f640bb20b746` @ `fix/data-root-wiring`（1 文件） | `git worktree add ~/fwp-wt-data-root-wiring fix/data-root-wiring` |

### 拆树（过期：落后 >300，分支引用保留）（28）

| 树 | 分支 | 落后 | 未合提交 | 封存 | PR / 复活 |
|---|---|---|---|---|---|
| `~/fwp-wt-docs-workbench-quality-residual-ux` | `docs/workbench-quality-residual-ux` | 576 | docs(spec): 品质残差预算 v1.1，收审查 PASS-WITH-NITS | — | `git worktree add ~/fwp-wt-docs-workbench-quality-residual-ux docs/workbench-quality-residual-ux` |
| `~/finance-workspace-private/tmp/fix-numeric-backfill` | `fix/forward-action-question-routing` | 578 | fix(verifier): 无主语的市场级问题恢复数值 backfill<br>fix(verifier): 放开的那一档收紧到「类型未解析」，题材仍 fail closed<br>docs: 本单收据与台账（R-20260824-01/02，pending）<br>…共 6 条 | — | `git worktree add ~/finance-workspace-private/tmp/fix-numeric-backfill fix/forward-action-question-routing` |
| `~/fwp-wt-code-map-land` | `codex/code-map-request-loop` | 609 | docs: design Code Map request-loop narrative<br>docs: plan Code Map request-loop narrative<br>feat: add Code Map request-loop narrative<br>…共 11 条 | 封存提交 `6c1b888b8df0` @ `codex/code-map-request-loop`（1 文件） | `git worktree add ~/fwp-wt-code-map-land codex/code-map-request-loop` |
| `~/fwp-wt-switchboard-p0-align` | `align/switchboard-p0` | 617 | feat(switchboard): 谓词真本源 + 并列开关板（默认空集合）<br>test(switchboard): 默认盒相对主链的表面棘轮<br>test(switchboard): 质量棘轮补双红/涨停探针<br>…共 14 条 | — | `git worktree add ~/fwp-wt-switchboard-p0-align align/switchboard-p0` |
| `~/fwp-wt-harness-ceiling-followup-spec` | `cursor/harness-ceiling-followup-spec-3f68` | 618 | docs(spec): 落 harness 上限与 8796 解耦后续单<br>docs(spec): v2 核稿改定 D2 结案单与 D1 两形状<br>docs(spec): v3 输入可加、输出闸只减<br>…共 8 条 | 封存提交 `21a9bcc1bcaf` @ `cursor/harness-ceiling-followup-spec-3f68`（3 文件） | `git worktree add ~/fwp-wt-harness-ceiling-followup-spec cursor/harness-ceiling-followup-spec-3f68` |
| `~/fwp-wt-knevo28-p0a-view` | `docs/knevo28-p0a-view-deepen` | 618 | docs(spec): 落 harness 上限与 8796 解耦后续单<br>docs(spec): v2 核稿改定 D2 结案单与 D1 两形状<br>docs(spec): v3 输入可加、输出闸只减<br>…共 6 条 | 封存提交 `73d2af5ca3cc` @ `docs/knevo28-p0a-view-deepen`（3 文件） | `git worktree add ~/fwp-wt-knevo28-p0a-view docs/knevo28-p0a-view-deepen` |
| `~/fwp-wt-market-watch-component-first-spec` | `docs/market-watch-component-first` | 618 | docs(spec): 盘面题改由组件包当第一执行者<br>docs(spec): 盘面组件包 v2，按核稿改落点 | — | `git worktree add ~/fwp-wt-market-watch-component-first-spec docs/market-watch-component-first` |
| `~/fwp-wt-switchboard-align` | `align/switchboard-catchup` | 627 | feat(switchboard): 谓词真本源 + 并列开关板（默认空集合）<br>test(switchboard): 默认盒相对主链的表面棘轮<br>test(switchboard): 质量棘轮补双红/涨停探针<br>…共 13 条 | 封存提交 `a3332a162602` @ `align/switchboard-catchup`（1 文件） | `git worktree add ~/fwp-wt-switchboard-align align/switchboard-catchup` |
| `~/fwp-wt-activation-receipt` | `feat/activation-receipt` | 628 | feat(harness): 激活收据——标题只认注入，不认用户点了谁 | — | `git worktree add ~/fwp-wt-activation-receipt feat/activation-receipt` |
| `~/fwp-wt-capability-switchboard` | `docs/capability-switchboard` | 636 | feat(switchboard): 谓词真本源 + 并列开关板（默认空集合）<br>test(switchboard): 默认盒相对主链的表面棘轮<br>test(switchboard): 质量棘轮补双红/涨停探针<br>…共 9 条 | 封存提交 `a1ddfcfcfbca` @ `docs/capability-switchboard`（1 文件） | `git worktree add ~/fwp-wt-capability-switchboard docs/capability-switchboard` |
| `~/fwp-wt-judge-mixed-subtract` | `fix/judge-mixed-method-subtract` | 637 | fix(judge): mixed 契约不再整篇封闭世界 | — | `git worktree add ~/fwp-wt-judge-mixed-subtract fix/judge-mixed-method-subtract` |
| `~/fwp-wt-qizhong-pronoun-routing` | `fix/qizhong-pronoun-routing` | 637 | fix(routing): 完整题不被指代粗信号一票否决<br>fix(judge): mixed 契约不再整篇封闭世界 | — | `git worktree add ~/fwp-wt-qizhong-pronoun-routing fix/qizhong-pronoun-routing` |
| `~/fwp-wt-v7-inputside-sensors` | `feat/v7-inputside-kb-sensors` | 702 | feat(V7): 输入侧 KB 传感器——题形×调用率三层 + 送达计数 + telemetr<br>docs(V7): 输入侧 KB 传感器验证文档——金标五案例 + TDD/变异证据 | — | `git worktree add ~/fwp-wt-v7-inputside-sensors feat/v7-inputside-kb-sensors` |
| `~/fwp-wt-v3-kbsearch-coarse-pipe` | `feat/v3-kbsearch-coarse-pipe` | 703 | feat(V3): kb_search 送达接 llm_evidence 粗管道<br>docs(V3): 补录 160 截断变异击杀证据<br>docs(V3): 复算命令去掉易碎的路径行字面量 | — | `git worktree add ~/fwp-wt-v3-kbsearch-coarse-pipe feat/v3-kbsearch-coarse-pipe` |
| `~/fwp-wt-v4-kb-index-hygiene` | `fix/v4-kb-index-hygiene` | 706 | fix(V4): 知识索引排除工件页并折叠同 slug 多版本<br>test(V4): 液冷 retrieve 钉改成路径子串，避免变异后自指断言仍绿<br>docs(V4): 回填变异击杀 3 条与液冷重放前后 top-5<br>…共 4 条 | — | `git worktree add ~/fwp-wt-v4-kb-index-hygiene fix/v4-kb-index-hygiene` |
| `~/fwp-wt-w1-ceiling-degrade` | `fix/ceiling-required-block-degrade` | 712 | fix: 判官对必需输出块降级保留，道歉横幅只归全灭闸（R-20260821-07） | — | `git worktree add ~/fwp-wt-w1-ceiling-degrade fix/ceiling-required-block-degrade` |
| `~/fwp-wt-w2-satisfiability` | `fix/w2-mandatory-satisfiability` | 713 | fix: 必需项可满足性两级对账，不可达必填格降为缺口（R-20260821-08）<br>docs: W2 变异实锤——预检反转与兜底拆除两钉均红<br>docs: 补 W2 干净树全量收据 a132f15f（5904P/0F） | — | `git worktree add ~/fwp-wt-w2-satisfiability fix/w2-mandatory-satisfiability` |
| `~/fwp-wt-ceiling-sensors` | `feat/ceiling-sensors` | 714 | feat: 封上限四形状传感器聚合为常驻计量<br>docs: 补 W5 变异复现与全量门禁读数 | — | `git worktree add ~/fwp-wt-ceiling-sensors feat/ceiling-sensors` |
| `~/fwp-wt-w3-numeric-backfill` | `fix/numeric-unsupported-anchor-backfill` | 714 | fix: NUMERIC_UNSUPPORTED 回填按锚定主体反推<br>docs: 立案 R-20260821-09 并写 W3 离线验证<br>docs: 补 W3 全量门禁收据 | — | `git worktree add ~/fwp-wt-w3-numeric-backfill fix/numeric-unsupported-anchor-backfill` |
| `~/fwp-wt-harness-success-path` | `docs/harness-success-path-spec` | 762 | docs: 路由后 harness 成功路径宪章（v1.1，记下子单 C） | 封存提交 `9e56ecef3b92` @ `docs/harness-success-path-spec`（1 文件） | `git worktree add ~/fwp-wt-harness-success-path docs/harness-success-path-spec` |
| `~/fwp-wt-retire-dual-blind` | `chore/retire-dual-blind-nightly` | 819 | chore: 夜跑拆掉双盲答卷回检，并记下 08-19 补洞收口 | — | `git worktree add ~/fwp-wt-retire-dual-blind chore/retire-dual-blind-nightly` |
| `~/fwp-wt-gate-release` | `fix/gate-partial-release` | 917 | fix(episode-verifier): 证据类型白名单改剔除式，类型缺口进语义放行名单<br>fix(episode-factory): 残差 prime_quote/prime_news <br>docs(handoff): fix/gate-partial-release 在途交接 | — | `git worktree add ~/fwp-wt-gate-release fix/gate-partial-release` |
| `~/fwp-wt-frozen-thirty-live` | `eval/frozen-thirty-live-baseline` | 1006 | eval: 冻结 30 题 live 基线（sidecar grounded，回归锚） | — | `git worktree add ~/fwp-wt-frozen-thirty-live eval/frozen-thirty-live-baseline` |
| `~/fwp-wt-dead-assets` | `feat/dead-assets-consumption` | 1063 | feat: 四张零消费表注册进语义层，两 JSON 归档不接<br>docs: live 三问未调 finance_query，记够得着≠想得到用 | — | `git worktree add ~/fwp-wt-dead-assets feat/dead-assets-consumption` |
| `~/fwp-wt-dead-assets-ask` | `docs/dead-assets-ask-wiring` | 1063 | docs(handoff): 派死资产想得到用单——ask D13–D16 意图门控 | — | `git worktree add ~/fwp-wt-dead-assets-ask docs/dead-assets-ask-wiring` |
| `~/.finance-runtime/finance-s7-sync` | `spec/continuous-depth-gap-r1` | 1365 | docs(spec): R3 增 P1-E 输出契约（四态对照/修订版契约/TTL/下期关注衔接<br>docs(spec): 附录A 内嵌 knevo-distill q4/q8 原文（6维审查框架<br>docs(spec): R4 勘误——P0/P1-C/E5 已入 main，P1-E 改为相对  | — | `git worktree add ~/.finance-runtime/finance-s7-sync spec/continuous-depth-gap-r1` |
| `~/fwp-wt-proactive-checks` | `feat/proactive-checks` | 1460 | docs: lessons_learned 补两条晨汇回填批次教训（自产 U+FFFD 后验扫描<br>feat(reading-baseline): 判读方法内置为领域基线（批一 8 条）<br>feat(reading-baseline): 批二 13 条挂数据块 + 批三 4 条挂缺口待 | 封存提交 `b6648f282a6c` @ `feat/proactive-checks`（9 文件） | `git worktree add ~/fwp-wt-proactive-checks feat/proactive-checks` |
| `~/fwp-wt-artifacts` | `chore/artifact-writeback-0814` | 1473 | chore(artifacts): 回写主仓工作树上积压的夜跑与评测产物 | 封存提交 `94b901d3ecf7` @ `chore/artifact-writeback-0814`（1 文件） | `git worktree add ~/fwp-wt-artifacts chore/artifact-writeback-0814` |

### 拆树（补丁已在基线）（29）

| 树 | 分支 | 落后 | 未合提交 | 封存 | PR / 复活 |
|---|---|---|---|---|---|
| `~/fwp-wt-ablate-s1` | `ablate/s1-candidate` | 126 | — | 封存提交 `0f48c717da5f` @ `salvage/fwp-wt-ablate-s1-0903`（3 文件） | `git worktree add ~/fwp-wt-ablate-s1 salvage/fwp-wt-ablate-s1-0903` |
| `~/fwp-wt-ablate-s2` | `ablate/s2-pronoun` | 126 | — | 封存提交 `c7b5eb9c0dcd` @ `salvage/fwp-wt-ablate-s2-0903`（1 文件） | `git worktree add ~/fwp-wt-ablate-s2 salvage/fwp-wt-ablate-s2-0903` |
| `~/fwp-wt-ablate-s3` | `ablate/s3-slots` | 126 | — | 封存提交 `32768ab47ac4` @ `salvage/fwp-wt-ablate-s3-0903`（2 文件） | `git worktree add ~/fwp-wt-ablate-s3 salvage/fwp-wt-ablate-s3-0903` |
| `~/fwp-wt-candidate-no-terminate` | `fix/candidate-no-terminate` | 126 | — | 封存提交 `b820c346f500` @ `salvage/fwp-wt-candidate-no-terminate-0903`（10 文件） | `git worktree add ~/fwp-wt-candidate-no-terminate salvage/fwp-wt-candidate-no-terminate-0903` |
| `~/fwp-wt-wind-l2-adapter` | `feat/wind-l2-adapter` | 144 | — | 钩子拦下 → patch+拷贝 `~/kb_work/worktree-salvage-2026-09-03/finance/fwp-wt-wind-l2-adapter/`（6 文件） | `git worktree add ~/fwp-wt-wind-l2-adapter salvage/fwp-wt-wind-l2-adapter-0903` |
| `~/finance-wt/seam-census` | `test/conformance-seam-census` | 153 | — | — | `git worktree add ~/finance-wt/seam-census test/conformance-seam-census` |
| `~/finance-wt/session-facts` | `fix/session-facts-shared-repo-freshness` | 154 | — | — | `git worktree add ~/finance-wt/session-facts fix/session-facts-shared-repo-freshness` |
| `~/finance-wt/runtime-conformance` | `test/runtime-conformance-suite` | 155 | — | — | `git worktree add ~/finance-wt/runtime-conformance test/runtime-conformance-suite` |
| `~/fwp-wt-qc-489-e2e` | `(detached)` | 186 | — | 封存提交 `0503be1dbbbd` @ `salvage/fwp-wt-qc-489-e2e-0903`（2 文件） | `git worktree add ~/fwp-wt-qc-489-e2e salvage/fwp-wt-qc-489-e2e-0903` |
| `~/fwp-wt-qc-439` | `(detached)` | 340 | — | 封存提交 `6ebaa623db62` @ `salvage/fwp-wt-qc-439-0903`（1 文件） | `git worktree add ~/fwp-wt-qc-439 salvage/fwp-wt-qc-439-0903` |
| `~/fwp-wt-qc-443` | `(detached)` | 342 | — | 封存提交 `c1cc1d7b331a` @ `salvage/fwp-wt-qc-443-0903`（2 文件） | `git worktree add ~/fwp-wt-qc-443 salvage/fwp-wt-qc-443-0903` |
| `~/fwp-wt-qc-0826` | `(detached)` | 374 | — | 封存提交 `4364034e5508` @ `salvage/fwp-wt-qc-0826-0903`（1 文件） | `git worktree add ~/fwp-wt-qc-0826 salvage/fwp-wt-qc-0826-0903` |
| `~/fwp-wt-forecast-residual-followup` | `feat/forecast-residual-followup` | 544 | — | 封存提交 `6bfbf1fc252e` @ `salvage/fwp-wt-forecast-residual-followup-0903`（1 文件） | `git worktree add ~/fwp-wt-forecast-residual-followup salvage/fwp-wt-forecast-residual-followup-0903` |
| `~/fwp-wt-forecast-residual-deep` | `feat/forecast-residual-deep` | 550 | — | 封存提交 `8993eaf5548f` @ `salvage/fwp-wt-forecast-residual-deep-0903`（2 文件） | `git worktree add ~/fwp-wt-forecast-residual-deep salvage/fwp-wt-forecast-residual-deep-0903` |
| `~/fwp-wt-outlook-live-weekly-pack` | `feat/outlook-live-weekly-pack` | 571 | — | 封存提交 `4bad15404543` @ `salvage/fwp-wt-outlook-live-weekly-pack-0903`（2 文件） | `git worktree add ~/fwp-wt-outlook-live-weekly-pack salvage/fwp-wt-outlook-live-weekly-pack-0903` |
| `~/fwp-wt-request-loop-map` | `docs/request-loop-three-paths` | 604 | — | 封存提交 `56e91eaf2cc3` @ `salvage/fwp-wt-request-loop-map-0903`（3 文件） | `git worktree add ~/fwp-wt-request-loop-map salvage/fwp-wt-request-loop-map-0903` |
| `~/fwp-wt-event-calendar-serving` | `feat/event-calendar-serving` | 614 | — | 封存提交 `3d3107f33f98` @ `salvage/fwp-wt-event-calendar-serving-0903`（1 文件） | `git worktree add ~/fwp-wt-event-calendar-serving salvage/fwp-wt-event-calendar-serving-0903` |
| `~/fwp-wt-workbench-quality-ceiling` | `codex/workbench-quality-ceiling` | 618 | — | 钩子拦下 → patch+拷贝 `~/kb_work/worktree-salvage-2026-09-03/finance/fwp-wt-workbench-quality-ceiling/`（35 文件） | `git worktree add ~/fwp-wt-workbench-quality-ceiling salvage/fwp-wt-workbench-quality-ceiling-0903` |
| `~/fwp-wt-agent-trace` | `feat/agent-adhoc-trace` | 628 | — | 封存提交 `da0a0c41530f` @ `salvage/fwp-wt-agent-trace-0903`（3 文件） | `git worktree add ~/fwp-wt-agent-trace salvage/fwp-wt-agent-trace-0903` |
| `~/fwp-wt-codex-workbench-product-value-spec` | `codex/docs-codex-workbench-product-value-spec` | 628 | — | 钩子拦下 → patch+拷贝 `~/kb_work/worktree-salvage-2026-09-03/finance/fwp-wt-codex-workbench-product-value-spec/`（19 文件） | `git worktree add ~/fwp-wt-codex-workbench-product-value-spec salvage/fwp-wt-codex-workbench-product-value-spec-0903` |
| `~/fwp-wt-eval-p0-abc` | `eval/p0-abc-rerun` | 628 | — | 封存提交 `92f93da732c4` @ `salvage/fwp-wt-eval-p0-abc-0903`（2 文件） | `git worktree add ~/fwp-wt-eval-p0-abc salvage/fwp-wt-eval-p0-abc-0903` |
| `~/fwp-wt-handoff-0822` | `chore/handoff-close-0822` | 637 | — | 封存提交 `dd156b234b44` @ `salvage/fwp-wt-handoff-0822-0903`（2 文件） | `git worktree add ~/fwp-wt-handoff-0822 salvage/fwp-wt-handoff-0822-0903` |
| `~/fwp-wt-retire-feishu-market-daily` | `fix/retire-feishu-market-daily` | 649 | — | 封存提交 `e5c840c9f642` @ `salvage/fwp-wt-retire-feishu-market-daily-0903`（1 文件） | `git worktree add ~/fwp-wt-retire-feishu-market-daily salvage/fwp-wt-retire-feishu-market-daily-0903` |
| `~/.cache/regcheck-314/finance-workspace-private` | `docs/r17-live-backfill` | 668 | — | 封存提交 `472b8d80c67e` @ `salvage/finance-workspace-private-0903`（1 文件） | `git worktree add ~/.cache/regcheck-314/finance-workspace-private salvage/finance-workspace-private-0903` |
| `~/fwp-wt-mainflow` | `docs/inputside-closeout-r2-spec` | 707 | — | 封存提交 `1e50aed9b7ff` @ `salvage/fwp-wt-mainflow-0903`（1 文件） | `git worktree add ~/fwp-wt-mainflow salvage/fwp-wt-mainflow-0903` |
| `~/.finance-runtime/finance-workspace-6320b3bcbf82` | `(detached)` | 726 | — | 封存提交 `0f61d40783e5` @ `salvage/finance-workspace-6320b3bcbf82-0903`（69 文件） | `git worktree add ~/.finance-runtime/finance-workspace-6320b3bcbf82 salvage/finance-workspace-6320b3bcbf82-0903` |
| `~/.finance-runtime/finance-workspace-be7c1e7eac81` | `(detached)` | 829 | — | 封存提交 `eca439f314d6` @ `salvage/finance-workspace-be7c1e7eac81-0903`（1 文件） | `git worktree add ~/.finance-runtime/finance-workspace-be7c1e7eac81 salvage/finance-workspace-be7c1e7eac81-0903` |
| `~/fwp-wt-verifier-ablation` | `docs/verifier-ablation-e` | 916 | — | 封存提交 `3a24af2f1187` @ `salvage/fwp-wt-verifier-ablation-0903`（1 文件） | `git worktree add ~/fwp-wt-verifier-ablation salvage/fwp-wt-verifier-ablation-0903` |
| `~/finance-workspace-wrong-main-5b456532` | `local/wrong-main-5b456532` | 1497 | — | 钩子拦下 → patch+拷贝 `~/kb_work/worktree-salvage-2026-09-03/finance/finance-workspace-wrong-main-5b456532/`（35 文件） | `git worktree add ~/finance-workspace-wrong-main-5b456532 salvage/finance-workspace-wrong-main-5b456532-0903` |

### 保留树，补分支引用保住游离提交（1）

| 树 | 分支 | 落后 | 未合提交 | 封存 | PR / 复活 |
|---|---|---|---|---|---|
| `~/.finance-runtime/finance-workspace-7afe37be1913` | `(detached)` | 578 | fix(verifier): 无主语的市场级问题恢复数值 backfill<br>fix(verifier): 放开的那一档收紧到「类型未解析」，题材仍 fail closed<br>docs: 本单收据与台账（R-20260824-01/02，pending）<br>…共 5 条 | 游离提交挂到 `salvage/detached-7afe37be1913` | `git worktree add ~/.finance-runtime/finance-workspace-7afe37be1913 salvage/detached-7afe37be1913` |

## 知识库仓 knowledge-base-private（16 棵）

### 开 PR（保留树）（7）

| 树 | 分支 | 落后 | 未合提交 | 封存 | PR / 复活 |
|---|---|---|---|---|---|
| `~/kb-wt-baseline-rebuild-0828` | `baseline/rebuild-queue-0828` | 234 | data(baseline): digest orphan P2 four names as r | 封存提交 `05678be3642f` @ `baseline/rebuild-queue-0828`（1 文件） | PR #133（合并有冲突，需 rebase） |
| `~/kb-wt-disclosure-archive-0813-0828` | `disclosure/archive-0813-0828` | 240 | data(disclosure): 归档 08-13~08-28 未跟踪巨潮 RSS 公告 21<br>data(disclosure): 收编 08-22~08-28 夜批 sidecar 队列与 <br>data(disclosure): P0 感光干膜官方年报补证并关闭 review-queue  | — | PR #135（合并有冲突，需 rebase） |
| `~/kb-wt-ima-slice-0828` | `theme-radar/ima-slice-0828` | 240 | concept-ingest: 原料药占位升 L1，32 candidates 按 8/16 口<br>docs: IMA 切片交接——CRO 队列关账，590 余量 517<br>fix: 原料药流水改 #6824，避开 queue-drain 医药 #6823 | 封存提交 `48f68e5c1af0` @ `theme-radar/ima-slice-0828`（11 文件） | PR #137（合并有冲突，需 rebase） |
| `~/kb-wt-queue-drain-0828` | `theme-radar/kb-queue-drain-0828` | 240 | 跨仓 kb-ingest 08-26/27/28 队列清零：医药占位升 L1，乡村振兴过宽不建。<br>data(queue): 把 08-26/27/28 终态和 08-28 第二包回写到 drai | 封存提交 `d65973bab538` @ `theme-radar/kb-queue-drain-0828`（1 文件） | PR #138（合并干净） |
| `~/kb-wt-concept-l1-0825` | `concept/l1-precious-industrial-0825` | 262 | docs(concept-ingest): 固化 IMA DeepDive 主路径（Copilo | — | PR #134（合并有冲突，需 rebase） |
| `~/worktrees/kb-batch-replay-0819` | `feature/batch-replay-20260819` | 288 | generate: 全量复盘 batch replay 2026-08-19（125 报告，mi<br>fix: 发酵复盘批量模式文件名守卫——sanitize + 撞名折叠检测 + 生成幂等 | — | PR #139（合并干净） |
| `~/kb-wt-entity-landing-0816` | `baseline/entity-landing-0816` | 290 | docs(handoff): 记录非ST实体落点批次在途状态 | 封存提交 `8b198a7f5b9f` @ `baseline/entity-landing-0816`（78 文件） | PR #136（合并有冲突，需 rebase） |

### 拆树（过期：落后 >300，分支引用保留）（1）

| 树 | 分支 | 落后 | 未合提交 | 封存 | PR / 复活 |
|---|---|---|---|---|---|
| `~/finance-workspace-private/tmp/kb-dual-engine-plan-cb3c4e21` | `codex/kb-dual-engine-plan` | 542 | docs: design dual-engine knowledge memory | 封存提交 `0222e9922ee8` @ `codex/kb-dual-engine-plan`（1 文件） | `git worktree add ~/finance-workspace-private/tmp/kb-dual-engine-plan-cb3c4e21 codex/kb-dual-engine-plan` |

### 拆树（补丁已在基线）（8）

| 树 | 分支 | 落后 | 未合提交 | 封存 | PR / 复活 |
|---|---|---|---|---|---|
| `~/kb-wt-wave97-gold-align-0829` | `baseline/wave97-gold-align-0829` | 23 | — | 封存提交 `28974262b0d8` @ `salvage/kb-wt-wave97-gold-align-0829-0903`（2712 文件） | `git worktree add ~/kb-wt-wave97-gold-align-0829 salvage/kb-wt-wave97-gold-align-0829-0903` |
| `~/kb-wt-ima-cpo-0826` | `ingest/cpo-deepdive-0826` | 225 | — | 封存提交 `ad72e7384889` @ `salvage/kb-wt-ima-cpo-0826-0903`（11 文件） | `git worktree add ~/kb-wt-ima-cpo-0826 salvage/kb-wt-ima-cpo-0826-0903` |
| `~/kb-wt-ima-renxing-0826` | `ingest/humanoid-robot-deepdive-0826` | 225 | — | 封存提交 `0de74be9fb75` @ `salvage/kb-wt-ima-renxing-0826-0903`（10 文件） | `git worktree add ~/kb-wt-ima-renxing-0826 salvage/kb-wt-ima-renxing-0826-0903` |
| `~/kb-wt-ima-stock-0826` | `ingest/ima-stock-logic-0826` | 225 | — | 封存提交 `1e12687c1ff4` @ `salvage/kb-wt-ima-stock-0826-0903`（672 文件） | `git worktree add ~/kb-wt-ima-stock-0826 salvage/kb-wt-ima-stock-0826-0903` |
| `~/kb-wt-ima-themes-0828` | `ingest/hot-theme-deepdive-0828` | 225 | — | 封存提交 `c31b0015242c` @ `salvage/kb-wt-ima-themes-0828-0903`（114 文件） | `git worktree add ~/kb-wt-ima-themes-0828 salvage/kb-wt-ima-themes-0828-0903` |
| `~/.devin-worktrees/ima-queue-auto-triage` | `fix/rag-gitea-release` | 274 | — | 封存提交 `048d5fe78fbc` @ `salvage/ima-queue-auto-triage-0903`（2 文件） | `git worktree add ~/.devin-worktrees/ima-queue-auto-triage salvage/ima-queue-auto-triage-0903` |
| `~/.devin-worktrees/ima-queue-0822` | `concept/ima-queue-0822` | 283 | — | 封存提交 `1581252de524` @ `salvage/ima-queue-0822-0903`（1 文件） | `git worktree add ~/.devin-worktrees/ima-queue-0822 salvage/ima-queue-0822-0903` |
| `~/.devin-ci/knowledge-base-private` | `(detached)` | 826 | — | — | `git worktree add ~/.devin-ci/knowledge-base-private 0025c34b8332` |

## 没动的（活跃或挂 PR）

金融仓 18 棵活跃 + 挂 PR 的 #517 `fix/judge-fallback-cli-backend`、#458 `feat/public-daily-brief`；知识库仓 17 棵活跃 + 挂 PR 的 #129 / #94 / #26。
保留的运行时快照：`c88c81da5120`（8792）、`d4fade5494ee`（回滚锚）、`40fd5a847c65`（capability-sidecar）、`7afe37be1913`（glm-canary 启动器引用，游离 5 提交已挂 `salvage/detached-7afe37be1913`）；`~/kb-runtime`（`com.kb.disclosure-scout` 在用）。

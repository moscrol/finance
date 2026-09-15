# 在途交接 · feat/sub-research-tool（已合 #610 → main `a11d76ca`，8792 已切）

## 这个分支做什么
把既有 `SubResearchCoordinator` 包成模型可点的工具 `sub_research`（spec `2026-09-03-subagent-tool-design.md`）：抄 dsh `tool-subagent` 形状（前台同步、深度 1），账本用我们的——分支证据经父账本 `branch_sink` 进账、hash 由父账本铸。收据 `docs/verification/2026-09-07-max-shape-readings-and-sub-research-live.md`。

## 决策与被否方案
- runner 在 `runtime` 层按 episode 绑、`build_episode_registry` 没 runner 不挂 / 否占位 runner / 没源不挂；审计脚本与 `memory_lookup` 同列条件装配。
- 分支 deadline 收进本批工具窗 ×0.9 / 否 episode deadline / 批执行器等的是窗。
- 分支事件在 runner 线程记（RLock），`origin=tool` / 否只进 telemetry。
- `_ContextRef` 让 runner 读升档后的 context / 否闭包捕获起步值。
- 协调器档位门 `∈ {deep, max}` / 否则 max 起步永远 `deep_mode_required`。
- 不做后台 / 可续接 / 嵌套。

## 当前状态
8792=`a11d76ca`（max 形状 + `sub_research`），三读一致、readiness 全绿、账本 ok；回滚锚 `cutover-20260907b-subresearch-rollback-8792.txt`（回 `5cc5aa8b`）。门禁 7943P/0F 同基线红集；13 新测试 + 3 变异各击杀 1；普查表（conformance / 开关板 / 进度标签 / 默认盒）已登记。**live n=1：sol 第一个工具就点了它，三支并行回 51 条证据，父臂 18 个绑定 hash 里 16 个是分支铸的。**

## 未验证 / 已知边界
- 分支上限已随档位放大（#615：max 150s/10）；150s 下仍 9/9 partial，下一档候选是分支内每批帽（quick=4）。
- sol 12/12 不交 PLAN：PLAN → deep 路径在 sol 上也是死的，子研究只靠工具形式可达。
- 分支 ×3 与全局 8 worker 争用未量。
- D 组读数里两条越线（D9 方向预测、D7 实体解析）是出口侧候选约束，见收据 §2，未实施。

## 下一步
1. ~~出口硬门~~ #612 已合；~~分支预算~~ #615 已合；顺带修了修复轮表达槽硬拒（#616）与 LLM 保险丝（#617），见 `2026-09-07-branch-budget-repair-fuse.md`。
2. 分支内每批帽（quick=4）是否是分支慢的原因：先量分支的 tool_menu / 派发数再动。→ 量的代码在 `feat/branch-level-trace`（`inflight/feat-branch-level-trace.md`），合入切流后重跑同题读 `branch_completed.batches`。
3. A/B/C 28 题 max 全景：Codex 5h 窗 70% / 周 69%，等用户拍。
4. 09-06 22:56 成批文件改写写者未查明——用户侧确认。

## 踩过的坑
- 后台批跑用工具自己的后台方式，`nohup … &` 会被回收（交接里早写过，又踩一次）。
- 参数 schema 经 `_freeze_json` 后 list 变 tuple；census 三张表（conformance / switchboard / progress 标签）新工具都要登记，全量门禁才抓得到。

## 已验证
门禁 7943P/0F；`test_sub_research_tool` 13 绿；切流三项验证；live 探针 `run_20260907_020835_725077` 判官 passed、degrade 0。

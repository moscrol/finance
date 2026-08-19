# 2026-08-19 派单：depth-gap 剩余施工 + 门禁放行 live 验证（五轨道）

> 给接单 agent 的执行派单。**判据真本源不在本文件**：depth-gap 各刀的验收判据在
> `docs/learning/spec-continuous-depth-gap-r1.md`（R5，main 上这份是唯一副本，分支已收编）；
> 门禁放行的验证清单在 `docs/handoffs/inflight/fix-gate-partial-release.md`。
> 本文件只管：谁、按什么顺序、在哪棵树、拿什么收据。判据两处存必漂（R4/main 分叉刚发生过），别抄。

## 环境事实（2026-08-19 15:10 快照，开工前自行复核）

| 项 | 值 |
|---|---|
| 生产 8792 | `441c60f2`（#224 门禁爆炸半径收敛已上线；快照 `~/.finance-runtime/finance-workspace-441c60f27cc2`，回滚锚 `finance-workspace-a7e2d74f7789`） |
| E4 分支 | `feat/p1e4-next-watch-consume` 已推 gitea（实现 `3e58aa1e` + 交接 `44e6ef42`，基点 `a7e2d74f`，与 #224 零文件交叠）；树 `~/fwp-wt-p1e4-next-watch`（干净） |
| spec 分支 | `spec/continuous-depth-gap-r1` 远端已删（R5 收编进 main）；本地检出还挂在 `~/.finance-runtime/finance-s7-sync`，勿动勿续写 |
| 定向测试收据 | 50 passed @ `~/.finance-runtime/test-receipts/20260819T065109Z-3e58aa1e.json`（验收方须独立复跑，不抄） |
| 合并/链切规程 | `docs/workflows/acceptance-workflow.md`（merge-tree 自探、四件套、链切五步、三项验证、备份、台账行） |
| sidecar 工具 | `scripts/live_probe.py ask '<题>' --repo-root <被测树> [--port 8796]`（自起自停，收据落 `~/.finance-runtime/live-probe-traceability/`；勿占 8792/8793/8795/8799/8801） |

## 轨道总览

| 轨道 | 内容 | 前置 | 可并行性 |
|---|---|---|---|
| A | 门禁放行 live 验证（打生产 8792） | **已关闭 15:28** | 与 B/E 并行；**B 现可链切** |
| B | E4 验收收口（sidecar live → 合并 → 切 8792） | 无，立即可开 | live 部分与 A/E 并行；**链切须在 A 重放完成后** |
| C | E2 修订版在前（continuous 接通） | **B 合并后**（同文件 `conversation_orchestrator`） | 与 D 串行 |
| D | E1 四态接 repair + E3 TTL 机器可读 | C 之后 | — |
| E | 验证器消融实验（只读，零合并） | 无 | 与 A/B 并行（sidecar 端口错开） |

## 轨道 A：门禁放行 live 验证

- 清单真本源：`docs/handoffs/inflight/fix-gate-partial-release.md`「下一步」节（原题重放 / 财务锚 fail-closed / 一周 telemetry）。
- 本轨道是唯一**允许打生产 8792** 的：重放就是要验生产行为。run 产物在 `~/.local/share/finance-workbench/users/<id>/runs/`。
- 交付：`docs/verification/2026-08-19-gate-partial-release-live.md`（预期读数 vs 实测：verified=completed 或 partial 放行正文；issues 至多剩 `stripped unsupported evidence type`；不再出「现有证据不足」模板）+ 更新该 inflight handoff。
- **已关闭（2026-08-19 15:28）**：读数见 verification。SPT 重放 `run_20260819_152316_348138` 放行正文；估值 `run_20260819_152635_937314` 仍 fail-closed。**轨道 B 可以链切**（当时无 in-flight；链切前再确认一次）。一周 telemetry / A3 不归本轨道收口。

## 轨道 B：E4 验收收口（验收方角色，独立复算）

1. 从 `gitea/main` 开验收树（或复用 `~/fwp-wt-p1e4-next-watch` 只读检视）；`git merge-tree --write-tree gitea/main feat/p1e4-next-watch-consume` 自探冲突（别信 Gitea `mergeable`）。
2. 定向测试独立复跑（`test_track_contract.py` + `test_foresight.py`，env -i + umask 022）。
3. sidecar live：`live_probe.py ask --repo-root ~/fwp-wt-p1e4-next-watch`，两道题——
   - 1 道**真 `theme_track`**（最好带上期 [M]/[V]）；跑完读 run.json 确认 `question_type=theme_track`，theme_analysis 不算数（R5 §四.3 教训）。
   - 1 道无基线跟踪题（验「无上期基线」降级路径）。
   - 判据见 R5 §三 P1-E「验收」段：下期关注子弹落 `checkpoints.jsonl`（`source=track_next_watch`、有若/则/阈值/日期、去重）、次日 foresight 提示词强制对照、E 覆盖率不回退。**禁止**套第五轮隔夜预测题。
4. 读数落 `docs/verification/2026-08-19-p1e4-next-watch-live.md`；结论（PASS/打回）写 PR 评论。
5. **用户确认后**走 acceptance-workflow §2 合并 → §3 四件套 → §4 链切五步 + 三项验证 + 备份 → §5 台账行。链切前确认轨道 A 重放已完成、8792 无在途 run（kickstart 会杀 in-flight，08-16 教训）。

## 轨道 C：E2 修订版在前（B 合并后开工）

- 从合并后的 `gitea/main` 新开 `feat/e2-revise-first`。
- 施工缝与边界：R5 §三 P1-E「E2（其后）」行——只接通 continuous 编排器呈现顺序（现状 `compose_revise_on_warn=False`），**不换**仓内 `output_review` 的 6 项，附录 A.1 缺口②③不做。
- 验收：另备 WARN 案例题（不是预测题），正文=修订版在前、审查意见进「输出质检」附录；测试先红后绿；sidecar live 一发。
- 合并需用户确认。

## 轨道 D：E1 四态接 repair + E3 TTL（C 之后）

- E1：`contract_missing_outputs` 收据已有，缺的是 episode **运行时**真正送进 repair（R5 §三 E1 行）。禁止再注入第二套文案。⚠ #224 已改 verifier issues 语义（新增 `stripped unsupported evidence type` 前缀、类型缺口可 partial 放行），对接 repair 词表以 main 现状为准，别拿旧 run 的 issue 文案当契约。
- E3：判断加机器可读 `valid_until` + 过期降级程序；过期只标注不删结论（R5 §三「边界」）。
- 验收：同轨道 B 的题型纪律（theme_track 真题）；测试先红后绿。合并需用户确认。

## 轨道 E（可选）：验证器消融实验

- R5 §五遗留：同题关闭 repair 裁剪复跑，预期多出来的是**无据阈值**（第六轮对照 run `110003` 的「约2.2万亿」就是活样本）而不是领跌结构。若结果相反，回改 R5 第二节第三层表述。
- sidecar only、零合并、零生产影响。读数落 `docs/verification/`。

## 全局纪律（所有轨道）

- 开工先 `git worktree list` + `git status --short` 逐条认领；解释器一律 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；提交一律 pathspec；推分支不推 main（hook 会拦，合并走 PR + 用户确认）。
- 每轨道收尾：读数文档 + inflight handoff 更新 + 台账行（若有合并/链切）。收据路径写进文档前先 `ls` 确认存在。
- E5 尾巴不归本派单：`feat/reading-rules-baseline-batch1` 合入时把 `foresight_methodology.md` §八登记进 `_METHODOLOGY_OVERLAP`（已写在该分支 inflight handoff）。

## 用户拍板点

1. 轨道 B 的合并与链切时机。
2. 轨道 C / D 的合并。
3. `finance_query` 要不要正式进 `prime_quote` 白名单（轨道 A 一周 telemetry 后，数据口径决定）。
4. 轨道 E 若证伪「无据数字触发线是负资产」的机制收窄表述 → R5 修订。

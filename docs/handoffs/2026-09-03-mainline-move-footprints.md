# 主检出树前移 main 与足迹保管（2026-09-03）

主检出树 `/Users/a77/finance-workspace-private` 自 08-30 停在 `fix/observation-qualifier-order`@`7f466357`
（补丁已在 main，cherry+0），带 25 个已跟踪修改与一批未跟踪的工单 / 设计稿 / 脚本，无 inflight 交接、归属不明，
会话钩子每次开工都在报警。09-03 照 08-28 先例（`wip/mainline-move-footprints-20260828`）处置：

- **保管分支** `wip/mainline-move-footprints-20260903` @ `10f7d73c`（已推 gitea，**不合 main**，归属 session 自取）。
  pre-commit 十一道全过，没用 `--no-verify`。
- **主检出树** `checkout -B main gitea/main` → `ccf93431`，上游 `gitea/main`，已跟踪脏文件 0。
- **数据产物原地保留**（154 个未跟踪：`复盘/daily/2026-08-26～09-02`、`market_feature_store/exports/*`、
  `intelligence/eval/runs/*.json`、反思 / 复盘台账 JSON、`skills/daily-full-review/state/quality-*.json`、
  `.workbuddy/`、`intelligence/users/ablation-veteran-probe/`），不进保管分支——它们是日报流水线的产物，
  等下一次 `chore(artifacts)` 回写；与 main 无路径冲突，切分支不碰它们。

## 保管分支里有什么（54 个文件，+5485 / −76）

| 类 | 文件 | 备注 |
|---|---|---|
| 会话 / 钩子 | `AGENTS.md`、`.claude/hooks/load-memory.sh`、`.codex/hooks/load-memory.sh`、`scripts/session_facts.sh`、`.devinignore` | 与 main 不同文 |
| 日报线代码 | `intelligence/cli.py`、`intelligence/workflows/daily_review.py`、`tests/test_daily_review_agent_entry.py`、`skills/daily-full-review/state/runlog.md` | 与 main 不同文 |
| 日报线代码（已等价在 main） | `intelligence/services/content_delta.py`、`skills/daily-full-review/SKILL.md`、`skills/daily-full-review/scripts/export_increment.py` | 工作副本与 main 逐字相同，为完整性收入 |
| 新代码 | `intelligence/services/ima_gap_report.py` + `tests/test_ima_gap_report.py`、`scripts/exp_umd_rejudge.py` / `exp_umd_structure_probe.py` / `exp_user_memory_diff.py`、`skills/duckdb-backfill/scripts/repair_duplicated_stock_daily.py` | main 无 |
| 工单 / 设计稿 | 08-28 十份 backlog 工单（含 INDEX）、08-29 五份 conformance 工单、08-30 五份设计稿、09-01 finance-base 形状对齐设计稿 + 收据 | 08-30 三份（`engine-b-into-a-strangler` / `optimized-orchestration-contract` / `workbench-correction-loop`）**与 main 同名不同文**，`coverage-without-number-ownership` 与 main 相同 |
| 学习产物 | `docs/learning/forecast-lessons/reflections/2026-07-0{3,7,8}.*.json`（7）、`forecast-review-ledger/index.{md,html}`、`docs/trace-profile.md` | 已跟踪修改 |
| 复盘矩阵 | `复盘/matrices/strategy-review-workbench.html` 等四张 | main 已不跟踪这些路径 |

## 怎么取回

```bash
# 看清单
git -C /Users/a77/finance-workspace-private show --stat wip/mainline-move-footprints-20260903
# 单文件拿回工作树（不切分支）
git -C <你的树> checkout wip/mainline-move-footprints-20260903 -- intelligence/workflows/daily_review.py
# 整体在新树上续做
git -C /Users/a77/finance-workspace-private worktree add ~/fwp-wt-<名> wip/mainline-move-footprints-20260903
```

08-30 三份同名不同文的设计稿：取回前先 `git diff gitea/main wip/mainline-move-footprints-20260903 -- <path>` 看
main 版本是不是已经吸收了你的改动。

## 为什么现在动

- 双盲链 plist 与 SessionStart 钩子都指主检出树；主树不在 main 上，`#498` 之后的解释器修复与最新 `session_facts.sh`
  对它们不生效（08-28 台账已点名「学习注入待主树前移到含 #498 的 main 后才真生效」）。
- 生产数据根就是这棵树；它停在哪个分支不影响 8792 的代码（那走快照），但影响所有以主树为 cwd 的定时任务。

## 没做

没判断这些足迹该不该合 main、没改任何一行内容、没删数据产物。归属者认领后自己决定。

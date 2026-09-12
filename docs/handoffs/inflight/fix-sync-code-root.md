# fix/sync-code-root · 夜跑 sync 代码根钉死

## 状态：已提交 `5b57d109`，**未推未合**，等用户确认

## 修了什么

夜跑 sync 从 2026-09-10 起连着三次 rc=2，**09-11（周五、交易日）整日没进库**，
20:40 finalize 守卫 rc=2 中止，方法飞轮那段根本没执行到。

根因链（逐段实测）：`nightly-review-sync-staged.py:39` 的 `SYNC_ROOT` 缺省是
`FINANCE_DATA_ROOT` → 也就是各 agent 共用的主检出树 `finance-workspace-private`
→ 它 detached 在 `b4a35fa2`、**落后 gitea/main 548 个提交**、`PLANS` 里没有
`local` → plist 设的 `REVIEW_SYNC_PLAN=local` 撞上
`ValueError: unknown plan 'local'` → staging 不换名。

改法：plist 显式给 `FINANCE_SYNC_CODE_ROOT=/Users/a77/finance-workspace-sync`
（新建的 detached worktree，跟随 `gitea/main`，只做这一件事，不在上面开发）。
**仓内源与装机副本两边都改了**——`install_eval_launchd.sh` 是 `cp 源 → dest`，
只改装机副本下次重装会被静默冲回（09-04 已在 `REVIEW_SYNC_PLAN` 上踩过同一坑）。
新测试断言该键存在、且既不等于 `FINANCE_DATA_ROOT` 也不等于 `FINANCE_CODE_ROOT`。

## 已验证

- 证伪对：旧 SYNC_ROOT 抛的正是生产那条 `ValueError`；新树 `resolve_plan('local')`
  解出 16 步、`preflight(require_fupanhui=False)` 全绿。
- 装机侧：`bootout` + `bootstrap` 后 `launchctl print` 显示新值，18:30 计划完好。
- ruff 全过；`tests/test_eval_launchd_wiring.py` 15 passed；新测试做过变异
  （删键转红、还原转绿）；`check_path_literals.py` exit 0；11 道 pre-commit 全过。
- **未跑全量 pytest**：另一 agent 16:50 起在 `fwp-wt-verify-8bc7252b` 跑全量，
  16 GB 机器不并发第二份。合入前补。

## 未决（留给用户，我没自作主张）

1. **`REVIEW_SYNC_PLAN` 仓内源=`auto`、装机副本=`local`，仍在漂。**
   下次 `install_eval_launchd.sh` 会把它冲回 `auto`；`auto` 在非周五=`cheap`，
   而 `cheap` 要 fupanhui 登录，**当前实测未登录**（`preflight(True)` 红）→ 会
   rc=3 停在 preflight。要么把 `local` 扶正进源（改档决定），要么恢复 Chrome 登录。
   现有测试 `test_review_sync_plist_source_carries_tiered_plan` 钉的是 `auto`，
   改档要连它一起改。
2. **9-11 数据补跑**：用户手动 `/daily-full-review`（有副作用技能）。
   `local` 档的 16 步覆盖标签需要的七张表（缺的 `theme-flow-daily` /
   `limit-advance` 标签口径不用）。

## 别做

- 别把 `FINANCE_SYNC_CODE_ROOT` 指回数据仓或运行快照（理由在 plist 注释里）。
- 别在 `/Users/a77/finance-workspace-sync` 上开发——它是夜跑代码根，
  只用 detached checkout 跟随 `gitea/main`。
- 别推进主检出树：64 个未提交改动、22 个与上游真冲突，是别人的 WIP。

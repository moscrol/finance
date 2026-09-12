# fix/sync-code-root · 夜跑两个代码根钉死

## 状态：三个提交，**未推未合**，等用户确认

`5b57d109` sync 代码根 / `6439ea77` 质检闸门代码根 / handoff。

## 完成口径（别写成「事故已修」）

已修掉 `unknown plan 'local'` 的代码根原因，并验证装机配置已加载；
**真实同步、最终检查、方法日步尚未贯通验收**。

## 两处都是同一个形状：根解析缺省落到共用主检出树

主检出树 `finance-workspace-private` detached 在 `b4a35fa2`、**落后 gitea/main 548
个提交**、带 64 个别人的未提交改动。它不能当任何运行时的代码根。

1. **sync**：`nightly-review-sync-staged.py:39` 的 `SYNC_ROOT` 缺省 `FINANCE_DATA_ROOT`
   → 那份 `run_review_sync.py` 的 `PLANS` 没有 `local` → `ValueError` rc=2 →
   **09-11（周五、交易日）整日没进库**。修：plist 显式
   `FINANCE_SYNC_CODE_ROOT=/Users/a77/finance-workspace-sync`（新建 detached
   worktree，跟随 `gitea/main`，只做这件事，不在上面开发）。
2. **质检闸门**：三处 `scripts/check_daily_review_data.py` 是裸相对路径，落在
   `cd "$WORKSPACE"` 之后 = 同一棵旧树；那份没有 `--plan`、表清单写死，
   plan=local 下必然少 `theme_flow` / `limit_advance`。同日同库实测（2026-09-10）：
   旧树 **exit=2 INCOMPLETE**（卡 `fact_theme_flow_daily`）/ CODE_ROOT 那份
   **exit=0 COMPLETE**。修：`REVIEW_CHECKER="$CODE_ROOT/scripts/…"`，缺了就停、
   不回退顶替。计划口径不用另传，`--plan` 缺省读 `REVIEW_SYNC_PLAN`，两个 plist 都有。

仓内源与装机副本**两边都改了**（`install_eval_launchd.sh` 是 `cp 源 → dest`）。
装机副本是外科式打补丁：它与仓内版有其它有意差异
（`docs/handoffs/inflight/chore-retire-feishu.md:71`），**别跑安装脚本覆盖它**。
两处原件备份为同目录 `*.bak-pre-*-20260912`。

## 订正两处我先前说错的

- `deploy_workbench_runtime.sh` **不更新** `scripts/`（只 rsync `intelligence/` 进
  **已有**快照），`install_eval_launchd.sh` 清单也不含 `method_validation.py`。
  要让 `$CODE_ROOT` 拿到 `activate`/`supersede`，得**重切快照**：
  `git worktree add --detach ~/.finance-runtime/finance-workspace-<sha> <sha>` + 换符号链接。
- `preflight(require_fupanhui=False)` 是**跳过复盘会登录检查**（第一行就 `return []`），
  不是「全绿」，它没验证 16 步的依赖可用。

## 未验证

- `--phase all` 在 09-10 仍红，红在「日报 md 不存在 / L2 三步无完成记录」——那是
  finalize 被守卫拦掉的后果，非独立阻塞，只能等一次完整跑通才能判。
- **未跑全量 pytest**（另一 agent 在并发跑，16 GB 机器不开第二份）。合入前补。

## 未决

1. `REVIEW_SYNC_PLAN` 仓内源=`auto`、装机=`local` 仍在漂；重装会冲回 `auto`，
   而 `auto` 非周五=`cheap` 要 fupanhui 登录（实测未登录）→ rc=3。
   扶正 `local` 要连 `test_review_sync_plist_source_carries_tiered_plan` 一起改。
2. 9-11 补数：用户手动 `/daily-full-review`。
3. 已发消息给 `feat/method-closed-loop` 那个 session：其
   `nightly_full_review.sh` 第 55 行在 LOG_DIR 赋值（75 行）前用它，`set -u` 下
   rc=1 → 静默回退旧 v3 协议，`active` 一次都没跑。对 tip `dd7b6f74` 仍复现。

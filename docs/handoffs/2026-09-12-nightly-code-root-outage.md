# 2026-09-12 · 夜跑链路「根解析缺省落到共用树」事故与两处修复

在途件 `docs/handoffs/inflight/fix-sync-code-root.md`（只留状态与下一步）。
本文记背景、被否方案、以及几次走错又纠回来的地方。

## 事故形状：同一个错误在一条链上出现了三次

三处都是「根解析的缺省值指向一棵会漂的共用树」：

| 处 | 缺省怎么写的 | 落到哪 |
|---|---|---|
| sync 子进程 | `SYNC_ROOT = env(FINANCE_SYNC_CODE_ROOT, FINANCE_DATA_ROOT)` | 主检出树 |
| 质检闸门 | 裸相对路径 `scripts/check_daily_review_data.py` + `cd "$WORKSPACE"` | 主检出树 |
| 方法 CLI | `$CODE_ROOT/scripts/method_validation.py`（存在性检查，非能力检查） | 运行快照（旧） |

主检出树 `finance-workspace-private` detached 在 `b4a35fa2`，**落后 gitea/main 548
个提交**，带 64 个别人的未提交改动（22 个与上游真冲突）。

第二处最隐蔽：**裸相对路径 + 一个 `cd` = 一次隐式的根解析**。grep 根变量抓不到它，
只有把两处放在一起读才看得出来。

## 被否方案

- **推进主检出树到 gitea/main**（09-10 交接定的正解）。否掉：64 个未提交改动、22 个
  真冲突，全是别人的 WIP，处理它等于替不明作者做语义判断——这正是 09-10 当时决定
  不做的理由，两天后理由没变。
- **`FINANCE_SYNC_CODE_ROOT` 指运行快照**（09-10 的应急手法）。否掉：同一份交接写明
  「不要长期使用」——sync 的状态文件按 ROOT 相对路径写（`RUNLOG = SKILL_DIR/state/
  runlog.md`），会污染代码树；且快照每次部署整体替换，写进去的状态会丢。
- **把 `REVIEW_SYNC_PLAN` 扶正成 `local`**。没做：那是改档决定，`local` 是缺登录态
  下的降级模式不是目标稳态，且要连 `test_review_sync_plist_source_carries_tiered_plan`
  一起改。留给用户。
- **闸门缺失时回退到 WORKSPACE 那份**。否掉：顶替会以「看起来完全合理的理由」判红，
  比缺闸门更难发现——09-10~09-11 两天没人察觉正是这个形状。改成 fail closed。

## 走错又纠回来的三处（留给下一个人少踩）

1. **`plutil -lint` 不校验 XML 注释合法性**。我在 plist 注释里写了 `git checkout
   --detach`，`--` 在 XML 注释里非法；`plutil -lint` 照样 OK，是 `plistlib`/expat
   才报 `not well-formed`。plist 改完要用 `plistlib.loads` 过一遍，不能只信 plutil。
2. **`active --help` 不能当子命令能力探针**。新旧 CLI 都返回 0——`--help` 被 argparse
   优先处理，子命令合法性根本没校验，旧 CLI 打印的是顶层 help。可用的探针是
   `--help` 输出里 grep `[{,]active[,}]`（实测旧=无、新=有）。
3. **`deploy_workbench_runtime.sh` 不更新 `scripts/`**。我先前说「跑它就能让运行快照
   拿到 activate」是错的：它只把 `intelligence/` rsync 进**已有**快照。快照是按
   revision 建的 git worktree，换 `scripts/` 要重切：
   `git worktree add --detach ~/.finance-runtime/finance-workspace-<sha> <sha>` + 换符号链接。

## 测量口径上的两条自我纠正

- 第一次「精确退出码」漏传 `MARKET_FEATURE_STORE_DB`，新树没有 `db/` 于是退出 1，
  被我一度当成「新检查器也红」。同库同日重测才是有效对照：旧 exit=2、新 exit=0。
- `preflight(require_fupanhui=False)` 第一行就 `return []`，是**跳过**登录检查，
  不是「全绿」；它没验证 16 步的依赖可用。原报告措辞已订正。

## 数字（都可复算）

- `fact_market_daily` max = 2026-09-10；09-11 是周五、交易日，整日缺。
- 同日同库同 `plan=local`：主检出树检查器 `exit=2 INCOMPLETE`（卡
  `fact_theme_flow_daily`）/ `$CODE_ROOT` 那份 `exit=0 COMPLETE`。
- `local` 档 16 步，相对 `full` 少 12 步、独有 11 个 `*-local` 替身；标签需要的七张表
  都有替身覆盖，缺的 `theme-flow-daily` / `limit-advance` 标签口径不用。
- 四方口径：协议 v3 / 共享库 v4 / 运行快照代码 v4 / 分支代码 v5。

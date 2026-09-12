# fix/sync-code-root · 夜跑代码根、补跑入口、staging 旁路

## 状态：未推未合。全量在冻结提交 `aef500e2` 的干净树上跑，**结果未出**

## 完成口径（别放宽）

已修：`unknown plan 'local'` 的代码根原因、质检闸门读错树、`sync|all` 绕开 staging
直写生产、手动入口不自带缺省、推荐命令未绑成功条件。
**真实同步、最终检查、方法日步仍未贯通验收**——9-11 未入库，日报与 L2 完成记录仍缺。

装机配置只能说到「**已重载、字段与仓内源一致**」：两个 launchd 任务当前
runs=0 / never exited，`launchctl list` 那个 0 是「无失败记录」，**不是「跑成功过」**。

## 同一形状出现五次：根解析缺省落到会漂的共用树

主检出树 `finance-workspace-private` detached 在 `b4a35fa2`、落后 gitea/main 548 个
提交、带 64 个未提交改动（含 `scripts/moneyflow/` 的在途 WIP）。

| # | 处 | 状态 |
|---|---|---|
| 1 | sync 子进程 `SYNC_ROOT` 缺省 `FINANCE_DATA_ROOT` | 已修（plist 显式给值） |
| 2 | 三处质检闸门裸相对路径 + `cd "$WORKSPACE"` | 已修（`$CODE_ROOT`，缺了 fail closed） |
| 3 | `run_sync()` 裸相对路径 | 已删（连同 `sync)` / `all)` 两个分支） |
| 4 | 两个手动入口不自带缺省 | 已修（脚本内缺省 + export） |
| 5 | 生成段 `python -m intelligence.cli daily` | **未修 → 工单 #50** |

## 同步段只有 S7 一条路

同步器自己**不做** staging：写的就是 `MARKET_FEATURE_STORE_DB` 指向的库。
克隆 / 过闸 / 原子换名全在 `nightly-review-sync-staged.py`。
`nightly_full_review.sh` 的 `sync` / `all`（含只传日期的缺省 `all`）已在**加锁前**拒绝
并给出替代命令；不在本脚本里套 S7——同一把 `daily-full-review.lock`，会自锁。
实测三种调用均 rc=2 且无锁残留。补跑用：

```
nightly-full-review-s7.sh <date> && nightly_full_review.sh finalize <date>
```

`&&` 不能省：两条独立命令时同步失败会被收尾的成功掩盖。

## 装机副本（口径要准）

- 5 个脚本字节一致；s7 脚本仅注释不同；6 份 plist **配置等价**（比的是
  `EnvironmentVariables`，**不是字节相同**）。
- `nightly_full_review.sh` 装机副本与仓内源有三组实质差异：moneyflow 根用
  `$DATA_ROOT`（L2 在途 WIP 在主检出树里）、**缺 L2 挂账暂停**、**缺三处
  `skip_method_flywheel` 留痕**。后者正是 9-11 没有跳过记录的原因。
- **装机副本不在仓内全量的验证范围内**——两次改动都是外科式打补丁 + 干净 shell 实跑，
  **别跑安装脚本覆盖它**。备份在同目录 `*.bak-pre-*-20260912`。

## 合入顺序（已预演，会冲突）

`git merge-tree feat/method-closed-loop fix/sync-code-root` → 两处 CONFLICT：
`workorders-INDEX.md`（他加 #49、我加 #50，相邻行追加）与
`nightly_full_review.sh`（只有 `@@ -53` 真重叠：他把 `LOG_DIR` 上移、我在同处加拒绝块；
他**没碰** `case` 与 `sync|all` 分支，所以我的删除无语义冲突）。
建议他先合，我 rebase 后解。解法是「两边都要」，顺序：
`CODE_ROOT` → `REVIEW_CHECKER` → `export REVIEW_SYNC_PLAN` → `LOG_DIR`+`mkdir` →
METHOD 绑定 → phase 解析 → 拒绝块 → 加锁。

## 未决

1. **9-11 补数**：用户手动 `/daily-full-review`，走 S7 入口。
2. 名单基线停在 9-02；同花顺日更没接进 `local` 的 16 步（相关表停 9-08）。
   数据面缺口，不在本分支改动面，未立单，**本轮也未复算**。
3. 生成段代码根 → 工单 #50（分支 `fix/generation-stage-code-root`，待派，六条验收）。

## 关联分支 feat/method-closed-loop（非本分支）

我复验的**只是** `22c60030` 的 LOG_DIR 顺序、`607f53a6` 的新旧 CLI 分流与 exit 2 二义
拆分，**不是整体结案**。另：本机所有 session 共用一个 git 身份，`%an` 区分不了谁，
判归属要用 `git branch --contains` + `git worktree list`。

背景与被否方案见 `docs/handoffs/2026-09-12-nightly-code-root-outage.md`。

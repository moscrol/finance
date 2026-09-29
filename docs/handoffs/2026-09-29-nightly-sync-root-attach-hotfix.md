> **归档注（2026-09-30，Arena 会话）**：本文记录的夜跑同步根 `0e7f77025409` 之后先被 `541ef50ba2b2`（#977）取代，又被 `9c1e3154f613`（#982）取代。文中的代码已随 #977 进入 main：分支 `fix/nightly-attach-names-0929` 新增的 21 个测试在 main 里 21/21 都找得到。原文照录，分支保留。

# 2026-09-29 夜跑同步根热修切换：冻结根 fe9fdbfd7 → 0e7f77025409（补名接线）

写完不改；更正走 `record-correction`。

## 授权

2026-09-29 约 16:14 CST，Arena Agent 会话里问「现在执行夜跑切换吗？（改 18:30 任务的代码根，属于生产发布，需要你确认）」，用户选「执行切换（推荐）」；同一轮对「要把分支推到 Gitea 吗」选「推两个分支，并为 feat 分支开 PR」。合并进 main 未授权、未做。

## 为什么切

夜跑 18:30 从冻结根 `~/.finance-runtime/finance-sync-fe9fdbfd70a6`（fe9fdbfd7，09-25 装机）执行。该根没有 `attach-capture-names` 接线，也没有执行件（`attach_capture_names.py` 09-26 才并入 main）。09-29 新股（`301716.SZ` N鸿富诚、`920202.BJ` N安达；`920201.BJ` 见 `2026-09-29-dated-quote-capture.md`）在同花顺桥里名为 NULL，会像 09-28 一样在 `limit-stats-local` 被 `InvalidStockName` 拦下。当日收盘后封存捕获已就绪：`db/quote-captures/tencent/2026-09-29/`，receipt.json sha256 `ed4f4f961a6cc6874ec684b7ed73be1fd8de342594ce7b5a9e34d1419ff5be67`（合同 1，见 `2026-09-29-name-source-acceptance.md`）。

## 做了什么

- 新建并锁定同步根 `~/.finance-runtime/finance-sync-0e7f77025409` = fe9fdbfd7 + `git cherry-pick -x` 4 个提交：`9f5fc05e4`→`2532fda78`、`eed8a2cca`→`214f8512f`、`5b515777c`→`1c484ea82`、`c495d2ca8`→`0e7f77025`。相对冻结根只有 9 个文件不同（执行件 + 其测试、采集件 + 其测试、接线测试、`run_review_sync.py`、`recover_local_review.py`、`consumption_registry.yaml`、`test_recovery_refresh_integration.py`），逐个与已测试的 `c495d2ca8` 逐字一致。分支 `fix/nightly-attach-names-0929`（根提交 = 0e7f77025，本文档在其后）。
- **只改一处生产配置**：`~/Library/LaunchAgents/com.financeworkspace.daily-full-review-sync.plist` 的 `EnvironmentVariables.FINANCE_SYNC_CODE_ROOT`，旧值冻结根 → 新根；备份 `…plist.bak-pre-attach-20260929`；`launchctl bootout/bootstrap` 重载（`runs` 归 0，18:30 排期不变，`REVIEW_SYNC_PLAN=local`）。
- 新根 `state/runlog.md` 从冻结根拷入，追加式历史不断。
- **没动**：finalize plist（20:40）、`FINANCE_CODE_ROOT`、`nightly-full-review-s7.sh` 里写死的兜底默认值（仍是旧冻结根，plist 显式值优先）、生产库、任何 staging、旧冻结根。

## 校验（实测）

- 热修树：ruff 全绿；目标测试 40 + 注册表 24 + 全仓扫描类 354 通过；完整 Python 叶 15664 passed / 74 skipped / 2 xfailed / 0 failed（992 s）。前端 / e2e 叶未跑（无前端文件变动）。
- 对 09-28 失败库的 APFS 克隆做 `attach_capture_names --dry-run`（09-29，`--expect-receipt-sha256` 钉住）：capture_validated true、5559 条、93 批、sha 相符；克隆已删，证据库大小 / mtime / 0444 未变。
- 15:58 复核：三只新股封存值与盘后终值成交额 / 量差 0；抽样创业板 76 / 科创板 14 / 主板 50 无超容差差异（北交所 25 抽 1 只有盘后成交，非目标）；三只涨跌幅 = round((close/pre_close-1)*100, 2)，离舍入临界点远。
- 切换后：plist 相对备份仅该键一行不同；用 plist 自己的环境从新根做计划探针：`stock-daily → attach-capture-names → hithink-sector-kline …`，`run_step` 子进程 cwd = 新根，今晚封存路径 found。

## 边界

- 补名**全有或全无**：任一空名行对不上（来源非同花顺、封存里没有该股、close / pre_close / pct_chg 容差 1e-6、amount 容差 1e-4 亿）整次拒写、退出 2，夜跑仍会在补名步失败——不会比切换前更糟；不放宽 `InvalidStockName`，不猜名。
- 夜跑接线没传 `--expect-receipt-sha256`；封存 receipt 的 sha 由人核对（切换前后 16:14 均相符）。
- 只有 09-29 有封存；09-30 起若没有当日捕获，补名步 skip，行为与接线前一致，新股仍会被 `InvalidStockName` 拦下。**每日 15:00 后采集尚无人 / 无定时**，宇宙 = 前一日库 + `--extra-codes` 人工补新股，新股没有自动发现来源——另立单。
- 09-24（缺 `920201.BJ` 首日）与 09-28（名 NULL、名称来源待用户接受）的缺口不在本次范围。

## 今晚看什么（18:30 起）

- 新根 `skills/daily-full-review/state/runlog.md`：应有 `attach-capture-names | ok`，随后 `limit-stats-local | ok`；补名收据在 `db/quote-captures/tencent/attach-receipts/`；日志 `logs/daily-full-review.{out,err}.log`。
- 若补名步失败：夜跑照旧失败、staging 保留（`remove_stale_staging` 只删 `.staging` 名字，不碰 `db/incident-20260928/`）；据收据里的 problems 定因，不要放宽校验。

## 回滚

`sh /tmp/wt-audit/rollback-sync-root.sh`（在 Mac 上，/tmp 重启会丢）；或手动：`cp -p <plist>.bak-pre-attach-20260929 <plist>` → `launchctl bootout gui/$(id -u)/com.financeworkspace.daily-full-review-sync` → `launchctl bootstrap gui/$(id -u) <plist>`。新根保留（已锁定）、不再被引用。

## 未做

- PR（`feat/dated-quote-capture-0929` → main）评审、以「main + PR」合并结果跑四叶、合并；合并后是否把同步根从热修根升级为 main 根（installer 不会自动按 HEAD 改 `FINANCE_SYNC_CODE_ROOT`），以及入口脚本兜底默认值是否随之更新。

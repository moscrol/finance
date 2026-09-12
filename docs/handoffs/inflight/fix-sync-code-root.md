# fix/sync-code-root · 夜跑代码根与补跑入口

## 状态：未推未合。全量在冻结提交 `8d0a438c` 的干净树上跑，**结果未出**

## 完成口径（别放宽）

已修：`unknown plan 'local'` 的代码根原因、质检闸门读错树、补跑入口绕开 staging、
手动入口不自带缺省。**真实同步、最终检查、方法日步仍未贯通验收**——9-11 未入库，
日报与 L2 完成记录仍缺。

装机配置只能说到「**已重载、字段与仓内源一致**」：两个 launchd 任务当前
runs=0 / never exited，`launchctl list` 那个 0 是「无失败记录」，**不是「跑成功过」**。

## 五处同一形状：根解析缺省落到会漂的共用树

主检出树 `finance-workspace-private` detached 在 `b4a35fa2`、落后 gitea/main 548 个
提交、带 64 个别人的未提交改动（含 `scripts/moneyflow/` 的在途 WIP）。

| # | 处 | 状态 |
|---|---|---|
| 1 | sync 子进程 `SYNC_ROOT` 缺省 `FINANCE_DATA_ROOT` | 已修（plist 显式给值） |
| 2 | 三处质检闸门裸相对路径 + `cd "$WORKSPACE"` | 已修（`$CODE_ROOT`，缺了 fail closed） |
| 3 | `run_sync()` 裸相对路径（手动补跑入口） | 已修（`$SYNC_CODE_ROOT`） |
| 4 | 两个手动入口不自带缺省，靠终端碰巧有变量 | 已修（脚本内缺省 + export） |
| 5 | **生成段 `python -m intelligence.cli daily`** | **未修，另单** |

第 5 条：`-m` 把 cwd 放进 `sys.path[0]`（实测空串），`intelligence` 仍从主检出树加载
（实测 `/Users/a77/finance-workspace-private/intelligence/__init__.py`）。
**闸门与同步器修对根 ≠ 整个 finalize 修对根。** 调用点与 SKILL.md 各留了指针。

## 补跑必须走 S7 入口

`run_review_sync.py` 自己**不做** staging——写的就是 `MARKET_FEATURE_STORE_DB` 指向的
库。克隆 staging / 过闸 / 原子换名全在 `nightly-review-sync-staged.py`。
直跑同步器 + 指向生产 = 直写生产，中途失败留下改了一半的库。
用 `nightly-full-review-s7.sh <date>` + `nightly_full_review.sh finalize <date>`。

## 装机副本

仓内源与装机副本两边都改了（`install_eval_launchd.sh` 是 `cp 源 → dest`）。
装机的 `nightly_full_review.sh` 是**外科式打补丁不是覆盖**——它与仓内版另有差异，
其中 moneyflow 根用 `$DATA_ROOT` 是因为 L2 的在途 WIP 在主检出树里，**别跑安装脚本
覆盖它**。同族普查：其余 5 个装机脚本 + 6 份 plist 与仓内源全部一致。

## 未决

1. **9-11 补数**：用户手动 `/daily-full-review`，走 S7 入口。
2. 名单基线停在 9-02；同花顺日更没接进 `local` 的 16 步（相关表停在 9-08）。
   两条是数据面缺口，不在本分支改动面，未立单，**本轮也未复算**。
3. 生成段代码根（上表第 5 条）另单。

## 关联分支 feat/method-closed-loop（非本分支）

`22c60030` LOG_DIR 顺序、`607f53a6` 旧 CLI 探针。我复验的**只是**新旧 CLI 分流那条
（旧=探不到走默认、新=探到走指针）与 exit 2 的二义拆分，**不是整体结案**。
`active --help` 不能当探针（argparse 优先处理 `--help`，两边都返 0）。

背景与被否方案见 `docs/handoffs/2026-09-12-nightly-code-root-outage.md`。

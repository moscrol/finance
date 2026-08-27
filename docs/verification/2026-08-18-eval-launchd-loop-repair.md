# 验证：评估/运维 launchd 在线环接线修复

日期：2026-08-18
执行树：`/Users/a77/fwp-wt-eval-launchd-repair` `fix/eval-launchd-loop-repair`
派单：`docs/handoffs/2026-08-18-eval-launchd-loop-repair.md`（#172）
红线：修接线不修判分；回补走原管线重放；未切 8792（pid **24113** 全程未换）

## 接线结果（2026-08-18 02:10–02:25）

六个 job 已从仓内源重装到 `~/Library/LaunchAgents/`，wrapper 落到 `~/.local/bin/`（不依赖 8792 快照里的旧 `.sh`）。解释器一律
`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（3.12，有 `TypeAlias`）。代码树一律
`~/finance-workspace-runtime`（当时 `d1be2d0c`，git 仓、干净）。

重装命令：`scripts/install_eval_launchd.sh`（可选 `--kickstart`）。装机副本与仓内源 `diff` 干净。

健康日志：`~/.finance-runtime/ops-health.log`（UTC 一行/次，含 python / code_root / rc）。

| job | kickstart / 重放 | 退出码 | 含义 |
|---|---|---|---|
| `fidelity-daily-agent` | kickstart 今日 08-18 | 0 | 无 `fact_market_daily` 行，skip（日历日不是交易日） |
| 同上 | 原脚本 `--date 2026-08-17` | 0 | theme 50 候选 + agent-daily 落盘（约 72s） |
| `fidelity-forward-acceptance` | kickstart 08-18 | 0 | skip 无交易日行 |
| 同上 | `--date 2026-08-17` | 1 | **接线已通**（git=`d1be2d0c`，不再 128/`TypeAlias`）；`result=blocked` 是既有判分（pit pending / generator 不一致），未改尺子 |
| `pit-snapshot` | kickstart | 2 | freeze 跑通，`already_frozen` + `validation_status=valid`；CLI 对 `status=pending` 返回 2（既有契约）。pending 原因：`required_failures=['fact_sw_l1_daily']`（SW 一级最新 08-14）。**未改 freeze 判分** |
| `checkpoint-recheck` | kickstart | 0 | 回检并落盘 11 条；可读日志 `agent-memory/可证伪点回检/2026-08-18.md` |
| `daily-full-review-finalize` | kickstart | 2 | 守卫：08-18 尚无行情行（最新 08-17）。venv python 已进闸。未强跑生成段 |
| `daily-full-review-sync` | **未**在 02:25 对 08-18 强跑全量 S7 | — | 非交易时段；下一窗口 18:30 自动跑。脚本语法 + 解释器解析已绿 |

`MARKET_FEATURE_STORE_DB` 在 plist 里指向 private 库，是 #164/#167 落地前的 env 止血件，台账标临时。

## 黑暗期（最后一次成功 → 2026-08-18 修复日）

| 产物 | 最后一次成功（修复前） | 黑暗期 | 证据 |
|---|---|---|---|
| fidelity daily-agent 判分/日报 | out.log 从 08-13 起连续 skip；其后 TypeAlias 炸 | 2026-08-13 → 2026-08-18 | `fidelity-daily-agent.out.log` / `.err.log` |
| forward-acceptance 记录 | `git rev-parse` 于 `88b28ab4-standalone` 退 128 | 至少 08-12 前后 → 2026-08-18 | err 栈 |
| pit 快照 | 08-17 文件在，但 `status=pending`；08-07/08-12 `generator_commit=''`；08-15/16 周末缺 | 空 commit 的 08-07/12 起校验会卡旧 as_of；新交易日 08-13 起又能写出 | 目录 listing + manifest 字段 |
| checkpoint 回检 | `ModuleNotFoundError: intelligence`（CLT python3 + 空 `finance-workspace-recheck`） | 自装错解释器起 → 2026-08-18 | `checkpoint-recheck.err.log` 6 行重复 |
| 复盘会 exports / `ops_pipeline_run_daily` | exports 最新业务日 **08-13**；ops 行停在 08-13（l2-moneyflow failed）/ 08-12（fupanhui-public-assets complete） | 2026-08-13 → 仍在 | DuckDB 查询；exports mtime |
| 行情主表 | `fact_market_daily` max **08-17** | 不停 | 另一条同步，不归这六个管 |

不许把今晚修好写成「一直好着」。08-13 至 08-17 的复盘会 exports **没有**被今晚的接线重放补上。

## 回补裁决（用户可否决）

一律原管线重放，不手搓行。

| 类 | 裁决 | 理由 |
|---|---|---|
| 2026-08-17 fidelity theme + daily-agent | **已补** | `run_fidelity_daily_agent.sh 2026-08-17` 原脚本；产物 `exports/2026-08-17-daily-agent.json`（02:25） |
| 2026-08-17 forward-acceptance 记录 | **已补（blocked 原样入账）** | 原 `record` 子命令；blocker 是判分不是接线 |
| 2026-08-13 / 08-14 fidelity | **建议补、本单未跑** | 同脚本 `--date`；各约 1–2 分钟。周末 08-15/16 **不补** |
| pit 08-07 / 08-12 空 `generator_commit` | **不补** | 已冻结对；手改或删了重冻会改 PIT hash。记 replay-ineligible |
| pit 08-15 / 08-16 | **不补** | 周末非交易日 |
| pit `fact_sw_l1_daily` 缺口（08-15 起） | **不在本单** | 判分/数据面；应走原 sync 管线补 SW 一级，另单 |
| checkpoint 积压到期点 | **已用原 CLI 重放今晚** | 11 条；更早漏跑的历史点若未到期则本来就不会进本 job |
| 08-13 以来复盘会 exports / ops 行 | **建议下一交易日 18:30 起自动恢复；不在 02:25 对 08-18 强跑 S7** | 08-18 尚无行情。若要补 08-14/08-17 的 fupanhui/exports，用 `nightly-full-review-s7.sh <date>` 原管线，需 CDP/登录态，用户拍了再跑 |
| DuckDB 撞锁 | **接线已加等待** | `REVIEW_GATE_LOCK_ATTEMPTS=36` × 10s；`ops_wait_duckdb_unlocked` 在 S7 入口。未改 `connect()` 写路径本体 |

## 顺手发现、未改判分

1. **隐藏临时文件名 vs 日期校验**：`.${D}-theme-candidates...json` 的 `Path.name[:10]` 得到 `.2026-08-1`。以前 daily-agent 从未跑过契约校验（先被 skip/TypeAlias 挡住）。已改为与 `sys.argv[2]`（真正的 `$D`）比较。不是放宽 fidelity 合同。
2. **pit pending**：SW 一级停在 08-14。freeze CLI 对 pending 退 2，保持。
3. **forward blocked**：pit `generator_commit=96446a93` vs 今晚 runtime `d1be2d0c`，以及 pit 冻结时 daily-agent 还不存在。这是时间线/判分，不改尺子。

## 重装步骤（下任）

```bash
# 在含本提交的树里
/bin/zsh scripts/install_eval_launchd.sh          # 只装，不跑
/bin/zsh scripts/install_eval_launchd.sh --kickstart  # 装完立刻跑一轮
# 不要 bootout com.a77.finance-workbench
```

核对：`diff` 仓内 plist 与 `~/Library/LaunchAgents/com.financeworkspace.*.plist`；`tail ~/.finance-runtime/ops-health.log`。

## 冻结 30 题 live 基线（#172 第二张）

**本单未开跑。** 先决是数据根代码面（handoff 写 #164；实现 PR **#167 仍 open**）。#164 只是文档派单。未合 #167 就跑会记下「无市场数据」残废基线。等 #167 合入且 sidecar 继承后再跑；不要与降级基线混序对比。

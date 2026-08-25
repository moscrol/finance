# docs/intraday-l2-sidecar

## 这个分支做什么

把 2026-08-25 摸底**没做完的后三步**落成独立设计稿。第一步（库存表进 `finance_query`）已在 PR #396，不是本单。

## 当前状态

正文：`docs/superpowers/specs/2026-08-26-intraday-l2-sidecar-design.md`（Draft v1，08-26 夜补 P0 前置校正）。
树：`/Users/a77/fwp-wt-intraday-l2-sidecar` ← `gitea/main@fe657cbc`。

P0 探针已落地：`scripts/moneyflow/probe_intraday_write.py`（ruff 绿，只读，复用
`make_client()`；双采样 + 服务器时钟偏移实测 + 午休交易秒滞后 + 腾讯开市核对；
收据落 `~/.finance-runtime/intraday-l2-probe/`，`--check-only` 只验链路不写收据）。

**P0 被鉴权挡住，探针本身没问题**：08-26 01:5x `--check-only` 实测 Code 516
Authentication failed（`hisdata180@36.139.233.80`）。不是新故障——`feature_l2_*`
自 08-07 停更，08-18 用户指示挂账（`state/l2-paused.flag`，
`reason=l2-datasource-auth-pending`），凭证 `~/.secrets/clickhouse.env` 还是 07-07 的。
摸底与设计稿初版都没交叉引用那份挂账交接，已回写 §3.4 校正 / §5.1 前置 / §8.1。

## 下一步

1. **77 先恢复 L2 鉴权**（供应商侧续期/取新密码 → 更新 `~/.secrets/clickhouse.env`）。
   不恢复则 P0/E4/P2 数据面搁置，P1 只剩 0 档。
2. 鉴权好了之后，交易日 10:00–14:30 在本树跑：
   `cd scripts/moneyflow && python3 probe_intraday_write.py`
   （盘后先 `--check-only` 验鉴权；正式跑写收据、退出码 0=有结论。）
3. 77 拍两扇门，或说「按推荐：A1 + B1」。
4. 再开 `feat/intraday-l2-sidecar` 做 P1。不要在 #396 那棵树上做。

## 不要做

- 不要和 `market-watch` 四袋稿搞混（那是盘后组件包）。
- 不要再登记 `_DATASETS`。
- 不要改 daily-full 的 `push2delay`。
- 不要等 #396 合 main。
- 不要拿 `connect_error` 收据当「盘中不写」的结论。
- 探针每次只发个位数条轻量聚合；不准顺手跑 `scan_*`、不准盘中全市场扫描。

# mootdx 停供护栏 + 同花顺→canonical 桥

## 这个分支做什么
定位 mootdx 返 0 行根因并加护栏；抢救 staging 里将被销毁的增量；建并验证
`fact_stock_daily_hithink` → `fact_stock_daily` 的桥。**一行未写生产库。**

## 为什么要这座桥
`fact_stock_daily` 缺当日行 → 13 个下游步骤全塌 → 夜跑 rc=2 → 不换名 →
当晚已抓到的 6 类同花顺数据（65,542 行）一并丢弃 → 次日重演。09-21 与
09-22 日志一字不差。同花顺自己的表反而最健康，缺的只是搬运通道。

## 决策与被否方案
| 选了什么 | 否了什么 / 理由 |
|---|---|
| 判 mootdx 供应商停供，不修客户端 | 39 台扫描 15 台可连，K 线 body 恒 2 字节，报文与 pytdx 1.72 逐字段一致 |
| 桥复用 `preview_stock_calculation` | 不重写除息/舍入；那套已在 09-11 验证过 |
| bridge 默认拒绝覆盖已有行 | 有旧行是 repair 的场景；两者分工写在模块 docstring |
| 指纹用整数 hash 求和 | 浮点求和不满足结合律，DuckDB 并行分片实测同数据 5 次出 3 个值 |
| 越界校验放 COMMIT 之前 | 放之后只能报警、回滚不了 |

## 当前状态
`d0815dd67` mootdx 护栏（12 测试）、`49bd531e6` 桥可行性证据、本次新增
`market_feature_store/sync/bridge_hithink_stock_daily.py` + 16 测试。
证据在 `tmp/mootdx-unblock-20260922/`（gitignore，**不可再生**）：
`staging-delta-20260922.tar.gz`（15 表 135,737 行）、`bridge-backtest-0918.json`、
`exdiv-agreement-0918.json`、`bridge-e2e-result.json`、`bridge-derived-rebuild.json`。
`bridge-e2e.duckdb`（3.5G，生产库 clonefile 副本）是验证现场，可删。

## 已验证
- 09-18 回测（该日有东财权威行）：**OHLC 5552/5552 逐位一致**；派生字段
  5550/5552 相等；30 只除息股中 28 只 `pre_close` 完全一致。
- 隔离副本端到端：09-21/09-22 各写 5551 行，其他日期指纹不变，生产库四表行数不变。
  09-22 的 `pre_close` 精确等于桥自己写的 09-21 `close`（链条自洽）。
- **09-22 全链打通**：`compute_features` 返回 complete，
  `feature_stock_window` 22130 / `technical` 5530（09-18 基线 22133 / 5531）。

## 未验证 / 已知边界
- **09-21 仍被第二个缺口卡住**：`fact_market_daily` 没有 09-21 这一行（该表只有
  09-16/17/18/22），`compute_features` 因此拒跑。它确实是交易日（5553 只有 bar）。
  这一行需另行抓取，桥不生产它。
- 两家对分红金额分歧 2 只（`000703.SZ` 0.90/0.82、`002255.SZ` 0.06/0.05），需第三方仲裁。
- 名单差异已解释未签合同：`302132.SZ`（东财漏收）、`688496.SH`（停牌，同花顺正确不含）。
- `turnover`（换手率）同花顺不提供，桥写 NULL。全市场范围口径（5553 vs 另一分支
  5565 并集）未定。未取写库授权。

## 踩过的坑
两表同名列语义全错位：同花顺 `turnover` 是成交额（元，÷1e8 得 amount）、`volume`
是股（÷100 得手），而 `fact_stock_daily.turnover` 是换手率。按同名列 INSERT 会灌进
量级差 1e8 的脏数据。删文件前必须比 `(inode,size,mtime_ns)`。`rows` 是 DuckDB 保留字。

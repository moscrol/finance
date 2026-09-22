# mootdx 停供排障 + 同花顺桥可行性验证

## 这个分支做什么
定位 mootdx 返 0 行根因并加护栏；抢救 staging 里将被销毁的增量；只读验证「同花顺→`fact_stock_daily`」这座桥。不写生产库。

## 决策与被否方案
| 选了什么 | 否了什么 / 理由 |
|---|---|
| 判定 mootdx 为供应商停供，停止修客户端 | 39 台扫描 15 台可连，K 线 body 恒 2 字节，报文与 pytdx 1.72 逐字段一致 |
| 护栏：三态探针 + 熔断 + `rc=2` | 不再让 `rc=0` 掩盖 `rows_written=0` |
| 先抢救 staging 增量 | 同花顺增量是 10 交易日滚动窗口，不保则 09-09 起逐日永久丢失 |
| 复用主线 `preview_stock_calculation` | 不重写除息/舍入算术；不新写 ingest（与 `fwp-wt-market-recovery-0921` 互补）|
| 不套 `SPEC_20260921` | 它假设当日已有旧行；09-21 整日 0 行会让 5553 只全落 `new_code_names` |

## 当前状态
已提交 `d0815dd67`（mootdx 护栏 + 12 测试）。证据全在 `tmp/mootdx-unblock-20260922/`（gitignore，**不可再生**）：`staging-delta-20260922.tar.gz`（2.3MB，sha256 见同名 .sha256）含 15 表 135,737 行；`diagnosis-conclusion.json` / `server-sweep.json` / `bridge-backtest-0918.json` / `exdiv-agreement-0918.json` / `full-market-preview.json`。

## 已验证
- 护栏端到端：`sync-stock-daily` 由 `rc=0` 变 `rc=2`，附 verdict/server/异常原文。测试 12+21 通过，Ruff 绿。
- 增量保全：边界日 09-08 与生产库**逐行零差异**，15 个 parquet 均可独立读回。
- 桥回测（09-18，有东财权威答案）：5553 只全算通、0 缺口；**OHLC 5552/5552 逐位一致**；`pre_close/pct_chg/amount/volume` 5550/5552 相等。
- 除息日 30 只中 **28 只 `pre_close` 完全一致**。
- 09-21/09-22 全市场预演：算通 5551/5553 与 5551/5554（99.96%/99.95%）。

## 未验证 / 已知边界
两家对分红金额分歧 2 只（`000703.SZ` 0.90/0.82；`002255.SZ` 0.06/0.05），需第三方仲裁。名单差异 2 只已解释未签合同：`302132.SZ`（东财漏收，与 SPEC_20260911 一致）、`688496.SH`（停牌，同花顺正确不含）。`stock_name`/`turnover` 同花顺不提供。全市场范围口径（5553 vs 另一分支 5565 并集）未定。桥**没有写者**，未取写库授权。

## 下一步
夜跑处于恶性循环：`fact_stock_daily` 缺当日行 → 13 个下游步骤全塌 → `rc=2` 不换名 → 当晚成功抓到的 6 类同花顺数据（65,542 行）全丢 → 次日重演（09-21、09-22 日志一字不差）。要打破它，需签三项政策（`turnover`=NULL、`stock_name` 取库内历史名标 unverified、停牌股留分母不造 K 线）+ 仲裁上述 4 只具名例外，再建写者并按阶段取授权。

## 踩过的坑
两表同名列语义全错位：同花顺 `turnover` 是成交额（元，÷1e8 得 amount）、`volume` 是股（÷100 得手），而 `fact_stock_daily.turnover` 是换手率。按同名列对齐 INSERT 会灌进量级差 1e8 的脏数据。删文件前必须比 `(inode,size,mtime_ns)`——这道检查拦下了一次 staging 误删。`rows` 是 DuckDB 保留字。

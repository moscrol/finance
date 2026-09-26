# mootdx 停供护栏 + 同花顺→canonical 桥（PR #871；工单 #61 目标 2）

## 这个分支做什么
mootdx 返 0 行加护栏；抢救 staging 里将被销毁的增量；建 `fact_stock_daily_hithink` → `fact_stock_daily` 的桥，补回 09-21/09-22 并接进夜跑兜底。缺当日行 → 13 个下游步骤全塌 → 夜跑 rc=2 → 当晚抓到的同花顺数据一并丢弃；同花顺表最健康，缺的只是搬运通道。

## 决策与被否方案
| 选了什么 | 否了什么 / 理由 |
|---|---|
| 判 mootdx 供应商停供，不修客户端 | 39 台扫描 15 台可连，K 线 body 恒 2 字节 |
| 桥复用 `preview_stock_calculation` | 不重写除息/舍入；09-11 已验证 |
| 桥默认拒绝覆盖已有行 | 该守卫让它成为天然兜底：主源成功即自动跳过 |
| 还原按**主键**反连接 | 按「晚于库内最大日」会漏掉补录的过去 ex_date |
| 指纹用整数 hash 求和 | 浮点求和在 DuckDB 并行分片下同数据 5 次出 3 个值 |
| 越界校验放 COMMIT 之前 | 放之后只能报警、回滚不了 |

## 当前状态
已前向到 `gitea/main@6f4265256`（`ecde76527`），PR **#871** → main，正文写明已写过生产一次。本 docs 提交后跑四叶（python 全仓 + registry-check；webapp 零 diff），读数贴 PR 评论，之后不再提交。合同枝 #861；五问 + 三合同决策页在 #861 的 `docs/handoffs/2026-09-22-market-recovery-decision-page.md`。

## 已执行（已获授权）
2026-09-22 21:47 换库 `run_id=92f6604e22f4`，staging 克隆 + 闸门 + 原子换名。回滚点 `db/market_feature_store.duckdb.bak-20260922T214745-92f6604e22f4`（sha256 + 恢复步骤收据）。主表 +11,102 行（09-21/09-22 各 5551）、同花顺表 +55,510。失败 staging 挪至 `tmp/…/failed-nightly-staging-92f6604e22f4.duckdb`。夜跑已加 `bridge-stock-daily` 步骤。

## 已验证
- 09-18 回测：OHLC 5552/5552 逐位一致，派生字段 5550/5552；30 只除息股 28 只 `pre_close` 一致。
- 换库前在一次性副本上跑完整套脚本含换名彩排。
- 链条闸：09-22 `pre_close == round(09-21 close − 当日红利, 2)`，5549 只零例外。
- 全量测试 1862 passed / 62 skipped（前向前）。

## 未验证 / 已知边界
- `fact_market_daily` 无 09-21 行 → `compute_features` 拒跑 → 该日 `feature_stock_*` 0 行。
- 分红金额分歧 2 只（`000703.SZ`、`002255.SZ`）待仲裁；53 只除权/送转被正确拒写待处置（五问 d）。
- `turnover` 写 NULL；`stock_name` 取库内历史名标 unverified；范围 5553 vs 5565 未定。
- 工单步骤 4 阳性对照读数见 #871 评论。

## 踩过的坑
同花顺 `turnover` 是成交额（元）、`volume` 是股，而 `fact_stock_daily.turnover` 是换手率。链条闸不能简单比 `pre_close == 前收`（除息日全误报），也不能用 0.005 容差。`DB_PATH` 默认解析到**本工作树** `db/`，跑生产必须显式 `MARKET_FEATURE_STORE_DB`。`rows` 是 DuckDB 保留字。

# Market Snapshot Provider Chain 设计

## 背景与问题

P1 已实现 AkShare 独立 venv、代理清理、Eastmoney/Sina 双端点和严格
`quality/freshness` contract，但 2026-07-16 的隔离真实验收仍得到：

```text
stock_zh_a_spot_em -> RemoteDisconnected
stock_zh_a_spot    -> RemoteDisconnected
exit=3, quality=partial
```

这证明公开 HTTP 行情端点不能作为 canonical 唯一来源。与此同时，本机
`db/market_feature_store.duckdb` 已有 2026-07-15 的完整事实层：5524 条个股行情、
224 条板块行情、市场总览和 4 个主线题材。成熟产品应优先复用已经进入治理链的内部
事实，外部公开接口只负责补最新日。

## 方案选择

### 采用：DuckDB exact-date → AkShare exact-date → DuckDB latest-complete

1. 目标交易日在 DuckDB 已完整落地：直接生成 complete snapshot。
2. DuckDB 尚无目标日：在临时目录调用独立 AkShare worker。
3. AkShare complete：原子发布目标日。
4. AkShare partial/failed：不把临时文件发布到 canonical，改用 DuckDB 最近一个完整日，
   标记 `freshness=historical` 并保留 provider attempt telemetry。
5. 三层都不可用：保持旧 complete snapshot，不改 `latest/meta`，同步返回非零。

### 未采用：继续叠加第三个公开端点

优点是改动较小；缺点是同样受反爬、域名、代理和返回字段变更影响，无法提供稳定的
canonical 事实层。后续可以作为新的 exact-date provider 插入链中，但不应替代 DuckDB。

### 未采用：继续以 partial 维持 readiness

这会让缺少全市场涨跌家数、成交额和广度的数据冒充可决策事实，与 P0.5 的 fail-closed
原则冲突。

## 架构边界

### DuckDB provider

新增独立 service，只负责：

- 以 read-only 方式打开 canonical DuckDB；
- 选择 exact date 或不晚于目标日的 latest date；
- 将 `fact_market_daily`、`fact_stock_daily`、`fact_sector_daily`、
  `fact_mainline_sector_daily` 映射到 snapshot contract；
- 在发布前执行数据完整度门禁；
- 返回候选 document 和 provenance，不负责调用 AkShare。

complete 门槛：

- 必须有一条 `fact_market_daily`；
- `fact_stock_daily` 至少 4000 行；
- `stock_ts_code/pct_chg/amount` 非空率均至少 98%；
- 必须能生成至少一个 theme 和一个 strong stock；
- `source_data_date` 与所有查询日期一致，不跨日拼接。

主题优先聚合 `fact_mainline_sector_daily`；若当天主线表为空，使用
`fact_sector_daily` 强度/涨幅靠前板块并显式写
`trigger_types=["duckdb_sector_strength"]`，不伪称主线。

### Provider orchestrator

新增编排 service/CLI，负责 provider 顺序、临时目录和原子发布。AkShare 仍在独立 venv
中运行，DuckDB provider 使用现有 Workbench Python；两者不共享传递依赖。

Provider attempt 记录：

- provider 名；
- requested/served trade date；
- quality/freshness；
- duration；
- error/skip 原因；
- 是否发布。

canonical 只保留 complete snapshot；partial 仅进入状态台账，不能写目标日、
`latest.json` 或 `meta.json`。

### 调度

LaunchAgent 继续工作日 16:15 运行，但入口从 AkShare-only runner 改为 provider-chain
runner。它使用：

- `/Users/a77/finance-workspace-runtime`：固定代码；
- `/Users/a77/finance-workspace-private`：数据根；
- `/Users/a77/finance-workspace-private/.venv-workbench`：DuckDB provider；
- `/Users/a77/.local/share/finance-workbench/akshare-venv`：AkShare provider。

## 数据映射

- `market.stage/total_amount/advancers/limit_up/limit_down`：来自
  `fact_market_daily`；decliners 由同日个股涨跌幅计算。
- `market.amount_ratio`：使用 `volume_ratio`，并在 provenance 标记字段映射。
- `market.capacity_top3`：使用市场表的前三行业及占比。
- `themes`：主线表按 theme 聚合；缺失时使用板块强度候选。
- `strong_stocks`：同日高涨幅股票按涨幅、成交额排序，限制 80 条；代码使用已有
  `stock_ts_code`，不重新猜交易所。

`source` 使用 `duckdb:market_feature_store`，并记录 source tables、数据库路径的逻辑名、
最大 `updated_at`；对外 JSON 不暴露绝对本机路径。

## Freshness 与 readiness

- exact target date → `freshness=fresh`；
- prior DuckDB complete date → `freshness=historical`；
- partial → `freshness=degraded` 且永不发布。

readiness 继续只接受 `complete + fresh|historical`。Workbench 回答必须展示 snapshot
实际日期；historical 表示服务可用但不能把旧盘面叙述为当天事实。未来若需要严格的
“收盘后必须当天”SLA，应另加交易日/时点 policy，而不是改变 snapshot 真实性。

## 错误处理与回滚

- 所有 provider 候选先写临时目录并通过 contract，再 `os.replace` 发布。
- 新同步失败不得覆盖现有 complete daily/latest/meta。
- DuckDB 只读连接，绝不执行 DDL/DML。
- AkShare subprocess 有绝对超时，超时后 terminate/kill。
- 状态台账独立原子写入，失败仍可审计。
- 回滚只需让 LaunchAgent 重新调用旧 AkShare runner；已生成的 DuckDB complete snapshot
  是派生数据，可保留。

## 验收标准

1. fixture 覆盖 exact DuckDB、AkShare complete、AkShare partial + historical DuckDB、
   三源失败与旧 complete 保全。
2. 使用 canonical DuckDB、临时输出目录真实生成 2026-07-15 snapshot，contract 必须
   `PASS + ready=true`，且 5524 行广度统计可核对。
3. 模拟 AkShare partial 时 canonical 目录不得出现目标日 partial 文件。
4. runner/plist 明确使用两个隔离 Python 环境。
5. readiness 对生成的 historical complete 返回 ready，并暴露实际日期/provider。
6. 全量 Python、前端、registry 与 E2E 回归保持通过。

## 明确不做

- 不增加 D6/D8 特征生成管线；
- 不让 Workbench API 请求同步行情；
- 不把 DuckDB 数据复制进 Git；
- 不把 historical 伪装成 fresh；
- 不承诺公开端点永久可用。

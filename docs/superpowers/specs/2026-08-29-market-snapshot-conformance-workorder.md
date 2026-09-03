# 2026-08-29 行情快照三源符合性套件工单（占位）

> 来源：`docs/verification/2026-08-29-conformance-seam-census.md`（缝普查 P1 #2）。
> 机制复用三件结构，参照 `intelligence/tests/conformance_tools/`。
>
> 状态：**已完成合并**（2026-08-29，PR #512 @`b90a7f6c`）。套件
> `intelligence/tests/conformance_snapshot/`，读数 **28 passed**、baseline 空
> （编排器单点收口的如实读数）。新增关键面：MS-1 对每一路发布产物跑
> `validate_market_snapshot_root`（此前无任何测试对发布结果跑校验器）。
> 交接：`docs/handoffs/inflight/test-market-snapshot-conformance.md`。

缝：`market_snapshot_sync.sync_market_snapshot`（L59）编排下的三源 provider 链
——`duckdb_exact`（L104-145）/ `akshare_exact`（L150-245，子进程）/
`duckdb_latest` 回退（L256-298），共享 `ProviderAttempt`（L30-41）与
`MarketSnapshotSyncResult`（L45-56）契约。三源分模块、分进程、分失败形状，
partial 污染与滞后钳事故在案。不变量草案：任一路发布的 snapshot 文档必须过
`validate_market_snapshot_root` 与 complete 不变量；降级必须显式
（`ProviderAttempt` 留痕，禁止静默回退——2026-06-22 sector 空壳回填的同族
失败形状：行数与覆盖率全绿、值是空的，只有跨源/跨日 diff 能抓）；回退链
顺序与放弃条件如实入收据。零网络：AkShare 路打假 runner，DuckDB 路用临时
只读小库。

验收：三源 × 全部不变量参数化跑通；与 `test_market_snapshot_sync.py` 既有
断言不重复；分支独立、pathspec 提交、不合 main。

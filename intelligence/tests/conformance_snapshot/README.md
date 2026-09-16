# 行情快照三源缝契约符合性套件

缝：`market_snapshot_sync.sync_market_snapshot` 编排下的供数链——
`existing_complete` 保护旁路 / `duckdb_exact` / `akshare_exact` / `duckdb_latest`
回退，共享 `ProviderAttempt` / `MarketSnapshotSyncResult` 契约。

来源工单：`docs/superpowers/specs/2026-08-29-market-snapshot-conformance-workorder.md`
（缝普查 P1 #2）；机制复用三件结构（参照 `conformance_tools/` / `conformance_datablocks/`）。

```bash
.venv-workbench/bin/python -m pytest intelligence/tests/conformance_snapshot/ -q
```

首轮读数（2026-08-29）：`28 passed`，baseline 为空（attempt/发布契约由编排器
单点收口，现状健康是如实读数——套件价值在棘轮：三源分模块、分进程、分失败
形状，各自演化时这里第一时间红）。

## 三件

| 文件 | 是什么 |
|---|---|
| `providers.py` | 参数表（旁路+三源）+ 声明表 + 场景驱动器（假 runner / 临时小库，零网络） |
| `baseline.py` | 棘轮 baseline（首轮为空） |
| `test_ms1..ms5_*.py` + `test_declarations.py` | 每不变量一文件，`parametrize(PROVIDER_NAMES)` 逐源跑 |

## 不变量 → 断言落点

| # | 不变量 | 断言落点 |
|---|---|---|
| MS-1 | 任一路发布的根目录必须过 `validate_market_snapshot_root`；发布文档带 requested/served/provider 全套；旧日回退不冒充当日；保护旁路零发布且原件字节不动 | 逐源发布场景 × root contract（2026-06-22 空壳家族的反面门） |
| MS-2 | 降级必须显式：落败/未配置的每一源都留带理由的 attempt 行；全败终态 ok=False 且零落盘 | 逐源落败场景 + runner 未配置 + 全败 |
| MS-3 | attempt 序列 = 链序前缀、首个成功即短路（其后零执行）、旁路命中整链零执行 | 逐源 + 全败走全链 |
| MS-4 | 每个终态落 status 收据且与返回值逐字段一致（运维读的是文件不是返回值） | 逐源 + 全败 |
| MS-5 | 发布门 fail-closed：非 complete / 缺 trade_date / 结构过不了 contract 的文档拒绝落盘、不污染发布目录 | 单点（`_publish_complete_document` 为三源唯一落盘口） |

## 与既有测试的分工（不重复）

`test_market_snapshot_sync.py` 盖**场景终态**（短路/发布/回退/保全的端到端断言）；
本套件盖**逐 provider 的统一契约**，新增的关键面是「发布产物过 root contract」
——此前没有任何测试对发布结果跑校验器。AkShare 子进程装配面归
`test_akshare_runtime_assets`；DuckDB 候选构造归 `test_duckdb_market_snapshot`
（本套件复用其 `_build_db` 夹具，不抄第二份 schema）。

## 怎么加新源

在编排器里接入新 provider 后：把名字加进 `providers.CHAIN_ORDER`（按真实尝试
顺序）、在 `run_publishing_scenario` 补最小发布场景、声明表自动展开。新源必须
全绿；有意的形状差异先写 `PROVIDER_NOTES`。

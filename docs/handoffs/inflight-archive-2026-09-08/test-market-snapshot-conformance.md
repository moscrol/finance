# 在途交接 · test/market-snapshot-conformance

- **工单**：`docs/superpowers/specs/2026-08-29-market-snapshot-conformance-workorder.md`
  （backlog INDEX #13，缝普查 P1 #2）。
- **分支状态**：套件建成，待验收合并。基线 main@`01d65edf`。
- **交付物**：`intelligence/tests/conformance_snapshot/`（providers/baseline +
  MS-1..MS-5 + 声明完整性 + README）。零生产代码 diff、零网络（AkShare 假
  runner；DuckDB 复用 `test_duckdb_market_snapshot._build_db` 临时小库）。
- **读数**：`28 passed`（2026-08-29，本分支）。baseline 为空——attempt/发布
  契约由编排器单点收口，现状健康是如实读数（判据同工具缝：单点强制层全
  SUPPORTED 不是套件没牙；本缝的牙在 MS-1 的 root contract 门——此前没有
  任何测试对发布产物跑校验器）。ruff 绿。
- **验收对照**（对照 #13 占位单）：
  - 三源 × 全部不变量参数化跑通 ✅（外加 existing_complete 旁路 = 4 供数面）
  - 「任一路发布的 snapshot 文档必须过 validate_market_snapshot_root 与
    complete 不变量」✅（MS-1，含旧日回退不冒充当日、保护旁路字节不动）
  - 「降级必须显式（ProviderAttempt 留痕，禁止静默回退）」✅（MS-2，含
    runner 未配置也留痕）
  - 「回退链顺序与放弃条件如实入收据」✅（MS-3 链序前缀 + MS-4 status
    收据逐字段镜像）
  - 零网络 ✅；与 `test_market_snapshot_sync.py` 既有断言不重复（分工表在
    README）✅
- **红线遵守**：pathspec 提交、未合 main、未改生产代码、零网络零 LLM。

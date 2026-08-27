# W5 duplicate / 参考日跟进 live（2026-08-19）

> 代码：`fix/w5-backfill-duplicate` @ `cf2bfaf1`（叠 `gitea/main` 含 #245）  
> sidecar：`:8796`，用户 `w5-dup`，`source_dirty=false`  
> 入口：`POST /api/conversations`，题目与 `docs/verification/2026-08-19-w5-backfill-live.md` 同一道阈值题  
> **生产 `:8792` 未切**，仍 `30f98d73`。  
> **结论：本刀要修的两件事过了。规格「补证后 completed」仍未过——挡住的是 `mainline_context`，不是 duplicate / stale。**

## 对照上一发（`850d6143` / `run_20260819_222138_157460`）

| | 修前 | 本发 `run_20260819_223516_391694`（30.1s） |
|---|---|---|
| `market_data` | stale：所需 08-19、供给 08-18，evidence=[] | **success**：requested=served=**2026-08-18**，8 条 |
| `duplicate_query` | 回填第二次 `market_data {}` 被拒 | **0** |
| `backfill_turns` | 1 | 1（仍因 `numeric_unsupported` 准入） |
| 预算帽 | 1 call / 22.5s | 同 |
| `verified_status` | `partial`（缺 market_data + mainline） | `partial`（**只剩 mainline_context**） |

## 判定

| 条 | 结果 |
|---|---|
| 空结果不占 duplicate 键 | **过**（本发甚至没再打出 duplicate） |
| 参考日不得超前 DuckDB | **过**（`market_data` 按 08-18 取到数；readiness 仍红 `market_data_consistency`，查询路径不再用 08-19 当 floor） |
| 回填后 `completed` | **未过**：结构层 `missing_mandatory_capability=mainline_context`。W5 触发集只有 numeric / 财务锚，不会为 mainline 开补证。 |

## 不在本刀

- 把 `mainline_context` 并进 `BACKFILL_TRIGGER_CODES`
- 链切 8792
- 合 #244（上一发读数，另单）

产物：`~/.finance-runtime/live-probe-traceability/w5-dup-cf2bfaf1/`。sidecar 已停。

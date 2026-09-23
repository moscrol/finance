# #65 交 #75 独立 QC 的候选包

本卡是 #65 的审查对象与证据指针，队列由 `docs/verification/2026-09-22-independent-qc-batch/QUEUE.md` 维护。09-23 实读审计树为 clean detached `da761024ed54c46b8e650d1b86076e1f9d261ed2`，含 #872 修复；开审前必须重核 HEAD 和干净状态，不能沿用早期卡片的 `6fc6bfa94`。本卡就绪不代表 #75 已开审或通过。

## 队列行（照 #75 的列序）

| 工单号 | PR | 被审 SHA（不是原 PR head） | 候选检出路径（绝对，独占只读） | 证据目录 | 主张清单来源 | 状态 |
|---|---|---|---|---|---|---|
| #65 | #850 / #854 / #872（均已入主干） | `da761024ed54c46b8e650d1b86076e1f9d261ed2` | `/Users/a77/fwp-gate-65-main/finance-workspace-private`（clean detached，保持冻结） | `docs/verification/2026-09-22-answer-claim-scope/`、`…-claim-scope-hardening/`、`…-claim-scope-backtest/`；本目录 README 与 `docs/handoffs/2026-09-23-claim-scope-ledger-negation-closeout.md` | #850 / #854 原主张；S5 审查两条发现及 #872 修复；不要把已修缺陷重复列为当前缺陷 | 事后审待执行；结论回写 INDEX #65，CHANGES_REQUIRED 另立修复单 |

审计树与 09-23 补验主干 `9a0227986` 的两份离线实现及两份测试逐文件相同；这只能连接该模块的证据，不能声称两棵整仓树相同或两者共用一份全量收据。

## 作者读数（与审查探针分开记账）

| 树 | 收据 | 读数 |
|---|---|---|
| #850 head `1cf35f51` | `~/.finance-runtime/test-receipts/20260922T154730Z-1cf35f51.json` | 定向 `intelligence/tests/test_answer_claim_scope.py` 31 passed，`dirty=false`。#850 head 上**没有** `tests/test_check_answer_claims.py`（该文件由 #854 新增），工单步骤 3 的定向集要按此收窄 |
| #854 head `5f5ce2d1` | 四叶收据见本目录 `README.md`（合并前补齐） | — |
| #872 head `0a258a098` | `~/.finance-runtime/test-receipts/gate-n4mE47Sb/pytest.json` | 14383 passed / 0 failed / 85 skipped / 2 xfailed，collected=14470；首轮 `b058a0a1` 因基座漂移超限作废，不采信 |

## 审查者值得压的三个点（作者视角外）

1. `_CLAIM_BINDING_WINDOW = 12`：限定词绑定窗口 12 字是经验值，找一句「限定词在 13 字外仍语义有效」的真实写法看是否误报。
2. `_LEDGER_FLOW` 台账判据：#872 已按子句排除否定语境；继续压**引用、跨子句、转述**等边界，不能仅重放旧的否定句就宣布审查完成。
3. `build_context` 只认 `_SECTOR_FIELDS` 三种 sector 字段：换一种真实取数形状（如按板块名而非代码过滤）看是否正确进 degraded 而非静默。

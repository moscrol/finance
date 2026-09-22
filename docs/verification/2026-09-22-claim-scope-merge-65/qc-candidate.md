# #65 交 #75 独立 QC 的候选包

#75 的队列文件 `docs/verification/<日期>-independent-qc-batch/QUEUE.md` 在 2026-09-22 23:50 尚不存在于任何本机检出（`ls /Users/a77/fwp-wt-*/docs/verification/*independent-qc*` 无命中），故候选行先落在这里并贴到两张 PR 评论；#75 建好队列后原样搬入。

## 队列行（照 #75 的列序）

| 工单号 | PR | head SHA | 候选检出路径（绝对，独占只读） | 证据目录 | 主张清单来源 | 状态 |
|---|---|---|---|---|---|---|
| #65 | #854（叠 #850）——**已合入** `6fc6bfa94` | `5f5ce2d114b238edd3f278504e5a25f35f31710d` | `/Users/a77/fwp-gate-65-main/finance-workspace-private`（detached @ 合后主干 `6fc6bfa94…`，独占只读） | 主干上 `docs/verification/2026-09-22-claim-scope-hardening/`、`…-claim-scope-backtest/`、`…-answer-claim-scope/` | PR #854 描述「修了什么」三条 + 「验证」表；PR #850 描述「内容」「检出器自己被真实语料抓出三个缺陷」；S5 第二方审查两条发现（`second-party-review.md`）作为已知起点 | 事后审（依用户授权已合，#75 结论回写 INDEX #65 行；CHANGES_REQUIRED 走后续单） |
| #65 | #850——**已合入** `a696c5e1d` | `1cf35f5167ed3adebbb7d6ce60a37f8b92c79d0c` | 同上 | `docs/verification/2026-09-22-answer-claim-scope/` | PR #850 描述 | 事后审（#850 ⊂ #854） |

## 作者读数（与审查探针分开记账）

| 树 | 收据 | 读数 |
|---|---|---|
| #850 head `1cf35f51` | `~/.finance-runtime/test-receipts/20260922T154730Z-1cf35f51.json` | 定向 `intelligence/tests/test_answer_claim_scope.py` 31 passed，`dirty=false`。#850 head 上**没有** `tests/test_check_answer_claims.py`（该文件由 #854 新增），工单步骤 3 的定向集要按此收窄 |
| #854 head `5f5ce2d1` | 四叶收据见本目录 `README.md`（合并前补齐） | — |

## 审查者值得压的三个点（作者视角外）

1. `_CLAIM_BINDING_WINDOW = 12`：限定词绑定窗口 12 字是经验值，找一句「限定词在 13 字外仍语义有效」的真实写法看是否误报。
2. `_LEDGER_FLOW` 台账正则：新闻正文里出现「净流入」即算资金流证据；找一条证据里「净流入」出现在**被否定/被引用**语境的样本，看是否把无证据判成有证据。
3. `build_context` 只认 `_SECTOR_FIELDS` 三种 sector 字段：换一种真实取数形状（如按板块名而非代码过滤）看是否正确进 degraded 而非静默。

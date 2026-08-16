# 2026-08-16 outlook 同题离线量测（R-20260816-03 预备）

roadmap_ref: R-20260816-03 / `docs/verification/2026-08-16-outlook-verification-budget-regression.md`

- 记账日: 2026-08-16
- 范围: 只读已落盘 episode。未占 8792，未调合成 LLM，未开 live 三臂。
- 题面: 「基于8.15的行情现状，你认为周一的机会在哪」
- `task_frame_hash`: `9a80be5bf31e90feadf55e1f4b4956c5de5c72ec3a9920dcaa6589c7030cf3a4`
- 数据日: `latest_data_date=2026-08-14`（用户口中的 8.15 不是本轮可用行情日）
- 禁止: 把 L04 chat 臂当对照；长尾窗收口前不另起 live 臂（与 8793 on 臂抢同一模型额度）。

## 1. 为什么还不是三臂结案

R-03 要的是单变量：只 #72（3-tool）/ 只第 4 次查询 / 四层全开。现有材料里 #72 与工具次数绑在一起：

| 样本 | revision 形状 | #72 `direct_answer` | 工具 | 证据条数 | detail 字 |
|---|---|---|---|---|---|
| pre1 `run_20260816_102941_554059` | `437cd5e9` | `evidence` | 3（无 `stock_high_daily`） | 35 | 3650 |
| pre2 `run_20260816_103318_230845` | `437cd5e9` | `evidence` | 3 | 35 | 3636 |
| L01 r1 `run_20260816_131941_597875` | `773b3d7e` | `model_reasoning` | 4（多 `stock_high_daily` 25 条） | 60 | 8036 |
| L01 r2 `run_20260816_141323_891938` | `773b3d7e` | `model_reasoning` | 规划 5 次；入账 2 张表 | 10 | 1608 |

r2 **不能**当 3-tool 对照：它在首轮研究窗就 `deadline_exhausted`，没有 `finalization`，TimeoutError 发生在 repair 再入场之后（`research_tools_open=true`）。和 r1「四次检索成功 → 首轮合成 68.3s 超时」不是同一条路径。

## 2. 体积差（只说明 H3 的量，不断因）

L01 r1 比 pre1 多出来的几乎全是 `stock_high_daily`：

- `stock_high_daily` detail **4444** 字 / 25 条
- 证据 detail 合计 3650 → 8036（约 2.2×）
- pre1 首轮合成成功：`input_tokens=17024`，draft 772 字
- L01 r1 首轮合成 TimeoutError：`input_tokens` 缺席（R-01 落地前无法对账）

体积变大是事实。它**不是**「60 条 / 第 4 次查询 ⇒ 必然空稿」的充分条件：pre2 在 35 条、无 #72 时首轮也 TimeoutError，但 30s 修复写出了 draft；r2 在 10 条时走另一条空稿路径。

H2（#72 提示变重）和 H3（第 4 次查询）仍然 **INCONCLUSIVE**。R-03 保持 `pending`。

## 3. 成功合成对照（pre1）

pre1 事件：规划 → 3 tool → `finalization.reason=retrieval_deadline_closed` → 合成成功（seq=12，17024/820）→ repair 把 `previous_draft_chars=0` 的账补成 `repair_model_finish`，episode draft 396 字。

pre2：首轮合成 TimeoutError（无 tokens）→ 修复 30s 写出 736 字。说明 30s 帽对「已经有可修草稿或合成其实跑得完」有效，对 r1「空稿且合成本身 >30s」无效。

## 4. live 三臂（收口后才开）

夹具冻结：同题、`as_of=2026-08-14`、同一 `task_frame_hash`。三臂：

1. #72 on + 冻结 3-tool（禁止 `stock_high_daily`）
2. #72 off + 允许第 4 次查询
3. 当前四层全开（与 L01 r1 同配方）

每臂只看：首轮 finalize `model_turn.timeout_asked`（#84）、`input_tokens`、draft 是否非空、`stop_reason`。L04 chat 不进对照。长尾 95 槽齐之前不跑。

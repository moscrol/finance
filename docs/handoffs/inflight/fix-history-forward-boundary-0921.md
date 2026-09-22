# fix/history-forward-boundary-0921 在途

整体 **CHANGES_REQUIRED / 未验收**。证据 `~/.finance-runtime/reviews/research-tail-formal-gate-20260922/summary.json`。未合、未推、未部署；#845 head 仍 `442476f7d`。

## 两个已固定对象
- 候选 `42784d27e` = `442476f7d` + #814 四文件**原样移植**（patch-id 同源、零产品改动，不建第二套门禁）
- 联合树 `de8b06732` = main `a2c8d1f9` + 候选 + runtime `cb16cd463`，**0 冲突**（main 已含集成基线 #831）

## 候选：正式门禁通过
`run_main_gate.sh` exit 0 / 981s，**12861P / 85S / 2X / 0F**；树外收据经 `main_gate_receipt.py` 复核 exit 0，负向控制（换 revision、谎报 pytest exit）各被拒 exit 4。前端 6 项全绿（110P、E2E 34P2S、build 产物与仓内静态资源逐字节一致），registry 5 项绿。
与 06 轮逐 ID 对账：新增 50 全来自 `test_main_gate_receipt.py`，消失 0，4 条变化因 `.code-review-graph/graph.db` 被 gitignore 致 code_map 互斥对换边。**覆盖差**：`test_structure_probe_daily_full` 本轮未跑（CI 同样不跑；06 那次用 `b6de1a38` 陈旧图）。

## 联合树：两绿一未完成
前端 6 项、registry 5 项全绿。**Python 叶未完成**：1968s 时被磁盘停止线中断（SIGINT，`stop_reason=disk-space-floor`，门禁 exit 4）。**不是测试红**——中断收据里的 12077P 和那条 hithink error 都是磁盘耗尽产物，不可当部分绿。成因是他人两个全量 pytest 吃掉约 20G。重跑需先留出 ~4G。

## 财务线进不来（真冲突，不是取舍）
`d82cb16b5` 与历史 6 文件 7 处、与 runtime 4 文件 5 处冲突，且是同一调用点的语义碰撞（`continuous_turn_adapter.py` 的 `contract_receipt`：历史加 `history_intent`，财务重写同一调用）。化解属作者级决定，未做。
历史∩runtime 有 4 个非测试 .py 文本合干净，语义仍押在那条未完成的 Python 叶上。

## 未验
独立终审、原四自然题、财务线与三领域全并、联合树 Python 叶；CI node22 vs 本机 node26。

## 坑
- `FWP_TEST_RECEIPT_DIR` 必须指树外；前端 build 会写 `intelligence/api/static`，须另开检出
- basetemp 一轮 2～3.4G 且含只读夹具，删前 `chmod -R u+w`；本机长期 97%+，多会话并跑会互相挤爆

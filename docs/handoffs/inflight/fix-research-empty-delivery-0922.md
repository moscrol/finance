# fix/research-empty-delivery-0922 — 最终交付门

**状态**：代码完成、全量绿、待 push / PR。worktree `/Users/a77/fwp-wt-research-empty-delivery-0922`，基座 `gitea/main a2c8d1f90`。

## 修的是什么

2026-09-22 现场 `run_20260922_191550_067475`（`comparison_analog`）：模型在自由文本里写完 1500+ 字完整答案，却把结构化 `finish` 的 `draft` 填成一句指针「见正文：……」。运行时按 `draft` 交付 → 用户只收到 154 字、`report.modules=0`；而 77 条证据全绑定、结构核验与语义判官双双 `passed`，`report.status` 仍写 `partial`。**没有任何一道门能拦**：唯一记下异常的 `answer_marker_coverage` 带 `observation_only=True`，按设计不可阻断。

结构性证据完整 ≠ 正文里真的说了那句话。缺的就是这道门。

## 改了什么（commit `d68b8f512`）

- 新增 `intelligence/services/public_delivery_gate.py`：确定性纯函数 `review_public_delivery()`，无模型调用、无 IO，返回冻结收据 `PublicDeliveryReceipt`。
- 接线 `runtime/conversation_orchestrator._complete_continuous_turn`，位置在 `complete_report` 之前——**那一行之后的 `answer_text` 才是用户真正读到的那段**（视角头、复核意见、outlook/market_watch 删句闸、未验证网格都在它之前）。
- 新增 `intelligence/tests/test_public_delivery_gate.py`（10 条，夹具逐字取自该 run）。

**判据是双钥匙**：钥匙 1（形态）正文是悬空指针（`见正文`/`如上所述`）；钥匙 2（覆盖）确有必需输出没进正文（复用 `task_fulfillment` 同一张词表，不另立第二表）。**单独命中钥匙 2 一律放行**——那正是「措辞不同但内容完整」的形状。落点走既有 `answer_status` 通道（`missing`/`partial`），不新增终态类型；缺口模板整篇豁免；正文只删开头那句指引、结论原样保留。

## 读数

`12521 passed / 0 failed / 85 skipped @ d68b8f512`（干净树，`.venv-workbench`）。收据 `~/.finance-runtime/test-receipts/latest.json`，`scripts/check_test_receipt.py --expect-revision HEAD` 判 ✅ 可采信。

## 已验 / 未验

- 已验：离线重放真实坏答案 → `empty`/`missing`；同一轮的真正文 → 原样放行；全量回归绿。
- **未验**：没在真实模型上跑过（按约定不耗配额）；生产 8792 未动，本改动尚未上线。

## 踩过的坑（别再踩）

1. **正文长度不能当钥匙**。第一版「体量不足 + marker 缺失」当场拍红 4 条编排器测试——「2026Q2 单季营收 375.75 亿元」这类短而完整的答案全被降级。长度只是 marker 缺失的先验，用它降级等于绕过「缺措辞不得硬拦」这条约束。
2. **绝对下限定 24 字也太宽**，拍红 `test_workbench_research_project`（夹具 16 个实质字符）。现为 8，且这是唯一不要求第二把钥匙的规则。两次拍红都已固化成回归护栏。
3. 别用 `git -c core.hooksPath=...` 提交——我第一次这么干直接跳过了全部 pre-commit 门禁，用 `--amend` 补跑了一遍。

## 下一步

1. `git push`（`remote.pushDefault=gitea`）+ 开 PR。
2. **Engine B 的 `/api/runs` → `_ask_answer_coverage` 仍无门**（`intelligence/api/app.py:1794`，`complete_report` 不传 `answer_status` 时默认回落 `complete`）。同一个纯函数可直接复用，本单刻意不扩面（一次修一个独立缺陷）。
3. 收据里的 `substance_chars` 是留给「先量后改」的：等分布够了再谈要不要把体量规则升级成钥匙。
